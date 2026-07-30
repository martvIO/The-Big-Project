# Copy deck — F15 Owner bookings (`apps/manage`, section «תורים»)

**Date**: 2026-07-30 · **Status**: DRAFTED under the approved register, self-approved with the design gate (Interview **Q2**), **flagged for the user's one-line edit** — this is console copy, not a customer-facing SMS, so there is no counsel gate · **Owner of the Hebrew: the user** · **Consumes**: `.planning/specs/owner-booking-management.md` (D1–D20) · **Lands in**: `Frontend/apps/manage/src/i18n/he.ts` (`nav.bookings` + a new `booking.*` namespace) and the **new** `Frontend/apps/manage/src/i18n/ar.ts`

**F15 adds no SMS template, changes no existing body, and does not touch `comms_templates.py`** (D13). There is no §SMS section in this deck, deliberately — the four approved bodies live in `../manage-booking/copy.md` §3 and none of them changes.

## 0. The rules this deck is written under — hard constraints, not preferences

1. **Zero exclamation marks.** The product contains none; `he.ts` and the approved F14/F16 decks are mechanically checkable. One here would be the single string that breaks the register.
2. **Never promise or imply an SMS was sent, in any tense.** `_deliver` swallows both `SmsSendError` and `SmsNotConfiguredError` (`comms.py:403-435`), and before a provider exists `NotificationService` raises before its insert (`notifications/service.py:104-105`) — so there is **no evidence row at all**. Every string states the **state change** and stops. No «נשלחה», no «תישלח», no «ההודעה בדרך», no «ייתכן ש…». This deck is what discharges spec **Risk 3(a)**; §4's `booking.deliveryNotice` states the limit positively, once.
3. **«Resend» is a rotation, and the Hebrew says the old link stops working** (D9). Both reasons to resend want the previous link dead, and for a booking whose reminder already fired a plain re-send is impossible anyway — `bookings` holds only the sha256 and terminal `scheduled_messages` rows clear the raw token.
4. **The phone correction is owner-attested, and the copy never claims the number was verified** (D8). It says the platform does not verify it and that the record is on the boutique's word.
5. **Plain-fact wording for bad news.** No marketing register, no reassurance the platform cannot back, no apology theatre.
6. **Every value is a real string.** No `…`-as-placeholder, no Lorem, nothing to be filled in later.
7. **The `ar` column is the approved Hebrew, standing in untranslated** (Interview Q3 / pre-decided #47). It is **never an empty string**: i18next's `returnEmptyString` default renders `""` rather than falling back, so a premature switch would blank the page instead of showing Hebrew. `lng` stays `"he"`, `fallbackLng` stays `"he"`, no switcher ships.

**77 rows.** Every one of them is a key F15 invents; F15 reuses no existing `booking.*` key (the storefront's `booking.*` namespace is a different app and a different catalog).

---

## 1. Navigation and section chrome

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated placeholder) | Status |
|---|---|---|---|---|
| `nav.bookings` | The sixth console nav item. One item away from «סוגי תורים» — read as words the two are unambiguous, and «יומן תורים» would promise the calendar that is out of scope | תורים | תורים | DRAFTED |
| `booking.heading` | The section `h2` | תורים | תורים | DRAFTED |

## 2. The day list

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `booking.dateLabel` | Visible label on the `DateField` day filter — a placeholder is never the label | תאריך | תאריך | DRAFTED |
| `booking.listLoading` | Carried by the `role="status"` count line while the day fetch is in flight (design F-1: the shipped console announces nothing while loading) | טוען תורים… | טוען תורים… | DRAFTED |
| `booking.dayCount` | The count line. **Label-then-number**, so it is grammatical at every count — Hebrew plural forms (one/two/many/other) would be four rows to say what one row says correctly | תורים ביום זה: {{count}} | תורים ביום זה: {{count}} | DRAFTED — `{{count}}` renders inside `<bdi dir="ltr">` |
| `booking.loadFailed` | Day list failed to load — the **outage** register: recoverable, unblaming, no technical words. Re-selecting the date refetches, so no retry control is offered | לא הצלחנו לטעון את התורים כרגע. | לא הצלחנו לטעון את התורים כרגע. | DRAFTED |
| `booking.emptyDayTitle` | `EmptyState` title for a day with no bookings — a fact, not a fault | אין תורים בתאריך הזה | אין תורים בתאריך הזה | DRAFTED |
| `booking.emptyDayBody` | The body. **No CTA** — the owner cannot create a booking (Interview Q6), so an action prompt here would point at nothing | אפשר לבחור תאריך אחר. | אפשר לבחור תאריך אחר. | DRAFTED |
| `booking.attendanceConfirmed` | The bride confirmed attendance through her link. Muted words on the row's meta line — **not** a second Badge, so nothing competes with the status chip | אישרה הגעה | אישרה הגעה | DRAFTED |

## 3. Status — the word inside the Badge carries the state

Status is **never** signalled by colour alone; the variant is redundant reinforcement (`Badge` has no gold variant — `gold-strong` is 3.80:1, under the text floor).

| Key | Badge variant | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|---|
| `booking.statusConfirmed` | `success` | The live, standing appointment | מאושר | מאושר | DRAFTED |
| `booking.statusCompleted` | `neutral` | It happened | התקיים | התקיים | DRAFTED |
| `booking.statusNoShow` | `warning` | She did not come. The subject shifts to the bride here and that is deliberate — «לא התקיים» would be indistinguishable from «בוטל» at a glance, on exactly the distinction E4 #19's refund arithmetic reads | לא הגיעה | לא הגיעה | DRAFTED |
| `booking.statusCancelled` | `muted` | A settled fact, not something to fix — which is why the variant is `muted` and never `danger` | בוטל | בוטל | DRAFTED |

## 4. The detail — chrome and facts

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `booking.back` | Returns to the day list | חזרה לרשימה | חזרה לרשימה | DRAFTED |
| `booking.detailTitle` | The detail `h2` and the focus destination. **Never the bride's name** — a name in the announced heading is PII in the landmark, and it is the first fact row one line below anyway | פרטי התור | פרטי התור | DRAFTED |
| `booking.detailLoading` | The `role="status"` region while the detail loads | טוען את פרטי התור… | טוען את פרטי התור… | DRAFTED |
| `booking.notFound` | 404 — including another tenant's id, which RLS makes indistinguishable from missing, by design | התור הזה לא נמצא. | התור הזה לא נמצא. | DRAFTED |
| `booking.customerHeading` | `h3` of the customer group | הלקוחה | הלקוחה | DRAFTED |
| `booking.customerName` | Label; value is a bare `<bdi>` | שם | שם | DRAFTED |
| `booking.customerPhone` | Label; value is `<bdi dir="ltr">` | טלפון | טלפון | DRAFTED |
| `booking.appointmentHeading` | `h3` of the appointment group | הפגישה | הפגישה | DRAFTED |
| `booking.when` | Label for date + time, both Jerusalem, both LTR-isolated | מועד | מועד | DRAFTED |
| `booking.type` | Label for the appointment-type snapshot | סוג הפגישה | סוג הפגישה | DRAFTED |
| `booking.dress` | Label for the dress snapshot; the name is a bare `<bdi>` | שמלה | שמלה | DRAFTED |
| `booking.dressSize` | Inline label before the size digits | מידה | מידה | DRAFTED |
| `booking.seat` | The seat index. Rendered plainly because with capacity > 1 it is how the owner tells two 14:00 appointments apart in her own room | עמדה | עמדה | DRAFTED |
| `booking.createdAt` | When the booking was made | נקבע בתאריך | נקבע בתאריך | DRAFTED |
| `booking.terms` | Label for the accepted-policy evidence | מדיניות שאושרה | מדיניות שאושרה | DRAFTED |
| `booking.termsVersion` | The version, rendered beside the acceptance date | גרסה {{version}} | גרסה {{version}} | DRAFTED — `{{version}}` inside `<bdi dir="ltr">` |
| `booking.manageLink` | Label for the manage-link fact | קישור ניהול | קישור ניהול | DRAFTED |
| `booking.manageLinkIssued` | `manage_token_hash IS NOT NULL`. Words, not a chip — one Badge per screen region, and the status owns it. The hash itself never reaches the wire | קישור ניהול פעיל | קישור ניהול פעיל | DRAFTED |
| `booking.manageLinkMissing` | No link was ever issued for this booking | לא הונפק קישור ניהול | לא הונפק קישור ניהול | DRAFTED |
| `booking.cancelledAt` | Shown only on a cancelled booking | בוטל בתאריך | בוטל בתאריך | DRAFTED |
| `booking.cancelledBy` | Label for `cancelled_by` | בוטל על ידי | בוטל על ידי | DRAFTED |
| `booking.cancelledByOwner` | `cancelled_by = 'owner'` | הבוטיק | הבוטיק | DRAFTED |
| `booking.cancelledByCustomer` | `cancelled_by = 'customer'` | הלקוחה | הלקוחה | DRAFTED |
| `booking.notesHeading` | `h3` of the notes group, kept last because it is the only free-text block and may be long | הערות הלקוחה | הערות הלקוחה | DRAFTED |
| `booking.notesEmpty` | No notes — a fact, not an invitation. The owner cannot write notes here | הלקוחה לא הוסיפה הערות. | הלקוחה לא הוסיפה הערות. | DRAFTED |

## 5. Actions — the group heading, the standing limit, and the cancelled dead end

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `booking.actionsHeading` | `h3` of the action group | פעולות | פעולות | DRAFTED |
| `booking.deliveryNotice` | **The Risk 3(a) discharge, stated positively once.** The platform cannot verify delivery, so instead of a lie or a silence that reads as an implicit yes, the screen says the limit and names the human exit. Muted register, not warning colour — a permanent property of the platform is not an alarm about something that happened | אין באפשרותנו לאמת שהודעות נמסרו ללקוחה. אם חשוב לוודא, אפשר להתקשר אליה. | אין באפשרותנו לאמת שהודעות נמסרו ללקוחה. אם חשוב לוודא, אפשר להתקשר אליה. | **PROPOSED (design P-1)** — tonal call, the user's |
| `booking.cancelledNoActions` | The whole action group on a cancelled booking. `cancelled` is terminal (D3) and owner-created bookings are out of scope (Q6), so the honest remedy is the storefront. Names it plainly rather than leaving a blank panel | תור שבוטל אינו ניתן לשחזור. לקביעת מועד חדש, הלקוחה מזמינה מחדש דרך אתר הבוטיק. | תור שבוטל אינו ניתן לשחזור. לקביעת מועד חדש, הלקוחה מזמינה מחדש דרך אתר הבוטיק. | DRAFTED |

## 6. Cancel — the only irreversible act

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `booking.cancelCta` | Ghost-danger trigger. States the act, no euphemism | ביטול התור | ביטול התור | DRAFTED |
| `booking.cancelModalTitle` | Modal title — a real question, not a warning | לבטל את התור? | לבטל את התור? | DRAFTED |
| `booking.cancelModalBody` | The consequence, in order of what she can no longer undo: it is final; the seat re-opens; the only route back is a customer rebook. **No money words** — deposits are E4. **No delivery claim** | הביטול סופי ואי אפשר לשחזר אותו. המועד יתפנה להזמנה, ולקביעת מועד חדש הלקוחה מזמינה מחדש דרך אתר הבוטיק. | הביטול סופי ואי אפשר לשחזר אותו. המועד יתפנה להזמנה, ולקביעת מועד חדש הלקוחה מזמינה מחדש דרך אתר הבוטיק. | DRAFTED |
| `booking.cancelConfirm` | The `danger` button — the click that destroys. The feature's only `danger` variant | אישור הביטול | אישור הביטול | DRAFTED |
| `booking.modalKeep` | Shared dismiss for both confirm Modals. Deliberately not «ביטול» — a cancel button on a cancellation dialog is the worst word in the deck | חזרה | חזרה | DRAFTED |
| `booking.cancelDone` | Inline success cue. State change only | התור בוטל. | התור בוטל. | DRAFTED |

## 7. Attendance outcomes — direct buttons, inline cues, no SMS at all (D13)

No template exists for these and none is added: a fifth body means a new copy row plus the Amendment-40 counsel gate, and texting a bride «you did not show up» is not a status field's decision. Ruled silent, not deferred — so none of these strings mentions the customer being told.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `booking.noShowCta` | Mark no-show. Legal only on a past `confirmed` / `completed` booking | סימון: לא הגיעה | סימון: לא הגיעה | DRAFTED |
| `booking.noShowDone` | Inline cue | התור סומן: לא הגיעה. | התור סומן: לא הגיעה. | DRAFTED |
| `booking.completeCta` | Mark completed | סימון: התקיים | סימון: התקיים | DRAFTED |
| `booking.completeDone` | Inline cue | התור סומן: התקיים. | התור סומן: התקיים. | DRAFTED |
| `booking.reopenCta` | The undo of a mis-tap, from `no_show` or `completed` back to `confirmed`. Named for the status it restores, because the console's buttons are named for the four statuses (D3 declined renaming the endpoint to `/reopen` for the same reason — one vocabulary) | החזרה לסטטוס מאושר | החזרה לסטטוס מאושר | DRAFTED |
| `booking.reopenDone` | Inline cue | הסטטוס הוחזר למאושר. | הסטטוס הוחזר למאושר. | DRAFTED |

## 8. Reschedule

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `booking.rescheduleCta` | Opens the dialog | שינוי מועד | שינוי מועד | DRAFTED |
| `booking.rescheduleTitle` | Modal title | שינוי מועד התור | שינוי מועד התור | DRAFTED |
| `booking.rescheduleCurrent` | Names the pre-selected current time **above** the picker — it cannot go inside a chip label, because `SlotPicker` renders labels in `<bdi dir="ltr">` and Hebrew there is itself a bidi defect | המועד הנוכחי: | המועד הנוכחי: | DRAFTED — the instant follows in `<bdi dir="ltr">` |
| `booking.rescheduleConsequence` | The consequence sentence above the single submit — this dialog **is** the confirm (design P-2). Says the link will point at the new time; **does not** say the old link dies, because reschedule only rotates the token when no pending reminder exists to inherit from (D11), so an unconditional rotation claim would be false half the time. **No delivery claim** | המועד יתעדכן, והקישור של הלקוחה יצביע על המועד החדש. | המועד יתעדכן, והקישור של הלקוחה יצביע על המועד החדש. | DRAFTED |
| `booking.rescheduleConfirm` | The submit | עדכון המועד | עדכון המועד | DRAFTED |
| `booking.rescheduleDone` | Inline cue | המועד עודכן. | המועד עודכן. | DRAFTED |
| `booking.pickDate` | `SlotPicker` `labels.pickDate` — the promotion turns three `t()` calls into props (D14) | תאריך | תאריך | DRAFTED |
| `booking.pickTime` | `SlotPicker` `labels.pickTime` — the fieldset `<legend>` | שעה | שעה | DRAFTED |
| `booking.noSlots` | `SlotPicker` `labels.noSlots`, serving both whole-window-empty and this-date-empty (one block, one string — the F14 ruling). Names the real remedy: there is no owner override of published availability (D5), so the way to open an unusual hour is an availability exception | אין מועדים פנויים בתאריך הזה. אפשר לבחור תאריך אחר, או לפתוח שעות נוספות במסך «שעות פעילות». | אין מועדים פנויים בתאריך הזה. אפשר לבחור תאריך אחר, או לפתוח שעות נוספות במסך «שעות פעילות». | DRAFTED |

## 9. Resend the manage link — a rotation, and the copy says so (D9)

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `booking.resendCta` | The button. Named «הנפקת קישור **חדש**», not «שליחה מחדש» — the verb has to carry the rotation, because a re-send of the same link is not a thing the platform can do | הנפקת קישור ניהול חדש | הנפקת קישור ניהול חדש | DRAFTED |
| `booking.resendHint` | Permanent `--text-xs` muted line **under the button** — pre-tap, since resend gets no confirm Modal. This is D9's requirement discharged where she reads it before acting | הנפקת קישור חדש מבטלת את הקישור הקודם של הלקוחה. | הנפקת קישור חדש מבטלת את הקישור הקודם של הלקוחה. | DRAFTED |
| `booking.resendDone` | Inline cue. Two state changes, no send | הונפק קישור חדש. הקישור הקודם בוטל. | הונפק קישור חדש. הקישור הקודם בוטל. | DRAFTED |

## 10. Phone correction — the dangerous surface (D8, Risk 2)

The one place in F15 where the copy carries a legal weight: after D8 a `customers.phone` can be an owner-typed value with **no possession proof behind it**, narrowing an invariant E3 stated three times to "verified at creation, owner-attested thereafter, with an audit row". The Hebrew must not paper over that.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `booking.phoneEditCta` | Reveals the inline field. «תיקון» not «עדכון» — this is a remedy for a number that demonstrably does not work, not routine maintenance | תיקון מספר הטלפון | תיקון מספר הטלפון | DRAFTED |
| `booking.phoneFieldLabel` | The `Input` label. The field opens **empty** — a pre-filled wrong number invites a one-character edit of the value she is trying to replace | מספר טלפון חדש | מספר טלפון חדש | DRAFTED |
| `booking.phoneEditCancel` | Closes the inline field without saving | ביטול העריכה | ביטול העריכה | DRAFTED |
| `booking.phoneSaveCta` | Opens the confirm Modal | שמירת המספר | שמירת המספר | DRAFTED |
| `booking.phoneModalTitle` | Modal title | לעדכן את מספר הטלפון? | לעדכן את מספר הטלפון? | DRAFTED |
| `booking.phoneModalBody` | Three things and no more: **echo the typed number** so the Modal is a proofreading step; state that the platform does **not verify** it and the record stands on the boutique's word (never «אומת», never «נבדק»); state that the existing link stops working and a new one is issued. **No delivery claim** | המספר שהוזן: {{phone}}. המערכת אינה מאמתת שהמספר שייך ללקוחה — העדכון נרשם על אחריות הבוטיק. הקישור הקיים של הלקוחה יפסיק לעבוד, ובמקומו יונפק קישור חדש. | המספר שהוזן: {{phone}}. המערכת אינה מאמתת שהמספר שייך ללקוחה — העדכון נרשם על אחריות הבוטיק. הקישור הקיים של הלקוחה יפסיק לעבוד, ובמקומו יונפק קישור חדש. | DRAFTED — `{{phone}}` renders **as typed**, inside `<bdi dir="ltr">` |
| `booking.phoneModalConfirm` | The commit | עדכון המספר | עדכון המספר | DRAFTED |
| `booking.phoneDone` | Inline cue. Two state changes, no send, no claim of verification | מספר הטלפון עודכן. הקישור הקודם בוטל. | מספר הטלפון עודכן. הקישור הקודם בוטל. | DRAFTED |

## 11. Errors — Hebrew for the four codes F15 owns

**Design P-5 / finding F-2.** `main.py`'s error bodies are English ("That time was just taken. Choose another.") and `api.ts` surfaces them verbatim, so without this map a Hebrew-only console shows English on the one screen where the owner must act on the message. This is **not** a client-side validator and mirrors no server bound (D20's ruling stands: no phone normalizer, no pattern, no length rule) — it is a code→string map, and the codes are pinned by `SPEC_ERROR_CODES` in `test_booking_owner_api.py`, so it cannot silently drift. Any other code, `VALIDATION_ERROR` included — whose message is computed per field and cannot be reproduced client-side — falls through to `errorMessage(error)`, the server's own text.

