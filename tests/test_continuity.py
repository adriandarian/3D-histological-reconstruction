import unittest

import numpy as np

from pipeline.continuity import score_continuity


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        # One trunk in the middle section spans two distal cross sections.
        self.ref = np.zeros((3, 8, 8), np.int32)
        self.ref[0, 3, 2:6] = 11
        self.ref[1, 3, 2:6] = 20
        self.ref[2, 3, 2] = 50
        self.ref[2, 3, 5] = 51
        self.pairs = [{"status": "reviewed", "edges": [[11, 20]]},
                      {"status": "reviewed", "edges": [[20, 50], [20, 51]]}]

    def test_distinct_reference_ids_verifiable_bifurcation(self):
        metrics = score_continuity(self.ref > 0, self.ref, self.pairs)["totals"]
        self.assertEqual(metrics["supportedLinks"], 3)
        self.assertEqual(metrics["missedSplits"], 0)
        self.assertEqual(metrics["falseSplits"], 0)

    def test_wrong_link_and_missing_branch_after_registration_failure(self):
        pred = self.ref > 0
        pred[2, 3, 5] = False
        self.pairs[1]["registration"] = "fail"
        report = score_continuity(pred, self.ref, self.pairs)
        self.assertEqual(report["pairs"][1]["missedSplits"], [20])
        self.assertEqual(report["pairs"][1]["missedLinks"], [(20, 51)])
        self.assertEqual(report["totals"]["registrationFailures"], 1)
        self.assertEqual(report["totals"]["missedRegions"], 1)
        self.pairs[1]["edges"] = [[20, 51]]
        self.assertEqual(score_continuity(pred, self.ref, self.pairs)["pairs"][1]["falseLinks"], [(20, 50)])

    def test_unreviewed_missing_and_uncertain_distinct_from_absent(self):
        for status in ("unreviewed", "missing", "uncertain"):
            report = score_continuity(self.ref > 0, self.ref, [self.pairs[0], {"status": status}],
                                      reviewed_sections=[True, True, False])
            self.assertEqual(report["totals"]["supportedLinks"], 1)
            self.assertEqual(report["totals"]["excludedPairs"], 1)
            self.assertEqual(report["pairs"][1]["status"], status)
            self.assertNotIn("missedLinks", report["pairs"][1])
        with self.assertRaises(ValueError):
            score_continuity(self.ref > 0, self.ref, self.pairs, reviewed_sections=[True, True, False])

    def test_false_merge_and_split_keep_unmatched_endpoints(self):
        pred = self.ref > 0
        ref = self.ref.copy()
        ref[2, 3, 5] = 0
        pairs = [self.pairs[0], {"status": "reviewed", "edges": [[20, 50]]}]
        report = score_continuity(pred, ref, pairs)
        self.assertEqual(report["totals"]["extraRegions"], 1)
        self.assertEqual(report["pairs"][1]["falseSplits"], [20])
        self.assertEqual(len(report["pairs"][1]["falseLinks"]), 1)
        reversed_pairs = [{"status": "reviewed", "edges": [[50, 20]]},
                          {"status": "reviewed", "edges": [[20, 11]]}]
        self.assertEqual(score_continuity(pred[::-1], ref[::-1], reversed_pairs)["pairs"][0]["falseMerges"], [20])

    def test_empty_planes_and_nonadjacent_reference_id(self):
        blank = np.zeros((2, 4, 4), np.int32)
        pairs = [{"status": "reviewed", "edges": []}]
        self.assertEqual(score_continuity(blank, blank, pairs)["totals"]["falseLinks"], 0)
        self.assertEqual(score_continuity(blank, blank + 1, pairs)["totals"]["missedRegions"], 2)
        self.assertEqual(score_continuity(blank + 1, blank, pairs)["totals"]["falseLinks"], 1)
        with self.assertRaises(ValueError):
            score_continuity(blank, blank, [{"status": "reviewed", "edges": [[1, 42]]}])
