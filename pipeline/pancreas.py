"""Export a display-scale RGB volume and an exploratory pancreas cavity candidate."""

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage

from pipeline.branching import surface


def cavity_candidates(rgb, valid):
    """Find enclosed bright regions away from the sampled field boundary."""
    light = np.uint8(rgb.min(axis=-1) >= 205)
    count, regions, stats, _ = cv2.connectedComponentsWithStats(light, connectivity=4)
    inside = cv2.erode(valid.astype('uint8'), np.ones((3, 3), np.uint8),
                       borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    excluded = set(np.unique(regions[~inside]))
    keep = [i for i in range(1, count) if i not in excluded
            and 4 <= stats[i, cv2.CC_STAT_AREA] <= 160]
    return np.isin(regions, keep)


def longest_candidate(mask):
    """Require face contact between observed sections; never bridge a gap."""
    components, _ = ndimage.label(mask)
    counts = np.bincount(components.ravel())
    tracks = [(box[0].stop - box[0].start, counts[i], i)
              for i, box in enumerate(ndimage.find_objects(components), 1) if box]
    depth, _, label = max(tracks, default=(0, 0, 0))
    return components == label if depth >= 2 else np.zeros_like(mask)


def export(source, out):
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf8"))
    width, height = manifest["width"], manifest["height"]
    size = (width // 4, height // 4)
    with np.load(source / manifest["volume"]) as volume:
        def reduce_stack(key):
            return np.stack([cv2.resize(section.astype(np.uint8), size,
                                        interpolation=cv2.INTER_AREA) for section in volume[key]])
        rgb = reduce_stack("rgb")
        tissue = reduce_stack("tissue").astype(bool)
        valid = np.stack([cv2.resize(np.float32(s > 0), size, interpolation=cv2.INTER_AREA) == 1
                          for s in volume["valid"]])
    candidate = longest_candidate(np.stack([cavity_candidates(im, v) for im, v in zip(rgb, valid)]))
    labels = np.uint8(tissue & valid)
    foreground = labels.copy()
    labels[candidate] = 2
    out.mkdir(parents=True, exist_ok=True)
    rgb.tofile(out / "rgb.bin")
    labels.tofile(out / "labels.bin")
    foreground.tofile(out / "foreground.bin")
    mesh = surface(candidate)
    sections = [i + 1 for i, plane in enumerate(candidate) if plane.any()]
    report = dict(sections=sections, voxels=int(candidate.sum()), triangles=len(mesh["indices"]) // 3)
    metadata = dict(dimensions=[*size, len(rgb)], spacing=None, unit=None,
                    registrationSha256=hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest(),
                    name="Pancreas 10x", anatomyName="Unverified bright cavity",
                    provenance="Registered and downsampled from Roy et al. (2023), CC BY 4.0, doi:10.17632/fzskwpzs5j.1",
                    sections=["../data/real/" + row["source"] for row in manifest["sections"]],
                    foreground="foreground.bin", rgb="rgb.bin", labels="labels.bin",
                    mesh="mesh.json", validation="validation.json")
    for key, value in [("mesh", mesh), ("validation", report), ("manifest", metadata)]:
        (out / (key + ".json")).write_text(json.dumps(value, separators=(",", ":")) + "\n", encoding="utf8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(export(args.source, args.output))
