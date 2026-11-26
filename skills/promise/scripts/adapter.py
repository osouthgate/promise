#!/usr/bin/env python3
"""Run a project's configured map and verification commands safely.

    python3 adapter.py [--cwd DIR] [--json] find "<query>"
    python3 adapter.py [--cwd DIR] [--json] find --query-file <path>
    python3 adapter.py [--cwd DIR] [--json] row <id>
    python3 adapter.py [--cwd DIR] [--json] next-id
    python3 adapter.py [--cwd DIR] [--json] learn --query-file <path> --row <id> --source <source>
    python3 adapter.py [--cwd DIR] [--json] refs-sync --input <path>
    python3 adapter.py [--cwd DIR] [--json] code <id>
    python3 adapter.py [--cwd DIR] [--json] checks
    python3 adapter.py [--cwd DIR] [--json] verify [--only typeCheck|test|lint ...]
    python3 adapter.py [--cwd DIR] [--json] surfaces [--out <path>]
    python3 adapter.py [--cwd DIR] show

A mode never composes a shell string from a configured command plus
user-supplied text. Every configured command string is split with
``shlex.split`` into its own argv, and a caller-supplied argument — a
search query, a row id — is appended as exactly one more argv element,
never interpolated into text a shell would parse. Every child process
runs with ``shell=False``, so a hostile query containing ``$(...)`` or
backticks is inert: it becomes one string in argv, nothing more, and
nothing it contains ever executes.

``find`` takes its query either as the positional argument or from
``--query-file <path>`` (``-`` reads stdin). The file form exists so a
query that may carry quotes — a verbatim feedback item, say — never has
to appear on a command line at all: write it to a file, name the file.
The file is read as UTF-8 (a BOM is tolerated) and only its trailing
line terminators are dropped; everything else reaches the child
verbatim, as one argv element.

Config is resolved through ``orient.py`` — this script parses no config
file of its own; ``map``, ``mapUsable`` and ``commands`` come straight
from its orientation JSON. ``mapUsable`` is the single source of "is a
map configured": when it is false for a map that is present but
incomplete, every map operation refuses and names the keys orient found
missing, rather than running whatever part of the map happens to exist.
``find``, ``row`` and ``next-id`` each run one configured command and
report one result. ``row`` additionally validates the id against
``map.rowIdPattern`` when the project sets one, and refuses — without
running anything — on a mismatch. ``checks`` runs ``map.checks`` in the
configured order and stops at the first non-zero exit. ``verify`` runs
``commands.typeCheck``, ``commands.test`` and ``commands.lint`` in that
order, skipping any that are not configured, and also stops at the first
non-zero exit; ``--only <name>`` (repeatable) narrows it to the named
commands, still in that order. ``surfaces`` runs ``map.surfaces`` -- a
command string, or an argv array used as written -- stopped after five
minutes, and prints the code's entry points one per line, as
``map_report.py --surfaces`` and ``check.py`` read them (a leading
byte-order mark, blank and ``#`` lines dropped, each line trimmed, the
first of each kept), or writes them to ``--out <path>`` with one line on
stderr saying how many; an empty list exits 1, since it proves nothing.
``learn`` runs ``map.learn`` with ``--query-file <absolute path> --row <id>
--source <source>`` appended, each one argv element: the map records the
words ``find`` missed the row by (the starter reader's ``learn``). The row
id is checked against ``map.rowIdPattern`` first, as for ``row``; the ask
itself travels only as a file, never on a command line. ``refs-sync``
runs ``map.refsSync`` with ``--input <absolute path>`` appended: a JSON file
of merged pull requests the caller fetched, whose promise blocks name the
rows that get a ref. ``code`` runs ``map.code`` with the row id appended,
checked against ``map.rowIdPattern`` as for ``row``: the local files the
row's cited tests import.
``show`` prints every command each op
would run, one per line, in the same "label: command" shape, and runs
nothing at all; an incomplete map is still printed, followed by a line
saying why its operations would refuse. It also lists ``map.surfaces``,
the command ``surfaces`` and ``check.py`` run to list the code's entry
points (a string, or an argv array shown shell-quoted).

A project with ``"map": false`` and a ``sibling`` object (orient reports
the object as ``sibling``; ``mapUsable`` stays false, since the project has
no map of its own) keeps its rows in another repository's map.
``find`` and ``row`` then run ``sibling.find`` and ``sibling.row`` the same
way, with the sibling checkout (``sibling.path``) as the working directory.
That map is read-only from here: every other map operation refuses with
exit 2, so nothing this script runs writes there, and ``find`` and ``row``
refuse too when there is no checkout at the path. ``show`` lists the two
commands and the folder they run in.

A request that cannot even be attempted — no map configured, a map
orient reports as incomplete, the specific command an op needs is absent
or is not a string, or a row id that fails ``map.rowIdPattern`` —
refuses with exit 2 and a one-line reason on stderr, always plain text
regardless of ``--json``, because there is no child result to report. A
configured executable that does not exist exits 127 with a one-line
reason instead of a traceback; this is treated as an attempted run, so
it does appear in ``--json`` output with ``"exit": 127``. A
``map.checks`` entry or a verify command that is not a string is
reported as its own step with ``"exit": 2`` and stops the sequence, the
same way an unparseable command string does.

Once a command actually runs, ``--json`` prints one object
``{"op", "argv", "exit", "stdout", "stderr"}`` for a single-command op, or
a JSON array of that shape, one entry per step actually attempted, for
``checks``/``verify``; ``surfaces`` adds ``entries``, the list. Without
``--json``, each child's own stdout and
stderr stream straight to this process's stdout and stderr as it runs,
and the process exits with the exit code of the last step attempted (0
when every step — or zero steps — succeeded).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import orient  # noqa: E402  (sibling-script import; see path insert above)

VERIFY_COMMAND_ORDER = ("typeCheck", "test", "lint")

MAP_OPERATIONS = ("find", "row", "next-id", "learn", "refs-sync", "code", "checks", "surfaces")

# The only map operations that run in a sibling's checkout: both read.
SIBLING_OPERATIONS = ("find", "row")

SURFACES_TIMEOUT = 300  # seconds

_MAP_COMMAND_LABELS = (("find", "map.find"), ("row", "map.row"), ("nextId", "map.nextId"),
                       ("learn", "map.learn"), ("refsSync", "map.refsSync"),
                       ("code", "map.code"))

MAP_INCOMPLETE_PREFIX = "map incomplete"


def _refuse(reason: str) -> int:
    """Print one plain reason line to stderr and return the exit code 2 to use.

    Used for every refusal that happens before any command is attempted —
    a missing or incomplete map, a missing configured command, a row id
    that fails ``map.rowIdPattern`` — so nothing downstream mistakes a
    refusal for a result whose ``--json`` object it should try to parse.
    """
    print(f"adapter.py: {reason}", file=sys.stderr)
    return 2


def split_command(command: Any) -> Tuple[Optional[List[str]], Optional[str]]:
    """Split a configured command string into argv with ``shlex.split``.

    Returns ``(argv, None)`` on success or ``(None, reason)`` when the
    value is not a string, is empty, or is not valid shell-word syntax
    (an unclosed quote, for instance) — a misconfigured project, not a
    crash.
    """
    if not isinstance(command, str):
        return None, f"configured command is not a string: {command!r}"
    try:
        argv = shlex.split(command, posix=True)
    except ValueError as exc:
        return None, f"could not parse configured command {command!r}: {exc}"
    if not argv:
        return None, f"configured command is empty: {command!r}"
    return argv, None


def run_argv(argv: List[str], cwd: str, op: str, timeout: Optional[float] = None) -> Dict[str, Any]:
    """Run one child process and report the outcome; never raises.

    A missing or unrunnable executable (``OSError`` — most commonly
    ``FileNotFoundError``) is reported as exit 127 in the same shape a
    real exit code would be, so a caller building a ``checks``/``verify``
    sequence can treat "not found" exactly like any other non-zero exit
    for the purpose of deciding whether to keep going. A child still
    running after ``timeout`` seconds is stopped and reported as exit 124.
    """
    try:
        proc = subprocess.run(argv, shell=False, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"op": op, "argv": argv, "exit": 124, "stdout": "", "stderr": f"{argv[0]}: timed out after {timeout:g}s\n"}
    except OSError as exc:
        return {
            "op": op,
            "argv": argv,
            "exit": 127,
            "stdout": "",
            "stderr": f"executable not found: {argv[0]} ({exc})",
        }
    return {"op": op, "argv": argv, "exit": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def emit_single(result: Dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(result["stdout"])
        sys.stderr.write(result["stderr"])


def run_sequence(steps: List[Tuple[str, Any]], cwd: str, as_json: bool) -> Tuple[List[Dict[str, Any]], int]:
    """Run ``(op_label, command_string)`` pairs in order; stop at the first failure.

    A command that fails to split — not a string, empty, or bad shell-word
    syntax — is reported as its own step result with ``"exit": 2`` rather
    than raising, so one malformed entry in a project's ``map.checks``
    still stops the sequence cleanly instead of crashing this process.
    Streams each step's captured stdout/stderr as it finishes when
    ``as_json`` is false, so output appears in the order the steps
    actually ran. Returns ``(results, exit_code)``; ``exit_code`` is 0
    when ``steps`` is empty or every attempted step exited 0.
    """
    results: List[Dict[str, Any]] = []
    exit_code = 0
    for op_label, command in steps:
        argv, reason = split_command(command)
        if argv is None:
            result: Dict[str, Any] = {
                "op": op_label,
                "argv": [],
                "exit": 2,
                "stdout": "",
                "stderr": f"{op_label}: {reason}\n" if reason else "",
            }
        else:
            result = run_argv(argv, cwd, op_label)
        results.append(result)
        if not as_json:
            sys.stdout.write(result["stdout"])
            sys.stderr.write(result["stderr"])
        exit_code = result["exit"]
        if exit_code != 0:
            break
    return results, exit_code


def run_single_map_command(
    map_value: Optional[dict], key: str, op_label: str, extra_arg: Optional[str], cwd: str, as_json: bool,
    extra_args: Optional[List[str]] = None, optional_args: bool = False,
) -> int:
    """Resolve ``map.<key>``, append ``extra_arg`` (if any) as one argv element, or
    ``extra_args`` as that many elements, and run it. With ``optional_args``, a command
    that does not know them (argparse's "unrecognized arguments") runs again without."""
    if not isinstance(map_value, dict):
        return _refuse(f"no map configured (needed for '{op_label}')")
    command = map_value.get(key)
    if command is None or command == "":
        return _refuse(f"map.{key} is not configured")
    if not isinstance(command, str):
        return _refuse(f"map.{key} is not a string: {command!r}")
    argv, reason = split_command(command)
    if argv is None:
        return _refuse(reason or f"map.{key} could not be parsed")
    if extra_arg is not None:
        argv = argv + [extra_arg]
    base = argv
    if extra_args:
        argv = argv + list(extra_args)
    result = run_argv(argv, cwd, op_label)
    if (optional_args and extra_args and result["exit"] == 2
            and "unrecognized arguments" in result["stderr"] and extra_args[0] in result["stderr"]):
        # a reader from before 1.25: its counter id, never a refusal mid-arm
        note = (f"adapter.py: map.{key} takes no {extra_args[0]}, so {op_label} gives its own id; "
                "copy templates/starter-map/capability_find.py over the reader to take ids from the item\n")
        result = run_argv(base, cwd, op_label)
        result["stderr"] = note + result["stderr"]
    emit_single(result, as_json)
    return result["exit"]


def _row_id_refusal(map_value: dict, row_id: str) -> Optional[str]:
    """The refusal reason when ``row_id`` fails ``map.rowIdPattern``, else None."""
    pattern = map_value.get("rowIdPattern")
    if isinstance(pattern, str) and pattern:
        try:
            compiled = re.compile(pattern)
        except re.error:
            return None  # an invalid pattern cannot be checked against; fall through and run
        if compiled.fullmatch(row_id) is None:
            return f"row id {row_id!r} does not match map.rowIdPattern {pattern!r}"
    return None


def run_learn(map_value: Optional[dict], query_file: str, row_id: str, source: str, cwd: str, as_json: bool) -> int:
    if not isinstance(map_value, dict):
        return _refuse("no map configured (needed for 'learn')")
    reason = _row_id_refusal(map_value, row_id)
    if reason:
        return _refuse(reason)
    path = os.path.abspath(query_file)
    if not os.path.isfile(path):
        return _refuse(f"no such --query-file: {query_file}")
    return run_single_map_command(map_value, "learn", "learn", None, cwd, as_json,
                                  ["--query-file", path, "--row", row_id, "--source", source])


def run_refs_sync(map_value: Optional[dict], input_file: str, cwd: str, as_json: bool) -> int:
    if not isinstance(map_value, dict):
        return _refuse("no map configured (needed for 'refs-sync')")
    path = os.path.abspath(input_file)
    if not os.path.isfile(path):
        return _refuse(f"no such --input: {input_file}")
    return run_single_map_command(map_value, "refsSync", "refs-sync", None, cwd, as_json, ["--input", path])


def run_code(map_value: Optional[dict], row_id: str, cwd: str, as_json: bool) -> int:
    if not isinstance(map_value, dict):
        return _refuse("no map configured (needed for 'code')")
    reason = _row_id_refusal(map_value, row_id)
    if reason:
        return _refuse(reason)
    return run_single_map_command(map_value, "code", "code", row_id, cwd, as_json)


def run_row(map_value: Optional[dict], row_id: str, cwd: str, as_json: bool) -> int:
    if not isinstance(map_value, dict):
        return _refuse("no map configured (needed for 'row')")
    pattern = map_value.get("rowIdPattern")
    if isinstance(pattern, str) and pattern:
        try:
            compiled = re.compile(pattern)
        except re.error:
            compiled = None  # an invalid pattern cannot be checked against; fall through and run
        if compiled is not None and compiled.fullmatch(row_id) is None:
            return _refuse(f"row id {row_id!r} does not match map.rowIdPattern {pattern!r}")
    return run_single_map_command(map_value, "row", "row", row_id, cwd, as_json)


def run_checks(map_value: Optional[dict], cwd: str, as_json: bool) -> int:
    if not isinstance(map_value, dict):
        return _refuse("no map configured (needed for 'checks')")
    checks = map_value.get("checks")
    if checks is None:
        return _refuse("map.checks is not configured")
    if not isinstance(checks, list):
        return _refuse("map.checks is not a list")
    # None and "" are "unset" and skipped; anything else (a string, or a
    # wrong-typed value) is a step, so a wrong type is reported, not hidden.
    steps = [(f"checks[{i}]", command) for i, command in enumerate(checks) if command not in (None, "")]
    results, exit_code = run_sequence(steps, cwd, as_json)
    if as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    return exit_code


def run_verify(commands: Optional[dict], cwd: str, as_json: bool, only: Optional[List[str]] = None) -> int:
    commands = commands if isinstance(commands, dict) else {}
    names = [name for name in VERIFY_COMMAND_ORDER if not only or name in only]
    steps = [(name, commands.get(name)) for name in names]
    steps = [(name, command) for name, command in steps if command not in (None, "")]
    results, exit_code = run_sequence(steps, cwd, as_json)
    if as_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    return exit_code


def command_argv(command: Any) -> Tuple[Optional[List[str]], Optional[str]]:
    """A configured command given either as a string (split as
    ``split_command`` does) or as an argv array of non-empty strings, used
    as it stands. ``map.surfaces`` takes either form."""
    if isinstance(command, list):
        if command and all(isinstance(part, str) and part for part in command):
            return list(command), None
        return None, f"configured command is not a non-empty array of strings: {command!r}"
    return split_command(command)


def entry_points(text: str) -> List[str]:
    """The entry points a surfaces command printed, as map_report.py reads
    them: a leading byte-order mark dropped (PowerShell writes one), each
    line trimmed, deduplicated, blank and ``#`` lines left out."""
    seen: Dict[str, None] = {}
    for line in text.lstrip("\ufeff").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            seen.setdefault(line, None)
    return list(seen)


def run_surfaces(map_value: Optional[dict], cwd: str, as_json: bool, out: Optional[str]) -> int:
    """Run ``map.surfaces`` as argv and print, or write to ``out``, the
    entry points it lists."""
    if not isinstance(map_value, dict):
        return _refuse("no map configured (needed for 'surfaces')")
    command = map_value.get("surfaces")
    if command in (None, "", []):
        return _refuse("map.surfaces is not configured")
    argv, reason = command_argv(command)
    if argv is None:
        return _refuse(f"map.surfaces: {reason}")
    result = run_argv(argv, cwd, "surfaces", timeout=SURFACES_TIMEOUT)
    points = entry_points(result["stdout"])
    listing = "".join(point + "\n" for point in points)
    if result["exit"] == 0 and not points:
        result = dict(result, exit=1, stderr=result["stderr"] + "adapter.py: map.surfaces printed no entry points; "
                                                                "an empty list proves nothing\n")
    if result["exit"] == 0 and out is not None:
        try:
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(listing)
        except OSError as exc:
            return _refuse(f"cannot write --out {out!r}: {exc}")
        count = "1 entry point" if len(points) == 1 else f"{len(points)} entry points"
        result = dict(result, stderr=result["stderr"] + f"adapter.py: {count} written to {out}\n")
    shown = listing if result["exit"] == 0 and out is None else ""
    if as_json:
        print(json.dumps(dict(result, stdout=shown, entries=points), indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(shown)
        sys.stderr.write(result["stderr"])
    return result["exit"]


def _map_incomplete_reason(orientation: Dict[str, Any]) -> str:
    """orient's own 'map incomplete: missing …' warning, or a generic line."""
    for warning in orientation.get("warnings") or []:
        if isinstance(warning, str) and warning.startswith(MAP_INCOMPLETE_PREFIX):
            return warning
    return MAP_INCOMPLETE_PREFIX


def _display_command(value: Any) -> str:
    return value if isinstance(value, str) else f"{value!r} (not a string)"


def _display_argv_or_command(value: Any) -> str:
    argv, _reason = command_argv(value) if isinstance(value, list) else (None, None)
    if argv is not None:
        return " ".join(shlex.quote(part) for part in argv)
    if isinstance(value, list):
        return f"{value!r} (not an array of strings)"
    return _display_command(value)


def show_commands(map_value: Optional[dict], commands: Optional[dict], orientation: Optional[Dict[str, Any]] = None) -> None:
    """Print every configured command, one per line, as ``<label>: <command>``. Runs nothing.

    A map orient reports as incomplete is still printed — the person can
    see what they wrote — followed by one ``#`` line naming the missing
    keys, so the listing never reads as runnable when it is not. With
    nothing configured at all, one ``#`` line says so instead of printing
    nothing.
    """
    lines: List[str] = []
    if isinstance(map_value, dict):
        for key, label in _MAP_COMMAND_LABELS:
            command = map_value.get(key)
            if command not in (None, ""):
                lines.append(f"{label}: {_display_command(command)}")
        checks = map_value.get("checks")
        if isinstance(checks, list):
            for i, command in enumerate(checks):
                if command not in (None, ""):
                    lines.append(f"map.checks[{i}]: {_display_command(command)}")
        surfaces = map_value.get("surfaces")
        if surfaces not in (None, "", []):
            lines.append(f"map.surfaces: {_display_argv_or_command(surfaces)}")
        if orientation is not None and not orientation.get("mapUsable"):
            lines.append(f"# {_map_incomplete_reason(orientation)} — map operations refuse until the config is complete")
    if isinstance(commands, dict):
        for name in VERIFY_COMMAND_ORDER:
            command = commands.get(name)
            if command not in (None, ""):
                lines.append(f"commands.{name}: {_display_command(command)}")
    sibling = orientation.get("sibling") if orientation is not None else None
    if isinstance(sibling, dict):
        where = sibling["path"] if sibling.get("checkout") else f"{sibling['path']}, no checkout there"
        for key in SIBLING_OPERATIONS:
            lines.append(f"sibling.{key}: {_display_command(sibling[key])}")
        lines.append(f"# sibling map of {sibling['repo']}: runs in {where}, read-only (find and row only)")
    if not lines:
        lines.append("# nothing configured: no map and no verify commands")
    for line in lines:
        print(line)


def read_query_file(path: str) -> Tuple[Optional[str], Optional[str]]:
    """The query text in ``path`` (``-`` = stdin), or ``(None, reason)``.

    Read as UTF-8 tolerating a BOM. Only trailing line terminators are
    dropped — a file written by an editor or a Write tool ends in one,
    and that newline is the file's, not the query's. Everything else,
    quotes and shell metacharacters included, is kept verbatim.
    """
    try:
        if path == "-":
            text = sys.stdin.read()
        else:
            # newline="" keeps an interior CRLF as written; universal-newlines
            # mode (newline=None) would rewrite it to LF before the child saw it.
            with open(path, "r", encoding="utf-8-sig", newline="") as fh:
                text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"cannot read --query-file {path!r}: {exc}"
    return text.rstrip("\r\n"), None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adapter.py",
        description=(
            "Run a project's configured map/verify commands without ever composing a "
            "shell string from configuration plus user-supplied text."
        ),
    )
    parser.add_argument("--cwd", default=None, help="project root to resolve config against (default: current directory)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="print a machine-readable result instead of streaming the child's own output",
    )
    subparsers = parser.add_subparsers(dest="op", required=True,
                                       metavar="{find,row,next-id,learn,refs-sync,code,checks,verify,surfaces,show}")

    find_parser = subparsers.add_parser("find", help="run map.find with a query appended as one argument")
    find_parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="search text; passed verbatim as one argv element, never interpolated",
    )
    find_parser.add_argument(
        "--query-file",
        metavar="PATH",
        default=None,
        help=(
            "read the query from this file ('-' for stdin) instead of the positional; "
            "use it whenever the text may contain quotes, so it never passes through a shell"
        ),
    )

    row_parser = subparsers.add_parser("row", help="run map.row with a row id appended as one argument")
    row_parser.add_argument("id", help="row id; checked against map.rowIdPattern before anything runs")

    next_parser = subparsers.add_parser("next-id", help="run map.nextId; --from ITEM passes the work item on")
    next_parser.add_argument("--from", dest="source", default=None, metavar="ITEM",
                             help="issue:<n>, pr:<n> or linear:<TEAM>-<n>, appended as `--from ITEM` (the "
                                  "starter reader then prints CAP-i<n>a, CAP-p<n>a or CAP-ENG-<n>a, or the next free letters)")
    learn_parser = subparsers.add_parser("learn", help="run map.learn: record the words find missed a row by")
    learn_parser.add_argument("--query-file", required=True, metavar="PATH", help="the ask, in a file")
    learn_parser.add_argument("--row", required=True, metavar="ID", help="the row it belongs to")
    learn_parser.add_argument("--source", required=True,
                              help="person, issue:<owner>/<repo>#<n> or pr:<owner>/<repo>#<n>")
    refs_parser = subparsers.add_parser("refs-sync", help="run map.refsSync over merged pull requests")
    refs_parser.add_argument("--input", required=True, metavar="PATH",
                             help="JSON list of merged pull requests: {repo, number, title, body, merged}")
    code_parser = subparsers.add_parser("code", help="run map.code: the local files a row's cited tests import")
    code_parser.add_argument("id", help="row id; checked against map.rowIdPattern before anything runs")
    subparsers.add_parser("checks", help="run each map.checks command in order; stop at the first failure")
    verify_parser = subparsers.add_parser(
        "verify", help="run commands.typeCheck, commands.test, commands.lint in order, skipping unset ones"
    )
    verify_parser.add_argument(
        "--only",
        action="append",
        choices=list(VERIFY_COMMAND_ORDER),
        default=None,
        metavar="{typeCheck,test,lint}",
        help="run only the named command(s), in the configured order; repeatable",
    )
    surfaces_parser = subparsers.add_parser(
        "surfaces", help="run map.surfaces with no shell and print the code's entry points, one per line"
    )
    surfaces_parser.add_argument(
        "--out", metavar="PATH", default=None,
        help="write the entry points to this file instead of printing them (for map_report.py --surfaces)",
    )
    subparsers.add_parser("show", help="print every configured command, one per line; run nothing")

    return parser


def dispatch(args: argparse.Namespace, cwd: str) -> int:
    orientation = orient.build_orientation(None, cwd)
    map_value = orientation.get("map")
    commands = orientation.get("commands")

    if args.op == "show":
        show_commands(map_value, commands, orientation)
        return 0

    sibling = orientation.get("sibling")
    if args.op in MAP_OPERATIONS and isinstance(sibling, dict):
        # the rows live in a sibling's map, which this project only reads:
        # find and row run there, nothing else does, and nothing writes there
        if args.op not in SIBLING_OPERATIONS:
            return _refuse(f"the map lives in {sibling['repo']}, read-only: only find and row run there, "
                           f"not '{args.op}'")
        if not sibling.get("checkout"):
            return _refuse(f"no checkout of {sibling['repo']} at {sibling['path']} (sibling.path): "
                           f"its rows cannot be read here (needed for '{args.op}')")
        if args.op == "row" and isinstance(args.id, str) and args.id.startswith("-"):
            # no rowIdPattern guards the sibling's reader: never hand it an option
            return _refuse(f"row id {args.id!r} starts with '-': not a row id")
        map_value = {"find": sibling["find"], "row": sibling["row"]}
        cwd = sibling["dir"]
    elif args.op in MAP_OPERATIONS and isinstance(map_value, dict) and not orientation.get("mapUsable"):
        # orient's mapUsable is the one source of "is a map configured":
        # a partial map is treated as no map, and the person is told
        # which keys are missing rather than watching part of it run.
        return _refuse(f"{_map_incomplete_reason(orientation)} — treated as no map (needed for '{args.op}')")

    if args.op == "find":
        if args.query is not None and args.query_file is not None:
            return _refuse("find takes a query or --query-file, not both")
        if args.query is None and args.query_file is None:
            return _refuse("find needs a query or --query-file")
        query = args.query
        if args.query_file is not None:
            query, reason = read_query_file(args.query_file)
            if query is None:
                return _refuse(reason or "cannot read --query-file")
        return run_single_map_command(map_value, "find", "find", query, cwd, args.json)
    if args.op == "row":
        return run_row(map_value, args.id, cwd, args.json)
    if args.op == "next-id":
        if args.source is not None and not re.fullmatch(
                r"(?:issue|pr):0*[1-9]\d*|linear:[A-Za-z][A-Za-z0-9]+-0*[1-9]\d*", args.source):
            return _refuse(f"--from {args.source!r} is not issue:<n>, pr:<n> or linear:<TEAM>-<n>")
        source = args.source
        pattern = map_value.get("rowIdPattern") if isinstance(map_value, dict) else None
        if source and isinstance(pattern, str) and pattern:
            try:
                kind, _, item = source.partition(":")
                team, _, number = item.rpartition("-")
                own = (f"CAP-{team.upper()}-{int(number)}a" if kind == "linear"
                       else f"CAP-{'i' if kind == 'issue' else 'p'}{int(item)}a")
                # the id this item would take: a pattern that has no room for it (CAP-ENG-4a
                # under ^CAP-(\d+|[ip]\d+[a-z]{1,2})$, or any id under 1.24's ^CAP-\d+$)
                # gets the counter id
                takes_tracker_ids = bool(re.fullmatch(pattern, own))
            except re.error:
                takes_tracker_ids = True  # orient reports the bad pattern; let the reader decide
            if not takes_tracker_ids:
                # a map set up before tracker ids: its counter id, never a refusal mid-arm
                print(f"adapter.py: map.rowIdPattern takes no id such as {own}, so next-id gives the counter id; "
                      "widen it (references/config.md) and update the reader to take ids from --from",
                      file=sys.stderr)
                source = None
        return run_single_map_command(map_value, "nextId", "next-id", None, cwd, args.json,
                                      ["--from", source] if source else None, optional_args=True)
    if args.op == "learn":
        return run_learn(map_value, args.query_file, args.row, args.source, cwd, args.json)
    if args.op == "refs-sync":
        return run_refs_sync(map_value, args.input, cwd, args.json)
    if args.op == "code":
        return run_code(map_value, args.id, cwd, args.json)
    if args.op == "checks":
        return run_checks(map_value, cwd, args.json)
    if args.op == "verify":
        return run_verify(commands, cwd, args.json, only=args.only)
    if args.op == "surfaces":
        return run_surfaces(map_value, cwd, args.json, args.out)
    return _refuse(f"unknown operation: {args.op}")  # pragma: no cover - argparse prevents this


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.cwd) if args.cwd else os.path.abspath(os.getcwd())
    if not os.path.isdir(cwd):
        return _refuse(f"no such directory: {cwd}")

    try:
        return dispatch(args, cwd)
    except Exception as exc:  # pragma: no cover - last-resort guard, never a traceback for the caller
        return _refuse(f"internal error: {exc}")


if __name__ == "__main__":
    sys.exit(main())
