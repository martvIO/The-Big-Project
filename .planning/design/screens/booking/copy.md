# Copy deck — F14 Storefront Booking UI (`/book/*`)

**Date**: 2026-07-29 · **Status**: **rev 5 — SIGNED OFF; every row APPROVED** (rev 5 = the R19 bidi shapes, applied for real) · **Owner of the Hebrew: the user** · **Consumes**: `.planning/specs/storefront-booking-ui.md` §Design i18n inventory (verbatim key list) · **Lands in**: `Frontend/apps/storefront/src/i18n/he.ts`

**What rev 5 changed** (review round 2, 2026-07-29): **R19 was ruled in rev 2 and then applied to two rows out of seven.** `confirmWhen`/`confirmWhat` became bare labels as designed; `typeDuration`, `forDress`, `refundWindow`, `forfeit`, `confirmDress` and — worst — `confirmTitleNamed` all shipped as interpolated strings carrying a value i18next cannot isolate. Rev 5 gives each of the six its split shape. **No Hebrew word changed in any of them**: the seam moved, the words did not. Two rows are added, and only because their values sit *mid-sentence* where a lead alone cannot carry the words after it — `refundWindowSuffix` and `forfeitSuffix`, each holding the second half of a sentence that was already approved. `typeDuration` was the awkward one: its approved Hebrew is value-first (`‏{{minutes}} דקות`) and carried an **RLM** as an ad-hoc substitute for the isolation, so it becomes a lead-less unit rendered *after* the isolated numeral, and the RLM goes with the defect it was patching.

**What rev 3 changed** (gate sign-off session, 2026-07-29): the user approved P1–P8, all seven proposed additions, and the FINDING 4 ruling; answered §7's six questions (answers recorded in place); and walked every ⚠ row. Four Hebrew cells changed: `booking.audienceBrides` (→ פגישת כלה), `booking.noTypes` (dropped its phone clause per FINDING 4), `booking.otpSent` (softened conditional), `booking.confirmCold` (honest short form). Two keys were added at the user's request beyond §4's seven: `booking.confirmTitleNamed` (named confirmation title, closes §7 Q4 as "yes") and `booking.sizeUnavailableNote` (the longer invitation under the size-chip group). Q5 was closed by code research — `forfeit_percent` is a percentage **of the deposit** (F7 spec `owner-settings.md:23`, model comment `terms_version.py:23`, shipped manage summary `TermsSection.tsx:99-100`); FINDING 2's premise was false. Q3 was closed the same way — the backend's single normalizer `normalize_israeli_mobile` (`Backend/app/notifications/validation.py:31-48`) serves all three phone-carrying calls and keys the OTP token on the normalized `+9725XXXXXXXX`, so formatting can never cause `PHONE_NOT_VERIFIED`; the draft's teach-(a)/accept-(c) assumption is exactly what is implemented.

**What rev 2 changed** (round 1 of adversarial review — full log in `booking.md` §14.2): two keys the design renders were **missing entirely** and would have been failing tests on day one (`booking.sizeRequired`, `errors.otpSendBudget`); `booking.otpSent` was drafted as a delivery claim the endpoint cannot support; `errors.phoneNotVerified` promised an automatic resend the design does not perform; `booking.otpResend` said "send a new code" on the button that sends the *first* one; `booking.sizeUnavailable` was a 100-character sentence where the design needs a ≤24-character phrase **inside the chip's own label**; and `confirmWhen`/`confirmWhat` were interpolated sentences where i18next cannot deliver the bidi isolation the values need, so they became bare labels. Additions are now **seven**, not two.

---

> ## ✅ SIGNED OFF — 2026-07-29
>
> **Every row in this deck was approved by the product owner on 2026-07-29** — P1–P8 confirmed, nine key additions accepted, §7's six questions answered, and every ⚠ row walked one by one. The design gate on `.planning/design/screens/booking/` is no longer blocked by this file. The build copies the approved column into `Frontend/apps/storefront/src/i18n/he.ts`. Any later wording change is a normal copy edit (layout-safe per §6), not a gate re-open.

---

## 1. How to use this file

1. **Read the `What it must say` column first.** It is the English intent — what the string has to accomplish for the bride at that moment. Judge the Hebrew against the intent, not against the spec; you should never need to reopen the spec to review a row.
2. **Rewrite the `DRAFT Hebrew` cell in place.** Do not add rows, do not rename keys — the key list is fixed by the spec's §Design i18n inventory and any drift breaks the design/test/build contract. Two additions to that list are proposed below and are marked as such (§4).
3. **Change the row's `Status` to `APPROVED`.** A row still reading `DRAFT` at gate time is an unsigned row and blocks the gate.
4. **The build copies the approved column into `Frontend/apps/storefront/src/i18n/he.ts`** — no component may hardcode Hebrew (`he.ts` header comment, lines 1–3).
5. **A missed row fails a test, it does not ship blank.** `Frontend/apps/storefront/src/__tests__/i18n-keys.test.ts` statically scans every source file under `src/` for `"section.key"` string literals and asserts each one resolves to a non-empty string in `he.translation`. A component referencing `booking.otpResendWait` with no such key is a red test, not an empty `<span>`.

### Rows marked ⚠

`⚠` in the Status column means **the builder is not confident of the Israeli-Hebrew idiom, the register, or a factual detail inside the string.** Read those first. Every `⚠` is also restated as a numbered question in §7 where the uncertainty is a judgement call rather than a wording preference.

---

## 2. Rules the rewrite must not break

These are contract, not taste. A rewrite that violates one of them fails a test or a review grep.

| # | Rule | Why |
|---|---|---|
| 1 | **No string may promise an SMS confirmation, a reminder, or any message after the booking is written.** | **D6.** F16 has not shipped; a booking created here sends nothing. The confirmation screen is the bride's only record. This bites `booking.confirmTitle`, `booking.confirmKeepScreen`, `booking.confirmWhen`, `booking.confirmWhat`, `booking.confirmCold`. |
| 2 | **The one-time verification code IS an SMS and may be named as one.** | Rule 1 is about the *confirmation*, not the OTP. F11 shipped OTP send. `booking.otpSent` may say a code was sent to the phone. It must **not** claim the code definitely arrived — `POST /storefront/otp/send` always answers `204` and deliberately reveals nothing. |
| 3 | **Interpolation is i18next `{{var}}`.** Variable names are fixed by this file and named in the English-intent column. | Renaming `{{minutes}}` to `{{duration}}` in the Hebrew without telling the builder produces a literal `{{minutes}}` on screen. |
| 4 | **An interpolated string may never reduce to placeholders alone.** `"{{time}}"` passes the i18n test; `"{{date}} {{time}}"` with no Hebrew word between them **fails** it. | `i18n-keys.test.ts` strips `{{…}}` and asserts Hebrew characters remain. |
| 5 | **Do not put digits, phone numbers, times or Latin text inside the Hebrew where you can avoid it — pass them as `{{vars}}`.** | Numeric and Latin runs are wrapped in `<bdi dir="ltr">` by the component. A number typed straight into the Hebrew string cannot be wrapped and will render in the wrong visual order beside Hebrew. The one deliberate exception is `booking.phoneHint`'s example number — flagged ⚠ for exactly this reason. |
| 6 | **No `₪` glyph in any string.** | `Frontend/scripts/qa-greps.sh:37` fails the build on the glyph inside `apps/storefront/src`. Money renders only through the `Price` component. No string in this deck carries money today; keep it that way. |
| 7 | **No promo, urgency or scarcity register anywhere** — no "מהרי", no "נותרו רק", no exclamation marks, no countdown framing. | `tokens.md` usage law 9. This bites the OTP resend cooldown (`booking.otpResendWait`): it is a functional cooldown, not urgency marketing, and its copy must read as calmly as a footnote. |
| 8 | **Error copy states what happened, then what to do next, in that order.** Never a generic apology for a case we can name. | Spec Risk 5: *"Missing one is not a crash: it is a bride told «משהו השתבש» when the real answer was «the slot was just taken»."* |
| 9 | **`booking.depositByPhone` and `booking.noTermsByPhone` must not read as errors or as an apology for a broken site.** | **D3** and **D5**. Phoning the boutique is a legitimate, designed path — the market's *normal* path. These two sentences sit above a `ContactPanel`. |
| 10 | **Six error keys cover seven backend codes.** `SMS_NOT_CONFIGURED` and `SMS_UNAVAILABLE` share `errors.smsUnavailable`. | Spec §Design, verbatim: *"the difference between them is the boutique's problem and not the bride's."* Write one sentence that is true of both — the bride must not be able to tell which one fired. |

