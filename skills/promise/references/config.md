# Config — `.claude/promise.config.json`

*The user-facing contract for the config file. `scripts/orient.py` checks key names
against an allowlist and the types in the tables below; there is no JSON Schema.
`references/architecture.md` §6 shows a complete example, verbatim from
`templates/promise.config.example.json`. This file explains what a project gets by
setting each field, not how the scripts parse it.*

## Location and fallback

- Primary: `<project>/.claude/promise.config.json`
- Fallback: `<project>/promise.config.json`, read only when the primary path is
  absent
- **All fields are optional.** A project with no config at all is fully supported —
  every mode falls back to detection (see "Without a map" below, and the detection
  rules `references/architecture.md` §5 lists for `docsHome`, `plansFolder` and
  `commands`).
- **Unknown top-level fields warn**, they do not error — a typo or a field from a
  future version does not stop a run.
- **`"version": 1` names the shape of this file.** It is the only version this skill
  reads; any other value warns. A `$schema` key from an earlier config is accepted
  with a deprecation warning. `$comment` is ignored wherever it appears, at the top
  level or inside `commands` or `map` — it is never read as a field.
- **Paths are project-relative with forward slashes.** A path written with
  backslashes is normalised and warned about. A path that escapes the project
  (`..` or absolute) warns: `docsHome`, `plansFolder` and `frameworkPath` then fall
  back to detection or the bundled copy; `map.recipe`, `map.index`, `map.file` and
  `map.junit` are returned as written, since the map object is never rewritten.
- **A path a mode types into a shell holds only letters, digits, spaces and
  `. _ - /`,** and does not start with `-`. A `docsHome` that breaks this warns and
  falls back to detection, and `adopt` refuses it as `--docs-home`; a `map.junit`
  entry that breaks it warns, and `check.py` leaves it out.

## Trust model

Every `map.find`, `map.row`, `map.nextId`, `map.checks[]`, `map.surfaces` and
`commands.*` command runs as you, with your permissions, in this project's directory (`sibling.find` and `sibling.row`: in the sibling's checkout) —
exactly like a `package.json` script or a Makefile target; `check.py` runs
`map.checks` and `map.surfaces` the same way, as argv with no shell. Anyone who can commit to the repo can
change them. `adapter.py` protects against a hostile *query* (the text is one argv
element, never a shell string); it does not and cannot protect against a hostile
*config*. `/promise` prints the commands (`adapter.py show`) and asks before the first
run in a session; review them yourself in a repository you did not write.

## Fields

