Read before this: outcome-framework.md § Lifecycle · references/altitude.md · references/anti-rationalizations.md · outcome-framework.md § Decision policy
Read at the bridge step: the project's `map.recipe`, if a map is configured.
Phase 0 line: mode `arm` (say if inferred), framework source, docs home and its source, the doc's `Status`, the count of unresolved BLOCKING §9 questions, whether the lint passes, whether a map is configured (orient's `mapUsable`), and whether the project is adopted.
Writes: the work branch (`feat/<capability>` by default; none is cut under `branch: current`), red tests and the stubs they import, the `Red run:` and `Filed without red run:` lines in §6, the header (`Red gate:` line) and `Status:` in the doc, committed by explicit path as the doc commit, after the red-gate commit; with a map, also each group's not-built row per the recipe and the §6 `Row` column, or, when every §6 line links a backfilled row, the bridge alone in one commit with no red gate; when the human takes the starter-map offer, also the three starter files and the config's `map` object; `commands.test` (and, with a map, `map.junit`) in the config when step 1 takes one.

# Arm — `agreed → building`

## Preconditions

- `Status:` is `agreed`.
- No `Depth: thin` line: a thin draft is filled with `revise` first (the lint reports it as `THIN_DRAFT`).
- Zero unresolved BLOCKING questions in §9. The lint does not check the BLOCKING count — read §9 yourself.
- `scripts/lint_outcome.py` passes on the doc (the lint checks shape, not whether the filled lines are true — read §4–§7 yourself).
- **The agent decisions still hold** (framework § Decision policy). `decisions.py recheck <doc>` lists each provisional
  §8 row due now: Review `before arm`, a review date that has come, or reversal that stops being cheap at arm. One
  no longer cheap to reverse → `decisions.py promote <doc> --decision <n> --by agent --reason "<why>"`: it becomes
  a BLOCKING §9 question, and arm waits for the answer. Say which rows you kept, and why each is still cheap.
- A map is configured, or it is not — state which; the rest of this mode branches on it.

Any precondition unmet → stop and say which one, rather than arming partway.

## First, the branch

Every edit below — map rows, §6, the header — and every commit land on **the work
branch**. The config's `branch` (orient's `branch`) says which branch that is:

- **A pattern** — `feat/{slug}` by default, or the project's own, such as
  `work/{slug}`; the slug is the capability title in lower-case kebab form (`a-z`,
  `0-9` and `-` only). orient takes a pattern only when it holds ASCII letters,
  digits and `. _ - /` around `{slug}`, with no `..`, no leading `-` and no part
  ending `.lock`; any other value warns and the default applies. The filled name
  keeps to those same characters, so check it before you type it, and quote it in
  single quotes on the shell line (`git switch -c 'feat/channel-muting'`). Cut the
  work branch from the branch the session is on, and refuse if it already exists.
  Name the base; if it is not the project's default branch, say so and ask before
  continuing — a branch cut from the wrong base is the user's call, not this mode's
  guess. Nothing lands on the branch you started from.
- **`current`** — for a host that lets a session push only to its own branch. Cut
  nothing: the work branch is the session's branch, and commits already on it stay.
  Refuse if it is the project's default branch. The setting is committed, so it
  holds on every host; a user who wants a branch cut this time says so, and the
  default pattern applies.

