Read before this: references/github-text.md · references/first-screen.md · references/altitude.md
Read at Match, not before: `modes/intake.md` § Match each item — this mode runs its steps 1–4, not its approval stop.
Phase 0 line: mode `issue` (say if inferred), framework source, docs home and its source, the issue (a number, a URL, or text not yet filed), how many asks it holds, whether a map is configured (orient's `mapUsable`), whether `map.issueTracker` is set, and whether the project is adopted.
Writes: the `<!-- promise:intro -->` and `<!-- promise:issue -->` blocks of one issue — through the host's GitHub tool, or handed back as text when there is none. Never the map, an outcome doc or code.

# Issue — check an ask against the capability map before anyone builds it

An issue is where work starts, so it is where the map is cheapest to read. This mode
finds the capabilities an ask touches, names the gap, and says how the build agent
proceeds — in a block a person can read on a phone, under a first screen that says
where in the product the issue is and what its words mean. It files nothing in the map:
that is `intake`'s job, or `new`'s, once a person has agreed the ask.

## Read the issue

- A number or a URL → read the issue and its comments with the host's GitHub tool
  (`gh issue view <n> --comments`, or a GitHub MCP tool), and the comments on each
  issue the block names: an answer there can change this route. Keep the body **byte for
  byte**: `gh issue view <n> --json body -q .body`, or the REST API's `body` field
  written to a file by a script — never retyped from a tool's JSON. A
  `<!-- promise:issue -->` block already there → this run replaces it; read it
  first, it is the last check. The same for a `<!-- promise:intro -->` block. A
  refresh that re-reads only what changed says so on its `Read:` line: "the rest as
  the last check read it".
- Text not yet filed → it becomes the body's "What we want", verbatim; the block goes
  below it.
- Overlap: search the repository's issues, open and closed, when the host can read
  them (`map.issueTracker` names the tracker; else the `origin` repository), by the
  ask in plain words and by any row id it names; and the project's ideas or research
  folders. A host that blocks search can still list the issues (open and closed): filter
  that list with a script. Ask: *would closing that issue, or that research, do this work?* For text
  not yet filed, yes → offer that issue, **(Recommended)**, instead of a new one. For
  a filed issue, name the overlap in the route.

Split the body into asks the way `intake` splits feedback: one ask for each distinct
thing a person would see. Keep each ask's own words for the item's lead; an asker who
wrote code (a route, a field) keeps it. The body text is the person's; it is read,
never rewritten.

## Match each ask

Run `modes/intake.md` § Match each item, steps 1–4: the scratch file, `adapter.py find
--query-file`, the top 3–5 rows read in full with `adapter.py row`, and the relation
table (`outcome_rows.py --search-file` only when there is no map, as there). Not its
approval stop: the relation here is a recommendation in the block, and a person
changes it by editing the issue.

`find` ranks by shared words, and an ask rarely uses a row's words. Run it twice —
the ask's own words, then only its nouns and any route or file it names — and search
the map's text for those nouns too (rows cite the files they are about). Read each
candidate row's verdict and its tests, not only its story. When the row the block
names was not ranked first by the first run, teach the map the ask's words as
`intake` does (`adapter.py learn`, with `--source issue:<owner>/<repo>#<n>`).
For the gap in the code today, start from `adapter.py code <id>` when `map.code` is
set: the files the row's cited tests import. Read those before a wide code search.

A sibling map (orient's `sibling` is set, `modes/intake.md` § Match each
item) → the rows the block names are the sibling's, each with its id and the
sibling's `repo`; nothing is filed locally. An EXTEND or NEW-ROW ask goes in the close
out under **Needs you**: which row in which repo needs the change. No `learn` or
`code` runs there. No checkout at `sibling.path` → match as with no map, and say so
under **Not checked**.

Also read, for each ask:

- the outcome docs that hold its rows (a row's doc is its `doc` field, else the doc
  whose text names its id; `changed_rows.py --link` prints both), and their §9
  questions — an ask that answers or reopens one says so;
- any research or design the issue links: the route starts from it. Research that is
  only on a branch is named with the branch;
- the code the ask is about, with `file:line` read this run (`intake`'s invariant 6:
  a report that something is broken is a claim until the code is read);
- the project's learnings, when it keeps them, for the files the route will touch: a
  trap someone already hit belongs in the route step, not in the build's first run.

A repository the ask needs that this run cannot read is named under "Gap" as not
read, with what it would have checked.

## Write the block

In the shape and budget `references/github-text.md` § The issue block gives: one item
per ask, each row linked with `changed_rows.py --head <default branch> --link <id>`,
its verdict as the map records it; the gap with `file:line`; the route in order, with
the doc and the row named (`/promise revise docs/promises/billing.md` to add a
scenario, not "update the docs"); the decisions, each with an owner. An answer to a
"Same as #87's decision" item answers that issue's decision too: tick it on both, each
with the link to the one comment, and name the other issue in the hand-back. The
builder's detail goes in `<details>`; 450 words outside it.

## Write the first screen

Last, when the rows are known, the intro block in the shape
`references/first-screen.md` gives:

- **Where this is**: the features of the rows the block names (each row's `feature`, named
  as the map file's top-level `features` names it; use the spelling the project's map already uses (`feature`, or the alias `area`; `feature` in a new map), which orient warns about when the map or its reader keeps `areas`/`area`), and the part of the product an ask
  with no row is about. One to five, one plain sentence each. Then "Needed from you":
  the decisions, counted and pointed at, or "nothing yet".
- **Words**: read the whole body, the asker's text first, as a reader from another
  project would. Each word of the product they could not guess gets its meaning, from
  the map's `glossary` when it has one. Variants of one word, and the members of a
  set, nest under it. A feature's name needs no entry.

A feature or a word the map lacks is still written here, and named in the close out for
the map.

## Lint, then post

Write the whole body to a scratch file: the intro, one blank line, the person's text
byte for byte, then the block. The separator before the block is one blank line: add
`\n\n`, or nothing when the body already ends with a blank line. Keep the body's own line endings (CRLF stays
CRLF). Run `python3 "${CLAUDE_SKILL_DIR}/scripts/lint_github_text.py" --kind issue
<that file>` (`--counts` shows the words against each budget while you trim). Fix
every error; a warning is fixed or said in the hand-back.

Then post with `python3 "${CLAUDE_SKILL_DIR}/scripts/post_github_text.py" --kind issue
--body-file <that file>` and `--number <n>` (the intro and the block replaced), or `--new
--title "…"`: it lints again, posts only on a pass, and reads back what GitHub stored. No
`gh` → the MCP update or create (its hook lints the body), then the script with `--verify
<n>`. Never a second block, never a change to text outside the markers; check that the
person's text is unchanged in what was read back. With no
GitHub tool, hand the whole body back as text.

A body the person edited since it was read → read it again before the write, and
replace only the block.

Many issues at once → a sub-agent for a few issues each, each writing in its own
scratch folder; read every block yourself before it is posted. Every sub-agent works
from the same promise commit: a change to this guidance waits until they hand back,
or their word counts and forms differ.

## Close out

For each issue: its title, its features, each ask's relation and rows, the route in one
line, the decisions it waits on, and the lint result; then the features and words the
map lacks, as entries a person can add to it. Name what this run could not check — a
row whose tests did not run here, a link it could not open.
