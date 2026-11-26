#!/usr/bin/env python3
"""Check that §0 of an agreed outcome doc did not change behind the human's back.

    python3 diff_outcome.py before.md after.md
    python3 diff_outcome.py doc.md --base origin/main
    python3 diff_outcome.py --dir docs/designs --base origin/main --json

§0 is the human's block. The framework's rule (outcome-framework.md, decision
F6): only the agent-maintained metadata in it may change without the human --
each rule's trailing ``→ AT-n`` / ``→ UNTESTED`` tag and the ``**Scenarios:**``
count. Any other change to §0 of a doc that is ``agreed``, ``building`` or
``shipped`` un-ratifies it, so the same change must drop ``Status:`` back to
``draft``.

This script compares the protected text of §0 before and after: the block from
``## 0. TLDR`` up to the ``Agent notes`` line (or ``## 1.``), with the rule tags
and the ``**Scenarios:**`` line removed, blank lines dropped and whitespace
collapsed. Lines inside a fenced code block count as text here, as they do in
the lint's line budget.

Rule ids:

- ``S0_CHANGED`` (error): the protected text changed, the doc was ``agreed``,
  ``building`` or ``shipped`` before, and it is not ``draft`` after.
- ``S0_REOPENED`` (warn): the protected text changed on such a doc and the
  status went back to ``draft``, as the rule asks. A human re-ratifies it.

A doc that was ``draft`` (thin or full), ``superseded-by``, or did not exist
before is not checked: its human half is still being written. A doc that was
deleted is not checked either (merge deletes docs by design).

Before and after come from two files, or from a git ref and the working tree
(``--base REF``: the doc as it is at REF, read with ``git show``). ``--dir``
checks every outcome doc directly inside the folder, as the lint does. The
script cannot tell who made a change -- a human's own edit to an agreed §0
fails the same way; the fix is the same too: set ``Status: draft`` and
re-agree.

Exit 0 when there is no error finding, 1 when there is, 2 on a usage error.
Human output is one line per finding, ``<path>:<line>: <RULE_ID> <message>``.
``--json`` prints one object for a file and an array for ``--dir``.
Deterministic; stdlib only; no network (git runs locally).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import lint_outcome  # noqa: E402  (sibling-script import; see path insert above)

RATIFIED = ("agreed", "building", "shipped")
SCENARIOS_MARKER = "**Scenarios:**"
TRAILING_TAG_RE = re.compile(r"\s*→\s*(UNTESTED|AT-\d+(?:\s*,\s*AT-\d+)*)\s*$")
WHITESPACE_RE = re.compile(r"\s+")


def protected_lines(text: str) -> List[Tuple[int, str]]:
    """(1-based line, normalised text) for each protected line of §0.

    Empty when the text has no ``## 0. TLDR`` heading."""
    lines = text.splitlines()
    bounds = lint_outcome.tldr_block_bounds(lines)
    if bounds is None:
        return []
    start, end = bounds
    out: List[Tuple[int, str]] = []
    for i in range(start, end):
        line = lines[i]
        if SCENARIOS_MARKER in line:
            continue
        line = TRAILING_TAG_RE.sub("", line)
        line = WHITESPACE_RE.sub(" ", line).strip()
        if line:
            out.append((i + 1, line))
    return out


def status_of(text: str) -> Optional[str]:
    return lint_outcome.get_status(text.splitlines())


def compare(before: Optional[str], after: Optional[str]) -> List[Dict[str, Any]]:
    """Findings for one doc, given its text before and after (None = absent)."""
    if before is None or after is None:
        return []
    status_before = status_of(before)
    if status_before not in RATIFIED:
        return []
    old = protected_lines(before)
    new = protected_lines(after)
    if [t for _, t in old] == [t for _, t in new]:
        return []
    line, detail = _first_difference(old, new)
    status_after = status_of(after)
    if status_after == "draft":
        return [
            lint_outcome.finding(
                "S0_REOPENED",
                line,
                f"§0 changed and Status: went from {status_before} to draft; "
                f"a human re-agrees it ({detail})",
                "warn",
            )
        ]
    return [
        lint_outcome.finding(
            "S0_CHANGED",
            line,
            f"§0 changed while Status: is {status_after or 'missing'} (was {status_before}); "
            f"only rule tags and the Scenarios: count may change without the human. "
            f"Revert the §0 edit, or set Status: draft so a human re-agrees it ({detail})",
            "error",
        )
    ]


