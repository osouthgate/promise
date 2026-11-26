---
type: regex
target: { source: file, path: app/checkout.py }
pattern: "def (?!total\\b)\\w+\\("
---
A helper beside `total()` exists: the fixture has `total` alone.
