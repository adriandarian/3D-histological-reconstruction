"""Ground truth, topology fault detection and mesh/source round-trip checks."""

from collections import Counter
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.branching import export, section_graph, source_sections


class BranchingTests(unittest.TestCase):
    def test_export_recovers_one_parent_and_two_distal_branches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = export(root)
            self.assertGreater(report["dice"], 0.97)
            self.assertTrue(report["graphMatches"])
            graph = report["recoveredGraph"]
            self.assertEqual(graph["roots"], [0])
            self.assertEqual(graph["tips"], [31, 31])
            self.assertEqual(graph["splits"], [14])
            self.assertEqual(graph["merges"], [])
            manifest = json.loads((root / "manifest.json").read_text())
            shape = manifest["dimensions"][::-1]
            stack = np.fromfile(root / manifest["rgb"], np.uint8).reshape(*shape, 3)
            for z, path in enumerate(manifest["sections"]):
                np.testing.assert_array_equal(stack[z], np.asarray(Image.open(root / path)))
            labels = np.fromfile(root / manifest["labels"], np.uint8).reshape(shape)
            mesh = json.loads((root / manifest["mesh"]).read_text())
            points = np.array(mesh["positions"]).reshape(-1, 3)
            triangles = np.array(mesh["indices"]).reshape(-1, 3)
            edges = Counter()
            for a, b, c in triangles:
                for i, j in ((a, b), (b, c), (c, a)):
                    edges[i, j] += 1
            self.assertEqual(edges, Counter({(j, i): n for (i, j), n in edges.items()}))
            # A step inward along each outward face normal lands in a labeled voxel.
            faces = points[triangles]
            normals = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
            xyz = np.rint(faces.mean(axis=1) - normals * 0.25).astype(int)
            self.assertTrue((labels[xyz[:, 2], xyz[:, 1], xyz[:, 0]] == 2).all())

    def test_missing_section_breaks_connectivity_despite_high_overlap(self):
        _, truth = source_sections()
        interrupted = truth.copy()
        interrupted[20] = False
        self.assertNotEqual(section_graph(truth), section_graph(interrupted))
        self.assertEqual(section_graph(interrupted)["roots"], [0, 21, 21])
