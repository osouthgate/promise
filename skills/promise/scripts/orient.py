#!/usr/bin/env python3
"""Phase 0 orientation for the promise skill.

Resolves the framework path, the project config, the docs home, the
project's type-check/test/lint commands, existing outcome docs, and
CLAUDE.md adoption state, then prints one JSON object to stdout. It also
reports how many Markdown files a docs home holds when none of them is an
outcome doc (``docsHomeForeignDocs``), the test runners the project's own
files name and how each writes JUnit XML (``testRunners``, read from
package.json and Python config files, never run), and the branch ``arm``
works on (``branch``: the config's ``current`` or ``{slug}`` pattern, else
``feat/{slug}``). ``skillVersion`` is the version in VERSION beside
SKILL.md (null when absent); a config's ``minSkillVersion`` above it warns.

See references/architecture.md §5 (schema and detection rules) and
§6 (config contract). For a valid invocation this script never exits
non-zero: every problem is recorded in the "warnings" list of the
emitted JSON instead of raising or failing the process, so a caller
can always parse stdout as JSON and always finds every schema key
present (null when unknown). Three things are not valid invocations
and exit 2 with one line on stderr: an argparse usage error (an
unrecognised flag, a missing value), a ``--cwd`` that is not a
directory, and an ``--input-file`` that cannot be read or is not UTF-8.

"mode" is the mode word passed with ``--mode`` (or "infer" for an
unrecognised word) and null when the flag was not given — the JSON
never claims a mode nobody asked for.

Config paths (docsHome, plansFolder, frameworkPath) are project-relative
with forward slashes; a value written with backslashes is normalised to
forward slashes and warned about, so a config written on one OS reads
the same on another. A configured docsHome, map.recipe or map.index
that does not exist on disk is warned about and still returned —
existence is reported, not enforced, so the first mode to use the path
can decide what to do.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

RECOGNISED_MODES = (
    "new", "revise", "review", "merge", "arm", "intake", "reconcile", "adopt",
    "backfill", "issue", "pr", "retro", "upgrade", "doctor", "onboard",
)

# "version" is the config's version key; "$schema" is accepted for configs
# written before it existed and warned about as deprecated.
CONFIG_VERSION = 1

KNOWN_CONFIG_KEYS = {
    "$schema", "$comment", "version", "docsHome", "frameworkPath", "plansFolder",
    "commands", "map", "branch", "run", "decisionPolicy", "minSkillVersion", "sibling",
    "protectedPaths",  # read by changed_rows.py's tiny check, which warns on a bad value
    "pinFiles",  # read by pin_check.py and upgrade.py, which refuse a bad value
    "upstreamPath",  # a local promise checkout pin_check.py reads a private upstream through
}

# The skill's own version: VERSION beside SKILL.md holds the plugin's version, so a
# vendored or linked copy of the skill still carries it. minSkillVersion in a config
# names the oldest skill the project expects.
VERSION_FILE = "VERSION"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

# A read-only map in a sibling repository, for a project with "map": false:
# the four string keys it needs. adapter.py runs only its find and row.
# mapUsable stays false beside it: the project has no map of its own, so every
# mode that writes to a map takes its no-map path; only reads look at "sibling".
SIBLING_KEYS = ("repo", "path", "find", "row")

# The repo's decision policy (outcome-framework.md § Decision policy): one config line a
# human sets, which every new doc takes; `auto` when it is not set.
DECISION_POLICIES = ("fast", "auto", "spec")
# The legacy value is read as exactly ``fast``; writers emit ``fast``.
DECISION_POLICY_ALIASES = {"prototype": "fast"}
DEFAULT_DECISION_POLICY = "auto"

# How big the ask is (SKILL.md § Size the ask first), from its words: a hint only, and
# only ever toward the larger size. A protected category's words make it risky; words
# cannot show that an ask is tiny, so that call is always the agent's.
SIZE_RISKY_RE = re.compile(
    r"\b(?:bill(?:s|ing)?|pric(?:e|es|ing)|payments?|pay(?:out)?s?|invoices?|refunds?|subscriptions?|"
    r"retention|retain|delet(?:e|es|ing|ion) (?:the |a |an |all )?(?:users?|accounts?|data|records?|history)|"
    r"gdpr|consent|privacy|legal|terms of (?:service|use)|licen[cs]es?|permissions?|auth(?:n|z|entic\w*|ori[sz]\w*)?|bcrypt|jsonwebtoken|passport|"
    r"log ?in|sign ?in|passwords?|credentials?|secrets?|security|access control|(?:user|admin|member) roles?|role-based|oauth|sso|saml|jwt|"
    r"stripe|paypal|braintree|terms (?:and|&|checkbox|page|link|text)|personal data|pii|email address(?:es)?|"
    r"migrations?|migrate|schema|(?:database|db|table) columns?|\w+\.\w+ columns?|api\w*|endpoints?|routes?|webhooks?|"
    r"(?:remove|ban|kick) (?:a |the |all )?(?:members?|users?)|"
    r"delet(?:e|es|ing|ion) (?:a |the |all |every )?(?:channels?|messages?|files?|members?|posts?)|"
    r"send(?:s|ing)? (?:an? )?(?:emails?|sms|texts?|notifications?|messages?))\b", re.IGNORECASE)


def resolve_decision_policy(config: Optional[dict], warnings: List[str]) -> Tuple[str, str]:
    """(policy, source): the config's ``decisionPolicy`` when it is one of the three,
    else ``auto`` from the default, with a warning for a value that is not one."""
    value = config.get("decisionPolicy") if isinstance(config, dict) else None
    if value is None:
        return DEFAULT_DECISION_POLICY, "default"
    if value in DECISION_POLICY_ALIASES:
        warnings.append(f"decisionPolicy {value!r} is read as {DECISION_POLICY_ALIASES[value]}; "
                        f"write {DECISION_POLICY_ALIASES[value]!r} in the config")
        return DECISION_POLICY_ALIASES[value], "config"
    if value not in DECISION_POLICIES:
        warnings.append(f"decisionPolicy {value!r} is not one of {', '.join(DECISION_POLICIES)}; "
                        f"using {DEFAULT_DECISION_POLICY}")
        return DEFAULT_DECISION_POLICY, "default"
    return value, "config"


# The person asks to build first and promise later: under pressure, a hotfix, a spike.
# Only words about the process count: "a spike chart", "the hotfix docs" and "get the tests
# first" are product asks, so hotfix and spike count only as the ask's first word.
DEFER_RE = re.compile(
    r"^\s*(?:/promise\s+)?(?:hot\s?fix|spike)\b"
    r"|\b(?:ship|release|push)\s+(?:it|this)\s+(?:out\s+)?first\b|\bjust\s+ship\s+it\b"
    r"|\b(?:promise|backfill|harden)\s+(?:it\s+|this\s+)?(?:later|after(?:wards)?)\b"
    r"|\bdeal\s+with\s+(?:it|the\s+promise|the\s+paperwork)\s+later\b"
    r"|\b(?:skip|no\s+time\s+for|without)\s+(?:the\s+)?(?:promise|paperwork)\b"
    r"|\bquick\s+and\s+dirty\b|\byolo\b|\bno\s+time,?\s+just\b",
    re.IGNORECASE,
)


def suggest_size(text: str) -> Tuple[Optional[str], List[str]]:
    """(size, signals) for the ask: ``deferred`` when the person asks to build first and
    promise later (references/sizing.md § Deferred), ``risky`` when it names a protected
    category, else None, and the agent sizes it by the release-note test. Deferred with a
    protected category stays deferred, and the signals say so: that one decision is
    still asked. Words never say an ask is tiny: "refactor checkout so it charges tax" is not."""
    risky = sorted({m.group(0).lower() for m in SIZE_RISKY_RE.finditer(text)})
    deferred = DEFER_RE.search(text)
    if deferred:
        signals = [f"asks to build first: {deferred.group(0).strip()!r}"]
        if risky:
            signals.append(f"names a protected category: every decision in it is still asked, as for risky "
                           f"({', '.join(risky[:5])})")
        return "deferred", signals
    if risky:
        return "risky", [f"names a protected category: {', '.join(risky[:5])}"]
    return None, []

KNOWN_COMMANDS_KEYS = {"$schema", "$comment", "typeCheck", "test", "lint"}

KNOWN_MAP_KEYS = {
    "$schema", "$comment", "recipe", "index", "find", "row", "nextId",
    "rowIdPattern", "lanes", "checks", "issueTracker", "file", "junit",
    "surfaces", "requireHomes", "learn", "refsSync", "code",
}

# Optional map commands a mode runs through adapter.py when they are set.
MAP_OPTIONAL_COMMANDS = ("learn", "refsSync", "code")

# The map keys that must all be present, as strings (lanes: as an object),
# before a map counts as configured — the mapUsable rule in
# architecture.md §5.
MAP_STRING_KEYS = ("recipe", "find", "row")

# The map keys that name a file in the project; each is warned about when
# it does not exist, without changing mapUsable.
MAP_FILE_KEYS = ("recipe", "index", "file")

ISSUE_TRACKER_KEYS = ("kind", "repo", "template")

DOCS_HOME_CANDIDATES = (
    "docs/designs", "docs/design", "docs/specs", "docs/rfcs", "design", "docs",
)

TYPE_CHECK_SCRIPT_NAMES = ("type-check", "typecheck", "tsc")

# The branch arm works on: a pattern with {slug} in it, or the literal
# "current" for a host that allows one branch per session.
DEFAULT_BRANCH = "feat/{slug}"
BRANCH_CURRENT = "current"
BRANCH_SLUG = "{slug}"
# arm creates the branch through a shell, and a mode types docsHome and
# map.junit into shell lines: a value that would read as shell syntax, or
# as a flag, is refused. A branch takes ASCII letters, digits and . _ - /
# around {slug}; a path also takes spaces and letters of any script.
BRANCH_SAFE_RE = re.compile(r"[A-Za-z0-9._/-]+")
PATH_SAFE_RE = re.compile(r"[\w ./-]+")
PATH_SAFE_WORDS = "letters, digits, spaces and . _ - /"

# Test-runner detection (testRunners): the package.json dependencies that
# name a runner, the Python config files that can mention pytest, how deep
# below the project root the scan looks, and for each runner the flag or
# setting that makes it write JUnit XML — the run map_report.py reads.
TEST_RUNNER_PACKAGES = (("vitest", "vitest"), ("jest", "jest"), ("playwright", "@playwright/test"))
PYTEST_CONFIG_FILES = ("pyproject.toml", "pytest.ini", "setup.cfg", "tox.ini")
RUNNER_SCAN_DEPTH = 3
NODE_TEST_SCRIPT_RE = re.compile(r"\bnode(?:\s+(?!&&|\|\||;)\S+)*?\s+--test(?=\s|$)")
JUNIT_HOW = {
    "vitest": "--reporter=default --reporter=junit --outputFile.junit=<path>",
    "jest": "--reporters=default --reporters=jest-junit, with JEST_JUNIT_OUTPUT_DIR=<dir> "
            "JEST_JUNIT_ADD_FILE_ATTRIBUTE=true JEST_JUNIT_CLASSNAME=\"{classname}\" "
            "JEST_JUNIT_TITLE=\"{title}\" JEST_JUNIT_ANCESTOR_SEPARATOR=\" > \" (needs the jest-junit "
            "package; without these settings the run records no file and the describe path cannot be told "
            "from the title, so a citation cannot be matched to one test)",
    "playwright": "--reporter=list,junit, with PLAYWRIGHT_JUNIT_OUTPUT_FILE=<path> "
                  "(PLAYWRIGHT_JUNIT_OUTPUT_NAME=<path> on older Playwright)",
    "pytest": "--junitxml=<path>",
    "unittest": "python -m unittest writes no JUnit: run the same suite with "
                "python3 \"${CLAUDE_SKILL_DIR}/scripts/junit_unittest.py\" --out <path> -s <tests folder> "
                "(stdlib; each case records its file, class and method), or pytest --junitxml=<path> "
                "if pytest is installed",
    "node:test": "--test-reporter=junit --test-reporter-destination=<path>. Node's own JUnit reporter "
                 "records no file and no describe path (every case has classname \"test\"), so cite "
                 "<file>::<the test's own title> and keep each title unique across the suite, or use a "
                 "reporter that records the file",
}

UNITTEST_IMPORT_RE = re.compile(r"^\s*(import unittest\b|from unittest\b)", re.M)

PROMISE_BEGIN_MARKER = "<!-- promise:begin"
IMPORT_LINE_RE = re.compile(r"^[ \t]*@(\S+?)[ \t]*$", re.MULTILINE)

TLDR_HEADING = "## 0. TLDR"

H1_RE = re.compile(r"^#\s+(.+?)\s*$")
STATUS_RE = re.compile(r"^Status:\s*(\S+)")
LAST_DECISION_RE = re.compile(r"Last decision:\s*(\S+)")
TARGET_NAME_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(?!=)")

# --- FEATURE 1: --input mode suggestion (architecture.md §4 rules 1-10) ---

_MODE_WORD_PUNCT = ".,;:!?'\"()[]{}"

# GitHub text: an issue to file or check against the map, or a pull
# request description to write. These write no doc, so they outrank every
# other signal: "review these issues" is not a doc review, and "write the PR
# description for #12" is not a reconcile.
ISSUE_PHRASE_RE = re.compile(
    r"\b(?:(?:write|file|raise|draft|create|triage|check|review|update|refresh|fill in"
    r"|open(?=\s+(?:a|an|the|one|new|this|that)\b))"
    r"(?:\s+(?!(?:for|with|in|into|about|of|on|to|from|without)\b)[\w-]+){0,4}?"
    r"\s+(?:issues\b|(?:github\s+|gh\s+)?issue\b"
    r"(?!\s+(?:tracker|refunds?|a|an|the|buttons?|forms?|pages?|screens?|links?|fields?|lists?|views?)\b))"
    r"|issues?\s+(?:#?\d+\s+)?against\s+the\s+(?:capability\s+)?map"
    r"|issue\s+template"
    r"|(?:capabilit(?:y|ies)|rows?)\s+(?:does|do|would)\s+(?:this|that|the)\s+issue"
    r"|(?:capabilit(?:y|ies)|rows?)\s+(?:for|of|in)\s+(?:(?:this|that|the)\s+)?issue\b"
    r"|map\s+(?:(?:this|that|the)\s+)?issues?\s+(?:#?\d+\s+)?(?:to|onto|against)\s+"
    r"(?:the\s+)?(?:rows?|capabilit(?:y|ies)|map)\b)",
    re.IGNORECASE,
)
PR_PHRASE_RE = re.compile(
    r"\b(?:(?:pr|pull request)\s+(?:description|body|text|summary|write-?up)"
    r"|(?:describe|write up|write|draft|fill in)\s+(?:(?:a|the|this|that|my|our)\s+)?(?:pr|pull request)\b"
    r"(?!\s+(?:template|tests?|feedback|reviews?|comments?|to|that|which|for|fixing|adding|with)\b)"
    r"|(?:description|body|text|summary|write-?up)\s+(?:for|of)\s+"
    r"(?:(?:a|the|this|that|my|our)\s+)?(?:pr|pull request)\b"
    r"|summari[sz]e\s+(?:(?:the|this|that|my|our)\s+)?(?:pr|pull request)\b"
    r"|(?:pr|pull request)\s+template)",
    re.IGNORECASE,
)
# "issue" and "pr" as a first word name the mode only when a number, a link
# or a plain pointer follows ("pr for #34", "issue 12"), and nothing says
# the work has landed: "PR #12 merged, update the map" is a reconcile, "PR
# feedback: …" an intake and "issue refunds to customers" a feature.
GITHUB_MODE_REST_RE = re.compile(
    r"\s*(?:$|#?\d+\b|https?://|[\w.-]+/[\w.-]+#\d+\b"
    r"|(?:for|about|on|from|this|these|that|the|a|an|text|body|description|block|mode"
    r"|file|write|check|triage|draft|update|refresh|open|create|describe)\b)",
    re.IGNORECASE,
)
GITHUB_MODE_VETO_RE = re.compile(
    r"\b(?:shipped|landed|merged|fixed|closed|already do|already covered)\b"
    r"|\bupdate the (?:map|row)\b",
    re.IGNORECASE,
)
# An issue phrase that names the issue for certain: a number, "file an
# issue", the map. Weaker ones ("check the issue in the billing doc") beside
# a matching doc leave the router to ask.
GITHUB_STRONG_RE = re.compile(
    r"#\d+|\b(?:issue|pr|pull request)\s+\d+\b|\b(?:file|raise|open|draft|create)\s+(?:a|an|one|new)\b"
    r"|\bagainst\s+the\s+(?:capability\s+)?map\b|\btemplate\b",
    re.IGNORECASE,
)
# A product feature around the phrase: "build a feature that lets users
# file issues" asks for a feature, not for issue text.
PRODUCT_FEATURE_RE = re.compile(
    r"\b(?:feature|button|screen|endpoint|integration"
    r"|lets?\s+(?:users?|clients?|people|admins?|customers?)"
    r"|a way (?:for|to)|automatically)\b",
    re.IGNORECASE,
)
CRITIQUE_VERB_RE = re.compile(
    r"\b(?:review|critique|feedback|check|is this any good)\b", re.IGNORECASE
)
ARM_PHRASE_RE = re.compile(
    r"\b(?:arm|start building|red tests|kick off|file the rows)\b", re.IGNORECASE
)
RECONCILE_PHRASE_RE = re.compile(
    r"\b(?:shipped|landed|already do|already covered)\b"
    r"|isn't .* covered"
    r"|update the (?:map|row)",
    re.IGNORECASE,
)
# Feedback vocabulary, the router's own phrases, and the shape of a plain
# complaint sentence — "users say X is broken", "customers complain that"
# — so a single reported sentence leans intake the way a list does.
INTAKE_WORD_RE = re.compile(
    r"\b(?:feedback|complaints?|complain(?:s|ed|ing)?|bug reports|wishes|feature requests"
    r"|(?:users?|customers?|people|clients?) (?:say|said|keep saying|report(?:ed)?|are asking|want)"
    r"|is broken|are broken|does nothing|doesn'?t work|don'?t work|not working"
    r"|what does this map to|map this|turn this into (?:scenarios|gherkins|a scenario)"
    r"|which (?:capability|promise|row) covers|add this as a scenario)\b",
    re.IGNORECASE,
)
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*]\s+|\d+\.\s+)")
# Backfill: map what an existing product does today, test by test, before
# (or instead of) promising anything new. "every test" (or route, page, …)
# counts only when a verb gives it a home ("every test needs a row",
# "every route has a home"), or as "every test we have". "backfill",
# "retrofit" and "existing product" count only beside a map word: alone,
# they are as likely a data job or a feature for that product. A bare
# "map", "row" or "test" is not a map word ("a map view", "a row limit").
# "promise", singular, names the plugin ("set up promise"), so only
# "promises" is one. A "docs site" is a product, not a set of docs.
BACKFILL_PHRASE_RE = re.compile(
    r"\b(?:map what the (?:code|product|system|app) does"
    r"|what the (?:product|code|system|app) does today)",
    re.IGNORECASE,
)
# Legacy docs moved into outcome docs. Docs moved to another tool ("migrate
# the docs to Notion", "move our docs to Confluence") are not backfill: a
# destination counts only when it names the outcome shape.
DOCS_PHRASE_RE = re.compile(
    r"\b(?:move (?:our|the) (?:existing |old )?docs\b(?![ -](?:site|website)\b)"
    r"|migrate (?:the |our )?(?:existing )?docs\b(?![ -](?:site|website)\b))",
    re.IGNORECASE,
)
DOCS_DESTINATION_RE = re.compile(
    r"(?:\s+[\w'-]+){0,5}?\s+(?:over\s+)?(?:to|into|onto)\s+(?P<dest>[^.,;:!?\n]+)", re.IGNORECASE
)
OUTCOME_SHAPE_RE = re.compile(r"\b(?:outcome|promises?|shape|capabilit(?:y|ies)|map)\b", re.IGNORECASE)
BACKFILL_WEAK_RE = re.compile(
    r"\b(?:backfill(?:s|ed|ing)?|retrofit(?:s|ted|ting)?"
    r"|existing (?:product|app|codebase|system|code))\b",
    re.IGNORECASE,
)
MAP_WORD_RE = re.compile(
    r"\b(?:(?:capability|promise|the|our) map|(?:map|capability) rows?"
    r"|capabilit(?:y|ies)|promises|outcome docs)\b",
    re.IGNORECASE,
)
# A test word is a weaker map word. It counts only where it says the
# product has the tests ("an existing product with a big test suite",
# "backfill from our tests", "it has a full test suite"), and only when no change word asks for work on
# the product or its tests ("fix the existing app so all tests pass", "the
# existing product's test suite is slow, speed it up").
TEST_WORD_RE = re.compile(
    r"\b(?:with|and|plus|from|has|have)\s+"
    r"(?:(?:a|an|its|our|the|their|all|existing|big|large|huge|full|whole|good|lot|lots|of|many|\d[\d,]*)\s+){0,3}"
    r"(?:tests|test suites?)\b",
    re.IGNORECASE,
)
CHANGE_WORD_RE = re.compile(
    r"\b(?:fix(?:es|ed|ing)?|speed\s+(?:\w+\s+)?up|faster|slow(?:er)?|flaky|failing"
    r"|refactor\w*|debug\w*|rewrite|upgrade|optimi[sz]e\w*)\b",
    re.IGNORECASE,
)
MAP_WORD_WINDOW = 40
EVERY_TEST_RE = re.compile(
    r"\bevery (?:existing )?(?:test|route|endpoint|entry point|page|screen)s?\b"
    r"(?:(?P<have>\s+(?:that\s+)?we\s+(?:already\s+)?have\b)"
    r"|(?P<home>(?:\s+(?:should|must|will|can|to|also|always|then|already))*"
    r"\s+(?:has|have|gets?|needs?|belongs?|lives?|goes|go)"
    r"(?:\s+(?:a|an|its|their|own|one|in|into|to|on|under|with))*"
    r"\s+(?:homes?|capabilit(?:y|ies)|rows?|(?:the|our|capability) map)\b))?",
    re.IGNORECASE,
)
# A feature, design, plan or spec for one thing is new, even beside a
# backfill phrase ("plan how we migrate the docs site", "add a map view to
# the existing product"). Beside one, backfill is only a hint: the
# suggestion is new, and the router asks.
FEATURE_WORD_RE = re.compile(
    r"\b(?:plan|design|spec|specify"
    r"|write (?:a|an|the|up a|up the) (?:doc|spec|plan|design|proposal)"
    r"|(?:add|show|build) (?:a|an|the|some)|implement"
    r"|let (?:users?|customers?|people|clients?)"
    r"|(?:users?|customers?|people|clients?) (?:can|should be able|to be able)"
    r"|a way to)\b",
    re.IGNORECASE,
)
# "set up" as two separate words, e.g. "set this project up", not only the
# contiguous "set up"/"setup".
ADOPT_TRIGGER_RE = re.compile(
    r"\bset\b(?:\s+\S+){0,6}?\s+up\b|\bsetup\b|\binstall\b|\bconfigure\b|\badopt\b",
    re.IGNORECASE,
)
PROMISE_WORD_RE = re.compile(r"\bpromise\b", re.IGNORECASE)
# Moving this repository to a newer promise: "upgrade promise", "update the promise
# pin", "bump the promise plugin", "is our promise version behind". The product's own
# "pin" or "version" never counts without "promise" right before it.
DOCTOR_PHRASE_RE = re.compile(
    r"\b(?:promise doctor|audit (?:the |this |our )?promise (?:setup|adoption))\b", re.IGNORECASE
)
ONBOARD_REST_RE = re.compile(
    r"^(?:promise\b|me\b|(?:this|my|our|a new|an existing) (?:project|repo)\b|an idea\b)", re.I
)
ONBOARD_PHRASE_RE = re.compile(
    r"^\s*(?:please\s+)?(?:help me (?:get started with|start using|roll out) promise\b"
    r"|guide me (?:through|into) promise\b|(?:start using|roll out) promise\b"
    r"|interview me (?:about|for) promise\b)", re.I
)
UPGRADE_PHRASE_RE = re.compile(
    r"\b(?:upgrade|update|bump)\s+(?:the\s+|our\s+|this\s+repo'?s\s+)?promise\b(?!\s+(?:docs?|sections?|in|on|for|to say)\b)"
    r"|\bpromise(?:'s)?\s+(?:pin|plugin|version|release)s?\b(?=.{0,40}\b(?:behind|upgrade|update|bump|move|old|out of date|latest)\b)"
    r"|\b(?:upgrade|update|bump|move)\b.{0,40}\bpromise(?:'s)?\s+(?:pin|plugin|version)s?\b",
    re.IGNORECASE,
)
# What may follow a leading "upgrade" for it to name the mode: promise itself (not a
# promise doc or section), or nothing but a version, a commit, "now" or "the pin".
UPGRADE_REST_RE = re.compile(
    r"(?:(?:the|our|this\s+repo'?s)\s+)?promise\b(?!'?s?\s+(?:docs?|sections?|in|on|for)\b)"
    r"|(?:to\s+)?v?\d+\.\d+(?:\.\d+)?\s*$|[0-9a-f]{7,40}\s*$|now\s*$|(?:the\s+)?pins?\s*$",
    re.IGNORECASE,
)
# An adopt trigger word aimed at *this* project reads as adopt even when the
# word "promise" is never said — "install it here", "set this project up".
ADOPT_LOCAL_RE = re.compile(
    r"\b(?:this project|this repo(?:sitory)?|it here|here)\b", re.IGNORECASE
)
ROW_ID_TOKEN_RE = re.compile(r"[^\s,;]+")

# A generic change verb aimed at "the doc"/"the outcome" with no title named
# still means revise whenever at least one outcome doc exists — the doc is
# ambiguous, the mode is not.
GENERIC_CHANGE_VERB_RE = re.compile(r"\b(?:fix|update|change)\b", re.IGNORECASE)
DOC_REFERENCE_WORD_RE = re.compile(r"\b(?:doc|outcome)\b", re.IGNORECASE)

# A critique verb with no existing-doc match: pasted or external content,
# not a request about a doc already on file. "feedback" is deliberately not
# one of these — a bare "feedback" leans intake (INTAKE_WORD_RE), and this
# rule only runs once intake's own checks have had first refusal.
REVIEW_NO_DOC_VERB_RE = re.compile(
    r"\b(?:review|critique|check|is this any good)\b", re.IGNORECASE
)

# Reconcile patterns strong enough to stand alone: a commit sha, a feat/fix
# branch prefix, or a test-file path. A bare ticket number is not among
# them — see TICKET_NUMBER_RE and RECONCILE_ACCOMPANY_RE below. A sha here
# is a 7-40 hex run with at least one letter: a digit-only run is a date
# or an id as often as a sha, and gets the same treatment as "#1234567" —
# reconcile only beside a shipped/landed/commit word.
RECONCILE_STRONG_PATTERN_RE = re.compile(
    r"\b(?=[0-9a-f]{7,40}\b)[0-9]*[a-f][0-9a-f]*\b"
    r"|\b(?:feat|fix)/"
    r"|\.test\."
    r"|\.spec\."
    r"|/tests/"
    r"|/test/",
    re.IGNORECASE,
)
TICKET_NUMBER_RE = re.compile(r"#\d+")
# A bare ticket number reads as reconcile only alongside one of these — a
# ticket mentioned next to design/plan words, with nothing else, is a
# reference for a doc still to be written, not evidence anything shipped.
RECONCILE_ACCOMPANY_RE = re.compile(
    r"\b(?:shipped|landed|merged|pr|pull request|commit|branch)\b", re.IGNORECASE
)


def read_text_tolerant(path: str) -> str:
    """Read a text file as UTF-8, tolerating a BOM and CRLF line endings.

    ``utf-8-sig`` strips a leading BOM if present and is otherwise a
    plain UTF-8 decode; the default universal-newlines text mode
    (``newline=None``) normalises CRLF and CR to LF.
    """
    with open(path, "r", encoding="utf-8-sig", newline=None) as fh:
        return fh.read()


def unfenced(lines: List[str]) -> List[str]:
    """The same list with every line inside a ``` / ~~~ fenced block (and
    the fence lines themselves) replaced by "", so a heading scan skips
    illustrations while indices still line up with the original.
    """
    out: List[str] = []
    in_fence = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return out


def get_skill_dir() -> str:
    """Return the absolute path to skills/promise (the parent of scripts/)."""
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(scripts_dir)


def skill_version(skill_dir: str) -> Optional[str]:
    """The version in VERSION beside SKILL.md; None when the file is absent,
    unreadable, or does not hold one version like 1.30.0."""
    try:
        text = read_text_tolerant(os.path.join(skill_dir, VERSION_FILE)).strip()
    except (OSError, ValueError):
        return None
    return text if VERSION_RE.match(text) else None


def _version_tuple(value: str) -> Tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def check_min_skill_version(config: Optional[dict], version: Optional[str], skill_dir: str,
                            warnings: List[str]) -> None:
    """Warn when the running skill is older than the project's minSkillVersion,
    naming both versions and how to update."""
    if not isinstance(config, dict) or "minSkillVersion" not in config:
        return
    wanted = config["minSkillVersion"]
    if not isinstance(wanted, str) or not VERSION_RE.match(wanted.strip()):
        warnings.append(f"minSkillVersion is not a version like 1.30.0: {wanted!r}; ignored")
        return
    wanted = wanted.strip()
    if version is not None and _version_tuple(version) >= _version_tuple(wanted):
        return
    this_copy = f"this copy is {version}" if version else "this copy has no VERSION file, so its version is unknown"
    warnings.append(f"this project expects promise >= {wanted} (minSkillVersion); {this_copy} ({skill_dir}). "
                    "Update the promise plugin, or remove this old copy's folder (or link) and run "
                    "scripts/install_skill.py from a current checkout of the promise repository, which will "
                    "not replace a copy already there, before following this skill's rules here")


def _path_escapes(value: str) -> bool:
    """True when a configured project-relative path is absolute or climbs
    out of the project with a ".." segment.

    Both slash styles are checked, and a Windows drive letter (``C:\\x``,
    ``C:/x``, the drive-relative ``D:docs``) counts as absolute on every
    OS -- ``os.path.isabs`` alone would pass it on POSIX -- so a config
    written on one OS is judged the same way on another. adopt.py applies
    this same rule to ``--docs-home``.
    """
    if os.path.isabs(value) or value.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", value):
        return True
    return ".." in re.split(r"[\\/]+", value)


def _path_unsafe(value: str) -> bool:
    """True when a configured path holds anything but letters, digits,
    spaces and ``. _ - /`` (a backslash counts as a slash), or starts with
    ``-``: a mode types these paths into shell lines, where ``$(…)``, a
    backtick, ``;`` or a leading ``-`` would read as something else.
    adopt.py applies this same rule to ``--docs-home``."""
    value = value.replace("\\", "/")
    return not PATH_SAFE_RE.fullmatch(value) or value.startswith("-")


def _branch_unsafe(value: str) -> bool:
    """True when a branch pattern, with ``{slug}`` filled, holds anything
    but ASCII letters, digits and ``. _ - /``, or a name git refuses: a
    ``..``, a leading ``-``, an empty segment (``//``, a leading or trailing
    ``/``), or a segment that starts with ``.`` or ends with ``.lock``."""
    body = value.replace(BRANCH_SLUG, "slug")
    if not BRANCH_SAFE_RE.fullmatch(body) or ".." in body or body.startswith("-") or body.endswith("."):
        return True
    return any(not seg or seg.startswith(".") or seg.endswith(".lock") for seg in body.split("/"))


def _normalise_slashes(value: str, key: str, warnings: List[str]) -> str:
    """Turn a backslash-separated config path into the forward-slash form
    the contract asks for, with a warning naming the key."""
    if "\\" in value:
        warnings.append(f"{key} uses backslashes; normalised to forward slashes: {value!r}")
        return value.replace("\\", "/")
    return value


def load_config(cwd: str) -> Tuple[Optional[dict], Optional[str], List[str]]:
    """Load .claude/promise.config.json, falling back to promise.config.json.

    Returns (raw_config_or_None, path_or_None, warnings). Unknown
    top-level keys warn; "$comment" is always ignored, at the top level
    and wherever else it appears. "version" is the config's version key;
    a top-level "$schema" is accepted with a deprecation warning.
    """
    warnings: List[str] = []
    candidates = [
        os.path.join(cwd, ".claude", "promise.config.json"),
        os.path.join(cwd, "promise.config.json"),
    ]
    for candidate in candidates:
        if not os.path.isfile(candidate):
            continue
        try:
            raw = json.loads(read_text_tolerant(candidate))
        except (OSError, ValueError) as exc:
            warnings.append(
                f"could not read or parse config at {candidate}: {exc}; using detection"
            )
            return None, candidate, warnings
        if not isinstance(raw, dict):
            warnings.append(
                f"config at {candidate} is not a JSON object; using detection"
            )
            return None, candidate, warnings
        unknown = sorted(k for k in raw.keys() if k not in KNOWN_CONFIG_KEYS)
        for key in unknown:
            warnings.append(f"unknown config key: {key}")
        if "$schema" in raw:
            warnings.append(
                '"$schema" is deprecated; replace it with "version": 1'
            )
        if "version" in raw and raw["version"] != CONFIG_VERSION:
            warnings.append(
                f"unsupported config version: {raw['version']!r}; this skill reads version {CONFIG_VERSION}"
            )
        return raw, candidate, warnings
    warnings.append("no config found at .claude/promise.config.json; using detection")
    return None, None, warnings


def detect_docs_home(cwd: str) -> Optional[str]:
    """Return the first existing candidate docs-home directory, or None."""
    for rel in DOCS_HOME_CANDIDATES:
        if os.path.isdir(os.path.join(cwd, rel)):
            return rel
    return None


def detect_plans_folder(cwd: str) -> Optional[str]:
    """Return "plans" if that directory exists under cwd, else None."""
    return "plans" if os.path.isdir(os.path.join(cwd, "plans")) else None


def _package_manager_prefix(cwd: str) -> str:
    if os.path.isfile(os.path.join(cwd, "pnpm-lock.yaml")):
        return "pnpm"
    if os.path.isfile(os.path.join(cwd, "yarn.lock")):
        return "yarn"
    # bun.lockb is the binary lockfile; bun.lock the text one Bun 1.2+ writes.
    if os.path.isfile(os.path.join(cwd, "bun.lockb")) or os.path.isfile(os.path.join(cwd, "bun.lock")):
        return "bun"
    return "npm run"


def _detect_commands_from_package_json(cwd: str) -> Optional[Dict[str, Optional[str]]]:
    path = os.path.join(cwd, "package.json")
    if not os.path.isfile(path):
        return None
    try:
        raw = json.loads(read_text_tolerant(path))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    scripts = raw.get("scripts")
    if not isinstance(scripts, dict):
        return None
    prefix = _package_manager_prefix(cwd)
    type_check_name = next((n for n in TYPE_CHECK_SCRIPT_NAMES if n in scripts), None)
    result: Dict[str, Optional[str]] = {
        "typeCheck": f"{prefix} {type_check_name}" if type_check_name else None,
        "test": f"{prefix} test" if "test" in scripts else None,
        "lint": f"{prefix} lint" if "lint" in scripts else None,
    }
    return result if any(result.values()) else None


def _parse_target_names(text: str) -> List[str]:
    """Return target/recipe names defined at column 0 of a line.

    Matches Makefile targets (``name:``) and simple justfile recipes
    (``name:``), while a leading tab (a Makefile recipe body) or a
    ``:=`` variable assignment never matches.
    """
    names = []
    for line in text.splitlines():
        m = TARGET_NAME_RE.match(line)
        if m:
            names.append(m.group(1))
    return names


def _detect_commands_from_makefile(cwd: str) -> Optional[Dict[str, Optional[str]]]:
    path = os.path.join(cwd, "Makefile")
    if not os.path.isfile(path):
        return None
    try:
        targets = set(_parse_target_names(read_text_tolerant(path)))
    except (OSError, ValueError):
        return None
    type_check_name = next((n for n in TYPE_CHECK_SCRIPT_NAMES if n in targets), None)
    result = {
        "typeCheck": f"make {type_check_name}" if type_check_name else None,
        "test": "make test" if "test" in targets else None,
        "lint": "make lint" if "lint" in targets else None,
    }
    return result if any(result.values()) else None


def _detect_commands_from_justfile(cwd: str) -> Optional[Dict[str, Optional[str]]]:
    path = None
    for name in ("justfile", "Justfile"):
        candidate = os.path.join(cwd, name)
        if os.path.isfile(candidate):
            path = candidate
            break
    if path is None:
        return None
    try:
        recipes = set(_parse_target_names(read_text_tolerant(path)))
    except (OSError, ValueError):
        return None
    type_check_name = next((n for n in TYPE_CHECK_SCRIPT_NAMES if n in recipes), None)
    result = {
        "typeCheck": f"just {type_check_name}" if type_check_name else None,
        "test": "just test" if "test" in recipes else None,
        "lint": "just lint" if "lint" in recipes else None,
    }
    return result if any(result.values()) else None


def detect_commands(cwd: str) -> Dict[str, Optional[str]]:
    """Detect typeCheck/test/lint commands: package.json, else Makefile, else justfile.

    The first source that yields at least one command wins outright
    (architecture.md §5's "else" chain is a whole-strategy fallback,
    not a per-field merge across sources).
    """
    for detector in (
        _detect_commands_from_package_json,
        _detect_commands_from_makefile,
        _detect_commands_from_justfile,
    ):
        found = detector(cwd)
        if found:
            found = dict(found)
            found["source"] = "detected"
            return found
    return {"typeCheck": None, "test": None, "lint": None, "source": "none"}


def resolve_commands(
    cwd: str, config: Optional[dict], warnings: List[str]
) -> Dict[str, Optional[str]]:
    """Config wins outright when it declares a commands object; else detect.

    A "commands" key present but not an object warns and is treated as
    absent, falling through to detection. An unknown key inside a valid
    commands object warns without changing what is returned.
    """
    if isinstance(config, dict) and "commands" in config and config["commands"] is not None:
        raw = config["commands"]
        if isinstance(raw, dict):
            unknown = sorted(k for k in raw.keys() if k not in KNOWN_COMMANDS_KEYS)
            for key in unknown:
                warnings.append(f"unknown commands key: {key}")
            detected = detect_commands(cwd)
            for key in ("typeCheck", "test", "lint"):
                if raw.get(key) is None and detected.get(key):
                    warnings.append(f"commands.{key} is null in the config but {detected[key]!r} is detected; "
                                    "set it there to use it")
            return {
                "typeCheck": raw.get("typeCheck"),
                "test": raw.get("test"),
                "lint": raw.get("lint"),
                "source": "config",
            }
        warnings.append("commands is not an object; using detection")
    return detect_commands(cwd)


def resolve_docs_home(
    cwd: str, config: Optional[dict], warnings: List[str]
) -> Tuple[Optional[str], str]:
    """Config's docsHome wins when it is a string that stays inside the
    project; else fall through to detection.

    A wrong type or an escaping path warns and is treated as absent, so
    resolution still falls through to detection rather than trusting a
    value nobody meant to configure. A configured folder that does not
    exist yet is warned about and still returned: the config is the
    project's choice, and the mode that writes there creates it only on
    the user's say-so (render_outcome.py --create-docs-home). A loaded
    config that pins no docsHome, in a project where detection finds no
    docs folder either, is warned about too: every later ``new`` would
    ask where docs live until someone sets it.
    """
    if isinstance(config, dict) and "docsHome" in config and config["docsHome"] is not None:
        value = config["docsHome"]
        if not isinstance(value, str):
            warnings.append("docsHome is not a string; using detection")
        elif _path_escapes(value):
            warnings.append("path escapes the project: docsHome")
        elif value and _path_unsafe(value):
            warnings.append(f"docsHome holds characters other than {PATH_SAFE_WORDS}, or starts with '-': "
                            f"{value!r}; using detection")
        elif value:
            value = _normalise_slashes(value, "docsHome", warnings)
            if not os.path.isdir(os.path.join(cwd, value)):
                warnings.append(f"docsHome does not exist: {value}")
            return value, "config"
    detected = detect_docs_home(cwd)
    if detected is not None:
        return detected, "detected"
    if isinstance(config, dict):
        warnings.append(
            "docsHome is null: no docs folder detected; set docsHome in the config "
            "or run /promise adopt --docs-home <dir>"
        )
    return None, "none"


def resolve_plans_folder(
    cwd: str, config: Optional[dict], warnings: List[str]
) -> Optional[str]:
    """Config's plansFolder wins when it is a string that stays inside the
    project; else fall through to detection, on the same terms as docsHome."""
    if isinstance(config, dict) and "plansFolder" in config and config["plansFolder"] is not None:
        value = config["plansFolder"]
        if not isinstance(value, str):
            warnings.append("plansFolder is not a string; using detection")
        elif _path_escapes(value):
            warnings.append("path escapes the project: plansFolder")
        elif value:
            return _normalise_slashes(value, "plansFolder", warnings)
    return detect_plans_folder(cwd)


def resolve_branch(config: Optional[dict], warnings: List[str]) -> Tuple[str, str]:
    """The branch ``arm`` works on, and where it came from.

    A configured ``branch`` is either the literal ``current`` (stay on the
    branch the session is on, for a host that allows one branch per
    session) or a pattern holding ``{slug}`` and no whitespace, made of
    ASCII letters, digits and ``. _ - /`` around it, and naming a branch
    git accepts (no ``..``, no leading ``-``, no ``.lock`` ending):
    ``arm`` creates the branch through a shell, so nothing in the pattern
    may read as shell syntax. A wrong type or a pattern that breaks a rule
    warns and yields the default, ``feat/{slug}``; so does an absent or null
    key, silently.
    """
    if not isinstance(config, dict) or config.get("branch") is None:
        return DEFAULT_BRANCH, "default"
    value = config["branch"]
    if not isinstance(value, str):
        warnings.append(f"branch is not a string; using {DEFAULT_BRANCH}")
        return DEFAULT_BRANCH, "default"
    if value == BRANCH_CURRENT:
        return value, "config"
    if BRANCH_SLUG not in value or re.search(r"\s", value):
        warnings.append(
            f"branch must be {BRANCH_CURRENT!r} or a pattern with {BRANCH_SLUG} and no whitespace: "
            f"{value!r}; using {DEFAULT_BRANCH}"
        )
        return DEFAULT_BRANCH, "default"
    if _branch_unsafe(value):
        warnings.append(
            f"branch holds what a branch name must not: {value!r}; use letters, digits and . _ - / "
            f"around {BRANCH_SLUG}, with no '..', no leading '-' and no '.lock' ending; using {DEFAULT_BRANCH}"
        )
        return DEFAULT_BRANCH, "default"
    return value, "config"


def _read_json_object(path: str) -> Optional[dict]:
    """A JSON file's top-level object, or None when it cannot be read or is not one."""
    try:
        raw = json.loads(read_text_tolerant(path))
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def _runners_in_package_json(raw: dict) -> List[str]:
    """The runners a package.json names: a vitest, jest or @playwright/test
    dependency or devDependency, and a script that runs ``node --test``."""
    deps: Dict[str, Any] = {}
    for key in ("dependencies", "devDependencies"):
        if isinstance(raw.get(key), dict):
            deps.update(raw[key])
    found = [runner for runner, package in TEST_RUNNER_PACKAGES if package in deps]
    scripts = raw.get("scripts")
    if isinstance(scripts, dict) and any(
        isinstance(v, str) and NODE_TEST_SCRIPT_RE.search(v) for v in scripts.values()
    ):
        found.append("node:test")
    return found


def detect_test_runners(cwd: str) -> List[Dict[str, str]]:
    """Every test runner the project's own files name, and how to make each
    write JUnit XML (the run ``map_report.py`` joins to the map).

    Reads, never runs: ``package.json`` at the root and in folders up to
    ``RUNNER_SCAN_DEPTH`` below it (a workspace's packages), skipping
    ``node_modules`` and dot-folders, for vitest, jest and
    @playwright/test dependencies and ``node --test`` scripts; and
    ``pyproject.toml``, ``pytest.ini``, ``setup.cfg`` or ``tox.ini`` in the
    same folders when the file mentions pytest; and, when no pytest config is
    found, a ``test*.py`` file that imports ``unittest`` (the first folder
    holding one), whose JUnit route is ``scripts/junit_unittest.py``. One entry per runner per
    file, sorted by runner then file; a file that cannot be read is skipped.
    """
    found = set()
    for root, dirs, files in os.walk(cwd):
        rel = os.path.relpath(root, cwd)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth >= RUNNER_SCAN_DEPTH:
            dirs[:] = []
        else:
            dirs[:] = sorted(d for d in dirs if d != "node_modules" and not d.startswith("."))
        prefix = "" if rel == "." else rel.replace(os.sep, "/") + "/"
        if "package.json" in files:
            raw = _read_json_object(os.path.join(root, "package.json"))
            for runner in _runners_in_package_json(raw) if raw is not None else []:
                found.add((runner, prefix + "package.json"))
        for name in PYTEST_CONFIG_FILES:
            if name not in files:
                continue
            try:
                text = read_text_tolerant(os.path.join(root, name))
            except (OSError, ValueError):
                continue
            if "pytest" in text:
                found.add(("pytest", prefix + name))
        if not any(r == "unittest" for r, _ in found):
            for name in sorted(files):
                if not (name.startswith("test") and name.endswith(".py")):
                    continue
                try:
                    text = read_text_tolerant(os.path.join(root, name))
                except (OSError, ValueError):
                    continue
                if UNITTEST_IMPORT_RE.search(text):
                    found.add(("unittest", prefix or "./"))
                    break
    if any(r == "pytest" for r, _ in found):
        # pytest runs unittest suites too, and writes JUnit itself: one runner is enough.
        found = {(r, w) for r, w in found if r != "unittest"}
    return [
        {"runner": runner, "where": where, "junit": JUNIT_HOW[runner]}
        for runner, where in sorted(found)
    ]


def resolve_framework_path(
    cwd: str, config: Optional[dict], skill_dir: str, warnings: List[str]
) -> Tuple[str, str]:
    """The project's own framework copy wins when config names one, the
    path stays inside the project, and the file exists there; else the
    bundled copy. Each way a configured path is rejected — wrong type, an
    escaping path, a file that is not there — warns and falls back to the
    bundled copy rather than raising.
    """
    bundled = (os.path.join(skill_dir, "outcome-framework.md"), "bundled")
    if isinstance(config, dict) and "frameworkPath" in config and config["frameworkPath"] is not None:
        candidate = config["frameworkPath"]
        if not isinstance(candidate, str):
            warnings.append("frameworkPath is not a string; using the bundled framework")
            return bundled
        if _path_escapes(candidate):
            warnings.append("path escapes the project: frameworkPath")
            return bundled
        if candidate:
            candidate = _normalise_slashes(candidate, "frameworkPath", warnings)
            abs_candidate = os.path.join(cwd, candidate)
            if os.path.isfile(abs_candidate):
                return os.path.abspath(abs_candidate), "project"
            warnings.append(
                f"frameworkPath does not exist: {candidate}; using the bundled framework"
            )
    return bundled


def resolve_map(
    config: Optional[dict], warnings: List[str], cwd: Optional[str] = None
) -> Tuple[Union[dict, bool, None], bool]:
    """Normalise config["map"]: unknown keys warn, "lanes" is checked for
    being an object of strings, "rowIdPattern" is checked for compiling,
    "checks" for being an array of strings, "issueTracker" for its three
    string fields, "surfaces" for being a command string or a non-empty
    argv array, "requireHomes" for being a boolean, and the return says
    whether the map is usable.

    ``"map": false`` says the project keeps no map, on purpose: it is
    returned as ``False``, with no warning, and no mode offers the starter
    map. ``null`` and absent mean no map yet.

    Any other "map" that is not an object warns and is treated as absent —
    there is no detection fallback for a map the way there is for
    docsHome or commands, so the value is simply null. A map that is an
    object keeps that object verbatim either way: a project can configure
    part of a map and still see what it wrote. "mapUsable" is true only
    when recipe, find, row and lanes are all present with the right
    shape; false when the map is absent or any of those four is missing
    or the wrong type, alongside a warning naming what is missing.

    When ``cwd`` is given, "recipe" and "index" are also checked on disk:
    a path that escapes the project or does not exist is warned about.
    Neither changes mapUsable — that stays a shape check, so the map a
    project configured is the map every script sees — and the map object
    is returned verbatim, backslashes included.
    """
    if not isinstance(config, dict) or "map" not in config or config["map"] is None:
        return None, False

    raw_map = config["map"]
    if raw_map is False:
        return False, False
    if not isinstance(raw_map, dict):
        warnings.append("map is not an object; treating as absent")
        return None, False

    unknown = sorted(k for k in raw_map.keys() if k not in KNOWN_MAP_KEYS)
    for key in unknown:
        warnings.append(f"unknown map key: {key}")

    lanes = raw_map.get("lanes")
    lanes_ok = isinstance(lanes, dict) and all(isinstance(v, str) for v in lanes.values())
    if "lanes" in raw_map and not lanes_ok:
        warnings.append("map.lanes is not an object of strings")

    missing = [key for key in MAP_STRING_KEYS if not isinstance(raw_map.get(key), str)]
    if not lanes_ok:
        missing.append("lanes")

    usable = not missing
    if not usable:
        warnings.append(f"map incomplete: missing {', '.join(missing)}")

    row_id_pattern = raw_map.get("rowIdPattern")
    if isinstance(row_id_pattern, str):
        try:
            re.compile(row_id_pattern)
        except re.error as exc:
            warnings.append(f"map.rowIdPattern does not compile: {row_id_pattern!r}: {exc}")
        else:
            if takes_bare_tracker_ids(row_id_pattern):
                warnings.append("map.rowIdPattern takes row ids without the CAP- prefix (i1890a, 1.25's form), "
                                "so words such as GPT-4o read as rows: use "
                                "^CAP-(\\d+|[ip]\\d+[a-z]{1,2}|[A-Z][A-Z0-9]+-\\d+[a-z]{1,2})$ (references/config.md)")

    checks = raw_map.get("checks")
    if "checks" in raw_map and not (
        isinstance(checks, list) and all(isinstance(c, str) for c in checks)
    ):
        warnings.append("map.checks is not an array of strings")

    for key in MAP_OPTIONAL_COMMANDS:
        if key in raw_map and raw_map[key] is not None and not (isinstance(raw_map[key], str) and raw_map[key].strip()):
            warnings.append(f"map.{key} is not a command string")

    map_file = raw_map.get("file")
    if map_file is not None and not isinstance(map_file, str):
        warnings.append("map.file is not a string")

    junit = raw_map.get("junit")
    if junit is not None:
        entries = [junit] if isinstance(junit, str) else junit
        if not (isinstance(entries, list) and all(isinstance(e, str) and e for e in entries)):
            warnings.append("map.junit is not a path or an array of paths")
        else:
            for entry in entries:
                if _path_escapes(entry):
                    warnings.append(f"path escapes the project: map.junit ({entry})")
                elif _path_unsafe(entry):
                    warnings.append(f"map.junit holds characters other than {PATH_SAFE_WORDS}, or starts "
                                    f"with '-': {entry!r}; check.py leaves it out")
                elif "\\" in entry:
                    warnings.append(f"map.junit uses backslashes; use forward slashes: {entry!r}")

    surfaces = raw_map.get("surfaces")
    if surfaces is not None and not (
        (isinstance(surfaces, str) and surfaces.strip())
        or (isinstance(surfaces, list) and surfaces
            and all(isinstance(part, str) and part for part in surfaces))
    ):
        warnings.append("map.surfaces is not a command string or a non-empty array of strings")

    require_homes = raw_map.get("requireHomes")
    if require_homes is not None and not isinstance(require_homes, bool):
        warnings.append("map.requireHomes is not true or false")

    tracker = raw_map.get("issueTracker")
    if "issueTracker" in raw_map and not (
        isinstance(tracker, dict)
        and all(isinstance(tracker.get(k), str) for k in ISSUE_TRACKER_KEYS)
    ):
        warnings.append(
            "map.issueTracker is not an object with string kind, repo, template"
        )

    if cwd is not None:
        for key in MAP_FILE_KEYS:
            rel = raw_map.get(key)
            if not isinstance(rel, str) or not rel:
                continue
            if _path_escapes(rel):
                warnings.append(f"path escapes the project: map.{key}")
                continue
            if "\\" in rel:
                warnings.append(f"map.{key} uses backslashes; use forward slashes: {rel!r}")
                rel = rel.replace("\\", "/")
            if not os.path.isfile(os.path.join(cwd, rel)):
                warnings.append(f"map.{key} does not exist: {rel}")

    return raw_map, usable


def map_spelling_warnings(cwd: str, map_value: Any, warnings: List[str]) -> None:
    """Warn when a mode must not write the ``feature`` spelling into this map:
    the map file uses the alias ``areas`` or ``area``, or the project's own
    reader (the script ``map.find`` runs) reads the alias (``--areas``, or the
    ``areas``/``area`` keys) and has no ``--features``. A mode writes the spelling the map already uses, and
    ``feature`` only in a new map. The map file is found as check.py finds it
    (``map.file``, else ``map.json`` beside the starter reader), and the reader
    check is upgrade.py's own."""
    if not isinstance(map_value, dict):
        return
    try:
        import check  # noqa: PLC0415  (sibling scripts; imported here, since both import orient)
        import upgrade  # noqa: PLC0415
    except ImportError:  # pragma: no cover
        return
    map_file, _how = check.map_file(map_value)
    path = os.path.join(cwd, map_file) if map_file else None
    data = None
    if path and os.path.isfile(path):
        try:
            data = json.loads(read_text_tolerant(path))
        except (OSError, ValueError):
            data = None
    if isinstance(data, dict):
        rows = data.get("rows") if isinstance(data.get("rows"), list) else []
        if "areas" in data or any(isinstance(r, dict) and "area" in r for r in rows):
            warnings.append(f"map {map_file} uses the alias spelling areas/area: write the spelling the map "
                            "already uses (area on a row) in every row a mode adds, never feature beside it")
    reader = upgrade._reader_path(cwd, map_value.get("find"))
    found = upgrade._reader_features(read_text_tolerant(reader)) if reader else set()
    # Only a reader that knows the alias and not the new name: a project's own reader
    # that never grouped rows by feature has nothing to warn about.
    knows_alias = bool({"flag --areas", "map key 'areas'", "map key 'area'"} & found)
    if reader and knows_alias and "flag --features" not in found:
        rel = os.path.relpath(reader, cwd).replace(os.sep, "/")
        warnings.append(f"the map reader {rel} has no --features, so it reads only areas/area: write the spelling "
                        "the map already uses, and run /promise upgrade to see what the reader lacks")


def resolve_sibling(
    config: Optional[dict], map_value: Union[dict, bool, None], warnings: List[str], cwd: str
) -> Optional[Dict[str, Any]]:
    """Read config["sibling"]: the sibling repository whose map holds this
    project's rows, read-only. It counts only beside ``"map": false`` -- a row
    has one home, so a project with its own map has no sibling map.

    Returns ``{repo, path, find, row, dir, checkout}`` when all four keys are
    non-empty strings and ``map`` is false; ``dir`` is ``path`` resolved from
    the project root (it may climb out with ``..``: it names another
    checkout), and ``checkout`` says whether a folder is there. A missing
    checkout warns; the sibling still counts, so a mode can say under
    **Not checked** that its rows could not be read. Anything else warns
    and returns None.
    """
    if not isinstance(config, dict) or config.get("sibling") is None:
        return None
    raw = config["sibling"]
    if map_value is not False:
        warnings.append('sibling is read only beside "map": false; ignored')
        return None
    if not isinstance(raw, dict):
        warnings.append("sibling is not an object; ignored")
        return None
    for key in sorted(k for k in raw.keys() if k not in SIBLING_KEYS and k != "$comment"):
        warnings.append(f"unknown sibling key: {key}")
    missing = [k for k in SIBLING_KEYS if not (isinstance(raw.get(k), str) and raw[k].strip())]
    if missing:
        warnings.append(f"sibling incomplete: missing {', '.join(missing)}; ignored")
        return None
    path = _normalise_slashes(raw["path"], "sibling.path", warnings)
    folder = os.path.normpath(os.path.join(cwd, path))
    checkout = os.path.isdir(folder)
    if not checkout:
        warnings.append(f"sibling.path has no checkout: {path} (the rows of {raw['repo']} cannot be read here)")
    return {"repo": raw["repo"], "path": path, "find": raw["find"], "row": raw["row"],
            "dir": folder, "checkout": checkout}


def _has_marker(path: str) -> bool:
    try:
        return os.path.isfile(path) and PROMISE_BEGIN_MARKER in read_text_tolerant(path)
    except (OSError, ValueError):
        return False


def imports_agents_md(claude_md: str, cwd: str) -> bool:
    """True when this CLAUDE.md imports the project's root AGENTS.md on a
    line of its own (``@AGENTS.md``; ``@../AGENTS.md`` from .claude/)."""
    try:
        text = read_text_tolerant(claude_md)
    except (OSError, ValueError):
        return False
    target = os.path.normcase(os.path.abspath(os.path.join(cwd, "AGENTS.md")))
    base = os.path.dirname(os.path.abspath(claude_md))
    for m in IMPORT_LINE_RE.finditer(text):
        ref = os.path.expanduser(m.group(1))
        if os.path.normcase(os.path.abspath(os.path.join(base, ref))) == target:
            return True
    return False


SECTION_STAMP_RE = re.compile(r"\btemplate:([0-9a-f]{8})\b")
SECTION_TEMPLATE = os.path.join("templates", "claude-md-section.md")


def template_stamp(skill_dir: str) -> Optional[str]:
    """Eight hex characters of the section template's hash: ``adopt.py`` writes it
    into the begin marker, so a section written from an older template shows."""
    try:
        text = read_text_tolerant(os.path.join(skill_dir, SECTION_TEMPLATE))
    except (OSError, ValueError):
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]


def section_current(section_path: str, skill_dir: str) -> Optional[bool]:
    """Whether the promise section was written from this skill's template: its begin
    marker carries the template's stamp. None when there is nothing to compare."""
    stamp = template_stamp(skill_dir)
    if not stamp:
        return None
    try:
        lines = read_text_tolerant(section_path).splitlines()
    except (OSError, ValueError):
        return None
    begin = next((l for l in lines if l.lstrip().startswith(PROMISE_BEGIN_MARKER)), None)
    if begin is None:
        return None
    m = SECTION_STAMP_RE.search(begin)
    return bool(m) and m.group(1) == stamp


def detect_claude_md(cwd: str) -> Dict[str, Any]:
    """CLAUDE.md at the project root, else .claude/CLAUDE.md, else absent;
    and ``sectionPath``, the file that holds the promise section. That is
    the CLAUDE.md itself, or the root AGENTS.md when the CLAUDE.md imports
    it (``@AGENTS.md``) or there is no CLAUDE.md: Claude Code reads the
    import, and reads AGENTS.md itself when no CLAUDE.md exists."""
    agents = os.path.abspath(os.path.join(cwd, "AGENTS.md"))
    for candidate in (
        os.path.join(cwd, "CLAUDE.md"),
        os.path.join(cwd, ".claude", "CLAUDE.md"),
    ):
        if os.path.isfile(candidate):
            path = os.path.abspath(candidate)
            if _has_marker(path):
                section: Optional[str] = path
            elif imports_agents_md(path, cwd) and _has_marker(agents):
                section = agents
            else:
                section = None
            return {"path": path, "hasPromiseSection": section is not None, "sectionPath": section}
    if _has_marker(agents):
        return {"path": None, "hasPromiseSection": True, "sectionPath": agents}
    return {"path": None, "hasPromiseSection": False, "sectionPath": None}


def markdown_files(
    cwd: str, docs_home: Optional[str], warnings: Optional[List[str]] = None
) -> List[Tuple[str, str]]:
    """Every *.md under docsHome, one level deep, as (path under docsHome,
    absolute path) — the files the outcome-doc scan reads. Empty when
    docsHome is null or not a folder; a subdirectory that cannot be listed
    is skipped, with a warning when a warnings list is given."""
    if not docs_home:
        return []
    docs_dir = os.path.join(cwd, docs_home)
    if not os.path.isdir(docs_dir):
        return []
    candidates: List[Tuple[str, str]] = []
    for name in sorted(os.listdir(docs_dir)):
        full = os.path.join(docs_dir, name)
        if os.path.isfile(full) and name.endswith(".md"):
            candidates.append((name, full))
        elif os.path.isdir(full):
            try:
                inner = sorted(os.listdir(full))
            except OSError as exc:
                if warnings is not None:
                    warnings.append(f"skipped unreadable folder {docs_home}/{name}: {exc}")
                continue
            for name2 in inner:
                full2 = os.path.join(full, name2)
                if os.path.isfile(full2) and name2.endswith(".md"):
                    candidates.append((f"{name}/{name2}", full2))
    return candidates


def foreign_docs_count(
    cwd: str, docs_home: Optional[str], existing_docs: List[Dict[str, Any]],
    framework_copy: Optional[str] = None,
) -> Optional[int]:
    """How many *.md files docsHome holds when none of them is an outcome
    doc (docsHomeForeignDocs): null when docsHome is null, 0 when the folder
    holds an outcome doc or no *.md file at all. A folder of design docs in
    another shape reads as a docs home to detection; this is how a caller
    tells that apart from a docs home of outcome docs. The project's own
    framework copy (``framework_copy``, an absolute path) is not a doc in
    another shape, and is not counted."""
    if not docs_home:
        return None
    if existing_docs:
        return 0
    skip = os.path.normcase(os.path.abspath(framework_copy)) if framework_copy else None
    return sum(1 for _rel, full in markdown_files(cwd, docs_home)
               if os.path.normcase(os.path.abspath(full)) != skip)


def foreign_docs_warning(docs_home: str, count: int) -> str:
    """The warning for a detected docsHome that holds no outcome doc;
    adopt.py prints the same text before it would pin that folder."""
    held = "its one doc is not" if count == 1 else f"none of its {count} docs is"
    return (
        f"docsHome {docs_home} was detected, but {held} an outcome doc; pin a new folder "
        "with adopt --docs-home (for example docs/promises)"
    )


# The statuses of a doc still in flight. An open doc with no policy line behaves as
# spec until a human's yes stamps it (decisions.py policy --open).
OPEN_STATUSES = ("draft", "agreed", "building")


def legacy_policy_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The open docs (from scan_existing_docs with keep_private) whose header has no
    ``Decision policy:`` line at all. A line with a value that is not one of the three
    is not counted: a person wrote it, and only a person changes it."""
    return [d for d in docs if d.get("status") in OPEN_STATUSES and d.get("_noPolicyLine")]


def scan_existing_docs(
    cwd: str, docs_home: Optional[str], warnings: Optional[List[str]] = None, keep_private: bool = False
) -> List[Dict[str, Any]]:
    """Every *.md under docsHome, one level deep -- the folder and its
    immediate subdirectories, the same scan lint_outcome.py and
    outcome_rows.py --search use -- whose §0 TLDR heading sits outside any
    fenced code block.

    Headings inside a ``` / ~~~ fence are illustrations, not structure,
    so a framework copy or a doc quoting the template is not listed as
    an outcome doc, and the title/status/date lookups skip fenced text
    too. A file that cannot be read or is not UTF-8 is skipped with a
    warning when a warnings list is given; a subdirectory that cannot be
    listed is skipped the same way. ``keep_private`` adds ``_noPolicyLine``
    to each entry, for legacy_policy_docs; it is never printed.
    """
    candidates = markdown_files(cwd, docs_home, warnings)
    results = []
    for name, full in candidates:
        try:
            text = read_text_tolerant(full)
        except (OSError, ValueError) as exc:
            if warnings is not None:
                warnings.append(f"skipped unreadable doc {docs_home}/{name}: {exc}")
            continue
        lines = unfenced(text.splitlines())
        if not any(line.startswith(TLDR_HEADING) for line in lines):
            continue
        title = None
        status = None
        last_decision = None
        policy = None
        header = True
        for line in lines:
            if line.startswith("## "):
                header = False
            if header and policy is None and line.startswith("Decision policy:"):
                policy = line[len("Decision policy:"):].strip()
            if title is None:
                m = H1_RE.match(line)
                if m:
                    title = m.group(1)
            if status is None:
                m = STATUS_RE.match(line)
                if m:
                    status = m.group(1)
            if last_decision is None:
                m = LAST_DECISION_RE.search(line)
                if m:
                    last_decision = m.group(1)
        results.append(
            {
                "path": "/".join([docs_home, name]),
                "title": title,
                "status": status,
                "lastDecision": last_decision,
                # The header's decision policy: None on a legacy doc, which behaves as spec.
                "decisionPolicy": DECISION_POLICY_ALIASES.get(policy, policy) if DECISION_POLICY_ALIASES.get(policy, policy) in DECISION_POLICIES else None,
            }
        )
        if keep_private:
            results[-1]["_noPolicyLine"] = policy is None
    return sorted(results, key=lambda d: d["path"])


def _first_word(text: str) -> str:
    """The input's first whitespace-delimited token, lower-cased and unpunctuated."""
    stripped = text.strip()
    if not stripped:
        return ""
    token = stripped.split(None, 1)[0]
    return token.strip(_MODE_WORD_PUNCT).lower()


