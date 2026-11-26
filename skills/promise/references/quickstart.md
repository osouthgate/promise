# Quickstart — the words, and the commands in order

*For any agent on its first run: Claude Code, Codex, Cursor, a chat bot. The mode
files hold the rules; this file holds the order. Where the two differ, the mode file
wins.*

`${CLAUDE_SKILL_DIR}` below is this skill's folder (`skills/promise` in the plugin, or
wherever `install_skill.py` put it). On a host that does not set it, put the real
path in its place. Every script takes `-h`.

## The words

| Word | Meaning |
|---|---|
| outcome doc | One document per capability, §0–§10, in `docsHome`. It is the design and the plan. |
| §0 | The doc's first block: outcome line, rules, how-we'll-know. The human's words; an agent never rewrites it, it appends numbered notes below. |
| status | The doc's `Status:` line, in four steps from `draft` to `shipped`. SKILL.md § Rules that hold in every mode says who may write each. |
| §6 row | One Given/When/Then acceptance line, `AT-n`, with an altitude. |
| altitude | What a `Then` is judged on: `data`, `response`, `perception`, `judgement` or `sibling` (`references/altitude.md`). |
| map | The project's capability map, optional: one row per user story (its id from the issue it came from, `CAP-i1890a`, or the older `CAP-n`), its scenarios, the tests cited as proof, and a verdict. |
| lane | The evidence array a scenario's altitude picks (`tests[]`, `e2eTests[]`, …), set in `map.lanes`. |
| verdict | A map row's proof: `not-built`, `under-proven` or `proven`. It moves only when a test at the `Then`'s altitude is watched failing, then passing. |
| bridge | The step in `arm` that files an agreed doc's §6 rows into the map. After it, §6 is a snapshot and the map is the source. |
| red gate | The commit of failing tests (and the stubs they import) made before any code. Its sha goes in the doc header as `Red gate: <sha> <YYYY-MM-DD>`. |
| backfill | Mapping observed behaviour inside the chosen product or pilot boundary, with rows marked `origin: backfill`. |
| decision sheet | How decisions reach the human: `references/decision-sheet.md`. |
| decision policy | The doc's `Decision policy:` line, `fast`, `auto` or `spec`, from the config's `decisionPolicy` (set once by a human, `auto` by default): which decisions the agent asks and which it records in §8 (outcome-framework.md § Decision policy). |

## First: orient

```
python3 "${CLAUDE_SKILL_DIR}/scripts/orient.py"
```

One JSON object: the docs home, the config, whether a map is usable (`mapUsable`),
the test runners it found and how each writes JUnit (`testRunners`), whether the
project is adopted, and warnings. Read `warnings` first: each names its fix.

## A new project

Unsure where to begin? Ask to get started with Promise. `modes/onboard.md`
uses the context you have, helps choose one user job and carries the answers
to the existing mode. For an established product, its selected pilot follows
`references/scoped-backfill.md`. The preview names both its boundary and its gaps.

1. **Adopt.** `python3 "${CLAUDE_SKILL_DIR}/scripts/adopt.py" --dry-run --docs-home docs/designs --policy <choice>`,
   with the policy asked once (`modes/adopt.md` § Ask the decision policy), show the diff, then run it without `--dry-run` on the user's yes. It writes the
   config (with `commands` for type check, test and lint, `null` until set) and the
   promise section in CLAUDE.md or AGENTS.md (`modes/adopt.md`).
2. **The first doc.** Size the ask first (`references/sizing.md`): a tiny one needs no
   doc. Otherwise take the config's `decisionPolicy`, ask once for what the ask left
   out of the human half (`modes/new.md`), then
   `python3 "${CLAUDE_SKILL_DIR}/scripts/render_outcome.py" --title "<Capability>" --owner "<name>" --policy <choice> --create-docs-home`
   and fill it. A new repo has no code, so §5 says so: "no code yet at `<sha>`".
3. **Lint.** `python3 "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py" <doc>` until it
   prints `0 errors`. Open questions go through the decision sheet, never a chat list.
4. **Arm the doc** when its human says it is ready (`modes/arm.md` has the precondition):
   - a work branch;
   - the starter map, if the user wants one:
     `python3 "${CLAUDE_SKILL_DIR}/scripts/start_map.py" --dry-run`, then without the flag;
   - a test command: `commands.test` is `null` → take the one `testRunners` names, and
     for plain unittest the JUnit route `scripts/junit_unittest.py`;
   - failing tests and the stubs they import, committed as the red gate;
   - the `Red run:` line in §6, the `Red gate:` line in the header, and `building` on
     the human's yes.
5. **Check.** `python3 "${CLAUDE_SKILL_DIR}/scripts/check.py" --no-map` (or with the map
   and a JUnit run) is what CI runs.

## A prototype first

The person built something to find the idea and now wants to lock it in
(`references/sizing.md` § The prototype door). The order is: read the prototype; the
person writes §0 and agrees the doc (`modes/new.md`); `arm` files lines for behaviour
that exists without a red run (`modes/arm.md` step 0); `reconcile` writes or finds each
test, watches it fail under a mutation, and promotes the row. Protected-category
decisions are still asked. Never stub working code to get a red run.

