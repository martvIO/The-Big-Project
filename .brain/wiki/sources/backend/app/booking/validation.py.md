---
tags: [backend, booking, python, validation, constants, timezone]
sources: [backend/app/booking/validation.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/validation.py
blob: d66e3fb7344c51bccab477f842e31106997d9692
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/validation.py

**Role.** The booking module's product-policy constants (slot granularity, window ceilings, name/notes lengths, list paging bounds), the pure request-shape checker that answers a clean 400 without touching the database, and the single Monday-first→Sunday-first conversion that makes Python's weekday agree with the Israeli week the availability tables are keyed on.

**Module.** [[backend/app/booking/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `BookingValidationError` | class | Subclass of `DomainValidationError`; the app-wide handler bound to the base answers it as the house-shape 400 |
| `SLOT_INTERVAL_MINUTES` | const | 30 — the scheduling granularity the grid steps by |
| `DEFAULT_SLOT_CAPACITY` | const | 1 — matches the `availability_rules.capacity` DB default; used only when an exception opens a date with no weekly rule to inherit from |
| `SLOT_WINDOW_DEFAULT_DAYS` / `SLOT_WINDOW_MAX_DAYS` | const | 14 / 60 — the picker's default span and the anonymous-request ceiling |
| `MAX_CUSTOMER_NAME_LENGTH` / `MAX_BOOKING_NOTES_LENGTH` | const | 80 / 500 |
| `BOOKING_LIST_DEFAULT_LIMIT` / `BOOKING_LIST_MAX_LIMIT` | const | 50 / 200 — the owner day list's paging bounds |
| `MAX_SEAT_INDEX` | const | 1000 — mirrors `MAX_RULE_CAPACITY` and 0008's `CHECK` |
| `validate_booking_request` | fn | Pure shape checks on name, notes and the dress/size pair |
| `jerusalem_day_index` | fn | `date` → 0=Sunday…6=Saturday, the `availability_rules.day_of_week` encoding |

## Behavior

`validate_booking_request` answers only questions the request can answer alone — blank or over-long name, over-long notes, forbidden control characters, and the dress/size pairing rule. Whether the dress exists, whether the size is one of its active variants and whether the slot is real are service questions needing the database, and they surface as 404/409 from [[backend/app/booking/service.py]] instead. The two control-character regexes differ on purpose and the difference is a real defence, not tidiness: `name` bars the whole C0 set because a newline in a value F16 templates into an SMS body is header-injection material, while `notes` is a paragraph and keeps tabs and newlines, barring only the non-whitespace controls. Both bar U+0000, which Postgres rejects outright in a `text` column — an uncaught asyncpg `DataError` on an anonymous route is a 500, so the NUL is an availability bug before it is a security one, and these are the first customer-authored strings in the product (every earlier free-text write sits behind manage auth). The dress rule enforces the two-path model at the boundary: item-based carries **both** `dress_id` and `dress_size`, generic carries **neither** — a size without a dress is noise, a dress without a size books unfittable stock.

`jerusalem_day_index` exists because `date.weekday()` is Monday-first and the availability tables are Sunday-first; the shift lives here once so no caller re-derives it. `frontend/packages/ui/src/lib/hours.ts` maps the same seven names to the same seven indices for rendering, and [[backend/tests/test_frontend_constant_parity.py]] pins the two together so a drift is a test failure rather than a wrong picker.

Every constant here is deliberately **not** env-tunable, per the house rule that `Settings` carries deployment identity and never product policy — an operator must not be able to raise a limit in env while a DB `CHECK` and a frontend validator stay put. The boutique wall clock itself is not restated here either: `BOUTIQUE_TIMEZONE` is imported from [[backend/app/storefront/validation.py]] by the modules that need it, because two zone constants is one too many.

## Depends On

- [[backend/app/errors.py]] — `DomainValidationError`, the base the app-wide 400 handler is bound to

## Depended On By

- [[backend/app/booking/service.py]] — `validate_booking_request`, `SLOT_WINDOW_MAX_DAYS` (via `BOOKABLE_HORIZON`), `BookingValidationError`
- [[backend/app/booking/slots.py]] — `SLOT_INTERVAL_MINUTES`, `DEFAULT_SLOT_CAPACITY`, `jerusalem_day_index`
- [[backend/app/booking/owner.py]] — `BOOKING_LIST_MAX_LIMIT`
- [[backend/app/booking/owner_router.py]] — `BOOKING_LIST_DEFAULT_LIMIT`, `BOOKING_LIST_MAX_LIMIT`
- [[backend/app/storefront/service.py]] — `SLOT_WINDOW_DEFAULT_DAYS`, `SLOT_WINDOW_MAX_DAYS`

## Concepts

- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_booking_validation.py]] — the shape checks and the control-character split
- [[backend/tests/test_slot_engine.py]] — uses the interval and capacity constants against the grid
- [[backend/tests/test_frontend_constant_parity.py]] — pins `jerusalem_day_index` and the module's constants against the frontend
- [[backend/tests/test_storefront_validation.py]] — the window constants as the storefront reads them

## Notes

`MAX_SEAT_INDEX` is 1000 rather than the usual 10x absurdity ceiling because it equals `MAX_RULE_CAPACITY` exactly: a seat index above capacity can never be claimed, so capacity is already the real bound. Note that nothing in the database ties a seat to *its own slot's* capacity — 0008's `CHECK` is only `1..1000` — which is why [[backend/app/booking/owner.py]]'s reschedule must recompute the lowest free seat in Python rather than carry the old one.

Design context: [[.planning/specs/booking-core.md]].
