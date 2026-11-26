---
description: capability-new
tags: [test, capability]
runs: 3
max_turns: 60
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

/promise Capability: Channel pinning.
Outcome: a member can pin a channel so it stays at the top of their own channel list.
Why: busy members lose the channels they care about under dozens of others.
Rule: pinning never changes another member's list.
How we'll know: Ana pins #design, reloads, and #design is first in her list while Ben's list is unchanged.
Example: Ana pins #design; her list shows #design first; Ben's order stays as it was.
You may run the project's configured commands.
