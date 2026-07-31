---
tags: [backend, booking, python, fastapi, router, anonymous, csrf, caching]
sources: [backend/app/booking/router.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/router.py
blob: 97d25c360ebaca758468415ddf0406c163ccc838
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/router.py

**Role.** The four anonymous, tenant-scoped POSTs on `/storefront`: create a booking, and the three token-authed manage actions (lookup, confirm-attendance, cancel) — plus the post-commit confirmation SMS.

**Module.** [[backend/app/booking/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `router` | `APIRouter` | Prefix `/storefront`, router-level `_no_store` dependency |
| `create_booking` | route | `POST /storefront/bookings` → 201 `BookingCreateResponse` |
| `lookup_booking` | route | `POST /storefront/booking/lookup` |
| `confirm_attendance` | route | `POST /storefront/booking/confirm-attendance` |
| `cancel_booking` | route | `POST /storefront/booking/cancel` |
| `get_booking_service` · `get_comms_service` · `get_manage_service` | dep | Pull the three singletons off `app.state` |
| `_no_store` | dep | Sets `cache-control: no-store` on every response |

## Behavior

**A sibling router on `/storefront`, not new routes in [[backend/app/storefront/router.py]]** — that router is contractually GET-only, so everything that mutates lives here. It is registered after it in `create_app()`, and because two routers now share the prefix a duplicated `(method, path)` would silently win or lose on include order; [[backend/tests/test_storefront_api.py]]'s cross-router shadowing guard is what keeps that honest.

**Anonymous and cookie-blind, so CSRF is structurally N/A.** On the create the credential is the single-use, phone-bound verification token minted by the OTP surface; on the three manage routes it is the manage token, which arrives in the **body** so no access log carries it. No cookie is read anywhere here, so there is nothing a cross-site request could ride — the controls are tenant-from-Host, token possession, and the per-tenant budgets inside the services. A cookie-blindness test keeps that claim true.

`_no_store` is applied at the **router** level for the same reason the OTP surface does it: every response here names a real person's appointment, which must never land in a shared cache or a bfcache entry — and the manage page is reached from an SMS on a phone, where bfcache is the default. Setting it centrally is what makes a route added later unable to forget it.

**The confirmation SMS fires here, after the transaction commits**, and only when the claim actually created a booking. Post-commit because `NotificationService.send_sms` structurally opens its own sessions and a provider hang inside the booking transaction would block commits; `await`ed rather than backgrounded so the send happens inside the request's own lifetime; and fire-and-forget because turning a committed booking into a 503 would be a lie. The guard is `claim.created and claim.manage_token is not None` — two spellings of one fact, since the idempotency-replay path carries no raw token. `send_confirmation` never raises (it swallows both provider failure modes after their evidence exists), so it cannot cost the caller their 201.

The manage lookup is a **POST for a read**, deliberately: a GET would put the token in the query string and from there into every access log, proxy trace and `Referer` header on the path.

## Depends On

- [[backend/app/booking/service.py]] — `BookingService`
- [[backend/app/booking/manage.py]] — `ManageBookingService`, `ManageTenant`
- [[backend/app/booking/comms.py]] — `BookingCommsService`, `CommsTenant`
- [[backend/app/booking/schemas.py]] — the four wire models
- [[backend/app/tenancy/middleware.py]] — `TenantContext`, `get_current_tenant`
- [[FastAPI]] — `APIRouter`, `Depends`

## Depended On By

- [[backend/app/main.py]] — includes the router and constructs all three services onto `app.state`
- [[backend/app/booking/owner_router.py]] — reuses `get_comms_service` rather than declaring a second one

## Concepts

- [[Tenant Resolution]]
- [[Rate Limiting]]

## Tests

- [[backend/tests/test_booking_api.py]] — the create route, every error status, and the cookie-blindness assertion
- [[backend/tests/test_booking_manage_api.py]] — the three manage routes
- [[backend/tests/test_storefront_api.py]] — the cross-router shadowing guard covering all four paths

## Notes

Design context: [[.planning/specs/booking-core.md]] and [[.planning/specs/booking-comms.md]].
