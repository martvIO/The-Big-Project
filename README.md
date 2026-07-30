<img src="assets/brand/modryn-mark.svg" alt="" width="72">

# MODRYN — Boutique Platform

Multi-tenant SaaS for bridal & evening-wear boutiques in Israel. Hebrew-first (RTL), luxury storefronts on tenant subdomains, booking with deposits, and in-store operations tooling.

**MODRYN is the platform's brand, not the boutiques'.** It appears on the owner console, the domain (`*.modryn.co.il`) and the SMS sender ID; a tenant storefront carries the boutique's own name and gets nothing from MODRYN but the favicon. Brand assets live in [`assets/brand/`](assets/brand/).

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

**Dress catalog (`/manage` API + the «שמלות» console tab)**: dresses carry a name, description, optional price (integer agorot) with a separate "show the price on the site" flag, a manual date-less `reserved` marker, and a catalog sort order. Stock is a per-dress size/quantity matrix replaced whole in one `PUT` (serialized per dress by an advisory lock), and `out_of_stock` is **derived from the variant rows, never stored** — zero variants means "no sizes defined yet", not "sold out". Delete is archive (`deleted_at`), and restore matches children on the archive stamp, so a photo deleted individually beforehand stays deleted. Photos go straight to object storage: the API mints a **presigned POST policy** pinning the exact key, the exact content type and an exact byte length, the browser posts the file itself, and a confirm step verifies the object's real content type and magic bytes before the row becomes visible. Storage keys are tenant-prefixed (`tenants/{tenant}/dresses/{dress}/media/{media}{ext}`) and reads are short-lived signed URLs served `Content-Disposition: attachment`. Routes: `GET/POST /manage/dresses`, `GET/PATCH/DELETE /manage/dresses/{id}`, `POST /manage/dresses/{id}/restore`, `PUT /manage/dresses/{id}/variants`, and `POST …/media/presign`, `POST …/media/{id}/confirm`, `DELETE …/media/{id}`, `PUT …/media/order`.

**Media storage is optional, and its absence is not an outage.** Six env names configure it — `MEDIA_BUCKET`, `MEDIA_REGION`, `MEDIA_ENDPOINT_URL`, `MEDIA_FORCE_PATH_STYLE`, `MEDIA_PRESIGN_MAX_PER_WINDOW`, `MEDIA_PRESIGN_WINDOW_SECONDS` (see `backend/.env.example`; **AWS credentials are deliberately not settings fields** — boto3 reads them from the process environment, so they never enter the config object or a `repr`). With **no `MEDIA_BUCKET` the app boots normally and the catalog is fully usable**: dress and variant CRUD, archive/restore, reorder and every read keep working, `MediaResponse.url` serialises as `null`, and only the three media write endpoints answer `503 MEDIA_NOT_CONFIGURED`. The console reads `media_uploads_enabled` off the dress detail and renders a calm "העלאת תמונות עדיין לא זמינה" notice instead of a broken uploader. `create_app()` logs which of the two states it is in at wiring time and `/health` reports `media` as `configured`/`unconfigured` (never the bucket name), because `Settings` ignores unknown keys and a typo'd `MEDIA_BUKCET` would otherwise degrade silently.

> **Deploying behind a proxy**: the per-IP login limit is OFF by default because `request.client.host` behind a load balancer is the proxy's IP (one global bucket). To enable it, terminate a single trusted proxy that appends `X-Forwarded-For`, run uvicorn with `--proxy-headers --forwarded-allow-ips=<lb-ip>`, and set `TRUST_FORWARDED_FOR=true`. The per-tenant+email limit (the real brute-force control) is always on and needs no proxy config.

**DB tests run as a non-owner role on purpose.** The test harness provisions a `boutique_app` login role (member of the `app_user` group from migration 0002) and runs the isolation suite as it — not as the container superuser. Superusers and table owners bypass row-level security unconditionally, so testing as one would make every isolation assertion vacuously pass. The suite asserts this about its own role, and the app refuses to start outside dev if its role could bypass RLS.

## Frontend dev workflow

The two apps share the origin `{slug}.localtest.me` in production (storefront at `/`, console at `/manage`) but are separate Vite servers in dev, so they need **separate ports**:

```bash
make dev                                 # backend API on :8000       (terminal 1)
cd frontend && pnpm --filter manage dev  # manage console  on :5173   (terminal 2)
make fe-dev                              # storefront      on :5174   (terminal 3)
```

Browse **`http://{slug}.localtest.me:5173`** for the console and **`:5174`** for the storefront (e.g. `http://bella.localtest.me:5174` after provisioning slug `bella`) — not plain `localhost`. Each Vite dev server proxies its API prefix (`/manage` for the console, `/storefront` for the storefront) plus `/health` to `http://localhost:8000` with `changeOrigin: false`, so the original `{slug}.localtest.me` Host header reaches the backend: tenant resolution and the host-only session cookie work exactly as in production. `allowedHosts: [".localtest.me"]` in each app's `vite.config.ts` is what lets Vite accept the subdomain Host at all — without it the proxy alone is not enough. Both apps are same-origin in production and proxied in dev; **CORS must never be added for either**.

Frontend unit tests: `make fe-test` (= `pnpm -r --if-present test`) — `apps/manage` and `apps/storefront` each run Vitest + Testing Library under jsdom via a standalone `vitest.config.ts`, no backend or browser required. CI runs the same command.

Browser end-to-end tests: `make e2e` (= build both apps, install Chromium, `pnpm e2e`) — Playwright + axe against `vite preview`, no backend required (the storefront specs stub `/storefront/*` with `page.route()`). CI runs this as a blocking job.

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
