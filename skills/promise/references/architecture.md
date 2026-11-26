# promise — architecture of the skill

*The durable spec for how this skill is built. Read this before editing any file in
`skills/promise/`. It is also the brief every contributor (human or agent) builds
against, so its interfaces are exact, not illustrative.*

---

## 1. Purpose

`/promise` carries a capability from **intent to proof** in one skill:

1. An **outcome doc** records the promise before anything is built — the human half
   verbatim and protected, the agent half derived (the Outcome Framework).
2. Where the project keeps a **capability map** — a machine-checked register of promises
   and the tests that prove them — the doc's acceptance rows become **rows** in that map
   when the doc is `agreed`, and the map becomes the source of the scenarios from then on.
3. **Arm** writes the acceptance rows as red tests. **Reconcile** moves a row's verdict
   only when the evidence reaches the altitude the row's own `Then` claims. **Intake**
   files feedback against existing promises instead of spawning new documents.

The Outcome Framework is how a promise is written down. The capability map is how the
project proves it kept it. This skill is the router over both.

## 2. Decisions this shape rests on

| # | Decision | Why |
|---|----------|-----|
| S1 | **One skill, thin router, mode files loaded on demand, scripts for mechanics.** Not a set of sibling skills; not one monolith. | Claude Code routes subcommands in prose only (`$0` is the word; there is no frontmatter dispatch) and documents no skill-to-skill call, so a router of sibling skills would have to duplicate the contract into every sibling. A single large file would load every mode's instructions on every run although the modes are mutually exclusive, and would exceed the ≤500-line SKILL.md guidance. |
| S2 | **Config over fork.** The plugin is generic. A project supplies `.claude/promise.config.json` (§6). No project-specific path, command or vocabulary is hard-coded anywhere in this skill. | One implementation serves every repository; a project supplies only what differs. A per-project fork of the skill is a second copy of the contract, and two copies of a contract drift apart. |
| S3 | **The framework wins.** `outcome-framework.md` beside SKILL.md is the contract for the doc: section rules, lifecycle, review rubric; the skeleton is `templates/outcome-doc.md`, which the framework points at. A project copy at `config.frameworkPath` wins over the bundled one. Mode files cite framework sections by number; they never restate them. | One home for the doc contract, and the mode files stay short. |
| S4 | **After `agreed`, where a map exists, the map is the source of scenarios.** §6 of the doc cites the map's rows (a `Row` column); it does not carry a second, independently edited copy. §0's rule tags keep the doc-local `AT-n` aliases, which are stable and append-only. | One promise, one home. A copy made at `agreed` would drift the day after. |
| S5 | **Scripts are Python 3, standard library only, invoked via `${CLAUDE_SKILL_DIR}`.** One implementation runs on every OS. The router invokes `python3`; if that is not on PATH it retries with `python`, then `py -3`, and uses the first spelling that runs for every script that session. The load-time preamble ends in `\|\| true` so a missing interpreter cannot abort the skill before this fallback is read. No `.sh`/`.ps1` parity pairs. | A parity pair is two implementations of one behaviour. Markdown parsing in shell is unreliable. |
| S6 | **Mechanical steps are scripts; judgement is prose; decisions are made in front of the user.** Sub-agents may rank, read and draft. They never decide a routing, a verdict move, a merge, or a status change. A verdict move that the rule settles (a watched kill at the `Then`'s altitude) is reported under Decided for you rather than asked. | Delegating enumeration is free; delegating a decision loses the reason it was made. |
| S7 | **Every shape rule of the framework has a check in `lint_outcome.py`** (§9), and the check runs at the end of every writing mode. The lint checks shape, not truth: whether §3 holds an example, whether §9 questions carry an owner and a BLOCKING flag, whether §4 invariants name an enforcement point, whether `Last decision:` is a real date, and whether a filled line is *true* are not checked — each writing mode says so in one line, so the author reads those sections themselves. | A rule that is only written down is advisory; a rule with a check is enforced. The lint makes the framework's shape rules hold in every doc, not only in the ones a careful author wrote. |

## 3. File tree (exact)

```
promise/                                  ← the repo root: the plugin and its own marketplace
  .claude-plugin/plugin.json  .claude-plugin/marketplace.json
  .github/workflows/tests.yml             ← the test suite on every push and pull request
  .github/workflows/release-tags.yml      ← tags each release on main v<version> and moves the major tag (v1): the ref a repository pins
  .github/scripts/release.sh              ← what that workflow runs, and a maintainer by hand when Actions cannot: the tag, v1, and the GitHub release from changelog_entry.py; --all, --check
  .pre-commit-hooks.yaml                  ← promise-section0 and promise-lint for the pre-commit framework
  action.yml                              ← the GitHub Action: lint_outcome.py and diff_outcome.py on a project's pull requests
  hooks/
    hooks.json                            ← the plugin's PreToolUse hooks: on Edit, MultiEdit and Write; on GitHub writes and gh; and the mod's module
    decisions-pane.js                     ← a Claude Code mod: the decision pane (decisions.py sheet --json in, apply - out), the tool decision_pane and /promise-decide
    precommit.py                          ← the §0 check and the lint before a commit, for agents with no PreToolUse hook
    guard_section0.py                     ← blocks a model edit to §0 of an agreed doc (diff_outcome.compare); fails open
    guard_github_text.py                  ← blocks an issue or pull request body whose promise block fails the lint, and asks before a new one with no block; fails open
  LICENSE            README.md            CHANGELOG.md
  evals/                                  ← behaviour evals for `claude plugin eval` (README.md, run.sh, _fixture/, one folder per case); their shape is checked by tests/test_evals.py
  examples/                               ← runnable, outside the skill; linted and exercised by tests/test_examples.py
    channel-muting.md                     ← one conforming outcome doc: Altitude column, §10 owners, lint exit 0
    backfill-moved.md                     ← a legacy design doc moved into an outcome doc at draft: the pending-confirmation line, quoted rules, an Open — Qn field
    key-tabs.md                           ← a doc under Decision policy: auto: three provisional agent decisions in §8 (the sheet's "Decided for you") and a protected one asked as a §9 question
    transcript.md                         ← a short annotated session: Phase 0 line, mode inference, one interview turn, one lint finding, the pasted §0
    proofmap/                             ← a six-row map with a JUnit run (run/): every outcome map_report.py can show
    decisions/asks.json                   ← an asks file with every item kind, for decisions.py sheet over channel-muting.md
    minimap/                              ← a tiny capability map: map.json, capability_find.py (find / --row / --next-id / --eval / learn / refs sync / --code), find-eval.json, promise.config.json, recipe.md, README.md, docs/designs/ with the bridged doc
  skills/promise/
    SKILL.md                              ← router. ≤ 150 lines. Frontmatter + contract summary + mode table + dispatch + Phase 0.
    VERSION                               ← the plugin's version, so a vendored or linked copy of the skill carries it; orient.py reports it as skillVersion
    outcome-framework.md                  ← THE contract for the doc (contract, section rules, decision policy, lifecycle, rubric, decisions F1–F12); the skeleton itself is templates/outcome-doc.md
    modes/
      new.md        revise.md    review.md    merge.md
      arm.md        intake.md    reconcile.md    backfill.md    adopt.md
      issue.md      pr.md        retro.md       upgrade.md       doctor.md    onboard.md
    references/
      architecture.md                     ← this file
      slates.md                           ← outcome-line slate + signal slate procedures; rules are never slated
      service-targets.md                  ← open-ended service assurance: policies, numeric bands, qualitative criteria and dated evidence
      altitude.md                         ← the proof taxonomy: signal kinds ↔ altitudes ↔ lanes ↔ what counts as evidence
      anti-rationalizations.md            ← the excuse/reality table, all modes
      config.md                           ← user-facing contract for .claude/promise.config.json
      quickstart.md                       ← for any agent: the words, the commands in order for a new project and for a backfill, the decision loop, hosts where the skill never loads
      scoped-backfill.md                  ← a selected workflow, bounded report inputs and explicit limits before expanding adoption
      decision-sheet.md                   ← decisions left for the human: pick the surface (rich sheet or question prompt), the asks file, apply
      research.md                         ← a big backlog of decisions: triage packets, research agents' piles, merge-research
      sizing.md                           ← size the ask first (tiny / small / capability / risky); batch, don't interrupt
      github-text.md                      ← the issue and pull request blocks: the reader's path, plain words, relation → route, what the lint checks
    templates/
      outcome-doc.md                      ← the §0–§10 skeleton, ONE canonical shape
      promise.config.example.json         ← every field, with comments in a sibling `$comment`; §6 shows it verbatim
      claude-md-section.md                ← the ≤20-line block `adopt` inserts into a project's CLAUDE.md (§13)
      decision-sheet.html                 ← the decision sheet page: decisions.py embeds the sheet; saves to an Artifact's db, or copies answers
      promise-ci.yml                      ← the workflow `adopt` offers: runs action.yml on pull requests
      github/                             ← ISSUE_TEMPLATE/capability.md and pull_request_template.md: what `adopt` offers for .github/, each with an empty promise block
      starter-map/                        ← map.json (no rows), capability_find.py (its reader; examples/minimap runs the same bytes), recipe.md — what start_map.py installs (§13)
    agents/
      openai.yaml                         ← Codex skill metadata (same skill, second host)
    scripts/                              ← Python 3, stdlib only (S5)
      orient.py                           ← Phase 0: resolve framework, config, docs home, commands, existing docs → JSON (§5)
      lint_outcome.py                     ← shape checks over one doc or a directory → findings, exit code (§9)
      outcome_rows.py                     ← extract §0 rules+tags and §6 rows (with altitude) as JSON; the bridge's input (§10)
      adopt.py                            ← write the config and the CLAUDE.md section, idempotently (§13)
      framework_section.py                ← print named `## ` sections of the resolved framework; modes read sections, not the file
      adapter.py                          ← run one configured command; the caller's text is one argv element, never a shell string (§14)
      render_view.py                      ← render a read-only outcome document as local HTML or structured JSON
      render_map.py                       ← render all capabilities and optional service reports as a local HTML page
      render_outcome.py                   ← instantiate templates/outcome-doc.md (--thin: the human half only; --policy: the decision policy the human picked); refuses to overwrite; makes the docs folder only with --create-docs-home
      bridge_validate.py                  ← a bridged doc's Row ids, snapshot line and Then text against the current map (§10)
      start_map.py                        ← install templates/starter-map/ and fill the config's map object; never over an existing map (§13)
      service_report.py                   ← separate dated service observations and supplied assessments; never changes functional verdicts
      map_report.py                       ← the map joined to a JUnit run and the code's entry points: a bucket and an altitude verdict per row, recorded vs run (§14)
      install_skill.py                    ← link or copy this skill into .agents/, .codex/ or .cursor/skills; --git-hook for other agents
      diff_outcome.py                     ← §0 before vs after (two files, or a git ref): S0_CHANGED on a ratified doc not set back to draft (§14)
      changed_rows.py                     ← the map at a change's merge base against its head: rows added, changed, removed or touched, docs, files no row names; --link prints row links (§14); --size/--body checks a tiny claim against the diff
      map_features.py                     ← the map's `features` and a row's `feature`, or the alias `areas` and `area`; the error FEATURE_AND_AREA for both (shared by lint_github_text.py and changed_rows.py)
      lint_github_text.py                 ← the promise block of an issue or pull request body: sections, budgets, plain words, rows named (§14)
      decisions.py                        ← sheet: open §9 questions + an asks file + the §8 agent decisions ("Decided for you") → one sheet, a surface hint, the page; apply: answers → one §9 line each, an "Ask me instead" → a new §9 question; promote, policy, recheck: agent decisions put to the human, the policy the human picked, the arm re-check (§14)
      junit_unittest.py                   ← runs a stdlib unittest suite and writes JUnit XML, each case with its file, class and method, so the map can join it
      session_report.py                   ← a Claude Code session's transcript → what it did with promise, as facts and signals, and each recorded run's size and stops (--record); --scrub, --scrub-check for a draft issue (modes/retro.md)
      pin_check.py                        ← the repository's promise pin against upstream's newest release tag (one git ls-remote): up to date, N releases behind, not reachable, or pins that disagree (exit 1); notices for a sha pin Claude Code does not read, a branch ref or moving tag, a promise section not from the pinned template, and a machine not on the pin; reads a private upstream through a local checkout (upstreamPath); changes no file (modes/upgrade.md)
      doctor.py                           ← read-only feature inventory and setup advice for the project
      upgrade.py                          ← the repository half of an upgrade: every pin site to a release tag (settings' source.ref, pinFiles shas and versions), the config keys a config lacks, minSkillVersion; prints what the project's recipe and reader lack of the starter map's; --dry-run prints the diff; never commits
      pin_machine.py                      ← the machine half: re-declares the marketplace at the pinned ref and updates the plugin (claude plugin …), puts back a settings file Claude Code only reordered, and checks installed_plugins.json is the pinned commit
      deferred.py                         ← the promise work owed: merged pull requests whose block says Size: deferred and has no Paid: line (through gh, or --input); changes nothing (references/sizing.md § Deferred)
      post_github_text.py                 ← post an issue or pull request body with gh only when its block passes lint_github_text.py, then read back what GitHub stored (--verify alone)
      check.py                            ← what the Action checks, as one local command, in six steps: lint, §0 against a base ref, the §6 lines no red run or kill covers, the map's own checks, the entry-point list, and the map joined to a test run (§14)
  tests/                                  ← `python3 -m unittest discover -s tests` (§12)
    test_scripts.py  test_shape.py  test_lint_hardening.py  test_acceptance_columns.py
    test_status_authority.py  test_followups.py  test_intake_phrases.py  test_prototype_door.py  test_kill_record.py
    test_adapter_render.py  test_orient_render.py  test_bridge_validate.py  test_examples.py
    test_adopt_hardening.py  test_packaging.py  test_start_map.py  test_thin_draft.py
    test_service_report.py  test_simulation_replay.py  test_render_view.py  test_render_map.py  test_doctor.py
    test_diff_outcome.py  test_map_report.py  test_check.py  test_other_hosts.py  test_row_ids.py
    test_github_text.py  test_changed_rows.py  test_agents_md_home.py  test_decisions.py  test_find.py  test_junit_unittest.py
    test_session_report.py  test_parallel_ids.py  test_decision_policy.py  test_sizing.py  test_evals.py  test_skill_version.py
    test_sibling_map.py  test_premise_checks.py  test_pin_check.py  test_github_posting.py  test_release.py  test_deferred.py
    mods/decisions-pane.test.ts           ← the mod's own tests: `claude plugin test` from the repo root
    fixtures/
      conforming.md + one-change violation docs      ← one fixture per lint rule
      lint-hardening/  acceptance-columns/  hardening/  premise-checks/  ← per-rule violation families
      minirepo/  adapter/  bridge/  followups/         ← mini repos and script-level fixtures
```

Budgets, enforced by `tests/test_shape.py`: `SKILL.md` ≤ 150 lines; each `modes/*.md` ≤ 220
lines; each `references/*.md` ≤ 220 lines except this file and the framework. A mode file
that needs more is restating the framework — cite it instead.

## 4. Mode dispatch — the input decides, not the syntax

The user types `/promise` and says what they want in plain words. **A leading mode word is a
shortcut, never a requirement.** People will not remember thirteen mode names and must not have
to. The router reads the input and Phase 0's findings, names the mode it inferred in one
line ("Reading this as **reconcile** — you named a PR"), and proceeds. It never answers "use
`/promise <mode>`", never refuses for syntax, and asks only when two modes are genuinely
plausible — then as one question with a `(Recommended)` option first and one concrete
reason.

| Mode | Mode file | The input looks like… |
|---|---|---|
| `onboard` | `modes/onboard.md` | "help me get started with Promise", "guide me through Promise", "roll out Promise": choose a first workflow and its evidence |
| `new` (default) | `modes/new.md` | an idea, ticket, transcript or braindump; "design / plan / spec this", "write a doc for X", "how should we build X" — and nothing below matches |
| `revise` | `modes/revise.md` | a path to, or the title of, an existing outcome doc plus a change: "update", "add a rule", "change the outcome", "the signal is wrong", "tighten §5" |
| `review` | `modes/review.md` | a substantial doc, URL or paste authored elsewhere plus a critique verb: "review", "critique", "feedback", "is this any good", "check this against the framework" |
| `merge` | `modes/merge.md` | two or more doc paths or titles; "fold these", "these overlap", "consolidate", "which one survives" |
| `arm` | `modes/arm.md` | an `agreed` doc plus "start building", "arm it", "write the red tests", "file the rows", "kick off the build" |
| `intake` | `modes/intake.md` | a list of complaints, wishes, bug reports or feedback about the product; "what does this map to", "turn this into scenarios / gherkins", "which capability covers X", "add this as a scenario to <row>" |
| `reconcile` | `modes/reconcile.md` | a PR number, branch, commit or test file; "we shipped X", "we already do this", "isn't X covered", "update the map / the row / the doc now that Y landed" |
| `backfill` | `modes/backfill.md` | a product that already exists: "backfill the map", "retrofit promises onto the product", "map what the code does today", "every test / every route needs a home", "move our docs into promise" |
| `issue` | `modes/issue.md` | an issue number or an ask to file: "file an issue for X", "check issue #12 against the map", "triage / review these issues", "which capabilities does this issue touch" |
| `pr` | `modes/pr.md` | a pull request to describe: "write the PR description", "describe this PR", "PR body for #34", "update the PR text" |
| `adopt` | `modes/adopt.md` | "set this project up", "install / configure promise here", "add promise to CLAUDE.md" — or Phase 0 reports the project is not adopted and the user agrees to fix that first |
| `doctor` | `modes/doctor.md` | "promise doctor", "audit Promise setup": read-only feature adoption and setup advice |
| `upgrade` | `modes/upgrade.md` | "upgrade promise", "update the promise pin", "is our promise version behind": this repository's pin to a newer promise, as a pull request of its own |

Inference uses Phase 0 too: an input that names or matches the title of a doc in
`existingDocs` leans `revise` (with a change) or `review` (with a critique verb); an input
matching `map.rowIdPattern` leans `intake` or `reconcile`; an input naming a test file or a
commit leans `reconcile`. `issue` and `pr` write GitHub text, never a doc, so an issue or
pull-request phrase wins over every other signal. A recognised first word (`new`, `revise`,
`review`, `merge`, `arm`, `intake`, `reconcile`, `backfill`, `issue`, `pr`, `adopt`, `retro`,
`upgrade`, `doctor`, `onboard`) wins outright and skips inference, except `review` at the start of an issue phrase
("review the open issues"), which reads as `issue`, and `upgrade` before anything but promise
itself, or only a version, a commit, "now" or "the pin" ("upgrade the checkout page", "upgrade
to React 19" are product asks). An upgrade
phrase ("upgrade promise", "bump the promise plugin") leans `upgrade`.
The guarded first word `onboard` names Promise guidance when alone or aimed at
Promise, the user or their project. "Onboard customers" is a product ask.
Explicit getting-started phrases select `onboard` after GitHub-text routing;
vague existing-product hints do not cause a second starting-point question.

SKILL.md loads **only** the mode file for the detected mode, plus the references that mode
names in its header. It never loads every mode.

## 5. Phase 0 — orient (every mode, every run)

SKILL.md runs, at load time or as its first action — with no part of the user's message on
the command line, because a quote in the message would break the shell line and user text is
never composed into a command:

```
python3 "${CLAUDE_SKILL_DIR}/scripts/orient.py" [--mode <mode>] [--cwd <path>] [--input-file <path|->]
```

`orient.py` never fails hard on a valid invocation. It prints one JSON object to stdout and
exits 0; problems go in `warnings[]`. A usage error — an unknown flag, a `--cwd` that is
not a directory, an `--input-file` that cannot be read — exits 2 like any CLI. When no
Python 3 interpreter runs under any of the spellings S5 names, the router names the host's
one-line install and continues by applying the scripts' rules by hand for that run; a second
implementation in another language is refused (S5), because two implementations of one
rule set drift and then the same doc passes in one project and fails in another. Schema (every key always present; `null` when unknown):

```json
{
  "skillDir": "/abs/path/to/skills/promise",
  "skillVersion": "1.30.0 — read from VERSION beside SKILL.md; null when it is absent",
  "cwd": "/abs/path/of/project",
  "mode": "new — the --mode word, or null when the flag was not given",
  "frameworkPath": "/abs/path — the project copy if config.frameworkPath exists, else the bundled copy",
  "frameworkSource": "project | bundled",
  "config": { "path": "/abs/.claude/promise.config.json or null", "loaded": true, "raw": { } },
  "docsHome": "docs/designs",
  "docsHomeSource": "config | detected | none",
  "docsHomeForeignDocs": "0 — the *.md files in docsHome when none is an outcome doc; null when docsHome is null",
  "plansFolder": "plans or null",
  "commands": { "typeCheck": "pnpm type-check or null", "test": "pnpm test or null", "lint": "pnpm lint or null", "source": "config | detected | none" },
  "testRunners": [ { "runner": "vitest", "where": "apps/web/package.json", "junit": "--reporter=default --reporter=junit --outputFile.junit=<path>" } ],
  "branch": "feat/{slug}",
  "branchSource": "config | default",
  "run": "the config's run command (how this project runs promise's scripts) | null",
  "map": { "…the config.map object verbatim, or null…" },
  "mapUsable": "false | true (a boolean; false beside a sibling map)",
  "sibling": { "…null, or repo, path, find, row, dir, checkout: the read-only sibling map beside \"map\": false…" },
  "claudeMd": { "path": "/abs/CLAUDE.md or null", "hasPromiseSection": false, "sectionPath": null, "sectionCurrent": "true | false | null" },
  "adopted": false,
  "existingDocs": [ { "path": "docs/designs/foo.md", "title": "Foo", "status": "draft", "lastDecision": "YYYY-MM-DD", "decisionPolicy": "auto" } ],
  "suggestedMode": "revise or null — from --input, see below",
  "signals": [ "matches existing doc 'Foo' + a change verb" ],
  "ambiguous": false,
  "suggestedSize": "deferred | risky | null — from --input, see below",
  "sizeSignals": [ "names a protected category: billing, refunds" ],
  "decisionPolicy": "auto | fast | spec",
  "decisionPolicySource": "config | default",
  "legacyPolicyDocs": "0 — the open existingDocs with no Decision policy: line, see below",
  "promisePin": "null, or { ref, sha, version }: the promise marketplace in .claude/settings.json, see below",
  "machinePlugin": "null, or { scope, version, gitCommitSha, installPath }: the promise plugin this machine runs here",
  "githubTemplates": { "pullRequest": ".github/pull_request_template.md or null (wherever GitHub finds one)", "issue": ".github/ISSUE_TEMPLATE/capability.md or null" },
  "warnings": [ "no config found at .claude/promise.config.json; using detection" ]
}
```

Detection rules when config is absent:

- **docsHome**: first existing of `docs/designs`, `docs/design`, `docs/specs`, `docs/rfcs`,
  `design`, `docs`. None → `null`, and the mode asks the user before writing. The skill
  never creates a docs folder unprompted; `new`/`adopt` may, on the user's explicit say-so,
  and `render_outcome.py` does it only when passed `--create-docs-home`.
- **docsHomeForeignDocs**: when docsHome holds at least one `*.md` (the same one-level
  scan as `existingDocs`) and none of them is an outcome doc, their count; `0` when it
  holds an outcome doc or no `*.md`; `null` when docsHome is `null`. It is counted
  whatever the source, and warned about only when docsHome was detected (`docsHome
  <dir> was detected, but none of its <n> docs is an outcome doc; pin a new folder with
  adopt --docs-home …`) — docsHome itself is still returned as detected. `adopt.py`
  prints the same warning, and will not write a fresh config pinning that folder
  without `--docs-home` (§13).
- **plansFolder**: `plans` if it exists, else `null`.
- **commands**: from `package.json` `scripts` (`type-check` | `typecheck` | `tsc` → typeCheck;
  `test`; `lint`) prefixed by the package manager the lockfile implies (`pnpm-lock.yaml` →
  `pnpm`, `yarn.lock` → `yarn`, `bun.lockb` or `bun.lock` → `bun`, else `npm run`); else `Makefile` targets
  of the same names (`make <target>`); else `justfile` recipes (`just <recipe>`); else `null`.
- **testRunners**: read, never run. `package.json` at the root and in folders up to three
  levels below it (skipping `node_modules` and dot-folders) is read for `vitest`, `jest`
  and `@playwright/test` in `dependencies`/`devDependencies`, and for a script running
  `node --test` (`node:test`); `pyproject.toml`, `pytest.ini`, `setup.cfg` or `tox.ini`
  in the same folders counts for `pytest` when it mentions pytest. One entry per runner
  per file, sorted by runner then `where`; `junit` is the flag (and environment
  variable, where one is needed) that makes that runner write the JUnit XML
  `map_report.py` reads.
- **branch / branchSource**: the config's `branch` when it is `current` or a pattern
  holding `{slug}`, made of ASCII letters, digits and `. _ - /` around it, with no
  `..`, no leading `-` and no part ending `.lock` (`config`); else `feat/{slug}`
  (`default`), with a warning when a value was there but did not qualify. `arm` types
  the filled name into a shell line, in single quotes.
- **existingDocs**: every `*.md` under docsHome, one level deep — the folder and its
  immediate subdirectories, the same scan `lint_outcome.py` and `outcome_rows.py
  --search` use (§9/§10) — whose text contains a line
  starting `## 0. TLDR` outside any fenced code block, so a framework copy or a doc
  quoting the template is not listed. `status` is the first token after `Status:`;
  `title` is the H1, both read from unfenced lines. A file that is not UTF-8 is skipped
  with a warning.
- **legacyPolicyDocs**: how many `existingDocs` are at `draft`, `agreed` or `building`
  with no `Decision policy:` line in the header. Each behaves as `spec`. A line with a
  value that is not one of the three is not counted. `revise` and `adopt` put the count
  under Needs you; `decisions.py policy --open` stamps the same docs (§14).
- **promisePin** / **machinePlugin**: the repo's promise marketplace declaration and the
  install Claude Code records in `plugins/installed_plugins.json` (`CLAUDE_CONFIG_DIR`,
  else `~/.claude`): this directory's project-scope install, else a local one, else the
  user-scope one. Claude Code's marketplace source reads `ref` (a branch or tag) and not
  `sha`, so a `sha` with no `ref` warns, and so does a machine whose version differs from
  a release-tag `ref`, or whose commit differs from a `sha`: the session runs a promise
  the repo did not pin (`modes/upgrade.md` § The machine step).
- **claudeMd**: `CLAUDE.md` at the project root, else `.claude/CLAUDE.md`, else `null`.
  `hasPromiseSection` is true when the file contains the marker `<!-- promise:begin`, or
  when the root `AGENTS.md` does and the `CLAUDE.md` imports it on a line of its own
  (`@AGENTS.md`; `@../AGENTS.md` from `.claude/`), or there is no `CLAUDE.md`.
  `sectionPath` is the file that holds the section, or `null`. A section in both
  `CLAUDE.md` and the `AGENTS.md` it imports is a warning: Claude reads it twice.
- **adopted**: true when a config was loaded AND `claudeMd.hasPromiseSection` is true. When
  false, `warnings[]` carries `project not adopted — run /promise adopt`, and the router
  offers `adopt` once per session (Recommended) before continuing with the requested mode.
- **suggestedSize / sizeSignals**: from the same input, a hint for SKILL.md § Size the ask
  first: `deferred` when the person asks to build first ("ship it first", "hotfix …" as
  the first word, "promise it later"), with a protected category named in the signals,
  whose every decision is still asked; else `risky` when the words name a protected
  category (billing, refunds, permissions, auth, a migration, a schema, a column, an API
  route, sending messages…); else null.
  Words never show an ask is tiny, so the agent sizes every other ask. It never decides.
- **decisionPolicy**: the config's `decisionPolicy` when it is `fast`, `auto` or
  `spec`, else `auto` (source `default`); another value warns. Every new doc takes it.
- **suggestedMode / signals**: `--input-file <path>` (or `-` for stdin; `--input "<text>"`
  exists for tests and programmatic callers) makes the
  script read the input against the §4 table deterministically — a leading mode word, an
  `existingDocs` title or path plus a critique or change verb, two doc matches, a PR or
  commit or test-file pattern (a commit is a 7–40 hex run with at least one letter, or a
  digit-only run beside a word such as merged, landed, PR, commit or branch — a bare date
  or id on its own is not one),
  a `map.rowIdPattern` match, complaints (a sentence or a list), a backfill phrase
  ("map what the code does", "migrate the docs" but not "the docs site", "every test"
  — or route, endpoint, entry point, page, screen — with a verb that gives it a home:
  "has a home", "needs a row", "belongs in the map"; or "every test we have"), an adopt
  phrase — and name the rule that fired. Docs moved "to" or "into" a place that is not
  the outcome shape ("migrate the docs to Notion") are only a hint. "backfill",
  "retrofit" and "existing product" count for backfill only with a map word within 40
  characters: "capability map", "the map", "capability", "promises", "outcome docs".
  A test word counts only where it says the product has the tests ("with a big test
  suite", "from our tests"), and never beside a change word ("fix", "slow", "speed it
  up", "flaky"). A bare "map", "row" or "test" is not a map word ("a map view", "a row
  limit"). Otherwise these three suggest `new` and set `ambiguous`, since they are as
  likely a data job, a fix or a feature for that product. A feature, design, plan or
  spec word ("plan", "design", "spec", "write a doc", "add a", "show a", "let users")
  turns any backfill phrase into the same hint: `new`, with `ambiguous` set. A backfill phrase
  ranks below reconcile and intake, so it never takes their phrases; beside one of them
  it only sets `ambiguous`. Without the flag both are `null` / `[]`.
  `ambiguous` is true only when two rules for different modes both matched; then the router
  asks. It is a hint the router confirms in its one-line statement, never a decision.
- **map**: the config's `map` object, verbatim; `null` when it is absent or `null` (no
  map yet), or another value that is not an object (with a warning); `false` when the
  config sets `false`, with no warning (no map in this project, on purpose: no mode
  offers the starter map, and `start_map.py` refuses).
- **mapUsable**: the single source of "is a map of this project's own configured", a
  boolean. True only when `map` carries
  `recipe`, `find` and `row` as strings and `lanes` as an object of strings. An incomplete
  map stays in `map` with a warning naming the missing keys (`map incomplete: missing …`);
  the modes treat it as not configured, `adapter.py` refuses map operations (exit 2, the
  message naming the missing keys) and `bridge_validate.py` reports `MAP_NOT_CONFIGURED`
  with the same keys named — neither runs with a partial map. A
  `recipe` or `index` file that does not exist, a `checks` value that is not an array of
  strings, an `issueTracker` that is not three strings, a `rowIdPattern` that does not
  compile, a `map.file` that is not a string or does not exist, a `map.junit` that is
  not a path or a list of paths, or escapes the project, a `map.surfaces` that is neither
  a command string nor a non-empty array of strings, and a `map.requireHomes` that is not
  a boolean each warn without changing it. Beside `"map": false` and a complete `sibling`
  object, `mapUsable` stays false: the project has no map of its own, so every mode that
  writes to a map takes its no-map path, and only sizing, `intake`'s match, `issue` and
  `pr` read the sibling's rows (`sibling`, below).
- **sibling**: `null`, or the config's `sibling` object (`repo`, `path`, `find`, `row`,
  all strings) with `dir` (the path resolved from the project root) and `checkout`
  (whether a folder is there; a missing one warns). It counts only beside
  `"map": false`; otherwise, or incomplete, it warns and is `null`. `adapter.py` runs
  `find` and `row` in that folder and refuses every other map operation.
- **Config warnings** (`warnings[]`, every one a string a person can act on): an unknown key
  at any level; a wrong-typed field; a path that escapes the project or uses backslashes; a
  `docsHome`, `frameworkPath`, `map.recipe` or `map.index` that does not exist
  (`frameworkPath` then falls back to the bundled copy; the others are returned as
  configured); a loaded config that pins no `docsHome` in a project where detection
  finds no docs folder either (`docsHome is null: …` — every later `new` would ask); a
  `branch` that is neither `current` nor a safe `{slug}` pattern; a `docsHome` or
  `map.junit` entry holding anything but letters, digits, spaces and `. _ - /`, or
  starting with `-` (a mode types these into shell lines); a
  `$schema` key (deprecated — use `"version": 1`); a `version` other than
  `1`; a `minSkillVersion` that is not a version like `1.30.0` (ignored); a running skill
  older than `minSkillVersion`, or with no `VERSION` file beside it (both versions named,
  and how to update). A path that escapes the project includes a Windows drive-letter path on every
  OS. Whether a configured command exists is not checked — `adapter.py` reports exit 127
  when it runs one that is not there.

The mode file states, in one line, what Phase 0 resolved: mode (and that it was inferred,
if it was), framework source, docs home and its source, whether a map is configured
(`mapUsable`), whether the project is adopted, and `skillVersion`.

## 6. Config contract — `.claude/promise.config.json`

Location: `<project>/.claude/promise.config.json`; fallback `<project>/promise.config.json`.
All fields optional. Unknown fields are a warning, not an error. `"version": 1` names the
shape of the file; a `$schema` key from an earlier config is accepted with a deprecation
warning. `references/config.md` is the user-facing contract, field by field. The example
below is `templates/promise.config.example.json`, verbatim — one example in two places,
kept byte-identical:

```json
{
  "version": 1,
  "minSkillVersion": "1.30.0",
  "$comment": "Config for the promise plugin, at .claude/promise.config.json. Every field is optional — a project with none of this still gets full detection (see references/config.md). minSkillVersion is the oldest promise skill this project expects: adopt writes the running skill's version, and an older copy warns. docsHome / frameworkPath / plansFolder / commands pin what orient.py would otherwise detect; decisionPolicy is the repo's decision policy (fast, auto or spec; auto when unset), which every new doc takes; branch names the branch arm works on: a pattern with {slug} in it (default feat/{slug}), or current to stay on the branch the session is on, for a host that allows one branch per session; adopt never writes it. protectedPaths names the paths a pull request sized tiny may not touch (changed_rows.py --size tiny). pinFiles names the places besides .claude/settings.json (whose promise marketplace pins a release tag in source.ref) that pin promise, each a path and a pattern whose first group is the value, a commit sha or, with kind version, a version (pin_check.py reads them; upgrade.py moves them, but never a site marked vendored: true alone). upstreamPath names a local promise checkout that reads a private upstream with its own git access. map turns on the bridge to a project's own machine-checked register of promises, and most projects start with no map at all. This file shows every field at once so each one has an example: copy it, then delete whatever this project does not need.",
  "docsHome": "docs/designs",
  "frameworkPath": "docs/how-to/outcome-framework.md",
  "plansFolder": "plans",
  "decisionPolicy": "auto",
  "branch": "feat/{slug}",
  "protectedPaths": ["billing/", "infra/*.tf"],
  "pinFiles": [
    {"path": "scripts/promise/run.sh", "pattern": "REF=([0-9a-f]{40})"},
    {"path": "scripts/promise/run.sh", "pattern": "REF_VERSION=(\\d+\\.\\d+\\.\\d+)", "kind": "version"}
  ],
  "upstreamPath": "../promise",
  "commands": {
    "$comment": "The verify commands the writing modes run at hand-back through adapter.py verify. Each is an argv line, split and run with no shell. Once this object exists, detection is off for all three; a null or missing key means 'this project has none'. Delete the whole object to go back to detection.",
    "typeCheck": "pnpm type-check",
    "test": "pnpm test",
    "lint": "pnpm lint"
  },
  "map": {
    "$comment": "Present only when this project keeps its own capability map — a machine-checked register of promises and the tests that prove them. Start one with scripts/start_map.py, which installs the skill's starter map (templates/starter-map/) and writes this object; examples/minimap/ in the plugin repository runs the same reader over example rows. recipe is the authority for mechanics: read it, do not expect this skill to restate it; whether a row is filed, and how big it is, is the skill's (references/sizing.md). find/row/nextId and checks are argv lines, split and run with no shell (an argument is appended as one argv element) — no pipes, &&, env prefixes or cd; put such logic in a script and name it here. learn is optional: the argv line that records the words find missed a row by, which adapter.py learn runs with --query-file, --row and --source appended (the starter reader's learn); refsSync, also optional, is the one reconcile runs with --input <merged pull requests as JSON> to record which rows each merged pull request named; code, optional too, prints the local files a row's cited tests import (adapter.py code <id>), read before a wide code search. rowIdPattern validates any row id this skill writes or parses. lanes maps the four altitudes (plus sibling) to this project's own evidence-array names, so references/altitude.md can stay generic. checks run, in order, at the end of arm/intake/reconcile and as check.py's checks step; the key is optional, but a project with no checks writes [] — with the key absent, adapter.py checks refuses (exit 2, 'map.checks is not configured'). issueTracker enables a duplicate-issue search before anything gets filed. file names the map's own JSON file, and junit the JUnit XML files or folders this project's test commands write; scripts/check.py joins the two with map_report.py (for the starter map, file can be left out: it is the map.json beside capability_find.py). surfaces is the command that prints the code's entry points, one per line — an argv line or, as here, an argv array — which check.py runs with no shell so the report can list every entry point no row names; requireHomes: true makes check.py fail on a test or an entry point with no row. A map counts as configured only with recipe, find, row and lanes (orient.py's mapUsable). Omit this whole object for a project with no map yet — see references/config.md 'Without a map'.",
    "recipe": "docs/how-to/adding-a-capability.md",
    "index": "docs/how-to/capability-map-index.md",
    "find": "scripts/capability-find",
    "row": "scripts/capability-find --row",
    "nextId": "scripts/capability-find --next-id",
    "learn": "scripts/capability-find learn",
    "refsSync": "scripts/capability-find refs sync",
    "code": "scripts/capability-find --code",
    "rowIdPattern": "^CAP-(\\d+|[ip]\\d+[a-z]{1,2}|[A-Z][A-Z0-9]+-\\d+[a-z]{1,2})$",
    "lanes": {
      "data": "tests[]",
      "response": "tests[]",
      "perception": "e2eTests[]",
      "judgement": "evalTests[]",
      "sibling": "siblingTests[]"
    },
    "checks": [
      "scripts/capability-check",
      "scripts/citation-strength-check"
    ],
    "issueTracker": {
      "kind": "github",
      "repo": "owner/repo",
      "template": ".github/ISSUE_TEMPLATE/capability.md"
    },
    "file": "docs/capabilities/map.json",
    "junit": [
      "test-results/unit.xml",
      "test-results/e2e"
    ],
    "surfaces": [
      "node",
      "tools/list-entry-points.mjs"
    ],
    "requireHomes": false
  }
}
```

Semantics the mode files rely on:

- **`map` absent, `null`, or unusable** (§5, `mapUsable`) → there is no capability map.
  `arm` writes red tests only. `intake` matches feedback against the §6 rows of the docs
  in `docsHome` and files the routing table into the doc (§6 / §9). `reconcile` updates
  the doc only (tags, `Scenarios:` count, a dated §8 entry). Each of those modes says "no
  map configured" in its Phase 0 line.
- **`map.recipe`** is the project's own how-to for writing a row. **It is the authority
  for the mechanics** — which files a row touches, what lockstep means there, what a
  citation looks like. The mode files never restate a project's mechanics; they say "read
  the recipe, work from the file". The generic *procedure* (split, match, route, draft,
  prove, apply, verify) lives in the mode file; the *mechanics* live in the recipe.
  Whether anything is filed, and at what size (the size, the relation, one row per
  job), is the skill's, in `references/sizing.md` § How big a row is: a recipe that
  says otherwise does not win there, and a recipe needs no row-size section.
- **`map.find` / `map.row` / `map.nextId`** are argv lines `adapter.py` splits and runs
  with `shell=False`, the argument appended as one argv element (`adapter.py find <query>`
  or `adapter.py find --query-file <path>`, `adapter.py row <id>`); no pipes, `&&`, env
  prefixes or `cd`. **`map.surfaces`** runs the same way, with no argument, through
  `adapter.py surfaces [--out <file>]` or `check.py`.
- **`map.lanes`** maps the four altitudes (plus `sibling`) to the project's evidence-array
  names, so `altitude.md` can be generic and the mode file can say "cite in the lane the
  altitude picks".
- **`map.checks`** run at the end of `arm`, `intake` and `reconcile`, in order, before the
  mode hands back. The key is optional, but a map with no checks writes `[]`: with the key
  absent, `adapter.py checks` refuses (exit 2, `map.checks is not configured`), and the
  modes run it only when a map is configured and `checks` is set — a refusal is
  reported as not run, never as a failed check.
- **Every configured command runs as the caller** — `references/config.md` § Trust model.
  The router prints `adapter.py show` and asks before the first configured command runs
  in a session; on no, the run continues as if no map and no `commands` were configured.

## 7. Vocabulary (use these words; define nothing else)

| Word | Meaning |
|---|---|
| **promise** | Something a person will be able to do, stated so it can be checked. An outcome doc makes one; a row keeps or breaks one. |
| **outcome doc** | The one document per capability in the Outcome Framework shape. |
| **capability map / map** | A project's machine-checked register of promises and their proof — the map of the platform. The goal state (F9): `arm` offers a starter when the first doc is agreed; configured in §6. |
| **row** | One entry in the map: a user story plus 1–5 Gherkin scenarios, evidence arrays, a verdict. Ids follow `map.rowIdPattern`. |
| **AT-n** | A doc-local acceptance-row id in §6. Stable, append-only. After the bridge it is an alias for a row's scenario, never a second copy. |
| **altitude** | What a `Then` asserts on: **data** (a stored fact), **response** (what a request returns), **perception** (what a person sees, is told, lands on), **judgement** (whether a model chose well) — plus **sibling**, a `Then` that only a sibling system's own tests can prove. §6's `Altitude` column carries one of the five. |
| **lane** | The kind of test that reaches an altitude, and the evidence array it is cited in. |
| **verdict** | The row's honest proof state — `proven` / `under-proven` / `not-built` in the minimap; a project may keep its own enum. It moves only when evidence reaches the `Then`'s altitude. |
| **kill mutation** | A production change, chosen before the test is trusted, that the cited test must fail on: applied, watched failing, reverted, watched passing (`references/altitude.md` § Kill mutation). |
| **kill witness** | The record of a kill mutation a cited test was watched to catch. No watched kill, no promotion. |
| **proof strength** | How much of a rule's cases the evidence checks: **example** (chosen cases), **property** (the real code on generated cases), **model** (every reachable state of a model, by machine-checked proof). Recorded on §4 invariants; a `model` proof needs a conformance test to reach the code (`references/altitude.md` § Proof strength). |
| **signal** | §0's *how we'll know*: one of four kinds — a red→green test, a watched demo, a number in prod, a claim we can make to a customer. |
| **slate** | A short list of candidate lines put to the human for the outcome line or the signal — never for a rule (`references/slates.md`). The human's edit enters, not the candidate. |
| **recipe** | `map.recipe`: the project's own how-to for writing a row. The authority for mechanics; a mode reads it and works from the file, never restates it. |
| **lockstep** | The recipe's rule for which files move together when a row changes, and in what order. Never traded for speed. |
| **ratchet** | A checker's floor or ceiling that only tightens — a coverage count, a citation-strength threshold. Loosening one to make a check pass is never a fix. |
| **red gate** | The commit that contains only the failing tests for a doc's §6 rows. Its sha and date sit in the header as `Red gate: <sha> <YYYY-MM-DD>`; that line is what `building` records. |
| **snapshot line** | The one line under a bridged doc's §6 table — `` Snapshot taken at `agreed` on <YYYY-MM-DD>; the map is the source of these scenarios from here on. `` — after which §6 is not edited. `bridge_validate.py` requires it. |
| **decision policy** | The doc's `Decision policy:` header line — `fast`, `auto` or `spec` — the repo's (the config's `decisionPolicy`, set by a human) or a human's choice for the doc: which decisions the agent asks and which it records in §8 as a row with Owner `agent`, a rollback and a review trigger. The protected categories are asked at every policy. A doc with no line behaves as `spec` (outcome-framework.md § Decision policy). |
| **thin draft** | A `draft` doc with `Depth: thin` in its header: the human half only, §3–§7 not written yet, each gap a BLOCKING §9 question. It cannot be agreed (`THIN_DRAFT`); `revise` fills it. |
| **confirmation sheet** | The one-screen summary of the human half — outcome line, rules, signal, example — put to the user for approval before anything is written (`references/slates.md` § The confirmation sheet). |

## 8. The bridge — doc status × map

| Doc status | Without a map | With a map |
|---|---|---|
| `draft` | Doc is the only home. §6 rows are the promise. | Same. Nothing is filed in the map yet. |
| `agreed` (human act) | No extra step; the doc stays the only home. | `arm` files each §6 row as a **not-built row** per the recipe, grouped by the job they serve, one row per "so that" — the grouping rule is the framework's (§ Lifecycle, decision F7), not restated here. §6 gains a `Row` column and the snapshot line (§7), and is not edited again: it is the record of what was agreed, the map is the live source. §0 tags keep AT aliases (stable and append-only, never replaced by the map's ids). `bridge_validate.py` (§10) is the staleness check between the two. |
| `building` | Red tests (and the stubs they import) written and committed first; one `Red run:` line in §6, and one `Filed without red run:` line for lines over working code; sha in header. | Same, plus each red test is cited in the lane its altitude picks. |
| `shipped` | Human flips it when §6 rows are green and each line went red or has a `Kill:` line. | Human flips it when **every** bridged row is `proven` at its `Then`'s altitude. `reconcile` is how rows get there. Doc keeps §0, §2, §4 as the living record. |

`agreed` and `shipped` are typed by a human. `building` is written by `arm`, only after
the human has seen the red-gate commit and confirmed it — the commit is the human act
the status records. `revise` states when a §0 change would drop a doc back to `draft`.
`merge` deletes a folded doc (`git rm`, one explicit-path commit with the survivor)
unless the user keeps the file, in which case it is marked `superseded-by <survivor>`
and nothing else in it changes again; a folded doc's map rows are re-pointed or retired
per the recipe, with the user.

## 9. `lint_outcome.py` — what it checks

```
python3 "${CLAUDE_SKILL_DIR}/scripts/lint_outcome.py" <doc.md | directory> [--json] [--strict] [--template]
```

Exit 0 when no error-severity findings; exit 1 when any error (or, under `--strict`, any
warning); exit 2 on a usage error. Human output is one line per finding:
`<path>:<line>: <RULE_ID> <message>`, with ` (warning)` at the end of a warn-severity
one, then a last line with the counts, `lint_outcome.py: <n> docs, <e> errors, <w>
warnings` (`--no-summary` leaves it out; `check.py` passes it). `--json` prints
`{"path": …, "findings": [{"rule": …, "line": …, "message": …, "severity": "error|warn"}], "stats": {…}}`
for one file, and a JSON array of those objects for a directory, so stdout is always one
parseable value. A directory lints every `*.md`, one level deep, whose `## 0. TLDR`
line sits outside a fence. Lines inside a fenced code block (``` or ~~~) are
illustrations: no heading, field marker, table row or placeholder inside one counts,
though the lines still count toward a line budget; an unclosed fence is its own finding
(`FENCE_UNCLOSED`), reported at the opening line.

| Rule id | Checks | Severity |
|---|---|---|
| `HEADER_STATUS` | A `Status:` line exists and its first token is one of `draft` `agreed` `building` `shipped` `superseded-by`; `superseded-by` names a target. Other text after the token is allowed. | error |
| `THIN_DRAFT` | A `Depth:` header line reads exactly `Depth: thin`, and only on a `draft` doc. On a thin draft, §3–§7 each hold a line that is just the not-written-yet marker (the sentence `render_outcome.py --thin` writes, or "Not written yet" alone, in emphasis or not; a line with any other text is content), and §4–§7 hold nothing else but their role line (`*(agent)*`) and an HTML comment; §3 may also hold a seed example the human gave. A thin draft holds the human half only: on one, `ACCEPTANCE_TABLE` does not require a table (a table that is there is checked in full), `WHY_LINE` does not run, `SCENARIOS_COUNT` counts a §3 with no parseable example as zero, and `RULES_PRESENT` is a warning. Past `draft` the line is this error and every rule applies in full, so a thin doc cannot be agreed. | error |
| `HEADER_OWNER` | `Owner:` and `Last decision:` present, with non-empty values. | error |
| `CONTENTS_LINE` | A `Contents:` line exists and links to all eleven anchors `#0-tldr` … `#10-out-of-scope`. | error |
| `HEADINGS_BARE` | Exactly one `## <n>. <Name>` per n in 0..10, matching the template's names, with nothing after the name on that line. | error |
| `TLDR_BUDGET` | Lines from `## 0. TLDR` up to (not including) the `Agent notes` line — or `## 1.` if there are none — number ≤ 40. Report the count. | error |
| `TLDR_FIELDS` | The block contains `**Outcome:**`, `**Rules:**`, `**How we'll know:**`, `**Scenarios:**`, and the Outcome and How-we'll-know values are non-empty. `**How we'll know:**` with a curly apostrophe (U+2019) is the same marker. The rules block ends at the next bold `**Field:**` line, the next `## ` heading or the end of §0 — never end-of-file — so a missing marker is one finding, not a cascade. | error |
| `RULES_FORMAT` | Every rule is a `- ` bullet with text before its tag. Numbered rules, and any other non-blank text in the rules block, are findings. | error |
| `RULES_PRESENT` | `**Rules:**` is present but has no `- ` rule bullet under it, at every status. A block holding only stray text is `RULES_FORMAT`'s and does not also fire this. On a thin draft (`THIN_DRAFT`) it is a warning. | error / warn |
| `RULES_TAGGED` | Every rule ends with `→ AT-n[, AT-m…]` or `→ UNTESTED`. | error |
| `TAGS_RESOLVE` | Every `AT-n` cited in a §0 tag exists as a row id in §6. | error |
| `AT_IDS_UNIQUE` | §6 row ids are unique and match `AT-\d+`. | error |
| `ACCEPTANCE_TABLE` | §6 holds at least one acceptance table — a header row whose first cell is `#`, `ID` or `AT` and which names `Given`, `When` and `Then` exactly once each (any order, case-insensitive, extra columns allowed, optional `Row` and `Altitude` columns recognised by name, each at most once) — with at least one data row; every data row has the right cell count and non-empty Given, When and Then. Columns are matched by header name, never position, so an extra column or a reordered `Row` never shifts what a cell means, and a header naming a column twice does not qualify — never a guessed mapping. Every `#`/`ID`/`AT`-headed table in §6 is checked on its own terms: a malformed table is reported even when a sibling table in the same section qualifies fine. Other, non-`#`/`ID`/`AT` tables in §6 are ignored. A row directly under a table that contains a pipe but lacks its leading or trailing pipe is read GFM-style (outer pipes stripped), so no row below it is dropped, and is reported at its own line. Cells split as GitHub splits them: at every pipe a backslash does not escape, inside a code span too; a pipe written `\|` is cell text, read back as `|`, and a row with too many cells says so. A Why line or the Snapshot line directly under the table is not read as a row, pipe or not. | error |
| `ACCEPTANCE_ALTITUDE` | When a §6 acceptance table has an `Altitude` column, every data cell in it is exactly one of `data`, `response`, `perception`, `judgement`, `sibling`. An empty cell or any other value is a finding; an angle-bracket cell (`<altitude>`) is `PLACEHOLDER`'s, not this rule's. | error |
| `SCENARIOS_COUNT` | The `**Scenarios:**` line is either the count-free form, `the acceptance rows in §6 and the worked examples in §3.`, which counts nothing and so is never checked or conflicted on (the template and `render_outcome.py` write it), or `<N> acceptance rows (§6), <M> worked example(s) (§3)`, singular or plural, carrying an acceptance-row count equal to the number of §6 rows. The worked-example count is checked only if §3 examples are parseable (`### ` or bold-led blocks); otherwise `warn` that it was not checked. | error / warn |
| `WHY_LINE` | §4, §5, §6, §7 each contain a line beginning `Why — what breaks without it:` with a value after the colon. A `<placeholder>` value is `PLACEHOLDER`'s. | error |
| `UNTESTED_ON_AGREED` | A rule tagged `UNTESTED` while `Status:` is `agreed`, `building` or `shipped`. | error |
| `PENDING_ON_AGREED` | `Status:` is `agreed`, `building` or `shipped` and §0 still holds `pending verbatim confirmation` (any case): a moved doc's candidate block a human never confirmed. The human confirms by deleting the `**Pending verbatim confirmation:**` line while the doc is `draft` (`modes/backfill.md`). | error |
| `OPEN_ON_AGREED` | `Status:` is past `draft` and the `**Outcome:**` or `**How we'll know:**` value still reads `Open — Qn …`, the value a moved doc gives a field its legacy doc never decided. An outcome that starts with the verb ("Open a shared channel") is not this. | error |
| `BLOCKING_OPEN_ON_AGREED` | `Status:` is past `draft` and a §9 question marked `BLOCKING` has no answer line (`Answer (YYYY-MM-DD…)` or `Answered …`, bare or in bold or italic, before the next question). | error |
| `BUILDING_NEEDS_GATE` | `Status:` is `building` and no header line (any line before the first `## ` heading, skipping anything inside a ` ``` `/`~~~` fence) matches `Red gate: <sha> <YYYY-MM-DD>` exactly — sha 7–40 hex characters (digits alone qualify), date a real calendar date (checked with Python's own date parser, not just the `\d{4}-\d{2}-\d{2}` shape); position among the header lines is not enforced, the line's own shape is. A hex-looking run inside another header value (`Supersedes: deadbeef`, a digit-only `Last decision:`), a `Red gate:` line inside a fenced code block, or one naming a date that does not exist (`2026-02-31`) does not satisfy it — the last of these is its own message, not silently treated as no line at all. | error |
| `SHIPPED_NEEDS_GATE` | `Status:` is `shipped` and a §6 line has no `Row` value, did not go red (the header holds no `Red gate:` line that `BUILDING_NEEDS_GATE` would accept, or the line is listed in `Filed without red run:`), and no well-formed `Kill:` line names it. Also when §6 has no line and there is no `Red gate:` line. A shipped doc carries proof that each §6 line was seen to fail (framework § Lifecycle); a line that cites a `Row` is left to `bridge_validate.py`, which reads the map (`SHIPPED_WITHOUT_GATE`). One finding per such line. | error |
| `KILL_RECORD_FORMAT` | A line under §6 that reads as a record line, through any list mark, quote, emphasis, backticks, HTML comment or case (`red-run` too), is not plain at the start of the line (four spaces of indent render as code); or a Filed line does not read `Filed without red run: AT-2, AT-4 — <reason>`, or is the second one; or a Kill line does not read `Kill: AT-2 — <the mutation> → <test id> failed; restored, passing at <sha> on <YYYY-MM-DD>` with a real date; or a record line (`Red run:` too) sits between two rows of the §6 table, which is read on past it so no row is hidden. Such a `Kill:` line proves nothing; such a Filed line still lists its AT ids as not red. Lines in a fence are ignored. | error |
| `KILL_RECORD_UNKNOWN` | A `Filed without red run:` or `Kill:` line names an AT id that is not a §6 line. | error |
| `PLACEHOLDER` | `TBD`, `TODO`, `<fill`, `decide later` inside §0; any `<…>` placeholder in §0, in the `Owner:` / `Last decision:` values, in a §6 data cell, in an agent note, on the first line of a §3 worked example, in a §9 question's owner, or in the value of a §4–§7 Why line (§5 body text is not scanned, so a generic like `Map<string, Row>` stays legal); a literal `YYYY-MM-DD`. `--template` exempts the angle-bracket and date placeholders so the bundled template can be linted; every other rule stays active. A copied, unfilled template therefore fails a normal lint. | error |
| `UNREADABLE` | The path cannot be read or is not valid UTF-8 — one finding for the file, never a traceback. | error |
| `FENCE_UNCLOSED` | A ``` or ~~~ fence is opened and never closed, so every line after it is read as an illustration by every other rule. Reported at the opening fence's own line, so the cascade of missing-heading findings it causes has a named cause. | error |
| `DECISION_POLICY` | A `Decision policy:` header line reads exactly `fast`, `auto` or `spec`, and there is at most one. A doc with no line is a legacy doc and behaves as `spec`; that is allowed, since a missing line is the strictest reading. `render_outcome.py` writes the line on every new doc, as a placeholder (`PLACEHOLDER`'s) until the human picks. | error |
| `AGENT_DECISION_FIELDS` | Each §8 row whose Owner is `agent` has, in its Why cell, `Category:`, `Because:`, `Rollback:`, `Reversible until:`, `Review:` and `State:`, each once and non-empty; a real date; a category from the framework's lists (`wording`, `naming`, `layout`, `order`, `default`, `internal`, or a protected one); a concrete review trigger (`before arm`, `before public release`, `on YYYY-MM-DD`, `after N uses`); a state of `provisional` or `asked Qn`, where §9 holds `Qn`. | error |
| `AGENT_DECISION_PROTECTED` | A `provisional` agent decision declares a protected category (`data-retention`, `destructive-migration`, `money`, `legal`, `security`, `contract`, `external-effect`, `regulated`, `third-party`). The agent never decides one alone, at any policy; `asked Qn` is the fix. | error |
| `AGENT_DECISION_UNRATIFIED` | A `provisional` agent decision under `Decision policy: spec`, or on a doc with no valid policy line (read as `spec`). | error |
| `DECISION_POLICY_ALIAS` | A `Decision policy:` header line reads `prototype`, a value still accepted and read as exactly `fast`. The warning asks for `fast`. | warn |
| `AGENT_DECISION_WORDS` | A `provisional` agent decision in a local category whose decision or reason uses a word of a protected category (`API`, `schema`, `retention`, `delete`, `billing`, `price`, `consent`, `token`, `permission`, `access`…). The category is the agent's own reading; a hit asks for a second one. | warn |
| `PREMISE_TABLE` | A §5 Load-bearing premises table (header first cell `Premise`, `outcome-framework.md` § Section rules) has a data row with an empty `Evidence` or `Existing join searched` cell, or a header naming neither column. Columns matched by name, case-insensitive, the same lookup `ACCEPTANCE_TABLE` uses — no table at all is not itself a finding; that judgement is `PREMISE_PHRASE`'s and a reviewer's. | error |
| `PREMISE_PHRASE` | A negative, design-constraining claim in §1 or §5 (`can't`/`cannot`, `doesn't have`/`does not have`, `no way to`, `unavailable`, `only X has`) outside a `PREMISE_TABLE` table, not cleared by a COMPLETE row (Evidence and Existing join searched both non-empty) whose Premise cell overlaps the claim literally once normalized (case folded, markdown emphasis stripped, whitespace collapsed — quoted or closely restated, not paraphrased), and not marked `<!-- not a premise -->` on its line. A wording heuristic — it flags the phrase, not whether the claim is true or load-bearing, so it is a warning a reviewer judges. One finding per line. | warn |
| `AGENT_NOTES_MANY` | More than 8 numbered agent notes under §0. | warn |
| `HUMAN_HALF_BUDGET` | §0 through the end of §2 plus the first §3 example ≤ 150 lines (measured to the end of §2 when §3 is not parseable; say so). | warn |
| `ALTITUDE_MISSING` | A §6 acceptance table has no `Altitude` header. A doc written before the column existed keeps linting; the column is how a `Then` says what it asserts on, and `reconcile` needs it to judge evidence. | warn |

`--strict` promotes `warn` to `error`. `HEADINGS_BARE` fires on a malformed heading even when a
well-formed heading for the same number also exists. The lint is deterministic and needs no
network.

## 10. `outcome_rows.py` — the bridge's input

```
python3 "${CLAUDE_SKILL_DIR}/scripts/outcome_rows.py" <doc.md> [--json]
```

Prints `{"path", "status", "rules": [{"index", "text", "tags": ["AT-1", …] | ["UNTESTED"]}],
"rows": [{"id": "AT-1", "given", "when", "then", "altitude": "data" | null, "row": "CAP-207" | null}],
"signal": "…"}`. `altitude` is the §6 `Altitude` column (§9: one of five values; `null`
when the table has no such column); `row` is the optional `Row` column (§8). A rule with no
tag at all yields `tags: []`, which the lint reports as `RULES_TAGGED`; the script extracts,
it does not judge. Human output is a compact table. This is what `arm` reads to file rows
and what `reconcile` reads to re-stamp tags. Two more flags: `--write-counts` rewrites only
the `**Scenarios:**` line from the real §6 row count (and the §3 example count when
countable), idempotently, pluralising `worked example(s)` as the count requires — the count
is agent-maintained metadata, so a script may own it, and a count-free line is left as it
is; `--count-free` swaps a counted line for the count-free form; `--search "<text>" --dir <docsHome>`
(or `--search-file <path>`, `-` for stdin, so the text never sits on a command line) ranks
every §6 row and §0 rule across the docs by token overlap — intake's matcher when no map is
configured. `--dir` is walked one level deep, as the lint scans (§9); a missing or
non-directory `--dir` exits 2.

### `bridge_validate.py` — the bridge's check

```
python3 "${CLAUDE_SKILL_DIR}/scripts/bridge_validate.py" <doc.md> [--cwd <path>] [--json] [--strict] [--linking]
```

Checks a bridged doc's §6 against the project's map. Config is resolved exactly as
`orient.py`/`adapter.py` do, under `--cwd`, and "configured" means orient's `mapUsable`
(§5): a map that is present but incomplete is `MAP_NOT_CONFIGURED`, with the missing keys
named in the message. Every `map.row` lookup runs through
`adapter.py --json row <id>` rather than a shell string composed from configuration
plus doc content, so a row id — however it is spelled — always travels as one argv
element.

Checked in this order — STATUS_UNKNOWN, then NOT_BRIDGED, then
MAP_NOT_CONFIGURED — because a doc with no readable status cannot be judged at
all, and a doc still at `draft`/`superseded-by` has not been bridged regardless
of whether a map exists to bridge it to:

| Rule id | Checks | Severity |
|---|---|---|
| `UNREADABLE` | DOC is missing or not valid UTF-8. | error |
| `STATUS_UNKNOWN` | `Status:` is missing or not one of the five tokens. Reports `bridged: false`; no other rule runs. | error |
| `NOT_BRIDGED` | `Status:` is `draft` or `superseded-by` — the bridge has not happened. Reports `bridged: false`; no other rule runs. | info |
| `MAP_NOT_CONFIGURED` | No `map` in the config (or `null`), no config at all, or a map orient reports as `mapUsable: false` — nothing usable to validate against; for an incomplete map the message names the missing keys. | error |
| `ROW_MISSING` | An AT row's `Row` cell is empty while `Status:` is `agreed`, `building` or `shipped`. | error |
| `ROW_ID_FORMAT` | A `Row` value does not match `map.rowIdPattern`. | error |
| `NO_ROW_ID_PATTERN` | `map.rowIdPattern` is not configured; `ROW_ID_FORMAT` is skipped. | warn |
| `INVALID_ROW_ID_PATTERN` | `map.rowIdPattern` is configured but does not compile as a regex — the exception text is carried in the message; `ROW_ID_FORMAT` is skipped, same as absence, but this is a misconfiguration, never silently treated as "no pattern". | error |
| `ROW_NOT_FOUND` | `map.row` is configured and `adapter.py row <id>` reports a non-zero exit or empty stdout. | error |
| `NO_MAP_ROW_COMMAND` | `map.row` is an empty string — still a string, so the map counts as usable, but no command is configured; the drift check against the map is skipped (an absent or non-string `map.row` is `MAP_NOT_CONFIGURED` instead). | warn |
| `SNAPSHOT_LINE_MISSING` | §6 has no line starting `Snapshot taken at` (a leading backtick or asterisk tolerated). | error |
| `THEN_NOT_IN_MAP` | When `map.row` prints the row as a JSON object with a `scenarios` list (the starter map does): a row's `Then` equals no scenario's `then`, case and runs of whitespace aside. Otherwise: the normalised `Then` is not a substring of the row's normalised text — a canary, not proof of agreement. The message names the three causes: the map moved on since the snapshot, the row was filed differently, or §6 was edited after the snapshot was taken. | warn (error under `--linking`) |
| `ALTITUDE_NOT_IN_MAP` | A JSON row has a scenario whose `then` equals the row's `Then`, but none of those scenarios has the row's `Altitude`: a link needs the same altitude. | warn (error under `--linking`) |
| `ALTITUDE_MISSING` | One finding for the §6 lines with no `Altitude` (an older table with no such column; the lint warns `ALTITUDE_MISSING`) whose `Then` equals a scenario that has an altitude: their altitude was not compared, and they are not drift. A link needs the same altitude, so under `--linking` this is an error. | info (error under `--linking`) |
| `SHIPPED_WITHOUT_GATE` | `Status:` is `shipped`, a §6 line did not go red (no real `Red gate:` line, or the line is listed in `Filed without red run:`) and no `Kill:` line names it, and the line cites a row that is not `origin: backfill` with `verdict: proven` — or whose `map.row` output is text, or with no `map.row` command, so neither can be read. A shipped doc carries proof that each §6 line was seen to fail: a red run, a `Kill:` line, or a proven backfilled row (framework § Lifecycle); `lint_outcome.py` reports such a line with no `Row` (`SHIPPED_NEEDS_GATE`). `check.py`'s gate step runs this script on each doc with such a line, and fails on an error. | error |
| `ROW_TEXT_ONLY` | `map.row` printed text, not a JSON row with a `scenarios` list, for the rows named: their `Then` was checked as a substring and no altitude was compared, so an exact link is not checked. | info |

`--strict` promotes every warn to error. `--linking` is for the run that makes the
links (`arm`'s bridge): it promotes only `THEN_NOT_IN_MAP` and `ALTITUDE_NOT_IN_MAP`,
because there a mismatch is a wrong link, not drift. Exit 0 with no error-severity
finding; 1 with any error; 2 on a usage error. Human output is one
line per finding, then a summary line `bridge: <n> rows, <m> mapped, <k> drifted`.
`--json` prints one object: `{"path", "status", "bridged", "mapConfigured", "rows":
[{"id", "row", "line", "found", "inSync", "exact"}], "findings": [{"rule", "line", "message",
"severity"}], "stats": {"rows", "mapped", "drifted", "errors", "warnings"}}`; a row's
`exact` is true when its `Then` and `Altitude` were compared with a JSON row's scenarios,
false when the map printed text, and null when no lookup ran. `arm` runs
it with `--linking` once the `Row` column and snapshot line are written, and fixes every error before
continuing; `reconcile` runs it before reading the map, because a `THEN_NOT_IN_MAP`
or an `ALTITUDE_NOT_IN_MAP` finding means §6 no longer says what the map says.

## 11. Rules for every file in this skill

- **Cite the framework by section; never restate it.** "§6 rows — framework § *Section
  rules*" is a citation. A paragraph explaining what §6 is, is a copy. A mode's header names
  the framework sections it needs (`outcome-framework.md § The contract · § Lifecycle`) and
  reads only those, through `scripts/framework_section.py`; only `new` needs most of it. A
  cited name is one `framework_section.py --list` prints — a `## ` heading of the framework
  itself, never a heading inside a fenced example.
- **Each mode file opens with a 3-line header**: `Read before this:` (the reference files
  this mode needs), `Phase 0 line:` (what to state), `Writes:` (which files it may touch).
  A mode that reads a project file only at a later step (`arm`, `intake`, `reconcile`) adds
  one `Read at <step>:` line between the first and the second.
- **Sanitised.** No real people, companies, repo paths, dates or ticket ids from any
  project. Actors in examples are `Ana`, `Ben`, `Ollie`. Project-shaped facts are shown as
  config, never as prose.
- **Every recommendation put to the user is one option marked `(Recommended)` first, with
  one concrete reason.** Every decision is the user's; the skill never resolves a
  `BLOCKING` question by drafting.
- **The user's edit enters, not the candidate.** Wherever a slate or draft is approved
  with changes, the changed text is what is written.
- **Verify before believing.** A current-state claim carries `file:line` the writer read
  this run. A test found uncited is evidence only after it was watched dying.
- **Say what was not checked.** Every mode's close-out names what it could not verify.
- **Never require syntax.** A mode word is a shortcut; the input decides (§4). `/promise fix
  the doc` gets `revise`, not a usage message.

## 12. Tests for the scripts

`python3 -m unittest discover -s tests` must pass on a clean checkout with no
third-party packages. The suites, one file each:

- `test_scripts.py` — the lint over one fully conforming doc (exit 0) and over one fixture
  per `error` rule in §9 (each is caught, and only it); `--strict` promotion; `orient.py`
  against the fixture mini repo (`package.json` + `pnpm-lock.yaml` + `docs/designs/` with
  one outcome doc, plus a complete map config) and against an empty directory (all-null,
  warnings present, exit 0); the config allowlist and type rules of §5; `outcome_rows.py`
  round-trips the conforming fixture; `adopt.py` on a temp project (dry-run writes nothing;
  first run creates the config and the CLAUDE.md section; second run is a byte-identical
  no-op; a hand-edited block is restored in place; a missing CLAUDE.md is created; a
  pre-existing config is never overwritten; malformed markers are refused; line endings and
  a BOM survive) and `orient.py` then reports `adopted: true`.
- `test_lint_hardening.py` — the second-shape variants of the header, `RULES_FORMAT`,
  `ACCEPTANCE_TABLE`, `PLACEHOLDER` and `HEADINGS_BARE` rules, `FENCE_UNCLOSED`,
  `--template` (and that a freshly rendered doc fails with `PLACEHOLDER` findings only),
  and `UNREADABLE` (`lint-hardening/not_utf8.md`).
- `test_acceptance_columns.py` — §6 columns matched by header name, never position;
  duplicate headers; a malformed table beside a valid one.
- `test_status_authority.py` — the status-authority wording in SKILL.md and arm.md,
  `BUILDING_NEEDS_GATE`, and a frozen allowlist of every sentence under `skills/promise/`
  that pairs `agreed`/`shipped` with a transition verb: a new one fails until a human reads
  it, and a stale entry fails too.
- `test_followups.py` — `orient.py --input-file` mode inference, rule by rule and against
  every example in the §4 table; `--write-counts`; `--search` / `--search-file`.
- `test_intake_phrases.py` — every intake phrase §4 lists infers `intake`.
- `test_kill_record.py` — a shipped doc covers each §6 line by a red run or a `Kill:` line:
  a prototype doc with a kill for every line, a mixed doc, one kill missing, a malformed
  record, and `check.py --no-map` on each.
- `test_prototype_door.py` — the prototype phrasings start in `new` and are not sized
  `deferred`; the router, sizing, arm, reconcile, onboard and the README state the door's rules.
- `test_adapter_render.py` — `adapter.py` (argv assembly, every refusal, `show`, `checks`,
  `verify`, `surfaces`, `--query-file`, the `mapUsable` gate) and `render_outcome.py` (refuses to
  overwrite, refuses a missing docs home with exit 2, `--dry-run`, `--json`, slugs).
- `test_orient_render.py` — `orient.py`'s refusals (exit 2, one line, never a traceback),
  every config warning §5 lists, the fenced-illustration doc scan, the digit-run hint;
  `framework_section.py`; `render_outcome.py` and `--create-docs-home`.
- `test_bridge_validate.py` — every rule in §10's table in its stated order, against
  `fixtures/bridge/` and a fake `map.row` command, including hostile row ids.
- `test_shape.py` — this file's own rules: line budgets, the mode headers, relative links,
  the sanitiser, the example config, the template lints clean, framework sections resolve.
- `test_examples.py` — `examples/*.md` lint with exit 0 and `bridge_validate.py` runs
  against `examples/minimap/`.
- `test_adopt_hardening.py` — `adopt.py`'s refusals (a wrong-typed path, a hostile
  `--docs-home`, a non-UTF-8 `CLAUDE.md`), symlink and file-mode preservation,
  `"version": 1`, the all-or-nothing `commands` object, and text inside the markers that
  adopt did not write (an ATX or setext section kept above the block, in `CLAUDE.md` or
  `AGENTS.md`, CRLF kept; a line in no section refused; a longer fence not closed early).
- `test_agents_md_home.py` — the section in `AGENTS.md`: found through a `CLAUDE.md`
  import or with no `CLAUDE.md`, refreshed there, never copied into `CLAUDE.md`, and a
  warning when both files hold it.
- `test_other_hosts.py` — `install_skill.py` (each host folder, idempotent, refuses what
  is in the way, copy and dry-run modes), the git pre-commit hook it installs (blocks a §0
  change, passes a tag change, refuses an existing hook), `hooks/precommit.py`,
  `adopt.py --agents-md`, and the `.pre-commit-hooks.yaml` entries.
- `test_map_report.py` — citation matching (file and name, describe paths, pytest
  classnames and node ids), every bucket, the lane rule for verdicts, sibling citations as
  external, config lanes, the no-run view, `--strict`, usage errors, and the proofmap example;
  the reverse join (a case no row cites is an orphan, a sibling or bad citation homes
  nothing, `--orphans`, `--fail-on-orphans`), the map's `leftOut` list (a left-out case is
  no orphan, an entry that matches nothing is stale), `--surfaces` (unmapped and stale
  entry points, `--fail-on-unmapped`, with or without a run), the count of rows with no
  outcome doc, and `--fail-on-skipped` (a skipped citation passes `--strict` and fails
  this gate).
- `test_check.py` — `check.py` in a temporary git repository: a conforming folder passes,
  a lint error and an agreed doc whose §0 changed against `--base` each fail their step, a
  missing docs folder is skipped; the gate step fails a `shipped` doc with a §6 line no red run
  or `Kill:` line covers, over rows that are not proven backfilled rows, with `--no-map` and in the Action's
  shell too; the checks step runs `map.checks` in order as argv and
  stops at the first failure; the map step runs `map_report.py --strict` over `--junit`
  (read from `--cwd`) or `map.junit` (a path that does not exist yet, or one holding
  shell syntax, is left out and named), the orphan gate fails when there is no run to
  join, a config slip and a `Supersedes:` path still left whole are printed as warnings
  (exit 0) and a `map.requireHomes` that is not a
  boolean fails, the map-file rule, `--json`, usage errors, and the Action's own shell run with
  bash (with no `docs-home` input it lints the config's `docsHome`); the surfaces step
  runs `map.surfaces` (a string or an argv array) or `--surfaces-cmd` with no shell, fails
  on a non-zero exit (quoting stderr), an empty list or a timeout, and
  `map.requireHomes` turns on both gates.
- `test_diff_outcome.py` — §0 protection: tag and `Scenarios:` changes pass, any other §0
  change on a ratified doc is `S0_CHANGED` unless the status goes to `draft`; git and
  `--dir` modes; the hook blocks Edit, MultiEdit and Write and fails open; the Action,
  the hook config and the CI template are wired to the scripts.
- `test_thin_draft.py` — the thin draft: the filled fixture lints clean, `Depth: thin` past
  `draft` is `THIN_DRAFT` and brings back the full shape, an empty rules block is a warning
  only there, a §6 table and the `Scenarios:` claim are still checked, and
  `render_outcome.py --thin` writes the shape.
- `test_packaging.py` — the pre-install surfaces agree with the plugin: the marketplace
  description equals `plugin.json`'s, every mode count equals the number of mode files,
  `plugin.json`'s version equals the top CHANGELOG entry. A release bumps `plugin.json`,
  the top CHANGELOG entry, the pre-commit `rev` and `skills/promise/VERSION` together.
- `test_skill_version.py` — the skill's own version: `VERSION` equals `plugin.json`'s,
  `orient.py` reports it as `skillVersion` (null without the file), `adopt.py` writes it
  into a fresh config as `minSkillVersion`, and an older copy of the skill warns.
- `test_changed_rows.py` — `changed_rows.py` in temporary git repositories: a renamed
  cited test, bare file names, docsHome spellings and subfolders, a README, a doc renamed
  out, a moved map, a base map that does not parse, a minified map's links, a shallow
  clone, a non-ASCII path, `fields`, surfaces as a set, scenarios without ids, repeated
  scenario ids, a project in a subfolder, the `leftOut` list, the Markdown cap, the
  docs that name a row with no doc, and features (a relabelled row, the report's `features`);
  `section6Changed`, and a tiny claim (`--size tiny`, or `--body` with its `Size:` line)
  that exits 1 on a changed scenario, a new row, §0 or §6, a migration folder or database
  schema file (a JSON schema is not one), a `protectedPaths` entry read at the merge base,
  or a change to that list itself.
- `test_find.py` — the starter reader as a finder: stopwords never match, stems meet,
  a rare word outranks a common one, a title finds its row, a named id or alias comes
  first, `--check` warns on a missing title, and on `tests/fixtures/find/three-rows/find-eval.json` (the example map as it stood with three rows)
  BM25 beats the substring scorer it replaced; `learn` (a miss learned and then found
  first, nothing learned when already first, private words refused, a near-duplicate
  skipped, the oldest ask dropped, an ask that does not help taken out again), the
  asks `--check` validates and the ask conflict it warns about, and `adapter.py learn`;
  `refs sync` (refs from the Capabilities section only, the issues a Why closes, one
  eval case for a one-row pull request, skips, `--dry-run`), the refs `--check`
  validates, and `adapter.py refs-sync`; `--code` (Python and JS/TS imports one step,
  missing and unsupported tests named, `docRoot` as the project root) and `adapter.py
  code`.
- `test_junit_unittest.py` — `junit_unittest.py`: each case's file, class and outcome
  (failure, skip, a failing subtest, a module that fails to import), the exit codes,
  and `map_report.py` joining its run by method and by `Class::method`; `orient.py`
  finding a unittest suite, and pytest winning over it.
- `test_decisions.py` — `decisions.py`: `sheet` keeps unanswered §9 questions only, reads
  the owner and the BLOCKING flag from the doc, merges an asks file without letting it
  change them, carries the brief and each doc's §0, warns on a thin rich item, refuses a bad asks file, picks the surface hint, and renders a page whose
  embedded data cannot close its script element; `apply` appends one dated line under
  the question, never twice, leaves every other line alone (line endings and a BOM
  included), refuses a doc outside `--cwd`, reads pasted text, and returns the answers
  that name no doc question under `forAgent`.
- `test_decision_policy.py` — the decision policy: the `Decision policy:` value, a
  legacy doc with no line and no agent rows linting as before, the agent row's fields
  and review trigger, a protected category, a provisional row under `spec` or with no
  line, the words warning and adversarial categories; `render_outcome.py --policy`;
  orient's `decisionPolicy`; the sheet's read-only "Decided for you" group (outside the
  round, never `all recommended`, in the page, chat and twin) and an "Ask me instead"
  applied as a new BLOCKING §9 question with the row set to `asked Qn`; `promote`,
  `policy` (tighter surfaces agent decisions, looser leaves open questions open),
  `policy --open` (only open docs with no line, a dry run, a second run that stamps
  nothing) with orient's `legacyPolicyDocs`, and `recheck`.

Fixtures: every `error` rule in §9 has a fixture that fires it alone; `AGENT_NOTES_MANY`,
`HUMAN_HALF_BUDGET`, `ALTITUDE_MISSING`, `DECISION_POLICY_ALIAS` and `AGENT_DECISION_WORDS` each have one that fires as the only finding
with exit 0, and exit 1 under `--strict`. A violation fixture is the conforming doc with exactly one change, plus
the one forced edit where a single change would trip an unrelated rule
(`building_no_gate.md` drops the conforming doc's third, `UNTESTED` rule so
`UNTESTED_ON_AGREED` stays quiet — every fixture whose status is past `draft` does the same; the
acceptance-table missing/no-rows fixtures adjust the `Scenarios:` count;
`at_ids_unique.md` adds a fourth row reusing an id and moves the `Scenarios:` count with
it, because every existing id is cited from §0). A fixture that could not fail is worse
than none.

## 13. `adopt.py` — the config and the CLAUDE.md section

A project is **adopted** when it has a config (§6) and its `CLAUDE.md` carries the promise
section, so every person and agent working in that repository is routed to this skill
instead of writing a design, plan or spec doc by hand.

```
python3 "${CLAUDE_SKILL_DIR}/scripts/adopt.py" [--cwd <path>] [--dry-run] [--docs-home <dir>] [--no-config] [--no-claude-md]
```

- **Config**: writes `.claude/promise.config.json` if absent — `"version": 1`,
  `minSkillVersion` (the running skill's `VERSION`, when it has one), `docsHome`
  (from `--docs-home`, else orient's detection, else omitted), `commands` (always, with
  all three keys, the detected ones filled and an undetected one as `null`, so a new
  project sees where its test command goes; a `commands` object switches detection off,
  so `orient.py` warns when a `null` key now has a detected command, and `arm` proposes
  `commands.test` when it is `null`),
  and `"map": null` with a sibling `$comment` naming the starter map
  (`start_map.py`) that `arm` will offer, and pointing at `references/config.md`. It never overwrites an existing config, and says so. It does not
  create the docs folder: `--docs-home` records the user's choice, and the folder is made at
  the first `new`, on the user's explicit say-so (`render_outcome.py --create-docs-home`).
- **CLAUDE.md section**: renders `templates/claude-md-section.md` with `{docsHome}`,
  `{configPath}` and `{frameworkPath}`, and places it between `<!-- promise:begin` and
  `<!-- promise:end -->` markers: appended after a blank line when absent, replaced in place
  when present, `CLAUDE.md` created at the project root when no file exists. adopt only
  removes text adopt wrote: inside the markers, a section under a heading the template never
  wrote (ATX `## …` or setext, outside a code fence) is kept, unchanged, just above the
  begin marker, with one line on stderr and `movedAboveBlock` (`[{"path", "lines": [first,
  last], "heading"}]`) in the JSON result; a heading under the promise heading, a line above
  the first heading (or in a block with no heading) that is not a rendered line, and a block
  with no promise heading beside a foreign one are refused (exit 2, with their line
  numbers), since they cannot be told apart from a hand-edit; any other difference inside
  the markers is a hand-edit of promise's own lines and is restored in place. The rendered
  block is ≤ 20 lines and says: capability work goes through `/promise` in plain words (the
  mode is inferred); one doc per capability in the docs home, in the Outcome Framework
  shape; §0 is the human's verbatim block and agents only append notes below it; `Status:`
  reaches `agreed` and `shipped` only by a human's hand, `building` only after the human
  approves the red-test commit; where a map is configured it is the source of scenarios
  after `agreed`, §6 is then a snapshot nobody edits, and a verdict moves only at the
  altitude the row's own `Then` claims; before writing any design, plan or spec doc by
  hand, run `/promise` — a sibling doc is a bug.
- **In AGENTS.md**: when `CLAUDE.md` imports the root `AGENTS.md` and holds no section,
  or there is no `CLAUDE.md` and `AGENTS.md` holds one, the section is written and
  refreshed in `AGENTS.md` and `CLAUDE.md` is not touched (one line on stderr says so);
  the JSON result then carries `agentsMdWritten` and `agentsMdPath`. `--agents-md` writes
  the same block into `AGENTS.md` as well as `CLAUDE.md`, unless they are one file.
- **Idempotent**: a second run with the same inputs changes no bytes and reports
  `"changed": false`. `--dry-run` prints a unified diff and writes nothing. A symlinked
  `CLAUDE.md` is written through its link and keeps its file mode; whitespace around the
  end marker is tolerated, and restoring a hand-edited block says so on stderr.
- Exit 0 on success or no-op; 2 on a usage error or a refusal — a `--docs-home` that is
  absolute (a drive letter included, on every OS — orient's own escape rule, imported),
  escapes the project, or holds a newline or a marker string; a `--docs-home` that
  disagrees with an already-loaded config's `docsHome` (edit the config instead; a
  `CLAUDE.md` naming one folder beside a config naming another is drift); a `CLAUDE.md` or
  config path that is a directory or sits under a file; a `CLAUDE.md` that is not UTF-8;
  markers that cannot be resolved (a begin with no end, two begins, an end before its
  begin); text inside the markers that cannot be told apart from the promise section (above) —
  with the JSON result still on stdout and nothing written. A `--docs-home` written with
  backslashes is recorded with forward slashes, and a fresh config that would pin no
  `docsHome` says so on stderr. Prints one JSON object on stdout:
  `{"configWritten": bool, "configPath": "…", "claudeMdWritten": bool, "claudeMdPath": "…", "docsHome": "docs/designs or null", "changed": bool, "dryRun": bool}`,
  plus `movedAboveBlock` when a section was kept above the block.

### `start_map.py` — the starter capability map

```
python3 "${CLAUDE_SKILL_DIR}/scripts/start_map.py" [--cwd <path>] [--dest <folder>] [--dry-run]
```

Copies `templates/starter-map/` into `--dest` (default `docs/capabilities`), filling
`{dir}` in the recipe with the destination and `{docRoot}` in `map.json` with the path
back to the project root, so a row's `doc` is its project-relative path. Then sets the
loaded config's `map` object — `recipe`, `find`, `row`, `nextId`, `rowIdPattern`
(`^CAP-\d+$`), `lanes` and `checks`, every command an argv line run from the project
root — and drops the top-level `$comment` only when it is `adopt.py`'s own "map is not
configured yet" note. Refuses, exit 2, writing nothing: no loaded config (adopt
first); a config whose `map` is already an object; a `--dest` that escapes the project,
is `.`, holds a space, or already holds files. `--dry-run` prints the files and the
config diff to stderr. One JSON object on stdout:
`{"dest": "…", "configPath": "…", "files": […], "filesWritten": […], "configWritten": bool, "changed": bool, "dryRun": bool}`.
`arm` and `adopt` offer it; neither runs it without the human's yes to the dry run.

The `adopt` mode confirms the docs home and the config contents with the user
(Recommended-first, one reason), runs the script, then runs `orient.py` and shows `adopted` is
now true. Every other mode offers `adopt` once per session when Phase 0 reports the project
is not adopted, and continues with the requested mode either way.

## 14. Scripts that exist, and scripts that are planned

Shipped (the seventeen in §3): `orient.py` (§5), `lint_outcome.py` (§9), `outcome_rows.py`
(§10), `adopt.py` and `start_map.py` (§13), `framework_section.py`, `install_skill.py`
(links or copies the skill into `.agents/`, `.codex/` or `.cursor/skills` for agents
other than Claude Code; `--git-hook` puts the §0 check in front of every commit),
`adapter.py` (runs every configured
command with the user's text as one argument — never a composed shell string; `find
--query-file` reads the query from a file; `verify --only <op>` narrows the verify run;
`surfaces --out <file>` runs `map.surfaces` and writes the entry points; refuses when
`mapUsable` is false),
`render_outcome.py` (instantiates the template; refuses to overwrite; `--create-docs-home`
is the only way it makes a folder), `bridge_validate.py` (§10: checks a bridged doc's §6
Row ids, snapshot line and `Then` text against the project's current map),
`diff_outcome.py` (§0 before and after, from two files or a git ref and the working tree;
only the rule tags and the `Scenarios:` count may change on an `agreed`, `building` or
`shipped` doc, unless the status goes back to `draft` — `S0_CHANGED` (error), `S0_REOPENED`
(warn); the plugin hook and the GitHub Action both run it), `map_report.py` (the map
joined to a JUnit test run: each citation `file::name` matched to a test case, a bucket
per row — failing, bad-citation, never-ran, skipped, not-run, passing, external, no-test,
where `not-run` is a lane whose suite is not in the run at all, never proof, named once
in `summary.lanesNotInRun` and not a `--strict` failure — and a
verdict computed from the lane each scenario's altitude picks, worst citation first,
compared with the recorded one: optimistic or promotable; it never writes the map). A
lane's suite is in the run once the run holds a file, a title or a folder the lane
cites, or a subfolder of one (in a run file named after a folder of the cited path,
such as `e2e.xml`, also a path recorded from that folder and a sibling folder under
it), so a lane whose every cited file was deleted reads `never-ran`. The
report also joins in reverse: every case in the run that no row cites is an orphan
(`--orphans` lists them, `--fail-on-orphans` exits 1 on one), and it counts the rows
that name no outcome doc. A test the map's `leftOut` list names (with a one-line reason
and a date) is left out on purpose, not an orphan. With `--surfaces <file>` it also
joins the code's entry points to the rows' `surfaces`: an entry point no row names is
unmapped (`--fail-on-unmapped` exits 1 on one), a row surface the list lacks is stale.
A cited test the run skipped proves nothing, but `--strict` fails only on a verdict
recorded higher than the run shows, so a row recorded `under-proven` passes with one of
its tests skipped. The JSON lists each one (`skippedCitations`, each `{id, lane, test}`,
and `summary.skippedCitationCount`), and `--fail-on-skipped` lists them in the tree and
exits 1 on one; `--strict` is unchanged.
The thirteenth script in §3 is `check.py`: what the Action checks, as one local command for
a team whose CI cannot run it, in six steps — **lint** (`lint_outcome.py` over docsHome),
**§0** (`diff_outcome.py --dir` against `--base`), **gate** (`bridge_validate.py` on each
`shipped` doc with a §6 line no red run and no `Kill:` line covers, so `SHIPPED_WITHOUT_GATE`
fails the run; with no map, or an incomplete one, such a doc fails the step, since no row can be read as a proven
backfilled row), **checks** (the config's `map.checks`,
in order, as `adapter.py checks` runs them), **surfaces** (the `map.surfaces` command, or
`--surfaces-cmd`) and **map** (`map_report.py --strict` over `--junit` or the
`map.junit` paths that exist, and that entry-point list, when the map is usable). Every
step is a subprocess with an argv list and no shell, reported as one
`promise check: <step>: ok|failed|skipped (<reason>)` line; exit 1 when a step failed.
Before the steps, each of orient's config warnings prints as one
`promise check: warning: <text>` line, since a config slip can turn a gate off. So
does each path on an outcome doc's `Supersedes:` line that still exists and is more
than one line naming the doc (a folded doc at `superseded-by` aside): a warning, never
a failure, since a human may keep a file on purpose.
`map.requireHomes: true` turns on `--fail-on-orphans` and `--fail-on-unmapped`, and a
value that is not a boolean fails the map step; the orphan gate fails, never passes, when
there is no run to join. `--fail-on-skipped` is passed to the report, and fails the step
with no run to join, as the orphan gate does. Relative paths are read from `--cwd`. The Action runs it with
`--no-map`, so lint, §0 and gate (`--no-map` does not skip the gate step: it needs no
test run, and runs `map.row` only for a doc with a §6 line no red run or kill covers), plus the map's
own checks with the `map-checks: "true"` input (`--map-checks`: `map.checks` needs no
test run either, and on a pull request's merge finds a row the merge lost; the workflow
`adopt` writes sets it, with full history), and with no
`docs-home` input reads docsHome from the config. With the `tiny-check: "true"` input
(also set by the workflow `adopt` writes) it then runs `changed_rows.py --body` on the
pull request's body from the event payload: a body whose `Size:` line says tiny fails
the job when the diff touches what tiny may not (§14). Each script's flags are in the section cited for it, or in its own docstring.

`decisions.py` serves `references/decision-sheet.md`. `sheet` reads the §9 questions of
the docs named (else every doc under docsHome) and keeps those with no `Answer (` line
dated in `YYYY-MM-DD` form; an asks file enriches one by its `<doc path>#Qn` id (options,
detail, code, image, links) or adds a decision outside the docs, never changing a
question's text, owner or BLOCKING flag. Each item carries a brief (why, blocks,
ifNoAnswer, example, `path:line` evidence) and each option a `then`; a `rich` sheet lists
`warnings` where they are missing, and `docs` holds each doc's §0 outcome, rules and
signal verbatim. A bare `§n` in what a person reads is given its section's name;
`unclear` lists a question, issue, row or item number with no words beside it, a
question that holds its own recommendation, and lines to confirm that are not shown,
and with any listed `sheet` writes no page, chat message or comment. `plain` puts a
doc question in plain words, with the doc's own words kept as `docText`. `words` holds
the terms the sheet uses, from the configured map's `glossary`, then the asks file's
`words` for one the glossary lacks. The page links each term's first use on a card to
its meaning. It prints the sheet (`--json`) with a `surface`
hint (`ask-questions` for at most four plain items, else `rich`) and renders
`templates/decision-sheet.html` (`--out`) in the form the Artifact tool publishes, with a plain Markdown twin (`--md`, only when asked for) for agents and editors;
one sheet is a round of at most 12 items (`--limit`, `--all`), BLOCKING first, and
`counts.later` says how many wait; `--asks-skeleton` writes this round's asks file to
fill, and `--prompt-json` prints it as question-prompt batches with each option's
reply code; `triage --out DIR` splits the open questions into packets for research
agents and `merge-research` checks their results (`answered` and `stale` need
`path:line` evidence that exists, `same-as` another open question) into the asks file,
where an answered item joins one "Checked by research" group outside the round limit
and a `sameAs` item is settled by the other's answer (`alsoAnswers`); `--chat` writes the sheet as one message (numbered items, lettered choices), `--comment` as a GitHub comment that carries the sheet's data, and `--only` keeps the items named. `apply --reply <file> --sheet <comment or JSON>` reads a person's short reply (`all recommended`, `1a 3c - note`, `2: words`) against that sheet, and refuses one it cannot read with every reason. `apply`
reads the page's `promise-answers` JSON, or pasted text holding it, and appends
`Answer (<date>, <by>): <text>` under each question; §0 and the Status line are never
touched, and answers that name no doc question come back under `forAgent`.

The agent decisions of each doc's §8 (Owner `agent`, `State: provisional`;
outcome-framework.md § Decision policy) join the sheet as one read-only group, "Decided
for you" (kind `decided`, id `<doc>#Dn`): outside the round and `counts.round`, counted
in `counts.decided` only when there are any, never picked by `all recommended`, never
enriched or skeletoned by the asks file. A sheet with no agent rows is byte for byte
what it was. Its one action, "Ask me instead" (`<n>a`), reaches `apply` as an answer
of kind `decided` naming the row; `apply` appends a new BLOCKING §9 question for it,
with a `Why asked (<date>, <by>): …` line, and sets the row's `State: asked Qn`.
`promote <doc> --decision <n> --by <name> [--reason …]` does the same for rows named by
hand (a human's objection, the arm re-check). `policy <doc> --to <value> --by <name>`
writes the header line the human picked and a §8 row that records it; tighter to
`spec` promotes every provisional row, tighter to `auto` promotes the rows named in
`--promote` and lists the rest under `toJudge`, and looser writes no question and
answers none (`openQuestions` lists what stays open). `policy --open --to <value> --by
<name> [--docs-home <dir>] [--dry-run]` does the same, on one human yes, for every doc
orient counts in `legacyPolicyDocs`: at `draft`, `agreed` or `building`, with no policy
line. Docs at `shipped` or `superseded` and a line a person wrote are left alone; the
edits stay in the working tree for the human to commit; `--dry-run` lists them; a
second run finds nothing to stamp. `recheck <doc> [--date]` lists
the provisional rows due at arm: Review `before arm` or a review date that has come,
and a reversible-until that names arm or a date that has come.

Two scripts serve the text a reviewer reads (`references/github-text.md`).
`changed_rows.py` compares the map at the merge base of `--base` and `--head` with the
map at the head, for the project at `--cwd` (its config read there, so a project in a
subfolder of its repository works): each row is `added`, `removed`, `changed` (story, a
scenario by id or else by its `then`, verdict, an evidence array, surfaces as a set, doc,
or any other top-level key in `fields`) or `touched` (unchanged, but a file it cites, a
file its text names by a path with a folder or by a bare name with a `:line` or unique in
the tree, or its outcome doc changed; a renamed file counts by its path before, so a row
whose cited test moved away is touched) or `relabelled` (only its `feature` changed). Each
row carries its `feature` and lists the cited files missing at the head, and a row with no
doc the outcome docs that name it; the report's `features` groups the moved and touched
rows by feature, with the names the map gives them. Beside them, the outcome docs
changed in `docsHome` or one folder below (not a README) with their status before and
after and whether §0 moved (`section0Changed`) and §6 (`section6Changed`), the `leftOut`
entries added or removed, and the changed files no row names or cites. `--size tiny`, or
`--body FILE` with a pull request body whose `Size:` line (under "Why") says tiny, checks
the claim: the report's `size.touches` lists each changed scenario or new or removed row,
each doc whose §0 or §6 changed, each migration or schema file (`migrations/`,
`alembic/versions/`, `db/migrate/`, `.prisma`, `schema.rb`, `structure.sql`, a
`*schema*.sql`), each path the config's `protectedPaths` covers (the list as it was at the
merge base, plus any the head adds) and a change to `protectedPaths` itself; anything there
exits 1 after the report. A base map that does not parse is a warning; a moved map is read
at its base path. `--json` for `pr` mode, `--markdown` (capped at 40 items a list) for
the `<details>` block, `--link ID` for a row's permalink at `--head`, followed by the docs
naming a row with no doc, which `issue` mode uses.
`lint_github_text.py --kind issue|pr` checks only the block between the promise markers:
the sections, the word budget outside `<details>` (a link as its text, a path as one
word), sentence length and code words in the people section, a linked issue, one to three
`path:line` items, each ask starting with its relation, a route when an ask needs
building, a question for each DECISION, row ids and the verdicts beside them against the
map, a meaning beside each row id and no range of ids (`--kind doc` runs these id rules
alone on any Markdown file), and — with `--changed` — every row the change moved named, or counted past 12. It
also checks the first screen (`references/first-screen.md`): an issue's intro block at
the top of the body, the features and the "Needed from you" line under "Where this is",
the terms under "Words", and — with the map's `features` and `glossary` — that each feature
is the map's, each named or moved row's feature is listed, and each glossary word the
reader meets is explained.

Planned, in the order they pay back. Each replaces a step a mode performs today by reading
prose — the model follows the rule and no script checks it, so
`references/anti-rationalizations.md` is the guard until the script ships, and drift is
the cost of not having it:

| Script | Replaces | Used by |
|---|---|---|
| `inspect_outcome.py DOC` | status, BLOCKING count, lint result, §0 text, note count, UNTESTED rules, counts, Row references — one JSON for every close-out | new, revise, review, arm, reconcile |
| `erosion_diff.py BEFORE AFTER` | the three erosion classes outside §0 (an OPEN decision turned assertion, operational content with no stated home), as a diff the model then judges | revise, review, merge |
| `evidence_probe.py --ref PR\|SHA\|BRANCH\|FILE` | declared row ids, cited and uncited test titles, ranked candidates (`changed_rows.py` gives the changed files and the rows they touch) | reconcile, intake |
| `kill_witness.py --test … --mutation …` | clean-tree check, apply the approved mutation, capture the named failure, restore exactly, rerun green, print the witness | intake, reconcile |
| `arm_gate.py DOC --branch SLUG` | the Git preflight, the red run, staged-path inspection, the two explicit-path commits (the red gate, then the doc) | arm |
| `issue_search.py --tracker … --row … --text …` | open and closed duplicate candidates before any issue is filed | intake, reconcile |
| `feedback_items.py INPUT` | numbering already-structured items and flagging compound sentences; the split stays a judgement | intake |
| `inventory.py --docs-home DIR --query TEXT` | §0 rules, §5 claims and §6 rows across docs, exact duplicates, ranked overlaps | new, merge |
