"""Score independent native-slide reviews against the frozen CODA viewer graph."""

import argparse
import csv
import hashlib
import itertools
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import label
from scipy.optimize import linear_sum_assignment

from pipeline.continuity import score_continuity

FROZEN = "2d8437b8f85cdaf52706c8f67b7d7a9c9cb1b4a4"
DIGESTS = {
    "labels.bin": "d29253e73d858d62a454ec3ae96ef8b6e2b1512f814c14dacdaf5f5bba4e642e",
    "manifest.json": "2c16a23f3064c9676767a5c85a417843c6aca88898dbc69047e0b7af4bb1866f",
}
NATIVE_MASK_SHA256 = "21b7683bdbdd29dbb7cac54f8dbf2cdfa4195f2dec2bf241bc0677b6302445e7"
MIN_IOU = 0.1  # consistent with the existing continuity benchmark
POSITIVE = {"CONTINUES", "SPLITS", "MERGES"}


def coda_export(folder, manifest):
    data = {}
    for name, digest in DIGESTS.items():
        raw = (folder / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f"Frozen candidate checksum mismatch: {name}")
        data[name] = raw
    sections = json.loads(data["manifest.json"])["sourceSections"]
    registry = Path(__file__).resolve().parents[1] / "scripts/coda_lung_sources.csv"
    with registry.open(newline="") as stream:
        sources = {r["filename"]: r["sha256"] for r in csv.DictReader(stream)}
    frames = []
    mask_digest = hashlib.sha256()
    for section, slide in zip(sections, manifest["slides"], strict=True):
        if (
            section["slide"] != slide["slide"]
            or sources[section["slide"]] != slide["sha256"]
        ):
            raise ValueError("Review and frozen source identities differ")
        # Registered voxel centers -> native level-zero edge coordinates, exactly
        # as the viewer inverts the 4x reduction and level-3 registration.
        inverse = np.linalg.inv(np.vstack((section["transform"], [0, 0, 1])))
        centers = np.array([[4, 0, 1.5], [0, 4, 1.5], [0, 0, 1.0]])
        matrix = (inverse @ centers)[:2] * section["step"]
        matrix[:, 2] += np.array(section["origin"]) + section["step"] / 2
        if (
            slide["crop_origin_level0"] != section["origin"]
            or slide["crop_step_level0"] != section["step"]
            or slide["crop_size"] != [640, 640]
            or slide["section"] != int(section["slide"][6:9])
            or manifest["section_stride"] != 2
        ):
            raise ValueError(
                "Review manifest differs from frozen crop or acquisition order"
            )
        native_to_first = np.vstack((slide["native_to_registered"], [0, 0, 1]))
        first_grid = np.vstack((matrix, [0, 0, 1]))
        first_native = np.array(
            [
                [32, 0, sections[0]["origin"][0] + 16],
                [0, 32, sections[0]["origin"][1] + 16],
                [0, 0, 1],
            ]
        )
        if not np.allclose(
            native_to_first @ first_grid, first_native, atol=1e-5, rtol=0
        ):
            raise ValueError("Review manifest registration differs from frozen export")
        mask_path = folder / (Path(section["slide"]).stem + "-mask.png")
        with Image.open(mask_path) as image:
            if image.size != (640, 640) or image.mode != "1":
                raise ValueError(f"Unexpected native candidate mask: {mask_path.name}")
            mask_digest.update(np.asarray(image, dtype=np.uint8).tobytes())
        frames.append(matrix)
    if mask_digest.hexdigest() != NATIVE_MASK_SHA256:
        raise ValueError("Frozen native candidate mask checksum mismatch")
    return np.frombuffer(data["labels.bin"], np.uint8).reshape(
        20, 160, 160
    ) == 2, frames


def raster_ring(points, shape):
    """Even-odd polygon membership at registered sample centers."""
    y, x = np.indices(shape)
    inside = np.zeros(shape, bool)
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        if ay != by:
            inside ^= ((ay > y) != (by > y)) & (
                x < ax + (bx - ax) * (y - ay) / (by - ay)
            )
    return inside


