#!/usr/bin/env python3
"""Shape checks for one outcome doc, or every outcome doc in a directory.

    python3 lint_outcome.py doc.md
    python3 lint_outcome.py docs/designs --json
    python3 lint_outcome.py doc.md --strict
    python3 lint_outcome.py doc.md --template

Checks the rules in references/architecture.md §9 against the Outcome
Framework template shape: §0 TLDR budget and non-empty fields, rule
bullet format and tags (and that ``**Rules:**`` holds at least one rule,
rule id RULES_PRESENT), headings, the §6 acceptance table (rule id
ACCEPTANCE_TABLE: a qualifying header, at least one data row, non-empty
Given/When/Then cells, and every row bounded by a leading and a trailing
pipe -- a row missing one is still read, GFM-style, and reported at its
own line rather than dropped with every row below it; a pipe written
``\\|`` is cell text, and any other pipe splits the cell, in a `code span`
too, as GitHub renders it), the §6 Altitude
column (rule id ACCEPTANCE_ALTITUDE: every cell is one of ``data``,
``response``, ``perception``, ``judgement``, ``sibling``; and, as a
warning, ALTITUDE_MISSING when a table has no ``Altitude`` header), the
Why lines (rule id WHY_LINE: present in §4-§7, each with a value), and
placeholder text (rule id PLACEHOLDER: TBD/TODO/etc markers plus any
angle-bracket ``<...>`` run in §0, in the header ``Owner:``/``Last
decision:`` values, in a §6 data cell, in an agent note, on a §3
example's first line, in a §9 owner, or in a Why line's value -- outside
a `code span`, where ``<id>`` is a command's argument), and
status authority (rule id BUILDING_NEEDS_GATE: a ``building`` doc's
header carries no red-gate commit sha; rule id SHIPPED_NEEDS_GATE: a
``shipped`` doc has a §6 line that no red run and no ``Kill:`` line covers
and that has no ``Row``, the one part of "or it cites a proven backfilled
row" the lint can see), the kill record under §6 (rule id
KILL_RECORD_FORMAT: a ``Filed without red run:`` or ``Kill:`` line out of
shape, or a second Filed line; rule id KILL_RECORD_UNKNOWN: either names an
AT id that is not a §6 line), and the thin draft (rule id
THIN_DRAFT: a ``Depth:`` header line must read ``Depth: thin`` and sits
only on a ``draft`` doc, where §3-§7 each hold a line that is just the
not-written-yet marker and §4-§7 hold nothing else), and the decision
policy (rule id DECISION_POLICY: a ``Decision policy:`` header line reads
``fast``, ``auto`` or ``spec``; ``prototype`` is read as ``fast`` and warned as
DECISION_POLICY_ALIAS; a doc with none behaves as ``spec``)
with the agent decisions it allows in §8 (rows whose Owner is ``agent``:
AGENT_DECISION_FIELDS, the structured fields and a concrete review
trigger; AGENT_DECISION_PROTECTED, a provisional row in a protected
category; AGENT_DECISION_UNRATIFIED, a provisional row under ``spec``;
and, as a warning, AGENT_DECISION_WORDS, a local row whose words name a
protected category), a §5 Load-bearing premises table (rule id
PREMISE_TABLE: a data row with an empty Evidence or Existing join searched
cell, or a header naming neither), and, as a warning, an unlisted negative
claim in §1 or §5 outside that table (rule id PREMISE_PHRASE: "can't"/"cannot",
"doesn't have"/"does not have", "no way to", "unavailable", "only X has" --
cleared by a COMPLETE row whose Premise cell overlaps the claim literally
after normalization, or by an ``<!-- not a premise -->`` comment on the
same line). A thin draft holds the human half only, so on
one the lint does not require the §6 table or the §4-§7 Why lines,
counts a §3 with no parseable example as zero, and reports an empty
**Rules:** block as a warning, not an error. ``--template`` exempts
angle-bracket placeholders and the literal ``YYYY-MM-DD`` so the bundled
template itself can be linted; every other rule stays active under it.
Lines inside a fenced code block (``` or ~~~) are illustrations: no
heading, field marker, table row or placeholder inside one counts,
though the lines still count toward a line budget; a fence that is
opened and never closed is its own finding (rule id FENCE_UNCLOSED, at
the opening line), since every line after it would otherwise vanish
from the scan with nothing naming the cause. A path that cannot be
read as UTF-8 text reports one UNREADABLE finding for itself instead
of raising.
Exit 0 when there is no error finding (a warning on its own exits 0), 1
when there is an error finding (a warning too under --strict, which
promotes every warning to an error), 2 on a usage error. Human output is
one line per finding: ``<path>:<line>: <RULE_ID> <message>``. ``--json``
prints one JSON object for a single file, or a JSON array of one such
object per file when a directory was given. Deterministic; no network.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Pattern, Tuple, Union

TLDR_HEADING = "## 0. TLDR"
AGENT_NOTES_PREFIX = "Agent notes"

SECTION_NAMES = {
    0: "TLDR",
    1: "Problem",
    2: "Outcome",
    3: "Worked examples",
    4: "Invariants",
    5: "Mechanism",
    6: "Acceptance",
    7: "Build phases",
    8: "Decisions",
    9: "Open questions",
    10: "Out of scope",
}

CONTENTS_ANCHORS = [
    "#0-tldr", "#1-problem", "#2-outcome", "#3-worked-examples", "#4-invariants",
    "#5-mechanism", "#6-acceptance", "#7-build-phases", "#8-decisions",
    "#9-open-questions", "#10-out-of-scope",
]

VALID_STATUS_TOKENS = {"draft", "agreed", "building", "shipped", "superseded-by"}

WHY_SECTIONS = (4, 5, 6, 7)

PLACEHOLDER_TERMS = ("tbd", "todo", "<fill", "decide later")
TEMPLATE_DATE_PLACEHOLDER = "YYYY-MM-DD"

# The five altitudes of references/altitude.md -- what a §6 row's Then
# asserts on. Matched exactly (after trimming), never case-folded.
ALTITUDES = ("data", "response", "perception", "judgement", "sibling")

FENCE_RE = re.compile(r"^\s*(```|~~~)")
HEADING_RE = re.compile(r"^## (\d+)\.\s*(.*?)\s*$")
ANY_HEADING_RE = re.compile(r"^## \d+\.")
STATUS_RE = re.compile(r"^Status:\s*(\S+)")
DEPTH_RE = re.compile(r"^Depth:\s*(\S*)")
BULLET_START_RE = re.compile(r"^-\s+(.*)$")
NUMBERED_START_RE = re.compile(r"^(\d+)\.\s+(.*)$")
TAG_RE = re.compile(r"→\s*(UNTESTED|AT-\d+(?:\s*,\s*AT-\d+)*)\s*$")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")
AT_ID_RE = re.compile(r"^AT-\d+$")
WHY_LINE_RE = re.compile(r"^Why\s*[-—]\s*what breaks without it:(.*)$")
SCENARIOS_RE = re.compile(
    r"\*\*Scenarios:\*\*\s*(\d+)\s*acceptance rows[^,]*,\s*(\d+)\s*worked examples?"
)
# The count-free form: nothing typed, so nothing for two branches to change at once.
SCENARIOS_FREE_LINE = "**Scenarios:** the acceptance rows in §6 and the worked examples in §3."
SCENARIOS_FREE_RE = re.compile(r"\*\*Scenarios:\*\*\s*the acceptance rows in §6\b")
NOTE_START_RE = re.compile(r"^(\d+)\.\s+")
H3_RE = re.compile(r"^###\s+\S")
BOLD_LED_RE = re.compile(r"^\*\*[^*]+\*\*")
BOLD_FIELD_RE = re.compile(r"^\s*\*\*[^*]+:\*\*")
ANGLE_PLACEHOLDER_RE = re.compile(r"<[^<>]+>")
OPEN_QUESTION_OWNER_RE = re.compile(r"^Q\w*\s*[-—]\s*owner:\s*(<[^<>]+>)")
RED_GATE_LINE_RE = re.compile(
    r"^Red gate:\s+([0-9a-fA-F]{7,40})\s+(\d{4}-\d{2}-\d{2})\s*$"
)
# The kill record under the §6 table (outcome-framework.md § Lifecycle): arm's
# one line naming the §6 lines it filed without a red run, and reconcile's one
# line per kill it watched.
FILED_PREFIX = "Filed without red run:"
KILL_PREFIX = "Kill:"
FILED_LINE_RE = re.compile(
    r"^Filed without red run:\s+(AT-\d+(?:\s*,\s*AT-\d+)*)\s+[—-]+\s+(\S.*?)\s*$"
)
KILL_LINE_RE = re.compile(
    r"^Kill:\s+(AT-\d+)\s+[—-]+\s+(\S.*?)\s+(?:→|->)\s+(\S.*?)\s+failed;\s+restored,\s+"
    r"passing at\s+([0-9a-fA-F]{7,40})\s+on\s+(\d{4}-\d{2}-\d{2})\.?\s*$"
)
AT_ID_ANYWHERE_RE = re.compile(r"\bAT-\d+\b")
# A record line is recognised through decoration a renderer or a hand may add (a list
# dash, a quote, emphasis, backticks, an HTML comment) and in any case, so a decorated
# line is never silently skipped: a Filed line always takes coverage away, and a Kill
# line gives coverage only in its exact shape (kill_record).
RECORD_DECORATION_RE = re.compile(r"^(?:\s|[`*_>\-]|<!--)*")
FILED_WORDS_RE = re.compile(r"^filed\s+without\s+red[\s-]+run\b", re.IGNORECASE)
KILL_WORDS_RE = re.compile(r"^kill\s*[`*_]*\s*:", re.IGNORECASE)
RED_RUN_WORDS_RE = re.compile(r"^red\s+run\s*[`*_]*\s*:", re.IGNORECASE)

RULES_MARKER = "**Rules:**"
# The How-we'll-know marker as a person sees it, plus the curly-apostrophe
# spelling (U+2019) a word processor substitutes -- both are the same
# field, so neither is reported as missing.
HOW_WE_KNOW_MARKER = "**How we'll know:**"
HOW_WE_KNOW_RE = re.compile(r"\*\*How we['’]ll know:\*\*")

Marker = Union[str, Pattern[str]]


def read_text_tolerant(path: str) -> str:
    """Read a text file as UTF-8, tolerating a BOM and CRLF line endings."""
    with open(path, "r", encoding="utf-8-sig", newline=None) as fh:
        return fh.read()


def find_line_index(lines: List[str], predicate, start: int = 0) -> Optional[int]:
    """0-indexed position of the first line (from start) matching predicate, or None."""
    for i in range(start, len(lines)):
        if predicate(lines[i]):
            return i
    return None


def unfenced(lines: List[str]) -> List[str]:
    """A copy of ``lines`` with every line inside a fenced code block (and the
    fence lines themselves) replaced by "", so indices stay aligned with the
    original while no heading, marker, table row or placeholder inside a
    fence can match a structural scan. A fence opens and closes on any line
    starting with ``` or ~~~ (the same rule framework_section.py uses)."""
    out: List[str] = []
    in_fence = False
    for line in lines:
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return out


def finding(rule: str, line: Optional[int], message: str, severity: str) -> Dict[str, Any]:
    return {"rule": rule, "line": line, "message": message, "severity": severity}


def _marker_span(line: str, marker: Marker) -> Optional[Tuple[int, int]]:
    """(start, end) of ``marker`` -- a literal or a compiled pattern -- on
    ``line``, or None when it is not there."""
    if isinstance(marker, str):
        pos = line.find(marker)
        return (pos, pos + len(marker)) if pos != -1 else None
    m = marker.search(line)
    return (m.start(), m.end()) if m else None


# ---------------------------------------------------------------------------
# Shared structural lookups (also used by outcome_rows.py and bridge_validate.py)
# ---------------------------------------------------------------------------


def _heading_number(line: str) -> Optional[str]:
    m = HEADING_RE.match(line)
    return m.group(1) if m else None


def section_bounds(lines: List[str], n: int) -> Optional[Tuple[int, int]]:
    """0-indexed [start, end) line range for ``## n. ...`` through the next heading.

    Headings inside a fenced code block are illustrations, not sections."""
    scan = unfenced(lines)
    start = find_line_index(scan, lambda l: _heading_number(l) == str(n))
    if start is None:
        return None
    end = find_line_index(scan, lambda l: ANY_HEADING_RE.match(l) is not None, start=start + 1)
    return start, end if end is not None else len(lines)


def tldr_block_bounds(lines: List[str]) -> Optional[Tuple[int, int]]:
    """0-indexed [start, end) for §0: the heading line up to (not incl.) Agent notes / §1."""
    scan = unfenced(lines)
    start = find_line_index(scan, lambda l: l.startswith(TLDR_HEADING))
    if start is None:
        return None
    end = find_line_index(scan, lambda l: l.startswith(AGENT_NOTES_PREFIX), start=start + 1)
    if end is None:
        end = find_line_index(scan, lambda l: l.startswith("## 1."), start=start + 1)
    if end is None:
        end = len(lines)
    return start, end


def get_status(lines: List[str]) -> Optional[str]:
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: STATUS_RE.match(l) is not None)
    if idx is None:
        return None
    return STATUS_RE.match(scan[idx]).group(1)


def get_depth(lines: List[str]) -> Optional[str]:
    """The ``Depth:`` header token ("" when the line is bare), or None when
    there is no such line."""
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: DEPTH_RE.match(l) is not None)
    if idx is None:
        return None
    return DEPTH_RE.match(scan[idx]).group(1)


def is_thin(lines: List[str]) -> bool:
    """True for a thin draft: ``Depth: thin`` on a ``draft`` doc. A
    ``Depth: thin`` line on any other status is THIN_DRAFT's error, and the
    doc is then held to the full shape."""
    return get_depth(lines) == "thin" and get_status(lines) == "draft"


def parse_header_field_value(
    lines: List[str], idx: int, marker: str, other_marker: Optional[str] = None
) -> str:
    """The text on ``lines[idx]`` after ``marker``.

    Stops before ``other_marker`` when it also appears later on the same
    line (so ``Owner:``'s value does not swallow a same-line
    ``Last decision:``); otherwise runs to the end of the line. Empty when
    ``marker`` is not actually on that line.
    """
    line = lines[idx]
    pos = line.find(marker)
    if pos == -1:
        return ""
    value = line[pos + len(marker):]
    if other_marker:
        other_pos = value.find(other_marker)
        if other_pos != -1:
            value = value[:other_pos]
    return value.strip()


def _rules_block_bounds(lines: List[str]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """0-indexed (rules_idx, how_idx, end) bracketing the §0 rules block.

    ``rules_idx`` is the ``**Rules:**`` line inside §0 (or, when the doc has
    no §0 heading at all, the first one anywhere), or None when absent.
    ``end`` is where the block stops: the next bold ``**Field:**`` marker
    (normally ``**How we'll know:**``, else ``**Scenarios:**``), the next
    ``## `` heading, or the end of §0 -- whichever comes first. It is never
    the end of the file while any of those exists, so a missing or
    mistyped How-we'll-know marker cannot sweep the rest of the doc into
    the rules block. ``how_idx`` is the ``**How we'll know:**`` line (ASCII
    or curly apostrophe) when it is the line that ends the block, else None.
    """
    scan = unfenced(lines)
    tldr = tldr_block_bounds(lines)
    if tldr is not None:
        tldr_start, tldr_end = tldr
        rules_idx = find_line_index(scan, lambda l: RULES_MARKER in l, start=tldr_start)
        if rules_idx is not None and rules_idx >= tldr_end:
            rules_idx = None
    else:
        tldr_end = len(lines)
        rules_idx = find_line_index(scan, lambda l: RULES_MARKER in l)
    if rules_idx is None:
        return None, None, None
    end = tldr_end
    stop = find_line_index(
        scan,
        lambda l: BOLD_FIELD_RE.match(l) is not None or l.startswith("## "),
        start=rules_idx + 1,
    )
    if stop is not None and stop < end:
        end = stop
    how_idx = end if end < len(lines) and HOW_WE_KNOW_RE.search(scan[end]) else None
    return rules_idx, how_idx, end


def parse_rules_block(lines: List[str]) -> Tuple[List[Dict[str, Any]], Optional[int], Optional[int]]:
    """Parse the §0 rules between **Rules:** and the next bold field.

    Returns (records, rules_line_idx, how_we_know_line_idx). Each record:
    ``{"start_line": 1-based, "format": "bullet"|"numbered", "raw_text": str,
    "tags": [...] or None}``. Continuation lines (indented, not starting a
    new ``- `` or ``N.`` item) are joined onto the currently open rule
    before the trailing tag is checked. A non-blank line that is neither a
    bullet, a numbered item, nor an indented continuation is excluded here
    entirely — ``check_rules_format`` reports it as a stray line. Returns
    ([], None, None) when the **Rules:** anchor is absent.
    """
    rules_idx, how_idx, end = _rules_block_bounds(lines)
    if rules_idx is None:
        return [], None, None
    scan = unfenced(lines)

    records: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for i in range(rules_idx + 1, end):
        raw_line = scan[i]
        if not raw_line.strip():
            current = None
            continue
        m_bullet = BULLET_START_RE.match(raw_line)
        m_numbered = NUMBERED_START_RE.match(raw_line)
        if m_bullet:
            current = {"start_line": i + 1, "format": "bullet", "parts": [m_bullet.group(1).rstrip()]}
            records.append(current)
        elif m_numbered:
            current = {"start_line": i + 1, "format": "numbered", "parts": [m_numbered.group(2).rstrip()]}
            records.append(current)
        elif current is not None and raw_line[:1].isspace():
            current["parts"].append(raw_line.strip())
        else:
            # Stray text: not a bullet/numbered start, and not an indented
            # continuation of the rule before it (or nothing is open).
            current = None

    for record in records:
        record["raw_text"] = " ".join(record.pop("parts")).strip()
        tag_match = TAG_RE.search(record["raw_text"])
        if tag_match:
            tag_text = tag_match.group(1)
            record["tags"] = ["UNTESTED"] if tag_text == "UNTESTED" else [
                t.strip() for t in tag_text.split(",")
            ]
            record["text"] = record["raw_text"][: tag_match.start()].rstrip()
        else:
            record["tags"] = None
            record["text"] = record["raw_text"]
    return records, rules_idx, how_idx


def find_stray_rule_lines(lines: List[str]) -> List[int]:
    """1-based line numbers in the §0 rules block that are neither a
    ``- `` bullet, a numbered item, nor an indented continuation of the
    line before them. Empty when the **Rules:** anchor is absent."""
    rules_idx, _how_idx, end = _rules_block_bounds(lines)
    if rules_idx is None:
        return []
    scan = unfenced(lines)

    stray: List[int] = []
    open_rule = False
    for i in range(rules_idx + 1, end):
        raw_line = scan[i]
        if not raw_line.strip():
            open_rule = False
            continue
        if BULLET_START_RE.match(raw_line) or NUMBERED_START_RE.match(raw_line):
            open_rule = True
            continue
        if open_rule and raw_line[:1].isspace():
            continue
        stray.append(i + 1)
        open_rule = False
    return stray


ACCEPTANCE_HEADER_RE = re.compile(r"^(#|id|at)$", re.IGNORECASE)


def _code_span_end(text: str, i: int) -> int:
    """Where the code span opened by the backtick run at ``text[i]`` ends
    (just past its closing run of the same length), or -1 when the run is
    never closed on this line -- a lone backtick is text, not code."""
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


def _backtick_run(text: str, i: int) -> int:
    j = i
    while j < len(text) and text[j] == "`":
        j += 1
    return j


