"""Post hoc diagnostic on already aligned phantoms; identity is the exact transform."""
import argparse
from pathlib import Path

import cv2
import numpy as np
from scipy.ndimage import label

from pipeline.__main__ import rigid_registration
from pipeline.robustness_phantom import generate
from pipeline.robustness_methods import reconstruct
from scripts.connection_robustness import SEEDS
from scripts.robustness_figures import write_table


def run(out):
    cv2.setNumThreads(1)
    rows = []
    points = np.array([[x, y, 1] for y in (16, 48, 80) for x in (16, 48, 80)])
    for seed in SEEDS:
        rgb, _ = generate(seed)
        gray = [cv2.cvtColor(im, cv2.COLOR_RGB2GRAY).astype(np.float32) for im in rgb]
        for anchor in (0, len(gray) // 2):
            transforms, qa = rigid_registration(gray, anchor)
            for z, matrix in enumerate(transforms):
                residuals = points @ matrix[:2].T - points[:, :2]
                rms = np.sqrt(np.mean(np.sum(residuals**2, axis=1)))
                rows.append(dict(seed=seed, anchor=anchor, z=z, status=qa[z]["status"],
                                 pair_ncc=qa[z]["score"], rms_xy_px=round(float(rms), 6)))
    out.mkdir(exist_ok=True, parents=True)
    write_table(out / "aligned_drift.csv", rows)

    # A projection of the entire prespecified edge gap, rather than a single cross-section.
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    rgb, ids = generate(SEEDS[0])
    retained = [z for z in range(len(ids)) if z < 9 or z > 15]
    methods, _ = reconstruct(rgb[retained], retained, len(ids), register=False)
    fig, axes = plt.subplots(1, 4, figsize=(11, 4), sharey=True, layout="constrained")
    roi = np.s_[:, 66:81, :23]
    ref = np.where(ids[roi] == 6, 1, np.where(ids[roi] == 7, 2, 0))
    axes[0].imshow(ref.max(axis=1), interpolation="nearest",
                   cmap=ListedColormap(["#15232c", "#e99852", "#68c5b1"]), vmin=0, vmax=2)
    axes[0].set_title("Known exit / entry")
    for ax, method, title in zip(axes[1:], ("observed_only", "nearest", "signed_distance"),
                                 ("Observed only", "Nearest section", "Signed distance")):
        comps, _ = label(methods[method])
        mask = (comps[roi] != 0).any(axis=1)
        ax.imshow(mask, cmap=ListedColormap(["#15232c", "#d9dddf"]), interpolation="nearest", vmin=0, vmax=1)
        ax.set_title(title)
    for ax in axes:
        for boundary in (8.5, 15.5):
            ax.axhline(boundary, color="#f15c70", lw=1, ls="--")
        ax.set_xlabel("X (pixels)")
    axes[0].set_ylabel("Section index (5 µm steps)")
    fig.suptitle("Field boundary, seed 11, no stage motion or registration\n"
                 "Projection through y=66–80 px. Dashed lines bracket seven omitted planes.")
    fig.savefig(out / "field-gap.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/robustness"))
    run(parser.parse_args().output)
