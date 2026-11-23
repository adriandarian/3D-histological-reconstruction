"""Compare paired landmarks in source and registered preview coordinates."""

import argparse
import sys
import csv
import json
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.deformation import to_registered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("pairs", type=Path)
    args = parser.parse_args()
    series = json.loads(args.manifest.read_text(encoding="utf8"))
    matrices = []
    for section in series["sections"]:
        dx, dy = section["shift"]
        matrices.append(np.array(section.get("transform", [[1, 0, dx], [0, 1, dy]])))

    def position(index, point):
        grid = series["sections"][index].get("pullGrid")
        return to_registered(
            point,
            matrices[index],
            np.asarray(grid) if grid is not None else None,
            series["width"],
            series["height"],
        )

    errors = []
    with args.pairs.open(newline="", encoding="utf8") as file:
        for row in csv.DictReader(file):
            i, j = (int(row[key]) - 1 for key in ("pair_first", "pair_second"))
            a, b = (
                np.array([float(row[f"{side}_x"]), float(row[f"{side}_y"])])
                for side in ("first", "second")
            )
            pair = (
                np.linalg.norm(a - b),
                np.linalg.norm(position(i, a) - position(j, b)),
            )
            errors.append(pair)
            print(f"{i + 1}/{j + 1}: {pair[0]:.1f} -> {pair[1]:.1f} px")
    before, after = np.mean(errors, axis=0)
    print(f"Mean TRE: {before:.1f} -> {after:.1f} preview px")


if __name__ == "__main__":
    main()
