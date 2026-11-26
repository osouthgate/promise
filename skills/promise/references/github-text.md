# GitHub text — issues and pull requests a person can review

*Read by `modes/issue.md` and `modes/pr.md`, with `references/first-screen.md` for the part a reader sees first.
Templates: `templates/github/ISSUE_TEMPLATE/capability.md`, `templates/github/pull_request_template.md`.
`scripts/lint_github_text.py` checks what a script can of the rules below; `scripts/post_github_text.py` posts only what passes.*

## The reader's path

A reviewer reads a change in three steps: the **issue** says what a person wanted and
why; the **capabilities** say which promises the change adds, changes or touches, and
their verdict; the **code** delivers them. Each step points at the next — the issue
names rows, the pull request names the same rows and the issue, each row links to its
tests — so the reviewer never has to rebuild the chain from the diff. Before all
three, the **first screen** says which parts of the product this is about, what the
reader must do, and what its words mean (`references/first-screen.md`).

The text is short on purpose. A reviewer who meets a wall of text asks a model to read
it, and then no person has reviewed the change. Say what changed and why in a few
plain sentences; put the facts a script can give (the row diff) in a `<details>` block;
point at one to three places in the code. Everything else is in the links.

## Plain words

The rules come from ASD-STE100 (Simplified Technical English), made smaller:

- One idea in each sentence. At most 20 words in "What changes for people", 25 in
  the other prose.
- Say who does what, in the active voice: "Team admins can no longer see a
  client's calendar link", not "the calendar link is no longer exposed". Name a
  person by name or role, never by a guessed pronoun.
- Use words a 12-year-old knows, and the same word for the same thing each time —
  the words the map's stories use for people (client, admin, visitor).
- Say what a person sees or can do, not how the code does it. "Before, … Now, …" is
  often the clearest shape.
- A number is better than an adjective: "one request, not sixteen".
- No code in the people section: no paths, routes, table, field or function names,
  and no row ids. Those go under "Capabilities" and "Check these first".

## The block, and who owns the rest

`/promise` writes only between its markers: `promise:intro` at the top of an issue
and `promise:issue` below the asker's words, `promise:pr` in a pull request, each as
`<!-- … -->` and `<!-- /… -->`. Text outside them is the person's own and never
changes: the asker's words in an issue are its §0. A second run replaces each block,
whole, and never adds a second.

## The issue block

```markdown
<!-- promise:issue -->
## Capability check

Read: <the outcome docs, research and learnings this check read, or "the map only">.

- **<the ask, in a few words>.** <RELATION> [<row id>](<row link>) (<verdict>): <what
  the row promises, in plain words>. <what this ask adds, or where it breaks the row>.

## Gap

<What the product does today, with path:line read this run, and what the asks need
that it does not do. One or two sentences for each ask with a gap.>

## How to build it

1. <the /promise steps for the relation, below, with the doc and the row named>

## Decisions needed

- [ ] <a question only a person can answer> Recommended: <an answer>, because <one reason>. (owner: <name>)
<!-- /promise:issue -->
```

- **Read:** what this run read, not an earlier check's list; another repository's
  file as `repo:path`. No words from the checking itself ("round 1", "worker").
- **One item for each ask**, starting after its bold lead with its relation. More than
  about six asks → asks with the same relation share an item (the DECISIONs with no
  row; the sibling rows for one repository). Each ask's detail, and a decision's
  background, go in `<details><summary>Each ask in full</summary>` after the sections.
- **Every row is linked** to its line in the map, with its verdict beside it as the
  map records it (the lint checks this). `changed_rows.py --head <default branch> --link
  <id>` prints the link: a permalink at the commit it ran on, so its line number stays
  right when the map moves. A row this pull request moves: `--head <its branch>`, with
  the verdict the branch records. A stored body whose links came back wrapped in
  backticks (`post_github_text.py` says so): link at a tag or branch instead; the line may drift. Name a scenario as `<row> S2`; name an acceptance row with
  its doc (`billing AT-4`), because AT ids repeat across docs.
