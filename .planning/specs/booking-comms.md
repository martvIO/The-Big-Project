# Spec: Feature 16 — Booking comms lifecycle (Epic E3)

**Created**: 2026-07-29 · **Status**: draft — awaiting Gate 1 · **Epic**: E3 · **Effort**: M
**Depends on**: #11 (SMS foundation), #13 (booking core), #14 (storefront booking UI — shipped, opens the silence window) · **Feeds**: #15 (owner management calls this feature's send/reissue seams), E4 #19 (deposit flow schedules through the same table; consumes `cancelled_at`)

---

## Problem

A real customer can complete a booking today and hear silence. #13 shipped the row, #14 shipped the flow, and every SMS was deliberately deferred here (booking-core.md Risk 1; the epic header calls this the open silence window). Concretely: no confirmation SMS exists, nothing reminds her at 24h, `attendance_confirmed_at` has zero writers, an owner change would notify nobody (no owner endpoints exist yet — F15), and she has no way to cancel without phoning the boutique — even though her refund window may be closing. The manage/cancel link must ride the **immediate confirmation**, not the reminder, because refund windows can close before the 24h mark (epic brief, line 18).

## Goal

Every confirmed booking immediately sends a Hebrew confirmation SMS carrying date/time, the boutique's maps link, and a tokenized manage link; a reminder lands 24h before the appointment with the same link; the link opens a public storefront page where she can **confirm attendance** (writes `attendance_confirmed_at`) or **cancel** (frees the seat, shows the policy consequence from her accepted terms version); owner-cancel/reschedule notification senders exist as tested seams F15 will call. All sends flow through `NotificationService.send_sms`; every send a configured provider handles leaves `message_log` evidence with `booking_id` populated (the unconfigured state is evidence-free by F11's own design — see the lifecycle-sends split).

## What already exists to build on (verified against code)

- **Transport**: `NotificationService.send_sms(tenant_id, *, phone, body, kind, booking_id, log_body)` — the contractual single writer of `message_log` (`app/notifications/service.py:1-5`: "F16's scheduler calls the same send_sms"). It opens its own sessions (cannot be atomic with a booking write) and raises `SmsSendError`/`SmsNotConfiguredError` on failure.
- **Kinds are pre-pinned**: `MessageKind.CONFIRMATION/REMINDER/OWNER_CANCEL/OWNER_RESCHEDULE` exist and the 0007 DB CHECK already allows them; `message_log.booking_id` exists ("F16 populates it"). **No message_log migration needed.**
- **Booking model**: `attendance_confirmed_at` exists (0008), unwritten. Both partial unique indexes exclude `status = 'cancelled'`, so a cancel **is** a status write and structurally frees the seat + re-opens the idempotency slot. `BookingStatus` is DB-CHECK-pinned — no new statuses here.
- **Token pattern**: `generate_session_token()`/`hash_token()` (≥128-bit, sha256-stored) with the `otp_codes` mint-hash-compare precedent.
- **Worker process**: `app/worker.py` is a deployed Railway service (`worker`, `uv run python -m app.worker`) with CI deploy step — a placeholder loop whose docstring reserves the scheduled-messages poller. F16 registers the first job; it does **not** introduce a process.
- **Clock injection**: `WallClock = Callable[[], datetime]` house pattern (`notifications/service.py:36-43`), `WallClockStub` in tests — no freezegun.
- **Policy data**: `terms_versions.refundable_until_hours_before` / `forfeit_percent`, append-only; bookings pin `terms_version_accepted`, so consequences are computed against the **accepted** version, not the current one.
- **Phone**: every booking's customer phone is already `+9725XXXXXXXX` (normalized at OTP send).

## Design

### Data (migration 0010)

Raw-SQL migration in the 0008/0009 house style (`_STANDARD` block, `_updated_at_trigger`, grants + `enable_tenant_rls`).

