# Plan: Feature 15 — Owner booking management (Epic E3, last feature)

**Status**: Gate 2 self-approved 2026-07-30 under Interview Q1.

**Spec**: `.planning/specs/owner-booking-management.md` (Gate 1 self-approved 2026-07-30, D1–D20, 33 review findings folded in) · **Design**: `.planning/design/screens/owner-bookings/owner-bookings.md` (`design-critic` rev 1 REVISE → 3 accepted → ACCEPT) · **Copy**: `.planning/design/screens/owner-bookings/copy.md` (77 rows, DRAFTED, flagged for the user's one-line edit) · **Branch**: `feature/owner-booking-management` · **Created**: 2026-07-30

TDD throughout. Local gate per task: `make lint` + `make test` for backend tasks, `pnpm -r lint && pnpm -r typecheck && pnpm -r test` for frontend ones, `bash Frontend/scripts/qa-greps.sh` clean from Task 17 onward. **`db`-marked tests are written here and executed only on CI** — there is no Docker locally. The tasks a local run cannot verify are listed in §"What a local run cannot prove".

F15 ships **no migration** (D1). `test_every_tenant_id_table_has_forced_rls` staying green is the assertion that none snuck in.

---

## Interview and spec rulings this plan is built on

| Ruling | Effect on the build |
|---|---|
| **Q1** — enumerated stop-list is F17/F18/F19/F20/F29/F48; F15 is not on it | Gate 2 self-approves. Risk 2 (owner-attested phone) is **re-nagged in the run report** and is a named row for the F21 audit; it does not stop the build. |
| **Q3 / pre-decided #47** | `apps/manage/src/i18n/ar.ts` is created in Task 13 carrying F15's keys only, values = the approved Hebrew, never `""`. `lng` stays `"he"`, no switcher. |
| **Q6** | Day filter only; **no owner-created bookings**. The `/manage/bookings` list takes `?date=` and nothing else (D17). |
| **Q2 / design gate** | Assembled from shipped components. P-1…P-6 are built as designed; P-1 (`booking.deliveryNotice`) and P-5 (the `booking.error.*` map) are the two the user may edit — both are one-line edits in `he.ts`/`ar.ts` after merge. |
| **D12** | Three shipped signatures are taken from the **code**, not from `booking-comms.md`. A plan written from the spec text would fail at the first call. |
| **pre-decided #38** | IS 5568 / WCAG 2.0 AA is a legal requirement. The a11y items in Tasks 14–16 are not optional polish. |

---

## Four contradictions found inside the spec — recorded, resolved, and amended into the spec in Task 0

The spec is binding and D1–D20 are not re-litigated. These are four places where the document disagrees with **itself or with the shipped tree**, and a plan cannot proceed without picking one side. Every resolution is the smaller of the two edits, and none of them touches a D-decision's substance.

### C1 — the owner-role guard raises an error the error table does not carry

D20 and the API section both require `if staff.role != StaffRole.OWNER: raise NotAuthorizedError`, and the Testing section requires "**a non-`OWNER` `StaffRole` is refused on every route**". But D19's table has **no** row for it, and D19 says "**two new error codes, three new handlers**" (transition, customer-already-booked, resend-throttled). `main.py:96` has no error registry — an unmapped typed error is a bare 500 — and `SPEC_ERROR_CODES` is asserted by **set equality** (`test_catalog_api.py:947-952`). So as written, either the guard's test asserts a 500, or the pinned literal red-fails on first run.

**Resolution (smallest edit):** a **fourth** new error class `NotAuthorizedError` in `app/booking/owner.py`, a **fourth** handler returning 403 `NOT_AUTHORIZED_BODY`, and a `NOT_AUTHORIZED` row added to D19's table and to `SPEC_ERROR_CODES`. Declined: reusing `NotAuthenticatedError` (401 for a staff member holding a live session is a lie, and it would make E6's assistant indistinguishable from a logged-out browser), and dropping the guard (D20's whole argument is that the guard must exist **before** E6 adds a second `StaffRole` member).

### C2 — the D8 rotation set needs a repository read the spec never names

D8's ruling table requires, on the non-collision branch, "for **every live booking of that customer** (`status='confirmed' AND starts_at > now`, one query over `idx_bookings_tenant_customer`, `0008:101-104`)". `BookingsRepository` has no such method: `active_at` is one instant, `list_confirmed_without_manage_token` filters on `manage_token_hash IS NULL`, and `count_by_start` is a count. The named constants table and the D5 writer list do not mention it.

**Resolution:** one new method, `BookingsRepository.list_live_for_customer(session, tenant_id, *, customer_id, after) -> list[Booking]`, predicate `customer_id = :c AND status = 'confirmed' AND starts_at > :after AND deleted_at IS NULL`, ordered by `starts_at`, riding `idx_bookings_tenant_customer`. It is exactly the query D8's parenthesis describes; the spec simply never gave it a name. Added to the D5/D8 writer inventory in Task 0.

### C3 — D20's `qa-greps.sh` pattern cannot run, and could not pass if it did

D20 and the frontend section both specify adding `Intl\.DateTimeFormat\((?![^)]*timeZone)` to the date-read block. Verified against the shipped script and the shipped sources, **both halves fail**:

**(a) The syntax is not ERE.** `qa-greps.sh:48` is `grep -rnE`. `(?!…)` is a PCRE lookahead; POSIX ERE has none. Run today, that alternation aborts the grep:

```
$ grep -rnE 'getDay\(\)|Intl\.DateTimeFormat\((?![^)]*timeZone)' apps/manage/src
grep: error at position 39 … invalid syntax
```

and because line 49 ends `2>/dev/null || true`, the error is swallowed, `$zoned` comes back empty, and the block prints **`ok  no unzoned date reads`** while checking nothing at all. The pattern would not merely fail to catch F15's formatters — it would silently retire the four checks that work today. `grep -P` is not a fix either: BSD grep has no `-P`, so it is not portable between a dev macOS box and CI.

**(b) The pattern is line-based and every *correct* formatter in the repo is multi-line.** Verified: `BookPage.tsx:82, 88, 132, 136`, `ManageBookingPage.tsx:18, 24` and `packages/ui/src/lib/hours.ts:86` all open `Intl.DateTimeFormat(` on one line and put `timeZone:` on the next. A single-line negative lookahead flags all seven — and **F15's own `lib/jerusalem.ts` is a verbatim port of `BookPage.tsx:82-93`**, so it would be flagged too, making Task 17's own "Done when … prints **none** of F15's own files" unreachable by construction.

**Resolution (still one warning-only block, still no exit-status change):** match only a **complete single-line** construction and drop the zoned ones with a second grep. Both real offenders — `HoursSection.tsx:15` and `TermsSection.tsx:9` — are single-line; every correctly-zoned formatter is either multi-line (no closing `)` on the line, so no match) or carries `timeZone` on the line (filtered). `partsOf(formatter: Intl.DateTimeFormat, …)` at `BookPage.tsx:95` does not match either — no `(` follows the name.

```bash
zoned=$( { grep -rnE 'getDay\(\)|getDate\(\)|toLocaleDateString|toLocaleTimeString' \
             apps/storefront/src apps/manage/src packages/ui/src;
           grep -rnE 'Intl\.DateTimeFormat\([^)]*\)' \
             apps/storefront/src apps/manage/src packages/ui/src | grep -v timeZone; \
         } 2>/dev/null || true)
```

This is D20's decision (a mechanical backstop for unzoned formatters, warning-only, F15 does not fix the two pre-existing files) implemented with a pattern that runs. Declined: `grep -P` (not portable), a multi-line `-z` scan (a parser in a checklist script), and dropping the backstop (D20's whole point is that the rule had none).

### C4 — D8/D10 put `record_failure` "after the post-commit send returns", but the send is the router's

D10 says the limiter is `record_failure`d "on the **success** path"; D8's rate-limit paragraph says "after the post-commit seam returns". D11 and `booking/router.py:18-23` put every send **in the router**, not the service. So as written the limiter would have to be spent by the router — which means threading the limiter, or a `spend()` hook, out of `OwnerBookingService` and into `owner_router.py` for three of the ten routes.

**Resolution:** the service spends the budget **immediately after its own transaction commits**, before returning to the router. Nothing is lost: `_deliver` swallows both provider exceptions and returns `False` (`comms.py:403-435`), so "after the send returns" and "after the commit" differ only in a value nobody branches on — and the thing D10 meters is the owner tap that *caused* a real SMS attempt, which is exactly the committed mutation. D10's substance is untouched: own instance, key `booking:owner_sms:{tenant_id}`, checked **before** the transaction opens so a 429 writes nothing and sends nothing, resend + phone + reschedule metered, cancel not. Declined: a `spend()` call in the router (limiter plumbing in three handlers to move one line).

---

All four are amended into the spec in **Task 0**, in the same PR — the `booking-comms.md` Task-1 precedent for a plan-phase spec amendment.

---

## Task 0 — This plan, and the four spec amendments
`.planning/plans/owner-booking-management.md` (this file), `.planning/specs/owner-booking-management.md`

- Amend D19's error table with the `NOT_AUTHORIZED` 403 row and change "two new error codes, three new handlers" → "three new error codes, four new handlers" (C1).
- Amend D5/D8's writer inventory with `BookingsRepository.list_live_for_customer` (C2).
- Amend D20 and the frontend section's qa-greps paragraph with C3's runnable two-grep form, and record why the lookahead cannot ship.
- Amend D8's rate-limit paragraph and D10 with C4: `record_failure` fires in the service, immediately post-commit.
- Note on the copy deck that P-1 and P-5 remain the user's one-line edits post-merge; do **not** flip the deck's status — that is the user's, not the loop's.
- **Done when**: both amendments are in the spec and this file is committed. No code, no tests.
- Commit: `docs(planning): F15 implementation plan — Gate 2 self-approved`.

---

# Part I — the three pure refactors, first, because they touch shipped code

These three land before any new behaviour so that a bisect can separate "the refactor broke something" from "F15 broke something". Each is **behaviour-neutral by construction** and each names the existing tests that prove it. No new test is written in Part I; a new assertion here would be indistinguishable from a behaviour change.

## Task 1 — `_offered_slot` becomes module-level `offered_slot` (D5)
`Backend/app/booking/slots_io.py` (**new**), `Backend/app/booking/service.py`

- New module, one coroutine, verbatim body from `service.py:362-399` with its docstring:
  ```python
  async def offered_slot(
      session: AsyncSession, *, tenant_id: uuid.UUID,
      starts_at: datetime.datetime, now: datetime.datetime,
      rules: AvailabilityRulesRepository,
      exceptions: AvailabilityExceptionsRepository,
      bookings: BookingsRepository,
  ) -> Slot | None
  ```
  The three repositories arrive as parameters instead of `self._rules` / `self._exceptions` / `self._bookings`. Nothing else in the body changes: same `astimezone(UTC)`, same boutique-calendar `target_date`, same half-open day window, same `count_by_start` feed, same `materialize_slots` call, same `next(... if slot.starts_at == wanted)`.
