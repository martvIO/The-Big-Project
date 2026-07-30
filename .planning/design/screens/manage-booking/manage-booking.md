# Screen: Manage Booking (F16 — `/b/{token}`, Epic E3)

**Date**: 2026-07-29 · **Status**: **DESIGN GATE CLOSED 2026-07-30** — critic ACCEPT (round 2, 2026-07-29) plus the user's copy approval, `.planning/epics/interview-2026-07-30.md` **Q5**; P1–P5 accepted by **pre-decided #7**, F-M3 discharged in the F16 plan (Task 3) · **Designer**: Claude (main agent) · **Critic**: design-critic — round 1 NEEDS CHANGES (8 findings, all folded in), round 2 ACCEPT with one plan-phase follow-up (F-M3)
**Consumes**: `.planning/specs/booking-comms.md` (Gate 1 approved, D1–D10) · tokens rev 1 · `packages/ui` as shipped
**Copy**: `copy.md` in this directory — **the Hebrew is the user's**; every row must be APPROVED before this gate closes.

---

## 0. Scope

One public screen: the page behind the tokenized manage link that rides the confirmation and reminder SMS. It is the **confirmation screen's sibling** — the same family as `/book/confirm` (§7 of `booking/booking.md`): single centered column, no stepper (this is not a flow; she arrived from a text message, possibly weeks later), facts first, actions second, boutique contact last. Everything renders inside `StorefrontLayout` (skip link, `main#content`, footer, A11yMenu inherited — nothing to design there).

