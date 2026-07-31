---
tags: [backend, booking, python, fastapi, router, owner-console, rbac, caching]
sources: [backend/app/booking/owner_router.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/owner_router.py
blob: 6ec9d727e9135f8e4c26f5387d2faaa41d5df54b
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/owner_router.py

**Role.** The owner console's ten booking routes on `/manage` — day list, detail, four status verbs, reschedule, phone correction, resend-link and the owner slot grid — behind a router-level role gate and `no-store`, with every SMS fired post-commit and discarded.

**Module.** [[backend/app/booking/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `router` | `APIRouter` | Prefix `/manage`, with `_no_store` and `require_role(OWNER, SHIFT_MANAGER)` as router-level dependencies |
| `list_bookings` | route | `GET /manage/bookings` — required `date`, plus `offset`/`limit` |
| `get_booking` | route | `GET /manage/bookings/{booking_id}` |
| `confirm_booking` · `cancel_booking` · `mark_no_show` · `mark_completed` | route | The four transition verbs |
| `reschedule_booking` · `correct_booking_phone` · `resend_booking_link` | route | The three writes that spend SMS credit |
| `list_owner_slots` | route | `GET /manage/slots` with `from`/`to` aliases |
| `get_owner_booking_service` | dep | Pulls the singleton off `app.state` |
| `_row` · `_detail` · `_detail_of` · `_customers` | fn | ORM row + customer → wire model |
| `_send_rotation` | fn | Post-commit `send_confirmation` when the mutation carried a token |

## Behavior

**A fourth router on `/manage`, not new routes in an existing one** — the catalog and boutique routers are the catalog's and the boutique's; bookings are neither. Because several routers now mount this prefix, a duplicated `(method, path)` would silently win or lose on include order, and [[backend/tests/test_booking_owner_api.py]]'s route table is what keeps that honest.

Authorization is a **router-level** `require_role` gate matching the boutique and catalog routers, so a route added later cannot forget it and the default-deny gating walker can read `allowed_roles` straight off the router. Both `OWNER` and `SHIFT_MANAGER` are admitted — the shift-manager console keeps near-owner permissions on the bookings section. The `staff` dependency on each handler is not a second guard; every handler needs the staff row for its audit entry anyway, and the router-level gate is what refuses. `_no_store` is likewise router-level, for the reason the anonymous booking router and the catalog router both state: every response here names a real person's appointment, her phone and her free-text notes, and setting the header centrally makes the invariant structural.

**Four verb sub-paths rather than one PATCH carrying a `status` field.** The four transitions are not four values of one operation: cancel is guarded on a *future* `starts_at`, sends an SMS and cancels a pending reminder; no-show and complete are guarded on a *past* one and send nothing; confirm is the undo of a mis-tap. One handler would collapse four preconditions and two side-effect sets into one body of ifs and one error code. Path parameters and real HTTP verbs are the shipped `/manage` convention here — the `.claude/rules` RPC/`@QueryValue` guidance describes a Kotlin codebase that does not exist in this repo.

**Every send is post-commit, here, awaited and discarded.** Post-commit because `NotificationService.send_sms` structurally opens its own sessions and a provider hang inside the service's transaction would block commits; awaited rather than backgrounded so the send happens inside the request's own lifetime; fire-and-forget because turning a committed mutation into a 503 would be a lie. There is no `BackgroundTasks` and no `asyncio.create_task` anywhere in the module. The service answers an `OwnerMutation` carrying `changed`, and cancel and reschedule branch on it — a no-op transition sends nothing. `_send_rotation` branches on `manage_token is not None` instead, because sha256 is one-way and the raw token minted inside the transaction travels out on the result or the message has no link to put in it. The reschedule notice deliberately reads the live token off the pending reminder the service's transaction already wrote, so the SMS carries the same link the future reminder will send — an ordering enforced by the transaction boundary rather than by two calls in the right sequence.

The projections encode three decisions. A **soft-deleted customer renders blank** rather than 500-ing the day list, because the booking is still the boutique's appointment either way. `manage_token_hash` never reaches the wire — the detail exposes only `manage_link_issued`, a boolean, since the hash is the stored half of a live control credential. And `offset` carries `le=MAX_LIST_OFFSET` at the boundary *and* is clamped again in the service, because it binds as `OFFSET $n::BIGINT` and an unbounded int from a non-router caller would die in asyncpg's encoder as a 500.

`GET /manage/slots` is a **sibling** of the anonymous `GET /storefront/slots`, not a reuse: that route spends the anonymous read budget, its projection is contractually blind to `capacity` and `remaining`, and the console's dev proxy forwards `/manage` only. The computation is still shared — this is `StorefrontService.list_slots` plus an owner projection, never a second materializer. A `to < from` window raises a `DomainValidationError` subclass, so the handler bound to the base already answers it as a 400 with no new code.

`GET /manage/bookings` requires `date` and takes no status filter: **cancelled rows are included**, as a constant in the repository query, because a cancelled row is the owner's evidence that the slot re-opened. The parameter is deliberately alone; a calendar view will widen this same route with an optional from/to pair rather than shipping two spellings of one filter now.

## Depends On

- [[backend/app/booking/owner.py]] — `OwnerBookingService`, `OwnerMutation`, `MAX_LIST_OFFSET`
- [[backend/app/booking/comms.py]] — `BookingCommsService`, `CommsTenant`
- [[backend/app/booking/router.py]] — reuses `get_comms_service` rather than declaring a second one
- [[backend/app/booking/schemas.py]] — the seven owner wire models
- [[backend/app/booking/slots.py]] — the `Slot` type it projects
- [[backend/app/booking/validation.py]] — `BOOKING_LIST_DEFAULT_LIMIT`, `BOOKING_LIST_MAX_LIMIT`
- [[backend/app/auth/dependencies.py]] — `get_current_staff`, `require_role`
- [[backend/app/auth/service.py]] — `StaffContext`
- [[backend/app/tenancy/middleware.py]] — `TenantContext`, `get_current_tenant`
- [[backend/app/models/booking.py]] · [[backend/app/models/customer.py]] · [[backend/app/models/constants.py]]
- [[FastAPI]] — `APIRouter`, `Depends`, `Query`

## Depended On By

- [[backend/app/main.py]] — includes the router after the catalog router and constructs the service it resolves off `app.state`

## Concepts

- [[Tenant Resolution]]
- [[Tenant Context]]
- [[Rate Limiting]]

## Tests

- [[backend/tests/test_booking_owner_api.py]] — the route table, every handler, and the shadowing guard
- [[backend/tests/test_staff_role_gating.py]] — the default-deny walker reading `allowed_roles` off this router
- [[backend/tests/test_booking_owner_service.py]] — the service behind these handlers

## Notes

[[backend/app/auth/staff_router.py]] records a deliberate decision to keep a third local copy of `_no_store` rather than import it from here: `app.auth` importing `app.booking` would point the dependency arrow backwards, and hoisting three lines into a new shared module would touch two shipped files for cosmetics.

Design context: [[.planning/specs/owner-booking-management.md]].
