"""Fetch the 32 measured H01 EM planes used for the Vessel 1 validation crop.

Requires tensorstore, numpy and OpenCV. The default output has shape (32,275,275)
in Z,Y,X order, uint8, at 64 x 64 x 33 nominal nm per voxel (XYZ).
"""

import argparse
import hashlib
from pathlib import Path

import cv2
import numpy as np
import tensorstore as ts


SOURCE = "https://h01-release.storage.googleapis.com/data/20210601/4nm_raw/"
# Vanderleest et al. specify the XY bounds on an 8 nm grid; scale 0 is 4 nm.
XY_ORIGIN = (249800 * 2, 175000 * 2)
NATIVE_WIDTH = 2200 * 2
OUTPUT_WIDTH = 275


def acquire():
    volume = ts.open({
        "driver": "neuroglancer_precomputed",
        "kvstore": {"driver": "http", "base_url": SOURCE},
        "scale_index": 0,
    }, open=True).result()
    spacing = [unit.multiplier for unit in volume.dimension_units[:3]]
    units = [unit.base_unit for unit in volume.dimension_units[:3]]
    if spacing != [4, 4, 33] or units != ["nm"] * 3:
        raise ValueError(f"Unexpected native H01 calibration: {volume.dimension_units}")
    x, y = XY_ORIGIN
    # Precomputed storage chunks span 16 z planes. Read them together for reuse.
    planes = []
    for start, stop in [(600, 608), (608, 624), (624, 632)]:
        block = volume[x:x+NATIVE_WIDTH, y:y+NATIVE_WIDTH, start:stop, 0].read().result()
        for image in block.transpose(2, 1, 0):
            planes.append(cv2.resize(image, (OUTPUT_WIDTH, OUTPUT_WIDTH), interpolation=cv2.INTER_AREA))
    return np.stack(planes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?", default=Path("data/h01/v1-em.npy"))
    args = parser.parse_args()
    data = acquire()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.save(args.output, data, allow_pickle=False)
    print(f"{args.output}: {data.shape}, pixel SHA-256 {hashlib.sha256(data.tobytes()).hexdigest()}")
