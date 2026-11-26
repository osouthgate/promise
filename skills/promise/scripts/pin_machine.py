#!/usr/bin/env python3
"""Move this machine's promise plugin to the release this repository pins, and check it.

    python3 pin_machine.py [--cwd DIR] [--dry-run] [--user]

The repository pins a release tag in ``.claude/settings.json`` (the promise
marketplace's ``source.ref``). Claude Code keeps its own copy of each marketplace it
knows, and ``claude plugin marketplace update`` refreshes that copy from the source it
saved, not from a ``ref`` the repository changed since, so a machine keeps running the
release it first installed. This script runs, in the repository:

    claude plugin marketplace add <repo>#<ref> --scope project
    claude plugin update promise@promise --scope project

The first re-declares the marketplace at the pinned ref, which moves the saved copy
(it may exit 1 with "now points at …": that is the move); the second installs from it.
``--user`` runs the pair for the user-scope install instead (no ``--scope``), from the
home directory. Claude Code rewrites ``.claude/settings.json`` in its own key order, and
may drop keys it does not know: the file's bytes are always put back, so the checkout
stays clean and the pin moves only in a pull request. Then it reads ``installed_plugins.json`` and exits 0 only when the install
is the pinned commit (or, with upstream not reachable, the pinned version). Restart
Claude Code to load it: a running session keeps the skill it loaded.

It changes this machine, never the pin: a ``source.sha`` with no ``ref`` (which Claude
Code does not read) is refused, since re-declaring would rewrite the pin; move it with
``/promise upgrade`` first. ``--dry-run`` prints the commands and runs nothing. Exit 0
moved and checked, 1 ran but the install is not the pin, 2 refused (no ``ref``, no
``claude`` on PATH).
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

import orient  # noqa: E402  (sibling-script import; see path insert above)
import pin_check  # noqa: E402

TIMEOUT = 300


REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9._-]+$")
URL_RE = re.compile(r"^https://[A-Za-z0-9.-]+(:\d+)?/[A-Za-z0-9._~/-]+$")
REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def ref_ok(ref: str) -> bool:
    """A ref git accepts that cannot read as an option: no leading ``-``, no ``..``."""
    return bool(REF_RE.match(ref)) and ".." not in ref and not ref.endswith((".lock", "/", "."))


def marketplace_source(source: Dict[str, Any], ref: str) -> Optional[str]:
    """The ``marketplace add`` argument for this declaration at ``ref``, or None when a
    value could read as an option to ``claude`` or is not the shape Claude Code takes."""
    if not ref_ok(ref):
        return None
    if source.get("source") == "github" and isinstance(source.get("repo"), str) and REPO_RE.match(source["repo"]):
        return f"{source['repo']}#{ref}"
    if source.get("source") == "git" and isinstance(source.get("url"), str) and URL_RE.match(source["url"]):
        return f"{source['url']}#{ref}"
    return None


def commands(add_source: str, user: bool) -> List[List[str]]:
    scope = [] if user else ["--scope", "project"]
    return [["claude", "plugin", "marketplace", "add", add_source, *scope],
            ["claude", "plugin", "update", orient.PROMISE_PLUGIN_ID, *scope]]


def saved_ref() -> Optional[str]:
    """The ref of Claude Code's saved copy of the promise marketplace."""
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    try:
        data = json.loads(orient.read_text_tolerant(os.path.join(base, "plugins", "known_marketplaces.json")))
        ref = data["promise"]["source"].get("ref")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return ref if isinstance(ref, str) else None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--cwd", default=os.getcwd(), help="the repository whose pin the machine moves to")
    ap.add_argument("--dry-run", action="store_true", help="print the commands; run nothing")
    ap.add_argument("--user", action="store_true", help="move the user-scope install, from the home directory")
    ap.add_argument("--timeout", type=float, default=5.0, help=argparse.SUPPRESS)
    ap.add_argument("--upstream-path", help="a local promise checkout to read a private upstream through")
    ap.add_argument("--upstream", default=pin_check.UPSTREAM, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    cwd = os.path.abspath(args.cwd)
    try:
        source = pin_check.settings_source(cwd)
    except pin_check.PinError as exc:
        print(f"pin_machine.py: {exc}", file=sys.stderr)
        return 2
    ref = source.get("ref") if source else None
    if not ref:
        print("pin_machine.py: .claude/settings.json pins no source.ref, and Claude Code reads no other pin "
              "(a source.sha is ignored). Move the pin to a release tag with /promise upgrade first.",
              file=sys.stderr)
        return 2
    add_source = marketplace_source(source, ref)
    if not add_source:
        print("pin_machine.py: the promise marketplace source is not a github owner/repo or an https git url "
              "with a plain ref (a value starting with '-', or holding '..', is refused)", file=sys.stderr)
        return 2
    cmds = commands(add_source, args.user)
    run_dir = os.path.expanduser("~") if args.user else cwd
    print(f"in {run_dir}:")
    for cmd in cmds:
        print("  " + " ".join(cmd))
    if args.dry_run:
        print("dry run: nothing ran")
        return 0
    if shutil.which("claude") is None:
        print("pin_machine.py: no claude on PATH; run the commands above by hand", file=sys.stderr)
        return 2
    settings_path = os.path.join(cwd, pin_check.SETTINGS)
    with open(settings_path, "rb") as fh:
        before = fh.read()
    for cmd in cmds:
        try:
            proc = subprocess.run(cmd, cwd=run_dir, capture_output=True, text=True, timeout=TIMEOUT,
                                  stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"pin_machine.py: {' '.join(cmd[:4])} did not finish: {exc}", file=sys.stderr)
            return 1
        said = (proc.stdout + proc.stderr).strip().splitlines()
        print(f"  → exit {proc.returncode}: {said[-1] if said else ''}")
    with open(settings_path, "rb") as fh:
        after = fh.read()
    if after != before:
        # The machine's state lives under ~/.claude; the repository's pin moves only in a
        # pull request, so its bytes always go back.
        try:
            same = json.loads(after.decode("utf-8-sig")) == json.loads(before.decode("utf-8-sig"))
        except ValueError:
            same = False
        with open(settings_path, "wb") as fh:
            fh.write(before)
        print(f"{pin_check.SETTINGS}: Claude Code " + ("reordered it" if same else "changed what it says") +
              "; its bytes are put back")
    if saved_ref() != ref:
        print(f"pin_machine.py: Claude Code's saved promise marketplace is at {saved_ref()!r}, not {ref!r}")
        return 1
    machine = orient.machine_plugin(cwd if not args.user else os.path.expanduser("~"))
    refs, refs_why = pin_check.upstream_refs(cwd, args.upstream, args.timeout, args.upstream_path)
    if refs_why:
        print(f"pin_machine.py: {refs_why}; the install is checked by its version only")
    want_sha = (refs.get(f"refs/tags/{ref}") or refs.get(f"refs/heads/{ref}")) if refs else None
    want_version = pin_check._release(ref)
    if not machine:
        print("pin_machine.py: installed_plugins.json has no promise install for this directory")
        return 1
    ok = (pin_check.same_commit(want_sha, machine["gitCommitSha"] or "") if want_sha and machine["gitCommitSha"]
          else bool(want_version) and machine["version"] == want_version)
    runs = f"{machine['version'] or '?'} ({pin_check.short(machine['gitCommitSha'])})"
    if not ok:
        print(f"pin_machine.py: this machine runs {runs}; the repo pins {ref}")
        return 1
    print(f"this machine now runs {runs}, the pinned {ref}. Restart Claude Code to load it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
