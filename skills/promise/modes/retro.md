Read before this: references/github-text.md (its plain-words rules)
Read at Draft, not before: the promise files the findings name.
Phase 0 line: mode `retro` (say if inferred), the sessions read (how many, and whether this one), whether the project is adopted, the promise version (orient's `skillVersion`), and the promise repository a draft would go to.
Writes: nothing in the project. A draft issue for the promise repository, in scratch, filed only on the human's yes.

# Retro — what promise could do better, from how a session went

Promise improves from real use: where an agent missed a rule, where a step took ten
round trips, and where the human got a file they could not use. This mode turns one
session into findings about promise, not about the project, and drafts one issue for
the promise repository. The human decides whether it is filed.

## Gather the facts

```
python3 "${CLAUDE_SKILL_DIR}/scripts/session_report.py" --json
```

It reads the newest session Claude Code keeps for this project (`--latest N` for more,
or pass `.jsonl` paths). It prints facts only: the promise files read and never read,
each script's runs and failures, and `signals`, each pattern promise has been seen to go
wrong in, with a count. A cloud session's transcript goes when its container does, so run
this before the session ends. With no transcript, say so and work from what the human
tells you.

It also lists `runs`: each close-out a mode recorded (`references/sizing.md` § Batch),
with its size, mode, stops by kind and the items under Needs you, Decided for you and
Not checked. `runTotals` sums them over the sessions read. Say the sums in one line:
"4 runs (3 tiny, 1 capability); 2 stops, both checkpoints; 1 needs you, 6 decided for you,
0 not checked". No run recorded → say so; that is a finding too.

Ask the human once, with the question prompt, what went wrong in their words. It is
optional ("nothing to add" is an answer).

## Find what promise let happen

One finding for each signal and each thing the human said, about promise only:

| Signal | Look at |
|---|---|
| `no-skill` | how the session found promise: the promise section in CLAUDE.md or AGENTS.md, and what it points to |
| `sheet-files-sent`, `sheet-not-published` | `references/decision-sheet.md` §2, and the next step `decisions.py sheet` printed |
| `hand-answers` | whether the agent knew `decisions.py apply`, and what stopped it |
| `rebuilt-script` | how the project runs promise's scripts (the config's `run`) |
| `repeated-command`, `promise.retries` | which step the agent repeated, and whether one script could have answered it |
| `script-refused` | the refusal's text: did it name the fix, and did the agent follow it |
| `promise.notRead` | why the session never needed that file, or never found it |
| `runs` | a tiny run with a stop or a Needs you item, a run with more than one stop, or no run recorded: `references/sizing.md`, its size test and § Batch |

Each finding says:
- **What happened**, in plain generic words: "an agent with no skill loaded sent the
  sheet's Markdown file". Never "in <project> the billing sheet…".
- **Where promise was involved**: the skill's file or script, as `skills/promise/…`.
- **Why it went wrong**: the rule was missing, or in a file the agent never read, or a
  script's output did not say it.
- **The fix**: a script's output, a check that refuses, a flag, or one doc line. The
  best fix puts the rule where the agent already looks: a script's `next` line, a
  refusal, the promise section. A rule only in a reference file gets missed.

Leave out what the project did wrong that promise could not have caught.

## Draft

Write `<scratch>/retro-issue.md` in this shape:

```markdown
## What happened

<two to four plain sentences>

## Where promise was involved

- `skills/promise/<path>`: <what it says or does now>

## Why it went wrong

<one to three sentences>

## Proposed fix

- <the change: script, flag, check or doc line>

<details><summary>Session facts (scrubbed)</summary>

<the output of session_report.py --scrub --json, in a json fence>

</details>
```

Title: `retro: <the pattern, in a few words>`. One issue can carry several findings, one
`##` block set each, when they share a cause. Otherwise it gets one issue each, most
important first.

**Scrub before anyone else sees it.** The promise repository is public. The draft names
no project, repository, folder, person, customer or product feature. It holds no path
outside the skill, no issue or pull request number, no code and no quote of the
project's docs. Counts are fine. Then run:

```
python3 "${CLAUDE_SKILL_DIR}/scripts/session_report.py" --scrub-check <scratch>/retro-issue.md
```

Fix every finding it lists and run it again, until it prints that the draft is clean.
The check cannot catch every word, so read the draft once more for a name it missed.

## Hand it to the human

Show the whole draft and ask once, with the question prompt: "File this on the promise
repository? (Recommended)", or "Change it first", or "Keep it local". On a yes, file it:

- with the host's GitHub tool, or `gh issue create --repo <repository-from-scrub-check> --title
  "<title>" --body-file <scratch>/retro-issue.md`;
- to the repository in `.claude-plugin/plugin.json` `repository` of the promise copy
  this project runs, or, for a copy with no `plugin.json` (vendored or linked), the
  repository its README names.

Say the issue's link in one line. On "keep it local", say where the draft is.

Never file without the human's yes. Never file a draft the scrub check did not pass.
Never change the project's files in this mode.
