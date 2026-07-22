# Spec: Feature 5 — Owner Auth (Epic E1)

**Created**: 2026-07-21 · **Status**: approved-for-build (pipeline continuation) · **Epic**: E1 Feature 5 · **Effort**: M
**Depends on**: Features 3+4 — stacked on `feature/subdomain-routing`

## Problem

Nothing protects management surfaces. Every E2+ feature (settings, catalog, bookings) needs an authenticated boutique owner whose session is cryptographically bound to exactly one tenant — a session minted at boutique A must be inert at boutique B, enforced by the same RLS layer that guards all tenant data.

## Goal

An owner logs in at `{slug}.{base}/manage/auth/login` with email+password; a host-only, HttpOnly session cookie authenticates subsequent requests on that subdomain only; failed logins are rate-limited and audit-logged; sessions expire, revoke on logout, and are **invisible across tenants at the database level**.

## Design

**Migration 0003** — three tenant-scoped tables, all secured via `enable_tenant_rls` (the Feature 3 metadata-scan test enforces this automatically):
- `staff_users`: `tenant_id`, `email`, `password_hash`, `display_name`, `role TEXT DEFAULT 'owner'` (owner-only in v1 — role model gets its first consumer in E6), standard columns; partial unique index `(tenant_id, email) WHERE deleted_at IS NULL`; `updated_at` trigger.
- `sessions`: `tenant_id`, `staff_user_id`, `token_hash`, `expires_at`, standard columns; index on `token_hash`.
- `audit_log`: `tenant_id`, `actor_id` (nullable), `action`, `entity` (nullable), `details JSONB`, standard columns — starts the Data Security Regs trail. Platform-level (CLI) audit gets its own non-tenant table in Feature 6.

**`app/auth/`** module:
- `passwords.py`: argon2id (argon2-cffi). `verify` against a **static dummy hash when the email is unknown** — login does constant-shape work, no timing enumeration.
- `rate_limit.py`: in-process fixed-window limiter (injectable clock), keyed by `(tenant, email)` and by client IP; limits from Settings (`login_max_attempts=5`, `login_window_seconds=900` — no magic numbers). Per-instance only; distributed limiting is the Feature 21 gate.
- `service.py`: login (verify → mint 256-bit token, store sha256 hash, TTL from `session_ttl_seconds`), logout (soft-revoke), current-staff lookup — all inside `tenant_session(...)` (new session-variant of the Feature 3 context helper), so RLS scopes every query.
- `router.py`: RPC-style under `/manage/auth` — `POST /login`, `POST /logout`, `GET /me`. snake_case JSON. **One generic 401 body for wrong-password and unknown-email** (`INVALID_CREDENTIALS`); `429 TOO_MANY_ATTEMPTS`; error envelope matches the tenancy `{"error": {code, message}}` shape via exception handlers.
- `dependencies.py`: `get_current_staff` — tenant (from middleware) + cookie → session lookup → `StaffContext` frozen dataclass; raises → handler returns generic 401.

**Cookie**: `boutique_session`, HttpOnly, SameSite=Lax, Path=/, **no Domain attribute** (host-only ⇒ exact-subdomain scoping), `Secure` outside dev.

**Out of scope**: owner creation UI (Feature 6 CLI provisions owners; tests seed directly), password reset (operator CLI, Feature 6), email flows, roles beyond `owner`, distributed rate limiting (F21), staff-facing audit viewer.

## Edge cases

1. Unknown email vs wrong password → identical 401 body + dummy-hash work.
2. Session replayed on another tenant's subdomain → 401 (RLS: row invisible under that tenant's context) — **the key isolation test**.
3. Expired / revoked (logged-out) session → 401.
4. 6th failed attempt inside the window → 429; window expiry restores access.
5. Soft-deleted or suspended... suspended tenant never reaches auth (middleware 404s); soft-deleted staff user → 401.
6. Cookie flags: HttpOnly + SameSite present, no Domain attribute ever.

## Testing

- Unit (local): password roundtrip + dummy verify; rate limiter windows with fake clock; 401/429 envelope + cookie-flag assertions via dependency-overridden app.
- DB (CI): migration applies + metadata scan proves forced RLS on all three tables; full login lifecycle on a tenant subdomain; cross-tenant cookie replay rejected; expiry/logout; rate-limit 429; audit rows recorded per tenant (login, login_failed, logout).

## Dependencies

argon2-cffi (new backend dep). No external services.
