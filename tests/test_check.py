"""Tests for check.py: one local command for what the GitHub Action checks.

Run from the repo root:

    python3 -m unittest discover -s tests -v

Each test builds a small git repository in a temporary directory: an outcome
doc in docs/designs, committed, then changed or not. check.py runs the lint,
the §0 check against a base ref, the project's entry-point command, and the
map report joined to a JUnit run and that list, each as its own subprocess,
and prints one line per step. The Action's own shell is run here too, so its
wiring is exercised, not only read.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parent
SCRIPTS_DIR = REPO / "skills" / "promise" / "scripts"
CHECK = SCRIPTS_DIR / "check.py"
ACTION = REPO / "action.yml"
CONFORMING = TESTS_DIR / "fixtures" / "conforming.md"
EXAMPLE = REPO / "examples" / "channel-muting.md"
RULE = "- A muted channel never sends a push or a badge count until it is unmuted."

MAP_CONFIG = {
    "recipe": "docs/capabilities/recipe.md",
    "find": "python3 docs/capabilities/capability_find.py",
    "row": "python3 docs/capabilities/capability_find.py --row",
    "lanes": {"data": "tests[]", "response": "tests[]", "perception": "e2eTests[]",
              "judgement": "evalTests[]", "sibling": "siblingTests[]"},
}


def git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=str(cwd), check=True, capture_output=True,
    )


def junit(*cases: str) -> str:
    return '<testsuites><testsuite name="s" file="t/a.test.ts">' + "".join(cases) + "</testsuite></testsuites>"


def case(name: str, outcome: str = "pass") -> str:
    inner = "<failure/>" if outcome == "fail" else ""
    return f'<testcase classname="c" name="{name}">{inner}</testcase>'


def row(verdict: str = "proven", tests=("t/a.test.ts::works",)) -> dict:
    return {"id": "CAP-1", "story": "A member mutes a channel.", "doc": None, "verdict": verdict,
            "scenarios": [{"id": "CAP-1.1", "given": "g", "when": "w", "then": "t", "altitude": "data"}],
            "tests": list(tests), "e2eTests": [], "evalTests": [], "siblingTests": []}


class Project(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.docs = self.root / "docs" / "designs"
        self.docs.mkdir(parents=True)
        shutil.copy(CONFORMING, self.docs / "conforming.md")
        git(self.root, "init", "-q")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "base")

    def check(self, *args: str, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
        full_env = dict(os.environ)
        full_env.pop("GITHUB_ACTIONS", None)
        full_env.update(env or {})
        return subprocess.run([sys.executable, str(CHECK), *args], cwd=str(self.root), capture_output=True,
                              text=True, encoding="utf-8", env=full_env)

    def check_json(self, *args: str) -> dict:
        result = self.check(*args, "--json")
        self.assertIn(result.returncode, (0, 1), result.stderr)
        return json.loads(result.stdout)

    def statuses(self, *args: str) -> Dict[str, str]:
        return {s["step"]: s["status"] for s in self.check_json(*args)["steps"]}

    def step(self, name: str, *args: str) -> Dict[str, Any]:
        return next(s for s in self.check_json(*args)["steps"] if s["step"] == name)

    def write_config(self, config: dict) -> Path:
        path = self.root / ".claude" / "promise.config.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def write_map(self, rows, folder: str = "docs/capabilities") -> Path:
        path = self.root / folder / "map.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": 1, "rows": rows}), encoding="utf-8")
        return path

    def write_run(self, xml: str, name: str = "results/unit.xml") -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(xml, encoding="utf-8")
        return path


class LintAndSection0(Project):
    def test_a_conforming_folder_passes_and_prints_one_line_per_step(self) -> None:
        result = self.check("--docs-home", "docs/designs")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("promise check: lint: ok (docs/designs)\n", result.stdout)
        self.assertIn("promise check: §0: skipped (no --base)\n", result.stdout)
        self.assertIn("promise check: surfaces: skipped (no entry-point command: pass --surfaces-cmd or set "
                      "map.surfaces)\n", result.stdout)
        self.assertIn("promise check: checks: skipped (no map configured)\n", result.stdout)
        self.assertIn("promise check: map: skipped (no map configured)\n", result.stdout)
        self.assertIn("promise check: gate: skipped (no shipped doc has a §6 line that needs a proven backfilled row)\n", result.stdout)
        self.assertTrue(result.stdout.endswith("promise check: 1 ok, 0 failed, 5 skipped\n"), result.stdout)

    def test_docs_home_comes_from_the_config_or_detection_and_the_flag_overrides(self) -> None:
        self.assertEqual(self.check_json()["docsHome"], "docs/designs")
        other = self.root / "docs" / "promises"
        other.mkdir()
        self.write_config({"version": 1, "docsHome": "docs/promises"})
        self.assertEqual(self.check_json()["docsHome"], "docs/promises")
        self.assertEqual(self.check_json("--docs-home", "docs/designs")["docsHome"], "docs/designs")

    def test_a_lint_error_fails_the_step_and_the_run(self) -> None:
        text = CONFORMING.read_text(encoding="utf-8").replace("Status: draft", "Status: someday", 1)
        (self.docs / "conforming.md").write_text(text, encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("HEADER_STATUS", result.stdout)
        self.assertIn("promise check: lint: failed (docs/designs: exit 1)", result.stdout)

    def test_an_agreed_doc_whose_section0_changed_fails_against_the_base(self) -> None:
        agreed = EXAMPLE.read_text(encoding="utf-8").replace("Status: draft", "Status: agreed", 1)
        (self.docs / "mute.md").write_text(agreed, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "agreed")
        self.assertEqual(self.check("--base", "HEAD").returncode, 0)
        (self.docs / "mute.md").write_text(agreed.replace(RULE, RULE[:-1] + " or a day passes."), encoding="utf-8")
        result = self.check("--base", "HEAD")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("S0_CHANGED", result.stdout)
        self.assertIn("promise check: lint: ok (docs/designs)", result.stdout)
        self.assertIn("promise check: §0: failed (docs/designs against HEAD: exit 1)", result.stdout)

    def test_a_missing_docs_folder_skips_lint_and_section0(self) -> None:
        result = self.check("--docs-home", "docs/nowhere", "--base", "HEAD")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("promise check: lint: skipped (no folder docs/nowhere)", result.stdout)
        self.assertIn("promise check: §0: skipped (no folder docs/nowhere)", result.stdout)

    def test_an_unknown_base_ref_fails_the_section0_step(self) -> None:
        result = self.check("--base", "no-such-ref")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown git ref", result.stdout)
        self.assertIn("promise check: §0: failed", result.stdout)

    def test_no_lint_skips_the_lint(self) -> None:
        self.assertEqual(self.statuses("--no-lint")["lint"], "skipped")

    def test_json_parses_each_scripts_own_json(self) -> None:
        data = self.check_json("--base", "HEAD")
        self.assertTrue(data["ok"])
        lint = data["steps"][0]
        self.assertEqual((lint["step"], lint["status"], lint["exit"]), ("lint", "ok", 0))
        self.assertEqual(lint["argv"][0], sys.executable)
        self.assertEqual(lint["output"][0]["findings"], [])
        self.assertEqual(data["steps"][1]["output"][0]["stats"]["errors"], 0)
        self.assertEqual([s["step"] for s in data["steps"]], ["lint", "§0", "gate", "checks", "surfaces", "map"])
        self.assertIsNone(data["steps"][5]["argv"])

    def test_github_actions_folds_each_steps_output_into_a_group(self) -> None:
        text = CONFORMING.read_text(encoding="utf-8").replace("Status: draft", "Status: someday", 1)
        (self.docs / "conforming.md").write_text(text, encoding="utf-8")
        out = self.check(env={"GITHUB_ACTIONS": "true"}).stdout
        self.assertRegex(out, r"::group::promise check: lint\n(.|\n)*HEADER_STATUS(.|\n)*::endgroup::\npromise check: lint: failed")

    def test_usage_errors_exit_two_without_a_traceback(self) -> None:
        bad = self.root / "bad.json"
        bad.write_text("[1, 2]", encoding="utf-8")
        for args in (("--cwd", str(self.root / "nope")), ("--config", str(self.root / "missing.json")),
                     ("--config", str(bad)), ("--frobnicate",)):
            with self.subTest(args=args):
                result = self.check(*args)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertNotIn("Traceback", result.stderr)
                self.assertIn("check.py", result.stderr)


class MapStep(Project):
    def test_map_and_junit_run_the_report(self) -> None:
        self.write_config({"version": 1, "map": MAP_CONFIG})
        self.write_map([row()])
        run = self.write_run(junit(case("works")))
        result = self.check("--junit", str(run))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 promises · 1 passing in this run · 1 lane-green", result.stdout)
        self.assertIn("promise check: map: ok (docs/capabilities/map.json joined to 1 run path)", result.stdout)

    def test_the_report_runs_strict_so_a_failing_or_optimistic_row_fails(self) -> None:
        self.write_config({"version": 1, "map": MAP_CONFIG})
        self.write_map([row()])
        run = self.write_run(junit(case("works", "fail")))
        result = self.check("--junit", str(run))
        self.assertEqual(result.returncode, 1)
        self.assertIn("promise check: map: failed (docs/capabilities/map.json joined to 1 run path: exit 1)", result.stdout)
        report = self.step("map", "--junit", str(run))
        self.assertIn("--strict", report["argv"])
        self.assertIn("--config", report["argv"])
        self.assertEqual(report["output"]["rows"][0]["bucket"], "failing")

    def test_fail_on_orphans_is_passed_through(self) -> None:
        self.write_config({"version": 1, "map": MAP_CONFIG})
        self.write_map([row()])
        run = self.write_run(junit(case("works"), case("nobody cites me")))
        self.assertEqual(self.check("--junit", str(run)).returncode, 0)
        result = self.check("--junit", str(run), "--fail-on-orphans")
        self.assertEqual(result.returncode, 1)
        self.assertIn("1 test has no row", result.stdout)

    def test_a_map_set_to_false_is_skipped_on_purpose(self) -> None:
        self.write_config({"version": 1, "map": False})
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("warning", result.stdout)
        for name in ("checks", "map"):
            self.assertIn(f"promise check: {name}: skipped (map is false: this project keeps no map, on purpose)",
                          result.stdout)
        # there is no map.surfaces to set, so the hint names only the flag
        self.assertIn("promise check: surfaces: skipped (no entry-point command: pass --surfaces-cmd (map is "
                      "false, so there is no map.surfaces))", result.stdout)
        run = self.write_run(junit(case("works")))
        result = self.check("--junit", str(run))
        self.assertEqual(result.returncode, 1)
        self.assertIn("promise check: map: failed (--junit needs a map, and the config has none (map is false: "
                      "this project keeps no map, on purpose))", result.stdout)

    def test_fail_on_skipped_is_passed_through_and_needs_a_run(self) -> None:
        self.write_config({"version": 1, "map": MAP_CONFIG})
        self.write_map([row(verdict="under-proven", tests=("t/a.test.ts::works", "t/a.test.ts::later"))])
        run = self.write_run(junit(case("works"), '<testcase classname="c" name="later"><skipped/></testcase>'))
        self.assertEqual(self.check("--junit", str(run)).returncode, 0)
        result = self.check("--junit", str(run), "--fail-on-skipped")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("CAP-1  t/a.test.ts::later  (tests)", result.stdout)
        self.assertIn("--fail-on-skipped", self.step("map", "--junit", str(run), "--fail-on-skipped")["argv"])
        result = self.check("--fail-on-skipped")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("promise check: map: failed (--fail-on-skipped needs a test run: no test run: pass --junit "
                      "or set map.junit)", result.stdout)

    def test_map_junit_from_the_config_waits_for_the_tests_to_run(self) -> None:
        self.write_config({"version": 1, "map": dict(MAP_CONFIG, junit=["results/unit.xml"])})
        self.write_map([row()])
        result = self.check()
        self.assertEqual(result.returncode, 0)
        self.assertIn("promise check: map: skipped (no JUnit results at map.junit yet (results/unit.xml); "
                      "run the tests first)", result.stdout)
        self.write_run(junit(case("works")))
        self.assertIn("promise check: map: ok", self.check().stdout)

    def test_a_map_junit_path_not_written_yet_is_left_out_and_named(self) -> None:
        self.write_config({"version": 1, "map": dict(MAP_CONFIG, junit=["results/unit.xml", "results/e2e"])})
        self.write_map([row()])
        self.write_run(junit(case("works")))
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("no such run file", result.stdout + result.stderr)
        self.assertIn("promise check: map: ok (docs/capabilities/map.json joined to 1 run path; "
                      "not written yet: results/e2e)", result.stdout)

    def test_fail_on_orphans_fails_when_no_run_can_be_joined(self) -> None:
        self.write_config({"version": 1, "map": dict(MAP_CONFIG, junit=["result/unit.xml"])})  # the run is in results/
        self.write_map([row()])
        self.write_run(junit(case("works"), case("nobody cites me")))
        self.assertIn("promise check: map: skipped (no JUnit results at map.junit yet", self.check().stdout)
        result = self.check("--fail-on-orphans")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("promise check: map: failed (--fail-on-orphans needs a test run: no JUnit results at "
                      "map.junit yet (result/unit.xml); run the tests first)", result.stdout)
        self.write_config({"version": 1, "map": dict(MAP_CONFIG, requireHomes=True, surfaces=[sys.executable, "-c",
                                                                                           "print('GET /me')"])})
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("promise check: map: failed (docs/capabilities/map.json joined to the entry-point list; "
                      "map.requireHomes needs a test run: no test run: pass --junit or set map.junit)", result.stdout)

    def test_a_config_slip_that_would_turn_a_gate_off_is_printed_and_fails(self) -> None:
        self.write_config({"version": 1, "map": dict(MAP_CONFIG, requireHomes="true",
                                                     junit=["results/unit.xml", "../../escape.xml"])})
        self.write_map([row()])
        self.write_run(junit(case("works"), case("nobody cites me")))
        result = self.check("--no-lint")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("promise check: warning: path escapes the project: map.junit (../../escape.xml)\n", result.stdout)
        self.assertIn("promise check: warning: map.requireHomes is not true or false\n", result.stdout)
        self.assertIn("promise check: map: failed (map.requireHomes is 'true', not true or false; "
                      "the gate it names cannot be read as on or off)", result.stdout)
        self.assertIn("path escapes the project", " ".join(self.check_json("--no-lint")["warnings"]))

    def test_a_map_junit_path_with_shell_syntax_is_left_out(self) -> None:
        self.write_config({"version": 1, "map": dict(MAP_CONFIG, junit=["results/unit.xml", "results/$(id).xml"])})
        self.write_map([row()])
        self.write_run(junit(case("works")))
        result = self.check("--no-lint")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("promise check: warning: map.junit holds", result.stdout)
        self.assertIn("promise check: map: ok (docs/capabilities/map.json joined to 1 run path)\n", result.stdout)

    def test_junit_is_read_from_the_project_root(self) -> None:
        self.write_config({"version": 1, "map": MAP_CONFIG})
        self.write_map([row()])
        self.write_run(junit(case("works")))
        with tempfile.TemporaryDirectory() as elsewhere:
            result = subprocess.run([sys.executable, str(CHECK), "--cwd", str(self.root), "--no-lint",
                                     "--junit", "results/unit.xml"], cwd=elsewhere, capture_output=True, text=True,
                                    encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("promise check: map: ok (docs/capabilities/map.json joined to 1 run path)", result.stdout)

    def test_map_file_wins_and_another_reader_needs_it(self) -> None:
        custom = dict(MAP_CONFIG, find="scripts/capability-find")
        self.write_config({"version": 1, "map": custom})
        self.write_map([row()], folder="registry")
        run = self.write_run(junit(case("works")))
        result = self.check("--junit", str(run))
        self.assertEqual(result.returncode, 1)
        self.assertIn("promise check: map: failed (map.file is not set and map.find is not the starter reader", result.stdout)
        self.write_config({"version": 1, "map": dict(custom, file="registry/map.json")})
        self.assertIn("promise check: map: ok (registry/map.json joined", self.check("--junit", str(run)).stdout)

    def test_the_starter_readers_own_map_flag_names_the_file(self) -> None:
        self.write_config({"version": 1, "map": dict(MAP_CONFIG, find="python3 tools/capability_find.py --map registry/rows.json")})
        (self.root / "registry").mkdir()
        (self.root / "registry" / "rows.json").write_text(json.dumps({"rows": [row()]}), encoding="utf-8")
        run = self.write_run(junit(case("works")))
        self.assertIn("promise check: map: ok (registry/rows.json joined", self.check("--junit", str(run)).stdout)

    def test_a_run_with_no_usable_map_fails_and_without_a_run_is_skipped(self) -> None:
        run = self.write_run(junit(case("works")))
        self.assertIn("promise check: map: failed (--junit needs a map, and the config has none)",
                      self.check("--junit", str(run)).stdout)
        self.write_config({"version": 1, "map": {"recipe": "r.md"}})
        self.assertIn("promise check: map: skipped (map incomplete: missing find, row, lanes)", self.check().stdout)
        result = self.check("--junit", str(run))
        self.assertEqual(result.returncode, 1)
        self.assertIn("promise check: map: failed (map incomplete: missing find, row, lanes)", result.stdout)

    def test_no_map_skips_the_step(self) -> None:
        self.write_config({"version": 1, "map": MAP_CONFIG})
        run = self.write_run(junit(case("works")))
        self.assertEqual(self.statuses("--junit", str(run), "--no-map")["map"], "skipped")

    def test_an_explicit_config_is_read_and_passed_to_the_report(self) -> None:
        config = self.root / "elsewhere.json"
        config.write_text(json.dumps({"version": 1, "map": MAP_CONFIG}), encoding="utf-8")
        self.write_map([row()])
        run = self.write_run(junit(case("works")))
        report = self.step("map", "--config", str(config), "--junit", str(run))
        self.assertEqual(report["status"], "ok")
        self.assertIn(str(config), report["argv"])


class SupersedesStillThere(Project):
    """A doc that replaced a legacy doc deletes it in its own commit, or cuts
    it to one line that names the doc (modes/backfill.md, modes/merge.md).
    check.py warns, and never fails, for each path still left behind."""

    LEGACY = "docs/design/MUTING.md"

    def supersede(self, value: str) -> None:
        doc = self.docs / "conforming.md"
        doc.write_text(doc.read_text(encoding="utf-8").replace("Supersedes: —", f"Supersedes: {value}", 1),
                       encoding="utf-8")

    def legacy(self, text: str, path: str = LEGACY) -> None:
        full = self.root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(text, encoding="utf-8")

    def warnings(self) -> list:
        return [w for w in self.check_json()["warnings"] if "Supersedes:" in w]

    def test_a_legacy_doc_still_whole_warns_and_does_not_fail(self) -> None:
        self.supersede(f"{self.LEGACY}, docs/design/GONE.md")
        self.legacy("# Muting\n\nThe old design.\n\nMore of it.\n")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("promise check: warning: docs/designs/conforming.md: Supersedes: names "
                      f"{self.LEGACY}, which still exists (3 lines): delete it in the doc's commit, "
                      "or cut it to one line that names conforming.md\n", result.stdout)
        self.assertEqual(len(self.warnings()), 1)

    def test_a_deleted_or_pointer_legacy_doc_is_quiet(self) -> None:
        self.supersede(f"`{self.LEGACY}`")
        self.assertEqual(self.warnings(), [])
        self.legacy("Moved to docs/designs/conforming.md.\n")
        self.assertEqual(self.warnings(), [])

    def test_a_pointer_that_names_another_doc_warns(self) -> None:
        self.supersede(self.LEGACY)
        self.legacy("See the wiki.\n")
        self.assertEqual(len(self.warnings()), 1)
        self.assertIn("its one line does not name conforming.md", self.warnings()[0])

    def test_a_folded_doc_marked_superseded_by_is_quiet(self) -> None:
        self.supersede("docs/designs/old-muting.md")
        text = CONFORMING.read_text(encoding="utf-8").replace(
            "Status: draft", "Status: superseded-by conforming.md", 1)
        self.legacy(text, "docs/designs/old-muting.md")
        self.assertEqual([w for w in self.warnings() if "old-muting.md" in w], [])

    def test_a_path_beside_the_doc_and_a_markdown_link_count(self) -> None:
        self.supersede("[old](old-muting.md)")
        self.legacy("# Old\n\nText.\n", "docs/designs/old-muting.md")
        self.assertEqual(len(self.warnings()), 1)
        self.assertIn("names old-muting.md, which still exists (2 lines)", self.warnings()[0])

    def test_the_docs_prescribe_the_shape_this_check_accepts(self) -> None:
        # The README and backfill's invariant 6 once kept the file whole with a
        # pointer line on top, which is the shape this check warns about.
        flat = {name: " ".join((REPO / name).read_text(encoding="utf-8").split())
                for name in ("README.md", "skills/promise/modes/backfill.md", "skills/promise/outcome-framework.md")}
        self.assertIn("If you keep it, it is cut to one line that points at the outcome doc", flat["README.md"])
        self.assertIn("On a no, it is cut, in the same commit, to one pointer line that names the outcome doc",
                      flat["skills/promise/modes/backfill.md"])
        self.assertIn("deletes it or cuts it to one line that names the new doc",
                      flat["skills/promise/outcome-framework.md"])
        for name, text in flat.items():
            self.assertNotIn("nothing else in it changes", text, name)
        self.supersede(self.LEGACY)
        self.legacy("Moved to docs/designs/conforming.md.\n")
        self.assertEqual(self.warnings(), [])
        self.legacy("Moved to docs/designs/conforming.md.\n\n# Muting\n\nThe old design.\n")
        self.assertEqual(len(self.warnings()), 1)

    def test_no_path_is_quiet(self) -> None:
        for value in ("—", "none", "the old muting doc"):
            with self.subTest(value=value):
                self.supersede(value)
                self.assertEqual(self.warnings(), [])
                shutil.copy(CONFORMING, self.docs / "conforming.md")


STARTER_READER = REPO / "skills" / "promise" / "templates" / "starter-map" / "capability_find.py"


class ChecksStep(Project):
    """map.checks -- the project's own checks of its map, such as the
    starter reader's --check -- run through adapter.py as part of the gate."""

    def setUp(self) -> None:
        super().setUp()
        reader = self.root / "docs" / "capabilities" / "capability_find.py"
        reader.parent.mkdir(parents=True)
        shutil.copy(STARTER_READER, reader)
        self.python = shlex.quote(sys.executable)

    def configure(self, checks: Any) -> None:
        self.write_config({"version": 1, "map": dict(MAP_CONFIG, checks=checks)})

    def test_a_broken_map_fails_the_checks_step(self) -> None:
        broken = dict(row(), doc="docs/nope.md")
        path = self.write_map([row(), dict(row()), broken])
        data = json.loads(path.read_text(encoding="utf-8"))
        data["leftOut"] = [{"test": "t/a.test.ts::helper"}]
        path.write_text(json.dumps(data), encoding="utf-8")
        self.configure([f"{self.python} docs/capabilities/capability_find.py --check"])
        result = self.check("--no-lint")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("duplicate id CAP-1", result.stdout)
        self.assertIn("doc docs/nope.md cannot be read", result.stdout)
        self.assertIn("leftOut[0]: reason must be one non-empty line", result.stdout)
        self.assertIn("promise check: checks: failed (map.checks[0] exited 1)", result.stdout)
        report = self.step("checks", "--no-lint")
        self.assertEqual(report["output"][0]["exit"], 1)
        self.assertEqual(report["argv"], [[sys.executable, "docs/capabilities/capability_find.py", "--check"]])

    def test_a_clean_map_passes_and_the_step_is_skipped_without_checks(self) -> None:
        self.write_map([row()])
        self.configure([f"{self.python} docs/capabilities/capability_find.py --check"])
        self.assertIn("promise check: checks: ok (1 command from map.checks)", self.check("--no-lint").stdout)
        self.configure([])
        self.assertIn("promise check: checks: skipped (map.checks is empty)", self.check("--no-lint").stdout)
        self.write_config({"version": 1, "map": MAP_CONFIG})
        self.assertIn("promise check: checks: skipped (map.checks is not configured)", self.check("--no-lint").stdout)
        self.assertEqual(self.statuses("--no-lint", "--no-map")["checks"], "skipped")
        self.configure([f"{self.python} docs/capabilities/capability_find.py --check"])
        self.assertEqual(self.statuses("--no-lint", "--no-map", "--map-checks")["checks"], "ok")

    def test_checks_run_in_order_as_argv_and_stop_at_the_first_failure(self) -> None:
        self.write_map([row()])
        self.configure([f"{self.python} -c \"open('first', 'w'); raise SystemExit(3)\"",
                        f"{self.python} -c \"open('second', 'w')\""])
        result = self.check("--no-lint")
        self.assertIn("promise check: checks: failed (map.checks[0] exited 3)", result.stdout)
        self.assertTrue((self.root / "first").exists())
        self.assertFalse((self.root / "second").exists())
        self.configure("not a list")
        self.assertIn("promise check: checks: failed (map.checks is not a list of commands)",
                      self.check("--no-lint").stdout)


