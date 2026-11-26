#!/usr/bin/env python3
"""The capability map, joined to a real test run: what is promised, and what is proven.

    python3 map_report.py --map docs/capabilities/map.json
    python3 map_report.py --map map.json --junit test-results/            # a folder of JUnit XML files
    python3 map_report.py --map map.json --junit a.xml --junit b.xml --format markdown
    python3 map_report.py --map map.json --junit run.xml --json
    python3 map_report.py --map map.json --junit run.xml --strict         # exit 1 on a failing, bad or never-run citation, or an optimistic verdict
    python3 map_report.py --map map.json --junit run.xml --orphans        # also list every test in the run that no row cites
    python3 map_report.py --map map.json --junit run.xml --fail-on-orphans  # exit 1 when any test in the run has no row
    python3 map_report.py --map map.json --surfaces entry-points.txt --fail-on-unmapped   # every entry point in the code has a row

A green test suite says the tests pass. It does not say the product keeps its
promises. This report reads each row of the map (a story, its Given/When/Then
scenarios, the altitude each `Then` asserts on, and the tests cited as proof)
and joins every citation to the test run, so each row's proof is shown as it
stands in that run, not as someone last wrote it down.

**Citations.** A citation is ``<test file>::<test name>``, as the recipe writes
it. It matches a JUnit ``<testcase>`` when the name matches and, if the run
records a file for the case, the file matches too, path segment by path
segment. The file comes from a ``file`` attribute on the case or its suite, a
suite named after a path (Vitest, Playwright; a nested suite named like a
path never overrides an outer suite's ``file`` attribute), or a dotted ``classname``
(pytest; a classname ending in a source extension such as ``.ts`` is a file
name, not a module). The name matches the case's own name, or its full title:
the classname and the name joined by `` › ``, `` > ``, ``.``, ``::`` or a
space. Only when nothing matches exactly does the name match as a leaf (a
title ending in a joiner and the name: Jest, Vitest and Playwright put the
describe path in the name) or as a describe block (a title starting with the
name, then `` > `` or `` › ``). A pytest parametrised case ``test_a[1-b]``
also answers to ``test_a``. A parametrised name (``%s``, ``${x}``, ``$name``)
matches any value in its slots; when its longest literal part is shorter than
three characters it would match nearly anything, so it is a ``bad-citation``.
So is a citation with no name, a non-string citation, or a ``<placeholder>``
left unfilled -- a ``<word>`` run in the name or the file that no case in the
run matches exactly; a real title can hold an HTML tag (``<script>``), and a
citation of one matches its case by exact title only. A citation that
matches no case is ``never-ran`` -- a skipped
file, a filtered project, a renamed test -- unless its whole lane is out of
the run: a run is often one suite's results, with the e2e suite written by
a command of its own. When no well-formed citation of a lane, across the
whole map, matches a case, and the run holds neither a file nor a test
title any of them cites (for a case that records no file, the last part
of a cited describe path counts as a title), nor a case in the folder of a
cited file or a subfolder of it, the lane's citations are ``not-run``: not
checked, never proof, but not a stale citation either. The summary names
each such lane once (``summary.lanesNotInRun``, each ``{lane, citations}``).
Once one citation of the lane matches, or the run holds a file, a title or a
folder it cites, the suite ran, and a citation that matches nothing stays
``never-ran``: a lane whose every cited file was deleted still fails
``--strict`` when its suite ran. A run file named after a folder of the
cited path (``e2e.xml`` for ``e2e/tests/a.spec.ts``) holds that folder's
suite: a path it records from a folder on the cited path
(``tests/b.spec.ts``, ``admin/new.spec.ts``) that lands in the cited folder
or below, or a path from the project root under the folder it is named
after (``e2e/smoke/new.spec.ts``), shows the suite ran; when the cited
folder is on disk, that path must be on disk too. Any other run file
cannot place a relative path or a sibling folder, and a unit run in a
subfolder of the cited folder is read as that lane's suite
(``_in_cited_folder``).
When a citation matches more than
one case, the worst result counts. Cases in one *place* -- one run file and
one recorded file -- are one test (a parametrised test, a describe block, a
test run once per project); a case with no recorded file is a place of its
own. Across places a citation is narrowed to the places whose recorded file
is the cited path itself, then to the one whose run file is named after a
folder the cited path runs through (``api.xml`` for
``apps/api/tests/x.test.ts`` when the run records ``tests/x.test.ts``). Left
with more than one place, the citation is ``ambiguous`` (JSON ``ambiguous``
and ``places``): the run cannot tell those tests apart, so the worst of them
counts and none is homed. A case is failing on ``<failure>``,
``<error>`` or a ``status``/``result`` attribute that says failed; skipped on
``<skipped>``, ``skipped="true"`` or a status such as ``notrun`` or
``disabled``.

**Buckets** (one per row, worst first): ``failing`` (a cited test failed),
``bad-citation``, ``never-ran``, ``skipped``, ``not-run`` (a citation in a
lane the run left out), ``passing`` (every citation ran and passed),
``external`` (only sibling citations), ``no-test`` (nothing cited). Citations in the sibling lane are another repository's proof: they are
checked for shape, listed as ``external``, and never looked up in this run. A
config that gives sibling the same array as another altitude is refused.

**Altitude verdict**, computed from the run. Each scenario's ``altitude`` picks
the one lane that can prove it (``map.lanes`` in the promise config; by
default data and response → ``tests``, perception → ``e2eTests``, judgement →
``evalTests``, sibling → ``siblingTests``). A scenario is **proven** when that
lane holds at least one citation that passed in this run and none that failed,
was skipped, never ran, was not run or is a bad citation: one green test proves nothing
while another in the same lane is red or unrun. A sibling scenario is proven
by at least one well-formed sibling citation. A row is:

- ``proven`` -- every scenario is proven;
- ``under-proven`` -- something cited for the row passed, but at least one
  scenario has no passing test in its own lane: green, below or beside what the
  sentence promises;
- ``not-built`` -- nothing cited for the row passed.

Data and response share ``tests`` by default, so a row's data and response
scenarios cannot be told apart by lane; say so in the recipe, or give response
its own array. The computed verdict is compared with the row's recorded
``verdict``: recorded higher than the run shows is **optimistic** (a finding);
recorded lower is **promotable** (``reconcile`` promotes it, after a watched
kill -- this report never writes the map); a recorded value that is not one of
the three is **unknown-verdict**.

The verdict trusts the lane a citation is filed in. A DOM-simulation test filed
in the perception lane reads as proof of what a person sees; a verdict typed by
hand has the same weakness. A watched kill (``reconcile``) is the guard, not
this report.

A row may carry ``priority`` (``must``, ``should`` or ``could``); when any row
does, the summary leads with the ``must`` rows not proven -- the number to
drive down.

**Every test has a home.** With a run, a test case is *homed* when at least
one well-formed citation in any evidence array of any row matches it, by the
matching above and not ambiguously; a sibling citation never matches a case
in this run. A case no row cites is an **orphan**: a test that proves
something the map does not promise, or a promise the map is missing. The
JSON carries ``orphans`` (each
``{file, name, classname, status}``; ``file`` is null when the run records
none, or only a dotted pytest classname) and ``summary.orphanCount`` whenever
a run is given; ``--orphans`` also lists them in the tree and the Markdown as
``file::name`` (the classname when the run records no file) with the case's
status, and ``--fail-on-orphans`` exits 1 when there is any. Both need
``--junit``.

A test can be left with no row on purpose -- a helper's own test, a type
test. The map's top-level ``leftOut`` list names each one:
``{"test": "<file>::<name>", "reason": "<one line>", "date": "YYYY-MM-DD"}``.
An entry names one test: it matches a case only by one of the case's exact
titles (its name, or its full title; a pytest parametrised case also
answers to its base name) and its file -- never by a leaf, a describe
block, a ``%s`` pattern or a bare name -- so one line cannot hide a
describe block or a file. A case an
entry matches is not an orphan, unless the entry has a ``problem``: its
test is not ``<file>::<name>``, its reason is not one line, its date is not
a real date, its name is an unfilled ``<placeholder>``, the run cannot
place the test, or a row cites the test too. The JSON always carries
``leftOut`` (each entry with its ``status``, ``problem`` and ``ran``:
whether it matched a case in this run, null with no run; with a run also
``matches`` and ``hides``, the cases it keeps from being orphans) and
``summary.leftOutCount`` and ``summary.leftOutProblemCount``; with a run,
an entry that matched no case is stale (``summary.staleLeftOutCount``: the
test is gone or renamed), a failing one is counted
(``summary.failingLeftOutCount``), and ``--orphans`` lists the entries
under "Left out".

**Every entry point has a home.** ``--surfaces FILE`` (``-`` for stdin)
reads the code's entry points, one per line -- in the project's own
notation, such as ``GET /me``, ``page /admin/clients`` or ``cron
weekly-update`` -- ignoring blank lines and lines starting with ``#``. A row
lists the entry points its behaviour enters through in ``surfaces``;
matching is exact after trimming. An entry point no row lists is
**unmapped** (JSON ``unmappedSurfaces``, ``summary.unmappedSurfaceCount``);
a row surface the list does not have is **stale** (``staleSurfaces``, each
``{id, surface}``, ``summary.staleSurfaceCount``): the code no longer has
it. Both are listed in the tree and the Markdown, and
``--fail-on-unmapped`` exits 1 on an unmapped one. An empty list is
refused. It works with or without ``--junit``.

**Rows with no outcome doc.** A row whose ``doc`` is null, absent or empty
records what the code does today -- a backfilled row, or one filed from
feedback -- and is not a promise until an outcome doc makes it one. The
summary counts them (``summary.rowsWithoutDoc``), with or without a run.

The run itself is checked: a run with no test cases is refused (an empty or
truncated result file must never read as "nothing failed"), and the JSON and
Markdown output record the run's totals and a sha256 fingerprint of the map and
every run file (and the config, when one is given), so a report can be traced
to exactly what it read. Every run file must hold at least one test case.

**Skipped citations.** A skipped test proves nothing, but ``--strict``
fails only on a verdict recorded higher than the run shows, so a row
recorded ``under-proven`` passes with one of its tests skipped. With a
run, the JSON carries ``skippedCitations`` (each ``{id, lane, test}``) and
``summary.skippedCitationCount``. ``--fail-on-skipped`` lists them in the
tree and the Markdown and exits 1 when there is one. It needs ``--junit``
and does not change ``--strict``.

With no ``--junit``, the report shows the map as recorded: rows, scenarios,
citations and recorded verdicts, and no buckets.

Exit 0, or 1 under ``--strict`` when a row is failing, bad-citation or
never-ran, or its recorded verdict is optimistic or unknown (a ``not-run``
lane never proves a scenario, so a verdict recorded on it is optimistic), under
``--fail-on-orphans`` when a test in the run has no row or a ``leftOut``
entry is stale, failing or has a problem, under
``--fail-on-unmapped`` when an entry point has no row, and under
``--fail-on-skipped`` when the run skipped a test a row cites; 2 on a usage error
(``--orphans``, ``--fail-on-orphans`` or ``--fail-on-skipped`` without ``--junit``,
``--fail-on-unmapped`` without ``--surfaces``) or an unreadable map, run or
entry-point file. Stdlib only; no network; the map is never
written.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from typing import Any, Dict, Iterable, List, Optional, Tuple

DEFAULT_LANES = {
    "data": "tests",
    "response": "tests",
    "perception": "e2eTests",
    "judgement": "evalTests",
    "sibling": "siblingTests",
}
EVIDENCE_ARRAYS = ("tests", "e2eTests", "evalTests", "siblingTests")
VERDICT_RANK = {"not-built": 0, "under-proven": 1, "proven": 2}
# Worst first: a row takes the first bucket any of its citations lands in.
BUCKET_ORDER = ("failing", "bad-citation", "never-ran", "skipped", "not-run", "passing")
# A citation in one of these states stops its lane from proving a scenario.
BLOCKING = ("failing", "bad-citation", "never-ran", "skipped", "not-run")
TITLE_JOINERS = (" › ", " > ", ".", " ", "::")
DESCRIBE_JOINERS = (" > ", " › ")
# A placeholder a person forgot to fill: <test name>, <file>. Not JSX such as <Button />.
PLACEHOLDER_RE = re.compile(r"<[a-z][a-z0-9 _-]*>")
# Parametrised titles: printf-style (%s, %d, …) and template (${x}, $name) slots.
PARAM_RE = re.compile(r"%[sdifjopc#%]|\$\{[^}]*\}|\$[A-Za-z_][A-Za-z0-9_.]*")
MIN_LITERAL = 3
SOURCE_EXT_RE = re.compile(
    r"\.(ts|tsx|js|jsx|mjs|cjs|mts|cts|py|go|java|kt|rb|php|cs|rs|swift|scala|ex|exs|feature)$", re.I
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SKIP_STATUS = {"notrun", "not_run", "skipped", "skip", "disabled", "suppressed", "pending", "ignored"}
FAIL_STATUS = {"failed", "failure", "fail", "error", "errored", "broken"}


class UsageError(Exception):
    pass


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------


def _norm_path(path: str) -> str:
    path = path.replace("\\", "/").strip()
    while path.startswith("./"):
        path = path[2:]
    return path


def _dotted_to_path(classname: str) -> Optional[str]:
    """``tests.test_mute.TestMute`` → ``tests/test_mute/TestMute`` (pytest style), else None.

    A classname that is a file name (``example.spec.ts``) is not a dotted module."""
    if "/" in classname or " " in classname or "." not in classname or SOURCE_EXT_RE.search(classname):
        return None
    return classname.replace(".", "/")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]  # drop an XML namespace


def load_run(paths: List[str]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Every JUnit ``<testcase>`` in the given files or folders, and the files read.

    A file with no test case at all is refused by name: an empty or truncated
    result file must never read as "nothing failed"."""
    files: List[str] = []
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, names in os.walk(p):
                files.extend(os.path.join(root, n) for n in sorted(names) if n.lower().endswith(".xml"))
        elif os.path.isfile(p):
            files.append(p)
        else:
            raise UsageError(f"no such run file or folder: {p}")
    if not files:
        raise UsageError("no JUnit XML files found in " + ", ".join(paths))
    cases: List[Dict[str, Any]] = []
    for f in sorted(files):
        try:
            root = ET.parse(f).getroot()
        except (ET.ParseError, OSError) as exc:
            raise UsageError(f"cannot read JUnit XML {f}: {exc}")
        found = list(_cases(root, suite_file=None))
        if not found:
            raise UsageError(f"{f} has no test cases; an empty or truncated run file proves nothing")
        for c in found:
            c["source"] = f  # the run file: part of where a case lives
        cases.extend(found)
    for i, c in enumerate(cases):
        c["titles"] = _titles(c)
        c["index"] = i  # the case's identity for the orphan count
    return cases, sorted(files)


