# Plan: Feature 13 — Booking Core API (Epic E3)

**Spec**: `.planning/specs/booking-core.md` · **Branch**: `feature/booking-core` · **Created**: 2026-07-28

TDD throughout. Local gate per task: `make lint` + `make test`.

## Task 1 — Migration 0008 + models + repositories (db tests)
`Backend/migrations/versions/0008_bookings.py`, `app/models/{customer,booking}.py`,
`app/db/repositories/{customers,bookings}.py` + `tests/test_booking_repositories.py`, `tests/test_booking_isolation.py`
- Mirror the 0005/0007 pattern (`_STANDARD`, trigger, grants, RLS loop, partial indexes). Downgrade drops bookings then customers.
- `CustomersRepository`: `by_phone`, `upsert` (attach-or-insert by (tenant, phone)).
- `BookingsRepository`: `insert`, `count_by_start(window)` (the F12 seam feed), `active_seats_at(starts_at)`, `by_id`.
- Isolation: a foreign tenant reads/claims nothing; the same phone under two tenants is two customers.

## Task 2 — Validation + status constants (fast tests)
`app/booking/validation.py` (extend), `app/models/constants.py` (`BookingStatus`)
- `MAX_CUSTOMER_NAME_LENGTH`, `MAX_BOOKING_NOTES_LENGTH`, `MAX_SEAT_INDEX`.
- `validate_booking_request` pure checks (name/notes bounds, size required iff dress given).

## Task 3 — The claim (db tests, the heart of the feature)
`app/booking/service.py` + `tests/test_booking_service.py`
- `BookingService.create_booking(...)` implementing the spec's seven ordered steps.
- Domain errors: `PhoneNotVerifiedError`, `SlotUnavailableError`, `TermsStaleError`, `BookingThrottledError`.
- `IntegrityError` on the seat index → `SlotUnavailableError`.
- **Concurrency tests first**: capacity 1 (two racers), capacity 3 (five racers), cancelled-seat reuse.
- Off-grid/past/closed-day rejection; token misuse; stale terms; customer upsert; snapshot freezing.

## Task 4 — Router + schemas + wiring (API tests)
`app/booking/router.py`, `app/booking/schemas.py`; `app/main.py` (state, handlers, router); `app/core/config.py` (create throttle) + `tests/test_booking_api.py`, route-table additions in `tests/test_storefront_api.py`
- `POST /storefront/bookings` → 201.
- Error handler registrations for the four new domain errors.
- Cookie-blindness + no-store + shadowing guard.

## Task 5 — Close F12's seam
`app/storefront/service.py`, and the F12 tests that assert the empty literal
- `list_slots` passes `booked=await bookings.count_by_start(...)`.
- Update `test_slots_materialize_from_rules_and_exceptions` and the API seam assertion; add a db test proving a booked capacity-1 slot disappears from `/storefront/slots`.

## Task 6 — Review + ship
- `make lint && make test` clean.
- Dual review: phase-reviewer + adversarial security (oversell under concurrency, token replay, off-grid claims, cross-tenant, customer-data disclosure, notes injection).
- Epic row F13 → done; PR `Feature 13: Booking core API (Epic E3)`; watch `gh pr checks`; merge.

## Commit sequence
1. `docs(planning): F13 spec + plan (Gate 1)`
2. `feat(booking): migration 0008, customer and booking models, repositories`
3. `feat(booking): request validation and booking status constants`
4. `feat(booking): the concurrency-safe slot claim`
5. `feat(booking): public booking endpoint, settings, wiring`
6. `feat(storefront): feed real booked counts into the slot grid (closes F12's seam)`
7. review fixes, then PR.
