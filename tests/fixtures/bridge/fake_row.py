#!/usr/bin/env python3
"""Stand-in for a project's `map.row` command, for bridge_validate.py's tests.

    python3 fake_row.py <id>
    FAKE_ROW_LOG=/path/to/log.jsonl python3 fake_row.py <id>
    FAKE_ROW_FORMAT=text python3 fake_row.py <id>

For a known id, prints the row as one JSON object, the shape the starter
map's reader prints: its id, its own argv (excluding the script path) under
``argv`` — so a test can confirm a row id, however it is spelled, arrived as
exactly one argv element rather than being parsed or expanded by a shell —
a story, and its scenarios, each with a ``then`` and an ``altitude``. An
unknown id exits 2 with nothing on stdout, matching how a real row-lookup
command behaves when a row does not exist.

``FAKE_ROW_FORMAT=text`` prints the older text shape instead: the argv as
one ``repr(...)`` line, then the row's scenario text as one sentence. A map
whose ``map.row`` prints text cannot be checked exactly; bridge_validate.py
falls back to its substring check for it.

When ``FAKE_ROW_LOG`` is set, one JSON line of ``sys.argv`` (the full argv,
script path included) is appended to that file per invocation — an
independent, out-of-band record a test can read back after running
bridge_validate.py end to end, so the cache and argv-safety proofs do not
depend on parsing this script's own stdout back out of bridge_validate.py's
JSON (which does not carry it) or on calling adapter.py directly instead of
going through the real bridge_validate.py -> adapter.py -> fake_row.py path.

R1's scenarios are AT-1's and AT-2's `Then` text and altitude from
agreed_bridged.md, so neither drifts. R2's scenario is deliberately reworded
against AT-3's `Then` in that same fixture, so the drift check has
something real to catch. R3's scenario holds a pipe inside a code span,
which a §6 cell writes as ``\\|``. The text shape holds the same sentences.
"""

from __future__ import annotations

import json
import os
import sys

ROWS = {
    "R1": {
        "story": "A member mutes a busy channel.",
        "scenarios": [
            {"then": "she gets no push or badge from it", "altitude": "perception"},
            {"then": "notifications resume immediately", "altitude": "perception"},
        ],
    },
    "R2": {
        "story": "A mute is per member.",
        "scenarios": [
            {
                "then": "a second, unmuted member keeps getting a push for every new message in the channel",
                "altitude": "perception",
            },
        ],
    },
    "R3": {
        "story": "The mute command says how to use it.",
        "scenarios": [
            {"then": "the usage line reads `mute <channel|all>`", "altitude": "response"},
        ],
    },
}

TEXT = {
    "R1": (
        "Row R1 -- a member mutes a busy channel: muting it means "
        "she gets no push or badge from it, and unmuting it means "
        "notifications resume immediately."
    ),
    "R2": (
        "Row R2 -- a mute is per member: a second, unmuted member "
        "keeps getting a push for every new message in the channel."
    ),
    "R3": "Row R3 -- the usage line reads `mute <channel|all>`.",
}


def log_invocation() -> None:
    log_path = os.environ.get("FAKE_ROW_LOG")
    if not log_path:
        return
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(sys.argv) + "\n")


def main(argv=None) -> int:
    log_invocation()
    args = sys.argv[1:] if argv is None else argv
    known = len(args) == 1 and args[0] in ROWS
    if os.environ.get("FAKE_ROW_FORMAT") == "text":
        print(repr(args))
        if known:
            print(TEXT[args[0]])
    if not known:
        print(f"fake_row.py: no such row: {args!r}", file=sys.stderr)
        return 2
    if os.environ.get("FAKE_ROW_FORMAT") != "text":
        print(json.dumps({"id": args[0], "argv": args, **ROWS[args[0]]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
