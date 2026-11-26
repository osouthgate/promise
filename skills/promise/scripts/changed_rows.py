#!/usr/bin/env python3
"""Which capabilities a change touches: the map at the base against the map at the head.

    python3 changed_rows.py                          # origin/main...HEAD, human summary
    python3 changed_rows.py --base main --head feat/x --json
    python3 changed_rows.py --markdown               # the block `pr` mode puts in <details>
    python3 changed_rows.py --head origin/main --link CAP-3 --link CAP-7   # row links for an issue

A reviewer reads a pull request from the issue it closes, to the capabilities
it changes, to the code that delivers them. This script gives the middle step
as facts, so the words written around it (`modes/pr.md`) can stay short.

The project is ``--cwd`` (default: the current folder). Its config is read
there, as orient and ``lint_github_text.py`` read it, and the folder may sit
below the top of its git work tree. Every path in the report is relative to
the project, as map citations are; a changed file outside the project folder
is listed apart (``outsideProject``).

It compares the capability map at the merge base of ``--base`` and ``--head``
(what GitHub shows as the pull request's diff) with the map at ``--head``, and
reads the files the change touched, renames followed (``git diff -z``, so a
file name reads as written, in any script). Each row it reports carries one
``change``:

- ``added`` / ``removed``: the row is new, or gone.
- ``changed``: the row itself changed -- its story, a scenario (its given,
  when, then or altitude; scenarios pair by id, one without an id by its
  ``then`` text, and by position only among equal ``then`` texts), its
  verdict, an evidence array, its surfaces (as a set: order is no change) or
  its doc, or any other top-level key, listed in ``fields`` (``parent``,
  ``aliases``, ``origin``).
- ``touched``: the row did not change, but the change touched a file the row
  cites, a file its own text names, or its outcome doc. The text names a file
  by a path with a folder in it (``routes/artefacts.ts:40`` names
  ``apps/api/src/routes/artefacts.ts``), or by a bare file name that carries a
  ``:line`` (``me.ts:66``) or is the only file of that name in the tree at the
  head and among the changed files. A renamed file counts by its path before
  the rename too, so a row that cites a file the change moved away is touched
  (``filesMoved``). A touched row asks one question of the author: does the
  verdict still hold?
- ``relabelled``: only the row's ``feature`` changed (``featureChanged``); the
  promise did not.

Each reported row carries its ``feature``, and the report's ``features`` lists the
features of the rows the change added, changed, removed or touched -- each with
the ``name`` and ``plain`` sentence the map's top-level ``features`` gives it and
its row ids, most rows first; rows with no feature share an entry with a null
id. A pull request names these features first ("Where this is",
``references/first-screen.md``). ``featuresRelabelled`` groups the relabelled
rows the same way, by their new feature; ``--markdown`` lists up to 12
relabelled rows by id and counts more by feature. The map may spell the keys
``areas`` and ``area``: they mean the same and the report says ``feature``. A map
that uses both spellings is the error ``FEATURE_AND_AREA``.

Each reported row also lists ``missingCitations``: the files it cites (the
sibling lane aside) that are not in the tree at the head. A row whose ``doc``
is null lists ``docsNaming``: the outcome docs in ``docsHome`` at the head
whose text names the row id as a word (``CAP-12``, not inside ``CAP-123``).

Beside the rows: each outcome doc in ``docsHome`` or one folder below it (a
README is not one) that the change added, removed (a doc renamed out counts)
or changed, with its status before and after and whether §0 changed; the
entries of the map's ``leftOut`` list (tests left without a row on purpose)
the change added or removed, matched by test; and the changed files no row
names or cites and no ``leftOut`` entry names (``unhomed``) -- code with no
capability behind it, or a row that forgot to name it. Prose files among them
(Markdown, text) are listed apart (``prose``): no row is expected to name a
note or a learning. ``docsHome`` is
``--docs-home``, else the config's, else the folder orient detects.

The map file comes from ``--map``, else ``map.file``, else the starter reader
rule ``check.py`` uses (``map.json`` beside ``capability_find.py``). When the
change moved the map (a rename, or a config at the merge base that names
another file), the base map is read at its path there (``map.basePath``). A
project with no map gets the docs and the files, and no rows. A base map that
does not parse is a warning (``warnings``) and reads as empty, so each row at
the head is added; a repeated row id or scenario id is a warning too, and the
first row of an id is the one compared. Row links point at the row's line in
the map at the head commit (a minified map links each row to line 1), on
``--repo-url``, else the GitHub repository ``map.issueTracker`` names, else an
``origin`` remote on github.com; with none of these, rows are named without
links.

``--markdown`` stays well under GitHub's 65,536-character body limit: at most
40 moved rows, 40 touched ids, 40 scenario lines, 40 docs and 40 ``leftOut``
entries, 15 unhomed files and 15 warnings, each list then closed by one line,
"and N more; run changed_rows.py --json for the full list"; long text is
clipped, and past 50,000 characters the block ends with a line that says it
was cut. ``--json`` is always complete.

``--link ID`` (repeatable) prints, for each row id, the id and its link at
``--head`` on one line, and nothing else: `issue` mode links rows at the
default branch this way. For a row whose ``doc`` is null the line goes on
with ``docs:`` and the outcome docs that name it, as ``docsNaming`` lists
them. An id not in the map there is a usage error.

**A tiny claim.** ``--size tiny``, or ``--body FILE`` with a pull request body whose
``Size:`` line says tiny (``references/sizing.md``: tiny never changes what a row
promises and never touches a protected category), checks the claim against the
diff. The report's ``size`` gives the claim, where it came from and what it
``touches``: a row whose scenarios the change adds, removes or changes (a row
added or removed with its scenarios too), an outcome doc whose §0 or §6 changed
(a doc added or removed changes both), a migration or schema file (a
``migrations/``, ``alembic/versions/`` or ``db/migrate/`` folder, a ``.prisma``
file, ``schema.rb``, ``structure.sql`` or another ``*schema*.sql``), a path the
config's ``protectedPaths`` lists, and a change to that list itself. The list is
read from the config as it was at the merge base (plus any the head adds), so a
change cannot shrink the list that checks it. Anything there fails the run: "sized tiny, but touches ...; size it again",
exit 1, after the report. Another size, or no ``Size:`` line, checks nothing.

Exit 0 on a report (whatever it holds), 1 when a tiny claim touches a promise or a
protected path, 2 on a usage error: an unknown ref, a
folder that is not a git work tree, two refs with no merge base (in a shallow
clone the message names the fetch that deepens it), a map that does not parse
at the head, or a ``--link`` with no map, no repository URL or an unknown row.
Deterministic; stdlib only; no network (git runs locally).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import posixpath
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import check  # noqa: E402  (sibling-script import; see path insert above)
import diff_outcome  # noqa: E402
import lint_outcome  # noqa: E402
import map_features  # noqa: E402
import map_report  # noqa: E402
import orient  # noqa: E402
import lint_github_text  # noqa: E402

SCENARIO_KEYS = ("given", "when", "then", "altitude", "at")
# Row keys diff_row reports under their own names, and a comment it skips;
# any other top-level key that differs is listed in ``fields``.
OWN_KEYS = ("id", "story", "scenarios", "surfaces", "doc", "verdict", "feature", "area", "$comment")
# A path a row names in its own words: at least one folder, a file name with
# an extension, and an optional :line or :line-line after it.
NAMED_PATH_RE = re.compile(r"(?<![\w./-])((?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]{1,8})(?::\d+(?:-\d+)?)?")
# A file a row names by its bare name: no folder, an extension, an optional
# :line (group 2) after it.
BARE_NAME_RE = re.compile(r"(?<![\w./-])(\.?[\w-][\w.-]*\.[A-Za-z0-9]{1,8})(?![\w/-])(?::(\d+)(?:-\d+)?)?")
ROW_ID_KEY_RE = re.compile(r'"id"\s*:\s*"([^"]+)"')
GITHUB_REMOTE_RE = re.compile(
    r"^(?:https?://(?:[^@/]+@)?github\.com/|git@github\.com:|ssh://git@github\.com/)"
    r"(?P<repo>[\w.-]+/[\w.-]+?)(?:\.git)?/?$"
)
REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")
LIST_LIMIT = 15      # unhomed files and warnings in --markdown
# Prose outside docsHome (notes, learnings, readmes): listed apart from code,
# since no row is expected to name it.
PROSE_RE = re.compile(r"\.(?:md|mdx|markdown|txt|rst|adoc)$", re.IGNORECASE)
RELABEL_LIST = 12    # more relabelled rows than this are counted by feature in --markdown
MD_LIMIT = 40        # moved rows, touched ids, scenario lines, docs and leftOut entries in --markdown
CLIP = 160           # characters of one Then in --markdown
FIELD_LIMIT = 5      # field names in one "What moved" cell
MD_BUDGET = 50000    # characters of --markdown, whatever the lists hold (GitHub's body limit is 65,536)
MORE = "and {n} more; run changed_rows.py --json for the full list"
CUT = "The rest is cut to fit a pull request body; run changed_rows.py --json for the full list."


class UsageError(Exception):
    pass


def norm_path(value: str) -> str:
    """A project path in one spelling: forward slashes, no leading ``./``,
    no trailing slash ("" for the project folder itself)."""
    path = value.strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    path = posixpath.normpath(path) if path else ""
    return "" if path == "." else path


def dedupe(items: List[str]) -> List[str]:
    seen: List[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


# ---------------------------------------------------------------------------
# git
# ---------------------------------------------------------------------------


def git(cwd: str, *args: str) -> str:
    try:
        done = subprocess.run(
            ["git", "-C", cwd, *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except OSError as exc:
        raise UsageError(f"cannot run git: {exc}")
    if done.returncode != 0:
        raise UsageError(f"git {' '.join(args)}: {(done.stderr or '').strip() or 'failed'}")
    return done.stdout


def resolve(cwd: str, ref: str) -> str:
    try:
        return git(cwd, "rev-parse", "--verify", "--quiet", ref + "^{commit}").strip()
    except UsageError:
        raise UsageError(f"unknown git ref {ref!r} (fetch it first)")


def show(cwd: str, sha: str, path: str) -> Optional[str]:
    """The file's text at ``sha`` (``path`` from the top of the work tree),
    or None when it did not exist there."""
    try:
        done = subprocess.run(
            ["git", "-C", cwd, "show", f"{sha}:{path}"], capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
    except OSError as exc:
        raise UsageError(f"cannot run git: {exc}")
    if done.returncode != 0:
        return None
    return done.stdout.lstrip("\ufeff").replace("\r\n", "\n")


def changed_files(cwd: str, base: str, head: str) -> List[Dict[str, str]]:
    """``[{"path", "status", "from"}]`` for each file the change touched,
    renames and copies followed (``from`` is the path before, else empty).
    Paths are from the top of the work tree, NUL-separated by git, so none
    comes back quoted."""
    out = git(cwd, "diff", "--name-status", "-z", "-M", "--no-color", base, head)
    parts = out.split("\0")
    files: List[Dict[str, str]] = []
    i = 0
    while i < len(parts):
        status = parts[i][:1]
        if not status:
            i += 1
            continue
        if status in "RC" and i + 2 < len(parts):
            files.append({"path": parts[i + 2], "status": status, "from": parts[i + 1]})
            i += 3
        elif i + 1 < len(parts):
            files.append({"path": parts[i + 1], "status": status, "from": ""})
            i += 2
        else:
            break
    return files


def tree_files(cwd: str, sha: str) -> List[str]:
    """Every file in the tree at ``sha``, from the top of the work tree."""
    out = git(cwd, "ls-tree", "-r", "--name-only", "-z", "--full-tree", sha)
    return [p for p in out.split("\0") if p]


def merge_base_of(top: str, args: argparse.Namespace, base_sha: str, head_sha: str) -> str:
    try:
        return git(top, "merge-base", base_sha, head_sha).strip()
    except UsageError:
        pass
    try:
        shallow = git(top, "rev-parse", "--is-shallow-repository").strip() == "true"
    except UsageError:
        shallow = False
    if shallow:
        raise UsageError(
            f"no merge base of {args.base} and {args.head} in this shallow clone; fetch more history "
            "(git fetch --deepen=<n>, or git fetch --unshallow) and run again")
    raise UsageError(f"{args.base} and {args.head} share no history")


# ---------------------------------------------------------------------------
# the project
# ---------------------------------------------------------------------------


class Project:
    """The project folder, the git work tree it sits in, and its config."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.cwd = os.path.abspath(args.cwd or os.getcwd())
        try:
            self.top = git(self.cwd, "rev-parse", "--show-toplevel").strip()
            self.prefix = git(self.cwd, "rev-parse", "--show-prefix").strip()
        except UsageError:
            raise UsageError(f"{self.cwd} is not inside a git work tree")
        config, config_path, _warnings = check.load_project_config(self.cwd, args.config)
        self.config = config if isinstance(config, dict) else None
        self.config_path = config_path
        map_value = self.config.get("map") if self.config else None
        self.map_value = map_value if isinstance(map_value, dict) else None

    def repo(self, path: str) -> str:
        """A project path as git names it, from the top of the work tree."""
        return self.prefix + path

    def local(self, path: str) -> Optional[str]:
        """A path from the top of the work tree as a project path, or None
        when it lies outside the project folder."""
        if not self.prefix:
            return path
        return path[len(self.prefix):] if path.startswith(self.prefix) else None

    def config_in_project(self) -> Optional[str]:
        """The config's project path, when it sits inside the project."""
        if not self.config_path:
            return None
        try:
            rel = os.path.relpath(os.path.abspath(self.config_path), self.cwd).replace(os.sep, "/")
        except ValueError:
            return None
        return None if rel == ".." or rel.startswith("../") else rel


