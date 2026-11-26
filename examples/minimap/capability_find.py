#!/usr/bin/env python3
"""The one reader of a starter capability map (map.json beside this file).

    python3 capability_find.py "<query>"      ranked matching rows, as a JSON array
    python3 capability_find.py --row <id>     one row, as a JSON object
    python3 capability_find.py --next-id --from issue:<n>
                                              the id for a new row of that issue (pr:<n>, linear:<TEAM>-<n>
                                              too): CAP-i<n>a, then CAP-i<n>b (CAP-ENG-421a), on no branch git knows yet
    python3 capability_find.py --next-id      the next CAP-<n> counter id, for a map with no tracker
                                              (--fetch refreshes the remote branches first)
    python3 capability_find.py --check        validate map.json's shape and each row's doc citation; exit 1 on a defect
    python3 capability_find.py --features     the map's features, each with its row count, as a JSON array
    python3 capability_find.py --feature <id> the rows in one feature, as a JSON array
                                              (--areas and --area are the same flags, kept as aliases)
    python3 capability_find.py --glossary     the map's glossary, as a JSON array
    python3 capability_find.py --eval [FILE]  top 1 and top 5 of find over real work items (default find-eval.json)
    python3 capability_find.py learn --query-file <f> --row <id> --source <s>
                                              record the words find missed the row by, as one of its asks
    python3 capability_find.py refs sync --input <pulls.json>
                                              add refs from merged pull requests' promise blocks
    python3 capability_find.py --code <id>    the local files the row's cited tests import

This is what a project supplies behind `map.find`, `map.row`, `map.nextId`
and `map.checks` in its promise config. The promise skill ships this file as
`templates/starter-map/capability_find.py`, and `scripts/start_map.py` copies
it into a project; after that it is the project's own file. The skill only
calls it, with the query or the row id appended as exactly one argv
element. Python 3 stdlib only. `examples/minimap/` runs the same file.

A query is ranked with BM25 over each row's text: its optional `title`, the
story, its feature's name, aliases, surfaces and scenario cells. Stopwords never
count, and a small stemmer lets "muting" meet "mute". Two query words side by side
in the row, in the query's order, add a small bonus. A row the query names by
id or alias comes first. Each hit carries a `score` and a `why` line: the words
it ranked on. A `title` is one line, written as a person would ask for the row
("mute a channel"); --check warns about a row with none, and it never fails on
that, so an old map still passes.

A row may hold `asks`: at most five `{"text", "source", "date"}`, the words a
person, an issue or a pull request used when `find` missed the row (`source` is
`person`, `issue:<owner>/<repo>#<n>` or `pr:<owner>/<repo>#<n>`). They count as
the row's text, and a query that repeats one, exactly or nearly, puts the row
first. `learn` adds one: it does nothing when `find` already ranks the row
first, refuses text with an email address or a handle, skips a near-duplicate,
drops the oldest ask of a full row, and keeps the ask only when `find` then
ranks the row in the top three. An ask is always a person's or a work item's
own words, never a synonym an agent made up. --check warns about an "ask
conflict": an ask whose words now rank another row first, so a person splits
the rows or retitles one.

A row may hold `refs`: `{"repo": "<owner>/<name>", "kind": "issue" | "pr",
"number": <n>}`, identifiers only (a title or a state goes stale), the repo
named in full. `refs sync --input <file>` reads merged pull requests, each
`{repo, number, title, body, merged}` as the caller fetched them, and adds a
`pr` ref (and an `issue` ref for each issue its "Why" closes) to every row the
pull request's promise block names under "Capabilities" as new or changed. A
pull request that names exactly one row adds its title to the eval fixture as a
case for that row, unless the title is already one of the row's asks.

--code <id> prints where the row's behaviour lives: the local files its cited
tests import, read from the project root (the map's directory joined with its
`docRoot`, as for a row's `doc`). It follows Python and JS/TS imports one step
and names the cited tests it could not find or read. Read these files before
a wide code search.

--eval reads a fixture of `{"text", "row"}` cases, the titles of real work items
(pull requests and issues) linked to one row, and prints how often the row came
first and how often it was in the first five. Never put a row's asks in the
fixture: a case whose text is already an ask is left out and counted.

Exit codes: 0 on success (a query with no hits still prints `[]` and exits
0); 2 on an unknown row id, a malformed id, or a usage error; 1 when
--check finds a defect. Every message that is not a result goes to stderr.

--check reads one thing besides the map: for every row whose `doc` names a
file, that doc must carry a §6 line
citing the row's id in its `Row` cell — the map-to-doc direction of the
recipe's lockstep rule, which `bridge_validate.py` (doc-to-map) does not
read. An optional `parent` must be a row id. A row's `doc` is resolved
against the map's optional top-level `docRoot` (a path relative to the map's
own directory, default "."), so a map kept in a subfolder can cite docs by
their project-relative path.

Three more optional row fields are checked when present. `aliases` is a
list of non-empty strings: the ids a row had in an older register (a journey
id such as `J4`), which a query matches like the row's own text. `surfaces`
is a list of non-empty strings too: the entry points the row's behaviour
enters through, in the project's own notation (`GET /me`, `page /settings`),
also matched by a query. `origin` says where the row came from: `doc` (an
outcome doc's §6), `intake` (feedback) or `backfill` (what the code does
today; such a row has `doc: null` until an outcome doc promises it).

A scenario's `given`, `when` and `then` are copied into an outcome doc's §6
word for word, and the doc lint (`lint_outcome.py` PLACEHOLDER) reads a
`<word>` outside a code span there as an unfilled slot. So --check refuses
a `<word>` outside a code span in those fields too: write `mute <channel>`
in backticks, and §6 can copy it as it is.

The map's optional top-level `leftOut` lists tests left without a row on
purpose, each `{"test": "<file>::<name>", "reason": "<one line>", "date":
"YYYY-MM-DD"}`, one entry per test (its exact title, never a %s or ${x}
pattern); --check validates that shape when the list is present.

Two more optional top-level lists help a person who reads an issue or a pull
request after a few days away. `features` names the parts of the product, each
`{"id": "portal-login", "name": "Portal login", "plain": "<one sentence a
newcomer understands>"}` with an optional `doc` (the outcome doc for that
part, resolved like a row's `doc`); a row's optional `feature` is one of those
ids, and a query matches the feature's name. The alias keys `areas` and `area`
mean the same and stay accepted; a map or a row that has both spellings is a
defect (FEATURE_AND_AREA). `glossary` explains the product's
own words, each `{"term": "Seat", "plain": "<one sentence>", "aliases":
["seats"]}`; a term or alias is used by one entry only. --check validates
both; a row's `feature` with no `features` list, or one that names no feature, is a
defect. A row with no `feature` is not: `--features` counts those rows under a
null id, so a map can take its features a few rows at a time.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MAP = os.path.join(HERE, "map.json")
DEFAULT_FIXTURE = "find-eval.json"

# Every row id starts CAP-, so one grep finds them all and no everyday word is one. Then
# either a counter, CAP-<n> (the first form, and a map with no tracker's), or the work it
# came from: i<n> for an issue, p<n> for a pull request, a Linear issue's own key (ENG-421:
# Linear numbers each team apart), then letters for each row of that item (CAP-i1890a,
# CAP-i1890b, … aa; CAP-ENG-421a). The tracker hands out each number once, so rows of
# different items cannot clash; two branches for one item still can before either
# pushes, and --check catches that at the merge.
ROW_ID_RE = re.compile(r"^CAP-(?:(\d+)|[ip]\d+[a-z]{1,2}|[A-Z][A-Z0-9]+-\d+[a-z]{1,2})$")
# the form 1.25 wrote, before the CAP- prefix: --check says how to rename it
BARE_TRACKER_ID_RE = re.compile(r"^(?:[ip]\d+[a-z]{1,2}|[A-Z][A-Z0-9]+-\d+[a-z]{1,2})$")


def _rename_hint(rid: Any) -> str:
    """How to fix an id 1.25 wrote without the CAP- prefix; empty for any other value."""
    if isinstance(rid, str) and BARE_TRACKER_ID_RE.match(rid):
        return f": 1.25's form, rename it CAP-{rid} everywhere it is written"
    return ""
CAP_ID_RE = re.compile(r"^CAP-(\d+)$")
FROM_PREFIX = {"issue": "i", "pr": "p"}
ROW_ID_TEXT = "CAP-<n>, or CAP- then i<n>, p<n> or a Linear key and letters, such as CAP-i1890a or CAP-ENG-421a"
VERDICTS = ("not-built", "under-proven", "proven")
ALTITUDES = ("data", "response", "perception", "judgement", "sibling")
EVIDENCE_ARRAYS = ("tests", "e2eTests", "evalTests", "siblingTests")
ORIGINS = ("doc", "intake", "backfill")
TOKEN_RE = re.compile(r"[a-z0-9#]+")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# A parametrised slot (%s, ${x}): a leftOut entry names one test, never a pattern.
PATTERN_RE = re.compile(r"%[sdifjopc]|\$\{[^}]*\}")
# The doc lint's placeholder: a `<word>` outside a code span (lint_outcome.py).
ANGLE_RE = re.compile(r"<[^<>]+>")
FEATURE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
# Where an ask came from: a person, or an issue or pull request by its full repo name.
ASK_SOURCE_RE = re.compile(r"^(person|(issue|pr):[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+#\d+)$")
EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
HANDLE_RE = re.compile(r"(^|[\s(])@[A-Za-z0-9_-]+")
MAX_ASKS = 5
ASK_MATCH = 0.8          # term-set overlap at which a query is a past ask
LEARN_TOP = 3            # after learn, the row must rank this high or the ask comes out
MAX_ASK_CHARS = 300
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REF_KINDS = ("issue", "pr")
PR_BLOCK_RE = re.compile(r"<!--\s*promise:pr\s*-->(.*?)<!--\s*/promise:pr\s*-->", re.S)
PY_FROM_RE = re.compile(r"^\s*from\s+(\.*[\w.]*)\s+import\s+\(?([^)#\n]*)", re.M)
PY_IMPORT_RE = re.compile(r"^\s*import\s+([\w.]+(?:\s+as\s+\w+)?(?:\s*,\s*[\w.]+(?:\s+as\s+\w+)?)*)", re.M)
JS_IMPORT_RES = (
    re.compile(r"""\b(?:import|export)\b[^'";]*?\bfrom\s*['"]([^'"]+)['"]"""),
    re.compile(r"""\bimport\s*['"]([^'"]+)['"]"""),
    re.compile(r"""\b(?:require|import)\s*\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""\bjest\.mock\s*\(\s*['"]([^'"]+)['"]"""),
)
JS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
CLOSES_RE = re.compile(r"\b(?:closes|fixes|resolves)\s+(?:([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+))?#(\d+)", re.I)


