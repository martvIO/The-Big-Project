# Epic: E3 — Booking Engine & SMS Lifecycle

**Created**: 2026-07-21 (rev 2 — post verification pass)
**Status**: in progress — #11–#14 are merged (PRs #16–#19), so the customer-facing half is live end to end: a bride browses, verifies her phone by OTP, accepts the versioned terms and claims a real slot on both paths, oversell-proof, in Hebrew RTL. #14 shipped with its backend amendment (`GET /storefront/terms`) and closed out through dual review plus a CI-only test race fixed post-review (the OTP cooldown's effect-scheduled timer vs. `advanceTimersByTime` — `passCooldown()` in the test file records the mechanism). #15 (owner management) and #16 (comms lifecycle) remain; **#16 is spec'd next** — see the paragraph below for why it cannot slip.

**#14's design gate and implementation plan were both drafted on 2026-07-29** (`.planning/design/screens/booking/` and `.planning/plans/storefront-booking-ui.md`), and **the gate was signed off the same day**: `copy.md` is APPROVED end to end (rev 3, 61 rows — two keys added at sign-off: `confirmTitleNamed`, `sizeUnavailableNote`), P1–P8 are all confirmed, and §7's questions are answered (Q3/Q5 closed by code evidence). **The build is unblocked.** The gate also produced amendments this epic's other features inherit — see the design doc's ⚠ FINDINGs, which include one row the spec's State matrix is missing, four i18n keys its inventory lacks, a `packages/ui` gate condition (`Input`/`TextArea`/`Select` expose no `ref`, so focus-to-first-invalid is currently unbuildable), and a pre-existing `StorefrontLayout` defect that is escalated rather than fixed here.

**A booking now sends nothing — and the flow that lets a real customer create one is merged.** #13 shipped the row; every SMS lives in #16. The ordering was harmless while nothing linked to the endpoint; #14's merge ended that, which makes #16 the epic's most urgent remaining feature and is why it must not slip behind #15. #14's D6 anticipated exactly this window: the confirmation screen carries the whole promise and says nothing about a text that will not arrive. One string on that screen changes when #16 lands.

External lead-time items that gate E3 remain user-owned: Israeli SMS sender-ID registration (#11) and the Grow merchant account (E4 #17).
**Owner**: team
**PRD**: §4 (dual booking paths, terms acceptance), §6 (confirmation + 24h reminder; waitlist loop deferred to E5)

---

## Why

This is the product's transactional core: turn the browse-only storefront into a boutique that takes real appointments, concurrency-safe, with the SMS lifecycle that fights no-shows. Verification pass added the blocker fix — **one-shot OTP phone verification inside the booking flow** (the tokenized SMS link is the customer's only control surface in v1; an unverified number strands paid customers and creates Spam-Law liability) — plus owner reschedule, owner-change SMS triggers, and the manage/cancel link in the *immediate* confirmation (waiting for the 24h reminder would put the link after most refund windows close). Deposits bolt onto this flow in E4.

---

## Success Criteria

- [ ] A customer completes both booking paths (item-based with dress metadata bound; generic) **after verifying their phone via one-shot OTP** and accepting the versioned terms — and a double-book of the same slot is structurally impossible (partial unique index proven by a concurrency test)
- [ ] The immediate confirmation SMS contains date/time, a Waze/Maps deep link, **and the tokenized manage/cancel link**; the 24h reminder lands with confirm/cancel; bookings made <24h out are handled sanely; **owner-initiated cancel/reschedule triggers a customer SMS including the refund/forfeit outcome**
- [ ] Owner sees and manages all bookings (list + day filter: confirm / cancel / **reschedule** / no-show / complete), can fix a customer's phone and resend the link; reminder-link "confirm" sets a visible `attendance_confirmed_at`

---

## Features

