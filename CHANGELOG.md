# Changelog

## 1.44.1

- First public release. The decision-sheet screenshots use fictional names and answers.
- Plugin, GitHub Action and pre-commit install examples use the public repository URL.

## 1.44.0

- Prepared a standalone release snapshot.
- GitHub Actions runs tests and releases on GitHub-hosted runners.

## 1.43.0

Released 2026-11-23.

- Two front doors. The README now shows "start from an idea" and "start from a
  prototype" side by side. Say "I built a prototype" or "lock in what I built" and
  the skill starts the prototype door: you write and agree the promise, `arm` files
  rows for code that already works without a red run and never stubs it, and
  `reconcile` proves each row by a test watched failing under a mutation. A new
  README section, "Run it unattended", says what can run without a person and why
  the promise itself never can. A new eval case, `prototype-door`, checks it.
- A doc from the prototype door can be shipped. `arm` writes one line under the
  §6 table that names each line it filed without a red run
  (`Filed without red run: AT-2, AT-4 — prototype`), and `reconcile` writes a `Kill:`
  line for each mutation it watched make a test fail. A shipped doc needs, for each §6
  line, a red run, a `Kill:` line, or (with a map) a proven backfilled row. The lint,
  `bridge_validate.py` and `check.py`'s gate step check this, with or without a map.
  Two new lint rules check the record: `KILL_RECORD_FORMAT` and `KILL_RECORD_UNKNOWN`.
  A decorated record line never helps: a Filed line still takes its lines' coverage away,
  and a Kill line counts only when written plain. No script checks that a Kill sha exists,
  so a reviewer does.
- The first time a project is set up, `adopt` asks the decision policy once, in plain
  words: "Ask only the risky things" (recommended), "Ask me everything" or "Let me move
  fast". With no answer it writes `auto` and lists that under Decided for you. A project
  that already has a policy is never asked. `adopt.py --policy` records the choice.
- The loosest policy is now called `fast`, so it no longer clashes with starting from a
  prototype. Docs and configs that say `prototype` still work and read as `fast`; the
  lint warns (`DECISION_POLICY_ALIAS`) and asks you to write `fast`.
  `decisions.py policy --to fast` rewrites a `prototype` header, and `upgrade.py`
  rewrites a config's `prototype` to `fast`.
- A map groups its rows by `feature`, the word product teams use. The map's list
  is `features`, a row's key is `feature`, and the starter reader has
  `--features` and `--feature <id>`. The issue and pull request first screen lists
  "Features". The names `areas`, `area`, `--areas` and `--area` stay as aliases, so
  existing maps keep working. A map or a row that uses both names, or rows that mix
  them, is the new error `FEATURE_AND_AREA` in `--check`, in `lint_github_text.py` and
  in `changed_rows.py`. Lint rule ids such as `AREA_UNKNOWN` do not change. orient
  warns when a map, or the project's own reader, still uses `areas`/`area`.
- `changed_rows.py --json` now reports `features`, `featuresRelabelled`, each row's
  `feature` and `featureChanged`, in place of the `area` keys. A tool outside promise
  that reads that report must read the new keys.
- The size of an ask that needs a new outcome doc is now `capability`, so `feature`
  names only a part of the product. `feature` still works as an alias: `--size feature`,
  `Size: feature` in a pull request body, and a recorded run all read as `capability`.
  The lint warns with the new rule `SIZE_ALIAS` and says to write `capability`. The
  `feature-new` eval is now `capability-new`.
- Script regressions and an independent review cover these changes. The
  model-backed evals (`first-run-policy`, `prototype-door`, `capability-new`) have
  not been run.

## 1.42.0

Released 2026-11-13.

- A guided `onboard` interview helps users choose a first workflow from an idea,
  a new repo, an established product or an existing Promise setup. It reuses
  supplied answers and the decision sheet, then hands off to the existing modes.
- Backfill supports one explicitly selected pilot. Functional reports accept
  repeated `--row` flags and label their scope. Service reports and both viewers
  show when only selected capabilities were assessed. A pilot leaves global
  coverage checks and unrelated capability rows in place.
- Pilot coverage uses the full map to recognise shared callbacks and entry
  points. Its selected capabilities keep their own verdicts, and any failing
  test in the supplied pilot run still fails the strict check. Stale left-out
  notes from files in that run remain visible.
- Worked conversations and a standalone visual form demonstrate the starting
  points. Script regressions and independent review cover the implementation.
  Behaviour-eval fixtures are included; model-backed evals and a live user pilot
  have not been run.

## 1.41.0

Released 2026-11-13.

- Relaxed capability grouping
  is available as an opt-in trial. A row marked `"grouping": "job"` can retain
  more than five scenarios for the same stable user job. Each scenario names
  its own evidence citations. Strict reports catch missing or invalid citations
  even when the row's test lane is green. Existing rows and continuation links
  keep their current rules.
- Both fictional simulations replay with `run_simulations.py --trial` and
  preserve all 35 scenarios across nine capabilities. These fixed stubs and
  historical service observations exercise Promise tooling and establish no
  product assurance.

- Capability report summaries and SLA evidence now render as
  readable tables
  with plain field labels. Both HTML viewers preserve nested measurements,
  sources and reasons, and distinguish missing values, empty lists, zero and
  false. Tables adapt to narrow screens.

- A local whole-map HTML viewer
  shows every capability, scenario, test citation
  and optional SLA report. It keeps lane results, explicit scenario
  evidence and dated service assessments visible, with a capability index and
  expandable evidence. Export `map_report.py --json`, then run
  `render_map.py map-report.json --out capabilities.html` and open the file.
  Add `--service-report sla-report.json` for a full service report from the same
  map. Supplied assessments retain their method and evidence in the expanded
  tables. The page reports snapshots of evidence at their recorded times.

## 1.40.0

