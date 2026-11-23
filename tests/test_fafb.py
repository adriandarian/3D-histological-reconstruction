"""A real named fork must demonstrate evidence beyond seed-mask containment."""

import hashlib
import json
from pathlib import Path
import unittest

import numpy as np
from PIL import Image

from pipeline.fafb import DAUGHTERS, assess, reconstruct, remove_resolved_arm


class FafbForkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = Path(__file__).resolve().parents[1] / "public" / "bifurcation"
        cls.manifest = json.loads((cls.folder / "manifest.json").read_text(encoding="utf8"))
        cls.trace = json.loads((cls.folder / cls.manifest["reference"]).read_text())
        cls.report = json.loads((cls.folder / cls.manifest["validation"]).read_text())
        cls.shape = cls.manifest["dimensions"][::-1]
        cls.mask = np.fromfile(cls.folder / cls.manifest["labels"], np.uint8).reshape(cls.shape) == 2

    def test_parent_reconstruction_excludes_disconnected_id_fragments(self):
        ids = np.zeros((2, 4, 4), np.uint64)
        ids[:, 0, 0] = 13
        ids[:, 3, 3] = 13
        mask, info = reconstruct(ids, {"x": 0, "y": 0})
        self.assertEqual(info["segmentId"], "13")
        self.assertEqual(info["discardedDisconnectedVoxels"], 2)
        self.assertTrue(mask[:, 0, 0].all())
        self.assertFalse(mask[:, 3, 3].any())

    def test_source_sections_and_archived_topology(self):
        rgb = np.fromfile(self.folder / self.manifest["rgb"], np.uint8).reshape(*self.shape, 3)
        self.assertEqual(hashlib.sha256(rgb[..., 0].tobytes()).hexdigest(), self.report["imageSha256"])
        for i, filename in enumerate(self.manifest["sections"]):
            self.assertEqual(filename, f"sections/{4691+i}.png")
            np.testing.assert_array_equal(np.asarray(Image.open(self.folder / filename)), rgb[i, ..., 0])
        rows = [p for plane in self.trace["planes"] for p in plane["points"]]
        self.assertEqual({p["node"] for p in rows if p["parent"] == 780}, {835, 781})
        self.assertEqual(self.report["archivedReference"]["edges"], 41)

    def test_both_independently_identified_daughter_paths(self):
        report = assess(self.mask, self.trace)
        for field, value in report.items():
            self.assertEqual(value, self.report[field])
        self.assertEqual(report["directDaughterSplitZ"], [4708])
        self.assertEqual(report["distinctDaughterPlanes"], list(range(4708, 4716)))
        for arm, n in zip(DAUGHTERS, [17, 16]):
            self.assertEqual(report["arms"][arm]["supportedEdges"], n)
            self.assertEqual(report["arms"][arm]["reachablePoints"], n)
        static = assess(np.broadcast_to(self.mask[0], self.mask.shape), self.trace)
        self.assertEqual(static["arms"], report["arms"])
        self.assertEqual(static["directDaughterSplitZ"], [])
        self.assertEqual(static["distinctDaughterPlanes"], [])

    def test_removing_each_daughter_invalidates_only_its_distal_path(self):
        for arm, other in [DAUGHTERS, DAUGHTERS[::-1]]:
            without_arm = remove_resolved_arm(self.mask, self.report, arm)
            control = assess(without_arm, self.trace)
            expected = self.report["removedDaughterControls"][arm]
            self.assertEqual(control["arms"], expected["arms"])
            self.assertEqual(control["arms"][other], self.report["arms"][other])
            self.assertEqual(control["arms"][arm]["hits"], self.report["arms"][arm]["hits"] - 8)
            self.assertEqual(control["directDaughterSplitZ"], [])
            self.assertEqual(control["distinctDaughterPlanes"], [])
