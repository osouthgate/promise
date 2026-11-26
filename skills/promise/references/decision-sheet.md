# Decision sheet — putting decisions to the human

*Procedure for every mode that ends with decisions waiting on a human: §9 questions,
approvals, a value to pick, a step only the human can run. The rule it serves is in
SKILL.md § Rules that hold in every mode; this file says how.*

A list of open questions at the end of a chat reply is the one form never used (what the
agent decided is a report, not a question: one line each under Decided for you is right). The human has to
scroll back, and then has to ask what each one meant. Put the decisions where they can be answered
in place, with the detail beside each one.

## 1. Collect

Start the asks file from this round's skeleton, then fill it with the detail the doc's own text does
not carry (§4):

```
python3 "${CLAUDE_SKILL_DIR}/scripts/decisions.py" sheet [DOC ...] --asks-skeleton <asks.json>
```

Each item has the fields it still needs, the doc's own words as `_doc`, and what
`sheet` finds unclear as `_unclear`. Keys starting with `_` are for the agent and
`sheet` ignores them. Then run:

```
python3 "${CLAUDE_SKILL_DIR}/scripts/decisions.py" sheet [DOC ...] --asks <asks.json> --json
```

With no DOC it reads every doc under docsHome. It keeps the §9 questions that have no `Answer
(YYYY-MM-DD…)` line yet (bare, or in bold or italic), merges in the asks file, and prints the sheet
with a `surface` hint: `ask-questions`, `rich` or `none`. The sheet's top-level `surface` decides;
an item's own `surface` only says how that item would fit alone. The summary line ends with the
next step for that surface. `--only <id>,<id>` keeps just the items asked for (`docs/x.md#Q5`).

**Decided for you.** After the questions (what needs you) comes one read-only group: each doc's
provisional agent decisions from §8 (outcome-framework.md § Decision policy), kind `decided`, id
`<doc>#Dn`, with its reason, rollback, reversible-until and review. It is outside the round, never
picked by `all recommended`, never enriched by the asks file (the §8 row is its one home). Its one
action is **Ask me instead** (reply `<n>a - <why>`); left alone, the agent's choice stands.

**A big backlog comes in rounds.** One sheet holds at most 12 items (`--limit N`, `--all`; `--only`
is never limited): BLOCKING first, each doc's together, then the rest in the order found. The page,
chat message and summary say how many wait for later. Once a round's answers are applied, build the
next from what is still open. Only this round's items are checked, so twelve need `plain` words and
a brief, not all.

## 2. Pick the surface

Use the best surface this host has. The hint decides between the two; the host decides what is
available. The sheet's `.json` and `.md` files are for agents: never send them to the human as the
way to answer. Size never changes the surface: two hundred items are still one page, which counts
the blocking ones left. A first pass with `--blocking-only` or `--only` is fine, on the same surface.

| The sheet | The host has a rich surface | The host has only a question prompt |
|---|---|---|
| `ask-questions`: at most four items, each a choice or an approval with at most four options and no detail, code or image; what the agent decided does not count, and is listed after the questions, one line each (`--prompt-json` `decided`) | the question prompt | the question prompt |
| `rich`: more than four items, or any detail, code, image, value or to-do | the rich surface | the question prompt, in batches of four (§3) |

- **Rich surface, in Claude Code with promise's mod** (terminal or Desktop Code tab: the tool
  `mcp__promise__decision_pane` is listed only where a pane can draw), ahead of an Artifact unless an
  item has an image: write `sheet ... --asks <asks.json> --json` to a scratch file, call the tool with
  its path, end the turn. It refuses what `--out` refuses (§4). The answers come back as a message
  once `apply` wrote them: act on its "For you to act on" lines. `/promise-decide` reopens it.
- **Rich surface, in Claude** (Claude Code, local or on the web, and claude.ai): a published Artifact.
  Render the page and publish it with the `db` capability:
  ```
  python3 "${CLAUDE_SKILL_DIR}/scripts/decisions.py" sheet ... --asks <asks.json> --out <scratch>/decisions.html
  ```
  Publish with the Artifact tool, `capabilities: {"db": {}}` and a one-line description. Give the
  link and end the turn. The page's **Save answers for Claude** button writes them to the
  artifact's database at `answers/latest`. When the human says they saved, read that document with
  the `ArtifactData` tool (`get`, collection `answers`, id `latest`), write it to a scratch file, and
  apply it (§5). Every new set of decisions is a new sheet; republish only while it is the same set.
