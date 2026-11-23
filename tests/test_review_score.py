"""Deterministic invented geometry. No slides or human annotations are used."""

import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from pipeline.review_score import coda_export, report
from pipeline.review_import import import_review


def synthetic_split():
    volume = np.zeros((4, 9, 12), bool)
    manifest = dict(
        case="synthetic",
        section_stride=1,
        sampled_interval_um=None,
        cut_thickness_um=None,
        slides=[
            dict(
                slide=f"s{i}",
                section=section,
                sha256=str(i) * 64,
                width=12,
                height=9,
                mpp=None,
                native_to_registered=np.eye(3)[:2].tolist(),
            )
            for i, section in enumerate([1, 2, 3, 5])
        ],
    )
    profiles = []

    def box(z, name, a, b):
        ring = [
            [a - 0.4, 2.6],
            [b + 0.4, 2.6],
            [b + 0.4, 4.4],
            [a - 0.4, 4.4],
            [a - 0.4, 2.6],
        ]
        profiles.append(
            dict(id=name, slide=f"s{z}", status="OBSERVED", role="TARGET", polygon=ring)
        )
        volume[z, 3:5, a : b + 1] = True

    box(0, "parent", 1, 8)
    box(1, "left", 1, 3)
    box(1, "right", 6, 8)
    box(2, "tip", 1, 3)
    box(3, "later", 1, 3)
    review = dict(
        case="synthetic",
        reviewer=dict(
            kind="SYNTHETIC",
            id="A",
            qualifications="Simulated",
            date="2026-01-01",
            blinded=True,
        ),
        planes=[dict(slide=f"s{z}", status="REVIEWED") for z in range(4)],
        profiles=profiles,
        edges=[
            dict(source="parent", target="left", type="SPLITS"),
            dict(source="parent", target="right", type="SPLITS"),
            dict(source="left", target="tip", type="CONTINUES"),
        ],
        intervals=[
            dict(
                source_slide=f"s{z}",
                target_slide=f"s{z + 1}",
                status="REVIEWED" if z == 0 else "INDETERMINATE",
                reason="synthetic test",
            )
            for z in range(3)
        ],
    )
    review["edges"][2]["type"] = "INDETERMINATE"
    # Exercise the same GeoJSON and edge import used by the CODA CLI.
    hashes = {s["slide"]: s["sha256"] for s in manifest["slides"]}
    for plane in review["planes"]:
        plane.update(sha256=hashes[plane["slide"]], reason="Synthetic fixture")
    for edge in review["edges"]:
        edge.update(reason="Synthetic fixture", confidence=1)
    features = []
    for profile in review.pop("profiles"):
        ring = profile.pop("polygon")
        profile.update(
            sha256=hashes[profile["slide"]], reason="Synthetic fixture", confidence=1
        )
        features.append(
            dict(
                type="Feature",
                properties=profile,
                geometry=dict(type="Polygon", coordinates=[ring]),
            )
        )
    edges = review.pop("edges")
    review.update(
        type="FeatureCollection",
        coordinates="native_level0_pixel_edges",
        features=features,
    )
    return (
        volume,
        [np.eye(3)[:2] for _ in volume],
        manifest,
        import_review(manifest, review, edges),
    )


class ReviewScoreTests(unittest.TestCase):
    def test_true_split_missed_stationary_branch_and_exclusions(self):
        v, frames, m, r = synthetic_split()
        reading = report(v, frames, m, [r])["readers"][0]
        actual = reading["candidate"]
        self.assertEqual(actual["totals"]["supportedLinks"], 2)
        self.assertEqual(actual["pairs"][0]["exactSplits"]["tp"], [(1, (2, 3))])
        self.assertEqual(reading["fixedSeed"]["totals"]["missedLinks"], 1)
        self.assertEqual(
            [p["status"] for p in actual["pairs"]], ["reviewed", "uncertain", "missing"]
        )
        self.assertEqual(actual["sections"][1]["dice"], 1.0)
        join = actual["pairs"][0]["predictedJoins"][1]
        self.assertEqual(join["endpoints"][1]["referenceProfile"], "right")
        self.assertEqual(join["endpoints"][1]["xyLevel0"], [6.0, 3.0])
        json.dumps(reading, allow_nan=False)

    def test_unrelated_pair_false_join_and_independent_disagreement(self):
        v, f, m, r = synthetic_split()
        other = copy.deepcopy(r)
        other["reviewer"]["id"] = "B"
        for p in other["profiles"]:
            p["id"] += "-B"
        for e in other["edges"]:
            e["source"] += "-B"
            e["target"] += "-B"
        other["profiles"][2]["role"] = "COMPETITOR"
        other["edges"][0]["type"] = "CONTINUES"
        other["edges"][1]["type"] = "UNRELATED"
        out = report(v, f, m, [r, other])
        self.assertEqual(out["readers"][1]["candidate"]["totals"]["falseLinks"], 1)
        competitor = out["readers"][1]["candidate"]
        self.assertAlmostEqual(competitor["sections"][1]["dice"], 2 / 3)
        self.assertEqual(competitor["sections"][1]["extra"], [2])
        false = competitor["pairs"][0]["predictedJoins"][1]
        self.assertEqual(
            false["endpoints"][1]["overlappingCompetitors"][0]["profile"], "right-B"
        )
        self.assertFalse(
            out["agreement"][0]["planes"][1]["matches"][1]["roleAgreement"]
        )
        v[1, :, 6:] = False
        without_spill = report(v, f, m, [other])["readers"][0]["candidate"]
        self.assertEqual(without_spill["sections"][1]["dice"], 1)
        self.assertEqual(without_spill["sections"][1]["missed"], [])
        a = out["agreement"][0]
        self.assertEqual(a["comparableIntervals"], 1)
        self.assertEqual(a["exactConnectivityAgreements"], 0)
        self.assertEqual(len(a["intervals"][0]["leftOnly"]), 1)
        self.assertEqual(len(a["planes"][1]["matches"]), 2)

    def test_missing_branch_incomplete_raster_and_pending_review(self):
        v, f, m, r = synthetic_split()
        v[1, :, 5:] = False
        out = report(v, f, m, [r])["readers"][0]["candidate"]
        self.assertEqual(out["totals"]["missedLinks"], 1)
        self.assertEqual(len(out["pairs"][0]["exactSplits"]["fn"]), 1)
        r["profiles"][0]["polygon"][1][0] = 21
        out = report(v, f, m, [r])["readers"][0]["candidate"]
        self.assertEqual(out["status"], "NOT EVALUABLE")
        self.assertEqual(out["sections"][0]["status"], "OUTSIDE PREDICTION FIELD")
        self.assertEqual(report(v, f, m, [])["status"], "REVIEW PENDING")
        with self.assertRaisesRegex(ValueError, "Duplicate reviewer"):
            report(v, f, m, [r, r])

    def test_modified_frozen_prediction_rejected(self):
        with TemporaryDirectory() as d:
            (Path(d) / "labels.bin").write_bytes(b"altered")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                coda_export(Path(d), {})


if __name__ == "__main__":
    unittest.main()
