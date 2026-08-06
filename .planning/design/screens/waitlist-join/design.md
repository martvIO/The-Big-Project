# Screen: Waitlist Join (F22 — storefront join + manage list, Epic E5)

**Date**: 2026-08-06 · **Status**: DESIGN GATE OPEN — awaiting critic + copy approval · **Designer**: Claude (main agent)
**Consumes**: `.planning/specs/waitlist-join.md` (Gate 1 standing-approved, D1–D7) · tokens rev 1 · `packages/ui` as shipped
**Copy**: every Hebrew row below needs APPROVAL before the gate closes. Register: calm, feminine address, **no exclamation marks** (pre-decided #5).

---

## 0. Scope

Two surfaces. Storefront: the full-day state on the `/book` slot step grows a CTA that opens an **inline reveal** (spec D6 — NOT a dialog; `ManageBookingPage.tsx:425`'s recorded preference overrides any dialog phrasing elsewhere): phone → OTP → confirmation. Manage: a new `WaitlistSection` listing active entries with a per-row cancel. Out of scope: offers/claim/SMS (F23), customer-side management (F24), any change to F58's walk-in queue waitlist.

**Binding inheritances from `booking/booking.md`** — obeyed, not restated: the three-gold law; R19 bidi isolation (`<bdi dir="ltr">` islands for every numeral/date/phone); §7.3 `Intl.DateTimeFormat('he-IL', { timeZone: Jerusalem })`; R30 (loading announces via the nested `VisuallyHidden > span[role="status"]` shape — the §0 ruling of `manage-booking.md` applies verbatim); R16/§12.3 (live regions announce discrete events only; `role="status"` good news, `role="alert"` failures); the qa-greps physical-direction ban; the house focus rule (**the mover is the state change that mounted the target**).

**The OTP block is the verify step's, copied not re-derived** (`BookPage.tsx:1540–1700`): single code field (never six boxes), `autocomplete="one-time-code"`, `dir="ltr"` on phone and code inputs with label/help staying in RTL flow, 60s resend cooldown (`OTP_RESEND_COOLDOWN_MS`), client send-budget mirror (`OTP_SEND_BUDGET` = 5), **one label for first send and resend**, digits-only code input, no auto-submit on the sixth digit.

## 1. Storefront — the full-day state with CTA (mobile 375)

`BookPage.tsx` slot step. `SlotPicker` renders `labels.noSlots` when `times.length === 0`; the CTA renders **under** that empty state, **only when `flow.typeId !== null`** (the entry binds to a type; `TypePicker` sits directly above on the same screen). No type picked → the empty state stands alone; the CTA must not invite a join it cannot bind.

```
|  [TypePicker — type picked]                  |
|  +----------------------------------------+ |
|  | SlotPicker Card                        | |
|  |   אין מועדים פנויים בתאריך הזה. …      | |   labels.noSlots, unchanged
|  |                                        | |
|  |  [ הצטרפות לרשימת ההמתנה ]             | |   Button secondary md, w-full sm:w-auto
|  +----------------------------------------+ |
```

The CTA is **secondary** — the empty state's own advice (pick another date, or call) stays the primary path; the waitlist is the third option, not a consolation prize dressed as a win. Picking a different date or type collapses an open reveal and resets it (the day/type it bound to is gone).

## 2. The inline reveal — `components/booking/WaitlistJoin.tsx`

Clicking the CTA replaces it with the reveal (no Modal, no route change, step machinery untouched). Focus moves to the phone input (the mover mounted it). One `<form>` so Enter fires the phase's one forward action.

```
|  +----------------------------------------+ |
|  | Card, --color-surface, p-6, gap-6      | |
|  |  טלפון נייד                            | |   Input, dir="ltr", inputMode="tel"
|  |  [___________________]                 | |   help: booking.phoneHint reused
|  |  [privacy notice line]                 | |   boutique.privacy_notice_text, --text-sm
|  |                                        | |   --color-ink-muted (D4 — shipped text verbatim)
|  |  [ שליחת קוד אימות ]                   | |   Button primary md → secondary once sent
|  |  ····· (hairline, once code sent) ···· | |
|  |  קוד האימות  [______]                  | |   Input, dir="ltr", max-w-[10ch], one field
|  |  [ אישור והצטרפות לרשימה ]             | |   Button primary lg (mounts with code field)
|  +----------------------------------------+ |
```

Phase rules, all inherited from the verify step: send button label never says "again" (`waitlist.send` covers first send and resend); while cooling it is disabled and its label becomes `waitlist.sendWait` — the label IS the explanation, since `disabled` drops it from the tab order. Editing the phone away from the number the code was minted for collapses the code field. The send answer is **always 204 and reveals nothing** — the "code sent" help line is conditional wording, never a delivery claim; a spent personal budget looks identical by design (the honest-silence ruling behind `errors.otpSendBudget`).

**On 201** the whole reveal is replaced by the confirmation line (`tabindex="-1"`, focused — the mover rule; `role="status"` so it announces once):

> נרשמת לרשימת ההמתנה ליום {{date}}. אם יתפנה תור, נשלח לך הודעה.

`{{date}}` formatted `Intl.DateTimeFormat('he-IL')` weekday + date, inside `<bdi dir="ltr">` islands for the numerals (R19 split shape). No promise of *when* — the SMS claim is F23's to make true. The **idempotent duplicate** (server re-read on IntegrityError) arrives as the same 201: the already-joined state IS the confirmed state, one rendering, no special copy.

## 3. Storefront states — the single source

| # | State | Trigger | What she sees | Test hook |
|---|---|---|---|---|
| D | default | CTA clicked | §2 card, phone phase; focus on phone input | axe clean on open reveal |
| S1 | sending | `/otp/send` in flight | send button `loading`; nested status region carries `waitlist.sending` (R30) | announced |
| C | code entry | 204 received | code field + join button mount; focus moves to code field; help = `booking.otpSent` | code focused |
| S2 | joining | `POST /storefront/waitlist` in flight | join button `loading`; status region `waitlist.joining` | double-submit guarded |
| K | confirmed | 201 (incl. idempotent duplicate) | confirmation line replaces card; focus on it | `role="status"` |
| E | error | per table below | field error (danger) or step line (muted `role="alert"`) — the verify step's blame split: only what she typed is danger | keys map |

Error mapping — **zero new keys**, the shipped `errorKey` table (`api.ts`): invalid phone → `booking.phoneInvalid` (field, danger); `OTP_INVALID`/`OTP_EXPIRED` → `errors.otpInvalid`/`errors.otpExpired` (code field); `PHONE_NOT_VERIFIED` → `errors.phoneNotVerified`; join 429 → `errors.tooManyAttempts`; 400 day-window → `errors.validation`; client send-budget mirror exhausted → `errors.otpSendBudget` (muted, with ContactCard — the verify step's dead-end shape); network/5xx → `errors.unknown`. Empty state: N/A — the reveal opens with the phone field.

## 4. Manage — `WaitlistSection.tsx` (desktop-first console)

New NAV row `{ key: "waitlist", labelKey: "nav.bookingWaitlist", roles: ["owner", "shift_manager"] }` — mirrors the backend gate; `SectionKey` is guide-typed, so the one-step guide entry ships in the same commit.

```
|  רשימת המתנה לתורים                        |   section h — t("nav.bookingWaitlist")
|  תאריך [ 2026-08-20 ▾ ]  [hint line]       |   DateField default today; cleared = all upcoming
|  +----------------------------------------+ |
|  | יום | סוג הפגישה | לקוחה | סטטוס |      | |
|  | נרשמה | (cancel)                        | |
|  |----------------------------------------| |
|  | ה׳ 20.8 | מדידה ראשונה | רותם לוי       | |   customer_name ?? phone; phone via
|  |  [ממתינה] | 14:32 | [ ביטול ]           | |   isolateLtr (numeric-run rule)
|  +----------------------------------------+ |
```

- **Row order IS the position** — `(day, created_at)` FIFO from the server, top row is next in line. **No position column** (spec D1: position is computed nowhere and returned to no one; quiet hours will make strict-position promises false). Anyone asking "who is next" reads the top row.
- Columns: day (`Intl he-IL` short weekday + date, `<bdi>` islands), type name, customer (`customer_name ?? phone`; a known customer shows her name, an unknown phone shows via `isolateLtr`), status `Badge` (waiting → `neutral`; offered → the F23-era row, renders `neutral` too if ever seen), joined-at time (HH:MM, `<bdi dir="ltr">`).
- **Cancel is two clicks on one control**: `Button secondary sm` «ביטול» → swaps in place to `Button danger sm` «אישור הביטול» (first console use of the F16 pairing, white-on-danger ≈7.0:1, in the ledger); a click elsewhere or Escape reverts. In-flight: house busy treatment; success removes the row (refetch) and the section's status region announces `bookingWaitlist.cancelled`; failure → shipped error `Toast`, row stays.
- **No `usePoll`** — a waitlist changes at human speed; the polling sections (board, floor) poll because brides physically move.
- Table wraps in `overflow-x-auto` at narrow widths (console is desktop-first; the table never forces page-level horizontal scroll).

Manage states: **skeleton** (Card-shaped `Skeleton` + status region `bookingWaitlist.loading`, R30) · **loaded** (table) · **empty** (`EmptyState` — `emptyTitle`/`emptyBody`; when a date filter is set, `emptyFiltered` instead: the day may simply have no entries) · **error** (inline `role="alert"` line + `Button secondary` retry — the console's honest-failure shape) · **cancel in-flight / cancel error** (above).

## 5. Component notes — exact tokens

| Element | Notes |
|---|---|
| CTA | `Button variant="secondary" size="md"` — 44px met by size |
| Reveal card | `Card` on `--color-surface`, `p-6`, `flex flex-col gap-6` — the verify step's card, same rhythm |
| Phone / code inputs | shipped `Input`, `dir="ltr"` content, labels in RTL flow; code `max-w-[10ch]` |
| Privacy notice line | `--text-sm --color-ink-muted`, `substituteBoutique(boutique.privacy_notice_text, name)` — the details step's exact call |
| Send / join buttons | primary md (→ secondary once sent) / primary lg; `loading` prop for busy |
| Confirmation line | `--text-lg --color-ink`, `role="status"`, `tabindex="-1"` |
| Manage badges | `Badge variant="neutral"` |
| Cancel / confirm-cancel | `Button secondary sm` / `Button danger sm` |
| Status regions | the nested `VisuallyHidden > span[role="status"]` shape everywhere (manage-booking §0 ruling) |

Contrast: all pairs already in the tokens ledger (ink/cream 15.24, muted 6.15, danger 6.78, white-on-danger ≈7.0). Nothing new to enumerate.

## 6. RTL notes

Logical properties only (qa-grep ban on physical directions). Phone and code are the only LTR-content islands in the reveal; every interpolated date/time/phone rides `<bdi dir="ltr">` (R19). The manage table lays out RTL naturally — first (inline-start) column is day, cancel sits at inline-end; no per-cell direction overrides except the phone/time runs. Reduced motion: the reveal and the cancel swap are instant show/hide; only shipped `--motion-fast` button transitions animate.

## 7. Accessibility (IS 5568 / WCAG 2.0 AA — legal floor)

- **Focus**: CTA→reveal mounts phone input, focus moves there; send→code mounts code field, focus moves there; join→confirmed mounts the line, focus moves there; collapse (date/type change) returns focus to the re-mounted CTA. Manage cancel-confirm swap keeps focus on the same control; row removal moves focus to the table container (`tabindex="-1"`) so it never drops to `<body>`.
- **Announcements**: discrete events only — sending, code sent (via help text + status region), joining, confirmed, cancelled. Never per keystroke.
- **Targets**: every interactive element ≥44px (`Button` md/lg and `sm` with its padded hit area; verify against the shipped `sm` box — if under 44px, the cancel control takes `min-h-[44px]`, ⚠ F-W1).
- **axe-zero** in e2e on: the open reveal (each phase), the confirmed state, the manage section loaded + empty + confirm-swap open.

## 8. i18n keys — storefront `waitlist.*` (he.ts; `ar.ts` mirrors with Hebrew values, pre-decided #47)

| Key | Hebrew | English annotation |
|---|---|---|
| `waitlist.cta` | הצטרפות לרשימת ההמתנה | "Join the waitlist" — spec-given |
| `waitlist.send` | שליחת קוד אימות | "Send a verification code" — one label, send and resend |
| `waitlist.sendWait` | אפשר לבקש קוד חדש בעוד רגע | "You can request a new code in a moment" — cooling label |
| `waitlist.sending` | שולחות את הקוד | "Sending the code" — hidden status |
| `waitlist.join` | אישור והצטרפות לרשימה | "Confirm and join the list" |
| `waitlist.joining` | רושמות אותך לרשימת ההמתנה | "Adding you to the waitlist" — hidden status |
| `waitlist.confirmed` | נרשמת לרשימת ההמתנה ליום {{date}}. אם יתפנה תור, נשלח לך הודעה. | "You're on the waitlist for {{date}}. If a slot frees up, we'll send you a message." — spec-given, no when-promise |

Reused rows (one Hebrew, no drift — the manage-booking P2 precedent, ⚠ P1 below): `booking.phone`, `booking.phoneHint`, `booking.phoneInvalid`, `booking.otpCode`, `booking.otpSent`, all `errors.*` above, and the privacy notice text itself (not an i18n key — owner data).

## 9. i18n keys — manage `bookingWaitlist.*` (+ `HE_F22` spread into `HE` in `i18n.test.ts`, with floor)

| Key | Hebrew | English annotation |
|---|---|---|
| `nav.bookingWaitlist` | רשימת המתנה לתורים | "Appointment waitlist" — distinct from F58's walk-in «רשימת המתנה» |
| `bookingWaitlist.dayFilter` | תאריך | "Date" — DateField label |
| `bookingWaitlist.dayFilterHint` | אפשר לנקות את התאריך כדי לראות את כל הימים הקרובים. | "Clear the date to see all upcoming days." |
| `bookingWaitlist.colDay` | יום | "Day" |
| `bookingWaitlist.colType` | סוג הפגישה | "Appointment type" |
| `bookingWaitlist.colCustomer` | לקוחה | "Customer" |
| `bookingWaitlist.colStatus` | סטטוס | "Status" |
| `bookingWaitlist.colJoined` | נרשמה בשעה | "Joined at" |
| `bookingWaitlist.statusWaiting` | ממתינה | "Waiting" — badge |
| `bookingWaitlist.statusOffered` | נשלחה הצעה | "Offer sent" — F23-era, shipped now so the badge never shows a raw value |
| `bookingWaitlist.cancel` | ביטול | "Cancel" |
| `bookingWaitlist.cancelConfirm` | אישור הביטול | "Confirm cancellation" — danger, second click |
| `bookingWaitlist.cancelled` | הרשומה בוטלה. | "The entry was cancelled." — status region |
| `bookingWaitlist.loading` | טוענת את רשימת ההמתנה | "Loading the waitlist" — hidden status |
| `bookingWaitlist.emptyTitle` | אין כרגע רשומות ברשימת ההמתנה | "No waitlist entries right now" |
| `bookingWaitlist.emptyBody` | כשלקוחה תצטרף לרשימת ההמתנה מיום מלא באתר, היא תופיע כאן. | "When a customer joins the waitlist from a full day on the site, she'll appear here." |
| `bookingWaitlist.emptyFiltered` | אין רשומות בתאריך הזה. | "No entries on this date." |
| `bookingWaitlist.loadFailed` / `.retry` | לא הצלחנו לטעון את הרשימה כרגע. / ניסיון נוסף | "Couldn't load the list right now." / "Try again" |

## 10. What these surfaces deliberately do not have

No dialog/Modal (D6 inline-reveal ruling) · no position number anywhere (D1) · no customer name field at join (entry = day + type + phone) · no marketing-consent checkbox (requested-message basis, D1) · no countdown on the cooldown (no-ticking-numbers ruling) · no pagination on the manage list (D5 recorded ceiling) · no polling (§4) · no waitlist toggle in settings (F27's row, later) · no delivery claim in any copy — send is 204-silent by design.

## 11. PROPOSED (user confirms at the gate)

- **P1 — OTP-mechanics rows reused from `booking.*`** instead of minting `waitlist.phoneLabel`/`codeLabel` duplicates (spec D6 sketched ~10 new keys; the manage-booking P2 precedent says one label, one Hebrew, no drift). New keys only where wording genuinely differs (§8).
- **P2 — CTA is secondary, not primary**: on a full day the honest first advice is still another date or a phone call; the waitlist must not read as the happy path.
- **P3 — manage cancel confirms in place** (button swap) rather than via a Modal — one mutation, console context, matches the inline-consequence house style.

## 12. ⚠ FINDINGS

- **F-W1**: verify `Button size="sm"`'s rendered box against the 44px floor before the manage cancel ships; if short, `min-h-[44px]` on that control (§7).
- **F-W2**: the F58 collision means `waitlist.*` exists in **manage** i18n already — the new storefront block is `waitlist.*` too (storefront `he.ts` has no such block; spec conflict 1 rules storefront may take it). Reviewers of any file touching both apps must check the import app, not just the key name.
- **F-W3**: the reveal collapses on date/type change (§1) — the build must also clear `codeSent`/token state on collapse, or a stale token for the old day survives into a new reveal.

Design Gate: accepted by design-critic, 2026-08-06
