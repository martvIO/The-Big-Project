---
tags: [infra, testing]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Docker

**Purpose.** Container runtime. Required locally only for [[Testcontainers]] to run the `-m db` suite; the application itself is run directly via [[Makefile]] targets in development.
