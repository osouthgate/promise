---
name: promise
description: |
  Carries a capability from intent to proof. Outcome docs record the promise,
  acceptance rows enter the capability map, and verdicts move with evidence.
  Use for "/promise", "outcome doc for X", "design this", "plan this", "spec this",
  or a braindump, transcript or ticket (new). Tiny changes need no doc.
  Also: a doc plus a change (revise); "review this doc" (review); "merge these docs"
  (merge); "arm" a doc (arm); feedback or "which capability covers this" (intake);
  "we already do this" or "update the map" (reconcile); "backfill the map"
  (backfill); "file an issue" (issue); "write the PR description" (pr);
  "set this project up for promise" (adopt); "upgrade promise" (upgrade);
  "promise doctor" (doctor); "help me get started with Promise" (onboard);
  "improve Promise" (retro). Infer the mode from plain words and name it.
argument-hint: "[onboard|new|revise|review|merge|arm|intake|reconcile|backfill|issue|pr|adopt|upgrade|retro|doctor] <what you want, in plain words>"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Agent
  - AskUserQuestion
---

# /promise

`outcome-framework.md`, beside this file, is the contract for the doc — section
rules, lifecycle, review rubric; `templates/outcome-doc.md` is the skeleton. When this
skill and the framework disagree, the framework wins. This skill produces the
doc up to `draft` and carries out the transitions a human calls for after
that; it never implements the capability the doc describes. A tiny ask
(§ Size the ask first) needs no doc and no mode; that section says the little it still does.
With a capability map, `arm` files an `agreed` doc's acceptance rows there and the map
becomes their home (`intake`/`reconcile` write it, not the doc); no map → the doc, always.

**Other hosts** (Codex, Cursor): the words and commands in order are in
`references/quickstart.md`. CLAUDE_SKILL_DIR is this file's directory; a line starting
with an exclamation mark and a backtick runs at load time — if it did not, run it first.

## Phase 0 — orient

!`python3 "${CLAUDE_SKILL_DIR}/scripts/orient.py" 2>&1 || true`

If the block above is empty or shows an error, run that exact command by hand first. No
`python3` → retry once with `python`, then `py -3`, and use that spelling all run. None
runs → say so, name the host's install (`winget install Python.Python.3.12`, `xcode-select
--install`, the distribution's package), and apply each script's rules by hand from the mode
files and the framework. Never substitute a second implementation.

User text is never composed into a command. For the mode and size hints, write the message
to a scratch file with the Write tool, run `python3 "${CLAUDE_SKILL_DIR}/scripts/orient.py"
--input-file <that file>`, and read `suggestedMode`, `signals[]`, `ambiguous` and
`suggestedSize`: hints; the sections below decide. Every later hop is the same: a query
reaches `adapter.py find` through `--query-file`, `outcome_rows.py --search` through `--search-file`.

State, in one line, what Phase 0 resolved: mode (inferred or not), size, framework source,
docs home and its source, `mapUsable` (`map: false` is "no map, on purpose"; a `sibling` map says so), `adopted`, and `skillVersion`.

Configured commands never run as composed shell strings: every `map.*` and verify command
runs through `python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py"` (`check.py` the same way),
which passes the user's text as one argument. They come from the project's config and run as
you. Before the first one in a session, print `adapter.py show` and ask — **(Recommended)**
run them, one reason — and run nothing configured until the yes; on no, continue as if no
map and no `commands` were configured, and say so.

`adopted: false` → mention once per session, in one line, that `/promise adopt` routes every
agent here; not a question. Continue with the requested mode.

## Size the ask first — before the mode, every time

An empty request or a request for guidance on starting Promise uses `onboard` first; size the product change once the user has chosen it.

Do the least the ask needs. Write the one line a release note would carry for it, then:

| Size | The release-note line | What promise does |
|---|---|---|
| **tiny** | none: wording, styling, layout, an internal rename or refactor, config that changes no behaviour, test-only work, or a fix that makes the product do what a row or §0 rule already promises | **No doc, no row, no mode, no question but the session's first-command yes** (first for a fix, else with the result). Build it (a fix starts with a failing test for the promise it restores, cited now on a `proven` row, else declared and left to `reconcile`: `references/sizing.md` § A tiny fix), run the tests (`adapter.py verify`), name the row whose tests it keeps green, and record the run (`session_report.py --record --size tiny`, § Batch) |
| **small** | one new behaviour whose line fits an existing doc's outcome or row's "so that" unchanged | `revise` that doc, or `intake` onto that row; no new doc. A new §0 rule is the human's, confirmed in `revise` |
| **capability** | a new job with its own "so that" | `new`, drafted from the user's own words, asking once for what is missing |
| **risky** | anything in a protected category (money, data retention, destructive migration, legal text, security or access, a public or persisted contract — a database column, an API field — an irreversible effect, regulated, third-party), even as a rename or a bump | `new` as written, at `spec` |
| **deferred** | the person's own words ask to build first: "ship it first", "hotfix", "spike", "promise it later" | **Build first: no doc, row or mode**, but every decision in a protected category is still asked. Run the tests there are; the close out and the pull request say `Size: deferred — owes: <each promise touched or made>`; `/promise reconcile` pays it later (`references/sizing.md` § Deferred) |

orient's `suggestedSize` says `deferred` when the person asks to build first, `risky` for a protected category, never tiny. In doubt, take
the larger. A tiny ask that turns out to change a promise or touch a protected category stops
and is sized again. Say the size and its reason in the Phase 0 line. Detail: `references/sizing.md`.
The skill decides whether anything is filed and at what size (the size, the relation, one row per job); the project's recipe decides how, and wins only there.

## Modes

