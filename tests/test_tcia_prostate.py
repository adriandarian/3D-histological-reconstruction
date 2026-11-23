import json
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile

import numpy as np

from scripts import tcia_prostate as study


class ProstateHoldouts(unittest.TestCase):
    def test_predictions_can_be_generated_without_holdout_xml(self):
        frames = dict(origin=[0,0],extent=[256,256],file="test.tif")
        image = np.zeros((256,256,3),np.uint8)
        mask = np.zeros((256,256),bool)
        mask[20:30,20:30] = True
        def known_inputs(root, level, suffix):
            if suffix == "xml":
                self.assertIn(level,study.ANCHORS)
            return Path(level)
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)
            with patch.object(study,"path_for",side_effect=known_inputs), patch.object(study,"section",return_value=(image,frames)), patch.object(study,"tumor",return_value=mask):
                study.reconstruct(out,out)
            volume=np.fromfile(out/"labels.bin",np.uint8).reshape(6,256,256)==2
            for plane in volume:
                np.testing.assert_array_equal(plane,mask)
            self.assertEqual(json.loads((out/"manifest.json").read_text())["dimensions"],[256,256,6])

    def test_complete_miss_reports_excess_and_missed_area(self):
        pred=np.array([True,False,False])
        ref=np.array([False,True,True])
        self.assertEqual(study.metrics(pred,ref),dict(dice=0,overlap_px=0,excess_px=1,missed_px=2))
    def test_published_scores_match_the_frozen_volume_and_held_out_masks(self):
        import hashlib
        root=Path(__file__).resolve().parents[1]
        data=root/"public/tcia-prostate"
        result=json.loads((root/"docs/tcia-prostate/scores.json").read_text())
        raw=(data/"labels.bin").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),result["prediction_sha256"])
        masks=np.frombuffer(raw,np.uint8).reshape(6,256,256)==2
        refs=np.fromfile(data/"held-out.bin",np.uint8).reshape(masks.shape).astype(bool)
        for level in study.HOLDOUT:
            z=study.LEVELS.index(level)
            self.assertEqual(study.metrics(masks[z],refs[z]),result["levels"][level]["interpolation"])
            self.assertEqual(study.metrics(masks[z-1],refs[z]),result["levels"][level]["nearest"])
