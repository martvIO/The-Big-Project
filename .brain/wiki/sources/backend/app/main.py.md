---
tags: [backend, api, python, fastapi, entrypoint, media, csrf]
sources: [backend/app/main.py]
created: 2026-07-23
updated: 2026-07-27
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/main.py
blob: 78cb50cb54531d8a25e4df78a930aeca3e3bde0e
commit: e8fd318e17e17aefef55205facf914e60e3a0160
kind: code
applicability: active
---

# backend/app/main.py

**Role.** The ASGI application factory: builds the `FastAPI` instance, installs the CSRF-origin and subdomain [[Tenant Resolution]] middleware, parks the shared `AuthService`, `BoutiqueSettingsService`, `CatalogService`, `MediaStorage`, and rate limiters on `app.state`, maps the platform's domain exceptions onto deliberately uninformative house-shaped JSON error bodies, and mounts the health, auth, boutique-settings, and catalog routers. `uvicorn app.main:app` is the process entrypoint used by the `Makefile`.

**Module.** [[backend/app/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `create_app` | fn | Builds and returns a configured `FastAPI`; takes an optional `resolver` override so tests can inject a fake [[backend/app/tenancy/middleware.py#TenantResolver]] instead of hitting Postgres |
| `app` | const | Module-level `create_app()` result — the ASGI callable Uvicorn imports |
| `lifespan` | fn | Async context manager that awaits [[backend/app/db/session.py#ensure_safe_database_role]] before serving the first request |
| `INVALID_CREDENTIALS_BODY` | const | 401 body shared by wrong-password and unknown-email |
| `TOO_MANY_ATTEMPTS_BODY` | const | 429 body for [[Rate Limiting]] rejections (login, terms creation, and media presign all reuse it) |
| `NOT_AUTHENTICATED_BODY` | const | 401 body for missing/expired/revoked/foreign sessions |
| `*_BODY` (catalog/media) | consts | Fixed house-shaped bodies for `NOT_FOUND`, `DUPLICATE_NAME/DATE/SIZE`, `CONFLICT`, and the media `*` codes — no bucket/region/endpoint/IAM/AWS text ever reaches a user message |
| `_build_media_storage` | fn | Returns `S3MediaStorage` when `media_bucket` is set, else `UnconfiguredMediaStorage`; logs one INFO line so a typo'd `MEDIA_BUKCET` (silently dropped by `extra="ignore"`) is observable |
| `_validation_summary` | fn | Flattens the first 3 `RequestValidationError` locs into one string for the `VALIDATION_ERROR` body |

## Behavior

`create_app` reads the cached settings, constructs the app with `lifespan`, and — unless a resolver is injected — builds a `RepositoryTenantResolver` over the lazy session factory; because the engine is a lazy singleton, importing this module never opens a connection, which [[backend/tests/test_app_import.py]] enforces. Middleware order is load-bearing: `CsrfOriginMiddleware` is added *after* `TenantResolutionMiddleware` so that (Starlette runs middleware in reverse-add order) it runs *before* resolution — a cross-origin forgery is rejected without a database lookup. Four services now share `app.state`, each built over the lazy session factory: `AuthService`, `BoutiqueSettingsService` (with its own terms-creation `FixedWindowRateLimiter`), `CatalogService` (with a presign limiter and `PENDING_MEDIA_TTL_SECONDS`), and the `MediaStorage` chosen by `_build_media_storage`. `S3MediaStorage.__init__` does no network I/O and no credential resolution, which is what keeps `create_app()` callable in the fast suite.

The exception handlers are the security surface and grew from four to a full set. The originals stand: `TenantNotResolvedError` → 404 with the *same* body as any other resolution failure (no 404 confirms a slug exists), `InvalidCredentialsError` → 401 shared across wrong-password and unknown-email (no account enumeration), `RateLimitedError` → 429, `NotAuthenticatedError` → 401. New ones: `RequestValidationError` → **400** house shape platform-wide (FastAPI's default 422 is normalized away everywhere, auth routes included); the domain handlers bind to the *base* classes `DomainValidationError` (→400) and `DomainNotFoundError` (→404) from [[backend/app/errors.py]], deliberately **not** to concrete subclasses — Starlette resolves a handler by walking `type(exc).__mro__`, so binding to a leaf class would turn every sibling into an unhandled 500. Concrete conflict handlers map `DuplicateName/Date/Size`, `TermsVersionConflict`, and the media `Limit/NotUploaded/Mismatch/OrderMismatch` errors to 409; `TermsThrottled` and `MediaPresignThrottled` reuse the 429 body. Storage-layer `MediaNotConfiguredError` and `MediaStorageUnavailableError` → **503** (never 500): a bucket with no usable credentials is operationally identical to no bucket. The boutique router is included before the catalog router; both mount `prefix="/manage"`, so a duplicated path would silently shadow — the `ROUTES` table in [[backend/tests/test_catalog_api.py]] is what keeps that honest. The startup hook still fails the process fast if the database role is a superuser, `BYPASSRLS`, or a table owner, since any of the three silently bypasses forced [[Row Level Security]].

## Depends On

- [[backend/app/core/config.py]] — `get_settings`/`Settings` for version, base domain, cookie/session/limiter knobs, and all media + terms-throttle knobs
- [[backend/app/db/session.py]] — lazy session factory and the startup role check
- [[backend/app/tenancy/middleware.py]] — middleware class, `TenantResolver` protocol, `TenantNotResolvedError`, shared 404 body
- [[backend/app/tenancy/resolver.py]] — default DB-backed resolver
- [[backend/app/csrf.py]] — `CsrfOriginMiddleware`
- [[backend/app/errors.py]] — `DomainValidationError` / `DomainNotFoundError` base classes the handlers bind to
- [[backend/app/auth/service.py]] — `AuthService`, `InvalidCredentialsError`
- [[backend/app/auth/router.py]] — auth routes and `RateLimitedError`
- [[backend/app/auth/dependencies.py]] — `NotAuthenticatedError`
- [[backend/app/auth/rate_limit.py]] — `FixedWindowRateLimiter` (reused for terms + presign throttles)
- [[backend/app/boutique/router.py]] — `/manage` boutique-settings routes
- [[backend/app/boutique/service.py]] — `BoutiqueSettingsService` + its domain errors
- [[backend/app/catalog/router.py]] — `/manage` catalog routes
- [[backend/app/catalog/service.py]] — `CatalogService` + its domain/media errors
- [[backend/app/catalog/validation.py]] — `PENDING_MEDIA_TTL_SECONDS`
- [[backend/app/storage/base.py]] — `MediaStorage` protocol, `MediaNotConfiguredError`, `MediaStorageUnavailableError`
- [[backend/app/storage/s3.py]] — `S3MediaStorage`
- [[backend/app/storage/unconfigured.py]] — `UnconfiguredMediaStorage`
- [[backend/app/api/routes/health.py]] — health router
- [[FastAPI]] — app, routing, exception handlers, `RequestValidationError`
- [[Uvicorn]] — ASGI server that imports `app`

## Depended On By

- [[backend/tests/test_health.py]]
- [[backend/tests/test_middleware.py]]
- [[backend/tests/test_auth_api.py]]
- [[backend/tests/test_tenancy_integration.py]]
- [[backend/tests/test_boutique_api.py]]
- [[backend/tests/test_catalog_api.py]]

## Concepts

- [[Tenant Resolution]]
- [[Owner Authentication]]
- [[Rate Limiting]]
- [[Row Level Security]]
- [[Media Storage]]
- [[CSRF Origin Check]]

## Tests

- [[backend/tests/test_app_import.py]] — import must not require a database or `DATABASE_URL`
- [[backend/tests/test_health.py]] — health route wiring
- [[backend/tests/test_middleware.py]] — resolution failures and exempt paths through the real app
- [[backend/tests/test_auth_api.py]] — login/logout/me over the app with an injected resolver and service
- [[backend/tests/test_tenancy_integration.py]] — end-to-end resolution against Postgres
- [[backend/tests/test_boutique_api.py]] — `/manage` boutique-settings endpoints and their error bodies
- [[backend/tests/test_catalog_api.py]] — the `ROUTES` table guarding `/manage` catalog paths, media flows, and every catalog/media error body

## Notes

`app = create_app()` runs at import time, so anything added to `create_app` must stay database-free until `lifespan`. Spec and plan: [[.planning/specs/subdomain-routing.md]], [[.planning/specs/owner-auth.md]], [[.planning/plans/owner-auth.md]].
