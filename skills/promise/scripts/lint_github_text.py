#!/usr/bin/env python3
"""Lint the part of an issue or a pull request body that `/promise` writes.

    python3 lint_github_text.py --kind issue body.md
    python3 lint_github_text.py --kind pr body.md --changed changed.json
    gh pr view 12 --json body -q .body | python3 lint_github_text.py --kind pr -
    python3 lint_github_text.py --kind issue body.md --counts
    python3 lint_github_text.py --kind doc docs/review/gaps.md

A reviewer reads a pull request from the issue it closes, to the capabilities
it changes, to the code that delivers them. The text that carries them is
short on purpose: a reviewer who meets a wall of text asks a model to read it,
and then no person has reviewed the change. `references/github-text.md` gives
the shape and the plain-words rules; this script checks the parts a script
can check.

Only the block between ``<!-- promise:issue -->`` and ``<!-- /promise:issue -->``
(or ``promise:pr``) is checked, and in an issue the ``<!-- promise:intro -->``
block at the top of the body. Text outside them is the person's own. HTML
comments and ``<details>`` blocks inside them are left out of every count.

The first screen -- the intro block of an issue, the first two sections of a
pull request -- tells a reader who comes back after days, from other work,
where in the product this is and what its words mean
(``references/first-screen.md``): "Where this is" lists the features, one
``- **Name**: <plain sentence>`` each, and a ``**Needed from you:**`` line;
"Words" explains the product's own words, one ``- **Term**: <meaning>``
each (nested items for the variants of one term), or says "None.".

Rule ids (severity):

- ``NO_BLOCK`` (error): the markers are missing, repeated or out of order.
  Markers inside a code fence do not count.
- ``MISSING_SECTION`` / ``EMPTY_SECTION`` (error): a required ``##`` heading is
  not in the block, or has no text under it. A pull request block with
  neither first-screen section is ``NO_INTRO`` instead.
- ``PLACEHOLDER`` (error): template text is still there (``<issue>``,
  ``<why>``, ``CAP-n``, ``path:line`` as written in the template). Inline
  code, autolinks and email addresses are not template text.
- ``TOO_LONG`` (error): the block shows more words than its budget outside
  ``<details>`` (450 in an issue, 250 in a pull request; a link counts as its
  text, and the template's headings do not count); or, in a pull request,
  "What changes for people" is over 60 words or 3 sentences.
- ``SENTENCE_TOO_LONG``: a sentence over 20 words in "What changes for
  people" (error), or over 25 words in a prose section (warn). ASD-STE100
  keeps procedure sentences to 20 words and descriptive ones to 25. A path,
  a code span or a link counts as one word.
- ``CODE_WORDS`` (error): "What changes for people" names code -- a
  backtick, a path, a file name, a route, a snake_case or camelCase word, or
  a row id. Code belongs in "Check these first".
- ``NO_LINK`` (error, pr): "Why" names no issue (``#12``, ``owner/repo#12``, an
  issue URL, or a tracker key after "Closes") and does not say "No issue".
- ``SIZE_ALIAS`` (warn, pr): the ``Size:`` line says ``feature``, the alias of
  ``capability``; it is read as ``capability``. Write ``capability``.
- ``SIZE`` (pr): the ``Size:`` line under "Why" ("Size: tiny — keeps CAP-12")
  does not start with tiny, small, capability, risky or deferred, or there is more than
  one, or a deferred line does not say what it ``owes:`` (error); there is none
  (warn). ``changed_rows.py --body`` checks a tiny claim against the diff. A deferred
  block (built first, ``references/sizing.md`` § Deferred) needs only "Why" and "Proof":
  a missing or empty section besides those, and the first screen, are warnings.
- ``CHECK_ITEMS`` (error, pr): "Check these first" has no item, more than
  three, or an item with no ``path:line`` (or a permalink to a line).
- ``RELATION`` (error, issue): an item in "Capability check" does not start
  with its relation (EXISTING-SCENARIO, DEFECT, EXTEND, NEW-ROW, SURFACE,
  DECISION, KEEPS) after its bold lead.
- ``READ_LINE`` (warn, issue): "Capability check" does not start with its
  ``Read:`` line.
- ``NO_ROUTE`` (error, issue): "How to build it" names no ``/promise`` step
  and does not say "Nothing to build"; or it says only "Nothing to build"
  while an ask is DEFECT, EXTEND, NEW-ROW or KEEPS.
- ``DECISIONS`` (issue): an ask is DECISION but "Decisions needed" says
  "None." (error); an open decision names no owner (warn). A ticked one
  (``- [x]``) is answered and needs none.
- ``ROW_UNKNOWN`` (error): a row id in the block, ``<details>`` included, is
  not in the map (rows a change removed, given by ``--changed``, count as
  known).
- ``VERDICT_WRONG`` (error): a verdict written beside a row id, as in
  ``CAP-12 (proven)`` or ``CAP-12 S2 (proven)``, is not the row's verdict in
  the map. ``<details>`` included.
- ``ID_RANGE`` (error): a range of row ids, "CAP-4 to CAP-9" or "CAP-4–CAP-9" (or
  "CAP-4–9"): it hides what each row means, so name each one. The second id is higher, of
  the same prefix; "moved from CAP-3 to CAP-4" is a change of id, not a range. Ids in
  links' targets, URLs, paths and ``<details>`` are exempt.
- ``ID_BARE`` (warn): a row id with no meaning beside it. A comma, a colon, a dash, a
  bracket or a middle dot followed by words gives one ("CAP-12, the saved card"); so does words
  before it, then the id in brackets or after a dash; so do the row's own title words a few words
  away. A tracker key after "Closes", ids in code, table rows, the "Touched, verdicts
  unchanged:" line and ``<details>`` are exempt.
- ``ROW_MISSING`` (pr, with ``--changed``): a row the change added, changed,
  removed (error) or touched (warn) is not named in the block. When more
  than 12 rows share a change, "Capabilities" may give their count instead
  ("192 rows added").
- ``UNHOMED`` (warn, pr, with ``--changed``): the change touched files no
  row names, and "Capabilities" does not say so.
- ``NO_INTRO``: there is no first screen. In an issue, the
  ``<!-- promise:intro -->`` block is missing (warn), or its markers are
  repeated or out of order (error). In a pull request, the block has
  neither "Where this is" nor "Words" (warn; one of the two alone is
  ``MISSING_SECTION``). A warning, so text written before the first screen
  still passes; ``/promise issue`` and ``/promise pr`` always write one.
  With no first screen, the rules below do not run. ``INTRO_FIRST`` (warn):
  text comes before the intro block; it opens the body.
- ``AREAS`` (error): "Where this is" lists no feature, or an item that is not
  ``- **Name**: <plain sentence>``; more than five features (warn). Past five,
  the rest go on one line, ``Also: **Name**, **Name**.``: they count for
  the feature rules below, not for the five, and explain only their own name, when the map's
  ``features`` hold it (the map's word for it). Code words in a feature's sentence
  are ``CODE_WORDS`` (error). The rule id keeps its name.
- ``NEEDED`` (warn): "Where this is" has no ``**Needed from you:**`` line.
- ``WORDS`` (error): "Words" neither says "None." nor explains each term as
  ``- **Term**: <meaning>``.
- ``TOO_LONG`` (error) also covers the first screen: 180 words at most, not
  counted in the block's own budget.
- ``AREA_UNKNOWN`` (warn, with the map's ``features``): a feature is not a name or
  id in the map, and its sentence does not say it is "not yet in the map".
- ``AREA_MISSING`` (warn, with the map's ``features``): a row the block names, or
  a row the change moved (``--changed``), belongs to a feature the first
  screen does not name.
- ``FEATURE_AND_AREA`` (error): the map has both ``features`` and ``areas``, or
  a row has both ``feature`` and ``area``. The alias spellings ``areas`` and
  ``area`` mean the same as the new ones, but a map uses one.
- ``TERM_UNDEFINED`` (warn, with the map's ``glossary``): a glossary term or
  one of its aliases is in the text a reader sees (in an issue, the whole
  body) but "Words" does not explain it. A term in "Words", or a feature's
  name, covers the glossary words it starts with, singular or plural: the
  feature's sentence explains it. Code spans, paths, URLs and file names are
  not read for terms.

- ``SIBLING_UNREAD`` (warn): the config says ``"map": false`` with a ``sibling``, and no
  checkout with a readable map is at ``sibling.path``, so no row was checked. With a checkout there, the rules
  above read the sibling's map, as they would read this project's own.

``--kind doc`` lints any Markdown file (a review, a register) for the row-id rules only:
``ID_RANGE``, ``ID_BARE``, ``ROW_UNKNOWN`` and ``VERDICT_WRONG``, over the whole file, with
no section, budget or template rule. Outcome docs keep ``lint_outcome.py``.

Exit 0 when there is no error finding, 1 when there is, 2 on a usage error.
Human output is one line per finding, ``<path>:<line>: <RULE> <message>``;
``--counts`` adds one last line with the words each part shows against its
budget (the first screen, the block, and "What changes for people").
``--json`` prints one object, the counts included. Deterministic; stdlib
only; no network.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import check  # noqa: E402  (sibling-script import; see path insert above)
import map_features  # noqa: E402
import orient  # noqa: E402

RELATIONS = ("EXISTING-SCENARIO", "EXISTING", "DEFECT", "EXTEND", "NEW-ROW", "SURFACE", "DECISION", "KEEPS")
BUILDS = ("DEFECT", "EXTEND", "NEW-ROW", "KEEPS")
SECTIONS = {
    "issue": ["Capability check", "Gap", "How to build it", "Decisions needed"],
    "pr": ["Where this is", "Words", "What changes for people", "Why", "Capabilities", "Check these first", "Proof"],
}
FIRST_SCREEN = ["Where this is", "Words"]
FIRST_SCREEN_BUDGET = 180
MAX_AREAS = 5
PLAIN = {"issue": [], "pr": ["What changes for people"]}
PROSE = {"issue": ["Gap"], "pr": ["Why"]}
WORD_BUDGET = {"issue": 450, "pr": 250}
PEOPLE_WORDS, PEOPLE_SENTENCES = 60, 3
PLAIN_SENTENCE, PROSE_SENTENCE = 20, 25
COUNT_INSTEAD = 12
COUNT_LABELS = (("firstScreen", "first screen"), ("block", "block"), ("people", "what changes for people"))
DEFAULT_ROW_ID = r"(?!(?:UTF|ISO|SHA|CVE|RFC|MD|HTTP|TLS|SSL|IPV|AES|RSA|ECMA|ES|PEP|GH)-)[A-Z][A-Z0-9]*-\d+"
KNOWN_VERDICTS = {"proven", "under-proven", "not-built", "watched", "partial", "untested", "stale"}

COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
DETAILS_TAG_RE = re.compile(r"<details\b[^>]*>|</details\s*>", re.IGNORECASE)
FENCE_RE = re.compile(r"^\s*(```|~~~)")
MARKER_RE = re.compile(r"^\s*<!--\s*(/?)promise:(issue|pr|intro)\s*-->\s*$")
HEADING_RE = re.compile(r"^##\s+(.+?)\s*#*\s*$")
ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
TOP_ITEM_RE = re.compile(r"^ ?(?:[-*+]|\d+[.)])\s+")
CODE_SPAN_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
PLACEHOLDER_RE = re.compile(
    r"<(?!/?(?:details|summary|br|b|i|em|strong|code|sub|sup|kbd|p|ul|ol|li|a|img)\b)"
    r"(?![a-z][\w+.-]*:)(?![^<>\s@]+@[^<>\s@]+>)[a-z][^<>\n]*>"
)
PLACEHOLDER_LITERAL_RE = re.compile(r"\bCAP-n\b|`path:line`")
PATH_LINE_RE = re.compile(
    r"[\w.-]+(?:/[\w.-]+)*\.[A-Za-z0-9]{1,8}:\d+"
    r"|\b(?:[\w.-]+/)*(?:Dockerfile|Makefile|Procfile|Gemfile|Rakefile|Justfile|Containerfile):\d+"
    r"|https?://\S+#L\d+"
)
LINK_RE = re.compile(
    r"(?:^|[\s(\[])(?:[\w.-]+/[\w.-]+)?#\d+\b|https?://\S+/(?:issues|pull)/\d+|https?://linear\.app/\S+/issue/"
    r"|\b(?:closes|fixes|resolves|refs?|see|part of)\s+[A-Z][A-Z0-9]+-\d+\b"
    r"|\bno issue\s*(?:[.:;,)]|$)",
    re.IGNORECASE,
)
ROUTE_RE = re.compile(r"/promise\b", re.IGNORECASE)
NOTHING_RE = re.compile(r"\bnothing to build\b", re.IGNORECASE)
OWNER_RE = re.compile(r"\bowner\b|@[\w-]+", re.IGNORECASE)
NONE_RE = re.compile(r"^\s*none\.?\s*$", re.IGNORECASE)
DONE_RE = re.compile(r"\s*(?:[-*+]\s+)?\[[xX]\]")
LEAD_ITEM_RE = re.compile(r"^(?:\*\*|__)((?:(?!\*\*|__).)+)(?:\*\*|__)(.*)$")
NEEDED_RE = re.compile(r"^\s*(?:\*\*|__)Needed from you:?(?:\*\*|__)", re.IGNORECASE)
BOLD_LEAD_RE = re.compile(r"^\s*(?:\*\*|__)(?:(?!\*\*|__).)+(?:\*\*|__)[\s.:,-]*")
FEATURE_LEAD_RE = re.compile(r"^( ?(?:[-*+]|\d+[.)])\s+)(?:\*\*|__)(?:(?!\*\*|__).)+(?:\*\*|__)")
ALSO_RE = re.compile(r"^\s*(?:\*\*|__)?Also:(?:\*\*|__)?\s*(\S.*)$", re.IGNORECASE)
BOLD_RE = re.compile(r"(?:\*\*|__)((?:(?!\*\*|__).)+)(?:\*\*|__)")
NOT_IN_MAP_RE = re.compile(r"\bnot (?:yet )?in the map\b", re.IGNORECASE)
FILE_NAME_RE = re.compile(r"\b[\w-]+\.(?:ts|tsx|js|jsx|mjs|py|rb|go|rs|java|json|ya?ml|toml|md|sql|sh|css|html)\b")
CODE_WORD_RES = (
    (re.compile(r"`"), "a backtick"),
    (re.compile(r"\b[\w-]+(?:/[\w.-]+)+\.[A-Za-z0-9]{1,8}\b"), "a path"),
    (FILE_NAME_RE, "a file name"),
    (re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+/|(?:^|\s)/[a-z][\w{}:.-]*/[\w{}:./-]*"), "a route"),
    (re.compile(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b"), "a snake_case word"),
    (re.compile(r"\b(?!(?:macOS|iOS|iPadOS|watchOS|tvOS|visionOS|eBay|iCloud|iPhone|iPad|iMac|npm)\b)"
                r"[a-z]{2,}[A-Z][A-Za-z0-9]*\b"), "a camelCase word"),
)
ABBREVIATION_RE = re.compile(r"\b(?:e\.g|i\.e|etc|vs|cf|approx|Dr|Mr|Mrs|Ms|St|No)\.", re.IGNORECASE)
SENTENCE_END_RE = re.compile(r"(?<=[.!?])[\"')\]*_]*\s+|\n+")
WORD_RE = re.compile(r"[A-Za-z0-9][\w'’.-]*")
MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)\s]*(?:\s+\"[^\"]*\")?\)")
SIZES = ("tiny", "small", "capability", "risky", "deferred")
# A word a reader takes for a size: `feature` is the alias of `capability`.
SIZE_ALIASES = {"feature": "capability"}


def canonical_size(word: str) -> str:
    """The size a word names: an alias gives its size, any other word itself."""
    return SIZE_ALIASES.get(word, word)
# A deferred change was built first, under pressure: its block needs only these, and its
# Size line says what it owes ("Size: deferred — owes: …"); `reconcile` pays it later.
DEFERRED_SECTIONS = ("Why", "Proof")
OWES_RE = re.compile(r"\bowes\s*:\s*\S", re.IGNORECASE)
SIZE_LINE_RE = re.compile(r"^\s*(?:[-*+]\s+)?Size\s*:\s*(\S*)", re.IGNORECASE)
ONE_WORD_RE = re.compile(r"`[^`]*`|https?://\S+|\S*[\w.-]/[\w./-]+(?::\d+(?:-\d+)?)?\S*")
# A row id never stands alone: "CAP-12, the saved card". What may sit between the id and
# its meaning (a link's target, scenarios, a verdict, bold), the marks that start a meaning,
# and the words that make an id a tracker key ("Closes ABC-12") rather than a row named.
ID_TAIL_RE = re.compile(r"^(?:\]\([^)]*\)|\]\[[^\]]*\])?(?:\s+S\d+(?:\s*(?:,|/|and)\s*S\d+)*)?(?:\s*\([a-z-]+\))?[*_`]*")
GLOSS_AFTER_RE = re.compile(r"^(?:\s+[a-z]+(?=:))?\s*(?:[,:;(\u2014\u2013\u00b7|]|\s-\s|-\s)\s*\[?[*_]*(\S+)")
GLOSS_BEFORE_RE = re.compile(r"[A-Za-z]{2,}[^\n]*?(?:[(\u2014\u2013\u00b7]|\s-)\s*[*_`]*\[?[*_`]*$")
# the pull request's "Touched, verdicts unchanged: C-4, C-7" line lists ids by design
TOUCHED_RE = re.compile(r"^\s*(?:[-*+]\s+)?(?:\*\*|__)?Touched\b", re.IGNORECASE)
TRACKER_BEFORE_RE = re.compile(r"\b(?:closes|fixes|resolves|refs?|part of)\s*:?\s*[*_`]*\[?$", re.IGNORECASE)
RANGE_SEP_RE = re.compile(r"\s*(?:to|through|thru|until|[\u2013\u2014]|\.\.|-)\s*", re.IGNORECASE)
RANGE_SHORT_RE = re.compile(r"^\s*(?:[\u2013\u2014]|\.\.(?!\.))\s*(\d+)(?![\w-])")
# "moved from CAP-3 to CAP-4", "renamed CAP-3 to CAP-4": a change of id, not a range
NOT_RANGE_BEFORE_RE = re.compile(r"\b(?:from|renamed|renames|renaming|moved|moves|merged|merges|changed|changes|"
                                 r"split|replaced|replaces|became|becomes)\s+[*_\[]*$", re.IGNORECASE)
LINK_TARGET_RE = re.compile(r"(?<=\]\()(?:<[^>\n]*>|[^()\s]*(?:\([^()\s]*\)[^()\s]*)*)(?:\s+\"[^\"]*\")?(?=\))")
SLASH_TOKEN_RE = re.compile(r"(?<!\S)[^\s\[\]()]*/[^\s\[\]()]*")
JOINED_RANGE_RE = re.compile(r"(?<=\d)([\u2013\u2014-])(?=[A-Z][A-Z0-9]*-\d)")
TITLE_STOP = {"the", "and", "for", "with", "from", "that", "this", "when", "into", "can", "its", "are", "not",
              "has", "have", "will", "they", "their", "user", "users", "story", "of", "to", "a", "an", "in",
              "on", "is", "be", "or", "as", "at", "by", "it"}
ID_GLOSS_WINDOW = 6


class UsageError(Exception):
    pass


def finding(rule: str, line: Optional[int], message: str, severity: str = "error") -> Dict[str, Any]:
    return {"rule": rule, "line": line, "message": message, "severity": severity}


# ---------------------------------------------------------------------------
# the block and its sections
# ---------------------------------------------------------------------------


def markers(text: str, kind: str) -> Tuple[List[int], List[int]]:
    """Line indexes of the block's opening and closing markers. A marker
    inside a code fence is text, not a marker."""
    begin: List[int] = []
    end: List[int] = []
    fence: Optional[str] = None
    for i, ln in enumerate(text.splitlines()):
        f = FENCE_RE.match(ln)
        if f:
            fence = None if fence == f.group(1) else (fence or f.group(1))
            continue
        m = MARKER_RE.match(ln) if fence is None else None
        if m and m.group(2) == kind:
            (end if m.group(1) else begin).append(i)
    return begin, end


def find_block(text: str, kind: str) -> Tuple[Optional[Tuple[int, int]], Optional[str]]:
    """(start, end) line indexes of the block's interior, or (None, why)."""
    begin, end = markers(text, kind)
    if not begin and not end:
        writer = "issue" if kind == "intro" else kind
        return None, f"no <!-- promise:{kind} --> block; `/promise {writer}` writes one"
    if len(begin) != 1 or len(end) != 1:
        return None, f"the <!-- promise:{kind} --> markers appear {len(begin)} and {len(end)} times; keep one pair"
    if end[0] < begin[0]:
        return None, f"<!-- /promise:{kind} --> comes before <!-- promise:{kind} -->"
    return (begin[0] + 1, end[0]), None


