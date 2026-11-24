"""Build graph sidecars without changing frozen case exports. Run from the repo root."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from pipeline.connection_evidence import build_graph
from pipeline.deformation import to_source


PROVENANCE = {
    "branching": ("Prealigned simulated grid.", "Dark-stain threshold and size filtering on simulated sections."),
    "pancreas": ("Roy rigid ECC and local H&E pull grid; physical spacing unknown.",
                 "Bright-cavity tracking; anatomical identity unknown."),
    "capillary": ("Publisher-registered H01 digital EM grid; physical cut identity unverified.",
                  "Optical-flow propagation from the published V1 lumen seed."),
    "bifurcation": ("Publisher-registered FAFB EM grid.", "Cropped FAFB-FFN1 segmentation."),
    "vascular-fork": ("Publisher-registered H01 EM grid.",
                      "Archived vascular segmentation; the mask is coarser in Z than the image."),
    "tcia-prostate": ("Stitched H&E levels normalized by organ bounds; cut spacing unknown.",
                      "Contour anchors B/D/F/G; signed-distance interpolation at C/E failed held-out localization."),
    "coda-lung": ("Local rigid tissue transforms; nominal 10 µm retained interval.",
                  "Publisher seed on 001 and sequential pale-airspace overlap tracking. REVIEW PENDING."),
}


def read(path):
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def graph_references(case, folder, manifest):
    refs = {}
    if case == "bifurcation":
        trace = read(folder / manifest["reference"])
        validation = read(folder / manifest["validation"])
        nodes = {}
        for z, (plane, assessment) in enumerate(zip(trace["planes"], validation["planes"], strict=True)):
            for p, hit in zip(plane["points"], assessment["points"], strict=True):
                assert p["node"] == hit["node"]
                parent = nodes.get(p["parent"])
                if parent and parent[0] == z-1 and hit.get("edgeSupported"):
                    refs[z-1, parent[1], hit["component"]] = dict(
                        status="verified", source=f"CATMAID skeleton {trace['skeletonId']}, nodes {p['parent']} and {p['node']}",
                        reason="Independent manual centerline supports neuronal identity between these samples. Membrane boundaries and physical junction depth remain unresolved.")
                nodes[p["node"]] = z, hit["component"]
    elif case == "capillary":
        study = read(folder / manifest["validation"])
        for z, pair in enumerate(study["pairs"]):
            maps = [{m["reference"]: m["predicted"] for m in s["matches"]} for s in study["sections"][z:z+2]]
            for a, b in pair["supportedLinks"]:
                refs[z, maps[0][a], maps[1][b]] = dict(status="unresolved", source="Published human-corrected V1 masks, S-BIAD3187",
                    reason="Both endpoints match the principal lumen labels. Inter-plane identity follows the study's operational rule; no independently traced edge was supplied.")
    return refs


def source_location(case, m, registration, point):
    x, y, z = point
    center = np.array([x + .5, y + .5])
    if case == "pancreas":
        rec = registration["sections"][z]
        size = np.array([registration["width"], registration["height"]])
        grid = np.array(rec["pullGrid"]) if rec.get("pullGrid") else None
        pos = to_source((center * size / m["dimensions"][:2] - .5).reshape(1, 1, 2),
                        np.array(rec["transform"]), grid, *size).reshape(2) + .5
        return "original TIFF pixel edges", pos * [1280/size[0], 960/size[1]]
    if case == "coda-lung":
        rec = m["sourceSections"][z]
        pos = to_source(center*4-.5, np.array(rec["transform"]), None, 640, 640)
        return "NDPI level-zero pixel edges", rec["origin"] + (pos+.5)*rec["step"]
    if case == "tcia-prostate":
        frame = m["prostateFrames"][z]
        return "stitched TIFF pixel edges", frame["origin"] + center*frame["extent"]/m["dimensions"][:2]
    if case == "capillary":
        return "H01 4 nm raster", [499600, 350000] + 16*center
    if "sourceOrigin" in m:
        return "native 4 nm EM raster", m["sourceOrigin"][:2] + center*np.array(m["spacing"][:2])*250
    return "simulated image pixel edges", center


def attach_readings(graph, folder, reader_files, manifest_file):
    """Attach local, unadjudicated per-reader judgments to the matching frozen component edges."""
    from pipeline.review_import import import_review, read_edges, read_json, validate_manifest
    from pipeline.review_score import coda_export, report
    manifest = read_json(manifest_file)
    validate_manifest(manifest)
    if manifest["case"] != "coda-lung":
        raise ValueError("Expected the CODA source manifest.")
    volume, frames = coda_export(folder, manifest)
    reviews = [import_review(manifest, read_json(g), read_edges(e)) for g, e in reader_files]
    if any(r["reviewer"]["kind"] != "PATHOLOGIST" for r in reviews):
        raise ValueError("Only independent pathology readings may be attached to CODA.")
    by_id = {edge["id"]: edge for edge in graph["edges"]}
    for reading in report(volume, frames, manifest, reviews)["readers"]:
        review = reading["review"]
        calls = {(e["source"], e["target"]): e for e in review["edges"]}
        for pair in reading["candidate"]["pairs"]:
            for join in pair["predictedJoins"]:
                a, b = join["endpoints"]
                edge = by_id[f"{pair['z']}:{a['component']}>{b['component']}"]
                endpoints = (a["referenceProfile"], b["referenceProfile"])
                edge.setdefault("readings", []).append(dict(
                    reader=review["reviewer"]["id"], interval=pair["status"], verdict=join["verdict"],
                    intervalReason=pair["reason"], profiles=list(endpoints), relationship=calls.get(endpoints)))
    for edge in graph["edges"]:
        entries = edge.get("readings", [])
        edge["reference"] = "Unadjudicated pathology comparisons. " + "; ".join(
            f"{r['reader']}: {r['interval']} / {r['verdict']}. "
            + (f"{r['relationship']['type']} ({r['relationship']['confidence']}): {r['relationship']['reason']}"
               if r["relationship"] else r["intervalReason"]) for r in entries)
        edge["reasons"].append("Individual reader comparisons are retained separately. Coordinator verification and adjudication are required.")


def export(case, roy_manifest, reader_files=(), review_manifest=None):
    coda = case == "coda-lung"
    folder = Path("public/data/coda-lung" if coda else f"public/{case}")
    m = read(folder / "manifest.json")
    reg = read(roy_manifest) if case == "pancreas" else None
    if reg and digest(roy_manifest) != m["registrationSha256"]:
        raise ValueError("Roy source registration differs from the frozen reconstruction.")
    sections = []
    for z in range(m["dimensions"][2]):
        name = (m["sourceSections"][z]["slide"] if coda else reg["sections"][z]["filename"] if reg
                else m["prostateFrames"][z]["file"] if "prostateFrames" in m else m["sections"][z])
        row = dict(id=name, measured=True, source=m["sourceSections"][z]["source"] if coda else m["sections"][z])
        if coda and z:
            row["missingBefore"] = [f"undistributed section {2*z:03d}"]
        sections.append(row)
    mask = np.fromfile(folder / m["labels"], np.uint8).reshape(m["dimensions"][::-1]) == 2
    graph = build_graph(mask, sections, registration=PROVENANCE[case][0], segmentation=PROVENANCE[case][1],
                        references=graph_references(case, folder, m))
    manifest_bytes = (folder / "manifest.json").read_bytes().replace(b"\r\n", b"\n")
    graph.update(case=case, labelsSha256=digest(folder / m["labels"]), manifestSha256=hashlib.sha256(manifest_bytes).hexdigest())
    for edge in graph["edges"]:
        edge["sourceCoordinates"] = []
        for pt in edge["flanks"]:
            if pt is None:
                edge["sourceCoordinates"].append(None)
                continue
            frame, xy = source_location(case, m, reg, pt)
            edge["sourceCoordinates"].append(dict(section=sections[pt[2]]["id"], frame=frame,
                                                   xy=np.round(xy, 3).tolist()))
        if case == "tcia-prostate":
            if any(p[2] in (1, 3) for p in (edge["a"], edge["b"])):
                edge["flags"].append("inferred_extent")
            edge["reasons"].append("Sparse organ levels; intervening physical cuts unknown. C/E tumor masks are interpolated, independently contoured for evaluation, and failed localization. The contours assess extent only.")
        if case == "vascular-fork":
            edge["reasons"].append("AI visual landmarks and coarse atlas; exact junction unresolved. See the case's separate point overlay.")
        if coda and not reader_files:
            edge["reasons"].append("REVIEW PENDING. No qualified independent downstream identity labels. The orange AI point is not a pathology reading.")
    if reader_files:
        attach_readings(graph, folder, reader_files, review_manifest)
    dest = folder / "connections.json" if coda else Path(f"public/connection-evidence/{case}.json")
    dest.parent.mkdir(exist_ok=True, parents=True)
    dest.write_text(json.dumps(graph, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print(case, len(graph["edges"]), "connections")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", choices=PROVENANCE)
    parser.add_argument("--roy-manifest", type=Path, default=Path("public/data/real/manifest.json"))
    parser.add_argument("--reader", action="append", type=Path, nargs=2, metavar=("GEOJSON", "EDGES"))
    parser.add_argument("--review-manifest", type=Path, default=Path("data/coda-review-manifest.json"))
    args = parser.parse_args()
    if args.reader and args.case != ["coda-lung"]:
        parser.error("--reader requires --case coda-lung (local-only output)")
    for case in args.case or [c for c in PROVENANCE if c != "coda-lung"]:
        export(case, args.roy_manifest, args.reader, args.review_manifest)
