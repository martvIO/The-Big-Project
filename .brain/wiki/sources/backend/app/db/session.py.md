---
tags: [backend, db, python, security, config]
sources: [backend/app/db/session.py]
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/session.py
blob: 21b8583c1938a8a04ba9c6c4b65529a4fe79c829
commit: d9d860b47f2c78acb9ce7304f18c1e18cc370851
kind: code
applicability: active
---

# backend/app/db/session.py

**Role.** Owns the process-wide async engine and session factory, and enforces the fail-fast guard that refuses to run against a database role capable of bypassing row-level security.

**Module.** [[backend/app/db/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `verify_database_role` | fn | Queries `pg_roles` for `current_user`; raises `RuntimeError` if the role is `rolsuper` or `rolbypassrls` |
| `ensure_safe_database_role` | fn | The when-to-check policy: runs `verify_database_role` on the shared engine unless `app_env == "dev"` |
| `get_engine` | fn | Lazily creates and memoises the singleton `AsyncEngine` (`pool_pre_ping=True`) |
| `get_session_factory` | fn | Lazily creates and memoises the singleton `async_sessionmaker` with `expire_on_commit=False` |

## Behavior

Both `_engine` and `_session_factory` are module-level globals created on first use, so importing this module does not open a connection — the engine URL comes from `Settings.effective_database_url` in [[backend/app/core/config.py]] at first call, and nothing is read from the environment until then. `verify_database_role` opens a plain connection and reads `rolsuper, rolbypassrls` for the connected role; either flag being true aborts startup, because Postgres RLS — including `FORCE` — is unconditionally bypassed by superusers and `BYPASSRLS` roles, so an over-privileged connection would void tenant isolation with **zero test failures**. `ensure_safe_database_role` centralises the exemption in one place so the web app and the CLI cannot drift: dev is skipped because local runs use the Postgres superuser, every other environment is checked. The `expire_on_commit=False` setting on the session factory is load-bearing, not cosmetic — [[backend/app/db/repositories/tenants.py]] returns ORM entities after their transaction commits and would otherwise raise `DetachedInstanceError`.

## Depends On

- [[backend/app/core/config.py]] — `get_settings()` for `effective_database_url` and `app_env`
- [[SQLAlchemy]] — `create_async_engine`, `async_sessionmaker`, `AsyncEngine`, `AsyncSession`
- [[PostgreSQL]] — the `pg_roles` catalog query is Postgres-specific

## Depended On By

- [[backend/app/main.py]] — calls `ensure_safe_database_role()` in the FastAPI lifespan, and `get_session_factory()` to build the tenant resolver and `AuthService`
- [[backend/app/cli.py]] — same guard + factory for the operator CLI entrypoint
- [[backend/app/db/repositories/tenants.py]] — documents `get_session_factory()` as the factory it expects

## Concepts

- [[Row Level Security]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_role_guard.py]] — `test_superuser_role_is_refused` (container superuser URL → `RuntimeError` matching "bypass row-level security") and `test_app_role_is_accepted` (the non-owner `boutique_app` role passes)
- [[backend/tests/test_app_import.py]] — asserts `import app.main` succeeds without eagerly constructing the engine

## Notes

The singletons are never reset. Tests that need a different URL build their own engine and `async_sessionmaker` (see the helpers in [[backend/tests/test_auth_integration.py]] and [[backend/tests/test_tenants_repository.py]]) rather than mutating these globals.

The role guard only matters because the application role is also a **non-owner** of its tables — table owners bypass non-`FORCE` RLS, which is why [[backend/migrations/versions/0002_tenants_app_role.py]] creates a separate `app_user` group role.