def load_map(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def _strings(value: Any) -> List[str]:
    """A list field's string entries; anything else reads as no entries."""
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


STOPWORDS = frozenset("""
a about above after again against all am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have
having he her here hers herself him himself his how i if in into is it its itself just me more most
my myself no nor not now of off on once only or other our ours ourselves out over own same she
should so some such than that the their theirs them themselves then there these they this those
through to too under until up very was we were what when where which while who whom why will with
would you your yours yourself yourselves
""".split())
# BM25's two constants, at the values most keyword rankers ship with.
BM25_K1 = 1.2
BM25_B = 0.75


def stem(word: str) -> str:
    """A small suffix stripper, so "mutes", "muted" and "muting" meet "mute".
    It never makes a word shorter than three letters."""
    w = word
    if len(w) <= 3 or not w.isalpha():
        return w
    if w.endswith("ies") and len(w) > 4:
        w = w[:-3] + "y"
    elif w.endswith("sses"):
        w = w[:-2]
    elif w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    for suffix in ("ingly", "edly", "ing", "ed", "ly"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3:
            w = w[: -len(suffix)]
            if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "lsz":
                w = w[:-1]
            break
    if len(w) > 3 and w.endswith("y"):
        w = w[:-1] + "i"
    if len(w) > 3 and w.endswith("e"):
        w = w[:-1]
    return w


def terms(text: str) -> List[str]:
    """The words BM25 counts: lower-cased, stopwords out, each stemmed."""
    return [stem(t) for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


def tokens(text: str) -> List[str]:
    return TOKEN_RE.findall(text.lower())


def _feature_list(data: Any) -> Any:
    """The map's feature list under ``features``, else its alias key ``areas``."""
    if not isinstance(data, dict):
        return None
    return data["features"] if data.get("features") is not None else data.get("areas")


def _row_feature(row: Any) -> Any:
    """A row's feature id under ``feature``, else its alias key ``area``."""
    if not isinstance(row, dict):
        return None
    return row["feature"] if "feature" in row else row.get("area")


def row_text(row: Dict[str, Any], area_names: Optional[Dict[str, str]] = None) -> str:
    """Everything a query is matched against: the row's title, story, its feature's
    name, aliases, surfaces and scenario cells."""
    parts = [str(row.get("title") or ""), str(row.get("story") or "")]
    if area_names and isinstance(_row_feature(row), str):
        parts.append(area_names.get(_row_feature(row), ""))
    parts.extend(_strings(row.get("aliases")))
    parts.extend(_strings(row.get("surfaces")))
    parts.extend(a["text"] for a in _asks(row))
    for scenario in row.get("scenarios", []) if isinstance(row.get("scenarios"), list) else []:
        if isinstance(scenario, dict):
            parts.extend(str(scenario.get(k, "")) for k in ("given", "when", "then"))
    return " ".join(parts)


def _asks(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The row's well-formed asks; anything else reads as none (--check names it)."""
    value = row.get("asks")
    return [a for a in value if isinstance(a, dict) and isinstance(a.get("text"), str)] if isinstance(value, list) else []


def overlap(a: str, b: str) -> float:
    """How far two texts use the same counted words: shared over all, 0 to 1."""
    x, y = set(terms(a)), set(terms(b))
    return len(x & y) / len(x | y) if x and y else 0.0


def _past_ask(row: Dict[str, Any], query: str) -> Optional[str]:
    """The row's ask the query repeats, exactly or nearly, or None."""
    best = max(_asks(row), key=lambda a: overlap(a["text"], query), default=None)
    return best["text"] if best is not None and overlap(best["text"], query) >= ASK_MATCH else None


def _names_row(row: Dict[str, Any], query: str) -> bool:
    """True when the query names the row by its id or one of its aliases, as a whole word."""
    for name in [str(row.get("id", ""))] + _strings(row.get("aliases")):
        if name and re.search(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])", query, re.IGNORECASE):
            return True
    return False


def find(rows: List[Dict[str, Any]], query: str,
         area_names: Optional[Dict[str, str]] = None, use_asks: bool = True) -> List[Dict[str, Any]]:
    """Rows ranked by BM25 over the row's text (title, story, feature name, aliases,
    surfaces, scenario cells), best first; equal scores keep map order. A row the
    query names by id or alias comes first, then a row whose past ask the query
    repeats (``use_asks``). Two query words that sit side by side in
    the row, in the query's order, add a small bonus. A row that shares no counted word with
    the query is not returned. Each hit carries ``score`` and ``why``: the words it
    ranked on, strongest first."""
    rows = [r for r in rows if isinstance(r, dict)]
    docs = [terms(row_text(r, area_names)) for r in rows]
    n = len(docs) or 1
    avg = (sum(len(d) for d in docs) / n) or 1.0
    df: Dict[str, int] = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    wanted = sorted(set(terms(query)))
    ordered = terms(query)
    pairs = {(a, b) for a, b in zip(ordered, ordered[1:]) if a != b}
    # The why line names the query's own words, not their stems.
    spelled: Dict[str, str] = {}
    for word in TOKEN_RE.findall(query.lower()):
        if word not in STOPWORDS:
            spelled.setdefault(stem(word), word)
    ranked = []
    for position, (row, doc) in enumerate(zip(rows, docs)):
        counts: Dict[str, int] = {}
        for t in doc:
            counts[t] = counts.get(t, 0) + 1
        parts = []
        for t in wanted:
            tf = counts.get(t, 0)
            if not tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            parts.append((idf * tf * (BM25_K1 + 1) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * len(doc) / avg)), t))
        # Two query words side by side, in the query's order, count once more:
        # "mute a channel" is closer to "Mute a channel so…" than to "channels are muted".
        adjacent = pairs & set(zip(doc, doc[1:]))
        idf_of = {t: math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) for pair in adjacent for t in pair}
        phrase = sum((idf_of[a] + idf_of[b]) / 2 for a, b in adjacent)
        named = _names_row(row, query)
        asked = _past_ask(row, query) if use_asks else None
        if not parts and not named:
            continue
        score = sum(p for p, _ in parts) + phrase
        why = [spelled.get(t, t) for _, t in sorted(parts, key=lambda x: (-x[0], x[1]))]
        reason = ("names this row; " if named else "") + (f"repeats a past ask: {asked!r}; " if asked else "") \
            + ("shared words: " + ", ".join(why) if why else "")
        if adjacent:
            reason += "; in the same order: " + ", ".join(
                f"{spelled.get(a, a)} {spelled.get(b, b)}" for a, b in sorted(adjacent))
        tier = 0 if named else 1 if asked else 2
        ranked.append((tier, -score, position, row, round(score, 3), reason.rstrip("; ")))
    ranked.sort(key=lambda item: item[:3])
    return [dict(row, score=score, why=why) for _n, _s, _p, row, score, why in ranked]


