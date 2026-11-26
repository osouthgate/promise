# BorrowWorks — fictional medium-sized project brief

**Synthetic PRD for a future Promise simulation; not an agreed outcome contract.**
The fictional owner answers and policies are exercise inputs, not real authority.
No bookings, messages or payments are made.

## Problem and outcome

A community workshop lends equipment across several sites. Members need reliable
reservations; coordinators need to approve restricted equipment and track returns;
maintenance staff need unsafe equipment removed from circulation. BorrowWorks
should let those people complete a loan without two members receiving one item.

## Actors and journey

A member selects a site, equipment and a time slot. Eligible reservations are
confirmed; restricted equipment waits for coordinator approval. The coordinator
records collection and return, including damage. Maintenance staff quarantine
and release equipment. A cancellation releases capacity and notifies the affected
people in the fictional workflow, without sending any real message.

Use [synthetic equipment and reservations](../fixtures/equipment.json). The inputs
include two simultaneous reservation attempts and one unavailable item so the
walkthrough has permission, concurrency and failure cases beyond the happy path.

## Initial user jobs and candidate grouping

| Job | Why the actor needs it | Cases that belong together |
|---|---|---|
| Reserve equipment | Members can rely on a usable booking | Available slot; collision; cancel; ineligible member |
| Decide a restricted booking | Coordinators can permit the right member | Approve; refuse; wrong site; already cancelled |
| Complete a loan | Coordinators can account for each item | Collect; return; late return; damage |
| Keep unsafe equipment out of circulation | Maintenance staff can prevent unsafe loans | Quarantine; pending booking; clear inspection; attempted collection |

Notifications are initially consequences of these jobs, not a new row per channel.
A notification centre with an independent user outcome might warrant its own job;
the later experiment must make that distinction explicit.

## Planned evolution

1. Add a waiting list, automatic offer expiry and a keyboard booking flow. Decide
   whether they extend the reservation job before adding any capability.
2. Script a regression in cross-site approval. Reuse the existing refusal scenario;
   do not file a new row for a bug that restores the same promise.
3. Add a workshop manager's utilisation report for equipment purchasing decisions.
   This is a candidate new job. No purchase or payment is performed.

## Illustrative service promises

- Reservation and approval share an availability definition over a stated window.
- A capacity promise states offered concurrent demand and completed throughput,
  with latency and error guardrails. Quiet-system throughput proves no peak capacity.
- Reservation and loan completion share response-time bands; a hard limit cannot
  be traded away for quality.
- All member and coordinator journeys share accessibility conformance with named
  scope, standard version and verification method; a Boolean assessment need not
  have a numeric quality score.
- Notification delivery deadlines illustrate a different kind of time promise.
  The fixture never sends messages or claims real delivery.

These examples are deliberately non-exhaustive. Later simulation inputs can add
another measurable or qualitative promise without inventing another capability
for every policy or modifying an exhaustive list of service domains.

## Non-goals and later simulation questions

No booking engine, queue, calendar, UI, auth, database, real messages, billing,
telemetry collection or live performance test is built. Payments remain out of
scope. Exercise initial adoption, requirement changes, fixed failures and recovery,
unknown service domains, and shared policies spanning several capabilities.
