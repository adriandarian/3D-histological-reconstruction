"""Import blinded native-level-zero readings and measure withheld landmark error."""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon


# SHA-256 of canonical JSON from the verified local candidate export. Pinning
# both inputs prevents a hand-edited manifest from changing independent TRE.
CODA_TRACE_DIGEST = "006789aef5f710846a952da89fd517913894aa743bceeeb33cf3976ff1f48b17"
CODA_MANIFEST_DIGEST = "51e7117626b716b631eb8963fe731d604d3d45c10d5525b59f7c5d3f6216f31a"


def json_digest(record):
    raw = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def label(row, field):
    value = row[field]
    require(isinstance(value, str) and value and value.strip() == value, f"Invalid {field}")
    return value


def number(value):
    return type(value) in (int, float) and np.isfinite(value)


def xy(value):
    return isinstance(value, list) and len(value) == 2 and all(number(v) for v in value)


def point(value, slide):
    require(xy(value) and 0 <= value[0] <= slide["width"] and 0 <= value[1] <= slide["height"],
            f"Point outside native slide {slide['slide']}")
    return value


def validate_manifest(manifest):
    label(manifest, "case")
    stride = manifest["section_stride"]
    require(type(stride) is int and stride > 0, "Invalid section stride")
    for field in ["sampled_interval_um", "cut_thickness_um"]:
        value = manifest[field]
        require(value is None or number(value) and value > 0, f"Invalid {field}")
    slides = {}
    previous = None
    for row in manifest["slides"]:
        key = label(row, "slide")
        require(key not in slides and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), "Duplicate slide or invalid digest")
        section = row["section"]
        require(type(section) is int and (previous is None or section > previous and
                (section - previous) % stride == 0), "Invalid slide order or sampling stride")
        previous = section
        require(all(type(row[k]) is int and row[k] > 0 for k in ("width", "height")), "Invalid native dimensions")
        affine = np.asarray(row["native_to_registered"])
        require(affine.shape == (2, 3) and affine.dtype.kind in "fiu" and np.isfinite(affine).all()
                and abs(np.linalg.det(affine[:, :2])) > 1e-12, "Invalid registration transform")
        require(row["mpp"] is None or xy(row["mpp"]) and min(row["mpp"]) > 0
                and row.get("calibration_verified") is True, "Unverified scanner spacing")
        if any(k in row for k in ("crop_origin_level0", "crop_size", "crop_step_level0")):
            origin = point(row["crop_origin_level0"], row)
            size, step = row["crop_size"], row["crop_step_level0"]
            require(xy(size) and all(type(v) is int and v > 0 for v in size)
                    and number(step) and step > 0, "Invalid crop sampling")
            point([o + n * step for o, n in zip(origin, size)], row)
        slides[key] = row
    require(slides, "No slides")
    if manifest["case"] == "coda-lung":
        # Absorb sub-nanopixel differences between LAPACK implementations.
        canonical_slides = [dict(s, native_to_registered=np.round(s["native_to_registered"], 8).tolist())
                            for s in slides.values()]
        require(json_digest(dict(manifest, slides=canonical_slides)) == CODA_MANIFEST_DIGEST,
                "Manifest differs from the frozen CODA source and registration")
    return slides


def reader(record):
    for field in ("id", "qualifications"):
        label(record, field)
    date.fromisoformat(record["date"])
    require(record["kind"] in ("SYNTHETIC", "PATHOLOGIST") and record["blinded"] is True,
            "Reader must explicitly attest blinded review and evidence kind")
    return record


def assessment(row):
    label(row, "reason")
    require(number(row["confidence"]) and 0 <= row["confidence"] <= 1, "Invalid confidence")


def ordered_pair(slides, row):
    a, b = row["source_slide"], row["target_slide"]
    names = list(slides)
    require(a in slides and b in slides and names.index(b) == names.index(a) + 1,
            "Intervals must connect consecutive retained slides in acquisition order")
    return a, b


