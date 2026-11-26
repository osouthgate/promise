Read before this: references/config.md
Phase 0 line: mode `upgrade` (say if inferred), `skillVersion`, orient's `promisePin` and `machinePlugin`, the pin and upstream from `pin_check.py --json` (versions, refs and shas, releases behind, its notices), every pin site, whether the section matches the pinned template, whether the project is adopted, and the branch the move goes on.
Writes: every promise pin site (`.claude/settings.json`'s promise marketplace `source.ref`, each `pinFiles` match) and the config's missing keys only through `scripts/upgrade.py`; the promise section only through the target release's `adopt.py`; this machine's plugin only through `scripts/pin_machine.py`; one branch, one commit and one pull request, all on the human's one yes. Never the default branch, never a merge.

# Upgrade — move this repository to a newer promise, as its own pull request

A repository pins promise to one release, so every session, hook and CI run in it uses
the same one. Three jobs stay separate:

1. **Check**, read-only, every pull request: `pin_check.py` says whether the pin is
   behind, and whether the section and this machine match it.
2. **Upgrade**, this mode: move every pin site, refresh the section with the new
   release's `adopt`, run the repository's checks, and open one pull request. A human
   reads and merges it: the pin moves only in a pull request a human has read.
3. **Adopt**, inside step 2 or at first set-up: the section only (`modes/adopt.md`).
   `adopt` never moves a pin.

**The pin is a release tag.** Claude Code's marketplace source reads `source.ref` (a
branch or a tag) and nothing else: a `source.sha` there pins nothing, so every machine
follows the default branch. `upgrade.py` writes `ref: vX.Y.Z` and drops the `sha`.

**The section is what agents read, not the changelog.** A repository pinned to a new
release whose `CLAUDE.md` or `AGENTS.md` still carries an earlier section runs the
earlier rules. Moving the pin without refreshing the section is half an upgrade.

## Read the state

Run `python3 "${CLAUDE_SKILL_DIR}/scripts/pin_check.py" --json` and read `state`:

- `current` with no `notices` → say "up to date (<version>)" and stop.
- `current` with notices → do only what they name: `section` → the adopt step below on
  a branch of its own; `machine` → the machine step; `sha-pin`, `branch-ref` or
  `moving-tag` (a tag such as `v1`, which moves) → the whole mode, to `upstream.ref`.
- `missing-ref` → the pinned tag is not upstream (never pushed, or a branch other than
  `main`): Claude Code cannot fetch it. The whole mode, to `upstream.ref`.
- `behind` → the whole mode. Name both versions and the releases between them.
- `disagree` → the pin sites name different releases: a defect. Say which file holds
  which value; the whole mode, to `upstream.ref` (reported beside the disagreement),
  moves them all to one tag and fixes it. `upstream` null → not reachable: stop.
- `unreachable` → say so, and stop. Never guess a tag or a sha. A private upstream is
  read through a local promise checkout the person keeps: name it in the config's
  `upstreamPath` or `PROMISE_UPSTREAM_PATH` (its own git access reads it), and run again.
- `unpinned` → nothing pins promise here: say so in one line, and stop. Pinning a
  repository that floats is the human's call.
- Exit 1 with `state: error` → a configured pin site cannot be read: name it, and stop.

Upstream's `upstream.ref` is not a release tag (`main`: upstream has none yet) → stop:
a marketplace can pin only a tag. Say that upstream needs release tags first.

## One ask, then the move

**One yes, not five.** Show, together, and ask once:

- the branch: `promise/upgrade-<version>`, or the session's own branch when the
  config's `branch` is `current` (any other value is `arm`'s pattern). Never the default branch;
- `python3 "${CLAUDE_SKILL_DIR}/scripts/upgrade.py" --to <upstream.ref> --sha <upstream.sha> --dry-run`:
  the diff of every pin site and the config, and what the project's own recipe and
  reader lack of the starter map's. The same preview includes Doctor's SLA
  inventory and setup suggestions. Pass `--observations <export.json>` if the
  user supplies a dated service observation export. Treat optional adoption as
  a separate decision from changing the pin;
