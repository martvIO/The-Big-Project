# Epic: E3 — Booking Engine & SMS Lifecycle

**Created**: 2026-07-21 (rev 2 — post verification pass)
**Status**: in progress — #11, #12 and #13 are merged (PRs #16, #17, #18), so the booking *engine* is done: a verified phone can claim a real slot, oversell-proof, and the public grid reports true availability. One backend gap blocks **#14** and it carries it — `GET /storefront/terms`, the public read an anonymous customer needs before she can send a `terms_version` at all, which is what moved #14 from M to L. (#15 and #16 carry substantial backend work of their own — see their briefs.) #14 (UI), #15 (owner management) and #16 (comms lifecycle) remain, and all three are now unblocked. **#14 passed Gate 1 on 2026-07-29** — its seven open questions are answered as D1–D7 in the spec, plus D8–D9 confirmed with the user post-gate and D10–D12 recording choices the shipped code had already forced; a design gate (`.planning/design/screens/booking/`) and an implementation plan are the next two steps before build.

**A booking currently sends nothing.** #13 shipped the row; every SMS lives in #16. That ordering was harmless only while nothing linked to the endpoint — **#14 ends that**: the moment it merges, a real customer completes a booking and hears silence. It is why #14's D6 makes the confirmation screen carry the whole promise (and say nothing about a text that will not arrive), and why #16 must not slip behind #15. One string on that screen changes when #16 lands.

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
| 14 | Storefront booking UI | Gate 1 approved — design gate + plan outstanding | [spec](../specs/storefront-booking-ui.md) | — | E2 #9, #10 · #11, #12, #13 |
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

### Feature 14: Storefront booking UI (L — revised up from M at Gate 1)
The customer-facing flow for both paths on the storefront. **Gate 1 (2026-07-29) settled its shape**: a `/book` **route** (not a modal behind the shipped CTA), stepped slot → details → terms → **OTP last** so the 600-second verification token cannot expire mid-policy, then the confirmation screen. It also carries a backend amendment — `GET /storefront/terms`, because `POST /storefront/bookings` requires a `terms_version` an anonymous bride has no public way to learn — which is what moved the estimate M → L. Luxury RTL per the Feature 9 system. Deposit-required appointment types show but book by phone until E4; when E4 lands, the deposit redirect inserts between OTP and confirmation without UI restructuring.

### Feature 15: Owner booking management (M)
`apps/manage` booking list + day filter (calendar visualization deferred to E10 — the list covers the operational need at pilot volume). Status transitions with audit log; booking detail incl. dress snapshot and accepted-terms version. **Owner reschedule: move a booking to a new slot — deposit (once E4 exists) carries over, no re-payment round-trip.** Remedy path: edit customer phone (re-verify or owner-attested) + resend confirmation/token SMS. No real-time board — refresh/poll acceptable until E6.

### Feature 16: Booking comms lifecycle (M)
All lifecycle sends on top of Feature 11: immediate confirmation (date, time, maps deep link, **manage/cancel link**), owner-cancel and owner-reschedule notifications (with refund/forfeit outcome once E4 exists), `scheduled_messages` + worker poller (`send_after`, `FOR UPDATE SKIP LOCKED`, idempotency keys) for the 24h reminder, and the tokenized confirm/cancel page: ≥128-bit single-purpose token stored hashed, expires at appointment time, idempotent; "confirm" writes `attendance_confirmed_at`. Bookings <24h out: reminder sent immediately, suppressed under 2h (final rule at spec).

---

## Risks

- ~~The slot capacity model has open product questions~~ — **resolved 2026-07-28**: a slot is a START TIME (no duration, no end time, no overlap arithmetic), and `availability_rules.capacity` is how many bookings may share one. F12's spec records the model; F13 enforces it with a per-tenant advisory lock plus a `seat_index` unique index, structural at any capacity.
- OTP adds SMS cost + a friction step to every booking — measured, it's the price of the tokenized-link security model; revisit only if pilot data shows abandonment.

## Notes

- Waitlist join + auto-reallocation is deliberately **not** here (E5 #1–2): it needs the booking core live first; the race-safe offer/claim design is already spec'd in the pressure-test plan.
