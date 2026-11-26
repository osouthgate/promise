# Two fictional Promise workflow simulations

**The fictional workflow simulation is complete. No application is implemented and no real evaluation has run.**

Read [the findings and recommendations](FINDINGS.md) for the counts and conclusions.
Every person, dataset, answer, test outcome and service observation here is synthetic.
The stubs can test the mechanics of the Promise walkthrough; they cannot prove
that either fictional product works or meets a service promise.

| Project | Brief | Synthetic input |
|---|---|---|
| ReportCheck: teacher report review | [PRD](projects/reportcheck.md) | [Teacher reports](fixtures/teacher-reports.csv) |
| BorrowWorks: shared equipment bookings and loans | [PRD](projects/borrowworks.md) | [Equipment and reservations](fixtures/equipment.json) |

[The experiment plan](experiment-plan.md) records the walkthrough procedure and its
stop conditions. [The fixture manifest](fixtures/workflows.json) holds jobs,
scenarios, proposed changes and predetermined outcomes. The neutral fixture format
is deliberately **not** Promise's capability-map or service-policy schema.

## What can run now

From the repository root:

```sh
python3 examples/simulation-prep/stubs.py --check
```

This checks only fixture integrity: ids, references, types and stated synthetic
provenance. It does not assess product quality, run an eval, invoke a model, or run
the full Promise simulation. It uses the Python standard library and no network.

`fixed_result(project, stage, scenario)` in `stubs.py` returns a declared Boolean
or `None` (not checked), without inspecting the supplied school or equipment data.
`fixed_service_observations(project, stage)` returns the declared fake observations.
These functions are the adapter boundary for the replay runner, not product
implementations. A false result is a scripted broken case, not a discovered bug.

## Completed after the verified service-level merge

The [replay runner](run_simulations.py) uses the checked-out commit, creates the synthetic
outcome docs/maps, runs actual local framework checks, and exercises fixed failures,
unchecked cases and service observations. See the findings for role-played human
gates and the exact limits. Run it with `python3 examples/simulation-prep/run_simulations.py`.
The runner writes a local, ignored `results/` directory with a `summary.json` and
per-project traces. Use `--out` to write to a different directory.

Do not mark fixture scenarios `proven`, call a scripted failure a kill witness,
or treat a fictional owner's answer as Oliver's permission. Real Promise
lifecycle changes remain human-controlled. The findings distinguish actual parser behaviour from scripted product outcomes;
they do not establish real product assurance.
