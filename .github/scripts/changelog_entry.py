#!/usr/bin/env python3
"""Print one version's CHANGELOG.md entry, as the notes of its GitHub release.

    python3 .github/scripts/changelog_entry.py 1.34.1 [--tag v1.34.1] [--changelog CHANGELOG.md]

The entry is everything under ``## <version>`` up to the next ``## <version>`` heading.
A version with no entry gets one line saying so. With ``--tag``, a last line links the
whole CHANGELOG at that tag. Exit 2 on a version that is not X.Y.Z.
"""
from __future__ import annotations

import argparse
import re
import sys

REPO = "osouthgate/promise"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def entry(text: str, version: str) -> str:
    """The entry's body, stripped, or "" when the CHANGELOG has none for it."""
    heading = re.compile(r"^## \[?v?" + re.escape(version) + r"\]?(?![\w.])[^\n]*\n", re.MULTILINE)
    m = heading.search(text)
    if not m:
        return ""
    nxt = re.compile(r"^## \[?v?\d+\.\d+\.\d+", re.MULTILINE).search(text, m.end())
    return text[m.end():nxt.start() if nxt else len(text)].strip()


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("version")
    ap.add_argument("--tag")
    ap.add_argument("--changelog", default="CHANGELOG.md")
    args = ap.parse_args(argv)
    if not VERSION_RE.match(args.version):
        print(f"changelog_entry.py: {args.version!r} is not X.Y.Z", file=sys.stderr)
        return 2
    with open(args.changelog, encoding="utf-8") as fh:
        body = entry(fh.read(), args.version) or f"No CHANGELOG entry for {args.version}."
    if args.tag:
        body += f"\n\n**Full changelog:** https://github.com/{REPO}/blob/{args.tag}/CHANGELOG.md"
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