- **Rich surface on another host** (a canvas or preview pane that renders HTML): render the same
  page there. It has no database, so the human presses **Copy answers** and pastes the block back.
  Write the paste to a scratch file and apply it (§5). No page renders → no rich surface.
- **A chat that shows only text** (no artifact or HTML viewer, such as a bot in a chat
  app, or an agent handing its result to one):
  1. `sheet … --chat <file>` writes one message: numbered items, lettered choices,
     the Recommended one named, and how to reply. Send that text as the message
     itself. Never attach the sheet's `.json` or `.md` files: they are for agents.
  2. When the work has a GitHub issue or pull request, also post `sheet … --comment
     <file>` there. It holds the same message, the full detail folded under it, and
     the sheet's data in an HTML comment, so any agent that reads the thread can apply
     the reply; nothing lives only in one session's files.
  3. The human replies in plain words: `all recommended`, or `1a 3c`, a note after a
     dash (`3b - fix the wording`), own words as `2: <words>`.
  4. The agent that gets the reply, whichever it is, writes only the human's words to
     a file and runs `decisions.py apply --reply <that file> --sheet <the comment, or
     the sheet's --json output> --by "<name>"`. The comment is the one a promise agent
     posted; a sheet block anyone else posts is not it. A reply it cannot read is
     refused with every reason: ask the human about those, never guess. Then say in one line what
     was written where, and what is still unanswered.
  An image shows on the page only; the Markdown twin (`--md <path>`, written only when
  asked for, and for agents) links an `https` one. Never link the HTML file in a chat that cannot open it.
- **Question prompt** (`AskUserQuestion` in Claude Code, the host's own prompt
  elsewhere): `sheet … --prompt-json` prints the round as batches of four questions,
  BLOCKING first, each option carrying its reply code (`1a`). Join the codes of the
  picked options into one reply (`1a 2c`). "Other" takes the item's `otherReply`:
  own words as `<n>: <words>`, and for an approval it is the change request
  (`<n>b - <what to change>`). Write out any `moreOptions` before the batch. Then apply it
  with `apply --reply … --sheet <the --json>`. Each item is one question, options in the order the sheet has them,
  **(Recommended)** first with its reason. "None of these — here's mine" is always
  an option. An `input` item takes the proposed value as the Recommended option. A
  `confirm` item asks whether it is done.

