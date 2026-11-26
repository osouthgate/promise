# Service assurance across capabilities

These examples are illustrative, not real telemetry, real audits or recommended
service levels. The [map](map.json) defines shared project-level policies; its
capability rows reference them. The [observations](observations.json) are separate
from tests and from the policies themselves.

From the repository root:

```bash
python3 skills/promise/scripts/service_report.py --map examples/service-targets/map.json --observations examples/service-targets/observations.json --replay --now 2026-11-04T12:00:00Z --json --strict
```

| Capability | Policy | Expected service result |
|---|---|---|
| Search | Quality/time | acceptable: 800 ms at baseline quality, 5000 ms at stronger quality |
| API requests | Request availability | target: all observed requests succeeded; not a claim about time-based uptime |
| Loaded service | Throughput under offered load | acceptable: 90–100 completed requests/s under observed offered load of 120 requests/s, retaining the latency guardrail |
| Search and checkout | One shared accessibility policy | target, as supplied by the explicitly illustrative assessment for each capability; the reader has not performed an audit |

All functional verdicts stay `not-built`: no test citations have been supplied.
The service observations do not promote them. The tiny sample minimum is for a
readable fixture, not adequate statistical evidence of a production SLA.

Drop the slow search's quality below its condition, make its duration 10000 ms,
or break a capacity guardrail, and the service becomes `unacceptable`. Return
`acceptable` for the pass/fail accessibility policy and it becomes `invalid-evidence`:
there is no such criterion. Evidence for search alone leaves checkout `missing`,
even though both reference one policy.

Omit both `--replay` and `--now` to assess current freshness: this historical
evidence becomes `stale`. Replay results never establish current compliance. Without
`--observations`, it is `missing`. Neither is acceptable. See the
[service-assurance contract](../../skills/promise/references/service-targets.md)
for fields, boundaries, freshness and the limits of automatic evaluation.

For a large availability cohort, see [the bounded bucket format](../../skills/promise/references/service-targets.md).
The collector exports complete cohort counts and condition extrema per time bucket;
the report does not require an object per request. Export and record limits are
explicit. Never cut the cohort down to fit them.
