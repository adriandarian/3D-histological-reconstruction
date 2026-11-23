"""Export and score the frozen H01 vascular model against source-only visual points."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import label

from pipeline.branching import surface
from pipeline.vascular_fork import reconstruct

FIRST = 2930
CSV = Path(__file__).resolve().parents[1] / "docs/vascular-fork-reader/annotations.csv"
HASHES = {
    "images": "1fd48fe435ceb0558ad571e693852c7ec30a6d643dac27ca691d9a681cd19253",
    "model": "f2acb18b791f10697b9881a38f75c9a81269df43ff8d9d27ed8a0f965871dff2",
    "atlas": "c443659e0ee2194269ac10c2b89f16177d1407f8cdf5c07c13a93938e54384e2",
}


def reference():
    planes = []
    with CSV.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            points = []
            for col, arm in [("parent", "parent"), ("nw", "daughterA"), ("se", "daughterB")]:
                if row[col+"_x"]:
                    # Preserve the center of the original measured source pixel.
                    x, y = [(float(row[col+"_"+axis])+.5)/2-.5 for axis in ("x", "y")]
                    points.append(dict(arm=arm, x=x, y=y))
            planes.append(dict(z=int(row["z"]), readerStatus=row["section_read"], points=points))
    if [r["z"] for r in planes] != list(range(FIRST, FIRST+48)):
        raise ValueError("Expected one review record on each of the 48 measured planes")
    return {"planes": planes}


def assess(mask, trace):
    """Propagate root reachability along shared voxel faces in ascending Z."""
    if len(mask) != len(trace["planes"]):
        raise ValueError("Section count mismatch")
    planes, arm_scores = [], {}
    previous, previous_observations, reached = None, {}, set()
    for slab, observed in zip(mask, trace["planes"]):
        regions, count = label(slab)
        edges = set()
        if previous is not None:
            contact = (previous > 0) & (regions > 0)
            edges = set(map(tuple, np.unique(np.stack((previous[contact], regions[contact]), axis=1), axis=0).tolist()))
            reached = {b for a, b in edges if a in reached}
        evidence, by_arm = [], {}
        for point in observed["points"]:
            x, y = (int(np.floor(point[k]+.5)) for k in ("x","y"))
            if not (0 <= y < regions.shape[0] and 0 <= x < regions.shape[1]):
                raise ValueError("Review point lies outside the image")
            arm, component = point["arm"], int(regions[y, x])
            if previous is None and component:
                reached.add(component)
            in_root = component in reached
            by_arm[arm] = component
            same_edge = None
            totals = arm_scores.setdefault(arm, dict(points=0,hits=0,reachablePoints=0,links=0,supportedLinks=0))
            totals["points"] += 1
            totals["hits"] += int(component > 0)
            totals["reachablePoints"] += int(in_root)
            if arm in previous_observations:
                same_edge = (previous_observations[arm], component) in edges
                totals["links"] += 1
                totals["supportedLinks"] += int(same_edge)
            evidence.append(dict(arm=arm, component=component, hit=component > 0,
                                 reachableFromParent=in_root, previousArmLink=same_edge))
        daughters = [by_arm.get(a) for a in ("daughterA", "daughterB")]
        distinct = bool(all(daughters) and daughters[0] != daughters[1]) if None not in daughters else None
        planes.append(dict(z=observed["z"], readerStatus=observed["readerStatus"],
                           points=evidence, distinctDaughters=distinct, predictedRegions=count))
        previous, previous_observations = regions, by_arm
    return dict(planes=planes, arms=arm_scores,
                distinctDaughterPlanes=sum(p["distinctDaughters"] is True for p in planes),
                uncertainPlanes=sum(not p["points"] for p in planes))


def export(folder, out):
    arrays = {}
    for name, digest in HASHES.items():
        a = np.load(folder / (name + ".npy"), allow_pickle=False)
        if hashlib.sha256(a.tobytes()).hexdigest() != digest:
            raise ValueError(f"Unexpected upstream crop for {name}")
        arrays[name] = a
    images = arrays["images"]
    prediction = reconstruct(arrays["model"])
    trace = reference()
    scores = assess(prediction, trace)
    scores["staticBaseline"] = assess(np.broadcast_to(prediction[:1], prediction.shape), trace)["distinctDaughterPlanes"]
    atlas = arrays["atlas"]
    scores["coarseAtlas"] = [dict(atlasZ=z, components=label(plane)[1],
                                  identicalToPrevious=z > 80 and np.array_equal(plane, atlas[z-81]))
                             for z, plane in enumerate(atlas,80)]
    gray = np.stack([cv2.resize(im,(200,200),interpolation=cv2.INTER_AREA) for im in images])
    (out / "sections").mkdir(parents=True, exist_ok=True)
    sections = []
    for z, image in enumerate(images, FIRST):
        name = f"sections/{z}.png"
        Image.fromarray(image).save(out / name)
        sections.append(name)
    np.repeat(gray[...,None], 3, axis=-1).tofile(out/"rgb.bin")
    (1 + prediction.astype(np.uint8)).tofile(out/"labels.bin")
    manifest = dict(dimensions=[200,200,48], spacing=[.128,.128,.033], unit="µm",
                    name="H01 vascular fork", anatomyName="Predicted vessel profile",
                    sourceOrigin=[617984,295040,FIRST], rgb="rgb.bin", labels="labels.bin",
                    mesh="mesh.json", sections=sections, reference="trace.json", validation="validation.json",
                    studyUrl="https://h01-release.storage.googleapis.com/data.html",
                    caseDescription="H01 human cortex. The released tissue model predicts a whole-vessel profile every 66 nm. Each predicted slab spans two registered EM planes. A blinded model-assisted reader marked profiles on individual measured planes; 15 transitional planes were uncertain. No human adjudicated the points.")
    for name, obj in [("trace",trace),("validation",scores),("mesh",surface(prediction)),("manifest",manifest)]:
        (out / (name+".json")).write_text(json.dumps(obj,separators=(",",":"))+"\n", encoding="utf8")
    return scores


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, default=Path("data/h01-fork"), nargs="?")
    parser.add_argument("output", type=Path, default=Path("public/vascular-fork"), nargs="?")
    args=parser.parse_args()
    print(export(args.folder,args.output)["arms"])
