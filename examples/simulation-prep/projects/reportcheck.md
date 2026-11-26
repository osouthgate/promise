# ReportCheck — fictional project brief

**Synthetic PRD for a future Promise simulation; not an agreed outcome contract.**
All product-owner choices below are invented experiment inputs. No real school,
student or teacher data is used. GDPR compliance is an assumption of this fixture,
not a compliance finding or a substitute for a real assessment.

## Problem and outcome

Teachers prepare grades and narrative reports in CSV files. A head of year needs
one review queue before returning clear corrections to each teacher. The fictional
product should help the head of year catch mistakes without automatically changing
or sending student reports.

## Actors and journey

- Teacher: uploads their CSV and receives their own reviewed feedback.
- Head of year: reviews findings, records a decision, and prepares teacher outputs.
- School administrator: configures the review period and participating teachers.

A teacher uploads the [synthetic reports](../fixtures/teacher-reports.csv).
Invalid rows are explained before the batch is accepted. The checker flags spelling,
grammar, inconsistent grades and suspicious text shared across different students.
The head of year accepts, dismisses or amends each finding. Each teacher then gets
one export containing only that teacher's reports and the review decisions.
The simulation stops at a prepared export: it sends nothing.

## Initial user jobs and candidate grouping

| Job | Why the actor needs it | Cases that belong together |
|---|---|---|
| Import a review batch | Teachers can submit reports without silently losing rows | Valid input; missing columns; malformed grades; duplicate student rows |
| Review report findings | The head of year can correct reports without trusting every flag | Spelling; grammar; grade consistency; copied text; dismissed false positive |
| Prepare teacher feedback | Each teacher can act on the right review decisions | Teacher separation; decisions included; unresolved findings block a final export |

These are **grouping hypotheses**, not capability-map rows already filed. A spelling
rule or a CSV column is not automatically a separate capability. The later walkthrough
must record where Promise agrees, requires a continuation row, or finds another job.

## Planned evolution

1. Add benign common phrases and a same-student report revision. These refine copied
   text detection under the review job; they are not two new user jobs.
2. Script a regression: a dismissed warning reappears as accepted in the export.
   The intended route is a defect against an existing promise, not a new capability.
3. Add a principal's year-wide review summary. This introduces a different actor's
   outcome and is a candidate new job, to be argued during the walkthrough.

## Illustrative service promises

Targets are invented experiment inputs, not globally agreed thresholds.

- The interactive review experience has a response-time target and a hard upper
  limit. A slower result is acceptable only when the declared quality condition holds.
- The import path has a capacity promise under an explicit batch size and concurrency.
- The review and export surfaces share an accessibility-conformance promise with
  a named standard, version, scope and verification method chosen in the simulation.
- Reports and exports share an availability or successful-request promise; the
  measurement definition must distinguish elapsed uptime from request success rate.

No numerical score is required for qualitative conformance. A middle band exists
only when the fictional owner supplies a meaningful acceptance condition.

## Non-goals and later simulation questions

No real checker, CSV application, rendering, export generator, authentication,
student storage or messaging is implemented. No automated compliance claim is made.
During the simulation, ask how repeated cases are parameterised, whether the sixth
review scenario causes a new row, and whether shared service rules multiply rows.
