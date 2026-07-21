# Epic: E3 — Booking Engine & SMS Lifecycle

**Created**: 2026-07-21 (rev 2 — post verification pass)
**Status**: planning
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
| 11 | SMS foundation | todo | — | — | E1 #2, #3 |
| 12 | Availability & slot engine | todo | — | — | E2 #7 |
| 13 | Booking core API | todo | — | — | E2 #7, #11, #12 |
| 14 | Storefront booking UI | todo | — | — | E2 #10, #13 |
| 15 | Owner booking management | todo | — | — | #13 |
| 16 | Booking comms lifecycle | todo | — | — | #13 |

---

## Feature Briefs

### Feature 11: SMS foundation (M)
`NotificationService` abstraction + the provider implementation chosen in E1 #2 (sender-ID registration already filed there). Tenant-scoped `message_log` for every send (Spam-Law evidence). **OTP send/verify primitive** (rate-limited per phone + per IP, ≤5-min expiry, single-use) — consumed by Feature 13's booking flow now and E5's client login later. Transactional-only; zero marketing content.

### Feature 12: Availability & slot engine (M)
Materialize bookable slots from `availability_rules` + exceptions + appointment-type durations, respecting the Israeli week and per-type audience (brides-only). Slots carry capacity and status. Pure-domain logic with heavy unit tests (holiday edges, DST, rule changes with existing bookings).

### Feature 13: Booking core API (L)
Backend only (UI is Feature 14). Both PRD paths: item-based (binds dress ID/name/size/image snapshot) and generic. **Customer record created/attached by (tenant, phone) only after OTP verification proves possession of the number.** Forced terms acceptance captures `terms_version_accepted` + timestamp. Concurrency safety: conditional slot update + partial unique index on active bookings per slot. Statuses: confirmed/cancelled/no_show/completed plus `attendance_confirmed_at` (set by the reminder link's confirm action); `pending_payment` added by E4.

### Feature 14: Storefront booking UI (M)
The customer-facing flow for both paths on the storefront: slot picker, details + OTP verification step, terms checkbox, confirmation screen. Luxury RTL per the Feature 9 system. When E4 lands, the deposit redirect inserts between OTP and confirmation without UI restructuring.

### Feature 15: Owner booking management (M)
`apps/manage` booking list + day filter (calendar visualization deferred to E10 — the list covers the operational need at pilot volume). Status transitions with audit log; booking detail incl. dress snapshot and accepted-terms version. **Owner reschedule: move a booking to a new slot — deposit (once E4 exists) carries over, no re-payment round-trip.** Remedy path: edit customer phone (re-verify or owner-attested) + resend confirmation/token SMS. No real-time board — refresh/poll acceptable until E6.

### Feature 16: Booking comms lifecycle (M)
All lifecycle sends on top of Feature 11: immediate confirmation (date, time, maps deep link, **manage/cancel link**), owner-cancel and owner-reschedule notifications (with refund/forfeit outcome once E4 exists), `scheduled_messages` + worker poller (`send_after`, `FOR UPDATE SKIP LOCKED`, idempotency keys) for the 24h reminder, and the tokenized confirm/cancel page: ≥128-bit single-purpose token stored hashed, expires at appointment time, idempotent; "confirm" writes `attendance_confirmed_at`. Bookings <24h out: reminder sent immediately, suppressed under 2h (final rule at spec).

---

## Risks

- The slot capacity model has open product questions (parallel appointments? fitting-room count?) — resolve with the pilot boutique **before** Feature 12's spec.
- OTP adds SMS cost + a friction step to every booking — measured, it's the price of the tokenized-link security model; revisit only if pilot data shows abandonment.

## Notes

- Waitlist join + auto-reallocation is deliberately **not** here (E5 #1–2): it needs the booking core live first; the race-safe offer/claim design is already spec'd in the pressure-test plan.
