# Screen: Deposit booking flow (F19 — the storefront's `pay` step, plus three edited surfaces)

**Date**: 2026-08-03 · **Status**: **DESIGN GATE SELF-APPROVED under the standing delegation.** Interview **Q2** named exactly **two** novel interaction patterns for this run — F34's shift board and F42's capacity matrix — and F19 is neither. A hand-off screen, a bounded poll and three status branches are assembled entirely from shipped shapes, so there is **no prototype and no `design-critic` pass** at this gate, and every `P-` in §8 carries a resolution rather than a question. F57's header states this reasoning verbatim for its own panel; this is the same reasoning at the second surface. **A deck without a prototype is deliberate, and what it costs is stated rather than hidden**: the one thing a human reviewer would have caught here is that **the bride leaves this origin and comes back with no client state at all** — the first screen in the whole product that must survive a full document load — and **§2.2** is where that is discharged. The second is **SC 2.2.1**, and **§7.4** is where that is discharged.
**Designer**: Claude · **Consumes**: `.planning/specs/deposit-booking-flow.md` (**MD1–MD5**, **D1–D21**, Gate 1 self-approved under the 2026-07-31 pre-authorization) · `.planning/design-config.md` (**binding**) · `.planning/design/system/tokens.md` rev 1 and `components.md` (**binding**) · `.planning/design/screens/booking/booking.md` (F14's shipped flow — this deck is a sixth step inside it and inherits its rulings whole) · `.planning/design/screens/manage-booking/manage-booking.md` (the bride's tokenized page) · `.planning/design/screens/owner-bookings/owner-bookings.md` (F15's console rulings) · `.planning/design/screens/design-system/manage-restyle.md` (**binding**) · `Frontend/scripts/qa-greps.sh` (a **blocking CI gate**, read and designed within — §6.2) · `packages/ui`, `apps/storefront` and `apps/manage` **as shipped**
**Copy**: **inline, in §6.1** — there is no sibling `copy.md` at this gate. Every string this feature declares is in one table with its Hebrew, and `ar.ts` takes the same Hebrew value untranslated (Interview Q3 / pre-decided #47 / the 2026-07-31 languages ruling). **The Hebrew remains the user's to edit post-merge** — a one-line `he.ts`/`ar.ts` edit, never a rebuild (the F15 P-1/P-5, F34 and F57 precedent).
**Prototype**: **none, deliberately** (see the status line).
**Parked**: **MD3's two approved Hebrew cancel sentences.** They block two strings, not this deck. **MD3's neutral interim ships in their place** (§4 `MB-cancel`, §6.1). The shipped `manage.cancelConsequenceFree` — *"cancelling carries no cost"* — becomes **false the day F19 merges** and **must not survive it**.

### Corrections this deck is written against — the spec text is stale on seven points

A code recon at pick time found seven. The spec's *rulings* are unaffected; its *citations* and one of its numbers are not. Nothing below reopens a decision.

| | Correction | Does it touch this deck? |
|---|---|---|
| **C1** | **The migration is 0017, not 0014.** 0014 is F34's shipped `0014_booking_check_in.py`; F57 holds 0015 and F33 takes 0016. F19 **builds** against 0015/`down_revision` 0014 so its own branch is self-coherent, then **renumbers at rebase time** (two literals and a filename), and **must not open its PR until F57 and F33 merge**. A single-head guard lands in `Backend/tests/test_migrations.py` (12 tests today, no head-count test) so the collision fails in `make test` rather than as a CI mystery | **No.** Recorded so a reader of §0 does not go looking for "migration 0014" |
| **C2** | `db/repositories/bookings.py` line citations shifted (F34 moved them): `cancel` is **:473** with its `== 'confirmed'` guard at **:510** (the spec says :346), `reschedule` **:525**, `list_window_facts` **:666** | No — backend only |
| **C3** | `dashboard/service.py` shifted: `dashboard` **:335**, the `list_window_facts` call **:361**, the `cohort_ids` fold **:370**. **D14's ruling is unchanged** — filter `pending_payment` out of `facts` once, right after `list_window_facts` returns | No — backend only |
| **C4** | `main.py`: the unbuilt-`PaymentService` comment is at **:709-712** (not :698-701); `_register_spas(app)` must stay the **last** registration (**:1057**) | **Yes, one line.** `/fake-pay` is an SPA route, not a server route — §8 **P-11** |
| **C5** | `models/constants.py` is a **live merge surface** (F57 is widening `StaffRole` in it right now). `BookingStatus.PENDING_PAYMENT` is **reserved by a comment at :47-54 and the member does not exist yet**. Append only; rebase before every push; never touch F57's role values | No — backend only, but it is why §0 says the frontend must not assume the enum exists on main |
| **C6** | `tests/test_payments_service.py:921-925` reaches the late-settlement branch by hand-setting `row.status = EXPIRED`. F19's new tests drive expiry **through the sweeper** | No — backend only |
| **C7** | **`bookings.source` does not exist** — no column, no model field. It is F50's, unbuilt. **Do not invent it**, and nothing on any screen in this deck branches on where a booking came from | **Yes.** §0's *not here* table |
| **C8** | *(found by this deck)* the spec's own frontend citations for the bride's page are stale: the cancelled branch is `ManageBookingPage.tsx:318` (spec says :291) and `manage.cancelConsequenceFree` is at **:417** (spec says :390). `:38` is correct | **Yes** — §9 **F-2** |

---

## 0. Scope

The storefront's `/book/*` flow gains a **sixth step**, and three shipped surfaces are edited. **Nothing else moves.**

| Surface | Who sees it | Shape |
|---|---|---|
| **`/book/pay`** — `BOOK_STEPS` gains `"pay"` (`router.tsx:27`, a closed set) | the bride, anonymous, usually 375px | **new.** One route, **five** states (§1, §4) |
| `/book/confirm` | the bride | **UNCHANGED.** Not redesigned, not restyled, not re-read. §8 **P-6** |
| `/book/slot` | the bride | the **deposit dead-end is deleted** — `depositBlocked` (`BookPage.tsx:478`) and its no-op forward (`:549-553`) go, and `booking.depositByPhone` goes with them. §8 **P-7** |
| `/b/{token}` — `ManageBookingPage` | the bride, from an SMS | a **sixth view** (awaiting payment) plus **MD3's** cancel sentence |
| `lib/booking.tsx`'s `statusBadge` | owner + every console role | a **fifth** entry in the four-entry `Map` (`:15-26`) |
| `BookingDetail.tsx` | owner | a **sixth** branch (`:201-205` derives five booleans from four statuses), a payment fact row, two markers and **MD1's** reschedule |
| `BookingsSection` row | owner | one muted payment line under the status `Badge` — **not** a second `Badge`. §8 **P-9** |
| **`/fake-pay`** | a developer, `import.meta.env.DEV` only | **new, dev-only, ~20 lines. F18 deletes it** (D21) |

**Zero new `packages/ui` components and zero new variants.** Everything here is `Card`, `Button`, `ButtonLink`, `Badge`, `Skeleton`, `VisuallyHidden`, **`Price`** and the shipped helpers (`safeHref`, `cn`, `focusRing`, `isolateLtr`, `statusBadge`, `bookingErrorText`). Checked against the shipped exports rather than assumed: **`packages/ui` has no `Field` and no `Alert`** — `role="alert"` is written inline by pages, which is what `BookPage.tsx` already does at `:952`, `:1028`, `:1044` and `:1414`. Design with what exists.

**Money is already solved and F19 writes none of it.** `Price` (`packages/ui/src/components/Price.tsx`) takes **`agorot: number`**, divides by 100 exactly once, formats through `Intl.NumberFormat("he-IL")` and emits `<bdi dir="ltr">{formatted} ₪</bdi>`. That *is* **D15** — integer agorot end to end, converted at render only, LTR-isolated — already shipped and already the only legal money renderer (tokens.md usage law 8; `qa-greps.sh` fails the build on a literal `₪` anywhere in `apps/storefront/src`). **No float, no decimal, no string, nowhere, and no new formatter.**

### Binding inheritances (obeyed, not restated)

From **`tokens.md` rev 1**: the gold law (`--color-gold-strong` never carries text — it appears in this feature **zero** times); focus ring on every control; ≥44×44 touch targets; no raw px in app code; `prefers-reduced-motion` is already global (`theme.css:155-163`); **usage law 8** (money only through `Price`); **usage law 9 — no countdowns, ever**, which is what §8 **P-3** turns into a ruling.
From **`design-config.md`**: quiet luxury, restraint over decoration; **anti-pattern list is a hard no** — nothing on a payment screen may read "tech product". No progress bars, no confetti, no lock icons, no card-brand logos.
From **`booking.md` (F14)**: the `h1` is the **step**, never the boutique (**R1**); the stepper is **inert** and `confirm` sits outside it; `PhoneOnly` is the flow's one named dead-end pattern (`BookPage.tsx:216`) and every terminal that cannot self-serve uses it; **no ticking number** anywhere (**R3**); instants render in the **boutique's** zone through the module-level `Intl` formatters, never the device's; no history-based back.
From **`manage-booking.md`**: the bride's page is the confirmation screen's **sibling, not a flow** — facts first, actions second, boutique contact last; the cancel is a **two-step inline reveal**, never a Modal.
From **`owner-bookings.md` (F15)**: **exactly one `Badge` per row region and the status owns it**; status is never colour alone — the Hebrew word carries it; **controls are ABSENT, not disabled**, for transitions the server forbids (`BookingDetail.tsx:432-435`: *"rendering buttons that answer 409 is a trap, and a disabled button with no explanation is worse"*); bare `<bdi>` on free text, `<bdi dir="ltr">` on numeric runs; the detail `h2` never carries the bride's name.
From **`manage-restyle.md`**: the three-register split — an **outage** is `text-ink-muted`, a thing-she-must-fix is `text-danger`, a nothing-failed **notice** is `text-warning-text`; inline muted cues over Toasts; **never override a `packages/ui` component's own utility from the call site** (F15 **F-6** — `cn()` is a plain join and the consumer loses).

### Explicitly NOT here — with the reasons

| Not shipped | Reason |
|---|---|
| **A hold countdown, a timer, a progress bar** | tokens.md **usage law 9** bans countdowns by name as *"the single clearest de-luxury signal in the Israeli market"*, and booking.md **R3** already declined a ticking number on the OTP cooldown for a second reason that applies here unchanged (i18next interpolation cannot carry the `<bdi>` a seconds run needs). §8 **P-3** |
| **A pause control on the poll** | SC 2.2.2 is **not engaged**: this poll repaints nothing until it has a terminal answer, and it stops by itself. §7.4 is the full argument, §8 **P-5** the ruling. This is a real divergence from F34/F57 and is argued, not assumed |
| **`usePoll`** | It **does not exist on main** — F57 is extracting it into `apps/manage` in another worktree. It would be the wrong hook anyway (a forever-loop with backoff, idle stop and a `{401,403}` terminal pair, for a console). §3 builds a bounded 40-tick loop in the page, which is ~12 lines |
| **A websocket / any realtime vendor** | Pre-decided #23. The spec says a plain interval |
| **A fifth stepper dot** | §8 **P-1** |
| **A receipt, an invoice, a קבלה** | Spec non-goal; the duty is the boutique's and is F21's audit row |
| **A refund figure, a sum, or any entitlement sentence on the cancel screen** | **MD3 is parked.** The neutral interim ships and names no number. **D16**'s computed number exists and is deliberately **not rendered by this deck** — the two sentences that will render it are the parked item |
| **An amount anywhere in the console** | **D18** gives `OwnerBookingRow` one field, `payment_status: str \| None`. It is a **status**, never a sum. `Price` appears on the storefront only. §8 **P-8** |
| **An owner "mark as paid" control** | Spec non-goal — a money mutation with no provider evidence |
| **A `/manage/payments` section** | **D18** declined it: it is F29's shape, and today it would be a router, a `ROUTES` row, an `OWNER_ONLY` row, a nav item and i18n for a section with one row in it |
| **Anything keyed on where a booking came from** | **C7** — `bookings.source` does not exist |
| **A new E2E spec** | The flow now ends at a third-party redirect Playwright cannot follow. The existing suite must stay green, unedited |

---

## 1. The pay step — mobile 375, each state

**375 is the primary case, not the fallback.** The storefront is a bride on a phone reached from an Instagram bio link, and this is the screen where she is asked for money.

⚠ **The diagrams below are drawn LEFT-TO-RIGHT, for legibility in a Markdown file. Every rendered screen is RTL** (`dir="rtl"` on `<html>`). So in the shipped app every run inverts: **inline-start is the physical RIGHT**. This deck ships **no prototype**, so these blocks are the sole visual source — a builder implementing the drawn order ships a mirrored screen that passes axe, passes every named vitest assertion, and reads wrong to the only people who will ever see it. The blocks are not redrawn in RTL because a hand-mirrored ASCII diagram is one more thing to keep true; this sentence is cheaper and says the same.

All four wireframes sit inside F14's shipped page shell — `mx-auto flex max-w-[640px] flex-col gap-6 px-4 pt-8 pb-16 md:px-6` (`BookPage.tsx`, identical to `/b/{token}`), inside `StorefrontLayout`'s `<main id="content" tabIndex={-1}>`, with the `A11yMenu` fixed trigger and **no `BookingCTA` bar** (the CTA is deliberately absent from `/book/*`).

### 1.1 State **A** — hand-off

```
+------------------------------------------------+
|  → חזרה לאוסף        <- NOT rendered on pay (§2.3)
|                                                |
|  מעבירים אותך לתשלום                            |  h1, font-display --text-2xl ink
|  ──── gold hairline (aria-hidden) ────          |  the shipped heading ornament
|                                                |
|  <VisuallyHidden><span role="status">           |  «מעבירים אותך לתשלום» — the ONE
|     booking.payHandoffStatus  </span>           |    announcement, fired once (§7.1)
|                                                |
|  עוד רגע נעביר אותך לדף התשלום המאובטח…          |  --text-base ink, max-w-[60ch]
|                                                |
|  +-- Card ----------------------------------+  |
|  |  סכום המקדמה                              |  |  --text-sm font-semibold ink-muted
|  |  <Price agorot={…} visible />              |  |  «500 ₪», bdi dir=ltr, ONE renderer
|  +-------------------------------------------+  |
|                                                |
|  [        מעבר לדף התשלום        ]              |  ButtonLink primary lg fullWidthMobile
|                                                |    rel="external", href=safeHref(url)
|  אם הדף לא נפתח מעצמו, אפשר להמשיך מהכפתור.     |  --text-sm ink-muted
+------------------------------------------------+
```

**The manual link is not a fallback that appears when the redirect fails — it is rendered from the first paint, always.** A page **cannot detect that a browser blocked its own navigation**: `window.location.assign()` in a popup-blocked or extension-hardened context fails silently, with no event, no exception and no callback. Anything conditional on "the redirect did not work" is conditional on a fact the client never learns. So the button is unconditional, it is the screen's primary control, and the automatic redirect is the *convenience* layered on top of it. If the redirect works she never reads the hint line.

**Three mechanical rulings on that one link**, each of which would otherwise ship broken:

- **`rel="external"`.** `shouldIntercept` (`router.tsx:168-207`) turns any same-origin `http(s)` anchor click into a client `pushState`, and its exclusion list explicitly honours `rel="external"`. In production the provider's URL is cross-origin and is not intercepted anyway; in **dev** `FakeGateway` returns a **root-relative** `"/fake-pay?session={id}"` (`payments/fake.py:121`), which *is* same-origin — so without `rel="external"` the dev link would be swallowed by the router. One attribute kills the whole class in both environments. §9 **F-1**.
- **`safeHref(redirect_url)` before the href and before `location.assign`.** The URL is provider-supplied and reaches an `href`; `safeHref` (`packages/ui/src/lib/url.ts`) is the shipped allowlist for exactly that, and *"React does NOT neutralise a `javascript:` href"* is its own comment. When it returns `undefined`, state **A** degrades to `PhoneOnly` — no link, no auto-redirect, the boutique's number.
- **The automatic redirect fires at most once per JS context**, guarded by a ref set *before* `location.assign`, and **only when the page was reached by the in-app navigation from `/book/verify`** — never on a document load. Back from the provider's page (or a bfcache restore, which restores refs in the same context) must land in state **B**, not bounce her straight back out. Without both guards, Back from the provider is an infinite redirect loop and the catalog becomes unreachable — the same trap `router.tsx:135-142` documents for guard redirects.

### 1.2 State **B** — awaiting, and **B-exhausted**

```
+------------------------------------------------+          +------------------------------------------------+
|  מאשרים את התשלום                               |          |  עוד לא קיבלנו אישור                            |
|  ──── gold hairline ────                        |          |  ──── gold hairline ────                        |
|                                                |          |                                                |
|  <VisuallyHidden><span role="status">           |          |  <p role="alert"> (§7.1: ONE alert, once)       |
|     «בודקות את התשלום» </span>                   |          |   אישור התשלום עדיין לא הגיע. אם התשלום עבר,     |
|                                                |          |   נשלח לך הודעה ברגע שהתור יאושר.               |
|  אנחנו בודקות מול חברת הסליקה שהתשלום נקלט.      |          |                                                |
|  זה לוקח כמה שניות.                              |          |  +-- PhoneOnly (the shipped pattern) --------+ |
|                                                |          |  |  ☎ 03-000-0000   ·   WhatsApp            | |
|  +-- Card ----------------------------------+  |          |  +-------------------------------------------+ |
|  |  <Skeleton variant="text" lines={2} />    |  |          |                                                |
|  +-------------------------------------------+  |          |  (no retry button — §3.3)                      |
+------------------------------------------------+          +------------------------------------------------+
```

**The webhook is authoritative; the return redirect is not.** She arrives here because a provider bounced her browser back, which proves only that she *left* the provider's page. The screen therefore claims nothing about her money until `payment-status` says `paid`, and its copy is about **us checking**, never about **us having received**.

**`aria-busy` on a div is announced by neither VoiceOver nor NVDA.** The shipped idiom is `Skeleton` (which is `aria-hidden`) plus `<VisuallyHidden><span role="status">` — `BookPage.tsx:961-966` writes exactly that, with the comment that says why. State **B** uses it and nothing else.

**B-exhausted is the state most likely to be forgotten, and it is not an error.** The poll runs out of attempts without a terminal answer (§3.2). Three things are true at that moment and the copy must not contradict any of them: her **hold is still live** (40 ticks ≈ 80 s against a 900 s hold), her payment may still land, and **D13's confirmation SMS is a real recoverer** — when the webhook arrives, the booking confirms and she is texted, whether or not this tab is still open. So the sentence is *"we haven't got the confirmation yet; if the payment went through we'll text you"*, and it is **true, not consoling**. It must never say "expired" — that is state **E**, and it is a different fact.

### 1.3 State **C** — paid

**The existing confirmed screen, unchanged.** `BookPage.tsx:1363-1428` renders it today and this feature does not touch one line of it: not the Card, not the two fact blocks, not `booking.confirmKeepScreen`, not the `booking.confirmCold` degrade. On a terminal `paid`, the pay step writes the four confirm facts into the flow's existing `booked` state (§2.2) and calls `navigate("/book/confirm" + suffix, { replace: true })` — `replace`, so Back does not walk her into a pay screen for a booking that is already confirmed. **Nothing is redesigned and nothing is re-read.** §8 **P-6**.

### 1.4 States **D** — declined — and **E** — expired

```
+------------------------------------------------+          +------------------------------------------------+
|  התשלום לא הושלם                                |          |  הזמן שמור לך פג                                |
|  ──── gold hairline ────                        |          |  ──── gold hairline ────                        |
|                                                |          |                                                |
|  <p role="alert">                               |          |  <p role="alert">                               |
|   התשלום לא הושלם, ולכן התור עדיין לא אושר.      |          |   לא הספקנו לקבל את התשלום בזמן, והמועד שוחרר.  |
|   המועד שבחרת עדיין שמור לך לזמן קצר —          |          |   אפשר לבחור מועד חדש.                          |
|   אפשר לחזור לאותו דף תשלום.                     |          |                                                |
|                                                |          |  [        בחירת מועד חדש        ]               |
|  [      חזרה לדף התשלום       ]                 |          |    ButtonLink secondary lg → /book/slot{suffix} |
|    ButtonLink secondary lg, rel="external",     |          |                                                |
|    the SAME safeHref(redirect_url)              |          |  → חזרה לאוסף                                   |
+------------------------------------------------+          +------------------------------------------------+
```

**D's copy must not imply a fresh attempt or a new price, because there is neither.** A retry re-enters the *same* hold: the create call converges (**D11b** — `live_pending_for_booking` returns the existing row with **no gateway call at all**) and **D8**'s stored `redirect_url` hands back the **same link**. So the label is *"back to the payment page"*, not *"pay again"*, and **no amount is re-rendered in state D** — showing the sum a second time is what makes a reader ask whether it is a second charge. The button carries the same `safeHref`ed URL the page already holds; it does not re-POST anything.

**E is the only state that sends her back into the picker**, and it goes to `/book/slot` carrying the dress suffix so an item-based booking keeps its binding. It makes **no claim about her original time still being free** — the seat was released by the sweeper and may be gone; the picker is the only thing that knows, and it will show her.

---

## 2. The state machine — anatomy and the control matrix

### 2.1 One route, five states, and the entry to each

| State | Entered by | Leaves to |
|---|---|---|
| **A** hand-off | in-app `navigate` from `/book/verify` after a 201 with `deposit_due: true` | the provider (browser navigation) |
| **B** awaiting | a **document load** of `/book/pay` — the return redirect, a manual reload, or Back from the provider | C / D / E / B-exhausted |
| **B-exhausted** | 40 ticks with no terminal answer (§3.2) | nothing — terminal, SMS is the recoverer |
| **C** paid | `payment_status === "paid"` | `/book/confirm` (`replace`) |
| **D** declined | terminal non-paid with the booking still `pending_payment` | back to the same hold |
| **E** expired | `booking_status === "cancelled"` **or** `payment_status === "expired"` | `/book/slot` |

**A and B are told apart by how the page was reached, not by a flag in the URL.** A is reachable only from an in-memory hand-off; every document load of `/book/pay` is B. This is the ruling that makes Back-from-the-provider safe (§1.1) and it needs no extra state anywhere.

**`/book/pay` is exempt from F14's step guard, exactly as `confirm` is.** `BookPage.tsx:513-531` bounces any step entered without `flow.startsAt` / `flow.typeId`, and `confirm` is exempt because *"the booking is already written, and there is no public endpoint to re-read it, so bouncing her to step one would lose the only record"* (`:501-503`). Every word of that is true of `pay` and more so — she arrives on a document load with the flow object empty by construction. **`pay` joins `slot` and `confirm` in the early-return.** Missing this is a redirect loop on the money surface.

### 2.2 What carries `payment_session_id` across the origin boundary — the deck's one mechanical ruling

**This is the problem no shipped screen in this product has.** The bride leaves `modryn.co.il`, pays on the provider's domain, and comes back on a **fresh document**: React state is gone, `flow` is empty, `booked` is `null`. `/book/confirm` already degrades for exactly this reason (`booking.confirmCold`, `BookPage.tsx:1364-1371`) — but there it is a rare reload, and here it is **every single time**.

**The return URL cannot carry the session id.** `return_url` is an *input* to `gateway.create_session` (`payments/base.py:126`) and the session id is minted *inside* it — the backend does not have the value at the moment it must supply the URL. And **`booking_id` must not be used**: `api.ts:305-308` records that the booking id is deliberately absent from every anonymous payload, and **D13** chose `provider_session_id` precisely because it is provider-minted, opaque and *"authorises nothing but a status read"*.

**Ruling: one `sessionStorage` record, written at hand-off, read on return.**

```
key    "modryn:pay"                     one record, overwritten, never a list
value  { payment_session_id,            D13's poll credential
         starts_at,                     the four /book/confirm facts, and ONLY these four
         appointment_type_name,
         dress_name, dress_size }
```

- **`sessionStorage`, not `localStorage`.** Per-tab, per-origin, cleared when the tab closes, and it survives an external round trip in that tab — which is the whole requirement. `qa-greps.sh` bans `localStorage` by name (its favorites rule) and this is not that; the record is deleted the moment the pay step reaches a terminal state.
- **It carries no identifier.** Not the booking id, not the manage token, not her name, not her phone. Everything in it is a fact her own browser already received in the 201 and everything in it is inert: possession of the record permits one anonymous status read and nothing else.
- **The four facts are what make state C warm.** Without them, a successful payment lands on `/book/confirm`'s **cold** branch — "call us" — immediately after she paid. With them, the pay step writes `booked` and the shipped confirm screen renders normally, with no change to it.
- **`?session=` in the query string overrides the record when present**, so a provider that does echo its session id, and D21's `/fake-pay` page (which we control and which returns to `/book/pay?session=…`), both work. `matchRoute` reads `pathname` only (`router.tsx:84, 127-130`), so a search string neither breaks routing nor triggers a re-render — it is read once from `window.location.search` at mount, which is correct for a value that only ever arrives on a document load.
- **Record missing *and* no `?session=` → state `PAY-nosession`** (§4). Designed, not spun.
- **Record missing but `?session=` present → the poll runs, and a terminal `paid` lands on `/book/confirm`'s shipped cold branch.** That degradation is free: the screen already exists, already handles exactly this case, and already offers the phone. No new state, no new copy.

**The ceiling, named**: a provider that returns into a *new* tab — some 3-D Secure app-switches on iOS do — lands on `PAY-nosession`. §9 **F-5**.

### 2.3 The control matrix

| State | Primary | Secondary | Back control | Announced |
|---|---|---|---|---|
| **A** | `ButtonLink primary lg` → the provider | — | **none** | `role="status"`, once |
| **B** | — | — | **none** | `role="status"`, once |
| **B-exhausted** | — | `PhoneOnly` (tap-to-call + WhatsApp) | — | `role="alert"`, once |
| **C** | *(the shipped confirm screen's own)* | | | |
| **D** | `ButtonLink secondary lg` → the same hold | `PhoneOnly` | — | `role="alert"`, once |
| **E** | `ButtonLink secondary lg` → `/book/slot{suffix}` | — | `Link` → the collection | `role="alert"`, once |
| **PAY-nosession** | — | `PhoneOnly` | `Link` → the collection | `role="alert"`, once |

**No `booking.backStep` control on this step, in any state.** F14 renders one on every step whose previous step is meaningful (`PREVIOUS_STEP`, `BookPage.tsx:68-71`); `pay`'s previous step is `verify`, and going back to it would offer to re-submit a booking that is already written. `confirm` handles this by rendering `booking.backToCatalog` instead, and the two terminal states here do the same. **A and B carry no exit at all, deliberately** — they are the two states where an exit is a control that abandons a live payment, and the manual link (A) or the phone (B-exhausted) is the affordance instead.

**Nothing on this step is ever `disabled`.** F14's **R7** already ruled that on this flow (*"the button is never disabled"*), and F15's absent-not-disabled rule says the same thing from the console side. A control that has nothing to do is not rendered.

### 2.4 The amount, rendered once

`<Price agorot={deposit_amount_agorot} visible hiddenLabel={…} />`, in state **A** only, inside the Card, under a `--text-sm font-semibold ink-muted` label. **`visible` is always `true` here** — `Price`'s hidden branch is the catalog's price-visibility toggle and has no meaning for a sum she is about to be charged. It appears **once in the whole feature**: not in B (nothing has changed about it), not in D (§1.4), not in E (there is nothing to pay), and **never in the console** (§8 **P-8**).

---

## 3. The poll, made visible

### 3.1 What she sees on a tick: nothing

| Tick outcome | What changes on screen | Announced |
|---|---|---|
| non-terminal (`pending` / `pending_payment`) — the common case | **nothing at all** | nothing |
| the fetch failed (network, 5xx, 429) | **nothing at all** — it counts as an attempt and is otherwise invisible | nothing |
| `paid` | the route changes to `/book/confirm` | the confirm screen's own |
| terminal decline | the whole screen becomes **D** | `role="alert"`, once |
| `cancelled` / `expired` | the whole screen becomes **E** | `role="alert"`, once |
| attempts exhausted | the whole screen becomes **B-exhausted** | `role="alert"`, once |

**A failed tick shows her nothing, and that is a ruling.** One dropped packet on a phone on a bus must not flash an error onto a screen that is about her money and then take it away two seconds later. The loop swallows failures, counts them as attempts, and lets **exhaustion** be the only thing that speaks. F34's console board makes the opposite call for the opposite reason — it has *correct data on screen* whose freshness it must stop vouching for; **this screen has no data on screen at all**, so there is no claim to withdraw.

**And that is why there is no freshness row, no «עודכן HH:MM», and no stale copy.** Every one of those exists to qualify a *displayed value*. There is no displayed value here.

### 3.2 The cadence, and the bound

| | Value | Why |
|---|---|---|
| First fetch | **immediately on mount** | the webhook often beats the browser back; an opening 2 s of spinner for an already-settled payment is 2 s of doubt on the money surface |
| Interval | **2 s** | fast enough that a normal settlement resolves before she reads the second sentence; slow enough that 40 ticks is 40 requests, not 400 |
| Bound | **40 attempts ≈ 80 s**, then **B-exhausted** | a bound, not a backoff — §3.3 |
| Backoff | **none** | a backoff exists to protect a server from a client that will never stop. This client stops in 80 seconds |
| `document.hidden` gate | **none** | it would silently pause the count and let a backgrounded tab sit "awaiting" indefinitely — the opposite of a bound |
| Cancellation | on unmount, and on the first terminal answer | one flag, checked before every `setState` |

**Both numbers are guesses until F18 and a real PSP**, and the spec says so in as many words under *"does not de-risk"* — the real latency between redirect-return and webhook is unknowable today. They are therefore **two module-level constants at the top of the file, named and adjacent**, not literals sprinkled through a hook. §9 **F-7**.

### 3.3 The two ways it stops

- **Terminally**, on an answer. The screen becomes C, D or E and the loop is dead — it cannot restart, because the terminal states render no control that re-enters it.
- **By exhaustion**, without an answer. **This is the state a design that only draws the happy path forgets**, and it is the one that must not lie. **No retry button**: a retry would restart a poll that has already asked forty times, and it would put a control in front of her that cannot change the outcome. What ships instead is the honest sentence plus `PhoneOnly` — the flow's shipped dead-end pattern (`BookPage.tsx:216`, used by four other terminals) — because the actual recoverer is **not on this screen**: it is **D13's confirmation SMS**, which fires whenever the webhook lands, hours later if need be, whether or not this tab still exists.

---

## 4. States — the single source for this feature

Every state, on every surface, with what is announced and where focus goes. **The list may not shrink.**

| # | State | Trigger | What she / the owner sees | Region / focus |
|---|---|---|---|---|
| **PAY-A** | Hand-off | 201, `deposit_due: true`, in-app nav | §1.1 — heading, body, the amount Card, the always-rendered manual link, the hint | `role="status"` in `VisuallyHidden`, written **once**. Focus lands on `<main>` as it does after every client navigation |
| **PAY-B** | Awaiting | document load of `/book/pay` with a session id | §1.2 left — heading, body, `Skeleton` in a Card | `role="status"` **once**, on mount only (§7.1) |
| **PAY-exhausted** | 40 ticks, no answer | §3.2 | §1.2 right — the honest sentence + `PhoneOnly`. **No retry** | `role="alert"`, `tabIndex={-1}`, **focused** |
| **PAY-C** | Paid | `payment_status === "paid"` | **the shipped `/book/confirm`** — warm if the §2.2 record survived, the shipped cold branch if not. **Not redesigned** | the confirm screen's own |
| **PAY-D** | Declined | terminal, booking still `pending_payment` | §1.4 left — no amount, "back to the payment page" onto the **same** hold | `role="alert"`, focused |
| **PAY-E** | Expired | `booking_status === "cancelled"` or `payment_status === "expired"` | §1.4 right — rebook from the normal picker; no claim about the old seat | `role="alert"`, focused |
| **PAY-nosession** | No record and no `?session=` | a new tab, a cleared session store, a hand-typed URL | heading + *"we couldn't identify the payment in this browser; if it went through we'll text you"* + `PhoneOnly` + a link to the collection. **Never a spinner** | `role="alert"`, focused |
| **PAY-hrefbad** | `safeHref(redirect_url)` returned `undefined` | a malformed / non-`http(s)` provider URL | state A **without** the link and **without** the auto-redirect: the amount Card plus `PhoneOnly`. A payment page we cannot safely open is a phone call | `role="alert"`, focused |
| **PAY-none (MD4)** | 201 with `deposit_due: false` on a deposit type | the provider was unreachable at checkout (**MD4** / **D11a**) | **`/book/pay` is never entered.** She goes to `/book/confirm` exactly as a non-deposit bride does, gets the ordinary confirmation SMS, and **is told nothing** — from her side nothing went wrong. Listed because "no screen" is a designed outcome here, not an omission | — |
| **SLOT-deposit** | A deposit type selected at `/book/slot` | `deposit_required: true` on the wire | the deposit is **disclosed** — one `--text-base ink` line naming the sum through `<Price>` — and the forward control is **live**. The shipped block (`booking.depositByPhone` + `ContactPanel` + a no-op forward) is **deleted**. §8 **P-7** | nothing announced |
| **MB-await** | The bride opens her manage link on an unpaid hold | `status === "pending_payment"` | a sixth view on `/b/{token}`: the facts block as usual, then *"this appointment is waiting for the deposit"*, then a `ButtonLink` to the checkout. **`אישור הגעה` and the cancel two-step are both SUPPRESSED** — today this page would render an unpaid hold as a standing appointment with a live cancel button (`ManageBookingPage.tsx:38, 318`) | `role="alert"`-free; the copy is a fact, not a failure |
| **MB-cancel** | She taps cancel on a booking that **has** a deposit | the reveal opens | **`manage.cancelConsequenceDeposit`** (MD3's neutral interim) replaces `manage.cancelConsequenceFree` at `:417`. `cancelConsequenceFree` survives **only** where no deposit exists. This is the one frontend edit F19 must not merge without | the reveal's shipped focus target (`:405`) is unchanged |
| **ROW-badge** | Any console list containing a held booking | `statusBadge("pending_payment")` | a **real** fifth entry — `warning` + «ממתין לתשלום». Today the four-entry `Map`'s raw-value fallback (`lib/booking.tsx:22-26`) renders the literal LTR string `pending_payment` inside a Hebrew RTL console | — |
| **ROW-payment** | An owner list row with a payment fact | `payment_status` non-null | **one muted `--text-sm` line under the status `Badge`, not a second `Badge`** (§8 **P-9**), in the register the fact deserves: ordinary → `ink-muted`; MD4's «נקבע ללא מקדמה» → `warning-text font-semibold`; paid-with-no-seat → `text-danger font-semibold` | — |
| **OD-await** | Owner opens a held booking's detail | `status === "pending_payment"` | **the sixth branch.** `BookingDetail.tsx:201-205` derives five booleans from four statuses, so today this booking satisfies **none** of them and renders with no state and **no action set at all** — an empty panel. It gains: the status `Badge`, the facts, a payment `<Fact>` row, one muted sentence saying no actions are available until the payment settles or expires, and **no controls** (every owner verb 409s on a hold) | nothing announced |
| **OD-noseat** | `payment_status === "paid"` on a `cancelled` booking | race rows #5 / #15 | the **action-needed** marker — `text-danger font-semibold`, above the action set — **and MD1's reschedule button behind it.** The marker without the button is the dead end **D18** names and **MD1** exists to close | the marker is a `<p>`, not an alert: the panel was opened deliberately |
| **OD-nodeposit** | MD4's compensated booking | `payment_status` carries the outage sentinel | «נקבע ללא מקדמה (חברת הסליקה לא הייתה זמינה)» in the **notice** register. No control — there is nothing she can do, and there is nothing wrong with the booking | — |
| **OD-cancelled-paid** | The same row, from the list | as OD-noseat | **MD1's** `booking.rescheduleCta` renders on a `cancelled` booking whose payment is `paid` — the *only* case where a non-`confirmed` booking carries an owner control, and it is the button D18's marker points at | the shipped reschedule dialog's own focus contract |
| **FP-dev** | A developer on `/fake-pay?session=…` | `import.meta.env.DEV` | two buttons — «שולם» / «נדחה» — that build the body with `fake_webhook_body`, sign with `sign_fake_webhook`, POST `/storefront/payments/webhook`, then return to `/book/pay?session=…`. **Dev-only, unstyled beyond the shipped `Button`, no i18n, no tokens. F18 deletes it** | — |

**Nineteen states, and the list may not shrink.** The five the spec's *Frontend changes* section enumerates are `PAY-A/B/C/D/E`; the fourteen others are what falls out of decomposing them against shipped code, and none is optional — `PAY-exhausted`, `PAY-nosession` and `PAY-hrefbad` are three different answers to "the happy path did not happen", and `OD-await` is an empty panel today.

**State precedence on the pay step.** A terminal answer always wins over the poll. `booking_status === "cancelled"` wins over any `payment_status` — the seat is gone and that is the fact she needs, whatever the money is doing. `PAY-nosession` and `PAY-hrefbad` are evaluated **before** the loop arms, so neither can co-exist with a spinner.

---

## 5. Breakpoints — 375 / 768 / 1440

**Mobile-first, and the pay step has exactly zero breakpoint branches of its own.**

| Width | What is different | Why |
|---|---|---|
| **375** (primary) | Page gutters `px-4`; the two `ButtonLink`s are `fullWidthMobile`; the amount Card is full width | 375 − 2×`--space-4` = **343px** of shell. The longest line on the screen is `booking.payHandoffBody` at `--text-base`; at 343px it runs four Hebrew lines, which is a paragraph, not a problem. No control competes for horizontal space with any other — there is at most one per screen |
| **375, long boutique name / long type name** | Nothing wraps that is not already free to wrap. **No truncation and no ellipsis anywhere** | The pay step renders neither: the type name lives on `/book/confirm`, which already handles it |
| **768** | Gutters `px-4` → `md:px-6`. **Nothing else moves** | The storefront column is capped at **640px** (`pageClass`, shared byte-for-byte with `/b/{token}`), so 768 has *more gutter*, not more column |
| **1440** | **Identical to 768** | The 640px reading column is the brand — a luxury reading column, not a dashboard. booking.md **§3.3** already ruled that 768 and 1440 are the same screen for this flow, and this step is not the exception |

**The console surfaces inherit F15's 720px cap** (`ConsoleShell.tsx:84`, in `packages/ui`) at every width, and **ROW-payment adds one `--text-sm` line to a row that already stacks vertically at 375** — the row's height grows by one line and nothing reflows sideways. `OD-await`'s panel is a shorter version of a panel that already renders at 375.

**One arithmetic check worth stating**: `<Price>` at `--text-base` renders «1,500 ₪» as a single 8-character LTR run inside its own `<bdi>`, under a `--text-sm` label, in a `Card` padded `--space-6`. At 343 − 48 = **295px** of card it cannot wrap and cannot collide with anything, because it is the only thing in the Card.

---

## 6. Component notes — exact tokens

| Element | Notes |
|---|---|
| Page shell | F14's shipped `pageClass` verbatim — `mx-auto flex max-w-[640px] flex-col gap-6 px-4 pt-8 pb-16 md:px-6`. **Not re-derived, not re-tuned** |
| `h1` | `<h1 className="font-display text-2xl text-ink">` + the shipped `<span aria-hidden="true" className="h-px w-12 bg-gold" />` hairline. **The `h1` is the state's own sentence** (booking.md **R1**: the `h1` is the step) — five states, five `h1`s, all static i18n strings |
| Body copy | `<p className="max-w-[60ch] text-base text-ink">`; secondary lines `text-sm text-ink-muted` |
| Amount Card | `<Card className="flex flex-col gap-1">` → `<p className="text-sm font-semibold text-ink-muted">` label, then `<Price agorot={…} visible hiddenLabel={t("booking.payAmountHidden")} />`. **The Card's own padding is never overridden** (F15 **F-6**) |
| Manual link (A) | `<ButtonLink href={safe} rel="external" variant="primary" size="lg" className="w-full sm:w-auto">`. `size="lg"`, not `md` — this is the screen's single act. `rel="external"` is load-bearing (§1.1) |
| Retry link (D) / rebook link (E) | `ButtonLink variant="secondary" size="lg"`, same width recipe. `secondary` not `primary`: neither is a forward step, both are recoveries |
| Back to collection | the shipped `<Link className={backLinkClass}>` with its `aria-hidden` `→` glyph, exactly as `/book/confirm` renders it |
| Awaiting placeholder | `<Card><Skeleton variant="text" lines={2} /></Card>` — `Skeleton` is `aria-hidden`, so announcing is the status span's job |
| The one status span | `<VisuallyHidden><span role="status">{t(key)}</span></VisuallyHidden>` — `BookPage.tsx:961-966`'s shipped idiom. **`aria-busy` on a div is announced by neither VoiceOver nor NVDA** and appears nowhere in this feature |
| Terminal alert | `<p role="alert" tabIndex={-1} ref={…} className="max-w-[60ch] text-base text-ink-muted">` — the **outage** register for exhausted / nosession (nothing failed that she caused), `text-warning-text` for declined and expired (a notice), and **never `text-danger`** on the storefront: danger is reserved for a thing the reader must fix, and none of these is hers to fix. There is **no `Alert` component**; this `<p>` is written inline, as four shipped call sites already do |
| `PhoneOnly` | the shipped component (`BookPage.tsx:216`), `muted` where it is a degrade rather than an instruction |
| Console status `Badge` | one new `Map` entry in `lib/booking.tsx:15-21` — `["pending_payment", { variant: "warning", labelKey: "booking.statusPendingPayment" }]`. **`warning`, not `danger`**: that file's own comment reserves `danger` for *"something the owner must fix"*, and an unpaid hold is not hers to fix — every owner verb 409s on it and the sweeper resolves it within a tick |
| Console payment line | `<p className="text-sm text-ink-muted">` / `text-warning-text font-semibold` / `text-danger font-semibold` by register (§4 ROW-payment). **Words, never a second `Badge`, never a glyph, never a dot** — F15's one-Badge-per-row-region rule, and F57 **P-5**'s three arguments against glyphs apply unchanged (an emoji is announced with a name the product did not choose; the console ships no icon vocabulary; a coloured dot beside a coloured pill teaches the reader to stop reading the word) |
| Console payment fact | `<Fact label={t("booking.paymentLabel")}>` — the shipped detail-panel row, the same one `checked_in_at` / `cancelled_at` / `cancelled_by` already use (`BookingDetail.tsx:371-383`). No new pattern |
| MD1's reschedule | the **shipped** `booking.rescheduleCta` `Button variant="secondary" size="md" fullWidthMobile` and the **shipped** reschedule dialog. MD1 widens a *predicate*, not a control |
| Bride's manage page | the awaiting view reuses `Facts` unchanged, then one `<p className="text-base text-ink">`, then `<ButtonLink href={safe} rel="external" className="w-full sm:w-auto">`. The `confirmed`/`cancelled`/`past` branches are untouched |
| `/fake-pay` | two `Button variant="secondary" size="md"`, no Card, no heading ornament, no Hebrew, behind `import.meta.env.DEV` so Vite's static replacement drops it from the production bundle. It needs a real `matchRoute` arm (`router.tsx:84-114`), because a client navigation to an unmatched path falls through to **the catalog** |

**Contrast, from the tokens ledger — not eyeballed.** ink 15.24 on cream · ink-muted 6.15 · warning-text 5.70 · danger 6.78 · success 6.10 · focus ring 5.57 · white-on-danger ≈7.0 (the shipped `Button danger` pairing). **This feature introduces no new colour pair, no new token and no gold beyond the shipped `h1` hairline.** The ledger needs no addition at this gate.

### 6.1 Strings — the keys this feature declares

`ar.ts` takes the **same Hebrew value**, untranslated (pre-decided #47). The he/ar key-parity assertion F17 added to `i18n.test.ts` is what catches a missing one.

| Key | Hebrew | Where |
|---|---|---|
| `booking.payTitle` | מעבירים אותך לתשלום | A `h1` |
| `booking.payHandoffBody` | עוד רגע נעביר אותך לדף התשלום המאובטח. המועד שבחרת שמור לך עד לסיום התשלום. | A |
| `booking.payHandoffStatus` | מעבירים אותך לתשלום | A, `role="status"` |
| `booking.payAmountLabel` | סכום המקדמה | A |
| `booking.payAmountHidden` | *(unreachable — `visible` is always true; declared only because `Price` requires the prop)* | A |
| `booking.payManualCta` | מעבר לדף התשלום | A |
| `booking.payHandoffHint` | אם הדף לא נפתח מעצמו, אפשר להמשיך מהכפתור. | A |
| `booking.payAwaitTitle` | מאשרים את התשלום | B `h1` |
| `booking.payAwaitBody` | אנחנו בודקות מול חברת הסליקה שהתשלום נקלט. זה לוקח כמה שניות. | B |
| `booking.payAwaitStatus` | בודקות את התשלום | B, `role="status"` |
| `booking.payPendingTitle` | עוד לא קיבלנו אישור | B-exhausted `h1` |
| `booking.payPendingBody` | אישור התשלום עדיין לא הגיע. אם התשלום עבר, נשלח לך הודעה ברגע שהתור יאושר. | B-exhausted |
| `booking.payDeclinedTitle` | התשלום לא הושלם | D `h1` |
| `booking.payDeclinedBody` | התשלום לא הושלם, ולכן התור עדיין לא אושר. המועד שבחרת עדיין שמור לך לזמן קצר — אפשר לחזור לאותו דף תשלום. | D |
| `booking.payRetryCta` | חזרה לדף התשלום | D |
| `booking.payExpiredTitle` | הזמן שמור לך פג | E `h1` |
| `booking.payExpiredBody` | לא הספקנו לקבל את התשלום בזמן, והמועד שוחרר. אפשר לבחור מועד חדש. | E |
| `booking.payRebookCta` | בחירת מועד חדש | E — **distinct from `manage.rebookCta`**, which lives on the bride's manage page and is that page's key |
| `booking.payNoSessionTitle` | לא הצלחנו לזהות את התשלום | PAY-nosession `h1` |
| `booking.payNoSessionBody` | לא הצלחנו לזהות את התשלום בדפדפן הזה. אם התשלום עבר, נשלח לך הודעה עם אישור התור. | PAY-nosession, PAY-hrefbad |
| `booking.paySlotDeposit` | לתור הזה נגבית מקדמה | SLOT-deposit — the disclosure line beside `<Price>` |
| `manage.awaitingPayment` | התור ממתין לתשלום המקדמה. עד שהתשלום יושלם המועד שמור לך, אבל התור עדיין לא אושר. | MB-await |
| `manage.awaitingPaymentCta` | מעבר לדף התשלום | MB-await |
| **`manage.cancelConsequenceDeposit`** | **הפיקדון מטופל בהתאם למדיניות הביטולים של הסלון.** | MB-cancel — **MD3's interim, verbatim from the spec.** Replaced by the two parked variants when they land: a value swap, no structure |
| `booking.statusPendingPayment` | ממתין לתשלום | ROW-badge, OD-await |
| `booking.paymentLabel` | מקדמה | OD `<Fact>` label |
| `booking.paymentPaid` | שולמה | OD, ROW |
| `booking.paymentPending` | ממתינה | OD, ROW |
| `booking.paymentExpired` | פגה | OD, ROW |
| `booking.paymentNoSeat` | שולמה מקדמה — המועד כבר לא פנוי | OD-noseat, ROW — the **action-needed** sentence |
| `booking.paymentNoDeposit` | נקבע ללא מקדמה (חברת הסליקה לא הייתה זמינה) | OD-nodeposit, ROW — **MD4**'s marker |
| `booking.awaitingPaymentDetail` | התור ממתין לתשלום המקדמה. אין פעולות זמינות עד שהתשלום יסתיים או יפוג. | OD-await |

**Deleted**: `booking.depositByPhone` (`he.ts:173`), together with the block it explains. §8 **P-7**.

### 6.2 `qa-greps.sh` is a blocking gate and this design lives inside it

Read, not assumed. Over `apps/storefront/src` it fails the build on: `ml-|mr-|pl-|pr-|left-|right-|text-left|text-right|border-l-|border-r-`; any 6-digit hex; a literal `₪`; `localStorage`; `history.back|navigate(-1)|router.back`; `href="#"`. Separately it flags unzoned date reads across **all three** source trees.

Consequences this deck accepts by construction: **logical properties only** (`ps-*`, `pe-*`, `ms-*`, `me-*`, `text-start`, `border-s-*`, `padding-block-end`); **no hex** — every colour is a token utility; **no `₪`** — it is inside `Price` in `packages/ui`, which the grep does not cover, and this feature writes none; **`sessionStorage`, never `localStorage`** (§2.2); **no back()** — the two exits are real `<Link>`s. `Intl.NumberFormat` is untouched by the date grep, and the pay step reads **no dates at all** — the only instants in this feature render on `/book/confirm` and `/b/{token}`, through their existing zoned formatters.

---

## 7. The a11y contract — IS 5568 / WCAG 2.0 AA is a legal requirement (pre-decided #38)

The axe job is **blocking CI**, and it is **not sufficient** — three of the rows below are invisible to it.

### 7.1 Live regions — a polling screen that never announces a tick

**The specific failure to design against is a live region that re-announces on every tick.** A `role="status"` written every 2 seconds for 80 seconds is a screen reader reading the same sentence forty times over a payment. The strategy, stated as a rule:

| Region | ARIA | Carries | When it is written |
|---|---|---|---|
| The status span (**A**, **B**) | `role="status"` inside `VisuallyHidden` | `booking.payHandoffStatus` / `booking.payAwaitStatus` | **once, on mount, and never again.** The poll **may not write into it** |
| The terminal paragraph (**exhausted**, **D**, **E**, **nosession**, **hrefbad**) | `role="alert"`, `tabIndex={-1}` | the state's own sentence | **once**, when the state is entered. It cannot repeat, because the loop is dead by then |
| Everything else | **no live attributes at all** | the heading, the body, the amount, the links | off |

**Three properties make the "never re-announced" claim structural rather than a promise:**

1. **The poll has no write path into any live region.** It sets one state variable; a non-terminal answer changes nothing, so React renders the same tree and no DOM mutation occurs inside `role="status"`.
2. **"Write" means write, not change.** F34's **F-7** applies unchanged: assigning a string to a text node runs string-replace-all and produces a real `childList` mutation inside `role="status"` **even when the two strings are byte-identical**. So the status text is a **constant per state**, not a value recomputed each tick — and the frontend test must drive **several consecutive non-terminal ticks with the region already populated**, because a single-tick assertion passes against the broken version.
3. **`role="alert"` fires at most once per page life**, in exactly one of five mutually exclusive terminal states, each of which stops the loop.

### 7.2 Focus

- **After a client navigation, focus lands on `<main id="content" tabIndex={-1}>`** — `StorefrontLayout`'s shipped behaviour, unchanged. Entering A takes it; entering C takes it.
- **A state transition inside `/book/pay` moves focus to the new terminal `role="alert"` paragraph**, keyed on the state rather than raised inside the handler: the alert node does not exist yet when the state is set. **This is the path that gets forgotten** — F34 compensated its success path and restored nothing on its failure path, and that was a Level A defect found in review, not in CI. Here **every** transition out of B is a "failure path".
- **Focus is never moved by a tick.** Forty focus moves during a payment is the worst version of this screen.
- **Nothing on the pay step ever unmounts a focused control**, because A's only control is the thing that navigates away.
- **Tab order**: skip link → `#content` → the state's one control (if any) → `PhoneOnly`'s links → footer. There is no second control anywhere on this step, in any state.
- **The auto-redirect must not race a screen reader.** It fires after the status span is in the DOM, one paint later — not synchronously in the same commit — so «מעבירים אותך לתשלום» is announced before the document is replaced.

### 7.3 Motion

Nothing on this feature animates except the `Skeleton` pulse in state B, already frozen globally by `theme.css:155-163` under `prefers-reduced-motion`. **No spinner, no progress bar, no pulse on the amount, no transition between states** — a state change here is a different screen, not a fade. **This feature adds no motion rule because it adds no motion.**

### 7.4 The rest of the floor, SC by SC

**SC 2.2.1 Timing Adjustable (Level A) — the row a human reviewer would have raised, discharged here.** There *is* a time limit: `deposit_hold_seconds`, default **900**. Three things resolve it and all three must hold:

1. **The limit is not on this page.** The 15 minutes run while she is on the **provider's** hosted page. Nothing on a MODRYN screen asks her to complete anything under a clock.
2. **It meets 2.2.1's *essential* exception**: extending a seat hold on request would invalidate the activity for every other bride looking at that slot — the hold exists precisely to be finite. This is the same class as an auction close, which the criterion names.
3. **The consequence of exceeding it is not loss.** **MD1** honours a late payment: the deposit follows her to a new time, **MD2** texts her within a worker tick, and if the seat is still free **D5** rebinds her to it automatically. A bride who takes twenty minutes does not lose her money and is not silent-failed.

**And we deliberately communicate no urgency**: no countdown, no "hurry", no timer (§8 **P-3**). A criterion about time pressure is best met by a screen that applies none.

**SC 2.2.2 Pause, Stop, Hide (Level A) — named, and argued as NOT engaged.** F34 and F57 both ship a pause control because they auto-update *content presented in parallel with other content*, forever, every five seconds. **This screen does neither**: the poll changes nothing on screen until it has a terminal answer (§3.1), so there is no auto-updating content to pause; and it **stops by itself in ~80 seconds** (§3.2), so it is not "presented in parallel" with anything for a duration a user could need to suppress. A pause control here would pause a fetch whose only visible effect is to end the screen she is waiting to end. **This is a divergence from two shipped surfaces and it is a ruling, not an omission** — §8 **P-5**, and axe cannot check either side of it.

**SC 4.1.3 Status Messages** is WCAG **2.1** AA and therefore sits *outside* the IS 5568 / 2.0 legal floor. §7.1 satisfies it anyway, because the mechanism costs nothing and the failure mode (a silent state change on a payment screen) is the one that matters most here.

- **SC 1.4.1 Use of Colour** — nothing is signalled by colour alone. Every console payment state carries a **Hebrew word**; the three registers are reinforcement. Every storefront state carries an `h1` sentence.
- **SC 1.4.3 Contrast** — §6's ledger. No pair below 4.5:1 for text; the `h1` hairline is decorative `--color-gold` and carries nothing.
- **SC 2.1.1 Keyboard** — every state's single control is a real `<a>` or `<button>`; nothing is a `div` with a handler; nothing is reachable by pointer only.
- **SC 2.4.6 Headings and Labels** — one `h1` per state, naming the state. No `h2` on the pay step: it has no groups.
- **SC 2.4.7 Focus Visible** — `focusRing` is applied unconditionally by `Button.tsx:62` and shared by `ButtonLink`. Nothing here sets `outline: none`.
- **SC 2.5.3 Label in Name** — the two `ButtonLink`s carry no `aria-label` at all, so the accessible name *is* the visible label and the criterion holds by construction. No `aria-label` is added anywhere in this feature.
- **SC 2.5.5 / target size** — `size="lg"` on both links, `fullWidthMobile` at 375; `size="md"` (`min-h-11` = 44px) on every console control. **`size="sm"` (`min-h-9` = 36px) appears nowhere.**
- **SC 3.3.1 Error Identification** — state D names what happened («התשלום לא הושלם») and what is still true (the hold survives) in the same paragraph, in text, in the alert.
- **Bidi** — **every numeral and Latin run is wrapped in `<bdi dir="ltr">`**: the amount (inside `Price`, already), the session id (**never rendered**), times and dates (through the shipped formatters on the surfaces that show them). **Owner- and bride-authored text takes a bare `<bdi>`** — the appointment-type name, the dress name, the boutique name. **`dir="ltr"` on Hebrew is itself a defect and it is the worse one because it looks deliberate** (`BookingDetail.tsx:252-254` says so in the shipped source). `isolateLtr` (`lib/booking.tsx:32`) emits `<bdi dir="ltr">` and is therefore **for numeric runs only** — it must not touch a name (F57 **F-11**, inherited).
- **An `axe` pass** runs over each of the five pay states and over the two edited console branches — **and it is explicitly not sufficient**: it cannot see 2.2.1, cannot see 2.2.2, cannot see a live region written on a timer, and cannot see a bidi defect. The named frontend tests are the only coverage of all four.

---

## 8. RESOLVED decisions — self-approved with the design gate, 2026-08-03

**All eleven carry a resolution and none is an open question.** Each keeps its reasoning, because the reasoning is what a later feature would have to overturn to reopen it. **The Hebrew remains the user's to edit post-merge.**

| | Resolution |
|---|---|
| **P-1** | **No fifth stepper dot.** The stepper is untouched |
| **P-2** | **The manual link is unconditional**, not a fallback that appears on failure |
| **P-3** | **No countdown, no hold timer, no elapsed clock** |
| **P-4** | **`sessionStorage` carries the session id and the four confirm facts**; `?session=` overrides |
| **P-5** | **No pause control on the poll** — SC 2.2.2 is not engaged, and it is argued |
| **P-6** | **`/book/confirm` is not redesigned.** PAY-C navigates to it |
| **P-7** | **The slot step's deposit dead-end is deleted**, and `booking.depositByPhone` with it |
| **P-8** | **The console renders a payment STATUS, never a sum** |
| **P-9** | **The payment fact is words, not a second `Badge`** |
| **P-10** | **MD3's interim ships; the two variants stay parked** |
| **P-11** | **`/fake-pay` is an SPA route behind `import.meta.env.DEV`**, not a server route |

- **P-1 — RESOLVED: `STEPPER_STEPS` stays four, and `pay` sits outside it exactly as `confirm` does.** `BookPage.tsx:57-66` calls `confirm` *"terminal and outside the stepper, which is why there is no fifth label"*, and the same is true here for a stronger reason: **by the time she reaches `/book/pay` the booking is already written** (D11 — created first, in `pending_payment`), so `pay` is not a step *toward* a booking. Adding a dot would also put a fifth item on the stepper of every earlier step for **every** bride, including the majority who will never see a deposit. Declined.
- **P-2 — RESOLVED: the `ButtonLink` renders from the first paint in state A, in every browser.** The alternative — render it only after the automatic redirect fails — is **unbuildable**: `location.assign` reports nothing when a browser refuses it. There is no event, no exception and no timeout that distinguishes "blocked" from "about to navigate". Anything conditional on that fact is conditional on a fact the client never has. So the button is the primary control and the redirect is the courtesy. The cost is one visible button on a screen most brides never read; the cost of the alternative is a bride stranded on a page with no way forward on the one surface where her money is about to move.
- **P-3 — RESOLVED: nothing on any screen states or implies how long the hold has left.** tokens.md **usage law 9** bans countdowns by name as the clearest de-luxury signal in this market; `design-config.md` lists the same family under hard-no anti-patterns; booking.md **R3** already declined a ticking number on this very flow, adding the mechanical reason (i18next interpolation cannot carry the `<bdi>` a seconds run needs, so the Hebrew word order would have to be pinned in TSX — exactly where bidi layouts break); and §7.4 shows the criterion the timer would supposedly serve is better met by applying no pressure. **What a timer buys — the reassurance that the seat is held — is bought instead by one sentence in state A** («המועד שבחרת שמור לך עד לסיום התשלום»), which cannot go stale and cannot tick.
- **P-4 — RESOLVED: one `sessionStorage` record, `modryn:pay`, holding the session id and the four `/book/confirm` facts, and nothing else.** §2.2 is the argument. Declined: **the return URL** (the backend does not have the session id when it must supply the URL — it is minted inside `create_session`); **the booking id** (`api.ts:305-308` keeps it off every anonymous payload deliberately, and D13 chose the provider session id precisely because it authorises nothing but a status read); **`localStorage`** (banned by `qa-greps.sh`, and wrong — the record must die with the tab); **widening the poll response with the confirm facts** (an API change to solve a client-state problem, and the client already has the facts). The record is deleted on every terminal state.
- **P-5 — RESOLVED: no pause control, and the reason is that SC 2.2.2 is not engaged.** §7.4 is the argument. **Recorded as a deliberate divergence rather than drift**, because two shipped surfaces in this product carry one and a reviewer will notice: F34's board and F57's panel repaint real content every five seconds for an entire shift; this screen repaints nothing and stops in eighty seconds. If a later change makes the pay screen render live content — a status line that updates, a "still checking (3)" counter — **2.2.2 becomes engaged and this ruling is void.** That is the trigger to watch, and it is why the state's copy is a constant (§7.1).
- **P-6 — RESOLVED: `/book/confirm` is not opened.** It already renders the four facts, the keep-this-screen instruction, the dress-dropped notice and the cold degrade, and it already handles the exact "no client state" case P-4's record exists to avoid. Reaching it with `booked` populated is a state write, not a screen change. **Declined**: a sixth "paid" screen on `/book/pay` — two confirmation screens for one booking, differing only in how she arrived.
- **P-7 — RESOLVED: `depositBlocked` (`BookPage.tsx:478`) and its no-op forward (`:549-553`) are deleted, along with `booking.depositByPhone` (`he.ts:173`) and the inline `ContactPanel` reveal.** That block exists because F14 had no way to take a deposit; F19 is the feature that gives it one, and leaving the block in place would mean the flow refuses to book the very appointments it can now charge for. **The one real consequence, stated rather than glossed**: after **D10**/**D19**, `deposit_required` on the wire means *"a deposit will be charged now"* — it is already false when `deposits_enabled` is off or the gateway is not connected — so a boutique that had deposits switched off **loses the "call us to arrange the deposit" copy and starts taking those bookings online with no deposit**. That is not a bug; it is **F17's Gate 1 Q1 ruling applied** (*"a dead calendar is worse than silently not collecting"*), and MD4 takes the same position for the outage case. It is nonetheless a visible change to a live storefront and it is filed as §9 **F-6**.
- **P-8 — RESOLVED: no money renders anywhere in `apps/manage`.** **D18** gives `OwnerBookingRow` exactly one field, `payment_status: str | None`, and rendering a sum would need a second field, a `Price` import into the console, and a decision about whether it is the amount held or the amount owed — the second of which nobody can answer before F29. The owner learns *that* a deposit is paid, expired, or was never taken; **what it was worth is the provider's dashboard's job** until refunds exist.
- **P-9 — RESOLVED: the payment fact is a `--text-sm` words line under the status `Badge`, not a second `Badge`.** This **diverges from the brief's word "badge" and the divergence is deliberate.** F15's rule — inherited by F34 and F57 and written into `lib/booking.tsx:12-14` — is *exactly one `Badge` per row region, and the status owns it*; a second pill in a 295px row at 375 teaches the reader to scan colours instead of words, which is precisely how a `warning` payment marker gets mistaken for a `warning` no-show. F57 **P-2** is the same ruling arrived at from the other side (the role is muted words; the single Badge is the status). On the **detail** panel the fact is a shipped `<Fact>` row, which is the pattern `checked_in_at` and `cancelled_at` already use. **No new `Badge` variant, no new component, no glyph, no dot.**
- **P-10 — RESOLVED: `manage.cancelConsequenceDeposit` ships with MD3's neutral interim; `manage.cancelConsequenceFree` survives only on a booking with no deposit.** The parked item is two approved Hebrew sentences that tell a bride who paid ₪500 whether that ₪500 comes back — a consumer-protection representation an engineer may not invent. The interim is true under **every** possible answer to the parked question, it promises nothing in either direction, the boutique's policy line is already on that screen, and when the two variants arrive it is a **value swap on one key** plus one branch on **D16**'s already-computed number: no schema, no API, no logic, no migration. **The hard constraint, unchanged: F19 must not merge with `cancelConsequenceFree` rendering on a deposit booking.** The interim satisfies it; the park does not.
- **P-11 — RESOLVED: `/fake-pay` is a `matchRoute` arm in `apps/storefront/src/router.tsx`, guarded by `import.meta.env.DEV`.** Not a FastAPI route: `main.py`'s `_register_spas(app)` must stay the **last** registration (**C4**, `:1057`), and a backend route would either precede it (fragile) or be shadowed by it (dead). Vite statically replaces `import.meta.env.DEV`, so the arm and the page are dead-code-eliminated from the production bundle — the guard is a build-time fact, not a runtime check. It is **unstyled beyond the shipped `Button`, carries no Hebrew and no tokens**, so nobody can mistake it for product; it lives in the graded tree so it obeys `qa-greps.sh` and nothing else. **F18 deletes it.**

## 9. ⚠ FINDINGS

- **F-1 — `FakeGateway` returns a ROOT-RELATIVE `redirect_url`, and the storefront's click delegation would swallow it.** `payments/fake.py:121` builds `"/fake-pay?session={id}"`, and `shouldIntercept` (`router.tsx:168-207`) turns any same-origin `http(s)` anchor click into a client `pushState`. Without a `matchRoute` arm for `fake-pay`, that pushState lands on **the catalog** (`:193-196`: everything unmatched is the collection) — so in dev the manual link would silently take the developer to the dress grid, and the automatic `location.assign` would do the same on a full load. **Fixed here by two things, both cheap**: `rel="external"` on the link (the exclusion list already honours it — `:184-191`) and P-11's route arm. **Recorded rather than folded in silently, because a real provider's absolute cross-origin URL never reproduces it** — the only environment where this breaks is the only environment where the flow can be exercised before F18. *Owner: team. Trigger: the first dev run of the flow.*
- **F-2 — the spec's frontend line citations for the bride's page are stale, in the same way C2/C3 are stale for the backend.** It cites `ManageBookingPage.tsx:291` for the cancelled branch and `:390` for `manage.cancelConsequenceFree`; the shipped file has them at **:318** and **:417**. `:38` (`const CANCELLED`) is correct. The **rulings are unaffected** — this is the F34-shaped drift the C-corrections already document, arriving at a fifth file. *Owner: team. Trigger: the build, which should re-grep rather than trust any line number in either document.*
- **F-3 — `payment_status: str | None` cannot distinguish MD4's booking from an ordinary one, and the marker is unrenderable until it can.** **D18** says the field carries *"one more value on one field"* for MD4's *"booked without a deposit"* marker — but MD4's compensating transaction leaves **no `payments` row at all** (D11a: `open_deposit` raised before the insert), so the field is `None`, which is byte-identical to a plain non-deposit booking. **The frontend cannot invent the distinction**: it does not know whether a deposit was ever due. **This deck's requirement on the backend: `payment_status` must carry an explicit sentinel** (`"unavailable"`, or whatever D11a's audit row is keyed on) **rather than `None`** for a booking whose deposit was skipped by the outage path. Without it, `OD-nodeposit` and its `ROW-payment` line cannot render — and the spec itself notes the MD4 marker *"has no other failing test"*, so nothing else would catch it. *Owner: team. Trigger: the plan's backend task for D18 — this must be settled before the frontend task starts.*
- **F-4 — the Arabic bundle carries Hebrew on a money surface.** Pre-decided #47 makes `ar.ts` Hebrew standing in until F45, which is a known and accepted platform-wide position — but F19 is the first feature where the untranslated strings tell a customer that a payment failed or that her deposit is subject to a policy. The he/ar **key**-parity test guards presence, not meaning. Nothing is done here; it is filed so the F45 copy pass knows this feature's 30-odd keys are the ones to translate first. *Owner: team. Trigger: F45.*
- **F-5 — a provider that returns into a NEW tab lands on `PAY-nosession`.** `sessionStorage` is per-tab, and some 3-D Secure app-switch flows on iOS return to a fresh tab rather than the originating one. The state is designed and honest (*"if the payment went through we'll text you"*), and **D13's confirmation SMS is a real recoverer**, so this is a degraded outcome rather than a failure. It is nonetheless the difference between "she sees her confirmation" and "she waits for a text", and it cannot be measured before a real provider. *Owner: team. Trigger: F18, then F21 UAT — count how often `PAY-nosession` is reached.*
- **F-6 — deleting the deposit dead-end silently changes what a boutique with deposits switched off does.** She keeps taking those bookings and stops collecting deposits, with no "call us" copy anywhere, because after D10/D19 the wire no longer tells the storefront that the type *has* a deposit policy — only whether one will be charged. This is **F17's Q1 ruling applied** and MD4 takes the same position, so it is coherent; it is still a visible behavioural change to a shipped public flow, made by deleting a string. §8 **P-7**. *Owner: user, via F21 UAT. Trigger: the first pilot boutique that switches deposits off.*
- **F-7 — the poll's two numbers (2 s, 40 attempts) are guesses, and `PAY-exhausted` is what happens if they are wrong.** The spec's own *"does not de-risk"* section says the real latency between redirect-return and webhook is unknowable until a production PSP. If it is routinely **over 80 seconds**, the exhausted screen stops being an edge case and becomes the ordinary post-payment experience — and it reads, correctly but unfortunately, like a non-answer. Both numbers are module-level constants (§3.2) so the fix is a one-line change, but **nothing will tell us it is needed except a pilot bride's phone call**. *Owner: team. Trigger: F18's first real settlement; F21 UAT.*
- **F-8 — axe sees none of the four things most likely to be wrong here.** It has no rule for SC 2.2.1 or 2.2.2 (both are human judgements), it cannot see a live region written on a timer (the region is valid; the *frequency* is the defect), and it cannot see a bidi defect (`dir="ltr"` on a Hebrew name is valid HTML). So the **named frontend tests are the sole coverage of a legal requirement** on this run's second self-approved gate: several consecutive non-terminal ticks with the status region already populated assert nothing is re-announced (§7.1); a terminal transition asserts focus reaches the alert; a rendered-DOM assertion checks no `<bdi>` wrapping a name carries `dir`. **They must not be cut as redundant with the axe assertion** — this is F57 **F-8** at the next surface, and it applies harder because there is no prototype and no `design-critic` behind this deck either. *Owner: team. Trigger: the code-review pass, and every later tidy-up of "redundant" a11y tests.*
- **F-9 — `deposit_required` changes meaning on the wire without changing its name.** Today it means *"this appointment type has a deposit policy"*; after D19 it means *"a deposit will be charged for this booking, now"* — the four-term predicate having already been evaluated server-side. `AppointmentTypeRow`'s docstring (`storefront/schemas.py:171-186`) still describes the old sense. The next reader of that field will get it wrong. **Mitigation inside this deck's control**: the storefront reads it through exactly **one** derived `depositDue` constant in `BookPage`, never inline at a call site, so there is one place to correct. *Owner: team. Trigger: the code-review pass — the schema docstring is a two-line fix and belongs in this PR.*
- **F-10 — until MD3's variants land, a bride who paid ₪500 and cancels reads a sentence that names no sum.** The interim is truthful, it is strictly better than today's shipped *"cancelling carries no cost"*, and the boutique's own policy line sits directly above it (`ManageBookingPage.tsx:405-412`) — but it does not tell her what she gets back, and **D16**'s number, which is computable today, is deliberately not rendered by this deck. F21 must check whether the two variants have landed; **if they have not, F21 records the interim as still-shipping rather than treating this as a closed finding** (the spec's own instruction under MD3). *Owner: user. Trigger: the parked copy landing; F21 UAT if it has not.*
