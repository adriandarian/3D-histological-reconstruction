"""Regression checks for measured-plane access, mask errors and alignment."""
import unittest

import cv2
import numpy as np

from pipeline.branching import segment
from pipeline.robustness_methods import reconstruct
from scripts.tcia_prostate import signed


class RobustnessMethodsTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(97)
        gray = cv2.GaussianBlur(rng.normal(size=(64, 64)), (0, 0), 1.2)
        background = np.uint8(np.clip(170 + 24 * gray / gray.std(), 113, 220))
        self.start = np.repeat(background[..., None], 3, axis=-1)
        self.start[24:33, 26:36] = [75, 48, 90]
        self.end = self.start.copy()
        self.end[24:33, 26:36] = 171
        self.end[24:33, 31:41] = [75, 48, 90]

    def test_measured_anchors_and_gap_rules(self):
        rgb = np.stack([self.start, self.end])
        masks = segment(rgb) == 2
        methods, qa = reconstruct(rgb, [0, 2], 3, register=False)
        for name in ["observed_only", "nearest", "signed_distance"]:
            np.testing.assert_array_equal(methods[name][[0, 2]], masks)
        self.assertFalse(methods["observed_only"][1].any())
        np.testing.assert_array_equal(methods["nearest"][1], masks[0])
        np.testing.assert_array_equal(methods["first_mask"][2], masks[0])
        np.testing.assert_array_equal(methods["signed_distance"][1],
                                      signed(masks[0]) + signed(masks[1]) > 0)
        self.assertEqual(len(qa), 2)
        self.assertEqual(qa[0], qa[1])

    def test_rigid_registration_aligns_a_shifted_target(self):
        dx, dy = 5, -3
        moved = cv2.warpAffine(self.start, np.float32([[1, 0, dx], [0, 1, dy]]),
                               (64, 64), borderValue=(255, 255, 255))
        rgb = np.stack([self.start, moved])
        on, aligned = reconstruct(rgb, [0, 1], 2)
        off, raw = reconstruct(rgb, [0, 1], 2, register=False)
        self.assertGreater(aligned[0], raw[0])
        self.assertGreater(aligned[0], .98)
        np.testing.assert_array_equal(on["nearest"][0], on["nearest"][1])
        self.assertFalse(np.array_equal(off["nearest"][0], off["nearest"][1]))

    def test_boundary_error_is_planar_and_unobservable_indices_rejected(self):
        rgb = np.stack([self.start, self.end])
        outputs = [reconstruct(rgb, [0, 3], 4, boundary_px=k, register=False)[0]
                   for k in (-1, 0, 1)]
        areas = [v["observed_only"][0].sum() for v in outputs]
        self.assertLess(areas[0], areas[1])
        self.assertLess(areas[1], areas[2])
        for v in outputs:
            self.assertFalse(v["observed_only"][1:3].any())
        for invalid in ([0, 2], [1, 3], [0, 1, 3], [0., 3.]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                reconstruct(rgb, invalid, 4)

    def test_no_seed_remains_empty_for_seeded_methods(self):
        rgb = np.stack([np.full_like(self.start, 200), self.end])
        volumes, qa = reconstruct(rgb, [0, 2], 3, register=False)
        for name in ("flow_seed", "first_mask"):
            self.assertFalse(volumes[name].any())
        np.testing.assert_array_equal(qa, [0, 0])
        self.assertTrue(volumes["signed_distance"][2].any())
