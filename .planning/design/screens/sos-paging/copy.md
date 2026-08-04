# Copy deck — F37 SOS paging (`apps/manage`: the app-level alert overlay, `SosCentre` inside the shipped `FloorPanel`, `SosRaiseDialog`, and one control on a room tile)

**Date**: 2026-08-03 · **Status**: **DRAFTED under the approved register, self-approved with the design gate.** Interview **Q2** named exactly two novel interaction patterns for this run — F34's shift board and F42's capacity matrix — and E7's screens assemble from F34's board shell and F57's shipped `FloorPanel`, so there is no prototype and no `design-critic` pass. **The gate goes away; this deck does not** — spec **D17** and **D18** make it a build task. **The Hebrew remains the user's to edit post-merge** — the F15 P-1/P-5, F34, F57 and F36 precedent: a one-line `he.ts` / `ar.ts` edit after merge, never a rebuild. Console copy, not a customer-facing SMS, so no counsel gate · **Owner of the Hebrew: the user**
**Consumes**: `.planning/specs/sos-paging.md` (**D1–D18**, and **D17**'s key table, which this deck **outranks**) · `design.md` in this directory (**§1–§11**) · `fitting-rooms/copy.md` (F36 — every reused string comes from it or from F57 unchanged) · `floor-staff-roles/copy.md` (F57)
**Lands in**: `frontend/apps/manage/src/i18n/he.ts` (a new flat `sos.*` namespace) **and `…/i18n/ar.ts`**, same keys, the approved Hebrew standing in untranslated.

**THIS DECK IS CANONICAL.** Spec D17 says so in as many words — *"The canonical key list is the copy deck … not this table"* — and `design.md`'s header repeats it: its inline Hebrew is illustrative. Where a string here differs from spec D17's table or from a `design.md` diagram, **this file is the value that ships**, and every such divergence is marked ⚠ **CORRECTS D17** in its own row with the reason. That is the F57 precedent (three corrections landed in `copy.md` first) and the F36 precedent (four).

**F37 adds no SMS template, sends no message and touches no `comms_templates.py` body.** There is no §SMS section and there cannot be one: **in-app only** (#32 and the 2026-07-31 ruling), no `message_log` row, no `MessageKind` value, no push, no APNs/FCM. ⚠ **That is exactly why §0 rule 2 is the most load-bearing rule in this file** and why it costs this feature its most natural button label.

**49 keys invented, all under `sos.*` — and 4 reused, plus F57's whole `floor.*` state block inherited through `FloorPanel`.** ⚠ Spec D17's table plus its trailing *"plus `sos.acceptedCue` / … / `sos.noteOptional`"* line reads as "~40"; the settled figure is **49** (48 plus DC-4's `sos.roomA11yPrefix`), and spec **Risk 11** («~40 keys transcribed by hand into two files») is understated by a fifth. The mitigation is that this file is **one file to one file** and that spec D17's `ar[key] === he[key]` assertion is the mechanical half of it.

---

## 0. The rules this deck is written under — hard constraints, not preferences

1. **Zero exclamation marks** (pre-decided #5). Mechanically checked — `__tests__/i18n.test.ts` filters every value in `HE` for `"!"`. ⚠ **This is the feature most likely to want one** — a full-screen red emergency is where a well-meaning editor writes «דנה קוראת לעזרה!» — and the rule holds: the red field, the 23px type and the word «עזרה» carry the urgency, and an exclamation mark on a screen a staffer sees fifty times a shift is the fastest way to teach her to read past it. **See §9 for the scan.**
2. ⚠ **Never claim, promise or hedge that a message was sent, in any tense.** `i18n.test.ts` enforces it as `/נשלח|תישלח|בדרך/` over every value in `HE`. **This feature pays for that rule in its single most important string: «בדרך» is the natural Hebrew for "on my way", i.e. for the ack button.** The guard is right and stays — it exists so no string in this console ever promises a message the product did not send, and «בדרך» reads as *en route* in exactly the sense the guard forbids elsewhere. **Resolved by wording, not by an exception**: the ack is **«אני מגיעה»**, the raiser's answer is **«{{name}} מגיעה.»**, and the raise cue is **«הקריאה נרשמה.»** and never «נשלחה».
   ⚠ **And the citation is only TRUE after §0.1's fold.** A `sos.*` namespace that is declared and not folded into `HE` is skipped by this guard entirely, which would leave the whole wording decision resting on nothing.
3. **The screens state, they do not reassure.** Every string is a fact. No «הכל תקין», no «מצוין», no encouragement, no apology, no «אנחנו כאן בשבילך». A staffer under pressure needs a name, a room and a verb.
4. **No string names or implies a retry interval.** F34's rule 9, inherited through `usePoll`'s backoff: consecutive failures stretch the interval 5s → ~60s, so «הרשימה תתעדכן מיד» is true at tick 1 and false by tick 5. Every stale or refused sentence names the **event** («בעדכון הבא»), never a duration.
5. ⚠ **No string names a duration or a threshold, and this rule is the one spec D17 corrected itself on.** «ללא מענה כבר 30 שניות» would state a flat thirty seconds to a shift manager looking at a four-minute-old page, because `escalated` is an unbounded boolean; in `SosCentre` it would sit beside `elapsedLine`'s «זה עתה» at t=31s. **Escalation and stall are named as STATES, never as durations** — «ללא מענה», «אין תזוזה מאז שאושרה» — and the card already carries «מאז 11:20» for the when and `elapsedLine` for the how-long. **Consequence: the client carries no number at all**, which is what makes spec D17's "mirroring a number nothing computes is parity theatre" a complete argument instead of one with a literal 30 sitting in the bundle contradicting it. There is **no literal digit anywhere in this namespace** and §9 asserts it.
6. ⚠ **No string may place a Hebrew preposition, article or agreeing verb immediately against `{{room}}`.** F36's **F-3**, inherited whole. The boutique types «חדר 1 / חדר 2 / הבמה» — the label carries its own noun and its own gender — so «בחדר {{room}}» renders **«בחדר חדר 2»** and «{{room}} נתפס» renders **«הבמה נתפס»**. This deck interpolates `{{room}}` **once**, in an `aria-label`, in the em-dash-value-last shape. Everywhere else the room label is **its own element** and no string touches it — which is `design.md` **P-5** and is why spec D17's `sos.room` row is a note here and not a key.
   **`{{name}}` is exempt and this is the whole distinction.** A name on this surface is always a woman — the product's persona convention is feminine throughout («פנויה», «תפוסה», «בהפסקה», «אשת הצוות») — so a feminine verb against `{{name}}` agrees by construction, which is why «{{name}} מגיעה.» is safe and «{{room}} נתפס» is not. ⚠ **And the ghost value is feminine too**: `sos.raiserGone` is «אשת צוות שאינה ברשימה», so «{{name}} קוראת לעזרה» renders «אשת צוות שאינה ברשימה קוראת לעזרה» — grammatical, which is why the ghost case needs **no second key**.
7. ⚠ **Every accessible name STARTS with its control's visible label** (WCAG 2.5.3 label-in-name, **Level A**, and therefore inside IS 5568's binding scope). Four controls on these screens carry an `aria-label` because the same word appears on several rows, and each is `«visible label» — «הקריאה מ{{name}}»`. **This is where spec D17's `sos.dismissAria` fails**: it proposes «הסתרת ההתראה — …» against a visible «הסתרה», and «הסתרת» is not «הסתרה». Corrected below.
8. **Status is carried by WORDS.** A `Badge`'s colour is reinforcement and never the signal — F51's shipped rule (*"The WORD carries the role; the colour never does"*) and `FloorPanel.tsx:42`+`:735`. ⚠ **On this feature that is not a formality**: the surface is a full-screen red field, and `tokens.md` law 2 is satisfied only because every state — «פתוחה», «מטופלת», «ללא מענה», «אין תזוזה מאז שאושרה» — is a Hebrew word. **Remove every colour from this feature and nothing is lost but emphasis. No emoji, no dots, no glyphs**: an emoji is announced by a screen reader with a name this product did not choose and cannot translate, and the console ships **no icon vocabulary at all**.
9. **Reuse before invention.** `SosCentre` lives inside `FloorPanel`'s poll and inherits every freshness, pause, idle, stale and terminal state; it **must not spell any of them a second way** (spec D17's rule and F57's **F-10** argument). §8 is the list. ⚠ **Two `sos.` keys spec D17 proposes are deleted for the same reason** — see §8.
10. **Every value is a real string.** No `…`-as-placeholder, no Lorem, nothing to be filled in later. There is no `…` anywhere in this deck.
11. **The `ar` column is the approved Hebrew standing in untranslated** (Interview Q3 / pre-decided #47 / the 2026-07-31 languages ruling) and is **never an empty string**: i18next's `returnEmptyString` default renders `""` rather than falling back, so a premature switch would blank the page instead of showing Hebrew. `lng` stays `"he"`, `fallbackLng` stays `"he"`, **no switcher ships**. Spec D17's assertion is `ar[key] === he[key]` for every `sos.*` key — **not "non-empty"**, which passes on an English string, a `TODO`, or a *different* Hebrew wording.

### 0.1 ⚠ The one test edit this deck depends on, and rule 2 is void without it

`i18n.test.ts` selects each feature's flat keys with its own constant and folds them into one `HE` array. **`HE_F37` must be FOLDED INTO `HE`, not merely declared** — the file says so about itself at `:32-36`: *"Folded in, not just declared: without this the resolve check, BOTH register guards and the `ar` parity guard silently skip every F52 key."*

```ts
const HE_F37 = entries(he.translation, (key) => key.startsWith("sos."));
const HE = [
  ...HE_F15, ...HE_F51, ...HE_F52, ...HE_F17, ...HE_F34,
  ...HE_F57, ...HE_F53, ...HE_F33, ...HE_F36, ...HE_F37,
];
```

⚠ **The array now folds NINE constants and F37 makes it ten.** The fold at `:33` is the mechanism and it does not move; the array's own line numbers do, every time a feature lands. **Read the fold, never a citation.**

Without the fold, all 49 hand-transcribed strings ship unchecked for the exclamation mark, for the `/נשלח|תישלח|בדרך/` send-ban — **the ban the entire «אני מגיעה» wording decision rests on** — and for a missing `ar` key.

**No `nav.` term in the selector, and that is an assertion rather than an omission** — F37 adds no nav row (spec D11: `SectionKey` and `NAV` stay thirteen). Every other feature's constant starts `key === "nav.x" || …`; this one does not, and it is the one-line proof that an alert is an interruption and not a destination.

**Give the block its own row-count floor** (`HE_F37.length > 44`), for the reason the file's own comment gives: folded into an existing list, this feature's rows could shrink by this many and still pass.

---

## 1. The alert card — the words she reads while walking

The card's first three lines **are** the `role="alert"` region's children (`design.md` §9.1), so what is written here is exactly what a screen reader announces, once, on mount, as one atomic utterance. ⚠ **The region's text is write-once**: nothing in this section may ever be re-rendered with a different value on the same card, or the whole card is re-announced assertively (AC16).

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `sos.calling` | **Line 1, and the loudest text on the screen.** Who is asking. `text-xl font-semibold`, the name in a bare `<bdi>`. Present tense and continuous — she is calling *now*, not "has called". «קוראת לעזרה» rather than «צריכה עזרה»: the first is an act aimed at the reader, the second is a condition | {{name}} קוראת לעזרה | {{name}} קוראת לעזרה | DRAFTED |
| `sos.raiserGone` | The value substituted into `{{name}}` when `raised_by_name` is `null` — her staff row was removed mid-page (F51's soft delete). **Feminine, so every string that takes `{{name}}` still agrees** (rule 6), which is why the ghost case needs no parallel key anywhere in this deck. Indefinite «אשת צוות», not F36's definite «אשת הצוות», because there is no antecedent here — nothing on this card has named her before | אשת צוות שאינה ברשימה | אשת צוות שאינה ברשימה | DRAFTED |
| — | **Line 2, WHERE.** ⚠ **The VALUE is not a key; the LABEL is.** The room label renders as a bare `<bdi>` in its own element with no prefix and no interpolated sentence (`design.md` **P-5**, rule 6) — but it is preceded by `sos.roomA11yPrefix` below. ⚠ **CORRECTS D17**, whose `sos.room` row already carries the reasoning but is listed as a key | — | — | ⚠ **CORRECTS D17** |
| `sos.roomA11yPrefix` | ⚠ **DC-4, and it is the one visually-hidden string in this deck.** A `<span className="sr-only">` **INSIDE** the `role="alert"` region, immediately before the bare `<bdi>`. It exists because the boutique may type a label that is fully supported on its own — «2» — and the atomic utterance «דנה כהן קוראת לעזרה … 2 … צריך סיכות» does not parse. **NOT an `aria-label` on the `<p>`**: ARIA prohibits naming `role=paragraph`, so the em-dash-value-last shape used for the `*Aria` keys is unavailable here and would have shipped a name nothing reads. One word, a label and never a copy of a value, so there is nothing to drift | מיקום | מיקום | ⚠ **ADDS to D17** |
| `sos.noRoom` | Line 2 when `room_label` is `null` — she was not in a room, which is ordinary (a seamstress at her table). A **defined, safe state**: spec D3 makes the room pointer permissive precisely so a stale or foreign id lands here rather than sending a responder to a stranger's curtain. A statement, so it needs no prefix either | לא בחדר מדידה | לא בחדר מדידה | DRAFTED |
| — | **Line 3, WHAT.** ⚠ **NOT A KEY.** The note is the staffer's own free text in a bare `<bdi>`, and **the element is absent when she typed nothing** — never an empty line, never a placeholder | — | — | — |
| `sos.since` | ⚠ **A SIBLING, outside the announced region.** The absolute raise time through `jerusalemTime`, which never subtracts and is immune to a boutique tablet's clock drift. `{{time}}` in `<bdi dir="ltr">` via `isolateLtr`. **No countdown and no live counter anywhere** (spec D15) — a ticking number inside a `role="alert"` re-announces on some screen readers and drags SC 2.2.2 onto a region whose whole argument is that it has nothing to pause | מאז {{time}} | מאז {{time}} | DRAFTED |
| `sos.escalated` | ⚠ **A SIBLING, outside the region.** Thirty seconds unacknowledged. `text-danger font-semibold`. ⚠ **NOT «ללא מענה כבר 30 שניות»** — rule 5. «ללא מענה» rather than «לא נענתה»: the first describes the alert's current state (which is what the shift manager triages on), the second describes a completed non-event | ללא מענה | ללא מענה | DRAFTED |
| `sos.stalled` | ⚠ **A SIBLING, outside the region.** Accepted and unresolved for two minutes — spec D6's second silence, the one thing between «דנה מגיעה» and an emergency nobody is answering. Same register, same no-number rule. «מאז שאושרה» names the event, not a clock | אין תזוזה מאז שאושרה | אין תזוזה מאז שאושרה | DRAFTED |

**No heading, no title, no chrome on the red field, and that is a decision** (`design.md` **P-8**). Line 1 *is* the heading, it is inside the live region where it does the most good, and a field-level heading would sit outside every region restating what the regions already say.

---

## 2. The overlay's two controls

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `sos.accept` | **The single most important button in this feature.** `Button primary lg fullWidthMobile`, 48px, **first in DOM so it is one Tab from the card container MOVE A lands on** — ⚠ **and deliberately NOT the destination of that move** (`design.md` **DC-1**/§2.3): MOVE A fires exactly when the next Space would be a page scroll, and there is no un-accept verb. ⚠ **NOT «אני בדרך»**, which is the natural Hebrew and trips the global `/נשלח\|תישלח\|בדרך/` ban (rule 2). «אני מגיעה» is first-person, present-continuous and commits her — «בסדר» or «קיבלתי» would acknowledge a *message*; this acknowledges a *person*, and the raiser is told the same word back | אני מגיעה | אני מגיעה | DRAFTED |
| `sos.acceptAria` | Its accessible name. Several cards can be up at once and «אני מגיעה» three times is a screen-reader dead end. **Starts with the visible label** (rule 7). An `aria-label` takes no markup, so the interpolated name needs no bidi treatment (F57 **F-11**). Renders «אני מגיעה — הקריאה מדנה כהן», and with a removed raiser «אני מגיעה — הקריאה מאשת צוות שאינה ברשימה» — grammatical in both | אני מגיעה — הקריאה מ{{name}} | אני מגיעה — הקריאה מ{{name}} | DRAFTED |
| `sos.dismiss` | `Button ghost md`, second in DOM, its own line. **Per-device and in-memory**: the alert stays open, keeps escalating, and comes back on reload — because if it is still open it is still an emergency. «הסתרה» and not «סגירה» or «ביטול», both of which would claim the alert was closed. It is also the SC 2.2.2 "hide" mechanism for the one region that has content | הסתרה | הסתרה | DRAFTED |
| `sos.dismissAria` | ⚠ **CORRECTS D17**, which proposes «הסתרת ההתראה — קריאה מ{{name}}» against a visible «הסתרה». **An accessible name must contain the visible label** — WCAG 2.5.3 label-in-name, **Level A** — and «הסתרת» is a different word from «הסתרה», so voice control would fail on the visible one. Same em-dash shape as the accept | הסתרה — הקריאה מ{{name}} | הסתרה — הקריאה מ{{name}} | ⚠ **CORRECTS D17** |

---

## 3. The two app-level surfaces the overlay renders instead of `null`

Both live on the eleven sections that have no `SosCentre` and no `role="status"` region of their own, which is why they exist at all.

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `sos.channelDown` | The persistent strip on a **403** on the poll (terminal `access` — ⚠ **not a logout**) or on a loop backed off beyond one tick. **«Nothing renders» is not an acceptable state for an emergency receiver that has stopped receiving.** States the fact and nothing else: it does not apologise, does not guess a cause and does not name an interval (rule 4). «ערוץ הקריאות» rather than «המערכת» — what is dead is this channel, not the console she is still using | ערוץ הקריאות אינו פעיל. | ערוץ הקריאות אינו פעיל. | DRAFTED |
| `sos.channelReload` | Its one control. ⚠ **CORRECTS D17**, which says «רענון». D17's own instruction is *"reuse `floor.reload`'s word"* — and `floor.reload` is **«רענון הדף»**; «רענון» is `floor.refresh`, a **different act** (refetch the list) offered by a different control. The strip's only remedy is a page reload, and a button labelled «רענון» that reloads the whole page is a promise the word does not make. Its own key, not a reuse, because the strip renders on eleven sections where `floor.*` does not | רענון הדף | רענון הדף | ⚠ **CORRECTS D17** |
| `sos.dismissedCount` | The persistent ≥44×44 affordance that re-opens the overlay while the dismiss set holds a **live** alert. **Without it, a dismissal on any of the eleven sections with no SOS centre is total and permanent** — and the role-targeted route is the raise dialog's first and default option, so that is the common path, not an edge. `{{count}}` in `<bdi dir="ltr">`; the middot is the console's shipped separator. **No literal digit** (rule 5) — `{{count}}` is an interpolation and the guard is on literals | קריאות עזרה · {{count}} | קריאות עזרה · {{count}} | DRAFTED |

**A 401 renders neither**, and that is deliberate: the loop stops, `onSessionEnded` fires exactly once, and `App` drops the console to `LoginForm` through the `setStaff(null)` it already has. A strip saying the channel is down over a login screen would be true and useless.

---

## 4. The SOS centre — on `board` and `floor`, which is 2 of 13 sections

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `sos.centreHeading` | The panel's `h3`, a sibling of F36's «חדרי מדידה» under F57's `h2` «צוות בקומה». Also `tabIndex={-1}`, MOVE G's last-resort target. Plural and indefinite: it names a group of things, not a destination, and there is no nav row for it to match | קריאות עזרה | קריאות עזרה | DRAFTED |
| `sos.centreEmpty` | ⚠ **The state this panel is in almost always**, and the design deliberately declines `EmptyState` for it (`design.md` **P-6**): 140px of `font-display text-xl` announcing that there is no emergency would make the absence of an emergency the visual centre of the floor screen. One muted line, `text-sm`. «אין עכשיו» rather than «אין» — *not right now*, which is a state, rather than *none*, which reads like a fault or an empty registry | אין עכשיו קריאות פתוחות. | אין עכשיו קריאות פתוחות. | DRAFTED |
| `sos.statusOpen` | The row's single `Badge`, `variant="danger"`. Feminine to agree with «קריאה». **The word carries the state; the colour never does** (rule 8) | פתוחה | פתוחה | DRAFTED |
| `sos.statusAccepted` | The same `Badge`, `variant="neutral"`. «מטופלת» — *being handled* — rather than «התקבלה», which would say only that somebody pressed a button | מטופלת | מטופלת | DRAFTED |
| `sos.acceptedBy` | ⚠ **The raiser's answer, and the reason the tick drops to two seconds.** Renders on the accepted row for everyone who can see it. The **same verb as the button**, deliberately: she pressed «אני מגיעה» and the raiser reads «דנה כהן מגיעה.» — one word, two screens, no translation between them. ⚠ **NOT «דנה בדרך»** (rule 2) | {{name}} מגיעה. | {{name}} מגיעה. | DRAFTED |
| — | ⚠ **The honesty note that belongs with the row above, recorded rather than softened (DC-6).** «{{name}} מגיעה.» is **deliberately stronger than the fact**: the product knows an *intention* — somebody tapped a button — and never a *walk*. Nothing in this feature observes a person moving, and the raiser reads that sentence and stops looking for help. What bounds the gap is D6's `_stalled` at two minutes, and nothing else. **See `design.md` §11 F-2**, which records the two-minute window as a finding rather than as reassurance | — | — | — |
| `sos.acceptedByUnknown` | The same line when `accepted_by_name` is `null` — the acceptor's staff row was removed between her accept and this read. **«מישהי» is better than a blank interpolation on a legally binding surface**: a sentence that admits it does not know beats «‎ כבר מגיעה.» | מישהי כבר מגיעה. | מישהי כבר מגיעה. | DRAFTED |
| `sos.resolve` | `Button ghost md`. Rendered for the raiser, the acceptor or an elevated caller. «נפתר» — the *emergency* resolved, not "the task completed" — and it is deliberately the same word the cancel-refusal points at (§7) | נפתר | נפתר | DRAFTED |
| `sos.resolveAria` | Several rows, one word. Starts with the visible label (rule 7) | נפתר — הקריאה מ{{name}} | נפתר — הקריאה מ{{name}} | DRAFTED |
| `sos.cancel` | `Button ghost md`. Rendered for the raiser or an elevated caller, and **only while the alert is open**: cancelling an *accepted* alert is a 409, because a colleague is already walking to that curtain. «ביטול הקריאה» rather than a bare «ביטול», because on a row that also offers «נפתר» the reader must be able to tell "never mind" from "it is over" | ביטול הקריאה | ביטול הקריאה | DRAFTED |
| `sos.cancelAria` | Starts with the visible label. ⚠ **The bare `— {{name}}` shape here and not `— הקריאה מ{{name}}`**, because the visible label already ends in «הקריאה» and the accessible name would otherwise read «ביטול הקריאה — הקריאה מדנה» | ביטול הקריאה — {{name}} | ביטול הקריאה — {{name}} | DRAFTED |

**No «הקריאה שלך» marker on the raiser's own row, and that is a resolved decision** (`design.md` §4.2): with one alert there is nothing to scan, with three her own name is right there, and the controls already differ — she is the one person with no accept control and the only one with cancel. One key fewer; add it if a pilot raiser ever asks which row is hers.

---

## 5. The raise control, on a room tile and in the SOS centre

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `sos.raise` | **Both triggers, one string.** The tile's fourth control (`Button danger md`, first in the action row, rendered only when `assignment.staff_user_id === selfId`) and the SOS centre's heading-row trigger (`Button danger md`, all five roles, always). ⚠ **CORRECTS D17**, which lists `sos.raise` and `sos.centreRaise` separately: the two strings are identical, and two keys holding one value are two things to keep true and twice the hand transcription into `ar.ts`. «קריאה לעזרה» and not «SOS» — the console ships no Latin abbreviation and a screen reader would spell it | קריאה לעזרה | קריאה לעזרה | ⚠ **CORRECTS D17** |
| `sos.raiseAria` | The **tile** trigger's accessible name only — one tile per room and the visible label repeats. The SOS-centre trigger needs none: its label is unique on that panel. ⚠ **Em-dash, value last** (rule 6): «קריאה לעזרה — חדר 2» and «קריאה לעזרה — הבמה» both read correctly, where «קריאה לעזרה מחדר {{room}}» would render «מחדר חדר 2» | קריאה לעזרה — {{room}} | קריאה לעזרה — {{room}} | DRAFTED |

**A mis-tap on either trigger costs one Esc**, because neither pages anybody — both open `SosRaiseDialog`, which has a default target and a separate send. That is what lets the control be as large and as prominent as an emergency deserves (`design.md` **P-7**).

---

## 6. `SosRaiseDialog`

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `sos.title` | The shipped `Modal`'s `title`, rendered as its own `h2` in the top layer. Same words as the trigger, its own key: a heading and a button label are different roles and diverge the first time anybody edits one | קריאה לעזרה | קריאה לעזרה | DRAFTED |
| `sos.targetPick` | The `Select`'s **label**, never a placeholder (`tokens.md` usage law 3). A question, because that is what she is answering under pressure. «למי לקרוא» and not «נמענת» or «יעד» — system words on the one screen that must read like a person | למי לקרוא | למי לקרוא | DRAFTED |
| `sos.targetManager` | ⚠ **The first option and the default** (`value=""` → `target_staff_user_id: null`). The route whose audience **can never be empty** — F51's last-owner advisory lock holds *"at least one live owner"*, and the role audience is `{owner, shift_manager}` — so it is the one choice a staffer under pressure never has to think about. The role, not a name, because that is what the column means | מנהלת המשמרת | מנהלת המשמרת | DRAFTED |
| — | A colleague on a break, annotated in the list. ⚠ **CORRECTS D17**, which proposes `sos.targetOnBreak` — **reuse the shipped `rooms.handoverOnBreak`** («{{name}} — בהפסקה»), identical string, identical purpose (annotating a colleague in a target `Select`), already transcribed into both bundles. **Annotated, never excluded**: a seamstress on a five-minute break is exactly who you want for a corset back | *(reused)* | *(reused)* | ⚠ **CORRECTS D17** |
| `sos.notePick` | The `Input`'s **label**. Four words is what a staffer holding a corset will type, so the label asks for a thing and not a sentence. «מה צריך» and not «הערה» — the second invites prose | מה צריך | מה צריך | DRAFTED |
| `sos.noteOptional` | The `Input`'s `help` line. ⚠ **It matters more here than anywhere else in the console**: a staffer who believes the field is required will type something rather than tap send, and this is the one screen where two seconds is real. `maxLength` is 120 client-side, so over-length is unreachable — **and the help line carries no number** (rule 5) | לא חובה | לא חובה | DRAFTED |
| `sos.send` | The `Modal` footer's confirm, `Button secondary md` (the house pattern: `ghost` dismiss + `secondary` confirm). ⚠ **«שליחת» does NOT trip the ban** — the regex is `/נשלח\|תישלח\|בדרך/` and «שליחת» contains neither `נשלח` nor `תישלח`. Checked, because it *looks* like it should. The verb is safe precisely because it describes **the act she is performing now**, not a message the product claims to have delivered | שליחת הקריאה | שליחת הקריאה | DRAFTED |
| — | The footer's ghost dismiss. **Reuse the shipped `rooms.cancel`** («ביטול»), exactly as F36 reuses `floor.*` inside `rooms` — cross-namespace reuse is the deck-wide rule, not an exception | *(reused)* | *(reused)* | — |

---

## 7. Outcomes — cues, the toast, the reroute acknowledgement, and the errors

⚠ **The five cue strings render in TWO different regions and that is deliberate** (spec D17, `design.md` §9.5). `SosCentre` writes them into `FloorPanel`'s single `role="status"`; `SosOverlay` passes them to the shipped app-level `useToast()`, because on the eleven sections with no `SosCentre` there is **no `role="status"` region at all** and an accept would otherwise produce: the red vanishes, focus jumps to the top of an unlabelled `<main>`, and nothing is announced or shown. **One string, two regions.**

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `sos.raisedCue` | After a raise that was **not** rerouted. ⚠ **«נרשמה», never «נשלחה»** (rule 2) — and the wording is honest as well as compliant: what happened is that a **row was written**, and whether a phone lights up depends on a colleague having a console open, which the product cannot promise (spec Risk 1) | הקריאה נרשמה. | הקריאה נרשמה. | DRAFTED |
| `sos.acceptedCue` | After **this** caller accepts. She needs to know the tap landed, because on a non-floor section the only other feedback is a red field disappearing | הקריאה התקבלה. | הקריאה התקבלה. | DRAFTED |
| `sos.resolvedCue` | After a resolve — from either live state. The emergency is over | הקריאה נסגרה. | הקריאה נסגרה. | DRAFTED |
| `sos.cancelledCue` | After a cancel — from `open` only | הקריאה בוטלה. | הקריאה בוטלה. | DRAFTED |
| `sos.dismissedCue` | After «הסתרה». ⚠ **Says «הוסתרה» and not «נסגרה»**, because the alert is untouched on the server: it stays open, keeps escalating, and comes back on reload. A cue that said "closed" would be the one lie this feature cannot afford | ההתראה הוסתרה. | ההתראה הוסתרה. | DRAFTED |
| `sos.rerouted` | ⚠ **The raise dialog's BODY on a rerouted raise, not a transient cue** (spec D16) — the dialog stays open and she must acknowledge it. Delivering the one message the ruling mandates as a polite cue, written into a region whose text the next cue overwrites, at the exact moment a `<dialog>` closes and focus moves, is the classic case AT drops or defers — **and it is unrecoverable**, because `rerouted` is a fact about the *request*, so no `SosCentre` row can ever say it again. **Two sentences: what is not true, then what is.** «לא מחוברת» rather than «לא בעבודה» — the product knows about sessions, not shifts, and spec D3 is explicit that a live session is an **upper bound** on reachability | {{name}} לא מחוברת עכשיו. הקריאה עברה למנהלת המשמרת. | {{name}} לא מחוברת עכשיו. הקריאה עברה למנהלת המשמרת. | DRAFTED |
| `sos.reroutedAck` | The one control that closes a rerouted dialog, `Button secondary md`, and **MOVE E's focus destination** — the send button it replaces has just unmounted. «הבנתי» is an acknowledgement rather than a dismissal, which is the correct interaction weight for a message the product needs her to have read | הבנתי | הבנתי | DRAFTED |

### 7.1 Errors

| Key | Condition | Approved Hebrew (`he`) | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `sos.error.SOS_ALREADY_ACCEPTED` | **409 on accept, with `details.staff_display_name`.** The ruling's *"a 409 NAMING THE OWNER"*, rendered. She has not lost anything — somebody is going | {{name}} כבר מגיעה. | {{name}} כבר מגיעה. | DRAFTED |
| `sos.error.alreadyAcceptedUnknown` | The same 409 **with the `details` key absent** — the winner's staff row was removed between her accept and this read. ⚠ **`details` is optional and typed `Record<string, string> \| undefined`, never `\| null`**, precisely so «‎ כבר מגיעה.» is unconstructible: a sentence that admits it does not know beats an empty interpolation on a legally binding surface | מישהי אחרת כבר מגיעה. | מישהי אחרת כבר מגיעה. | DRAFTED |
| `sos.error.SOS_CLOSED` | **409 on accept** of a resolved or cancelled alert. Two codes and not one with a discriminating `details`: two causes, two sentences, **two remedies** — go somewhere else, versus there is nothing to do | הקריאה כבר נסגרה. | הקריאה כבר נסגרה. | DRAFTED |
| `sos.error.cancelAfterAccept` | **409 on cancel** of an accepted alert. ⚠ **The asymmetry with resolve is the point**: a colleague is already walking to that curtain, and silently cancelling would send her to an empty room and teach her that accepting means nothing. **So the sentence carries the remedy**, and the remedy is one word over. Guillemets around «נפתר» because it is a control's name (F36's shipped shape) | {{name}} כבר מגיעה. אפשר לסמן «נפתר» במקום. | {{name}} כבר מגיעה. אפשר לסמן «נפתר» במקום. | DRAFTED |
| `sos.error.cancelAfterAcceptUnknown` | ⚠ **The `details`-less variant of the row above, which spec D17 does not list.** D5's cancel table marks `details` **optional** on the cancel 409 by the same rule as D4's — the acceptor can be removed at any moment — so without this key the console renders an empty interpolation on exactly the path D14's whole optional-`details` argument exists to prevent. **Deck-added, and it is the second key this deck adds beyond D17** | מישהי אחרת כבר מגיעה. אפשר לסמן «נפתר» במקום. | מישהי אחרת כבר מגיעה. אפשר לסמן «נפתר» במקום. | ⚠ **ADDS TO D17** |
| `sos.error.notFound` | **404 on any of the three actions** — the alert was swept or never existed. **Not terminal.** Names the event and never an interval (rule 4) | הקריאה כבר לא פתוחה. הרשימה תתוקן בעדכון הבא. | הקריאה כבר לא פתוחה. הרשימה תתוקן בעדכון הבא. | DRAFTED |
| `sos.error.noteTooLong` | **400** on an over-length note. Unreachable client-side (`maxLength` = `MAX_SOS_NOTE_LENGTH`), and the string exists anyway because the server's rule is the real one. **Carries no number** (rule 5) | ההודעה ארוכה מדי. | ההודעה ארוכה מדי. | DRAFTED |
| `sos.error.selfTarget` | **400** on `target_staff_user_id == actor.id`. Unreachable because the dialog excludes her from the list — **excluding it prevents the error rather than explaining it**, which is F36's `RoomHandoverDialog` argument. The string exists because the server refuses it | אי אפשר לקרוא לעצמך. | אי אפשר לקרוא לעצמך. | DRAFTED |
| `sos.error.raiseFailed` | ⚠ **The send did not complete** — a 5xx, a dropped connection, a wifi blackspot inside a curtain, which is the single most likely real-world failure of a phone held behind a closed fitting-room curtain. Without this key the builder falls through to `errorMessage()`'s `FALLBACK_ERROR_MESSAGE` — «אירעה שגיאה בלתי צפויה. נסי שוב.» — **on the one screen in the product where «try again» alone is the wrong instruction.** ⚠ **«נרשמה», never «נשלחה»** (rule 2). **The only string in this console that names the manual fallback out loud**, and the dialog stays open with the note preserved so a retry costs one tap | הקריאה לא נרשמה. נסי שוב — או קראי בקול. | הקריאה לא נרשמה. נסי שוב — או קראי בקול. | DRAFTED |
| `sos.error.actionFailed` | An unmapped failure on **accept / resolve / cancel** — 5xx, network. ⚠ **Deliberately does NOT name the manual fallback, and the distinction is real**: a failed *raise* means nobody was called and the emergency is invisible, so «or shout» is the correct instruction. A failed *accept* means only that **she** did not claim it — the alert is still open, still rising on every other targeted device and still escalating, so nothing has been dropped and «נסי שוב» is exactly right. **Deck-added; D17 has no key for this path and `staff.loadFailed` («לא הצלחנו לטעון את רשימת הצוות כרגע.») is about loading a staff list** | הפעולה לא הושלמה. נסי שוב. | הפעולה לא הושלמה. נסי שוב. | ⚠ **ADDS TO D17** |

---

## 8. Reused — SHIPPED, never re-declared, never counted into the 49

`SosCentre` lives inside `FloorPanel`'s poll and **must not spell any of its states a second way** (rule 9, F57's **F-10**).

| Key | Value | Owner | Where F37 uses it |
|---|---|---|---|
| `rooms.cancel` | ביטול | F36 | `SosRaiseDialog`'s ghost dismiss |
| `rooms.handoverOnBreak` | {{name}} — בהפסקה | F36 | the target `Select`'s on-break annotation ⚠ **replaces D17's proposed `sos.targetOnBreak`** |
| `rooms.elapsed` | כבר {{minutes}} דק' | F36 | every `SosCentre` row, through the shipped `elapsedLine` |
| `rooms.elapsedJustNow` | זה עתה | F36 | the same, under one minute |
| `floor.heading` · `floor.loading` · `floor.updatedAt` · `floor.staleAt` · `floor.staleBody` · `floor.refresh` · `floor.pause` · `floor.pauseAria` · `floor.resume` · `floor.resumeAria` · `floor.pausedAt` · `floor.paused` · `floor.idleStopped` · `floor.resumed` · `floor.sessionEnded` · `floor.accessEnded` · `floor.reload` | *(as shipped)* | F57 | inherited whole by `SosCentre` — it owns **no** poll, **no** freshness row, **no** pause control and **no** live region of its own |

⚠ **`lib/elapsed.ts` hardcodes `rooms.elapsed` and `rooms.elapsedJustNow`**, so the cross-namespace reuse is not a stylistic choice: the alternative is a second elapsed implementation, which spec D17's own no-date-library rule forbids. Recorded as a deliberate cross-namespace reuse, exactly as F36 reused `floor.*` inside `rooms`.

⚠ **`floor.reload` is reused as a WORD but not as a KEY** — §3's `sos.channelReload` copies its value «רענון הדף» into its own key, because the strip renders on eleven sections where no `floor.*` string otherwise appears and a `floor.`-prefixed key on the catalog screen would be a namespace lie. **That is the one duplicate value this deck ships, and it is deliberate** — F57's **F-9** already records ten `board.*` / `floor.*` duplicates and names the `poll.*` rename as the upgrade path; this is the eleventh and F36 predicted it. *`design.md` **F-4** carries the trigger.*

---

## 9. The scan — every rule, mechanically, over all 49 values

| Rule | Method | Result |
|---|---|---|
| **1 — no `"!"`** | every value scanned | **0 hits.** ⚠ The temptation is real on a full-screen emergency and the answer is that the red field, the 23px type and the word «עזרה» carry it |
| **2 — no `/נשלח\|תישלח\|בדרך/`** (⚠ **the THREE-term regex at `i18n.test.ts:560`, NOT the `HE_F33`-scoped FIVE-term `/נשלח\|תישלח\|בדרך\|SMS\|הודעה/` at `:547`** — «הודעה» is in the approved `sos.error.noteTooLong`, so the five-term form would red this namespace on an approved string) | every value scanned, **including the near-misses** | **0 hits.** ⚠ Checked by hand and not by eye: **«שליחת הקריאה»** contains neither `נשלח` nor `תישלח` (it is ש-ל-י-ח-ת); **«הקריאה נרשמה.»** and **«הקריאה לא נרשמה.»** are `נרשמ`, not `נשלח`; **«אני מגיעה» / «{{name}} מגיעה.» / «מישהי כבר מגיעה.» / «{{name}} כבר מגיעה.»** are the four places «בדרך» would have been written and none of them is. **The `sos.*`-scoped assertion in `i18n.test.ts` states this where the block is read** — belt-and-braces over the global guard §0.1's fold restores, not a substitute for it |
| **3 — states, does not reassure** | every value | no «הכל תקין», no «מצוין», no apology, no encouragement |
| **4 — no retry interval** | every value | «בעדכון הבא» once (`sos.error.notFound`); no «מיד», no «בקרוב», no seconds |
| **5 — no duration, no threshold, NO LITERAL DIGIT** | `/\d/` over every value | **0 hits.** «ללא מענה» and «אין תזוזה מאז שאושרה» name the thresholds as **states**; «מאז {{time}}» and «קריאות עזרה · {{count}}» carry interpolations, not literals. **This is what makes spec D17's refusal to mirror `ESCALATION_AFTER` a complete argument** |
| **6 — nothing glued to `{{room}}`** | every `{{room}}` use | **one** use, `sos.raiseAria`, in the em-dash-value-last shape. Everywhere else the room label is its own element and no string touches it |
| **7 — accessible name contains the visible label** | the four `*Aria` keys | ✓ after the `sos.dismissAria` correction. `sos.acceptAria` / `sos.dismissAria` / `sos.resolveAria` / `sos.cancelAria` each start with their control's exact visible string |
| **8 — status is a word** | every state | «פתוחה», «מטופלת», «ללא מענה», «אין תזוזה מאז שאושרה», «לא בחדר מדידה». **No emoji, no dot, no glyph, in any value** |
| **10 — every value is real** | every value | no `…`, no placeholder, no TODO |
| **11 — `ar[key] === he[key]`** | all 49 rows | ✓ by construction — the two columns of this file are byte-identical, which is what the spec's assertion checks and what makes this deck **one file to one file** |

---

## 10. Landing checklist

1. **Transcribe all 49 rows into `he.ts` and `ar.ts`, from this file and not from spec D17's table.** Five rows differ (§0, §2, §3, §5, §6) and two are additions D17 does not have (§7.1).
2. ⚠ **Add `HE_F37` to `i18n.test.ts` AND FOLD IT INTO `HE`** (§0.1) — **first**, before any assertion is written, because without it the exclamation guard, the send-ban and the `ar` parity guard all silently skip this namespace and the «אני מגיעה» decision rests on nothing. Give it its own row-count floor.
3. **Add the `sos.*`-scoped assertions**: every key resolves in `he` and in `ar`; `ar[key] === he[key]` for every key (**not** "non-empty"); no value matches the **three-term** `/נשלח|תישלח|בדרך/` (⚠ **not** the `HE_F33`-scoped five-term form — «הודעה» is in the approved `sos.error.noteTooLong`); no value contains a literal digit.
4. **Do not renumber or "tidy" anything else in `i18n.test.ts`.** Two `it(` blocks already both claim *"resolves the eleventh nav item"* after F53 landed. It is a shipped inconsistency, it is not F37's, and touching it puts an unrelated edit on this PR's diff.
5. **`MAX_SOS_NOTE_LENGTH` is mirrored** through the existing `id="manage-floor"` param in `test_frontend_constant_parity.py` — one name added to one tuple. **`ESCALATION_AFTER` and `STALLED_AFTER` are NOT**, because the client never computes them and, after rule 5, carries no number for them either.
6. **`vite.config.ts` and `scripts/qa-greps.sh` need no change** — every route's second path segment is `floor`, and this deck adds no formatter (`jerusalemTime` already sets `timeZone`).