def next_id(rows: List[Dict[str, Any]], taken: Optional[Dict[int, str]] = None) -> str:
    """One past the highest id in this map and in ``taken``: the numbers other
    branches already hold, so two branches never give out the same one."""
    highest = max(taken or {0: ""})
    for row in rows:
        m = CAP_ID_RE.match(str(row.get("id", "")))
        if m:
            highest = max(highest, int(m.group(1)))
    return f"CAP-{highest + 1}"


def letters(n: int) -> str:
    """0 → a, 25 → z, 26 → aa: the letters of the n-th row of one tracker item."""
    out = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(97 + r) + out
    return out


def next_id_from(source: str, used: set) -> str:
    """The id for a new row of the work item ``source`` (``issue:1890``, ``pr:2091``,
    or ``linear:ENG-421``, whose own key is the stem, since Linear numbers each team
    apart), after ``CAP-``: then the letters after the last ones a row, retired id or
    other branch has used for it."""
    kind, _, number = source.partition(":")
    if kind == "linear":
        team, _, number = number.rpartition("-")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]+", team) or not number.isdigit() or int(number) < 1:
            raise ValueError(f"--from {source!r}: a Linear issue is linear:<TEAM>-<n>, such as linear:ENG-421")
        stem = f"CAP-{team.upper()}-{int(number)}"
    elif kind in FROM_PREFIX and number.isdigit() and int(number) >= 1:
        stem = f"CAP-{FROM_PREFIX[kind]}{int(number)}"
    else:
        raise ValueError(f"--from {source!r} is not issue:<n>, pr:<n> or linear:<TEAM>-<n>")
    # after the last letters this item has used, so a row deleted without being retired
    # never hands its id to another row
    # an id 1.25 wrote without the prefix (i1890a) holds its letters too, until renamed
    bare = stem[len("CAP-"):]
    taken = [n for n in range(26 + 26 * 26) if f"{stem}{letters(n)}" in used or f"{bare}{letters(n)}" in used]
    n = taken[-1] + 1 if taken else 0
    if n < 26 + 26 * 26:  # a to zz: at most two letters
        return f"{stem}{letters(n)}"
    raise ValueError(f"--from {source!r}: every id for this item, a to zz, is taken; use another item")


# ---------------------------------------------------------------------------
# Parallel branches. The map is one file that every branch appends to, so two
# branches can take one number, and a merge that keeps one side of the
# conflict drops the other side's row without a word. --next-id looks at every
# branch git knows; --check, on a merge commit, finds a row either side added
# that the merge lost, and a number both sides gave to different rows.
# ---------------------------------------------------------------------------


def _git(args: List[str], cwd: str, timeout: int = 60) -> Optional[str]:
    try:
        proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _repo_path(map_path: str) -> Optional[Tuple[str, str]]:
    """The git work tree holding the map, and the map's path inside it."""
    folder = os.path.dirname(os.path.abspath(map_path))
    top = _git(["rev-parse", "--show-toplevel"], folder)
    if not top:
        return None
    root = top.strip()
    return root, os.path.relpath(os.path.realpath(os.path.abspath(map_path)), os.path.realpath(root)).replace(os.sep, "/")


