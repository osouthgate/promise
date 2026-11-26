Read before this: references/sizing.md · references/slates.md · references/anti-rationalizations.md · references/altitude.md · templates/outcome-doc.md · outcome-framework.md § The contract · § Section rules · § Decision policy
Phase 0 line: mode `new` (say if inferred), the size (`references/sizing.md`), the decision policy and its source, framework source, docs home + its source, `plansFolder` (or "none"), whether a map is configured (orient's `mapUsable`), and whether the project is adopted.
Writes: one new doc under `docsHome`, or under the `--docs-home` folder the user named when `docsHome` is null.

# New — create an outcome doc

Produce **the one doc for a capability**, in the Outcome Framework shape.
You produce the doc up to `draft`. You do not implement the capability.

## The decision policy — taken, not asked

Take it from orient's `decisionPolicy`: the repo config's, `auto` when unset
(framework § Decision policy). Never ask it. The user's own words for this doc
override it ("just move fast" is `fast`, "write the full spec" is `spec`). A
risky ask (`references/sizing.md`) takes `spec` whatever the repo's policy — the
stricter choice only makes you ask more — unless the user named another. Say which
policy you took, and where from, in the Phase 0 line, and pass it to
`render_outcome.py --policy`.

## Elicit the human half

Never skip this, never draft ahead of it. The human half is §0 TLDR, §1
Problem, §2 Outcome, and one seed worked example — framework § The contract
(the 60-second standard): §0 ≤ 40 lines, the whole human half ≤ 150 lines.

Only if the ask names service conditions, follow `references/service-targets.md`.
A prototype door ask ("I built a prototype", "lock in what I built") follows `references/sizing.md` § The prototype door.
Mark it in §8, in the usual row format with the person as Owner: "Starts from a prototype (<which code>)", so `arm` and `reconcile` see it.

- **Take what the ask already says; ask once for the rest.** The human half
  answers five prompts: *what is true after this ships* (§0 outcome line,
  expanded in §2), *why do we need it* (§2), *what must always / never be
  true* (§0 rules), *how will we know* (§0 — the user's decision; never fill
  it in), and *walk me through one concrete example* (the §3 seed — named
  actors, concrete state, expected outcome; you extend it later, never
  invent it). Take every answer the user's message already holds, in their
  words. Ask only for the ones missing, all in one turn — never one prompt
  at a time. A rule the user typed enters as typed; a rule you extracted
  from a longer source (a transcript, a ticket) is shown back once, in one
  list, for a yes. The **owner** is `git config user.name`: use it and say
  so; unset → ask for it in the same turn. `render_outcome.py` requires
  `--owner` and the lint rejects a placeholder.
  This one turn is `new`'s checkpoint (`references/sizing.md` § Batch): every
  question below that the ask did not already answer goes in it, not after it.
- **The outcome line and how-we'll-know are forced choices, never blanks.**
  Ask the open question first. If it doesn't come back as one crisp line,
  run the candidate-slate procedure for whichever field stalled —
  references/slates.md. **Rules are never slated:** a rule the user typed
  enters as typed; candidates you extract from a braindump or transcript go
  back in one list for verbatim confirmation, and only confirmed lines enter
  §0, exactly as confirmed.
- **Once the signal is chosen, re-read every OPEN decision against it** —
  framework § Section rules. An option under which the signal can't be
  staged has been ruled out; record the narrowing in §8 with the
  implication stated, and leave ratification with the human.
- **§0 is protected** the instant it's written — framework § The contract.
  Disagreements, gaps and contradictions become numbered agent notes below
  the block, never edits inside it.
- **Keep the confirmation sheet small and staged.** One screen. Large
  source material → confirm the ~10 most load-bearing lines first; the rest
  can follow in later passes. A sheet with everything on it doesn't get
  answered.
- **A pending sheet doesn't block other work.** User redirects to review,
  iteration, or anything else before answering → do that work; the human
  half stays pending, and you re-surface the *open remainder* compactly
  (never the full sheet again) at the next natural decision point. Only
  drafting a NEW doc's agent half waits on the human half.
- Can't yet state the outcome line, even from a slate? Stop. That's the
  finding — there is nothing to promise yet. Offer to help think it through
  conversationally; write nothing to `docsHome`.
- Outcome line confirmed, but no rules, no signal or no example yet, or the
  user asks to "just capture it"? Write a **thin draft** — § Thin draft
  below — and say so: the idea is in version control today, and the gaps
  are BLOCKING questions, not guesses. The user can ask for the full doc.

## Capability hunt — one doc per capability

First the release-note test (`references/sizing.md`): no line → no doc, say so and
build it; a line that an existing doc's outcome already holds → `revise` that doc,
not a new one. A new doc is for a new job with its own "so that". Then check
Phase 0's `existingDocs` for overlapping
surface — it already enumerated the docs home, so don't re-search it from
scratch. `plansFolder` is not null → also search it (every status folder)
for the same capability.

- Overlap found → propose **merge-and-delete**: name the surviving doc, the
  docs to fold in, and the docs to delete. A sibling doc is a bug, not a
  cross-reference target. Three or more docs, or entangled scenarios → point
  the user at `/promise merge` instead of resolving it inline here.
- `plansFolder` present and a touched plan doc has still-live content →
  migrate it into the new doc's §7, then propose deleting the plan file in
  the same commit as the new doc. It receives no new docs.
- Wait for the user's yes before deleting anything (a stop that batching keeps:
  `references/sizing.md` § Batch).
