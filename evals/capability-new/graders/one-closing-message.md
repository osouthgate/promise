---
type: llm
focus: last_message
---
PASS if the reply ends the work with one message that separates what needs the user
(or says nothing does), what the agent decided for them, and what was not checked, and
it did not stop to ask the user anything the ask already answered.
FAIL if it stopped to ask for the outcome, rules, signal, example or owner, or asked the
user to pick a decision policy, or has no account of what it decided for the user.
