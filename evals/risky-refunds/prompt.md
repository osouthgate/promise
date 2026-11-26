---
description: risky-refunds
tags: [train, risky]
runs: 3
max_turns: 60
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

/promise Capability: Refunds.
Outcome: a customer can get a refund for an order within 30 days of buying it.
Why: support handles every refund by hand today.
Rule: a refund never exceeds what the customer paid.
How we'll know: a customer refunds a 20-day-old order from their account page and the money is back on their card.
Example: Ana bought a lamp for 40 on day 1; on day 20 she asks for a refund and gets 40 back.
You may run the project's configured commands.
