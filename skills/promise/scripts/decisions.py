#!/usr/bin/env python3
"""Collect the decisions waiting on a human into one sheet, and write the answers back.

    python3 decisions.py sheet [DOC ...] [--docs-home DIR] [--asks FILE] [--blocking-only] [--cwd DIR] [--out FILE] [--json]
    python3 decisions.py apply ANSWERS [--cwd DIR] [--date YYYY-MM-DD] [--by NAME] [--dry-run] [--json]
    python3 decisions.py promote DOC --decision ID [--decision ID ...] --by NAME [--reason TEXT] [--date YYYY-MM-DD] [--dry-run] [--json]
    python3 decisions.py policy DOC --to fast|auto|spec --by NAME [--promote ID,ID] [--date YYYY-MM-DD] [--dry-run] [--json]
    python3 decisions.py policy --open --to fast|auto|spec --by NAME [--docs-home DIR] [--date YYYY-MM-DD] [--dry-run] [--json]
    python3 decisions.py recheck DOC [--date YYYY-MM-DD] [--json]

``sheet`` reads the §9 open questions of each outcome doc (the DOC paths given, else
every doc under docsHome) and keeps the unanswered ones. A question is answered once
a line starting ``Answer (YYYY-MM-DD`` or ``Answered``, bare or in Markdown bold or
italic (``**Answer (YYYY-MM-DD, name):**``), follows it before the next question or
the end of §9, blank lines between them included. ``--asks`` adds a JSON
file the agent wrote: the sheet's ``title`` and ``intro``, and ``items`` that either
enrich a §9 question (same ``id``, ``<doc path>#Qn``: its ``options``, ``detail``,
``code``, ``image``, ``links``, and the brief: ``why``, ``blocks``, ``ifNoAnswer``,
``evidence``, ``example``) or add a decision that lives outside the docs (kind
``question``, ``approve``, ``input`` or ``confirm``). The question text, owner and
BLOCKING flag always come from the doc, never from the asks file.

Each item gets a ``surface`` hint, and the sheet gets one too: ``ask-questions`` when
every item fits the host's plain question prompt (at most four items, each a
``question`` or ``approve`` with at most four options and no detail, code or image),
else ``rich``. A rich sheet lists ``warnings``: an item with no ``why`` or
``blocks``, an option with no ``because`` or ``then``. Each doc's §0 outcome, rules
and signal go in ``docs``, verbatim, so the page can show what the doc promises.
``--md PATH`` writes the same items as plain Markdown, for agents and editors; it is
never sent to the human, and ``--out`` no longer writes it beside the page.
The one-line summary lists the first five BLOCKING items, so an agent can paste
them into a chat as they are. ``--out FILE`` renders ``templates/decision-sheet.html`` with the
sheet embedded, in the form the Artifact tool publishes (no doctype: the publisher
wraps it). ``--json`` prints the sheet, each item with its lettered ``replies`` (code, label, the
value it records, Recommended) and ``replyWords`` (whether words may stand in for a
letter), for a surface that draws its own controls. With neither, a one-line summary.

``apply`` reads answers in the page's format (``format: promise-answers``), from a
JSON file or from pasted text that holds the JSON in a fence (``-``: standard input), or
the promise mod's pane's picks (``format: promise-picks``: the sheet and one pick per item,
read through ``answer_entry`` as a chat reply is).
An answer naming a doc and a question is appended under that question in §9 as one line,
``Answer (<date>, <by>): <text>``; nothing else in the doc changes, §0 and the
Status line included. An answer already there is not written twice. A doc path
outside ``--cwd`` is refused. Answers that name no doc question (approvals, values,
to-dos) are returned under ``forAgent`` for the agent to act on.

The agent decisions in §8 (rows whose Owner is ``agent``, State ``provisional``;
outcome-framework.md § Decision policy) join the sheet as one read-only group,
``Decided for you``: kind ``decided``, never counted in the round, never picked by
``all recommended``. Its one action is ``Ask me instead``. ``apply`` turns that
answer into a new BLOCKING §9 question (appended, as answers are) and marks the
row ``State: asked Qn``. ``promote`` does the same for rows the agent names (the
arm re-check, a policy change). ``policy`` writes the ``Decision policy:`` header
line the human picked and logs it in §8: moving to ``spec`` promotes every
provisional row; moving from ``fast`` to ``auto`` promotes the rows named in
``--promote`` and lists the rest for the agent to judge; relaxing never answers an
open §9 question. ``policy --open`` does the same for every doc at draft, agreed or
building whose header has no ``Decision policy:`` line (orient's ``legacyPolicyDocs``),
on one human yes; shipped and superseded docs are left alone, the edits stay in the
working tree for the human to commit, and ``--dry-run`` lists them. ``recheck`` lists the provisional rows due at arm: a review
trigger of ``before arm`` or one whose date has come, and a reversible-until that
closes at arm or whose date has come.

Exit codes: 0 done; 2 usage or input error (one line on stderr, never a traceback).
"""

from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
import os
import re
import sys
import zlib
from typing import Any, Dict, List, Optional, Tuple

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import lint_outcome  # noqa: E402  (sibling-script import; see path insert above)
from lint_outcome import ANSWER_RE, QUESTION_RE, parse_questions  # noqa: E402,F401  (§9 is read one way)
import orient  # noqa: E402

TEMPLATE_RELATIVE_PATH = os.path.join("..", "templates", "decision-sheet.html")
SHEET_MARKER = "__PROMISE_SHEET__"
KINDS = ("question", "approve", "input", "confirm")
BRIEF_KEYS = ("why", "blocks", "ifNoAnswer", "example")
ENRICH_KEYS = ("options", "detail", "code", "image", "imageAlt", "links", "evidence", "plain", "research",
               "sameAs", "group", "groupTitle") + BRIEF_KEYS
EXTRA_KEYS = ENRICH_KEYS + ("id", "kind", "text", "owner", "blocking",
                            "proposed", "inputType", "placeholder", "doneLabel")
# What a research agent found for an open question (references/research.md).
PILES = ("answered", "same-as", "stale", "needs-you")
RESEARCHED = ("answered", "stale")  # checked by research: one "Accept all" group, outside the round limit
RESEARCH_GROUP = "Checked by research"
# The agent decisions of the docs' §8 (outcome-framework.md § Decision policy): read-only,
# outside the round, one action (ask me instead).
DECIDED_GROUP = "Decided for you"
ASK_INSTEAD = "Ask me instead"
OPTION_KEYS = ("label", "recommended", "detail", "because", "commits", "think", "then")
ASK_LIMIT = 4
# One round of a sheet: what a person can answer in one sitting. The rest come in later
# rounds, built from what is still open once these answers are applied.
ROUND_LIMIT = 12
# The Outcome Framework's sections, so a bare "§2" reaches the reader as "§2 Outcome".
SECTION_NAMES = {0: "TLDR", 1: "Problem", 2: "Outcome", 3: "Worked examples", 4: "Invariants",
                 5: "Mechanism", 6: "Acceptance", 7: "Build phases", 8: "Decisions", 9: "Open questions",
                 10: "Out of scope"}
SECTION_REF_RE = re.compile(r"§\s?(\d{1,2})(?![\w]|\.\d)")
# The item and option fields a person reads; code, evidence refs and links are left alone.
READ_FIELDS = ("text", "why", "blocks", "ifNoAnswer", "example", "detail", "doneLabel", "placeholder")
OPTION_READ_FIELDS = ("label", "detail", "because", "commits", "think", "then")
# A number a reader must remember to follow: fine only with its words right after it,
# as in `#87 ("Muted channels still badge")`, `Q4: the thread question`, `item 3 — the badge`.
WORDS_AFTER = r"(?!\s*(?:\(|:|\"|“|‘|'|—|–|-\s))"
BARE_REFS = (
    # "Q3 2026" is a quarter; "#1 priority" a rank.
    (re.compile(r"(?<![\w#])Q\d+\b(?!\s*\d{4})" + WORDS_AFTER), "a question number (a quarter takes its year)"),
    (re.compile(r"(?<![\w&/#])#\d+\b(?!\s+(?:priority|choice|pick|place|spot|rank)\b)" + WORDS_AFTER),
     "an issue or pull request number"),
    # a map row id: CAP-12, or one from an issue, pull request or Linear key (CAP-i1890a, CAP-ENG-421a)
    (re.compile(r"\b(?:AT-\d+|CAP-(?:[ip]\d+[a-z]{1,2}|[A-Z][A-Z0-9]+-\d+[a-z]{1,2}|\d+))(?:\.\d+)?\b(?!\.\d)"
                + WORDS_AFTER), "an acceptance or map row id"),
    (re.compile(r"\b(?:item|line|row|point|number|rule|note|question|option|step|case)\s+\d+\b" + WORDS_AFTER,
                re.I), "a numbered item"),
)
# A numbered name of the product's own ("mode 3", "tier 2") needs its meaning in `words`,
# or words right beside it, as the issue's first screen defines one.
VARIANT_RE = re.compile(r"\b(?:mode|tier|level|stage|variant)\s+\d+\b(?!\.\d)" + WORDS_AFTER, re.I)
# Paths belong in evidence, behind the fold; the card says what they show.
# A path has a folder or a line number: "Next.js" is a product, "db/schema.ts" and "schema.ts:623" are paths.
_EXT = r"\.(?:ts|tsx|js|jsx|mjs|py|rb|go|rs|java|kt|swift|json|ya?ml|toml|md|sql|sh|css|html)"
PATH_RE = re.compile(r"(?<![\w`])(?:[\w.-]+/)+[\w.-]+" + _EXT + r"(?::\d+(?:[-,]\s*\d+)*)?\b"
                     r"|(?<![\w`/])[\w.-]+" + _EXT + r":\d+(?:[-,]\s*\d+)*\b")
CARD_FIELDS = ("text", "why", "blocks", "ifNoAnswer")
TEXT_WORDS, WHY_WORDS = 35, 60
LINK_TARGET_RE = re.compile(r"\]\([^)\s]*\)|https?://\S+")  # a link's URL is not text a person reads
RECOMMENDED_RE = re.compile(r"\brecommended\b", re.I)
UNSHOWN_LINES_RE = re.compile(r"\b(?:each|every) line\b|\bline by line\b|\bas written\b", re.I)
VALUE_LIMIT = 2000
SUMMARY_LIMIT = 5

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
FENCED_JSON_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.S)


class InputError(Exception):
    """A bad argument or input file: reported as one line, exit 2."""


# ---------------------------------------------------------------------------
# Reading §9
# ---------------------------------------------------------------------------


def doc_header(lines: List[str]) -> Tuple[str, str]:
    title, status = "", ""
    for line in lint_outcome.unfenced(lines)[:40]:
        if not title and line.startswith("# "):
            title = line[2:].strip()
        m = lint_outcome.STATUS_RE.match(line)
        if m and not status:
            status = m.group(1)
    return title, status


def find_docs(cwd: str, paths: List[str], docs_home_arg: Optional[str]) -> List[str]:
    if paths:
        docs = []
        for p in paths:
            full = p if os.path.isabs(p) else os.path.join(cwd, p)
            if not os.path.isfile(full):
                raise InputError(f"no such doc: {p}")
            docs.append(full)
        return docs
    home = docs_home_arg or orient.build_orientation(None, cwd).get("docsHome")
    if not home:
        raise InputError("no docs home; pass --docs-home or name the docs")
    home = home if os.path.isabs(home) else os.path.join(cwd, home)
    if not os.path.isdir(home):
        raise InputError(f"docs home is not a folder: {home}")
    docs = []
    for root, dirs, files in os.walk(home):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if name.endswith(".md") and name.lower() != "readme.md":
                docs.append(os.path.join(root, name))
    return docs


def rel(cwd: str, path: str) -> str:
    return os.path.relpath(path, cwd).replace(os.sep, "/")


# ---------------------------------------------------------------------------
# The sheet
# ---------------------------------------------------------------------------


def _string(value: Any, where: str) -> str:
    if not isinstance(value, str):
        raise InputError(f"{where} must be a string")
    return value


def _clean_option(opt: Any, where: str) -> Dict[str, Any]:
    if not isinstance(opt, dict) or not isinstance(opt.get("label"), str) or not opt["label"].strip():
        raise InputError(f"{where} needs a non-empty label")
    out: Dict[str, Any] = {}
    for k in OPTION_KEYS:
        if k in opt:
            out[k] = bool(opt[k]) if k == "recommended" else _string(opt[k], f"{where}.{k}")
    return out


