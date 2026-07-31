---
tags: [backend, db, python, booking, concurrency, idempotency, repositories, manage-token]
sources: [backend/app/db/repositories/bookings.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/db/repositories/bookings.py
blob: b2d17a71509e59eaf0ded3cf397479ede3ed820b
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/db/repositories/bookings.py

**Role.** The single writer for the `bookings` table — slot/seat claim, status graph, cancel, reschedule, manage-token mint-and-rotate, and the owner/storefront read paths — written so that overselling a slot is refused by two partial unique indexes rather than by any Python check, and so that every conditional write reports "matched nothing" through its own `RETURNING` rather than through a re-read.

**Module.** [[backend/app/db/repositories/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `BookingsRepository` | class | Stateless; `AsyncSession` passed per call |
| `insert` | method | Claims `(tenant, starts_at, seat_index)`; a lost race surfaces as `IntegrityError` |
| `by_id` | method | One live booking of this tenant, any status |
| `active_at` | method | This customer's non-cancelled booking at one instant — the idempotency probe |
| `active_seats_at` | method | `set[int]` of seat indexes occupied at one instant |
| `by_manage_token_hash` | method | The tokenized page's only read path; no status predicate |
| `set_manage_token_hash` | method | Mint-or-rotate, optionally guarded by `allowed_from` + `not_before` |
| `set_customer_id` | method | Re-points a booking at another customer row (phone-correction collision branch) |
| `confirm_attendance` | method | Stamps `attendance_confirmed_at`, idempotent by `IS NULL` predicate |
| `set_status` | method | The three non-cancel owner transitions, guarded by `allowed_from` + clock bounds |
| `cancel` | method | Sets `cancelled` + `cancelled_at` + `cancelled_by` in one guarded statement |
| `reschedule` | method | Moves `starts_at` and `seat_index` in place under the same indexes |
| `list_day` | method | Owner day list — page plus whole-day total, **cancelled rows included** |
| `list_live_for_customer` | method | Her future confirmed bookings — the set a phone correction must re-mint |
| `list_confirmed_without_manage_token` | method | The backfill feed; self-limiting on a second run |
| `count_by_start` | method | Per-instant occupied-seat counts for the public availability map |

## Behavior

**Oversell is structurally impossible, and the lock is about fairness, not safety.** `insert` deliberately does not pre-check the seat: `idx_bookings_slot_seat_unique` (migration [[backend/migrations/versions/0008_bookings.py]]) is the truth, and a pre-check would be a TOCTOU window. The flush raises `IntegrityError`, which [[backend/app/booking/service.py]] maps to `SLOT_UNAVAILABLE`. On top of that, **any caller that picks `seat_index` from `active_seats_at` must first hold `pg_advisory_xact_lock(hashtext(tenant_id))`** — skipping it does not cause an oversell (the index still refuses), it causes an honest customer to get a spurious 409 because the read and the write raced. `active_seats_at` and `active_at` both use `status <> 'cancelled'`, which mirrors the index predicates exactly: a no-show or completed booking still holds its seat, only a cancellation frees it, so a cancelled seat number can be handed back out instead of overflowing past capacity.

**Idempotency is the second index.** `active_at`'s predicate mirrors `idx_bookings_tenant_customer_starts_unique` (migration [[backend/migrations/versions/0009_booking_idempotency.py]]) exactly, so a hit is precisely a row that index would refuse to duplicate — which is what lets a replayed create return the existing booking rather than a second appointment. `scalar_one_or_none` is safe for the same reason: the index permits at most one.

**Every conditional write reads its own `RETURNING`, and that is not stylistic.** `cancel`'s docstring records why: `update(Booking)` on an `AsyncSession` is ORM-enabled DML whose default `evaluate` synchronization stamps the SET values onto the identity-mapped instance *whatever the database matched*, and the subsequent `by_id` hands that same instance back. So a re-read cannot tell your write from a concurrent one — an owner cancel that lost to a customer cancel would come back reading `cancelled_by='owner'` while the row says `customer`. Reading the `.returning()` scalar is the only way to learn that zero rows matched. `set_status`, `set_manage_token_hash`, `set_customer_id`, `cancel` and `reschedule` all follow this shape; `confirm_attendance` is the exception and ignores its result on purpose, because a repeat tap keeping the first timestamp is a success the caller should render, not a 409.

**Guarded by predicate, not read-then-write.** `cancel` is guarded on `status = 'confirmed'`, so a repeat cancel writes nothing and preserves the first cancellation's evidence. `confirm_attendance` is guarded on `attendance_confirmed_at IS NULL`, so a second tap keeps the *first* confirmation's timestamp instead of moving it. `set_status` takes `allowed_from` as the graph edge plus `not_after` (attendance verbs need a past appointment) or `not_before` (anything that only applies to a future one), and never writes `cancelled_at`/`cancelled_by` or `attendance_confirmed_at` — cancel keeps its own writer because it carries that evidence and is shared with the customer path, and `attendance_confirmed_at` means the bride said she is coming, not that the owner recorded an outcome. `cancel`'s `not_before` is owner-only: the customer path has already ruled out the started case in Python, and widening the predicate unconditionally would turn its 409 `BOOKING_ALREADY_STARTED` into a 200 rendering an un-cancelled booking.

**Cancel and reschedule both exploit the same index property.** Because both partial unique indexes exclude `status = 'cancelled'`, one `UPDATE` simultaneously returns the seat to the grid and re-opens the idempotency slot for a rebook at the same instant — no separate release statement exists. `reschedule` likewise needs no source-seat release: the indexes are re-evaluated over the row's new values, and a collision raises `IntegrityError` mapped to `SLOT_UNAVAILABLE` just like a lost create. `reschedule` returning `None` is meaningful: the advisory lock serializes it against public creates but **not** against the owner status endpoints, so zero rows means a concurrent cancel or no-show landed in between, and the service rolls back rather than committing an audit row for a move that never happened.

**Token paths.** `by_manage_token_hash` is the tokenized page's only read path — possession of a link, never an id — and rides `idx_bookings_manage_token` ([[backend/migrations/versions/0010_booking_comms.py]]). It carries no status predicate: a cancelled or past booking still answers its link, because an honest "this was cancelled" beats a dead link for someone re-opening her SMS; the service decides which *actions* remain legal. `set_manage_token_hash`'s `allowed_from`/`not_before` default to off so the backfill and reissue keep their original contract; the owner's edit-phone and resend pass `('confirmed',)` and `now`, so the same predicate the Python guard checked rides the rotation UPDATE and a booking that stopped being confirmed-and-future between the read and the write cannot be handed a fresh live control token.

**Read paths differ on cancelled rows on purpose.** `list_day` includes every status — a cancelled row is the owner's evidence that the slot re-opened — while `count_by_start` excludes cancelled because it mirrors the occupancy indexes. Both windows are `[from_instant, until_instant)`, half-open on the right so a caller can pass start-of-next-day without double-counting midnight, and both ride `idx_bookings_tenant_starts`. `list_day` issues two statements (page and unpaged `COUNT`) over the same window tuple, so the total can never drift from the filter.

Every method also carries an explicit `tenant_id` predicate and `deleted_at IS NULL`. The tenant predicate is redundant with FORCE RLS by design — defense-in-depth, per the class docstring.

## Depends On

- [[backend/app/models/booking.py]] — the ORM model
- [[backend/app/models/constants.py]] — `BookingStatus`
- [[SQLAlchemy]] — `select`, `update`, `func.count`, `AsyncSession`

## Depended On By

- [[backend/app/booking/service.py]] — public create (advisory lock + claim + idempotent replay)
- [[backend/app/booking/manage.py]] — the tokenized customer page
- [[backend/app/booking/owner.py]] — the owner console's status graph, cancel, reschedule, phone correction, resend
- [[backend/app/booking/comms.py]] — SMS confirmation and reminders
- [[backend/app/booking/backfill.py]] — mints manage tokens for pre-token rows
- [[backend/app/booking/slots_io.py]] — occupancy feed for the slot engine
- [[backend/app/booking/tokens.py]] — token hashing beside `by_manage_token_hash`
- [[backend/app/storefront/service.py]] — public availability

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Partial Unique Index]]
- [[Advisory Lock]]
- [[Soft Delete]]

## Tests

- [[backend/tests/test_booking_repositories.py]] — the direct round-trip suite: `test_slot_seat_unique_index_rejects_double_claim_and_frees_on_cancel`, `test_customer_instant_unique_index_and_active_at`, `test_cancel_answers_none_when_its_own_update_matched_nothing` (the ORM-DML trap above), `test_set_status_walks_the_reversible_pairs_and_returns_the_reread`, `test_reschedule_moves_both_columns_under_its_guard`, `test_reschedule_into_an_occupied_seat_raises_integrity_error`, `test_list_day_returns_the_whole_day_cancelled_rows_included`, `test_set_manage_token_hash_guard_refuses_a_stale_booking`, `test_set_customer_id_repoints_the_booking_under_the_same_guard`
- [[backend/tests/test_booking_isolation.py]] — `test_bookings_invisible_and_seats_uncontended_across_tenants`
- [[backend/tests/test_booking_service.py]] — the concurrency proof for the claim itself
- [[backend/tests/test_booking_owner_db.py]] · [[backend/tests/test_booking_owner_service.py]] — owner transitions
- [[backend/tests/test_booking_comms_db.py]] · [[backend/tests/test_storefront_integration.py]]

## Notes

`appointment_type_name`, `dress_name` and `dress_size` are denormalized snapshots stored on the booking, so soft-deleting a type or a dress does not rewrite what the customer agreed to. `terms_version_accepted` / `terms_accepted_at` are the same idea for [[backend/app/db/repositories/terms.py]].