class GateStep(Project):
    """A shipped doc's §6 line that did not go red and has no Kill line must
    cite a row with origin backfill and verdict proven (tests/test_kill_record.py
    covers the Kill lines). The lint sees only a line with no Row, so
    check.py runs bridge_validate.py on each such doc, with or without
    --no-map, and the Action runs it too. The C4 repro: the minimap doc,
    typed shipped with no Red gate line over rows that are not built, used
    to pass the lint and check.py."""

    MINIMAP = REPO / "examples" / "minimap"

    def setUp(self) -> None:
        super().setUp()
        shutil.copytree(self.MINIMAP, self.root, dirs_exist_ok=True)
        config_path = self.root / "promise.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        exe = shlex.quote(sys.executable)
        for key in ("find", "row", "nextId"):
            config["map"][key] = config["map"][key].replace("python3 ", exe + " ", 1)
        config["map"]["checks"] = [c.replace("python3 ", exe + " ", 1) for c in config["map"]["checks"]]
        config_path.write_text(json.dumps(config), encoding="utf-8")
        self.doc = self.docs / "channel-muting.md"
        text = self.doc.read_text(encoding="utf-8")
        self.doc.write_text(text.replace("Status: agreed\n", "Status: " + "shipped\n", 1), encoding="utf-8")

    def prove_rows(self, origin: str = "backfill") -> None:
        path = self.root / "map.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data["rows"][:2]:
            row.update(origin=origin, verdict="proven")
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_a_shipped_doc_over_rows_not_built_fails_the_gate_and_passes_the_lint(self) -> None:
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("promise check: lint: ok (docs/designs)", result.stdout)
        self.assertEqual(result.stdout.count("SHIPPED_WITHOUT_GATE"), 3)
        self.assertIn("promise check: gate: failed (docs/designs/channel-muting.md: bridge_validate.py found "
                      "an error)", result.stdout)
        gate = self.step("gate")
        self.assertEqual(gate["argv"], [[sys.executable, str(SCRIPTS_DIR / "bridge_validate.py"),
                                         "docs/designs/channel-muting.md", "--json"]])
        rules = [f["rule"] for f in gate["output"][0]["findings"]]
        self.assertEqual(rules.count("SHIPPED_WITHOUT_GATE"), 3)

    def test_no_map_does_not_skip_the_gate(self) -> None:
        self.assertEqual(self.check("--no-map").returncode, 1)
        self.assertEqual(self.statuses("--no-map")["gate"], "failed")
        self.prove_rows(origin="doc")
        self.assertEqual(self.statuses("--no-map")["gate"], "failed")

    def test_every_row_a_proven_backfilled_row_passes(self) -> None:
        self.prove_rows()
        result = self.check("--no-map")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("promise check: gate: ok (1 shipped doc with a §6 line no red run or Kill line covers: "
                      "each such line cites a proven backfilled row)", result.stdout)

    def test_a_red_gate_line_is_not_a_skipped_gate(self) -> None:
        text = self.doc.read_text(encoding="utf-8")
        self.doc.write_text(text.replace("Supersedes: —\n", "Supersedes: —\nRed gate: a1b2c3d 2026-01-02\n", 1),
                            encoding="utf-8")
        self.assertIn("promise check: gate: skipped (no shipped doc has a §6 line that needs a proven backfilled row)", self.check().stdout)

    def test_with_no_usable_map_the_gate_fails(self) -> None:
        # with no map, typed Row cells satisfy the lint but no row can be a
        # proven backfilled row: the doc needs its Red gate line
        config_path = self.root / "promise.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        for value, status, reason in (
            (None, "failed", "1 shipped doc with a §6 line no red run or Kill line covers, and no map configured: "
                             "no row can be a proven backfilled row, so each such line needs a red run or a Kill line"),
            (False, "failed", "1 shipped doc with a §6 line no red run or Kill line covers, and map is false: this project keeps "
                              "no map, on purpose: no row can be a proven backfilled row"),
            ({"find": "x"}, "failed", "1 shipped doc with a §6 line no red run or Kill line covers, and map incomplete"),
        ):
            with self.subTest(map=value):
                config_path.write_text(json.dumps(dict(config, map=value)), encoding="utf-8")
                gate = self.step("gate")
                self.assertEqual(gate["status"], status)
                self.assertTrue(gate["reason"].startswith(reason), gate["reason"])

    def test_another_config_is_not_read_by_the_gate(self) -> None:
        other = self.root / "other.json"
        shutil.copy(self.root / "promise.config.json", other)
        gate = self.step("gate", "--config", str(other))
        self.assertEqual(gate["status"], "failed")
        self.assertIn("reads only the project's own config, not --config", gate["reason"])
        self.assertEqual(self.step("gate", "--config", str(self.root / "promise.config.json"))["status"], "failed")
        self.prove_rows()
        self.assertEqual(self.step("gate", "--config", str(self.root / "promise.config.json"))["status"], "ok")


