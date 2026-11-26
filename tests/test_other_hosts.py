"""Tests for promise outside Claude Code: install_skill.py, hooks/precommit.py,
adopt.py --agents-md and the pre-commit framework entries.

Run from the repo root:

    python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO = TESTS_DIR.parent
SKILL = REPO / "skills" / "promise"
INSTALL = SKILL / "scripts" / "install_skill.py"
ADOPT = SKILL / "scripts" / "adopt.py"
PRECOMMIT = REPO / "hooks" / "precommit.py"
HOOKS_YAML = REPO / ".pre-commit-hooks.yaml"
EXAMPLE = REPO / "examples" / "channel-muting.md"
RULE = "- A muted channel never sends a push or a badge count until it is unmuted."


def run(*args: str, cwd: str = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, cwd=cwd)


def git(cwd, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
        cwd=cwd, capture_output=True, text=True,
    )


def agreed() -> str:
    return EXAMPLE.read_text(encoding="utf-8").replace("Status: draft", "Status: agreed", 1)


class Installer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def install(self, *args):
        result = run(INSTALL, "--home", self.home, *args)
        return result.returncode, json.loads(result.stdout)

    def test_default_is_the_shared_agents_folder(self):
        code, data = self.install()
        self.assertEqual(code, 0)
        target = self.home / ".agents" / "skills" / "promise"
        self.assertEqual([(r["host"], r["result"]) for r in data["skills"]], [("agents", "installed")])
        self.assertTrue(target.is_symlink())
        self.assertTrue((target / "SKILL.md").is_file())

    def test_all_hosts_and_a_second_run_is_a_no_op(self):
        code, data = self.install("--host", "all")
        self.assertEqual(sorted(r["host"] for r in data["skills"]), ["agents", "codex", "cursor"])
        for host in (".agents", ".codex", ".cursor"):
            self.assertTrue((self.home / host / "skills" / "promise" / "SKILL.md").is_file())
        code, data = self.install("--host", "all")
        self.assertEqual(code, 0)
        self.assertEqual({r["result"] for r in data["skills"]}, {"already-installed"})

    def test_copy_mode_copies_and_recognises_itself(self):
        code, data = self.install("--host", "cursor", "--copy")
        target = self.home / ".cursor" / "skills" / "promise"
        self.assertFalse(target.is_symlink())
        self.assertTrue((target / "scripts" / "lint_outcome.py").is_file())
        self.assertFalse(list(target.rglob("__pycache__")))
        self.assertEqual(self.install("--host", "cursor", "--copy")[1]["skills"][0]["result"], "already-installed")

    def test_something_else_in_the_way_is_refused_not_overwritten(self):
        target = self.home / ".codex" / "skills" / "promise"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("someone else's skill", encoding="utf-8")
        code, data = self.install("--host", "codex")
        self.assertEqual(code, 1)
        self.assertEqual(data["skills"][0]["result"], "refused")
        self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "someone else's skill")

    def test_dry_run_writes_nothing(self):
        code, data = self.install("--dry-run", "--host", "all")
        self.assertEqual({r["result"] for r in data["skills"]}, {"would-install"})
        self.assertEqual(list(self.home.iterdir()), [])

    def test_project_scope_and_usage_errors(self):
        project = self.home / "proj"
        project.mkdir()
        result = run(INSTALL, "--project", project, "--host", "agents")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((project / ".agents" / "skills" / "promise" / "SKILL.md").is_file())
        self.assertEqual(run(INSTALL, "--git-hook").returncode, 2)
        self.assertEqual(run(INSTALL, "--project", self.home / "missing").returncode, 2)


class GitHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "muting.md").write_text(agreed(), encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "doc")

    def tearDown(self):
        self.tmp.cleanup()

    def commit_change(self, old, new) -> subprocess.CompletedProcess:
        doc = self.repo / "docs" / "muting.md"
        doc.write_text(doc.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")
        git(self.repo, "add", "docs/muting.md")
        return git(self.repo, "commit", "-q", "-m", "change")

    def test_installed_hook_blocks_a_rule_change_and_passes_a_tag_change(self):
        result = run(INSTALL, "--project", self.repo, "--git-hook")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["gitHook"]["result"], "installed")
        blocked = self.commit_change(RULE, "- Changed.")
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("S0_CHANGED", blocked.stderr)
        git(self.repo, "reset", "-q", "--hard", "HEAD")
        self.assertEqual(self.commit_change("→ AT-3", "→ AT-3, AT-4").returncode, 0)

    def test_an_existing_hook_is_refused(self):
        hook = self.repo / ".git" / "hooks" / "pre-commit"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        result = run(INSTALL, "--project", self.repo, "--git-hook")
        self.assertEqual(result.returncode, 1)
        self.assertIn("add this line", json.loads(result.stdout)["gitHook"]["reason"])
        self.assertEqual(hook.read_text(encoding="utf-8"), "#!/bin/sh\nexit 0\n")

    def test_precommit_section0_and_lint_directly(self):
        doc = self.repo / "docs" / "muting.md"
        doc.write_text(agreed().replace(RULE, "- Changed.", 1), encoding="utf-8")
        git(self.repo, "add", "docs/muting.md")
        self.assertEqual(run(PRECOMMIT, "section0", "docs/muting.md", cwd=self.repo).returncode, 1)
        self.assertEqual(run(PRECOMMIT, "section0", "README.txt", cwd=self.repo).returncode, 0)
        self.assertEqual(run(PRECOMMIT, "lint", "docs/muting.md", cwd=self.repo).returncode, 0)
        (self.repo / "bad.md").write_text("## 0. TLDR\n", encoding="utf-8")
        self.assertEqual(run(PRECOMMIT, "lint", "bad.md", cwd=self.repo).returncode, 1)
        self.assertEqual(run(PRECOMMIT).returncode, 2)


class AgentsMd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def block(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        return text[text.index("<!-- promise:begin"):text.index("<!-- promise:end -->")]

    def test_agents_md_gets_the_same_block_and_a_rerun_changes_nothing(self):
        result = run(ADOPT, "--cwd", self.cwd, "--docs-home", "docs/designs", "--agents-md")
        data = json.loads(result.stdout)
        self.assertTrue(data["agentsMdWritten"])
        self.assertEqual(self.block(self.cwd / "AGENTS.md"), self.block(self.cwd / "CLAUDE.md"))
        again = json.loads(run(ADOPT, "--cwd", self.cwd, "--agents-md").stdout)
        self.assertFalse(again["changed"])

    def test_existing_agents_md_content_is_kept(self):
        (self.cwd / "AGENTS.md").write_text("# Build\n\nRun make.\n", encoding="utf-8")
        run(ADOPT, "--cwd", self.cwd, "--docs-home", "docs/designs", "--agents-md")
        text = (self.cwd / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Build\n\nRun make.\n"))
        self.assertIn("$promise", text)

    def test_a_claude_md_symlinked_to_agents_md_is_written_once(self):
        (self.cwd / "AGENTS.md").write_text("# Notes\n", encoding="utf-8")
        os.symlink("AGENTS.md", self.cwd / "CLAUDE.md")
        data = json.loads(run(ADOPT, "--cwd", self.cwd, "--docs-home", "docs/designs", "--agents-md").stdout)
        self.assertFalse(data["agentsMdWritten"])
        self.assertEqual((self.cwd / "AGENTS.md").read_text(encoding="utf-8").count("<!-- promise:begin"), 1)

    def test_without_the_flag_no_agents_md_and_no_new_keys(self):
        data = json.loads(run(ADOPT, "--cwd", self.cwd, "--docs-home", "docs/designs").stdout)
        self.assertNotIn("agentsMdWritten", data)
        self.assertFalse((self.cwd / "AGENTS.md").exists())


class PreCommitFramework(unittest.TestCase):
    def test_each_hook_entry_is_an_executable_script(self):
        text = HOOKS_YAML.read_text(encoding="utf-8")
        ids = re.findall(r"^- id: (\S+)", text, re.M)
        entries = re.findall(r"^  entry: (\S+)", text, re.M)
        self.assertEqual(ids, ["promise-section0", "promise-lint"])
        for entry in entries:
            path = REPO / entry
            self.assertTrue(path.is_file(), entry)
            self.assertTrue(os.access(path, os.X_OK), f"{entry} is not executable")
        self.assertTrue(os.access(INSTALL, os.X_OK))


if __name__ == "__main__":
    unittest.main()