---

## 3. The strings, in flow order

Grouped by the screen the bride sees them on. Within a group, in reading order down the screen.

### 3.1 Route level

| Key | Where it appears | What it must say (English intent) | DRAFT Hebrew | Status |
|---|---|---|---|---|
| `document.book` | Browser tab / `<title>`, **for all five steps** — one title for the whole flow, the router rewrites it on every step transition (spec §Design) | The page's name in a tab strip. Short. Same word the CTA uses. | קביעת תור | APPROVED |
| `booking.stepsLabel` | Accessible name of the step indicator (`aria-label` on the stepper) | Names the progress indicator for a screen-reader user. Not visible. | שלבי קביעת התור | APPROVED |
| `booking.stepSlot` | Step indicator, position 1; also the in-flow back link's destination name | Step 1's name: choosing what and when. | מועד | APPROVED |
| `booking.stepDetails` | Step indicator, position 2 | Step 2's name: her name and phone. | פרטים | APPROVED |
| `booking.stepTerms` | Step indicator, position 3 | Step 3's name: the cancellation policy. | מדיניות ביטולים | APPROVED |
| `booking.stepOtp` | Step indicator, position 4. (URL slug is `verify`; the label is named after what the step *asks for* — spec **D8**, "deliberate, not a typo") | Step 4's name: proving the phone number. | אימות טלפון | APPROVED |
| `booking.continue` | **ADDITION (R4 / P6).** The forward button on steps 1–3 — the slot, details and terms steps. **Not** step 4, which commits the booking and uses `booking.submit` | Advance one step. Neutral and quiet: nothing is committed yet, and it must not promise a booking three screens early. | המשך | APPROVED |
| `booking.backStep` | The in-flow back control on steps 2–4 (a `<Link>` to the previous step, never `history.back()`) | Go back one step. Must not say "cancel" — nothing is lost. | חזרה לשלב הקודם | APPROVED |
| `booking.backToCatalog` | The way out from the confirmation screen, and from the two phone-only degraded entries | Leave the flow, return to the dresses. | חזרה לקולקציה | APPROVED |

> ⚠ on `booking.backToCatalog`: `he.ts:50` already ships `dress.backToCatalog` = "חזרה לקולקציה", and `dress.back` = the same words. The spec's inventory names a **third** key with the same job. Keeping it is correct (the booking flow must not import the dress namespace), but the two strings should stay **identical** unless you want them to differ.

### 3.2 Step 1 — `slot`: what and when

The appointment type is picked at the **top** of this step (**D11**), the date and time below it.

| Key | Where it appears | What it must say (English intent) | DRAFT Hebrew | Status |
|---|---|---|---|---|
| `booking.typeHeading` | Heading above the appointment-type picker | Labels the "what kind of appointment" choice. | סוג הפגישה | APPROVED |
| `booking.typeDuration` | Under each appointment type's name. **R19 SPLIT — the key is the lead-less UNIT and the component renders `<bdi dir="ltr">{duration_minutes}</bdi>` *before* it**, because the approved Hebrew is value-first and a value-first sentence has no lead to hold. The RLM the interpolated draft carried was an ad-hoc stand-in for exactly this isolation and is dropped with it | How long that appointment takes. Reads as a fact, not a constraint. | דקות | APPROVED (shape rev 5 — R19; wording unchanged) |
| `booking.audienceBrides` | A `Badge` on an appointment type whose `audience` is brides-only (**D10** — it labels, it does not gate; the type stays selectable) | This service is for brides. Not a warning, not a lock. | פגישת כלה | APPROVED |
| `booking.noTypes` | Replaces the whole picker when `GET /appointment-types` returns an empty list — over a `ContactPanel` | No appointment types are published for online booking yet. Offer the phone warmly. | בשלב זה אין כאן סוגי פגישות לקביעה מקוונת. | APPROVED |
| `booking.pickDate` | Visible label on the native `<input type="date">` | Which day. | תאריך | APPROVED |
| `booking.pickTime` | **ADDITION (F-A6).** The visible `<legend>` of the slot grid's `<fieldset>` | Which time. A radio group's accessible name is its legend, and usage law 3 requires it to be visible — the inventory has `pickDate` but no counterpart for the grid. | שעה | APPROVED |
| `booking.forDress` | **ADDITION.** A non-interactive label above the name field on the item-based path only. **R19 SPLIT — the key is the lead and the component renders `<bdi>{dress name}</bdi>` after it.** A **bare** `<bdi>` (i.e. `dir="auto"`), not `dir="ltr"`: the dress name is owner text and is usually Hebrew, and forcing LTR on it is itself a bidi defect | Reassures her the flow remembered which dress she came from. Reads as a label, not as an editable choice — there is no unbind control. | עבור | APPROVED (shape rev 5 — R19; wording unchanged) |
| `booking.typeRequired` | **ADDITION (build-time, approved 2026-07-29).** The validation error under the appointment-type `<fieldset>` when she presses forward without choosing one. R7 removed the disabled forward button, so "nothing chosen" needs prose — the same gap R21 found for `sizeRequired`, on the identical template | She has to pick an appointment type. A prompt, not a scolding. | צריך לבחור סוג פגישה כדי להמשיך | APPROVED |
| `booking.timeRequired` | **ADDITION (build-time, approved 2026-07-29).** The validation error under the slot grid's `<fieldset>` when she presses forward without choosing a time | She has to pick a time. Same template as `typeRequired` and `sizeRequired`. | צריך לבחור מועד כדי להמשיך | APPROVED |
| `booking.loading` | **ADDITION (build-time, approved 2026-07-29).** The `VisuallyHidden role="status"` announcement while the step's reads are in flight (R30 — `aria-busy` on a plain div is announced by neither VoiceOver nor NVDA). Screen-reader-only; costs no layout | What is loading, said accurately. `catalog.loading` ("טוענת את הקולקציה") was reused at first and is factually wrong here — this flow loads times, not a collection. | טוענות את המועדים | APPROVED |
| `booking.noSlots` | Under the date field when `GET /slots` returns an empty list — the state every new tenant ships in | There is nothing free on this day. Two ways forward: another day, or the phone. Never a dead end. | אין מועדים פנויים בתאריך הזה. אפשר לבחור תאריך אחר, ואפשר גם להתקשר ונמצא לך מועד. | APPROVED |
| `booking.slotsError` | Replaces the slot grid when the `/slots` fetch itself fails (not empty — failed) | We could not load the times right now. Paired with a retry button. Matches the house error voice (`catalog.error`, `dress.error`). | לא הצלחנו לטעון את המועדים כרגע. | APPROVED |
| `booking.depositByPhone` | The sentence above a `ContactPanel` when the selected type has `deposit_required` (**D3** — visible, labelled, not bookable online until E4) | This particular appointment is arranged by phone, because a deposit is part of it. Warm, matter-of-fact. **Not an error. Not an apology.** | את הפגישה הזאת אנחנו קובעות בטלפון, כדי לסגור יחד גם את המקדמה. נשמח שתתקשרי — זה לוקח רגע. | APPROVED |

