# Plan: Feature 23 — Waitlist auto-reallocation loop (Epic E5)

**Spec**: `.planning/specs/waitlist-auto-reallocation.md` (2026-08-06, Gate 1 self-approved, D1–D8)
**Design**: `.planning/design/screens/waitlist-auto-reallocation/design.md` (Design Gate accepted 2026-08-06 — **R1 binds: no countdown**, P1–P4 taken, F-O1…F-O4 owed)
**Plan written**: 2026-08-06. **Observed alembic head on `origin/main`: `0026_waitlist_entries.py`.** Build the migration as **head+1 resolved at build time**, and **expect to renumber**: F24 holds `0027` in a live worktree and F25/F28 are queued (§5).
**Depends on**: F22 (`waitlist_entries`, five states, 0026), F16 (`scheduled_messages` + `drain_due` + `worker.poll_once`), F19 (`DepositSweeper`, `open_deposit`, `honour_late_settlement`), F13 (`create_booking`'s advisory lock + `idx_bookings_slot_seat_unique`) — all merged.
**Worktree**: `.worktrees/waitlist-auto-reallocation`, branched from `origin/main`.

---

## 0. How to read this plan

Every task is one TDD cycle: the named failing test first, then the code that makes it pass. **The races are the feature** — §3 is the acceptance contract and its file is authored whole at B1, before any cascade or claim code exists. Backend before frontend. Spec D1–D8 and design R1 are binding and not restated. Every path below was verified against the tree on 2026-08-06.

## 1. Verified facts the tasks lean on

| Claim | Verified at |
|---|---|
| Head migration `0026_waitlist_entries.py`; F22's module is `app/waitlist/` (`router.py`, `manage_router.py`, `schemas.py`, `service.py`, `validation.py`) | `Backend/migrations/versions/`, `Backend/app/waitlist/` |
| `WaitlistEntriesRepository` = `insert`/`by_active_tuple`/`list_active`/`cancel`/`by_id` | `Backend/app/db/repositories/waitlist_entries.py:22-125` |
| `poll_once` runs drain then sweep, each in its own `try`, `for tenant in await tenants.list_active()` | `Backend/app/worker.py:68-120` |
| `drain_due` re-reads the **booking** per claimed row; unconfigured provider `break`s leaving rows pending; `SmsSendError` → `failed` | `Backend/app/booking/comms.py:400-478` |
| `_expire_holds` — the guarded-bulk-UPDATE shape to copy (id-subquery bound, `synchronize_session=False`, answer off `RETURNING`) | `Backend/app/payments/sweeper.py:156-194` |
| `offered_slot(session, *, tenant_id, starts_at, now, rules, exceptions, bookings)` → `Slot | None`; it builds `booked` from `count_by_start` and calls `materialize_slots` for one boutique day | `Backend/app/booking/slots_io.py:75-115` |
| `create_booking`'s tail: `pg_advisory_xact_lock(hashtext(:tenant_id))` at `:388` → `offered_slot` `:447` → `active_seats_at` `:475` → INSERT → `IntegrityError` → `SlotUnavailableError` `:515` | `Backend/app/booking/service.py:251-539` |
| `mint_manage_token` / `manage_token_hash` / `manage_token_matches` | `Backend/app/booking/tokens.py:15-23` |
| Template helpers: `truncate_boutique_name`, `manage_link`, `mask_manage_link`, `ucs2_segments`, `jerusalem_weekday/date/time` | `Backend/app/booking/comms_templates.py:58-111` |
| `ScheduledMessage.booking_id` is `nullable=False`; `manage_token` already documented as "raw link token while pending" | `Backend/app/models/scheduled_message.py:29,35` |
| Settings present: `waitlist_join_*`, `waitlist_retention_days=30`, `worker_poll_interval_seconds=60`, `deposit_hold_seconds=900` | `Backend/app/core/config.py:119-269` |
| F22's limiters are **own instances** built in `create_app()` at `:855-866` — the pattern for the offer lookup limiter | `Backend/app/main.py` |
| **There is no `test_waitlist_isolation.py`** (spec §Test plan names one). Waitlist isolation ships inside `test_waitlist_db.py::test_another_tenants_entries_are_invisible` | `Backend/tests/test_waitlist_db.py:228` |
| Token-gated storefront routes are **exempt with a reason** in the walker, not walked («possession, not tenancy»), and `test_the_exemptions_each_carry_a_reason` asserts the **count** | `Backend/tests/test_cross_tenant_walker.py:345-372, 1010` |
| Race-file shape to mirror: `NullPool` engine per driver + `asyncio.gather` | `Backend/tests/test_deposit_races_db.py:61,145` |
| `RouteName` union + `RouteMatch`; the `manage` route's "token is opaque here" rule | `Frontend/apps/storefront/src/router.tsx:27-66` |
| `Facts` is a **local function inside** `ManageBookingPage.tsx:106`, not a shared component — its *shape* is reused, not the symbol | `Frontend/apps/storefront/src/routes/ManageBookingPage.tsx` |
| Terms prose is inline in `BookPage.tsx`'s terms step (F-O4's two-callers problem is real) | `Frontend/apps/storefront/src/routes/BookPage.tsx:637-644` |
| Storefront reused keys all exist: `errors.termsStale` `:112`, `booking.acceptTerms` `:259`, `booking.confirmWhen` `:284`, `booking.payHandoff` `:313`, `manage.rebookCta` `:409` | `Frontend/apps/storefront/src/i18n/he.ts` |
| Storefront i18n test has no per-prefix floor except the `F19_KEYS` block — mirror that shape | `.../__tests__/i18n-keys.test.ts:201` |
| Manage `bookingWaitlist.*` block incl. `statusOffered` («הוצע תור») already ships; `HE_F22` spread at `i18n.test.ts:130,150` | `Frontend/apps/manage/src/i18n/he.ts:2458-2489` |
| `getBookingWaitlist` / `cancelBookingWaitlistEntry` + `BookingWaitlistRow` | `Frontend/apps/manage/src/api.ts:662-685, 1845-1857` |
| **There is no `Frontend/e2e/fixtures/storefront.ts`** — storefront stubs are inline `page.route` blocks per spec file | `Frontend/e2e/waitlist.spec.ts:80-101`, `Frontend/e2e/fixtures/` |
| Storefront vite proxies `/storefront` wholesale → **no proxy edit**; manage gains no route → **no `MANAGE_API` edit** | `Frontend/apps/storefront/vite.config.ts:15` |

