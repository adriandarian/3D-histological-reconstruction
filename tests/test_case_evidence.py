import hashlib
import json
from pathlib import Path
import unittest

from scripts.export_connection_evidence import PROVENANCE, graph_references


class CaseEvidence(unittest.TestCase):
    def test_all_packaged_graphs_match_inputs_and_record_two_source_coordinates(self):
        for case in set(PROVENANCE) - {"coda-lung"}:
            with self.subTest(case=case):
                case_dir = Path("public") / case
                graph = json.loads(Path(f"public/connection-evidence/{case}.json").read_bytes())
                manifest_bytes = (case_dir / "manifest.json").read_bytes()
                manifest = json.loads(manifest_bytes)
                self.assertEqual(graph["manifestSha256"], hashlib.sha256(manifest_bytes.replace(b"\r\n", b"\n")).hexdigest())
                self.assertEqual(graph["labelsSha256"], hashlib.sha256((case_dir / manifest["labels"]).read_bytes()).hexdigest())
                self.assertGreater(len(graph["edges"]), 0)
                refs = graph_references(case, case_dir, manifest)
                for edge in graph["edges"]:
                    self.assertEqual(len(edge["sourceCoordinates"]), 2)
                    for point, native in zip(edge["flanks"], edge["sourceCoordinates"]):
                        self.assertEqual(native["section"], graph["sections"][point[2]]["id"])
                        self.assertEqual(len(native["xy"]), 2)
                    key = edge["a"][2], edge["fromComponent"], edge["toComponent"]
                    self.assertEqual("verified_identity" in edge["flags"], refs.get(key, {}).get("status") == "verified")

    @unittest.skipUnless(Path("public/data/coda-lung/connections.json").exists(), "requires local CODA evidence")
    def test_coda_graph_never_promotes_unadjudicated_calls(self):
        graph = json.loads(Path("public/data/coda-lung/connections.json").read_bytes())
        self.assertEqual(len(graph["edges"]), 19)
        for z, edge in enumerate(graph["edges"]):
            self.assertIn("inferred_gap", edge["flags"])
            self.assertNotIn("verified_identity", edge["flags"])
            self.assertEqual(edge["missingSections"], [f"undistributed section {2*z+2:03d}"])
            self.assertEqual(edge["sourceCoordinates"][0]["frame"], "NDPI level-zero pixel edges")
