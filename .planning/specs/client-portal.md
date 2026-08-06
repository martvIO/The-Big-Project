# Spec: Feature 24 — Client portal: OTP login, "My Bookings", `.ics`, bell (Epic E5)

**Created**: 2026-08-06 · **Status**: **Gate 1: standing approval — interview-2026-07-30.md §Standing approvals** (Q1: F24 touches neither payments, refunds, privacy-law text nor billing — it self-approves; the named exceptions are F17/F18/F19/F20/F29/F48) · **Epic**: E5 · **Effort**: L
**Depends on**: F11 (OTP primitive), F13 (booking core + customers), F16 (comms — message_log lifecycle rows, tokenized manage page) · **Feeds**: E9 multi-fitting dashboard, F35 staff bell (mirror, no dependency)
**Pre-decided**: #17 (OTP-only login, per-booking `.ics` download, no 2-way calendar sync) · #18 (bell refreshes on page open — no polling loop)

---

## Problem

A customer's only durable surface today is the tokenized SMS link (`/b/{token}`). Lose the text, and she has nothing: no way to see her upcoming fittings, no way to cancel, no calendar entry, no history of what the boutique told her. F24 gives her a login she can return to — without introducing passwords, email, or any identity the platform doesn't already hold.

## Goal

On the tenant storefront, a customer logs in with her phone + OTP (the same F11 primitive the booking flow uses), sees all her bookings at that boutique, performs the same confirm-attendance / cancel actions the tokenized page offers (which **remains valid** for non-login users), downloads a per-booking `.ics`, and sees a notification bell listing the booking messages the boutique has sent her. Hebrew-first RTL, `ar` keys shipped untranslated, no exclamation marks, axe zero-violation (IS 5568 / WCAG 2.0 AA).

## Conflicts between the brief and shipped reality (recorded, codebase-consistent reading taken)

