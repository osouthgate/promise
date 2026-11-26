Read before this: references/github-text.md · references/first-screen.md
Read at Gather the facts, not before: the issue the change closes, and its `<!-- promise:issue -->` block.
Phase 0 line: mode `pr` (say if inferred), framework source, docs home and its source, the base and head refs, the pull request (a number, or not yet opened), the issues it closes, whether a map is configured (orient's `mapUsable`), and whether the project is adopted.
Writes: the `<!-- promise:pr -->` block of one pull request's description — through the host's GitHub tool, or handed back as text when there is none. Never the map, an outcome doc or code.

# PR — tell a reviewer what changed and why, then point at the capabilities

A reviewer reads the issue, then the capabilities, then the code. This mode writes the
middle of that path for one pull request: what changes for people in a few plain
sentences, the rows the change moved with their verdicts, and one to three places in
the code to read first. A script gives the facts; the words stay short.

## Gather the facts

1. The refs: the pull request's base branch and its head. Not yet opened → the
   project's default branch and `HEAD`.
2. Run `python3 "${CLAUDE_SKILL_DIR}/scripts/changed_rows.py" --base <base> --head
   <head> --json` and keep the output in a scratch file; then the same with
   `--markdown` for the `<details>` block. Exit 2 → fix what it names (most often a
   ref to fetch) and run it again; never guess the row list.
3. The issue: `Closes #n` in the body, the branch name, or the commits. Read its body
   and its `<!-- promise:issue -->` block — the asks, their relations and rows. No
   issue → the "Why" says "No issue" and gives the reason in one sentence.
4. Each added or changed row, in full (`adapter.py row <id>`): its story, its `Then`s,
   its verdict. The `Then` is what a person sees; the people section is built from it.
5. What ran: the project's own checks for this change and their numbers, from this
   session. A check that did not run is named as not run.
6. A sibling map (orient's `sibling` is set, `references/config.md` §
   Without a map) → the rows are in another repository's map, which `changed_rows.py`
   does not see. Take the rows from the issue's block and `adapter.py find`, and read
   each with `adapter.py row`: it runs in the sibling's checkout. No checkout at
   `sibling.path` → say so under **Not checked**.
7. The pin: `python3 "${CLAUDE_SKILL_DIR}/scripts/pin_check.py"`. It changes no
   file and exits 0 when behind or offline; keep its lines. Exit 1 (pins that
   disagree, or a pin site it cannot read) is a finding for the close out.

## Write the block

In the shape `references/github-text.md` § The pull request block gives:

- **Where this is** — the report's `features` (the rows the change moved or touched),
  named as the map names them, one plain sentence each; then "Needed from you": what
  to read before merging, and who merges. `references/first-screen.md`. Use the spelling the project's map already uses (`feature`, or the alias `area`; `feature` in a new map), which orient warns about when the map or its reader keeps `areas`/`area`.
- **Words** — the product's own words this description uses that a reader from
  another project could not guess, from the map's `glossary`; "None." when there are
  none.
- **What changes for people** — one to three sentences, 60 words at most, no code.
  "Before, … Now, …" when behaviour changed. A change no person can see says what a
  person gets from it. Write it last, from the rows' `Then`s and the issue's words.
- **Why** — `Closes #n`, then one sentence of the problem in the issue's own words.
  Then the size the ask was given (`references/sizing.md`), and why: "Size: tiny —
  keeps CAP-12", "Size: small — a scenario on CAP-4". Built first under pressure →
  "Size: deferred — owes: <each promise touched or made>"; the block then needs only
  **Why** and **Proof**.
- **Capabilities** — every row the script reports as added, changed or removed, each
  linked, with its verdict before and after; rows with one story share a line.
  Touched rows share one line. Files no row names are listed, with the reason. More
  than 12 rows share a change → their count, and the few a reviewer should open. No
  map → one line saying so, then the parts of the product the change moves, each
  with its test. A sibling map → the sibling's rows the change keeps or extends, each
  with its id and the sibling's `repo`; nothing is filed locally, and a row that needs
  a change goes in the close out under **Needs you**: which row in which repo.
  Then **planned and done**: a row the issue named that the change leaves alone, or
  a row it moves that the issue never named, gets one line saying why.
- **Check these first** — one to three `path:line` items: where the behaviour changes,
  the test that proves it, and a risk if there is one. Read each line this run.
- **Proof** — the commands that ran and what they said, with numbers. The pin behind,
  or its section stale → one more bullet, `Not checked: <pin_check.py's lines>`: the
  change was judged at the pinned promise, not upstream's. Up to date → nothing.
- **`<details>`** — the script's `--markdown` output, as printed.

A verdict that moved up needs its evidence in the change: a cited test that ran and
passed at the altitude the row's `Then` claims (`references/altitude.md`). A row
the change moved to `proven` without one is a finding for the hand-back, not a line
to smooth over.

## Lint, then post

Write the whole description to a scratch file and run
`python3 "${CLAUDE_SKILL_DIR}/scripts/lint_github_text.py" --kind pr <that file>
--changed <the --json file>` (`--counts` shows the words against each budget). Fix
every error; fix or name each warning. Each changed `.md` file outside the outcome docs
(a review, a register) gets `lint_github_text.py --kind doc <file>`: a row id with no
meaning beside it, or a range of ids, is fixed in the change. Then run `changed_rows.py` with the same refs
and `--body <that file>`: exit 1 says a tiny size touches a promise or a protected
path; size it again, and fix the block. CI runs the same check where the Action's
`tiny-check` input is on (the workflow `adopt` writes turns it on). Then post
the description with the block replaced and text outside the markers unchanged:
`python3 "${CLAUDE_SKILL_DIR}/scripts/post_github_text.py" --kind pr --body-file <that
file> --number <n> --changed <the --json file>`, or, not yet opened, push the branch and
use `--new --title "…" --head <branch> --draft`. It lints again, posts only on a pass (through `gh`), and reads back what
GitHub stored: a difference it names (links wrapped in backticks, most often) is fixed and
posted again. No `gh` → post with the MCP tool (its hook lints the body too), then run
the script with `--verify <n>`. With no GitHub tool, hand the whole description back as text. A project with a pull
request template of its own: keep its sections outside the block.

After each push that changes the rows, run the script again and replace the block. A
reviewer reads the current state, not the first draft.

## Close out

The block as posted, the lint result, and anything the reader should know that the
block does not say: a verdict that moved without evidence, a planned row left out, a
check that did not run, a feature or a word the map lacks, and with a sibling map, which
row in which repo needs the change.
