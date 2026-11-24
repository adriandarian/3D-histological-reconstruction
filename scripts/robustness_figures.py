"""Summarize every paired run and render the protocol-selected figures."""
import csv
import gzip
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def write_table(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def gate_table(out):
    groups = defaultdict(list)
    with gzip.open(out / "intervals.csv.gz", "rt") as stream:
        for row in csv.DictReader(stream):
            groups[row["scenario"], row["registration"], row["method"]].append(row)
    summaries = []
    for (scenario, registration, method), rows in groups.items():
        for threshold in (None, .60, .90, .97):
            for require_measured in (False, True):
                selected = [r for r in rows if (threshold is None or float(r["ncc"]) >= threshold)
                            and (not require_measured or int(r["measured_pair"]))]
                sums = {k: sum(int(r[k]) for r in selected) for k in
                        ("tp", "fp", "fn", "wrong_family", "unmatched_fp", "branch_eligible", "branch_recovered")}
                all_edges = sum(int(r["tp"]) + int(r["fn"]) for r in rows)
                summaries.append(dict(scenario=scenario, registration=registration, method=method,
                                      min_ncc=threshold, measured_only=int(require_measured),
                                      total_intervals=len(rows), accepted=len(selected),
                                      excluded_reference_edges=all_edges-sums["tp"]-sums["fn"], **sums))
    write_table(out / "gates.csv", summaries)


def figures(out, panels):
    gate_table(out)
    with (out / "runs.csv").open() as stream:
        runs = list(csv.DictReader(stream))
    groups = defaultdict(list)
    for row in runs:
        groups[row["scenario"], row["registration"], row["method"]].append(row)
    metrics = ("dice", "hidden_dice", "tp", "fp", "fn", "wrong_family", "unmatched_fp",
               "false_splits", "missed_splits", "false_merges", "missed_merges",
               "branch_recovered", "sampled_branch_path", "fused_planes", "connected_family_pairs", "exit_entry_join")
    summary = []
    for (scenario, registration, method), rows in groups.items():
        stats = dict(scenario=scenario, registration=registration, method=method, seeds=len(rows))
        for k in metrics:
            vals = [float(r[k]) for r in rows if r[k] != ""]
            for suffix, fn in (("mean", np.mean), ("min", min), ("max", max)):
                stats[k+"_"+suffix] = round(float(fn(vals)), 6) if vals else None
        summary.append(stats)
    write_table(out / "summary.csv", summary)
    cases = [r for r in summary if r["method"] == "signed_distance" and r["registration"] == "1"]
    fig, axes = plt.subplots(1, 3, figsize=(11, 7.6), sharey=True, layout="constrained")
    y = np.arange(len(cases))
    for ax, k, title in zip(axes, ("dice", "connected_family_pairs", "fn"),
                            ("Foreground Dice", "Unrelated family pairs joined", "Missed reference edges")):
        mean = np.array([r[k+"_mean"] for r in cases])
        lo = mean - [r[k+"_min"] for r in cases]
        hi = [r[k+"_max"] for r in cases] - mean
        ax.errorbar(mean, y, xerr=np.maximum([lo, hi], 0), fmt="o", ms=4, color="#245c76", capsize=2)
        ax.set_title(title, fontsize=11)
        ax.grid(axis="x", alpha=.25)
    axes[0].set_yticks(y, [r["scenario"] for r in cases])
    axes[0].invert_yaxis()
    fig.suptitle("Registered segmentation with signed-distance gap fill\nMean and full range across six paired seeds")
    fig.savefig(out / "sensitivity.png", dpi=145)
    plt.close(fig)

    fig, axes = plt.subplots(len(panels), 4, figsize=(9, 2.15*len(panels)), layout="constrained")
    for row, (name, (rgb, ref, pred, retained)) in enumerate(panels.items()):
        z = 12 if name in ("edge_gap", "dilate2") else 10
        anchor = min(retained, key=lambda i: abs(i-z))
        axes[row, 0].imshow(rgb[anchor])
        axes[row, 0].set_title(f"{name}: acquired z={anchor}", fontsize=9)
        axes[row, 1].imshow(ref[z], cmap="tab10", vmin=0, vmax=9, interpolation="nearest")
        axes[row, 1].set_title(f"Reference identities z={z}", fontsize=9)
        axes[row, 2].imshow(pred[z], cmap="gray", vmin=0, vmax=1)
        axes[row, 2].set_title("Predicted" if z in retained else "Interpolated", fontsize=9)
        truth = ref[z] > 0
        colors = np.zeros((*truth.shape, 3), dtype=np.uint8)
        colors[truth & pred[z]] = (204, 211, 214)
        colors[truth & ~pred[z]] = (72, 162, 216)
        colors[~truth & pred[z]] = (239, 140, 52)
        axes[row, 3].imshow(colors)
        axes[row, 3].set_title("Orange extra / blue missed", fontsize=9)
        for ax in axes[row]:
            ax.set_axis_off()
    fig.suptitle("Prespecified synthetic sections, seed 11\nFirst column uses the nearest acquired image in its native frame")
    fig.savefig(out / "sections.png", dpi=145)
    plt.close(fig)
