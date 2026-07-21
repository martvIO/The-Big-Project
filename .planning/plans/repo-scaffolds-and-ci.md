# Plan: Repo Scaffolds & CI

**Branch**: `feature/repo-scaffolds-and-ci` · **Spec**: `../specs/repo-scaffolds-and-ci.md` · **Epic**: E1 · **Created**: 2026-07-21

Six tasks, dependency-ordered. TDD where testable (health endpoint, migration smoke); scaffold/config files are implement-then-verify per workflow rules. Local machine lacks Docker, so the Testcontainers smoke test is verified in CI; locally we verify the specced "clear error when Docker absent" behavior instead.

### Task 1 — Root hygiene & cleanup
Files: delete `Backend/**` (tracked empty placeholders), migrate `Frontend/App` → `frontend/apps/storefront`; add root `README.md`, `Makefile`, `.editorconfig`, `.gitattributes`; adjust `.gitignore` (un-ignore `.python-version`, keep `uv.lock`/`pnpm-lock.yaml` tracked).
Test: `git ls-files` shows no `Backend/` or `Frontend/`; grep finds no firebase/firestore references.

### Task 2 — Backend project (uv + FastAPI)
Files: `backend/pyproject.toml` (py 3.13; fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings; dev: pytest, pytest-asyncio, httpx, testcontainers, ruff, mypy), `backend/.python-version`, `backend/app/main.py` (factory), `backend/app/core/config.py`, `backend/app/api/routes/health.py`, `backend/app/worker.py` (stub loop), `backend/.env.example`, `backend/uv.lock`.
Test first: `tests/test_health.py` — `GET /health` → 200 `{status, version}`; snake_case JSON. Red → implement → green.

### Task 3 — DB harness (SQLAlchemy 2 + Alembic)
Files: `backend/app/db/session.py` (async engine/session factory), `backend/alembic.ini`, `backend/migrations/env.py` (async), baseline migration `0001` enabling `uuid-ossp`. No domain tables.
Test first: `tests/test_migrations.py` — Testcontainers Postgres: `alembic upgrade head` applies; `uuid_generate_v4()` callable.

### Task 4 — Test harness ergonomics
Files: `backend/tests/conftest.py` — session-scoped Postgres container fixture with Docker-availability pre-check that fails with an actionable message ("Docker/OrbStack required — see README"); pytest markers separating `unit` from `db` tests.
Test: locally (no Docker) `db` tests fail with the clear message, `unit` tests pass; CI runs both green.

### Task 5 — Frontend pnpm monorepo
Files: `frontend/pnpm-workspace.yaml`, `frontend/package.json` (packageManager pin), `frontend/tsconfig.base.json`, `apps/storefront` + `apps/manage` (Vite + React 19 + TS + Tailwind 4 + oxlint, placeholder pages), `packages/ui` (placeholder token export), `packages/api-client` (openapi-typescript generation script), `frontend/pnpm-lock.yaml`.
Test: `pnpm -r build`, `pnpm -r lint`, `pnpm -r typecheck` green; both apps render placeholder.

### Task 6 — CI (GitHub Actions)
Files: `.github/workflows/ci.yml` — backend job (setup-uv, `uv sync --locked`, ruff check + format check, mypy, pytest incl. Testcontainers), frontend job (pnpm setup, `--frozen-lockfile`, oxlint, typecheck, build), audit job (pip-audit + pnpm audit, warn-only).
Test: PR shows all checks; broken lockfile or TS error fails the run.

**Commits (batched)**: (1) cleanup + root files, (2) backend + db + tests, (3) frontend monorepo, (4) CI + planning docs.
