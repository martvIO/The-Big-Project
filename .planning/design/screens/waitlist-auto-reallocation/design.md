# Screen: Waitlist auto-reallocation (F23 — the offer SMS, `/w/{token}`, three manage fields, Epic E5)

**Date**: 2026-08-06 · **Status**: DESIGN GATE OPEN — awaiting copy approval · **Designer**: Claude (subagent)
**Consumes**: `.planning/specs/waitlist-auto-reallocation.md` (Gate 1 self-approved, D1–D8) · `waitlist-join/design.md` (F22, the sibling) · `manage-booking/manage-booking.md` (the shipped `/b/{token}` page this one is modelled on) · `deposit-booking-flow/design.md` (F19's hand-off, reused whole) · tokens rev 1 · `packages/ui`, `apps/storefront`, `apps/manage` **as shipped**
**Copy**: every Hebrew row needs APPROVAL before the gate closes. Register: calm, feminine address, **no exclamation marks**, no urgency, **no delivery promises** (pre-decided #5).

---

## 0. Scope

Three surfaces. **The offer SMS body** (a fifth lifecycle body beside the four in `comms_templates.py`). **`/w/{token}`** — a new tokenized storefront route, the `/b/{token}` page's sibling, not a flow. **`WaitlistSection`** — three fields on F22's shipped table. Out of scope: the cascade itself, any owner "offer now" control, notification-bell rows (F35), portal display (F24).

**Binding inheritances from `manage-booking.md` and `booking/booking.md`** — obeyed, not restated: the `pageClass` reading column (`max-w-[640px]`, centred, `pb-16`); the display-font h1 + gold hairline; facts-first / actions-second / contact-last; the `View` union derived from the server's answer, never from what a tap hoped for; the deferred-focus `moveFocusTo` ref pattern; R19 bidi isolation (`<bdi dir="ltr">` islands for every numeral, date, time and phone); §7.3 `Intl.DateTimeFormat` in `JERusalem`; R30 (loading announces via `VisuallyHidden > span[role="status"]`); R16 (live regions announce discrete events only); the qa-greps physical-direction ban; the house focus rule (**the mover is the state change that mounted the target**).

### R1 — THE RULING THIS DECK EXISTS TO MAKE: no countdown, anywhere

Spec D6 writes *"a countdown to `offer_expires_at`"*. **It does not ship.** `tokens.md` usage law 9 bans countdowns outright, `booking/booking.md` R3 removed the only ticking number in the product for three independent reasons, `manage-booking.md:117` already generalised the ruling to this exact surface, and `sos-paging` D15 re-made it under emergency pressure. A 1 Hz repaint on a page whose whole job is a deadline is the single most recognisable promo-register device in the Israeli market, and it drags SC 2.2.2 onto a screen that otherwise has nothing to pause.

**What ships instead: one static, absolute Jerusalem clock time**, exactly as `sos.since` renders «מאז 11:20». It never subtracts, so it is immune to a phone's clock drift, it is readable off a screenshot, and it is the same value the SMS already carried. The deadline is a *fact*, not a timer.

---

## 1. The offer SMS body — the fifth body

```
{name}: התפנה תור ביום {weekday}, {date} בשעה {time}. שמור עבורך עד {deadline}, לאישור: {url}
```

> *"{Boutique}: a slot has freed up on {weekday}, {date} at {time}. Held for you until {deadline}, to confirm: {link}"*

| Rule | Why |
|---|---|
| **Absolute deadline, never «בעוד שעתיים»** | The reminder's own rule (`reminder_sms_body`): a body renders from an instant, never from a relative offset, because an SMS read forty minutes late makes a relative claim false. The 2-hour window is a *setting*; the clock time is a *fact*. |
| **No send-promise, no "first come first served", no "only you"** | The cascade offers sequentially (#13), but the bride is owed no statement about other brides, and «נשלח רק אלייך» would be an urgency device. |
| **Quiet-hours-aware by construction, not by wording** | The cascade never issues inside `[21:00, 08:00)`, so the body says nothing about hours. Latest possible issue 20:59 + a 2h window = 22:59 — **the deadline can never cross midnight at the shipped default**, which is what lets it render as a bare `HH:MM`. ⚠ **F-O1**: that guarantee is a function of `waitlist_offer_window_seconds`; see §12. |
| **Segment budget: 3, at parity with the reminder** | Prefix 101 UCS-2 units at a 25-char truncated name (`truncate_boutique_name`) and the longest weekday; link 97 at the documented 30-char slug budget → **198 ≤ 201**. Pinned by a test beside `test_booking_comms_templates.py`. |
| **`mask_manage_link` on the `message_log` copy** | Identical reasoning to the reminder: `waitlist_entries` stores only the sha256, so the raw token may not sit in the forever-table beside its own hash. |
| **No exclamation mark, no «מהרי», no «נותרו רק»** | Rule 7 of `booking/copy.md`. The whole storefront bundle contains zero exclamation marks and this body will not be the first. |

## 2. `/w/{token}` — `OfferPage.tsx`, `RouteName` `"offer"`

Token opaque in the router (the `manage` route's verbatim rule — a dead token must reach the page so the page renders its own state). No login. Same `pageClass`, same `Heading` shape, same trailing `ContactCard`, same `VisuallyHidden` status region.

```
|  התפנה תור עבורך                            |   h1 --font-display --text-2xl --color-ink
|  ▁▁▁▁                                       |   gold hairline, aria-hidden
|  +----------------------------------------+ |
|  | Card — the facts (Facts's shape reused) | |
|  |  מתי                                    | |   booking.confirmWhen (REUSED label)
|  |  יום חמישי, 20.8.2026 · 14:30           | |   <bdi dir="ltr"> islands, R19
|  |  ────────────────────────────────────   | |
|  |  מה                                     | |   booking.confirmWhat (REUSED)
|  |  מדידה ראשונה                            | |   <bdi> — owner-authored, may be Latin
|  +----------------------------------------+ |
|  אפשר לאשר את התור עד השעה 12:15            |   --text-base --color-ink, STATIC (R1)
|  [ policy prose — the /book/terms block ]   |   reused verbatim, incl. the R19 splits
|  [x] קראתי את מדיניות הביטולים …             |   Checkbox, booking.acceptTerms (REUSED)
|  שם מלא  [__________________]               |   Input, booking.name (REUSED)
|  [ אישור וקביעת התור ]                      |   Button primary lg, booking.submit (REUSED)
|  [ ויתור על התור ]                          |   Button secondary md — reveals §2.1
|  [ ContactCard ]                            |
```

**The deadline line** is the R19 split shape: `offer.deadlineLead` + `<bdi dir="ltr">{TIME}</bdi>`. When the deadline's Jerusalem calendar day is not today it renders `{WEEKDAY}, <bdi>{DATE}</bdi> <bdi>{TIME}</bdi>` instead — one conditional, no new key, and the guard that makes an owner-raised window safe.

**No countdown, no progress ring, no colour ramp, no motion** (R1). Nothing here for `prefers-reduced-motion` to switch off.

### 2.1 Decline is two-step, and the consequence sentence is load-bearing

Declining does not skip one slot — it writes `cancelled` and **takes her off the waitlist for that day** (spec D4). One tap must never do that, so the secondary button reveals a `Card bg-surface-raised` carrying the question, the consequence, a `danger` confirm and `manage.cancelKeep` (reused) to back out — the `/b/{token}` cancel reveal's exact shape and its exact focus behaviour. A decline whose copy said only «לא מתאים לי» would silently remove a bride who thought she was passing on one time.

### 2.2 The deposit variant is a hand-off, not a new screen

A claim on a deposit-on type returns `pending_payment` + `redirect_url` from the shipped `open_deposit`. The page then renders **F19's shipped hand-off verbatim** — `booking.payHandoff`, the automatic redirect, and `booking.payManualHint` / `booking.payManualCta` as the fallback for a browser that blocks it. **Zero new copy, zero new payment code** (spec D5). Once she leaves for the hosted page, `/book/pay`'s shipped polling surface owns every subsequent state; `/w/{token}` is not re-entered and must not try to be a second checkout.

## 3. The states — the single source

| # | State | Trigger | What she sees | Focus / announce |
|---|---|---|---|---|
| L | loading | mount | `Heading` + `Skeleton` in a Card | `role="status"` `offer.loading` (R30) |
| **A** | **live offer** | lookup 200, `offered` ∧ unexpired | §2 in full | h1 on arrival (layout `MAIN_ID`) |
| A2 | claiming | claim in flight | primary `loading`; decline hidden | `offer.claiming` |
| **B** | **claimed — deposit** | 201 with `redirect_url` | §2.2 hand-off; facts stay | redirect fires beside it |
| **C** | **claimed — no deposit** | 201, no `redirect_url` | facts stay; `offer.claimed` replaces both buttons | line `tabindex="-1"`, focused, `role="status"` |
| **D** | **already claimed by you** | lookup 200, `claimed` | `offer.claimedReturning` + **`manage.invalidHint` reused** | — |
| **E** | **expired** | lookup 200, `expired`/past deadline | `offer.expired` + `offer.pickAnotherHint` + `manage.rebookCta` → `/book/slot` | — |
| **F** | **gone — someone else won** | claim 409 `SLOT_UNAVAILABLE` | `offer.gone` + hint + rebook CTA. **The entry stays `offered`** (the transaction rolled back), so a reload re-renders **A** until the offer expires — deliberate and correct | line `role="alert"` |
| G | declined | decline 200, or lookup on `cancelled` | `offer.declined` + hint + rebook CTA | line focused |
| **H** | **invalid / unknown / wrong tenant** | 404 | **`manage.invalid` + `manage.invalidHint`, reused verbatim** — one indistinguishable state, no oracle | — |
| I | load failed | 429 / 5xx / network | `manage.loadFailed` + `manage.retry` (reused) | `role="alert"` |
| J | stale terms | claim 409 `TERMS_STALE` | `errors.termsStale` (shipped) above a re-rendered policy block, tick cleared | `role="alert"` |

**State D's copy is a ruling.** Spec D6 drafted «התור כבר נקבע. הקישור לניהול נשלח אליך בהודעה» — a delivery claim the product may not make (the provider can be unconfigured; F16's whole 204-silent posture exists for this). The phone always works, so the shipped `manage.invalidHint` («לכל שאלה על התור, אפשר להתקשר לבוטיק.») is both more honest and one fewer key.

Error mapping otherwise: **no new error keys.** 429 → `errors.tooManyAttempts`; missing name → `booking.nameRequired`; unticked terms → `booking.acceptRequired`; 400 → `errors.validation`; 5xx/network → `errors.unknown`.

## 4. Manage — `WaitlistSection` gains three fields, and nothing else

One new column, **«ההצעה»**, between status and joined-at. It renders only for an `offered` row (`—` otherwise): the offered slot's day+time, then `bookingWaitlist.offerUntil` + `<bdi dir="ltr">{expiry}</bdi>` on a second muted line.

```
| יום | סוג הפגישה | לקוחה | סטטוס | ההצעה | נרשמה | |
| ה׳ 20.8 | מדידה ראשונה | רותם לוי | [הוצע תור] | ה׳ 20.8 14:30 | 14:32 | [ ביטול ] |
|         |               |          |            | בתוקף עד 12:15 |       |            |
```

- The `offered` badge becomes **`Badge variant="warning"`** — the shipped `bookingWaitlist.statusOffered` («הוצע תור») is already in `he.ts` and its value does not change; only the variant does. `warning` is the one variant that reads "in flight, will resolve on its own" without claiming success or failure, and it passes AA at badge size.
- **Cancelling an `offered` row kills a live offer a bride is holding right now**, so the danger phase takes its own label — `bookingWaitlist.cancelOfferedConfirm` — rather than the generic one. Same in-place swap, same `min-h-[44px]` (F22's F-W1 answer, already shipped).
- **Cascade history: none, deliberately** (spec D8 says "small, enumerated"). No expiry log, no per-entry offer trail, no "offered 3 times" counter. An expired entry simply reads `ממתינה` again or drops off; the audit trail lives in `audit_log`, not in this table. The one thing an owner needs from this row is *is anyone holding this slot right now, and until when* — which is exactly what the column says.
- Still **no polling** and no pagination (F22's recorded ceilings, unchanged).

## 5. Component notes — exact tokens

| Element | Notes |
|---|---|
| h1 + hairline | `font-display text-2xl text-ink` + `h-px w-12 bg-gold` `aria-hidden` — identical to `/b/{token}` and every `/book/*` |
| Facts card | `Card flex flex-col gap-4`, the `Facts` component's shape and its **reused** labels (manage-booking P2) |
| Deadline line | `text-base text-ink` — **not** `--color-danger`, **not** bold, **not** a chip. It is a fact, not an alarm |
| Terms block | the `/book/terms` prose + `Checkbox` verbatim, incl. `refundWindow`/`forfeit` R19 splits |
| Name field | shipped `Input`, RTL content |
| Claim / decline | `Button primary lg` / `Button secondary md`, `fullWidthMobile` — 44px met by size |
| Decline reveal | `Card bg-surface-raised`, `Button danger md` + `Button ghost md` — the `/b/{token}` cancel reveal |
| Terminal lines | `text-lg text-ink`, `tabindex="-1"`, `role="status"` (F uses `role="alert"`) |
| Manage offer column | `text-base` line + `text-sm text-ink-muted` expiry line; `Badge variant="warning"` |

Contrast: every pair is already in the tokens ledger. `warning-text` on cream is in it from F34. Nothing new to enumerate.

## 6. RTL

Logical properties only. **The page has no LTR-content island except the numerals** — no phone input, no code field, so every `<bdi dir="ltr">` here wraps a date, a time or nothing. The owner-authored type name takes a bare `<bdi>` (never `dir="ltr"` — that is itself a bidi defect on Hebrew, `ManageBookingPage.tsx:124`). The manage offer column's two runs are `<bdi dir="ltr">` islands inside an RTL cell. Reduced motion: nothing animates but the shipped `--motion-fast` button transitions.

## 7. Accessibility (IS 5568 / WCAG 2.0 AA — legal gate)

- **SC 2.2.1 is the one to defend, and R1 is the defence.** The offer has a time limit, but **nothing on the page auto-updates**: no counter, no poll, no re-render. The criterion governs a session/interaction limit the user must be able to extend — here the limit is a *server-side business deadline*, essential to the activity (2.2.1 exception (e)), it is **stated in advance and in absolute terms**, and missing it is non-destructive: the slot returns to the pool and she may book it directly or rejoin. **No live region ticks, so there is nothing to pause.** This paragraph is the audit answer; do not add a timer and invalidate it.
- **Focus**: page arrival lands on the layout's `<main tabindex="-1">` (the router's shipped behaviour) — the h1 is the first thing read. Decline-reveal focuses the question; back-out returns focus to the re-mounted trigger via the deferred `moveFocusTo` ref (never a synchronous `.focus()` on an unmounted node — `ManageBookingPage.tsx:220`'s recorded hazard). Every terminal line is `tabindex="-1"` and focused by the transition that mounted it; focus never drops to `<body>`.
- **Announcements**: discrete events only — loading, claiming, claimed, declined, gone. Never per render.
- **Targets**: ≥44px on every control (`Button` md/lg by size; the checkbox's shipped hit area).
- **axe-zero** in e2e on: the live offer (A), expired (E), the open decline reveal, and the manage section with an offered row.

## 8. i18n — storefront `offer.*` (he.ts; `ar.ts` mirrors the Hebrew untranslated, #47)

Fourteen new keys. Everything else is **reused** — `booking.confirmWhen` / `confirmWhat` / `name` / `nameRequired` / `acceptTerms` / `acceptRequired` / `termsHeading` / `refundWindow*` / `forfeit*` / `submit` / `payHandoff` / `payManualHint` / `payManualCta`, `manage.invalid` / `invalidHint` / `loadFailed` / `retry` / `rebookCta` / `cancelKeep`, and the whole `errors.*` map (P1: one label, one Hebrew, no drift).

| Key | Hebrew | English annotation |
|---|---|---|
| `offer.title` | התפנה תור עבורך | "A slot has freed up for you" — h1, matches the SMS's opening verb |
| `offer.loading` | טוענות את פרטי ההצעה | "Loading the offer details" — hidden status |
| `offer.deadlineLead` | אפשר לאשר את התור עד השעה | "You can confirm the appointment until" — R19 lead; the time follows in a `<bdi>` |
| `offer.claiming` | קובעות את התור | "Booking the appointment" — hidden status (mirrors `booking.submitting`) |
| `offer.claimed` | התור נקבע. נתראה. | "The appointment is booked. See you." — `manage.attendanceDone`'s register |
| `offer.claimedReturning` | התור הזה כבר נקבע. | "This appointment is already booked." — no delivery claim; `manage.invalidHint` follows |
| `offer.expired` | תוקף ההצעה הזו פג. | "This offer has expired." — plain fact, no blame |
| `offer.gone` | התור הזה נתפס בינתיים. | "This appointment was taken in the meantime." — the same sentence a direct booker meets |
| `offer.pickAnotherHint` | אפשר לבחור מועד אחר מהמועדים הפנויים. | "You can choose another time from the available ones." — shared by expired / gone / declined |
| `offer.declineCta` | ויתור על התור | "Give up the appointment" — the reveal trigger, not the action |
| `offer.declineQuestion` | לוותר על התור הזה? | "Give up this appointment?" |
| `offer.declineConsequence` | הוויתור יסיר אותך גם מרשימת ההמתנה ליום הזה. | "Declining also removes you from the waitlist for this day." — the load-bearing sentence |
| `offer.declineConfirm` | אישור הוויתור | "Confirm" — the `danger` control |
| `offer.declined` | ויתרת על התור, והסרנו אותך מרשימת ההמתנה ליום הזה. | "You gave up the appointment, and we removed you from that day's waitlist." |

## 9. i18n — manage `bookingWaitlist.*` (+ `HE_F23` **spread into `HE`** in `i18n.test.ts`, with its floor)

| Key | Hebrew | English annotation |
|---|---|---|
| `bookingWaitlist.colOffer` | ההצעה | "The offer" — new column header |
| `bookingWaitlist.offerUntil` | בתוקף עד | "Valid until" — R19 lead; the expiry time follows in a `<bdi>` |
| `bookingWaitlist.cancelOfferedConfirm` | אישור — ההצעה תבוטל | "Confirm — the offer will be cancelled" — the danger label on an `offered` row |

`bookingWaitlist.statusOffered` («הוצע תור») **already ships** from F22 — its value does not change, only its `Badge` variant. An unspread `HE_F23` block is silently green; the floor assertion is the guard.

## 10. What these surfaces deliberately do not have

No countdown, timer, progress ring or ticking anything (**R1**) · no "only N left" / "first come first served" / any scarcity register · no exclamation marks · no login on `/w/{token}` · no position number · no second checkout surface (§2.2 hands to F19's) · no cascade history, offer counter or expiry log in manage (§4) · no polling on either surface · no owner "offer now" button · no name prefill from `customers` (one field, one ask — spec D6) · no manage-link display on the claimed state (the SMS carries it; asserting otherwise is a delivery claim) · no new error keys · no new privacy Hebrew (F20's shipped notice, unchanged).

## 11. PROPOSED (user confirms at the gate)

- **P1 — R1, the countdown removal**, overriding the spec's D6 wording. A static absolute deadline instead. Three prior rulings and a legal gate stand behind it; the spec's own copy elsewhere never asked for a timer.
- **P2 — decline is two-step with an explicit consequence sentence**, matching `/b/{token}`'s cancel. A one-tap decline silently empties a bride's place on the list.
- **P3 — state D reuses `manage.invalidHint` instead of the spec's SMS-delivery sentence.** More honest under an unconfigured provider, and one fewer key.
- **P4 — the `offered` badge is `warning`, not `neutral`.** F22 shipped `neutral` as a placeholder for a status that could not yet occur; now that it can, an owner scanning the table needs the in-flight row to separate from the waiting ones.

## 12. ⚠ FINDINGS

- **F-O1 — the bare `HH:MM` deadline is only unambiguous while the window is short.** At the shipped default (2h window, 21:00 gate) the deadline cannot cross midnight. Raise `waitlist_offer_window_seconds` past ~3h and a 20:30 offer expires *tomorrow*, and both the SMS body and the page line would read as today. The page has the guard (§2, weekday+date when not today); **the SMS body must get the same conditional** — append the weekday word when the deadline's Jerusalem day differs from the send day — and a unit test must pin it. Cheap now, a support call later.
- **F-O2 — state F is a live-offer state, not a terminal one.** The claim's rollback leaves the entry `offered`, so a reload after «התור הזה נתפס בינתיים» re-renders the *live offer* for a slot that is gone, until expiry. Correct per spec D4 (no eager advance), but the build must not "fix" it by expiring the entry client-side, and the e2e must assert the reload behaviour so a later reader does not read it as a bug.
- **F-O3 — `offer.*` is a new storefront namespace with no manage collision**, unlike F22's `waitlist.*` (F-W2). Recorded so the next reviewer does not go looking for one.
- **F-O4 — the terms prose block is currently inline in `BookPage.tsx`'s terms step.** Two callers now. Extract it to a component rather than copy it; a second, drifting copy of a *legal* policy render is the one duplication this deck will not accept.

Design Gate: accepted by design-critic, 2026-08-06