def reference(review, manifest, frames, shape):
    slides = [s["slide"] for s in manifest["slides"]]
    planes = {p["slide"]: p["status"] for p in review["planes"]}
    raster = np.zeros(shape, np.int32)
    reasons = {s: planes.get(s, "UNREVIEWED") for s in slides}
    ids = {}
    for i, p in enumerate(review["profiles"], 1):
        s = p["slide"]
        z = slides.index(s)
        ids[p["id"]] = i
        if p["status"] != "OBSERVED":
            reasons[s] = "INDETERMINATE PROFILE"
            continue
        frame = frames[z]
        points = np.linalg.solve(
            frame[:, :2], (np.array(p["polygon"]) - frame[:, 2]).T
        ).T
        if np.any(points < -0.5) or np.any(points > np.array(shape[:0:-1]) - 0.5):
            reasons[s] = "OUTSIDE PREDICTION FIELD"
        slide = manifest["slides"][z]
        if "crop_origin_level0" in slide:
            offsets = np.array(p["polygon"]) - slide["crop_origin_level0"]
            if np.any(offsets < 0) or np.any(
                offsets > np.array(slide["crop_size"]) * slide["crop_step_level0"]
            ):
                reasons[s] = "OUTSIDE MEASURED CROP"
        mask = raster_ring(points, shape[1:])
        if not mask.any() or np.any(raster[z][mask]):
            reasons[s] = "PROFILE UNRESOLVED AT SCORING RESOLUTION"
        raster[z][mask] = i
    intervals = {(p["source_slide"], p["target_slide"]): p for p in review["intervals"]}
    edges = defaultdict(list)
    locations = {p["id"]: p["slide"] for p in review["profiles"]}
    for edge in review["edges"]:
        edges[locations[edge["source"]], locations[edge["target"]]].append(edge)
    pairs = []
    for z, (a, b) in enumerate(zip(slides, slides[1:])):
        entry = intervals.get((a, b), {})
        calls = edges[a, b]
        reason = entry.get("reason", "")
        if (
            manifest["slides"][z + 1]["section"] - manifest["slides"][z]["section"]
            != manifest["section_stride"]
        ):
            status = "missing"
        elif (
            entry.get("status") == "REVIEWED"
            and all(reasons[s] == "REVIEWED" for s in (a, b))
            and all(e["type"] != "INDETERMINATE" for e in calls)
        ):
            status = "reviewed"
        elif entry:
            status = "uncertain"
        else:
            status = "unreviewed"
        pairs.append(
            dict(
                status=status,
                reason=reason,
                edges=[
                    (ids[e["source"]], ids[e["target"]])
                    for e in calls
                    if e["type"] in POSITIVE
                ],
            )
        )
    return (
        raster,
        reasons,
        pairs,
        ids,
        {ids[p["id"]] for p in review["profiles"] if p["role"] == "COMPETITOR"},
    )


def overlap(a, b):
    both = int((a & b).sum())
    union = int((a | b).sum())
    return dict(
        dice=2 * both / (union + both) if union else None,
        iou=both / union if union else None,
        intersection=both,
        union=union,
    )


def event_sets(edges, axis):
    groups = defaultdict(set)
    for edge in edges:
        groups[edge[axis]].add(edge[1 - axis])
    return {
        (node, tuple(sorted(neighbors)))
        for node, neighbors in groups.items()
        if len(neighbors) > 1
    }


