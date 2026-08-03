# Copy deck — F41 Atelier alteration tickets + kanban (`apps/manage`, `AtelierSection` and the section «תפירה»)

**Date**: 2026-08-03 · **Status**: **DRAFTED under the approved register, self-approved with the design gate** — Interview **Q2** named only F34's board and F42's capacity matrix as novel patterns for this run (`LOOP-STATE.md` `rulings_2026_07_31`), and a board of `Card`s on F34's shipped shell is neither. **The Hebrew remains the user's to edit post-merge** — the F15 P-1/P-5, F34 and F57 precedent: a one-line `he.ts` / `ar.ts` edit after merge, never a rebuild. Console copy, not a customer-facing SMS, so there is no counsel gate · **Owner of the Hebrew: the user** · **Consumes**: `.planning/specs/alteration-tickets.md` (**D1–D19**, above all **D16–D18**) and `design.md` in this directory · **Lands in**: `Frontend/apps/manage/src/i18n/he.ts` (`nav.atelier` + a new `atelier.*` namespace) **and `…/i18n/ar.ts`**, same keys, Hebrew standing in untranslated.

**F41 adds no SMS template, sends no message, queues no scheduled message and touches no `comms_templates.py` body.** There is no §SMS section in this deck and there cannot be one: every verb in this feature writes a timestamp, a column or a row and tells nobody. Stated because «נודיע לתופרת» is exactly the sentence a well-meaning editor adds to an assign cue — and it would be a **lie**, not merely a register slip.

**Four of these strings correct a proposal in the spec rather than transcribing it**, and each is recorded in `design.md` §11 rather than folded in silently:

| | What D18 proposed | What ships | Where |
|---|---|---|---|
| **F-10** | `atelier.cue.advanced` «{{name}} — הועבר ל{{stage}}.» | «{{name}} — שלב חדש: {{stage}}.» | §4 |
| **F-10** | `atelier.cue.undone` «{{name}} — הוחזר ל{{stage}}.» | «{{name}} — חזרה לשלב: {{stage}}.» | §4 |
| **F-10** | `atelier.cue.assigned` «{{name}} — שויך ל{{seamstress}}.» | «שויך ל{{seamstress}}.» — one name, not two | §4 |
| **F-5** | «reuse a subject-named shipped key» for the outage | `atelier.loadFailed` is **declared**, because no shipped key names this subject | §6 |

**And two keys the spec's D18 table does not list are added, because without them the board fails WCAG 4.1.2 on a 30-card column**: `atelier.skipCommitAria` and `atelier.assignCommitAria` (§3.1). D18 gives a disambiguating `aria` name to the two `<Select>`s and to «לשלב הבא» / «ביטול שלב» / «עריכה» / «מחיקה», and to neither of the two **commit `Button`s** — which are per-card controls with a fixed label exactly like the others.

## 0. The rules this deck is written under — hard constraints, not preferences

