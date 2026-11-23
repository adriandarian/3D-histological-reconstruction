"""Retrieve the published V1 lumen annotations (H01 native digital z=600..631)."""

import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen

import cv2
import numpy as np
from PIL import Image

BASE = "https://ftp.ebi.ac.uk/biostudies/fire/S-BIAD/187/S-BIAD3187/Files/Vessel1%20Label%20Matrices/"
CHECKSUMS = Path(__file__).with_name("h01_label_checksums.txt")


def fetch(z, folder, hashes):
    name = f"image{z:05d}z_249800x_175000y.tiff"
    dest = folder / name
    if dest.exists():
        data = dest.read_bytes()
    else:
        with urlopen(BASE + name, timeout=90) as response:
            data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != hashes[name]:
        raise ValueError(f"Annotation checksum mismatch for {name}")
    with Image.open(BytesIO(data)) as image:
        if image.size != (4400, 4400) or image.mode != "L":
            raise ValueError(f"Unexpected annotation geometry in {name}")
        lumen = np.asarray(image) == 4
    # A display voxel belongs to lumen if a majority of its 16x16 native pixels do.
    mask = cv2.resize(lumen.astype(np.float32), (275, 275), interpolation=cv2.INTER_AREA) > .5
    if not dest.exists():
        dest.write_bytes(data)
    return mask


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path, default=Path("data/h01"))
    folder = parser.parse_args().folder
    folder.mkdir(parents=True, exist_ok=True)
    hashes = {name: digest for digest, name in
              (line.split() for line in CHECKSUMS.read_text().splitlines())}
    with ThreadPoolExecutor(max_workers=4) as pool:
        masks = list(pool.map(lambda z: fetch(z, folder, hashes), range(600, 632)))
    np.save(folder / "v1-reference.npy", np.stack(masks))


if __name__ == "__main__":
    main()