## 2. Migration `00NN_waitlist_offers.py`

Raw SQL, `0026`'s template. Exactly spec D1's DDL: four columns on `waitlist_entries` (`offered_at`, `offer_expires_at`, `offer_starts_at`, `offer_token_hash`) + `idx_waitlist_entries_offer_token` (partial unique) + `idx_waitlist_entries_offer_expiry`; on `scheduled_messages` `booking_id DROP NOT NULL`, `waitlist_entry_id`, the named XOR CHECK `ck_scheduled_messages_subject`, the widened `scheduled_messages_kind_check`, and `idx_scheduled_messages_offer_pending_unique`. Each index carries its rationale as a comment **at the index** (0018's demand). **No `enable_tenant_rls` re-run** — `ADD COLUMN` preserves policies. Downgrade drops all of it and restores `booking_id NOT NULL` (safe: every legacy row has one).

## 3. The race matrix — the acceptance contract, authored FIRST

`Backend/tests/test_waitlist_races_db.py` (new, **`db`-marked**), `test_deposit_races_db.py`'s shape verbatim: two real sessions on a `NullPool` engine, `asyncio.gather`, the injected clock moved on both sides. **All six functions are written at task B1 and are red until Phase C lands.** That red never reaches CI — B and C are one push.

| # | Function | Mirrors (shipped) | Asserts |
|---|---|---|---|
| 1 | `test_a_claim_and_a_direct_booker_race_the_last_seat_and_exactly_one_wins` | `test_deposit_races_db.py::test_two_brides_race_for_the_last_seat_and_the_unpaid_hold_keeps_it` | one `bookings` row; loser gets 409 `SLOT_UNAVAILABLE` either direction; entry is `claimed` **iff** the claim won, and **`offered` (not `expired`) when it lost** — the rollback covers step 2 (D4, design F-O2) |
| 2 | `test_two_deliveries_of_one_offer_token_book_once_and_mint_one_manage_token` | `::test_two_concurrent_deliveries_confirm_once_text_once_and_log_once` | one booking, one manage token, second call answers already-claimed |
| 3 | `test_the_expiry_sweep_and_a_late_claim_never_both_win` | `::test_the_sweeper_and_the_webhook_never_both_win_the_same_hold` | claim-first → `claimed` and the expiry UPDATE matches nothing; expiry-first → claim answers expired and books nothing |
| 4 | `test_two_cascade_ticks_never_produce_two_live_offers_for_one_pair` | `::test_the_crash_window_is_repaired_exactly_once_by_concurrent_redeliveries` | the guarded `WHERE status='waiting'` UPDATE is the only arbiter — one `offered` entry, one pending `waitlist_offer` row; a cancellation landing mid-tick is picked up next tick, never lost |
| 5 | `test_an_unpaid_claim_hold_expires_and_the_next_fifo_entry_is_offered` (**cascade re-entry — the epic's named hardest problem**) | `::test_an_orphaned_hold_is_swept_and_the_seat_really_goes_to_another_bride` | claim on a deposit type → `pending_payment` → `DepositSweeper.sweep` cancels → next `WaitlistCascade` tick offers the next FIFO entry; **the claimer stays `claimed`, never back to `waiting`** (D5) |
| 6 | `test_a_late_webhook_after_a_waitlist_claimer_took_the_seat_has_exactly_two_outcomes` | `::test_a_late_delivery_racing_a_new_bride_has_exactly_two_outcomes` | F19's shipped shape unchanged: rebound-and-confirmed, or `notify_payment_received_no_slot` with no seat |

## 4. Ordered task list

### Phase A — schema, ORM, settings, the clamp (commit 1)

| # | Task | Test first | Files (C=create, M=modify) |
|---|---|---|---|
| A1 | Migration per §2. | `test_migrations.py::test_migration_00NN_adds_the_offer_columns` (**db**) — four columns; both new indexes and `idx_scheduled_messages_offer_pending_unique` pinned via `pg_indexes.indexdef`; both named CHECKs via `pg_get_constraintdef`; `booking_id` nullable; the XOR CHECK **rejects both-null and both-set**; `::test_migration_00NN_round_trips`. `test_exactly_one_migration_head` + `test_every_tenant_id_table_has_forced_rls` green **unedited** | C `Backend/migrations/versions/00NN_waitlist_offers.py`, M `Backend/tests/test_migrations.py` |
| A2 | ORM + repo: four `Mapped` fields on `WaitlistEntry`; `ScheduledMessage.booking_id` → `uuid.UUID | None` + `waitlist_entry_id`. Repo gains `offer(entry_id, …)` (guarded UPDATE `WHERE status='waiting'`, returns rowcount), `expire_offers(now)` (bulk, `_expire_holds`'s shape, `RETURNING id`), `return_to_waiting(ids)`, `by_offer_token_hash`, `claim(entry_id, now)` (guarded UPDATE `status='offered' AND offer_expires_at > now`), `waiting_pairs(from_day)` (distinct `(day, type)` **minus pairs holding an `offered` entry**), `oldest_waiting(day, type)`. `ScheduledMessagesRepository` gains `insert(..., waitlist_entry_id=)` and `pending_for_entry` / `cancel_pending_for_entry`. | `test_waitlist_db.py` extended (**db**) — offer guard moves 0 rows on an already-`offered` row; expiry bulk returns exactly the due ids; claim guard refuses an expired row; `waiting_pairs` skips a pair with a live offer; FIFO tie-break on `created_at`; **cross-tenant: tenant A's offer token is invisible to B** (the unique index is global, RLS makes it a 404) — extends `::test_another_tenants_entries_are_invisible`, no new file | M `Backend/app/models/waitlist_entry.py`, M `Backend/app/models/scheduled_message.py`, M `Backend/app/db/repositories/waitlist_entries.py`, M `Backend/app/db/repositories/scheduled_messages.py`, M `Backend/tests/test_waitlist_db.py` |
| A3 | Four settings (`waitlist_offer_window_seconds=7200`, `waitlist_quiet_start_hour=21`, `waitlist_quiet_end_hour=8`, `waitlist_offer_min_lead_seconds=7200`) + the two pure functions: `offer_expiry(now, slot_starts_at, *, window, min_lead) -> datetime | None` and `in_quiet_hours(now, *, start_hour, end_hour) -> bool`, both in Jerusalem wall clock. | `test_waitlist_offer_schedule.py` (**non-db**, new) — frozen clock at 20:59 / 21:00 / 21:30 / 03:00 / 07:59 / 08:00; the `slot − min_lead` truncation at 2h30m lead; `None` when the slot is too close; **Jerusalem DST both directions incl. the nonexistent 03:00 hour** (spec Risk 5) | M `Backend/app/core/config.py`, C `Backend/app/waitlist/schedule.py`, C `Backend/tests/test_waitlist_offer_schedule.py` |

### Phase B — the cascade (commit 2) — **races authored first**

| # | Task | Test first | Files |
|---|---|---|---|
| B1 | **Author `test_waitlist_races_db.py` whole** — all six §3 functions, real assertions, no `skip`. Red until C3. | this IS the test; §3 is its spec | C `Backend/tests/test_waitlist_races_db.py` |
| B2 | `WaitlistCascade.run(tenant)` step 1 — expire first, at all hours (D2.1): bulk UPDATE `offered ∧ offer_expires_at <= now` → `expired`, clearing `offer_token_hash`/`offer_expires_at`; then cancel each entry's pending `waitlist_offer` row. **D7's rule: an entry whose offer message never reached `sent` returns to `waiting` instead** — one `EXISTS` against `scheduled_messages`, one log line per return. | `test_waitlist_cascade.py` (**db**, new) — a due offer expires and its pending message is cancelled; a `pending` (unconfigured provider) message → entry back to `waiting`, logged; a `failed` message → same; a `sent` message → `expired`; expiry runs **inside** quiet hours | C `Backend/app/waitlist/cascade.py`, C `Backend/tests/test_waitlist_cascade.py` |
| B3 | Steps 2–6: quiet-hours gate returns before any offer; `waiting_pairs(from_day=today_jerusalem)`; per pair build the day grid the way `offered_slot` does (`list_active` rules + exceptions + `count_by_start` → `materialize_slots`) and take the earliest slot with `starts_at > now + min_lead`; no slot or no entry → **silent** (no log, no error); otherwise the D3 offer write in one transaction — guarded UPDATE (0 rows → skip the pair, no error) → `mint_manage_token()` → INSERT `scheduled_messages(kind='waitlist_offer', waitlist_entry_id=…, booking_id=None, send_after=now, manage_token=<raw>)`, `IntegrityError` converges. | `test_waitlist_cascade.py` extended (**db**) — offers the FIFO-oldest; skips a pair already holding an `offered` entry; skips a slot inside the lead; silent when no free slot and when no `waiting` entry; quiet hours issue nothing; the offer row carries the raw token and the entry only its sha256; `offer_expiry` returning `None` issues nothing. **§3 #4 greens here** | M `Backend/app/waitlist/cascade.py`, M `Backend/tests/test_waitlist_cascade.py` |
| B4 | Fourth job in `worker.poll_once`, **its own try block**, after the sweep; wired in `main`/worker construction. | `test_worker.py` — every active tenant is cascaded once per tick; a cascade failure does not stop the other tenants **and does not defer their drain or sweep**; a quiet tick totals to nothing (mirrors `::test_one_tenants_failure_does_not_silence_the_others`) | M `Backend/app/worker.py`, M `Backend/tests/test_worker.py` |

### Phase C — the claim (commit 3)

| # | Task | Test first | Files |
|---|---|---|---|
| C1 | Extract `create_booking`'s steps 4b–9 (`service.py:388-539`) into `claim_seat(session, *, tenant_id, starts_at, customer_id, appointment_type_id, deposit_due, now)` used by **both** callers. Pure refactor. **Risk 3's mitigation is the gate: every existing booking/deposit/race test passes UNEDITED — any edit to one is a review stop.** | no new test. `test_booking_*`, `test_deposit_*_db.py`, `test_deposit_races_db.py` all green **unedited** | M `Backend/app/booking/service.py` |
| C2 | `WaitlistOfferService`: `lookup(token)` → offer facts; `claim(token, name, terms_version)` — one `tenant_session`: `by_offer_token_hash` → `manage_token_matches` re-compare → the atomic guarded claim (0 rows → read the row and answer its state; missing → the same indistinguishable 404 the manage page uses) → terms check → `customers.upsert` → `claim_seat`. `SlotUnavailableError` rolls the whole transaction back, **entry stays `offered`**. `decline(token)` → guarded `offered → cancelled` + cancel the pending message. | `test_waitlist_offer_service.py` (**db**, new) — happy claim (no deposit) → `confirmed` + manage token; deposit type → `pending_payment`; expired token; already-`claimed`; `cancelled`; unknown token → 404; stale terms → `TermsStaleError`; decline cancels entry **and** its pending message | C `Backend/app/waitlist/offer_service.py`, M `Backend/app/waitlist/schemas.py`, C `Backend/tests/test_waitlist_offer_service.py` |
| C3 | Three routes `POST /storefront/waitlist/offer|claim|decline`, **token in the body**, `_no_store`; **its own** `FixedWindowRateLimiter` instance in `create_app()` (`waitlist_offer_lookup_*` settings) — never a second key on the booking-lookup limiter (`.memory/limiter-max-is-per-instance`). Post-commit in the router: `open_deposit(...)` then confirmation SMS or `redirect_url`, byte-for-byte `POST /storefront/bookings`'s tail. Walker: the three routes join `UNWALKABLE` with the shipped possession-not-tenancy reason pointing at `test_waitlist_offer_token.py`; **bump the count in `test_the_exemptions_each_carry_a_reason`**. | `test_waitlist_offer_api.py` (fast, new) — 200/201/404/409/429; **no new members in any error-code set-equality assertion**. `test_waitlist_offer_token.py` (**db**, new, `test_manage_token.py`'s shape) — a foreign tenant's offer token 404s. `test_cross_tenant_walker.py::test_the_walk_and_the_exemptions_are_the_whole_route_table` reds on the new routes until this lands — that red IS the failing test. **§3 #1,2,3,5,6 green here** | C `Backend/app/waitlist/offer_router.py`, M `Backend/app/main.py`, M `Backend/app/core/config.py`, C `Backend/tests/test_waitlist_offer_api.py`, C `Backend/tests/test_waitlist_offer_token.py`, M `Backend/tests/test_cross_tenant_walker.py` |
| C4 | D8's widened owner guard: `WaitlistService.cancel_entry` accepts `status IN ('waiting','offered')` and cancels the pending offer message in the **same transaction** (shares C2's decline path). Audit `details` unchanged — still no phone. | `test_waitlist_service.py` extended (**db**) — cancelling an `offered` entry moves it to `cancelled` **and** its pending message to `cancelled`; second tap still idempotent; audit `details` **key-set equality** holds | M `Backend/app/waitlist/service.py`, M `Backend/app/db/repositories/waitlist_entries.py`, M `Backend/tests/test_waitlist_service.py` |

### Phase D — the offer SMS (commit 4)

| # | Task | Test first | Files |
|---|---|---|---|
| D1 | `waitlist_offer_sms_body(*, boutique_name, slot_starts_at, deadline, offer_url)` beside the four shipped bodies — design §1's exact Hebrew, `truncate_boutique_name`, absolute deadline, **no exclamation mark, no urgency, no delivery promise**. **F-O1: append the weekday word when the deadline's Jerusalem calendar day differs from the send day**, else bare `HH:MM`. | `test_booking_comms_templates.py` extended (**non-db**) — exact body at a 25-char name + longest weekday; `ucs2_segments <= 3` at the 30-char slug budget (198 ≤ 201); the F-O1 conditional fires on a >3h window and does not on the default; `mask_manage_link` hides the raw token; **zero `!`** | M `Backend/app/booking/comms_templates.py`, M `Backend/tests/test_booking_comms_templates.py` |
| D2 | `drain_due` gains the `kind` branch: `waitlist_offer` re-reads the **entry** (not the booking) — not `offered`, or `offer_expires_at <= now` → mark `cancelled`, send nothing. Link `https://{slug}.{domain}/w/{token}` via a `link_for` sibling. Unconfigured-provider and `SmsSendError` behaviour unchanged. | `test_booking_comms_db.py` extended (**db**) — offer sent and marked `sent`; entry no longer `offered` → message `cancelled`, nothing sent; expired offer → same; unconfigured provider → row stays `pending` (and B2's rule then returns the entry to `waiting`); `SmsSendError` → `failed`; **a reminder row in the same batch is unaffected** | M `Backend/app/booking/comms.py`, M `Backend/tests/test_booking_comms_db.py` |

### Phase E — storefront `/w/{token}` (commit 5)

| # | Task | Test first | Files |
|---|---|---|---|
| E1 | **F-O4**: extract `BookPage.tsx`'s inline terms prose + `Checkbox` (incl. the `refundWindow`/`forfeit` R19 splits) into `components/booking/TermsConsent.tsx`. Two callers, one legal render. | `BookPage.test.tsx` passes **unedited** (the extraction is behaviour-preserving); `TermsConsent.test.tsx` (new) — renders the prose, the tick gates its callback | C `Frontend/apps/storefront/src/components/booking/TermsConsent.tsx`, M `Frontend/apps/storefront/src/routes/BookPage.tsx`, C `.../__tests__/TermsConsent.test.tsx` |
| E2 | `RouteName` gains `"offer"`, `RouteMatch` gains `{ name: "offer"; token: string }` (**token opaque — a dead token must reach the page**), `DOC_TITLE_KEYS` entry, `/w/{token}` parse. `OfferPage.tsx` per design §2: facts card (`ManageBookingPage`'s `Facts` **shape**, reused labels), **static absolute deadline line — NO countdown, no timer, no poll (R1, and it is the SC 2.2.1 audit answer)**, weekday+date conditional when the deadline is not today, `TermsConsent`, name `Input`, claim + two-step decline reveal with the consequence sentence (§2.1), F19's `payHandoff` hand-off verbatim on `redirect_url` (§2.2). All ten states L/A/A2/B/C/D/E/F/G/H/I/J from design §3, incl. **F stays a live-offer state** (F-O2). `api.ts`: three calls + wire types. | `OfferPage.test.tsx` (new) — each state renders its designed copy; **no element updates without a user action** (the R1 regression guard); claim posts **exactly three keys** (`Object.keys` equality); unticked terms and empty name gate the button; 409 `SLOT_UNAVAILABLE` → `offer.gone`, 409 `TERMS_STALE` → `errors.termsStale` with the tick cleared; 404 → `manage.invalid`; deposit response renders the hand-off. `router.test.tsx` — `/w/{token}` parses, an unknown token still routes | M `Frontend/apps/storefront/src/router.tsx`, C `.../routes/OfferPage.tsx`, M `.../api.ts`, C `.../__tests__/OfferPage.test.tsx`, M `.../__tests__/router.test.tsx` |
| E3 | i18n: design §8's **fourteen** `offer.*` keys in storefront `he.ts`; `ar.ts` mirrors the Hebrew untranslated (#47). Everything else reused — **no new error keys, no new privacy Hebrew**. | `i18n-keys.test.ts` — an `F23_KEYS` block mirroring the shipped `F19_KEYS` shape at `:201`, `toBeGreaterThanOrEqual(14)` + the ar-presence walk; the existing zero-`!` assertion covers the new copy | M `Frontend/apps/storefront/src/i18n/he.ts`, M `.../i18n/ar.ts`, M `.../__tests__/i18n-keys.test.ts` |

### Phase F — manage, three fields (commit 6)

| # | Task | Test first | Files |
|---|---|---|---|
| F1 | `WaitlistSection.tsx`: one «ההצעה» column between status and joined-at, rendering `—` unless the row is `offered`, else the offered slot's day+time plus `bookingWaitlist.offerUntil` + `<bdi dir="ltr">{expiry}</bdi>` on a muted second line. `offered` badge → **`variant="warning"`** (P4). The danger label on an `offered` row is `bookingWaitlist.cancelOfferedConfirm` (design §4). **No polling, no pagination, no cascade history, no new nav row** (so `guide.ts` and `MANAGE_API` are untouched). | `WaitlistSection.test.tsx` extended — the offer column renders for `offered` and `—` for `waiting`; the badge variant; the offered-row danger label differs from the generic one; `min-h-[44px]` preserved | M `Frontend/apps/manage/src/components/WaitlistSection.tsx`, M `.../__tests__/WaitlistSection.test.tsx` |
| F2 | `BookingWaitlistRow` gains `offer_starts_at` / `offer_expires_at` (nullable). i18n: design §9's three `bookingWaitlist.*` keys in `he.ts` + `ar.ts`; **`HE_F23` spread into `HE`** in `i18n.test.ts` with `toBeGreaterThanOrEqual(3)` — an unspread block is silently green. | `i18n.test.ts` — the spread + the floor; the ar-presence guard binds via the new keys | M `Frontend/apps/manage/src/api.ts`, M `.../i18n/he.ts`, M `.../i18n/ar.ts`, M `.../__tests__/i18n.test.ts` |

### Phase G — e2e + axe (commit 7)

| # | Task | Test first | Files |
|---|---|---|---|
| G1 | `offeredWaitlistEntry()` factory beside F22's `bookingWaitlistRow()` in the manage fixtures. **Storefront offer stubs go inline in the spec file** — there is no storefront fixture module. | consumed below | M `Frontend/e2e/fixtures/manage.ts` |
| G2 | `offer.spec.ts` (per-feature file, `waitlist.spec.ts`'s pattern). Storefront: stub lookup + claim; walk live-offer → tick → name → claim → confirmation; **focus lands on the h1 at open**; the decline reveal opens, focuses the question, Escape returns focus to the trigger; **F-O2: after the 409 «התור הזה נתפס בינתיים», a reload re-renders the LIVE offer** — asserted so a later reader does not read it as a bug. **axe zero-violation (IS 5568) on: live offer, expired, the open decline reveal**, and in the manage half on the section showing an offered row. | this IS the test | C `Frontend/e2e/offer.spec.ts` |

## 5. Build environment — RECORD, these are facts not suggestions

- **No Docker locally.** Tests marked `db` or `s3` run **on CI only**. Do not chase local db-test failures.
- **The local fast lane (`-m 'not db'`) points at a CLOSED Postgres port by design (F21).** A test that dials a real DB without the `db` marker **fails locally — that is correct**, not a bug to fix. Every new db-touching test MUST carry the `db` marker; §3's whole file does.
- **The worktree has no `Backend/.env`.** Config-default tests behave differently than in the main checkout — there a failure is REAL (`.memory/local-env-breaks-config-tests`).
- **Local gates, all must pass before push**: `make lint` · backend non-db tests (`make test`) · `make fe-test` · `make fe-build` · `make e2e`.
- The db-marked tests' first run is CI (`.memory/boutique-ci-first-run-surprises`) — write them carefully against §3 and the spec's test plan.

## 6. Build discipline

**Commit boundaries** (conventional, scoped):
1. `feat(waitlist): offer columns, scheduled-message subject XOR, offer schedule (00NN)` — A1-A3.
2. `feat(waitlist): the offer cascade as a fourth worker job` — B1-B4 (**the race file lands here, red**).
3. `feat(waitlist): the atomic offer claim through the shipped booking engine` — C1-C4 (**greens it**).
4. `feat(waitlist): the offer SMS body and the drain kind branch` — D1-D2.
5. `feat(storefront): the offer page at /w/{token}` — E1-E3.
6. `feat(manage): the offer column on the waitlist section` — F1-F2.
7. `test(e2e): offer page and manage offer column with axe` — G1-G2.

**Migration renumber protocol**: build at `alembic heads` + 1 **resolved at build time** (observed `0026` → `0027`), and **expect a collision** — F24 holds `0027` in a live worktree, F25/F28 are queued. Keep the migration the **last commit on the branch**; immediately before the pre-push rebase re-run `alembic heads` against rebased main and, if taken, renumber (filename + `revision` + `down_revision`) in one `fix(waitlist):` commit. A reserved-but-wrong number breaks alembic outright and reds every db test (`.memory/parallel-alembic-numbering`).

**Pathspec**: git tracks `backend/`/`frontend/` **lowercase**. `git add Backend/…` silently skips modified tracked files — lowercase every pathspec, verify with `git show --stat` (`.memory/git-add-uppercase-pathspec-trap`).

**Frontend build check**: `pnpm build` before staging any `.ts`/`.tsx`.

**Focus/dialog assertions belong to Playwright, not vitest** — jsdom has no `<dialog>` and setup.ts stubs it; only state assertions are valid in vitest (`.memory/jsdom-has-no-dialog`). The decline reveal is not a dialog, but its focus-movement assertions still measure real browsers only (G2).

**After any merge-conflict resolution**: parse every touched test file's collection count — a broken file reads as one `Tests no tests` line, not N failures (`.memory/silently-unexecuted-test-files`). §3's file is the one that matters most.

**Do not "fix" two deliberate behaviours**: an entry stays `offered` after a lost claim race (F-O2), and no eager cascade advance happens on a lost claim (D4).

## 7. Risks this plan adds to the spec's list

- **R-A — `claim_seat()` (C1) is a refactor of the most race-tested function in the repo.** The gate is that no existing test is edited. If a shipped test *must* change to accommodate the extraction, the extraction is wrong — inline the duplication question to review rather than editing the test.
- **R-B — the three offer routes are exempted from the cross-tenant walker, not walked.** That is the shipped precedent for token-gated routes, but an exemption is only honest if `test_waitlist_offer_token.py` actually exists and proves the foreign-token 404. Land C3's two files together.
- **R-C — `WaitlistCascade` builds a day grid by re-assembling what `offered_slot` does internally.** If that assembly drifts from `slots_io`'s, the cascade will offer slots the booking engine refuses. Prefer calling into `slots_io` for the grid; if a new helper is needed, put it **there**, not in `cascade.py`.
- **R-D — `test_the_exemptions_each_carry_a_reason` asserts a count** (`test_cross_tenant_walker.py:1010`). Adding three exemptions without bumping it reds a test that reads like an unrelated failure.