LISTER = """import sys
sys.stdout.write(open("entry-points.txt", encoding="utf-8").read())
sys.stderr.write(open("lister-stderr.txt", encoding="utf-8").read() if len(sys.argv) > 1 else "")
sys.exit(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
"""


class SurfacesStep(Project):
    """The entry-point command (map.surfaces or --surfaces-cmd) runs as argv
    from the project root; its list joins the map with or without a run."""

    def setUp(self) -> None:
        super().setUp()
        (self.root / "lister.py").write_text(LISTER, encoding="utf-8")
        self.points("GET /me", "GET /admin", "# a comment", "")
        self.write_map([dict(row(), surfaces=["GET /me"])])

    def points(self, *lines: str) -> None:
        (self.root / "entry-points.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def configure(self, surfaces: Any = None, **extra: Any) -> None:
        if surfaces is None:
            surfaces = [sys.executable, "lister.py"]
        self.write_config({"version": 1, "map": dict(MAP_CONFIG, surfaces=surfaces, **extra)})

    def test_an_argv_array_from_the_config_joins_the_map_without_a_run(self) -> None:
        self.configure()
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("promise check: surfaces: ok (2 entry points from map.surfaces)\n", result.stdout)
        self.assertIn("promise check: map: ok (docs/capabilities/map.json joined to the entry-point list)",
                      result.stdout)
        self.assertIn("Entry points with no row (1)", result.stdout)
        self.assertIn("1 entry point has no row", result.stdout)
        self.assertNotIn("# a comment", result.stdout)
        surfaces = self.step("surfaces")
        self.assertEqual(surfaces["output"], ["GET /me", "GET /admin"])
        self.assertEqual(surfaces["argv"], [sys.executable, "lister.py"])
        report = self.step("map")
        self.assertIn("--surfaces", report["argv"])
        self.assertNotIn("--strict", report["argv"])
        self.assertEqual(report["output"]["unmappedSurfaces"], ["GET /admin"])

    def test_fail_on_unmapped_fails_the_map_step(self) -> None:
        self.configure()
        result = self.check("--fail-on-unmapped")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("promise check: map: failed (docs/capabilities/map.json joined to the entry-point list: exit 1)",
                      result.stdout)
        self.points("GET /me")
        self.assertEqual(self.check("--fail-on-unmapped").returncode, 0)

    def test_require_homes_turns_on_both_gates(self) -> None:
        self.configure(requireHomes=True)
        run = self.write_run(junit(case("works"), case("nobody cites me")))
        report = self.step("map", "--junit", str(run))
        self.assertEqual(report["status"], "failed")
        for flag in ("--strict", "--fail-on-orphans", "--fail-on-unmapped"):
            self.assertIn(flag, report["argv"])
        self.assertIn("map.json joined to 1 run path and the entry-point list", report["reason"])
        self.assertEqual(report["output"]["summary"]["orphanCount"], 1)

    def test_require_homes_without_a_run_checks_entry_points_and_fails_for_want_of_one(self) -> None:
        self.configure(requireHomes=True)
        self.points("GET /me")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Entry points with no row (0)", result.stdout)
        self.assertIn("map.requireHomes needs a test run: no test run: pass --junit or set map.junit", result.stdout)

    def test_a_byte_order_mark_is_not_part_of_the_first_entry_point(self) -> None:
        (self.root / "entry-points.txt").write_bytes(
            b"\xef\xbb\xbfGET /me\r\n\r\n   \r\nGET /me\r\n# comment\r\nPOST /x\r\n")
        self.configure()
        self.assertIn("promise check: surfaces: ok (2 entry points from map.surfaces)", self.check().stdout)
        self.assertEqual(self.step("surfaces")["output"], ["GET /me", "POST /x"])

    def test_the_flag_overrides_the_config_and_a_string_is_split_like_other_commands(self) -> None:
        self.configure(surfaces="does-not-exist-lister")
        self.points("GET /me")
        result = self.check("--surfaces-cmd", f"{shlex.quote(sys.executable)} lister.py")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("promise check: surfaces: ok (1 entry point from --surfaces-cmd)", result.stdout)
        self.configure(surfaces=f"{shlex.quote(sys.executable)} lister.py")
        self.assertIn("promise check: surfaces: ok (1 entry point from map.surfaces)", self.check().stdout)

    def test_a_failing_command_fails_the_step_and_quotes_its_stderr(self) -> None:
        self.configure(surfaces=[sys.executable, "lister.py", "3"])
        (self.root / "lister-stderr.txt").write_text("reading routes\ncannot read the router\n", encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn('promise check: surfaces: failed (map.surfaces exited 3: "cannot read the router")', result.stdout)
        self.assertIn("reading routes\n", result.stdout)
        self.assertNotIn("GET /admin", result.stdout, "the list goes to the report, not the log")
        self.assertIn("promise check: map: skipped (no test run: pass --junit or set map.junit)", result.stdout)

    def test_an_empty_list_a_missing_program_or_a_bad_config_value_fails(self) -> None:
        self.points("# nothing yet", "")
        self.configure()
        self.assertIn("promise check: surfaces: failed (map.surfaces printed no entry points; an empty list "
                      "proves nothing)", self.check().stdout)
        self.configure(surfaces=["does-not-exist-lister"])
        self.assertIn('promise check: surfaces: failed (map.surfaces did not finish: "cannot run does-not-exist-lister',
                      self.check().stdout)
        self.configure(surfaces=["node", 3])
        self.assertIn("promise check: surfaces: failed (map.surfaces: configured command is not a non-empty array "
                      "of strings", self.check().stdout)
        self.configure(surfaces="lister 'unclosed")
        self.assertIn("promise check: surfaces: failed (map.surfaces: could not parse configured command",
                      self.check().stdout)

    def test_asking_for_the_check_with_no_command_fails(self) -> None:
        self.write_config({"version": 1, "map": MAP_CONFIG})
        self.assertIn("promise check: surfaces: failed (--fail-on-unmapped needs an entry-point command",
                      self.check("--fail-on-unmapped").stdout)
        self.write_config({"version": 1, "map": dict(MAP_CONFIG, requireHomes=True)})
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("promise check: surfaces: failed (map.requireHomes needs map.surfaces", result.stdout)

    def test_no_map_skips_the_command_and_no_config_map_fails_the_flag(self) -> None:
        self.configure(surfaces=[sys.executable, "-c", "open('ran', 'w')"])
        self.assertEqual(self.statuses("--no-map")["surfaces"], "skipped")
        self.assertFalse((self.root / "ran").exists())
        (self.root / ".claude" / "promise.config.json").unlink()
        result = self.check("--surfaces-cmd", f"{shlex.quote(sys.executable)} lister.py")
        self.assertEqual(result.returncode, 1)
        self.assertIn("promise check: map: failed (--surfaces-cmd needs a map, and the config has none)", result.stdout)

    def test_the_command_never_goes_through_a_shell(self) -> None:
        if shutil.which("echo") is None:
            self.skipTest("echo is not available")
        self.configure(surfaces="echo $(touch pwned) `touch pwned2`")
        result = self.check()
        self.assertFalse((self.root / "pwned").exists())
        self.assertFalse((self.root / "pwned2").exists())
        self.assertIn("promise check: surfaces: ok (1 entry point from map.surfaces)", result.stdout)
        self.assertEqual(self.step("surfaces")["output"], ["$(touch pwned) `touch pwned2`"])

    def test_a_command_that_runs_too_long_is_stopped(self) -> None:
        sys.path.insert(0, str(SCRIPTS_DIR))
        self.addCleanup(sys.path.remove, str(SCRIPTS_DIR))
        import check  # noqa: E402

        run = check.run_command([sys.executable, "-c", "import time; time.sleep(10)"], str(self.root), timeout=0.5)
        self.assertIsNone(run["exit"])
        self.assertIn("timed out after 0.5s", run["stderr"])
        self.assertEqual(check.SURFACES_TIMEOUT, 300)


class ActionShell(Project):
    """The Action's own `run:` block, run with bash: same inputs, same
    behaviour -- lint the folder, §0 against a base when there is one, no map
    step."""

    def action(self, docs_home: str = "docs/designs", base: str = "", lint: str = "true",
               extra_env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
        text = ACTION.read_text(encoding="utf-8")
        body = text.split("      run: |\n", 1)[1]
        script = "\n".join(line[8:] for line in body.splitlines())
        env = dict(os.environ, DOCS_HOME=docs_home, BASE_REF=base, RUN_LINT=lint, SCRIPTS=str(SCRIPTS_DIR))
        for key in ("GITHUB_BASE_REF", "GITHUB_ACTIONS", "GITHUB_EVENT_PATH", "RUN_TINY_CHECK"):
            env.pop(key, None)
        env.update(extra_env or {})
        return subprocess.run(["bash", "-c", script], cwd=str(self.root), capture_output=True,
                              text=True, encoding="utf-8", env=env)

    def setUp(self) -> None:
        if shutil.which("bash") is None:
            self.skipTest("bash is not available")
        super().setUp()

    def test_lint_and_section0_run_and_the_map_step_does_not(self) -> None:
        self.write_config({"version": 1, "map": dict(MAP_CONFIG, junit="results/unit.xml")})
        self.write_run(junit(case("works")))
        result = self.action(base="HEAD")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("promise check: lint: ok (docs/designs)", result.stdout)
        self.assertIn("promise check: §0: ok (docs/designs against HEAD)", result.stdout)
        self.assertIn("promise check: surfaces: skipped (--no-map)", result.stdout)
        self.assertIn("promise check: map: skipped (--no-map)", result.stdout)

    def test_the_action_fails_a_shipped_doc_that_skipped_the_red_gate(self) -> None:
        shutil.copytree(GateStep.MINIMAP, self.root, dirs_exist_ok=True)
        config_path = self.root / "promise.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["map"]["row"] = config["map"]["row"].replace("python3 ", shlex.quote(sys.executable) + " ", 1)
        config_path.write_text(json.dumps(config), encoding="utf-8")
        doc = self.docs / "channel-muting.md"
        doc.write_text(doc.read_text(encoding="utf-8").replace("Status: agreed\n", "Status: " + "shipped\n", 1),
                       encoding="utf-8")
        result = self.action()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("promise check: lint: ok (docs/designs)", result.stdout)
        self.assertIn("SHIPPED_WITHOUT_GATE", result.stdout)
        self.assertIn("promise check: gate: failed (docs/designs/channel-muting.md", result.stdout)

    def test_the_inputs_still_mean_what_they_did(self) -> None:
        text = CONFORMING.read_text(encoding="utf-8").replace("Status: draft", "Status: someday", 1)
        (self.docs / "conforming.md").write_text(text, encoding="utf-8")
        self.assertEqual(self.action().returncode, 1)
        skipped = self.action(lint="false")
        self.assertEqual(skipped.returncode, 0, skipped.stdout)
        self.assertIn("promise check: lint: skipped (--no-lint)", skipped.stdout)
        self.assertIn("promise check: §0: skipped (no --base)", skipped.stdout)
        missing = self.action(docs_home="docs/nowhere", base="HEAD")
        self.assertEqual(missing.returncode, 0, missing.stdout + missing.stderr)
        self.assertIn("promise check: lint: skipped (no folder docs/nowhere)", missing.stdout)

    def test_with_no_docs_home_input_it_lints_the_folder_the_config_names(self) -> None:
        # the same folder a local check.py run with no flag lints
        promises = self.root / "docs" / "promises"
        promises.mkdir(parents=True)
        text = CONFORMING.read_text(encoding="utf-8").replace("Status: draft", "Status: someday", 1)
        (promises / "broken.md").write_text(text, encoding="utf-8")
        self.write_config({"version": 1, "docsHome": "docs/promises"})
        local = self.check("--no-map")
        result = self.action(docs_home="")
        self.assertEqual((result.returncode, local.returncode), (1, 1), result.stdout + result.stderr)
        self.assertIn("promise check: lint: failed (docs/promises", result.stdout)
        self.assertIn("promise check: lint: failed (docs/promises", local.stdout)


    def test_a_body_sized_tiny_that_touches_a_protected_path_fails_with_the_input_on(self) -> None:
        self.write_config({"version": 1, "protectedPaths": ["billing/"]})
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "config")
        (self.root / "billing").mkdir()
        (self.root / "billing" / "charge.ts").write_text("x\n", encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "change")
        event = self.root / ".git" / "event.json"  # outside the tree the change is read from
        event.write_text(json.dumps({"pull_request": {"body": "## Why\n\nSize: tiny — a refactor.\n"}}),
                         encoding="utf-8")
        tiny = {"RUN_TINY_CHECK": "true", "GITHUB_EVENT_PATH": str(event)}
        result = self.action(base="HEAD~1", extra_env=tiny)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("sized tiny, but touches billing/charge.ts (protected: billing/)", result.stderr)
        self.assertEqual(self.action(base="HEAD~1").returncode, 0, "off by default")
        event.write_text(json.dumps({"pull_request": {"body": "## Why\n\nSize: risky — it charges.\n"}}),
                         encoding="utf-8")
        self.assertEqual(self.action(base="HEAD~1", extra_env=tiny).returncode, 0)


class NoShell(unittest.TestCase):
    def test_every_sibling_runs_as_an_argv_list_with_this_interpreter(self) -> None:
        source = CHECK.read_text(encoding="utf-8")
        self.assertNotIn("shell=True", source)
        self.assertNotIn("os.system", source)
        self.assertRegex(source, re.escape("argv = [sys.executable, os.path.join(_SCRIPTS_DIR, script), *args]"))


if __name__ == "__main__":
    unittest.main()


class ReviewRegressions(unittest.TestCase):
    """A misspelt --docs-home skipped lint, §0 and the gate and passed every run."""

    def test_a_docs_home_that_is_not_a_folder_is_named_as_a_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "docs" / "designs").mkdir(parents=True)
            result = subprocess.run([sys.executable, str(CHECK), "--cwd", tmp, "--docs-home", "docs/design"],
                                    capture_output=True, text=True)
            self.assertIn("warning: docs home 'docs/design' is not a folder", result.stdout)
            ok = subprocess.run([sys.executable, str(CHECK), "--cwd", tmp, "--docs-home", "docs/designs"],
                                capture_output=True, text=True)
            self.assertNotIn("is not a folder", ok.stdout)