def _doc_basename_stem(doc: Dict[str, Any]) -> str:
    """A doc's path basename with a trailing .md removed, for substring matching."""
    path = doc.get("path") or ""
    name = os.path.basename(path)
    if name.lower().endswith(".md"):
        name = name[: -len(".md")]
    return name


def _matching_docs(text_lower: str, existing_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """existingDocs whose path basename (sans .md) or title is a substring of the input."""
    matches = []
    for doc in existing_docs:
        basename = _doc_basename_stem(doc).lower()
        title = (doc.get("title") or "").lower()
        if (basename and basename in text_lower) or (title and title in text_lower):
            matches.append(doc)
    return matches


def _doc_label(doc: Dict[str, Any]) -> str:
    """The name to show for a doc in a signal: its title, else its basename."""
    return doc.get("title") or _doc_basename_stem(doc)


def _near(text_lower: str, re_a: re.Pattern[str], re_b: re.Pattern[str], window_chars: int = 30) -> bool:
    """True when some re_a match and some re_b match sit within window_chars of each other."""
    a_spans = [m.span() for m in re_a.finditer(text_lower)]
    if not a_spans:
        return False
    b_spans = [m.span() for m in re_b.finditer(text_lower)]
    if not b_spans:
        return False
    for a_start, a_end in a_spans:
        for b_start, b_end in b_spans:
            gap = max(a_start, b_start) - min(a_end, b_end)
            if gap <= window_chars:
                return True
    return False


# A row id without the CAP- prefix, as 1.25 wrote them (i1890a, ENG-421a); words such as
# GPT-4o, mid-90s and i3wm have the same shape, so a pattern that takes it reads them as rows.
BARE_TRACKER_SHAPE_RE = re.compile(r"(?:[ip]\d+|[A-Za-z][A-Za-z0-9]*-\d+)[a-z]{1,2}", re.IGNORECASE)


def takes_bare_tracker_ids(pattern: str) -> bool:
    """True for 1.25's ``rowIdPattern``, which took the counter (CAP-12) and an issue's id
    with no CAP- prefix (i12a). A project's own scheme (WEB-12a) is not this."""
    try:
        return bool(re.fullmatch(pattern, "CAP-12") and re.fullmatch(pattern, "i12a"))
    except re.error:
        return False


def suggest_mode(
    input_text: str,
    existing_docs: List[Dict[str, Any]],
    map_value: Optional[dict],
) -> Tuple[Optional[str], List[str], List[str], bool]:
    """A mode hint for the --input text (architecture.md §4's dispatch table).

    A recognised first word wins outright and skips every check below it —
    there is nothing left to be ambiguous with. Otherwise each remaining
    rule is checked, in the table's own priority order, against the same
    input, and the highest-priority match is the suggestion. Returns
    (suggestedMode, signals, extraWarnings, ambiguous) — extraWarnings
    folds into the caller's own warnings[] (currently only a bad
    map.rowIdPattern); ambiguous is true only when a lower-priority rule
    also matched with a different mode, in which case that rule's own
    signal is appended too, or when a phrase that only leans towards
    backfill is the only signal ("backfill", "retrofit" or "existing
    product" with no map word near it, or beside a test word and a change
    word; docs moved to another tool; or any backfill phrase beside a
    feature, design, plan or spec word): the suggestion is then ``new``,
    and the router asks. This never raises: an input that trips
    nothing falls through to the default, because this is a hint for the
    router, not a second router that could itself be "wrong".
    """
    text = input_text or ""
    text_lower = text.lower()
    extra_warnings: List[str] = []
    if not text.strip():
        return "onboard", ["no task supplied; offer the starting-point interview"], extra_warnings, False

    # A recognised first word wins outright and skips inference entirely.
    first = _first_word(text)
    if first == "review" and (ISSUE_PHRASE_RE.match(text.lstrip()) or PR_PHRASE_RE.search(text)):
        # "review these issues" and "review the PR description" ask for
        # GitHub text, not a doc review — unless a doc is named and nothing
        # pins the issue down ("review issues in the billing doc").
        kind = "issue" if ISSUE_PHRASE_RE.match(text.lstrip()) else "pr"
        signal = [f"first word 'review' starts {'an issue' if kind == 'issue' else 'a pull request text'} phrase"]
        named = _matching_docs(text_lower, existing_docs)
        if named and not GITHUB_STRONG_RE.search(text):
            return kind, signal + [f"matches existing doc {_doc_label(named[0])!r} + critique verb"], extra_warnings, True
        return kind, signal, extra_warnings, False
    if first in ("issue", "pr"):
        rest = text.strip().split(None, 1)[1] if len(text.split()) > 1 else ""
        if GITHUB_MODE_REST_RE.match(rest) and not GITHUB_MODE_VETO_RE.search(rest):
            return first, ["first word is a mode name"], extra_warnings, False
    elif first == "upgrade":
        # "upgrade the checkout page" is a product ask: the word leads to upgrade
        # only alone, or before promise, its pin, or a version.
        rest = text.strip().split(None, 1)[1] if len(text.split()) > 1 else ""
        if not rest or UPGRADE_REST_RE.match(rest):
            return first, ["first word is a mode name"], extra_warnings, False
    elif first == "doctor":
        rest = text_lower.split(None, 1)[1] if len(text_lower.split()) > 1 else ""
        if not rest or re.fullmatch(r"(?:promise|adoption|(?:(?:the|this|our) )?setup)", rest):
            return first, ["first word is a mode name"], extra_warnings, False
    elif first == "onboard":
        rest = text.strip().split(None, 1)[1] if len(text.split()) > 1 else ""
        if not rest or ONBOARD_REST_RE.match(rest):
            return "onboard", ["first word asks for Promise onboarding"], extra_warnings, False
    elif first in RECOGNISED_MODES:
        return first, ["first word is a mode name"], extra_warnings, False

    matches = _matching_docs(text_lower, existing_docs)
    candidates: List[Tuple[str, List[str]]] = []

    # GitHub text first: an issue or pull-request phrase writes no doc.
    github_start: Optional[int] = None
    m = PR_PHRASE_RE.search(text)
    if m:
        candidates.append(("pr", [f"matches a pull request text phrase: {m.group(0)!r}"]))
        github_start = m.start()
    m = ISSUE_PHRASE_RE.search(text)
    if m:
        candidates.append(("issue", [f"matches an issue phrase: {m.group(0)!r}"]))
        github_start = m.start() if github_start is None else min(github_start, m.start())
    feature = PRODUCT_FEATURE_RE.search(text[:github_start]) if github_start is not None else None
    if feature:
        candidates.insert(0, ("new", [f"{feature.group(0)!r} before the phrase asks for a product feature"]))
    onboarding = ONBOARD_PHRASE_RE.search(text)
    if onboarding:
        candidates.append(("onboard", [f"asks to get started with Promise: {onboarding.group(0)!r}"]))

    # Existing-doc match: at most one outcome from this block — each case
    # refines the same matches/status, not an independent signal.
    if matches and CRITIQUE_VERB_RE.search(text):
        label = _doc_label(matches[0])
        candidates.append(("review", [f"matches existing doc {label!r} + critique verb"]))
    elif len(matches) >= 2:
        candidates.append(("merge", [f"matches {len(matches)} distinct existing docs"]))
    elif len(matches) == 1:
        doc = matches[0]
        status = (doc.get("status") or "").lower()
        label = _doc_label(doc)
        if status == "agreed" and ARM_PHRASE_RE.search(text):
            candidates.append(("arm", [f"matches existing doc {label!r} (agreed) + arm phrase"]))
        else:
            candidates.append(("revise", [f"matches existing doc {label!r}"]))
    elif existing_docs and GENERIC_CHANGE_VERB_RE.search(text) and DOC_REFERENCE_WORD_RE.search(text):
        # A generic change verb aimed at "the doc"/"the outcome", no title
        # named: which doc is ambiguous, the mode is not — at least one
        # outcome doc exists, so this can only be a change to it.
        signal = ['generic change verb + "doc"']
        if len(existing_docs) > 1:
            signal.append("ambiguous: which doc")
        candidates.append(("revise", signal))

    # Reconcile: a commit sha, a feat/fix branch or a test-file path stand
    # alone. A bare ticket number needs an accompanying shipped/landed/PR
    # word; failing that, a shipped/landed phrase on its own still counts.
    m = RECONCILE_STRONG_PATTERN_RE.search(text)
    if m:
        candidates.append(
            ("reconcile", [f"matches a PR/commit/branch/test-file pattern: {m.group(0)!r}"])
        )
    else:
        ticket = TICKET_NUMBER_RE.search(text)
        if ticket and RECONCILE_ACCOMPANY_RE.search(text):
            candidates.append(
                (
                    "reconcile",
                    [f"matches a PR/commit/branch/test-file pattern: {ticket.group(0)!r}"],
                )
            )
        else:
            m = RECONCILE_PHRASE_RE.search(text)
            if m:
                candidates.append(
                    ("reconcile", [f"matches a shipped/landed phrase: {m.group(0)!r}"])
                )

    # Intake: the input names a row id shaped by the project's own map.
    if isinstance(map_value, dict) and map_value.get("rowIdPattern"):
        pattern_text = map_value["rowIdPattern"]
        try:
            row_id_re = re.compile(pattern_text, re.IGNORECASE)
        except re.error as exc:
            extra_warnings.append(f"bad map.rowIdPattern {pattern_text!r}: {exc}; skipping rule 7")
        else:
            bare = takes_bare_tracker_ids(pattern_text)
            for token in ROW_ID_TOKEN_RE.findall(text):
                candidate_token = token.strip(_MODE_WORD_PUNCT)
                if bare and BARE_TRACKER_SHAPE_RE.fullmatch(candidate_token or ""):
                    continue  # 1.25's pattern: GPT-4o and i3wm have this shape too
                if candidate_token and row_id_re.fullmatch(candidate_token):
                    candidates.append(
                        ("intake", [f"token {candidate_token!r} matches map.rowIdPattern"])
                    )
                    break

    # Intake: a list shape, or feedback vocabulary.
    list_item_count = sum(1 for line in text.splitlines() if LIST_ITEM_RE.match(line))
    if list_item_count >= 3:
        candidates.append(("intake", [f"{list_item_count} list items (>= 3)"]))
    else:
        m = INTAKE_WORD_RE.search(text)
        if m:
            candidates.append(("intake", [f"contains intake word {m.group(0)!r}"]))

    # Backfill: map what the product does today. It sits below reconcile
    # and intake, so a phrase either of them already claims ("we already
    # do this", a complaint) keeps its mode and only marks the input as
    # ambiguous when a backfill phrase is there too.
    backfill_hint: Optional[List[str]] = None
    backfill_signal: Optional[str] = None
    m = BACKFILL_PHRASE_RE.search(text)
    docs = DOCS_PHRASE_RE.search(text)
    dest = DOCS_DESTINATION_RE.match(text, docs.end()) if docs else None
    elsewhere = dest.group("dest").strip() if dest and not OUTCOME_SHAPE_RE.search(dest.group("dest")) else None
    every = next(
        (e for e in EVERY_TEST_RE.finditer(text) if e.group("home") or e.group("have")), None
    )
    weak = BACKFILL_WEAK_RE.search(text)
    change = CHANGE_WORD_RE.search(text)
    if m:
        backfill_signal = repr(m.group(0))
    elif docs and not elsewhere:
        backfill_signal = repr(docs.group(0))
    elif every:
        backfill_signal = repr(every.group(0))
    elif weak and _near(text_lower, BACKFILL_WEAK_RE, MAP_WORD_RE, MAP_WORD_WINDOW):
        backfill_signal = f"{weak.group(0)!r} + a map word"
    elif weak and not change and _near(text_lower, BACKFILL_WEAK_RE, TEST_WORD_RE, MAP_WORD_WINDOW):
        backfill_signal = f"{weak.group(0)!r} + the tests it has"
    elif docs:
        # docs moved to another tool: a hint that never wins
        backfill_hint = [f"backfill phrase {docs.group(0)!r}, but the docs go to {elsewhere!r}, not into outcome docs"]
    elif weak and change:
        backfill_hint = [f"backfill phrase {weak.group(0)!r}, but {change.group(0)!r} asks for a change"]
    elif weak:
        # alone, "backfill", "retrofit" or "existing product" is as likely a
        # data job or a feature: a hint that never wins, but makes the input
        # ambiguous
        backfill_hint = [f"backfill phrase {weak.group(0)!r} with no map word near it"]
    feature = FEATURE_WORD_RE.search(text) if backfill_signal else None
    if feature:
        backfill_hint = [
            f"backfill phrase {backfill_signal}, but {feature.group(0)!r} asks for a feature,"
            " design, plan or spec"
        ]
    elif backfill_signal:
        candidates.append(("backfill", [f"matches a backfill phrase: {backfill_signal}"]))

    # Review: a critique verb with no existing-doc match — pasted or
    # external content, not a request about a doc already on file. A bare
    # "feedback" is deliberately not one of these verbs (see
    # REVIEW_NO_DOC_VERB_RE): it has already had its chance to read as
    # intake above, and a plain mention leans there.
    if not matches:
        m = REVIEW_NO_DOC_VERB_RE.search(text)
        if m:
            candidates.append(
                ("review", [f"critique verb {m.group(0)!r}, no doc match (external content)"])
            )

    doctor_phrase = DOCTOR_PHRASE_RE.search(text)
    if doctor_phrase:
        candidates.append(("doctor", [f"matches a Doctor phrase: {doctor_phrase.group(0)!r}"]))

    m = UPGRADE_PHRASE_RE.search(text)
    if m:
        candidates.append(("upgrade", [f"matches an upgrade phrase: {m.group(0)!r}"]))

    # Adopt: the literal CLAUDE.md, an install/setup verb near "promise",
    # or an install/setup verb aimed at this project without the word
    # "promise" ever appearing.
    if "claude.md" in text_lower:
        candidates.append(("adopt", ["contains 'CLAUDE.md'"]))
    elif not doctor_phrase and _near(text_lower, ADOPT_TRIGGER_RE, PROMISE_WORD_RE):
        candidates.append(("adopt", ["adopt trigger word near 'promise'"]))
    elif not doctor_phrase and ADOPT_TRIGGER_RE.search(text_lower) and ADOPT_LOCAL_RE.search(text_lower):
        candidates.append(("adopt", ["adopt trigger word + local project reference"]))

    if not candidates:
        if backfill_hint:
            return "new", ["no stronger signal; default"] + backfill_hint, extra_warnings, True
        # A bare ticket number, alone, is not a signal for any mode above
        # — say it was seen rather than claiming nothing stood out at all.
        if TICKET_NUMBER_RE.search(text) and not RECONCILE_ACCOMPANY_RE.search(text):
            return "new", ["ticket reference"], extra_warnings, False
        return "new", ["no stronger signal; default"], extra_warnings, False
    if backfill_hint:
        candidates.append(("backfill", backfill_hint))

    winner_mode, winner_signals = candidates[0]
    signals = list(winner_signals)
    if winner_mode == "onboard":
        return winner_mode, signals, extra_warnings, False
    ambiguous = False
    github_weak = not GITHUB_STRONG_RE.search(text)
    for mode, sig in candidates[1:]:
        # issue and pr outrank every other mode. Only each other, a product
        # feature before the phrase, or a matching doc beside a weak phrase
        # make them ambiguous.
        if mode == winner_mode:
            continue
        if (winner_mode not in ("issue", "pr") or mode in ("issue", "pr", "new")
                or (github_weak and matches and mode in ("review", "revise", "merge", "arm"))):
            ambiguous = True
            signals.extend(sig)
    return winner_mode, signals, extra_warnings, ambiguous


def build_orientation(
    mode_arg: Optional[str], cwd_arg: Optional[str], input_arg: Optional[str] = None
) -> Dict[str, Any]:
    warnings: List[str] = []
    cwd = os.path.abspath(cwd_arg) if cwd_arg else os.path.abspath(os.getcwd())
    skill_dir = get_skill_dir()
    mode = _mode_word(mode_arg)
    version = skill_version(skill_dir)

    try:
        raw_config, config_path, config_warnings = load_config(cwd)
    except Exception as exc:  # pragma: no cover - defensive, never fail hard
        raw_config, config_path, config_warnings = None, None, [f"config detection failed: {exc}"]
    warnings.extend(config_warnings)
    try:
        check_min_skill_version(raw_config, version, skill_dir, warnings)
    except Exception as exc:  # pragma: no cover
        warnings.append(f"minSkillVersion check failed: {exc}")

    try:
        docs_home, docs_home_source = resolve_docs_home(cwd, raw_config, warnings)
    except Exception as exc:  # pragma: no cover
        docs_home, docs_home_source = None, "none"
        warnings.append(f"docsHome detection failed: {exc}")

    try:
        plans_folder = resolve_plans_folder(cwd, raw_config, warnings)
    except Exception as exc:  # pragma: no cover
        plans_folder = None
        warnings.append(f"plansFolder detection failed: {exc}")

    try:
        commands = resolve_commands(cwd, raw_config, warnings)
    except Exception as exc:  # pragma: no cover
        commands = {"typeCheck": None, "test": None, "lint": None, "source": "none"}
        warnings.append(f"commands detection failed: {exc}")

    try:
        framework_path, framework_source = resolve_framework_path(
            cwd, raw_config, skill_dir, warnings
        )
    except Exception as exc:  # pragma: no cover
        framework_path = os.path.join(skill_dir, "outcome-framework.md")
        framework_source = "bundled"
        warnings.append(f"frameworkPath resolution failed: {exc}")

    try:
        map_value, map_usable = resolve_map(raw_config, warnings, cwd)
    except Exception as exc:  # pragma: no cover
        map_value, map_usable = None, False
        warnings.append(f"map resolution failed: {exc}")

    try:
        map_spelling_warnings(cwd, map_value, warnings)
    except Exception as exc:  # pragma: no cover
        warnings.append(f"map spelling check failed: {exc}")

    try:
        sibling = resolve_sibling(raw_config, map_value, warnings, cwd)
    except Exception as exc:  # pragma: no cover
        sibling = None
        warnings.append(f"sibling resolution failed: {exc}")

    try:
        claude_md = detect_claude_md(cwd)
        if (claude_md["path"] and claude_md["sectionPath"] == claude_md["path"]
                and imports_agents_md(claude_md["path"], cwd) and _has_marker(os.path.join(cwd, "AGENTS.md"))):
            warnings.append("the promise section is in CLAUDE.md and in the AGENTS.md it imports, so Claude "
                            "reads it twice; keep it in AGENTS.md and let CLAUDE.md import it")
        claude_md["sectionCurrent"] = (section_current(claude_md["sectionPath"], skill_dir)
                                       if claude_md["sectionPath"] else None)
        if claude_md["sectionCurrent"] is False:
            warnings.append(f"the promise section in {os.path.relpath(claude_md['sectionPath'], cwd)} was written "
                            "from an older template; run /promise adopt (scripts/adopt.py) to refresh it")
    except Exception as exc:  # pragma: no cover
        claude_md = {"path": None, "hasPromiseSection": False, "sectionPath": None, "sectionCurrent": None}
        warnings.append(f"claudeMd detection failed: {exc}")

    try:
        scanned = scan_existing_docs(cwd, docs_home, warnings, keep_private=True)
        legacy_count = len(legacy_policy_docs(scanned))
        existing_docs = [{k: v for k, v in d.items() if not k.startswith("_")} for d in scanned]
    except Exception as exc:  # pragma: no cover
        existing_docs, legacy_count = [], 0
        warnings.append(f"existingDocs scan failed: {exc}")

    try:
        foreign_docs = foreign_docs_count(cwd, docs_home, existing_docs,
                                          framework_path if framework_source == "project" else None)
    except Exception as exc:  # pragma: no cover
        foreign_docs = None
        warnings.append(f"docsHome scan failed: {exc}")
    if foreign_docs and docs_home_source == "detected":
        warnings.append(foreign_docs_warning(docs_home, foreign_docs))

    run_command = None
    try:
        branch, branch_source = resolve_branch(raw_config, warnings)
        run_command = raw_config.get("run") if isinstance(raw_config, dict) else None
        if run_command is not None and not (isinstance(run_command, str) and run_command.strip()):
            warnings.append("run is not a command string; agents run the scripts by their path instead")
            run_command = None
    except Exception as exc:  # pragma: no cover
        branch, branch_source = DEFAULT_BRANCH, "default"
        warnings.append(f"branch resolution failed: {exc}")

    try:
        test_runners = detect_test_runners(cwd)
    except Exception as exc:  # pragma: no cover
        test_runners = []
        warnings.append(f"testRunners detection failed: {exc}")

    decision_policy, decision_policy_source = resolve_decision_policy(raw_config, warnings)

    try:
        pin, machine = promise_pin(cwd), machine_plugin(cwd)
        pin_warnings(pin, machine, warnings)
    except Exception as exc:  # pragma: no cover - defensive, never fail hard
        pin, machine = None, None
        warnings.append(f"promise pin check failed: {exc}")

    config_loaded = raw_config is not None
    adopted = bool(config_loaded and claude_md.get("hasPromiseSection"))
    if not adopted:
        warnings.append("project not adopted — run /promise adopt")

    suggested_mode: Optional[str] = None
    signals: List[str] = []
    ambiguous = False
    suggested_size: Optional[str] = None
    size_signals: List[str] = []
    if input_arg is not None:
        try:
            suggested_size, size_signals = suggest_size(input_arg)
        except Exception as exc:  # pragma: no cover - defensive, never fail hard
            warnings.append(f"size suggestion failed: {exc}")
        try:
            suggested_mode, signals, suggest_warnings, ambiguous = suggest_mode(
                input_arg, existing_docs, map_value
            )
            warnings.extend(suggest_warnings)
        except Exception as exc:  # pragma: no cover - defensive, never fail hard
            suggested_mode, signals, ambiguous = None, [], False
            warnings.append(f"mode suggestion failed: {exc}")

    return {
        "skillDir": skill_dir,
        "skillVersion": version,
        "cwd": cwd,
        "mode": mode,
        "frameworkPath": framework_path,
        "frameworkSource": framework_source,
        "config": {
            "path": config_path,
            "loaded": config_loaded,
            "raw": raw_config if config_loaded else {},
        },
        "docsHome": docs_home,
        "docsHomeSource": docs_home_source,
        "docsHomeForeignDocs": foreign_docs,
        "plansFolder": plans_folder,
        "commands": commands,
        "testRunners": test_runners,
        "branch": branch,
        "run": run_command.strip() if run_command else None,
        "branchSource": branch_source,
        "map": map_value,
        "mapUsable": map_usable,
        "sibling": sibling,
        "claudeMd": claude_md,
        "adopted": adopted,
        "existingDocs": existing_docs,
        "suggestedMode": suggested_mode,
        "signals": signals,
        "ambiguous": ambiguous,
        "suggestedSize": suggested_size,
        "sizeSignals": size_signals,
        "decisionPolicy": decision_policy,
        "decisionPolicySource": decision_policy_source,
        "legacyPolicyDocs": legacy_count,
        "promisePin": pin,
        "machinePlugin": machine,
        "githubTemplates": github_templates(cwd),
        "warnings": warnings,
    }


# Where GitHub looks for a pull request template, in its own order; any one is the project's.
PR_TEMPLATE_PLACES = (".github/pull_request_template.md", ".github/PULL_REQUEST_TEMPLATE.md",
                      "pull_request_template.md", "PULL_REQUEST_TEMPLATE.md",
                      "docs/pull_request_template.md", "docs/PULL_REQUEST_TEMPLATE.md",
                      ".github/PULL_REQUEST_TEMPLATE")
ISSUE_TEMPLATE = ".github/ISSUE_TEMPLATE/capability.md"


def github_templates(cwd: str) -> Dict[str, Optional[str]]:
    """The project's pull request template (wherever GitHub finds one) and the
    capability issue template ``adopt`` offers, each project-relative, or None
    when missing: every mode's Phase 0 line can then say so."""
    pr = next((p for p in PR_TEMPLATE_PLACES if os.path.exists(os.path.join(cwd, p))), None)
    issue = ISSUE_TEMPLATE if os.path.isfile(os.path.join(cwd, ISSUE_TEMPLATE)) else None
    return {"pullRequest": pr, "issue": issue}


PROMISE_PLUGIN_ID = "promise@promise"
RELEASE_TAG_RE = re.compile(r"^v?(\d+\.\d+\.\d+)$")
HEX_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")


def promise_pin(cwd: str) -> Optional[Dict[str, Any]]:
    """How ``.claude/settings.json`` declares the promise marketplace: ``ref`` (a
    branch or tag, the only pin Claude Code reads), ``sha`` (a key Claude Code's
    marketplace source ignores), and ``version`` when ``ref`` is a release tag.
    None when the file or the declaration is absent or unreadable."""
    path = os.path.join(cwd, ".claude", "settings.json")
    try:
        data = json.loads(read_text_tolerant(path))
        source = data["extraKnownMarketplaces"]["promise"]["source"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if not isinstance(source, dict):
        return None
    ref = source.get("ref") if isinstance(source.get("ref"), str) else None
    sha = source.get("sha") if isinstance(source.get("sha"), str) else None
    m = RELEASE_TAG_RE.match(ref or "")
    return {"ref": ref, "sha": sha.lower() if sha else None, "version": m.group(1) if m else None}


def machine_plugin(cwd: str) -> Optional[Dict[str, Any]]:
    """The promise plugin this machine runs in this project, from Claude Code's
    ``plugins/installed_plugins.json`` (``CLAUDE_CONFIG_DIR``, else ``~/.claude``):
    the project-scope install for this directory, else a local one, else the
    user-scope one. None when there is none, or the file cannot be read."""
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    try:
        data = json.loads(read_text_tolerant(os.path.join(base, "plugins", "installed_plugins.json")))
        entries = data["plugins"][PROMISE_PLUGIN_ID]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        return None
    here = os.path.normcase(os.path.realpath(cwd))

    def at_here(e: Dict[str, Any]) -> bool:
        where = e.get("projectPath")
        return isinstance(where, str) and os.path.normcase(os.path.realpath(where)) == here

    entries = [e for e in entries if isinstance(e, dict)]
    for pick in (lambda e: e.get("scope") == "project" and at_here(e),
                 lambda e: e.get("scope") == "local" and at_here(e),
                 lambda e: e.get("scope") in ("user", None) and not e.get("projectPath")):
        for e in entries:
            if pick(e):
                sha = e.get("gitCommitSha")
                where = e.get("installPath")
                return {"scope": e.get("scope") or "user",
                        "version": e.get("version") if isinstance(e.get("version"), str) else None,
                        "gitCommitSha": sha.lower() if isinstance(sha, str) else None,
                        "installPath": where if isinstance(where, str) else None}
    return None


def pin_warnings(pin: Optional[Dict[str, Any]], machine: Optional[Dict[str, Any]], warnings: List[str]) -> None:
    """A pin Claude Code cannot read, and a machine that runs another release than
    the repo pins: both mean a session runs promise the repo did not choose."""
    if not pin:
        return
    if pin["sha"] and not pin["ref"]:
        warnings.append("the repo pins promise by source.sha in .claude/settings.json, which Claude Code's "
                        "marketplace source does not read (it follows the default branch); pin a release tag "
                        "in source.ref instead: /promise upgrade")
    if not machine:
        return
    runs = f"{machine['version'] or '?'} ({(machine['gitCommitSha'] or '?')[:7]})"
    if pin["version"] and machine["version"] and pin["version"] != machine["version"]:
        warnings.append(f"this machine runs promise {runs}, the repo pins {pin['ref']}: run the machine step "
                        "(modes/upgrade.md § The machine step), then restart Claude Code")
    elif (not pin["ref"] and pin["sha"] and HEX_SHA_RE.match(pin["sha"]) and machine["gitCommitSha"]
          and not machine["gitCommitSha"].startswith(pin["sha"]) and not pin["sha"].startswith(machine["gitCommitSha"])):
        warnings.append(f"this machine runs promise {runs}, the repo pins {pin['sha'][:7]}: run the machine step "
                        "(modes/upgrade.md § The machine step), then restart Claude Code")


def _mode_word(mode_arg: Optional[str]) -> Optional[str]:
    """The "mode" value: the recognised word, "infer" for an unrecognised
    one, null when no --mode was passed."""
    if not mode_arg:
        return None
    if mode_arg in RECOGNISED_MODES:
        return mode_arg
    return "infer"


def _fallback_result(mode_arg: Optional[str], cwd_arg: Optional[str], error: Exception) -> Dict[str, Any]:
    """Absolute last resort so the process can still print a valid, complete schema."""
    cwd = os.path.abspath(cwd_arg) if cwd_arg else os.path.abspath(os.getcwd())
    skill_dir = get_skill_dir()
    return {
        "skillDir": skill_dir,
        "skillVersion": skill_version(skill_dir),
        "cwd": cwd,
        "mode": _mode_word(mode_arg),
        "frameworkPath": os.path.join(skill_dir, "outcome-framework.md"),
        "frameworkSource": "bundled",
        "config": {"path": None, "loaded": False, "raw": {}},
        "docsHome": None,
        "docsHomeSource": "none",
        "docsHomeForeignDocs": None,
        "plansFolder": None,
        "commands": {"typeCheck": None, "test": None, "lint": None, "source": "none"},
        "testRunners": [],
        "branch": DEFAULT_BRANCH,
        "branchSource": "default",
        "run": None,
        "map": None,
        "mapUsable": False,
        "sibling": None,
        "claudeMd": {"path": None, "hasPromiseSection": False, "sectionPath": None, "sectionCurrent": None},
        "adopted": False,
        "existingDocs": [],
        "suggestedMode": None,
        "signals": [],
        "ambiguous": False,
        "suggestedSize": None,
        "sizeSignals": [],
        "decisionPolicy": DEFAULT_DECISION_POLICY,
        "decisionPolicySource": "default",
        "legacyPolicyDocs": 0,
        "promisePin": None,
        "machinePlugin": None,
        "githubTemplates": {"pullRequest": None, "issue": None},
        "warnings": [f"orient.py internal error: {error}", "project not adopted — run /promise adopt"],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="orient.py",
        description=(
            "Resolve promise skill Phase 0 orientation (framework, config, "
            "docs home, commands, existing docs, CLAUDE.md adoption) and "
            "print it as one JSON object. Exits 0 for any valid invocation; "
            "a usage error (an unrecognised flag), a --cwd that is not a "
            "directory, or an --input-file that cannot be read exits 2."
        ),
    )
    parser.add_argument(
        "--mode", default=None,
        help="the mode word the skill was invoked with; without it the JSON says \"mode\": null",
    )
    parser.add_argument(
        "--cwd", default=None, help="project root to orient against (default: current directory)"
    )
    parser.add_argument(
        "--input",
        default=None,
        help=(
            "the user's full argument string; when given, the JSON gains "
            "suggestedMode, signals and ambiguous (a router hint, "
            "architecture.md §4)"
        ),
    )
    parser.add_argument(
        "--input-file",
        default=None,
        help="read the user's message from this file ('-' for stdin) instead of --input; "
             "use it whenever the message may contain quotes, so it never passes through a shell",
    )
    args = parser.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")

    if args.cwd is not None and not os.path.isdir(args.cwd):
        print(f"orient.py: no such directory: {args.cwd}", file=sys.stderr)
        return 2

    if getattr(args, "input_file", None):
        try:
            if args.input_file == "-":
                args.input = sys.stdin.read()
            else:
                with open(args.input_file, "r", encoding="utf-8-sig") as fh:
                    args.input = fh.read()
        except UnicodeDecodeError as exc:
            print(f"orient.py: --input-file is not UTF-8: {exc}", file=sys.stderr)
            return 2
        except OSError as exc:
            print(f"orient.py: cannot read --input-file: {exc}", file=sys.stderr)
            return 2

    try:
        result = build_orientation(args.mode, args.cwd, args.input)
    except Exception as exc:  # pragma: no cover - absolute last resort
        result = _fallback_result(args.mode, args.cwd, exc)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