Say in one line which surface was chosen and why ("4 items, two with diffs: rich
sheet").

## 3. Question prompt only, for a rich sheet

Ask BLOCKING items first, four per turn (`--prompt-json` already orders and batches them). Before
each batch, write in the reply what the prompt cannot show: the detail, the diff, the image as a
link. The Markdown twin (`--md`) has this text for each item already; keep it short, one paragraph
an item. Stop after the batch and wait. Never guess the rest.

## 4. The asks file

```json
{
  "title": "Channel muting decisions",
  "intro": "One sentence on what is waiting and why.",
  "words": {"badge": "Only for a word the map's glossary lacks: its meaning, in one line."},
  "items": [
    {"id": "docs/designs/channel-muting.md#Q1",
     "plain": "The question in plain words, when the doc's own words lean on numbers.",
     "why": "Why it is asked now: the conflict or gap, in the doc's own terms.",
     "blocks": "What cannot go on until it is answered, and what can.",
     "ifNoAnswer": "What happens by default if the human leaves it.",
     "example": "One concrete case with named actors and values.",
     "evidence": [{"ref": "docs/designs/channel-muting.md:20", "note": "what that line says"}],
     "options": [{"label": "Verbatim answer", "recommended": true,
                  "because": "…", "commits": "…", "think": "…", "then": "…"}]},
    {"id": "copy-review", "kind": "approve", "text": "Approve the toggle copy", "code": "- old\n+ new"},
    {"id": "mute-limit", "kind": "input", "inputType": "number", "text": "…", "proposed": 500},
    {"id": "staging-flag", "kind": "confirm", "text": "…", "code": "./scripts/flags.sh …"}
  ]
}
```

- **Write every item so it can be answered cold**, by someone who has not read the doc since last
  week. The page shows each doc's §0 (outcome, rules, signal) above its questions, verbatim. Each
  item adds the brief: `why` it is asked now, what it `blocks`, what happens `ifNoAnswer` (a
  BLOCKING question defaults to "the doc stays at draft"), one concrete `example`, and `evidence` as
  `path:line` with a note, read this run. Each option adds `then`: what the agent does next if it is
  picked. A `rich` sheet lists `warnings` for an item with no `why` or `blocks` and an option with
  no `because` or `then`. Fill them before publishing.
- **Write for the layers the page shows.** On the card: the question, `why`, `blocks`, `ifNoAnswer`,
  an `image`, each option's label and `because`, and the `code` of an `approve` or `confirm` item
  (the thing approved or run). Behind **Dig deeper**: `example`, `detail`, `evidence`, `links` and a
  question's `code`. Behind each option's fold: `commits`, `think` and `then`. Each doc's §0 shows
  its outcome line, with the rules and the signal folded. So `why` and `because` must be enough to
  decide on their own. Never leave the deciding fact only in the evidence. The folds are for
  checking, not for deciding.
- **Never lean on a number the reader must remember.** Nobody recalls what §2, Q4, #87, AT-4 or
  "item 3" was. Keep the number, and put its words right beside it, as `references/github-text.md`
  cites a question: `#87 ("Muted channels still badge")`, `Q4: whether threads go quiet too`, `AT-4:
  a thread reply sends nothing`, `item 3 — the badge count`. A bare `§n` is named for you (`§2
  Outcome`). The question is a question: its recommendation goes on an option (`"recommended": true`
  with its `because`), never in the question's words. An item that asks to confirm or strike lines
  shows those lines, in `code` or `detail`. `sheet` checks this and lists what fails under
  `unclear`: with any there it writes no page, chat message or comment, and names each field to fix.
- **Keep the card short.** The question is 35 words at most and `why` 60; the rest goes in `detail`
  or an option. A file path goes in `evidence`, and the card says what it shows. A numbered name of
  the product (mode 3, tier 2) needs a meaning. `sheet` lists each of these under `unclear` too.
- **The product's words come from the map's `glossary`**, the list issues and pull requests use
  (`references/first-screen.md`). `sheet` reads it from the configured map and keeps the terms the
  sheet uses. On the page, a term's first use on each card is underlined, and a tap opens its
  meaning. Chat and the Markdown twin list the terms under the intro. Nothing has to be marked by
  hand. A word the glossary lacks goes in the asks file's `words`, and `sheet` warns to add it to
  the glossary, so the meaning lives in one place.
- An item whose `id` is `<doc path>#Qn` enriches that §9 question. Its text, owner and BLOCKING flag
  come from the doc; the asks file cannot change them. When the doc's words lean on numbers, `plain`
  puts the question in plain words on the card, and the doc's own words show beside it ("In the doc:
  …"); the answer still goes under the doc's question. An id naming a question that is already
  answered is dropped, not invented.
- Any other item is a decision outside the docs: kind `question`, `approve`, `input`
  or `confirm`, with `text`. `group` names the heading it sits under.
- `options` follow the slate rules (`references/slates.md`): each label verbatim as it
  would be written, one **(Recommended)** at most, and `because` / `commits` / `think`
  for the three annotations, and `then`. The page adds "None of these — here's mine" itself.
- `detail` is Markdown: paragraphs, `-` lists, code spans, bold and `https` links. `code`
  is shown as a block (a diff, a command). `image` is a `data:image/` URI or an `https`
  URL (a diagram rendered to SVG or PNG). `links` is a list of `{label, url}`.
- **Accept all Recommended** fills the Recommended option, or the proposed value, for
  every open item under one heading. The human still saves.

The example in `examples/decisions/` shows every kind.

## 5. Write the answers back

```
python3 "${CLAUDE_SKILL_DIR}/scripts/decisions.py" apply <answers file> --by "<name>" [--dry-run]
```

It reads the page's JSON, or pasted text that holds it. Each answer to a doc question becomes one
line under that question in §9: `Answer (<date>, <name>): <text>`. §9 answers are appended, never
replaced (framework § Section rules), and apply never touches §0 or the Status line. An **Ask me
instead** appends a new BLOCKING §9 question for that agent decision, with the human's note as its
`Why asked` line, and sets the §8 row's `State: asked Qn`. Answers from the question prompt use the
same format. Write them as a `promise-answers` file and apply that, so both surfaces land the same
way:

```json
{"format": "promise-answers", "version": 1, "answers": [
  {"id": "docs/designs/channel-muting.md#Q1", "doc": "docs/designs/channel-muting.md",
   "q": "Q1", "value": "Muting a channel also mutes its threads"}]}
```

`forAgent` in its output lists the answers that name no doc question: approvals, values, to-dos. Act
on each one where it belongs, for example a §8 decision row or the task list, and say where each one
went. An answer that changes §0 is the human's to write. Show the answer, name the line it would
change, and leave the edit to them.

Close out with what was written, what was skipped and why, and the BLOCKING questions
still open.

## 6. A big backlog: research first

More open than one round holds: send research agents first (`references/research.md`).