def project_files(proj: Project, files: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], List[str]]:
    """The changed files as project paths, and the ones outside the project.
    A file moved out of the project reads as deleted, one moved in as added."""
    inside: List[Dict[str, str]] = []
    outside: List[str] = []
    for f in files:
        path = proj.local(f["path"])
        before = proj.local(f["from"]) if f["from"] else None
        if path is None:
            outside.append(f["path"])
            if before is not None and f["status"] == "R":
                inside.append({"path": before, "status": "D", "from": ""})
            continue
        if f["from"] and before is None:
            inside.append({"path": path, "status": "A", "from": ""})
            continue
        inside.append({"path": path, "status": f["status"], "from": before or ""})
    return inside, outside


def docs_home_of(args: argparse.Namespace, proj: Project) -> Optional[str]:
    """``--docs-home``, else the config's docsHome, else the folder orient detects."""
    if args.docs_home is not None:
        value: Optional[str] = args.docs_home
    else:
        value, _how = orient.resolve_docs_home(proj.cwd, proj.config, [])
    if not isinstance(value, str) or not value.strip():
        return None
    return norm_path(value)


def locate_map(args: argparse.Namespace, map_value: Optional[dict]) -> Tuple[Optional[str], str]:
    if args.map:
        return norm_path(args.map), "--map"
    if isinstance(map_value, dict):
        path, how = check.map_file(map_value)
        return (norm_path(path) if path else None), how
    return None, "no map configured"


def base_map_path(proj: Project, sha: str, map_path: str, files: List[Dict[str, str]]) -> str:
    """Where the map was at ``sha`` when the change moved it: the path a
    rename came from, else the file the config there names; else ``map_path``."""
    for f in files:
        if f["status"] == "R" and f["path"] == map_path and f["from"]:
            return f["from"]
    rel = proj.config_in_project()
    candidates = [rel] if rel else [".claude/promise.config.json", "promise.config.json"]
    text = None
    for candidate in candidates:
        text = show(proj.top, sha, proj.repo(candidate))
        if text is not None:
            break
    try:
        raw = json.loads(text) if text else None
    except ValueError:
        raw = None
    map_value = raw.get("map") if isinstance(raw, dict) else None
    if isinstance(map_value, dict):
        path, _how = check.map_file(map_value)
        if path:
            return norm_path(path)
    return map_path


# ---------------------------------------------------------------------------
# the map
# ---------------------------------------------------------------------------


