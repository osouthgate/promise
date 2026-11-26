"""Tests for decisions.py: the decision sheet and writing its answers back.

`sheet` collects the unanswered §9 questions and an asks file into one sheet with a
surface hint and renders the page; `apply` appends each answer under its question
as one dated line and touches nothing else.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parent
SCRIPT = REPO / "skills" / "promise" / "scripts" / "decisions.py"
CONFORMING = TESTS_DIR / "fixtures" / "conforming.md"
EXAMPLE_ASKS = REPO / "examples" / "decisions" / "asks.json"
ONBOARDING_ASKS = REPO / "examples" / "onboarding" / "asks.json"


class OnboardingAnswers(unittest.TestCase):
    def test_standalone_interview_uses_the_existing_sheet_and_creates_no_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sheet_result = run("sheet", "--docs-home", ".", "--asks", str(ONBOARDING_ASKS),
                               "--json", "--out", "interview.html", cwd=root)
            self.assertEqual(sheet_result.returncode, 0, sheet_result.stderr)
            sheet = json.loads(sheet_result.stdout)
            self.assertEqual(sheet["docs"], {})
            self.assertEqual(sheet["unclear"], [])
            self.assertEqual(len(sheet["items"]), 3)
            self.assertFalse(any(r["recommended"] for r in sheet["items"][0]["replies"]))
            (root / "sheet.json").write_text(sheet_result.stdout)
            replies = {item["id"]: index for index, item in enumerate(sheet["items"], 1)}
            reply = (f"{replies['starting-point']}: An established product\n"
                     f"{replies['first-workflow']}: A teacher imports reports; every row is accounted for.\n"
                     f"{replies['success-example']}: Two teachers receive only their own feedback.\n")
            (root / "reply.txt").write_text(reply)
            applied = run("apply", "--reply", "reply.txt", "--sheet", "sheet.json", "--json", cwd=root)
            self.assertEqual(applied.returncode, 0, applied.stderr)
            result = json.loads(applied.stdout)
            self.assertEqual(result["written"], [])
            self.assertEqual({item["id"] for item in result["forAgent"]},
                             {"starting-point", "first-workflow", "success-example"})
            self.assertFalse((root / ".claude").exists())
            self.assertFalse((root / "docs").exists())
            page = (root / "interview.html").read_text()
            self.assertIn("Start with one useful promise", page)

SECTION_9 = """## 9. Open questions

Q1 — owner: Ollie — BLOCKING: which plan tiers can mute
channels?

Q2 — owner: Ben — non-blocking: should muting sync across devices?
Answer (2026-01-02, Ben): yes, through the account settings.

Q3 — owner: Ana — non-blocking: is a muted channel greyed out?

