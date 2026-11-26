#!/usr/bin/env python3
"""Read Claude Code session transcripts and print what a session did with promise, as facts.

    python3 session_report.py [TRANSCRIPT.jsonl ...] [--cwd DIR] [--latest N] [--json] [--scrub]
    python3 session_report.py --scrub-check DRAFT.md [--cwd DIR]
    python3 session_report.py --record --size tiny --reason "copy change; keeps CAP-12" [--mode pr]
        [--stop checkpoint ...] [--needs-you N] [--decided N] [--not-checked N]

With no transcript it reads the newest ``--latest`` (default 1) session files Claude Code
keeps for the project at ``--cwd``: ``~/.claude/projects/<the path, with every character
that is not a letter or digit as "-">/*.jsonl`` (``CLAUDE_CONFIG_DIR`` moves ``~/.claude``).
A cloud session's files go when its container does, so run it inside the session it
reviews, or on transcripts saved from a local one.

The report is facts a script can count, for ``modes/retro.md`` to judge:

- ``promise.read`` / ``promise.notRead``: the skill's files the agent opened, and the
  core ones it never did (``SKILL.md`` and ``references/quickstart.md`` always;
  ``references/decision-sheet.md`` once ``decisions.py`` ran).
- ``promise.scripts``: each promise script run, by subcommand, with its failures and
  exit codes (the shell command's: a script piped into another program reports the
  pipe's); ``promise.retries``: a command run again after it failed.
- ``signals``: the patterns promise has been seen to go wrong in, each with a count:
  ``no-skill`` (scripts ran, ``SKILL.md`` never read), ``sheet-files-sent`` (a sheet's
  ``.md`` or ``.json`` handed to the human), ``sheet-not-published`` (a sheet built and
  no page published, nor the mod's decision pane opened), ``hand-answers`` (an
  ``Answer (`` line written by hand, not by ``decisions.py apply``), ``rebuilt-script`` (a file named like a promise script written
  outside the skill), ``repeated-command`` (one shell command run three times or more),
  ``script-refused`` (a promise script's exit 2).
- ``runs``: each run a mode closed out with ``--record``: its size and one-line reason,
  its mode (null for a tiny ask, which has none), its mid-flow stops by kind
  (``references/sizing.md`` § Batch: ``first-command``, ``delete-or-commit``,
  ``checkpoint``, ``no-outcome``), and the items it put under Needs you, Decided for
  you and Not checked. ``runTotals`` sums them, with the runs of each size.

``--record`` writes nothing: the command itself, in the transcript, is the record, and a
later report reads it back from there. It checks its flags and prints one line.

It never prints a file's contents or a message's words. ``--scrub`` also drops the shell
commands and every path outside the skill, each recorded run's reason, and a recorded
mode that is not one of the skill's (it reads "other"), for a report that leaves the project.
``--scrub-check`` reads a draft (an issue for the promise repository) and lists what
names the project: its repository and folder names, paths outside the skill, issue and
pull request numbers, links to other repositories, and email addresses. Exit 1 when it
finds any.

Exit codes: 0 on success (and a clean ``--scrub-check``, and a valid ``--record``), 1 when
``--scrub-check`` finds something, 2 on a usage error (a ``--record`` flag out of range too). Python 3 stdlib only.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shlex
import subprocess
import sys
from collections import Counter
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = sorted(os.path.basename(p) for p in glob.glob(os.path.join(SKILL_DIR, "scripts", "*.py")))
# The skill's modes, one file each: a recorded --mode outside this list is free text.
MODES = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(SKILL_DIR, "modes", "*.md")))
CORE = ("SKILL.md", "references/quickstart.md")
# A script is run when it follows a Python command or is given as a path (a pinned wrapper
# takes its name too); a name in a commit message or a heredoc is not a run.
SCRIPT_RE = re.compile(
    r"(?:(?<![\w.-])(?:[\w.~/-]*/)?(?:python(?:\d(?:\.\d+)?)?|py(?:\s+-3)?)\s+(?:-(?!m\b)\S+\s+)*"  # [/usr/bin/]python3.12 [flags]
    r"|\S*run\.sh\s+"                                               # a pinned wrapper: run.sh x.py
    r"|(?:^|[;&|\n])\s*(?=[\w.${}~\"'-]*/))"                          # a path in command position: ./scripts/x.py
    r"([\"']?(?:[\w.${}~\"'-]*/)*)(?<![\w-])(" + "|".join(re.escape(s) for s in SCRIPTS) + r")[\"']?"
    r"(?:\s+([a-z][\w-]*))?", re.M)
# The script is promise's: under skills/promise/scripts/, the skill's own folder variable, or a wrapper.
PROMISE_PATH_RE = re.compile(r"skills/promise/scripts/$|CLAUDE_SKILL_DIR|SKILL_DIR")
IN_SKILL_RE = re.compile(r"\bcd\s+[\"']?(?:\$\{?CLAUDE_SKILL_DIR\}?|\S*skills/promise)[\"'/]?(?=\s|&|;|$)")
IN_SCRIPTS_RE = re.compile(r"\bcd\s+[\"']?(?:\$\{?CLAUDE_SKILL_DIR\}?|\S*skills/promise)/scripts[\"'/]?(?=\s|&|;|$)")


def _subcommands() -> Dict[str, set]:
    """Each script's subcommands, from its own argparse calls: a word after a script is
    a subcommand only if the script defines it."""
    out: Dict[str, set] = {}
    for name in SCRIPTS:
        try:
            with open(os.path.join(SKILL_DIR, "scripts", name), "r", encoding="utf-8") as fh:
                out[name] = set(re.findall(r"add_parser\(\s*[\"']([\w-]+)[\"']", fh.read()))
        except OSError:
            out[name] = set()
    return out


SUBCOMMANDS = _subcommands()
# A promise file, wherever the skill sits: the plugin, an installed copy, a pinned cache.
SKILL_FILE_RE = re.compile(r"(?:^|/)skills/promise/([\w.-]+\.md|(?:modes|references|templates|scripts|agents)/[\w./-]+)$")
EXIT_RE = re.compile(r"^Exit code (\d+)")
SHELL_READ_RE = re.compile(r"(?:skills/promise/|\$\{?(?:CLAUDE_)?SKILL_DIR\}?/)([\w.-]+\.md|(?:modes|references)/[\w.-]+\.md)")
# The files decisions.py writes: sent to the human instead of the page, they are the known failure.
SHEET_OUT_RE = re.compile(r"--(?:md|chat|comment|asks-skeleton)[=\s]+[\"']?([^\s\"';|&]+)|>\s*[\"']?([^\s\"';|&]+\.(?:md|json))")
# A skill typed as a command reaches the transcript as its text, with no Skill call.
TYPED_SKILL_RE = re.compile(r"<command-name>/?promise(?::\w+)?</command-name>|Base directory for this skill: \S*promise\b")
# The promise mod's decision pane (hooks/decisions-pane.js): a sheet's surface, as a published page is.
PANE_TOOL = "mcp__promise__decision_pane"
# How its result starts when the sheet is on the pane, open or waiting for a wider terminal
# (PANE_SHOWN in hooks/decisions-pane.js; tests/test_session_report.py checks they agree).
PANE_SHOWN = "The decision pane is"
ANSWER_LINE_RE = re.compile(r"(?m)^\s*[*_]*Answer \(\d{4}-\d{2}-\d{2}")


SIZES = ("tiny", "small", "capability", "risky", "deferred")
SIZE_ALIASES = {"feature": "capability"}  # `feature` is read as `capability`
# The four mid-flow stops of references/sizing.md § Batch, in its order.
STOP_KINDS = ("first-command", "delete-or-commit", "checkpoint", "no-outcome")
COUNTS = (("needs_you", "needsYou"), ("decided", "decidedForYou"), ("not_checked", "notChecked"))
SHELL_OPS = {"&&", "||", ";", "|", "&"}


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    """An argparse parser that raises instead of exiting: a record read back from a
    transcript must never end the report."""

    def error(self, message: str) -> None:  # type: ignore[override]
        raise UsageError(message)


def _count(value: str) -> int:
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a whole number: {value!r}")
    if n < 0:
        raise argparse.ArgumentTypeError(f"not 0 or more: {value!r}")
    return n


def add_record_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--record", action="store_true",
                        help="record one run's size, stops and close-out counts (writes nothing)")
    parser.add_argument("--size", type=lambda v: SIZE_ALIASES.get(v, v), choices=SIZES, default=None, help="the size the ask was given")
    parser.add_argument("--reason", default=None, help="the size's one-line reason")
    parser.add_argument("--mode", default=None, help="the mode that ran (none for a tiny ask)")
    parser.add_argument("--stop", action="append", choices=STOP_KINDS, default=[],
                        help="one mid-flow stop, by kind (repeat it for each stop)")
    parser.add_argument("--needs-you", type=_count, default=0, help="items under Needs you")
    parser.add_argument("--decided", type=_count, default=0, help="items under Decided for you")
    parser.add_argument("--not-checked", type=_count, default=0, help="items under Not checked")


def run_record(args: argparse.Namespace) -> Dict[str, Any]:
    """One run, from the --record flags."""
    if not args.size:
        raise UsageError("--record needs --size (tiny, small, capability, risky or deferred)")
    mode = (args.mode or "").strip().lower()
    stops = Counter(args.stop)
    return {"size": args.size, "reason": (args.reason or "").strip() or None,
            "mode": None if mode in ("", "none") else mode,
            "stops": {k: stops[k] for k in STOP_KINDS if stops[k]},
            **{key: getattr(args, attr) for attr, key in COUNTS}}


RECORD_PARSER = _Parser(add_help=False)
add_record_flags(RECORD_PARSER)


def recorded_runs(command: str) -> List[Dict[str, Any]]:
    """The runs a shell command recorded with ``session_report.py --record``."""
    if "session_report.py" not in command or "--record" not in command:
        return []
    try:
        tokens = shlex.split(command, comments=False)
    except ValueError:
        return []
    out = []
    for i, tok in enumerate(tokens):
        if not tok.endswith("session_report.py"):
            continue
        before = tokens[i - 1] if i else ""
        # run by python, by a pinned wrapper, or as a path in command position; a name an echo prints is no run
        if not (i == 0 or before in SHELL_OPS or before.endswith("run.sh")
                or re.search(r"(?:^|/)(?:python(?:\d(?:\.\d+)?)?|py)$", before)):
            continue
        rest: List[str] = []
        for t in tokens[i + 1:]:
            if t in SHELL_OPS:
                break
            rest.append(t)
        try:
            args, _unknown = RECORD_PARSER.parse_known_args(rest)
            if args.record:
                out.append(run_record(args))
        except UsageError:
            continue  # the record refused itself: it counts for nothing
    return out


def run_totals(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    stops: Counter = Counter()
    for r in runs:
        stops.update(r["stops"])
    sizes = Counter(r["size"] for r in runs)
    return {"runs": len(runs), "bySize": {s: sizes[s] for s in SIZES if sizes[s]},
            "stops": {k: stops[k] for k in STOP_KINDS if stops[k]}, "stopsTotal": sum(stops.values()),
            **{key: sum(r[key] for r in runs) for _attr, key in COUNTS}}


def project_slug(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(path))


def find_transcripts(cwd: str, latest: int) -> List[str]:
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    folders = [os.path.join(home, "projects", project_slug(p)) for p in dict.fromkeys((cwd, os.path.realpath(cwd)))]
    folder = next((f for f in folders if os.path.isdir(f)), folders[0])
    files = sorted(glob.glob(os.path.join(folder, "*.jsonl")), key=os.path.getmtime, reverse=True)
    if not files:
        raise UsageError(f"no session transcripts for {cwd} under {folder}; pass the .jsonl files")
    return files[:latest]


def records(path: str) -> Iterator[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except ValueError:
                continue
            if isinstance(data, dict):
                yield data


def _blocks(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    content = (record.get("message") or {}).get("content") if isinstance(record.get("message"), dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _result_text(block: Dict[str, Any]) -> str:
    content = block.get("content")
    if isinstance(content, list):
        return " ".join(str(c.get("text", "")) for c in content if isinstance(c, dict))
    return str(content or "")


def skill_file(path: str) -> Optional[str]:
    m = SKILL_FILE_RE.search(str(path).replace("\\", "/"))
    return m.group(1) if m else None


def analyse(paths: List[str]) -> Dict[str, Any]:
    tools: Counter = Counter()
    read: set = set()
    skill_loaded = False
    turns = 0
    cost = 0.0
    calls: Dict[str, Dict[str, Any]] = {}  # tool_use id -> what it ran
    scripts: Dict[Tuple[str, str], Dict[str, Any]] = {}
    commands: Counter = Counter()
    failed_commands: set = set()
    retries: Counter = Counter()
    sent_files: List[str] = []
    sheet_outputs: set = set()
    published_pages = 0
    pane_calls: Set[str] = set()
    sheets_built = 0
    hand_answers = 0
    rebuilt: List[str] = []
    recorded: List[Dict[str, Any]] = []
    for path in paths:
        session_cost = 0.0  # a session's cost-state is its running total: its last is its cost
        for rec in records(path):
            if rec.get("type") == "cost-state":
                try:
                    session_cost = max(session_cost, float(rec.get("totalCostUSD") or 0))
                except (TypeError, ValueError):
                    pass
            if rec.get("type") == "user" and (rec.get("origin") or {}).get("kind") == "human":
                turns += 1
            if rec.get("type") == "user":
                message = rec.get("message") if isinstance(rec.get("message"), dict) else {}
                texts = [message.get("content")] if isinstance(message.get("content"), str) else \
                    [b.get("text", "") for b in _blocks(rec) if b.get("type") == "text"]
                if any(TYPED_SKILL_RE.search(str(t)) for t in texts):
                    skill_loaded = True
            for b in _blocks(rec):
                if b.get("type") == "tool_use":
                    name = str(b.get("name") or "")
                    args = b.get("input") if isinstance(b.get("input"), dict) else {}
                    tools[name] += 1
                    if name == "Skill" and "promise" in str(args.get("skill", "")):
                        skill_loaded = True
                    if name == "Read":
                        f = skill_file(str(args.get("file_path", "")))
                        if f:
                            read.add(f)
                    if name in ("Write", "Edit", "NotebookEdit"):
                        target = str(args.get("file_path", ""))
                        text = str(args.get("content", "")) + str(args.get("new_string", ""))
                        old = str(args.get("old_string", ""))
                        # Only an edit adds lines we can see: a whole-file Write keeps every line apply wrote.
                        if name == "Edit" and target.endswith(".md") and \
                                len(ANSWER_LINE_RE.findall(text)) > len(ANSWER_LINE_RE.findall(old)):
                            hand_answers += 1
                        if os.path.basename(target) in SCRIPTS and not skill_file(target) and "promise" in text:
                            rebuilt.append(target)
                    if name == "SendUserFile":
                        sent_files += [str(f) for f in args.get("files") or []]
                    if name == "Artifact" and str(args.get("file_path", "")).endswith(".html") \
                            and args.get("action") in (None, "publish") and not args.get("asset"):
                        published_pages += 1
                    if name == PANE_TOOL:  # the promise mod's pane is the sheet's surface too, once it opens
                        pane_calls.add(str(b.get("id")))
                    if name == "Bash":
                        command = str(args.get("command", ""))
                        commands[command] += 1
                        recorded += recorded_runs(command)
                        if command in failed_commands:
                            retries[command] += 1
                        runs = [(m.group(2), m.group(3) if m.group(3) in SUBCOMMANDS.get(m.group(2), ()) else "")
                                for m in SCRIPT_RE.finditer(command)
                                if PROMISE_PATH_RE.search(m.group(1).strip("\"'")) or "run.sh" in m.group(0)
                                or (m.group(1).strip("\"'") in ("scripts/", "./scripts/") and IN_SKILL_RE.search(command))
                                or (m.group(1).strip("\"'") in ("", "./") and IN_SCRIPTS_RE.search(command))]
                        for script, sub in runs:
                            if script == "decisions.py" and sub == "sheet":
                                sheets_built += 1
                                for a, b2 in SHEET_OUT_RE.findall(command):
                                    sheet_outputs.add(os.path.basename(a or b2))
                            if script == "session_report.py":
                                continue
                            entry = scripts.setdefault((script, sub), {"script": script, "sub": sub or None,
                                                                         "runs": 0, "failed": 0, "exitCodes": Counter()})
                            entry["runs"] += 1
                        calls[str(b.get("id"))] = {"command": command, "scripts": runs}
                    # a promise file read through the shell counts as read
                    if name == "Bash":
                        command = str(args.get("command", ""))
                        if re.search(r"\b(cat|sed|head|tail|less|more|grep|awk)\b", command):
                            for f in SHELL_READ_RE.findall(command):
                                read.add(f)
                elif b.get("type") == "tool_result":
                    if str(b.get("tool_use_id")) in pane_calls and _result_text(b).startswith(PANE_SHOWN):
                        published_pages += 1  # a refused call, or an empty sheet, showed the human nothing
                    call = calls.get(str(b.get("tool_use_id")))
                    if not call:
                        continue
                    error = b.get("is_error") in (True, "True", "true")
                    m = EXIT_RE.match(_result_text(b).strip())
                    code = int(m.group(1)) if m else (1 if error else 0)
                    if code:
                        failed_commands.add(call["command"])
                    else:
                        failed_commands.discard(call["command"])  # it passes now: a later run is no retry
                    for script, sub in call["scripts"]:
                        entry = scripts.get((script, sub))
                        if entry is None:
                            continue
                        entry["exitCodes"][str(code)] += 1
                        if code:
                            entry["failed"] += 1
        cost += session_cost
    ran = {s for s, _ in scripts}
    sent_sheet_files = [f for f in sent_files if os.path.basename(f) in sheet_outputs]
    expected = list(CORE) + (["references/decision-sheet.md"] if "decisions.py" in ran else [])
    not_read = [f for f in expected if f not in read and not (f == "SKILL.md" and skill_loaded)]
    script_list = []
    for entry in sorted(scripts.values(), key=lambda e: (e["script"], e["sub"] or "")):
        entry["exitCodes"] = dict(sorted(entry["exitCodes"].items()))
        script_list.append(entry)
    refused = sum(e["exitCodes"].get("2", 0) for e in script_list)
    repeated = {c: n for c, n in commands.items() if n >= 3}
    signals = []

    def signal(kind: str, count: int, detail: Any) -> None:
        if count:
            signals.append({"kind": kind, "count": count, "detail": detail})

    signal("no-skill", 1 if ran and not skill_loaded and "SKILL.md" not in read else 0,
           "promise scripts ran, and SKILL.md was never read")
    signal("sheet-files-sent", len(sent_sheet_files), sent_sheet_files)
    signal("sheet-not-published", 1 if sheets_built and not published_pages else 0,
           f"{sheets_built} sheet builds, no page published")
    signal("hand-answers", hand_answers, "Answer lines written by hand instead of decisions.py apply")
    signal("rebuilt-script", len(rebuilt), rebuilt)
    signal("repeated-command", len(repeated), [{"command": c[:120], "times": n} for c, n in
                                                sorted(repeated.items(), key=lambda x: (-x[1], x[0]))[:10]])
    signal("script-refused", refused, "promise scripts that exited 2 (refused)")
    return {
        "format": "promise-session-report", "version": 1,
        "transcripts": [os.path.basename(p) for p in paths],
        "turns": turns, "costUSD": round(cost, 2) if cost else None,
        "toolCalls": dict(tools.most_common()),
        "promise": {"skillLoaded": skill_loaded, "read": sorted(read), "notRead": not_read,
                    "scripts": script_list,
                    "retries": [{"command": c[:120], "times": n} for c, n in retries.most_common(10)]},
        "signals": signals,
        "runs": recorded, "runTotals": run_totals(recorded),
    }


def scrub(report: Dict[str, Any]) -> Dict[str, Any]:
    """The report with no shell command and no path outside the skill: safe to leave the project."""
    out = json.loads(json.dumps(report))
    out["transcripts"] = [f"session-{n + 1}" for n in range(len(out["transcripts"]))]
    tools: Counter = Counter()
    for name, n in out["toolCalls"].items():
        tools["mcp (connector)" if name.startswith("mcp__") else name] += n  # a connector's name can name a project
    out["toolCalls"] = dict(tools.most_common())
    out["promise"]["retries"] = [{"times": r["times"]} for r in out["promise"]["retries"]]
    for r in out["runs"]:
        r["reason"] = None  # the agent's own words: they can name the project
        if r.get("mode") is not None and r["mode"] not in MODES:
            r["mode"] = "other"  # not one of the skill's modes: free text, which can too
    for s in out["signals"]:
        if s["kind"] == "repeated-command":
            s["detail"] = [{"times": d["times"]} for d in s["detail"]]
        elif s["kind"] in ("sheet-files-sent", "rebuilt-script"):
            s["detail"] = sorted({os.path.basename(p) if os.path.basename(p) in SCRIPTS else
                                  "a " + os.path.splitext(p)[1] + " file" for p in s["detail"]})
    return out


def project_words(cwd: str) -> List[str]:
    """Names that point at this project: its folder, its git remotes' owner and name,
    and its top-level folders that are not common ones."""
    common = {"src", "docs", "doc", "tests", "test", "scripts", "lib", "app", "apps", "packages", "bin", "build",
              "dist", "node_modules", "public", "assets", "config", "examples", "tools", "vendor", "skills", "hooks",
              "api", "web", "server", "client", "db", "data", "cache", "tmp", "out", "fixtures", "spec", "types"}
    words = {os.path.basename(os.path.abspath(cwd))} - {w for w in common}
    try:
        remotes = subprocess.run(["git", "-C", cwd, "remote", "-v"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        remotes = ""
    for owner, name in re.findall(r"[:/]([\w.-]+)/([\w.-]+?)(?:\.git)?\s", remotes):
        words.update({owner, name})
    try:
        for entry in os.listdir(cwd):
            if os.path.isdir(os.path.join(cwd, entry)) and not entry.startswith(".") and entry.lower() not in common:
                words.add(entry)
    except OSError:
        pass
    return sorted(w for w in words if len(w) >= 3 and w.lower() not in common | {"promise", "claude"})


PLUGIN_JSON = os.path.join(os.path.dirname(os.path.dirname(SKILL_DIR)), ".claude-plugin", "plugin.json")


def promise_repository() -> str:
    """owner/name of the promise repository, from the plugin's own manifest."""
    try:
        with open(PLUGIN_JSON, "r", encoding="utf-8") as fh:
            url = json.load(fh).get("repository") or ""
    except (OSError, ValueError):
        url = ""
    m = re.search(r"github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?/?$", str(url))
    return m.group(1) if m else "osouthgate/promise"


