# Promise simulation: useful grouping, with two concrete sources of friction

Both fictional workflows were exercised against the merged service-level implementation.
Promise kept user jobs much smaller than a row-per-detail map. The five-scenario
ceiling still split one unchanged job in each project, and shared service references
then expanded with those continuation rows. A separate control confirmed that a
lane-green report can conceal a missing scenario citation; the existing manual
per-scenario rule remains essential.

**Scope:** actual local Promise tools processed fictional projects and fixed stub
outcomes. No product, UI, model eval, accessibility audit or live service ran.
All stored functional verdicts remain `not-built`. A computed `proven` in a raw
parser report means only that the supplied stub citations matched; it is not proof
of either product. Historical service outputs are explicitly replay, not current
compliance.

## Version and reproducibility

The recorded findings were collected with Promise skill version **1.39.1**.
The public replay uses the tools from the checked-out commit and records that
commit in the output. It makes no network calls.

From the repository root:

```sh
python3 examples/simulation-prep/stubs.py --check
python3 examples/simulation-prep/run_simulations.py
python3 -m unittest discover -s tests -p test_simulation_replay.py -v
```

The walkthrough runs in two temporary git sandboxes. [The runner](run_simulations.py)
records every actual command, stdout, stderr and exit code in the per-project
traces. The generated `results/summary.json` records grouping counts, classifications
and file edits. Test times, service generation times and temporary paths can differ
on replay; compare conclusions and structured counts, not byte-identical logs.

## What ran, and what was role-played

| Step | Actual execution | Simulated input or boundary |
|---|---|---|
| Orient and map setup | `adopt.py --no-claude-md`, `start_map.py`, `orient.py`, `adapter.py show` | Bounded fixture commands were authorised for this exercise. No real project's agent instructions changed. Adoption intentionally omits the agent-routing file. |
| New job | `render_outcome.py`, `outcome` lint, map id allocation through `adapter.py next-id` | Fictional owner words, decisions and `agreed` status are labelled fixture inputs. |
| Arm bridge | Map grouping and §6 links were assembled, then checked with `bridge_validate.py --strict --linking` and `adapter.py checks` | The human red-gate decision was role-played, not actually given. No real implementation or production mutation exists; no real `building` or `shipped` transition is claimed. |
| Intake | Local lookup with `adapter.py find` and `row`; appended cases and continuation rows; actual change reports | NEW-JOB, EXTEND and DEFECT calls are the experimenter's simulated product judgement, recorded in stage summaries. |
| Functional reconciliation | `adapter.py verify` ran standard-library unittest stubs; `map_report.py` joined their JUnit output | Every result was fixed true/false/unchecked. Judgement and perception citations point at scripted stand-ins, not model or rendered-surface evidence. No real verdict promotion or kill witness. |
| Service reconciliation | The merged `service_report.py` processed actual-schema synthetic exports and assessments | Historical `--replay --now` is used only for fictional evidence. Assessment conclusions are supplied, not independently checked. |
| Shared-policy change | A sandbox commit changed one policy; `changed_rows.py` identified every referring row | The policy revision was fictional. It was restored in the final snapshot, not ratified as a product requirement. |

The command traces contain **73 ReportCheck** and **81 BorrowWorks** actual local
commands, including sandbox git bookkeeping and the negative controls. This is a
reproducibility count, not a measurement of a normal user's effort or model cost.

The [worked conversations](WORKED-WALKTHROUGHS.md) record the fictional owner reasoning
and the new / intake / reconcile decisions for both projects.

## Capability growth observed

| Project and stage | Distinct jobs | Scenarios | One row per detail | Current Promise rows | Continuation rows | Relaxed job-grain hypothesis |
|---|---:|---:|---:|---:|---:|---:|
| ReportCheck initial | 3 | 12 | 12 | 3 | 0 | 3 |
| Add review cases and scripted regression | 3 | 14 | 14 | 4 | 1 | 3 |
| Add principal summary and scripted recovery | 4 | 15 | 15 | 5 | 1 | 4 |
| BorrowWorks initial | 4 | 16 | 16 | 4 | 0 | 4 |
| Add reservation cases and scripted regression | 4 | 19 | 19 | 5 | 1 | 4 |
| Add manager report and scripted recovery | 5 | 20 | 20 | 6 | 1 | 5 |

Current job grouping finishes with **11 rows for 35 scenarios**, rather than 35
rows. The relaxed hypothesis keeps **9 jobs and all 35 scenarios**. That removes
only two continuation rows in this sample; it is not evidence that this change
alone solves a real register containing thousands of capabilities.

The atomised final maps actually pass the starter reader's structural checks.
That checker cannot decide whether a human outcome has been fragmented into
implementation details. Conversely, both relaxed maps actually fail with
`scenarios must be a list of 1-5 entries`. The relaxed result is therefore a
**proposed experiment, not supported current behaviour**. No checker was loosened.

### ReportCheck worked trace

- Initial jobs are import a batch, review findings, and prepare teacher feedback.
  CSV columns, spelling, grammar and copied text are cases inside those jobs.
- Adding benign phrases and same-student revision handling expands review from
  five to seven cases. The current rule creates a child row with the same story.
- A fixed false result in feedback-decision preservation makes one row visibly
  failing. It adds no scenario or capability: the promise already exists.
- A principal's year-wide summary has a different actor outcome, so it creates a
  genuine new job. Its `null` stub result is skipped/unchecked, never green.

### BorrowWorks worked trace