| Field | Type | Default when absent | What changes when it is set |
|---|---|---|---|
| `version` | the number `1` | Read as `1` | Nothing today. A later shape of this file will carry a different number, and `orient.py` will say which one it reads |
| `docsHome` | string, a project-relative path | The first existing of the common docs-folder names detection checks for; `null` if none exist. A detected folder that holds Markdown but no outcome doc is still returned, with a warning (`docsHomeForeignDocs` counts its files; the project's own framework copy is not counted), and `adopt` will not name it in a config or in `CLAUDE.md` without `--docs-home`: it refuses, with `--dry-run` and `--no-config` too | Pins where outcome docs live — every mode searches and writes there instead of relying on detection. The folder need not exist yet: `orient.py` warns that it is missing, and it is created only on the user's explicit choice (`new` passes `--create-docs-home` to `render_outcome.py`) |
| `frameworkPath` | string, a project-relative path | The framework bundled with this plugin | A project's own copy of the framework wins over the bundled one — use this when the project wants to own and edit its contract. A path that does not exist warns and falls back to the bundled copy |
| `plansFolder` | string, a project-relative path | `plans` if it exists, else `null` | Names a legacy plans folder so writing modes can offer to migrate still-live content out of it |
| `commands` | object — `typeCheck`, `test`, `lint`, each an argv line (split, run with no shell — see the `map` rows below) or `null` | Detected from the project's build tooling; a command with nothing detected is `null` | Pins the exact commands the writing modes run at hand-back through `adapter.py verify`, instead of relying on detection. Once a `commands` object is present, detection is off for all three — a key that is `null` or absent means "this project has none". Delete the whole `commands` object to return to detection |
| `run` | string, a command | none: agents run each script by its path in the skill's folder | How this project runs promise's scripts: a prefix an agent puts before `<script>.py <args>`, such as a wrapper pinned to one promise commit (`tools/promise-run.sh`). `adopt --run <cmd>` writes it in a fresh config, and the promise section names it, so an agent on a host where the skill never loads finds the scripts without searching. A value that is not a non-empty string warns and is left out |
| `minSkillVersion` | string, a version like `1.30.0` | none: any copy of the skill runs without a warning | The oldest promise skill this project expects. `adopt` writes the running skill's version (`VERSION` beside `SKILL.md`, which `orient.py` reports as `skillVersion`) in a fresh config. A copy of the skill older than it, or with no `VERSION` file, warns with both versions and how to update: the promise plugin, or `install_skill.py` from a current checkout. A value that is not a version warns and is ignored. A copy from before this key existed cannot compare versions: it warns only "unknown config key: minSkillVersion", which means the same thing |
| `decisionPolicy` | `fast`, `auto` or `spec` | `auto` | The repo's decision policy (framework § Decision policy): which product decisions the agent asks and which it decides and records in §8. Every new doc takes it into its `Decision policy:` header, and nobody is asked per doc; a person's own words for one doc ("write the full spec") override it for that doc. `adopt` asks it once, in plain words, and writes the answer (`auto` when no one answers); a human changes it here, once, for the whole repo. An old `prototype` is read as `fast` and orient warns; `upgrade.py` rewrites it to `fast` |
| `branch` | string: `current`, or a pattern holding `{slug}`, made of letters, digits and `. _ - /` around it, that git accepts as a branch name (no `..`, no leading `-`, no `.lock` ending) | `feat/{slug}` | Names the branch `arm` works on: the pattern with the doc's slug in place of `{slug}`, or `current` to stay on the branch the session is on, for a host that allows one branch per session (`upgrade` reads only `current`: any other value, it cuts `promise/upgrade-<version>`). `arm` creates the branch through a shell, so another value — whitespace, `$(…)`, a backtick, `;` — warns and the default applies. `adopt` never writes it |
| `map` | object (below), `false`, `null`, or absent | Absent | Turns on everything that depends on a machine-checked map — `arm`'s bridge step, `intake`'s and `reconcile`'s row-filing and citation steps, the duplicate-issue search. Absent is a fully supported, first-class configuration. `null` and absent mean no map yet: `arm` may offer the starter map. `false` means no map in this project, on purpose: no mode offers one (§ Without a map) |
| `sibling` | object — `repo`, `path`, `find`, `row`, four strings; read only beside `"map": false` | none | Names the sibling repository whose map holds this project's rows, read-only (§ Without a map). `path` is its checkout, from the project root (`../name`); `find` and `row` are argv lines as in the `map` object, which `adapter.py find` and `row` run with that checkout as the working directory. No other map operation runs there, and nothing writes there. `orient.py` reports it as `sibling` (with `mapUsable` still false: the project has no map of its own, so every writing mode takes its no-map path) and warns when no checkout is at `path`; beside any other `map`, or with a key missing, it warns and is ignored |
| `protectedPaths` | a list of project-relative path patterns: a glob (`*` crosses folders, as in `infra/*.tf`) or a folder ending in `/` (`billing/`), which covers everything below it | none | Names the paths a change sized tiny may not touch, beside the ones `changed_rows.py` always refuses for tiny (a row's scenarios, a doc's §0 or §6, a migration or schema file). `changed_rows.py --size tiny`, or `--body` with a pull request whose `Size:` line says tiny, exits 1 when the diff touches one. A value that is not a list of strings warns and is left out. `adopt` never writes it |
| `pinFiles` | a list of objects, each a project-relative `path`, a `pattern` (a regular expression whose first group, or whole match, is the value: `"REF=([0-9a-f]{40})"`), a `kind`: `sha` (the default) or `version` (`"REF_VERSION=(\\d+\\.\\d+\\.\\d+)"`), and `vendored: true` for the file that records a vendored copy's commit | none: the one pin is `.claude/settings.json`'s promise marketplace `source.ref`, a release tag (Claude Code reads `ref`, never a `sha` there) | Names the other places this repository pins promise, such as a wrapper script's `REF` and `REF_VERSION`. `pin_check.py` reads every site and exits 1 when two disagree (two commits, two versions, or a tag's commit against a sha), or a site's file or pattern finds no value; `upgrade.py` moves them all at once (`modes/upgrade.md`), but never a `vendored` site alone: it refuses until the copy is synced, since the sha would name a release the copy does not hold. `adopt` never writes it |
| `upstreamPath` | string, a path to a local promise checkout (from the project root; `~` expands) | none: upstream is read over the network, with no credentials | For a private upstream: `pin_check.py`, `upgrade.py` and `pin_machine.py` read upstream through this checkout's `origin`, with that checkout's own git access, and fetch a commit it lacks into it (objects only; none of its branches move). No token passes through the scripts. `PROMISE_UPSTREAM_PATH`, or `--upstream-path`, names one per machine instead, and wins. The path must be a checkout's own root, not this repository; git there runs with no prompt and ignores a hook's `GIT_DIR`. A named checkout that cannot be used is said so, never skipped for the network |

