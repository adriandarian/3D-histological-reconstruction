import json
import unittest
from pathlib import Path

import numpy as np
from scipy.ndimage import label

from pipeline.h01_fork import assess, reference


class VascularForkTests(unittest.TestCase):
    def test_both_daughters_remain_distinct_and_a_missing_arm_is_detected(self):
        root = Path(__file__).resolve().parents[1] / "public/vascular-fork"
        trace = reference()
        mask = np.fromfile(root / "labels.bin", dtype=np.uint8).reshape(48,200,200) == 2
        published = json.loads((root / "validation.json").read_text())
        result = assess(mask,trace)
        self.assertEqual(result["arms"],published["arms"])
        self.assertEqual(result["distinctDaughterPlanes"],20)
        self.assertEqual(result["uncertainPlanes"],15)
        self.assertEqual(published["staticBaseline"],0)
        # 66-nm predictions span two distinct measured EM planes.
        np.testing.assert_array_equal(mask[::2],mask[1::2])
        self.assertNotEqual((root/"sections/2958.png").read_bytes(),(root/"sections/2959.png").read_bytes())
        index = 2968-2930
        daughter = next(p for p in trace["planes"][index]["points"] if p["arm"] == "daughterB")
        regions, _ = label(mask[index])
        component = regions[int(daughter["y"]+.5),int(daughter["x"]+.5)]
        self.assertGreater(component,0)
        mask[index, regions == component] = False
        interrupted = assess(mask,trace)
        self.assertEqual(interrupted["arms"]["daughterA"],result["arms"]["daughterA"])
        self.assertEqual(interrupted["arms"]["daughterB"]["hits"],19)
        self.assertEqual(interrupted["arms"]["daughterB"]["supportedLinks"],17)
        self.assertEqual(interrupted["distinctDaughterPlanes"],19)
