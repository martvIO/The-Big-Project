# Screen: Owner bookings (F15 — `apps/manage` sixth section, Epic E3)

**Date**: 2026-07-30 · **Status**: DESIGN GATE — self-approving under Interview **Q2** (assembled from shipped components; nothing novel), designer-drafted, `design-critic` must ACCEPT · **Designer**: Claude · **Consumes**: `.planning/specs/owner-booking-management.md` (Gate 1 self-approved 2026-07-30, D1–D20) · tokens rev 1 · `.planning/design/screens/design-system/manage-restyle.md` (**binding**) · `packages/ui` as shipped
**Copy**: `copy.md` in this directory — Hebrew drafted here under the approved register, flagged for the user's one-line edit. It also carries the **full i18n key inventory** (`he` + untranslated `ar`), which is why no key table is duplicated in this file.

**Gate record** — `design-critic` rev 1 verdict **REVISE**: 3 findings (1 BLOCKER, 1 MAJOR, 1 MINOR). **3 accepted, 0 rejected.** All three were re-verified against the shipped sources before fixing, and the two className-override findings turned out to be **stronger than the critic argued**: the critic called the Tailwind cascade order "unproven", but the built stylesheets prove both overrides *lose*. See **F-6** — that check is now the deck's own finding, because it generalizes past this feature. Fixes: destructive trigger is `variant="danger"` (§2, §3.2, §5); the list `Card` padding override is dropped (§1); the facts grid uses `max-content` instead of an ungrounded `7rem` (§2). The false precedent citations are corrected here and in `manage-restyle.md:37,38,40`.

---

## 0. Scope

The owner console gains a **sixth section** — `nav` key `bookings`, label «תורים» — rendered inside the shipped `ConsoleShell` (skip link, single sr-only `h1`, plain `<nav>` with `aria-current="page"`, 720px content cap: nothing to design there). Three new components, one in-panel state swap between them:

| Surface | Component | Shape |
|---|---|---|
| Day list | `BookingsSection.tsx` | `DateField` day filter → `role="status"` count line → `<ul className="divide-y">` of row buttons |
| Detail | `BookingDetail.tsx` | facts in three `h3` groups + one actions group; in-component swap, the `CatalogSection` → `DressEditor` pattern |
| Reschedule | `RescheduleDialog.tsx` | `Modal` owning the `GET /manage/slots` fetch and the promoted `SlotPicker` |

Plus two confirm `Modal`s inside `BookingDetail` (cancel, phone correction) and the promotion of `SlotPicker` into `packages/ui` with a `labels` prop (spec D14 — the storefront's two call sites gain the prop; the component's fieldset/legend/radio contract is unchanged).

### Binding inheritances (obeyed, not restated)

From **`manage-restyle.md`**: 720px content cap at every breakpoint; the register split (an **outage** is `text-ink-muted`, a thing-she-must-fix is `text-danger`, a nothing-failed **notice** is `text-warning-text`); `EmptyState` over a blank column; inline muted cues over Toasts for success; **no `role="tab"` anywhere**; the console drops the storefront's ornament level (no gold hairlines on forms); the only LTR islands are numeric/URL fields.
From **`tokens.md`** rev 1: the gold law (`gold-strong` never carries text — which is why `Badge` has no gold variant and status never uses one); focus ring on every control; ≥44×44 touch targets; no raw px in app code.
From the **spec**: no migration, no calendar, no audit history UI, no owner-created bookings, no delivery-failure indicator.

### Explicitly NOT here — with the spec's reasons