def evaluate(volume, manifest, frames, prepared):
    all_profiles, reasons, pairs, ids, competitors = prepared
    raster = np.where(np.isin(all_profiles, list(competitors)), 0, all_profiles)
    names = {i: name for name, i in ids.items()}
    slides = manifest["slides"]
    checked = [reasons[s["slide"]] == "REVIEWED" for s in slides]
    result = score_continuity(
        volume, raster, pairs, reviewed_sections=checked, min_iou=MIN_IOU
    )
    result["profileIds"] = ids
    components = [label(plane)[0] for plane in volume]
    competing = []
    for z, row in enumerate(result["sections"]):
        competing.append({})
        if checked[z]:
            for component in range(1, row["predictedCount"] + 1):
                mask = components[z] == component
                competing[z][component] = [
                    dict(profile=names[i], **overlap(mask, all_profiles[z] == i))
                    for i in sorted(set(np.unique(all_profiles[z][mask])) & competitors)
                ]
        row.update(slide=slides[z]["slide"], status=reasons[slides[z]["slide"]])
        if checked[z]:
            row.update(overlap(volume[z], raster[z] > 0))
            inverse = {m["reference"]: m["predicted"] for m in row["matches"]}
            row["profileOverlap"] = {}
            for profile, i in ids.items():
                truth = raster[z] == i
                if truth.any():
                    component = inverse.get(i)
                    mask = (
                        components[z] == component
                        if component
                        else np.zeros_like(truth)
                    )
                    row["profileOverlap"][profile] = dict(
                        predictedComponent=component, **overlap(mask, truth)
                    )
    for z, row in enumerate(result["pairs"]):
        row["slides"] = [s["slide"] for s in slides[z : z + 2]]
        row["reason"] = pairs[z]["reason"]
        a, b = components[z : z + 2]
        y, x = np.where((a > 0) & (b > 0))
        contacts = np.column_stack((a[y, x], b[y, x]))
        links, first = np.unique(contacts, axis=0, return_index=True)
        evidence = []
        observed = set()
        expected = set(pairs[z]["edges"])
        for (i, j), k in zip(links, first):
            endpoints, edge = [], []
            for depth, component in [(z, int(i)), (z + 1, int(j))]:
                slide = slides[depth]
                native = frames[depth] @ [x[k], y[k], 1]
                mapping = {
                    m["predicted"]: m["reference"]
                    for m in result["sections"][depth].get("matches", [])
                }
                edge.append(mapping.get(component, -component))
                endpoints.append(
                    dict(
                        slide=slide["slide"],
                        sha256=slide["sha256"],
                        xyLevel0=native.tolist(),
                        component=component,
                        referenceProfile=names.get(edge[-1]),
                        overlappingCompetitors=competing[depth].get(component, []),
                    )
                )
                if manifest["case"] == "coda-lung":
                    stem = Path(slide["slide"]).stem
                    endpoints[-1].update(
                        measuredCrop=f"/data/coda-lung/{stem}.png",
                        cropXY=(
                            (native - slide["crop_origin_level0"])
                            / slide["crop_step_level0"]
                        ).tolist(),
                        nativeCandidateMask=f"/data/coda-lung/{stem}-mask.png",
                    )
            observed.add(tuple(edge))
            verdict = "excluded"
            if row["status"] == "reviewed":
                verdict = "TP" if tuple(edge) in expected else "FP"
            evidence.append(
                dict(
                    endpoints=endpoints,
                    registeredContactXY=[int(x[k]), int(y[k])],
                    verdict=verdict,
                )
            )
        row["predictedJoins"] = evidence
        if row["status"] == "reviewed":
            for axis, key in enumerate(["exactSplits", "exactMerges"]):
                pred, ref = event_sets(observed, axis), event_sets(expected, axis)
                row[key] = {
                    "tp": sorted(pred & ref),
                    "fp": sorted(pred - ref),
                    "fn": sorted(ref - pred),
                }
    for event in ["exactSplits", "exactMerges"]:
        result["totals"][event] = {
            k: sum(len(p[event][k]) for p in result["pairs"] if event in p)
            for k in ("tp", "fp", "fn")
        }
    result["status"] = (
        "REVIEW SCORED" if result["totals"]["scoredPairs"] else "NOT EVALUABLE"
    )
    return result


def agreement(left, right, left_ref, right_ref, manifest):
    """Align independent profile names geometrically; retain both original calls."""
    reports, plane_agreement = [], []
    correspondence = {}
    for z, slide in enumerate(manifest["slides"]):
        a, b = left_ref[0][z], right_ref[0][z]
        ai, bi = [np.unique(v[v > 0]) for v in (a, b)]
        similarities = np.array(
            [[overlap(a == i, b == j)["iou"] for j in bi] for i in ai]
        ).reshape(len(ai), len(bi))
        valid = similarities >= MIN_IOU
        rows, cols = linear_sum_assignment(
            valid * (min(similarities.shape) + 1 + similarities), maximize=True
        )
        plane = dict(
            slide=slide["slide"],
            statuses=[r[1][slide["slide"]] for r in (left_ref, right_ref)],
        )
        plane_agreement.append(plane)
        if plane["statuses"] != ["REVIEWED", "REVIEWED"]:
            continue
        plane.update(
            overlap(
                (a > 0) & ~np.isin(a, list(left_ref[4])),
                (b > 0) & ~np.isin(b, list(right_ref[4])),
            )
        )
        plane["matches"] = []
        for i, j in zip(rows, cols):
            if valid[i, j]:
                correspondence[int(bi[j])] = int(ai[i])
                plane["matches"].append(
                    dict(
                        left=int(ai[i]),
                        right=int(bi[j]),
                        roleAgreement=(int(ai[i]) in left_ref[4])
                        == (int(bi[j]) in right_ref[4]),
                        iou=float(similarities[i, j]),
                    )
                )
        plane["leftOnly"] = sorted(
            set(map(int, ai)) - {m["left"] for m in plane["matches"]}
        )
        plane["rightOnly"] = sorted(
            set(map(int, bi)) - {m["right"] for m in plane["matches"]}
        )
    for z, (a, b) in enumerate(zip(left_ref[2], right_ref[2])):
        entry = dict(
            slides=[s["slide"] for s in manifest["slides"][z : z + 2]],
            statuses=[a["status"], b["status"]],
        )
        if a["status"] == b["status"] == "reviewed":
            l_edges = set(a["edges"])
            r_edges = {tuple(correspondence.get(v, -v) for v in e) for e in b["edges"]}
            entry.update(
                common=sorted(l_edges & r_edges),
                leftOnly=sorted(l_edges - r_edges),
                rightOnly=sorted(r_edges - l_edges),
            )
        reports.append(entry)
    return dict(
        readers=[left["reviewer"]["id"], right["reviewer"]["id"]],
        intervals=reports,
        planes=plane_agreement,
        rightToLeftIds=correspondence,
        comparableIntervals=sum("common" in r for r in reports),
        exactConnectivityAgreements=sum(
            "common" in r and not (r["leftOnly"] or r["rightOnly"]) for r in reports
        ),
    )


