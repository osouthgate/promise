"""Whole-map rendering retains evidence boundaries and treats report text as data."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/promise/scripts/render_map.py"


class CapabilityMapView(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.report = self.folder / "report.json"
        self.service = self.folder / "service.json"
        self.output = self.folder / "map.html"
        self.citation = {"file": "tests/search.py", "name": "test_search",
                         "lane": "tests", "status": "passing"}
        self.row = {
            "id": "CAP-1", "story": "Search <script>alert(1)</script>",
            "doc": "javascript:alert(1)", "recorded": "not-built", "computed": "proven",
            "bucket": "passing", "citations": [self.citation],
            "scenarios": [
                {"id": "CAP-1.1", "then": "Return the best match", "altitude": "response", "lane": "tests",
                 "evidence": {"status": "missing-citation", "citations": [], "unresolved": []}},
                {"id": "CAP-1.2", "then": "Legacy lane result", "altitude": "response", "lane": "tests"},
            ],
        }
        self.payload = {"mapDigest": "a" * 64, "summary": {}, "lanes": {}, "rows": [self.row]}

    def run_view(self, service=False):
        self.report.write_text(json.dumps(self.payload))
        args = [sys.executable, str(SCRIPT), str(self.report), "--out", str(self.output)]
        if service:
            args += ["--service-report", str(self.service)]
        return subprocess.run(args, capture_output=True, text=True)

    def test_shows_all_rows_and_scenarios_without_promoting_lane_evidence(self):
        second = copy.deepcopy(self.row)
        second.update(id="CAP-2", story="An unbuilt workflow", computed=None, citations=[], scenarios=[])
        self.payload["rows"].append(second)
        before = json.dumps(self.payload)
        result = self.run_view()
        self.assertEqual(result.returncode, 0, result.stderr)
        page = self.output.read_text()
        self.assertIn("2 capabilities", page)
        self.assertIn("CAP-2 · An unbuilt workflow", page)
        self.assertIn("CAP-1.2", page)
        self.assertIn("Explicit scenario evidence: missing-citation", page)
        self.assertIn("Computed row status: lane-green", page)
        self.assertIn("A green lane does not establish scenario proof", page)
        self.assertEqual(page.count("tests/search.py::test_search"), 1)
        self.assertIn("No SLA report supplied", page)
        self.assertIn("not checked", page)
        self.assertNotIn("<script>", page)
        self.assertNotIn('href="javascript:', page)
        self.assertIn("&lt;script&gt;", page)
        self.assertEqual(json.loads(self.report.read_text()), json.loads(before))

    def test_service_replay_and_supplied_assessment_keep_provenance(self):
        self.service.write_text(json.dumps({
            "mapDigest": "a" * 64, "referenceTime": "2026-11-04T12:00:00Z", "replay": True,
            "targets": [{"row": "CAP-1", "target": "accessibility", "status": "unacceptable",
                         "evaluation": "supplied-assessment", "rationale": "<img src=x onerror=alert(1)>"}],
        }))
        result = self.run_view(service=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        page = self.output.read_text()
        self.assertIn("Historical SLA replay", page)
        self.assertIn("2026-11-04T12:00:00Z", page)
        self.assertIn("accessibility · Unacceptable", page)
        self.assertIn("Supplied assessment", page)
        self.assertNotIn("<img", page)

    def test_project_policy_errors_remain_visible(self):
        self.service.write_text(json.dumps({
            "mapDigest": "a" * 64, "referenceTime": "2026-11-04T12:00:00Z", "replay": False,
            "targets": [{"row": None, "target": "unlinked-policy", "status": "invalid-policy",
                         "reasons": ["target threshold is missing"]}],
        }))
        result = self.run_view(service=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        page = self.output.read_text()
        self.assertIn("Service policies without a capability", page)
        self.assertIn("unlinked-policy · Invalid policy", page)
        self.assertIn("target threshold is missing", page)

    def test_scoped_map_and_partial_service_reports_state_their_limits(self):
        self.payload["scope"] = {"rows": ["CAP-1"], "supportingRows": ["CAP-9"]}
        self.assertEqual(self.run_view().returncode, 0)
        self.assertIn("Selected capabilities only: CAP-1", self.output.read_text())
        self.assertIn("Other map capabilities covering supplied inputs: CAP-9", self.output.read_text())
        self.output = self.folder / "service-view.html"
        second = copy.deepcopy(self.row)
        second["id"] = "CAP-2"
        self.payload.pop("scope")
        self.payload["rows"].append(second)
        self.service.write_text(json.dumps({
            "mapDigest": "a" * 64, "referenceTime": "2026-11-04T12:00:00Z", "replay": False,
            "scope": {"rows": ["CAP-1"]}, "targets": [],
        }))
        self.assertEqual(self.run_view(service=True).returncode, 0)
        page = self.output.read_text()
        self.assertIn("SLA report covers selected capabilities only: CAP-1", page)
        self.assertIn("This capability is outside the supplied SLA report", page)
        self.output = self.folder / "invalid.html"
        self.payload["scope"] = {"rows": ["CAP-1", "CAP-999"]}
        result = self.run_view()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())

    def test_nested_evidence_and_summary_are_readable_tables(self):
        self.payload["summary"] = {
            "rows": 1, "run": {"cases": 0, "files": ["tests/result.xml"]},
            "verdicts": {"proven": 1}, "recorded": {"proven": 0},
        }
        self.service.write_text(json.dumps({
            "mapDigest": "a" * 64, "referenceTime": "2026-11-04T12:00:00Z", "replay": False,
            "targets": [{"row": "CAP-1", "target": "latency", "status": "target",
                         "hardBreach": False, "sampleCount": 0,
                         "measurements": {"duration": {"value": 0, "unit": "ms"},
                                          "unfamiliarMetric": None,
                                          "latency_ms": {"value": 10, "unit": "ms"},
                                          "latencyMs": {"value": 20, "unit": "ms"}},
                         "evidence": [{"ref": "<script>bad</script>", "description": "Fixture result"}],
                         "reasons": [], "evaluation": "supplied-assessment"}],
        }))
        result = self.run_view(service=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        page = self.output.read_text()
        self.assertIn('<table class="evidence-table">', page)
        self.assertIn('scope="row">Hard limit breached</th><td>No</td>', page)
        self.assertIn('scope="row">Number of samples</th><td>0</td>', page)
        self.assertIn('scope="row">Unfamiliar metric (unfamiliarMetric)</th><td>Not reported</td>', page)
        self.assertIn("Latency ms (latency_ms)", page)
        self.assertIn("Latency ms (latencyMs)", page)
        self.assertIn('scope="row">Reasons</th><td>None reported</td>', page)
        self.assertIn('scope="row">Lane green</th><td>1</td>', page)
        self.assertIn('scope="row">Proven</th><td>0</td>', page)
        self.assertIn("latency · Target met", page)
        self.assertIn("tests/result.xml", page)
        self.assertNotIn('"hardBreach":', page)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;bad&lt;/script&gt;", page)

    def test_rejects_mismatched_snapshots_and_malformed_exports(self):
        self.service.write_text(json.dumps({
            "mapDigest": "b" * 64, "referenceTime": "now", "replay": False, "targets": [],
        }))
        result = self.run_view(service=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("same map snapshot", result.stderr)
        self.assertFalse(self.output.exists())
        for malformed in ({"computed": []}, {"citations": [{}]},
                          {"scenarios": [{"evidence": {"status": "passing", "citations": None}}]}):
            with self.subTest(malformed=malformed):
                self.payload["rows"] = [{**self.row, **malformed}]
                result = self.run_view()
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(self.output.exists())

    def test_no_overwrite_and_empty_map(self):
        self.payload["rows"] = []
        self.assertEqual(self.run_view().returncode, 0)
        self.assertIn("The map has no capabilities", self.output.read_text())
        original = self.output.read_bytes()
        self.assertNotEqual(self.run_view().returncode, 0)
        self.assertEqual(self.output.read_bytes(), original)
        self.output = self.report
        self.assertNotEqual(self.run_view().returncode, 0)
        self.assertEqual(json.loads(self.report.read_text()), self.payload)


if __name__ == "__main__":
    unittest.main()
