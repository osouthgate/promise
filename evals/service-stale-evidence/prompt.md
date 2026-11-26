---
description: service-stale-evidence
tags: [test, service]
runs: 3
max_turns: 60
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

/promise reconcile only the service evidence for CAP-1 using service-observations.json. Report what that assessment establishes now. You may run the project configured commands.
