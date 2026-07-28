---
tags: [backend, config, python, pydantic, media]
sources: [backend/app/core/config.py]
created: 2026-07-23
updated: 2026-07-28
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/core/config.py
blob: 59893e5ae7caea8da4f747b23d4b511b1045ae10
commit: 3bf3795889113127f3fae36eb18e91a29ebe7fda
kind: code
applicability: active
---

# backend/app/core/config.py

**Role.** The single environment-backed settings object: database URL, platform base domain, session TTL, login rate-limit window, and the proxy-trust flag — with two boot-time validators that refuse to start a non-dev deployment that forgot `DATABASE_URL` or `BASE_DOMAIN`.

**Module.** [[backend/app/core/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Settings` | class | `BaseSettings` subclass reading env vars and `.env`, `extra="ignore"` |
| `get_settings` | fn | `lru_cache`d accessor — one `Settings` instance per process |
| `DEV_DATABASE_URL` | const | `postgresql+asyncpg://postgres:postgres@localhost:5432/boutique`, used only when `database_url` is unset |
| `Settings.secure_cookies` | property | `app_env != "dev"` — drives the cookie `Secure` flag |
| `Settings.effective_database_url` | property | `database_url` or the dev fallback |
| `Settings.media_*` | fields | Media storage identity (`media_bucket`, `media_region="il-central-1"`, `media_endpoint_url`, `media_force_path_style`) + presign throttle (`media_presign_max_per_window=60` / `media_presign_window_seconds=300`) |
| `Settings.terms_creation_*` | fields | Per-tenant terms-version throttle (`terms_creation_max_per_window=10` / `terms_creation_window_seconds=3600`) |
| `Settings.storefront_read_*` | fields | Per-tenant budget on anonymous storefront reads (`storefront_read_max_per_window=6000` / `storefront_read_window_seconds=60`) |
| `_require_usable_media_config` | validator | `model_validator(mode="after")` — a *wrong* media config aborts boot; a *missing* bucket does not |

## Behavior

Fields default to a working local setup — `app_env="dev"`, `base_domain="localtest.me"` (whose wildcard subdomains resolve to 127.0.0.1, so `{slug}.localtest.me` needs no `/etc/hosts` editing), `database_url=None`. Two `model_validator(mode="after")` hooks close the resulting production holes: outside `dev`, a missing `DATABASE_URL` raises rather than silently booting against localhost as superuser, and a `base_domain` still equal to `localtest.me` raises rather than 404-ing every request (no real host ends in `.localtest.me`). Auth knobs — `login_max_attempts=5`, `login_window_seconds=900`, `session_ttl_seconds=43200` — are read by [[backend/app/main.py]] when it builds the limiter and by [[backend/app/auth/service.py]] when it stamps session expiry. `trust_forwarded_for` defaults to `False` on purpose: behind a load balancer `request.client.host` is the proxy, so a per-IP bucket would be one global bucket that a small burst could use to 429 every tenant; the flag must only be turned on when exactly one trusted proxy appends `X-Forwarded-For`. `get_settings` is cached, so tests that need different values construct `Settings(...)` directly instead of mutating the environment.

Two feature areas added knobs here. **Media** fields carry deployment identity only — bucket, region, endpoint — never AWS credentials: `boto3` reads those from the process environment so they never enter this object or a repr. Product policy (byte caps, TTLs) lives once in [[backend/app/catalog/validation.py]], not here, so an operator cannot raise a limit in env while the DB `CHECK` and the frontend validator stay put. A third `model_validator(mode="after")`, `_require_usable_media_config`, mirrors the base-domain guard's "missing is fine, wrong is fatal" stance: a missing `media_bucket` is a supported deployment (upload endpoints answer 503), but a `media_endpoint_url` left set against production, a non-`https` endpoint outside dev, or `media_force_path_style` in production all abort startup — the endpoint override is a CI / S3-compatible seam that must never point real uploads elsewhere. The **terms** throttle knobs bound creation on the append-only `terms_versions` table (spam there is permanent bloat) and are read by [[backend/app/boutique/service.py]]; the presign throttle is read by [[backend/app/catalog/service.py]]. The **storefront** read-throttle knobs (F10) are read by [[backend/app/storefront/router.py]]'s `_throttle` dependency: a per-*tenant* runaway brake on the unauthenticated `/storefront` GETs, deliberately generous (~3000 first-paints/minute at 2 requests per first paint) so it cannot fire on organic traffic — per-IP keying is an F21 concern because it requires a trusted proxy chain.

## Depends On

- [[Pydantic Settings]] — `BaseSettings`, `SettingsConfigDict`, env/`.env` loading
- [[Pydantic]] — `model_validator`

## Depended On By

- [[backend/app/main.py]]
- [[backend/app/auth/router.py]]
- [[backend/app/auth/service.py]]
- [[backend/app/boutique/service.py]] — terms-creation throttle knobs
- [[backend/app/catalog/service.py]] — presign throttle knobs
- [[backend/app/storefront/router.py]] — storefront read-throttle knobs
- [[backend/app/storage/s3.py]] — media bucket/region/endpoint
- [[backend/app/db/session.py]]
- [[backend/app/api/routes/health.py]]

## Concepts

- [[Fail Fast Configuration]]
- [[Tenant Resolution]]
- [[Rate Limiting]]

## Tests

- [[backend/tests/test_config.py]] — validator behavior for each `app_env`, defaults, and `effective_database_url`
- [[backend/tests/test_auth_integration.py]] — constructs `Settings` directly to drive `AuthService`
- [[backend/tests/test_provisioning.py]]

## Notes

`backend/.env.example` documents the deployable variables. The runtime backstop for a still-misconfigured deployment is [[backend/app/db/session.py#verify_database_role]] at startup, not this file.
