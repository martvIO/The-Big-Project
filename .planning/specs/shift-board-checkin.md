# Spec: F34 — Live shift board + check-in (5s poll) (Epic SMC, phase SMC-5)

**Created**: 2026-07-30 · **Revised**: 2026-07-30 (adversarial review: 12 of 13 findings applied, 3 of them BLOCKER — see *Review findings raised and REJECTED* for the one that was not) · **Status**: **Gate 1 self-approved under Interview Q1** (not a money or legal surface — F34 is not on Q1's enumerated exception list; the escalation raised at review was rejected, and the privacy hand-off it correctly identified is discharged to F20 at Risk 9) · **DESIGN GATE PENDING — the existing `shift-board/` deck, copy and prototype must be REVISED to this document before the user reviews them** (Interview Q2, novel pattern; D14's pause/idle control and D4.3's `{401,403}` terminal set are new since they were authored) · **Epic**: `.planning/epics/shift-manager-console.md` (SMC-5) · **Effort**: **M** — one nullable column, two thin endpoints on a router that already exists, two one-statement repository writers, two `AuditAction` members, and one new console section whose only hard part is a poll loop. Wall-clock time is nevertheless **user-bound, not build-bound**: the prototype gate parks the queue entry (`LOOP-STATE.md:194-196`), and F51–F53 fill the wait.
**Depends on**: **F15** (`owner_router.py`'s ten routes, `GET /manage/bookings?date=`, the `OwnerBookingRow`/`OwnerBookingDetail` pair, `OwnerMutation`, `lib/booking.tsx`, `lib/jerusalem.ts`) · **F31** (`require_role` at router level, and the default-deny walker that makes a new `/manage` route's authorization structural rather than remembered) · **Feeds**: **F50/SMC-6** (walk-in create lands on this board; a walk-in is `checked_in_at` at birth), **F52** (which owns the console's landing section)

**What F34 does *not* feed, corrected.** When F32 was subsumed, every downstream dep list naming it was rewritten to name F34 (`LOOP-STATE.md:339-361`), and F37's note still reads "Rides F34's 5s poll" (`LOOP-STATE.md:411`). **That inheritance is a documented pattern, not an executable substrate, and this spec ships nothing for F35/F37/F44 to import.** D13 keeps the loop inside `BoardSection.tsx`; and what F34 polls is `GET /manage/bookings?date=`, which structurally cannot carry a bell item or an SOS page — so there is nothing to ride even in principle. Each of F35/F37/F44 ships **its own endpoint and its own loop**, inheriting D4's six named mechanisms and the one interval constant by copying them, until a second caller makes the extraction reviewable (D13). Stated here because three later features are otherwise scheduled against a substrate that does not exist.

**F32 is subsumed here and must never be built** (`LOOP-STATE.md:339-356`, SMC ruling 3). There is no versioned board state, no realtime vendor and no `version` field: computing a version costs the same as answering the day in full, so the poll *is* the full refetch.

---

## Problem

F15 shipped the owner every booking operation and one way to see them: pick a Jerusalem day, get a list, tap a row. That is a desk screen. It answers "what is booked" and it cannot answer the two questions a shift manager asks fifty times a shift — **is she here yet**, and **has anything changed since I last looked**.

Both gaps are literal. `bookings` has no arrival column at all: the four timestamps on the row are `created_at`, `terms_accepted_at`, `attendance_confirmed_at` (written by the *bride*, through her SMS link — `bookings.py:204-224`) and `cancelled_at`. Nothing anywhere records that a person walked through the door. And `BookingsSection.tsx:27-49` fetches once per `[date, reload]`: two staffers on two phones diverge the moment either of them acts, and neither is told. F15's own Out-of-scope names this and hands it here — "**Real-time / a live board.** Refresh and poll are acceptable until E6" (`owner-booking-management.md:549`). This feature is that line's discharge.

The consequence is a boutique running its floor on shouting. A bride checks in at reception; the shift manager on the shop floor has no way to learn it; the seamstress upstairs has no way to learn it either, which is why E7's SOS and E9's workshop board both list this feature as their substrate. **Nothing in F34 is dangerous.** The dangerous surfaces in this area shipped with F15 and were acknowledged (its Risk 2); F34 adds no PII to any payload, no SMS, no money and no new authorization decision. What it adds is a request every five seconds, per phone, per shift — and *that* is the part of this document that gets argued.

## Goal

`apps/manage` gains a seventh section: the day's board. It opens on the current **Jerusalem** calendar day, lists every booking on it in `(starts_at, seat_index)` order, and converges on server state within five seconds of any change made by anybody — the owner cancelling from the «תורים» section, a bride cancelling through her SMS link, another staffer checking someone in. Each row carries one action: **check in**, and its undo. Check-in writes `bookings.checked_in_at`. The poll pauses when the tab is hidden and resumes with an immediate fetch. Two staffers tapping the same bride at the same instant both get a success and one timestamp.

**F34 ships one migration** — a single nullable `TIMESTAMPTZ` — **and no new error code, no new handler, no new SMS, no new router, no new limiter, and no second materializer of any question the codebase already answers.**

## What already exists to build on (verified against code)

- **The board's data endpoint is already shipped and already correct for this.** `GET /manage/bookings?date=` (`owner_router.py:154-181`) converts a Jerusalem calendar date to a `[midnight, next-midnight)` UTC pair through the DST-safe arithmetic `list_day` documents (`owner.py:150-189`), returns **every status including cancelled** as a deliberate constant rather than a `?status=` parameter (`bookings.py:369-394`), and orders by `(starts_at, seat_index)`. It rides `idx_bookings_tenant_starts` (`0008_bookings.py:95-98`). The board needs no new read.
- **The router already sets `no-store` at router level.** `dependencies=[Depends(_no_store), …]` (`owner_router.py:78-84`), so `cache-control: no-store` is on every response by construction (`owner_router.py:61,69-70`). That is load-bearing for a poll and not merely hygiene: without it a proxy or the browser could serve a stale 200 and the board would freeze *while looking alive* — the one failure a live board must not have.
- **Authorization is already structural and already admits both roles.** `Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))` sits at router level (`owner_router.py:82`), the gate fails closed on any role the enum does not know (`auth/dependencies.py:40-62`), and `test_staff_role_gating.py`'s walker reads `allowed_roles` off the **live** route table — so a route added to this router inherits the gate and is policy-checked with no new test. Role changes bite on the next request because `resolve_session` re-reads `staff_users` and writes nothing (`auth/service.py:87-95`).
- **The idempotent-timestamp *predicate* has a precedent in this exact table — but not the concurrency answer.** `BookingsRepository.confirm_attendance` guards `attendance_confirmed_at IS NULL` so "a second tap keeps the FIRST confirmation's timestamp rather than moving it" (`bookings.py:204-224`), and F34 copies that predicate shape verbatim. **It stops there.** `confirm_attendance` never returns `None` for zero rows — it unconditionally `return await self.by_id(...)` — and `ManageBookingService.confirm_attendance` (`manage.py:123-141`) renders whatever comes back, because a bride re-tapping her own link has exactly one possible meaning. Check-in has two, so it needs a discrimination that precedent deliberately declines. **The governing precedent is `cancel`'s instead** (`bookings.py:287-295`): the `.returning()` scalar is the only honest signal that a write happened, and an ORM re-read cannot substitute for it. D4(5) is where that is spent.
- **The transition discipline is written out.** `_transition` runs load → compare (`status == to` ⇒ 200, `changed=False`, **no audit row**) → raise 409 → guarded write → audit, all in one `tenant_session`, with the reason step 4 is not redundant with step 3 spelled out in the code (`owner.py:234-356`). `OwnerMutation(booking, changed, manage_token)` is the shape every mutation answers (`owner.py:95-113`).
- **`audit_log` needs no migration for new actions.** `action` is plain `TEXT` with no CHECK (`0003_auth.py:71-79`), the table has full CRUD under FORCE RLS (`0003_auth.py:83-86`), and `AuditLogRepository.record` joins the caller's transaction (`db/repositories/audit_log.py:11-30`). `AuditAction` already carries seven F15 members added on exactly this basis (`models/constants.py`).
- **The frontend helpers exist and are already shared.** `lib/booking.tsx` holds `statusBadge` (a five-variant map with `danger` deliberately absent, status never signalled by colour alone), `isolateLtr` and `bookingErrorText` — and its header records *why* they live in `lib/` rather than on a component (BookingsSection → BookingDetail → RescheduleDialog is already an import chain and shared helpers on either end would close it into a cycle). `lib/jerusalem.ts` holds `jerusalemTime`, `jerusalemIsoDate` and `todayJerusalem`, every formatter passing `timeZone: JERusalem` imported from `@boutique/ui`.
- **The section mechanism is four lines.** `apps/manage` has no router: `SectionKey` is a union, `nav` is an array, and the body is a render branch (`App.tsx:14, 50-56, 74-80`). F15 appended the sixth item this way.
- **The list→patch contract is shipped and reusable verbatim.** Every mutation answers `OwnerBookingDetail`, which extends `OwnerBookingRow`, so a mutation response *is* a list row and `BookingsSection.tsx:74-78` patches in place without a refetch. `apiFetch` throws `ApiError {status, code, message}`.
- **`ar.ts` exists in the console and expects to grow.** Its header states the rule this feature inherits: values are the approved Hebrew standing in untranslated, never empty strings (i18next's `returnEmptyString` renders `""` rather than falling back), `lng` stays `"he"`, and "later console features append theirs".
- **The session outlives a shift, but only just.** `session_ttl_seconds = 60 * 60 * 12` (`core/config.py:24`) and `resolve_session` performs **no sliding renewal** — it reads, it never writes. A board left open longer than twelve hours starts answering 401. D4 handles it.

## Design

### D1 — Check-in is a column, not a fifth status

`bookings.checked_in_at TIMESTAMPTZ NULL`, plus the matching `mapped_column` on `models/booking.py` (D2 — the migration alone is half the change). The status CHECK, both partial unique indexes and E4's future `pending_payment` widening are untouched, and the migration proves it mechanically.

The tempting alternative is a fifth `BookingStatus`, and it is tempting because it looks like less: one CHECK widening, one enum member, no new column, and the board could then read status alone. **It breaks the product.** Verified against the code, not asserted:

- `bookings.status` is `CHECK (status IN ('confirmed','cancelled','no_show','completed'))` (`0008_bookings.py:66-67`) and **eight** shipped guards read `= 'confirmed'` or enumerate that exact set: `BookingsRepository.cancel` (`bookings.py:302-307`), `reschedule` (`:343-354`), `confirm_attendance` (`:211-222`), `list_live_for_customer` (`:403-414`), `list_confirmed_without_manage_token` (`:416+`), the three `allowed_from` tuples in `owner.py:250-293`, and `ManageBookingService`'s branches on the customer's own token page. A bride whose status became `checked_in` could no longer be cancelled by anyone, could no longer be rescheduled, and her SMS page would fall through every branch it has.
- Both partial unique indexes key on `status <> 'cancelled'` — `idx_bookings_slot_seat_unique` (`0008:88-92`) and `idx_bookings_tenant_customer_starts_unique` (`0009:32-36`) — and 0008's comment states the invariant a fifth status must respect: "a no-show or completed booking still OCCUPIED its seat, and only a cancellation frees it. That is also what keeps this index correct when E4 adds `'pending_payment'`". A `checked_in` status happens to satisfy that, which is exactly what makes the trap quiet: the indexes would stay correct while the guards silently stopped matching.
- E4 has a reserved widening on this CHECK (`constants.py`, `BookingStatus`: "E4 widens it with `'pending_payment'`"). Two features widening one CHECK in sequence is two chances to disagree about what the set means.

Status answers *what became of the appointment*. Check-in answers *whether a person is in the building*. They are orthogonal — a bride is checked in and then `completed`, and both facts are true simultaneously — and orthogonal facts in one enum is the shape that forces the impossible-tuple conversation later.

**Also declined, and this is the cheapest-looking wrong answer: reusing `attendance_confirmed_at`.** It is already a nullable timestamp on `bookings`, so it needs no migration at all. It is written by the **bride**, through her tokenized manage link, guarded `IS NULL AND status = 'confirmed'` (`bookings.py:204-224`); it already renders on F15's list as its own cue (`BookingsSection.tsx:168-172`); and F15's `/confirm` deliberately refuses to touch it, in writing — "`attendance_confirmed_at` is F16's column and means the BRIDE said she is coming, so the owner correcting her own record of the outcome does not get to speak for her" (`owner.py:250-259`). Overloading it would make a staffer's tap speak for the bride, and would make a cue that ships today ambiguous on a screen that ships today. One column is cheaper than that.

Declined too: a `check_ins` table (one nullable timestamp per booking needs no table; the undo would become a soft-delete with its own RLS policy, its own grants and its own F20 retention row) and an index on `checked_in_at` (nothing filters or sorts on it — the board reads the day and renders the value, so a partial index would serve no reader and cost every write).

### D2 — One migration, one ORM column — and the revision id is *not* pinned here

**The revision id and `down_revision` are resolved at build time from `alembic heads`, not from this document.** HEAD is `0011_staff_roles.py` today (`revision = "0011"`, `down_revision = "0010"`), so a naive reading gives 0012/0011 — but this feature **parks on the user's prototype gate and F51–F53 fill the wait** (`LOOP-STATE.md:194-201`), and F53's queue entry carries a migration of its own ("customers.notes TEXT + tags TEXT[] (migration)", `LOOP-STATE.md:234`). 0012 is therefore very likely taken before F34's build resumes. The build step is: read `alembic heads`, take the next number, revise whatever HEAD then is. Everything below keyed to "0012" means **"this feature's migration"**, and the pinned assertions in D2's test are keyed to *after this feature's migration* rather than after any literal.

```python
"""booking check-in: the arrival timestamp the live board writes

Revision ID: <next after `alembic heads` at build time>
Revises:     <whatever HEAD is at build time — NOT hardcoded 0011>
"""

def upgrade() -> None:
    # When a staff member recorded that this person is physically in the
    # boutique. NOT a fifth BookingStatus (spec D1): status says what became of
    # the appointment, this says whether she is in the building, and the two are
    # true at once. NULL means "not arrived (yet)" and is the only sentinel —
    # there is no 'left' timestamp in v1.
    op.execute("ALTER TABLE bookings ADD COLUMN checked_in_at TIMESTAMPTZ")

def downgrade() -> None:
    op.execute("ALTER TABLE bookings DROP COLUMN IF EXISTS checked_in_at")
```

That is the entire DDL. Deliberately absent, each for a verified reason:

- **No `GRANT`.** `0008_bookings.py:107-110` issued table-level `GRANT SELECT, INSERT, UPDATE, DELETE ON bookings TO app_user`; table grants are column-agnostic and no column-level grant was ever issued on this table. (The `.claude/CLAUDE.md` `ALTER DEFAULT PRIVILEGES` gotcha is about newly *created* tables, not added columns.)
- **No `enable_tenant_rls`.** RLS is a table property, already forced by 0008, and `test_every_tenant_id_table_has_forced_rls` stays green because F34 adds no table.
- **No `_updated_at_trigger`.** `trg_bookings_updated_at` exists from `0008:105`.
- **No index, no CHECK, no default.**

**The ORM model is the second half of this migration, and it is not optional.** `Backend/app/models/booking.py:26-53` declares **every** column explicitly as `mapped_column` — nothing in this repo derives a mapping from a migration, and no model↔migration parity test exists over `Backend/tests/` to catch the gap. So the same change adds, beside `attendance_confirmed_at` (`:33-35`, the exact shape to copy):

```python
# When a staff member recorded that this person is physically in the boutique.
# NULL = not arrived (yet), and it is the only sentinel. NOT a fifth
# BookingStatus (D1): status says what became of the appointment, this says
# whether she is in the building, and the two are true at once.
checked_in_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
```

Without it, `update(Booking).values(checked_in_at=at)`, `Booking.checked_in_at.is_(None)` and `booking.checked_in_at` in `_row_fields` are every one of them an `AttributeError` or a compile failure — i.e. **every backend line D5 and D6 specify fails to import.** Migration + ORM model are one atomic change here, the two-halves pattern `0008_bookings.py` / `models/booking.py` already follow.

**What this migration must prove it did not do.** The brief's demand — the status CHECK and both partial unique indexes stay untouched — becomes a db-marked test rather than a promise: `test_migrations.py` reads `pg_get_constraintdef` for the status CHECK and `pg_indexes.indexdef` for both unique indexes **after this feature's migration** and pins all three against literals. This is the highest-value test in the feature, because the thing it guards against is a *future* edit: when E4 widens the CHECK for `pending_payment` it will collide with a pinned literal and a deliberate edit, instead of colliding with nothing.

### D3 — The board is a client 5-second poll of `GET /manage/bookings?date=`, and there is no version field

The board runs `GET /manage/bookings?date=<today, Jerusalem>&offset=0&limit=50` every five seconds and replaces its rows with the answer. No new endpoint, no delta, no `If-None-Match`, no `?since=`, no `version`.

**Why no version.** SMC ruling 3 settles it and the arithmetic backs it: answering "has anything changed" honestly requires reading the same day's rows the answer would contain, so a version endpoint is the full query plus a hash. Pre-decided #25's "events are versioned hints, server is truth" and `architecture.md:12`'s Pusher line describe a substrate that does not exist and that this feature is ruled not to build; what survives of them is the part that matters — **the server is the truth and the client holds no derived state** — and a full refetch every five seconds satisfies it more completely than a version gap ever could, because there is no gap to miss.

**Why not ETag / 304.** It would halve the bytes and change nothing that costs: the query still runs, the session still resolves, the row still serialises before the hash. And it would fight `no-store`, which D-nothing gets to weaken (`owner_router.py:10-13`).

**Why five seconds, and what it costs — counted off the code path, not off the handler.** The naive count is five queries (two for the session, two for `list_day`, one for `customers.by_ids`) and it is **~3× too low**, because it omits everything the request does before and around the handler. Per tick, per device:

| Per tick | Count | Where |
|---|---|---|
| Sessions opened | **4** | `tenants.by_slug` (its own session, `db/repositories/tenants.py:36-45`) → `resolve_session` → `list_day` → `customers_for` |
| `SELECT set_config(...)` + explicit BEGIN/COMMIT | **3** of each | `tenant_session` wraps each of the three tenant-scoped sessions (`db/tenant.py:25-29`) |
| `SELECT 1` on pool checkout | **4** | `pool_pre_ping=True` (`db/session.py:59`) |
| Business SQL | **5** | session ×2, `list_day` page + count, `customers.by_ids` |
| **Total** | **~9 SQL statements, ~17 round trips, 4 pool checkouts** | |

Ten phones on one tenant is 2 req/s and **~90 statements/s**, not ~10; 50 tenants × 3 devices is 30 req/s and **~270 statements/s**, not ~150.

**The highest-leverage lever is `tenants.by_slug`**, and it is already assigned: `TenantsMiddleware` calls the resolver on **every** non-exempt request (`tenancy/middleware.py:74`; `EXEMPT_PATHS` is `/health` plus docs only), and `RepositoryTenantResolver`'s own docstring says "Direct indexed lookup per request … Caching is deliberately deferred to E5" (`tenancy/resolver.py:8-9`) — which is pre-decided #21's F29 caching row. One uncached indexed read per tick per device is the single cheapest thing to delete. Risk 2 exists to hand F29 a number rather than let it discover one, so it hands over **this** number, and the 4 pool checkouts per request against the default `QueuePool` size besides.

**No throttle on the read, and D6's reasoning is now weaker but still right.** F15 declined a limiter on this router because "a per-tenant read budget there is a self-DoS with no attacker on the other side of it" (`owner-booking-management.md:173`). A poll makes the traffic real, but it does not make an attacker: the caller holds a live session for this tenant, is CSRF-fenced, and can already spend more by holding the tab open than by abusing anything. A budget here would mean a board that stops updating mid-shift because too many staffers were looking at it — a limiter whose only reachable victim is the feature it protects. Declined; recorded as Risk 4 with F29 as the trigger.

**But declining the server-side limiter obliges the client to throttle itself, and the first draft did neither.** With no server ceiling *and* no client backoff, a backend outage means every open board retries every five seconds indefinitely — unthrottled at both ends, exactly when the server is least able to answer. **D4(6) is the discharge**: consecutive failures back the interval off to a ~60s cap, the first success resets it. That is the honest completion of this paragraph, not a contradiction of it — the limiter was declined because there is no attacker, and the backoff exists because there is no attacker either, only a fleet of loyal clients pointed at a sick server.

**`limit=50` and the truth when it is not enough.** `BOOKING_LIST_DEFAULT_LIMIT` is 50 and the board asks for it — three times headroom over a full boutique day (eight hours × two parallel seats ≈ 16 fittings). The board does **not** hardcode `BOOKING_LIST_MAX_LIMIT`: the router declares `limit: Annotated[int, Query(ge=1, le=BOOKING_LIST_MAX_LIMIT)]` (`owner_router.py:168`), so a client pinned to today's ceiling would start 422-ing the day the ceiling is lowered, which is exactly the silent client/server drift `test_frontend_constant_parity.py` exists to catch — and it guards `validation.ts` files only, so this constant would be unguarded. Instead: ask for 50, and when `total > items.length` render one line saying so and pointing at the «תורים» section. A hidden bride is the one failure a board may not have, so the truncation is stated rather than absorbed. No new row in `MIRRORS`.

### D4 — The poll's six failure modes, each with its mechanism

This is the part of the feature that can be subtly wrong, so each case gets a named answer rather than a library.

1. **Overlapping requests.** The loop is **schedule-after-settle**, not `setInterval`: the next tick is armed from the previous request's `.finally()`. At most one poll is in flight per tab *by construction*, so there is nothing to abort and no in-flight flag to get wrong. Declined: `setInterval` plus an `AbortController` (two mechanisms and a cancellation path to test, to reproduce a property one `setTimeout` gives free) and any `useSWR`/`react-query` dependency (a data-fetching library for one polled endpoint in an app whose other five sections are hand-written `fetch`).

2. **A slow response landing after a newer one.** Impossible between two polls, by (1). It remains possible between a poll and a **mutation**, which is case (4). One monotonic `generationRef` covers both: every poll captures the generation at issue time and applies its result only if the generation is unchanged. The date roll and the manual retry bump it too, so a poll issued for yesterday can never paint today's board.

3. **The tab backgrounded for an hour.** `document.hidden` pauses the loop (brief-mandated, and honest independently: browsers already throttle background timers to ≥1/minute, so an unpaused loop would silently become a slow loop and the board would look live while being a minute stale). On `visibilitychange` back to visible the board fetches **immediately** rather than waiting out a five-second tick — it is stale by however long it was hidden, and five more seconds of a wrong board is the worst moment to add. **And the twelve-hour case is real:** `session_ttl_seconds` is 43200 with no sliding renewal (`config.py:24`, `auth/service.py:87-95`), so a tab left on the counter overnight wakes to a 401.

   **The terminal set is `{401, 403}` — not `{401}`, and the difference is F31's whole guarantee.** The two revocation paths diverge in code and only one of them ends in a 401:
   - **Deactivation** → `staff_users.by_id` filters `deleted_at.is_(None)` (`db/repositories/staff_users.py:25-33`) → `resolve_session` returns `None` (`auth/service.py:87-95`) → **401**.
   - **Demotion** (the role changed to one this router does not admit) → the session still resolves fine, and `RoleGate.__call__` raises `NotAuthorizedError` (`auth/dependencies.py:57-62`) → **403**.

   `RoleGate`'s own docstring promises that "role changes and deactivations bite on the very next request … there is no session state to sweep" (`auth/dependencies.py:46-48`). A board that stops only on 401 keeps polling at 0.2 req/s forever after a demotion, showing a generic error while the demotion has **no visible effect** — silently defeating that guarantee on the one screen in the product that keeps making requests after a revocation. And F51, the feature that makes demotion possible at all, merges *during* F34's park (`LOOP-STATE.md:194-201`). Nothing catches this above the component: no 401 or 403 handling exists anywhere in `apps/manage` today (`grep -rn "status === 401\|status === 403\|NOT_AUTHORIZED" Frontend/apps/manage/src` is empty).

   So: **one branch on `ApiError.status` (`api.ts:9-19`) covering both 401 and 403 stops the loop** and shows the session-or-permission-ended alert with a reload affordance. Without that rule a dead or demoted tab hammers `/manage/bookings` every five seconds forever. The copy must cover both causes honestly — the 403 body is generic by design (`auth/dependencies.py:17-21`: one body for every unadmitted role, so a probe cannot learn which roles exist), so the client cannot and must not tell the staffer *which* role she now holds. Declined: lifting the 401/403 into `App.tsx`'s `staff` state to force the login screen (it needs a prop threaded through `ConsoleShell`'s children for a case a reload already solves, and it would silently discard whatever the owner had typed elsewhere).

4. **Optimistic check-in versus the poll overwriting it. The board is not optimistic, deliberately.** The POST answers the full `OwnerBookingDetail` — the F15 contract every mutation already keeps — so the row is patched from the *server's* row, the `BookingsSection.tsx:74-78` shape exactly. Two rules close the window: the loop **does not issue a tick while a mutation is in flight**, and the mutation's settle **bumps the generation**, which discards the one poll that could still be in the air (the one issued before the tap). An optimistic tick would buy one round-trip of perceived speed on boutique wifi and pay for it with a check-mark that un-ticks on a 409 — on the one surface whose entire job is answering "is she here". The tapped button carries `disabled={busy}` (the `BookingDetail.tsx` pattern) so a double-tap does not fire twice; and even if it does, (5) makes the second call a no-op.

   **And the suppressed tick must be re-armed, or the board stops converging the first time anybody checks anybody in.** (1) names exactly one arming site — the previous request's `.finally()` — and this rule suppresses a tick with no stated re-arm; a board that silently stops the moment a staffer acts would pass every other test in this document, on the one surface whose entire job is answering "has anything changed". The rule that closes it needs no second timer, because **the mutation *is* the in-flight request: its `.finally()` is "the previous request's `.finally()`" and arms the next tick**, exactly as a poll's would. Same single arming site, same at-most-one-in-flight-by-construction property. This holds for a **failed** mutation too — a rejected check-in must not park the loop either — so the arming lives in the mutation's `.finally()`, never in its success path.

5. **Two staff check the same bride in at once.** Idempotent by predicate: the UPDATE carries `checked_in_at IS NULL`, so the second writer matches zero rows, writes nothing, and **keeps the first staffer's timestamp**. Zero rows must then be discriminated, because the two ways to match nothing mean opposite things — already checked in ⇒ **200, unchanged, `changed=False`, no audit row** (the outcome the caller wanted is the outcome that holds; the audit row belongs to the staffer who actually wrote it, and a 409 here would be a lie told to the person who was right); no longer `confirmed`, somebody cancelled her in the gap ⇒ **409 `BOOKING_TRANSITION_INVALID`**, nothing written.

   **The discrimination must be read off the database, and an ORM re-read cannot supply it.** This is the trap the repo has already been bitten by once and documented three times. `update(Booking)` on an `AsyncSession` is ORM-enabled DML whose default `evaluate` synchronization stamps the SET values onto the identity-mapped instance **whatever the database matched**, and the session factory is built `expire_on_commit=False` (`db/session.py:66`) inside one `tenant_session` transaction (`db/tenant.py:25`), so a trailing `by_id` hands back that same in-memory object without overwriting its already-loaded attributes. `cancel`'s docstring says it in full (`bookings.py:287-295`), `owner.py` says it at `:325-333`, `:401-408` and `:538-546`, and `test_booking_owner_db.py:747-760` pins it with a docstring that is verbatim this bug: *"Reading the re-fetched row therefore cannot answer 'did I do this?'"*.

   So a naive `if booking.checked_in_at is not None` after the write is decided by **the value this request just wrote in memory, never by the database**. It fires for *both* zero-row causes: the 409 branch is unreachable, and a check-in that lost to a concurrent cancel answers a false 200 "she is checked in" while the row is cancelled with `checked_in_at IS NULL` — a check-mark on a cancelled booking with no audit row behind it. **The same poisoning corrupts the render**: the losing writer's in-memory row carries *its own* timestamp, so a 200-unchanged built from it would show the second staffer's time, not the first's — contradicting the guarantee this very case exists to make.

   **The mechanism: the repository does the discrimination, off a re-read that defeats the identity map.** After the guarded UPDATE, the writer re-reads with `select(Booking).where(tenant_id, id, deleted_at IS NULL).execution_options(populate_existing=True)` — `populate_existing` overwrites the identity-mapped instance's attributes from the row the database actually holds, and under READ COMMITTED that statement sees the other transaction's commit. One statement, one documented flag, and it fixes discrimination and rendering together. The writer returns a three-valued outcome plus the refreshed row, so **the service branches on database truth and never on the object it just mutated** (shapes in D5). A column-only Core `select(Booking.status, Booking.checked_in_at)` would answer the discrimination equally well but leaves the entity poisoned for rendering, so it would need a second re-read anyway.

   **The `confirm_attendance` precedent is cited nowhere in this feature, and that is a correction.** `BookingsRepository.confirm_attendance` (`bookings.py:204-224`) never returns `None` for zero rows — it unconditionally `return await self.by_id(...)` — and `ManageBookingService.confirm_attendance` (`manage.py:123-141`) renders whatever comes back. It *deliberately declines* the discrimination check-in needs, because a bride re-tapping her own link has only one possible meaning. The governing precedent is `cancel`'s rule instead: **`None` off the `.returning()` scalar is the only honest signal that a write happened**, and everything after it must come from a fresh read.

   No advisory lock. F15 takes `pg_advisory_xact_lock(hashtext(tenant_id))` for the reschedule because it *picks a seat from a count* (`bookings.py:38-43`); check-in reads and writes one column on one row and has no cross-row invariant to serialise. Adding the lock would serialise every check-in in the boutique against every public booking create, for nothing.

6. **The backend is down, or slow, or 500-ing.** Not a case the first draft enumerated, and the omission is load-bearing: with no backoff, every open board retries every five seconds indefinitely during an outage — unthrottled at both ends, precisely when the server is least able to answer. There is no server-side ceiling to catch it either: every `FixedWindowRateLimiter` in `main.py` is login / terms / presign / storefront / phone / tenant / verify / create / lookup / sms, and D3 declines a read limiter for reasons that remain right. So the throttle is the client's. **Consecutive failed ticks back the interval off — 5s doubling to a ~60s cap — and the first success resets it to 5s.** It lives in the same `.finally()` that already arms the next tick (D4.1), so it is three lines and no new mechanism, and it is the same lever Risk 2 already names as the cheap one. A 401 or 403 is not a "failure" for this purpose — those are terminal by (3) and stop the loop outright rather than backing it off.

### D5 — Two endpoints on F15's existing owner router

```
POST /manage/bookings/{booking_id}/check-in        -> OwnerBookingDetail
POST /manage/bookings/{booking_id}/undo-check-in   -> OwnerBookingDetail
```

Same router (`app/booking/owner_router.py`), same verb-sub-path convention as the shipped `/no-show`, `/complete`, `/resend-link` (D7's ruling: path parameters and real HTTP verbs are the `/manage` convention; the `.claude/rules` RPC guidance is Kotlin boilerplate for another codebase). Same `OwnerBookingDetail` answer, so the board patches its row from the response and cannot disagree with itself. Both inherit `_no_store` and the router-level `RoleGate` — **owner and shift_manager both admitted**, and neither joins `test_staff_role_gating.py`'s `OWNER_ONLY` set, because a board a shift manager cannot act on is not a shift manager's board (SMC's locked matrix: owner-only is staff management and `POST /manage/terms`, nothing else).

Declined: one `POST .../check-in` with a `{"checked_in": bool}` body. Two verbs, two guards (check-in requires `status = 'confirmed'`; the undo requires nothing), two audit actions, two payload shapes for `details` — one handler would collapse all of that into a body of `if`s, which is the argument D7 already made against a single `PATCH` carrying `status`.

**Service methods** on the existing `OwnerBookingService`, in one `tenant_session` each, the `_transition` five-step shape:

```python
async def check_in(self, tenant_id, booking_id, *, staff) -> OwnerMutation
async def undo_check_in(self, tenant_id, booking_id, *, staff) -> OwnerMutation
```

`check_in`: load (missing ⇒ 404 `BookingNotFoundError`) → `checked_in_at is not None` ⇒ 200 unchanged, no audit row → `status != 'confirmed'` ⇒ 409 → guarded write → **branch on the repository's outcome, never on the loaded object** (D4(5)) → audit row only on `WROTE` → commit.

The two Python pre-checks are step 2 and step 3 of `_transition`'s shape and they stay — they are what makes the *answer* honest in the uncontended case (`owner.py:244-249`). What changed is step 4's aftermath: it is the repository, not the service, that says which of the three things happened, because only the repository is holding the `.returning()` scalar and the refreshed row at the same moment.

**No clock bound on check-in, in either direction.** A bride arrives twenty minutes early and that is the ordinary case the board exists for; a `starts_at <= now` guard would refuse it. An early arrival is not a lie, it is a fact with a timestamp.

`undo_check_in`: load (missing ⇒ 404) → `checked_in_at is None` ⇒ 200 unchanged, no audit row → clear it → `WROTE` ⇒ audit row carrying `previous_checked_in_at`; anything else ⇒ 200 unchanged, no audit row, rendering the **refreshed** row (D4(5)'s re-read applies here too — a concurrent undo must render the database's NULL, not this request's stamped one). **The undo has no failure mode except 404, and no status guard at all** — the `/confirm` precedent, which takes no clock bound because "a mis-tap is correctable whenever it is noticed" (`owner.py:253-259`). A bride checked in and then cancelled must still have the mis-tap undoable; refusing it would leave a permanent wrong arrival record with no remedy on a surface where the tap is one finger wide.

**A status transition never touches `checked_in_at`.** Marking a checked-in bride `no_show` looks contradictory and the temptation is to clear the timestamp inside `set_status`. Declined: it would make F15's one status writer do two things, it would destroy the only record of an arrival as a side effect of an unrelated verb, and it presumes the owner meant the arrival was wrong when she may have meant the bride left. The explicit undo is the remedy. Asserted by a db-marked test, so the absence is a decision rather than an oversight.

**Repository writers** — two. Each is a guarded UPDATE plus one identity-map-defeating re-read, and **each returns an outcome rather than a bare row**, because a `Booking | None` cannot express the three answers this caller needs (D4(5)):

```python
class CheckInOutcome(StrEnum):
    WROTE                = "wrote"                 # the predicate matched; this request wrote it
    ALREADY_CHECKED_IN   = "already_checked_in"    # zero rows, and the DB says she is checked in  -> 200 unchanged
    NOT_CONFIRMED        = "not_confirmed"         # zero rows, and the DB says status != confirmed -> 409
    MISSING              = "missing"               # the row is gone / soft-deleted                 -> 404

async def check_in(
    self, session, tenant_id, booking_id, *, at: datetime
) -> tuple[CheckInOutcome, Booking | None]:
#   1. UPDATE bookings SET checked_in_at = :at
#        WHERE tenant_id AND id AND checked_in_at IS NULL
#              AND status = 'confirmed' AND deleted_at IS NULL
#        RETURNING id
#      -> the scalar is the ONLY honest "did I write?" (cancel's rule, bookings.py:287-295)
#   2. re-read: select(Booking).where(tenant_id, id, deleted_at IS NULL)
#                 .execution_options(populate_existing=True)
#      -> refreshes the identity-mapped instance from the row the DB actually holds,
#         undoing `evaluate` synchronization's stamp. Correct render AND correct branch.
#   3. classify from (scalar, refreshed row), never from the caller's loaded object.

async def undo_check_in(
    self, session, tenant_id, booking_id
) -> tuple[CheckInOutcome, Booking | None]:
#   WHERE tenant_id AND id AND checked_in_at IS NOT NULL AND deleted_at IS NULL  RETURNING id
#   Same re-read. The undo has no 409 (D5's no-status-guard ruling), so it only ever
#   answers WROTE / ALREADY_CHECKED_IN (read as "already clear") / MISSING — but it uses
#   the same refreshed read so a concurrent undo renders the DB's NULL, not its own.
```

The `.returning(Booking.id)` scalar is `set_status`'s and `cancel`'s convention unchanged; what is new is that the row handed back beside it is **refreshed**, which neither of those two needed because neither had to answer a three-way question.

### D6 — `checked_in_at` joins the row shape, and F15's detail renders it

`OwnerBookingRow` gains `checked_in_at: datetime | None` (`booking/schemas.py`), which `OwnerBookingDetail` inherits by subclassing, and `_row_fields` in `owner_router.py:99-110` gains one line. The board needs it on the **row**, because the board only ever reads the list.

That unavoidably touches F15's surface, and the SMC epic says the bookings section is "F15's, untouched". **Recorded as a conflict and read narrowly**: "untouched" scopes re-design and re-scoping, not the byte-level immutability of a shared wire shape — a new column that the console cannot see anywhere would be the stranger choice. So F15's `BookingDetail.tsx` renders one `<Fact>` when `checked_in_at !== null`, the same three-line treatment `cancelled_at` already gets (`BookingDetail.tsx:365-369`). **The check-in control does not appear there** — the action lives on the board, one place, and the detail states the fact.

Two shipped assertions red-fail on this field and that is the point of them: **`test_booking_owner_api.py:502`** (the detail, `test_the_detail_carries_the_phone_the_notes_and_the_terms_evidence`) and **`:422-432`** (the list row, inside `test_the_list_applies_the_documented_defaults` at `:409` — `assert body["items"] == [ … "attendance_confirmed_at": None … ]`). The plan updates both literals as a visible, reviewed edit.

**`:657` is *not* one of them**, and an earlier draft of this spec named it. That line is `test_the_owner_slot_grid_carries_capacity_and_remaining` (`:649-664`) and its literal is `{"slots": [{"starts_at": …, "capacity": 2, "remaining": 1}]}` — no booking fields at all, so `checked_in_at` cannot touch it. The list-row literal — the one the board actually consumes — is the one that was missing. Corrected here so the plan updates the payload that breaks rather than the one that does not, and is not surprised by a third.

### D7 — Zero new error codes, zero new handlers

The **client consequence** column is not decoration: D4.3's terminal set is defined here, and the first draft of this table listed 403 with no consequence at all — which is how the poll ended up retrying a demotion forever.

| Condition | Status | Code | New? | Client consequence (D4.3) |
|---|---|---|---|---|
| Unknown booking id (incl. another tenant's, indistinguishable under RLS) | 404 | `NOT_FOUND` | no — `BookingNotFoundError` subclasses `DomainNotFoundError`, handler bound to the base (`main.py:463-465`) | mutation failure cue; **loop continues** |
| Check-in on a booking that is not `confirmed` | 409 | `BOOKING_TRANSITION_INVALID` | no — F15's, handler at `main.py:604-608` | mutation failure cue; **loop continues** (the next tick corrects the row) |
| Repeat check-in, repeat undo, undo of a never-checked-in booking | **200** | — | not errors, by D4(5)/D5 | success; row patched from the server's row |
| No session cookie, or an expired one | 401 | `NOT_AUTHENTICATED` | no — app-wide | **TERMINAL — loop stops**, session-ended alert + reload |
| A role outside `{owner, shift_manager}` — i.e. a **demotion mid-shift** | 403 | `NOT_AUTHORIZED` | no — F31's, generic body (`auth/dependencies.py:17-21`) | **TERMINAL — loop stops**, same alert + reload. Without this row the board polls a revoked role forever and F31's "demotion bites on the next request" is silently defeated |
| Mutating `/manage` request from a foreign origin | 403 | `CSRF_ORIGIN_MISMATCH` | no — `csrf.py:15-16,48` | unreachable from the console's own origin; falls into the same terminal branch if it ever fires, which is the safe direction |
| Backend down / 5xx / network | — | — | no | **not terminal** — backoff per D4(6), stale-but-labelled rows |

`SPEC_ERROR_CODES` in `test_booking_owner_api.py:110-120` is asserted by **set equality**, and F34 adds no member to it — which is a real result and not an accident of laziness. `BOOKING_TRANSITION_INVALID`'s docstring already scopes itself to "an illegal status pair … and resend/phone/reschedule on a booking that is not confirmed-and-future" (`owner.py:61-69`); check-in on a cancelled booking is the same sentence. Declined: `BOOKING_ALREADY_CHECKED_IN` — a repeat check-in is a 200 by D4(5), so the code would name a condition that never answers an error, and `main.py` has no error registry (an unmapped typed error is a bare 500), so every code invented here is a handler somebody has to remember.

### D8 — Two `AuditAction` members, and the undo's `details` carry the value it destroys

| Member | Value | Written by | `details` |
|---|---|---|---|
| `BOOKING_CHECKED_IN` | `booking_checked_in` | check-in that actually wrote | `{"checked_in_at": "…Z"}` |
| `BOOKING_CHECK_IN_UNDONE` | `booking_check_in_undone` | undo that actually cleared | `{"previous_checked_in_at": "…Z"}` |

No migration (`action` is plain TEXT with no CHECK, `0003_auth.py:71-79`), `actor_id=staff.id`, `entity=str(booking.id)`, written in the same transaction before commit — F15's D2 shape, unchanged. **A no-op writes no audit row**, D3-step-2's rule: the second staffer's tap changed nothing, so `{from: checked_in, to: checked_in}` noise in the one trail this area has would be worse than silence.

The undo's `previous_checked_in_at` is the load-bearing one. Clearing the column destroys the only copy of the arrival time and `bookings` has no history table — the same argument D2 made for carrying `old_customer_id` on a phone correction. Nothing reads these rows in v1 (F15's Risk 7, unchanged).

### D9 — No dispatch, no on-shift staff list, no queue tickets

The E6 epic's F34 "IN" list names three things this feature does not ship, and each one has no data to stand on. This is recorded as a conflict, resolved codebase-first, and the SMC epic's phase table — user-answered, later — is the ruling that governs (`shift-manager-console.md:47`: "`checked_in_at`, check-in/undo endpoints, 5s-poll board").

- **On-shift staff with role badges.** `staff_users` is `id, tenant_id, created_at, updated_at, deleted_at, email, password_hash, display_name, role` and nothing else (`0003_auth.py:34-41`). There is no `on_shift` column: E6's F31 brief proposed manual on-shift marking, the SMC epic re-scoped F31 to roles + gating, and the shipped F31 spec's Non-goals say so. Pre-decided #33 makes F40's published roster the eventual source. A board cannot list who is on shift.
- **Dispatch (assign a ticket to a named staffer, writing the assignment record).** It needs assignees, and until **F51** ships staff CRUD the only `staff_users` rows in existence are the owners the provisioning CLI created — F51 sits *after* F34 in the queue by the user's own ordering (`LOOP-STATE.md:176-178`). It also needs somewhere to put the notification, which is F35. Pre-decided #28's "queue + dispatch" done bar is **E6's** done bar, and E6-proper is explicitly still queued (SMC ruling 2); F34 does not inherit it by being renumbered into SMC.
- **The day's queue in arrival order.** Queue tickets are F33's, which the 2026-07-30 ruling keeps but builds after F20. The board therefore renders **bookings**, and F33 will have to answer where its non-booking tickets appear — the ruling's own hedge already anticipates it ("If F34's board makes the queue-ticket model redundant in practice, say so then"). What F34 *does* ship is the arrival timestamp F33's queue-position-computed-on-read (pre-decided #30) would need anyway.

And per #28, **no wait-time analytics, no owner reporting**: `checked_in_at − starts_at` is now computable and nothing computes it.

### D10 — The board is a seventh section, and it does not become the landing page

`SectionKey` gains `"board"`; `nav` gains `{ key: "board", label: t("nav.board") }` appended after «תורים»; one render branch. F15's «תורים» section is otherwise untouched — the two coexist because they answer different questions, and merging them would put a five-second timer inside the screen that owns the reschedule dialog and three confirm Modals (a poll repainting a list behind an open `<dialog>` is a focus-management problem bought for nothing).

**The default landing section stays `"profile"`.** F52's queue note names it — "Landing section for the console" (`LOOP-STATE.md:226`) — and changing the default here would be F34 spending F52's decision.

**But the ordering runs backwards and the first draft did not notice.** This entry **parks** on the user's prototype review while F51–F53 build (`LOOP-STATE.md:194-201`); F52 is eligible now (deps `[F31]`, merged) and the loop takes the first eligible entry in file order. **F52 ships the landing section during F34's park** — so an answer collected at F34's design gate would arrive after the decision it is supposed to bind. Two things follow, and both are one line:

1. **Q-5 is lifted out of the prototype gate** and put to the user *now*, before F52 is picked (see Questions).
2. **F52 must ship the landing section as a single constant** — one `SectionKey` default in `App.tsx`, no persisted preference, no per-role table — so that if the user's answer arrives late, flipping it is a one-line F34 follow-up rather than an F52 redesign. This spec states it; F52's queue note must carry it too.

**A board row does not navigate.** One row, one action. The full record — phone, notes, terms evidence — is one section away, and the list payload deliberately carries neither (F15's D18: the list "is not a bulk PII export of the boutique's whole day"). Deep-linking a row into `BookingDetail` would mean lifting selection state into `App.tsx` and giving that screen a second entry point with a different lifecycle. Declined *provisionally* — it is the prototype's Q-2, and the user may overrule it.

### D11 — The poll must never write into an aria-live region

`role="status"` is the console's one announced region and both shipped booking screens use it (`BookingsSection.tsx:110-121`, `BookingDetail.tsx:231-239`). A five-second poll writing into it would announce the board to a screen-reader user every five seconds, forever — which fails IS 5568 / WCAG 2.0 AA in practice however green an automated check comes back, and pre-decided #38 makes that a **legal** requirement, not a preference.

So: **the announced region carries only user-initiated outcomes** — the check-in cue, the undo cue, the initial load, the session-ended alert. A poll that changes rows repaints them silently. The freshness signal is a *visible, non-announced* line (an `aria-hidden` "updated HH:MM" or equivalent) whose exact form is the prototype's. No shimmer, no pulse, no flash on refresh — the same rule serves `prefers-reduced-motion`. This is mechanical, not aesthetic, so it is pinned here and asserted by a frontend test rather than left to the deck.

### D12 — i18n, Arabic, and the formatters

New `board.*` namespace plus `nav.board` in `apps/manage/src/i18n/he.ts`, and the **same keys appended to `ar.ts`** with the approved Hebrew standing in untranslated — Interview Q3 / pre-decided #47, and the mechanics are the ones `ar.ts`'s own header already fixes (never empty strings; `lng` and `fallbackLng` stay `"he"`; no switcher). F34 does not retrofit the four hardcoded-Hebrew console sections (F15's D16) and does not invent a he/ar parity guard (F15's Risk 5, inherited unchanged).

**No new date or time formatter.** `lib/jerusalem.ts`'s `jerusalemTime` and `todayJerusalem` are exactly what the board needs, every one already passing `timeZone: JERusalem`. F34 therefore adds nothing for `scripts/qa-greps.sh`'s unzoned-formatter grep to find — the block F15 extended stays as it is.

**The Jerusalem date is recomputed on every tick, not captured at mount.** `todayJerusalem()` at mount is wrong for a device left on the counter past midnight, which is precisely pre-decided #27's reception tablet. The tick compares the current Jerusalem date to the one it is showing and, when it rolls, bumps the generation and refetches for the new day.

### D14 — The board carries a user-operable pause/resume and an idle stop, because WCAG 2.0 SC 2.2.2 is Level A and axe cannot see it

**This is a legal bar, not a preference, and the first draft failed it.** Pre-decided #38 makes IS 5568 / WCAG 2.0 AA a **legal requirement** for these staff screens (`interview-2026-07-30.md:138`), and Level A criteria are inside AA conformance. **SC 2.2.2 Pause, Stop, Hide** requires that for content that *auto-updates*, starts automatically and is presented in parallel with other content, there is **a mechanism for the user** to pause, stop, or hide it, or to control its update frequency. A board repainting every five seconds all day is squarely that, and the first draft's a11y floor listed seven items — live-region rule, 44×44, no colour-only, `bdi`, one `h1`, 720px cap, focus ring — **none of them a pause, stop, hide or frequency control**. The only pause in the spec was `document.hidden` (D4.3), which is automatic; a mechanism the user cannot operate is not "a mechanism for the user".

**And this is precisely the criterion the promised checks cannot catch.** The security checklist's entire accessibility section is four rows whose one automated item is `axe-core` (`security-checklist-v1.md:46-50`), and axe has **no 2.2.2 rule** — the criterion needs human judgement about what is auto-updating. D11 already concedes this class of failure "passes automated checks however green". So this ships green in CI and non-conformant in law. That is exactly the shape of gap that has to be closed in the spec rather than left to a reviewer.

**The mechanism, and it is one control:**

- **A visible pause / resume toggle on the board**, inside the 44×44 floor and in the tab order, next to the freshness line (which already states *when* the board last updated, so pausing has a legible consequence rather than a mystery). Pausing stops the loop; resuming fetches **immediately** and then resumes the interval, the D4.3 `visibilitychange` behaviour reused rather than reinvented. Paused state is announced once through the existing `role="status"` region — it is user-initiated, which is exactly what D11 admits there.
- **An idle stop**: after N minutes with no interaction the loop stops itself and the board says so, requiring one tap to resume. This is the same code path as the manual pause, with a timer instead of a tap.

**Three other problems fall to the same control, which is why it is one and not four:**

1. **The unattended-display exposure.** Pre-decided #27 puts a signed-in device on a reception counter, and D3/the Goal keep it repainting all day — so without an idle stop an unattended counter tablet holds a live, self-refreshing list of named brides' appointments on screen for the whole 12-hour session TTL. The idle stop ends that without a kiosk mode, a lock screen or a session change.
2. **Risk 2's sustained load**, roughly halved by every board that idles out instead of polling through a quiet hour.
3. **Q-1** ("is five seconds the beat?") is mostly answered by making the interval user-visible and user-stoppable.

Declined: a frequency picker (2.2.2 is satisfied by *any one* of pause / stop / hide / control-frequency, and a dropdown of intervals is a settings surface, a persisted preference and a second constant, for a criterion one button already discharges). Declined: relying on `document.hidden` (automatic, not user-operable — it is what makes the gap easy to miss). Declined: relying on the browser's own tab controls (2.2.2 asks for a mechanism *in the content*).

**SC 2.2.1 is a separate Level A item and it is *not* F34's to fix — but it must stop being mis-filed as an ops annoyance.** `session_ttl_seconds = 43200` is 12 hours, **under** 2.2.1's 20-hour exception, and it is unextendable and unwarned (no sliding renewal, `auth/service.py:87-95`). That is a Timing Adjustable gap, not merely a board that dies quietly. F34 cannot close it — the remedy is a warning before expiry plus a way to extend, which is a session-model change with its own security argument and belongs to F21. What F34 does is **name the criterion** so F21 inherits a legal item rather than a comfort item, and answer the arrival honestly when it happens (D4.3). Recorded in Risk 3 with the right label.

### Design gate — this one does not self-approve

Interview Q2 names the staff shift board as a genuinely novel interaction pattern, so **the design gate is the user's, not the designer's plus `design-critic`'s** (`interview-2026-07-30.md:19-20`; `e6-instore-realtime.md:4`; `LOOP-STATE.md:184-196`). The deliverables, in order, and **no `.tsx` is written before the user rules**:

1. `.planning/design/screens/shift-board/shift-board.md` — the §0–§8 deck skeleton the `owner-bookings` deck established, and `copy.md` in its three-table format with an `ar` column left untranslated.
2. `.planning/design/screens/shift-board/prototype.html` — **clickable, and it must fake the tick.** Static HTML/CSS/JS, no React, at mobile 375 first, RTL, real Hebrew from the copy deck, with a JS timer mutating a fixture so the user can *feel* whether a five-second beat reads as live and whether a one-tap check-in is right under a thumb. A still image cannot answer either question, which is the whole reason Q2 flagged this feature.
3. The queue entry **parks** on the user's review. Build resumes on the user's word; F51–F53 fill the wait.

**The three deliverables above were authored against the first draft of this spec and now need a matching revision before the gate.** `shift-board/design.md`, `copy.md` and `prototype.html` all exist. This revision changes things the deck is the single source for, so it must be updated first — the user reviews the prototype, not this document:

- **D14's pause/resume control and idle stop are new** and appear in neither the deck nor the prototype: they need a place in §1's layout beside the freshness row, a control spec in §2/§6 (44×44, tab order, focus ring), **two new states** (`B-paused`, `B-idle`), copy keys (`board.pause` / `board.resume` / `board.paused` / `board.idleStopped`, he + ar), and the prototype must let the user *operate* them — a pause the user cannot press does not demonstrate 2.2.2. §7's a11y contract gains 2.2.2 as an explicit row.
- **D4.3's terminal set widened to `{401, 403}`.** The deck's state table has `B-401` (`design.md:207`) and no 403 state. Either `B-401` generalises to a session-or-permission-ended state or a sibling `B-403` joins it; the copy at `copy.md:72` (`board.sessionEnded`) currently says only «תוקף החיבור פג» and must also cover a demotion **without naming the role** (the 403 body is generic by design).
- **D4(6)'s backoff** changes what "stale" means over time — the deck's `P-6` stale notice (a `--color-warning-text` escalation) now has to read correctly when the retry interval has stretched to a minute.
- The deck's **F-1** ruling (the freshness row is readable and not `aria-hidden`, a considered departure from D11's parenthetical) is **accepted into this spec** and is stated in the a11y floor below — D11's "or equivalent" is taken. It is no longer a deviation.

## API surface

| Method | Path | Body | Answers |
|---|---|---|---|
| `GET` | `/manage/bookings` | `?date=YYYY-MM-DD&offset=&limit=` — **unchanged, F15's** | `OwnerBookingListResponse`, rows now carrying `checked_in_at` |
| `POST` | `/manage/bookings/{booking_id}/check-in` | — | `OwnerBookingDetail` |
| `POST` | `/manage/bookings/{booking_id}/undo-check-in` | — | `OwnerBookingDetail` |

```jsonc
// OwnerBookingRow — one added key, everything else F15's
{
  "id": "…", "starts_at": "2026-08-02T07:00:00Z", "status": "confirmed",
  "attendance_confirmed_at": null,
  "checked_in_at": "2026-08-02T06:52:00Z",   // NEW — null until a staffer taps
  "customer_name": "נועה", "appointment_type_name": "מדידת שמלה", "dress_name": "Aurora"
}
```

No new request body: both mutations take the booking id in the path and nothing else, so neither needs a `ForbidExtraModel`.

## Frontend changes

| File | Change |
|---|---|
| `apps/manage/src/App.tsx` | `SectionKey` gains `"board"`; one `nav` entry; one render branch. Default section unchanged (D10) |
| `apps/manage/src/api.ts` | `checked_in_at` on the `OwnerBookingRow` interface; two `apiFetch` wrappers (`checkInBooking`, `undoBookingCheckIn`) on the exported `api` object, using the existing private `bookingPath()` |
| `…/components/BoardSection.tsx` | **new** — the poll loop (arm-on-settle incl. after a mutation, D4.4; `{401,403}` terminal, D4.3; failure backoff, D4(6)), the day's rows, the check-in / undo control, **the pause/resume control and idle stop (D14)**, the truncation line, the session-or-permission-ended alert |
| `…/components/BookingDetail.tsx` | one `<Fact>` when `checked_in_at !== null`, the `cancelled_at` treatment (D6) |
| `…/lib/booking.tsx` | **no change** — `statusBadge`, `isolateLtr` and `bookingErrorText` are imported as they are |
| `…/lib/jerusalem.ts` | **no change** (D12) |
| `…/i18n/he.ts`, `…/i18n/ar.ts` | `nav.board` + the `board.*` namespace, both files |
| `…/__tests__/BoardSection.test.tsx` | **new** |
| `…/__tests__/BookingDetail.test.tsx` | the new `Fact` row; fixtures gain `checked_in_at` |
| `…/__tests__/BookingsSection.test.tsx` | fixtures gain `checked_in_at` |
| `vite.config.ts` | **no change** — every endpoint is under `/manage`, already proxied |
| `scripts/qa-greps.sh` | **no change** (D12) |
| `test_frontend_constant_parity.py` | **no change** — `POLL_INTERVAL_MS` and the board's page limit mirror no server bound (D3) |

**States the board must design** (the deck's §4 owns the arrangement; this list is the contract it may not shrink): initial load · loaded with rows · **empty day** (an `EmptyState`, never a blank column) · load failure on the *first* fetch (the outage register, `text-ink-muted`) · **a failed poll while rows are already on screen** — which is *not* the same state: the board keeps showing the last good rows and marks itself stale rather than blanking, because stale-and-labelled beats empty, **and the stale copy must stay true as D4(6)'s backoff stretches the retry interval** · **session-or-permission ended** (401 **or 403**, loop stopped, reload affordance, and the copy must not name the role — the 403 body is generic by design) · **paused by the user** (D14) · **stopped by the idle timer** (D14) · truncated day · check-in in flight · checked-in row · a mutation failure.

**A11y floor**, non-negotiable (pre-decided #38, IS 5568 / WCAG 2.0 AA is a **legal** requirement, and Level A criteria are inside AA):

- **SC 2.2.2 Pause, Stop, Hide (Level A)** — D14's user-operable pause/resume plus the idle stop. **axe has no rule for this**, so it is asserted by a named frontend test and reviewed at the design gate, not delegated to CI.
- **SC 2.2.1 Timing Adjustable (Level A)** — the 12-hour session TTL is under the 20-hour exception and is unextendable and unwarned. **Not closed by F34**; named, labelled and handed to F21 (Risk 3). Recorded here so it is not lost as an ops annoyance.
- D11's live-region rule — and the freshness line is **readable, reachable and not in a live region** rather than `aria-hidden`. D11's parenthetical said `aria-hidden … or equivalent`; the literal reading would make the board's only honesty signal sighted-only, so a screen-reader user could never learn the board stopped updating — on a statutory-AA surface, about the one fact the feature exists to convey. The "or equivalent" is taken (the deck's F-1, accepted).
- 44×44 minimum on the check-in control **and on the pause control**, which on a phone in a boutique is the whole ergonomic argument.
- Check-in state never signalled by colour alone, and no second `Badge` competing with the status chip for meaning in one region (`lib/booking.tsx`'s stated rule). Paused state likewise carries text, not just an icon.
- `<bdi dir="ltr">` around every numeric run (times, counts) and **bare** `<bdi>` around Hebrew free text — customer name, type name, dress name — because `dir="ltr"` on Hebrew is itself a bidi defect.
- One `h1` (the shell's), the board heading `h2` · content capped at 720px · visible focus ring on every control, and focus never dropped to `<body>` when a row repaints under a tapped button.

## Testing

**Fast suite (no marker, no Docker):**

- `tests/test_booking_owner_api.py` (extended — same router, same module): two rows added to `ROUTES`, which automatically extends the 401 walk, the wiring walk and the `cache-control: no-store` parametrization; `FakeOwnerBookingService` gains `check_in` / `undo_check_in`; each route reaches its own service method with the right arguments; a service `BookingTransitionInvalidError` leaves as 409 `BOOKING_TRANSITION_INVALID` and `BookingNotFoundError` as 404 `NOT_FOUND`; `SPEC_ERROR_CODES` **unchanged** and still set-equal; the two whole-payload booking literals — **`:502` (the detail) and `:422-432` (the list row, inside `test_the_list_applies_the_documented_defaults`)** — updated for `checked_in_at`. **`:657` is the slot grid and carries no booking fields; it is not touched** (D6).
- `tests/test_booking_owner_service.py` (extended): the check-in table — `confirmed` ⇒ written + one audit row; repeat ⇒ 200, `changed=False`, **no** audit row; `cancelled` / `no_show` / `completed` ⇒ 409, nothing written; no clock bound (a booking two hours in the future checks in); undo of a checked-in row ⇒ cleared + audit row carrying `previous_checked_in_at`; undo of a never-checked-in row ⇒ 200, no audit row; undo of a **cancelled** checked-in row ⇒ succeeds (D5's no-status-guard ruling, asserted).
- `tests/test_staff_role_gating.py`: **no edit.** Its walker derives from the live route table, so the two new routes are policy-checked for free — and the test that would go red if the router-level gate were dropped is named in the plan so the reviewer can see the coverage is real rather than absent.

**db-marked (CI only — no Docker locally, per the run's standing constraint):**

- `tests/test_migrations.py`: this feature's migration up and down; `checked_in_at` is a nullable `TIMESTAMPTZ`; **and the three pinned definitions** — `pg_get_constraintdef` for the `status` CHECK, `pg_indexes.indexdef` for `idx_bookings_slot_seat_unique` and for `idx_bookings_tenant_customer_starts_unique` — asserted byte-identical **after this feature's migration** (not after any hardcoded revision id, D2). This is D1's promise made mechanical and it is the test that will still be earning its keep when E4 widens the CHECK.
- `tests/test_booking_owner_db.py` (extended). **The two headline concurrency tests must NOT use `asyncio.gather`, and an earlier draft specified exactly that.** `gather` does not order two transactions, so there is no defined "first writer" and no forced interleave — the repo's own analogue of this race (`test_booking_owner_db.py:747-804`) uses `gather` and then asserts deliberately outcome-agnostically, its comment at `:788-792` saying "The only claim that matters, and it holds whichever writer won", precisely because of this. Worse: under `gather` the loser most often loads *after* the winner commits, takes the service's Python pre-check (`checked_in_at is not None ⇒ 200 unchanged`) and **never reaches the guarded UPDATE at all** — so the zero-row branch D4(5) is entirely about would be green without ever executing. So:
  - **"the first timestamp survives"** — two **sequential** service instances with two injected clocks, the `test_booking_comms_db.py:788-811` pattern verbatim (`first_tap` at `NOW`, `later_tap` at `NOW + 2h`; assert both answer 200 and both read back `NOW`), plus exactly one `audit_log` row.
  - **"a cancel landing between the read and the write ⇒ 409"** — the interleave is **forced**, not raced: open the loser's `tenant_session` and load the booking, commit the cancel from a **second** session, then let the loser's guarded UPDATE run. That is the only way to reach the zero-row branch deterministically. Assert 409, **no** audit row, rolled back — and assert the DB row still reads `checked_in_at IS NULL`, which is the assertion that actually fails if the discrimination is read off the poisoned in-memory object (D4(5)).
  - **"a concurrent check-in landing in the gap ⇒ 200 unchanged carrying the FIRST writer's timestamp"** — same forced interleave, the other cause of zero rows. This is the pair that proves the discrimination is real; either one alone can be passed by a coin flip.
  - If a `gather` test is kept as well, its assertions must be set-shaped like `:788-801` and it must **not** claim to prove the 409.
  - Unchanged: check-in then `/complete` and check-in then `/no-show` both leave `checked_in_at` **intact** (D5's declined auto-clear, asserted as a decision); `list_day` returns `checked_in_at`; RLS isolation — tenant B's staff can neither read nor check in tenant A's booking (404, indistinguishable from missing).

**Frontend (vitest, `apps/manage/src/__tests__/BoardSection.test.tsx`)** — the `CatalogSection.test.tsx` pattern (`vi.mock("../api")` with `importActual` for `ApiError`/`errorMessage`, fixture builders, `vi.mocked`) plus `vi.useFakeTimers()`:

- exactly one request per tick, and **never two in flight**: advance timers while a fetch is unresolved and assert the call count did not grow (D4.1);
- a poll response issued before a check-in is **discarded** and the row keeps the mutation's value (D4.2/D4.4);
- `document.hidden` pauses the loop; a `visibilitychange` back to visible fetches **immediately** rather than after the interval (D4.3);
- a **401** stops the loop — advance several intervals and assert no further calls — and renders the session-ended alert (D4.3);
- a **403** stops the loop the same way and renders the same alert — advance several intervals, assert no further calls. **This is the mid-shift-demotion case and it is a separate test from the 401**, because the two arrive by different code paths (`resolve_session` returning `None` vs `RoleGate` raising) and the first draft's terminal set omitted it entirely;
- **after a successful check-in, advancing the interval issues another poll** — and **after a FAILED check-in too** (D4.4's re-arm). Without these two the board silently stops converging the first time a staffer acts, and every other test here still passes;
- **consecutive failed ticks back the interval off and a success resets it** (D4(6)): fail N ticks, assert the gap between calls grows and caps; then answer one 200 and assert the next gap is back to the base interval;
- **the pause control stops the loop and resume fetches immediately** (D14): tap pause, advance several intervals, assert no calls; tap resume, assert a call **before** the interval elapses;
- **the idle stop fires** after the idle window with no interaction, and one tap resumes (D14);
- a Jerusalem date roll refetches for the new day (D12);
- a failed poll with rows on screen keeps the rows and marks stale; a failed *first* fetch shows the outage register;
- check-in patches the row from the response, the control is disabled while in flight, and a double-tap fires one request;
- **the announced region does not change on a poll tick** and does change on a check-in and on a pause (D11, D14);
- truncation line appears only when `total > items.length`;
- an axe pass — **explicitly not sufficient**: axe has no SC 2.2.2 rule, so the pause/idle assertions above are the only automated coverage of that criterion and must not be dropped as redundant with the axe row (D14).

**No E2E is promised**, and the reason is F15's verbatim: the console's entire e2e surface is two login-screen tests because `vite preview` runs with no backend and nothing can log in (`e2e/a11y.spec.ts:10-13`). A board e2e needs `/manage/**` route interception that no spec has built. Recorded rather than silently skipped.

## Out of scope

- **Dispatch and the staff↔client assignment record** (D9) — needs F51's staff rows and F35's bell; stays E6-proper's.
- **On-shift staff with role badges** (D9) — no `on_shift` column exists; F40's published roster is the eventual source (pre-decided #33).
- **Queue tickets** (D9) — F33's, after F20; the board renders bookings.
- **Wait-time analytics and any owner reporting** — pre-decided #28. `checked_in_at − starts_at` becomes computable here and nothing computes it.
- **A realtime vendor, a version field, an event table, sockets** — SMC ruling 3; pre-decided #23 permits Pusher only if the pilot proves the poll too slow, and E9's F44 is the one place authorised to assume it exists.
- **A read-only kiosk / display mode** — pre-decided #27 calls it a small follow-up if the pilot asks.
- **Walk-in creation from the board** — F50/SMC-6, which depends on this feature. When it lands, its rows arrive through this same list API with `checked_in_at` already set and no `manage_token`; the board needs no change to render them, because the list row carries neither terms nor `manage_link_issued`.
- **A board detail view, drag-to-reorder the queue, notifications, SOS, fitting rooms** — F35 / F37 / F36.
- **Any change to the check-in control's placement in F15's detail screen** — the detail states the fact, the board owns the action (D6).
- **A polling abstraction for F35/F37/F44 to inherit.** The loop lives in `BoardSection.tsx`. A hook with one caller, no second consumer and no test of its own is an abstraction bought on speculation; the extraction is mechanical the day F35 has a second caller, and F35's dep list already names this feature so it will be looking. **What those three inherit is D4's six mechanisms as a documented pattern and one interval constant — nothing executable** (header note). Each ships its own endpoint and its own loop; `GET /manage/bookings?date=` cannot carry a bell item or an SOS page.
- **The privacy notice and the processing-activities entry for the arrival record.** F20's, `spec_gate: user`, and the hand-off is stated in Risk 9 rather than assumed.

## Codebase conflicts recorded

1. **E6's F34 brief names dispatch, on-shift staff and a queue; none has data.** `e6-instore-realtime.md:77` lists all three as IN. Verified against code: `staff_users` has no `on_shift` column (`0003_auth.py:34-41`), no queue-ticket table exists, and the only `staff_users` rows before F51 are provisioned owners. The SMC epic's phase table (user-answered, 2026-07-30) scopes SMC-5 to `checked_in_at` + endpoints + the poll. **Codebase-consistent reading taken:** the board is the day's bookings; D9 records the rest as E6-proper's.
2. **Pre-decided #25 and `architecture.md:12` describe versioned event hints with full refetch on version gap.** SMC ruling 3 drops the version. There is no event substrate to version, so the mechanism has no subject; the principle it protects — server is truth, client holds no derived state — is satisfied more completely by a permanent full refetch. E6's DoD line "full refetch on version gap or reconnect" (`e6-instore-realtime.md:29`) survives as D4.3's visibility-resume fetch, which is the only reconnect a poll has.
3. **`LOOP-STATE.md:190` drops F33 as a dependency; `e6-instore-realtime.md:45` says F33's "only consumer is F34's board".** The 2026-07-30 ruling keeps F33 but sequences it after F20 — i.e. after this feature. So F34 ships with no queue tickets to render and F33 will have to answer where its non-booking tickets appear. Named, not resolved here.
4. **The SMC epic says the bookings section is "F15's, untouched"; D6 adds a field to its wire shape and a `Fact` row to its detail.** Read narrowly (re-scoping, not byte-immutability) with the reasoning in D6. Flagged so a reviewer finds a ruling.
5. **F15's D6 declined a throttle on this router because there was "no attacker on the other side of it".** A five-second poll makes the traffic real without making an attacker; the conclusion holds and the reasoning is restated rather than inherited (D3, Risk 4). **What does not survive unchanged is the silence on the client side**: with no server ceiling, the only throttle on an outage is the board's own, so D4(6) adds failure backoff. Declining the limiter and adding no backoff was the gap.
6. **`LOOP-STATE.md` still records F35/F37/F44 as riding F34's poll** (`:411` "Rides F34's 5s poll (F32 subsumed)"), inherited when F32 was subsumed and every dep list naming it was rewritten to name F34. **D13 ships nothing for them to ride, and `GET /manage/bookings?date=` structurally cannot carry a bell item or an SOS page.** Read as a *pattern* inheritance, stated in the header and D13. Flagged so those three features spec their own endpoint and loop rather than discovering the substrate is absent.

## Review findings raised and REJECTED

Everything else from the 2026-07-30 adversarial pass was verified against the code and applied above. This one was not, and it is recorded rather than silently dropped.

**REJECTED — "escalate Gate 1 to the user instead of self-approving it."** Raised as the second half of the privacy finding: since the feature starts recording a named person's physical presence before any privacy notice exists, the argument ran, the Gate-1 classification is the user's pilot call, "the same class of decision as the F15 phone-correction acknowledgement, which did go to the user."

**Why it does not hold.** Interview Q1 is not a judgement call this spec gets to re-make — it is a standing approval with an **explicitly enumerated** exception list: *"anything touching payments, refunds, privacy-law text, or tenant billing. Concretely that means **F17, F18, F19, F20, F29 and F48** present their spec and wait; every other feature self-approves"* (`interview-2026-07-30.md:14`). F34 is not on that list, and the enumeration is what makes the rule operable — a spec that promotes itself onto it on its own reading of "privacy-law" turns a closed list into a per-feature argument and spends a user turn the user already declined to spend. The finding's own premise also points the other way: **the privacy-law text is F20's**, F20 *is* on the list and is `spec_gate: user`, so the decision the finding wants made reaches the user through the feature that owns it. The F15 comparison does not transfer either — that acknowledgement was a **question inside an already-approved spec**, not a re-classification of the gate.

The substantive half of the same finding — that the arrival record is a new processing purpose needing a notice and a processing-activities entry — **was accepted** and is discharged as an explicit F20 hand-off (Risk 9, Out of scope). What was rejected is only the gate change. **Gate 1 stands self-approved under Q1.**

## Risks & open items

1. **The prototype gate is the schedule.** The build cannot start until the user reviews a clickable prototype (Interview Q2), and the queue entry parks there. If the review stalls, F50/SMC-6 stalls behind it — F50's walk-in half ships *from this board* — and so do F35 and F37, whose dep lists name this feature (for the **pattern**, not a substrate — header note and conflict 6). F51–F53 are the designed absorber. **The review now depends on a deck revision first**: D14's pause/idle control and D4.3's `{401,403}` terminal set post-date the authored `shift-board/` deck, copy and prototype, so those three artifacts must be brought to this document before they go to the user — otherwise the user reviews and approves a board without the control that makes it lawful. *Owner: **user**, unblocked by a designer pass. Trigger: the prototype review itself; the loop re-nags in every run report until it clears.*
2. **A five-second poll per phone is the first sustained load this product has ever taken, and it costs ~3× what a handler-level count suggests.** Per tick, per device: **4 sessions, ~9 SQL statements, ~17 round trips, 4 pool checkouts** — the handler's 5 business queries plus one uncached `tenants.by_slug` in its own session, three `set_config` + BEGIN/COMMIT pairs, and four `pool_pre_ping` `SELECT 1`s (D3's table has the citations). Ten devices on one tenant is **~90 statements/s** for a whole shift; 50 tenants × 3 devices is **~270 statements/s** of polling alone. Nothing throttles it server-side (D3), no connection-pool ceiling has been sized against 4 checkouts per request, and the pilot is the first measurement. Two cheap levers: the interval (one client constant, and D14's idle stop already removes the quiet hours), and **caching `tenants.by_slug`, which is one uncached indexed read per tick per device and is already assigned to F29 by pre-decided #21** (`tenancy/resolver.py:8-9` says so in its own docstring). *Owner: team. Trigger: F29's k6 pass, whose targets pre-decided #22 derives from staging metrics — **this** number must be handed to it, not discovered by it.*
3. **A board open past twelve hours dies quietly — and that is a WCAG 2.0 SC 2.2.1 (Level A) gap, not an ops annoyance.** `session_ttl_seconds = 43200` with no sliding renewal (`config.py:24`, `auth/service.py:87-95`), so an overnight tablet — pre-decided #27's explicit case — wakes to a 401. **12 hours is under 2.2.1's 20-hour exception**, and the limit is both unextendable and unwarned, which is precisely what Timing Adjustable is about; pre-decided #38 makes that a legal bar, so mis-filing it as an annoyance is how it stays open forever. F34 cannot close it: the remedy is a warning before expiry plus a way to extend, i.e. a session-model change with its own security argument. What F34 does is stop the loop and say so honestly (D4.3) and **hand F21 a labelled Level A item** (D14). *Owner: team. Trigger: F21's hardening pass, or the first pilot morning that starts with a dead board.*
4. **The board's freshness claim can be wrong for up to five seconds, and a stale-but-labelled board is a judgement call.** When a poll fails with rows on screen the board keeps them and marks itself stale rather than blanking. That is right for a floor tool and it means a staffer can act on a row the server has already moved — she gets a clean 409 or an idempotent 200, never a corrupt write, but she can be surprised. *Owner: user, at the prototype gate (how loud "stale" must be). Trigger: design gate.*
5. **`checked_in_at` makes wait-time measurable and pre-decided #28 forbids measuring it.** The column is exactly the input an analytics feature would want, and the first person to notice will propose a chart. The ruling stands until an epic reopens it. *Owner: team. Trigger: E6-proper's or E9's analytics scope.*
6. **Nothing keeps `ar.ts` in sync with `he.ts`.** Inherited unchanged from F15's Risk 5; F34 adds keys to both by hand and invents no parity guard. *Owner: team. Trigger: the feature that makes Arabic selectable (F45).*
7. **The audit rows are still write-only.** F34 adds two more actions nothing renders (F15's Risk 7). The undo's `previous_checked_in_at` is the only surviving copy of a destroyed arrival time and there is no way to read it without `psql`. *Owner: user. Trigger: pilot feedback, or F53's SMS/activity log, which is the first read surface over per-customer history.*
8. **No E2E covers the poll.** The loop's six failure modes are unit-tested with fake timers against a mocked `api`; none is exercised against a real backend, and the mode most likely to differ in reality — a genuinely slow response on boutique wifi — is the one fake timers model least faithfully. *Owner: team. Trigger: the feature that builds `/manage/**` interception for the console's e2e suite.*
9. **`checked_in_at` starts collecting a new class of personal data — a named person's physical presence at a place and time — and no privacy notice exists in the product to cover it.** D1 argues at length that this is emphatically *not* `attendance_confirmed_at`, i.e. not the fact the bride already consented to reporting through her own link — which is the same argument that it is a **new processing purpose**. The only consent artifact shipped today is a cancellation policy (`storefront/src/i18n/he.ts:200,210`; `bookings.terms_version_accepted` → `terms_versions`, `models/booking.py:36-38`). Pre-decided #10 puts bookings at 7 years, so the arrival record inherits a 7-year retention — mechanically fine, and exactly the minimisation/purpose question Amendment 13 asks. **Hand-off, and it is the whole remedy: F20 (`spec_gate: user`, owns the platform-written collection notice) must carry an arrival/check-in entry in both the notice and the processing-activities record — purpose = floor operations, retention = with the booking.** No build work here and no change to F34's scope. *Owner: team, discharged by F20. Trigger: F20's spec, which stops for the user anyway.*

## Questions the prototype must put to the user

- **Q-1 Is five seconds the beat?** A visible "updated HH:MM" line may make ten seconds feel just as live and halve every number in Risk 2.
- **Q-2 Does a board row need to reach the full booking** (phone, notes), or is one tap = check in, with «תורים» for the rest? D10 declines it provisionally; the list payload carries no phone by F15's D18, so saying yes here means either a second fetch on tap or a change to that ruling.
- **Q-3 Is undo always visible, or only for a few minutes after check-in?** Always-visible is one less rule; time-boxed is one less mis-tap.
- **Q-4 One chronological list, or expected / here / done bands?** Bands make "who is waiting" instant and make the ordering non-obvious when someone arrives early.
**Q-5 has been LIFTED OUT of this list** — see below. Q-1 through Q-4 stay at the prototype gate.

### Q-5 goes to the user NOW, not at the design gate

**Does the board become the console's landing section?** Asking it at the prototype gate would ask a question whose stated binding target has already shipped: F52 owns the landing decision (`LOOP-STATE.md:226`) and **F52 builds during this entry's park** (D10). So Q-5 is put to the user with the parked prototype rather than inside it, before F52 is picked. If the answer does not arrive in time, the fallback is already specified and costs nothing: **F52 ships the landing section as a single `SectionKey` constant** — no persisted preference, no per-role table — so flipping it later is a one-line F34 follow-up. F52's queue note must carry that sentence.

## Decisions Log

- **D1 — Check-in is `bookings.checked_in_at TIMESTAMPTZ`, not a fifth `BookingStatus`.** Eight shipped guards read `status = 'confirmed'` or enumerate the four (`bookings.py:302-307, 343-354, 211-222, 403-414`; `owner.py:250-293`; `manage.py`), so a fifth value would make a checked-in bride uncancellable, unreschedulable and unrenderable on her own SMS page — while both partial unique indexes would stay *correct*, which is what makes the trap quiet. Status says what became of the appointment; check-in says whether a person is in the building; they are true at once. Declined: reusing `attendance_confirmed_at` (the bride's column, written through her token link, already rendered as its own cue, and `/confirm` refuses to touch it in writing — `owner.py:250-259`), a `check_ins` table, and an index on the new column.
- **D2 — One `ALTER TABLE … ADD COLUMN` plus the matching `mapped_column` on `models/booking.py`, and the revision id is resolved at build time.** No grant (0008's table-level grant is column-agnostic), no `enable_tenant_rls` (a table property, already forced), no trigger (`trg_bookings_updated_at` exists), no index, no default. **The revision id is NOT pinned to 0012/0011**: this entry parks on the prototype gate and F53 carries a migration of its own during the wait (`LOOP-STATE.md:234`), so the build reads `alembic heads` and revises whatever HEAD then is; the pinned assertions key to "after this feature's migration". **The ORM column is not optional** — `models/booking.py` declares every column explicitly and no parity test exists, so without it every backend line D5/D6 specify is an `AttributeError`. What the migration must prove it did *not* do is pinned by a db-marked test asserting the status CHECK and both partial unique index definitions byte-identical after it — so E4's `pending_payment` widening collides with a literal rather than with nothing.
- **D3 — The board is a client 5s poll of the shipped `GET /manage/bookings?date=`, with no version, no delta and no new endpoint.** Answering "has anything changed" costs the same query as answering the day, which is SMC ruling 3's arithmetic. Declined: ETag/304 (halves bytes, changes nothing that costs, fights the router's `no-store`), a realtime vendor (pre-decided #23 permits one only if the pilot proves the poll too slow), a throttle on the read (F15's D6 reasoning restated: the only reachable victim is the board), and hardcoding `BOOKING_LIST_MAX_LIMIT` client-side (the router's `Query(le=…)` would 422 a client pinned to a ceiling that later drops — ask for 50 and state the truncation instead).
- **D4 — The six failure modes, each with one mechanism.** Schedule-after-settle ⇒ no overlap by construction (declined `setInterval` + `AbortController`, and any data-fetching dependency); **the mutation's `.finally()` is the same single arming site, so a suppressed tick is re-armed and the board does not stop converging the first time a staffer acts** — on a failed mutation too. One monotonic generation ⇒ no stale apply, covering poll-vs-mutation and the date roll (declined per-row timestamps). `document.hidden` pauses and `visibilitychange` fetches immediately. **The terminal set is `{401, 403}`, not `{401}`** — deactivation ends in 401 (`staff_users.by_id` filters `deleted_at` → `resolve_session` returns `None`) but **demotion ends in 403** (`RoleGate` raises `NotAuthorizedError`, `auth/dependencies.py:57-62`), and a 401-only rule leaves the board polling a revoked role forever, silently defeating F31's "demotion bites on the next request" on the one screen that keeps requesting after a revocation — with F51, which makes demotion possible, merging during this entry's park (declined threading it into `App.tsx`'s staff state). **A transient failure backs the interval off 5s → ~60s cap and a success resets it** — there is no server-side ceiling on this path (every `FixedWindowRateLimiter` in `main.py` is login/terms/presign/storefront/phone/tenant/verify/create/lookup/sms) and D3 declines one, so the throttle is the client's; three lines in the `.finally()` that already arms the tick. **Not optimistic** ⇒ rows patch from the server's own `OwnerBookingDetail`, the shipped `BookingsSection.tsx:74-78` shape (declined optimism: one round-trip of speed paid for with a check-mark that un-ticks). Idempotent by predicate on `checked_in_at IS NULL` ⇒ two staffers both succeed and the first timestamp survives (declined an advisory lock: one column on one row has no cross-row invariant to serialise).
- **D5 — Two endpoints on F15's router, `/check-in` and `/undo-check-in`, both answering `OwnerBookingDetail`, both admitting owner and shift_manager.** Zero rows is discriminated **in the repository, off a re-read that defeats the identity map** — never off the loaded object. ORM-enabled DML's `evaluate` synchronization stamps the SET value onto the in-memory instance whatever the DB matched and `by_id` hands that same object back (`bookings.py:287-295`; `owner.py:325-333`; pinned by `test_booking_owner_db.py:747-760`), so `if booking.checked_in_at is not None` fires for **both** zero-row causes: the 409 branch is unreachable and a check-in that lost to a concurrent cancel answers a false 200 on a cancelled row — and the render carries the wrong staffer's timestamp besides. So the writers return `(CheckInOutcome, Booking | None)` from the `.returning()` scalar plus a `populate_existing=True` re-read: `WROTE` ⇒ write the audit row; `ALREADY_CHECKED_IN` ⇒ 200 unchanged, no audit row (a 409 would lie to the person who was right), rendering the **first** writer's timestamp; `NOT_CONFIRMED` ⇒ 409; `MISSING` ⇒ 404. **The `confirm_attendance` precedent is cited only for the predicate shape** — it never returns `None` for zero rows and deliberately declines this discrimination; `cancel`'s `.returning()`-scalar rule is the governing one. **No clock bound on check-in** (early arrival is the ordinary case) and **no status guard on the undo** (the `/confirm` precedent — a mis-tap is correctable whenever noticed), so the undo's only failure is 404. Declined: one endpoint with a boolean body (two guards, two audit actions, two `details` shapes collapsed into one body of `if`s — D7's argument against a single `PATCH`); clearing `checked_in_at` inside a status transition (it would make F15's one status writer do two things and destroy an arrival record as a side effect of an unrelated verb); and a column-only Core `select` for the discrimination (equally correct for the branch, but it leaves the entity poisoned for rendering and needs a second re-read anyway).
- **D6 — `checked_in_at` joins `OwnerBookingRow` (inherited by the detail), and F15's `BookingDetail` renders one `Fact`; the control stays on the board.** The board only reads the list, so the field must be on the row. The SMC epic's "F15's, untouched" is read as re-scoping rather than byte-immutability — a column the console cannot see anywhere would be stranger. Two shipped whole-payload **booking** assertions red-fail and are updated as a visible edit, which is what a pinned literal is for: **`test_booking_owner_api.py:502` (detail) and `:422-432` (list row)**. Corrected from an earlier draft that named `:657` — that is the slot-grid literal (`{"slots": [...capacity, remaining]}`), carries no booking fields, and is untouched.
- **D7 — Zero new error codes and zero new handlers.** 404 rides `DomainNotFoundError`; the 409 rides F15's `BOOKING_TRANSITION_INVALID`, whose docstring already scopes itself to this class of refusal (`owner.py:61-69`); repeats are 200s. `SPEC_ERROR_CODES` stays set-equal unchanged. Declined `BOOKING_ALREADY_CHECKED_IN`: it would name a condition that never answers an error, and with no error registry every invented code is a handler somebody must remember or ship a 500.
- **D8 — Two `AuditAction` members, no migration, and the undo carries the value it destroys.** `action` is plain TEXT with no CHECK (`0003_auth.py:71-79`). No-ops write no row (D3-step-2's rule). `previous_checked_in_at` is load-bearing because clearing the column destroys the only copy and `bookings` has no history table — D2's `old_customer_id` argument, same shape.
- **D9 — No dispatch, no on-shift staff list, no queue tickets, no wait-time analytics.** Each has no data: `staff_users` has no `on_shift` column (`0003_auth.py:34-41`), the only staff rows before F51 are provisioned owners, and queue tickets are F33's (after F20). Pre-decided #28's "queue + dispatch" done bar belongs to E6-proper, which SMC ruling 2 leaves queued — F34 does not inherit it by being renumbered into SMC. Recorded as conflict 1.
- **D10 — The board is a seventh section; F15's «תורים» keeps its own screen; the default landing section is untouched.** Merging them would put a five-second timer inside the screen that owns three Modals and the reschedule dialog. A board row does not navigate — the list payload carries no phone by F15's D18, and deep-linking would give `BookingDetail` a second entry point with a different lifecycle. Both the row-navigation and landing-section questions go to the prototype (Q-2, Q-5); F52 owns landing.
- **D11 — The poll never writes into an aria-live region.** A `role="status"` update every five seconds is an AA failure in practice however green the automated check is, and pre-decided #38 makes AA a legal requirement. Announced output is user-initiated only; freshness is a visible non-announced line; no shimmer or pulse, which serves `prefers-reduced-motion` from the same rule. Mechanical, so it is asserted by a test rather than left to the deck.
- **D12 — New `board.*` keys in both `he.ts` and `ar.ts` (Hebrew standing in untranslated), and no new formatter.** Q3 / pre-decided #47 and `ar.ts`'s own header mechanics (never empty strings — i18next's `returnEmptyString` would blank the page). `lib/jerusalem.ts` already answers everything the board needs with `timeZone: JERusalem`, so `qa-greps.sh` gains nothing. The Jerusalem date is recomputed **every tick**, not captured at mount, because a counter tablet crosses midnight — pre-decided #27's own device. Declined: retrofitting the four hardcoded-Hebrew sections and inventing a he/ar parity guard (F15's D16, unchanged).
- **D13 — The poll loop lives in `BoardSection.tsx` and is not extracted for F35/F37/F44.** A hook with one caller, no second consumer and no test of its own is an abstraction bought on speculation. F35's dep list already names this feature, so the day there is a second caller the extraction is mechanical and reviewed. **Consequence, stated rather than left implied:** F34 is *not* the live-update substrate F32 was, and the header's "feeds" claim is corrected — `GET /manage/bookings?date=` cannot carry a bell item or an SOS page, so F35/F37/F44 each ship their own endpoint and their own loop, inheriting D4's six mechanisms as a **documented pattern plus one interval constant, nothing executable**. Recorded so three later features are not scheduled against a substrate that does not exist.
- **D14 — The board carries a user-operable pause/resume and an idle stop, because SC 2.2.2 is Level A and axe cannot test it.** Pre-decided #38 makes IS 5568 / WCAG 2.0 AA a **legal** bar and Level A sits inside AA; a five-second auto-updating board with no pause/stop/hide/frequency mechanism fails 2.2.2, and the only automated a11y check the checklist promises is axe (`security-checklist-v1.md:46-50`), which has no rule for it — so this ships green in CI and non-conformant in law. `document.hidden` is automatic and is not "a mechanism for the user". One control discharges it and also ends the unattended-counter-tablet exposure that pre-decided #27 creates (an idle stop, not a kiosk mode), roughly halves Risk 2's quiet hours, and answers most of Q-1 by making the interval visible and stoppable. Declined: a frequency picker (2.2.2 needs any *one* of pause/stop/hide/frequency; a dropdown buys a settings surface and a persisted preference for a criterion one button closes) and relying on the browser's own tab controls (2.2.2 asks for a mechanism in the content). **SC 2.2.1 is named but not closed here**: the 12h TTL is under the 20-hour exception and is unwarned and unextendable, which is a Level A item owned by F21, not the ops annoyance Risk 3 first called it.