| Not shipped | Reason (spec) |
|---|---|
| **Owner-created bookings** | Interview Q6, verbatim: a booking the owner creates has no bride-verified phone and no accepted terms, so the SMS control link would target an unverified number — "new legal and security ground that earns its own spec, not a corner of F15". Consequence the UI must live with: a mis-tapped cancel has **no in-product remedy** (Risk 1), so the cancel Modal's copy points at the storefront rebook rather than at a button that does not exist. |
| **Calendar / month / week view** | Pre-decided #48, E10. It layers over this feature's list API with an optional `from`/`to` widening (D17's correction: "no new endpoints" survives, "data the API already returns" does not). The day view is deliberately not a proto-calendar. |
| **Delivery-failure indicator** | D18 / Risk 3(b): a `failed` indicator by construction only exists once a provider is configured, and reading it means a new `message_log` terminal-row read plus owner-facing copy about delivery states no provider has yet produced — a surface designed against zero real data. F15 ships the **remedy** (resend) without the **signal**. `booking-comms.md:185`/`:193` stay open against provider go-live. |
| **Audit history UI** | D2 / Risk 7: rows are written, nothing reads them in v1. A history list nobody asked for in front of a 720px cap is the wrong trade; the read endpoint is a follow-up over a table that already grants SELECT. |
| **A "sent" badge or any delivery claim** | Risk 3(a): `_deliver` swallows both provider exceptions and the pre-provider window leaves **no `message_log` row at all**, so a "sent" badge would be empty for every booking until a provider exists. Discharged by copy — see §6.4. |
| **A late-recorded cancellation** | D3 / Risk 8: past `confirmed → cancelled` is refused by the clock split, and `no_show` would assert something false on a field E4 #19 reads. The pilot answer is that the owner marks nothing, and D3 already rules that "confirmed and past, never marked" is not an error state — so the UI must render such a row **without an error affordance**. |
| **Un-cancel** | `cancelled` is terminal (D3). Reviving re-enters two partial unique indexes against a possibly resold seat. |
| **Paging controls** | Endpoint carries `offset`/`limit`; the UI ships no prev/next — a Jerusalem day at pilot volume fits fifty rows. The `role="status"` count line stays regardless (it is the console's only announced list state and the post-mutation focus destination). |
| **A retry button on list load failure** | The spec's states table pins the treatment as a `role="alert"` paragraph in the outage register. Re-selecting the date in the `DateField` refetches, so a dedicated retry control would be a second tab stop for one act. Considered, declined, recorded. |
| **Real-time / live board, deposits, waitlist, a no-show SMS** | Spec "Out of scope" — E6, E4 #19, E5 #23, D13 respectively. |

---

## 1. The day list — mobile 375, loaded (state **L**)

```
+------------------------------------------------+
| [ConsoleShell header: boutique name / יציאה]   |
| [nav: פרופיל | שעות | סוגי תורים | מדיניות |    |   6th item «תורים», aria-current="page",
|  שמלות | תורים]  (stacked full-width ≤767)     |   gold-strong underline + font-semibold
+------------------------------------------------+
|  <main #console-main tabIndex=-1, max-w-720>   |
|                                                |
|  תורים                                          |   h2, --text-lg font-semibold ink
|                                                |   (console drops the display-serif + hairline
|  +------ Card (paper, p-6) ----------------+    |    ornament — manage-restyle "Notes")
|  |  תאריך                                  |    |   DateField label (visible, required)
|  |  [ 2026-08-04            ] dir="ltr"    |    |   max-w-[200px], native OS picker
|  +-----------------------------------------+    |
|                                                |
|  תורים ביום זה: 3                               |   role="status" tabIndex={-1}
|                                                |   --text-sm --color-ink-muted
|  +------ Card (paper, p-6) ----------------+    |
|  | <ul class="divide-y divide-border">     |    |
|  | ┌ <li><button class="w-full py-4        |    |
|  | │        flex items-start gap-3         |    |
|  | │        text-start">                   |    |
|  | │  10:00   מיכל לוי         [ מאושר ]    |    |   time: w-14 shrink-0, font-semibold,
|  | │          מדידה ראשונה · אישרה הגעה     |    |     <bdi dir="ltr">
|  | │          שמלת אלמה                    |    |   name: bare <bdi>, font-semibold
|  | └                                       |    |   Badge inline-end of the name row
|  | ┌  11:30  נועה כהן        [ בוטל ]      |    |   meta: --text-sm ink-muted
|  | │          מדידה ראשונה                  |    |   dress: bare <bdi>, --text-sm muted
|  | ┌  14:00  שיר אברהם     [ לא הגיעה ]     |    |
|  | └ </ul>                                 |    |
|  +-----------------------------------------+    |
+------------------------------------------------+
```

- **One affordance per row**: the whole row is the button that opens the detail (the `CatalogSection.tsx:209` ruling — a second «פתיחה» button would be two tab stops for one action). `py-4` + `text-base` gives ≥44px without a `min-h` literal.
- **The time is the leading cell, not a repeated date.** The date is the filter; printing it on twelve rows is noise. Fixed `w-14` so the times form a scannable column at every width.
- **Exactly one `Badge` per row**, and it is the status. `attendance_confirmed_at` renders as the muted words «אישרה הגעה» on the meta line — **not** a second Badge — so nothing competes with the status chip for meaning. (The list response carries the field; ignoring it would waste the single most operationally useful fact on a day view.)
- **Cancelled rows are in the list** (D17) and are not visually demoted beyond their `muted` Badge — a cancelled row is the owner's evidence that the slot re-opened, so hiding or greying the whole row would delete the reason it is there.
- Order is the server's `(starts_at, seat_index)`; the client never re-sorts.
- **The rows are inset by the `Card`'s own `p-6`, and the `divide-y` rules stop 24px short of the card edge.** Rev 1 of this deck specified `Card (paper, p-0 sm:p-6)` to get edge-to-edge rows at ≤767px. That is **withdrawn** (critic MAJOR, accepted): `cn()` is a plain join with no class-merge, so a consumer `p-0` and the `Card`'s baked-in `p-6` are two same-specificity rules and the winner is stylesheet order, not JSX order — and the built stylesheet emits `.p-0` **before** `.p-6`, so `p-6` wins and the override does nothing at any width (F-6). Rather than fight it or thread a `padding` prop through a gate-passed component with 25+ call sites for one mobile nicety, the list adopts the shipped console shape: `TypesSection.tsx:213` and `CatalogSection.tsx:118` both render their row list inside a normally-padded `Card`, and inset dividers are what the console already reads like. Edge-to-edge was a preference; consistency with four shipped sections is worth more than it.



### 768 / 1440 deltas

None that matter, and that is the ruling. The nav becomes a horizontal row at ≥768 (shell behaviour), the content column stays capped at **720px** at 1440 — and that cap is exactly why the day view is **a list of rows and not a table**: four to six meaningful columns (time, name, type, dress, status, attendance) cannot hold a readable Hebrew line length inside 720px, and a table that scrolls horizontally on the owner's phone is worse than a list on every device. Row internals are already a wrap-tolerant flex, so 375 and 1440 render the same DOM with no breakpoint branches.

---

## 2. The detail — mobile 375, loaded confirmed-and-future (state **DL**)

```
+------------------------------------------------+
|  [ ← חזרה לרשימה ]                              |   Button ghost sm, first in reading order
|                                                |
|  פרטי התור                        [ מאושר ]      |   h2 tabIndex={-1} (focus lands here)
|                                                |   Badge inline-end, same map as the list
|  <p role="status" tabIndex={-1}>                |   the ONE region: loading text, then success
|                                                |   cues. Empty when idle.
|  +------ Card ----------------------------+    |
|  |  הלקוחה                                 |    |   h3, --text-base font-semibold ink
|  |  שם            מיכל לוי                 |    |   label --text-sm muted / value ink
|  |  טלפון         +972501234567            |    |   value in <bdi dir="ltr">
|  |                [ תיקון מספר הטלפון ]     |    |   Button secondary sm
|  |  ·······································    |
|  |  הפגישה                                 |    |   h3
|  |  מועד          4.8.2026 · 10:00          |    |   one <bdi dir="ltr"> per run
|  |  סוג הפגישה     מדידה ראשונה             |    |
|  |  שמלה          שמלת אלמה · מידה 36       |    |   name bare <bdi>; size <bdi dir="ltr">
|  |  עמדה          2                        |    |   <bdi dir="ltr">
|  |  נקבע בתאריך    1.8.2026 · 09:12         |    |
|  |  מדיניות שאושרה  גרסה 3 · 1.8.2026        |    |   version + accepted-at, both LTR runs
|  |  קישור ניהול     קישור ניהול פעיל          |    |   manage_link_issued as words, no chip
|  |  ·······································    |
|  |  הערות הלקוחה                            |    |   h3 — kept last: it is the only
|  |  «באה עם אמא ואחות, מגיעות מחיפה»         |    |   free-text block and may be long
|  +---------------------------------------- +    |
|                                                |
|  +------ Card ----------------------------+    |
|  |  פעולות                                 |    |   h3
|  |  אין באפשרותנו לאמת שהודעות נמסרו…       |    |   the standing limit line, --text-sm muted
|  |                                         |    |
|  |  [ שינוי מועד ]                          |    |   Button secondary md
|  |  [ הנפקת קישור ניהול חדש ]                |    |   Button secondary md
|  |  הנפקת קישור חדש מבטלת את הקישור הקודם.   |    |   --text-xs muted, sits UNDER its button
|  |                                         |    |
|  |  [ ביטול התור ]                          |    |   Button variant="danger" size="md"
|  |                                         |    |     (the console's one destructive-trigger
|  |                                         |    |      pattern — §3.2)
|  +-----------------------------------------+    |
+------------------------------------------------+
```

### Which controls exist, per status and clock

The action group renders **only the transitions the D3 graph allows for this row's status and clock**. Rendering four buttons where three answer 409 is a trap; a disabled button with no explanation is worse than an absent one; and the clock split is a fact about the appointment, not a permission. The server stays the authority — an action that races the clock still 409s and renders in the fix-this register (§4).

| Row state | Controls |
|---|---|
| `confirmed`, `starts_at > now` | שינוי מועד · הנפקת קישור ניהול חדש · תיקון מספר הטלפון · **ביטול התור** |
| `confirmed`, `starts_at ≤ now` | סימון: לא הגיעה · סימון: התקיים |
| `no_show` | סימון: התקיים · החזרה לסטטוס מאושר |
| `completed` | סימון: לא הגיעה · החזרה לסטטוס מאושר |
| `cancelled` | **none** — the group renders `booking.cancelledNoActions` (muted), which names the storefront rebook as the remedy (Risk 1) |

Phone correction and resend appear only in the first row because D8 mechanic 4 guards both on confirmed-and-future. A past `confirmed` row therefore carries **no** error affordance and no nag — D3's ruling that "confirmed and past, never marked" is not an error state (Risk 8) is rendered as *silence*, not as a warning.

### 768 / 1440 deltas

The label/value rows go from stacked (`flex flex-col`) to a two-column grid at ≥768 — `grid grid-cols-[max-content_1fr] gap-x-4` — which is the only breakpoint branch in the whole feature. Rev 1 said `grid-cols-[7rem_1fr]`; 7rem (112px) corresponds to nothing in `tokens.md`'s 4/8/12/16/24/32/48/64 scale and was a guess at the width of «מדיניות שאושרה» (critic MINOR, accepted). `max-content` deletes the number instead of justifying it: CSS sizes the column from the longest label actually rendered, so it cannot drift when copy is edited, cannot be wrong at a user-scaled font size, and — the reason it matters here — cannot be wrong for the untranslated `ar` column, whose glyph metrics differ from the Hebrew the 7rem was eyeballed against. The label set is eight short closed-set field names inside a 720px cap, so there is no runaway-column risk to cap. `gap-x-4` stays: `--space-4` is a token. Action buttons are `fullWidthMobile` and become an inline wrapped row at ≥768, primary reading order first, **ביטול התור last and visually separated** by a `border-t border-border pt-4`. Content stays 720px at 1440; there is deliberately no side-by-side facts/actions desktop layout — five facts and four buttons do not earn a dashboard.

---

## 3. The reschedule dialog, and the confirm Modals

### 3.1 Reschedule (`RescheduleDialog.tsx`)

```
+--- Modal (bg-surface-raised, w-[min(28rem,100vw-2rem)]) ---+
|  שינוי מועד התור                                            |  Modal title (h2 inside dialog)
|                                                            |
|  המועד הנוכחי: 4.8.2026 · 10:00                             |  --text-sm muted, LTR runs isolated
|                                                            |
|  [ SlotPicker ]                                            |
|    תאריך  [ 2026-08-04 ] dir="ltr"                          |  labels.pickDate
|    ┌ שעה ─────────────────────────── <legend>              |  labels.pickTime
|    │ (10:00) (10:45) (11:30) (12:15)                       |  radio chips, min-h-11
|    └                                                        |
|                                                            |
|  המועד יתעדכן, והקישור של הלקוחה יצביע על המועד החדש.        |  consequence, --text-sm ink
|                                                            |
|  footer:  [ חזרה ]        [ עדכון המועד ]                    |  ghost · primary (disabled while
+------------------------------------------------------------+   in flight)
```

- **The dialog *is* the confirm surface.** The spec asks for a confirm Modal on reschedule, and this dialog satisfies it: a consequence sentence sits directly above the one submit control, and the submit is never reachable by a single stray tap. A second `Modal` stacked on this one would put a focus trap over a focus trap for a decision the owner is already reading. **Ruled** (§7 P-2).
- **The current time is always present and pre-selected** (D6 — the engine drops full slots, so a capacity-1 target the booking itself occupies never appears in the grid, and "change my mind" must have a way back). The dialog injects a `SlotTime` for the booking's own `starts_at` when the fetched grid lacks it, and `value` starts at that instant. Re-submitting it is free — D5 step 3 short-circuits to a no-op 200.
- **The injected option carries the bare time and nothing else.** `SlotPicker` renders every label inside `<bdi dir="ltr">`; appending «(המועד הנוכחי)» would put Hebrew inside `dir="ltr"`, which is itself the bidi defect §6.3 bans. The current time is named in the line **above** the picker instead, and the picker's own three-channel selection (native `:checked` + gold fill + font-semibold) shows it is chosen. **Ruled** (§7 P-3).
- **Window and refetch.** Opens on the booking's current Jerusalem date and fetches `GET /manage/slots?from=<that date>&to=<+13d>` — one fetch, in-memory date filtering, the component's shipped contract. Changing the date **outside** the fetched window refetches a fresh 14-day window anchored at the new date. `min` is today (Jerusalem) because a past date can never hold a target; **no `max`** — the bookable horizon is a server bound and the spec's constants ruling is that F15 mirrors no server bound client-side, so a date past it simply materializes no slots, which is the truth.
- **No separate `EmptyState` for no-slots.** `SlotPicker`'s own centered muted block is the shipped, tested treatment for both whole-window-empty and this-date-empty (the F14 ruling: same block, same string). Stacking an `EmptyState` above it would render two empty messages for one emptiness. The spec's states-table cell is satisfied in substance by the same visual family. **Ruled** (§7 P-4).

### 3.2 Cancel confirm

`Button variant="danger"` trigger → shared `Modal`, confirm in the caller-supplied `footer` (`Modal.tsx:8-13`), dismiss `ghost`. Title «לבטל את התור?»; body states that cancellation is **final** and that the seat re-opens, and names the storefront rebook as the only route back — because owner-created bookings are out of scope and the owner's real recovery is the customer rebooking (Risk 1). Both danger buttons are `bg-danger text-surface-raised`, white-on-danger ≈7.0:1, already in the tokens ledger from the F16 gate.

**Trigger and confirm are both `danger`, and that is the shipped pattern, not a duplication.** Rev 1 of this deck specified a "ghost-danger" trigger (`variant="ghost"` + `className="text-danger"`) and cited a `TypesSection`/`CatalogSection` precedent. Both halves of that were wrong (critic BLOCKER, accepted):

- **No such variant, and no such usage.** `Button.tsx:4` defines exactly four variants — `primary | secondary | ghost | danger`. A repo-wide grep finds `variant="ghost"` at seven sites, every one of them a Modal dismiss or a text toggle, and none of them paired with `text-danger`. No shipped `Button` anywhere overrides a variant's text colour via consumer `className`.
- **It would not even render red.** `cn()` (`lib/styles.ts:4`) is a plain join, so ghost's baked-in `text-ink` and a consumer `text-danger` are same-specificity rules decided by stylesheet order — and the built CSS emits `.text-danger` **before** `.text-ink`, so **`text-ink` wins**. The documented trigger would have shipped as an ordinary ink-coloured ghost button, silently deleting the destructive affordance on this feature's one irreversible operation, with no test to catch it (F-6).
- **The real precedent is solid `danger`, three for three.** `TypesSection.tsx:276` (archive), `DressEditor.tsx:401` (archive) and `HoursSection.tsx:305` (remove exception) are all `variant="danger"` triggers, each opening a `Modal` whose footer is `ghost` dismiss + `danger` confirm (`TypesSection.tsx:312-318`, `DressEditor.tsx:411-414`, `HoursSection.tsx:325-328`). Trigger and confirm are never co-visible — the Modal covers the panel — so two danger buttons is the shipped ergonomics, not a hierarchy failure. `CatalogSection` ships **no** archive trigger at all; the rev 1 citation named the wrong component as well as the wrong variant.

The **Modal** half of the rev 1 ruling stands unchanged, and is still deliberately the console pattern rather than the customer manage page's inline two-step reveal (`manage-booking.md` §3, `ManageBookingPage.tsx:349-420`, which is `secondary` trigger → inline reveal → `danger` confirm). The divergence is a ruling: the console's other destructive acts already use a Modal, and the owner is inside a dense multi-action panel where an inline reveal would push the remaining actions off the fold. What changed is only the trigger's variant — from a combination that does not exist to the one the console actually ships.

### 3.3 Phone-correction confirm — the dangerous surface

Two surfaces on purpose, and this is the one place the extra step is worth its cost:

1. **Inline edit inside the הלקוחה group.** «תיקון מספר הטלפון» reveals an `Input` (`label` = «מספר טלפון חדש», `dir="ltr"`, `type="tel"`, `inputMode="tel"`), pre-filled with **nothing** — a pre-filled wrong number invites a one-character edit of the field she is trying to replace. Save + «ביטול העריכה» sit under it. **No client-side validation of any kind** (D20): no normalizer, no pattern, no length rule. The server's 400 `VALIDATION_ERROR` is the only authority and its message renders in the field's `error` slot.
2. **Confirm `Modal` that echoes the typed number.** The body renders the number **as she typed it**, inside `<bdi dir="ltr">`, so the Modal is a proofreading step and not a ceremony. It states three things and no more: the number is **not verified by the platform** and the update is on the boutique's word (D8 — owner-attested, no OTP); the customer's existing link **stops working**; a new link is issued. It does **not** say a message was sent, in any tense.

The 409 `CUSTOMER_ALREADY_BOOKED` that a re-point can raise (D8's 0009 pre-check) renders as the action-failure line in the fix-this register — the owner's next move is to open the other booking, and the message names the collision.

### 3.4 Resend gets no Modal, and its warning is pre-tap

The spec pins Modals to cancel, reschedule and phone correction; resend is a direct button. D9 nevertheless requires the Hebrew to say the old link stops working — so that sentence is a **permanent `--text-xs` muted line under the button**, readable before the tap, not a post-hoc explanation. The success cue repeats it. The button is disabled while its request is in flight, which is D9's stated client-side mitigation for the double-tap it explicitly declined to serialize server-side.

---

## 4. States — the single source for this feature

Every row of the spec's States-per-screen table, plus what it announces and where focus goes.

| # | Screen · state | Trigger | What she sees | Region / focus |
|---|---|---|---|---|
| **L-load** | List · loading | day fetch in flight | count line carries `booking.listLoading`; `<Skeleton variant="text" lines={4} />` below | the count line is `role="status"`, so loading **is** announced — the shipped console's bare `aria-hidden` Skeleton announces nothing, and this reuses the region the count needs anyway (§8 F-1) |
| **L-fail** | List · load failure | any non-2xx / network | `<p role="alert" className="text-sm text-ink-muted">` + the server message — **outage** register, no blame, no retry control | alert |
| **L-empty** | List · empty day | 200, `total === 0` | `<EmptyState title body />` inside the Card — never a blank column. Body offers **another date**, no CTA (there is no owner-create) | count line reads `…: 0` |
| **L** | List · loaded | 200, `total > 0` | §1 | count line announces the count |
| **DL-load** | Detail · loading | row tapped | `h2` + Badge-less header mount immediately; status region carries `booking.detailLoading`; `<Skeleton variant="text" lines={4} />` | `h2` focused on mount (`DressEditor.tsx:126-128`) |
| **DL-404** | Detail · not found | 404 `NOT_FOUND` (incl. another tenant's id under RLS — indistinguishable, by design) | `<p role="alert">` `booking.notFound` + the back control; no facts Card | alert; back control remains reachable |
| **DL** | Detail · loaded | 200 | §2, controls per the status/clock table | — |
| **DA-fail** | Detail · action failure | 409 `BOOKING_TRANSITION_INVALID` / `SLOT_UNAVAILABLE` / `CUSTOMER_ALREADY_BOOKED`, 429 `TOO_MANY_ATTEMPTS`, 400 `VALIDATION_ERROR` | `<p role="alert" className="text-sm text-danger">` in the action group — **fix-this** register. The row is **re-rendered from the response the mutation returned** where one exists; a 409 never leaves the screen showing a state the server refused | alert; focus stays on the control (it is still mounted) |
| **DA-ok** | Detail · action success | 2xx | inline muted cue in the status region (**not** a Toast, `manage-restyle.md:57`); the whole detail re-renders from `OwnerBookingDetail` and the list row is patched from the same object (`CatalogSection.tsx:78-80` — the two views cannot disagree if they render one object) | the cue's region is `tabIndex={-1}` and is **focused**, because a successful transition can unmount the very control that was clicked; focus must never drop to `<body>` (the house mover-rule, `manage-booking.md` §5) |
| **RD-load** | Reschedule · loading | dialog opened, `/manage/slots` in flight | `<Skeleton variant="text" lines={3} />` in the Modal body; footer confirm disabled | Modal's native focus trap; `Modal` autofocus lands in the panel |
| **RD-empty** | Reschedule · no slots | 200, window empty for the chosen date | `SlotPicker`'s own muted no-slots block (§3.1 ruling); confirm disabled | — |
| **RD** | Reschedule · loaded | 200 with times | §3.1, current time pre-selected | — |
| **RD-fail** | Reschedule · submit failure | 409 / 429 / 400 | inline `<p role="alert" className="text-sm text-danger">` above the footer; **dialog stays open** with the grid intact so she can pick another time — closing it would throw away the fetch she needs | alert |
| **M-cancel / M-phone** | Confirm Modals | trigger tapped | §3.2 / §3.3 | native `<dialog>` trap; **focus restored to the trigger on close** by the `DressEditor.tsx:130-136` effect — the trigger unmounts while the dialog is open, so native focus-return lands on `<body>` |

**State precedence when an action races reality.** Every mutation answers the same `OwnerBookingDetail` (D7), so a success always re-renders the whole detail from the response and never from what the client hoped. A 409 renders **DA-fail** and leaves the previously-rendered facts in place; the owner's recovery is the back control (which refetches the day) — the console never guesses a new state from an error.

---

## 5. Component notes — exact tokens

| Element | Notes |
|---|---|
| Section heading | `<h2 className="text-lg font-semibold text-ink">` — matches `CatalogSection.tsx:116`; **not** `SectionHeading`+ornament (the console drops storefront flourishes) |
| Day filter | `DateField` (`packages/ui`), visible `label`, `dir="ltr"`, `className="max-w-[200px]"`. Native `<input type="date">` — no picker library, no popover: the OS control brings the OS locale and the OS a11y stack (`SlotPicker`'s own rationale) |
| Count line | `<p role="status" tabIndex={-1} className="text-sm text-ink-muted">` with the number in `<bdi dir="ltr">` — the `CatalogSection.tsx:148-160` shape |
| Row button | `flex w-full items-start gap-3 py-4 text-start`; leading time cell `w-14 shrink-0 font-semibold` |
| Facts Card | `Card` (paper, `rounded-md p-6 shadow-sm`); label `--text-sm --color-ink-muted`, value `--text-base --color-ink`; group dividers `border-t border-border pt-4` |
| Status Badge | see §6.1 |
| Destructive trigger | `Button variant="danger" size="md"` — the console's uniform pattern: `TypesSection.tsx:276`, `DressEditor.tsx:401`, `HoursSection.tsx:305`. **Never** `variant="ghost"` + `className="text-danger"`: no such variant exists and the override loses the cascade (§3.2, F-6) |
| Confirm-destructive | `Button variant="danger" size="md"` — `bg-danger text-surface-raised`, ≈7.0:1. Two per feature (trigger + confirm), never co-visible: the `Modal` covers the panel |
| Other actions | `Button variant="secondary" size="md"` (`min-h-11` = 44px), `fullWidthMobile` |
| Back control | `Button variant="ghost" size="sm"` — `min-h-9` (36px) is under the 44 floor, so it ships `size="md"` on the detail screen; ruled here rather than left to the build |
| Confirm dialogs | shared `Modal` with confirm in `footer`; `useId`-based `aria-labelledby` is the component's (a screen can mount two) |
| Loading | `Skeleton variant="text"` — `aria-hidden`, so the announcement is the `role="status"` region's job, never `aria-busy` alone |
| Empty | `EmptyState title body` — icon-less, no CTA on the empty day |
| Notes block | `<p className="whitespace-pre-wrap">` inside a bare `<bdi>` — preserves her line breaks with no markdown pass and no linkification (§6.5) |
| Reschedule picker | promoted `SlotPicker` from `@boutique/ui`, `labels={{ pickDate, pickTime, noSlots }}`; chips `min-h-11`, selection carried by `:checked` + gold fill + `font-semibold` — three channels, none hue alone |

**Contrast, from the tokens ledger — not eyeballed.** ink/paper 13.89 · ink-muted/paper 5.61 · danger/paper 6.18 · success/paper 5.56 · warning-text/paper 5.20 · white-on-danger ≈7.0 · focus ring (gold-text) 5.57 on cream. Every Badge variant passes AA at `--text-xs` (`Badge.tsx` header). **No new pair is introduced by this feature**, so the ledger needs no addition at this gate.

---

## 6. The a11y contract — IS 5568 / WCAG 2.0 AA is a legal requirement here

### 6.1 Status is never signalled by colour alone

| `status` | `Badge variant` | Hebrew inside the Badge |
|---|---|---|
| `confirmed` | `success` | מאושר |
| `completed` | `neutral` | התקיים |
| `no_show` | `warning` | לא הגיעה |
| `cancelled` | `muted` | בוטל |

The **word inside the Badge carries the state** — the `CatalogSection` stock-badge precedent — so the variant is redundant reinforcement and the mapping survives greyscale, colour blindness and forced-colours mode. `danger` is **not** in the map: it is reserved for something the owner must fix, and a cancelled booking is a settled fact. There is no `gold` variant to reach for and that is not an omission — `gold-strong` is 3.80:1, under the 4.5:1 text floor, and a Badge is always small text (`tokens.md` gold law).

One subject shifts across the set: «לא הגיעה» is about the bride, «התקיים» about the appointment. Kept deliberately — it is the owner's own vocabulary, and «לא התקיים» would be indistinguishable from «בוטל» at a glance, on the one distinction E4 #19's refund arithmetic depends on.

### 6.2 Headings, landmarks, nav

- The console's single `h1` is the shell's (sr-only). The bookings section heading is **`h2`**; the detail's title is **`h2`** (it *replaces* the list in the same panel, so the panel always has exactly one `h2`); the detail's fact groups and action group are **`h3`**. No skipped levels, no second `h1`, and the `Modal`'s own title is an `h2` inside a `<dialog>` — a separate accessibility tree, not a level clash.
- The detail's `h2` is **`booking.detailTitle` («פרטי התור»), never the bride's name.** A name in the heading puts PII in the announced landmark of a screen the owner may present to someone standing beside her, and buys nothing: the name is the first fact row, one line below.
- The nav item is a plain `<nav>` `<button>` with `aria-current="page"` and `aria-controls="console-main"` (shell-provided). **No `role="tab"` anywhere** — a `role="tab"` without the full roving-tabindex/Arrow-key contract is a defect. The gold-strong underline is never the only active signal (`aria-current` + `font-semibold` also mark it).
- **The nav label is «תורים»**, one item away from the existing «סוגי תורים». Considered and accepted: the two are unambiguous read as words («תורים» = the appointments, «סוגי תורים» = their types), and «יומן תורים» would promise the calendar that is explicitly out of scope.

### 6.3 Bidi — the rule that has a wrong direction and a wronger one

Hebrew is `dir="rtl"`. Every interpolated value is isolated **at the call site**, and the isolation has two forms that are not interchangeable:

| Value | Wrapper | Why |
|---|---|---|
| time (`10:00`), date (`4.8.2026`), phone (`+972501234567`), terms version (`3`), seat index (`2`), dress size (`36`), the day count | **`<bdi dir="ltr">`** | numeric/Latin runs: without the explicit direction, a mixed run reorders around the surrounding Hebrew and a phone number renders with its digits in the wrong order |
| customer name, dress name, **`notes`** | **bare `<bdi>`** | free text authored by a person. `dir="ltr"` on Hebrew is **itself a bidi defect** (`BookPage.tsx:1019-1022`) — it forces Hebrew to render left-to-right. Bare `<bdi>` isolates the run and lets the UA infer direction per content, which is the only correct answer for a field that may hold Hebrew, Arabic, Latin or a mix |

Getting the phone wrong in the *first* direction is the likely defect and the one review should look for. Getting a Hebrew name wrapped in `dir="ltr"` is the worse one, because it looks deliberate.

`d.m.yyyy` — matching the approved SMS deck, so the owner sees one date spelling across the product — and `HH:MM`, both derived from the two `Intl.DateTimeFormat` instances in `apps/manage/src/lib/jerusalem.ts`. **Every formatter passes `timeZone: JERusalem`** (imported from `@boutique/ui`, never re-declared), including the day filter's own "today": a Jerusalem calendar date, never `new Date().toLocaleDateString()`. The new `qa-greps.sh` pattern `Intl\.DateTimeFormat\((?![^)]*timeZone)` is the mechanical backstop (D20).

### 6.4 The copy contract that discharges Risk 3(a)

The platform **cannot know** whether an SMS was delivered: `_deliver` swallows both `SmsSendError` and `SmsNotConfiguredError`, and before a provider exists `NotificationService` raises before its insert, so there is **no evidence row at all**. Therefore:

- **No string on this screen claims, implies or hedges a send, in any tense.** Every success cue states the **state change** and stops: «התור בוטל.», «המועד עודכן.», «הונפק קישור חדש. הקישור הקודם בוטל.» No «נשלחה הודעה», no «תישלח הודעה», no «ההודעה בדרך», no «ייתכן שההודעה נשלחה».
- **The limit is stated positively once**, as a standing `--text-sm --color-ink-muted` line at the head of the action group: the boutique cannot verify that messages were received, and if it matters she should phone. That is a truthful answer to the question the owner actually has ("will she find out?"), and it is better than silence, which reads as an implicit yes. It sits in the **muted** register, not `text-warning-text` — a permanent fact of the platform is not a warning about something that happened, and warning colour on every detail screen would cry wolf. (§7 P-1, flagged for the user.)
- **Zero exclamation marks**, here and everywhere. The product contains none (`he.ts` and the approved F14/F16 decks are mechanically checkable), so one would be the single string that breaks the register.

### 6.5 `notes` is text, and only text

`booking-core.md:173` names F15: "F15 must not innerHTML it." It is the product's first customer-authored string to reach the owner console. React escapes by default; **the rule is that F15 never opts out** — no `dangerouslySetInnerHTML`, no markdown pass, no linkification, no auto-`<a>`. `whitespace-pre-wrap` is the whole of the formatting.

### 6.6 The rest of the floor

- **≥44×44** on every target: `Button size="md"` is `min-h-11`; row buttons get there via `py-4` + `text-base`; `SlotPicker` chips are `min-h-11`. The back control ships `size="md"` for this reason (§5).
- **Visible focus ring** on every interactive element — `focusRing` from `@boutique/ui` (2px `--color-focus`, 2px offset). Nothing sets `outline: none`.
- **`SlotPicker`'s fieldset/legend/radio-group contract survives the promotion unchanged**: the `<legend>` stays the fieldset's first element child (it stops naming the group otherwise), the error `<p role="alert">` stays **outside** the fieldset for the same reason, radios stay `sr-only` with the `<label>` as the target, and `name` stays `useId`-scoped so two pickers on one page never merge. `BookPage.test.tsx:733-758` is what proves it, and it must keep passing after the move — the promotion changes three `t()` calls into a `labels` prop and nothing else.
- **Reduced motion**: nothing in this feature animates beyond the shipped `Modal` panel/backdrop transitions and the `Skeleton` pulse, both already frozen by the global `prefers-reduced-motion` block in `theme.css`.
- **`A11yMenu` / `A11yStatementLink` are storefront-only** (`tokens.md`) — the console does not ship them, so the `--space-a11y-footprint` footer reservation does not apply here.
- **An `axe` pass** runs over the list and detail in `__tests__` (spec Testing).

---

## 7. PROPOSED decisions (the user confirms at the gate)

- **P-1 — the standing "we cannot verify delivery" line** sits on every booking detail, in the muted register, at the head of the action group (§6.4). It answers the owner's real question without a delivery claim, and it is what turns Risk 3(a) from "say nothing" into "say the truth". The alternative was silence on the whole subject; silence reads as an implicit yes. Tonal call, so it is the user's.
- **P-2 — the reschedule dialog is its own confirm** (§3.1): one `Modal`, consequence sentence above the single submit, rather than a confirm Modal stacked on the picker Modal.
- **P-3 — the pre-selected current time is named above the picker**, not inside the chip label (§3.1) — because Hebrew inside `SlotPicker`'s `<bdi dir="ltr">` would be a bidi defect.
- **P-4 — no separate `EmptyState` in the reschedule dialog** (§3.1): `SlotPicker`'s own no-slots block is the state, and two stacked empty messages for one emptiness is worse than a small deviation from the spec's states-table cell.
- **P-5 — the four new error codes render Hebrew from a `booking.error.<CODE>` map; everything else renders the server's message.** See §8 F-2 — this is the one decision with a compliance edge, and it is deliberately raised rather than assumed.
- **P-6 — controls are absent, not disabled, for transitions the graph forbids** (§2). The alternative (four always-visible buttons, three of which 409) was rejected as a trap; the alternative-alternative (disabled with a tooltip) needs a tooltip pattern the console does not have.

## 8. ⚠ FINDINGS

- **F-1 — the shipped console announces nothing while loading.** `ProfileSection`, `CatalogSection` and `DressEditor` all render a bare `aria-hidden` `Skeleton` with no live region, so a screen-reader user hears silence between a tap and the data. On a surface carrying a statutory obligation that is a defect, and F15 closes it **for itself only**, at zero cost, by reusing regions it already needs: the list's `role="status"` count line carries `booking.listLoading` while loading, and the detail mounts its `role="status"` cue region immediately with `booking.detailLoading`. F15 does **not** retrofit the four hardcoded-Hebrew sections — same posture as the spec's i18n retrofit ruling (D16) — so this stays open against the E3 epic-boundary QA pass.
- **F-2 — backend error messages are English, on a Hebrew-only console.** `main.py`'s `*_BODY` literals are English ("That time was just taken. Choose another."), `api.ts` surfaces `ApiError.message` verbatim, and the four shipped sections already render them. D20 rules that for the phone field "the server's 400 is the only authority and the console renders its message" — which is a ruling about **not pre-validating**, not a ruling that the console must show English. IS 5568 makes the language of an error message operationally load-bearing for the owner who has to act on it. **Design ruling (P-5):** F15 ships a four-row `booking.error.*` map keyed on `ApiError.code` — `BOOKING_TRANSITION_INVALID`, `SLOT_UNAVAILABLE`, `CUSTOMER_ALREADY_BOOKED`, `TOO_MANY_ATTEMPTS` — with `errorMessage(error)` as the fallback for every other code. This is not a normalizer and mirrors no bound: the codes are pinned by `SPEC_ERROR_CODES` in `test_booking_owner_api.py`, so the map cannot silently drift, and `VALIDATION_ERROR` (whose message is computed per field) deliberately falls through to the server's text. The four existing sections are not retrofitted; recorded against the epic-boundary QA pass.
- **F-3 — `manage_link_issued` is the owner's only cue for Risk 9, and it is a weak one.** After a phone correction, a sibling booking whose reminder already fired holds no live link until the owner taps resend on **that** booking's detail — and nothing on the corrected booking's screen mentions the sibling. The design renders `manage_link_issued` as words in the facts group, but `manage_token_hash IS NOT NULL` stays **true** for a sibling whose token was rotated, so the field does not actually distinguish the broken case. Surfacing it properly needs a per-sibling read the spec ruled out. Recorded so the cue's weakness is a known limit rather than an assumed mitigation; owner: team, trigger: the first pilot report of a bride with two live bookings.
- **F-4 — the phone-correction Modal is the only place the attestation is stated, and it is dismissible.** After the update, nothing on the screen records that this number is owner-attested rather than OTP-verified (D1 declined an `owner_attested_phone` flag, and the audit row is not read in v1 — Risk 7). So the console cannot show the provenance of the number it is about to text. Correct per D1/D2, but it means the audit row is the *only* answer to an Amendment-13 complaint and there is no UI path to it. Recorded; trigger: the F21 security audit, where Risk 2 is already a named row.
- **F-5 — no he/ar parity guard exists in this repo** (spec Risk 5). `copy.md`'s `ar` column is transcribed into `apps/manage/src/i18n/ar.ts` by hand and nothing mechanically keeps it in step with `he.ts`. F15 does not invent the guard, because inventing it means owning it for every feature to F49. The mitigation is that this deck's copy table **is** the single source for both columns, so the transcription is one file to one file.
- **F-6 — a consumer `className` cannot override a `packages/ui` component's own utility, and nothing in the repo says so.** `cn()` (`lib/styles.ts:4`) is `values.filter(Boolean).join(" ")` — a plain join, deliberately no `clsx`/`tailwind-merge` ("no clsx dependency for a handful of conditionals"). So when a consumer passes a class that conflicts with one the component bakes in, both survive into the class attribute at equal specificity and the **stylesheet order decides**, not the JSX order. Tailwind emits utilities in its own sort order, which for these pairs is effectively alphabetical, and the built bundles (`apps/manage/dist`, `apps/storefront/dist`) show it resolving *against* the consumer in both cases this deck tried: `.text-danger` before `.text-ink` (so ghost's `text-ink` beats a consumer `text-danger`) and `.p-0` before `.p-6` (so `Card`'s `p-6` beats a consumer `p-0`). Both rev 1 specifications were silently inert, and one of them — the cancel trigger — would have shipped a destructive action rendered as an ordinary button. This is not a bug in `cn()`; the join is the right call for the conditionals it was written for. It is an **undocumented constraint** on every `packages/ui` consumer, and the reason no shipped component overrides a variant's colour or a `Card`'s padding is more likely that it was tried and quietly failed than that nobody wanted to. F15 obeys it (§1, §3.2) and does not fix it: the fix is either `tailwind-merge` (a dependency and a runtime cost for the whole system) or first-class props on the components that need them, and both are design-system decisions above this feature's pay grade. Recorded against the E3 epic-boundary QA pass; the cheap interim guard is a `qa-greps.sh` pattern for a `className` on a `packages/ui` component carrying a utility that component already sets. Trigger: the next deck that wants a variant it does not have — the right answer is to add the variant to `Button.tsx`, never to override one from the call site.

  **Where the myth came from, and what is still contaminated.** `screens/design-system/prototype.html:70` defines a real `.btn-ghost-danger` CSS class — transparent background, `color: var(--color-danger)` — and in that standalone HTML prototype it works, because there is no competing `text-ink` rule. The name then travelled into `manage-restyle.md` and from there into decks, but `packages/ui`'s React `Button` never gained the variant. **`manage-catalog.md` (F8) is still contaminated** at `:234`, `:288`, `:390`, `:534` and `:679`, and `:288` is provably wrong against what F8 actually shipped — it specifies `Button ghost-danger` with `color: var(--color-danger)` on paper for the dress archive row, where `DressEditor.tsx:401` ships `variant="danger"`. F15 does not edit another feature's approved deck; corrected here and in `manage-restyle.md` only, and F8's deck is flagged for the E3 epic-boundary QA pass. Note the contrast ledger consequence: `manage-catalog.md:679` certifies danger-on-surface at **6.18:1** for these buttons, whereas the shipped solid `danger` is white-on-danger at **≈7.0:1** — the shipped control is the *safer* of the two, so nothing that shipped is out of compliance; only the documents are wrong.
