"""Build the H01 V1 web volume and compare a frozen seeded trace to author labels."""

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import label

from pipeline.branching import surface
from pipeline.capillary import trace_lumen
from pipeline.continuity import score_continuity

FIRST = 600
SPACING = [0.064, 0.064, 0.033]
CHECKS = Path(__file__).resolve().parents[1] / "docs" / "h01_local_checks.csv"


def compare(prediction, reference):
    # V1 is one published capillary. Class 4 also contains small detached
    # islands whose parent identity the archive does not separately annotate.
    main = np.zeros_like(reference, dtype=bool)
    for z, plane in enumerate(reference):
        parts, count = label(plane)
        if not count:
            raise ValueError(f"Missing author lumen on section {FIRST + z}")
        main[z] = parts == (1 + np.argmax(np.bincount(parts.ravel())[1:]))
    pairs = [dict(status="reviewed", edges=[[1, 1]], registration="unknown")
             for _ in reference[1:]]
    checks = {}
    with CHECKS.open(newline="") as stream:
        for row in csv.DictReader(stream):
            error = np.hypot(float(row["x1"]) - float(row["x2"]), float(row["y1"]) - float(row["y2"]))
            checks.setdefault(int(row["z"]), []).append(float(error))
    for z, distances in checks.items():
        pairs[z - FIRST]["registration"] = "pass" if max(distances) <= 4 else "fail"
    result = score_continuity(prediction, main, pairs, min_iou=0.5)
    result["localCheckErrorsPx"] = checks
    result["unassignedReferenceVoxels"] = int(np.count_nonzero(reference & ~main))
    result["seedZ"] = FIRST
    def dice(a, b):
        return float(2 * np.count_nonzero(a & b) / (a.sum() + b.sum()))
    held = reference[1:]
    fixed = np.broadcast_to(reference[0], held.shape)
    result["heldOutDice"] = dice(prediction[1:], held)
    result["fixedSeedDice"] = dice(fixed, held)
    result["fixedSeedSupportedLinks"] = score_continuity(
        np.broadcast_to(reference[0], reference.shape), main, pairs, min_iou=.5
    )["totals"]["supportedLinks"]
    result["iouSensitivity"] = {
        str(cutoff): score_continuity(prediction, main, pairs, min_iou=cutoff)["totals"]
        for cutoff in (.75, .9)
    }
    for z, row in enumerate(result["sections"]):
        row["sourceZ"] = FIRST + z
        row["dice"] = dice(prediction[z], reference[z])
        row["seed"] = z == 0
    return result


def export(folder, out):
    images = np.load(folder / "v1-em.npy", allow_pickle=False)
    reference = np.load(folder / "v1-reference.npy", allow_pickle=False)
    if images.shape != (32, 275, 275) or reference.shape != images.shape or reference.dtype != bool:
        raise ValueError("Expected paired V1 images and binary annotations on the published crop grid")
    # The viewer's external coordinates and TIFF links identify these exact inputs.
    for array, digest in [
        (images, "4a000879e38c126579dc0c3f821e58ac11ec37f748b86f1f504643d8d7809874"),
        (reference, "09256c8f35b3c35224c6f744ca36921fd2710c7107bb05da602b781188e7be00"),
    ]:
        if hashlib.sha256(array.tobytes()).hexdigest() != digest:
            raise ValueError("Input differs from the archived V1 validation window")
    prediction = trace_lumen(images, reference[0])
    report = compare(prediction, reference)
    (out / "sections").mkdir(parents=True, exist_ok=True)
    sections = []
    for z, plane in enumerate(images, FIRST):
        name = f"sections/{z}.png"
        Image.fromarray(plane).save(out / name)
        sections.append(name)
    np.repeat(images[..., None], 3, axis=-1).tofile(out / "rgb.bin")
    # Entire crop is within the EM specimen; layer 1 means sampled field.
    (1 + prediction.astype(np.uint8)).tofile(out / "labels.bin")
    reference.astype(np.uint8).tofile(out / "reference.bin")
    uncertain = np.stack([np.isin(label(plane)[0], row["extra"])
                          for plane, row in zip(prediction, report["sections"])])
    uncertain.astype(np.uint8).tofile(out / "uncertain.bin")
    manifest = dict(name="H01 cortical capillary V1", anatomyName="Traced V1 lumen",
                    dimensions=[275, 275, 32], spacing=SPACING, unit="µm",
                    rgb="rgb.bin", labels="labels.bin", reference="reference.bin",
                    mesh="mesh.json", uncertain="uncertain.bin", validation="validation.json", sections=sections)
    for basename, data in [("mesh", surface(prediction)), ("validation", report), ("manifest", manifest)]:
        (out / (basename + ".json")).write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, nargs="?", default=Path("data/h01"))
    parser.add_argument("output", type=Path, nargs="?", default=Path("public/capillary"))
    args = parser.parse_args()
    print(json.dumps(export(args.input, args.output)["totals"], indent=2))
