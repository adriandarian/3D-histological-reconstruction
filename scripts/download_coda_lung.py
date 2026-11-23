"""Retrieve and verify the first 20 distributed CODA lung slides and section 001 XML."""

import argparse
import csv
import hashlib
from pathlib import Path
import shutil
import tempfile
from urllib.parse import urlencode
from urllib.request import urlopen


def matches(path, record):
    if path.stat().st_size != int(record["bytes"]):
        return False
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest() == record["sha256"]


def retrieve(output, record):
    dest = output / record["filename"]
    if dest.exists():
        if matches(dest, record):
            return
        raise ValueError(f"Existing file differs from pinned source: {dest}")
    query = urlencode({"id": record["drive_id"], "export": "download", "confirm": "t",
                       "file": record["filename"]})
    with tempfile.TemporaryDirectory(dir=output) as temporary:
        stage = Path(temporary) / dest.name
        with urlopen("https://drive.usercontent.google.com/download?" + query, timeout=120) as src:
            with stage.open("wb") as sink:
                shutil.copyfileobj(src, sink, length=1 << 20)
        if not matches(stage, record):
            raise ValueError(f"Download differs from pinned source: {dest.name}")
        stage.replace(dest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=Path("data/coda-lung"))
    args = parser.parse_args()
    args.output.mkdir(exist_ok=True, parents=True)
    with Path(__file__).with_name("coda_lung_sources.csv").open(encoding="ascii", newline="") as manifest:
        for record in csv.DictReader(manifest):
            retrieve(args.output, record)
            print("Verified", record["filename"], flush=True)


if __name__ == "__main__":
    main()