def fingerprint(paths: List[str], extra: Optional[str] = None) -> str:
    """A short sha256 over every file read, in order, and ``extra`` text
    (the entry-point list, which may come from stdin) when given."""
    digest = hashlib.sha256()
    for path in paths:
        with open(path, "rb") as fh:
            digest.update(fh.read().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    if extra is not None:
        digest.update(extra.replace("\r\n", "\n").encode("utf-8"))
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()[:16]


def load_surfaces(path: str) -> Tuple[List[str], str]:
    """The entry points listed in ``path`` (``-`` for stdin, read as UTF-8),
    one per line, trimmed, first occurrence kept; a leading byte-order mark,
    blank lines and ``#`` lines are ignored.
    Also returns the text read, for the fingerprint. An empty list is
    refused: it would read as "every entry point has a row"."""
    try:
        if path == "-":
            # read bytes, so a leading BOM (PowerShell writes one) is dropped
            # like a file's, whatever the console's own encoding is
            raw = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode("utf-8")
            text = raw.decode("utf-8-sig")
        else:
            with open(path, "r", encoding="utf-8-sig") as fh:
                text = fh.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise UsageError(f"cannot read entry points from {path}: {exc}")
    surfaces: List[str] = []
    seen = set()
    for line in text.splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#") and entry not in seen:
            seen.add(entry)
            surfaces.append(entry)
    if not surfaces:
        raise UsageError(f"{path} lists no entry points; an empty list proves nothing")
    return surfaces, text


def row_surfaces(row: Dict[str, Any]) -> List[str]:
    """A row's ``surfaces``: its non-empty strings, trimmed (a lone string
    is one entry point)."""
    value = row.get("surfaces")
    values = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    return [v.strip() for v in values if isinstance(v, str) and v.strip()]


def join_surfaces(rows: List[Dict[str, Any]], surfaces: List[str]) -> Tuple[List[str], List[Dict[str, Any]]]:
    """(entry points no row lists, row surfaces the list does not have).

    Matching is exact after trimming. A row surface missing from the list
    is stale: the code no longer has that entry point, or names it
    differently."""
    listed = set(surfaces)
    homed = {s for r in rows for s in r["surfaces"]}
    unmapped = [s for s in surfaces if s not in homed]
    stale = [{"id": r["id"], "surface": s} for r in rows for s in r["surfaces"] if s not in listed]
    return unmapped, stale


def _suite_file(node: ET.Element) -> Tuple[Optional[str], int]:
    """The file a suite names, and how sure that is: 3 for a ``file`` or
    ``filepath`` attribute, 2 for a name ending in a source extension, 1 for
    a name with a slash (Vitest and Playwright name the suite after the test
    file; a describe block such as ``v1/users`` looks the same), 0 for none."""
    file = node.get("file") or node.get("filepath")
    if file:
        return file, 3
    name = node.get("name") or ""
    if " " in name:
        return None, 0
    if SOURCE_EXT_RE.search(name):
        return name, 2
    return (name, 1) if "/" in name else (None, 0)


def _cases(node: ET.Element, suite_file: Optional[str], sure: int = 0) -> Iterable[Dict[str, Any]]:
    if _local(node.tag) == "testsuite":
        # a nested suite's file wins only when it is at least as sure as the
        # outer one: a describe named like a path never overrides a file attribute
        file, how = _suite_file(node)
        if file and how >= sure:
            suite_file, sure = file, how
    if _local(node.tag) == "testcase":
        yield _case(node, suite_file)
        return
    for child in node:
        if _local(child.tag) in ("testcase", "testsuite", "testsuites"):
            yield from _cases(child, suite_file, sure)


def _case(el: ET.Element, suite_file: Optional[str]) -> Dict[str, Any]:
    tags = {_local(c.tag) for c in el}
    status = (el.get("status") or el.get("result") or "").strip().lower()
    if "failure" in tags or "error" in tags or status in FAIL_STATUS:
        outcome = "failing"
    elif "skipped" in tags or status in SKIP_STATUS or (el.get("skipped") or "").lower() == "true":
        outcome = "skipped"
    else:
        outcome = "passing"
    classname = (el.get("classname") or "").strip()
    file = el.get("file") or el.get("filepath") or suite_file
    dotted = False
    if not file:
        file = _dotted_to_path(classname)
        dotted = file is not None
    return {
        "name": (el.get("name") or "").strip(),
        "classname": classname,
        "file": _norm_path(file) if file else None,
        "dotted": dotted,
        "outcome": outcome,
    }


def _titles(case: Dict[str, Any]) -> List[str]:
    name, cls = case["name"], case["classname"]
    names = [name]
    if "[" in name and name.endswith("]"):
        names.append(name[: name.index("[")])  # pytest parametrised: test_a[1-b] is also test_a
    titles = list(names)
    if cls:
        for n in names:
            titles.extend(cls + j + n for j in TITLE_JOINERS)
            if _dotted_to_path(cls):
                # pytest node ids cite the class: tests/test_x.py::TestX::test_y
                titles.append(cls.rsplit(".", 1)[-1] + "::" + n)
    return titles


def _name_matchers(name: str):
    """(exact, fallback) predicates over a case's titles, or None when the name
    cannot identify a test. The fallback -- a leaf title after any joiner, or a
    describe block's title -- is used only when nothing matches exactly."""
    if PARAM_RE.search(name):
        literals = PARAM_RE.split(name)
        if max((len(l.strip()) for l in literals), default=0) < MIN_LITERAL:
            return None
        pattern = re.compile(".+".join(re.escape(l) for l in literals) + "$")

        def parametrised(titles: List[str]) -> bool:
            return any(pattern.match(t) for t in titles)
        return parametrised, None

    def exact(titles: List[str]) -> bool:
        return name in titles

    def fallback(titles: List[str]) -> bool:
        return any(
            t.endswith(j + name) for t in titles for j in TITLE_JOINERS
        ) or any(t.startswith(name + j) for t in titles for j in DESCRIBE_JOINERS)
    return exact, fallback


def exact_cases(file: str, name: str, cases: List[Dict[str, Any]],
                index: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> List[Dict[str, Any]]:
    """The cases whose own title is exactly ``name`` (no leaf, describe or
    parametrised matching) and whose recorded file matches ``file``. A
    ``<placeholder>`` in the file part matches only a file the run records."""
    pool = index.get(name, []) if index is not None else [c for c in cases if name in c["titles"]]
    file_placeholder = bool(PLACEHOLDER_RE.search(file))
    return [c for c in pool if (not file or _file_matches(file, c)) and (c["file"] or not file_placeholder)]


def _file_matches(cited: str, case: Dict[str, Any]) -> bool:
    case_file = case["file"]
    if not case_file:
        return True  # the run records no file for this case: match on name alone
    cited = _norm_path(cited)
    stem = SOURCE_EXT_RE.sub("", cited)
    for candidate in (cited, stem):
        if candidate == case_file or candidate.endswith("/" + case_file) or case_file.endswith("/" + candidate):
            return True
        # only a dotted classname carries the test class after the module: tests/test_x/TestX
        if case["dotted"] and case_file.startswith(candidate + "/"):
            return True
    return False


# ---------------------------------------------------------------------------
# The map
# ---------------------------------------------------------------------------


def load_map(path: str) -> Tuple[List[Dict[str, Any]], List[Any], str]:
    """Return the rows, left-out list and digest of the map snapshot read."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        data = json.loads(raw.decode("utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read map {path}: {exc}")
    rows = data.get("rows") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise UsageError(f"{path} has no 'rows' list")
    left_out = data.get("leftOut") if isinstance(data, dict) else None
    if left_out is not None and not isinstance(left_out, list):
        raise UsageError(f"{path}: leftOut is not a list")
    return [r for r in rows if isinstance(r, dict)], list(left_out or []), hashlib.sha256(raw).hexdigest()


def load_lanes(config_path: Optional[str]) -> Dict[str, str]:
    lanes = dict(DEFAULT_LANES)
    if config_path:
        try:
            with open(config_path, "r", encoding="utf-8-sig") as fh:
                config = json.load(fh)
        except (OSError, ValueError) as exc:
            raise UsageError(f"cannot read config {config_path}: {exc}")
        map_config = config.get("map") if isinstance(config, dict) else None
        raw = map_config.get("lanes") if isinstance(map_config, dict) else None
        if isinstance(raw, dict):
            for altitude, value in raw.items():
                if isinstance(value, str) and value.replace("[]", "").strip():
                    lanes[altitude] = value.replace("[]", "").strip()
    sibling = lanes.get("sibling")
    shared = sorted(a for a, lane in lanes.items() if lane == sibling and a != "sibling")
    if shared:
        raise UsageError(
            f"map.lanes gives sibling the same array as {', '.join(shared)} ({sibling}); sibling citations "
            "are another repository's proof and are never checked against this run, so they need their own array"
        )
    return lanes


def split_citation(citation: Any) -> Tuple[str, str]:
    if isinstance(citation, dict):
        file, name = citation.get("file"), citation.get("name")
        return (file if isinstance(file, str) else "").strip(), (name if isinstance(name, str) else "").strip()
    if not isinstance(citation, str):
        return "", ""
    if "::" in citation:
        file, name = citation.split("::", 1)
        return file.strip(), name.strip()
    return "", citation.strip()


# ---------------------------------------------------------------------------
# The join
# ---------------------------------------------------------------------------


def judge_citation(citation: Any, lane: str, cases: Optional[List[Dict[str, Any]]],
                   sibling_lane: str, index: Optional[Dict[str, List[Dict[str, Any]]]] = None,
                   homed: Optional[Dict[int, str]] = None, owner: str = "a row") -> Dict[str, Any]:
    """One citation's status in the run. ``homed``, when given, maps the
    index of every case the citation homes to ``owner`` (the first to home
    it wins): the reverse direction, used to find the tests no row cites."""
    file, name = split_citation(citation)
    out: Dict[str, Any] = {"lane": lane, "file": file, "name": name}
    matchers = _name_matchers(name) if name else None
    if not name or matchers is None:
        out["status"] = "bad-citation"
        return out
    if PLACEHOLDER_RE.search(name) or PLACEHOLDER_RE.search(file):
        # An unfilled <placeholder> -- unless the run holds a test by exactly
        # this name (a real title may carry an HTML tag), and then only an
        # exact match counts.
        if lane == sibling_lane or cases is None or not exact_cases(file, name, cases, index):
            out["status"] = "bad-citation"
            return out
        matchers = (lambda titles: name in titles), None
    if lane == sibling_lane:
        out["status"] = "external"
        return out
    if cases is None:
        out["status"] = "not-run"
        return out
    exact, fallback = matchers

    def pick(pred, pool):
        return [c for c in pool if pred(c["titles"]) and (not file or _file_matches(file, c))]

    pool = index.get(name, []) if (index is not None and fallback is not None) else cases
    matched = pick(exact, pool)
    if not matched and fallback is not None:
        matched = pick(fallback, cases)
    meant, places = narrow(file, matched)
    if places > 1:
        # the run cannot say which of these tests the citation means: judge
        # the worst of them, and home none
        out["ambiguous"] = True
        out["places"] = places
    else:
        matched = meant
        if homed is not None:
            for c in matched:
                homed.setdefault(c["index"], owner)
    out["matches"] = len(matched)
    if not matched:
        out["status"] = "never-ran"
    else:
        out["status"] = min((c["outcome"] for c in matched), key=BUCKET_ORDER.index)
    return out


def _place(case: Dict[str, Any]) -> Tuple[Any, ...]:
    """Where a case lives, as far as the run can say: its run file and the
    file it records. A case with no recorded file is a place of its own --
    two such cases with one name may be two tests in two files."""
    return (case["source"], case["file"]) if case["file"] else (case["source"], None, case["index"])


def _leading_segments(cited: str, case_file: str) -> List[str]:
    """The segments of the cited path in front of the case's recorded file
    (``apps/api`` for ``apps/api/tests/x.test.ts`` against ``tests/x.test.ts``)."""
    for candidate in (cited, SOURCE_EXT_RE.sub("", cited)):
        if candidate.endswith("/" + case_file):
            return [s.lower() for s in candidate[: -len(case_file) - 1].split("/") if s]
    return []


def narrow(file: str, matched: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """The cases a citation means, and how many places they sit in.

    Cases in one place -- one run file and one recorded file -- are one test
    (a parametrised test, a describe block, a test run once per project).
    Across places the citation is narrowed: to the places whose recorded file
    is the cited path itself, then to the one whose run file is named after
    a folder the cited path runs through (``api.xml`` for
    ``apps/api/tests/x.test.ts`` when the run records ``tests/x.test.ts``).
    Returns ``(cases, 1)`` once one place is left, else ``(matched, n)``:
    the run cannot tell the tests apart."""
    places: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
    for c in matched:
        places.setdefault(_place(c), []).append(c)
    if len(places) <= 1:
        return matched, len(places)
    keep = list(places)
    if file:
        cited = _norm_path(file)
        exact = [p for p in keep if p[1] in (cited, SOURCE_EXT_RE.sub("", cited))]
        keep = exact or keep
        if len(keep) > 1:
            named = [p for p in keep if p[1] and os.path.splitext(os.path.basename(p[0]))[0].lower()
                     in _leading_segments(cited, p[1])]
            keep = named if len(named) == 1 else keep
    if len(keep) == 1:
        return places[keep[0]], 1
    return matched, len(places)


def build_index(cases: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = {}
    for c in cases:
        for t in set(c["titles"]):
            index.setdefault(t, []).append(c)
    return index


def row_citations(row: Dict[str, Any], lanes: Dict[str, str], cases: Optional[List[Dict[str, Any]]],
                  index: Optional[Dict[str, List[Dict[str, Any]]]] = None,
                  homed: Optional[Dict[int, str]] = None) -> List[Dict[str, Any]]:
    """Every citation in the row's evidence arrays, judged against the run."""
    sibling_lane = lanes.get("sibling", "siblingTests")
    owner = row.get("id") if isinstance(row.get("id"), str) and row.get("id") else "a row"
    arrays = list(EVIDENCE_ARRAYS) + sorted(set(lanes.values()) - set(EVIDENCE_ARRAYS))
    citations = []
    for lane in arrays:
        values = row.get(lane)
        if values is None:
            continue
        if not isinstance(values, list):
            values = [values] if isinstance(values, (str, dict)) else [None]
        for value in values:
            citation = judge_citation(value, lane, cases, sibling_lane, index, homed, owner)
            if row.get("grouping") == "job" and isinstance(value, str):
                citation["reference"] = value
            citations.append(citation)
    return citations


def lanes_not_in_run(citations: List[Dict[str, Any]], cases: List[Dict[str, Any]],
                     index: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """The lanes whose suite the run left out, each ``{lane, citations}``.

    A run is often one suite's results -- the unit tests, with the e2e suite
    written by a command of its own. A lane is out of the run when none of
    its well-formed citations, across the whole map, matched a case, and the
    run holds neither a file nor a test title any of them cites -- nor, for
    a case that records no file (node:test's own reporter), a title that is
    the last part of a cited describe path -- nor a case in the suite of a
    file the lane cites (``_in_cited_folder``). Once one citation of the
    lane matched, or the run holds a file, a title or a folder the lane
    cites, the suite ran, and a citation that matches nothing is stale or
    names the wrong file or title (``never-ran``). So a lane whose every
    cited file was deleted still fails ``--strict`` when its suite ran."""
    by_lane: Dict[str, List[Dict[str, Any]]] = {}
    for c in citations:
        if c["status"] not in ("external", "bad-citation"):
            by_lane.setdefault(c["lane"], []).append(c)
    recorded = [c for c in cases if c["file"]]
    fileless = {t for c in cases if not c["file"] for t in c["titles"]}
    out = []
    for lane, cited in by_lane.items():
        if any(c["status"] != "never-ran" or c["name"] in index or _leaf(c["name"]) in fileless for c in cited):
            continue
        if any(_file_matches(c["file"], case) for c in cited if c["file"] for case in recorded):
            continue
        if any(_in_cited_folder(c["file"], case) for c in cited if c["file"] for case in recorded):
            continue
        out.append({"lane": lane, "citations": len(cited)})
    return out


def _in_cited_folder(cited: str, case: Dict[str, Any]) -> bool:
    """Whether a case the run records a file for is in the suite of a cited
    file. Paths from the project root: the case is in the cited folder or a
    subfolder of it (``e2e/tests/admin/new.spec.ts`` for
    ``e2e/tests/a.spec.ts``). A run file named after a folder of the cited
    path (``e2e.xml``) holds that folder's suite, so two more cases count:

    - a path recorded from a folder before the cited folder, or from the
      cited folder itself, that lands in the cited folder or below it
      (``tests/b.spec.ts``, ``b.spec.ts`` or ``admin/new.spec.ts``, as
      Playwright records a spec from its own testDir). A path whose first
      folder is a folder of the cited path is not read from the cited folder
      itself: ``tests/x.test.ts`` in ``tests.xml`` is not in ``e2e/tests``;
    - a path from the project root that is in the folder the run file is
      named after, or below it (``e2e/smoke/new.spec.ts`` in ``e2e.xml``: a
      sibling folder under the lane root).

    A unit run that records ``tests/x.test.ts`` in ``api.xml`` is not in
    ``e2e/tests``. When the cited folder is on disk (the report runs from
    the project root), a case read from a folder on the cited path, or from
    the project root, counts only when its file is on disk there too, so
    ``tests/harness.test.ts`` in ``bot.xml`` is not in
    ``evals/bot/evals``. The limits: a unit run in a subfolder of the
    cited folder counts (``tests/unit/a.test.ts`` for a lane that cites
    ``tests/login.spec.ts``), and with the cited folder not on disk a run
    file named after a folder of a lane's path is read as that lane's
    suite, so a unit run in ``web.xml`` counts for a lane that cites
    ``packages/web/e2e/a.spec.ts``. Both give a loud ``never-ran``, never a
    false pass."""
    case_file = case["file"]
    if not case_file:
        return False
    cited_dir = os.path.dirname(_norm_path(cited))
    case_dirs = [os.path.dirname(case_file)]
    if case["dotted"]:
        # a dotted classname may carry the test class after the module
        case_dirs.append(os.path.dirname(case_dirs[0]))
    parts = [part for part in cited_dir.split("/") if part]
    lower = [part.lower() for part in parts]
    stem = os.path.splitext(os.path.basename(case.get("source") or ""))[0].lower()
    # When the cited folder is on disk, a case read into it must be on disk
    # too: bot.xml's tests/harness.test.ts is not in
    # evals/bot/evals/ when evals/bot/evals/tests/harness.test.ts is
    # not there.
    on_disk = bool(cited_dir) and os.path.isdir(cited_dir)

    def there(path: str) -> bool:
        return not on_disk or os.path.exists(path)

    for case_dir in case_dirs:
        if case_dir == cited_dir or (cited_dir and case_dir.startswith(cited_dir + "/")):
            return True
        if not stem or stem not in lower:
            continue
        first = case_dir.split("/", 1)[0].lower() if case_dir else ""
        # recorded from a folder `lead`, where the cited folder is lead/tail
        for cut in range(len(parts), -1, -1):
            tail = "/".join(parts[cut:])
            if tail and case_dir != tail and not case_dir.startswith(tail + "/"):
                continue
            if not tail and first in lower:
                continue  # recorded from above the cited folder, not from it
            if stem in lower[:cut] and there("/".join(parts[:cut] + [case_file])):
                return True
        # from the project root, in the folder the run file is named after
        root = "/".join(parts[: lower.index(stem) + 1])
        if (case_dir == root or case_dir.startswith(root + "/")) and there(case_file):
            return True
    return False


def _leaf(name: str) -> str:
    """A test's own title: the last part of a describe path (``b`` in ``a > b``)."""
    return re.split("|".join(re.escape(j) for j in DESCRIBE_JOINERS), name)[-1].strip()


def scenario_evidence(refs: Any, citations: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Resolve explicit links within one altitude's lane. A lane pass cannot fill a gap."""
    if refs is None or refs == []:
        return {"status": "missing-citation", "citations": []}
    if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
        return {"status": "invalid-citation", "citations": []}
    linked = [citations[ref] for ref in dict.fromkeys(refs) if ref in citations]
    unresolved = [ref for ref in dict.fromkeys(refs) if ref not in citations]
    statuses = {citation["status"] for citation in linked}
    if unresolved or "bad-citation" in statuses or any(c.get("ambiguous") for c in linked):
        status = "invalid-citation"
    elif "failing" in statuses:
        status = "failing"
    elif statuses == {"passing"}:
        status = "passing"
    elif statuses == {"external"}:
        status = "external"
    else:
        status = "unchecked"
    return {"status": status, "citations": linked, "unresolved": unresolved}


def judge_row(row: Dict[str, Any], lanes: Dict[str, str], cases: Optional[List[Dict[str, Any]]],
              index: Optional[Dict[str, List[Dict[str, Any]]]] = None,
              homed: Optional[Dict[int, str]] = None,
              citations: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """One row joined to the run: its bucket, scenarios and computed verdict.
    ``citations``, when given, are the row's citations already judged."""
    if citations is None:
        citations = row_citations(row, lanes, cases, index, homed)

    recorded = row.get("verdict")
    result: Dict[str, Any] = {
        "id": row.get("id"),
        "story": row.get("story") or row.get("title") or "",
        "doc": row.get("doc"),
        "recorded": recorded,
        "priority": row.get("priority"),
        "surfaces": row_surfaces(row),
        "citations": citations,
        "scenarios": [],
    }
    for s in row.get("scenarios") or []:
        if not isinstance(s, dict):
            continue
        altitude = s.get("altitude")
        lane = lanes.get(altitude) if isinstance(altitude, str) else None
        in_lane = [c for c in citations if c["lane"] == lane] if lane else []
        if cases is None:
            proven = None
        elif altitude == "sibling":
            proven = bool(in_lane) and all(c["status"] == "external" for c in in_lane)
        else:
            # worst-of: one passing citation proves nothing while another in the same lane is red or unrun
            proven = any(c["status"] == "passing" for c in in_lane) and not any(
                c["status"] in BLOCKING for c in in_lane
            )
        scenario = {
            "id": s.get("id"),
            "then": s.get("then") or "",
            "altitude": altitude,
            "lane": lane,
            "proven": proven,
        }
        if row.get("grouping") == "job":
            references = {c["reference"]: c for c in in_lane if "reference" in c}
            scenario["evidence"] = scenario_evidence(s.get("evidence"), references)
        result["scenarios"].append(scenario)

    if cases is None:
        result["bucket"] = None
        result["computed"] = None
        result["finding"] = None
        return result

    runnable = [c for c in citations if c["status"] != "external"]
    if not citations:
        bucket = "no-test"
    elif not runnable:
        bucket = "external"
    else:
        bucket = min((c["status"] for c in runnable), key=BUCKET_ORDER.index)
    result["bucket"] = bucket

    scen = result["scenarios"]
    anything_passed = any(c["status"] == "passing" for c in citations) or any(s["proven"] for s in scen)
    if scen and all(s["proven"] for s in scen):
        computed = "proven"
    elif anything_passed:
        computed = "under-proven"
    else:
        computed = "not-built"
    result["computed"] = computed

    finding = None
    if recorded is not None and recorded not in VERDICT_RANK:
        finding = "unknown-verdict"
    elif recorded in VERDICT_RANK:
        if VERDICT_RANK[recorded] > VERDICT_RANK[computed]:
            finding = "optimistic"
        elif VERDICT_RANK[recorded] < VERDICT_RANK[computed]:
            finding = "promotable"
    result["finding"] = finding
    return result


def _one_line(value: Any) -> bool:
    return isinstance(value, str) and len(value.strip().splitlines()) == 1


def _real_date(value: Any) -> bool:
    if not isinstance(value, str) or not DATE_RE.match(value):
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def judge_left_out(entries: List[Any], cases: Optional[List[Dict[str, Any]]],
                   index: Optional[Dict[str, List[Dict[str, Any]]]],
                   homed: Optional[Dict[int, str]]) -> List[Dict[str, Any]]:
    """Each ``leftOut`` entry -- a test the team chose to leave with no row.

    An entry names one test: it matches a case only by the case's whole
    title and file (``exact_cases``: no leaf, describe-block or
    parametrised matching), so it can never hide a describe block, a
    pattern of tests or a file. ``matches`` is how many cases it matched
    and ``hides`` how many it keeps from being orphans (more than one only
    for one test run several ways: a pytest parametrised test, a test run
    once per project). It hides nothing, and ``problem`` says why, when
    its test is not ``<file>::<name>``, its reason is not one line, its
    date is not a real ``YYYY-MM-DD`` date, its name is an unfilled
    ``<placeholder>``, the run cannot place the test (``places``), or a
    row cites the test too. ``ran`` is whether it matched a case (null
    with no run); a well-formed entry that matched none is stale: the test
    is gone or renamed, so the note about it is too. Rows are judged
    first, so ``homed`` already holds every case a row cites."""
    row_homed = dict(homed) if homed is not None else {}
    out = []
    for entry in entries:
        test = entry.get("test") if isinstance(entry, dict) else None
        reason = entry.get("reason") if isinstance(entry, dict) else None
        date = entry.get("date") if isinstance(entry, dict) else None
        file, name = split_citation(test) if isinstance(test, str) and "::" in test else ("", "")
        problem = None
        if not file or not name:
            problem = "the test is not <file>::<name>"
        elif not _one_line(reason):
            problem = "no one-line reason"
        elif not _real_date(date):
            problem = "no real YYYY-MM-DD date"
        judged: Dict[str, Any] = {
            "test": test if isinstance(test, str) else None,
            "reason": reason if isinstance(reason, str) else None,
            "date": date if isinstance(date, str) else None,
            "status": "not-run" if cases is None else "never-ran",
            "ran": None,
            "problem": problem,
        }
        out.append(judged)
        if not file or not name:
            judged["status"] = "bad-citation"
            if cases is not None:
                judged.update(ran=False, matches=0, hides=0)
            continue
        if cases is None:
            continue
        matched = exact_cases(file, name, cases, index)
        if not matched and (PLACEHOLDER_RE.search(name) or PLACEHOLDER_RE.search(file)):
            judged.update(status="bad-citation", ran=False, matches=0, hides=0,
                          problem=problem or "an unfilled <placeholder>")
            continue
        meant, places = narrow(file, matched)
        if places > 1:
            judged["places"] = places
            problem = problem or f"matches tests in {places} places the run cannot tell apart"
        else:
            matched = meant
        cited = sorted({row_homed[c["index"]] for c in matched if c["index"] in row_homed})
        if cited:
            problem = problem or f"also cited by {', '.join(cited)}"
        hides = 0
        if problem is None and homed is not None:
            for c in matched:
                homed.setdefault(c["index"], "leftOut")
            hides = len(matched)
        judged.update(
            status=min((c["outcome"] for c in matched), key=BUCKET_ORDER.index) if matched else "never-ran",
            ran=bool(matched), matches=len(matched), hides=hides, problem=problem,
        )
    return out


def has_doc(row: Dict[str, Any]) -> bool:
    """True when the row names an outcome doc: a row with none records what
    the code does today and is not a promise yet."""
    doc = row.get("doc")
    return isinstance(doc, str) and bool(doc.strip())


def find_orphans(cases: List[Dict[str, Any]], homed: Dict[int, str]) -> List[Dict[str, Any]]:
    """Every case in the run that no row's citation matched, in run order.

    ``file`` is the file the run records for the case, or null when it
    records none or only a dotted pytest classname (a module path, not a
    file); the classname is kept either way."""
    return [
        {
            "file": None if c["dotted"] else c["file"],
            "name": c["name"],
            "classname": c["classname"],
            "status": c["outcome"],
        }
        for c in cases
        if c["index"] not in homed
    ]


def orphan_label(orphan: Dict[str, Any]) -> str:
    """``file::name``, with the classname standing in when the run records no file."""
    where = orphan["file"] or orphan["classname"]
    return f"{where}::{orphan['name']}" if where else orphan["name"]


def summarise(rows: List[Dict[str, Any]], ran: bool) -> Dict[str, Any]:
    summary: Dict[str, Any] = {"rows": len(rows)}
    summary["rowsWithoutDoc"] = sum(1 for r in rows if not has_doc(r))
    if not ran:
        summary["recorded"] = {v: sum(1 for r in rows if r["recorded"] == v) for v in VERDICT_RANK}
        return summary
    summary["buckets"] = {b: sum(1 for r in rows if r["bucket"] == b) for b in BUCKET_ORDER + ("external", "no-test")}
    summary["verdicts"] = {v: sum(1 for r in rows if r["computed"] == v) for v in ("proven", "under-proven", "not-built")}
    summary["passingButUnderProven"] = sum(1 for r in rows if r["bucket"] == "passing" and r["computed"] == "under-proven")
    summary["optimistic"] = sum(1 for r in rows if r["finding"] == "optimistic")
    if any(r.get("priority") for r in rows):
        must = [r for r in rows if r.get("priority") == "must"]
        summary["must"] = len(must)
        summary["mustNotProven"] = sum(1 for r in must if r["computed"] != "proven")
    summary["promotable"] = sum(1 for r in rows if r["finding"] == "promotable")
    return summary


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

MARK = {"passing": "✓", "failing": "✗", "skipped": "–", "never-ran": "?", "bad-citation": "!", "external": "↗", "not-run": "·"}
# The computed verdict joins citations by lane, not by scenario: "every lane green" is
# the most it can say, never "proven" (that needs a test asserting each scenario's own
# Then, watched failing: reconcile). The JSON keeps the value names check.py compares.
VERDICT_MARK = {"proven": "LANE-GREEN", "under-proven": "UNDER-PROVEN", "not-built": "not built"}
COMPUTED_LABEL = {"proven": "lane-green"}


def _clip(text: str, width: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[: width - 1] + "…"


# A section the report prints after the rows: a title, and its entries as
# (tree line, Markdown line).
Section = Tuple[str, List[Tuple[str, str]]]


def orphan_section(orphans: List[Dict[str, Any]]) -> Section:
    entries = [
        (f"{MARK.get(o['status'], '?')} {orphan_label(o)}  {o['status']}", f"`{orphan_label(o)}` — {o['status']}")
        for o in orphans
    ]
    return f"Tests with no row ({len(orphans)})", entries


def left_out_section(left_out: List[Dict[str, Any]]) -> Section:
    entries = []
    for e in left_out:
        status = "never ran (stale)" if e["status"] == "never-ran" else e["status"]
        if e.get("hides", 0) > 1:
            status += f", hides {e['hides']} cases"
        note = f" — {e['reason']}" + (f" ({e['date']})" if e["date"] else "") if e["reason"] else ""
        if e["problem"]:
            note += f" [hides nothing: {e['problem']}]"
        test = e["test"] or "(no test)"
        entries.append((f"{MARK.get(e['status'], '?')} {test}  {status}{note}", f"`{test}` — {status}{note}"))
    return f"Left out ({len(left_out)})", entries


def skipped_citations(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Each citation the run skipped, as ``{id, lane, test}``: a skipped test
    proves nothing, and ``--strict`` alone passes a row whose recorded verdict
    already sits at or below what the rest of its citations show."""
    out = []
    for r in rows:
        for c in r["citations"]:
            if c["status"] == "skipped":
                test = f"{c['file']}::{c['name']}" if c.get("file") else str(c.get("name") or "")
                out.append({"id": r["id"], "lane": c["lane"], "test": test})
    return out


def skipped_section(skipped: List[Dict[str, Any]]) -> Section:
    entries = [(f"{MARK['skipped']} {e['id']}  {e['test']}  ({e['lane']})", f"{e['id']}: `{e['test']}` ({e['lane']})")
               for e in skipped]
    return f"Cited tests that were skipped ({len(skipped)})", entries


def unmapped_section(unmapped: List[str]) -> Section:
    return f"Entry points with no row ({len(unmapped)})", [(s, f"`{s}`") for s in unmapped]


def stale_section(stale: List[Dict[str, Any]]) -> Section:
    entries = [(f"{e['id']}  {e['surface']}", f"{e['id']}: `{e['surface']}`") for e in stale]
    return f"Row surfaces not in the entry-point list ({len(stale)})", entries


def format_tree(rows: List[Dict[str, Any]], summary: Dict[str, Any], ran: bool,
                sections: Optional[List[Section]] = None) -> str:
    out: List[str] = []
    for r in rows:
        if ran:
            status = VERDICT_MARK[r["computed"]]
            if r["finding"] == "optimistic":
                status += f"  (map says {r['recorded']})"
            elif r["finding"] == "promotable":
                status += f"  (map says {r['recorded']}; promote with reconcile)"
            head = f"{r['id']}  {_clip(r['story'], 60):<60}  {r['bucket']:<12} {status}"
        else:
            head = f"{r['id']}  {_clip(r['story'], 60):<60}  map says {r['recorded']}"
        out.append(head)
        if r.get("doc"):
            out.append(f"  why: {r['doc']}")
        if r.get("surfaces"):
            out.append(f"  enters: {' · '.join(r['surfaces'])}")
        passing_in = {}
        for c in r["citations"]:
            if c["status"] in ("passing", "external"):
                passing_in[c["lane"]] = passing_in.get(c["lane"], 0) + 1
        sharing = {}
        for s in r["scenarios"]:
            sharing[s["lane"]] = sharing.get(s["lane"], 0) + 1
        for s in r["scenarios"]:
            if s["proven"] is None:
                tick = ""
            elif not s["proven"]:
                tick = "  ✗ no passing test in its lane"
            elif passing_in.get(s["lane"], 0) < sharing.get(s["lane"], 0):
                tick = "  ✓ lane green, but its lane has fewer passing tests than scenarios: check one asserts this Then"
            else:
                tick = "  ✓ lane green"
            evidence = s.get("evidence")
            if evidence is not None:
                tick += f" · explicit evidence: {evidence['status']}"
            out.append(f"  ├─ {s['id']}  {_clip(s['then'], 52)}  [{s['altitude']} → {s['lane']}]{tick}")
            if evidence is not None:
                for c in evidence["citations"]:
                    out.append(f"  │    {c['reference']}  {c['status']}")
                for ref in evidence.get("unresolved", []):
                    out.append(f"  │    {ref}  not cited in this lane")
        for c in r["citations"]:
            out.append(f"  │    {MARK.get(c['status'], '?')} {c['lane']:<12} {_clip(c['file'], 44)} › {_clip(c['name'], 48)}  {c['status']}")
        if not r["citations"]:
            out.append("  │    (no test cited)")
        out.append("")
    for title, entries in sections or []:
        out.append(title)
        out.extend(f"  {tree}" for tree, _md in entries)
        out.append("")
    out.append("─" * 78)
    out.append(summary_line(summary, ran))
    return "\n".join(out)


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def homes_line(summary: Dict[str, Any]) -> str:
    """What has no home: tests in the run no row cites, entry points no row
    lists (and row surfaces the code no longer lists), and rows no outcome
    doc promises. Empty when everything has one."""
    parts = []
    if summary.get("orphanCount"):
        parts.append(_count(summary["orphanCount"], "test has no row", "tests have no row"))
    if summary.get("staleLeftOutCount"):
        parts.append(_count(summary["staleLeftOutCount"], "left-out test is not in the run", "left-out tests are not in the run"))
    if summary.get("failingLeftOutCount"):
        parts.append(_count(summary["failingLeftOutCount"], "left-out test fails", "left-out tests fail"))
    if summary.get("leftOutProblemCount"):
        parts.append(_count(summary["leftOutProblemCount"], "left-out entry has a problem", "left-out entries have a problem"))
    if summary.get("unmappedSurfaceCount"):
        parts.append(_count(summary["unmappedSurfaceCount"], "entry point has no row", "entry points have no row"))
    if summary.get("staleSurfaceCount"):
        parts.append(_count(summary["staleSurfaceCount"], "row surface is not in the entry-point list",
                            "row surfaces are not in the entry-point list"))
    if summary.get("rowsWithoutDoc"):
        parts.append(_count(summary["rowsWithoutDoc"], "row has no outcome doc", "rows have no outcome doc"))
    return " · ".join(parts)


def summary_line(summary: Dict[str, Any], ran: bool) -> str:
    n = summary["rows"]
    homes = homes_line(summary)
    if not ran:
        rec = summary["recorded"]
        line = f"{n} promises · recorded: {rec['proven']} proven · {rec['under-proven']} under-proven · {rec['not-built']} not built (no test run joined)"
        return line + ("\n" + homes if homes else "")
    b, v = summary["buckets"], summary["verdicts"]
    lead = ""
    if "mustNotProven" in summary:
        lead = f"{summary['mustNotProven']} of {summary['must']} must rows not lane-green · "
    line = lead + (
        f"{n} promises · {b['passing']} passing in this run · {v['proven']} lane-green · "
        f"{v['under-proven']} under-proven · {v['not-built']} not built"
    )
    extra = []
    if summary["passingButUnderProven"]:
        extra.append(_count(summary["passingButUnderProven"], "is green but not proven", "are green but not proven")
                     + " at the altitude promised")
    if b["failing"]:
        extra.append(f"{b['failing']} failing")
    if b["never-ran"]:
        extra.append(_count(b["never-ran"], "cites a test that never ran", "cite tests that never ran"))
    for lane in summary.get("lanesNotInRun") or []:
        extra.append(f"{lane['lane']} was not in this run ("
                     + _count(lane["citations"], "citation", "citations") + " not checked)")
    if summary["optimistic"]:
        extra.append(_count(summary["optimistic"], "is recorded higher than the run shows", "are recorded higher than the run shows"))
    return line + ("\n" + " · ".join(extra) if extra else "") + ("\n" + homes if homes else "")


def format_markdown(rows: List[Dict[str, Any]], summary: Dict[str, Any], ran: bool,
                    sections: Optional[List[Section]] = None) -> str:
    out = ["# Capability map — proof report", "", "**" + summary_line(summary, ran).replace("\n", "**  \n**") + "**", ""]
    if ran:
        run = summary["run"]
        out += [f"Run: {run['cases']} test cases ({run['passing']} passed, {run['failing']} failed, "
                f"{run['skipped']} skipped) from {len(run['files'])} file(s). Fingerprint `{summary['fingerprint']}`.", ""]
    if ran:
        out += ["| Row | Promise | Bucket | Verdict (this run) | Map says | Tests |", "|---|---|---|---|---|---:|"]
        for r in rows:
            flag = " ⚠" if r["finding"] == "optimistic" else ""
            out.append(
                f"| {r['id']} | {_clip(r['story'], 70)} | {r['bucket']} | {COMPUTED_LABEL.get(r['computed'], r['computed'])}{flag} | {r['recorded']} | {len(r['citations'])} |"
            )
    else:
        out += ["| Row | Promise | Map says | Tests |", "|---|---|---|---:|"]
        for r in rows:
            out.append(f"| {r['id']} | {_clip(r['story'], 70)} | {r['recorded']} | {len(r['citations'])} |")
    out += ["", "```", format_tree(rows, summary, ran), "```", ""]
    for title, entries in sections or []:
        out += [f"## {title}", ""]
        out += [f"- {md}" for _tree, md in entries] or ["None."]
        out.append("")
    return "\n".join(out)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="map_report.py",
        description="Join the capability map to a JUnit test run: what is promised, and what is proven.",
    )
    parser.add_argument("--map", required=True, help="the map.json to read")
    parser.add_argument("--row", action="append", help="report selected capabilities only (repeatable); label the limited scope")
    parser.add_argument("--junit", action="append", default=[], help="a JUnit XML file or a folder of them (repeatable)")
    parser.add_argument("--config", default=None, help="promise config whose map.lanes picks each altitude's lane")
    parser.add_argument("--format", choices=("tree", "markdown"), default="tree")
    parser.add_argument("--json", action="store_true", help="print JSON instead")
    parser.add_argument("--strict", action="store_true",
                        help="fail on bad run evidence, an optimistic verdict, or missing/invalid explicit scenario citations")
    parser.add_argument("--orphans", action="store_true", help="also list every test in the run that no row cites (needs --junit)")
    parser.add_argument("--fail-on-orphans", action="store_true",
                        help="exit 1 when any test in the run has no row, or a leftOut entry is stale, failing "
                             "or has a problem (needs --junit)")
    parser.add_argument("--fail-on-skipped", action="store_true",
                        help="exit 1 when the run skipped a test a row cites, and list each one (needs --junit)")
    parser.add_argument("--surfaces", default=None, metavar="FILE",
                        help="the code's entry points, one per line ('-' for stdin): report each one no row lists")
    parser.add_argument("--fail-on-unmapped", action="store_true", help="exit 1 when an entry point has no row (needs --surfaces)")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    if (args.orphans or args.fail_on_orphans) and not args.junit:
        flag = "--orphans" if args.orphans else "--fail-on-orphans"
        print(f"map_report.py: {flag} needs --junit: a test with no row is a case in a run", file=sys.stderr)
        return 2
    if args.fail_on_skipped and not args.junit:
        print("map_report.py: --fail-on-skipped needs --junit: a skipped test is a case in a run", file=sys.stderr)
        return 2
    if args.fail_on_unmapped and args.surfaces is None:
        print("map_report.py: --fail-on-unmapped needs --surfaces: the list of the code's entry points", file=sys.stderr)
        return 2
    try:
        rows, left_out_entries, map_digest = load_map(args.map)
        lanes = load_lanes(args.config)
        cases, run_files = load_run(args.junit) if args.junit else (None, [])
        surfaces, surfaces_text = load_surfaces(args.surfaces) if args.surfaces is not None else (None, None)
        if args.row:
            selected = set(args.row)
            ids = [r.get("id") for r in rows]
            if not all(isinstance(rid, str) and rid for rid in ids) or len(set(ids)) != len(ids):
                raise UsageError("pilot selection needs map rows with unique non-empty ids")
            known = set(ids)
            if selected - known:
                raise UsageError("row selection names an unknown capability: " + ", ".join(sorted(selected - known)))
    except UsageError as exc:
        print(f"map_report.py: {exc}", file=sys.stderr)
        return 2

    ran = cases is not None
    index = build_index(cases) if cases is not None else None
    out_of_scope_left_out = 0
    if args.row and cases is not None:
        run_files_by_kind = {(c["file"], c["dotted"]) for c in cases}
        run_file_cases = [{"file": file, "dotted": dotted} for file, dotted in run_files_by_kind]
        relevant_left_out = []
        shapes = judge_left_out(left_out_entries, None, None, None)
        for entry, shape in zip(left_out_entries, shapes):
            file, name = split_citation(entry.get("test") if isinstance(entry, dict) else None)
            malformed = shape["problem"] or PLACEHOLDER_RE.search(file) or PLACEHOLDER_RE.search(name)
            if malformed or not file or not name or any(_file_matches(file, c) for c in run_file_cases):
                relevant_left_out.append(entry)
            else:
                out_of_scope_left_out += 1
        left_out_entries = relevant_left_out
    homed: Optional[Dict[int, str]] = {} if ran else None
    cited = [row_citations(r, lanes, cases, index, homed) for r in rows]
    not_in_run = lanes_not_in_run([c for cs in cited for c in cs], cases, index or {}) if cases is not None else []
    absent = {e["lane"] for e in not_in_run}
    for c in (c for cs in cited for c in cs):
        if c["lane"] in absent and c["status"] == "never-ran":
            c["status"] = "not-run"
    all_judged = [judge_row(r, lanes, cases, citations=cs) for r, cs in zip(rows, cited)]
    judged = [r for r in all_judged if r["id"] in selected] if args.row else all_judged
    if args.row:
        selected_lane_counts = {}
        for r in judged:
            for citation in r["citations"]:
                if citation["status"] in ("bad-citation", "external"):
                    continue
                lane = citation["lane"]
                selected_lane_counts[lane] = selected_lane_counts.get(lane, 0) + 1
        not_in_run = [{**entry, "citations": selected_lane_counts[entry["lane"]]}
                      for entry in not_in_run if selected_lane_counts.get(entry["lane"])]
    left_out = judge_left_out(left_out_entries, cases, index, homed)
    summary = summarise(judged, ran)
    summary["leftOutCount"] = len(left_out)
    summary["leftOutProblemCount"] = sum(1 for e in left_out if e["problem"])
    if args.row:
        summary["leftOutOutOfScopeCount"] = out_of_scope_left_out
    orphans: Optional[List[Dict[str, Any]]] = None
    skipped: Optional[List[Dict[str, Any]]] = None
    sections: List[Section] = []
    if ran:
        summary["run"] = {
            "files": run_files,
            "cases": len(cases),
            "passing": sum(1 for c in cases if c["outcome"] == "passing"),
            "failing": sum(1 for c in cases if c["outcome"] == "failing"),
            "skipped": sum(1 for c in cases if c["outcome"] == "skipped"),
        }
        summary["lanesNotInRun"] = not_in_run
        skipped = skipped_citations(all_judged if args.row else judged)
        summary["skippedCitationCount"] = len(skipped)
        if args.fail_on_skipped:
            sections.append(skipped_section(skipped))
        orphans = find_orphans(cases, homed or {})
        summary["orphanCount"] = len(orphans)
        summary["staleLeftOutCount"] = sum(1 for e in left_out if e["status"] == "never-ran")
        summary["failingLeftOutCount"] = sum(1 for e in left_out if e["status"] == "failing")
        if args.orphans:
            sections.append(orphan_section(orphans))
            if left_out:
                sections.append(left_out_section(left_out))
    unmapped: Optional[List[str]] = None
    stale: Optional[List[Dict[str, Any]]] = None
    if surfaces is not None:
        unmapped, stale = join_surfaces(all_judged, surfaces)
        if args.row:
            stale = [entry for entry in stale if entry["id"] in selected]
        summary["surfaces"] = len(surfaces)
        summary["unmappedSurfaceCount"] = len(unmapped)
        summary["staleSurfaceCount"] = len(stale)
        sections.append(unmapped_section(unmapped))
        if stale:
            sections.append(stale_section(stale))
    extra = json.dumps({"rows": sorted(set(args.row)), "surfaces": surfaces_text}) if args.row else surfaces_text
    summary["fingerprint"] = fingerprint([args.map] + ([args.config] if args.config else []) + run_files, extra)
    supporting_rows = []
    if args.row:
        supplied_surfaces = set(surfaces or [])
        supporting_rows = sorted({
            r["id"] for r in all_judged
            if isinstance(r["id"], str) and r["id"] not in selected
            and (any(c.get("matches", 0) for c in r["citations"])
                 or set(r["surfaces"]) & supplied_surfaces)
        })
    if args.json:
        payload: Dict[str, Any] = {"mapDigest": map_digest, "summary": summary, "lanes": lanes, "rows": judged, "leftOut": left_out}
        if args.row:
            payload["scope"] = {"rows": sorted(set(args.row)),
                                "note": "Selected capabilities only; coverage outside the supplied run and surfaces is not assessed."}
            payload["scope"]["supportingRows"] = supporting_rows
        if orphans is not None:
            payload["orphans"] = orphans
        if skipped is not None:
            payload["skippedCitations"] = skipped
        if surfaces is not None:
            payload["unmappedSurfaces"] = unmapped
            payload["staleSurfaces"] = stale
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif args.format == "markdown":
        if args.row:
            print("> Selected capabilities only. Coverage outside the supplied run and surfaces is not assessed.\n")
            if supporting_rows:
                print("> Other map capabilities covering supplied inputs: " + ", ".join(supporting_rows) + "\n")
        print(format_markdown(judged, summary, ran, sections))
    else:
        if args.row:
            print("Selected capabilities only. Coverage outside the supplied run and surfaces is not assessed.")
            if supporting_rows:
                print("Other map capabilities covering supplied inputs: " + ", ".join(supporting_rows))
        print(format_tree(judged, summary, ran, sections))
    gate = ("failing", "bad-citation", "never-ran")
    if args.strict and args.row and cases is not None and any(c["outcome"] == "failing" for c in cases):
        print("map_report.py: supplied pilot run contains failing tests; inspect the run summary", file=sys.stderr)
        return 1
    if args.strict and any(
        s.get("evidence", {}).get("status") in ("missing-citation", "invalid-citation")
        for r in judged for s in r["scenarios"]
    ):
        return 1
    if args.strict and ran and any(r["bucket"] in gate or r["finding"] in ("optimistic", "unknown-verdict") for r in judged):
        return 1
    left_out_gate = any(e["problem"] or e["status"] in ("never-ran", "failing") for e in left_out)
    if args.fail_on_orphans and (orphans or left_out_gate):
        return 1
    if args.fail_on_unmapped and unmapped:
        return 1
    if args.fail_on_skipped and skipped:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
