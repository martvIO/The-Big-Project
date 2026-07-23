---
tags: [backend, python, config]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Pydantic Settings

**Purpose.** Environment-driven, type-validated application configuration.

Used in [[backend/app/core/config.py]]. Configuration fails fast at startup rather than at first use — see [[Fail Fast Configuration]]. The full variable list is documented in [[backend/.env.example]].