- [Promise Doctor](README.md#audit-promise-feature-adoption)
  checks SLA adoption and puts capability counts in context. Its read-only
  inventory separates available features, linked policies and dated observations.
  The upgrade preview includes setup suggestions tied to the map and export.
- A [local outcome viewer](README.md#view-a-rule-and-its-evidence-together)
  shows rules, acceptance rows and their evidence together as HTML or JSON.
  Recorded map verdicts, test-lane results and SLA observations remain separate.
  The view preserves the TLDR in JSON, shows acceptance rows without a rule
  tag, and includes the supplied source revision and UTC render time.
  Regenerate older map and SLA reports from the same map before combining them.
- Project-level `servicePolicies`, referenced by capability rows, express shared,
  open-ended service promises. Quantitative bands and qualitative/pass-fail
  criteria keep functional proof and service assurance separate.
- `service_report.py` evaluates generic higher/lower numeric metrics and observed
  request-success ratios, or records cited qualitative assessments with explicit
  scope, revision and method. Hard constraints cannot be traded away; missing,
  stale, insufficient or malformed evidence never passes.
- Includes search quality/time, request availability, throughput under offered
  load, and shared accessibility illustrations. These are examples, not a closed
  list of service types. Existing maps need no migration. The report collects no
  telemetry and does not independently verify supplied assessments.
- Shared policy changes appear in capability diffs and reject tiny-change claims.
  Large availability cohorts use exact count/extrema buckets with bounded inputs;
  row-scoped reports, evidence safeguards and deterministic regressions cover the
  review findings. Behavioural eval fixtures are included; model-backed evals were
  not run under this task's no-spend constraint.
- Verification has a bounded policies-only summary and row-scoped live reports.
  Historical malformed service metadata warns instead of blocking unrelated or
  repair diffs; newly malformed metadata is rejected. Replay is explicitly
  labelled, supplier text is bounded/escaped, and fresh hard breaches cannot hide
  behind insufficient sample counts. Small ratio cohorts alone remain unchecked.
- Added a [replayable simulation](examples/simulation-prep/README.md) for two
  fictional projects. The fixtures and four regression checks exercise functional
  and service evidence together. The [findings](examples/simulation-prep/FINDINGS.md)
  record 35 scenarios across 11 capability rows and a nine-row grouping to trial.
  The five-scenario limit and existing proof rules still apply.

## 1.39.1

- **The skill description fits claude.ai.** `skills/promise/SKILL.md`'s `description` was about
  1,640 characters with angle brackets; claude.ai allows 1,024 and cut the tail, so the later
  modes (issue, pr, adopt, upgrade) could be missed there. It is now under 1,000 characters with
  no angle brackets, and keeps every mode name and its main trigger phrases. Claude Code was
  never affected.

## 1.39.0

The decisions waiting on you, answered in a pane inside Claude Code: promise's first mod.

- **`hooks/decisions-pane.js`**, a Claude Code mod in the plugin itself (`hooks/hooks.json`
  names it under `modules`, beside the PreToolUse hooks, which are unchanged). It needs
  Claude Code v2.1.287 or later, and draws in the terminal and the Desktop app's Code tab.
  - It gives the agent the tool `mcp__promise__decision_pane`, only where a pane can draw.
    The agent passes the path of a sheet it built (`decisions.py sheet ... --json`) and
    ends its turn; the person picks each answer in the pane, with a field for a note or
    their own words, and **Save answers** runs `decisions.py apply`. What it wrote, and
    what is left for the agent, comes back as a message that starts the next turn.
  - `/promise-decide [doc ...]` opens the same pane from the person's side: the sheet the
    agent sent, or the open §9 questions of the docs named.
  - It decides nothing itself. The scripts build the sheet and read the picks; the pane
    draws each item's brief (why, what it blocks, what happens if left, the code to
    approve, sources, each choice's reasons) and one picker, and hands the picks over.
  - It shows what `sheet --out` would show, and refuses what it refuses: a sheet whose
    words a person cannot follow without the doc (§4). A sheet with an image goes to
    the Artifact page. Items left for a later round are counted, and handed back.
- **`decisions.py sheet --json`** gives each item its lettered `replies` (code, label,
  the answer it records, Recommended, `noteAsk`, the option's brief) and `replyWords`,
  exactly as a chat reply picks them. The page, comment and chat message are unchanged.
- **`decisions.py apply -`** reads answers from standard input, including the pane's
  `promise-picks`: the sheet and one pick per item. They are read through
  `answer_entry`, the same function a chat reply goes through, so a pick writes the same
  §9 line on every surface. A request for changes must say what.
- **`references/decision-sheet.md`** puts the pane first among the rich surfaces, ahead
  of an Artifact; where nothing draws (`claude -p`, the VS Code panel, a cloud session)
  the tool is not offered and the surfaces there are as before.
- **`session_report.py`** counts a sheet sent to the pane as published, so
  `sheet-not-published` no longer fires for it.
- **CI** runs `claude plugin validate --strict` and the mod's tests (`claude plugin test`,
  `tests/mods/`).

## 1.38.0

A row id never stands alone, in a pull request, an issue or a plain doc.

- **`ID_RANGE` (error):** `CAP-4 to CAP-9`, `CAP-4–CAP-9` or `CAP-4–9` hides what each
  row means; name each one. "Moved from CAP-3 to CAP-4", a number after an id, and ids
  in a link's target, a URL or a path are not ranges.
- **`ID_BARE` (warn):** a row id with no meaning beside it. A comma, colon, dash or
  bracket followed by words gives one, and so do words before the id in brackets, or the
  row's own title words a few words away. Ids in code, tables, `<details>`, the
  "Touched, verdicts unchanged:" line and a tracker key after "Closes" are exempt.
- **`lint_github_text.py --kind doc <file>`** runs the row-id rules (with `ROW_UNKNOWN`
  and `VERDICT_WRONG`) on any Markdown file, with no section or template rule.
  `/promise pr` runs it on each changed `.md` file outside the outcome docs.

## 1.37.0

Build first, promise after, and nothing is lost.

- **A fifth size, `deferred`, given in the person's own words** ("ship it first",
  "hotfix", "spike", "promise it later"; never the agent's choice). The change is built
  now: no doc, no row, no mode, and no question but the session's first-command yes.
  - A protected category still has every decision in it asked, as for a risky ask:
    deferral waives the paperwork, never the decisions that are hard to undo.
  - The tests there are run, and what did not run is said under Not checked.
  - orient's `suggestedSize` says `deferred` for those words (hotfix and spike only as
    the ask's first word, so "a spike chart" stays a product ask), and still names a
    protected category beside it.
  - `session_report.py --record --size deferred` records the run.
- **What is owed is written down.** The pull request's block says
  `Size: deferred — owes: <each promise touched or made>`. `lint_github_text.py` takes
  it, requires the `owes:`, and asks only for Why and Proof; the rest are warnings.
- **And paid back.** `/promise reconcile` with no input lists the merged pull requests
  still owed, oldest first (`scripts/deferred.py`, through `gh`). Paying one is a
  reconcile of that pull request: the rows, the tests, a mutation watched failing. Its
  block then gets a `Paid:` line; `Paid in part:` keeps it on the list.

## 1.36.1

Every release gets its tag and its GitHub release.

- **`.github/scripts/release.sh`**, run by the `release tags` workflow on every push
  to `main`, and by a maintainer from an up-to-date `main` when Actions cannot run:
  - it tags `v<version>` on the first commit whose `plugin.json` names that version,
    and a release tag never moves;
  - it moves `v1` to the newest release;
  - it publishes the GitHub release with that version's CHANGELOG entry as its notes
    (`changelog_entry.py`), marked latest only for the newest.

  `--all` publishes a release for every tag that has none. `--check` exits 1 while the
  version on `main` has no tag. Re-running is safe.
- **`pin_check.py` names an untagged release:** "upstream main is at 1.36.0, but its
  newest release tag is v1.33.0". `--strict` does not fail on it, since it is
  upstream's to fix, not the repository's.

## 1.36.0

GitHub text reaches GitHub only through the lint.

- **`post_github_text.py`** lints a body file, posts it with `gh` only on a pass
  (`--number`, or `--new --title`), then reads back what GitHub stored. Things it
  handles on read-back:
  - The footer an agent's GitHub integration appends is known, and ignored.
  - Anything else that changed is a finding, and so is a stored body that fails the lint.
  - Links that came back wrapped in backticks are named, because they no longer
    render as links.

  `--verify <n>` only reads back. `/promise pr` and `/promise issue` post through it.
  With no `gh`, they post with the MCP tool, then verify.
- **A hook before any post.** `hooks/guard_github_text.py` runs before a GitHub MCP
  write (create or update a pull request or an issue) and before
  `gh pr|issue create|edit` with a body. In an adopted project:
  - a body whose promise block fails the lint is blocked, with the findings;
  - a new one with no block asks the person first.

  It fails open.
- **The templates, for every repository.** `adopt.py --github-templates` copies the
  issue and pull request templates where the project has none, and a pull request
  template anywhere GitHub looks counts as the project's own. orient reports
  `githubTemplates`, and `adopt` offers them in a `"map": false` project too.
- **Sibling rows are checked.** Beside `"map": false` with a `sibling`,
  `lint_github_text.py` reads the sibling's map from its checkout, so `ROW_UNKNOWN`,
  the verdict and area rules all work. No checkout there → `SIBLING_UNREAD` (warn).
- **Smaller fixes:**
  - An `Also:` area name the map's `areas` hold counts as explained, so it no longer
    raises `TERM_UNDEFINED`.
  - `github-text.md` says which link to use for a row the branch moves: the branch's,
    with its verdict. It also gives the fallback when permalinks come back mangled.

## 1.35.0

A repository learns that its pin is behind while upstream is private.

- **`upstreamPath`: read a private upstream through a local checkout.** A new config
  key, or `PROMISE_UPSTREAM_PATH`, or `--upstream-path`, names a promise checkout the
  person already keeps. `pin_check.py`, `upgrade.py` and `pin_machine.py` then run git
  in that checkout, against its `origin`, with its own access:
  - `ls-remote` for `main` and the tags;
  - `show` for the files, fetching a commit the checkout lacks (objects only; none of
    its branches or tags move).

  No token passes through the scripts, and the network path still sends none. A named
  checkout that cannot be used is said so, never skipped for the network.
- **Unreachable says why.** A network upstream that cannot be read now adds a line:
  it may be private, name a checkout. `/promise upgrade` says the same when it stops.
- **A vendored copy moves only with its files.** A `pinFiles` site marked
  `"vendored": true` (the file that records a vendored copy's commit) is never moved on
  its own. `upgrade.py` refuses until the copy is synced, because the sha would name a
  release the copy does not hold.
- **A vendored copy with no pin is named.** `pin_check.py` says the skill runs from a
  copy inside the repository and names its folder, where it used to say only "no pin
  found".

## 1.34.0

A premise is a claim, not a citation.

- **A negative, design-constraining claim gets a row, not a sentence.** A cross-repo
  design once cited a real file:line showing a meeting API returned participant ids
  and no emails, and stated as fact that the source "can't say who spoke" — in §1
  Problem, not §5, since that is usually where this kind of claim first gets written
  down. The citation was true of the field checked and false of the entity: the
  participant id WAS the account id, which the other repository already stored and
  already joined on for a sibling connector, documented in two of that repository's
  own design docs, and nobody had searched for it. A design and a follow-up spike
  were built on the false premise before a reviewer caught it a day later. §5 now
  carries a **Load-bearing premises** table whenever a claim — in §1's account of
  current behaviour as much as in §5's own — depends on something being
  impossible, absent, or available in only one place: `Premise` / `Evidence` (the
  source's *whole* field or identifier set for the entity, not just the field
  checked) / `Existing join searched` (every repository or doc the capability
  touches, and what was found there) / `What would make it false`. The table's
  home is always §5, a §1 claim included — one home, not a second table.
  `lint_outcome.py` flags a row missing `Evidence` or `Existing join searched`
  (`PREMISE_TABLE`, error) and, as a warning, an unlisted negative phrase in §1 or
  §5 outside the table (`PREMISE_PHRASE`: "can't", "cannot", "doesn't have", "no
  way to", "unavailable", "only X has") — cleared by a COMPLETE row whose Premise
  cell quotes or closely restates the claim (a literal-text check, not a semantic
  one: a paraphrase still reads as unlisted), or by marking a genuine non-premise
  with `<!-- not a premise -->` on its line. `new` and `revise` build and
  re-verify the table — reaching back into already-drafted §1 prose, not only
  fresh §5 claims — before writing §5 (including the cross-repo search); `review`
  applies it as rubric item 9; `references/anti-rationalizations.md` names the
  excuse directly: "the citation is correct, so the conclusion is."

## 1.33.0

The pin a machine really runs, and one upgrade for
the repository and each machine.

- **Correction to 1.32.0: a `source.sha` pins nothing.** Claude Code's marketplace
  source reads `ref` (a branch or a tag) and nothing else, so a repository that pins
  `extraKnownMarketplaces.promise.source.sha` leaves every machine on the default
  branch. `claude plugin install --scope project` rewrites `.claude/settings.json` and
  drops the sha. And `claude plugin marketplace update` alone does not move a machine:
  Claude Code keeps a saved copy of the marketplace at the ref it was first added with.
  So the 1.32.0 step (`marketplace update`, then `plugin update`) does not move a
  machine by itself.
- **The pin is a release tag.** Each release on `main` is tagged `v<version>`, and the
  major tag `v1` moves with it (`.github/workflows/release-tags.yml`). The `v1` tag is
  also what `osouthgate/promise@v1` and pre-commit's `rev` name. A repository pins
  `"ref": "v1.33.0"`.
- **`pin_check.py`** reads the tag and upstream's newest release in one
  `git ls-remote`. It adds a line for each of these:
  - a `sha` pin that Claude Code does not read;
  - a `ref` that is a branch, or that upstream lacks;
  - a machine whose install in `installed_plugins.json` is not the pinned commit.

  `pinFiles` gains `"kind": "version"` for a pinned version such as `REF_VERSION`.
  Sites disagree when two commits differ, when two versions differ, or when a tag's
  commit differs from a sha.
- **orient** reports `promisePin` and `machinePlugin`, and warns on a `sha` pin and on
  a machine that is not on the pin. A session can no longer run one release against a
  repository pinned to another without saying so.
- **`upgrade.py`** replaces 1.32.0's `pin_move.py` and does the repository half of an
  upgrade in one dry run and one write:
  - every pin site to the tag: `source.ref` set, a `source.sha` dropped, `sha` and
    `version` sites moved;
  - the keys a config from an earlier release lacks (`decisionPolicy`);
  - `minSkillVersion` raised to the release.

  It also prints what the project's own recipe and reader lack of the starter map's:
  its sections, flags, subcommands and map keys. It writes none of that.
- **`pin_machine.py`** does the machine half, as tested:
  1. `claude plugin marketplace add <repo>#<tag> --scope project`, which moves the
     saved copy;
  2. `claude plugin update promise@promise --scope project`;
  3. puts back `.claude/settings.json` when Claude Code only reordered it;
  4. checks `installed_plugins.json` against the pin.

  `--user` does the same for the user-scope install. Restart Claude Code afterwards.
- **`/promise upgrade`** runs, on one yes:
  1. `upgrade.py`;
  2. `pin_machine.py`;
  3. `adopt` from the new release's install, so the section is the new release's and
     not the one being left;
  4. the checks and `pin_check.py`;
  5. the pull request.

## 1.32.0

A repository finds out its promise pin is behind, and moves it in one pull request.

- **`pin_check.py`: is this repository's pin behind?** It reads the plugin pin in
  `.claude/settings.json` and every site the new optional `pinFiles` config key lists,
  asks upstream `main` with one `git ls-remote`, and prints one line:
  `promise pin: 1.29.0 (fbb96c4), upstream 1.31.0 (f7caec2), 2 releases behind`, or
  `promise pin: up to date (1.31.0)`. `--json` gives the same as fields.
  - It changes no file.
  - It exits 0 when behind, up to date or offline ("upstream not reachable, not
    checked"). It exits 1 when two pin sites name different commits, or a configured
    site holds no sha. `--strict` also exits 1 when behind.
  - Each network call times out after 5 seconds. Git runs with no credential helper and
    no prompt, and a URL with a token in it is refused.
  - A second line warns when the promise section in `CLAUDE.md` or `AGENTS.md` was not
    written by the pinned release's template. Agents read that section, so a repository
    pinned to a new release with an earlier section still runs the earlier rules.
- **`/promise pr`** runs it, and when the pin is behind puts the line in Proof as
  `Not checked:`: the change was judged at the pinned release.
- **`/promise upgrade`**, a new mode, does the move as a pull request of its own:
  every pin site to upstream's commit (`pin_move.py`), `adopt` so the section matches,
  the repository's checks, `pin_check.py` again, then the pull request. A person
  merges it. It prints the step each machine runs after the merge:
  `claude plugin marketplace update promise`, then
  `claude plugin update promise@promise --scope project`. `adopt` still never moves a
  pin.

## 1.31.1

A follow-up sweep of 1.28–1.31.

- **`adopt` refreshes an old block.** An adopted project whose promise section is from
  an older release (`claudeMd.sectionCurrent` false) now gets the block refreshed on one
  yes, instead of "already adopted". Text adopt did not write is kept.
- **An existing config keeps its keys.** `adopt` never rewrites a config, so a project
  adopted before 1.28 has no `decisionPolicy` or `minSkillVersion`. `adopt` now says
  under Needs you which keys to add by hand (a one-command upgrade is).
- **Tiny says its one question.** In a session that has not yet said yes to
  configured commands, that yes is tiny's one question. A fix asks it first, because
  its failing test must run before the fix; a copy or styling change asks it with the
  result. Tests that did not run are never reported as passing. The `tiny-copy` eval no longer grants it in its prompt, so the eval measures
  this.
- **A single broken promise is tiny work:** reproduce it, then fix it. `intake` is for
  several items, or when the person asks to file. `intake` no longer stops for approval
  on a KEEPS item, which files nothing.
- **Smaller fixes:**
  - architecture's orient schema says `mapUsable` is a boolean, false beside a sibling
    map;
  - `retro` reads the version from orient's `skillVersion`;
  - `sizing.md` names every mode that reads it.

## 1.31.0

The seven issues filed after 1.28–1.30 reached a project with a large map.

- **`adopt` keeps text it did not write**. A section inside the promise markers
  whose heading the template never wrote moves, unchanged, to just above the block, and
  is reported as `movedAboveBlock`. Text it cannot tell apart is refused with exit 2 and
  its line numbers, never deleted. This covers setext headings, fences and CRLF files.
- **The skill knows its version**. `skills/promise/VERSION` holds it, and a test
  keeps it equal to the plugin's. `orient.py` reports `skillVersion`, and the Phase 0
  line names it. `adopt` writes `minSkillVersion`, and an older copy of the skill warns
  with both versions and how to update. A copy synced from the old skills repository is
  frozen at 1.3.0.
- **Legacy docs can take the repo's policy on one yes**.
  `decisions.py policy --open --to <policy> --by <name>` stamps every open doc with no
  policy line and writes a §8 row for each. `orient.py` counts them as
  `legacyPolicyDocs`, and `revise` and `adopt` put the count under Needs you. A missing
  line still reads as `spec`.
- **The skill decides whether to file; the recipe decides how**. "How big a row
  is" moved from the starter recipe into `references/sizing.md`, which every mode reads,
  so a project's own recipe no longer overrides the sizing.
- **A tiny fix cites its test now only on a `proven` row**. The proof had a hole
  there. On any other row, the test declares the row and `reconcile` cites it later,
  listed under Decided for you.
- **Size and stops are recorded, and a tiny claim is checked**.
  - `session_report.py --record` keeps each run's size, mode, stops by kind and closing
    counts, and `retro` sums them.
  - `pr` writes a `Size:` line, which the lint checks.
  - `changed_rows.py --size tiny` (or `--body`) fails when the diff touches a row's
    scenarios, a doc's §0 or §6, a migration or schema, or a `protectedPaths` entry.
    `protectedPaths` is read at the merge base.
  - The Action's `tiny-check` input runs the check in CI, and `promise-ci.yml` turns it
    on.
- **A sibling repository's map, read-only**. With `"map": false` and a `sibling`
  object in the config, `adapter.py find` and `row` run in the sibling checkout, and
  nothing writes there. `mapUsable` stays false, so no mode writes to a map it does not
  own. `intake`, `issue` and `pr` name the sibling's rows and say under Needs you which
  row needs the change.

## 1.30.0

Behaviour evals for the skill itself (`evals/`, run with `claude plugin eval`).

- **Eight cases**, each run in a fresh `claude -p` session inside a small chat app that
  `evals/_fixture/make-project.sh` builds and adopts with the plugin's own scripts. The
  cases cover tiny asks, trap asks that look tiny but are risky (tax, renaming a
  database column), a small extension, a new feature, a risky feature and a defect.
  They are split into train and test for hill-climbing.
- **`bash evals/run.sh`** runs them on the credential Claude Code is signed in with. On
  a claude.ai subscription, runs count against the plan's usage. `evals/README.md`
  says how to run them, how to change promise against them without overfitting, and
  how to add a case.
- **`tests/test_evals.py`** checks each case's shape and builds both fixtures.

## 1.29.0

Capabilities are cut at the size of a job, not a detail.

- **A row is one job with its own "so that"** (the starter recipe's § How big a row
  is). The job's rules, limits, permissions, undo and error paths are its scenarios,
  and a change with no release-note line gets no row and no scenario.
- **`arm` groups by the job, not the §0 rule:** one row per "so that". A doc with one
  outcome and at most five acceptance rows files one row, whatever its rule count.
  The framework's F7 and architecture § 8 say the same.
- **`intake`:**
  - EXTEND when the item serves the row's "so that", so a limit, an error path or a
    permission is a scenario, never a row of its own.
  - A new KEEPS relation files nothing for a refactor, config, or a speed or cost fix
    no caller sees.
- **`issue` / `pr`:** a guard test is cited on the scenario it guards and adds none. A
  fifth onboarding step is EXTEND.
- **`new`** runs the release-note test before the capability hunt: no line means no
  doc; a line an existing doc holds means `revise`.
- **`backfill`** folds tests that differ only in their data into one scenario. An
  untested route still gets a row of its own, so it never hides inside a tested one.
- **A bigger row needs more tests, never fewer.** `proven` needs every scenario's own
  test at its altitude, watched to fail. A case in a scenario's `given` that behaves
  differently needs its own test. A job over five scenarios continues in a chain.
- **A promised `Then` the product breaks is DEFECT, never KEEPS:** its fix starts with
  a failing test for that scenario.
- **The example map files the channel-muting doc as one row.** `CAP-1` has three
  scenarios, and `CAP-2`, the per-member rule as a row of its own, is retired.

## 1.28.0

Promise does the least the ask needs, and asks much less along the way.

- **Size the ask first** (SKILL.md, `references/sizing.md`). Before the mode, write the
  one line a release note would carry:
  - **tiny** (no line: wording, styling, a refactor, config, a fix to what a row
    already promises): no doc, no row, no question. Build it and run the tests.
  - **small** (a line about something a doc or row holds): `revise` or `intake` into it.
  - **feature** (a new job): `new`, drafted from the user's own words.
  - **risky** (a protected category, even as a rename or a bump): `new`, at `spec`.

  `orient.py` flags `risky` asks (a protected category's words) as `suggestedSize`,
  with `sizeSignals`. It never says tiny: that call is the agent's. The CLAUDE.md block
  leads with the rule, so refresh it with `/promise adopt`.
- **The decision policy is set once for the repo:** the config's `decisionPolicy`,
  `auto` when unset, and `adopt` writes it. `orient.py` reports it; `new` takes it and
  never asks. A legacy doc still behaves as `spec` until a human moves it.
- **Batch, don't interrupt.** Take the Recommended option on anything reversible, keep
  working, and end with one message: **Needs you**, **Decided for you** (with undo),
  **Not checked**. Work stops mid-flow for only four things:
  - the first configured command of a session;
  - deleting files, or committing on the default branch;
  - each mode's one checkpoint: `new`'s one question turn, `intake`'s approval table,
    `arm`'s red gate, `merge`'s deletions;
  - an ask with no outcome.
- **Fewer stops in the modes:**
  - `new` takes what the ask already says and asks for the rest in one turn. It no
    longer echoes typed rules or waits on the owner or the invariants skill, and
    writes a thin draft without asking. Where docs live joins that one turn.
  - `intake` stops once, before Apply, and offers a defect's fix in its closing message.
  - `arm` groups rows by the rule and shows the grouping at the red gate, takes the
    test command from `testRunners`, and asks for one yes at the gate.
  - `reconcile` moves a verdict by the rule.
  - Research agents go out without asking.
  - `adopt` asks for one yes.
- **Fixes:**
  - The agent's own decisions no longer turn a sheet of one or two plain questions
    into a page. They are listed after the questions (`--prompt-json` `decided`).
  - A defect filed with no map is a non-blocking §9 note, so it no longer turns an
    agreed doc's lint and CI red.

## 1.27.0

Every row id starts `CAP-`, and the `Scenarios:` line no longer holds a count that
parallel branches both change.

- **Row ids from a work item take the `CAP-` prefix:** `CAP-i1890a`, `CAP-p2091a`,
  `CAP-ENG-421a`, beside the counter's `CAP-12`. `grep -rn 'CAP-'` now finds every row,
  and no everyday word (`GPT-4o`, `i18n`, `i3wm`) can read as one. The guesswork 1.25
  added to tell a bare `i1890a` from such words is gone from `lint_github_text.py`,
  `orient.py` and `decisions.py`, and ids no longer skip numeronym letters.
- **The starter `rowIdPattern`** is now `^CAP-(\d+|[ip]\d+[a-z]{1,2}|[A-Z][A-Z0-9]+-\d+[a-z]{1,2})$`.
  A project on 1.25 copies it in, and copies `templates/starter-map/capability_find.py`
  over its reader. `--check` names any row 1.25 wrote without the prefix: rename it
  `CAP-<id>` in `map.json` (rows, `parent` and `retired` too), in its doc's §6 and in
  its tests. Until then, its letters
  stay taken (`--next-id --from issue:1890` beside `i1890a` gives `CAP-i1890b`). A project
  still on 1.25's pattern gets an `orient.py` warning, and only `CAP-` ids count as rows in
  its text, so `GPT-4o` never does.
- **A count-free `Scenarios:` line:** `**Scenarios:** the acceptance rows in §6 and the
  worked examples in §3.` It counts nothing, so it never goes stale and never conflicts
  when two branches add rows to one doc. The template, `render_outcome.py` and the
  examples write it. `SCENARIOS_COUNT` still checks a counted line, so older docs pass
  as they are. `outcome_rows.py --count-free` swaps a counted line for the count-free
  one, and `--write-counts` leaves the count-free line alone.

## 1.26.0

A decision policy per doc: a planner answers every question, a prototyper only the ones
that are hard to undo.

- **`Decision policy:`**, a new header line: `prototype`, `auto` or `spec`. The human
  picks it. `new` asks once, first, with `auto` as Recommended; `render_outcome.py
  --policy` writes it. A doc with no line is a legacy doc and behaves as `spec`, as
  before. `Depth: thin` keeps its own meaning.
- **Protected categories are asked at every policy:** data retention, destructive
  migrations, money, legal text and consent, security and access, public or persisted
  contracts, irreversible external effects, regulated behaviour, third-party
  commitments. The agent decides alone only when the impact is local, no protected
  category or contract is touched, there is a concrete rollback, and reversal stays
  cheap. Doubt means ask.
- **An agent decision is a §8 row** with Owner `agent` and six fields: category,
  reason, rollback, reversible-until, a concrete review trigger and a state
  (`provisional`, or `asked Qn`). No new section.
- **The decision sheet shows them as "Decided for you":** read-only, outside the round,
  never picked by `all recommended`. Its one action, **Ask me instead**, becomes a new
  BLOCKING §9 question, and the row says `asked Qn`. A sheet with no agent rows is
  byte for byte what it was.
- **`decisions.py promote`, `policy` and `recheck`:** put named decisions to the human;
  write the policy the human picked (tighter surfaces agent decisions as questions,
  looser answers none); list the decisions due for a second look at `arm`.
- **New lint rules:** `DECISION_POLICY`, `AGENT_DECISION_FIELDS`,
  `AGENT_DECISION_PROTECTED`, `AGENT_DECISION_UNRATIFIED` (errors) and
  `AGENT_DECISION_WORDS` (a warning: a local decision that uses a protected word such
  as `API` or `retention`).
- **`orient.py`** reports each doc's `decisionPolicy`.
- **`examples/key-tabs.md`:** a doc under `auto`, with three agent decisions and one
  protected decision asked as a question.

## 1.25.0

Row ids come from the work they came from, so parallel branches cannot take the same
one.

- **`capability_find.py --next-id --from issue:<n>`** (also `pr:<n>`, and
  `linear:ENG-421`, which gives `ENG-421a`: Linear's own key, because it numbers each team
  apart)
  prints `i<n>a`, then `i<n>b` and on to `i<n>aa`. It gives the letters after the last ones a
  row, retired id or other branch has used for that item, so a deleted row's id never
  comes back. GitHub and Linear hand out each
  number once, so rows of different issues never clash, pushed or not. Two branches for
  the same issue should still push soon; `--check` catches a clash at the merge.
- **`adapter.py next-id --from ITEM`** passes the item on to the project's `map.nextId`.
  A map whose `rowIdPattern` has no room for the item's id gets its counter id instead, with a
  note, so `arm` keeps working on a project set up before 1.25.
  So does a reader from before 1.25 that does not know `--from`.
- **The counter form stays.** Old `CAP-<n>` rows keep their ids, and a map with no
  tracker still takes `--next-id` alone.
- **`rowIdPattern`**: the starter map's now takes both forms and leaves out numeronyms
  (`i18n`, `p2p`, `i2c`), so they are never read as rows, and letters that would make
  one are skipped. An id has at most two letters after its number, which allows 702
  rows per item.
- **Everyday words that look like ids** (`GPT-4o`, `COVID-19s`, `mid-90s`):
  - `lint_github_text.py` counts such a word in issue and pull request text as a row id
    only when the map has that row or it is an item's next one (`i1890b` beside
    `i1890a`), so `i3wm` stays a word beside `i3a`, and a counter id only in a family the map's ids use, such as `CAP-`;
  - `orient.py` reads them the same way, and ignores case only for a counter id (`cap-3`);
  - `decisions.py sheet` flags a bare row id such as `i1890a` only when the map holds
    that id, so `p99th` or `i3wm` in a decision is left alone.

  A map
  started earlier has `^CAP-\d+$`: widen it, and copy the new
  `templates/starter-map/capability_find.py` over its reader.
- **Recipe, `modes/arm.md`, `modes/backfill.md` and `quickstart.md`:** take the id from
  the issue the work comes from. A backfill numbers its rows under its own issue or pull
  request.

## 1.24.0

Row ids and merges are safe across parallel branches.

- **`capability_find.py --next-id`** (the starter map's reader) skips every row number
  another branch holds, local or remote, and says which it skipped. `--fetch`
  refreshes the remotes first.
- **`capability_find.py --check` on a merge commit** fails when the merge lost a row
  or a `leftOut` entry that either side added. Keeping one side of a `map.json`
  conflict used to pass. It also fails when both sides gave one id to two rows that
  are both still in the map.
- **`retired`**, a new top-level map list of `{"id", "reason", "date"}` entries: a row
  dropped on purpose, such as a duplicate removed in a merge. The merge check accepts it,
  and `--next-id` never gives its number out again. A `leftOut` entry is no loss once a
  row cites its test, and the check also reads every merge a branch brought in.
- **CI:** the Action can run the map's own checks (`map.checks`) as well, with the input
  `map-checks: "true"` (`check.py --map-checks`); they need no test run. It is off by
  default, so an existing workflow keeps passing. The workflow `adopt` writes
  (`templates/promise-ci.yml`) turns it on and checks out full history, so the check can
  read both sides of a pull request's merge. An older workflow adds both lines to get it.
- **`--check` during a merge:** it also runs while a merge is still in progress,
  before the merge commit, right when the recipe says to run it.
- **Recipe, `modes/arm.md`, `modes/backfill.md` and `quickstart.md`:** fetch before
  taking an id, push the new row soon after, and in a map conflict keep every side's
  rows.
- **For a project whose map was installed earlier:** copy the new
  `templates/starter-map/capability_find.py` over its own copy to get these checks.

## 1.23.1

Every ask explains itself, not only the ones on a decision sheet.

- **SKILL.md, rules that hold in every mode:** an ask says in plain words what it is
  and what the human chooses, wherever it is put: a sheet, a reply, an issue or a pull
  request. An id (`Q2`, `AT-3`, `#87`) never stands alone, even when an earlier message
  explained it. SKILL.md stays within its 150 lines.
- **The project section** (`templates/claude-md-section.md`) carries the same line, so
  a host repo's CLAUDE.md or AGENTS.md reminds every agent, with or without the skill
  loaded. The block stays within its 20 lines. A host sees `sectionCurrent: false`
  until `adopt` refreshes the section.

## 1.23.0

Promise learns from how it was used.

- **`session_report.py`** reads a Claude Code session's transcript (the project's
  newest, or the `.jsonl` files named) and prints facts, never contents:
  - the promise files read and never read;
  - each script's runs, failures and exit codes, and commands retried after a failure;
  - `signals` for the patterns promise has been seen to go wrong in: `no-skill`,
    `sheet-files-sent`, `sheet-not-published`, `hand-answers`, `rebuilt-script`,
    `repeated-command`, `script-refused`.

  `--scrub` drops commands and project paths. `--scrub-check DRAFT` lists what in a
  draft names the project: its folder and repository names, paths outside the skill,
  issue numbers, other repositories' links, and email addresses.
- **`/promise retro`** (`modes/retro.md`) turns a session into findings about promise:
  what happened, where promise was involved, why, and the fix. It drafts one issue for
  the promise repository, scrubs it until `--scrub-check` passes, and files it only on
  the human's yes.

## 1.22.0

A big backlog goes to research agents before it reaches the human.

- **`decisions.py triage --out DIR`** splits the open questions into packets of ten,
  one doc at a time, each with the prompt for a research agent.
- **Research piles.** Each agent sorts every question into `answered`, `same-as`,
  `stale` or `needs-you`, with evidence.
- **`decisions.py merge-research DIR --asks FILE`** checks the results and merges
  them into the asks file:
  - an answered or stale result needs `path:line` evidence that exists;
  - a same-as result must name another open question;
  - anything else is rejected with its reason.
- **The sheet**, for what research found:
  - one "Checked by research" group, with one "Accept all" and each card folded;
  - outside the round limit;
  - a same-as question is settled by the other's answer, written under both.
- **The next step says "research first"** when more is open than one round holds.
  `references/research.md` has the procedure.

## 1.21.0

A big backlog of decisions comes in rounds a person can finish.

- **Rounds of 12.** `decisions.py sheet` puts at most 12 items on one sheet
  (`--limit N`, `--all`). BLOCKING questions come first, each doc's together, then
  the rest in the order found. The page, chat message and summary say how many
  come in later rounds (`counts.later`), and only this round's items are checked.
- **`--asks-skeleton <path>`** writes this round's asks file to fill in: each item's
  missing fields, the doc's own words (`_doc`) and what is unclear (`_unclear`).
- **`--prompt-json`** prints the round as question-prompt batches of four, BLOCKING
  first. Each option carries its reply code, so the answers go back through
  `apply --reply`. "Other" has its own reply form (`otherReply`); for an approval it
  is the change request, so the note is kept. Options past four are listed in
  `moreOptions`.
- **The Markdown twin is written only with `--md`**, never beside the page by
  default: it is for agents, and an agent once sent it to the human. `--out` refuses
  an `.md` name.

## 1.20.2

A sheet a person answers without the doc open: no number is left for them to remember.

- **`decisions.py sheet`** names every bare section (`§2` → `§2 Outcome`) in what a
  person reads, and lists under `unclear`:
  - a question, issue, row or item number with no words beside it (`#87`, `Q4`,
    `AT-4`, `item 3`);
  - a question that holds its own recommendation;
  - a question that asks to confirm lines it does not show.

  While any are listed, it writes no page, chat message or comment, and names each
  field to fix. `references/decision-sheet.md` §4 has the rule.
- **`plain`** in the asks file puts a doc question in plain words on the card. The
  doc's own words sit behind **Dig deeper**, and the answer still goes under the
  doc's question.
- **The card stays short.** `unclear` also lists:
  - a question over 35 words, or a `why` over 60;
  - a file path on the card (it belongs in `evidence`);
  - a numbered name of the product (mode 3, tier 2) with no meaning.
- **Help for the product's words.** `sheet` reads the terms from the configured map's
  `glossary`, the list issues and pull requests use, so nothing new is kept by hand.
  On the page, a term's first use on each card is underlined, and a tap opens its
  meaning; chat and the Markdown twin list the terms under the intro. The asks
  file's `words` fill a gap, with a warning to add the word to the glossary.
- **`examples/decisions/`**: the decision sheet made from `asks.json`, so a reader can
  see it before running anything: the page, the chat message, the GitHub comment, the
  Markdown twin, and screenshots on a desktop (light) and a phone (dark). The README
  shows it under "Answer the decisions in one place". `tests/test_examples.py` fails
  when a rendered file falls behind the script.

## 1.20.1

A cloud session with no skill loaded sent the human the sheet's `.md` files instead
of an Artifact: the only line it read said "`decisions.py sheet`" and nothing about
where the sheet goes. The rule now sits where such an agent looks.

- **The promise section** (CLAUDE.md or AGENTS.md) says decisions go on the surface
  the sheet names, in Claude an Artifact with `db`, never a chat list or the sheet's
  files; and that a session with no `promise` skill loaded reads `SKILL.md` and
  `references/quickstart.md` before acting. `adopt.py` refreshes the section; orient
  warns until it does.
- **`decisions.py sheet`** ends its summary with the next step for the sheet's surface
  (the `next` key with `--json`), and `sheet -h` says the same.
- **`references/decision-sheet.md`**: the top-level `surface` decides, not an item's;
  size never changes the surface; the sheet's files are for agents only.

## 1.20.0

A decision sheet a person answers from a phone, in any chat, and any agent can apply.

- **`decisions.py sheet --chat <file>`**: the sheet as one message: numbered items,
  lettered choices, the Recommended one named, and one line on how to reply
  (`all recommended`, `1a 3c`, a note after a dash, own words as `2: <words>`).
- **`--comment <file>`**: the same message for a GitHub issue or pull request, the full
  detail folded under it, and the sheet's data in an HTML comment, so whichever agent
  reads the thread can apply the reply with no local file.
- **`apply --reply <file> --sheet <comment or JSON>`**: reads the short reply against
  that sheet and writes each answer under its question in §9; a reply it cannot read
  is refused with every reason. The output lists what is still unanswered.
- **`--only <id>,<id>`**: a sheet of just the items asked for.
- **`run` in the config**: how the project runs promise's scripts (a pinned wrapper).
  `adopt --run <cmd>` writes it, the promise section names it, and `orient.py` reports
  it, so an agent on another host finds the scripts instead of rebuilding them.
- **Guidance**: `references/decision-sheet.md` and `quickstart.md` say to send the chat
  message as the message, post the comment to the issue, never attach the sheet's files,
  and apply the reply yourself, then say what was written.

## 1.19.1

The map report stops saying "proven" for what it cannot see, and the backfill
verifier has a hand-off.

- **`map_report.py`**: a row whose every lane is green reads `LANE-GREEN`, and the
  headline counts `lane-green`, since the report joins tests by lane, not by
  scenario. A scenario reads `✓ lane green`, and says when its lane holds fewer
  passing tests than scenarios, so one test may stand for several. The JSON keeps
  its values, so `check.py` is unchanged.
- **The backfill verifier**: `references/quickstart.md` gives the writer's scratch
  file shape, `backfill-<area>.json`, and the verifier's prompt, with the human as the
  verifier on a host that cannot start a second agent. `modes/backfill.md` points
  there.

## 1.19.0

An agent on any host can learn promise from two files, and keep its section current.

- **`references/quickstart.md`**: the words (§0, status, map, row, altitude, lane,
  verdict, bridge, red gate, backfill), the commands in order for a new project and
  for an existing repo, the decision loop (`sheet`, a surface, `apply`), and what to do
  on a host where the skill never loads (Cursor cloud agents, chat bots). `SKILL.md` and
  the CLAUDE.md / AGENTS.md block point at it.
- **A current section**: `adopt.py` stamps the promise section's begin marker with the
  template's hash, and `orient.py` reports `claudeMd.sectionCurrent` and warns when the
  section was written from an older template, naming `adopt` as the refresh. The block
  now says answers go back through `decisions.py apply`.
- **The lint is never silent**: a last line counts docs, errors and warnings, and a
  warning ends in ` (warning)`. `--no-summary` leaves the count out; `check.py` uses it.
- **The recipe** gives the scenario id format (`CAP-<n>.<m>`) and says what
  `${CLAUDE_SKILL_DIR}` means outside Claude Code. `capability_find.py -h` keeps its
  usage lines apart.

## 1.18.1

`arm` says where a new project's stubs go and what §6 records of the red run.

- **Stubs**: a stub is only a signature that throws. A new stub module rides in the
  red-gate commit with the tests it serves, and a test failing inside a stub is a
  valid red gate. A test that fails to import or compile is broken, not red.
- **One `Red run:` line**: arm writes `Red run: <command> — <n> failing, <m> passing
  at <sha> on <YYYY-MM-DD>` under the §6 table (under the snapshot line, with a map),
  in place of pasted output. It is the one line §6 takes after the snapshot; the
  framework says so. An unwitnessed run says `Red run: not witnessed here; prove with
  <command>`.

## 1.18.0

A new project with no code gets a test command and a test run the map can join.

- **`adopt.py`** always writes `commands` with all three keys, the undetected ones as
  `null`, as `references/config.md` says, so a new project sees where its test
  command goes. `orient.py` warns when a `null` key now has a detected command.
- **`arm`**: when `commands.test` is `null`, propose one from orient's `testRunners`,
  with the `map.junit` path its JUnit route writes, and write both on the user's yes.
- **`scripts/junit_unittest.py`**: runs a stdlib unittest suite and writes JUnit XML,
  each case with its file, class and method, so `map_report.py` joins a citation by
  `file::method` or `file::Class::method`. `orient.py` finds a unittest suite and
  names this route; pytest wins when the project uses it.

## 1.17.0

A moved doc's §0 has one written form, and the lint holds it to that form.

- **The pending line**: a legacy doc moved into an outcome doc opens §0 with
  `**Pending verbatim confirmation:** <n> quotes from <path> at <sha>. A human
  confirms by deleting this line.` Each quote reads `"<words>" (source: <path>:<line>
  @ <sha>)`. `modes/backfill.md` says so, and `examples/backfill-moved.md` shows it.
- **Three lint rules past `draft`**: `PENDING_ON_AGREED` (§0 still pending),
  `OPEN_ON_AGREED` (the outcome line or how-we'll-know still reads `Open — Qn`), and
  `BLOCKING_OPEN_ON_AGREED` (a BLOCKING §9 question with no answer). Each is an
  error. The lint and `decisions.py` now read §9 with one parser.

## 1.16.0

A decision sheet a chat with no HTML viewer can show.

- **`decisions.py sheet --out FILE.html`** also writes `FILE.md`: the same items in
  plain Markdown, grouped by doc, Recommended first, with the why, what waits and what
  happens with no answer on each item and the rest under "More, if you need it". The
  human replies one line per item, `<id>: <answer>`. `--md <path>` names the file, or
  writes it without the page.
- **The one-line summary** lists the first five BLOCKING items, so an agent can paste
  them into a chat as they are.
- **`references/decision-sheet.md`**: a chat that shows only text gets the Markdown
  twin, never a link to an HTML file it cannot open.

## 1.15.2

- **`decisions.py`**: a blank line between a §9 question and its `Answer` line no
  longer hides the answer. A question now runs until the next question or the end of
  §9: a blank line ends its text, and a later answer line still counts. `apply` puts a
  new answer under the last one, past the blank line.

## 1.15.1

- **`decisions.py`**: an answer line in Markdown bold or italic counts as answered
  (`**Answer (YYYY-MM-DD, name):** …`, `_Answered YYYY-MM-DD_ …`), so `sheet` no longer
  reopens a question a person answered by hand. `apply` still writes the bare form.
- **The CLAUDE.md / AGENTS.md block** points agents at the decision sheet: open §9
  questions go to the human through `decisions.py sheet`, never as a list in chat.

## 1.15.0

`find` finds the right row, and the map learns from its misses.

- **BM25 `find`** in the starter reader (`templates/starter-map/capability_find.py`,
  and `examples/minimap/`, which runs the same bytes): stopwords never count, a small
  stemmer lets "muting" meet "mute", a rare word outranks a common one, and two query
  words side by side in a row, in the query's order, add a small bonus. A row the
  query names by id or alias still comes first. Each hit carries a `why` line: the
  words it ranked on.
- **Row `title`**: optional, one line, in the words a person asks with. `find` ranks
  on it; `--check` warns about a row with none and never fails on that.
- **`--eval [FIXTURE]`**: top 1 and top 5 over `find-eval.json`, the titles of real
  pull requests and issues linked to one row. A case whose text is already one of a
  row's asks is left out and counted. `examples/minimap/find-eval.json` is the
  example; BM25 beats the substring scorer on it.
- **Row `asks`, and `capability_find.py learn`**: at most five `{text, source, date}`
  per row, the words a person, an issue or a pull request used when `find` missed
  the row. They count as the row's text, and a query that repeats one puts the row
  first. `learn` adds nothing when the row already ranks first, refuses an email
  address or a handle, skips a near-duplicate, drops the oldest ask of a full row,
  and keeps the ask only when the row then ranks in the top three. `--check`
  validates asks and warns about an ask conflict (an ask that now finds another row
  first).
- **`map.learn` and `adapter.py learn`**: the optional command that runs it, with the
  ask passed as a file. `start_map.py` sets it for the starter map. `intake` and
  `issue` run it after a match lands on a row `find` did not rank first; the
  CLAUDE.md block's lookup rule points there.
- **Row `refs`, and `capability_find.py refs sync`**: a row may hold
  `{repo, kind: issue|pr, number}` refs, identifiers only, the repo named in full.
  `refs sync --input <file>` reads merged pull requests (the caller fetches them) and
  adds a ref to every row a promise block names as new or changed under
  "Capabilities", plus one for each issue its "Why" closes. A pull request that names
  one row adds its title to the eval fixture. `map.refsSync` and `adapter.py
  refs-sync` run it; `reconcile` does, so no CI job needs write access.
- **`capability_find.py --code <id>`**: the local files a row's cited tests import,
  Python and JS/TS followed one step, read from the project root. `map.code` and
  `adapter.py code <id>` run it; `issue` and `new` read those files before a wide code
  search.

## 1.14.0

Decisions a run leaves for the human go on the best surface the agent has, never
as a list at the end of a chat reply.

- **`decisions.py sheet`**: collects the unanswered §9 questions (the docs named, or
  every doc under docsHome) and an asks file the agent writes: options with the slate
  annotations, detail, a diff or command, an image, links, and decisions outside the
  docs (approve, a value, a to-do). The question text, owner and BLOCKING flag come
  from the doc only. Each item carries a brief so it can be answered cold: why it is
  asked, what it blocks, what happens with no answer, an example, and `path:line`
  evidence; each option says what happens next. A rich sheet warns about an item or
  option missing them. The page shows each doc's §0 above its questions, verbatim.
  Each card shows only what a decision needs (why, what waits, what happens with no
  answer, each option's reason). The example, detail and evidence sit behind **Dig
  deeper**, each option's trade-offs behind its own fold, and §0's rules and signal
  behind its outcome line. **Show all details**, **Hide all details** and **Hide
  answered** sit in the header, and the page remembers which folds were open. It prints a `surface` hint (`ask-questions` for at most four
  plain choices, else `rich`) and renders the page.
- **`templates/decision-sheet.html`**: the page, published as a Claude Artifact with
  the `db` capability. Recommended first, "None of these — here's mine" second,
  Accept all Recommended per doc, progress and blocking counts, light and dark,
  phone width. **Save answers for Claude** writes `answers/latest`; **Copy answers**
  works on any host.
- **`decisions.py apply`**: writes each answer under its question in §9 as
  `Answer (<date>, <by>): <text>`, once, keeping line endings and a BOM. §0 and the
  Status line are never touched. Answers that name no doc question come back under
  `forAgent`.
- **`references/decision-sheet.md`**: when to use the rich sheet and when the
  question prompt, how answers come back from each, and the asks file.
  `SKILL.md` points every close-out at it.

## 1.13.0

One instruction file for every agent: the promise section may live in `AGENTS.md`.

- **`orient.py`**: the project is adopted when the section is in `CLAUDE.md`, or in
  the root `AGENTS.md` that `CLAUDE.md` imports on a line of its own (`@AGENTS.md`),
  or in `AGENTS.md` when there is no `CLAUDE.md`. `claudeMd.sectionPath` names the
  file that holds it. A section in both `CLAUDE.md` and the `AGENTS.md` it imports is
  a warning, because Claude reads it twice.
- **`adopt.py`**: in those cases the section is written and refreshed in `AGENTS.md`,
  and `CLAUDE.md` is not touched. A project with an `AGENTS.md` that `CLAUDE.md` does
  not import still gets the section in `CLAUDE.md`, as before.
- **`modes/adopt.md`**: recommends the section in `AGENTS.md` and a `CLAUDE.md` that
  imports it, and says how to move a section that is in `CLAUDE.md` now.

## 1.12.0

The first screen after its first use on a batch of real issues: fewer false
warnings, and the word counts in view while a writer trims.

- **`lint_github_text.py`**: an area's name counts as a defined word, so an area
  explains its own word in the rest of the body. A term covers the glossary words it
  starts with in the singular or the plural ("Modules" covers "module"). Code spans,
  paths, URLs and file names are not read for terms (`TERM_UNDEFINED`).
- **Areas past five**: the five that matter most stay bullets; the rest go on one
  `Also: **Name**, **Name**.` line. Its names count for `AREA_UNKNOWN` and
  `AREA_MISSING`, not for the five, and explain no word (no sentence of their own).
  An area whose sentence says it is "not yet in the
  map" is not `AREA_UNKNOWN`.
- **Word counts**: `--json` gives `counts`, the words the first screen, the block and
  "What changes for people" show against their budgets; `--counts` prints them as one
  last line.
- **Guidance**: one form for a ticked decision, with the owner's own words in
  `<details>`; a "Same as" answer ticks both issues; an answered DECISION takes the
  relation its answer leads to; a refresh's `Read:` line; the issue mode reads the
  comments on each issue its block names; members of a set nest under their word.

## 1.11.1

Text written before the first screen still passes the lint.

- **`lint_github_text.py`**: no first screen is a warning, not an error (`NO_INTRO`):
  an issue with no `promise:intro` block, or a pull request block with neither "Where
  this is" nor "Words". The other first-screen rules do not run on it. A first screen
  that is there is still checked in full: intro markers repeated or out of order, or
  one of the two sections alone, are errors. The `issue` and `pr` modes always write
  it.
- **A map's lists**: `areas` or `glossary` that is not a list no longer crashes the
  starter reader (it reads as empty; `--check` names it) or the lint (a usage error,
  exit 2). `NO_INTRO` names `/promise issue`, the mode that writes the intro.

## 1.11.0

A first screen for a reader who comes back to an issue or a pull request after days
away, from other work.

- **First screen**: an issue opens with a `<!-- promise:intro -->` block above the
  asker's words, and a pull request's block opens with the same two sections. "Where
  this is" names the parts of the product, one plain sentence each, then "Needed from
  you:" says what the reader must do. "Words" explains the product's own words, with
  variants nested under their word. `references/first-screen.md` gives the shape, the
  rules and a 180-word budget of its own. The issue and pull request templates carry
  the empty sections.
- **Areas and glossary in the map**: two optional top-level lists. `areas` names the
  parts of the product (`id`, `name`, `plain`, an optional `doc`), and a row's
  optional `area` names one; `glossary` explains the product's words (`term`,
  `plain`, `aliases`). The starter reader checks both (`--check`), prints them
  (`--areas`, `--area <id>`, `--glossary`) and matches an area's name in a query; a
  row with no area is allowed, so a map can take its areas a few rows at a time.
- **`changed_rows.py`**: each row carries its `area`; the report's `areas` lists the
  areas of the rows the change moved or touched, with their names; the Markdown block
  names them. A change to a row's `area` alone is `relabelled`, not a change to its
  promise; `areasRelabelled` groups those rows by their new area, and the Markdown
  counts more than 12 of them by area instead of listing each. Rows sort by number
  (CAP-2 before CAP-10).
- **`lint_github_text.py`**: `NO_INTRO` and `INTRO_FIRST` for an issue; `AREAS`,
  `NEEDED` and `WORDS` for the first screen's shape, and code words in an area's
  sentence; with the map's lists, `AREA_UNKNOWN`, `AREA_MISSING` (a named or moved
  row whose area is not listed) and `TERM_UNDEFINED` (a glossary word the reader meets,
  in an issue anywhere in its body, that "Words" does not explain; an area's own name
  in "Where this is" does not count, since its sentence explains it). A relabelled row
  left unnamed is a warning.
- **New rows get an area**: the starter recipe's lockstep appends a row with its
  `area` when the map has `areas`; `backfill`'s area table becomes the map's `areas`,
  and each backfilled row carries its `area`.
- **Issue block**: its last `<details>` explains a row and each relation used, beside
  the verdicts ("What the map words mean"). The reference points at the lint's own
  rule list in place of a copy of it.

## 1.10.0

What twelve real issues and one pull request taught the `issue` and `pr` modes.

- **Relations**: `KEEPS` for work a caller does not see (a refactor, a cost fix):
  build it and name the rows whose scenarios must still hold. A kept row whose tests
  do not run the changed code proves nothing, so the route adds that test.
- **Issue routes**: EXTEND revises the row's doc, or goes through `intake` when the
  row has none. NEW-ROW with one promise goes through `intake`; a capability with
  rules of its own goes through `new`, or revises the doc whose outcome it serves.
  Work can go before its row when the row waits on a decision: its guard tests go in
  the map's `leftOut` list with the decision as the reason.
- **Issue block**: a `Read:` line first; one item per ask, grouped by relation past
  six; "Each ask in full" and "Later decisions" in `<details>`; forms for an answered
  decision, a question another doc or issue already asks, a row another issue files,
  and a decision with no recommendation. A row named by two docs belongs to the one
  whose §6 holds it. The route names the learnings that change a step. Plain words
  name a person by name or role, never by a guessed pronoun.
- **`pr` mode**: a project with no map says so in one line, then names the parts of
  the product the change moves, each with its test, not every file.
- **`changed_rows.py`**: renames, bare file names, a docs home in a subfolder, the
  `leftOut` entries added or removed, prose files (notes, learnings, readmes) listed
  apart from code, and a Markdown block capped to fit a pull request body. The
  project is `--cwd`, so one in a subfolder of its repository works. `--link` prints
  a row's outcome docs when the row has no doc.
- **`lint_github_text.py`**: headings do not count toward the word budget; a verdict
  after a scenario id (`[CAP-4](…) S2 (proven)`) and every row and verdict in
  `<details>` are checked against the map; `READ_LINE` warns when the `Read:` line is
  missing; a ticked decision needs no owner.
- **Routing**: a first word of `PR` or `Issue` names the mode only before a number, a
  link or a plain pointer, never beside "merged", "landed" or "fixed" ("PR #12
  merged, update the map" stays `reconcile`). A product feature around the phrase ("a
  button that lets users file issues"), or a named doc beside a weak phrase, is
  ambiguous and the router asks.

## 1.9.1

Fixes from a pre-launch review of 1.8.0 and 1.9.0.

- `.pre-commit-hooks.yaml` pins the current release; a packaging test keeps its
  `rev` equal to the plugin version.
- `check.py` and `references/config.md` said the gate step is skipped with no map;
  it fails, as the README and the code say. Both now say so.
- `check.py` warns on every run when the docs folder is not a folder, since lint,
  §0 and the gate all skip on it: a misspelt folder no longer passes in silence.
- `map_report.py --config` no longer crashes on a config whose `map` is not an
  object; it uses the default lanes.
- Test names and paths from a private project are neutral now, and the leak check
  covers `tests/`, `examples/`, `hooks/`, the README and this file.
- The Action's description names the red-gate check; the README's "What's in the
  box" lists `install_skill.py`, `hooks/`, `action.yml` and `examples/proofmap/`.

## 1.9.0

Issues and pull requests a person can review. A reviewer reads a change from the issue,
to the capabilities it moved, to the code. Two modes and two scripts give that path.

- **`issue` mode** (`modes/issue.md`): reads an issue, splits it into asks, matches
  each against the map with `intake`'s match step, and writes a block below the
  asker's words: each ask's relation and rows (linked, with verdicts), the gap in the
  code today with `file:line`, the `/promise` steps the build agent takes, and the
  decisions it waits on. It files nothing in the map.
- **`pr` mode** (`modes/pr.md`): writes the block a reviewer reads — what changes for
  people in one to three plain sentences, the issue it closes, every row the change
  moved with its verdict before and after, one to three `path:line` places to read
  first, the proof that ran — with the full row diff in `<details>`.
- **`changed_rows.py`**: the map at a change's merge base against the map at its
  head. Each row is `added`, `removed`, `changed` (story, a scenario, verdict,
  evidence, surfaces, doc) or `touched` (a test file it cites, a file it names, or
  its outcome doc changed). Also the outcome docs changed, with status and whether §0
  moved, and the changed files no row names. `--json`, `--markdown`, and `--link ID`
  for a row's permalink.
- **`lint_github_text.py`**: checks the promise block of an issue or a pull request —
  sections, a line budget outside `<details>`, sentence length and no code words in
  the people section (rules from ASD-STE100), a linked issue, `path:line` items, a
  relation and a route per ask, row ids against the map, and every moved row named.
- **Templates**: `templates/github/ISSUE_TEMPLATE/capability.md` and
  `templates/github/pull_request_template.md`, each with an empty promise block.
  `adopt` offers them, and names the `map.issueTracker` object to add.
- **Routing**: `issue` and `pr` phrases outrank every doc mode ("review these issues"
  reads as `issue`, "write the PR description for #12" as `pr`); `orient.py` knows
  both mode words. `references/github-text.md` holds the shape and the rules.

## 1.8.0

Backfill: fit promise to a product that already exists, and prove that every test
and every entry point has a home. Before release, a review of the rules and the
scripts found gaps; the fixes are listed below by script and by mode, each with a
test or a rule line.

- **A ninth mode, `backfill`** (`modes/backfill.md`). Three sweeps, area by area:
  every test case in a JUnit run goes to a row (or a `leftOut` entry that names that
  one test, with a reason); every entry point the code lists goes to a row, and one
  with no test gets its own `not-built` row, so untested production code is visible;
  legacy design docs move into outcome docs at `draft`, their §0 a block of verbatim
  quotes marked `pending verbatim confirmation`. A writer pass is always checked by
  a different verifier. Backfilled rows carry `origin: backfill` and `doc: null`
  until an agreed doc bridges them, and their verdicts stop at `under-proven` until
  `reconcile` watches a kill. Framework decision F11 and a lifecycle line: a
  backfilled capability may go from `agreed` to `shipped`, typed by a human, with no
  red gate, once every §6 line links a backfilled row and every such row is proven.
- **`map_report.py`**: `--orphans` and `--fail-on-orphans` (tests no row cites),
  `--surfaces FILE` and `--fail-on-unmapped` (entry points no row names, and row
  entry points the code no longer has), the map's top-level `leftOut` list, a count
  of rows with no outcome doc, and a `not-run` bucket for a lane whose suite is not
  in the run.
- **`scripts/check.py`**: what the Action checks, as one local command for projects
  that cannot run Actions, in six steps — lint, §0 against a base ref, each
  `shipped` doc that skipped the red gate, the map's own checks (`map.checks`), the
  entry-point list, and the map against a test run. `action.yml` now calls it, with
  `--no-map`.
- **Config**: `branch` (`current`, or a pattern with `{slug}`; `arm` uses it, for
  hosts that allow one branch per session), and `map.file`, `map.junit`,
  `map.surfaces` (an argv line or array) and `map.requireHomes`.
- **`orient.py`**: `docsHomeForeignDocs` and a warning when a detected docs folder
  holds no outcome docs (`adopt.py` then refuses to name it without `--docs-home`);
  `testRunners` with the flag that makes each runner write JUnit; `backfill`
  inference.
- **The starter map reader**: optional row fields `aliases` (ids from an older
  register), `surfaces` and `origin`, and `leftOut` validation.
- `arm` links a §6 line to a backfilled row, instead of filing a new one, when the
  line's `Then` and `Altitude` equal one of the row's scenarios. A linked line never
  goes red: `reconcile` proves it one scenario at a time. `adopt` offers `backfill`
  and the local check, and names the `branch` line for the user to add.
- Found by adopting promise on a real product: a pnpm monorepo whose docs folder held
  19 design docs in another shape, whose org could not run Actions, and whose tests
  wrote no JUnit.

### Review fixes, by script

- **`map_report.py`**. A lane none of whose citations matches a case, in a run that
  holds none of their files or exact titles, reads `not-run`, not `never-ran`: never
  proof, not a `--strict` failure, named once in `summary.lanesNotInRun`, and
  printed as "`<lane>` was not in this run (N citations not checked)". A run that
  records no file but holds a cited test's own title has run the lane. So has a run
  that holds a case in the folder of a cited file or a subfolder of it
  (`e2e/tests/admin/new.spec.ts`), so a lane whose every cited file was deleted
  reads `never-ran` and fails `--strict`. A run file named after a folder of the
  cited path (`e2e.xml` for `e2e/tests/`) also places a path recorded from a folder
  on that path (`tests/b.spec.ts`, or Playwright's `admin/new.spec.ts`) and a
  sibling folder under the folder it is named after (`e2e/smoke/new.spec.ts`). A
  path whose first folder is a folder of the cited path is not read from the cited
  folder, so `tests/x.test.ts` in `api.xml` or `tests.xml` leaves an `e2e/tests`
  lane `not-run`. When the cited folder is on disk, a path placed from a folder on
  the cited path, or from the project root, counts only when that file is on disk
  too, so `tests/harness.test.ts` in `bot.xml` leaves an `evals/bot/evals`
  lane `not-run`. The limit: any other run file cannot place a relative path or a
  sibling folder, and a unit run in a subfolder of the cited folder is read as that
  lane's suite (a loud `never-ran`, never a false pass). `--fail-on-skipped` (new, also on `check.py`) exits 1 when the run
  skipped a test a row cites, and lists each one; the JSON always carries
  `skippedCitations` with a run. `--strict` is unchanged: it passes a skipped
  citation on a row recorded at or below what the run shows. A citation
  homes only a test the run can place: the same file in two run files, or two cases
  with no file, is ambiguous, judged on the worst case, and homes none. A `leftOut`
  entry matches only by one exact title and its file, with a one-line reason and a
  real date; otherwise it hides nothing and carries a problem, and a stale, failing
  or broken entry fails `--fail-on-orphans`. A `<word>` run in a citation is a
  placeholder only when no case in the run has exactly that title. A nested suite
  named like a path no longer overrides the outer suite's `file` attribute. A
  leading byte-order mark on stdin is not part of the first entry point.
- **`check.py`**. The checks step runs `map.checks` as `adapter.py checks` does:
  argv, no shell, in order, stopping at the first failure. Each of orient's config
  warnings prints as `promise check: warning: …` before the steps, and the map step
  fails on a `map.requireHomes` that is not `true` or `false`. Only the `map.junit`
  paths that exist are joined, and the rest are named; the orphan gate fails, never
  passes, when there is no run to join. `--junit` is read from `--cwd`. A `map.junit`
  entry that holds shell syntax is left out. A leading byte-order mark in the
  surfaces output is dropped. A new **gate** step, after §0, runs
  `bridge_validate.py` on each `shipped` doc with no `Red gate:` line and fails on an
  error, so `SHIPPED_WITHOUT_GATE` fails the run. Before, no gate ran it, and a
  shipped doc over rows that are not built passed the lint and `check.py`. The step
  needs no test run, so `--no-map` does not skip it and the Action runs it. It
  fails with no map (`null` or `false`: no row can be a proven backfilled row, even
  when §6 carries typed `Row` cells), with an incomplete map, or with a `--config`
  that is not the project's own. The Action and the CI template say to keep the
  `pull_request` trigger, since the step runs the project's `map.row` command. With
  `"map": false` the surfaces hint names only `--surfaces-cmd`. A path on an outcome doc's `Supersedes:` line that
  still exists, and is more than one line that names the doc, prints a warning (never
  a failure); a folded doc at `superseded-by` is not warned about. `merge.md`, the
  framework and `backfill.md` now agree: `merge` and `backfill` fill that line.
- **`bridge_validate.py`**. When `map.row` prints the row as JSON with its
  scenarios, as the starter map does, a §6 line matches its row only when its
  `Then` equals one scenario's `then`, case and whitespace aside
  (`THEN_NOT_IN_MAP`), and that scenario's altitude equals its `Altitude`
  (`ALTITUDE_NOT_IN_MAP`, new). Before, the `Then` was a substring of the whole row
  text and no altitude was compared, so a perception promise could link to a
  response-altitude row. A map that prints text keeps the substring check, and
  `ROW_TEXT_ONLY` (info) names its rows. `--linking`, which `arm` runs at its own
  bridge, makes both findings errors; each JSON row carries `exact`. A §6 line with
  no `Altitude` (an older table with no such column, which the lint only warns
  about) is not compared and is not drift: one `ALTITUDE_MISSING` (info; an error
  under `--linking`) names such lines, so `--strict` passes such a doc again. A `shipped`
  doc with no `Red gate:` line whose §6 cites a row that is not `origin: backfill`
  with `verdict: proven` is `SHIPPED_WITHOUT_GATE` (error): the framework allows
  the skipped gate only then. A proven row that is not `origin: backfill` does not
  pass, and a test now shows it.
- **`adapter.py`**. A new `surfaces` op runs `map.surfaces` as argv, with no shell
  and a five-minute limit, and prints the entry points or writes them to
  `--out <file>`; blank and `#` lines are dropped and the list is trimmed and
  deduplicated; an empty list exits 1. `check.py` reads the list the same way.
- **`orient.py`**. A `branch` pattern takes only ASCII letters, digits and
  `. _ - /` around `{slug}`, with no `..`, no leading `-` and no part ending
  `.lock`; a `docsHome` or `map.junit` entry takes only letters, digits, spaces and
  `. _ - /`, with no leading `-`. Anything else warns, and the default or detection
  applies. "backfill", "retrofit" or "existing product" suggests `backfill` only
  with a map word within 40 characters ("capability map", "the map", "capability",
  "promises"); a bare "map", "row" or "test" is not one. A test word ("our tests",
  "test suite") counts only where it says the product has the tests ("with a big
  test suite", "from our tests", "it has a full test suite"), and never beside a change word, so "fix the
  existing app so all tests pass" is not backfill. Docs moved to another tool
  ("migrate the docs to Notion") are not backfill: a destination counts only when it
  names the outcome shape. Without a signal it suggests `new`, marked ambiguous, so
  the router asks. Every test,
  route, endpoint, entry point, page or screen suggests `backfill` only with a verb
  that gives it a home ("needs a row", "has a home", "belongs in the map") or "we
  have"; "log every test" alone no longer does. "the docs site" is not "the docs". A
  feature, design, plan or spec word ("plan", "spec", "write a doc", "add a", "let
  users") turns any backfill phrase into the same hint, so "plan how we migrate the
  docs site to Astro" and "add a map view to the existing product" suggest `new`.
  `testRunners` gives jest the `jest-junit` settings that make a joinable run, and
  says what node:test's own reporter leaves out. `"map": false` (new) says a project
  keeps no map, on purpose: orient reports `false` with no warning, where it used to
  warn and report `null`, so `arm` offered the starter map. `arm`, `adopt` and
  `backfill` never offer it then, `start_map.py` refuses, `check.py` skips its map
  steps with that reason, and `bridge_validate.py` names it. `null` still means no
  map yet.
- **`adopt.py`**. Any run that would name a detected docs folder holding no outcome
  doc refuses (exit 2) until `--docs-home` picks one: the dry run, the real run,
  `--no-config`, and a run that writes only the `AGENTS.md` block (`--agents-md`,
  from 1.7.0). With a config loaded, it asks for the config's `docsHome` instead.
  A `--docs-home` that a shell would misread is refused. The project's own framework
  copy is not a foreign doc.
- **The Action**. The `docs-home` input defaults to empty and is passed only when
  set, so the Action lints the folder the config names, as a local `check.py` does.
  `templates/promise-ci.yml` no longer sets it.
- **`lint_outcome.py`**. A §6 cell splits as GitHub splits it: at every pipe a
  backslash does not escape, in a code span too. A pipe written `\|` is cell text,
  and a row with too many cells says so. A code span is never a `PLACEHOLDER`:
  `` `mute <id>` `` is a command's argument, while a bare `<one line>` still is.
  `SHIPPED_NEEDS_GATE` (error): a `shipped` doc with no `Red gate:` line and a §6
  line with no `Row`, the part of the skipped-gate rule the lint can see.
  `THIN_DRAFT` now also reads the sections of a thin draft: §3–§7 each say they are
  not written yet, and §4–§7 hold nothing else. A moved legacy doc marked
  `Depth: thin` with its agent half written used to lint clean. Only a line that is
  just the marker (the sentence the thin render writes, or "Not written yet" alone)
  says a section is not written yet: any other text on the line is content, so
  "- Not written yet in full, but: a token is …" in §4 is a finding.
- **The starter map reader**. `--check` rejects a `%s` or `${x}` pattern in a
  `leftOut` test, and the recipe says an entry names one test. It also refuses a
  `<word>` outside a code span in a scenario's `given`, `when` or `then`, with the
  doc lint's own rule: §6 copies those fields word for word, and the lint reads a
  bare `<word>` there as `PLACEHOLDER`. Before, a backfilled doc had to put the word
  in backticks, and its `Then` then no longer equalled the map's, so `arm` could not
  link it. The recipe and `backfill` say so.

### Review fixes, by mode

- **`backfill`**. It runs only for an input about the whole product; a design, plan
  or spec for one thing is `new`. The entry-point list comes from
  `adapter.py surfaces --out <file>`, never a shell line. An entry point joins a row
  only when a test that row cites enters through it; otherwise it gets its own
  `not-built` row. A `leftOut` entry names one test exactly. A moved legacy doc is a
  full draft, not a thin one: its §6 takes every scenario of its rows, in row order,
  and a long §6 is expected. A moved doc that no row enters is a full draft too:
  §3–§7 come from the legacy text, and §6 is derived from §3 as proposed lines that
  join the map through `arm`. Each §0 quote cites `path:line` at a commit the
  default branch holds, now or after the merge: a squash merge drops a commit only
  a branch holds, and `git show <sha>:<path>` then fails. The verifier re-cites such
  a quote. The legacy file is deleted only on a yes; on a no it is cut to one
  pointer line that names the new doc, and the README and invariant 6 now say so
  too (they said the whole file stayed, with a line on top, which `check.py` warns
  about). A legacy register is
  deleted, or cut to one pointer line, once every id in it is an alias on a row. A
  struck row stays in the map as observed behaviour, with no doc. A lane in
  `summary.lanesNotInRun` is joined before it is judged. The hand-off says the
  report's proven is computed, not proven.
- **`arm`**. A link to a backfilled row needs an exact `Then` and the same
  altitude; anything less is a new row, and a `THEN_NOT_IN_MAP` from arm's own
  bridge is fixed before the commit. With no new line, `arm` commits the bridge
  alone and writes no status. `branch: current` has its own path, and the default
  branch comes from `git symbolic-ref` on `origin/HEAD`, else one question. The
  branch name is checked against the allowed characters and quoted in single quotes
  on the shell line. The two commits are named the red-gate commit and the doc
  commit.
- **`reconcile`**. Promotes one scenario at a time, on a test that asserts that
  scenario's own `Then`, watched dying: the computed verdict joins citations by
  lane, not by scenario. It stops when a linked line's altitude and its row's
  disagree.
- **`revise`**. Keeps the §6 lines a backfilled doc took from the map, instead of
  deriving §6 from §3 again.
- **`reconcile`, `revise`, `review`**. Each handles `ALTITUDE_NOT_IN_MAP` where it
  handles `THEN_NOT_IN_MAP`: in `reconcile` the scenario's verdict does not move and
  the user gets a finding; in `revise` an `ALTITUDE_NOT_IN_MAP` only in the after-run
  is an edit to the snapshot, reverted; in `review` it is a finding against the doc.
  A deleted `Altitude` column is `ALTITUDE_MISSING` (info), not drift, so older docs
  keep passing; `revise` treats one only in the after-run as its own edit, and
  `review` as a finding unless the doc never had the column.
  A test checks that each paragraph that names one names the other.
- **`adopt`**. The set-up offers match what `adopt` may write: the `branch` line is
  named for the user to add, and `map.junit` and `map.surfaces` wait for a map,
  where `backfill` sets them. A product with code and tests is a reason to start the
  starter map. The CI offer copies the template as it stands.
- **`merge`**. A `building` doc's red tests sit on its work branch, whatever the
  `branch` setting names.
- **The router and references**. `SKILL.md` says `map.surfaces` runs through
  `adapter.py` or `check.py`, never a shell line, and states the `backfill` phrase
  rules. `altitude.md` and an anti-rationalisation say a computed proven is not
  proven. `architecture.md` describes `check.py`'s six steps, the `not-run` bucket,
  the `surfaces` op and the shell-safe config values.
- **The framework**. The agreed-to-shipped arrow with no red gate names its
  condition. A pipe inside a §6 cell is written `\|`. § Lifecycle, where `arm` and
  `adopt` offer the starter map, names the `"map": false` exception, as `config.md`,
  `arm`, `adopt` and `backfill` do.
- **README**. The report's buckets, worst first, with `not-run`; the Action and a
  local `check.py` read the same `docsHome`; a `leftOut` entry names one test; a
  `shipped` doc with no `Red gate:` line is an error unless every §6 line links a
  proven backfilled row (`SHIPPED_NEEDS_GATE`, `SHIPPED_WITHOUT_GATE`). The enforcement tables name the shell-safe config values,
  the exact-link rule (`bridge_validate.py --linking`), and the git pre-commit hook
  that checks §0 for agents other than Claude Code.

## 1.7.0

promise in Codex, Cursor and other agents.

- **`scripts/install_skill.py`** links (or `--copy`) the skill into
  `.agents/skills/promise`, which Codex and Cursor both read, or into
  `.codex/skills` and `.cursor/skills` (`--host`), for one user or one project. It
  never overwrites something else, and a second run is a no-op.
- **`adopt.py --agents-md`** writes the same routing block into `AGENTS.md`, which
  Codex, Cursor, Copilot, Gemini CLI, Windsurf and Zed read. The block now names
  `/promise`, `$promise` and the Cursor skill.
- **The §0 rule for agents without a pre-edit hook:** `install_skill.py --git-hook`
  installs a git pre-commit hook (`hooks/precommit.py section0`), and
  `.pre-commit-hooks.yaml` offers `promise-section0` and `promise-lint` to the
  pre-commit framework.
- The example author is Ollie.

## 1.6.0

The map, joined to a real test run.

- **`scripts/map_report.py`.** Reads each row of the capability map (story,
  scenarios with their altitude, cited tests per lane) and joins every
  `file::name` citation to a JUnit run (Vitest, Jest, Playwright, pytest). Each row
  gets a bucket — failing, bad-citation, never-ran, skipped, passing, external,
  no-test — and a verdict computed from the lane its scenarios' altitudes pick:
  proven, under-proven (green, but not in the lane the sentence needs), not-built.
  The computed verdict is compared with the recorded one (optimistic, promotable,
  unknown-verdict); the map is never written. Tree, Markdown and JSON output;
  `--strict` for CI.
- Worst result wins in the proving lane: one green test proves nothing next to a
  red, skipped, never-run or bad citation. An empty run file is refused. The report
  records run totals and a sha256 fingerprint of the map, config and run files.
  Optional `must`/`should` priority leads the summary with "must rows not proven".
- Hardened by an adversarial review: 11 findings, each fixed with a regression test.
- `examples/proofmap/`: a six-row map with a JUnit run that shows every outcome.
- The `CLAUDE.md` block `adopt` writes tells agents to start at the map for any
  question about what the product does.
- README: credits the work `promise` answers (Beck, Böckeler, the AI-native SDLC
  playbook, gstack), with links.

## 1.5.0

The human's block is now enforced, not only requested.

- **`scripts/diff_outcome.py`.** Compares §0 before and after — two files, or a git
  ref and the working tree, or every doc in a folder. On an `agreed`, `building` or
  `shipped` doc, only the rule tags and the `Scenarios:` count may change; anything
  else is `S0_CHANGED` (error) unless the same change sets `Status: draft`
  (`S0_REOPENED`, a warning). It replaces the planned script of the same name.
- **A plugin hook.** `hooks/hooks.json` runs `hooks/guard_section0.py` before every
  Edit, MultiEdit and Write. It blocks a model edit that `diff_outcome.py` would
  reject, and tells the model to put the change to the human as a note. It fails
  open, and it does not see shell commands or a person's own edits.
- **A GitHub Action.** `uses: osouthgate/promise@v1` lints the outcome docs and runs
  `diff_outcome.py` against the pull request's base branch. `adopt` offers
  `templates/promise-ci.yml`, Recommended when the project already has workflows.
- README: "Enforce it in CI"; the §0 rule moves from the "followed by the model"
  table to the "enforced by a script" table.

## 1.4.1

promise has its own repository: `osouthgate/promise`.

- Install with `claude plugin marketplace add osouthgate/promise` and
  `claude plugin install promise@promise`. The repo root is both the marketplace
  and the plugin.
- The git history of the plugin comes with it.
- The test suite runs from the repo root: `python3 -m unittest discover -s tests -v`.

## 1.4.0

The thin draft: start a promise with less.

- **`Depth: thin`.** A `draft` doc can now hold the human half only: §0–§2, §8–§10
  and any seed example, with §3–§7 marked "not written yet". `new` offers it,
  Recommended, when the outcome line is known but the rules, the signal or an
  example are not. Each gap is a BLOCKING §9 question, never text the model wrote
  for the human. Rules stay verbatim-confirmed. Framework decision F10.
- **`render_outcome.py --thin`** writes the shape: the `Depth: thin` line, one rule
  slot tagged `→ UNTESTED`, zero `Scenarios:` counts.
- **New lint rule `THIN_DRAFT`** (error): a `Depth:` line must read `Depth: thin`,
  and only on a `draft`. On a thin draft the lint does not require the §6 table or
  the §4–§7 Why lines, counts an empty §3 as zero, and reports an empty rules block
  as a warning. Past `draft` every rule applies in full, so a thin doc cannot be
  agreed or armed.
- **`revise` fills a thin draft** once the human half is complete, with `new`'s
  agent-half steps, and removes the line. `arm` names the thin line as a
  precondition.
- README: rewritten for a first-time reader. The one-line pitch and the install
  command come first, then the four-step path, then the §0 example. A "Why
  promise" section explains the name. The capability map is one optional
  paragraph, and the word list keeps the seven core terms.
- The plugin and marketplace description is two sentences.

## 1.3.0

Proof strength: a second axis beside altitude, for §4 invariants.

- **Three strengths.** `example` (chosen cases), `property` (the real code on
  generated cases), `model` (every reachable state of a model, by a machine-checked
  proof such as Lean or an exhaustive TLA+ check). Altitude says what evidence reaches;
  strength says how much of it. "Must never" is a claim about every case, and an
  invariant held only by examples now says so. New section
  `references/altitude.md` § Proof strength; framework decision F8.
- **§4 enforcement points** gain `property` and `proof` beside constraint, test and
  `file:line`, and name their strength when they are evidence — in the framework's
  Section rules, the template and `new`. The review rubric's depth item checks it.
- **A `model` proof never enforces an invariant alone.** It names a conformance test
  that runs the real code against the model, because the model is a second copy of the
  logic and can differ from the code while every theorem stays green.
- **Red and kill rules carry over.** A proof with `sorry`, `admit` or an unchosen axiom
  is red. The kill mutation is applied to the model (allow the forbidden transition,
  watch the proof fail, revert); the positive control proves the protected state is
  reachable.
- §6 rows, map lanes and the verdict rule are unchanged. Vocabulary gains
  **proof strength**.

The capability map becomes the goal, offered at the first agreed doc.

- **A starter map ships with the skill.** `templates/starter-map/` holds an empty
  `map.json`, its stdlib reader `capability_find.py` and a `recipe.md`. The new
  `scripts/start_map.py` copies it into a project (`docs/capabilities` by default),
  fills `{dir}` and `{docRoot}`, and writes the config's `map` object so `orient.py`
  reports `mapUsable: true` straight after. It refuses, writing nothing, when there is
  no config, when the config already has a `map` object (even a partial one), or when
  the destination escapes the project or already holds files; `--dry-run` shows the
  files and the config diff.
- **`arm` offers it, Recommended,** when no map is configured and `map` is null, before
  anything is filed; the files and the config ride the doc commit. **`adopt`**
  recommends it when an agreed doc already exists, and otherwise leaves `map` null and
  says `arm` will offer it. adopt's null-map `$comment` says so too; `start_map.py`
  removes exactly that comment when it fills the map.
- **The framework says why.** § Lifecycle gains "The capability map is the goal"; new
  decision F9. `config.md`, the README, the architecture (tree, §13, §14, vocabulary)
  and the example config stop saying the plugin ships no map.
- **The reader gains `docRoot`.** `capability_find.py --check` resolves a row's `doc`
  against the map's optional top-level `docRoot` (relative to the map, default `.`), so
  a map in a subfolder cites docs by their project-relative path. `examples/minimap/`
  runs the same file byte for byte; `tests/test_start_map.py` holds the two copies equal
  and covers install, refusal and `docRoot`.

## 1.2.0

The `outcome` plugin is removed from this repository; its framework lives on here.
The doc contract gains one column, every script is hardened against the inputs a real
project hands it, the router gains a confirmation gate, and every pre-install surface
is brought level with the plugin.

### Doc contract

- **Altitude column in §6.** The acceptance table gains a fifth column between `Then`
  and `Row`: `| #    | Given | When | Then | Altitude | Row |`, with exactly one of
  `data`, `response`, `perception`, `judgement`, `sibling` per row — the machine-readable
  left operand of the verdict rule (`references/altitude.md`). `lint_outcome.py` gains
  `ACCEPTANCE_ALTITUDE` (error: the column is present and a cell is empty or not one of
  the five) and `ALTITUDE_MISSING` (warning: a §6 table has no `Altitude` header, so
  older docs keep linting). `outcome_rows.py` emits `"altitude"` per row (`null` when
  the column is absent). The framework, the template, `altitude.md`, `new`, `arm`,
  `reconcile`, architecture §9/§10 and the fixtures all carry the column.
- **The framework states the two lines its tooling already required.** A `building`
  doc's `Red gate: <sha> <YYYY-MM-DD>` header line, directly under `Supersedes:`
  (`lint_outcome.py BUILDING_NEEDS_GATE`), and a bridged doc's
  `` Snapshot taken at `agreed` on <YYYY-MM-DD>; the map is the source of these scenarios from here on. ``
  line under the §6 table (`bridge_validate.py SNAPSHOT_LINE_MISSING`) are now in
  `outcome-framework.md`'s Lifecycle, not only in `modes/arm.md`.
- **One home for the template.** `outcome-framework.md` no longer embeds a second copy
  of the skeleton; `templates/outcome-doc.md` is the one shape and the framework points
  at it. The §4 boundary guidance that lived only in the embedded copy moved into
  Section rules.
- **§0 carries only the human's words.** The template's five-line note to the agent,
  which every rendered doc carried inside the protected block and counted against its
  40 lines, is gone; the "Agent notes" line takes the framework's wording. The
  `**Scenarios:**` line pluralises correctly: the lint accepts `worked example` and
  `worked examples`, `outcome_rows.py --write-counts` writes the right one, and the
  template says `1 worked example`.
- **Worked-example minimum reworded.** "the happy path, the disconnect/undo path, the
  permission-removal path" — one product's shape — becomes "the happy path, the
  undo/reverse path, and any permission or visibility edge the capability has" in the
  framework, the template and `new`.

### Scripts

- **`§`, never `SS`.** `lint_outcome.py`, `outcome_rows.py`, `orient.py` and `adopt.py`
  print `§` where they printed the digraph `SS`; stdout is reconfigured to degrade to
  `?` on a console that cannot encode it instead of crashing.
- **Config `"version": 1`.** Replaces `"$schema": "promise.config/v1"`, a reserved key
  holding a value nothing resolved. `orient.py` accepts both and warns on `$schema` as
  deprecated; `adopt.py` writes `"version": 1`; the example config, the fixtures and
  `config.md` say so.
- **Query files.** `adapter.py find --query-file <path>` and
  `outcome_rows.py --search-file <path>` read the query from a file (`-` = stdin); the
  inline form stays. `intake` and `reconcile` write the verbatim item to a scratch file
  with the Write tool and pass the flag, so "no composed shell strings" now holds for
  both hops, not only the adapter's.
- **Map usability is one field.** `orient.py`'s `mapUsable` is the single source of "is
  a map configured". When it is false, `adapter.py` refuses map operations (exit 2) and
  `bridge_validate.py` reports `MAP_NOT_CONFIGURED`, both naming the missing keys,
  instead of running against a partial map; `adapter.py show` still prints the partial
  map with a note. Mode files say "whether a map is configured (orient's `mapUsable`)".
- **`render_outcome.py --create-docs-home`.** The docs folder is created only when that
  flag is passed — the user's explicit choice in `new` or `adopt` — never unprompted; a
  `--dry-run` needs neither the folder nor the flag. Also new: `--slug <name>` for a
  title with no ASCII letter or digit (an empty slug is refused instead of writing a
  hidden `.md`), `--date` must be a real calendar date, `--title` and `--owner` must be
  non-blank single lines, and a docs home that is a file is refused.
- **`lint_outcome.py` hardening.** New error rule `RULES_PRESENT` (a `**Rules:**` marker
  with no rule bullet). Lines inside a ``` or ~~~ fence are illustrations — no heading,
  field marker, table row or placeholder inside one counts — so a framework copy in
  `docsHome` is no longer linted as a doc. `ACCEPTANCE_TABLE` reads a row missing its
  leading or trailing pipe GFM-style and reports it at its own line instead of dropping
  it and every row below. `TLDR_FIELDS` accepts a curly apostrophe in
  `**How we'll know:**` and bounds the rules block by the next field, heading or the
  end of §0 — one finding, not a cascade. `WHY_LINE` fires on an empty value;
  `PLACEHOLDER` also scans agent notes, the first line of each §3 example, a §9 owner
  and every Why-line value. A Why line or the snapshot line directly under the §6
  table is never read as a table row, pipe in its prose or not. A fence that is
  opened and never closed is its own error, `FENCE_UNCLOSED`, at the opening line —
  every line after it is an illustration to every other rule, and the wall of
  missing-heading findings that produces now has a named cause. The exit contract is
  documented as it is: 0 with no error finding, 1 on an error (or a warning under
  `--strict`), 2 on usage. `HUMAN_HALF_BUDGET` gains its one-change fixture, so every
  lint rule now has one.
- **`orient.py`.** `mode` is `null` when `--mode` was not passed. It warns when a
  configured `docsHome`, `map.recipe` or `map.index` is not on disk (the value is still
  returned; `mapUsable` stays a shape check), when a path uses backslashes (normalised
  for `docsHome`, `plansFolder` and `frameworkPath`), and when `map.checks` or
  `map.issueTracker` is malformed, and when a loaded config pins no `docsHome` in a
  project where detection finds no docs folder either. A path that escapes the project
  includes a Windows drive-letter path (`C:\\x`, `C:/x`, `D:docs`) on every OS. The
  existing-docs scan reads one level deep — the folder and its immediate subdirectories,
  the same scan the lint and `--search` use — ignores fenced headings and
  skips a non-UTF-8 file with a warning. A digit-only 7–40 run is no longer read as a
  commit sha; a plain complaint sentence ("users say X is broken") leans `intake`;
  `bun.lock` is detected. A `--cwd` that is not a directory or a non-UTF-8
  `--input-file` exits 2 with one line, never a traceback.
- **`framework_section.py`.** Resolves `frameworkPath` through `orient.py`, so an
  escaping or missing path falls back to the bundled copy exactly as Phase 0 does; no
  section name and no `--list` prints usage and exits 2.
- **`adapter.py`.** `verify --only typeCheck|test|lint` (repeatable) narrows the verify
  run; `show` prints a note line for an incomplete map and for nothing configured; a
  non-string configured command is a plain refusal, never a traceback. `--query-file`
  and `outcome_rows.py --search-file` keep an interior CRLF as written — only the
  trailing line terminator is dropped.
- **`bridge_validate.py`.** New error rule `STATUS_UNKNOWN` (a missing or invalid
  `Status:`), checked before `NOT_BRIDGED`; `THEN_NOT_IN_MAP` names all three causes —
  the map moved on, the row was filed differently, or §6 was edited after the snapshot.
- **`outcome_rows.py`.** `--search --dir` walks the folder plus its immediate
  subdirectories, as the lint does, and refuses a missing or non-directory `--dir` with
  exit 2; a non-UTF-8 doc is an exit-2 refusal.
- **`adopt.py`.** Writes the `commands` object only when at least one command was
  detected, then with all three keys (undetected as `null`); writes through a symlinked
  `CLAUDE.md` and keeps its mode; refuses a `--docs-home` that is absolute, escapes the
  project, or holds a newline or a marker string, a `CLAUDE.md` or config path that is
  a directory or sits under a file, and a non-UTF-8 `CLAUDE.md` — JSON still on stdout,
  nothing written; tolerates whitespace around the end marker and says on stderr when
  it restores a hand-edited block. A `--docs-home` written with backslashes is recorded
  with forward slashes; a `--docs-home` that disagrees with an already-loaded config's
  `docsHome` is refused (exit 2) rather than re-rendering `CLAUDE.md` against a folder
  the config does not name; a fresh config that would pin no `docsHome` says so on
  stderr; the JSON result carries `docsHome`. The escape rule is orient's, imported,
  not a second copy.

### Router and modes

- **A missing interpreter no longer aborts the skill.** The load-time line ends in
  `|| true`; the fallback paragraph tries `python`, then `py -3`, before asking for an
  install, and uses the first spelling that runs for every script that session.
- **Configured commands run on a yes, not a print.** Before the first configured command
  runs in a session, `adapter.py show` is printed and the person is asked
  ((Recommended) first, one reason); nothing configured runs until the yes, and on no
  the session continues as if no map and no `commands` were configured. `config.md`
  gains a "Trust model" section: every configured string runs as the caller, like a
  `package.json` script; the adapter protects against a hostile query, not a hostile
  config.
- **Completeness scores dropped.** "(Recommended) first, with one concrete reason"
  stays; the mandatory 1–10 completeness score is gone from every mode and reference,
  along with `adopt`'s pre-baked numbers. Reading-assignment close-outs in `intake` and
  `reconcile` are an offer, not a requirement.
- **`arm` in order.** The branch is cut first; the bridge runs on `feat/<slug>` behind
  a reachability gate (`adapter.py --json next-id` / `row` must succeed before anything
  is filed) with a per-rule table for every `bridge_validate.py` finding; the red run is
  `adapter.py --json verify`; the doc — and, with a map, the recipe's row files — is
  committed by explicit path as the branch's second commit. Loosening `rowIdPattern`, a
  checker or a ratchet is never a fix. The unreachable "protected branch" refusal became:
  name the base branch and ask when it is not the project's main branch.
- **§6 is a snapshot once bridged.** `revise` edits §6 only while it carries no `Row`
  ids and no snapshot line, and runs `bridge_validate.py` before and after an edit to a
  bridged doc; `review` folds `THEN_NOT_IN_MAP` and `SNAPSHOT_LINE_MISSING` in as
  findings; `reconcile` runs it before reading the map.
- **`merge` names its mechanics.** `git rm` by explicit path and one commit with the
  survivor; a bridged folded doc's map rows are re-pointed or retired per the recipe,
  with the user; a `building` folded doc's red gate is retired in §8 and the branch's
  disposition asked; `Status: superseded-by <survivor>` is written only on a folded doc
  the user chooses to keep, and the framework's Lifecycle says so.
- **One hand-back sequence.** `arm`, `intake` and `reconcile` all run
  `adapter.py checks` if a map is configured (and `map.checks` is set),
  `adapter.py verify` if any `commands.*` is configured (`[]` is reported as "not
  verified", never a pass), and the lint always. Each writing mode says in one line that
  the lint checks shape, not truth.
- **`new` asks for the whole human half.** Five prompts in one turn — outcome, why,
  rules echoed for verbatim confirmation, how-we'll-know, one concrete example — plus
  the owner, with `git config user.name` as the recommended default. The §3 minimum is
  the happy path, the undo/reverse path and any permission or visibility edge.

### Packaging and docs

- **The `outcome` plugin is removed** — its directory, its marketplace entry and the root
  README's install line. Every remaining supersession sentence says so.
- **The pre-install surfaces agree with the plugin.** The marketplace entry and the root
  README undercounted the modes by one; there are eight. The marketplace description is now the same
  string as `plugin.json`'s, and neither lists `agreed` among the modes — `agreed` is a
  status a human types; `arm` is the mode that files rows and commits the red tests
  once a human has typed it.
- **The README leads with the doc, not the map.** A filled §0, the four-step path that
  needs no config and no capability map, a table of what a script checks versus what
  the model is instructed to do, a definition of "capability map" at first use with a
  plain statement that this plugin ships none, a Codex/Cursor install path, a
  ten-word glossary and a prior-art paragraph. The Scripts block runs verbatim from
  `promise/`.
- **Examples outside `tests/`.** `examples/channel-muting.md` (a lint-clean doc),
  `examples/transcript.md` (a short annotated session) and `examples/minimap/` (a tiny
  capability map with a stdlib `capability_find.py`, so `arm`, `bridge_validate.py`
  and `adapter.py` can be watched doing the bridge). The minimap's
  `capability_find.py --check` also reads each row's `doc` and requires a §6 line
  citing the row — the map-to-doc direction `bridge_validate.py` does not read — and
  validates an optional `parent` as a row id. `tests/test_examples.py` lints
  the examples and runs `bridge_validate.py` against the minimap.
- **Tests and CI.** New suites `test_orient_render.py`, `test_adopt_hardening.py`,
  `test_examples.py` and `test_packaging.py` (the pre-install surfaces agree with the
  plugin: marketplace description, mode count, version). `.github/workflows/tests.yml`
  runs `python3 -m unittest discover -s promise/tests -v` on ubuntu-latest with Python
  3.12 on every push and pull request.
- **Config contract corrected.** `map.find` / `row` / `nextId` / `checks` and
  `commands.*` are documented as argv lines run with no shell, which is what
  `adapter.py` does. `orient.py`'s warnings are described as what they are — key names,
  types, path escapes, whether `frameworkPath`, `docsHome`, `map.recipe` and `map.index`
  exist on disk, map completeness, `rowIdPattern` compilation — never as a check that the
  configured commands exist or run.
- **Architecture doc brought level.** §3's file tree lists every script, the Codex
  metadata file and every test file; the example config is byte-identical to
  `templates/promise.config.example.json` (a shape test pins both); §7's vocabulary
  gains slate, recipe, lockstep, ratchet, red gate, kill mutation and snapshot line;
  §9 and §10 list every rule above.
- A root `LICENSE`, editor and OS artefacts in `.gitignore`, and the marketplace's own
  metadata (version 0.2.0) now names the plugins it lists.

## 1.1.0

`bridge_validate.py` closes the gap between a bridged doc's §6 and the capability
map it cites: Row ids against `rowIdPattern`, every AT row mapped, the snapshot
line present, and each row's `Then` against the map's current text — read through
`adapter.py`, so a row id always travels as one argv element, never a shell string
composed from configuration plus doc content. `NOT_BRIDGED` is checked before
`MAP_NOT_CONFIGURED`, so a still-`draft` doc reads as not-yet-bridged even in a
project with no map, never as a map problem. An invalid `map.rowIdPattern` (bad
regex syntax) is its own error, `INVALID_ROW_ID_PATTERN`, carrying the compiler's
own exception text — never silently folded into `NO_ROW_ID_PATTERN`'s "absent"
warning, which stays for a pattern that is genuinely not configured. `arm` runs it
once the `Row` column and snapshot line are written, and fixes every error before
continuing; `reconcile` runs it before reading the map, because a drift finding
means §6 no longer says what the map says.

`lint_outcome.py` gains `BUILDING_NEEDS_GATE` (error): a `building` doc's header
must carry its own line matching `Red gate: <sha> <YYYY-MM-DD>` exactly — position
among the header lines is not enforced, the line's own shape is, so a hex-looking
run inside some other header value never quietly satisfies it. `arm` records the
line there, so the status stays traceable to the act that earned it. A new test
locks the wider rule this is one piece of: `agreed` and `shipped` are typed by a
human, never by this skill; `building` is the one exception, written only after
the human confirms the red gate. `acceptance_column_map` now also rejects a header
that names `Given`, `When`, `Then` or `Row` more than once — never a guessed
mapping, the same `ACCEPTANCE_TABLE` error as a header missing one of them.

## 1.0.0

First release. Supersedes the `outcome` plugin, which stays in this repository with a
pointer here; its framework lives on here. [The `outcome` plugin was removed in 1.2.0.]

### What it contains

- **One skill, 8 modes.** `new`, `revise`, `review`, `merge` cover the doc's
  lifecycle; `arm`, `intake`, `reconcile` carry the promise past `agreed` into a
  project's capability map, its red tests, and its reconciliation with shipped work;
  `adopt` sets a project up. A thin `SKILL.md` infers the mode; only that mode's file loads.
- **The Outcome Framework, with its decisions recorded.** The outcome line and the
  success signal are forced choices from verbatim candidate slates; rules are never
  slated. Revise has an explicit procedure. §0 has exactly two agent-maintained
  carve-outs (rule test tags and the `Scenarios:` count); agent notes sit below the
  block and do not count toward its 40 lines. The framework's own decision table (F1–F7)
  states each choice and its reason.
- **The map is the source after `agreed`.** Where a project keeps a machine-checked
  capability map, `arm` files the §6 rows into it as not-built rows and the doc's §6
  cites them through a `Row` column instead of carrying a second copy. §0 keeps the
  doc-local `AT-n` aliases.
- **Config over fork.** A project supplies `.claude/promise.config.json` (docs home,
  framework path, commands, and an optional `map` adapter naming its recipe, search
  commands, evidence lanes, checks and issue tracker). Nothing project-specific is
  hard-coded. See `skills/promise/references/config.md`.
- **Scripts.** `orient.py` resolves the project shape in Phase 0 and prints one JSON
  object. `lint_outcome.py` checks every shape rule the framework states (§0 budget, bare
  headings, contents anchors, rule format and tags, tag resolution, scenario counts,
  why-lines, placeholders, UNTESTED-on-agreed) with stable rule ids and exit codes.
  `outcome_rows.py` extracts §0 rules and §6 rows as JSON for the bridge.
  `framework_section.py` prints only the framework sections a mode names in its header,
  so a run loads what it needs rather than the whole contract. Standard library only;
  one implementation for every OS.
- **No composed shell strings.** `adapter.py` runs every configured project command with
  the user's text as one argument, and `show` lists them before any runs. `render_outcome.py`
  instantiates the template and refuses to overwrite.
- **Tests.** `python3 -m unittest discover -s promise/tests -v` covers every lint rule
  except `HUMAN_HALF_BUDGET` (a warning) with a one-change fixture, `orient.py` against a
  fixture repo and an empty directory, and `outcome_rows.py` round-trips.
- **A proof taxonomy shared with the map.** `references/altitude.md` maps §0's four
  signal kinds onto the four `Then` altitudes and their lanes, and states the verdict
  rule: evidence moves a verdict only when it reaches the altitude the row's own `Then`
  claims.
- **Plain words, not syntax.** A leading mode word is a shortcut, never a requirement. The
  router infers the mode from the input and from Phase 0 (existing docs, configured map),
  states the inference in one line, and asks only when two modes are genuinely plausible.
  `orient.py --input` reads the same signals deterministically and names the rule that
  fired, as a hint the router confirms.
- **Adopt.** `/promise adopt` writes the project config and inserts a fenced section into the
  project's `CLAUDE.md` that routes every agent and person to the skill. `orient.py` reports
  `adopted` and every mode offers the step once when it is false.

### Why the rename

An outcome doc *makes* a promise; a proven row *keeps* it; a defect *breaks* it. The
skill now spans both halves, so it takes the word that covers both. The framework keeps
its name — the Outcome Framework is how a promise is written down.