# Paths every adopted project has, named by promise itself: they say nothing about the project.
PROMISE_OWN_PATHS = {".claude/promise.config.json", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
                     ".claude/settings.json", ".pre-commit-hooks.yaml"}


def _promise_path(path: str) -> bool:
    """A path to a real file of the skill: skills/promise/<file>, or modes/…, references/…,
    templates/… or scripts/… as the skill has them."""
    if path in PROMISE_OWN_PATHS:
        return True
    if path.startswith("skills/promise/"):  # the skill's own tree, including a file a fix proposes
        rel = path[len("skills/promise/"):]
        return bool(re.match(r"(?:modes|references|templates|scripts|agents)/", rel)) \
            or os.path.exists(os.path.join(SKILL_DIR, rel))
    # a bare modes/…, references/… or scripts/… path: only one the skill has (a project has scripts/ too)
    return bool(re.match(r"(?:modes|references|templates|scripts|agents)/", path)) \
        and os.path.exists(os.path.join(SKILL_DIR, path))


def scrub_check(text: str, cwd: str) -> List[str]:
    """What in a draft names the project it came from."""
    found = []
    repo = promise_repository()
    text = re.sub(r"\$\{?CLAUDE_SKILL_DIR\}?/", "skills/promise/", text)  # the skill's own path form
    for url in re.findall(r"https?://[^\s<>]+", text):
        url = url.rstrip(".,);]>")
        if not re.match(r"https?://github\.com/" + re.escape(repo) + r"(?:[/#?]|$)", url, re.I):
            found.append(f"'{url}': a link outside the promise repository")
    plain = re.sub(r"https?://[^\s<>]+", " ", text)
    # An absolute path names a machine's folders, whatever it ends in: its user, a client's folder.
    for m in re.finditer(r"(?<![\w.])(?:~[\w.-]*/|/(?=[\w.-]+/)|[A-Za-z]:\\)[^\s'\"`)<>,;]*", plain):
        found.append(f"'{m.group(0)}': an absolute path")
    relative = re.sub(r"(?<![\w.])(?:~[\w.-]*/|/(?=[\w.-]+/)|[A-Za-z]:\\)[^\s'\"`)<>,;]*", " ", plain)
    for m in re.finditer(r"(?<![\w/])(?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]{1,6}\b", relative):
        if not _promise_path(m.group(0)):
            found.append(f"'{m.group(0)}': a path outside the skill")
    # promise's own words (its folders, files and repository) never count as the project's
    own = {w.lower() for w in re.split(r"[/.]", repo)} | {"promise", "claude"}
    for root, dirs, files in os.walk(SKILL_DIR):
        own.update(d.lower() for d in dirs)
        own.update(os.path.splitext(f)[0].lower() for f in files)
    words_text = re.sub(r"(?<![\w/])(?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]{1,6}\b",
                        lambda m: " " if _promise_path(m.group(0)) else m.group(0), plain)
    for word in project_words(cwd):
        if word.lower() in own:
            continue
        m = re.search(r"(?<![\w-])" + re.escape(word) + r"(?![\w-])", words_text, re.I)
        if m:
            found.append(f"'{m.group(0)}': names this project (a folder or repository name)")
    for m in re.finditer(r"(?<![\w&/#])#\d+\b", plain):
        found.append(f"'{m.group(0)}': an issue or pull request number from the project")
    for m in re.finditer(r"\b[\w.-]+/[\w.-]+#\d+\b", plain):  # owner/repo#87 names a repository and an issue
        if not m.group(0).lower().startswith(repo.lower() + "#"):
            found.append(f"'{m.group(0)}': another repository's issue or pull request")
    for m in re.finditer(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text):
        found.append(f"'{m.group(0)}': an email address")
    return list(dict.fromkeys(found))


