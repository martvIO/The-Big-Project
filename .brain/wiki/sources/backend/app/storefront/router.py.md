---
tags: [backend, storefront, python, fastapi, routing, public-api, rate-limiting]
sources: [backend/app/storefront/router.py]
created: 2026-07-27
updated: 2026-07-29
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storefront/router.py
blob: 469c3c5cc407313e2e50ac87d7608376c7d32fb9
commit: 9507140f3d31cba691e762fc0ed89c9f738e912b
kind: code
applicability: active
---

# backend/app/storefront/router.py

**Role.** The public storefront read API: **six** anonymous, tenant-scoped `GET`s plus the pure projection functions that map `StorefrontService`'s frozen views onto the public wire models. Three are F10's catalog/identity reads (`/dresses`, `/dresses/{dress_id}`, `/boutique`); F12 added the booking grid (`/slots`, `/appointment-types`); F14 added the cancellation-policy read (`/terms`). Rewritten in the F10 spec-conformance pass (PR #15): it now fronts its own [[backend/app/storefront/service.py]] instead of `CatalogService`, and its throttle is per-tenant with its own error class.

**Module.** [[backend/app/storefront/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `router` | const | `APIRouter(prefix="/storefront")` with `_no_store` + `_throttle` as router-level dependencies |
| `list_dresses` | route | `GET /storefront/dresses` — `offset` (ge=0) and `limit` (ge=1, le=`STOREFRONT_LIST_MAX_LIMIT`) are the ONLY query params; no `search`, no `archived` |
| `get_dress` | route | `GET /storefront/dresses/{dress_id}` — archived/unknown/foreign ids are one indistinguishable 404 (`by_id` pins `deleted_at IS NULL`) |
| `get_boutique` | route | `GET /storefront/boutique` — `tenant.name` + six profile keys + hours + upcoming exceptions |
| `list_slots` | route | `GET /storefront/slots` — `from`/`to` are boutique-calendar dates, both bounds inclusive; `to < from` is a 400, not an empty list |
| `list_appointment_types` | route | `GET /storefront/appointment-types` |
| `get_terms` | route | `GET /storefront/terms` — the current policy; no published version is a 404 (**F14 D5**) |
| `get_storefront_service` | fn | Dependency reading `app.state.storefront_service` |
| `public_dress` / `public_dress_detail` / `public_boutique` / `public_dress_list` / `public_slots` / `public_terms` / `public_appointment_type` | fn | Module-level projections, non-underscored so tests import and assert on them directly |
| `_public_price` | fn | The ONE place the price rule lives: `row.price_agorot if row.price_visible else None` — a hidden price never leaves the process |
| `_throttle` | fn | Per-tenant read budget; raises `StorefrontThrottledError` |
| `NO_STORE` | const | `"no-store"` |

## Behavior

**Why `prefix="/storefront"` and not a public corner of `/manage`.** [[backend/app/csrf.py]]'s `PROTECTED_PREFIX` is `/manage`; a third `/manage` router would make path shadowing a three-way hazard; the dev proxy needs one unambiguous prefix; and any future edge rule (WAF, CDN policy, per-path rate rule) written against `/manage` must not accidentally cover — or exempt — anonymous traffic. It is deliberately **not** added to `EXEMPT_PATHS` in [[backend/app/tenancy/middleware.py]]: public is not host-agnostic, and an unresolvable host must 404 before a handler runs. There is **no auth dependency anywhere** — that is the feature, and [[backend/tests/test_storefront_api.py]] runs F8's authentication guard in reverse over the same route table. **No handler reads a cookie**: the storefront and console share the origin, so a test asserts a request carrying a valid owner cookie gets a byte-identical response to one carrying none. GET only — HEAD stays 405 deliberately (a HEAD would mint signed URLs and spend the read budget to return a discarded body).

`_no_store` is set on the ROUTER, not per route: every dress response carries presigned GET URLs valid for `SIGNED_GET_TTL_SECONDS` — bearer material for their whole TTL — and a route added later cannot forget the header. `_throttle` keys `app.state.storefront_rate_limiter` on `f"storefront:{tenant.id}"` — **per tenant, not per IP**, an honest trade: per-IP keying needs `trust_forwarded_for`, and behind an untrusted proxy `request.client.host` is the proxy, so an IP key would silently collapse to one bucket anyway. Every read records against the bucket via `record_failure` (the limiter's "successes never count" stance is right for a login form and wrong here — a *successful* list is exactly what the bound caps; without that line the limiter is inert). Tripping it raises `StorefrontThrottledError` — its own class, not auth's `RateLimitedError` — handled in [[backend/app/main.py]] as the shared 429 body. The window (`storefront_read_*` in [[backend/app/core/config.py]], default 6000/60s ≈ 3000 first-paints/minute) is sized so it cannot fire on organic traffic. It is a runaway brake, not a defence: in-process, single-instance, and it does not bound S3 egress — distributed limiting, per-IP keying and a WAF are the F21 hardening gate.

**This router is GET-only, and that is load-bearing rather than incidental.** E3's mutating public routes — OTP send/verify (F11) and booking create (F13) — live in *sibling* routers on the same `/storefront` prefix instead of here, so the no-auth / no-cookie / no-mutation contract above stays mechanically true. The cross-router shadowing guard in [[backend/tests/test_storefront_api.py]] covers the whole prefix, and its route table is **derived from the registered routes**, so a new public surface is automatically pulled into all five guard suites (no-auth, no-store, tenant-not-exempt, forbidden-key wire-walk, throttle-not-inert). Adding `/terms` to that hand-maintained literal set is deliberately manual: a new public surface **must fail one test on purpose** before it is allowed through.

The projections are the field allowlist in code. `public_dress`/`public_dress_detail` serialize `id`, `name`, `price_agorot` (already nulled by `_public_price` when hidden — the wire cannot distinguish "hidden" from "price null + visible", by design), `reserved`, cover/media, description (`or None`), and `sizes` as `{size_label, available}` — never `quantity`, never `out_of_stock`, never `sort_order` or timestamps. `public_slots` ships start times only — **neither `capacity` nor `remaining`** (see [[backend/app/storefront/schemas.py]] for why `remaining` was dropped: with nothing booked it equals `capacity` exactly, smuggling a fenced field past a key-based absence walk). `public_terms` builds field-by-field and never serializes the row, so `id`, `tenant_id`, `created_by` and the timestamps — operator provenance — cannot reach the wire. `public_boutique` reads exactly six keys out of the `tenants.settings` JSONB (`essence`, `description`, `phone`, `address`, `maps_url`, `instagram`), so a key a later feature adds to `profile` cannot reach the public page by default, and `toggles` is not read at all; each field goes through `.strip()` then an `""`-to-null collapse, because `""` is the wire's canonical cleared value and shipping it would render `<a href="tel:">` with no accessible name — a WCAG 2.4.4 failure, worst on the statutory הצהרת נגישות contact block. Upcoming-exceptions filtering and the Jerusalem clock live in [[backend/app/storefront/service.py]] / [[backend/app/storefront/validation.py]], not here.

## Depends On

- [[backend/app/storefront/schemas.py]] — every response model
- [[backend/app/storefront/service.py]] — `StorefrontService` and its frozen `Storefront*View` dataclasses
- [[backend/app/storefront/validation.py]] — `STOREFRONT_LIST_DEFAULT_LIMIT`, `STOREFRONT_LIST_MAX_LIMIT`, `StorefrontThrottledError`
- [[backend/app/catalog/service.py]] — `MediaView` (the signed-URL view type only; no service call)
- [[backend/app/auth/rate_limit.py]] — `FixedWindowRateLimiter` (type of the state-parked limiter)
- [[backend/app/tenancy/middleware.py]] — `get_current_tenant`, and `TenantContext.name`/`settings` for the boutique route
- [[backend/app/models/dress.py]] — `Dress` row type the price rule reads
- [[backend/app/models/appointment_type.py]] — `AppointmentType` row type
- [[backend/app/models/terms_version.py]] — `TermsVersion` row type `public_terms` projects
- [[backend/app/booking/slots.py]] — `Slot`, the engine's frozen view `public_slots` reads
- [[FastAPI]] — `APIRouter`, `Depends`, `Query`

## Depended On By

- [[backend/app/main.py]] — includes the router; parks `storefront_rate_limiter` and `storefront_service` on `app.state`
- [[backend/tests/test_storefront_api.py]]
- [[backend/tests/test_storefront_isolation.py]]

## Concepts

- [[Tenant Resolution]]
- [[Tenant Isolation]]
- [[Rate Limiting]]
- [[Media Storage]]

## Tests

- [[backend/tests/test_storefront_api.py]] — the public-route table run in reverse (no auth), key-absence assertions per forbidden field, cookie-invariance, the pure projections, throttle trip/429 body
- [[backend/tests/test_storefront_isolation.py]] — cross-tenant probes on a public surface as the non-owner `boutique_app` role
- [[backend/tests/test_storefront_validation.py]] — constants and error class
- [[backend/tests/test_storefront_integration.py]] — the three GETs against real Postgres

## Notes

`_throttle`'s docstring names its own ceiling — in-process fixed window, single instance, resets on deploy, no cross-replica aggregation; Redis-backed distributed limiting is F21. Spec: [[.planning/specs/storefront-browse.md]] (canonical; supersedes the two "Note for F10" blocks in [[.planning/specs/catalog-management.md]]). Plan: [[.planning/plans/storefront-browse.md]] — the conformance pass that produced this file's current shape.
