# Promise onboarding interview

Status: draft
Owner: osouthgate        Last decision: 2026-11-13
Decision policy: auto
Supersedes: —

Contents: [0. TLDR](#0-tldr) · [1. Problem](#1-problem) · [2. Outcome](#2-outcome) · [3. Worked examples](#3-worked-examples) · [4. Invariants](#4-invariants) · [5. Mechanism](#5-mechanism) · [6. Acceptance](#6-acceptance) · [7. Build phases](#7-build-phases) · [8. Decisions](#8-decisions) · [9. Open questions](#9-open-questions) · [10. Out of scope](#10-out-of-scope)

## 0. TLDR
*(author: agent, 2026-11-06 — draft for owner confirmation)*

**Outcome:** Someone starting with Promise can choose one workflow to cover and leave with a plan to show whether it works.
**Rules:**
- Reuse the user's answers and ask only for information that changes the next step. → AT-1, AT-2
- Scope a rollout in an existing product to one agreed workflow at a time. → AT-3, AT-5
- Show existing behaviour, the proposed promise and evidence gaps separately. → AT-3, AT-4
- Let the user review the scope and proposed writes before changing the project. → AT-5
**How we'll know:** Open — Q1 (BLOCKING).
**Scenarios:** 5 acceptance rows (§6), 4 worked examples (§3).

Agent notes:
1. The outcome and rules are draft interpretations. The owner described four starting points and raised chat and the existing Artifact as possible surfaces.
2. The worked examples are illustrative. They record no owner decisions or product evidence.
3. The user authorised implementation and independent review. The draft human half remains a proposal. Script checks and worked conversations exercise routing and evidence boundaries; a live user pilot still decides whether the flow is useful.

## 1. Problem

Ollie asked for “a user interview process for promise that guides a user from different points”. Someone with only an idea needs help deciding what to promise first. Someone with an established product needs help choosing where to start and deciding which existing behaviour deserves a promise.

## 2. Outcome

**After this ships, it is true that:** A user leaves the interview with one selected workflow, the smallest useful Promise output for their starting point, and a next step that identifies which evidence exists and which they still need.

**Why we need it:** A team can get value from Promise on a workflow that matters before deciding whether to expand it.

## 3. Worked examples

**Ana has an idea for equipment loans.** She says a member should be able to reserve an available item. The interview already has an actor and a job. It asks what happens when two members try for the last item and how Ana will judge success. Once confirmed, the first output is a draft outcome for reservations.

**Ben has an empty Promise project.** He has already named report upload as his first workflow. The interview uses the detected setup and his existing answer, then asks for the expected outcome and one case that would show it worked. The proposed first change is one outcome, with map and test work staged for the normal agreement and arm steps.

**Cara has a large application with recurring refund failures.** She picks refunds ahead of catalogue search because the incidents are recurring and affect customers' money. The interview shows which refund behaviours current evidence supports, which rules still need confirmation and which failures need tests. It proposes one refund pilot with an exit check, leaving other features outside its scope.

**Dev already uses Promise.** Doctor shows several rows with the same returns story. Dev says the return deadline changed. The interview offers to extend the existing return job and shows which evidence should change. It asks separately about any service expectation the deadline imposes.

## 4. Invariants

- The unit of adoption is a user job with its own outcome. A route, a test or a service policy can provide evidence or constraints for that job. Enforcement: AT-2 and AT-4.
- A recorded behaviour becomes a promise through the existing agreement path. A test run, a source citation and an agreed rule each keep their own meaning. Enforcement: AT-3 and AT-4.
- The preview states its boundary and lists proposed writes before invoking a writing mode. A skipped inspection or unavailable test run appears as a gap. Enforcement: AT-5.

Why — what breaks without it: a team could mistake today's behaviour for a commitment or start a rollout beyond the agreed workflow.

## 5. Mechanism

Start with one question when the initial request leaves the route unclear. “Where are you starting, and what should work better first?” Offer **idea before code**, **new project**, **established product**, and **already using Promise**. If the user already answered, infer the route and say what you inferred.

1. **Use the context you have.** For a repo, use [orientation](../../skills/promise/scripts/orient.py) to establish its setup. If Promise is already present, use [Doctor](../../skills/promise/modes/doctor.md) and existing outcome or map lookups to find a likely home for the job. Respect the existing approval for project-configured commands.
2. **Ask the smallest useful batch.** Identify the actor, their job, the failure or opportunity that makes it matter, and one concrete example. For an established product, rank candidate workflows by incident frequency and user impact. Use available evidence to size the pilot and expose gaps, so a poorly instrumented workflow can still come first.
3. **Read back a one-screen proposal.** Include the workflow, any explicit exclusions, what is already observed, the intended outcome, the evidence to collect and what the next step would write. If service expectations matter, ask about the condition and how it would be measured or assessed.
4. **Use the existing hand-off.** Route an idea to [new](../../skills/promise/modes/new.md), an empty repo to [adopt](../../skills/promise/modes/adopt.md) if it needs setup and then [new](../../skills/promise/modes/new.md), and an existing Promise project to [revise](../../skills/promise/modes/revise.md) or [intake](../../skills/promise/modes/intake.md) when there is a suitable home. An established product can use [scoped backfill](../../skills/promise/references/scoped-backfill.md), with explicit capability selection and bounded original test exports.

The [onboarding mode](../../skills/promise/modes/onboard.md) carries the answers between these steps. The [example form](../../examples/onboarding/asks.json) renders through the existing decision sheet in a fresh scratch directory. Reports and both viewers label selected capability scope. No new project configuration is needed for a pilot.

Use chat for the first pass and reuse the [decision sheet](../../skills/promise/references/decision-sheet.md) for confirmations when the host can display it. The selected workflow and evidence plan should be identical on either surface.

Why — what breaks without it: repeated questions slow down the interview, and separate question sets can produce different plans.

## 6. Acceptance

| # | Given | When | Then | Altitude | Row |
|---|---|---|---|---|---|
| AT-1 | An idea names the actor and their job | The interview begins | It carries both forward, asks for the missing example or signal, and offers a draft outcome as the next step | response | |
| AT-2 | An empty Promise project whose owner already named report upload | The interview inspects the setup | It proposes one report-upload outcome and gives the next step for its evidence | response | |
| AT-3 | An established app with recurring refund failures and incomplete evidence | The user picks refunds | The pilot names refunds as its boundary and distinguishes observed behaviour, proposed rules and missing evidence | response | |
| AT-4 | An existing returns capability and a new deadline for the same user job | The user asks what to change | The proposal names the existing capability and the changed scenario or evidence | response | |
| AT-5 | A pilot proposal is waiting for scope confirmation | The user stops after reviewing it | The checkout retains its original config, map and outcomes | data | |

Why — what breaks without it: the happy path can pass while an established project's interview reads too broadly or writes before confirmation.

## 7. Build phases

1. Walk through all four examples in chat. Check which questions change the outcome and which the supplied context already answers.
2. Wire the opening interview and decision sheet to the existing modes. Validate the same answers on both surfaces.
3. Define and test the scoped backfill boundary separately, using a fixture with in-scope gaps and unrelated tests outside the pilot.

Why — what breaks without it: testing the conversation first separates unclear questions from defects in the rollout tooling.

## 8. Decisions

| # | Date | Decision | Owner | Why |
|---|---|---|---|---|
| D1 | 2026-11-06 | Prototype the interview in chat and reuse the existing decision sheet for confirmation. | agent | Category: default. Because: both surfaces can use the same questions. Rollback: use chat for the entire interview. Reversible until: first release. Review: before arm. State: provisional |

## 9. Open questions

Q1 — owner: osouthgate — BLOCKING before arm: What would show that the interview helped?
**(Recommended)** Run it on an idea and a real existing project. In each case, the user can name the first workflow, the evidence they need and the next action after reviewing one proposal. A broader alternative is to measure whether teams complete the pilot and return for a second feature.

## 10. Out of scope

- A new Artifact format or a whole-map viewer.
- Repository-wide migration and automatic expansion beyond the selected pilot.
- Changing existing evidence, lifecycle or service policy rules.
