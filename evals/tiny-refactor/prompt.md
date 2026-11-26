---
description: tiny-refactor
tags: [test, tiny]
runs: 3
max_turns: 60
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, Bash, Write, Edit]
---

/promise refactor app/checkout.py so total() uses a small helper for each line's amount. Its behaviour must not change. You may run the project's configured commands.
