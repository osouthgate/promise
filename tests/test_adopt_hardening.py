"""Hardening tests for the promise skill's adopt.py script.

Run from the repo root:

    python3 -m unittest discover -s tests -v

Mirrors test_scripts.py's own conventions: the script is located relative
to this file and exercised as a real subprocess (argv, stdout, stderr,
exit code). Every scenario is built in a temporary directory. What is
locked here, one class each: the config it writes ("version": 1, all
three command keys once any is detected), a prose fallback that is not
rendered as code, a symlinked CLAUDE.md that keeps its link, file modes
that survive the write, a docsHome that would break the managed block,
whitespace around the end marker, and refusals — not tracebacks — for a
wrong-typed path or a CLAUDE.md that is not text.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional, Tuple

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent / "skills" / "promise" / "scripts"
ADOPT = SCRIPTS_DIR / "adopt.py"
ORIENT = SCRIPTS_DIR / "orient.py"

BEGIN_PREFIX = "<!-- promise:begin"
END_MARKER = "<!-- promise:end -->"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ADOPT), *args], capture_output=True, text=True)


def run_json(*args: str) -> Tuple[subprocess.CompletedProcess, Optional[dict]]:
    result = run(*args)
    data = json.loads(result.stdout) if result.stdout.strip() else None
    return result, data


class ConfigShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)
        self.config_path = self.cwd / ".claude" / "promise.config.json"

    def _config(self) -> dict:
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def test_fresh_config_carries_version_1_and_no_schema_key(self) -> None:
        result = run("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        config = self._config()
        self.assertEqual(config["version"], 1)
        self.assertNotIn("$schema", config)
        # version is the first key, where a reader looks for it
        self.assertEqual(list(config.keys())[0], "version")

    def test_no_detected_commands_still_writes_all_three_keys_as_null(self) -> None:
        # A new project with no code sees where its test command goes; orient
        # warns once a null key has a detected command, so nothing is pinned off silently.
        run("--cwd", str(self.cwd))
        self.assertEqual(self._config()["commands"], {"typeCheck": None, "test": None, "lint": None})
        (self.cwd / "package.json").write_text(
            json.dumps({"name": "x", "scripts": {"test": "vitest run"}}), encoding="utf-8")
        orient = subprocess.run([sys.executable, str(ORIENT), "--cwd", str(self.cwd)], capture_output=True, text=True)
        warnings = json.loads(orient.stdout)["warnings"]
        self.assertIn("commands.test is null in the config but 'npm run test' is detected; "
                      "set it there to use it", warnings)

    def test_the_section_carries_the_template_stamp_and_orient_checks_it(self) -> None:
        run("--cwd", str(self.cwd))
        claude_md = self.cwd / "CLAUDE.md"
        begin = claude_md.read_text(encoding="utf-8").splitlines()[0]
        self.assertRegex(begin, r"^<!-- promise:begin .* template:[0-9a-f]{8} -->$")

        def orient():
            out = subprocess.run([sys.executable, str(ORIENT), "--cwd", str(self.cwd)], capture_output=True, text=True)
            return json.loads(out.stdout)

        data = orient()
        self.assertIs(data["claudeMd"]["sectionCurrent"], True)
        self.assertFalse(any("older template" in w for w in data["warnings"]))
        claude_md.write_text(claude_md.read_text(encoding="utf-8").replace(begin, "<!-- promise:begin (old) -->"),
                             encoding="utf-8")
        data = orient()
        self.assertIs(data["claudeMd"]["sectionCurrent"], False)
        self.assertTrue(any("older template; run /promise adopt" in w for w in data["warnings"]), data["warnings"])
        run("--cwd", str(self.cwd))  # a refresh restores the stamp
        self.assertIs(orient()["claudeMd"]["sectionCurrent"], True)

    def test_run_is_written_named_in_the_section_and_reported(self) -> None:
        run("--cwd", str(self.cwd), "--run", "scripts/promise/run.sh")
        config = self._config()
        self.assertEqual(config["run"], "scripts/promise/run.sh")
        self.assertEqual(list(config).index("run"), list(config).index("map") - 1)
        section = (self.cwd / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("scripts run as `scripts/promise/run.sh <script>.py …`", section)
        out = subprocess.run([sys.executable, str(ORIENT), "--cwd", str(self.cwd)], capture_output=True, text=True)
        self.assertEqual(json.loads(out.stdout)["run"], "scripts/promise/run.sh")
        config["run"] = 7
        self.config_path.write_text(json.dumps(config), encoding="utf-8")
        data = json.loads(subprocess.run([sys.executable, str(ORIENT), "--cwd", str(self.cwd)],
                                         capture_output=True, text=True).stdout)
        self.assertIsNone(data["run"])
        self.assertIn("run is not a command string; agents run the scripts by their path instead", data["warnings"])

    def test_run_on_an_existing_config_says_what_to_set_and_keeps_the_config(self) -> None:
        run("--cwd", str(self.cwd))
        before = self.config_path.read_bytes()
        result = run("--cwd", str(self.cwd), "--run", "tools/promise-run.sh")
        self.assertIn('--run is not recorded: the config exists and adopt never edits it; set "run": '
                      '"tools/promise-run.sh"', result.stderr)
        self.assertEqual(self.config_path.read_bytes(), before)
        self.assertNotIn("tools/promise-run.sh", (self.cwd / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_run_with_no_config_says_it_is_not_recorded(self) -> None:
        result = run("--cwd", str(self.cwd), "--no-config", "--run", "tools/promise-run.sh")
        self.assertIn("--run is not recorded: no config is written this run", result.stderr)
        self.assertFalse(self.config_path.exists())
        self.assertNotIn("tools/promise-run.sh", (self.cwd / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_without_run_the_section_names_the_skill_path(self) -> None:
        run("--cwd", str(self.cwd))
        self.assertNotIn("run", self._config())
        self.assertIn("`python3 <the skill's folder>/scripts/<script>.py …`",
                      (self.cwd / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_detected_commands_are_written_with_all_three_keys(self) -> None:
        # A package.json with only a test script: the config must show
        # typeCheck and lint pinned to null, because once a commands
        # object exists detection is off for all three.
        (self.cwd / "package.json").write_text(
            json.dumps({"name": "x", "scripts": {"test": "vitest run"}}), encoding="utf-8"
        )
        result = run("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        commands = self._config()["commands"]
        self.assertEqual(set(commands.keys()), {"typeCheck", "test", "lint"})
        self.assertEqual(commands["test"], "npm run test")
        self.assertIsNone(commands["typeCheck"])
        self.assertIsNone(commands["lint"])

    def test_docs_home_flag_is_recorded(self) -> None:
        run("--cwd", str(self.cwd), "--docs-home", "docs/rfcs")
        self.assertEqual(self._config()["docsHome"], "docs/rfcs")

    def test_docs_home_flag_is_reported_in_json(self) -> None:
        result, data = run_json("--cwd", str(self.cwd), "--docs-home", "docs/rfcs")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(data["docsHome"], "docs/rfcs")

    def test_no_docs_home_says_so_on_stderr(self) -> None:
        # An empty project: nothing detected, no flag. The config is still
        # written (exit 0) but pins no docsHome, and stderr says what that
        # costs and how to fix it — the JSON shows the null too.
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("docsHome", self._config())
        self.assertIsNone(data["docsHome"])
        self.assertIn("--docs-home", result.stderr)
        self.assertIn("every later `new` will ask", result.stderr)

    def test_a_detected_docs_home_does_not_warn(self) -> None:
        (self.cwd / "docs" / "designs").mkdir(parents=True)
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(data["docsHome"], "docs/designs")
        self.assertNotIn("--docs-home", result.stderr)

    def test_backslash_docs_home_is_recorded_with_forward_slashes(self) -> None:
        # The config contract asks for forward slashes; a value written the
        # Windows way is recorded in that form so orient never warns about
        # a file this script wrote.
        result, data = run_json("--cwd", str(self.cwd), "--docs-home", "docs\\designs", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"docsHome": "docs/designs"', result.stderr)
        self.assertIn("lives in `docs/designs`", result.stderr)
        self.assertNotIn("\\", result.stderr.split("---", 1)[-1])
        self.assertEqual(data["docsHome"], "docs/designs")
        self.assertIn("backslashes", result.stderr)


class DocsHomeDriftTests(unittest.TestCase):
    """On an already-adopted project, a --docs-home that disagrees with the
    loaded config is refused before any write: CLAUDE.md and the config
    must never name different folders."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)

    def test_disagreeing_docs_home_is_refused_and_claude_md_is_untouched(self) -> None:
        first = run("--cwd", str(self.cwd), "--docs-home", "docs/designs")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        before = (self.cwd / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn("docs/designs", before)

        result, data = run_json("--cwd", str(self.cwd), "--docs-home", "docs/rfcs")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("disagrees", result.stderr)
        self.assertIn("docs/designs", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(data["changed"])
        self.assertEqual((self.cwd / "CLAUDE.md").read_text(encoding="utf-8"), before)

    def test_agreeing_docs_home_is_a_no_op(self) -> None:
        run("--cwd", str(self.cwd), "--docs-home", "docs/designs")
        result, data = run_json("--cwd", str(self.cwd), "--docs-home", "docs/designs")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(data["changed"])


class ForeignDocsHomeTests(unittest.TestCase):
    """A detected docs folder that holds Markdown but no outcome doc is not
    pinned by default: a run that would name it in a fresh config or in the
    CLAUDE.md or AGENTS.md block refuses, dry or not, until --docs-home picks
    the folder outcome docs will live in."""

    WARNING = ("docsHome docs/design was detected, but none of its 2 docs is an outcome doc; "
               "pin a new folder with adopt --docs-home (for example docs/promises)")

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)
        design = self.cwd / "docs" / "design"
        design.mkdir(parents=True)
        for name in ("a.md", "b.md"):
            (design / name).write_text(f"# {name}\n", encoding="utf-8")

    def written(self) -> list:
        return sorted(str(p.relative_to(self.cwd)) for p in self.cwd.rglob("*") if p.is_file())

    def test_a_dry_run_refuses_as_the_real_run_does(self) -> None:
        # a preview the real run would refuse is not a change the user can approve
        result, data = run_json("--cwd", str(self.cwd), "--dry-run")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(self.WARNING, result.stderr)
        self.assertIn("pass --docs-home <dir>", result.stderr)
        self.assertNotIn("+++", result.stderr, "no diff is printed")
        self.assertFalse(data["changed"])
        self.assertEqual(self.written(), ["docs/design/a.md", "docs/design/b.md"])

    def test_no_config_still_refuses_a_claude_md_that_names_the_folder(self) -> None:
        for flags in (("--no-config",), ("--no-config", "--dry-run")):
            with self.subTest(flags=flags):
                result, data = run_json("--cwd", str(self.cwd), *flags)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("pass --docs-home <dir>", result.stderr)
                self.assertFalse(data["changed"])
                self.assertEqual(self.written(), ["docs/design/a.md", "docs/design/b.md"])

    def test_an_agents_md_block_that_names_the_folder_refuses_too(self) -> None:
        # AGENTS.md carries the same block, and sends Codex, Cursor and the rest there
        for flags in (("--no-config", "--no-claude-md", "--agents-md"),
                      ("--no-config", "--no-claude-md", "--agents-md", "--dry-run")):
            with self.subTest(flags=flags):
                result, data = run_json("--cwd", str(self.cwd), *flags)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("pass --docs-home <dir>", result.stderr)
                self.assertFalse(data["changed"])
                self.assertEqual(self.written(), ["docs/design/a.md", "docs/design/b.md"])

    def test_a_run_that_names_no_folder_only_warns(self) -> None:
        result, data = run_json("--cwd", str(self.cwd), "--no-config", "--no-claude-md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"adopt.py: {self.WARNING}", result.stderr)
        self.assertEqual(self.written(), ["docs/design/a.md", "docs/design/b.md"])

    def test_the_project_s_own_framework_copy_is_not_a_foreign_doc(self) -> None:
        (self.cwd / "docs" / "design" / "a.md").unlink()
        (self.cwd / "docs" / "design" / "b.md").rename(self.cwd / "docs" / "design" / "framework.md")
        config = self.cwd / ".claude" / "promise.config.json"
        config.parent.mkdir()
        config.write_text('{"version": 1, "frameworkPath": "docs/design/framework.md"}\n', encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(data["docsHome"], "docs/design")

    def test_a_loaded_config_with_no_docs_home_is_told_to_set_one(self) -> None:
        config = self.cwd / ".claude" / "promise.config.json"
        config.parent.mkdir()
        config.write_text('{"version": 1}\n', encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("set docsHome in", result.stderr)
        self.assertFalse((self.cwd / "CLAUDE.md").exists())

    def test_a_real_run_refuses_and_writes_nothing(self) -> None:
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(self.WARNING, result.stderr)
        self.assertIn("pass --docs-home <dir>", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertFalse(data["changed"])
        self.assertEqual(self.written(), ["docs/design/a.md", "docs/design/b.md"])

    def test_docs_home_pins_the_chosen_folder(self) -> None:
        result, data = run_json("--cwd", str(self.cwd), "--docs-home", "docs/promises")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("was detected, but", result.stderr)
        self.assertEqual(data["docsHome"], "docs/promises")
        config = json.loads((self.cwd / ".claude" / "promise.config.json").read_text(encoding="utf-8"))
        self.assertEqual(config["docsHome"], "docs/promises")

    def test_an_outcome_doc_in_the_folder_makes_it_a_docs_home(self) -> None:
        (self.cwd / "docs" / "design" / "mute.md").write_text(
            "# Mute\n\nStatus: draft\n\n## 0. TLDR\n**Outcome:** x.\n", encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(data["docsHome"], "docs/design")


class ProseFallbackRenderingTests(unittest.TestCase):
    """The backticks belong to the value: a real path is code, a prose
    fallback is prose. Checked on the dry-run diff, which carries the
    rendered block verbatim."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)

    def _rendered(self, *args: str) -> str:
        run("--cwd", str(self.cwd), *args)
        return (self.cwd / "CLAUDE.md").read_text(encoding="utf-8")

    def test_unknown_docs_home_is_prose_not_code(self) -> None:
        text = self._rendered()
        self.assertIn("lives in the project's docs home,", text)
        self.assertNotIn("`the project's docs home`", text)

    def test_bundled_framework_is_prose_not_code(self) -> None:
        text = self._rendered()
        self.assertIn("(the copy bundled with the promise skill)", text)
        self.assertNotIn("`the copy bundled with the promise skill`", text)

    def test_a_real_docs_home_is_code(self) -> None:
        text = self._rendered("--docs-home", "docs/rfcs")
        self.assertIn("lives in `docs/rfcs`,", text)
        self.assertNotIn("``docs/rfcs``", text)

    def test_config_path_is_code_exactly_once(self) -> None:
        text = self._rendered()
        self.assertIn("`.claude/promise.config.json`", text)
        self.assertNotIn("``.claude/promise.config.json``", text)

    def test_a_project_framework_copy_is_code(self) -> None:
        (self.cwd / "docs").mkdir()
        (self.cwd / "docs" / "outcome-framework.md").write_text("# framework\n", encoding="utf-8")
        claude_dir = self.cwd / ".claude"
        claude_dir.mkdir()
        (claude_dir / "promise.config.json").write_text(
            json.dumps({"version": 1, "frameworkPath": "docs/outcome-framework.md", "map": None}),
            encoding="utf-8",
        )
        text = self._rendered()
        self.assertIn("(`docs/outcome-framework.md`)", text)


@unittest.skipIf(os.name == "nt", "symlinks and POSIX modes")
class SymlinkAndModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)

    def test_symlinked_claude_md_keeps_its_link_and_the_target_gets_the_section(self) -> None:
        agents = self.cwd / "AGENTS.md"
        agents.write_text("# Agents\n\nShared notes.\n", encoding="utf-8")
        link = self.cwd / "CLAUDE.md"
        os.symlink("AGENTS.md", str(link))

        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(data["claudeMdWritten"])
        self.assertTrue(os.path.islink(link), "the link must survive the write")
        self.assertEqual(os.readlink(link), "AGENTS.md")
        target_text = agents.read_text(encoding="utf-8")
        self.assertIn("Shared notes.", target_text)
        self.assertIn(BEGIN_PREFIX, target_text)
        self.assertIn(END_MARKER, target_text)

        second, data2 = run_json("--cwd", str(self.cwd))
        self.assertEqual(second.returncode, 0)
        self.assertFalse(data2["changed"], "a rerun through the link is still a no-op")

    def test_existing_claude_md_keeps_its_mode(self) -> None:
        claude_md = self.cwd / "CLAUDE.md"
        claude_md.write_text("# Notes\n", encoding="utf-8")
        os.chmod(claude_md, 0o664)
        result = run("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(stat.S_IMODE(os.stat(claude_md).st_mode), 0o664)

    def test_new_files_are_not_owner_only(self) -> None:
        # mkstemp creates 0600; the written files must end up with what
        # open(2) would have given them under the umask instead.
        old_umask = os.umask(0o022)
        self.addCleanup(os.umask, old_umask)
        result = run("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for path in (self.cwd / "CLAUDE.md", self.cwd / ".claude" / "promise.config.json"):
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o644, path)


class DocsHomeValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)

    def _assert_refused(self, value: str, fragment: str) -> None:
        result, data = run_json("--cwd", str(self.cwd), "--docs-home", value)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(fragment, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIsNotNone(data, "stdout is always JSON")
        self.assertFalse(data["changed"])
        self.assertEqual(list(self.cwd.iterdir()), [], "nothing is written on a refusal")

    def test_newline_in_docs_home_is_refused(self) -> None:
        self._assert_refused("docs/designs\n<!-- promise:end -->", "single line")

    def test_marker_text_in_docs_home_is_refused(self) -> None:
        self._assert_refused("docs <!-- promise:end -->", "marker")

    def test_shell_syntax_in_docs_home_is_refused(self) -> None:
        # the folder reaches hand-typed shell lines through the CLAUDE.md block
        for value in ("docs/$(id)", "docs/`id`", "docs;id", "docs|id"):
            with self.subTest(value=value):
                self._assert_refused(value, "letters, digits, spaces and . _ - /")
        result, data = run_json("--cwd", str(self.cwd), "--docs-home=-docs")
        self.assertEqual((result.returncode, data["changed"]), (2, False), result.stderr)
        self.assertIn("must not start with '-'", result.stderr)

    def test_absolute_docs_home_is_refused(self) -> None:
        self._assert_refused(str(self.cwd / "docs"), "relative")

    def test_windows_drive_letter_docs_home_is_refused_on_every_os(self) -> None:
        # orient's rule, shared: a drive letter is absolute whatever OS the
        # script runs on.
        self._assert_refused("C:\\Users\\x\\docs", "relative")
        self._assert_refused("D:docs", "relative")

    def test_escaping_docs_home_is_refused(self) -> None:
        self._assert_refused("../elsewhere", "escape")

    def test_idempotency_holds_because_a_marker_never_reaches_the_file(self) -> None:
        # The failure this guards: a docsHome carrying an end marker used
        # to render into CLAUDE.md and make the next run refuse on
        # duplicated markers. Now the first run refuses and the second
        # (with a sane value) adopts and reruns clean.
        run("--cwd", str(self.cwd), "--docs-home", "docs\n<!-- promise:end -->")
        first = run("--cwd", str(self.cwd), "--docs-home", "docs/designs")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertFalse(data["changed"])


class EndMarkerWhitespaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)
        self.claude_md = self.cwd / "CLAUDE.md"

    def test_trailing_whitespace_after_the_end_marker_is_tolerated(self) -> None:
        run("--cwd", str(self.cwd))
        original = self.claude_md.read_text(encoding="utf-8")
        self.assertTrue(original.rstrip("\n").endswith(END_MARKER))
        with_trailing = original.rstrip("\n") + "   \n\n## Trailer\n\nKeep this.\n"
        self.claude_md.write_text(with_trailing, encoding="utf-8")

        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("end at line none", result.stderr)
        after = self.claude_md.read_text(encoding="utf-8")
        self.assertIn("Keep this.", after)
        self.assertEqual(after.count(END_MARKER), 1)

    def test_indented_end_marker_is_tolerated(self) -> None:
        run("--cwd", str(self.cwd))
        original = self.claude_md.read_text(encoding="utf-8")
        indented = original.replace(END_MARKER, "  " + END_MARKER)
        self.assertNotEqual(indented, original)
        self.claude_md.write_text(indented, encoding="utf-8")
        result = run("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_restoring_a_hand_edited_block_says_so_on_stderr(self) -> None:
        run("--cwd", str(self.cwd))
        original = self.claude_md.read_text(encoding="utf-8")
        self.claude_md.write_text(original.replace("plain words", "VANDALISED"), encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(data["claudeMdWritten"])
        self.assertIn("differed from the rendered form", result.stderr)

    def test_a_clean_rerun_does_not_claim_a_restore(self) -> None:
        run("--cwd", str(self.cwd))
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0)
        self.assertFalse(data["changed"])
        self.assertNotIn("differed from the rendered form", result.stderr)


class WrongTypedPathTests(unittest.TestCase):
    """A path this script would write that is a directory, or sits under
    a file, is refused with one line and the JSON result — never an
    IsADirectoryError or NotADirectoryError traceback, on a dry run or a
    real one."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)

    def _assert_refused(self, *args: str) -> None:
        for flags in ((), ("--dry-run",)):
            result, data = run_json("--cwd", str(self.cwd), *args, *flags)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("adopt.py:", result.stderr)
            self.assertIsNotNone(data)
            self.assertFalse(data["changed"])
            self.assertFalse(data["configWritten"])
            self.assertFalse(data["claudeMdWritten"])

    def test_claude_md_that_is_a_directory_is_refused(self) -> None:
        (self.cwd / "CLAUDE.md").mkdir()
        self._assert_refused()
        self.assertFalse((self.cwd / ".claude").exists(), "the config is not written either")

    def test_dot_claude_that_is_a_file_is_refused(self) -> None:
        (self.cwd / ".claude").write_text("not a directory\n", encoding="utf-8")
        self._assert_refused()
        self.assertFalse((self.cwd / "CLAUDE.md").exists())

    def test_config_path_that_is_a_directory_is_refused(self) -> None:
        (self.cwd / ".claude" / "promise.config.json").mkdir(parents=True)
        self._assert_refused()

    def test_non_utf8_claude_md_is_refused_with_json_on_stdout(self) -> None:
        (self.cwd / "CLAUDE.md").write_bytes(b"\xff\xfe\x00# notes\x00")
        self._assert_refused()
        self.assertEqual((self.cwd / "CLAUDE.md").read_bytes(), b"\xff\xfe\x00# notes\x00")


class ForeignTextInsideMarkersTests(unittest.TestCase):
    """adopt only removes text adopt wrote: a section inside the markers
    that the template never wrote is moved, unchanged, above the block."""

    FOREIGN = "## Questions to the human go through `/q`\n\n- Ask one question at a time.\n- Wait for the answer.\n"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name)
        self.claude_md = self.cwd / "CLAUDE.md"
        result = run("--cwd", str(self.cwd), "--docs-home", "docs/designs")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.block = self.claude_md.read_text(encoding="utf-8")
        self.begin, _, self.rest = self.block.partition("\n")

    def _two_sections(self, foreign: str = FOREIGN) -> str:
        # A project's own section, then the promise section, both inside the markers.
        return "# Notes\n\nKeep me.\n\n" + self.begin + "\n" + foreign + "\n" + self.rest

    def test_the_foreign_section_is_kept_above_the_block(self) -> None:
        self.claude_md.write_text(self._two_sections(), encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(data["claudeMdWritten"])
        self.assertEqual(self.claude_md.read_text(encoding="utf-8"),
                         "# Notes\n\nKeep me.\n\n" + self.FOREIGN + "\n" + self.block)
        self.assertEqual(data["movedAboveBlock"], [{
            "path": str(self.claude_md), "lines": [6, 9],
            "heading": "## Questions to the human go through `/q`"}])
        self.assertIn("did not write", result.stderr)
        self.assertIn("(lines 6-9)", result.stderr)
        self.assertNotIn("restored", result.stderr)

    def test_a_section_after_the_promise_section_is_kept_too(self) -> None:
        text = self.block.replace(END_MARKER, "\n" + self.FOREIGN + END_MARKER)
        self.claude_md.write_text(text, encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.claude_md.read_text(encoding="utf-8"), self.FOREIGN + "\n" + self.block)
        self.assertEqual(len(data["movedAboveBlock"]), 1)
        self.assertNotIn("restored", result.stderr)

    def test_the_dry_run_shows_the_move_and_writes_nothing(self) -> None:
        before = self._two_sections()
        self.claude_md.write_text(before, encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd), "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.claude_md.read_text(encoding="utf-8"), before)
        self.assertTrue(data["changed"])
        self.assertEqual(data["movedAboveBlock"][0]["lines"], [6, 9])
        self.assertIn("would move it, unchanged", result.stderr)
        self.assertIn("-" + self.begin + "\n", result.stderr)
        self.assertIn("+" + self.begin + "\n", result.stderr)
        self.assertNotIn("-- Ask one question at a time.", result.stderr)

    def test_a_second_run_changes_nothing(self) -> None:
        self.claude_md.write_text(self._two_sections(), encoding="utf-8")
        run("--cwd", str(self.cwd))
        after_first = self.claude_md.read_bytes()
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(data["changed"])
        self.assertNotIn("movedAboveBlock", data)
        self.assertEqual(self.claude_md.read_bytes(), after_first)

    def test_a_hand_edit_of_the_promise_section_is_still_restored(self) -> None:
        self.claude_md.write_text(self._two_sections().replace("plain words", "EDITED"), encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.claude_md.read_text(encoding="utf-8")
        self.assertNotIn("EDITED", text)
        self.assertIn(self.FOREIGN, text)
        self.assertIn("restored", result.stderr)

    def test_a_heading_under_the_promise_heading_is_refused_with_its_lines(self) -> None:
        text = self.block.replace(END_MARKER, "### Our own rule\n- Keep it short.\n" + END_MARKER)
        self.claude_md.write_text(text, encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(data["changed"])
        self.assertEqual(self.claude_md.read_text(encoding="utf-8"), text)
        line = text.splitlines().index("### Our own rule") + 1
        self.assertIn(f"lines {line}-{line + 1}", result.stderr)
        self.assertIn("did not write", result.stderr)

    def test_text_above_a_foreign_heading_is_refused(self) -> None:
        text = self.begin + "\nA loose line.\n" + self.FOREIGN + self.rest
        self.claude_md.write_text(text, encoding="utf-8")
        result, _ = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("lines 2-2", result.stderr)
        self.assertEqual(self.claude_md.read_text(encoding="utf-8"), text)

    def test_an_earlier_template_heading_is_promise_s_own(self) -> None:
        old = self.block.replace("## Capability work goes through the `promise` skill",
                                 "## Capability work goes through `/promise`")
        self.claude_md.write_text(old, encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("movedAboveBlock", data)
        self.assertEqual(self.claude_md.read_text(encoding="utf-8"), self.block)

    def test_a_heading_inside_a_code_fence_is_not_a_section(self) -> None:
        text = self.block.replace(END_MARKER, "```\n## not a heading\n```\n" + END_MARKER)
        self.claude_md.write_text(text, encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("movedAboveBlock", data)
        self.assertEqual(self.claude_md.read_text(encoding="utf-8"), self.block)

    def test_a_setext_heading_is_a_section_of_its_own(self) -> None:
        setext = "Our rules\n---------\n- Keep it short.\n"
        text = self.block.replace(END_MARKER, "\n" + setext + END_MARKER)
        self.claude_md.write_text(text, encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.claude_md.read_text(encoding="utf-8"), setext + "\n" + self.block)
        self.assertEqual(data["movedAboveBlock"][0]["heading"], "Our rules")
        self.assertNotIn("restored", result.stderr)

    def test_a_line_in_no_section_is_refused_not_deleted(self) -> None:
        for text in (self.begin + "\nOur own line.\n" + self.rest,          # above the heading
                     self.begin + "\nOur own line.\n" + END_MARKER + "\n"):  # a block with no heading
            with self.subTest(text=text[:80]):
                self.claude_md.write_text(text, encoding="utf-8")
                result, data = run_json("--cwd", str(self.cwd))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(data["changed"])
                self.assertIn("lines 2-2", result.stderr)
                self.assertEqual(self.claude_md.read_text(encoding="utf-8"), text)

    def test_a_longer_fence_is_not_closed_by_a_shorter_one(self) -> None:
        fenced = "````\n```\n## inside the fence\n```\n````\n"
        text = self.block.replace(END_MARKER, fenced + END_MARKER)
        self.claude_md.write_text(text, encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("movedAboveBlock", data)
        self.assertEqual(self.claude_md.read_text(encoding="utf-8"), self.block)

    def test_a_crlf_file_keeps_crlf_around_the_moved_section(self) -> None:
        text = self._two_sections().replace("\n", "\r\n")
        self.claude_md.write_bytes(text.encode("utf-8"))
        result, data = run_json("--cwd", str(self.cwd))
        self.assertEqual(result.returncode, 0, result.stderr)
        after = self.claude_md.read_bytes()
        self.assertEqual(after.count(b"\n"), after.count(b"\r\n"))
        self.assertEqual(after.decode("utf-8"),
                         ("# Notes\n\nKeep me.\n\n" + self.FOREIGN + "\n" + self.block).replace("\n", "\r\n"))

    def test_a_crlf_text_handed_in_directly_gets_no_bare_lf(self) -> None:
        sys.path.insert(0, str(SCRIPTS_DIR))
        try:
            import adopt
        finally:
            sys.path.remove(str(SCRIPTS_DIR))
        text = self._two_sections().replace("\n", "\r\n")
        new_text, moved, _ = adopt.apply_block(text, self.block)
        self.assertEqual(len(moved), 1)
        self.assertEqual(new_text.count("\n"), new_text.count("\r\n"))
        self.assertTrue(new_text.startswith("# Notes\r\n\r\nKeep me.\r\n\r\n## Questions"))

    def test_a_foreign_section_in_agents_md_is_kept_above_its_block(self) -> None:
        agents = self.cwd / "AGENTS.md"
        run("--cwd", str(self.cwd), "--agents-md")
        agents_block = agents.read_text(encoding="utf-8")
        begin, _, rest = agents_block.partition("\n")
        agents.write_text(begin + "\n" + self.FOREIGN + "\n" + rest, encoding="utf-8")
        result, data = run_json("--cwd", str(self.cwd), "--agents-md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(agents.read_text(encoding="utf-8"), self.FOREIGN + "\n" + agents_block)
        self.assertEqual([m["path"] for m in data["movedAboveBlock"]], [str(agents)])
        self.assertIn("AGENTS.md: the promise block held text adopt did not write", result.stderr)


if __name__ == "__main__":
    unittest.main()