def split_cells(inner: str) -> List[str]:
    """A table row's cells, from the text between its outer pipes, split as
    GitHub splits them: at every pipe a backslash does not escape, inside a
    `code span` too, since the row is cut into cells before code is read. A
    pipe written ``\\|`` is cell text, read back as ``|``; ``\\\\|`` is an
    escaped backslash and then a column break."""
    cells: List[str] = []
    buf: List[str] = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner):
            nxt = inner[i + 1]
            buf.append("|" if nxt == "|" else ch + nxt)
            i += 2
        elif ch == "|":
            cells.append("".join(buf))
            buf = []
            i += 1
        else:
            buf.append(ch)
            i += 1
    cells.append("".join(buf))
    return [c.strip() for c in cells]


def strip_code_spans(text: str) -> str:
    """``text`` with every closed `code span` blanked out: what a
    placeholder scan reads, since ``<id>`` in code is a command's own
    argument, not an unfilled slot."""
    out: List[str] = []
    i = 0
    while i < len(text):
        if text[i] == "`":
            end = _code_span_end(text, i)
            if end == -1:
                end = _backtick_run(text, i)
                out.append(text[i:end])
            else:
                out.append(" ")
            i = end
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def split_tables(
    lines: List[str], start: int, end: int, pipeless: Optional[List[int]] = None
) -> List[List[Tuple[int, List[str]]]]:
    """Every pipe table in [start, end) as its own list of (line_no, cells).

    A table is a run of consecutive pipe rows; any other line ends it. A section may
    hold several tables, and only the acceptance table is subject to row-id rules.

    A line directly under a running table that contains a pipe but lacks its
    leading or trailing one is still a row of that table -- GFM treats the
    outer pipes as optional -- and is read with the outer pipes stripped, so
    a one-character slip never drops the row, nor every intact row below
    it. Its 1-based line number is appended to ``pipeless`` when a list is
    given, so ACCEPTANCE_TABLE can report it at its own line. Rows inside a
    fenced code block are not rows. A Why line or the Snapshot line -- the
    two structural lines the contract puts directly under the table -- ends
    the table even when its prose holds a pipe: a structural line is never
    a row. A kill-record line (``record_kind``) with a row below it does not
    end the table, so a misplaced record line never hides the rows after it. Cells are split by ``split_cells``: an escaped pipe stays in its
    cell, and any other pipe, in a code span too, starts the next one.
    """
    scan = unfenced(lines)
    tables: List[List[Tuple[int, List[str]]]] = []
    current: List[Tuple[int, List[str]]] = []
    for i in range(start, end):
        line = scan[i].rstrip("\r\n")
        m = TABLE_ROW_RE.match(line)
        if current and not m and record_kind(line):
            # a record line between two rows: read on, so no row below it is hidden
            # (check_kill_record reports the line itself)
            j = i + 1
            while j < end and record_kind(scan[j]):
                j += 1
            if j < end and TABLE_ROW_RE.match(scan[j]):
                continue
        if m and not _escaped_at_end(m.group(1)):
            current.append((i + 1, split_cells(m.group(1))))
        elif (m or current) and "|" in line and not _is_structural_under_table(line):
            inner = line.strip()
            if inner.startswith("|"):
                inner = inner[1:]
            if inner.endswith("|") and not _escaped_at_end(inner[:-1]):
                inner = inner[:-1]
            current.append((i + 1, split_cells(inner)))
            if pipeless is not None:
                pipeless.append(i + 1)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def _escaped_at_end(text: str) -> bool:
    """True when ``text`` ends in an odd run of backslashes, so the pipe
    that follows it is escaped: cell text, not the row's closing pipe."""
    return (len(text) - len(text.rstrip("\\"))) % 2 == 1


def _is_structural_under_table(line: str) -> bool:
    """True for a Why line, a Snapshot line, arm's ``Red run:`` line or a
    kill-record line (``Filed without red run:``, ``Kill:``) (a
    leading backtick or asterisk tolerated on the last two, as
    bridge_validate.py tolerates it on the Snapshot line): the lines the
    contract places directly under the §6 table, which end a table whatever
    characters their prose carries (a command's ``|`` included)."""
    stripped = line.lstrip()
    if WHY_LINE_RE.match(stripped):
        return True
    return stripped.lstrip("`*").startswith(("Snapshot taken at", "Red run:", FILED_PREFIX, KILL_PREFIX))


def is_separator(cells: List[str]) -> bool:
    return bool(any(cells)) and all(SEPARATOR_CELL_RE.match(c) for c in cells if c)


def parse_table_data_rows(lines: List[str], start: int, end: int) -> List[Tuple[int, List[str]]]:
    """Data rows of the acceptance tables in [start, end): header and separator skipped.

    An acceptance table is one whose header's first cell is ``#`` (the template's
    shape) or ``ID``/``AT``. Other tables in the section — a classification table,
    a summary — are not acceptance rows and are left alone.
    """
    out: List[Tuple[int, List[str]]] = []
    for table in split_tables(lines, start, end):
        header = table[0][1]
        if not header or not ACCEPTANCE_HEADER_RE.match(header[0]):
            continue
        body = table[1:]
        if body and is_separator(body[0][1]):
            body = body[1:]
        out.extend(body)
    return out


REQUIRED_ACCEPTANCE_COLUMNS = ("given", "when", "then")
NAMED_ACCEPTANCE_COLUMNS = REQUIRED_ACCEPTANCE_COLUMNS + ("altitude", "row")


def acceptance_column_map(header_cells: List[str]) -> Optional[Dict[str, Optional[int]]]:
    """Column name -> 0-based index for one §6 acceptance-table header, or
    None when the header does not qualify as an acceptance table at all.

    Columns are matched by HEADER NAME, case-insensitive and trimmed, never
    by position — a real doc's header can read ``# | Label | Given | When |
    Then`` (an extra column before Given) or carry ``Row`` anywhere, and
    still qualify. The id column is always the first cell, and must be
    ``#``, ``ID`` or ``AT`` (case-insensitive) — this one column is
    positional by definition, not looked up by name. ``Given``, ``When``
    and ``Then`` must each appear by name somewhere in the header (any
    order); a header missing one of them does not qualify, the same as no
    table at all. ``Altitude`` and ``Row`` are optional: each maps to its
    index when a column carries that name, else None, so a doc without one
    reads every row's ``altitude``/``row`` as None rather than misreading
    some other column (ALTITUDE_MISSING warns about the absent Altitude
    column separately). Any other header cell (``Label``, ``Notes``, ...)
    sits in the table but is never read into a named field. A header that
    names ``Given``, ``When``, ``Then``, ``Altitude`` or ``Row`` more than
    once does not qualify either — there is no rule for which occurrence
    is "the" column, so this never guesses; ACCEPTANCE_TABLE reports it the
    same as a header missing one of them.
    """
    if not header_cells or not ACCEPTANCE_HEADER_RE.match(header_cells[0]):
        return None
    by_name: Dict[str, int] = {}
    duplicated: set = set()
    for i, cell in enumerate(header_cells):
        key = cell.strip().lower()
        if not key:
            continue
        if key in by_name:
            duplicated.add(key)
        else:
            by_name[key] = i
    if duplicated & set(NAMED_ACCEPTANCE_COLUMNS):
        return None
    for name in REQUIRED_ACCEPTANCE_COLUMNS:
        if name not in by_name:
            return None
    mapping: Dict[str, Optional[int]] = {"id": 0}
    mapping.update({name: by_name[name] for name in REQUIRED_ACCEPTANCE_COLUMNS})
    mapping["altitude"] = by_name.get("altitude")
    mapping["row"] = by_name.get("row")
    return mapping


