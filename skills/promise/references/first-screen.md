# The first screen — where this is, and what its words mean

*Read by `modes/issue.md` and `modes/pr.md`, beside `references/github-text.md`.
`scripts/lint_github_text.py` checks what a script can check of it.*

## Who reads it

Write for a reader who comes back to an issue or a pull request after a day or two
away, from other work: often another project, with other tools and other words. They
have a minute. Before the ask, the rows or the code, the first screen tells them three
things: which parts of the product this is about, what they must do, and what the
product's own words mean. A reader who must rebuild that from the body puts it off,
or asks a model to read it for them.

The text describes the product and the work, never the reader.

## Where it goes

- **Issue**: its own block, `<!-- promise:intro -->` … `<!-- /promise:intro -->`, at
  the very top of the body, above the asker's words. A second run replaces it, whole.
  The asker's text is still never changed: the intro only sits above it.
- **Pull request**: the first two sections of the `<!-- promise:pr -->` block.

## The shape

```markdown
## Where this is

This <issue|change> is about <n> parts of the product:

- **<Feature name>**: <one plain sentence: what this part does, and for whom>.

**Needed from you:** <what the reader must do, or "nothing yet">.

## Words

- **<Term>**: <what it means, in one or two plain sentences>.
  - **<Term 1, a variant>**: <what this variant means>.
```

- **Features**: one to five, one bullet each, named as the map names them. A feature the
  map lacks still gets a bullet whose sentence says it is "not yet in the map", and
  the hand-back names it for the map. The sentence says what the part does for a
  person, not where its code is: no paths, routes or row ids. Every row the block
  names belongs to a feature in the list. More than five → the five that matter most
  as bullets, then the rest on one line of their own, after a blank line: `Also:
  **Billing**, **Support requests**.`
- **Needed from you**: one line. In an issue: the decisions (how many, and where), a
  review, or "nothing yet: this is for the record". In a pull request: what to read
  before merging, and who merges.
- **Words**: each word of the product that a newcomer could not guess: a name (a
  bot's name), a numbered variant (mode 2), a short form (DPA), a common word used in
  a sense of its own (seat). Take the meaning from the map's glossary; a word it lacks
  gets a plain meaning here, and the hand-back names it for the glossary. Variants of
  one word, and the members of a set (the plans a company can buy), are nested
  under it. A feature's name needs no entry: its sentence explains it. A term covers
  the words it starts with, singular or plural: "Team seat" covers "team" and
  "team seats". "None." when the text has no such word. The promise's
  own words (row, verdict, NEW-ROW) are not listed here: the issue block explains them
  in its last `<details>`.
- **Budget**: 180 words, apart from the block's own budget. Sentences of 25 words at
  most, in the plain words of `references/github-text.md` § Plain words.

## An example

```markdown
<!-- promise:intro -->
## Where this is

This issue is about two parts of the product:

- **Shared channels**: rooms where members of two companies talk.
- **Billing**: what a company pays each month, and for which seats.

**Needed from you:** one decision, under "Decisions needed" below.

## Words

- **Seat**: one paid member account. A company pays for each seat.
- **Guest**: a person from the other company. A guest has no seat.
- **Plan**: what a company buys. There are two:
  - **Plan 1, team**: channels inside one company only.
  - **Plan 2, network**: shared channels too.
<!-- /promise:intro -->
```

## The map's part

Two optional top-level lists of the map file, beside `rows`, give the first screen
its names and meanings, so every issue and pull request uses the same ones:

- `features`: the parts of the product, each `{"id", "name", "plain"}`, with an optional
  `doc` (its outcome doc). A row's optional `feature` field names one by its `id`.
  The alias keys `areas` and `area` mean the same. A map or a row that has both
  spellings, or rows that mix them, is the error `FEATURE_AND_AREA`. Write the spelling
  the map already uses, and `feature` in a new map: a project's own reader may predate
  `--features` and read only `areas`/`area` (orient warns when it does).
- `glossary`: the product's own words, each `{"term", "plain"}`, with optional
  `aliases` (other spellings, plurals, short forms). A word belongs to one entry.

The project's recipe says how to add them; a starter map's reader validates both
(`--check`) and prints them (`--features`, `--feature <id>`, `--glossary`). A map without
them still gets a first screen: the names come from the outcome docs, the code and
the body, and the hand-back offers the entries for the map.

`changed_rows.py --json` gives each reported row its `feature`, and the report's `features`
lists the features of the rows the change added, changed, removed or touched, with their
names and plain sentences: the start of a pull request's "Where this is". A change to
a row's `feature` alone is `relabelled`, not a change to its promise.

The lint reads the same lists: `AREA_UNKNOWN` (a feature the map does not have, and
whose sentence does not say "not yet in the map"), `AREA_MISSING` (a named or moved
row whose feature the list, its `Also:` line included, leaves out) and `TERM_UNDEFINED`
(a glossary word the reader meets that "Words" or a feature's name does not explain).
In an issue, the reader meets every word of the body, the asker's text included;
code spans, paths, URLs and file names are code, not words, and are not read. The
lint's `--counts` prints the words the first screen and the block show against
their budgets, so a trim can stop as soon as it fits.

A body with no first screen at all, such as one written before it existed, is a
warning (`NO_INTRO`), so it still passes. A first screen that is there is checked in
full: broken intro markers, or "Where this is" without "Words", are errors. The
`issue` and `pr` modes always write it.