| # | Feature | Status | Spec | Plan | Depends On |
|---|---------|--------|------|------|------------|
| 11 | SMS foundation | **done** (PR #16) | [spec](../specs/sms-foundation.md) | [plan](../plans/sms-foundation.md) | E1 #2, #3 |
| 12 | Availability & slot engine | **done** (PR #17) | [spec](../specs/availability-slot-engine.md) | [plan](../plans/availability-slot-engine.md) | E2 #7 |
| 13 | Booking core API | **done** (PR #18) | [spec](../specs/booking-core.md) | [plan](../plans/booking-core.md) | E2 #7, #11, #12 |
| 14 | Storefront booking UI | **done** (PR #19) | [spec](../specs/storefront-booking-ui.md) · [design](../design/screens/booking/booking.md) · [copy](../design/screens/booking/copy.md) | [plan](../plans/storefront-booking-ui.md) | E2 #9, #10 · #11, #12, #13 |
| 15 | Owner booking management | **spec'd** — Gate 1 self-approved 2026-07-30, building | [spec](../specs/owner-booking-management.md) | — | #12, #13, #16 |
| 16 | Booking comms lifecycle | done (PR #21) | `booking-comms.md` | `booking-comms.md` | #13 |

**Remaining order is #14 → #16 → #15, and the ordering is deliberate.** #16 is sequenced ahead of #15 because the day #14 merges, a real customer completes a booking and hears silence — that is a customer-facing hole, where #15's absence is only an owner inconvenience the owner can work around by reading the database or phoning the bride back. #14's D6 makes the confirmation screen carry the whole promise in the meantime, and one string on it changes when #16 lands.

---

## Feature Briefs

### Feature 11: SMS foundation (M)
`NotificationService` abstraction + the provider implementation chosen in E1 #2 (sender-ID registration already filed there). Tenant-scoped `message_log` for every send (Spam-Law evidence). **OTP send/verify primitive** (rate-limited per phone + per IP, ≤5-min expiry, single-use) — consumed by Feature 13's booking flow now and E5's client login later. Transactional-only; zero marketing content.

### Feature 12: Availability & slot engine (M)
Materialize bookable slots from `availability_rules` + exceptions + appointment-type durations, respecting the Israeli week and per-type audience (brides-only). Slots carry capacity and status. Pure-domain logic with heavy unit tests (holiday edges, DST, rule changes with existing bookings).

### Feature 13: Booking core API (L)
Backend only (UI is Feature 14). Both PRD paths: item-based (binds dress ID/name/size/image snapshot) and generic. **Customer record created/attached by (tenant, phone) only after OTP verification proves possession of the number.** Forced terms acceptance captures `terms_version_accepted` + timestamp. Concurrency safety: conditional slot update + partial unique index on active bookings per slot. Statuses: confirmed/cancelled/no_show/completed plus `attendance_confirmed_at` (set by the reminder link's confirm action); `pending_payment` added by E4.

### Feature 14: Storefront booking UI (L — revised up from M at Gate 1)
The customer-facing flow for both paths on the storefront. **Gate 1 (2026-07-29) settled its shape**: a `/book` **route** (not a modal behind the shipped CTA), stepped slot → details → terms → **OTP last** so the 600-second verification token cannot expire mid-policy, then the confirmation screen. It also carries a backend amendment — `GET /storefront/terms`, because `POST /storefront/bookings` requires a `terms_version` an anonymous bride has no public way to learn — which is what moved the estimate M → L. Luxury RTL per the Feature 9 system. Deposit-required appointment types show but book by phone until E4; when E4 lands, the deposit redirect inserts between OTP and confirmation without UI restructuring.

### Feature 15: Owner booking management (L — revised up from M at Gate 1)
`apps/manage` booking list + day filter (calendar visualization deferred to E10 — the list covers the operational need at pilot volume). Status transitions with audit log; booking detail incl. dress snapshot and accepted-terms version. **Owner reschedule: move a booking to a new slot — deposit (once E4 exists) carries over, no re-payment round-trip.** Remedy path: edit customer phone (re-verify or owner-attested) + resend confirmation/token SMS. No real-time board — refresh/poll acceptable until E6.

### Feature 16: Booking comms lifecycle (M)
All lifecycle sends on top of Feature 11: immediate confirmation (date, time, maps deep link, **manage/cancel link**), owner-cancel and owner-reschedule notifications (with refund/forfeit outcome once E4 exists), `scheduled_messages` + worker poller (`send_after`, `FOR UPDATE SKIP LOCKED`, idempotency keys) for the 24h reminder, and the tokenized confirm/cancel page: ≥128-bit single-purpose token stored hashed, expires at appointment time, idempotent; "confirm" writes `attendance_confirmed_at`. Bookings <24h out: reminder sent immediately, suppressed under 2h (final rule at spec).

---

## Risks

- ~~The slot capacity model has open product questions~~ — **resolved 2026-07-28**: a slot is a START TIME (no duration, no end time, no overlap arithmetic), and `availability_rules.capacity` is how many bookings may share one. F12's spec records the model; F13 enforces it with a per-tenant advisory lock plus a `seat_index` unique index, structural at any capacity.
- OTP adds SMS cost + a friction step to every booking — measured, it's the price of the tokenized-link security model; revisit only if pilot data shows abandonment.

## Notes

- Waitlist join + auto-reallocation is deliberately **not** here (E5 #22–23): it needs the booking core live first; the race-safe offer/claim design is already spec'd in the pressure-test plan.
