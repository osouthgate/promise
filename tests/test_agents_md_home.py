"""The promise section may live in AGENTS.md, the one file every agent reads:
when CLAUDE.md imports it (a line ``@AGENTS.md``) and holds no section, or when
there is no CLAUDE.md. orient counts the project as adopted, and adopt.py
refreshes the section there and never adds a second copy to CLAUDE.md."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "skills" / "promise" / "scripts"
ORIENT = SCRIPTS_DIR / "orient.py"
ADOPT = SCRIPTS_DIR / "adopt.py"
MARKER = "<!-- promise:begin"


def run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)


class AgentsMdHome(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "docs" / "promises").mkdir(parents=True)

    def write(self, name: str, text: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def adopt(self, *extra: str) -> dict:
        done = run(ADOPT, "--cwd", str(self.root), "--docs-home", "docs/promises", *extra)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def orient(self) -> dict:
        done = run(ORIENT, "--cwd", str(self.root))
        return json.loads(done.stdout)

    def test_a_claude_md_that_imports_agents_md_keeps_the_section_there(self) -> None:
        claude = self.write("CLAUDE.md", "@AGENTS.md\n")
        agents = self.write("AGENTS.md", "# Agents\n\nKeep this.\n")
        data = self.adopt()
        self.assertTrue(data["agentsMdWritten"])
        self.assertFalse(data["claudeMdWritten"])
        self.assertEqual(claude.read_text(encoding="utf-8"), "@AGENTS.md\n")
        text = agents.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Agents\n\nKeep this.\n"))
        self.assertEqual(text.count(MARKER), 1)
        found = self.orient()
        self.assertTrue(found["adopted"])
        self.assertEqual(found["claudeMd"]["path"], str(claude.resolve()))
        self.assertEqual(found["claudeMd"]["sectionPath"], str(agents.resolve()))
        # A second run changes nothing.
        again = run(ADOPT, "--cwd", str(self.root))
        self.assertFalse(json.loads(again.stdout)["changed"], again.stderr)

    def test_a_section_moved_by_hand_is_found_and_refreshed_in_agents_md(self) -> None:
        self.write("CLAUDE.md", "@AGENTS.md\n\nMore notes.\n")
        self.adopt("--no-claude-md")  # the config only
        section = ("<!-- promise:begin (managed by the promise skill; run /promise adopt to refresh it) -->\n"
                   "## Capability work goes through `/promise`\nstale text\n<!-- promise:end -->\n")
        agents = self.write("AGENTS.md", "# Agents\n\n" + section)
        self.assertTrue(self.orient()["adopted"])
        data = self.adopt()
        self.assertTrue(data["agentsMdWritten"])
        self.assertNotIn("stale text", agents.read_text(encoding="utf-8"))
        self.assertNotIn(MARKER, (self.root / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_with_no_claude_md_a_section_in_agents_md_counts(self) -> None:
        self.write("CLAUDE.md", "@AGENTS.md\n")
        self.write("AGENTS.md", "# Agents\n")
        self.adopt()
        (self.root / "CLAUDE.md").unlink()
        found = self.orient()
        self.assertTrue(found["adopted"])
        self.assertIsNone(found["claudeMd"]["path"])
        data = self.adopt()
        self.assertFalse(data["changed"])
        self.assertFalse((self.root / "CLAUDE.md").exists())

    def test_an_agents_md_without_the_section_still_gets_a_claude_md(self) -> None:
        self.write("AGENTS.md", "# Agents\n")
        data = self.adopt()
        self.assertTrue(data["claudeMdWritten"])
        self.assertNotIn("agentsMdWritten", data)
        self.assertIn(MARKER, (self.root / "CLAUDE.md").read_text(encoding="utf-8"))
        self.assertNotIn(MARKER, (self.root / "AGENTS.md").read_text(encoding="utf-8"))

    def test_an_import_of_another_file_is_not_agents_md(self) -> None:
        self.write("CLAUDE.md", "@docs/AGENTS.md\nSee @AGENTS.md in the text.\n")
        self.write("AGENTS.md", "# Agents\n")
        data = self.adopt()
        self.assertTrue(data["claudeMdWritten"])
        self.assertIn(MARKER, (self.root / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_a_claude_md_under_dot_claude_imports_the_root_agents_md(self) -> None:
        self.write(".claude/CLAUDE.md", "@../AGENTS.md\n")
        agents = self.write("AGENTS.md", "# Agents\n")
        data = self.adopt()
        self.assertTrue(data["agentsMdWritten"])
        self.assertIn(MARKER, agents.read_text(encoding="utf-8"))
        self.assertEqual(self.orient()["claudeMd"]["sectionPath"], str(agents.resolve()))

    def test_a_section_in_both_files_is_a_warning(self) -> None:
        self.write("CLAUDE.md", "@AGENTS.md\n")
        agents = self.write("AGENTS.md", "# Agents\n")
        self.adopt()
        block = agents.read_text(encoding="utf-8").split("# Agents\n", 1)[1]
        self.write("CLAUDE.md", "@AGENTS.md\n" + block)
        found = self.orient()
        self.assertTrue(found["adopted"])
        self.assertTrue(any("reads it twice" in w for w in found["warnings"]), found["warnings"])


if __name__ == "__main__":
    unittest.main()
