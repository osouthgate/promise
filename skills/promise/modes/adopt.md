Read before this: references/config.md
Phase 0 line: mode `adopt` (say if inferred), framework source, docs home and its source, `claudeMd.path` and `hasPromiseSection`, whether a config is loaded (and from where), orient's `mapUsable`, `adopted`, `claudeMd.sectionCurrent` and `githubTemplates`.
Writes: `.claude/promise.config.json` (only if absent) and the `<!-- promise:begin -->…<!-- promise:end -->` section of `CLAUDE.md` (created if absent, else replaced in place) — both only through `scripts/adopt.py`, never by hand; and, when the human takes the starter-map option, the starter map and the config's `map` object, only through `scripts/start_map.py`; and, when the human takes the CI option, `.github/workflows/promise.yml`, copied from `templates/promise-ci.yml`; and, when the human takes the GitHub text option, `.github/ISSUE_TEMPLATE/capability.md` and `.github/pull_request_template.md`, each only if absent, only through `scripts/adopt.py --github-templates`; and, on the human's yes to stamping the open docs with no policy line, that line and a §8 row in each, only through `scripts/decisions.py policy --open`.

# Adopt — route the project through `/promise`

A project is **adopted** once it has a config (§6) and its `CLAUDE.md` carries the
promise section, so every person and agent working there is routed to `/promise`
instead of writing a design, plan or spec doc by hand. The section may live in
`AGENTS.md` instead, when `CLAUDE.md` imports it (a line `@AGENTS.md`) or there is no
`CLAUDE.md`: orient's `claudeMd.sectionPath` names the file that holds it. `scripts/adopt.py -h` states
exactly what the script writes; this mode is the conversation around running it.

**One yes, not seven.** Each choice below has a **(Recommended)** option. Take them
all, show one dry run that covers every file they write (the config and section,
the starter map, the CI workflow, the GitHub templates), and ask once; the user
can drop any item in their reply. Ask a choice on its own only where the
Recommended option does not apply (a foreign docs folder, two plausible maps).
A fresh config it writes carries `decisionPolicy` — the repo's decision policy,
chosen here once (§ Ask the decision policy) — and `minSkillVersion`, this skill's
version, so an older copy of the skill warns in this project. An existing config is
never rewritten (§ Show the current state says what to do about its missing keys).

## Show the current state

Read Phase 0's JSON and show, in one line each: `claudeMd.path` and
`hasPromiseSection`, whether a `config` was loaded (and from where), and `adopted`.
Already `adopted` and `claudeMd.sectionCurrent` true → say so and stop; nothing below
needs to run, except the two notes below. Adopted with `sectionCurrent` false → the section is from an
older release, or null (the begin marker sits mid-line, or its stamp cannot be read): run § Run
the script for the block alone, show its diff, and refresh it on the yes (text adopt did
not write is kept: `movedAboveBlock`; text it cannot place is refused with its lines).

**Keys an existing config lacks.** The loaded config has no `decisionPolicy` or no
`minSkillVersion` → one line under Needs you, adopted or not, naming the key and the
line to add by hand (`"decisionPolicy": "auto"`, `"minSkillVersion": "<skillVersion>"`).

**Open docs with no policy line.** Orient's `legacyPolicyDocs` above zero →
put one line under Needs you, adopted or not: "N open docs predate the repo's
policy and behave as spec; say so and I will stamp them". Not adopted yet → the
policy and docs home are only detected here: ask it in the closing message, once
`adopt.py` has written the config. On the human's yes, and never before the config
exists, run `decisions.py policy --open --to <the config's policy> --by "<name>"`. It
stamps each open doc that has none (the line and a §8 row) and leaves the
edits for the human to commit. A doc with no line still
reads as `spec`; only that yes writes the lines.

## Ask the decision policy

A person chooses the policy knowingly, in the same one ask. Ask it only when
`adopt.py` is about to write a fresh config; a config that has `decisionPolicy`
is never asked again. One standalone ask (`references/decision-sheet.md`, the
form of `examples/onboarding/asks.json`), **(Recommended)** first:

- **Ask only the risky things** (`auto`, **Recommended**). Reason: the agent
  decides cheap, reversible local choices and records each; it always asks about
  money, security, contracts and the other protected categories.
- **Ask me everything** (`spec`). The agent decides nothing alone.
- **Let me move fast** (`fast`). The agent decides all but the protected categories.