def summary_lines(report: Dict[str, Any]) -> List[str]:
    p = report["promise"]
    out = [f"promise session report: {len(report['transcripts'])} transcript(s), {report['turns']} human turns, "
           f"{sum(report['toolCalls'].values())} tool calls" + (f", ${report['costUSD']}" if report["costUSD"] else "")]
    out.append(f"skill loaded: {'yes' if p['skillLoaded'] else 'no'}; read: {', '.join(p['read']) or 'none'}")
    if p["notRead"]:
        out.append(f"never read: {', '.join(p['notRead'])}")
    for s in p["scripts"]:
        name = s["script"] + (f" {s['sub']}" if s["sub"] else "")
        out.append(f"script: {name}: {s['runs']} runs, {s['failed']} failed, exit codes {s['exitCodes']}")
    for s in report["signals"]:
        out.append(f"signal: {s['kind']} ({s['count']})")
    for r in report["runs"]:
        stops = ", ".join(f"{k} {n}" for k, n in r["stops"].items()) or "none"
        out.append(f"run: {r['size']}" + (f" ({r['reason']})" if r["reason"] else "")
                   + f", mode {r['mode'] or 'none'}; stops: {stops}; needs you {r['needsYou']}, "
                   f"decided for you {r['decidedForYou']}, not checked {r['notChecked']}")
    t = report["runTotals"]
    if t["runs"]:
        sizes = ", ".join(f"{k} {n}" for k, n in t["bySize"].items())
        out.append(f"runs: {t['runs']} ({sizes}); {t['stopsTotal']} stops; needs you {t['needsYou']}, "
                   f"decided for you {t['decidedForYou']}, not checked {t['notChecked']}")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = _Parser(description="What a Claude Code session did with promise, as facts.")
    parser.add_argument("transcripts", nargs="*", help="session .jsonl files (default: the project's newest)")
    parser.add_argument("--cwd", default=None, help="the project (default: the current directory)")
    parser.add_argument("--latest", type=int, default=1, help="how many of the newest sessions to read (default 1)")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--scrub", action="store_true", help="drop shell commands and paths outside the skill")
    parser.add_argument("--scrub-check", default=None, metavar="DRAFT",
                        help="list what in a draft names this project; exit 1 if anything does")
    add_record_flags(parser)
    try:
        args = parser.parse_args(argv)
    except UsageError as exc:
        print(f"session_report.py: {exc}", file=sys.stderr)
        return 2
    cwd = os.path.abspath(args.cwd or os.getcwd())
    try:
        if args.record:
            run = run_record(args)
            stops = sum(run["stops"].values())
            print(f"session_report.py: recorded a {run['size']} run, mode {run['mode'] or 'none'}, {stops} stops, "
                  f"{run['needsYou']} needs you, {run['decidedForYou']} decided for you, "
                  f"{run['notChecked']} not checked")
            return 0
        if args.scrub_check:
            try:
                with open(args.scrub_check, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError as exc:
                raise UsageError(f"cannot read {args.scrub_check}: {exc}")
            found = scrub_check(text, cwd)
            if args.json:
                print(json.dumps({"format": "promise-scrub-check", "found": found}, indent=2))
            else:
                for f in found:
                    print(f"names the project: {f}")
                print(f"session_report.py: {len(found)} finding(s)" if found else "session_report.py: the draft is clean")
            return 1 if found else 0
        if args.latest < 1:
            raise UsageError("--latest must be 1 or more")
        paths = [os.path.abspath(p) for p in args.transcripts] or find_transcripts(cwd, args.latest)
        missing = [p for p in paths if not os.path.isfile(p)]
        if missing:
            raise UsageError("no such transcript: " + ", ".join(missing))
        report = analyse(paths)
        if args.scrub:
            report = scrub(report)
        print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else "\n".join(summary_lines(report)))
        return 0
    except UsageError as exc:
        print(f"session_report.py: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
