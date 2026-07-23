---
tags: [backend, api, python, fastapi, entrypoint]
sources: [backend/app/main.py]
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/main.py
blob: 1b9d87ecda01072b0c17bd9df5683f3e3ade6f19
commit: d9d860b47f2c78acb9ce7304f18c1e18cc370851
kind: code
applicability: active
---

# backend/app/main.py

**Role.** The ASGI application factory: builds the `FastAPI` instance, installs the subdomain [[Tenant Resolution]] middleware, parks the shared `AuthService` and login rate limiter on `app.state`, maps four domain exceptions onto deliberately uninformative JSON error bodies, and mounts the health and auth routers. `uvicorn app.main:app` is the process entrypoint used by the `Makefile`.

**Module.** [[backend/app/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `create_app` | fn | Builds and returns a configured `FastAPI`; takes an optional `resolver` override so tests can inject a fake [[backend/app/tenancy/middleware.py#TenantResolver]] instead of hitting Postgres |
| `app` | const | Module-level `create_app()` result — the ASGI callable Uvicorn imports |
| `lifespan` | fn | Async context manager that awaits [[backend/app/db/session.py#ensure_safe_database_role]] before serving the first request |
| `INVALID_CREDENTIALS_BODY` | const | 401 body shared by wrong-password and unknown-email |
| `TOO_MANY_ATTEMPTS_BODY` | const | 429 body for [[Rate Limiting]] rejections |
| `NOT_AUTHENTICATED_BODY` | const | 401 body for missing/expired/revoked/foreign sessions |

## Behavior

`create_app` reads the cached settings, constructs the app with `lifespan`, and — unless a resolver is injected — builds a `RepositoryTenantResolver` over the lazy session factory; because the engine is a lazy singleton, importing this module never opens a connection, which [[backend/tests/test_app_import.py]] enforces. `TenantResolutionMiddleware` is added first so every non-exempt request carries a resolved `TenantContext` before any route or auth dependency runs. A single `AuthService` and a single in-process `FixedWindowRateLimiter` (clocked by `time.monotonic`) live on `app.state`, so limiter buckets and the session factory are shared across requests rather than rebuilt per call. The four exception handlers are the security surface: `TenantNotResolvedError` → 404 with the *same* body as any other resolution failure (no distinguishable 404s that would confirm a slug exists), `InvalidCredentialsError` → 401 with one body for both wrong-password and unknown-email (no account enumeration), `RateLimitedError` → 429, `NotAuthenticatedError` → 401. The startup hook fails the process fast if the database role is a superuser or table owner, since either would silently bypass forced [[Row Level Security]].

## Depends On

- [[backend/app/core/config.py]] — `get_settings` for version, base domain, cookie/session/limiter knobs
- [[backend/app/db/session.py]] — lazy session factory and the startup role check
- [[backend/app/tenancy/middleware.py]] — middleware class, `TenantResolver` protocol, `TenantNotResolvedError`, shared 404 body
- [[backend/app/tenancy/resolver.py]] — default DB-backed resolver
- [[backend/app/auth/service.py]] — `AuthService`, `InvalidCredentialsError`
- [[backend/app/auth/router.py]] — auth routes and `RateLimitedError`
- [[backend/app/auth/dependencies.py]] — `NotAuthenticatedError`
- [[backend/app/auth/rate_limit.py]] — `FixedWindowRateLimiter`
- [[backend/app/api/routes/health.py]] — health router
- [[FastAPI]] — app, routing, exception handlers
- [[Uvicorn]] — ASGI server that imports `app`

## Depended On By

- [[backend/tests/test_health.py]]
- [[backend/tests/test_middleware.py]]
- [[backend/tests/test_auth_api.py]]
- [[backend/tests/test_tenancy_integration.py]]

## Concepts

- [[Tenant Resolution]]
- [[Owner Authentication]]
- [[Rate Limiting]]
- [[Row Level Security]]

## Tests

- [[backend/tests/test_app_import.py]] — import must not require a database or `DATABASE_URL`
- [[backend/tests/test_health.py]] — health route wiring
- [[backend/tests/test_middleware.py]] — resolution failures and exempt paths through the real app
- [[backend/tests/test_auth_api.py]] — login/logout/me over the app with an injected resolver and service
- [[backend/tests/test_tenancy_integration.py]] — end-to-end resolution against Postgres

## Notes

`app = create_app()` runs at import time, so anything added to `create_app` must stay database-free until `lifespan`. Spec and plan: [[.planning/specs/subdomain-routing.md]], [[.planning/specs/owner-auth.md]], [[.planning/plans/owner-auth.md]].
