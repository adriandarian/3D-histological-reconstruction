import unittest
import numpy as np
from scripts.robustness_measured import contact_areas


class ContactPerturbations(unittest.TestCase):
    def test_translation_preserves_ids_and_does_not_wrap_at_crop_edge(self):
        earlier = np.array([[1, 1, 0, 2]])
        later = np.array([[3, 3, 0, 4]])
        self.assertEqual(contact_areas(earlier, later, 0, 0), {(1, 3): 2, (2, 4): 1})
        self.assertEqual(contact_areas(earlier, later, 1, 0), {(1, 3): 1})
        self.assertEqual(contact_areas(earlier, later, -2, 0), {(1, 4): 1})
        self.assertEqual(contact_areas(earlier, later, 4, 0), {})