Pass it as `adopt.py --policy <auto|fast|spec>`. No answer, or a host that cannot
ask → `auto` (the default), under **Decided for you**: "Decision policy set to
`auto`; change `decisionPolicy` in `.claude/promise.config.json`."

## Confirm the docs home

Put the docs home to the user as a choice, **(Recommended)** first, each with one
concrete reason:

- **(Recommended)** — Phase 0's own detection (`docsHome` / `docsHomeSource`).
  Right whenever a docs folder already exists and holds outcome docs.
- `docsHomeForeignDocs` is above zero → the detected folder holds docs in another
  shape, and the lint would fail on every one of them. **(Recommended)** instead: a
  new folder whose name does not sit next to it (for example `docs/promises` beside a
  `docs/design`), passed as `--docs-home`. With no `--docs-home`, any run of
  `adopt.py` that would name the foreign folder refuses (exit 2): the dry run, the
  real run, `--no-config`, and `--agents-md`, since the `CLAUDE.md` or `AGENTS.md`
  block would send every agent there. With a config already loaded, it asks for
  the config's `docsHome` to be set instead. The legacy docs move in later, one
  capability at a time (`modes/backfill.md`).
- A different existing folder the user names. Right only when detection picked
  the wrong one.
- A new folder. Only on the user's explicit choice (the one ask above) — this skill
  never creates one unprompted. Pass it as `--docs-home <dir>` so the config pins it; `new` creates
  it (`render_outcome.py --create-docs-home`) the first time it writes there.

`docsHomeSource` is `none` → the detection option does not exist; the
**(Recommended)** option is then a new folder (default `docs/designs`, passed as
`--docs-home docs/designs`), because without it the config pins nothing and every
later `new` asks again.

## Decide whether to configure a map now

A capability map is where this project's promises add up: one row per story, the
tests that prove it, an honest verdict — the map of the platform. The framework
treats it as the goal (`outcome-framework.md` § Lifecycle); the only question here
is when it starts. Read `existingDocs` from Phase 0, then put one of these first:

- The config already sets `map` to `false` (no map in this project, on purpose;
  `references/config.md` § Without a map) → offer no map and no `backfill`; keep it.

