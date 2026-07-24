---
tags: []
sources: [<PATH>]
created: <DATE>
updated: <DATE>
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: <PATH>
blob: <GIT_HASH_OBJECT>
commit: <GIT_HEAD>
kind: code
applicability: active
---

# <PATH>

**Role.** One sentence: what this file exists to do.

**Module.** [[<PARENT_DIR>/_index]] · **Layer.** api | auth | db | models | tenancy | platform | worker | cli | test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `name` | fn / class / const | what it does |

## Behavior

2–6 sentences. Control flow, error paths, invariants, side effects. No line numbers.

## Depends On

- [[some/other/file.py]] — why
- [[Third Party Tool]] — why (entity)

## Depended On By

- [[some/caller.py]]

## Concepts

- [[Row Level Security]]

## Tests

- [[backend/tests/test_thing.py]]

## Notes

Gotchas, TODOs, links to [[.planning/specs/relevant-spec.md]].
