"""Image-only reconstructions on a uniformly spaced evaluation grid.

Inputs contain only observed images and their integer positions. Plane zero
anchors registration. The dense outputs at omitted positions are hypotheses.
"""
import cv2
import numpy as np
from scipy.ndimage import binary_dilation, binary_erosion

from pipeline.__main__ import ncc, rigid_registration, warp
from pipeline.branching import segment
from pipeline.capillary import trace_lumen
from scripts.tcia_prostate import signed


def fill_distances(anchors, masks, depth):
    """Linear signed-distance blend with the TCIA zero-contour convention."""
    result = np.zeros((depth, *masks.shape[1:]), dtype=bool)
    result[anchors] = masks
    for i, (a, b) in enumerate(zip(anchors, anchors[1:])):
        if b == a + 1:
            continue
        # An empty plane has no interior boundary. Use a uniform negative
        # canvas diagonal, avoiding a fictitious feature at an image corner.
        diagonal = np.hypot(*masks.shape[1:])
        fields = [
            signed(mask) if mask.any() else np.full(mask.shape, -diagonal)
            for mask in masks[i:i + 2]
        ]
        for z in range(a + 1, b):
            fraction = (z - a) / (b - a)
            result[z] = (1 - fraction) * fields[0] + fraction * fields[1] > 0
    return result


def reconstruct(observed_rgb, retained, depth, boundary_px=0, register=True):
    """Return dense mask volumes and adjacent-interval NCC on [-1, 1].

    The QA value for a pair of consecutive observed planes is repeated on
    each dense interval between them; no intermediate image is consulted.
    """
    rgb, anchors = np.asarray(observed_rgb), np.asarray(retained)
    if rgb.ndim != 4 or rgb.dtype != np.uint8 or rgb.shape[-1] != 3:
        raise ValueError("Expected observed uint8 ZYXC RGB images")
    if (anchors.ndim != 1 or anchors.dtype.kind not in "iu" or len(anchors) < 2
            or len(anchors) != len(rgb) or anchors[0] != 0 or anchors[-1] != depth - 1
            or np.any(anchors[1:] <= anchors[:-1])):
        raise ValueError("Expected ordered observed indices spanning the evaluation grid")
    if not isinstance(boundary_px, (int, np.integer)):
        raise ValueError("Boundary perturbation must be an integer pixel radius")

    gray = [cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float32) for image in rgb]
    if register:
        transforms, qa = rigid_registration(gray, reference=0)
        aligned = np.stack([warp(image, m, (255, 255, 255)) for image, m in zip(rgb, transforms)])
        pair_confidence = [q["score"] for q in qa[1:]]
    else:
        aligned = rgb
        pair_confidence = [ncc(a, b) for a, b in zip(gray, gray[1:])]

    masks = segment(aligned) == 2
    if boundary_px:
        operation = binary_dilation if boundary_px > 0 else binary_erosion
        masks = np.stack([operation(mask, iterations=abs(boundary_px)) for mask in masks])
    observed = np.zeros((depth, *masks.shape[1:]), dtype=bool)
    observed[anchors] = masks
    # argmin picks the earlier observed mask at an exact tie.
    nearest = np.abs(np.arange(depth)[:, None] - anchors).argmin(axis=1)
    gray_aligned = np.stack([cv2.cvtColor(im, cv2.COLOR_RGB2GRAY) for im in aligned])
    flow = np.zeros_like(masks)
    if masks[0].any() and gray_aligned[0].std():
        flow = trace_lumen(gray_aligned, masks[0])
    volumes = {
        "observed_only": observed,
        "first_mask": np.broadcast_to(masks[0], observed.shape),
        "flow_seed": flow[nearest],
        "nearest": masks[nearest],
        "signed_distance": fill_distances(anchors, masks, depth),
    }
    return volumes, np.repeat(pair_confidence, np.diff(anchors))
