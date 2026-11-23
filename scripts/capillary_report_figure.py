"""Render the report figure from the web export (optional dependency: matplotlib)."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / "public" / "capillary"
shape = (32, 275, 275)
reference = np.fromfile(folder / "reference.bin", np.uint8).reshape(shape).astype(bool)
prediction = np.fromfile(folder / "labels.bin", np.uint8).reshape(shape) == 2

fig = plt.figure(figsize=(10, 6.3), layout="constrained")
grid = fig.add_gridspec(2, 3, height_ratios=[1.6, 1])
gold, cyan = "#ffaf20", "#08dce8"
for col, z in enumerate([0, 15, 30]):
    ax = fig.add_subplot(grid[0, col])
    ax.imshow(Image.open(folder / "sections" / f"{600+z}.png"), cmap="gray", vmin=0, vmax=255)
    ax.contour(prediction[z], levels=[.5], colors=[gold], linewidths=1.35)
    ax.contour(reference[z], levels=[.5], colors=[cyan], linewidths=.95, linestyles="dashed")
    ax.set(xlim=(0, 134), ylim=(124, 0), title=f"z = {600+z}" + (" (seed)" if z == 0 else ""))
    ax.set_axis_off()
    ax.plot([9, 9+1000/64], [113, 113], color="white", linewidth=3)
    ax.text(8, 109, "1 µm", color="white", fontsize=10)
ax = fig.add_subplot(grid[1, :])
for volume, color, name in [(prediction, "#9c4714", "Image-guided trace"),
                            (np.broadcast_to(reference[0], shape), "#465d77", "Unmoved seed")]:
    ratios = [2*(p & r).sum() / (p.sum()+r.sum()) for p, r in zip(volume[1:], reference[1:])]
    ax.plot(range(601, 632), ratios, label=name, color=color, linewidth=2)
ax.set(xlabel="Held-out H01 digital plane", ylabel="Lumen Dice", ylim=(0, 1.04))
ax.spines[["right", "top"]].set_visible(False)
ax.legend(loc="lower left", frameon=False, ncol=2)
fig.legend([Line2D([0],[0],color=gold), Line2D([0],[0],color=cyan,linestyle="--")],
           ["Traced lumen", "Published lumen"], loc="outside upper center", ncol=2, frameon=False)
fig.savefig(ROOT / "docs" / "capillary-validation.png", dpi=150)
