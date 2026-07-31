---
tags: [backend, db, repository, auth, sessions, python, sqlalchemy]
sources: [backend/app/db/repositories/sessions.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/sessions.py
blob: 0ded66074a9f0d8c9fb4f729a423195f6aad00cb
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/sessions.py

**Role.** Staff session rows: mint one for a login, resolve a live one from a cookie's token hash, revoke every session a staffer holds (optionally sparing the caller's own), and revoke a single session on logout.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `SessionsRepository` | class | The repository; no constructor state |
| `insert` | method | New `Session` for `(tenant_id, staff_user_id, token_hash, expires_at)` |
| `active_by_token_hash` | method | The one live, unexpired session for a token hash within a tenant |
| `revoke_for_staff_user` | method | Soft-deletes every live session of a staffer, minus `except_token_hash` |
| `revoke_by_token_hash` | method | Logout: soft-deletes one session; `True` iff a live row was hit |

## Behavior

`active_by_token_hash` is the request-path read — it filters `deleted_at IS NULL` **and** `expires_at > now`, so both revocation and expiry are one indistinguishable miss, and it carries an explicit `tenant_id` predicate beside RLS because session resolution is the cross-tenant boundary that matters most. `revoke_for_staff_user` exists specifically for **password change**: deactivating a staffer needs no session sweep because session resolution re-reads `staff_users` and a soft-deleted staffer 401s on her next request, but nothing on that path ever consults `password_hash`, so without this call the sessions the old password could have leaked would survive for the whole TTL. Its `except_token_hash` is what keeps the password-changing staffer logged in on her own device. It returns nothing — no caller wants the count. `revoke_by_token_hash` is deliberately **not** tenant-scoped in its predicate: it matches a token hash alone (RLS still confines it to the connection's tenant), and its `deleted_at IS NULL` guard makes a repeated logout answer `False` rather than re-stamping the timestamp. Only hashes are stored; the raw cookie value never reaches this table.

## Depends On

- [[backend/app/models/session.py]] — the `Session` ORM entity
- [[SQLAlchemy]] — `select` / `update` / `func`, `AsyncSession`

## Depended On By

- [[backend/app/auth/service.py]] — login mint, session resolution, logout
- [[backend/app/auth/staff.py]] — revokes on password change and on staff mutations

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Tenant Context]]

## Tests

- [[backend/tests/test_staff_service.py]]
- [[backend/tests/test_auth_integration.py]]
- [[backend/tests/test_auth_api.py]]

## Notes

Unlike its siblings this class carries no defence-in-depth docstring, but the tenant predicate is present on the two methods where it matters; `revoke_by_token_hash` leans on RLS alone by design, since a token hash is already a global-uniqueness-grade key. `expires_at` is stamped by [[backend/app/auth/service.py]] from `session_ttl_seconds` in [[backend/app/core/config.py]] — this file never computes a TTL.
