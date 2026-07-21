# Spec: Feature 3 — Tenant Core + RLS Isolation Harness (Epic E1)

**Created**: 2026-07-21 · **Status**: approved-for-build (user directive: continue building) · **Author**: team · **Epic**: E1 Platform Foundation
**Depends on**: Feature 1 (scaffold) — built stacked on `feature/repo-scaffolds-and-ci`

## Problem

Nothing enforces tenant separation yet. Every later feature stores boutique data, and the platform's existential requirement is that no query can ever cross boutiques. Isolation must be a database-enforced guarantee with a permanent CI proof, not an application convention.

## Goal

The `tenants` table exists; a non-superuser application role is the only identity the app (and its tests) connect with; any tenant-scoped table gets RLS via one shared helper; and a CI suite proves — against real Postgres — that a connection with tenant A's context can never read or write tenant B's rows, and that no context means zero rows.

## User Stories

- As a **platform engineer**, when I add a tenant-scoped table in any later feature, I call one migration helper and inherit forced RLS with the standard policy — no bespoke security code.
- As a **boutique owner**, my catalog/customers/bookings are invisible to every other boutique even if application-layer filtering regresses, because the database itself refuses.

## Requirements

### Must-have
1. **Migration 0002**:
   - `update_updated_at()` trigger function (house rule: created once, reused by all tables).
   - `tenants` table per house DB rules: `id UUID PK DEFAULT uuid_generate_v4()`, `slug TEXT`, `name TEXT`, `status TEXT DEFAULT 'active'`, `settings JSONB DEFAULT '{}'`, `created_at/updated_at/deleted_at TIMESTAMPTZ`, **no FKs**; partial unique index `idx_tenants_slug_unique ON tenants(slug) WHERE deleted_at IS NULL`; `updated_at` trigger.
   - **`app_user` NOLOGIN group role** (idempotent): `USAGE` on schema, `SELECT/INSERT/UPDATE/DELETE` on all tables + default privileges for future tables. NOT superuser, NOT owner — RLS `FORCE` therefore binds it. (Security advisory (a) from Feature 1 review.)
2. **RLS helper** `app/db/rls.py`: `enable_tenant_rls(table_name)` returning the DDL trio — `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, policy `USING/WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)`. `missing_ok=true` ⇒ unset context yields NULL ⇒ **zero rows, not an error**.
3. **Tenant context** `app/db/tenant.py`: async helper that opens a transaction and sets the context via parameterized `SELECT set_config('app.tenant_id', :id, true)` (transaction-local, injection-safe); context never comes from client input (middleware wires it in Feature 4).
4. **Models** `app/models/`: SQLAlchemy 2 `Base` + `StandardColumns` mixin (id/created_at/updated_at/deleted_at) + `Tenant` mapped class matching migration exactly.
5. **TenantsRepository** `app/db/repositories/tenants.py`: `by_slug` (active only — `deleted_at IS NULL` and `status='active'` filtering), `insert`, `suspend` (status flip), `soft_delete`, `list_active`. Platform-scoped (tenants table itself has no tenant_id, no RLS).
6. **Config guard** (security advisory (b)): `app_env` setting (`dev` default); outside `dev`, missing `DATABASE_URL` fails startup fast instead of defaulting to localhost-as-superuser.
7. **Test harness upgrade**: fixtures create a `boutique_app` LOGIN role granted `app_user`, and an **app engine fixture that connects as that role** — DB tests exercising isolation run as the same (non-owner) principal production will use.
8. **Permanent CI isolation suite** `tests/test_tenant_isolation.py` (blocking from now on):
   - asserts the app role is neither superuser nor table owner (guards against vacuous-pass);
   - a probe table created *with the shared helper* seeded for tenants A+B: context A ⇒ only A's rows; context B ⇒ only B's; **no context ⇒ zero rows**;
   - write-path: with context A, inserting/claiming a row with `tenant_id = B` is rejected (`WITH CHECK`);
   - owner-bypass check: `FORCE` verified via `pg_class.relforcerowsecurity`.

### Nice-to-have
- `tests/test_tenants_repository.py`: insert/by_slug/suspend/soft-delete/slug-reuse-after-delete coverage.

### Out of scope
Host→tenant middleware + reserved slugs (**Feature 4**) · owner auth (**Feature 5**) · provisioning CLI (**Feature 6**) · any tenant-scoped domain tables (Features 7+ consume the helper) · Redis caching (E5).

## Data Model

`tenants` only (columns above). The RLS policy helper is defined here but first applied to real domain tables in Features 7-8; the isolation suite applies it to a probe table so the guarantee is proven now, not when catalog lands.

## API Changes

None — no new endpoints. (`/health` unchanged.)

## Edge Cases

1. Unset tenant context → queries return zero rows (never an error, never all rows).
2. Soft-deleted tenant: `by_slug` returns None; its slug is re-claimable (partial unique index).
3. Suspended tenant: row exists, `by_slug` (active) returns None — Feature 4 will serve 404.
4. Context set to a non-UUID string → `set_config` accepts only values we pass as `str(UUID)`; helper takes a `UUID` type so garbage can't reach SQL.
5. Tests accidentally running as superuser → suite fails on the explicit not-superuser assertion (vacuous-pass guard).

## Testing Criteria

- Happy: migration applies on real Postgres; isolation suite green under the `boutique_app` role; repository tests green; unit tests (config guard) green without Docker.
- Edge: all five cases above have explicit tests.
- CI: full pytest (unit + db) green on the stacked PR; local runs without Docker still get the actionable skip-error for db tests.

## Dependencies

Feature 1 scaffold (merged or stacked). No external services.
