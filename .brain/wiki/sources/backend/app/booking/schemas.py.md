---
tags: [backend, booking, python, pydantic, schemas, wire-models, pii]
sources: [backend/app/booking/schemas.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/schemas.py
blob: aa3cba1a305565f6bc50dfa4f02e2b35d5777c74
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/schemas.py

**Role.** Every wire shape the booking feature exposes across three audiences — the anonymous create, the token-authed manage page, and the session-authed owner console — with the PII boundary between them expressed as separate models rather than as filtering.

**Module.** [[backend/app/booking/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `BookingCreateRequest` / `BookingCreateResponse` | model | The anonymous create; the response is what the confirmation screen needs and nothing else |
| `ManageTokenRequest` | model | The one body all three manage endpoints take — just `token` |
| `ManageBookingFacts` · `ManagePolicy` · `ManageBoutique` · `ManageBookingResponse` | model | The `/b/{token}` page's payload; lookup, confirm and cancel all answer the same envelope |
| `OwnerBookingRow` / `OwnerBookingListResponse` | model | One line of the owner's day list, plus the paged envelope (`items`/`total`/`offset`/`limit`) |
| `OwnerBookingDetail` | model | `OwnerBookingRow` plus the fields the owner opened the booking for |
| `OwnerSlotRow` / `OwnerSlotListResponse` | model | The owner slot grid, carrying `capacity` and `remaining` |
| `RescheduleRequest` / `PhoneCorrectionRequest` | model | `ForbidExtraModel` bodies for the two owner writes that take one |
| `MAX_TOKEN_INPUT_LENGTH` · `MAX_NAME_INPUT_LENGTH` · `MAX_NOTES_INPUT_LENGTH` · `MAX_SIZE_INPUT_LENGTH` | const | Generous ceilings, not product policy |

## Behavior

The `Field(max_length=…)` ceilings here are deliberately **not** the product's bounds — the real limits (name 80, notes 500, the dress/size pairing) live in [[backend/app/booking/validation.py]] and answer a clean domain 400. These only stop a megabyte body from reaching the service layer. `starts_at` on both `BookingCreateRequest` and `RescheduleRequest` is `AwareDatetime`, so a naive timestamp is a schema 400 and the services only ever compare real instants against the grid.

**The three audiences do not share models, and that is the security posture.** No public model inherits from a richer one (the F10 rule): the public wire is defined by narrow models, never by inheritance. `ManageBookingFacts` deliberately carries **no** customer name, phone, id, seat index or notes — the manage link is possession-auth, so the payload carries the appointment's facts and no PII beyond them. `OwnerBookingDetail` inverts that reasoning on purpose and the docstring warns against copying `ManageBookingFacts` as a precedent: it answers an authenticated owner over a session-authed, CSRF-fenced, `no-store` surface, and the operational point of the screen is that she can phone the bride and read what she wrote. The inheritance that does exist runs **narrow → rich** (`OwnerBookingDetail(OwnerBookingRow)`), so a field added to the detail can never reach an anonymous surface by default.

Three omissions are decisions rather than gaps. `OwnerBookingRow` has no `customer_phone` and no `notes`, so the day list is not a bulk PII export of the boutique's whole day — those are what the owner opens a booking to see. `OwnerBookingDetail` has no `manage_token_hash`: it is the stored half of a live control credential, so the wire carries only `manage_link_issued`, a boolean. And `ManagePolicy` has no `terms_text` — the page states the window and the consequence, and the full policy she already accepted is not what that screen is for; the numbers come from the **accepted** terms version, never the current one.

`OwnerSlotRow` carries `capacity` and `remaining`, which the anonymous `SlotRow` in [[backend/app/storefront/schemas.py]] fences off because they disclose how many parallel fittings the boutique runs. That fence is about anonymous visitors; an owner picking a reschedule target legitimately needs to know she is taking the last place.

`ManageTokenRequest` puts the credential in the **body**, never a path or query parameter, so no access log, referrer or proxy trace carries it — which is why the manage lookup is a POST for what is semantically a read.

## Depends On

- [[Pydantic]] — `BaseModel`, `Field`, `AwareDatetime`
- [[backend/app/schemas.py]] — `ForbidExtraModel`
- [[backend/app/notifications/schemas.py]] — `MAX_PHONE_INPUT_LENGTH`

## Depended On By

- [[backend/app/booking/router.py]] — the create and the three manage routes
- [[backend/app/booking/owner_router.py]] — all ten owner routes
- [[backend/app/booking/manage.py]] — builds `ManageBookingResponse` directly

## Concepts

- [[Tenant Isolation]]

## Tests

- [[backend/tests/test_booking_api.py]] — the create's request validation and response shape
- [[backend/tests/test_booking_manage_api.py]] — the manage envelope across all three endpoints
- [[backend/tests/test_booking_owner_api.py]] — the owner row/detail split and the slot projection
- [[backend/tests/test_booking_owner_service.py]] — the schemas as the service produces them

## Notes

`MAX_SIZE_INPUT_LENGTH` is 64 against a catalog cap of 32 — anything longer can never match a variant, so the ceiling is pure body-size defence.

Design context: [[.planning/specs/booking-core.md]], [[.planning/specs/booking-comms.md]], [[.planning/specs/owner-booking-management.md]].
