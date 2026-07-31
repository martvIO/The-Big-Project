---
tags: [backend, auth, python, sessions, login, audit, tenancy, security]
sources: [backend/app/auth/service.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/auth/service.py
blob: 7c79a42fa65c36526a9f47bf03461b93d0ff33ed
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/auth/service.py

**Role.** Verifies staff credentials against `staff_users`, mints and stores a hashed session row, resolves a cookie back to a `StaffContext` on every request, and revokes on logout — writing a `LOGIN` / `LOGIN_FAILED` / `LOGOUT` audit row on every outcome, all inside a tenant-bound RLS session.

**Module.** [[backend/app/auth/_index]] · **Layer.** auth

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `StaffContext` | frozen dataclass | `id`, `tenant_id`, `email`, `display_name`, `role` — the authenticated principal passed to every `/manage` handler |
| `InvalidCredentialsError` | exception | Unknown email *or* wrong password — one type, so [[backend/app/main.py]] answers one 401 body |
| `AuthService` | class | Built once per app from a session factory and `Settings` |
| `AuthService.login` | async fn | `(StaffContext, plaintext_token)` on success, raises otherwise |
| `AuthService.resolve_session` | async fn | Token → `StaffContext` or `None`; re-reads `staff_users` every call |
| `AuthService.logout` | async fn | Revokes by token hash; audits only if a row was actually revoked |
| `_to_context` | fn | `StaffUser` row → `StaffContext` (drops `password_hash`) |

## Behavior

The single most important line in `login` is a *non*-line: the raise happens **outside** the `async with tenant_session(...)` block. `tenant_session` wraps the work in `session.begin()`, so raising inside it rolls the transaction back — and that would silently discard the `LOGIN_FAILED` audit row the failure just wrote. So the method computes an `outcome` variable, lets the transaction close and commit normally, and only then raises `InvalidCredentialsError`. Remove that shape and failed-login auditing quietly stops working with no test-visible error anywhere else.

Three branches share one exit. Unknown email calls `verify_password_dummy` so the path costs the same argon2 work as a real verify (no enumeration oracle — see [[backend/app/auth/passwords.py]]) and audits with the submitted address as `entity` but no `actor_id`. Wrong password audits with the `actor_id` filled in. Success mints a token via [[backend/app/auth/tokens.py]], stores only its SHA-256 with `expires_at = now + session_ttl_seconds` from [[backend/app/core/config.py]], and audits `LOGIN`. The plaintext token is returned to the caller and never persisted.

`resolve_session` is the hot path — it runs on every authenticated `/manage` request. It looks the session up by token hash *and* current time (expiry is a query predicate, not a background sweep), then re-reads the staff row by id. That second read is why role changes and deactivations take effect on the very next request without any session invalidation: `by_id` filters `deleted_at IS NULL`, so a deactivated staffer's live cookie resolves to `None` and becomes a 401. A live session whose staff row vanished returns `None` rather than a half-populated context.

`logout` revokes by token hash and audits **only if** `revoked` is truthy, so replaying a stale cookie does not manufacture phantom `LOGOUT` rows. Every method opens its own `tenant_session`, so forced RLS bounds every query to the calling tenant — a cross-tenant token is not rejected, it is invisible.

## Depends On

- [[backend/app/auth/passwords.py]] — `verify_password`, `verify_password_dummy`
- [[backend/app/auth/tokens.py]] — `generate_session_token`, `hash_token`
- [[backend/app/core/config.py]] — `session_ttl_seconds`
- [[backend/app/db/tenant.py]] — `tenant_session` (binds `app.tenant_id`, opens the transaction)
- [[backend/app/db/repositories/staff_users.py]] — `by_email`, `by_id`
- [[backend/app/db/repositories/sessions.py]] — `insert`, `active_by_token_hash`, `revoke_by_token_hash`
- [[backend/app/db/repositories/audit_log.py]] — `record`
- [[backend/app/models/constants.py]] — `AuditAction`
- [[backend/app/models/staff_user.py]] — the ORM row `_to_context` reads
- [[SQLAlchemy]] — async session factory (entity)

## Depended On By

- [[backend/app/main.py]] — constructs it onto `app.state.auth_service`, registers the `InvalidCredentialsError` 401 handler
- [[backend/app/auth/dependencies.py]] — `resolve_session` and `StaffContext` behind `get_current_staff`
- [[backend/app/auth/router.py]] — `login` / `logout`
- [[backend/app/auth/staff.py]] · [[backend/app/booking/owner.py]] · [[backend/app/boutique/router.py]] · [[backend/app/catalog/router.py]] · [[backend/app/booking/owner_router.py]] — consume `StaffContext` as the acting principal

## Concepts

- [[Owner Authentication]]
- [[Audit Trail]]
- [[Row Level Security]]
- [[Enumeration Resistance]]

## Tests

- [[backend/tests/test_auth_integration.py]] — real database: login success/failure, the audit rows each writes, session resolution and expiry, logout revocation
- [[backend/tests/test_auth_api.py]] — the HTTP surface against a fake service
- [[backend/tests/test_provisioning.py]] — logs in as the owner the provisioning CLI just seeded
- [[backend/tests/test_staff_management_db.py]] — asserts a password reset actually kills the target's other sessions

## Notes

`StaffContext` is frozen and deliberately carries no `password_hash`, so nothing downstream can leak one by accident. It is the type the whole `/manage` surface is written against — see [[backend/app/auth/dependencies.py#RoleGate]].

Design context: [[.planning/specs/owner-auth.md]].