> ⚠ on `booking.audienceBrides`: the Hebrew has to be a *label*, and "לכלות בלבד" reads faintly like a velvet rope. Alternatives worth your ear: "פגישת כלה", "מיועד לכלות". The chosen wording is also read aloud as part of the type's accessible name.
>
> ⚠ on `booking.depositByPhone`: **P4 proposes showing `deposit_amount_agorot` next to this sentence, rendered through the `Price` component** (spec §Out of scope permits disclosure; `research/insights.md:34` — *"never hide fees mid-flow"*). If you confirm P4, this sentence must read correctly with a price sitting beside it. If you decline P4, it must read correctly with no number at all. It currently does both, deliberately.

### 3.3 Step 2 — `details`: who she is

Size chips live on this step (**P2 — APPROVED 2026-07-29**), and only on the item-based path.

| Key | Where it appears | What it must say (English intent) | DRAFT Hebrew | Status |
|---|---|---|---|---|
| `booking.name` | **Visible** label on the name field (usage law 3 — a placeholder is never a label) | Her name. | שם מלא | APPROVED |
| `booking.nameRequired` | Field error, `role="alert"`, tied by `aria-describedby` | The field is empty and the form cannot go on. Says why we need it. | צריך למלא שם כדי שנוכל לרשום את התור. | APPROVED |
| `booking.nameTooLong` | Field error at 81+ characters. Client bound mirrors `MAX_CUSTOMER_NAME_LENGTH` = **80** (**D7**) | Too long, and by how much. State the number. | השם ארוך מדי. עד 80 תווים. | APPROVED |
| `booking.phone` | **Visible** label on the phone field | Her mobile number. | טלפון נייד | APPROVED |
| `booking.phoneHint` | Help text under the phone field (the `help` prop on `Input`, `aria-describedby`-linked) | Why we want it *and* what format to type. This is the only place the format is taught, so it must match `validation.ts`'s `validatePhone` exactly. | לשליחת קוד אימות חד-פעמי. אפשר להזין עשר ספרות, למשל 0501234567. | APPROVED |
| `booking.phoneInvalid` | Field error, `role="alert"` | This is not a valid Israeli mobile number, and here is what one looks like. | המספר לא נראה כמו מספר נייד ישראלי. אפשר להזין עשר ספרות שמתחילות ב-05. | APPROVED |
| `booking.notes` | **Visible** label on the optional notes textarea (**D7**) | Anything she wants us to know before she arrives. Optional, and it must look optional. | משהו שנשמח לדעת מראש | APPROVED |
| `booking.notesHint` | Help text under the notes field | Says it is optional, and gives two real examples so the field is not intimidating. | לא חובה. למשל: מגיעה עם אמא, צריך שולחן נגיש, או דגם שראית ואהבת. | APPROVED |
| `booking.notesTooLong` | Field error at 501+ characters. Client bound mirrors `MAX_BOOKING_NOTES_LENGTH` = **500** (**D7**) | Too long, and by how much. | ההערה ארוכה מדי. עד 500 תווים. | APPROVED |
| `booking.sizeUnavailable` | **A second line inside the unavailable chip's own `<label>`** — not a sentence under the group (**R15**). **Hard limit ≤24 characters**: it sits inside a 44px chip and becomes part of that radio's accessible name | **An invitation, not a warning.** That size is not in the boutique right now, she may still choose it, and it can be brought in for the fitting. A fitting is not a purchase. | אפשר להזמין במיוחד | APPROVED |
| `booking.sizeRequired` | **ADDITION (R21).** The validation error under the size `<fieldset>` when she presses forward on the item-based path without choosing a size | She has to pick a size. Not a scolding — a prompt. **The backend makes this genuinely required**: `Backend/app/booking/validation.py` rejects a `dress_id` sent without a non-blank `dress_size`, so this is not a UI preference. | צריך לבחור מידה כדי להמשיך | APPROVED |
| `booking.sizeUnavailableNote` | **ADDITION (gate sign-off 2026-07-29).** A sentence under the size-chip group, rendered only when at least one chip is unavailable | The longer, warmer form of the in-chip invitation: a size not in the boutique right now can be brought in for the fitting. Complements `booking.sizeUnavailable`, which stays inside the chip label. | מידה שאינה כרגע בבוטיק אפשר להזמין במיוחד לקראת המדידה. | APPROVED |

> ⚠ on `booking.nameTooLong` / `booking.notesTooLong`: the digits `80` and `500` sit inside the Hebrew, against rule 5. They are short, unambiguous and identical in every locale, so the builder left them inline rather than adding `{{max}}` — **say if you would rather they were interpolated**, which would also let one string serve both fields.
>
> ⚠ on the three phone rows: see §7 question 3 — the format the hint teaches must be the format `validatePhone` accepts, and that function does not exist yet. Whatever you write here **defines** it.
>
> ⚠ on `booking.notesHint`: the two examples are invented. Replace them with the two things brides actually write, which you will know and the builder does not.
>
> ⚠ on `booking.sizeUnavailable`: this is the single hardest row in the deck to get right — it must not read as "out of stock", which is retail language on a screen that is deliberately not retail. **The ≤24-character limit is not stylistic**: review round 1 found that a group-level sentence left the chips reading `36 / 38 / 40 / 42 / 44` with nothing marking *which* size was unavailable — a WCAG 1.3.1 failure invisible to axe. Putting the phrase inside the chip's own `<label>` makes it part of that radio's accessible name by construction, and a 100-character sentence will not fit there. If you want the longer, warmer sentence as well, say so and it becomes a **second** key rendered under the group — the short in-chip phrase still has to exist.

### 3.4 Step 3 — `terms`: the policy

