# Start with one useful promise

Say `/promise help me get started with Promise`, or describe where you are
starting in your own words. The agent uses what you already said and asks
only for the answers that change your next step.

The default is a short conversation. If you prefer one visual page, the agent
can use Promise's existing decision sheet. [The example form](asks.json)
contains standalone interview questions for a user who has supplied no context.
It is sample content; a real sheet includes only unanswered questions.

To preview it from a scratch directory, use the absolute path to the skill
and this asks file:

```sh
python3 /path/to/promise/skills/promise/scripts/decisions.py sheet \
  --docs-home . --asks /path/to/promise/examples/onboarding/asks.json --out interview.html
```

Open `interview.html`. On a host with a Promise decision pane or Artifact,
the agent uses that same surface. The page's saved answers go through the
existing `decisions.py apply` path. These standalone questions return
answers for the agent; they create no outcome doc and authorise no setup.

## Worked conversations

These are scripted examples of the intended flow, not recorded user research.

| Starting point | What the user already said | First useful response | Result to review |
|---|---|---|---|
| Idea before code | “A member reserves equipment, and I want to plan it before building.” | “What should happen when two members request the last item?” Then ask for a success signal if still missing. | One reservation job, a concrete example and the remaining questions before a draft. |
| New project | “Start with uploading reports. Every submitted row must be accounted for. I will check a two-teacher batch.” | Carry the job, rule and example forward. Ask for the unresolved result of malformed input. | A draft upload outcome and any setup preview still needed. |
| Established product | “Refunds keep failing after the payment callback. Search is slow too.” | Recommend the refund journey for its recurring failures and money impact. Let the user choose or change the boundary. | A refund pilot covering request, callback and recovery, with gaps labelled. |
| Already using Promise | “The returns deadline changed. We already have a returns capability.” | Find that job and the deadline rule, then ask only for the changed expectation. | Extend or revise the existing capability, retaining its evidence. |
| Unsure where to start | “We have a big app and too much capability noise.” | Run Doctor read-only, then offer two candidate jobs from the user's context. | One selected improvement, with no conclusion drawn from capability count alone. |

A proposed workflow can be changed, skipped or paused. The confirmation says
what the next action would write. After that action is chosen, the agent
carries the answers into the existing mode.

For an existing product, the pilot's result labels the selected capabilities,
test run and entry points. Untested parts of that journey remain gaps. Other
features remain outside the assessment. Expand only after reviewing the pilot.
