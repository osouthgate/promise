"""Locks the skill's status-authority rule: `agreed` and `shipped` are typed
by a human, never by this skill; `building` is the one exception, written by
`arm` only after the human has confirmed the red-gate commit.

Run from the repo root:

    python3 -m unittest discover -s tests -v

Checks, matching the ways this rule could quietly stop holding:
(a) arm.md still states the step and names itself the only writer; (b)
SKILL.md still states the rule in the open; (c) every sentence anywhere
under skills/promise/ that mentions `agreed`/`shipped` alongside a
status-transition verb is checked against a FROZEN ALLOWLIST, not a
heuristic — a heuristic can always be bypassed (a rewording it wasn't built
for) or false-positive (unrelated prose it wasn't built to exclude); the
collector here is deliberately broad instead, and a human decides, once,
which of what it finds are real; (d) the lint rule that makes `building`
checkable — BUILDING_NEEDS_GATE — fires as an ERROR on a `building` doc with
no red-gate commit line in its unfenced header, is not fooled by a
hex-looking run elsewhere in the header, a fenced illustration, or an
impossible calendar date, accepts a digit-only sha, and clears once a real
`Red gate: <sha> <date>` line is added.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional, Tuple

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
SKILL = TESTS_DIR.parent / "skills" / "promise"
SCRIPTS_DIR = SKILL / "scripts"
LINT = SCRIPTS_DIR / "lint_outcome.py"

ARM_MD = SKILL / "modes" / "arm.md"
SKILL_MD = SKILL / "SKILL.md"
BUILDING_NO_GATE = FIXTURES_DIR / "building_no_gate.md"


def normalize_whitespace(text: str) -> str:
    """Collapse every run of whitespace (including a line-wrap plus the next
    line's indentation) to one space, so a "literal" phrase check matches
    prose that markdown wraps across lines the same way a reader sees it —
    the wrap column is a formatting choice, not part of what the doc says."""
    return re.sub(r"\s+", " ", text)


def skill_prose_files() -> List[Path]:
    """SKILL.md, modes/*.md, references/*.md, outcome-framework.md, templates/*.md."""
    files = [SKILL_MD, SKILL / "outcome-framework.md"]
    files += sorted((SKILL / "modes").glob("*.md"))
    files += sorted((SKILL / "references").glob("*.md"))
    files += sorted((SKILL / "templates").glob("*.md"))
    return [f for f in files if f.is_file()]


def lint_json(path: Path, *args: str) -> Tuple[subprocess.CompletedProcess, Optional[dict]]:
    result = subprocess.run(
        [sys.executable, str(LINT), str(path), "--json", *args],
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout) if result.stdout.strip() else None
    return result, data


# ---------------------------------------------------------------------------
# The status-transition collector — deliberately broad, no negation or
# clause logic at all. A heuristic that tries to be clever about what
# counts as "really" an instruction is exactly what a rewording bypasses
# and unrelated prose false-positives on; this one does neither, on
# purpose, and leaves the judgement to the frozen allowlist below.
# ---------------------------------------------------------------------------

STATUS_WORD_RE = re.compile(r"\b(agreed|shipped)\b", re.IGNORECASE)
TRANSITION_VERB_RE = re.compile(
    r"\b(write|writes|written|set|sets|flip|flips|mark|marks|move|moves|"
    r"change|changes|type|typed|types|advance|advances|promote|promotes|"
    r"reach|reaches|becomes)\b",
    re.IGNORECASE,
)
_LIST_MARKER_RE = re.compile(r"^([-*]|\d+\.)\s+")


def logical_sentences(text: str) -> List[str]:
    """Markdown line-wraps collapsed into logical paragraphs, then split
    into sentences.

    A new paragraph starts at a blank line, a heading, a table row, a
    fence line, or a list-item marker; every other line continues the
    current paragraph (this is how a wrapped sentence — "cannot move to\\n
    `agreed`." — is seen as one piece of text, the way a reader sees it,
    not two unrelated lines). Each paragraph is then split into sentences
    on a period followed by whitespace or the paragraph's end. This is
    presentation unwrapping, not a grammar parser — an abbreviation would
    over-split, which only ever produces a smaller, still-checked
    fragment, never a missed one.
    """
    paragraphs: List[str] = []
    current: List[str] = []

    def flush() -> None:
        if current:
            paragraphs.append(re.sub(r"\s+", " ", " ".join(current)).strip())
            current.clear()

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            flush()
            continue
        starts_new = (
            stripped.startswith("#")
            or stripped.startswith("|")
            or stripped.startswith("```")
            or stripped.startswith("~~~")
            or bool(_LIST_MARKER_RE.match(stripped))
        )
        if starts_new:
            flush()
        current.append(stripped)
    flush()

    sentences: List[str] = []
    for para in paragraphs:
        for piece in re.split(r"(?<=[.])\s+", para):
            piece = piece.strip()
            if piece:
                sentences.append(piece)
    return sentences


def is_status_transition_sentence(sentence: str) -> bool:
    """True when `sentence` names `agreed`/`shipped` (with or without
    backticks — `\\b` does not care either way) AND any transition verb,
    anywhere in the sentence, in any order. No negation check, no clause
    check, no proximity requirement: deliberately broad."""
    return bool(STATUS_WORD_RE.search(sentence) and TRANSITION_VERB_RE.search(sentence))


def collect_status_transition_sentences() -> Dict[str, List[str]]:
    """sentence text -> the files it was found in (usually one; the `arm`
    mode-dispatch row is documented verbatim in two places). Every
    sentence collected here must be a key in STATUS_TRANSITION_ALLOWLIST
    below, and every key in that allowlist must show up here — see
    StatusTransitionAllowlistTests.
    """
    found: Dict[str, List[str]] = {}
    for path in skill_prose_files():
        text = path.read_text(encoding="utf-8")
        for sentence in logical_sentences(text):
            if is_status_transition_sentence(sentence):
                found.setdefault(sentence, []).append(str(path.relative_to(SKILL)))
    return found


# ---------------------------------------------------------------------------
# The frozen allowlist. Every sentence collect_status_transition_sentences()
# finds under skills/promise/ today, each with why it is not an instruction
# for THIS SKILL to write `agreed`/`shipped` itself:
#
#   human-actor              -- names a human as the one who does it, as a rule
#   describes-the-human-act  -- narrates the human act in passing, not as a rule
#   negated                  -- describes when the transition is NOT allowed
#   not-a-transition         -- the verb and the status word are unrelated here
#
# A sentence the collector finds that is not a key here fails the test: a
# human must read it and either add it, with a reason, or reword the doc so
# it no longer reads as a status-transition instruction. A key here that the
# collector no longer finds anywhere also fails — a stale entry would hide a
# doc change from review just as surely as a missing one would.
# ---------------------------------------------------------------------------

STATUS_TRANSITION_ALLOWLIST: Dict[str, str] = {
    "Shipped (the seventeen in §3): `orient.py` (§5), `lint_outcome.py` (§9), `outcome_rows.py` (§10), `adopt.py` and `start_map.py` (§13), `framework_section.py`, `install_skill.py` (links or copies the skill into `.agents/`, `.codex/` or `.cursor/skills` for agents other than Claude Code; `--git-hook` puts the §0 check in front of every commit), `adapter.py` (runs every configured command with the user's text as one argument — never a composed shell string; `find --query-file` reads the query from a file; `verify --only <op>` narrows the verify run; `surfaces --out <file>` runs `map.surfaces` and writes the entry points; refuses when `mapUsable` is false), `render_outcome.py` (instantiates the template; refuses to overwrite; `--create-docs-home` is the only way it makes a folder), `bridge_validate.py` (§10: checks a bridged doc's §6 Row ids, snapshot line and `Then` text against the project's current map), `diff_outcome.py` (§0 before and after, from two files or a git ref and the working tree; only the rule tags and the `Scenarios:` count may change on an `agreed`, `building` or `shipped` doc, unless the status goes back to `draft` — `S0_CHANGED` (error), `S0_REOPENED` (warn); the plugin hook and the GitHub Action both run it), `map_report.py` (the map joined to a JUnit test run: each citation `file::name` matched to a test case, a bucket per row — failing, bad-citation, never-ran, skipped, not-run, passing, external, no-test, where `not-run` is a lane whose suite is not in the run at all, never proof, named once in `summary.lanesNotInRun` and not a `--strict` failure — and a verdict computed from the lane each scenario's altitude picks, worst citation first, compared with the recorded one: optimistic or promotable; it never writes the map).":
        "not-a-transition",

    "``` promise/ ← the repo root: the plugin and its own marketplace .claude-plugin/plugin.json .claude-plugin/marketplace.json .github/workflows/tests.yml ← the test suite on every push and pull request .github/workflows/release-tags.yml ← tags each release on main v<version> and moves the major tag (v1): the ref a repository pins .github/scripts/release.sh ← what that workflow runs, and a maintainer by hand when Actions cannot: the tag, v1, and the GitHub release from changelog_entry.py; --all, --check .pre-commit-hooks.yaml ← promise-section0 and promise-lint for the pre-commit framework action.yml ← the GitHub Action: lint_outcome.py and diff_outcome.py on a project's pull requests hooks/ hooks.json ← the plugin's PreToolUse hooks: on Edit, MultiEdit and Write; on GitHub writes and gh; and the mod's module decisions-pane.js ← a Claude Code mod: the decision pane (decisions.py sheet --json in, apply - out), the tool decision_pane and /promise-decide precommit.py ← the §0 check and the lint before a commit, for agents with no PreToolUse hook guard_section0.py ← blocks a model edit to §0 of an agreed doc (diff_outcome.compare); fails open guard_github_text.py ← blocks an issue or pull request body whose promise block fails the lint, and asks before a new one with no block; fails open LICENSE README.md CHANGELOG.md evals/ ← behaviour evals for `claude plugin eval` (README.md, run.sh, _fixture/, one folder per case); their shape is checked by tests/test_evals.py examples/ ← runnable, outside the skill; linted and exercised by tests/test_examples.py channel-muting.md ← one conforming outcome doc: Altitude column, §10 owners, lint exit 0 backfill-moved.md ← a legacy design doc moved into an outcome doc at draft: the pending-confirmation line, quoted rules, an Open — Qn field key-tabs.md ← a doc under Decision policy: auto: three provisional agent decisions in §8 (the sheet's \"Decided for you\") and a protected one asked as a §9 question transcript.md ← a short annotated session: Phase 0 line, mode inference, one interview turn, one lint finding, the pasted §0 proofmap/ ← a six-row map with a JUnit run (run/): every outcome map_report.py can show decisions/asks.json ← an asks file with every item kind, for decisions.py sheet over channel-muting.md minimap/ ← a tiny capability map: map.json, capability_find.py (find / --row / --next-id / --eval / learn / refs sync / --code), find-eval.json, promise.config.json, recipe.md, README.md, docs/designs/ with the bridged doc skills/promise/ SKILL.md ← router.":
        "not-a-transition",

    "Reason: the plugin's hook stops the model editing an agreed §0 in a session; CI checks every change, whoever made it.":
        "not-a-transition",

    "Its PreToolUse hook (`hooks/guard_section0.py`) blocks an Edit, MultiEdit or Write that changes §0 of an `agreed`, `building` or `shipped` doc beyond the rule tags and the `Scenarios:` count, unless the same edit sets `Status: draft`; CI runs the same check (`diff_outcome.py`).":
        "not-a-transition",

    "With a capability map, `arm` files an `agreed` doc's acceptance rows there and the map "
    "becomes their home (`intake`/`reconcile` write it, not the doc); no map → the doc, "
    "always.": "describes-the-human-act",

    '| `arm` | `modes/arm.md` | an `agreed` doc plus "start building", '
    '"arm it", "write the red tests", "file the rows", "kick off the '
    'build" |': "not-a-transition",

    "- `agreed` and `shipped` are typed by a human, never by this skill.":
        "human-actor",

    "- A doc in `draft` with unresolved BLOCKING questions cannot move to "
    "`agreed`.": "negated",

    "`lint_outcome.py` accepts the shape on a `draft` only (`THIN_DRAFT`), "
    "so a thin doc cannot be agreed; `revise` writes the agent half and "
    "removes the line.": "negated",

    "| F10 | A thin draft (`Depth: thin`) holds the human half only, and is a "
    "`draft` that cannot be agreed | A doc that asks for rules, a signal and "
    "a worked example before it is written stops the ideas that most need a "
    "home; a thin draft takes the idea as it is and turns each gap into a "
    "BLOCKING question, and the lint keeps it out of `agreed`, so the checks "
    "at every gate stay as strict as before |": "negated",

    "Write the new row id into the `Row` column of each §6 line it "
    "covers, adding the column between `Altitude` and the table's edge if "
    "the doc has none, and add one line under the §6 table: `Snapshot taken at "
    "`agreed` on <date>; the map is the source of these scenarios from "
    "here on.` §0's rule tags stay AT aliases; they do not change.":
        "not-a-transition",

    "A new rule a person must agree is a §0 change, confirmed by the human in `revise` | §0 is the human's "
    "words; `agreed` and `shipped` are typed by a human |": "human-actor",

    "- Set `Status: draft` on the survivor, even where a folded doc was "
    "`agreed` or later — the merge is a new draft until the human "
    "re-ratifies it.": "not-a-transition",

    "**The human flips `Status: shipped`, never this mode.**": "human-actor",

    "- Doc is `agreed` or later → a §0 change un-ratifies it.":
        "not-a-transition",

    "| \"Status agreed is a formality, I'll flip it.\" | It's the human "
    "act the whole framework protects.": "describes-the-human-act",

    "Where the project keeps a **capability map** — a machine-checked "
    "register of promises and the tests that prove them — the doc's "
    "acceptance rows become **rows** in that map when the doc is "
    "`agreed`, and the map becomes the source of the scenarios from then "
    "on.": "not-a-transition",

    "| `shipped` | Human flips it when §6 rows are green and each line went red or has a `Kill:` line.": "human-actor",
    "The person signs off the doc; the agent never sets `agreed` or `shipped` (`arm` may set `building` as usual).":
        "negated",

    "`agreed` and `shipped` are typed by a human.": "human-actor",

    "The rendered block is ≤ 20 lines and says: capability work goes "
    "through `/promise` in plain words (the mode is inferred); one doc "
    "per capability in the docs home, in the Outcome Framework shape; §0 "
    "is the human's verbatim block and agents only append notes below "
    "it; `Status:` reaches `agreed` and `shipped` only by a human's hand, "
    "`building` only after the human approves the red-test commit; where a "
    "map is configured it is the source of scenarios after `agreed`, §6 is "
    "then a snapshot nobody edits, and a verdict moves only at the altitude "
    "the row's own `Then` claims; before writing any design, plan or spec "
    "doc by hand, run `/promise` — a sibling doc is a bug.": "human-actor",

    "Look in the recipe for the parts a "
    "mode will ask for by name: a **routing table** (which relation a "
    "piece of feedback becomes), the **lockstep rule** (which files move "
    "together, and in what order), a **lane table** (how a `Then`'s "
    "altitude picks a test kind), a **verification block** (the commands "
    "to run before calling anything done), and a **shipped-work "
    "section** — the mirror direction, code landed and a row needs "
    "updating.": "not-a-transition",

    "`agreed` and `shipped` are typed by a human; `building` only after the human "
    "approves the red-test commit.":
        "human-actor",

    'When every bridged row is a backfilled row, proven through `reconcile`, the human may type `shipped` with no red gate, because the code came before the promise and there was nothing to turn red.':
        'human-actor',

    "| F11 | A product that exists before its promises gets a map by `backfill`: every test case in a JUnit run and every entry point the project's own command lists must land in a row (`map_report.py --orphans`, `--surfaces`), a writer pass is checked by a different verifier, backfilled rows are `origin: backfill` with `doc: null` until an agreed doc bridges them, verdicts are capped at `under-proven` until `reconcile` watches a kill, and legacy docs move into outcome docs with a verbatim, pending §0 | A green suite over a product nobody mapped says nothing about the code no test runs; the check has to start from what exists — the tests and the entry points — or untested production code stays invisible.":
        'describes-the-human-act',

    'It becomes a promise only through the bridge of an agreed outcome doc.':
        'describes-the-human-act',

    "- When a moved doc is agreed, `arm`'s bridge links each §6 line to its backfilled row (the `Row` cell cites the existing id and the row's `doc` is set) instead of filing a new row.":
        'describes-the-human-act',

    'When every bridged row is a backfilled row, proven through `reconcile`, the human may type `shipped` with no red gate: the code came before the promise (framework § Lifecycle).':
        'human-actor',
}


class ArmWritesOnlyBuilding(unittest.TestCase):
    def test_arm_states_the_step_text(self) -> None:
        text = normalize_whitespace(ARM_MD.read_text(encoding="utf-8"))
        self.assertIn(
            "Ask, then write `Status: building`",
            text,
            "arm.md must state the confirm-then-write step for `building`",
        )

    def test_arm_states_it_is_the_only_status_this_skill_writes(self) -> None:
        text = normalize_whitespace(ARM_MD.read_text(encoding="utf-8"))
        self.assertIn(
            "This is the only status this skill writes",
            text,
            "arm.md must say `building` is the only status this skill writes",
        )


class ArmCommitsTheDoc(unittest.TestCase):
    """The doc edits arm makes (§6 output, the `Red gate:` line, `Status:`)
    reach git as the branch's second commit, after the test-only first one."""

    def test_arm_names_the_doc_commit(self) -> None:
        text = normalize_whitespace(ARM_MD.read_text(encoding="utf-8"))
        self.assertIn("docs(<scope>): arm", text)
        self.assertIn("test(<scope>): red acceptance gate", text)
        self.assertIn("both commit shas", text)


MERGE_MD = SKILL / "modes" / "merge.md"


class MergeNamesItsMechanics(unittest.TestCase):
    """merge is the one mode that deletes files and the one mode that writes
    `superseded-by`; each mechanic must be stated, not left to the model."""

    def test_deletion_is_git_rm_by_explicit_path(self) -> None:
        text = normalize_whitespace(MERGE_MD.read_text(encoding="utf-8"))
        self.assertIn("`git rm <path>`", text, "the Delete and commit section names the git mechanics")
        self.assertIn("Never `git rm` a file the user did not name", text)

    def test_a_building_doc_has_its_red_gate_retired(self) -> None:
        text = normalize_whitespace(MERGE_MD.read_text(encoding="utf-8"))
        self.assertIn("Red gate", text, "the Folding a building doc section names the Red gate line")
        self.assertIn("feat/<slug>", text)

    def test_a_bridged_doc_has_its_rows_repointed_or_retired(self) -> None:
        text = normalize_whitespace(MERGE_MD.read_text(encoding="utf-8"))
        self.assertIn("**Re-point**", text)
        self.assertIn("**Retire**", text)

    def test_superseded_by_is_written_only_on_a_kept_folded_doc(self) -> None:
        text = normalize_whitespace(MERGE_MD.read_text(encoding="utf-8"))
        self.assertIn("`Status: superseded-by <survivor path>`", text)
        self.assertIn("the one case any mode writes that status", text)


class SkillStatesTheRule(unittest.TestCase):
    def test_skill_md_states_typed_by_a_human(self) -> None:
        text = normalize_whitespace(SKILL_MD.read_text(encoding="utf-8"))
        self.assertIn("typed by a human", text)


class StatusTransitionAllowlistTests(unittest.TestCase):
    """(c): every collected sentence must be allowlisted; every allowlisted
    sentence must still be collected. Both directions are load-bearing —
    the first catches a new bypass-shaped sentence, the second catches an
    allowlist that has quietly gone stale and stopped meaning anything."""

    def test_every_collected_sentence_is_allowlisted(self) -> None:
        collected = collect_status_transition_sentences()
        unlisted = [s for s in collected if s not in STATUS_TRANSITION_ALLOWLIST]
        self.assertEqual(
            unlisted,
            [],
            "new status-transition sentence — a human must read it and add it to "
            "the allowlist, or reword it:\n\n"
            + "\n\n".join(f"{s!r}\n  found in: {', '.join(collected[s])}" for s in unlisted),
        )

    def test_every_allowlist_entry_still_exists(self) -> None:
        collected = collect_status_transition_sentences()
        stale = [s for s in STATUS_TRANSITION_ALLOWLIST if s not in collected]
        self.assertEqual(
            stale,
            [],
            "allowlisted sentence no longer found anywhere under skills/promise/ "
            "(a stale entry hides a doc change from review):\n\n"
            + "\n\n".join(repr(s) for s in stale),
        )

    def test_allowlist_reasons_are_one_of_the_four_words(self) -> None:
        allowed_reasons = {"human-actor", "describes-the-human-act", "negated", "not-a-transition"}
        for sentence, reason in STATUS_TRANSITION_ALLOWLIST.items():
            with self.subTest(sentence=sentence[:60]):
                self.assertIn(reason, allowed_reasons, f"{reason!r} is not one of {allowed_reasons}")

    def test_collector_found_at_least_one_sentence(self) -> None:
        # A collector that silently finds nothing would make both checks
        # above vacuous — the rule IS stated in arm.md/SKILL.md, so at
        # least one sentence must be found.
        collected = collect_status_transition_sentences()
        self.assertGreater(len(collected), 0, "no status-transition sentence was found at all")


class CollectorUnitProbes(unittest.TestCase):
    """A heuristic detector was bypassable and had false positives (a prior
    Codex re-review finding); these three fixed phrasings are the proof —
    the deliberately broad collector above must COLLECT all three (whether
    they are ALLOWED is the allowlist's job, and none of them is in it,
    since none exists in the real docs today)."""

    PROBES = (
        # Bypassed a "does the line also say human" check: `human` appears,
        # but not as the actor of the write.
        "Set Status: shipped without human approval.",
        # False-positived a negation/clause heuristic: this sentence STATES
        # the rule correctly (the skill never sets it) but was flagged as
        # if it were the violation.
        "`shipped` should never be set by the skill.",
        # Missed by a heuristic requiring the verb and the status word
        # within a short gap or a specific order.
        "Change the status and the document state to shipped.",
    )

    def test_all_three_probes_are_collected(self) -> None:
        for probe in self.PROBES:
            with self.subTest(probe=probe):
                self.assertTrue(
                    is_status_transition_sentence(probe),
                    f"the broad collector must catch this phrasing: {probe!r}",
                )

    def test_none_of_the_probes_is_allowlisted(self) -> None:
        for probe in self.PROBES:
            with self.subTest(probe=probe):
                self.assertNotIn(
                    probe, STATUS_TRANSITION_ALLOWLIST,
                    f"probe should not already exist in the real docs: {probe!r}",
                )


class BuildingNeedsGateRule(unittest.TestCase):
    def test_fixture_exists(self) -> None:
        self.assertTrue(BUILDING_NO_GATE.is_file(), "missing fixture: building_no_gate.md")

    def _write(self, tmp: str, text: str) -> Path:
        path = Path(tmp) / "doc.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_fires_as_an_error_with_no_red_gate_commit(self) -> None:
        proc, data = lint_json(BUILDING_NO_GATE)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        findings = [f for f in data["findings"] if f["rule"] == "BUILDING_NEEDS_GATE"]
        self.assertEqual(len(findings), 1, data["findings"])
        self.assertEqual(findings[0]["severity"], "error")
        # No other error-severity rule fires alongside it: the fixture is
        # conforming.md with Status: building and every rule tagged.
        error_rules = sorted({f["rule"] for f in data["findings"] if f["severity"] == "error"})
        self.assertEqual(error_rules, ["BUILDING_NEEDS_GATE"])

    def test_strict_has_no_additional_effect(self) -> None:
        # Already an error: --strict (which only promotes warn -> error)
        # changes nothing about it.
        proc, data = lint_json(BUILDING_NO_GATE, "--strict")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        findings = [f for f in data["findings"] if f["rule"] == "BUILDING_NEEDS_GATE"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["severity"], "error")

    def test_clears_once_a_red_gate_commit_is_in_the_header(self) -> None:
        # A real line directly under `Supersedes:` clears the rule.
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        with_gate = text.replace(
            "Supersedes: —\n", "Supersedes: —\nRed gate: a1b2c3d 2026-01-02\n", 1
        )
        self.assertNotEqual(with_gate, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, with_gate))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        rules = [f["rule"] for f in data["findings"]]
        self.assertNotIn("BUILDING_NEEDS_GATE", rules, data["findings"])

    def test_digit_only_sha_is_valid(self) -> None:
        # The regex's sha group is [0-9a-fA-F]{7,40} -- digits alone qualify.
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        with_gate = text.replace(
            "Supersedes: —\n", "Supersedes: —\nRed gate: 1234567 2026-01-02\n", 1
        )
        self.assertNotEqual(with_gate, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, with_gate))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        rules = [f["rule"] for f in data["findings"]]
        self.assertNotIn("BUILDING_NEEDS_GATE", rules, data["findings"])

    def test_hex_word_elsewhere_in_the_header_does_not_satisfy_the_rule(self) -> None:
        # False positive: a hex-looking run on a DIFFERENT header line (not
        # its own `Red gate:` line) must never quietly clear the rule.
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        mutated = text.replace("Supersedes: —\n", "Supersedes: deadbeef\n", 1)
        self.assertNotEqual(mutated, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, mutated))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        rules = [f["rule"] for f in data["findings"]]
        self.assertIn("BUILDING_NEEDS_GATE", rules, data["findings"])

    def test_digit_only_date_elsewhere_does_not_satisfy_the_rule(self) -> None:
        # False positive: an un-hyphenated digit run (e.g. a Last decision:
        # date with no dashes) must never quietly clear the rule either.
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        mutated = text.replace("Last decision: 2026-01-01", "Last decision: 20260101", 1)
        self.assertNotEqual(mutated, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, mutated))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        rules = [f["rule"] for f in data["findings"]]
        self.assertIn("BUILDING_NEEDS_GATE", rules, data["findings"])

    def test_fenced_red_gate_line_does_not_clear_the_rule(self) -> None:
        # A Red gate: line sitting inside a fenced code block (an
        # illustration, not the doc's own header) must not clear the rule.
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        fenced = text.replace(
            "Supersedes: —\n",
            "Supersedes: —\n```\nRed gate: a1b2c3d 2026-01-02\n```\n",
            1,
        )
        self.assertNotEqual(fenced, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, fenced))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        rules = [f["rule"] for f in data["findings"]]
        self.assertIn("BUILDING_NEEDS_GATE", rules, data["findings"])
        finding = next(f for f in data["findings"] if f["rule"] == "BUILDING_NEEDS_GATE")
        self.assertIn("none found", finding["message"])

    def test_tilde_fenced_red_gate_line_does_not_clear_the_rule(self) -> None:
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        fenced = text.replace(
            "Supersedes: —\n",
            "Supersedes: —\n~~~\nRed gate: a1b2c3d 2026-01-02\n~~~\n",
            1,
        )
        self.assertNotEqual(fenced, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, fenced))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        rules = [f["rule"] for f in data["findings"]]
        self.assertIn("BUILDING_NEEDS_GATE", rules, data["findings"])

    def test_impossible_date_fires_its_own_message(self) -> None:
        # A line matching the sha/date SHAPE but naming a date that does
        # not exist on the calendar is its own finding, not silently
        # treated as no line at all.
        text = BUILDING_NO_GATE.read_text(encoding="utf-8")
        bad_date = text.replace(
            "Supersedes: —\n", "Supersedes: —\nRed gate: a1b2c3d 2026-02-31\n", 1
        )
        self.assertNotEqual(bad_date, text)
        with tempfile.TemporaryDirectory() as tmp:
            proc, data = lint_json(self._write(tmp, bad_date))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        findings = [f for f in data["findings"] if f["rule"] == "BUILDING_NEEDS_GATE"]
        self.assertEqual(len(findings), 1, data["findings"])
        self.assertEqual(findings[0]["severity"], "error")
        self.assertIn("not a real calendar date", findings[0]["message"])
        self.assertIn("2026-02-31", findings[0]["message"])

    def test_conforming_and_template_still_lint_clean(self) -> None:
        # A rule this specific must not fire on either baseline fixture —
        # conforming.md is Status: draft, and the template is exempted via
        # --template, so neither carries Status: building at all.
        proc, conforming = lint_json(FIXTURES_DIR / "conforming.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(conforming["stats"], {"errors": 0, "warnings": 0, "total": 0})

        template = SKILL / "templates" / "outcome-doc.md"
        result = subprocess.run(
            [sys.executable, str(LINT), str(template), "--template"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class ShippedNeedsGateRule(unittest.TestCase):
    """A shipped doc carries proof that each §6 line was seen to fail: a red
    run, a Kill line, or a proven backfilled row (outcome-framework.md §
    Lifecycle; the Kill lines are in tests/test_kill_record.py). The lint
    cannot see the map, so it reports each uncovered §6 line with no Row; bridge_validate.py checks the rest
    (SHIPPED_WITHOUT_GATE, tests/test_bridge_validate.py)."""

    SHIPPED = "Status: " + "shipped"
    MINIMAP_DOC = TESTS_DIR.parent / "examples" / "minimap" / "docs" / "designs" / "channel-muting.md"

    def lint_text(self, text: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            path.write_text(text, encoding="utf-8")
            proc, data = lint_json(path)
        data["returncode"] = proc.returncode
        return data

    def shipped(self, path: Path, status: str) -> str:
        text = path.read_text(encoding="utf-8")
        out = text.replace(f"Status: {status}\n", self.SHIPPED + "\n", 1)
        self.assertNotEqual(out, text)
        return out

    def test_rows_with_no_row_cell_and_no_red_gate_are_an_error(self) -> None:
        # The C4 repro, lint half: conforming.md's rows cite no map row.
        data = self.lint_text(self.shipped(BUILDING_NO_GATE, "building"))
        found = [f for f in data["findings"] if f["rule"] == "SHIPPED_NEEDS_GATE"]
        self.assertEqual([f["line"] for f in found], [79, 80, 81], data["findings"])
        self.assertEqual({f["severity"] for f in found}, {"error"})
        self.assertIn("AT-1 has no red run and no 'Kill:' line, and cites no row", found[0]["message"])
        self.assertEqual(data["returncode"], 1)
        self.assertNotIn("BUILDING_NEEDS_GATE", {f["rule"] for f in data["findings"]})

    def test_a_red_gate_line_clears_it(self) -> None:
        text = self.shipped(BUILDING_NO_GATE, "building").replace(
            "Supersedes: —\n", "Supersedes: —\nRed gate: a1b2c3d 2026-01-02\n", 1
        )
        data = self.lint_text(text)
        self.assertEqual(data["findings"], [])
        self.assertEqual(data["returncode"], 0)

    def test_a_red_gate_line_with_a_date_that_does_not_exist_does_not_clear_it(self) -> None:
        text = self.shipped(BUILDING_NO_GATE, "building").replace(
            "Supersedes: —\n", "Supersedes: —\nRed gate: a1b2c3d 2026-02-31\n", 1
        )
        rules = [f["rule"] for f in self.lint_text(text)["findings"]]
        self.assertEqual(rules, ["SHIPPED_NEEDS_GATE"] * 3)

    def test_every_row_cited_is_left_to_bridge_validate(self) -> None:
        # Every §6 line has a Row: whether each is a proven backfilled row
        # is in the map, which bridge_validate.py reads.
        data = self.lint_text(self.shipped(self.MINIMAP_DOC, "agreed"))
        self.assertEqual(data["findings"], [])

    def test_other_statuses_are_not_touched(self) -> None:
        data = self.lint_text(BUILDING_NO_GATE.read_text(encoding="utf-8").replace(
            "Status: building\n", "Status: draft\n", 1))
        self.assertNotIn("SHIPPED_NEEDS_GATE", {f["rule"] for f in data["findings"]})


if __name__ == "__main__":
    unittest.main()