The user types `/promise` and says what they want, in plain words. A leading mode
word is a shortcut, never a requirement. Read the input and Phase 0's findings,
name the mode inferred in one line ("Reading this as **reconcile** — you named a
PR"), and proceed. Never answer "use `/promise <mode>`", never refuse for syntax,
and ask only when two modes are genuinely plausible — then as one question with a
**(Recommended)** option first and one reason.

| Mode | Mode file | The input looks like… |
|---|---|---|
| `onboard` | `modes/onboard.md` | "help me get started with Promise", "guide me through Promise", "roll out Promise": choose a first workflow and its next step, using the context already supplied |
| `new` (default) | `modes/new.md` | an idea, ticket, transcript or braindump; "design / plan / spec this", "write a doc for X", "how should we build X" — and nothing below matches. Also the prototype door: "I built a prototype", "start from my prototype", "promise this prototype", "lock in what I built" (`references/sizing.md` § The prototype door: the person writes §0, `reconcile` proves each row by a watched mutation) |
| `revise` | `modes/revise.md` | a path to, or the title of, an existing outcome doc plus a change: "update", "add a rule", "change the outcome", "the signal is wrong", "tighten §5" |
| `review` | `modes/review.md` | a substantial doc, URL or paste authored elsewhere plus a critique verb: "review", "critique", "feedback", "is this any good", "check this against the framework" |
| `merge` | `modes/merge.md` | two or more doc paths or titles; "fold these", "these overlap", "consolidate", "which one survives" |
| `arm` | `modes/arm.md` | an `agreed` doc plus "start building", "arm it", "write the red tests", "file the rows", "kick off the build" |
| `intake` | `modes/intake.md` | a list of complaints, wishes, bug reports or feedback about the product; "what does this map to", "turn this into scenarios / gherkins", "which capability covers X", "add this as a scenario to <row>" |
| `reconcile` | `modes/reconcile.md` | a PR number, branch, commit or test file; "we shipped X", "we already do this", "isn't X covered", "update the map / the row / the doc now that Y landed" |
| `backfill` | `modes/backfill.md` | a product that already exists: "backfill the map", "retrofit promises onto the product", "map what the code does today", "every test / every route needs a home", "move our docs into promise" |
| `issue` | `modes/issue.md` | an issue number or an ask to file: "file an issue for X", "check issue #12 against the map", "triage / review these issues", "which capabilities does this issue touch" |
| `pr` | `modes/pr.md` | a pull request to describe: "write the PR description", "describe this PR", "PR body for #34", "update the PR text" |
| `retro` | `modes/retro.md` | a problem with promise itself, not the product: "retro", "what went wrong with promise", "improve promise", "report this to promise", "why did the agent do that" |
| `adopt` | `modes/adopt.md` | "set this project up", "install / configure promise here", "add promise to CLAUDE.md" — or Phase 0 reports the project is not adopted and the user agrees to fix that first |
| `doctor` | `modes/doctor.md` | "promise doctor", "audit Promise adoption": inspect feature adoption and suggest simplifications |
| `upgrade` | `modes/upgrade.md` | "upgrade promise", "move the promise pin", "is our promise version behind": this repository's pin to a newer promise, as its own pull request (`pin_check.py` says how far behind) |

Inference uses Phase 0 too (architecture.md § 4 has every signal): a doc in `existingDocs`
plus a change leans `revise`, plus a critique verb `review`; a row id leans `intake` or
`reconcile`; a test file or commit leans `reconcile`; observed behaviour in a whole product or
an explicitly bounded existing feature is `backfill` — a new design or spec is `new`. `issue` and `pr` win over every
other signal; a recognised first word wins outright (`review these issues` is `issue`).

Read only the detected mode file and the references its header names; for framework sections,
only those: `python3 "${CLAUDE_SKILL_DIR}/scripts/framework_section.py" "The contract" "Lifecycle"`.

## Rules that hold in every mode

- The doc's `Decision policy:` (framework § Decision policy), from the repo's config (orient's `decisionPolicy`, `auto`
  when unset, never asked per doc), says which product decisions go to the user; the agent records the rest in §8 with a
  rollback, and a protected category, or doubt, is always asked. Every decision put to the user is one option marked
  **(Recommended)** first, with one concrete reason — never a silent pick. The user's edit enters, not the candidate.
- **Batch, don't interrupt** (`references/sizing.md` § Batch): take the Recommended option on anything reversible, keep
  working, and end with one message: **Needs you** (on the best surface the host has, `references/decision-sheet.md`),
  **Decided for you** (one line each, with undo), **Not checked**. Then record the run, a tiny one too
  (`session_report.py --record`, § Batch): its size, stops and those three counts.
- Every ask explains itself, anywhere (a sheet, a reply, an issue, a pull request): in plain
  words, what it is and what to choose. An id (`Q2`, `AT-3`, `#87`) never stands alone, even if explained before.
- Verify before believing: a current-state claim carries `file:line` read this run, not remembered from an earlier one. A negative claim ("can't", "no way to", "only X has") is a premise, not a citation: it gets a Load-bearing premises row — the full field set the source returns, not just the field you went looking for, and every repository this capability touches searched for an existing way it is already done (framework § Section rules).
- `agreed` and `shipped` are typed by a human, never by this skill. `building` is the
  one exception: `arm` writes it, and only after the human has seen the red gate
  commit and said yes — the commit is the human act the status records.
- Every mode that writes a doc closes out by pasting §0 inline, verbatim, and says what it could not check. Never
  require syntax: a mode word is a shortcut; the input decides (`/promise fix the doc` gets `revise`).

Read `references/anti-rationalizations.md` before new, revise, merge, arm, intake, reconcile and backfill: required reading there, not background.