def import_review(manifest, geojson, edges):
    slides = validate_manifest(manifest)
    require(geojson["type"] == "FeatureCollection" and geojson["coordinates"] == "native_level0_pixel_edges"
            and geojson["case"] == manifest["case"], "Wrong feature collection, case or coordinate system")
    reviewer = reader(geojson["reviewer"])
    planes = {}
    for row in geojson["planes"]:
        key = row["slide"]
        require(key in slides and key not in planes and row["sha256"] == slides[key]["sha256"],
                "Unknown, repeated, or mismatched source plane")
        require(row["status"] in ("REVIEWED", "INDETERMINATE"), "Invalid plane status")
        label(row, "reason")
        planes[key] = row
    intervals = {}
    for row in geojson["intervals"]:
        a, b = ordered_pair(slides, row)
        require((a, b) not in intervals and row["status"] in ("REVIEWED", "INDETERMINATE"), "Invalid interval")
        label(row, "reason")
        if row["status"] == "REVIEWED":
            require(slides[b]["section"] - slides[a]["section"] == manifest["section_stride"],
                    "Missing sampled cut must remain indeterminate")
            require(all(planes.get(k, {}).get("status") == "REVIEWED" for k in (a, b)),
                    "Reviewed interval requires two exhaustively reviewed planes")
        intervals[a, b] = row
    profiles = {}
    for feature in geojson["features"]:
        props, geometry = feature["properties"], feature["geometry"]
        key, slide = label(props, "id"), props["slide"]
        require(key not in profiles and slide in planes and props["sha256"] == slides[slide]["sha256"],
                "Duplicate profile ID, unknown plane or mismatched slide checksum")
        require(props["role"] in ("TARGET", "COMPETITOR"), "Invalid profile role")
        assessment(props)
        require(props["status"] in ("OBSERVED", "INDETERMINATE"), "Invalid profile status")
        require(feature["type"] == "Feature" and geometry["type"] == "Polygon" and
                len(geometry["coordinates"]) == 1, "Expected one exterior polygon ring")
        ring = geometry["coordinates"][0]
        require(len(ring) >= 4 and ring[0] == ring[-1], "Polygon ring must be explicitly closed")
        for vertex in ring:
            point(vertex, slides[slide])
        polygon = Polygon(ring)
        require(polygon.is_valid and polygon.area > 0, "Invalid or degenerate polygon")
        profiles[key] = {**props, "polygon": ring}
    pairs, incoming, outgoing = {}, Counter(), Counter()
    for edge in edges:
        source, target, kind = edge["source"], edge["target"], edge["type"]
        assessment(edge)
        require(source in profiles and target in profiles and (source, target) not in pairs,
                "Unknown endpoint or duplicate edge")
        require(kind in ("CONTINUES", "SPLITS", "MERGES", "UNRELATED", "INDETERMINATE"), "Invalid edge type")
        interval = profiles[source]["slide"], profiles[target]["slide"]
        require(interval in intervals, "Edge outside declared interval")
        if kind != "INDETERMINATE":
            require(intervals[interval]["status"] == "REVIEWED" and all(
                profiles[k]["status"] == "OBSERVED" for k in (source, target)), "Edge requires reviewed evidence")
        if kind in ("CONTINUES", "SPLITS", "MERGES"):
            require(all(profiles[k]["role"] == "TARGET" for k in (source, target)),
                    "Positive target edges cannot connect a competing profile")
            incoming[target] += 1
            outgoing[source] += 1
        pairs[source, target] = kind
    for (source, target), kind in pairs.items():
        if kind in ("CONTINUES", "SPLITS", "MERGES"):
            require((outgoing[source] > 1) == (kind == "SPLITS") and
                    (incoming[target] > 1) == (kind == "MERGES"), "Edge type inconsistent with branch degrees")
    return dict(case=manifest["case"], reviewer=reviewer, planes=list(planes.values()),
                intervals=list(intervals.values()), profiles=list(profiles.values()), edges=edges)


def landmark_report(manifest, document):
    slides = validate_manifest(manifest)
    require(document["case"] == manifest["case"] and document["coordinates"] == "native_level0_pixel_edges"
            and document["withheld_from_registration"] is True, "Invalid landmark protocol")
    reviewer = reader(document["reviewer"])
    rows, seen = [], set()
    for mark in document["landmarks"]:
        key = label(mark, "id")
        a, b = ordered_pair(slides, mark)
        require((a, b, key) not in seen, "Repeated landmark")
        seen.add((a, b, key))
        transforms = []
        for side, slide in (("source", slides[a]), ("target", slides[b])):
            require(mark[f"{side}_sha256"] == slide["sha256"], "Landmark slide digest mismatch")
            transforms.append(np.vstack([slide["native_to_registered"], [0, 0, 1]]))
        src = point(mark["source_xy"], slides[a])
        dest = point(mark["target_xy"], slides[b])
        projected = np.linalg.solve(transforms[1], transforms[0] @ [*src, 1])[:2]
        residual = projected - dest
        rows.append({**mark, "target_prediction_xy": projected.tolist(),
                     "tre_target_px": float(np.linalg.norm(residual)),
                     "tre_um": None if slides[b]["mpp"] is None else float(np.linalg.norm(residual * slides[b]["mpp"]))})
    physical = [r["tre_um"] for r in rows if r["tre_um"] is not None]
    return dict(case=document["case"], reviewer=reviewer, status="EVALUATED" if rows else "NOT EVALUABLE",
                landmarks=rows, n=len(rows), n_calibrated=len(physical),
                mean_target_px=float(np.mean([r["tre_target_px"] for r in rows])) if rows else None,
                mean_um=float(np.mean(physical)) if physical else None,
                sampled_interval_um=manifest["sampled_interval_um"], cut_thickness_um=manifest["cut_thickness_um"])


