# Screen: Client Portal (F24 — `/portal`, Epic E5)

**Date**: 2026-08-06 · **Status**: DESIGN GATE OPEN — awaiting critic + copy approval · **Designer**: Claude (design subagent)
**Consumes**: `.planning/specs/client-portal.md` (Gate 1 standing-approved, D1–D8) · tokens rev 1 · `packages/ui` as shipped
**Copy**: every Hebrew row below needs APPROVAL. Register: calm, feminine address, **no exclamation marks** (pre-decided #5).

---

## 0. Scope

One storefront SPA route, `/portal` (RouteName `portal`, `document.portal` title), inside `StorefrontLayout` (skip link, `main#content`, footer, A11yMenu inherited). Four surfaces on that route: login panel, "My Bookings" dashboard, booking detail, bell panel. Plus one addition to the existing `/b/{token}` page: the `.ics` download control (spec D5). Out of scope: waitlist surfaces (F22/F23), profile editing, any change to the tokenized page's existing actions.

**Binding inheritances from `booking/booking.md` and `manage-booking.md`** — obeyed, not restated: three-gold law; R19 bidi isolation (`<bdi dir="ltr">` islands for every numeral/date/phone); §7.3 `Intl.DateTimeFormat('he-IL', { timeZone: Jerusalem })`; R30 (loading announces via the nested `VisuallyHidden > span[role="status"]` shape — manage-booking §0 ruling verbatim); R16/§12.3 (live regions announce discrete events only; `role="status"` good news, `role="alert"` failures); qa-greps physical-direction ban; the house focus rule (**the mover is the state change that mounted the target**); router contract (focus lands on `main#content` after navigation).

**The OTP block is the verify step's, copied not re-derived** (the same ruling waitlist-join §0 took): single code field (never six boxes), `autocomplete="one-time-code"`, `dir="ltr"` on phone and code inputs with labels in RTL flow, 60s resend cooldown, client send-budget mirror, **one label for first send and resend** (`booking.otpResend`), digits-only, no auto-submit on the sixth digit. Send is **always 204 and reveals nothing** — the "code sent" line is conditional wording, never a delivery claim; a spent personal budget looks identical by design (the honest-silence ruling behind `errors.otpSendBudget`).

## 1. Page anatomy — `PortalPage.tsx` bootstraps on `portalMe()`

- **401** → login panel (§2). **200** → dashboard (§3) with header row: greeting + bell button + logout, then the bookings sections.
- Layout container: `mx-auto max-w-[640px] px-4 pt-8 pb-16 md:px-6 flex flex-col gap-6` — the manage/booking column, so the portal reads as the same product.
- One page-level nested status region (§0 shape) announces discrete events: signed in, signed out, session expired, cancellation completed, attendance confirmed, bell opened count.

## 2. Login panel — `PortalLogin.tsx` (mobile 375)

```
|  האזור האישי                               |   h1 --font-display --text-2xl ink, gold hairline
|  +----------------------------------------+ |
|  | Card --color-surface p-6 gap-6         | |
|  |  אפשר להיכנס עם מספר הטלפון            | |   portal.loginIntro, --text-base ink
|  |  שאיתו קבעת תור.                       | |
|  |  טלפון נייד                            | |   booking.phone; Input dir="ltr" inputMode="tel"
|  |  [___________________]                 | |   help: booking.phoneHint (reused verbatim)
|  |  [ שליחת קוד אימות ]                   | |   booking.otpResend; primary md → secondary once sent
|  |  ····· (hairline once code sent) ····· | |
|  |  קוד האימות  [______]                  | |   booking.otpCode; Input dir="ltr" max-w-[10ch]
|  |  [ כניסה ]                             | |   portal.loginSubmit; Button primary lg
|  +----------------------------------------+ |
```

One `<form>`; Enter fires the phase's one forward action. `כניסה` chains `otp/verify` → `portal/session` on one click — the two calls are one gesture to her. Editing the phone away from the number the code was minted for collapses the code field (waitlist F-W3 rule: clear `codeSent` + token state on collapse).

### Login states

| # | State | Trigger | What she sees | Test hook |
|---|---|---|---|---|
| D | default | 401 bootstrap | phone phase; focus stays on `#content` (route rule) — no autofocus | axe clean |
| S1 | sending | `/otp/send` in flight | send button `loading`; status region `portal.sending` (R30) | announced |
| C | code entry | 204 received | code field + כניסה mount; focus moves to code field; help = `booking.otpSent` | code focused |
| S2 | signing in | verify+mint in flight | כניסה `loading`; status region `portal.loggingIn` | double-submit guarded |
| E1 | wrong code | verify 400 `OTP_INVALID` | `errors.otpInvalid` on the code field (danger — she typed it) | field error |
| E2 | expired code | `OTP_EXPIRED` | `errors.otpExpired` on the code field | field error |
| E3 | verification expired / burned | mint 401 `PHONE_NOT_VERIFIED` | `portal.verifyExpired` as a step line (muted, `role="alert"`) — NOT `errors.phoneNotVerified`, whose "your details are saved" tail is booking-flow-only | key mapped |
| E4 | rate-limited, silent | personal send budget spent (204) | **identical to C by design** — no distinct rendering exists; client mirror exhausted → `errors.otpSendBudget` + ContactCard dead-end shape | mirror only |
| E5 | tenant ceiling | send/verify 429 | **two shapes, split by face (booking.md states 11/12)** — verify 429: `errors.tooManyAttempts` as a muted step line, **form fully intact** (the window is short and self-clearing); send 429: **dead-end block replaces the form** — `errors.otpSendBudget` over ContactPanel, focus into the block (`tabIndex={-1}`; no `role="alert"` — reached *by* the focus move, the booking dead-end ruling) | both faces |
| E6 | SMS down | send 503 `SMS_NOT_CONFIGURED` / `SMS_UNAVAILABLE` | booking.md state 13 verbatim: **dead-end block replaces the form** — `errors.smsUnavailable` over ContactPanel; the h1 and card frame stay so she is not trapped; focus into the block (`tabIndex={-1}`, no `role="alert"`) | key mapped |
| E7 | mint brake | 429 on `portal/session` (spec D3's new per-tenant limiter) during S2's chained call | `errors.tooManyAttempts` as a muted step line — a tenant flood-brake, not her mistake, not her typing; **form stays intact** and the held `verification_token` is unspent, so retrying `כניסה` re-fires the mint alone, never a second verify on a burned code (E3 covers the token having died by then) | key mapped |
| N | no bookings | mint 404 `PORTAL_NO_BOOKINGS` | §3's empty screen replaces the card — **byte-identical to the logged-in empty dashboard** (no enumeration surface: "this phone has no bookings here" is one screen however you reach it); focus moves to its title | same component |
| X | session expired mid-use | any portal call 401s | login panel remounts with `portal.sessionExpired` line above the card (muted, announced via status region — a fact, not a fault) | announced once |

Blame split inherited from the verify step: only what she typed renders danger; everything else is a muted step line.

## 3. "My Bookings" — `PortalBookingList.tsx`

```
|  שלום, רותם                                |   portal.greeting, h1 row; <bdi> on the name
|  [🔔 3]                      [ יציאה ]     |   bell button (§5) · logout: Button ghost md
|                                             |
|  תורים קרובים                              |   portal.upcoming — h2 --text-lg semibold
|  +----------------------------------------+ |
|  | יום שלישי, 4 באוגוסט, 10:00            | |   row = button, Card surface, ≥44px
|  | מדידה ראשונה · שמלת אלמה, מידה 36      | |   muted line; <bdi> islands
|  | [ממתין לתשלום המקדמה]                  | |   Badge — only non-default statuses
|  +----------------------------------------+ |
|  תורים קודמים                              |   portal.past — h2
|  | … rows, past DESC …    [בוטל]          | |
```

- Rows are whole-row buttons → detail (§4). Upcoming ASC, past DESC — the server's order, unre-sorted.
- **Badges**: `pending_payment` → `portal.statusAwaitingPayment` (`Badge neutral`); `cancelled` → `portal.statusCancelled` (`Badge neutral` — a fact, not an alarm). Confirmed upcoming rows carry **no badge** (default state needs no label); `completed` and `no_show` past rows carry none either — the boutique's attendance bookkeeping is not rendered back at her.
- Section empty lines: `portal.upcomingEmpty` / `portal.pastEmpty`, muted — only when the *other* section has rows.
- **Both sections empty** (and login-state N): `EmptyState` — `portal.emptyTitle` + `portal.emptyBody` + `ButtonLink` → `/book/slot` (`portal.emptyCta`, secondary — an invitation, not a push).
- Loading: Card-shaped `Skeleton` + status region `portal.loadingBookings` (R30). Load failure: `manage.loadFailed` + `Button secondary` `manage.retry` (reused verbatim — same failure, same words).

## 4. Booking detail — `PortalBookingDetail.tsx` + `.ics`

Renders the **`ManageBookingResponse` shape via the pieces extracted from `ManageBookingPage.tsx`** (spec D8 owns the extraction) — facts card (labels reuse `booking.confirmWhen`/`confirmWhat`/`confirmDress`), actions, policy line, ContactPanel. The manage-booking states table applies **verbatim**: L / L2 (attendance confirmed, cancel stays) / C (cancelled + rebook ButtonLink) / P (past) / A (awaiting payment — `manage.awaitingPayment` + `manage.invalidHint`, both actions absent) / R (retryable failure). The cancel two-step is the same inline consequence reveal — `Button danger` on the second click only, focus into the revealed block, 409s re-render from the response body, never from hope. Same status-region announcements (`manage.attendanceDone`, `manage.cancelled`).

Portal-only deltas:

- Back link above the h1: `portal.backToList`, `ButtonLink ghost md` — returns to §3, focus to `#content`. (`md` without exception: `sm` is min-h-9 = 36px, under the house 44px floor — F-W1's resolution, same as BookingDetail.tsx's back button.)
- Unknown or not-hers id (house 404): `errors.notFound` line + back link — no facts, no oracle distinction.
- **`.ics` row** under the actions, above the policy line, on states L and L2 only (and past-`completed` P): a plain `<a href={portalIcsUrl(id)} download>` styled `Button secondary md` — `portal.icsDownload` + a muted help line `portal.icsHint`. A native GET link, not fetch-and-blob: on iOS the direct `text/calendar` response opens the add-to-calendar sheet. Cancelled/awaiting-payment states render no download control (the server 409s regardless; nothing to word on a control that cannot act — the manage A-state ruling).
- **Tokenized `/b/{token}` page gains the same control** in the same position, same keys, on the same states — delivered via `manageIcs(token)` (POST + blob URL; tokens never ride URLs, F14 D7). One rendering, two transports.

## 5. The bell — `PortalBell.tsx`

Icon button in the dashboard header row. **Portal page only, fetched once on portal mount** (pre-decided #18 — no polling, no focus-refetch).

- **Button**: accessible name `portal.bellLabel`; with unread, `portal.bellLabelUnread` interpolating the count. Visible badge = unread count capped **"9+"** (`<bdi dir="ltr">`), `--color-gold` dot-badge on the icon, `aria-hidden` (the count lives in the accessible name). `aria-expanded` + `aria-controls` — a disclosure, not a Modal.
- **Open**: inline panel mounts below the header row (Card, `--color-surface-raised`); focus moves to its heading `portal.bellTitle` (`tabindex="-1"`) — the mover rule. Opening fires `portalBellSeen()`; the badge clears **after** the POST resolves (the seen-stamp is the truth, not the click). Escape or the close button collapses and returns focus to the bell button.
- **Items** (`created_at` DESC, cap 20, no pagination): kind line (semibold, one key per rendered kind — §7 table) + booking line `{{type}} · {{date}}` (muted, `<bdi>` islands) + sent-date (muted `--text-sm`). Items link to the booking detail (§4). Rendered **from `kind` + booking facts via i18n only — never `message_log.body`** (masked tokens live there; evidence, not UI copy).
- **Empty**: `portal.bellEmpty`, muted, inside the open panel — a designed quiet, not a bug (unconfigured-SMS deployments are honestly empty).
- **Load failure** (`GET /storefront/portal/bell` 5xx / network): the bell button renders with **no badge** — never a stale or invented count — and stays operable; the open panel carries `manage.loadFailed` (muted — §3's ruling reused verbatim: same failure, same words) + `Button secondary` `manage.retry` re-firing the fetch. Focus still moves to the panel heading on open (the mover rule, unchanged); the failure line carries no `role="alert"` (reached *by* the focus move — the booking dead-end ruling), but a retry that fails re-renders it **with** `role="alert"` (it arrives without one). `portalBellSeen()` does **not** fire from a failed-fetch open — nothing was shown, so nothing is marked seen (F-P2's logic).
- Unknown/future kinds render nothing (skip the row) — no raw enum ever reaches the screen.

## 6. Logout + session expiry

- `יציאה` (`portal.logout`, `Button ghost md`) → `portalLogout()` → login panel remounts; status region announces `portal.loggedOut`; focus to `#content`. No confirmation step — logout is cheap (one OTP re-entry) and undoing it is the login panel itself.
- Any portal call answering 401 mid-session → login state X (§2): panel + `portal.sessionExpired` line. No countdown, no warning before expiry (no-ticking-numbers ruling; a 30-day TTL makes a warning theater).

## 7. Responsive — 375 / 768 / 1440

The column stays `max-w-[640px]` centered at every width (the manage ruling: a reading column, not a dashboard — E9's multi-fitting dashboard can revisit). 375: buttons `w-full`, header row wraps (greeting line, then bell+logout row). ≥768 (`sm:`): buttons `w-auto`, header on one row, detail buttons inline-row primary-first. 1440: no further deltas. The bell panel is full-column-width at all sizes.

## 8. Component notes — exact tokens

| Element | Notes |
|---|---|
| h1 / section h2 | `--font-display --text-2xl` + gold hairline (`h-px w-12 aria-hidden`) / `--text-lg` semibold ink |
| Login card, bell panel | `Card` on `--color-surface` / `--color-surface-raised`, `p-6 gap-6` |
| Phone / code inputs | shipped `Input`, `dir="ltr"` content, labels RTL; code `max-w-[10ch]` |
| Send / כניסה | `Button primary md` (→ secondary once sent) / `primary lg`; `loading` prop busy |
| Booking rows | whole-row `<button>` in Card, `min-h-[44px]`, chevron at inline-end `aria-hidden` |
| Badges | `Badge variant="neutral"` — both statuses; danger is reserved for the click that destroys |
| `.ics` control | `Button secondary md` as `<a download>` (portal) / `Button secondary md` + blob (token page) |
| Logout / back / bell close | `Button ghost md` — `sm` is 36px and banned for touch controls; F-W1's resolution is md-only (see WaitlistPanel.tsx, BookingDetail.tsx) |
| Cancel two-step | manage-booking §3 verbatim: secondary trigger → inline reveal → `danger` confirm + `ghost` keep |
| Status regions | nested `VisuallyHidden > span[role="status"]` everywhere (§0 ruling) |

Contrast: all pairs already in the tokens ledger (ink/cream 15.24, muted 6.15, white-on-danger ≈7.0, gold-text 5.57). Nothing new to enumerate.

## 9. RTL notes

Logical properties only. LTR islands: phone input, code input, every date/time/count/size numeral via `<bdi dir="ltr">` (R19 split shape where interpolation crosses a numeral). Bell badge count is one LTR run. Chevrons/arrows via logical inline-end placement, never hardcoded left/right glyphs. Reduced motion: bell panel and cancel reveal are instant show/hide; only shipped `--motion-fast` button transitions animate.

## 10. Accessibility (IS 5568 / WCAG 2.0 AA — legal floor)

- **Focus**: route entry → `#content` (router contract, e2e-asserted). Send→code mounts code field, focus there; login→dashboard focuses `#content`; list→detail and back → `#content`; bell open → panel heading; bell close → bell button; cancel reveal/confirm → manage rules verbatim; logout/expiry → `#content` with the status line announced. Focus never drops to `<body>`.
- **Announcements**: discrete events only — sending, code sent, signing in, signed in, signed out, session expired, cancelled, attendance confirmed. Bell open announces nothing extra (the panel receives focus; its heading is the announcement).
- **Targets**: every interactive element ≥44px (rows `min-h-[44px]`; all buttons `md` — F-W1 resolved that `sm` (36px) fails the floor, so no `sm` anywhere in this feature).
- **axe-zero** in e2e on: login (each phase incl. error states and the E5/E6 dead-end blocks), empty dashboard, populated dashboard, detail (L + cancel reveal open), bell open (empty + populated + load-failed), session-expired panel.

## 11. i18n keys — storefront `portal.*` + `document.portal` (he.ts; ar.ts mirrors with Hebrew values, pre-decided #47)

| Key | Hebrew | English annotation |
|---|---|---|
| `document.portal` | האזור האישי | "Your personal area" — tab title |
| `portal.loginTitle` | האזור האישי | h1 — page and login share it |
| `portal.loginIntro` | אפשר להיכנס עם מספר הטלפון שאיתו קבעת תור. | "You can sign in with the phone number you booked with." |
| `portal.loginSubmit` | כניסה | "Sign in" |
| `portal.sending` | שולחות את הקוד | "Sending the code" — hidden status |
| `portal.loggingIn` | נכנסות לאזור האישי | "Signing you in" — hidden status |
| `portal.loggedIn` | נכנסת לאזור האישי. | "You are signed in." — status region |
| `portal.verifyExpired` | האימות פג תוקף. אפשר לבקש קוד חדש ולהיכנס. | "The verification expired. You can request a new code and sign in." |
| `portal.sessionExpired` | החיבור לאזור האישי הסתיים. אפשר להיכנס שוב עם קוד אימות. | "Your session has ended. You can sign in again with a verification code." |
| `portal.greeting` | שלום, {{name}} | "Hello, {{name}}" |
| `portal.logout` | יציאה | "Sign out" |
| `portal.loggedOut` | יצאת מהאזור האישי. | "You have signed out." — status region |
| `portal.upcoming` | תורים קרובים | "Upcoming appointments" |
| `portal.past` | תורים קודמים | "Past appointments" |
| `portal.upcomingEmpty` | אין תורים קרובים כרגע. | "No upcoming appointments right now." |
| `portal.pastEmpty` | עדיין אין תורים קודמים. | "No past appointments yet." |
| `portal.emptyTitle` | אין תורים למספר הזה | "No bookings for this number" — one screen for state N and the empty dashboard |
| `portal.emptyBody` | כשתקבעי תור בבוטיק, הוא יופיע כאן. | "When you book an appointment at the boutique, it will appear here." |
| `portal.emptyCta` | קביעת תור | "Book an appointment" |
| `portal.loadingBookings` | טוענות את התורים שלך | "Loading your appointments" — hidden status |
| `portal.statusAwaitingPayment` | ממתין לתשלום המקדמה | "Awaiting deposit payment" — badge |
| `portal.statusCancelled` | בוטל | "Cancelled" — badge |
| `portal.backToList` | חזרה לתורים שלי | "Back to my appointments" |
| `portal.icsDownload` | הוספה ליומן | "Add to calendar" — downloads the `.ics` |
| `portal.icsHint` | הקובץ נפתח ביומן של הטלפון או המחשב. | "The file opens in your phone or computer calendar." |
| `portal.bellLabel` | הודעות מהבוטיק | "Messages from the boutique" — bell accessible name |
| `portal.bellLabelUnread` | הודעות מהבוטיק, {{count}} חדשות | "…, {{count}} new" — unread accessible name |
| `portal.bellTitle` | הודעות מהבוטיק | panel heading |
| `portal.bellEmpty` | אין הודעות עדיין. הודעות על התורים שלך יופיעו כאן. | "No messages yet. Messages about your appointments will appear here." |
| `portal.bellKindConfirmation` | אישור קביעת התור | "Booking confirmation" |
| `portal.bellKindReminder` | תזכורת לתור | "Appointment reminder" |
| `portal.bellKindOwnerCancel` | התור בוטל על ידי הבוטיק | "The boutique cancelled the appointment" |
| `portal.bellKindOwnerReschedule` | מועד התור עודכן | "The appointment time was updated" |
| `portal.bellKindPaymentReceivedNoSlot` | התשלום התקבל ונחזור אלייך לגבי המועד | "Your payment was received; we will be in touch about the time" |

Reused rows (one Hebrew, no drift — the manage-booking P2 precedent): `booking.phone`, `booking.phoneHint`, `booking.phoneInvalid`, `booking.otpCode`, `booking.otpSent`, `booking.otpResend`, `booking.confirmWhen`/`confirmWhat`/`confirmDress`, all `errors.*` mapped in §2, and the whole `manage.*` vocabulary on the detail (states, cancel two-step, `awaitingPayment`, `loadFailed`/`retry`). Zero exclamation marks anywhere.

## 12. What this surface deliberately does not have

No passwords/email/social login (#17) · no polling or realtime bell (#18) · no bell outside `/portal` (HttpOnly means the SPA cannot probe for a session without a request) · no per-item read state (one `bell_seen_at` timestamp is the model) · no profile editing · no reschedule action (mirror of the tokenized page, which has none) · no `.ics` on cancelled/awaiting-payment · no expiry countdown or warning · no distinct "phone unknown" vs "no bookings" rendering (one screen, by construction) · no raw `message_log.body` ever on screen.

## 13. PROPOSED (user confirms at the gate)

- **P1 — `כניסה` chains verify + session-mint on one button**: two API calls, one gesture; a separate "verify" then "enter" pair would make her click twice for one decision.
- **P2 — state N and the empty dashboard are one component**: same title, body, CTA — enumeration-neutral and one less screen to maintain.
- **P3 — badge policy**: statuses render badges only when they demand action or explain absence (`pending_payment`, `cancelled`); `no_show` is never shown to her.
- **P4 — bell opens as an inline disclosure panel**, not a Modal/popover — matches the house inline-reveal preference and spares focus-trap machinery.

## 14. ⚠ FINDINGS

- **F-P1**: `errors.phoneNotVerified`'s tail ("הפרטים שמילאת נשמרו") is booking-flow-specific — the portal must map `PHONE_NOT_VERIFIED` to `portal.verifyExpired`, not reuse the shipped row.
- **F-P2**: badge clearing must wait for the `bell/seen` 2xx; clearing on click paints a read state the server never recorded (offline/failure would resurrect the badge on next visit and read as a bug).
- **F-P3**: the detail extraction from `ManageBookingPage.tsx` must keep the token page's state precedence (409 re-renders from response body) — a forked copy that drifts is the mirror guarantee lost; the plan owns the extraction shape.

Design Gate: accepted by design-critic (round 3), 2026-08-06
