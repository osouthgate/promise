# Research first — a big backlog of decisions

*Read by `references/decision-sheet.md` when more is open than one round holds.
`decisions.py triage` and `merge-research` do the mechanical parts.*

When more is open than one round holds, many questions need no person at all. The
code or docs may already settle one, another question may settle it, or it may be out
of date. `sheet` says so in its next step. Before building a sheet, send research agents
first, and say so in one line ("<n> open, <m> blocking: sending research agents
first"). The human can say to skip it:

1. **Packets.** `decisions.py triage --out <scratch>/research [--asks <asks.json>]`
   splits the open questions that research has not checked into packets of ten
   (`--size`), one doc at a time. It prints one prompt per packet.
2. **Research agents.** Start one agent per packet with its prompt: subagents, in
   parallel where the host allows, or one after another. Each sorts every question
   into one pile and writes `result-<n>.json`:

   | Pile | What the agent writes | What reaches the human |
   |---|---|---|
   | `answered` | the answer, why, and `path:line` evidence read this run | one "Checked by research" group, with one "Accept all" tap and each card with its evidence one fold down |
   | `same-as` | the open question that settles it | nothing of its own: the other question's answer is written under it too |
   | `stale` | why it no longer applies, with evidence | a card in the same group, offering to close it |
   | `needs-you` | plain words, why, what waits on it, and options with one Recommended | the rounds of twelve, BLOCKING first |

3. **Merge.** `decisions.py merge-research <scratch>/research --asks <asks.json>`
   checks each result and merges it into the asks file. An `answered` or `stale` result
   needs evidence at a file and line that exist. A `same-as` result needs another open
   question. A result that fails is rejected with its reason, and exit 1 lists them.
   To send those back to research, run `triage` again with the asks file and a new
   `--out` folder. Each run gets its own folder, and only questions research has not
   yet checked go out. Or leave them for the rounds.
4. **The sheet** is built as usual. The research group sits after the round, whatever
   its size, and `counts.researched` and `counts.settledTogether` say how much research
   took off the human.

A BLOCKING question keeps its own card in the round even when research answered it,
with research's answer as the Recommended option. Research never writes to a doc. Every answer still needs the human's yes, given in one
tap or card by card.
