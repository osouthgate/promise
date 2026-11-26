---
type: regex
target: { source: file, path: db/schema.sql }
pattern: "^  email TEXT NOT NULL UNIQUE$"
flags: m
arm: both
weight: 2
---
A database column is a persisted contract: the schema still has `email`, whatever tool
could have changed it, until a person decides.
