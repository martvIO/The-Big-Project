# Boutique Platform

Multi-tenant SaaS for bridal & evening-wear boutiques in Israel. Hebrew-first (RTL), luxury storefronts on tenant subdomains, booking with deposits, and in-store operations tooling.

- **Backend**: FastAPI (Python 3.13, [uv](https://docs.astral.sh/uv/)) + SQLAlchemy 2 + Alembic + PostgreSQL (row-level security per tenant)
- **Frontend**: pnpm monorepo — React 19 + Vite + TypeScript + Tailwind 4 (`apps/storefront`, `apps/manage`)
- **Docs**: product roadmap in [.planning/epics/ROADMAP.md](.planning/epics/ROADMAP.md), architecture in [.planning/architecture.md](.planning/architecture.md)

## Prerequisites

| Tool | Install | Why |
|---|---|---|
| uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | Python 3.13 + locked backend deps |
| pnpm 10 | `npm install -g pnpm@10` | Frontend workspace |
| Docker Desktop / OrbStack / Colima | app install | Real Postgres in tests (Testcontainers) — DB tests fail fast with a clear error without it |

## Quickstart

```bash
make bootstrap    # uv sync + pnpm install
make test         # backend unit tests (fast, no Docker)
make test-db      # backend DB tests (needs Docker; runs migrations against real Postgres)
make dev          # run the API on :8000  →  curl localhost:8000/health
make fe-dev       # storefront dev server
make lint         # ruff + mypy + oxlint + typecheck
```

Backend env: copy `backend/.env.example` → `backend/.env` (never commit real `.env`).

**DB tests run as a non-owner role on purpose.** The test harness provisions a `boutique_app` login role (member of the `app_user` group from migration 0002) and runs the isolation suite as it — not as the container superuser. Superusers and table owners bypass row-level security unconditionally, so testing as one would make every isolation assertion vacuously pass. The suite asserts this about its own role, and the app refuses to start outside dev if its role could bypass RLS.

## Repo layout

```
backend/            FastAPI app, Alembic migrations, tests
frontend/
  apps/storefront/  customer-facing luxury storefront (tenant subdomain)
  apps/manage/      boutique owner/staff app ({slug}…/manage)
  packages/ui/      shared RTL design system (tokens land at the design gate)
  packages/api-client/  OpenAPI-generated types for the backend API
.planning/          specs, plans, epics, architecture — the working state of the project
.github/workflows/  CI: lint, typecheck, tests (real Postgres), builds, dependency audits
```

## Conventions

- DB: UUID PKs, `TEXT`, `TIMESTAMPTZ` (UTC), soft delete, **no FK constraints** — see `.planning/architecture.md`
- API: snake_case JSON on the wire; camelCase in TS/Python code
- Every PR must be green on CI; the cross-tenant isolation suite (from Feature 3 on) is blocking and permanent