A `commands` or `map` value that is not an object warns and is treated as absent (`"map": false` aside:
it is a choice, not a slip, so it does not warn); a path field that is not a string warns and falls back to detection. `orient.py` does
not check that a configured command exists — a wrong command is found by the first
mode that runs it, as an exit 127 from `adapter.py`.

A freshly adopted config (below) carries `"version": 1`, the skill's own version as `minSkillVersion`,
all three `commands` keys (an undetected one as `null`, so the pinning is visible), and `map` as
`null` with a `$comment` pointing back here; a `null` map is the same as leaving the key out.

### The `map` object

Present only when the project keeps a machine-checked register of promises — its
own, or one started from the skill's starter. The starter is
`templates/starter-map/` (an empty `map.json`, its stdlib reader
`capability_find.py`, and a `recipe.md`); `scripts/start_map.py` copies it into the
project (`docs/capabilities` unless `--dest` says otherwise) and writes this object
for it. It refuses a config that already has a `map` object, writes nothing on
`--dry-run` or a refusal, and after it the three files are the project's own.
`arm` offers it when the first doc is agreed; `adopt` offers it when an agreed doc
already exists (`outcome-framework.md` § Lifecycle, F9). `examples/minimap/` at the
plugin root runs the same reader over three example rows, so `arm`, `adapter.py`
and `bridge_validate.py` can be watched doing the bridge.

**`map.recipe` is the authority for mechanics** — which files a row touches, what
its lockstep rule means, what a citation looks like there. No mode file restates a
project's mechanics; each says "read the recipe, work from the file." Whether
anything is filed, and at what size, is the skill's (`references/sizing.md` § How big
a row is), not the recipe's. Look in the recipe for the parts a mode will ask for by name: a **routing table** (which
relation a piece of feedback becomes), the **lockstep rule** (which files move
together, and in what order), a **lane table** (how a `Then`'s altitude picks a test
kind), a **verification block** (the commands to run before calling anything done),
and a **shipped-work section** — the mirror direction, code landed and a row needs
updating.

