"""Check the generated CODA volume against deposited native-slide landmarks."""
import csv
import json
from pathlib import Path
import unittest

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "public/data/coda-lung"


class CodaTraceTests(unittest.TestCase):
    def test_review_and_audit_cover_the_same_twenty_retained_slides(self):
        def records(filename):
            with (ROOT / "docs/coda-lung" / filename).open(newline="") as stream:
                return list(csv.DictReader(stream))

        points, audit = records("bronchiole-3.csv"), records("audit.csv")
        names = [f"lungs_{n:03}.ndpi" for n in range(1, 40, 2)]
        self.assertEqual([p["slide"] for p in points], names)
        self.assertEqual([r["slide"] for r in audit], names)
        self.assertEqual([int(r["nominal_z_um"]) for r in audit], list(range(0, 200, 10)))
        self.assertEqual(sum(r["point_in_mask"] == "True" for r in audit), 20)
        self.assertEqual(sum(r["point_in_transported_first_mask"] == "True" for r in audit), 9)

    @unittest.skipUnless((CASE / "manifest.json").exists(), "requires local CODA export")
    def test_one_face_connected_profile_contains_all_source_landmarks(self):
        m = json.loads((CASE / "manifest.json").read_text())
        volume = np.fromfile(CASE / m["labels"], np.uint8).reshape(m["dimensions"][::-1]) == 2
        components, count = ndimage.label(volume)
        self.assertEqual(count, 1)
        self.assertTrue((volume[1:] & volume[:-1]).any(axis=(1, 2)).all())
        self.assertFalse(volume[:, [0,-1]].any() or volume[:, :, [0,-1]].any())
        for z, section in enumerate(m["sourceSections"]):
            mat = np.array(section["transform"])
            source = (np.array(section["point"])-section["origin"])/section["step"]-.5
            x,y = np.rint((mat[:, :2] @ source + mat[:, 2] + .5)/4-.5).astype(int)
            self.assertEqual(components[z,y,x], 1, section["slide"])
