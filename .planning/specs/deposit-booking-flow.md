# Spec: Feature 19 — Deposit booking flow (Epic E4)

**Created**: 2026-07-31 · **Status**: Gate 1 pre-authorized by the user (2026-07-31) — the money-behaviour questions were ruled at F17's gate; this spec records them, decides what they left open, and builds · **Epic**: E4 · **Effort**: **L**
**Depends on**: F17 (port, credential service, `PaymentService`, migration 0012), F13 (slot claim), F16 (confirmation SMS), F14 (storefront booking UI) · **Feeds**: F21 (hardening/UAT), F29 (refunds)

---

## Problem

The product has promised a deposit since F7 and has never taken one. `deposits_enabled` shipped with zero readers; `appointment_types.deposit_required` and `deposit_amount_agorot` ship with DB CHECKs and are already disclosed to anonymous visitors. F17 built the machinery to hold and settle money and deliberately stopped short of touching `bookings` — its `settle_from_webhook` docstring says so outright: *"Flipping a booking to confirmed and firing F16's confirmation SMS is F19's transaction."*

So today a bride books a deposit-required appointment and pays nothing, and the boutique discovers it at the door.

## Goal

A bride picks a slot for a deposit-required appointment type, is sent to the provider's hosted page, pays, and comes back to a confirmed booking with the F16 confirmation SMS already sent. If she abandons the page, the seat frees itself and someone else can take it. If her card is declined, the seat frees itself too and no SMS is sent. If her payment lands late — after the seat was freed — the money is honoured and the owner is told, because taking money and silently dropping it is the one outcome that must never happen.

## The rulings this inherits (binding, from F17's Gate 1)

| Ruling | What F19 must do |
|---|---|
| **Q1 — deposits on, no gateway connected** | The storefront **hides the deposit entirely and books as if deposits were off.** The boutique keeps taking bookings and silently stops collecting. A dead calendar is worse than uncollected deposits; the owner-side `PolicyBlockerBanner` (F17) is the nudge. |
| **Q4 — a verified webhook against an EXPIRED hold** | **Honour the money and alert the owner.** If the slot is still free, rebind the booking to it. If it is not, surface the booking to the owner as needing a new time, money already taken. No `refund()` is added (D12 stands). |
| **Decline** (F17 review) | `settle_from_webhook` already records `GATEWAY_PAYMENT_DECLINED`, leaves the hold `pending`, and returns `newly_settled=False`. F19 must therefore **not** confirm the booking and **not** send the SMS on that path — the sweeper frees the seat naturally. |

## What this spec decides (left open by F17)

**D1 — `bookings.status` gains `pending_payment`.** Migration 0014 widens 0008's CHECK. `constants.py:45` already anticipates it: *"E4 widens it with 'pending_payment'"*. A booking in that state **occupies its seat** — the partial unique slot-seat indexes exclude only `cancelled`, so an unpaid hold blocks the seat exactly as intended, and the sweeper is what releases it.

**D2 — the retry gap F17 flagged is closed with a column, not a re-mint.** `DepositHold.redirect_url` is `None` on the converged path because 0012 stores `provider_session_id` but not the hosted-page URL. Migration 0014 adds `payments.redirect_url TEXT`. A bride who closes the tab and returns within the hold window gets **the same link back** — re-minting a session would leave an orphaned checkout at the provider and risk two live sessions for one seat.

**D3 — the webhook is an anonymous, tenant-scoped route: `POST /storefront/payments/webhook`.** It carries no session and no CSRF (the provider is not a browser), and the tenant comes from the Host header exactly like every other storefront route — which works precisely because credentials are per-tenant: each boutique registers `https://{her-slug}.modryn.co.il/storefront/payments/webhook` in her own provider account. Authenticity is the HMAC signature and nothing else, so the route must reach `verify_webhook` before it touches anything.

