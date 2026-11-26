#!/usr/bin/env python3
"""Git pre-commit checks for promise, for any agent or person that commits.

    precommit.py section0 <file.md> ...   # §0 of a ratified doc changed? compare the staged file with HEAD
    precommit.py lint <file.md> ...       # the outcome-doc shape lint, on the outcome docs among the files

Claude Code runs the §0 check before each edit (hooks/guard_section0.py);
other agents do not, so this runs it before each commit instead. It is what
``install_skill.py --git-hook`` installs, and what the ``promise-section0`` and
``promise-lint`` entries of ``.pre-commit-hooks.yaml`` run.

``section0`` compares each file as staged with its version at ``HEAD``, using
``diff_outcome.compare``: on an ``agreed``, ``building`` or ``shipped`` doc,
only the rule tags and the ``Scenarios:`` count may change, unless the same
change sets ``Status: draft``. Files that are not outcome docs, new files and
drafts pass. ``lint`` runs ``lint_outcome.py`` on the files that hold a
``## 0. TLDR`` heading. Exit 0 when every file passes, 1 when one does not,
2 on a usage error. Stdlib only.
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "skills", "promise", "scripts"))
sys.path.insert(0, SCRIPTS)

import diff_outcome  # noqa: E402
import lint_outcome  # noqa: E402


def staged_text(path: str):
    """The file as staged, or as on disk when it is not staged."""
    shown = subprocess.run(["git", "show", f":{path}"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    if shown.returncode == 0:
        return shown.stdout
    return diff_outcome.read_file(path)


def head_text(path: str):
    shown = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    return shown.stdout if shown.returncode == 0 else None


def section0(paths) -> int:
    failed = 0
    for path in paths:
        if not path.lower().endswith(".md"):
            continue
        for f in diff_outcome.compare(head_text(path), staged_text(path)):
            line = f["line"] if f["line"] is not None else 1
            print(f"{path}:{line}: {f['rule']} {f['message']}", file=sys.stderr)
            if f["severity"] == "error":
                failed = 1
    if failed:
        print("promise: commit blocked. §0 is the human's block; put the change to them as a note, "
              "or set Status: draft in the same change so they agree it again.", file=sys.stderr)
    return failed


def lint(paths) -> int:
    failed = 0
    for path in paths:
        if not path.lower().endswith(".md") or not lint_outcome.contains_tldr(path):
            continue
        result = lint_outcome.lint_file(path, strict=False)
        for f in result["findings"]:
            line = f["line"] if f["line"] is not None else 1
            print(f"{path}:{line}: {f['rule']} {f['message']}", file=sys.stderr)
        if result["stats"]["errors"]:
            failed = 1
    return failed


def main(argv) -> int:
    if not argv or argv[0] not in ("section0", "lint"):
        print("usage: precommit.py section0|lint <file.md> ...", file=sys.stderr)
        return 2
    command, paths = argv[0], argv[1:]
    return section0(paths) if command == "section0" else lint(paths)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
