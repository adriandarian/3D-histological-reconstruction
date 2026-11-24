import unittest

import numpy as np

from pipeline.connection_evidence import build_graph


def graph(mask, *, retained=None, **extra):
    if retained is None:
        retained = range(len(mask))
    sections = [dict(id=f"s{z}", measured=z in retained) for z in range(len(mask))]
    return build_graph(mask, sections, registration="identity", segmentation="fixture", **extra)


class ConnectionEvidenceTests(unittest.TestCase):
    def test_false_path_across_unmatched_intermediate_planes(self):
        mask = np.zeros((9, 7, 7), bool)
        mask[:, 1:5, 2:5] = True
        truth = np.zeros_like(mask, dtype=int)
        truth[0][mask[0]] = 6
        truth[-1][mask[-1]] = 7
        g = graph(mask, retained=[0, 8], oracle=truth, families={6: 6, 7: 7})
        self.assertEqual(len(g["edges"]), 8)
        for edge in g["edges"]:
            self.assertTrue({"contradicted", "mixed_path", "inferred_gap"} <= set(edge["flags"]))
            self.assertNotIn("verified_identity", edge["flags"])
            self.assertEqual(edge["missingSections"], [f"s{i}" for i in range(1, 8)])
            self.assertEqual(edge["contactPixels"], 12)
            for point, z_expected in zip(edge["flanks"], [0, 8]):
                x, y, z = point
                self.assertTrue(mask[z, y, x])
                self.assertEqual(z, z_expected)

    def test_source_ids_can_skip_cuts_without_a_dense_interpolated_plane(self):
        sections = [dict(id="slide001", measured=True),
                    dict(id="slide003", measured=True, missingBefore=["slide002"])]
        e, = build_graph(np.ones((2, 2, 2), bool), sections, registration="rigid",
                         segmentation="candidate")["edges"]
        self.assertEqual(e["missingSections"], ["slide002"])
        self.assertIn("inferred_gap", e["flags"])
        self.assertIn("unresolved", e["flags"])

    def test_perturbations_and_review_scope(self):
        mask = np.zeros((3, 7, 10), bool)
        mask[:, 2:5, 2] = True
        mask[:, 2:5, 4] = True
        refs = {(0, 1, 1): dict(status="verified", source="test-only independent trace",
                                reason="Named endpoint pair is independently traced")}
        edges = graph(mask, references=refs)["edges"]
        self.assertEqual(len(edges), 4)
        for edge in edges:
            self.assertIn("registration_sensitive", edge["flags"])
            self.assertIn("segmentation_sensitive", edge["flags"])
            self.assertIn("observed_contact", edge["flags"])
            self.assertEqual(edge["erodedContactPixels"], 0)
            self.assertTrue(edge["dilationFusion"])
            self.assertIn("unresolved", edge["pathRisk"].lower())
            if edge["id"] == "0:1>1":
                self.assertIn("verified_identity", edge["flags"])
            else:
                self.assertIn("unresolved", edge["flags"])
        with self.assertRaisesRegex(ValueError, "nonexistent"):
            graph(mask, references={(0, 99, 99): refs[0, 1, 1]})

    def test_gap_branch_flanks_and_unreachable_flank(self):
        mask = np.zeros((5, 4, 9), bool)
        mask[:2, 1, 1:7] = True
        mask[2:, 1, 1:3] = True
        mask[2:4, 1, 5:7] = True
        mask[4, 1, 5:7] = True
        for edge in graph(mask, retained=[0,4])["edges"]:
            self.assertIn("split_depth_uncertain", edge["flags"])
        # Both endpoints of the last local contact are interpolated and no
        # corresponding component exists on either measured boundary.
        mask[0] = mask[4] = False
        for edge in graph(mask, retained=[0,4])["edges"]:
            self.assertEqual(edge["flanks"], [None, None])
            self.assertEqual(edge["flankSections"], [0, 4])
            self.assertIn("unresolved", edge["flags"])
