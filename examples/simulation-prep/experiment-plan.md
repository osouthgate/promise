# Experiment plan — run only after the service-level change is merged

**Completed as a scripted fictional exercise against the verified service-level merge.**
The procedure below is retained as the experiment plan; actual counts, traces and
limits are in [FINDINGS.md](FINDINGS.md).

## Question

Can Promise preserve useful, testable user outcomes and cross-cutting service
promises without a separate capability for every detail and excessive upkeep?

## Preparation boundary

The PRDs, input data, scenario catalogue and result stubs are ready in this folder.
They do not create real products or real evidence. Do not run real evals, call a
model or score the school reports. Any later Promise tooling consumes predetermined
results, labelled synthetic. Simulated owner decisions stay inside the exercise.

## Procedure for the later walkthrough

1. Pin the merged Promise commit. Record its version, grouping rules, service-policy
   format and commands. Keep the prep commit as the experiment's input baseline.
2. For ReportCheck, play a fictional owner from the PRD. Keep the initial jobs at
   their user-outcome grain; explicitly record which decisions were invented.
3. Draft the outcome documents and file map rows through Promise's normal workflow,
   rather than silently creating a hand-optimised map. Label every artifact synthetic.
4. Repeat for BorrowWorks. Use identical classification rules for both projects.
5. Translate the neutral service observations into the **merged** policy format.
   One shared policy can apply to several capability rows. Do not duplicate policies
   simply because several rows depend on them. Preserve a separately recorded
   functional result and service assessment.
6. Replay each project's initial, extension/regression and new-job/recovery stage
   using the stubs. A scripted false result must remain visible. New work with a
   `null` result is unchecked, not green. Do not promote a real verdict on a stub.
7. Compare three grouping strategies against the same cases: one row per detail;
   Promise's current job-grain rule including continuation rows after five scenarios;
   and a proposed relaxed job-grain rule if the current workflow creates friction.
   The third is an experiment, not an unapproved change to the framework.
8. Record concrete required edits and commands at each stage. Diagnose whether
   burden comes from job granularity, the five-scenario rule, evidence duplication,
   service-policy repetition or something else. Recommend changes only from that trace.

## Results sheet to fill during the walkthrough

| Project / stage / strategy | User jobs | Rows | Continuation rows | Scenarios | Shared service policies | Files edited | Repeated facts edited | Unchecked cases | Minutes or counted steps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Not run | — | — | — | — | — | — | — | — | — |

For the existing five-scenario rule, predict rows as the sum of `ceil(cases / 5)`
per job. Count one-detail rows as a deliberately bad comparison, not as current
Promise behaviour. For the relaxed hypothesis count one row per user job while
retaining every scenario and its separate evidence obligation.
These counts alone cannot establish usability; attach the actual editing trace.

## Counterexamples the later run must exercise

- A spelling variant adds data coverage, not a new user outcome.
- A sixth case may require a continuation row under current rules; record the cost.
- A defect restores an existing promise without inventing a new capability.
- A principal's or manager's new reporting job can justify a genuine new capability.
- A passing stub cannot substitute for missing, stale or failed service evidence.
- A fast answer with poor quality fails its quality condition. Better quality may
  justify the middle latency band, but never the hard maximum.
- A qualitative accessibility condition can be missing, pass or fail without a
  numeric score or an invented middle range. The fixture checklist is fictional;
  an actual standards audit has not happened.
- Request success ratio does not prove time-based uptime. Capacity observations
  must state offered load, time window and guardrails.
- Introduce a new service domain, such as a notification deadline, without treating
  the example domains as an exhaustive type list or creating a capability per policy.

## Adapter readiness checklist

- [x] Service-level PR merge independently verified and merged commit recorded.
- [x] Actual service-policy schema read; no pre-merge schema guessed from these fixtures.
- [x] Synthetic provenance survives translation and all generated reports.
- [x] False and unchecked results remain distinguishable.
- [x] Every scenario can be linked to its own fixed outcome; a shared lane is not proof.
- [x] No fixture outcome is published as a real capability verdict or audit finding.

## Review and stopping rule

Return two worked traces, counts, concrete friction and proposed changes to Oliver.
If Promise remains manageable, say so with the trace; do not manufacture a defect.
If broad grouping hides a distinct actor outcome or weakens evidence, reject that
relaxation. The objective is usable assurance, not fewer rows at any cost.
