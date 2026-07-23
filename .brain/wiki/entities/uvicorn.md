---
tags: [backend, python, server]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Uvicorn

**Purpose.** The ASGI server that runs the [[FastAPI]] app in development.

Invoked by the `dev` target in [[Makefile]] as `uvicorn app.main:app --reload --port 8000`.