| Key | Meaning |
|---|---|
| `recipe` | Path to the project's how-to for writing a row. Authoritative for mechanics, per above. `orient.py` warns when the file does not exist. |
| `index` | Path to the project's own reference for the map's shape — what each backing file is, what the evidence arrays mean, what each checker does and does not see. Read it alongside the recipe when the recipe assumes a concept — an evidence-array name, a checker — that this index actually defines. `orient.py` warns when the file does not exist. |
| `find` | An argv line, not a shell command: it is split like a shell would split it and run with no shell, and the query is appended as one extra argv element (`adapter.py find <query>`, or `--query-file <path>` when the query lives in a file). Pipes, `&&`, `VAR=x` prefixes, `cd` and globs are not interpreted — they arrive as literal arguments or fail with exit 127. Put such logic in a script in the repo and name that script here. |
| `row` | An argv line (as above); the row id is appended as one element (`adapter.py row <id>`). |
| `nextId` | An argv line, run with no argument appended, that prints the id the next new row would take. |
| `learn` | Optional. An argv line (as above) that records the words `find` missed a row by, as one of the row's asks; `adapter.py learn --query-file <path> --row <id> --source <source>` appends those three flags, each value one argv element. The starter reader's is `python3 <dir>/capability_find.py learn`. `intake`, `issue` and the lookup rule run it when the row they settled on was not ranked first. `orient.py` warns when it is not a command string. |
| `refsSync` | Optional. An argv line that records, on each row, the merged pull requests (and the issues they close) whose promise block names it, and adds each pull request that names one row to the eval fixture; `adapter.py refs-sync --input <path>` appends the JSON file of merged pull requests. The starter reader's is `python3 <dir>/capability_find.py refs sync`. `reconcile` runs it, so no CI job needs write access. |
| `code` | Optional. An argv line; the row id is appended as one element (`adapter.py code <id>`, checked against `rowIdPattern` first). It prints the local files the row's cited tests import, as JSON. The starter reader's is `python3 <dir>/capability_find.py --code`, which follows Python and JS/TS imports one step. A mode reads those files before a wide code search. |
| `rowIdPattern` | A regular expression every row id must match. `orient.py` warns when it does not compile. The starter map's ids all start `CAP-`, so one grep finds every row and no everyday word (`GPT-4o`, `i18n`) reads as one. After it comes the older counter (`CAP-12`) or the item the row came from: an issue, a pull request or a Linear issue (`CAP-i1890a`, `CAP-p2091a`, `CAP-ENG-421a`), up to two letters after the number (702 rows an item): `^CAP-(\d+\|[ip]\d+[a-z]{1,2}\|[A-Z][A-Z0-9]+-\d+[a-z]{1,2})$`. A map started before 1.25 has `^CAP-\d+$`; widen it to take the new ids. Rows 1.25 wrote without the prefix (`i1890a`) are renamed `CAP-i1890a`; `--check` names each one. |
| `lanes` | An object mapping the four altitudes plus `sibling` to the project's own evidence-array names. This is what lets `references/altitude.md` stay generic — a mode cites "the lane the altitude picks," and `map.lanes.<altitude>` is where that array name comes from. |
| `checks` | An array of argv lines, each run with no shell, in order, at the end of `arm`, `intake` and `reconcile`, before the mode hands back, and as `check.py`'s own checks step, so the map's shape is part of the local gate. Optional, but a project with no checks writes `[]` explicitly: with the key absent, `adapter.py checks` refuses with exit 2 (`map.checks is not configured`), and the modes run it only when a map is configured and `checks` is set — a refusal is reported as not run, never as a failed check. |
| `issueTracker` | Optional. An object `{ kind, repo, template }` of three strings naming the project's issue tracker; `template` is the issue template's path (`adopt` offers `templates/github/`, copied to `.github/ISSUE_TEMPLATE/capability.md`). When present, `intake`, `reconcile` and `issue` search it — by row id and by the promise in plain words, open and closed — before filing anything new, and `changed_rows.py` links rows on a `github` `repo`. |
| `file` | Optional. The path of the map's own JSON file, which `scripts/check.py` hands to `map_report.py`. Without it, `check.py` locates a starter map by rule: when `find` is the starter reader (`python3 <dir>/capability_find.py`, optionally with `--map <path>`), the map is `<dir>/map.json` (or that path); any other `find` needs `file`. `orient.py` warns when the file does not exist. |
| `junit` | Optional. A path, or a list of paths, to the JUnit XML files or folders this project's test commands write; `orient.py`'s `testRunners` names the flag that makes each detected runner write one. `check.py` joins the ones that exist to the map, names the ones not written yet (those tests have not run), and skips that step when none exists -- unless the orphan check is asked for (`--fail-on-orphans` or `requireHomes`), which then fails for want of a run. A lane whose suite is in none of the files joined (no citation of it matches, and the run holds no file, title or folder it cites, nor a subfolder of one) reads `not-run`: named once in the report, never proof, and not a `--strict` failure; list that suite's file here to have it checked. |
| `surfaces` | Optional. The command that prints the code's entry points, one per line, in the project's own notation (`GET /me`, `page /settings`); blank and `#` lines are ignored. An argv line (split as above) or an argv array used as written, such as `["node", "tools/list-entry-points.mjs"]`. `check.py` runs it from the project root, with no shell and a five-minute limit, and `map_report.py --surfaces` lists every entry point no row names in its own `surfaces` field; a mode that needs the list runs it the same way through `adapter.py surfaces --out <file>`, never typed into a shell. A failing command or an empty list fails that step. |
| `requireHomes` | Optional, `true` or `false` (default). `true` makes `check.py` fail on a test in the run with no row and on an entry point with no row, and fail when `surfaces` is not set or no `junit` run exists. A test left without a row on purpose goes in the map's `leftOut` list (the recipe shows how): one entry per test, by its exact title, with a one-line reason and a date. |

