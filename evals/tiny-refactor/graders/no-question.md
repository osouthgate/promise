---
type: llm
focus: last_message
---
PASS if the reply says the change is made and does not wait on the user: it asks
nothing the user must answer before the work is done (the prompt already allows the
project's configured commands). An offer at the end ("say if you want X") is fine.
FAIL if it asks the user to confirm, choose or supply something, or says it wrote, or
needs, a design doc, spec or outcome doc for this change.
