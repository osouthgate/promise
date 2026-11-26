#!/usr/bin/env python3
"""Install the promise skill for agents other than Claude Code: Codex, Cursor and
any agent that reads the shared ``.agents/skills`` folder.

    python3 install_skill.py                               # ~/.agents/skills/promise (Codex and Cursor both read it)
    python3 install_skill.py --host codex --host cursor    # ~/.codex/skills/promise and ~/.cursor/skills/promise
    python3 install_skill.py --project . --host all        # .agents/, .codex/ and .cursor/skills/promise in this repo
    python3 install_skill.py --project . --git-hook        # also a git pre-commit hook for the §0 rule
    python3 install_skill.py --copy                        # copy instead of symlink (Windows, or a vendored copy)
    python3 install_skill.py --dry-run                     # say what it would do; write nothing

In Claude Code, install the plugin instead (``claude plugin install
promise@promise``): the plugin also brings the hook that stops the model
editing an agreed §0. Other agents have no such hook, so ``--git-hook`` puts
the same check in front of every commit, and the GitHub Action
(``uses: osouthgate/promise@v1``) puts it in front of every pull request.

Each host reads a skill from a folder named after it, holding ``SKILL.md``:

- ``agents``: ``~/.agents/skills/promise`` or ``<project>/.agents/skills/promise``
  (the shared folder; Codex and Cursor both read it);
- ``codex``:  ``~/.codex/skills/promise`` or ``<project>/.codex/skills/promise``;
- ``cursor``: ``~/.cursor/skills/promise`` or ``<project>/.cursor/skills/promise``.

A symlink keeps the installed skill up to date with this checkout; ``--copy``
makes an independent copy. An existing target is left alone unless it is
already this skill (same link, or a copy with the same ``SKILL.md``), in which
case the run is a no-op; anything else there is refused, never overwritten.

``--git-hook`` needs ``--project`` and writes ``<project>/.git/hooks/pre-commit``,
which runs ``hooks/precommit.py section0`` from this checkout on the staged
Markdown files. An existing pre-commit hook that is not this one is refused;
add the line it prints to your own hook instead. Projects that use the
pre-commit framework can use the ``.pre-commit-hooks.yaml`` at this repo's root.

Prints one JSON object: what was installed, skipped or refused. Exit 0 when
nothing was refused, 1 when something was, 2 on a usage error. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
from typing import Any, Dict, List, Optional

SKILL_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO_ROOT = os.path.normpath(os.path.join(SKILL_DIR, "..", ".."))
PRECOMMIT = os.path.join(REPO_ROOT, "hooks", "precommit.py")
HOSTS = {"agents": ".agents", "codex": ".codex", "cursor": ".cursor"}
HOOK_MARKER = "# promise: §0 check (install_skill.py)"


def target_for(host: str, base: str) -> str:
    return os.path.join(base, HOSTS[host], "skills", "promise")


def _same_skill(target: str) -> bool:
    if os.path.islink(target):
        return os.path.realpath(target) == os.path.realpath(SKILL_DIR)
    mine = os.path.join(SKILL_DIR, "SKILL.md")
    theirs = os.path.join(target, "SKILL.md")
    if os.path.isfile(theirs):
        with open(mine, "rb") as a, open(theirs, "rb") as b:
            return a.read() == b.read()
    return False


def install(target: str, copy: bool, dry_run: bool) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"target": target, "mode": "copy" if copy else "symlink"}
    if os.path.lexists(target):
        if _same_skill(target):
            entry["result"] = "already-installed"
        else:
            entry["result"] = "refused"
            entry["reason"] = "something else is already there; move it away first"
        return entry
    entry["result"] = "would-install" if dry_run else "installed"
    if dry_run:
        return entry
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if copy:
        shutil.copytree(SKILL_DIR, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        os.symlink(SKILL_DIR, target, target_is_directory=True)
    return entry


def hook_script() -> str:
    return (
        "#!/bin/sh\n"
        f"{HOOK_MARKER}\n"
        "# Fails the commit when §0 of an agreed, building or shipped outcome doc changed\n"
        "# in anything but its rule tags and Scenarios: count without going back to draft.\n"
        f'exec python3 "{PRECOMMIT}" section0 $(git diff --cached --name-only --diff-filter=M -- "*.md")\n'
    )


def install_git_hook(project: str, dry_run: bool) -> Dict[str, Any]:
    git_dir = os.path.join(project, ".git")
    target = os.path.join(git_dir, "hooks", "pre-commit")
    entry: Dict[str, Any] = {"target": target}
    if not os.path.isdir(git_dir):
        entry["result"] = "refused"
        entry["reason"] = f"{project} is not the root of a git work tree (no .git folder)"
        return entry
    script = hook_script()
    if os.path.exists(target):
        with open(target, "r", encoding="utf-8", errors="replace") as fh:
            existing = fh.read()
        if existing == script:
            entry["result"] = "already-installed"
        else:
            entry["result"] = "refused"
            entry["reason"] = "a pre-commit hook already exists; add this line to it: " + script.splitlines()[-1]
        return entry
    entry["result"] = "would-install" if dry_run else "installed"
    if not dry_run:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(script)
        mode = os.stat(target).st_mode
        os.chmod(target, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return entry


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="install_skill.py",
        description="Install the promise skill for Codex, Cursor and other agents that read SKILL.md.",
    )
    parser.add_argument("--host", action="append", choices=sorted(HOSTS) + ["all"],
                        help="where to install (repeatable; default: agents, which Codex and Cursor both read)")
    parser.add_argument("--project", default=None, help="install into this project instead of your home folder")
    parser.add_argument("--home", default=None, help=argparse.SUPPRESS)  # tests point this at a temp folder
    parser.add_argument("--copy", action="store_true", help="copy the skill instead of symlinking it")
    parser.add_argument("--git-hook", action="store_true", help="also install a git pre-commit hook (needs --project)")
    parser.add_argument("--dry-run", action="store_true", help="write nothing; say what would be done")
    args = parser.parse_args(argv)

    if args.git_hook and not args.project:
        print("install_skill.py: --git-hook needs --project", file=sys.stderr)
        return 2
    if args.project and not os.path.isdir(args.project):
        print(f"install_skill.py: no such directory: {args.project}", file=sys.stderr)
        return 2
    hosts = args.host or ["agents"]
    if "all" in hosts:
        hosts = sorted(HOSTS)
    base = os.path.abspath(args.project) if args.project else (args.home or os.path.expanduser("~"))
    copy = args.copy or (os.name == "nt")

    results = [dict(install(target_for(h, base), copy, args.dry_run), host=h) for h in sorted(set(hosts))]
    out: Dict[str, Any] = {"skill": SKILL_DIR, "scope": "project" if args.project else "user", "skills": results}
    if args.git_hook:
        out["gitHook"] = install_git_hook(os.path.abspath(args.project), args.dry_run)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    refused = [r for r in results if r["result"] == "refused"]
    if args.git_hook and out["gitHook"]["result"] == "refused":
        refused.append(out["gitHook"])
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
