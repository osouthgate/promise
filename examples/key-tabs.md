# Keys page tabs

Status: draft
Owner: Ollie        Last decision: 2026-01-03
Decision policy: auto
Supersedes: —

Contents: [0. TLDR](#0-tldr) · [1. Problem](#1-problem) · [2. Outcome](#2-outcome) ·
[3. Worked examples](#3-worked-examples) · [4. Invariants](#4-invariants) ·
[5. Mechanism](#5-mechanism) · [6. Acceptance](#6-acceptance) ·
[7. Build phases](#7-build-phases) · [8. Decisions](#8-decisions) ·
[9. Open questions](#9-open-questions) · [10. Out of scope](#10-out-of-scope)

## 0. TLDR
*(author: Ollie, 2026-01-01 — protected: do not rewrite, expand, or paraphrase — human)*

**Outcome:** An admin finds every kind of key on one Keys page, one tab per kind.
**Rules:**
- Each kind of key has exactly one tab, and no key shows on two tabs.  → AT-1, AT-2
- A secret is shown once, when it is made, and never again.  → AT-3
**How we'll know:** Ana opens Keys, finds her team's service key on its tab in
under ten seconds, and never sees a secret she did not just make.
**Scenarios:** the acceptance rows in §6 and the worked examples in §3.

Agent notes (appended, numbered — never edited into the block above; they sit
under §0 but do NOT count toward its 40-line budget):
1. Doc made under `Decision policy: auto`: three small choices are recorded in §8
   as agent decisions, each with its rollback; one more was asked (Q2).

## 1. Problem

The menu holds three items for keys today, one per kind, so an admin hunts
through three pages to find one key. Evidence: support tickets that ask where
a key went.

## 2. Outcome

**After this ships, it is true that:**
- One Keys item in the menu opens one page.
- Each kind of key has its own tab on that page.

**Why we need it:** admins lose time and make second keys they do not need.

## 3. Worked examples

### Example: Ana finds a service key

Ana opens Keys. The page opens on the Personal tab. She picks the Service tab
and sees her team's two service keys, each with its name and date.

### Example: a secret is shown once

Ben makes a new personal key. The page shows its secret once, with a copy
button. When Ben comes back, the key shows its name and date, never the secret.

## 4. Invariants

A key must never show on two tabs. Enforcement: the page reads each tab's keys
by kind, one query per kind (example).
Why — what breaks without it: a key on two tabs looks like two keys, and an
admin deletes the wrong one.

## 5. Mechanism

Today, each kind of key has its own page. This puts the three lists on one
page, as tabs, and keeps each list's own query. Why: no query changes.
Why — what breaks without it: without one page, the menu keeps its three items.

## 6. Acceptance

| #    | Given | When | Then | Altitude | Row |
|------|-------|------|------|----------|-----|
| AT-1 | Ana has a personal and a service key | she opens Keys | she sees one tab per kind | perception |  |
| AT-2 | Ana has a service key | she opens the Service tab | the key shows there and on no other tab | perception |  |
| AT-3 | Ben made a key yesterday | he opens Keys | he sees its name and date, not its secret | perception |  |
Why — what breaks without it: without rows, "one tab per kind" is a claim with
nothing to test.

## 7. Build phases

Phase 1 turns AT-1 and AT-2 green: the page and its tabs.
Phase 2 turns AT-3 green: the secret is shown only at creation.
Why — what breaks without it: without phases, all the red tests land at once.

## 8. Decisions

| # | Date | Decision | Owner | Why |
|---|------|----------|-------|-----|
| 1 | 2026-01-01 | Decision policy: auto (was none, read as spec). | Ollie | Ollie chose it; from here the agent asks or records decisions by it. |
| 2 | 2026-01-02 | The tabs read Personal, Team and Service. | agent | Category: wording. Because: those are the words admins use in support tickets. Rollback: change the three tab labels. Reversible until: public release. Review: before public release. State: provisional. |
| 3 | 2026-01-02 | The tabs sit in the order Personal, Team, Service. | agent | Category: order. Because: most admins look for their own keys first. Rollback: reorder the tab list. Reversible until: public release. Review: after 50 uses. State: provisional. |
| 4 | 2026-01-02 | The page opens on the Personal tab. | agent | Category: default. Because: it is the tab most visits need. Rollback: change the default tab. Reversible until: arm. Review: before arm. State: provisional. |
| 5 | 2026-01-02 | A secret is shown once, when the key is made. | agent | Category: security. Because: a secret shown again can be copied by anyone at the screen. Rollback: none that is cheap: a secret once shown cannot be taken back. Reversible until: never. Review: before arm. State: asked Q2. |

## 9. Open questions

Q1 — owner: Ollie — non-blocking: should a team key show who made it?

Q2 — owner: Ollie — BLOCKING — the agent chose: A secret is shown once, when the key is made (§8 Decisions). Keep that, or decide another way?
Why asked (2026-01-02, agent): security is a protected category; the agent never decides one alone.
Answer (2026-01-03, Ollie): keep it; it is now a rule in §0.

## 10. Out of scope

Rotating a key is a separate capability, owned by [Key rotation](key-rotation.md).
