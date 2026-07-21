# Architecture — Bridal Boutique Multi-Tenant SaaS

**Source**: approved pressure-test plan (2026-07-21), verified by three-critic pass. This is the standing architecture reference for all epics; per-feature specs live in `specs/`.

## Locked decisions

| Area | Decision |
|---|---|
| Stack | FastAPI (Python 3.13 via uv) + SQLAlchemy 2 + Alembic · React 19 + Vite + TypeScript + Tailwind 4 in a pnpm monorepo |
| Tenancy | Shared DB + `tenant_id` + **Postgres RLS forced** (non-owner app role, `SET LOCAL app.tenant_id` per transaction); schema/DB-per-tenant rejected at 50+ tenants |
| Routing | Wildcard `*.ourbrand.co.il`, host→tenant middleware (direct DB lookup in v1), reserved slugs, storefront on subdomain, staff app at `/manage`, cookies scoped to exact subdomain |
| Real-time | Pusher (managed), from E6. Sockets are hints, server is truth: versioned events + full-state refetch on reconnect |
| Payments | Grow (Meshulam) hosted payment page, per-tenant merchant accounts, **J4 charge not J5 hold**, PCI SAQ-A, webhook-authoritative |
| Comms | SMS-first (provider chosen by cost; sender-ID registration filed week 1); WhatsApp in E10; scheduled_messages table + poller worker (`FOR UPDATE SKIP LOCKED`), never "cron exactly 24h" |
| Waitlist race | Sequential offers with expiry cascade + atomic conditional-update claim + partial unique index on active bookings per slot |
| Identity | Customers per-boutique = (tenant, phone), OTP-verified at booking; owner/staff email+password; platform ops via audited CLI (v1) |
| i18n | RTL-first (he default; ar storefront strings in E10), i18next everywhere, CSS logical properties |
| Hosting | AWS il-central-1 (data residency), staging on Railway/similar; S3 tenant-prefixed media + signed URLs |
| Calendar | `.ics` links (E5); no 2-way sync |
| Compliance | Boutique = controller, platform = processor (DPA in ToS); PPL Amendment 13 in force; Data Security Regs medium level; Spam Law: separate unbundled marketing opt-in; IS 5568 (WCAG 2.0 AA) legally required; see `security-checklist-v1.md` |

## System shape

```
             *.ourbrand.co.il (wildcard DNS + cert)
                            │
        {slug}.…/ storefront   {slug}.…/manage staff app
                            │
              FastAPI modular monolith (API + worker modes)
              ├─ tenant-resolution middleware (host → tenant_id)
              ├─ auth realms: customer OTP / staff
              ├─ domain routers: catalog, booking, payments, comms, …
              └─ realtime events → Pusher (E6+)
                            │
   PostgreSQL 16 (RLS)   Redis (E5+)   S3+CDN media   Grow · SMS provider
```

- **Backend**: one deployable, router-per-domain; worker entrypoint runs pollers (scheduled messages, hold sweeper, offer cascade).
- **Frontend**: pnpm monorepo — `apps/storefront`, `apps/manage`, `packages/ui` (RTL design system), `packages/api-client` (OpenAPI-generated types).
- **DB conventions**: UUID PKs (`uuid-ossp`), TEXT not VARCHAR, TIMESTAMPTZ/UTC, soft delete (`deleted_at`) with a real PII-scrub path for PPL erasure, no FK constraints (app-level integrity), indexed `*_id` columns, partial indexes for active rows, snake_case JSON on the wire.

## Tenant-isolation defense in depth (the crown jewels)

1. Middleware binds tenant from hostname only — never from client input.
2. Every transaction: `SET LOCAL app.tenant_id`; RLS `FORCE`d on all tenant tables; app role is non-owner; unset context ⇒ zero rows.
3. Repository base injects tenant filter; no raw queries without tenant scope.
4. Tenant-prefixed S3 keys + signed URLs; tenant-scoped cache keys and (later) realtime channels.
5. **Permanent CI cross-tenant isolation suite** — probes every repository + endpoint as tenant A against tenant B; blocking, never removed.

## Core data model (v1; every tenant table: `id, tenant_id, created_at, updated_at, deleted_at`)

`tenants` (slug, status, settings JSONB) · `tenant_gateway_credentials` · `staff_users` · `customers` (phone unique/tenant, language, marketing_opt_in_at) · `dresses` + `dress_media` + `dress_variants` · `appointment_types` · `availability_rules`/`availability_exceptions` · `slots` · `bookings` (status, dress snapshot, terms_version_accepted, cancel_token_hash, attendance_confirmed_at; partial unique index on slot_id where active) · `terms_versions` (text + structured refund-window fields) · `payments` · `scheduled_messages` · `message_log` · `audit_log`. Later: waitlist/queue/staff/alteration tables per epics E5–E9.

## Test strategy (standing)

Tenant-isolation CI suite · unit (slot math, policy math, reminder math) · repository tests on real Postgres via Testcontainers (RLS must be real — SQLite would lie) · explicit concurrency/race tests (double-book, waitlist claim, duplicate webhooks) · API integration via TestClient (happy/401/cross-tenant-404/400) · Playwright E2E in Hebrew RTL + axe-core a11y · k6 load before multi-tenant onboarding (E5).
