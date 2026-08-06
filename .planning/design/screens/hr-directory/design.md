# Screen design — F38 HR directory (`apps/manage`, section «צוות» — extends F51)

**Date**: 2026-08-06 · **Status**: DRAFTED, design gate self-approved (assembled from shipped `packages/ui` components; the photo control is `MediaGallery.tsx`'s pattern reduced to one file — no novel pattern) · **Spec**: `.planning/specs/hr-directory.md` · **Extends**: `.planning/design/screens/manage-staff/` (design + copy) · **Tokens**: `.planning/design/system/tokens.md` — binding

## What this is

Not a new screen. F38 grows F51's `StaffSection.tsx` (the seventh console section, owner-only) with a photo, an eligibility flag, three profile fields, and turns its deactivate action into a real offboarding. It also puts the photo on F36's staff cards in `FloorPanel.tsx` (which F34's `BoardSection` composes). **No parallel surface, no HR tab, no employee detail page.**

## Three readings recorded before anything is drawn

**R1 — the editable fields live in the row's existing edit panel, not on every list row.** The spec's UI note reads "each row: a photo cell … an upload/replace/remove control … a checkbox … inputs". Taken literally that is seven file inputs, seven checkboxes and fourteen date pickers on one 720px screen. F51's shipped shape is: **list row = read-only meta + two buttons; edit panel = every editable field.** F38 follows it. The list row gains a read-only avatar and a muted eligibility word; the photo control, checkbox, phone and start-date land in the edit panel next to `display_name`/`role`/password, which already exists and already has its own state machine, validation slot and save/cancel pair. Bonus a11y consequence: exactly one file input is mounted at a time, so its label needs no `— {{name}}` disambiguator (unlike the row buttons, which do).

**R2 — `last_day` has exactly one render site, and it is the confirm dialog.** Offboarding sets `last_day` and soft-deletes in the same transaction, and this list is live-only (`handleDeactivate` drops the row; the service's `list_live` excludes soft-deleted rows from every surface). So there is no state in which a row both exists on this screen and carries a `last_day`. The spec's "`last_day` shown on offboarded rows" is therefore drawn as: **a date input inside the offboard dialog, defaulted to today**, plus the date echoed in the success line. If an archived-staff list is ever added (F38 OUT, F51 OUT), that list renders `last_day` muted — the field is on the wire either way.

**R3 — one `Modal`, two bodies.** The section already holds one confirm `Modal` driven by `pending: StaffMember | null`. F38 needs a second destructive confirm (photo removal — `MediaGallery.tsx:508` is the precedent that a deleted image gets one). Widen the state to `pending: { kind: "offboard" | "photo"; row: StaffMember } | null` and switch the title/body/confirm inside the one element. A second `<Modal>` would duplicate the focus-restore effect (`StaffSection.tsx:83-93`) that exists because the trigger unmounts under the open dialog.

## Components — all shipped, nothing new, nothing promoted

`Card` · `Input` · `Select` · `Button` · `Badge` · `Modal` · `Skeleton` · **`Checkbox`** · **`DateField`** — all exported from `packages/ui/src/index.ts` today. `Checkbox` already carries a `description` slot and a `min-h-11` label row, so the 44px floor and the `aria-describedby` link come for free.

- **`Checkbox`, not `Toggle`.** `Toggle` is `role="switch"` (on/off — a setting that takes effect). Eligibility is a recorded fact about a person that F38 enforces nowhere (F40 is its only consumer), which is checked/unchecked, not on/off. Same reasoning `Checkbox.tsx`'s own comment records for consent.
- **`DateField`, not a picker.** It is the shared `Input` with `type="date"` — native, keyboard-complete, locale-formatted by the browser, zero bytes.
- **F-W1**: every touch control here is `size="md"` (44px). `sm` is 36px and fails the floor. No `sm` anywhere in this feature.

## Structure — the diff against F51's shape

```
Card
  <ul>  one <li> per live staff row
        default:  [avatar 44px] · <bdi>displayName</bdi> · <bdi dir=ltr>email</bdi>
                  · role Badge · «יכולה לנהל משמרת» (muted, when eligible)
                  · [עריכה] [סיום העסקה]
        editing:  Input(name) · Select(role) · Input(new password) [· Input(current password)]
                  + Input(phone, type=tel, dir=ltr)
                  + DateField(start date)
                  + Checkbox(shift_manager_eligible, description = the meaning line)
                  + photo block:  [preview 88px | initial]  Input(type=file, single)
                                  help = purpose line + formats
                                  role="status" upload line
                                  [הסרת תמונה] (danger, only when a photo exists)
                  [שמירה] [ביטול]
Card  <form> create — unchanged, plus Input(phone) · DateField(start date) · Checkbox(eligible)
Modal  kind="offboard": DateField(last day, default today) + retention note
       kind="photo":    remove-photo confirm
<p role="status">  post-offboard confirmation line
```

The photo block is **its own two API calls**, committed immediately (presign → confirm), *not* batched into `שמירה`: an S3 object cannot participate in a `PATCH` body, and the pending/live column pair exists precisely so the old photo keeps rendering until the new one confirms. `שמירה` still sends only what moved (F51's audit-honesty rule), now over six fields instead of three.

## 1 — Photo

Key discipline, all inherited from `MediaGallery.tsx`: a **real, visible, focusable** `<input type="file">` rendered through `Input` — never `display:none` plus a label shim, which breaks Safari/VoiceOver and hides the disabled reason. `accept="image/jpeg,image/png,image/webp"`, **no `multiple`** (one photo per person). Client bounds mirror the server: 2 MiB, three types.

| State | Treatment |
|---|---|
| empty | 88px square, `bg-surface`, the first grapheme of `display_name` centred `text-ink-muted` + `aria-hidden="true"`; file input labelled `staff.photoUploadLabel` |
| uploading | input `disabled`, `role="status"` line `staff.photoUploading` |
| verifying | same region, `staff.photoVerifying` (the confirm round-trip that reads magic bytes) |
| ready | preview renders; status line `staff.photoAdded` or `staff.photoReplaced`; input relabels to `staff.photoReplaceLabel`; `[הסרת תמונה]` appears |
| failed | `<p role="alert" class="text-sm text-danger">` with the mapped sentence + `[נסי שוב]` (`secondary`, md). **The previous photo is still shown** — a failed replace never blanks the cell |
| storage unavailable (503) | same alert, `staff.error.MEDIA_STORAGE_UNAVAILABLE`; existing photos keep rendering (the `sign_media` degrade-to-null posture is read-side and unaffected) |
| removing | confirm Modal (R3) → on success the cell returns to the initial fallback, `role="status"` `staff.photoRemoved` |

**Replace is the same control**, not a separate flow: picking a file when a photo exists runs presign → confirm and the server swaps live ← pending. No crop, no rotate, no thumbnail (spec OUT).

**The PPL purpose line is in the `help` slot**, which `Input` links with `aria-describedby` — so it is announced *at capture*, before a file is chosen, to keyboard and screen-reader users alike, not parked in a footnote. `help={`${t("staff.photoPurpose")} ${t("staff.photoFormats")}`}` — concatenated deliberately so the purpose sentence stays one greppable, quotable key. It is an operational label, not legal text: F38 authors no privacy wording, and F20's platform notice already ships in its own «פרטיות» section. No link is drawn to it (a link is new copy and new IA; the spec asks for neither).

**Build note — `MAPPED_CODES`.** `StaffSection.tsx:18-23` is a hand-maintained `Set` that nothing pins; a code missing from it renders the server's English. F38 adds five entries (§copy 6). Adding a photo error code later without touching that Set is an English string on a green build.

## 2 — `shift_manager_eligible`

One `Checkbox` in the edit panel and in the create form. Label `staff.eligibleLabel`; the one-line meaning goes in `description`, which sits outside the `<label>` so it describes without joining the accessible name.

The meaning line has one job: say that this is **not** a role and **not** a permission. It is who may be put in charge of a shift when the roster is built. A `seamstress` may be eligible; a staffer whose `role` is already `shift_manager` may be un-eligible — F38 stores the boolean and enforces nothing (O4; F40 decides).

On the list row it renders as **muted words, not a second Badge**: the row already carries the role Badge, and F36's ruling is one pill per row so the pill means one thing.

## 3 — Phone, start date

- **`phone`** — `Input type="tel" dir="ltr"`, optional, `help` states plainly that it is a contact number and that sign-in is email + password (C1: it is not a login identifier and never will be). Rendered in `<bdi dir="ltr">` when read back.
- **`start_date`** — `DateField`, optional. No help text; the label is the whole meaning.
- Both are ordinary `PATCH` fields under F51's send-only-what-moved rule, so each earns its own audit row.

## 4 — Offboarding

The existing row action, promoted in name and in body. Trigger keeps `variant="danger"` on the row **and** on the modal confirm — `StaffSection.tsx:342-352` and `DressEditor.tsx:401` are the house destructive pattern, and this list is single-digit rows, so the table-density exception the platform console took does not apply here.

**Confirm dialog** (`kind: "offboard"`):
1. Title `staff.deactivateTitle` — «לסיים את ההעסקה?»
2. `<Trans>` body naming her inside a bare `<bdi>` (a Latin display name — every founding owner is seeded with `display_name = owner_email` — reorders inside a Hebrew sentence without an isolate). States the two immediate facts: access stops on her next action, and the photo is deleted now.
3. `DateField` for `last_day`, **defaulted to today** (Jerusalem). A blank would silently exempt her from the retention clock. Client bounds mirror the server (`>= start_date`, `<= today + 1 year`), message hardcoded in `validation.ts` per F51's deck rule.
4. `staff.offboardRetentionNote` — the retention paragraph, plain and unhedged: operational records are kept as they are, personal details are erased at the end of the retention period, and she can be added again later **as a new staff member** (re-hire continuity is OUT — a returning staffer is a new row).
5. Footer: `[ביטול]` (ghost) + `[סיום העסקה]` (danger).

**After.** The row leaves the list (F51 patches locally rather than refetching) and a `role="status"` line confirms the act with her name and the last day. Nothing else changes: there is **no** archived list, no restore control, no "offboarded" section — the soft-deleted row is invisible on every surface by construction (`list_live`). The status line is the only feedback there is, which is exactly why it exists; F51 showed nothing here, and F51's act had no retention consequence worth stating.

Guard refusals (`LAST_OWNER_REQUIRED`, `STAFF_SELF_MANAGE`, `NOT_AUTHORIZED`) keep their shipped Hebrew and their existing `role="alert"` slot under the list. No self-offboard control is drawn — the server refuses it and a door that always refuses is worse than no door.

## 5 — Staff cards (`FloorPanel.tsx`, rendered by F34's board and F36's floor)

A 44px `rounded-full` avatar at the **inline start** of the card's flex row (`me-3`, logical properties, `shrink-0`), before the name.

| State | Treatment |
|---|---|
| `photo_url` present | `<img>` `object-cover`, `loading="lazy"`, `decoding="async"`, **`alt=""`** |
| `photo_url === null` (no photo, or storage degraded to null) | the first grapheme of `display_name`, `aria-hidden="true"`, on `bg-surface` |
| `<img>` `onError` (a signed URL that expired between ticks) | fall back to the initial for that id **and drop its pin**, so the next ~5s poll adopts the fresh URL. No refetch call — the poll *is* the recovery here, unlike `MediaGallery`'s one-shot `hasRefreshed` |

**Alt contract: `alt=""`, deliberately.** The display name is a text node immediately beside the image; `alt="תמונה של {{name}}"` would announce the name twice per card on a board that lists the whole shift. The photo adds nothing a screen-reader user can use — it is the definition of decorative. The initial fallback is `aria-hidden` for the same reason. Nothing in the card's accessible name changes.

**URL pinning** (spec, and it is load-bearing): the card keeps the URL it already rendered, keyed by `(id, photo_confirmed_at)`. Without it, every ~5s poll returns a freshly signed — therefore different — `src`, and the browser re-downloads every face on the board forever. The `onError` path above is the one thing allowed to break a pin.

## Responsive — 375 / 768 / 1440

`ConsoleShell` caps content at 720px, which is why this list is rows and not a table. Rows stay `flex flex-wrap`: at 375px the meta and the two buttons wrap under the name while the avatar holds its 44px and does not shrink. The edit panel's fields are already a wrapping row; the photo block stacks preview-over-input below `sm`. The 88px edit preview and the file input never force a horizontal scroll — the page does not scroll sideways at any of the three widths. `Card`'s baked-in `p-6` is not overridden.

## Accessibility — IS 5568 / WCAG 2.0 AA is a **legal** requirement (pre-decided #38)

- **Upload keyboard path**: Tab reaches the real `<input type="file">` (visible, never `display:none`); Space/Enter opens the OS picker; on return, focus is still on the input and the `role="status"` region announces `מעלה…` → `מאמת…` → `התמונה נוספה.` — the same region for running and terminal states, so a failure is never left silent after a progress message. `[נסי שוב]` and `[הסרת תמונה]` are ordinary buttons in the same panel.
- **Image alt contract**: `alt=""` on every staff photo (board card and edit preview) — the name is always adjacent; initial fallbacks are `aria-hidden="true"`.
- Photo removal is a two-step `Modal` confirm with focus trap and focus restore to its trigger (the trigger survives here, but the `DressEditor.tsx:130-136` effect is kept for the failure-path close). `Esc` and `[ביטול]` close without acting.
- Every new control has a real visible `<label>`: `Input(phone)`, `DateField(start date)`, `DateField(last day)`, `Checkbox` (its own `<label>` wraps box + text at `min-h-11`), file input.
- 44px minimum on everything — `Button` `md` only (F-W1), `Checkbox`'s `min-h-11` label row, the avatar is display-only and exempt.
- Contrast from `tokens.md`: the initial fallback is `text-ink-muted` on `bg-surface`, which passes AA at `text-base`. **Nothing in this feature is signalled by colour alone** — eligibility is a word, offboarding is a word.
- Bidi: bare `<bdi>` around display names (`dir="ltr"` on a Hebrew name is itself a defect), `<bdi dir="ltr">` around email and phone.
- Heading order unchanged: shell `h1` (sr-only) → `staff.heading` `h2` → create form `h3`. The photo block is not a heading.
- axe **zero violations** in `e2e/a11y.spec.ts` across: list with and without photos, edit panel mid-upload, both modals, RTL.

## Copy deck — `he.ts` + `ar.ts`, added together, `ar` = the approved Hebrew standing in untranslated (Q3 / #47), never `""` · **zero exclamation marks** (#5, enforced by `__tests__/i18n.test.ts`) · no form of «נשלח» in any tense

Client-side validation messages are **not** in this deck — `validation.ts` returns hardcoded Hebrew (F51's rule, `validateUploadFile`'s precedent): «סוג הקובץ אינו נתמך — JPG, PNG או WebP בלבד» · «הקובץ גדול מ-2MB» · «HEIC אינו נתמך. שמרי כ-JPG» · «יום העבודה האחרון אינו יכול להקדים את תאריך תחילת העבודה.»

### 1. Photo

| Key | Notes (EN) | Approved Hebrew (`he` = `ar`) |
|---|---|---|
| `staff.photoUploadLabel` | file input label, no photo yet | תמונת פרופיל |
| `staff.photoReplaceLabel` | same control once a photo exists | החלפת תמונת פרופיל |
| `staff.photoPurpose` | **the PPL Amendment 13 purpose line, verbatim from the spec.** Its own key so it stays greppable and quotable; announced at capture via the `help` slot | התמונה משמשת לזיהוי בלוח המשמרת ובכרטיסי הצוות בלבד. |
| `staff.photoFormats` | concatenated after the purpose line in the same `help` slot | JPG, PNG או WebP · עד 2MB |
| `staff.photoUploading` | `role="status"`, mirrors `MediaGallery`'s word | מעלה… |
| `staff.photoVerifying` | the magic-byte confirm round-trip | מאמת… |
| `staff.photoAdded` | terminal, first upload | התמונה נוספה. |
| `staff.photoReplaced` | terminal, replace | התמונה הוחלפה. |
| `staff.photoRemoved` | terminal, delete | התמונה הוסרה. |
| `staff.photoRetryCta` | `secondary`, md | נסי שוב |
| `staff.photoRemoveCta` | `danger`, md, only when a photo exists | הסרת תמונה |
| `staff.photoRemoveTitle` | Modal title (`kind="photo"`) | להסיר את התמונה? |
| `staff.photoRemoveBody` | states the irreversibility and the way back | התמונה תימחק מהאחסון ולא ניתן לשחזר אותה. אפשר להעלות תמונה חדשה בכל עת. |
| `staff.photoRemoveConfirm` | the `danger` footer button | הסרה |

### 2. Eligibility, phone, start date

| Key | Notes (EN) | Approved Hebrew |
|---|---|---|
| `staff.eligibleLabel` | `Checkbox` label; reused as the muted marker on the list row | יכולה לנהל משמרת |
| `staff.eligibleHelp` | `description` slot — the one-line meaning: a roster fact, not a role and not a permission | הסימון קובע מי יכולה להיות אחראית על משמרת בסידור העבודה. הוא אינו משנה את התפקיד ואינו משנה הרשאות. |
| `staff.phoneLabel` | label | טלפון |
| `staff.phoneHelp` | C1 stated plainly — contact only, sign-in is unchanged | מספר ליצירת קשר בלבד. הכניסה למערכת היא באמצעות אימייל וסיסמה. |
| `staff.startDateLabel` | label | תאריך תחילת עבודה |
| `staff.lastDayLabel` | label, inside the offboard dialog | יום עבודה אחרון |
| `staff.lastDayHelp` | why it is pre-filled | ברירת המחדל היא היום. אפשר לבחור תאריך אחר. |

### 3. Offboarding — four F51 keys change **value** (names unchanged; `StaffSection.test.tsx` asserts on these strings)

| Key | Was (F51) | New value — «השבתה» understated an act that now sets a last working day and deletes her photo |
|---|---|---|
| `staff.deactivateCta` | השבתה | סיום העסקה |
| `staff.deactivateAria` | השבתה — {{name}} | סיום העסקה — {{name}} |
| `staff.deactivateTitle` | להשבית את הגישה? | לסיים את ההעסקה? |
| `staff.deactivateConfirm` | השבתה | סיום העסקה |
| `staff.deactivateBody` | «…אפשר להוסיף אותה מחדש בכל עת.» | הגישה של \<bdi\>{{name}}\</bdi\> לניהול הבוטיק תיפסק בפעולה הבאה שלה, והתמונה שלה תימחק מיד. |

| New key | Notes (EN) | Approved Hebrew |
|---|---|---|
| `staff.offboardRetentionNote` | the retention paragraph — what is kept, what is erased and when, and that a return is a new record. No hedging, no legal claim | רישומי העבודה שלה — שיבוצים לחדרים, קריאות ותיקונים — נשמרים כפי שהם. הפרטים האישיים שלה יימחקו מהמערכת בתום תקופת השמירה. אפשר להוסיף אותה מחדש בעתיד כאשת צוות חדשה. |
| `staff.offboardDone` | `role="status"` after the row leaves the list; `<Trans>` for the `<bdi>` | ההעסקה של \<bdi\>{{name}}\</bdi\> הסתיימה בתאריך {{date}}. רישומי העבודה שלה נשמרו. |

### 4. Error codes → Hebrew (add all five to `MAPPED_CODES`)

| Key | Server code | Approved Hebrew |
|---|---|---|
| `staff.error.MEDIA_MISMATCH` | 400 — magic bytes disagree with the declared type | הקובץ אינו תמונה תקינה. |
| `staff.error.MEDIA_NOT_UPLOADED` | 400 — confirm found no object | הקובץ לא הגיע לשרת. נסי שוב. |
| `staff.error.MEDIA_STORAGE_UNAVAILABLE` | 503 — writes refused, reads degrade to null | אחסון התמונות אינו זמין כרגע. התמונות הקיימות מוצגות כרגיל. |
| `staff.error.MEDIA_NOT_CONFIGURED` | 503 — no bucket configured; same sentence, the owner cannot tell the two apart and does not need to | אחסון התמונות אינו זמין כרגע. התמונות הקיימות מוצגות כרגיל. |
| `staff.error.TOO_MANY_ATTEMPTS` | 429 — the dedicated staff presign limiter | יותר מדי העלאות בזמן קצר. נסי שוב בעוד כמה דקות. |

## What this surface deliberately does not have

No archived-staff list or restore control (R2, F51 OUT) · no crop, rotate, thumbnail or second photo · no drag-and-drop upload (a file input is the keyboard-complete path, and the batch queue exists in `MediaGallery` only because a dress takes ten) · no staff self-service photo or profile editing (O3 — owner-only; F39 owns the first non-owner screen) · no eligibility enforcement anywhere (O4 — F40) · no retention countdown, expiry date or scrub preview (the clock is an app `Settings` value, ships disarmed, and is counsel's question at F21) · no contracts, pay, hours or leave (spec OUT) · no new `packages/ui` component and no promotion.

---

Design Gate: accepted by design-critic, 2026-08-06
