---
tags: [backend, config, python, pydantic]
sources: [backend/app/core/config.py]
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/core/config.py
blob: 41757a8a08290ffc5ded5c73ff2d70000bc968a1
commit: d9d860b47f2c78acb9ce7304f18c1e18cc370851
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

## Behavior

Fields default to a working local setup — `app_env="dev"`, `base_domain="localtest.me"` (whose wildcard subdomains resolve to 127.0.0.1, so `{slug}.localtest.me` needs no `/etc/hosts` editing), `database_url=None`. Two `model_validator(mode="after")` hooks close the resulting production holes: outside `dev`, a missing `DATABASE_URL` raises rather than silently booting against localhost as superuser, and a `base_domain` still equal to `localtest.me` raises rather than 404-ing every request (no real host ends in `.localtest.me`). Auth knobs — `login_max_attempts=5`, `login_window_seconds=900`, `session_ttl_seconds=43200` — are read by [[backend/app/main.py]] when it builds the limiter and by [[backend/app/auth/service.py]] when it stamps session expiry. `trust_forwarded_for` defaults to `False` on purpose: behind a load balancer `request.client.host` is the proxy, so a per-IP bucket would be one global bucket that a small burst could use to 429 every tenant; the flag must only be turned on when exactly one trusted proxy appends `X-Forwarded-For`. `get_settings` is cached, so tests that need different values construct `Settings(...)` directly instead of mutating the environment.

## Depends On

- [[Pydantic Settings]] — `BaseSettings`, `SettingsConfigDict`, env/`.env` loading
- [[Pydantic]] — `model_validator`

## Depended On By

- [[backend/app/main.py]]
- [[backend/app/auth/router.py]]
- [[backend/app/auth/service.py]]
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
