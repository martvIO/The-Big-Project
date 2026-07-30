# Copy deck — F51 Staff management (`apps/manage`, section «צוות»)

**Date**: 2026-07-30 · **Status**: DRAFTED under the approved register, self-approved with the design gate (Interview **Q2** — assembled from shipped `packages/ui` components, no novel pattern) · **Owner of the Hebrew: the user** · **Consumes**: `.planning/specs/staff-management.md` (D1–D9) · **Lands in**: `Frontend/apps/manage/src/i18n/he.ts` (`nav.staff` + a new `staff.*` namespace) and `Frontend/apps/manage/src/i18n/ar.ts`

**F51 adds no SMS template and no email.** There is no §SMS section in this deck, and that is the point of §0 rule 2 — the initial credential travels by the owner's own voice (spec D2), so nothing here may hint at a message.

## 0. The rules this deck is written under — hard constraints, not preferences

1. **Zero exclamation marks** (pre-decided #5). Mechanically enforced in `__tests__/i18n.test.ts`.
2. **Never claim, imply or hedge that anything was sent, in any tense.** For F15 this discharged a swallowed-error risk; here it is literally true — **there is no channel at all**. `Backend/app/notifications/` is SMS-only with no registered sender ID, no mailer exists anywhere in `Backend/app`, and SMC ruling 1 removed SMS from the staff auth path. The password notice therefore states the fact positively and stops. The same `i18n.test.ts` guard that reads F15's keys reads these: no «נשלח», no «תישלח», no «בדרך» — which is why §4's notice is phrased «יש למסור…» and not «הסיסמה אינה נשלחת…».
3. **The word inside the role Badge carries the role; colour never carries it alone.** `owner → success`, `shift_manager → neutral`, and both are read as words.
4. **Plain-fact wording for the two refusals.** The last-owner guard and the self-guard each get one sentence that states the *rule*, not the error, and neither names a count (spec D7).
5. **Every value is a real string.** No `…`-as-placeholder, nothing to be filled in later.
6. **The `ar` column is the approved Hebrew, standing in untranslated** (Interview Q3 / pre-decided #47), **never an empty string** — i18next's `returnEmptyString` default renders `""` rather than falling back.

**29 rows.** F51 invents every one of them and reuses no existing key.

Client-side validation messages are **not** in this deck: `validation.ts` returns hardcoded Hebrew, the shipped `validateAppointmentType` / `validateDress` precedent. Nor is the non-owner terms-blocker sentence (plan C4) — that is hardcoded Hebrew inside `TermsSection.tsx`, per F15's D16.

---

## 1. Navigation and section chrome

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `nav.staff` | The seventh console nav item, **rendered for an owner only** (spec D9). «צוות» over «משתמשים» — a boutique has staff, not users | צוות | צוות | DRAFTED |
| `staff.heading` | The section `h2` under `ConsoleShell`'s `sr-only` `h1` | צוות | צוות | DRAFTED |

## 2. The list

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `staff.loadFailed` | The list failed to load — the **outage** register: recoverable, unblaming, no technical words, no retry control (reopening the section refetches) | לא הצלחנו לטעון את רשימת הצוות כרגע. | לא הצלחנו לטעון את רשימת הצוות כרגע. | DRAFTED |
| `staff.roleOwner` | The `owner` Badge word. Not «מנהלת» — the boutique has exactly one kind of owner and the console is hers | בעלת הבוטיק | בעלת הבוטיק | DRAFTED |
| `staff.roleShiftManager` | The `shift_manager` Badge word, matching the SMC epic's persona name | אחראית משמרת | אחראית משמרת | DRAFTED |
| `staff.selfMarker` | Muted marker on the acting owner's own row. There is no empty state for this list — she is always in it | זו את | זו את | DRAFTED |
| `staff.editCta` | Opens the row's inline edit | עריכה | עריכה | DRAFTED |
| `staff.deactivateCta` | Opens the confirm Modal. «השבתה», never «מחיקה» — the row is soft-deleted and the audit history survives | השבתה | השבתה | DRAFTED |

## 3. The inline edit

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `staff.displayNameLabel` | Visible `<label>` — a placeholder is never the label | שם לתצוגה | שם לתצוגה | DRAFTED |
| `staff.emailLabel` | Visible label on the create form; the row renders the address read-only inside `<bdi dir="ltr">`. **Not editable after creation** (spec D5) | אימייל | אימייל | DRAFTED |
| `staff.roleLabel` | Label on the native `<select>` | תפקיד | תפקיד | DRAFTED |
| `staff.newPasswordLabel` | The optional reset field on an existing row | סיסמה חדשה | סיסמה חדשה | DRAFTED |
| `staff.newPasswordHelp` | Why it may be left blank — the `Input` `help` slot, so it is `aria-describedby`-linked | אפשר להשאיר ריק כדי לא לשנות את הסיסמה. | אפשר להשאיר ריק כדי לא לשנות את הסיסמה. | DRAFTED |
| `staff.currentPasswordLabel` | Shown **only** on the acting owner's own row when she types a new password (spec D4) | הסיסמה הנוכחית שלך | הסיסמה הנוכחית שלך | DRAFTED |
| `staff.currentPasswordHelp` | Why the field exists at all | נדרשת כדי לשנות את הסיסמה של עצמך. | נדרשת כדי לשנות את הסיסמה של עצמך. | DRAFTED |
| `staff.currentPasswordWrong` | **Plan C6.** The server answers this 400 with an English `VALIDATION_ERROR` message; the console renders this in the field's own `error` slot instead of through the code map. Honest only because every other 400 this form can produce is caught client-side by a mirrored bound | הסיסמה הנוכחית שגויה. יש להזין את הסיסמה הנוכחית כדי לשנות אותה. | הסיסמה הנוכחית שגויה. יש להזין את הסיסמה הנוכחית כדי לשנות אותה. | DRAFTED |
| `staff.saveCta` | Commits the inline edit | שמירה | שמירה | DRAFTED |
| `staff.cancelCta` | Abandons it | ביטול | ביטול | DRAFTED |

## 4. The create form

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `staff.createHeading` | The form's `h3` | הוספת אשת צוות | הוספת אשת צוות | DRAFTED |
| `staff.passwordLabel` | The initial credential the owner chooses | סיסמה | סיסמה | DRAFTED |
| `staff.passwordNotice` | **The D2 line.** States plainly that delivery is hers to do, and — per §0 rule 2 — contains no form of «נשלח», because nothing is sent and no channel exists to send it on | יש למסור את הסיסמה לעובדת בעצמך. המערכת אינה מעבירה אותה לאיש. | יש למסור את הסיסמה לעובדת בעצמך. המערכת אינה מעבירה אותה לאיש. | DRAFTED |
| `staff.createCta` | Submits | הוספה לצוות | הוספה לצוות | DRAFTED |

## 5. The deactivate confirm

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `staff.deactivateTitle` | The Modal title | להשבית את הגישה? | להשבית את הגישה? | DRAFTED |
| `staff.deactivateBody` | States the two facts that make this safe to tap: it bites immediately (no sweep — spec Goal), and it is undoable by re-creating the account. The `<bdi>` is **in the string** and rendered through `<Trans components={{ bdi: <bdi /> }}>` — the only key in this deck carrying markup, because the name is a Latin run inside an RTL sentence and reorders without an isolate | הגישה של \<bdi\>{{name}}\</bdi\> לניהול הבוטיק תיפסק בפעולה הבאה שלה. אפשר להוסיף אותה מחדש בכל עת. | הגישה של \<bdi\>{{name}}\</bdi\> לניהול הבוטיק תיפסק בפעולה הבאה שלה. אפשר להוסיף אותה מחדש בכל עת. | DRAFTED |
| `staff.deactivateConfirm` | The `danger` button in the Modal's `footer` | השבתה | השבתה | DRAFTED |

## 6. Error codes → Hebrew

Keyed on `ApiError.code`, pinned by `SPEC_ERROR_CODES` in `test_staff_api.py` so the map cannot silently drift. Every code not listed falls through to `errorMessage(error)`.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `staff.error.DUPLICATE_EMAIL` | 409 on create. Says «פעילה» because a soft-deleted row frees its address again (spec D5) | כתובת האימייל הזו כבר משויכת לאשת צוות פעילה. | כתובת האימייל הזו כבר משויכת לאשת צוות פעילה. | DRAFTED |
| `staff.error.LAST_OWNER_REQUIRED` | 409. States the **rule**, names no count — a count is not the owner's problem to solve (spec D7) | לבוטיק חייבת להיות בעלת בוטיק אחת לפחות. | לבוטיק חייבת להיות בעלת בוטיק אחת לפחות. | DRAFTED |
| `staff.error.STAFF_SELF_MANAGE` | 409. Names both halves of the guard, and implicitly what is still allowed | אי אפשר לשנות את התפקיד של עצמך או להשבית את עצמך. | אי אפשר לשנות את התפקיד של עצמך או להשבית את עצמך. | DRAFTED |
| `staff.error.NOT_AUTHORIZED` | 403 on a mid-session demotion. Mapped here because the server's generic body is **English** (`main.py:105-108`) and `errorMessage()` surfaces it verbatim; the wider leak across the other five sections is spec Risk 4 | הפעולה הזו זמינה לבעלת הבוטיק בלבד. | הפעולה הזו זמינה לבעלת הבוטיק בלבד. | DRAFTED |