def parse_map(text: Optional[str], where: str, warnings: Optional[List[str]] = None
              ) -> Tuple[Optional[Dict[str, Dict[str, Any]]], List[Dict[str, Any]]]:
    """Rows by id (None when the map did not exist there), and the map's
    ``leftOut`` entries. A repeated id keeps its first row, with a warning."""
    if text is None:
        return None, []
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise UsageError(f"the map at {where} does not parse: {exc}")
    rows = data.get("rows") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise UsageError(f"the map at {where} has no 'rows' list")
    clash = map_features.conflicts(data, rows)
    if clash:
        raise UsageError(f"the map at {where}: " + "; ".join(clash))
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        if not isinstance(r, dict) or r.get("id") is None:
            continue
        if "area" in r:  # the alias reads as the primary key
            r = {("feature" if k == "area" else k): v for k, v in r.items()}
        rid = str(r["id"])
        if rid in out:
            if warnings is not None:
                warnings.append(f"the map at {where} has more than one row with id {rid}; the first is compared")
            continue
        out[rid] = r
    left_out = data.get("leftOut") if isinstance(data, dict) else None
    if left_out is not None and not isinstance(left_out, list) and warnings is not None:
        warnings.append(f"the map at {where} has a leftOut that is not a list; it is read as empty")
    return out, [e for e in left_out if isinstance(e, dict)] if isinstance(left_out, list) else []


def parse_rows(text: Optional[str], where: str,
               warnings: Optional[List[str]] = None) -> Optional[Dict[str, Dict[str, Any]]]:
    """Rows by id, or None when the map did not exist there."""
    return parse_map(text, where, warnings)[0]


def parse_features(text: Optional[str]) -> Dict[str, Dict[str, Any]]:
    """The map's top-level ``features`` (or ``areas``) by id (empty when there
    are none, or the map does not parse)."""
    try:
        data = json.loads(text) if text else None
    except ValueError:
        return {}
    return map_features.features_by_id(data)


def features_of(rows_out: List[Dict[str, Any]], known: Dict[str, Dict[str, Any]],
             relabelled: bool = False) -> List[Dict[str, Any]]:
    """The features of the rows a change moved or touched, each with its name,
    its plain sentence and those rows; most rows first. Rows with no feature
    share one entry with a null id. With ``relabelled``, the new features of
    the rows whose feature alone changed."""
    groups: Dict[Optional[str], List[str]] = {}
    for r in rows_out:
        if (r["change"] == "relabelled") != relabelled:
            continue
        key = r.get("feature") if isinstance(r.get("feature"), str) else None
        groups.setdefault(key, []).append(r["id"])
    out = []
    for key, ids in groups.items():
        meta = known.get(key) if key is not None else None
        out.append({"id": key, "name": (meta or {}).get("name"), "plain": (meta or {}).get("plain"), "rows": ids})
    out.sort(key=lambda a: (a["id"] is None, -len(a["rows"]), str(a["name"] or a["id"] or "")))
    return out


def id_key(rid: Any) -> Tuple[Any, ...]:
    """A row id's sort key: CAP-2 before CAP-10."""
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in re.split(r"(\d+)", str(rid)) if p)