- **The private method is DELETED, not kept as a delegate.** Its only three references in the repo are the definition (`service.py:362`), its one call site (`service.py:300`) and a docstring mention (`test_booking_service.py:1050`); the Gate-1 draft's "so F13's tests keep their entry point" was false.
- `service.py:300` becomes `slot = await offered_slot(session, tenant_id=tenant_id, starts_at=starts_at, now=now, rules=self._rules, exceptions=self._exceptions, bookings=self._bookings)`.
- Update the prose reference at `test_booking_service.py:1050` (`_offered_slot` → `offered_slot`) — a docstring, not an assertion.
- Why a new module rather than `slots.py`: `slots.py:1-15` is **pure by construction** ("no session, no ORM write, no `Settings`, no `datetime.now()`"). A coroutine taking an `AsyncSession` and three repositories would break that header on the file whose purity is the reason it is trustworthy. `slots_io.py` is the I/O-shaped sibling and its own header says so.
- **Neutrality proof (existing tests, unchanged):** `Backend/tests/test_booking_service.py` in full — the off-grid, past-instant, closed-day and full-slot 409 cases all reach the claim only through this call, and the concurrency proof at `:290-318` exercises it under `asyncio.gather`. `Backend/tests/test_booking_api.py` covers the route above it against a fake service.
- **Done when**: `make lint` clean (`ruff` + `mypy app tests`) and `make test` green. ⚠ `test_booking_service.py` is `pytestmark = pytest.mark.db` — **the real neutrality proof for this task runs on CI only**; locally, mypy resolving the new signature at the single call site is the whole check.
- Commit: `refactor(booking): module-level offered_slot, _offered_slot deleted`.

## Task 2 — `reschedule_reminder`'s body becomes module-level `upsert_reminder` (D11)
`Backend/app/booking/comms.py`

- New module-level coroutine, verbatim body from `comms.py:287-316` minus the `tenant_session` wrapper:
  ```python
  async def upsert_reminder(
      session: AsyncSession, *, tenant_id: uuid.UUID, booking_id: uuid.UUID,
      starts_at: datetime.datetime, now: datetime.datetime,
      bookings: BookingsRepository, scheduled: ScheduledMessagesRepository,
  ) -> datetime.datetime | None
  ```
  Same order, and the order is the subtlety: `reminder_send_after` first; `pending_for_booking`; **read `pending.manage_token` BEFORE `cancel_pending` clears it**; `cancel_pending`; `None` short-circuit on the <2h suppression band; mint + `set_manage_token_hash` only when nothing pending was there to inherit from; `insert` the fresh row carrying the token.
- `BookingComms.reschedule_reminder` becomes the one-line wrapper — the seam and its signature (`tenant: CommsTenant, *, booking_id, starts_at`) are unchanged, so F16's callers and tests keep their entry point:
  ```python
  async with tenant_session(self._session_factory, tenant.id) as session:
      return await upsert_reminder(session, tenant_id=tenant.id, booking_id=booking_id,
                                   starts_at=starts_at, now=self._clock(),
                                   bookings=self._bookings, scheduled=self._scheduled)
  ```
  One behavioural detail to preserve exactly: today `self._clock()` is read **before** the session opens and `send_after` is computed outside it. Moving the clock read inside the wrapper's call is the same instant for every purpose the tests measure, but keep `now=self._clock()` evaluated at the call, not inside `upsert_reminder`, so the injected frozen clocks in `test_booking_comms_db.py` still govern.
- **Neutrality proof (existing tests, unchanged):** `Backend/tests/test_booking_comms_db.py:962`, `:996`, `:1027` — the three `reschedule_reminder` cases (pending inherited, nothing pending so a fresh token rotates, suppression band returns `None`). Also `test_booking_comms_service.py`'s band tests, which exercise `reminder_send_after` directly and are unaffected.
- **Done when**: `make lint` clean, `make test` green. ⚠ `test_booking_comms_db.py` is `db`-marked — **CI only**, same caveat as Task 1.
- Commit: `refactor(booking): module-level upsert_reminder behind reschedule_reminder`.

## Task 3 — `SlotPicker` promoted into `packages/ui` with a `labels` prop (D14)
`Frontend/packages/ui/src/components/SlotPicker.tsx` (**new, moved**), `Frontend/packages/ui/src/index.ts`, `Frontend/apps/storefront/src/routes/BookPage.tsx`, `Frontend/apps/storefront/src/__tests__/BookPage.test.tsx`, delete `Frontend/apps/storefront/src/components/booking/SlotPicker.tsx`

- Move the file verbatim. The only edit is the i18n de-coupling: drop `import { useTranslation } from "react-i18next"` and `const { t } = useTranslation()`, add
  ```ts
  export interface SlotPickerLabels { pickDate: string; pickTime: string; noSlots: string; }
  ```
  as a **required** `labels` prop on `SlotPickerProps`, and replace the three call sites — `t("booking.pickDate")` → `labels.pickDate` (`:55`), `t("booking.pickTime")` → `labels.pickTime` (`:76`), `t("booking.noSlots")` → `labels.noSlots` (`:83`). Required, not optional-with-default: `packages/ui` holds **no** Hebrew (`Price.tsx:7`, `Gallery.tsx:12`, `BoutiqueHeader.tsx:7`) and a default would be the first.
- Everything else survives untouched, and this is the load-bearing part: `useId`-scoped radio `name`, the `<legend>` as the fieldset's **first element child**, the error `<p role="alert">` **outside** the fieldset, `sr-only` radios with the `<label>` as the target, `min-h-11` chips, three-channel selection (`:checked` + gold fill + `font-semibold`), the `<bdi dir="ltr">` label, `ref` forwarded to the first radio.
- `packages/ui/src/index.ts` gains `export { SlotPicker }` and `export type { SlotPickerProps, SlotPickerLabels, SlotTime }`.
- Two call sites gain the prop: `BookPage.tsx:27-28` (imports move to `@boutique/ui`) and `:947` (`labels={{ pickDate: t("booking.pickDate"), pickTime: t("booking.pickTime"), noSlots: t("booking.noSlots") }}`); `BookPage.test.tsx:14` and `:736` the same. **No storefront `he.ts`/`ar.ts` key changes** — the three keys stay exactly where they are and keep their values; only who reads them moves.
- **Neutrality proof (existing tests, unchanged):** `BookPage.test.tsx:733-758` is the fieldset/legend/radio-group contract, and the rest of the `BookPage` suite drives the picker end to end. Unlike Tasks 1 and 2, **this one runs locally** — vitest, no Docker.
- **Done when**: `pnpm -r lint && pnpm -r typecheck && pnpm -r test` green with **zero** assertion edits in `BookPage.test.tsx` beyond the import path and the new prop, `pnpm -r build` clean, and `grep -r "SlotPicker" Frontend/apps/storefront/src/components` returns nothing.
- Commit: `refactor(ui): promote SlotPicker into packages/ui with a labels prop`.

## Task 4 — The D12 contract corrections, as a real diff
`Backend/app/db/repositories/bookings.py`, `Backend/app/booking/comms.py`, `Backend/app/models/constants.py`, `Backend/tests/test_booking_comms_db.py`, `.planning/specs/booking-comms.md`

Docstrings and comments only — zero behaviour, zero assertion change. **Eight** edits, all of them statements that are now **false**:

| Where | Says today | Becomes |
|---|---|---|
| `bookings.py:38-43` (`insert`) | "F15's owner-side **create** and reschedule are the next callers" | "F15's owner-side reschedule is the next caller; owner-side create is out of F15 (Interview Q6) and belongs to the owner-created-bookings spec." |
| `bookings.py:129-131` (`set_manage_token_hash` docstring — the spec's `:132-135` is the statement, not the prose) | "F15's edit-phone remedy uses it **through `reissue_manage_token`**" | "F15's edit-phone remedy and its resend call this **directly**, inside their own transaction (D8)." |
| `comms.py:248-254` (`reissue_manage_token` docstring — the spec's `:250-253` is the middle of it) | "Rotate the hash and resend the confirmation — F15's edit-phone remedy." | "Kept as a tested seam with no caller: D8 requires the mint-rotate-repoint half to run inside F15's own transaction, so this belongs to the surface that can afford a second one." |
| `constants.py:54-58` (`BookingCancelledBy`) | "'owner' has no writer until F15 ships the console" | "F15's owner cancel is the `'owner'` writer." — **added by this plan**; D12 lists four items and this is the same class of stale forward reference, one file over from two of them. |
| `test_booking_comms_db.py:750` | "# Rotation (F15's edit-phone remedy) kills the old link." | "# Rotation kills the old link. F15's remedy rotates in its own transaction (D8); this proves the seam, not its caller." — **added by this plan**: the same false attribution as the two docstrings above, in the file that exercises them, and the Done-when grep below would otherwise leave it standing. A comment, not an assertion. |
| `.planning/specs/booking-comms.md:70` | "F15's **owner-create** … inherits the same contract" | same re-point at the owner-created-bookings spec. |
| `.planning/specs/booking-comms.md:185` | "retry/requeue of failed sends (evidence row + **F15 remedy** is the v1 answer)" | **added by this plan.** F15's spec rules explicitly that these two lines "are re-pointed at the provider-go-live feature and are **not** discharged by F15's merge" (§Out of scope, Risk 3(b)) — but the Gate-2 draft never edited them, so F15 would merge leaving two shipped spec lines naming it as the answer to a thing it deliberately does not ship. Becomes: "evidence row + the resend remedy F15 ships; the *signal* (a failed-send indicator) is the provider-go-live feature's." |
| `.planning/specs/booking-comms.md:193` (Risk 3, kosher phones) | "until **F15** ships the remedy surface … *Trigger: F15 build + provider go-live.*" | "F15 ships the remedy surface (resend) and not the signal; the only trace of a permanent failure remains a `failed` `message_log` row that nothing renders. *Trigger: provider go-live.*" |

- **Done when**: `make lint` clean, `make test` green, and both greps return nothing:
  - `grep -rn "owner-side create\|through .reissue_manage_token\|no writer until F15\|F15's edit-phone remedy" Backend`
  - `grep -rn "F15 remedy\|until F15 ships the remedy\|F15's owner-create" .planning/specs/booking-comms.md`
- Commit: `docs(booking): re-point F15's stale forward references (D12)`.

---

# Part II — the backend

## Task 5 — Constants, `Settings`, the three (+1) error classes and the four exception handlers
`Backend/app/models/constants.py`, `Backend/app/booking/validation.py`, `Backend/app/booking/owner.py` (**new**), `Backend/app/core/config.py`, `Backend/app/main.py`

**`AuditAction` gains seven members** (D2 — no migration; `audit_log.action` is plain TEXT with no CHECK, `0003_auth.py:71-79`), carrying the file's house comment:

`BOOKING_CONFIRMED = "booking_confirmed"` · `BOOKING_CANCELLED = "booking_cancelled"` · `BOOKING_NO_SHOW = "booking_no_show"` · `BOOKING_COMPLETED = "booking_completed"` · `BOOKING_RESCHEDULED = "booking_rescheduled"` · `BOOKING_PHONE_CORRECTED = "booking_phone_corrected"` · `BOOKING_LINK_RESENT = "booking_link_resent"`

**`booking/validation.py`** gains `BOOKING_LIST_DEFAULT_LIMIT = 50` and `BOOKING_LIST_MAX_LIMIT = 200`, each with the "why this number" comment the file uses for every other bound. Not env-tunable — the file header's rule.

**`booking/owner.py`** starts as constants + error classes only (the service arrives in Task 7):
- `MAX_LIST_OFFSET = 1_000_000` with the `catalog/service.py:73-81` reasoning restated: `offset` reaches asyncpg as `OFFSET $n::BIGINT` and a value past int8 dies in `int8_encode` as an unhandled `DataError`, i.e. a 500.
- `class BookingTransitionInvalidError(Exception)` — carries the refused pair in its message.
- `class CustomerAlreadyBookedError(Exception)` — reschedule target, **and** D8's re-point collision on 0009.
- `class OwnerResendThrottledError(Exception)` — its own class, per the `StorefrontThrottledError` / `OtpThrottledError` / `BookingThrottledError` precedent; the F21 reparenting note applies.
- `class NotAuthorizedError(Exception)` — C1's resolution.

**`Settings`** gains two fields beside the existing `booking_*` block (`config.py:82-98`):
`booking_owner_sms_max_per_tenant_window: int = 20` · `booking_owner_sms_window_seconds: int = 3600`

**`main.py` gains four `*_BODY` literals and four handlers — enumerated, because there is no error registry and an unmapped typed error is a 500 (`main.py:96`):**

| # | Exception | Status | Body |
|---|---|---|---|
| 1 | `BookingTransitionInvalidError` | 409 | new `BOOKING_TRANSITION_INVALID_BODY` — `{"code": "BOOKING_TRANSITION_INVALID", "message": "That change is not allowed for this booking's current state."}` |
| 2 | `CustomerAlreadyBookedError` | 409 | new `CUSTOMER_ALREADY_BOOKED_BODY` — `{"code": "CUSTOMER_ALREADY_BOOKED", "message": "This customer already has a booking at that time."}` |
| 3 | `OwnerResendThrottledError` | 429 | **existing** `TOO_MANY_ATTEMPTS_BODY` — no new code (D10) |
| 4 | `NotAuthorizedError` | 403 | new `NOT_AUTHORIZED_BODY` — `{"code": "NOT_AUTHORIZED", "message": "This action requires an owner account."}` (C1) |

**Deliberately NOT registered, because the base handler already answers them** — stated here so a reviewer can check the list is complete rather than short:
`SlotUnavailableError` → already bound at `main.py:511-513` (409) · `BookingNotFoundError`-shaped 404s → subclass `DomainNotFoundError`, bound to the **base** at `main.py:401-413` · `BookingValidationError` **and** `SlotWindowError` → both subclass `DomainValidationError`, bound to the base (400 `VALIDATION_ERROR`) · `NotAuthenticatedError` → app-wide 401 · CSRF → app-wide 403.

`FixedWindowRateLimiter` lives at **`app/auth/rate_limit.py`**, not `app/core/` — the spec's bare `rate_limit.py:20-26` / `:37-39` citations do not say so, and `main.py` already imports it from there.

- **Done when**: `make lint` clean and `make test` green. The handlers ship **registered and unexercised** in this task, deliberately: there is no route to raise them from until **Task 11**, and `SPEC_ERROR_CODES` there is their proof. No test is invented here to cover a route that does not exist.
- Commit: `feat(booking): owner audit actions, list bounds, owner-SMS budget and four error handlers`.

## Task 6 — The repository writers (TDD, `db`-marked)
`Backend/app/db/repositories/bookings.py`, `Backend/app/db/repositories/customers.py`, `Backend/tests/test_booking_repositories.py`

**Tests first**, appended to the existing `db`-marked module (`pytestmark = pytest.mark.db`, `:29`) using its engine/fixture idioms (`_factory`, `_phone`, `_insert_booking`, `tenant_session`).

**Correction to the Gate-2 draft: `test_booking_repositories.py:189-196` is NOT rewritten.** The draft said that block's hand-set `seat1.status = NO_SHOW` / `= CANCELLED` "is replaced with a `set_status` call, which is the first proof the writer works". Verified against the file, that is unbuildable and wrong on three counts:

- Its instants are `T0 = 2099-08-02` (`:35`) — **future**. `set_status(to='no_show', not_after=now)` carries `starts_at <= :not_after`, so it would match zero rows and return `None`. The test would red-fail on the writer working correctly.
- The second hand-set is `CANCELLED`, which `set_status` does not write at all (D3 keeps that on the shipped `cancel`, which also writes `cancelled_at`/`cancelled_by` — evidence this test neither wants nor asserts).
- The test is `test_occupancy_queries_ignore_cancelled_and_respect_window`; its subject is `active_seats_at` / `count_by_start`. Routing its fixture through a brand-new writer couples an unrelated shipped test to F15's clock guard for no assertion gained — and Part I's own rule is that a refactor adds no assertion.

The hand-set stays. **F15's writers are proven by new tests with their own past/future fixtures** (a `PAST_SLOT` constant beside `T0`/`T1`, since three of the four transitions are clock-guarded).

| Method | Signature | Tests written first |
|---|---|---|
| `BookingsRepository.set_status` | `(session, tenant_id, booking_id, *, to: str, allowed_from: tuple[str, ...], not_before: datetime \| None = None, not_after: datetime \| None = None) -> Booking \| None` | every legal pair writes and returns the row; a `from` outside `allowed_from` returns `None` and writes nothing; `not_after=now` refuses a future `starts_at`; `not_before=now` refuses a past one; a soft-deleted row returns `None`; the returned row is re-read through `by_id` (house shape) |
| `BookingsRepository.cancel` | **existing**, gains `not_before: datetime \| None = None` → adds `starts_at > :not_before` to the predicate **only when passed** | passing `not_before=now` refuses a past booking (returns the un-cancelled row); **omitting it reproduces today's behaviour byte for byte** — this is the assertion that F16's `ManageBookingService.cancel` and its `BookingAlreadyStartedError` contract are untouched, and the existing cancel tests are re-run unedited as the other half of that proof |
| `BookingsRepository.reschedule` | `(session, tenant_id, booking_id, *, starts_at, seat_index, not_before) -> Booking \| None` | writes both columns; predicate `status='confirmed' AND starts_at > :not_before AND deleted_at IS NULL`, `RETURNING id`; zero rows → `None`; a collision on `idx_bookings_slot_seat_unique` raises `IntegrityError` out of the flush (the service maps it) |
| `BookingsRepository.list_day` | `(session, tenant_id, *, from_instant, until_instant, offset, limit) -> tuple[list[Booking], int]` | half-open `[from, until)`; **cancelled rows ARE returned** (D17 — it does not inherit `count_by_start`'s `status != 'cancelled'` reflex); ordered `(starts_at, seat_index)`; `total` counts the whole day, not the page; `offset`/`limit` page correctly |
| `BookingsRepository.list_live_for_customer` | `(session, tenant_id, *, customer_id, after) -> list[Booking]` (**C2**) | returns only `confirmed` bookings with `starts_at > after`; excludes cancelled, no-show, completed, past and soft-deleted; ordered by `starts_at` |
| `CustomersRepository.set_phone` | `(session, tenant_id, customer_id, *, phone) -> Customer \| None` | one UPDATE, returns the row; a phone already held by another live customer of this tenant raises `IntegrityError` from `idx_customers_tenant_phone_unique` at flush (the service pre-checks and re-points instead — Task 11); unknown id → `None` |

Every predicate keeps `deleted_at IS NULL` and the redundant `tenant_id` (house defence-in-depth, `BookingsRepository`'s own class docstring).

- **Done when**: `make lint` clean, `make test` green (these are `db`-marked, so locally they are collected and skipped — **the proof runs on CI**), `make test-db` green on CI.
- Commit: `feat(booking): owner transition, reschedule, day-list and phone repository writers`.

## Task 7 — `OwnerBookingService` reads: day list, detail, owner slot grid (TDD)
`Backend/app/booking/owner.py`, `Backend/app/booking/schemas.py`, `Backend/tests/test_booking_owner_service.py` (**new, no DB**)

**Tests first**, against fake repositories — pure shaping, no Postgres, so this suite runs locally.

- `OwnerBookingService.__init__(session_factory, *, storefront: StorefrontService, comms: BookingCommsService, sms_limiter: FixedWindowRateLimiter, clock: Clock | None = None)` plus the repositories (`bookings`, `customers`, `scheduled`, `audit`, `rules`, `exceptions`). `storefront` is injected rather than re-implemented: `GET /manage/slots` is `StorefrontService.list_slots` plus an owner projection (D6), and a second materializer is what `slots.py:1-8` exists to forbid.
- `list_day(tenant_id, *, date: datetime.date, offset: int, limit: int) -> tuple[list[Booking], int]` — converts the **Jerusalem calendar date** into a `[midnight, next-midnight)` UTC instant pair exactly the way `storefront/service.py:198-206` does (`datetime.combine(..., tzinfo=BOUTIQUE_TIMEZONE).astimezone(UTC)`, half-open on the right), clamps `offset` at `MAX_LIST_OFFSET` **below the router**, and calls `list_day`.
- `detail(tenant_id, booking_id) -> Booking` — `by_id`, `None` → `BookingNotFoundError` (a `DomainNotFoundError` subclass, so 404 with no new handler).
- `list_slots(tenant_id, *, from_date, to_date) -> list[Slot]` — one call into `StorefrontService.list_slots`, full `Slot` objects. `SlotWindowError` propagates untouched (400 through the base handler).

**Schemas** in `app/booking/schemas.py` (responses are plain `BaseModel` declared as return-type annotations, never `response_model=`; requests subclass `ForbidExtraModel`):

- `OwnerBookingRow` — `id`, `starts_at`, `status`, `attendance_confirmed_at`, `customer_name`, `appointment_type_name`, `dress_name`
- `OwnerBookingListResponse` — `{items, total, offset, limit}`, the house envelope (`catalog/schemas.py:160-165`)
- `OwnerBookingDetail` — every list field **plus** `customer_phone`, `notes`, `dress_id`, `dress_size`, `seat_index`, `created_at`, `terms_version_accepted`, `terms_accepted_at`, `cancelled_at`, `cancelled_by`, `manage_link_issued: bool`
- `OwnerSlotRow { starts_at, capacity, remaining }` and `OwnerSlotListResponse { slots }`
- `RescheduleRequest(ForbidExtraModel) { starts_at: AwareDatetime }`, `PhoneCorrectionRequest(ForbidExtraModel) { phone: str }`

Tests assert, explicitly: **`manage_token_hash` is not a field on any response model** (`assert "manage_token_hash" not in OwnerBookingDetail.model_fields`) — it is the stored half of a live credential; `manage_link_issued` is `manage_token_hash is not None`; `customer_phone` and `notes` are on the **detail only**, never on the row (D18); a Jerusalem date crossing a DST boundary still produces a 24-or-23-hour half-open window; `offset` beyond `MAX_LIST_OFFSET` is clamped, not passed through.

**`ManageBookingFacts` is not copied.** It is deliberately PII-free because it answers an anonymous token (`booking/schemas.py:63-73`); this surface answers an authenticated owner and the reasoning inverts (D18). A comment on `OwnerBookingDetail` says so, so nobody reaches for the wrong precedent.

- **Done when**: `make lint` + `make test` green, both locally and on CI.
- Commit: `feat(booking): OwnerBookingService reads — day list, detail and the owner slot grid`.

## Task 8 — The D3 transition graph and the owner cancel (TDD)
`Backend/app/booking/owner.py`, `Backend/tests/test_booking_owner_service.py`

**Tests first** — the graph as a table, driven against fake repositories.

The house shape, written out as code: **read → compare → return-or-raise → guarded write → audit**.

1. Load inside the transaction (`tenant_session`, `db/tenant.py:25-30`). Missing → `BookingNotFoundError` (404).
2. `booking.status == target` → **return the booking unchanged, 200, no audit row.** A no-op is not a transition (`manage.py:158-161`'s shape).
3. Illegal pair or illegal clock → `BookingTransitionInvalidError` (409), nothing written.
4. The guarded write, carrying the same predicate as belt. **Zero rows → `BookingTransitionInvalidError` and the transaction rolls back before the audit row** — another request moved the row between 1 and 4.
5. `AuditLogRepository.record(session, tenant_id=…, action=…, actor_id=staff.id, entity=str(booking.id), details={"from": …, "to": …})`, same transaction, before commit.

| Method | Repository call | Audit action |
|---|---|---|
| `no_show` | `set_status(to='no_show', allowed_from=('confirmed','completed'), not_after=now)` | `BOOKING_NO_SHOW` |
| `complete` | `set_status(to='completed', allowed_from=('confirmed','no_show'), not_after=now)` | `BOOKING_COMPLETED` |
| `confirm` | `set_status(to='confirmed', allowed_from=('no_show','completed'))` — **no clock bound**, and it writes `status` **only**, never `attendance_confirmed_at` (that is F16's reminder-link column and means something different) | `BOOKING_CONFIRMED` |
| `cancel` | the **shipped** `cancel(at=now, by=BookingCancelledBy.OWNER.value, not_before=now)` + `scheduled.cancel_pending(booking_id, REMINDER)` | `BOOKING_CANCELLED` |

**Owner cancel cancels its own pending reminder.** `notify_owner_cancel` does not touch `scheduled_messages` (`comms.py:187-204`), so without this the customer gets a cancellation SMS and then a reminder for the cancelled appointment. `ManageBookingService.cancel` already does exactly this for the customer path (`manage.py:172-177`).

Test table, every row asserted:

| From → To | Expected |
|---|---|
| `confirmed` → `cancelled`, future | 200, `cancelled_by='owner'`, `cancelled_at` set, pending reminder flipped, one audit row |
| `confirmed` → `cancelled`, **past** | 409 `BOOKING_TRANSITION_INVALID`, nothing written |
| `confirmed` → `no_show` / `completed`, **past** | 200, one audit row each |
| `confirmed` → `no_show` / `completed`, **future** | 409 |
| `no_show` ↔ `completed` | 200 both directions |
| `no_show` / `completed` → `confirmed` | 200 (the undo of a mis-tap), `attendance_confirmed_at` **unchanged** |
| `no_show` / `completed` → `cancelled` | 409 |
| `cancelled` → anything | 409 (terminal) |
| any → same status | **200, unchanged, zero audit rows** |
| `set_status` returns `None` mid-flight | 409 **and** rollback — `audit.record` was never called |

Also asserted: no-show / complete / confirm write **nothing to `scheduled_messages`** and send **nothing** (D13 — they are guarded on `starts_at <= now`, so the reminder has already fired or the worker's claim-time re-check flips it); cancel is **not** metered by the owner-SMS limiter (D10 — `cancelled` is terminal, so it is bounded at one SMS per booking).

- **Done when**: `make lint` + `make test` green.
- Commit: `feat(booking): the D3 transition graph and the owner cancel`.

## Task 9 — The D5 reschedule protocol (TDD)
`Backend/app/booking/owner.py`, `Backend/tests/test_booking_owner_service.py`

**Tests first.** One `tenant_session`, and the step order **is** the correctness argument — a test that passes with the steps reordered is not testing this.

0. **Horizon guard before any arithmetic**: `if not now < new_starts_at <= now + BOOKABLE_HORIZON: raise SlotUnavailableError`. Copied verbatim from `service.py:180-186` for its reason — `AwareDatetime` accepts the whole datetime range and `.astimezone()` on a year-9999 instant raises `OverflowError`, an unhandled 500. Comparison itself cannot overflow, so the guard is total.
1. **`SELECT pg_advisory_xact_lock(hashtext(:tenant_id))` — before any read of the booking.** The obligation `bookings.py:38-43` records by name and `create_booking` honours at `service.py:261-264`.
2. **Post-lock** `by_id`: missing → 404; `status != 'confirmed'` → 409 `BOOKING_TRANSITION_INVALID`; `starts_at <= now` → 409 `BOOKING_TRANSITION_INVALID`. **Every value used below — the status, the short-circuit comparison, `old_starts_at`, `old_seat_index` — comes from this read.**
3. `new_starts_at == booking.starts_at` → return unchanged: no audit row, no SMS, no reminder write. Not a nicety — `active_at` and `active_seats_at` have no booking-id exclusion (`bookings.py:74-106`), so a no-op move would find **itself**.
4. `offered_slot(...)` → `None` ⇒ 409 `SLOT_UNAVAILABLE`. This one call buys past-instant drop, off-grid rejection, closed and exception days, the DST rules (`slots.py:81-104`) and capacity (full slots are dropped, `slots.py:150-152`).
5. `active_at(customer_id=booking.customer_id, starts_at=new)` → hit ⇒ 409 `CUSTOMER_ALREADY_BOOKED`. Step 3 already excluded the row itself, so a hit here is always another booking.
6. `seats = active_seats_at(new)`; `next((i for i in range(1, slot.capacity + 1) if i not in seats), None)`; `None` ⇒ 409 `SLOT_UNAVAILABLE`. **Never carry the old `seat_index`** — nothing in the database bounds a seat by its slot's capacity (`0008:65` is `1..1000`), so seat 3 into a capacity-1 target is a silent oversell that satisfies both the CHECK and the unique index.
7. `bookings.reschedule(..., not_before=now)`. Zero rows ⇒ `BookingTransitionInvalidError` + rollback (the four status endpoints take no lock, so a concurrent owner cancel can land between 2 and 7). `IntegrityError` ⇒ `SlotUnavailableError`, the same backstop mapping `create_booking` uses (`service.py:342-345`).
8. `upsert_reminder(session, ...)` — **in this transaction** (Task 2's promotion is what makes that possible), then the audit row `BOOKING_RESCHEDULED` with `{"old_starts_at", "new_starts_at", "old_seat_index", "new_seat_index"}`, then commit. A `None` from `upsert_reminder` is **not an error** — the moved appointment is inside the <2h band and legitimately gets no reminder.

The limiter is consulted **before the transaction opens** (D10): `sms_limiter.is_blocked(f"booking:owner_sms:{tenant_id}")` → `OwnerResendThrottledError`. `record_failure` fires on the **success** path only, because `FixedWindowRateLimiter` counts nothing the caller does not record (`app/auth/rate_limit.py:20-26`) — and per **C4** it fires **in the service, immediately after the transaction commits**, not "after the post-commit send returns": the send is the router's (D11), and reaching back into it would put limiter plumbing in three handlers to move one line. A no-op short-circuit at step 3 spends nothing — no mutation, no SMS.

Unit tests here (fakes, no DB): the horizon guard rejects year-9999 without an `OverflowError`; the lock statement is issued **before** `by_id` (assert on the fake session's recorded statement order — this is the assertion that fails if the read moves back above the lock); each of the four 409 causes is distinguishable; the no-op short-circuit writes nothing anywhere; the old seat is never carried; a zero-row `reschedule` rolls back with no audit row; a `None` from `upsert_reminder` still commits and still audits.

- **Done when**: `make lint` + `make test` green. The concurrency behaviour is Task 13's `db` suite — **CI only**.
- Commit: `feat(booking): the D5 reschedule protocol`.

## Task 10 — Phone correction and resend: the rotation, inside the write (TDD)
`Backend/app/booking/owner.py`, `Backend/tests/test_booking_owner_service.py`

**Tests first.** This is the feature's dangerous surface (Risk 2) and the one place the test list is longer than the code.

**Shared preconditions for both operations** (D8 mechanic 4, D10):
- limiter checked **before the transaction opens** — a 429 writes nothing and sends nothing — and `record_failure`d in the service immediately **after commit** (**C4**), never from the router;
- both return a result carrying the **raw token minted for the edited booking**, because the router's post-commit `send_confirmation` needs it and `bookings` stores only the sha256 — there is no second chance to read it;
- the booking must be `confirmed` **and** `starts_at > now`, evaluated in Python **and** carried as the predicate on every rotation UPDATE, so it cannot go stale mid-operation → otherwise 409 `BOOKING_TRANSITION_INVALID`.

### `correct_phone(tenant_id, booking_id, *, phone, staff)`

1. `normalize_israeli_mobile(phone)` — the same function the claim uses (`booking/service.py:49`). Malformed → 400 `VALIDATION_ERROR`, before anything is written. **No client-side copy of this exists and none is added** (D20).
2. Open the transaction. Load and guard.
3. `customers.by_phone(normalized)`:
   - **No collision →** `customers.set_phone(customer_id, phone=normalized)`, then rotate **every live booking of that customer**: `bookings.list_live_for_customer(customer_id=…, after=now)` (C2) → for each, `mint_manage_token()` + `set_manage_token_hash` under the guard predicate + re-point that booking's pending reminder's `manage_token` via `scheduled.pending_for_booking`. **A `None` from any rotation raises and rolls the whole transaction back** — never a discarded result.
   - **Collision →** the target customer already exists. **Pre-check 0009 first**: `active_at(customer_id=<target>, starts_at=booking.starts_at)` → hit ⇒ `CustomerAlreadyBookedError` (409, never a 500). Then re-point `bookings.customer_id` at the existing customer and rotate **this booking only** — on this branch the digits were never wrong, the *identity* was, and the original customer may be a real other person whose other bookings are genuinely hers. `customers.phone` is **not** touched; both customer rows survive. The flush's `IntegrityError` maps to `CustomerAlreadyBookedError` as the backstop.
4. Audit `BOOKING_PHONE_CORRECTED` with `{"old_phone_last4", "new_phone_last4", "attested": true, "old_customer_id", "new_customer_id", "repointed": bool, "rotated_booking_ids": [...]}`. **Full numbers are deliberately absent** — `audit_log` is retained on the audit clock and a full number in JSONB is a second uncontrolled copy of the one PII field this feature edits. The customer ids are what let an Amendment-13 complaint be answered at all.
5. Commit. Post-commit, in the router: `send_confirmation(tenant, booking=…, manage_token=<the token minted for THIS booking>)`. **Only this booking's SMS** — rotating a sibling's token silently is the safety half and must be unconditional; texting N confirmations for N bookings is spend and noise (Risk 9).

**`reissue_manage_token` is NOT called** (D8, D12). It bundles mint + rotate + re-point + send across its **own** `tenant_session` (`comms.py:255`), returns `None` on any miss, and discards `set_manage_token_hash`'s `None` — so the mint-rotate-repoint half cannot be inside our transaction if we call it. F15 calls the public `send_confirmation` post-commit with the token it already minted, which is the same message.

### `resend_link(tenant_id, booking_id, *, staff)`

Same mechanic, no phone edit (D9): limiter → transaction → guard → mint → `set_manage_token_hash` under the guard predicate → re-point the pending reminder → audit `BOOKING_LINK_RESENT` with `{"customer_id": …}` → commit → `send_confirmation` post-commit. **Resend is a rotation, not a re-send** — the old link dies, and the Hebrew says so (`booking.resendHint`).

**No compare-and-swap on the rotation** (D9, the one rejected review finding). Two rotations seconds apart produce one live link and one dead one, which is the specified behaviour; the row lock on `bookings` orders the writes so the surviving hash is always a real one. The mitigation is the client disabling the button while its request is in flight (Task 16).

Unit tests here (fakes, no DB): a malformed phone 400s before any write; a throttled call leaves `customers.phone` **and** `manage_token_hash` unchanged and sends nothing; the guard refuses a cancelled / past / no-show booking on both operations; the no-collision branch rotates **every** live booking and names all of them in `rotated_booking_ids`; the collision branch rotates **exactly one** and leaves the original customer's other bookings untouched; the 0009 pre-check raises `CustomerAlreadyBookedError` rather than letting the flush 500; a `None` from any `set_manage_token_hash` aborts the whole thing; the audit `details` contains **last4 only** and never a full number; `send_confirmation` is called with the token minted for the edited booking and **not once per sibling**.

- **Done when**: `make lint` + `make test` green.
- Commit: `feat(booking): owner-attested phone correction and link rotation`.

## Task 11 — `owner_router.py`, the role guard, `main.py` wiring, and the fast API suite (TDD)
`Backend/app/booking/owner_router.py` (**new**), `Backend/app/booking/owner.py`, `Backend/app/main.py`, `Backend/tests/test_booking_owner_api.py` (**new**)

**Tests first**, on the `test_catalog_api.py` template: a duck-typed `FakeOwnerBookingService` assigned to **`app.state.owner_booking_service`** (not `app.dependency_overrides` on the `Annotated` alias — the catalog module keys overrides on the dependency *function*, and the booking router's `get_*_service(request)` reads `app.state` directly).

**The router**: `APIRouter(prefix="/manage", dependencies=[Depends(_no_store), Depends(require_owner)])`.

- `_no_store` is **router-level**, for the reason `booking/router.py:59-64` and `catalog/router.py:44-56` both state: every response here names a real person's appointment, phone and free-text notes, and setting the header centrally is what makes the invariant structural. The boutique router has no such dependency; F15 does not retrofit it.
- `require_owner(staff: Staff) -> StaffContext` raises `NotAuthorizedError` unless `staff.role == StaffRole.OWNER`. **A no-op today** — `StaffRole` has one member (`constants.py:9-11`) — and that is the argument for it: on the day E6 adds `ASSISTANT`, a data change with no code change and no failing test would otherwise hand that assistant the bride's phone and notes, the ability to cancel any booking, and the ability to re-point a live SMS control link at any number with no OTP.
- `Staff = Annotated[StaffContext, Depends(get_current_staff)]` and `Owner = Annotated[OwnerBookingService, Depends(get_owner_booking_service)]`, the `boutique/router.py:30` / `booking/router.py:54-57` alias pattern. Every route takes `staff`, even where the handler only needs `staff.id` for the audit row.

**The ten routes**, all answering the shapes from Task 7:

| # | Method | Path | Input | Answers |
|---|---|---|---|---|
| 1 | `GET` | `/manage/bookings` | `date: datetime.date` (**required**), `offset: int = 0`, `limit: int = Query(BOOKING_LIST_DEFAULT_LIMIT, ge=1, le=BOOKING_LIST_MAX_LIMIT)` | `OwnerBookingListResponse` |
| 2 | `GET` | `/manage/bookings/{booking_id}` | — | `OwnerBookingDetail` |
| 3 | `POST` | `/manage/bookings/{booking_id}/confirm` | — | `OwnerBookingDetail` |
| 4 | `POST` | `/manage/bookings/{booking_id}/cancel` | — | `OwnerBookingDetail` |
| 5 | `POST` | `/manage/bookings/{booking_id}/no-show` | — | `OwnerBookingDetail` |
| 6 | `POST` | `/manage/bookings/{booking_id}/complete` | — | `OwnerBookingDetail` |
| 7 | `POST` | `/manage/bookings/{booking_id}/reschedule` | `RescheduleRequest` | `OwnerBookingDetail` |
| 8 | `POST` | `/manage/bookings/{booking_id}/phone` | `PhoneCorrectionRequest` | `OwnerBookingDetail` |
| 9 | `POST` | `/manage/bookings/{booking_id}/resend-link` | — | `OwnerBookingDetail` |
| 10 | `GET` | `/manage/slots` | `from_date`/`to_date` as `from`/`to` query aliases | `OwnerSlotListResponse` |

Path parameters and REST verbs are the shipped `/manage` convention (`boutique/router.py:92, 114, 171`; `catalog/router.py:181, 203, 212, 223`). The `.claude/rules` RPC / `@QueryValue` guidance is Kotlin boilerplate and does not apply here. Four verb sub-paths rather than one `PATCH` with a `status` field (D7): cancel is guarded on a *future* `starts_at`, sends an SMS and cancels a reminder; no-show and complete are guarded on a *past* one and send nothing; confirm is the undo.

**Post-commit sends, in the router, awaited and discarded** — the `booking/router.py:18-23, 95-107` pattern, for its stated reasons (post-commit because `NotificationService.send_sms` opens its own sessions; awaited so the send happens inside the request's lifetime; fire-and-forget because turning a committed mutation into a 503 is a lie). The service returns a result carrying whether the mutation actually happened; the router branches on it and builds `CommsTenant.from_settings(tenant_id=tenant.id, slug=tenant.slug, name=tenant.name, settings=tenant.settings)` from `get_current_tenant(request)`. **No `BackgroundTasks`, no `asyncio.create_task`.**

| Route | After commit |
|---|---|
| cancel | `notify_owner_cancel(t, booking=updated)` |
| no-show / complete / confirm | **nothing** (D13) |
| reschedule | `notify_owner_reschedule(t, booking=refreshed)` |
| phone / resend-link | `send_confirmation(t, booking=…, manage_token=<minted>)` |

**`main.py` wiring:**
- `app.state.owner_booking_service = OwnerBookingService(get_session_factory(), storefront=app.state.storefront_service, comms=app.state.booking_comms_service, sms_limiter=FixedWindowRateLimiter(max_attempts=settings.booking_owner_sms_max_per_tenant_window, window_seconds=settings.booking_owner_sms_window_seconds, clock=time.monotonic), ...)` — **its own limiter instance, never a second key on an existing one**, with the house comment restated (`max_attempts` lives on the limiter, so a shared budget could never trip first; the rule is stated three times already at `main.py:346-353`, `booking/manage.py:89-92`, `rate_limit.py:37-39`). Constructed **after** `booking_comms_service` and `storefront_service`.
- `app.include_router(owner_booking_router)` **after** `catalog_router`, carrying the shadowing comment `main.py:552-556` already models — four routers now mount `/manage`, and a duplicated `(method, path)` would silently shadow.

**The test module**, the `test_catalog_api.py:103-115, 417-435, 707-727` template:
- `ROUTES: list[tuple[str, str, dict | None]]` — all ten — driving `test_every_route_requires_authentication` (401 `NOT_AUTHENTICATED`, and the fake records **zero** calls: the guard fires first), `test_every_route_is_wired_and_reaches_the_service` (200 + the service was reached — this is what catches a `/manage` shadow), and the `cache-control: no-store` parametrization.
  ⚠ **`LIST_PATH` must carry the query string**: `date` is a required `datetime.date` query param, so `"/manage/bookings"` alone answers **400 `VALIDATION_ERROR`** (`main.py`'s `RequestValidationError` handler, not a 422) and `test_every_route_is_wired_and_reaches_the_service`'s `assert resp.status_code == 200` red-fails on a correctly-built route. Spell it `LIST_PATH = "/manage/bookings?date=2026-08-02"`, the `test_catalog_api.py:95-97` f-string-constant shape. `/manage/slots`'s `from`/`to` are optional (`slot_window(None, None, today)` defaults the window) and need none.
- `SPEC_ERROR_CODES` pinned against D19's amended table: `{"VALIDATION_ERROR", "NOT_FOUND", "BOOKING_TRANSITION_INVALID", "SLOT_UNAVAILABLE", "CUSTOMER_ALREADY_BOOKED", "TOO_MANY_ATTEMPTS", "NOT_AUTHORIZED", "NOT_AUTHENTICATED", "CSRF_ORIGIN_MISMATCH"}` with `test_every_spec_error_code_is_asserted` doing the set equality (last two added unconditionally, per the template). **This is the proof for Task 5's four handlers.**
  ⚠ The template computes `covered = {case.code for case in ERROR_CASES}` (`test_catalog_api.py:946-952`) — **not** from every assertion in the module. So the seven non-unconditional codes each need an **`ERROR_CASES` row**, including `NOT_AUTHORIZED`: the role-guard test below is a separate function and would not feed the set. Rows: `VALIDATION_ERROR` (a `to < from` on `/manage/slots`, and a malformed phone on `/phone` — the spec's fast-suite "phone normalization" line), `NOT_FOUND`, `BOOKING_TRANSITION_INVALID`, `SLOT_UNAVAILABLE`, `CUSTOMER_ALREADY_BOOKED`, `TOO_MANY_ATTEMPTS`, `NOT_AUTHORIZED`.
- **A non-`OWNER` `StaffRole` is refused on every route** — a fake `StaffContext` carrying a synthetic role; 403 `NOT_AUTHORIZED`, and the fake records zero calls. `StaffContext.role` is a plain `str` (`auth/service.py:19-25`), so the fake needs no enum widening and `require_owner`'s `staff.role != StaffRole.OWNER` compares correctly against a `StrEnum`. Vacuous today, deliberate on the day E6 adds a second member.
- List clamping (`?offset=2**63` does not 500; `?limit=201` is a 400 from `Query(le=…)`), `?date=` parsing (missing → 400, malformed → 400), a `to < from` on `/manage/slots` → 400 `VALIDATION_ERROR` via `SlotWindowError`, an unknown body key → 400 via `ForbidExtraModel`.
- The transition graph as a table over the HTTP surface: every legal pair 200, every illegal pair 409, both `starts_at` boundaries, **a legal repeat answering 200 with no audit row**, and **a reschedule of a past `confirmed` booking answering 409**.
- `test_no_route_is_registered_twice_across_routers` (`test_storefront_api.py:564-573`) stays green untouched — F15 adds no `/storefront` path, so that test's explicit storefront literal is not edited.

- **Done when**: `make lint` + `make test` green, both locally and on CI. This is the first task where the whole route table is exercised without Docker.
- Commit: `feat(booking): /manage/bookings router, owner-role guard and app wiring`.

## Task 12 — The `db`-marked suite (written here, executed on CI)
`Backend/tests/test_booking_owner_db.py` (**new**), `Backend/tests/test_booking_isolation.py`

NullPool engines in `try/finally`, the `app_role_url` fixture (never the superuser), frozen module-constant clocks injected as `clock=lambda: NOW` — the `test_booking_service.py:51-93` idioms.

- **The headline: reschedule concurrency.** Capacity 1 at instant B; `asyncio.gather` of a public `create_booking` and an owner reschedule onto it; exactly one winner, one `SlotUnavailableError`, never two rows on one seat (the `test_booking_service.py:290-318` template).
- **Two concurrent reschedules of the same booking onto the same free target**: one wins; the other is a no-op 200 or a clean 409, **never a self-collision**, and the audit rows chain `T0→T1` then `T1→T2`, never `T0→T2` twice. **This is the test that fails if the `by_id` read moves back above the advisory lock.**
- Reschedule picks the **lowest free seat at the target**, not the old one: a seat-3 booking into a target whose seat 1 is free lands at 1; into a full target it is 409.
- Reschedule to an off-grid time, a past time, a closed day and a full slot each 409 through `offered_slot`.
- Reschedule to the same instant: unchanged row, no audit row, no SMS, no self-collision.
- Reschedule where the customer already holds another live booking at the target → `CUSTOMER_ALREADY_BOOKED`, **distinguishable** from `SLOT_UNAVAILABLE`.
- **The ordering proof.** A day-of reschedule with the prior reminder already drained (`_make_due` + `drain_due`, `test_booking_comms_db.py:493-502, 951-1041`): after `upsert_reminder` in the transaction, then `notify_owner_reschedule` post-commit, the token in the `OWNER_RESCHEDULE` body still resolves through `ManageBookingService.lookup`. **Reversing the two fails this test — that is the point of it.**
- **The worker race** (Risk 10): `_make_due` + `drain_due` interleaved between the reschedule commit and `notify_owner_reschedule`; assert the **outcome** (the bride's newest message carries a link that resolves), not the absence of the race.
- Owner cancel: seat freed (a rebook at the same instant succeeds), pending reminder flipped to `cancelled`, `cancelled_by='owner'`, one audit row, an `OWNER_CANCEL` body in the `FakeSmsSender` outbox.
- Each transition writes exactly **one** `audit_log` row with `actor_id=staff.id`, `entity=str(booking.id)` and the from/to in `details`; a refused transition writes **none**.
- Phone correction, both paths: no-collision updates the customer row and rotates the token (the old link 404s through `lookup`, the new one resolves — the `test_booking_comms_db.py:736-767` pattern); collision re-points `bookings.customer_id` and leaves **both** customer rows intact.
- **Sibling revocation**: one customer, **two** live future bookings against the wrong number; correct from one; the *other* booking's old token no longer resolves through `lookup`, its pending reminder carries the new token, and `rotated_booking_ids` names both. The re-point branch's counterpart: the original customer's other live bookings are asserted **unchanged**.
- **Atomicity**: a phone correction that fails after the phone write (injected failure in the rotation) leaves the customer row unchanged — there is no committed state in which the phone is corrected and the old hash survives.
- **The 0009 collision on re-point**: two sisters live at the same instant; correcting one onto the other's number answers 409 `CUSTOMER_ALREADY_BOOKED`, **never a 500**.
- Budget: the 21st resend in the window is `TOO_MANY_ATTEMPTS` and sends nothing; **a throttled phone correction leaves both `customers.phone` and `manage_token_hash` unchanged**; the Nth reschedule in the window is 429 and sends nothing; **cancel is never metered**.
- The day list returns cancelled rows and orders by `(starts_at, seat_index)`.
- **RLS isolation**: tenant B's owner can neither read nor transition tenant A's booking — 404, indistinguishable from missing. Added to the permanent isolation suite.

- **Done when**: `make test-db` green **on CI**. Locally these collect and skip; `make lint` (mypy over `tests`) is the only local signal.
- Commit: `test(booking): db-marked owner concurrency, rotation and isolation coverage`.

---

# Part III — the frontend

## Task 13 — i18n (`he` + the first console `ar`), the API client, and the sixth nav item
`Frontend/apps/manage/src/i18n/he.ts`, `…/i18n/ar.ts` (**new**), `…/i18n/index.ts`, `…/api.ts`, `…/App.tsx`, `…/lib/jerusalem.ts` (**new**), `…/__tests__/api.test.ts`, `Frontend/apps/manage/package.json`

**Tests first** in `api.test.ts`, the shipped fetch-mock pattern.

- **`he.ts`**: `nav.bookings` + the new `booking.*` namespace — **every row in `copy.md`, verbatim**, including the four `booking.error.<CODE>` rows (design P-5 / F-2). (The deck's header says "77 rows"; the tables carry **76**. Transcribe the tables, not the count — and do not add a filler key to reach 77.) Mechanical checks that ride along: zero exclamation marks in the added block; no string containing «נשלח»/«תישלח»/«בדרך» (the Risk 3(a) discharge, `copy.md` §0 rule 2).
- **`package.json`: the `test` script becomes `TZ=America/New_York vitest run`.** One word, and without it the Jerusalem assertions below are theatre: `apps/storefront` and `packages/ui` both pin a deliberately-wrong TZ for exactly this reason, and `apps/manage` is the only workspace that does not. On a UTC runner an unzoned `new Date().toLocaleDateString()` agrees with `todayJerusalem()` for 21 hours out of 24, so "a Jerusalem-date default that does not depend on the runner's TZ" cannot fail on CI as things stand. This is the *mechanical* half of the rule Task 17's grep only warns about.
- **`ar.ts`** — the console's first. F15's keys **only**, every value the approved Hebrew as a placeholder, **never `""`** (i18next's `returnEmptyString` default renders `""` rather than falling back, so a premature switch would blank the page instead of showing Hebrew). Header restates the storefront file's rationale (`apps/storefront/src/i18n/ar.ts:1-22`).
- **`i18n/index.ts`**: `resources: { he: {...}, ar: { translation: ar.translation } }`. `lng` stays `"he"`, `fallbackLng` stays `"he"`, **no switcher**. ⚠ **Nothing keeps `ar.ts` in sync with `he.ts`** — no he/ar parity guard exists in this repo and F15 does not invent one (Risk 5, design F-5). Stated in both file headers.
- **F15 does not retrofit** the four hardcoded-Hebrew sections (`HoursSection`, `TypesSection`, `TermsSection`, `CatalogSection`) or their three sub-components (`DressEditor`, `MediaGallery`, `VariantMatrix`), and **does not port** the storefront's `i18n-keys.test.ts` (its anti-vacuous floor of `USED_KEYS.length > 40` fails on a console carrying ~30 dotted keys today).
- **`lib/jerusalem.ts`**, ~20 lines, ported from `BookPage.tsx:82-109`: two `Intl.DateTimeFormat` instances (`en-CA` date parts, `en-GB` 24h time parts), `partsOf`, `jerusalemDate(instant)`, `jerusalemTime(instant)`, plus `todayJerusalem()` for the day filter's default. **Every formatter passes `timeZone: JERusalem`, imported from `@boutique/ui`** (`packages/ui/src/lib/hours.ts:7`) and never re-declared. The day filter's "today" is a Jerusalem calendar date — **never** `new Date().toLocaleDateString()`. Also ported: the rule that date bounds come from instants the server returned, never from the browser. `TermsSection.tsx:8-12` and `HoursSection.tsx:14-18` currently omit `timeZone`; **F15 does not fix them and does not join them.**
- **`api.ts`**: snake_case wire interfaces mirroring the Python schemas verbatim (`OwnerBookingRow`, `OwnerBookingListResponse`, `OwnerBookingDetail`, `OwnerSlotRow`, `OwnerSlotListResponse`) + **ten** `apiFetch` wrappers on the exported `api` object: `listBookings({date, offset, limit})`, `getBooking(id)`, `confirmBooking(id)`, `cancelBooking(id)`, `noShowBooking(id)`, `completeBooking(id)`, `rescheduleBooking(id, startsAt)`, `correctBookingPhone(id, phone)`, `resendBookingLink(id)`, `listManageSlots(from, to)`. No case conversion — this app speaks the backend's snake_case verbatim.
- **`App.tsx`**: four lines — `SectionKey` gains `"bookings"` (`:13`), `nav` gains `{ key: "bookings", label: t("nav.bookings") }` as the **sixth** item (`:50-56`), one render branch (`:70-74`).
- **No `vite.config.ts` change**: every endpoint is under `/manage`, which the proxy already forwards (`vite.config.ts:9-19`).
- **No client-side phone validator** (D20). `validation.ts` is **not touched**. A third hand-written copy of `normalize_israeli_mobile` is a normalizer, not a bound, and the constants paragraph's "no bound to drift" rationale does not cover it — it could refuse a legal Israeli number, or show her an E.164 different from the one actually stored on the row whose SMS link is about to rotate. The server's 400 is the only authority. `test_frontend_constant_parity.py`'s `MIRRORS` and `_MIRRORED_PATTERNS` gain **no row**.
- **Done when**: `pnpm -r lint && pnpm -r typecheck && pnpm -r test` green, `pnpm -r build` clean, and the console renders a sixth nav item that swaps to an empty panel.
- Commit: `feat(manage): bookings API client, Hebrew copy and the first console ar bundle`.

## Task 14 — `BookingsSection` — the day list
`Frontend/apps/manage/src/components/BookingsSection.tsx` (**new**), `…/__tests__/BookingsSection.test.tsx` (**new**), `Frontend/apps/manage/package.json`

**Tests first**, the `CatalogSection.test.tsx` pattern: `vi.mock("../api")` with `importActual` for `ApiError` / `errorMessage`, fixture builders, `vi.mocked`.

⚠ **The axe pass needs a dependency this repo does not have, and the Gate-2 draft did not name it.** Verified: the only axe package anywhere is `@axe-core/playwright` at the repo root, used by `Frontend/e2e/a11y.spec.ts`; neither `apps/manage` nor `apps/storefront` depends on `axe-core`, `jest-axe` or `vitest-axe`, and **no vitest test in the repo runs axe today** (the storefront's three "axe" hits are prose in comments). Since IS 5568 / WCAG 2.0 AA is a legal requirement here (pre-decided #38) and the plan promises zero-violation axe passes on both new console screens, the smallest honest resolution is: add **`axe-core`** to `apps/manage`'s `devDependencies` and call it directly —

```ts
import { run } from "axe-core";
const results = await run(container);
expect(results.violations).toEqual([]);
```

— rather than `jest-axe`, which is a matcher wrapper plus `@types/jest-axe` for one assertion. Declined: dropping the axe passes (the statutory floor is the one thing this plan may not simplify away) and moving them to Playwright (the console's e2e cannot log in — see "No E2E is promised"). Recorded here rather than in Task 13 because this is the task that first needs it.

Structure (design §1): `<h2 className="text-lg font-semibold text-ink">` → `Card` holding a `DateField` (visible label «תאריך», `dir="ltr"`, `className="max-w-[200px]"`, default `todayJerusalem()`) → the `role="status" tabIndex={-1}` count line → `Card` holding `<ul className="divide-y divide-border">` of full-row `<button>`s.

- Row: `flex w-full items-start gap-3 py-4 text-start`; leading time cell `w-14 shrink-0 font-semibold` inside `<bdi dir="ltr">`; customer name a **bare `<bdi>`**, `font-semibold`; **exactly one `Badge`** per row and it is the status; `attendance_confirmed_at` renders as the muted words «אישרה הגעה» on the meta line, **not** a second Badge; dress name a bare `<bdi>`.
- **One affordance per row** — the whole row is the button (`CatalogSection.tsx:209`). `py-4` + `text-base` clears 44px with no `min-h` literal.
- **Cancelled rows are in the list** and are not demoted beyond their `muted` Badge (D17).
- Order is the server's; the client never re-sorts. **No paging controls** — the count line stays regardless.
- **The `Card` padding is NOT overridden.** Design F-6: `cn()` is a plain join, so a consumer `p-0` and `Card`'s baked-in `p-6` are same-specificity and the built stylesheet emits `.p-0` before `.p-6` — `p-6` wins and the override is silently inert. Inset dividers are the shipped console shape (`TypesSection.tsx:213`, `CatalogSection.tsx:118`).

States tested (design §4): **L-load** — the count line carries `booking.listLoading` (design F-1: the shipped console announces nothing while loading; F15 closes that **for itself only** by reusing the region it already needs) plus `<Skeleton variant="text" lines={4} />`; **L-fail** — `<p role="alert" className="text-sm text-ink-muted">`, the **outage** register, no retry control (re-selecting the date refetches); **L-empty** — `<EmptyState title body />`, no CTA (the owner cannot create a booking); **L** — the loaded list.

Also tested: the badge map (`confirmed→success` «מאושר», `completed→neutral` «התקיים», `no_show→warning` «לא הגיעה», `cancelled→muted` «בוטל»), status never signalled by colour alone (the word is asserted, not the class), a Jerusalem-date default that does not depend on the runner's TZ, and an `axe` pass at zero violations.

- **Done when**: `pnpm -r lint && pnpm -r typecheck && pnpm -r test` green, `pnpm -r build` clean.
- Commit: `feat(manage): bookings day list section`.

## Task 15 — `BookingDetail` — facts, transitions, phone correction, confirm Modals
`Frontend/apps/manage/src/components/BookingDetail.tsx` (**new**), `…/components/BookingsSection.tsx`, `…/__tests__/BookingDetail.test.tsx` (**new**)

**Tests first.** List→detail is an **in-component state swap**, the `CatalogSection.tsx:39-40, 73-107` shape — `apps/manage` has no router and F15 does not introduce one. Mutations **patch the list row from the mutation response** rather than refetching (`CatalogSection.tsx:78-80`: the two views cannot disagree if they render one object).

Structure (design §2): back control (`Button variant="ghost" size="md"` — `size="sm"`'s `min-h-9` is under the 44px floor) → `<h2 tabIndex={-1}>` «פרטי התור» + the status `Badge` → the one `<p role="status" tabIndex={-1}>` region → facts `Card` with three `h3` groups (הלקוחה / הפגישה / הערות הלקוחה) → actions `Card` with an `h3` and the standing `booking.deliveryNotice` line.

- **The `h2` is never the bride's name** — PII in the announced landmark, and the name is the first fact row one line below.
- Label/value rows: `flex flex-col` stacked, `md:grid md:grid-cols-[max-content_1fr] md:gap-x-4` at ≥768 — **`max-content`, not `7rem`**: 7rem corresponds to nothing in the token scale and would be wrong for the `ar` column's glyph metrics.
- **Bidi, the rule with a wrong direction and a wronger one**: `<bdi dir="ltr">` around time, date, **phone**, terms version, seat index, dress size, the day count. **Bare `<bdi>`** around customer name, dress name and `notes` — `dir="ltr"` on Hebrew free text is itself a bidi defect (`BookPage.tsx:1019-1022`).
- **`notes` is rendered as text, and only text** (`booking-core.md:173` names F15 by name): `<p className="whitespace-pre-wrap">` inside a bare `<bdi>`. **No `dangerouslySetInnerHTML`, no markdown pass, no linkification.** A test asserts an input containing `<script>` renders as literal characters.
- **Controls are absent, not disabled**, for transitions the graph forbids (design P-6), per the status/clock table: `confirmed`+future → שינוי מועד · הנפקת קישור ניהול חדש · תיקון מספר הטלפון · **ביטול התור**; `confirmed`+past → סימון: לא הגיעה · סימון: התקיים; `no_show` → סימון: התקיים · החזרה לסטטוס מאושר; `completed` → סימון: לא הגיעה · החזרה לסטטוס מאושר; `cancelled` → **none**, the group renders `booking.cancelledNoActions`. A past `confirmed` row therefore carries **no error affordance and no nag** (Risk 8 rendered as silence).
- **Destructive trigger is `Button variant="danger" size="md"`** — the shipped console pattern (`TypesSection.tsx:276`, `DressEditor.tsx:401`, `HoursSection.tsx:305`). **Never `variant="ghost"` + `className="text-danger"`**: no such variant exists and the override loses the cascade (design F-6 — the built CSS emits `.text-danger` before `.text-ink`, so ghost's `text-ink` wins and the destructive affordance silently disappears).
- **Two confirm `Modal`s** (cancel, phone), the shared `packages/ui` `Modal` with the confirm in a caller-supplied `footer` (`Modal.tsx:8-13`), dismiss `ghost` «חזרה». Each copies the **focus-restore effect at `DressEditor.tsx:130-136`** — the trigger unmounts while the dialog is open, so native `<dialog>` focus-return lands on `<body>`. The jsdom `<dialog>` stub in `src/test/setup.ts` is required.
- **Phone correction, two surfaces** (design §3.3): «תיקון מספר הטלפון» reveals an `Input` (`label` = «מספר טלפון חדש», `dir="ltr"`, `type="tel"`, `inputMode="tel"`) opening **empty** — a pre-filled wrong number invites a one-character edit of the value she is replacing. **No client-side validation of any kind**; the server's 400 renders in the field's `error` slot. The confirm Modal **echoes the typed number as typed**, inside `<bdi dir="ltr">`, and states the three things `booking.phoneModalBody` says: not verified by the platform, on the boutique's word, the existing link stops working and a new one is issued.
- **Resend gets no Modal.** Its warning is a **permanent `--text-xs` muted line under the button** (`booking.resendHint`), readable **before** the tap; the success cue repeats it. **The button is disabled while its request is in flight** — D9's stated client-side mitigation for the double-tap it explicitly declined to serialize server-side. Every action button follows the same in-flight disable.
- **Error rendering (design P-5 / F-2)**: a `booking.error.<CODE>` map keyed on `ApiError.code` for the four codes F15 owns — `BOOKING_TRANSITION_INVALID`, `SLOT_UNAVAILABLE`, `CUSTOMER_ALREADY_BOOKED`, `TOO_MANY_ATTEMPTS` — with `errorMessage(error)` as the fallback for every other code including `VALIDATION_ERROR` (whose message is computed per field and cannot be reproduced client-side). `main.py`'s `*_BODY` literals are English on a Hebrew-only console, and IS 5568 makes the language of an error message operationally load-bearing. This is **not** a validator and mirrors **no** bound; the codes are pinned by `SPEC_ERROR_CODES` so the map cannot silently drift.
- **The register split**: an **outage** is `text-ink-muted`, a thing-she-must-fix is `text-danger`, a nothing-failed notice is `text-warning-text`. Action failure is `<p role="alert" className="text-sm text-danger">` in the action group; success is an **inline muted cue in the `role="status"` region, not a Toast**.
- **Focus after a successful transition**: the cue's region is `tabIndex={-1}` and is **focused**, because a success can unmount the very control that was clicked. Focus must never drop to `<body>`.
- **A 409 never leaves the screen showing a state the server refused**: every mutation answers the same `OwnerBookingDetail`, so a success re-renders the whole detail from the response and never from what the client hoped; a 409 renders the failure line and leaves the previously-rendered facts in place.

Also tested: **DL-load** (`h2` focused on mount, `booking.detailLoading` in the status region, Skeleton), **DL-404** (`role="alert"` + `booking.notFound`, back control still reachable, no facts Card), `manage_link_issued` rendered as **words** and never a chip, `cancelled_at` / `cancelled_by` shown only on a cancelled booking, and an `axe` pass at zero violations.

- **Done when**: `pnpm -r lint && pnpm -r typecheck && pnpm -r test` green, `pnpm -r build` clean.
- Commit: `feat(manage): booking detail, transitions, phone correction and confirm modals`.

## Task 16 — `RescheduleDialog` over the promoted `SlotPicker`
`Frontend/apps/manage/src/components/RescheduleDialog.tsx` (**new**), `…/components/BookingDetail.tsx`, `…/__tests__/BookingDetail.test.tsx`

**Tests first**, in `BookingDetail.test.tsx` — the spec's frontend file table names two console test modules and this is the second one's content, not a third file.

- A `Modal` owning the `GET /manage/slots` fetch and the **promoted** `SlotPicker` from `@boutique/ui` with `labels={{ pickDate: t("booking.pickDate"), pickTime: t("booking.pickTime"), noSlots: t("booking.noSlots") }}`.
- **The dialog IS the confirm** (design P-2): the consequence sentence `booking.rescheduleConsequence` sits directly above the single submit. No second Modal stacked on this one — a focus trap over a focus trap for a decision she is already reading.
- **The current time is always present and pre-selected** (D6's client answer): the dialog injects a `SlotTime` for the booking's own `starts_at` when the fetched grid lacks it (the engine drops full slots, so a capacity-1 target the booking itself occupies never appears), and `value` starts at that instant. Re-submitting it is free — the server short-circuits to a no-op 200.
- **The injected option carries the bare time and nothing else** (design P-3): `SlotPicker` renders every label inside `<bdi dir="ltr">`, so appending «(המועד הנוכחי)» would put Hebrew inside `dir="ltr"`. The current time is named in `booking.rescheduleCurrent` **above** the picker instead.
- **Window and refetch**: opens on the booking's current Jerusalem date, fetches `?from=<that date>&to=<+13d>`, filters in memory; changing the date **outside** the fetched window refetches a fresh 14-day window anchored at the new date. `min` is today (Jerusalem); **no `max`** — the bookable horizon is a server bound and F15 mirrors no server bound client-side.
- **No separate `EmptyState`** (design P-4): `SlotPicker`'s own centered muted no-slots block is the state; two stacked empty messages for one emptiness is worse.
- States tested: **RD-load** (Skeleton in the Modal body, confirm disabled), **RD-empty**, **RD** (current time pre-selected), **RD-fail** (inline `role="alert" text-danger` above the footer and **the dialog stays open with the grid intact** — closing it would throw away the fetch she needs).
- Also tested: focus restore to the trigger on close; the submit disabled while in flight; success closes the dialog, re-renders the detail from the response and patches the list row.
- **Done when**: `pnpm -r lint && pnpm -r typecheck && pnpm -r test` green, `pnpm -r build` clean.
- Commit: `feat(manage): reschedule dialog over the promoted SlotPicker`.

## Task 17 — The `qa-greps.sh` unzoned-formatter check (D20, as corrected by C3)
`Frontend/scripts/qa-greps.sh`

- Extend the **warning-only** date-read block at `:47-54` with a **second grep**, per **C3** — *not* the spec's `Intl\.DateTimeFormat\((?![^)]*timeZone)`, which is a PCRE lookahead inside a `grep -rnE` and aborts the whole block into a silent `ok` (C3(a)), and which would flag all seven correctly-zoned multi-line formatters plus F15's own `lib/jerusalem.ts` even if the syntax worked (C3(b)):

  ```bash
  zoned=$( { grep -rnE 'getDay\(\)|getDate\(\)|toLocaleDateString|toLocaleTimeString' \
               apps/storefront/src apps/manage/src packages/ui/src;
             grep -rnE 'Intl\.DateTimeFormat\([^)]*\)' \
               apps/storefront/src apps/manage/src packages/ui/src | grep -v timeZone; \
           } 2>/dev/null || true)
  ```

  Only a **complete single-line** construction matches, so every zoned formatter is exempt for one of two structural reasons: it is multi-line and has no closing `)` on the line (`BookPage.tsx:82, 88, 132, 136`; `ManageBookingPage.tsx:18, 24`; `packages/ui/src/lib/hours.ts:86` — and, by the same shape, F15's ported `lib/jerusalem.ts`), or it is single-line and carries `timeZone` (`ManageBookingPage.tsx:17`). The type annotation at `BookPage.tsx:95` (`formatter: Intl.DateTimeFormat,`) has no `(` after the name and never matches.
- **Why it is needed at all**: the Gate-1 draft claimed the existing block warns about the console's unzoned formatters. It does not — `TermsSection.tsx:9-11` and `HoursSection.tsx:15-17` use `new Intl.DateTimeFormat("he-IL", {…})` on one line, which none of the four patterns match, so the script prints `ok  no unzoned date reads` today (verified by running it) and would keep printing it over a new unzoned formatter in `lib/jerusalem.ts`. "Every formatter passes `timeZone: JERusalem`" had **no mechanical backstop**. Those two are also the only two lines the new grep catches — which is the check working, not a coincidence.
- The block stays **warning-only and never sets exit status**, so the two existing files surface as review output rather than as a red build. That is the honest state; F15 does not fix them and does not join them.
- **Verify the grep before trusting its silence.** An ERE that errors is indistinguishable from an ERE that finds nothing, because line 49 ends `2>/dev/null || true`. Run the two greps once *without* the redirect and confirm they print `HoursSection.tsx:15` and `TermsSection.tsx:9` and nothing else.
- **Done when**: `bash Frontend/scripts/qa-greps.sh` exits 0, prints **exactly** `HoursSection.tsx:15` and `TermsSection.tsx:9` under `review  date reads`, prints **none** of F15's own files, and prints **no** `ok  no unzoned date reads` line (that line now means the grep died).
- Commit: `chore(qa): flag unzoned Intl.DateTimeFormat constructions (D20)`.

## Task 18 — Gates and the run report
No files.

Run the full verification below, report what ran and what passed, and state **explicitly** that the `db`-marked suites execute only on CI. **Re-nag Risk 2 in the run report** — the owner-attested phone narrows an invariant E3 stated three times, the loop declined the review's request to hold for a user acknowledgement, and Q1 plus `e3-booking-and-comms.md:60` are why. Also carry forward: the owner-created-bookings spec **has no queue entry yet** and the loop must append one (Risk 1's only remedy path routes through it). No push, no PR — the orchestrator owns review and shipping.

---

## What a local run cannot prove

No Docker locally, so `pytest -m db` collects and skips. These tasks' real proofs run on CI only:

| Task | Proof that is CI-only | What the local run still gives |
|---|---|---|
| **1** (`offered_slot`) | `test_booking_service.py` in full — the only caller's whole suite | `ruff` + `mypy app tests` resolving the new signature at the one call site |
| **2** (`upsert_reminder`) | `test_booking_comms_db.py:962, 996, 1027` — the three upsert cases | `ruff` + `mypy`; `test_booking_comms_service.py`'s band tests are unaffected and run locally |
| **6** (repositories) | every assertion in the task | `mypy` over the new signatures |
| **9** (reschedule) | the concurrency and ordering behaviour | the step-order, guard and short-circuit unit tests against fakes **do** run locally |
| **10** (rotation) | the sibling-revocation, atomicity and 0009-collision proofs | the guard, limiter-ordering and audit-payload unit tests **do** run locally |
| **12** (the whole `db` module) | all of it | `mypy` over `tests` |

Everything in Tasks 3, 5, 7, 8, 11 and 13–17 verifies locally. **Task 11 is the milestone**: it is the first point at which the full ten-route table, the four exception handlers and the role guard are exercised end to end with no Postgres.

---

## Testing plan → spec criteria

| Spec criterion | Where |
|---|---|
| Route table wired, authenticated, `no-store`, no `/manage` shadow | `test_booking_owner_api.py` `ROUTES` (fast) |
| `SPEC_ERROR_CODES` set equality — all nine codes | `test_booking_owner_api.py` (fast) |
| A non-`OWNER` `StaffRole` refused on every route | `test_booking_owner_api.py` (fast) |
| The D3 graph: every pair, both clock boundaries, repeat = 200 + no audit row | `test_booking_owner_service.py` (fast) + `test_booking_owner_api.py` (fast) + `test_booking_owner_db.py` (`db`) |
| Reschedule step order — lock **before** the read | `test_booking_owner_service.py` (fast, statement-order assert) + `test_booking_owner_db.py` two-concurrent-reschedules (`db`) |
| Reschedule concurrency against a public create | `test_booking_owner_db.py` (`db`) |
| Lowest-free-seat pick, never the old seat | `test_booking_owner_db.py` (`db`) |
| `CUSTOMER_ALREADY_BOOKED` distinguishable from `SLOT_UNAVAILABLE` | both suites |
| The D11 ordering proof (upsert in-transaction, notify after) | `test_booking_owner_db.py` (`db`) |
| Risk 10 worker race — newest link live | `test_booking_owner_db.py` (`db`) |
| Phone correction: both branches, sibling revocation, atomicity, 0009 collision | `test_booking_owner_service.py` (fast, shape) + `test_booking_owner_db.py` (`db`, truth) |
| Audit row per transition: `actor_id`, `entity`, `details`; none on refusal; **last4 only** | both suites |
| Owner-SMS budget: 429 writes nothing, cancel unmetered | both suites |
| Day list includes cancelled, orders `(starts_at, seat_index)`, clamps offset/limit | `test_booking_owner_service.py` + `test_booking_owner_api.py` + `test_booking_owner_db.py` |
| `manage_token_hash` never on the wire; phone/notes detail-only | `test_booking_owner_service.py` (model-field assert) |
| RLS isolation, tenant B → 404 | `test_booking_isolation.py` (`db`) |
| No migration snuck in | `test_every_tenant_id_table_has_forced_rls` (`db`, unchanged) |
| `SlotPicker` a11y contract survives the promotion | `BookPage.test.tsx:733-758`, **unedited** |
| List and detail states, badge map, `notes` as text, bidi, focus moves, axe | `BookingsSection.test.tsx`, `BookingDetail.test.tsx` |
| Reschedule dialog's four slot-fetch states + pre-selected current time | `BookingDetail.test.tsx` |
| Every new formatter is zoned | `qa-greps.sh` (Task 17, **warning-only** — never red) + the `TZ=America/New_York` pin on `apps/manage`'s test script (Task 13), which is the half that can actually fail |
| Both new console screens pass axe at zero violations | `BookingsSection.test.tsx`, `BookingDetail.test.tsx` — **requires the new `axe-core` devDependency named in Task 14**; no vitest test in this repo runs axe today |

**No E2E is promised.** The console's entire e2e surface is two login-screen tests, because `vite preview` runs with no backend and nothing can log in (`e2e/a11y.spec.ts:10-13`). A booking e2e would first need `/manage/**` route interception, which no existing spec builds — net-new infrastructure, not a checkbox. Recorded rather than quietly skipped.

**Inherited review debt.** `.planning/LOOP-STATE.md:48-54` parks two un-run F16 review dimensions into F15's review. F15's dual review therefore covers, **beyond F15's own diff**: F16's shipped spec-conformance (Task 4 is the first instalment — five stale references corrected) and F16's manage-booking page for frontend/a11y. Whatever the reviewers do not reach is re-pointed at the E3 epic-boundary QA pass, **not** silently closed by F15's merge.

---

## Verification

```
make lint      # ruff check . && ruff format --check . && mypy app tests
               #   + pnpm -r lint && pnpm -r typecheck
               #   + bash Frontend/scripts/qa-greps.sh
make test      # pytest -m "not db" -q
make fe-test   # pnpm -r --if-present test
make fe-build  # pnpm -r build
make e2e       # pnpm -r build && playwright install chromium && pnpm e2e
```

**Green looks like:**

- `make lint` — ruff clean, `ruff format --check` clean, **mypy zero errors over `app` and `tests`**, `pnpm -r lint` and `pnpm -r typecheck` clean across all four workspace packages, and `qa-greps.sh` **exit 0** with its date-read block listing exactly `TermsSection.tsx:9` and `HoursSection.tsx:15` (pre-existing, warning-only) and **none** of F15's files. Note the seven `check` calls above that block scan `$SRC = apps/storefront/src` only, so Task 3 moving `SlotPicker` into `packages/ui` takes it out of the physical-direction and raw-hex checks' reach; it passes both today, and widening `$SRC` is not F15's to do (recorded, not fixed).
- `make test` — all fast tests pass; `test_booking_owner_api.py` and `test_booking_owner_service.py` are green; the `db`-marked modules are **collected and deselected**, and the summary line says so. `test_no_route_is_registered_twice_across_routers` and `test_frontend_constant_parity.py` pass **unedited**.
- `make fe-test` — `BookPage.test.tsx` green with **no assertion edits** from Task 3; `BookingsSection.test.tsx` and `BookingDetail.test.tsx` green including their axe passes at **zero** violations.
- `make fe-build` — both apps build; no unused-import or unused-variable TS error from the `SlotPicker` move.
- `make e2e` — the existing storefront and console specs stay green. **F15 adds no e2e spec**, so an unchanged e2e count is the expected result, not a gap.
- **CI additionally**: `make test-db` green, including the two concurrency proofs, the ordering proof, the sibling-revocation proof and the RLS isolation case.

---

## Out of scope (unchanged from the spec)

A delivery-failure indicator (`booking-comms.md:185` / `:193` stay open against provider go-live) · a late-recorded cancellation (Risk 8) · owner-created bookings (Q6 — **the loop must still queue its spec**) · un-cancelling · an audit-trail read endpoint or history UI (Risk 7) · the calendar view (pre-decided #48, E10) · real-time / a live board · deposit money movement (E4 #19) · waitlist notification (E5 #23) · a customer SMS for no-show / completed and any new SMS template (D13) · reviving `packages/api-client` or hoisting the duplicated `apiFetch` (D15) · retrofitting the four hardcoded-Hebrew console sections and their three sub-components, and any he/ar parity guard (D16, Risk 5) · a compare-and-swap or lock on token rotation (D9) · a client-side phone validator (D20).
