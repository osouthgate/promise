"""Tests for map_report.py: the capability map joined to a JUnit test run.

Run from the repo root:

    python3 -m unittest discover -s tests -v

The example under examples/proofmap/ has one row per outcome the report can
show; the unit tests below build small maps and runs to pin each rule.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parent
REPORT = REPO / "skills" / "promise" / "scripts" / "map_report.py"
EXAMPLE = REPO / "examples" / "proofmap"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(REPORT), *args], capture_output=True, text=True)


def row(rid="CAP-1", altitude="data", verdict="not-built", **lanes):
    base = {"tests": [], "e2eTests": [], "evalTests": [], "siblingTests": []}
    base.update(lanes)
    return {"id": rid, "story": f"story {rid}", "doc": None, "verdict": verdict,
            "scenarios": [{"id": rid + ".1", "then": "then", "altitude": altitude}], **base}


def junit(*cases: str, file: str = "t/a.test.ts") -> str:
    body = "".join(cases)
    return f'<testsuites><testsuite name="s" file="{file}">{body}</testsuite></testsuites>'


def case(name, outcome="pass", classname="t/a.test.ts"):
    inner = {"pass": "", "fail": "<failure message='x'/>", "error": "<error/>", "skip": "<skipped/>"}[outcome]
    return f'<testcase classname="{classname}" name="{name}">{inner}</testcase>'


class Harness(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def report(self, rows, xml=None, *extra):
        map_path = self.dir / "map.json"
        map_path.write_text(json.dumps({"version": 1, "rows": rows}), encoding="utf-8")
        args = ["--map", str(map_path), "--json", *extra]
        if xml is not None:
            xml_path = self.dir / "run.xml"
            xml_path.write_text(xml, encoding="utf-8")
            args += ["--junit", str(xml_path)]
        result = run(*args)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return json.loads(result.stdout)

    def one(self, rows, xml=None, *extra):
        return self.report(rows, xml, *extra)["rows"][0]

    def report_files(self, data, runs, *extra):
        """The report over a map (``data``) and a folder of run files
        (``runs``: name -> XML), and its exit code."""
        map_path = self.dir / "map.json"
        map_path.write_text(json.dumps(data), encoding="utf-8")
        folder = self.dir / "run"
        folder.mkdir(exist_ok=True)
        for name, text in runs.items():
            (folder / name).write_text(text, encoding="utf-8")
        result = run("--map", str(map_path), "--junit", str(folder), "--json", *extra)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return result.returncode, json.loads(result.stdout)


class Buckets(Harness):
    def test_selected_pilot_keeps_run_gaps_and_changes_its_fingerprint(self):
        rows = [
            row("CAP-1", tests=["t/a.test.ts::works"]),
            row("CAP-2", tests=["t/a.test.ts::other"]),
        ]
        xml = junit(case("works"))
        full = self.report(rows, xml)
        scoped = self.report(rows, xml, "--row", "CAP-1", "--strict")
        self.assertEqual([r["id"] for r in scoped["rows"]], ["CAP-1"])
        self.assertEqual(scoped["scope"]["rows"], ["CAP-1"])
        self.assertEqual(scoped["mapDigest"], full["mapDigest"])
        self.assertNotEqual(scoped["summary"]["fingerprint"], full["summary"]["fingerprint"])
        scoped = self.report(rows, junit(case("works"), case("unhomed")),
                             "--row", "CAP-1", "--orphans", "--fail-on-orphans")
        self.assertEqual(scoped["summary"]["orphanCount"], 1)
        result = run("--map", str(self.dir / "map.json"), "--row", "CAP-999", "--json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown capability", result.stderr)

    def test_pilot_left_out_checks_use_the_supplied_run(self):
        data = {"rows": [row(tests=["t/a.test.ts::works"])],
                "leftOut": [
                    {"test": "t/a.test.ts::helper", "reason": "Helper only", "date": "2026-11-13"},
                    {"test": "outside.ts::outside", "reason": "Other area", "date": "2026-11-13"},
                ]}
        code, report = self.report_files(data, {"pilot.xml": junit(case("works"), case("helper"))},
                                         "--row", "CAP-1", "--fail-on-orphans")
        self.assertEqual(code, 0)
        self.assertEqual(len(report["leftOut"]), 1)
        self.assertEqual(report["leftOut"][0]["test"], "t/a.test.ts::helper")
        self.assertEqual(report["summary"]["leftOutOutOfScopeCount"], 1)

    def test_pilot_keeps_malformed_exclusions_even_outside_the_run(self):
        for entry in (
            {"test": {"file": "outside.ts", "name": "x"}, "reason": "Other", "date": "2026-11-13"},
            {"test": "outside.ts::x", "date": "2026-11-13"},
            {"test": "outside.ts::x", "reason": "Other", "date": "2026-02-30"},
            {"test": "outside.ts::<placeholder>", "reason": "Other", "date": "2026-11-13"},
        ):
            with self.subTest(entry=entry):
                data = {"rows": [row(tests=["t/a.test.ts::works"])], "leftOut": [entry]}
                code, report = self.report_files(
                    data, {"pilot.xml": junit(case("works"))},
                    "--row", "CAP-1", "--fail-on-orphans")
                self.assertEqual(code, 1)
                self.assertEqual(report["summary"]["leftOutOutOfScopeCount"], 0)
                self.assertEqual(report["summary"]["leftOutProblemCount"], 1)

    def test_pilot_absent_lane_counts_only_unchecked_valid_citations(self):
        rows = [row(tests=["t/a.test.ts::works"],
                    e2eTests=["e2e/outside.ts::outside", "e2e/outside.ts::<placeholder>"])]
        report = self.report(rows, junit(case("works")), "--row", "CAP-1")
        self.assertEqual(report["summary"]["lanesNotInRun"],
                         [{"lane": "e2eTests", "citations": 1}])

    def test_pilot_uses_shared_coverage_without_gating_unrun_supporting_citations(self):
        rows = [
            row("CAP-1", tests=["t/a.test.ts::refund"], surfaces=["/refund"]),
            row("CAP-9", tests=["t/a.test.ts::callback", "t/a.test.ts::unrelated"],
                surfaces=["/callback", "/unrelated"]),
            row("CAP-10", altitude="perception", e2eTests=["e2e/outside.ts::outside"]),
        ]
        surfaces = self.dir / "surfaces.txt"
        surfaces.write_text("/refund\n/callback\n")
        data = {"rows": rows, "leftOut": []}
        code, report = self.report_files(
            data, {"pilot.xml": junit(case("refund"), case("callback"))},
            "--row", "CAP-1", "--strict", "--fail-on-orphans",
            "--surfaces", str(surfaces), "--fail-on-unmapped")
        self.assertEqual(code, 0)
        self.assertEqual(report["summary"]["orphanCount"], 0)
        self.assertEqual(report["summary"]["unmappedSurfaceCount"], 0)
        self.assertEqual(report["scope"]["supportingRows"], ["CAP-9"])
        self.assertEqual(report["summary"]["lanesNotInRun"], [])
        self.assertEqual([r["id"] for r in report["rows"]], ["CAP-1"])
        code, report = self.report_files(
            data, {"pilot.xml": junit(case("refund"), case("callback", "fail"))},
            "--row", "CAP-1", "--strict", "--fail-on-orphans")
        self.assertEqual(code, 1)
        self.assertEqual(report["summary"]["run"]["failing"], 1)
        code, report = self.report_files(
            data, {"pilot.xml": junit(case("refund"), case("callback", "skip"))},
            "--row", "CAP-1", "--fail-on-skipped")
        self.assertEqual(code, 1)
        self.assertEqual(report["skippedCitations"][0]["id"], "CAP-9")
        data["leftOut"] = [{"test": "t/a.test.ts::callback", "reason": "Helper", "date": "2026-11-13"}]
        code, report = self.report_files(
            data, {"pilot.xml": junit(case("refund"), case("callback"))},
            "--row", "CAP-1", "--fail-on-orphans")
        self.assertEqual(code, 1)
        self.assertIn("also cited by CAP-9", report["leftOut"][0]["problem"])

    def test_pilot_keeps_a_stale_left_out_note_for_a_file_in_the_run(self):
        data = {"rows": [row(tests=["t/a.test.ts::works"])],
                "leftOut": [{"test": "t/a.test.ts::deleted", "reason": "Helper", "date": "2026-11-13"}]}
        code, report = self.report_files(data, {"pilot.xml": junit(case("works"))},
                                         "--row", "CAP-1", "--fail-on-orphans")
        self.assertEqual(code, 1)
        self.assertEqual(report["summary"]["staleLeftOutCount"], 1)
    def test_passing_citation_in_its_own_lane_is_proven(self):
        r = self.one([row(tests=["t/a.test.ts::works"])], junit(case("works")))
        self.assertEqual((r["bucket"], r["computed"]), ("passing", "proven"))

    def test_failing_error_and_skipped(self):
        for outcome, bucket in (("fail", "failing"), ("error", "failing"), ("skip", "skipped")):
            with self.subTest(outcome=outcome):
                r = self.one([row(tests=["t/a.test.ts::works"])], junit(case("works", outcome)))
                self.assertEqual(r["bucket"], bucket)
                self.assertEqual(r["computed"], "not-built")

    def test_never_ran_when_no_case_matches(self):
        r = self.one([row(tests=["t/a.test.ts::renamed"])], junit(case("works")))
        self.assertEqual(r["bucket"], "never-ran")
        self.assertEqual(r["citations"][0]["matches"], 0)

    def test_no_test_when_nothing_is_cited(self):
        r = self.one([row()], junit(case("works")))
        self.assertEqual((r["bucket"], r["computed"]), ("no-test", "not-built"))

    def test_placeholder_and_empty_names_are_bad_citations(self):
        for cite in ("t/a.test.ts::<test name>", "<file>::works", "t/a.test.ts::"):
            with self.subTest(cite=cite):
                r = self.one([row(tests=[cite])], junit(case("works")))
                self.assertEqual(r["bucket"], "bad-citation")

    def test_worst_citation_sets_the_bucket(self):
        r = self.one([row(tests=["t/a.test.ts::a", "t/a.test.ts::b"])], junit(case("a"), case("b", "fail")))
        self.assertEqual(r["bucket"], "failing")

    def test_duplicate_matches_take_the_worst_result(self):
        xml = junit(case("same"), case("same", "fail"))
        r = self.one([row(tests=["t/a.test.ts::same"])], xml)
        self.assertEqual(r["citations"][0]["matches"], 2)
        self.assertEqual(r["bucket"], "failing")


class Matching(Harness):
    def test_file_must_match_when_the_run_records_one(self):
        r = self.one([row(tests=["t/other.test.ts::works"])], junit(case("works")))
        self.assertEqual(r["bucket"], "never-ran")

    def test_describe_path_title_matches(self):
        xml = junit(case("works", classname="Mute > per member"))
        for cite in ("t/a.test.ts::Mute > per member > works", "t/a.test.ts::works"):
            with self.subTest(cite=cite):
                self.assertEqual(self.one([row(tests=[cite])], xml)["bucket"], "passing")

    def test_pytest_dotted_classname_matches_the_file(self):
        xml = ('<testsuites><testsuite name="pytest">'
               '<testcase classname="tests.test_mute.TestMute" name="test_stores"/></testsuite></testsuites>')
        for cite in ("tests/test_mute.py::test_stores", "tests/test_mute.py::TestMute::test_stores"):
            with self.subTest(cite=cite):
                self.assertEqual(self.one([row(tests=[cite])], xml)["bucket"], "passing")
        self.assertEqual(self.one([row(tests=["tests/test_other.py::test_stores"])], xml)["bucket"], "never-ran")

    def test_a_case_without_any_file_matches_on_name(self):
        xml = '<testsuites><testsuite name="x"><testcase classname="Mute" name="works"/></testsuite></testsuites>'
        self.assertEqual(self.one([row(tests=["any/file.ts::works"])], xml)["bucket"], "passing")

    def test_dict_citations_are_accepted(self):
        r = self.one([row(tests=[{"file": "t/a.test.ts", "name": "works"}])], junit(case("works")))
        self.assertEqual(r["bucket"], "passing")


class LessonsFromARealMap(Harness):
    def test_citing_a_describe_covers_every_case_under_it(self):
        xml = junit(case("Mute > stores it"), case("Mute > clears it", "fail"), case("Other > x"))
        r = self.one([row(tests=["t/a.test.ts::Mute"])], xml)
        self.assertEqual(r["citations"][0]["matches"], 2)
        self.assertEqual(r["bucket"], "failing")
        self.assertEqual(self.one([row(tests=["t/a.test.ts::Mut"])], xml)["bucket"], "never-ran")

    def test_parametrised_names_match_any_value(self):
        xml = junit(case("exports 3 rows as csv"), case("exports 10 rows as csv"))
        for cite in ("t/a.test.ts::exports %d rows as csv", "t/a.test.ts::exports ${n} rows as csv",
                     "t/a.test.ts::exports $n rows as csv"):
            with self.subTest(cite=cite):
                r = self.one([row(tests=[cite])], xml)
                self.assertEqual((r["bucket"], r["citations"][0]["matches"]), ("passing", 2))

    def test_a_parametrised_name_with_too_little_text_is_a_bad_citation(self):
        for cite in ("t/a.test.ts::%s", "t/a.test.ts::$a $b", "t/a.test.ts::%s ok"):
            with self.subTest(cite=cite):
                self.assertEqual(self.one([row(tests=[cite])], junit(case("x ok")))["bucket"], "bad-citation")

    def test_an_empty_run_is_refused(self):
        map_path = self.dir / "map.json"
        map_path.write_text(json.dumps({"rows": [row()]}), encoding="utf-8")
        xml = self.dir / "empty.xml"
        xml.write_text("<testsuites></testsuites>", encoding="utf-8")
        result = run("--map", str(map_path), "--junit", str(xml))
        self.assertEqual(result.returncode, 2)
        self.assertIn("no test cases", result.stderr)

    def test_must_rows_lead_the_summary(self):
        rows = [dict(row("CAP-1", tests=["t/a.test.ts::works"]), priority="must"),
                dict(row("CAP-2"), priority="must"), dict(row("CAP-3"), priority="should")]
        summary = self.report(rows, junit(case("works")))["summary"]
        self.assertEqual((summary["must"], summary["mustNotProven"]), (2, 1))

    def test_run_totals_and_fingerprint_are_recorded(self):
        data = self.report([row(tests=["t/a.test.ts::works"])], junit(case("works"), case("other", "fail")))
        self.assertEqual({k: data["summary"]["run"][k] for k in ("cases", "passing", "failing")},
                         {"cases": 2, "passing": 1, "failing": 1})
        self.assertRegex(data["summary"]["fingerprint"], r"^sha256:[0-9a-f]{16}$")
        again = self.report([row(tests=["t/a.test.ts::works"])], junit(case("works"), case("other", "fail")))
        self.assertEqual(again["summary"]["fingerprint"], data["summary"]["fingerprint"])


class ReviewRegressions(Harness):
    """One test per finding of the adversarial review: each reproduced a false result."""

    def test_a_red_citation_in_the_proving_lane_blocks_proven(self):
        xml = junit(case("a"), case("b", "fail"))
        r = self.one([row(verdict="proven", tests=["t/a.test.ts::a", "t/a.test.ts::b"])], xml)
        self.assertEqual((r["bucket"], r["computed"], r["finding"]), ("failing", "under-proven", "optimistic"))
        for second, bucket in (("t/a.test.ts::gone", "never-ran"), ("t/a.test.ts::", "bad-citation")):
            with self.subTest(second=second):
                r = self.one([row(verdict="proven", tests=["t/a.test.ts::a", second])], junit(case("a")))
                self.assertEqual((r["bucket"], r["computed"]), (bucket, "under-proven"))

    def test_strict_fails_on_never_ran_and_bad_citation(self):
        for cite in ("t/a.test.ts::gone", "t/a.test.ts::<test name>"):
            with self.subTest(cite=cite):
                m = self.dir / "m.json"
                m.write_text(json.dumps({"rows": [row(tests=[cite])]}), encoding="utf-8")
                x = self.dir / "x.xml"
                x.write_text(junit(case("works")), encoding="utf-8")
                self.assertEqual(run("--map", str(m), "--junit", str(x), "--strict").returncode, 1)

    def test_sibling_citations_are_validated_and_prove_only_sibling_scenarios(self):
        for cite in ("<repo>::<test>", "", None, 3):
            with self.subTest(cite=cite):
                r = self.one([row(altitude="sibling", siblingTests=[cite])], junit(case("x")))
                self.assertEqual(r["bucket"], "bad-citation")
                self.assertEqual(r["computed"], "not-built")
        r = self.one([row(altitude="data", siblingTests=["other::t"])], junit(case("x")))
        self.assertEqual(r["computed"], "not-built")

    def test_a_config_that_shares_the_sibling_array_is_refused(self):
        config = self.dir / "c.json"
        config.write_text(json.dumps({"map": {"lanes": {"sibling": "tests[]"}}}), encoding="utf-8")
        m = self.dir / "m.json"
        m.write_text(json.dumps({"rows": [row(tests=["t/a.test.ts::a"])]}), encoding="utf-8")
        x = self.dir / "x.xml"
        x.write_text(junit(case("a", "fail")), encoding="utf-8")
        result = run("--map", str(m), "--junit", str(x), "--config", str(config))
        self.assertEqual(result.returncode, 2)
        self.assertIn("sibling", result.stderr)

    def test_default_reporter_titles_match_a_leaf_citation(self):
        jest = '<testsuites><testsuite name="jest tests"><testcase classname="Mute stores it" name="Mute stores it"/></testsuite></testsuites>'
        vitest = junit(case("Mute > stores it", classname="t/a.test.ts"))
        playwright = junit(case("Mute › no badge", classname="a.spec.ts"), file="t/a.test.ts")
        for xml, cite in ((jest, "t/a.test.ts::stores it"), (vitest, "t/a.test.ts::stores it"),
                          (playwright, "t/a.test.ts::no badge")):
            with self.subTest(cite=cite):
                self.assertEqual(self.one([row(tests=[cite])], xml)["bucket"], "passing")

    def test_an_exact_title_wins_over_a_leaf_collision(self):
        xml = junit(case("stores it"), case("Other > stores it", "fail"))
        r = self.one([row(tests=["t/a.test.ts::stores it"])], xml)
        self.assertEqual((r["bucket"], r["citations"][0]["matches"]), ("passing", 1))

    def test_pytest_parametrised_ids_match_the_base_name(self):
        xml = ('<testsuites><testsuite name="pytest">'
               '<testcase classname="tests.test_x" name="test_a[1-b]"/>'
               '<testcase classname="tests.test_x" name="test_a[2-c]"><failure/></testcase>'
               '</testsuite></testsuites>')
        r = self.one([row(tests=["tests/test_x.py::test_a"])], xml)
        self.assertEqual((r["bucket"], r["citations"][0]["matches"]), ("failing", 2))

    def test_a_root_level_js_file_is_not_a_dotted_module(self):
        xml = '<testsuites><testsuite name="x"><testcase classname="example.spec.ts" name="has title"/></testsuite></testsuites>'
        self.assertEqual(self.one([row(tests=["example.spec.ts::has title"])], xml)["bucket"], "passing")

    def test_the_suite_name_is_a_file_when_it_is_a_path(self):
        xml = '<testsuites><testsuite name="tests/e2e/a.test.ts"><testcase classname="x" name="works"><failure/></testcase></testsuite>' \
              '<testsuite name="tests/unit/a.test.ts"><testcase classname="x" name="works"/></testsuite></testsuites>'
        r = self.one([row(tests=["tests/unit/a.test.ts::works"])], xml)
        self.assertEqual((r["bucket"], r["citations"][0]["matches"]), ("passing", 1))

    def test_an_outer_suites_file_attribute_wins_over_an_inner_suite_named_like_a_path(self):
        xml = ('<testsuites><testsuite name="Root Suite" file="tests/api.test.js">'
               '<testsuite name="v1/users"><testcase classname="c" name="lists users"/></testsuite>'
               '<testsuite name="café › menu"><testcase classname="c" name="shows menu"/></testsuite>'
               '</testsuite></testsuites>')
        data = self.report([row(tests=["tests/api.test.js::lists users", "tests/api.test.js::shows menu"])], xml)
        self.assertEqual([c["status"] for c in data["rows"][0]["citations"]], ["passing", "passing"])
        self.assertEqual(data["orphans"], [])
        nested = ('<testsuites><testsuite name="tests/a.test.ts"><testsuite name="v1/users">'
                  '<testcase classname="c" name="works"/></testsuite></testsuite></testsuites>')
        self.assertEqual(self.one([row(tests=["tests/a.test.ts::works"])], nested)["bucket"], "passing")
        inner = ('<testsuites><testsuite name="all" file="tests/a.test.ts"><testsuite name="x" file="tests/b.test.ts">'
                 '<testcase classname="c" name="works"/></testsuite></testsuite></testsuites>')
        self.assertEqual(self.one([row(tests=["tests/b.test.ts::works"])], inner)["bucket"], "passing")

    def test_a_directory_is_not_a_file_citation(self):
        self.assertEqual(self.one([row(tests=["t::works"])], junit(case("works")))["bucket"], "never-ran")

    def test_status_attributes_are_honoured(self):
        for attrs, bucket in (('status="notrun"', "skipped"), ('result="suppressed"', "skipped"),
                              ('skipped="true"', "skipped"), ('status="failed"', "failing")):
            with self.subTest(attrs=attrs):
                xml = f'<testsuites><testsuite name="s" file="t/a.test.ts"><testcase classname="c" name="w" {attrs}/></testsuite></testsuites>'
                self.assertEqual(self.one([row(tests=["t/a.test.ts::w"])], xml)["bucket"], bucket)

    def test_jsx_in_a_name_is_not_a_placeholder(self):
        xml = junit(case("renders &lt;Button /&gt;"))
        self.assertEqual(self.one([row(tests=["t/a.test.ts::renders <Button />"])], xml)["bucket"], "passing")

    def test_a_real_test_name_with_an_html_tag_can_be_cited_and_homed(self):
        name = "isSafeConnectionLink > rejects data:text/html,<script>alert(1)</script>"
        xml = ('<testsuites><testsuite name="tests/g.test.ts"><testcase classname="tests/g.test.ts" '
               'name="isSafeConnectionLink &gt; rejects data:text/html,&lt;script&gt;alert(1)&lt;/script&gt;"/>'
               '</testsuite></testsuites>')
        code, out = self.report_files({"rows": [row(tests=[f"apps/api/tests/g.test.ts::{name}"])]},
                                      {"a.xml": xml}, "--fail-on-orphans")
        self.assertEqual(out["rows"][0]["citations"][0]["status"], "passing")
        self.assertEqual((out["summary"]["orphanCount"], code), (0, 0))
        left = {"test": f"tests/g.test.ts::{name}", "reason": "a guard's own test", "date": "2026-01-01"}
        code, out = self.report_files({"rows": [row()], "leftOut": [left]}, {"a.xml": xml}, "--fail-on-orphans")
        self.assertEqual((out["leftOut"][0]["status"], out["summary"]["orphanCount"], code), ("passing", 0, 0))

    def test_a_placeholder_that_matches_nothing_exactly_is_still_a_bad_citation(self):
        xml = junit(case("works"), case("Other &gt; &lt;test name&gt;"))
        for cite in ("t/a.test.ts::<test name>", "t/a.test.ts::wor<k>s"):
            with self.subTest(cite=cite):
                self.assertEqual(self.one([row(tests=[cite])], xml)["bucket"], "bad-citation")
        no_file = '<testsuites><testsuite name="x"><testcase classname="Mute" name="works"/></testsuite></testsuites>'
        self.assertEqual(self.one([row(tests=["<file>::works"])], no_file)["bucket"], "bad-citation")

    def test_each_empty_run_file_is_refused_and_namespaces_are_read(self):
        m = self.dir / "m.json"
        m.write_text(json.dumps({"rows": [row(tests=["t/a.test.ts::works"])]}), encoding="utf-8")
        d = self.dir / "run"
        d.mkdir()
        (d / "a.xml").write_text(junit(case("works")), encoding="utf-8")
        (d / "b.xml").write_text("<testsuites/>", encoding="utf-8")
        result = run("--map", str(m), "--junit", str(d))
        self.assertEqual(result.returncode, 2)
        self.assertIn("b.xml", result.stderr)
        ns = self.dir / "ns.xml"
        ns.write_text('<testsuites xmlns="urn:x"><testsuite name="s" file="t/a.test.ts"><testcase classname="c" name="works"/></testsuite></testsuites>', encoding="utf-8")
        self.assertEqual(json.loads(run("--map", str(m), "--junit", str(ns), "--json").stdout)["rows"][0]["bucket"], "passing")

    def test_unknown_recorded_verdict_is_a_finding(self):
        r = self.one([row(verdict="PROVEN", tests=["t/a.test.ts::works"])], junit(case("works")))
        self.assertEqual(r["finding"], "unknown-verdict")

    def test_a_non_list_lane_is_still_read(self):
        rr = row()
        rr["tests"] = "t/a.test.ts::works"
        self.assertEqual(self.one([rr], junit(case("works")))["bucket"], "passing")

    def test_a_large_run_is_fast(self):
        import time
        cases = "".join(case(f"test {i}") for i in range(20000))
        rows = [row(f"CAP-{i}", tests=[f"t/a.test.ts::test {i * 7}"]) for i in range(2000)]
        start = time.time()
        data = self.report(rows, junit(cases))
        self.assertLess(time.time() - start, 30)
        self.assertEqual(data["summary"]["buckets"]["passing"], 2000)


class LaneNotInRun(Harness):
    """A suite the run left out (the e2e suite, written by its own command)
    is not a stale citation: when no citation of a lane matches a case and
    no file they cite is in the run, the lane's citations read not-run."""

    def rows(self, verdict="under-proven"):
        both = row("CAP-1", verdict=verdict, tests=["t/a.test.ts::works"], e2eTests=["e2e/a.spec.ts::shows it"])
        both["scenarios"].append({"id": "CAP-1.2", "then": "seen", "altitude": "perception"})
        return [both, row("CAP-2", altitude="perception", e2eTests=["e2e/b.spec.ts::other"])]

    def e2e(self, *cases_by_file):
        suites = "".join(f'<testsuite name="{f}">' + case(n, classname=f) + "</testsuite>" for f, n in cases_by_file)
        return "<testsuites>" + suites + "</testsuites>"

    def test_a_lane_whose_suite_is_not_in_the_run_is_not_run(self):
        code, out = self.report_files({"rows": self.rows()}, {"unit.xml": junit(case("works"))}, "--strict")
        self.assertEqual(code, 0)
        self.assertEqual([c["status"] for r in out["rows"] for c in r["citations"]], ["passing", "not-run", "not-run"])
        self.assertEqual([(r["bucket"], r["computed"]) for r in out["rows"]],
                         [("not-run", "under-proven"), ("not-run", "not-built")])
        self.assertEqual(out["summary"]["lanesNotInRun"], [{"lane": "e2eTests", "citations": 2}])
        m = str(self.dir / "map.json")
        tree = run("--map", m, "--junit", str(self.dir / "run")).stdout
        self.assertIn("e2eTests was not in this run (2 citations not checked)", tree)
        self.assertNotIn("never ran", tree)

    def test_once_the_suite_ran_a_citation_that_matches_nothing_never_ran(self):
        runs = {"unit.xml": junit(case("works")), "e2e.xml": self.e2e(("e2e/a.spec.ts", "shows it"))}
        code, out = self.report_files({"rows": self.rows()}, runs, "--strict")
        self.assertEqual(code, 1)
        self.assertEqual([r["bucket"] for r in out["rows"]], ["passing", "never-ran"])
        self.assertEqual(out["summary"]["lanesNotInRun"], [])

    def test_a_lane_whose_cited_files_ran_but_whose_tests_were_renamed_never_ran(self):
        runs = {"unit.xml": junit(case("works")),
                "e2e.xml": self.e2e(("e2e/a.spec.ts", "shows it again"), ("e2e/b.spec.ts", "another"))}
        code, out = self.report_files({"rows": self.rows()}, runs, "--strict")
        self.assertEqual(code, 1)
        self.assertEqual([c["status"] for r in out["rows"] for c in r["citations"]], ["passing", "never-ran", "never-ran"])

    def test_a_lane_whose_cited_files_were_all_deleted_never_ran_when_its_suite_ran(self):
        # the e2e run holds other specs in the cited folder, and no cited spec
        # exists any more: the suite ran, so the citations are stale
        runs = {"unit.xml": junit(case("works")), "e2e.xml": self.e2e(("e2e/c.spec.ts", "a newer spec"))}
        code, out = self.report_files({"rows": self.rows()}, runs, "--strict")
        self.assertEqual(code, 1)
        self.assertEqual([c["status"] for r in out["rows"] for c in r["citations"]], ["passing", "never-ran", "never-ran"])
        self.assertEqual(out["summary"]["lanesNotInRun"], [])

    def test_a_run_file_named_after_the_cited_folder_ran_when_it_records_paths_from_there(self):
        # Playwright records the spec from its own testDir: "c.spec.ts", not "e2e/tests/c.spec.ts"
        data = {"rows": [row("CAP-1", altitude="perception", e2eTests=["e2e/tests/a.spec.ts::shows it"])]}
        for recorded in ("c.spec.ts", "tests/c.spec.ts"):
            with self.subTest(recorded=recorded):
                code, out = self.report_files(data, {"e2e.xml": self.e2e((recorded, "a newer spec"))}, "--strict")
                self.assertEqual((code, out["rows"][0]["bucket"], out["summary"]["lanesNotInRun"]), (1, "never-ran", []))

    def test_a_unit_run_that_records_paths_from_a_package_root_leaves_the_e2e_lane_not_run(self):
        # api.xml records "tests/x.test.ts" for apps/api/tests/x.test.ts; e2e/tests is another folder
        data = {"rows": [row("CAP-1", tests=["apps/api/tests/x.test.ts::works"]),
                         row("CAP-2", altitude="perception", e2eTests=["e2e/tests/a.spec.ts::shows it"])]}
        api = junit(case("works", classname="tests/x.test.ts"), file="tests/x.test.ts")
        code, out = self.report_files(data, {"api.xml": api}, "--strict")
        self.assertEqual(code, 0)
        self.assertEqual(out["summary"]["lanesNotInRun"], [{"lane": "e2eTests", "citations": 1}])

    def only(self, name, recorded, *extra):
        """The report over deleted_specs() and one run file, alone in its folder."""
        for old in (self.dir / "run").glob("*.xml"):
            old.unlink()
        return self.report_files(self.deleted_specs(), {name: self.e2e((recorded, "a newer spec"))}, *extra)

    def deleted_specs(self):
        """Two rows that cite e2e/tests specs; the run holds none of them."""
        return {"rows": [row("CAP-1", altitude="perception", e2eTests=["e2e/tests/a.spec.ts::shows it"]),
                         row("CAP-2", altitude="perception", e2eTests=["e2e/tests/b.spec.ts::other"])]}

    def test_a_case_in_a_subfolder_of_a_cited_folder_ran(self):
        # the N1 repro: the cited specs were deleted, and the suite now runs
        # only in a subfolder; from the project root, any run file shows it
        for name in ("e2e.xml", "results.xml"):
            with self.subTest(run_file=name):
                code, out = self.only(name, "e2e/tests/admin/new.spec.ts", "--strict")
                self.assertEqual((code, out["summary"]["lanesNotInRun"]), (1, []))
                self.assertEqual([r["bucket"] for r in out["rows"]], ["never-ran", "never-ran"])

    def test_a_run_file_named_after_the_lane_places_a_subfolder_or_a_sibling_folder(self):
        # admin/new.spec.ts and tests/admin/new.spec.ts: Playwright's paths from
        # its testDir; e2e/smoke/new.spec.ts: a sibling folder under e2e/
        for recorded in ("admin/new.spec.ts", "tests/admin/new.spec.ts", "e2e/smoke/new.spec.ts"):
            with self.subTest(recorded=recorded):
                code, out = self.only("e2e.xml", recorded, "--strict")
                self.assertEqual((code, out["summary"]["lanesNotInRun"]), (1, []))

    def test_a_run_file_named_after_no_folder_of_the_lane_cannot_place_it(self):
        # the limit: with no run-file name to go on, a relative path or a
        # sibling folder is not read as this lane's suite
        for recorded in ("admin/new.spec.ts", "e2e/smoke/new.spec.ts"):
            with self.subTest(recorded=recorded):
                _code, out = self.only("results.xml", recorded)
                self.assertEqual(out["summary"]["lanesNotInRun"], [{"lane": "e2eTests", "citations": 2}])

    def test_a_unit_run_named_after_a_folder_of_the_lane_that_records_from_above_it_is_not_the_lane(self):
        # tests.xml records tests/x.test.ts from the project root: the unit
        # suite, not e2e/tests; read from e2e/tests it would be a subfolder
        _code, out = self.report_files(self.deleted_specs(),
                                       {"tests.xml": junit(case("works", classname="tests/x.test.ts"),
                                                           file="tests/x.test.ts")})
        self.assertEqual(out["summary"]["lanesNotInRun"], [{"lane": "e2eTests", "citations": 2}])

    def test_with_the_cited_folder_on_disk_a_case_read_into_it_must_be_there_too(self):
        # a package's bot.xml records tests/harness.test.ts from its package;
        # a lane that cites evals/bot/evals/ must not read it as its suite
        data = {"rows": [row("CAP-1", evalTests=["evals/bot/evals/refusal.eval.ts::refuses"])]}
        (self.dir / "map.json").write_text(json.dumps(data), encoding="utf-8")
        (self.dir / "run").mkdir(exist_ok=True)
        (self.dir / "run" / "bot.xml").write_text(
            junit(case("works", classname="tests/harness.test.ts"), file="tests/harness.test.ts"), encoding="utf-8")
        (self.dir / "evals" / "bot" / "evals").mkdir(parents=True)

        def report():
            result = subprocess.run([sys.executable, str(REPORT), "--map", "map.json", "--junit", "run",
                                     "--json", "--strict"], capture_output=True, text=True, cwd=self.dir)
            return result.returncode, json.loads(result.stdout)["summary"]["lanesNotInRun"]

        self.assertEqual(report(), (0, [{"lane": "evalTests", "citations": 1}]))
        # the same path on disk under the cited folder: the suite ran
        (self.dir / "evals" / "bot" / "evals" / "tests").mkdir()
        (self.dir / "evals" / "bot" / "evals" / "tests" / "harness.test.ts").write_text("", encoding="utf-8")
        self.assertEqual(report(), (1, []))

    def test_a_lane_that_cites_a_test_in_the_run_under_the_wrong_file_never_ran(self):
        data = {"rows": [row("CAP-1", altitude="perception", e2eTests=["e2e/a.spec.ts::works"])]}
        code, out = self.report_files(data, {"unit.xml": junit(case("works"))}, "--strict")
        self.assertEqual((code, out["rows"][0]["bucket"], out["summary"]["lanesNotInRun"]), (1, "never-ran", []))

    def test_a_run_that_records_no_file_ran_when_it_holds_the_cited_test_s_own_title(self):
        # node:test's own reporter: no file, classname "test", and the describe
        # title only on the enclosing suite
        xml = ('<testsuites><testsuite name="invoices"><testcase classname="test" name="totals add up"/>'
               '</testsuite></testsuites>')
        data = {"rows": [row("CAP-1", tests=["tests/a/x.test.mjs::invoices > totals add up"])]}
        code, out = self.report_files(data, {"node.xml": xml}, "--strict")
        self.assertEqual((code, out["rows"][0]["bucket"], out["summary"]["lanesNotInRun"]), (1, "never-ran", []))

    def test_a_row_recorded_higher_than_its_missing_proof_still_fails_strict(self):
        code, out = self.report_files({"rows": self.rows(verdict="proven")}, {"unit.xml": junit(case("works"))},
                                      "--strict")
        self.assertEqual((code, out["rows"][0]["finding"]), (1, "optimistic"))


