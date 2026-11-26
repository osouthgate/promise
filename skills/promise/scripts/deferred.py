#!/usr/bin/env python3
"""List the promise work that was deferred and is still owed.

    python3 deferred.py [--cwd DIR] [--limit 100] [--json]
    python3 deferred.py --input prs.json [--json]      # gh pr list --json number,title,url,body,mergedAt

A change built first, under pressure (``references/sizing.md`` § Deferred), says so in its
pull request's promise block: ``Size: deferred — owes: <each promise it touched or made>``.
``/promise reconcile`` pays it later, and marks the block with a ``Paid:`` line (``Paid:
#131, CAP-12 S4``). This script reads the merged pull requests whose body says ``Size:
deferred`` (through ``gh``, which holds its own credentials, or ``--input``) and prints each
one with no ``Paid:`` line: its number, title, merge date and what it owes, oldest first.

It changes nothing. Exit 0 (an empty list included), 2 when there is no ``gh`` and no
``--input``, or the list cannot be read.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

sys.dont_write_bytecode = True
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import lint_github_text  # noqa: E402  (sibling-script import; see path insert above)

OWES_RE = re.compile(r"\bowes\s*:\s*(.+)$", re.IGNORECASE)
PAID_RE = re.compile(r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?Paid(?:\*\*|__)?\s*:\s*\S", re.IGNORECASE | re.MULTILINE)
PART_RE = re.compile(r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?Paid in part(?:\*\*|__)?\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
SEARCH = '"Size: deferred" in:body'


def owed(body: str) -> Optional[str]:
    """What a pull request body owes, or None when it is not deferred, or is paid."""
    body = (body or "").replace("\r\n", "\n")
    said = lint_github_text.size_lines(body)
    if not any(word == "deferred" for _n, word in said):
        return None
    bounds, _why = lint_github_text.find_block(body, "pr")
    block = lint_github_text.visible("\n".join(body.split("\n")[bounds[0]:bounds[1]]) if bounds else body)
    if PAID_RE.search(block):
        return None
    lines = lint_github_text.visible(body).split("\n")
    owes = "(the Size line does not say)"
    for n, word in said:
        if word == "deferred":
            m = OWES_RE.search(re.sub(r"\*\*|__", "", lines[n - 1]))
            owes = m.group(1).strip() if m else owes
            break
    parts = [p.strip() for p in PART_RE.findall(block)]
    return owes + (f" (paid in part: {'; '.join(parts)})" if parts else "")


def from_gh(cwd: str, limit: int) -> List[Dict[str, Any]]:
    proc = subprocess.run(["gh", "pr", "list", "--state", "merged", "--search", SEARCH, "--limit", str(limit),
                           "--json", "number,title,url,body,mergedAt"], capture_output=True, text=True, cwd=cwd,
                          stdin=subprocess.DEVNULL, timeout=120)
    if proc.returncode != 0:
        raise ValueError(f"gh pr list failed: {proc.stderr.strip()[:300]}")
    return json.loads(proc.stdout or "[]")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--limit", type=int, default=100, help="merged pull requests to read (default 100)")
    ap.add_argument("--input", help="gh pr list --json number,title,url,body,mergedAt output, instead of gh")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.input:
            with open(args.input, "r", encoding="utf-8-sig") as fh:
                prs = json.load(fh)
        elif shutil.which("gh"):
            prs = from_gh(os.path.abspath(args.cwd), args.limit)
        else:
            print("deferred.py: no gh on PATH; search merged pull requests for "
                  f"{SEARCH} with the host's GitHub tool, or pass --input", file=sys.stderr)
            return 2
        if not isinstance(prs, list):
            raise ValueError("the list is not a JSON array of pull requests")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"deferred.py: {exc}", file=sys.stderr)
        return 2
    debts = []
    for pr in prs:
        if not isinstance(pr, dict):
            continue
        owes = owed(str(pr.get("body") or ""))
        if owes is not None:
            debts.append({"number": pr.get("number"), "title": pr.get("title"), "url": pr.get("url"),
                          "mergedAt": pr.get("mergedAt"), "owes": owes})
    debts.sort(key=lambda d: str(d.get("mergedAt") or "9999"))  # an unknown date sorts last
    if not args.input and len(prs) >= args.limit:
        print(f"deferred.py: read the newest {args.limit} deferred pull requests only, paid ones included; "
              "older debts may be missing: raise --limit", file=sys.stderr)
    if args.json:
        print(json.dumps({"owed": debts, "count": len(debts)}, indent=2, ensure_ascii=False))
    elif not debts:
        print("nothing deferred is owed")
    else:
        for d in debts:
            print(f"#{d['number']} {d['title']} (merged {str(d.get('mergedAt') or '?')[:10]}): owes {d['owes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
