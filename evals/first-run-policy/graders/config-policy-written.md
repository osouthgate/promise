---
type: llm
focus: result
---
PASS if `.claude/promise.config.json` exists and its `decisionPolicy` is `auto` (the run is non-interactive, so nobody answered), and the closing message lists the policy under "Decided for you" and says how to change it. FAIL if the config has no `decisionPolicy`, holds `prototype`, or the closing message does not mention the policy it chose.