def size_lines(text: str) -> List[Tuple[int, str]]:
    """(1-based line, first word lowercased) of each ``Size:`` line a reader sees
    under the pull request block's "Why" heading, where the template puts it (the
    whole block when it has no "Why", the whole text when it has no block). A Why with
    no Size line falls back to the whole block, for a line that names a size, so a
    tiny claim under another heading is still read. The word ends at a dash too:
    "Size: tiny—keeps CAP-12" says tiny. Case is ignored."""
    bounds, _why = find_block(text, "pr")
    lines = text.split("\n")
    start, end = bounds if bounds else (0, len(lines))
    shown = visible("\n".join(lines[start:end])).split("\n")
    why = sections(shown, start).get("why")
    whole = [(start + i + 1, line) for i, line in enumerate(shown)]

    def read(scanned: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
        out = []
        for n, line in scanned:
            m = SIZE_LINE_RE.match(re.sub(r"\*\*|__", "", line))
            if m:
                word = re.split(r"[—–]|-(?=\s|-|$)|--", m.group(1))[0]
                # `tiny`, *tiny* and _tiny_ are the same claim to a reader
                out.append((n, word.strip(".,;:—–-`*_").lower()))
        return out

    if not why:
        return read(whole)
    found = read(why[1])
    return found or [(n, w) for n, w in read(whole) if canonical_size(w) in SIZES]


def size_rules(text: str, line: int) -> List[Dict[str, Any]]:
    said = size_lines(text)
    if not said:
        return [finding("SIZE", line, "no 'Size:' line; `/promise pr` writes one under 'Why' "
                        "(Size: tiny — keeps CAP-12)", "warn")]
    found = [finding("SIZE", n, f"'Size:' says {word or 'nothing'!r}; say tiny, small, capability, risky or "
                     "deferred (references/sizing.md)") for n, word in said if canonical_size(word) not in SIZES]
    found += [finding("SIZE_ALIAS", n, f"'Size: {word}' is read as {SIZE_ALIASES[word]}; write "
                      f"{SIZE_ALIASES[word]}", "warn") for n, word in said if word in SIZE_ALIASES]
    lines = visible(text).split("\n")  # a comment is not what a reader sees
    for n, word in said:
        seen = re.sub(r"\*\*|__", "", lines[n - 1]) if 0 < n <= len(lines) else ""
        if word == "deferred" and not OWES_RE.search(seen):
            found.append(finding("SIZE", n, "a deferred size says what it owes, on its line: "
                                 "'Size: deferred — owes: <each promise the change touched or made>'"))
    if len(said) > 1:
        found.append(finding("SIZE", said[1][0], f"{len(said)} 'Size:' lines; keep one"))
    return found


def _blank(text: str) -> str:
    return "\n" * text.count("\n")


def blank_details(text: str) -> str:
    """The text with each outermost <details> block blanked, nested ones
    included; an unclosed one runs to the end."""
    out: List[str] = []
    depth, pos, opened = 0, 0, 0
    for m in DETAILS_TAG_RE.finditer(text):
        closing = m.group(0).startswith("</")
        if not closing:
            if depth == 0:
                out.append(text[pos:m.start()])
                opened = m.start()
            depth += 1
        elif depth:
            depth -= 1
            if depth == 0:
                out.append(_blank(text[opened:m.end()]))
                pos = m.end()
    out.append(_blank(text[opened:]) if depth else text[pos:])
    return "".join(out)


def visible(text: str) -> str:
    """The text with HTML comments and <details> blocks blanked, keeping
    every newline so line numbers still hold."""
    return blank_details(COMMENT_RE.sub(lambda m: _blank(m.group(0)), text))


def details_text(text: str) -> str:
    """What the <details> blocks hold: the block less what is visible."""
    shown = visible(text).split("\n")
    return "\n".join(ln for ln, s in zip(text.split("\n"), shown) if ln.strip() and not s.strip())


def sections(lines: List[str], offset: int) -> Dict[str, Tuple[int, List[Tuple[int, str]]]]:
    """Heading -> (line number, [(line number, line)]) for the ``##``
    sections of the block; line numbers are 1-based in the whole body."""
    out: Dict[str, Tuple[int, List[Tuple[int, str]]]] = {}
    current: Optional[str] = None
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m:
            current = m.group(1).strip().lower()
            out.setdefault(current, (offset + i + 1, []))
            continue
        if current is not None:
            out[current][1].append((offset + i + 1, line))
    return out


def body_lines(section: Tuple[int, List[Tuple[int, str]]]) -> List[Tuple[int, str]]:
    return [(n, ln) for n, ln in section[1] if ln.strip()]


def plain_text(line: str) -> str:
    """A line as a reader sees it: a link is its text, and a path, a code
    span or a URL is one word."""
    return ONE_WORD_RE.sub("X", MD_LINK_RE.sub(lambda m: m.group(1), line))


def sentences(entries: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
    out: List[Tuple[int, str]] = []
    for n, line in entries:
        line = ITEM_RE.sub("", line).strip()
        line = ABBREVIATION_RE.sub(lambda m: m.group(0).replace(".", "\u2024"), line)
        for part in SENTENCE_END_RE.split(line):
            if WORD_RE.search(part or ""):
                out.append((n, part.strip().replace("\u2024", ".")))
    return out


def words(text: str) -> int:
    return len(WORD_RE.findall(plain_text(text)))


def items(entries: List[Tuple[int, str]], top: bool = False) -> List[Tuple[int, str]]:
    """List items, each joined with its continuation lines; with ``top``, a
    nested item joins its parent instead of counting as one."""
    out: List[Tuple[int, str]] = []
    start = TOP_ITEM_RE if top else ITEM_RE
    for n, line in entries:
        if start.match(line):
            out.append((n, ITEM_RE.sub("", line).strip()))
        elif out and line.startswith((" ", "\t")):
            out[-1] = (out[-1][0], out[-1][1] + " " + line.strip())
    return out


def lead_item(item: str) -> Optional[Tuple[str, str]]:
    """(name, text) of an item written ``**Name**: text`` (or ``**Name:**
    text``, or a dash in place of the colon); None when it is not."""
    m = LEAD_ITEM_RE.match(item.strip())
    if not m:
        return None
    name, rest = m.group(1).strip(), m.group(2).strip()
    if name.endswith(":"):
        name = name[:-1].strip()
    else:
        sep = re.match(r"^(?::|\u2014|\u2013|-)\s*", rest)
        if not sep:
            return None
        rest = rest[sep.end():]
    return (name, rest) if name and rest else None


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


# ---------------------------------------------------------------------------
# the rules
# ---------------------------------------------------------------------------


def lint(text: str, kind: str, row_ids: Optional[set], row_re: re.Pattern,
         changed: Optional[Dict[str, Any]], verdicts: Optional[Dict[str, str]] = None,
         meta: Optional[Dict[str, Any]] = None, counts: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """The findings for one body. ``counts``, when given, is filled with the
    words each part shows and its budget."""
    meta = dict(meta or {})
    counts = {} if counts is None else counts
    meta.setdefault("rowRe", row_re)
    bounds, why = find_block(text, kind)
    intro: List[Dict[str, Any]] = []
    if kind == "issue":
        intro_bounds, intro_why = find_block(text, "intro")
        if intro_bounds is None:
            # No intro at all: most likely text from before the first screen, a
            # warning. Markers repeated or out of order are a broken block.
            absent = markers(text, "intro") == ([], [])
            intro.append(finding("NO_INTRO", 1, (intro_why or "no intro block") + "; it opens the body with "
                                 "'Where this is' and 'Words' (references/first-screen.md)",
                                 "warn" if absent else "error"))
    if bounds is None:
        return [finding("NO_BLOCK", 1, why or "no block")] + intro
    start, end = bounds
    raw_lines = text.splitlines()
    block_text = "\n".join(raw_lines[start:end])
    shown = visible(block_text).split("\n")
    found: List[Dict[str, Any]] = list(intro)

    for i, line in enumerate(shown):
        m = PLACEHOLDER_LITERAL_RE.search(line) or PLACEHOLDER_RE.search(CODE_SPAN_RE.sub("", line))
        if m:
            found.append(finding("PLACEHOLDER", start + i + 1, f"template text is still here: {m.group(0)!r}"))

    secs = sections(shown, start)
    first = {n for name in FIRST_SCREEN for n, _ln in (secs.get(name.lower()) or (0, []))[1]}
    count = sum(words(ln) for i, ln in enumerate(shown)
                if ln.strip() and not HEADING_RE.match(ln) and start + i + 1 not in first)
    if count > WORD_BUDGET[kind]:
        found.append(finding("TOO_LONG", start + 1, f"the block shows {count} words outside <details>; the budget is "
                             f"{WORD_BUDGET[kind]}. Move detail into <details> or cut it"))
    first_count = sum(words(ln) for i, ln in enumerate(shown)
                      if ln.strip() and not HEADING_RE.match(ln) and start + i + 1 in first)
    if first_count > FIRST_SCREEN_BUDGET:
        found.append(finding("TOO_LONG", start + 1, f"the first screen ('Where this is' and 'Words') shows "
                             f"{first_count} words; keep it to {FIRST_SCREEN_BUDGET}"))

    no_first = kind == "pr" and not any(name.lower() in secs for name in FIRST_SCREEN)
    if kind == "pr" and not no_first:
        counts["firstScreen"] = {"words": first_count, "budget": FIRST_SCREEN_BUDGET}
    counts["block"] = {"words": count, "budget": WORD_BUDGET[kind]}
    if no_first:
        found.append(finding("NO_INTRO", start + 1, "the block does not open with 'Where this is' and 'Words'; "
                             "`/promise pr` writes them (references/first-screen.md)", "warn"))
    deferred = kind == "pr" and any(w == "deferred" for _n, w in size_lines(text))
    for name in SECTIONS[kind]:
        key = name.lower()
        # a deferred block owes the rest: only Why and Proof are required now
        severity = "warn" if deferred and name not in DEFERRED_SECTIONS else "error"
        if key not in secs:
            if (no_first or deferred) and name in FIRST_SCREEN:
                continue
            found.append(finding("MISSING_SECTION", start + 1, f"no '## {name}' section", severity))
        elif not body_lines(secs[key]):
            found.append(finding("EMPTY_SECTION", secs[key][0], f"'## {name}' has no text", severity))

    for name in PLAIN[kind]:
        sec = secs.get(name.lower())
        if not sec:
            continue
        entries = body_lines(sec)
        total = sum(words(ln) for _, ln in entries)
        said = sentences(entries)
        counts["people"] = {"words": total, "budget": PEOPLE_WORDS}
        if total > PEOPLE_WORDS or len(said) > PEOPLE_SENTENCES:
            found.append(finding("TOO_LONG", sec[0], f"'{name}' is {total} words in {len(said)} sentences; "
                                 f"keep it to {PEOPLE_SENTENCES} sentences and {PEOPLE_WORDS} words"))
        for n, s in said:
            if words(s) > PLAIN_SENTENCE:
                found.append(finding("SENTENCE_TOO_LONG", n, f"{words(s)} words; keep a sentence here to "
                                     f"{PLAIN_SENTENCE}: {s[:80]!r}"))
        for n, line in entries:
            for rx, what in CODE_WORD_RES + ((row_re, "a row id"),):
                m = rx.search(line)
                if m:
                    found.append(finding("CODE_WORDS", n, f"'{name}' names {what} ({m.group(0).strip()!r}); say "
                                         "what a person sees, and put the code under 'Check these first'"))
                    break

    for name in PROSE[kind]:
        sec = secs.get(name.lower())
        for n, s in sentences(body_lines(sec)) if sec else []:
            if words(s) > PROSE_SENTENCE:
                found.append(finding("SENTENCE_TOO_LONG", n, f"{words(s)} words; keep a sentence to "
                                     f"{PROSE_SENTENCE}: {s[:80]!r}", "warn"))

    if kind == "pr":
        found += pr_rules(secs, changed, block_text)
        found += size_rules(text, (secs.get("why") or (start + 1,))[0])
        moved = [r for r in (changed or {}).get("rows") or [] if isinstance(r, dict) and r.get("change") != "relabelled"]
        named = ([str(r.get("id")) for r in moved] if changed is not None
                 else [m.group(0) for ln in shown for m in row_re.finditer(ln)])
        term_lines = terms_seen([(start + i + 1, ln) for i, ln in enumerate(shown)], secs)
        if not no_first:
            found += first_screen_rules(secs, meta, named, term_lines)
    else:
        found += issue_rules(secs)
        found += intro_rules(text, meta, [m.group(0) for ln in shown for m in row_re.finditer(ln)], counts)

    known = _known(row_ids, changed)
    # Rows and verdicts are checked in <details> too: a builder reads them there.
    found += row_rules(COMMENT_RE.sub(lambda m: _blank(m.group(0)), block_text).split("\n"), start, row_re, known,
                       verdicts)
    # A meaning beside each id is checked where a reader sees it: a <details> list of rows is exempt.
    found += id_rules(shown, start, row_re, known, meta.get("rowTitle"))
    return found


def intro_rules(text: str, meta: Dict[str, Any], named: List[str],
                counts: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """The intro block of an issue: first in the body, with the first-screen
    sections. Terms are looked for in the whole body a reader sees."""
    bounds, _why = find_block(text, "intro")
    if bounds is None:
        return []  # NO_INTRO is reported by lint()
    start, end = bounds
    lines = text.splitlines()
    found: List[Dict[str, Any]] = []
    shown_all = visible(text).split("\n")
    if any(ln.strip() for ln in shown_all[:start - 1]):
        found.append(finding("INTRO_FIRST", start, "text comes before the intro block; the intro opens the body, "
                             "above the person's own words", "warn"))
    shown = visible("\n".join(lines[start:end])).split("\n")
    secs = sections(shown, start)
    for name in FIRST_SCREEN:
        key = name.lower()
        if key not in secs:
            found.append(finding("MISSING_SECTION", start, f"the intro has no '## {name}' section"))
        elif not body_lines(secs[key]):
            found.append(finding("EMPTY_SECTION", secs[key][0], f"'## {name}' has no text"))
    count = sum(words(ln) for ln in shown if ln.strip() and not HEADING_RE.match(ln))
    if counts is not None:
        counts["firstScreen"] = {"words": count, "budget": FIRST_SCREEN_BUDGET}
    if count > FIRST_SCREEN_BUDGET:
        found.append(finding("TOO_LONG", start, f"the intro, the first screen, shows {count} words; keep it to "
                             f"{FIRST_SCREEN_BUDGET}"))
    term_lines = terms_seen([(i + 1, ln) for i, ln in enumerate(shown_all)], secs)
    return found + first_screen_rules(secs, meta, named, term_lines)


def terms_seen(numbered: List[Tuple[int, str]],
               secs: Dict[str, Tuple[int, List[Tuple[int, str]]]]) -> List[Tuple[int, str]]:
    """The lines a glossary term is looked for in: not 'Words' itself, and
    a feature's bold name in 'Where this is' blanked (its sentence explains it)."""
    words_sec, where = secs.get("words"), secs.get("where this is")
    skip = {n for n, _ in words_sec[1]} if words_sec else set()
    leads = {n for n, _ in where[1]} if where else set()
    out: List[Tuple[int, str]] = []
    for n, ln in numbered:
        if n in skip:
            continue
        if n in leads and TOP_ITEM_RE.match(ln):
            ln = FEATURE_LEAD_RE.sub(r"\1", ln)
        out.append((n, ln))
    return out


def first_screen_rules(secs: Dict[str, Tuple[int, List[Tuple[int, str]]]], meta: Dict[str, Any],
                       named: List[str], term_lines: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
    """'Where this is' and 'Words': the features, the line that says what the
    reader must do, and the product's own words."""
    found: List[Dict[str, Any]] = []
    listed: List[str] = []
    also: List[str] = []  # features past five: no sentence of their own, so they explain no word
    unmapped: set = set()
    where = secs.get("where this is")
    if where and body_lines(where):
        entries = body_lines(where)
        feats = items(entries, top=True)
        if not feats:
            found.append(finding("AREAS", where[0], "list each part of the product this is about as "
                                 "'- **Name**: one plain sentence'"))
        if len(feats) > MAX_AREAS:
            found.append(finding("AREAS", where[0], f"{len(feats)} features; name the {MAX_AREAS} that matter most, "
                                 "and the rest on one line: 'Also: **Name**, **Name**.'", "warn"))
        for n, item in feats:
            lead = lead_item(item)
            if lead is None:
                found.append(finding("AREAS", n, "write this feature as '- **Name**: one plain sentence'"))
                continue
            listed.append(_norm(lead[0]))
            if NOT_IN_MAP_RE.search(lead[1]):
                unmapped.add(_norm(lead[0]))
            for rx, what in CODE_WORD_RES + ((meta.get("rowRe") or re.compile(r"(?!)"), "a row id"),):
                m = rx.search(lead[1])
                if m:
                    found.append(finding("CODE_WORDS", n, f"the feature's sentence names {what} "
                                         f"({m.group(0).strip()!r}); say what the part does for a person"))
                    break
        for n, sent in sentences(entries):
            if words(sent) > PROSE_SENTENCE:
                found.append(finding("SENTENCE_TOO_LONG", n, f"{words(sent)} words; keep a sentence to "
                                     f"{PROSE_SENTENCE}: {sent[:80]!r}", "warn"))
        for _n, ln in entries:
            also_line = ALSO_RE.match(ln)
            if also_line:
                also += also_names(also_line.group(1))
        if not any(NEEDED_RE.match(ln) for _, ln in entries):
            found.append(finding("NEEDED", where[0], "add '**Needed from you:** <what the reader must do, or "
                                 "nothing>' under the features", "warn"))
    defined: List[str] = []
    words_sec = secs.get("words")
    if words_sec and body_lines(words_sec):
        entries = body_lines(words_sec)
        if not all(NONE_RE.match(ln) for _, ln in entries):
            terms = items(entries)
            if not terms:
                found.append(finding("WORDS", words_sec[0], "explain each term as '- **Term**: its meaning', "
                                     "or say 'None.'"))
            for n, item in terms:
                lead = lead_item(item)
                if lead is None:
                    found.append(finding("WORDS", n, "write this term as '- **Term**: its meaning'"))
                else:
                    defined.append(_norm(lead[0]))
            for n, sent in sentences(entries):
                if words(sent) > PROSE_SENTENCE:
                    found.append(finding("SENTENCE_TOO_LONG", n, f"{words(sent)} words; keep a sentence to "
                                         f"{PROSE_SENTENCE}: {sent[:80]!r}", "warn"))
    if where and (listed or also):
        found += feature_rules(where[0], listed + also, meta, named, unmapped)
    # A feature's name is explained by its sentence, so it counts as a defined word.
    # An 'Also:' feature has no sentence, but a name the map's features hold is the map's own
    # word: it counts as explained too.
    feature_names = {_norm(str(a.get("name") or "")) for a in (meta.get("features") or {}).values()}
    feature_names |= {_norm(aid) for aid in (meta.get("features") or {})}
    found += term_rules(words_sec[0] if words_sec else 1, defined + listed + [a for a in also if a in feature_names],
                        meta.get("glossary") or [], term_lines)
    return found


def also_names(text: str) -> List[str]:
    """The features an 'Also:' line names: its bold names, else its list."""
    parts = BOLD_RE.findall(text) or re.split(r",\s*|\s+and\s+", text)
    return [_norm(p.strip(" .;:")) for p in parts if p.strip(" .;:")]


def feature_rules(line: int, listed: List[str], meta: Dict[str, Any], named: List[str],
               unmapped: Optional[set] = None) -> List[Dict[str, Any]]:
    areas: Dict[str, Dict[str, Any]] = meta.get("features") or {}
    if not areas:
        return []
    found: List[Dict[str, Any]] = []
    known = {_norm(str(a.get("name") or "")): aid for aid, a in areas.items()}
    known.update({_norm(aid): aid for aid in areas})
    for name in listed:
        if name not in known and name not in (unmapped or set()):
            found.append(finding("AREA_UNKNOWN", line, f"'{name}' is not a feature in the map; use the map's name, "
                                 "or add the feature to the map", "warn"))
    said = {known[n] for n in listed if n in known}
    row_area: Dict[str, str] = meta.get("rowFeature") or {}
    wanted: Dict[str, List[str]] = {}
    for rid in named:
        aid = row_area.get(rid)
        if aid and aid in areas and aid not in said:
            wanted.setdefault(aid, [])
            if rid not in wanted[aid]:
                wanted[aid].append(rid)
    for aid, rids in wanted.items():
        found.append(finding("AREA_MISSING", line, f"{', '.join(rids[:3])} belong to '{areas[aid].get('name') or aid}'; "
                             "name that feature under 'Where this is'", "warn"))
    return found


def term_rules(line: int, defined: List[str], glossary: List[Dict[str, Any]],
               term_lines: List[Tuple[int, str]]) -> List[Dict[str, Any]]:
    """A glossary term the reader meets must be explained under 'Words'."""
    found: List[Dict[str, Any]] = []
    # A code span, a path, a URL or a file name is code, not a word a reader must learn.
    plain = [(n, FILE_NAME_RE.sub(" ", ONE_WORD_RE.sub(" ", MD_LINK_RE.sub(lambda m: m.group(1),
                                                                         CODE_SPAN_RE.sub(" ", ln)))))
             for n, ln in term_lines]
    for entry in glossary:
        spellings = [str(entry.get("term") or "")] + [str(a) for a in entry.get("aliases") or [] if isinstance(entry.get("aliases"), list)]
        spellings = [_norm(w) for w in spellings if w.strip()]
        if not spellings:
            continue
        if any(_covers(w, d) for w in spellings for d in defined):
            continue
        rx = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(w).replace(r"\ ", r"\s+") for w in spellings)
                        + r")(?:s|es)?(?![\w-])", re.IGNORECASE)
        for n, ln in plain:
            m = rx.search(ln)
            if m:
                found.append(finding("TERM_UNDEFINED", n, f"'{m.group(0)}' is in the glossary ({entry.get('term')}); "
                                     "explain it under 'Words'", "warn"))
                break
    return found


def _covers(spelling: str, term: str) -> bool:
    """A defined term covers a glossary spelling it starts with, in the
    singular or the plural: 'Team seat' covers 'team', 'Modules' covers
    'module', 'Invoice' covers 'invoices'."""
    stems = {spelling}
    for end in ("es", "s"):
        if spelling.endswith(end) and len(spelling) > len(end) + 2:
            stems.add(spelling[:-len(end)])
    return any(re.match(re.escape(s) + r"(?:s|es)?(?![\w-])", term) for s in stems)


def verdict_rules(shown: List[str], start: int, row_re: re.Pattern,
                  verdicts: Dict[str, str]) -> List[Dict[str, Any]]:
    """A verdict written beside a row id must be the row's verdict."""
    found: List[Dict[str, Any]] = []
    words_seen = KNOWN_VERDICTS | set(verdicts.values())
    for i, line in enumerate(shown):
        for m in row_re.finditer(line):
            rest = line[m.end():]
            rest = re.sub(r"^\]\([^)]*\)", "", rest)
            v = re.match(r"(?:\s+S\d+(?:\s*(?:,|and)\s*S\d+)*)?\s*\(([a-z-]+)[),;]", rest)
            said = v.group(1) if v else None
            actual = verdicts.get(m.group(0))
            if said and actual and said in words_seen and said != actual:
                found.append(finding("VERDICT_WRONG", start + i + 1, f"{m.group(0)} is {verdicts[m.group(0)]} in "
                                     f"the map, not {said}"))
    return found


def _title_words(title: str) -> set:
    return {w for w in re.findall(r"[a-z]{3,}", title.lower()) if w not in TITLE_STOP}


def _near_title(line: str, m: re.Match, title: str) -> bool:
    """The row's own title words within a few words of its id."""
    want = _title_words(title)
    if not want:
        return False
    before = re.findall(r"[a-z]{3,}", line[:m.start()].lower())[-ID_GLOSS_WINDOW:]
    after = re.findall(r"[a-z]{3,}", line[m.end():].lower())[:ID_GLOSS_WINDOW]
    return any(w.rstrip("s") in {t.rstrip("s") for t in want} for w in before + after)


def _ascending(a: str, b: str) -> bool:
    """Two ids of one prefix, the second higher: the ends of a range."""
    pa, _s, na = a.rpartition("-")
    pb, _s, nb = b.rpartition("-")
    return pa == pb and na.isdigit() and nb.isdigit() and int(nb) > int(na)


def id_lines(lines: List[str]) -> List[str]:
    """The lines a row id is read on for the id rules: code fences, code spans and table
    rows blanked (a table of rows is its own gloss), hyphen-joined ranges split."""
    out: List[str] = []
    fenced = False
    for line in lines:
        if FENCE_RE.match(line):
            fenced = not fenced
            out.append("")
            continue
        if fenced or line.lstrip().startswith("|") or TOUCHED_RE.match(line):
            out.append("")
            continue
        blank = lambda m: " " * len(m.group(0))  # noqa: E731
        # code, link targets, URLs and paths are not text a reader reads an id in
        line = CODE_SPAN_RE.sub(blank, line)
        line = LINK_TARGET_RE.sub(blank, line)
        line = SLASH_TOKEN_RE.sub(blank, line)
        out.append(JOINED_RANGE_RE.sub(r" \1 ", line))
    return out


def id_rules(lines: List[str], start: int, row_re: re.Pattern, known: Optional[set],
             titles: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """``ID_RANGE``: a range of row ids hides what each one means. ``ID_BARE``: a row id
    with no meaning beside it. ``lines`` are what a reader sees (comments and
    ``<details>`` blanked); ``start`` is the line number before the first."""
    found: List[Dict[str, Any]] = []
    titles = titles or {}
    for i, line in enumerate(id_lines(lines)):
        ids = [m for m in row_re.finditer(line) if known is None or m.group(0) in known]
        in_range = set()
        for a, b in zip(ids, ids[1:]):
            between = re.sub(r"^(?:\]\(\s*\)|\])", "", line[a.end():b.start()])
            between = re.sub(r"[*_\[]+$", "", re.sub(r"^[*_]+", "", between))
            if RANGE_SEP_RE.fullmatch(between) and _ascending(a.group(0), b.group(0)) \
                    and not NOT_RANGE_BEFORE_RE.search(line[:a.start()]):
                in_range |= {a.start(), b.start()}
                found.append(finding("ID_RANGE", start + i + 1, f"'{a.group(0)} to {b.group(0)}' is a range: name "
                                     f"each row with what it means ('{a.group(0)}, <what it promises>')"))
        for m in ids:
            if m.start() in in_range:
                continue
            rest = ID_TAIL_RE.sub("", line[m.end():], count=1)
            short = RANGE_SHORT_RE.match(line[m.end():])
            if short and _ascending(m.group(0), m.group(0).rsplit("-", 1)[0] + "-" + short.group(1)) \
                    and len(short.group(1)) <= len(m.group(0).rsplit("-", 1)[1]):
                found.append(finding("ID_RANGE", start + i + 1, f"'{m.group(0)}{short.group(0)}' "
                                     "is a range: name each row with what it means"))
                continue
            before = line[:m.start()]
            if TRACKER_BEFORE_RE.search(before):
                continue  # "Closes ABC-12": a tracker key, not a row named
            after = GLOSS_AFTER_RE.match(rest)
            if after and re.match(r"[A-Za-z]", after.group(1)) and not row_re.match(after.group(1)):
                continue
            if GLOSS_BEFORE_RE.search(before) or _near_title(line, m, titles.get(m.group(0), "")):
                continue
            found.append(finding("ID_BARE", start + i + 1, f"{m.group(0)} stands alone; say what it is beside it "
                                 f"('{m.group(0)}, <what the row promises>')", "warn"))
    return found


def doc_lint(text: str, row_ids: Optional[set], row_re: re.Pattern, changed: Optional[Dict[str, Any]],
             verdicts: Optional[Dict[str, str]] = None, meta: Optional[Dict[str, Any]] = None
             ) -> List[Dict[str, Any]]:
    """``--kind doc``: a Markdown file in the repo, the id rules only."""
    known = _known(row_ids, changed)
    titles = (meta or {}).get("rowTitle") or {}
    found = id_rules(visible(text).split("\n"), 0, row_re, known, titles)
    found += row_rules(COMMENT_RE.sub(lambda m: _blank(m.group(0)), text).split("\n"), 0, row_re, known, verdicts)
    return found


def _known(row_ids: Optional[set], changed: Optional[Dict[str, Any]]) -> Optional[set]:
    known = set(row_ids) if row_ids is not None else None
    rows = changed.get("rows") if isinstance(changed, dict) else None
    if known is not None and isinstance(rows, list):
        known |= {str(r.get("id")) for r in rows if isinstance(r, dict)}
    return known


def row_rules(checked: List[str], start: int, row_re: re.Pattern, known: Optional[set],
              verdicts: Optional[Dict[str, str]]) -> List[Dict[str, Any]]:
    """``ROW_UNKNOWN`` and ``VERDICT_WRONG`` on ``checked`` (comments blanked)."""
    found: List[Dict[str, Any]] = []
    if known is not None:
        for i, line in enumerate(checked):
            for m in row_re.finditer(line):
                if m.group(0) not in known:
                    found.append(finding("ROW_UNKNOWN", start + i + 1, f"{m.group(0)} is not a row in the map"))
    if verdicts:
        found += verdict_rules(checked, start, row_re, verdicts)
    return found


def _named(rid: str, text: str) -> bool:
    return bool(re.search(r"(?<![\w-])" + re.escape(rid) + r"(?![\w-])", text))


def pr_rules(secs: Dict[str, Tuple[int, List[Tuple[int, str]]]],
             changed: Optional[Dict[str, Any]], block_text: str = "") -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    why = secs.get("why")
    if why and body_lines(why) and not any(LINK_RE.search(ln) for _, ln in body_lines(why)):
        found.append(finding("NO_LINK", why[0], "'Why' names no issue; link it (Closes #12) or say 'No issue.'"))
    check_sec = secs.get("check these first")
    if check_sec and body_lines(check_sec):
        listed = items(body_lines(check_sec), top=True)
        if not listed or len(listed) > 3:
            found.append(finding("CHECK_ITEMS", check_sec[0], f"'Check these first' lists {len(listed)} items; "
                                 "give one to three"))
        for n, item in listed:
            if not PATH_LINE_RE.search(item):
                found.append(finding("CHECK_ITEMS", n, "this item has no path:line for the reviewer to open"))
    caps = secs.get("capabilities")
    if changed is not None and caps is not None:
        text = "\n".join(ln for _, ln in caps[1])
        anywhere = text + "\n" + details_text(block_text)
        by_change: Dict[str, List[str]] = {}
        for row in changed.get("rows") or []:
            rid = str(row.get("id"))
            if not _named(rid, anywhere):
                by_change.setdefault(str(row.get("change")), []).append(rid)
        totals: Dict[str, int] = {}
        for row in changed.get("rows") or []:
            totals[str(row.get("change"))] = totals.get(str(row.get("change")), 0) + 1
        for change, missing in by_change.items():
            total = totals.get(change, 0)
            if total > COUNT_INSTEAD and re.search(rf"\b{total}\s+(?:\w+\s+)?rows?\b[^.\n]*\b{change}\b", text,
                                                   re.IGNORECASE):
                continue
            severity = "warn" if change in ("touched", "relabelled") else "error"
            for rid in missing[:COUNT_INSTEAD]:
                found.append(finding("ROW_MISSING", caps[0], f"{rid} was {change} by this change; "
                                     "name it under 'Capabilities'", severity))
            if len(missing) > COUNT_INSTEAD:
                found.append(finding("ROW_MISSING", caps[0], f"and {len(missing) - COUNT_INSTEAD} more {change} rows; "
                                     f"with more than {COUNT_INSTEAD}, give the count ('{total} rows {change}')",
                                     severity))
        unhomed = changed.get("unhomed") or []
        says = re.search(r"\bno row (?:names|cites)\b|\bfiles? no row\b|\bno row\b", text, re.IGNORECASE)
        if unhomed and not says and not any(os.path.basename(f) in text for f in unhomed):
            found.append(finding("UNHOMED", caps[0], f"{len(unhomed)} changed files have no row; say so "
                                 "under 'Capabilities' ('No row names: ...'), or name the row", "warn"))
    return found


def _relation(item: str) -> Optional[str]:
    """The relation an ask starts with, after its bold lead."""
    rest = BOLD_LEAD_RE.sub("", item, count=1).lstrip("*_ ")
    for rel in RELATIONS:
        if re.match(re.escape(rel) + r"(?![\w-])", rest):
            return rel
    return None


def issue_rules(secs: Dict[str, Tuple[int, List[Tuple[int, str]]]]) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    relations: List[str] = []
    cap = secs.get("capability check")
    if cap and body_lines(cap):
        first = body_lines(cap)[0]
        if not re.match(r"\s*Read:", first[1]):
            found.append(finding("READ_LINE", first[0], "start 'Capability check' with 'Read: <the docs, research "
                                 "and learnings this check read, or \"the map only\">.'", "warn"))
        listed = items(body_lines(cap), top=True)
        if not listed:
            found.append(finding("RELATION", cap[0], "'Capability check' lists no ask; give one item per ask, "
                                 "each with its relation"))
        for n, item in listed:
            rel = _relation(item)
            if rel is None:
                found.append(finding("RELATION", n, "start this ask, after its bold lead, with its relation ("
                                     + ", ".join(r for r in RELATIONS if r != "EXISTING") + ")"))
            else:
                relations.append(rel)
    route = secs.get("how to build it")
    if route and body_lines(route):
        lines = [ln for _, ln in body_lines(route)]
        builds = sorted({r for r in relations if r in BUILDS})
        if not any(ROUTE_RE.search(ln) for ln in lines):
            if not any(NOTHING_RE.search(ln) for ln in lines):
                found.append(finding("NO_ROUTE", route[0], "'How to build it' names no /promise step; say which one, "
                                     "or 'Nothing to build'"))
            elif builds:
                found.append(finding("NO_ROUTE", route[0], f"an ask is {', '.join(builds)}, so there is something "
                                     "to build; name its /promise step"))
    decisions = secs.get("decisions needed")
    if decisions and body_lines(decisions):
        lines = body_lines(decisions)
        if "DECISION" in relations and all(NONE_RE.match(ln) for _, ln in lines):
            found.append(finding("DECISIONS", decisions[0], "an ask is DECISION, but 'Decisions needed' says None; "
                                 "put the question here with its owner"))
        for n, item in items(lines, top=True):
            if not DONE_RE.match(item) and not OWNER_RE.search(item):
                found.append(finding("DECISIONS", n, "this decision names no owner; add (owner: <name>)", "warn"))
    return found


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------


def load_map(cwd: str, config_arg: Optional[str], map_arg: Optional[str]
             ) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """Row id -> verdict from ``--map`` or the config, and the row-id pattern."""
    verdicts, pattern, _meta = load_map_meta(cwd, config_arg, map_arg)
    return verdicts, pattern


def load_map_meta(cwd: str, config_arg: Optional[str], map_arg: Optional[str], _via_sibling: bool = False
                  ) -> Tuple[Optional[Dict[str, str]], Optional[str], Dict[str, Any]]:
    """Row id -> verdict, the row-id pattern, and what the first screen reads
    from the map: ``features`` by id, each row's feature (``rowFeature``) and the
    ``glossary``. A project with ``"map": false`` and a ``sibling`` reads the
    sibling's map, from its checkout at ``sibling.path`` (``meta["sibling"]`` names
    its repo; ``meta["siblingUnread"]`` does, when no checkout is there)."""
    config, _path, _warnings = check.load_project_config(cwd, config_arg)
    map_value = config.get("map") if isinstance(config, dict) else None
    if map_arg is None and map_value is False and not _via_sibling:
        sib = orient.resolve_sibling(config, False, [], cwd)
        if sib and sib["checkout"]:
            try:
                verdicts, pattern, meta = load_map_meta(sib["dir"], None, None, _via_sibling=True)
            except (UsageError, check.UsageError, OSError, ValueError):
                verdicts = None
            if verdicts is not None:
                return verdicts, pattern, dict(meta, sibling=sib["repo"])
            # a checkout with no readable map (never adopted, or a map that is not one)
            return None, None, {"siblingUnread": sib["repo"], "siblingPath": sib["path"]}
        if sib:
            return None, None, {"siblingUnread": sib["repo"], "siblingPath": sib["path"]}
    pattern = map_value.get("rowIdPattern") if isinstance(map_value, dict) else None
    path = map_arg
    if path is None and isinstance(map_value, dict):
        path, _how = check.map_file(map_value)
    if not path:
        return None, pattern, {}
    full = path if os.path.isabs(path) else os.path.join(cwd, path)
    try:
        with open(full, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read the map {path}: {exc}")
    rows = data.get("rows") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise UsageError(f"{path} has no 'rows' list")
    top = data if isinstance(data, dict) else {}
    feature_key = "features" if "features" in top or "areas" not in top else "areas"
    for key, value in ((feature_key, map_features.feature_list(top)), ("glossary", top.get("glossary"))):
        if value is not None and not isinstance(value, list):
            raise UsageError(f"{path}: '{key}' is not a list")
    meta = {
        "features": map_features.features_by_id(top),
        "rowFeature": {str(r.get("id")): str(map_features.row_feature(r)) for r in rows
                       if isinstance(r, dict) and map_features.row_feature(r)},
        "featureConflicts": map_features.conflicts(top, rows),
        "glossary": [g for g in top.get("glossary") or [] if isinstance(g, dict)],
        "rowTitle": {str(r.get("id")): str(r.get("title") or r.get("story") or "") for r in rows
                     if isinstance(r, dict)},
    }
    return {str(r.get("id")): str(r.get("verdict") or "") for r in rows if isinstance(r, dict)}, pattern, meta


def map_row_ids(cwd: str, config_arg: Optional[str], map_arg: Optional[str]) -> Tuple[Optional[set], Optional[str]]:
    """The map's row ids and the row-id pattern, from ``--map`` or the config."""
    verdicts, pattern = load_map(cwd, config_arg, map_arg)
    return (set(verdicts) if verdicts is not None else None), pattern


def row_pattern(value: Optional[str], row_ids: Optional[set] = None) -> re.Pattern:
    """The row-id pattern for finding ids in text: the config's, with its
    anchors taken out (each alternative's too); else one built from the
    map's own id prefixes; else a default that skips UTF-8, SHA-256 and the
    like."""
    text = (value or "").strip()
    # 1.25's pattern also took ids with no CAP- prefix, a shape words such as GPT-4o and
    # i3wm share: under it, only a CAP- id counts (orient warns to update the pattern)
    guard = r"(?=CAP-)" if text and orient.takes_bare_tracker_ids(text) else ""
    text = re.sub(r"(?<![\\\[])\^", "", text)
    text = re.sub(r"(?<!\\)\$", "", text)
    if not text and row_ids:
        prefixes = sorted({m.group(1) for m in (re.match(r"^([A-Za-z][\w]*-)\d+$", i) for i in row_ids) if m})
        if prefixes:
            text = "(?:" + "|".join(re.escape(p) for p in prefixes) + r")\d+"
    try:
        return re.compile(r"(?<![\w-])" + guard + r"(?:" + (text or DEFAULT_ROW_ID) + r")(?![\w-])")
    except re.error:
        return re.compile(r"(?<![\w-])(?:" + DEFAULT_ROW_ID + r")(?![\w-])")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lint_github_text.py",
        description="Lint the /promise block of an issue or pull request body, or the row ids in a doc.",
    )
    parser.add_argument("body", help="the body as a file, or - for stdin")
    parser.add_argument("--kind", choices=("issue", "pr", "doc"), required=True,
                        help="doc: any Markdown file in the repo, for the row-id rules only")
    parser.add_argument("--changed", default=None, help="changed_rows.py --json output (pr)")
    parser.add_argument("--cwd", default=None, help="project root (default: current directory)")
    parser.add_argument("--config", default=None, help="the promise config (default: the one orient finds)")
    parser.add_argument("--map", default=None, help="the map's JSON file (default: from the config)")
    parser.add_argument("--no-map", action="store_true", help="do not check row ids against the map")
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.add_argument("--counts", action="store_true",
                        help="end with one line of word counts against their budgets")
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    cwd = os.path.abspath(args.cwd or os.getcwd())
    try:
        if args.body == "-":
            text = sys.stdin.read()
        else:
            with open(args.body, "r", encoding="utf-8-sig") as fh:
                text = fh.read()
        text = text.replace("\r\n", "\n")
        changed = None
        if args.changed:
            with open(args.changed, "r", encoding="utf-8-sig") as fh:
                changed = json.load(fh)
            if not isinstance(changed, dict):
                raise UsageError("--changed is not a changed_rows.py --json report")
        verdicts, pattern, meta = (None, None, {}) if args.no_map else load_map_meta(cwd, args.config, args.map)
        row_ids = set(verdicts) if verdicts is not None else None
        if args.no_map:
            config, _p, _w = check.load_project_config(cwd, args.config)
            m = config.get("map") if isinstance(config, dict) else None
            pattern = m.get("rowIdPattern") if isinstance(m, dict) else None
    except (OSError, ValueError, UsageError, check.UsageError) as exc:
        print(f"lint_github_text.py: {exc}", file=sys.stderr)
        return 2

    counts: Dict[str, Any] = {}
    if args.kind == "doc":
        findings = doc_lint(text, row_ids, row_pattern(pattern, row_ids), changed, verdicts, meta)
    else:
        findings = lint(text, args.kind, row_ids, row_pattern(pattern, row_ids), changed, verdicts, meta, counts)
    for conflict in meta.get("featureConflicts") or []:
        findings.append(finding(map_features.FEATURE_AND_AREA, 1, conflict.split(": ", 1)[1]))
    if meta.get("siblingUnread"):
        findings.append(finding("SIBLING_UNREAD", 1, f"the rows live in {meta['siblingUnread']}'s map, and no "
                                f"readable map is at sibling.path ({meta['siblingPath']}): no row was checked",
                                "warn"))
    findings.sort(key=lambda f: (f["line"] or 0, f["rule"]))
    errors = sum(1 for f in findings if f["severity"] == "error")
    if args.json:
        print(json.dumps({"path": args.body, "kind": args.kind, "findings": findings,
                          "stats": {"errors": errors, "warnings": len(findings) - errors},
                          "counts": counts},
                         indent=2, ensure_ascii=False))
    else:
        for f in findings:
            print(f"{args.body}:{f['line'] or 1}: {f['rule']} {f['message']}"
                  + (" (warn)" if f["severity"] == "warn" else ""))
        if args.counts:
            shown = [f"{label} {counts[key]['words']}/{counts[key]['budget']}" for key, label in COUNT_LABELS
                     if key in counts]
            print(f"{args.body}: words: " + (", ".join(shown) or "no block"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