class SkippedCitations(Harness):
    """A skipped test proves nothing. --strict fails only on a verdict
    recorded higher than the run shows, so a row recorded under-proven
    passes with one cited test skipped; --fail-on-skipped does not."""

    def data(self):
        rr = row("CAP-1", verdict="under-proven", tests=["t/a.test.ts::works", "t/a.test.ts::mints a key"])
        return {"rows": [rr, row("CAP-2", verdict="under-proven", tests=["t/a.test.ts::other"])]}

    RUN = {"unit.xml": junit(case("works"), case("mints a key", "skip"), case("other"))}

    def test_strict_alone_passes_a_skipped_citation(self):
        code, out = self.report_files(self.data(), self.RUN, "--strict")
        self.assertEqual(code, 0)
        self.assertEqual(out["rows"][0]["bucket"], "skipped")
        self.assertEqual(out["summary"]["skippedCitationCount"], 1)
        self.assertEqual(out["skippedCitations"], [{"id": "CAP-1", "lane": "tests", "test": "t/a.test.ts::mints a key"}])

    def test_fail_on_skipped_fails_and_lists_each_one(self):
        code, _out = self.report_files(self.data(), self.RUN, "--strict", "--fail-on-skipped")
        self.assertEqual(code, 1)
        tree = run("--map", str(self.dir / "map.json"), "--junit", str(self.dir / "run"), "--fail-on-skipped")
        self.assertEqual(tree.returncode, 1)
        self.assertIn("Cited tests that were skipped (1)\n  – CAP-1  t/a.test.ts::mints a key  (tests)", tree.stdout)
        md = run("--map", str(self.dir / "map.json"), "--junit", str(self.dir / "run"), "--fail-on-skipped",
                 "--format", "markdown")
        self.assertIn("- CAP-1: `t/a.test.ts::mints a key` (tests)", md.stdout)

    def test_fail_on_skipped_passes_when_nothing_cited_was_skipped(self):
        run_all = {"unit.xml": junit(case("works"), case("mints a key"), case("other"), case("uncited", "skip"))}
        code, out = self.report_files(self.data(), run_all, "--strict", "--fail-on-skipped")
        self.assertEqual((code, out["summary"]["skippedCitationCount"], out["skippedCitations"]), (0, 0, []))

    def test_fail_on_skipped_needs_a_run(self):
        m = self.dir / "map.json"
        m.write_text(json.dumps(self.data()), encoding="utf-8")
        result = run("--map", str(m), "--fail-on-skipped")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--fail-on-skipped needs --junit", result.stderr)
        self.assertNotIn("skippedCitations", json.loads(run("--map", str(m), "--json").stdout))


