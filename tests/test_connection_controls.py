import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
from PIL import Image

from pipeline.robustness_phantom import generate
from scripts.connection_controls import CONTROLS, export_control


ROOT = Path(__file__).resolve().parents[1]
PACKAGED = ROOT / "public/evidence-controls"


class ConnectionControlTests(unittest.TestCase):
    def test_export_matches_study_and_distributes_only_retained_images(self):
        with (ROOT / "docs/robustness/runs.csv").open() as stream:
            frozen = {r["scenario"]: r for r in csv.DictReader(stream)
                      if (r["seed"], r["registration"], r["method"]) == ("11", "0", "signed_distance")}
        with TemporaryDirectory() as temp:
            for name, (scenario, _) in CONTROLS.items():
                with self.subTest(name=name):
                    manifest = export_control(name, Path(temp))
                    folder = PACKAGED / name
                    self.assertEqual(json.loads((folder / "manifest.json").read_bytes()), manifest)
                    self.assertEqual(float(frozen[scenario]["dice"]), manifest["dice"])
                    self.assertEqual((Path(temp) / name / "graph.json").read_bytes(), (folder / "graph.json").read_bytes())
                    self.assertEqual((Path(temp) / name / manifest["rgb"]).read_bytes(),
                                     (folder / manifest["rgb"]).read_bytes())
                    rgb = np.fromfile(folder / manifest["rgb"], np.uint8).reshape(25, 96, 96, 3)
                    opacity = np.fromfile(folder / manifest["foreground"], np.uint8).reshape(rgb.shape[:-1])
                    paths = {folder / p for p in manifest["sections"] if p}
                    self.assertEqual(paths, set((folder / "sections").glob("*.png")))
                    for z, p in enumerate(manifest["sections"]):
                        if p:
                            with Image.open(folder / p) as im:
                                np.testing.assert_array_equal(rgb[z], np.asarray(im))
                        else:
                            self.assertTrue((rgb[z] == 255).all())
                            self.assertFalse(opacity[z].any())

    def test_chosen_connections_demonstrate_the_intended_failure(self):
        for name in CONTROLS:
            with self.subTest(name=name):
                manifest = json.loads((PACKAGED / name / "manifest.json").read_bytes())
                graph = json.loads((PACKAGED / name / manifest["graph"]).read_bytes())
                edge = next(e for e in graph["edges"] if e["id"] == manifest["defaultEdge"])
                flags = set(edge["flags"])
                self.assertNotIn("verified_identity", flags)
                if name == "field-gap":
                    self.assertGreater(manifest["dice"], .94)
                    self.assertTrue({"inferred_gap", "contradicted", "mixed_path"} <= flags)
                    self.assertEqual([p[2] for p in edge["flanks"]], [8, 16])
                    self.assertEqual([edge["a"][2], edge["b"][2]], [12, 13])
                    self.assertEqual(manifest["sections"][9:16], [None] * 7)
                    _, identities = generate(11)
                    for field in ("a", "b"):
                        x, y, z = edge[field]
                        self.assertEqual(identities[z, y, x], 0)
                    self.assertIn("6, 7", edge["pathRisk"])
                elif name == "branch-depth":
                    self.assertTrue({"inferred_gap", "split_depth_uncertain"} <= flags)
                    self.assertEqual([p[2] for p in edge["flanks"]], [8, 12])
                    self.assertTrue(any("cannot locate its exact depth" in r for r in edge["reasons"]))
                else:
                    self.assertTrue({"observed_contact", "contradicted", "mixed_path"} <= flags)
                    self.assertTrue(any("profiles 4 and 5" in r for r in edge["reasons"]))