def find_acceptance_tables(
    lines: List[str], start: int, end: int
) -> List[Tuple[int, List[str], List[Tuple[int, List[str]]], Optional[Dict[str, Optional[int]]], List[int]]]:
    """Every #/ID/AT-headed candidate table in [start, end), qualifying or not.

    A table is a candidate the instant its header's first cell is
    #/ID/AT -- acceptance_column_map then says whether it QUALIFIES (a
    dict) or not (None -- missing or duplicate Given/When/Then/Altitude/Row).
    Every candidate is returned either way, so a malformed table is still
    reported by ACCEPTANCE_TABLE even when a sibling table in the same
    section qualifies fine -- the two are never conflated into one verdict
    for the section. A table whose first cell does not match at all is not
    a candidate (a Decisions-style table, say) and is not returned. Returns
    a list of (header_line, header_cells, data_rows, column_map_or_None,
    pipeless_row_lines), each already separator-stripped; the last element
    is the 1-based line of every row in that table that lacks its leading
    or trailing pipe (see split_tables).
    """
    pipeless: List[int] = []
    found = []
    for table in split_tables(lines, start, end, pipeless):
        header_line, header_cells = table[0]
        if not header_cells or not ACCEPTANCE_HEADER_RE.match(header_cells[0]):
            continue
        column_map = acceptance_column_map(header_cells)
        body = table[1:]
        if body and is_separator(body[0][1]):
            body = body[1:]
        own_lines = {line_no for line_no, _cells in body}
        found.append(
            (header_line, header_cells, body, column_map, [n for n in pipeless if n in own_lines])
        )
    return found


def _cell_at(cells: List[str], idx: Optional[int]) -> str:
    """cells[idx], or "" when idx is None or past the row's own length --
    a short row (ACCEPTANCE_TABLE's own concern) never raises here."""
    return cells[idx] if idx is not None and idx < len(cells) else ""


def parse_acceptance_rows(lines: List[str]) -> List[Dict[str, Any]]:
    """Well-formed §6 rows (id, given, when, then, altitude, row) keyed on AT-\\d+.

    Reuses find_acceptance_tables so a table is a candidate on exactly the
    same terms ACCEPTANCE_TABLE judges it by. A QUALIFYING header (see
    acceptance_column_map) is read by name -- an extra column (a Label) or
    a reordered Row never shifts what a cell means, and altitude/row are
    None whenever no header cell is named Altitude/Row (or the cell is
    empty). A candidate whose header does NOT qualify (missing or duplicate
    Given/When/Then/Altitude/Row -- ACCEPTANCE_TABLE reports the header
    itself as broken) still contributes its row ids, for SCENARIOS_COUNT's
    count and TAGS_RESOLVE's lookup -- but ONLY that: given/when/then come
    back empty and altitude/row come back None, never a value read from a
    position that might belong to an entirely different column (the
    concrete failure this guards: a duplicate Then column, read
    positionally, put the second Then's text into row).
    """
    bounds = section_bounds(lines, 6)
    if bounds is None:
        return []
    start, end = bounds
    rows = []
    for _header_line, _header_cells, body, column_map, _pipeless in find_acceptance_tables(
        lines, start + 1, end
    ):
        for line_no, cells in body:
            if not cells or not AT_ID_RE.match(cells[0]):
                continue
            if column_map is None:
                rows.append(
                    {
                        "line": line_no,
                        "id": cells[0],
                        "given": "",
                        "when": "",
                        "then": "",
                        "altitude": None,
                        "row": None,
                    }
                )
                continue
            given = _cell_at(cells, column_map["given"])
            when = _cell_at(cells, column_map["when"])
            then = _cell_at(cells, column_map["then"])
            altitude_text = _cell_at(cells, column_map["altitude"]).strip()
            row_text = _cell_at(cells, column_map["row"]).strip()
            rows.append(
                {
                    "line": line_no,
                    "id": cells[0],
                    "given": given,
                    "when": when,
                    "then": then,
                    "altitude": altitude_text or None,
                    "row": row_text or None,
                }
            )
    return rows


def parse_bold_field_value(lines: List[str], marker: Marker) -> str:
    """The text after a ``**Field:**`` marker (a literal, or a compiled
    pattern such as HOW_WE_KNOW_RE), with wrapped continuation lines
    joined. Continuation stops at a blank line, the next bold field, or a
    ``- `` bullet — whichever comes first. Empty when ``marker`` is not
    found in ``lines`` at all. Fenced lines never carry the marker."""
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: _marker_span(l, marker) is not None)
    if idx is None:
        return ""
    _start, end_of_marker = _marker_span(scan[idx], marker)
    parts = [scan[idx][end_of_marker:].strip()]
    i = idx + 1
    while i < len(scan):
        stripped = scan[i].strip()
        if not stripped or stripped.startswith("**") or stripped.startswith("-"):
            break
        parts.append(stripped)
        i += 1
    return " ".join(p for p in parts if p).strip()


def parse_signal(lines: List[str]) -> str:
    """The **How we'll know:** text, with wrapped continuation lines joined."""
    return parse_bold_field_value(lines, HOW_WE_KNOW_RE)


def worked_examples(lines: List[str]) -> Tuple[List[Tuple[int, int]], Optional[str]]:
    """§3 example (start, end) 0-indexed ranges, and which pattern was used.

    Tries ``### `` headings first, then bold-led paragraphs. Returns
    ``([], None)`` when neither pattern yields at least one example.
    """
    bounds = section_bounds(lines, 3)
    if bounds is None:
        return [], None
    start, end = bounds
    scan = unfenced(lines)
    for pattern, kind in ((H3_RE, "heading"), (BOLD_LED_RE, "bold")):
        starts = [i for i in range(start + 1, end) if pattern.match(scan[i])]
        if starts:
            ranges = []
            for idx, s in enumerate(starts):
                e = starts[idx + 1] if idx + 1 < len(starts) else end
                ranges.append((s, e))
            return ranges, kind
    return [], None


# ---------------------------------------------------------------------------
# Rule checks
# ---------------------------------------------------------------------------


def check_header_status(lines: List[str]) -> List[Dict[str, Any]]:
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: STATUS_RE.match(l) is not None)
    if idx is None:
        return [finding("HEADER_STATUS", 1, "missing a 'Status:' line", "error")]
    match = STATUS_RE.match(scan[idx])
    token = match.group(1)
    if token not in VALID_STATUS_TOKENS:
        return [
            finding(
                "HEADER_STATUS",
                idx + 1,
                f"Status: token {token!r} is not one of draft, agreed, building, shipped, superseded-by",
                "error",
            )
        ]
    if token == "superseded-by" and not scan[idx][match.end():].strip():
        return [
            finding(
                "HEADER_STATUS",
                idx + 1,
                "Status: superseded-by must name a target",
                "error",
            )
        ]
    return []


# The marker render_outcome.py --thin writes in each of §3-§7. Only a line
# that is just the marker -- the template's sentence, or "Not written yet"
# alone, in emphasis or not -- says a section is not written yet. Any other
# text on the line ("Not written yet in full, but: ...") is content.
THIN_PENDING_RE = re.compile(
    r"^[*_]*\s*not written yet\s*"
    r"(?::\s*this is a thin draft\.\s*run `/promise revise` on this doc to write it\.|[.:])?"
    r"\s*[*_]*$",
    re.IGNORECASE,
)
ROLE_LINE_RE = re.compile(r"^\*\(.*\)\*$")
HTML_COMMENT_RE = re.compile(r"^<!--.*-->$")
THIN_SECTIONS = (3, 4, 5, 6, 7)


def _thin_section_findings(lines: List[str]) -> List[Dict[str, Any]]:
    """On a thin draft, §3-§7 each hold the not-written-yet marker (a line
    that is just the marker: ``THIN_PENDING_RE``), and §4-§7 hold nothing
    else but their role line (``*(agent)*``): a thin draft is the human half
    only. §3 may also hold a seed example the human gave.
    Every other line in §4-§7 -- text, a table, a Why line, a fence -- is
    agent-half content on a doc that says it has none."""
    out: List[Dict[str, Any]] = []
    for n in THIN_SECTIONS:
        bounds = section_bounds(lines, n)
        if bounds is None:
            continue  # HEADINGS_BARE reports the missing heading
        start, end = bounds
        body = [(i, lines[i].strip()) for i in range(start + 1, end) if lines[i].strip()]
        if not any(THIN_PENDING_RE.match(text) for _i, text in body):
            out.append(
                finding(
                    "THIN_DRAFT",
                    start + 1,
                    f"§{n} does not say it is not written yet; a thin draft holds the human half only",
                    "error",
                )
            )
        if n == 3:
            continue
        content = [
            i for i, text in body
            if not (THIN_PENDING_RE.match(text) or ROLE_LINE_RE.match(text) or HTML_COMMENT_RE.match(text))
        ]
        if content:
            out.append(
                finding(
                    "THIN_DRAFT",
                    content[0] + 1,
                    f"§{n} holds text on a thin draft ({len(content)} line(s)); a thin draft holds the "
                    "human half only: write the agent half with revise and remove the Depth: line, "
                    "or move the text out",
                    "error",
                )
            )
    return out


def check_thin_draft(lines: List[str]) -> List[Dict[str, Any]]:
    """THIN_DRAFT (error): a ``Depth:`` line reads anything but ``thin``, or
    a thin doc's status is not ``draft``. A thin draft has no acceptance rows
    to test, so it cannot be agreed; the agent half is written and the line
    removed first. On a thin draft, §3-§7 each say they are not written yet,
    and §4-§7 hold nothing else (``_thin_section_findings``)."""
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: DEPTH_RE.match(l) is not None)
    if idx is None:
        return []
    depth = DEPTH_RE.match(scan[idx]).group(1)
    if depth != "thin":
        return [
            finding(
                "THIN_DRAFT",
                idx + 1,
                f"Depth: token {depth!r} is not 'thin' (a full doc has no Depth: line)",
                "error",
            )
        ]
    status = get_status(lines)
    if status != "draft":
        return [
            finding(
                "THIN_DRAFT",
                idx + 1,
                f"Depth: thin on a doc whose Status: is {status}; write §3-§7 and remove "
                "the Depth: line before the doc leaves draft",
                "error",
            )
        ]
    return _thin_section_findings(lines)


def check_header_owner(lines: List[str]) -> List[Dict[str, Any]]:
    scan = unfenced(lines)
    out = []
    owner_idx = find_line_index(scan, lambda l: "Owner:" in l)
    if owner_idx is None:
        out.append(finding("HEADER_OWNER", 1, "missing an 'Owner:' field", "error"))
    elif not parse_header_field_value(scan, owner_idx, "Owner:", "Last decision:"):
        out.append(finding("HEADER_OWNER", owner_idx + 1, "'Owner:' value is empty", "error"))

    last_decision_idx = find_line_index(scan, lambda l: "Last decision:" in l)
    if last_decision_idx is None:
        out.append(
            finding(
                "HEADER_OWNER",
                owner_idx + 1 if owner_idx is not None else 1,
                "missing a 'Last decision:' field",
                "error",
            )
        )
    elif not parse_header_field_value(scan, last_decision_idx, "Last decision:"):
        out.append(
            finding("HEADER_OWNER", last_decision_idx + 1, "'Last decision:' value is empty", "error")
        )
    return out


def check_contents_line(lines: List[str]) -> List[Dict[str, Any]]:
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: l.strip().startswith("Contents:"))
    if idx is None:
        return [finding("CONTENTS_LINE", 1, "missing a 'Contents:' line", "error")]
    block = [scan[idx]]
    i = idx + 1
    while i < len(scan) and scan[i].strip():
        block.append(scan[i])
        i += 1
    text = " ".join(block)
    missing = [a for a in CONTENTS_ANCHORS if a not in text]
    if missing:
        return [
            finding(
                "CONTENTS_LINE",
                idx + 1,
                "Contents: line is missing anchor(s): " + ", ".join(missing),
                "error",
            )
        ]
    return []


def check_headings_bare(lines: List[str]) -> List[Dict[str, Any]]:
    by_number: Dict[int, List[Tuple[int, str]]] = {}
    for i, line in enumerate(unfenced(lines)):
        m = HEADING_RE.match(line)
        if not m:
            continue
        n = int(m.group(1))
        by_number.setdefault(n, []).append((i + 1, m.group(2)))

    out = []
    for n in range(0, 11):
        expected = f"{n}. {SECTION_NAMES[n]}"
        entries = by_number.get(n, [])
        if not entries:
            out.append(finding("HEADINGS_BARE", 1, f"missing heading '## {expected}'", "error"))
            continue
        # Every malformed heading fires, whether or not a well-formed one for
        # the same number also exists — a valid heading must never mask a
        # malformed duplicate.
        good = [e for e in entries if e[1] == SECTION_NAMES[n]]
        bad = [e for e in entries if e[1] != SECTION_NAMES[n]]
        for line_no, actual in bad:
            out.append(
                finding(
                    "HEADINGS_BARE",
                    line_no,
                    f"heading must read exactly '## {expected}' (found '## {n}. {actual}')",
                    "error",
                )
            )
        if len(good) > 1:
            out.append(
                finding(
                    "HEADINGS_BARE",
                    good[1][0],
                    f"heading '## {expected}' appears more than once",
                    "error",
                )
            )
    return out