| Key | Where it appears | What it must say (English intent) | DRAFT Hebrew | Status |
|---|---|---|---|---|
| `booking.termsHeading` | The step's `h1` | Names the policy she is about to accept. | מדיניות ביטולים | APPROVED |
| `booking.refundWindow` | Above the policy text, as a plain-language summary. **R19 SPLIT, mid-sentence: this key is the LEAD**, the component renders `<bdi dir="ltr">{refundable_until_hours_before}</bdi>`, and `refundWindowSuffix` closes the sentence | The free-cancellation window, in plain words, so she does not have to infer it from a paragraph. | ביטול עד | APPROVED (shape rev 5 — R19; wording unchanged) |
| `booking.refundWindowSuffix` | **ADDITION (R19 shape, review round 2).** The tail of `refundWindow`, after the isolated number. Exists only because the value sits mid-sentence: a lead alone cannot carry the words that follow it, and i18next interpolation cannot carry the `<bdi>` | The rest of the same approved sentence. **Not new copy** — the seam moved, the words did not. | שעות לפני המועד — ללא חיוב. | APPROVED (shape rev 5 — R19; wording unchanged) |
| `booking.forfeit` | Directly under `refundWindow`. **R19 SPLIT, mid-sentence: this key is the LEAD**, the component renders `<bdi dir="ltr">{forfeit_percent}%</bdi>` — the `%` rides **inside** the bdi so "50%" is one LTR run rather than a digit run beside a loose neutral — and `forfeitSuffix` closes the sentence | What is charged for a late cancellation or a no-show. | ביטול מאוחר יותר, או אי-הגעה — חיוב של | APPROVED (shape rev 5 — R19; wording unchanged) |
| `booking.forfeitSuffix` | **ADDITION (R19 shape, review round 2).** The tail of `forfeit`, after the isolated percentage | The rest of the same approved sentence. **Not new copy.** | מהמקדמה. | APPROVED (shape rev 5 — R19; wording unchanged) |
| `booking.acceptTerms` | Label on the consent **checkbox** (not a switch — see the components section of this package) | She read it and agrees. First person, her voice, not ours. | קראתי את מדיניות הביטולים ואני מסכימה לה. | APPROVED |
| `booking.acceptRequired` | Error under the checkbox when she submits without it, `role="alert"` | The box is required, and why. | כדי להמשיך צריך לאשר את מדיניות הביטולים. | APPROVED |
| `booking.noTermsByPhone` | The sentence above a `ContactPanel` at the **entry** to the flow when `GET /storefront/terms` answers `404 NOT_FOUND` (**D5** — the boutique has published no policy) | Online booking is not open here yet; phone us and we will arrange it. **Warm. Not an outage message, not an apology.** She must not conclude the site is broken. | קביעת תור מקוונת תיפתח כאן בקרוב. בינתיים נשמח שתתקשרי אלינו ונקבע יחד מועד. | APPROVED |

> ⚠ on `booking.forfeit`: the draft says the forfeit is **a percentage of the deposit** (`מהמקדמה`). The backend field is named `forfeit_percent` with no stated base. If it is a percentage of the *service price* rather than the deposit, this string is factually wrong on a legal surface. See §7 question 5 — **this row cannot be approved without an answer.**
>
> ⚠ on `booking.noTermsByPhone`: "תיפתח כאן בקרוב" is a promise about the boutique's own roadmap. If you would rather not promise it, the sentence still works without the clause — but then it has to earn its warmth some other way, because "we don't do online booking" is exactly the dead end this feature exists to remove.

### 3.5 Step 4 — `verify`: the code

The 600-second verification token is minted here and burned by the booking call (**D2** — this is why it is last).

| Key | Where it appears | What it must say (English intent) | DRAFT Hebrew | Status |
|---|---|---|---|---|
| `booking.otpSent` | **The code field's `help` text, under its label** (**R16**) — not a paragraph above the field, and not a live region. Focus moves to the field, so `aria-describedby` speaks it exactly once | A code is on its way, and it is short-lived. **Must be conditional, not a delivery claim** — `POST /storefront/otp/send` always answers `204` and deliberately reveals nothing, not even whether the number exists (rule 2). | שלחנו קוד בן שש ספרות למספר שהזנת. הוא תקף לחמש דקות. | APPROVED |
| `booking.otpCode` | **Visible** label on the code field | The code. | קוד האימות | APPROVED |
| `booking.otpResend` | **One label serving two jobs** (**R18**): the primary button that sends the code for the **first** time, and the secondary button that sends another after the cooldown. There is no separate first-send key | Send the code. **Must not say "again" or "new"** — in sub-state A nothing has been sent yet, and a screen-reader user arriving at an empty form would hear a button offering to resend something that never happened. | שליחת קוד אימות | APPROVED |
| `booking.otpResendWait` | Replaces the resend button's label while it is cooling down. **No interpolation** — see R3 below | The button is not available yet. **Calm and functional — a footnote, not a countdown.** No urgency register (rule 7). Also serves as the disabled button's own explanation, because `disabled` drops it from the tab order and an `aria-describedby` from a disabled control is inert. | אפשר לבקש קוד חדש בעוד רגע | APPROVED |
| `booking.submit` | The final submit button — this is the button that writes the booking | Confirm and book. Unambiguous that this is the commitment. | אישור וקביעת התור | APPROVED |
| `booking.submitting` | The submit button's label while the request is in flight (`Button loading`) | Working. Present tense, no ellipsis drama. | קובעות את התור | APPROVED |

> **`booking.otpResendWait` — resolved by R3, and this row is why.** The first draft interpolated `{{seconds}}`, and ⚠ FINDING 3 below caught that Hebrew wants "בעוד שנייה אחת" at 1 and "בעוד שתי שניות" at 2, so the string was only correct from 3 up — with no i18next plural resources configured anywhere in this repo to fix it. Assembly then found two more costs (interpolation cannot carry the `<bdi dir="ltr">` the numeral needs, and a 1 Hz repaint is the one element a reviewer would read as a countdown under usage law 9) and **removed the number entirely**. The cooldown is still 60 seconds; the label just does not count it down. FINDING 3 is therefore closed, not deferred.
>
> ⚠ on `booking.submitting`: first-person plural feminine, matching the boutique's voice in `he.ts` ("אנחנו מאמינות", "ממשיכות לשפר"). Confirm the voice — see §7 question 2.

### 3.6 The confirmation — outside the stepper

**D6**: F16 has not shipped. A booking created here sends **nothing**. This screen is her only record.