| Key | Raised by | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `booking.error.BOOKING_TRANSITION_INVALID` | An illegal status pair, no-show/complete before `starts_at`, cancel after `starts_at`, resend/phone/reschedule on a booking that is not confirmed-and-future, or a row another request moved between the read and the write | לא ניתן לבצע את הפעולה במצב הנוכחי של התור. כדאי לחזור לרשימה ולפתוח את התור מחדש. | לא ניתן לבצע את הפעולה במצב הנוכחי של התור. כדאי לחזור לרשימה ולפתוח את התור מחדש. | **PROPOSED (design P-5)** |
| `booking.error.SLOT_UNAVAILABLE` | The reschedule target is off-grid, past, closed, full, or was taken in the seconds since the grid was fetched | המועד הזה נתפס הרגע. אפשר לבחור מועד אחר. | המועד הזה נתפס הרגע. אפשר לבחור מועד אחר. | **PROPOSED (design P-5)** |
| `booking.error.CUSTOMER_ALREADY_BOOKED` | The bride already holds a live booking at the target instant — on reschedule, or on a phone-correction re-point onto a customer who already holds it (D8's 0009 pre-check). Deliberately distinct from a full slot: the target can have room and still be unmovable-into for *this* bride | ללקוחה כבר יש תור פעיל במועד הזה. | ללקוחה כבר יש תור פעיל במועד הזה. | **PROPOSED (design P-5)** |
| `booking.error.TOO_MANY_ATTEMPTS` | The owner-SMS budget (resend / phone correction / reschedule, 20 per hour per tenant). The realistic cause is a stuck button and an impatient owner, not an attacker — so the wording is a pause, not an accusation. A 429 writes nothing and sends nothing | בוצעו יותר מדי פעולות בזמן קצר. כדאי להמתין מעט ולנסות שוב. | בוצעו יותר מדי פעולות בזמן קצר. כדאי להמתין מעט ולנסות שוב. | **PROPOSED (design P-5)** |

---

## 12. Register check — the mechanical pass

| Rule | Result |
|---|---|
| Exclamation marks in this deck | **0** |
| Strings claiming, implying or hedging an SMS send (any tense) | **0** — `deliveryNotice` states the opposite; `cancelDone` / `rescheduleDone` / `resendDone` / `phoneDone` state state changes only |
| Strings claiming the corrected number was verified | **0** — `phoneModalBody` states it is not |
| Rotation stated in Hebrew for resend | `resendHint` (pre-tap) and `resendDone` (post-tap) |
| Rotation claimed where it is conditional (reschedule) | **not claimed** — `rescheduleConsequence` says the link points at the new time, which is true whether or not the token rotated |
| Money words | **0** — deposits are E4 |
| Placeholders, Lorem, `…`-as-content | **0** — the two `…` glyphs are inside the two loading strings, where they are the content |
| `ar` values that are empty strings | **0** — every row carries the Hebrew as its placeholder |