- Initial jobs are reserve equipment, decide a restricted booking, complete a
  loan, and keep unsafe equipment out of circulation.
- A waiting list, offer expiry and keyboard booking expand reservation from four
  to seven cases. Promise needs a continuation row despite the unchanged job.
- A scripted cross-site approval failure belongs to the existing refusal case.
  Repairing that fixed result does not require a capability for “fix approval”.
- A manager's utilisation report is a genuine new reporting outcome; it remains
  unchecked in the final stage rather than inheriting another lane's pass.

## Maintenance observed

Each extension/regression stage changed three authored fixture inputs: the map,
fixed results and service observations. Each new-job/recovery stage changed those
three plus its new outcome doc. Generated JUnit output and the lookup query are
listed separately from authored inputs. Initial outcome docs stayed unchanged
when later scenarios were appended to the map, respecting the frozen §6 snapshot.

This bounded example did **not** require repeatedly rewriting every document.
It does not measure manual authoring time: the runner wrote files automatically.
The concrete friction is the extra row identity, parent link, scenario ids,
citations and policy references created at the sixth case. Removing the row limit
would not remove any scenario or evidence obligation.

## Service promises exercised

Five shared definitions were used in each fictional project: conditional interactive
response, request success ratio, throughput under offered load, fictional keyboard
conformance, and a prepared-output deadline. These are examples, not a closed
catalogue. The deadline uses the general assessment adapter without adding a new
domain type or a capability devoted to the policy.

| Input or change | Observed report result |
|---|---|
| Fast result with baseline quality | `target` |
| Slower result with the stronger quality condition | `acceptable`, with separate duration and relevance values |
| Hard time limit, even at high quality | `unacceptable` |
| Fast result below the quality floor | `unacceptable` |
| Request ratio over fixed complete buckets | Target classification; explicitly request availability, not time-based uptime |
| Zero request traffic | `insufficient`, never a pass |
| Completed throughput with enough offered load and latency guardrail | Target classification for that scoped input only |
| High throughput with insufficient offered load | `unacceptable` guardrail result |
| Qualitative assessment absent / fixed failure / fixed pass | `missing` / `unacceptable` / supplied target assessment |
| Missing or stale observations | `missing` or `stale`, independent of passing functional stubs |
| Obsolete policy revision | `invalid-evidence` |

A single qualitative policy edit touched one map file and appeared against all
five ReportCheck rows or six BorrowWorks rows in actual change reports. Shared
criteria were not copied. This part works as intended.

Continuation rows still multiply applicability references and row-specific evidence:

| Final grouping | ReportCheck policy references | BorrowWorks policy references |
|---|---:|---:|
| One detail per row | 44 | 65 |
| Current job grouping with continuations | 14 | 19 |
| Relaxed job-grain hypothesis | 11 | 14 |

The definitions stay at five per project. The additional eight references across
the two continuation chains are administrative expansion, not eight new service
promises. Do not simply reuse a passing assessment across unrelated jobs; evidence
must still cover each affected journey.

## Evidence-grain control

Removing one response-scenario citation while leaving another passing citation
in that row's lane still gives a computed `proven`. This reproduced in both
projects. The map's recorded verdict stays `not-built` throughout.

This behaviour is already disclosed in [the pinned proof taxonomy](../../skills/promise/references/altitude.md#the-verdict-rule).
It is not a newly discovered undocumented regression. Broader capability grouping
makes per-scenario proof tracking more important, not less.

The source rules checked for this run are the [job and continuation sizing rule](../../skills/promise/references/sizing.md),
[per-scenario reconciliation rule](../../skills/promise/modes/reconcile.md),
and [shared-policy change rule](../../skills/promise/references/service-targets.md).

## Recommendations for Oliver — not implemented

1. **Make the five-scenario boundary a review trigger, not an automatic new
   capability identity.** Keep a stable user-job row with navigable scenario groups.
   Split when the actor's outcome or assurance boundary changes. Before: review
   findings plus a child row after case five. After: one review-findings capability
   containing all seven cases and their distinct evidence. This preserves the
   user-level map while reducing the observed continuation overhead.
2. **Add a grouping challenge before filing a row.** Require “new actor outcome”
   versus “case/limit/bug of an existing outcome”, show the nearest existing row,
   and let the person disagree. The rules already say this; the structurally valid
   detail maps show why shape validation alone cannot enforce it. Do not add a
   capability for every rule, format variant, test or service policy.
3. **Make per-scenario evidence visible in the normal report.** A lane-green state
   should not read as scenario proof. This is especially necessary before allowing
   larger rows. Retain independent functional proof and service assessment views.
4. **Apply shared service policies to stable capability identities, with explicit
   scoped evidence coverage.** A navigation group or continuation should not create
   another business commitment merely to satisfy a scenario-count ceiling.

### Decision options

- **9/10 — trial relaxed job grouping together with explicit per-scenario evidence
  (recommended).** It addresses the observed row and evidence friction without
  deleting cases. Implement as a separately reviewed framework change, then rerun
  these exact inputs and one real-project sample.
- **7/10 — retain the ceiling and collapse continuation rows in the human view.**
  Lower schema risk, but underlying ids and policy references still multiply.
- **4/10 — leave the current workflow unchanged.** Valid when maps are manageable,
  but the reproduced continuation and lane-level interpretation costs remain.

No framework rule, schema, reporter or default was changed by this experiment.
The next step is Oliver's choice; these synthetic projects do not justify silently
rewriting the framework or declaring real implementations assured.