- **Two readings** → the **(Recommended)** relation first, then the other with one
  reason: `EXTEND (Recommended) [CAP-4](…); or NEW-ROW, if it serves another "so that"`.
  A fifth onboarding step serves the onboarding row's "so that": EXTEND, a scenario on it,
  with NEW-ROW as the other reading only when the step has a purpose of its own. A build
  that waits on a yes is DECISION, with "If yes: …" in the route.
- **NEW-ROW** names the closest rows and why each stops short: `NEW-ROW, closest
  [CAP-13](…) (under-proven): it sends the brief, not a digest`. Another issue files
  it → `NEW-ROW, filed in #90`.
- **Gap** keeps to what is true today, with `path:line`. Lines the issue cites that
  have moved, or a branch or pull request it names that has merged or closed, get one
  sentence with the current state; the asker's text is not changed.
- **How to build it** is in order: `Needs #87 first`; `Built in #88`; research only on
  a branch is merged first, and the step names the branch; a learning that changes a
  step is named in it. Work can go before a row that waits on a decision when it
  changes nothing a caller sees: its guard tests go in `leftOut`, the decision as the
  reason, until the row is filed when the decision lands; then they are cited on it.
- **Decisions needed** says "None." when there are none; a DECISION ask always has
  one. Each has an owner and a **Recommended** answer with its reason, or `No
  recommendation: <what only the owner can weigh>`. A question a doc holds (§9, a
  research doc's open questions) is cited: `- [ ] Answer modules.md Q4: <a few
  words>. Recommended: …`; one another issue asks: `- [ ] Same as #87's decision: <a
  few words>`. An answered one is ticked, on one line: `- [x] <the question> Answered
  by [<name>, <date>](<comment link>): <the answer>.`; the owner's own words go in
  "Each ask in full". More than four → those the first step waits on stay; the rest go
  in `<details><summary>Later decisions</summary>`, each with its owner.
- **Budget:** 450 words outside `<details>` (a link counts as its text, a path as
  one word, headings not at all); about 40 for each ask's item.
- **Last**, `<details><summary>What the map words mean</summary>`: a *row* is one
  promise and the tests that prove it; *proven*, a test at the promise's level passes
  and was seen to fail on broken code; *under-proven*, tests pass below that level or
  were never seen to fail; *not-built*, no test yet; each relation used, in one line.

### Relation → how to build it

The relations are `modes/intake.md`'s:

| Relation | How to build it |
|---|---|
| EXISTING-SCENARIO | Nothing to build: a row already promises it and the product does it. Close the issue with the row and its tests. A verdict short of `proven` → `/promise reconcile` the row first |
| DEFECT | Reproduce it, add a red test for the row's scenario, fix the code, then `/promise reconcile` the row. No doc change |
| EXTEND | The row's doc → `/promise revise` it to add the scenario; a human agrees it; `/promise arm`. No doc → `/promise intake` files the scenario on the row once a person approves the match. Then build, and `/promise reconcile` |
| NEW-ROW | One promise → `/promise intake` files the row once a person approves the match (with a map; without one, a doc). A capability with rules of its own to agree → `/promise new`, or `revise` the doc whose outcome it serves; a human agrees it; `/promise arm`. Then build, and `/promise reconcile` |
| SURFACE | A screen, wording or colour change only: build it and name the row that owns the screen. No map change |
| DECISION | Nothing to build yet. The owner answers under "Decisions needed", or in the doc's §9. When the route after each answer is clear, give it: "If yes: `/promise revise` …". Once it is answered, the next run gives the ask the relation the answer leads to: a row's `Then` that changes is EXTEND, a new promise is NEW-ROW |
| KEEPS | The ask changes how, not what: a refactor, a cost or speed fix a caller does not see. Build it, and name the rows whose scenarios must still hold; their tests are the proof, and the pull request names them as touched. A limit a person can see (a page size, a timeout) is a promise: EXTEND, a scenario on the row whose job it limits. A guard test the work adds is cited in the row's lane for the scenario it guards, so the row is `changed`; it adds no scenario. A kept row whose tests do not run the changed code (fixture-only tests for a change on the database path) proves nothing here: the route adds that test, and the ask is NEW-ROW or a `/promise reconcile` of the kept row |

**A row's doc** is its `doc` field; a backfilled row has none, and its doc is the outcome doc whose text
names the row id (`changed_rows.py --link` prints both). Two docs name it → the one whose §6 holds it.
A doc that owns the behaviour in words but never names the row is still its doc: the revise adds the id.

**Code in another repository.** The build happens there; the rows stay in this map when the project
keeps its sibling repositories' promises here (the adopt notes say so), and cite that repository's
tests. The route names the repository.

**Research first.** Research or a design the ask already has is named in the route:
`/promise new` or `revise` moves that text into an outcome doc, not a second one.

## The pull request block

```markdown
<!-- promise:pr -->
## Where this is

<The features of the rows the change moved, one bullet each, then "Needed from you:".>

## Words

<The product's own words the text uses, one bullet each, or "None.">

## What changes for people

<One to three sentences, 60 words at most, plain words. Before, … Now, …>

## Why

Closes #<n>. <One sentence: the problem, in the issue's own words.>

Size: <tiny, small, capability, risky or deferred> — <its reason; for tiny, the rows it keeps; for deferred, "owes: …">.

## Capabilities

- [<row id>](<link>) new: <what it promises, plain words>. Verdict: <verdict>.
- [<row id>](<link>), [<row id>](<link>) changed: <what moved>. Verdict: <before> → <after>.
- Touched, verdicts unchanged: <row ids>.
- No row names: <files>, because <reason>.

## Check these first

1. `<path:line>`: <why a reviewer reads this first>

## Proof

- <command>: <what it said>

<details><summary>Full capability diff</summary>

<changed_rows.py --markdown, as printed>

</details>
<!-- /promise:pr -->
```

- **Where this is** and **Words** follow `references/first-screen.md`; the features
  start from `changed_rows.py --json`'s `features`.
- **What changes for people** comes from the issue's ask and the rows' `Then`s, told
  as what a person sees. A change nobody can see ("the auth check reads one column,
  not the whole profile") says what a person gets from it ("pages load the same;
  the database sends less data, so the monthly limit lasts longer").
- **Capabilities** names every row `changed_rows.py` reports as added, changed or
  removed, each on a line with its verdict before and after; rows with the same story
  share a line. Touched rows (a cited test or a named file changed, the row did not)
  share one line. Files no row names are listed, with the reason — or the row that
  should name them. More than 12 rows share a change → give their count ("192 rows
  added") and the few a reviewer should open; the full list is in `<details>`. A KEEPS
  change names the rows it keeps as touched, with their tests' result. A project with
  no map says so in one line, then names the parts of the product the change moves
  (a command, a page, a mode) as a reader would name them, each with the test that
  covers it — not a list of every file.
- **Size** is the ask's size (`references/sizing.md`), so a reviewer sees the claim.
- **Planned and done.** Compare the issue's rows with the change's. A row the issue
  named that the change leaves alone, or a row the change moves that the issue never
  named, gets one line saying why.
- **Check these first** is where a person's eyes are worth most: the line where the
  behaviour changes, the test that proves it, and a risk if there is one.
- **Proof** is what ran, with numbers: tests passed and skipped, the promise check,
  anything that could not run and why.

## What the lint checks

`scripts/lint_github_text.py --kind issue|pr <body>` (`--changed` with the `changed_rows.py
--json` file for a pull request) checks the markers, sections and budgets, code words, links,
relations, routes, owners, rows and verdicts, the size, the first screen, and that no row id
stands alone (`ID_BARE`) or sits in a range (`ID_RANGE`); `--kind doc <file>` runs the row-id
rules alone on any Markdown file. `changed_rows.py --body <body>` fails a tiny size that changes
a promise. No lint judges a sentence true, plain or kind: read it as the reviewer will, on a phone.
