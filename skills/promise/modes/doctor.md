Read before this: references/config.md and references/service-targets.md.
Phase 0 line: mode `doctor`, the project root, and whether Doctor can locate a capability map.
Writes: nothing. Report local evidence and ask before adopting or changing anything.

# Doctor

Run `python3 "${CLAUDE_SKILL_DIR}/scripts/doctor.py" --cwd <project> --json`.
If the map uses a custom layout, use `--map <file>` inside the project root.
For a sibling map, use its own project root.
Use `--observations <export.json>` only when the user supplies a service observation
export. Read the files directly. Do not run project commands or collect telemetry.

Show availability in the running copy, the repo's configuration, and observed
evidence separately. Cite the map, the supplied export and relevant policy or row
IDs. Keep unknown, invalid, synthetic, stale and missing evidence distinct.
An unacceptable result still shows that a measurement occurred. A supplied
assessment records the assessor's judgement. A local run does not establish the
origin or truth of supplied observations.

Use the recommendations as review prompts. Repeated stories, continuations and
identical policies are evidence of possible maintenance work. Ask which user
outcomes differ before suggesting a move. Retain coverage, current sizing rules
and the proof attached to each capability. Do not propose changes from row counts
alone or infer team behaviour from missing files. Compare roots, continuations,
scenarios, declared surfaces and policy links together. A map's declared surfaces
describe that map's coverage. Ask about missing journeys or complexity before
drawing a conclusion about the whole project.

For a pin or version change, use `modes/upgrade.md`. Its dry run uses the same
inventory. Upgrading a pin makes features available. Choosing to configure a
service policy or collect observations is a separate project decision.
