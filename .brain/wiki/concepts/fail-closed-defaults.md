---
tags: [backend, security, design]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: n/a
---

# Fail Closed Defaults

**Purpose.** When something is missing or malformed, deny rather than allow.

Instances in this codebase:
- Missing [[Tenant Context]] yields zero rows, not every row — [[Row Level Security]]
- Slug parsing separates extraction from validation so a malformed slug is rejected rather than coerced — [[.memory/patterns/two-layer-fail-closed-parsing.md]]
- Configuration is validated at startup so a bad environment fails immediately — [[Fail Fast Configuration]]

The pattern is worth preserving explicitly, because the fail-open version of each of these looks almost identical in code.
