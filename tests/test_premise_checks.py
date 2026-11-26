"""Load-bearing premises: §5's table, and the phrase heuristic over §1 and §5.

Run from the repo root:

    python3 -m unittest discover -s tests -v

Mirrors test_scripts.py's and test_lint_hardening.py's own conventions:
scripts and fixtures are located relative to this file rather than the
current working directory, and lint_outcome.py is exercised as a real
subprocess (argv, stdout, stderr, exit code) -- never imported and called
in-process. test_scripts.py's ERROR_RULE_FIXTURES/WARN_RULE_FIXTURES already
cover the canonical one-change-from-conforming fixture for PREMISE_TABLE
(`premise_table.md`) and PREMISE_PHRASE (`premise_phrase.md`); this module
covers the shapes those two fixtures don't reach: a complete table (clean,
even with a negative phrase inside its own Premise cell), a row missing the
OTHER required cell, a malformed header, the suppression comment, the exact
reference-incident shape (§1, not §5), and the literal-vs-semantic coverage
rule (IncidentShapeTests).

Reference incident (outcome-framework.md § Section rules, § The framework as
a review rubric item 9): a cross-repo outcome doc cited a real file:line
showing a meeting API returned participant ids and no emails, and stated as
fact that the source "can't say who spoke" -- in §1 Problem, not §5, since
that is where this kind of claim usually first gets written down. The
citation was true of the field checked and false of the entity: the
participant id WAS the account id, which the other repository already
stored and already joined on for a sibling connector, documented in two of
that repository's own design docs, and nobody had searched for it. A design
and a follow-up spike were built on the false premise before a reviewer
caught it a day later. An earlier version of this check only scanned §5 and
would have missed this exact case; PREMISE_PHRASE now scans §1 too
(IncidentShapeTests reproduces the shape directly), and a premises row must
inventory evidence AND say where else was searched, and a negative claim
with neither is at least a warning.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
PREMISE_DIR = FIXTURES_DIR / "premise-checks"
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"

LINT = SCRIPTS_DIR / "lint_outcome.py"

CONFORMING = FIXTURES_DIR / "conforming.md"
TABLE_COMPLETE = PREMISE_DIR / "table_complete.md"
MISSING_EVIDENCE = FIXTURES_DIR / "premise_table.md"
MISSING_EXISTING_JOIN = PREMISE_DIR / "missing_existing_join.md"
HEADER_MISSING_COLUMN = PREMISE_DIR / "header_missing_column.md"
PHRASE_UNLISTED = FIXTURES_DIR / "premise_phrase.md"
PHRASE_SUPPRESSED = PREMISE_DIR / "phrase_suppressed.md"
INCIDENT_NO_TABLE = PREMISE_DIR / "incident_shape_no_table.md"
INCIDENT_COVERED = PREMISE_DIR / "incident_shape_covered.md"


def lint_json(path: Path, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(LINT), str(path), "--json", *args],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def rules_in(data: dict) -> list:
    return sorted(f["rule"] for f in data["findings"])


class IncidentShapeTests(unittest.TestCase):
    """Reproduces the reference incident's exact shape: the false premise
    sat in §1 Problem, not §5 -- "**The source can't say who spoke.** The
    API gives participant ids and no emails (`x.ts:1-2`)." -- so this is the
    case that would have slipped past a §5-only PREMISE_PHRASE. With no
    premises table anywhere in the doc, it's a warning; with a complete §5
    row whose Premise cell quotes the same claim, it's clean."""

    def test_no_table_fires_premise_phrase_in_section_one(self) -> None:
        data = lint_json(INCIDENT_NO_TABLE)
        self.assertEqual(rules_in(data), ["PREMISE_PHRASE"])
        f = data["findings"][0]
        self.assertEqual(f["severity"], "warn")
        self.assertIn("in §1", f["message"])

    def test_covering_row_in_section_five_clears_it(self) -> None:
        data = lint_json(INCIDENT_COVERED)
        self.assertEqual(data["findings"], [])
        self.assertEqual(data["stats"], {"errors": 0, "warnings": 0, "total": 0})

    def test_covered_fixture_really_does_carry_the_same_claim(self) -> None:
        # The clean result above must come from the coverage rule, not from
        # accidentally deleting the §1 claim or the phrase inside the row.
        text = INCIDENT_COVERED.read_text(encoding="utf-8")
        self.assertIn("The source can't say who spoke.", text)
        self.assertEqual(text.count("The source can't say who spoke."), 2)  # §1 and the Premise cell

    def test_a_row_that_only_shares_topic_not_wording_does_not_clear_it(self) -> None:
        # The coverage check is literal, not semantic (framework § The
        # framework as a review rubric, item 9): a row about the same
        # subject in different words leaves the §1 line unlisted.
        covered_text = INCIDENT_COVERED.read_text(encoding="utf-8")
        paraphrased_row = (
            "| Speaker identity is not derivable from the raw feed. "
        )
        self.assertIn("| The source can't say who spoke. ", covered_text)
        text = covered_text.replace("| The source can't say who spoke. ", paraphrased_row, 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            path.write_text(text, encoding="utf-8")
            data = lint_json(path)
            self.assertEqual(rules_in(data), ["PREMISE_PHRASE"])


class PremiseTableCompleteTests(unittest.TestCase):
    """table present and complete: clean, even with a negative phrase inside
    its own Premise cell -- the phrase is the claim the table exists to
    carry, not a violation of the check that requires one."""

    def test_complete_table_lints_clean(self) -> None:
        data = lint_json(TABLE_COMPLETE)
        self.assertEqual(data["findings"], [])
        self.assertEqual(data["stats"], {"errors": 0, "warnings": 0, "total": 0})

    def test_complete_table_contains_a_negative_phrase_that_is_not_flagged(self) -> None:
        text = TABLE_COMPLETE.read_text(encoding="utf-8")
        self.assertIn("cannot tell which", text)
        data = lint_json(TABLE_COMPLETE)
        self.assertNotIn("PREMISE_PHRASE", rules_in(data))


class PremiseTableMissingCellTests(unittest.TestCase):
    """missing cell: an error, naming exactly which cell (or cells) is missing."""

    def test_missing_evidence_is_the_only_error(self) -> None:
        data = lint_json(MISSING_EVIDENCE)
        self.assertEqual(rules_in(data), ["PREMISE_TABLE"])
        f = data["findings"][0]
        self.assertEqual(f["severity"], "error")
        self.assertIn("missing Evidence", f["message"])
        self.assertNotIn("Existing join searched", f["message"])

    def test_missing_existing_join_names_that_cell(self) -> None:
        data = lint_json(MISSING_EXISTING_JOIN)
        self.assertEqual(rules_in(data), ["PREMISE_TABLE"])
        f = data["findings"][0]
        self.assertIn("missing Existing join searched", f["message"])
        self.assertNotIn("missing Evidence", f["message"])

    def test_missing_evidence_fixture_is_conforming_plus_one_table(self) -> None:
        conforming = CONFORMING.read_text(encoding="utf-8")
        fixture = MISSING_EVIDENCE.read_text(encoding="utf-8")
        self.assertNotEqual(conforming, fixture)
        # every line of conforming.md still appears, in order, in the fixture --
        # the table is an addition, not a rewrite of anything else.
        c_lines = conforming.splitlines()
        f_lines = fixture.splitlines()
        it = iter(f_lines)
        self.assertTrue(all(line in it for line in c_lines), "fixture must be conforming.md plus an insertion")

    def test_header_missing_a_required_column_is_reported_once_at_the_header(self) -> None:
        data = lint_json(HEADER_MISSING_COLUMN)
        self.assertEqual(rules_in(data), ["PREMISE_TABLE"])
        self.assertEqual(len(data["findings"]), 1)
        f = data["findings"][0]
        self.assertIn("must name both", f["message"])


class PremisePhraseUnlistedTests(unittest.TestCase):
    """unlisted negative phrase: a warning, not an error -- the run still
    exits 0 without --strict, and --strict promotes it."""

    def test_unlisted_phrase_is_a_warning_only(self) -> None:
        data = lint_json(PHRASE_UNLISTED)
        self.assertEqual([(f["rule"], f["severity"]) for f in data["findings"]], [("PREMISE_PHRASE", "warn")])

    def test_strict_promotes_it_to_error(self) -> None:
        data = lint_json(PHRASE_UNLISTED, "--strict")
        self.assertEqual([(f["rule"], f["severity"]) for f in data["findings"]], [("PREMISE_PHRASE", "error")])

    def test_message_cites_the_phrase_and_the_table_shape(self) -> None:
        data = lint_json(PHRASE_UNLISTED)
        message = data["findings"][0]["message"]
        self.assertIn("cannot", message)
        self.assertIn("not a premise", message)

    def test_each_listed_phrase_shape_fires_on_its_own_minimal_sentence(self) -> None:
        """The six phrase shapes framework § Section rules names, each in a
        fresh doc built from conforming.md, one sentence added to §5, no
        table -- every shape must fire PREMISE_PHRASE and nothing else."""
        base = CONFORMING.read_text(encoding="utf-8")
        anchor = "Today, every channel member is notified on every message (`messages.ts:88`)."
        self.assertIn(anchor, base)
        sentences = {
            "can't": "The client can't tell which tab is focused.",
            "cannot": "The client cannot tell which tab is focused.",
            "doesn't have": "The event payload doesn't have a tab identifier.",
            "does not have": "The event payload does not have a tab identifier.",
            "no way to": "There is no way to tell which tab sent the event.",
            "unavailable": "Per-tab focus state is unavailable in the payload.",
            "only X has": "Only the service worker has the tab id.",
        }
        with tempfile.TemporaryDirectory() as tmp:
            for label, sentence in sentences.items():
                with self.subTest(phrase=label):
                    path = Path(tmp) / "doc.md"
                    path.write_text(base.replace(anchor, anchor + " " + sentence, 1), encoding="utf-8")
                    data = lint_json(path)
                    self.assertEqual(
                        rules_in(data), ["PREMISE_PHRASE"],
                        f"{label!r} ({sentence!r}) did not fire PREMISE_PHRASE alone: {data['findings']}",
                    )
                    path.unlink()


class PremisePhraseSuppressionTests(unittest.TestCase):
    """suppression: marking a line `<!-- not a premise -->` is clean."""

    def test_suppressed_line_lints_clean(self) -> None:
        data = lint_json(PHRASE_SUPPRESSED)
        self.assertEqual(data["findings"], [])
        self.assertEqual(data["stats"], {"errors": 0, "warnings": 0, "total": 0})

    def test_suppression_marker_is_present_on_the_negative_line(self) -> None:
        text = PHRASE_SUPPRESSED.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "cannot report" in line:
                self.assertIn("<!-- not a premise", line)
                return
        self.fail("expected fixture to contain the suppressed sentence")

    def test_marker_only_suppresses_its_own_line(self) -> None:
        """A negative phrase on a DIFFERENT line from the marker still fires --
        the suppression is per-line, not per-document."""
        base = CONFORMING.read_text(encoding="utf-8")
        old = (
            "Today, every channel member is notified on every message (`messages.ts:88`).\n"
            "This adds a `mutedChannels` join table keyed by (member, channel); the send\n"
        )
        new = (
            "Today, every channel member is notified on every message (`messages.ts:88`).\n"
            "<!-- not a premise: unrelated aside -->\n"
            "This adds a `mutedChannels` join table keyed by (member, channel); the send\n"
            "path cannot reach a muted member on a second device.\n"
        )
        self.assertIn(old, base)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            path.write_text(base.replace(old, new, 1), encoding="utf-8")
            data = lint_json(path)
            self.assertEqual(rules_in(data), ["PREMISE_PHRASE"])


if __name__ == "__main__":
    unittest.main()