| Key | Where it appears | What it must say (English intent) | DRAFT Hebrew | Status |
|---|---|---|---|---|
| `booking.confirmTitle` | The confirmation screen's `h1` **when the boutique fetch has failed or the name is unavailable** — the nameless fallback | It is done. Unmistakably. | התור נקבע | APPROVED |
| `booking.confirmTitleNamed` | **ADDITION (gate sign-off 2026-07-29, closes §7 Q4 as "yes").** The confirmation screen's `h1` when boutique data is in memory. An i18next string cannot be conditional, so the named/nameless split needs two keys. **R19 SPLIT — this key is the LEAD and the component renders `<bdi>{boutique name}</bdi>` immediately after it, with NO space: the lead ends in the "ב" prefix, which attaches to the name.** A **bare** `<bdi>`, not `dir="ltr"` — the name is free tenant text. This row was added at sign-off *after* R19 was ruled and so was never checked against it; it is the highest-risk instance in the deck, because the value is arbitrary tenant text inside the `h1` of the bride's only record | It is done, at this boutique — so a screenshot stays self-explanatory weeks later. The generic "חנות הכלות" fallback must never appear on her only record; that is what `confirmTitle` is for. | התור נקבע ב | APPROVED (shape rev 5 — R19; wording unchanged) |
| `booking.confirmWhen` | **A bare label** beside the value, not a sentence (**R11**, **R19**). The date and time are rendered by the component from the `201`'s `starts_at`, each wrapped in `<bdi dir="ltr">` at the call site | The word introducing *when*. She will read this back off a screenshot in three weeks, so the value beside it must be bidi-isolated — which an interpolated string cannot do. | מתי | APPROVED |
| `booking.confirmWhat` | **A bare label**, directly under `confirmWhen`. The value (`appointment_type_name` from the `201`) is rendered by the component | The word introducing *what kind of appointment*. | מה | APPROVED |
| `booking.confirmDress` | **ADDITION — not in the spec's inventory.** The dress line on the item-based path only. **R19 SPLIT — value-first AND two-valued, so the key is the lead-less word between them**: the component renders `<bdi>{dress_name}</bdi>`, an `aria-hidden` `·` (the `confirmWhen` precedent), this key, then `<bdi>{dress_size}</bdi>`. Both values are owner text, so both take a **bare** `<bdi>` | Which dress and which size she is coming to try. Omitted entirely on the generic path. | מידה | APPROVED (shape rev 5 — R19; wording unchanged) |
| `booking.confirmKeepScreen` | Under the appointment details, as the screen's closing instruction | **This is the only record.** Tell her to screenshot or save it — warmly, without alarming her, and **without promising any message will follow.** | זה האישור היחיד שלך — כדאי לצלם את המסך או לשמור אותו. אנחנו נחכה לך. | APPROVED |
| `booking.confirmCold` | The whole screen when `/book/confirm` is loaded cold — a reload, or the iOS screenshot round-trip — with no `201` payload in memory (**D8**). Rendered over a `ContactPanel` | Her appointment exists; we simply cannot show the details again from here, and there is no honest way to pretend otherwise. Offer the phone. **Must not frighten her into thinking the booking was lost.** | אם השלמת את קביעת התור, הוא קיים — ואפשר להתקשר ונאשר לך את הפרטים. | APPROVED (rev 4 — conditional per R14) |

> ⚠ **`booking.confirmKeepScreen` changes when F16 ships** (spec Risk 2: *"when F16 ships, revisit the confirmation copy"*). It is the one string in this deck with a known expiry date. Write it so its replacement is a clean swap of this row and nothing else — i.e. do not spread the "this is your only record" idea across `confirmTitle` and `confirmWhat` as well.
>
> ⚠ **`booking.confirmWhat` and `booking.confirmDress` — see ⚠ FINDING 1 in §5.** The inventory has one key for what is structurally two lines, and the dress line is optional. Approving `confirmDress` is a gate decision.
>
> **Why all three confirm rows became bare labels in rev 2.** They were first drafted as interpolated sentences (`{{date}} בשעה {{time}}`). Review round 1 established that **i18next interpolation cannot carry markup**, so the `<bdi dir="ltr">` isolation every one of those values needs is unachievable inside a `t()` string — and this is the one screen whose entire job is to be legible in a screenshot weeks later, where an unisolated `4.8.2026` beside `16:30` can visually reorder. The label/value split (**R19**) is the house pattern already used for `depositByPhone` + `<Price>`. Separately: `{{duration}}` was dropped because **the `201` payload carries no duration** — it is `{id, starts_at, status, appointment_type_name, dress_name, dress_size}` — so the number could only come from the in-memory type list, which the cold branch does not have.
>
> **`booking.confirmCold` — rev 4, and this row has now moved twice.** Sign-off took the honest short form over the draft's reference to a screen she may not remember seeing. The build then surfaced the half R14 actually asked for and sign-off had not delivered: the short form still *asserted* ("התור שלך נקבע"), and `/book/confirm` is guard-exempt, so a hand-typed URL or a stale bookmark reaches this screen with no booking behind it at all. **Rev 4 makes the sentence conditional** — it tells a bride who did complete a booking that it exists, without claiming one to a visitor who did not. The heading stays `document.book` ("קביעת תור") per R12's precedent for a screen that cannot carry a step claim, so no new key was needed. R14 is now satisfied in both halves, structural and textual.

### 3.7 Mid-flow conflicts and dead ends

Every one of these appears **without a page navigation**, so each is announced with `role="alert"` and each must name a next action.

| Key | Where it appears | What it must say (English intent) | DRAFT Hebrew | Status |
|---|---|---|---|---|
| `errors.slotUnavailable` | `409 SLOT_UNAVAILABLE` on submit. The slots are re-fetched and she is returned to the grid | The time was taken while she was filling the form. Here are the current ones. **No blame, no drama** — this is the commonest real failure. | המועד הזה נתפס בינתיים. אלה המועדים הפנויים המעודכנים — אפשר לבחור מועד אחר. | APPROVED |
| `errors.termsStale` | `409 TERMS_STALE` on submit. The policy is re-fetched and re-shown, and the checkbox is cleared | The policy was republished while she was in the flow; this is the new one; read and accept again. | מדיניות הביטולים התעדכנה בזמן שמילאת את הפרטים. זו הגרסה המעודכנת — נשמח שתקראי ותאשרי אותה שוב. | APPROVED |
| `errors.otpInvalid` | `400 OTP_INVALID` — inline under the code field | Wrong code. Two ways out: retype, or ask for a new one. | הקוד שהוזן אינו נכון. אפשר להקליד אותו שוב, או לבקש קוד חדש. | APPROVED |
| `errors.otpExpired` | `400 OTP_EXPIRED` — inline under the code field | The code aged out. One way out: a new code. | תוקף הקוד פג. אפשר לבקש קוד חדש. | APPROVED |
| `errors.phoneNotVerified` | `403 PHONE_NOT_VERIFIED` on submit — the 600-second token died or was already spent. The step collapses to sub-state A with focus on the phone field | The verification expired, not the booking. Nothing she typed is lost. **She must ask for a new code — the design does not send one automatically**, so this may not promise that it did. | האימות פג תוקף. אפשר לבקש קוד חדש ולהמשיך מכאן — הפרטים שמילאת נשמרו. | APPROVED |
| `errors.smsUnavailable` | `503 SMS_NOT_CONFIGURED` **or** `503 SMS_UNAVAILABLE` — one string for both codes (rule 10) | Phone verification is down, so this booking cannot be completed here. **Say it honestly and hand her the phone.** She must not be left retrying. | אימות הטלפון אינו זמין כרגע, ולכן אי אפשר להשלים כאן את קביעת התור. נשמח שתתקשרי אלינו ונקבע יחד מועד. | APPROVED |
| `errors.otpSendBudget` | **ADDITION (R21).** `429` on `POST /storefront/otp/send` specifically — she has spent the per-phone send budget (five an hour). Distinct from `errors.tooManyAttempts`, which covers a spent *verify* or read budget | She has asked for too many codes. The wait is real and roughly an hour, so **offer the phone rather than leaving her to guess when to retry.** | ביקשת כמה קודים בזמן קצר. אפשר לנסות שוב עוד כשעה, ואפשר פשוט להתקשר אלינו ונקבע יחד מועד. | APPROVED |
| `booking.typeGoneRepick` | `404 NOT_FOUND` on submit, and the probe found the appointment type gone. She returns to the type picker | The kind of appointment she chose was withdrawn mid-session. Pick another from the refreshed list. | סוג הפגישה שבחרת כבר אינו זמין. אפשר לבחור סוג אחר מהרשימה המעודכנת. | APPROVED |
| `booking.dressGoneGeneric` | The dress read answered `404` — either before the flow (entered from a stale link) or on the submit probe. **The binding is dropped and the flow continues as a generic appointment** | That dress is no longer listed, and the appointment continues without it. Reassuring, not a dead end. | השמלה שבחרת כבר אינה זמינה. אפשר להמשיך ולקבוע פגישת מדידה רגילה — נשמח למצוא איתך דגמים דומים. | APPROVED |
| `booking.sizeGoneRepick` | `404 NOT_FOUND` on submit, and the probe found the type and dress both present — so the size variant went. She returns to the size chips | The size she picked is no longer listed. Pick another. | המידה שבחרת כבר אינה מופיעה ברשימה. אפשר לבחור מידה אחרת מהרשימה המעודכנת. | APPROVED |
| `booking.contactUnavailable` | **ADDITION — not in the spec's inventory (gate proposal P5).** Replaces the `ContactPanel` in **all three** of its branches — the D3 deposit note, the D5 no-terms entry, and the cold confirmation — when the app-wide boutique fetch has failed and there is therefore no phone, no WhatsApp and no address to render (**D12**'s honest consequence) | We cannot show the boutique's contact details right now. Suggest reloading. **Must be name-free** — by definition the boutique's name is unavailable too. | לא הצלחנו לטעון כאן את פרטי הקשר של הבוטיק. אפשר לנסות לרענן את העמוד בעוד רגע. | APPROVED |

