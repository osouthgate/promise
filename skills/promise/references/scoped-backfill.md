# Backfill one selected workflow

Use with `modes/backfill.md`. A pilot follows its evidence and verification
rules within the boundary the user chose. A request to change the product is
`new`, `revise` or `intake`; backfill describes existing behaviour.

## Name the boundary before writing

Put the pilot boundary in the existing work item or PR description, beside its
result. Use one short table, not a second capability register:

| Boundary | Record |
|---|---|
| User job | Actor, outcome, included error and recovery paths |
| Entry points | Exact routes, pages, jobs or tools read from code |
| Tests | Exact suite or test selection and its JUnit output |
| Shared behaviour | Dependencies inspected and anything still unchecked |
| Outside this pilot | Named journeys and suites left for later |
| Exit check | What evidence the user needs to decide whether to expand |

Do not infer completeness from a folder name. A refund workflow may cross a
web route, a worker and a callback. Include those paths or call out the
uninspected boundary. A new dependency widens the proposed scope; show it before
claiming the pilot covers the job. Reuse explicit permission already given.

## Run the bounded pass

1. Read only the selected feature's tests, handlers and relevant existing docs.
   Inspect shared dependencies when they affect the job's outcome.
2. Use the project's test runner to produce JUnit for the selected tests.
   Retain failures and skips. For the entry-point list, use code-derived output
   from the configured surfaces command and document the exact pilot selection.
   Keep all in-scope entry points, including the ones that have no test.
3. Use the existing map and its feature IDs. Append or extend verified rows there,
   following the recipe. Never create a parallel pilot map or remove unrelated
   rows. Whole-product backfill still uses the full run and surfaces list.
4. Verify the pilot with the selected capability IDs, the bounded test export and
   the bounded surfaces file:

```sh
python3 skills/promise/scripts/map_report.py --map map.json \
  --row CAP-1 --row CAP-2 --junit pilot-results.xml \
  --surfaces pilot-surfaces.txt --orphans --fail-on-orphans \
  --fail-on-unmapped --fail-on-skipped --strict --json
```

The report labels the selection and keeps the original map digest. Test and
entry-point homes are checked against the full map, so shared callbacks can
belong to a supporting capability. The report lists those supporting IDs.
Verdicts are judged only for the selected capabilities; other citations on a
supporting capability need not run. Any failure in the supplied pilot run still
fails its strict check.

Tests and surfaces are exactly the inputs supplied; `--row` does not select tests
or trim a full JUnit export. A whole run can therefore expose unrelated failures
or unhomed tests. Produce the bounded export at the test runner, retaining every
in-scope result. Left-out notes for a file in that run remain checked even when
their test is missing. Notes for other files are counted outside scope.
Malformed entries remain visible. With no test run they remain unchecked.
When JUnit omits test file paths, keep left-out notes conservatively because
the report cannot establish which files lie outside the run.

For an existing map, first find the selected feature's orphan tests against the
full map and bounded run, then choose the pilot's row IDs after rows are filed.
For a first pilot on an empty map, that initial report identifies every supplied
test as unhomed. Keep evidence gaps as gaps until the selected rows account for
them. The independent verifier reads the same boundary and original exports.

## Show the result at its actual scope

Run `service_report.py` with the same repeated `--row` flags when services are
part of the pilot. The JSON records its selection. Policies without a selected
capability and service observations from other features are outside this assessment.
Invalid global inputs can still prevent a report; repair them in the normal path.

Pass the map and service JSON reports from the same map snapshot to
`render_map.py`. The page identifies selected capabilities and the limits of
their test and service inputs. Use the viewer for stories and evidence, then
ask whether the pilot was useful enough to expand.

Report gaps in the selected workflow separately from features outside the pilot.
No report establishes whole-product coverage from this bounded run. Keep
`map.requireHomes`, global surfaces discovery and existing CI unchanged.
The pilot does not disable unrelated checks or mark other features complete.
An observation becomes a promise only through the normal agreement path.
