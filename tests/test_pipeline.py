import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from pipeline.__main__ import load_series, reconstruct
from pipeline.phantom import generate
from pipeline.contours import refine_exposed_tips
from pipeline.deformation import pixel_grid, to_registered, to_source


class ReconstructionTests(unittest.TestCase):
    def test_registration_recovers_acquisition_jitter_and_preserves_order(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            reconstruct(generate(9), out, "test", "synthetic", "generated")
            manifest = json.loads((out / "manifest.json").read_text())
            rows = manifest["sections"]
            self.assertEqual([s["index"] for s in rows], list(range(9)))
            self.assertEqual(rows[4]["shift"], [0, 0])
            with np.load(out / manifest["volume"]) as volume:
                self.assertEqual(volume["rgb"].shape, (9, 320, 400, 3))
                for s in rows:
                    error = np.subtract(s["shift"], s["expectedShift"])
                    self.assertLess(np.linalg.norm(error), 1)
                    if s["fixed"] is not None:
                        self.assertGreaterEqual(s["score"], s["beforeScore"])
                    with Image.open(out / s["registered"]) as image:
                        np.testing.assert_array_equal(image, volume["rgb"][s["index"]])
                    with Image.open(out / s["texture"]) as texture:
                        self.assertEqual(texture.getchannel("A").getextrema(), (0, 255))

    def test_recovers_rotation_and_translation_in_preview_coordinates(self):
        _, moving, _ = next(generate(1))
        h, w = moving.shape[:2]
        expected = cv2.getRotationMatrix2D((w / 2, h / 2), 6, 1)
        expected[:, 2] += [10, -7]
        fixed = cv2.warpAffine(moving, expected, (w, h), borderValue=(255, 255, 255))
        rows = [("1.png", moving, None), ("2.png", fixed, None)]
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            reconstruct(rows, out, "rotation", "measured", "test")
            record = json.loads((out / "manifest.json").read_text())["sections"][0]
            points = np.array([[40, 50, 1], [330, 260, 1], [200, 160, 1]]).T
            error = (np.array(record["transform"]) - expected) @ points
            self.assertLess(np.linalg.norm(error, axis=0).max(), 1.0)

    def test_local_warp_improves_known_landmarks_and_round_trips(self):
        _, reference, _ = next(generate(1))
        h, w = reference.shape[:2]
        coords = pixel_grid(w, h)
        coords[:, :, 0] += 8 * np.sin(coords[:, :, 1] * 2 * np.pi / h)
        moving = cv2.remap(
            reference, coords, None, cv2.INTER_LINEAR, borderValue=(255, 255, 255)
        )
        for mode in (True, "he"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp:
                out = Path(temp)
                reconstruct(
                    [("1", moving, None), ("2", reference, None)],
                    out,
                    "warp",
                    "synthetic",
                    "test",
                    local=mode,
                )
                rows = json.loads((out / "manifest.json").read_text())["sections"]
                matrix = np.array(rows[0]["transform"])
                field = np.array(rows[0]["pullGrid"])
                self.assertFalse(np.any(rows[1]["pullGrid"]))
                points = np.array([[170, 80], [240, 240]])
                truth = coords[points[:, 1], points[:, 0]]
                rigid = to_registered(points, matrix, None, w, h)
                aligned = to_registered(points, matrix, field, w, h)
                self.assertLess(
                    np.linalg.norm(aligned - truth), np.linalg.norm(rigid - truth)
                )
                np.testing.assert_allclose(
                    to_source(aligned, matrix, field, w, h), points, atol=0.01
                )
                with np.load(out / "volume.npz") as volume:
                    self.assertGreaterEqual(volume["valid"][0].mean(), 0.7)
                    np.testing.assert_array_equal(volume["rgb"][1], reference)

    def test_exposed_tip_moves_while_interior_points_stay_fixed(self):
        h, w = 320, 400
        images = []
        for dx in (0, 8):
            image = np.full((h, w, 3), 255, np.uint8)
            cv2.rectangle(image, (32, 206), (368, h), (192, 90, 153), -1)
            polygon = np.array(
                [[158, 208], [192 + dx, 112], [202 + dx, 112], [230, 208]]
            )
            cv2.fillPoly(image, [polygon], (192, 90, 153))
            images.append(image)
        grids = np.zeros((2, 15, 18, 2), np.float32)
        grids[..., 0] = 1
        matrices = np.repeat(np.eye(3)[None], 2, axis=0)
        coords = pixel_grid(w, h) + [1, 0]
        registered = [
            cv2.remap(
                im,
                coords.astype("f"),
                None,
                cv2.INTER_LINEAR,
                borderValue=(255, 255, 255),
            )
            for im in images
        ]
        masks = [np.ones((h, w), np.uint8) for _ in images]
        point = np.array([197.0, 112.0])
        refine_exposed_tips(images, matrices, grids, registered, masks)
        first, second = [
            to_registered(p, m, g, w, h)
            for p, m, g in zip((point, point + [8, 0]), matrices, grids)
        ]
        self.assertLess(np.linalg.norm(first - second), 5)
        np.testing.assert_array_equal(grids[:, -1, :, 0], 1)
        for im, matrix, grid, output in zip(images, matrices, grids, registered):
            expected = cv2.remap(
                im,
                to_source(pixel_grid(w, h), matrix, grid, w, h),
                None,
                cv2.INTER_LINEAR,
                borderValue=(255, 255, 255),
            )
            np.testing.assert_array_equal(output, expected)

    def test_missing_sections_refused_and_real_series_uncalibrated(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            im = Image.new("RGB", (40, 24), "white")
            im.save(folder / "9_Pancreas_10x.tif")
            im.save(folder / "11_Pancreas_10x.tif")
            with self.assertRaisesRegex(ValueError, "consecutive"):
                list(load_series(folder, 20))
            im.save(folder / "10_Pancreas_10x.tif")
            out = folder / "out"
            out.mkdir()
            reconstruct(load_series(folder, 20), out, "tests", "measured", "local")
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertIsNone(manifest["section_interval_um"])
            self.assertEqual(manifest["sections"][0]["filename"], "9_Pancreas_10x.tif")
            self.assertEqual(manifest["width"], 20)
            self.assertEqual(manifest["sections"][0]["status"], "identity fallback")
