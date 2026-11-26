"""Tests for the promise skill's bridge_validate.py script.

Run from the repo root:

    python3 -m unittest discover -s tests -v

Mirrors test_adapter_render.py's own conventions: scripts and fixtures are
located relative to this file, not the current working directory, and
bridge_validate.py is exercised as a real subprocess (argv, stdout, stderr,
exit code) — never imported and called in-process, except where the
sibling-module ``normalize()`` helper itself is worth a direct unit check.
Fixtures live under fixtures/bridge/: agreed_bridged.md is the conforming
doc, bridged, with one deliberately drifted row; each other .md fixture is
agreed_bridged.md with exactly one further change, named after the rule it
trips. fake_row.py stands in for a project's `map.row` command.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures" / "bridge"
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"

BRIDGE = SCRIPTS_DIR / "bridge_validate.py"
LINT = SCRIPTS_DIR / "lint_outcome.py"
FAKE_ROW = FIXTURES_DIR / "fake_row.py"

# A Row cell carrying every shell metacharacter that would matter if it were
# ever composed into a shell command instead of passed as one argv element.
HOSTILE_ROW = 'R1"; echo PWNED; $(echo X) `whoami`'

FIXTURE_NAMES = (
    "agreed_bridged.md",
    "agreed_missing_row.md",
    "agreed_bad_row_id.md",
    "agreed_no_snapshot.md",
    "draft_unbridged.md",
)


def run(
    *args: str, cwd: Optional[str] = None, env: Optional[Dict[str, str]] = None
) -> subprocess.CompletedProcess:
    """Run bridge_validate.py as a real subprocess. `env`, when given, is
    merged onto a copy of this process's own environment (never replaces it
    outright) — so FAKE_ROW_LOG reaches fake_row.py at the bottom of the
    real bridge_validate.py -> adapter.py -> fake_row.py chain, since none
    of the three subprocess calls in that chain override `env` themselves."""
    full_env = {**os.environ, **env} if env is not None else None
    return subprocess.run(
        [sys.executable, str(BRIDGE), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=full_env,
    )


def run_json(
    *args: str, env: Optional[Dict[str, str]] = None
) -> Tuple[subprocess.CompletedProcess, dict]:
    result = run(*args, env=env)
    data = json.loads(result.stdout) if result.stdout.strip() else None
    return result, data


def read_invocation_log(path: Path) -> List[list]:
    """Every fake_row.py invocation logged to `path` (FAKE_ROW_LOG), as a
    list of argv lists, in call order. Empty when fake_row.py was never
    actually invoked (the file is never created otherwise)."""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_config(project_dir: Path, config: dict) -> None:
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    (claude_dir / "promise.config.json").write_text(json.dumps(config), encoding="utf-8")


def fixture_command(name: str, *extra_args: str) -> str:
    """A shlex-safe ``<python3> <abs path to fixtures/bridge/name>`` string."""
    parts = [shlex.quote(sys.executable), shlex.quote(str(FIXTURES_DIR / name))]
    parts.extend(shlex.quote(a) for a in extra_args)
    return " ".join(parts)


def bridged_project(project_dir: Path, row_id_pattern: Optional[str] = r"^R\d+$", with_row: bool = True) -> Path:
    """A temp project dir whose map orient reports as usable (recipe, find,
    row strings; lanes an object of strings) and whose map.row runs
    fake_row.py. ``with_row=False`` leaves map.row an empty string — still
    a string, so the map stays usable, but no command is configured."""
    map_value = {
        "recipe": "docs/how-to/adding-a-row.md",
        "find": fixture_command("fake_row.py"),
        "row": fixture_command("fake_row.py") if with_row else "",
        "lanes": {"data": "tests[]"},
    }
    if row_id_pattern is not None:
        map_value["rowIdPattern"] = row_id_pattern
    write_config(project_dir, {"map": map_value})
    return project_dir


class ScriptExistsTests(unittest.TestCase):
    def test_script_exists(self) -> None:
        self.assertTrue(BRIDGE.is_file())

    def test_help_works_and_exits_zero(self) -> None:
        result = run("-h")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage", result.stdout.lower())


class FixturesExistTests(unittest.TestCase):
    def test_every_fixture_exists(self) -> None:
        for name in (*FIXTURE_NAMES, "fake_row.py"):
            self.assertTrue((FIXTURES_DIR / name).is_file(), f"missing fixture: {name}")

    def test_agreed_bridged_lints_clean(self) -> None:
        result = subprocess.run(
            [sys.executable, str(LINT), str(FIXTURES_DIR / "agreed_bridged.md"), "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["stats"], {"errors": 0, "warnings": 0, "total": 0})


class RuleIsolationTests(unittest.TestCase):
    """Each fixture trips exactly its own rule, as an error, and no other
    error-severity rule fires alongside it. Every fixture here is `agreed`
    with AT-3 mapped to R2, whose map text is deliberately reworded (see
    fake_row.py) — so THEN_NOT_IN_MAP (a warning, never an error) is
    expected to co-occur in every case and is asserted on its own below."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = bridged_project(Path(self._tmp.name))

    def error_rules(self, filename: str) -> Tuple[subprocess.CompletedProcess, dict, list]:
        result, data = run_json(str(FIXTURES_DIR / filename), "--cwd", str(self.project), "--json")
        self.assertIsNotNone(data, result.stdout + result.stderr)
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        return result, data, error_rules

    def test_agreed_bridged_has_no_error(self) -> None:
        result, data, error_rules = self.error_rules("agreed_bridged.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(error_rules, [])
        self.assertEqual(data["status"], "agreed")
        self.assertTrue(data["bridged"])
        self.assertTrue(data["mapConfigured"])

    def test_missing_row_trips_only_row_missing(self) -> None:
        result, _, error_rules = self.error_rules("agreed_missing_row.md")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(error_rules, ["ROW_MISSING"])

    def test_bad_row_id_trips_only_row_id_format(self) -> None:
        result, _, error_rules = self.error_rules("agreed_bad_row_id.md")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(error_rules, ["ROW_ID_FORMAT"])

    def test_bad_row_id_is_never_looked_up(self) -> None:
        # A malformed id must never reach ROW_NOT_FOUND/THEN_NOT_IN_MAP —
        # bridge_validate.py must not attempt a lookup for an id it has
        # already rejected on shape.
        _, data, _ = self.error_rules("agreed_bad_row_id.md")
        bad_row = next(r for r in data["rows"] if r["row"] == "R1x")
        self.assertIsNone(bad_row["found"])
        self.assertIsNone(bad_row["inSync"])

    def test_no_snapshot_trips_only_snapshot_line_missing(self) -> None:
        result, _, error_rules = self.error_rules("agreed_no_snapshot.md")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(error_rules, ["SNAPSHOT_LINE_MISSING"])

    def test_draft_is_not_bridged_and_runs_no_other_check(self) -> None:
        result, data, error_rules = self.error_rules("draft_unbridged.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(error_rules, [])
        self.assertEqual(data["status"], "draft")
        self.assertFalse(data["bridged"])
        self.assertTrue(data["mapConfigured"])
        self.assertEqual(data["rows"], [])
        self.assertEqual([f["rule"] for f in data["findings"]], ["NOT_BRIDGED"])
        self.assertEqual(data["findings"][0]["severity"], "info")


class DriftTests(unittest.TestCase):
    """THEN_NOT_IN_MAP: AT-3's Then no longer appears in R2's current text."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = bridged_project(Path(self._tmp.name))

    def test_drift_is_a_warning_and_exits_zero(self) -> None:
        result, data = run_json(
            str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        drift = [f for f in data["findings"] if f["rule"] == "THEN_NOT_IN_MAP"]
        self.assertEqual(len(drift), 1)
        self.assertEqual(drift[0]["severity"], "warn")
        self.assertEqual(data["stats"]["drifted"], 1)
        self.assertEqual(data["stats"]["mapped"], 3)
        self.assertEqual(data["stats"]["rows"], 3)

    def test_strict_promotes_drift_to_error_and_exits_one(self) -> None:
        result, data = run_json(
            str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json", "--strict"
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        drift = [f for f in data["findings"] if f["rule"] == "THEN_NOT_IN_MAP"]
        self.assertEqual(drift[0]["severity"], "error")

    def test_row_found_and_in_sync_per_row(self) -> None:
        _, data = run_json(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json")
        by_id = {r["id"]: r for r in data["rows"]}
        self.assertTrue(by_id["AT-1"]["found"])
        self.assertTrue(by_id["AT-1"]["inSync"])
        self.assertTrue(by_id["AT-2"]["found"])
        self.assertTrue(by_id["AT-2"]["inSync"])
        self.assertTrue(by_id["AT-3"]["found"])
        self.assertFalse(by_id["AT-3"]["inSync"])

    def test_drift_message_names_all_three_causes(self) -> None:
        # The check is symmetric: it cannot tell a map that moved on from
        # a §6 cell edited after the snapshot, so the message must name
        # both, or it misdirects the reader to the map every time.
        _, data = run_json(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json")
        drift = next(f for f in data["findings"] if f["rule"] == "THEN_NOT_IN_MAP")
        self.assertIn("the map has moved on", drift["message"])
        self.assertIn("filed differently", drift["message"])
        self.assertIn("§6 was edited after the snapshot", drift["message"])

    def test_adapter_called_once_per_distinct_row_id(self) -> None:
        # R1 covers both AT-1 and AT-2; a correct cache calls fake_row.py
        # once for R1 and once for R2, never twice for the same id. Proven
        # through fake_row.py's own invocation log, written by the real
        # bridge_validate.py -> adapter.py -> fake_row.py chain — not from
        # output text (mapped/drifted counts) that a duplicate lookup would
        # not change either way, so could pass even with a broken cache.
        log_path = self.project / "fake_row.log"
        result = run(
            str(FIXTURES_DIR / "agreed_bridged.md"),
            "--cwd", str(self.project),
            env={"FAKE_ROW_LOG": str(log_path)},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        invocations = read_invocation_log(log_path)
        row_ids = [argv[-1] for argv in invocations]
        # Exactly one invocation each for R1 and R2 -- a broken cache would
        # invoke R1 twice (once for AT-1, once for AT-2), giving three
        # entries, which sorted(row_ids) == ["R1", "R2"] would catch.
        self.assertEqual(sorted(row_ids), ["R1", "R2"], row_ids)


class ExactLinkTests(unittest.TestCase):
    """The link rule arm follows (modes/arm.md): a §6 line matches a row only
    when its Then equals one scenario's then, case and whitespace aside, and
    that scenario's altitude equals the line's Altitude. fake_row.py prints
    each row as JSON with its scenarios, as the starter map does."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = bridged_project(Path(self._tmp.name))

    def doc_with(self, at_id: str, then: Optional[str] = None, altitude: Optional[str] = None) -> Path:
        """agreed_bridged.md with one AT line's Then and/or Altitude cell changed."""
        base = (FIXTURES_DIR / "agreed_bridged.md").read_text(encoding="utf-8")
        out = []
        for line in base.splitlines(keepends=True):
            if line.startswith(f"| {at_id} |"):
                cells = line.rstrip("\n").split(" | ")
                # | AT-n | Given | When | Then | Altitude | Row |
                if then is not None:
                    cells[3] = then
                if altitude is not None:
                    cells[4] = altitude
                line = " | ".join(cells) + "\n"
            out.append(line)
        text = "".join(out)
        self.assertNotEqual(text, base)
        path = self.project / "doc.md"
        path.write_text(text, encoding="utf-8")
        return path

    def check(self, doc: Path, *extra: str, env: Optional[Dict[str, str]] = None):
        result, data = run_json(str(doc), "--cwd", str(self.project), "--json", *extra, env=env)
        self.assertIsNotNone(data, result.stdout + result.stderr)
        by_rule: Dict[str, list] = {}
        for f in data["findings"]:
            by_rule.setdefault(f["rule"], []).append(f)
        return result, data, by_rule

    def test_every_row_is_checked_exactly_when_the_map_prints_json(self) -> None:
        _, data, by_rule = self.check(FIXTURES_DIR / "agreed_bridged.md")
        self.assertEqual([r["exact"] for r in data["rows"]], [True, True, True])
        self.assertNotIn("ROW_TEXT_ONLY", by_rule)
        self.assertEqual(len(by_rule["THEN_NOT_IN_MAP"]), 1)  # AT-3, the fixture's known drift

    def test_case_and_whitespace_aside_the_then_links(self) -> None:
        doc = self.doc_with("AT-1", then="She gets  no push or badge FROM it")
        _, data, by_rule = self.check(doc)
        at1 = next(r for r in data["rows"] if r["id"] == "AT-1")
        self.assertTrue(at1["inSync"])
        self.assertEqual([f["line"] for f in by_rule["THEN_NOT_IN_MAP"]], [81])  # AT-3 only

    def test_part_of_a_scenario_is_not_a_link(self) -> None:
        # The substring check read this as in sync: "no push" occurs inside
        # R1's first scenario. An exact link needs the whole sentence.
        doc = self.doc_with("AT-1", then="no push")
        result, data, by_rule = self.check(doc)
        at1 = next(r for r in data["rows"] if r["id"] == "AT-1")
        self.assertFalse(at1["inSync"])
        self.assertEqual(sorted(f["line"] for f in by_rule["THEN_NOT_IN_MAP"]), [79, 81])
        self.assertEqual(result.returncode, 0)  # drift is a warning on an ordinary run

    def test_a_then_at_another_altitude_is_not_a_link(self) -> None:
        # The C2 repro: the Then text matches, the altitude does not. A
        # perception promise must never link to a row that proves it at
        # response altitude.
        doc = self.doc_with("AT-1", altitude="response")
        result, data, by_rule = self.check(doc)
        self.assertEqual(result.returncode, 0, result.stdout)
        at1 = next(r for r in data["rows"] if r["id"] == "AT-1")
        self.assertFalse(at1["inSync"])
        [finding] = by_rule["ALTITUDE_NOT_IN_MAP"]
        self.assertEqual((finding["line"], finding["severity"]), (79, "warn"))
        self.assertIn("at altitude perception, not response", finding["message"])
        self.assertEqual(data["stats"]["drifted"], 2)

    def test_a_table_with_no_altitude_column_is_not_drift(self) -> None:
        # An older doc: ALTITUDE_MISSING is a lint warning so that it keeps
        # linting. With no Altitude to compare, a line whose Then is exact is
        # in sync, and --strict passes as it did before the altitude compare.
        base = (FIXTURES_DIR / "agreed_bridged.md").read_text(encoding="utf-8")
        out = []
        for line in base.splitlines(keepends=True):
            cells = line.rstrip("\n").split("|")
            if line.startswith("|") and len(cells) == 8:  # the §6 table: drop the Altitude column
                del cells[5]
                line = "|".join(cells) + "\n"
            out.append(line)
        doc = self.project / "doc.md"
        doc.write_text("".join(out), encoding="utf-8")
        self.assertIn("| AT-1 | Ana is in a channel | she mutes it | she gets no push or badge from it | R1 |",
                      doc.read_text(encoding="utf-8"))
        result, data, by_rule = self.check(doc, "--strict")
        self.assertNotIn("ALTITUDE_NOT_IN_MAP", by_rule)
        self.assertEqual([r["inSync"] for r in data["rows"]], [True, True, False])  # AT-3: the known drift
        self.assertEqual(data["stats"]["drifted"], 1)
        [missing] = by_rule["ALTITUDE_MISSING"]
        self.assertEqual(missing["severity"], "info")
        self.assertIn("no Altitude for AT-1, AT-2, so", missing["message"])  # AT-3's Then matched nothing
        self.assertEqual(result.returncode, 1)  # AT-3's Then, under --strict
        self.assertEqual(sorted(by_rule), ["ALTITUDE_MISSING", "THEN_NOT_IN_MAP"])
        # AT-3 in sync too: --strict passes, and --linking does not link a line with no altitude
        doc.write_text("".join(out).replace("| Ben is still notified normally |", "| a second, unmuted member "
                                            "keeps getting a push for every new message in the channel |"),
                       encoding="utf-8")
        result, data, by_rule = self.check(doc, "--strict")
        self.assertEqual((result.returncode, data["stats"]["drifted"]), (0, 0), result.stdout)
        self.assertIn("no Altitude for AT-1, AT-2, AT-3, so", by_rule["ALTITUDE_MISSING"][0]["message"])
        result, data, by_rule = self.check(doc, "--linking")
        self.assertEqual((result.returncode, by_rule["ALTITUDE_MISSING"][0]["severity"]), (1, "error"))

    def test_linking_makes_a_wrong_link_an_error(self) -> None:
        doc = self.doc_with("AT-1", altitude="response")
        result, data, by_rule = self.check(doc, "--linking")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(by_rule["ALTITUDE_NOT_IN_MAP"][0]["severity"], "error")
        self.assertEqual(by_rule["THEN_NOT_IN_MAP"][0]["severity"], "error")
        # --linking touches only the link rules: a config warning stays a warning
        project = bridged_project(self.project, row_id_pattern=None)
        result, data = run_json(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(project), "--json", "--linking")
        severities = {f["rule"]: f["severity"] for f in data["findings"]}
        self.assertEqual(severities["NO_ROW_ID_PATTERN"], "warn")
        self.assertEqual(severities["THEN_NOT_IN_MAP"], "error")

    def test_an_escaped_pipe_in_the_cell_equals_the_pipe_in_the_map(self) -> None:
        # R3's then holds `mute <channel|all>`; in a §6 cell that pipe is
        # written \| (GitHub splits a cell at any other pipe, in a code span too).
        base = (FIXTURES_DIR / "agreed_bridged.md").read_text(encoding="utf-8")
        old_line = "| Ben is still notified normally | perception | R2 |"
        self.assertIn(old_line, base)
        doc = self.project / "doc.md"
        doc.write_text(
            base.replace(old_line, "| the usage line reads `mute <channel\\|all>` | response | R3 |"),
            encoding="utf-8",
        )
        _, data, by_rule = self.check(doc)
        at3 = next(r for r in data["rows"] if r["id"] == "AT-3")
        self.assertEqual((at3["row"], at3["exact"], at3["inSync"]), ("R3", True, True))
        self.assertNotIn("THEN_NOT_IN_MAP", by_rule)
        self.assertNotIn("ALTITUDE_NOT_IN_MAP", by_rule)

    def test_a_map_that_prints_text_falls_back_to_the_substring_check(self) -> None:
        doc = self.doc_with("AT-1", altitude="response")
        result, data, by_rule = self.check(doc, "--linking", env={"FAKE_ROW_FORMAT": "text"})
        self.assertEqual([r["exact"] for r in data["rows"]], [False, False, False])
        at1 = next(r for r in data["rows"] if r["id"] == "AT-1")
        self.assertTrue(at1["inSync"])  # no altitude to compare against
        self.assertNotIn("ALTITUDE_NOT_IN_MAP", by_rule)
        [info] = by_rule["ROW_TEXT_ONLY"]
        self.assertEqual(info["severity"], "info")
        self.assertIn("R1, R2", info["message"])
        self.assertIn("no Altitude was compared", info["message"])
        self.assertEqual(result.returncode, 1)  # AT-3's drift, an error under --linking


class ModesHandleEveryLinkFinding(unittest.TestCase):
    """A mode that says what to do on THEN_NOT_IN_MAP says it for
    ALTITUDE_NOT_IN_MAP too, in the same paragraph: both are §6/map drift,
    and a mode that names one only reads the other as nothing."""

    def test_each_paragraph_that_names_the_then_rule_names_the_altitude_rule(self) -> None:
        skill = TESTS_DIR.parent / "skills" / "promise"
        files = sorted((skill / "modes").glob("*.md")) + [skill / "references" / "architecture.md"]
        checked = 0
        for path in files:
            for paragraph in path.read_text(encoding="utf-8").split("\n\n"):
                if "THEN_NOT_IN_MAP" in paragraph:
                    checked += 1
                    with self.subTest(file=path.name, paragraph=paragraph[:80]):
                        self.assertIn("ALTITUDE_NOT_IN_MAP", paragraph)
        self.assertGreaterEqual(checked, 7)


class ShippedWithoutGateTests(unittest.TestCase):
    """A shipped doc's §6 line that did not go red (no Red gate line, or
    listed in Filed without red run) and has no Kill line must cite a row
    with origin backfill and verdict proven (outcome-framework.md § Lifecycle). The
    C4 repro: the minimap doc, typed shipped with no Red gate line, over
    rows that are not built, used to validate clean."""

    MINIMAP = TESTS_DIR.parent / "examples" / "minimap"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "minimap"
        shutil.copytree(self.MINIMAP, self.project)
        config_path = self.project / "promise.config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        exe = shlex.quote(sys.executable)
        for key in ("find", "row", "nextId"):
            config["map"][key] = config["map"][key].replace("python3 ", exe + " ", 1)
        config_path.write_text(json.dumps(config), encoding="utf-8")
        # Two rows under one doc, so a row short of proven names only its own lines: the
        # example map as it stood with CAP-2 (tests/fixtures/find/three-rows).
        shutil.copy(TESTS_DIR / "fixtures" / "find" / "three-rows" / "map.json", self.project / "map.json")
        self.doc = self.project / "docs" / "designs" / "channel-muting.md"
        text = self.doc.read_text(encoding="utf-8").replace(
            "| Ben is still notified normally | perception | CAP-1 |", "| Ben is still notified normally | perception | CAP-2 |")
        shipped = text.replace("Status: agreed\n", "Status: " + "shipped\n", 1)
        self.assertNotEqual(shipped, text)
        self.doc.write_text(shipped, encoding="utf-8")

    def set_rows(self, **fields_by_id: dict) -> None:
        map_path = self.project / "map.json"
        data = json.loads(map_path.read_text(encoding="utf-8"))
        for row in data["rows"]:
            row.update(fields_by_id.get(row["id"].replace("-", "_"), {}))
        map_path.write_text(json.dumps(data), encoding="utf-8")

    def check(self):
        result, data = run_json(str(self.doc), "--cwd", str(self.project), "--json")
        self.assertIsNotNone(data, result.stdout + result.stderr)
        return result, [f for f in data["findings"] if f["rule"] == "SHIPPED_WITHOUT_GATE"]

    def test_rows_that_are_not_proven_backfilled_rows_are_an_error(self) -> None:
        result, found = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual([f["line"] for f in found], [79, 80, 81])
        self.assertEqual({f["severity"] for f in found}, {"error"})
        self.assertIn("cites CAP-1: it is origin None, verdict 'not-built'", found[0]["message"])

    def test_every_row_a_proven_backfilled_row_is_clean(self) -> None:
        proven = {"origin": "backfill", "verdict": "proven"}
        self.set_rows(CAP_1=proven, CAP_2=proven)
        result, found = self.check()
        self.assertEqual((result.returncode, found), (0, []), result.stdout)

    def test_a_proven_row_that_backfill_did_not_file_is_an_error(self) -> None:
        # Proven is not enough: the gate is skipped only over code that came
        # before the promise, which is what origin backfill records.
        self.set_rows(CAP_1={"verdict": "proven"}, CAP_2={"origin": "doc", "verdict": "proven"})
        result, found = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual([f["line"] for f in found], [79, 80, 81])
        self.assertIn("cites CAP-1: it is origin None, verdict 'proven'", found[0]["message"])
        self.assertIn("cites CAP-2: it is origin 'doc', verdict 'proven'", found[2]["message"])

    def test_one_row_short_names_only_its_lines(self) -> None:
        self.set_rows(CAP_1={"origin": "backfill", "verdict": "proven"},
                      CAP_2={"origin": "backfill", "verdict": "under-proven"})
        result, found = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertEqual([f["line"] for f in found], [81])

    def test_a_red_gate_line_means_the_gate_was_not_skipped(self) -> None:
        text = self.doc.read_text(encoding="utf-8")
        self.doc.write_text(text.replace("Supersedes: —\n", "Supersedes: —\nRed gate: a1b2c3d 2026-01-02\n", 1),
                            encoding="utf-8")
        result, found = self.check()
        self.assertEqual((result.returncode, found), (0, []), result.stdout)

    def kill_record(self, red_gate: bool, extra: str) -> None:
        text = self.doc.read_text(encoding="utf-8")
        if red_gate:
            text = text.replace("Supersedes: —\n", "Supersedes: —\nRed gate: a1b2c3d 2026-01-02\n", 1)
        snapshot = "the map is the source of these scenarios from here on.\n"
        self.assertIn(snapshot, text)
        self.doc.write_text(text.replace(snapshot, snapshot + extra, 1), encoding="utf-8")

    KILL_3 = ("Kill: AT-3 — mute every member of the channel → tests/test_mute.py::test_per_member failed; "
              "restored, passing at a1b2c3d on 2026-02-01\n")

    def test_a_line_filed_without_a_red_run_needs_a_proven_backfilled_row(self) -> None:
        # A Red gate line covers only the lines that went red: AT-3, filed
        # without a red run, must still cite a proven backfilled row.
        self.kill_record(True, "Filed without red run: AT-3 — backfilled\n")
        result, found = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual([f["line"] for f in found], [82])
        self.assertIn("AT-3 has no red run and no 'Kill:' line, and it cites CAP-2", found[0]["message"])

    def test_a_kill_line_covers_a_line_filed_without_a_red_run(self) -> None:
        self.kill_record(True, "Filed without red run: AT-3 — backfilled\n" + self.KILL_3)
        result, found = self.check()
        self.assertEqual((result.returncode, found), (0, []), result.stdout)

    def test_with_no_red_gate_a_kill_line_covers_only_its_own_line(self) -> None:
        self.kill_record(False, self.KILL_3)
        result, found = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual([f["line"] for f in found], [79, 80])

    def test_a_map_that_prints_text_cannot_show_the_rows_are_proven(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = bridged_project(Path(tmp))
            text = (FIXTURES_DIR / "agreed_bridged.md").read_text(encoding="utf-8")
            doc = project / "doc.md"
            doc.write_text(text.replace("Status: agreed\n", "Status: " + "shipped\n", 1), encoding="utf-8")
            result, data = run_json(str(doc), "--cwd", str(project), "--json", env={"FAKE_ROW_FORMAT": "text"})
        found = [f for f in data["findings"] if f["rule"] == "SHIPPED_WITHOUT_GATE"]
        self.assertEqual(len(found), 3, data["findings"])
        self.assertIn("printed text, not a JSON row, so its origin and verdict cannot be read", found[0]["message"])
        self.assertEqual(result.returncode, 1)


class MapNotConfiguredTests(unittest.TestCase):
    def test_no_config_is_map_not_configured_and_exits_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result, data = run_json(
                str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", tmp, "--json"
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual([f["rule"] for f in data["findings"]], ["MAP_NOT_CONFIGURED"])
            self.assertEqual(data["findings"][0]["severity"], "error")
            self.assertFalse(data["mapConfigured"])
            self.assertFalse(data["bridged"])
            # status is still reported: the doc itself was read successfully.
            self.assertEqual(data["status"], "agreed")

    def test_no_map_key_in_config_is_also_map_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_config(project, {"docsHome": "docs/designs"})
            result, data = run_json(
                str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(project), "--json"
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual([f["rule"] for f in data["findings"]], ["MAP_NOT_CONFIGURED"])

    def test_a_map_set_to_false_says_no_map_on_purpose(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_config(project, {"docsHome": "docs/designs", "map": False})
            result, data = run_json(
                str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(project), "--json"
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual([f["rule"] for f in data["findings"]], ["MAP_NOT_CONFIGURED"])
            self.assertIn("map is false: this project keeps no map, on purpose", data["findings"][0]["message"])

    def test_incomplete_map_is_map_not_configured_and_names_the_missing_keys(self) -> None:
        # orient's mapUsable is the one source of "is a map configured":
        # a map with only `row` set would have let the drift check run
        # against fake_row.py, but it is not a map, so nothing is checked
        # and the finding says which keys are missing.
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_config(project, {"map": {"row": fixture_command("fake_row.py")}})
            log_path = project / "fake_row.log"
            result, data = run_json(
                str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(project), "--json",
                env={"FAKE_ROW_LOG": str(log_path)},
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual([f["rule"] for f in data["findings"]], ["MAP_NOT_CONFIGURED"])
            self.assertIn("map incomplete: missing recipe, find, lanes", data["findings"][0]["message"])
            self.assertFalse(data["mapConfigured"])
            self.assertFalse(data["bridged"])
            self.assertEqual(data["rows"], [])
            self.assertEqual(read_invocation_log(log_path), [], "nothing may be looked up against a partial map")

    def test_empty_map_object_is_map_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            write_config(project, {"map": {}})
            result, data = run_json(
                str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(project), "--json"
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual([f["rule"] for f in data["findings"]], ["MAP_NOT_CONFIGURED"])
            self.assertFalse(data["mapConfigured"])

    def test_draft_with_no_config_is_not_bridged_not_map_not_configured(self) -> None:
        # Precedence: NOT_BRIDGED is checked before MAP_NOT_CONFIGURED. A
        # draft doc has not been bridged regardless of whether a map is
        # configured, so an empty project (no config at all) must still
        # report NOT_BRIDGED, never MAP_NOT_CONFIGURED, and exit 0.
        with tempfile.TemporaryDirectory() as tmp:
            result, data = run_json(
                str(FIXTURES_DIR / "draft_unbridged.md"), "--cwd", tmp, "--json"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual([f["rule"] for f in data["findings"]], ["NOT_BRIDGED"])
            self.assertEqual(data["findings"][0]["severity"], "info")
            self.assertEqual(data["status"], "draft")
            self.assertFalse(data["bridged"])
            self.assertFalse(data["mapConfigured"])


class StatusUnknownTests(unittest.TestCase):
    """A doc whose Status: is missing or not one of the five tokens is
    neither bridged nor known to be unbridged: STATUS_UNKNOWN (error),
    bridged false, and no other check — never validated as bridged with
    ROW_MISSING quietly suppressed."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = bridged_project(Path(self._tmp.name))
        self.base = (FIXTURES_DIR / "agreed_bridged.md").read_text(encoding="utf-8")

    def _doc(self, name: str, text: str) -> Path:
        path = self.project / name
        path.write_text(text, encoding="utf-8")
        return path

    def _assert_status_unknown(self, doc: Path, expected_status) -> None:
        log_path = self.project / "fake_row.log"
        result, data = run_json(str(doc), "--cwd", str(self.project), "--json", env={"FAKE_ROW_LOG": str(log_path)})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual([f["rule"] for f in data["findings"]], ["STATUS_UNKNOWN"])
        self.assertEqual(data["findings"][0]["severity"], "error")
        self.assertEqual(data["status"], expected_status)
        self.assertFalse(data["bridged"])
        self.assertTrue(data["mapConfigured"])
        self.assertEqual(data["rows"], [])
        self.assertEqual(read_invocation_log(log_path), [], "an unplaceable doc is never looked up against the map")

    def test_invalid_status_token_is_status_unknown(self) -> None:
        text = self.base.replace("Status: agreed\n", "Status: approved\n")
        self.assertNotEqual(text, self.base)
        self._assert_status_unknown(self._doc("invalid_status.md", text), "approved")

    def test_missing_status_line_is_status_unknown(self) -> None:
        text = self.base.replace("Status: agreed\n", "")
        self.assertNotEqual(text, self.base)
        self._assert_status_unknown(self._doc("no_status.md", text), None)

    def test_invalid_status_with_a_missing_row_is_still_only_status_unknown(self) -> None:
        # The doc that used to slip through: an invalid status made
        # ROW_MISSING not apply, so the doc validated clean as "bridged".
        text = (FIXTURES_DIR / "agreed_missing_row.md").read_text(encoding="utf-8").replace(
            "Status: agreed\n", "Status: approved\n"
        )
        self._assert_status_unknown(self._doc("invalid_missing_row.md", text), "approved")


class UnreadableTests(unittest.TestCase):
    def test_missing_doc_is_unreadable_exit_one_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result, data = run_json(str(Path(tmp) / "does-not-exist.md"), "--cwd", tmp, "--json")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual([f["rule"] for f in data["findings"]], ["UNREADABLE"])
            self.assertIsNone(data["status"])
            self.assertNotIn("Traceback", result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_missing_doc_human_output_has_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run(str(Path(tmp) / "nope.md"), "--cwd", tmp)
            self.assertEqual(result.returncode, 1)
            self.assertIn("UNREADABLE", result.stdout)
            self.assertNotIn("Traceback", result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_not_utf8_doc_is_unreadable_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            bad = project / "bad.md"
            bad.write_bytes(b"\xff\xfe\x00Status: agreed\x00")
            result, data = run_json(str(bad), "--cwd", str(project), "--json")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual([f["rule"] for f in data["findings"]], ["UNREADABLE"])
            self.assertNotIn("Traceback", result.stdout)
            self.assertNotIn("Traceback", result.stderr)


class HostileRowIdTests(unittest.TestCase):
    """A hostile Row cell fails ROW_ID_FORMAT under the real pattern; relaxed
    so a lookup is attempted, it reaches fake_row.py as exactly one argv
    element through the real bridge_validate.py -> adapter.py -> fake_row.py
    path (shell=False throughout every one of those three subprocess calls),
    never as text a shell parses."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name)
        self.marker = self.project / "PWNED"
        self.addCleanup(lambda: self.marker.unlink(missing_ok=True))
        # A payload that WOULD create `self.marker` if it were ever naively
        # embedded in a double-quoted shell argument -- `touch`, not a mere
        # `echo`, so its absence afterwards is real evidence: a payload
        # whose worst case only prints something proves nothing either way.
        self.hostile = f'R1"; touch {self.marker}; echo "'
        base = (FIXTURES_DIR / "agreed_bridged.md").read_text(encoding="utf-8")
        # Replace AT-1's Row cell (the last cell of its line) with the
        # payload, whatever other columns the fixture's table carries.
        replaced = []
        for line in base.splitlines(keepends=True):
            if line.startswith("| AT-1 "):
                self.assertTrue(line.rstrip().endswith("| R1 |"), line)
                line = line.rstrip()[: -len("| R1 |")] + f"| {self.hostile} |\n"
            replaced.append(line)
        doc_text = "".join(replaced)
        self.assertNotEqual(doc_text, base)
        self.doc = self.project / "hostile.md"
        self.doc.write_text(doc_text, encoding="utf-8")

    def test_payload_is_a_genuine_positive_control(self) -> None:
        # Before trusting the marker's absence as proof of safety below,
        # prove the payload really would create it under a real shell —
        # otherwise a payload that could never create the marker (an
        # unmatched quote, or a command that only prints) would make that
        # proof vacuous.
        self.assertFalse(self.marker.exists())
        subprocess.run(f'true "{self.hostile}"', shell=True)
        self.assertTrue(
            self.marker.exists(),
            "the payload must be able to create the marker under a real shell, "
            "or its absence later proves nothing",
        )
        self.marker.unlink()

    def test_fails_row_id_format_under_the_real_pattern(self) -> None:
        bridged_project(self.project, row_id_pattern=r"^R\d+$")
        result, data = run_json(str(self.doc), "--cwd", str(self.project), "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        self.assertEqual(error_rules, ["ROW_ID_FORMAT"])
        self.assertFalse(self.marker.exists(), "the hostile Row cell must never reach a shell")

    def test_relaxed_pattern_reaches_fake_row_as_one_argv_element_through_bridge(self) -> None:
        bridged_project(self.project, row_id_pattern=".*")
        log_path = self.project / "fake_row.log"
        result, data = run_json(
            str(self.doc), "--cwd", str(self.project), "--json",
            env={"FAKE_ROW_LOG": str(log_path)},
        )
        # bridge_validate.py's own run: no ROW_ID_FORMAT now that the id
        # "matches"; the lookup is attempted and the map genuinely has no
        # such row, so ROW_NOT_FOUND — not a crash, not a shell escape.
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        self.assertEqual(error_rules, ["ROW_NOT_FOUND"])
        self.assertFalse(self.marker.exists(), "the hostile Row cell must never reach a shell")

        # fake_row.py's own invocation log -- written from inside the real
        # bridge_validate.py -> adapter.py -> fake_row.py chain, not a
        # direct adapter.py call -- proves the id arrived as exactly one
        # argv element. The fixture's other two rows (R1, R2) are looked up
        # too since the pattern is relaxed to `.*`; filter to the hostile
        # id's own invocation(s) specifically.
        invocations = read_invocation_log(log_path)
        hostile_calls = [argv for argv in invocations if argv[-1] == self.hostile]
        self.assertEqual(len(hostile_calls), 1, invocations)
        self.assertEqual(len(hostile_calls[0]), 2, hostile_calls[0])  # sys.argv: [fake_row.py, id]
        self.assertEqual(hostile_calls[0][-1], self.hostile)


class NoRowIdPatternTests(unittest.TestCase):
    def test_missing_pattern_warns_and_skips_row_id_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = bridged_project(Path(tmp), row_id_pattern=None)
            result, data = run_json(
                str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(project), "--json"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)  # warns only
            rules = [f["rule"] for f in data["findings"]]
            self.assertIn("NO_ROW_ID_PATTERN", rules)
            self.assertNotIn("ROW_ID_FORMAT", rules)
            self.assertNotIn("INVALID_ROW_ID_PATTERN", rules)
            warn = next(f for f in data["findings"] if f["rule"] == "NO_ROW_ID_PATTERN")
            self.assertEqual(warn["severity"], "warn")


class InvalidRowIdPatternTests(unittest.TestCase):
    """`map.rowIdPattern` present but not a valid regex is a distinct,
    error-severity finding from `NO_ROW_ID_PATTERN` (absent) — never
    silently treated the same way."""

    def test_invalid_pattern_is_an_error_not_a_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = bridged_project(Path(tmp), row_id_pattern="[")  # unterminated char class
            result, data = run_json(
                str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(project), "--json"
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            rules = [f["rule"] for f in data["findings"]]
            self.assertIn("INVALID_ROW_ID_PATTERN", rules)
            self.assertNotIn("NO_ROW_ID_PATTERN", rules)
            self.assertNotIn("ROW_ID_FORMAT", rules)
            finding = next(f for f in data["findings"] if f["rule"] == "INVALID_ROW_ID_PATTERN")
            self.assertEqual(finding["severity"], "error")
            self.assertIn("[", finding["message"])

    def test_invalid_pattern_carries_the_regex_exception_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = bridged_project(Path(tmp), row_id_pattern="[")
            _, data = run_json(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(project), "--json")
            finding = next(f for f in data["findings"] if f["rule"] == "INVALID_ROW_ID_PATTERN")
            # The exact wording is Python's re module's own, and only needs
            # to be present -- not asserted verbatim, since it is not this
            # script's to word.
            self.assertTrue(finding["message"], finding)
            self.assertIn("does not compile", finding["message"])

    def test_row_id_format_is_skipped_but_the_drift_check_still_runs(self) -> None:
        # An unusable pattern only disables the FORMAT check (ROW_ID_FORMAT
        # can't validate against a pattern that doesn't compile) -- it does
        # not also disable the separate map.row lookup, exactly like a
        # genuinely absent pattern (NO_ROW_ID_PATTERN) does not either.
        with tempfile.TemporaryDirectory() as tmp:
            project = bridged_project(Path(tmp), row_id_pattern="[")
            _, data = run_json(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(project), "--json")
            by_id = {r["id"]: r for r in data["rows"]}
            self.assertTrue(by_id["AT-1"]["found"])
            self.assertTrue(by_id["AT-1"]["inSync"])
            self.assertTrue(by_id["AT-3"]["found"])
            self.assertFalse(by_id["AT-3"]["inSync"])  # the fixture's known drift, unaffected


class NoMapRowCommandTests(unittest.TestCase):
    def test_empty_row_command_warns_and_skips_drift_check(self) -> None:
        # mapUsable requires map.row to be a string; "" is one, and
        # configures nothing — the one way this warning is still reached.
        with tempfile.TemporaryDirectory() as tmp:
            project = bridged_project(Path(tmp), with_row=False)
            result, data = run_json(
                str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(project), "--json"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            rules = [f["rule"] for f in data["findings"]]
            self.assertIn("NO_MAP_ROW_COMMAND", rules)
            self.assertNotIn("ROW_NOT_FOUND", rules)
            self.assertNotIn("THEN_NOT_IN_MAP", rules)
            for row in data["rows"]:
                self.assertIsNone(row["found"])
                self.assertIsNone(row["inSync"])


class JsonSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = bridged_project(Path(self._tmp.name))

    def test_top_level_keys(self) -> None:
        _, data = run_json(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json")
        self.assertEqual(
            set(data.keys()),
            {"path", "status", "bridged", "mapConfigured", "rows", "findings", "stats"},
        )

    def test_row_keys(self) -> None:
        _, data = run_json(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json")
        for row in data["rows"]:
            self.assertEqual(set(row.keys()), {"id", "row", "line", "found", "inSync", "exact"})

    def test_finding_keys(self) -> None:
        _, data = run_json(str(FIXTURES_DIR / "agreed_missing_row.md"), "--cwd", str(self.project), "--json")
        for f in data["findings"]:
            self.assertEqual(set(f.keys()), {"rule", "line", "message", "severity"})

    def test_stats_keys(self) -> None:
        _, data = run_json(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json")
        self.assertEqual(
            set(data["stats"].keys()), {"rows", "mapped", "drifted", "errors", "warnings"}
        )

    def test_stdout_is_exactly_one_parseable_value(self) -> None:
        result = run(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(self.project), "--json")
        json.loads(result.stdout)  # raises if this is not exactly one JSON value


class HumanOutputTests(unittest.TestCase):
    def test_summary_line_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = bridged_project(Path(tmp))
            result = run(str(FIXTURES_DIR / "agreed_missing_row.md"), "--cwd", str(project))
            lines = result.stdout.strip().splitlines()
            self.assertTrue(lines[0].startswith(str(FIXTURES_DIR / "agreed_missing_row.md") + ":"))
            self.assertIn("ROW_MISSING", lines[0])
            self.assertEqual(lines[-1], "bridge: 3 rows, 2 mapped, 1 drifted")


class UsageErrorTests(unittest.TestCase):
    def test_no_doc_argument_is_a_usage_error(self) -> None:
        result = run()
        self.assertEqual(result.returncode, 2)

    def test_bad_cwd_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = run(str(FIXTURES_DIR / "agreed_bridged.md"), "--cwd", str(Path(tmp) / "does-not-exist"))
            self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
