#!/usr/bin/env python3
"""PreToolUse hook: lint an issue or pull request body before an agent posts it.

Claude Code runs this before a GitHub MCP tool writes an issue or a pull request
(``create_pull_request``, ``update_pull_request``, ``issue_write``, ``create_issue``,
``update_issue``, whatever the server's name) and before a shell command that runs
``gh pr|issue create|edit`` with ``--body-file`` or ``--body`` (hooks/hooks.json). In a
project adopted for promise (a config and the promise section):

- a body with a ``<!-- promise:pr -->`` or ``<!-- promise:issue -->`` block that fails
  ``lint_github_text.py`` is blocked: exit 2, with the findings on stderr, which Claude
  Code shows to the model;
- a new issue or pull request whose body has no block asks the person first
  (``permissionDecision: ask``): ``/promise issue`` and ``/promise pr`` write one, and a
  body that needs none is theirs to wave through.

Everything else passes: a project not adopted, a call with no body, a comment. It
fails open: any error of its own exits 0, so a bug here never stops unrelated work.
``scripts/post_github_text.py`` is the one way the modes post, and it reads the stored
body back; this hook covers the calls that do not go through it.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "skills", "promise", "scripts"))
MCP_WRITE_RE = re.compile(r"^mcp__.*github.*__(create_pull_request|update_pull_request|issue_write|create_issue|"
                          r"update_issue)$", re.IGNORECASE)
MARKER = {"pr": "<!-- promise:pr -->", "issue": "<!-- promise:issue -->"}


def from_mcp(tool: str, tool_input: dict) -> Optional[Tuple[str, str, bool]]:
    """(kind, body, creates) for a GitHub MCP write, or None."""
    m = MCP_WRITE_RE.match(tool or "")
    if not m:
        return None
    name = m.group(1).lower()
    kind = "pr" if "pull_request" in name else "issue"
    creates = name.startswith("create") or (name == "issue_write" and tool_input.get("method") == "create")
    body = tool_input.get("body")
    if not isinstance(body, str):
        # an update that leaves the body alone passes; a new one with no body has no block
        return (kind, "", True) if creates else None
    return kind, body, creates


def from_shell(command: str, cwd: str) -> Optional[Tuple[str, str, bool]]:
    """(kind, body, creates) for ``gh pr|issue create|edit`` with a body, or None."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        argv = list(lexer)
    except ValueError:
        return None
    for i in range(len(argv) - 2):
        if os.path.basename(argv[i]) == "gh" and argv[i + 1] in ("pr", "issue") and argv[i + 2] in ("create", "edit"):
            rest = argv[i + 3:]
            # this command's own words only: the next one starts at a shell operator
            cut = next((k for k, w in enumerate(rest) if w and set(w) <= set("&|;()<>")), len(rest))
            rest = rest[:cut]
            for j, word in enumerate(rest):
                value = None
                if word in ("--body-file", "-F") and j + 1 < len(rest):
                    path = rest[j + 1]
                    if path == "-":
                        return None
                    with open(os.path.join(cwd, path), "r", encoding="utf-8-sig") as fh:
                        value = fh.read()
                elif word.startswith("--body-file="):
                    with open(os.path.join(cwd, word.split("=", 1)[1]), "r", encoding="utf-8-sig") as fh:
                        value = fh.read()
                elif word in ("--body", "-b") and j + 1 < len(rest):
                    value = rest[j + 1]
                elif word.startswith("--body="):
                    value = word.split("=", 1)[1]
                if value is not None:
                    if not word.startswith("--body-file") and word != "-F" and ("$" in value or "`" in value):
                        return None  # the shell builds it ($(cat <<EOF …), $VAR): the text is not known here
                    return argv[i + 1], value, argv[i + 2] == "create"
            if argv[i + 2] == "create":
                return argv[i + 1], "", True  # gh fills the body itself (--fill, the template): no block
    return None


def adopted(cwd: str) -> bool:
    sys.path.insert(0, SCRIPTS)
    import orient  # noqa: E402
    config, _path, _warnings = orient.load_config(cwd)
    return isinstance(config, dict) and bool(orient.detect_claude_md(cwd).get("hasPromiseSection"))


def lint_errors(kind: str, body: str, cwd: str) -> list:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(body)
        path = fh.name
    try:
        proc = subprocess.run([sys.executable, os.path.join(SCRIPTS, "lint_github_text.py"), "--kind", kind, path,
                               "--cwd", cwd, "--json"], capture_output=True, text=True, timeout=25)
    finally:
        os.unlink(path)
    if proc.returncode not in (0, 1):
        return []  # a usage error is the lint's, not the body's: fail open
    data = json.loads(proc.stdout)
    return [f for f in data.get("findings", []) if f.get("severity") == "error"]


def main() -> int:
    try:
        event = json.load(sys.stdin)
        tool = event.get("tool_name") or ""
        tool_input = event.get("tool_input") or {}
        cwd = event.get("cwd") or os.getcwd()
        if not isinstance(tool_input, dict):
            return 0
        if tool == "Bash":
            found = from_shell(str(tool_input.get("command") or ""), cwd)
        else:
            found = from_mcp(tool, tool_input)
        if not found or not adopted(cwd):
            return 0
        kind, body, creates = found
        noun = "pull request" if kind == "pr" else "issue"
        if MARKER[kind] not in body:
            if creates:
                print(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "PreToolUse", "permissionDecision": "ask",
                    "permissionDecisionReason": (
                        f"promise: this new {noun}'s body has no {MARKER[kind]} block. /promise {kind} writes one "
                        "and lints it (scripts/post_github_text.py posts it). Post it without one?")}}))
            return 0
        errors = lint_errors(kind, body, cwd)
        if errors:
            listed = "; ".join(f"line {f.get('line') or 1}: {f['rule']} {f['message']}" for f in errors[:8])
            print(f"promise: blocked. This {noun} body fails lint_github_text.py: {listed}. Fix the block, lint the "
                  f"file (lint_github_text.py --kind {kind} <file>), and post it with scripts/post_github_text.py.",
                  file=sys.stderr)
            return 2
    except Exception:  # fail open: never block work because of a bug here
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
