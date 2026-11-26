Read before this: references/altitude.md · references/anti-rationalizations.md · outcome-framework.md § The contract · § Lifecycle
Read at the file step: the project's `map.recipe` (and `map.index`, if configured), before any row is written.
Phase 0 line: mode `backfill` (say if inferred), framework source, docs home and its source (and `docsHomeForeignDocs`), whether a map is configured (orient's `mapUsable`), whether `map.junit` and `map.surfaces` are set, the `testRunners` found, and whether the project is adopted.
Writes: map rows per the recipe, each sized by `references/sizing.md` § How big a row is, which a recipe never overrides (`origin: backfill`, `doc: null`), in lockstep, one commit per feature. With the user's yes: `map.junit` and `map.surfaces` in the config's existing `map` object; outcome docs at `draft` under `docsHome` that replace legacy design docs, each with the `git rm` of the replaced doc in the same commit (or, on a no to the delete, its cut to one pointer line that names the new doc) and the links that pointed at it; and the `git rm` of each register the map absorbed, or its cut to one pointer line.

# Backfill — fit promise to a product that already exists

A product built before promise has code, tests and legacy docs, and no map. Backfill
writes the map of observed behaviour, for the whole product or a selected pilot
(`references/scoped-backfill.md`). Within that boundary every test and entry point
has a home, and every gap shows. A backfilled row records
observed behaviour until an agreed outcome doc cites it (framework § Lifecycle).

## Invariants — state them, never trade them for speed

1. **Observed is not promised.** A backfilled row carries `origin: backfill` and
   `doc: null`. Its story says what the code does today, with `file:line` read this
   run. It becomes a promise only through the bridge of an agreed outcome doc.
2. **Every test has a home.** Each test case in the run is cited by a row, or sits on
   the dated "left out" list with a reason the human confirmed. A `leftOut` entry
   matches one test exactly: its full `<file>::<name>`, never a describe block, a file
   or a `%s` pattern, so the human confirms each test, not a group.
   `map_report.py --orphans` is the check, not a reading of the suite.
3. **Every entry point has a home.** Each line the project's `map.surfaces` command
   prints is in some row's `surfaces`. `map_report.py --surfaces` is the check. An
   entry point joins a row only when a test that row cites enters through it. A
   route with no test gets a `not-built` row of its own, even when a tested story
   covers it: production code nobody proves is the gap this mode exists to show.
4. **The recorded verdict never goes above the run.** Record the verdict
   `map_report.py` computes, capped at `under-proven`. Its `LANE-GREEN` is not proven:
   it joins citations by lane, not by scenario, so one passing test turns every
   scenario at that altitude green. `proven` needs, per scenario, a test asserting its
   own `Then` and a watched kill: `reconcile`, one scenario at a time.
5. **The writer never verifies its own rows.** Pass 2 is a different agent or person.
6. **A legacy doc moves; it is not copied.** Its content goes into one outcome doc, and
   the legacy file is deleted in the same commit on the user's yes (framework § The
   contract, rule 2). On a no, it is cut, in the same commit, to one pointer line that
   names the outcome doc: never two homes. §0 holds verbatim quotes only (rule 1).
7. **Delegate enumeration, never decisions** (`modes/intake.md`, invariant 7). What
   is a promise, what is left out, and which rows are `must` are the user's calls.

## Before you start

Stop and fix, in this order, rather than backfilling partway:

- **The boundary.** Map observed behaviour across the product or the selected
  pilot (`references/scoped-backfill.md`). A design for new behaviour is `new`.
- **Adopted.** Not adopted → `modes/adopt.md` first, **(Recommended)**.
- **A map.** None → offer `scripts/start_map.py` **(Recommended)**: a backfill with no
  map has nowhere to file rows. `map: false` (none, on purpose) → say so and stop. An
  incomplete `map` object → name the missing keys and stop: `start_map.py` keeps it.
- **A test run in JUnit.** `map.junit` names where the tests write it; orient's
  `testRunners` names the flag for each runner. No JUnit → set it up first, and, on
  the user's yes, add `map.junit` to the map object. Without a run, citations guess.
- **An entry-point list.** `map.surfaces` is a command that prints the product's
  entry points, one per line, from the code (routes, pages, jobs, webhooks, tools).
  None → write a small script with the user and, with their yes, set it as
  `map.surfaces`; say that the list is only as complete as that script.
- **Coverage (optional, Recommended).** It shows code in an entry point no test runs.
- **Features.** For a pilot, use its one selected feature. For a whole product, suggest
  3–8 features by surface, with tests and entry points. The user can change the table.

## Pass 1 — write (one writer per feature)

Tests first, then entry points, then legacy registers and docs. Each writer writes its
candidate rows to a scratch file for its feature (quickstart § The backfill verifier), never to the map.

