---
tags: [backend, python, validation]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Pydantic

**Purpose.** Request/response schema validation, used by [[FastAPI]] for automatic parsing and error responses.

Auth request and response shapes are in [[backend/app/auth/schemas.py]]. Application configuration uses the companion library [[Pydantic Settings]].