- `docsHome` is null → where outcome docs live goes in the one question turn
  above, `docs/designs` **(Recommended)**; the folder is created only on that
  choice, by passing it with `--create-docs-home` below. `adopt` can pin the
  folder in the config; it is still created here, on the first write.

## Thin draft — the human half only

A thin draft is a `draft` doc with `Depth: thin` in its header. It holds §0,
§1, §2, §8–§10 and any seed example; §3–§7 each hold one line that is just the
"not written yet" marker the render writes. It is the intent stage of a promise:
a place to start, never a place to agree.

- The capability hunt above runs first, the same as for a full doc.
- Render with `render_outcome.py ... --thin`. It adds the `Depth: thin` line,
  one rule slot tagged `→ UNTESTED`, and the count-free `Scenarios:` line.
- **§0 rules stay verbatim-confirmed.** Each confirmed rule is tagged
  `→ UNTESTED`. No confirmed rule → remove the slot and add a BLOCKING §9
  question that asks for the rules. The lint reports the empty block as a
  warning on a thin draft only.
- **How-we'll-know is never guessed.** Not decided → write `Open — Qn
  (BLOCKING).` as its value and add that question to §9.
- §1 and §2 take the user's own words; mark what they did not say as a §9
  question, not as text you wrote for them.
- A seed example the user gave goes in §3. Do not extend it; do not draft §4–§7: the lint reports text there,
  and a §3–§7 section with no "not written yet" line (`THIN_DRAFT`).
- Close out as § Close out at draft says, and add: the doc is thin, which
  §9 questions block the full doc, and that `/promise revise <doc>` writes
  the agent half once they have answers. A thin draft cannot be agreed —
  the lint's `THIN_DRAFT` rule rejects `Depth: thin` past `draft`.

## Draft the agent half

Instantiate the template with `python3 "${CLAUDE_SKILL_DIR}/scripts/render_outcome.py"
--title "<Capability>" --owner "<name>" --policy <fast|auto|spec> [--docs-home <folder> --create-docs-home]`
— it writes `<docsHome>/<slug>.md`, refuses to overwrite, and leaves every
interview placeholder for you to fill. `docsHome` null → pass the folder the
user chose in the capability hunt as `--docs-home`, with `--create-docs-home`
so the script creates it. Phase 0 warned `docsHome does not exist` (the user
pinned it in `adopt`) → pass `--create-docs-home` alone. Otherwise omit both
flags and it writes under Phase 0's `docsHome`. Every current-state claim
carries file:line evidence, verified this run — never remembered from an
earlier one.

- **§3 Worked examples:** extend the user's seed to cover at minimum the
  happy path, the undo/reverse path, and any permission or visibility edge
  the capability has — ABC form, named actors, concrete state, expected
  outcome. Show the diff between your examples and the user's seed.
- **§4 Invariants:** if an invariants-analysis skill is available this
  session, mention it in one line and carry on; run it only when the user
  asks — never auto-invoke it. Otherwise derive §4
  yourself and say the four moves (uniqueness claim, two-concepts-one-knob,
  fail-open-or-closed, schema-wins) ran unassisted. Either way, §4 lands the
  same shape: standing + new invariants, one line each, enforcement point
  (constraint / test / property / proof / file:line) or **UNENFORCED**, its
  proof strength where the point is evidence (`example`, `property` or
  `model`, `references/altitude.md` § Proof strength), plus a boundary line
  where the guarantee has an edge.
- **§5 Mechanism:** reuse-first — anything new names the existing primitive
  considered and why it's insufficient. The project's own nouns only;
  define any imported term explicitly. Subject spans repositories → read
  the other repository's own contract docs before claiming storage-layer
  facts, and name that read as an Existing join searched row below. A map
  row this capability extends → `adapter.py code <id>` (when `map.code` is
  set) names the files its tests import; read those first.
  **Before writing a negative claim** ("can't", "cannot", "doesn't have", "no
  way to", "unavailable", "only X has") that constrains the design — including
  one already sitting in §1's Problem prose from the interview above — give it
  a §5 Load-bearing premises row (framework § Section rules) instead of loose
  prose: `Evidence` is the source's whole field or identifier set for the
  entity, read this run — not just the field that prompted the claim —
  and `Existing join searched` names every repository or doc this
  capability touches and what was found there. An unlisted negative claim in
  §1 or §5, not covered by a matching row, is a finding
  (`lint_outcome.py PREMISE_PHRASE`).
- **§6 Acceptance:** Given/When/Then rows, derived from §3 — every worked
  example yields at least one row. Capabilities about access, permission or
  visibility → phrase rows as user questions: `Given <role> | When they ask
  "<question>" | Then answered / refused / partially answered`. Each row's
  altitude goes in the `Altitude` column — exactly one of `data`,
  `response`, `perception`, `judgement`, `sibling` (references/altitude.md);
  the lint rejects anything else. The `Row` column is already in the
  template: leave it empty at `draft` — `arm` fills it when a map files the
  rows, and nothing is filed in the map before then. After drafting rows,
  stamp each §0 rule's tag (`→ AT-n`, or `→ UNTESTED`) and say which rules
  came out UNTESTED.
- **§7 Build phases:** small, ordered, verifiable; each phase names the §6
  rows it turns green.
- Every agent-half section ends `Why — what breaks without it:` — framework
  § The contract. Can't write the line → cut the section.
- Length budgets — framework § The contract, § Section rules. §5 may run
  long when information-dense; if it's long AND the capability has two
  separable outcomes, propose the split by outcome, not by layer.

Before close-out, run `python3 "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py"
<doc>` and fix every finding, or say why one stands. The lint checks shape
only. It does not check: that §3 holds at least one example, that §9
questions carry an owner and a BLOCKING/non-blocking flag, that §4
invariants name an enforcement point or UNENFORCED, that `Last decision:`
is a real date, whether a filled Why line, example or mechanism is
*true*, or whether an agent decision's category is the true one — read
those yourself before close-out.

## Close out at draft

- Number the agent notes and open questions (owner + BLOCKING flag on
  each).
- Ask or record each open decision by the doc's policy. Ask it → an explicit
  §9 question with a **(Recommended)** option and one reason; state the
  invariants at stake in each option. Record it (only when the policy allows
  and every condition in framework § Decision policy holds) → a §8 row with
  Owner `agent`, its category, reason, rollback, reversible-until, review
  trigger and `State: provisional`. A protected category, or any doubt → ask.
- End with the one message `references/sizing.md` § Batch names: **Needs you**
  (the §9 questions the policy leaves to the human), **Decided for you** (each
  agent decision and choice this run made, one line, with how to undo it), and
  **Not checked**. The decision sheet shows the same group, where any one can be
  asked instead.
- Set `Status: draft`. Moving to `agreed` is a human act — never do it
  yourself.
- **Paste §0 inline in chat, verbatim.** It is the close-out deliverable —
  the reviewer reacts to it in the conversation, not to a doc path. If they
  can't disagree with §0 alone, the doc failed, whatever else it contains.
- Report: doc path, agent-note count, BLOCKING question count, any rules
  tagged UNTESTED, any proposed deletions awaiting a yes, and what you
  could not check.
