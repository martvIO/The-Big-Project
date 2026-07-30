---
tags: [backend, api, python, fastapi, entrypoint, media, csrf, sms, booking]
sources: [backend/app/main.py]
created: 2026-07-23
updated: 2026-07-30
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/main.py
blob: 881d0b40858bd2037c8a4e94fb52bd557914294f
commit: ac70f3d6a500bbf9edde55cd38fb9e2354d8c693
kind: code
applicability: active
---

# backend/app/main.py

**Role.** The ASGI application factory: builds the `FastAPI` instance (API docs/schema dark outside dev), installs the security-headers, CSRF-origin and subdomain [[Tenant Resolution]] middleware, parks the shared `AuthService`, `BoutiqueSettingsService`, `CatalogService`, `StorefrontService`, `NotificationService`, `OtpService`, `BookingService`, `BookingCommsService`, `ManageBookingService`, `MediaStorage` and `SmsSender` on `app.state`, wires **ten** `FixedWindowRateLimiter` instances (two parked on `app.state` — login and storefront — and eight handed to the services that own their budget), maps the platform's domain exceptions onto deliberately uninformative house-shaped JSON error bodies, and mounts the health, auth, boutique-settings, catalog, public storefront, OTP and booking routers. `uvicorn app.main:app` is the process entrypoint used by the `Makefile`.

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
| `*_BODY` (SMS/OTP/booking) | consts | Fixed bodies for `SMS_NOT_CONFIGURED`, `SMS_UNAVAILABLE`, `OTP_INVALID`, `OTP_EXPIRED`, `PHONE_NOT_VERIFIED`, `SLOT_UNAVAILABLE`, `TERMS_STALE` — no provider name, account id or provider text ever reaches a user message |
| `BOOKING_LINK_INVALID_BODY` | const | F16 — **one** body for unknown, rotated *and* malformed manage tokens |
| `BOOKING_ALREADY_STARTED_BODY` / `BOOKING_CANCELLED_BODY` | consts | F16 — the two states where the link resolves but the action is refused |
| `NOT_AUTHORIZED_BODY` | const | F31 — 403 for a live session whose **role** is not admitted. **One** body for every unadmitted role, so a probe cannot learn which roles exist |
| `BOOKING_TRANSITION_INVALID_BODY` | const | F15 — 409 covering an illegal status pair, a no-show before the appointment, and a cancel after it (D19) |
| `CUSTOMER_ALREADY_BOOKED_BODY` | const | F15 — 409 when a reschedule target, or a phone-correction re-point, would put one customer at two live bookings on one instant (0009's index) |
| `_build_media_storage` | fn | Returns `S3MediaStorage` when `media_bucket` is set, else `UnconfiguredMediaStorage`; logs one INFO line so a typo'd `MEDIA_BUKCET` (silently dropped by `extra="ignore"`) is observable |
| `_build_sms_sender` | fn | Mirrors `_build_media_storage`: `FakeSmsSender` when `sms_provider == "fake"`, else `UnconfiguredSmsSender` (OTP send answers 503). Logs one INFO line for the same `extra="ignore"` reason |
| `_validation_summary` | fn | Flattens the first 3 `RequestValidationError` locs into one string for the `VALIDATION_ERROR` body |

## Behavior

`create_app` reads the cached settings, constructs the app with `lifespan`, and — unless a resolver is injected — builds a `RepositoryTenantResolver` over the lazy session factory; because the engine is a lazy singleton, importing this module never opens a connection, which [[backend/tests/test_app_import.py]] enforces. Since F10 the constructor also passes `docs_url`/`redoc_url`/`openapi_url` as `None` unless `app_env == "dev"`: F10 made the origin publicly crawlable, and `/openapi.json` is a complete uncredentialed description of every `/manage` route and of exactly the fields the storefront allowlist fences off — pulled forward from the F21 hardening gate because F21 lands after the pilot is public. Middleware order is load-bearing: `CsrfOriginMiddleware` is added *after* `TenantResolutionMiddleware` so that (Starlette runs middleware in reverse-add order) it runs *before* resolution — a cross-origin forgery is rejected without a database lookup — and [[backend/app/security_headers.py]]'s `SecurityHeadersMiddleware` is added **last = outermost**, which is what puts the headers on the `TENANT_NOT_FOUND` 404 that `TenantResolutionMiddleware` returns from its own dispatch without reaching a handler. Five services now share `app.state`, each built over the lazy session factory: `AuthService`, `BoutiqueSettingsService` (with its own terms-creation `FixedWindowRateLimiter`), `CatalogService` (with a presign limiter and `PENDING_MEDIA_TTL_SECONDS`), `StorefrontService` (with its own per-tenant read limiter — deliberately its *own* service, never `CatalogService`, so `out_of_stock`/`total_quantity`/`variant_count` are never even computed for anonymous requests), and the `MediaStorage` chosen by `_build_media_storage`. `S3MediaStorage.__init__` does no network I/O and no credential resolution, which is what keeps `create_app()` callable in the fast suite.

**E3 added three more state-parked services and the SMS sender.** `_build_sms_sender` deliberately mirrors `_build_media_storage`: absence is a *supported* deployment that answers 503, and because `extra="ignore"` silently swallows a typo'd `SMS_PROVDER`, the INFO line is what makes the degradation observable rather than mysterious. `NotificationService`, `OtpService` and `BookingService` are built over the same lazy session factory. The limiter wiring carries one non-obvious constraint worth reading before touching it: `BookingService` gets **two separate `FixedWindowRateLimiter` instances**, not one limiter with two keys, because `max_attempts` is a property of the *limiter* — sharing an instance would hand the per-phone budget the per-tenant ceiling, so the phone budget could never trip first. (This is the general trap: one budget = one instance.)

**F16 parked two more services and added the manage-link handlers.** `BookingCommsService` takes `settings.base_domain` rather than a hardcoded host, because the manage link embedded in an SMS must resolve to the tenant's own storefront in dev, staging and production alike — deployment identity belongs in [[backend/app/core/config.py]], not in a template. `ManageBookingService` gets its **own** `FixedWindowRateLimiter` for the lookup budget, and the reason is the same trap spelled out above for `BookingService`: `max_attempts` is a property of the limiter, so hanging a second key off an existing budget would mean the new one could never trip first. One budget, one instance — the rule now has three instances honouring it.

The three F16 endpoints are POSTs on the existing booking router (`/booking/lookup`, `/booking/confirm-attendance`, `/booking/cancel`), so no new router mounts. **POST for a read is deliberate**: the manage token is a bearer credential, and a GET would put it in the request line, where it reaches access logs, `Referer` headers and browser history. The customer-facing `/b/{token}` path is a storefront SPA route: the token arrives as a path segment in the link her SMS carries, and the page hands it to these endpoints in a request body.

Their handlers extend the existing discipline. `BookingLinkInvalidError` → 404 under **one** body for unknown, rotated and malformed tokens alike: distinguishing them would turn the lookup into an oracle for "is this token even shaped right", which is the same collapse `SlotUnavailableError` makes for taken/off-grid/past/closed and `TenantNotResolvedError` makes for unknown slugs. `BookingAlreadyStartedError` and `BookingCancelledError` are separate codes because, unlike token-shape probes, they describe states the legitimate holder of the link genuinely needs told apart. `BookingLookupThrottledError` reuses the shared 429 body and is a fourth throttle class — the F21 consolidation note below now covers five.

The exception handlers are the security surface and grew from four to a full set. The originals stand: `TenantNotResolvedError` → 404 with the *same* body as any other resolution failure (no 404 confirms a slug exists), `InvalidCredentialsError` → 401 shared across wrong-password and unknown-email (no account enumeration), `RateLimitedError` → 429, `NotAuthenticatedError` → 401. New ones: `RequestValidationError` → **400** house shape platform-wide (FastAPI's default 422 is normalized away everywhere, auth routes included); the domain handlers bind to the *base* classes `DomainValidationError` (→400) and `DomainNotFoundError` (→404) from [[backend/app/errors.py]], deliberately **not** to concrete subclasses — Starlette resolves a handler by walking `type(exc).__mro__`, so binding to a leaf class would turn every sibling into an unhandled 500. Concrete conflict handlers map `DuplicateName/Date/Size`, `TermsVersionConflict`, and the media `Limit/NotUploaded/Mismatch/OrderMismatch` errors to 409; `TermsThrottled`, `MediaPresignThrottled`, and `StorefrontThrottled` reuse the 429 body — the storefront one deliberately has its *own* exception class and handler rather than reusing auth's `RateLimitedError`, because the login form and the anonymous read surface have unrelated budgets (consolidating the four throttle errors onto one base is an F21 cleanup). Storage-layer `MediaNotConfiguredError` and `MediaStorageUnavailableError` → **503** (never 500): a bucket with no usable credentials is operationally identical to no bucket. E3's handlers follow the same discipline: `SmsNotConfiguredError` and `SmsSendError` → 503 with fixed bodies that name no provider; `OtpInvalidError`/`OtpExpiredError` → 400 as **two distinct codes**, because they have genuinely different remedies (retype vs. request a new code); `PhoneNotVerifiedError` → 403; `TermsStaleError` → 409. `SlotUnavailableError` → 409 under **one body for taken, off-grid, past and closed** — collapsing them is deliberate, since distinguishing them would let a prober map the shape of the boutique's grid. The boutique router is included before the catalog router; both mount `prefix="/manage"`, so a duplicated path would silently shadow — the `ROUTES` table in [[backend/tests/test_catalog_api.py]] is what keeps that honest. The storefront router mounts last under its own `/storefront` prefix, never `/manage`: `CsrfOriginMiddleware` and any future edge rule keyed on `/manage` must not cover — or exempt — anonymous traffic. The startup hook still fails the process fast if the database role is a superuser, `BYPASSRLS`, or a table owner, since any of the three silently bypasses forced [[Row Level Security]].

**F31 and F15 landed together and their interaction is the thing to know here.** F31 added role gating: `NotAuthorizedError` lives in [[backend/app/auth/dependencies.py]] — deliberately not in a domain module, because every `/manage` router raises it — and maps to a single generic 403. F15 then mounted a **fourth** `/manage` router, [[backend/app/booking/owner_router.py]], after the catalog router and under the same shadowing caution. Built in parallel, the two features had each invented their own `NotAuthorizedError`; the rebase merged with no textual conflict, so this module briefly imported both, and because Python's second binding wins, *both* handlers registered against F15's class and F31's was left unhandled — every role-gated 403 in already-merged code would have returned a bare 500. Ruff's `F811` on CI is the only thing that caught it. The resolution was pre-written in `.planning/epics/shift-manager-console.md`: F15 dropped its copy and adopted `require_role`. **The lesson this page exists to carry: there is no error registry here.** Every typed error needs an explicit `@app.exception_handler`, an unmapped one is a 500, and a *duplicate* one is worse than missing because it fails silently.

F15's own three handlers follow the established discipline. `BookingTransitionInvalidError` → **409, not 400**: the request is well-formed and it is the booking's state, or the clock, that refuses it. `CustomerAlreadyBookedError` → 409 and deliberately **not** merged into `SLOT_UNAVAILABLE` — that merge is anti-enumeration for anonymous callers, and the owner is authenticated staff who needs to know the target has room but this bride already holds it. `OwnerResendThrottledError` reuses the existing `TOO_MANY_ATTEMPTS_BODY` rather than minting a fourth spelling of the same fact. The `OwnerBookingService` on `app.state` is constructed after the storefront and comms services because it holds both, and the storefront service is **injected rather than re-implemented**: `GET /manage/slots` is its `list_slots` plus an owner projection, and a second materializer is the one thing [[backend/app/booking/slots.py]] exists to forbid. Its `FixedWindowRateLimiter` is its own instance for the fourth time and the same reason — `max_attempts` lives on the limiter, not per key, so a second key on an existing budget could never trip first.

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
- [[backend/app/storefront/router.py]] — public `/storefront` routes
- [[backend/app/storefront/service.py]] — `StorefrontService`
- [[backend/app/storefront/validation.py]] — `StorefrontThrottledError`
- [[backend/app/notifications/router.py]] — public OTP send/verify routes
- [[backend/app/notifications/service.py]] — `NotificationService`, `OtpService` + `OtpInvalid/Expired/Throttled` errors
- [[backend/app/notifications/base.py]] — `SmsSender` protocol, `SmsNotConfiguredError`, `SmsSendError`
- [[backend/app/notifications/fake.py]] — `FakeSmsSender`
- [[backend/app/notifications/unconfigured.py]] — `UnconfiguredSmsSender`
- [[backend/app/booking/router.py]] — public booking-create route
- [[backend/app/booking/owner_router.py]] — F15's `/manage/bookings` + `/manage/slots` routes
- [[backend/app/booking/owner.py]] — `OwnerBookingService` and its three error classes
- [[backend/app/booking/service.py]] — `BookingService` + `SlotUnavailable/TermsStale/PhoneNotVerified/BookingThrottled` errors
- [[backend/app/security_headers.py]] — `SecurityHeadersMiddleware` (outermost)
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
- [[backend/tests/test_storefront_api.py]]

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
- [[backend/tests/test_storefront_api.py]] — public routes work with *no* cookie, throttle 429 body, security headers on every response incl. the middleware-emitted 404, OpenAPI/docs unreachable outside dev

## Notes

`app = create_app()` runs at import time, so anything added to `create_app` must stay database-free until `lifespan`. Spec and plan: [[.planning/specs/subdomain-routing.md]], [[.planning/specs/owner-auth.md]], [[.planning/plans/owner-auth.md]].
