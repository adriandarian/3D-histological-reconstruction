"""Acquire and reconstruct the named FAFB VA6 projection neuron branch."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.request import urlopen

import numpy as np
from PIL import Image
from scipy.spatial import cKDTree
import tensorstore as ts

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.branching import surface
from pipeline.fafb import DAUGHTERS, assess, reconstruct, remove_resolved_arm

CATMAID = "https://fafb.catmaid.virtualflybrain.org/1"
ROOT = "https://storage.googleapis.com/"
EM = "neuroglancer-fafb-data/fafb_v14/fafb_v14_orig"
FFN = "fafb-ffn1-20200412/segmentation"
ARCHIVE = "fafb-ffn1/fafb-public-skeletons/16"
NAME = "Uniglomerular mALT VA6 adPN 017 DB"
# Release-grid coordinates (16 nm XY, 40 nm Z); all intervals half-open.
X0, X1, Y0, Y1, Z0, Z1 = 27281, 27612, 8388, 8567, 4691, 4716


def get(url):
    with urlopen(url, timeout=90) as response:
        return response.read()


def human_trace():
    rows = json.loads(get(f"{CATMAID}/skeletons/16/compact-detail"))[0]
    by_id = {row[0]: row for row in rows}
    # Endpoints and direction correspond to the two actual child subtrees. The
    # sequences between these IDs are read from parent pointers, never interpolated.
    traces = []
    for tip, stop, arm in [(780, 771, "parent"), (851, 780, "daughterA"), (796, 780, "daughterB")]:
        branch = []
        while tip != stop:
            if tip in branch or tip not in by_id:
                raise ValueError("Reference parent chain differs from the selected trace")
            branch.append(tip)
            tip = by_id[tip][1]
        traces.extend((by_id[node], "junction" if node == 780 else arm) for node in reversed(branch))
    planes = [{"z": z, "points": []} for z in range(Z0, Z1)]
    for row, arm in traces:
        node, parent, _, x, y, z, *_ = row
        if z % 40 or not Z0 <= z/40 < Z1:
            raise ValueError("Unexpected source plane")
        planes[int(z/40)-Z0]["points"].append(dict(node=node, parent=parent, arm=arm,
                                                   x=x/16-X0-.5, y=y/16-Y0-.5))
    return {"name": NAME, "skeletonId": 16, "branchNode": 780, "planes": planes}, traces


def confirm_archive(traces):
    """Confirm all current edges against the manual skeleton predating the FFN release."""
    blob = get(ROOT + ARCHIVE)
    nv, ne = map(int, np.frombuffer(blob, "<u4", 2))
    vertices = np.frombuffer(blob, "<f4", nv*3, 8).reshape(-1, 3)
    edges = np.frombuffer(blob, "<u4", ne*2, 8+12*nv).reshape(-1, 2)
    edges = {tuple(sorted(row)) for row in edges.tolist()}
    rows = [r for r, _ in traces]
    dist, nearest = cKDTree(vertices).query([r[3:6] for r in rows])
    ids = {r[0]: int(i) for r, i in zip(rows, nearest)}
    observed = [tuple(sorted((ids[r[0]], ids[r[1]]))) for r in rows if r[1] in ids]
    if len(set(nearest)) != len(nearest) or max(dist) >= 40 or not set(observed) <= edges:
        raise ValueError("Current skeleton differs from the pre-2020 release in this window")
    return dict(nodes=len(nearest), edges=len(observed), maxVertexDistanceNm=float(max(dist)),
                archiveSha256=hashlib.sha256(blob).hexdigest(), url=ROOT + ARCHIVE)


def volume(source):
    store = ts.open({"driver": "neuroglancer_precomputed",
                     "kvstore": {"driver": "http", "base_url": ROOT+source+"/"},
                     "scale_index": 2}, open=True).result()
    if [(u.multiplier, u.base_unit) for u in store.dimension_units[:3]] != [(16, "nm"), (16, "nm"), (40, "nm")]:
        raise ValueError("Release grid differs from manual trace transform")
    return np.ascontiguousarray(store[X0:X1, Y0:Y1, Z0:Z1, 0].read().result().transpose(2, 1, 0))


def write_json(path, data):
    path.write_text(json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf8")


def export(folder):
    trace, rows = human_trace()
    archive = confirm_archive(rows)
    bad = json.loads(get(CATMAID + "/stack/1/info"))["broken_slices"]
    if any(str(z) in bad for z in range(Z0, Z1)):
        raise ValueError("CATMAID marks a selected source section as broken")
    image = volume(EM)
    ids = volume(FFN)
    if image.dtype != np.uint8:
        raise ValueError("Expected grayscale EM intensity")
    image_sha = hashlib.sha256(image.tobytes()).hexdigest()
    instance_sha = hashlib.sha256(ids.astype("<u8").tobytes()).hexdigest()
    trace_sha = hashlib.sha256(json.dumps(trace, separators=(",", ":")).encode()).hexdigest()
    if (image_sha != "829095659da6bdf4dfc0a49f0c9f1640a1395e3585375d208c8cf336ff47faa4"
            or instance_sha != "7a938c2963b27e5cfafe017c7bb9a28444597c1bd079fe179d58622fb7fc8095"
            or trace_sha != "c6ac4e9219440afa6195222250180096a2f7396a83ded2694a606ff11c8a00a3"):
        raise ValueError("Released pixels, segmentation, or trace changed since case selection")
    mask, reconstruction = reconstruct(ids, trace["planes"][0]["points"][0])
    report = assess(mask, trace)
    # Compare observed evidence to an unchanging copy of the seed-plane mask.
    baseline = assess(np.broadcast_to(mask[0], mask.shape), trace)
    metrics = ["arms", "directDaughterSplitZ", "distinctDaughterPlanes"]
    report["staticParentBaseline"] = {k: baseline[k] for k in metrics}
    report["removedDaughterControls"] = {}
    for arm in DAUGHTERS:
        control = assess(remove_resolved_arm(mask, report, arm), trace)
        report["removedDaughterControls"][arm] = {k: control[k] for k in metrics}
    report.update(reconstruction=reconstruction, archivedReference=archive,
                  imageSha256=image_sha, instanceSha256=instance_sha, traceSha256=trace_sha)
    (folder/"sections").mkdir(parents=True, exist_ok=True)
    paths = []
    for i, section in enumerate(image):
        paths.append(f"sections/{Z0+i}.png")
        Image.fromarray(section).save(folder / paths[-1])
    np.repeat(image[..., None], 3, axis=-1).tofile(folder / "rgb.bin")
    (1 + mask.astype(np.uint8)).tofile(folder / "labels.bin")
    write_json(folder/"trace.json", trace)
    write_json(folder/"validation.json", report)
    write_json(folder/"mesh.json", surface(mask))
    write_json(folder/"manifest.json", dict(name="FAFB VA6 projection neuron bifurcation",
               anatomyName="Parent-seeded FFN neurite", dimensions=[X1-X0, Y1-Y0, Z1-Z0],
               spacing=[.016,.016,.040], unit="µm", sourceOrigin=[4*X0,4*Y0,Z0],
               sourceResolutionNm=[4,4,40], sections=paths, rgb="rgb.bin", labels="labels.bin",
               mesh="mesh.json", reference="trace.json", validation="validation.json",
               attribution="EM: Zheng, Lauritzen et al. (2018), CC BY-NC 4.0, cropped and downsampled. "
                           "Manual trace: Zheng et al. via Virtual Fly Brain CATMAID. "
                           "Automated segmentation: Li et al., FAFB-FFN1-20200412, cropped and meshed.",
               imageLicense="https://creativecommons.org/licenses/by-nc/4.0/",
               studyUrl="https://fafb-ffn1.storage.googleapis.com/data.html",
               caseDescription="The FFN surface comes from automated EM segmentation. Independent manual CATMAID centerline nodes identify the parent and two daughters. Membrane boundaries lack independent contours in this window."))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", type=Path, default=Path("public/bifurcation"))
    result = export(parser.parse_args().output)
    print(json.dumps({k: result[k] for k in ["arms","directDaughterSplitZ","distinctDaughterPlanes","unadjudicatedLinks","reconstruction","staticParentBaseline"]}, indent=2))
