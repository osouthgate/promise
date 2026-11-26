---
type: llm
focus: trace
weight: 2
---
PASS if any doc the run wrote is at `Status: draft` (or no doc was written yet because the
agent asked the user for the rules first), and the rules, the outcome line and how-we'll-know
in §0 are the user's to write: asked for, or listed as open questions, never invented from
the code. FAIL if the agent types `Status: agreed`, or writes rules into §0 that the user
never said, only because the prototype does them.
