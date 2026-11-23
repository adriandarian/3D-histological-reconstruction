"""Generate serial optical sections and recover a branching duct from RGB alone.

Run python -m pipeline.branching [output directory]. Voxel centers use XYZ
coordinates, with image Y increasing downward and section Z increasing in order.
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

WIDTH, HEIGHT, DEPTH = 80, 72, 32
SPACING = [2, 2, 5]


def source_sections(seed=41):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[:HEIGHT, :WIDTH]
    tissue = ((x - 40) / 38) ** 2 + ((y - 36) / 33) ** 2 < 1
    images, truth = [], []
    for z in range(DEPTH):
        span = max(0, z - 10)
        lumen = np.zeros_like(tissue)
        for sign in (-1, 1):
            cx = 39 + sign * span * 0.94
            cy = 35 + sign * span * 0.36 + 2 * np.sin(z / 8)
            lumen |= (x - cx) ** 2 + (y - cy) ** 2 <= 4.3 ** 2
        # Optical blur, heterogeneous stain and isolated dark specks challenge
        # segmentation. The binary reference is never supplied to segment().
        coverage = cv2.GaussianBlur(lumen.astype(np.float32), (5, 5), 0.95)
        rgb = np.where(tissue[..., None], [215, 149, 178], [249, 249, 249])
        rgb = rgb * (1 - coverage[..., None]) + coverage[..., None] * [86, 48, 105]
        rgb += rng.normal(0, 5, rgb.shape)
        rgb[20 + z % 3, 30] = [85, 44, 95]
        images.append(np.uint8(np.clip(rgb, 0, 255)))
        truth.append(lumen)
    return np.stack(images), np.stack(truth)


def segment(rgb):
    labels = np.zeros(rgb.shape[:-1], dtype=np.uint8)
    labels[rgb[..., 1] < 205] = 1
    for z, section in enumerate(rgb):
        dark = np.uint8(section[..., 1] < 99)
        count, ids, stats, _ = cv2.connectedComponentsWithStats(dark, connectivity=4)
        for region in range(1, count):
            if stats[region, cv2.CC_STAT_AREA] >= 8:
                labels[z, ids == region] = 2
    return labels


def section_graph(mask):
    """Vertices are planar 4-connected regions, edges share a voxel face in Z."""
    slices = [cv2.connectedComponents(np.uint8(im), connectivity=4) for im in mask]
    incoming, outgoing = {}, {}
    counts = []
    for z, (count, ids) in enumerate(slices):
        counts.append(count - 1)
        for region in range(1, count):
            incoming[z, region] = 0
            outgoing[z, region] = 0
        if z:
            prev = slices[z - 1][1]
            overlap = (prev > 0) & (ids > 0)
            for parent, child in np.unique(np.stack((prev[overlap], ids[overlap]), axis=1), axis=0):
                outgoing[z - 1, parent] += 1
                incoming[z, child] += 1
    return {
        "regionsPerSection": counts,
        "roots": sorted(z for (z, _), n in incoming.items() if n == 0),
        "tips": sorted(z for (z, _), n in outgoing.items() if n == 0),
        "splits": sorted(z for (z, _), n in outgoing.items() if n > 1),
        "merges": sorted(z for (z, _), n in incoming.items() if n > 1),
    }


def surface(mask):
    """Triangulate the exterior faces of the segmented voxel union."""
    vertices, indices, lookup = [], [], {}
    padded = np.pad(mask, 1)
    for axis in range(3):
        for sign in (-1, 1):
            neighbor = [slice(1, -1)] * 3
            neighbor[2 - axis] = slice(None, -2) if sign < 0 else slice(2, None)
            for z, y, x in np.argwhere(mask & ~padded[tuple(neighbor)]):
                quad = []
                for a, b in [(-1, -1), (1, -1), (1, 1), (-1, 1)]:
                    point = [int(x), int(y), int(z)]
                    point[axis] += sign / 2
                    point[(axis + 1) % 3] += a / 2
                    point[(axis + 2) % 3] += b / 2
                    key = tuple(point)
                    if key not in lookup:
                        lookup[key] = len(vertices) // 3
                        vertices.extend(key)
                    quad.append(lookup[key])
                if sign < 0:
                    quad.reverse()
                i, j, k, m = quad
                indices.extend([i, j, k, i, k, m])
    return {"positions": vertices, "indices": indices}


def export(out):
    (out / "sections").mkdir(parents=True, exist_ok=True)
    images, truth = source_sections()
    sections = []
    for z, image in enumerate(images):
        name = f"sections/{z:03d}.png"
        Image.fromarray(image).save(out / name)
        sections.append(name)
    # Feed the segmentation the source PNGs from disk, just as with collected slides.
    stack = np.stack([np.asarray(Image.open(out / path).convert("RGB")) for path in sections])
    labels = segment(stack)
    prediction = labels == 2
    expected, observed = section_graph(truth), section_graph(prediction)
    report = {
        "dice": float(2 * np.count_nonzero(prediction & truth) / (prediction.sum() + truth.sum())),
        "referenceGraph": expected, "recoveredGraph": observed, "graphMatches": expected == observed,
    }
    stack.tofile(out / "rgb.bin")
    labels.tofile(out / "labels.bin")
    np.uint8(truth).tofile(out / "truth.bin")
    manifest = {
        "dimensions": [WIDTH, HEIGHT, DEPTH], "spacing": SPACING, "unit": "µm",
        "rgb": "rgb.bin", "labels": "labels.bin", "truth": "truth.bin",
        "mesh": "mesh.json", "validation": "validation.json", "sections": sections,
        "provenance": "Simulated optical sections on a known grid. Identity registration.",
    }
    for name, obj in [("mesh", surface(prediction)), ("validation", report), ("manifest", manifest)]:
        (out / f"{name}.json").write_text(json.dumps(obj, separators=(",", ":")) + "\n", encoding="utf8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=Path("public/branching"))
    print(json.dumps(export(parser.parse_args().output), indent=2))
