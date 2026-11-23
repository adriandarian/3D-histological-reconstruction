import cv2
import numpy as np


def displacement_grids(images, valid, reference, *, he_channels=None):
    """Fit smooth corrections in the common rigid frame to adjacent optical flow."""
    h, w = images[0].shape
    size = (max(2, round(w / 24) + 1), max(2, round(h / 24) + 1))
    grid_x, grid_y = np.meshgrid(
        np.linspace(0, w - 1, size[0], dtype="f"),
        np.linspace(0, h - 1, size[1], dtype="f"),
    )

    def grid(image):
        return cv2.remap(image, grid_x, grid_y, cv2.INTER_LINEAR)

    y, x = np.indices((h, w), dtype="f")
    pinned = {reference}
    edges = []
    weights = []

    def observation(forward, backward, i):
        fx, fy = x + forward[:, :, 0], y + forward[:, :, 1]
        inverse = cv2.remap(backward, fx, fy, cv2.INTER_LINEAR)
        mask = valid[i].astype(bool) & (
            cv2.remap(valid[i + 1], fx, fy, cv2.INTER_NEAREST) > 0
        )
        confidence = (
            np.exp(-np.sum((forward + inverse) ** 2, axis=2) / 16)
            * mask
            * (np.linalg.norm(forward, axis=2) < 35)
        )
        weighted = grid(cv2.GaussianBlur(forward * confidence[:, :, None], (0, 0), 12))
        return weighted, grid(cv2.GaussianBlur(confidence, (0, 0), 12))

    def polynomial_flow(a, b, window):
        return cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 4, window, 5, 7, 1.5, 0)

    # Tiny previews have too little support for the DIS patch pyramid.
    use_he = he_channels is not None and min(w, h) >= 16
    if use_he:
        inverse_search = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)

    for i, (a, b) in enumerate(zip(images, images[1:])):
        overlap = (valid[i] != 0) & (valid[i + 1] != 0)
        left, right = a[overlap], b[overlap]
        if left.size and left.std() > 0 and right.std() > 0:
            if np.corrcoef(left, right)[0, 1] > 0.98:
                pinned.update((i, i + 1))
        if use_he:
            red, green = he_channels
            red_a, red_b = red[i : i + 2]
            green_a, green_b = green[i : i + 2]
            broad, broad_weight = observation(
                inverse_search.calc(red_a, red_b, None),
                inverse_search.calc(red_b, red_a, None),
                i,
            )
            fine, fine_weight = observation(
                polynomial_flow(green_a, green_b, 17),
                polynomial_flow(green_b, green_a, 17),
                i,
            )
            # Normalize separately so one channel's brightness and confidence
            # cannot suppress the displacement measured in the other channel.
            broad /= np.maximum(broad_weight[:, :, None], 1e-6)
            fine /= np.maximum(fine_weight[:, :, None], 1e-6)
            edge = (2 * broad + fine) / 3
            weight = (broad_weight + fine_weight) / 2
        else:
            weighted, weight = observation(
                polynomial_flow(a, b, 35), polynomial_flow(b, a, 35), i
            )
            edge = weighted / np.maximum(weight[:, :, None], 1e-6)
        edges.append(edge)
        weights.append(weight)
    # Pull displacements satisfy g[i+1]-g[i] = flow[i]; penalize departures from rigid.
    n = len(images)
    diag = np.ones((n, *weights[0].shape), dtype="f") * 0.35
    rhs = np.zeros((*diag.shape, 2), dtype="f")
    for i, (value, weight) in enumerate(zip(edges, weights)):
        diag[i] += weight
        diag[i + 1] += weight
        rhs[i] -= weight[:, :, None] * value
        rhs[i + 1] += weight[:, :, None] * value
    # Preserve the middle plane and near-identical rigid pairs. The diagonal
    # penalties in neighboring equations still pull toward these zero fields.
    for index in pinned:
        diag[index] = 1
        rhs[index] = 0
        for edge in (index - 1, index):
            if 0 <= edge < len(weights):
                weights[edge] = np.zeros_like(weights[edge])
    # Thomas algorithm: solve one tridiagonal system per grid node for X and Y.
    for i, weight in enumerate(weights):
        ratio = weight / diag[i]
        diag[i + 1] -= ratio * weight
        rhs[i + 1] += ratio[:, :, None] * rhs[i]
    result = rhs
    result[-1] /= diag[-1, :, :, None]
    for i in reversed(range(n - 1)):
        result[i] = (rhs[i] + weights[i][:, :, None] * result[i + 1]) / diag[
            i, :, :, None
        ]
    # A contraction makes the inverse unique. Bound the Frobenius norm of
    # the bilinear displacement derivative, including inside each grid cell.
    for field in result:
        sx = (
            np.max(np.linalg.norm(np.diff(field, axis=1), axis=2))
            * (size[0] - 1)
            / (w - 1)
        )
        sy = (
            np.max(np.linalg.norm(np.diff(field, axis=0), axis=2))
            * (size[1] - 1)
            / (h - 1)
        )
        field /= max(1.0, np.hypot(sx, sy) / 0.6)
    return result


def pixel_grid(width, height):
    y, x = np.indices((height, width), dtype=np.float32)
    return np.stack([x, y], axis=-1)


def displacement(points, field, width, height):
    """Bilinear, endpoint-aligned grid sampled in registered preview pixels."""
    rows, cols = field.shape[:2]
    uv = np.clip(points / [width - 1, height - 1], 0, 1) * [cols - 1, rows - 1]
    x, y = np.moveaxis(uv, -1, 0)
    ix = np.minimum(x.astype(int), cols - 2)
    iy = np.minimum(y.astype(int), rows - 2)
    fx, fy = (x - ix)[..., None], (y - iy)[..., None]
    return (1 - fy) * ((1 - fx) * field[iy, ix] + fx * field[iy, ix + 1]) + fy * (
        (1 - fx) * field[iy + 1, ix] + fx * field[iy + 1, ix + 1]
    )


def to_source(points, matrix, field, width, height):
    rigid = (
        points if field is None else points + displacement(points, field, width, height)
    )
    inverse = cv2.invertAffineTransform(matrix[:2])
    return (rigid @ inverse[:, :2].T + inverse[:, 2]).astype(np.float32)


def to_registered(points, matrix, field, width, height):
    rigid = points @ matrix[:2, :2].T + matrix[:2, 2]
    result = rigid
    if field is not None:
        for _ in range(24):
            update = rigid - displacement(result, field, width, height)
            if np.max(np.abs(update - result)) < 0.001:
                return update
            result = update
    return result
