Text the author wrote stays here.

<!-- promise:pr -->
## Where this is

- **Reports**: the reports a client reads and downloads.

**Needed from you:** read the two places under "Check these first", then merge.

## Words

- **Export**: download a report as a file.

## What changes for people

Before, the export button did nothing when a report was empty. Now it downloads an empty report and says so.

## Why

Closes #12. Clients pressed export and nothing happened.

Size: small — one new behaviour on C-2, the report download.

## Capabilities

- [C-2](https://github.com/o/r/blob/abc/map.json#L20) changed: an empty report downloads too. Verdict: proven → under-proven, until the new test is watched failing.
- [C-3](https://github.com/o/r/blob/abc/map.json#L40) new: the button says when a report is empty. Verdict: under-proven.
- Touched, verdicts unchanged: C-4.
- No row names: README.md, because it is a doc change only.

## Check these first

1. `src/export.ts:41`: the early return is gone.
2. `tests/export.test.ts:10`: the test for an empty report.

## Proof

- npm test: 42 passed, 0 skipped.

<details><summary>Full capability diff</summary>

| Row | Change |
|---|---|
| C-2 | changed |

</details>
<!-- /promise:pr -->

🤖 Footer text outside the block.
