"""Retrieve measured EM, released tissue predictions and a sparse manual atlas for an H01 fork.

Requires the optional tensorstore package. All source coordinates are absolute;
the 4 nm raster origin is (617984, 295040). Every measured EM plane is fetched.
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
import tensorstore as ts

BASE = "https://h01-release.storage.googleapis.com/data/20210601/"
X4, Y4 = 617984, 295040
FIRST, STOP = 2930, 2978


def open_layer(name, level, expected):
    vol = ts.open({
        "driver": "neuroglancer_precomputed",
        "kvstore": {"driver": "http", "base_url": BASE + name + "/"},
        "scale_index": level,
    }, open=True).result()
    if [(u.multiplier, u.base_unit) for u in vol.dimension_units[:3]] != [(v, "nm") for v in expected]:
        raise ValueError(f"Unexpected sampling for {name}")
    return vol


def acquire(out):
    em = open_layer("4nm_raw", 3, (32, 32, 33))
    planes = []
    for start in range(FIRST, STOP, 8):
        block = em[X4//8:X4//8+800, Y4//8:Y4//8+800, start:min(STOP,start+8), 0].read().result()
        for plane in block.transpose(2, 1, 0):
            planes.append(cv2.resize(plane, (400, 400), interpolation=cv2.INTER_AREA))
    model = open_layer("masking", 0, (64, 64, 66))
    classes = model[X4//16:X4//16+400, Y4//16:Y4//16+400, FIRST//2:STOP//2, 0].read().result()
    atlas = open_layer("blood_vessels_segmented", 0, (128, 128, 1056))
    # Extended depth only for inspecting vessel identity and direction away from
    # the split. The manual atlas has no consecutive native-Z annotations.
    manual = atlas[X4//32:X4//32+200, Y4//32:Y4//32+200, 80:101, 0].read().result()
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "images.npy", np.stack(planes))
    np.save(out / "model.npy", np.uint8(classes.transpose(2, 1, 0)))
    np.save(out / "atlas.npy", manual.transpose(2, 1, 0) > 0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, nargs="?", default=Path("data/h01-fork"))
    acquire(parser.parse_args().output)