A map counts as configured only when `recipe`, `find` and `row` are strings and
`lanes` is an object of strings — the `mapUsable` rule `references/architecture.md`
§5 states. A map missing any of these is reported by `orient.py` as `map incomplete:
missing …` with `mapUsable: false`; every mode then treats it as no map, `adapter.py`
refuses map operations (exit 2, naming the missing keys) and `bridge_validate.py`
reports `MAP_NOT_CONFIGURED` with the same keys named — neither works from a partial
map. A missing `recipe`, `index` or `file`, a
`checks` value that is not an array of strings, an `issueTracker` that is not three
strings, a `junit` that is not a path or a list of paths (or escapes the project),
a `surfaces` that is neither a command string nor a non-empty array of strings, a
`requireHomes` that is not a boolean, and a `rowIdPattern` that does not compile each warn without changing
`mapUsable` — the map a project configured is the map every script sees. `check.py`
prints each of these warnings on its own line before its steps, and fails its map
step on a `requireHomes` that is not a boolean: a slip that turns a gate off never
reads as a pass.

Scripts read `find`, `row`, `nextId`, `learn`, `refsSync`, `code`, `rowIdPattern` and `checks` (`adapter.py`,
`bridge_validate.py`), and `checks`, `file`, `junit`, `surfaces` and `requireHomes` (`check.py`). `recipe`, `index`, `lanes` and `issueTracker` are read by the
modes, from the file, never by a script.

## Without a map

Each writing mode has a fully defined behaviour when `map` is absent, `null`, or
incomplete (`mapUsable: false`), and each states "no map configured" in its Phase 0
line:

- **`arm`** writes the acceptance rows as red tests and nothing more. There is no
  bridge step, no not-built row is filed anywhere, and there is no row id to write
  into a `Row` column.
- **`intake`** matches feedback against the outcome docs already in `docsHome` —
  specifically their §6 (Acceptance) rows — instead of a map, and files its routing
  table into the doc itself: §6 for a new or extended row, §9 (Open questions) for a
  decision.
- **`reconcile`** updates the doc only: it re-stamps §0's rule tags and the
  `Scenarios:` count, and appends a dated §8 entry. There is no evidence array to
  cite into and no kill witness to record, because there is no map row to promote.

