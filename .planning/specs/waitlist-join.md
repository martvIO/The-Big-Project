# Spec: F22 — Waitlist join + entries model (Epic E5)

**Created**: 2026-08-06 · **Status**: **Gate 1: standing approval — interview-2026-07-30.md §Standing approvals.** Q1's stop-list is enumerated (F17, F18, F19, F20, F29, F48) and F22 is not on it. It is not a money surface (no deposit, no payment row — the deposit interplay is F23's, and E5 features ship deposit-free until Grow lands, Interview Q7). The one legal edge — the join collects a phone from the subject, a new §11 collection point — is discharged by **reusing the shipped platform privacy notice verbatim** (D4): zero new legal Hebrew, so the gate does not reopen. · **Epic**: `.planning/epics/e5-growth.md` Feature 22 · **Effort**: **M** — one new table + module, one storefront endpoint, two manage endpoints, one inline storefront reveal, one console section, and three legal ripples (export, erase, retention) that are the reason this is not S.
**Depends on**: **F12** (slot engine: `SLOT_WINDOW_MAX_DAYS`, the day grid), **F13** (booking core: `consume_verification` inside the transaction, limiter-per-instance discipline), **F14** (BookPage: the slot step where the full-day state renders). All merged.
**Feeds**: **F23** (auto-reallocation) reads this table's `waiting` entries FIFO and owns offers/cascade/claim. The status lifecycle below is the shared contract.

---

## Problem