The project's default branch is the one `git symbolic-ref --short
refs/remotes/origin/HEAD` names, less its `origin/` prefix. When git cannot name
it, ask the user once; never guess. Either way, refuse and say why if HEAD is
detached, or if the working tree has staged changes that are not the test files
this mode writes (an unrelated staged file would ride into the red-gate commit).
Show `git status --short` before and after.

## No map yet — offer the starter

When no map is configured (orient's `mapUsable` is false) **and** the config's
`map` is `null` or absent, offer once, on the work branch, before anything is filed:

- **(Recommended)** — start the project's capability map now, from the skill's
  starter. Reason: this doc is a promise a human has just agreed, and the map is
  where the project's promises add up — one row per story, each naming the tests
  that prove it, with an honest verdict — so the platform's map starts with its
  first real promise, not on the day of adoption.
- Arm without a map. §6 stays the only home of these rows; `arm` can offer again
  on the next agreed doc.

Show `python3 "${CLAUDE_SKILL_DIR}/scripts/start_map.py" --dry-run` (the three
files and the config diff it prints; `--dest <folder>` if the human wants another
home than `docs/capabilities`). On yes, run it without `--dry-run`, then re-run
`orient.py` and confirm `mapUsable` is true. The dry run printed every command the
new map configures, so that yes is also the session's yes for running them (SKILL.md
Phase 0). Then carry on with the bridge below, with the map just started.

A config whose `map` is an object, even an incomplete one, is the project's own map
in progress: never offer the starter over it (`start_map.py` refuses it too) — say
which keys are missing, per orient's warnings, and arm without a map.

A config whose `map` is `false` keeps no map, on purpose (`references/config.md`
§ Without a map): never offer the starter. Say "no map, on purpose" in one line and
arm without a map.

## The bridge, with a map

On the work branch:
Run `python3 "${CLAUDE_SKILL_DIR}/scripts/outcome_rows.py" <doc> --json` to get the
§6 rows and the §0 rules with their tags. Group the AT rows into map rows **by the job
they serve**: one row per distinct "so that" (`references/sizing.md` § How big a row is). A §0
rule is a set of scenarios, not a story, so a doc whose AT rows (at most five) serve one
"so that" files one row, whatever its rule count. One map row is one story plus 1–5
scenarios; a job with more is a chain — split it, with a parent. An
AT row that already carries a `Row` id is not re-filed. Nor is one that matches a
backfilled row (`origin: backfill`, `doc: null`, `modes/backfill.md`): propose linking
it — the `Row` cell cites that id and the row's `doc` is set to this doc, in the same
lockstep commit. A match is exact: the line's `Then` equals one of the row's scenario
`then` texts, case and whitespace aside, and its `Altitude` equals that scenario's
`altitude`. Read both with `adapter.py --json row <id>`; the doc's §8 names the rows
its §6 was copied from. Anything less is a new row, never a link.
`bridge_validate.py --linking` checks each link on this rule when `map.row` prints
the row as JSON with its scenarios, as the starter map does; a map that prints text
gets `ROW_TEXT_ONLY` instead, and then you check each link by hand.

Group by the job; show the table at the red gate (step 5), where the user can regroup.
Ask first only when the split is not plain (two "so that"s, or one job over five that must
chain) — **(Recommended)** first, one concrete reason. Flag AT rows no §0 rule cites there.

Service policies, only when named: follow `references/service-targets.md`.
(Gated once per session — SKILL.md Phase 0 asks before the first configured
command runs. `adapter.py` runs the project's own commands, unsandboxed, in the
project root; they may install packages or write files.) Before filing anything,
read `map.recipe` from the file and run
`git fetch`, then `python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" --json next-id --from issue:<n>`, the issue the doc's work comes from (`pr:<n>` when there is none), so no row of another issue can hold the id; push soon after, since another branch for the same issue could take the same letters (and
`--json row <an existing id>` if the recipe names one). The recipe unreadable, or
either call exiting non-zero (2 = refused, 127 = executable not found, anything
else = the project's own command failed) → **stop before filing**, paste the
adapter's output verbatim, and say the map config is broken (`map.recipe` /
`map.row` / `map.nextId`). Phase 0 does not check these — `orient.py` checks the
config's shape and `adapter.py show` runs nothing — so this is the first point
that can. Fix the config, never the doc; never invent a row id.