def coda_manifest(folder, trace_path):
    import openslide
    sources = Path(__file__).resolve().parents[1] / "scripts/coda_lung_sources.csv"
    with sources.open(newline="") as stream:
        scans = [r for r in csv.DictReader(stream) if r["filename"].endswith(".ndpi")]
    trace = read_json(trace_path)
    require(json_digest(trace) == CODA_TRACE_DIGEST, "Registration trace differs from frozen CODA candidate")
    require([r["slide"] for r in trace] == [r["filename"] for r in scans], "Wrong trace sequence")
    slides = []
    for scan, row in zip(scans, trace):
        name = scan["filename"]
        with (folder / name).open("rb") as stream:
            require(hashlib.file_digest(stream, "sha256").hexdigest() == scan["sha256"], f"Source changed: {name}")
        with openslide.OpenSlide(str(folder / name)) as slide:
            width, height = slide.dimensions
            mpp = [float(slide.properties[f"openslide.mpp-{axis}"]) for axis in "xy"]
            require(mpp == row["mpp"] == [float(scan[f"mpp_{axis}"]) for axis in "xy"], "Scanner spacing mismatch")
        step, origin = row["crop_step_level0"], np.array(row["crop_origin_level0"])
        require(step == 8, "Unexpected trace crop scale")
        # OpenCV transforms pixel centers. Convert pixel edges into center indices
        # before inverting the trace transform, then return to first-plane native edges.
        native_to_crop = np.array([[1/step, 0, -origin[0]/step-.5], [0, 1/step, -origin[1]/step-.5], [0, 0, 1]])
        first_origin = trace[0]["crop_origin_level0"]
        crop_to_first = np.array([[step, 0, first_origin[0]+step*.5], [0, step, first_origin[1]+step*.5], [0, 0, 1]])
        affine = crop_to_first @ np.linalg.solve(np.vstack([row["first_crop_to_current"], [0, 0, 1]]), native_to_crop)
        slides.append(dict(slide=name, section=int(name[6:9]), sha256=scan["sha256"], width=width,
                           height=height, mpp=mpp, calibration_verified=True, native_to_registered=affine[:2].tolist(),
                           crop_origin_level0=origin.tolist(), crop_step_level0=step, crop_size=[640, 640]))
    manifest = dict(case="coda-lung", section_stride=2, sampled_interval_um=10, cut_thickness_um=None, slides=slides)
    validate_manifest(manifest)
    return manifest


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_edges(path):
    if path.suffix.lower() != ".csv":
        return read_json(path)
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row["confidence"] = float(row["confidence"])
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    coda = sub.add_parser("coda-manifest")
    coda.add_argument("output", type=Path)
    coda.add_argument("--slides", type=Path, default=Path("data/coda-lung"))
    coda.add_argument("--trace", type=Path, default=Path("public/data/coda-lung/trace.json"))
    for cmd, inputs in (("annotations", ["geojson", "edges"]), ("landmarks", ["pairs"])):
        child = sub.add_parser(cmd)
        for arg in ["manifest", *inputs, "output"]:
            child.add_argument(arg, type=Path)
    args = parser.parse_args()
    try:
        if args.cmd == "coda-manifest":
            result = coda_manifest(args.slides, args.trace)
        elif args.cmd == "annotations":
            result = import_review(read_json(args.manifest), read_json(args.geojson), read_edges(args.edges))
        else:
            result = landmark_report(read_json(args.manifest), read_json(args.pairs))
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write("\n")
    except (KeyError, ValueError, TypeError, OSError, np.linalg.LinAlgError) as error:
        parser.exit(2, f"Import failed: {error}\n")


if __name__ == "__main__":
    main()
