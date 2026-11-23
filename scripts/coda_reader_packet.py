"""Export an unmarked H&E reading set for independent CODA review."""
import argparse
import csv
import json
from pathlib import Path

import openslide
from PIL import ImageDraw

from scripts.trace_coda_lung import SLIDES, seed_polygon


def export(slides, trace, destination):
    rows = json.loads(trace.read_text(encoding="utf-8"))
    if [row["slide"] for row in rows] != SLIDES:
        raise ValueError("Expected the 20 pinned CODA slides in order")
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / "frames.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["image", "slide", "origin_x_level0", "origin_y_level0", "level0_pixels_per_pixel"])
        for index, row in enumerate(rows):
            name = row["slide"]
            origin = tuple(row["crop_origin_level0"])
            with openslide.OpenSlide(str(slides / name)) as slide:
                if slide.level_downsamples[1] != 2:
                    raise ValueError(f"Unexpected scan pyramid on {name}")
                crop = slide.read_region(origin, 1, (2560, 2560)).convert("RGB")
            image = Path(name).with_suffix(".png").name
            crop.save(destination / image)
            writer.writerow([image, name, *origin, 2])
            if index == 0:
                outline = (seed_polygon(slides / "lungs_001.xml") - origin) / 2
                ImageDraw.Draw(crop).polygon([tuple(p) for p in outline], outline="orange", width=3)
                crop.save(destination / "seed-key.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--slides", type=Path, default=Path("data/coda-lung"))
    parser.add_argument("--trace", type=Path, default=Path("public/data/coda-lung/trace.json"))
    args = parser.parse_args()
    export(args.slides, args.trace, args.destination)
