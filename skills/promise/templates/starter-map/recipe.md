# Adding or extending a row — the recipe for this map

This is the file `map.recipe` points at. The promise modes read it for the
mechanics of this project's map and never restate them: which files a row
touches, what lockstep means here, what a citation looks like, and which lane a
`Then` lands in. The map is `{dir}/map.json`; its only reader is
`{dir}/capability_find.py`. Both started as the promise skill's starter map
(`scripts/start_map.py`) and are this project's own files now: change them
here, in this file first, when the project outgrows them.

Every command below runs from the project root. `${CLAUDE_SKILL_DIR}` is the promise
skill's folder; outside Claude Code, put the path where the project installed or
pinned the skill in its place.

## Why keep a map

One row per promise the product makes, each with the tests that prove it and an
honest verdict, is the map of the platform: what it promises, and how much of
that is proven today. Outcome docs make promises one capability at a time; the
map is where they add up.

## What a row is

One row is one user story plus one to five Given/When/Then scenarios, four
evidence arrays, and a verdict. A row's id comes from the work it came from, so rows of
different issues can never take the same one: `CAP-`, then `i<n>` for an issue, `p<n>` for a
pull request with no issue, or a Linear issue's own key (`linear:ENG-421` gives
`CAP-ENG-421a`, since Linear numbers each team apart), then letters for each row of that
item (`CAP-i1890a`, `CAP-i1890b`, … `CAP-i1890aa`). Every id starts `CAP-`, so
`grep -rn 'CAP-'` finds them all. `python3 {dir}/capability_find.py --next-id --from
issue:1890` prints the next free one, on no branch git knows yet. A backfill numbers its
rows under the backfill's own issue or pull request. With no tracker, `--next-id` alone
gives the counter form, `CAP-<n>`. Rows keep the id they were given; old `CAP-<n>`
rows are never renumbered. Ids are append-only.
In a merge conflict in `map.json`, keep every side's rows, give a clashing row a new id
from `--next-id --from` its own issue (the counter `--next-id` only on a map with no
tracker), and run `--check`. On a merge commit it names any row or `leftOut`
entry the merge lost, and any id both sides gave to different rows. A row dropped on
purpose (a duplicate of another, or one folded into another as its scenarios) goes in the top-level `retired` list, as `{"id",
"reason", "date"}`, and its number is never given out again. When its id lives on in
the row that was kept, use `{"story", "reason", "date"}` instead. A scenario that came from an
outcome doc keeps the doc's `AT-n` id in its `at` field as an alias, so the doc's
§0 tags and the map agree without either copying the other.

### How big a row is

A row is one job an actor does, with its own "so that"; its rules, limits and edge
cases are its scenarios. The full rule, with the release-note test that says whether
anything is filed at all, is the promise skill's, not this file's:
`${CLAUDE_SKILL_DIR}/references/sizing.md` § How big a row is. The skill decides whether
anything is filed and at what size; this file decides how. A bigger row needs more
tests, never fewer: the verdict moves to `proven` only when every scenario has its own
test at its altitude (§ Shipped work).