## An existing repo

1. **Orient and adopt** as above. `docsHomeForeignDocs` counts design docs already
   there; pick a docs home of promise's own when it is not zero.
2. **Start the map**: `start_map.py`. Set `map.junit` (where the tests write JUnit;
   `testRunners[].junit` says how) and `map.surfaces` (a command that prints the
   entry points, one per line) on the user's yes (`modes/backfill.md`).
3. **Run the tests with JUnit**, then see what has no home:
   `python3 "${CLAUDE_SKILL_DIR}/scripts/map_report.py" --map <map.json> --junit <run> --orphans --surfaces <list>`.
4. **Backfill, one feature at a time** (`modes/backfill.md`): rows for tests and entry
   points, `python3 <map dir>/capability_find.py --next-id --from issue:<the backfill's issue>`
   for each id (`CAP-i<n>a`, `CAP-i<n>b`: no other branch can hold them), scenario ids
   `<row id>.<m>`, then `capability_find.py --check`. A second agent or the human
   verifies the rows; the writer never verifies its own.
5. **Legacy design docs** move into outcome docs at `draft`, §0 pending a human's
   confirmation (`examples/backfill-moved.md`), and the legacy file is deleted.
6. **Check**: `check.py` with the map; `map_report.py --strict` shows a verdict
   recorded above what the run shows.

From then on, new work goes through `/promise` like a new project's.

## The backfill verifier

A writer never checks its own rows (`modes/backfill.md`, invariant 5). The writer
leaves one scratch file per feature, `backfill-<feature>.json`:

```json
{"feature": "<id>", "commit": "<sha the rows were read at>", "run": "<JUnit path>",
 "surfaces": "<entry-point list path>",
 "rows": [ <each candidate row, in the map's own shape> ],
 "leftOut": [ {"test": "<file>::<name>", "reason": "<one line>", "date": "YYYY-MM-DD"} ],
 "movedDocs": [ "<outcome doc path>" ]}
```

Start the verifier (a subagent, a second session, or a person) with this prompt:

> Verify the candidate rows in `backfill-<feature>.json` against the code at `<commit>`,
> the JUnit run and the entry-point list it names. Apply the checklist in
> `modes/backfill.md` § Pass 2 to every row, every left-out entry and every moved
> doc. Change nothing. Report one line per finding: `<row id or path>: <check>:
> <what is wrong>`, then `verified: <n> rows, <m> findings`.

On a host that cannot start a second agent, give the human the same file and
checklist, and wait for their findings. The writer fixes each finding, and the
verifier checks again before any row is filed.

## Decisions for the human

1. Collect: `decisions.py sheet --asks-skeleton <asks.json>`, fill it in, then
   `python3 "${CLAUDE_SKILL_DIR}/scripts/decisions.py" sheet --asks <asks.json> --json`.
   A sheet is one round of at most 12 items, BLOCKING first; the rest come in later
   rounds (`--only <id>,<id>` for just the items asked for).
2. Pick the surface by the sheet's top-level `surface` and the host
   (`references/decision-sheet.md` §2). `rich` in Claude, however many items: the `--out`
   page published as an Artifact with `capabilities: {"db": {}}`. Elsewhere an HTML
   canvas, the host's question prompt, or, in a chat that shows only text, the `--chat`
   message, with `--comment` posted to the issue. Never the sheet's `.json` or `.md` files.
3. The human answers. A short reply (`all recommended`, `1a 3c - note`) is applied as
   it is: `decisions.py apply --reply <file> --sheet <comment or sheet JSON> --by "<name>"`.
   Other answers go in as `promise-answers` JSON: `decisions.py apply <answers>`.
4. Say what was written where, and what is still unanswered. The agent's own decisions
   show as "Decided for you"; an **Ask me instead** on one becomes a §9 question.

## Hosts where the skill never loads

Some agents (a Cursor cloud agent, a chat bot) never load `SKILL.md`. They see only
the promise section in AGENTS.md or CLAUDE.md, and whatever the project pins.

- **Install**: pin the plugin repo in the project (a submodule, a vendored copy, or a
  `run.sh` that fetches one commit), and run its scripts from there. Or
  `python3 "${CLAUDE_SKILL_DIR}/scripts/install_skill.py"` links the skill into
  `.agents/skills`, `.codex/skills` or `.cursor/skills` (`README.md` § Codex, Cursor
  and other agents).
- **Read** the promise section first, then this file. There is no `/promise` command
  and no `AskUserQuestion`: run the scripts, and follow the mode file by name.
- **Scripts**: the config's `run` (orient's `run`, named in the promise section) is how
  this project runs them, such as a wrapper pinned to one promise commit. Use it; never
  rebuild a script from the promise repository's source.
- **Decisions**: the host's own question tool if it has one; else the `--chat` message
  as the reply text, the `--comment` on the issue, and `apply --reply` on the answer.
- **Keep the section current**: orient warns when the promise section was written from
  an older template; `adopt.py` refreshes it in place.
- **Hooks**: with no plugin hook, `install_skill.py --project . --git-hook` puts the §0 check in
  front of every commit, and the GitHub Action does the same for pull requests.
