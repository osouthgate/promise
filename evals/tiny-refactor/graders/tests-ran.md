---
type: tool_used
tool: Bash
input_match: 'unittest|adapter\.py.{0,4}\s+(--json\s+)?verify'
---
The project's tests ran, directly or through `adapter.py verify` (whose path the agent
quotes, so the JSON input holds `adapter.py\" verify`).
