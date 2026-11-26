import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/promise/scripts/render_view.py"
EXAMPLE = ROOT / "examples/channel-muting.md"


class RenderView(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.folder = Path(scratch.name)

    def cli(self, source, *args, check=True, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(source), *map(str, args)],
            capture_output=True,
            check=check,
            env=env,
        )

    def test_json_preserves_tldr_line_endings_and_leaves_source_untouched(self):
        source = self.folder / "outcome.md"
        original = EXAMPLE.read_text(encoding="utf-8").replace("\n", "\r\n").encode()
        source.write_bytes(original)
        before = source.stat().st_mtime_ns

        view = json.loads(self.cli(source, "--json", env={**os.environ, "PYTHONIOENCODING": "ascii"}).stdout)
        start = original.index(b"## 0. TLDR")
        end = original.index(b"Agent notes", start)
        self.assertEqual(view["tldr"].encode(), original[start:end])
        self.assertEqual(view["agentNotes"].encode(), original[end:original.index(b"## 1. Problem")])
        self.assertEqual(len(view["rules"]), 2)
        self.assertEqual(len(view["rows"]), 3)
        page = self.folder / "view.html"
        self.cli(source, "--out", page)
        self.assertIn("Confirmed there is no existing mute primitive", page.read_text(encoding="utf-8"))

        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(source.stat().st_mtime_ns, before)

    def test_html_treats_supplied_markup_as_text(self):
        source = self.folder / "outcome.md"
        payload = '</title><script>alert(1)</script><img src=x onerror=alert(1)>'
        source.write_text(
            EXAMPLE.read_text(encoding="utf-8").replace("# Channel muting", "# " + payload)
            .replace("**Outcome:**", "**Outcome:** " + payload),
            encoding="utf-8",
        )
        output = self.folder / "view.html"
        self.cli(source, "--out", output)

        page = output.read_text(encoding="utf-8")
        self.assertNotIn("<script>", page)
        self.assertNotIn("<img ", page)
        self.assertIn("&lt;/title&gt;&lt;script&gt;", page)
        self.assertIn("Rules and acceptance rows", page)
        self.assertIn("AT-1", page)

    def test_refuses_to_overwrite_source_or_an_existing_page(self):
        source = self.folder / "outcome.md"
        original = EXAMPLE.read_bytes()
        source.write_bytes(original)
        result = self.cli(source, "--out", source, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(source.read_bytes(), original)

        output = self.folder / "view.html"
        output.write_text("Keep this", encoding="utf-8")
        result = self.cli(source, "--out", output, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_text(encoding="utf-8"), "Keep this")

    def test_reports_keep_row_test_and_service_evidence_separate(self):
        source = self.folder / "outcome.md"
        baseline = json.loads(self.cli(EXAMPLE, "--json").stdout)
        then = baseline["rows"][0]["then"]
        altitude = baseline["rows"][0]["altitude"]
        text = EXAMPLE.read_text(encoding="utf-8").replace("→ AT-1, AT-2", "→ AT-2")
        lines = text.splitlines()
        header = next(index for index, line in enumerate(lines) if line.startswith("| # "))
        for offset, cell in enumerate(("Row", "-----", "CAP-1", "", "")):
            lines[header + offset] += f" {cell} |"
        source.write_text("\n".join(lines) + "\n", encoding="utf-8")
        map_report = self.folder / "map.json"
        entry = {
            "id": "CAP-1", "doc": "./outcome.md", "recorded": "under-proven",
            "computed": "proven", "scenarios": [{"then": then, "altitude": altitude, "lane": "tests"}],
            "citations": [
                {"file": "tests/test_view.py", "name": "test_one", "lane": "tests", "status": "passing"},
                {"file": "another.py", "name": "unrelated", "lane": "e2e", "status": "passing"},
            ],
        }
        map_payload = {"mapDigest": "a" * 64, "summary": {}, "lanes": {}, "rows": [entry]}
        map_report.write_text(json.dumps(map_payload))
        service_report = self.folder / "service.json"
        service_report.write_text(json.dumps({
            "mapDigest": "a" * 64, "referenceTime": "2026-11-04T12:00:00+00:00", "replay": True,
            "targets": [
                {"row": "CAP-1", "target": "availability", "status": "unacceptable",
                 "source": "<script>unsafe</script>", "evaluation": "supplied-assessment",
                 "assessmentBand": "unacceptable"},
                {"row": "CAP-2", "target": "unrelated", "status": "target"},
            ],
        }))
        args = ("--project-root", self.folder, "--map-report", map_report,
                "--service-report", service_report, "--source-revision", "rev-one")
        view = json.loads(self.cli(source, "--json", *args).stdout)
        proof = view["rows"][0]["evidence"]
        self.assertEqual(view["provenance"]["sourceRevision"], "rev-one")
        self.assertTrue(view["evidenceSources"]["service"]["replay"])
        self.assertEqual(proof["recordedVerdict"], "under-proven")
        self.assertEqual(proof["computedRowStatus"], "lane-green")
        self.assertEqual([c["name"] for c in proof["testCitations"]], ["test_one"])
        self.assertEqual([s["status"] for s in proof["serviceTargets"]], ["unacceptable"])

        output = self.folder / "view.html"
        self.cli(source, "--out", output, *args)
        page = output.read_text(encoding="utf-8")
        self.assertIn("Historical SLA replay", page)
        self.assertIn("Acceptance rows without a rule tag", page)
        self.assertIn("Test: <code>tests/test_view.py::test_one</code> · passing", page)
        self.assertIn("does not establish scenario proof", page)
        self.assertIn("SLA: availability · unacceptable · supplied assessment", page)
        self.assertIn('<table class="evidence-table">', page)
        self.assertIn('scope="row">Evaluation method</th><td>Supplied assessment</td>', page)
        self.assertNotIn('"evaluation":', page)
        self.assertNotIn("<script>", page)
        self.assertNotIn("unrelated", page)

        map_report.write_text(json.dumps({**map_payload, "scope": {"rows": ["CAP-1"]}}))
        view = json.loads(self.cli(source, "--json", *args).stdout)
        self.assertEqual(view["evidenceSources"]["capabilityScope"], ["CAP-1"])
        map_report.write_text(json.dumps({
            **map_payload, "scope": {"rows": ["CAP-2"]},
            "rows": [{**entry, "id": "CAP-2"}],
        }))
        view = json.loads(self.cli(source, "--json", *args).stdout)
        self.assertEqual(view["rows"][0]["evidence"], {"status": "outside-scope"})
        map_report.write_text(json.dumps({**map_payload, "scope": {"rows": ["CAP-2"]}}))
        result = self.cli(source, "--json", *args, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"scope does not match", result.stderr)
        map_report.write_text(json.dumps(map_payload))

        scenario = {**entry["scenarios"][0], "evidence": {"status": "missing-citation", "citations": []}}
        map_report.write_text(json.dumps({**map_payload, "rows": [{**entry, "scenarios": [scenario]}]}))
        view = json.loads(self.cli(source, "--json", *args).stdout)
        proof = view["rows"][0]["evidence"]
        self.assertEqual(proof["computedRowStatus"], "lane-green")
        self.assertEqual(proof["scenarioEvidenceStatus"], "missing-citation")
        self.assertEqual(proof["testCitations"], [])

        for change, expected in (({"doc": "other.md"}, "doc-mismatch"),
                                 ({"doc": "."}, "doc-mismatch"),
                                 ({"doc": "./"}, "doc-mismatch"),
                                 ({"scenarios": [{"then": "old", "altitude": altitude}]}, "scenario-mismatch")):
            with self.subTest(change=change):
                map_report.write_text(json.dumps({**map_payload, "rows": [{**entry, **change}]}))
                view = json.loads(self.cli(source, "--json", *args).stdout)
                self.assertEqual(view["rows"][0]["evidence"], {"status": expected})

        map_report.write_text(json.dumps({**map_payload, "rows": [{**entry, "doc": None}]}))
        view = json.loads(self.cli(source, "--json", *args).stdout)
        self.assertFalse(view["rows"][0]["evidence"]["mapDocumentRecorded"])

        map_report.write_text(json.dumps({**map_payload, "mapDigest": "b" * 64}))
        result = self.cli(source, "--json", *args, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"same map snapshot", result.stderr)

    def test_rejects_a_service_report_without_a_map_report(self):
        report = self.folder / "service.json"
        report.write_text('{"mode": "policy-validation", "policies": 0}')
        result = self.cli(EXAMPLE, "--json", "--service-report", report, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"needs --map-report", result.stderr)

    def test_report_generators_identify_the_same_map_snapshot(self):
        map_file = self.folder / "map.json"
        map_file.write_text('{"rows": []}', encoding="utf-8")
        exports = []
        for script in ("map_report.py", "service_report.py"):
            result = subprocess.run(
                [sys.executable, str(SCRIPT.with_name(script)), "--map", str(map_file), "--json"],
                capture_output=True,
                check=True,
            )
            exports.append(json.loads(result.stdout)["mapDigest"])
        self.assertRegex(exports[0], r"^[0-9a-f]{64}$")
        self.assertEqual(exports[0], exports[1])
