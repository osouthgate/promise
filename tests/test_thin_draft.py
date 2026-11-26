"""Tests for the thin draft: a `draft` doc that holds the human half only.

A thin draft carries `Depth: thin` in its header. The lint accepts it with
no §6 table, no §4-§7 Why lines, no §3 example and, as a warning, no rule;
it rejects `Depth: thin` on any status past `draft` (THIN_DRAFT), so a thin
doc cannot be agreed. `render_outcome.py --thin` writes the shape.
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
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"
LINT = SCRIPTS_DIR / "lint_outcome.py"
RENDER = SCRIPTS_DIR / "render_outcome.py"
THIN = FIXTURES_DIR / "thin_conforming.md"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)


def lint_text(text: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "doc.md"
        path.write_text(text, encoding="utf-8")
        result = run(LINT, str(path), "--json")
        data = json.loads(result.stdout)
        data["returncode"] = result.returncode
        return data


class ThinDraftLint(unittest.TestCase):
    def test_filled_thin_draft_lints_clean(self):
        data = lint_text(THIN.read_text(encoding="utf-8"))
        self.assertEqual(data["findings"], [])
        self.assertEqual(data["returncode"], 0)

    def test_thin_on_agreed_is_an_error(self):
        text = THIN.read_text(encoding="utf-8").replace("Status: draft", "Status: agreed", 1)
        data = lint_text(text)
        thin = [f for f in data["findings"] if f["rule"] == "THIN_DRAFT"]
        self.assertEqual(len(thin), 1, data["findings"])
        self.assertEqual(thin[0]["severity"], "error")
        self.assertIn("agreed", thin[0]["message"])
        # Past draft the doc is held to the full shape again.
        rules = {f["rule"] for f in data["findings"]}
        self.assertIn("ACCEPTANCE_TABLE", rules)
        self.assertIn("WHY_LINE", rules)

    def test_depth_other_than_thin_is_an_error(self):
        data = lint_text((FIXTURES_DIR / "thin_draft.md").read_text(encoding="utf-8"))
        self.assertEqual([f["rule"] for f in data["findings"]], ["THIN_DRAFT"])

    def test_empty_rules_is_a_warning_on_a_thin_draft(self):
        text = THIN.read_text(encoding="utf-8")
        rule = "- A muted channel never sends a push or a badge count until it is unmuted.  → UNTESTED\n"
        self.assertIn(rule, text)
        data = lint_text(text.replace(rule, "", 1))
        self.assertEqual(
            [(f["rule"], f["severity"]) for f in data["findings"]], [("RULES_PRESENT", "warn")]
        )
        self.assertEqual(data["returncode"], 0)

    def test_empty_rules_stays_an_error_on_a_full_draft(self):
        text = THIN.read_text(encoding="utf-8").replace("Depth: thin\n", "", 1)
        rule = "- A muted channel never sends a push or a badge count until it is unmuted.  → UNTESTED\n"
        data = lint_text(text.replace(rule, "", 1))
        present = [f for f in data["findings"] if f["rule"] == "RULES_PRESENT"]
        self.assertEqual([f["severity"] for f in present], ["error"])

    def test_a_table_on_a_thin_draft_is_still_checked(self):
        text = THIN.read_text(encoding="utf-8").replace(
            "## 6. Acceptance\n*(agent drafts, human confirms)*\n",
            "## 6. Acceptance\n*(agent drafts, human confirms)*\n\n"
            "| # | Given | When | Then | Altitude | Row |\n"
            "|---|-------|------|------|----------|-----|\n"
            "| AT-1 | a | b |  | data |  |\n",
            1,
        )
        rules = {f["rule"] for f in lint_text(text)["findings"]}
        self.assertIn("ACCEPTANCE_TABLE", rules)

    def test_scenarios_claim_is_still_checked(self):
        # the render writes the count-free line; a counted one is still checked
        text = THIN.read_text(encoding="utf-8").replace(
            "the acceptance rows in §6 and the worked examples in §3.",
            "0 acceptance rows (§6), 1 worked example (§3).", 1)
        rules = [f["rule"] for f in lint_text(text)["findings"]]
        self.assertEqual(rules, ["SCENARIOS_COUNT"])
        text = text.replace("1 worked example", "0 worked examples", 1)
        self.assertEqual([f["rule"] for f in lint_text(text)["findings"]], [])


PENDING = "*Not written yet: this is a thin draft. Run `/promise revise` on this doc to write it.*"


class ThinDraftHoldsTheHumanHalfOnly(unittest.TestCase):
    """A thin draft's §3-§7 each say they are not written yet, and §4-§7
    hold nothing else: the agent half of a thin doc is empty. The repro
    is a moved legacy doc marked Depth: thin with §3-§7 written, which
    linted clean."""

    def with_section(self, n: int, name: str, body: str, text: str = "") -> str:
        """``text`` (the thin fixture by default) with §n's body after its
        role line replaced by ``body``."""
        text = text or THIN.read_text(encoding="utf-8")
        heading = f"## {n}. {name}\n"
        start = text.index(heading)
        role_end = text.index("\n", start + len(heading)) + 1
        end = text.index("\n## ", role_end) + 1
        return text[:role_end] + body + text[end:]

    def thin_findings(self, text: str) -> list:
        data = lint_text(text)
        return [(f["line"], f["message"]) for f in data["findings"] if f["rule"] == "THIN_DRAFT"]

    def test_text_in_section_four_to_seven_is_a_finding(self) -> None:
        for n, name in ((4, "Invariants"), (5, "Mechanism"), (6, "Acceptance"), (7, "Build phases")):
            with self.subTest(section=n):
                text = self.with_section(n, name, f"\n{PENDING}\n\n- the agent wrote this anyway\n\n")
                found = self.thin_findings(text)
                self.assertEqual(len(found), 1, found)
                self.assertIn(f"§{n} holds text on a thin draft (1 line(s))", found[0][1])
                line = text.splitlines().index("- the agent wrote this anyway") + 1
                self.assertEqual(found[0][0], line)

    def test_only_a_line_that_is_just_the_marker_is_exempt(self) -> None:
        # Agent-half text on the marker's own line used to pass: any line
        # that held "not written yet" anywhere was exempt.
        for content in ("- Not written yet in full, but: a token is never stored in plain text.",
                        "Not written yet in full, but: a token is never stored in plain text.",
                        "A token is never stored in plain text; the rest is not written yet."):
            with self.subTest(content=content):
                text = self.with_section(4, "Invariants", f"\n{PENDING}\n\n{content}\n\n")
                found = self.thin_findings(text)
                self.assertEqual(len(found), 1, found)
                self.assertEqual(found[0][0], text.splitlines().index(content) + 1)
                self.assertIn("§4 holds text on a thin draft (1 line(s))", found[0][1])
        # alone, that line is text, and §4 no longer says it is not written yet
        found = self.thin_findings(self.with_section(4, "Invariants", f"\n{content}\n\n"))
        self.assertEqual([m.split(";")[0] for _l, m in found],
                         ["§4 does not say it is not written yet", "§4 holds text on a thin draft (1 line(s))"])
        # the marker as the template writes it, or alone, is not text
        for marker in (PENDING, "Not written yet.", "*Not written yet*", "_not written yet:_"):
            with self.subTest(marker=marker):
                self.assertEqual(self.thin_findings(self.with_section(4, "Invariants", f"\n{marker}\n\n")), [])

    def test_a_why_line_is_agent_half_text(self) -> None:
        text = self.with_section(6, "Acceptance", f"\n{PENDING}\n\nWhy — what breaks without it: no rows.\n\n")
        found = self.thin_findings(text)
        self.assertEqual([m for _l, m in found], ["§6 holds text on a thin draft (1 line(s)); a thin draft holds "
                                                  "the human half only: write the agent half with revise and "
                                                  "remove the Depth: line, or move the text out"])

    def test_a_section_that_does_not_say_it_is_not_written_yet_is_a_finding(self) -> None:
        text = self.with_section(5, "Mechanism", "\n")
        found = self.thin_findings(text)
        self.assertEqual(len(found), 1, found)
        self.assertIn("§5 does not say it is not written yet", found[0][1])

    def test_a_seed_example_in_section_three_is_the_human_half(self) -> None:
        seed = ("\n" + PENDING + "\n\n### Example: Ana mutes a busy channel\n\n"
                "Ana mutes #general and gets no push from it.\n\n")
        text = self.with_section(3, "Worked examples", seed).replace("0 worked examples", "1 worked example", 1)
        data = lint_text(text)
        self.assertEqual(data["findings"], [])
        self.assertEqual(data["returncode"], 0)

    def test_section_three_still_says_the_rest_is_not_written_yet(self) -> None:
        seed = "\n### Example: Ana mutes a busy channel\n\nAna mutes #general and gets no push from it.\n\n"
        text = self.with_section(3, "Worked examples", seed).replace("0 worked examples", "1 worked example", 1)
        found = self.thin_findings(text)
        self.assertEqual(len(found), 1, found)
        self.assertIn("§3 does not say it is not written yet", found[0][1])

    def test_a_moved_doc_with_every_section_written_is_not_thin(self) -> None:
        # The repro: a full agent half under a Depth: thin header.
        text = THIN.read_text(encoding="utf-8")
        for n, name in ((4, "Invariants"), (5, "Mechanism"), (7, "Build phases")):
            text = self.with_section(n, name, "\nWritten from the legacy doc.\n\nWhy — what breaks without it: x.\n\n",
                                     text)
        data = lint_text(text)
        self.assertEqual(data["returncode"], 1)
        messages = [f["message"].split(";")[0] for f in data["findings"]]
        self.assertEqual(messages, [
            "§4 does not say it is not written yet", "§4 holds text on a thin draft (2 line(s))",
            "§5 does not say it is not written yet", "§5 holds text on a thin draft (2 line(s))",
            "§7 does not say it is not written yet", "§7 holds text on a thin draft (2 line(s))",
        ], data["findings"])

    def test_the_rule_is_only_for_a_thin_draft(self) -> None:
        text = self.with_section(4, "Invariants", f"\n{PENDING}\n\n- text\n\n").replace("Depth: thin\n", "", 1)
        self.assertEqual(self.thin_findings(text), [])


class ThinRender(unittest.TestCase):
    def render(self, *extra: str) -> str:
        result = run(
            RENDER, "--title", "Channel muting", "--owner", "Ollie", "--date", "2026-01-01",
            "--docs-home", "unused", "--dry-run", *extra,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_thin_render_adds_depth_and_cuts_the_agent_half(self):
        text = self.render("--thin")
        self.assertIn("\nSupersedes: —\nDepth: thin\n", text)
        self.assertIn("**Scenarios:** the acceptance rows in §6 and the worked examples in §3.", text)
        self.assertEqual(text.count("→ UNTESTED"), 1)
        self.assertNotIn("→ AT-", text)
        self.assertNotIn("| AT-1", text)
        self.assertNotIn("Why — what breaks without it:", text)
        self.assertEqual(text.count("this is a thin draft"), 5)

    def test_raw_thin_render_reports_only_placeholders(self):
        rules = {f["rule"] for f in lint_text(self.render("--thin"))["findings"]}
        self.assertEqual(rules, {"PLACEHOLDER"})

    def test_filled_fixture_matches_the_thin_render_shape(self):
        # The fixture is the thin render with its slots filled; every line
        # outside §0, the agent notes and §9 is the render's line.
        rendered = self.render("--thin").splitlines()
        fixture = THIN.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(rendered), len(fixture))
        differing = [i for i, (a, b) in enumerate(zip(rendered, fixture)) if a != b]
        self.assertEqual(len(differing), 6, differing)  # the five slots, and the decision policy the human picked

    def test_full_render_is_unchanged_without_the_flag(self):
        text = self.render()
        self.assertNotIn("Depth:", text)
        self.assertIn("| AT-1", text)


if __name__ == "__main__":
    unittest.main()
