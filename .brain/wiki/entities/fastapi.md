---
tags: [backend, python, framework]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# FastAPI

**Purpose.** The ASGI web framework this backend is built on. Routers, dependency injection, and Pydantic-backed request/response validation.

Entry point is [[backend/app/main.py]]. Route modules live under `backend/app/api/routes/`; auth routes are in [[backend/app/auth/router.py]]. Dependency-injection helpers that enforce authentication and tenant scope are in [[backend/app/auth/dependencies.py]].

Served in development by [[Uvicorn]] via `make dev`.