def _map_at(root: str, ref: str, rel: str) -> Optional[Dict[str, Any]]:
    text = _git(["show", f"{ref}:{rel}"], root)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _rows_of(data: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = data.get("rows") if isinstance(data, dict) else None
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def taken_on_branches(map_path: str, fetch: bool = False, ids: Optional[Dict[str, str]] = None) -> Dict[int, str]:
    """Each CAP row number some branch's copy of the map holds, local or remote, with
    the first branch that holds it; every id of any shape goes in ``ids`` too. With
    ``fetch``, the remotes are refreshed first."""
    where = _repo_path(map_path)
    if where is None:
        return {}
    root, rel = where
    if fetch:
        _git(["fetch", "--quiet", "--all", "--prune"], root, timeout=120)
    refs = _git(["for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes"], root) or ""
    taken: Dict[int, str] = {}
    for ref in refs.split():
        if ref.endswith("/HEAD"):
            continue  # a remote's HEAD points at one of its branches, read on its own
        name = re.sub(r"^refs/(?:heads|remotes)/", "", ref)
        branch_map = _map_at(root, ref, rel)
        for row in _rows_of(branch_map):
            rid = str(row.get("id", ""))
            if ids is not None:
                ids.setdefault(rid, name)
            m = CAP_ID_RE.match(rid)
            if m:
                taken.setdefault(int(m.group(1)), name)
        if ids is not None:
            for rid in retired_ids(branch_map):
                ids.setdefault(rid, name)
    return taken


def _row_key(row: Dict[str, Any]) -> str:
    """What a row is, whatever number it was given: its story, else its title, else its id."""
    text = row.get("story") or row.get("title") or row.get("id") or ""
    return " ".join(str(text).lower().split())


def _merge_losses(root: str, rel: str, parents: List[str], result: Dict[str, Any], now_rows: List[Dict[str, Any]],
                  now_left_out: Any, what: str, retired: set) -> List[str]:
    """Rows and leftOut entries a parent added since the parents' merge base that the
    merge's ``result`` does not hold and the map today does not hold either; and, for
    the merge in hand, one id both sides gave to rows that are both still here."""
    base = (_git(["merge-base", "--octopus", *parents], root) or "").strip()
    sides = [_map_at(root, p, rel) for p in parents]
    if not base or any(side is None for side in sides):
        return []  # git cannot see the history (a shallow clone): nothing to say
    base_map = _map_at(root, base, rel) or {}
    base_keys = {_row_key(r) for r in _rows_of(base_map)}
    base_ids = {str(r.get("id", "")) for r in _rows_of(base_map)}
    kept = {_row_key(r) for r in _rows_of(result)} | {_row_key(r) for r in now_rows if isinstance(r, dict)}
    base_tests = {str(e.get("test")) for e in _list(base_map.get("leftOut")) if isinstance(e, dict)}
    kept_tests = {str(e.get("test")) for e in _list(result.get("leftOut")) + _list(now_left_out) if isinstance(e, dict)}
    # a test a row cites now needs no leftOut entry: dropping it is no loss
    kept_tests |= {str(t) for r in now_rows if isinstance(r, dict) for k in EVIDENCE_ARRAYS for t in _list(r.get(k))}
    kept_ids = {str(r.get("id", "")) for r in _rows_of(result)} | {str(r.get("id", "")) for r in now_rows
                                                                   if isinstance(r, dict)}
    problems: List[str] = []
    added_by_id: Dict[str, Dict[str, str]] = {}
    added: List[Tuple[str, str, str, Dict[str, Any]]] = []
    for parent, side in zip(parents, sides):
        for row in _rows_of(side):
            key = _row_key(row)
            if key in base_keys or str(row.get("id", "")) in base_ids:
                continue  # not new on this side: an edit to an existing row is no added row
            rid = str(row.get("id", ""))
            added_by_id.setdefault(rid, {})[parent] = key
            added.append((parent, rid, key, row))
    for parent, rid, key, row in added:
        # kept by its story, or by its id when no other side gave that id to another row
        # (a reworded row keeps its id; one side kept of a clash does not keep the other)
        if key in kept or rid in retired or key in retired or \
                (rid in kept_ids and len(set(added_by_id[rid].values())) == 1):
            continue
        # its id still on another row: it can be retired only by its story
        how = (f"list its story under retired" if rid in kept_ids else f"list {rid} under retired")
        problems.append(f"{what} lost row {rid} ({str(row.get('story') or row.get('title') or '')[:60]}),"
                        f" added on {parent[:8]}: restore it from that side, with a new id from --next-id --from its issue; "
                        f"or, dropped on purpose, {how} with a reason")
    for parent, side in zip(parents, sides):
        for entry in _list(side.get("leftOut")):
            if isinstance(entry, dict) and str(entry.get("test")) not in base_tests | kept_tests:
                problems.append(f"{what} lost the leftOut entry for {entry.get('test')}, added on {parent[:8]}")
    here_ids = [str(r.get("id", "")) for r in now_rows if isinstance(r, dict)]
    for rid, by_parent in added_by_id.items():
        # still on two rows here: say why, and how to fix it (a renumbered merge is fine)
        if len(by_parent) > 1 and len(set(by_parent.values())) > 1 and here_ids.count(rid) > 1:
            problems.append(f"both sides of {what} gave {rid} to a new row: keep both rows, and give one "
                            "a new id from --next-id --from its issue")
    return problems


def merge_problems(map_path: str, rows: List[Dict[str, Any]], left_out: Any, retired: Optional[set] = None) -> List[str]:
    """What a merge lost. The merge in hand (a merge commit, or one in progress,
    before it is committed): every row and leftOut entry either side added since
    their merge base is still in the map, and no id was given by both sides to two
    rows still here. Then every earlier merge on this branch (since the default
    branch, or the merge's first parent): a row one of them dropped, when main was
    merged into the branch and one side of the conflict was kept, is still missing
    now. Nothing to say outside git, or when git cannot see the history (a shallow
    clone: fetch it)."""
    where = _repo_path(map_path)
    if where is None:
        return []
    root, rel = where
    line = (_git(["rev-list", "--parents", "-n", "1", "HEAD"], root) or "").split()
    if not line:
        return []
    git_dir = (_git(["rev-parse", "--git-dir"], root) or "").strip()
    try:
        with open(os.path.join(root, git_dir, "MERGE_HEAD") if git_dir else "", encoding="utf-8") as fh:
            merging = fh.read().split()  # one sha a line: several in an octopus merge
    except OSError:
        merging = []
    parents = [line[0], *merging] if merging else line[1:] if len(line) >= 3 else []
    # What the merge kept: the working tree while it is in progress, else the merge commit
    # itself (a row removed on purpose after the merge is no loss of the merge's).
    kept = {"rows": rows, "leftOut": left_out} if merging else (_map_at(root, "HEAD", rel) or {})
    problems = (_merge_losses(root, rel, parents, kept, rows, left_out, "the merge", retired or set())
                if len(parents) > 1 else [])
    # Earlier merges this branch brought in: those since the default branch, or, for the
    # merge in hand (CI's test merge of a pull request), those on the side coming in.
    if len(parents) > 1:
        ranges = [f"{parents[0]}..{p}" for p in parents[1:]]
    else:
        default = (_git(["rev-parse", "--abbrev-ref", "origin/HEAD"], root) or "").strip()
        ranges = [f"{default}..HEAD"] if default and default != "origin/HEAD" else []
    for span in ranges:
        for commit in (_git(["rev-list", "--merges", span], root) or "").split():
            earlier = (_git(["rev-list", "--parents", "-n", "1", commit], root) or "").split()[1:]
            result = _map_at(root, commit, rel)
            if len(earlier) > 1 and result is not None:
                problems += _merge_losses(root, rel, earlier, result, rows, left_out, f"merge {commit[:8]}",
                                          retired or set())
    return list(dict.fromkeys(problems))


ROW_CELL_RE_TEMPLATE = r"^\| AT-\d+ \|.*\| {id} \|$"


def doc_cites_row(doc_path: str, row_id: str) -> bool:
    """True when the doc holds a §6 line whose last cell is exactly this
    row id — a line of the shape `| AT-n | … | <id> |`."""
    pattern = re.compile(ROW_CELL_RE_TEMPLATE.format(id=re.escape(row_id)))
    with open(doc_path, encoding="utf-8-sig") as fh:
        return any(pattern.match(line.rstrip("\r\n")) for line in fh)


def _code_span_end(text: str, i: int) -> int:
    """Just past the run of backticks that closes the code span opened at
    ``text[i]``, or -1 when nothing closes it: a lone backtick is text."""
    j = i
    while j < len(text) and text[j] == "`":
        j += 1
    width, k = j - i, j
    while k < len(text):
        if text[k] != "`":
            k += 1
            continue
        m = k
        while m < len(text) and text[m] == "`":
            m += 1
        if m - k == width:
            return m
        k = m
    return -1


def bare_placeholders(text: str) -> List[str]:
    """Each `<word>` in ``text`` outside a closed code span: what the doc
    lint reports as PLACEHOLDER once §6 copies the text."""
    out: List[str] = []
    i = 0
    while i < len(text):
        if text[i] == "`":
            end = _code_span_end(text, i)
            if end == -1:
                while i < len(text) and text[i] == "`":
                    out.append("`")
                    i += 1
                continue
            out.append(" ")
            i = end
        else:
            out.append(text[i])
            i += 1
    return ANGLE_RE.findall("".join(out))


def check(rows: Any, base_dir: str = HERE) -> List[str]:
    """Every defect in the map's shape, as one line each; empty when clean.

    ``base_dir`` is the directory a row's ``doc`` is resolved against — the
    map's own directory joined with its ``docRoot`` — and the doc must cite
    the row in a §6 ``Row`` cell.
    """
    problems: List[str] = []
    if not isinstance(rows, list):
        return ["rows is not a list"]
    seen = set()
    for i, row in enumerate(rows):
        label = f"rows[{i}]"
        if not isinstance(row, dict):
            problems.append(f"{label}: not an object")
            continue
        rid = row.get("id")
        if _rename_hint(rid):
            problems.append(f"{label}: id {rid!r} needs the CAP- prefix: rename it CAP-{rid} here, in its doc's "
                            "§6, in its tests and in any parent or retired entry")
        elif not isinstance(rid, str) or not ROW_ID_RE.match(rid):
            problems.append(f"{label}: id {rid!r} is not a row id ({ROW_ID_TEXT})")
        elif rid in seen:
            problems.append(f"{label}: duplicate id {rid}")
        else:
            seen.add(rid)
            label = rid
        if not isinstance(row.get("story"), str) or not row["story"].strip():
            problems.append(f"{label}: story is missing or empty")
        if "title" in row and not _one_line(row.get("title")):
            problems.append(f"{label}: title must be one non-empty line")
        scenarios = row.get("scenarios")
        grouped = row.get("grouping") == "job"
        if not isinstance(scenarios, list) or not scenarios:
            limit = "at least 1 entry" if grouped else "1-5 entries"
            problems.append(f"{label}: scenarios must be a list of {limit}")
        elif not grouped and len(scenarios) > 5:
            problems.append(f"{label}: scenarios must be a list of 1-5 entries")
        else:
            for j, scenario in enumerate(scenarios):
                if not isinstance(scenario, dict):
                    problems.append(f"{label}: scenarios[{j}] is not an object")
                    continue
                for key in ("given", "when", "then"):
                    if not isinstance(scenario.get(key), str) or not scenario[key].strip():
                        problems.append(f"{label}: scenarios[{j}].{key} is missing or empty")
                        continue
                    for word in bare_placeholders(scenario[key]):
                        problems.append(f"{label}: scenarios[{j}].{key} holds {word} outside a code span; "
                                        f"write it in backticks so §6 can copy it as it is")
                if scenario.get("altitude") not in ALTITUDES:
                    problems.append(f"{label}: scenarios[{j}].altitude {scenario.get('altitude')!r} is not one of {ALTITUDES}")
        for key in EVIDENCE_ARRAYS:
            value = row.get(key)
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                problems.append(f"{label}: {key} must be an array of strings")
        if row.get("verdict") not in VERDICTS:
            problems.append(f"{label}: verdict {row.get('verdict')!r} is not one of {VERDICTS}")
        elif row["verdict"] == "proven" and not any(row.get(key) for key in EVIDENCE_ARRAYS):
            problems.append(f"{label}: verdict is proven with no citation in any evidence array")
        parent = row.get("parent")
        if parent is not None and (not isinstance(parent, str) or not ROW_ID_RE.match(parent)):
            problems.append(f"{label}: parent {parent!r} is not a row id{_rename_hint(parent)}")
        for key in ("aliases", "surfaces"):
            value = row.get(key)
            if value is not None and not (
                isinstance(value, list) and all(isinstance(v, str) and v.strip() for v in value)
            ):
                problems.append(f"{label}: {key} must be an array of non-empty strings")
        problems += check_asks(row.get("asks"), label)
        problems += check_refs(row.get("refs"), label)
        origin = row.get("origin")
        if origin is not None and origin not in ORIGINS:
            problems.append(f"{label}: origin {origin!r} is not one of {ORIGINS}")
        doc = row.get("doc")
        if doc is not None and not isinstance(doc, str):
            problems.append(f"{label}: doc {doc!r} is neither a path nor null")
        elif isinstance(doc, str) and isinstance(rid, str) and ROW_ID_RE.match(rid):
            doc_path = os.path.join(base_dir, doc)
            try:
                cited = doc_cites_row(doc_path, rid)
            except (OSError, UnicodeDecodeError) as exc:
                problems.append(f"{label}: doc {doc} cannot be read: {exc}")
            else:
                if not cited:
                    problems.append(f"{label}: doc {doc} has no §6 line citing it")
    return problems


def private_words(text: str) -> bool:
    """True when the text holds an email address or an @handle: an ask records what
    was asked, never who asked it."""
    return bool(EMAIL_RE.search(text) or HANDLE_RE.search(text))


def check_asks(asks: Any, label: str) -> List[str]:
    """Every defect in a row's optional ``asks``: at most five, each ``{text, source,
    date}``, the text one line with no email address or handle, the source ``person``
    or ``issue:<owner>/<repo>#<n>`` / ``pr:<owner>/<repo>#<n>``, the date real."""
    if asks is None:
        return []
    if not isinstance(asks, list):
        return [f"{label}: asks must be an array"]
    problems = []
    if len(asks) > MAX_ASKS:
        problems.append(f"{label}: asks holds {len(asks)} entries; at most {MAX_ASKS}")
    for i, ask in enumerate(asks):
        where = f"{label}: asks[{i}]"
        if not isinstance(ask, dict):
            problems.append(f"{where} is not an object")
            continue
        text = ask.get("text")
        if not _one_line(text):
            problems.append(f"{where}.text must be one non-empty line")
        elif private_words(text):
            problems.append(f"{where}.text holds an email address or a handle")
        if not isinstance(ask.get("source"), str) or not ASK_SOURCE_RE.match(ask["source"]):
            problems.append(f"{where}.source {ask.get('source')!r} is not person, issue:<owner>/<repo>#<n> or pr:<owner>/<repo>#<n>")
        if not _real_date(ask.get("date")):
            problems.append(f"{where}.date {ask.get('date')!r} is not a real YYYY-MM-DD date")
    return problems


def check_refs(refs: Any, label: str) -> List[str]:
    """Every defect in a row's optional ``refs``: each ``{repo, kind, number}`` and
    nothing else (a title or a state goes stale), the repo named in full
    (``owner/name``), ``kind`` issue or pr, ``number`` a positive integer, no two alike."""
    if refs is None:
        return []
    if not isinstance(refs, list):
        return [f"{label}: refs must be an array"]
    problems, seen = [], set()
    for i, ref in enumerate(refs):
        where = f"{label}: refs[{i}]"
        if not isinstance(ref, dict):
            problems.append(f"{where} is not an object")
            continue
        extra = sorted(set(ref) - {"repo", "kind", "number"})
        if extra:
            problems.append(f"{where} holds {', '.join(extra)}; a ref holds repo, kind and number only")
        if not isinstance(ref.get("repo"), str) or not REPO_RE.match(ref["repo"]):
            problems.append(f"{where}.repo {ref.get('repo')!r} is not <owner>/<name>")
        if ref.get("kind") not in REF_KINDS:
            problems.append(f"{where}.kind {ref.get('kind')!r} is not issue or pr")
        number = ref.get("number")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            problems.append(f"{where}.number {number!r} is not a positive integer")
        key = (ref.get("repo"), ref.get("kind"), ref.get("number"))
        if key in seen:
            problems.append(f"{where} repeats an earlier ref")
        seen.add(key)
    return problems


def ask_conflicts(rows: Any, area_names: Optional[Dict[str, str]] = None) -> List[str]:
    """An ask whose own words now rank another row first, before the past-ask rule
    applies: two rows compete for the same words, and a person splits them or retitles one."""
    rows = [r for r in (rows if isinstance(rows, list) else []) if isinstance(r, dict)]
    out = []
    for row in rows:
        for ask in _asks(row):
            hits = find(rows, ask["text"], area_names, use_asks=False)
            if hits and hits[0].get("id") != row.get("id"):
                out.append(f"ask conflict: {row.get('id')}'s ask {ask['text']!r} finds {hits[0].get('id')} first")
    return out


def _real_date(value: Any) -> bool:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def check_left_out(left_out: Any) -> List[str]:
    """Every defect in the map's optional top-level ``leftOut`` list: each
    entry names a test as ``<file>::<name>``, a one-line reason and the real
    date it was left out, ``YYYY-MM-DD``. Empty when absent or clean."""
    if left_out is None:
        return []
    if not isinstance(left_out, list):
        return ["leftOut is not a list"]
    problems: List[str] = []
    for i, entry in enumerate(left_out):
        label = f"leftOut[{i}]"
        if not isinstance(entry, dict):
            problems.append(f"{label}: not an object")
            continue
        test = entry.get("test")
        file, sep, name = test.partition("::") if isinstance(test, str) else ("", "", "")
        if not sep or not file.strip() or not name.strip():
            problems.append(f"{label}: test {test!r} is not <file>::<name>")
        elif PATTERN_RE.search(name):
            problems.append(f"{label}: test {test!r} names a pattern of tests, not one test by its exact title")
        reason = entry.get("reason")
        if not isinstance(reason, str) or len(reason.strip().splitlines()) != 1:
            problems.append(f"{label}: reason must be one non-empty line")
        if not _real_date(entry.get("date")):
            problems.append(f"{label}: date {entry.get('date')!r} is not a real YYYY-MM-DD date")
    return problems


def check_retired(retired: Any, rows: Any) -> List[str]:
    """Every defect in the optional top-level ``retired`` list: the rows dropped
    on purpose (a duplicate a merge dropped, a row removed). Each entry is
    ``{"id", "reason", "date"}``, and no live row holds the id; or, for a row
    whose id another row keeps (one side of a clash), ``{"story", "reason",
    "date"}``. ``--next-id`` never gives out a retired number."""
    if retired is None:
        return []
    if not isinstance(retired, list):
        return ["retired is not a list"]
    live = {str(r.get("id")) for r in rows if isinstance(r, dict)} if isinstance(rows, list) else set()
    problems: List[str] = []
    for i, entry in enumerate(retired):
        label = f"retired[{i}]"
        if not isinstance(entry, dict):
            problems.append(f"{label}: not an object")
            continue
        rid = entry.get("id")
        if rid is None and _one_line(entry.get("story")):
            pass  # retired by its story: its id lives on in another row
        elif not isinstance(rid, str) or not ROW_ID_RE.match(rid):
            problems.append(f"{label}: id {rid!r} is not a row id ({ROW_ID_TEXT}), and there is no story"
                            f"{_rename_hint(rid)}")
        elif rid in live:
            problems.append(f"{label}: {rid} is retired and still a row")
        if not _one_line(entry.get("reason")):
            problems.append(f"{label}: reason must be one non-empty line")
        if not _real_date(entry.get("date")):
            problems.append(f"{label}: date {entry.get('date')!r} is not a real YYYY-MM-DD date")
    return problems


def retired_ids(data: Any) -> set:
    """The retired ids, and the retired stories in the form the merge check matches rows by."""
    entries = data.get("retired") if isinstance(data, dict) else None
    out: set = set()
    for e in entries if isinstance(entries, list) else []:
        if isinstance(e, dict):
            if e.get("id") is not None:
                out.add(str(e.get("id")))
            if e.get("story"):
                out.add(_row_key({"story": e["story"]}))
    return out


def _one_line(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value.strip().splitlines()) == 1


def check_features(data: Any, rows: Any, base_dir: str = HERE) -> List[str]:
    """Every defect in the optional top-level ``features`` list (alias key
    ``areas``) and in the rows' ``feature`` fields (alias key ``area``). Each
    feature has a unique kebab-case ``id``, a unique ``name`` and a one-line
    ``plain`` sentence; an optional ``doc`` must be a file under ``base_dir``.
    A row's ``feature`` must name one of them. Both spellings in one map, in
    one row, across the rows, or between the top level and the rows, is
    ``FEATURE_AND_AREA``."""
    problems: List[str] = []
    if isinstance(data, dict) and "features" in data and "areas" in data:
        problems.append("FEATURE_AND_AREA: the map has both 'features' and 'areas'; keep 'features'")
    key = "features" if isinstance(data, dict) and "features" in data else "areas"
    areas = _feature_list(data)
    known: set = set()
    if areas is not None and not isinstance(areas, list):
        problems.append(f"{key} is not a list")
        areas = []
    names: set = set()
    for i, area in enumerate(areas or []):
        label = f"{key}[{i}]"
        if not isinstance(area, dict):
            problems.append(f"{label}: not an object")
            continue
        aid = area.get("id")
        if not isinstance(aid, str) or not FEATURE_ID_RE.match(aid):
            problems.append(f"{label}: id {aid!r} is not a lower-case kebab-case id")
        elif aid in known:
            problems.append(f"{label}: duplicate id {aid}")
        else:
            known.add(aid)
            label = f"feature {aid}"
        name = area.get("name")
        if not _one_line(name):
            problems.append(f"{label}: name must be one non-empty line")
        elif name.strip().lower() in names:
            problems.append(f"{label}: another feature has the name {name.strip()!r}")
        else:
            names.add(name.strip().lower())
        if not _one_line(area.get("plain")):
            problems.append(f"{label}: plain must be one non-empty line")
        doc = area.get("doc")
        if doc is not None and (not isinstance(doc, str) or not os.path.isfile(os.path.join(base_dir, doc))):
            problems.append(f"{label}: doc {doc!r} is not a file")
    top = None
    if isinstance(data, dict) and ("features" in data) != ("areas" in data):
        top = "features" if "features" in data else "areas"
    spelled: Dict[str, List[str]] = {"feature": [], "area": []}
    for i, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict) or ("feature" not in row and "area" not in row):
            continue
        label = row.get("id") if isinstance(row.get("id"), str) else f"rows[{i}]"
        if "feature" in row and "area" in row:
            problems.append(f"FEATURE_AND_AREA: {label} has both 'feature' and 'area'; keep 'feature'")
            continue
        spelled["feature" if "feature" in row else "area"].append(label)
        area = _row_feature(row)
        if areas is None:
            problems.append(f"{label}: feature {area!r} but the map has no features list")
        elif not isinstance(area, str) or area not in known:
            problems.append(f"{label}: feature {area!r} is not an id in {key}")
    if spelled["feature"] and spelled["area"]:
        problems.append(f"FEATURE_AND_AREA: the rows mix the spellings: {spelled['feature'][0]} has 'feature' "
                        f"and {spelled['area'][0]} has 'area'; use 'feature' on every row")
    elif top == "features" and spelled["area"]:
        problems.append(f"FEATURE_AND_AREA: the map lists 'features' but {spelled['area'][0]} has 'area'; "
                        "use 'feature'")
    elif top == "areas" and spelled["feature"]:
        problems.append(f"FEATURE_AND_AREA: the map lists 'areas' but {spelled['feature'][0]} has 'feature'; "
                        "use one spelling: 'features' and 'feature'")
    return problems