class Verdicts(Harness):
    def test_green_in_the_wrong_lane_is_under_proven(self):
        r = self.one([row(altitude="perception", verdict="proven", tests=["t/a.test.ts::works"])], junit(case("works")))
        self.assertEqual((r["bucket"], r["computed"], r["finding"]), ("passing", "under-proven", "optimistic"))

    def test_every_scenario_needs_its_own_lane(self):
        rr = row(tests=["t/a.test.ts::works"])
        rr["scenarios"].append({"id": "CAP-1.2", "then": "seen", "altitude": "perception"})
        r = self.one([rr], junit(case("works")))
        self.assertEqual(r["computed"], "under-proven")
        self.assertEqual([s["proven"] for s in r["scenarios"]], [True, False])

    def test_recorded_lower_is_promotable(self):
        r = self.one([row(verdict="under-proven", tests=["t/a.test.ts::works"])], junit(case("works")))
        self.assertEqual(r["finding"], "promotable")

    def test_sibling_citations_are_external_and_prove_a_sibling_scenario(self):
        r = self.one([row(altitude="sibling", siblingTests=["other-repo::its test"])], junit(case("works")))
        self.assertEqual(r["citations"][0]["status"], "external")
        self.assertEqual((r["bucket"], r["computed"]), ("external", "proven"))

    def test_config_lanes_override_the_default(self):
        config = self.dir / "promise.config.json"
        config.write_text(json.dumps({"map": {"lanes": {"response": "apiTests[]"}}}), encoding="utf-8")
        rr = row(altitude="response", tests=["t/a.test.ts::works"])
        rr["apiTests"] = []
        r = self.one([rr], junit(case("works")), "--config", str(config))
        self.assertEqual(r["scenarios"][0]["lane"], "apiTests")
        self.assertEqual(r["computed"], "under-proven")

    def test_no_run_shows_the_map_as_recorded(self):
        data = self.report([row(tests=["t/a.test.ts::works"])])
        r = data["rows"][0]
        self.assertIsNone(r["bucket"])
        self.assertEqual(r["citations"][0]["status"], "not-run")
        self.assertIn("recorded", data["summary"])


