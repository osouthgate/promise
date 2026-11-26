"""The kill record: a shipped doc must carry checkable proof that each §6
line was seen to fail (outcome-framework.md § Lifecycle).

A line went red when the doc has a ``Red gate:`` line and arm's ``Filed
without red run:`` line does not list it; a line that never went red (code
from the prototype door, or a backfilled row) is covered by reconcile's
``Kill:`` line, or, with a map, by a proven backfilled row
(tests/test_bridge_validate.py). Each fixture under fixtures/kill-record/ is
building_no_gate.md typed shipped, plus the kill record lines it names.

Run from the repo root:

    python3 -m unittest tests.test_kill_record -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List, Tuple

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES = TESTS_DIR / "fixtures" / "kill-record"
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"
LINT = SCRIPTS_DIR / "lint_outcome.py"
CHECK = SCRIPTS_DIR / "check.py"


def lint(path: Path) -> Tuple[int, List[Tuple[str, int]]]:
    proc = subprocess.run([sys.executable, str(LINT), str(path), "--json"], capture_output=True, text=True)
    data = json.loads(proc.stdout)
    return proc.returncode, [(f["rule"], f["line"]) for f in data["findings"]]


def lint_text(text: str) -> Tuple[int, List[Tuple[str, int]]]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "doc.md"
        path.write_text(text, encoding="utf-8")
        return lint(path)


class ShippedPrototypeDoc(unittest.TestCase):
    """A doc from the prototype door: every §6 line filed without a red run."""

    def test_a_kill_for_every_line_and_no_red_gate_is_clean(self) -> None:
        self.assertEqual(lint(FIXTURES / "shipped_prototype.md"), (0, []))

    def test_one_kill_missing_is_an_error_at_that_line(self) -> None:
        code, found = lint(FIXTURES / "shipped_prototype_kill_missing.md")
        self.assertEqual((code, found), (1, [("SHIPPED_NEEDS_GATE", 80)]))

    def test_with_no_filed_line_the_kills_alone_cover_it(self) -> None:
        text = (FIXTURES / "shipped_prototype.md").read_text(encoding="utf-8")
        filed = "Filed without red run: AT-1, AT-2, AT-3 — prototype\n"
        self.assertIn(filed, text)
        self.assertEqual(lint_text(text.replace(filed, "", 1)), (0, []))

    def test_a_kill_line_with_an_impossible_date_proves_nothing(self) -> None:
        text = (FIXTURES / "shipped_prototype.md").read_text(encoding="utf-8")
        bad = text.replace("restored, passing at a1b2c3d on 2026-02-01\n", "restored, passing at a1b2c3d on 2026-02-31\n", 1)
        self.assertNotEqual(bad, text)
        code, found = lint_text(bad)
        self.assertEqual(code, 1)
        self.assertEqual(sorted(found), [("KILL_RECORD_FORMAT", 83), ("SHIPPED_NEEDS_GATE", 79)])


class ShippedMixedDoc(unittest.TestCase):
    """A Red gate line, and AT-3 filed without a red run."""

    def test_a_kill_for_the_filed_line_is_clean(self) -> None:
        self.assertEqual(lint(FIXTURES / "shipped_mixed.md"), (0, []))

    def test_no_kill_for_the_filed_line_is_an_error(self) -> None:
        code, found = lint(FIXTURES / "shipped_mixed_no_kill.md")
        self.assertEqual((code, found), (1, [("SHIPPED_NEEDS_GATE", 82)]))

    def test_a_malformed_filed_line_still_counts_its_lines_as_not_red(self) -> None:
        text = (FIXTURES / "shipped_mixed_no_kill.md").read_text(encoding="utf-8")
        bad = text.replace("Filed without red run: AT-3 — prototype\n", "Filed without red run: AT-3\n", 1)
        self.assertNotEqual(bad, text)
        code, found = lint_text(bad)
        self.assertEqual(sorted(found), [("KILL_RECORD_FORMAT", 83), ("SHIPPED_NEEDS_GATE", 82)])

    def test_a_second_filed_line_is_out_of_shape(self) -> None:
        text = (FIXTURES / "shipped_mixed.md").read_text(encoding="utf-8")
        filed = "Filed without red run: AT-3 — prototype\n"
        code, found = lint_text(text.replace(filed, filed + "Filed without red run: AT-2 — prototype\n", 1))
        self.assertEqual(found, [("SHIPPED_NEEDS_GATE", 81), ("KILL_RECORD_FORMAT", 84)])

    def test_the_record_does_not_end_the_table_early_or_read_as_a_row(self) -> None:
        # The lines sit directly under the table, as Red run does: they end
        # it, and no ACCEPTANCE_TABLE finding reads them as a broken row.
        text = (FIXTURES / "shipped_mixed.md").read_text(encoding="utf-8")
        self.assertEqual(lint_text(text.replace("— prototype", "— prototype | backfilled", 1)), (0, []))


class RecordLinesAreReadSafely(unittest.TestCase):
    """Anything that looks like a Filed line takes coverage away; a Kill line gives it
    only in its exact shape. A record line between table rows hides no row."""

    FILED = "Filed without red run: AT-3 — prototype\n"
    KILL_3 = ("Kill: AT-3 — mute every member of the channel → tests/test_mute.py::test_mute_is_per_member "
              "failed; restored, passing at a1b2c3d on 2026-02-01\n")

    def no_kill(self) -> str:
        text = (FIXTURES / "shipped_mixed_no_kill.md").read_text(encoding="utf-8")
        self.assertIn(self.FILED, text)
        return text

    def test_a_decorated_filed_line_still_takes_coverage_away(self) -> None:
        for variant in ("**Filed without red run:** AT-3 — prototype", "- Filed without red run: AT-3 — prototype",
                        "`Filed without red run: AT-3 — prototype`", "> Filed without red run: AT-3 — prototype",
                        "filed without red run: AT-3 — prototype", "Filed without red-run: AT-3 — prototype",
                        "<!-- Filed without red run: AT-3 — prototype -->",
                        "    Filed without red run: AT-3 — prototype"):
            with self.subTest(variant=variant):
                code, found = lint_text(self.no_kill().replace(self.FILED, variant + "\n", 1))
                self.assertEqual(code, 1)
                self.assertEqual(sorted(found), [("KILL_RECORD_FORMAT", 83), ("SHIPPED_NEEDS_GATE", 82)])

    def test_a_decorated_or_indented_kill_line_gives_no_coverage(self) -> None:
        for variant in ("- " + self.KILL_3, "**Kill:**" + self.KILL_3[5:], "`" + self.KILL_3.strip() + "`\n",
                        "> " + self.KILL_3, "kill:" + self.KILL_3[5:], "    " + self.KILL_3,
                        "<!-- " + self.KILL_3.strip() + " -->\n"):
            with self.subTest(variant=variant):
                code, found = lint_text(self.no_kill().replace(self.FILED, self.FILED + variant, 1))
                self.assertEqual(code, 1)
                self.assertEqual(sorted(found), [("KILL_RECORD_FORMAT", 84), ("SHIPPED_NEEDS_GATE", 82)])
        self.assertEqual(lint_text(self.no_kill().replace(self.FILED, self.FILED + self.KILL_3, 1)), (0, []))

    def test_record_lines_in_a_fence_are_ignored(self) -> None:
        fenced = self.no_kill().replace(self.FILED, self.FILED + "```\n" + self.KILL_3 + "```\n", 1)
        self.assertEqual(lint_text(fenced), (1, [("SHIPPED_NEEDS_GATE", 82)]))
        # a Filed line in a fence takes nothing away either: the doc reads as all red
        mixed = (FIXTURES / "shipped_mixed.md").read_text(encoding="utf-8")
        fenced_filed = mixed.replace(self.FILED + self.KILL_3, "```\n" + self.FILED + "```\n", 1)
        self.assertNotEqual(fenced_filed, mixed)
        self.assertEqual(lint_text(fenced_filed), (0, []))

    def test_a_record_line_between_rows_hides_no_row(self) -> None:
        proto = (FIXTURES / "shipped_prototype.md").read_text(encoding="utf-8")
        lines = proto.splitlines(keepends=True)
        kills = [l for l in lines if l.startswith("Kill:")]
        filed = [l for l in lines if l.startswith("Filed without red run:")]
        row1 = [l for l in lines if l.startswith("| AT-1 ")][0]
        text = proto
        for l in kills + filed:
            text = text.replace(l, "", 1)
        text = text.replace(row1, row1 + kills[0], 1)  # one Kill after AT-1; AT-2, AT-3 have nothing
        code, found = lint_text(text)
        self.assertEqual(code, 1)
        self.assertEqual(sorted(found), [("KILL_RECORD_FORMAT", 80), ("SHIPPED_NEEDS_GATE", 81),
                                         ("SHIPPED_NEEDS_GATE", 82)])
        red_run = text.replace(kills[0], "Red run: pytest — 3 failing, 0 passing at a1b2c3d on 2026-01-02\n", 1)
        self.assertEqual(sorted(lint_text(red_run)[1]), [("KILL_RECORD_FORMAT", 80), ("SHIPPED_NEEDS_GATE", 79),
                                                         ("SHIPPED_NEEDS_GATE", 81), ("SHIPPED_NEEDS_GATE", 82)])


class CheckGateStep(unittest.TestCase):
    """check.py's gate step runs bridge_validate.py only on a doc with a line
    no red run and no Kill line covers; a fully killed doc needs no map."""

    def check(self, fixture: str) -> subprocess.CompletedProcess:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        docs = Path(tmp.name) / "docs" / "designs"
        docs.mkdir(parents=True)
        shutil.copy(FIXTURES / fixture, docs / "channel-muting.md")
        return subprocess.run([sys.executable, str(CHECK), "--no-map", "--cwd", tmp.name, "--docs-home",
                               "docs/designs"], capture_output=True, text=True)

    def test_a_shipped_prototype_doc_with_its_kills_passes_with_no_map(self) -> None:
        result = self.check("shipped_prototype.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("promise check: lint: ok (docs/designs)", result.stdout)
        self.assertIn("promise check: gate: skipped (no shipped doc has a §6 line that needs a proven "
                      "backfilled row)", result.stdout)

    def test_a_line_with_no_kill_fails_the_gate_with_no_map(self) -> None:
        result = self.check("shipped_mixed_no_kill.md")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("promise check: gate: failed (1 shipped doc with a §6 line no red run or Kill line "
                      "covers, and no map configured", result.stdout)


class DocsStateTheRecord(unittest.TestCase):
    """Each doc that states the shipped rule names both record lines."""

    SKILL = TESTS_DIR.parent / "skills" / "promise"

    def test_each_doc_names_the_filed_and_kill_lines(self) -> None:
        for rel in ("outcome-framework.md", "modes/arm.md", "modes/reconcile.md", "references/sizing.md",
                    "references/architecture.md", "../../README.md"):
            text = " ".join((self.SKILL / rel).read_text(encoding="utf-8").split())
            with self.subTest(doc=rel):
                self.assertIn("Filed without red run:", text)
                self.assertIn("`Kill:`", text)

    def test_arm_writes_the_filed_line_in_every_case(self) -> None:
        text = " ".join((self.SKILL / "modes" / "arm.md").read_text(encoding="utf-8").split())
        step = text.split("0. **Code that already exists needs no red test.**", 1)[1].split(" 1. **", 1)[0]
        self.assertIn("in every case: `Filed without red run: AT-2, AT-4 — prototype` (or `— backfilled`)", step)


if __name__ == "__main__":
    unittest.main()
