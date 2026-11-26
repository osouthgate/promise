#!/usr/bin/env python3
"""Move this repository to a promise release: every pin, the config's new keys, and a report.

    python3 upgrade.py --to v1.33.0 [--sha <its commit>] [--cwd DIR] [--dry-run]

``--to`` is a release tag (``vX.Y.Z``). In one pass, and with ``--dry-run`` as a diff
that writes nothing, it:

- sets ``.claude/settings.json``'s promise marketplace ``source.ref`` to the tag and
  drops a ``source.sha``: Claude Code's marketplace source reads ``ref`` and nothing
  else, so a sha pinned nothing;
- sets each ``pinFiles`` site: a ``sha`` site to the tag's commit (``--sha``, else read
  with one ``git ls-remote``), a ``version`` site to the version (a ``v`` kept as it was);
- adds to ``.claude/promise.config.json`` the keys a config from an earlier release
  lacks, at their defaults (``decisionPolicy``: ``auto``), rewrites an alias value to the
  name it reads as (``decisionPolicy: "prototype"`` becomes ``"fast"``), and raises
  ``minSkillVersion`` to the release, so an older copy of the skill warns here;
- prints, and never writes, what the project's own copies of the starter map lack: the
  recipe's ``##`` and ``###`` sections, and the reader's flags, subcommands and map keys
  (``map.recipe`` and the script ``map.find`` runs, against ``templates/starter-map/``
  of the skill that runs this). A project whose map is its own may lack them on purpose.

It never runs ``adopt.py``, the checks, git or ``claude``: ``/promise upgrade``
(``modes/upgrade.md``) runs those, puts the edits in a pull request of its own that a
human merges, and prints the machine step (``pin_machine.py``). Exit 0 written (or
nothing to change), 2 refused: a tag that is not ``vX.Y.Z``, a commit that is not 40
hex characters or not the tag's, a tag upstream does not have (with upstream not
reachable, only ``--sha`` lets it move, unchecked), or a pin site ``pin_check.py`` cannot
read or the move would erase. Each file keeps its bytes but for the values it moves.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shlex
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.dont_write_bytecode = True
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import orient  # noqa: E402  (sibling-script import; see path insert above)
import pin_check  # noqa: E402

STARTER = os.path.join(os.path.dirname(_SCRIPTS_DIR), "templates", "starter-map")
TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")
# Config keys a release added, with the value a config from before it takes.
NEW_KEYS = (("decisionPolicy", "auto"),)
# An alias value a config may hold, and the name it reads as (orient reads it the same way).
RENAMED_VALUES = (("decisionPolicy", "prototype", "fast"),)
HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$", re.MULTILINE)
FLAG_RE = re.compile(r"""add_argument\(\s*["'](--[a-z][a-z0-9-]*)["']""")
SUBCOMMAND_RE = re.compile(r"""argv\[:\d\]\s*==\s*\[([^\]]+)\]""")
MAP_KEY_RE = re.compile(r"""data\.get\(\s*["']([A-Za-z_][A-Za-z0-9_]*)["']""")
MACHINE_NEXT = ("Then, on each machine, in each repository that pins promise: "
                "python3 <skill>/scripts/pin_machine.py (and once with --user, for the user-scope install), "
                "then restart Claude Code.")


def read(path: str) -> str:
    """The file as written: a BOM and CRLF kept, so an edit changes only its values."""
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def _json(text: str) -> Any:
    return json.loads(text.lstrip("\ufeff"))


def _member(key: str, value: str) -> str:
    return r'"' + re.escape(key) + r'"\s*:\s*"' + re.escape(value) + r'"'


def settings_edit(cwd: str, tag: str) -> Optional[Tuple[str, str, str]]:
    """(path, text, moved text) for the settings pin, or None with no declaration.
    Only the ``ref`` value changes and a ``sha`` member goes (a ``sha`` with no ``ref``
    becomes the ``ref``); the rest of the file keeps its bytes. An edit that would not
    give exactly that is refused."""
    source = pin_check.settings_source(cwd)
    if not source:
        return None
    path = os.path.join(cwd, pin_check.SETTINGS)
    text = read(path)
    ref, sha = source.get("ref"), source.get("sha")
    new = text
    if ref is not None:
        new, n = re.subn(_member("ref", ref), lambda m: f'"ref": {json.dumps(tag)}', new, count=1)
        if n != 1:
            raise pin_check.PinError(f"{pin_check.SETTINGS}: source.ref is not written as a plain string")
        if sha is not None:
            new, n = re.subn(r",\s*" + _member("sha", sha) + r"|" + _member("sha", sha) + r"\s*,\s*", "", new,
                             count=1)
            if n != 1:
                raise pin_check.PinError(f"{pin_check.SETTINGS}: source.sha is not written as a plain string")
    elif sha is not None:
        new, n = re.subn(_member("sha", sha), lambda m: f'"ref": {json.dumps(tag)}', new, count=1)
        if n != 1:
            raise pin_check.PinError(f"{pin_check.SETTINGS}: source.sha is not written as a plain string")
    else:
        raise pin_check.PinError(f"{pin_check.SETTINGS}: the promise marketplace has neither ref nor sha; "
                                 "add \"ref\" by hand once")
    want = {k: v for k, v in source.items() if k != "sha"}
    want["ref"] = tag
    got = _json(new)["extraKnownMarketplaces"]["promise"]["source"]
    before = _json(text)
    before["extraKnownMarketplaces"]["promise"]["source"] = want
    if got != want or _json(new) != before:
        raise pin_check.PinError(f"{pin_check.SETTINGS}: the in-place edit would change more than the pin")
    return pin_check.SETTINGS, text, new


def pin_file_edits(cwd: str, sha: str, version: str,
                   seed: Dict[str, Tuple[str, str]]) -> Dict[str, Tuple[str, str]]:
    """One (original, moved) per file, on top of ``seed`` (the settings edit), so a
    pinFiles pattern on the same file moves on top of it, never over it."""
    edits = dict(seed)
    for spec in pin_check.pin_file_specs(cwd):
        path = spec["path"]
        _text, found = pin_check.pin_file_matches(cwd, spec)  # a site that holds no value is refused
        want = sha if spec["kind"] == "sha" else version
        if spec.get("vendored"):
            if all(v.lstrip("v") == want or (spec["kind"] == "sha" and pin_check.same_commit(v, want))
                   for _s, _e, v in found):
                continue
            raise pin_check.PinError(
                f"{path} records a vendored copy of the skill: moving its {spec['kind']} alone would name a "
                "release the copy does not hold. Sync the copy first (install_skill.py --project . --copy from a "
                "promise checkout at the tag, and whatever writes this file), then run upgrade.py again")
        if path not in edits:
            text = read(os.path.join(cwd, path))
            edits[path] = (text, text)
        original, text = edits[path]
        rx = re.compile(spec["pattern"], re.MULTILINE)
        group = 1 if rx.groups else 0
        pieces, last = [], 0
        for m in rx.finditer(text):
            old = m.group(group) or ""
            value = sha if spec["kind"] == "sha" else ("v" if old.startswith("v") else "") + version
            pieces += [text[last:m.start(group)], value]
            last = m.end(group)
        pieces.append(text[last:])
        edits[path] = (original, "".join(pieces))
    return edits


def config_edit(cwd: str, version: str) -> Optional[Tuple[str, str, str, List[str]]]:
    """(path, text, new text, what changed) for the config, or None with no config.
    New keys go in after the opening brace, and ``minSkillVersion``'s value is
    replaced in place; every other byte stays."""
    config, path, _warnings = orient.load_config(cwd)
    if not isinstance(config, dict) or not path:
        return None
    rel = os.path.relpath(path, cwd).replace(os.sep, "/")
    text = read(path)
    want = dict(config)
    changed: List[str] = []
    inserts: List[Tuple[str, Any]] = []
    for key, default in NEW_KEYS:
        if key not in config:
            inserts.append((key, default))
            want[key] = default
            changed.append(f'added "{key}": {json.dumps(default)}')
    new = text
    for key, old, now in RENAMED_VALUES:
        if config.get(key) == old:
            new, n = re.subn(_member(key, old), lambda m, k=key, v=now: f"{json.dumps(k)}: {json.dumps(v)}",
                             new, count=1)
            if n != 1:
                raise pin_check.PinError(f"{rel}: {key} is not written as a plain string")
            want[key] = now
            changed.append(f'"{key}": "{old}" → "{now}" (the same policy, under its current name)')
    current = config.get("minSkillVersion")
    if not (isinstance(current, str) and orient.VERSION_RE.match(current)
            and pin_check.vtuple(current) >= pin_check.vtuple(version)):
        want["minSkillVersion"] = version
        if isinstance(current, str):
            new, n = re.subn(_member("minSkillVersion", current), lambda m: f'"minSkillVersion": "{version}"',
                             new, count=1)
            if n != 1:
                raise pin_check.PinError(f"{rel}: minSkillVersion is not written as a plain string")
            changed.append(f'"minSkillVersion": "{current}" → "{version}"')
        else:
            if "minSkillVersion" in config:
                raise pin_check.PinError(f"{rel}: minSkillVersion is not a string; fix it by hand")
            inserts.insert(0, ("minSkillVersion", version))
            changed.append(f'added "minSkillVersion": "{version}"')
    if inserts:
        m = re.search(r"\{([ \t]*\r?\n?[ \t]*)", new)
        if not m or not config:
            raise pin_check.PinError(f"{rel}: no place to add {', '.join(k for k, _ in inserts)}; add by hand")
        gap = m.group(1) or " "
        anchor = re.search(r'"version"\s*:\s*1\s*,([ \t]*\r?\n?[ \t]*)', new)
        at, gap = (anchor.end(), anchor.group(1) or " ") if anchor else (m.end(), gap)
        added = "".join(f"{json.dumps(k)}: {json.dumps(v)},{gap}" for k, v in inserts)
        new = new[:at] + added + new[at:]
    if new != text and _json(new) != want:
        raise pin_check.PinError(f"{rel}: the in-place edit would change more than the keys named")
    return rel, text, new, changed


def headings(text: str) -> List[Tuple[str, str]]:
    """The ``##`` and ``###`` headings outside fenced code."""
    return HEADING_RE.findall("\n".join(orient.unfenced(text.splitlines())))


def _is_python(path: str) -> bool:
    if path.endswith(".py"):
        return True
    try:
        first = read(path).splitlines()[:1]
    except (OSError, ValueError):
        return False
    return bool(first) and first[0].startswith("#!") and "python" in first[0]


def _reader_features(text: str) -> Set[str]:
    found = {f"flag {f}" for f in FLAG_RE.findall(text)}
    for words in SUBCOMMAND_RE.findall(text):
        found.add("subcommand " + " ".join(w.strip().strip("\"'") for w in words.split(",")))
    found |= {f"map key {k!r}" for k in MAP_KEY_RE.findall(text)}
    return found


def _reader_path(cwd: str, find: Any) -> Optional[str]:
    """The script ``map.find`` runs: its first argument that is a file in the project."""
    try:
        argv = find if isinstance(find, list) else shlex.split(find) if isinstance(find, str) else []
    except ValueError:
        return None
    for token in argv:
        if isinstance(token, str) and not token.startswith("-") and not pin_check._release(token):
            path = os.path.join(cwd, token)
            if os.path.isfile(path):
                return path if _is_python(path) else None
    return None


def starter_report(cwd: str) -> List[str]:
    """What the project's own recipe and reader lack of the starter map's."""
    config, _path, _warnings = orient.load_config(cwd)
    map_value = config.get("map") if isinstance(config, dict) else None
    if not isinstance(map_value, dict):
        return []
    out: List[str] = []
    recipe = map_value.get("recipe")
    starter_recipe = os.path.join(STARTER, "recipe.md")
    if isinstance(recipe, str) and os.path.isfile(os.path.join(cwd, recipe)) and os.path.isfile(starter_recipe):
        have = {h.strip().lower() for _lvl, h in headings(read(os.path.join(cwd, recipe)))}
        for lvl, heading in headings(read(starter_recipe)):
            if heading.strip().lower() not in have:
                out.append(f"{recipe} lacks the starter recipe's section {lvl} {heading}")
    reader = _reader_path(cwd, map_value.get("find"))
    starter_reader = os.path.join(STARTER, "capability_find.py")
    if reader and os.path.isfile(starter_reader):
        rel = os.path.relpath(reader, cwd).replace(os.sep, "/")
        if read(reader) != read(starter_reader):
            missing = sorted(_reader_features(read(starter_reader)) - _reader_features(read(reader)))
            out += [f"{rel} lacks the starter reader's {item}" for item in missing]
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--to", required=True, help="the release tag to move to, vX.Y.Z")
    ap.add_argument("--sha", help="the tag's commit (40 hex); read upstream when left out")
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--dry-run", action="store_true", help="print the diff and the report; write nothing")
    ap.add_argument("--observations", help="service observation export for the read-only dry-run inventory")
    ap.add_argument("--timeout", type=float, default=5.0, help=argparse.SUPPRESS)
    ap.add_argument("--upstream-path", help="a local promise checkout to read a private upstream through "
                    "(default: PROMISE_UPSTREAM_PATH, else the config's upstreamPath)")
    ap.add_argument("--upstream", default=pin_check.UPSTREAM, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.observations and not args.dry_run:
        ap.error("--observations requires --dry-run")
    m = TAG_RE.match(args.to.strip())
    if not m:
        print(f"upgrade.py: --to must be a release tag like v1.33.0, not {args.to!r}", file=sys.stderr)
        return 2
    tag, version = args.to.strip(), m.group(1)
    cwd = os.path.abspath(args.cwd)
    sha = (args.sha or "").strip().lower()
    if sha and not pin_check.FULL_SHA_RE.match(sha):
        print(f"upgrade.py: --sha must be a full 40-character commit sha, not {args.sha!r}", file=sys.stderr)
        return 2
    try:
        pin_check._refuse_credentials(args.upstream, "--upstream")
    except pin_check.Refused as exc:
        print(f"upgrade.py: {exc}", file=sys.stderr)
        return 2
    refs, refs_why = pin_check.upstream_refs(cwd, args.upstream, args.timeout, args.upstream_path)
    if refs is not None:
        tag_sha = refs.get(f"refs/tags/{tag}")
        if not tag_sha:
            print(f"upgrade.py: {tag} is not a tag upstream; Claude Code could not fetch it", file=sys.stderr)
            return 2
        if sha and sha != tag_sha:
            print(f"upgrade.py: --sha {sha[:7]} is not {tag}'s commit ({tag_sha[:7]})", file=sys.stderr)
            return 2
        sha = tag_sha
    elif not sha:
        print(f"upgrade.py: {refs_why}, so the tag cannot be checked; pass --sha (its commit) "
              "to move without checking", file=sys.stderr)
        return 2
    else:
        print(f"upgrade.py: {refs_why}: {tag} at {sha[:7]} is not checked")
    try:
        specs = pin_check.pin_file_specs(cwd)
        seed: Dict[str, Tuple[str, str]] = {}
        found = settings_edit(cwd, tag)
        if found:
            seed[found[0]] = (found[1], found[2])
        edits = pin_file_edits(cwd, sha, version, seed)
        cfg = config_edit(cwd, version)
    except pin_check.PinError as exc:
        print(f"upgrade.py: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"upgrade.py: {exc}", file=sys.stderr)
        return 2
    if cfg:
        path, before, after, what = cfg
        if path in edits:  # pinFiles on the config itself: move on top of the key edit
            print("upgrade.py: pinFiles may not name the config file", file=sys.stderr)
            return 2
        edits[path] = (before, after)
    for i, spec in enumerate(specs):  # a site the move would erase breaks every later check
        text = edits.get(spec["path"], (None, None))[1]
        if text is None:
            continue
        rx = re.compile(spec["pattern"], re.MULTILINE)
        if not rx.search(text):
            print(f"upgrade.py: pinFiles[{i}] ({spec['path']}) would match nothing after the move; "
                  "change its pattern first", file=sys.stderr)
            return 2
    if not found and not specs:
        print("upgrade.py: no pin site: .claude/settings.json declares no promise marketplace, "
              "and the config has no pinFiles", file=sys.stderr)
        return 2
    changed = [(p, a, b) for p, (a, b) in edits.items() if a != b]
    for path, before, after in changed:
        sys.stdout.writelines(difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True), f"a/{path}", f"b/{path}"))
    for line in (cfg[3] if cfg else []):
        print(f"config: {line}")
    report = starter_report(cwd)
    if report:
        print("The project's own copies of the starter map lack (nothing written; add what applies):")
        for line in report:
            print(f"  {line}")
    if args.dry_run:
        import doctor

        print(doctor.format_report(doctor.inspect_project(cwd, observations=args.observations)))
    if not changed:
        print(f"every pin site is already at {tag}")
        return 0
    if args.dry_run:
        print(f"dry run: {len(changed)} file(s) would move to {tag}; nothing written")
        return 0
    for path, _before, after in changed:
        with open(os.path.join(cwd, path), "w", encoding="utf-8", newline="") as fh:
            fh.write(after)
    print(f"moved {len(changed)} file(s) to {tag}")
    print(MACHINE_NEXT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
