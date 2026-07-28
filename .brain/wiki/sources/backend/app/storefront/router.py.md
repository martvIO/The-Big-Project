---
tags: [backend, storefront, python, fastapi, routing, public-api, rate-limiting]
sources: [backend/app/storefront/router.py]
created: 2026-07-27
updated: 2026-07-27
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storefront/router.py
blob: 77e56bc97acc7158850eb04b062f9fbc716e12a1
commit: c9b045a8b70028db0de520384cdecf68f9b34c74
kind: code
applicability: active
---

# backend/app/storefront/router.py

**Role.** The public storefront read API: three anonymous, tenant-scoped `GET`s (`/storefront/dresses`, `/storefront/dresses/{dress_id}`, `/storefront/boutique`) plus the pure mappers that project the manage services' frozen views onto the public wire models.

**Module.** [[backend/app/storefront/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `router` | const | `APIRouter(prefix="/storefront")` with `_no_store` + `_rate_limit` as router-level dependencies |
| `list_dresses` | route | `GET /storefront/dresses` — `offset` is the ONLY query param; page size pinned to `DRESS_LIST_DEFAULT_LIMIT` |
| `get_dress` | route | `GET /storefront/dresses/{dress_id}` — calls `CatalogService.get_dress(..., include_archived=False)` |
| `get_boutique` | route | `GET /storefront/boutique` — `tenant.name` + profile + hours |
| `public_price` | fn | The ONE place the price rule lives: `row.price_agorot if row.price_visible else None` |
| `public_dress` / `public_dress_detail` / `public_media` / `public_boutique` | fn | Module-level mappers, non-underscored so tests import and assert on them directly |
| `upcoming_exceptions` | fn | `[row for row in rows if row.date >= today]` — takes the clock as a parameter |
| `jerusalem_today` | fn | `datetime.now(ZoneInfo("Asia/Jerusalem")).date()` |
| `BOUTIQUE_TIMEZONE` | const | `ZoneInfo("Asia/Jerusalem")` |

## Behavior

**Why `prefix="/storefront"` and not a public corner of `/manage`.** [[backend/app/csrf.py]]'s `PROTECTED_PREFIX` is `/manage`, and any future edge rule (WAF, CDN policy, per-path rate rule) written against `/manage` must not accidentally cover — or exempt — anonymous traffic. It is deliberately **not** added to `EXEMPT_PATHS` in [[backend/app/tenancy/middleware.py]]: public is not host-agnostic, and an unresolvable host must 404 before a handler runs. There is **no auth dependency anywhere** — that is the feature, and [[backend/tests/test_storefront_api.py]] runs F8's authentication guard in reverse to keep a copy-paste from [[backend/app/catalog/router.py]] from quietly breaking it.

`_no_store` is set on the ROUTER, not per route: every dress response carries presigned GET URLs valid for `SIGNED_GET_TTL_SECONDS`, which are bearer material for their whole TTL. `_rate_limit` keys a `FixedWindowRateLimiter` on `f"sf:{tenant.id}:{ip}"` and is **skipped entirely** when `_client_ip` returns `None` — without a trusted proxy the key would collapse to a per-tenant bucket that a single anonymous visitor could use to 429 a boutique's whole storefront, which is strictly worse than no limiter. Every read records against the bucket (the limiter counts only what is explicitly recorded), because a *successful* list is exactly the request the bound exists to cap. Tripping it raises the existing `RateLimitedError` → the existing 429 `TOO_MANY_ATTEMPTS` handler; F10 adds zero error codes.

The list exposes no `limit` and no `search`, so one anonymous request can never mint 100 signed URLs; the envelope still returns `limit` so the client can page. The detail passes `include_archived=False`, which routes an archived id through `DressesRepository.by_id` → `CatalogNotFoundError` → the shared 404, indistinguishable from an unknown or a foreign id. `public_boutique` reads only the four keys the design renders out of the `tenants.settings` JSONB blob, so a key a later feature adds to `profile` cannot reach the public page by default, and `toggles` is not read at all.

## Depends On

- [[backend/app/storefront/schemas.py]] — every response model
- [[backend/app/catalog/service.py]] — `CatalogService`, `DressView`, `MediaView`
- [[backend/app/catalog/router.py]] — `get_catalog_service`
- [[backend/app/catalog/validation.py]] — `DRESS_LIST_DEFAULT_LIMIT`
- [[backend/app/boutique/service.py]] — `BoutiqueSettingsService`, `SettingsResult`, `AvailabilityResult`
- [[backend/app/boutique/router.py]] — `get_boutique_service`
- [[backend/app/auth/router.py]] — `RateLimitedError` and the `_client_ip` helper, reused verbatim
- [[backend/app/auth/rate_limit.py]] — `FixedWindowRateLimiter`
- [[backend/app/core/config.py]] — `get_settings().trust_forwarded_for`
- [[backend/app/tenancy/middleware.py]] — `get_current_tenant`, and `TenantContext.name` for the page heading
- [[backend/app/models/dress.py]], [[backend/app/models/availability.py]] — row types the mappers read
- [[FastAPI]] — `APIRouter`, `Depends`, `Query`

## Depended On By

- [[backend/app/main.py]] — includes the router and parks `storefront_rate_limiter` on `app.state`
- [[backend/tests/test_storefront_api.py]]
- [[backend/tests/test_storefront_isolation.py]]

## Concepts

- [[Tenant Resolution]]
- [[Tenant Isolation]]
- [[Rate Limiting]]
- [[Media Storage]]

## Tests

- [[backend/tests/test_storefront_api.py]] — the public-route table, the recursive forbidden-key walk, the pure mappers, and the limiter's skip/trip behaviour
- [[backend/tests/test_storefront_isolation.py]] — cross-tenant probes on a public surface as the non-owner `boutique_app` role

## Notes

`_rate_limit` carries a `ponytail:` comment naming its ceiling — in-process fixed window, single instance, no bucket eviction. Redis-backed distributed limiting is the F21 hardening gate. Spec: `.planning/specs/catalog-management.md`, the two "Note for F10" blocks.
