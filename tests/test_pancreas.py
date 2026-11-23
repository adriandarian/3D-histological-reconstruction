import unittest

import numpy as np

from pipeline.pancreas import cavity_candidates, longest_candidate


class PancreasTests(unittest.TestCase):
    def test_invalid_field_and_open_glass_are_excluded(self):
        rgb = np.full((20, 20, 3), 90, np.uint8)
        rgb[6:9, 5:8] = 250
        rgb[13:16, 6:9] = 250
        rgb[:5, 12:15] = 250
        valid = np.ones((20, 20), bool)
        valid[12, 6] = False
        result = cavity_candidates(rgb, valid)
        self.assertEqual(result.sum(), 9)
        self.assertTrue(result[7, 6])

    def test_gaps_and_diagonal_contacts_do_not_join_candidates(self):
        mask = np.zeros((5, 4, 4), bool)
        mask[:2, 2, 2] = True
        mask[2, 1, 2] = True
        mask[4, 1, 2] = True
        self.assertEqual(longest_candidate(mask).sum(), 2)
        self.assertFalse(longest_candidate(mask[2:]).any())