def check_glossary(glossary: Any) -> List[str]:
    """Every defect in the optional top-level ``glossary``: each entry has a
    ``term``, a one-line ``plain`` meaning and optional ``aliases``; no
    term or alias belongs to two entries (case does not count)."""
    if glossary is None:
        return []
    if not isinstance(glossary, list):
        return ["glossary is not a list"]
    problems: List[str] = []
    owner: Dict[str, Any] = {}
    for i, entry in enumerate(glossary):
        label = f"glossary[{i}]"
        if not isinstance(entry, dict):
            problems.append(f"{label}: not an object")
            continue
        term = entry.get("term")
        if not _one_line(term):
            problems.append(f"{label}: term must be one non-empty line")
            continue
        label = f"glossary {term.strip()!r}"
        if not _one_line(entry.get("plain")):
            problems.append(f"{label}: plain must be one non-empty line")
        aliases = entry.get("aliases", [])
        if not isinstance(aliases, list) or not all(_one_line(a) for a in aliases):
            problems.append(f"{label}: aliases must be an array of non-empty strings")
            aliases = []
        for word in [term] + aliases:
            key = " ".join(word.split()).lower()
            if key in owner and owner[key][0] != i:
                problems.append(f"{label}: {word.strip()!r} is also a word of {owner[key][1]!r}")
            owner.setdefault(key, (i, term.strip()))
    return problems


