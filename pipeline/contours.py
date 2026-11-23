"""Match exposed tissue tips in the H&E registered frame."""

import cv2
import numpy as np

from .deformation import displacement, gradient_bound, pixel_grid, to_source

PATCH_RADIUS = 36
SEARCH_RADIUS = 16
SUPPORT_RADIUS = 24


def _exposed_tips(gray, valid):
    bright = ((gray >= 235) & (valid != 0)).astype(np.uint8)
    _, labels = cv2.connectedComponents(bright)
    kernel = np.ones((3, 3), np.uint8)
    border = valid - cv2.erode(
        valid, kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0
    )
    exterior = np.unique(labels[(border != 0) & (bright != 0)])
    if not exterior.size:
        return np.empty((0, 2), dtype=int)
    glass = np.isin(labels, exterior).astype(np.float32)
    contour = (cv2.GaussianBlur(glass, (0, 0), 3) > 0.5).astype(np.uint8)
    contour = cv2.morphologyEx(contour, cv2.MORPH_GRADIENT, kernel)
    interior = cv2.erode(
        valid,
        np.ones((21, 21), np.uint8),
        borderType=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    # A protruding tip has more exterior glass around it than a straight edge.
    exposure = cv2.GaussianBlur(glass, (0, 0), 24) * contour * interior
    peaks = (exposure == cv2.dilate(exposure, np.ones((35, 35), np.uint8))) & (
        exposure > 0.62
    )
    y, x = np.where(peaks)
    return np.column_stack((x, y))


def _patch_motion(source, target, point):
    x, y = point
    r, s = PATCH_RADIUS, SEARCH_RADIUS
    patch = source[y - r : y + r + 1, x - r : x + r + 1]
    window = target[y - r - s : y + r + s + 1, x - r - s : x + r + s + 1]
    scores = cv2.matchTemplate(window, patch, cv2.TM_CCOEFF_NORMED)
    _, peak, _, position = cv2.minMaxLoc(scores)
    return np.asarray(position) - s, peak


def _tip_updates(gray, valid, grids, nodes):
    tips = [_exposed_tips(im, mask) for im, mask in zip(gray, valid)]
    width = 2 * (PATCH_RADIUS + SEARCH_RADIUS) + 1
    kernel = np.ones((width, width), np.uint8)
    safe = [
        cv2.erode(mask, kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0)
        for mask in valid
    ]
    blurred = [cv2.GaussianBlur(im, (0, 0), 2) for im in gray]
    shifts = np.zeros_like(grids)
    weights = np.zeros_like(grids[..., 0])
    for i, (left, right) in enumerate(zip(tips, tips[1:])):
        if not len(left) or not len(right):
            continue
        distances = np.linalg.norm(left[:, None] - right, axis=2)
        nearest_left = distances.argmin(axis=0)
        for j, k in enumerate(distances.argmin(axis=1)):
            if distances[j, k] > SUPPORT_RADIUS or nearest_left[k] != j:
                continue
            p, q = left[j], right[k]
            if not all(mask[y, x] for mask in safe[i : i + 2] for x, y in (p, q)):
                continue
            forward, f_score = _patch_motion(blurred[i], blurred[i + 1], p)
            backward, b_score = _patch_motion(blurred[i + 1], blurred[i], q)
            if (
                min(f_score, b_score) < 0.70
                or np.linalg.norm(forward + backward) > 4
                or np.max(np.abs([forward, backward])) >= SEARCH_RADIUS
            ):
                continue
            # Split the estimated motion equally between the two planes.
            half_motion = (forward - backward) / 4
            for index, tip, delta in ((i, p, -half_motion), (i + 1, q, half_motion)):
                weight = np.clip(
                    2 - np.linalg.norm(nodes - tip, axis=2) / SUPPORT_RADIUS, 0, 1
                )
                shifts[index] += weight[:, :, None] * delta
                weights[index] += weight
    return shifts / np.maximum(weights[..., None], 1)


def refine_exposed_tips(images, transforms, grids, registered, valid):
    """Update images, masks and pull grids together. Each pass resamples the original."""
    h, w = images[0].shape[:2]
    pixels = pixel_grid(w, h)
    rows, cols = grids.shape[1:3]
    nodes = np.float32(
        pixel_grid(cols, rows) * [(w - 1) / (cols - 1), (h - 1) / (rows - 1)]
    )
    source_valid = np.ones((h, w), np.uint8)

    for _ in range(2):
        gray = [cv2.cvtColor(im, cv2.COLOR_RGB2GRAY) for im in registered]
        updates = _tip_updates(gray, valid, grids, nodes)
        for i, (base, update) in enumerate(zip(grids, updates)):
            if not np.any(base) or not np.any(update):
                continue
            # Compose the residual pull with the existing field. Keep all nodes
            # outside the matched neighborhoods exactly as they were.
            delta = np.where(
                np.any(update != 0, axis=2, keepdims=True),
                update + displacement(nodes + update, base, w, h) - base,
                0,
            )
            step = 1.0
            while step >= 1 / 1024:
                candidate = (base + step * delta).astype(np.float32)
                if gradient_bound(candidate, w, h) <= 0.600001:
                    coords = to_source(pixels, transforms[i], candidate, w, h)
                    mask = cv2.remap(source_valid, coords, None, cv2.INTER_NEAREST)
                    if mask.mean() >= 0.70:
                        registered[i] = cv2.remap(
                            images[i],
                            coords,
                            None,
                            cv2.INTER_LINEAR,
                            borderValue=(255, 255, 255),
                        )
                        valid[i] = mask
                        grids[i] = candidate
                        break
                step *= 0.5
