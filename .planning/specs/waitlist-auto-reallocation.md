# Spec: F23 — Auto-reallocation loop (Epic E5)

**Created**: 2026-08-06 · **Status**: **Gate 1: standing approval — interview-2026-07-30.md §Standing approvals.** Q1's stop-list is enumerated (F17, F18, F19, F20, F29, F48) and F23 is not on it. It touches the deposit flow but **writes no payment code**: the claim calls F19's shipped `open_deposit` on the shipped path, so no money surface is authored here (D5). No new privacy Hebrew — the offer page reuses F20's shipped notice, and the entry's phone is already F22's declared collection point. · **Epic**: `.planning/epics/e5-growth.md` Feature 23 · **Effort**: **L** — one additive migration on two tables, one new worker job, one new claim path through the shipped booking core, one storefront route, three manage fields, and six concurrency tests that are the feature.
**Depends on**: **F22** (`waitlist_entries`, the five-state lifecycle, 0026 — merged), **F16** (`scheduled_messages` + `drain_due` poller + `worker.poll_once`), **F19** (`DepositSweeper`, `open_deposit`, `honour_late_settlement`), **F13** (`create_booking`'s advisory lock + `idx_bookings_slot_seat_unique`).
**Interview**: pre-decided **#12** (2h window, quiet hours 21:00–08:00, both per-boutique settings), **#13** (sequential offers + expiry cascade, atomic conditional claim on the existing partial unique index, no broadcast), **#14** (FIFO by join time), **#15** (stop offering under ~2h lead; truncate the final window), **#16** (offers ride `scheduled_messages`, widened `kind` CHECK, no new scheduler).

---

## Problem

F22 collects `waiting` entries and offers them nothing. Every freed slot — a customer cancel, an owner cancel, an owner reschedule's source slot, an expired deposit hold, a widened availability rule — still evaporates. F23 is the loop that puts the slot back to work, and it is the epic's hardest race problem: the claim must be exactly as double-book-proof as a direct booking, and a claim on a deposit-on type must neither hold the slot forever nor lose it unfairly.

## What already exists to build on (verified against code)

- **`BookingsRepository.cancel`** (`db/repositories/bookings.py:553`) is a guarded UPDATE whose seat release is *structural* — `idx_bookings_slot_seat_unique` (0008) is `ON (tenant_id, starts_at, seat_index) WHERE deleted_at IS NULL AND status <> 'cancelled'`. Three callers: `ManageBookingService.cancel` (customer, tokenized page), `OwnerBookingService.cancel` (`owner.py:701`), `DepositSweeper.sweep` (`sweeper.py:108`, `allowed_from=('pending_payment',)`).
- **Two writers free a slot WITHOUT calling it**: `DepositSweeper._cancel_orphans` (`sweeper.py:250`) is a bounded bulk `update(Booking)`, and `BookingsRepository.reschedule` (`:684`) moves a row in place, freeing the source instant with no cancel at all. A sixth path frees capacity with no booking write whatsoever: an owner widening an availability rule or deleting an exception.
- **`create_booking`** (`booking/service.py:287-539`) is the claim's engine: `pg_advisory_xact_lock(hashtext(tenant_id))` → `offered_slot` → `customers.upsert` → lowest-free-seat off `active_seats_at` → INSERT (`pending_payment` if `deposit_due`, else `confirmed`) → reminder row. `IntegrityError` → `SlotUnavailableError` (409). `materialize_slots` is **type-agnostic** — `offered_slot` takes no appointment type — so an entry's type never filters the grid.
- **`scheduled_messages` (0010)**: `booking_id UUID NOT NULL`, `kind TEXT CHECK (kind IN ('reminder'))`, `manage_token TEXT` cleared on every terminal transition, `idx_scheduled_messages_pending_unique ON (tenant_id, booking_id, kind) WHERE status='pending'`. `drain_due` (`comms.py:400`) claims `FOR UPDATE SKIP LOCKED`, **re-reads the booking** and cancels the row if it is not `confirmed`, leaves rows pending when no provider is configured, marks `failed` on `SmsSendError`.
- **`worker.poll_once`** (`worker.py:68`) enumerates active tenants and runs drain + sweep, each in its **own try block** so one tenant's failure never silences another's. `architecture.md` already reserves "offer cascade" as a worker job.
- **`DepositSweeper`** is the pattern for a guarded bulk expiry: id-subquery bound, `synchronize_session=False`, answer read off `RETURNING`, both claims in one transaction.
- **F19's late-webhook answer already exists**: `honour_late_settlement` + `_free_seat` + `rebind(allowed_from=('cancelled','pending_payment'), not_before=now)`; no free seat → `None` → `notify_payment_received_no_slot` (owner alert, manual refund). Race-tested in `test_deposit_races_db.py` (`test_a_late_delivery_racing_a_new_bride_has_exactly_two_outcomes`, `test_the_sweeper_racing_a_late_webhook_never_alerts_on_a_free_seat`).
- **Token primitives**: `mint_manage_token()` / `manage_token_hash()` / `manage_token_matches()` (`booking/tokens.py`) — 32 random bytes, sha256 stored, `compare_digest` re-check. The link shape is `https://{slug}.{domain}/b/{token}` (`comms_templates.py:75`) and the token travels in a **POST body**, never a URL the access log sees (`manage.py` D7).
- **Jerusalem is `BOUTIQUE_TIMEZONE = ZoneInfo("Asia/Jerusalem")`** (`storefront/validation.py:40`) with `today_jerusalem(clock)`. **No quiet-hours concept exists anywhere in the codebase** — F23 introduces it.
- Settings already carry `deposit_hold_seconds=900`, `worker_poll_interval_seconds=60`, `waitlist_join_*` limiters, `waitlist_retention_days=30`. `AuditAction.WAITLIST_ENTRY_CANCELLED` exists; `action` is CHECK-less TEXT, so new members need no migration.

## Where the brief and the code disagree

| # | The brief / interview says | The code says | Taken as |
|---|---|---|---|
| 1 | "When a slot frees … offer it" — implying a trigger at the freeing transition | There is no single freeing seam. `BookingsRepository.cancel` covers 3 of 6 paths; `_cancel_orphans` is a bulk UPDATE, `reschedule` frees the source instant without cancelling, and an availability widening frees capacity with no booking write at all. | **The cascade is a poller keyed off `waiting` entries, not a hook keyed off cancellations** (D2). Same outcome, one call site instead of six, and it is the only shape that catches the availability case. |
| 2 | Pre-decided #16: offers ride `scheduled_messages`, "widening its `kind` CHECK by migration. No new scheduler." | `booking_id` is `NOT NULL` and `drain_due` re-reads a **booking** per row to decide whether to send. An offer has no booking. | Ride it, and pay for it honestly: `booking_id` becomes nullable, a `waitlist_entry_id` column joins it under an XOR CHECK, and `drain_due` gains a kind branch (D3). #16's intent — no second poller, no second process — is fully honoured. |
| 3 | Epic brief: "an expired claim-hold **re-fires** the cascade" | Nothing re-fires anything; `DepositSweeper` knows nothing about waitlists. | No re-fire is written. The sweeper frees the seat, and the cascade's next tick finds free capacity and a `waiting` entry (D5). The coupling the brief implies is exactly what D2 removes. |
| 4 | F22 Risk 5 left the door open for a sixth lifecycle state | Five states suffice: `waiting → offered → claimed \| expired \| cancelled`, with decline reusing `cancelled` and an unsent offer returning to `waiting` (D8). | No CHECK widening on `waitlist_entries.status`. |

---

## Design

### D1 — The additive migration (`waitlist_entries` + `scheduled_messages`)

**Revision id and `down_revision` resolve from `alembic heads` at build time.** Observed head is `0026` today, so this is *head+1* — but **F24 is building `0027` in a live worktree and F25/F28 are queued, so this number WILL shift**: build at head+1, renumber at rebase, keep the migration the last commit on the branch (0018's recorded hazard, `.memory/parallel-alembic-numbering`).

```sql
ALTER TABLE waitlist_entries
  ADD COLUMN offered_at        TIMESTAMPTZ,
  ADD COLUMN offer_expires_at  TIMESTAMPTZ,
  ADD COLUMN offer_starts_at   TIMESTAMPTZ,   -- THE slot instant this offer is for
  ADD COLUMN offer_token_hash  TEXT;          -- sha256 only, never the raw token

-- The claim's lookup, and collision-impossible by construction.
CREATE UNIQUE INDEX idx_waitlist_entries_offer_token
  ON waitlist_entries (offer_token_hash)
  WHERE offer_token_hash IS NOT NULL AND deleted_at IS NULL;

-- The expiry claim's range scan, per tenant, per tick.
CREATE INDEX idx_waitlist_entries_offer_expiry
  ON waitlist_entries (tenant_id, offer_expires_at)
  WHERE status = 'offered' AND deleted_at IS NULL;

ALTER TABLE scheduled_messages
  ALTER COLUMN booking_id DROP NOT NULL,
  ADD COLUMN waitlist_entry_id UUID,
  ADD CONSTRAINT ck_scheduled_messages_subject
    CHECK ((booking_id IS NULL) <> (waitlist_entry_id IS NULL)),
  DROP CONSTRAINT scheduled_messages_kind_check,
  ADD CONSTRAINT scheduled_messages_kind_check
    CHECK (kind IN ('reminder','waitlist_offer'));

-- The offer half of the idempotency key. The existing pending-unique index on
-- (tenant_id, booking_id, kind) never refuses an offer row: NULLs are distinct
-- in a unique index, so the two halves cannot interfere.
CREATE UNIQUE INDEX idx_scheduled_messages_offer_pending_unique
  ON scheduled_messages (tenant_id, waitlist_entry_id, kind)
  WHERE deleted_at IS NULL AND status = 'pending' AND waitlist_entry_id IS NOT NULL;
```

No new `waitlist_entries.status` value (conflict 4). No RLS re-run — `ALTER TABLE … ADD COLUMN` preserves policies; `test_every_tenant_id_table_has_forced_rls` must stay green unedited. Downgrade drops the columns, indexes and CHECKs and restores `booking_id NOT NULL` (safe: every legacy row has one). ORM: four fields on `WaitlistEntry`, one nullable `booking_id` + one `waitlist_entry_id` on `ScheduledMessage`. **`manage_token` carries the raw offer token** for a pending offer row — that is its existing semantics verbatim (kept only while pending, cleared on every terminal transition), so no fifth column.

New settings, all per-boutique-tunable defaults per #12: `waitlist_offer_window_seconds=7200`, `waitlist_quiet_start_hour=21`, `waitlist_quiet_end_hour=8`, `waitlist_offer_min_lead_seconds=7200` (#15).

### D2 — The trigger is a poller, not a transition hook

`WaitlistCascade`, a fourth job in `worker.poll_once`, **its own try block**, on the existing 60-second tick. No new process, no beat, no daemon (#16's spirit). Per tenant, in one `tenant_session`:

1. **Expire first** (runs regardless of quiet hours — an offer must be able to die at night so the slot is directly bookable again). Guarded bulk UPDATE, `DepositSweeper._expire_holds`'s shape: `status='offered' AND offer_expires_at <= now` → `expired`, clearing `offer_token_hash` and `offer_expires_at`; answer read off `RETURNING`. Then cancel each entry's pending `waitlist_offer` message. **Exception, D8**: an entry whose offer message never reached `sent` returns to `waiting` instead.
2. **Quiet-hours gate**: if `now` in Jerusalem is inside `[21:00, 08:00)`, issue no new offers for this tenant this tick. Return.
3. Read the distinct `(day, appointment_type_id)` pairs of `waiting` entries with `day >= today_jerusalem`, **skipping any pair that already has an `offered` entry** — that single predicate *is* "sequential, one at a time, no broadcast blast" (#13).
4. Per pair: materialize the day grid (`materialize_slots` fed real `count_by_start` counts, the call `offered_slot` makes) and take the earliest slot with `starts_at > now + waitlist_offer_min_lead_seconds` (#15). A full slot is dropped by `materialize_slots` itself, so "the earliest materialized slot" already means "free".
5. No slot, or no `waiting` entry → **the cascade dies silently**: no log line per tick (this is the steady state), no error, entries sit `waiting` until F22's retention purge takes them.
6. Otherwise offer to the FIFO-oldest `waiting` entry (`ORDER BY created_at`) — D3.

> ponytail: O(tenants × distinct (day,type) pairs with waiting entries) grid materializations per tick. Noise at pilot volume — #12's basis is a 4–5 person queue — and it is the same work one storefront page load does. F29's scale pass revisits.

### D3 — The offer write, and the quiet-hours clamp stated precisely

One transaction, three statements:

1. **Guarded UPDATE** `WHERE id = :entry AND status = 'waiting'` → `offered`, setting `offered_at=now`, `offer_starts_at=slot.starts_at`, `offer_token_hash`, `offer_expires_at`. Zero rows → another worker won; skip the pair, no error. This is the cascade-vs-cascade race answer and it needs no lock.
2. `mint_manage_token()` for the offer token — same primitive, new purpose; the hash commits atomically with the row it authorises.
3. INSERT `scheduled_messages(kind='waitlist_offer', waitlist_entry_id=…, booking_id=NULL, send_after=now, manage_token=<raw>)`. `IntegrityError` on the new pending-unique index converges rather than double-sending, exactly as the reminder's does.

**The clamp, in one pure function** `offer_expiry(now, slot_starts_at, *, window, min_lead) -> datetime | None`, computed in Jerusalem wall clock:

```
expires_at = min(now + window, slot_starts_at - min_lead)
return None if expires_at <= now else expires_at
```

with the quiet-hours rule stated as the single sentence it is: **quiet hours gate the cascade, never the window.** An expiry is never extended and a send is never deferred. Three worked cases, because the brief asks for them:

- **An offer generated at 21:30** — none is. Step 2 returns before step 3; the cascade resumes at 08:00 and offers then, with a full 2-hour window starting at 08:00. The clock never runs on an offer she has not been sent.
- **An offer that would expire inside quiet hours** — an offer issued at 20:59 expires at 22:59, and that is correct and deliberate. She was texted while awake, the window is hers, and at 22:59 the slot returns to the pool and stays directly bookable all night. The *next* offer waits for 08:00. The rejected alternative — extending the window across the quiet block — would hold a live slot hostage for one bride for ~13 hours, which is the opposite of what the feature is for.
- **A slot 2h30m out at 20:00** — `min(22:00, slot−2h)` truncates the window to 20:30 (#15), so an offer can never expire after the appointment has begun. A slot under 2h out was already excluded at selection.

### D4 — The claim: atomic, one transaction, the same index as direct booking

```
POST /storefront/waitlist/offer     { token }                          → offer facts
POST /storefront/waitlist/claim     { token, name, terms_version }     → BookingCreateResponse (201)
POST /storefront/waitlist/decline   { token }                          → 200
```

All three POST the token in a **body**, never a path or query (`manage.py` D7's rule). The lookup carries its **own** per-tenant anti-scrape limiter instance — never a second key on the booking-lookup limiter (`max_attempts` lives on the limiter; `.memory/limiter-max-is-per-instance`).

`WaitlistClaimService.claim`, one `tenant_session`:

1. Resolve the entry by `offer_token_hash`, then `manage_token_matches` re-compare (the shipped redundant-by-design gate).
2. **The atomic conditional claim**: guarded UPDATE `WHERE id = :entry AND status = 'offered' AND offer_expires_at > :now` → `claimed`, clearing `offer_token_hash`. Zero rows → read the row and answer its state: `claimed` → already-claimed, `expired`/`cancelled` → expired, missing → the same indistinguishable 404 the manage page uses (no oracle). **This one statement is the claim-vs-claim and the expiry-vs-late-claim winner.**
3. **Create the booking through the shipped engine.** The seat arithmetic, the per-tenant advisory lock and `offered_slot` are **not re-implemented** — `create_booking`'s steps 4b–9 are extracted into a shared `claim_seat()` helper in `booking/service.py` that both callers use. A second, subtly-different oversell path is the one thing this feature must not create. Terms: `terms_version` checked against `current` exactly as `create_booking` does → `TermsStaleError` (409, page reloads). `name` comes from the request — `waitlist_entries` has no name column, and F22 deliberately has none.
4. Post-commit, in the router, **the shipped path verbatim**: `open_deposit(...)` then either the confirmation SMS or the deposit `redirect_url`, identical to `POST /storefront/bookings`.

**Exactly one winner against a direct booking.** The claim and the direct booker contend on the same `pg_advisory_xact_lock` and, behind it, the same `idx_bookings_slot_seat_unique`. If the direct booker commits first, the claim's `offered_slot` returns `None` (or its INSERT raises `IntegrityError`) → `SlotUnavailableError` → **the whole transaction rolls back, including step 2**, so the entry stays `offered`. The offer page renders «התור הזה נתפס בינתיים» with a link to `/book`. If the claim commits first, the direct booker gets the shipped 409 `SLOT_UNAVAILABLE` she would get from any other race — no new code, no new copy, and she cannot tell a waitlist claimer from another bride.

No eager cascade advance on a lost claim: the slot is gone, so there is nothing to advance *to*. The offer expires on its own clock and the entry leaves the pool then. *ponytail: skipped eager advance; add if the pilot shows brides staring at dead offers.*

**Decline** is a guarded UPDATE `offered → cancelled` (F22's existing "off the list" state — she said no, and it must leave the active-unique predicate) plus cancelling the pending message. The cascade advances on the next tick.

### D5 — The deposit interplay, exhaustively

**The whole answer is that no deposit code is written.** The claim runs `create_booking`'s branch, so a deposit-on type produces `status='pending_payment'` and `open_deposit`'s `redirect_url` in the claim response — the shipped flow, the shipped hold, the shipped sweeper.

- **Claim on a deposit-required type** → booking in `pending_payment` + F19's 15-minute hold + the payment link in the claim response. The entry is `claimed` the moment the row commits, **even unpaid** — correct, because every occupancy predicate excludes only `cancelled`, so the seat is genuinely hers for the hold's duration and no one else can take it.
- **Hold expires unpaid** → the **existing** `DepositSweeper` cancels the booking (`allowed_from=('pending_payment',)`, `cancelled_by='expired'`) and the seat frees structurally. The cascade's next tick sees free capacity and a `waiting` entry and offers to the next bride. **No re-fire hook exists or is needed** (conflict 3) — this is D2's second dividend.
- **The expired claimer stays `claimed`, terminal — she does not return to `waiting`.** She was offered, she claimed, she did not pay. Re-queueing her to the head of the FIFO would let one bride hold a slot indefinitely by claiming-and-not-paying in a loop, which is precisely the "must not hold the slot forever" failure the epic names. She may rejoin (F22's active-unique predicate excludes `claimed`, so the join succeeds) or book directly. That is the "nor lose it unfairly" half.
- **Paid-but-slow webhook after hold expiry** → F19's shipped answer runs unchanged: `honour_late_settlement` marks the payment paid, `_free_seat` looks for a seat, `rebind` confirms her booking and re-arms the reminder; no seat → `None` → `notify_payment_received_no_slot`, owner alerted, manual refund. **The waitlist consequence, stated:** between her hold expiring and her money landing, the cascade may already have offered that slot and another bride may have claimed it. At capacity 1, `_free_seat` then returns `None` and she lands in F19's existing owner-alert branch — the identical outcome a direct booker taking the seat would produce. **The waitlist changes the probability, not the mechanism, and nothing new is owed.** Recorded as an accepted consequence; the pilot-visible symptom is a rise in `notify_payment_received_no_slot` alerts, which is the metric to watch if `deposit_hold_seconds` needs raising.

### D6 — The offer claim surface

New storefront route `/w/{token}` (`RouteName` `"offer"`, `OfferPage.tsx`), token opaque in the client — an unknown or dead token must reach the page so the page renders its own state (the `manage` route's verbatim rule). **No login**: possession of a token that was sent to her phone is the proof, the same posture as `/b/{token}`.

States, all designed: **live offer** (boutique name, the offered slot's day and time, type name, a countdown to `offer_expires_at`, the shipped terms tick, a name field, claim + decline buttons, F20's shipped privacy line) · **expired** · **already claimed** («התור כבר נקבע. הקישור לניהול נשלח אליך בהודעה» — the raw manage token is minted once and cannot be reproduced, so the SMS is the honest answer) · **declined** · **slot taken in the meantime** (with a link to `/book`) · **unknown/invalid token** (one indistinguishable state). Hebrew-first RTL, `ar` keys shipped untranslated (#47), **no exclamation marks**, axe zero-violation.

No name prefill from `customers` — one field, one ask. *ponytail: skipped prefill.*

### D7 — SMS delivery, and the failure honesty rule

`drain_due` gains a `kind` branch. The `waitlist_offer` path re-reads the **entry** where the reminder path re-reads the booking: not `offered`, or `offer_expires_at <= now` → mark the message `cancelled`, send nothing. Body is a new template beside the reminder's, boutique name truncated to 25 chars (#8), link `https://{slug}.{domain}/w/{token}`, and `mask_manage_link` applied to the `message_log` copy for the same reason the reminder applies it.

**The offer clock must not run on an unsent SMS** (#15's spirit). The rule, in one predicate at the expiry step: **an expiring entry goes to `expired` only if its offer message reached `sent`; otherwise it returns to `waiting`.** That covers both failure shapes verified in `_deliver` — an unconfigured provider (row left `pending`, F16's rule unchanged) and a hard `SmsSendError` (row `failed`) — and it costs one `EXISTS` against `scheduled_messages`.

The residual, recorded: with the provider down, the FIFO-oldest entry is offered and returned to `waiting` once per window, indefinitely. It is a slow loop on **one** entry, not a burn through the queue, it self-heals on the first tick after the adapter returns, and the alternative — expiring the whole queue unread — is strictly worse. One log line at each return-to-waiting makes it visible.

### D8 — Manage visibility (small, enumerated)

F22's `WaitlistSection` and `ManageWaitlistRow` gain exactly three fields — `offer_starts_at`, `offer_expires_at`, and a `Badge` variant for the `offered` status — plus three `bookingWaitlist.*` i18n keys in `he.ts` and their `ar.ts` mirror, and the `HE_F23` block **spread into `HE`** in `i18n.test.ts` with its floor (an unspread block is silently green). **F22's cancel guard widens** to `WHERE status IN ('waiting','offered')` — F22 D5 named this explicitly — and cancelling an `offered` entry must also cancel its pending offer message in the same transaction. No new route, no new nav row, no polling (a waitlist changes at human speed).

---

## Test plan

**The races are the feature.** New `test_waitlist_races_db.py`, `test_deposit_races_db.py`'s shape exactly — two real sessions on real Postgres, `NullPool`, the injected clock moved on both sides:

1. **claim-vs-direct-booking** on the last seat → exactly one booking row, the loser gets 409 `SLOT_UNAVAILABLE`, and the entry reads `claimed` **iff** the claim won (E3 #13's double-book standard).
2. **claim-vs-claim** — two deliveries of one offer token → one booking, one manage token, the second answered already-claimed.
3. **expiry-vs-late-claim** — the cascade's expiry UPDATE interleaved with a claim → never both; a claim committing first takes the seat and the expiry matches nothing.
4. **cascade-vs-cascade / cascade-vs-new-cancellation** — two workers ticking concurrently never produce two live offers for one (day, type); a cancellation landing mid-tick is picked up on the next tick, never lost.
5. **The epic's named hardest problem, end to end** — claim on a deposit type → hold expires → `DepositSweeper` cancels → next cascade tick offers the next FIFO entry; and the claimer stays `claimed`, not `waiting`.
6. **late webhook after a waitlist claimer took the seat** → F19's shipped two-outcome shape, waitlist variant: honoured-and-rebound, or owner-alerted with no seat.

**Unit (non-db)** — `test_waitlist_offer_schedule.py`: the D3 clamp against a frozen clock — inside/outside quiet hours at 20:59, 21:00, 21:30, 03:00, 07:59, 08:00; DST boundaries in Jerusalem; the `slot − min_lead` truncation; `None` when the slot is too close. Template/body budget beside `test_booking_comms_templates.py`.

**db-marked** — migration (both tables, named CHECKs and all three indexes pinned via `pg_get_constraintdef`/`pg_indexes.indexdef`, `booking_id` nullable, the XOR CHECK rejecting both-null and both-set; `test_exactly_one_migration_head` and `test_every_tenant_id_table_has_forced_rls` green unedited) · isolation (`test_waitlist_isolation.py` extended: tenant A's offers and offer tokens invisible to B; the offer-token unique index is global but RLS makes a foreign token a 404) · cascade service (offers FIFO; skips a pair with a live offer; skips slots under the lead; silent when no slot and when no entry; quiet-hours gate issues nothing and expiry still runs) · claim service (happy; deposit branch produces `pending_payment` + `redirect_url`; expired token; already-claimed; declined; stale terms 409) · drain branch (offer sent; entry no longer `offered` → message cancelled, nothing sent; unconfigured provider → pending, entry returns to `waiting` at expiry; `SmsSendError` → `failed`, same return-to-`waiting`) · F22's widened cancel guard cancels an `offered` entry and its pending message.

**API (fast)** — the three storefront routes through TestClient: 200/201/404/409/429, **no new members in any error-code set-equality assertion**; the routes join the cross-tenant walker's table (a new `Kind.WAITLIST_OFFER` populated through the product's own API — cascade the entry under the OTP dev-code path — or exempted with a written reason, which the whole-route-table test forces either way).

**Frontend (vitest)** — `OfferPage.test.tsx`: each of the six states renders; the countdown; claim posts exactly three keys; the terms tick gates the button; error keys map. `WaitlistSection.test.tsx` gains the offer columns and the `offered` badge.

**E2E (Playwright + axe)** — storefront: stub the offer lookup and claim, walk live-offer → terms → name → claim → confirmation, **axe zero-violation** on the live-offer and expired states (IS 5568 is a legal gate), focus lands on the heading at open. Manage: the section shows an offered row with its expiry, axe clean.

**Fixtures** — `offeredWaitlistEntry()` in the manage e2e fixtures beside F22's `bookingWaitlistRow()`; storefront fixtures for the offer states. No new `MANAGE_API` segment (the manage surface adds no route), so `test_spa_serving.py` needs no edit — the storefront config proxies `/storefront` wholesale.

---

## In scope / Out of scope

**In**: the cascade poller, the quiet-hours gate and expiry clamp, the offer write + SMS, the tokenized offer page (claim/decline/expired states), the atomic claim through the shipped booking engine, the deposit branch via the shipped `open_deposit`, expiry + return-to-`waiting` on an unsent offer, three manage fields, the widened F22 cancel guard.

**Out**: **multi-slot offers** (one offer names one instant) · **batch/broadcast offers** (#13 forbids them) · **bride preferences** (time-of-day, "any day this month" — #14 forbids them) · **notification-bell rows — F35 owns that surface** · **portal display of offers — recorded as an F24 follow-up if the pilot asks**; F24 owns its own surface and this spec adds nothing to it · **an owner "offer now" button** and any manual override · **offer analytics / conversion reporting** · **a waitlist toggle in owner settings** — F27's matrix grows a row · **pagination on the manage list** (F22's recorded ceiling, unchanged).

## Risks & open items

1. **The cascade is a poller, so an offer lags a cancellation by up to `worker_poll_interval_seconds` (60s).** Accepted: the alternative is six hooks including two bulk UPDATEs, and a minute is invisible against a 2-hour window. *Trigger: pilot complaint, or F29's scale pass.*
2. **A provider outage loops one entry through offer → unsent → `waiting`, once per window, indefinitely** (D7). Bounded to one entry, self-healing, logged. *Trigger: the log line appearing in production.*
3. **`create_booking`'s tail is refactored into `claim_seat()` so two callers share one oversell path** (D4). The refactor touches the most race-tested function in the repo; the mitigation is that its existing tests must pass **unedited**, and any edit to them is a review stop. *Trigger: code review of the extraction.*
4. **A waitlist claimer can now be the bride who takes a late payer's seat** (D5). No new mechanism, but it raises the rate of F19's owner-alert branch. *Trigger: pilot review of `notify_payment_received_no_slot` volume — the remedy is a longer `deposit_hold_seconds`, one settings row.*
5. **Quiet hours are a wall-clock rule in a DST zone.** `ZoneInfo("Asia/Jerusalem")` handles the shift, but the 03:00 nonexistent-hour case must be a test, not an assumption (D3's unit list). *Trigger: the DST test.*
6. **The migration number will shift.** F24 is building `0027` in a live worktree and F25/F28 are queued. Build at head+1, renumber at rebase, migration last on the branch. *Trigger: rebase.*

## Decisions Log

- **D1 — One additive migration on two tables**: four offer columns + two indexes on `waitlist_entries`; `scheduled_messages.booking_id` nullable + `waitlist_entry_id` + XOR CHECK + widened `kind` CHECK + an offer-side pending-unique index. `manage_token` carries the raw offer token — its existing semantics, so no fifth column. No sixth lifecycle state.
- **D2 — The cascade is a poller keyed off `waiting` entries, not a hook keyed off cancellations.** Six paths free capacity and no single seam covers them; one of them writes no booking at all. Fourth job in `worker.poll_once`, own try block, existing tick, no new process.
- **D3 — Quiet hours gate the cascade, never the window.** No offer is issued inside `[21:00, 08:00)` Jerusalem; expiry runs at all hours; `expires_at = min(now + window, slot_starts_at − min_lead)`, never extended, never deferred. One pure function, unit-tested against a frozen clock.
- **D4 — The claim is one guarded conditional UPDATE (`offered ∧ unexpired → claimed`) followed by the SHIPPED booking engine** under its own advisory lock and `idx_bookings_slot_seat_unique`, in one transaction. `create_booking`'s tail is extracted to `claim_seat()` rather than duplicated. The loser of a direct-booking race gets the shipped 409 `SLOT_UNAVAILABLE` in both directions. Decline reuses `cancelled`.
- **D5 — The deposit interplay writes no deposit code**: the claim rides `open_deposit` and F19's hold; an expired claim-hold is cancelled by the existing sweeper and the freed seat is found by D2's poller (no re-fire hook). **The unpaid claimer stays `claimed`** — terminal, so a slot cannot be held by a claim-and-don't-pay loop; she may rejoin. The late-webhook answer is F19's, unchanged; the waitlist changes its probability, not its mechanism.
- **D6 — One tokenized page at `/w/{token}`, no login**, token in a POST body, six designed states, its own anti-scrape limiter instance.
- **D7 — Offers ride `drain_due` with a kind branch, and the clock does not run on an unsent SMS**: an expiring entry goes `expired` only if its message reached `sent`, otherwise back to `waiting`.
- **D8 — Manage gains three fields and one badge variant**; F22's cancel guard widens to `offered` and cancels the pending message with it.
- **Gate 1 — self-approved under Interview Q1**: not on the stop-list, no money surface authored (D5), no new privacy Hebrew. The gate reopens if the design ever writes a payment path of its own.