A fully-booked day turns brides away with nothing but «אין תורים פנויים ביום הזה» (`SlotPicker`'s `noSlots` state, `packages/ui/src/components/SlotPicker.tsx:87-94`). The demand evaporates: when a slot frees (cancellation, expired deposit hold), the boutique has no one to offer it to. E5's first thrust is recovering that demand; F22 builds the entries model and the join, F23 builds the reallocation.

## Goal

On the `/book` slot step, when the picked day has no times, a CTA appears under the empty state: «הצטרפות לרשימת ההמתנה». It opens an **inline reveal** (not a dialog — `ManageBookingPage.tsx:425`'s recorded preference) that takes a phone, proves it with the **same F11 OTP primitive the booking flow uses** — the shipped `POST /storefront/otp/send` + `/otp/verify`, unchanged — and creates one `waitlist_entries` row bound to **(tenant, day, appointment type) + the verified phone, FIFO by join time** (pre-decided #14, restated authoritatively in `LOOP-STATE.md`'s F22 note). The owner sees and cancels entries in `/manage`. Nothing else: offers, cascade, claim, deposit interplay are all F23.

## What already exists to build on (verified against code)

- **The OTP primitive is two shipped anonymous endpoints** — `POST /storefront/otp/send` (204) and `POST /storefront/otp/verify` → single-use `verification_token` (`notifications/router.py:52-65`), with per-phone / per-tenant / per-IP send budgets and a verify budget as four separate limiter instances (`main.py:801-826`). F13 consumes the token inside the booking transaction: `consume_verification(session, …)` so the burn commits or rolls back with the write (`booking/service.py:318-322`, `notifications/service.py:377-390`). The join reuses exactly this shape.
- **The full-day state is one branch** — `SlotPicker` renders `labels.noSlots` when `times.length === 0`; `BookPage` owns the labels and the picked `date` (YYYY-MM-DD string) and renders `TypePicker` **above** `SlotPicker` (`BookPage.tsx:1236-1278`), so at the moment the empty state shows, the appointment type the entry binds to is already pickable on the same screen.
- **The new-table template is `0018_queue_tickets.py`**: `_STANDARD` columns (uuid PK via `uuid_generate_v4()`, `tenant_id`, timestamps, `deleted_at`), TEXT not VARCHAR, named CHECKs, partial index for active rows, `_updated_at_trigger`, `GRANT … TO app_user`, `enable_tenant_rls(table)` (`app/db/rls.py`). `test_every_tenant_id_table_has_forced_rls` covers any new `tenant_id` table automatically — the migration must call the helper or that test reds.
- **A stored Jerusalem DATE is the ruled day mechanism** — `queue_tickets.queue_day` is a stored `DATE` computed in Python via `today_jerusalem(clock)`, never a DB expression, with the reasons written into `0018`'s comment. The waitlist `day` is the same kind of value, except the customer picks it.
- **`app/queue/` is the module layout to mirror**: `router.py` (storefront, anonymous), `manage_router.py`, `schemas.py`, `service.py`, `validation.py`.
- **The manage gate is structural** — router-level `require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)` (`customers/router.py:72-79`, `booking/owner_router.py:81-85`); `test_staff_role_gating.py`'s walker reads `allowed_roles` off the live route table, so new routes are policy-checked with no new test. The SMC locked matrix admits **all-five or exactly-two** gates only.
- **The cross-tenant walker closes over the whole route table** — `test_cross_tenant_walker.py::test_the_walk_and_the_exemptions_are_the_whole_route_table` forces every new route to be either walked (its id kind populated through the product's own API) or exempted with a written reason.
- **The vite trap is real and tested** — `apps/manage/vite.config.ts` proxies `/manage` API calls by an explicit segment alternation (`MANAGE_API`), and `Backend/tests/test_spa_serving.py` derives that set from the live route table and asserts the config line matches: a new `/manage/waitlist` segment reds that test until the alternation gains `waitlist`. The storefront config proxies `/storefront` wholesale — no change needed there. `frontend/e2e/fixtures/manage.ts` mirrors the same segment set and must gain it too.
- **F20's subject surfaces enumerate PII tables by phone** — `export_subject` selects `queue_tickets` rows by `(tenant_id, phone)` (`privacy/service.py:217-231`), `erase_subject` scrubs their phone (`:497-518`), and `app/privacy/retention.py` is a policy registry with named future consumers. A new phone-bearing table **must** join all three or the §13/§14 answers are silently incomplete.
- **Zero-new-error-code toolkit**: `NOT_FOUND` (404, `DomainNotFoundError`), `VALIDATION_ERROR` (400), `PHONE_NOT_VERIFIED`, `OTP_INVALID`/`OTP_EXPIRED`, and the 429 rate-limit handler are all app-level (`main.py:196-263, 1020-1145`).

## Where the brief and the code disagree

| # | The brief says | The code says | Taken as |
|---|---|---|---|
| 1 | (naming, implicit) the feature is "the waitlist" | **The name is taken.** F58 shipped a walk-in-queue "waitlist": `WaitlistPanel.tsx`, api.ts types `Waitlist`/`WaitlistEntry`, ~37 `waitlist.*` keys in manage `he.ts`, e2e fixtures `waitlistEntry()`/`waitlist()`. | **F22 uses distinct names everywhere in `apps/manage`**: types `BookingWaitlistRow`/`BookingWaitlistList`, component `WaitlistSection.tsx`, i18n `bookingWaitlist.*`, fixture `bookingWaitlistRow()`. The backend table/route (`waitlist_entries`, `/manage/waitlist`) collide with nothing — `queue_tickets` routes live under `/manage/floor` and `/storefront/checkin`. Storefront `he.ts` has no `waitlist.*` block; F22 takes it there. |
| 2 | F33's `0018` deleted a `(tenant, day, phone)` partial unique index and recorded two reasons any later reader "must answer before re-adding any uniqueness here" | Both reasons are answered by this feature's different trust posture (D1): the join's refusal is only visible to a caller who **proved possession of the phone via OTP**, so there is no presence oracle; and F22 ships an owner cancel, so a stuck key has an in-product remedy. | The unique index is taken, with the answers recorded at the index (D1). |
| 3 | `architecture.md` §data-model: "Later: waitlist/queue/staff/alteration tables per epics E5–E9" | queue/staff/alteration have since shipped (0018, 0015, 0020). | Stale enumeration, no conflict. F22 adds the waitlist table it reserves. |

## Design

### D1 — The table: `waitlist_entries`, one migration, `0018`'s template

**Revision id and `down_revision` resolve from `alembic heads` at build time — head reads `0025` today, so this is *head+1*, never a number this file pins** (0018's own header records the renumber-at-rebase hazard; the migration stays the last commit on the branch).

```sql
CREATE TABLE waitlist_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    day DATE NOT NULL,                    -- Jerusalem-local, computed in Python (0018's ruling)
    appointment_type_id UUID NOT NULL,    -- no FK, app-level integrity (house rule)
    phone TEXT NOT NULL,                  -- normalize_israeli_mobile output, matches customers.phone spelling
    status TEXT NOT NULL DEFAULT 'waiting'
        CHECK (status IN ('waiting','offered','claimed','expired','cancelled'))
);

-- One ACTIVE entry per (tenant, phone, day, type). Rationale at the index, per 0018's demand:
--   * no presence oracle — the refusal is only reachable through an OTP-proven caller,
--     so it reveals the caller's own state to herself and nothing to anyone else;
--   * no stuck key — cancelled/claimed/expired leave the predicate, the owner cancel
--     (D5) is the remedy F33 lacked, and a stale 'waiting' key blocks only re-joining
--     a PAST day, which is unbookable anyway.
CREATE UNIQUE INDEX idx_waitlist_entries_active_unique
    ON waitlist_entries (tenant_id, phone, day, appointment_type_id)
    WHERE deleted_at IS NULL AND status IN ('waiting','offered');

-- The list/cascade read path: one day's entries, FIFO. deleted_at-only predicate so
-- F20's retention sweep sees closed rows (0018's reasoning, inherited).
CREATE INDEX idx_waitlist_entries_tenant_day
    ON waitlist_entries (tenant_id, day) WHERE deleted_at IS NULL;
```

Plus, verbatim from the 0018 template: `trg_waitlist_entries_updated_at`, `GRANT SELECT, INSERT, UPDATE, DELETE ON waitlist_entries TO app_user`, `enable_tenant_rls("waitlist_entries")`. Downgrade: `DROP TABLE IF EXISTS waitlist_entries` (touches no existing table, nothing to un-touch).

**The status lifecycle is F23's contract, decided now**: `waiting → offered → claimed | expired | cancelled`. **F22 writes only `waiting` (join) and `cancelled` (owner cancel).** The CHECK ships all five states so the lifecycle is pinned where F23 cannot re-litigate it, and F23's offer bookkeeping (`offered_at`, `offer_expires_at`, offer token hash, expiry-cascade cursor) is **F23's own additive migration** — speculative columns nobody writes are exactly what 0018's unwritten-column comment had to apologize for, and F23's spec owns the offer/claim design (`architecture.md` locked row: sequential offers, expiry cascade, atomic conditional-update claim against the bookings partial unique index — the *claim* races on `bookings`, not on this table). Whether `expired` is terminal or re-queues is also F23's (pre-decided #12/#15 constrain it); every state F23 could need is representable today.

**No name column, no dress binding, no terms, no marketing consent, no position.** Pre-decided #14: entry = (tenant, day, type) + phone, "no per-dress waitlists, no priority scoring". A join from a dress-bound `/book/{dressId}` flow still writes a type+day entry only. Terms are accepted at *booking* time — F23's claim runs the booking path, which enforces them. Marketing consent has no field because the offer SMS is a **requested** message, outside the Spam Law's marketing restriction (pre-decided #12's basis) — and an absent field is the only spelling a future caller cannot flip (F50 D3b's rule). Position is computed nowhere and returned to no one: quiet hours (pre-decided #12) will make strict-position promises false, and FIFO is `ORDER BY created_at` when F23 needs it (pre-decided #14: "FIFO is one ORDER BY").

ORM: `app/models/waitlist_entry.py`, `StandardColumns` + explicit columns matching the DDL. Repository: `app/db/repositories/waitlist_entries.py`.

### D2 — Storefront join: `POST /storefront/waitlist`, and it is F13's create shape minus the booking

```
POST /storefront/waitlist        (201)
{ "phone": "05…", "verification_token": "…", "day": "2026-08-20", "appointment_type_id": "<uuid>" }
→ { "day": "2026-08-20", "appointment_type_id": "<uuid>", "status": "waiting" }
```

New module `app/waitlist/` mirroring `app/queue/` (`router.py`, `manage_router.py`, `schemas.py`, `service.py`, `validation.py`). The router mounts under the existing `/storefront` prefix with `_no_store`, like `notifications/router.py`.

The service method, in one `tenant_session`, in F13's order:
1. `normalize_israeli_mobile(phone)`; validate `day`: `today_jerusalem(clock) <= day <= today + SLOT_WINDOW_MAX_DAYS` — outside → 400 `VALIDATION_ERROR`.
2. **Check both join budgets, spend after proof** (F13's comment at `booking/service.py:300-313`, applied verbatim): tripped → the shipped 429.
3. `consume_verification(session, …)` — false → `PhoneNotVerifiedError` (shipped 400).
4. `AppointmentTypesRepository.by_id` — `None` (unknown or archived) → `DomainNotFoundError` (shipped 404).
5. INSERT `status='waiting'`. **`IntegrityError` from the active-unique index → re-read the existing active row and return the same 201 body — the duplicate join is idempotent.** She asked to be on the list; she is. This is also the whole race answer: two concurrent joins for one tuple collapse to one row and two identical answers, and it is what keeps the feature at zero new error codes. (The token was burned either way — a duplicate join spends her verification, which is correct: single-use is the token's contract.)

**The server deliberately does not verify the day is actually full.** Requiring fullness at join is a TOCTOU race against concurrent cancellations, and the CTA only renders on an empty day (D4). A hand-crafted join for an open day strands its own author until the day fills and frees — bounded, recorded as an accepted limit, and F23's matching logic is the layer that could ever say otherwise.

**No `customers` write.** The row a booking creates is "proof of phone possession" (`models/customer.py:12-15`); a waitlist entry carries its own proven phone and creates no customer until F23's claim runs the real booking path. **No response id**: there is no customer-side management in F22 (Out of scope), and an id on the wire is a capability shape with no consumer (F58's A29 lesson).

### D3 — Rate limits: the OTP budgets are shared by construction; the join budget is its own two instances

The join reuses the OTP **endpoints**, so the per-phone/per-tenant/per-IP *send* budgets and the *verify* budget are the same `app.state.otp_service` instances the booking flow spends — **correct, not accidental**: one phone proving itself is one proof, whichever flow consumes it, and a second budget would double the SMS-cost exposure per phone.

The join endpoint itself gets **its own two `FixedWindowRateLimiter` instances** in `create_app()` — `waitlist_join_max_per_phone_window` / `waitlist_join_max_per_tenant_window` (+ `_seconds`, config names in F13's pattern) — and never a key on `BookingService`'s `create_limiter`: `max_attempts` lives on the limiter, so a shared instance is one ceiling for both surfaces and waitlist joins could eat the booking budget (`.memory/limiter-max-is-per-instance`, restated at every limiter in `main.py`).

### D4 — The §11 collection point, and why Gate 1 still self-approves

The join collects a phone from the subject — a genuine new collection point under Amendment 13. The reveal therefore renders the boutique's **shipped** privacy notice line (`boutique.privacy_notice_text`, the same text the BookPage details step and F33's check-in form stand behind) above the send button, and F20's §11 collection-point table (`ppl-compliance.md` §11) gains a row naming this surface. **No new legal text is authored** — the platform default (Interview Q8) covers it, which is the entire Gate 1 argument: F22 is off Q1's stop-list *and* writes no privacy-law Hebrew of its own.

Three ripples that make this feature M, all in F20's surfaces, all landing in the same PR as the migration (F50 Risk 2's discipline):
- **Export** (`privacy/service.py::export_subject`): a `waitlist_entries` array (day, type name, status, created_at) selected by `(tenant_id, phone)` — mirror of the `queue_tickets` block at `:217-231`, plus the `ExportedWaitlistEntry` schema and its `api.ts` type-only mirror.
- **Erase** (`erase_subject`): scrub `phone` to the `erased:{id}` spelling on this table too (mirror of `:497-518`); an erased phone can rejoin later — new OTP, new entry, new consent context — which is correct.
- **Retention** (`privacy/retention.py`): one PURGE policy — the row *is* the personal data, `queue_tickets`' class — for entries whose `day` is more than `waitlist_retention_days` (setting, default 30) behind `today_jerusalem`. Predicate is falsified by its own DELETE, satisfying D22's registry rule. Flagged for counsel at F21 with the rest of pre-decided #10.

### D5 — Manage: list + cancel, two-role gate, one audit member

```
GET  /manage/waitlist?day=YYYY-MM-DD      → { "entries": [ { id, day, appointment_type_id,
                                              appointment_type_name, phone, customer_name|null,
                                              status, created_at } ] }
POST /manage/waitlist/{entry_id}/cancel   → the same row shape
```

- Router-level `require_role(OWNER, SHIFT_MANAGER)` + `_no_store` — the `customers/router.py` shape verbatim. Exactly-two, matching the booking-management gate: the SMC matrix forbids a three-role gate, and cancel is a mutation reception should route through a manager. The role walker covers both routes with no new test.
- `day` optional; default = all active (`status IN ('waiting','offered')`, `deleted_at IS NULL`) entries for `day >= today`, ordered `(day, created_at)` — FIFO visible as list order. No pagination: the population is bounded by the booking horizon × realistic queue depth (pre-decided #12's "4–5 person queue"); recorded as a ceiling, F25/F29 revisit if a tenant proves it wrong.
- `customer_name` is a decoration: one `(tenant, phone)` lookup against `customers` (phone is unique per tenant) — app-level join, no FK, `null` for a phone the boutique has never booked. The phone itself ships on the row deliberately: it is the disambiguator and the owner's only way to call her (`customers/schemas.py:27-34`'s reasoning).
- **Cancel is a guarded UPDATE** — `SET status='cancelled' WHERE status='waiting'` (F23 widens the guard for `offered` when offers exist); zero rows + row exists → return the row as-is (idempotent; a double-tap is not an error). Unknown/foreign id → the shipped 404. Audit: one new `AuditAction` member `WAITLIST_ENTRY_CANCELLED` (`waitlist_entry_cancelled`), `action` is CHECK-less TEXT so no migration; `details` carries `{entry_id, day, appointment_type_id}` and **no phone** (F20's `phone_last4` rule made moot by carrying no phone at all).
- **The walkers**: the cancel route carries an id path param, so the cross-tenant walker needs a `Kind.WAITLIST_ENTRY` populated through the product's own API — the storefront join with the OTP dev-code path (`otp_dev_code` setting, the walker already patches settings). Exemption-with-reason is the fallback the whole-table test forces if that proves awkward; the plan decides, the obligation is named here.

### D6 — Storefront UI: CTA + inline reveal on the slot step

`BookPage.tsx`, slot step. When `times.length === 0` **and** `flow.typeId !== null` (the entry binds to a type; `TypePicker` sits directly above), a secondary Button «הצטרפות לרשימת ההמתנה» renders under `SlotPicker`'s empty state. Without a type picked, the empty state stands alone — the CTA must not invite a join it cannot bind.

The reveal (new `components/booking/WaitlistJoin.tsx`, inline expand — no Modal, no route change, the flow's step machinery untouched):
1. Phone `Input` + the D4 privacy-notice line + send Button — the verify step's shipped conventions copied, not re-derived: 60s resend cooldown (`OTP_RESEND_COOLDOWN_MS`), send-budget mirror (`OTP_SEND_BUDGET`), one label for send and resend.
2. Code `Input` + join Button once sent.
3. On 201: the reveal is replaced by a confirmation line — «נרשמת לרשימת ההמתנה ליום {{date}}. אם יתפנה תור, נשלח לך הודעה.» — `role="status"`, **no exclamation mark** (the register rule), and no promise of *when*: the SMS claim is F23's to make true, and the copy survives F23 by promising only what the cascade does.
4. Errors render via the shipped `errorKey` mapping (`api.ts:64-66` handles `OTP_INVALID`/`OTP_EXPIRED`; `errors.validation`, `errors.phoneNotVerified`, 429 → existing keys). The idempotent duplicate needs no error state at all.

States: default / sending / code-entry / joining / confirmed / error — all six designed, empty is N/A (the reveal opens with the phone field).

i18n: new nested `waitlist` block in storefront `he.ts` (~10 keys: cta, phoneLabel, notice-reuse, send, resend, codeLabel, join, confirmed, plus errors reused) and the same keys in `ar.ts` with Hebrew values (pre-decided #47's file rule).

### D7 — Manage UI: `WaitlistSection.tsx`

New nav row `{ key: "waitlist", labelKey: "nav.bookingWaitlist", roles: ["owner", "shift_manager"] }` in `App.tsx`'s NAV, mirroring the backend gate. **`SectionKey` is guide-typed**: `lib/guide.ts`'s `satisfies Record<SectionKey, …>` makes a new key without guide steps a type error — the section ships its one-step guide entry in the same commit.

The section: a date filter (`DateField`, default today) over a plain table — day, type name, `customer_name ?? phone` (phone via `isolateLtr`, the numeric-run rule), status `Badge`, joined-at time, and a cancel Button per active row with one confirm click. Simple fetch-on-mount + refetch-on-mutate; **no `usePoll`** — a waitlist changes at human speed and carries no freshness claim; the shipped sections that poll (board, floor) poll because brides physically move.

Types in `api.ts`: `BookingWaitlistRow`, `BookingWaitlistList`, `getBookingWaitlist(day?)`, `cancelBookingWaitlistEntry(id)` — the F58 collision (conflict 1) makes the `bookingWaitlist` spelling load-bearing, not stylistic. i18n: `bookingWaitlist.*` keys (~12) in manage `he.ts` + `ar.ts` mirror, and a new `HE_F22` block **spread into `HE`** in `i18n.test.ts` with its floor — an unspread block is silently green (the file's own warning).

**Registration trap, named**: `MANAGE_API` in `apps/manage/vite.config.ts` gains `waitlist` in the alternation (test_spa_serving.py reds until it does), and `frontend/e2e/fixtures/manage.ts`'s mirrored segment set gains it too, plus stub handlers (`bookingWaitlistRow()` fixture) for the section's GET.

## Test plan

**Unit (non-db)** — `test_waitlist_validation.py`: day-bounds math against a frozen clock (today ok, horizon edge ok, past/beyond → validation error); phone normalization reuse; schema shapes.

**db-marked** —
- Migration (`test_migrations.py` conventions): table exists with named CHECK and both partial indexes pinned via `pg_get_constraintdef`/`pg_indexes.indexdef`; round-trip test; `test_exactly_one_migration_head` and `test_every_tenant_id_table_has_forced_rls` stay green unedited (the latter is the RLS assertion).
- Isolation (`test_waitlist_isolation.py`, `test_booking_isolation.py`'s shape, non-owner role, NullPool): tenant A's entries invisible to B; **the active-unique index is per-tenant** — same (phone, day, type) inserts under two tenants both succeed; manage routes join the cross-tenant walker's table (D5).
- **Uniqueness race**: two concurrent joins for one tuple → one row, both callers answered 201 with the same body (the F13 double-book test's standard, applied to the entry).
- Service: happy join; duplicate join idempotent (one row, token burned); unknown/archived type 404; day validation 400; unverified token → `PHONE_NOT_VERIFIED`; budgets: own-instance join limiters trip without touching the booking budget (assert `BookingService`'s limiter unspent). Manage: list FIFO order; day filter; `customer_name` decoration null and non-null; cancel happy + idempotent + foreign-id 404; audit row with no phone in `details`.
- Privacy ripples: export answers a subject's waitlist entries; erase scrubs the phone and the entry survives as evidence; retention purges a past-day entry and leaves today's; the D22 predicate-falsification loop in `test_retention_db.py` covers the new policy by construction.

**API (fast)** — routes join the role walker's table by existing (no edit); the manage matrix asserts shift_manager succeeds and the route is absent from `OWNER_ONLY`; storefront join through TestClient: 201/400/404/PHONE_NOT_VERIFIED/429, no new members in any error-code set-equality assertion.

**Frontend (vitest)** — `WaitlistJoin.test.tsx`: CTA absent when slots exist and when no type is picked; present on the empty day; notice line renders before send; cooldown disables resend; join posts exactly four keys; confirmation replaces the form; error keys map. `WaitlistSection.test.tsx`: rows render, cancel fires and refetches, empty state. `i18n.test.ts`: `HE_F22` spread + floor; ar-presence guard binds via the new prefixes.

**E2E (Playwright + axe)** — storefront: stub an empty day + OTP routes, walk CTA → phone → code → confirmation, axe zero-violation on the open reveal (IS 5568); focus lands on the phone input at open. Manage: stub the new segment in the fixtures harness, open the section, cancel an entry, axe clean.

## Out of scope (all F23 unless said otherwise)

- **Offers, expiry cascade, claim, quiet hours, offer SMS** — the whole reallocation loop, including widening `scheduled_messages.kind` (pre-decided #16) and the claim's race against direct booking. The deposit interplay rides with it.
- **Any customer-facing management beyond join + confirmation** — no lookup, no customer cancel, no position display. F24's portal is the natural home if the pilot asks.
- **Offer bookkeeping columns** — F23's additive migration (D1).
- **A waitlist toggle in owner settings** — F27's matrix grows a row when F23 makes the feature externally visible; an entries model with no offers needs no switch.
- **Pagination on the manage list** (D5's recorded ceiling) and **any change to F58's queue waitlist** — the two waitlists stay disjoint by name and by table.

## Risks & open items

1. **An entry can exist for a day with open capacity** (D2's no-fullness-check). Bounded: the CTA gates the honest path, and F23's matching decides whether such an entry ever gets an offer. *Trigger: F23's spec, which owns matching.*
2. **The F58 naming collision is a standing trap** — `waitlist.*` vs `bookingWaitlist.*` one file apart invites the wrong import or key. Mitigated by distinct type/component/fixture names (conflict 1) and the i18n floors. *Trigger: review of any file touching both.*
3. **`waiting` entries for past days accumulate until retention purges them** — they hold no unique key that matters (D1) and the manage default filter hides them, but a 30-day window of dead rows is visible to an owner who filters backwards. Accepted; the sweep is the remedy. *Trigger: pilot feedback on the list.*
4. **The join burns a verification token even on an idempotent duplicate** (D2 step 5). Correct by the token's single-use contract, but a bride double-tapping through a slow network spends two SMS. The 60s resend cooldown bounds it. *Trigger: pilot SMS-cost review.*
5. **F23 inherits a lifecycle it did not write** (D1's CHECK). Deliberate — the contract is pinned where the cascade cannot bend it — but if F23's design genuinely needs a sixth state, it is one CHECK-widening migration (0025's `lemonsqueezy` precedent). *Trigger: F23's spec.*

## Decisions Log

- **D1 — Entry = (tenant, day, appointment_type) + OTP-verified phone, FIFO by `created_at`** (pre-decided #14, LOOP-STATE note authoritative). **Active-uniqueness per exact tuple** via partial unique index; F33's two recorded objections answered at the index (no oracle behind OTP; owner cancel is the remedy). **Status CHECK ships all five lifecycle states; F22 writes two; offer columns are F23's migration.** No name, no dress, no terms, no consent field, no position.
- **D2 — Join is F13's create shape minus the booking**: budgets checked-then-spent-after-proof, token consumed in-transaction, 201, **idempotent duplicate via IntegrityError → re-read** — zero new error codes. No fullness check (TOCTOU; UI gates). No `customers` write, no id on the wire.
- **D3 — OTP budgets shared by construction (same endpoints, same instances — correct); join budget is its own two limiter instances**, never a key on the booking limiter (`.memory/limiter-max-is-per-instance`).
- **D4 — The join is a new §11 collection point, discharged by reusing the shipped platform notice verbatim** — zero new legal Hebrew keeps Gate 1 self-approval. Export + erase + retention (PURGE, `waitlist_retention_days` default 30) land in the same PR as the migration.
- **D5 — Manage = GET list + POST cancel, exactly-two gate (owner, shift_manager), guarded idempotent UPDATE, one CHECK-less `AuditAction`, no phone in audit details.** Cross-tenant walker fed via the storefront join under the OTP dev code, or exempted with a written reason.
- **D6/D7 — Inline reveal on the slot step (no Modal, no new route), type-gated CTA; new manage section with guide-typed `SectionKey`; `bookingWaitlist` naming in `apps/manage` because F58 owns `waitlist` there; `MANAGE_API` + e2e fixture segment sets gain `waitlist`.**
- **Gate 1 — self-approved under Interview Q1**: not on the stop-list, no money surface, and the legal edge is reuse-not-authorship (D4). The gate reopens if the design ever authors new privacy text or adds a deposit branch.
