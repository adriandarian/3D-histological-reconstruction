import unittest

import numpy as np

from pipeline.robustness_phantom import generate, reference_pairs
from scripts.connection_robustness import connected_families, evaluate, fused_families, summarize


class ConnectionOutcomes(unittest.TestCase):
    def test_oracle_and_measured_gate(self):
        _, ids = generate(11)
        result, rows = evaluate(ids > 0, ids, reference_pairs(ids, range(25)),
                                [0, 24], np.ones(24))
        self.assertEqual(result["connected_family_pairs"], 0)
        self.assertEqual(result["hidden_dice"], 1)
        self.assertEqual(result["sampled_branch_path"], 1)
        all_pairs = summarize(rows)
        self.assertEqual(all_pairs["fp"] + all_pairs["fn"], 0)
        self.assertEqual(all_pairs["branch_recovered"], 1)
        excluded = summarize(rows, threshold=.9, measured_only=True)
        self.assertEqual(excluded["accepted"], 0)
        self.assertEqual(excluded["rejected_truth"], all_pairs["tp"])

    def test_gap_bridge_with_no_in_plane_fusion(self):
        ids = np.zeros((3, 5, 5), np.uint8)
        ids[0, 2, 2] = 6
        ids[2, 2, 2] = 7
        mask = ids > 0
        self.assertEqual(connected_families(mask, ids), set())
        mask[1, 2, 2] = True
        self.assertEqual(fused_families(mask, ids), 0)
        self.assertEqual(connected_families(mask, ids), {(6, 7)})
