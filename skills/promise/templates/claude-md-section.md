<!-- promise:begin (managed by the promise skill; run /promise adopt to refresh it) -->
## Capability work goes through the `promise` skill

- `/promise` in Claude Code, `$promise` in Codex, the `promise` skill in Cursor; plain words.
- **Size every ask first** (the skill's `references/sizing.md`). Tiny — no release-note line: copy, styling, a refactor,
  config, a fix to what a row already promises — needs no doc, no row, no question (but a session's first-command yes): build it, keep its tests green.
  Small goes into its doc or row; a new capability or a protected category gets a new doc. In doubt, the larger. "Ship it first" is deferred: build now, the PR says `Size: deferred — owes: …`, `reconcile` pays it later.
- Decisions follow the config's `decisionPolicy`, set once for the repo. Batch, don't interrupt: decide what is reversible,
  keep working, end with one message — Needs you (`decisions.py sheet`, on the surface it names; a rich one `--out`
  published as an Artifact with `db`, never a chat list or the sheet's files), Decided for you (with undo), Not checked.
- No `promise` skill loaded (a cloud session, any other agent)? Read its `SKILL.md` and `references/quickstart.md`; scripts run as {runScripts}.
- One doc per capability lives in {docsHome}, in the Outcome Framework shape ({frameworkPath}).
- §0 is the human's verbatim block; an agent only appends numbered notes below it. `agreed` and `shipped` are typed by a human;
  `building` only after the human approves the red-test commit.
- A capability map, once configured in {configPath}, is the source of scenarios after a doc is `agreed`;
  §6 is then a snapshot. A verdict moves only when evidence reaches the altitude its `Then` claims.
- What the product does starts at the map (row, verdict, tests, code); so do `/promise issue <n>` and `/promise pr`.
- Every ask (a sheet, a reply, an issue, a pull request) says in plain words what it is and what to choose; an id (`Q2`, `AT-3`, `#87`) never stands alone.
- Run `/promise` before any design, plan or spec doc; one written by hand outside it is a bug.
<!-- promise:end -->