def check_tldr_budget(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = tldr_block_bounds(lines)
    if bounds is None:
        return []
    start, end = bounds
    count = end - start
    if count > 40:
        return [
            finding(
                "TLDR_BUDGET",
                start + 1,
                f"§0 TLDR block is {count} lines (max 40)",
                "error",
            )
        ]
    return []


def check_tldr_fields(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = tldr_block_bounds(lines)
    if bounds is None:
        return []
    start, end = bounds
    block_lines = unfenced(lines)[start:end]
    out = []
    fields: List[Tuple[str, Marker]] = [
        ("**Outcome:**", "**Outcome:**"),
        ("**Rules:**", RULES_MARKER),
        (HOW_WE_KNOW_MARKER, HOW_WE_KNOW_RE),
        ("**Scenarios:**", "**Scenarios:**"),
    ]
    present = {
        name: find_line_index(block_lines, lambda l, m=marker: _marker_span(l, m) is not None)
        for name, marker in fields
    }
    for name, _marker in fields:
        if present[name] is None:
            out.append(finding("TLDR_FIELDS", start + 1, f"§0 is missing {name}", "error"))

    # A field that IS present must still carry a value — text on the marker's
    # own line, or on indented/plain continuation lines before the next bold
    # field. **Rules:** has its own shape rules (RULES_PRESENT for an empty
    # block, RULES_FORMAT/RULES_TAGGED for each bullet) and **Scenarios:**
    # has SCENARIOS_COUNT, so only the two freeform fields are checked for
    # emptiness here.
    for name, marker in fields:
        if name not in ("**Outcome:**", HOW_WE_KNOW_MARKER) or present[name] is None:
            continue
        if not parse_bold_field_value(block_lines, marker):
            out.append(finding("TLDR_FIELDS", start + present[name] + 1, f"{name} has no value", "error"))
    return out


def check_rules_present(lines: List[str]) -> List[Dict[str, Any]]:
    """A ``**Rules:**`` marker with no rule bullet under it is an error at
    every status: a field checked for presence is also checked for a value,
    the same as ``**Outcome:**`` and ``**How we'll know:**``. A block that
    holds only stray text is left to RULES_FORMAT, which already names the
    stray line, so the two never fire together on the same defect."""
    records, rules_idx, _ = parse_rules_block(lines)
    if rules_idx is None or records or find_stray_rule_lines(lines):
        return []
    # A thin draft may start before the human can state a rule; the gap is
    # a warning there, and a BLOCKING §9 question carries it.
    return [
        finding(
            "RULES_PRESENT",
            rules_idx + 1,
            "**Rules:** has no rule bullets (at least one '- ' rule is required)",
            "warn" if is_thin(lines) else "error",
        )
    ]


def check_rules_format(lines: List[str]) -> List[Dict[str, Any]]:
    records, rules_idx, _ = parse_rules_block(lines)
    if rules_idx is None:
        return []
    out = [
        finding("RULES_FORMAT", r["start_line"], "rule must be a '- ' bullet, not numbered", "error")
        for r in records
        if r["format"] == "numbered"
    ]
    out.extend(
        finding("RULES_FORMAT", line_no, "text in the rules block is not a rule bullet", "error")
        for line_no in find_stray_rule_lines(lines)
    )
    out.extend(
        finding("RULES_FORMAT", r["start_line"], "rule bullet has no text before its tag", "error")
        for r in records
        if r["format"] == "bullet" and r["tags"] is not None and not r["text"]
    )
    return out


def check_rules_tagged(lines: List[str]) -> List[Dict[str, Any]]:
    records, rules_idx, _ = parse_rules_block(lines)
    if rules_idx is None:
        return []
    return [
        finding(
            "RULES_TAGGED",
            r["start_line"],
            "rule does not end with '→ AT-n[, AT-m]' or '→ UNTESTED'",
            "error",
        )
        for r in records
        if r["tags"] is None
    ]


def check_tags_resolve(lines: List[str]) -> List[Dict[str, Any]]:
    records, rules_idx, _ = parse_rules_block(lines)
    if rules_idx is None:
        return []
    row_ids = {r["id"] for r in parse_acceptance_rows(lines)}
    out = []
    for r in records:
        if not r["tags"] or r["tags"] == ["UNTESTED"]:
            continue
        for tag in r["tags"]:
            if tag not in row_ids:
                out.append(
                    finding(
                        "TAGS_RESOLVE",
                        r["start_line"],
                        f"{tag} cited in §0 does not exist as a §6 row id",
                        "error",
                    )
                )
    return out


def check_at_ids_unique(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = section_bounds(lines, 6)
    if bounds is None:
        return []
    start, end = bounds
    out = []
    seen: Dict[str, int] = {}
    for line_no, cells in parse_table_data_rows(lines, start + 1, end):
        if not cells:
            continue
        row_id = cells[0]
        if not AT_ID_RE.match(row_id):
            out.append(
                finding("AT_IDS_UNIQUE", line_no, f"§6 row id {row_id!r} does not match AT-\\d+", "error")
            )
            continue
        if row_id in seen:
            out.append(finding("AT_IDS_UNIQUE", line_no, f"duplicate §6 row id {row_id}", "error"))
        else:
            seen[row_id] = line_no
    return out


def check_acceptance_table(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = section_bounds(lines, 6)
    if bounds is None:
        # HEADINGS_BARE already reports a missing "## 6." heading.
        return []
    start, end = bounds
    tables = find_acceptance_tables(lines, start + 1, end)  # every candidate, qualifying or not
    if not tables:
        if is_thin(lines):
            # A thin draft has no acceptance rows yet; a table it does
            # carry is still checked in full below.
            return []
        return [
            finding(
                "ACCEPTANCE_TABLE",
                start + 1,
                "§6 has no acceptance table (need a header row whose first cell is "
                "'#', 'ID' or 'AT' and which names Given, When and Then)",
                "error",
            )
        ]

    qualifying = [t for t in tables if t[3] is not None]
    malformed = [t for t in tables if t[3] is None]

    out: List[Dict[str, Any]] = []

    # A row missing its leading or trailing pipe is read anyway (see
    # split_tables) and reported at its own line, for every candidate table.
    for _header_line, _header_cells, _body, _column_map, pipeless in tables:
        for line_no in pipeless:
            out.append(
                finding(
                    "ACCEPTANCE_TABLE",
                    line_no,
                    "acceptance table row is missing its leading or trailing pipe "
                    "(a line with a pipe directly under a table is read as one of its rows)",
                    "error",
                )
            )

    if not qualifying:
        # Every #/ID/AT-headed candidate failed its own header check --
        # report each on the "no acceptance table" terms (matches the
        # single-candidate case's long-standing message), at its own line.
        for header_line, _header_cells, _body, _column_map, _pipeless in malformed:
            out.append(
                finding(
                    "ACCEPTANCE_TABLE",
                    header_line,
                    "§6 has no acceptance table (need a header row whose first cell is "
                    "'#', 'ID' or 'AT' and which names Given, When and Then)",
                    "error",
                )
            )
        return out

    # At least one candidate qualifies: a malformed SIBLING is reported on
    # its own terms -- never silently dropped just because another table
    # in the same section is fine (that used to make a duplicate-column
    # sibling produce zero findings at all).
    for header_line, _header_cells, _body, _column_map, _pipeless in malformed:
        out.append(
            finding(
                "ACCEPTANCE_TABLE",
                header_line,
                "a second acceptance-shaped table's header does not qualify — Given, When "
                "and Then must each appear exactly once (Altitude and Row at most once)",
                "error",
            )
        )

    total_rows = 0
    required_cell_names = ("Given", "When", "Then")
    for header_line, header_cells, body, column_map, _pipeless in qualifying:
        width = len(header_cells)
        for line_no, cells in body:
            total_rows += 1
            if len(cells) != width:
                out.append(
                    finding(
                        "ACCEPTANCE_TABLE",
                        line_no,
                        f"acceptance table row has {len(cells)} cells, expected {width}"
                        + (" (a pipe inside a cell, in code too, is written \\|)" if len(cells) > width else ""),
                        "error",
                    )
                )
                continue
            for name in required_cell_names:
                idx = column_map[name.lower()]
                if not cells[idx].strip():
                    out.append(
                        finding(
                            "ACCEPTANCE_TABLE",
                            line_no,
                            f"acceptance table row's {name} cell is empty",
                            "error",
                        )
                    )
    if total_rows == 0:
        out.append(
            finding("ACCEPTANCE_TABLE", qualifying[0][0], "acceptance table has no data rows", "error")
        )
    return out


def check_acceptance_altitude(lines: List[str]) -> List[Dict[str, Any]]:
    """Every qualifying §6 table names each row's altitude.

    ACCEPTANCE_ALTITUDE (error, every status): the ``Altitude`` column is
    present and a data cell is empty or not exactly one of ``data``,
    ``response``, ``perception``, ``judgement``, ``sibling``. A cell that
    is an angle-bracket placeholder (``<altitude>``) is PLACEHOLDER's
    concern, not this rule's, so the bundled template reports it once. A
    row whose cell count differs from the header's is ACCEPTANCE_TABLE's
    concern and is skipped here. ALTITUDE_MISSING (warn): a qualifying
    table has no ``Altitude`` header at all -- an older doc keeps linting,
    and the warning says what to add.
    """
    bounds = section_bounds(lines, 6)
    if bounds is None:
        return []
    start, end = bounds
    out: List[Dict[str, Any]] = []
    for header_line, header_cells, body, column_map, _pipeless in find_acceptance_tables(
        lines, start + 1, end
    ):
        if column_map is None:
            continue
        idx = column_map["altitude"]
        if idx is None:
            out.append(
                finding(
                    "ALTITUDE_MISSING",
                    header_line,
                    "§6 acceptance table has no Altitude column (add one between Then and Row; "
                    "each cell is data, response, perception, judgement or sibling)",
                    "warn",
                )
            )
            continue
        for line_no, cells in body:
            if len(cells) != len(header_cells):
                continue
            value = cells[idx].strip()
            if ANGLE_PLACEHOLDER_RE.fullmatch(value):
                continue
            if not value:
                out.append(
                    finding(
                        "ACCEPTANCE_ALTITUDE",
                        line_no,
                        "acceptance table row's Altitude cell is empty "
                        "(one of data, response, perception, judgement, sibling)",
                        "error",
                    )
                )
            elif value not in ALTITUDES:
                out.append(
                    finding(
                        "ACCEPTANCE_ALTITUDE",
                        line_no,
                        f"acceptance table row's Altitude {value!r} is not one of "
                        "data, response, perception, judgement, sibling",
                        "error",
                    )
                )
    return out


def check_scenarios_count(lines: List[str]) -> List[Dict[str, Any]]:
    bounds = tldr_block_bounds(lines)
    if bounds is None:
        return []
    start, end = bounds
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: "**Scenarios:**" in l, start=start)
    if idx is None or idx >= end:
        return []
    m = SCENARIOS_RE.search(scan[idx])
    if not m and SCENARIOS_FREE_RE.search(scan[idx]):
        return []  # it names the sections and counts nothing, so it cannot go stale
    if not m:
        return [
            finding(
                "SCENARIOS_COUNT",
                idx + 1,
                f"Scenarios: line is neither {SCENARIOS_FREE_LINE!r} nor "
                "'<N> acceptance rows (§6), <M> worked examples (§3).'",
                "error",
            )
        ]
    out = []
    n_claimed, m_claimed = int(m.group(1)), int(m.group(2))
    n_actual = len(parse_acceptance_rows(lines))
    if n_claimed != n_actual:
        out.append(
            finding(
                "SCENARIOS_COUNT",
                idx + 1,
                f"Scenarios: claims {n_claimed} acceptance rows but §6 has {n_actual}",
                "error",
            )
        )
    ranges, kind = worked_examples(lines)
    if kind is None and is_thin(lines):
        # A thin §3 holds no example until the human seeds one: count zero.
        ranges, kind = [], "thin"
    if kind is None:
        out.append(
            finding(
                "SCENARIOS_COUNT",
                idx + 1,
                "§3 worked-example count not checked (no '### ' headings or bold-led paragraphs found)",
                "warn",
            )
        )
    else:
        m_actual = len(ranges)
        if m_claimed != m_actual:
            out.append(
                finding(
                    "SCENARIOS_COUNT",
                    idx + 1,
                    f"Scenarios: claims {m_claimed} worked examples but §3 has {m_actual}",
                    "error",
                )
            )
    return out


def _why_lines(lines: List[str], n: int) -> List[Tuple[int, str]]:
    """(0-indexed line, value after the colon) of every Why line in section n."""
    bounds = section_bounds(lines, n)
    if bounds is None:
        return []
    start, end = bounds
    scan = unfenced(lines)
    out = []
    for i in range(start, end):
        m = WHY_LINE_RE.match(scan[i].lstrip())
        if m:
            out.append((i, m.group(1).strip()))
    return out


def check_why_line(lines: List[str]) -> List[Dict[str, Any]]:
    """§4-§7 each carry a ``Why — what breaks without it:`` line, and the line
    carries a value. An angle-bracket value (``<one line>``) is a
    placeholder, reported by PLACEHOLDER rather than here, so the template
    lints under ``--template`` and a raw render reports each slot once."""
    if is_thin(lines):
        # §4-§7 are not written yet on a thin draft.
        return []
    out = []
    for n in WHY_SECTIONS:
        bounds = section_bounds(lines, n)
        if bounds is None:
            continue
        found = _why_lines(lines, n)
        if not found:
            out.append(
                finding(
                    "WHY_LINE",
                    bounds[0] + 1,
                    f"§{n} is missing a line beginning 'Why — what breaks without it:'",
                    "error",
                )
            )
            continue
        for i, value in found:
            if not value:
                out.append(
                    finding(
                        "WHY_LINE",
                        i + 1,
                        f"§{n} 'Why — what breaks without it:' has no value",
                        "error",
                    )
                )
    return out


QUESTION_RE = re.compile(
    r"^(Q\w*)\s+[—–-]+\s+owner:\s*(.+?)\s+[—–-]+\s+(BLOCKING|non-blocking)\b\s*[:.,;—–-]?\s*(.*)$",
    re.IGNORECASE,
)
# An answer line, written bare by `apply` or wrapped in Markdown emphasis by a person
# ("**Answer (YYYY-MM-DD, name):** …", "_Answered YYYY-MM-DD_ …").
ANSWER_RE = re.compile(r"^\s*[*_]{0,3}\s*(Answer|Answered)\b[^\n]*?\d{4}-\d{2}-\d{2}")
# The same answer appended on the question's own line ("… threads? Answered YYYY-MM-DD: …").
INLINE_ANSWER_RE = re.compile(r"(?:^|[\s.?!;:)])[*_]{0,3}(Answer|Answered)\b[^\n]*?\d{4}-\d{2}-\d{2}")


def parse_questions(lines: List[str]) -> List[Dict[str, Any]]:
    """Every §9 question: id, owner, blocking, text, answered, and its [start, end) lines."""
    bounds = section_bounds(lines, 9)
    if bounds is None:
        return []
    scan = unfenced(lines)
    out: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for i in range(bounds[0] + 1, bounds[1]):
        line = scan[i]
        m = QUESTION_RE.match(line)
        if m:
            current = {
                "q": m.group(1), "owner": m.group(2).strip(), "blocking": m.group(3).upper() == "BLOCKING",
                "parts": [m.group(4).strip()], "answered": bool(INLINE_ANSWER_RE.search(m.group(4))),
                "start": i, "end": i + 1,
            }
            out.append(current)
            continue
        if current is None:
            continue
        # A question runs until the next question or the end of §9. A blank line ends
        # its text, not the question: "Q2 … \n\n**Answer (…):** …" is answered.
        if not line.strip():
            current["gap"] = True
            continue
        if ANSWER_RE.match(line):
            current["answered"] = True
            current["gap"] = False
        elif current.get("gap"):
            continue  # a later paragraph that is not an answer belongs to no question
        elif not current["answered"]:
            current["parts"].append(line.strip())
            if INLINE_ANSWER_RE.search(line):
                current["answered"] = True
        current["end"] = i + 1
    for q in out:
        q["text"] = " ".join(p for p in q.pop("parts") if p)
        q.pop("gap", None)
    return out


PENDING_MARKER_RE = re.compile(r"pending verbatim confirmation", re.IGNORECASE)
# "Open — Q1 (BLOCKING)." — never an outcome that starts with the verb ("Open a shared channel").
OPEN_FIELD_RE = re.compile(r"^\s*(?i:open)\s*[—–-]+\s*Q\d+")
PAST_DRAFT = ("agreed", "building", "shipped")


def check_pending_on_agreed(lines: List[str]) -> List[Dict[str, Any]]:
    """A moved doc's §0 is a candidate block of quotes until a human confirms it by
    deleting its ``**Pending verbatim confirmation:**`` line. Past ``draft`` that
    marker, anywhere in §0, is an error: the block was never confirmed."""
    status = get_status(lines)
    bounds = tldr_block_bounds(lines)
    if status not in PAST_DRAFT or bounds is None:
        return []
    scan = unfenced(lines)
    return [
        finding("PENDING_ON_AGREED", i + 1,
                f"§0 is still marked pending verbatim confirmation while Status: is {status}; "
                "a human confirms the quotes by deleting that line, at draft", "error")
        for i in range(bounds[0], bounds[1]) if PENDING_MARKER_RE.search(scan[i])
    ]


def check_open_on_agreed(lines: List[str]) -> List[Dict[str, Any]]:
    """An §0 field a legacy doc never decided reads ``Open — Qn (BLOCKING).``; past
    ``draft`` the outcome line and how-we'll-know must say what was decided."""
    status = get_status(lines)
    if status not in PAST_DRAFT:
        return []
    scan = unfenced(lines)
    out = []
    for name, marker in (("Outcome", "**Outcome:**"), ("How we'll know", HOW_WE_KNOW_RE)):
        value = parse_bold_field_value(lines, marker)
        if value and OPEN_FIELD_RE.match(value):
            idx = find_line_index(scan, lambda l: _marker_span(l, marker) is not None)
            out.append(finding("OPEN_ON_AGREED", idx + 1 if idx is not None else None,
                               f"**{name}:** still reads {value[:40]!r} while Status: is {status}", "error"))
    return out


def check_blocking_open_on_agreed(lines: List[str]) -> List[Dict[str, Any]]:
    """A BLOCKING §9 question with no ``Answer (YYYY-MM-DD…)`` line under it is an
    error past ``draft`` (framework § Lifecycle)."""
    status = get_status(lines)
    if status not in PAST_DRAFT:
        return []
    return [
        finding("BLOCKING_OPEN_ON_AGREED", q["start"] + 1,
                f"{q['q']} is BLOCKING and has no answer while Status: is {status}", "error")
        for q in parse_questions(lines) if q["blocking"] and not q["answered"]
    ]


def check_untested_on_agreed(lines: List[str]) -> List[Dict[str, Any]]:
    status = get_status(lines)
    if status not in ("agreed", "building", "shipped"):
        return []
    records, rules_idx, _ = parse_rules_block(lines)
    if rules_idx is None:
        return []
    return [
        finding(
            "UNTESTED_ON_AGREED",
            r["start_line"],
            f"rule is tagged UNTESTED while Status: is {status}",
            "error",
        )
        for r in records
        if r["tags"] == ["UNTESTED"]
    ]


def red_gate_line(lines: List[str]) -> Tuple[bool, Optional[Tuple[int, str]]]:
    """Whether the header block (everything before the first ``## ``
    heading, fenced lines excluded) holds a ``Red gate: <sha> <YYYY-MM-DD>``
    line with a real date; and, when it holds none but one with a date that
    does not exist, that line's 1-based number and date text."""
    scan = unfenced(lines)
    header_end = find_line_index(scan, lambda l: l.startswith("## "))
    if header_end is None:
        header_end = len(lines)
    bad_date: Optional[Tuple[int, str]] = None
    for i in range(header_end):
        m = RED_GATE_LINE_RE.match(scan[i])
        if not m:
            continue
        try:
            datetime.date.fromisoformat(m.group(2))
        except ValueError:
            if bad_date is None:
                bad_date = (i + 1, m.group(2))
            continue
        return True, None
    return False, bad_date


def check_building_needs_gate(lines: List[str]) -> List[Dict[str, Any]]:
    """`building` records the human-confirmed act that earned the status: the
    red-gate commit, as its own header line matching ``RED_GATE_LINE_RE``
    exactly — ``Red gate: <sha> <YYYY-MM-DD>``, sha 7-40 hex characters
    (digits alone qualify), date a real calendar date. Error when `Status:`
    is `building` and no line in the header block (everything before the
    first ``## `` heading, fenced lines excluded the way every other scan
    excludes them) matches it. Position among the header lines is not
    enforced, the line's own shape is: a hex-looking run inside some other
    header value (``Supersedes: deadbeef``, a digit-only ``Last decision:``)
    does not satisfy it, nor does a ``Red gate:`` line sitting inside a
    fenced code block (an illustration, not the doc's own header) — only a
    real, unfenced ``Red gate:`` line with a real date does. A line matching
    the sha/date shape but naming a date that does not exist (a day past
    the last of its month) is reported on its own terms, not silently
    treated as no line at all.
    """
    status = get_status(lines)
    if status != "building":
        return []

    found, bad_date = red_gate_line(lines)
    if found:
        return []  # a real, unfenced Red gate line with a real date clears the rule
    if bad_date is not None:
        line_no, date_text = bad_date
        return [
            finding(
                "BUILDING_NEEDS_GATE",
                line_no,
                f"'Red gate:' line found, but {date_text!r} is not a real calendar date",
                "error",
            )
        ]
    return [
        finding(
            "BUILDING_NEEDS_GATE",
            1,
            "arm records the red-gate commit in the header as its own line "
            "'Red gate: <sha> <YYYY-MM-DD>'; none found",
            "error",
        )
    ]


def _indent(line: str) -> int:
    return len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip(" "))


def record_kind(line: str) -> Optional[str]:
    """``filed``, ``kill`` or ``red run`` for a line that reads as one of the record
    lines under §6, decoration and case aside (see RECORD_DECORATION_RE), else None."""
    core = RECORD_DECORATION_RE.sub("", line, count=1)
    if FILED_WORDS_RE.match(core):
        return "filed"
    if KILL_WORDS_RE.match(core):
        return "kill"
    if RED_RUN_WORDS_RE.match(core):
        return "red run"
    return None


def kill_record(lines: List[str]) -> Dict[str, Any]:
    """The kill record under the §6 table, fenced lines excluded. A line counts
    as a record line when it reads as one through any decoration or case
    (``record_kind``); only a plain line in the exact shape, indented fewer
    than four spaces (more renders as code), is well formed.

    - ``filed``: the AT ids every Filed line names, well formed or not, so a
      decorated or malformed Filed line still takes coverage away: anything that
      looks like ``Filed without red run: AT-2, AT-4 — <reason>`` lists its ids
      as not red.
    - ``killed``: the AT id of each well-formed ``Kill: AT-2 — <mutation> →
      <test id> failed; restored, passing at <sha> on <YYYY-MM-DD>`` line with a
      real date. A decorated, indented or malformed Kill line proves nothing.
    - ``named``: (1-based line, AT id) for every id either kind names.
    - ``malformed``: (1-based line, what is wrong) for each bad line."""
    out: Dict[str, Any] = {"filed": [], "killed": [], "named": [], "malformed": []}
    bounds = section_bounds(lines, 6)
    if bounds is None:
        return out
    scan = unfenced(lines)
    filed_lines = 0
    for i in range(bounds[0] + 1, bounds[1]):
        raw = scan[i].rstrip("\r\n")
        kind = record_kind(raw)
        if kind not in ("filed", "kill"):
            continue
        text = raw.strip()
        plain = _indent(raw) < 4 and text.startswith(FILED_PREFIX if kind == "filed" else KILL_PREFIX)
        if kind == "filed":
            filed_lines += 1
            m = FILED_LINE_RE.match(text) if plain else None
            ids = [s.strip() for s in m.group(1).split(",")] if m else AT_ID_ANYWHERE_RE.findall(text)
            out["filed"].extend(ids)
            out["named"].extend((i + 1, at) for at in ids)
            if not plain:
                out["malformed"].append((i + 1, "a 'Filed without red run:' line is written plain, at the start of "
                                                "the line, with no list mark, quote, emphasis or code; its lines "
                                                "count as not red until it is"))
            elif not m:
                out["malformed"].append((i + 1, "a 'Filed without red run:' line reads "
                                                "'Filed without red run: AT-2, AT-4 — <reason>'"))
            elif filed_lines > 1:
                out["malformed"].append((i + 1, "§6 takes one 'Filed without red run:' line; this is another"))
            continue
        m = KILL_LINE_RE.match(text) if plain else None
        date_ok = False
        if m:
            try:
                datetime.date.fromisoformat(m.group(5))
                date_ok = True
            except ValueError:
                pass
        ids = [m.group(1)] if m else AT_ID_ANYWHERE_RE.findall(text)[:1]
        out["named"].extend((i + 1, at) for at in ids)
        if m and date_ok:
            out["killed"].append(m.group(1))
        elif m:
            out["malformed"].append((i + 1, f"the Kill line's date {m.group(5)!r} is not a real calendar date"))
        elif not plain:
            out["malformed"].append((i + 1, "a 'Kill:' line is written plain, at the start of the line, with no "
                                            "list mark, quote, emphasis or code (four spaces of indent render as "
                                            "code); it proves nothing until it is"))
        else:
            out["malformed"].append((i + 1, "a 'Kill:' line reads 'Kill: AT-2 — <the mutation> → <test id> "
                                            "failed; restored, passing at <sha> on <YYYY-MM-DD>': the test, "
                                            "the sha or the date is missing"))
    return out


def record_lines_inside_table(lines: List[str]) -> List[int]:
    """1-based numbers of the record lines (Filed, Kill, Red run) under §6 that sit
    between two rows of a table. The table reads on past them (split_tables), so
    no row is hidden; the line is still out of place."""
    bounds = section_bounds(lines, 6)
    if bounds is None:
        return []
    scan = unfenced(lines)
    out = []
    for i in range(bounds[0] + 1, bounds[1]):
        if not record_kind(scan[i]):
            continue
        before = i - 1
        while before > bounds[0] and record_kind(scan[before]):
            before -= 1
        after = i + 1
        while after < bounds[1] and record_kind(scan[after]):
            after += 1
        if (before > bounds[0] and TABLE_ROW_RE.match(scan[before])
                and after < bounds[1] and TABLE_ROW_RE.match(scan[after])):
            out.append(i + 1)
    return out


def gate_uncovered_rows(lines: List[str]) -> List[Dict[str, Any]]:
    """The §6 lines that no red run and no watched kill covers: a line is
    covered when the doc has a real ``Red gate:`` line and the line is not in
    ``Filed without red run:``, or when a ``Kill:`` line names it. On a
    ``shipped`` doc each line left here must cite a row with ``origin:
    backfill`` and ``verdict: proven`` (outcome-framework.md § Lifecycle):
    the lint reports one with no ``Row`` (``SHIPPED_NEEDS_GATE``) and
    ``bridge_validate.py`` reads each cited row (``SHIPPED_WITHOUT_GATE``)."""
    red = red_gate_line(lines)[0]
    record = kill_record(lines)
    filed, killed = set(record["filed"]), set(record["killed"])
    return [
        r for r in parse_acceptance_rows(lines)
        if not ((red and r["id"] not in filed) or r["id"] in killed)
    ]


def check_kill_record(lines: List[str]) -> List[Dict[str, Any]]:
    """KILL_RECORD_FORMAT (error): a ``Filed without red run:`` or ``Kill:``
    line under §6 that does not have its shape (a Kill line missing the
    test, the sha or a real date; either one decorated, in any case, or
    indented as code), a second Filed line, or a record line (``Red run:``
    too) between two rows of the §6 table. KILL_RECORD_UNKNOWN
    (error): either kind of line names an AT id that is not a §6 line."""
    record = kill_record(lines)
    out = [finding("KILL_RECORD_FORMAT", line_no, why, "error") for line_no, why in record["malformed"]]
    out.extend(
        finding("KILL_RECORD_FORMAT", line_no, "a record line sits between rows of the §6 table; put it under "
                "the table", "error")
        for line_no in record_lines_inside_table(lines)
    )
    known = {r["id"] for r in parse_acceptance_rows(lines)}
    out.extend(
        finding("KILL_RECORD_UNKNOWN", line_no, f"the kill record names {at}, which is not a §6 line", "error")
        for line_no, at in record["named"]
        if at not in known
    )
    return out


def check_shipped_needs_gate(lines: List[str]) -> List[Dict[str, Any]]:
    """SHIPPED_NEEDS_GATE (error): a ``shipped`` doc must carry proof that each
    §6 line was seen to fail (outcome-framework.md § Lifecycle). A line is
    covered when it went red (a real ``Red gate:`` header line, the line not
    in ``Filed without red run:``), when a ``Kill:`` line names it, or when
    it cites a row with ``origin: backfill`` and ``verdict: proven``. The lint
    cannot see the map, so it reports each line no red run or kill covers
    that has no ``Row`` value, and a §6 with no line at all and no red gate;
    ``bridge_validate.py`` checks each cited row (``SHIPPED_WITHOUT_GATE``)."""
    if get_status(lines) != "shipped":
        return []
    red = red_gate_line(lines)[0]
    rows = parse_acceptance_rows(lines)
    why = (
        "needs proof that each §6 line was seen to fail: a red run (a 'Red gate: <sha> <YYYY-MM-DD>' "
        "line, the line not in 'Filed without red run:'), a 'Kill:' line, or a proven backfilled row "
        "in its Row cell"
    )
    if not rows and not red:
        return [finding("SHIPPED_NEEDS_GATE", 1, f"Status: shipped {why}, and §6 has no line", "error")]
    filed = set(kill_record(lines)["filed"])
    out = []
    for r in gate_uncovered_rows(lines):
        if r["row"]:
            continue
        what = ("is filed without a red run, has no 'Kill:' line" if r["id"] in filed
                else "has no red run and no 'Kill:' line")
        out.append(finding("SHIPPED_NEEDS_GATE", r["line"],
                           f"Status: shipped {why}; {r['id']} {what}, and cites no row", "error"))
    return out


# ---------------------------------------------------------------------------
# Decision policy and agent decisions (outcome-framework.md § Decision policy)
# ---------------------------------------------------------------------------

DECISION_POLICIES = ("fast", "auto", "spec")
# A value older docs and configs may still hold: read as exactly ``fast``.
DECISION_POLICY_ALIASES = {"prototype": "fast"}
DECISION_POLICY_RE = re.compile(r"^Decision policy:\s*(.*?)\s*$")
# The categories an agent may decide alone, and the protected ones it never may.
LOCAL_CATEGORIES = ("wording", "naming", "layout", "order", "default", "internal")
PROTECTED_CATEGORIES = (
    "data-retention", "destructive-migration", "money", "legal", "security",
    "contract", "external-effect", "regulated", "third-party",
)
AGENT_OWNER = "agent"
AGENT_FIELDS = ("Category", "Because", "Rollback", "Reversible until", "Review", "State")
AGENT_FIELD_RE = re.compile(r"(?<![\w])(Category|Because|Rollback|Reversible until|Review|State):")
REVIEW_TRIGGER_RE = re.compile(
    r"^(?:before arm|before public release|on (\d{4}-\d{2}-\d{2})|after [1-9]\d* uses?)$", re.IGNORECASE
)
AGENT_STATE_RE = re.compile(r"^(provisional|asked (Q\d+))$")
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# Words that name a protected category. A local agent decision that uses one is a
# warning: the category is the agent's own reading, so a hit means read it again.
PROTECTED_WORDS_RE = re.compile(
    r"\b(retention|retain(?:ed|s)?|delet(?:e|ed|es|ion)|purge[sd]?|migrat(?:e|ed|ion|ions)|billing|"
    r"invoices?|pric(?:e|es|ing)|payments?|refunds?|legal|consent|privacy|passwords?|credentials?|"
    r"tokens?|secrets?|permissions?|access|api|apis|endpoints?|schemas?|webhooks?)\b",
    re.IGNORECASE,
)


def _header_end(scan: List[str]) -> int:
    idx = find_line_index(scan, lambda l: l.startswith("## "))
    return idx if idx is not None else len(scan)


def decision_policy_lines(lines: List[str]) -> List[Tuple[int, str]]:
    """(0-indexed line, value) of every ``Decision policy:`` line in the header
    block (before the first ``## `` heading, fenced lines excluded)."""
    scan = unfenced(lines)
    out = []
    for i in range(_header_end(scan)):
        m = DECISION_POLICY_RE.match(scan[i])
        if m:
            out.append((i, m.group(1)))
    return out


def get_decision_policy(lines: List[str]) -> Optional[str]:
    """The doc's decision policy when its header names a valid one, else None.

    None covers a legacy doc with no line and a line with a value that is not
    one of the three: both behave as ``spec``, the strictest policy, so a
    missing or broken line can only make the agent ask more, never less."""
    found = decision_policy_lines(lines)
    if not found:
        return None
    value = DECISION_POLICY_ALIASES.get(found[0][1], found[0][1])
    return value if value in DECISION_POLICIES else None


def effective_policy(lines: List[str]) -> str:
    return get_decision_policy(lines) or "spec"


def agent_fields(text: str) -> Tuple[Dict[str, str], List[str]]:
    """The labelled fields of an agent decision's Why cell, and any label given
    twice. ``Category: wording. Because: … Rollback: …`` -- each value runs to
    the next label, its trailing ``.`` or ``;`` dropped."""
    marks = list(AGENT_FIELD_RE.finditer(text))
    fields: Dict[str, str] = {}
    twice: List[str] = []
    for n, m in enumerate(marks):
        end = marks[n + 1].start() if n + 1 < len(marks) else len(text)
        value = text[m.end():end].strip().rstrip(".;").strip()
        if m.group(1) in fields:
            twice.append(m.group(1))
        fields[m.group(1)] = value
    return fields, twice


def parse_agent_decisions(lines: List[str]) -> List[Dict[str, Any]]:
    """Every §8 row whose ``Owner`` cell is exactly ``agent``: a decision the agent
    took under the doc's decision policy. Each record: ``line`` (1-based), ``id``,
    ``date``, ``decision``, ``why`` (the raw Why cell), ``fields`` (the labelled
    fields of the Why cell), ``twice`` (labels given twice) and ``state``
    (``provisional``, ``asked Qn``, or whatever the cell says). Tables are read by
    header name, like §6: a §8 table needs ``Decision`` and ``Owner`` columns."""
    bounds = section_bounds(lines, 8)
    if bounds is None:
        return []
    out: List[Dict[str, Any]] = []
    for table in split_tables(lines, bounds[0] + 1, bounds[1]):
        header = [c.strip().lower() for c in table[0][1]]
        if "decision" not in header or "owner" not in header:
            continue
        col = {name: header.index(name) for name in ("#", "date", "decision", "owner", "why") if name in header}
        body = table[1:]
        if body and is_separator(body[0][1]):
            body = body[1:]
        for line_no, cells in body:
            if _cell_at(cells, col.get("owner")).strip().lower() != AGENT_OWNER:
                continue
            why = _cell_at(cells, col.get("why"))
            fields, twice = agent_fields(why)
            out.append({
                "line": line_no,
                "id": _cell_at(cells, col.get("#")).strip(),
                "date": _cell_at(cells, col.get("date")).strip(),
                "decision": _cell_at(cells, col.get("decision")).strip(),
                "why": why,
                "fields": fields,
                "twice": twice,
                "state": fields.get("State", "").strip(),
            })
    return out


def check_decision_policy(lines: List[str]) -> List[Dict[str, Any]]:
    """DECISION_POLICY (error): a ``Decision policy:`` header line holds a value
    other than ``fast``, ``auto`` or ``spec``, or appears twice. The legacy value
    ``prototype`` is read as ``fast`` and draws the warning DECISION_POLICY_ALIAS. A doc with no
    line is a legacy doc and behaves as ``spec``; that is allowed, because the
    missing line is the strictest reading. An angle-bracket value is the
    template's placeholder: PLACEHOLDER reports it (and ``--template`` exempts it)."""
    found = decision_policy_lines(lines)
    out: List[Dict[str, Any]] = []
    if len(found) > 1:
        out.append(finding("DECISION_POLICY", found[1][0] + 1,
                           "more than one 'Decision policy:' line; a doc has one policy", "error"))
    if not found:
        return out
    idx, value = found[0]
    if ANGLE_PLACEHOLDER_RE.fullmatch(value):
        return out
    if value in DECISION_POLICY_ALIASES:
        out.append(finding(
            "DECISION_POLICY_ALIAS", idx + 1,
            f"Decision policy: {value} is read as {DECISION_POLICY_ALIASES[value]}; "
            f"write 'Decision policy: {DECISION_POLICY_ALIASES[value]}' in the doc",
            "warn"))
    elif value not in DECISION_POLICIES:
        out.append(finding(
            "DECISION_POLICY", idx + 1,
            f"Decision policy: {value!r} is not one of fast, auto, spec (the human picks it; "
            "a doc with no line behaves as spec)", "error"))
    return out


def _review_problem(value: str) -> Optional[str]:
    m = REVIEW_TRIGGER_RE.match(value.strip())
    if not m:
        return (f"review trigger {value!r} is not concrete: write 'before arm', 'before public release', "
                "'on YYYY-MM-DD' or 'after N uses'")
    if m.group(1):
        try:
            datetime.date.fromisoformat(m.group(1))
        except ValueError:
            return f"review trigger {value!r} names a date that does not exist"
    return None


def check_agent_decisions(lines: List[str]) -> List[Dict[str, Any]]:
    """The agent decisions in §8 (rows whose Owner is ``agent``):

    - AGENT_DECISION_FIELDS (error): a row lacks one of Category, Because, Rollback,
      Reversible until, Review and State, gives one twice or empty, has no real date,
      names a category outside the framework's lists, a review trigger that is not
      concrete, a state other than ``provisional`` or ``asked Qn``, or an ``asked Qn``
      whose question is not in §9.
    - AGENT_DECISION_PROTECTED (error): a ``provisional`` row declares a protected
      category. The agent never decides those alone at any policy; promoting the row
      to a §9 question (``asked Qn``) is the fix.
    - AGENT_DECISION_UNRATIFIED (error): a ``provisional`` row under ``spec``, or on a
      doc with no valid policy line (which behaves as ``spec``): under spec the human
      decides every product decision.
    - AGENT_DECISION_WORDS (warn): a ``provisional`` row in a local category whose
      decision or reason uses a word of a protected category (``API``, ``retention``,
      ``billing``…). The category is the agent's own reading; the script cannot prove
      it honest, so a hit means read it again, and ask when in doubt."""
    rows = parse_agent_decisions(lines)
    if not rows:
        return []
    policy = effective_policy(lines)
    questions = {q["q"] for q in parse_questions(lines)}
    out: List[Dict[str, Any]] = []
    for r in rows:
        name = f"agent decision {r['id'] or '(no id)'}"
        problems: List[str] = []
        missing = [k for k in AGENT_FIELDS if not r["fields"].get(k)]
        if missing:
            problems.append("no " + ", ".join(f"{k}:" for k in missing)
                            + " (every agent decision records " + ", ".join(AGENT_FIELDS) + ")")
        if r["twice"]:
            problems.append("gives " + ", ".join(f"{k}:" for k in r["twice"]) + " twice")
        if not ISO_DATE_RE.match(r["date"]) or not _is_real_date(r["date"]):
            problems.append(f"date {r['date']!r} is not a real YYYY-MM-DD date")
        category = r["fields"].get("Category", "").strip().lower()
        if category and category not in LOCAL_CATEGORIES + PROTECTED_CATEGORIES:
            problems.append(
                f"category {category!r} is not one the framework knows ({', '.join(LOCAL_CATEGORIES)}; "
                "or a protected one); a choice that fits none of the local ones is not the agent's to take: ask")
        if r["fields"].get("Review"):
            p = _review_problem(r["fields"]["Review"])
            if p:
                problems.append(p)
        state_m = AGENT_STATE_RE.match(r["state"]) if r["state"] else None
        if r["state"] and not state_m:
            problems.append(f"state {r['state']!r} is not 'provisional' or 'asked Qn'")
        elif state_m and state_m.group(2) and state_m.group(2) not in questions:
            problems.append(f"state says {r['state']!r}, but §9 has no {state_m.group(2)}")
        for p in problems:
            out.append(finding("AGENT_DECISION_FIELDS", r["line"], f"{name}: {p}", "error"))
        if r["state"] != "provisional":
            continue
        if category in PROTECTED_CATEGORIES:
            out.append(finding(
                "AGENT_DECISION_PROTECTED", r["line"],
                f"{name} declares the protected category {category!r}; the agent never decides one alone, "
                "at any policy: promote it to a §9 question (decisions.py promote)", "error"))
            continue
        if policy == "spec":
            out.append(finding(
                "AGENT_DECISION_UNRATIFIED", r["line"],
                f"{name} is provisional under "
                + ("Decision policy: spec" if get_decision_policy(lines) else "no valid Decision policy line (read as spec)")
                + "; under spec the human decides: promote it to a §9 question (decisions.py promote)", "error"))
        words = sorted({m.group(1).lower() for m in PROTECTED_WORDS_RE.finditer(
            f"{r['decision']} {r['fields'].get('Because', '')}")})
        if category in LOCAL_CATEGORIES and words:
            out.append(finding(
                "AGENT_DECISION_WORDS", r["line"],
                f"{name} is filed as {category!r} but uses {', '.join(repr(w) for w in words)}, a word of a "
                "protected category; read it again, and ask when in doubt", "warn"))
    return out


def _is_real_date(text: str) -> bool:
    try:
        datetime.date.fromisoformat(text)
        return True
    except ValueError:
        return False


def _agent_notes_bounds(lines: List[str]) -> Optional[Tuple[int, int]]:
    """0-indexed [start, end) from the Agent notes line up to ``## 1.``."""
    scan = unfenced(lines)
    idx = find_line_index(scan, lambda l: l.startswith(AGENT_NOTES_PREFIX))
    if idx is None:
        return None
    end = find_line_index(scan, lambda l: l.startswith("## 1."), start=idx + 1)
    return idx, end if end is not None else len(lines)


def check_placeholder(lines: List[str], template: bool = False) -> List[Dict[str, Any]]:
    """TBD/TODO-style terms in §0, plus angle-bracket ``<...>`` placeholders
    in §0, the header ``Owner:``/``Last decision:`` values, §6 data cells,
    agent notes, the first line of each §3 worked example, a §9 question's
    owner, and the value of each §4-§7 Why line. The scans are scoped on
    purpose: §5's body may legitimately hold generics such as
    ``Map<string, Row>``, so no whole-document scan is made.

    Every scan reads its text with code spans blanked (``strip_code_spans``):
    ``mute <id>`` in backticks is a command's argument, not a slot; a bare
    ``<one line>`` beside it still is.

    ``template=True`` exempts angle-bracket placeholders and the literal
    ``YYYY-MM-DD`` (the bundled template's own placeholder shapes) so the
    template can be linted in template mode; the TBD/TODO-style terms stay
    active either way.
    """
    out: List[Dict[str, Any]] = []
    seen_terms = set()
    scan = [strip_code_spans(line) for line in unfenced(lines)]

    bounds = tldr_block_bounds(lines)
    if bounds is not None:
        start, end = bounds
        for i in range(start, end):
            lowered = scan[i].lower()
            for term in PLACEHOLDER_TERMS:
                if term in lowered and term not in seen_terms:
                    seen_terms.add(term)
                    out.append(finding("PLACEHOLDER", i + 1, f"placeholder text {term!r} found in §0", "error"))
            if not template:
                for m in ANGLE_PLACEHOLDER_RE.finditer(scan[i]):
                    out.append(
                        finding("PLACEHOLDER", i + 1, f"placeholder {m.group(0)!r} found in §0", "error")
                    )

    if template:
        return out

    owner_idx = find_line_index(scan, lambda l: "Owner:" in l)
    if owner_idx is not None:
        value = strip_code_spans(parse_header_field_value(scan, owner_idx, "Owner:", "Last decision:"))
        for m in ANGLE_PLACEHOLDER_RE.finditer(value):
            out.append(
                finding(
                    "PLACEHOLDER",
                    owner_idx + 1,
                    f"placeholder {m.group(0)!r} found in the header 'Owner:' value",
                    "error",
                )
            )

    last_decision_idx = find_line_index(scan, lambda l: "Last decision:" in l)
    if last_decision_idx is not None:
        value = parse_header_field_value(scan, last_decision_idx, "Last decision:")
        for m in ANGLE_PLACEHOLDER_RE.finditer(value):
            out.append(
                finding(
                    "PLACEHOLDER",
                    last_decision_idx + 1,
                    f"placeholder {m.group(0)!r} found in the header 'Last decision:' value",
                    "error",
                )
            )
        if value == TEMPLATE_DATE_PLACEHOLDER:
            out.append(
                finding(
                    "PLACEHOLDER",
                    last_decision_idx + 1,
                    f"placeholder {TEMPLATE_DATE_PLACEHOLDER!r} found in the header 'Last decision:' value",
                    "error",
                )
            )

    for idx, value in decision_policy_lines(lines)[:1]:
        if ANGLE_PLACEHOLDER_RE.search(value):
            out.append(
                finding(
                    "PLACEHOLDER",
                    idx + 1,
                    f"placeholder {value!r} found in the header 'Decision policy:' value "
                    "(ask the human: fast, auto or spec)",
                    "error",
                )
            )

    bounds6 = section_bounds(lines, 6)
    if bounds6 is not None:
        start6, end6 = bounds6
        for line_no, cells in parse_table_data_rows(lines, start6 + 1, end6):
            for cell in cells:
                for m in ANGLE_PLACEHOLDER_RE.finditer(strip_code_spans(cell)):
                    out.append(
                        finding(
                            "PLACEHOLDER",
                            line_no,
                            f"placeholder {m.group(0)!r} found in a §6 data cell",
                            "error",
                        )
                    )

    notes = _agent_notes_bounds(lines)
    if notes is not None:
        for i in range(notes[0] + 1, notes[1]):
            if not NOTE_START_RE.match(scan[i]):
                continue
            for m in ANGLE_PLACEHOLDER_RE.finditer(scan[i]):
                out.append(
                    finding("PLACEHOLDER", i + 1, f"placeholder {m.group(0)!r} found in an agent note", "error")
                )

    ranges, _kind = worked_examples(lines)
    for s, _e in ranges:
        for m in ANGLE_PLACEHOLDER_RE.finditer(scan[s]):
            out.append(
                finding("PLACEHOLDER", s + 1, f"placeholder {m.group(0)!r} found in a §3 worked example", "error")
            )

    bounds9 = section_bounds(lines, 9)
    if bounds9 is not None:
        for i in range(bounds9[0] + 1, bounds9[1]):
            m = OPEN_QUESTION_OWNER_RE.match(scan[i])
            if m:
                out.append(
                    finding("PLACEHOLDER", i + 1, f"placeholder {m.group(1)!r} found in a §9 owner", "error")
                )

    for n in WHY_SECTIONS:
        for i, value in _why_lines(lines, n):
            for m in ANGLE_PLACEHOLDER_RE.finditer(strip_code_spans(value)):
                out.append(
                    finding("PLACEHOLDER", i + 1, f"placeholder {m.group(0)!r} found in a §{n} Why line", "error")
                )
    return out


def check_agent_notes_many(lines: List[str]) -> List[Dict[str, Any]]:
    notes = _agent_notes_bounds(lines)
    if notes is None:
        return []
    idx, end = notes
    scan = unfenced(lines)
    count = sum(1 for i in range(idx + 1, end) if NOTE_START_RE.match(scan[i]))
    if count > 8:
        return [
            finding(
                "AGENT_NOTES_MANY",
                idx + 1,
                f"§0 has {count} agent notes (consolidate past 8)",
                "warn",
            )
        ]
    return []


def check_human_half_budget(lines: List[str]) -> List[Dict[str, Any]]:
    tldr_bounds = tldr_block_bounds(lines)
    if tldr_bounds is None:
        return []
    start = tldr_bounds[0]
    section2 = section_bounds(lines, 2)
    if section2 is None:
        return []
    _, end_of_2 = section2
    ranges, kind = worked_examples(lines)
    if kind is None:
        end = end_of_2
        measured_note = "§3 not measured (no parseable example found)"
    else:
        end = ranges[0][1]
        measured_note = "through the first §3 example"
    count = end - start
    if count > 150:
        return [
            finding(
                "HUMAN_HALF_BUDGET",
                start + 1,
                f"human half is {count} lines (max 150), {measured_note}",
                "warn",
            )
        ]
    return []


PREMISE_HEADER_FIRST_CELL_RE = re.compile(r"^premise$", re.IGNORECASE)

# The heuristic's phrase list -- outcome-framework.md § Section rules and
# § The framework as a review rubric name these six shapes: a flat "can't" /
# "cannot", the two spellings of "doesn't have" (ASCII and curly apostrophe,
# the same tolerance HOW_WE_KNOW_RE gives "how we'll know"), "no way to",
# "unavailable", and the "only X has" shape (bounded to a handful of words so
# it does not run past the end of its own clause). This is text-matching on
# WORDING, not an understanding of the sentence, so it is a warning a human
# judges -- never an error the lint enforces alone.
NEGATIVE_PREMISE_PATTERNS: Tuple[Pattern[str], ...] = (
    re.compile(r"\bcan['’]t\b", re.IGNORECASE),
    re.compile(r"\bcannot\b", re.IGNORECASE),
    re.compile(r"\bdoes(?:n['’]t| not)\s+have\b", re.IGNORECASE),
    re.compile(r"\bno way to\b", re.IGNORECASE),
    re.compile(r"\bunavailable\b", re.IGNORECASE),
    re.compile(r"\bonly\b(?:\s+\S+){1,6}?\s+has\b", re.IGNORECASE),
)

# The suppression idiom: an HTML comment, the same "invisible in the
# rendered doc, ignored by every structural scan" device the template
# already uses for the Red gate line and that THIN_PENDING's HTML_COMMENT_RE
# already treats as non-content. Anywhere on the line, so it reads as a
# trailing annotation on the sentence it excuses.
NOT_A_PREMISE_RE = re.compile(r"<!--\s*not a premise\b[^>]*-->", re.IGNORECASE)


def find_premise_tables(
    lines: List[str], start: int, end: int
) -> List[Tuple[int, List[str], List[Tuple[int, List[str]]], Optional[Dict[str, int]], set]]:
    """Every Load-bearing premises table in [start, end): a table whose
    header's first cell (case-insensitive, trimmed) reads exactly
    ``Premise``, the same first-cell-led detection ``find_acceptance_tables``
    uses for ``#``/``ID``/``AT``. Returns (header_line, header_cells,
    data_rows, column_map_or_None, table_lines) per table -- column_map maps
    ``evidence`` and ``existing_join`` to a 0-based cell index only when the
    header names both (by name, case-insensitive, trimmed -- the same
    lookup ``acceptance_column_map`` uses, so an extra column or a
    reordered one never shifts what a cell means); ``table_lines`` is every
    line number the table occupies (header, separator and data rows alike),
    for the phrase scan to exclude wholesale.
    """
    found = []
    for table in split_tables(lines, start, end):
        header_line, header_cells = table[0]
        if not header_cells or not PREMISE_HEADER_FIRST_CELL_RE.match(header_cells[0].strip()):
            continue
        by_name: Dict[str, int] = {}
        for i, cell in enumerate(header_cells):
            key = cell.strip().lower()
            if key and key not in by_name:
                by_name[key] = i
        column_map = None
        if "evidence" in by_name and "existing join searched" in by_name:
            column_map = {"evidence": by_name["evidence"], "existing_join": by_name["existing join searched"]}
        body = table[1:]
        if body and is_separator(body[0][1]):
            body = body[1:]
        table_lines = {line_no for line_no, _cells in table}
        found.append((header_line, header_cells, body, column_map, table_lines))
    return found


def check_load_bearing_premises(lines: List[str]) -> List[Dict[str, Any]]:
    """PREMISE_TABLE (error): a §5 Load-bearing premises table -- required
    whenever the design depends on something being impossible, absent, or
    available in only one place (outcome-framework.md § Section rules) --
    has a data row with an empty Evidence or Existing join searched cell.
    A header that names neither column is reported once, at the header, as
    a malformed table (never guessed at by position, the same rule
    ACCEPTANCE_TABLE follows for §6). No table at all is not itself a
    finding here -- whether one is required is a judgement call the lint
    cannot make; CHECK_PREMISE_PHRASES flags the unlisted claims that would
    justify one."""
    bounds = section_bounds(lines, 5)
    if bounds is None:
        return []
    start, end = bounds
    out: List[Dict[str, Any]] = []
    for header_line, _header_cells, body, column_map, _table_lines in find_premise_tables(
        lines, start + 1, end
    ):
        if column_map is None:
            out.append(
                finding(
                    "PREMISE_TABLE",
                    header_line,
                    "Load-bearing premises table must name both an Evidence and an "
                    "Existing join searched column",
                    "error",
                )
            )
            continue
        for line_no, cells in body:
            missing = []
            if not _cell_at(cells, column_map["evidence"]).strip():
                missing.append("Evidence")
            if not _cell_at(cells, column_map["existing_join"]).strip():
                missing.append("Existing join searched")
            if missing:
                out.append(
                    finding(
                        "PREMISE_TABLE",
                        line_no,
                        "premises table row is missing " + " and ".join(missing)
                        + " (a load-bearing premise needs both, or it is not verified — "
                        "framework § Section rules)",
                        "error",
                    )
                )
    return out


PREMISE_TEXT_STRIP_RE = re.compile(r"[`*_]")
PREMISE_TEXT_TRAILING_RE = re.compile(r"[\s.:;,—-]+$")


def _normalize_premise_text(text: str) -> str:
    """``text`` lower-cased, with markdown emphasis/code markers removed,
    whitespace collapsed, and trailing punctuation trimmed -- enough to
    recognise a claim quoted or closely restated word-for-word into a
    Premise cell, and nothing more. This is a literal overlap check, not
    a semantic one: two different words for the same fact do not match,
    and that is by design (see CHECK_PREMISE_PHRASES)."""
    text = PREMISE_TEXT_STRIP_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = PREMISE_TEXT_TRAILING_RE.sub("", text)
    return text.lower()


def _covered_premise_texts(lines: List[str]) -> List[str]:
    """Normalized Premise-cell text of every COMPLETE row in every §5
    Load-bearing premises table -- complete meaning its own Evidence and
    Existing join searched cells are both non-empty. An incomplete row
    already gets its own PREMISE_TABLE finding, so it does not also buy
    phrase coverage: that would let a garbage row silence the warning it
    exists to raise. The Premise cell is always the table's first column
    (find_premise_tables requires it, the same positional rule
    ACCEPTANCE_TABLE's id column follows)."""
    bounds = section_bounds(lines, 5)
    if bounds is None:
        return []
    start, end = bounds
    covered = []
    for _hl, _hc, body, column_map, _table_lines in find_premise_tables(lines, start + 1, end):
        if column_map is None:
            continue
        for _line_no, cells in body:
            evidence = _cell_at(cells, column_map["evidence"]).strip()
            existing_join = _cell_at(cells, column_map["existing_join"]).strip()
            if not evidence or not existing_join:
                continue
            premise_text = _cell_at(cells, 0).strip()
            if premise_text:
                covered.append(_normalize_premise_text(premise_text))
    return covered


def check_premise_phrases(lines: List[str]) -> List[Dict[str, Any]]:
    """PREMISE_PHRASE (warn): a negative, design-constraining claim
    ('can't', 'cannot', "doesn't have"/"does not have", 'no way to',
    'unavailable', 'only X has') in §1 Problem or §5 Mechanism -- the two
    sections that state a current, real-world fact (outcome-framework.md
    § Section rules) -- outside a §5 Load-bearing premises table.

    §1 is in scope because that is where this kind of claim is usually
    first written down: a Problem statement citing what a source does or
    does not return is exactly the shape of claim the table exists to
    check, and by the time §5 is drafted the claim may already read as
    settled fact. The table itself always lives in §5 (framework § Section
    rules); a §1 claim is listed there too, not in a second table.

    A flagged line is cleared two ways: an ``<!-- not a premise -->``
    marker on its own line (checked first), or a COMPLETE premises row
    (PREMISE_TABLE's own terms: Evidence and Existing join searched both
    non-empty) whose Premise cell and the flagged line overlap literally
    after normalization -- one contains the other, case-insensitive,
    markdown emphasis and trailing punctuation ignored. This is a
    literal-text check, not a semantic one, so a claim RESTATED in
    different words is not recognised as covered: the practical fix for
    either miss is the same, and both are named in the message -- quote
    or closely restate the claim into its row, or mark the line
    ``<!-- not a premise -->`` if it genuinely is not one. One finding
    per line (its first matching phrase), so one sentence with two hits
    does not double-report. A phrase inside a recognised premises table
    (qualifying or not -- CHECK_LOAD_BEARING_PREMISES already has that
    one's own finding) is the claim the table exists to carry, not a
    violation of it, so those lines are excluded outright. This is a
    wording heuristic, not a reading of the sentence, so it is a warning
    a reviewer judges -- never an error the lint enforces alone:
    references/anti-rationalizations.md, "the citation is correct, so the
    conclusion is."."""
    bounds5 = section_bounds(lines, 5)
    scan = unfenced(lines)
    excluded_lines: set = set()
    if bounds5 is not None:
        start5, end5 = bounds5
        for _hl, _hc, _body, _cm, table_lines in find_premise_tables(lines, start5 + 1, end5):
            excluded_lines |= table_lines
    covered = [p for p in _covered_premise_texts(lines) if p]
    out: List[Dict[str, Any]] = []
    for section_no in (1, 5):
        bounds = section_bounds(lines, section_no)
        if bounds is None:
            continue
        start, end = bounds
        for i in range(start + 1, end):
            line_no = i + 1
            if line_no in excluded_lines:
                continue
            text = scan[i]
            if not text.strip() or NOT_A_PREMISE_RE.search(text):
                continue
            for pattern in NEGATIVE_PREMISE_PATTERNS:
                m = pattern.search(text)
                if not m:
                    continue
                normalized_line = _normalize_premise_text(text)
                if normalized_line and any(
                    normalized_line in p or p in normalized_line for p in covered
                ):
                    break  # a complete row already carries this claim
                out.append(
                    finding(
                        "PREMISE_PHRASE",
                        line_no,
                        f"negative claim ({m.group(0)!r}) in §{section_no} outside a "
                        "Load-bearing premises table -- quote or closely restate it as "
                        "a Premise / Evidence / Existing join searched / "
                        "What-would-make-it-false row in §5, or mark the line "
                        "`<!-- not a premise -->` if it genuinely is not one",
                        "warn",
                    )
                )
                break
    return out


def check_unclosed_fence(lines: List[str]) -> List[Dict[str, Any]]:
    """FENCE_UNCLOSED (error): a ``` / ~~~ fence opened and never closed.

    Every line after such a fence is read as an illustration by every
    other rule, so the doc would otherwise report a wall of "missing
    heading" findings at line 1 and nothing naming the fence. Reported at
    the opening fence's own line."""
    in_fence = False
    open_line: Optional[int] = None
    for i, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            open_line = i + 1 if in_fence else None
    if in_fence and open_line is not None:
        return [
            finding(
                "FENCE_UNCLOSED",
                open_line,
                "fenced code block opened here is never closed, so every line after it "
                "is read as an illustration (no heading, field, table row or placeholder counts)",
                "error",
            )
        ]
    return []


RULE_CHECKS = (
    check_unclosed_fence,
    check_header_status,
    check_thin_draft,
    check_header_owner,
    check_contents_line,
    check_headings_bare,
    check_tldr_budget,
    check_tldr_fields,
    check_rules_present,
    check_rules_format,
    check_rules_tagged,
    check_tags_resolve,
    check_at_ids_unique,
    check_acceptance_table,
    check_acceptance_altitude,
    check_scenarios_count,
    check_why_line,
    check_untested_on_agreed,
    check_pending_on_agreed,
    check_open_on_agreed,
    check_blocking_open_on_agreed,
    check_building_needs_gate,
    check_shipped_needs_gate,
    check_kill_record,
    check_decision_policy,
    check_agent_decisions,
    check_load_bearing_premises,
    check_premise_phrases,
    check_agent_notes_many,
    check_human_half_budget,
)


def lint_lines(lines: List[str], strict: bool, template: bool = False) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for check in RULE_CHECKS:
        findings.extend(check(lines))
    findings.extend(check_placeholder(lines, template))
    if strict:
        for f in findings:
            if f["severity"] == "warn":
                f["severity"] = "error"
    findings.sort(key=lambda f: (f["line"] if f["line"] is not None else 0, f["rule"]))
    return findings


def lint_file(path: str, strict: bool, template: bool = False) -> Dict[str, Any]:
    try:
        text = read_text_tolerant(path)
    except (OSError, UnicodeDecodeError) as exc:
        findings = [finding("UNREADABLE", None, f"cannot read {path}: {exc}", "error")]
        return {"path": path, "findings": findings, "stats": {"errors": 1, "warnings": 0, "total": 1}}
    lines = text.splitlines()
    findings = lint_lines(lines, strict, template)
    errors = sum(1 for f in findings if f["severity"] == "error")
    warns = sum(1 for f in findings if f["severity"] == "warn")
    return {
        "path": path,
        "findings": findings,
        "stats": {"errors": errors, "warnings": warns, "total": len(findings)},
    }


def contains_tldr(path: str) -> bool:
    """True when ``path`` is UTF-8 text containing the §0 TLDR heading
    outside any fenced code block (a framework or how-to that only shows
    the heading inside a fence is not an outcome doc).

    A file that cannot be read or decoded also counts as True: a directory
    scan surfaces a broken doc as an UNREADABLE finding (via ``lint_file``)
    rather than silently excluding it from the scan.
    """
    try:
        text = read_text_tolerant(path)
    except (OSError, UnicodeDecodeError):
        return True
    return any(line.startswith(TLDR_HEADING) for line in unfenced(text.splitlines()))


def collect_directory_docs(root: str) -> List[str]:
    """Every *.md under root containing a §0 TLDR heading, one level of recursion deep."""
    found = []
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        if os.path.isfile(full) and name.endswith(".md") and contains_tldr(full):
            found.append(full)
        elif os.path.isdir(full):
            for name2 in sorted(os.listdir(full)):
                full2 = os.path.join(full, name2)
                if os.path.isfile(full2) and name2.endswith(".md") and contains_tldr(full2):
                    found.append(full2)
    return found


def format_human(results: List[Dict[str, Any]]) -> str:
    lines_out = []
    for result in results:
        for f in result["findings"]:
            line_part = f["line"] if f["line"] is not None else "?"
            tail = " (warning)" if f["severity"] == "warn" else ""
            lines_out.append(f"{result['path']}:{line_part}: {f['rule']} {f['message']}{tail}")
    return "\n".join(lines_out)


def summary_line(results: List[Dict[str, Any]]) -> str:
    """The last line of a human run, so a clean run is not silent: docs, errors, warnings."""
    errors = sum(1 for r in results for f in r["findings"] if f["severity"] == "error")
    warns = sum(1 for r in results for f in r["findings"] if f["severity"] == "warn")
    docs = len(results)
    return (f"lint_outcome.py: {docs} doc{'s' if docs != 1 else ''}, "
            f"{errors} error{'s' if errors != 1 else ''}, {warns} warning{'s' if warns != 1 else ''}")


def main(argv: Optional[List[str]] = None) -> int:
    # Findings carry '§', '→' and '—'. A console that cannot encode them
    # (a cp1252 pipe on Windows, a C locale) prints '?' in their place
    # rather than dying with UnicodeEncodeError and no findings at all.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    parser = argparse.ArgumentParser(
        prog="lint_outcome.py",
        description="Check an outcome doc (or a directory of them) against the framework shape.",
    )
    parser.add_argument("path", help="a doc.md, or a directory to scan one level deep")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    parser.add_argument("--no-summary", action="store_true",
                        help="leave out the last line's doc, error and warning counts (check.py prints its own)")
    parser.add_argument("--strict", action="store_true", help="promote warn findings to error")
    parser.add_argument(
        "--template",
        action="store_true",
        help="exempt angle-bracket and literal YYYY-MM-DD placeholders, for linting the bundled template",
    )
    args = parser.parse_args(argv)

    if not os.path.exists(args.path):
        print(f"lint_outcome.py: no such file or directory: {args.path}", file=sys.stderr)
        return 2

    if os.path.isdir(args.path):
        doc_paths = collect_directory_docs(args.path)
    elif os.path.isfile(args.path):
        doc_paths = [args.path]
    else:
        print(f"lint_outcome.py: not a file or directory: {args.path}", file=sys.stderr)
        return 2

    # Every path is read inside lint_file, which turns an unreadable file or
    # a decoding failure into an UNREADABLE finding rather than raising, so
    # nothing here needs to guard against that.
    results = [lint_file(p, args.strict, args.template) for p in doc_paths]

    # Exit 1 only for error-severity findings. --strict has already
    # promoted warn to error in place (inside lint_lines) by this point,
    # so a plain warning that was never promoted does not fail the run.
    any_errors = any(f["severity"] == "error" for r in results for f in r["findings"])

    if args.json:
        payload = results[0] if os.path.isfile(args.path) else results
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        text = format_human(results)
        if text:
            print(text)
        if not args.no_summary:
            print(summary_line(results))

    return 1 if any_errors else 0


if __name__ == "__main__":
    sys.exit(main())
