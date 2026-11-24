"""Geometry and acquisition checks for the independently specified lineage phantom."""
import unittest

import numpy as np

from pipeline.continuity import score_continuity
from pipeline.robustness_phantom import (
    BRANCH_EDGES, DEPTH, SPLIT_Z, PhantomSettings, generate, reference_pairs,
)


class PhantomRobustnessTests(unittest.TestCase):
    def test_oracle_masks_recover_dense_lineage_and_one_split(self):
        for seed in (3, 41, 73):
            with self.subTest(seed=seed):
                _, truth = generate(seed)
                pairs = reference_pairs(truth, range(DEPTH))
                self.assertTrue(set(BRANCH_EDGES).issubset(pairs[SPLIT_Z - 1]["edges"]))
                totals = score_continuity(truth > 0, truth, pairs)["totals"]
                self.assertGreater(totals["supportedLinks"], 100)
                for metric in ("missedLinks", "falseLinks", "missedSplits", "falseSplits",
                               "missedMerges", "falseMerges"):
                    self.assertEqual(totals[metric], 0, metric)
                self.assertTrue(((truth == 6)[:, :, 0]).any())
                self.assertTrue(((truth == 7)[:, :, 0]).any())
                # Sparse sampling across different boundary identities cannot
                # turn a field exit and re-entry into a positive truth edge.
                edges = reference_pairs(truth, [8, 19])[0]["edges"]
                self.assertNotIn((6, 7), edges)
                self.assertTrue(set(BRANCH_EDGES).issubset(edges))

    def test_paired_realizations_and_first_plane_anchor(self):
        baseline, truth = generate(23)
        perturb = PhantomSettings(translation_px=4, rotation_deg=8, deformation_px=2)
        changed, reference = generate(23, perturb)
        np.testing.assert_array_equal(reference, truth)
        np.testing.assert_array_equal(changed[0], baseline[0])
        np.testing.assert_array_equal(changed, generate(23, perturb)[0])
        self.assertFalse(np.array_equal(changed[1:], baseline[1:]))
        self.assertFalse(np.array_equal(generate(22)[1], truth))

    def test_artifacts_affect_only_challenged_planes(self):
        clean, truth = generate(17)
        fold, reference = generate(17, PhantomSettings(fold=True))
        np.testing.assert_array_equal(truth, reference)
        np.testing.assert_array_equal(np.where(np.any(fold != clean, axis=(1, 2, 3)))[0],
                                      np.arange(9, 13))
        loss, _ = generate(17, PhantomSettings(tissue_loss=True))
        np.testing.assert_array_equal(np.where(np.any(loss != clean, axis=(1, 2, 3)))[0],
                                      np.arange(11, 15))
        for indices in ([2, 2], [-1, 3], [0, DEPTH]):
            with self.assertRaises(ValueError):
                reference_pairs(truth, indices)
