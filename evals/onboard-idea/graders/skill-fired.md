---
type: regex
target: trace
pattern: "skills/promise/"
arm: with-only
---
The promise skill ran. `/promise` loads the skill's text as a slash command, which the
trace does not record, so this looks for the run reading or running something under the
skill's folder instead: a mode file, a reference, orient, the adapter or
`session_report.py`, which even a tiny ask runs. An indicator only.