def diff_left_out(before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """The ``leftOut`` entries the change added and removed, matched by test."""
    def key(entry: Dict[str, Any]) -> str:
        return json.dumps(entry.get("test"), sort_keys=True)
    was, now = {key(e) for e in before}, {key(e) for e in after}
    return {"added": [e for e in after if key(e) not in was], "removed": [e for e in before if key(e) not in now]}


def lane_names(lanes: Dict[str, str]) -> List[str]:
    return dedupe(list(lanes.values()))


def then_text(sc: Dict[str, Any]) -> str:
    return " ".join(str(sc.get("then") or "").split())


def split_scenarios(row: Dict[str, Any], rid: str, where: str,
                    warnings: List[str]) -> Tuple[Dict[str, Tuple[int, Dict[str, Any]]],
                                                  List[Tuple[int, Dict[str, Any], str]]]:
    """The row's scenarios keyed by id, as (position, scenario); and the rest
    -- no id, or an id an earlier scenario holds -- as (position, scenario,
    label), the label ``#n`` or ``id#n`` by 1-based position."""
    by_id: Dict[str, Tuple[int, Dict[str, Any]]] = {}
    loose: List[Tuple[int, Dict[str, Any], str]] = []
    for n, sc in enumerate(row.get("scenarios") or []):
        if not isinstance(sc, dict):
            continue
        sid = "" if sc.get("id") is None else str(sc.get("id"))
        if sid and sid not in by_id:
            by_id[sid] = (n, sc)
            continue
        if sid:
            warnings.append(f"{rid} has more than one scenario with id {sid} at {where}; "
                            "each after the first is matched by its Then")
        loose.append((n, sc, f"{sid}#{n + 1}" if sid else f"#{n + 1}"))
    return by_id, loose


def pair_loose(old: List[Tuple[int, Dict[str, Any], str]], new: List[Tuple[int, Dict[str, Any], str]]):
    """Scenarios without an id, paired by their Then text, in order among
    equal Thens. One left on each side is the same scenario, edited."""
    pairs = []
    free = list(new)
    gone = []
    for item in old:
        match = next((x for x in free if then_text(x[1]) == then_text(item[1])), None)
        if match is None:
            gone.append(item)
        else:
            pairs.append((item, match))
            free = [x for x in free if x[0] != match[0]]
    if len(gone) == 1 and len(free) == 1:
        pairs.append((gone[0], free[0]))
        gone, free = [], []
    return pairs, gone, free


def short_scenario(sc_id: str, sc: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": sc_id, "then": sc.get("then"), "altitude": sc.get("altitude")}


def all_scenarios(row: Dict[str, Any], rid: str, where: str, warnings: List[str]) -> List[Dict[str, Any]]:
    by_id, loose = split_scenarios(row, rid, where, warnings)
    items = [(n, i, sc) for i, (n, sc) in by_id.items()] + [(n, label, sc) for n, sc, label in loose]
    return [short_scenario(label, sc) for _n, label, sc in sorted(items, key=lambda t: t[0])]


def citation_files(row: Dict[str, Any], lanes: List[str]) -> List[str]:
    files: List[str] = []
    for lane in lanes:
        for citation in row.get(lane) or []:
            file, _name = map_report.split_citation(citation)
            if file:
                files.append(norm_path(file))
    return dedupe(files)


def row_text(row: Dict[str, Any]) -> str:
    parts = [str(row.get("story") or "")]
    for sc in row.get("scenarios") or []:
        if isinstance(sc, dict):
            parts.extend(str(sc.get(k) or "") for k in ("given", "when", "then"))
    return "\n".join(parts)


def text_refs(row: Dict[str, Any]) -> Tuple[List[str], Dict[str, bool]]:
    """The files a row's text names: paths with a folder, and bare file names
    (each True when some mention of it carries a ``:line``)."""
    text = row_text(row)
    paths = sorted({m.group(1) for m in NAMED_PATH_RE.finditer(text)})
    bare: Dict[str, bool] = {}
    for m in BARE_NAME_RE.finditer(text):
        bare[m.group(1)] = bare.get(m.group(1), False) or m.group(2) is not None
    return paths, bare


def names_file(named: str, path: str) -> bool:
    return path == named or path.endswith("/" + named)


def names_changed(path: str, paths: List[str], bare: Dict[str, bool], unique: Set[str]) -> bool:
    """True when a row's text names ``path``: by a path with a folder, or by
    its bare name with a ``:line`` or held by no other file."""
    if any(names_file(n, path) for n in paths):
        return True
    name = posixpath.basename(path)
    return name in bare and (bare[name] or name in unique)


def unique_names(paths: Set[str]) -> Set[str]:
    counts: Dict[str, int] = {}
    for p in paths:
        name = posixpath.basename(p)
        counts[name] = counts.get(name, 0) + 1
    return {name for name, n in counts.items() if n == 1}


def diff_row(before: Dict[str, Any], after: Dict[str, Any], lanes: List[str],
             rid: str = "", warnings: Optional[List[str]] = None) -> Dict[str, Any]:
    """What changed inside one row; empty dict when nothing did."""
    warnings = [] if warnings is None else warnings
    delta: Dict[str, Any] = {}
    if (before.get("story") or "") != (after.get("story") or ""):
        delta["storyChanged"] = True
    old_ids, old_loose = split_scenarios(before, rid, "the merge base", warnings)
    new_ids, new_loose = split_scenarios(after, rid, "the head", warnings)
    pairs, gone, fresh = pair_loose(old_loose, new_loose)
    added = [(n, short_scenario(i, sc)) for i, (n, sc) in new_ids.items() if i not in old_ids]
    added += [(n, short_scenario(label, sc)) for n, sc, label in fresh]
    removed = [(n, short_scenario(i, sc)) for i, (n, sc) in old_ids.items() if i not in new_ids]
    removed += [(n, short_scenario(label, sc)) for n, sc, label in gone]
    matched = [(i, old_ids[i][1], n, sc) for i, (n, sc) in new_ids.items() if i in old_ids]
    matched += [(new[2], old[1], new[0], new[1]) for old, new in pairs]
    changed = []
    for label, was, n, sc in matched:
        keys = [k for k in SCENARIO_KEYS if was.get(k) != sc.get(k)]
        if keys:
            changed.append((n, {"id": label, "fields": keys,
                                "then": {"before": was.get("then"), "after": sc.get("then")},
                                "altitude": sc.get("altitude")}))
    if added or removed or changed:
        delta["scenarios"] = {part: [x for _n, x in sorted(items, key=lambda t: t[0])]
                              for part, items in (("added", added), ("removed", removed), ("changed", changed))}
    evidence: Dict[str, Dict[str, List[str]]] = {"added": {}, "removed": {}}
    for lane in lanes:
        was_c = [json.dumps(c, sort_keys=True) if not isinstance(c, str) else c for c in before.get(lane) or []]
        now_c = [json.dumps(c, sort_keys=True) if not isinstance(c, str) else c for c in after.get(lane) or []]
        plus = [c for c in now_c if c not in was_c]
        minus = [c for c in was_c if c not in now_c]
        if plus:
            evidence["added"][lane] = plus
        if minus:
            evidence["removed"][lane] = minus
    if evidence["added"] or evidence["removed"]:
        delta["evidence"] = evidence
    s_old = dedupe([str(s) for s in before.get("surfaces") or []])
    s_new = dedupe([str(s) for s in after.get("surfaces") or []])
    if set(s_old) != set(s_new):
        delta["surfaces"] = {"added": [s for s in s_new if s not in s_old],
                             "removed": [s for s in s_old if s not in s_new]}
    if before.get("doc") != after.get("doc"):
        delta["doc"] = {"before": before.get("doc"), "after": after.get("doc")}
    if before.get("verdict") != after.get("verdict"):
        delta["verdictMoved"] = True
    if before.get("feature") != after.get("feature"):
        delta["featureChanged"] = {"before": before.get("feature"), "after": after.get("feature")}
    own = set(OWN_KEYS) | set(lanes)
    fields = sorted(k for k in set(before) | set(after) if k not in own and before.get(k) != after.get(k))
    if fields:
        delta["fields"] = fields
    return delta


def row_lines(text: Optional[str]) -> Dict[str, int]:
    """The 1-based line of each ``"id"`` value in the map's text, the first
    time it appears; every id on a line counts, so a minified map links each
    row to line 1."""
    lines: Dict[str, int] = {}
    if not text:
        return lines
    for n, line in enumerate(text.splitlines(), start=1):
        for m in ROW_ID_KEY_RE.finditer(line):
            lines.setdefault(m.group(1), n)
    return lines


# ---------------------------------------------------------------------------
# docs
# ---------------------------------------------------------------------------


def doc_facts(text: Optional[str]) -> Dict[str, Any]:
    if text is None:
        return {"title": None, "status": None}
    lines = text.splitlines()
    title = next((m.group(1) for m in (re.match(r"^#\s+(.+?)\s*$", ln) for ln in lines) if m), None)
    return {"title": title, "status": lint_outcome.get_status(lines)}


def is_outcome_doc(text: Optional[str]) -> bool:
    """A ``Status:`` line or a §0 heading outside any code fence."""
    if text is None:
        return False
    lines = text.splitlines()
    return lint_outcome.get_status(lines) is not None \
        or any(ln.startswith(orient.TLDR_HEADING) for ln in orient.unfenced(lines))


def in_docs_home(path: str, docs_home: Optional[str]) -> bool:
    """A ``.md`` file in ``docs_home`` or one folder below it, a README aside."""
    if docs_home is None or not path.endswith(".md") or posixpath.basename(path).lower() == "readme.md":
        return False
    folder = posixpath.dirname(path)
    return folder == docs_home or (folder != "" and posixpath.dirname(folder) == docs_home)


def diff_docs(proj: Project, base: str, head: str, files: List[Dict[str, str]],
              docs_home: Optional[str]) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for f in files:
        before_path = f["from"] if f["status"] == "R" and f["from"] else f["path"]
        before_in, after_in = in_docs_home(before_path, docs_home), in_docs_home(f["path"], docs_home)
        if not before_in and not after_in:
            continue
        before = show(proj.top, base, proj.repo(before_path)) if before_in else None
        after = show(proj.top, head, proj.repo(f["path"])) if after_in and f["status"] != "D" else None
        if not is_outcome_doc(before) and not is_outcome_doc(after):
            continue
        a, b = doc_facts(before), doc_facts(after)
        change = "added" if before is None else "removed" if after is None else "changed"
        section0 = bool(before is not None and after is not None
                        and [t for _, t in diff_outcome.protected_lines(before)]
                        != [t for _, t in diff_outcome.protected_lines(after)])
        entry: Dict[str, Any] = {
            "path": f["path"] if after_in else before_path, "change": change, "title": b["title"] or a["title"],
            "status": {"before": a["status"], "after": b["status"]}, "section0Changed": section0,
            "section6Changed": bool(before is not None and after is not None
                                    and section_lines(before, 6) != section_lines(after, 6)),
        }
        if f["status"] == "R" and f["from"]:
            entry["renamed"] = {"from": f["from"], "to": f["path"]}
        docs.append(entry)
    return docs


def section_lines(text: str, n: int) -> List[str]:
    """The non-blank lines of a doc's ``## n.`` section, spaces evened out."""
    lines = text.splitlines()
    bounds = lint_outcome.section_bounds(lines, n)
    if bounds is None:
        return []
    return [re.sub(r"\s+", " ", ln).strip() for ln in lines[bounds[0] + 1:bounds[1]] if ln.strip()]


# ---------------------------------------------------------------------------
# a tiny claim
# ---------------------------------------------------------------------------

SIZES = lint_github_text.SIZES
# A migration folder (migrations/, migration/, alembic/versions/, db/migrate/), a
# .prisma file, or a database schema dump (schema.rb, structure.sql, any *schema*.sql);
# a JSON schema or a test named like schema is not one.
MIGRATION_RE = re.compile(r"(?:^|/)(?:migrations?|alembic/versions|db/migrate)/"
                          r"|(?:^|/)[\w.-]*schema[\w.-]*\.sql$|(?:^|/)(?:schema\.rb|structure\.sql)$|\.prisma$",
                          re.IGNORECASE)


def size_claim(args: argparse.Namespace) -> Tuple[Optional[str], Optional[str]]:
    """(the size, where it came from): ``--size``, else the ``Size:`` line of ``--body``."""
    if args.size:
        return args.size, "--size"
    if not args.body:
        return None, None
    try:
        if args.body == "-":
            text = sys.stdin.read()
        else:
            with open(args.body, "r", encoding="utf-8-sig") as fh:
                text = fh.read()
    except OSError as exc:
        raise UsageError(f"cannot read --body {args.body}: {exc}")
    said = [lint_github_text.canonical_size(word)
            for _n, word in lint_github_text.size_lines(text.replace("\r\n", "\n"))
            if lint_github_text.canonical_size(word) in SIZES]
    # any tiny claim is checked as tiny: a second Size line never hides one
    if "tiny" in said:
        return "tiny", "--body"
    return (said[0], "--body") if said else (None, "--body")


def _protected_list(value: Any, warnings: List[str]) -> List[str]:
    """A ``protectedPaths`` value as project-relative path patterns."""
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        warnings.append("protectedPaths is not a list of path patterns; it is left out")
        return []
    # a leading "/" (the gitignore and CODEOWNERS habit) means the project root
    return [norm_path(v.strip().lstrip("/")) + ("/" if v.strip().endswith("/") else "") for v in value]


def _config_at(proj: "Project", sha: str) -> Tuple[bool, Any]:
    """(found, the config's ``protectedPaths``) in the config file as it was at
    ``sha``; not found when the config sits outside the work tree, did not
    exist there, or does not parse."""
    if not proj.config_path:
        return False, None
    rel = os.path.relpath(os.path.abspath(proj.config_path), proj.top).replace(os.sep, "/")
    if rel == ".." or rel.startswith("../"):
        return False, None
    text = show(proj.top, sha, rel)
    if text is None:
        return False, None
    try:
        data = json.loads(text)
    except ValueError:
        return False, None
    return True, (data.get("protectedPaths") if isinstance(data, dict) else None)


def _base_config_elsewhere(proj: "Project", sha: str) -> Tuple[bool, Any]:
    """The merge base's ``protectedPaths`` from either place a config lives
    (``.claude/promise.config.json``, then ``promise.config.json``, beside the
    project's folder), so a change that moves the config still meets the list it had."""
    prefix = proj.prefix or ""
    for name in (".claude/promise.config.json", "promise.config.json"):
        text = show(proj.top, sha, prefix + name)
        if text is None:
            continue
        try:
            data = json.loads(text)
        except ValueError:
            continue
        return True, (data.get("protectedPaths") if isinstance(data, dict) else None)
    return False, None


def protected_paths(proj: "Project", merge_base: str, head_sha: str,
                    warnings: List[str]) -> Tuple[List[str], Optional[str]]:
    """The patterns a tiny claim may not touch, and the touch a change to the
    list itself makes (or None). The list is the merge base's config, so a
    change cannot shrink the list that checks it; the head's own list is added
    to it, since a wider list only checks more. The touch is a pattern the merge
    base had and the head dropped."""
    base_found, base_value = _config_at(proj, merge_base)
    if not base_found:
        base_found, base_value = _base_config_elsewhere(proj, merge_base)
    head_found, head_value = _config_at(proj, head_sha)
    if not head_found:
        head_value = (proj.config or {}).get("protectedPaths")
    patterns = dedupe(_protected_list(base_value, warnings) + _protected_list(head_value, warnings))
    changed = None
    # Only a shrink is a touch: a wider list checks more. A config git cannot read at
    # the merge base (outside the work tree, or new in this change) has nothing to shrink.
    kept = set(_protected_list(head_value, []))
    if base_found and any(p not in kept for p in _protected_list(base_value, [])):
        where = proj.config_in_project() or "the config"
        changed = f"{where} protectedPaths (the list of protected paths itself changed)"
    return patterns, changed


def is_protected(path: str, patterns: List[str]) -> Optional[str]:
    """The first pattern that covers the path: a glob (``*`` crosses folders),
    or a folder, with everything below it."""
    for pat in patterns:
        folder = pat.rstrip("/")
        if fnmatch.fnmatchcase(path, pat) or fnmatch.fnmatchcase(path, folder + "/*"):
            return pat
    return None


def tiny_touches(rows_out: List[Dict[str, Any]], docs: List[Dict[str, Any]], files: List[Dict[str, str]],
                 patterns: List[str], outside: Optional[List[str]] = None,
                 policies: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    """What a change sized tiny may not touch, one plain item each."""
    out: List[str] = []
    out.extend(f"service policy {p['id']} ({p['change']})" for p in policies or [])
    for r in rows_out:
        if "servicePolicyRefs" in r.get("fields", []):
            out.append(f"{r['id']}'s service policy references")
        if r["change"] in ("added", "removed") and r.get("scenarioCount"):
            out.append(f"{r['id']}'s scenarios (the row is {r['change']})")
        elif r.get("scenarios"):
            out.append(f"{r['id']}'s scenarios")
    for d in docs:
        if d["change"] in ("added", "removed"):
            out.append(f"{d['path']} §0 and §6 (the doc is {d['change']})")
            continue
        parts = [p for p, key in (("§0", "section0Changed"), ("§6", "section6Changed")) if d.get(key)]
        if parts:
            out.append(f"{d['path']} {' and '.join(parts)}")
    for f in files:
        for p in dict.fromkeys([f["path"]] + ([f["from"]] if f.get("from") else [])):
            if MIGRATION_RE.search(p):
                out.append(f"{p} (a migration or schema file)")
            pat = is_protected(p, patterns)
            if pat:
                out.append(f"{p} (protected: {pat})")
    for p in outside or []:
        # outside the project folder, but in the same change: a migration still counts
        if MIGRATION_RE.search(p):
            out.append(f"{p} (a migration or schema file, outside the project folder)")
    return dedupe(out)


def service_policies(text: Optional[str], warnings=None, where="head", base_text=None, tolerant=False) -> Dict[str, Any]:
    """Ignore historical malformed groups; reject newly introduced malformed data."""
    def raw(source):
        try:
            data = json.loads(source) if source else {}
        except (ValueError, TypeError):
            return []  # parse_map diagnoses bad JSON independently.
        return data.get("servicePolicies", []) if isinstance(data, dict) else []

    values, previous = raw(text), raw(base_text)
    def same(left, right):
        return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)
    def bad(message, inherited):
        if not tolerant and not inherited:
            raise UsageError(f"{where}: {message}")
        if warnings is not None:
            warnings.append(f"{where}: {message}; malformed service policies read as empty")
    if not isinstance(values, list):
        bad("servicePolicies must be an array", same(values, previous))
        return {}
    previous = previous if isinstance(previous, list) else []
    groups, invalid = {}, []
    for value in values:
        if not isinstance(value, dict) or not isinstance(value.get("id"), str) or not value["id"].strip():
            invalid.append(value)
        else:
            groups.setdefault(value["id"], []).append(value)
    out = {}
    for pid, group in groups.items():
        if len(group) == 1:
            out[pid] = group[0]
        else:
            inherited = [v for v in previous if isinstance(v, dict) and v.get("id") == pid]
            bad("servicePolicies has duplicate ids", same(group, inherited))
    if invalid:
        old_invalid = [v for v in previous if not isinstance(v, dict) or not isinstance(v.get("id"), str) or not v["id"].strip()]
        bad("servicePolicies has entries without non-empty ids", same(invalid, old_invalid))
    return out


class DocsNaming:
    """The outcome docs in docsHome at one commit, read once, searched by row id."""

    def __init__(self, proj: Project, sha: str, docs_home: Optional[str], tree: Optional[List[str]] = None):
        self.proj, self.sha, self.docs_home, self.tree = proj, sha, docs_home, tree
        self.texts: Optional[List[Tuple[str, str]]] = None

    def load(self) -> List[Tuple[str, str]]:
        if self.texts is None:
            self.texts = []
            if self.docs_home is not None:
                if self.tree is None:
                    local = (self.proj.local(p) for p in tree_files(self.proj.top, self.sha))
                    self.tree = [p for p in local if p is not None]
                for path in sorted(p for p in self.tree if in_docs_home(p, self.docs_home)):
                    text = show(self.proj.top, self.sha, self.proj.repo(path))
                    if text is not None and is_outcome_doc(text):
                        self.texts.append((path, text))
        return self.texts

    def naming(self, rid: str) -> List[str]:
        word = re.compile(r"(?<![\w-])" + re.escape(rid) + r"(?![\w-])")
        return [path for path, text in self.load() if word.search(text)]


def doc_is_null(row: Dict[str, Any]) -> bool:
    doc = row.get("doc")
    return not isinstance(doc, str) or not doc.strip()


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------


def repo_url(args: argparse.Namespace, cwd: str, map_value: Optional[dict]) -> Optional[str]:
    if args.repo_url:
        return args.repo_url.rstrip("/")
    tracker = map_value.get("issueTracker") if isinstance(map_value, dict) else None
    if isinstance(tracker, dict) and tracker.get("kind") == "github" \
            and isinstance(tracker.get("repo"), str) and REPO_RE.match(tracker["repo"]):
        return f"https://github.com/{tracker['repo']}"
    try:
        remote = git(cwd, "remote", "get-url", "origin").strip()
    except UsageError:
        return None
    m = GITHUB_REMOTE_RE.match(remote)
    return f"https://github.com/{m.group('repo')}" if m else None


def row_links(args: argparse.Namespace) -> List[Tuple[str, str, List[str]]]:
    """(id, link, the docs naming it when its doc is null) for each ``--link``."""
    proj = Project(args)
    map_path, how = locate_map(args, proj.map_value)
    if not map_path:
        raise UsageError(f"--link needs a map: {how}")
    url = repo_url(args, proj.top, proj.map_value)
    if not url:
        raise UsageError("--link needs a repository URL: pass --repo-url, set map.issueTracker, "
                         "or use an origin remote on github.com")
    head_sha = resolve(proj.top, args.head)
    text = show(proj.top, head_sha, proj.repo(map_path))
    rows = parse_rows(text, args.head)
    if rows is None:
        raise UsageError(f"no map at {map_path} in {args.head}")
    lines = row_lines(text)
    naming = DocsNaming(proj, head_sha, docs_home_of(args, proj))
    out = []
    for rid in args.link:
        if rid not in rows or rid not in lines:
            raise UsageError(f"{rid} is not a row in the map at {args.head}")
        docs = naming.naming(rid) if doc_is_null(rows[rid]) else []
        out.append((rid, f"{url}/blob/{head_sha}/{proj.repo(map_path)}#L{lines[rid]}", docs))
    return out


def build_report(args: argparse.Namespace) -> Dict[str, Any]:
    proj = Project(args)
    top = proj.top
    warnings: List[str] = []
    docs_home = docs_home_of(args, proj)

    base_sha = resolve(top, args.base)
    head_sha = resolve(top, args.head)
    merge_base = merge_base_of(top, args, base_sha, head_sha)
    all_files = changed_files(top, merge_base, head_sha)
    files, outside = project_files(proj, all_files)
    paths = [f["path"] for f in files]
    moved_from = {f["from"] for f in files if f["status"] == "R" and f["from"]}
    tree = [p for p in (proj.local(t) for t in tree_files(top, head_sha)) if p is not None]
    tree_set = set(tree)
    unique = unique_names(tree_set | set(paths) | {f["from"] for f in files if f["from"]})
    touched_paths = set(paths) | moved_from

    map_path, map_how = locate_map(args, proj.map_value)
    lanes_by_altitude = map_report.load_lanes(proj.config_path) if proj.config_path else dict(map_report.DEFAULT_LANES)
    lanes = lane_names(lanes_by_altitude)
    proof_lanes = [lane for lane in lanes if lane != lanes_by_altitude.get("sibling")]
    rows_out: List[Dict[str, Any]] = []
    left_out: Dict[str, List[Dict[str, Any]]] = {"added": [], "removed": []}
    map_info: Optional[Dict[str, Any]] = None
    known_features: Dict[str, Dict[str, Any]] = {}
    homed: Set[str] = set()
    policy_changes: List[Dict[str, Any]] = []
    map_disabled = None
    if not map_path:
        base_path = base_map_path(proj, merge_base, "", files)
        if base_path:
            map_disabled = f"{base_path} (map configured at merge base, disabled or unset at head)"
    if map_path:
        head_text = show(top, head_sha, proj.repo(map_path))
        after_rows, left_after = parse_map(head_text, args.head, warnings)
        after_rows = after_rows or {}
        base_path = map_path
        base_text = show(top, merge_base, proj.repo(map_path))
        if base_text is None:
            base_path = base_map_path(proj, merge_base, map_path, files)
            if base_path != map_path:
                base_text = show(top, merge_base, proj.repo(base_path))
        where = f"{args.base} (merge base)"
        try:
            before_rows, left_before = parse_map(base_text, where, warnings)
        except UsageError as exc:
            warnings.append(f"{exc}; it reads as empty, so each row at the head is added")
            before_rows, left_before = {}, []
        before_rows = before_rows or {}
        before_policies = service_policies(base_text, warnings, where, tolerant=True)
        after_policies = service_policies(head_text, warnings, "head", base_text=base_text)
        raw_base_refs = {rid: row.get("servicePolicyRefs", []) for rid, row in before_rows.items()}
        for rid, row in before_rows.items():
            refs = row.get("servicePolicyRefs", [])
            if not isinstance(refs, list) or any(not isinstance(v, str) or not v.strip() for v in refs):
                warnings.append(f"{where}: {rid} has malformed servicePolicyRefs; base references read as empty")
                before_rows[rid] = dict(row, servicePolicyRefs=[])
        for rid, row in after_rows.items():
            refs = row.get("servicePolicyRefs", [])
            if not isinstance(refs, list) or any(not isinstance(v, str) or not v.strip() for v in refs):
                inherited = rid in raw_base_refs and json.dumps(refs, sort_keys=True) == json.dumps(raw_base_refs[rid], sort_keys=True)
                if not inherited:
                    raise UsageError(f"{rid} at head: newly malformed servicePolicyRefs must be an array of policy ids")
                warnings.append(f"head: {rid} inherits malformed servicePolicyRefs; references read as empty")
                after_rows[rid] = dict(row, servicePolicyRefs=[])
        policy_changes = [{"id": pid, "change": "added" if pid not in before_policies else
                           "removed" if pid not in after_policies else "changed"}
                          for pid in sorted(before_policies.keys() | after_policies.keys())
                          if before_policies.get(pid) != after_policies.get(pid)]
        known_features = dict(parse_features(base_text), **parse_features(head_text))
        left_out = diff_left_out(left_before, left_after)
        for entry in left_before + left_after:
            file, _name = map_report.split_citation(entry.get("test"))
            if file:
                homed.add(norm_path(file))  # a test left out on purpose has a home
        map_info = {"path": map_path, "source": map_how,
                    "atBase": base_text is not None, "atHead": head_text is not None}
        if base_path != map_path:
            map_info["basePath"] = base_path
        url = repo_url(args, top, proj.map_value)
        lines = row_lines(head_text)
        naming = DocsNaming(proj, head_sha, docs_home, tree)
        for rid in list(after_rows) + [r for r in before_rows if r not in after_rows]:
            before, after = before_rows.get(rid), after_rows.get(rid)
            row = after or before or {}
            cited = set(citation_files(row, lanes))
            ref_paths, bare = text_refs(row)
            tests_changed: List[str] = []
            files_named: List[str] = []
            files_moved: List[Dict[str, str]] = []
            for f in files:
                seen = [f["path"]] + ([f["from"]] if f["from"] else [])
                for p in seen:
                    is_cited = p in cited
                    is_named = names_changed(p, ref_paths, bare, unique)
                    if not (is_cited or is_named):
                        continue
                    homed.add(f["path"])
                    if p == f["from"] and f["status"] != "R":
                        continue  # a copy: the file the row cites is still there
                    if is_cited and p not in tests_changed:
                        tests_changed.append(p)
                    if is_named and p not in files_named:
                        files_named.append(p)
                    if p == f["from"]:
                        files_moved.append({"from": p, "to": f["path"]})
            doc_path = None if doc_is_null(row) else norm_path(row["doc"])
            doc_changed = doc_path is not None and doc_path in touched_paths
            if doc_changed:
                homed.add(doc_path)
            row_warnings: List[str] = []
            if before is None:
                change, delta = "added", {}
            elif after is None:
                change, delta = "removed", {}
            else:
                delta = diff_row(before, after, lanes, rid, row_warnings)
                refs = set()
                for r in (before, after):
                    values = r.get("servicePolicyRefs", [])
                    if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                        raise UsageError(f"{rid}: servicePolicyRefs must be an array of policy ids")
                    refs.update(values)
                affected = [f"servicePolicies.{p['id']}" for p in policy_changes if p["id"] in refs]
                if affected:
                    delta["fields"] = sorted(set(delta.get("fields", [])) | set(affected))
                promised = [k for k in delta if k != "featureChanged"]
                change = "changed" if promised else (
                    "touched" if tests_changed or files_named or doc_changed else (
                        "relabelled" if delta else None))
            if change is None:
                continue  # a row the change left alone: its own slips are not this change's
            missing = [c for c in citation_files(after, proof_lanes) if c not in tree_set] if after else []
            entry: Dict[str, Any] = {
                "id": rid, "change": change, "story": row.get("story"), "feature": row.get("feature"),
                "verdict": {"before": (before or {}).get("verdict"), "after": (after or {}).get("verdict")},
                "scenarioCount": len(row.get("scenarios") or []),
                "testsChanged": tests_changed, "filesNamed": files_named, "docChanged": doc_changed,
                "filesMoved": files_moved, "missingCitations": missing,
                "link": (f"{url}/blob/{head_sha}/{proj.repo(map_path)}#L{lines[rid]}"
                         if url and rid in lines and after else None),
            }
            if doc_path is None:
                only_policy = (change == "changed" and set(delta) == {"fields"}
                               and all(k.startswith("servicePolicies.") for k in delta["fields"])
                               and not tests_changed and not files_named and not doc_changed)
                entry["docsNaming"] = [] if only_policy else naming.naming(rid)
                if only_policy:
                    entry["docsNamingSkipped"] = "only shared service policy changed"
            if change == "added":
                entry["scenarios"] = {"added": all_scenarios(row, rid, "the head", row_warnings),
                                      "removed": [], "changed": []}
            entry.update(delta)
            rows_out.append(entry)
            warnings.extend(row_warnings)
        homed.update((map_path, base_path))
    order = {"added": 0, "changed": 1, "removed": 2, "touched": 3, "relabelled": 4}
    rows_out.sort(key=lambda r: (order[r["change"]], id_key(r["id"])))

    docs = diff_docs(proj, merge_base, head_sha, files, docs_home)
    for d in docs:
        homed.add(d["path"])
        if d.get("renamed"):
            homed.add(d["renamed"]["to"])
    size, size_source = size_claim(args)
    size_info: Optional[Dict[str, Any]] = None
    if size_source:
        size_info = {"claimed": size, "source": size_source, "touches": []}
        if size == "tiny":
            patterns, list_changed = protected_paths(proj, merge_base, head_sha, warnings)
            size_info["touches"] = tiny_touches(rows_out, docs, files, patterns, outside, policy_changes) + (
                [list_changed] if list_changed else []) + ([map_disabled] if map_disabled else [])
    unhomed_all = [p for p in paths if p not in homed]
    prose = [p for p in unhomed_all if PROSE_RE.search(p)]
    unhomed = [p for p in unhomed_all if not PROSE_RE.search(p)]
    summary = {
        "files": len(all_files),
        "rowsAdded": sum(r["change"] == "added" for r in rows_out),
        "rowsChanged": sum(r["change"] == "changed" for r in rows_out),
        "rowsRemoved": sum(r["change"] == "removed" for r in rows_out),
        "rowsTouched": sum(r["change"] == "touched" for r in rows_out),
        "rowsRelabelled": sum(r["change"] == "relabelled" for r in rows_out),
        "verdictsMoved": sum(bool(r.get("verdictMoved")) for r in rows_out),
        "docsChanged": len(docs),
        "unhomedFiles": len(unhomed),
        "proseFiles": len(prose),
        "filesOutsideProject": len(outside),
        "leftOutAdded": len(left_out["added"]),
        "leftOutRemoved": len(left_out["removed"]),
    }
    return {
        "base": args.base, "head": args.head, "baseSha": base_sha, "headSha": head_sha,
        "mergeBase": merge_base, "docsHome": docs_home, "map": map_info, "rows": rows_out,
        "features": features_of(rows_out, known_features),
        "featuresRelabelled": features_of(rows_out, known_features, relabelled=True),
        "docs": docs, "leftOut": left_out, "unhomed": unhomed, "prose": prose, "outsideProject": outside,
        "servicePolicies": policy_changes,
        "warnings": dedupe(warnings),
        "summary": summary, "size": size_info,
    }


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------


def _verdict(r: Dict[str, Any]) -> str:
    before, after = r["verdict"]["before"], r["verdict"]["after"]
    if r["change"] == "added":
        return after or "none"
    if r["change"] == "removed":
        return f"{before or 'none'} (row removed)"
    return f"{before or 'none'} → {after or 'none'}" if before != after else (after or "none")


def _scenario_note(r: Dict[str, Any]) -> str:
    sc = r.get("scenarios") or {}
    parts = []
    if sc.get("added"):
        parts.append(f"+{len(sc['added'])}")
    if sc.get("changed"):
        parts.append(f"~{len(sc['changed'])}")
    if sc.get("removed"):
        parts.append(f"-{len(sc['removed'])}")
    return " ".join(parts) or "none"


def _file_notes(r: Dict[str, Any]) -> List[str]:
    notes = []
    if r.get("filesMoved"):
        notes.append(f"{len(r['filesMoved'])} file(s) it cites or names moved")
    if r.get("missingCitations"):
        notes.append(f"{len(r['missingCitations'])} cited file(s) missing at head")
    return notes


def _why_touched(r: Dict[str, Any]) -> str:
    why = []
    if r.get("storyChanged"):
        why.append("story")
    if r.get("scenarios") and r["change"] != "added":
        why.append("scenarios")
    if r.get("evidence"):
        why.append("evidence")
    if r.get("surfaces"):
        why.append("surfaces")
    if r.get("doc"):
        why.append("doc link")
    if r.get("verdictMoved"):
        why.append("verdict")
    if r.get("featureChanged"):
        why.append("feature")
    fields = r.get("fields") or []
    why.extend(fields[:FIELD_LIMIT])
    if len(fields) > FIELD_LIMIT:
        why.append(f"{len(fields) - FIELD_LIMIT} more fields")
    if r["testsChanged"]:
        why.append(f"{len(r['testsChanged'])} cited test file(s) changed")
    if r["filesNamed"]:
        why.append(f"{len(r['filesNamed'])} named file(s) changed")
    if r["docChanged"]:
        why.append("its outcome doc changed")
    why.extend(_file_notes(r))
    return ", ".join(why) or r["change"]


def _row_name(r: Dict[str, Any]) -> str:
    return f"[{r['id']}]({r['link']})" if r.get("link") else r["id"]


def _clip(text: Any, limit: int = CLIP) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= limit else s[:limit - 1].rstrip() + "…"


def _cell(text: Any, limit: int = 2 * CLIP) -> str:
    return _clip(text, limit).replace("|", "\\|")


def _code(text: str) -> str:
    return f"`` {text} ``" if "`" in text else f"`{text}`"


def _left_out_counts(report: Dict[str, Any]) -> str:
    left = report.get("leftOut") or {}
    return ", ".join(f"{len(left[k])} {k}" for k in ("added", "removed") if left.get(k))


def _more(n: int) -> List[str]:
    return ["", MORE.format(n=n)] if n > 0 else []


def format_markdown(report: Dict[str, Any]) -> str:
    s = report["summary"]
    out = [
        f"{s['files']} files changed. Rows: {s['rowsAdded']} added, {s['rowsChanged']} changed, "
        f"{s['rowsRemoved']} removed, {s['rowsTouched']} touched"
        + (f", {s['rowsRelabelled']} relabelled" if s.get("rowsRelabelled") else "")
        + f"; {s['verdictsMoved']} verdicts moved. "
        f"Outcome docs: {s['docsChanged']}. Files no row names: {s['unhomedFiles']}."
        + (f" Files outside the project folder: {s['filesOutsideProject']}." if s.get("filesOutsideProject") else ""),
    ]
    if report["map"] is None:
        out.append("")
        out.append("No capability map is configured, so no rows are listed.")
    if report.get("servicePolicies"):
        out += ["", "Service policy changes:"]
        out += [f"- {p['id']}: {p['change']}" for p in report["servicePolicies"][:LIST_LIMIT]]
        if len(report["servicePolicies"]) > LIST_LIMIT:
            out.append(MORE.format(n=len(report["servicePolicies"]) - LIST_LIMIT))
    named_features = [a for a in report.get("features") or [] if a.get("id") is not None]
    if named_features:
        out += ["", "Features: " + ", ".join(f"{a.get('name') or a['id']} ({len(a['rows'])})" for a in named_features)
                + "."]
    moved = [r for r in report["rows"] if r["change"] not in ("touched", "relabelled")]
    touched = [r for r in report["rows"] if r["change"] == "touched"]
    relabelled = [r for r in report["rows"] if r["change"] == "relabelled"]
    if moved:
        out += ["", "| Row | Change | Verdict | Scenarios | What moved |", "|---|---|---|---|---|"]
        for r in moved[:MD_LIMIT]:
            out.append(f"| {_row_name(r)} | {r['change']} | {_cell(_verdict(r))} | {_scenario_note(r)} "
                       f"| {_cell(_why_touched(r))} |")
        out += _more(len(moved) - MD_LIMIT)
    if touched:
        named = []
        for r in touched[:MD_LIMIT]:
            notes = "; ".join([r["verdict"]["after"] or "none"] + _file_notes(r))
            named.append(f"{_row_name(r)} ({notes})")
        out += ["", "Touched, the row itself unchanged (a test file it cites, a file it names, or its "
                "outcome doc changed; check the verdict still holds): " + ", ".join(named) + "."]
        out += _more(len(touched) - MD_LIMIT)
    if len(relabelled) > RELABEL_LIST:
        groups = report.get("featuresRelabelled") or []
        out += ["", f"Feature changed, the promise unchanged: {len(relabelled)} rows. Their new features: "
                + ", ".join(f"{a.get('name') or a.get('id') or 'none'} ({len(a['rows'])})" for a in groups) + "."]
    elif relabelled:
        named = [f"{_row_name(r)} ({(r.get('featureChanged') or {}).get('before') or 'none'} → "
                 f"{(r.get('featureChanged') or {}).get('after') or 'none'})" for r in relabelled]
        out += ["", "Feature changed, the promise unchanged: " + ", ".join(named) + "."]
    detail = []
    for r in report["rows"]:
        sc = r.get("scenarios") or {}
        for s_ in sc.get("added", []):
            detail.append(f"- {r['id']} {s_['id']} added ({s_.get('altitude')}): {_clip(s_.get('then'))}")
        for s_ in sc.get("changed", []):
            then = s_["then"]
            if then["before"] != then["after"]:
                detail.append(f"- {r['id']} {s_['id']} Then was: {_clip(then['before'])}. "
                              f"Now: {_clip(then['after'])}")
            else:
                detail.append(f"- {r['id']} {s_['id']} changed: {', '.join(s_['fields'])}")
        for s_ in sc.get("removed", []):
            detail.append(f"- {r['id']} {s_['id']} removed: {_clip(s_.get('then'))}")
    if detail:
        out += ["", "Scenarios:", ""] + detail[:MD_LIMIT]
        if len(detail) > MD_LIMIT:
            out.append(f"- {MORE.format(n=len(detail) - MD_LIMIT)}")
    if report["docs"]:
        out += ["", "| Outcome doc | Change | Status | §0 changed |", "|---|---|---|---|"]
        for d in report["docs"][:MD_LIMIT]:
            st = d["status"]
            status = st["after"] if st["before"] == st["after"] else f"{st['before'] or 'none'} → {st['after'] or 'none'}"
            out.append(f"| {_cell(d['title'] or d['path'], CLIP)} (`{d['path']}`) | {d['change']} | {_cell(status)} "
                       f"| {'yes' if d['section0Changed'] else 'no'} |")
        out += _more(len(report["docs"]) - MD_LIMIT)
    left = report.get("leftOut") or {}
    entries = [(k, e) for k in ("added", "removed") for e in left.get(k) or []]
    if entries:
        out += ["", f"Tests left out of the map on purpose: {_left_out_counts(report)}.", ""]
        out += [f"- {_code(_clip(e.get('test'), 2 * CLIP))} ({k}): {_clip(e.get('reason'))}"
                for k, e in entries[:MD_LIMIT]]
        if len(entries) > MD_LIMIT:
            out.append(f"- {MORE.format(n=len(entries) - MD_LIMIT)}")
    if report["unhomed"]:
        shown = report["unhomed"][:LIST_LIMIT]
        more = len(report["unhomed"]) - len(shown)
        out += ["", "Files no row names or cites:", ""] + [f"- `{p}`" for p in shown]
        if more:
            out.append(f"- {MORE.format(n=more)}")
    if report.get("prose"):
        shown = report["prose"][:LIST_LIMIT]
        out += ["", "Prose files no row names (notes, learnings, readmes):", ""] + [f"- `{p}`" for p in shown]
        if len(report["prose"]) > len(shown):
            out.append(f"- {MORE.format(n=len(report['prose']) - len(shown))}")
    if report.get("warnings"):
        warned = report["warnings"]
        out += ["", "Warnings:", ""] + [f"- {_clip(w, 2 * CLIP)}" for w in warned[:LIST_LIMIT]]
        if len(warned) > LIST_LIMIT:
            out.append(f"- {MORE.format(n=len(warned) - LIST_LIMIT)}")
    text = "\n".join(out)
    if len(text) > MD_BUDGET:
        text = text[:text.rfind("\n", 0, MD_BUDGET - len(CUT) - 2)] + "\n\n" + CUT
    return text


def format_human(report: Dict[str, Any]) -> str:
    lines = [f"{report['base']}...{report['head']} ({report['mergeBase'][:7]}..{report['headSha'][:7]})"]
    lines += [f"warning: {w}" for w in report.get("warnings") or []]
    lines += [f"service policy {p['id']}: {p['change']}" for p in report.get("servicePolicies", [])]
    for r in report["rows"]:
        lines.append(f"{r['id']}: {r['change']} ({_why_touched(r)}); verdict {_verdict(r)}")
    for d in report["docs"]:
        lines.append(f"{d['path']}: {d['change']}; status {d['status']['before']} -> {d['status']['after']}"
                     + ("; §0 changed" if d["section0Changed"] else ""))
    if _left_out_counts(report):
        lines.append(f"tests left out of the map on purpose: {_left_out_counts(report)}")
    if report["unhomed"]:
        lines.append(f"{len(report['unhomed'])} changed files no row names or cites")
    if report.get("outsideProject"):
        lines.append(f"{len(report['outsideProject'])} changed files outside the project folder")
    size = report.get("size")
    if size:
        lines.append(f"size: {size['claimed'] or 'none said'} ({size['source']})"
                     + (f"; touches {len(size['touches'])}" if size["touches"] else ""))
    s = report["summary"]
    lines.append(f"summary: {s['rowsAdded']} added, {s['rowsChanged']} changed, {s['rowsRemoved']} removed, "
                 f"{s['rowsTouched']} touched, {s.get('rowsRelabelled', 0)} relabelled, {s['docsChanged']} docs, "
                 f"{s['unhomedFiles']} unhomed files")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="changed_rows.py",
        description="Which capability rows and outcome docs a change adds, changes or touches.",
    )
    parser.add_argument("--base", default="origin/main", help="the branch the change goes into (default origin/main)")
    parser.add_argument("--head", default="HEAD", help="the change (default HEAD)")
    parser.add_argument("--cwd", default=None,
                        help="the project folder, where its config is (default: the current folder)")
    parser.add_argument("--config", default=None, help="the promise config (default: the one orient finds)")
    parser.add_argument("--map", default=None, help="the map's JSON file, project-relative (default: from the config)")
    parser.add_argument("--docs-home", default=None,
                        help="the outcome docs folder (default: the config's docsHome, else the one orient detects)")
    parser.add_argument("--repo-url", default=None, help="https URL of the repository, for row links")
    parser.add_argument("--size", type=lint_github_text.canonical_size, choices=SIZES, default=None,
                        help="the size the change was given; tiny is checked against the diff")
    parser.add_argument("--body", default=None, metavar="FILE",
                        help="a pull request body (or - for stdin): its Size: line is the size, as --size")
    parser.add_argument("--link", action="append", default=None, metavar="ID",
                        help="print this row's link at --head and nothing else (repeatable)")
    out = parser.add_mutually_exclusive_group()
    out.add_argument("--json", action="store_true", help="print the report as JSON")
    out.add_argument("--markdown", action="store_true", help="print the Markdown block for a pull request")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        if args.link:
            for rid, link, docs in row_links(args):
                print(f"{rid} {link}" + (f" docs: {', '.join(docs)}" if docs else ""))
            return 0
        report = build_report(args)
    except (UsageError, check.UsageError, map_report.UsageError) as exc:
        print(f"changed_rows.py: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.markdown:
        print(format_markdown(report))
    else:
        print(format_human(report))
    touches = (report.get("size") or {}).get("touches") or []
    if touches:
        print(f"changed_rows.py: sized tiny, but touches {'; '.join(touches)}; size it again "
              "(references/sizing.md)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