## 10. Out of scope
"""


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=str(cwd))


def make_doc(root: Path, name: str = "muting.md", newline: str = "\n", bom: bool = False) -> Path:
    text = CONFORMING.read_text(encoding="utf-8")
    start = text.index("## 9. Open questions")
    end = text.index("## 10. Out of scope") + len("## 10. Out of scope\n")
    text = text[:start] + SECTION_9 + text[end:]
    path = root / "docs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.replace("\n", newline).encode("utf-8")
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)
    return path


def sheet_json(root: Path, *args: str) -> dict:
    result = run("sheet", "--docs-home", "docs", "--json", *args, cwd=root)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


class Sheet(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_doc(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_keeps_only_unanswered_questions_with_the_doc_fields(self) -> None:
        sheet = sheet_json(self.root)
        ids = [i["id"] for i in sheet["items"]]
        self.assertEqual(ids, ["docs/muting.md#Q1", "docs/muting.md#Q3"])
        q1 = sheet["items"][0]
        self.assertEqual((q1["owner"], q1["blocking"]), ("Ollie", True))
        self.assertEqual(q1["text"], "which plan tiers can mute channels?")
        self.assertEqual(q1["docStatus"], "draft")
        self.assertEqual(sheet["counts"], {"items": 2, "blocking": 1, "later": 0, "laterBlocking": 0,
                                           "round": 2, "unresearched": 2, "researched": 0,
                                           "settledTogether": 0})

    def test_an_answer_in_bold_or_italic_counts(self) -> None:
        doc = self.root / "docs" / "muting.md"
        text = doc.read_text(encoding="utf-8")
        for line in ("**Answer (Ollie, 2026-01-03, issue #96):** every tier.",
                     "_Answered 2026-01-03 by Ollie_: every tier.",
                     "  *Answer (2026-01-03)*: every tier."):
            with self.subTest(line=line):
                doc.write_text(text.replace("which plan tiers can mute\nchannels?\n",
                                            "which plan tiers can mute\nchannels?\n" + line + "\n"), encoding="utf-8")
                self.assertEqual([i["q"] for i in sheet_json(self.root)["items"]], ["Q3"])
                self.assertEqual(sheet_json(self.root, "--blocking-only")["items"], [])

    def test_an_answer_after_a_blank_line_counts(self) -> None:
        doc = self.root / "docs" / "muting.md"
        text = doc.read_text(encoding="utf-8")
        doc.write_text(text.replace("which plan tiers can mute\nchannels?\n",
                                    "which plan tiers can mute\nchannels?\n\nA note about tiers, not an answer.\n\n"
                                    "**Answer (Ollie, 2026-01-03, issue #96):** every tier.\n"), encoding="utf-8")
        sheet = sheet_json(self.root)
        self.assertEqual([i["q"] for i in sheet["items"]], ["Q3"])
        self.assertEqual(sheet_json(self.root, "--blocking-only")["items"], [])

    def test_a_paragraph_after_a_blank_line_is_not_question_text(self) -> None:
        doc = self.root / "docs" / "muting.md"
        text = doc.read_text(encoding="utf-8")
        doc.write_text(text.replace("which plan tiers can mute\nchannels?\n",
                                    "which plan tiers can mute\nchannels?\n\nSome later prose.\n"), encoding="utf-8")
        q1 = sheet_json(self.root)["items"][0]
        self.assertEqual(q1["text"], "which plan tiers can mute channels?")

    def test_apply_after_a_blank_line_answer_goes_under_the_last_answer(self) -> None:
        doc = self.root / "docs" / "muting.md"
        text = doc.read_text(encoding="utf-8").replace(
            "Answer (2026-01-02, Ben): yes, through the account settings.",
            "\nAnswer (2026-01-02, Ben): yes, through the account settings.")
        doc.write_text(text, encoding="utf-8")
        answers = self.root / "a.json"
        answers.write_text(json.dumps({"format": "promise-answers", "version": 1, "answers": [
            {"id": "docs/muting.md#Q2", "doc": "docs/muting.md", "q": "Q2", "value": "and on the web"}]}),
            encoding="utf-8")
        result = run("apply", str(answers), "--date", "2026-01-05", cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = doc.read_text(encoding="utf-8").splitlines()
        at = lines.index("Answer (2026-01-05): and on the web")
        self.assertEqual(lines[at - 1], "Answer (2026-01-02, Ben): yes, through the account settings.")

    def test_blocking_only(self) -> None:
        sheet = sheet_json(self.root, "--blocking-only")
        self.assertEqual([i["q"] for i in sheet["items"]], ["Q1"])

    def write_asks(self, data: dict) -> str:
        path = self.root / "asks.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return str(path)

    def test_asks_enrich_a_question_but_never_change_its_doc_fields(self) -> None:
        asks = self.write_asks({"items": [
            {"id": "docs/muting.md#Q1", "text": "rewritten", "owner": "Ben", "blocking": False,
             "detail": "Only paid tiers mute today.",
             "options": [{"label": "Every tier", "recommended": True}, {"label": "Paid tiers only"}]},
            {"id": "docs/muting.md#Q2", "detail": "already answered, so dropped"},
        ]})
        items = sheet_json(self.root, "--asks", asks)["items"]
        q1 = items[0]
        self.assertEqual((q1["text"], q1["owner"], q1["blocking"]), ("which plan tiers can mute channels?", "Ollie", True))
        self.assertEqual(q1["detail"], "Only paid tiers mute today.")
        self.assertEqual(len(q1["options"]), 2)
        self.assertEqual(len(items), 2)

    def test_asks_add_decisions_outside_the_docs(self) -> None:
        asks = self.write_asks({"title": "Muting", "items": [
            {"id": "copy", "kind": "approve", "text": "Approve the copy"},
            {"id": "limit", "kind": "input", "text": "Mute limit?", "proposed": 500},
        ]})
        sheet = sheet_json(self.root, "--asks", asks)
        self.assertEqual(sheet["title"], "Muting")
        self.assertEqual([i["id"] for i in sheet["items"]][-2:], ["copy", "limit"])

    def test_bad_asks_are_refused_with_one_line(self) -> None:
        cases = [
            {"items": [{"id": "x", "kind": "vote", "text": "t"}]},
            {"items": [{"id": "x", "kind": "question"}]},
            {"items": [{"kind": "question", "text": "t"}]},
            {"items": [{"id": "x", "kind": "question", "text": "t", "image": "javascript:alert(1)"}]},
            {"items": [{"id": "x", "kind": "question", "text": "t",
                        "options": [{"label": "a", "recommended": True}, {"label": "b", "recommended": True}]}]},
            {"items": [{"id": "x", "kind": "approve", "text": "t"}, {"id": "x", "kind": "approve", "text": "t"}]},
        ]
        for data in cases:
            result = run("sheet", "--docs-home", "docs", "--asks", self.write_asks(data), cwd=self.root)
            self.assertEqual(result.returncode, 2, data)
            self.assertEqual(len(result.stderr.strip().splitlines()), 1, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_surface_hint(self) -> None:
        self.assertEqual(sheet_json(self.root)["surface"], "ask-questions")
        asks = self.write_asks({"items": [{"id": "docs/muting.md#Q1", "code": "- a\n+ b"}]})
        self.assertEqual(sheet_json(self.root, "--asks", asks)["surface"], "rich")
        many = self.write_asks({"items": [{"id": f"a{n}", "kind": "approve", "text": "t"} for n in range(3)]})
        self.assertEqual(sheet_json(self.root, "--asks", many)["surface"], "rich")
        empty = Path(self.tmp.name) / "empty"
        (empty / "docs").mkdir(parents=True)
        self.assertEqual(sheet_json(empty)["surface"], "none")

    def test_page_embeds_the_sheet_safely(self) -> None:
        asks = self.write_asks({"title": "A <b> title", "items": [
            {"id": "x", "kind": "approve", "text": "</script><script>alert(1)</script>"}]})
        out = self.root / "sheet.html"
        result = run("sheet", "--docs-home", "docs", "--asks", asks, "--out", str(out), cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        html = out.read_text(encoding="utf-8")
        self.assertTrue(html.startswith("<title>A &lt;b&gt; title</title>"))
        self.assertNotIn("<!doctype", html.lower())
        self.assertEqual(html.lower().count("</script>"), 2)
        self.assertNotIn("__PROMISE_SHEET__", html)
        data = re.search(r'<script type="application/json" id="promise-sheet">(.*?)</script>', html, re.S).group(1)
        self.assertEqual(json.loads(data)["items"][-1]["text"], "</script><script>alert(1)</script>")

    def test_brief_doc_promise_and_warnings(self) -> None:
        sheet = sheet_json(self.root)
        self.assertEqual(sheet["items"][0]["ifNoAnswer"], "The doc stays at draft until this is answered.")
        self.assertNotIn("ifNoAnswer", sheet["items"][1])
        doc = sheet["docs"]["docs/muting.md"]
        self.assertTrue(doc["outcome"])
        self.assertTrue(doc["rules"])
        self.assertTrue(doc["signal"])
        self.assertEqual(sheet["warnings"], [])  # an ask-questions sheet is not checked
        asks = self.write_asks({"items": [
            {"id": "docs/muting.md#Q1", "code": "x", "why": "w", "blocks": "b",
             "evidence": [{"ref": "docs/muting.md:3", "note": "n"}],
             "options": [{"label": "A", "because": "c", "then": "t"}, {"label": "B"}]}]})
        sheet = sheet_json(self.root, "--asks", asks)
        self.assertEqual(sheet["items"][0]["evidence"], [{"ref": "docs/muting.md:3", "note": "n"}])
        self.assertIn("docs/muting.md#Q1: option 'B' has no because or then", sheet["warnings"])
        self.assertIn("docs/muting.md#Q3: no why or blocks", sheet["warnings"])
        self.assertFalse(any(w.startswith("docs/muting.md#Q1: no") for w in sheet["warnings"]))
        bad = self.write_asks({"items": [{"id": "docs/muting.md#Q1", "evidence": ["muting.md:3"]}]})
        self.assertEqual(run("sheet", "--docs-home", "docs", "--asks", bad, cwd=self.root).returncode, 2)

    def test_md_writes_a_markdown_twin_and_the_summary_names_blocking_items(self) -> None:
        asks = self.write_asks({"title": "Muting", "items": [
            {"id": "docs/muting.md#Q1", "why": "Only paid tiers mute today.", "blocks": "The pricing page.",
             "options": [{"label": "Paid tiers only", "because": "b"}, {"label": "Every tier", "recommended": True,
                                                                        "because": "a", "then": "t"}]},
            {"id": "copy", "kind": "approve", "text": "Approve the copy", "code": "a ```fence``` inside"}]})
        out = self.root / "sheet.html"
        result = run("sheet", "--docs-home", "docs", "--asks", asks, "--out", str(out), cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "sheet.md").exists(), "the twin is for agents: only --md writes it")
        result = run("sheet", "--docs-home", "docs", "--asks", asks, "--md", "sheet.md", cwd=self.root)
        self.assertIn("blocking: docs/muting.md#Q1: which plan tiers can mute channels?", result.stdout)
        md = (self.root / "sheet.md").read_text(encoding="utf-8")
        self.assertTrue(md.startswith("# Muting\n"))
        self.assertIn("### 1 · Q1 · BLOCKING · owner: Ollie", md)
        self.assertIn("id: `docs/muting.md#Q1`", md)
        first = md.index("- a) **Every tier** (Recommended) — a")
        self.assertLess(first, md.index("- b) **None of these"))
        self.assertLess(md.index("- b) **None of these"), md.index("- c) **Paid tiers only** — b"))
        self.assertIn("- Every tier, then: t", md)
        self.assertIn("````\na ```fence``` inside\n````", md)
        self.assertIn("Reply with `all recommended`", md)
        sheet = json.loads(run("sheet", "--docs-home", "docs", "--asks", asks, "--json", cwd=self.root).stdout)
        self.assertEqual(sheet["items"][0]["choices"], ["Every tier", None, "Paid tiers only"])
        self.assertEqual(run("sheet", "--docs-home", "docs", "--out", str(self.root / "x.md"), cwd=self.root).returncode, 2)
        same = self.root / "same.html"
        self.assertEqual(run("sheet", "--docs-home", "docs", "--out", str(same), "--md", str(same),
                             cwd=self.root).returncode, 2)
        only_md = self.root / "only.md"
        result = run("sheet", "--docs-home", "docs", "--md", str(only_md), cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("· Q3 · non-blocking", only_md.read_text(encoding="utf-8"))

    def test_markdown_twin_carries_images_and_option_detail(self) -> None:
        asks = self.write_asks({"items": [
            {"id": "a", "kind": "approve", "text": "Approve the mockup", "image": "https://example.test/m.png",
             "imageAlt": "the toggle"},
            {"id": "b", "kind": "approve", "text": "Approve the chart", "image": "data:image/png;base64,AAAA"},
            {"id": "docs/muting.md#Q1", "options": [{"label": "Every tier", "detail": "one price for all"}]}]})
        md_path = self.root / "t.md"
        self.assertEqual(run("sheet", "--docs-home", "docs", "--asks", asks, "--md", str(md_path),
                             cwd=self.root).returncode, 0)
        md = md_path.read_text(encoding="utf-8")
        self.assertIn("Image: [the toggle](https://example.test/m.png)", md)
        self.assertIn("An image goes with this item; it shows on the HTML page, not here.", md)
        self.assertNotIn("data:image", md)
        self.assertIn("- Every tier, detail: one price for all", md)

    def test_missing_doc_and_docs_home_are_refused(self) -> None:
        self.assertEqual(run("sheet", "docs/nope.md", cwd=self.root).returncode, 2)
        self.assertEqual(run("sheet", "--docs-home", "nowhere", cwd=self.root).returncode, 2)

    def test_example_asks_file_builds(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "sheet", "examples/channel-muting.md", "--asks", str(EXAMPLE_ASKS), "--json"],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(result.returncode, 0, result.stderr)
        sheet = json.loads(result.stdout)
        self.assertEqual({i["kind"] for i in sheet["items"]}, {"question", "approve", "input", "confirm"})
        self.assertIn("options", sheet["items"][0])
        self.assertEqual(sheet["warnings"], [], "the shipped example must carry a full brief")


class ChatAndReplies(unittest.TestCase):
    """--only, the chat message, the GitHub comment that carries the sheet, and short replies."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.doc = make_doc(self.root)
        self.asks = self.root / "asks.json"
        self.asks.write_text(json.dumps({"title": "Muting", "items": [
            {"id": "docs/muting.md#Q1", "why": "Plans differ.", "blocks": "Pricing.",
             "options": [{"label": "Paid tiers only", "because": "b"},
                         {"label": "Every tier", "recommended": True, "because": "a"}]},
            {"id": "copy", "kind": "approve", "text": "Approve the copy", "why": "w", "blocks": "b"},
            {"id": "limit", "kind": "input", "text": "Mute limit?", "proposed": 500, "why": "w", "blocks": "b"},
        ]}), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def sheet(self, *args: str) -> subprocess.CompletedProcess:
        return run("sheet", "--docs-home", "docs", "--asks", str(self.asks), *args, cwd=self.root)

    def reply(self, text: str, *extra: str) -> subprocess.CompletedProcess:
        (self.root / "reply.txt").write_text(text + "\n", encoding="utf-8")
        return run("apply", "--reply", "reply.txt", "--sheet", "comment.md", "--date", "2026-01-05",
                   "--by", "Ollie", "--json", *extra, cwd=self.root)

    def test_only_keeps_the_named_items_and_refuses_an_unknown_one(self) -> None:
        data = json.loads(self.sheet("--only", "docs/muting.md#Q1,limit", "--json").stdout)
        self.assertEqual([i["id"] for i in data["items"]], ["docs/muting.md#Q1", "limit"])
        bad = self.sheet("--only", "docs/muting.md#Q2")  # answered, so not open
        self.assertEqual(bad.returncode, 2)
        self.assertIn("--only names no open item: docs/muting.md#Q2", bad.stderr)

    def test_the_summary_names_the_next_step_for_its_surface(self) -> None:
        rich = self.sheet("--out", "sheet.html")
        self.assertIn("surface: rich", rich.stdout)
        self.assertIn("next: in Claude Code with the promise mod (the tool mcp__promise__decision_pane is listed), "
                      "pass this sheet's --json file to that tool", rich.stdout)
        self.assertIn('else in Claude, publish the --out page with the Artifact tool, capabilities {"db": {}}',
                      rich.stdout)
        self.assertIn("Never send the sheet's files", rich.stdout)
        self.assertIn("add --out <scratch>/decisions.html", self.sheet().stdout)
        as_json = self.sheet("--json")
        self.assertEqual(json.loads(as_json.stdout)["surface"], "rich")
        self.assertIn("next: in Claude", json.loads(as_json.stdout)["next"])
        self.assertEqual(as_json.stderr, "")
        self.assertIn("publish --out as an Artifact with the db capability", " ".join(self.sheet("-h").stdout.split()))
        small = run("sheet", "--docs-home", "docs", "--only", "docs/muting.md#Q1", cwd=self.root)
        self.assertIn("next: ask these with the host's question prompt", small.stdout)

    def test_the_chat_message_numbers_items_and_letters_choices(self) -> None:
        chat = self.sheet("--chat", "-").stdout
        self.assertIn("**Muting**: 4 to decide, 1 blocking", chat)
        self.assertIn("**1.** which plan tiers can mute channels? · BLOCKING (docs/muting.md Q1)", chat)
        self.assertIn("  a) Every tier (Recommended): a", chat)
        self.assertIn("  b) None of these: reply with your own words", chat)
        self.assertIn("  c) Paid tiers only", chat)
        self.assertIn("  a) Approve", chat)
        self.assertIn("  a) 500 (proposed)", chat)
        self.assertIn("Reply with `all recommended`", chat)
        self.assertNotIn("promise-sheet:v1", chat)

    def test_all_recommended_applies_from_the_comment_alone(self) -> None:
        self.assertEqual(self.sheet("--comment", "comment.md").returncode, 0)
        comment = (self.root / "comment.md").read_text(encoding="utf-8")
        self.assertIn("<details><summary>Full detail</summary>", comment)
        self.assertRegex(comment, r"<!-- promise-sheet:v1:[A-Za-z0-9+/=]+ -->")
        result = json.loads(self.reply("All recommended").stdout)
        self.assertEqual([w["line"] for w in result["written"]], ["Answer (2026-01-05, Ollie): Every tier"])
        self.assertEqual([f["id"] for f in result["forAgent"]], ["limit"])
        self.assertEqual(result["notAnswered"], ["docs/muting.md#Q3", "copy"])
        self.assertIn("Answer (2026-01-05, Ollie): Every tier", self.doc.read_text(encoding="utf-8"))

    def test_codes_notes_and_own_words(self) -> None:
        self.sheet("--comment", "comment.md")
        result = json.loads(self.reply("1c, 3b - strike line 4 of the copy, 4: 250\n2: no, it stays grey").stdout)
        lines = [w["line"] for w in result["written"]]
        self.assertEqual(lines, ["Answer (2026-01-05, Ollie): Paid tiers only",
                                 "Answer (2026-01-05, Ollie): no, it stays grey"])
        agent = {f["id"]: f["value"] for f in result["forAgent"]}
        self.assertEqual(agent, {"copy": "Changes requested. strike line 4 of the copy", "limit": "250"})
        self.assertEqual(result["notAnswered"], [])

    def test_codes_on_one_line_and_own_words_after_none_of_these(self) -> None:
        self.sheet("--comment", "comment.md")
        result = json.loads(self.reply("1b - every paid tier and trials, 3a 4a", "--dry-run").stdout)
        self.assertEqual(result["written"][0]["line"], "Answer (2026-01-05, Ollie): every paid tier and trials")
        self.assertEqual({f["id"]: f["value"] for f in result["forAgent"]}, {"copy": "Approved", "limit": "500"})

    def test_all_recommended_with_an_override_in_any_order(self) -> None:
        self.sheet("--comment", "comment.md")
        for text in ("all recommended, 1c", "1c, all recommended", "4: 250, 3a all recommended"):
            with self.subTest(text=text):
                result = json.loads(self.reply(text, "--dry-run").stdout)
                agent = {f["id"]: f["value"] for f in result["forAgent"]}
                if text.startswith("4"):
                    self.assertEqual(agent, {"copy": "Approved", "limit": "250"})
                    self.assertEqual(result["written"][0]["line"].split(": ", 1)[1], "Every tier")
                else:
                    self.assertEqual(result["written"][0]["line"].split(": ", 1)[1], "Paid tiers only")
                    self.assertEqual(agent, {"limit": "500"})

    def test_a_reply_by_id_and_a_lone_letter_after_the_number(self) -> None:
        self.sheet("--comment", "comment.md")
        result = json.loads(self.reply("docs/muting.md#Q1: c, 3: a - fine, `docs/muting.md#Q3`: grey it out",
                                       "--dry-run").stdout)
        lines = [w["line"].split(": ", 1)[1] for w in result["written"]]
        self.assertEqual(lines, ["Paid tiers only", "grey it out"])
        self.assertEqual({f["id"]: f["value"] for f in result["forAgent"]}, {"copy": "Approved. fine"})
        own = json.loads(self.reply("2: a new plan for greying", "--dry-run").stdout)
        self.assertEqual(own["written"][0]["line"].split(": ", 1)[1], "a new plan for greying")

    def test_a_reply_file_that_holds_the_sheet_is_refused(self) -> None:
        self.sheet("--comment", "comment.md")
        thread = (self.root / "comment.md").read_text(encoding="utf-8") + "\nOK: 1c\n"
        (self.root / "reply.txt").write_text(thread, encoding="utf-8")
        before = self.doc.read_bytes()
        for args in (["--sheet", "comment.md"], []):
            proc = run("apply", "--reply", "reply.txt", *args, cwd=self.root)
            self.assertEqual(proc.returncode, 2)
        self.assertIn("holds the sheet itself", run("apply", "--reply", "reply.txt", "--sheet", "comment.md",
                                                    cwd=self.root).stderr)
        self.assertIn("--reply needs --sheet", run("apply", "--reply", "reply.txt", cwd=self.root).stderr)
        self.assertEqual(self.doc.read_bytes(), before)

    def test_an_unreadable_reply_is_refused_with_every_reason(self) -> None:
        self.sheet("--comment", "comment.md")
        before = self.doc.read_bytes()
        proc = self.reply("1b, 3: looks fine, 4z, 9a")
        self.assertEqual(proc.returncode, 2)
        for reason in ("1b: 'None of these' needs your own words", "3: pick a letter (a, b, c)",
                       "4z: item 4 has choices a to a", "9: there is no item 9 (the sheet has 4)"):
            self.assertIn(reason, proc.stderr)
        self.assertEqual(self.doc.read_bytes(), before)

    def test_numbers_inside_a_note_answer_nothing(self) -> None:
        self.sheet("--comment", "comment.md")
        for text, note in (("1c - ship it in 2d", "ship it in 2d"),
                           ("1c - keep it small, in 2 weeks", "keep it small, in 2 weeks")):
            with self.subTest(text=text):
                result = json.loads(self.reply(text, "--dry-run").stdout)
                self.assertEqual([w["line"].split(": ", 1)[1] for w in result["written"]],
                                 [f"Paid tiers only. {note}"])
                self.assertIn("docs/muting.md#Q3", result["notAnswered"])

    def test_a_number_then_a_dash_or_one_letter_is_a_code(self) -> None:
        self.sheet("--comment", "comment.md")
        for text in ("1a, 2 - use postgres, 3 a", "1a\n2 - use postgres\n3 a - fine", "1a 3a 2 - use postgres"):
            with self.subTest(text=text):
                result = json.loads(self.reply(text, "--dry-run").stdout)
                self.assertEqual([w["line"].split(": ", 1)[1] for w in result["written"]],
                                 ["Every tier", "use postgres"])
                self.assertEqual([f["id"] for f in result["forAgent"]], ["copy"])

    def test_runs_take_spaced_letters_and_a_bracket_after_the_letter(self) -> None:
        self.sheet("--comment", "comment.md")
        for text in ("1c 3 a 4a", "1c) 3a. 4a"):
            with self.subTest(text=text):
                result = json.loads(self.reply(text, "--dry-run").stdout)
                self.assertEqual([w["line"].split(": ", 1)[1] for w in result["written"]], ["Paid tiers only"])
                self.assertEqual({f["id"]: f["value"] for f in result["forAgent"]},
                                 {"copy": "Approved", "limit": "500"})

    def test_two_answers_run_together_are_asked_about(self) -> None:
        self.sheet("--comment", "comment.md")
        proc = self.reply("1a 4: 9090 2: keep it")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("more than one answer here?", proc.stderr)
        ratio = json.loads(self.reply("4: 16:9 is fine", "--dry-run").stdout)
        self.assertEqual(ratio["forAgent"][0]["value"], "16:9 is fine")

    def test_a_number_then_plain_words_is_asked_about(self) -> None:
        self.sheet("--comment", "comment.md")
        for text in ("1c - keep it small, 2 people max", "1a\n4 10"):
            with self.subTest(text=text):
                proc = self.reply(text)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("an item or part of the words?", proc.stderr)

    def test_one_letter_to_an_item_with_no_choices_is_words(self) -> None:
        self.asks.write_text(json.dumps({"items": [
            {"id": "ie", "kind": "input", "text": "Drop IE11? y/n", "why": "w", "blocks": "b"}]}), encoding="utf-8")
        self.sheet("--comment", "comment.md")
        self.assertIn("Reply `3: <the value>`.", (self.root / "comment.md").read_text(encoding="utf-8"))
        self.assertNotIn("- or reply", (self.root / "comment.md").read_text(encoding="utf-8"))
        result = json.loads(self.reply("3: y", "--dry-run").stdout)
        self.assertEqual({f["id"]: f["value"] for f in result["forAgent"]}, {"ie": "y"})

    def test_words_with_no_code_in_front_are_refused(self) -> None:
        self.sheet("--comment", "comment.md")
        before = self.doc.read_bytes()
        for text, reason in (("2 a new endpoint instead", "is 2 an item or part of the words?"),
                             ("OK: 1c", "no item number in front")):
            with self.subTest(text=text):
                proc = self.reply(text)
                self.assertEqual(proc.returncode, 2)
                self.assertIn(reason, proc.stderr)
        self.assertEqual(self.doc.read_bytes(), before)

    def test_an_id_or_all_recommended_inside_a_note_is_just_words(self) -> None:
        self.sheet("--comment", "comment.md")
        result = json.loads(self.reply("1c - raise the limit: to 5, 2: grey, 3a - I would not do all recommended here",
                                       "--dry-run").stdout)
        self.assertEqual([w["line"].split(": ", 1)[1] for w in result["written"]],
                         ["Paid tiers only. raise the limit: to 5", "grey"])
        self.assertEqual({f["id"]: f["value"] for f in result["forAgent"]},
                         {"copy": "Approved. I would not do all recommended here"})
        self.assertEqual(result["notAnswered"], ["limit"])

    def test_an_approval_with_options_is_lettered_by_its_options_everywhere(self) -> None:
        self.asks.write_text(json.dumps({"items": [
            {"id": "ship", "kind": "approve", "text": "Ship it?", "why": "w", "blocks": "b",
             "options": [{"label": "Ship"}, {"label": "Hold", "recommended": True}]}]}), encoding="utf-8")
        self.sheet("--comment", "comment.md")
        comment = (self.root / "comment.md").read_text(encoding="utf-8")
        for line in ("  a) Hold (Recommended)", "  c) Ship", "- a) **Hold** (Recommended)", "- c) **Ship**"):
            self.assertIn(line, comment)
        self.assertNotIn("Reject", comment)
        for text, value in (("3c", "Ship"), ("all recommended", "Hold")):  # after the doc's Q1 and Q3
            with self.subTest(text=text):
                result = json.loads(self.reply(text, "--dry-run").stdout)
                self.assertEqual({f["id"]: f["value"] for f in result["forAgent"]}, {"ship": value})

    def test_own_words_after_codes_on_one_line_go_to_their_item(self) -> None:
        self.sheet("--comment", "comment.md")
        result = json.loads(self.reply("1c 3a 2: use postgres", "--dry-run").stdout)
        self.assertEqual([w["line"].split(": ", 1)[1] for w in result["written"]],
                         ["Paid tiers only", "use postgres"])
        self.assertEqual({f["id"]: f["value"] for f in result["forAgent"]}, {"copy": "Approved"})

    def test_an_item_answered_twice_is_refused(self) -> None:
        self.sheet("--comment", "comment.md")
        proc = self.reply("1a 1c")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("1: answered twice", proc.stderr)

    def test_a_thread_with_two_sheets_is_refused(self) -> None:
        self.sheet("--comment", "comment.md")
        first = (self.root / "comment.md").read_text(encoding="utf-8")
        self.sheet("--only", "limit", "--comment", "comment.md")
        (self.root / "comment.md").write_text(first + "\n" + (self.root / "comment.md").read_text(encoding="utf-8"),
                                              encoding="utf-8")
        proc = self.reply("1a")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("holds 2 sheets", proc.stderr)

    def test_a_three_digit_value_on_a_small_sheet_is_words(self) -> None:
        self.sheet("--comment", "comment.md")
        result = json.loads(self.reply("1c - set timeout, 300s is fine, 4: cap it at 5, 100 per user", "--dry-run").stdout)
        self.assertEqual(result["written"][0]["line"].split(": ", 1)[1], "Paid tiers only. set timeout, 300s is fine")
        self.assertEqual({f["id"]: f["value"] for f in result["forAgent"]}, {"limit": "cap it at 5, 100 per user"})

    def test_a_number_list_after_a_comma_stays_in_the_words(self) -> None:
        self.sheet("--comment", "comment.md")
        result = json.loads(self.reply("4: 1, 3", "--dry-run").stdout)
        self.assertEqual({f["id"]: f["value"] for f in result["forAgent"]}, {"limit": "1, 3"})

    def test_the_comment_leaves_out_an_embedded_image_and_refuses_to_outgrow_github(self) -> None:
        import base64, os
        picture = "data:image/png;base64," + base64.b64encode(os.urandom(60000)).decode()
        self.asks.write_text(json.dumps({"items": [
            {"id": "look", "kind": "approve", "text": "The look", "why": "w", "blocks": "b", "image": picture}]}),
            encoding="utf-8")
        self.assertEqual(self.sheet("--comment", "comment.md").returncode, 0)
        self.assertLess(len((self.root / "comment.md").read_text(encoding="utf-8")), 65536)
        self.assertEqual(json.loads(self.reply("3a", "--dry-run").stdout)["forAgent"][0]["value"], "Approved")
        self.asks.write_text(json.dumps({"items": [
            {"id": "big", "kind": "approve", "text": "Big", "why": "w", "blocks": "b",
             "code": base64.b64encode(os.urandom(60000)).decode()}]}), encoding="utf-8")
        proc = self.sheet("--comment", "comment2.md")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("over GitHub's 65536", proc.stderr)
        self.assertFalse((self.root / "comment2.md").exists())

    def test_only_one_output_may_print(self) -> None:
        for args in (["--json", "--chat", "-"], ["--chat", "-", "--comment", "-"]):
            with self.subTest(args=args):
                proc = self.sheet(*args)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("would all print", proc.stderr)

    def test_the_sheet_json_works_as_the_source_too(self) -> None:
        (self.root / "sheet.json").write_text(self.sheet("--json").stdout, encoding="utf-8")
        (self.root / "reply.txt").write_text("1a\n", encoding="utf-8")
        proc = run("apply", "--reply", "reply.txt", "--sheet", "sheet.json", "--json", "--dry-run", cwd=self.root)
        self.assertEqual(json.loads(proc.stdout)["written"][0]["line"].split(": ", 1)[1], "Every tier")
        (self.root / "junk.txt").write_text("nothing", encoding="utf-8")
        self.assertEqual(run("apply", "--reply", "reply.txt", "--sheet", "junk.txt", cwd=self.root).returncode, 2)
        self.assertEqual(run("apply", cwd=self.root).returncode, 2)


class PlainWords(unittest.TestCase):
    """A sheet never leans on a number the reader must remember: a section gets its name,
    a question, issue, row or item number gets words beside it, and a question the doc
    words badly gets `plain` words, with the doc's own words kept beside them."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_doc(self.root)
        self.asks = self.root / "asks.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def sheet(self, items, *args: str) -> subprocess.CompletedProcess:
        self.asks.write_text(json.dumps({"items": items}), encoding="utf-8")
        return run("sheet", "--docs-home", "docs", "--asks", str(self.asks), *args, cwd=self.root)

    CONFIRM = {"id": "confirm-lines", "kind": "approve", "why": "w", "blocks": "b",
               "text": "§1, §2 and the agent examples in §3 are agent-written from the code and the issue. "
                       "Confirm or strike each line. (Recommended) Confirm as written."}

    def test_the_numbers_the_reader_cannot_follow_are_refused_and_nothing_is_written(self) -> None:
        why = {"id": "docs/muting.md#Q1", "why": "Written from the code and issue #87, not by you.",
               "blocks": "b", "example": "§2 item 3 says the state text goes after the name"}
        proc = self.sheet([self.CONFIRM, why], "--out", "sheet.html", "--chat", "chat.md")
        self.assertEqual(proc.returncode, 2)
        for reason in ("confirm-lines: the question holds its own recommendation",
                       "confirm-lines: it asks to check lines it does not show",
                       "docs/muting.md#Q1: why leans on an issue or pull request number, '#87'",
                       "docs/muting.md#Q1: example leans on a numbered item, 'item 3'"):
            self.assertIn(reason, proc.stderr)
        self.assertFalse((self.root / "sheet.html").exists() or (self.root / "chat.md").exists())
        listed = json.loads(self.sheet([self.CONFIRM, why], "--json").stdout)
        self.assertEqual(len(listed["unclear"]), 4)

    def test_numbers_with_their_words_pass_and_sections_get_their_names(self) -> None:
        items = [{"id": "docs/muting.md#Q1", "plain": "Can every plan mute channels, or only paid plans?",
                  "why": "Issue #87 (\"Muted channels still badge\") asks for it; §2 says every member.",
                  "blocks": "Q3: the grey-out question waits on it", "example": "item 3 — the badge count",
                  "options": [{"label": "Every plan", "recommended": True, "because": "§1 (problem) is for all",
                               "then": "the agent adds AT-4: a free member mutes a channel"}]},
                 {"id": "copy", "kind": "approve", "text": "Approve the toggle copy", "why": "w", "blocks": "b",
                  "code": "- Turn off notifications\n+ Mute channel"}]
        proc = self.sheet(items, "--out", "sheet.html", "--md", "sheet.md", "--chat", "chat.md")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        twin = (self.root / "sheet.md").read_text(encoding="utf-8")
        self.assertIn("Can every plan mute channels, or only paid plans?", twin)
        self.assertIn("In the doc: which plan tiers can mute channels?", twin)
        self.assertIn("§2 Outcome says every member", twin)
        self.assertIn("§1 (problem) is for all", twin)
        chat = (self.root / "chat.md").read_text(encoding="utf-8")
        self.assertIn("**1.** Can every plan mute channels, or only paid plans?", chat)
        page = (self.root / "sheet.html").read_text(encoding="utf-8")
        self.assertIn('"docText": "which plan tiers can mute channels?"', page)
        # the answer still goes under the doc's own question
        (self.root / "reply.txt").write_text("1a\n", encoding="utf-8")
        (self.root / "s.json").write_text(self.sheet(items, "--json").stdout, encoding="utf-8")
        run("apply", "--reply", "reply.txt", "--sheet", "s.json", "--date", "2026-01-05", cwd=self.root)
        self.assertIn("channels?\nAnswer (2026-01-05): Every plan",
                      (self.root / "docs" / "muting.md").read_text(encoding="utf-8"))


class Words(unittest.TestCase):
    """The product's words come from the map's glossary, the one list issues and pull
    requests use too; the asks file's `words` only fill a gap, and say so."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_doc(self.root)
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "promise.config.json").write_text(
            json.dumps({"docsHome": "docs", "map": {"file": "map.json"}}), encoding="utf-8")
        (self.root / "map.json").write_text(json.dumps({"version": 1, "rows": [], "glossary": [
            {"term": "Mode 3", "plain": "The client lets the agent act for them.", "aliases": ["connection mode 3"]},
            {"term": "Seat", "plain": "One paid member account."}]}), encoding="utf-8")
        self.asks = self.root / "asks.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def sheet(self, asks, *args: str) -> subprocess.CompletedProcess:
        self.asks.write_text(json.dumps(asks), encoding="utf-8")
        return run("sheet", "--asks", str(self.asks), *args, cwd=self.root)

    ITEM = {"id": "brief", "kind": "question", "text": "Should a brief fail closed for a client with no mode 3 record?",
            "why": "Nothing records it today.", "blocks": "b",
            "options": [{"label": "Fail closed", "recommended": True, "because": "the rule holds by design",
                         "then": "t"}, {"label": "Save it anyway", "because": "b", "then": "t"}]}

    def test_a_map_row_id_needs_its_words_too(self) -> None:
        item = {"id": "c", "kind": "approve", "text": "Approve the copy", "why": "CAP-i1890a still fails", "blocks": "b"}
        for rid in ("CAP-i1890a", "CAP-ENG-421a", "CAP-3"):
            with self.subTest(rid=rid):
                item["why"] = f"{rid} still fails"
                listed = json.loads(self.sheet({"items": [item]}, "--json").stdout)["unclear"]
                self.assertIn(f"'{rid}'", " ".join(listed))
        # with its words; and everyday words shaped like ids are words
        item["why"] = "CAP-i1890a (the badge row) still fails; i18n, p99th, i3wm, i1890a and GPT-4o are fine"
        self.assertEqual(json.loads(self.sheet({"items": [item]}, "--json").stdout)["unclear"], [])

    def test_the_glossary_explains_the_words_the_sheet_uses_and_nothing_else(self) -> None:
        data = json.loads(self.sheet({"items": [self.ITEM]}, "--json").stdout)
        self.assertEqual(data["unclear"], [])
        self.assertEqual([(w["term"], w["from"]) for w in data["words"]], [("Mode 3", "map")])
        self.assertEqual(self.sheet({"items": [self.ITEM]}, "--chat", "chat.md").returncode, 0)
        self.assertIn("- **Mode 3**: The client lets the agent act for them.",
                      (self.root / "chat.md").read_text(encoding="utf-8"))

    def test_a_numbered_name_with_no_meaning_is_unclear_and_asks_words_fill_the_gap(self) -> None:
        item = dict(self.ITEM, text="Should a brief fail closed for a client on tier 2?")
        proc = self.sheet({"items": [item]}, "--out", "sheet.html")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("names 'tier 2' with no meaning; add it to `words`", proc.stderr)
        data = json.loads(self.sheet({"items": [item], "words": {"tier 2": "Clients who pay yearly.",
                                                                "Seat": "a chair"}}, "--json").stdout)
        self.assertEqual(data["unclear"], [])
        self.assertEqual([(w["term"], w["from"]) for w in data["words"]], [("tier 2", "asks")])
        self.assertIn("words: 'tier 2' is not in the map's glossary; add it there", " ".join(data["warnings"]))
        self.assertIn("words: 'Seat' is in the map's glossary; its meaning comes from there",
                      " ".join(data["warnings"]))

    def test_a_long_question_or_why_is_unclear(self) -> None:
        item = dict(self.ITEM, text="Should " + "a very long " * 12 + "question pass?", why="why " * 61)
        found = " ".join(json.loads(self.sheet({"items": [item]}, "--json").stdout)["unclear"])
        self.assertIn("text is 39 words; put it in 35 words or fewer", found)
        self.assertIn("why is 61 words; put it in 60 words or fewer", found)

    def test_ordinary_words_are_not_mistaken_for_numbers_or_paths(self) -> None:
        item = dict(self.ITEM, text="Move the brief page to Next.js, our #1 priority, in Q3 2026?",
                    why="§2.3 of the plan, and decision-sheet.md §4, say so; Python version 3.12 and type 2 too.",
                    blocks="The rule lives in §4, and AT-3.2 (the badge row) proves it; see §9 open question Q1: threads.",
                    ifNoAnswer="See [the spec](https://github.com/o/r/blob/main/docs/spec.md#12) or https://x.io/a/b.ts")
        data = json.loads(self.sheet({"items": [item]}, "--json").stdout)
        self.assertEqual(data["unclear"], [])
        why = {i["id"]: i.get("why") for i in data["items"]}["brief"]
        self.assertEqual(why, "§2.3 of the plan, and decision-sheet.md §4, say so; Python version 3.12 and type 2 too.")
        self.assertEqual({i["id"]: i.get("blocks") for i in data["items"]}["brief"], "The rule lives in §4 Invariants, and AT-3.2 (the badge row) proves it; see §9 open question Q1: threads.")

    def test_a_term_covers_only_its_own_number_and_notes_and_blank_plain_are_left_alone(self) -> None:
        item = dict(self.ITEM, text="Should a brief fail closed for a client in mode 30?", plain="  ",
                    evidence=[{"ref": "api.ts:42", "note": "line 42 returns early"}], why="See §2a.")
        data = json.loads(self.sheet({"items": [item]}, "--json").stdout)
        self.assertEqual(len(data["unclear"]), 1)
        self.assertIn("names 'mode 30' with no meaning", data["unclear"][0])
        brief = {i["id"]: i for i in data["items"]}["brief"]
        self.assertEqual((brief["text"], brief["why"]), (item["text"], "See §2a."))

    def test_plain_on_an_item_outside_the_docs_is_just_its_text(self) -> None:
        item = dict(self.ITEM, plain="Should the brief wait for consent?")
        data = json.loads(self.sheet({"items": [item]}, "--json").stdout)
        brief = {i["id"]: i for i in data["items"]}["brief"]
        self.assertEqual((brief["text"], "docText" in brief), ("Should the brief wait for consent?", False))

    def test_a_blank_glossary_term_is_left_out(self) -> None:
        (self.root / "map.json").write_text(json.dumps({"version": 1, "rows": [], "glossary": [
            {"term": " ", "plain": "nothing"}, {"term": "Seat", "plain": "One paid account.", "aliases": "seat"},
            {"term": "Mode 3", "plain": "The agent acts for the client."}]}),
            encoding="utf-8")
        data = json.loads(self.sheet({"items": [self.ITEM]}, "--json").stdout)
        self.assertEqual([w["term"] for w in data["words"]], ["Mode 3"])

    def test_a_path_on_the_card_goes_to_evidence(self) -> None:
        item = dict(self.ITEM, why="Saving moves the client (docs/ideas/connection-modes.md:24, 28).")
        data = json.loads(self.sheet({"items": [item]}, "--json").stdout)
        self.assertIn("why shows a file path, 'docs/ideas/connection-modes.md:24, 28'", " ".join(data["unclear"]))


