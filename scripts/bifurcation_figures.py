"""Render a branch validation plate from the packaged EM, predictions and reference points."""
from pathlib import Path
import json

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def plate(case, sections, output):
    folder = ROOT / "public" / case
    manifest = json.loads((folder / "manifest.json").read_text())
    trace = json.loads((folder / manifest["reference"]).read_text())["planes"]
    report = json.loads((folder / manifest["validation"]).read_text())["planes"]
    labels = np.fromfile(folder / manifest["labels"], dtype=np.uint8).reshape(manifest["dimensions"][::-1])
    fig, axes = plt.subplots(1, len(sections), figsize=(4 * len(sections), 3.6), layout="constrained")
    colors = {"parent": "white", "junction": "white", "daughterA": "#00edff", "daughterB": "#ff73dd"}
    for ax, z in zip(axes, sections):
        i = next(i for i, plane in enumerate(trace) if plane["z"] == z)
        plane = Image.open(folder / manifest["sections"][i])
        h, w = labels.shape[1:]
        ax.imshow(plane, cmap="gray", vmin=0, vmax=255, extent=(-.5, w-.5, h-.5, -.5))
        ax.contour(labels[i] == 2, levels=[.5], colors=["#ffac1a"], linewidths=.7)
        for pt in trace[i]["points"]:
            ax.scatter(pt["x"], pt["y"], s=42, facecolors="none",
                       edgecolors=colors[pt["arm"]], linewidth=1.7)
        ax.set_title(f"Section {z}")
        result = report[i]["distinctDaughters"]
        subtitle = "Distinct profiles" if result is True else "Shared or unresolved" if result is False else ""
        ax.set_xlabel(subtitle)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        scale = 1 / manifest["spacing"][0]
        ax.plot([.04*w, .04*w + scale], [.93*h, .93*h], color="white", linewidth=3)
        ax.text(.04*w,.88*h,"1 µm",color="white",fontsize=8)
    legend = [Line2D([0],[0],color="#ffac1a",label="Predicted boundary")]
    for arm, title in [("parent","Parent / junction"), ("daughterA","Daughter A"), ("daughterB","Daughter B")]:
        legend.append(Line2D([0],[0], marker="o", color="none", markerfacecolor=colors[arm],
                             markeredgecolor="#333", label=title))
    fig.legend(handles=legend,loc="outside upper center",ncol=4,frameon=False)
    fig.savefig(ROOT / "docs" / output, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    plate("bifurcation", [4699, 4707, 4708, 4715], "fafb-daughters.png")
    plate("vascular-fork", [2940, 2954, 2958, 2977], "h01-fork-daughters.png")
