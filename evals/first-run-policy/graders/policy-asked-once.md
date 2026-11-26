---
type: llm
focus: trace
---
PASS if the agent puts the decision policy as one question in plain words with three answers (ask only the risky things, ask everything, move fast), marks "ask only the risky things" as recommended with a reason, and does not ask it a second time. FAIL if it never offers the choice, asks it more than once, uses the bare words `auto`, `spec` or `prototype` as the only labels, or offers a fourth policy.
