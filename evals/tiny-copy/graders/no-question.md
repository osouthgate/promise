---
type: llm
focus: last_message
---
PASS if the reply says the change is made and does not wait on the user for anything
but one thing: a yes to run the project's configured commands (such as its tests),
asked after the change, is allowed. An offer at the end ("say if you want X") is fine.
FAIL if it asks the user to confirm, choose or supply anything else, or asks before
making the change, or says it wrote, or needs, a design doc, spec or outcome doc.
