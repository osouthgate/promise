---
description: service-conditions
tags: [train, service]
runs: 3
max_turns: 60
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

/promise Design search for chat history. The response-time target is below one second. A slower answer may be acceptable only when its quality improves, but we have not decided the hard ceiling, quality rubric, workload or observation window. Ask for those decisions without inventing them. You may run the project configured commands.
