"""Tests for §0 protection: diff_outcome.py, the PreToolUse hook and the Action.

Run from the repo root:

    python3 -m unittest discover -s tests -v

§0 of an `agreed`, `building` or `shipped` doc may change without the human
only in its rule tags and its `Scenarios:` count; any other change must set
`Status: draft` in the same change. diff_outcome.py checks two versions (two
files, or a git ref and the working tree); hooks/guard_section0.py applies the
same check to the model's Edit, MultiEdit and Write calls before they run.
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
SCRIPTS_DIR = REPO / "skills" / "promise" / "scripts"
DIFF = SCRIPTS_DIR / "diff_outcome.py"
HOOK = REPO / "hooks" / "guard_section0.py"
HOOKS_JSON = REPO / "hooks" / "hooks.json"
ACTION = REPO / "action.yml"
CI_TEMPLATE = SCRIPTS_DIR.parent / "templates" / "promise-ci.yml"
EXAMPLE = REPO / "examples" / "channel-muting.md"

RULE = "- A muted channel never sends a push or a badge count until it is unmuted."


def agreed_text() -> str:
    text = EXAMPLE.read_text(encoding="utf-8")
    assert "Status: draft" in text and RULE in text
    return text.replace("Status: draft", "Status: agreed", 1)


def run(*args: str, stdin: str = None, cwd: str = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args], input=stdin, capture_output=True, text=True, cwd=cwd
    )


def git(cwd: str, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=cwd, check=True, capture_output=True,
    )


class DiffFiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.before = self.dir / "before.md"
        self.before.write_text(agreed_text(), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, after_text: str) -> subprocess.CompletedProcess:
        after = self.dir / "after.md"
        after.write_text(after_text, encoding="utf-8")
        return run(str(DIFF), str(self.before), str(after), "--json")

    def rules(self, result: subprocess.CompletedProcess):
        return [(f["rule"], f["severity"]) for f in json.loads(result.stdout)["findings"]]

    def test_no_change_passes(self):
        result = self.check(agreed_text())
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.rules(result), [])

    def test_tag_and_scenarios_changes_pass(self):
        text = agreed_text().replace("→ AT-3", "→ AT-3, AT-4", 1)
        text = text.replace("**Scenarios:** 3 acceptance rows", "**Scenarios:** 4 acceptance rows", 1)
        self.assertNotEqual(text, agreed_text())
        result = self.check(text)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_agent_notes_and_other_sections_are_not_protected(self):
        text = agreed_text().replace("## 1. Problem", "## 1. Problem\n\nA new sentence.", 1)
        text = text.replace("Agent notes (appended", "Agent notes (appended — edited", 1)
        self.assertEqual(self.check(text).returncode, 0)

    def test_rule_change_on_agreed_is_an_error(self):
        result = self.check(agreed_text().replace(RULE, RULE[:-1] + " or a day passes.", 1))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.rules(result), [("S0_CHANGED", "error")])
        self.assertIn("a day passes", json.loads(result.stdout)["findings"][0]["message"])

    def test_removed_rule_and_outcome_change_are_errors(self):
        self.assertEqual(self.check(agreed_text().replace(RULE, "", 1)).returncode, 1)
        text = agreed_text().replace("**Outcome:** A member", "**Outcome:** An admin", 1)
        self.assertEqual(self.check(text).returncode, 1)

    def test_whitespace_only_change_passes(self):
        text = agreed_text().replace(RULE, RULE.replace(" never ", "  never "), 1)
        self.assertEqual(self.check(text).returncode, 0)

    def test_change_with_status_back_to_draft_is_a_warning(self):
        text = agreed_text().replace(RULE, RULE[:-1] + " or a day passes.", 1)
        text = text.replace("Status: agreed", "Status: draft", 1)
        result = self.check(text)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.rules(result), [("S0_REOPENED", "warn")])

    def test_a_draft_before_is_not_checked(self):
        self.before.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        text = EXAMPLE.read_text(encoding="utf-8").replace(RULE, "- Something else entirely.", 1)
        self.assertEqual(self.check(text).returncode, 0)

    def test_building_and_shipped_are_protected(self):
        for status in ("building", "shipped"):
            with self.subTest(status=status):
                before = agreed_text().replace("Status: agreed", f"Status: {status}", 1)
                self.before.write_text(before, encoding="utf-8")
                self.assertEqual(self.check(before.replace(RULE, "- Changed.", 1)).returncode, 1)

    def test_usage_errors_exit_two(self):
        self.assertEqual(run(str(DIFF)).returncode, 2)
        self.assertEqual(run(str(DIFF), "--dir", str(self.dir)).returncode, 2)
        self.assertEqual(run(str(DIFF), str(self.dir / "missing.md"), str(self.before)).returncode, 2)


class DiffGit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.tmp.name, "init", "-q", "-b", "main")
        self.docs = self.repo / "docs" / "designs"
        self.docs.mkdir(parents=True)
        (self.docs / "muting.md").write_text(agreed_text(), encoding="utf-8")
        git(self.tmp.name, "add", "-A")
        git(self.tmp.name, "commit", "-q", "-m", "base")

    def tearDown(self):
        self.tmp.cleanup()

    def test_dir_mode_catches_a_changed_rule(self):
        doc = self.docs / "muting.md"
        doc.write_text(agreed_text().replace(RULE, "- Changed.", 1), encoding="utf-8")
        result = run(str(DIFF), "--dir", str(self.docs), "--base", "main", "--json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual([f["rule"] for r in data for f in r["findings"]], ["S0_CHANGED"])

    def test_dir_mode_passes_a_new_doc_and_an_unchanged_one(self):
        (self.docs / "new.md").write_text(agreed_text(), encoding="utf-8")
        result = run(str(DIFF), "--dir", str(self.docs), "--base", "main")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_single_doc_against_a_ref(self):
        doc = self.docs / "muting.md"
        doc.write_text(agreed_text().replace("→ AT-3", "→ UNTESTED", 1), encoding="utf-8")
        self.assertEqual(run(str(DIFF), str(doc), "--base", "main").returncode, 0)

    def test_unknown_ref_is_a_usage_error(self):
        result = run(str(DIFF), "--dir", str(self.docs), "--base", "no-such-ref")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown git ref", result.stderr)


class Hook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.doc = Path(self.tmp.name) / "muting.md"
        self.doc.write_text(agreed_text(), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, tool: str, tool_input: dict) -> subprocess.CompletedProcess:
        event = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
                 "cwd": self.tmp.name}
        return run(str(HOOK), stdin=json.dumps(event))

    def test_edit_to_an_agreed_rule_is_blocked(self):
        result = self.hook("Edit", {"file_path": str(self.doc), "old_string": RULE,
                                    "new_string": "- Changed."})
        self.assertEqual(result.returncode, 2)
        self.assertIn("§0", result.stderr)
        self.assertIn("Status: draft", result.stderr)

    def test_tag_only_edit_passes(self):
        result = self.hook("Edit", {"file_path": str(self.doc), "old_string": "→ AT-3",
                                    "new_string": "→ AT-3, AT-4"})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_edit_that_also_sets_draft_passes(self):
        edits = [{"old_string": RULE, "new_string": "- Changed."},
                 {"old_string": "Status: agreed", "new_string": "Status: draft"}]
        result = self.hook("MultiEdit", {"file_path": str(self.doc), "edits": edits})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_multiedit_and_write_are_checked(self):
        edits = [{"old_string": "→ AT-3", "new_string": "→ AT-4"},
                 {"old_string": RULE, "new_string": "- Changed."}]
        self.assertEqual(self.hook("MultiEdit", {"file_path": str(self.doc), "edits": edits}).returncode, 2)
        content = agreed_text().replace(RULE, "- Changed.", 1)
        self.assertEqual(self.hook("Write", {"file_path": str(self.doc), "content": content}).returncode, 2)

    def test_relative_path_resolves_against_cwd(self):
        result = self.hook("Edit", {"file_path": "muting.md", "old_string": RULE, "new_string": "- X."})
        self.assertEqual(result.returncode, 2)

    def test_draft_doc_non_markdown_and_new_files_pass(self):
        self.doc.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertEqual(self.hook("Edit", {"file_path": str(self.doc), "old_string": RULE,
                                            "new_string": "- X."}).returncode, 0)
        other = Path(self.tmp.name) / "notes.txt"
        other.write_text("## 0. TLDR\nStatus: agreed\n", encoding="utf-8")
        self.assertEqual(self.hook("Write", {"file_path": str(other), "content": "x"}).returncode, 0)
        new = Path(self.tmp.name) / "new.md"
        self.assertEqual(self.hook("Write", {"file_path": str(new), "content": agreed_text()}).returncode, 0)

    def test_other_tools_and_bad_input_fail_open(self):
        self.assertEqual(self.hook("Bash", {"command": "rm -rf /"}).returncode, 0)
        self.assertEqual(run(str(HOOK), stdin="not json").returncode, 0)
        self.assertEqual(self.hook("Edit", {"file_path": str(self.doc), "old_string": "absent",
                                            "new_string": "x"}).returncode, 0)


class Wiring(unittest.TestCase):
    def test_hooks_json_runs_the_guard_before_edits(self):
        config = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        entries = config["hooks"]["PreToolUse"]
        self.assertEqual(len(entries), 2, "the §0 guard, then the GitHub text guard")
        for tool in ("Edit", "MultiEdit", "Write"):
            self.assertIn(tool, entries[0]["matcher"])
        command = entries[0]["hooks"][0]["command"]
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/hooks/guard_section0.py", command)

    def test_action_runs_check_py_from_its_own_path(self):
        # check.py runs lint_outcome.py and diff_outcome.py --dir (tests/test_check.py);
        # the Action passes its inputs through and leaves the map step out.
        text = ACTION.read_text(encoding="utf-8")
        self.assertIn("using: composite", text)
        self.assertIn("${{ github.action_path }}/skills/promise/scripts", text)
        self.assertIn('python3 "$SCRIPTS/check.py" "${args[@]}"', text)
        self.assertIn('args=(--no-map)', text)
        self.assertIn('args+=(--docs-home "$DOCS_HOME")', text)  # only when the input is set
        self.assertIn("args+=(--no-lint)", text)
        self.assertIn('args+=(--base "$base")', text)
        self.assertIn('base="origin/$GITHUB_BASE_REF"', text)

    def test_ci_template_uses_the_action(self):
        text = CI_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("uses: osouthgate/promise@v1", text)
        self.assertIn("pull_request:", text)


if __name__ == "__main__":
    unittest.main()
