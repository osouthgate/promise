"""GitHub text reaches GitHub only through the lint (#62).

- `hooks/guard_github_text.py` blocks a body whose promise block fails the lint, and
  asks before a new issue or pull request with no block, in an adopted project.
- `scripts/post_github_text.py` lints, posts with `gh`, and reads the stored body back:
  a known footer is ignored; links wrapped in backticks are a finding.
- `adopt.py --github-templates` copies the templates a project lacks; orient reports them.
- `lint_github_text.py` reads a sibling's map beside `"map": false`, and counts an
  `Also:` area the map holds as explained.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SKILL = REPO / "skills" / "promise"
SCRIPTS = SKILL / "scripts"
HOOK = REPO / "hooks" / "guard_github_text.py"
POST = SCRIPTS / "post_github_text.py"
LINT = SCRIPTS / "lint_github_text.py"
FIX = HERE / "fixtures" / "github"
GOOD_PR = (FIX / "pr_good.md").read_text(encoding="utf-8")
BAD_PR = GOOD_PR.replace("## Why", "## Reasons")  # a required section is missing
MAP = {"recipe": "recipe.md", "find": "python3 find.py", "row": "python3 find.py --row", "lanes": {},
       "file": "map.json"}


def project(root: Path, adopted: bool = True, map_value=None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / ".claude").mkdir(exist_ok=True)
    (root / ".claude" / "promise.config.json").write_text(json.dumps(
        {"version": 1, "map": MAP if map_value is None else map_value}), encoding="utf-8")
    shutil.copy(FIX / "map.json", root / "map.json")
    if adopted:
        (root / "CLAUDE.md").write_text("<!-- promise:begin -->\nx\n<!-- promise:end -->\n", encoding="utf-8")
    return root


def hook(event: dict) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True, text=True)


class Hook(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = project(self.tmp / "p")

    def mcp(self, tool: str, **tool_input) -> subprocess.CompletedProcess:
        return hook({"tool_name": tool, "tool_input": tool_input, "cwd": str(self.root)})

    def test_a_body_that_passes_the_lint_passes(self) -> None:
        done = self.mcp("mcp__github__update_pull_request", body=GOOD_PR, pullNumber=3)
        self.assertEqual((done.returncode, done.stdout), (0, ""), done.stderr)

    def test_a_block_that_fails_the_lint_is_blocked(self) -> None:
        for tool in ("mcp__github__create_pull_request", "mcp__plugin_github_github__update_pull_request"):
            with self.subTest(tool=tool):
                done = self.mcp(tool, body=BAD_PR)
                self.assertEqual(done.returncode, 2)
                self.assertIn("MISSING_SECTION", done.stderr)
                self.assertIn("post_github_text.py", done.stderr)

    def test_a_new_body_with_no_block_asks_and_an_update_passes(self) -> None:
        done = self.mcp("mcp__github__issue_write", method="create", body="just words")
        self.assertEqual(done.returncode, 0)
        decision = json.loads(done.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "ask")
        self.assertIn("<!-- promise:issue -->", decision["permissionDecisionReason"])
        self.assertEqual(self.mcp("mcp__github__issue_write", method="update", body="just words").stdout, "")

    def test_gh_with_a_body_file_is_linted(self) -> None:
        (self.root / "body.md").write_text(BAD_PR, encoding="utf-8")
        done = hook({"tool_name": "Bash", "cwd": str(self.root),
                     "tool_input": {"command": "gh pr edit 4 --body-file body.md"}})
        self.assertEqual(done.returncode, 2)
        done = hook({"tool_name": "Bash", "cwd": str(self.root),
                     "tool_input": {"command": "gh pr create --title t --body 'no block here'"}})
        self.assertEqual(json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_a_body_the_shell_builds_is_not_guessed_at(self) -> None:
        command = f"gh pr create --title x --body \"$(cat <<'EOF'\n{GOOD_PR}\nEOF\n)\""
        done = hook({"tool_name": "Bash", "cwd": str(self.root), "tool_input": {"command": command}})
        self.assertEqual((done.returncode, done.stdout), (0, ""), done.stderr)

    def test_only_the_gh_commands_own_flags_count(self) -> None:
        for command in ('gh pr create --title x --fill && gh pr comment 5 --body "thanks"',
                        'gh pr edit 3 --add-label y && gh pr comment 3 --body "<!-- promise:pr --> quote"'):
            with self.subTest(command=command):
                done = hook({"tool_name": "Bash", "cwd": str(self.root), "tool_input": {"command": command}})
                self.assertEqual(done.returncode, 0)
                if "create" in command:  # a new pull request gh fills itself: no block, so it asks
                    self.assertEqual(json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")
                else:
                    self.assertEqual(done.stdout, "")

    def test_a_new_one_with_no_body_asks(self) -> None:
        done = self.mcp("mcp__github__create_pull_request", title="t", head="b", base="main")
        self.assertEqual(json.loads(done.stdout)["hookSpecificOutput"]["permissionDecision"], "ask")

    def test_everything_else_passes(self) -> None:
        plain = project(self.tmp / "plain", adopted=False)
        cases = [
            {"tool_name": "mcp__github__create_pull_request", "tool_input": {"body": BAD_PR}, "cwd": str(plain)},
            {"tool_name": "Bash", "tool_input": {"command": "ls -la"}, "cwd": str(self.root)},
            {"tool_name": "mcp__github__add_issue_comment", "tool_input": {"body": BAD_PR}, "cwd": str(self.root)},
            {"tool_name": "mcp__github__update_pull_request", "tool_input": {"title": "t"}, "cwd": str(self.root)},
            {"not": "an event"},
        ]
        for event in cases:
            with self.subTest(event=event.get("tool_name")):
                done = hook(event)
                self.assertEqual((done.returncode, done.stdout), (0, ""))

    def test_hooks_json_runs_it_on_github_writes_and_bash(self) -> None:
        entries = json.loads((REPO / "hooks" / "hooks.json").read_text())["hooks"]["PreToolUse"]
        entry = next(e for e in entries if "guard_github_text.py" in e["hooks"][0]["command"])
        self.assertIn("Bash", entry["matcher"])
        self.assertIn("update_pull_request", entry["matcher"])


FAKE_GH = textwrap.dedent('''\
    #!/usr/bin/env python3
    import json, os, sys
    log = os.environ["FAKE_GH_LOG"]
    with open(log, "a") as fh:
        fh.write(" ".join(sys.argv[1:]) + "\\n")
    args = sys.argv[1:]
    if args[1] in ("edit", "create"):
        body = open(args[args.index("--body-file") + 1]).read()
        with open(os.environ["FAKE_GH_STORE"], "w") as fh:
            fh.write(os.environ.get("FAKE_GH_MANGLE", "") and body.replace("[C-2](", "`[C-2](").replace("#L20)", "#L20)`") or body)
        if args[1] == "create":
            print("https://github.com/o/r/pull/41")
    elif args[1] == "view":
        stored = open(os.environ["FAKE_GH_STORE"]).read()
        print(json.dumps({"body": stored + "\\n\\n---\\n_Generated by [Claude Code](https://claude.ai/code)_"}))
    ''')


class Post(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = project(self.tmp / "p")
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "gh"
        fake.write_text(FAKE_GH.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1))
        fake.chmod(0o755)
        self.log, self.store = self.tmp / "gh.log", self.tmp / "stored.md"
        self.env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ['PATH']}", FAKE_GH_LOG=str(self.log),
                        FAKE_GH_STORE=str(self.store))

    def post(self, body: str, *args: str, env: dict = None) -> subprocess.CompletedProcess:
        path = self.tmp / "body.md"
        path.write_text(body, encoding="utf-8")
        return subprocess.run([sys.executable, str(POST), "--kind", "pr", "--body-file", str(path),
                               "--cwd", str(self.root), "--changed", str(FIX / "changed.json"), *args],
                              capture_output=True, text=True, env=env or self.env)

    def calls(self) -> list:
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_a_body_that_fails_the_lint_is_not_posted(self) -> None:
        done = self.post(BAD_PR, "--number", "12")
        self.assertEqual(done.returncode, 1)
        self.assertIn("nothing was posted", done.stderr)
        self.assertEqual(self.calls(), [])

    def test_a_good_body_is_posted_and_read_back_past_the_known_footer(self) -> None:
        done = self.post(GOOD_PR, "--number", "12")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual([c.split()[:3] for c in self.calls()], [["pr", "edit", "12"], ["pr", "view", "12"]])
        self.assertIn("stored the body as sent", done.stdout)

    def test_links_wrapped_in_backticks_are_named(self) -> None:
        done = self.post(GOOD_PR, "--new", "--title", "Empty exports", env=dict(self.env, FAKE_GH_MANGLE="1"))
        self.assertEqual(done.returncode, 1)
        self.assertIn("pr 41: GitHub stored a different body", done.stdout)
        self.assertIn("wrapped in backticks", done.stdout)

    def test_verify_posts_nothing(self) -> None:
        self.store.write_text(GOOD_PR, encoding="utf-8")
        done = self.post(GOOD_PR, "--verify", "12")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual([c.split()[:2] for c in self.calls()], [["pr", "view"]])

    def test_a_relative_body_file_is_the_callers_not_the_projects(self) -> None:
        (self.tmp / "body.md").write_text(GOOD_PR, encoding="utf-8")
        (self.root / "body.md").write_text("another file\n", encoding="utf-8")
        done = subprocess.run([sys.executable, str(POST), "--kind", "pr", "--body-file", "body.md", "--cwd",
                               str(self.root), "--changed", str(FIX / "changed.json"), "--number", "12"],
                              capture_output=True, text=True, env=self.env, cwd=self.tmp)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.store.read_text(), GOOD_PR)

    def test_the_known_footer_in_its_forms(self) -> None:
        sys.path.insert(0, str(SCRIPTS))
        import post_github_text
        for footer in ("\n\n---\n_Generated by [Claude Code](https://claude.ai/code)_",
                       "\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)"):
            with self.subTest(footer=footer):
                self.assertEqual(post_github_text.compare(GOOD_PR, GOOD_PR + footer), [])

    def test_no_gh_says_what_to_do(self) -> None:
        done = self.post(GOOD_PR, "--number", "12", env=dict(self.env, PATH=str(self.tmp / "nothing")))
        self.assertEqual(done.returncode, 2)
        self.assertIn("--verify", done.stderr)


class Templates(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def adopt(self, root: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPTS / "adopt.py"), "--cwd", str(root), "--docs-home",
                               "docs/designs", *args], capture_output=True, text=True)

    def orient(self, root: Path) -> dict:
        return json.loads(subprocess.run([sys.executable, str(SCRIPTS / "orient.py"), "--cwd", str(root)],
                                         capture_output=True, text=True).stdout)

    def test_orient_reports_them_and_adopt_copies_the_missing_ones(self) -> None:
        root = self.tmp / "p"
        root.mkdir()
        self.assertEqual(self.orient(root)["githubTemplates"], {"pullRequest": None, "issue": None})
        dry = self.adopt(root, "--github-templates", "--dry-run")
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertFalse((root / ".github").exists())
        self.assertIn(".github/pull_request_template.md", dry.stderr)
        self.assertEqual(self.adopt(root, "--github-templates").returncode, 0)
        self.assertEqual(self.orient(root)["githubTemplates"],
                         {"pullRequest": ".github/pull_request_template.md",
                          "issue": ".github/ISSUE_TEMPLATE/capability.md"})
        self.assertEqual((root / ".github" / "pull_request_template.md").read_text(),
                         (SKILL / "templates" / "github" / "pull_request_template.md").read_text())

    def test_the_projects_own_template_is_left_as_it_is(self) -> None:
        root = self.tmp / "p"
        (root / "docs").mkdir(parents=True)
        (root / "docs" / "PULL_REQUEST_TEMPLATE.md").write_text("ours\n")
        done = self.adopt(root, "--github-templates")
        self.assertEqual(json.loads(done.stdout)["githubTemplatesWritten"], [".github/ISSUE_TEMPLATE/capability.md"])
        self.assertEqual((root / "docs" / "PULL_REQUEST_TEMPLATE.md").read_text(), "ours\n")
        self.assertFalse((root / ".github" / "pull_request_template.md").exists())


class SiblingAndAlso(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def lint(self, root: Path, body: str) -> dict:
        done = subprocess.run([sys.executable, str(LINT), "--kind", "pr", "-", "--cwd", str(root), "--json",
                               "--changed", str(FIX / "changed.json")], input=body, capture_output=True, text=True)
        self.assertIn(done.returncode, (0, 1), done.stderr)
        return json.loads(done.stdout)

    def here(self) -> Path:
        project(self.tmp / "sibling")
        return project(self.tmp / "here", map_value=False)

    def test_a_sibling_map_checks_the_rows(self) -> None:
        root = self.here()
        cfg = json.loads((root / ".claude" / "promise.config.json").read_text())
        cfg["sibling"] = {"repo": "o/sibling", "path": "../sibling", "find": "python3 find.py", "row": "python3 find.py"}
        (root / ".claude" / "promise.config.json").write_text(json.dumps(cfg))
        self.assertEqual(self.lint(root, GOOD_PR)["findings"], [])
        rules = {f["rule"] for f in self.lint(root, GOOD_PR.replace("Touched, verdicts unchanged: C-4",
                                                                    "Touched, verdicts unchanged: C-99"))["findings"]}
        self.assertIn("ROW_UNKNOWN", rules)

    def test_a_sibling_with_no_checkout_says_no_row_was_checked(self) -> None:
        root = project(self.tmp / "here", map_value=False)
        cfg = json.loads((root / ".claude" / "promise.config.json").read_text())
        cfg["sibling"] = {"repo": "o/sibling", "path": "../gone", "find": "f", "row": "r"}
        (root / ".claude" / "promise.config.json").write_text(json.dumps(cfg))
        self.assertIn("SIBLING_UNREAD", {f["rule"] for f in self.lint(root, GOOD_PR)["findings"]})

    def test_a_sibling_checkout_with_no_map_says_no_row_was_checked(self) -> None:
        (self.tmp / "bare").mkdir()
        root = project(self.tmp / "here", map_value=False)
        cfg = json.loads((root / ".claude" / "promise.config.json").read_text())
        cfg["sibling"] = {"repo": "o/bare", "path": "../bare", "find": "f", "row": "r"}
        (root / ".claude" / "promise.config.json").write_text(json.dumps(cfg))
        self.assertIn("SIBLING_UNREAD", {f["rule"] for f in self.lint(root, GOOD_PR)["findings"]})

    def test_an_also_area_the_map_holds_explains_its_own_name(self) -> None:
        root = project(self.tmp / "p")
        data = json.loads((root / "map.json").read_text())
        data["features"].append({"id": "catalogue", "name": "Catalogue", "plain": "What a client can order."})
        data["glossary"].append({"term": "Catalogue", "plain": "What a client can order."})
        (root / "map.json").write_text(json.dumps(data))
        body = GOOD_PR.replace("**Needed from you:**", "Also: **Catalogue**.\n\n**Needed from you:**")
        rules = [f for f in self.lint(root, body)["findings"] if f["rule"] == "TERM_UNDEFINED"]
        self.assertEqual(rules, [])


if __name__ == "__main__":
    unittest.main()
