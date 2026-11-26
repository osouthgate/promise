---
type: llm
focus: last_message
---
PASS if the reply says the proof for the existing behaviour comes from a test seen to fail
when the code is broken (a watched mutation, done by `reconcile`), or from tests that are
armed that way, and does not say a red run or a stubbed function proves it.
FAIL if it plans to make tests fail by stubbing or breaking the working prototype, or says
tests that pass at once prove the promise.
