---
tags: [backend, models, python, auth, session, sqlalchemy]
sources: [backend/app/models/session.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/models/session.py
blob: 60c8e135e86385a318b71236bef3525cb1d5eba4
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/models/session.py

**Role.** The server-side half of a staff login cookie — one row per live session, storing only the **hash** of the session token plus its owner and hard expiry, so a database read cannot reconstruct a usable cookie.

**Module.** [[backend/app/models/_index]] · **Layer.** models

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Session` | class | ORM mapping for `sessions`; `StandardColumns` + `Base`. No docstring — the shape *is* the documentation |
| `Session.tenant_id` | col | `UUID NOT NULL` — the RLS discriminator |
| `Session.staff_user_id` | col | `UUID NOT NULL` — the staffer this cookie authenticates. No FK, by house convention |
| `Session.token_hash` | col | `TEXT NOT NULL` — digest of the raw cookie value; the raw token exists only in the client's cookie |
| `Session.expires_at` | col | `TIMESTAMPTZ NOT NULL` — absolute cutoff, stamped from `session_ttl_seconds` at login |

## Behavior

The whole file is four column declarations; everything interesting is in the DDL and in [[backend/app/db/repositories/sessions.py]]. Session resolution is the hottest read in the authenticated API, and [[backend/migrations/versions/0003_auth.py]] gives it a *partial* index on `token_hash WHERE deleted_at IS NULL` so revoked rows never enter the scan; a second plain index on `expires_at` exists purely to make a future expired-session sweep cheap and is not on any request path today. Note the model carries no unique constraint on `token_hash` — collisions are prevented by the token's entropy, not by the schema.

Three columns are checked together on every request, never individually: the repository's `active_by_token_hash` requires `deleted_at IS NULL` **and** `expires_at > now`, so revocation and expiry are two independent kill switches and neither depends on the other running. That read also carries an explicit `tenant_id` predicate on top of FORCE RLS — this is the exact boundary where a leak would let a cookie minted for one boutique authenticate against another, so it is the one place the redundancy is most deliberate. Logout and "sign out my other devices" are both **soft** deletes (`revoke_by_token_hash`, `revoke_for_staff_user`), which is why the row survives revocation and why every read must filter `deleted_at`; `revoke_for_staff_user` deliberately excludes the caller's own cookie so a password change does not log the actor out of the tab they are using.

## Depends On

- [[backend/app/models/base.py]] — `Base`, `StandardColumns`
- [[SQLAlchemy]] — declarative mapping

## Depended On By

- [[backend/app/db/repositories/sessions.py]] — the only repository over this table
- [[backend/app/auth/service.py]] — mints a session at login, revokes at logout
- [[backend/app/auth/staff.py]] — revokes a staffer's other sessions on password reset / deactivation

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Tenant Context]]

## Tests

- [[backend/tests/test_auth_integration.py]] — login → cookie → authenticated request against a migrated database
- [[backend/tests/test_staff_service.py]] — session revocation on password reset and deactivation
- [[backend/tests/test_tenant_isolation.py]] — `sessions` is one of the three tables 0003 puts under forced RLS

## Notes

`staff_user_id` has no foreign key — the house convention is no FK constraints anywhere, so a session pointing at a soft-deleted staffer is structurally possible and is closed in application code (the staff service revokes sessions when it deactivates a user), not by the database.

Design context: [[.planning/specs/owner-auth.md]], [[.planning/plans/owner-auth.md]].