File each group as a **not-built row**, per the recipe (uncommitted until the doc commit, after the gate's yes) — the recipe's
lockstep names every file it touches, and a must-priority row needs a real test or
a dated, reasoned exemption from day one. Write the new row id into the `Row` column
of each §6 line it covers, adding the column between `Altitude` and the table's edge
if the doc has none, and add one line under the §6 table: `Snapshot taken at
`agreed` on <date>; the map is the source of these scenarios from here on.` §0's
rule tags stay AT aliases; they do not change. From this point `reconcile` reads the
map, never §6.

Then run `python3 "${CLAUDE_SKILL_DIR}/scripts/bridge_validate.py" --linking <doc>`:
this run made the links, so a `Then` or an altitude that is not in the map is an
error here. Fix every error before the steps below, by rule:

| Rule | Meaning | Do |
|---|---|---|
| `ROW_MISSING`, `SNAPSHOT_LINE_MISSING` | a doc omission | fix the doc |
| `ROW_ID_FORMAT` | the id written is not one the map issues | re-read it from `next-id` or the recipe and correct the `Row` cell; **never edit `map.rowIdPattern` to admit it** |
| `ROW_NOT_FOUND` | ambiguous | run `adapter.py --json row <id>` and read the child output: the map's own "no such row" text means a wrong id in the doc (fix the cell); a command failure means `map.row` is broken (stop, config problem) |
| `INVALID_ROW_ID_PATTERN`, `UNREADABLE` | config or file problem | stop and say so |
| `NO_ROW_ID_PATTERN`, `NO_MAP_ROW_COMMAND` (warn) | `map.rowIdPattern` is unset, or `map.row` is an empty string | say so; fix the config, not the doc |
| `THEN_NOT_IN_MAP`, `ALTITUDE_NOT_IN_MAP` (errors under `--linking`) | the §6 `Then` is not one of the row's scenarios, or that scenario has another altitude | from this run's own bridge: a row or a link this run made is wrong — fix the row this run filed, or unlink and file a new row, before the commit; never edit §6. On a later run (no `--linking`, a warning): drift — name it in the close-out; never edit §6, which is now a snapshot |
| `ROW_TEXT_ONLY` (info) | `map.row` prints text, not a JSON row, so the `Then` was checked as a substring and the altitude not at all | check each link against `adapter.py --json row <id>` yourself, and say so in the close-out |
| `ALTITUDE_MISSING` (error under `--linking`) | a §6 line with no `Altitude` has the `Then` of a scenario that has one | never link it: a link needs the same altitude. Ask the human for the altitude, then link or file the line. On a later run (info): name it in the close-out |

Loosening `map.rowIdPattern`, a checker, a ceiling or a ratchet to make
`bridge_validate.py` or `map.checks` pass is never a fix — as in `intake` and `reconcile`.
No map → skip this section: the `Row` column stays empty and `bridge_validate.py` does not run.

## With or without a map

0. **Code that already exists needs no red test.** A new test for working code passes
   at once, and nothing can be stubbed without breaking that code: never stub or break
   it to get a red run. Two kinds of §6 line are this: with a map, a line linked to a
   backfilled row; and, from a prototype (`references/sizing.md` § The prototype door),
   a line for behaviour the code already has. Neither is armed red. Name them all, in §6
   order, in one line under the §6 table (and the snapshot line), in every case:
   `Filed without red run: AT-2, AT-4 — prototype` (or `— backfilled`). `reconcile`
   writes or finds each test, watches the kill and writes its `Kill:` line, the
   proof for that line (framework § Lifecycle). Only lines for behaviour not built yet go
   red below. None → no red gate and no `building`: skip steps 1–7, and commit by
   explicit path the `Row` cells, the snapshot and Filed lines, a dated §8 entry saying
   nothing was left to turn red, and the map's `doc` fields, as `docs(<scope>): bridge
   <capability> to existing code`. The status stays as the human left it. Hand back (step 8).
1. **No test command yet** — `commands.test` is `null` (a new project has none) →
   take the one orient's `testRunners` names (`pytest`, `node --test`, `python3 -m
   unittest discover -s tests`…) and, with a map, its `map.junit` path
   (`testRunners[].junit`; plain unittest: `scripts/junit_unittest.py`); write both
   into the config, listed under Decided for you (ask only when orient names two).
   The config rides in the doc commit (step 6). No runner at all → the tests you write
   in this step pick it; say which.
   **Write the §6 rows as failing tests**, with typed stubs that throw, so
   `commands.typeCheck` stays green while the tests fail at the assertion. If
   `typeCheck` is `null`, say so and rely on the tests alone — never invent a
   command the project does not have. A stub is only a signature that throws
   (`raise NotImplementedError`, `throw new Error("not built")`), never a value that
   could pass a test. A new stub module goes in the red-gate commit with the tests
   (step 3); a test failing inside a stub is red. A test that fails to import or to
   compile is broken, not red: fix it before the commit.
2. **Run them RED** with `python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" --json verify`.
   Expect `typeCheck` exit 0 and `test` non-zero; the sequence stops there, so
   `lint` does not run at arm time — that is expected. Keep the `test` step's counts
   for the `Red run:` line (step 3); the full output goes in the close-out. A
   `typeCheck` step reporting exit 127 (`executable not found`) is a configured
   command that cannot run here: quote its stderr, treat `typeCheck` as `null` for
   this run (step 1), and prove the red gate per step 7 —
   never substitute or invent a command; a pre-existing `typeCheck` failure that would
   stop the sequence is run past with `verify --only test`, and named in the close-out.
   `[]`: no `commands.*` is set and nothing ran; prove the red gate per step 7, say so.
3. **Show the staged diff, then commit only the test files, and the stubs they
   import, by explicit path** as the red-gate commit — `test(<scope>): red
   acceptance gate for <capability>` — and record the sha in the doc header as its
   own line, directly under `Supersedes:`: `Red gate: <sha> <YYYY-MM-DD>`. Add one
   line under the §6 table (with a map, under the snapshot line), with that same sha:
   `Red run: <command> — <n> failing, <m> passing at <sha> on <YYYY-MM-DD>`. With the
   Filed line of step 0, these are the only lines arm adds to §6 after the snapshot.
4. **With a map**, cite each red test in the lane its row's `Altitude` column
   picks, per `map.lanes` (`references/altitude.md`), so the row's evidence is
   honest from day one — under-proven, visibly, rather than silent.
5. **Ask, then write `Status: building`.** Show the red output, the commit sha, the
   grouping table and what you decided this run (the base, the test command), and ask
   the human to confirm the gate — one yes for all of it; on yes, write `building`.
   This is the only status this skill writes; the approved commit is the act it records.
6. **Commit the doc — and, with a map, the recipe's row files, plus the three starter
   files and the promise config when this run started the map or set a command — by
   explicit path**, as the doc commit, after the red-gate commit:
   `docs(<scope>): arm <capability> — building`. Show `git status --short` after
   it. Anything else the tree now shows (a lockfile, `node_modules/`, a cache) came
   from the project's own commands; name it in the close-out, never add it.
7. Red proof cannot be witnessed in this environment (no dependencies, no sandbox) →
   **say so in the `Red run:` line with the exact command** that would prove it
   (`Red run: not witnessed here; prove with <command>`) — never silently skip it.
8. **Hand back.** Run `python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" checks` if a
   map is configured and `map.checks` is set (the adapter refuses with exit 2
   otherwise — that is not a failed check); `adapter.py verify` if any `commands.*`
   is configured — when step 1 wrote tests, the `test` step is red by design: say
   so rather than reporting a failure; then `scripts/lint_outcome.py <doc>`, always.

## Close out

Paste §0 inline. List: the rows filed (with a map) or the AT rows armed (without
one), the backfilled rows linked, the tests written, both commit shas (red gate,
doc) or the one bridge commit when nothing went red, any `bridge_validate.py`
drift warnings, what `git status --short` still shows and why, and what could not
be checked in this environment.
