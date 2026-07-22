# Spec: Feature 7 — Owner Settings, Toggles & Structured Cancellation Policy (Epic E2)

**Created**: 2026-07-22 · **Revised**: 2026-07-22 (rev 2 — post six-critic verification pass) · **Status**: approved-for-build (pipeline continuation) · **Epic**: E2 Feature 7 (first E2 feature) · **Effort**: M
**Depends on**: E1 #5 (owner auth) — branches off `main` (E1 merged) · **Feeds**: E3 #12 (slot engine reads hours/types), E4 #19 (refund/forfeit evaluates the structured policy fields), E2 #10 (storefront renders profile/hours)

## Problem

A provisioned boutique is an empty shell: no profile, no opening hours, no appointment types, no cancellation policy, no toggles. Nothing downstream can exist without this configuration — the slot engine (E3) needs hours + types, the deposit flow (E4) needs machine-readable refund windows, and the storefront (E2 #10) needs a profile to render. The cancellation policy must be **immutable evidence**: what the customer accepted at booking time must be reconstructable forever (forfeiture disputes + PPL).

## Goal

The owner logs into `{slug}…/manage` and configures: boutique profile + v1 toggles, weekly hours with exception dates, appointment types (duration, audience, deposit), and a versioned cancellation policy. Each policy save creates a new immutable version combining terms text + structured refund fields. **An active terms version is required for ANY booking** (E3's forced terms acceptance is unconditional — bookings snapshot the accepted version id), so the manage console surfaces "no policy yet" as a setup blocker, not an optional section.

## Design

### Data (migration `0005`, copying `0003_auth.py`'s structure: `_STANDARD` columns — which **already include `tenant_id`** — `_updated_at_trigger`, per-table `GRANT` + `enable_tenant_rls` loop)

All four tables are tenant-scoped — the `test_every_tenant_id_table_has_forced_rls` metadata scan enforces FORCE RLS automatically. Domain bounds that feed E4's refund math get **CHECK constraints in the migration**, not just service validation (immutable financial evidence must be safe against any non-router write path).

- **`appointment_types`** — `name TEXT NOT NULL`, `duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0)`, `audience TEXT NOT NULL DEFAULT 'all'` (StrEnum `AppointmentAudience: all | brides_only`), `deposit_required BOOLEAN NOT NULL DEFAULT false`, `deposit_amount_agorot INTEGER NULL CHECK (deposit_amount_agorot IS NULL OR deposit_amount_agorot > 0)` (money in agorot — integer, never float), `sort_order INTEGER NOT NULL DEFAULT 0`. Partial unique `(tenant_id, name) WHERE deleted_at IS NULL`. Soft delete = archive (E3 bookings reference types by id + snapshot, so archiving never corrupts history).
- **`availability_rules`** — weekly recurring windows: `day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6)` (0=Sunday … 6=Saturday; Israeli week), `open_time TIME NOT NULL`, `close_time TIME NOT NULL` (close > open), **`capacity INTEGER NOT NULL DEFAULT 1 CHECK (capacity > 0)`** (parallel appointments per window — the ROADMAP's open capacity question resolved forward-compatibly; E3 #12 may refine semantics with the pilot, additively). Multiple windows per day; non-overlapping per day enforced in service.
- **`availability_exceptions`** — `date DATE NOT NULL`, `open_time TIME NULL`, `close_time TIME NULL` (both NULL = closed all day; both set = special hours; **exactly one set → 400**), `note TEXT NULL`. Partial unique `(tenant_id, date) WHERE deleted_at IS NULL`. **Known v1 limitation, intentional**: one window per exception date (regular weekdays support multiple windows; split-day special dates are out — documented for E3 #12 and pilot onboarding).
- **`terms_versions`** — **append-only, DB-enforced**: `version INTEGER NOT NULL CHECK (version > 0)`, `terms_text TEXT NOT NULL` (max 50 KB, service-enforced), `refundable_until_hours_before INTEGER NOT NULL CHECK (refundable_until_hours_before >= 0)`, `forfeit_percent INTEGER NOT NULL DEFAULT 100 CHECK (forfeit_percent BETWEEN 0 AND 100)` (% of deposit forfeited outside the window), `created_by UUID NOT NULL` (staff id). **Plain unique `(tenant_id, version)`** (no partial predicate — nothing is ever deleted). Grants: **`REVOKE ALL` then `GRANT SELECT, INSERT` only** (default privileges from 0002 give full CRUD — revoke first, the `0004` precedent). No UPDATE/DELETE possible ⇒ immutability is structural. SELECT is granted (unlike `platform_audit_log`) so `INSERT … RETURNING` and reads work. Current policy = max(version). No `updated_at` trigger.
- **Profile + toggles** — no new table. `tenants.name` stays the display name; profile (`phone`, `address`, `description`, `maps_url`) and toggles (`deposits_enabled: bool`, `brides_only: bool`) live in **`tenants.settings` JSONB** under `profile` / `toggles` keys. **`brides_only` semantics**: when true, the slot engine and storefront treat every appointment type as brides-only regardless of per-type `audience` (consumers: E3 #12/#13, E2 #10). Profile validation: `maps_url` must be an absolute `http(s)` URL (scheme allowlist — a `javascript:` URL here is stored XSS on the public storefront in F10), `phone` restricted to a phone-safe charset, max lengths on all fields (description ≤ 2000). The settings write is **one atomic SQL statement** — `UPDATE tenants SET settings = settings || :patch::jsonb WHERE id = :tenant_id AND deleted_at IS NULL` via a new `TenantsRepository.merge_settings` (platform-scoped repo pattern; `tenants` has no RLS) — never a Python read-modify-write, so concurrent writers of sibling settings keys (E4 #17/#20 will add them) are never clobbered. The id comes only from the server-side session (`staff.tenant_id`); the client never supplies it.

### Hardening delivered with this feature

- **`verify_database_role` extension** (consumed by F2's staging checks): also fail startup when `current_user` owns tables in `public` (a non-superuser *owner* connection passes the current superuser/BYPASSRLS check while silently voiding FORCE RLS's intent and every REVOKE-based guarantee, including `terms_versions` immutability).
- **CSRF defense-in-depth for the first cookie-authenticated mutating surface**: middleware on mutating `/manage` routes rejects requests whose `Origin` header (when present) does not match the request host (SameSite=Lax does not protect against same-site sibling subdomains once public tenant pages exist in F10). One middleware + tests.
- **No CORS**: the manage app is same-origin in production and uses a **Vite dev proxy** in development (below). CORS-with-credentials must never be added for the manage app.

### API (`app/boutique/` module: `router.py`, `schemas.py`, `service.py`; repositories in `app/db/repositories/`)

`APIRouter(prefix="/manage")`, registered in `create_app()`. Every route guarded by `get_current_staff` + `get_current_tenant`; tenant-scoped writes inside `tenant_session(session_factory, tenant.id)`. FastAPI-idiomatic verbs (house style):

- `GET /manage/settings` → profile + toggles. `PUT /manage/settings` → atomic merge of the two keys (validated Pydantic models, unknown keys rejected).
- `GET /manage/appointment-types` · `POST /manage/appointment-types` · `PATCH /manage/appointment-types/{id}` · `DELETE /manage/appointment-types/{id}` (soft).
- `GET /manage/availability` → rules + exceptions. `PUT /manage/availability/rules` → replace the full weekly set atomically **with per-tenant serialization** (`pg_advisory_xact_lock` keyed on tenant_id — two concurrent replaces under READ COMMITTED would otherwise both pass validation and union their sets): validate overlaps → soft-delete current → insert new, one transaction. `POST /manage/availability/exceptions` · `DELETE /manage/availability/exceptions/{id}` (soft).
- `GET /manage/terms` → current version + history (**last 50 + offset paging** — history is unbounded by design). `POST /manage/terms` → create next version (server assigns `version = max + 1`; unique index is the concurrency backstop — on `IntegrityError` the transaction is aborted, so the **retry opens a fresh `tenant_session`** and recomputes max there; second failure → 409). Modest per-tenant creation throttle reusing `FixedWindowRateLimiter` (spam on an irreversible write path is permanent bloat).

**Error shape**: a scoped `RequestValidationError` handler is added in `create_app()` emitting the house shape `{"error": {"code": "VALIDATION_ERROR", "message": …}}` with status 400 (this intentionally also normalizes malformed-body responses on the existing auth routes — consistent shape platform-wide). Domain rules enforced in the service map to house-shape 400s: duration ≤ 0, close ≤ open, overlapping windows, one-sided exception times, `deposit_required` without amount, forfeit outside 0–100, empty/oversized terms text, invalid `maps_url`/phone/lengths. **IntegrityError mappings**: duplicate active type name → 409 `DUPLICATE_NAME`; duplicate exception date → 409 `DUPLICATE_DATE`. Deposit-toggle interplay: `deposits_enabled=false` hides deposit behavior downstream but per-type fields stay stored (no destructive cascade).

### Frontend (`apps/manage`) — functional UI, restyled at F9's design gate

Replace the placeholder `App.tsx` with a minimal owner console: login gate (reuse `/manage/auth` — login form, `me` bootstrap, logout) and four sections: **Profile & toggles · Hours & exceptions · Appointment types · Cancellation policy** (with a prominent "no policy yet" setup-blocker state). Hebrew RTL, Tailwind v4 utility styling with the placeholder `@boutique/ui` tokens only (F9 owns the design system; this UI is deliberately plain).

- **Dev serving (first real FE↔BE integration — no precedent exists)**: Vite `server.proxy` forwards `/manage` and `/health` to `http://localhost:8000` **preserving the original Host header** (`changeOrigin: false`), so the app is developed at `http://{slug}.localtest.me:5173` and tenant resolution + host-only cookies work unchanged. README note included. No CORS anywhere.
- Data access: local typed `src/api.ts` fetch helper (`credentials: "include"`, snake_case wire types) — the OpenAPI-generated client wrapper stays F10 scope.
- Terms UX: the form always **creates a new version** (history read-only) — the UI never edits in place, mirroring the DB guarantee.
- **Frontend test bootstrap**: Vitest + Testing Library + jsdom in `apps/manage` (`test` script) + `pnpm -r --if-present test` in the CI frontend job and a matching `Makefile` target (local/CI parity). **Compatibility check before install**: `apps/manage` pins Vite 8 (rolldown) — pin a Vitest major verified against it, else use a standalone `vitest.config` that doesn't extend the app's Vite config; record the chosen versions in the plan.

## Out of scope

Slot generation/booking (E3 #12–13) · public storefront read endpoints (E2 #10) · per-item price visibility (E2 #8) · deposit charging (E4) · marketing-consent toggles (E4 #20) · **role gating — deferred to E6, and E6 MUST revisit every `/manage` mutation added here** (today all staff are owners by construction) · holiday auto-import (manual exceptions in v1) · design-system styling (E2 #9) · split-day exception dates (documented limitation).

## Edge cases

1. Two concurrent terms saves → unique `(tenant_id, version)`; loser retries once **in a fresh `tenant_session`** (aborted transaction cannot be reused), else 409.
2. `PUT /availability/rules` concurrent replaces → serialized by `pg_advisory_xact_lock(tenant_id)`; validation failures leave state untouched.
3. Soft-deleted appointment type: name freed for reuse (partial unique); archived type invisible in lists; history safe via E3 snapshots.
4. `deposit_required=true` with null/zero amount → 400. Amount on a `deposit_required=false` type is allowed-but-inert.
5. Cross-tenant probes: every new repository/endpoint gets an isolation test (tenant A cannot read/write B's rows — RLS + explicit predicate defense-in-depth).
6. Exception on a date with no weekly window (special opening) is valid — exceptions override the weekly grid in both directions; E3 consumes rules+exceptions with exceptions winning.
7. No terms version yet: `GET /manage/terms` returns empty history (not 404); booking-time enforcement (any booking requires an active version) lands in E3 #13; the F7 UI surfaces the setup blocker.
8. Settings write preserves unknown top-level keys **by construction** (atomic `||` merge at the SQL level) — verified by a concurrent-writer test, not just a sequential one.
9. Duplicate active type name / exception date → 409 with domain codes (IntegrityError mapped, never a raw 500).
10. Stored-XSS attempt via profile (`javascript:` maps_url, oversized description) → 400 at write time; F10 still escapes at render time (defense in depth).

## Testing

- Local (no Docker): schema/validation unit tests (bounds, overlaps, money, URL/phone/lengths); fast API tests with fake services + hardcoded `TenantContext` (`test_auth_api.py` style): wiring, 401s, validation 400s, 409 mappings, CSRF Origin-mismatch rejection, error-shape conformance; frontend Vitest for form logic + terms-versioning UX.
- CI (db): repository + service integration on real Postgres as `boutique_app` (`test_auth_integration.py` style): CRUD per table, advisory-locked weekly replace (explicit concurrency test), terms version race (fresh-session retry), **terms UPDATE/DELETE denied at the DB for `app_user`**, CHECK-constraint rejects, atomic settings merge preserving concurrent sibling keys, cross-tenant invisibility per new resource, `verify_database_role` table-ownership extension; migration `0005` exercised by `migrated_db`; the RLS metadata scan covers FORCE-RLS automatically.

## Dependencies

Backend: none new. Frontend: Vitest + @testing-library/react + jsdom (devDeps; `pnpm-lock.yaml` update — CI is `--frozen-lockfile`; Vite-8 compatibility verified first). Reuses: `enable_tenant_rls`, `tenant_session`, `get_current_staff`, `get_current_tenant`, `StandardColumns`, `0003`'s migration idioms, `FixedWindowRateLimiter`, error-handler pattern from `main.py`.
