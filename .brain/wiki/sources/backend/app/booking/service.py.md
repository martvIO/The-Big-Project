---
tags: [backend, booking, python, concurrency, advisory-lock, idempotency, rate-limiting, transactions]
sources: [backend/app/booking/service.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/service.py
blob: 13dc2744aa809c8ea0af948acc6a7d20b54369d8
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/service.py

**Role.** The claim: turns a phone-verified anonymous request into exactly one `bookings` row at a slot the grid offers, under a per-tenant advisory lock with a partial unique index as the structural backstop — and returns the raw manage token that only exists in flight.

**Module.** [[backend/app/booking/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `BookingService.create_booking` | async method | The whole protocol; returns a `BookingClaim` |
| `BookingClaim` | frozen dataclass | `booking`, `created`, `manage_token` — the token is `None` on a replay |
| `BOOKABLE_HORIZON` | const | `SLOT_WINDOW_MAX_DAYS + 2` days — the outer bound on `starts_at` |
| `BookingNotFoundError` | class | `DomainNotFoundError` — unknown appointment type, dress, or a size that is not an active variant. Indistinguishable 404s by design |
| `PhoneNotVerifiedError` | class | The verification token does not prove possession → 403 `PHONE_NOT_VERIFIED` |
| `SlotUnavailableError` | class | One error for full / off-grid / past / closed → 409 `SLOT_UNAVAILABLE` |
| `TermsStaleError` | class | Accepted terms version is not current → 409 `TERMS_STALE` |
| `BookingThrottledError` | class | A create budget is spent → the shared 429 |

## Behavior

Everything happens inside **one** `tenant_session`, and the ordering of the steps is the correctness argument rather than an implementation detail. Before the session opens: pure shape validation, phone normalization, and a total range guard on `starts_at` — `AwareDatetime` accepts the entire datetime range and `.astimezone()` on a year-9999 instant raises `OverflowError`, an unhandled 500 on an anonymous route, so the guard is expressed as a comparison (which cannot overflow) and answers the same leak-free 409 as any other unoffered time.

The two rate-limit budgets are **checked before the transaction and spent only after the phone is proven**. Metering an unproven caller would invert the whole cost model: garbage tokens would exhaust a boutique's hourly allowance and lock every real bride out at zero cost to the attacker. They live on **two separate limiter instances**, never two keys on one — `max_attempts` lives on the limiter, so a shared instance would give the per-phone budget the tenant ceiling and it could never trip first. The per-phone budget is the real control (a failed claim rolls its own token burn back, so one verified number can retry); the per-tenant one is a runaway brake sized so it cannot fire on organic traffic. Because the limiter is in-memory it survives the transaction rollback by design, which is precisely what stops a reusable token from buying unlimited attempts.

Inside the session, in order: consume the verification token (first, so a caller who cannot prove the phone never causes a lock to be taken); spend both budgets; load the appointment type and assert the accepted terms version is the current one; on the item-based path snapshot the dress name and resolve the size **case-insensitively** against the dress's active variants, storing the boutique's own label rather than the customer's spelling; then `pg_advisory_xact_lock(hashtext(tenant_id))`, and everything from there to COMMIT holds it.

**Idempotency comes before availability, and that order is the entire fix.** When a claim commits but its 201 dies on a flaky mobile network, the token is already spent, so the retry arrives with a fresh code — at capacity 1 the bride's own booking now fills the slot, so checking availability first would 409 her onto a time she does not need, and at higher capacity it would silently give her two seats. So a live booking for this proven phone at this instant is *this request's outcome*: it is returned unchanged, `created=False`, `manage_token=None`. It is implemented as a **read** rather than as catching the `IntegrityError`, because a failed flush aborts the Postgres transaction and recovering would need a SAVEPOINT around the INSERT for a path the 409 would beat anyway; the read cannot race because every claim takes the advisory lock first, and 0009's partial unique index backstops any writer that does not.

Then the grid is **re-materialized** through [[backend/app/booking/slots_io.py]] with the real booked counts (which is also how capacity is enforced), the customer is upserted for the proven phone, and the **lowest free seat** is picked by scanning `1..capacity` against the active seats at that instant — counting alone would overflow past a seat freed by a cancellation into an occupied one. The manage token is minted here so its hash commits atomically with the row it authorises, and an `IntegrityError` on the INSERT (a race the advisory lock should have prevented) is mapped to the same `SlotUnavailableError` the caller would have seen anyway. Finally the reminder's `scheduled_messages` row is written **in this same transaction**: leaving it to a post-commit block would let a crash between commit and block lose the reminder permanently with nothing sweeping for the gap. A `None` `send_after` means the appointment is inside the two-hour suppression band and no row is correct.

The SMS send is the only post-commit work and it belongs to [[backend/app/booking/router.py]], because `NotificationService.send_sms` structurally opens its own sessions and a provider hang inside this transaction would block commits.

## Depends On

- [[backend/app/db/tenant.py]] — `tenant_session`, the RLS-bound session
- [[backend/app/booking/slots_io.py]] — `offered_slot`
- [[backend/app/booking/validation.py]] — `validate_booking_request`, `SLOT_WINDOW_MAX_DAYS`, `BookingValidationError`
- [[backend/app/booking/tokens.py]] — mint and hash the manage token
- [[backend/app/booking/comms.py]] — `reminder_send_after` for the D3 bands
- [[backend/app/notifications/service.py]] — `OtpService.consume_verification`
- [[backend/app/notifications/validation.py]] — `normalize_israeli_mobile`
- [[backend/app/catalog/validation.py]] — `normalize_size_label`
- [[backend/app/auth/rate_limit.py]] — `FixedWindowRateLimiter`
- [[backend/app/db/repositories/bookings.py]] · [[backend/app/db/repositories/customers.py]] · [[backend/app/db/repositories/appointment_types.py]] · [[backend/app/db/repositories/terms.py]] · [[backend/app/db/repositories/dresses.py]] · [[backend/app/db/repositories/dress_variants.py]] · [[backend/app/db/repositories/availability.py]] · [[backend/app/db/repositories/scheduled_messages.py]]
- [[backend/app/models/booking.py]] · [[backend/app/models/constants.py]] · [[backend/app/errors.py]] · [[backend/app/storefront/validation.py]]

## Depended On By

- [[backend/app/booking/router.py]] — the anonymous `POST /storefront/bookings`
- [[backend/app/main.py]] — constructs the service, wires both limiters, and binds an exception handler to each of the four typed errors
- [[backend/app/booking/owner.py]] — reuses `BOOKABLE_HORIZON`, `BookingNotFoundError` and `SlotUnavailableError` rather than restating them

## Concepts

- [[Row Level Security]]
- [[Tenant Context]]
- [[Rate Limiting]]

## Tests

- [[backend/tests/test_booking_service.py]] — the protocol end to end, including the concurrency proof for the seat claim
- [[backend/tests/test_booking_api.py]] — the HTTP surface and each error's status/code
- [[backend/tests/test_booking_repositories.py]] — the two repositories the claim writes
- [[backend/tests/test_booking_isolation.py]] — that one tenant's bookings never contend for another's seats
- [[backend/tests/test_booking_comms_db.py]] — the reminder row written inside the claim's transaction

## Notes

`BOOKABLE_HORIZON` carries **two** days of slack past the grid's publishable ceiling, not one: the ceiling is a boutique *date* while this is a UTC *instant*, and an Israeli DST fall-back between now and the ceiling shifts every local wall time an hour later in UTC — at +1 day that ate the last half-hour of the final day's grid.

A `ponytail:` comment marks the deliberate ceiling on the lock: one advisory lock per tenant serializes **all** claims for that tenant, upgradeable to per-slot lock keys if pilot throughput ever cares.

Design context: [[.planning/specs/booking-core.md]] and [[.planning/specs/booking-comms.md]].
