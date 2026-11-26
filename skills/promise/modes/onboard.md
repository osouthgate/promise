Read before this: references/decision-sheet.md · references/sizing.md
Phase 0 line: mode `onboard`, the starting point inferred from the ask, project root if available, adoption/map status and warnings.
Writes: scratch interview notes and a decision sheet only. Project writes follow the selected mode after the user chooses its scope and next action.

# Onboard — start with one useful promise

Help the user leave with one workflow, a concrete success example and a useful
next action. Carry forward the answers in their request. Name the job in their
words. If their request already names a specific action, use that mode directly.

## Start where they are

Use orientation's context, never infer product maturity from the presence of a
map. An existing product can have no Promise setup. No repository yet is a valid
starting point; keep talking and defer file locations until there is a place to
save the result. A broken config is a named repair, not an empty project.

If the starting point is unclear, ask one question with these choices in plain
words, accepting their own answer too:

- **An idea before code.** Explore the first user job and how they will recognise success.
- **A prototype already built.** Take the prototype door: `new`, per `references/sizing.md` § The prototype door.
- **A new project.** Pick the first workflow and preview the smallest setup it needs.
- **An established product.** Choose one workflow to pilot, with the problem that makes it matter.
- **Already using Promise.** Find the existing job and the improvement they want next.

Do not recommend a starting point without evidence. Say what you inferred when
their request already identifies it, then proceed to the first unanswered point.
An empty `/promise` with no concrete task offers this interview.

## Ask what changes the next step

Use a conversational first pass. Ask at most two short, related questions per
turn. Start with what is missing from “who needs to do what, and why now?”
Then ask for one concrete successful example, including what would make it fail.
Ask how they will judge success only if they have not supplied that signal.
Take a braindump or a document as an answer; show extracted rules back once for
confirmation before they become the user's protected wording.

When they are unsure, offer two or three candidate jobs drawn from what they
said, recommend one with a reason, and accept “something else”. A candidate is
a proposal until the user picks it. Let them skip an unknown, pause or change
direction. Keep unresolved answers visible and resume from them.

For an established product, use recurring failures and user impact to suggest a
first feature. Evidence availability affects the work required, not whether an
important poorly tested workflow deserves attention. Two candidates are usually
enough. Ask for incident counts only when the choice depends on them.

Use Doctor's read-only inventory when there is a project to inspect. Use map
lookup only through the existing adapter and its configured-command permission.
Read only the files needed for the selected workflow. A sibling map remains
read-only. With `map: false`, offer a document-based pilot. A sparse map is a
question about coverage, never a score for the team.

## Keep one job in view

Find the nearest existing capability before proposing one. Cases, constraints,
bugs and test variants normally extend that job. Split when the actor's outcome
or assurance boundary differs. Count scenarios and keep their evidence.
For the opt-in relaxed grouping trial, follow the project's recipe and the
running reader's support. Do not rewrite an existing map or enable a trial as a
side effect of onboarding.

Ask about service conditions when the user mentions them or when a concrete
failure example depends on them. Offer speed, availability, capacity or
accessibility as examples if helpful. Let the user name any other condition.
Read `references/service-targets.md` when those conditions come up.
Keep a proposed target, a configured policy and dated observations distinct.
Do not invent thresholds or require an SLA for every job.

## One screen to review

Read back the smallest proposal that answers these points, omitting repetition:

| Item | What the user reviews |
|---|---|
| First workflow | Actor, job and intended outcome, in their words |
| Why this one | The failure or opportunity that makes it worth doing now |
| Boundary | Included journeys and the features left for later |
| Worked example | Concrete input, action, expected result and failure case |
| Evidence | What is observed, what is proposed and what remains unchecked |
| Service conditions | Supplied expectations and unresolved measurement choices |
| Next action | The existing mode, proposed writes and the next visible result |

Reuse `references/decision-sheet.md` for confirmation. Generate only the items
that still need a choice. Use standalone asks for interview answers; a sheet
with no outcome doc does not require creating one. On a rich host, the existing
decision sheet supplies the visual form. On a text host, its chat reply codes
and free text carry the same questions. The example in
`examples/onboarding/asks.json` shows the standalone form.
For an interview with no outcome docs, run `sheet --docs-home . --asks <absolute asks path>`
from a fresh scratch folder. This reuses the existing sheet without scanning
the project as a substitute docs home.

An answer to “where are you starting?” selects a route. It grants no permission
to run commands or write project files. A confirmation that names a scoped
action and its writes authorises that action. Reuse authorisation already
given in the session. Do not ask again merely because a mode boundary changed.
Standalone answers returned by `decisions.py apply` are actions for the agent
to consume in this conversation; they do not become agreed outcome-doc rules.
Copy any confirmed human wording to the draft only through the selected mode.

## Hand off without restarting

| The chosen result | Continue with |
|---|---|
| An idea with enough human intent | `new`, carrying its confirmed words, example and signal |
| An idea with an unresolved signal | `new`'s thin draft when requested; otherwise continue the conversation |
| A new project needing setup | `adopt`'s preview, then `new`; show only the setup choices still open, including its one policy question |
| A pilot in an existing product | `backfill` with `references/scoped-backfill.md` and the selected boundary |
| A change to an existing job | `revise` for intent, `intake` for a case, or `reconcile` for implementation evidence |
| A confusing or noisy setup | `doctor`, then a selected simplification with its evidence retained |
| A request to update the installed version | `upgrade` as its own change |

Carry the answers, chosen boundary, source references and permissions into the
next mode. Ask only its remaining questions. Agreement and build transitions
still use their existing human checkpoints.

End with the selected job, what will happen next and any unanswered point that
changes it. A planning-only interview ends at the reviewed proposal. Expansion
to another workflow is a new choice after the pilot's result is reviewed.
