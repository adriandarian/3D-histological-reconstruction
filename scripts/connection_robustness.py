"""Run the prespecified paired-seed synthetic study. See docs/robustness/PROTOCOL.md."""
import argparse
import csv
import gzip
import io
from itertools import combinations
from pathlib import Path

import cv2
import numpy as np
from scipy.ndimage import label

from pipeline.continuity import score_continuity
from pipeline.robustness_methods import reconstruct
from pipeline.robustness_phantom import (
    BRANCH_EDGES, LINEAGE, SPLIT_Z, PhantomSettings, generate, reference_pairs,
)

SEEDS = (11, 23, 37, 53, 71, 89)
SCENARIOS = {
    "clean": {}, "shift2": {"translation_px": 2}, "shift6": {"translation_px": 6},
    "rotate3": {"rotation_deg": 3}, "rotate9": {"rotation_deg": 9},
    "warp2": {"deformation_px": 2}, "warp5": {"deformation_px": 5},
    "stride2": {"stride": 2}, "stride4": {"stride": 4},
    "gap1": {"gap": 1}, "gap3": {"gap": 3},
    "contrast75": {"contrast": .75}, "contrast50": {"contrast": .5},
    "noise12": {"noise_sd": 12}, "noise24": {"noise_sd": 24},
    "fold": {"fold": True}, "loss": {"tissue_loss": True},
    "erode2": {"boundary": -2}, "erode1": {"boundary": -1},
    "dilate1": {"boundary": 1}, "dilate2": {"boundary": 2},
    "combined": {"translation_px": 6, "rotation_deg": 9, "deformation_px": 5,
                 "contrast": .75, "noise_sd": 12, "stride": 2},
    "edge_gap": {"omit": (9, 15)},
}


def dice(pred, ref):
    denom = pred.sum() + ref.sum()
    return round(float(2 * (pred & ref).sum() / denom), 6) if denom else None


def fused_families(pred, ref):
    """Number of cross-sections with a substantial bridge between unrelated profiles."""
    count = 0
    for mask, ids in zip(pred, ref):
        regions, n = label(mask)
        families = [set() for _ in range(n + 1)]
        for identity in np.unique(ids[ids > 0]):
            hits = np.bincount(regions[ids == identity], minlength=n + 1)
            for region in np.flatnonzero(hits[1:] >= .25 * hits.sum()) + 1:
                families[region].add(LINEAGE[identity])
        count += any(len(group) > 1 for group in families)
    return count


def connected_families(pred, ref):
    """Pairs of distinct known families reached by one six-connected 3D component."""
    regions, n = label(pred)
    families = [set() for _ in range(n + 1)]
    for plane, ids in zip(regions, ref):
        for identity in np.unique(ids[ids > 0]):
            hits = np.bincount(plane[ids == identity], minlength=n + 1)
            for region in np.flatnonzero(hits[1:] >= .25 * hits.sum()) + 1:
                families[region].add(LINEAGE[identity])
    return set().union(*(set(combinations(sorted(group), 2)) for group in families))


def sampled_branch_path(pred, sections, retained):
    """Secondary endpoint: directed reachability between matched measured flanks."""
    lo = max(z for z in retained if z < SPLIT_Z)
    hi = min(z for z in retained if z >= SPLIT_Z)
    regions = label(pred[lo])[0]
    parent = BRANCH_EDGES[0][0]
    reached = [m["predicted"] for m in sections[lo]["matches"] if m["reference"] == parent]
    for z in range(lo + 1, hi + 1):
        later = label(pred[z])[0]
        contacts = later[np.isin(regions, reached) & (later > 0)]
        reached = np.unique(contacts)
        regions = later
    daughters = {m["reference"] for m in sections[hi]["matches"] if m["predicted"] in reached}
    return int(all(child in daughters for _, child in BRANCH_EDGES))


