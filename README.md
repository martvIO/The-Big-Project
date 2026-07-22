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
make fe-test      # frontend unit tests (Vitest, no backend needed)
make lint         # ruff + mypy + oxlint + typecheck
```

Backend env: copy `backend/.env.example` → `backend/.env` (never commit real `.env`).

**Tenant subdomains in dev**: the API resolves boutiques from the hostname. `*.localtest.me` resolves to `127.0.0.1`, so after inserting a tenant with slug `bella`, browse `http://bella.localtest.me:8000/` — no `/etc/hosts` editing. Unknown, suspended, deleted, and reserved subdomains all return the same generic 404. `BASE_DOMAIN` env sets the real platform domain in staging/production.

**Owner auth**: owners log in at `{slug}.{base}/manage/auth/login` (email+password → argon2id). The session cookie `boutique_session` is HttpOnly, SameSite=Lax, and **host-only (no Domain attribute)** — a session minted at boutique A is never sent to boutique B, and even a copied token fails there because RLS makes the session row invisible under another tenant's context. Failed logins are rate-limited and every attempt (including failures) is committed to the per-tenant `audit_log`. Owner accounts are provisioned by the operator CLI (below).

**Provisioning tenants (operator CLI)**: onboarding is done over SSH/CI, not a web console. `python -m app.cli provision --slug bella --name "Bella Bridal" --owner-email owner@bella.example` creates the tenant + its first owner atomically (the owner can log in immediately); the **password is read from stdin/getpass, never an argv** (which would leak into the process list). Other commands: `suspend --slug`, `reset-password --slug --owner-email`, `list`. Every state change is written to `platform_audit_log` — a **platform-scoped** table (column `target_tenant_id`, deliberately not `tenant_id`, so it stays cross-tenant-readable and isn't caught by the forced-RLS metadata scan). `--operator` (default `$USER`) labels the audit row.

**Owner settings (`/manage` API)**: once logged in, the owner configures the boutique — profile + v1 toggles (`deposits_enabled`, `brides_only`; stored under `tenants.settings` JSONB and written with a single atomic SQL merge so concurrent writers of sibling keys never clobber each other), weekly opening hours with per-window capacity plus per-date exceptions (closed all day or special hours), appointment types (duration, audience, deposit in integer agorot; delete = archive, so booking history stays intact), and a **versioned cancellation policy**: each save creates a new immutable version combining terms text with machine-readable refund fields (`refundable_until_hours_before`, `forfeit_percent`). The `terms_versions` table is append-only at the database level (UPDATE/DELETE revoked from the app role), so what a customer accepted at booking time is reconstructable forever. The API surface is `GET/PUT /manage/settings`, `GET/POST/PATCH/DELETE /manage/appointment-types[/{id}]`, `GET /manage/availability` + `PUT /manage/availability/rules` (atomic full-replace of the weekly set, serialized per tenant by an advisory lock) + `POST/DELETE /manage/availability/exceptions[/{id}]`, and `GET/POST /manage/terms` (history paginated, 50 per page) — every route requires the session cookie and is tenant-scoped under RLS; mutations additionally pass an Origin-vs-Host CSRF check, and all errors use the house shape `{"error": {"code", "message"}}`. An active terms version is required for any booking (enforced in E3), so the manage console surfaces "no policy yet" as a setup blocker rather than an optional section.

> **Deploying behind a proxy**: the per-IP login limit is OFF by default because `request.client.host` behind a load balancer is the proxy's IP (one global bucket). To enable it, terminate a single trusted proxy that appends `X-Forwarded-For`, run uvicorn with `--proxy-headers --forwarded-allow-ips=<lb-ip>`, and set `TRUST_FORWARDED_FOR=true`. The per-tenant+email limit (the real brute-force control) is always on and needs no proxy config.

**DB tests run as a non-owner role on purpose.** The test harness provisions a `boutique_app` login role (member of the `app_user` group from migration 0002) and runs the isolation suite as it — not as the container superuser. Superusers and table owners bypass row-level security unconditionally, so testing as one would make every isolation assertion vacuously pass. The suite asserts this about its own role, and the app refuses to start outside dev if its role could bypass RLS.

## Frontend dev workflow (manage app)

```bash
make dev                                 # backend API on :8000 (terminal 1)
cd frontend && pnpm --filter manage dev  # Vite dev server on :5173 (terminal 2)
```

Browse **`http://{slug}.localtest.me:5173`** (e.g. `http://bella.localtest.me:5173` after provisioning slug `bella`) — not plain `localhost`. The Vite dev server proxies `/manage` and `/health` to `http://localhost:8000` with `changeOrigin: false`, so the original `{slug}.localtest.me` Host header reaches the backend: tenant resolution and the host-only session cookie work exactly as in production. `allowedHosts: [".localtest.me"]` in `apps/manage/vite.config.ts` is what lets Vite accept the subdomain Host at all — without it the proxy alone is not enough. The manage app is same-origin in production and proxied in dev; **CORS must never be added for it**.

Frontend unit tests: `make fe-test` (= `pnpm -r --if-present test`) — `apps/manage` runs Vitest + Testing Library under jsdom via a standalone `vitest.config.ts`, no backend or browser required. CI runs the same command.

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
