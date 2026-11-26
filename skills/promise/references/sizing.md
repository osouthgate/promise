# Sizing and batching — do the least the ask needs

*Read by SKILL.md § Size the ask first, by every mode's close-out, and by every mode
that files or sizes a row.*

Most asks are small. The full procedure (an outcome doc, an interview, rows in the
map, a red gate) is for the promises that need it. Size the ask first, say the size
in the Phase 0 line, and do no more than that size needs.

## The one-step test

Write the one line a release note would carry for this change.

- **No line** → **tiny**.
- **A line about something a row or doc already holds** → **small**: a scenario on
  that row or an AT row in that doc, or nothing when one already says it.
- **A line naming a new job, with its own "so that"** → **capability**.
- **Any line touching a protected category** (framework § Decision policy) → **risky**.

orient's `suggestedSize` reads the ask's words: `deferred` when they ask to build first
(§ Deferred; a protected category in them is still asked in full), `risky` when they name
a protected category, else null. Words can show that an ask is risky, never that it is tiny
("refactor checkout so it charges tax" is not), so tiny is always your call, by the
test above. In doubt between two sizes, take the larger.

With a sibling map (orient's `sibling` is set; `mapUsable` stays false), the rows a line may be about
are in another repository's map: look them up there with `adapter.py find` and `row`
(`references/config.md` § Without a map), and name them with that repo. No checkout
at `sibling.path` → size as with no map, and say so under **Not checked**.

## What each size does

| Size | The ask | What promise does | Still holds |
|---|---|---|---|
| **tiny** | Wording, styling, layout, an internal rename or refactor, config that changes no behaviour, test-only work, or a fix that makes the product do what a row or §0 rule already promises. Not a rename of a database column or an API field, legal text, or a bump of a payment or auth library: those are risky | No doc, no map row, no mode, and no question but the one below: the Phase 0 line says "tiny — building it". Build it; a fix starts with a failing test for the promise it restores (§ A tiny fix says where it is cited). Run the project's tests (`adapter.py verify`); in a session that has not yet said yes to configured commands (SKILL.md Phase 0), that yes is the one question tiny asks: a fix asks it first, since its failing test must run before the fix; a change with nothing to reproduce (copy, styling) asks it with the result. Never say tests pass that did not run: say so under **Not checked**. A single report that a promised `Then` is broken is this too: reproduce it, then fix it; `intake` is for several items, or when the person asks to file. Name the row or doc that covers the area, if one does, and that its tests still pass. A pull request lists the rows it keeps (`pr` mode) | The project's tests and CI; §0 of an agreed doc is never edited (the hook) |
| **small** | One new behaviour whose release-note line fits an existing doc's outcome, or a row's "so that", unchanged | `revise` that doc; with a map, `intake` files it as a scenario on that row. No new doc. A new rule a person must agree is a §0 change, confirmed by the human in `revise` | §0 is the human's words; `agreed` and `shipped` are typed by a human |
| **capability** | A new job with its own "so that": a new capability | `new`, drafted straight from the user's own words, asking once for only what is missing, at the repo's decision policy | Everything |
| **risky** | A protected category, or work across another team's system | `new` as written, at `spec` (the stricter policy only asks more), unless the user named another | Everything, and every decision is asked |
| **deferred** | The person's own words ask to build first: "ship it first", "hotfix …", "spike …", "promise it later", "no time for the paperwork". Never the agent's choice | Build it now; the promise work is owed, not skipped (§ Deferred) | Every decision in a protected category, asked; the tests there are; the hook on an agreed §0 |

The scripts read `feature` as an alias of `capability`; write `capability`.

## A tiny fix

A fix still starts with a failing test for the promise it restores, watched failing
before the fix. The row's verdict decides where that test is cited:

- **The row is `proven`** → cite the test on the row now. The promise broke while
  the row's tests passed, so the proof had a hole, and the new test is the evidence
  it lacked. The closing message says so.
- **The row is `under-proven` or `not-built`** → the test declares the row in the
  project's lightest form: the recipe's header declaration, or a comment naming the
  row. The citation goes under **Decided for you** as a follow-up for `reconcile`,
  whose probes find the declared test and cite it on that row.

No row covers the area → the test names the §0 rule or doc it restores. Either way
the verdict moves only by the recipe's rule, and a bigger row needs more tests,
never fewer.

A tiny ask that turns out to change what a row promises, or to touch a protected
category, stops there: say so, and size it again. A pull request checks the claim: `changed_rows.py
--size tiny` (or `--body`, with the block's `Size:` line) fails when the diff changes a
row's scenarios, a doc's §0 or §6, a migration or schema file, or a path the config's
`protectedPaths` lists.

## Deferred

Under pressure (a release, an incident) the person may want the code first and the
promise after. The size is theirs to give, in words, never the agent's to pick; a
spike on a throwaway branch needs none of this until the person keeps the code.

- **Build first.** No doc, no row, no scenario, no mode; no question but the session's
  first-command yes, and, in a protected category (money, data, security or access, a
  public contract), every decision in it, asked as a risky ask asks them: deferral waives
  the paperwork, never the decisions that are hard to undo. Run the tests there are; say under **Not checked**
  which did not run, and that no new test proves the change.
- **Write down what is owed.** The close out, and the pull request's block, carry
  `Size: deferred — owes: <each promise the change touched or made, in plain words>`:
  "a scenario on CAP-12 for a card saved before the migration, and its test". The block
  needs only **Why** and **Proof** then (the lint warns for the rest). Record the run with
  `session_report.py --record --size deferred`.
- **Pay it back.** `/promise reconcile` with no input lists what is owed
  (`scripts/deferred.py`: merged pull requests whose block says deferred and has no
  `Paid:` line). Paying one is a reconcile of that pull request, or `intake` or `new`
  when the change made a new promise: the rows, the tests, a mutation watched failing.
  Then its block gets `Paid: <the change that paid it>, <the rows>`, posted with
  `post_github_text.py`. A debt paid in part gets `Paid in part: …` and stays listed.

## The prototype door

Some people find the idea by building. "I built a prototype", "start from my prototype",
"promise this prototype", "lock in what I built": these ask for the second front door
(README § Two front doors). It is a first-class path, and it needs the person's own
words, so it is not `deferred`: nothing is skipped, only the order is different.

- **Ask in `new`.** Read the prototype first, to see what it does. Then interview for
  the human half as usual: the person says what must be true, and writes §0 in their
  own words. The prototype's behaviour is a source of questions, never of rules. The
  person signs off the doc; the agent never sets `agreed` or `shipped` (`arm` may set
  `building` as usual).
- **Mark the doc.** `new` writes a §8 row whose decision says the doc starts from a
  prototype, so a later `arm` or `reconcile` session can see it.
- **Protected categories are asked.** Money, security, contracts, data retention and the
  rest of framework § Decision policy still go to the person, even in code that exists.
- **Proof is a watched mutation, never a red run.** Code that already works makes a new
  test pass at once, so a red run shows nothing. Do not stub working code to force one.
  File each §6 line for existing behaviour as `modes/arm.md` step 0 says: arm lists
  them in one `Filed without red run: … — prototype` line. `reconcile` writes or finds
  the test at the `Then`'s altitude, breaks the code, watches the test fail, restores
  it, and only then writes that line's `Kill:` line and promotes the row. The doc can
  be shipped once every filed line has its `Kill:` line (framework § Lifecycle).
- **New behaviour in the same doc** is still armed red, as usual.

## How big a row is

A row is **one job an actor does, with its own "so that"**. The job's rules, limits,
permissions, undo, error paths and edge cases are its scenarios, not rows of their
own. Cases that differ only in their data are one scenario, its `given` naming them.
Write the one line a release note would carry for the change:

- **No line** (wording, styling, layout, a refactor, config, a dependency bump,
  test-only work) → no row and no scenario. A fix that restores a `then` already
  promised is no new scenario either: it starts with a failing test for that
  scenario, cited as § A tiny fix says (on a `proven` row now, else by `reconcile`).
- **A line about an existing row's job** → a scenario on that row, or nothing when a
  scenario already says it.
- **A line naming a new job, with a new "so that"** → a new row.

An outcome doc with one outcome usually files one to three rows; one with at most
five acceptance rows and one "so that" files one row. A job with more than five
scenarios continues in a chain: a child row with `parent`, the same "so that" split
by case, never a row per rule.

If the user explicitly chose the supported relaxed job trial, a row with
`grouping: job` keeps its stable identity beyond five cases. Each scenario
names its evidence citations, and strict reporting checks those links. Review
the boundary when a row becomes hard to scan; a count alone creates no new job.
Existing maps keep their current rules until that choice is made.

A bigger row needs more tests, never fewer. The evidence arrays are per lane, so one
passing test can make every scenario at its altitude look green; the verdict moves to
`proven` only when **every** scenario has its own test at its altitude, watched to
fail. A scenario whose `given` names several cases needs a test for each case that
behaves differently.

## The skill decides whether, the recipe decides how

**This skill decides whether anything is filed and at what size**: the size, the
relation (a scenario on a row, a new row, nothing), one row per job. **The project's
recipe decides how**: which files a row touches, the lockstep, the checks. Where a
recipe says otherwise on whether to file (a row for a refactor, a row per rule),
this file wins; a recipe with no row-size section needs none.

## Batch

A question whose answer does not change your next step waits for the end. Take the
**(Recommended)** option on anything reversible, keep working, and record what you
chose. A mode stops only at these, and each is one ask that gathers every question
due there:

1. the first configured command of a session (SKILL.md Phase 0);
2. deleting files, or committing on the default branch;
3. a mode's own checkpoint — `new`'s one question turn for the human half the ask
   left out, `intake`'s one approval table before Apply, `arm`'s red gate before
   `building`, `merge`'s survivor and deletions;
4. an ask with no outcome to promise yet (`new`).

A question the mode text asks in passing (an altitude, an unplaced row) goes in the
next of these, never on its own.

Everything else goes in one message at the end of the mode, in three parts:

- **Needs you** — what only a person can answer: a protected category, a §0 line, an
  open decision the policy leaves to them, a legacy doc's policy. They go on the
  surface `references/decision-sheet.md` picks — the question prompt for a few plain
  ones, the sheet for more — never as a bare list.
- **Decided for you** — one line each, with how to undo it: the owner, the docs home,
  the base branch, the test command, how rows were grouped, a verdict that moved by
  the rule, and every §8 agent decision.
- **Not checked** — what this environment could not run or read.

The person reads one message, not a string of stops. An objection to anything under
Decided for you is a one-line reply, and the agent undoes it.

Then record the run, a tiny one too, so `/promise retro` can count it:
`python3 "${CLAUDE_SKILL_DIR}/scripts/session_report.py" --record --size <size> --reason
"<the size's reason>" --mode <mode, or none> --stop <kind>` once for each stop above
(`first-command`, `delete-or-commit`, `checkpoint`, `no-outcome`), and `--needs-you`,
`--decided` and `--not-checked` with the item count of each part. It writes nothing:
the command, in the session's transcript, is the record.
