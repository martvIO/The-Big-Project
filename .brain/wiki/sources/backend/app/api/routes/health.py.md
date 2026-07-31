---
tags: [backend, api, python, health, media, observability]
sources: [backend/app/api/routes/health.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/api/routes/health.py
blob: bd7b745919276d1676a8b572a17a25e08b97c301
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/api/routes/health.py

**Role.** The unauthenticated, host-agnostic liveness probe: answers `{status, version, media}` where `media` reports only *whether* a media bucket is configured — never which one.

**Module.** [[backend/app/api/routes/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `router` | `APIRouter` | Mounted at the app root by [[backend/app/main.py]]; no prefix |
| `HealthResponse` | class | `status` · `version` · `media` — a plain `BaseModel`, not a request model, so no `extra="forbid"` base |
| `MEDIA_CONFIGURED` / `MEDIA_UNCONFIGURED` | const | The two literal values `media` can take |
| `health` | fn | `GET /health` |

## Behavior

Reads `request.app.state.media_storage` — the [[backend/app/storage/base.py]] port that `create_app` chose at boot — and reports its `is_configured` flag; it never calls a storage network method, so the probe stays fast and cannot fail on an S3 outage. `version` comes from `get_settings().app_version`. The `media` field exists because `Settings` is `extra="ignore"`: a typo'd `MEDIA_BUKCET` env var is discarded in silence and a deployment with no bucket still boots (missing media is a *supported* deployment where upload endpoints answer 503, per [[backend/app/core/config.py]]), so staging needs a way to learn that before it attempts a presign. The response reports **state, never identity** — no bucket name, region or endpoint may appear, because this endpoint is unauthenticated and reachable by IP; `test_health_reports_media_configured_but_never_names_the_bucket` asserts the bucket string is absent from the whole body. `/health` is one of the `EXEMPT_PATHS` in [[backend/app/tenancy/middleware.py]], so an infra probe hitting the bare IP is not 404'd by tenant resolution.

## Depends On

- [[backend/app/core/config.py]] — `get_settings().app_version`
- [[backend/app/storage/base.py]] — the `MediaStorage` port and its `is_configured` flag
- [[FastAPI]] · [[Pydantic]]

## Depended On By

- [[backend/app/main.py]] — `include_router(health_router)`, included first
- [[backend/app/tenancy/middleware.py]] — names `/health` in `EXEMPT_PATHS`

## Concepts

- [[Tenant Resolution]]

## Tests

- [[backend/tests/test_health.py]] — `test_health_returns_ok_and_version`, `test_health_reports_media_unconfigured_without_a_bucket`, `test_health_reports_media_configured_but_never_names_the_bucket`
- [[backend/tests/test_middleware.py]] — `/health` answers without a resolvable tenant host
- [[backend/tests/test_staff_role_gating.py]] — uses `/health` as the unauthenticated control route

## Notes

There is no readiness variant and no database ping. Adding one would make the probe fail during a database blip and take the deployment down with it; the database-role backstop runs once at startup instead ([[backend/app/db/session.py#verify_database_role]]).
