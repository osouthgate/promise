#!/usr/bin/env python3
"""Adopt the promise skill into a project: config file + CLAUDE.md section.

    python3 adopt.py --cwd /path/to/project
    python3 adopt.py --cwd /path/to/project --dry-run
    python3 adopt.py --cwd /path/to/project --agents-md      # also AGENTS.md, for Codex, Cursor and others
    python3 adopt.py --docs-home docs/rfcs --no-config
    python3 adopt.py --policy fast        # the decision policy the human chose: fast, auto (default) or spec

A project is "adopted" once it has a `.claude/promise.config.json` (or a
root `promise.config.json` fallback) and its CLAUDE.md carries the
promise section (references/architecture.md §13), so every person and
agent working there is routed to `/promise` instead of writing a design,
plan or spec doc by hand.

The section lives in AGENTS.md instead when the CLAUDE.md imports it on
a line of its own (``@AGENTS.md``) and holds no section itself, or when
there is no CLAUDE.md and AGENTS.md holds the section: one file every
agent reads. This script then refreshes the section there and leaves
CLAUDE.md alone, so Claude never reads the section twice.

The config it writes carries ``"version": 1``, ``docsHome`` when one is
known, and a ``commands`` object with all three keys, the undetected ones
as null, so the file shows what each verify step runs. Once that object
exists detection is off for all three; ``orient.py`` warns when a null key
now has a detected command, and ``arm`` proposes a test command when
``commands.test`` is null. ``map`` is written as null with a comment.

Never overwrites an existing config, at either the primary or the
fallback location — when one is already loaded, this script writes no
second one and reports where the loaded one lives. Idempotent: running
it again with the same inputs changes no bytes and reports "changed":
false. A hand-edited interior of the managed CLAUDE.md block is restored
to the rendered form, with one line on stderr saying so; content outside
the ``<!-- promise:begin`` / ``<!-- promise:end -->`` markers is left
untouched, byte for byte, including its own line-ending style and a
leading BOM (whitespace around the end marker is tolerated). adopt only
removes text adopt wrote: a section inside the markers under a heading
the template never wrote is kept, unchanged, just above the begin
marker, with one line on stderr and ``movedAboveBlock`` in the JSON
result (a setext heading counts as a heading; one inside a code fence does
not); text that cannot be told apart from the promise section -- a heading
under the promise heading, or a line above the first heading that is not
one of the rendered lines -- is refused (exit 2) with its line numbers. Every file
this script writes goes through a temporary file in the same directory
followed by ``os.replace``, so a reader never observes a half-written
file; the write goes to the real path behind a symlink, so a
``CLAUDE.md -> AGENTS.md`` link keeps pointing where it did, and an
existing file keeps its mode (a new one gets what ``open`` would have
given it under the current umask). ``--dry-run`` writes nothing and
prints a unified diff to stderr; the JSON result is always the only line
on stdout.

A ``--docs-home`` written with backslashes is recorded with forward
slashes (the config contract's form), with one line on stderr saying so.
A docs folder found by detection that holds Markdown but no outcome doc
(orient's ``docsHomeForeignDocs``) is not pinned by default: without
``--docs-home``, a run that would name that folder -- in a fresh config, or
in the CLAUDE.md or AGENTS.md block, so with ``--no-config`` too -- refuses (exit 2)
with the warning orient gives, until ``--docs-home`` picks one (or, with a
config already loaded, until its docsHome is set). ``--dry-run`` refuses
the same way, so its diff never previews a change the real run refuses;
a run that writes neither file only warns.
When a fresh config would pin no docsHome at all — nothing detected and
no ``--docs-home`` given — one line on stderr says that every later
``new`` will ask where docs live; the JSON result carries ``docsHome`` so
a caller can see what was pinned.

Exit 0 on success or no-op. Exit 2 on a usage error, and also when the
CLAUDE.md markers cannot be resolved safely — an unmatched or duplicated
``<!-- promise:begin``, or text inside them adopt cannot tell apart (above) — when a path this script would write is a
directory (or sits under a file), when CLAUDE.md is not UTF-8, when
``--docs-home`` is absolute, escapes the project, or carries a line
break, a marker string or shell syntax, when a detected docs folder
holds no outcome doc (above), or when ``--docs-home`` disagrees with the
docsHome of a config that is already loaded (the config is edited, not
argued with; a CLAUDE.md naming one folder beside a config naming another
is the drift this script exists to prevent). In every one of those cases
nothing is written at all and the JSON result still prints, with
"changed": false, so a caller can always parse stdout as JSON.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import stat
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import orient  # noqa: E402  (sibling-script import; see path insert above)

BEGIN_PREFIX = "<!-- promise:begin"
END_MARKER = "<!-- promise:end -->"
TEMPLATE_NAME = "claude-md-section.md"
UNKNOWN_DOCS_HOME_TEXT = "the project's docs home"
BUNDLED_FRAMEWORK_TEXT = "the copy bundled with the promise skill"
UTF8_BOM = b"\xef\xbb\xbf"
CONFIG_VERSION = 1
VERIFY_COMMAND_KEYS = ("typeCheck", "test", "lint")
# The comment a fresh config carries while map is null. start_map.py removes
# it, and only it, when it fills the map in.
NULL_MAP_COMMENT = (
    "map is not configured yet. `/promise arm` offers to start one from the "
    "skill's starter map (scripts/start_map.py) when the first doc is agreed; "
    "references/config.md has the shape (recipe, index, find/row/nextId "
    "commands, lanes, checks) for a map of your own."
)


# Headings earlier templates wrote. A block that still has one is promise's
# own section from an older template, not text adopt did not write.
EARLIER_SECTION_HEADINGS = ("## Capability work goes through `/promise`",)
_HEADING_RE = re.compile(r"^ {0,3}#{1,6}(?:[ \t].*)?$")
# A setext underline: the line above it is a heading (level 1 for =, 2 for -).
_SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
# A line that cannot be a setext heading's text: a list item, a quote, a table row.
_NOT_SETEXT_TEXT_RE = re.compile(r"^ {0,3}(?:[-*+>|]|\d{1,9}[.)])(?:[ \t]|$)")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


class ForeignTextError(Exception):
    """The block holds text adopt did not write, and it cannot be told
    apart from promise's own section: a heading of its own under the
    promise heading, text above the first heading, or no promise heading
    at all. The caller writes nothing and names the lines."""

    def __init__(self, first_line: int, last_line: int):
        self.first_line = first_line
        self.last_line = last_line
        super().__init__(
            "the promise block holds text adopt did not write, and it cannot be told apart "
            f"from the promise section (lines {first_line}-{last_line}); move it out of the "
            "markers, then run again"
        )


class MalformedMarkersError(Exception):
    """The CLAUDE.md promise markers cannot be resolved to a safe edit.

    Raised for anything other than "no markers at all" or "exactly one
    begin followed by exactly one end" — a begin with no end, an end
    with no begin, two begins, or an end that comes before its begin.
    Guessing at which lines belong to the managed block in any of these
    shapes risks deleting content a person wrote by hand, so the caller
    is expected to catch this, write nothing, and ask a human to fix the
    markers first.
    """

    def __init__(self, begin_lines: List[int], end_lines: List[int]):
        self.begin_lines = begin_lines
        self.end_lines = end_lines
        super().__init__(self._describe())

    def _describe(self) -> str:
        # 1-based line numbers, matching what an editor shows.
        begin_display = ", ".join(str(i + 1) for i in self.begin_lines) or "none"
        end_display = ", ".join(str(i + 1) for i in self.end_lines) or "none"
        return (
            "cannot resolve the promise:begin/end markers in CLAUDE.md "
            f"(begin at line {begin_display}; end at line {end_display}); "
            "fix the markers by hand, then run again"
        )


def render_section(docs_home: Optional[str], config_path: str, framework_path: str, skill_dir: str,
                   run: Optional[str] = None) -> str:
    """Render templates/claude-md-section.md with {docsHome}/{configPath}/{frameworkPath}.

    Each placeholder is substituted with ``str.replace``, one at a time,
    rather than ``str.format`` — the template's own prose may contain
    other ``{``/``}`` characters that a format-string parse would choke on.
    The backticks belong to the value, not the template: a real path is
    rendered as code (`docs/designs`) and a prose fallback ("the project's
    docs home") as prose, so a template that still backtick-quotes a
    placeholder has those backticks folded into the value's own.
    ``config_path`` and ``framework_path`` arrive already made portable by
    ``display_paths``: a CLAUDE.md is committed and shared, so it must never
    carry one machine's absolute paths.
    """
    template_path = os.path.join(skill_dir, "templates", TEMPLATE_NAME)
    text = orient.read_text_tolerant(template_path)
    for placeholder in ("{docsHome}", "{configPath}", "{frameworkPath}"):
        text = text.replace(f"`{placeholder}`", placeholder)
    text = text.replace("{docsHome}", f"`{docs_home}`" if docs_home else UNKNOWN_DOCS_HOME_TEXT)
    text = text.replace("{configPath}", config_path)
    text = text.replace("{frameworkPath}", framework_path)
    text = text.replace("{runScripts}", f"`{run} <script>.py …`" if run
                        else "`python3 <the skill's folder>/scripts/<script>.py …`")
    # Stamp the begin marker with the template's hash, so orient.py can tell a
    # section written from an older template and name adopt as the refresh.
    stamp = orient.template_stamp(skill_dir)
    first, sep, rest = text.partition("\n")
    if stamp and first.lstrip().startswith(orient.PROMISE_BEGIN_MARKER) and first.rstrip().endswith("-->"):
        first = first.rstrip()[:-3].rstrip() + f" template:{stamp} -->"
    text = first + sep + rest
    return text.rstrip("\n") + "\n"


def display_paths(cwd: str, config_path: str, orientation: Dict[str, Any]) -> Tuple[str, str]:
    """Project-relative config path (as code), and a framework reference
    that is true on every machine: the project's own copy as code, or the
    bundled copy as prose."""
    config_display = "`" + os.path.relpath(config_path, cwd).replace(os.sep, "/") + "`"
    fw = orientation.get("frameworkPath")
    if orientation.get("frameworkSource") == "project" and fw:
        framework_display = "`" + os.path.relpath(fw, cwd).replace(os.sep, "/") + "`"
    else:
        framework_display = BUNDLED_FRAMEWORK_TEXT
    return config_display, framework_display


def build_config(effective_docs_home: Optional[str], commands: Dict[str, Any],
                 skill_version: Optional[str] = None, policy: str = "auto") -> Dict[str, Any]:
    """The config a fresh adoption writes.

    ``commands`` is always written, with all three keys — the undetected
    ones as null — so a new project sees where its test command goes.
    ``minSkillVersion`` is the running skill's version, when it has one, so
    an older copy of the skill says it is older than the project expects.
    """
    config: Dict[str, Any] = {"version": CONFIG_VERSION}
    if skill_version:
        config["minSkillVersion"] = skill_version
    if effective_docs_home:
        config["docsHome"] = effective_docs_home
    # every new doc takes it; the human changes it here, once, for the whole repo
    config["decisionPolicy"] = policy
    command_fields = {
        k: (commands.get(k) if isinstance(commands.get(k), str) and commands.get(k) else None)
        for k in VERIFY_COMMAND_KEYS
    }
    config["commands"] = command_fields
    config["map"] = None
    config["$comment"] = NULL_MAP_COMMENT
    return config


def _scan_markers(lines: List[str]) -> Tuple[List[int], List[int]]:
    """Every line index carrying a begin marker, and every line index that
    is the end marker (surrounding whitespace tolerated) — the full
    picture, not just the first of each, so a caller can tell a
    well-formed file from a malformed one."""
    begin_lines = []
    end_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(BEGIN_PREFIX):
            begin_lines.append(i)
        if stripped == END_MARKER:
            end_lines.append(i)
    return begin_lines, end_lines


def _headings(lines: List[str]) -> List[Tuple[int, int, str]]:
    """(index, level, heading text) for every Markdown heading outside a
    ``` / ~~~ fence, the text with its spaces collapsed. An ATX heading
    (``## Title``) and a setext one (``Title`` over ``---`` or ``===``) both
    count; a setext heading is reported at its text line, as ``## Title``
    (or ``# Title``) so it compares like the ATX form. A fence closes only on
    a line of the same character, at least as long, with nothing after it."""
    found: List[Tuple[int, int, str]] = []
    fence: Optional[str] = None
    for i, raw in enumerate(lines):
        line = raw.rstrip("\r\n")
        stripped = line.strip()
        if fence:
            if stripped.startswith(fence) and not stripped.lstrip(fence[0]).strip():
                fence = None
            continue
        opening = _FENCE_RE.match(line)
        if opening and not (opening.group(1)[0] == "`" and "`" in opening.group(2)):
            fence = opening.group(1)
            continue
        if _HEADING_RE.match(line):
            text = " ".join(stripped.split())
            found.append((i, len(text) - len(text.lstrip("#")), text))
            continue
        underline = _SETEXT_RE.match(line)
        if underline and i > 0 and (not found or found[-1][0] != i - 1):
            above = lines[i - 1].rstrip("\r\n")
            if (above.strip() and not _HEADING_RE.match(above) and not _FENCE_RE.match(above)
                    and not _SETEXT_RE.match(above) and not _NOT_SETEXT_TEXT_RE.match(above)
                    and len(above) - len(above.lstrip(" ")) < 4):
                level = 1 if underline.group(1)[0] == "=" else 2
                found.append((i - 1, level, "#" * level + " " + " ".join(above.split())))
    return found


def _foreign_segments(interior: List[str], own_headings: set, own_lines: set,
                      offset: int) -> List[Tuple[int, int]]:
    """The (start, end) index ranges of ``interior`` that hold a section
    the template never wrote: a heading the rendered section (or an
    earlier template) does not have, and the lines under it up to the
    next such heading, the promise heading or the end marker. ``offset``
    turns an index into a file line number for ForeignTextError. No such
    heading -> [] (a hand-edit of promise's own section, restored).

    Every template opens with its heading, so a line above the first
    heading (or in a block with no heading at all) sits in no section:
    unless it is one of the rendered lines (``own_lines``, stripped), it is
    text adopt never wrote, and ForeignTextError names it rather than
    deleting it."""
    heads = _headings(interior)
    first_head = heads[0][0] if heads else len(interior)
    loose = [i for i in range(first_head)
             if interior[i].strip() and interior[i].strip() not in own_lines]
    if loose:
        raise ForeignTextError(offset + loose[0] + 1, offset + loose[-1] + 1)
    if not any(text not in own_headings for _, _, text in heads):
        return []
    if not any(text in own_headings for _, _, text in heads):
        raise ForeignTextError(offset + 1, offset + len(interior))
    above = [i for i in range(heads[0][0]) if interior[i].strip()]
    if above:
        raise ForeignTextError(offset + above[0] + 1, offset + above[-1] + 1)
    segments: List[Tuple[int, int]] = []
    own_level: Optional[int] = None
    for n, (i, level, text) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(interior)
        if text in own_headings:
            own_level = level
            continue
        if own_level is not None and level > own_level:
            # a heading under promise's own heading: a hand-edit, or a
            # section of its own? Not safe to guess.
            raise ForeignTextError(offset + i + 1, offset + end)
        own_level = None
        if segments and segments[-1][1] == i:
            segments[-1] = (segments[-1][0], end)
        else:
            segments.append((i, end))
    return segments


def apply_block(existing_text: Optional[str],
                rendered_section: str) -> Tuple[str, List[Dict[str, Any]], bool]:
    """Insert or replace the managed block; content outside it is untouched.

    No file, or a file with no markers at all: append the section after
    exactly one blank line. Exactly one begin followed by exactly one
    end: replace the block in place. Anything else — a begin with no
    end, an end with no begin, two begins, an end before its begin —
    raises MalformedMarkersError rather than guessing, because a wrong
    guess here deletes content a person wrote by hand.

    adopt only removes text adopt wrote: a section inside the markers
    that the template never wrote is kept, unchanged, just above the
    begin marker, and reported as ``{"lines": [first, last], "heading":
    ...}`` (line numbers in the file as it was). Text that cannot be told
    apart safely raises ForeignTextError. Returns the new text, the
    sections moved, and whether promise's own part of the block differed
    from the rendered form.
    """
    section_text = rendered_section.rstrip("\n")
    if not existing_text:
        return section_text + "\n", [], False

    lines = existing_text.splitlines(keepends=True)
    begin_lines, end_lines = _scan_markers(lines)

    if not begin_lines and not end_lines:
        # No existing block: append after exactly one blank line.
        return existing_text.rstrip("\n") + "\n\n" + section_text + "\n", [], False

    if len(begin_lines) == 1 and len(end_lines) == 1 and begin_lines[0] < end_lines[0]:
        begin_idx, end_idx = begin_lines[0], end_lines[0]
        before = "".join(lines[:begin_idx])
        after = "".join(lines[end_idx + 1 :])
        interior = lines[begin_idx + 1 : end_idx]
        rendered_lines = (section_text + "\n").splitlines()
        own_headings = {text for _, _, text in _headings(rendered_lines)} | set(EARLIER_SECTION_HEADINGS)
        own_lines = {l.strip() for l in rendered_lines} | set(EARLIER_SECTION_HEADINGS)
        segments = _foreign_segments(interior, own_headings, own_lines, begin_idx + 1)
        kept_own = list(interior)
        for start, end in reversed(segments):
            del kept_own[start:end]
        while segments and kept_own and not kept_own[-1].strip():
            kept_own.pop()  # the blank line that stood before a moved section
        block = [lines[begin_idx]] + kept_own + [lines[end_idx]]
        restored = [l.rstrip("\r\n") for l in block] != rendered_lines
        moved: List[Dict[str, Any]] = []
        chunks: List[str] = []
        # The file's own line ending, for the lines this edit adds: main()
        # hands in text with LF only, a direct caller may not.
        nl = "\r\n" if lines[begin_idx].endswith("\r\n") else "\n"
        for start, end in segments:
            chunk = interior[start:end]
            while chunk and not chunk[-1].strip():
                chunk = chunk[:-1]
            chunks.append("".join(chunk).rstrip("\r\n") + nl)
            first_line = begin_idx + 1 + start + 1
            moved.append({"lines": [first_line, first_line + len(chunk) - 1],
                          "heading": interior[start].strip()})
        if chunks:
            before_lines = before.splitlines()
            if before_lines and before_lines[-1].strip():
                before += nl if before.endswith("\n") else nl + nl
            before += nl.join(chunks) + nl
        section_out = section_text.replace("\n", nl) + nl
        return before + section_out + after, moved, restored

    raise MalformedMarkersError(begin_lines, end_lines)


def apply_claude_md(existing_text: Optional[str], rendered_section: str) -> str:
    """apply_block's new text alone."""
    return apply_block(existing_text, rendered_section)[0]


def has_managed_block(existing_text: Optional[str]) -> bool:
    """True when the text carries exactly one well-formed managed block."""
    if not existing_text:
        return False
    begin_lines, end_lines = _scan_markers(existing_text.splitlines(keepends=True))
    return len(begin_lines) == 1 and len(end_lines) == 1 and begin_lines[0] < end_lines[0]


def _detect_newline_and_bom(path: str) -> Tuple[str, bool]:
    """The file's dominant line ending and whether it opens with a UTF-8
    BOM, read from raw bytes so CRLF is never normalised away before it
    can be counted. Defaults to ("\\n", False) — plain UTF-8, no BOM —
    when the file cannot be read at all, which is the shape a brand new
    file is written in.
    """
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return "\n", False
    had_bom = raw.startswith(UTF8_BOM)
    if had_bom:
        raw = raw[len(UTF8_BOM) :]
    crlf_count = raw.count(b"\r\n")
    lf_count = raw.count(b"\n") - crlf_count  # bare LF, excluding CRLF's own LF
    dominant = "\r\n" if crlf_count > lf_count else "\n"
    return dominant, had_bom


def _encode_claude_md(new_text: str, dominant_newline: str, had_bom: bool) -> bytes:
    """The exact bytes to write for CLAUDE.md: new_text (canonical,
    "\\n"-delimited) re-expressed in the file's own dominant line ending,
    with its BOM reinstated if it had one."""
    if dominant_newline != "\n":
        new_text = new_text.replace("\n", dominant_newline)
    data = new_text.encode("utf-8")
    return (UTF8_BOM + data) if had_bom else data


def _new_file_mode() -> int:
    """The mode ``open(2)`` would give a brand new file under the current
    umask. Reading the umask means setting it and putting it back; that
    is not thread-safe, and is fine here because this script is
    single-threaded."""
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def _atomic_write_bytes(path: str, data: bytes) -> None:
    """Write data to path via a temporary file in the same directory,
    then os.replace — so a reader (or a crash) never observes a
    partially written file, and the write is a rename on every platform
    where the target and the temp file share a filesystem.

    Writes through a symlink rather than severing it: the target is
    ``os.path.realpath(path)``, so a ``CLAUDE.md -> AGENTS.md`` link
    keeps pointing at the file that now carries the section. An existing
    file keeps its own mode; a new file gets what ``open`` would have
    given it, never mkstemp's 0600.
    """
    path = os.path.realpath(path)
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    try:
        mode = stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        mode = _new_file_mode()
    fd, tmp_path = tempfile.mkstemp(prefix=".promise-adopt-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _unwritable_reason(path: str, label: str) -> Optional[str]:
    """Why ``path`` cannot be written as a regular file, or None.

    A path that exists but is not a regular file (a directory, say), or
    whose nearest existing ancestor is not a directory (``.claude`` is a
    file), is refused up front — never left to ``os.replace`` to
    traceback on.
    """
    if os.path.lexists(path) and not os.path.isfile(path):
        return f"{label} exists but is not a regular file: {path}"
    parent = os.path.dirname(path) or "."
    while not os.path.lexists(parent):
        next_parent = os.path.dirname(parent)
        if next_parent == parent:
            break
        parent = next_parent
    if os.path.lexists(parent) and not os.path.isdir(parent):
        return f"{label} cannot be created under {parent}: not a directory"
    return None


def _docs_home_reason(value: str) -> Optional[str]:
    """Why ``value`` cannot be recorded as docsHome, or None.

    docsHome is written into JSON and substituted into a CLAUDE.md line,
    so it must be one line, must not carry a marker string (which would
    break the managed block on the next run), must stay inside the
    project like every other configured path, and, since the CLAUDE.md
    block sends agents to it in shell lines, must hold only letters,
    digits, spaces and ``. _ - /`` and not start with ``-`` (orient's rule).
    """
    if "\n" in value or "\r" in value:
        return "--docs-home must be a single line"
    if BEGIN_PREFIX in value or END_MARKER in value:
        return "--docs-home must not contain a promise:begin/end marker"
    if orient._path_escapes(value):
        # orient's rule, not a second copy of it: absolute on either OS
        # (a drive letter included) or climbing out with '..'.
        return "--docs-home must be relative to the project root and must not escape it ('..')"
    if orient._path_unsafe(value):
        return f"--docs-home must hold only {orient.PATH_SAFE_WORDS}, and must not start with '-'"
    return None


def _refused(result: Dict[str, Any], reason: str) -> int:
    """Print the reason to stderr and the (unchanged) JSON result to
    stdout, and return exit 2 — nothing has been written."""
    print(f"adopt.py: {reason}", file=sys.stderr)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 2


def main(argv: Optional[list] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(
        prog="adopt.py",
        description="Write .claude/promise.config.json and insert the CLAUDE.md pointer section.",
    )
    parser.add_argument("--cwd", default=None, help="project root (default: current directory)")
    parser.add_argument("--dry-run", action="store_true", help="write nothing; print a unified diff to stderr")
    parser.add_argument("--docs-home", default=None, help="docsHome to record in a freshly written config")
    parser.add_argument("--policy", choices=("fast", "auto", "spec", "prototype"), default=None,
                        help="the decision policy the human chose, recorded as decisionPolicy in a freshly written "
                             "config (default auto; the alias prototype is written as fast); an existing "
                             "config is never changed, and the run says the policy was not applied")
    parser.add_argument("--run", default=None, metavar="CMD",
                        help="how this project runs promise's scripts (a pinned wrapper such as scripts/promise/run.sh), "
                             "recorded in a fresh config and named in the section")
    parser.add_argument("--no-config", action="store_true", help="skip writing the config file")
    parser.add_argument("--no-claude-md", action="store_true", help="skip the CLAUDE.md section")
    parser.add_argument(
        "--agents-md",
        action="store_true",
        help="also write the same managed section into AGENTS.md (Codex, Cursor, Copilot, Gemini CLI and "
        "others read it); skipped when AGENTS.md and CLAUDE.md are the same file",
    )
    parser.add_argument(
        "--github-templates",
        action="store_true",
        help="also copy templates/github/ into .github/ (the capability issue template and the pull request "
        "template), each only where the project has none; a map: false project takes them too",
    )
    args = parser.parse_args(argv)
    # prototype is an alias of fast: read, never written (outcome-framework.md § Decision policy)
    policy = "fast" if args.policy == "prototype" else (args.policy or "auto")

    cwd = os.path.abspath(args.cwd) if args.cwd else os.path.abspath(os.getcwd())
    if not os.path.isdir(cwd):
        print(f"adopt.py: no such directory: {cwd}", file=sys.stderr)
        return 2

    skill_dir = orient.get_skill_dir()
    orientation = orient.build_orientation(None, cwd)

    effective_docs_home = args.docs_home or (
        orientation["docsHome"] if orientation["docsHomeSource"] != "none" else None
    )

    # --- Resolve where the config lives (or would live), never shadowing
    # an already-loaded one at either the primary or the fallback path
    # (architecture.md §6's own load order) with a second, poorer copy. ---
    config_path = os.path.join(cwd, ".claude", "promise.config.json")
    config_reason_skipped: Optional[str] = None
    will_write_new_config = False

    if orientation["config"]["loaded"] and orientation["config"]["path"]:
        config_path = orientation["config"]["path"]
        if not args.no_config:
            config_reason_skipped = (
                f"config already loaded from {config_path}; not writing a second one"
            )
    elif not args.no_config:
        if os.path.isfile(config_path):
            config_reason_skipped = f"config already exists at {config_path}; not overwriting"
        else:
            will_write_new_config = True

    claude_md_path = orientation["claudeMd"]["path"] or os.path.join(cwd, "CLAUDE.md")
    agents_md_path = os.path.join(cwd, "AGENTS.md")
    same_file = (
        os.path.exists(agents_md_path)
        and os.path.exists(claude_md_path)
        and os.path.realpath(agents_md_path) == os.path.realpath(claude_md_path)
    )
    # The section's home is AGENTS.md when CLAUDE.md imports it and holds no
    # section itself, or when there is no CLAUDE.md and AGENTS.md holds one.
    if orientation["claudeMd"]["path"]:
        in_agents = (not orient._has_marker(claude_md_path)
                     and orient.imports_agents_md(claude_md_path, cwd))
    else:
        in_agents = orient._has_marker(agents_md_path)
    in_agents = in_agents and not same_file
    write_claude_md = not args.no_claude_md and not in_agents
    do_agents_md = (args.agents_md or (in_agents and not args.no_claude_md)) and not same_file
    if in_agents and not args.no_claude_md:
        print("adopt.py: the promise section lives in AGENTS.md (CLAUDE.md imports it, or there is no "
              "CLAUDE.md); CLAUDE.md is left as it is", file=sys.stderr)

    refused_result = {
        "configWritten": False,
        "configPath": config_path,
        "claudeMdWritten": False,
        "claudeMdPath": claude_md_path,
        "docsHome": effective_docs_home,
        "changed": False,
        "dryRun": args.dry_run,
    }

    # --- Refuse anything that could not be written safely, before either
    # file is touched: a wrong-typed path, a docsHome that would break the
    # managed block, a CLAUDE.md that is not text. ---
    if args.docs_home is not None:
        reason = _docs_home_reason(args.docs_home)
        if reason is not None:
            return _refused(refused_result, reason)
        if "\\" in args.docs_home:
            # The config contract asks for forward slashes; orient would
            # otherwise warn about this file on every later run.
            effective_docs_home = args.docs_home.replace("\\", "/")
            print(
                f"adopt.py: --docs-home uses backslashes; recorded as {effective_docs_home!r}",
                file=sys.stderr,
            )
        if orientation["config"]["loaded"] and effective_docs_home != orientation["docsHome"]:
            return _refused(
                refused_result,
                f"--docs-home {effective_docs_home!r} disagrees with the loaded config's "
                f"docsHome {orientation['docsHome']!r} ({orientation['docsHomeSource']}); "
                "edit the config, then rerun without the flag",
            )
    elif effective_docs_home and ("\n" in effective_docs_home or "\r" in effective_docs_home):
        return _refused(refused_result, "docsHome from the config must be a single line")

    # A detected docs folder that holds no outcome doc (design docs in
    # another shape, say) is not a docs home to pin by default: say so, and
    # refuse a run that would name it -- in a fresh config, or in the
    # CLAUDE.md or AGENTS.md block that sends every agent there -- until the
    # user picks a folder. A dry run refuses too: its diff would preview a change the
    # real run refuses, for the user to approve.
    foreign_docs = orientation.get("docsHomeForeignDocs")
    if args.docs_home is None and orientation["docsHomeSource"] == "detected" and foreign_docs:
        warning = orient.foreign_docs_warning(orientation["docsHome"], foreign_docs)
        if will_write_new_config or write_claude_md or do_agents_md:
            if orientation["config"]["loaded"]:
                how = (f"set docsHome in {orientation['config']['path']} to the folder outcome docs "
                       "live in, then run again")
            else:
                how = "pass --docs-home <dir> to choose the folder outcome docs live in, then run again"
            return _refused(refused_result, f"{warning}; {how}")
        print(f"adopt.py: {warning}", file=sys.stderr)

    if will_write_new_config:
        reason = _unwritable_reason(config_path, "config path")
        if reason is not None:
            return _refused(refused_result, reason)
    if write_claude_md:
        reason = _unwritable_reason(claude_md_path, "CLAUDE.md")
        if reason is not None:
            return _refused(refused_result, reason)
    if do_agents_md:
        reason = _unwritable_reason(agents_md_path, "AGENTS.md")
        if reason is not None:
            return _refused(refused_result, reason)

    # --run is recorded in a fresh config only: adopt never edits an existing one, so
    # there it names the change to make, and the section keeps the config's value.
    asked_run = args.run.strip() if args.run and args.run.strip() else None
    run_command = orientation.get("run")
    if asked_run and will_write_new_config:
        run_command = asked_run
    elif asked_run and asked_run != run_command:
        where = orientation["config"]["path"] or ".claude/promise.config.json"
        why = ("the config exists and adopt never edits it" if orientation["config"]["loaded"]
               else "no config is written this run")
        print(f"adopt.py: --run is not recorded: {why}; set \"run\": {json.dumps(asked_run)} in {where}, "
              "then run adopt again", file=sys.stderr)

    # --- Resolve the CLAUDE.md edit up front, without writing anything,
    # so a malformed-marker file can refuse the whole run before either
    # file is touched. ---
    claude_md_new_text: Optional[str] = None
    claude_md_moved: List[Dict[str, Any]] = []
    claude_md_restored = False
    claude_md_marker_error: Optional[str] = None
    existing_claude_md_text: Optional[str] = None
    if os.path.isfile(claude_md_path):
        try:
            existing_claude_md_text = orient.read_text_tolerant(claude_md_path)
        except UnicodeDecodeError as exc:
            return _refused(refused_result, f"CLAUDE.md is not UTF-8 text ({claude_md_path}): {exc}")
        except OSError as exc:
            return _refused(refused_result, f"cannot read CLAUDE.md ({claude_md_path}): {exc}")

    if write_claude_md:
        config_display, framework_display = display_paths(cwd, config_path, orientation)
        rendered = render_section(effective_docs_home, config_display, framework_display, skill_dir, run_command)
        try:
            claude_md_new_text, claude_md_moved, claude_md_restored = apply_block(existing_claude_md_text, rendered)
        except MalformedMarkersError as exc:
            claude_md_marker_error = str(exc)
        except ForeignTextError as exc:
            claude_md_marker_error = "CLAUDE.md: " + str(exc)

    if claude_md_marker_error is not None:
        return _refused(refused_result, claude_md_marker_error)

    # The same managed block, in AGENTS.md: the file most other agents read.
    agents_md_existing: Optional[str] = None
    agents_md_new_text: Optional[str] = None
    agents_md_moved: List[Dict[str, Any]] = []
    if do_agents_md:
        if os.path.isfile(agents_md_path):
            try:
                agents_md_existing = orient.read_text_tolerant(agents_md_path)
            except UnicodeDecodeError as exc:
                return _refused(refused_result, f"AGENTS.md is not UTF-8 text ({agents_md_path}): {exc}")
            except OSError as exc:
                return _refused(refused_result, f"cannot read AGENTS.md ({agents_md_path}): {exc}")
        config_display, framework_display = display_paths(cwd, config_path, orientation)
        rendered = render_section(effective_docs_home, config_display, framework_display, skill_dir, run_command)
        try:
            agents_md_new_text, agents_md_moved, _ = apply_block(agents_md_existing, rendered)
        except (MalformedMarkersError, ForeignTextError) as exc:
            return _refused(refused_result, "AGENTS.md: " + str(exc))

    # --- Everything above was read-only. From here, actually write (or,
    # under --dry-run, only report and diff). ---
    config_written = False
    config_diff = ""

    if config_reason_skipped is not None:
        print(f"adopt.py: {config_reason_skipped}", file=sys.stderr)
        if args.policy is not None:
            print(f"adopt.py: the existing config is kept, so --policy {policy} was not applied; "
                  "a human changes decisionPolicy in the config", file=sys.stderr)
    elif will_write_new_config:
        if not effective_docs_home:
            print(
                "adopt.py: no docs folder detected and no --docs-home given; the config "
                "will pin no docsHome and every later `new` will ask where docs live — "
                "pass --docs-home <dir> (adopt.md's default is docs/designs)",
                file=sys.stderr,
            )
        new_config = build_config(effective_docs_home, orientation["commands"],
                                  orient.skill_version(skill_dir), policy)
        if run_command:
            ordered: Dict[str, Any] = {}
            for key, value in new_config.items():
                if key == "map":
                    ordered["run"] = run_command
                ordered[key] = value
            new_config = ordered
        new_config_text = json.dumps(new_config, indent=2, ensure_ascii=False) + "\n"
        if args.dry_run:
            rel = os.path.relpath(config_path, cwd)
            config_diff = "".join(
                difflib.unified_diff([], new_config_text.splitlines(keepends=True), fromfile=rel, tofile=rel)
            )
        else:
            _atomic_write_bytes(config_path, new_config_text.encode("utf-8"))
            config_written = True

    claude_md_written = False
    claude_md_changed = False
    claude_md_diff = ""

    if write_claude_md:
        claude_md_changed = existing_claude_md_text != claude_md_new_text
        if claude_md_changed:
            if has_managed_block(existing_claude_md_text) and (claude_md_restored or not claude_md_moved):
                print(
                    "adopt.py: the managed promise block in CLAUDE.md differed from the rendered "
                    "form; it is restored (content outside the markers is untouched)",
                    file=sys.stderr,
                )
            if args.dry_run:
                rel = os.path.relpath(claude_md_path, cwd)
                claude_md_diff = "".join(
                    difflib.unified_diff(
                        (existing_claude_md_text or "").splitlines(keepends=True),
                        (claude_md_new_text or "").splitlines(keepends=True),
                        fromfile=rel,
                        tofile=rel,
                    )
                )
            else:
                dominant_newline, had_bom = _detect_newline_and_bom(claude_md_path)
                data = _encode_claude_md(claude_md_new_text or "", dominant_newline, had_bom)
                _atomic_write_bytes(claude_md_path, data)
                claude_md_written = True

    agents_md_written = False
    agents_md_changed = False
    agents_md_diff = ""
    if do_agents_md:
        agents_md_changed = agents_md_existing != agents_md_new_text
        if agents_md_changed:
            if args.dry_run:
                rel = os.path.relpath(agents_md_path, cwd)
                agents_md_diff = "".join(
                    difflib.unified_diff(
                        (agents_md_existing or "").splitlines(keepends=True),
                        (agents_md_new_text or "").splitlines(keepends=True),
                        fromfile=rel,
                        tofile=rel,
                    )
                )
            else:
                dominant_newline, had_bom = _detect_newline_and_bom(agents_md_path)
                data = _encode_claude_md(agents_md_new_text or "", dominant_newline, had_bom)
                _atomic_write_bytes(agents_md_path, data)
                agents_md_written = True

    # The GitHub templates: each copied only where the project has none of its own.
    templates_written: List[str] = []
    templates_diff = ""
    if args.github_templates:
        present = orient.github_templates(cwd)
        for key, src, dest in (("issue", "ISSUE_TEMPLATE/capability.md", orient.ISSUE_TEMPLATE),
                               ("pullRequest", "pull_request_template.md", ".github/pull_request_template.md")):
            if present[key]:
                print(f"adopt.py: {present[key]} exists; left as it is (issue and pr add their block to the "
                      "project's own template)", file=sys.stderr)
                continue
            with open(os.path.join(skill_dir, "templates", "github", src), "r", encoding="utf-8") as fh:
                text = fh.read()
            if args.dry_run:
                templates_diff += "".join(difflib.unified_diff([], text.splitlines(keepends=True),
                                                               fromfile=dest, tofile=dest))
            else:
                _atomic_write_bytes(os.path.join(cwd, dest), text.encode("utf-8"))
            templates_written.append(dest)

    if args.dry_run:
        changed = bool(will_write_new_config or claude_md_changed or agents_md_changed or templates_written)
    else:
        changed = bool(config_written or claude_md_written or agents_md_written or templates_written)

    # adopt only removes text adopt wrote: say what it kept and moved.
    moved_above_block: List[Dict[str, Any]] = []
    for path, moved in ((claude_md_path, claude_md_moved if write_claude_md else []),
                        (agents_md_path, agents_md_moved)):
        for item in moved:
            moved_above_block.append({"path": path, **item})
        if moved:
            spans = "; ".join(f"{m['heading']} (lines {m['lines'][0]}-{m['lines'][1]})" for m in moved)
            verb = "would move" if args.dry_run else "moved"
            print(f"adopt.py: {os.path.basename(path)}: the promise block held text adopt did not write: "
                  f"{spans}; {verb} it, unchanged, to just above {BEGIN_PREFIX}", file=sys.stderr)

    diff_text = config_diff + claude_md_diff + agents_md_diff + templates_diff
    if args.dry_run and diff_text:
        sys.stderr.write(diff_text)

    result = {
        "configWritten": config_written,
        "configPath": config_path,
        "claudeMdWritten": claude_md_written,
        "claudeMdPath": claude_md_path,
        "docsHome": effective_docs_home,
        "changed": changed,
        "dryRun": args.dry_run,
    }
    if args.agents_md or in_agents:
        result["agentsMdWritten"] = agents_md_written
        result["agentsMdPath"] = agents_md_path if do_agents_md else claude_md_path
    if moved_above_block:
        result["movedAboveBlock"] = moved_above_block
    if args.github_templates:
        result["githubTemplatesWritten"] = templates_written if not args.dry_run else []
        result["githubTemplatesToWrite"] = templates_written if args.dry_run else []
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