def title_warnings(rows: Any) -> List[str]:
    """A row with no ``title``: not a defect, since old maps have none, but a title in
    the words a person asks with is what finds the row. A title that is not one
    non-empty line is a defect, reported by ``check``."""
    return [f"{row['id']}: no title; write one in the words a person would ask with"
            for row in (rows if isinstance(rows, list) else [])
            if isinstance(row, dict) and isinstance(row.get("id"), str) and "title" not in row]


def load_fixture(path: str) -> List[Dict[str, str]]:
    """An eval fixture: ``{"cases": [{"text", "row"}, ...]}`` or a bare list of cases.
    Each case is the words of a real work item (a PR or issue title) and the row it
    belongs to."""
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list):
        raise ValueError("the fixture is not a list of cases, nor an object with one under 'cases'")
    out = []
    for i, case in enumerate(cases):
        if not (isinstance(case, dict) and isinstance(case.get("text"), str) and case["text"].strip()
                and isinstance(case.get("row"), str)):
            raise ValueError(f"cases[{i}] needs a text and a row")
        out.append(case)
    return out


def evaluate(rows: List[Dict[str, Any]], cases: List[Dict[str, str]],
             area_names: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Top 1 and top 5 over the fixture: how often ``find`` puts the case's row first,
    and in the first five. A case whose text is already one of a row's asks is left
    out and counted, since it would test the map against its own memory."""
    asked = {" ".join(terms(a["text"])) for r in rows if isinstance(r, dict)
             for a in (r.get("asks") if isinstance(r.get("asks"), list) else []) if isinstance(a, dict)
             and isinstance(a.get("text"), str)}
    scored, misses, circular = [], [], 0
    for case in cases:
        if " ".join(terms(case["text"])) in asked:
            circular += 1
            continue
        ids = [h.get("id") for h in find(rows, case["text"], area_names)]
        rank = ids.index(case["row"]) + 1 if case["row"] in ids else None
        scored.append(rank)
        if rank != 1:
            misses.append({"text": case["text"], "row": case["row"], "rank": rank, "first": ids[0] if ids else None})
    n = len(scored)
    return {
        "cases": n,
        "top1": round(sum(1 for r in scored if r == 1) / n, 3) if n else None,
        "top5": round(sum(1 for r in scored if r is not None and r <= 5) / n, 3) if n else None,
        "leftOutAsAsks": circular,
        "misses": misses,
    }


def _list(value: Any) -> List[Any]:
    """A top-level list, or empty when it is missing or not a list (--check names that)."""
    return value if isinstance(value, list) else []


def features_with_counts(data: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Each feature with its row count, in map order; rows with no feature are
    counted last, under a null id."""
    counts: Dict[Optional[str], int] = {}
    for row in rows:
        if isinstance(row, dict):
            key = _row_feature(row) if isinstance(_row_feature(row), str) else None
            counts[key] = counts.get(key, 0) + 1
    out = [dict(a, rows=counts.get(a.get("id"), 0))
           for a in _list(_feature_list(data)) if isinstance(a, dict)]
    if counts.get(None):
        out.append({"id": None, "name": None, "plain": "rows with no feature yet", "rows": counts[None]})
    return out


def save_map(path: str, data: Dict[str, Any]) -> None:
    """Write the map back as two-space JSON, through a temporary file, so a failed
    write never leaves half a map."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def learn(data: Dict[str, Any], row_id: str, text: str, source: str, date: str,
          area_names: Optional[Dict[str, str]] = None) -> Tuple[int, Dict[str, Any]]:
    """Add ``text`` to the row's asks when ``find`` missed the row, and prove it helps.

    1. ``find`` already ranks the row first: nothing to learn.
    2. Text with an email address or a handle is refused; a near-duplicate of one
       of the row's asks is skipped.
    3. The ask goes in; with five already there, the oldest comes out.
    4. ``find`` runs again. The row must now rank in the top three, or the ask comes
       out again and learn fails.

    Returns ``(exit code, result)``; the map in ``data`` changes only on success.
    """
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    row = next((r for r in rows if isinstance(r, dict) and r.get("id") == row_id), None)
    if row is None:
        return 2, {"learned": False, "reason": f"no such row: {row_id}"}
    if private_words(text):
        return 2, {"learned": False, "reason": "the text holds an email address or a handle; record the ask without it"}
    before = [h.get("id") for h in find(rows, text, area_names)]
    rank = before.index(row_id) + 1 if row_id in before else None
    if rank == 1:
        return 0, {"learned": False, "reason": "find already ranks this row first", "rank": 1}
    for ask in _asks(row):
        if overlap(ask["text"], text) >= ASK_MATCH:
            return 0, {"learned": False, "reason": f"a near-duplicate of the ask {ask['text']!r}", "rank": rank}
    old = row.get("asks")
    asks = list(_asks(row)) + [{"text": text, "source": source, "date": date}]
    dropped = None
    if len(asks) > MAX_ASKS:
        oldest = min(range(len(asks) - 1), key=lambda i: (str(asks[i].get("date", "")), i))
        dropped = asks.pop(oldest)
    row["asks"] = asks
    after = [h.get("id") for h in find(rows, text, area_names, use_asks=False)]
    new_rank = after.index(row_id) + 1 if row_id in after else None
    if new_rank is None or new_rank > LEARN_TOP:
        if old is None:
            del row["asks"]
        else:
            row["asks"] = old
        return 1, {"learned": False, "reason": f"with the ask, the row still ranks {new_rank or 'nowhere'}; "
                   f"it must reach the top {LEARN_TOP}, so the ask was taken out", "rank": rank}
    result = {"learned": True, "row": row_id, "rankBefore": rank, "rankAfter": new_rank}
    if dropped is not None:
        result["dropped"] = dropped
    return 0, result


def learn_main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="capability_find.py learn",
                                     description="record the words find missed a row by, as one of its asks")
    parser.add_argument("--map", default=DEFAULT_MAP)
    parser.add_argument("--query-file", required=True, help="the ask, read from this file")
    parser.add_argument("--row", required=True, help="the row the ask belongs to")
    parser.add_argument("--source", required=True, help="person, issue:<owner>/<repo>#<n> or pr:<owner>/<repo>#<n>")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    args = parser.parse_args(argv)
    date = args.date or datetime.date.today().isoformat()
    if not ROW_ID_RE.match(args.row):
        print(f"capability_find.py: {args.row!r} is not a row id (expected {ROW_ID_TEXT})", file=sys.stderr)
        return 2
    if not ASK_SOURCE_RE.match(args.source):
        print(f"capability_find.py: --source {args.source!r} is not person, issue:<owner>/<repo>#<n> "
              f"or pr:<owner>/<repo>#<n>", file=sys.stderr)
        return 2
    if not _real_date(date):
        print(f"capability_find.py: --date {date!r} is not a real YYYY-MM-DD date", file=sys.stderr)
        return 2
    try:
        with open(args.query_file, encoding="utf-8-sig") as fh:
            text = " ".join(fh.read().split())
        data = load_map(args.map)
    except (OSError, ValueError) as exc:
        print(f"capability_find.py: {exc}", file=sys.stderr)
        return 2
    if not text or len(text) > MAX_ASK_CHARS:
        print(f"capability_find.py: the ask must be 1-{MAX_ASK_CHARS} characters", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("capability_find.py: the map is not an object", file=sys.stderr)
        return 2
    names = {a["id"]: str(a.get("name") or "") for a in _list(_feature_list(data))
             if isinstance(a, dict) and isinstance(a.get("id"), str)}
    code, result = learn(data, args.row, text, args.source, date, names)
    if result.get("learned"):
        save_map(args.map, data)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if code:
        print(f"capability_find.py: {result['reason']}", file=sys.stderr)
    return code


def pr_rows(body: str, known: List[str]) -> Tuple[List[str], List[int]]:
    """The rows a merged pull request's promise block names under "Capabilities" (new
    or changed; a "Touched" line and a "No row names" line name none), and the issue
    numbers its "Why" section closes, each with the repo it names or None."""
    m = PR_BLOCK_RE.search(body or "")
    if not m:
        return [], []
    # A template's placeholders sit in HTML comments ("<!-- Closes #12. -->"); they name nothing.
    block = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S)
    rows: List[str] = []
    section = None
    for line in block.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if section != "capabilities":
            continue
        if re.match(r"^\s*-\s*(touched|no row names)\b", line, re.I):
            continue
        for rid in known:
            if re.search(r"(?<![\w-])" + re.escape(rid) + r"(?![\w-])", line) and rid not in rows:
                rows.append(rid)
    why = re.search(r"^## Why\s*$(.*?)(?=^## |\Z)", block, re.S | re.M)
    closes = [(repo, int(n)) for repo, n in CLOSES_RE.findall(why.group(1))] if why else []
    return rows, closes


def refs_sync(data: Dict[str, Any], pulls: List[Dict[str, Any]], fixture: Dict[str, Any]) -> Dict[str, Any]:
    """Add a ref to every row a merged pull request's promise block names, one for the
    pull request and one for each issue it closes; a pull request that names exactly
    one row adds its title to the eval fixture as a case for that row."""
    rows = [r for r in (data.get("rows") if isinstance(data.get("rows"), list) else []) if isinstance(r, dict)]
    by_id = {r.get("id"): r for r in rows if isinstance(r.get("id"), str)}
    cases = fixture.setdefault("cases", [])
    report: Dict[str, Any] = {"pulls": 0, "refsAdded": [], "casesAdded": [], "skipped": []}
    for pull in pulls:
        repo, number = pull.get("repo"), pull.get("number")
        label = f"{repo}#{number}"
        if not (isinstance(repo, str) and REPO_RE.match(repo) and isinstance(number, int) and number > 0):
            report["skipped"].append({"pull": label, "reason": "needs repo as <owner>/<name> and a number"})
            continue
        if pull.get("merged") is not True:
            report["skipped"].append({"pull": label, "reason": "not merged"})
            continue
        named, closes = pr_rows(str(pull.get("body") or ""), list(by_id))
        if not named:
            report["skipped"].append({"pull": label, "reason": "its promise block names no row"})
            continue
        report["pulls"] += 1
        new_refs = [{"repo": repo, "kind": "pr", "number": number}]
        new_refs += [{"repo": other or repo, "kind": "issue", "number": n} for other, n in closes]
        for rid in named:
            row = by_id[rid]
            refs = row.get("refs") if isinstance(row.get("refs"), list) else []
            for ref in new_refs:
                if ref not in refs:
                    refs.append(dict(ref))
                    report["refsAdded"].append(dict(ref, row=rid))
            row["refs"] = refs
        title = " ".join(str(pull.get("title") or "").split())
        if len(named) == 1 and title:
            asked = {" ".join(terms(a["text"])) for a in _asks(by_id[named[0]])}
            if " ".join(terms(title)) in asked:
                report["skipped"].append({"pull": label, "reason": "its title is already one of the row's asks"})
            elif not any(isinstance(c, dict) and c.get("text") == title and c.get("row") == named[0] for c in cases):
                case = {"text": title, "row": named[0], "source": f"pr:{repo}#{number}"}
                cases.append(case)
                report["casesAdded"].append(case)
    return report


def refs_main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(prog="capability_find.py refs sync",
                                     description="add refs from merged pull requests' promise blocks")
    parser.add_argument("--map", default=DEFAULT_MAP)
    parser.add_argument("--input", required=True,
                        help="JSON: the merged pull requests, each {repo, number, title, body, merged}")
    parser.add_argument("--eval-file", default=None, help="the eval fixture (default: find-eval.json beside the map)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    fixture_path = args.eval_file or os.path.join(os.path.dirname(os.path.abspath(args.map)), DEFAULT_FIXTURE)
    try:
        data = load_map(args.map)
        with open(args.input, encoding="utf-8-sig") as fh:
            pulls = json.load(fh)
        fixture: Dict[str, Any] = {"$comment": "Real work-item titles linked to the one row each is about. "
                                   "Never put a row's asks here.", "cases": []}
        if os.path.exists(fixture_path):
            with open(fixture_path, encoding="utf-8-sig") as fh:
                loaded = json.load(fh)
            fixture = loaded if isinstance(loaded, dict) else {"cases": loaded}
    except (OSError, ValueError) as exc:
        print(f"capability_find.py: {exc}", file=sys.stderr)
        return 2
    if isinstance(pulls, dict):
        pulls = pulls.get("pulls")
    if not isinstance(data, dict) or not isinstance(pulls, list) or not isinstance(fixture.get("cases", []), list):
        print("capability_find.py: --input must be a list of pull requests, and the map and fixture objects",
              file=sys.stderr)
        return 2
    report = refs_sync(data, [p for p in pulls if isinstance(p, dict)], fixture)
    if not args.dry_run:
        if report["refsAdded"]:
            save_map(args.map, data)
        if report["casesAdded"]:
            save_map(fixture_path, fixture)
    report["dryRun"] = args.dry_run
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def cited_test_files(row: Dict[str, Any]) -> List[str]:
    """The files the row's evidence arrays cite, in order, each once."""
    out: List[str] = []
    for key in EVIDENCE_ARRAYS:
        for citation in _strings(row.get(key)):
            path = citation.partition("::")[0].strip()
            if path and path not in out:
                out.append(path)
    return out