**1a. Tests to rows.** Run
`python3 "${CLAUDE_SKILL_DIR}/scripts/map_report.py" --map <map> --junit <run> --orphans --json`.
For each orphan test, grouped by test file: read the test and the code it calls,
then use the recipe's routing table: an existing scenario, a case on the same job
or a genuinely new job. Preserve the current sizing rules unless the user chose
the supported relaxed job trial. Tests differing only in data are one scenario. The altitude comes from the
`Then`, never from the test that happens to exist: a lower-altitude test is cited,
and the row stays `under-proven`. A test that proves no behaviour (a type test, a
helper) goes on the "left out" list with a one-line reason, one entry per test.

**1b. Entry points to rows.** Run
`python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" surfaces --out <scratch file>`
after the session's yes (SKILL.md Phase 0): it runs `map.surfaces` as argv with no
shell and writes the entry points, one per line. Never type the configured command
into a shell line. Run the same report with `--surfaces <that file>`. For each entry
point with no row, read its handler. A test an existing row cites enters through it
→ add the entry point to that row's `surfaces`. No cited test does → a new row, even
when an existing story covers it: the story from the code, naming the entry point,
1–5 scenarios, empty evidence arrays, verdict `not-built`, and `parent` naming the
covering row if any. With coverage: an uncovered branch inside a mapped entry point
(an error path, a permission check) becomes a scenario with no citation; the
computed verdict cannot see it (invariant 4), so the hand-off names it.

**1c. Legacy registers and docs.** A register the project already keeps (a journey
catalogue, a coverage table, a list of golden tasks) is input: its ids go in a row's
`aliases`, never as row ids, and its pass criteria are candidate scenarios that the
code confirms or refutes. Classify each legacy register and design doc:

| It is… | It becomes… |
|---|---|
| a register of promises, journeys or gaps | nothing, once every id in it is an alias on a row: the map holds its pass criteria now. With the user's yes, delete it, or cut it to one line pointing at the map, in the commit of the last feature that absorbed it. Kept whole, it is a second list of gaps that nothing checks (framework § The contract, rule 2) |
| a file tests read as input (golden tasks an eval runs) | test data, not a register: it stays, and its ids stay aliases |
| the design of one capability | one outcome doc at `draft`, rendered with `render_outcome.py` |
| two or more docs on one capability | one outcome doc; `modes/merge.md` decides the survivor |
| architecture, hosting, a runbook, a glossary | nothing; it stays where it is, and the close-out says so |

The outcome doc is a full draft, never a thin one: `revise` fills a thin draft from
`modes/new.md` and would lose the legacy text and the map's, and the lint rejects a
thin draft with §4–§7 written. Its `Supersedes:` line names the legacy path.

- **§0** is a candidate block of verbatim quotes from the legacy doc's decisions and
  rules, each citing `path:line` at a commit the default branch holds, now or after
  the merge (a squash merge drops a branch-only commit), so `git show <sha>:<path>`
  finds it after the delete. Its first line is `**Pending verbatim confirmation:** <n>
  quotes from <path> at <sha>. A human confirms by deleting this line.`; a quote reads
  `"<words>" (source: <path>:<line> @ <sha>)` (`examples/backfill-moved.md`). The human
  checks each against its source and deletes that line, at `draft`; the lint fails a
  doc past `draft` that still holds it. A field it never
  decided (the outcome line, how-we'll-know) reads `Open — Qn (BLOCKING).`, with that
  question in §9: the doc cannot be agreed until it is answered.
- **§3–§5, §7:** §3, §4 and §7 follow `modes/new.md` § Draft the agent half, from
  the legacy doc and the code; §7 names the rows with a gap, since the code exists.
  §5 comes from the legacy doc and the code, pinned to a commit, with design and
  description kept apart.
- **§6** takes every scenario of this capability's backfilled rows, one line each,
  ordered by row, `Then` and `Altitude` copied verbatim from the map (the map keeps a
  `<word>` in a code span, so the copy lints), `Row` cells empty until the bridge. A
  long §6 is expected (a hundred lines or more); it sits outside the review surface
  (framework § Section rules), and each line is one scenario `arm` links. Split the
  doc only when its rows serve two separable outcomes. No row enters the doc → derive
  §6 from §3 as `new` does: proposed lines, which join the map through `arm` as new rows.
- **§8** keeps the legacy doc's decisions with their owners and dates, and one entry
  names the rows §6 was copied from, which `revise` and `arm` read.

## Pass 2 — verify (a different agent per feature)

Hand each verifier its feature's scratch file and this list (`references/quickstart.md` §
The backfill verifier: prompt, file shape); no second agent → the human checks the list.

- **Story:** each claim checked against the code at the pinned commit. An invented
  identifier is a finding, not a nit.
- **Citations:** each one matches one case in the run (its bucket is not
  `bad-citation` or `never-ran`, and a citation the report marks `ambiguous` is a
  finding), and sits in the lane its scenario's altitude picks. A lane in
  `summary.lanesNotInRun` was not in this run: join its suite's JUnit, then judge.
