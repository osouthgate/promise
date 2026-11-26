# Behaviour evals for promise

The unit tests in `tests/` check the scripts. These evals check the skill itself: given
a real ask, does an agent running `/promise` do the least that ask needs, and still
stop where a person must decide? Each case runs in a fresh, isolated `claude -p`
session with only this plugin loaded, inside a small chat app that
`_fixture/make-project.sh` builds and adopts for promise.

They run with [`claude plugin eval`](https://code.claude.com/docs/en/plugin-evals), on
the credential Claude Code is signed in with. On a claude.ai subscription, runs and
judge calls count against the plan's usage, not an API bill. The report's dollar
figures are the list-price estimate the tool prints.

## Run them

```
bash evals/run.sh --runs 1            # every case once: a quick look (about 2 minutes)
bash evals/run.sh                     # every case 3 times: a score to trust
bash evals/run.sh --tag train         # the cases a change may be tuned on
bash evals/run.sh --tag test          # the held-out cases, to accept a change
bash evals/run.sh --case tiny-copy    # one case (one glob; --case once per run)
```

`run.sh` passes these flags to `claude plugin eval`:
- `--scaffold` builds each case's fixture.
- `--allow-tools Bash Write Edit` lets the skill run its scripts and write docs. On
  Linux, Bash runs in the OS sandbox, which needs `bubblewrap` and `socat` installed.
- `--ablation none` skips the no-plugin arm. `/promise` means nothing without the
  plugin, so that arm measures nothing here.
- `-j 4` runs four at a time.
- `--max-cost-usd 20` sets a cost ceiling. Change it with `EVAL_MAX_COST_USD`.

The report is written to `evals/results/<timestamp>/report.html`, which is git-ignored.
On a subscription it is also published as a private artifact; pass `--no-publish` to
keep it local.

## The cases

| Case | Tag | The ask | Passes when |
|---|---|---|---|
| `tiny-copy` | train | change an empty-state string | the copy changes, no doc is written, nothing is asked before the change; its prompt grants no yes for configured commands, so the session's one question may only come with the result |
| `tiny-refactor` | test | extract a helper, behaviour unchanged | a helper appears, the tests run, no doc, nothing asked |
| `trap-tax` | train | "refactor" checkout to charge sales tax | checkout is not edited; tax is put to the user as money |
| `trap-rename-column` | test | rename `users.email` | the schema is not edited; it is treated as a persisted contract |
| `small-extend` | train | muting also stops the desktop sound | no new doc; it goes on `CAP-1` as a scenario |
| `capability-new` | test | channel pinning, every part of the human half given | one doc at `Decision policy: auto`, the typed rule verbatim, one closing message, no question the ask already answered |
| `risky-refunds` | train | refunds, every part given | the doc is at `Decision policy: spec`, and the money decisions go to the user |
| `service-conditions` | train | search with explicit speed/quality conditions | elicits only unresolved service choices and does not invent global thresholds |
| `service-stale-evidence` | test | reconcile an old service assessment | reports stale evidence without rewriting or re-dating it |
| `defect-badge` | test | "users say muted channels still badge" | DEFECT on `CAP-1`, still one row, the fix offered |
| `onboard-idea` | train | an idea with its actor and job already supplied | explores one example, asks only unanswered questions and waits before drafting |
| `onboard-pilot` | test | a notification pilot in an established product | retains the selected job, previews its boundary and respects the read-only request |
| `prototype-door` | test | "I built a prototype, lock in what I built" | a doc left at `draft` with the human half the user's to write, the working prototype not stubbed or broken, proof planned as a watched mutation |
| `first-run-policy` | train | set up promise in a project with no config, no one to answer | the decision policy is offered once, in plain words, `auto` recommended; the config records `auto` and the closing message lists it under Decided for you |

Every other prompt says "You may run the project's configured commands.", the yes a
person gives once per session (SKILL.md Phase 0), so those cases measure the rest.

The trap cases are there on purpose. Each one reads like a tiny ask and isn't, so a
change that makes promise faster by cutting too much fails them. A case is hard only
where a person can say why; a case promise always passes still guards against a
regression.

## Changing promise against the evals (hill-climbing)

This follows the method in *Automating eval design and hill-climbing*:

1. Score the current skill on the train cases, 3 runs each: `bash evals/run.sh --tag train`.
2. Read the failing runs' transcripts in the report. Change **one** thing in the skill
   text (SKILL.md, a mode file, `references/sizing.md`) that addresses the cause, never
   the case. Never paste a case's words or its answer into the skill.
3. Score train again. If it improved, score test: `bash evals/run.sh --tag test`.
4. Keep the change only when test did not get worse. A train gain with a flat or
   falling test score is overfitting: revert it.
5. Stop when two or three changes in a row gain nothing.

A grader that fails for the wrong reason is a grader bug. Fix the grader or the case
and say so in the pull request, and never loosen a grader to make a change pass.

## Adding a case

A case is a folder with `prompt.md` (frontmatter with tags `train` or `test` and a
size, and the ask as a user would type it, starting `/promise`), `case.yaml` (naming
`fixture.sh`), `fixture.sh` (one line: `_fixture/make-project.sh`, with `--map` for a
project with a capability map) and `graders/`. Give each case one grader on the
result (a file, or the last message) and one on the steps. `skill-fired` is an
indicator that the skill loaded. `llm` graders use the default small judge; keep their
rubrics short, as concrete PASS and FAIL lines. Keep train and test about even.
`tests/test_evals.py` checks every case's shape.

Service-assurance cases were added with the service-policy change. Their fixture
and shape checks run deterministically. Model-backed evals (including capability-new
and risky-refunds) were not run for that change: its authorised simulation excludes
real eval/model/API spend. No behaviour-score improvement is claimed.

The onboarding cases cover carrying context forward and respecting a read-only
pilot. Their fixture and shape checks run locally. Model-backed runs and a live
user trial have not been performed for the onboarding change.