1. **Brief: "the bell is poll-based in this epic"** — superseded by pre-decided #18: refresh on page open, **no polling loop**. Every event the bell shows already sent an SMS the same second; the bell is a history list, not the alert channel.
2. **Brief: "E5 predates E6's Pusher foundation"** — stale. E6/E7 floor features (F57–F59, F33–F37) shipped with **no realtime vendor** (pre-decided #23: ~5s refetch boards). There is no Pusher to wait for and none is pulled forward.
3. **Brief: "the delivery substrate question is settled at spec time"** — settled here: the bell is a read-side projection over `message_log` (D6), fetched on portal open.
4. **Brief implies customer identity is just "OTP-verified phone"** — shipped reality is stronger: F13/F53/F20 built a full `customers` row keyed (tenant, phone) with CRM + consent + erasure fields, and `bookings.customer_id` is NOT NULL. The portal binds to the customer row, not to a bare phone.

## What already exists to build on (verified against code)

- **OTP**: `OtpService.send/verify/consume_verification` (`app/notifications/service.py`) with per-phone, per-tenant, per-verify and (inert) per-IP limiter instances; endpoints `POST /storefront/otp/send`, `POST /storefront/otp/verify` (`notifications/router.py`). `verification_token` is 128-bit, sha256-stored, single-use, TTL 600s. `otp_dev_code` exists for dev (boot-fails in production).
- **Customers**: `customers` keyed (tenant, phone), created only after OTP proof (`models/customer.py`); erasure rewrites `phone` to `erased:{id}` (F20).
- **Bookings**: `customer_id` NOT NULL; statuses `confirmed/cancelled/no_show/completed/pending_payment`; `attendance_confirmed_at`, `cancelled_at`, `cancelled_by` exist. Duration lives on `appointment_types.duration_minutes` (bookings have no end time).
- **Tokenized manage page**: `ManageBookingService.lookup/confirm_attendance/cancel` (`booking/manage.py`) with guards (`BookingLinkInvalidError`, `BookingAlreadyStartedError`, `BookingCancelledError`, `BookingAwaitingPaymentError`) and the `ManageBookingResponse` wire shape (booking facts + policy + boutique). Tokens ride POST bodies, **never URLs** (F14 D7 — logs must not see capabilities).
- **Bell substrate candidates**: `message_log` (kinds `otp/confirmation/reminder/owner_cancel/owner_reschedule/payment_received_no_slot`, `booking_id` populated since F16, `status` sent/failed, retained 24 months) and `scheduled_messages` (schedule state only, purged with its booking). Verified: message_log is the only table that records what was actually told to her.
- **Sessions (staff)**: `sessions` table (staff_user_id NOT NULL) + `boutique_session` cookie — host-only, HttpOnly, SameSite=Lax, `session_ttl_seconds` = 12h (`auth/cookies.py`, `core/config.py`). The dependency pattern is `get_current_staff` reading the cookie.
- **No customer session exists anywhere today** — the portal introduces the first one.
- **No calendar code exists** (grepped `\.ics|text/calendar|VEVENT` — only node_modules type unions).
- **Storefront SPA**: hand-rolled router (`src/router.tsx`) — exact-literal routes + regex paths; `RouteName "manage"` is **taken** (the `/b/{token}` page). i18n groups live under `translation.{booking,manage,checkin,...}` in `he.ts`/`ar.ts`. Vite proxies only `/storefront` and `/health`. `main.py` `_RESERVED_SEGMENTS = {manage, storefront}`.
- **PPL (F20)**: subject export/erase are **owner-console** endpoints (`/manage/privacy/subject-*`, OWNER_ONLY). `/privacy` public notice page shipped.
- **Migrations**: 0001–0025 merged; **F22 is building on 0026 in a parallel worktree** — F24 numbers its migration **head+1 at build time** (parallel-alembic-numbering rule).

## Scope

**IN**
- Customer session: `customer_sessions` table, cookie, login (OTP) / logout, TTL.
- Portal page on the storefront SPA (`/portal`): login panel → "My Bookings" dashboard.
- Booking list + detail; mirrored confirm-attendance and cancel actions (session-authed, same transition rules as the tokenized page).
- Per-booking `.ics` download — from the portal **and** from the tokenized `/b/{token}` page.
- Notification bell on the portal: badge + list, mark-seen, page-open refresh only.
- Erase integration: F20 subject-erase revokes the customer's portal sessions.

**OUT**
- Email login, passwords, social login (pre-decided #17).
- 2-way Google/Apple calendar sync (#17 — `.ics` download is the recorded replacement).
- Push or polling bell, realtime substrate of any kind (#18).
- Customer profile editing (name/phone edits stay owner-side, F15/F53).
- Multi-fitting dashboards (E9 — builds on this feature later).
- Replacing the tokenized link — `/b/{token}` remains fully valid for non-login users.
- Self-service subject export/erase from the portal (the DSR flow stays owner-mediated, see §PPL).
- Waitlist surfaces (F22/F23 own those).

## Design

### D1 — Identity: the session binds to a `customers` row, minted only after OTP proof

Login flow reuses the booking flow's exact three steps: `POST /storefront/otp/send` → `POST /storefront/otp/verify` → a **new** `POST /storefront/portal/session {phone, verification_token}` that calls `consume_verification` (single-use burn, same as `create_booking`) and then resolves the customer by (tenant, normalized phone).

- **Customer exists** → insert `customer_sessions` row (token via `generate_session_token`, sha256-stored), set cookie, return `{customer_name}`.
- **No customer row** → `404 {code: PORTAL_NO_BOOKINGS}`. Not an oracle: she just proved possession of the phone, so "this number has no bookings here" discloses only her own data. The login page renders a friendly state pointing at the catalog. An **erased** customer's phone is `erased:{id}` and can never match — same path, by construction.
- Login never creates a customer (`customers.name` is NOT NULL and only a booking supplies a name).

### D2 — Session mechanics

- **New table `customer_sessions`** (never widen `sessions` — `staff_user_id` is NOT NULL there, and staff/customer auth must not share a lookup path): standard columns + `tenant_id`, `customer_id`, `token_hash`, `expires_at`. Partial index `(tenant_id, token_hash) WHERE deleted_at IS NULL`. RLS via `enable_tenant_rls`, house grants.
- **Cookie `boutique_customer_session`** — a *different name* from the staff `boutique_session` (both apps live on the same tenant host; one name would let a staff login clobber a customer session and vice versa). Same attributes: host-only (no Domain → tenant-isolated at the cookie layer), HttpOnly, Secure (prod), SameSite=Lax, path=/.
- **TTL**: new setting `portal_session_ttl_seconds`, default 30 days. Deliberately longer than the staff 12h: every re-login costs the tenant a real SMS, so a short TTL is a recurring bill and a worse product. Fixed expiry, **no sliding renewal** (renewal is a write per read; re-login is one OTP). Recorded tension with pre-decided #10 ("sessions at existing TTL"): #10 fixed retention *classes* as tunable settings and this is a new class with its own tunable — flagged for the counsel pass like the rest of #10.
- **Logout**: `POST /storefront/portal/logout` soft-deletes the row, clears the cookie.
- **Auth dependency**: `get_current_customer` mirroring `get_current_staff` — cookie → hash → live row (`deleted_at IS NULL`, `expires_at > now()`) → `CustomerContext(customer_id, name, phone)`; raises the existing `NotAuthenticatedError` (401 house body).
- **Erase integration**: F20's `subject_erase` gains one step — soft-delete all `customer_sessions` for the erased customer, in the same transaction. An erased subject with a live session would otherwise keep reading her "gone" record for up to 30 days.

### D3 — Rate limits (recorded per the per-instance rule)

- **OTP send/verify budgets are SHARED with the booking flow — deliberately.** The portal calls the *same* endpoints, same `OtpService`, same limiter instances, same keys (`otp:phone:{tenant}:{phone}`, `otp:tenant:{tenant}`, `otp:verify:…`). The metered resource is the SMS spend and the guess surface, identical whichever flow asks; the same person logging in and booking is one actor on one phone. The **F21 per-IP arm is inherited automatically** and stays inert until `trust_forwarded_for` (F62's parked concern) — no new code, recorded as unchanged.
- **One NEW limiter instance** for `POST /storefront/portal/session`, per-tenant key — **its own `FixedWindowRateLimiter`, never a key on an existing budget** (`max_attempts` lives on the instance; the rule main.py states five times). It brakes anonymous DB-write floods on the mint path. Settings: `portal_login_max_per_tenant_window` / `portal_login_window_seconds`.
- No limiter on the cookie-authed reads: they cost one indexed query and require a live session; the anonymous storefront read brake is not shared onto them.

### D4 — "My Bookings" and mirrored actions

- `GET /storefront/portal/me` → `{customer_name}` (the SPA's session bootstrap; 401 renders the login panel).
- `GET /storefront/portal/bookings` → `{upcoming: [PortalBookingRow], past: [PortalBookingRow]}` — her bookings only (`customer_id` from the session), split on `starts_at` vs now, upcoming ASC / past DESC. Row = `id, starts_at, status, attendance_confirmed_at, appointment_type_name, dress_name, dress_size`. `pending_payment` rows appear in upcoming with their status — the seat is hers, the money is not in.
- `GET /storefront/portal/booking?id={uuid}` → the **existing `ManageBookingResponse` shape verbatim** (booking facts + policy-from-accepted-version + boutique). Resolution by (session customer_id, id) instead of token; unknown or not-hers → the house 404 body (no cross-customer existence oracle). Reusing the shape is the mirror guarantee: the portal detail and the tokenized page render from the same contract.
- `POST /storefront/portal/booking/confirm-attendance {id}` and `POST /storefront/portal/booking/cancel {id}` — delegate to the **same transition code** `ManageBookingService` uses (extract the token-resolution from the transition so both callers share one guard set; the plan owns the refactor shape). Same 409s (`BOOKING_ALREADY_STARTED`, `BOOKING_CANCELLED`, `BOOKING_AWAITING_PAYMENT`), same seat-freeing semantics, `cancelled_by='customer'`, same reminder-row cancellation. CSRF: covered by `CsrfOriginMiddleware` + SameSite=Lax, like every shipped POST.
- The tokenized `/b/{token}` page and its endpoints are **untouched**.

### D5 — `.ics` contract

- **Builder**: new pure module `app/booking/ics.py`, stdlib only (datetime + string assembly — no dependency). One VEVENT per file, CRLF line endings, lines folded at 75 octets:
  - `UID:{booking_id}@{slug}.{base_domain}` · `DTSTAMP` (now, UTC)
  - `DTSTART`/`DTEND` as **UTC instants (`…Z`)** — no VTIMEZONE block. An absolute instant is DST-proof and every calendar client renders it in local (Asia/Jerusalem) wall-clock. `DTEND = starts_at + appointment_types.duration_minutes`, read from the type row regardless of its `deleted_at` (soft-deleted types keep their duration; no fallback constant needed).
  - `SUMMARY:{appointment_type_name} — {boutique name}` (Hebrew, UTF-8) · `LOCATION:{address}` when present · `STATUS:CONFIRMED`
  - **No manage token anywhere in the file body** — `.ics` files get forwarded and synced to shared calendars; a capability inside one leaks control of the booking.
- **Delivery, two thin routes, one builder**:
  - Portal: `GET /storefront/portal/booking.ics?id={uuid}` — cookie-authed, booking id is not a secret so a plain GET download link works natively (matters on iOS, where a direct `text/calendar` response opens the add-to-calendar sheet). `Content-Type: text/calendar; charset=utf-8`, `Content-Disposition: attachment; filename="appointment.ics"` (ASCII filename — Hebrew filenames in that header are an encoding tarpit).
  - Tokenized page: `POST /storefront/booking/ics {token}` → same body; the SPA downloads via blob URL. POST because **tokens never ride URLs** (F14 D7 — access logs).
- Only `confirmed` (and `completed`) bookings serve a file; cancelled/pending_payment answer the transition-appropriate 409/404 the manage page already defines.

### D6 — The bell: a projection over `message_log`, one new column, no new table

The bell answers "what has the boutique told me" — and `message_log` already *is* that, with `booking_id` populated since F16. Cheapest honest design consistent with #18:

- `GET /storefront/portal/bell` → `{unread_count, items: [{id, kind, created_at, booking_id, starts_at, appointment_type_name}]}`:
  - rows from `message_log` where `booking_id` belongs to one of **her** bookings, `kind != 'otp'`, `status = 'sent'` (a failed send never reached her; the bell mirrors her inbox, not our attempts), joined to `bookings` for `starts_at` / type name; `created_at DESC`, cap 20, no pagination (message_log's 24-month retention bounds the window naturally).
  - The client renders each item from `kind` + booking facts via i18n — **never from `message_log.body`** (bodies store masked tokens as `●●●` by design; they are evidence, not UI copy). Kinds rendered: `confirmation`, `reminder`, `owner_cancel`, `owner_reschedule`, `payment_received_no_slot`.
- **Badge count** = rows newer than `customers.bell_seen_at` (new nullable TIMESTAMPTZ column; NULL = never opened = all unread). Displayed capped at "9+".
- **Mark-read**: `POST /storefront/portal/bell/seen` sets `bell_seen_at = now()`; the SPA calls it when the bell list is opened. No per-item read state — one timestamp is the whole model (ponytail ceiling: per-item read rows if the pilot ever asks; nothing in the PRD does).
- **Liveness**: fetched once when the portal mounts (page open/reload). No interval, no focus-refetch, no websocket — pre-decided #18 verbatim. The bell lives **on the portal page only** (not the storefront-wide layout): a bell for anonymous visitors would need a session probe on every catalog view, and HttpOnly means the SPA cannot even see whether a cookie exists without one.
- On unconfigured-SMS deployments message_log is evidence-free by F11's design → the bell is honestly empty; with the fake sender (dev/e2e) and Twilio (prod) rows exist.

### D7 — Data model changes (one migration, head+1 at build time)

Raw-SQL migration in the house style (`_STANDARD` block, `updated_at` trigger, grants, `enable_tenant_rls`), numbered **head+1 when the build branch cuts** (F22 holds 0026 in a parallel worktree — renumber at rebase, never squat a taken number):

```sql
CREATE TABLE customer_sessions (
  -- _STANDARD: id uuid_generate_v4() PK, tenant_id, created_at, updated_at, deleted_at
  customer_id  UUID NOT NULL,          -- no FK, house rule; validated in app
  token_hash   TEXT NOT NULL,
  expires_at   TIMESTAMPTZ NOT NULL
);
CREATE INDEX idx_customer_sessions_token ON customer_sessions (tenant_id, token_hash)
  WHERE deleted_at IS NULL;
CREATE INDEX idx_customer_sessions_customer ON customer_sessions (tenant_id, customer_id)
  WHERE deleted_at IS NULL;            -- the erase-revocation path
-- RLS + grants exactly as sessions has them.

ALTER TABLE customers ADD COLUMN bell_seen_at TIMESTAMPTZ;  -- NULL = never opened the bell
```

No changes to `message_log`, `scheduled_messages`, or `bookings`.

### D8 — Frontend changes (Frontend/apps/storefront unless rooted)

- **Router** (`src/router.tsx`): exact literal `/portal` → `RouteName "portal"` (the name `manage` is taken by `/b/{token}` — verified; no `portal`/`account` collisions in src). `DOC_TITLE_KEYS.portal = "document.portal"`. Remember the switch-case trap the router file documents: add the `case` AND the router.test.tsx render-pair assertion.
- **New route component** `src/routes/PortalPage.tsx`: bootstraps on `api.portalMe()`; 401 → login panel, 200 → dashboard.
- **New components** `src/components/portal/`: `PortalLogin.tsx` (phone → code, reusing the booking verify step's field/error patterns and the shared OTP endpoints), `PortalBookingList.tsx`, `PortalBookingDetail.tsx` (renders the `ManageBookingResponse` shape — extract/reuse the fact-list and cancel-confirm pieces of `ManageBookingPage.tsx` rather than forking them; the plan owns the extraction), `PortalBell.tsx` (button + badge + list).
- **`src/api.ts`**: `portalMe`, `portalLogin`, `portalLogout`, `portalBookings`, `portalBooking`, `portalConfirmAttendance`, `portalCancel`, `portalBell`, `portalBellSeen`, `portalIcsUrl(id)` (href for the GET download), `manageIcs(token)` (POST + blob download helper). House `ApiError`/`errorMessageKey` handling; new error codes mapped: `PORTAL_NO_BOOKINGS`.
- **i18n** (`src/i18n/he.ts` + `ar.ts`, ar untranslated per Q3/#47): new `document.portal` and a `portal` group — `login.*` (title, phone label, code label, send, verify, noBookings state), `bookings.*` (title, upcoming, past, empty, statusLabels reusing manage vocabulary), `bell.*` (label, empty, one body key per rendered kind), `ics.*` (download label), `logout`. **Zero exclamation marks** (pre-decided #5 register); reuse the approved manage-page Hebrew vocabulary for booking facts verbatim where the same fact is shown.
- **No `/manage` app changes** → no manage e2e harness (walker) registration, no manage nav rows.
- **No vite proxy change and no `_RESERVED_SEGMENTS` change**: every new endpoint lives under the existing `/storefront` prefix — do not invent a new top-level API family (trap recorded; a `/portal` API prefix would need vite proxy + SPA-fallback + CSRF review for zero benefit). The SPA route `/portal` is served by the existing catch-all.

## API summary (all under the existing `/storefront` prefix, `_no_store` like siblings)

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /storefront/portal/session` | verification_token | mint session (new per-tenant limiter) |
| `POST /storefront/portal/logout` | cookie | revoke session |
| `GET /storefront/portal/me` | cookie | session bootstrap → `{customer_name}` |
| `GET /storefront/portal/bookings` | cookie | upcoming + past rows |
| `GET /storefront/portal/booking?id=` | cookie | `ManageBookingResponse` shape |
| `POST /storefront/portal/booking/confirm-attendance` | cookie | mirrors tokenized action |
| `POST /storefront/portal/booking/cancel` | cookie | mirrors tokenized action |
| `GET /storefront/portal/booking.ics?id=` | cookie | `.ics` download |
| `POST /storefront/booking/ics` | manage token (body) | `.ics` for the tokenized page |
| `GET /storefront/portal/bell` | cookie | items + unread_count |
| `POST /storefront/portal/bell/seen` | cookie | stamp `bell_seen_at` |

OTP send/verify: existing endpoints, unchanged.

## Security model (named)

Possession-of-phone is the identity (Q11 gave staff the same model). Session token ≥128-bit, sha256-stored, single cookie: HttpOnly (no JS theft), host-only (no cross-subdomain replay), SameSite=Lax + `CsrfOriginMiddleware` (CSRF), Secure in prod. RLS isolates `customer_sessions` per tenant; every portal query additionally filters `customer_id` from the session. Cross-customer probes answer the house 404 (no oracle). Erase revokes sessions in-transaction. The `.ics` carries no capability. Manage tokens continue to never appear in URLs.

## PPL relation (F20)

The portal is a **subject-access surface**: she sees her own bookings and message history by logging in. It does **not** replace the DSR flow — subject export and erase remain owner-mediated console actions (`/manage/privacy/subject-*`, shipped), and the public `/privacy` notice is untouched. One F20 integration only: erase revokes portal sessions (D2).

## Test plan

- **Fast lane (unit)**: `ics.py` builder — UTC `Z` formatting, DTEND arithmetic, an IDT (summer) and an IST (winter) booking, CRLF + folding, no token in output; portal login service with repository fakes (customer found / not found / erased); bell item shaping.
- **db-marked**: RLS isolation on `customer_sessions` (tenant A cannot read B's — house suite pattern); mint→me→logout lifecycle; expiry honored; verification token burned single-use; `PORTAL_NO_BOOKINGS` on unknown phone; bookings list scoped to the session's customer only; portal cancel frees the seat + cancels the pending reminder + stamps `cancelled_by='customer'` (same assertions as the token-page cancel suite); confirm-attendance writes `attendance_confirmed_at`; 409 matrix (started / cancelled / awaiting payment) via the shared transition code; bell projection — OTP and failed rows excluded, only her bookings' rows, unread vs `bell_seen_at`, seen-stamp; subject-erase revokes sessions; mint limiter 429.
- **API auth matrix**: every portal route 401 without cookie; cross-customer id 404; `.ics` content-type + disposition; token-body ics with rotated token → `BOOKING_LINK_INVALID`.
- **e2e (Playwright + axe, `Frontend/e2e/portal.spec.ts`)**: local interception fixtures in the `storefront.spec.ts` style (extend its route map with the portal endpoints — the harness stubs the API and proves the journey, not the contract): login journey phone→code→dashboard; empty and populated bookings; cancel dialog flow (red button on final confirm only, per the manage-page precedent); bell badge shown → open → seen POST → badge cleared; `.ics` download triggered; `PORTAL_NO_BOOKINGS` state; **axe zero-violation** on login, dashboard, detail, bell open, cancel dialog; RTL rendering; focus lands on `#content` after navigation (router contract).

## Traps (for the plan)

- Migration number is **head+1 at build time**; F22 holds 0026 in a live worktree — renumber at rebase (`.memory/parallel-alembic-numbering`).
- `git add` pathspecs lowercase (`backend/…`), reads capitalized (`Backend/…`).
- Router switch fallthrough: a missing `case "portal"` renders the catalog under the portal title and stays green — add the render-pair test first.
- Limiter instances: never key the mint brake onto an existing budget.
- Do not read `message_log.body` for UI — masked tokens (`●●●`) live there.
- The e2e interception harness proves the console, not the contract — the db-marked API tests are the contract side; keep both.

## Decisions log

| # | Decision | Basis |
|---|---|---|
| D1 | Session binds to existing `customers` row; login never creates one | `bookings.customer_id` NOT NULL; name only exists via booking |
| D2 | New `customer_sessions` table + `boutique_customer_session` cookie, 30-day fixed TTL, no sliding renewal | staff table/cookie unshareable; re-login costs tenant SMS money |
| D3 | OTP budgets shared with booking flow; one new per-tenant mint limiter; F21 IP arm inherited (inert) | metered resource is the SMS itself; per-instance limiter rule |
| D4 | Portal detail/actions reuse `ManageBookingResponse` + `ManageBookingService` transitions; tokenized page untouched | the mirror is a shared contract, not a copy |
| D5 | `.ics`: stdlib, UTC instants, no VTIMEZONE, no token in file; GET for portal, POST-body for token page | DST-proof; capabilities never in URLs or shareable files |
| D6 | Bell = projection over `message_log` (sent, non-OTP, her bookings) + one `customers.bell_seen_at` column; page-open fetch only; portal-page-only | cheapest honest substrate that already exists; pre-decided #18 |
| D7 | All endpoints under `/storefront` prefix | zero vite/CSP/fallback changes |
| D8 | SPA route `/portal`, RouteName `portal` | `manage` name taken by `/b/{token}` |

## Open questions (non-blocking)

- Portal session TTL (30d) vs pre-decided #10's "sessions at existing TTL" — shipped as its own tunable setting, flagged for the counsel/retention pass alongside #10's numbers.
- Whether the bell should also surface waitlist-offer messages once F23 ships — F23's spec owns widening the rendered-kind list.