- **Left out:** each entry names exactly one case in the run, with a reason the
  human confirmed. An entry for a describe block, a file or a pattern is a finding.
- **Scenarios:** 1–5, or the explicit supported relaxed job trial; each `Then` is assertable; its wording
  and altitude agree (an "I see…" `Then` is `perception`); a `<word>` is in backticks.
- **Surfaces:** each one is in the surfaces file, and a test the row cites enters
  through it (a `not-built` row cites none: its surfaces are its reason to exist).
  None is claimed by two rows unless both stories really enter there.
- **Duplicates:** two rows with one story are merged before filing. A `not-built`
  row for an untested entry point, whose `parent` names the tested row, is not one.
- **Verdict:** equal to the computed one, capped at `under-proven`.

For each moved doc, the verifier greps every §0 quote in the legacy doc at its cited
commit (verbatim or it goes; a commit the default branch will not hold is re-cited at
one it does), checks that no content of the legacy doc vanished without a stated home
(framework § The framework as a review rubric, check 4), and checks that each path on
the `Supersedes:` line is deleted in the doc's commit or holds only the pointer line
(`check.py` warns for a path that holds more).

Send rows back with numbered reasons; the writer fixes them; verify again. Two
rounds at most: what is still disputed goes to the user as a list, never filed.

## File, in lockstep

Read the recipe from the file, fresh. Run `git fetch`, then take ids from `next-id --from <the backfill's issue or pull request>` in feature order (`CAP-i<n>a`, `CAP-i<n>b`, …, pushed feature by feature, since another branch under the same issue could take the same letters), append
the verified rows with `origin: backfill`, `doc: null` and their feature, in the spelling the project's map already uses (`feature`, or the alias `area`; `feature` in a new map), which orient warns about when the map or its reader keeps `areas`/`area`; run the recipe's
checks. Then run `map_report.py` with `--orphans` and `--surfaces`: both lists must be
empty apart from the confirmed "left out" tests. One commit per feature for the map; one
commit per moved doc, holding the outcome doc, the `git rm` of the legacy doc (or, on
a no, its pointer line) and the updated links (`grep` every path that named it). A
register the user agreed to retire goes in the commit of the last feature that absorbed
it, with its links updated too.

## Hand the result to the user

The user does not read every scenario. Give, in this order:

1. The headline from `map_report.py`: rows, proven, under-proven, not-built, tests
   with no row, entry points with no row. Say plainly that its `proven` is computed,
   not proven: it counts passing tests per lane, not per scenario, and no kill was
   watched. Every row is recorded `under-proven` at most.
2. The stories, one line each, by feature, with their verdict: the list to disagree
   with. The user strikes behaviour that is not a promise and marks the `must` rows.
   A struck row stays in the map as observed (`origin: backfill`, `doc: null`), so
   its tests and entry points keep their home: striking means no outcome doc links
   it, and its lines leave any moved doc's §6. A row goes only when its code does.
3. The gaps: `not-built` rows with entry points, which is production code with no
   test, and scenarios with no citation. `must` rows first.
4. The moved docs: each outcome doc with its count of pending §0 lines, its open
   BLOCKING questions and its §6 line count. Each §0 line waits for the user's
   verbatim confirmation; nothing here is `agreed`.
5. What was not checked: features skipped, a surfaces script that cannot see an entry
   point kind, suites that did not run here.

## From observed to promised

- When a moved doc is agreed, `arm`'s bridge links each §6 line to its backfilled row
  (the `Row` cell cites the existing id and the row's `doc` is set) instead of
  filing a new row. It links only on an exact match of a scenario's `Then` and
  altitude (`modes/arm.md`).
- A linked row describes code that exists, so `arm` never arms it red; only a §6 line
  no backfilled row matches is a new promise, armed red as usual. When every bridged
  row is a backfilled row, proven through `reconcile`, the human may type `shipped`
  with no red gate: the code came before the promise (framework § Lifecycle).
- Promotion to `proven` is `reconcile`, one scenario at a time, on a test that
  asserts that scenario's own `Then`, watched dying; `must` rows first.

## What this mode refuses to do

- Record `proven` without a watched kill, or any verdict above the run, or read a
  computed `LANE-GREEN` as proof.
- Write a §0 line that is not a verbatim quote, sourced at a commit, marked pending.
- Let a writer verify its own rows.
- Leave a test or an entry point with no home without saying so.
- Put an untested entry point in a tested row's `surfaces`.
- Delete a legacy doc or register before its content has a home, or without the
  user's yes; or keep one whole, or more than its pointer line, beside its new home.
- Build the entry-point list by hand: it comes from a command that reads the code,
  run through `adapter.py surfaces`, never typed into a shell line.