class Rounds(unittest.TestCase):
    """A big backlog comes in rounds a person can finish: BLOCKING first, one doc's
    questions together, and the page says how many wait for later."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        make_doc(self.root)
        self.asks = self.root / "asks.json"
        items = [{"id": f"ask-{n}", "kind": "approve", "text": f"Approve the copy for screen {chr(65 + n)}",
                  "why": "w", "blocks": "b"} for n in range(15)]
        self.asks.write_text(json.dumps({"items": items}), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def sheet(self, *args: str) -> subprocess.CompletedProcess:
        return run("sheet", "--docs-home", "docs", "--asks", str(self.asks), *args, cwd=self.root)

    def test_a_round_holds_twelve_blocking_first_and_counts_the_rest(self) -> None:
        data = json.loads(self.sheet("--json").stdout)
        ids = [i["id"] for i in data["items"]]
        self.assertEqual(len(ids), 12)
        self.assertEqual(ids[0], "docs/muting.md#Q1")  # the BLOCKING question leads
        self.assertEqual(ids[1:3], ["docs/muting.md#Q3", "ask-0"])  # then the rest, in the order found
        self.assertNotIn("ask-14", ids)
        self.assertEqual((data["counts"]["later"], data["counts"]["laterBlocking"]), (5, 0))
        summary = self.sheet("--out", "sheet.html").stdout
        self.assertIn("5 more (0 blocking) in later rounds: apply this round's answers, then build the next",
                      summary)
        self.assertIn('"later": 5', (self.root / "sheet.html").read_text(encoding="utf-8"))
        self.assertIn("12 to decide, 1 blocking. 5 more come in later rounds", self.sheet("--chat", "-").stdout)
        self.assertEqual(len(json.loads(self.sheet("--json", "--all").stdout)["items"]), 17)
        self.assertEqual(len(json.loads(self.sheet("--json", "--limit", "3").stdout)["items"]), 3)
        self.assertEqual(len(json.loads(self.sheet("--json", "--only", "ask-14").stdout)["items"]), 1)
        self.assertEqual(self.sheet("--limit", "0").returncode, 2)

    def test_the_asks_skeleton_names_what_to_fill_and_what_is_unclear(self) -> None:
        later = [{"id": f"ask-{n}", "kind": "approve", "text": f"Approve screen {n}", "why": "w", "blocks": "b"}
                 for n in range(12)]
        self.asks.write_text(json.dumps({"words": {"toggle": "The mute switch."}, "items": [
            {"id": "docs/muting.md#Q1", "why": "Written from issue #87."}] + later}), encoding="utf-8")
        self.assertEqual(self.sheet("--asks-skeleton", str(self.asks)).returncode, 0)
        skeleton = json.loads(self.asks.read_text(encoding="utf-8"))
        # written over its own asks file, nothing outside this round is lost
        self.assertEqual({i["id"] for i in skeleton["items"]} >= {f"ask-{n}" for n in range(12)}, True)
        self.assertEqual(skeleton["words"], {"toggle": "The mute switch."})
        q1 = skeleton["items"][0]
        self.assertEqual((q1["id"], q1["_doc"], q1["plain"], q1["why"], q1["blocks"]),
                         ("docs/muting.md#Q1", "which plan tiers can mute channels?", "", "Written from issue #87.", ""))
        self.assertIn("'#87'", q1["_unclear"][0])
        # filled in and passed back, it is an asks file; the _ keys are ignored
        q1.update(plain="Can every plan mute channels?", why="Issue #87 (\"Mute for free plans\") asks.", blocks="b")
        (self.root / "skeleton.json").write_text(json.dumps(skeleton), encoding="utf-8")
        again = run("sheet", "--docs-home", "docs", "--asks", "skeleton.json", "--json", cwd=self.root)
        self.assertEqual(json.loads(again.stdout)["unclear"], [])

    def test_prompt_batches_carry_the_reply_code_of_each_option(self) -> None:
        data = json.loads(self.sheet("--prompt-json", "--limit", "5").stdout)
        self.assertEqual([len(b) for b in data["batches"]], [4, 1])
        first = data["batches"][0][0]
        self.assertEqual((first["item"], first["header"]), (1, "Channel"))
        self.assertEqual((first["freeText"], [o["code"] for o in first["options"]]), (True, [None, None]))
        approve = next(q for b in data["batches"] for q in b if q["id"] == "ask-0")
        self.assertEqual([o["code"] for o in approve["options"]], ["3a", "3c"])
        self.assertEqual([o["label"] for o in approve["options"]], ["Approve", "Reject"])
        self.assertEqual(approve["otherReply"], "3b - <what to change>")
        self.assertEqual(first["otherReply"], "1: <their words>")

    def test_prompt_batches_put_blocking_first_and_list_options_past_four(self) -> None:
        self.asks.write_text(json.dumps({"items": [
            {"id": "pick", "kind": "question", "text": "Which colour?", "why": "w", "blocks": "b",
             "options": [{"label": c, "because": "b", "then": "t"} for c in ("Red", "Blue", "Green", "Grey", "Gold")]},
            {"id": "block", "kind": "question", "text": "Ship it?", "blocking": True, "why": "w", "blocks": "b",
             "options": [{"label": "Yes", "recommended": True, "because": "b", "then": "t"},
                         {"label": "No", "because": "b", "then": "t"}]},
            {"id": "cap", "kind": "input", "text": "Mute limit", "proposed": 500, "why": "Sends slow down",
             "blocks": "b"}]}), encoding="utf-8")
        data = json.loads(self.sheet("--prompt-json").stdout)
        cap = next(q for b in data["batches"] for q in b if q["id"] == "cap")
        todo = {"id": "flag", "kind": "confirm", "text": "Turn the flag on", "why": "w", "blocks": "b"}
        self.asks.write_text(json.dumps({"items": [todo]}), encoding="utf-8")
        flag = json.loads(self.sheet("--prompt-json").stdout)["batches"][0][2]
        self.assertEqual(flag["otherReply"], "3b - <their words>")
        (self.root / "s.json").write_text(self.sheet("--json").stdout, encoding="utf-8")
        (self.root / "r.txt").write_text("3b - rotated half of them\n", encoding="utf-8")
        applied = run("apply", "--reply", "r.txt", "--sheet", "s.json", "--json", "--dry-run", cwd=self.root)
        self.assertEqual(json.loads(applied.stdout)["forAgent"][0]["value"], "Not done yet. rotated half of them")
        self.assertEqual((cap["options"][0]["label"], cap["question"]), ("500 (Recommended)", "Mute limit — Sends slow down"))
        order = [(q["id"], q["item"]) for b in data["batches"] for q in b]
        self.assertEqual(order[:2], [("docs/muting.md#Q1", 1), ("block", 4)])
        pick = next(q for b in data["batches"] for q in b if q["id"] == "pick")
        self.assertEqual([o["code"] for o in pick["options"]], ["3a", "3c", "3d", "3e"])
        self.assertEqual([o["code"] for o in pick["moreOptions"]], ["3f"])
        self.assertIn("apply --reply", data["reply"])


class Research(unittest.TestCase):
    """A big backlog goes to research agents first: each open question is sorted into
    answered, same-as, stale or needs-you, and only what needs a person reaches the
    rounds. Nothing is taken on trust: evidence must point at a real line."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.doc = make_doc(self.root)
        (self.root / "src").mkdir()
        (self.root / "src" / "plans.ts").write_text("export const MUTE_TIERS = ['free', 'paid'];\nexport const X = 1;\n",
                                                   encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_(self, *args: str) -> subprocess.CompletedProcess:
        return run(*args, cwd=self.root)

    def test_triage_merge_sheet_and_one_answer_for_two_questions(self) -> None:
        proc = self.run_("triage", "--docs-home", "docs", "--out", "research")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        triage = json.loads(proc.stdout)
        self.assertEqual((triage["questions"], len(triage["packets"])), (2, 1))
        packet = json.loads(Path(triage["packets"][0]["packet"]).read_text(encoding="utf-8"))
        self.assertEqual([i["id"] for i in packet["items"]], ["docs/muting.md#Q1", "docs/muting.md#Q3"])
        self.assertIn("research/result-01.json", triage["packets"][0]["prompt"])
        (self.root / "research" / "result-01.json").write_text(json.dumps({
            "format": "promise-research", "version": 1, "packet": "packet-01", "results": [
                {"id": "docs/muting.md#Q1", "pile": "answered", "answer": "Every tier: free and paid",
                 "because": "the plan list already lets both tiers mute",
                 "evidence": [{"ref": "src/plans.ts:1", "note": "both tiers are in the mute list"}]},
                {"id": "docs/muting.md#Q3", "pile": "same-as", "sameAs": "docs/muting.md#Q1", "because": "b"},
                {"id": "docs/muting.md#Q1", "pile": "answered", "answer": "x", "evidence": []},
                {"id": "docs/muting.md#Q1", "pile": "answered", "answer": "x",
                 "evidence": [{"ref": "src/plans.ts:99"}]},
                {"id": "docs/muting.md#Q1", "pile": "answered", "answer": "x",
                 "evidence": [{"ref": "src/plans.ts:9-1"}]},
                {"id": "docs/muting.md#Q1", "pile": "stale", "answer": "x", "evidence": [{"ref": "src/nope.ts:1"}]},
                {"id": "docs/muting.md#Q2", "pile": "answered", "answer": "x"},
                {"id": "docs/muting.md#Q3", "pile": "same-as", "sameAs": "docs/muting.md#Q3"}]}), encoding="utf-8")
        merged = self.run_("merge-research", "research", "--out", "asks.json")
        self.assertEqual(merged.returncode, 1)  # something was rejected
        report = json.loads(merged.stdout)
        self.assertEqual(report["piles"], {"answered": 1, "same-as": 1, "stale": 0, "needs-you": 0})
        self.assertEqual([r["reason"] for r in report["rejected"]], [
            "no evidence: research that finds an answer shows where",
            "evidence 'src/plans.ts:99': the file has 2 lines",
            "evidence 'src/plans.ts:9-1': the file has 2 lines",
            "evidence 'src/nope.ts:1': no such file in this project",
            "not an open question",
            "sameAs must name another open question"])
        sheet = json.loads(self.run_("sheet", "--docs-home", "docs", "--asks", "asks.json", "--json").stdout)
        self.assertEqual([i["id"] for i in sheet["items"]], ["docs/muting.md#Q1"])
        q1 = sheet["items"][0]
        self.assertNotEqual(q1.get("blocks"), "Nothing new: research found the answer; it needs your yes.")
        # Q1 BLOCKS its doc, so research's answer is a card in the round, not in the "Accept all" group
        self.assertEqual((q1.get("group"), q1["research"], [a["id"] for a in q1["alsoAnswers"]]),
                         (None, "answered", ["docs/muting.md#Q3"]))
        self.assertEqual((sheet["counts"]["researched"], sheet["counts"]["settledTogether"], sheet["counts"]["round"]),
                         (0, 1, 1))
        self.assertIn("1 to decide, 1 blocking.",
                      self.run_("sheet", "--docs-home", "docs", "--asks", "asks.json", "--chat", "-").stdout)
        page = self.run_("sheet", "--docs-home", "docs", "--asks", "asks.json", "--out", "sheet.html")
        self.assertEqual(page.returncode, 0, page.stderr)
        # one reply, written under both questions
        (self.root / "s.json").write_text(json.dumps(sheet), encoding="utf-8")
        (self.root / "r.txt").write_text("all recommended\n", encoding="utf-8")
        self.run_("apply", "--reply", "r.txt", "--sheet", "s.json", "--date", "2026-01-05", "--by", "Ollie")
        text = self.doc.read_text(encoding="utf-8")
        self.assertIn("channels?\nAnswer (2026-01-05, Ollie): Every tier: free and paid", text)
        self.assertIn("greyed out?\nAnswer (2026-01-05, Ollie): Every tier: free and paid", text)
        again = json.loads(self.run_("triage", "--docs-home", "docs", "--out", "research2").stdout)
        self.assertEqual(again["questions"], 0)

    def test_a_bad_needs_you_result_is_rejected_and_a_second_result_replaces_the_first(self) -> None:
        (self.root / "research").mkdir()
        first = {"format": "promise-research", "version": 1, "results": [
            {"id": "docs/muting.md#Q3", "pile": "same-as", "sameAs": "docs/muting.md#Q1"},
            {"id": "docs/muting.md#Q1", "pile": "needs-you", "plain": "Which plans mute?",
             "options": [{"label": "A", "recommended": True}, {"label": "B", "recommended": True}]}]}
        (self.root / "research" / "result-01.json").write_text(json.dumps(first), encoding="utf-8")
        merged = json.loads(self.run_("merge-research", "research", "--out", "asks.json").stdout)
        self.assertIn("more than one option Recommended", merged["rejected"][0]["reason"])
        self.assertEqual(self.run_("sheet", "--docs-home", "docs", "--asks", "asks.json", "--json").returncode, 0)
        second = {"format": "promise-research", "version": 1, "results": [
            {"id": "docs/muting.md#Q3", "pile": "answered", "answer": "Yes, greyed", "because": "b",
             "evidence": [{"ref": "src/plans.ts:2", "note": "n"}]}]}
        (self.root / "research" / "result-01.json").write_text(json.dumps(second), encoding="utf-8")
        self.run_("merge-research", "research", "--asks", "asks.json")
        entry = {e["id"]: e for e in json.loads((self.root / "asks.json").read_text(encoding="utf-8"))["items"]}
        self.assertNotIn("sameAs", entry["docs/muting.md#Q3"])
        self.assertEqual(entry["docs/muting.md#Q3"]["research"], "answered")

    def test_merge_rejects_a_bad_same_as_and_reads_and_writes_the_same_asks_file(self) -> None:
        (self.root / "research").mkdir()
        (self.root / "research" / "result-01.json").write_text(json.dumps({
            "format": "promise-research", "version": 1, "results": [
                {"id": "docs/muting.md#Q3", "pile": "same-as", "sameAs": ["docs/muting.md#Q1"]}]}), encoding="utf-8")
        (self.root / "asks.json").write_text(json.dumps({"title": "Kept", "items": []}), encoding="utf-8")
        with tempfile.TemporaryDirectory() as elsewhere:
            proc = subprocess.run([sys.executable, str(SCRIPT), "merge-research", str(self.root / "research"),
                                   "--cwd", str(self.root), "--docs-home", "docs",
                                   "--asks", str(self.root / "asks.json")], capture_output=True, text=True,
                                  cwd=elsewhere)
        self.assertEqual(json.loads(proc.stdout)["rejected"][0]["reason"], "sameAs must name another open question")
        self.assertEqual(json.loads((self.root / "asks.json").read_text(encoding="utf-8"))["title"], "Kept")

    def test_same_as_chains_fold_whatever_the_order_and_a_broken_link_stops_short(self) -> None:
        items = [{"id": f"q{n}", "kind": "question", "text": f"Pick {c}?", "why": "w", "blocks": "b"}
                 for n, c in enumerate("ABCD")]
        items[1]["sameAs"], items[0]["sameAs"] = "q2", "q1"  # q1 folds first, then q0 finds q1 folded
        items[2]["sameAs"] = "gone"  # a broken link: q2 stays and settles q0 and q1
        (self.root / "asks.json").write_text(json.dumps({"items": items}), encoding="utf-8")
        sheet = json.loads(self.run_("sheet", "--docs-home", "docs", "--asks", "asks.json", "--json").stdout)
        by_id = {i["id"]: i for i in sheet["items"]}
        self.assertNotIn("q0", by_id)
        self.assertNotIn("q1", by_id)
        self.assertEqual(sorted(a["id"] for a in by_id["q2"]["alsoAnswers"]), ["q0", "q1"])
        chat = self.run_("sheet", "--docs-home", "docs", "--asks", "asks.json", "--chat", "-").stdout
        self.assertIn("Also settles: Pick", chat)
        items[0]["plain"] = "Which shade for the badge?"
        (self.root / "asks.json").write_text(json.dumps({"items": items}), encoding="utf-8")
        sheet = json.loads(self.run_("sheet", "--docs-home", "docs", "--asks", "asks.json", "--json").stdout)
        also = {a["id"]: a["text"] for a in {i["id"]: i for i in sheet["items"]}["q2"]["alsoAnswers"]}
        self.assertEqual(also["q0"], "Which shade for the badge?")

    def test_a_same_as_whose_other_question_was_answered_goes_back_to_research(self) -> None:
        (self.root / "asks.json").write_text(json.dumps({"items": [
            {"id": "docs/muting.md#Q3", "research": "same-as", "sameAs": "docs/muting.md#Q1"}]}), encoding="utf-8")
        self.doc.write_text(self.doc.read_text(encoding="utf-8").replace(
            "channels?\n", "channels?\nAnswer (2026-01-01): every tier\n", 1), encoding="utf-8")
        sheet = json.loads(self.run_("sheet", "--docs-home", "docs", "--asks", "asks.json", "--json").stdout)
        self.assertEqual(sheet["counts"]["unresearched"], 1)
        triage = json.loads(self.run_("triage", "--docs-home", "docs", "--asks", "asks.json", "--out", "r").stdout)
        self.assertEqual(triage["questions"], 1)

    def test_a_sheet_past_ninety_nine_items_can_still_be_answered_by_number(self) -> None:
        items = [{"id": f"q{n}", "kind": "question", "text": f"Pick {n}?", "research": "answered", "why": "w",
                  "blocks": "b", "options": [{"label": f"Answer {n}", "recommended": True, "because": "b", "then": "t"}],
                  "evidence": [{"ref": "src/plans.ts:1", "note": "n"}]} for n in range(105)]
        (self.root / "asks.json").write_text(json.dumps({"items": items}), encoding="utf-8")
        (self.root / "s.json").write_text(
            self.run_("sheet", "--docs-home", "docs", "--asks", "asks.json", "--json").stdout, encoding="utf-8")
        (self.root / "r.txt").write_text("100a 101: set the timeout to 300s\n", encoding="utf-8")
        applied = self.run_("apply", "--reply", "r.txt", "--sheet", "s.json", "--json", "--dry-run")
        self.assertEqual(applied.returncode, 0, applied.stderr)
        values = {f["id"]: f["value"] for f in json.loads(applied.stdout)["forAgent"]}
        self.assertEqual(len(values), 2)
        (self.root / "r.txt").write_text("1a 3: 9090 105: keep it\n", encoding="utf-8")
        refused = self.run_("apply", "--reply", "r.txt", "--sheet", "s.json")
        self.assertIn("more than one answer here?", refused.stderr)

    def test_a_blocking_question_folded_into_a_research_answer_stays_in_the_round(self) -> None:
        (self.root / "research").mkdir()
        (self.root / "research" / "result-01.json").write_text(json.dumps({
            "format": "promise-research", "version": 1, "results": [
                {"id": "docs/muting.md#Q3", "pile": "answered", "answer": "Greyed", "because": "b",
                 "evidence": [{"ref": "src/plans.ts:1", "note": "n"}]},
                {"id": "docs/muting.md#Q1", "pile": "same-as", "sameAs": "docs/muting.md#Q3"}]}), encoding="utf-8")
        merged = self.run_("merge-research", "research", "--docs-home", "docs", "--asks", "new-asks.json")
        self.assertEqual(merged.returncode, 0, merged.stdout + merged.stderr)  # a first merge starts the file
        sheet = json.loads(self.run_("sheet", "--docs-home", "docs", "--asks", "new-asks.json", "--json").stdout)
        q3 = sheet["items"][0]
        self.assertEqual((q3["id"], q3.get("group"), q3["blocking"]), ("docs/muting.md#Q3", None, True))
        self.assertEqual((sheet["counts"]["blocking"], sheet["counts"]["researched"]), (1, 0))

    def test_triage_refuses_a_folder_with_earlier_results(self) -> None:
        (self.root / "research").mkdir()
        (self.root / "research" / "result-04.json").write_text("{}", encoding="utf-8")
        proc = self.run_("triage", "--docs-home", "docs", "--out", "research")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("holds packets or results from an earlier triage", proc.stderr)

    def test_the_twin_titles_the_research_group_by_its_name(self) -> None:
        (self.root / "asks.json").write_text(json.dumps({"items": [
            {"id": "docs/muting.md#Q3", "research": "answered", "group": "Checked by research", "why": "w",
             "blocks": "b", "options": [{"label": "Greyed", "recommended": True, "because": "b", "then": "t"}],
             "evidence": [{"ref": "src/plans.ts:1", "note": "n"}]}]}), encoding="utf-8")
        self.run_("sheet", "--docs-home", "docs", "--asks", "asks.json", "--md", "t.md")
        twin = (self.root / "t.md").read_text(encoding="utf-8")
        self.assertIn("## Checked by research", twin)
        self.assertNotIn("> **Outcome:**", twin.split("## Checked by research")[1])

    def test_a_second_merge_takes_back_only_what_research_set_and_the_round_count_leaves_research_out(self) -> None:
        (self.root / "research").mkdir()
        result = self.root / "research" / "result-01.json"
        hand = [{"label": "Grey", "recommended": True, "because": "hand", "then": "t"}]
        (self.root / "asks.json").write_text(json.dumps({"items": [
            {"id": "docs/muting.md#Q3", "detail": "kept from the asks file", "why": "hand why",
             "options": hand}]}), encoding="utf-8")
        result.write_text(json.dumps({"format": "promise-research", "version": 1, "results": [
            {"id": "docs/muting.md#Q3", "pile": "answered", "answer": "Greyed", "because": "b",
             "evidence": [{"ref": "src/plans.ts:1", "note": "n"}]}]}), encoding="utf-8")
        self.run_("merge-research", "research", "--asks", "asks.json")
        # the skeleton, written over the asks file, keeps research's bookkeeping
        self.run_("sheet", "--docs-home", "docs", "--asks", "asks.json", "--asks-skeleton", "asks.json")
        result.write_text(json.dumps({"format": "promise-research", "version": 1, "results": [
            {"id": "docs/muting.md#Q3", "pile": "needs-you", "plain": "Grey it out?"}]}), encoding="utf-8")
        self.run_("merge-research", "research", "--asks", "asks.json")
        entry = {e["id"]: e for e in json.loads((self.root / "asks.json").read_text(encoding="utf-8"))["items"]}[
            "docs/muting.md#Q3"]
        self.assertEqual((entry["detail"], entry["why"], entry["options"]), ("kept from the asks file", "hand why", hand))
        self.assertNotIn("blocks", entry)  # research's "found the answer" line went with its answer
        self.assertNotIn("group", entry)
        self.run_("merge-research", "research", "--asks", "asks.json")  # the same result again
        entry = {e["id"]: e for e in json.loads((self.root / "asks.json").read_text(encoding="utf-8"))["items"]}[
            "docs/muting.md#Q3"]
        self.assertEqual((entry["detail"], entry["plain"]), ("kept from the asks file", "Grey it out?"))

    def test_merge_reads_a_doc_named_outside_docs_home(self) -> None:
        (self.root / "research").mkdir()
        (self.root / "research" / "result-01.json").write_text(json.dumps({
            "format": "promise-research", "version": 1, "results": [
                {"id": "docs/muting.md#Q3", "pile": "same-as", "sameAs": "docs/muting.md#Q1"}]}), encoding="utf-8")
        proc = self.run_("merge-research", "research", "--doc", "docs/muting.md", "--out", "asks.json")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_a_backlog_past_one_round_is_offered_research_first(self) -> None:
        asks = {"items": [{"id": f"q{n}", "kind": "question", "text": f"Pick colour {chr(65 + n)}?", "why": "w",
                           "blocks": "b"} for n in range(13)]}
        (self.root / "asks.json").write_text(json.dumps(asks), encoding="utf-8")
        out = self.run_("sheet", "--docs-home", "docs", "--asks", "asks.json").stdout
        self.assertIn("research first: 15 open items is more than one round", out)
        self.assertIn("decisions.py triage", out)
        for i in asks["items"]:
            i["research"] = "needs-you"
        (self.root / "asks.json").write_text(json.dumps(asks), encoding="utf-8")
        make_doc(self.root).write_text(make_doc(self.root).read_text(encoding="utf-8").replace(
            "Q1 — owner: Ollie — BLOCKING: which plan tiers can mute\nchannels?\n",
            "Q1 — owner: Ollie — BLOCKING: which plan tiers can mute\nchannels?\nAnswer (2026-01-01): every tier\n")
            .replace("Q3 — owner: Ana — non-blocking: is a muted channel greyed out?\n",
                     "Q3 — owner: Ana — non-blocking: is a muted channel greyed out?\nAnswer (2026-01-01): yes\n"),
            encoding="utf-8")
        again = self.run_("sheet", "--docs-home", "docs", "--asks", "asks.json").stdout
        self.assertNotIn("research first", again)  # all of it has been researched


class Apply(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def answers(self, *answers: dict, name: str = "answers.json", wrap: bool = False) -> str:
        data = {"format": "promise-answers", "version": 1, "sheet": "x", "answers": list(answers)}
        text = json.dumps(data, indent=2)
        if wrap:
            text = "promise answers: paste this whole block back to the agent\n```json\n" + text + "\n```\n"
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    Q1 = {"id": "docs/muting.md#Q1", "doc": "docs/muting.md", "q": "Q1", "value": "Every tier.\nNo limits."}

    def test_appends_one_dated_line_and_changes_nothing_else(self) -> None:
        doc = make_doc(self.root)
        before = doc.read_text(encoding="utf-8").splitlines()
        result = run("apply", self.answers(self.Q1), "--date", "2026-01-05", "--by", "Ollie", "--json", cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = doc.read_text(encoding="utf-8").splitlines()
        added = [l for l in after if l not in before]
        self.assertEqual(added, ["Answer (2026-01-05, Ollie): Every tier. No limits."])
        at = after.index(added[0])
        self.assertEqual(after[at - 1], "channels?")
        self.assertEqual(after[:at] + after[at + 1:], before)
        # the question now reads as answered
        sheet = sheet_json(self.root)
        self.assertEqual([i["q"] for i in sheet["items"]], ["Q3"])

    def test_second_apply_writes_nothing(self) -> None:
        doc = make_doc(self.root)
        path = self.answers(self.Q1)
        run("apply", path, "--date", "2026-01-05", cwd=self.root)
        once = doc.read_bytes()
        result = run("apply", path, "--date", "2026-01-06", "--json", cwd=self.root)
        self.assertEqual(doc.read_bytes(), once)
        self.assertEqual(json.loads(result.stdout)["skipped"][0]["reason"], "already written")

    def test_crlf_and_bom_survive(self) -> None:
        doc = make_doc(self.root, newline="\r\n", bom=True)
        run("apply", self.answers(self.Q1), "--date", "2026-01-05", cwd=self.root)
        raw = doc.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertIn(b"channels?\r\nAnswer (2026-01-05): Every tier. No limits.\r\n", raw)
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))

    def test_dry_run_writes_nothing(self) -> None:
        doc = make_doc(self.root)
        before = doc.read_bytes()
        result = run("apply", self.answers(self.Q1), "--dry-run", "--json", cwd=self.root)
        self.assertEqual(doc.read_bytes(), before)
        self.assertEqual(len(json.loads(result.stdout)["written"]), 1)

    def test_pasted_text_is_read(self) -> None:
        make_doc(self.root)
        result = run("apply", self.answers(self.Q1, wrap=True), "--json", cwd=self.root)
        self.assertEqual(len(json.loads(result.stdout)["written"]), 1)

    def test_doc_outside_the_project_is_refused(self) -> None:
        outside = Path(self.tmp.name).parent / "outside-promise-test.md"
        make_doc(self.root)
        bad = dict(self.Q1, doc="../outside-promise-test.md")
        result = run("apply", self.answers(bad), "--json", cwd=self.root)
        self.assertFalse(outside.exists())
        self.assertEqual(len(json.loads(result.stdout)["skipped"]), 1)

    def test_unknown_question_is_skipped(self) -> None:
        make_doc(self.root)
        result = run("apply", self.answers(dict(self.Q1, q="Q9")), "--json", cwd=self.root)
        self.assertIn("not a §9 question", json.loads(result.stdout)["skipped"][0]["reason"])

    def test_answers_without_a_doc_question_go_to_the_agent(self) -> None:
        make_doc(self.root)
        other = {"id": "copy", "kind": "approve", "doc": None, "q": None, "value": "Approved", "verdict": "approve"}
        result = run("apply", self.answers(other), "--json", cwd=self.root)
        data = json.loads(result.stdout)
        self.assertEqual((data["written"], data["forAgent"][0]["id"]), ([], "copy"))

    def test_bad_input_exits_2(self) -> None:
        make_doc(self.root)
        (self.root / "junk.txt").write_text("nothing here", encoding="utf-8")
        self.assertEqual(run("apply", "junk.txt", cwd=self.root).returncode, 2)
        self.assertEqual(run("apply", self.answers(self.Q1), "--date", "2026-02-30", cwd=self.root).returncode, 2)
        self.assertEqual(run("apply", self.answers(self.Q1), "--by", "a\nb", cwd=self.root).returncode, 2)


class PaneReplies(unittest.TestCase):
    """The lettered replies a surface that draws its own controls reads from --json, and
    answers handed to apply on standard input: the promise mod's decision pane."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.doc = make_doc(self.root)
        self.asks = self.root / "asks.json"
        self.asks.write_text(json.dumps({"items": [
            {"id": "docs/muting.md#Q1", "why": "Plans differ.", "blocks": "Pricing.",
             "options": [{"label": "Paid tiers only", "because": "b"},
                         {"label": "Every tier", "recommended": True, "because": "a"}]},
            {"id": "copy", "kind": "approve", "text": "Approve the copy", "why": "w", "blocks": "b"},
            {"id": "limit", "kind": "input", "text": "Mute limit?", "proposed": 500, "why": "w", "blocks": "b"},
        ]}), encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def items(self) -> dict:
        return {i["id"]: i for i in sheet_json(self.root, "--asks", str(self.asks))["items"]}

    def test_each_item_carries_its_lettered_replies(self) -> None:
        items = self.items()
        q1 = items["docs/muting.md#Q1"]
        self.assertEqual([(r["code"], r["value"], r["recommended"]) for r in q1["replies"]],
                         [("a", "Every tier", True), ("b", None, False), ("c", "Paid tiers only", False)])
        self.assertTrue(q1["replies"][0]["label"].startswith("Every tier (Recommended)"))
        self.assertTrue(q1["replyWords"])
        copy = items["copy"]
        self.assertEqual([r["value"] for r in copy["replies"]], ["Approved", "Changes requested", "Rejected"])
        self.assertFalse(any(r["recommended"] for r in copy["replies"]))
        self.assertFalse(copy["replyWords"], "an approval takes a letter, as a chat reply does")
        self.assertEqual([(r["code"], r["value"], r["recommended"]) for r in items["limit"]["replies"]],
                         [("a", "500", True)])
        self.assertEqual(items["docs/muting.md#Q3"]["replies"], [])
        self.assertTrue(items["docs/muting.md#Q3"]["replyWords"])

    def test_the_replies_letter_choices_as_a_chat_reply_reads_them(self) -> None:
        sheet = self.root / "sheet.json"
        result = run("sheet", "--docs-home", "docs", "--asks", str(self.asks), "--json", cwd=self.root)
        sheet.write_text(result.stdout, encoding="utf-8")
        numbered = json.loads(result.stdout)["items"]
        n = next(k for k, i in enumerate(numbered, 1) if i["id"] == "docs/muting.md#Q1")
        (self.root / "reply.txt").write_text(f"{n}c\n", encoding="utf-8")
        applied = run("apply", "--reply", "reply.txt", "--sheet", "sheet.json", "--dry-run", "--json",
                      "--date", "2026-01-05", cwd=self.root)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        expected = numbered[n - 1]["replies"][2]["value"]
        self.assertEqual([w["line"] for w in json.loads(applied.stdout)["written"]],
                         [f"Answer (2026-01-05): {expected}"])

    def test_apply_reads_answers_from_standard_input(self) -> None:
        answers = {"format": "promise-answers", "version": 1, "answers": [
            {"id": "docs/muting.md#Q3", "kind": "question", "doc": "docs/muting.md", "q": "Q3",
             "value": "No, it keeps its colour.", "note": None},
            {"id": "limit", "kind": "input", "doc": None, "q": None, "value": "500", "note": None}]}
        result = subprocess.run([sys.executable, str(SCRIPT), "apply", "-", "--date", "2026-01-05", "--by", "Ana",
                                 "--json"], input=json.dumps(answers), capture_output=True, text=True,
                                cwd=str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual([w["line"] for w in out["written"]], ["Answer (2026-01-05, Ana): No, it keeps its colour."])
        self.assertEqual([f["id"] for f in out["forAgent"]], ["limit"])
        self.assertIn("Answer (2026-01-05, Ana): No, it keeps its colour.", self.doc.read_text(encoding="utf-8"))

    def picks(self, picks, *extra: str) -> subprocess.CompletedProcess:
        sheet = sheet_json(self.root, "--asks", str(self.asks))
        data = {"format": "promise-picks", "version": 1, "sheet": sheet, "picks": picks}
        return subprocess.run([sys.executable, str(SCRIPT), "apply", "-", "--date", "2026-01-05", "--by", "Ana",
                               "--json", *extra], input=json.dumps(data), capture_output=True, text=True,
                              cwd=str(self.root))

    def numbered(self) -> dict:
        return {i["id"]: n for n, i in enumerate(sheet_json(self.root, "--asks", str(self.asks))["items"], 1)}

    def test_pane_labels_carry_no_dash_and_name_what_the_note_is_for(self) -> None:
        copy = self.items()["copy"]
        self.assertEqual([r["label"] for r in copy["replies"]], ["Approve", "Request changes", "Reject"])
        self.assertEqual([r.get("noteAsk") for r in copy["replies"]], [None, "what", None])
        self.assertEqual([r.get("noteRequired", False) for r in copy["replies"]], [False, True, False])
        q1 = self.items()["docs/muting.md#Q1"]["replies"]
        self.assertEqual(q1[2]["because"], "b", "a choice carries its own reason")
        self.assertNotIn("because", q1[0], "the Recommended one's reason is already in its label")

    def test_picks_record_what_the_same_chat_reply_records(self) -> None:
        n = self.numbered()
        q1, q3, copy = n["docs/muting.md#Q1"], n["docs/muting.md#Q3"], n["copy"]
        reply_text = f"{q1}c - only yearly\n{q3}: No, it keeps its colour.\n{copy}b - shorter"
        sheet = self.root / "sheet.json"
        sheet.write_text(json.dumps(sheet_json(self.root, "--asks", str(self.asks))), encoding="utf-8")
        (self.root / "reply.txt").write_text(reply_text + "\n", encoding="utf-8")
        chat = run("apply", "--reply", "reply.txt", "--sheet", "sheet.json", "--dry-run", "--json",
                   "--date", "2026-01-05", "--by", "Ana", cwd=self.root)
        self.assertEqual(chat.returncode, 0, chat.stderr)
        pane = self.picks([{"n": q1, "code": "c", "note": "only yearly"}, {"n": q3, "code": None, "note": "No, it keeps its colour."},
                           {"n": copy, "code": "b", "note": "shorter"}], "--dry-run")
        self.assertEqual(pane.returncode, 0, pane.stderr)
        a, b = json.loads(chat.stdout), json.loads(pane.stdout)
        self.assertEqual(b["written"], a["written"])
        self.assertEqual(b["forAgent"], a["forAgent"])
        self.assertEqual(b["notAnswered"], ["limit"])

    def test_a_change_request_must_say_what_and_none_of_these_needs_words(self) -> None:
        n = self.numbered()
        before = self.doc.read_text(encoding="utf-8")
        result = self.picks([{"n": n["copy"], "code": "b", "note": ""}, {"n": n["docs/muting.md#Q1"], "code": "b"},
                             {"n": n["docs/muting.md#Q3"], "code": None, "note": "kept"}])
        self.assertEqual(result.returncode, 2)
        self.assertIn(f"{n['copy']}b: say what to change in the note", result.stderr)
        self.assertIn("'None of these' needs your own words", result.stderr)
        self.assertEqual(self.doc.read_text(encoding="utf-8"), before, "one bad pick writes nothing")

    def test_a_sheet_that_is_not_decisions_pys_or_another_version_is_refused_in_one_line(self) -> None:
        for data, message in (
                ({"format": "promise-picks", "version": 1, "sheet": {"items": [{"id": "x"}]}, "picks": []},
                 "items are not decisions.py's"),
                ({"format": "promise-picks", "version": 2, "sheet": {"items": []}, "picks": []},
                 "promise-picks version 2 is not 1")):
            result = subprocess.run([sys.executable, str(SCRIPT), "apply", "-"], input=json.dumps(data),
                                    capture_output=True, text=True, cwd=str(self.root))
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(message, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_a_code_is_one_letter(self) -> None:
        n = self.numbered()["copy"]
        for bad in ("", "ab", 1):
            result = self.picks([{"n": n, "code": bad}])
            self.assertEqual(result.returncode, 2, bad)
            self.assertNotIn("Answer (", result.stdout)

    def test_json_names_each_item_kind_for_the_pane(self) -> None:
        self.assertEqual({i: v["kindTag"] for i, v in self.items().items()},
                         {"docs/muting.md#Q1": "question", "docs/muting.md#Q3": "question",
                          "copy": "approval", "limit": "value"})

    def test_picks_that_name_no_item_or_one_twice_are_refused(self) -> None:
        result = self.picks([{"n": 1, "code": "a"}, {"n": 1, "code": "a"}, {"n": 99, "code": "a"}, {"n": True}])
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.count("not one item"), 3, result.stderr)

    def test_standard_input_without_answers_is_refused_with_one_line(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT), "apply", "-"], input="not json",
                                capture_output=True, text=True, cwd=str(self.root))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.strip(), "decisions.py: - holds no promise-answers JSON")


if __name__ == "__main__":
    unittest.main()