1. **Zero exclamation marks** (pre-decided #5). Mechanically checkable, and `__tests__/i18n.test.ts:397-399` already reads for it.
2. **Never claim, promise or hedge that a message was sent, in any tense.** `i18n.test.ts:401-402` rejects `/נשלח|תישלח|בדרך/` in any selected value. Trivially satisfied here — F41 notifies nobody — and stated anyway. ⚠ Note the third alternative, «בדרך», is the one a copy editor would reach for innocently («השמלה בדרך»), and it is banned in this bundle whatever it means.
3. **The board states, it does not reassure.** Every string is a fact, and the ones about time have a time on them. No «הכל תקין», no «מעולה», no encouragement. A seamstress reads this screen fifty times a shift and warmth at that frequency is noise.
4. **Freshness is claimed weakly and honestly.** «עודכן 14:07» says *this was true at 14:07*. Nothing anywhere says «בזמן אמת» or «חי» — the board polls, and a claim it cannot keep even for one interval is worse than the truth.
5. **No string names or implies a retry interval** (F34's rule 9, inherited through `usePoll`'s backoff). Consecutive failures stretch the interval 5 s → ~60 s, so «הלוח יתעדכן מיד» is true at tick 1 and false by tick 5. The stale copy states **what is unknown**, never **when it will be known**, and the three card-level errors name the **event** («בעדכון הבא»), never a duration.
6. **The 403 body is generic by design and may not be made specific** (F34's rule 10). `NotAuthorizedError` ships one body for every unadmitted role so a probe cannot learn which roles exist. Naming a role, or saying what changed, would be an invention the server never made — and on the demotion path it would be the product telling a staffer she was demoted, which is her manager's sentence to say, not a screen's.
7. **Status and urgency are carried by WORDS.** The stage is the column heading; overdue is «באיחור» inside a `Badge` whose colour is reinforcement only (`design.md` §2.4). **No emoji, no dots, no glyphs anywhere** — an emoji is announced by a screen reader with a name this product did not choose and cannot translate, and the console ships no icon vocabulary at all.
8. **One spelling per fact.** Where two surfaces in this feature say the same thing about the same thing, they share a key: the intake CTA and the create dialog's title are both `atelier.newTicket`; the delete card button and the confirm dialog's confirm are both `atelier.delete`; the dialog's dismiss and the confirm's dismiss are both `atelier.form.cancel`. Two byte-identical strings under two keys is how a console ends up spelling one fact two ways the day somebody edits one of them.
9. **Every value is a real string.** No `…`-as-placeholder, no Lorem, nothing to be filled in later. The one `…` in this deck is inside `atelier.loading`, where it is the content.
10. **The `ar` column is the approved Hebrew, standing in untranslated** (Interview Q3 / pre-decided #47 / the 2026-07-31 languages ruling), and it is **never an empty string**: i18next's `returnEmptyString` default renders `""` rather than falling back, so a premature switch would blank the page instead of showing Hebrew. `lng` stays `"he"`, `fallbackLng` stays `"he"`, no switcher ships.
11. **⚠ NO INTERPOLATION IN THIS DECK IS NAMED `count`.** The column heading interpolates **`{{total}}`**. `count` is i18next's plural-resolution trigger: passing it makes the translator look for `key_one` / `key_two` / `key_many` / `key_other` before the base key, so a bundle with only the base key resolves through a fallback path rather than directly. It works today and it is one library upgrade away from not. Hebrew agreement is why the string carries no noun at all — `design.md` **F-3**.

**96 keys invented, 0 reused.** `nav.atelier` plus 95 under `atelier.*`. F57 reused four shipped keys and F41 reuses none — not an oversight: no shipped key names *this* subject. `staff.loadFailed` is the staff list, `board.*` names a screen, and the atelier's own namespace is what F57's **F-10** rule (*reuse a key whose namespace names its subject*) actually points at here. `design.md` **F-5**. Three of the 96 are reused **within** this deck rather than re-declared, per §0 rule 8 (`atelier.newTicket` as CTA and create title, `atelier.delete` as card trigger and confirm, `atelier.form.cancel` as both dialogs' dismiss), so the number of **rendered** strings is larger than the number of keys.

⚠ **«נשלח» appears three times in this file and zero times in a value.** It is in §0 rule 2, in `atelier.stage.delivered`'s rationale and in §9's check row — all three explaining why the fifth stage is «נמסר». `i18n.test.ts:401-402` reads **values**, so the guard is clean; a reader grepping this deck rather than the bundle will find them and should not report them.

---

## 1. Navigation and section chrome

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `nav.atelier` | The **thirteenth** console nav row, rendered for owner / shift_manager / seamstress, inserted immediately after `floor` (`design.md` §0 — which is the same slot as "after «לוח היום», before «צוות»" in the owner's filtered list). One word, because the console's nav rows are one or two words each and it sits beside «צוות» and «לקוחות». «תפירה» — the craft — not «תיקונים» (repairs, which reads as fixing a mistake) and not «אטלייה» (a transliteration the boutique does not say out loud) | תפירה | תפירה | DRAFTED |
| `atelier.heading` | The section `h2`. Definite where the nav row is bare, because a heading names the thing on screen while a nav row names a destination — F57's `nav.floor` / `floor.heading` split, in the other direction. «לוח» is the word every other string in this deck uses for this surface, so the pause, the idle stop and the two card errors all agree with it | לוח התפירה | לוח התפירה | DRAFTED |
| `atelier.newTicket` | The intake CTA above the columns, **and** the create dialog's title (§0 rule 8). `Button variant="primary"` — the one primary on the screen. «כרטיס חדש», not «הוספת כרטיס»: the thing being made is a card, and the shortest true noun phrase is what fits under a thumb at 375 | כרטיס חדש | כרטיס חדש | DRAFTED |

## 2. The freshness row and the SC 2.2.2 mechanism

**Ten of this deck's strings are byte-identical to F34's `board.*` and F57's `floor.*` equivalents and are still declared separately**, which is a deliberate cost recorded as `design.md` **F-9**. F57's own **F-9** predicted this PR as the one where a shared `poll.*` namespace becomes worth the rename, and the rename is still declined for the reason that has not changed: it would edit `BoardSection`'s and `FloorPanel`'s i18n, and both components must pass **unedited** — which is the only thing separating a faithful fourth `usePoll` consumer from a subtly different one.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.updatedAt` | The freshness claim at the row's inline-end. Changes **only when a fetch succeeds**, so it is a claim the board can keep. Past tense on purpose | עודכן {{time}} | עודכן {{time}} | DRAFTED — `{{time}}` is `jerusalemTime()`, `HH:MM`, inside `<bdi dir="ltr">` |
| `atelier.staleAt` | Replaces `updatedAt` after a failed tick, in `--color-warning-text font-semibold`. The cards are still on screen and still correct as of that time — which is exactly why this must be legible rather than muted: plausible-looking data beside a grey notice is what gets scanned past | אין עדכון מאז {{time}} | אין עדכון מאז {{time}} | DRAFTED |
| `atelier.staleBody` | The line under it. Says what is unknown, not what is wrong — the board cannot tell a dead wifi from a dead server. No apology, no «אנא», **no interval** (§0 rule 5) | ייתכן שהמידע אינו עדכני. | ייתכן שהמידע אינו עדכני. | DRAFTED |
| `atelier.refresh` | The retry button, in the stale state and the first-load failure. **Never** rendered while paused or idle-stopped — the resume control is the affordance there, and «רענון» beside «חידוש» is two Hebrew words a hurried reader will not tell apart | רענון | רענון | DRAFTED |

### 2.1 Pause / resume and the idle stop — WCAG 2.0 SC 2.2.2, a legal item

**Eight keys, and at zero of them the product ships green in CI and non-conformant in law**, because **axe has no rule for SC 2.2.2**. This is the **third** auto-updating surface in the console.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.pause` | The control's visible label while the board is updating. **Identical to the board's and the floor panel's on purpose**: one product vocabulary, and a staffer must not have to learn that «השהיה» and «עצירה» are the same act. Not «עצור» (a stop, and this is reversible in one tap), not «הקפאה» (a freeze implies the data froze; the data is fine, the *fetching* stopped) | השהיה | השהיה | **APPROVED** (spec D17) |
| `atelier.pauseAria` | Its accessible name — it must say **which** region it stops, because two other pause controls exist in this console with the same visible label. The `—` shape is the shipped one (`board.pauseAria`, `floor.pauseAria`), and it **starts with the visible label** so WCAG 2.5.3 label-in-name holds: «השהיית» would be a different word form and a speech-input user saying «השהיה» would match nothing (F57's **F-2**) | השהיה — לוח התפירה | השהיה — לוח התפירה | **APPROVED** (spec D17) |
| `atelier.resume` | The same control once stopped — **one button whose name changes**, not two buttons, and not `aria-pressed`. Not «רענון»: that word is taken above for the one-shot retry, and the two acts differ (one fetch now vs. start the beat again) | חידוש | חידוש | DRAFTED |
| `atelier.resumeAria` | Same rule, same `—` shape | חידוש — לוח התפירה | חידוש — לוח התפירה | DRAFTED |
| `atelier.pausedAt` | Replaces `updatedAt` at the inline-end whenever the loop is stopped, in the **identical** `--color-warning-text` escalation `staleAt` gets, for the identical reason: a board *she* paused is easier to forget than one that broke. Serves both the manual pause and the idle stop; the body line below says which | מושהה · עודכן {{time}} | מושהה · עודכן {{time}} | DRAFTED — `{{time}}` inside `<bdi dir="ltr">` |
| `atelier.paused` | The body line after a **manual** pause. States the consequence, does not apologise for it and does not thank her for it — she asked for this. Names «לוח התפירה» rather than «הלוח», because `board.paused` already owns that word one section over | העדכון מושהה. לוח התפירה לא יתעדכן עד לחידוש. | העדכון מושהה. לוח התפירה לא יתעדכן עד לחידוש. | DRAFTED |
| `atelier.idleStopped` | The body line after the **idle** stop. Names the cause, because the difference between "I paused this" and "this paused itself" is the whole difference between a control and a bug — **and names its own REGION**, F57's **F-4** generalised. `board.idleStopped` and `floor.idleStopped` both ship, all three write into a `role="status"` region, and all three idle windows are reset by the same global listeners in `usePoll`. This console renders one section at a time so the collision is rarer here — the string still names its region, because the reason is a rule and not a coincidence | עדכון לוח התפירה הופסק אחרי {{minutes}} דקות ללא פעילות. | עדכון לוח התפירה הופסק אחרי {{minutes}} דקות ללא פעילות. | DRAFTED — `{{minutes}}` inside `<bdi dir="ltr">`; the value is `IDLE_STOP_MINUTES` from `usePoll`, = 10 |
| `atelier.resumed` | The announced cue on resume, in the existing `role="status"` region. Not symmetry: on resume the button's own accessible name flips, and a screen reader does **not** reliably re-announce the name of a control that is already focused — so without this string the one confirmation a sighted user gets for free is denied to the user 2.2.2 exists for | העדכון חודש. | העדכון חודש. | DRAFTED |

**Declined: a frequency picker.** 2.2.2 is satisfied by *any one* of pause / stop / hide / control-frequency, and a picker is a settings surface, a persisted preference, a second constant and three more strings for a criterion one button closes.

## 3. The board's structure — the rail, the five stages, the counts

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.railAria` | The `aria-label` on the in-page stage rail's `<nav>` — a **second** navigation landmark on a page that already has the shell's, so it must be named or a screen-reader user cycling landmarks lands on two things both called "navigation". Names the act, not the thing: these are five links that move you | מעבר לשלב | מעבר לשלב | DRAFTED — `aria-label` only, never rendered |
| `atelier.stageCount` | The rail chip **and** the column `<h3>` — one string, one source, two renderings (`design.md` §1.1). ⚠ **`{{total}}`, never `{{count}}`** (§0 rule 11). ⚠ **And no noun**: «{{total}} כרטיסים» is wrong at 1 and wrong at 2 (Hebrew takes a dual), and doing it properly needs four i18next plural suffixes per string in two bundles — while the `<ul>`'s own list role already announces the item count to the reader the noun was for. `design.md` **F-3** | {{stage}} · {{total}} | {{stage}} · {{total}} | DRAFTED — `{{total}}` inside `<bdi dir="ltr">`; `{{stage}}` is one of the five below and needs no isolation |
| `atelier.stage.intake` | Column 1. The garment is in the boutique and nothing has been done to it. «התקבל» — received. Not «חדש» (which dates rather than describes) and not «קליטה» (a process word for the desk, not a state of the dress) | התקבל | התקבל | **APPROVED** (spec D18) |
| `atelier.stage.inProgress` | Column 2. Someone is sewing. «בעבודה» is what a workroom says out loud; «בתהליך» is a project-management word | בעבודה | בעבודה | **APPROVED** (spec D18) |
| `atelier.stage.qc` | Column 3 — **the stage the E9 brief added and pre-decided #39 did not have**. The work is done and someone is checking it. «בקרה» — inspection. Not «בדיקה» (which reads as trying it on) and not «איכות» alone | בקרה | בקרה | **APPROVED** (spec D18) |
| `atelier.stage.ready` | Column 4. Finished and waiting for the bride. «מוכן» — masculine, agreeing with «כרטיס», which is what the column is a column of | מוכן | מוכן | **APPROVED** (spec D18) |
| `atelier.stage.delivered` | Column 5. The bride has it. «נמסר» — handed over. ⚠ **Deliberately not «נשלח»**, which is both wrong (nothing is shipped; she collects) and **banned outright by `i18n.test.ts:401-402`**. Nothing in this product delivers anything to anybody | נמסר | נמסר | **APPROVED** (spec D18) |
| `atelier.emptyColumn` | Inside a column with no cards when the board is not empty. The four other columns are the context that makes an empty one legible rather than broken | אין כרטיסים בשלב זה | אין כרטיסים בשלב זה | DRAFTED |

### 3.1 The per-card controls — and why every one of them carries a name with the bride in it

**A 30-card board otherwise exposes 30 controls all named «לשלב הבא», 30 more all named «העברה» and 30 more all named «שיוך».** A screen-reader user pulling up the control list, or a speech-input user saying the label, then cannot address a specific ticket — WCAG 4.1.2 and 2.4.6. Every per-card control therefore carries an `aria-label` that **starts with its visible label** (WCAG 2.5.3 label-in-name) and adds the bride's name; `i18n.test.ts` asserts the containment for every pair rather than trusting it.

⚠ **`@boutique/ui`'s `Select` derives its accessible name SOLELY from its required `label` prop**, which it renders as a visible `<label htmlFor>` — there is no name-override path in its API. Both selects therefore spread an `aria-label` onto the `<select>` through `...rest`.

⚠ **An `aria-label` takes no markup**, so `{{name}}` in every `*Aria` key below interpolates plainly, with no `<bdi>` and no helper. There is nothing rendered to reorder.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.advance` | **The primary control**, `Button variant="secondary"`, on every card that can move. Names the destination generically because the destination is whatever comes next — spelling it («העברה לבקרה») would be five strings and would change under the reader as the card moves | לשלב הבא | לשלב הבא | **APPROVED** (spec D18) |
| `atelier.advanceAria` | Its per-card name | לשלב הבא — {{name}} | לשלב הבא — {{name}} | **APPROVED** — `aria-label` only |
| `atelier.skip` | The **visible `<label>`** of the skip `<Select>`, rendered above it. Offers only stages strictly later than the current one, and renders only when two or more exist (`design.md` §2.3) | העברה לשלב | העברה לשלב | **APPROVED** (spec D18) |
| `atelier.skipAria` | Its per-card name, containing the visible label | העברה לשלב — {{name}} | העברה לשלב — {{name}} | **APPROVED** — `aria-label` only |
| `atelier.skipCommit` | The **sibling commit `Button`**. ⚠ Selection and commit are separate controls because a *closed* native `<select>` fires `change` on every arrow keypress — an onChange-mutating skip would write three timestamps and three audit rows while a keyboard user was still choosing (WCAG **3.2.2 On Input**, Level A; `design.md` §3.2) | העברה | העברה | **APPROVED** (spec D18) |
| `atelier.skipCommitAria` | ⚠ **NOT IN D18's TABLE — added here.** Thirty commit buttons all named «העברה» is the same 4.1.2 dead end D18 fixes for the `<Select>` beside them | העברה — {{name}} | העברה — {{name}} | DRAFTED — `aria-label` only |
| `atelier.undo` | The undo (spec D4), `Button variant="ghost"`. Absent on an `intake` card, because `intake` cannot be undone. «ביטול שלב» — it cancels *a stage*, not the ticket, and the distinction is the whole reason «מחיקה» is a different word | ביטול שלב | ביטול שלב | **APPROVED** (spec D18) |
| `atelier.undoAria` | Its per-card name | ביטול שלב — {{name}} | ביטול שלב — {{name}} | **APPROVED** — `aria-label` only |
| `atelier.assignLabel` | The **visible `<label>`** of the assign `<Select>` — owner and shift manager only. ⚠ **Not spec D18's «שיוך»**: the commit `Button` beside it is also «שיוך», so two controls in one card would carry the same accessible name — WCAG 4.1.2, and a speech-input user saying «שיוך» could not tell them apart. The `<Select>` names **what is being chosen** and the `Button` names **the act**, which is also how the skip pair reads | תופרת | תופרת | DRAFTED — a copy correction to D18, `design.md` §11 |
| `atelier.assignAria` | Its per-card name, containing the revised visible label | תופרת — {{name}} | תופרת — {{name}} | DRAFTED — `aria-label` only |
| `atelier.assignCommit` | The **sibling commit `Button`**. Same 3.2.2 argument as `skipCommit`: the `<Select>` sets draft state and issues nothing | שיוך | שיוך | **APPROVED** (spec D18) |
| `atelier.assignCommitAria` | ⚠ **NOT IN D18's TABLE — added here**, same reason as `skipCommitAria` | שיוך — {{name}} | שיוך — {{name}} | DRAFTED — `aria-label` only |
| `atelier.claim` | A **seamstress's** single control on an unassigned ticket — she takes it. `Button variant="secondary"`. Two syllables, because it lives under a thumb. Not «שייך לי» (an administrative act on a record) | לקחת | לקחת | **APPROVED** (spec D18) |
| `atelier.claimAria` | Its per-card name | לקחת — {{name}} | לקחת — {{name}} | **APPROVED** — `aria-label` only |
| `atelier.release` | The mirror, on a ticket assigned to her. `Button variant="ghost"` — the reversible half of the pair, exactly as «חזרה» is to «להפסקה» | לשחרר | לשחרר | **APPROVED** (spec D18) |
| `atelier.releaseAria` | Its per-card name | לשחרר — {{name}} | לשחרר — {{name}} | **APPROVED** — `aria-label` only |
| `atelier.edit` | Reopens the dialog in edit mode. `Button variant="ghost"`. Owner and shift manager on any ticket; a seamstress on **her own** only — and which control renders is cosmetics, the service is the control | עריכה | עריכה | **APPROVED** (spec D18) |
| `atelier.editAria` | Its per-card name | עריכה — {{name}} | עריכה — {{name}} | **APPROVED** — `aria-label` only |
| `atelier.delete` | The card's destructive trigger, `Button variant="danger"` — **and the confirm dialog's confirm button** (§0 rule 8). Owner and shift manager only. There is no un-delete | מחיקה | מחיקה | **APPROVED** (spec D18) |
| `atelier.deleteAria` | Its per-card name | מחיקה — {{name}} | מחיקה — {{name}} | **APPROVED** — `aria-label` only |

**No string for "you may not do this".** A seamstress on a colleague's ticket sees **no controls at all** — no disabled button, no lock, no explanation (`design.md` §2.3). The absence is cosmetics; the control is the server's D3/D9/D10 checks, which is why there is nothing here to word.

## 4. The card's own facts, and the effort bands

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.dueDate` | The due line, on **every** card — it is the priority key the whole epic subtracts from. Escalates to `--color-danger font-semibold` when overdue, which is the second of the two text signals. «יעד» — the target date — not «תאריך» alone (which says nothing) and not «למסירה» (which would put a delivery word on four columns that have not delivered anything) | יעד {{date}} | יעד {{date}} | DRAFTED — `{{date}}` is `plainDate()`, `d.m.yyyy`, inside `<bdi dir="ltr">` |
| `atelier.overdue` | The `Badge variant="danger"` word in the name row. **The word is the signal and the colour is reinforcement** — the E9 Risks name colour-only urgency as this epic's hard accessibility case. Never rendered on a delivered ticket: a garment delivered late is history, not a thing to chase | באיחור | באיחור | **APPROVED** (spec D18) |
| `atelier.unassigned` | On a card with no seamstress, **and** as the release option in the elevated assign `<Select>`. Muted words, not a red flag — unassigned is the normal state of a ticket ten seconds old, and it is what a seamstress is looking for when she claims | לא משויך | לא משויך | **APPROVED** (spec D18) |
| `atelier.assigneeInactive` | On a card whose assignee came back with `assignable: false` — her role was changed or she was retired by F51's staff CRUD, which knows nothing about this table (spec D9). **The flag is on the wire**, so this is a fact and not an inference from absence, and surfacing it is the signal a manager needs to reassign | תופרת שאינה פעילה | תופרת שאינה פעילה | **APPROVED** (spec D18) |
| `atelier.band.thirtyMin` | Q13's first band. The word, not the number — the number lives in `bandOption` where the choice is made | חצי שעה | חצי שעה | **APPROVED** (spec D18) |
| `atelier.band.oneHour` | Q13's second band, **and the intake form's default** — the middle-low value, because a default of «יום מלא» inflates every estimate in the boutique and «חצי שעה» deflates it | שעה | שעה | **APPROVED** (spec D18) |
| `atelier.band.twoHours` | Q13's third | שעתיים | שעתיים | **APPROVED** (spec D18) |
| `atelier.band.halfDay` | Q13's fourth. ⚠ The band whose tenant mapping is most likely to be wrong — *"'half-day' is not 240 minutes in a boutique whose shifts are six hours"* (the E9 brief), and F41 ships **no editor** for the mapping | חצי יום | חצי יום | **APPROVED** (spec D18) |
| `atelier.band.fullDay` | Q13's fifth | יום מלא | יום מלא | **APPROVED** (spec D18) |
| `atelier.bandOption` | The `<option>` label in the intake form's effort `<Select>` — **the word AND its tenant-resolved minutes**. This is the whole of `design.md` §7.2: F41 reads the mapping and F42 owns the editor, so showing the number at the moment the estimate is made is what lets an owner discover on day one that the platform thinks her half-day is four hours. ⚠ **An `<option>` takes no markup**, so no isolation helper is available — the string is built so the numeric run is **bracketed by Hebrew on both sides**, which is what makes the bidi resolution safe without markup. A string ending in the number would put a neutral run at the paragraph edge | {{band}} · {{minutes}} דק׳ | {{band}} · {{minutes}} דק׳ | DRAFTED |
| `atelier.effortMinutes` | The **card's** effort word when a stored `effort_minutes` matches no current band — a boutique re-tuned «חצי יום» after the ticket was estimated. Honest, and it is the visible consequence of D8's *"minutes persist, never the label"*: a ticket estimated under the old mapping must not be silently re-valued | {{minutes}} דק׳ | {{minutes}} דק׳ | DRAFTED — `{{minutes}}` inside `<bdi dir="ltr">` |

### 4.1 The announced cues — user-initiated only, and the naming rule

The `role="status"` region carries **nothing the poll produces** (spec D17, F34's D11). Every string below is the direct consequence of an activation, and `atelier.loading` fires once on a first load nobody else can trigger.

**A cue is spoken once per activation, and staying on screen is not speaking again.** No cue is cleared on a timer — once written it remains visible until the next one replaces it. That is only safe because the region is **written only when its value changes** (F34's **F-7**): re-asserting an unchanged string into `role="status"` still replaces the text node and still announces, so a five-second repaint that "kept the cue the same" would read it aloud every five seconds until the end of the shift.

**⚠ THE NAMING RULE, and it is what makes every one of these fit the shipped one-value helper: a cue names the TICKET only when the ticket moved out from under the user; when the card stays put, focus is the referent and the cue names only the new value.** An advance moves the card to another column and the undo moves it back, so both name the bride and the destination; an assign leaves the card exactly where it is with focus still on it, so it names only the seamstress. A create closes a dialog that returns focus to «כרטיס חדש» — not to the new card — so it names the bride. A delete removes the card and sends focus to a column heading, so it names the bride.

**What that buys mechanically**: every cue has **at most one interpolated *user* value**, so `isolateBidi(cueText, cue.name)` and the shipped `{ text, name }` state shape (`FloorPanel.tsx:428`) work unmodified and **no second helper is invented**. `{{stage}}` needs no isolation — it is our own Hebrew vocabulary from §3, not user data.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.loading` | Carried by the cue region on the **first** load only. The shipped console announces nothing while loading; this section closes that for itself by reusing the region it already needs | טוען את לוח התפירה… | טוען את לוח התפירה… | DRAFTED |
| `atelier.cue.created` | After a successful intake. Names the bride because the dialog returned focus to «כרטיס חדש» and **not** to the new card, so this is the only thing that says which ticket was opened | {{name}} — נפתח כרטיס. | {{name}} — נפתח כרטיס. | DRAFTED — `{{name}}` in a bare `<bdi>` |
| `atelier.cue.advanced` | After a successful advance or skip. ⚠ **THE SINGLE MOST IMPORTANT STRING IN THIS DECK**: for a sighted user the move is self-evident because the card is visibly in another column, and **for a screen-reader user this sentence IS the move**. The acceptance criterion asserts the region's *textContent* contains the bride's name and the stage word, not merely that it changed. ⚠ **Not D18's «הועבר ל{{stage}}»**: the five stage words are past-tense verbs and an adjective, and «ל» does not prefix them — «הועבר לבעבודה» is ungrammatical. The colon construction is word-agnostic, so a sixth stage can never break it (`design.md` **F-10**) | {{name}} — שלב חדש: {{stage}}. | {{name}} — שלב חדש: {{stage}}. | DRAFTED — a copy correction to D18 |
| `atelier.cue.undone` | After a successful undo — the card moves **back** a column. ⚠ **Not D18's «הוחזר ל{{stage}}»**, and this is the half where the grammar actually breaks in production: undoing `in_progress` returns the ticket to «התקבל», and «הוחזר להתקבל» is the commonest undo there is | {{name}} — חזרה לשלב: {{stage}}. | {{name}} — חזרה לשלב: {{stage}}. | DRAFTED — a copy correction to D18 |
| `atelier.cue.assigned` | After a successful assign or claim. ⚠ **Not D18's «{{name}} — שויך ל{{seamstress}}.»**: the card does not move on an assign, so focus is still on it and the ticket is already the referent — and naming both would put **two** user-supplied names in one string, which the shipped `isolateBidi(text, value)` cannot isolate without a second helper. Naming the new value alone is both the smaller string and the correct one | שויך ל{{seamstress}}. | שויך ל{{seamstress}}. | DRAFTED — `{{seamstress}}` in a bare `<bdi>`; a copy correction to D18 |
| `atelier.cue.released` | After a successful release. No interpolation at all — the card did not move, focus is on it, and there is no new value to name | השיוך בוטל. | השיוך בוטל. | **APPROVED** (spec D18) |
| `atelier.cue.deleted` | After a successful delete. Names the bride: the card is gone and focus is on a column heading, so nothing else can say which ticket left | {{name}} — הכרטיס נמחק. | {{name}} — הכרטיס נמחק. | **APPROVED** (spec D18) |

## 5. The intake / edit dialog

The dialog's **title in create mode is `atelier.newTicket`**, reused from §1 (§0 rule 8) — the CTA and the title name the same act.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.form.editTitle` | The dialog's title in edit mode | עריכת כרטיס | עריכת כרטיס | DRAFTED |
| `atelier.form.customerName` | The bride's name. **Create mode only** — a ticket opened for the wrong bride is a delete, not an edit (spec's `UpdateTicketRequest`), so in edit mode the customer renders as a static line and not a field | שם הלקוחה | שם הלקוחה | DRAFTED |
| `atelier.form.customerPhone` | Create mode only. The `(tenant, phone)` key every writer in this product identifies a bride by | טלפון | טלפון | DRAFTED — `dir="ltr"` on the field |
| `atelier.form.existingCustomer` | ⚠ Appears beside the phone field **the moment the phone parses to a customer whose stored name differs from what she typed**. `upsert` rewrites `customers.name` **unconditionally** (spec D6) and F53 now renders that name on a screen of its own, so a seamstress typing «מיכל» for a customer stored as «מיכל לוי» must not do that invisibly. `--color-warning-text`, not `--color-danger`: nothing is wrong, something is about to change | לקוחה קיימת — השם יעודכן ל{{name}}. | לקוחה קיימת — השם יעודכן ל{{name}}. | DRAFTED — `{{name}}` in a bare `<bdi>` |
| `atelier.form.dueDate` | The `DateField` label. Defaults to **empty, never to today** — a due date is the one field a hurried user must not be able to accept by not looking at it | תאריך יעד | תאריך יעד | DRAFTED |
| `atelier.form.pastDue` | ⚠ A **warning, never a block**, under the date field when the chosen date is already past. The server agrees: there is **no lower bound** and a past date is a 200 on create and on update (spec D5), and there is no `min` attribute. Pre-decided #40's advisory rule — *a dress that was due yesterday is exactly the ticket a boutique most needs to open*. The second sentence is what stops it reading as an error | התאריך שנבחר כבר עבר. אפשר להמשיך. | התאריך שנבחר כבר עבר. אפשר להמשיך. | DRAFTED |
| `atelier.form.effortBand` | The effort `<Select>`'s label. «הערכה» is the honest word — the E9 brief's central accepted risk is that these estimates are wrong, and a label reading «זמן עבודה» would state as fact what the whole epic treats as a guess | הערכת זמן | הערכת זמן | DRAFTED |
| `atelier.form.dress` | The dress `<Select>`'s label — the tenant's live catalog plus the option below | שמלה | שמלה | DRAFTED |
| `atelier.form.dressNone` | The `<option>` that reveals the free-text name field. An alteration is frequently on a gown the bride already owns, which has no catalog row at all (spec D6) — so this is the normal case, not the exception, and it is worded as a plain fact rather than as «אחר» | לא מהקטלוג | לא מהקטלוג | DRAFTED |
| `atelier.form.dressName` | The free-text field, revealed only by the option above. The server copies the name from `dresses` when a catalog dress is chosen, so this field and that choice are mutually exclusive by construction | שם השמלה | שם השמלה | DRAFTED |
| `atelier.form.dressSize` | Free text, never validated against `dress_variants` — a seamstress records what she measured («38, מותן מוקטן»), not a stock bucket | מידה | מידה | DRAFTED |
| `atelier.form.notes` | The `TextArea` label. ⚠ **This is the field most likely to hold a bride's measurements** (spec Risk 8), which is the most intimate data this platform will ever carry — and it is why the label is a neutral «הערות» rather than anything that invites them | הערות | הערות | DRAFTED |
| `atelier.form.notesHelp` | The `help` line under it. Says what the field is *for*, which is the work order the seamstress reads off the card — and the shipped `showCount` counter beside it is what makes `design.md` §2.2's "the board never truncates a note" honest, by putting the length in front of whoever is writing it | מה צריך לעשות בשמלה. | מה צריך לעשות בשמלה. | DRAFTED |
| `atelier.form.submitCreate` | The create dialog's confirm. Names the act, not «אישור» | פתיחת כרטיס | פתיחת כרטיס | DRAFTED |
| `atelier.form.submitEdit` | The edit dialog's confirm | שמירה | שמירה | DRAFTED |
| `atelier.form.cancel` | The dismiss on **both** dialogs (§0 rule 8), `Button variant="ghost"`. Esc and the backdrop do the same thing, and never the confirm | ביטול | ביטול | DRAFTED |

### 5.1 Field validation — refused before the request, and the server refuses the same things

Each rides its field's own `error` prop, which wires `aria-describedby` + `role="alert"` and flips the border to `--color-danger`. **The register is fix-this, so every one names what to do and none apologises.**

| Key | Raised by | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.form.error.customerName` | Empty, or over 80 characters | צריך שם לקוחה. | צריך שם לקוחה. | DRAFTED |
| `atelier.form.error.customerPhone` | `normalize_israeli_mobile` refuses it | מספר הטלפון אינו תקין. | מספר הטלפון אינו תקין. | DRAFTED |
| `atelier.form.error.dueDate` | Empty | צריך תאריך יעד. | צריך תאריך יעד. | DRAFTED |
| `atelier.form.error.dueDateHorizon` | Beyond `MAX_DUE_DATE_HORIZON_DAYS` (730) — a **typo fence**, not a policy about how far ahead a boutique may plan, so the copy names the shape of the mistake rather than quoting a number the client does not hold | התאריך רחוק מדי. כדאי לבדוק את השנה. | התאריך רחוק מדי. כדאי לבדוק את השנה. | DRAFTED |
| `atelier.form.error.dressName` | Over 200 characters | שם השמלה ארוך מדי. | שם השמלה ארוך מדי. | DRAFTED |
| `atelier.form.error.dressSize` | Over 40 characters | המידה ארוכה מדי. | המידה ארוכה מדי. | DRAFTED |
| `atelier.form.error.notes` | Over 500 characters | ההערות ארוכות מדי. | ההערות ארוכות מדי. | DRAFTED |

## 6. States

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.empty` | The `EmptyState` **title** on a board with no tickets at all. ⚠ **This is the first thing every new boutique sees on this screen**, so it is designed rather than blank: the five columns and the rail are replaced entirely (`design.md` §10 **P-2**), because five headings each reading «אין כרטיסים בשלב זה» is a wall of nothing that looks broken. «עדיין» is doing real work — it says *not yet*, not *not ever* | אין עדיין כרטיסי תפירה | אין עדיין כרטיסי תפירה | DRAFTED |
| `atelier.emptyBody` | The `EmptyState` **body** — and **the only place in the product where the five stages are taught in one sentence**. This is what the replaced columns would have taught at the cost of looking broken, delivered as a sentence instead. It must name all five, in order, in the same words the columns use, or a reader learns a vocabulary the board does not speak | כל כרטיס עובר חמישה שלבים: התקבל, בעבודה, בקרה, מוכן, נמסר. אפשר לפתוח את הכרטיס הראשון עכשיו. | כל כרטיס עובר חמישה שלבים: התקבל, בעבודה, בקרה, מוכן, נמסר. אפשר לפתוח את הכרטיס הראשון עכשיו. | DRAFTED — the `EmptyState`'s `action` is the shipped «כרטיס חדש» CTA, not a new key |
| `atelier.truncated` | Above the rail when the server hit `BOARD_TICKET_LIMIT`. ⚠ **The console never states the number** — the limit is server-only, the `truncated` flag is on the wire precisely so it stays that way, and a client that quoted 500 would be one constant away from lying. Ordering is `due_date` ascending, so what is missing is the **least** urgent, and the copy says so rather than leaving her to wonder which end was cut | מוצגים הכרטיסים הדחופים ביותר. כרטיסים רחוקים יותר אינם מוצגים כאן. | מוצגים הכרטיסים הדחופים ביותר. כרטיסים רחוקים יותר אינם מוצגים כאן. | DRAFTED |
| `atelier.loadFailed` | The **first** fetch failed and there is nothing on screen — the **outage** register: recoverable, unblaming, no technical words. ⚠ **Declared, not reused.** The spec's state table asks for a subject-named shipped key, citing F57's **F-10** — but F-10's rule is *reuse a key whose namespace names its **subject***, and no shipped key names this one: `staff.loadFailed` is the staff list and `board.*` names a screen. `atelier.*` **is** the subject namespace here, so declaring it is F-10 obeyed (`design.md` **F-5**) | לא הצלחנו לטעון את לוח התפירה כרגע. | לא הצלחנו לטעון את לוח התפירה כרגע. | DRAFTED |
| `atelier.sessionEnded` | A tick or a mutation answered **401** and **the loop stopped**. `role="alert"`. The session outlives a shift by design (`session_ttl_seconds` = 43200, no sliding renewal), so the realistic reader is a phone left on a bench overnight — a plain instruction, not an alarm. Word-for-word the board's and the floor panel's sentence, because it is the same fact | תוקף החיבור פג. צריך להתחבר מחדש. | תוקף החיבור פג. צריך להתחבר מחדש. | DRAFTED |
| `atelier.accessEnded` | A tick or a mutation answered **403** and the loop stopped — a mid-shift role change, or a staffer re-roled between the last tick and her tap. **Deliberately generic** (§0 rule 6): no role is named, nothing is said about what changed, and it does not claim the change is permanent — «כרגע» is doing real work, because a re-promotion restores the board. Points at a person rather than at a retry, because there is nothing here she can fix from this screen | אין הרשאה לצפות בלוח התפירה כרגע. לבירור אפשר לפנות לבעלת הבוטיק. | אין הרשאה לצפות בלוח התפירה כרגע. לבירור אפשר לפנות לבעלת הבוטיק. | DRAFTED |
| `atelier.reload` | The button beside **both** of the two above. Says what it does. On the 401 a reload lands on the login screen; on the 403 it lands on a console whose board answers 403 again — the honest behaviour of F31's *"a demotion bites on the very next request"*, recorded as F34's **F-10** and inherited, not papered over | רענון הדף | רענון הדף | DRAFTED |

## 7. Errors on a card — two new codes, one shared shape

**F41 adds exactly two error codes** (`SPEC_ERROR_CODES` set equality, spec D13), and **they are two and not one because the user's next move differs**: a garment moved on and she should look again; a person took it and the next tick will name her. Collapsing them into the shipped generic `CONFLICT` would make the console branch on a message string.

All three render **inside the card**, `role="alert" tabIndex={-1}`, `--color-danger`, and all three **name the event that repairs them and never a duration** (§0 rule 5).

| Key | Raised by | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.error.stageConflict` | **409 `TICKET_STAGE_CONFLICT`** — the ticket is not where her board last showed it. Either a colleague advanced it, or she is undoing a stage that a legal forward skip has already left behind (spec D3, D4). The remedy is to look again, which the next tick does for her | הכרטיס כבר התקדם. הלוח יתעדכן בעדכון הבא. | הכרטיס כבר התקדם. הלוח יתעדכן בעדכון הבא. | **APPROVED** (spec D18) |
| `atelier.error.alreadyAssigned` | **409 `TICKET_ALREADY_ASSIGNED`** — two seamstresses tapped «לקחת» on one ticket and she lost. Does **not** name the winner: the console does not have her name at the moment of the refusal, and the next tick renders it on the card | הכרטיס כבר משויך. הלוח יתעדכן בעדכון הבא. | הכרטיס כבר משויך. הלוח יתעדכן בעדכון הבא. | **APPROVED** (spec D18) |
| `atelier.error.notFound` | ⚠ **NOT IN D18's TABLE — added here.** **404 `NOT_FOUND`** — a mutation on a ticket deleted in the gap between the last tick and the tap (or, indistinguishably, another tenant's id, which RLS makes invisible). D13's error table lists the status and the code and D18 declares no string for it, so without this row the one reachable 404 on this surface falls through to `errorMessage(error)` and renders `main.py`'s **English** body in a Hebrew console. **Not terminal** — a ticket vanishing is a fact about the ticket, not about her access | הכרטיס כבר לא קיים. הלוח יתעדכן בעדכון הבא. | הכרטיס כבר לא קיים. הלוח יתעדכן בעדכון הבא. | DRAFTED |

## 8. The delete confirmation

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.deleteConfirmTitle` | The `Modal` title | מחיקת כרטיס | מחיקת כרטיס | **APPROVED** (spec D18) |
| `atelier.deleteConfirmBody` | The body. **Two sentences, and the second is the whole reason this dialog exists**: there is no un-delete (spec Risk 6), so a ticket removed by mistake is recoverable only through `psql`. It names the bride because a board-level sentence names nobody, and the confirm is being read at the moment the wrong card might be the focused one | הכרטיס של {{name}} יימחק מהלוח. לא ניתן לשחזר אותו. | הכרטיס של {{name}} יימחק מהלוח. לא ניתן לשחזר אותו. | **APPROVED** (spec D18) — `{{name}}` in a bare `<bdi>` |

The confirm button is `atelier.delete` and the dismiss is `atelier.form.cancel`, both reused (§0 rule 8). **`api.deleteTicket` is not called until the confirm is activated** — its own acceptance line and its own test.

---

## 9. Register check — the mechanical pass

| Rule | Result |
|---|---|
| Exclamation marks in this deck | **0** |
| Values matching `/נשלח\|תישלח\|בדרך/` (`i18n.test.ts:401-402`) | **0** — and the near miss is deliberate: the fifth stage is «נמסר», never «נשלח». Nothing in F41 sends anything, so any such string would also be a lie |
| Strings claiming the board is realtime / live / instant | **0** — «עודכן {{time}}» is past tense by construction; «בזמן אמת» appears nowhere |
| Strings naming or implying a **retry interval** (§0 rule 5) | **0** — `staleBody` states what is unknown; all three card errors name the next **event**, never a duration; nothing anywhere says «חמש שניות» |
| Strings naming a **role**, or saying what changed, on the 403 (§0 rule 6) | **0** — `accessEnded` says only that there is no permission, that it is «כרגע», and who to ask |
| Strings for the SC 2.2.2 mechanism (spec D17) | **8** — `pause` / `pauseAria` / `resume` / `resumeAria` / `pausedAt` / `paused` / `idleStopped` / `resumed`. **At zero the product ships green in CI and non-conformant in law**, because axe has no SC 2.2.2 rule — and this is the **third** such surface in the console |
| Per-card controls without a disambiguating accessible name | **0** — ten control keys, ten `*Aria` siblings, **two of which D18 omits** (`skipCommitAria`, `assignCommitAria`) and this deck adds |
| `*Aria` values that do not contain their visible label (WCAG 2.5.3) | **0** — every one begins with the visible string and adds « — {{name}}». Asserted in `i18n.test.ts`, not trusted |
| Controls sharing an accessible name within one card | **0** — ⚠ D18's `assignLabel` «שיוך» collided with `assignCommit` «שיוך»; the `<Select>`'s label is revised to «תופרת» (§3.1) |
| Emoji, glyphs or icon characters anywhere in a value (§0 rule 7) | **0** |
| Statuses expressible without their word | **0** — the stage is the column heading; overdue carries «באיחור» **and** an escalated due line; unassigned carries «לא משויך»; paused carries «מושהה», a body line and the control's own label flip |
| Strings that blame the staffer | **0** — `staleBody` states what is unknown, `loadFailed` is first-person-plural and unblaming, `pastDue` explicitly ends «אפשר להמשיך» |
| Money words, ILS amounts, deposit words | **0** — deliberately, per the E9 brief and Interview Q1's money fence. There is no `Price` on this screen |
| Photo, image or attachment words | **0** — out of scope by the same brief |
| Measurement-inviting words in a field label | **0** — `notes` is «הערות» and its help line says «מה צריך לעשות בשמלה», not «מידות». `notes` is the column spec Risk 8 hands to F20 |
| Reassurance / encouragement copy | **0** — §0 rule 3 |
| Placeholders, Lorem, `…`-as-content | **0** — the one `…` is inside `atelier.loading`, where it is the content |
| `ar` values that are empty strings | **0** — every row carries the Hebrew as its placeholder. `i18n.test.ts:406-415` is the one guard that catches this **without** the `HE_F41` fold |
| Keys that overwrite or edit a shipped `board.*`, `floor.*`, `staff.*` or `customers.*` key | **0** — every key in this deck is new and under `atelier.*` (plus `nav.atelier`). Ten values are byte-identical to shipped ones under other namespaces and are **declared, not reused** — `design.md` **F-9** |
| Values for a stage or a state the wire cannot carry | **0** — five stage words for five columns, three card errors for three reachable statuses, and no string for a sixth of anything |
| Strings a **poll tick** can cause to be announced | **0** — ten strings ever enter the live region (`loading`, six cues, `paused`, `idleStopped`, `resumed`) and none is reachable from a tick: `loading` fires once before any tick, six are the direct consequence of an activation, and the idle stop is the consequence of her *not* activating anything. The region is written only when its value changes, so a repaint carrying an unchanged cue produces zero mutation records (F34's **F-7**) |
| Interpolations of a **user-supplied** value, per string | **≤ 1 everywhere** — which is what lets the shipped `isolateBidi(text, value)` and the shipped `{ text, name }` cue state work unmodified and **no second helper be invented** (§4.1's naming rule) |
| Interpolations named `count` | **0** — the column heading uses `{{total}}` (§0 rule 11) |
| Interpolations needing a bidi helper that cannot take one | **1, and it is safe by construction** — `atelier.bandOption` renders inside an `<option>`, which takes no markup, so the numeric run is **bracketed by Hebrew on both sides** rather than isolated (§4). The assign `<select>`'s options carry Hebrew display names and need no treatment at all |
| Helper chosen per interpolation, not per string (F57's **F-11**) | ✓ — `{{time}}`, `{{minutes}}`, `{{total}}` and `{{date}}` are **numeric** runs and go through `isolateLtr` (`<bdi dir="ltr">`); `{{name}}` and `{{seamstress}}` are **display names** and go through `isolateBidi` (bare `<bdi>`), because `dir="ltr"` on «נועה לוי» reverses its words and *looks deliberate*. `{{stage}}` and `{{band}}` are **our own Hebrew vocabulary** and need neither. Every `*Aria` key interpolates plainly — an `aria-label` takes no markup at all |
| **`HE_F41` declared but not spread into `HE`** | ⚠ **THE ONE FAILURE THAT WOULD MAKE THIS WHOLE TABLE VACUOUS.** `HE` is a hand-assembled union (`i18n.test.ts:48`) and **four** shipped guards iterate it — the resolve check, both register guards and the `ar` parity guard, which **does exist and has since F52**. A block that is declared and not folded in is skipped **silently and greenly**, which the file records in its own words for F52 and which F53 asserts against explicitly. F41 asserts the fold itself: `expect(HE.map(([key]) => key)).toContain("nav.atelier")` |
