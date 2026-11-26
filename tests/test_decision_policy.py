"""Tests for the decision policy (outcome-framework.md § Decision policy).

A doc's `Decision policy:` header line (`fast`, `auto` or `spec`, picked by the
human) says which decisions the agent asks and which it records in §8 as a row with
Owner `agent`. The lint checks the value and each agent row; `decisions.py` shows the
provisional rows as a read-only "Decided for you" group, turns an "Ask me instead"
into a §9 question, and applies the switching rules. A doc with no line is a legacy
doc: it behaves as `spec`, and lints exactly as it did.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import List, Optional

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parent
SCRIPTS = REPO / "skills" / "promise" / "scripts"
LINT = SCRIPTS / "lint_outcome.py"
DECISIONS = SCRIPTS / "decisions.py"
RENDER = SCRIPTS / "render_outcome.py"
ORIENT = SCRIPTS / "orient.py"
CONFORMING = TESTS_DIR / "fixtures" / "conforming.md"
EXAMPLE = REPO / "examples" / "key-tabs.md"
TEMPLATE = REPO / "skills" / "promise" / "templates" / "outcome-doc.md"

OWNER = "Owner: Ollie        Last decision: 2026-01-01\n"
ROW1 = ("| 1 | 2026-01-01 | Mute state is per member, not per channel. | Ollie | Matches how every reference "
        "product does it; a shared mute would surprise someone. |\n")

sys.path.insert(0, str(SCRIPTS))
import lint_outcome  # noqa: E402


def run(script: Path, *args: str, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True,
                          encoding="utf-8", cwd=str(cwd) if cwd else None)


def agent_row(decision: str = "The mute item sits at the top of the channel menu.", *, n: int = 2,
              category: str = "layout", because: str = "members look there first",
              rollback: Optional[str] = "move the menu item back", until: str = "public release",
              review: str = "before public release", state: str = "provisional", date: str = "2026-01-02") -> str:
    fields = [f"Category: {category}.", f"Because: {because}."]
    if rollback is not None:
        fields.append(f"Rollback: {rollback}.")
    fields += [f"Reversible until: {until}.", f"Review: {review}.", f"State: {state}."]
    return f"| {n} | {date} | {decision} | agent | {' '.join(fields)} |"


def doc(policy: Optional[str] = None, rows: List[str] = ()) -> str:
    text = CONFORMING.read_text(encoding="utf-8")
    if policy is not None:
        text = text.replace(OWNER, OWNER + f"Decision policy: {policy}\n", 1)
    return text.replace(ROW1, ROW1 + "".join(r + "\n" for r in rows), 1)


def findings(text: str) -> List[dict]:
    return lint_outcome.lint_lines(text.splitlines(), strict=False)


def rules(text: str) -> List[str]:
    return sorted({f["rule"] for f in findings(text)})


def messages(text: str, rule: str) -> List[str]:
    return [f["message"] for f in findings(text) if f["rule"] == rule]


class PolicyValue(unittest.TestCase):
    def test_each_policy_value_lints_clean(self) -> None:
        for value in ("fast", "auto", "spec"):
            with self.subTest(value=value):
                self.assertEqual(findings(doc(value)), [])

    def test_the_legacy_prototype_value_is_read_as_fast_and_warned(self) -> None:
        text = doc("prototype")
        self.assertEqual(rules(text), ["DECISION_POLICY_ALIAS"])
        self.assertEqual({f["severity"] for f in findings(text)}, {"warn"})
        self.assertIn("write 'Decision policy: fast'", messages(text, "DECISION_POLICY_ALIAS")[0])
        self.assertEqual(lint_outcome.get_decision_policy(text.splitlines()), "fast")
        self.assertEqual(lint_outcome.get_decision_policy(doc("fast").splitlines()), "fast")

    def test_the_legacy_value_ranks_as_fast(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        import decisions  # noqa: PLC0415
        self.assertEqual(decisions.POLICY_RANK["prototype"], decisions.POLICY_RANK["fast"])
        self.assertLess(decisions.POLICY_RANK["fast"], decisions.POLICY_RANK["auto"])

    def test_a_value_outside_the_three_is_an_error(self) -> None:
        for value in ("quick", "Auto", "auto spec", "depth"):
            with self.subTest(value=value):
                self.assertEqual(rules(doc(value)), ["DECISION_POLICY"])

    def test_two_policy_lines_are_an_error(self) -> None:
        text = doc("auto").replace("Decision policy: auto\n", "Decision policy: auto\nDecision policy: spec\n", 1)
        self.assertEqual(rules(text), ["DECISION_POLICY"])

    def test_the_template_placeholder_is_a_placeholder_until_the_human_picks(self) -> None:
        text = doc("<fast | auto | spec>")
        self.assertEqual(rules(text), ["PLACEHOLDER"])
        self.assertIn("ask the human", messages(text, "PLACEHOLDER")[0])

    def test_a_policy_line_below_the_header_is_not_the_policy(self) -> None:
        text = doc().replace("## 10. Out of scope\n", "## 10. Out of scope\n\nDecision policy: fast\n", 1)
        self.assertEqual(findings(text), [])
        self.assertIsNone(lint_outcome.get_decision_policy(text.splitlines()))

    def test_depth_thin_is_untouched_and_separate(self) -> None:
        # `Depth:` keeps its own meaning; the policy is its own line.
        self.assertEqual(rules(doc("auto").replace("Supersedes: —\n", "Supersedes: —\nDepth: deep\n", 1)),
                         ["THIN_DRAFT"])


class LegacyDocs(unittest.TestCase):
    def test_a_doc_with_no_policy_line_lints_as_before(self) -> None:
        self.assertEqual(findings(doc()), [])
        self.assertEqual(lint_outcome.effective_policy(doc().splitlines()), "spec")

    def test_the_shipped_examples_lint_clean_under_strict(self) -> None:
        for path in (REPO / "examples" / "channel-muting.md", EXAMPLE):
            with self.subTest(doc=path.name):
                result = run(LINT, "--strict", str(path))
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_legacy_doc_with_an_asked_agent_row_is_fine(self) -> None:
        self.assertEqual(findings(doc(rows=[agent_row(state="asked Q1")])), [])

    def test_an_invalid_policy_reads_as_spec(self) -> None:
        text = doc("quick", [agent_row()])
        self.assertEqual(rules(text), ["AGENT_DECISION_UNRATIFIED", "DECISION_POLICY"])


class AgentRowFields(unittest.TestCase):
    def test_a_well_formed_row_is_clean_under_auto_and_fast(self) -> None:
        for policy in ("auto", "fast"):
            with self.subTest(policy=policy):
                self.assertEqual(findings(doc(policy, [agent_row()])), [])
        # The old name reads as fast: the row is clean, and the one finding is the alias warning.
        self.assertEqual([(f["rule"], f["severity"]) for f in findings(doc("prototype", [agent_row()]))],
                         [("DECISION_POLICY_ALIAS", "warn")])

    def test_a_missing_field_is_named(self) -> None:
        text = doc("auto", [agent_row(rollback=None)])
        self.assertEqual(rules(text), ["AGENT_DECISION_FIELDS"])
        self.assertIn("no Rollback:", messages(text, "AGENT_DECISION_FIELDS")[0])

    def test_every_field_is_required(self) -> None:
        full = agent_row()
        for label in ("Category", "Because", "Rollback", "Reversible until", "Review", "State"):
            with self.subTest(label=label):
                row = re.sub(re.escape(label) + r": [^.]*\. ?", "", full, count=1)
                self.assertIn("AGENT_DECISION_FIELDS", rules(doc("auto", [row])))

    def test_a_label_given_twice_or_empty_is_an_error(self) -> None:
        twice = agent_row(because="members look there first. Because: and it is quick")
        self.assertIn("twice", " ".join(messages(doc("auto", [twice]), "AGENT_DECISION_FIELDS")))
        empty = agent_row(rollback="")
        self.assertIn("no Rollback:", " ".join(messages(doc("auto", [empty]), "AGENT_DECISION_FIELDS")))

    def test_the_review_trigger_is_concrete(self) -> None:
        for good in ("before arm", "before public release", "on 2026-03-01", "after 20 uses", "after 1 use"):
            with self.subTest(good=good):
                self.assertEqual(findings(doc("auto", [agent_row(review=good)])), [])
        for bad in ("after use", "later", "when we have data", "on 2026-02-31", "after 0 uses"):
            with self.subTest(bad=bad):
                self.assertEqual(rules(doc("auto", [agent_row(review=bad)])), ["AGENT_DECISION_FIELDS"])

    def test_the_date_state_and_category_are_checked(self) -> None:
        cases = {
            "date": agent_row(date="soon"),
            "state": agent_row(state="confirmed"),
            "asked": agent_row(state="asked Q9"),
            "category": agent_row(category="cosmetic"),
        }
        for name, row in cases.items():
            with self.subTest(case=name):
                self.assertEqual(rules(doc("auto", [row])), ["AGENT_DECISION_FIELDS"])

    def test_only_rows_owned_by_the_agent_are_read(self) -> None:
        human = "| 2 | 2026-01-02 | Muting has no limit. | Ollie | Nobody asked for one. |"
        self.assertEqual(findings(doc("spec", [human])), [])
        self.assertEqual(lint_outcome.parse_agent_decisions(doc("auto", [human]).splitlines()), [])


class ProtectedCategories(unittest.TestCase):
    def test_a_provisional_row_in_any_protected_category_is_an_error_at_every_policy(self) -> None:
        for category in lint_outcome.PROTECTED_CATEGORIES:
            for policy in ("fast", "auto"):
                with self.subTest(category=category, policy=policy):
                    self.assertEqual(rules(doc(policy, [agent_row(category=category)])),
                                     ["AGENT_DECISION_PROTECTED"])

    def test_a_protected_row_already_asked_is_fine(self) -> None:
        self.assertEqual(findings(doc("auto", [agent_row(category="money", state="asked Q1")])), [])


class SpecMeansAsk(unittest.TestCase):
    def test_a_provisional_row_under_spec_is_unratified(self) -> None:
        text = doc("spec", [agent_row()])
        self.assertEqual(rules(text), ["AGENT_DECISION_UNRATIFIED"])
        self.assertIn("Decision policy: spec", messages(text, "AGENT_DECISION_UNRATIFIED")[0])

    def test_a_provisional_row_on_a_legacy_doc_is_unratified(self) -> None:
        text = doc(None, [agent_row()])
        self.assertEqual(rules(text), ["AGENT_DECISION_UNRATIFIED"])
        self.assertIn("read as spec", messages(text, "AGENT_DECISION_UNRATIFIED")[0])

    def test_a_row_asked_under_spec_is_fine(self) -> None:
        self.assertEqual(findings(doc("spec", [agent_row(state="asked Q1")])), [])


class AdversarialCategories(unittest.TestCase):
    """A script cannot prove a category honest. These are the framework's own examples:
    what the lint accepts, what it rejects, and what it only warns about."""

    def test_rename_a_button_is_the_agents(self) -> None:
        row = agent_row('The button reads "Save changes", not "Save".', category="wording",
                        because="it says what happens")
        self.assertEqual(findings(doc("auto", [row])), [])

    def test_tab_order_is_the_agents(self) -> None:
        row = agent_row("The tabs sit in the order Personal, Team, Service.", category="order",
                        because="most people look for their own first")
        self.assertEqual(findings(doc("auto", [row])), [])

    def test_rename_the_api_field_declared_honestly_is_protected(self) -> None:
        row = agent_row("The response field is renamed to mutedUntil.", category="contract",
                        because="it reads well")
        self.assertEqual(rules(doc("auto", [row])), ["AGENT_DECISION_PROTECTED"])

    def test_rename_the_api_field_filed_as_naming_is_flagged(self) -> None:
        row = agent_row("Rename the API field to mutedUntil.", category="naming", because="it reads well")
        text = doc("auto", [row])
        self.assertEqual([(f["rule"], f["severity"]) for f in findings(text)], [("AGENT_DECISION_WORDS", "warn")])
        self.assertIn("'api'", messages(text, "AGENT_DECISION_WORDS")[0])
        self.assertEqual(run_lint_strict_code(text), 1)

    def test_retention_from_twelve_to_six_months_is_protected_or_flagged(self) -> None:
        honest = agent_row("Client memory is kept 6 months, not 12.", category="data-retention",
                           because="less to store")
        self.assertEqual(rules(doc("auto", [honest])), ["AGENT_DECISION_PROTECTED"])
        disguised = agent_row("Change retention from 12 to 6 months.", category="default", because="less to store")
        self.assertEqual(rules(doc("auto", [disguised])), ["AGENT_DECISION_WORDS"])

    def test_the_framework_carries_the_examples(self) -> None:
        text = " ".join((REPO / "skills" / "promise" / "outcome-framework.md").read_text(encoding="utf-8").split())
        for phrase in ("Rename a field in the public API response", "Keep client memory for 6 months, not 12",
                       "The order of the tabs on a settings page", "doubt about the category means ask",
                       "A script cannot prove a category honest"):
            self.assertIn(phrase, text)


def run_lint_strict_code(text: str) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "doc.md"
        path.write_text(text, encoding="utf-8")
        return run(LINT, "--strict", str(path)).returncode


class RenderAndOrient(unittest.TestCase):
    def render(self, *extra: str) -> subprocess.CompletedProcess:
        return run(RENDER, "--title", "Channel muting", "--owner", "Ollie", "--date", "2026-01-01",
                   "--docs-home", "unused", "--dry-run", *extra)

    def test_policy_fills_the_header_line(self) -> None:
        result = self.render("--policy", "auto")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("\nOwner: Ollie        Last decision: 2026-01-01\nDecision policy: auto\nSupersedes: —\n",
                      result.stdout)

    def test_without_policy_the_placeholder_stays_and_the_lint_asks_for_it(self) -> None:
        result = self.render()
        self.assertIn("Decision policy: <fast | auto | spec>", result.stdout)
        placeholder = [f for f in findings(result.stdout) if f["rule"] == "PLACEHOLDER" and "Decision policy" in f["message"]]
        self.assertEqual(len(placeholder), 1)

    def test_an_unknown_policy_is_refused(self) -> None:
        self.assertEqual(self.render("--policy", "quick").returncode, 2)

    def test_policy_fast_is_written_and_the_old_name_is_written_as_fast(self) -> None:
        for value in ("fast", "prototype"):
            result = self.render("--policy", value)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("\nDecision policy: fast\n", result.stdout)
            self.assertNotIn("prototype", result.stdout)

    def test_thin_render_keeps_the_policy(self) -> None:
        self.assertIn("Decision policy: spec", self.render("--thin", "--policy", "spec").stdout)

    def test_the_template_lints_under_template(self) -> None:
        self.assertEqual(run(LINT, "--template", str(TEMPLATE)).returncode, 0)

    def test_orient_reports_each_docs_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "docs" / "designs"
            home.mkdir(parents=True)
            (home / "a.md").write_text(doc("auto"), encoding="utf-8")
            (home / "b.md").write_text(doc(), encoding="utf-8")
            (home / "c.md").write_text(doc("quick"), encoding="utf-8")
            (home / "d.md").write_text(doc("prototype"), encoding="utf-8")
            (home / "e.md").write_text(doc("fast"), encoding="utf-8")
            data = json.loads(run(ORIENT, "--cwd", tmp).stdout)
            self.assertEqual({d["path"]: d["decisionPolicy"] for d in data["existingDocs"]},
                             {"docs/designs/a.md": "auto", "docs/designs/b.md": None, "docs/designs/c.md": None,
                              "docs/designs/d.md": "fast", "docs/designs/e.md": "fast"})


class Project(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.doc = self.root / "docs" / "muting.md"
        self.doc.parent.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, text: str) -> None:
        self.doc.write_text(text, encoding="utf-8")

    def decisions(self, *args: str) -> subprocess.CompletedProcess:
        return run(DECISIONS, *args, cwd=self.root)

    def sheet(self, *args: str) -> dict:
        result = self.decisions("sheet", "docs/muting.md", "--json", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def text(self) -> str:
        return self.doc.read_text(encoding="utf-8")

    def section0_and_status(self, text: str) -> tuple:
        lines = text.splitlines()
        start, end = lint_outcome.tldr_block_bounds(lines)
        return lines[start:end], lint_outcome.get_status(lines)


TWO_ROWS = [agent_row(), agent_row('The mute item reads "Mute channel".', n=3, category="wording",
                                   because="it matches the other menu items", rollback="change the label",
                                   until="arm", review="before arm")]


class DecidedForYou(Project):
    def test_a_doc_without_agent_rows_gets_the_sheet_it_always_got(self) -> None:
        self.write(doc("auto"))
        sheet = self.sheet()
        self.assertNotIn("decided", sheet["counts"])
        self.assertEqual([i["kind"] for i in sheet["items"]], ["question"])
        self.write(doc())
        self.assertEqual(self.sheet()["counts"], sheet["counts"])

    def test_provisional_rows_are_one_read_only_group_outside_the_round(self) -> None:
        self.write(doc("auto", TWO_ROWS + [agent_row("Asked already.", n=4, state="asked Q1")]))
        sheet = self.sheet()
        decided = [i for i in sheet["items"] if i["kind"] == "decided"]
        self.assertEqual([i["id"] for i in decided], ["docs/muting.md#D2", "docs/muting.md#D3"])
        self.assertTrue(all(i["group"] == "Decided for you" for i in decided))
        self.assertEqual(decided[0]["rollback"], "move the menu item back")
        self.assertEqual(decided[1]["review"], "before arm")
        self.assertEqual(sheet["counts"]["decided"], 2)
        self.assertEqual(sheet["counts"]["round"], 1)
        self.assertEqual(sheet["counts"]["later"], 0)
        # the round is one plain question, so the decided group never makes it a page
        self.assertEqual(sheet["surface"], "ask-questions")
        self.assertEqual(sheet["warnings"], [])

    def test_blocking_only_leaves_the_group_out_and_only_can_pick_one(self) -> None:
        self.write(doc("auto", TWO_ROWS))
        self.assertEqual(self.sheet("--blocking-only")["items"], [])
        only = self.sheet("--only", "docs/muting.md#D3")
        self.assertEqual([i["id"] for i in only["items"]], ["docs/muting.md#D3"])

    def test_every_surface_shows_the_group(self) -> None:
        self.write(doc("auto", TWO_ROWS))
        chat = self.decisions("sheet", "docs/muting.md", "--chat", "-")
        self.assertIn("**Decided for you.**", chat.stdout)
        self.assertIn("a) Ask me instead", chat.stdout)
        self.assertIn("Rollback: move the menu item back", chat.stdout)
        md = self.root / "twin.md"
        self.decisions("sheet", "docs/muting.md", "--md", str(md))
        twin = md.read_text(encoding="utf-8")
        self.assertIn("## Decided for you", twin)
        self.assertIn("**Reversible until:** arm", twin)
        page = self.root / "page.html"
        self.decisions("sheet", "docs/muting.md", "--out", str(page))
        html = page.read_text(encoding="utf-8")
        self.assertIn('"kind": "decided"', html)
        self.assertIn("decidedControls", html)
        prompt = json.loads(self.decisions("sheet", "docs/muting.md", "--prompt-json").stdout)
        # beside one plain question, the agent's decisions are listed, not asked
        self.assertEqual(self.sheet()["surface"], "ask-questions")
        self.assertEqual([e["id"] for b in prompt["batches"] for e in b], ["docs/muting.md#Q1"])
        self.assertEqual([d["id"] for d in prompt["decided"]], ["docs/muting.md#D2", "docs/muting.md#D3"])
        self.assertEqual(prompt["decided"][0]["askInstead"], "2a")

    def test_all_recommended_never_overrides_an_agent_decision(self) -> None:
        self.write(doc("auto", TWO_ROWS))
        sheet_file = self.root / "sheet.json"
        sheet_file.write_text(json.dumps(self.sheet()), encoding="utf-8")
        reply = self.root / "reply.txt"
        reply.write_text("all recommended", encoding="utf-8")
        before = self.text()
        result = self.decisions("apply", "--reply", str(reply), "--sheet", str(sheet_file), "--by", "Ollie")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.text(), before)

    def test_ask_me_instead_becomes_a_blocking_question_and_the_row_says_so(self) -> None:
        self.write(doc("auto", TWO_ROWS))
        before = self.text()
        sheet_file = self.root / "sheet.json"
        sheet_file.write_text(json.dumps(self.sheet()), encoding="utf-8")
        reply = self.root / "reply.txt"
        reply.write_text("2a - put it at the bottom", encoding="utf-8")
        result = self.decisions("apply", "--reply", str(reply), "--sheet", str(sheet_file), "--by", "Ollie",
                                "--date", "2026-01-05")
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.text()
        questions = {q["q"]: q for q in lint_outcome.parse_questions(text.splitlines())}
        self.assertTrue(questions["Q2"]["blocking"])
        self.assertEqual(questions["Q2"]["owner"], "Ollie")
        self.assertIn("The mute item sits at the top of the channel menu", questions["Q2"]["text"])
        self.assertIn("Why asked (2026-01-05, Ollie): Ollie chose to decide it: put it at the bottom.", text)
        self.assertIn("State: asked Q2.", text)
        self.assertIn("State: provisional.", text)  # the other row stands
        self.assertEqual(findings(text), [])
        # Nothing above §9 changed but the one row's state; §0 and Status never.
        self.assertEqual(self.section0_and_status(text), self.section0_and_status(before))
        self.assertEqual(before.split("## 9.")[0].replace("State: provisional. |\n| 3", "State: asked Q2. |\n| 3", 1),
                         text.split("## 9.")[0])
        # Q1 and its text are untouched: the question is appended, like an answer.
        self.assertEqual(before.split("## 9. Open questions")[1].split("## 10.")[0].rstrip(),
                         text.split("## 9. Open questions")[1].split("Q2 —")[0].rstrip())
        # A second apply asks nothing twice.
        again = self.decisions("apply", "--reply", str(reply), "--sheet", str(sheet_file), "--by", "Ollie")
        self.assertIn("already asked Q2", again.stdout)
        self.assertEqual(self.text(), text)

    def test_the_pages_answers_file_asks_the_same_way(self) -> None:
        self.write(doc("auto", TWO_ROWS))
        answers = self.root / "answers.json"
        answers.write_text(json.dumps({"format": "promise-answers", "version": 1, "answers": [
            {"id": "docs/muting.md#D3", "kind": "decided", "doc": "docs/muting.md", "q": None, "decision": "3",
             "value": "Ask me instead", "note": None}]}), encoding="utf-8")
        result = self.decisions("apply", str(answers), "--by", "Ana", "--date", "2026-01-05", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        written = json.loads(result.stdout)["written"]
        self.assertEqual([(w["q"], w["decision"]) for w in written], [("Q2", "3")])
        self.assertIn("State: asked Q2.", self.text())

    def test_an_override_naming_no_row_is_skipped(self) -> None:
        self.write(doc("auto", TWO_ROWS))
        answers = self.root / "answers.json"
        answers.write_text(json.dumps({"format": "promise-answers", "version": 1, "answers": [
            {"id": "x", "kind": "decided", "doc": "docs/muting.md", "decision": "9", "value": "Ask me instead"}]}),
            encoding="utf-8")
        result = self.decisions("apply", str(answers), "--by", "Ana", "--json")
        self.assertEqual(json.loads(result.stdout)["written"], [])
        self.assertIn("no agent decision", json.loads(result.stdout)["skipped"][0]["reason"])

    def test_the_example_doc_shows_three_decided_for_you(self) -> None:
        result = run(DECISIONS, "sheet", "examples/key-tabs.md", "--json", cwd=REPO)
        sheet = json.loads(result.stdout)
        self.assertEqual(sheet["counts"]["decided"], 3)
        self.assertNotIn("examples/key-tabs.md#D5", [i["id"] for i in sheet["items"]])  # asked, not decided


class Switching(Project):
    def test_tightening_to_spec_asks_every_provisional_decision(self) -> None:
        self.write(doc("auto", TWO_ROWS))
        before = self.text()
        result = self.decisions("policy", "docs/muting.md", "--to", "spec", "--by", "Ollie", "--date", "2026-01-07",
                                "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual((out["from"], out["to"], out["direction"]), ("auto", "spec", "tighter"))
        self.assertEqual([w["q"] for w in out["written"]], ["Q2", "Q3"])
        text = self.text()
        self.assertIn("Decision policy: spec\n", text)
        self.assertNotIn("State: provisional", text)
        self.assertIn("| Decision policy: spec (was auto). | Ollie |", text)
        self.assertEqual(findings(text), [])
        self.assertEqual(self.section0_and_status(text), self.section0_and_status(before))

    def test_fast_to_auto_promotes_what_the_agent_names_and_lists_the_rest(self) -> None:
        self.write(doc("fast", TWO_ROWS))
        out = json.loads(self.decisions("policy", "docs/muting.md", "--to", "auto", "--by", "Ollie", "--promote", "3",
                                        "--json").stdout)
        self.assertEqual([w["decision"] for w in out["written"]], ["3"])
        self.assertEqual(out["toJudge"], ["D2"])
        self.assertEqual(findings(self.text()), [])

    def test_relaxing_never_answers_an_open_question(self) -> None:
        text = doc("spec").replace("Q1 — owner: Ollie — non-blocking:", "Q1 — owner: Ollie — BLOCKING:", 1)
        self.write(text)
        out = json.loads(self.decisions("policy", "docs/muting.md", "--to", "fast", "--by", "Ollie",
                                        "--json").stdout)
        self.assertEqual(out["direction"], "looser")
        self.assertIn("Decision policy: fast\n", self.text())
        self.assertEqual(out["written"], [])
        self.assertEqual(out["openQuestions"], ["Q1"])
        after = self.text()
        self.assertFalse(lint_outcome.parse_questions(after.splitlines())[0]["answered"])
        self.assertEqual(after.split("## 9.")[1], text.split("## 9.")[1])

    def test_a_legacy_doc_gets_its_first_policy_line_under_owner(self) -> None:
        self.write(doc())
        out = json.loads(self.decisions("policy", "docs/muting.md", "--to", "auto", "--by", "Ollie", "--json").stdout)
        self.assertEqual((out["from"], out["direction"]), (None, "looser"))
        self.assertIn(OWNER + "Decision policy: auto\nSupersedes:", self.text())
        self.assertIn("(was none (read as spec))", self.text())

    def test_a_header_with_the_old_name_is_rewritten_to_fast(self) -> None:
        self.write(doc("prototype", TWO_ROWS))
        before = self.text()
        result = self.decisions("policy", "docs/muting.md", "--to", "fast", "--by", "Ollie", "--date", "2026-01-07",
                                "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual((out["from"], out["to"], out["direction"], out["written"]), ("prototype", "fast", "same", []))
        self.assertNotIn("openQuestions", out)
        text = self.text()
        self.assertIn("Decision policy: fast\n", text)
        self.assertNotIn("Decision policy: prototype", text)
        self.assertIn("| Decision policy: fast (was prototype). | Ollie |", text)
        self.assertEqual(text.count("State: provisional"), before.count("State: provisional"))
        self.assertEqual(findings(text), [])
        # and once it says fast, asking for fast again is refused
        self.assertEqual(self.decisions("policy", "docs/muting.md", "--to", "fast", "--by", "Ollie").returncode, 2)

    def test_to_prototype_writes_fast(self) -> None:
        self.write(doc("spec"))
        result = self.decisions("policy", "docs/muting.md", "--to", "prototype", "--by", "Ollie", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["to"], "fast")
        text = self.text()
        self.assertIn("Decision policy: fast\n", text)
        self.assertNotIn("prototype", text)

    def test_the_same_policy_again_and_a_blank_name_are_refused(self) -> None:
        self.write(doc("auto"))
        self.assertEqual(self.decisions("policy", "docs/muting.md", "--to", "auto", "--by", "Ollie").returncode, 2)
        self.assertEqual(self.decisions("policy", "docs/muting.md", "--to", "spec", "--by", " ").returncode, 2)

    def test_promote_by_hand_and_dry_run(self) -> None:
        self.write(doc("auto", TWO_ROWS))
        before = self.text()
        dry = json.loads(self.decisions("promote", "docs/muting.md", "--decision", "D2", "--by", "Ollie",
                                        "--dry-run", "--json").stdout)
        self.assertEqual([w["q"] for w in dry["written"]], ["Q2"])
        self.assertEqual(self.text(), before)
        self.decisions("promote", "docs/muting.md", "--decision", "2,3", "--by", "agent", "--reason",
                       "no longer cheap to reverse")
        self.assertEqual(self.text().count("State: asked Q"), 2)
        self.assertIn("Why asked", self.text())
        again = json.loads(self.decisions("promote", "docs/muting.md", "--decision", "2", "--by", "Ollie",
                                          "--json").stdout)
        self.assertEqual(again["written"], [])
        self.assertIn("already asked Q2", again["skipped"][0])

    def test_recheck_lists_what_is_due_at_arm(self) -> None:
        rows = TWO_ROWS + [agent_row("Old default.", n=4, category="default", until="2026-01-03",
                                     review="after 10 uses"),
                           agent_row("Dated review.", n=5, category="default", review="on 2026-02-01")]
        self.write(doc("auto", rows))
        out = json.loads(self.decisions("recheck", "docs/muting.md", "--date", "2026-01-10", "--json").stdout)
        self.assertEqual([d["id"] for d in out["due"]], ["D3", "D4"])
        later = json.loads(self.decisions("recheck", "docs/muting.md", "--date", "2026-03-01", "--json").stdout)
        self.assertEqual([d["id"] for d in later["due"]], ["D3", "D4", "D5"])


class StampOpenDocs(Project):
    """policy --open: one human yes writes the repo's policy into every doc in flight
    that has no line; orient's legacyPolicyDocs counts them."""

    DOCS = {"draft.md": ("draft", None), "agreed.md": ("agreed", None), "building.md": ("building", None),
            "shipped.md": ("shipped", None), "superseded.md": ("superseded", None),
            "has-line.md": ("draft", "spec"), "broken-line.md": ("agreed", "fast")}

    def setUp(self) -> None:
        super().setUp()
        for name, (status, policy) in self.DOCS.items():
            (self.root / "docs" / name).write_text(doc(policy).replace("Status: draft", f"Status: {status}", 1),
                                                   encoding="utf-8")
        (self.root / "docs" / "notes.md").write_text("# Notes\n\nStatus: draft\n", encoding="utf-8")
        self.before = {p.name: p.read_text(encoding="utf-8") for p in (self.root / "docs").iterdir()}

    def stamp(self, *args: str) -> subprocess.CompletedProcess:
        return self.decisions("policy", "--open", "--to", "auto", "--by", "Ollie", "--docs-home", "docs",
                              "--date", "2026-01-07", *args)

    def legacy_count(self) -> int:
        result = run(ORIENT, "--cwd", str(self.root))
        return json.loads(result.stdout)["legacyPolicyDocs"]

    def test_orient_counts_the_open_docs_with_no_line(self) -> None:
        self.assertEqual(self.legacy_count(), 3)

    def test_stamps_only_open_docs_with_no_line(self) -> None:
        result = self.stamp("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual([s["doc"] for s in out["stamped"]],
                         ["docs/agreed.md", "docs/building.md", "docs/draft.md"])
        self.assertEqual(out["skipped"], [])
        for name in ("draft.md", "agreed.md", "building.md"):
            text = (self.root / "docs" / name).read_text(encoding="utf-8")
            self.assertIn(OWNER + "Decision policy: auto\n", text)
            self.assertIn("| Decision policy: auto (was none (read as spec)). | Ollie |", text)
        for name in ("shipped.md", "superseded.md", "has-line.md", "broken-line.md", "notes.md"):
            self.assertEqual((self.root / "docs" / name).read_text(encoding="utf-8"), self.before[name], name)
        self.assertEqual(self.legacy_count(), 0)

    def test_dry_run_lists_and_writes_nothing(self) -> None:
        result = self.stamp("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("would write docs/building.md: Decision policy: auto (was none; building)", result.stdout)
        self.assertNotIn("shipped", result.stdout)
        self.assertEqual({p.name: p.read_text(encoding="utf-8") for p in (self.root / "docs").iterdir()},
                         self.before)
        self.assertEqual(self.legacy_count(), 3)

    def test_a_second_run_stamps_nothing(self) -> None:
        self.assertEqual(self.stamp().returncode, 0)
        after = {p.name: p.read_text(encoding="utf-8") for p in (self.root / "docs").iterdir()}
        again = self.stamp()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("nothing to stamp", again.stdout)
        self.assertEqual({p.name: p.read_text(encoding="utf-8") for p in (self.root / "docs").iterdir()}, after)

    def test_open_with_a_doc_or_promote_is_refused(self) -> None:
        self.assertEqual(self.stamp("docs/draft.md").returncode, 2)
        self.assertEqual(self.stamp("--promote", "2").returncode, 2)
        self.assertEqual(self.decisions("policy", "--to", "auto", "--by", "Ollie").returncode, 2)
        self.assertEqual({p.name: p.read_text(encoding="utf-8") for p in (self.root / "docs").iterdir()},
                         self.before)


class ModesSayIt(unittest.TestCase):
    """The rules a script cannot run live in the mode files: new asks once, first;
    revise asks only for a legacy doc or a change; arm re-checks."""

    def flat(self, name: str) -> str:
        return " ".join((REPO / "skills" / "promise" / name).read_text(encoding="utf-8").split())

    def test_new_takes_the_repos_policy_and_never_asks(self) -> None:
        text = self.flat("modes/new.md")
        self.assertLess(text.index("## The decision policy — taken, not asked"), text.index("## Elicit the human half"))
        for phrase in ("orient's `decisionPolicy`", "Never ask it", "render_outcome.py --policy",
                       '"write the full spec" is `spec`'):
            self.assertIn(phrase, text)
        self.assertNotIn("**Auto (Recommended)**", text)

    def test_revise_never_loosens_a_legacy_doc_itself(self) -> None:
        text = self.flat("modes/revise.md")
        for phrase in ("**A legacy doc**", "**The human asks to change it**", "Never write a policy on it yourself",
                       "a missing line may only make you ask more", "Never ask the three-choice question",
                       "never answer one because the policy now allows it"):
            self.assertIn(phrase, text)

    def test_revise_merges_its_two_lines_and_adopt_stamps_after_the_config(self) -> None:
        revise = self.flat("modes/revise.md")
        self.assertIn("Three cases touch it:", revise)
        self.assertIn("This doc is one of them → one line, not two", revise)
        adopt = self.flat("modes/adopt.md")
        self.assertIn("never before the config exists", adopt)

    def test_revise_and_adopt_offer_to_stamp_the_open_docs(self) -> None:
        for mode in ("modes/revise.md", "modes/adopt.md"):
            with self.subTest(mode=mode):
                text = self.flat(mode)
                for phrase in ("`legacyPolicyDocs` above zero", "predate the repo's policy and behave as spec",
                               "say so and I will stamp them", "decisions.py policy --open"):
                    self.assertIn(phrase, text)

    def test_orient_reads_the_repos_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".claude").mkdir()
            cfg = Path(tmp) / ".claude" / "promise.config.json"
            for value, want in (({}, ("auto", "default")), ({"decisionPolicy": "spec"}, ("spec", "config")),
                                ({"decisionPolicy": "fast"}, ("fast", "config")),
                                ({"decisionPolicy": "prototype"}, ("fast", "config")),
                                ({"decisionPolicy": "quick"}, ("auto", "default"))):
                with self.subTest(value=value):
                    cfg.write_text(json.dumps({"version": 1, **value}), encoding="utf-8")
                    out = json.loads(subprocess.run([sys.executable, str(REPO / "skills" / "promise" / "scripts"
                                                                         / "orient.py"), "--cwd", tmp],
                                                    capture_output=True, text=True).stdout)
                    self.assertEqual((out["decisionPolicy"], out["decisionPolicySource"]), want)

    def test_arm_rechecks_agent_decisions(self) -> None:
        text = self.flat("modes/arm.md")
        self.assertIn("decisions.py recheck", text)
        self.assertIn("arm waits for the answer", text)

    def test_skill_md_dispatches_on_the_policy_and_keeps_status_with_the_human(self) -> None:
        text = self.flat("SKILL.md")
        self.assertIn("`Decision policy:`", text)
        self.assertIn("`agreed` and `shipped` are typed by a human", text)

    def test_the_framework_says_what_agreed_means_with_agent_decisions(self) -> None:
        self.assertIn('means "permission to build them", not "the human chose them"',
                      self.flat("outcome-framework.md"))


if __name__ == "__main__":
    unittest.main()