- The project already keeps its own register of promises and the tests that prove
  them → **(Recommended)** configure `map` to point at it after the script below
  runs. A map counts as configured (orient's `mapUsable`) once `recipe`, `find`,
  `row` and `lanes` are set; `nextId`, `checks`, `rowIdPattern` and `issueTracker`
  are optional — `references/config.md` names every key.
- Any doc in `existingDocs` is `agreed`, `building` or `shipped` → **(Recommended)**
  start the starter map now, after the script below: show
  `python3 "${CLAUDE_SKILL_DIR}/scripts/start_map.py" --dry-run`, and run it without
  `--dry-run` on yes. Reason: the project already has a promise a human agreed,
  and it has nowhere to be counted. Its rows are filed the next time `arm` or
  `reconcile` touches the doc.
- The product already has code and tests (orient's `testRunners` is not empty, or
  the user says so) → **(Recommended)** start the starter map now, as above. Reason:
  `backfill` needs a map to file rows in, and `map.junit` and `map.surfaces` live
  inside it.
- Otherwise → **(Recommended)** leave `map` null. `arm` offers the starter map when
  the first doc is agreed, which is when there is a real promise to put in it.

## Run the script

```
python3 "${CLAUDE_SKILL_DIR}/scripts/adopt.py" --dry-run [--docs-home <dir>] [--policy <auto|fast|spec>]
```

Show the diff it prints — the config it would write (if one is absent, with
`"version": 1` as its first key) and the `CLAUDE.md` section it would insert or
replace. On the user's yes, run the same command without `--dry-run`. A dry run
that exits 2 wrote nothing and has no diff to approve: act on what it names (most
often `--docs-home`), then run the dry run again. On a project that already has a
config, a `--docs-home` that disagrees with its `docsHome` is refused (exit 2):
change the config, not the flag, so `CLAUDE.md` and the config never name
different folders. The block holds a section the template never wrote → the script
keeps it, unchanged, just above `<!-- promise:begin` (`movedAboveBlock`); list it
under **Decided for you**. Text it cannot tell apart exits 2 with its lines: ask the
human to move it out of the markers.

## Offer AGENTS.md

When the project has an `AGENTS.md`, or the user works with Codex, Cursor or another
agent besides Claude Code, offer one file for every agent: **(Recommended)** when
`AGENTS.md` exists, the section in `AGENTS.md` and a `CLAUDE.md` that imports it (a
line `@AGENTS.md`). Claude Code reads the import, and reads `AGENTS.md` by itself
when there is no `CLAUDE.md`; the script finds the section there and refreshes it
there, never a second copy in `CLAUDE.md`. To move a section that is in `CLAUDE.md`
now: move the lines from `<!-- promise:begin` to `<!-- promise:end -->` into
`AGENTS.md`, leave `@AGENTS.md` in `CLAUDE.md`, and run the script. The other choice
is `adopt.py --agents-md`: the same block in both files. It is skipped when
`CLAUDE.md` and `AGENTS.md` are the same file. For those
agents, also mention `install_skill.py --project . --git-hook`: they have no hook
before an edit, so the §0 check runs at each commit instead.

## Offer the CI check

Once, after the script has run: offer `.github/workflows/promise.yml`, a copy of
`templates/promise-ci.yml` as it stands. With no `docs-home` input the Action reads
`docsHome` from the config, as a local `check.py` does, so the two never lint
different folders. On every pull request it lints the docs and fails when §0 of an
`agreed`, `building` or `shipped` doc changed without going back to `draft`
(`diff_outcome.py`). Mark it
**(Recommended)** only when the project already has `.github/workflows/`; otherwise
offer it in one line. Reason: the plugin's hook stops the model editing an agreed
§0 in a session; CI checks every change, whoever made it. The file exists → say so
and write nothing. Never write it without the yes.

## Offer the GitHub templates

Once, after the CI offer, and in a `"map": false` project too (a sibling's rows still
need the blocks): offer the issue and pull request templates, copied by
`adopt.py --github-templates` (with the dry run's diff) into `.github/`, each only where
orient's `githubTemplates` says the project has none. Each carries an empty promise block that `issue` and `pr` fill, so every
issue gets checked against the map before anyone builds it, and every pull request
names the capabilities it moved (`references/github-text.md`). **(Recommended)** when
the project is on GitHub. A file already there → write nothing, and say that `issue`
and `pr` add their block to whatever body the project's own template gives. With a
map, name the `map.issueTracker` object for the user to add to the config —
`{"kind": "github", "repo": "<owner>/<repo>", "template":
".github/ISSUE_TEMPLATE/capability.md"}` — since this mode writes the config only
through its scripts. Never write the templates without the yes.

## Offer the rest of the set-up

One line each, in the same one ask as above; write nothing without its yes. This mode
writes the config only through its scripts, so none of these edits the config here:

- **One branch per session.** A host that lets a session push only to its own
  branch → name the line `"branch": "current"` for the user to add to the config
  (`adopt` never writes `branch`: `references/config.md`), so `arm` does not cut
  `feat/<slug>`.
- **JUnit output and entry points.** `map_report.py` and `backfill` need a run and a
  list. `map.junit` and `map.surfaces` are keys of the `map` object, so they wait for
  a map: added to a `null` map, either leaves an incomplete map that `start_map.py`
  refuses. Once a map exists, name the flag orient's `testRunners` gives for each
  runner found; `backfill` sets both keys, with the user's yes, when it starts.
- **The product already exists.** Code and tests → offer `backfill`,
  **(Recommended)**, once the map exists, so untested code shows as a gap.
- **No Actions.** The project cannot run the Action → offer `scripts/check.py` as a
  local step (a package script or a pre-push hook): the same lint and §0 check,
  plus the map's own checks and the map joined to a run when a map is configured.

## Verify

Run `python3 "${CLAUDE_SKILL_DIR}/scripts/orient.py"` again; show `adopted: true`.

## Rules

- **Never overwrite an existing config.** `adopt.py` refuses to; a config is
  already there → say so and move on to the `CLAUDE.md` section alone.
- **Never edit `CLAUDE.md` outside the `<!-- promise:begin` / `<!-- promise:end
  -->` markers.** Everything else in the file is the project's own.
- **The block is rendered from `templates/claude-md-section.md`, never
  hand-written.** The block needs to say something the template does not → that is
  a template change, not a one-off edit.

## Close out

Paste the inserted (or replaced) `CLAUDE.md` block verbatim. List the files
written. Say what was left undone — most often, `map` still `null`, and that `arm`
will offer the starter map when the first doc is agreed (never with `map: false`) —
and whether the CI check and the GitHub templates were added.
