"""Importer contracts use invented polygons, identities and landmarks exclusively."""
import copy
import tempfile
import unittest
from pathlib import Path

from pipeline.review_import import import_review, landmark_report, read_edges, validate_manifest


def synthetic_packet():
    slides = []
    for i in range(4):
        slides.append(dict(slide=f"synthetic-{i}", section=[1, 3, 5, 9][i], width=20, height=20,
                           sha256=str(i)*64, native_to_registered=[[1, 0, -i], [0, 1, 0]],
                           calibration_verified=True, mpp=[2, 3]))
    manifest = dict(case="synthetic", section_stride=2, sampled_interval_um=10, cut_thickness_um=None, slides=slides)
    planes = [dict(slide=s["slide"], sha256=s["sha256"], status="REVIEWED", reason="Synthetic fixture") for s in slides]
    intervals = [dict(source_slide=a["slide"], target_slide=b["slide"], reason="Synthetic fixture",
                      status="INDETERMINATE" if b["section"] == 9 else "REVIEWED") for a, b in zip(slides, slides[1:])]
    reviewer = dict(id="fixture", kind="SYNTHETIC", qualifications="Simulation", date="2026-01-01", blinded=True)
    geo = dict(type="FeatureCollection", coordinates="native_level0_pixel_edges", case="synthetic",
               reviewer=reviewer, planes=planes, intervals=intervals, features=[])
    for name, i, x in [("parent", 0, 1), ("daughterA", 1, 1), ("daughterB", 1, 4), ("neighbor", 1, 8),
                       ("merged", 2, 1)]:
        props = dict(slide=slides[i]["slide"], sha256=slides[i]["sha256"], status="OBSERVED", id=name,
                     confidence=1, reason="Synthetic fixture", role="COMPETITOR" if name == "neighbor" else "TARGET")
        ring = [[x, 1], [x+2, 1], [x+2, 3], [x, 1]]
        geo["features"].append(dict(type="Feature", properties=props, geometry=dict(type="Polygon", coordinates=[ring])))
    edges = [dict(source=src, target=dst, type=kind, reason="Synthetic fixture", confidence=1)
             for src, dst, kind in [("parent", "daughterA", "SPLITS"), ("parent", "daughterB", "SPLITS"),
                                    ("parent", "neighbor", "UNRELATED"), ("daughterA", "merged", "MERGES"),
                                    ("daughterB", "merged", "MERGES")]]
    return manifest, geo, edges


class ReviewImportTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.geo, self.edges = synthetic_packet()

    def load(self):
        return import_review(self.manifest, self.geo, self.edges)

    def test_valid_branch_and_gap(self):
        imported = self.load()
        self.assertEqual(imported["edges"], self.edges)
        self.assertEqual(imported["intervals"][-1]["status"], "INDETERMINATE")
        self.assertEqual(imported["reviewer"]["kind"], "SYNTHETIC")

    def test_invalid_geometry(self):
        ring = self.geo["features"][0]["geometry"]["coordinates"]
        for invalid in ([[0, 0], [1, 1], [2, 0]], [[0, 0], [2, 2], [2, 0], [0, 2], [0, 0]],
                        [[0, 0], [float("nan"), 1], [2, 0], [0, 0]], [[0, 0], [21, 1], [2, 0], [0, 0]]):
            ring[0] = invalid
            with self.assertRaises(ValueError):
                self.load()

    def test_invalid_annotations_and_branch_cardinality(self):
        for mutation in (
            lambda: self.geo["reviewer"].pop("qualifications"),
            lambda: self.geo["reviewer"].update(blinded=False),
            lambda: self.geo.update(coordinates="crop"),
            lambda: self.geo["features"][0]["properties"].pop("role"),
            lambda: self.geo["features"][0]["properties"].update(role="OTHER"),
            lambda: self.geo["features"][0]["properties"].update(role="COMPETITOR"),
            lambda: self.geo["features"].append(self.geo["features"][0]),
            lambda: self.geo["features"][0]["properties"].update(sha256="f"*64),
            lambda: self.edges[0].update(target="unknown"),
            lambda: self.edges[0].update(confidence=1.1),
            lambda: self.edges[0].update(type="CONTINUES"),
            lambda: self.edges.append(self.edges[0]),
            lambda: self.edges[0].update(source="merged"),
            lambda: self.geo["intervals"][0].update(status="INDETERMINATE"),
            lambda: self.geo["intervals"][2].update(status="REVIEWED"),
            lambda: self.geo["planes"][0].update(status="INDETERMINATE"),
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                mutation()
                with self.assertRaises((ValueError, KeyError)):
                    self.load()

    def test_order_transform_and_spacing(self):
        for bad in (dict(section=1), dict(native_to_registered=[[0, 0, 1], [0, 0, 2]]),
                    dict(crop_origin_level0=[0, 0], crop_size=[11, 11], crop_step_level0=2),
                    dict(calibration_verified=False), dict(mpp=[-1, 1])):
            manifest = copy.deepcopy(self.manifest)
            manifest["slides"][1].update(bad)
            with self.assertRaises(ValueError):
                validate_manifest(manifest)

    def test_unpinned_coda_registration_is_rejected(self):
        self.manifest["case"] = "coda-lung"
        with self.assertRaisesRegex(ValueError, "frozen CODA"):
            validate_manifest(self.manifest)

    def test_csv_json_parity(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "edges.csv"
            path.write_text("source,target,type,reason,confidence\nparent,daughterA,SPLITS,Synthetic fixture,1\n")
            self.assertEqual(read_edges(path), self.edges[:1])

    def test_withheld_registration_and_units(self):
        mark = dict(id="bif", source_slide="synthetic-0", source_xy=[3, 4], source_sha256="0"*64,
                    target_slide="synthetic-1", target_xy=[7, 8], target_sha256="1"*64)
        document = dict(case="synthetic", coordinates="native_level0_pixel_edges", reviewer=self.geo["reviewer"],
                        withheld_from_registration=True, landmarks=[mark])
        report = landmark_report(self.manifest, document)
        self.assertEqual(report["mean_target_px"], 5)
        self.assertAlmostEqual(report["mean_um"], (6**2 + 12**2)**.5)
        self.manifest["slides"][1]["mpp"] = None
        self.assertIsNone(landmark_report(self.manifest, document)["mean_um"])
        document["landmarks"] = []
        self.assertEqual(landmark_report(self.manifest, document)["status"], "NOT EVALUABLE")
        document["withheld_from_registration"] = False
        with self.assertRaises(ValueError):
            landmark_report(self.manifest, document)