> ⚠ on `errors.slotUnavailable`: "אלה המועדים הפנויים המעודכנים" assumes the refreshed grid is visible directly under the message. If the design puts the message somewhere the grid is not adjacent, the sentence needs rewording. It is the commonest real failure in the flow, so it earns the most careful sentence in this deck.
>
> ⚠ on `errors.phoneNotVerified`: two promises about behaviour here, and both were checked in round 1. **"הפרטים שמילאת נשמרו" holds** — the design package's §6.12 "what survives" table establishes that the slot, name, notes and terms acceptance all persist across a re-verification, because the backend rolls the whole transaction back. **The original draft's "נשלח קוד חדש" did not hold** and was corrected: the design collapses to the phone sub-state and sends nothing, so she would have read a promise and then had to press a button. Auto-sending was declined because it spends one of five hourly `/otp/send` budgets without her asking.
>
> ⚠ on `booking.dressGoneGeneric`: the draft says "נשמח למצוא איתך דגמים דומים", which commits the boutique to something. Trim it if you would rather not.
>
> ⚠ on `booking.contactUnavailable`: this is an ADDITION and needs your approval as such. Its shape is copied from a shipped precedent — `statement.coordinatorNoChannel` (`he.ts:184-185`), which says plainly that no channel is published rather than rendering an empty list. That precedent interpolates `{{name}}`; this one **cannot**, because the failed fetch is exactly what took the name away.

---

## 4. Additions to the spec's inventory

The spec's §Design i18n inventory is the fixed key list. This deck proposed **seven** keys beyond it, and the sign-off session added **two** more — all **nine approved 2026-07-29**. None replaces a spec key; each covers something the inventory cannot express.

**Two of the seven are not optional.** `booking.sizeRequired` and `errors.otpSendBudget` are rendered by the design and had no row here until review round 1 caught them. `i18n-keys.test.ts` scans `src/` for dotted literals and asserts each resolves to non-empty Hebrew, so a component calling `t("booking.sizeRequired")` against a deck that never defined it is a **failing test on day one**, not a blank span. Declining them means changing the design, not dropping a string.

| Key | Why it is not in the spec | Status |
|---|---|---|
| `booking.contactUnavailable` | **Gate proposal P5.** **D12** was written after the inventory and its consequence — that all `ContactPanel` branches must degrade to plain copy when `useBoutique()` has nothing — has no key in the list. Without it those branches render an **empty box**: `ContactPanel` guards every row on truthiness and returns a bare `<div>` when all five channel props are absent. | **APPROVED — 2026-07-29** |
| `booking.confirmDress` | See ⚠ FINDING 1. The `201` payload carries `dress_name` and `dress_size`, **D6** requires the confirmation to state the appointment in full, and the inventory has one `confirmWhat` key for what is two lines — one of which is conditional. | **APPROVED — 2026-07-29** |
| `booking.continue` | **Gate proposal P6 / reconciliation R4.** The inventory carries **one** forward label (`booking.submit`) for **four** forward actions. Steps 1–3 advance; step 4 commits an appointment after a cancellation policy has just been accepted. One string cannot honestly be both — a "שליחה" on the slot step promises a booking three screens early, and a neutral "המשך" on the verify step under-states an irreversible commitment. | **APPROVED — 2026-07-29** |
| `booking.pickTime` | **F-A6.** The slot grid is a `<fieldset>` of radios, so its accessible name is its `<legend>`, and usage law 3 requires that legend to be **visible**. The inventory has `pickDate` for the date control and nothing for the grid beside it. | **APPROVED — 2026-07-29** |
| `booking.forDress` | The item-based path shows a non-interactive chip naming the bound dress, so a bride who arrived from a dress page can see the flow remembered it. The inventory has no key for it, and hardcoding the Hebrew is what `i18n-keys.test.ts` exists to prevent. | **APPROVED — 2026-07-29** |
| `booking.sizeRequired` | **R21 — not optional.** The item-based path cannot submit without a size: `Backend/app/booking/validation.py` rejects a `dress_id` sent without a non-blank `dress_size`. The step therefore has a required-field validation error and the inventory has no string for it. | **APPROVED — 2026-07-29** |
| `errors.otpSendBudget` | **R21 — not optional.** A `429` on `/otp/send` is a distinct face from a `429` on `/otp/verify` or on a read: the wait is roughly an hour and the right answer is the phone, not a retry. Folding it into `errors.tooManyAttempts` would tell her to try again shortly when she cannot. | **APPROVED — 2026-07-29** |
| `booking.confirmTitleNamed` | **Added at sign-off (§7 Q4 answered "yes").** The named confirmation title; `confirmTitle` becomes the nameless fallback. Two keys because an i18next string cannot be conditional. | **APPROVED — 2026-07-29** |
| `booking.sizeUnavailableNote` | **Added at sign-off.** The longer invitation under the size-chip group when any chip is unavailable — the warm sentence the ≤24-char in-chip phrase cannot carry. | **APPROVED — 2026-07-29** |