| Field | Meaning |
|---|---|
| `story` | The promise at story grain — one job, one sentence a person can disagree with, with its "so that" (the skill's `references/sizing.md` § How big a row is). |
| `title` | Optional, one line — the row in the words a person asks with ("mute a channel"), not the engineer's. `find` ranks on it; `--check` warns about a row with none. |
| `asks` | Optional, at most five `{"text", "source", "date"}` — the words a person, an issue or a pull request used when `find` missed the row; `source` is `person`, `issue:<owner>/<repo>#<n>` or `pr:<owner>/<repo>#<n>`. Added by `capability_find.py learn`, never by hand from an agent's synonyms. |
| `refs` | Optional — the issues and pull requests about the row, each `{"repo": "<owner>/<name>", "kind": "issue" \| "pr", "number": <n>}`: identifiers only, never a title or a state. `capability_find.py refs sync` adds them from merged pull requests' promise blocks. |
| `doc` | The outcome doc that made the promise, or `null` for a row filed from feedback or backfilled. |
| `scenarios[]` | `id` (`<row id>.<m>`, such as `CAP-i1890a.1`: the row's id, a dot, the scenario's number in the row, from 1), `at` (the doc's AT alias or `null`), `given`, `when`, `then`, `altitude`. An outcome doc's §6 copies `given`, `when` and `then` word for word, so a `<word>` in them sits in a code span (`` `mute <channel>` ``), which the doc lint accepts; `--check` refuses one outside. |
| `tests[]`, `e2eTests[]`, `evalTests[]`, `siblingTests[]` | Citations, one string each: `<test file>::<test name>`. |
| `verdict` | `not-built`, `under-proven` or `proven`. |
| `servicePolicyRefs` | Optional — ids from the map's project-level `servicePolicies`. Shared quantitative or qualitative service promises, with separate evidence per capability; see the promise skill's `references/service-targets.md`. |
| `parent` | Optional — the id of the row this one continues when a story outgrew five scenarios (a chain). |
| `aliases` | Optional — ids the row had in an older register (a journey id such as `J4`); a query matches them like the row's own text. |
| `origin` | Optional — `doc`, `intake` or `backfill`. A backfill row records what the code does today: it carries `origin: backfill` and `doc: null` until an outcome doc promises it. |
| `surfaces` | Optional — the entry points the row's behaviour enters through, in the project's own notation (`GET /me`, `page /settings`); `map_report.py --surfaces` lists every entry point no row names. |
| `feature` | Optional — the id of the part of the product the row belongs to, from the map's top-level `features`; a query matches the feature's name. the alias `area` means the same; a row with both is an error. |

A test left without a row on purpose goes in the map's top-level `leftOut` list, one `{"test": "<test file>::<test name>", "reason": "<one line>", "date": "YYYY-MM-DD"}` per test: `map_report.py` then does not count it as a test with no row, and `--check` validates the shape. An entry names one test by its exact title, never a describe block, a file or a `%s` pattern; one with no reason or no date, or naming a test a row also cites, hides nothing, and `map_report.py --fail-on-orphans` fails on it, on a left-out test that fails, and on one no longer in the run.

Optional top-level `servicePolicies` define each shared service promise once.
Rows refer to its id through `servicePolicyRefs`; a policy definition alone gives
no capability coverage. `service_report.py` validates these separately from test
proof. Existing maps need no policies and remain unconfigured for service assurance.

Two more top-level lists serve a person who reads an issue or a pull request after days away: they open with the features it touches and the words it uses (the promise skill's `references/first-screen.md`).

- `features` — the parts of the product (the alias key `areas` means the same; a map with both is an error), each `{"id": "<kebab-case>", "name": "<what a person calls it>", "plain": "<one sentence a newcomer understands>"}`, with an optional `doc` (the outcome doc for that part). A row's `feature` names one. `python3 {dir}/capability_find.py --features` lists them with their row counts, rows with no feature under a null id; `--feature <id>` prints a feature's rows (`--areas` and `--area` still work).
- `glossary` — the product's own words, each `{"term": "<word>", "plain": "<one sentence>", "aliases": ["<other spellings>"]}`; `--glossary` prints it. A word belongs to one entry. Add a word the first time an issue or a pull request has to explain it.

`--check` validates both lists, and refuses a row's `feature` that names no feature. A row with no `feature` is allowed, so a map can take its features a few rows at a time.

## Finding a row

`python3 {dir}/capability_find.py "<words>"` ranks rows with BM25: stopwords never
count, "muting" meets "mute", and a row's `title` weighs like its story. Each hit
says why it ranked. To see whether `find` works on this map, keep
`{dir}/find-eval.json`: the titles of real pull requests and issues, each linked to
the one row it is about, as `{"cases": [{"text": "<title>", "row": "CAP-<n>"}]}`.
`python3 {dir}/capability_find.py --eval` prints how often the row came first and in
the first five. Add a case when a work item names one row; never a row's own words.

When `find` missed a row, the map learns the words it missed by:

```
python3 {dir}/capability_find.py learn --query-file <file with the words> --row CAP-<n> --source <person | issue:<owner>/<repo>#<n> | pr:<owner>/<repo>#<n>>
```

It adds nothing when the row already ranks first, refuses an email address or a
handle, skips a near-duplicate, and keeps the ask only when the row then ranks in the
top three. A row holds five asks; the oldest goes out first. `--check` warns about an
ask conflict (an ask that now finds another row first): split the rows, or retitle
one.

`python3 {dir}/capability_find.py --code CAP-<n>` prints where a row's behaviour
lives: the local files its cited tests import (Python and JS/TS, one step). Read
those before searching the whole tree.

## The lockstep rule

A row and the thing that promises it move together, in this order, in one
commit:

1. The outcome doc's §6 row exists and its `Then` is final — the map copies the
   `Then` text verbatim, so `bridge_validate.py` can find it again later.
2. `python3 {dir}/capability_find.py --next-id --fetch --from issue:<n>` for the id (the
   issue the work comes from; `pr:<n>` when there is none, a draft opened first if need
   be). It skips every id another branch holds. Two branches for the same issue can
   still take the same letters before either pushes, so push the new row soon after;
   `--check` catches a clash at the merge. Never reuse a deleted id.
3. Append the row to `{dir}/map.json` with a `title` in the words a person asks with, its `feature` (when the map has `features`), every
   scenario, all four evidence arrays (empty when nothing is cited yet) and `"verdict": "not-built"`.
4. Write the id into the doc's `Row` column for every §6 line the row covers, and
   add the snapshot line under the table.
5. `python3 {dir}/capability_find.py --check`, then `bridge_validate.py` on the doc.

Nothing lands out of order, and step 5 reads both directions: a row whose `doc`
names a file with no §6 line citing it fails `--check`, and a `Row` cell citing an
id the map does not have fails `bridge_validate.py` (`ROW_NOT_FOUND`); a map `Then`
that no longer matches the doc's snapshot is reported there as `THEN_NOT_IN_MAP`.

## Routing table — what a piece of feedback becomes

| The feedback is… | It becomes… |
|---|---|
| no release-note line: wording, styling, a refactor, config | no new row or scenario; the rows it touches keep their tests passing |
| a promised `then` the product breaks | no new scenario: a failing test for that scenario, then the fix; the test is cited in its row's lane now when the row is `proven`, else declared on the row and cited by `reconcile` (`references/sizing.md` § A tiny fix) |
| a case an existing scenario already covers | no map change; cite the row in the reply |
| a new case under an existing story — a rule, a limit, a permission, an undo or an error path of its job | a new scenario appended to that row (a row keeps at most five; a sixth means a new row with `parent` naming this one) |
| a story no row makes | a new row, filed through the lockstep rule above, with `doc` pointing at the outcome doc that promises it |
| a decision the story needs first | a §9 question in the owning doc, not a row |

## Lane table — which array a `Then` is cited in

| The `Then` asserts on | Altitude | Array | What counts as a citation |
|---|---|---|---|
| a stored fact | `data` | `tests[]` | a test calling the query or function directly |
| what a request returns | `response` | `tests[]` | a test against the real handler |
| what a person sees, is told, or lands on | `perception` | `e2eTests[]` | a test driving the real rendered surface |
| whether a model chose well | `judgement` | `evalTests[]` | a scored suite run through a judge |
| behaviour that lives in another repo | `sibling` | `siblingTests[]` | that repo's own test, by path |

A citation in the wrong array is real evidence at the wrong altitude: it stays
in the map and the verdict does not move.

## Verification block

Run, in order, before calling anything done:

```
python3 {dir}/capability_find.py --check
python3 "${CLAUDE_SKILL_DIR}/scripts/bridge_validate.py" <the outcome doc>
```

When service policies are present, run
`python3 "${CLAUDE_SKILL_DIR}/scripts/service_report.py" --map {dir}/map.json --policies-only`.
This validates each shared policy once and checks refs, with a bounded summary;
it does not assess service evidence or emit every capability/policy pair.
For available live evidence, run the report with `--row <id>` for each touched
capability (repeatable), `--observations <export.json> --strict`. Never use
`--now`/`--replay` for production reconciliation. Missing/stale evidence stays
unchecked. Keep dated service observations separate from functional `verdict`.

## Shipped work — the mirror direction

Code landed and a test now proves a scenario:

1. Find the row (`python3 {dir}/capability_find.py "<words from the story>"`) and the
   scenario the test asserts on.
2. Cite the test in the array the scenario's `altitude` picks — never in the
   array the test was convenient to write for.
3. Move `verdict` to `proven` only when every scenario in the row has a citation
   at its own altitude and each citation has been watched to fail under a
   mutation of the production behaviour. One scenario short, or one citation at
   a lower altitude, is `under-proven`.
4. `python3 {dir}/capability_find.py --check`.