**D4 — hold length is 15 minutes**, config-driven (`deposit_hold_seconds`, default 900). Long enough for a real card entry including a 3-D Secure step, short enough that an abandoned checkout does not hold a Saturday slot all afternoon. Named, not magic (`KOTLIN.md`'s no-magic-numbers rule applies here in spirit).

**D5 — the sweeper rides the existing worker.** `app/worker.py` already polls `scheduled_messages`; expired holds are a second sweep in the same process, with the same `FOR UPDATE SKIP LOCKED` discipline. No new process, no new deploy target.

**D6 — the booking is created BEFORE the payment, in `pending_payment`.** The alternative (pay first, then create) cannot hold the seat, so two brides could pay for the same slot. Creating first means the seat is claimed by F13's existing advisory-lock protocol and the payment is a state transition on a row that already exists. The cost is that an abandoned checkout leaves a row until the sweeper runs; that is what `pending_payment` is for.

## Design

### The happy path

1. Storefront booking flow reaches the terms step as today. If the appointment type requires a deposit **and** the tenant has a connected gateway, a payment step follows.
2. `POST /storefront/bookings` creates the booking in `pending_payment` (F13's claim protocol unchanged), then calls `PaymentService.open_deposit`. The response carries `redirect_url`.
3. The bride pays on the provider's page and is returned to `/book/confirm`.
4. The provider posts the webhook. `settle_from_webhook` verifies and settles the payment row; **F19's own transaction** then flips the booking to `confirmed` and enqueues F16's confirmation SMS.
5. The return page polls booking status (the webhook may land before or after the redirect — neither ordering may break it).

**The webhook is authoritative, not the redirect.** A bride who closes the tab after paying still gets confirmed. A bride who reaches the return page before the webhook lands sees "we're confirming your payment" and the page resolves when it arrives.

### The unhappy paths, each with a named outcome

| What happens | Booking | SMS | Evidence |
|---|---|---|---|
| Abandoned checkout | `pending_payment` → swept → `cancelled` | none | audit row |
| Declined card | stays `pending_payment` → swept | none | `GATEWAY_PAYMENT_DECLINED` (F17) |
| Paid, webhook on time | → `confirmed` | confirmation | payment `paid` |
| Paid, webhook late, **seat still free** | → `confirmed`, rebound | confirmation | `GATEWAY_LATE_SETTLEMENT` |
| Paid, webhook late, **seat taken** | flagged to owner, NOT confirmed | none (owner alert instead) | `GATEWAY_LATE_SETTLEMENT` + `payments.error` |
| Duplicate webhook delivery | unchanged | not resent | `newly_settled=False` |

The last row is the one that most needs a test: F16's SMS must be gated on `newly_settled`, or a provider that redelivers ten times texts the bride ten times.

### Deposits on with no gateway (Q1)

`GET /storefront/appointment-types` already discloses `deposit_required`/`deposit_amount_agorot`. F19 adds: when the tenant has no connected gateway, the storefront **omits the deposit fields entirely** and the booking flow skips the payment step. The decision is made server-side — a client-side hide would still leak the amount to anyone reading the JSON, and would let a crafted request reach a payment step that cannot work.

### Frontend (storefront)

A payment step in the existing `/book/{step}` flow (`router.tsx` already carries `slot|details|terms|verify|confirm`; this adds `pay`). Hebrew copy follows F16's deck. States to design: the redirect hand-off, the return-and-waiting state, paid, declined, expired. RTL, `<bdi dir="ltr">` on amounts, axe-clean — the standing IS 5568 / WCAG 2.0 AA gate is legal, not aspirational.

## Non-goals

- **No refunds** — F29's, and it now has a provider API to build against.
- **No partial payments, no instalments, no saved cards.**
- **No owner-side "mark as paid"** — that would be a money mutation with no provider evidence; the owner's remedy for a late settlement is F15's reschedule.
- **No receipt generation.** The provider issues its own; the Israeli קבלה duty sits with the boutique and is named in F21's audit.

## Tests

Fast: the storefront omits deposit fields with no gateway; the booking response carries a redirect only when a deposit is due; the webhook route is anonymous and 400s an invalid signature; the return page's states.

db-marked (the ones that matter):
- Paid webhook → booking `confirmed` **and** exactly one confirmation SMS enqueued.
- **Redelivery → no second SMS** (gated on `newly_settled`).
- Declined → booking stays `pending_payment`, no SMS.
- Sweeper frees an expired hold → seat bookable again by another bride.
- **Late settlement, seat free** → rebound + confirmed. **Late settlement, seat taken** → owner-visible, not confirmed, money recorded.
- Concurrency: two brides racing the last seat where one is mid-payment — exactly one holds it.
- The retry path returns the **same** `redirect_url` (D2), and does not mint a second provider session.

## Risks

1. **The webhook URL is per-boutique and self-registered.** A boutique who never registers it takes payments that never confirm. Mitigation: `GET /manage/gateway` (F17) shows the URL to copy, and the owner console warns when a gateway is connected but no webhook has ever been received.
2. **Clock skew between hold expiry and provider settlement** is exactly what the late-settlement path exists for; it is a designed-for case, not an edge.
3. **The sweeper cancels bookings.** It must never touch a booking whose payment is `paid` — the guard is the payment row's status, not the clock alone, and that is the single most important assertion in the sweeper's tests.
4. **F19 is where LS's merchant-of-record problem becomes visible to a bride**: her receipt says the store's name. Acceptable for test mode; recorded again here because it is the last point before real money where it can be reconsidered.
