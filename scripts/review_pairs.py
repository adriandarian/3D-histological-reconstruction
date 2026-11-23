"""Render ten spread-out adjacent pairs for visual registration review."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps


def overlay(root, first, second, field):
    def gray(record):
        with Image.open(root / record[field]) as image:
            thumbnail = ImageOps.contain(image.convert("L"), (215, 120))
            return np.asarray(thumbnail)

    a, b = gray(first), gray(second)
    return Image.fromarray(np.stack([a, b, b], axis=-1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = json.loads(args.manifest.read_text(encoding="utf8"))["sections"]
    indices = np.linspace(1, len(rows) - 1, min(len(rows) - 1, 10), dtype=int)
    sheet = Image.new("RGB", (900, ((len(indices) + 1) // 2) * 154), "white")
    draw = ImageDraw.Draw(sheet)
    for slot, index in enumerate(indices):
        x, y = (slot % 2) * 450, (slot // 2) * 154
        for offset, field in enumerate(("source", "registered")):
            left = x + offset * 224
            draw.text((left, y), f"{index} / {index+1}   {field}", fill="black")
            sheet.paste(overlay(args.manifest.parent, rows[index-1], rows[index], field),
                        (left, y + 20))
    sheet.save(args.output)


if __name__ == "__main__":
    main()