def _clean_fields(src: Dict[str, Any], keys: Tuple[str, ...], where: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in keys:
        if k not in src:
            continue
        v = src[k]
        if k == "options":
            if not isinstance(v, list):
                raise InputError(f"{where}.options must be a list")
            out[k] = [_clean_option(o, f"{where}.options[{n}]") for n, o in enumerate(v)]
            if sum(1 for o in out[k] if o.get("recommended")) > 1:
                raise InputError(f"{where}.options marks more than one option Recommended")
        elif k == "links":
            if not isinstance(v, list):
                raise InputError(f"{where}.links must be a list")
            out[k] = [{"label": _string(l.get("label", l.get("url", "")), f"{where}.links"),
                       "url": _string(l.get("url", ""), f"{where}.links")}
                      for l in v if isinstance(l, dict)]
        elif k == "evidence":
            if not isinstance(v, list) or not all(isinstance(e, dict) for e in v):
                raise InputError(f"{where}.evidence must be a list of objects")
            out[k] = [{"ref": _string(e.get("ref", ""), f"{where}.evidence.ref"),
                       "note": _string(e.get("note", ""), f"{where}.evidence.note")} for e in v]
        elif k == "blocking":
            out[k] = bool(v)
        elif k == "proposed":
            if not isinstance(v, (str, int, float)) or isinstance(v, bool):
                raise InputError(f"{where}.proposed must be a string or a number")
            out[k] = v
        elif k == "image":
            v = _string(v, f"{where}.image")
            if not (v.startswith("data:image/") or v.startswith("https://")):
                raise InputError(f"{where}.image must be a data:image/ URI or an https:// URL")
            out[k] = v
        else:
            out[k] = _string(v, f"{where}.{k}")
    return out


def load_asks(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    try:
        data = json.loads(orient.read_text_tolerant(path))
    except (OSError, ValueError) as exc:
        raise InputError(f"could not read --asks {path}: {exc}")
    if not isinstance(data, dict):
        raise InputError("--asks must hold a JSON object")
    items = data.get("items", [])
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        raise InputError("--asks items must be a list of objects")
    return data


def surface_for(item: Dict[str, Any]) -> str:
    if item["kind"] not in ("question", "approve"):
        return "rich"
    if len(item.get("options", [])) > ASK_LIMIT or any(item.get(k) for k in ("detail", "code", "image")):
        return "rich"
    return "ask-questions"


def build_sheet(cwd: str, docs: List[str], asks: Dict[str, Any], blocking_only: bool,
                only: Optional[List[str]] = None, limit: Optional[int] = ROUND_LIMIT) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    by_id: Dict[str, Dict[str, Any]] = {}
    doc_briefs: Dict[str, Dict[str, Any]] = {}
    decided: List[Dict[str, Any]] = []
    for path in docs:
        try:
            lines = orient.read_text_tolerant(path).splitlines()
        except (OSError, ValueError) as exc:
            raise InputError(f"could not read {rel(cwd, path)}: {exc}")
        title, status = doc_header(lines)
        doc_briefs[rel(cwd, path)] = doc_brief(lines, title, status)
        for q in parse_questions(lines):
            if q["answered"] or (blocking_only and not q["blocking"]):
                continue
            item = {
                "id": f"{rel(cwd, path)}#{q['q']}", "kind": "question", "doc": rel(cwd, path), "q": q["q"],
                "docTitle": title, "docStatus": status, "owner": q["owner"], "blocking": q["blocking"],
                "text": q["text"],
            }
            if q["blocking"]:
                item["ifNoAnswer"] = "The doc stays at draft until this is answered."
            items.append(item)
            by_id[item["id"]] = item
        if not blocking_only:
            decided += decided_items(rel(cwd, path), lines, title, status)
    doc_ids = set(by_id)
    for n, extra in enumerate(asks.get("items", [])):
        where = f"--asks items[{n}]"
        item_id = extra.get("id")
        if not isinstance(item_id, str) or not item_id.strip():
            raise InputError(f"{where} needs an id")
        if item_id in doc_ids:
            by_id[item_id].update(_clean_fields(extra, ENRICH_KEYS, where))
            continue
        if "#" in item_id and item_id.split("#", 1)[0].endswith(".md"):
            # names a doc question that is answered, filtered out, or not there: never invent one
            continue
        if item_id in by_id:
            raise InputError(f"{where}: id {item_id!r} is used twice")
        if extra.get("kind") not in KINDS:
            raise InputError(f"{where}: kind must be one of {', '.join(KINDS)}")
        if not isinstance(extra.get("text"), str) or not extra["text"].strip():
            raise InputError(f"{where} needs text")
        item = _clean_fields(extra, EXTRA_KEYS, where)
        items.append(item)
        by_id[item_id] = item
    if only:
        missing = [i for i in only if i not in by_id and i not in {d["id"] for d in decided}]
        if missing:
            raise InputError("--only names no open item: " + ", ".join(missing)
                             + " (an answered question is not open; check the id against the doc's §9)")
        wanted = set(only)
        items = [i for i in items if i["id"] in wanted]
        decided = [d for d in decided if d["id"] in wanted]
    items = _fold_same_as(items, by_id)
    for i in items:
        if i.get("research") in RESEARCHED and i.get("blocking") is True and i.get("group") == RESEARCH_GROUP:
            i.pop("group")  # a BLOCKING question, even one research answered, gets its own card in the round
    researched = [i for i in items if in_research_group(i)]
    for i in researched:
        i.setdefault("group", RESEARCH_GROUP)
    items = [i for i in items if not in_research_group(i)]
    open_items, open_blocking = len(items), sum(1 for i in items if i.get("blocking") is True)
    unresearched = sum(1 for i in items if i["kind"] == "question" and not i.get("research"))
    if limit and not only and len(items) > limit:
        # BLOCKING first, then the rest in the order found; the stable sort keeps each doc's
        # BLOCKING questions together, so a round can clear a doc's blockers and let it move on.
        items = sorted(items, key=lambda i: 0 if i.get("blocking") is True else 1)[:limit]
    # What research answered is checked in one group after the round, whatever its size;
    # what the agent decided is shown after that, read-only, whatever its size.
    items = items + researched + decided
    for item in items:
        if isinstance(item.get("plain"), str) and not item["plain"].strip():
            item.pop("plain")
        if item.get("plain") and item.get("doc"):
            # The question in plain words on the card; the doc's own words stay one fold down.
            item["docText"], item["text"] = item["text"], item.pop("plain")
        elif "plain" in item:
            item["text"] = item.pop("plain") or item["text"]  # an asks item's own text is already its words
        _name_sections(item, READ_FIELDS)
        for o in item.get("options", []):
            _name_sections(o, OPTION_READ_FIELDS)
        item["surface"] = surface_for(item)
        if item.get("options"):
            # The order the page and the Markdown twin both show: Recommended first,
            # then "None of these" (null), then the rest. A reply "2" is choices[1].
            ordered = sorted(item["options"], key=lambda o: not o.get("recommended"))
            item["choices"] = [ordered[0]["label"], None] + [o["label"] for o in ordered[1:]]
    used = {i["doc"] for i in items if i.get("doc")}
    glossary, glossary_notes = map_glossary(cwd)
    used_words, word_notes = sheet_words(asks.get("words"), items, glossary or [], glossary is not None)
    digest = hashlib.sha256(json.dumps(items, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    # What the agent decided is a list to glance at, not a question: it never makes a
    # round of one or two plain questions into a page.
    asked = [i for i in items if i["kind"] != "decided"]
    surface = ("ask-questions" if asked and len(asked) <= ASK_LIMIT and all(
        i["surface"] == "ask-questions" for i in asked) else "rich") if items else "none"
    outside = len(researched) + len(decided)  # shown after the round, never counted in it
    counts = {"items": len(items),
              "blocking": sum(1 for i in items if i.get("blocking") is True and not in_research_group(i)),
              "later": open_items - (len(items) - outside),
              "laterBlocking": open_blocking - sum(1 for i in items if i.get("blocking") is True
                                                   and not in_research_group(i)),
              "round": len(items) - outside,
              "unresearched": unresearched,
              "researched": len(researched),
              "settledTogether": sum(len(i.get("alsoAnswers", [])) for i in items)}
    if decided:
        counts["decided"] = len(decided)
    return {
        "format": "promise-sheet", "version": 1, "id": digest,
        "title": name_sections(_string(asks.get("title", "Decisions waiting on you"), "--asks title")),
        "intro": name_sections(_string(asks.get("intro", ""), "--asks intro")),
        "surface": surface,
        "counts": counts,
        "docs": {k: v for k, v in doc_briefs.items() if k in used},
        "warnings": (thin_warnings(items) if surface == "rich" else []) + glossary_notes + word_notes,
        "words": used_words,
        "unclear": unclear_findings(items, used_words),
        "items": items,
    }


def decision_key(row_id: str) -> str:
    """``D3`` for a §8 row numbered ``3`` (or already written ``D3``): the part of a
    decided item's id after the ``#``, as ``Q3`` is for a question."""
    text = row_id.strip()
    return text.upper() if text[:1] in ("D", "d") and text[1:].isdigit() else f"D{text}"


def decided_items(doc: str, lines: List[str], title: str, status: str) -> List[Dict[str, Any]]:
    """The doc's provisional agent decisions (§8 rows whose Owner is ``agent``), as
    read-only sheet items: a generated view of §8, never a second copy of it."""
    out = []
    for r in lint_outcome.parse_agent_decisions(lines):
        if r["state"] != "provisional":
            continue
        f = r["fields"]
        item = {"id": f"{doc}#{decision_key(r['id'])}", "kind": "decided", "doc": doc,
                "decision": r["id"], "docTitle": title, "docStatus": status, "group": DECIDED_GROUP,
                "text": r["decision"], "why": f.get("Because", ""), "category": f.get("Category", ""),
                "rollback": f.get("Rollback", ""), "reversibleUntil": f.get("Reversible until", ""),
                "review": f.get("Review", ""), "decidedOn": r["date"]}
        out.append({k: v for k, v in item.items() if v != ""})
    return out


def map_glossary(cwd: str) -> Tuple[Optional[List[Dict[str, Any]]], List[str]]:
    """The capability map's ``glossary`` ([{term, plain, aliases}]), or None when the
    config names no map: the one list of the product's words that issues, pull requests
    and sheets share."""
    import check  # noqa: PLC0415  (sibling script; only a sheet with a map needs it)
    try:
        config, _path, _warnings = check.load_project_config(cwd, None)
    except Exception:  # noqa: BLE001  (a bad config is orient's to report, not the sheet's)
        return None, []
    map_value = config.get("map") if isinstance(config, dict) else None
    if not isinstance(map_value, dict):
        return None, []
    path, _how = check.map_file(map_value)
    if not path:
        return None, []
    try:
        data = json.loads(orient.read_text_tolerant(os.path.join(cwd, path)))
    except (OSError, ValueError) as exc:
        return [], [f"the map's glossary was not read ({path}: {exc})"]
    glossary = data.get("glossary") if isinstance(data, dict) else None
    entries = [g for g in glossary or [] if isinstance(g, dict) and isinstance(g.get("term"), str)
               and isinstance(g.get("plain"), str)] if isinstance(glossary, list) else []
    return entries, []


def sheet_words(raw: Any, items: List[Dict[str, Any]], glossary: List[Dict[str, Any]],
                has_map: bool) -> Tuple[List[Dict[str, Any]], List[str]]:
    """The words the sheet's items use, with their meanings: from the map's glossary
    first, then from the asks file's ``words`` ({term: meaning}) for a term the map lacks."""
    if raw is not None and (not isinstance(raw, dict)
                            or not all(isinstance(k, str) and isinstance(v, str) for k, v in raw.items())):
        raise InputError("--asks words must be an object of term: meaning strings")
    entries = [{"term": g["term"].strip(), "meaning": " ".join(g["plain"].split()),
                "aliases": [a.strip() for a in (g.get("aliases") if isinstance(g.get("aliases"), list) else [])
                            if isinstance(a, str) and a.strip()],
                "from": "map"} for g in glossary if g["term"].strip() and g["plain"].strip()]
    known = {w.lower() for e in entries for w in [e["term"]] + e["aliases"]}
    notes: List[str] = []
    for term, meaning in (raw or {}).items():
        if not term.strip():
            continue
        if term.strip().lower() in known:
            notes.append(f"words: {term.strip()!r} is in the map's glossary; its meaning comes from there")
            continue
        entries.append({"term": term.strip(), "meaning": " ".join(meaning.split()), "aliases": [], "from": "asks"})
        if has_map:
            notes.append(f"words: {term.strip()!r} is not in the map's glossary; add it there, so issues, "
                         "pull requests and sheets all share one meaning")
    shown = " ".join(str(v) for i in items for k, v in i.items() if k in READ_FIELDS or k == "docText")
    shown += " " + " ".join(str(o.get(k, "")) for i in items for o in i.get("options", []) for k in OPTION_READ_FIELDS)
    used = [e for e in entries if any(re.search(r"(?<!\w)" + re.escape(w) + r"(?:e?s)?(?!\w)", shown, re.I)
                                      for w in [e["term"]] + e["aliases"])]
    return used, notes


def name_sections(text: str) -> str:
    """``§2`` → ``§2 Outcome``, unless its name already follows it, bare or in brackets."""
    def one(m: "re.Match[str]") -> str:
        name = SECTION_NAMES.get(int(m.group(1)))
        after = text[m.end():m.end() + 40].lstrip().lstrip("(").lower()
        other_file = re.search(r"\.[a-z]{1,5}\s*$", text[max(0, m.start() - 40):m.start()])
        if name is None or after.startswith(name.lower().rstrip("s")) or other_file:  # "§9 open question" too  # "decision-sheet.md §4" is not an outcome doc
            return m.group(0)
        return f"{m.group(0)} {name}"
    return SECTION_REF_RE.sub(one, text)


def _name_sections(obj: Dict[str, Any], fields: Tuple[str, ...]) -> None:
    for k in fields:
        if isinstance(obj.get(k), str):
            obj[k] = name_sections(obj[k])


def unclear_findings(items: List[Dict[str, Any]], words: List[Dict[str, str]]) -> List[str]:
    """What a person could not follow without the doc open: a number with no words beside
    it, a question that holds its own recommendation, or lines to check that the item
    does not show. ``sheet`` writes no page, chat message or comment while any stand."""
    out: List[str] = []
    for item in items:
        where = item["id"]
        texts = [(k, item.get(k)) for k in READ_FIELDS]
        texts += [(f"option {o['label']!r} {k}", o.get(k)) for o in item.get("options", [])
                  for k in OPTION_READ_FIELDS]
        for field, value in texts:
            if not isinstance(value, str):
                continue
            value = LINK_TARGET_RE.sub("]", value)
            for rx, what in BARE_REFS:
                m = rx.search(value)
                if m:
                    fix = "give the item `plain` words" if field == "text" and item.get("doc") else "say it in words"
                    out.append(f"{where}: {field} leans on {what}, '{m.group(0)}', with no words beside it; "
                               f"{fix}, or put a few words right after the number")
        card = [(k, item.get(k)) for k in CARD_FIELDS] + [
            (f"option {o['label']!r} {k}", o.get(k)) for o in item.get("options", []) for k in ("label", "because")]
        for field, value in card:
            if not isinstance(value, str):
                continue
            value = LINK_TARGET_RE.sub("]", value)
            m = PATH_RE.search(value)
            if m:
                out.append(f"{where}: {field} shows a file path, '{m.group(0)}'; say what it shows, and put "
                           "the path in `evidence`")
            m = VARIANT_RE.search(value)
            if m and not any(re.search(r"(?<!\w)" + re.escape(m.group(0)) + r"(?!\w)", name, re.I)
                             for w in words for name in [w["term"]] + w.get("aliases", [])):
                out.append(f"{where}: {field} names '{m.group(0)}' with no meaning; add it to `words`, "
                           "or put a few words right after it")
        for field, limit in (("text", TEXT_WORDS), ("why", WHY_WORDS)):
            count = len(str(item.get(field) or "").split())
            if count > limit:
                fix = "`plain` words" if field == "text" and item.get("doc") else f"{limit} words or fewer"
                out.append(f"{where}: {field} is {count} words; put it in {fix}, the rest in `detail` or an option")
        if item["kind"] in ("question", "approve") and RECOMMENDED_RE.search(item.get("text", "")):
            out.append(f"{where}: the question holds its own recommendation; put it on an option "
                       "(\"recommended\": true, with its \"because\") and keep the question a question"
                       + (", in `plain` words" if item.get("doc") else ""))
        if UNSHOWN_LINES_RE.search(item.get("text", "")) and not (item.get("code") or item.get("detail")):
            out.append(f"{where}: it asks to check lines it does not show; put them in `code` or `detail`")
    return out


def in_research_group(item: Dict[str, Any]) -> bool:
    """Checked by research, in the one "Accept all" group: an answered or stale result
    for a question that blocks nothing. A BLOCKING one stays in the round."""
    return item.get("research") in RESEARCHED and item.get("blocking") is not True


def _fold_same_as(items: List[Dict[str, Any]], by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """An item whose ``sameAs`` names another open item is settled by that item's answer:
    it leaves the sheet and is listed under the other's ``alsoAnswers``, so one answer is
    written under every question it settles. A chain is followed to its last open item;
    a broken or looping link stops it there, and an item that points at nothing open
    stays as it was."""
    folded: Dict[str, str] = {}  # a folded item's id -> the item it was folded into
    for item in items:
        if not item.get("sameAs"):
            continue
        root, seen = item, {item["id"]}
        while root.get("sameAs"):
            nxt = by_id.get(root["sameAs"])
            while nxt is not None and nxt["id"] in folded:  # already folded: go on to where it went
                nxt = by_id.get(folded[nxt["id"]])
            if nxt is None or nxt not in items or nxt["id"] in seen:
                break
            seen.add(nxt["id"])
            root = nxt
        if root is item:
            item.pop("sameAs")
            if item.get("research") == "same-as":
                item.pop("research")  # what settled it is gone: it goes back to research, not to a bare card
            continue
        also = {k: item.get(k) for k in ("id", "kind", "doc", "q", "docTitle")}
        plain = item.get("plain") if isinstance(item.get("plain"), str) and item["plain"].strip() else None
        also["text"] = name_sections(plain or item.get("text") or "")  # the words a person reads
        root.setdefault("alsoAnswers", []).append(also)
        root["alsoAnswers"] += item.pop("alsoAnswers", [])
        if item.get("blocking") is True:
            root["blocking"] = True
        folded[item["id"]] = root["id"]
        for other_id, into in list(folded.items()):
            if into == item["id"]:
                folded[other_id] = root["id"]
    return [i for i in items if i["id"] not in folded]


def doc_brief(lines: List[str], title: str, status: str) -> Dict[str, Any]:
    """What the doc promises, from §0 exactly as the human wrote it."""
    records, _, _ = lint_outcome.parse_rules_block(lines)
    return {
        "title": title, "status": status,
        "outcome": lint_outcome.parse_bold_field_value(lines, "**Outcome:**"),
        "rules": [r["text"] for r in records],
        "signal": lint_outcome.parse_signal(lines),
    }


def thin_warnings(items: List[Dict[str, Any]]) -> List[str]:
    """A rich item a reader cannot answer cold: no reason it is asked, or nothing said
    about what waits on it; an option with no reason or no consequence."""
    out: List[str] = []
    for item in items:
        if item["kind"] == "decided":
            continue  # read-only: what the agent decided and how to undo it, from §8
        missing = [k for k in ("why", "blocks") if not item.get(k)]
        if missing:
            out.append(f"{item['id']}: no {' or '.join(missing)}")
        for o in item.get("options", []):
            gaps = [k for k in ("because", "then") if not o.get(k)]
            if gaps:
                out.append(f"{item['id']}: option {o['label']!r} has no {' or '.join(gaps)}")
    return out


def _md(text: Any) -> str:
    """One Markdown paragraph from sheet text: line breaks folded, nothing else changed."""
    return " ".join(str(text).split())


def _fenced(code: Any) -> List[str]:
    """A code block whose fence is longer than any backtick run inside it."""
    text = str(code)
    runs = [len(r) for r in re.findall(r"`+", text)]
    fence = "`" * max(3, max(runs, default=0) + 1)
    return [fence, text, fence]


def render_markdown(sheet: Dict[str, Any]) -> str:
    """The sheet as plain Markdown, for a chat or editor that cannot show the HTML page.
    Same items, same order and grouping, Recommended first; the human answers by
    replying one line per item, ``<id>: <answer>``."""
    items = sheet["items"]
    c = sheet["counts"]
    out = [f"# {_md(sheet['title'])}", ""]
    if sheet.get("intro"):
        out += [_md(sheet["intro"]), ""]
    out += _words_lines(sheet)
    out += [f"{c.get('round', c['items'])} items, {c['blocking']} blocking{_researched(c)}.{_later(c)} {REPLY_HELP}", ""]
    if not items:
        out += ["Nothing is waiting on you.", ""]
    groups: List[Tuple[str, List[Dict[str, Any]]]] = []
    for item in items:
        key = item.get("group") or item.get("doc") or "Other decisions"
        if not groups or groups[-1][0] != key:
            match = [g for g in groups if g[0] == key]
            if match:
                match[0][1].append(item)
                continue
            groups.append((key, []))
        groups[-1][1].append(item)
    for key, members in groups:
        first = members[0]
        named = bool(first.get("group"))  # a named group (research's) spans docs: no one doc's header
        out += [f"## {_md(first.get('groupTitle') or (first['group'] if named else first.get('docTitle')) or key)}", ""]
        doc = None if named else sheet.get("docs", {}).get(first.get("doc") or "")
        if key == DECIDED_GROUP:
            out += [DECIDED_INTRO, ""]
        if first.get("doc") and not named:
            status = f" · Status: {first['docStatus']}" if first.get("docStatus") else ""
            out += [f"`{first['doc']}`{status}", ""]
        if doc and doc.get("outcome"):
            out += [f"> **Outcome:** {_md(doc['outcome'])}", ""]
        for item in members:
            tags = [item.get("q") or item["id"]]
            if item.get("blocking") is True:
                tags.append("BLOCKING")
            elif item.get("blocking") is False:
                tags.append("non-blocking")
            if item["kind"] != "question":
                tags.append(KIND_TAGS[item["kind"]])
            if item.get("owner"):
                tags.append(f"owner: {item['owner']}")
            if item["kind"] == "decided" and item.get("docTitle"):
                tags.append(item["docTitle"])
            number = sheet["items"].index(item) + 1
            out += [f"### {number} · {' · '.join(tags)}", "", f"id: `{item['id']}`", "", _md(item.get("text", "")), ""]
            if item.get("docText"):
                out += [f"In the doc: {_md(item['docText'])}", ""]
            if item.get("alsoAnswers"):
                out += [_also_line(item), ""]
            fields = DECIDED_LABELS if item["kind"] == "decided" else (
                ("why", "Why"), ("blocks", "Waits on it"), ("ifNoAnswer", "If you don't answer"))
            for field, label in fields:
                if item.get(field):
                    out.append(f"**{label}:** {_md(item[field])}  ")
            if any(item.get(f) for f, _label in fields):
                out.append("")
            if item.get("code") and item["kind"] in ("approve", "confirm"):
                out += _fenced(item["code"]) + [""]
            if item.get("image"):
                if item["image"].startswith("https://"):
                    alt = _md(item.get("imageAlt") or "image")
                    out += [f"Image: [{alt}]({item['image']})", ""]
                else:
                    out += ["An image goes with this item; it shows on the HTML page, not here.", ""]
            options = sorted(item.get("options", []), key=lambda o: not o.get("recommended"))
            by_label = {o["label"]: o for o in options}
            for letter, label in zip(LETTERS, item.get("choices") or []):
                if label is None:
                    out.append(f"- {letter}) **None of these — reply with your own words**")
                    continue
                o = by_label[label]
                rec = " (Recommended)" if o.get("recommended") else ""
                because = f" — {_md(o['because'])}" if o.get("because") else ""
                out.append(f"- {letter}) **{_md(o['label'])}**{rec}{because}")
            if options:
                out.append("")
            elif item["kind"] in ("approve", "confirm", "input", "decided"):
                number = sheet["items"].index(item) + 1
                choices = reply_choices(item)
                for letter, (shown, _value) in zip(LETTERS, choices):
                    out.append(f"- {letter}) {shown}")
                if item["kind"] == "input":
                    out.append(f"- or reply `{number}: <the value>`" if choices
                               else f"Reply `{number}: <the value>`.")
                out.append("")
            more = []
            if item.get("example"):
                more.append(f"- Example: {_md(item['example'])}")
            for o in options:
                for f, label in (("detail", "detail"), ("commits", "commits you to"), ("think", "think about"),
                                 ("then", "then")):
                    if o.get(f):
                        more.append(f"- {_md(o['label'])}, {label}: {_md(o[f])}")
            for e in item.get("evidence", []):
                more.append(f"- Evidence: `{e['ref']}` {_md(e['note'])}".rstrip())
            if item.get("detail"):
                more.append(f"- Detail: {_md(item['detail'])}")
            for link in item.get("links", []):
                more.append(f"- {link['label']}: {link['url']}")
            if item.get("code") and item["kind"] not in ("approve", "confirm"):
                more += [""] + _fenced(item["code"])
            if more:
                out += ["More, if you need it:", ""] + more + [""]
    return "\n".join(out).rstrip() + "\n"


SHEET_DATA_RE = re.compile(r"<!--\s*promise-sheet:v1:([A-Za-z0-9+/=\s]+?)\s*-->")
LETTERS = "abcdefghijklmnopqrstuvwxyz"
FIXED_REPLIES = {
    "approve": [("Approve", "Approved"), ("Request changes (say what after a dash)", "Changes requested"),
                ("Reject", "Rejected")],
    "confirm": [("Done", "Done"), ("Not yet", "Not done yet")],
    # No answer keeps the agent's choice; the one action puts it to the human as a §9 question.
    "decided": [(f"{ASK_INSTEAD} (say why after a dash)", ASK_INSTEAD)],
}
# What a fixed reply's label asks for after the dash (``what`` or ``why``): a pane draws a
# field for it instead, and the label without it.
AFTER_A_DASH_RE = re.compile(r" \(say (what|why) after a dash\)$")
# A pick on the pane that means nothing without its note (a chat reply is read as it is).
NOTE_REQUIRED = {"Changes requested": "say what to change in the note"}


def _fixed(item: Dict[str, Any]) -> bool:
    """An item answered from FIXED_REPLIES: an approval, a to-do or an agent decision
    with no options of its own. It takes a letter, never words in its place."""
    return item["kind"] in FIXED_REPLIES and not item.get("choices")
KIND_TAGS = {"approve": "approval", "input": "value", "confirm": "to do", "decided": "decided for you"}
DECIDED_LABELS = (("why", "Because"), ("rollback", "Rollback"), ("reversibleUntil", "Reversible until"),
                  ("review", "Review"), ("category", "Category"), ("decidedOn", "Decided on"))
DECIDED_INTRO = ("The agent made these choices under the doc's decision policy and recorded each with its "
                 "rollback. Nothing here needs an answer: leave them, and they stand. To decide one "
                 "yourself, pick \"Ask me instead\"; it becomes a question in the doc.")
REPLY_HELP = ("Reply with `all recommended`, or one code per item, like `1a 2c`. "
              "Add a note after a dash (`2b - fix the wording`); for your own words, `3: <your words>`.")


def reply_choices(item: Dict[str, Any]) -> List[Tuple[str, Optional[str]]]:
    """The lettered choices a chat reply picks from, in order: (what the human reads,
    the answer it records). ``None`` records the human's own words. An item's options,
    of any kind, are its choices, as the page and the Markdown twin letter them."""
    if _fixed(item):
        return list(FIXED_REPLIES[item["kind"]])
    if not item.get("choices") and item["kind"] == "input":
        proposed = item.get("proposed")
        return [(f"{proposed} (proposed)", str(proposed))] if proposed not in (None, "") else []
    by_label = {o["label"]: o for o in item.get("options", [])}
    out: List[Tuple[str, Optional[str]]] = []
    for label in item.get("choices") or []:
        if label is None:
            out.append(("None of these: reply with your own words", None))
        else:
            o = by_label[label]
            shown = _md(label)
            if o.get("recommended"):
                shown += " (Recommended)" + (f": {_md(o['because'])}" if o.get("because") else "")
            out.append((shown, label))
    return out


def pane_replies(item: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], bool]:
    """The lettered choices of ``reply_choices`` as data, for a surface that draws its own
    controls (the promise mod's pane): each with its ``code``, what the human reads (no
    "after a dash": the pane has a field), the answer it records (``None``: the human's
    own words), whether it is the Recommended one, ``noteAsk`` (``what`` or ``why``) when
    the field asks for something, ``noteRequired`` when the pick means nothing without it,
    and the option's own brief; and whether the item also
    takes words in place of a letter, as ``parse_reply`` reads them."""
    rec = _recommended(item)
    by_label = {o["label"]: o for o in item.get("options", [])}
    replies = []
    for letter, (shown, value) in zip(LETTERS, reply_choices(item)):
        reply = {"code": letter, "label": AFTER_A_DASH_RE.sub("", shown), "value": value,
                 "recommended": value is not None and value == rec}
        ask = AFTER_A_DASH_RE.search(shown) if _fixed(item) else None
        if ask:
            reply["noteAsk"] = ask.group(1)
        if value in NOTE_REQUIRED:
            reply["noteRequired"] = True  # parse_picks refuses this pick with an empty note
        option = by_label.get(value) if value is not None else None
        for key in ("detail", "because", "commits", "think", "then"):
            if option and option.get(key) and not (key == "because" and reply["recommended"]):
                reply[key] = option[key]  # the Recommended one's reason is already in its label
        replies.append(reply)
    return replies, not _fixed(item)


def _recommended(item: Dict[str, Any]) -> Optional[str]:
    if item.get("choices") or item["kind"] == "question":
        rec = [o["label"] for o in item.get("options", []) if o.get("recommended")]
        return rec[0] if rec else None
    if item["kind"] == "input" and item.get("proposed") not in (None, ""):
        return str(item["proposed"])
    return None


def _also_line(item: Dict[str, Any]) -> str:
    """The other questions one answer settles, for a reader who sees only text."""
    return "Also settles: " + "; ".join((f"{o['docTitle']}: " if o.get("docTitle") else "") + _md(o.get("text") or o["id"])
                                         for o in item["alsoAnswers"])


def _researched(counts: Dict[str, Any]) -> str:
    n = counts.get("researched") or 0
    return f", plus {n} found by research to check" if n else ""


def _later(counts: Dict[str, Any]) -> str:
    """' 178 more come in later rounds.' when this sheet is one round of more."""
    later = counts.get("later") or 0
    return f" {later} more come in later rounds, once these are in." if later else ""


def _words_lines(sheet: Dict[str, Any]) -> List[str]:
    """The words the sheet uses, one line each, before the first item."""
    words = sheet.get("words") or []
    return [f"- **{_md(w['term'])}**: {_md(w['meaning'])}" for w in words] + ([""] if words else [])


def render_chat(sheet: Dict[str, Any]) -> str:
    """The sheet as one chat message a person answers from a phone: each item numbered,
    its choices lettered, the Recommended one named, and one line on how to reply."""
    c = sheet["counts"]
    blocking = f", {c['blocking']} blocking" if c["blocking"] else ""
    out = [f"**{_md(sheet['title'])}**: {c.get('round', c['items'])} to decide{blocking}{_researched(c)}.{_later(c)}", ""]
    if sheet.get("intro"):
        out += [_md(sheet["intro"]), ""]
    out += _words_lines(sheet)
    if not sheet["items"]:
        out.append("Nothing is waiting on you.")
        return "\n".join(out) + "\n"
    for n, item in enumerate(sheet["items"], 1):
        if item["kind"] == "decided" and (n == 1 or sheet["items"][n - 2]["kind"] != "decided"):
            out += [f"**{DECIDED_GROUP}.** {DECIDED_INTRO}", ""]
        tags = []
        if item.get("blocking") is True:
            tags.append("BLOCKING")
        if item["kind"] != "question":
            tags.append({"approve": "approval", "input": "a value", "confirm": "to do",
                         "decided": "decided for you"}[item["kind"]])
        where = (f" ({item['doc']} {item.get('q') or decision_key(str(item.get('decision', '')))})"
                 if item.get("doc") else "")
        tail = f" · {' · '.join(tags)}" if tags else ""
        out.append(f"**{n}.** {_md(item.get('text', ''))}{tail}{where}")
        if item.get("alsoAnswers"):
            out.append(_also_line(item))
        if item.get("why"):
            out.append(f"{'Because' if item['kind'] == 'decided' else 'Why'}: {_md(item['why'])}")
        if item["kind"] == "decided" and item.get("rollback"):
            out.append(f"Rollback: {_md(item['rollback'])}")
        choices = reply_choices(item)
        for letter, (shown, _value) in zip(LETTERS, choices):
            out.append(f"  {letter}) {shown}")
        if not choices:
            out.append(f"  Reply `{n}: <your answer>`.")
        elif item["kind"] == "input":
            out.append(f"  or reply `{n}: <the value>`")
        if item.get("code") and item["kind"] in ("approve", "confirm"):
            out += _fenced(item["code"])
        out.append("")
    out.append(REPLY_HELP)
    return "\n".join(out) + "\n"


GITHUB_COMMENT_LIMIT = 65536


def encode_sheet(sheet: Dict[str, Any]) -> str:
    # An embedded image is left out: a reply never needs it, and it would outgrow a comment.
    items = [{k: v for k, v in i.items() if not (k == "image" and str(v).startswith("data:"))}
             for i in sheet["items"]]
    raw = json.dumps(dict(sheet, items=items), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(zlib.compress(raw, 9)).decode("ascii")


def render_comment(sheet: Dict[str, Any]) -> str:
    """The sheet as a GitHub issue comment: the chat message, the full Markdown twin
    folded under it, and the sheet's data in an HTML comment, so any agent that reads
    the thread can apply a reply with no local file."""
    text = (render_chat(sheet) + "\n<details><summary>Full detail</summary>\n\n" + render_markdown(sheet)
            + "\n</details>\n\n" + f"<!-- promise-sheet:v1:{encode_sheet(sheet)} -->\n")
    if len(text) > GITHUB_COMMENT_LIMIT:
        raise InputError(f"the comment is {len(text)} characters, over GitHub's {GITHUB_COMMENT_LIMIT}; "
                         "split the sheet with --only and post one comment each")
    return text


def load_sheet(path: str) -> Dict[str, Any]:
    """A sheet from its ``--json`` output, or from text that holds a posted comment
    (the comment itself, or a whole thread pasted into a file)."""
    try:
        raw = orient.read_text_tolerant(path)
    except (OSError, ValueError) as exc:
        raise InputError(f"could not read --sheet {path}: {exc}")
    found = SHEET_DATA_RE.findall(raw)
    if len({"".join(f.split()) for f in found}) > 1:
        raise InputError(f"{path} holds {len(found)} sheets; pass only the comment the reply answers")
    if found:
        try:
            data = json.loads(zlib.decompress(base64.b64decode("".join(found[-1].split()))).decode("utf-8"))
        except (ValueError, zlib.error) as exc:
            raise InputError(f"the sheet data in {path} does not decode: {exc}")
    else:
        try:
            data = json.loads(raw)
        except ValueError:
            raise InputError(f"{path} holds no sheet: pass the sheet's --json output or its posted comment")
    if not isinstance(data, dict) or data.get("format") != "promise-sheet" or not isinstance(data.get("items"), list):
        raise InputError(f"{path} holds no promise-sheet")
    return data


def _code_res(width: int) -> Tuple["re.Pattern[str]", "re.Pattern[str]", "re.Pattern[str]"]:
    """The reply-code patterns for a sheet whose item numbers have up to ``width`` digits,
    so "300s" in a note on a small sheet stays a value, not item 300."""
    d = f"\\d{{1,{width}}}"
    lead = re.compile(r"[).]?\s*(" + d + r")([a-z])?(?=$|[\s:.)\-–—])", re.I)
    nxt = re.compile(r"[).]?\s+" + d + r"(?:[a-z](?=$|[\s:.)\-–—])|\s*[:\-–—]|\s+[a-z](?=[).]?(?:\s*$|\s*[-–—]|\s+\d)))",
                     re.I)
    # "12a" or "105:" in a note is a second answer; "300s" is a value.
    like = re.compile(r"(?<![\w.:])(?:\d{1,2}(?:[a-z](?![a-z])|\s*:(?!\d))"
                      + (r"|\d{3," + str(width) + r"}\s*:(?!\d)" if width > 2 else "") + ")", re.I)
    return lead, nxt, like
ALL_RECOMMENDED_RE = re.compile(r"(accept\s+)?all\s+(the\s+)?recommended[.!]?", re.I)


SPACED_LETTER_RE = re.compile(r"\s+([a-z])(?=[).]?(?:\s*$|\s*[-–—]|\s+\d))", re.I)


def _reply_codes(text: str, width: int = 2) -> Tuple[List[Tuple[int, Optional[str], str]], List[str], bool]:
    """The codes in a reply, as (item number, letter or None, note), the problems it
    raises, and whether it says ``all recommended``. A part of the reply (split at
    commas, semicolons and line ends) opens with a run of codes: ``1a 2b 3c``, the last
    of which may carry a note after it (``3c - fix the wording``), or one number and its
    words (``2: my words``, ``2 - my words``, ``2 b``). Once a note starts, nothing in it
    is a code, so ``ship it in 2d`` never answers another item. A part with no code
    continues the note before it; a part that opens with a number and plain words
    (``2 people max``) could be either, so it is a problem, never a guess.
    ``all recommended`` counts only as a whole part, or as all that follows its codes
    (``3a all recommended``); inside a note it is just words."""
    LEAD_CODE_RE, NEXT_CODE_RE, CODE_LIKE_RE = _code_res(width)
    codes: List[Tuple[int, Optional[str], str]] = []
    problems: List[str] = []
    everything = False
    parts = re.split(r"([,;\n]+)", text)
    for index in range(0, len(parts), 2):
        segment = parts[index]
        run: List[Tuple[int, Optional[str]]] = []
        pos = 0
        m = LEAD_CODE_RE.match(segment)
        unclear = False
        while m:
            letter, end = m.group(2), m.end()
            if letter is None:
                after = segment[end:]
                spaced = SPACED_LETTER_RE.match(after)
                if spaced:  # "2 b"
                    letter, end = spaced.group(1), end + spaced.end()
                elif not re.match(r"\s*[:.)\-–—]", after):  # not "2: words" nor "2 - words"
                    # A lone number, as in "2: 1, 3", is words continuing the note before it.
                    unclear = bool(after.strip())
                    break
            run.append((int(m.group(1)), letter))
            pos = end
            if letter is None or not NEXT_CODE_RE.match(segment, pos):
                break
            m = LEAD_CODE_RE.match(segment, pos)
        if unclear:
            problems.append(f"'{segment.strip()[:60]}': is {m.group(1)} an item or part of the words? "
                            f"Write `{m.group(1)}: <words>` for an item's words, or keep it in a note")
            continue
        rest = (segment[pos:] if run else segment).strip()
        if ALL_RECOMMENDED_RE.fullmatch(rest):
            everything, rest = True, ""
        rest = rest.lstrip(":.)").strip()
        if run and not rest[:1] in ("-", "–", "—") and CODE_LIKE_RE.search(rest):
            problems.append(f"'{segment.strip()[:60]}': more than one answer here? Put a comma between "
                            "answers, and a dash before a note")
            continue
        rest = rest.lstrip("-–—").strip()
        if run:
            for num, letter in run[:-1]:
                codes.append((num, letter.lower() if letter else None, ""))
            num, letter = run[-1]
            codes.append((num, letter.lower() if letter else None, rest))
        elif rest:
            if codes:
                num, letter, note = codes[-1]
                joiner = parts[index - 1].strip()[:1] or ","
                codes[-1] = (num, letter, f"{note}{joiner} {rest}" if note else rest)
            else:
                problems.append(f"'{rest[:60]}': no item number in front, so it answers nothing")
    return codes, problems, everything


LONE_LETTER_RE = re.compile(r"^([a-z])\s*(?:$|[-–—]\s*(.*))$", re.I | re.S)


def parse_reply(text: str, sheet: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """A person's short reply, read against the sheet it answers, as promise-answers
    entries, and the items left unanswered. An item may be named by its number or its
    id (``docs/x.md#Q2: b``), and ``2: b`` picks choice b. A reply that cannot be read
    raises, naming each part, so the agent asks the person rather than guessing."""
    items = sheet["items"]
    for n, item in sorted(enumerate(items, 1), key=lambda x: -len(x[1]["id"])):
        text = re.sub(r"(^|[,;\n])\s*`?" + re.escape(item["id"]) + r"`?\s*:",
                      lambda m, n=n: f"{m.group(1)}\n{n}:", text)
    picked: Dict[int, Tuple[Optional[str], str]] = {}
    codes, problems, everything = _reply_codes(text, max(2, len(str(len(items)))))
    for num, letter, note in codes:
        if not 1 <= num <= len(items):
            problems.append(f"{num}: there is no item {num} (the sheet has {len(items)})")
            continue
        if num in picked:
            problems.append(f"{num}: answered twice; give each item one code")
            continue
        picked[num] = (letter, note)
    answers, unanswered = [], []
    for n, item in enumerate(items, 1):
        if n in picked:
            letter, note = picked[n]
            choices = reply_choices(item)
            lone = LONE_LETTER_RE.match(note) if letter is None and choices else None
            if lone:  # "2: b", or "2: b - a note"; "2: y" to an item with no choices is words
                letter, note = lone.group(1).lower(), (lone.group(2) or "").strip()
            entry, problem = answer_entry(n, item, letter, note, choices=choices)
        elif everything and _recommended(item) is not None:
            entry, problem = answer_entry(n, item, None, _recommended(item), recommended=True)
        else:
            unanswered.append(item["id"])
            continue
        if problem:
            problems.append(problem)
        else:
            answers.append(entry)
    if problems:
        raise InputError("the reply could not be read: " + "; ".join(problems))
    return with_also(answers, sheet), unanswered


def answer_entry(n: int, item: Dict[str, Any], letter: Optional[str], note: str, recommended: bool = False,
                 choices: Optional[List[Tuple[str, Optional[str]]]] = None
                 ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """One item's promise-answers entry from a pick: a choice's letter with an optional
    note, or (no letter) the person's own words in ``note``; else the reason it cannot
    be read. A chat reply and the mod's pane both come through here, so a pick records
    the same answer whichever surface it was made on. ``recommended``: the item's
    Recommended answer, taken as it is. ``choices``: the item's, when the caller has them."""
    choices = reply_choices(item) if choices is None else choices
    if recommended:
        value, note = note, ""
    elif letter is not None:
        k = LETTERS.index(letter) if len(letter) == 1 and letter in LETTERS else len(LETTERS)
        if k >= len(choices):
            return None, (f"{n}{letter}: item {n} has choices a to {LETTERS[max(len(choices) - 1, 0)]}"
                          if choices else f"{n}{letter}: item {n} takes words, not a letter")
        value = choices[k][1]
        if value is None:
            if not note:
                return None, f"{n}{letter}: 'None of these' needs your own words after it"
            value, note = note, ""
    else:
        if _fixed(item):
            return None, (f"{n}: pick a letter ({', '.join(LETTERS[:len(choices)])}), "
                          "with any note after a dash")
        if not note:
            return None, f"{n}: no choice and no words"
        value, note = note, ""
    entry = {"id": item["id"], "kind": item["kind"], "doc": item.get("doc"), "q": item.get("q"),
             "value": f"{value}. {note}" if note else value, "note": note or None}
    if item.get("decision"):
        entry["decision"] = item["decision"]
    return entry, None


def parse_picks(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """The mod's pane's answers (``format: promise-picks``): the sheet it drew and one
    pick per answered item, by number: ``{"n", "code", "note"}``, where ``code`` is a
    choice's letter, or null with the person's own words in ``note``. Read through ``answer_entry`` as a
    chat reply is, into promise-answers, with the items left unanswered. A pick that
    cannot be read, or a request for changes that does not say what, is refused with
    every reason."""
    sheet = data.get("sheet")
    if not isinstance(sheet, dict) or not isinstance(sheet.get("items"), list):
        raise InputError("promise-picks needs the sheet it answers, as decisions.py sheet --json printed it")
    if not isinstance(data.get("picks"), list):
        raise InputError("promise-picks needs a list of picks")
    items = sheet["items"]
    if not all(isinstance(i, dict) and isinstance(i.get("id"), str) and i.get("kind") in KINDS + ("decided",)
               for i in items):
        raise InputError("promise-picks carries a sheet whose items are not decisions.py's: rebuild it with sheet --json")
    answers, problems, seen = [], [], set()
    for pick in data["picks"]:
        n = pick.get("n") if isinstance(pick, dict) else None
        if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= len(items) or n in seen:
            problems.append(f"{n}: not one item of the {len(items)} on the sheet, once")
            continue
        seen.add(n)
        item = items[n - 1]
        code, note = pick.get("code"), str(pick.get("note") or "").strip()
        if code is not None and not isinstance(code, str) or code == "":
            problems.append(f"{n}: a pick's code is one letter, or null for the person's own words")
            continue
        entry, problem = answer_entry(n, item, code, note)
        if not problem and code and entry["value"] in NOTE_REQUIRED:  # chosen, and nothing said after it
            problem = f"{n}{code}: {NOTE_REQUIRED[entry['value']]}"
        if problem:
            problems.append(problem)
        else:
            answers.append(entry)
    if problems:
        raise InputError("the answers could not be read: " + "; ".join(problems))
    unanswered = [i["id"] for k, i in enumerate(items, 1) if k not in seen and i["kind"] != "decided"]
    return ({"format": "promise-answers", "version": 1, "sheet": sheet.get("id"),
             "answers": with_also(answers, sheet)}, unanswered)



def with_also(answers: List[Dict[str, Any]], sheet: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Each answer, then the same answer under every question its item settles too."""
    by_id = {i["id"]: i for i in sheet.get("items", [])}
    out: List[Dict[str, Any]] = []
    for a in answers:
        out.append(a)
        for other in by_id.get(a["id"], {}).get("alsoAnswers", []):
            out.append(dict(a, id=other["id"], kind=other.get("kind") or a.get("kind"), doc=other.get("doc"),
                            q=other.get("q")))
    return out


def asks_skeleton(sheet: Dict[str, Any], asks: Dict[str, Any]) -> Dict[str, Any]:
    """An asks file for this round, to fill in: each item with the fields it has and the
    brief it still needs, the doc's own words as ``_doc`` and what is unclear as
    ``_unclear``. Keys starting with ``_`` are for the agent; ``sheet`` ignores them.
    Every asks item and word outside this round is kept as it was, so the skeleton can
    be written over the asks file it came from."""
    unclear: Dict[str, List[str]] = {}
    for u in sheet["unclear"]:
        unclear.setdefault(u.split(": ", 1)[0], []).append(u.split(": ", 1)[1])
    raw = {i["id"]: i for i in asks.get("items", []) if isinstance(i, dict) and isinstance(i.get("id"), str)}
    out = []
    for item in sheet["items"]:
        if item["kind"] == "decided":
            continue  # a view of §8: the row itself is where its words change
        # The asks file's own entry first, "_" bookkeeping and all, then what the sheet adds.
        entry: Dict[str, Any] = dict(raw.get(item["id"], {"id": item["id"]}))
        entry.pop("_unclear", None)
        if item.get("doc"):
            entry["_doc"] = item.get("docText") or item.get("text", "")
            entry.setdefault("plain", item["text"] if item.get("docText") else "")
        else:
            entry.update({k: item[k] for k in ("kind", "text") if k in item})
        for k in ENRICH_KEYS + tuple(k for k in EXTRA_KEYS if not item.get("doc")):
            if k in item and k not in entry and k not in ("plain", "id"):
                entry[k] = item[k]
        for k in BRIEF_KEYS[:3]:
            entry.setdefault(k, "")
        if item["id"] in unclear:
            entry["_unclear"] = unclear[item["id"]]
        out.append(entry)
    shown = {i["id"] for i in sheet["items"]}
    out += [dict(i) for i in asks.get("items", []) if isinstance(i, dict) and i.get("id") not in shown]
    words = dict(asks.get("words") or {}) if isinstance(asks.get("words"), dict) else {}
    return {"title": asks.get("title", sheet["title"]), "intro": asks.get("intro", sheet.get("intro", "")),
            "words": words, "items": out}


def _chip(text: str, limit: int = 12) -> str:
    """The whole words of ``text`` that fit a prompt's header chip."""
    out = ""
    for word in text.split():
        if len(out) + len(word) + (1 if out else 0) > limit:
            break
        out = f"{out} {word}".strip()
    return out or text[:limit]


def prompt_batches(sheet: Dict[str, Any]) -> Dict[str, Any]:
    """This round for a host's question prompt (AskUserQuestion): batches of four
    questions, two to four options each, Recommended first. Each option carries the
    reply code it stands for; the answers go back as a short reply through
    ``apply --reply``, and a person's own words ("Other") as ``<n>: <words>``."""
    batches: List[List[Dict[str, Any]]] = []
    listed: List[Dict[str, Any]] = []
    numbered = sorted(enumerate(sheet["items"], 1), key=lambda x: 0 if x[1].get("blocking") is True else 1)
    for n, item in numbered:  # BLOCKING first; each keeps its sheet number, so the codes stay right
        if item["kind"] == "decided" and sheet.get("surface") == "ask-questions":
            # beside a few plain questions, what the agent decided is one line each in the
            # message, never a prompt of its own; "<n>a" asks it instead
            listed.append({"item": n, "id": item["id"], "text": _md(item.get("text", "")),
                           "rollback": _md(item.get("rollback", "")), "askInstead": f"{n}a"})
            continue
        options = []
        other = f"{n}: <their words>"
        for letter, (shown, value) in zip(LETTERS, reply_choices(item)):
            if value is None:
                continue  # the prompt's own "Other" box is "None of these"
            if value == "Changes requested":
                other = f"{n}{letter} - <what to change>"  # a click carries no note: Other is the change request
                continue
            label = _md(re.sub(r"\s*\(Recommended\).*$", "", shown)) if item.get("options") else _md(shown)
            by_label = {o["label"]: o for o in item.get("options", [])}
            o = by_label.get(value, {})
            if o.get("recommended") or (item["kind"] == "input" and not item.get("options")):
                label = re.sub(r" \(proposed\)$", "", label) + " (Recommended)"
            description = _md(o.get("because") or o.get("then") or "")[:200]
            if item["kind"] == "decided":
                label, description = ASK_INSTEAD, "It becomes a BLOCKING question in the doc, for you to answer."
            options.append({"label": label[:120], "description": description, "code": f"{n}{letter}"})
        if item["kind"] == "confirm" and not item.get("choices"):
            other = f"{n}b - <their words>"  # a to-do takes a letter: its own words are "not yet", with a note
        if item["kind"] == "decided":
            other = f"{n}a - <their words>"  # their own words are an objection: ask me instead, with the note
            options.insert(0, {"label": "Keep it", "description": "The agent's choice stands; nothing is written.",
                               "code": None})
        free = not options  # a question with no choices is answered in the prompt's own "Other" box
        options, more = options[:4], options[4:]
        for label, why in (("Not now", "Leave it open; it comes back in a later round."),
                           ("Talk it through", "Leave it open, and talk it over with the agent first.")):
            if len(options) < 2:
                options.append({"label": label, "description": why, "code": None})
        header = {"approve": "Approval", "input": "A value", "confirm": "To do", "decided": "Decided"}.get(
            item["kind"], _chip(item.get("docTitle") or "Question"))
        question = _md(item.get("text", ""))
        if item.get("why"):
            question += " — " + _md(item["why"])
        if not batches or len(batches[-1]) == ASK_LIMIT:
            batches.append([])
        entry = {"item": n, "id": item["id"], "header": header, "question": question,
                 "multiSelect": False, "freeText": free, "options": options, "otherReply": other}
        if more:
            entry["moreOptions"] = more  # the prompt holds four: write these out before the batch
        batches[-1].append(entry)
    out: Dict[str, Any] = {"batches": batches}
    if listed:
        out["decided"] = listed
        out["decidedHelp"] = ("List these after the questions, one line each with its rollback, under "
                              "'Decided for you'; a person who objects replies with its askInstead code.")
    return {**out,
            "reply": "Join the codes of the picked options with spaces (\"1a 2c\"). For 'Other', add the "
                     "item's otherReply with the person's words in place (a freeText item is answered only "
                     "that way; for an approval, Other is the change request). Skip 'Not now' and 'Talk it "
                     "through'. List any moreOptions, with their codes, in the text before the batch. Then "
                     "run decisions.py apply --reply <file> --sheet <this sheet's --json>."}


PACKET_SIZE = 10
RESEARCH_PROMPT = """Research the open questions in {packet}. For each one, read the doc it comes from and
the code and docs it concerns, then sort it into one pile:
- answered: the code or docs already settle it. Give the answer, why, and evidence as path:line you read
  this run.
- same-as: another open question (from the packet's allOpen list) settles it. Give that id as sameAs.
- stale: it no longer applies (the code or a later decision moved on). Say why, with evidence.
- needs-you: only a person can decide it (money, legal, product taste, risk). Give plain words (35 words
  at most), why, what waits on it, and two to four options with one Recommended and its reason.
Never mark a question answered without evidence, and never write to a doc. Put words beside every number
(#87 ("title"), Q4: <a few words>), and keep paths in evidence. Write your results to {result} in this shape:
{shape}
Then reply with one line: how many in each pile."""
RESULT_SHAPE = {"format": "promise-research", "version": 1, "packet": "<the packet's id>", "results": [
    {"id": "<doc>#Qn", "pile": "answered", "answer": "<the answer, in the doc's terms>", "because": "<why>",
     "evidence": [{"ref": "path/to/file.ts:42", "note": "<what that line shows>"}]},
    {"id": "<doc>#Qn", "pile": "same-as", "sameAs": "<the id that settles it>", "because": "<why>"},
    {"id": "<doc>#Qn", "pile": "stale", "answer": "<why it no longer applies>", "because": "<why>",
     "evidence": [{"ref": "path:line", "note": "…"}]},
    {"id": "<doc>#Qn", "pile": "needs-you", "plain": "<the question>", "why": "…", "blocks": "…",
     "options": [{"label": "…", "recommended": True, "because": "…", "then": "…"}, {"label": "…", "because": "…"}]}]}


def triage(sheet: Dict[str, Any], out_dir: str, size: int) -> Dict[str, Any]:
    """Split the open questions no research has checked into packets of ``size``, one
    doc at a time, for research agents to sort (references/research.md)."""
    todo = [i for i in sheet["items"] if i["kind"] == "question" and not i.get("research")]
    all_open = [{"id": i["id"], "text": _md(i.get("text", ""))} for i in sheet["items"] if i["kind"] == "question"]
    by_doc: Dict[str, List[Dict[str, Any]]] = {}
    for item in todo:
        by_doc.setdefault(item.get("doc") or "", []).append(item)
    os.makedirs(out_dir, exist_ok=True)
    stale = sorted(f for f in os.listdir(out_dir) if f.startswith(("result-", "packet-")) and f.endswith(".json"))
    if stale:
        raise InputError(f"{out_dir} holds packets or results from an earlier triage ({', '.join(stale[:3])}"
                         f"{'…' if len(stale) > 3 else ''}); each triage run gets its own folder: give --out a "
                         "new one (merge-research reads a folder's results as one set)")
    packets = []
    for doc, group in by_doc.items():
        for start in range(0, len(group), size):
            n = len(packets) + 1
            name = f"packet-{n:02d}"
            chunk = group[start:start + size]
            packet = {"format": "promise-research-packet", "version": 1, "packet": name, "doc": doc or None,
                      "promise": sheet.get("docs", {}).get(doc), "items": [
                          {k: i[k] for k in ("id", "text", "docText", "owner", "blocking", "why", "blocks",
                                             "options", "evidence") if k in i} for i in chunk],
                      "allOpen": all_open}
            path = os.path.join(out_dir, f"{name}.json")
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(packet, indent=2, ensure_ascii=False) + "\n")
            result = os.path.join(out_dir, f"result-{n:02d}.json")
            packets.append({"packet": path, "result": result, "doc": doc or None, "items": len(chunk),
                            "blocking": sum(1 for i in chunk if i.get("blocking") is True),
                            "prompt": RESEARCH_PROMPT.format(packet=path, result=result,
                                                             shape=json.dumps(RESULT_SHAPE, indent=1))})
    return {"format": "promise-triage", "version": 1, "questions": len(todo), "packets": packets,
            "next": "Start one research agent per packet with its prompt (in parallel where the host allows), "
                    "then run decisions.py merge-research " + out_dir + " --asks <asks.json>."}


def _evidence_problem(cwd: str, ref: str) -> Optional[str]:
    m = re.match(r"^(.+?):(\d+)(?:-(\d+))?$", ref.strip())
    if not m:
        return f"evidence {ref!r} is not path:line"
    path = os.path.normpath(os.path.join(cwd, m.group(1)))
    if orient._path_escapes(m.group(1)) or not os.path.isfile(path):
        return f"evidence {ref!r}: no such file in this project"
    try:
        count = len(orient.read_text_tolerant(path).splitlines())
    except (OSError, ValueError):
        return f"evidence {ref!r}: the file could not be read"
    first, last = int(m.group(2)), int(m.group(3) or m.group(2))
    if not 1 <= first <= last <= count:
        return f"evidence {ref!r}: the file has {count} lines"
    return None


NEEDS_YOU_KEYS = ("plain", "why", "blocks", "ifNoAnswer", "example", "options", "evidence", "detail")


def _clear_research(entry: Dict[str, Any]) -> None:
    """Take back what an earlier research result put on an asks entry: the fields it
    listed in ``_research``, and nothing the asks file had before it."""
    entry.pop("research", None)
    entry.pop("sameAs", None)
    for k in entry.pop("_research", []):
        entry.pop(k, None)
    entry.update(entry.pop("_saved", {}))  # what research wrote over comes back


RESEARCH_BLOCKS = "Nothing new: research found the answer; it needs your yes."
RESEARCH_STALE = "Nothing: research found it no longer applies; closing it needs your yes."


def merge_research(cwd: str, sheet: Dict[str, Any], paths: List[str], asks: Dict[str, Any]
                   ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Research results, checked, merged into the asks file. An answered or stale result
    needs evidence that points at a real file and line; a same-as result an open question
    other than itself. A result that fails is rejected with its reason, never guessed at."""
    files: List[str] = []
    for p in paths:
        full = os.path.abspath(p)  # a path typed on the command line is from where it runs; evidence is from the project
        if os.path.isdir(full):
            files += sorted(os.path.join(full, f) for f in os.listdir(full)
                            if f.startswith("result-") and f.endswith(".json"))
        else:
            files.append(full)
    blocking_ids = {i["id"] for i in sheet["items"] if i.get("blocking") is True}
    open_ids = {i["id"] for i in sheet["items"]}
    open_ids |= {a["id"] for i in sheet["items"] for a in i.get("alsoAnswers", [])}
    entries = {i["id"]: dict(i) for i in asks.get("items", []) if isinstance(i, dict) and i.get("id")}
    order = [i["id"] for i in asks.get("items", []) if isinstance(i, dict) and i.get("id")]
    piles = {p: 0 for p in PILES}
    rejected: List[Dict[str, str]] = []
    for path in files:
        try:
            data = json.loads(orient.read_text_tolerant(path))
        except (OSError, ValueError) as exc:
            rejected.append({"file": rel(cwd, path), "reason": f"not readable JSON: {exc}"})
            continue
        if not isinstance(data, dict) or data.get("format") != "promise-research" or not isinstance(data.get("results"), list):
            rejected.append({"file": rel(cwd, path), "reason": "not a promise-research file"})
            continue
        for r in data["results"]:
            rid = r.get("id") if isinstance(r, dict) else None
            reason = None
            if not isinstance(rid, str) or rid not in open_ids:
                reason = "not an open question"
            elif r.get("pile") not in PILES:
                reason = f"pile must be one of {', '.join(PILES)}"
            elif r["pile"] in RESEARCHED:
                ev = r.get("evidence")
                if not isinstance(r.get("answer"), str) or not r["answer"].strip():
                    reason = "no answer"
                elif not isinstance(ev, list) or not ev or not all(isinstance(e, dict) for e in ev):
                    reason = "no evidence: research that finds an answer shows where"
                else:
                    reason = next((x for x in (_evidence_problem(cwd, str(e.get("ref", ""))) for e in ev) if x), None)
            elif r["pile"] == "same-as" and (not isinstance(r.get("sameAs"), str) or r["sameAs"] not in open_ids
                                             or r["sameAs"] == rid):
                reason = "sameAs must name another open question"
            elif r["pile"] == "needs-you":
                try:  # the same checks the asks file gets, so a bad result never breaks a later run
                    needs = _clean_fields(r, NEEDS_YOU_KEYS, f"result {rid}")
                except InputError as exc:
                    reason = str(exc)
            if reason:
                rejected.append({"id": str(rid), "file": rel(cwd, path), "reason": reason})
                continue
            entry = entries.setdefault(rid, {"id": rid})
            if rid not in order:
                order.append(rid)
            _clear_research(entry)  # a question researched again keeps nothing of its last result
            pile = r["pile"]
            piles[pile] += 1
            entry["research"] = pile
            for k in ("because", "answer"):
                entry.pop("_" + k, None)
            def own(keys: Tuple[str, ...]) -> None:
                """Research is about to set these: keep what the asks file had, to put back."""
                entry["_saved"] = {k: entry[k] for k in keys if k in entry}
                entry["_research"] = list(keys)
            if pile in RESEARCHED:
                label = r["answer"].strip() if pile == "answered" else "Close it: " + r["answer"].strip()
                quiet = rid not in blocking_ids and "blocks" not in entry  # a BLOCKING one does hold its doc up
                own(("options", "evidence", "why", "group") + (("blocks",) if quiet else ()))
                entry["options"] = [{"label": label, "recommended": True,
                                     "because": str(r.get("because") or "research found it"),
                                     "then": "the answer is written under the question in its doc"}]
                entry["evidence"] = [{"ref": str(e.get("ref", "")), "note": str(e.get("note", ""))}
                                     for e in r["evidence"]]
                entry["why"] = str(r.get("because") or "")
                if quiet:
                    entry["blocks"] = RESEARCH_BLOCKS if pile == "answered" else RESEARCH_STALE
                entry["group"] = RESEARCH_GROUP
            elif pile == "same-as":
                entry["sameAs"] = r["sameAs"]
            else:
                own(tuple(needs))
                entry.update(needs)
    merged = dict(asks, items=[entries[i] for i in order])
    return merged, {"format": "promise-merge", "files": len(files), "piles": piles, "rejected": rejected}


def render_sheet(sheet: Dict[str, Any]) -> str:
    template_path = os.path.normpath(os.path.join(_SCRIPTS_DIR, TEMPLATE_RELATIVE_PATH))
    template = orient.read_text_tolerant(template_path)
    # Escaped so no string in the data can close the <script> element that carries it.
    data = json.dumps(sheet, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    title = sheet["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return template.replace("<title>Decision sheet</title>", f"<title>{title}</title>", 1).replace(SHEET_MARKER, data, 1)


# ---------------------------------------------------------------------------
# Applying answers
# ---------------------------------------------------------------------------


def load_answers(path: str) -> Dict[str, Any]:
    try:
        # "-" is standard input: the promise mod's pane hands its answers over that way.
        raw = sys.stdin.buffer.read().decode("utf-8-sig") if path == "-" else orient.read_text_tolerant(path)
    except (OSError, ValueError) as exc:
        raise InputError(f"could not read {path}: {exc}")
    candidates = [raw] + FENCED_JSON_RE.findall(raw)
    if "{" in raw:
        candidates.append(raw[raw.index("{"): raw.rindex("}") + 1])
    for text in candidates:
        try:
            data = json.loads(text)
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("format") == "promise-picks":
            if data.get("version") != 1:
                raise InputError(f"promise-picks version {data.get('version')!r} is not 1")
            return data  # the pane's picks: apply reads them with parse_picks
        if isinstance(data, dict) and data.get("format") == "promise-answers":
            if data.get("version") != 1:
                raise InputError(f"answers version {data.get('version')!r} is not 1")
            if not isinstance(data.get("answers"), list):
                raise InputError("answers must be a list")
            return data
    raise InputError(f"{path} holds no promise-answers JSON")


def one_line(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text if len(text) <= VALUE_LIMIT else text[: VALUE_LIMIT - 1] + "…"


def _read_doc(path: str) -> Tuple[List[str], str, bool]:
    with open(path, "rb") as fh:
        raw = fh.read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    newline = "\r\n" if b"\r\n" in raw else "\n"
    return orient.read_text_tolerant(path).split("\n"), newline, bom


def _inside(cwd: str, doc_arg: str) -> Optional[str]:
    doc = os.path.normpath(os.path.join(cwd, str(doc_arg)))
    return doc if os.path.commonpath([doc, cwd]) == cwd and os.path.isfile(doc) else None


def apply_answers(cwd: str, data: Dict[str, Any], date: str, by: Optional[str], dry_run: bool) -> Dict[str, Any]:
    written: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for_agent: List[Dict[str, Any]] = []
    pending: Dict[str, List[Tuple[Dict[str, Any], str]]] = {}
    overrides: Dict[str, List[Dict[str, Any]]] = {}
    for n, ans in enumerate(data["answers"]):
        if not isinstance(ans, dict) or not isinstance(ans.get("value"), str) or not ans["value"].strip():
            skipped.append({"index": n, "reason": "no value"})
            continue
        if ans.get("kind") == "decided":
            # "Ask me instead" on an agent decision: the row becomes a §9 question.
            doc = _inside(cwd, ans["doc"]) if ans.get("doc") and ans.get("decision") else None
            if doc is None:
                skipped.append({"id": ans.get("id"), "reason": "names no agent decision in a doc under the project"})
            else:
                overrides.setdefault(doc, []).append(ans)
            continue
        if not ans.get("doc") or not ans.get("q"):
            for_agent.append(ans)
            continue
        doc = _inside(cwd, ans["doc"])
        if doc is None:
            skipped.append({"id": ans.get("id"), "reason": f"doc not found under the project: {ans['doc']}"})
            continue
        pending.setdefault(doc, []).append((ans, one_line(ans["value"])))
    stamp = f"{date}, {one_line(by)}" if by and by.strip() else date
    for doc in list(dict.fromkeys(list(pending) + list(overrides))):
        lines, newline, bom = _read_doc(doc)
        inserts: List[Tuple[int, str]] = []
        questions = {q["q"]: q for q in parse_questions(lines)}
        for ans, value in pending.get(doc, []):
            q = questions.get(str(ans["q"]))
            if q is None:
                skipped.append({"id": ans.get("id"), "reason": f"{ans['q']} is not a §9 question in {rel(cwd, doc)}"})
                continue
            body = lines[q["start"]:q["end"]]
            if any(ANSWER_RE.match(l) and l.rstrip().endswith(f"): {value}") for l in body):
                skipped.append({"id": ans.get("id"), "reason": "already written"})
                continue
            line = f"Answer ({stamp}): {value}"
            inserts.append((q["end"], line))
            written.append({"doc": rel(cwd, doc), "q": q["q"], "line": line})
        for at, line in sorted(inserts, key=lambda x: x[0], reverse=True):
            lines.insert(at, line)
        for ans in overrides.get(doc, []):
            note = (ans.get("note") or "").strip()
            reason = f"{one_line(by) if by and by.strip() else 'the owner'} chose to decide it"
            lines, done, why_not = promote_rows(lines, [str(ans["decision"])], stamp,
                                                f"{reason}: {one_line(note)}" if note else reason)
            written += [dict(w, doc=rel(cwd, doc)) for w in done]
            skipped += [{"id": ans.get("id"), "reason": r} for r in why_not]
        if (inserts or any(w["doc"] == rel(cwd, doc) and w.get("decision") for w in written)) and not dry_run:
            write_doc(doc, lines, newline, bom)
    return {"written": written, "skipped": skipped, "forAgent": for_agent, "dryRun": dry_run}


def write_doc(doc: str, lines: List[str], newline: str, bom: bool) -> None:
    with open(doc, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as fh:
        fh.write(newline.join(lines))


# ---------------------------------------------------------------------------
# Agent decisions: promote to a §9 question, change the policy, re-check at arm
# ---------------------------------------------------------------------------


# ``prototype`` is the legacy name of ``fast``: read as fast, never written.
POLICY_RANK = {"fast": 0, "prototype": 0, "auto": 1, "spec": 2}
STATE_PROVISIONAL_RE = re.compile(r"State:\s*provisional\b")


def _header_value(lines: List[str], marker: str, other: Optional[str] = None) -> str:
    scan = lint_outcome.unfenced(lines)
    idx = lint_outcome.find_line_index(scan, lambda l: marker in l)
    return lint_outcome.parse_header_field_value(scan, idx, marker, other) if idx is not None else ""


def _next_question_number(lines: List[str]) -> int:
    numbers = [int(q["q"][1:]) for q in parse_questions(lines) if re.fullmatch(r"Q\d+", q["q"])]
    return max(numbers, default=0) + 1


def _append_to_section(lines: List[str], n: int, new: List[str]) -> List[str]:
    """``new`` appended at the end of section ``n``, after its last non-blank line,
    with one blank line before it and one after."""
    bounds = lint_outcome.section_bounds(lines, n)
    if bounds is None:
        raise InputError(f"the doc has no §{n}")
    at = bounds[1]
    while at > bounds[0] + 1 and not lines[at - 1].strip():
        at -= 1
    block = [""] + new + ([""] if at < len(lines) and lines[at].strip() else [])
    return lines[:at] + block + lines[at:]


def _find_agent_row(lines: List[str], row_id: str) -> Optional[Dict[str, Any]]:
    want = decision_key(row_id)
    for r in lint_outcome.parse_agent_decisions(lines):
        if decision_key(r["id"]) == want:
            return r
    return None


def promote_rows(lines: List[str], row_ids: List[str], stamp: str, reason: str
                 ) -> Tuple[List[str], List[Dict[str, Any]], List[str]]:
    """Each named provisional agent decision, put to the human: a new BLOCKING §9
    question at the end of §9 (appended, as answers are; nothing in §9 is rewritten)
    and the row's ``State: provisional`` made ``State: asked Qn``. Returns the new
    lines, what was written, and why any row was left as it was."""
    owner = _header_value(lines, "Owner:", "Last decision:") or "the doc's owner"
    written: List[Dict[str, Any]] = []
    problems: List[str] = []
    for row_id in row_ids:
        row = _find_agent_row(lines, row_id)
        if row is None:
            problems.append(f"{decision_key(row_id)}: no agent decision with that number in §8")
            continue
        if row["state"] != "provisional":
            problems.append(f"{decision_key(row_id)}: already {row['state'] or 'without a state'}")
            continue
        q = f"Q{_next_question_number(lines)}"
        idx = row["line"] - 1
        lines = list(lines)
        lines[idx] = STATE_PROVISIONAL_RE.sub(f"State: asked {q}", lines[idx], count=1)
        question = (f"{q} — owner: {owner} — BLOCKING — the agent chose: {one_line(row['decision']).rstrip('.')} "
                    "(§8 Decisions). Keep that, or decide another way?")
        why = f"Why asked ({stamp}): {one_line(reason)}."
        lines = _append_to_section(lines, 9, [question, why])
        written.append({"decision": row["id"], "q": q, "line": question})
    return lines, written, problems


def _open_doc(cwd: str, doc_arg: str) -> str:
    doc = _inside(cwd, doc_arg)
    if doc is None:
        raise InputError(f"no such doc under the project: {doc_arg}")
    return doc


def promote_command(cwd: str, doc_arg: str, row_ids: List[str], date: str, by: str, reason: Optional[str],
                    dry_run: bool) -> Dict[str, Any]:
    doc = _open_doc(cwd, doc_arg)
    lines, newline, bom = _read_doc(doc)
    lines, written, problems = promote_rows(lines, row_ids, f"{date}, {one_line(by)}",
                                           reason or "asked for by name")
    if written and not dry_run:
        write_doc(doc, lines, newline, bom)
    return {"doc": rel(cwd, doc), "written": written, "skipped": problems, "dryRun": dry_run}


def _set_policy_line(lines: List[str], policy: str) -> List[str]:
    found = lint_outcome.decision_policy_lines(lines)
    lines = list(lines)
    if found:
        lines[found[0][0]] = f"Decision policy: {policy}"
        return lines
    scan = lint_outcome.unfenced(lines)
    end = lint_outcome._header_end(scan)
    at = lint_outcome.find_line_index(scan[:end], lambda l: l.startswith("Owner:"))
    if at is None:
        at = lint_outcome.find_line_index(scan[:end], lambda l: lint_outcome.STATUS_RE.match(l) is not None)
    if at is None:
        raise InputError("the doc has no Status: or Owner: header line to put the policy under")
    return lines[:at + 1] + [f"Decision policy: {policy}"] + lines[at + 1:]


def _log_in_section_8(lines: List[str], date: str, decision: str, owner: str, why: str) -> List[str]:
    """One row appended to §8's decisions table (the one with Decision and Owner columns)."""
    bounds = lint_outcome.section_bounds(lines, 8)
    if bounds is None:
        raise InputError("the doc has no §8 Decisions")
    for table in lint_outcome.split_tables(lines, bounds[0] + 1, bounds[1]):
        header = [c.strip().lower() for c in table[0][1]]
        if "decision" in header and "owner" in header:
            numbers = [int(cells[0]) for _n, cells in table[1:] if cells and cells[0].strip().isdigit()]
            number = max(numbers, default=0) + 1
            row = {"#": str(number), "date": date, "decision": decision, "owner": owner, "why": why}
            cells = [row.get(h, "") for h in header]
            last = table[-1][0]  # 1-based line of the table's last row
            return lines[:last] + ["| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |"] + lines[last:]
    raise InputError("§8 has no decisions table (a header with Decision and Owner columns)")


def policy_command(cwd: str, doc_arg: str, to: str, by: str, promote: List[str], date: str,
                   dry_run: bool) -> Dict[str, Any]:
    """The human picked ``to``: write it in the header, log it in §8, and apply the
    switching rules (outcome-framework.md § Decision policy)."""
    doc = _open_doc(cwd, doc_arg)
    lines, newline, bom = _read_doc(doc)
    before = lint_outcome.get_decision_policy(lines)
    found = lint_outcome.decision_policy_lines(lines)
    written_as = found[0][1] if found else None
    # A header that holds an alias (``prototype``) is rewritten to the name it
    # reads as, so "already fast" is said only of a line that says fast.
    if before == to and written_as == to:
        raise InputError(f"the doc's decision policy is already {to}")
    tightening = POLICY_RANK[to] > POLICY_RANK[before or "spec"]
    same = POLICY_RANK[to] == POLICY_RANK[before or "spec"]  # an alias rewritten: no rule changes
    provisional = [r["id"] for r in lint_outcome.parse_agent_decisions(lines) if r["state"] == "provisional"]
    if to == "spec":
        named = provisional  # under spec the human decides every one
    else:
        named = promote
    lines = _set_policy_line(lines, to)
    was = (written_as if written_as in lint_outcome.DECISION_POLICY_ALIASES else before) or "none (read as spec)"
    lines = _log_in_section_8(lines, date, f"Decision policy: {to} (was {was}).", one_line(by),
                              f"{one_line(by)} chose it; from here the agent asks or records decisions by it.")
    stamp = f"{date}, {one_line(by)}"
    lines, written, problems = promote_rows(lines, named, stamp, f"the doc moved to Decision policy: {to}")
    left = [r for r in provisional if decision_key(r) not in {decision_key(w["decision"]) for w in written}]
    open_questions = [q["q"] for q in parse_questions(lines) if not q["answered"]]
    if not dry_run:
        write_doc(doc, lines, newline, bom)
    shown_from = written_as if written_as in lint_outcome.DECISION_POLICY_ALIASES else before
    result: Dict[str, Any] = {"doc": rel(cwd, doc), "from": shown_from, "to": to,
                              "direction": "tighter" if tightening else "same" if same else "looser",
                              "written": written, "skipped": problems, "dryRun": dry_run}
    if tightening and to != "spec" and left:
        result["toJudge"] = [decision_key(r) for r in left]
        result["next"] = ("judge each provisional decision against the new policy; promote any it would have "
                          "asked: decisions.py promote <doc> --decision <id> --by <name>")
    if not tightening and not same:
        result["openQuestions"] = open_questions
        result["next"] = "a looser policy never answers an open question: these stay open for the human"
    return result


def open_policy_command(cwd: str, to: str, by: str, docs_home_arg: Optional[str], date: str,
                        dry_run: bool) -> Dict[str, Any]:
    """The human said yes to stamping the docs in flight: every doc at draft, agreed or
    building whose header has no ``Decision policy:`` line gets the line and the §8 row
    ``policy`` writes. Shipped and superseded docs, and a doc whose line holds a value a
    person wrote, are left alone. The same scan and the same test as orient's
    ``legacyPolicyDocs``; a second run finds nothing to stamp."""
    home = docs_home_arg or orient.build_orientation(None, cwd).get("docsHome")
    if not home:
        raise InputError("no docs home; pass --docs-home")
    if not os.path.isdir(os.path.join(cwd, home)):
        raise InputError(f"docs home is not a folder: {home}")
    stamped: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    for d in orient.legacy_policy_docs(orient.scan_existing_docs(cwd, home, keep_private=True)):
        doc = rel(cwd, os.path.join(cwd, d["path"]))
        lines, _newline, _bom = _read_doc(os.path.join(cwd, doc))
        if lint_outcome.decision_policy_lines(lines):
            # a line the lint reads that orient's quick scan did not: said, so a count
            # orient still reports is never met with a silent "nothing to stamp"
            skipped.append({"doc": doc, "reason": "its header has a Decision policy line the lint reads, which "
                                                  "orient's scan did not: left as it is"})
            continue
        try:
            result = policy_command(cwd, doc, to, by, [], date, dry_run)
        except InputError as exc:
            skipped.append({"doc": doc, "reason": str(exc)})
            continue
        entry = {"doc": doc, "status": d["status"], "written": result["written"]}
        if result.get("openQuestions"):
            entry["openQuestions"] = result["openQuestions"]  # a looser policy answers none of them
        stamped.append(entry)
    return {"to": to, "stamped": stamped, "skipped": skipped, "dryRun": dry_run,
            "next": ("the edits are in the working tree: show them to the human, who commits them"
                     if stamped and not dry_run else None)}


REVERSIBLE_AT_ARM_RE = re.compile(r"\barm(ed|ing)?\b", re.IGNORECASE)
DATE_IN_TEXT_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def recheck(cwd: str, doc_arg: str, date: str) -> Dict[str, Any]:
    """The provisional agent decisions ``arm`` must look at again before it arms:
    a review trigger of ``before arm`` or one whose date has come, and a
    reversible-until that closes at arm or whose date has come. The script says
    which are due; whether each is still cheap to reverse is the agent's reading,
    and any that is not goes to the human (``promote``)."""
    doc = _open_doc(cwd, doc_arg)
    lines, _newline, _bom = _read_doc(doc)
    due = []
    for r in lint_outcome.parse_agent_decisions(lines):
        if r["state"] != "provisional":
            continue
        review = r["fields"].get("Review", "")
        until = r["fields"].get("Reversible until", "")
        reasons = []
        if review.strip().lower() == "before arm":
            reasons.append("its review is before arm")
        m = re.match(r"(?i)^on (\d{4}-\d{2}-\d{2})$", review.strip())
        if m and m.group(1) <= date:
            reasons.append(f"its review date {m.group(1)} has come")
        if REVERSIBLE_AT_ARM_RE.search(until):
            reasons.append("it stops being cheap to reverse at arm")
        for d in DATE_IN_TEXT_RE.findall(until):
            if d <= date:
                reasons.append(f"it was reversible until {d}")
        if reasons:
            due.append({"id": decision_key(r["id"]), "decision": r["decision"], "why": "; ".join(reasons),
                        "rollback": r["fields"].get("Rollback", ""), "line": r["line"]})
    return {"doc": rel(cwd, doc), "date": date, "due": due,
            "next": ("for each, is reversal still cheap? If not, decisions.py promote <doc> --decision <id> "
                     "--by <name> --reason <why>, and arm waits for the answer") if due else "nothing is due"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


NEXT_STEP = {
    "rich": ("next: in Claude Code with the promise mod (the tool mcp__promise__decision_pane is listed), "
             "pass this sheet's --json file to that tool and end the turn; else in Claude, publish the --out page "
             "with the Artifact tool, capabilities {\"db\": {}}, and give the link; on a host with an HTML canvas, show the page there; in a chat that shows "
             "only text, send the --chat text as the message. Never send the sheet's files "
             "(references/decision-sheet.md §2)"),
    "ask-questions": ("next: ask these with the host's question prompt (AskUserQuestion in Claude Code); "
                      "never send the sheet's files (references/decision-sheet.md §2)"),
}
SHEET_EPILOG = ("Show the sheet on the surface its 'surface' names (references/decision-sheet.md §2). "
                "rich: in Claude, publish --out as an Artifact with the db capability; an HTML canvas "
                "elsewhere; --chat in a text-only chat. ask-questions: the host's question prompt. "
                "Never send the sheet's .json or .md files to the human: they are for agents.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect the decisions waiting on a human; write the answers back.")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("sheet", help="collect open §9 questions and extra asks into one sheet",
                       epilog=SHEET_EPILOG)
    s.add_argument("docs", nargs="*", help="outcome docs (default: every doc under docsHome)")
    s.add_argument("--docs-home", default=None)
    s.add_argument("--asks", default=None, help="JSON file: title, intro, items")
    s.add_argument("--blocking-only", action="store_true")
    s.add_argument("--cwd", default=None)
    s.add_argument("--out", default=None, help="write the HTML page here")
    s.add_argument("--md", default=None, help="write the Markdown twin here: for agents and editors, never the human")
    s.add_argument("--limit", type=int, default=ROUND_LIMIT, metavar="N",
                   help=f"at most N items in this round, BLOCKING first (default {ROUND_LIMIT}); the rest come later")
    s.add_argument("--all", action="store_true", help="every open item in one sheet, with no round limit")
    s.add_argument("--asks-skeleton", default=None, metavar="PATH",
                   help="write an asks file for this round: each item's fields to fill, the doc's words, what is unclear")
    s.add_argument("--prompt-json", action="store_true",
                   help="print this round as question-prompt batches of four, with the reply code for each option")
    s.add_argument("--only", action="append", default=None, metavar="IDS",
                   help="only these item ids, comma-separated or repeated (a doc question is <path>#Qn)")
    s.add_argument("--chat", default=None, metavar="PATH",
                   help="write the sheet as one chat message here ('-' prints it): numbered items, lettered choices")
    s.add_argument("--comment", default=None, metavar="PATH",
                   help="write the sheet as a GitHub comment here ('-' prints it), with its data inside")
    s.add_argument("--json", action="store_true")
    t = sub.add_parser("triage", help="split the open questions into packets for research agents (references/research.md)")
    t.add_argument("docs", nargs="*", help="outcome docs (default: every doc under docsHome)")
    t.add_argument("--docs-home", default=None)
    t.add_argument("--asks", default=None, help="the asks file so far: what research has checked is left out")
    t.add_argument("--cwd", default=None)
    t.add_argument("--out", required=True, metavar="DIR", help="where the packets go")
    t.add_argument("--size", type=int, default=PACKET_SIZE, help=f"questions per packet (default {PACKET_SIZE})")
    m = sub.add_parser("merge-research", help="check research results and merge them into the asks file (references/research.md)")
    m.add_argument("results", nargs="+", help="result files, or the triage folder")
    m.add_argument("--doc", action="append", default=[], metavar="PATH",
                   help="an outcome doc triage was given by name (repeat); default: every doc under docsHome")
    m.add_argument("--docs-home", default=None)
    m.add_argument("--asks", default=None, help="the asks file to merge into (default: a new one)")
    m.add_argument("--out", default=None, help="where to write the merged asks file (default: --asks)")
    m.add_argument("--cwd", default=None)
    a = sub.add_parser("apply", help="append answers to §9 of each doc")
    a.add_argument("answers", nargs="?", default=None,
                   help="a promise-answers JSON file, or pasted text holding one; '-' reads standard input")
    a.add_argument("--reply", default=None, metavar="PATH",
                   help="a person's short reply ('all recommended', '1a 2b - note', '3: words') in a file")
    a.add_argument("--sheet", default=None, metavar="PATH",
                   help="the sheet the reply answers: its --json output, or its posted comment (or the thread)")
    a.add_argument("--cwd", default=None)
    a.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    a.add_argument("--by", default=None, help="who answered")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--json", action="store_true")
    pr = sub.add_parser("promote", help="put named agent decisions (§8, Owner agent) to the human as §9 questions")
    pr.add_argument("doc")
    pr.add_argument("--decision", action="append", required=True, metavar="ID",
                    help="the §8 row: 3 or D3 (repeat, or comma-separate)")
    pr.add_argument("--by", required=True, help="who asks: the human, or 'agent' at the arm re-check")
    pr.add_argument("--reason", default=None, help="why it is asked now, in plain words")
    po = sub.add_parser("policy", help="write the decision policy the human picked, and apply the switching rules")
    po.add_argument("doc", nargs="?", default=None, help="the doc (not with --open)")
    po.add_argument("--open", action="store_true",
                    help="stamp every doc at draft, agreed or building that has no policy line (one human yes)")
    po.add_argument("--docs-home", default=None, help="with --open: the folder to scan (default: orient's docsHome)")
    po.add_argument("--to", required=True, choices=sorted(POLICY_RANK), help="the policy the human picked")
    po.add_argument("--by", required=True, help="the human who picked it")
    po.add_argument("--promote", action="append", default=[], metavar="IDS",
                    help="agent decisions the new policy would have asked (fast to auto: the agent's reading)")
    rc = sub.add_parser("recheck", help="the provisional agent decisions due for a second look at arm")
    rc.add_argument("doc")
    for s_ in (pr, po, rc):
        s_.add_argument("--cwd", default=None)
        s_.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
        s_.add_argument("--json", action="store_true")
    for s_ in (pr, po):
        s_.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    cwd = os.path.abspath(args.cwd) if args.cwd else os.path.abspath(os.getcwd())
    try:
        if not os.path.isdir(cwd):
            raise InputError(f"no such directory: {cwd}")
        if args.command == "sheet":
            printing = [n for n, on in (("--json", args.json), ("--chat -", args.chat == "-"),
                                        ("--comment -", args.comment == "-"), ("--prompt-json", args.prompt_json)) if on]
            if args.limit is not None and args.limit < 1:
                raise InputError("--limit must be 1 or more")
            if len(printing) > 1:
                raise InputError(f"{' and '.join(printing)} would all print; write all but one to a file")
            only = [i.strip() for group in (args.only or []) for i in group.split(",") if i.strip()]
            asks = load_asks(args.asks)
            sheet = build_sheet(cwd, find_docs(cwd, args.docs, args.docs_home), asks,
                                args.blocking_only, only or None, None if args.all else args.limit)
            md_path = args.md
            if args.asks_skeleton:
                with open(args.asks_skeleton, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(json.dumps(asks_skeleton(sheet, asks), indent=2, ensure_ascii=False) + "\n")
            if sheet["unclear"] and (args.out or args.md or args.chat or args.comment or args.prompt_json):
                raise InputError("the sheet leans on what a person cannot follow without the doc open, so "
                                 "nothing was written (references/decision-sheet.md §4):\n  - "
                                 + "\n  - ".join(sheet["unclear"]))
            if args.out and args.out.lower().endswith(".md"):
                raise InputError("--out writes the HTML page; give it an .html name (the twin is --md)")
            if args.out and md_path and os.path.abspath(md_path) == os.path.abspath(args.out):
                raise InputError("the Markdown twin would overwrite the page; give --out an .html name "
                                 "or --md another path")
            if args.out:
                html = render_sheet(sheet)
                with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(html)
            if md_path:
                with open(md_path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(render_markdown(sheet))
            for target, render in ((args.chat, render_chat), (args.comment, render_comment)):
                text = render(sheet) if target else ""
                if target == "-":
                    sys.stdout.write(text)
                elif target:
                    with open(target, "w", encoding="utf-8", newline="\n") as fh:
                        fh.write(text)
            if args.prompt_json:
                print(json.dumps(prompt_batches(sheet), indent=2, ensure_ascii=False))
                return 0
            if "-" in (args.chat, args.comment):
                return 0
            next_step = NEXT_STEP.get(sheet["surface"])
            if sheet["counts"]["later"] and sheet["counts"]["unresearched"]:
                next_step = (f"research first: {sheet['counts']['later'] + sheet['counts']['items']} open items is "
                             "more than one round. Offer to send research agents before asking the human "
                             "(decisions.py triage; references/research.md). " + (next_step or ""))
            if next_step and sheet["surface"] == "rich" and not args.out:
                next_step = next_step.replace("the --out page", "the page (add --out <scratch>/decisions.html)")
            if args.json:
                # Only the --json output carries each item's lettered replies: the page, the
                # comment and the chat message letter their own, and embed the sheet without them.
                shown = dict(sheet, items=[dict(i, replies=r, replyWords=w, kindTag=KIND_TAGS.get(i["kind"], "question"))
                                           for i in sheet["items"] for r, w in [pane_replies(i)]])
                print(json.dumps(dict(shown, next=next_step) if next_step else shown, indent=2, ensure_ascii=False))
            else:
                c = sheet["counts"]
                wrote = [p for p in (args.out, md_path, args.chat, args.comment, args.asks_skeleton) if p]
                where = f"; wrote {' and '.join(wrote)}" if wrote else ""
                later = (f"; {c['later']} more ({c['laterBlocking']} blocking) in later rounds: apply this "
                         "round's answers, then build the next") if c["later"] else ""
                print(f"promise decisions: {c['items']} items, {c['blocking']} blocking; surface: "
                      f"{sheet['surface']}{where}{later}")
                blocking = [i for i in sheet["items"] if i.get("blocking") is True and not in_research_group(i)]
                for i in blocking[:SUMMARY_LIMIT]:
                    print(f"blocking: {i['id']}: {_md(i.get('text', ''))[:120]}")
                if len(blocking) > SUMMARY_LIMIT:
                    print(f"blocking: and {len(blocking) - SUMMARY_LIMIT} more")
                for w in sheet["warnings"]:
                    print(f"warning: {w}")
                for w in sheet["unclear"]:
                    print(f"unclear: {w}")
                if next_step:
                    print(next_step)
            return 0
        if args.command in ("triage", "merge-research"):
            # a first merge starts the asks file it names
            fresh = args.command == "merge-research" and args.asks and not os.path.exists(args.asks)
            asks = {} if fresh else load_asks(args.asks)
            docs = find_docs(cwd, getattr(args, "docs", None) or getattr(args, "doc", []), args.docs_home)
            sheet = build_sheet(cwd, docs, asks, False, None, None)
            if args.command == "triage":
                if args.size < 1:
                    raise InputError("--size must be 1 or more")
                result = triage(sheet, os.path.abspath(args.out), args.size)
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0
            target = args.out or args.asks
            if not target:
                raise InputError("merge-research needs --asks or --out: the asks file to write")
            merged, report = merge_research(cwd, sheet, args.results, asks)
            with open(os.path.abspath(target), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")
            report["wrote"] = target
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 1 if report["rejected"] else 0
        if args.date is not None and (not ISO_DATE_RE.match(args.date) or not _is_date(args.date)):
            raise InputError(f"--date {args.date!r} is not a calendar date in YYYY-MM-DD form")
        date = args.date or datetime.date.today().isoformat()
        if getattr(args, "to", None) == "prototype":
            args.to = "fast"  # the legacy name is read, never written
        if getattr(args, "by", None) is not None and ("\n" in args.by or "\r" in args.by):
            raise InputError("--by must be one line")
        if args.command in ("promote", "policy") and not args.by.strip():
            raise InputError("--by must name who decided")
        if args.command in ("promote", "policy", "recheck"):
            if args.command == "promote":
                ids = [i.strip() for g in args.decision for i in g.split(",") if i.strip()]
                result = promote_command(cwd, args.doc, ids, date, args.by, args.reason, args.dry_run)
            elif args.command == "policy" and args.open:
                if args.doc or args.promote:
                    raise InputError("policy --open stamps every open doc with no policy line; "
                                     "name no doc and no --promote")
                result = open_policy_command(cwd, args.to, args.by, args.docs_home, date, args.dry_run)
                if args.json:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                    return 0
                verb = "would write" if args.dry_run else "wrote"
                for s_ in result["stamped"]:
                    print(f"{verb} {s_['doc']}: Decision policy: {args.to} (was none; {s_['status']})")
                    if s_.get("openQuestions"):
                        print(f"  still open for the human: {', '.join(s_['openQuestions'])}")
                for s_ in result["skipped"]:
                    print(f"skipped {s_['doc']}: {s_['reason']}")
                if not result["stamped"] and not result["skipped"]:
                    print("nothing to stamp: every doc at draft, agreed or building has a Decision policy line")
                if result.get("next"):
                    print("next: " + result["next"])
                return 0
            elif args.command == "policy":
                if not args.doc:
                    raise InputError("policy needs a doc, or --open for every open doc with no policy line")
                if args.docs_home:
                    raise InputError("--docs-home goes with --open")
                ids = [i.strip() for g in args.promote for i in g.split(",") if i.strip()]
                result = policy_command(cwd, args.doc, args.to, args.by, ids, date, args.dry_run)
            else:
                result = recheck(cwd, args.doc, date)
            if args.json:
                print(json.dumps(result, indent=2, ensure_ascii=False))
                return 0
            verb = "would write" if result.get("dryRun") else "wrote"
            if args.command == "policy":
                print(f"{verb} {result['doc']}: Decision policy: {result['to']} (was {result['from'] or 'none'}; "
                      f"{result['direction']})")
            for w in result.get("written", []):
                print(f"{verb} {result['doc']} {w['q']} for agent decision {decision_key(w['decision'])}: {w['line']}")
            for s_ in result.get("skipped", []):
                print(f"skipped {s_}")
            for d in result.get("due", []):
                print(f"due {d['id']}: {_md(d['decision'])} ({d['why']})")
            if result.get("toJudge"):
                print("to judge: " + ", ".join(result["toJudge"]))
            if result.get("openQuestions"):
                print("still open: " + ", ".join(result["openQuestions"]))
            if result.get("next"):
                print("next: " + result["next"])
            return 0
        unanswered: List[str] = []
        if args.reply:
            if args.answers:
                raise InputError("apply takes an answers file or --reply, not both")
            if not args.sheet:
                raise InputError("--reply needs --sheet: the posted comment, or the sheet's --json output")
            sheet = load_sheet(args.sheet)
            try:
                reply_text = orient.read_text_tolerant(args.reply)
            except (OSError, ValueError) as exc:
                raise InputError(f"could not read --reply {args.reply}: {exc}")
            if SHEET_DATA_RE.search(reply_text) or REPLY_HELP in reply_text:
                raise InputError("the reply file holds the sheet itself; save only the person's own words "
                                 "to it, and pass the sheet with --sheet")
            answers, unanswered = parse_reply(reply_text, sheet)
            data = {"format": "promise-answers", "version": 1, "sheet": sheet.get("id"), "answers": answers}
        elif args.answers:
            data = load_answers(args.answers)
            if data.get("format") == "promise-picks":
                data, unanswered = parse_picks(data)
        else:
            raise InputError("apply needs an answers file, or --reply with --sheet")
        result = apply_answers(cwd, data, date, args.by, args.dry_run)
        result["notAnswered"] = unanswered
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            verb = "would write" if args.dry_run else "wrote"
            for w in result["written"]:
                print(f"{verb} {w['doc']} {w['q']}: {w['line']}")
            for s in result["skipped"]:
                print(f"skipped {s.get('id', s.get('index'))}: {s['reason']}")
            for f in result["forAgent"]:
                print(f"for the agent {f.get('id')}: {one_line(f.get('value', ''))}")
            for i in result["notAnswered"]:
                print(f"not answered: {i}")
        return 0
    except InputError as exc:
        print(f"decisions.py: {exc}", file=sys.stderr)
        return 2


def _is_date(text: str) -> bool:
    try:
        datetime.date.fromisoformat(text)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    sys.exit(main())