`null` or absent means no map yet, and `arm` offers the starter map when a doc is
agreed. `"map": false` means this project keeps no map, on purpose — for example,
its promises are rows in a sibling repository's map. Set it by hand. Then:

- `orient.py` reports `"map": false` and `mapUsable: false`, with no warning (bar a
  `sibling` with no checkout), and each mode's Phase 0 line says "no map, on purpose".
- `arm`, `adopt` and `backfill` never offer the starter map, and `start_map.py`
  refuses (exit 2) until a person sets the value to `null`.
- `check.py` skips its checks and map steps with that reason, and fails its gate step
  for a `shipped` doc with a §6 line no red run or `Kill:` line covers, since no row can prove it; a `--junit`
  or `--surfaces-cmd` fails the map step; `bridge_validate.py` reports
  `MAP_NOT_CONFIGURED` with that reason.
- Every writing mode behaves as described above for a project with no map.

With a `sibling` object beside it (the Fields table), the bullets above still hold,
with one narrowing: sizing, `intake`'s match step, `issue` and `pr` read the sibling's rows through `adapter.py find` and `row`. They
name the rows a change keeps or extends, file nothing locally, and say under
**Needs you** which row in which repo needs the change. With no checkout at `path`
they say so under **Not checked** and size as without a map. A row has one home.

## Adopting in a project

The fast path is **`/promise adopt`** (`modes/adopt.md`). It runs
`scripts/adopt.py`, which writes `.claude/promise.config.json` if one is not already
there — `"version": 1`, `minSkillVersion`, `docsHome`, the three `commands` keys as detected, and
`map: null` with a `$comment` pointing back to this file — and inserts, or on a
later run replaces, a short section in the project's `CLAUDE.md` between
`<!-- promise:begin` and `<!-- promise:end -->` markers. That section is what routes
every person and agent in the project to `/promise` instead of a hand-written
design, plan or spec doc — see `references/architecture.md` §13 for the script's
exact contract. Adopting never overwrites an existing config, never creates a docs
folder unprompted (a folder is created only on the user's explicit choice), and the
`CLAUDE.md` edit never touches anything outside its own markers; the section itself
is rendered from a template, never hand-written.

`orient.py` reports an `adopted` boolean in its JSON — true only when a config was
loaded **and** the `CLAUDE.md` section exists — and warns `project not adopted — run
/promise adopt` when it is false. Every mode's Phase 0 line states it, and offers
`adopt` once per session when it is false, continuing with the requested mode either
way.

### Adopting by hand

The same outcome as `/promise adopt`, done manually — for a project that wants to
write its own config without the script:

1. **Pick `docsHome`.** Use an existing docs folder, or decide where outcome docs
   will live if the project has none yet.
2. **Optionally copy the framework.** The bundled framework works as-is; copy it
   into the project — and point `frameworkPath` at the copy — only when the project
   wants to own and edit its own contract.
3. **Write the config** at `.claude/promise.config.json`, starting from
   `templates/promise.config.example.json` and deleting what does not apply. Most
   projects start with no `map` at all.
4. **Run `scripts/orient.py`** and read its `warnings[]`. An unknown key, a
   wrong-typed field, a path that escapes the project or uses backslashes, a
   `docsHome`, `frameworkPath`, `map.recipe`, `map.index` or `map.file` that does
   not exist, a detected `docsHome` with no outcome doc in it, an incomplete `map`,
   a `rowIdPattern` that does not compile, a malformed `checks`, `issueTracker`,
   `junit`, `surfaces` or `requireHomes`, a `branch` that is neither `current` nor a `{slug}`
   pattern, a `version` other than `1`, and a deprecated `$schema` key
   all surface here before any mode runs. orient does **not** check
   that the configured commands exist — a wrong command is found by the first mode
   that runs it.
5. **Run `scripts/lint_outcome.py` over `docsHome` once**, and read what it finds.
   Docs written before this config existed will not conform on the first pass —
   that is the adoption cost, not a bug.