**If you decline any of these five**, say so and the design collapses the affected surface rather than shipping an untranslated string: without `continue` the forward label reverts to a step-neutral `booking.submit` (§3's F-A7 records that fallback); without `pickTime` the grid's legend falls back to `booking.pickDate`, which is wrong but not silent; without `forDress` the binding chip is dropped entirely; without `confirmDress` the item-based confirmation loses its dress line; without `contactUnavailable` the three degraded branches render nothing at all, which is the one case with no acceptable fallback.

---

## 5. ⚠ FINDINGS — things the spec's inventory cannot express as written

### ⚠ FINDING 1 — the item-based confirmation has no key for the dress

**The problem.** `POST /storefront/bookings` answers `201 {id, starts_at, status, appointment_type_name, dress_name, dress_size}`. **D6** requires the confirmation to "state the appointment in full" because it is the bride's only record. The inventory offers exactly two content keys for that screen — `confirmWhen` and `confirmWhat` — and the item-based path has three facts to state: the time, the appointment type, and the dress + size. The dress line is also **conditional**: the generic path has no dress at all.

**Why it cannot be folded into `confirmWhat`.** One key is one string. Interpolating `{{dress}}` and `{{size}}` into `confirmWhat` and passing empty strings on the generic path leaves a dangling separator ("מדידה · 60 דקות · מידה") on the commonest path — and an i18next string is not conditional. The alternative, two differently-worded `confirmWhat` values selected in code, is a hardcoded-Hebrew branch, which `i18n-keys.test.ts` exists to prevent.

**Ruling.** `booking.confirmWhat` states the type and duration on **both** paths. A new key `booking.confirmDress` states the dress and size and is rendered **only** on the item-based path. — **APPROVED — 2026-07-29.**

### ⚠ FINDING 2 — `booking.forfeit` states a fact the spec never establishes

`forfeit_percent` ships on `GET /storefront/terms` alongside `refundable_until_hours_before`, described in the spec as one of *"the two numbers a bride is actually agreeing to"*. Neither the spec nor the field name says **a percentage of what** — the deposit, or the price of the service. The draft Hebrew commits to *the deposit*, which is a guess.

This is a legal surface: the string is the plain-language summary of a policy the bride formally accepts, and `terms_version` is recorded against her booking. **`booking.forfeit` cannot be approved on the builder's guess.** §7 question 5.

**RESOLVED 2026-07-29 — the premise was false; the base IS established, in three places the finding missed.** The F7 spec states it in the schema definition itself — `owner-settings.md:23`: *"`forfeit_percent INTEGER NOT NULL DEFAULT 100 CHECK (forfeit_percent BETWEEN 0 AND 100)` (% of deposit forfeited outside the window)"*. The shipped model repeats it as a comment on the column (`Backend/app/models/terms_version.py:23`: *"% of deposit forfeited outside the refund window"*). And the manage app already shows the owner *"חילוט {forfeit_percent}% מהמקדמה"* (`Frontend/apps/manage/src/components/TermsSection.tsx:99-100`) — the storefront saying anything else would contradict the surface the boutique agreed to. Structurally there is also nothing else to take a percentage of: no service-price field exists anywhere; the only money on an appointment type is `deposit_amount_agorot`. **The draft Hebrew (`מהמקדמה`) is correct as written and is approved.**

### ⚠ FINDING 3 — the OTP resend cooldown has no correct singular form

`booking.otpResendWait` interpolates `{{seconds}}`. Hebrew requires "בעוד שנייה אחת" at 1 and "בעוד שתי שניות" at 2; only 3 and up take the draft's "בעוד {{seconds}} שניות". Nothing in this repo configures i18next plural resources, and `he.ts` has no `_one` / `_two` / `_other` key anywhere.

**Ruling — CLOSED, and more simply than this finding proposed.** The finding is correct and it turned out to be one of three independent reasons to **delete the number entirely** (**R3**). The cooldown label is now a fixed sentence with no interpolation at all, so there is no singular, no dual and no plural to get right. The two other reasons, found during assembly and review: i18next interpolation cannot carry the `<bdi dir="ltr">` markup a numeral needs inside Hebrew, and a per-second repaint is the one element in this flow a reviewer would read as a countdown under usage law 9.

Superseded, and recorded so nobody re-proposes them: the earlier "display only while `seconds >= 3`" compromise, and adding i18next plural resources for one string (which would change the i18n configuration for the whole app and need the `CustomTypeOptions` work the `he.ts` header warns about). The cooldown is still 60 seconds — the label just does not count it down.

### ⚠ FINDING 4 — `booking.noTypes` and `booking.noSlots` both offer a phone the app may not have

**Corrected in rev 2 — the finding's premise was half wrong.** It originally claimed both strings are "plain body copy with no panel below them". That is true of **`booking.noSlots`** only. **`booking.noTypes` does get a full `ContactPanel`** and its own D12 degrade — the design package's F-A2 and its S1-e wireframe both give it one, on the reasoning that a boutique which cannot take *any* booking online is structurally the same dead end as one with no published terms. D12's "all three `ContactPanel` branches" is itself an undercount; there are four.

So the finding reduces to one row, and gains a second point:

1. **`booking.noSlots`** genuinely has no panel. Under D12 its closing phone invitation becomes a suggestion she cannot act on.
2. **`booking.noTypes`** has a panel, which means its sentence should **not** carry a phone invitation of its own — a written "call us" immediately above a labelled call button is the same instruction twice.

**Ruling.** `booking.noSlots` keeps its phone invitation: it is *softer* than a labelled button ("אפשר גם להתקשר"), a bride who arrived from Instagram has a route back to the boutique regardless, and a second degraded variant to cover a rare compound failure is not worth a row. `booking.noTypes` **drops** its invitation and lets the panel beneath it do that job. — **APPROVED — 2026-07-29.** Declined: a `contactUnavailable`-style variant of each, and dropping the phone clause from `noSlots` too, which would make the commonest empty state — a brand-new tenant with no availability yet — a flat dead end.

---

## 6. What a rewrite may safely change, and what it may not

| Change | Safe? |
|---|---|
| Any wording, tone, register, length **within one line of rendered text** | Yes — no layout decision in this package depends on it |
| Making an error string longer | Yes, within reason. Errors render as wrapping body copy with no fixed height |
| Making a **button label** longer | ⚠ Check with the design package's component tables. `booking.submit`, `booking.otpResend` and `booking.otpResendWait` sit in buttons with a 44px minimum block size and no fixed inline size, but `otpResend`/`otpResendWait` swap **inside the same button** and a large width jump between the two reads as a glitch at 375 |
| Making `booking.stepSlot` / `stepDetails` / `stepTerms` / `stepOtp` longer | ⚠ Four labels share one row of the step indicator at 375px. Keep them to one or two words each |
| Renaming a key | **No** — fixed by the spec's inventory; drift breaks the design/test/build contract |
| Renaming an interpolation variable | **No** — rule 3 |
| Adding a key | **No**, other than the two in §4, which are proposals for you to accept or reject |
| Removing the Hebrew from an interpolated string | **No** — rule 4, fails `i18n-keys.test.ts` |

---

## 7. Open copy questions for the user — ALL ANSWERED 2026-07-29

Six genuine judgement calls. Everything else in this deck is a wording preference you can simply overwrite. **Answers recorded under each question.**

1. **Register — is the bride addressed as "את" throughout?** The draft assumes yes, following the shipped storefront copy ("נסי שוב", `catalog.retry`; "אפשר לקבוע תור", `catalog.emptyBody`). But `he.ts:187-189` addresses the accessibility-statement reader in the **plural masculine** ("נתקלתם", "שתספרו לנו"), so the file is not internally consistent today. Confirm "את" for the whole booking flow, and say whether the accessibility page's plural is a deliberate difference or a drift to fix later.

   **ANSWERED: "את" throughout, as drafted.** The accessibility page's plural masculine is drift, logged for a later fix outside F14's scope.

2. **The boutique's voice — first person plural feminine, or third person?** The draft uses "אנחנו קובעות", "נשמח", "שלחנו", matching `statement.intro` ("אנחנו מאמינות… ממשיכות לשפר"). The alternative — referring to the boutique in the third person ("הבוטיק קובע פגישות אלה בטלפון") — is more formal and reads as more distant. This choice touches roughly a third of the deck, so it is worth settling before you rewrite anything.

   **ANSWERED: first person plural feminine, as drafted.**

3. **How should the phone format be taught for Israeli mobiles?** This is not only copy — **whatever you write in `booking.phoneHint` defines what `validation.ts`'s `validatePhone` must accept**, and the same normalisation has to be used on all three calls that carry the number (`/otp/send`, `/otp/verify`, `/bookings`) or a correct code returns `PHONE_NOT_VERIFIED`. Pick one and the builder implements to it: (a) ten digits, `0501234567`; (b) hyphenated, `050-123-4567`; (c) accept both and any spacing, normalise silently; (d) international, `+972 50 123 4567`. The draft assumes **(a) taught, (c) accepted**. Note the example number itself is Latin digits inside a Hebrew sentence — the only such case in this deck.

   **ANSWERED: (a) taught, (c) accepted — confirmed against the shipped backend, which already implements exactly this.** `normalize_israeli_mobile` (`Backend/app/notifications/validation.py:31-48`) is the single normalizer behind all three phone-carrying calls; it accepts `0501234567`, `050-123-4567`, `050 123 4567`, `(050) 1234567`, `+972…`, strips separators, and keys the OTP token on the normalized `+9725XXXXXXXX` — so a formatting difference between send and book **cannot** cause `PHONE_NOT_VERIFIED` (`Backend/tests/test_notifications_validation.py:16-54` is the contract, verbatim). `validatePhone` mirrors its algorithm: charset gate `^\+?[0-9 ()\-]+$` on the raw string → strip non-digits → leading `05` becomes `972` (replacing the zero) → final shape `^9725\d{8}$`. The hint teaches the 10-digit form only.

4. **Should the confirmation name the boutique?** "התור נקבע ב{{name}}" is warmer and makes a screenshot self-explanatory three weeks later — which is exactly what **D6** asks this screen to be. It costs one interpolation and one degraded case: on a failed boutique fetch there is no name, and the fallback would be the generic "חנות הכלות" (`catalog.essenceFallback`), which is arguably worse than no name at all on the bride's only record. The draft **does not** name it. Say if you want it.

   **ANSWERED: yes, name it — with a graceful fallback.** New key `booking.confirmTitleNamed` ("התור נקבע ב{{name}}") renders when boutique data is in memory; `booking.confirmTitle` ("התור נקבע") is the nameless fallback. The generic "חנות הכלות" never appears on the confirmation.

5. **`forfeit_percent` — a percentage of the deposit, or of the price of the service?** See ⚠ FINDING 2. The draft says the deposit. This row is a legal statement recorded against a versioned policy and **cannot be approved without your answer.**

   **ANSWERED: of the deposit — closed by code research, not by preference.** See FINDING 2's RESOLVED note: the F7 spec (`owner-settings.md:23`), the model column comment (`terms_version.py:23`) and the shipped owner-facing summary (`TermsSection.tsx:99-100`, "מהמקדמה") all state the base. Draft approved as written.

6. **Is "מדיניות ביטולים" the right name for the policy on the storefront?** It is what the manage console calls it (`ideation/flows.md:43`, the blocking banner "אין מדיניות ביטולים"), and matching the console keeps one vocabulary across the product. But the storefront is speaking to a bride, not an owner, and the policy also covers no-shows. Alternatives: "תנאי ביטול", "מדיניות ביטול והגעה". This one word appears in `booking.stepTerms`, `booking.termsHeading`, `booking.acceptTerms`, `booking.acceptRequired` and `errors.termsStale` — five rows move together.

   **ANSWERED: "מדיניות ביטולים" — keep the console's vocabulary.** One term across the product; all five rows stay as drafted.

---

## 8. The three `booking.*` keys that already exist

`Frontend/apps/storefront/src/i18n/he.ts:95-99` ships a `booking` section today, from F10's CTA seam.

| Key | Current Hebrew | Fate under D1 | Action |
|---|---|---|---|
| `booking.cta` | קביעת תור למדידה | **Survives, unchanged.** The button's label does not change — only what the button does. Its two call sites (`BookingCTAButton.tsx:32`, and the tests) keep referencing it. | **Keep. Do not renumber, do not reword** unless you want the storefront CTA to read differently, which is a separate change with four test sites behind it |
| `booking.panelTitle` | לקביעת תור, דברו איתנו | **Dead.** Its only production reference is `BookingCTAButton.tsx:42`, the title of the modal that **D1** deletes. Its only other reference is `AboutPage.test.tsx:296`, inside the `it("opens the contact panel…")` block that **Risk 3** names for deletion | **Delete from `he.ts` in the same pass as the modal.** `i18n-keys.test.ts` only checks *used → defined*, never *defined → used*, so a dead key will sit there indefinitely without failing anything |
| `booking.close` | סגירה | **Dead.** Only reference is `BookingCTAButton.tsx:45`, the modal's close button, deleted by **D1** | **Delete from `he.ts` in the same pass.** Same reasoning |

Verified by grep over `Frontend/apps` and `Frontend/packages` at `76ff91d`: `panelTitle` and `close` have no other consumer anywhere in the repo.

> The `booking` section after F14 therefore = `cta` (kept) + the 45 new keys in §3 + the additions in §4 − `panelTitle` − `close`. (Of §4's nine additions, eight are `booking.*`; the ninth, `errors.otpSendBudget`, joins the `errors` section.)

---

## 9. Sign-off

| | |
|---|---|
| Rows in this deck | 1 (`document.book`) + 45 (`booking.*` from the spec's inventory) + 6 (`errors.*`) + 9 (additions, §4 — seven proposed + two added at sign-off) + 3 (build-time additions: `typeRequired`, `timeRequired`, `loading` — approved 2026-07-29) + 2 (rev 5 R19 sentence tails: `refundWindowSuffix`, `forfeitSuffix`) = **66** |
| Rows marked ⚠ | 21 — every one walked and resolved at the 2026-07-29 sign-off session |
| Rows that **cannot** be approved without an answer to a §7 question | None — Q3 and Q5 were closed by code research; all six §7 answers are recorded in place |
| Gate status | **APPROVED — 66 of 66 rows, 2026-07-29** |

**Build-time additions.** Three rows were added during the F14 build and approved the same day. Each exists because a rev-2 ruling removed the UI element that used to carry the meaning: R7 deleted the disabled forward button (so `typeRequired`/`timeRequired` must say in prose what a greyed-out button used to imply), and R30 required a real `role="status"` announcement (so `loading` must name what is loading, where the reused `catalog.loading` said "collection" on a screen that loads times). The pattern is worth noting for F15/F16: **an accessibility ruling that removes a visual affordance usually adds a string.**

The design package's wireframes and state tables can be reviewed and accepted independently of this file; they reference every string by key. **The gate as a whole cannot pass until this table reads `APPROVED` end to end.**