Out of scope here: SMS bodies (spec-owned templates, wording in the copy deck's §SMS section for the same sign-off), the owner console (F15), deposits (E4).

**Binding inheritances from `booking/booking.md`** — this doc does not restate them, it obeys them: the three-gold law; R19 bidi isolation (every interpolated value is isolated at the call site, `<bdi dir="ltr">` for numerals/dates/phones); §7.3 instant formatting (`Intl.DateTimeFormat('he-IL', { timeZone: JERusalem })`, weekday + date + time); R30 (loading announces via a visually-hidden status region, never `aria-busy` alone); R16/§12.3 (live regions announce discrete events only; `role="status"` for good news, `role="alert"` for failures); the qa-greps physical-direction ban; `--space-a11y-footprint` on the footer.

**The status-region shape, ruled once**: `VisuallyHidden` as shipped takes no props beyond `children` (`A11y.tsx`) — the shipped F14 pattern is a plain `<span role="status">` **nested inside** `VisuallyHidden` (this is the exact DOM `/book/verify` renders today). Every "status region" in this doc means that nested shape; no `packages/ui` change is needed or wanted.

## 1. The page, mobile 375 — loaded, upcoming (state L)

```
+---------------------------------------------+
| [StorefrontLayout header/skip — inherited]  |
|                                             |
|  התור שלך                                   |   h1, --font-display, --text-2xl, --color-ink
|  ────                                       |   gold hairline, w-12 h-px, aria-hidden
|                                             |
|  +---------------------------------------+  |
|  |            Card (--color-surface)     |  |
|  |  מועד                                 |   label row: --text-sm semibold ink
|  |  יום שלישי, 4 באוגוסט, 10:00          |   value: --text-lg ink, <bdi dir="ltr"> islands
|  |  ·············································· divider: h-px --color-border
|  |  סוג הפגישה                           |
|  |  מדידה ראשונה                          |
|  |  ·············································· (dress rows only on item-based)
|  |  שמלה                                 |
|  |  שמלת אלמה · מידה 36                  |   <bdi> for the owner-authored name
|  +---------------------------------------+  |
|                                             |
|  [ אישור הגעה ]                             |   Button primary lg, w-full sm:w-auto
|  [ ביטול התור ]                             |   Button secondary md, w-full sm:w-auto
|                                             |
|  לפי המדיניות שאישרת: ביטול עד             |   policy line, --text-sm --color-ink-muted,
|  48 שעות לפני המועד.                        |   {{hours}} in <bdi dir="ltr">
|                                             |
|  [ContactPanel — phone / waze / maps]       |   the §2.5 phone-only block family
|                                             |
| [footer — inherited]                        |
+---------------------------------------------+
```

Layout container: `mx-auto max-w-[640px] px-4 pt-8 pb-16 md:px-6 flex flex-col gap-6` — identical to `/book/*` so the two surfaces read as one product.

### 768 / 1440 deltas

The column stays 640 and centered (same ruling as the booking flow — a luxury reading column, not a dashboard). Buttons go `w-auto` inline-row (`sm:flex-row`, primary first in reading order). Nothing else changes; there is deliberately no two-column desktop layout for five facts and two buttons.

## 2. States — the single source for this screen

| # | State | Trigger | What she sees | Test hook |
|---|---|---|---|---|
| S | skeleton | lookup in flight | Card-shaped `Skeleton` + the nested status region (§0 ruling) carrying `manage.loading` (R30) | loading announced |
| L | loaded, upcoming | 200, status `confirmed`, `starts_at` future, no `attendance_confirmed_at` | §1 wireframe | facts + both actions |
| L2 | attendance confirmed | 200 with `attendance_confirmed_at` set, or just confirmed on-page | facts Card; primary button replaced by a success line `✓ manage.attendanceDone` (`--color-success`, ✓ `aria-hidden`); **cancel stays available** | confirm idempotent; cancel still rendered |
| C | cancelled | 200 with status `cancelled`, or just cancelled on-page | facts Card kept (she may need the date to rebook); `manage.cancelled` line in `--color-ink` + `ButtonLink` → `/book/slot` (`manage.rebookCta`); no actions | actions absent |
| P | past | 200, `starts_at` ≤ now, not cancelled | facts Card; `manage.past` line, muted; no actions; ContactPanel stays | actions absent |
| X | invalid link | 404 `BOOKING_LINK_INVALID` | no facts; `manage.invalid` (`--text-lg`), `manage.invalidHint` (muted) pointing at the boutique; ContactPanel if the layout's boutique fetch succeeded | no Card |
| R | retryable failure | 429 / network / 5xx on lookup | `manage.loadFailed` + `Button secondary` `manage.retry` + ContactPanel — F14's honest-throttle shape: recoverable, no blame, phone as the human exit | retry refetches |

State precedence when actions race the clock: a 409 `BOOKING_ALREADY_STARTED` on an action re-renders **P** from the response body; a 409 `BOOKING_CANCELLED` re-renders **C**. The page always re-renders from the response's booking — never from what it optimistically hoped.

## 3. The cancel two-step — ruled

One tap must never cancel a wedding-dress appointment. The `ביטול התור` (secondary) button does not call the API; it **reveals** an inline consequence block between the buttons and the policy line:

```
+---------------------------------------+
|  Card, --color-surface-raised          |   revealed block, tabindex="-1", focus moves here
|  לבטל את התור?                         |   --text-lg, ink
|  [consequence sentence — see below]    |   --text-base, ink
|  [ אישור הביטול ]   [ השארת התור ]     |   Button danger md · Button ghost md
+---------------------------------------+
```

- Focus moves to the revealed block on open (house rule: the mover is the state change that mounted the target). `השארת התור` collapses it and returns focus to the cancel button. No `Modal` — an inline reveal keeps the whole decision on one surface and spares the focus-trap machinery for a two-button choice.
- `אישור הביטול` is the screen's only `danger` variant. In-flight: disabled with the house busy treatment; success re-renders **C** and the status region announces `manage.cancelled`.
- **The consequence sentence, pre-E4 (⚠ P1)**: every F16-era booking is deposit-free (deposits arrive in E4 #19), so the honest consequence is that cancellation costs nothing. The block therefore shows the window fact from her accepted terms (`manage.cancelPolicyLead` + isolated `{{hours}}` + suffix, R19 split shape) followed by `manage.cancelConsequenceFree`. The in-window/out-of-window **split ships as structure** (the page computes which side of the window she is on from `starts_at − now` vs `refundable_until_hours_before`) but pre-E4 both sides render the same free-cancellation sentence — a scary forfeit warning about a deposit that was never taken would be a lie. E4 swaps the out-of-window key for the deposit-era wording. Recorded as PROPOSED for the user.

## 4. Component notes — exact tokens

| Element | Notes |
|---|---|
| h1 | `--font-display --text-2xl --color-ink`; gold hairline `h-px w-12 bg-gold` `aria-hidden` below — identical to every `/book/*` heading |
| Facts Card | `Card` on `--color-surface`, `rounded-md p-6 shadow-sm`, label/value rows exactly as `/book/confirm` §7.2 (labels reuse the approved `booking.confirmWhen`/`confirmWhat`/`confirmDress` rows — P2) |
| Primary action | `Button variant="primary" size="lg"` — ink on gold, elevation hover |
| Cancel reveal trigger | `Button variant="secondary" size="md"` |
| Confirm-cancel | `Button variant="danger" size="md"` — `--color-danger` bg, `--color-surface-raised` text (shipped variant; first storefront use) |
| Keep button | `Button variant="ghost" size="md"` |
| Rebook | `ButtonLink` → `/book/slot` |
| Policy line | `--text-sm --color-ink-muted`; `{{hours}}` inside `<bdi dir="ltr">` |
| Status region | one nested-shape status region (§0 ruling) for the page, written on discrete events only (R16/§12.3): attendance confirmed, cancellation completed — never on keystrokes or renders |
| ContactPanel | existing composite, boutique data from `useBoutique()` (layout fetch); renders only rows whose data exists |
| Skeleton | existing primitive, Card-shaped |

Contrast: ink/cream 15.24, muted/cream 6.15, success/cream 6.10, gold-text links 5.57 — all in the tokens ledger. White-on-danger (the shipped `Button danger` pairing, `#FFFFFF` on `#A03232`) computes ≈7.0:1 and is **added to the tokens ledger with this gate** — it was not previously enumerated there.

## 5. Document title, route, focus

- Route `'manage'`, pattern `/b/{token}` — token is opaque `[A-Za-z0-9_-]+`; anything after `/b/` matches the route (the page owns invalid-token rendering — the catalog fallthrough must never swallow a bad token, spec D7/D8).
- `DOC_TITLE_KEYS` entry → `document.manageTitle` (WCAG 2.4.2).
- On route entry the layout's existing focus handling applies (`main#content` focus target). No autofocus on buttons — she reads the facts first.
- **The two success transitions remove the control that was just clicked, so each rules its focus destination** (the house rule: the mover is the state change that mounted the target): L→L2 mounts the `manage.attendanceDone` success line with `tabindex="-1"` and focuses it; reveal→C mounts the `manage.cancelled` line with `tabindex="-1"` and focuses it. Focus never drops to `<body>` after the one action the page exists for.
- Reduced motion: the reveal is an instant show/hide; nothing else animates. (House: motion only through shipped `--motion-fast` transitions on buttons.)

## 6. What this screen deliberately does not have

No stepper (not a flow) · no boutique hero/photography (a utility moment, not a lookbook page — but the display-font h1 and gold hairline keep it in the brand's voice) · no map embed (ContactPanel links out) · no reschedule action (F15's owner remedy; a self-serve reschedule is a bigger product decision than a comms feature should smuggle in) · no dress image (bookings snapshot no media — spec wire shape) · no countdown/timer (R3's no-ticking-numbers ruling generalizes: the reminder already carries urgency).

## 7. PROPOSED decisions (user confirms at the gate)

- **P1 — pre-E4 consequence wording**: window math shown, both window sides render the free-cancellation truth until E4 swaps the out-of-window key. (§3 above.)
- **P2 — facts-card labels reuse the approved `booking.confirmWhen`/`confirmWhat`/`confirmDress` rows** instead of minting `manage.*` duplicates — one label, one Hebrew, no drift; the i18n guard sees cross-section literals fine.
- **P3 — cancel remains available after attendance is confirmed** (L2 keeps the cancel button): confirming attendance is a courtesy signal, not a lock-in; plans change.
- **P4 — the cancelled state carries a rebook `ButtonLink` to `/book/slot`**: the seat she freed is bookable again (spec: index predicates), and the person most likely to want it is her. One tonal caveat for the user's read: a cancellation is not always a glad-to-rebook moment (a called-off wedding is the hard case) — the link's presence is ruled here, its register belongs to the copy row.
- **P5 — `Button danger` makes its first storefront appearance** on the confirm-cancel control only. The reveal trigger stays secondary — danger is reserved for the click that destroys.

## 8. ⚠ FINDINGS

- **F-M1**: `errors.*` copy exists for the booking flow's failures but none of it fits a lookup that failed before any form exists — the R state needs its own two rows (`manage.loadFailed`, `manage.retry`) rather than borrowing `errors.slotsError`'s "the times didn't load" wording. Copy deck carries them.
- **F-M3 (critic round 2 — plan-phase follow-up)**: `tenants.name` is unbounded TEXT (`tenant.py:17`), but the confirmation-SMS segment arithmetic assumes a ≤25-char boutique name with ~8 chars of headroom. The build must make production match the fixture: `BookingCommsService` truncates (or guards) the interpolated boutique name at 25 chars in SMS bodies. Carries into the F16 plan as a named task detail.
- **F-M2 (corrected at the gate — the critic caught the first version scoped backwards)**: ContactPanel renders from `useBoutique()` (the layout fetch) as primary. The lookup response's `boutique` block exists **only inside the 200 payload**, so it can serve as fallback **for L/L2/C/P only**, when the layout fetch failed but the lookup succeeded. X and R are lookup failures — their responses are the `ErrorResponse` shape and carry no boutique data under any circumstance; ContactPanel there depends solely on `useBoutique()`, and when that also failed the states render without the contact block (the invalid/failed copy still stands on its own).
