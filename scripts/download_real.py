"""Fetch the pancreas 10x series from version 1 of the Roy et al. dataset."""

import hashlib
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen


DEST = Path(__file__).resolve().parents[1] / "data" / "real"
INDEX = (
    "https://data.mendeley.com/public-api/datasets/fzskwpzs5j/files"
    "?folder_id=8ae46787-806f-4313-894d-4996b8a9bfc6&version=1"
)


def fetch(entry):
    target = DEST / entry["filename"]
    details = entry["content_details"]
    digest = details["sha256_hash"]
    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
        return
    if target.exists():
        raise ValueError(f"Existing file differs from the published checksum: {target}")
    with urlopen(Request(details["download_url"], headers={"User-Agent": "serial-histology-poc/1"}), timeout=120) as response:
        data = response.read()
    if len(data) != details["size"] or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError(f"Download checksum mismatch: {target.name}")
    with tempfile.NamedTemporaryFile(dir=DEST, delete=False) as pending:
        pending.write(data)
    Path(pending.name).replace(target)


def main():
    with urlopen(Request(INDEX, headers={"User-Agent": "serial-histology-poc/1"}), timeout=60) as response:
        entries = json.load(response)
    expected = {f"{i}_Pancreas_10x.tif" for i in range(1, 37)}
    if len(entries) != 36 or {e["filename"] for e in entries} != expected:
        raise ValueError("Unexpected file inventory for version 1")
    DEST.mkdir(parents=True, exist_ok=True)
    extras = [p.name for p in DEST.iterdir() if p.name not in expected]
    if extras:
        raise ValueError(f"Unrelated files in the series directory: {extras}")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, entries))
    print(f"Verified {len(entries)} TIFFs in {DEST}")


if __name__ == "__main__":
    main()
