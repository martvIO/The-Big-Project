# Plan: Feature 16 — Booking comms lifecycle (Epic E3)

**Spec**: `.planning/specs/booking-comms.md` (Gate 1 approved 2026-07-29, D1–D10) · **Design**: `.planning/design/screens/manage-booking/manage-booking.md` (critic ACCEPT r2) · **Copy**: `.planning/design/screens/manage-booking/copy.md` (APPROVED — Interview Q5) · **Branch**: `feature/booking-comms` · **Created**: 2026-07-30

**Gate 2: SELF-APPROVED** under the standing approval in `.planning/epics/interview-2026-07-30.md` §1 (Q1). F16 touches no payment, refund, privacy-law text or tenant-billing surface — the named stop-list is F17/F18/F19/F20/F29/F48 — so it self-approves and proceeds. The design gate closed with Interview **Q5** ("F16 Hebrew: approved as drafted"); Task 0 records that on the copy deck.

TDD throughout. Local gate per task: `make lint` + `make test` for backend tasks, `pnpm -r lint && pnpm -r typecheck && pnpm -r test` for frontend ones, `frontend/scripts/qa-greps.sh` clean from Task 9 onward. **`db`-marked tests are written here and executed only on CI** — no Docker locally.

---

## Interview rulings this plan is built on

| Ruling | Effect on the build |
|---|---|
| **Q4** — short-notice reminder sends immediately and **drops «מחר»** | ONE date-led reminder body serves all bands: `{{boutique}}: תזכורת — התור שלך ביום {{weekday}}, {{date}} בשעה {{time}}. לאישור הגעה או ביטול: {{link}}`. The copy deck's `reminder` row is rewritten; a test asserts the body contains no «מחר» in any band. Bands unchanged (pre-decided #6). |
| **Q5** — all 19 page strings + 4 SMS bodies + the cancel-cost line + the softened confirmation line are APPROVED | Build them verbatim. Counsel sign-off on the SMS bodies stays a pre-provider gate, not a pre-merge one. |
| **pre-decided #3** | `booking.confirmKeepScreen` → «פרטי התור נשמרו אצלנו, וכדאי בכל זאת לצלם את המסך. אנחנו נחכה לך.» |
| **pre-decided #4** | `manage.cancelConsequenceFree` → «לא נגבה תשלום על התור, כך שהביטול אינו כרוך בעלות.» — rendered on **both** sides of the window until E4. |
| **pre-decided #5** | `manage.attendanceDone` → «ההגעה אושרה. נתראה.» — **no exclamation mark**. This resolves the copy deck's ⚠ register question and overrides the drafted «נתראה!»; Q5's "as drafted" and #5 conflict on exactly one glyph and #5 is the specific, later ruling, with a mechanically checkable basis (`he.ts` contains zero exclamation marks). Recorded on the deck in Task 0. |
| **pre-decided #7** | P2–P5 accepted as designed: reused fact labels, cancel-after-confirm, rebook link on the cancelled state, `danger` only on the final click. |
| **pre-decided #8** | `truncate_boutique_name(name, 25)` inside SMS templates — production must match the tested fixture (design finding F-M3). |
| **pre-decided #9** | Backfill is a one-time `python -m app.cli backfill-booking-links`, on the existing audited CLI. |
| **Q3 / pre-decided #47** | Ship `ar` resource keys alongside the new Hebrew ones, untranslated, wired into the existing i18next setup. Arabic is not selectable; no switcher, no second stylesheet. |

---

## The one thing the spec does not answer, ruled here

**How does the worker reproduce the manage link hours or days after the booking transaction?**

The spec requires three things that cannot all hold as written: the reminder carries "the same manage link" (§lifecycle sends 2), `bookings` stores only `manage_token_hash` (D1), and sha256 is one-way ("the raw token is unrecoverable after the transaction", D1). Something has to give. The three candidates:

| Option | Verdict |
|---|---|
| **(a) The pending `scheduled_messages` row carries the raw token**, cleared the moment the row leaves `pending` | **CHOSEN** |
| (b) Derive the token by HMAC from a new platform secret | Declined: introduces the platform's **first** shared secret, a `Settings` field with a production boot validator, a `manage_token_version` column for `reissue_manage_token` to bump, and a footgun where rotating or losing the secret silently invalidates every live link. Real machinery for a pilot with no key management. |
| (c) The worker mints a fresh token and rotates the hash at send time | Declined, decisively, by **Q4**: in the 2–24h band the reminder fires *seconds* after the confirmation, so rotation would kill the link in the text she is still looking at. It also breaks D1's "idempotent, not single-use — she will click the link more than once". |

