---
type: file_exists
path: "docs/designs/*.md"
exists: false
arm: both
weight: 2
---
The behaviour belongs to the channel-muting doc and row: no new doc. `file_exists` counts
only files the run created, so the fixture's own `channel-muting.md` does not count.
