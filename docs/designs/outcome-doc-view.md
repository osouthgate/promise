# Outcome doc view

Status: draft
Owner: osouthgate        Last decision: 2026-10-06
Decision policy: auto
Supersedes: —
<!-- Red gate: <sha> <YYYY-MM-DD> — arm writes this as its own header line, outside this comment, when Status becomes building -->

Contents: [0. TLDR](#0-tldr) · [1. Problem](#1-problem) · [2. Outcome](#2-outcome) ·
[3. Worked examples](#3-worked-examples) · [4. Invariants](#4-invariants) ·
[5. Mechanism](#5-mechanism) · [6. Acceptance](#6-acceptance) ·
[7. Build phases](#7-build-phases) · [8. Decisions](#8-decisions) ·
[9. Open questions](#9-open-questions) · [10. Out of scope](#10-out-of-scope)

## 0. TLDR
*(author: osouthgate, 2026-10-06 — protected: do not rewrite, expand, or paraphrase — human)*

**Outcome:** A reader can see any outcome doc as one page that shows each rule with its proof.
**Rules:**
- The .md doc is the only source of truth; the page never shows text the doc does not hold.  → AT-1, AT-2, AT-6
- The page shows §0 word for word and never rewrites it.  → AT-3
- An answer given on the page reaches the doc only through decisions.py apply.  → AT-4
**How we'll know:** Ollie opens the page for the channel-muting example doc and says each rule and its proof state without opening the .md.
**Scenarios:** the acceptance rows in §6 and the worked examples in §3.

Agent notes (appended, numbered — never edited into the block above; they
sit under §0 but do NOT count toward its 40-line budget):
1. The outcome line, the three rules, the signal and the §3 seed were
   confirmed on the decision sheet on 2026-10-06 (all Recommended options).
   The rules came from the agent's replies in the project thread; Ollie
   approved them word for word.
2. Rule 1 permits fixed page labels ("How we prove it", section names) that
   are not in the doc. AT-1 counts them as chrome, not doc text. If that
   reading is wrong, rule 1 needs a revise.
3. Review: note 2 is an agent interpretation, not a recorded human ruling.
   Q1 and Q2 have recommendations but no recorded answers; §5's choices are
   proposals. Rule 1's relationship to external proof sources waits on Q4.
4. Generated source digests, revision identifiers and render times are not
   doc text or fixed labels. Their inclusion is also an unresolved part of
   Q4; neither this draft nor AT-1 authorises that exception.

## 1. Problem
*(human)*

An outcome doc is a long Markdown file. To see whether a rule is proved, a
reader must jump from §0 to §3, §5 and §6 and join the parts in their head.
Ollie asked, in the project thread on 2026-10-06: "should promise have a
visual template to show the outcome document? what would that look like?"
The prompt was the html-plan plugin, which draws a plan as a tree of claims,
each with one exhibit. The prototype rendered [the channel-muting example](../../examples/channel-muting.md).

## 2. Outcome
*(human)*

**After this ships, it is true that:**
- A reader can see any outcome doc as one page that shows each rule with its proof.

**Why we need it:** Ollie's words: "should promise have a visual template to
show the outcome document?" A fuller why is open as Q3.

## 3. Worked examples
*(human seeds ≥1, agent extends)*

**Ollie views a draft doc (seed, confirmed by Ollie).**
Ollie has the channel-muting doc at draft. He runs the render script and
opens the page. He sees two rules; each shows its scenario, its mechanism
with file:line, and its AT rows, all red. Q1 waits at the bottom. The .md
file does not change.

Agent extension (diff from the seed: three new cases). The seed's "all red"
is retained as human wording, not evidence that tests have run or failed.
AT-5 proposes "no verdict yet" without proof; Q4 must settle the source and
meaning of proof labels before implementation:

**Ben views a doc with an empty section.**
Ben renders a thin draft whose §3 holds only the "not written yet" line. The
page shows that §3 is not written yet. It does not draw a scenario that the
doc does not hold.

**Ana answers a question on the page (reverse path).**
Ana opens the page for channel-muting. Its Q1 has no options, so she types
"No, threads still notify" as her own free-text answer and presses Save.
The page does not invent a picklist or present that text as existing doc
content. She runs `decisions.py apply` on the saved answers. One
`Answer (2026-10-07, Ana): …` line appears under Q1 in §9. No other line of
the doc changes. If she does not run apply, the doc stays as it was.

**Ollie edits the doc after a render (visibility edge).**
Ollie changes a §6 row's Then in the .md. The old page still shows the old
text until he renders again. If Q4 authorises generated source metadata,
the proposal identifies the actual doc bytes with a content digest and
shows the render time; a git revision may also be shown. Otherwise these
values are omitted. A commit hash alone would not identify local,
uncommitted changes. The old page is a snapshot, not a live view.

## 4. Invariants
*(agent derives, human confirms)*

The four moves (uniqueness claim, two-concepts-one-knob, fail-open-or-closed,
schema-wins) ran unassisted. These are proposed invariants: the renderer and
its tests do not exist yet, so none is implemented or proved by this draft.

- The renderer must never write to the .md doc. Enforcement: planned test (AT-6,
  proof strength: example); UNENFORCED until that test is implemented.
  Boundary: `decisions.py apply` writes the doc;
  that is the answer path, not the renderer.
- Doc text must never run as HTML or script on the page. Enforcement: the
  page builds nodes with `textContent` and `createTextNode`, as the decision
  sheet does (`skills/promise/templates/decision-sheet.html:185`,
  `:189`), and the data block escapes `<`, `>` and `&`
  (`skills/promise/scripts/decisions.py:1473-1480`). Proof strength: example
  (fixtures covering H1/title, header text and a rule). UNENFORCED until
  AT-1's real-page checks cover those cases.
- One parser for each part of the doc. The view must read rules, rows and
  questions through `lint_outcome.py`, never a second parser. Enforcement:
  code review; UNENFORCED by a test. Why: `outcome_rows.py` says the same
  ("Reuses lint_outcome.py's rule and table parsing … so the two scripts
  cannot silently disagree", `skills/promise/scripts/outcome_rows.py:13`).
- A verdict on the page must never be higher than its source supports. With
  no authorised proof source, a row shows "no verdict yet", never "proven".
  Enforcement: planned test (AT-5); UNENFORCED. Boundary: Q4 must resolve
  whether the page may load external evidence at all. A map's recorded
  verdict and `map_report.py`'s computed lane-green result are distinct;
  neither this viewer nor the report promotes a recorded verdict. A test
  citation alone does not establish scenario-level proof (see
  `skills/promise/references/altitude.md:84-89`).

Why — what breaks without it: a page that drifts from the doc, or shows a
row greener than it is, is worse than no page, because the reader trusts it.

## 5. Mechanism
*(agent)*

**Evidence pin and implementation status.** Current-state references in
The draft adds no renderer, template, tests or proof. The human-half confirmation
claims above are retained as provenance in this draft, not fresh permission to build.

**What exists today.**
- `outcome_rows.py --json` already turns a doc into JSON: status, §0 rules
  with tags, §6 rows with altitude and Row id, and the signal
  (`skills/promise/scripts/outcome_rows.py:57-97`).
- `decisions.py` reads §0 for the sheet with `doc_brief`
  (`skills/promise/scripts/decisions.py:598-606`), and renders
  `templates/decision-sheet.html` by putting escaped JSON in place of
  `__PROMISE_SHEET__` (`skills/promise/scripts/decisions.py:1473-1480`,
  `skills/promise/templates/decision-sheet.html:154`).
- `lint_outcome.py` has the parsers: `section_bounds` (`:209`),
  `tldr_block_bounds` (`:221`), `parse_rules_block` (`:319`),
  `parse_acceptance_rows` (`:655`), `parse_signal` (`:737`),
  `worked_examples` (`:742`), `parse_questions` (`:1432`), all in
  `skills/promise/scripts/lint_outcome.py`.
- `map_report.py` compares a recorded map verdict with a computed result
  from a supplied JUnit run; without JUnit it only reports recorded state
  (`skills/promise/scripts/map_report.py:84-110`, `:182-183`). Computation
  joins evidence by lane, not by individual scenario, so a green lane is not
  by itself proof of every scenario (`skills/promise/references/altitude.md:84-89`).
- The decision pane now renders decision-sheet items and submits picks to
  `decisions.py apply` (`hooks/decisions-pane.js:1-15`, `:115-130`). It is
  an answer surface, not a complete outcome-doc viewer. The existing HTML
  sheet remains a reuse candidate; the proposed view does not replace the pane.
- Service policies and observations now have a separate report
  (`skills/promise/references/service-targets.md:1-24`,
  `skills/promise/scripts/service_report.py`). A functional verdict must not
  stand in for service compliance; whether this view includes either source
  is still Q4, not an added requirement in this draft.
Why: every part the page needs is already parsed; the view adds a page, not
a parser.

**Proposed changes — not implemented, and not permission to arm.**
1. A new script, `skills/promise/scripts/render_view.py <doc> --out
   <page.html> [--json]`. It builds one JSON object from the doc with the
   `lint_outcome.py` parsers: header (title, status, owner, policy, last
   decision), §0 verbatim, §1 and §2 text, each §3
   example, §4 lines, §5 text, §6 rows, §7 phases, §8 rows, §9 questions,
   §10 text. `--json` prints that object and writes no page. This is the
   proposed answer to Q1, which remains open: artifacts could read derived
   JSON while the doc stays Markdown. A `tldr` field retains the raw source
   slice selected by `tldr_block_bounds` over original lines, including line
   endings. Its UTF-8 bytes are the preservation contract; parsed outcome,
   rule and signal fields may be extra data, never a replacement for it.
   A generated source digest, optional revision and render time are only
   proposed if Q4 and any required human rule clarification authorise them;
   omit those values otherwise.
2. A new template, `skills/promise/templates/outcome-view.html`, built on the
   decision sheet's shape: one `<script type="application/json">` data
   block, rendered in the browser with `textContent` only. Every supplied
   field, including H1/title, owner and other header text, follows that
   escaped data path; no source string is pasted directly into HTML. If
   the browser title is updated, use the text-only DOM title property.
3. Proposed layout: lifecycle metadata at the top; §0 in a protected block;
   one branch per rule containing its tagged §6 rows; §3 examples, §4
   invariants and §5 mechanism each once, without invented per-rule joins;
   §9 questions, §1 and §10 at the foot. Proof counts and labels must follow
   the evidence-source decision in Q4. Q2's example grouping is still open.
4. A rule-to-example join: an example belongs to a rule when an AT row the
   rule tags came from it. The doc does not record that link today, so v1
   proposes all §3 examples under "Worked examples" once, and each rule's
   tagged rows beside that rule. This is Q2's recommendation, not a recorded
   owner answer.
5. Verdicts: without an authorised proof source or a filed Row id, show
   "no verdict yet". A lifecycle status and a `Red gate:` commit are source
   metadata, not a current test result; `building` does not mean the tests
   are still red. If Q4 permits map/run evidence, label recorded verdict,
   computed lane-green status, run provenance and missing evidence separately.
   Never manufacture "proven" from a status header or a single green lane.
6. §9 on the page uses the decision sheet's item cards and its
   `promise-answers` payload, so `decisions.py apply` reads a saved answer
   with no change (§8 D2). Limit the proposed viewer to ordinary §9 question
   answers: `apply` can also promote agent decisions and update §8 when a
   sheet exposes "Ask me instead" (`skills/promise/scripts/decisions.py:1532-1602`), which is outside
   this draft's answer path.
Why: reuse-first. The parsers, the escaping and the answer path exist; the
view is a template and a thin script.

### Load-bearing premises
*(agent, whenever a claim in §1 or above is a negative — something is
impossible, absent, or available in only one place)*

| Premise | Evidence | Existing join searched | What would make it false |
|---------|----------|-------------------------|---------------------------|
| A doc does not record which §3 example a §6 row came from. | Template fields for §6: `#`, `Given`, `When`, `Then`, `Altitude`, `Row` (`skills/promise/templates/outcome-doc.md`, §6 table); `parse_acceptance_rows` returns id, given, when, then, altitude, row (`skills/promise/scripts/outcome_rows.py:76-86`). | `osouthgate/promise`: template, framework, `lint_outcome.py`, `outcome_rows.py`, `examples/`. No other repo is touched. | A §6 column or a §3 tag that names the example. |
| The outcome format has no dedicated structured image field. | The §6 fields are `#`, `Given`, `When`, `Then`, `Altitude`, `Row`; `worked_examples` returns source ranges (`skills/promise/scripts/lint_outcome.py:742`). Markdown image/link text may still appear in prose; this is not a claim that docs cannot contain pictures. | Template, framework, `lint_outcome.py`, `outcome_rows.py`, examples, and the decision sheet's separate item `image` field (`skills/promise/references/decision-sheet.md` §4). No other repo is touched. | A structured image field/convention is added, or the viewer is explicitly asked to render existing Markdown media. |
| The standard outcome-doc row has no recorded verdict field. | `outcome_rows.py` returns top-level `path`, `status`, `rules`, `rows`, `signal`; rows contain `id`, `given`, `when`, `then`, `altitude`, `row` (`skills/promise/scripts/outcome_rows.py:57-97`). Map/run reports are separate sources (`skills/promise/scripts/map_report.py:84-110`, `:182-183`). | Doc/template, map scripts, framework and altitude taxonomy. No other repo is touched. | The row schema gains a verdict field, or Q4 authorises a separate labelled proof source. |

Why — what breaks without it: the page would draw joins and verdicts that the
doc does not hold, which breaks rule 1.

## 6. Acceptance
*(agent drafts, human confirms)*

| #    | Given   | When   | Then   | Altitude   | Row |
|------|---------|--------|--------|------------|-----|
| AT-1 | test copies of `examples/channel-muting.md` carrying HTML metacharacters and script-like text in H1/title, owner/other header text, and a rule | `render_view.py --json` and `--out` run, and the page opens | supplied title, header and rule text stays inert through the escaped data path; every displayed string traces to doc text or a source/label explicitly authorised by a human answer to Q4 and any required human rule clarification; unapproved generated metadata is absent | perception |     |
| AT-2 | a thin draft whose §3 holds only the "not written yet" line | `render_view.py --out` runs on it | the page data holds no §3 example, and the page says §3 is not written yet | perception |     |
| AT-3 | `examples/channel-muting.md`, including its wrapped signal and original AT tags | `render_view.py --json` runs on it | the JSON `tldr` value, encoded as UTF-8, is byte-equal to the raw §0 source slice selected with `tldr_block_bounds`, retaining whitespace, tags and line endings; parsed fields are optional extra data, not the comparison target | response |     |
| AT-4 | a page for channel-muting, with the user typing a free-text answer to optionless Q1 and saving the `promise-answers` payload | `decisions.py apply` runs on that file | one `Answer (…)` line is under Q1 in §9 and every other line of the doc is unchanged | data |     |
| AT-5 | channel-muting at draft, with no map | Ollie opens the rendered page | he sees two rules, each with its AT rows marked "no verdict yet", the worked examples, and Q1 at the foot | perception |     |
| AT-6 | any doc in `examples/` | `render_view.py` runs on it, with and without `--json` | the doc's bytes and modified time are unchanged | data |     |

Why — what breaks without it: without rows, "the page is faithful" is a
claim with nothing to test.

## 7. Build phases
*(agent)*

1. `render_view.py --json`, using shared bounds for the raw `tldr` slice
   and existing parsers for extra fields, with tests on `examples/`.
   Turns AT-3 and AT-6 green.
2. `templates/outcome-view.html` and `--out`, with the escape fixture and
   the thin-draft fixture. Turns AT-1 and AT-2 green.
3. §9 cards with the `promise-answers` payload; an apply round trip test.
   Turns AT-4 green.
4. Render channel-muting locally and exercise AT-1/AT-2 against the real
   page, not only its data block. Turns their perception assertions green.
5. Ollie runs the §0 signal on the page. Turns AT-5 green. Publication needs
   separate authorisation; no build or publication is performed by this draft.
6. Only after Q4 is resolved: add any authorised external-proof display with
   its own acceptance cases before implementation. AT-5 covers only no-map
   rendering and cannot stand as proof of map-backed behaviour.

Why — what breaks without it: the JSON is the base the page and any other
artifact build on; it must be right first.

## 8. Decisions
| # | Date | Decision | Owner | Why |
|---|------|----------|-------|-----|
| 1 | 2026-10-06 | Outcome, rules, signal, seed example, docs home `docs/designs` and owner as on the decision sheet. | osouthgate | All Recommended options, saved on the sheet. |
| D1 | 2026-10-06 | The script is `render_view.py`; the template is `templates/outcome-view.html`, built on the decision sheet's data-block shape. | agent | Category: naming. Because: reuses the escaping and render path that exist. Rollback: rename the files. Reversible until: the first release that ships them. Review: before arm. State: provisional |
| D2 | 2026-10-06 | §9 on the page uses the decision sheet's cards and `promise-answers` payload. | agent | Category: internal. Because: `apply` then needs no change, which rule 3 asks for. Rollback: show §9 read-only with a link to the sheet. Reversible until: arm. Review: before arm. State: provisional |

## 9. Open questions
Q1 — owner: osouthgate — non-blocking: should the .md docs become JSON docs,
so any artifact can use them? (Ollie's note on the sheet, 2026-10-06.)
**(Recommended)** No: keep Markdown as the one source, and add
`render_view.py --json`, which gives any artifact the whole doc as JSON.
Because: rule 1 makes the .md the only source of truth, and every script,
the lint and every human review read Markdown today; a JSON source would
need a second home or a migration of every doc. Other option: JSON source
with a Markdown render, which reverses rule 1.

Q2 — owner: osouthgate — non-blocking: should §3 examples name the AT rows
they produce, so the page can put each example under its rule? **(Recommended)**
Not in v1: show the examples once, and each rule its rows. Because: it needs a
template and lint change for every doc.

Q3 — owner: osouthgate — BLOCKING before arm: §2 "Why we need it" holds
only your question. What does a page give that the .md does not? One line
is enough. The agent must not supply the human's reason.

Q4 — owner: osouthgate — BLOCKING before arm: rule 1 says the page shows
no text absent from the .md, but proof labels, map verdicts, JUnit
observations and service status would come from other sources. Generated
source digest, revision and render-time values are also absent from the doc,
and are not fixed labels. Which of these may the page include?
**(Recommended)** Keep Markdown canonical for intent and §0 verbatim, but
explicitly authorise labelled external evidence, fixed chrome and generated
source metadata before implementation. Because: useful proof status requires provenance and cannot
be inferred from lifecycle metadata. Other option: a strictly doc-only v1,
with no external proof/service-compliance claims or generated source metadata.
The recommendation requires a human clarification of rule 1; this draft
does not make it. If any of those values are later authorised, update their
specific acceptance inventory before arm rather than silently widening AT-1.

## 10. Out of scope

- Mockups or pictures inside a doc (a §3 image field): see Q2 and the
  premises table. html-plan draws them; this view does not invent them.
- Direct document editing. The proposed viewer offers only ordinary §9
  question answers through `decisions.py apply`; its other capabilities
  (including §8 decision promotion) are not exposed here.
- A JSON source format for docs (Q1).
- Installing or wrapping the html-plan plugin. It stays a separate tool to
  use alongside Promise.
