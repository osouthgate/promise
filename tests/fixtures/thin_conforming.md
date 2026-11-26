# Channel muting

Status: draft
Owner: Ollie        Last decision: 2026-01-01
Decision policy: auto
Supersedes: —
Depth: thin
<!-- Red gate: <sha> <YYYY-MM-DD> — arm writes this as its own header line, outside this comment, when Status becomes building -->

Contents: [0. TLDR](#0-tldr) · [1. Problem](#1-problem) · [2. Outcome](#2-outcome) ·
[3. Worked examples](#3-worked-examples) · [4. Invariants](#4-invariants) ·
[5. Mechanism](#5-mechanism) · [6. Acceptance](#6-acceptance) ·
[7. Build phases](#7-build-phases) · [8. Decisions](#8-decisions) ·
[9. Open questions](#9-open-questions) · [10. Out of scope](#10-out-of-scope)

## 0. TLDR
*(author: Ollie, 2026-01-01 — protected: do not rewrite, expand, or paraphrase — human)*

**Outcome:** A member can mute a channel so it stops notifying them.
**Rules:**
- A muted channel never sends a push or a badge count until it is unmuted.  → UNTESTED
**How we'll know:** Open — Q1 (BLOCKING).
**Scenarios:** the acceptance rows in §6 and the worked examples in §3.

Agent notes (appended, numbered — never edited into the block above; they
sit under §0 but do NOT count toward its 40-line budget):
1. Thin draft: §3-§7 wait for Q1 and a seed example.

## 1. Problem
*(human)*

What breaks today, in current-state terms — the behaviour, not the feature idea.
Evidence: a bug report, a quote, or a file:line. A claim here that something is
impossible, absent, or available in only one place gets a row in §5's
Load-bearing premises table too, not just this prose.

## 2. Outcome
*(human)*

**After this ships, it is true that:** 2–5 observable statements expanding §0's
outcome line.
**Why we need it:** what it unlocks; what breaks or stays broken without it.
(The how-we'll-know line lives in §0 — one home, no copy here.)

## 3. Worked examples
*(human seeds ≥1, agent extends)*

*Not written yet: this is a thin draft. Run `/promise revise` on this doc to write it.*

## 4. Invariants
*(agent derives, human confirms)*

*Not written yet: this is a thin draft. Run `/promise revise` on this doc to write it.*

## 5. Mechanism
*(agent)*

*Not written yet: this is a thin draft. Run `/promise revise` on this doc to write it.*

## 6. Acceptance
*(agent drafts, human confirms)*

*Not written yet: this is a thin draft. Run `/promise revise` on this doc to write it.*

## 7. Build phases
*(agent)*

*Not written yet: this is a thin draft. Run `/promise revise` on this doc to write it.*

## 8. Decisions
| # | Date | Decision | Owner | Why |
|---|------|----------|-------|-----|

Decisions may be partially ruled: record the ruling made, by whom, and the
narrowed residual question. A decision the agent took under the decision
policy has Owner `agent`, and its Why cell reads `Category: … Because: …
Rollback: … Reversible until: … Review: … State: provisional`
(outcome-framework.md § Decision policy).

## 9. Open questions
Q1 — owner: Ollie — BLOCKING — how will we know muting works: a demo or a metric?
Answers appended inline with a date, never deleted.

## 10. Out of scope
Explicit. Link the one doc that owns each excluded surface.
