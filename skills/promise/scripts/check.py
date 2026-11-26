#!/usr/bin/env python3
"""One local command for what the promise GitHub Action checks.

    python3 check.py
    python3 check.py --base origin/main
    python3 check.py --junit test-results/ --fail-on-orphans
    python3 check.py --surfaces-cmd "node tools/list-entry-points.mjs" --fail-on-unmapped
    python3 check.py --docs-home docs/designs --json

Some teams cannot run the Action, and everyone wants the answer before a
push. This runs the same checks from the project root, each one a sibling
script beside this file run with this interpreter, or a command the config
names (``map.checks``, ``map.surfaces``), always as an argv list -- never a
shell string:

1. **lint** -- ``lint_outcome.py <docsHome>``: the shape of every outcome
   doc. Skipped with ``--no-lint``, or when docsHome is unknown or is not a
   folder.
2. **§0** -- ``diff_outcome.py --dir <docsHome> --base <REF>``: §0 of a
   ratified doc changed only in its tags and count, or went back to draft.
   Skipped without ``--base``, or when the docs folder does not exist.
3. **gate** -- ``bridge_validate.py <doc>`` for each outcome doc at
   ``shipped`` with a §6 line that no red run and no ``Kill:`` line covers
   (a line went red when the doc has a real ``Red gate:`` line and the line
   is not in ``Filed without red run:``): such a line needs a row with
   ``origin: backfill`` and ``verdict: proven`` (``SHIPPED_WITHOUT_GATE``).
   The lint sees only a line with no ``Row`` (``SHIPPED_NEEDS_GATE``). The
   step fails when any run exits non-zero. It needs no test run, and it
   runs ``map.row`` only for such a doc, so ``--no-map`` does not skip it
   and the Action runs it. Skipped when every shipped doc's lines are
   covered by a red run or a kill; it fails when the config has no map
   (``null`` or ``false``), since no row can then be proven, when the map
   is incomplete, or when ``--config`` names another file than the
   project's own config, which ``bridge_validate.py`` reads.
4. **checks** -- the config's ``map.checks``, the project's own checks of
   its map (the starter reader's ``--check``: duplicate ids, a doc that
   cannot be read, a malformed ``leftOut`` entry), each run as
   ``adapter.py checks`` runs it: an argv line with no shell, in order,
   stopping at the first non-zero exit, which fails the step. On a merge
   commit the starter reader also finds a row or ``leftOut`` entry the merge
   lost. Skipped with ``--no-map`` (unless ``--map-checks``, as the Action
   passes: these checks need no test run), with no usable map, or when ``map.checks`` is absent or
   empty; a ``map.checks`` that is not a list fails. A config that sets
   ``"map": false`` (no map, on purpose) skips this step and the map step
   with that reason.
5. **surfaces** -- the command that prints the code's entry points, one
   per line: ``--surfaces-cmd``, else the config's ``map.surfaces`` (a
   command string, split like the other map commands, or an argv array).
   It runs from the project root as an argv list, never through a shell,
   and is stopped after five minutes. A non-zero exit, a timeout or an
   empty list fails the step, quoting the command's last stderr line.
   Skipped with ``--no-map`` or when there is no command -- unless
   ``--fail-on-unmapped`` or ``map.requireHomes`` asks for the check, which
   then fails for want of one.
6. **map** -- ``map_report.py --map <map file> --config <config> --junit …
   --strict --surfaces <list>``: the map joined to a test run and to the
   entry-point list. It runs when the config's map is usable (orient's
   ``mapUsable``) and there is a run -- the ``--junit`` paths, else the
   config's ``map.junit`` -- or an entry-point list from step 5. Skipped
   with ``--no-map``, with no map, or with neither; a ``map.junit`` path
   that does not exist yet means those tests have not run, so it is left
   out, and named in the step's reason, until it does. Asking for a run or
   a list (``--junit``, ``--surfaces-cmd``, or ``map.junit`` /
   ``map.surfaces`` in the config) with no usable map fails the step
   instead: the report cannot run. ``--fail-on-orphans``,
   ``--fail-on-skipped`` and ``--fail-on-unmapped`` (with a list) are passed through;
   ``map.requireHomes: true`` turns on the orphan and entry-point gates.
   The orphan and skip checks never pass for want of a run: with
   ``--fail-on-orphans``, ``--fail-on-skipped`` or ``map.requireHomes`` and
   no run to join, the step fails and says which paths it looked for.

docsHome and the map are resolved from the project config exactly as
``orient.py`` resolves them -- its functions, imported, not a second copy.
``--docs-home`` overrides docsHome; ``--config`` names a config file other
than the one orient would find under the project root. Every relative path
-- ``--docs-home``, ``--junit``, and the config's own -- is read from the
project root (``--cwd``), not from the shell's folder.

**The map file.** ``map.file`` when the config sets it. Otherwise, when
``map.find`` is the starter reader -- ``python3 <dir>/capability_find.py``,
optionally with ``--map <path>`` -- the map is ``<dir>/map.json`` (or that
path), which is where ``start_map.py`` puts it. Any other ``find`` names a
reader this script cannot see into, so the map step fails and says to set
``map.file``.

First, one ``promise check: warning: <text>`` line for each of orient's
warnings about the config (a key it does not know, a path that escapes the
project, a value of the wrong type): a config slip can turn a gate off, and
a green run must not hide it. Then one such line for each path on an
outcome doc's ``Supersedes:`` line that still exists: the doc that
replaced it deletes it in the same commit, or cuts it to one line that
names the doc (``modes/backfill.md``, ``modes/merge.md``). A folded doc
at ``superseded-by`` is not a copy. It is a warning, never a failure: a
human may keep a file on purpose. A ``map.requireHomes`` that is not ``true`` or
``false`` fails the map step. Then each step prints its own output (the
surfaces step only its stderr, not the list), then one line,
``promise check: <step>: ok|failed|skipped (<reason>)``, and a last line
counts the steps. Under GitHub Actions (``GITHUB_ACTIONS=true``) each
step's output is folded into a log group. ``--json`` prints one object
instead: ``{"ok", "cwd", "docsHome", "steps": [{"step", "status",
"reason", "argv", "exit", "output", "stderr"}], "warnings"}``, each script
run with its own ``--json`` and its output parsed where it is JSON; the
checks step's ``argv`` lists each command's argv and its ``output`` is
adapter.py's result for each (``op``, ``argv``, ``exit``, ``stdout``,
``stderr``); the gate step's ``argv`` and ``output`` are lists too, one
entry for each doc it checks; the surfaces step's ``output`` is its list
of entry points.

Exit 0 when every step passed or was skipped; 1 when any failed; 2 on a
usage error -- an unknown flag, a ``--cwd`` that is not a directory, or a
``--config`` that cannot be read or is not a JSON object. Stdlib only; no
network (the §0 check reads the base ref from the local git repository, so
fetch it first).
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import adapter  # noqa: E402  (sibling-script import; see path insert above)
import lint_outcome  # noqa: E402
import orient  # noqa: E402

STARTER_READER = "capability_find.py"
PYTHON_RE = re.compile(r"^(?:python(?:3(?:\.\d+)?)?|py)(?:\.exe)?$", re.IGNORECASE)
OK, FAILED, SKIPPED = "ok", "failed", "skipped"
SURFACES_TIMEOUT = 300  # seconds
NO_MAP_ON_PURPOSE = "map is false: this project keeps no map, on purpose"
SUPERSEDES_RE = re.compile(r"^Supersedes:\s*(.*?)\s*$")
LINK_TARGET_RE = re.compile(r"\]\(([^)\s]+)\)")
NO_SUPERSEDES = {"", "—", "–", "-", "none", "n/a"}


class UsageError(Exception):
    pass


def load_project_config(cwd: str, config_arg: Optional[str]) -> Tuple[Optional[dict], Optional[str], List[str]]:
    """The config, its path, and orient's warnings about it: ``--config`` when
    given (it must be a readable JSON object), else the one orient finds."""
    if config_arg is None:
        raw, path, warnings = orient.load_config(cwd)
        return raw, (path if raw is not None else None), warnings
    path = os.path.abspath(config_arg)
    try:
        raw = json.loads(orient.read_text_tolerant(path))
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read --config {config_arg}: {exc}")
    if not isinstance(raw, dict):
        raise UsageError(f"--config {config_arg} is not a JSON object")
    return raw, path, []


def map_file(map_value: Dict[str, Any]) -> Tuple[Optional[str], str]:
    """The map's JSON file, project-relative, and how it was found -- or
    ``(None, reason)`` when neither ``map.file`` nor the starter-reader rule
    names one."""
    value = map_value.get("file")
    if isinstance(value, str) and value.strip():
        if orient._path_escapes(value):
            return None, "map.file escapes the project"
        return value.replace("\\", "/"), "map.file"
    argv, _reason = adapter.split_command(map_value.get("find"))
    rest = list(argv or [])
    if rest and PYTHON_RE.match(posixpath.basename(rest[0].replace("\\", "/"))):
        rest = rest[1:]
        if rest and rest[0] == "-3":  # py -3
            rest = rest[1:]
    if rest and posixpath.basename(rest[0].replace("\\", "/")) == STARTER_READER:
        script = rest[0].replace("\\", "/")
        if len(rest) == 1:
            return posixpath.join(posixpath.dirname(script), "map.json"), "beside the starter reader"
        if len(rest) == 3 and rest[1] == "--map" and not orient._path_escapes(rest[2]):
            return rest[2].replace("\\", "/"), "the starter reader's --map"
    return None, (
        "map.file is not set and map.find is not the starter reader "
        "(python3 <dir>/capability_find.py); set map.file"
    )


def config_junit(map_value: Optional[dict]) -> List[str]:
    """``map.junit`` as a list of project-relative paths; entries of the
    wrong type, escaping the project or holding shell syntax are left out
    (orient warns)."""
    raw = map_value.get("junit") if isinstance(map_value, dict) else None
    entries = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else []
    return [e for e in entries
            if isinstance(e, str) and e and not orient._path_escapes(e) and not orient._path_unsafe(e)]


def run_script(script: str, args: List[str], cwd: str, as_json: bool) -> Dict[str, Any]:
    """Run one sibling script from the project root; never raises."""
    argv = [sys.executable, os.path.join(_SCRIPTS_DIR, script), *args] + (["--json"] if as_json else [])
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env
        )
    except OSError as exc:
        return {"argv": argv, "exit": None, "stdout": "", "stderr": f"cannot run {script}: {exc}\n"}
    return {"argv": argv, "exit": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def run_command(argv: List[str], cwd: str, timeout: float = SURFACES_TIMEOUT) -> Dict[str, Any]:
    """Run one configured command from the project root, as argv with no
    shell, stopped after ``timeout`` seconds; never raises."""
    try:
        proc = subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return {"argv": argv, "exit": None, "stdout": "", "stderr": f"{argv[0]}: timed out after {timeout:g}s\n"}
    except OSError as exc:
        return {"argv": argv, "exit": None, "stdout": "", "stderr": f"cannot run {argv[0]}: {exc}\n"}
    return {"argv": argv, "exit": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    last = lines[-1] if lines else ""
    return last if len(last) <= 200 else last[:197] + "..."


def require_homes(map_value: Optional[dict]) -> bool:
    return isinstance(map_value, dict) and map_value.get("requireHomes") is True


def step(name: str, status: str, reason: str, run: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"step": name, "status": status, "reason": reason, "run": run}


def ran(name: str, what: str, run: Dict[str, Any]) -> Dict[str, Any]:
    """A step whose script ran: ok on exit 0, failed on anything else."""
    if run["exit"] == 0:
        return step(name, OK, what, run)
    code = "did not start" if run["exit"] is None else f"exit {run['exit']}"
    return step(name, FAILED, f"{what}: {code}", run)


def supersedes_paths(value: str) -> List[str]:
    """The paths on a ``Supersedes:`` line: comma-separated, each bare, in
    backticks or a Markdown link. ``—`` and a name with no ``/`` and no
    file extension are not paths."""
    paths = []
    for part in value.split(","):
        token = part.strip()
        link = LINK_TARGET_RE.search(token)
        if link:
            token = link.group(1)
        token = token.strip().strip("`").strip()
        if token.lower() in NO_SUPERSEDES:
            continue
        if "/" not in token and not os.path.splitext(token)[1]:
            continue
        paths.append(token)
    return paths


def _left_behind(cwd: str, doc: str, path: str) -> Optional[str]:
    """Why a superseded path still counts as a copy of the doc, or None.

    The path is read from the project root, then from the doc's folder. A
    file that is gone, that is outside the project, that is an outcome doc
    at ``superseded-by`` (``modes/merge.md`` keeps one on the user's no), or
    that holds one line naming the doc (a pointer) is fine."""
    root = os.path.realpath(cwd)
    for base in (cwd, os.path.dirname(doc)):
        full = os.path.realpath(os.path.join(base, path))
        if full == os.path.realpath(doc) or not (full + os.sep).startswith(root + os.sep):
            continue
        if os.path.isdir(full):
            return "still exists, as a folder"
        if not os.path.isfile(full):
            continue
        try:
            lines = lint_outcome.read_text_tolerant(full).splitlines()
        except (OSError, UnicodeDecodeError):
            return "still exists and cannot be read"
        text = [line.strip() for line in lines if line.strip()]
        status = next((lint_outcome.STATUS_RE.match(line) for line in text if line.startswith("Status:")), None)
        if status and status.group(1).startswith("superseded-by"):
            return None
        if len(text) == 1 and os.path.basename(doc) in text[0]:
            return None
        if len(text) == 1:
            return f"still exists, and its one line does not name {os.path.basename(doc)}"
        return f"still exists ({len(text)} lines)"
    return None


def supersedes_warnings(cwd: str, docs_home: Optional[str]) -> List[str]:
    """One warning for each path on an outcome doc's ``Supersedes:`` line
    that is still more than a pointer (``_left_behind``): the doc that
    replaced it deletes it in its own commit, or cuts it to one line that
    names the doc (``modes/backfill.md``, ``modes/merge.md``). A warning,
    never a failure: a human may keep a file on purpose."""
    if not docs_home or not os.path.isdir(os.path.join(cwd, docs_home)):
        return []
    warnings = []
    for doc in lint_outcome.collect_directory_docs(os.path.join(cwd, docs_home)):
        try:
            lines = lint_outcome.unfenced(lint_outcome.read_text_tolerant(doc).splitlines())
        except (OSError, UnicodeDecodeError):
            continue  # the lint step reports the doc as UNREADABLE
        for line in lines:
            if line.startswith("## "):
                break
            m = SUPERSEDES_RE.match(line)
            if not m:
                continue
            rel = os.path.relpath(doc, cwd).replace(os.sep, "/")
            for path in supersedes_paths(m.group(1)):
                why = _left_behind(cwd, doc, path)
                if why:
                    warnings.append(
                        f"{rel}: Supersedes: names {path}, which {why}: delete it in the doc's "
                        f"commit, or cut it to one line that names {os.path.basename(doc)}"
                    )
            break
    return warnings


def lint_step(args: argparse.Namespace, cwd: str, docs_home: Optional[str]) -> Dict[str, Any]:
    if args.no_lint:
        return step("lint", SKIPPED, "--no-lint")
    if not docs_home:
        return step("lint", SKIPPED, "no docs home: pass --docs-home or set docsHome")
    if not os.path.isdir(os.path.join(cwd, docs_home)):
        return step("lint", SKIPPED, f"no folder {docs_home}")
    return ran("lint", docs_home, run_script("lint_outcome.py", [docs_home, "--no-summary"], cwd, args.json))


def section0_step(args: argparse.Namespace, cwd: str, docs_home: Optional[str]) -> Dict[str, Any]:
    if not args.base:
        return step("§0", SKIPPED, "no --base")
    if not docs_home or not os.path.isdir(os.path.join(cwd, docs_home)):
        return step("§0", SKIPPED, f"no folder {docs_home}" if docs_home else "no docs home")
    run = run_script("diff_outcome.py", ["--dir", docs_home, "--base", args.base], cwd, args.json)
    return ran("§0", f"{docs_home} against {args.base}", run)


def gate_skipped_docs(cwd: str, docs_home: str) -> List[str]:
    """The outcome docs under ``docs_home`` at ``shipped`` with a §6 line no
    red run and no ``Kill:`` line covers, project-relative: the docs whose
    proof must come from proven backfilled rows."""
    found = []
    for doc in lint_outcome.collect_directory_docs(os.path.join(cwd, docs_home)):
        try:
            lines = lint_outcome.read_text_tolerant(doc).splitlines()
        except (OSError, UnicodeDecodeError):
            continue  # the lint step reports the doc as UNREADABLE
        if lint_outcome.get_status(lines) == "shipped" and (
                lint_outcome.gate_uncovered_rows(lines)
                or not (lint_outcome.red_gate_line(lines)[0] or lint_outcome.parse_acceptance_rows(lines))):
            found.append(os.path.relpath(doc, cwd).replace(os.sep, "/"))
    return found


def gate_step(args: argparse.Namespace, cwd: str, docs_home: Optional[str], config_path: Optional[str],
              map_value: Optional[dict], map_usable: bool, warnings: List[str]) -> Dict[str, Any]:
    """Run ``bridge_validate.py`` on each shipped doc with a §6 line no red
    run and no ``Kill:`` line covers. Each such line must cite a row with
    ``origin: backfill`` and ``verdict: proven`` (``SHIPPED_WITHOUT_GATE``);
    the lint sees only a line with no ``Row`` (``SHIPPED_NEEDS_GATE``). The
    step needs no test run and runs ``map.row`` only for such a doc, so
    ``--no-map`` does not skip it, and the Action runs it. With no map
    (``map`` null or ``false``) no row can be a proven backfilled row, so
    such a doc fails the step, also when its §6 lines carry typed ``Row``
    cells that the lint accepts."""
    if not docs_home or not os.path.isdir(os.path.join(cwd, docs_home)):
        return step("gate", SKIPPED, f"no folder {docs_home}" if docs_home else "no docs home")
    docs = gate_skipped_docs(cwd, docs_home)
    if not docs:
        return step("gate", SKIPPED, "no shipped doc has a §6 line that needs a proven backfilled row")
    count = "1 shipped doc" if len(docs) == 1 else f"{len(docs)} shipped docs"
    what = f"{count} with a §6 line no red run or Kill line covers"
    if map_value is None or map_value is False:
        why = "no map configured" if map_value is None else NO_MAP_ON_PURPOSE
        return step("gate", FAILED, f"{what}, and {why}: no row can be a proven backfilled row, "
                                    "so each such line needs a red run or a Kill line")
    if not map_usable:
        reason = next((w for w in warnings if w.startswith("map incomplete")), "map incomplete")
        return step("gate", FAILED, f"{what}, and {reason}: its rows cannot be read")
    own_config = orient.load_config(cwd)[1]
    if config_path and (own_config is None or os.path.realpath(config_path) != os.path.realpath(own_config)):
        return step("gate", FAILED, f"{what}: bridge_validate.py reads only the project's own config, "
                                    "not --config, so its rows cannot be read against this map")
    runs = [run_script("bridge_validate.py", [doc], cwd, args.json) for doc in docs]
    run = {
        "argv": [r["argv"] for r in runs],
        "exit": next((r["exit"] for r in runs if r["exit"] != 0), 0),
        "stdout": "".join(r["stdout"] for r in runs),
        "stderr": "".join(r["stderr"] for r in runs),
        "output": [_parsed(r["stdout"]) for r in runs],
    }
    failed = [doc for doc, r in zip(docs, runs) if r["exit"] != 0]
    if not failed:
        return step("gate", OK, f"{what}: each such line cites a proven backfilled row", run)
    return step("gate", FAILED, f"{', '.join(failed)}: bridge_validate.py found an error", run)


def checks_step(args: argparse.Namespace, cwd: str, map_value: Optional[dict], map_usable: bool,
                warnings: List[str]) -> Dict[str, Any]:
    """Run ``map.checks`` -- the project's own checks of its map -- through
    adapter.py's sequence: each an argv line with no shell, in order,
    stopping at the first that fails."""
    if args.no_map and not getattr(args, "map_checks", False):
        return step("checks", SKIPPED, "--no-map")
    if map_value is None or map_value is False:
        return step("checks", SKIPPED, "no map configured" if map_value is None else NO_MAP_ON_PURPOSE)
    if not map_usable:
        return step("checks", SKIPPED, next((w for w in warnings if w.startswith("map incomplete")), "map incomplete"))
    checks = map_value.get("checks")
    if checks is None:
        return step("checks", SKIPPED, "map.checks is not configured")
    if not isinstance(checks, list):
        return step("checks", FAILED, "map.checks is not a list of commands")
    commands = [(f"map.checks[{i}]", c) for i, c in enumerate(checks) if c not in (None, "")]
    if not commands:
        return step("checks", SKIPPED, "map.checks is empty")
    results, code = adapter.run_sequence(commands, cwd, as_json=True)
    run = {
        "argv": [r["argv"] for r in results],
        "exit": code,
        "stdout": "".join(r["stdout"] for r in results),
        "stderr": "".join(r["stderr"] for r in results),
        "output": results,
    }
    if code == 0:
        count = "1 command" if len(results) == 1 else f"{len(results)} commands"
        return step("checks", OK, f"{count} from map.checks", run)
    return step("checks", FAILED, f"{results[-1]['op']} exited {code}", run)


def surfaces_command(args: argparse.Namespace, map_value: Optional[dict]) -> Tuple[Optional[Any], str]:
    """The configured entry-point command and where it came from, or
    ``(None, "")`` when there is none."""
    if args.surfaces_cmd is not None:
        return args.surfaces_cmd, "--surfaces-cmd"
    if isinstance(map_value, dict) and map_value.get("surfaces") is not None:
        return map_value["surfaces"], "map.surfaces"
    return None, ""


def surfaces_step(args: argparse.Namespace, cwd: str, map_value: Optional[dict],
                  folder: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """Run the entry-point command; on success, write what it printed to a
    file in ``folder`` for the map step and return that file's path."""
    if args.no_map:
        return step("surfaces", SKIPPED, "--no-map"), None
    command, source = surfaces_command(args, map_value)
    if command is None:
        # a project with "map": false has no map.surfaces to set
        how = ("pass --surfaces-cmd (map is false, so there is no map.surfaces)" if map_value is False
               else "pass --surfaces-cmd or set map.surfaces")
        if args.fail_on_unmapped:
            return step("surfaces", FAILED, f"--fail-on-unmapped needs an entry-point command: {how}"), None
        if require_homes(map_value):
            return step("surfaces", FAILED, "map.requireHomes needs map.surfaces, a command that "
                                            "prints the code's entry points"), None
        return step("surfaces", SKIPPED, f"no entry-point command: {how}"), None
    argv, problem = (adapter.split_command(command) if source == "--surfaces-cmd"
                     else adapter.command_argv(command))
    if argv is None:
        return step("surfaces", FAILED, f"{source}: {problem}"), None
    run = run_command(argv, cwd)
    points = adapter.entry_points(run["stdout"])
    run = dict(run, stdout="", output=points)  # the list goes to the report, not the log
    stderr = _last_line(run["stderr"])
    quoted = f": {json.dumps(stderr, ensure_ascii=False)}" if stderr else " (no stderr)"
    if run["exit"] is None:
        return step("surfaces", FAILED, f"{source} did not finish{quoted}", run), None
    if run["exit"] != 0:
        return step("surfaces", FAILED, f"{source} exited {run['exit']}{quoted}", run), None
    if not points:
        return step("surfaces", FAILED, f"{source} printed no entry points; an empty list proves nothing", run), None
    path = os.path.join(folder, "entry-points.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(points) + "\n")
    count = "1 entry point" if len(points) == 1 else f"{len(points)} entry points"
    return step("surfaces", OK, f"{count} from {source}", run), path


def map_step(args: argparse.Namespace, cwd: str, config_path: Optional[str],
             map_value: Optional[dict], map_usable: bool, warnings: List[str],
             surfaces_path: Optional[str] = None) -> Dict[str, Any]:
    if args.no_map:
        return step("map", SKIPPED, "--no-map")
    configured = config_junit(map_value)
    wanted = bool(args.junit or configured or surfaces_command(args, map_value)[0] is not None)
    if map_value is None or map_value is False:
        why = "" if map_value is None else f" ({NO_MAP_ON_PURPOSE})"
        for flag, value in (("--junit", args.junit), ("--surfaces-cmd", args.surfaces_cmd)):
            if value:
                return step("map", FAILED, f"{flag} needs a map, and the config has none{why}")
        return step("map", SKIPPED, "no map configured" if map_value is None else NO_MAP_ON_PURPOSE)
    if not map_usable:
        reason = next((w for w in warnings if w.startswith("map incomplete")), "map incomplete")
        return step("map", FAILED if wanted else SKIPPED, reason)
    homes = map_value.get("requireHomes")
    if homes is not None and not isinstance(homes, bool):
        return step("map", FAILED, f"map.requireHomes is {homes!r}, not true or false; "
                                   "the gate it names cannot be read as on or off")
    junit: List[str] = []
    missing: List[str] = []
    no_run = ""
    if args.junit:
        junit = [os.path.join(cwd, p) for p in args.junit]  # like every other path: from the project root
    elif configured:
        junit = [p for p in configured if os.path.exists(os.path.join(cwd, p))]
        missing = [p for p in configured if p not in junit]
        if not junit:
            no_run = f"no JUnit results at map.junit yet ({', '.join(configured)}); run the tests first"
    else:
        no_run = "no test run: pass --junit or set map.junit"
    strict_homes = require_homes(map_value)
    # the orphan gate asked for, and no run to check it against: fail, never pass quietly
    unchecked = ""
    if not junit and (args.fail_on_orphans or strict_homes or args.fail_on_skipped):
        gate = ("--fail-on-orphans" if args.fail_on_orphans else "map.requireHomes" if strict_homes
                else "--fail-on-skipped")
        unchecked = f"{gate} needs a test run: {no_run}"
    if not junit and surfaces_path is None:
        return step("map", FAILED, unchecked) if unchecked else step("map", SKIPPED, no_run)
    path, how = map_file(map_value)
    if path is None:
        return step("map", FAILED, how)
    report_args = ["--map", path]
    if config_path:
        report_args += ["--config", config_path]
    joined: List[str] = []
    if junit:
        for p in junit:
            report_args += ["--junit", p]
        report_args.append("--strict")
        if args.fail_on_orphans or strict_homes:
            report_args.append("--fail-on-orphans")
        if args.fail_on_skipped:
            report_args.append("--fail-on-skipped")
        joined.append("1 run path" if len(junit) == 1 else f"{len(junit)} run paths")
    if surfaces_path is not None:
        report_args += ["--surfaces", surfaces_path]
        if args.fail_on_unmapped or strict_homes:
            report_args.append("--fail-on-unmapped")
        joined.append("the entry-point list")
    run = run_script("map_report.py", report_args, cwd, args.json)
    what = f"{path} joined to {' and '.join(joined)}"
    if missing:
        what += f"; not written yet: {', '.join(missing)}"
    if unchecked:
        return step("map", FAILED, f"{what}; {unchecked}", run)
    return ran("map", what, run)


def _parsed(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return text


def main(argv: Optional[List[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(
        prog="check.py",
        description="Run what the promise GitHub Action checks, locally: lint the outcome docs, "
                    "check §0 against a base ref, check each shipped line no red run or kill covers, run the "
                    "map's own checks, and join the map to a test run and the code's entry points.",
    )
    parser.add_argument("--cwd", default=None, help="project root (default: current directory)")
    parser.add_argument("--docs-home", default=None, help="the outcome-doc folder (default: the config's docsHome, else detection)")
    parser.add_argument("--base", default=None, help="git ref to check §0 against (without it the §0 check is skipped)")
    parser.add_argument("--junit", action="append", default=[],
                        help="a JUnit XML file or folder for the map step, relative to the project root "
                             "(repeatable; default: map.junit)")
    parser.add_argument("--fail-on-orphans", action="store_true", help="fail the map step when a test in the run has no row")
    parser.add_argument("--fail-on-skipped", action="store_true",
                        help="fail the map step when the run skipped a test a row cites")
    parser.add_argument("--surfaces-cmd", default=None, metavar="COMMAND",
                        help="a command that prints the code's entry points, one per line, run as argv with no shell "
                             "(default: map.surfaces)")
    parser.add_argument("--fail-on-unmapped", action="store_true",
                        help="fail the map step when an entry point has no row")
    parser.add_argument("--config", default=None, help="the promise config to read (default: the one orient.py finds)")
    parser.add_argument("--no-lint", action="store_true", help="skip the shape lint")
    parser.add_argument("--no-map", action="store_true",
                        help="skip the checks, surfaces and map steps (the gate step still runs)")
    parser.add_argument("--map-checks", action="store_true",
                        help="with --no-map, still run the checks step: the map's own checks need no test run")
    parser.add_argument("--json", action="store_true", help="print one JSON object instead")
    args = parser.parse_args(argv)

    cwd = os.path.abspath(args.cwd) if args.cwd else os.path.abspath(os.getcwd())
    if not os.path.isdir(cwd):
        print(f"check.py: no such directory: {cwd}", file=sys.stderr)
        return 2
    try:
        config, config_path, warnings = load_project_config(cwd, args.config)
    except UsageError as exc:
        print(f"check.py: {exc}", file=sys.stderr)
        return 2
    if args.docs_home is not None:
        docs_home: Optional[str] = args.docs_home
    else:
        docs_home, _source = orient.resolve_docs_home(cwd, config, warnings)
    map_value, map_usable = orient.resolve_map(config, warnings, cwd)
    warnings.extend(supersedes_warnings(cwd, docs_home))
    if docs_home and not os.path.isdir(os.path.join(cwd, docs_home)):
        # lint, §0 and the gate all skip on a missing folder, so a misspelt one
        # would pass every run without a word; say so on every run
        warnings.append(f"docs home {docs_home!r} is not a folder: lint, §0 and the gate are skipped")

    grouped = os.environ.get("GITHUB_ACTIONS") == "true" and not args.json
    if not args.json:
        # orient's warnings name every config slip, some of which turn a gate
        # off; a green run must never hide one
        for warning in warnings:
            print(f"promise check: warning: {warning}")
    steps: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="promise-check-") as folder:
        surfaces: Dict[str, Optional[str]] = {"path": None}

        def run_surfaces() -> Dict[str, Any]:
            result, surfaces["path"] = surfaces_step(args, cwd, map_value, folder)
            return result

        for make in (
            lambda: lint_step(args, cwd, docs_home),
            lambda: section0_step(args, cwd, docs_home),
            lambda: gate_step(args, cwd, docs_home, config_path, map_value, map_usable, warnings),
            lambda: checks_step(args, cwd, map_value, map_usable, warnings),
            run_surfaces,
            lambda: map_step(args, cwd, config_path, map_value, map_usable, warnings, surfaces["path"]),
        ):
            result = make()
            steps.append(result)
            if args.json:
                continue
            run = result["run"]
            if run and (run["stdout"] or run["stderr"]):
                if grouped:
                    print(f"::group::promise check: {result['step']}")
                sys.stdout.write(run["stdout"])
                sys.stdout.write(run["stderr"])
                if not (run["stdout"] + run["stderr"]).endswith("\n"):
                    sys.stdout.write("\n")
                if grouped:
                    print("::endgroup::")
            print(f"promise check: {result['step']}: {result['status']} ({result['reason']})", flush=True)

    counts = {s: sum(1 for r in steps if r["status"] == s) for s in (OK, FAILED, SKIPPED)}
    if args.json:
        payload = {
            "ok": counts[FAILED] == 0,
            "cwd": cwd,
            "docsHome": docs_home,
            "steps": [
                {
                    "step": r["step"],
                    "status": r["status"],
                    "reason": r["reason"],
                    "argv": r["run"]["argv"] if r["run"] else None,
                    "exit": r["run"]["exit"] if r["run"] else None,
                    "output": (r["run"]["output"] if "output" in r["run"] else _parsed(r["run"]["stdout"]))
                    if r["run"] else None,
                    "stderr": r["run"]["stderr"] if r["run"] else None,
                }
                for r in steps
            ],
            "warnings": warnings,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"promise check: {counts[OK]} ok, {counts[FAILED]} failed, {counts[SKIPPED]} skipped")
    return 1 if counts[FAILED] else 0


if __name__ == "__main__":
    sys.exit(main())