- the machine step for this machine (`pin_machine.py --dry-run`): it changes this
  machine, not the repository;
- the checks that will run (`adapter.py show`; the session's first-command yes).

On the yes, in order:

1. Create the branch.
2. `upgrade.py --to <tag> --sha <sha>`.
3. `python3 "${CLAUDE_SKILL_DIR}/scripts/pin_machine.py"`. Exit 0 → this machine runs
   the pinned release. Not 0 → name what it printed under **Needs you**, and stop
   before the section: the running skill cannot write the new release's section.
4. The section, from the new release: run orient again and take `machinePlugin.installPath`;
   run `python3 "<installPath>/skills/promise/scripts/adopt.py" --dry-run`, then without
   `--dry-run`. That is the target release's `adopt`, so the section is the target's; the
   `adopt` beside this file would write the release being left. Text it cannot place exits
   2 with its lines: put them under **Needs you**, and leave the section as it is.
5. The repository's checks: `python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" verify`,
   `python3 "${CLAUDE_SKILL_DIR}/scripts/adapter.py" checks` if a map is configured, and
   `python3 "${CLAUDE_SKILL_DIR}/scripts/check.py"`. A check that fails is reported
   with its output, never skipped, and the pull request says so.
6. `pin_check.py` again: it must say up to date with no notice. It does not → say what
   it printed under **Not checked**.
7. Commit the pin sites, the config and the section together (`promise: upgrade to
   <version>`), push, and open the pull request (below). Never merge it.

The starter-map report goes in the pull request as a list for the human: a project
whose map is its own may lack a section or a flag on purpose. A vendored copy of the
skill (`install_skill.py --project .` with `--copy`) moves only with its files: sync it
first (that install from a promise checkout at the tag, and whatever writes the file that
records its commit), then run `upgrade.py`. That file is a `pinFiles` site with
`"vendored": true`, which `upgrade.py` refuses to move alone; no such site and the skill
running from inside the repository → `pin_check.py` says so, and the site goes under **Needs you**.

## The pull request

Title `promise: upgrade to <version>`. The body, in plain words:

- **What moves**: from `<version>` to `<version> (<sha>)`, and each pin site.
- **Releases**: each version between, newest first, with its CHANGELOG entry's first
  line (upstream's `CHANGELOG.md`). Link the full entries; do not paste them.
- **Section**: refreshed by the new release's `adopt`, or unchanged, and why.
- **Config**: each key `upgrade.py` added or raised.
- **Starter map**: what the project's recipe and reader lack, for the human to add or leave.
- **Checks**: each command and its numbers.
- **After merging, on each machine**: the machine step below.
- **Needs you**: anything a step above could not do.

`/promise pr` is for pull requests about the product; this one describes the upgrade.

## The machine step

A merged pin reaches a machine only when its plugin moves, and `claude plugin
marketplace update` alone does not move it: Claude Code keeps a saved copy of the
marketplace at the ref it was first added with. In each repository that pins promise:

```
python3 <promise>/skills/promise/scripts/pin_machine.py
```

and once with `--user`, from any repository, for the user-scope install. It runs
`claude plugin marketplace add <repo>#<tag> --scope project` (which moves the saved
copy; it may exit 1 with "now points at …") and `claude plugin update promise@promise
--scope project`, puts back `.claude/settings.json` when Claude Code only reordered it,
and checks `installed_plugins.json`. Then restart Claude Code. Uninstall then install
does not work for a project-scope plugin: uninstall is refused, and install says it is
already installed. A host other than Claude Code: check out the tag in the promise
checkout, or re-run `install_skill.py` for a copy.

## Close out

One message: **Needs you** (review and merge the pull request; the machine step on each
other machine; the starter-map items), **Decided for you** (the branch, the section
refresh, the config keys), **Not checked** (a check that did not run, a `pin_check.py`
line that was not up to date). Link the pull request.