**What (a) costs, stated plainly**: `scheduled_messages.manage_token TEXT` holds a live secret at rest while a reminder is pending. It is `NULL` on every terminal row, and the rows are purged with their booking (pre-decided #10). What it preserves: `bookings` — the table retained for 7 years and the one a leak most plausibly targets — never holds a secret, and `message_log.body` never holds one (D2's masking is unchanged). What a leaked live token grants is bounded by the endpoints: read the booking facts (the lookup response carries no customer name), confirm attendance, cancel. A reader who can reach `scheduled_messages` can already read `customers.phone`, `customers.name` and `bookings.notes`, which is strictly worse; the marginal harm is the ability to cancel an upcoming appointment. Accepted, recorded, and reversible — swapping to (b) later is one migration plus one function.

This is a **spec amendment** and Task 1 writes it into `booking-comms.md` §Data in the same PR.

## Second ruling: the manage-link segment budget has a slug ceiling the spec did not name

`CONFIRMATION_MAX_SEGMENTS = 3` is 201 UCS-2 units (3 × 67 concatenated). The worst case computes to **199** with a 30-char slug, a 43-char token, `modryn.co.il`, a 25-char boutique name and a 10-char date — two units of headroom. But `is_valid_slug` (`app/tenancy/slugs.py`) permits a **63**-character DNS label, which pushes the confirmation body to 4 segments.

Ruling: the budget test pins the **documented** worst case (30-char slug) and a second test documents the true ceiling as a named constant, `MANAGE_LINK_SLUG_BUDGET_CHARS = 30`. A longer slug costs one extra segment; it does not break the send. Capping slug length belongs to F6's provisioning surface, not to a comms feature, and a boot-time guard on a legitimate slug would be worse than a fourth segment. Recorded as a finding, not fixed here.

---

## Task 0 — Close the design gate on paper
`.planning/design/screens/manage-booking/copy.md`

- Status line: `DRAFT — awaiting user sign-off` → `APPROVED 2026-07-30 (Interview Q5)`; every row's Status column → `APPROVED`.
- Rewrite the `reminder` row to Q4's date-led body and strike its ⚠.
- Resolve the `manage.attendanceDone` ⚠ to pre-decided #5's «ההגעה אושרה. נתראה.», with the conflict noted.
- Replace §4 "Questions for the user" with the four answers (Q4, Q5, pre-decided #3/#4/#5) so the deck stops asking a settled question.
- Note pre-decided #8's 25-char truncation on the SMS table (F-M3's plan-phase follow-up, discharged in Task 3).
- Commit: `docs(design): F16 copy deck approved — Interview Q5`.

## Task 1 — Plan + spec amendment
`.planning/plans/booking-comms.md` (this file), `.planning/specs/booking-comms.md`

- Amend the spec's §Data with the `scheduled_messages.manage_token` column and the ruling above; amend §Named constants with `MANAGE_LINK_SLUG_BUDGET_CHARS`.
- Commit: `docs(planning): F16 implementation plan — Gate 2 self-approved`.

## Task 2 — Migration 0010 + models
`backend/migrations/versions/0010_booking_comms.py`, `backend/app/models/{booking,scheduled_message}.py`, `backend/app/models/constants.py`

- **0010, revises 0009** — 0009 is the current head (`ls backend/migrations/versions`), and the spec named 0010 before it existed.
- `bookings` gains `manage_token_hash TEXT`, `cancelled_at TIMESTAMPTZ`, `cancelled_by TEXT CHECK (cancelled_by IN ('customer','owner'))` + `idx_bookings_manage_token ON bookings (tenant_id, manage_token_hash) WHERE deleted_at IS NULL AND manage_token_hash IS NOT NULL`.
- `scheduled_messages` in the 0008 house style: the `_STANDARD` block, `_updated_at_trigger`, `GRANT SELECT, INSERT, UPDATE, DELETE … TO app_user`, then `enable_tenant_rls` — the standard FORCE RLS policy, no exception (D6). `test_every_tenant_id_table_has_forced_rls` picks the new table up automatically, which is why no test list needs editing.
- Both partial indexes from the spec, plus `manage_token TEXT` per the ruling above.
- `ScheduledMessage` model; `ScheduledMessageKind`/`ScheduledMessageStatus` in `constants.py` with the "the DB pins this exact set" comment the file uses everywhere else.
- Commit: `feat(booking): migration 0010 — manage token, cancel evidence, scheduled_messages`.

## Task 3 — Pure templates + segment budget (TDD, no DB)
`backend/app/booking/comms_templates.py`, `backend/tests/test_booking_comms_templates.py`

Tests first. Pure module, imports nothing from `app/db`:
- `manage_link(*, slug, base_domain, token)` → `https://{slug}.{base_domain}/b/{token}`. Always https — a real SMS may not carry `http:`.
- `truncate_boutique_name(name)` at `BOUTIQUE_NAME_MAX_CHARS = 25` (pre-decided #8).
- `jerusalem_weekday/date/time` — hand-rolled Hebrew weekday tuple and `d.m.yyyy`, both computed in `BOUTIQUE_TIMEZONE`. Never `locale`-dependent formatting: the CI runner, a laptop and Israel are three different calendar days for part of every day, and the server must render the boutique's.
- `confirmation_sms_body`, `reminder_sms_body`, `owner_cancel_sms_body` (drops its contact clause when the boutique published no phone), `owner_reschedule_sms_body`.
- `mask_manage_link(body, token)` → the token replaced by `●●●`, reusing `MASK_CHAR` from `app/notifications/validation.py` (D2's mechanism, same glyph).
- `ucs2_segments(body)` counting **UTF-16 code units** (a surrogate pair is 2), `1` up to `UCS2_SINGLE_LIMIT = 70`, else `ceil(units / UCS2_CONCAT_LIMIT = 67)`.

Assertions: every body clears its `*_MAX_SEGMENTS = 3` budget at the documented worst-case fixture; the link survives intact; the token is absent from the masked body and the mask is present; the reminder contains **no «מחר»** and does contain weekday + date (Q4); a 26-char name is truncated to 25; the 63-char-slug ceiling is documented, not asserted as passing.

Commit: `feat(booking): Hebrew lifecycle SMS templates with a UCS-2 segment budget`.

## Task 4 — The manage token (TDD, no DB)
`backend/app/booking/tokens.py`, `backend/tests/test_manage_token.py`

- `mint_manage_token()` → `generate_session_token()` (43 chars, 256 bits — reuses the `otp_codes` mint-hash-compare precedent rather than inventing a second primitive).
- `manage_token_hash(raw)` → `hash_token(raw)`.
- `manage_token_matches(raw, stored_hash)` → `hmac.compare_digest` against the stored hex, `False` on `None`.

`manage_token_matches` is the final gate after the indexed SELECT, and it is not decoration: the SELECT is an equality on the hash, so it *should* be redundant — which is precisely why it is there. If the predicate is ever widened (a prefix match, a `LIKE`, a join that drops the tenant clause) the constant-time re-check is what stops the widened query from handing back a booking whose token the caller does not hold. Tests: correct token matches, one-character-off does not, `None` hash never matches, the raw token is never returned by any function here.

Commit: `feat(booking): hashed manage token with constant-time verification`.

## Task 5 — Repositories (TDD; unit where pure, `db` for the rest)
`backend/app/db/repositories/{scheduled_messages,bookings,terms}.py`, `backend/tests/test_booking_repositories.py`

- `ScheduledMessagesRepository`: `insert`, `pending_for_booking`, `cancel_pending(booking_id, kind) -> int` (clears `manage_token`), `claim_due(now, limit)`, `mark(id, status)` (clears `manage_token` on every terminal status).
- `claim_due` is `select(...).where(status='pending', send_after <= now, deleted_at IS NULL, tenant_id=…).order_by(send_after).limit(limit).with_for_update(skip_locked=True)` — the codebase's first `SKIP LOCKED`, committed by `architecture.md` ("never cron exactly 24h").
- `BookingsRepository` gains `by_manage_token_hash`, `set_manage_token_hash`, `confirm_attendance`, `cancel` (one statement setting `status`/`cancelled_at`/`cancelled_by`), and `list_confirmed_after(instant)` for the backfill. Every predicate keeps `deleted_at IS NULL` and the redundant `tenant_id` (house defence-in-depth).
- `TermsVersionsRepository.by_version(session, tenant_id, version)` — one select on the existing unique `(tenant_id, version)`. **`current()`/`public_terms` must not be reused for the manage page**: computing her consequence from re-published terms is the bug `terms_version_accepted` exists to prevent.
- Commit: `feat(booking): scheduled-message and manage-token repositories`.

## Task 6 — Reminder bands + `BookingCommsService` (TDD)
`backend/app/booking/comms.py`, `backend/tests/test_booking_comms_service.py`

- Module-level and pure, so the band tests need no DB: `REMINDER_LEAD_SECONDS = 86_400`, `REMINDER_SUPPRESS_UNDER_SECONDS = 7_200`, `reminder_send_after(*, starts_at, now) -> datetime | None`. `lead < 2h` → `None`; `lead >= 24h` → `starts_at − 24h`; otherwise → `now`. Both boundaries are tested at the exact second, and both Israeli DST edges are tested through an injected `WallClock` (house pattern, no freezegun).
- `BookingCommsService(session_factory, *, notifications, clock)` with the bookings / scheduled-messages / customers repositories:
  - `send_confirmation(...)` — checks `notifications.is_configured` **up front** and skips with one app-log warning when it is false, because F11 raises `SmsNotConfiguredError` *before* any insert (`service.py:104-105`) and leaves no row to lean on. `SmsSendError` is swallowed *after* its `failed` evidence row exists. The booking stands as a 201 either way (D4).
  - `notify_owner_cancel`, `notify_owner_reschedule` — F15's seams, unit-tested here with a fake sender, no caller yet.
  - `reissue_manage_token` — rotate the hash, rewrite the pending reminder's stored token, resend the confirmation. F15's edit-phone remedy calls it.
  - `reschedule_reminder` — an **upsert, never a re-target**: cancel any pending row, then create a fresh one from the new `starts_at` under the D3 bands including the <2h suppression, regardless of whether the prior row was `sent`, `cancelled`, or absent. A day-of reschedule is the common case and its old reminder has already fired, so "re-target the pending row" is a silent no-op that ships green.
  - `drain_due(...)` — the poller body for one tenant (Task 8 calls it).
- Commit: `feat(booking): lifecycle comms service and D3 reminder bands`.

## Task 7 — `create_booking` grows a result shape; the router fires the confirmation (TDD)
`backend/app/booking/{service,router}.py`, `backend/app/main.py`, `backend/tests/test_booking_service.py`, `backend/tests/test_booking_api.py`

- `create_booking` returns `BookingClaim(booking, created: bool, manage_token: str | None)`. It must: today it returns a bare `Booking` on both the fresh-insert and the 0009-replay path, so the caller cannot tell them apart, and sha256 makes the raw token unrecoverable afterwards. `manage_token` is `None` on replay — which is what makes "the replay must not resend" structural rather than a remembered `if`.
- Inside the one transaction: mint + hash onto the INSERT, and write the `scheduled_messages` row **in the same transaction**. Post-commit scheduling would lose the reminder permanently on a crash between commit and block, with nothing sweeping the gap; the send is the only post-commit work.
- Router: after the call, `if claim.created and claim.manage_token is not None: await comms.send_confirmation(...)`. Wire shape unchanged.
- `main.py`: build `BookingCommsService`, pass `ScheduledMessagesRepository` into `BookingService`, and register the three new exception handlers (Task 8's error table).
- Every existing caller and stub in `test_booking_api.py` / `test_booking_service.py` moves to the new return shape — a mechanical but wide edit, stated rather than discovered.
- Commit: `feat(booking): mint the manage token and schedule the reminder inside the claim`.

## Task 8 — The tokenized page's three endpoints (TDD)
`backend/app/booking/{manage,schemas,router}.py`, `backend/app/storefront/{validation,router}.py`, `backend/app/main.py`, `backend/tests/{test_booking_manage_api,test_storefront_api}.py`

- `ManageBookingService` in a new `app/booking/manage.py`: `lookup`, `confirm_attendance`, `cancel`. All three return the **same** response shape post-action, so the page re-renders from one type.
- Errors, per the spec's table: `BOOKING_LINK_INVALID` 404, `BOOKING_ALREADY_STARTED` 409, `BOOKING_CANCELLED` 409, `TOO_MANY_ATTEMPTS` 429. Repeat confirm and repeat cancel are **200s** (idempotent, checklist row 21). The page stays *readable* after `starts_at` — actions expire, lookup survives — which is the spec's recorded amendment of checklist row 21's wording.
- `cancel` is one transaction: `status='cancelled'`, `cancelled_at`, `cancelled_by='customer'`, and the pending reminder flipped to `'cancelled'`. Seat and idempotency slot free structurally via 0008/0009's index predicates. No SMS (D5).
- Routes on the **existing** `/storefront` sibling in `app/booking/router.py` — anonymous, cookie-blind, `no-store`, token in the **body** so no access log carries it. Lookup carries its own `FixedWindowRateLimiter` **instance** (house rule: budgets never share instances, because `max_attempts` lives on the limiter and not per key), tuned by two new `Settings` fields.
- **Extract `profile_text(profile, key)` into `app/storefront/validation.py`** and call it from both `public_boutique` and the manage response. The ""→null collapse is a WCAG 2.4.4 rule with a comment in `storefront/router.py` saying the projection is where it lives; a second public projection re-implementing it is exactly the drift that comment warns about. Behaviour-identical, covered by the existing tests.
- `test_storefront_api.py`: add the three paths to the hand-maintained literal set in `test_no_route_is_registered_twice_across_routers` — **this fails on purpose first**, and fixing it is what arms the derived guard suites. `ROUTES` is derived from GET routes only, so three POSTs add no GET parametrisation.
- Commit: `feat(booking): tokenized lookup, confirm-attendance and cancel`.

## Task 9 — The worker becomes real (TDD)
`backend/app/worker.py`, `backend/app/core/config.py`, `backend/tests/test_worker.py`

- `Settings` + `ensure_safe_database_role()` (keep the `app_user` URL — the stray `MIGRATIONS_DATABASE_URL` on the worker service is a recorded remediation, not something to start using), then a poll loop every `worker_poll_interval_seconds` (default 60).
- Per tick: `TenantsRepository.list_active()` (the `tenants` table is RLS-free by design), then one `tenant_session` per tenant to claim and drain. O(tenants) queries per tick — noise at pilot volume, carried as a `ponytail:` comment pointing at E5 #29's scale pass.
- Per claimed row, in order: re-read the booking; not `confirmed`, missing, or already started → flip to `'cancelled'` and send nothing (defence against races the schedule-time rules cannot see); sender unconfigured → leave the row **pending** and stop this tenant's batch, so the pre-provider backlog flushes itself the first tick after the adapter lands; `SmsSendError` → `'failed'` (evidence exists in `message_log`); success → `'sent'`, token cleared.
- **Idempotency and concurrency safety, the three mechanisms**: (1) `idx_scheduled_messages_pending_unique` admits at most one pending reminder per `(tenant, booking, kind)`, so double-scheduling converges instead of double-sending; (2) `FOR UPDATE SKIP LOCKED` + `status='pending'` means a second replica claiming concurrently gets nothing, never the same row; (3) the row lock **spans the send** and the mark commits with it, so a crash before the mark leaves the row pending and redelivery is at-least-once. Trade (a) from the spec, recorded in the code: the upgrade path if duplicates ever matter is claim-commit-then-send with a `'sending'` status.
- The loop body is a plain function taking the service, so `test_worker.py` drives one tick against a fake sender with **no** DB.
- Commit: `feat(worker): scheduled-message poller with SKIP LOCKED claims`.

## Task 10 — Backfill command (TDD)
`backend/app/booking/backfill.py`, `backend/app/cli.py`, `backend/app/models/constants.py`, `backend/tests/test_cli.py`

- `python -m app.cli backfill-booking-links` — per pre-decided #9, one command on the existing audited CLI, run once at F16 deploy. Per tenant: every `confirmed` booking with `starts_at` in the future and `manage_token_hash IS NULL` gets a token and a D3-band reminder. **No retroactive confirmation SMS** (D10) — a "confirmed!" text days later reads as spam, and the reminder carries the link.
- Idempotent by predicate: a second run finds nothing, because the first run filled `manage_token_hash`. Bounded by the batch-loop convention.
- `PlatformAuditAction.BOOKING_LINKS_BACKFILLED` — `platform_audit_log.action` is plain `TEXT` with **no** CHECK (`0004`), so this needs no migration.
- Commit: `feat(booking): one-time manage-link backfill command`.

## Task 11 — db-marked suites (written here, executed on CI)
`backend/tests/{test_booking_comms_db,test_booking_isolation}.py`

Everything that needs real Postgres, per the spec's testing section: two concurrent claimers under `SKIP LOCKED` (the second gets nothing, no double send); the pending-unique index converging double-scheduling; RLS isolation for `scheduled_messages` (added to the permanent isolation suite); the cancel transaction freeing the seat — a rebook at the same instant succeeds — and flipping the pending reminder; the reschedule upsert yielding exactly one new pending row even when the prior reminder already `sent`; the token endpoints happy / invalid / past / idempotent-repeat; the accepted-version ≠ current-version policy case through `by_version`; `SmsSendError` on the confirmation leaving a 201 **and** a `failed` evidence row while the unconfigured path leaves a 201 and **no** row; the 0009 replay not resending; the backfill.

Commit: `test(booking): db-marked comms, claim-race and isolation coverage`.

## Task 12 — Frontend: router, api, i18n
`frontend/apps/storefront/src/{router.tsx,api.ts,i18n/he.ts,i18n/ar.ts,i18n/index.ts}`, `src/__tests__/{router,api,i18n-keys}.test.*`

- Router's five coordinated, compiler-enforced edits: `RouteName` gains `"manage"`; `RouteMatch` gains `{name:"manage"; token:string}`; `DOC_TITLE_KEYS` gains `manage: "document.manageTitle"` (a `Record<RouteName,string>` — it will not compile without it); the `matchRoute` chain gains `/^\/b\/([^/]+)$/` **above** the catalog fallthrough, so a bad token reaches the page's own invalid-link state and is never swallowed by the catalog (D7/D8); the render switch.
- `api.ts`: `ManageBookingResponse` and the three POSTs, token in the body. Wire snake_case verbatim — this app does no case conversion.
- `he.ts`: `document.manageTitle` + the 17 `manage.*` rows verbatim from the approved deck, and the one `booking.confirmKeepScreen` rewrite. `booking.confirmCold` **stays** — the cold `/book/confirm` branch still holds no token, so its premise is still true (ruled explicitly in the spec rather than inherited silently).
- `ar.ts`: new bundle carrying exactly the F16 keys, values left as the Hebrew pending translation, registered in `i18n/index.ts` alongside `he`. `lng` stays `"he"` and no switcher ships — Arabic is not live for the pilot (Q3). This is the first `ar` bundle in the repo, so F16 creates the file the remaining features append to.
- Commit: `feat(storefront): /b/{token} route, manage API calls and Hebrew copy`.

## Task 13 — `ManageBookingPage` (design-dependent — follows `manage-booking.md`)
`frontend/apps/storefront/src/routes/ManageBookingPage.tsx`, `src/__tests__/ManageBookingPage.test.tsx`

- `packages/ui` primitives only: `Card`, `Button`, `ButtonLink`, `Skeleton`, `VisuallyHidden`, plus the existing `ContactCard`. **Nothing new in `packages/ui`** — `Button variant="danger"` already ships and makes its first storefront appearance here (P5).
- Layout `mx-auto flex max-w-[640px] flex-col gap-6 px-4 pt-8 pb-16 md:px-6`, identical to `/book/*` so the two surfaces read as one product. `Card` padding stays `p-6` at every width (R9: `cn` has no tailwind-merge, so a caller's `p-4` ships both classes and loses on stylesheet order).
- **All six states** from §2: skeleton (with the nested `VisuallyHidden` → `<span role="status">` shape — R30; `aria-busy` on a div is announced by neither VoiceOver nor NVDA), loaded, attendance-confirmed, cancelled, past, invalid link, retryable failure. The page always re-renders from the **response's** booking, never from what it optimistically hoped: a 409 `BOOKING_ALREADY_STARTED` renders **P**, a 409 `BOOKING_CANCELLED` renders **C**.
- The cancel **two-step**: the secondary button reveals an inline block (no `Modal` — an inline reveal keeps one decision on one surface and spares the focus-trap machinery for a two-button choice); focus moves to the revealed block; `השארת התור` collapses it and returns focus to the trigger. The window fact renders as the R19 split shape (lead + isolated `<bdi dir="ltr">{hours}</bdi>` + suffix) and **both** window sides render `manage.cancelConsequenceFree` until E4 (P1 / pre-decided #4).
- Focus destinations for the two success transitions, since each removes the control that was just clicked: L→L2 focuses the mounted `manage.attendanceDone` line, reveal→C focuses the mounted `manage.cancelled` line. Focus never drops to `<body>` after the one action the page exists for.
- ContactPanel from `useBoutique()` as primary, the lookup payload's `boutique` as fallback for L/L2/C/P only — X and R are lookup failures whose responses are the `ErrorResponse` shape and carry no boutique data under any circumstance (F-M2 as corrected at the gate).
- Instants render in **Jerusalem**, weekday + date + time, with `<bdi dir="ltr">` on every numeral island (R19, §7.3).
- Commit: `feat(storefront): manage-booking page with confirm and two-step cancel`.

## Task 14 — The one F14 string, and its tests
`frontend/apps/storefront/src/__tests__/BookPage.test.tsx`

The `confirmKeepScreen` rewrite lands in Task 12; this task re-points every assertion that pinned the old sentence. `confirmTitle`/`confirmWhen`/`confirmWhat` are untouched by gate ruling.

Commit folded into Task 13's if the diff is small; otherwise `test(storefront): confirmation screen no longer claims to be the only record`.

## Task 15 — E2E + mechanical
`frontend/e2e/storefront.spec.ts`, `frontend/e2e/a11y.spec.ts`

- Fixture the three new endpoints into `installApi`'s `BOOKING_PATHS` map. Specs: the `/b/{token}` happy path (facts → confirm attendance → two-step cancel → the cancelled state's rebook link), the cancelled state, and the invalid-token state.
- axe with `withTags(["wcag2a","wcag2aa"])` on the new route in every state that has content, at **zero** violations; no horizontal scroll at 375/768/1440; the skip link stays the first Tab stop.
- `qa-greps.sh` clean — note its `localStorage` ban (the "no favorites" check) and its physical-direction ban; the page uses logical properties throughout and stores nothing.
- Commit: `test(e2e): /b/{token} happy path, cancelled and invalid-token states`.

## Task 16 — Gates + report
`make lint`, `make test`, `make fe-test`, `make fe-build`, `make e2e`. Report what ran, what passed, and — explicitly — that the `db`-marked suites execute only on CI. No push, no PR: the orchestrator owns review and shipping.

---

## Testing plan → spec criteria

| Spec criterion | Where |
|---|---|
| D3 bands, both boundaries, both DST edges | `test_booking_comms_service.py`, injected `WallClock` |
| Q4: no «מחר» in any band | `test_booking_comms_templates.py` |
| Every body ≤ 3 UCS-2 segments at the worst-case fixture | `test_booking_comms_templates.py` |
| Token masked in `log_body`, never stored raw on `bookings` | `test_booking_comms_templates.py` + `test_booking_comms_db.py` |
| Constant-time verify; wrong/absent token rejected | `test_manage_token.py` |
| Poller claim under two concurrent claimers | `test_booking_comms_db.py` (`db`) |
| Worker idempotency (pending-unique, re-check, at-least-once) | `test_worker.py` (fake sender) + `test_booking_comms_db.py` (`db`) |
| Cancel inside vs outside the policy window | `ManageBookingPage.test.tsx` (the sentence) + `test_booking_comms_db.py` (the transition) |
| Invalid / expired token | `test_booking_manage_api.py`, `test_booking_comms_db.py`, e2e |
| Six page states + two-step reveal + axe | `ManageBookingPage.test.tsx`, `storefront.spec.ts` |
| Route posture (anonymous, cookie-blind, no-store, POST-only) | `test_booking_manage_api.py` + the derived guards in `test_storefront_api.py` |
| `scheduled_messages` RLS isolation | `test_booking_isolation.py` (`db`) + the automatic `test_every_tenant_id_table_has_forced_rls` |

## Out of scope (unchanged from the spec)

Real SMS provider adapter · owner endpoints/UI for cancel/reschedule/resend (**F15** — this ships their tested seams only) · refunds and money words (**E4 #19**) · delivery receipts, retry/requeue of failed sends · waitlist notification (**E5 #23**) · `.ics` (**E5 #24**).
