# Screen: Date-bound dress reservation (F28 — manage catalog pane + storefront dress page, Epic E5)

**Date**: 2026-08-06 · **Status**: DESIGN GATE OPEN — awaiting critic + copy approval · **Designer**: Claude (main agent)
**Consumes**: `.planning/specs/dress-reservation.md` (Gate 1 standing-approved, D1–D8) · tokens rev 1 · `packages/ui` as shipped
**Copy**: every Hebrew row below needs APPROVAL before the gate closes. Register: calm, feminine address, **no exclamation marks** (pre-decided #5).

---

## 0. Scope

Two surfaces. **Manage**: a `ReservationsPane` inside `DressEditor.tsx`, third pane after `VariantMatrix` and `MediaGallery` — create/list/delete only (no edit; delete + re-add covers a postponed wedding, spec ceiling). **Storefront**: `DressPage.tsx` gains an unavailability block between sizes and the CTA; `BookPage` maps the new `DRESS_UNAVAILABLE` 409. Out of scope: calendar widgets or greyed-out picker dates (spec OUT), storefront-side reservation requests, any change to the slot engine or the dress *card*.

**Binding inheritances, obeyed not restated**: three-gold law · R19 bidi isolation (`<bdi dir="ltr">` islands for every numeral run) · `Intl.DateTimeFormat('he-IL')` house formatting · logical properties only (physical direction props are a review defect, manage-catalog §preamble) · F-W1 (`Button size="sm"` is 36px, fails the 44px floor — **md only** on touch controls) · the house focus rule (the mover is the state change that mounted the target) · discrete-event-only live regions.

**Date inputs — verified**: `packages/ui` ships `DateField` (`DateTimeFields.tsx`) = native `<input type="date">` through the shared `Input`, which supplies the full contract: real `<label for>`, `help` via `aria-describedby`, `error` as `role="alert"` + `aria-invalid`. `SlotPicker` already uses it ("no calendar" comment is house doctrine). **Use `DateField`; invent nothing.**

## 1. Manage — `ReservationsPane` (`apps/manage/src/components/ReservationsPane.tsx`)

Same pane contract as `VariantMatrix`/`MediaGallery`: `dressId` null in create mode → disabled Card with reason; archived dress → disabled with `ARCHIVED_REASON`. The shared `CREATE_HINT` constant is reworded (§3, C-M1). Copy is **inline Hebrew constants** — the F8 catalog convention the spec pins (D8); no manage i18n keys are minted (recorded ruling, the newer-sections `t()` style stops at this file's boundary).

```
+-- Card -----------------------------------------------+
| הזמנות לתאריך                          (hard-coded h3 — matches sibling panes, §8)
| [explainer line, --text-sm ink-muted]                 |
|                                                       |
| תאריך החתונה   [ 2026-08-12 ]          DateField      |
|   [help: prefill explanation]                         |
| מהתאריך [ 2026-08-12 ]  עד התאריך (כולל) [ 2026-08-17 ]   two DateFields, row ≥640, stacked @375
| לקוחה (לא חובה)  [ חיפוש שם או טלפון ]  §1.1          |
| הערות  [TextArea, maxLength 500, dir="auto"]          |
|   [char counter, <bdi dir="ltr">, editor precedent]   |
| [form-level role="alert" line — overlap / validation] |
|                              [ הוספת הזמנה ]  Button md
|-------------------------------------------------------|
| <bdi>12–17</bdi> באוגוסט · רותם לוי · [notes]  [ מחיקה ] Button danger md
| <bdi>3–9</bdi> בספטמבר                        [ מחיקה ] |
+-------------------------------------------------------+
```

- **Prefill**: typing the wedding date sets `starts_on = date`, `ends_on = date + RESERVATION_BUFFER_DAYS` (FE constant, **5**); both range fields then fully editable and never re-clobbered by later wedding-date edits unless the range fields are still untouched. Wedding-date field is a convenience, not sent to the server.
- **List**: live reservations newest `starts_on` first (server order), each row range (§5 formatting) · customer name when linked (pointer resolved server-side) · notes as plain text · delete. Past rows still listed — the owner ends a rental early by deleting it.
- **Delete confirms via `Modal`** — the MediaGallery precedent in this same file covers the modal shape only (ghost «ביטול» + danger confirm). The post-delete focus handling is **new here, not inherited**: MediaGallery relies on native `<dialog>` focus-return-to-trigger, which silently fails once the deleted row unmounts, and ships no fallback — there is nothing to copy. ReservationsPane instead uses the shipped house pattern for post-mutation focus — a `role="status" tabIndex={-1}` list/count region as the focus destination after a mutation (`BookingsSection.tsx` ~line 110, `CatalogSection.tsx` ~line 154) — and on modal close after a successful delete moves focus there explicitly. Not the waitlist in-place swap: same-file consistency wins for the modal shape (P2).
- **Overlap 409** (`RESERVATION_OVERLAP`): form-level `role="alert"` line under the fields (VariantMatrix shape), interpolating the conflicting range from `details` (§3 C-M8). Fields keep their values — the fix is editing dates, not retyping everything.
- **Add success**: form clears, row appears in list, hidden `role="status"` region announces C-M12; focus stays on the add button (P3 — no focus jump for a non-navigating success).

### 1.1 Customer picker (optional)

Reuse the CustomersSection search shape against the shipped `listCustomers` query: one `Input` (label C-M6, `dir="auto"`), results as a short list of `Button variant="ghost" size="md"` rows (name · phone via `<bdi dir="ltr">`); picking one collapses the search into the chosen name + an «הסרה» ghost button. No new endpoint, no combobox ARIA gymnastics — it is a filtered list of buttons, each a real tab stop. A renter not in CRM goes in notes (C-M7 help says so).

## 2. Storefront — `DressPage.tsx` unavailability block

Renders between the sizes list and `BookingCTAButton`, **only when `unavailable_ranges` is non-empty**. Plain static content — no live region, no alert: nothing happened, this is a fact about the dress.

```
| מוזמנת בתאריכים                     h2, text-sm ink-muted — same level/style as «מידות» |
|   <bdi>12–18</bdi> באוגוסט          ul, one li per range, --text-base ink               |
|   28 בדצמבר – 2 בינואר 2027                                                            |
| בשאר התאריכים אפשר לקבוע מדידה.     --text-sm ink-muted                                 |
```

The note line is Q9 spelled as copy: it keeps the fitting CTA honest and un-scary — the ranges state where the gown is, the note states what stays possible, and the CTA below stays exactly as the shipped reserved-dress test pins it. No warning colour, no icon, no badge tone: `--color-ink` on surface, the same register as the sizes block. The `reserved` boolean's «הוזמן» badge is orthogonal and may render simultaneously (D5).

**`BookPage`**: `DRESS_UNAVAILABLE` joins the `errorMessageKey` switch → `errors.dressUnavailable` (house `errors.*` shape; the spec's `booking.errors.dressUnavailable` is read as intent, P1). It renders via the `stepAlert` mechanism — the pattern `errors.tooManyAttempts` uses (~BookPage line 1548): stay on the current step, muted `role="alert"` paragraph, NO navigation and NO slot refetch. Explicitly NOT the `SLOT_UNAVAILABLE` path: that one calls `recoverSlot()` (navigate back to /book/slot + refetch), and since the slot list has zero awareness of reservation windows (spec D4), reusing it would re-offer the same times on the blocked day and loop the 409. The copy itself names the remedy (another date). No picker changes (spec OUT).

## 3. Copy — manage inline Hebrew (each row needs approval)

| # | Where | Hebrew | English annotation |
|---|---|---|---|
| C-M1 | shared `CREATE_HINT` reword | יש לשמור את השמלה לפני הוספת מידות, תמונות והזמנות | "Save the dress before adding sizes, photos and reservations" |
| C-M2 | pane heading | הזמנות לתאריך | "Date reservations" — spec-given |
| C-M3 | explainer | בתאריכים האלה השמלה מוצגת באתר כלא זמינה, ומדידות בתאריכים אחרים נקבעות כרגיל. | "On these dates the site shows the dress as unavailable; fittings on other dates book as usual." |
| C-M4 | wedding date label + help | תאריך החתונה · הטווח מתמלא אוטומטית — יום החתונה ועוד חמישה ימים לניקוי ולהחזרה. אפשר לערוך את התאריכים. | "Wedding date · Range auto-fills — wedding day plus five days for cleaning and return. The dates can be edited." |
| C-M5 | range labels | מהתאריך · עד התאריך (כולל) | "From date · To date (inclusive)" — inclusive stated on the label, D2 |
| C-M6 | customer label | לקוחה (לא חובה) — חיפוש לפי שם או טלפון | "Customer (optional) — search by name or phone" — reuses the customers-search wording |
| C-M7 | notes label + help | הערות · לקוחה שאינה במערכת אפשר לרשום כאן. | "Notes · A customer not in the system can be written here." |
| C-M8 | overlap error | התאריכים מתנגשים עם הזמנה קיימת ({{range}}). אפשר לבחור תאריכים אחרים. | "The dates clash with an existing reservation ({{range}}). Other dates can be chosen." — range from 409 `details`, §5 format |
| C-M9 | validation errors | תאריך הסיום לפני תאריך ההתחלה · טווח ההזמנה ארוך משנה | "End date before start date" (ends field) · "Reservation longer than a year" (form line) |
| C-M10 | add button | הוספת הזמנה | "Add reservation" — primary md |
| C-M11 | empty list | אין הזמנות לשמלה הזאת. | "No reservations for this dress." — shared `EmptyState` component (title + one-line body), matching the sibling panes' contract: VariantMatrix.tsx:237 and MediaGallery.tsx:446 both use `EmptyState` for their in-pane empty states. Body: הוסיפי הזמנה בטופס למטה. ("Add a reservation in the form below.") |
| C-M12 | added (status region) | ההזמנה נוספה. | "Reservation added." |
| C-M13 | delete button / modal title / body / confirm | מחיקה · למחוק את ההזמנה? · מחיקת ההזמנה מפנה את התאריכים באתר מיד, גם אם ההשכרה עדיין פעילה. · מחיקה | "Delete · Delete the reservation? · Deleting frees the dates on the site immediately, even if the rental is still active." — the body IS the end-early copy; ghost «ביטול» cancels |
| C-M14 | deleted (status region) | ההזמנה נמחקה. | "Reservation deleted." |
| C-M15 | `reserved` toggle helper reword | סימון ידני ללא תאריך, למשל שמלה שנמכרה. להשכרה בתאריכים ידועים משתמשים ב«הזמנות לתאריך» למטה. | "Manual, date-less mark — e.g. a sold dress. For a rental with known dates use «Date reservations» below." — D5's narrowing, pointed at the pane |
| C-M16 | load error + retry | לא הצלחנו לטעון את ההזמנות כרגע. · ניסיון נוסף | "Couldn't load the reservations right now." · "Try again" — console honest-failure shape |

## 4. Copy — storefront i18n keys (he.ts; `ar.ts` mirrors with Hebrew values, pre-decided #47)

| Key | Hebrew | English annotation |
|---|---|---|
| `dress.reservedDatesHeading` | מוזמנת בתאריכים | "Reserved on these dates" — spec-given |
| `dress.reservedDatesNote` | בשאר התאריכים אפשר לקבוע מדידה. | "On all other dates a fitting can be booked." — spec-given, the CTA-protecting line |
| `errors.dressUnavailable` | השמלה אינה זמינה בתאריך שנבחר. אפשר לבחור תאריך אחר. | "The dress is unavailable on the chosen date. Another date can be chosen." — spec-given, D4 |

## 5. Range formatting — one helper, both apps' rules identical

`Intl.DateTimeFormat('he-IL', { day: 'numeric', month: 'long' })`, year appended only when it differs from the current year (spec D6). Same month: one numeral island `<bdi dir="ltr">12–18</bdi> באוגוסט` (en-dash **inside** the island). Cross-month: each date formatted whole, en-dash between them in RTL flow, every numeral run its own `<bdi>` (R19 split shape): `28 באוגוסט – 3 בספטמבר`. Cross-year: `28 בדצמבר 2026 – 2 בינואר 2027`.

**Trap (binding on the build)**: `starts_on`/`ends_on` are date-only strings. `new Date("2026-08-12")` parses as UTC midnight — format with `timeZone: "UTC"` on that object (or split the string) so the rendered day can never shift. Never route these through the Jerusalem-timezone datetime formatter. Prefill arithmetic (`+5`) runs in date parts, not milliseconds.

## 6. States

| Surface | State | Treatment |
|---|---|---|
| Pane | create mode | disabled Card, C-M1 hint — VariantMatrix contract verbatim |
| Pane | archived dress | disabled, `ARCHIVED_REASON` (endpoints 404 anyway) |
| Pane | loading | Card-shaped `Skeleton` + hidden status «טוענת את ההזמנות» |
| Pane | loaded / empty | list / C-M11 `EmptyState`; form always present |
| Pane | add in-flight | add button `loading`; double-submit guarded |
| Pane | overlap / validation | C-M8 / C-M9, form keeps values |
| Pane | delete confirm / in-flight / error | Modal → danger `loading` → shipped error `Toast`, row stays |
| Pane | load error | C-M16 inline `role="alert"` + secondary retry |
| DressPage | no ranges | block absent — no empty heading ever renders |
| DressPage | ranges | §2 block; past rows already excluded server-side |
| BookPage | claim 409 | `errors.dressUnavailable` via `stepAlert` (no navigation, no refetch) |

## 7. RTL + responsive

Logical properties only. LTR islands: date values (native input renders localized; no `dir` override on `DateField`), every numeral run per §5, phone runs in the picker. Manage: 720px console column, fields stack @375, range fields pair up ≥640; table-free pane so no overflow container needed. Storefront block is plain stacked text — nothing to break at 375/768/1440. Reduced motion: nothing animates beyond shipped `--motion-fast` button transitions.

## 8. Accessibility (IS 5568 / WCAG 2.0 AA — legal floor)

- **Date inputs**: `DateField`'s shipped contract (real label, help via `aria-describedby`, `role="alert"` field errors) is the whole a11y story; native `type="date"` is keyboard-operable by default. No custom picker exists to audit.
- **Errors**: field-level on the offending field (C-M9 first item on the end-date field), cross-field/overlap on the form-level `role="alert"` line. Announced on mount, never per keystroke.
- **Focus**: after delete, focus moves explicitly to the pane's `role="status" tabIndex={-1}` list region — the shipped post-mutation focus pattern (`BookingsSection.tsx` ~110, `CatalogSection.tsx` ~154), **new behavior in this pane**, not inherited from MediaGallery (whose native `<dialog>` focus-return fails silently when the trigger row unmounts, with no fallback); add keeps focus (P3). Pane heading is a hard-coded `<h3>`, matching `VariantMatrix` (line 149), `MediaGallery` (line 356) and `DressEditor`'s field card (line 260) as shipped — the documented `headingLevel` cascade is unshipped in every sibling pane, and implementing it in this pane alone would fracture the sibling heading outline at ≤767.
- **Targets**: every control `Button` **md** or the 44px-padded shipped inputs — no `sm` anywhere in this feature (F-W1).
- **axe-zero (e2e)**: pane in create-disabled, loaded, overlap-error and modal-open states; dress page with ranges (+ RTL rendering of `<bdi>` lines); BookPage error state.

## 9. What these surfaces deliberately do not have

No calendar/greyed dates (spec OUT) · no edit action (delete + re-add, D8 ceiling) · no date-aware storefront badge (D5 — an October bride must not be scared off by an August rental) · no warning styling on the storefront block · no PII text fields (customer is a pointer; notes is the accepted owner-text class, D7) · no exclamation marks anywhere · no manage i18n keys (F8 inline convention, §1).

## 10. PROPOSED (user confirms at the gate)

- **P1** — error key ships as `errors.dressUnavailable` inside the house `errorMessageKey` switch; the spec's `booking.errors.dressUnavailable` spelling is read as intent, not a new namespace.
- **P2** — delete confirms in a `Modal` (MediaGallery precedent, same file) rather than the waitlist's in-place swap; "end early" is the same delete, carried by C-M13's body copy instead of a second action.
- **P3** — add success announces via status region without moving focus; the form is the owner's continuing context (she often records several rentals in a row).

## 11. ⚠ FINDINGS

- **F-R1**: C-M1/C-M15 reword shipped strings — grep manage unit/e2e tests for the old literals («יש לשמור את השמלה לפני», «סימון ידני, ללא תאריך») before merge; pinned copy assertions will red.
- **F-R2**: the date-only parsing trap (§5) will pass every test in Israel (UTC+2/+3) and fail west of UTC — the FE unit test for formatting must pin the `timeZone: "UTC"` call, not just the output string.
- **F-R3**: storefront `dress.*` block already exists in `he.ts` — the two new keys slot in there; `ar.ts` must gain the same rows (Hebrew values) in the same commit or the i18n floor test reds.

Design Gate: accepted by design-critic (round 3), 2026-08-06
