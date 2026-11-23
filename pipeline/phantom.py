"""A seeded, graded phantom with known acquisition translations."""

import cv2
import numpy as np


def generate(count=36):
    rng = np.random.default_rng(21)
    h, w = 320, 400
    y, x = np.mgrid[:h, :w]
    # Stable nuclei and gland landmarks survive adjacent sectioning.
    cells = rng.uniform((0, 0), (w, h), (6000, 2))
    glands = rng.uniform((65, 65), (w - 65, h - 65), (35, 2))
    offsets = rng.integers(-9, 10, (count, 2))
    for i, offset in enumerate(offsets):
        depth = (i - (count - 1) / 2) / count
        u = (x - w / 2 - 4 * np.sin(y / 27 + depth)) / (174 - 55 * depth**2)
        v = (y - h / 2 - 7 * np.sin(x / 35 - depth)) / (135 - 48 * depth**2)
        tissue = u * u + v * v < 1 + 0.08 * np.cos(5 * np.arctan2(v, u) + depth)
        wave = np.sin(x / 9 + y / 14 + depth) * np.cos(y / 19 - depth)
        rgb = np.array([222, 151, 191]) + wave[..., None] * [12, 23, 18]
        rgb = rgb.astype(np.uint8)
        for j, (cx, cy) in enumerate(cells):
            point = (
                round(cx + depth * np.sin(j) * 4),
                round(cy + depth * np.cos(j) * 4),
            )
            cv2.ellipse(rgb, point, (1 + j % 2, 1), j % 180, 0, 360, (130, 73, 141), -1)
        for j, (cx, cy) in enumerate(glands):
            point = (round(cx + depth * 5), round(cy - depth * 3))
            axes = (5 + j % 8, 3 + j % 5)
            cv2.ellipse(rgb, point, axes, j * 31, 0, 360, (134, 73, 135), 4)
            cv2.ellipse(rgb, point, axes, j * 31, 0, 360, (248, 226, 231), -1)
        rgb[~tissue] = 252
        rgb = cv2.warpAffine(
            rgb,
            np.float32([[1, 0, offset[0]], [0, 1, offset[1]]]),
            (w, h),
            borderValue=(252, 252, 252),
        )
        yield f"phantom_{i:03}.png", rgb, offset.tolist()
