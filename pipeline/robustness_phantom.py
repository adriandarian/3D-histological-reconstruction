"""Synthetic serial optical sections with identity and lineage specified before imaging.

The grid is Z,Y,X, with 2 um in-plane and 5 um between dense section centers.
ID 1 splits into 2 and 3; IDs 4 and 5 approach but stay separate; ID 6 exits
the field before unrelated ID 7 enters near the same location. The graph
depends on these identities, not on overlap, registration or segmentation.
"""
from dataclasses import dataclass

import cv2
import numpy as np


DEPTH, HEIGHT, WIDTH = 25, 96, 96
SPLIT_Z = 10
LINEAGE = {1: 1, 2: 1, 3: 1, 4: 4, 5: 5, 6: 6, 7: 7}
BRANCH_EDGES = ((1, 2), (1, 3))
SPACING_UM = (2, 2, 5)  # XYZ


@dataclass(frozen=True)
class PhantomSettings:
    """Translation bound per axis (px), rotation bound (deg), nonlinear pull amplitude (px).

    Contrast scales target-to-stroma color difference; noise_sd is additive
    Gaussian SD per uint8 channel. A fold adds a dark ribbon on planes 9-12;
    tissue loss removes a rectangular patch on planes 11-14.
    """
    translation_px: float = 0.
    rotation_deg: float = 0.
    deformation_px: float = 0.
    contrast: float = 1.
    noise_sd: float = 3.
    fold: bool = False
    tissue_loss: bool = False


def _anatomy(rng, x, y):
    # Small block-specific offsets and subpixel phase perturb the boundaries
    # while preserving lineage and sampling design.
    ox, oy = rng.uniform(-1.25, 1.25, 2)
    phase = rng.uniform(0, 2 * np.pi)
    ids = np.zeros((DEPTH, HEIGHT, WIDTH), dtype=np.int16)
    for z, plane in enumerate(ids):
        def ellipse(identity, cx, cy, rx, ry):
            inside = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1
            plane[inside] = identity

        cx = 31 + ox + 1.2 * np.sin(z / 7 + phase)
        cy = 34 + oy + 1.3 * np.sin(z / 8)
        if z < SPLIT_Z:
            ellipse(1, cx, cy, 4.2 + max(0, z - 5) * .65, 3.9)
        else:
            spread = 4.6 + (z - SPLIT_Z) * .62
            ellipse(2, cx - spread, cy, 3.55, 3.8)
            ellipse(3, cx + spread, cy, 3.55, 3.8)

        # Minimum center spacing of 8.3 px leaves a sub-2-px gap.
        nx = 60 + ox + 1.2 * np.sin(z / 6 + phase)
        ny = 64 + oy + 2 * np.sin(z / 6)
        ellipse(4, nx, ny, 3.45, 3.9)
        ellipse(5, nx + 8.3 + .042 * (z - 12) ** 2, ny, 3.45, 3.9)

        # Clipped circular cross-sections leave through the left FOV boundary
        # and a different tube enters. No hidden path connects their lineages.
        ellipse(6, 15 - 1.65 * z, 72 + oy, 3.7, 3.9)
        ellipse(7, -4.5 + 1.55 * (z - 14), 72.7 + oy, 3.7, 3.9)
    return ids


def reference_pairs(ids, indices):
    """Directed lineage restricted to retained endpoints, including across gaps."""
    indices = list(indices)
    if any(not 0 <= z < len(ids) for z in indices) or any(
            b <= a for a, b in zip(indices, indices[1:])):
        raise ValueError("Expected increasing, in-bounds plane indices")
    pairs = []
    for a, b in zip(indices, indices[1:]):
        left = set(map(int, np.unique(ids[a]))) - {0}
        right = set(map(int, np.unique(ids[b]))) - {0}
        edges = [(i, i) for i in sorted(left & right)]
        if a < SPLIT_Z <= b:
            edges.extend(BRANCH_EDGES)
        pairs.append(dict(status="reviewed", edges=edges))
    return pairs


def generate(seed, settings=PhantomSettings()):
    """Return acquired RGB sections (ZYXC) and undistorted reference IDs (ZYX).

    The same seed gives identical identities, texture and driving noise across
    ablations. Pose is uniform independently per plane; the first plane anchors
    the canonical coordinate frame. Sinusoidal pulls vary smoothly within planes.
    """
    geom_rng, texture_rng, pose_rng, noise_rng = [
        np.random.default_rng(stream) for stream in np.random.SeedSequence(seed).spawn(4)
    ]
    y, x = np.mgrid[:HEIGHT, :WIDTH].astype(np.float32)
    ids = _anatomy(geom_rng, x, y)
    texture = cv2.GaussianBlur(texture_rng.normal(size=x.shape), (0, 0), 1.6)
    texture *= 8. / texture.std()
    tissue = np.stack([213 + texture, 155 + texture, 180 + texture], axis=-1)
    # The stable pattern provides non-target landmarks for image registration.
    tissue = np.clip(tissue, [170, 116, 140], [238, 188, 209])
    result = []
    for z, plane in enumerate(ids):
        coverage = cv2.GaussianBlur((plane > 0).astype(np.float32), (5, 5), .70)
        image = tissue + coverage[..., None] * settings.contrast * ([80, 43, 98] - tissue)
        if settings.fold and 9 <= z <= 12:
            fold = (abs(y - (64 + .35 * (x - 66))) <= 1.5) & (x > 56) & (x < 78)
            image[fold] = [72, 46, 87]
        if settings.tissue_loss and 11 <= z <= 14:
            image[26:42, 14:31] = [248, 248, 248]

        tx, ty, angle, phase = pose_rng.uniform(-1, 1, 4)
        if z != 0:
            pose = cv2.getRotationMatrix2D(((WIDTH - 1) / 2, (HEIGHT - 1) / 2),
                                           angle * settings.rotation_deg, 1.)
            pose[:, 2] += np.array([tx, ty]) * settings.translation_px
            inverse = cv2.invertAffineTransform(pose)
            mx = inverse[0, 0] * x + inverse[0, 1] * y + inverse[0, 2]
            my = inverse[1, 0] * x + inverse[1, 1] * y + inverse[1, 2]
            mx += settings.deformation_px * np.sin(y / 11 + phase * np.pi)
            my += settings.deformation_px * np.sin(x / 15 - phase * np.pi)
            image = cv2.remap(image, mx.astype(np.float32), my.astype(np.float32),
                              cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                              borderValue=(247, 247, 247))
        image += noise_rng.normal(0, settings.noise_sd, image.shape)
        result.append(np.uint8(np.clip(image, 0, 255)))
    return np.stack(result), ids
