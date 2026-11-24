"""Audit measured source previews and perturb frozen adjacent mask contacts.

Run from the repository root. This writes numeric tables only. The source
exports and original scans are read-only; each case can be run separately.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import label

from scripts.tcia_prostate import section as tcia_section


CASES = {"coda": "public/data/coda-lung", "roy": "public/pancreas",
         "tcia": "public/tcia-prostate"}
SHIFTS = [(0, 0)] + [(dx * radius, dy * radius)
                       for radius in (2, 4)
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def contact_areas(earlier, later, dx, dy):
    """Translate the later labeled plane by (dx, dy) with no edge wraparound."""
    h, w = earlier.shape
    if abs(dx) >= w or abs(dy) >= h:
        return {}
    x0, x1 = max(0, dx), min(w, w + dx)
    y0, y1 = max(0, dy), min(h, h + dy)
    a = earlier[y0:y1, x0:x1]
    b = later[y0-dy:y1-dy, x0-dx:x1-dx]
    inside = (a > 0) & (b > 0)
    pairs, counts = np.unique(np.column_stack([a[inside], b[inside]]),
                              axis=0, return_counts=True)
    return {tuple(pair): int(count) for pair, count in zip(pairs, counts)}


def pair_ids(pairs):
    return "|".join(f"{a}>{b}" for a, b in sorted(pairs))


def source_planes(case, manifest, folder):
    if case == "coda":
        import openslide
        for meta in manifest["sourceSections"]:
            native = Path("data/coda-lung") / meta["slide"]
            with openslide.OpenSlide(str(native)) as slide:
                if slide.level_downsamples[3] != meta["step"]:
                    raise ValueError(f"Unexpected sampling on {native.name}")
                rgb = slide.read_region(tuple(meta["origin"]), 3, (640, 640)).convert("RGB")
            yield native, folder / meta["source"], np.asarray(rgb)
    elif case == "roy":
        registration = Path("public/data/real/manifest.json")
        if sha256(registration) != manifest["registrationSha256"]:
            raise ValueError("Pancreas source and target exports use different registrations")
        meta = json.loads(registration.read_text(encoding="utf-8"))
        for row, png in zip(meta["sections"], manifest["sections"], strict=True):
            native = Path("data/real") / row["filename"]
            with Image.open(native) as slide:
                rgb = ImageOps.exif_transpose(slide).convert("RGB")
            rgb.thumbnail((meta["width"], meta["height"]), Image.Resampling.LANCZOS)
            yield native, folder / png, np.asarray(rgb)
    else:
        for frame, png in zip(manifest["prostateFrames"], manifest["sections"], strict=True):
            native = Path("data/tcia/files") / frame["file"]
            rgb, regenerated_frame = tcia_section(native)
            if frame != regenerated_frame:
                raise ValueError(f"Different organ normalization for {native.name}")
            yield native, folder / png, rgb


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def audit(case, output):
    folder = Path(CASES[case])
    manifest_file = folder / "manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    labels_file = folder / manifest["labels"]
    masks = np.fromfile(labels_file, np.uint8).reshape(manifest["dimensions"][::-1]) == 2
    source_rows, pair_rows = [], []
    for native, png, comparable in source_planes(case, manifest, folder):
        with Image.open(png) as image:
            pixels = np.asarray(image.convert("RGB"))
        if comparable.shape != pixels.shape:
            raise ValueError(f"Source dimensions disagree for {native.name}")
        source_rows.append(dict(native=native.name, native_sha256=sha256(native),
                                preview=png.name, preview_sha256=sha256(png),
                                height=pixels.shape[0], width=pixels.shape[1],
                                disagreeing_rgb_pixels=int(np.any(pixels != comparable, axis=-1).sum()),
                                green_p05=int(np.percentile(pixels[:, :, 1], 5, method="lower")),
                                green_p95=int(np.percentile(pixels[:, :, 1], 95, method="lower"))))
    if len(source_rows) != len(masks):
        raise ValueError("Source and mask depths differ")
    for z in range(len(masks) - 1):
        a, b = [label(mask)[0] for mask in masks[z:z+2]]
        contacts = set(contact_areas(a, b, 0, 0))
        for dx, dy in SHIFTS:
            areas = contact_areas(a, b, dx, dy)
            for minimum in (1, 4):
                retained = {key for key, area in areas.items() if area >= minimum}
                pair_rows.append(dict(earlier=source_rows[z]["native"], later=source_rows[z+1]["native"],
                                      dx=dx, dy=dy, minimum_area=minimum, n_base=len(contacts),
                                      n_current=len(retained), n_lost=len(contacts-retained),
                                      n_gained=len(retained-contacts), baseline_ids=pair_ids(contacts),
                                      lost_ids=pair_ids(contacts-retained), gained_ids=pair_ids(retained-contacts)))
    output.mkdir(exist_ok=True, parents=True)
    write_csv(output / f"{case}-sources.csv", source_rows)
    write_csv(output / f"{case}-sensitivity.csv", pair_rows)
    print(case, "manifest SHA256", sha256(manifest_file), "labels SHA256", sha256(labels_file),
          "RGB disagreement pixels", sum(r["disagreeing_rgb_pixels"] for r in source_rows))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=list(CASES), action="append")
    parser.add_argument("--output", type=Path, default=Path("docs/robustness/measured"))
    args = parser.parse_args()
    for name in args.case or CASES:
        audit(name, args.output)