**`bookings` gains three columns** (architecture.md:52 committed `cancel_token_hash`; the rest is cancel evidence E4 #19 will consume):

```sql
ALTER TABLE bookings ADD COLUMN manage_token_hash TEXT;         -- sha256 of the link token; NULL only for pre-F16 rows
ALTER TABLE bookings ADD COLUMN cancelled_at TIMESTAMPTZ;       -- when status became 'cancelled'
ALTER TABLE bookings ADD COLUMN cancelled_by TEXT
  CHECK (cancelled_by IN ('customer', 'owner'));                -- who did it; E4 evaluates refund-due vs forfeit from (cancelled_at, starts_at, accepted version)
CREATE INDEX idx_bookings_manage_token ON bookings (tenant_id, manage_token_hash)
  WHERE deleted_at IS NULL AND manage_token_hash IS NOT NULL;
```

**`scheduled_messages`** — the schedule state, never the evidence (that stays `message_log`'s):

```sql
CREATE TABLE scheduled_messages (
  -- _STANDARD: id, tenant_id, created_at, updated_at, deleted_at
  booking_id  UUID NOT NULL,
  kind        TEXT NOT NULL CHECK (kind IN ('reminder')),        -- E4/E5 widen (hold-expiry, offers) by migration
  send_after  TIMESTAMPTZ NOT NULL,
  status      TEXT NOT NULL DEFAULT 'pending'
              CHECK (status IN ('pending', 'sent', 'cancelled', 'failed'))
);
CREATE UNIQUE INDEX idx_scheduled_messages_pending_unique
  ON scheduled_messages (tenant_id, booking_id, kind)
  WHERE deleted_at IS NULL AND status = 'pending';               -- idempotency key: at most one pending reminder per booking
CREATE INDEX idx_scheduled_messages_due
  ON scheduled_messages (tenant_id, send_after)
  WHERE deleted_at IS NULL AND status = 'pending';
```

`scheduled_messages` keeps the standard **FORCE RLS** policy. The poller stays inside the tenancy posture by enumerating tenants (the `tenants` table is deliberately RLS-free) and claiming due rows one `tenant_session` at a time — cross-tenant leakage is the recorded existential risk, and this is the first background reader; it does not get to be the first RLS exception. <!-- ponytail: O(tenants) queries per tick — fine at pilot volume; revisit at E5 #29's scale pass -->

### The manage token (D1, D2)

Minted **inside the booking transaction** with `generate_session_token()`, hash committed atomically with the row; the raw value appears **only** inside SMS bodies and the link. This changes `create_booking`'s return contract: it grows a result shape — booking + `created: bool` + `manage_token: str | None` — because today it returns a bare `Booking` on both the fresh-insert and 0009-replay paths, the caller cannot tell them apart, and sha256 is one-way so the raw token is unrecoverable after the transaction. The token is `None` on replay; F15's owner-create (the next caller named in `bookings.py`'s insert docstring) inherits the same contract. Properties, from security-checklist row 21:

- **Lifetime**: valid until `starts_at` for actions; the page remains **readable** after `starts_at` (an honest "this appointment has passed" beats a dead link for someone re-opening the SMS). This is a deliberate, recorded amendment of row 21's "expire at appointment time" wording — actions expire, read-only lookup survives — so F21's audit finds a ruling, not a deviation (Risk 4 carries the trigger).
- **Idempotent, not single-use**: repeat confirm returns the same success; repeat cancel returns the same cancelled state. She will click the link more than once.
- **Never logged raw**: SMS bodies passed to `send_sms` use `log_body` with the token replaced by `●●●` — otherwise `message_log.body` would store the raw token beside its hash on `bookings`, defeating hashed storage (same reasoning as OTP masking).
- **Reissue seam**: `reissue_manage_token(booking)` rotates hash + resends confirmation — built and tested here, called by F15's edit-phone remedy.

### The lifecycle sends (D3, D4, D5)

New module `app/booking/comms.py` (`BookingCommsService`), depending on `NotificationService`, the bookings/scheduled_messages repositories, and an injected `WallClock`. Templates live beside it as pure functions (`confirmation_sms_body(...)` etc.) in `validation.py` style — Hebrew, strictly non-promotional (Amendment 40 posture: counsel sign-off before the real provider ships; recorded in sms-foundation.md:161).

1. **Confirmation** — fired by the booking router **after** `create_booking` commits, only when `created` is true (the 0009 replay must not resend — and now structurally cannot: the replay path carries no raw token). Failure semantics are **split, because F11 split them**: `SmsSendError` (configured provider failed) is swallowed **after** the `failed` `message_log` row exists; `SmsNotConfiguredError` is raised *before any insert* (`service.py:104-105`, deliberate F11 ruling) and leaves **no row** — so `BookingCommsService` checks the sender's `is_configured` up front and skips the send with one app-log warning. Until the real provider adapter lands, confirmations are evidence-free by that F11 design; the booking always stands as a 201 either way. When `maps_url` is null the body falls back to the address line.
2. **Reminder scheduling** — the `scheduled_messages` row is written **inside the booking transaction** (same database; leaving it to a post-commit block would let a crash between commit and block lose the reminder permanently, with nothing sweeping for the gap). Only the SMS send is post-commit work. Body carries date/time, boutique name, and the same manage link; its confirm action is what writes `attendance_confirmed_at`.
3. **Customer cancel** (token page) — one transaction: `status='cancelled'`, `cancelled_at=now()`, `cancelled_by='customer'`, and the pending reminder row flipped to `'cancelled'`. Seat and idempotency slot free structurally via the index predicates. No SMS is sent for a self-service cancel in v1 — the page itself is the receipt.
4. **Owner seams (callers arrive with F15)** — `notify_owner_cancel(booking)` and `notify_owner_reschedule(booking, old_starts_at)` send `OWNER_CANCEL`/`OWNER_RESCHEDULE` bodies. Reschedule's reminder handling is an **upsert, never a re-target**: cancel any *pending* row, then create a fresh row from the new `starts_at` under the D3 bands (including <2h suppression) — explicitly regardless of whether the prior row was `sent`, `cancelled`, or never existed. A day-of reschedule is the common case, its old reminder has already fired, and "re-target the pending row" would be a silent no-op that ships green-tested to F15. The owner-cancel body states the refund/forfeit outcome **only once E4 exists** — until then it states the cancellation and points at the boutique (seam recorded, no money words).

**D3 — reminder timing** (the epic deferred the final rule to this spec):

| Lead time at creation | Rule |
|---|---|
| ≥ 24h | `send_after = starts_at − 24h` |
| 2h–24h | `send_after = now` (immediate — she still gets the confirm-attendance ask) |
| < 2h | no reminder row — the confirmation SMS is seconds old; a second message inside two hours is noise, not service |

At claim time the worker re-checks the booking: not `confirmed` or already started → flip the row to `'cancelled'`, send nothing (defense against races the schedule-time rules can't see).

**Pre-F16 bookings are backfilled (D10)**: F14 is live, so confirmed future-dated bookings with no token and no reminder row will exist at deploy. A one-time backfill step at F16 deploy (CLI command, run once — mechanism is the plan's call) mints a token and schedules a D3-band reminder for every `confirmed` booking with `starts_at` in the future. No retroactive confirmation SMS is sent — a "confirmed!" text days after booking reads as noise; the reminder carries the link and closes the gap the ROADMAP DoD promises unconditionally.

### The worker (D6)

`app/worker.py` becomes real: load `Settings`, `ensure_safe_database_role()` (it keeps the `app_user` URL — the stray `MIGRATIONS_DATABASE_URL` on the worker service is a recorded remediation, not something to start using), then a poll loop every `worker_poll_interval_seconds` (Settings, default 60):

```
for tenant in enumerate_tenants():            # tenants table is RLS-free by design
    with tenant_session(tenant.id):
        rows = claim due pending rows          # FOR UPDATE SKIP LOCKED, LIMIT batch
        for row: re-check booking → send via NotificationService.send_sms(kind='reminder', booking_id=...)
                 → mark 'sent' / 'failed'
```

`SKIP LOCKED` (first use in the codebase, committed by architecture.md:14 — "never cron exactly 24h") makes a second replica safe later; today there is one replica and `send_after <= now()` claiming means missed windows during deploys self-heal on the next tick. A reminder that fires late says the true time — the body renders from `starts_at`, not from "in 24 hours". Sends are unmetered in the worker (the API's limiters are per-process and unreachable from here; volume is bounded by bookings ≤ horizon).

Two deliberate trades, recorded: (a) the claim's row lock intentionally **spans the send** — the same "no DB transaction across a provider call" principle send_sms enforces for itself is traded here for the standard SKIP-LOCKED queue guarantee (crash before mark → row stays pending → at-least-once redelivery; worst case one hung batch per tenant, self-healing on connection timeout). If at-least-once duplicates ever matter, the upgrade path is claim-commit-then-send with a `'sending'` status. (b) `SmsNotConfiguredError` at send time leaves the row **pending** (no status change) — the pre-provider backlog then flushes itself the first tick after the adapter lands, and rows whose `starts_at` passes meanwhile are flipped to `'cancelled'` by the claim-time re-check, so the retry loop is bounded and honest. `SmsSendError` marks the row `'failed'` (evidence exists in message_log).

### The tokenized page (D7, D8) — `/b/{token}`

New storefront route (short path on purpose: the URL rides inside UCS-2 Hebrew SMS where every character is segment budget). The SPA page calls three new endpoints on the **sibling** storefront router (the read router is contractually GET-only; posture copied from `notifications/router.py`: anonymous, cookie-blind, `Cache-Control: no-store`, token in the **body** so API access logs never carry it):

| Endpoint | Does |
|---|---|
| `POST /storefront/booking/lookup` | token → the summary below |
| `POST /storefront/booking/confirm-attendance` | sets `attendance_confirmed_at` (idempotent; rejected after `starts_at` or on a cancelled booking) |
| `POST /storefront/booking/cancel` | the transition in "lifecycle sends" §3 (idempotent; rejected after `starts_at`) |

Lookup's 200 (confirm/cancel return the **same shape**, post-action — the page re-renders from one response type):

```
{ booking:  { starts_at, status, attendance_confirmed_at, appointment_type_name,
              dress_name, dress_size },              -- the snapshots; no image is minted (bookings store none)
  policy:   { refundable_until_hours_before, forfeit_percent },   -- from the ACCEPTED version
  boutique: { name, phone, address, maps_url } }     -- the ContactPanel subset of BoutiqueResponse
```

`policy` requires a new `TermsVersionsRepository.by_version(session, tenant_id, version)` — a single select on the existing unique `(tenant_id, version)` index. The existing `get_terms`/`public_terms` paths return the **current** version and must not be reused here: computing her consequence from re-published terms is precisely the bug `terms_version_accepted` exists to prevent.

This is deliberately **not** a general read-a-booking-by-id endpoint — lookup is by token possession only (F-C7's argument is inherited, and this is its answer: the booking becomes readable again *through the link she was sent*). Page states, six: loaded (upcoming) / attendance confirmed / cancelled / past appointment / invalid link / **retryable failure** (429, network, 5xx — retry affordance plus the boutique phone, the F14 "honest throttle" precedent). Cancel is two-step on the page: the first tap reveals the policy consequence sentence (computed from the accepted version — in-window vs out-of-window wording) plus a confirm control; no silent one-tap cancellation of a wedding-dress appointment. An unknown token renders the invalid-link state on the page itself (the router's catalog fallback never sees it).

Rate limit: one new per-tenant `FixedWindowRateLimiter` **instance** on lookup (house rule: budgets never share instances), Settings-tunable; no per-IP keying until F21 settles `trust_forwarded_for` — same posture as OTP.

### Errors

| Error | Status | Code |
|---|---|---|
| Unknown/invalid token | 404 | `BOOKING_LINK_INVALID` |
| Action after `starts_at` | 409 | `BOOKING_ALREADY_STARTED` |
| Action on cancelled booking (confirm-attendance) | 409 | `BOOKING_CANCELLED` |
| Lookup budget exhausted | 429 | `TOO_MANY_ATTEMPTS` |

Repeat confirm-attendance and repeat cancel are **200s**, not errors (idempotent by checklist row 21).

### Named constants

| Constant | Value | Why |
|---|---|---|
| `REMINDER_LEAD_SECONDS` | 86 400 | the 24h mark (PRD §6 via architecture.md) |
| `REMINDER_SUPPRESS_UNDER_SECONDS` | 7 200 | <2h → confirmation just landed; a second SMS is noise |
| `worker_poll_interval_seconds` | 60 (Settings) | deploy-tunable without code |
| `booking_lookup_max_per_tenant_window` | 60 / 300s (Settings) | anti-scrape ceiling on the public lookup |
| `CONFIRMATION_MAX_SEGMENTS` / `REMINDER_MAX_SEGMENTS` | 3 | UCS-2 ceiling the template tests pin mechanically; worst case fixed as: 30-char slug, 43-char token (`generate_session_token` length), ASCII URL chars costing one UCS-2 char each inside a Hebrew body, 67 chars per concatenated segment |

## Frontend changes

- **Router** (`apps/storefront/src/router.tsx`): new `RouteName` `'manage'`, pattern `/b/{token}`, `DOC_TITLE_KEYS` entry (WCAG 2.4.2), Router switch case.
- **New page** `src/routes/ManageBookingPage.tsx` inside `StorefrontLayout` — packages/ui primitives only (`Card`, `Button`, `ButtonLink`, `VisuallyHidden`, `ContactPanel`), logical properties, `<bdi dir="ltr">` isolation for date/time per R19, Jerusalem rendering via the `JERusalem` helpers.
- **`src/api.ts`**: three wire calls + types for the endpoints above.
- **`src/i18n/he.ts`**: new `manage.*` section (all six page states including the retryable-failure copy, confirm/cancel copy, policy-consequence sentences — user-authored Hebrew at the design gate, F14 precedent) — all keys as dotted literals so `i18n-keys.test.ts` sees them.
- **The one-key change** (design gate, booking.md:1823): `booking.confirmKeepScreen` is rewritten — the screen stops being "your only record" because an SMS now exists. `confirmTitle`/`confirmWhen`/`confirmWhat` stay untouched by gate ruling. **`booking.confirmCold` also stays**: the cold `/book/confirm` branch still holds no token, so its premise is still true (ruled here explicitly rather than inherited silently). §7.4's forbidden-copy table is amended at the design gate — the self-serve-cancel ban lifts.
- **Design gate required**: the manage page is a new public screen → `/spartan:ux prototype manage-booking` before Gate 2, per the frontend workflow.

## Testing

- **Unit (backend)**: D3 reminder math across the three bands and both DST edges (injected `WallClock`, no sleeps); token mint/verify/rotate; template rendering — each body with the worst-case fixture (30-char slug, 43-char token, null and non-null `maps_url`) carries the link intact, the token masked in `log_body`, and stays within its `*_MAX_SEGMENTS` budget.
- **db-marked (CI)**: poller claim under two concurrent claimers (SKIP LOCKED — second claimer gets nothing, no double-send); pending-unique index converges double-scheduling; RLS isolation for `scheduled_messages` (permanent isolation suite gains the table); cancel transaction frees the seat (rebook same instant succeeds) and flips the pending reminder; reschedule-upsert yields exactly one new pending row at new `starts_at` − 24h even when the prior reminder already `sent`; token endpoints happy/invalid/past/idempotent-repeat, and the accepted-version ≠ current-version policy case via `by_version`; `SmsSendError` on confirmation leaves a 201 **and** a `failed` evidence row, while the unconfigured path leaves a 201 and **no** row; idempotent booking replay does not resend; the `/storefront*` route-guard set in `test_no_route_is_registered_twice_across_routers` is extended with the three new paths (it fails on purpose until it is — F11's sibling-router precedent).
- **Frontend**: ManageBookingPage states — all six, including retryable failure — two-step cancel reveal, i18n guard, axe pass; BookPage test updates for the `confirmKeepScreen` rewrite.
- **E2E**: book → fetch link from FakeSmsSender outbox (staging seam) → open `/b/{token}` → confirm attendance → cancel → slot reappears in the picker.

## Out of scope

- Real SMS provider adapter (own commit once the user-owned sender-ID registration lands — F11 decision; everything here degrades through `SmsNotConfiguredError` until then).
- Owner endpoints/UI for cancel/reschedule/resend (**F15** — this feature ships their notification + reissue seams with unit tests only).
- Refund execution, refund-due/forfeit bookkeeping beyond `cancelled_at`/`cancelled_by` evidence (**E4 #19**), and money words in any SMS body.
- Delivery receipts/DLR ingestion; retry/requeue of failed sends (evidence row + F15 remedy is the v1 answer).
- Waitlist notification on a freed slot (E5 #23).
- Calendar attachments/`.ics` (E5 #24).

## Risks & open items

1. **The reminder-timing rule (D3) is this spec's proposal, not yet the user's.** The epic deferred it here; the 2h/24h bands need a human yes. *Owner: user. Trigger: Gate 1.*
2. **SMS copy is user-authored and legally constrained** — four Hebrew bodies + the `confirmKeepScreen` rewrite + the manage-page copy, strictly non-promotional, counsel sign-off before the real provider ships (sms-foundation.md:161). *Owner: user (copy at design gate; counsel before provider go-live). Trigger: design gate.*
3. **Kosher phones never receive any SMS** — confirmation/reminder can fail permanently for a legitimate customer; until F15 ships the remedy surface, the only trace is a `failed` message_log row — and that trace exists **only once a real provider is configured**: in the unconfigured state F11 deliberately raises before any insert, so pre-provider degradation is evidence-free (one app-log warning; the pending `scheduled_messages` row is the reminder's only trace). Accepted for the window between F16 and F15/provider. *Owner: team. Trigger: F15 build + provider go-live.*
4. **Token rides in a URL** — SMS links are possession-auth by nature; mitigations are hashed storage, action cutoff at `starts_at`, body-carried tokens on API calls, and no PII on the page beyond the booking facts. Residual exposure (forwarded SMS = forwarded control) is inherent to the product shape and accepted. *Owner: team. Trigger: F21 audit re-checks.*
5. **Single worker replica; deploys are not atomic across services** — a reminder due during a worker restart sends late (self-healing claim), and a stuck loop is currently undetectable (no healthcheck on the worker service). A liveness signal is deliberately not built here. *Owner: team. Trigger: F21 hardening pass revisits.*
6. **E4 seam**: owner-cancel wording must gain the refund/forfeit outcome clause when E4 #19 lands; `cancelled_by`/`cancelled_at` are recorded now so E4 evaluates without a second migration. *Owner: team. Trigger: E4 #19 spec.*

## Decisions Log

- **D1 — One manage token per booking, on the row, valid to `starts_at`, idempotent actions.** Declined: single-use tokens (she re-opens the SMS; checklist row 21 says idempotent), a separate tokens table (one live token per booking needs no table; rotation overwrites the hash), and reusing the OTP verification token (spent inside F13's booking transaction; 10-min TTL is the wrong shape).
- **D2 — Raw token only in SMS + URL; `message_log` stores a masked body.** Reason: the evidence trail must not hold the raw secret beside its hash; identical reasoning to OTP masking, same `log_body` mechanism.
- **D3 — Reminder bands ≥24h / 2–24h / <2h as tabled.** Declined: always-send (a <2h reminder double-texts within minutes of the confirmation); skip-if-under-24h (loses the confirm-attendance ask for most same-week bookings, which is most of a boutique's book).
- **D4 — Confirmation SMS is post-commit; reminder row + token hash are in-transaction; failure handling split by exception.** `SmsSendError` swallowed after its `failed` evidence row; unconfigured skipped up front (F11 raises before insert — no row exists to lean on). Declined: in-transaction send (send_sms structurally holds its own sessions; a provider hang would block booking commits), propagating `SmsSendError` (turns a committed booking into a 503 — the F14 review already fought this class of lie), and post-commit reminder scheduling (a crash between commit and block loses the reminder with nothing sweeping the gap; same-database work belongs in the transaction).
- **D5 — No customer-cancel SMS in v1.** The page she is looking at is the receipt; every SMS is segment cost and Amendment-40 surface. Declined: cancel-confirmation SMS (adds a template, a kind-CHECK migration, and legal surface for a message whose content she just read).
- **D6 — Poller enumerates tenants under FORCE RLS; `scheduled_messages` gets the standard policy.** Declined: an RLS-exempt schedule table (first exception to the existential-risk control, for an O(tenants)-per-tick saving that is noise at pilot volume).
- **D7 — Page route is `/b/{token}`; API takes tokens in POST bodies.** Reason: UCS-2 segment budget on the SMS side; access-log hygiene on the API side. Declined: `/manage-booking/{token}` (spends ~14 extra UCS-2 chars per SMS forever) and `GET /storefront/booking?token=` (tokens in server logs).
- **D8 — Lookup is by token only; still no public read-a-booking-by-id.** F-C7's cold-confirm problem is answered by the link, not by an ID endpoint; `booking.confirmCold` therefore stays as-is (the cold branch has no token in hand).
- **D9 — `scheduled_messages.kind` starts as `('reminder')` alone.** E4's hold-expiry sweep and E5's offer cascade widen the CHECK when they arrive; pre-adding speculative kinds is exactly the un-lazy thing.
- **D10 — Pre-F16 confirmed future bookings are backfilled** (token minted, D3-band reminder scheduled) by a one-time deploy step; no retroactive confirmation SMS. Declined: accept-the-gap (the ROADMAP DoD promises the reminder unconditionally, and the gap's victims are the pilot's first real customers) and retroactive confirmations (a "confirmed!" text days later reads as spam; the reminder carries the link anyway).
