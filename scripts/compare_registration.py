"""Compare two registrations on identical pixels in each fixed source image."""

import argparse
import sys
import json
from pathlib import Path

import cv2
import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.deformation import pixel_grid, to_registered, to_source


def transforms(series):
    matrices = []
    for row in series["sections"]:
        dx, dy = row["shift"]
        matrix = row.get("transform", [[1, 0, dx], [0, 1, dy]])
        matrices.append(np.vstack((matrix, [0, 0, 1])))
    return matrices


def compare(baseline, candidate):
    series = [
        json.loads(path.read_text(encoding="utf8")) for path in (baseline, candidate)
    ]
    names = [[s["filename"] for s in m["sections"]] for m in series]
    if names[0] != names[1] or series[0]["reference"] != series[1]["reference"]:
        raise ValueError("Comparison requires matching section order and reference")
    transforms_by_method = [transforms(m) for m in series]
    scores = []
    pairs = []
    for i, row in enumerate(series[1]["sections"]):
        fixed = row["fixed"]
        if series[0]["sections"][i]["fixed"] != fixed:
            raise ValueError("Comparison requires matching adjacent pairs")
        if fixed is None:
            continue
        images = []
        for j in (i, fixed):
            copies = [
                cv2.imread(
                    str(path.parent / m["sections"][j]["source"]), cv2.IMREAD_GRAYSCALE
                )
                for path, m in zip((baseline, candidate), series)
            ]
            if copies[0] is None or not np.array_equal(*copies):
                raise ValueError("Source images must exist and match")
            images.append(copies[0])
        moving, target = images
        h, w = target.shape
        valid = np.ones((h, w), dtype=bool)
        warped = []
        pixels = pixel_grid(w, h)
        for m, matrices in zip(series, transforms_by_method):

            def field(index):
                grid = m["sections"][index].get("pullGrid")
                return None if grid is None else np.asarray(grid)

            aligned = to_registered(pixels, matrices[fixed], field(fixed), w, h)
            coords = to_source(aligned, matrices[i], field(i), w, h)
            warped.append(cv2.remap(moving, coords, None, cv2.INTER_LINEAR))
            mask = cv2.remap(
                np.ones_like(moving, dtype=np.float32), coords, None, cv2.INTER_LINEAR
            )
            valid &= mask >= 1
        if valid.sum() < 2 or any(
            np.ptp(image[valid]) == 0 for image in [target, *warped]
        ):
            raise ValueError(
                f"Correlation undefined for section pair {i + 1}/{fixed + 1}"
            )
        pairs.append(tuple(sorted((i + 1, fixed + 1))))
        scores.append(
            [np.corrcoef(target[valid], image[valid])[0, 1] for image in warped]
        )
    scores = np.asarray(scores)
    print(
        f"Mean common-overlap NCC: {scores[:, 0].mean():.3f} -> {scores[:, 1].mean():.3f}"
    )
    delta = scores[:, 1] - scores[:, 0]
    print(
        f"Improved: {sum(delta > 1e-5)}, unchanged: {sum(abs(delta) <= 1e-5)}, worse: {sum(delta < -1e-5)}"
    )
    for index in np.flatnonzero(delta < -1e-5):
        a, b = pairs[index]
        print(
            f"Lower correlation on {a}/{b}: {scores[index, 0]:.3f} -> {scores[index, 1]:.3f}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    compare(args.baseline, args.candidate)