def evaluate(pred, ref, pairs, retained, confidence):
    result = score_continuity(pred, ref, pairs, min_iou=.50)
    measured = np.isin(np.arange(len(ref)), retained)
    rows = []
    for z, pair in enumerate(result["pairs"]):
        false = pair["falseLinks"]
        supported = set(map(tuple, pair["supportedLinks"]))
        branch = z == SPLIT_Z - 1
        rows.append(dict(
            z=z, measured_pair=int(measured[z] and measured[z+1]),
            ncc=float(confidence[z]), tp=len(supported), fp=len(false),
            fn=len(pair["missedLinks"]),
            wrong_family=sum(i > 0 and j > 0 and LINEAGE[i] != LINEAGE[j] for i, j in false),
            unmatched_fp=sum(i < 0 or j < 0 for i, j in false),
            false_splits=len(pair["falseSplits"]), missed_splits=len(pair["missedSplits"]),
            false_merges=len(pair["falseMerges"]), missed_merges=len(pair["missedMerges"]),
            branch_eligible=int(branch), branch_recovered=int(branch and set(BRANCH_EDGES) <= supported),
        ))
    reached = connected_families(pred, ref)
    return dict(dice=dice(pred, ref > 0), hidden_dice=dice(pred[~measured], ref[~measured] > 0),
                sampled_branch_path=sampled_branch_path(pred, result["sections"], retained),
                connected_family_pairs=len(reached), exit_entry_join=int((6, 7) in reached),
                fused_planes=fused_families(pred, ref), measured_planes=int(measured.sum())), rows


def summarize(rows, threshold=None, measured_only=False):
    selected = [r for r in rows if (threshold is None or r["ncc"] >= threshold)
                and (not measured_only or r["measured_pair"])]
    excluded_truth = sum(r["tp"] + r["fn"] for r in rows) - sum(r["tp"] + r["fn"] for r in selected)
    fields = list(rows[0])[3:]
    return dict(accepted=len(selected), rejected_truth=excluded_truth,
                **{k: sum(r[k] for r in selected) for k in fields})


def write_row(file, writers, key, row):
    if key not in writers:
        writers[key] = csv.DictWriter(file, fieldnames=row, lineterminator="\n")
        writers[key].writeheader()
    writers[key].writerow(row)


def run(out):
    out.mkdir(exist_ok=True, parents=True)
    writers, panels = {}, {}
    cv2.setNumThreads(1)
    with (out / "runs.csv").open("w", newline="") as runs, (out / "intervals.csv.gz").open("wb") as raw, \
            gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz, \
            io.TextIOWrapper(gz, encoding="ascii", newline="") as intervals:
        for name, config in SCENARIOS.items():
            for seed in SEEDS:
                settings = {k: v for k, v in config.items() if k not in ("stride", "gap", "boundary", "omit")}
                rgb, ref = generate(seed, PhantomSettings(**settings))
                depth = len(ref)
                retained = [z for z in range(0, depth, config.get("stride", 1))
                            if not config.get("gap") or abs(z - SPLIT_Z) > config["gap"] // 2]
                if "omit" in config:
                    lo, hi = config["omit"]
                    retained = [z for z in retained if not lo <= z <= hi]
                pairs = reference_pairs(ref, range(depth))
                for register in (False, True):
                    methods, confidence = reconstruct(rgb[retained], retained, depth,
                                                      boundary_px=config.get("boundary", 0), register=register)
                    for method, pred in methods.items():
                        key = dict(scenario=name, seed=seed, registration=int(register), method=method)
                        spatial, rows = evaluate(pred, ref, pairs, retained, confidence)
                        write_row(runs, writers, "runs", {**key, **spatial, **summarize(rows)})
                        for row in rows:
                            write_row(intervals, writers, "intervals", {**key, **row})
                        if (name in ("clean", "dilate2", "gap3", "combined", "edge_gap") and seed == SEEDS[0]
                                and register and method == "signed_distance"):
                            panels[name] = (rgb, ref, pred, retained)
            print(name, flush=True)
    from scripts.robustness_figures import figures
    figures(out, panels)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/robustness"))
    run(parser.parse_args().output)