class Homes(Harness):
    """Every test in the run has a row, and every row an outcome doc: what has
    no home is counted, listed on request, and can fail the run."""

    def files(self, rows, xml):
        m = self.dir / "m.json"
        m.write_text(json.dumps({"rows": rows}), encoding="utf-8")
        x = self.dir / "x.xml"
        x.write_text(xml, encoding="utf-8")
        return str(m), str(x)

    def test_a_case_no_row_cites_is_an_orphan(self):
        data = self.report([row(tests=["t/a.test.ts::a"])], junit(case("a"), case("b", "fail")))
        self.assertEqual(data["summary"]["orphanCount"], 1)
        self.assertEqual(data["orphans"], [{"file": "t/a.test.ts", "name": "b", "classname": "t/a.test.ts", "status": "failing"}])

    def test_a_citation_in_any_row_and_any_lane_homes_its_cases(self):
        rows = [row("CAP-1", tests=["t/a.test.ts::a"]),
                row("CAP-2", altitude="perception", e2eTests=["t/a.test.ts::Mute"])]
        xml = junit(case("a"), case("Mute > stores it"), case("Mute > clears it", "skip"), case("other"))
        data = self.report(rows, xml)
        self.assertEqual([o["name"] for o in data["orphans"]], ["other"])

    def test_parametrised_and_pytest_citations_home_every_case_they_match(self):
        xml = junit(case("exports 3 rows"), case("exports 10 rows"))
        self.assertEqual(self.report([row(tests=["t/a.test.ts::exports %d rows"])], xml)["orphans"], [])
        pytest_xml = ('<testsuites><testsuite name="pytest">'
                      '<testcase classname="tests.test_x" name="test_a[1-b]"/>'
                      '<testcase classname="tests.test_x" name="test_a[2-c]"/>'
                      '<testcase classname="tests.test_x" name="test_b"/></testsuite></testsuites>')
        orphans = self.report([row(tests=["tests/test_x.py::test_a"])], pytest_xml)["orphans"]
        self.assertEqual(orphans, [{"file": None, "name": "test_b", "classname": "tests.test_x", "status": "passing"}])

    HEALTH = ('<testsuites><testsuite name="tests/health.test.ts"><testcase classname="tests/health.test.ts" '
              'name="returns ok"/></testsuite></testsuites>')

    def test_a_citation_in_one_package_does_not_home_the_same_test_in_another(self):
        portal = self.HEALTH.replace('name="returns ok"/>', 'name="returns ok"><failure/></testcase>')
        code, out = self.report_files({"rows": [row(tests=["apps/api/tests/health.test.ts::returns ok"])]},
                                      {"api.xml": self.HEALTH, "portal.xml": portal}, "--fail-on-orphans")
        # the run file named after the package picks the api case; the portal's is cited by nobody
        self.assertEqual((out["summary"]["orphanCount"], code), (1, 1))
        self.assertTrue(out["orphans"][0]["status"] == "failing")
        citation = out["rows"][0]["citations"][0]
        self.assertEqual((citation["status"], citation["matches"]), ("passing", 1))
        self.assertNotIn("ambiguous", citation)

    def test_a_citation_the_run_cannot_place_is_ambiguous_and_homes_nothing(self):
        portal = self.HEALTH.replace('name="returns ok"/>', 'name="returns ok"><failure/></testcase>')
        code, out = self.report_files({"rows": [row(tests=["tests/health.test.ts::returns ok"])]},
                                      {"a.xml": self.HEALTH, "b.xml": portal}, "--fail-on-orphans")
        citation = out["rows"][0]["citations"][0]
        self.assertEqual((citation["status"], citation["matches"], citation["ambiguous"], citation["places"]),
                         ("failing", 2, True, 2))
        self.assertEqual((out["summary"]["orphanCount"], code), (2, 1))

    def test_two_cases_with_no_file_are_two_places(self):
        # node's built-in reporter: classname "test" and no file for every case
        xml = ('<testsuites><testsuite name="a"><testcase classname="test" name="helpers"/></testsuite>'
               '<testsuite name="b"><testcase classname="test" name="helpers"><failure/></testcase></testsuite>'
               '</testsuites>')
        data = self.report([row(tests=["a/x.test.mjs::helpers"])], xml)
        self.assertTrue(data["rows"][0]["citations"][0]["ambiguous"])
        self.assertEqual(data["summary"]["orphanCount"], 2)
        one = '<testsuites><testsuite name="a"><testcase classname="test" name="helpers"/></testsuite></testsuites>'
        self.assertEqual(self.report([row(tests=["a/x.test.mjs::helpers"])], one)["orphans"], [])

    def test_the_cited_file_itself_wins_over_a_longer_path_that_ends_in_it(self):
        xml = ('<testsuites><testsuite name="apps/api/tests/x.test.ts"><testcase classname="c" name="works">'
               '<failure/></testcase></testsuite><testsuite name="tests/x.test.ts"><testcase classname="c" '
               'name="works"/></testsuite></testsuites>')
        data = self.report([row(tests=["tests/x.test.ts::works"])], xml)
        self.assertEqual(data["rows"][0]["bucket"], "passing")
        self.assertEqual([o["file"] for o in data["orphans"]], ["apps/api/tests/x.test.ts"])

    def test_the_same_test_twice_in_one_place_is_one_test(self):
        # a Playwright run with two projects lists each test once per project
        xml = junit(case("works"), case("works", "fail"))
        data = self.report([row(tests=["t/a.test.ts::works"])], xml)
        self.assertEqual((data["rows"][0]["bucket"], data["summary"]["orphanCount"]), ("failing", 0))
        self.assertNotIn("ambiguous", data["rows"][0]["citations"][0])

    def test_sibling_and_bad_citations_never_home_a_case(self):
        rows = [row(altitude="sibling", siblingTests=["t/a.test.ts::works"]),
                row("CAP-2", tests=["t/a.test.ts::<test name>", "t/other.test.ts::works"])]
        data = self.report(rows, junit(case("works")))
        self.assertEqual(data["summary"]["orphanCount"], 1)

    def test_orphans_flag_lists_them_in_the_tree_and_the_markdown(self):
        m, x = self.files([row(tests=["t/a.test.ts::a"])], junit(case("a"), case("b", "skip")))
        plain = run("--map", m, "--junit", x)
        self.assertNotIn("Tests with no row", plain.stdout)
        self.assertIn("1 test has no row", plain.stdout)
        tree = run("--map", m, "--junit", x, "--orphans")
        self.assertIn("Tests with no row (1)\n  – t/a.test.ts::b  skipped", tree.stdout)
        md = run("--map", m, "--junit", x, "--orphans", "--format", "markdown")
        self.assertIn("## Tests with no row (1)\n\n- `t/a.test.ts::b` — skipped", md.stdout)

    def test_a_case_with_no_file_is_labelled_by_its_classname(self):
        xml = '<testsuites><testsuite name="x"><testcase classname="Mute" name="works"/></testsuite></testsuites>'
        m, x = self.files([row()], xml)
        self.assertIn("  ✓ Mute::works  passing", run("--map", m, "--junit", x, "--orphans").stdout)

    def test_fail_on_orphans_exits_one_only_when_there_is_one(self):
        m, x = self.files([row(tests=["t/a.test.ts::a"])], junit(case("a"), case("b")))
        self.assertEqual(run("--map", m, "--junit", x, "--fail-on-orphans").returncode, 1)
        self.assertEqual(run("--map", m, "--junit", x).returncode, 0)
        m, x = self.files([row(tests=["t/a.test.ts::a"])], junit(case("a")))
        self.assertEqual(run("--map", m, "--junit", x, "--fail-on-orphans").returncode, 0)

    def test_orphan_flags_need_a_run(self):
        m, _x = self.files([row()], junit(case("a")))
        for flag in ("--orphans", "--fail-on-orphans"):
            with self.subTest(flag=flag):
                result = run("--map", m, flag)
                self.assertEqual(result.returncode, 2)
                self.assertIn("needs --junit", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_no_run_has_no_orphans(self):
        data = self.report([row()])
        self.assertNotIn("orphans", data)
        self.assertNotIn("orphanCount", data["summary"])

    def test_rows_without_an_outcome_doc_are_counted_with_or_without_a_run(self):
        rows = [row("CAP-1"), dict(row("CAP-2"), doc="docs/designs/mute.md"), dict(row("CAP-3"), doc="  ")]
        del rows[0]["doc"]
        m, x = self.files(rows, junit(case("a")))
        self.assertEqual(self.report(rows)["summary"]["rowsWithoutDoc"], 2)
        self.assertEqual(self.report(rows, junit(case("a")))["summary"]["rowsWithoutDoc"], 2)
        self.assertIn("\n2 rows have no outcome doc", run("--map", m).stdout)
        self.assertIn("1 test has no row · 2 rows have no outcome doc", run("--map", m, "--junit", x).stdout)
        m, _x = self.files([row()], junit(case("a")))
        self.assertIn("1 row has no outcome doc", run("--map", m).stdout)

    def test_every_home_filled_adds_no_line(self):
        m, x = self.files([dict(row(tests=["t/a.test.ts::a"]), doc="docs/designs/a.md")], junit(case("a")))
        out = run("--map", m, "--junit", x).stdout
        self.assertNotIn("has no row", out)
        self.assertNotIn("outcome doc", out)


class LeftOut(Harness):
    """A test the team chose to leave with no row is named in the map's
    top-level leftOut list: not an orphan, listed apart, stale when gone."""

    def files(self, data, xml=None):
        m = self.dir / "m.json"
        m.write_text(json.dumps(data), encoding="utf-8")
        if xml is None:
            return str(m), None
        x = self.dir / "x.xml"
        x.write_text(xml, encoding="utf-8")
        return str(m), str(x)

    def entry(self, test, reason="a helper's own test", date="2026-01-01"):
        return {"test": test, "reason": reason, "date": date}

    def test_a_left_out_test_is_not_an_orphan_and_a_gone_one_is_stale(self):
        data = {"rows": [row(tests=["t/a.test.ts::a"])],
                "leftOut": [self.entry("t/a.test.ts::formats a date"), self.entry("t/a.test.ts::renamed long ago")]}
        m, x = self.files(data, junit(case("a"), case("formats a date"), case("stray")))
        out = json.loads(run("--map", m, "--junit", x, "--json").stdout)
        self.assertEqual([o["name"] for o in out["orphans"]], ["stray"])
        self.assertEqual([(e["test"], e["status"], e["ran"]) for e in out["leftOut"]],
                         [("t/a.test.ts::formats a date", "passing", True),
                          ("t/a.test.ts::renamed long ago", "never-ran", False)])
        self.assertEqual((out["summary"]["leftOutCount"], out["summary"]["staleLeftOutCount"]), (2, 1))

    def test_an_entry_matches_one_test_exactly_never_a_describe_block_or_a_pattern(self):
        xml = ('<testsuites><testsuite name="s" file="tests/api/auth.test.ts">'
               + case("Auth &gt; logs in") + case("Auth &gt; logs out") + '</testsuite>'
               '<testsuite name="s" file="tests/api/billing.test.ts">'
               + case("Billing &gt; charges") + case("Billing &gt; refunds") + '</testsuite></testsuites>')
        data = {"rows": [row()], "leftOut": [self.entry("tests/api/auth.test.ts::Auth"),
                                              self.entry("tests/api/billing.test.ts::Bil%s")]}
        m, x = self.files(data, xml)
        out = json.loads(run("--map", m, "--junit", x, "--json").stdout)
        self.assertEqual(out["summary"]["orphanCount"], 4)
        self.assertEqual([(e["status"], e["ran"], e["hides"]) for e in out["leftOut"]],
                         [("never-ran", False, 0), ("never-ran", False, 0)])
        self.assertEqual(run("--map", m, "--junit", x, "--fail-on-orphans").returncode, 1)

    def test_a_renamed_left_out_test_does_not_home_a_test_with_the_same_leaf(self):
        xml = ('<testsuites><testsuite name="tests/util.test.ts">'
               '<testcase classname="tests/util.test.ts" name="format helper builds a string"/>'
               '<testcase classname="tests/util.test.ts" name="invoices &gt; format"><failure/></testcase>'
               '</testsuite></testsuites>')
        m, x = self.files({"rows": [row()], "leftOut": [self.entry("tests/util.test.ts::format")]}, xml)
        out = json.loads(run("--map", m, "--junit", x, "--json").stdout)
        self.assertEqual({o["name"] for o in out["orphans"]}, {"invoices > format", "format helper builds a string"})
        self.assertEqual((out["leftOut"][0]["status"], out["summary"]["staleLeftOutCount"]), ("never-ran", 1))

    def test_an_entry_reports_how_many_cases_it_hides(self):
        pytest_xml = ('<testsuites><testsuite name="pytest">'
                      '<testcase classname="tests.test_x" name="test_a[1-b]"/>'
                      '<testcase classname="tests.test_x" name="test_a[2-c]"/></testsuite></testsuites>')
        m, x = self.files({"rows": [row()], "leftOut": [self.entry("tests/test_x.py::test_a")]}, pytest_xml)
        out = json.loads(run("--map", m, "--junit", x, "--json").stdout)
        self.assertEqual((out["leftOut"][0]["matches"], out["leftOut"][0]["hides"], out["orphans"]), (2, 2, []))
        self.assertIn("  ✓ tests/test_x.py::test_a  passing, hides 2 cases — a helper's own test (2026-01-01)",
                      run("--map", m, "--junit", x, "--orphans").stdout)

    def test_an_entry_with_no_reason_no_date_or_no_file_hides_nothing(self):
        xml = junit(case("a"), case("b"), case("c"))
        entries = [{"test": "t/a.test.ts::a"}, self.entry("t/a.test.ts::b", date="someday"), self.entry("c")]
        m, x = self.files({"rows": [row()], "leftOut": entries}, xml)
        out = json.loads(run("--map", m, "--junit", x, "--json").stdout)
        self.assertEqual([o["name"] for o in out["orphans"]], ["a", "b", "c"])
        self.assertEqual([e["problem"] for e in out["leftOut"]],
                         ["no one-line reason", "no real YYYY-MM-DD date", "the test is not <file>::<name>"])
        self.assertEqual(out["summary"]["leftOutProblemCount"], 3)
        self.assertIn("3 left-out entries have a problem", run("--map", m, "--junit", x).stdout)
        no_run = json.loads(run("--map", m, "--json").stdout)
        self.assertEqual(no_run["summary"]["leftOutProblemCount"], 3)

    def test_a_test_both_cited_and_left_out_is_a_problem(self):
        m, x = self.files({"rows": [row(tests=["t/a.test.ts::a"])], "leftOut": [self.entry("t/a.test.ts::a")]},
                          junit(case("a")))
        out = json.loads(run("--map", m, "--junit", x, "--json").stdout)
        self.assertEqual(out["leftOut"][0]["problem"], "also cited by CAP-1")
        self.assertEqual(out["orphans"], [])
        self.assertEqual(run("--map", m, "--junit", x, "--fail-on-orphans").returncode, 1)

    def test_a_failing_stale_or_broken_entry_fails_the_orphan_gate(self):
        for entry, xml in ((self.entry("t/a.test.ts::a"), junit(case("a", "fail"))),
                           (self.entry("t/a.test.ts::gone"), junit(case("a"))),
                           ({"test": "t/a.test.ts::a", "reason": "x"}, junit(case("a")))):
            with self.subTest(entry=entry):
                rows = [row(tests=["t/a.test.ts::a"])] if entry["test"].endswith("gone") else [row()]
                m, x = self.files({"rows": rows, "leftOut": [entry]}, xml)
                result = run("--map", m, "--junit", x, "--fail-on-orphans")
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn("Tests with no row (0)" if entry.get("date") else "Tests with no row (1)",
                              run("--map", m, "--junit", x, "--orphans").stdout)
        m, x = self.files({"rows": [row()], "leftOut": [self.entry("t/a.test.ts::a")]}, junit(case("a")))
        self.assertEqual(run("--map", m, "--junit", x, "--fail-on-orphans").returncode, 0)

    def test_orphans_flag_lists_them_apart_and_the_summary_names_the_stale(self):
        data = {"rows": [row()], "leftOut": [self.entry("t/a.test.ts::a"), self.entry("t/a.test.ts::gone", date="2026-02-03")]}
        m, x = self.files(data, junit(case("a")))
        out = run("--map", m, "--junit", x, "--orphans").stdout
        self.assertIn("Tests with no row (0)", out)
        self.assertIn("Left out (2)\n  ✓ t/a.test.ts::a  passing — a helper's own test (2026-01-01)\n"
                      "  ? t/a.test.ts::gone  never ran (stale) — a helper's own test (2026-02-03)", out)
        self.assertIn("1 left-out test is not in the run", out)
        self.assertEqual(run("--map", m, "--junit", x, "--fail-on-orphans").returncode, 1, "a stale entry fails the gate")

    def test_without_a_run_left_out_is_listed_with_ran_null(self):
        m, _ = self.files({"rows": [row()], "leftOut": [self.entry("t/a.test.ts::a")]})
        out = json.loads(run("--map", m, "--json").stdout)
        self.assertIsNone(out["leftOut"][0]["ran"])
        self.assertEqual(out["summary"]["leftOutCount"], 1)
        self.assertNotIn("staleLeftOutCount", out["summary"])

    def test_a_malformed_entry_homes_nothing_and_a_bad_list_is_refused(self):
        m, x = self.files({"rows": [row()], "leftOut": [self.entry("t/a.test.ts::<test name>"), "a"]}, junit(case("a")))
        out = json.loads(run("--map", m, "--junit", x, "--json").stdout)
        self.assertEqual([e["status"] for e in out["leftOut"]], ["bad-citation", "bad-citation"])
        self.assertEqual(out["summary"]["orphanCount"], 1)
        m, _ = self.files({"rows": [row()], "leftOut": {"test": "x::y"}})
        result = run("--map", m)
        self.assertEqual(result.returncode, 2)
        self.assertIn("leftOut is not a list", result.stderr)


class Surfaces(Harness):
    """Every entry point in the code has a row: --surfaces joins the code's
    entry points to the rows' surfaces, both ways."""

    def files(self, rows, surfaces_text):
        m = self.dir / "m.json"
        m.write_text(json.dumps({"rows": rows}), encoding="utf-8")
        f = self.dir / "surfaces.txt"
        f.write_text(surfaces_text, encoding="utf-8")
        return str(m), str(f)

    ENTRY_POINTS = "# routes\nGET /me\n\n  POST /tickets  \ncron weekly-update\nGET /me\n"

    def test_unmapped_and_stale_entry_points(self):
        rows = [dict(row("CAP-1"), surfaces=["GET /me", " page /old "]), dict(row("CAP-2"), surfaces="POST /tickets")]
        m, f = self.files(rows, self.ENTRY_POINTS)
        out = json.loads(run("--map", m, "--surfaces", f, "--json").stdout)
        self.assertEqual(out["unmappedSurfaces"], ["cron weekly-update"])
        self.assertEqual(out["staleSurfaces"], [{"id": "CAP-1", "surface": "page /old"}])
        self.assertEqual((out["summary"]["surfaces"], out["summary"]["unmappedSurfaceCount"],
                          out["summary"]["staleSurfaceCount"]), (3, 1, 1))
        self.assertEqual(out["rows"][1]["surfaces"], ["POST /tickets"])

    def test_tree_and_markdown_list_them_and_the_summary_counts_them(self):
        m, f = self.files([dict(row(), surfaces=["GET /me", "page /old"])], self.ENTRY_POINTS)
        tree = run("--map", m, "--surfaces", f).stdout
        self.assertIn("  enters: GET /me · page /old", tree)
        self.assertIn("Entry points with no row (2)\n  POST /tickets\n  cron weekly-update", tree)
        self.assertIn("Row surfaces not in the entry-point list (1)\n  CAP-1  page /old", tree)
        self.assertIn("2 entry points have no row · 1 row surface is not in the entry-point list", tree)
        md = run("--map", m, "--surfaces", f, "--format", "markdown").stdout
        self.assertIn("## Entry points with no row (2)\n\n- `POST /tickets`\n- `cron weekly-update`", md)

    def test_it_works_beside_a_run(self):
        m, f = self.files([dict(row(tests=["t/a.test.ts::works"]), surfaces=["GET /me"])], "GET /me\n")
        x = self.dir / "x.xml"
        x.write_text(junit(case("works")), encoding="utf-8")
        out = json.loads(run("--map", m, "--surfaces", f, "--junit", str(x), "--json").stdout)
        self.assertEqual((out["unmappedSurfaces"], out["rows"][0]["bucket"]), ([], "passing"))

    def test_fail_on_unmapped(self):
        m, f = self.files([dict(row(), surfaces=["GET /me"])], "GET /me\nPOST /tickets\n")
        self.assertEqual(run("--map", m, "--surfaces", f).returncode, 0)
        self.assertEqual(run("--map", m, "--surfaces", f, "--fail-on-unmapped").returncode, 1)
        m, f = self.files([dict(row(), surfaces=["GET /me", "GET /gone"])], "GET /me\n")
        self.assertEqual(run("--map", m, "--surfaces", f, "--fail-on-unmapped").returncode, 0, "stale does not fail")

    def test_stdin_is_read_with_a_dash(self):
        m, _ = self.files([row()], "")
        result = subprocess.run([sys.executable, str(REPORT), "--map", m, "--surfaces", "-", "--json"],
                                input="GET /me\n", capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout)["unmappedSurfaces"], ["GET /me"])

    def test_a_byte_order_mark_on_stdin_is_not_part_of_the_first_entry_point(self):
        m, _ = self.files([dict(row(), surfaces=["GET /me"])], "")
        result = subprocess.run([sys.executable, str(REPORT), "--map", m, "--surfaces", "-", "--json",
                                 "--fail-on-unmapped"], input=b"\xef\xbb\xbfGET /me\r\n\r\nGET /me\r\n",
                                capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        out = json.loads(result.stdout)
        self.assertEqual((out["unmappedSurfaces"], out["staleSurfaces"], out["summary"]["surfaces"]), ([], [], 1))

    def test_the_list_is_in_the_fingerprint(self):
        m, f = self.files([row()], "GET /me\n")
        first = json.loads(run("--map", m, "--surfaces", f, "--json").stdout)["summary"]["fingerprint"]
        Path(f).write_text("GET /you\n", encoding="utf-8")
        self.assertNotEqual(json.loads(run("--map", m, "--surfaces", f, "--json").stdout)["summary"]["fingerprint"], first)

    def test_usage_errors(self):
        m, f = self.files([row()], "# nothing but comments\n\n")
        for args, message in (((("--surfaces", f)), "lists no entry points"),
                               (("--surfaces", str(self.dir / "missing.txt")), "cannot read entry points"),
                               (("--fail-on-unmapped",), "needs --surfaces")):
            with self.subTest(args=args):
                result = run("--map", m, *args)
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)
                self.assertNotIn("Traceback", result.stderr)


