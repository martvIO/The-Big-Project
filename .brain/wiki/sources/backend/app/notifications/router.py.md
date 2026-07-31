---
tags: [backend, notifications, otp, python, fastapi, api, storefront, security]
sources: [backend/app/notifications/router.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/notifications/router.py
blob: bcf044720d23774ece9ba7b9ca1edaaf8048b400
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/notifications/router.py

**Role.** The public OTP surface: two anonymous, tenant-scoped POSTs (`/storefront/otp/send` → 204, `/storefront/otp/verify` → a `verification_token`), both forced `cache-control: no-store`, both resolving the tenant from the Host header and delegating everything else to `OtpService`.

**Module.** [[backend/app/notifications/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `router` | `APIRouter` | prefix `/storefront`, router-level `_no_store` dependency |
| `get_otp_service` | fn | Pulls `app.state.otp_service` off the request — the DI seam tests override |
| `_no_store` | fn | Sets `cache-control: no-store` on every response from this router |
| `NO_STORE` | const | `"no-store"` |
| `send_otp` | route | `POST /storefront/otp/send`, `status_code=204` |
| `verify_otp` | route | `POST /storefront/otp/verify` → `OtpVerifyResponse` |

## Behavior

**It is a sibling router on `/storefront`, not new routes inside [[backend/app/storefront/router.py]].** That router is contractually GET-only (its docstring and the HEAD-405 argument depend on it), so putting mutations there would quietly falsify a claim other tests rest on. Both routers share the prefix and this one is registered *after* the read router in `create_app`; the cross-router shadowing guard in [[backend/tests/test_storefront_api.py]] covers the pair so a future path collision fails loudly.

**CSRF is structurally N/A here, and there is a test that keeps it that way.** These endpoints read no cookie and carry no ambient credential, so a cross-site POST has nothing to ride: the actual controls are tenant-from-Host, the per-phone and per-tenant send budgets, and possession of the code itself. `test_owner_cookie_changes_nothing` sends a request carrying a valid owner cookie and asserts a byte-identical response — that is what makes the cookie-blindness claim permanent rather than a comment.

**Send answers 204 unconditionally on a well-formed request.** The response confirms acceptance, never delivery — whether a code went out is observable by the phone's owner alone, and unknown phones answer identically to known ones, so there is nothing to enumerate. This is why an exhausted *per-phone* budget also returns 204 (silently sending nothing) while an exhausted *per-tenant* budget 429s: see [[backend/app/notifications/service.py#send]].

Both handlers do the same three things and nothing more: `get_current_tenant(request)` from the tenancy middleware, call the service, shape the response. Every error — `DomainValidationError`, `SmsNotConfiguredError`, `SmsSendError`, `OtpInvalidError`, `OtpExpiredError`, `OtpThrottledError` — propagates to an explicit handler in [[backend/app/main.py]]; there is no `try` here. The `_no_store` dependency is router-level rather than per-route because the verify response carries a bearer `verification_token` that must never land in a shared cache or a bfcache entry, and send pays nothing for carrying the same header.

## Depends On

- [[backend/app/notifications/schemas.py]] — the three wire models
- [[backend/app/notifications/service.py]] — `OtpService`
- [[backend/app/tenancy/middleware.py]] — `get_current_tenant`
- [[FastAPI]]

## Depended On By

- [[backend/app/main.py]] — `include_router(otp_router)` after the storefront read router

## Concepts

- [[One Time Passcode]]
- [[Tenant Resolution]]
- [[Enumeration Resistance]]

## Tests

- [[backend/tests/test_notifications_api.py]] — `test_send_accepts_anonymous_and_returns_204`, `test_verify_returns_the_token_once`, `test_otp_paths_are_not_exempt_from_tenant_resolution`, `test_otp_responses_are_never_cached`, `test_get_stays_405`, `test_owner_cookie_changes_nothing`, `test_security_headers_are_on_an_otp_response`, `test_verify_error_mapping`, `test_send_error_mapping`
- [[backend/tests/test_storefront_api.py]] — the cross-router shadowing guard

## Notes

`get_otp_service` reads `request.app.state.otp_service`, which is populated in `create_app`. The API tests swap in a stub service through that same attribute rather than through FastAPI dependency overrides.
