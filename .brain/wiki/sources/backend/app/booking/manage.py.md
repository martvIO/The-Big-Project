---
tags: [backend, booking, python, manage-link, tokens, idempotency, rate-limiting]
sources: [backend/app/booking/manage.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/manage.py
blob: df882de361a08f81d172a4f3085084958a5c5b7f
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/manage.py

**Role.** The service behind the anonymous `/b/{token}` page: resolve a booking by manage-token possession alone, render its facts with the policy from the **accepted** terms version, and let the customer confirm attendance or cancel — both idempotent, both expiring at `starts_at` while the page itself stays readable.

**Module.** [[backend/app/booking/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ManageBookingService.lookup` | async method | Read-only, and the only metered call of the three |
| `ManageBookingService.confirm_attendance` | async method | Writes `attendance_confirmed_at`; idempotent |
| `ManageBookingService.cancel` | async method | Status write + cancel evidence + kills the pending reminder, in one transaction |
| `ManageTenant` | frozen dataclass | The tenant identity the page renders: `id`, `name`, `settings` |
| `BookingLinkInvalidError` | class | Unknown, rotated or malformed token → 404 `BOOKING_LINK_INVALID` |
| `BookingAlreadyStartedError` | class | The appointment has started → 409 `BOOKING_ALREADY_STARTED` |
| `BookingCancelledError` | class | Confirming attendance at a cancelled appointment → 409 `BOOKING_CANCELLED` |
| `BookingLookupThrottledError` | class | The per-tenant lookup budget is spent → the shared 429 |

## Behavior

Lookup is by **token possession only** — deliberately not a read-a-booking-by-id endpoint. The booking becomes readable again through the link she was sent and nothing else: `_resolve` hashes the incoming token, selects on the stored sha256, and then re-checks with `manage_token_matches`, a redundancy that exists so a future widening of the query predicate cannot hand back a booking whose token the caller does not hold. Every failure mode collapses into one `BookingLinkInvalidError`, because distinguishing "never existed" from "no longer yours" would make this endpoint an oracle.

**The page stays readable after `starts_at`; only the actions expire.** That is a recorded amendment to the security checklist's "expire at appointment time" wording — an honest "this appointment has passed" beats a dead link for someone re-opening her SMS weeks later.

**Only `lookup` is metered**, and the budget is recorded on **every** attempt, hit or miss, because the resource being metered is the guess itself — a limiter that only counted successes would be inert against a token walk. It runs on its **own** `FixedWindowRateLimiter` instance, never a second key on someone else's, because `max_attempts` lives on the limiter and a shared instance would hand this budget an unrelated ceiling. Keyed per tenant rather than per IP for the same reason as the OTP surface: `trust_forwarded_for` is unresolved, and behind an untrusted proxy an IP key collapses to one bucket anyway. The token's 256 bits of entropy remain the real control; this is the anti-scrape floor beneath it.

`confirm_attendance` writes the column F13 shipped with no writer — the whole no-show defence the reminder exists to collect. It is idempotent through the repository's `IS NULL` guard, so a second tap keeps the **first** confirmation's timestamp instead of moving it, and she sees the same success either way (she will click more than once).

`cancel` is one transaction: the status write, the cancel evidence with `cancelled_by = 'customer'`, and the pending reminder flipped to `cancelled` — without that last step she would get a reminder for an appointment she just cancelled. The seat and the idempotency slot free themselves **structurally**, because both partial unique indexes (0008, 0009) exclude `status = 'cancelled'`, so the freed time reappears in the picker and she can rebook the same instant with no extra work here. A repeat cancel is checked **before** the clock and returns the same success even once the appointment time has passed — that ordering is the difference between idempotent and merely lenient. No SMS is sent: the page she is looking at *is* the receipt, and every body is segment cost plus legal surface.

`_render` reads the **accepted** terms version, never the current one — computing a customer's cancellation consequence from re-published terms is exactly the bug `bookings.terms_version_accepted` exists to prevent. A missing accepted row yields `policy=None` rather than a fabricated number; the table is append-only by DB grant, so that is a guard and not a path.

## Depends On

- [[backend/app/db/tenant.py]] — `tenant_session`
- [[backend/app/booking/tokens.py]] — `manage_token_hash`, `manage_token_matches`
- [[backend/app/booking/schemas.py]] — the four response models
- [[backend/app/db/repositories/bookings.py]] · [[backend/app/db/repositories/terms.py]] · [[backend/app/db/repositories/scheduled_messages.py]]
- [[backend/app/auth/rate_limit.py]] — `FixedWindowRateLimiter`
- [[backend/app/models/booking.py]] · [[backend/app/models/constants.py]]
- [[backend/app/storefront/validation.py]] — `Clock`, `profile_text`

## Depended On By

- [[backend/app/booking/router.py]] — the three manage routes
- [[backend/app/main.py]] — constructs the service, wires the lookup limiter from the `booking_lookup_*` settings, and binds a handler to each of the four typed errors

## Concepts

- [[Row Level Security]]
- [[Tenant Context]]
- [[Rate Limiting]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_booking_manage_api.py]] — the HTTP surface, the throttle, and every error status
- [[backend/tests/test_booking_comms_db.py]] — the service against real rows, including the reminder cancellation
- [[backend/tests/test_manage_token.py]] — the credential primitives it resolves through

## Notes

`ManageTenant` is built from the host-resolved `TenantContext` at the router rather than re-read here, following the `StorefrontService.get_boutique` precedent of passing identity explicitly.

`BookingLookupThrottledError` is its own class rather than a reuse of another throttle because these budgets have unrelated keys and unrelated operational meanings; reparenting all four onto one base is deferred.

Design context: [[.planning/specs/booking-comms.md]] and [[.planning/design/screens/manage-booking/manage-booking.md]].