def _inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), root]) == root
    except ValueError:
        return False


def _python_imports(source: str, test_path: str, root: str) -> List[str]:
    found: List[str] = []
    here = os.path.dirname(test_path)

    def resolve(module: str, names: List[str]) -> None:
        dots = len(module) - len(module.lstrip("."))
        parts = [p for p in module.lstrip(".").split(".") if p]
        if dots:
            base = here
            for _ in range(dots - 1):
                base = os.path.dirname(base)
            bases = [base]
        else:
            bases = [root, here, os.path.join(root, "src")]
        for base in bases:
            target = os.path.join(base, *parts) if parts else base
            candidates = [target + ".py", os.path.join(target, "__init__.py")]
            candidates += [os.path.join(target, n + ".py") for n in names]
            for c in candidates:
                if os.path.isfile(c) and _inside(c, root) and c not in found:
                    found.append(c)

    for m in PY_FROM_RE.finditer(source):
        names = [n.strip().split(" as ")[0].strip() for n in m.group(2).split(",")]
        resolve(m.group(1), [n for n in names if n.isidentifier()])
    for m in PY_IMPORT_RE.finditer(source):
        for part in m.group(1).split(","):
            resolve(part.strip().split(" as ")[0].strip(), [])
    return found


def _js_imports(source: str, test_path: str, root: str) -> List[str]:
    found: List[str] = []
    here = os.path.dirname(test_path)
    for pattern in JS_IMPORT_RES:
        for spec in pattern.findall(source):
            if not spec.startswith("."):
                continue  # a package, or a path alias the first version does not follow
            target = os.path.normpath(os.path.join(here, spec))
            stem_path = os.path.splitext(target)[0] if target.endswith((".js", ".jsx", ".mjs", ".cjs")) else target
            candidates = [target] + [stem_path + e for e in JS_EXTS] + [os.path.join(target, "index" + e) for e in JS_EXTS]
            for c in candidates:
                if os.path.isfile(c) and _inside(c, root):
                    if c not in found:
                        found.append(c)
                    break
    return found


