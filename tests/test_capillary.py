import json
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.capillary import trace_lumen
from pipeline.h01 import compare


class CapillaryTests(unittest.TestCase):
    def test_blank_plane_breaks_seed_propagation(self):
        generator = np.random.default_rng(7)
        frame = generator.integers(0, 255, (50, 50), dtype=np.uint8)
        seed = np.zeros_like(frame, dtype=bool)
        seed[12:29, 11:38] = True
        result = trace_lumen(np.stack([frame, frame, frame*0, frame]), seed)
        np.testing.assert_array_equal(result[1], seed)
        self.assertFalse(result[2:].any())

    def test_packaged_evidence_matches_slides_and_detects_an_interruption(self):
        folder = Path(__file__).resolve().parents[1] / "public" / "capillary"
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf8"))
        shape = manifest["dimensions"][::-1]
        rgb = np.fromfile(folder / manifest["rgb"], dtype=np.uint8).reshape(*shape, 3)
        reference = np.fromfile(folder / manifest["reference"], dtype=np.uint8).reshape(shape).astype(bool)
        prediction = np.fromfile(folder / manifest["labels"], dtype=np.uint8).reshape(shape) == 2
        for z, filename in enumerate(manifest["sections"]):
            self.assertEqual(Path(filename).stem, str(600 + z))
            np.testing.assert_array_equal(np.asarray(Image.open(folder / filename)), rgb[z, :, :, 0])
        self.assertEqual(manifest["spacing"], [.064, .064, .033])
        np.testing.assert_array_equal(prediction[0], reference[0])
        report = compare(prediction, reference)
        published = json.loads((folder / "validation.json").read_text())
        self.assertEqual(report["totals"], published["totals"])
        self.assertAlmostEqual(report["heldOutDice"], published["heldOutDice"])
        prediction[16] = False
        interrupted = compare(prediction, reference)
        self.assertEqual(interrupted["totals"]["supportedLinks"], report["totals"]["supportedLinks"] - 2)
        self.assertEqual(interrupted["totals"]["missedLinks"], report["totals"]["missedLinks"] + 2)