def report(volume, frames, manifest, reviews):
    reader_ids = [r["reviewer"]["id"] for r in reviews]
    if len(set(reader_ids)) != len(reader_ids):
        raise ValueError("Duplicate reviewer ID")
    prepared = [reference(r, manifest, frames, volume.shape) for r in reviews]
    baseline = np.broadcast_to(volume[0], volume.shape)
    readings = [
        dict(
            review=r,
            candidate=evaluate(volume, manifest, frames, p),
            fixedSeed=evaluate(baseline, manifest, frames, p),
        )
        for r, p in zip(reviews, prepared)
    ]
    return dict(
        status="REVIEW PENDING"
        if not reviews
        else "UNADJUDICATED INDEPENDENT READINGS",
        agreement=[
            agreement(reviews[i], reviews[j], prepared[i], prepared[j], manifest)
            for i, j in itertools.combinations(range(len(reviews)), 2)
        ],
        readers=readings,
    )


def main():
    from pipeline.review_import import (
        import_review,
        read_edges,
        read_json,
        validate_manifest,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--export", type=Path, default=Path("public/data/coda-lung"))
    parser.add_argument(
        "--reader",
        nargs=2,
        type=Path,
        action="append",
        default=[],
        metavar=("GEOJSON", "EDGES"),
    )
    args = parser.parse_args()
    result = dict(
        case="coda-lung",
        status="REVIEW PENDING",
        evaluation="NOT EVALUABLE",
        frozenCommit=FROZEN,
        frozenLocalExportSha256=DIGESTS,
        nativeMaskPixelsSha256=NATIVE_MASK_SHA256,
        readers=[],
    )
    try:
        if args.reader or args.manifest:
            if not args.manifest:
                parser.error("--reader requires --manifest")
            manifest = read_json(args.manifest)
            validate_manifest(manifest)
            if manifest["case"] != "coda-lung":
                raise ValueError("Expected the CODA manifest")
            volume, frames = coda_export(args.export, manifest)
            reviews = [
                import_review(manifest, read_json(g), read_edges(e))
                for g, e in args.reader
            ]
            if any(r["reviewer"]["kind"] != "PATHOLOGIST" for r in reviews):
                raise ValueError("Synthetic reviews cannot score the biological case")
            result.update(report(volume, frames, manifest, reviews))
            if not reviews:
                empty = dict(profiles=[], intervals=[], planes=[], edges=[])
                audit = evaluate(
                    volume,
                    manifest,
                    frames,
                    reference(empty, manifest, frames, volume.shape),
                )
                result["unreviewedIntervals"] = audit["pairs"]
            result["evaluation"] = (
                "UNADJUDICATED"
                if any(
                    r["candidate"]["totals"]["scoredPairs"] for r in result["readers"]
                )
                else "NOT EVALUABLE"
            )
        print(json.dumps(result, allow_nan=False, indent=2))
    except (KeyError, TypeError, ValueError, OSError, np.linalg.LinAlgError) as error:
        parser.exit(2, f"Cannot score review: {error}\n")


if __name__ == "__main__":
    main()