def _first_difference(
    old: List[Tuple[int, str]], new: List[Tuple[int, str]]
) -> Tuple[Optional[int], str]:
    for (_, a), (line, b) in zip(old, new):
        if a != b:
            return line, f"was {_clip(a)!r}, now {_clip(b)!r}"
    if len(new) > len(old):
        line, b = new[len(old)]
        return line, f"added {_clip(b)!r}"
    _, a = old[len(new)]
    last = new[-1][0] if new else None
    return last, f"removed {_clip(a)!r}"


def _clip(text: str, width: int = 200) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def read_file(path: str) -> Optional[str]:
    if not os.path.isfile(path):
        return None
    return lint_outcome.read_text_tolerant(path)


def read_at_ref(path: str, ref: str) -> Optional[str]:
    """The file's text at ``ref``, or None when it did not exist there.

    Raises RuntimeError when git itself cannot run or the ref is unknown."""
    directory = os.path.dirname(os.path.abspath(path)) or "."
    name = os.path.basename(path)
    try:
        known = subprocess.run(
            ["git", "-C", directory, "rev-parse", "--verify", "--quiet", ref + "^{commit}"],
            capture_output=True, text=True,
        )
    except OSError as exc:
        raise RuntimeError(f"cannot run git: {exc}")
    if known.returncode != 0:
        raise RuntimeError(f"unknown git ref {ref!r} (fetch it first)")
    shown = subprocess.run(
        ["git", "-C", directory, "show", f"{ref}:./{name}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if shown.returncode != 0:
        return None
    return shown.stdout.lstrip("﻿").replace("\r\n", "\n")


def result(path: str, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    errors = sum(1 for f in findings if f["severity"] == "error")
    warns = sum(1 for f in findings if f["severity"] == "warn")
    return {
        "path": path,
        "findings": findings,
        "stats": {"errors": errors, "warnings": warns, "total": len(findings)},
    }


def format_human(results: List[Dict[str, Any]]) -> str:
    out = []
    for r in results:
        for f in r["findings"]:
            line = f["line"] if f["line"] is not None else 1
            out.append(f"{r['path']}:{line}: {f['rule']} {f['message']}")
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="diff_outcome.py",
        description="Fail when §0 of an agreed outcome doc changed without going back to draft.",
    )
    parser.add_argument("paths", nargs="*", help="BEFORE AFTER, or one DOC with --base")
    parser.add_argument("--base", default=None, help="git ref to read the 'before' version from")
    parser.add_argument("--dir", default=None, help="check every outcome doc in this folder (needs --base)")
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    def usage(message: str) -> int:
        print(f"diff_outcome.py: {message}", file=sys.stderr)
        return 2

    results: List[Dict[str, Any]] = []
    try:
        if args.dir is not None:
            if args.paths or not args.base:
                return usage("--dir takes no paths and needs --base")
            if not os.path.isdir(args.dir):
                return usage(f"no such directory: {args.dir}")
            for path in lint_outcome.collect_directory_docs(args.dir):
                results.append(result(path, compare(read_at_ref(path, args.base), read_file(path))))
        elif args.base is not None:
            if len(args.paths) != 1:
                return usage("--base takes exactly one DOC")
            path = args.paths[0]
            results.append(result(path, compare(read_at_ref(path, args.base), read_file(path))))
        else:
            if len(args.paths) != 2:
                return usage("give BEFORE and AFTER, or one DOC with --base, or --dir with --base")
            before_path, after_path = args.paths
            if not os.path.isfile(before_path):
                return usage(f"no such file: {before_path}")
            results.append(result(after_path, compare(read_file(before_path), read_file(after_path))))
    except RuntimeError as exc:
        return usage(str(exc))
    except (OSError, UnicodeDecodeError) as exc:
        return usage(f"cannot read: {exc}")

    if args.json:
        payload: Any = results if args.dir is not None else results[0]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        text = format_human(results)
        if text:
            print(text)
    return 1 if any(r["stats"]["errors"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
