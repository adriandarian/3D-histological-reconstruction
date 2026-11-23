import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.__main__ import load_series, reconstruct
from pipeline.phantom import generate


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