class Cli(Harness):
    def test_example_proofmap_shows_every_outcome(self):
        result = run("--map", str(EXAMPLE / "map.json"), "--junit", str(EXAMPLE / "run"), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = {r["id"]: (r["bucket"], r["computed"], r["finding"]) for r in json.loads(result.stdout)["rows"]}
        self.assertEqual(rows, {
            "CAP-1": ("passing", "proven", None),
            "CAP-2": ("passing", "under-proven", "optimistic"),
            "CAP-3": ("failing", "not-built", "optimistic"),
            "CAP-4": ("never-ran", "not-built", "optimistic"),
            "CAP-5": ("passing", "proven", "promotable"),
            "CAP-6": ("no-test", "not-built", "optimistic"),
        })

    def test_example_proofmap_has_one_test_with_no_row(self):
        result = run("--map", str(EXAMPLE / "map.json"), "--junit", str(EXAMPLE / "run"), "--json")
        data = json.loads(result.stdout)
        self.assertEqual(data["summary"]["orphanCount"], 1)
        self.assertEqual((data["orphans"][0]["file"], data["orphans"][0]["name"]),
                         ("tests/e2e/share.spec.ts", "reader sees no edit control"))
        self.assertEqual(data["summary"]["rowsWithoutDoc"], 6)

    def test_tree_and_markdown_print_the_headline(self):
        for fmt in ("tree", "markdown"):
            with self.subTest(fmt=fmt):
                result = run("--map", str(EXAMPLE / "map.json"), "--junit", str(EXAMPLE / "run"), "--format", fmt)
                self.assertEqual(result.returncode, 0)
                self.assertIn("3 of 4 must rows not lane-green · 6 promises · 3 passing in this run · 2 lane-green", result.stdout)
                self.assertIn("1 is green but not proven at the altitude promised", result.stdout)

    def test_strict_exits_one_on_failing_or_optimistic(self):
        self.assertEqual(run("--map", str(EXAMPLE / "map.json"), "--junit", str(EXAMPLE / "run"), "--strict").returncode, 1)
        ok = self.dir / "ok.json"
        ok.write_text(json.dumps({"rows": [row(verdict="proven", tests=["t/a.test.ts::works"])]}), encoding="utf-8")
        xml = self.dir / "ok.xml"
        xml.write_text(junit(case("works")), encoding="utf-8")
        self.assertEqual(run("--map", str(ok), "--junit", str(xml), "--strict").returncode, 0)

    def test_usage_errors_exit_two(self):
        bad_xml = self.dir / "bad.xml"
        bad_xml.write_text("<testsuites><testsuite>", encoding="utf-8")
        self.assertEqual(run("--map", str(self.dir / "missing.json")).returncode, 2)
        self.assertEqual(run("--map", str(EXAMPLE / "map.json"), "--junit", str(self.dir / "nope")).returncode, 2)
        self.assertEqual(run("--map", str(EXAMPLE / "map.json"), "--junit", str(bad_xml)).returncode, 2)
        empty = self.dir / "empty"
        empty.mkdir()
        self.assertEqual(run("--map", str(EXAMPLE / "map.json"), "--junit", str(empty)).returncode, 2)

    def test_the_map_is_never_written(self):
        before = (EXAMPLE / "map.json").read_bytes()
        run("--map", str(EXAMPLE / "map.json"), "--junit", str(EXAMPLE / "run"))
        self.assertEqual((EXAMPLE / "map.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()


class ConfigShapes(Harness):
    def test_a_map_that_is_not_an_object_uses_the_default_lanes(self):
        for value in ("oops", False, None, 3):
            with self.subTest(value=value):
                config = self.dir / "c.json"
                config.write_text(json.dumps({"map": value}), encoding="utf-8")
                r = self.one([row(tests=["t/a.test.ts::works"])], junit(case("works")), "--config", str(config))
                self.assertEqual(r["computed"], "proven")
