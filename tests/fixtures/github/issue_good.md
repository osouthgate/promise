<!-- promise:intro -->
## Where this is

- **Reports**: the reports a client reads and downloads.

**Needed from you:** one decision, under "Decisions needed".

## Words

- **Export**: download a report as a file, such as a PDF.
<!-- /promise:intro -->

## What we want

Clients see an export button that does nothing.

<!-- promise:issue -->
## Capability check

Read: docs/designs/export.md.

- **The export button does nothing.** DEFECT [C-2](https://github.com/o/r/blob/abc/map.json#L20) (proven): a client downloads their report as a file. The button no longer sends the request.
- **Export as a spreadsheet too.** NEW-ROW: no row promises a spreadsheet; C-2, the report download, stops at a PDF.

## Gap

The button's handler returns early when the report is empty (src/export.ts:41). The spreadsheet format does not exist.

## How to build it

1. Reproduce it, add a red test for C-2 S1, the download, fix the handler, then `/promise reconcile` C-2, the export row.
2. `/promise new` for the spreadsheet export; a human agrees it; `/promise arm`, build, `/promise reconcile`.

## Decisions needed

- [ ] Is a spreadsheet export worth building this quarter? (owner: Ollie)
<!-- /promise:issue -->