def code_files(row: Dict[str, Any], root: str) -> Dict[str, Any]:
    """The local files the row's cited tests import: where to read before a wide code
    search. Python and JS/TS imports are followed one step; a package, a path alias
    or another language is not."""
    root = os.path.abspath(root)
    tests, missing, unsupported, files = [], [], [], []
    for rel in cited_test_files(row):
        path = os.path.normpath(os.path.join(root, rel))
        if not _inside(path, root) or not os.path.isfile(path):
            missing.append(rel)
            continue
        tests.append(rel)
        try:
            with open(path, encoding="utf-8-sig", errors="replace") as fh:
                source = fh.read()
        except OSError:
            missing.append(rel)
            continue
        if path.endswith(".py"):
            found = _python_imports(source, path, root)
        elif path.endswith(JS_EXTS):
            found = _js_imports(source, path, root)
        else:
            unsupported.append(rel)
            continue
        for f in found:
            name = os.path.relpath(f, root).replace(os.sep, "/")
            if name not in files:
                files.append(name)
    test_names = set(tests)
    return {"row": row.get("id"), "tests": tests,
            "files": sorted(f for f in files if f not in test_names),
            "missing": missing, "unsupported": unsupported}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="capability_find.py", description=__doc__.split("\n\n")[1],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--map", default=DEFAULT_MAP, help="path to map.json (default: beside this script)")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--row", metavar="ID", help="print one row by id; exit 2 when there is no such row")
    group.add_argument("--next-id", action="store_true",
                       help="print the id the next new row would take, skipping every number another branch holds")
    parser.add_argument("--fetch", action="store_true", help="with --next-id: git fetch the remotes first")
    parser.add_argument("--from", dest="source", metavar="ITEM", default=None,
                        help="with --next-id: the id from the work item a row comes from, issue:<n>, pr:<n> or "
                             "linear:<TEAM>-<n> (CAP-i1890a, then CAP-i1890b; CAP-ENG-421a); no branch can take the same one")
    group.add_argument("--check", action="store_true", help="validate map.json; exit 1 on any defect")
    group.add_argument("--features", "--areas", dest="features", action="store_true",
                       help="print the features, each with its row count (--areas is an alias)")
    group.add_argument("--feature", "--area", dest="feature", metavar="ID",
                       help="print the rows in one feature; exit 2 when there is no such feature (--area is an alias)")
    group.add_argument("--glossary", action="store_true", help="print the glossary")
    group.add_argument("--code", metavar="ID",
                       help="print the local files the row's cited tests import; exit 2 when there is no such row")
    group.add_argument("--eval", metavar="FIXTURE", nargs="?", const=DEFAULT_FIXTURE,
                       help="print top 1 and top 5 over a fixture of {text, row} cases "
                            "(default: find-eval.json beside the map)")
    parser.add_argument("query", nargs="?", help="search text; ranked matching rows are printed as a JSON array")
    return parser


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    # "learn" alone is a query; the subcommand always has its flags after it.
    if argv[:1] == ["learn"] and len(argv) > 1 and argv[1].startswith("--"):
        return learn_main(argv[1:])
    if argv[:2] == ["refs", "sync"]:
        return refs_main(argv[2:])
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        data = load_map(args.map)
    except (OSError, ValueError) as exc:
        print(f"capability_find.py: cannot read map {args.map}: {exc}", file=sys.stderr)
        return 2
    rows = data.get("rows", []) if isinstance(data, dict) else []

    if args.check:
        doc_root = data.get("docRoot", ".") if isinstance(data, dict) else "."
        if not isinstance(doc_root, str) or os.path.isabs(doc_root):
            print(f"capability_find.py: docRoot {doc_root!r} is not a relative path", file=sys.stderr)
            print(f"capability-check: {len(rows)} rows, 1 problems")
            return 1
        base_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(args.map)), doc_root))
        problems = check(rows, base_dir)
        problems += check_left_out(data.get("leftOut") if isinstance(data, dict) else None)
        problems += check_features(data, rows, base_dir)
        problems += check_glossary(data.get("glossary") if isinstance(data, dict) else None)
        problems += check_retired(data.get("retired") if isinstance(data, dict) else None, rows)
        problems += merge_problems(args.map, rows, data.get("leftOut") if isinstance(data, dict) else None,
                                   retired_ids(data))
        names_for_check = {a["id"]: str(a.get("name") or "") for a in _list(_feature_list(data))
                           if isinstance(a, dict) and isinstance(a.get("id"), str)}
        warnings = title_warnings(rows) + ask_conflicts(rows, names_for_check)
        for line in problems:
            print(f"capability_find.py: {line}", file=sys.stderr)
        for line in warnings:
            print(f"capability_find.py: warning: {line}", file=sys.stderr)
        tail = f", {len(warnings)} warnings" if warnings else ""
        print(f"capability-check: {len(rows)} rows, {len(problems)} problems{tail}")
        return 1 if problems else 0

    if args.source is not None and not args.next_id:
        print("capability_find.py: --from goes with --next-id", file=sys.stderr)
        return 2
    if args.next_id and args.source is not None:
        ids: Dict[str, str] = {}
        taken_on_branches(args.map, args.fetch, ids)
        used = set(ids) | {str(r.get("id", "")) for r in rows if isinstance(r, dict)} | retired_ids(data)
        try:
            print(next_id_from(args.source, used))
        except ValueError as exc:
            print(f"capability_find.py: {exc}", file=sys.stderr)
            return 2
        return 0
    if args.next_id:
        taken = taken_on_branches(args.map, args.fetch)
        for rid in retired_ids(data):  # a retired number is never given out again
            m = CAP_ID_RE.match(rid)
            if m:
                taken.setdefault(int(m.group(1)), "retired")
        here = {int(m.group(1)) for m in (CAP_ID_RE.match(str(r.get("id", ""))) for r in rows if isinstance(r, dict)) if m}
        elsewhere = sorted(n for n in taken if n not in here and n > max(here or {0}) and taken[n] != "retired")
        if elsewhere:
            print("capability_find.py: skipped " + ", ".join(f"CAP-{n} ({taken[n]})" for n in elsewhere[:5])
                  + ": taken on another branch", file=sys.stderr)
        print(next_id(rows, taken))
        return 0

    meta = data if isinstance(data, dict) else {}
    if args.features:
        print(json.dumps(features_with_counts(meta, rows), indent=2, ensure_ascii=False))
        return 0
    if args.feature is not None:
        if not any(isinstance(a, dict) and a.get("id") == args.feature for a in _list(_feature_list(meta))):
            print(f"capability_find.py: no such feature: {args.feature}", file=sys.stderr)
            return 2
        print(json.dumps([r for r in rows if isinstance(r, dict) and _row_feature(r) == args.feature],
                         indent=2, ensure_ascii=False))
        return 0
    if args.glossary:
        print(json.dumps(_list(meta.get("glossary")), indent=2, ensure_ascii=False))
        return 0

    if args.code is not None:
        if not ROW_ID_RE.match(args.code):
            print(f"capability_find.py: {args.code!r} is not a row id (expected {ROW_ID_TEXT})", file=sys.stderr)
            return 2
        row = next((r for r in rows if isinstance(r, dict) and r.get("id") == args.code), None)
        if row is None:
            print(f"capability_find.py: no such row: {args.code}", file=sys.stderr)
            return 2
        doc_root = meta.get("docRoot", ".")
        doc_root = doc_root if isinstance(doc_root, str) and not os.path.isabs(doc_root) else "."
        root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(args.map)), doc_root))
        print(json.dumps(code_files(row, root), indent=2, ensure_ascii=False))
        return 0

    if args.row is not None:
        if not ROW_ID_RE.match(args.row):
            print(f"capability_find.py: {args.row!r} is not a row id (expected {ROW_ID_TEXT})", file=sys.stderr)
            return 2
        for row in rows:
            if row.get("id") == args.row:
                print(json.dumps(row, indent=2, ensure_ascii=False))
                return 0
        print(f"capability_find.py: no such row: {args.row}", file=sys.stderr)
        return 2

    names = {a["id"]: str(a.get("name") or "") for a in _list(_feature_list(meta))
             if isinstance(a, dict) and isinstance(a.get("id"), str)}
    if args.eval is not None:
        path = args.eval
        if path == DEFAULT_FIXTURE:
            path = os.path.join(os.path.dirname(os.path.abspath(args.map)), DEFAULT_FIXTURE)
        try:
            cases = load_fixture(path)
        except (OSError, ValueError) as exc:
            print(f"capability_find.py: cannot read fixture {path}: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(evaluate(rows, cases, names), indent=2, ensure_ascii=False))
        return 0

    if args.query is None:
        parser.print_usage(sys.stderr)
        print("capability_find.py: a query, --row <id>, --next-id, --check, --features, --feature <id> or --glossary "
              "is required", file=sys.stderr)
        return 2
    print(json.dumps(find(rows, args.query, names), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
