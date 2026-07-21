# Spec: Feature 1 — Repo Scaffolds & CI (Epic E1)

## Context

First feature of the approved v1 roadmap (`.planning/epics/ROADMAP.md`). The repo currently holds only empty placeholders: `Backend/` is a 0-byte FastAPI-shaped skeleton with leftover Firebase/Firestore file names, `Frontend/App/` is a fresh npm Vite app. This feature replaces both with the real foundation every later feature builds on: a FastAPI backend project and a pnpm monorepo frontend, wired into CI. Decisions confirmed this session: **uv** for Python (pinned 3.13), **clean restructure** to `backend/` + `frontend/`, **Docker/OrbStack** locally for Testcontainers. On approval, this spec is saved to `.planning/specs/repo-scaffolds-and-ci.md` (Gate 1 passed) and built with TDD → security pass → review.

**Status**: draft · **Author**: team · **Epic**: E1 Platform Foundation · **Created**: 2026-07-21

---

## Problem

There is no runnable codebase — every later feature (tenancy+RLS, routing, auth) needs a project skeleton, a migration harness, a test harness that can exercise real Postgres, and a CI gate. Without a lockfile-based toolchain and CI from day one, dependency drift and untested merges poison the foundation the tenant-isolation guarantees depend on.

## Goal

`git clone` → documented bootstrap → `make dev` runs the API locally and `make test` passes against a real Postgres container; every PR runs lint + typecheck + tests + builds and blocks on failure. The empty placeholder tree is gone.

## User Stories

- As a **developer**, I clone the repo, follow README prerequisites (uv, pnpm via corepack, Docker/OrbStack), and have API + tests running in under 15 minutes, so feature work starts on rails.
- As a **reviewer**, every PR shows green lint/typecheck/test/build checks before merge, so foundation regressions can't land silently.

## Requirements

### Must-have

**Backend (`backend/`)**
- FastAPI app: `app/main.py` (app factory), `app/core/config.py` (pydantic-settings, `.env.example` only — never a real `.env`), `app/api/routes/health.py` (`GET /health` → `{status, version}`), router-per-domain layout ready for later features
- Worker entrypoint stub (`python -m app.worker`) — empty loop, the Feature 16 poller slots in later
- SQLAlchemy 2 + Alembic harness: async engine/session factory, baseline migration enabling `uuid-ossp` (no domain tables — `tenants` is Feature 3)
- uv project: `pyproject.toml` + committed `uv.lock`, Python pinned 3.13; ruff (lint+format), mypy, pytest configured
- Test harness: pytest + Testcontainers-Postgres session fixture that runs Alembic migrations; one smoke test proving migrate+connect; one TestClient test for `/health`

**Frontend (`frontend/`)**
- pnpm workspace (`pnpm-workspace.yaml`, corepack-pinned pnpm): `apps/storefront`, `apps/manage`, `packages/ui`, `packages/api-client`
- Apps: Vite + React 19 + **TypeScript** + Tailwind 4 (carried from `Frontend/App`), oxlint kept; each renders a minimal placeholder page and builds clean
- `packages/ui`: placeholder token export (real tokens arrive at Feature 9's design gate); `packages/api-client`: OpenAPI type-generation script against the backend's `/openapi.json`

**Repo & CI**
- Delete `Backend/` placeholders (incl. stray local `.venv/`, `.env`) and migrate `Frontend/App` → `apps/storefront`; root `README.md`, `Makefile` (bootstrap/dev/test/lint), `.editorconfig` (2-space, LF), `.gitattributes` (LF)
- GitHub Actions on PR + main: backend job (ruff, mypy, `uv sync --locked`, pytest w/ Testcontainers), frontend job (`pnpm install --frozen-lockfile`, oxlint, tsc, `pnpm -r build`), dependency audit (pip-audit, pnpm audit) non-blocking-warn initially
- `.gitignore` adjusted: ensure `uv.lock` is tracked (currently fine), keep `.env*` ignored with `!.env.example`

### Nice-to-have
- `make bootstrap` script that installs uv + enables corepack; PR template referencing the spec/gate workflow

### Out of scope
- Staging env, wildcard DNS/TLS, Grow + SMS applications (**Feature 2**) · tenants table/RLS (**Feature 3**) · any auth, domain logic, or real UI · deploy Dockerfiles/IaC (**Feature 2**) · Storybook, E2E/Playwright (arrives with real UI)

## Data Model

None — Alembic harness + `uuid-ossp` baseline migration only. House conventions (UUID/TEXT/TIMESTAMPTZ/soft-delete, no FKs) documented in the backend README section for later features.

## API Changes

`GET /health` → `200 {"status": "ok", "version": "<git sha or 0.1.0>"}` — the only endpoint. snake_case JSON convention configured globally from the start.

## UI Changes

None user-facing — placeholder pages proving each app builds and renders.

## Edge Cases

1. **Repo path contains spaces and `+`** (`Ryan + rawad + mrwen`) — all Makefile/scripts must quote paths; verify uv, pnpm, Vite, and Testcontainers tolerate it locally (CI clones to a clean path, so this is a local-dev hazard).
2. **Docker absent on a dev machine** — pytest fails fast with a clear "Docker/OrbStack required, see README" skip-with-error message instead of a cryptic Testcontainers stack trace.
3. **Lockfile drift** — CI uses `uv sync --locked` / `--frozen-lockfile` so an unlocked dependency change fails the build rather than silently floating.
4. **System Python is 3.14** — uv pins and fetches 3.13 regardless of system interpreter; CI uses the same pin.
5. **Stale placeholder imports** — nothing may reference the deleted `Backend/` names (firebase/firestore leftovers); grep-clean is part of done.

## Testing Criteria

- **Happy path**: fresh clone + README bootstrap → `make test` green locally (incl. Testcontainers smoke: container up → migrations apply → `uuid-ossp` present) and `make dev` serves `/health`; `pnpm -r build` green.
- **Edge**: pytest without Docker running → clear actionable error; `uv.lock` tampered → CI fails; TS type error in any app → CI fails; oxlint violation → CI fails.
- **CI proof**: open a scaffold PR — all four checks (backend, frontend, audits, build) visible and green; a deliberately broken commit on a branch shows red.

## Dependencies

None upstream (first feature). Local prerequisites documented: uv, corepack/pnpm, Docker Desktop **or** OrbStack/Colima. GitHub Actions available on the repo.

---

## Gate 1 checklist (all pass)

Problem specific ✓ · goal measurable ✓ · user stories ✓ · must/nice/out-of-scope split ✓ · data model N/A-with-reason ✓ · API follows conventions with example ✓ · ≥3 edge cases ✓ · happy+edge testing criteria ✓ · dependencies ✓

## Verification (end-to-end, after build)

1. `make bootstrap && make test` from a clean checkout on this machine (spaces-in-path proof included).
2. `make dev` → `curl localhost:8000/health` returns the JSON above; `/openapi.json` served; api-client generation script runs.
3. `pnpm -r build && pnpm -r lint` green; both apps render placeholders via `pnpm --filter storefront dev`.
4. Push a branch + PR → observe all CI checks green; verify branch protection can require them.

## On approval (execution steps beyond the code)

- Save this spec to `.planning/specs/repo-scaffolds-and-ci.md`; flip Feature 1 to `spec` in `.planning/epics/e1-platform-foundation.md` and proceed to `/spartan:plan`.
- Port the architecture/decision content of the earlier pressure-test plan into `.planning/architecture.md` so repo docs are self-contained (ROADMAP currently references a `~/.claude/plans/` file).
