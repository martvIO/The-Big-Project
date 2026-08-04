# Copy deck — F42 Seamstress capacity + load bars + balanced assignment (`apps/manage`, `SeamstressPanel` inside the shipped «תפירה» section)

**Date**: 2026-08-04 · **Status**: **DRAFTED under the approved register, self-approved with the design gate** — Interview **Q2** named F42's capacity matrix as a novel pattern and `LOOP-STATE.md` `rulings_2026_07_31` self-approves it: *"build through their Q2 novel-pattern gates without pausing."* **The Hebrew remains the user's to edit post-merge** — the F15 P-1/P-5, F34, F57 and F41 precedent: a one-line `he.ts` / `ar.ts` edit after merge, never a rebuild. Console copy, not a customer-facing SMS, so there is no counsel gate · **Owner of the Hebrew: the user** · **Consumes**: `.planning/specs/seamstress-capacity.md` (**D1–D16**, above all **D9**, **D10** and **D15**) and `design.md` in this directory · **Lands in**: `Frontend/apps/manage/src/i18n/he.ts` (`atelier.capacity.*`, `atelier.settings.*`, one `atelier.cue.*`) **and `…/i18n/ar.ts`**, same keys, Hebrew standing in untranslated.

**F42 adds no SMS template, sends no message, queues no scheduled message and touches no `comms_templates.py` body. Nothing in this feature notifies anybody.** There is no §SMS section in this deck and there cannot be one. Stated because **«נודיע לתופרת» is exactly the sentence a well-meaning editor would add to an overload cue** — and it would be a **lie** as well as a red under `i18n.test.ts:401-402`.

**Four of these strings correct or complete a proposal in the spec rather than transcribing it**, and each is recorded in `design.md` §12 rather than folded in silently:

| | What the spec's D15 table has | What ships | Where |
|---|---|---|---|
| **F-6** | one `useDefault` control in the dialog **footer**, submitting `null`, with no help line | the control moves into the **body** and CLEARS the field; **two** help strings, because «ברירת מחדל של הבוטיק» is a lie on a tenant that has none | §3 |
| **F-6** | *(no confirm-button key for the capacity dialog at all)* | `atelier.capacity.submit` is **declared** | §3 |
| **F-11** | *(nothing about D4's silent relabel)* | `atelier.settings.bandsHelp` is **declared** | §4 |
| **F-5** | *"every numeric run is `<bdi dir="ltr">`"* (D9) | **no bidi helper anywhere in this feature** — the strings are safe by construction and the shipped helper cannot isolate three runs without a live substring collision | §9 |

---

## 0. The rules this deck is written under — hard constraints, not preferences

1. **Zero exclamation marks** (pre-decided #5). Mechanically checkable; `i18n.test.ts:397-399` already reads for it.
2. **Never claim, promise or hedge that a message was sent, in any tense.** `i18n.test.ts:401-402` rejects `/נשלח|תישלח|בדרך/` in any selected value. Trivially satisfied — F42 notifies nobody — and stated anyway. ⚠ The third alternative, **«בדרך»**, is the one a copy editor would reach for innocently («העבודה בדרך»), and it is banned in this bundle whatever it means.
3. **The panel states, it does not reassure.** Every string is a fact. No «הכל תקין», no «מעולה», no «כל הכבוד» on an empty queue. A shift manager reads this panel fifty times a shift and warmth at that frequency is noise — **and on an overload row it would be worse than noise.**
4. **⚠ NO STRING IN THIS DECK MAY CONTAIN «168» OR «1440».** They are `MAX_WEEKLY_CAPACITY_HOURS` and `MAX_BAND_MINUTES` — **server** bounds — and a Hebrew sentence quoting one is a mirror exactly as much as a TypeScript constant is, **with none of the protection**: `test_frontend_constant_parity.py` scrapes only the two `validation.ts` files, so raising the DB CHECK to 200 would leave the sentences lying, silently and greenly. **The precedent is not ambiguous**: F41 declared `atelier.form.error.dueDateHorizon` and **cut it at review** for this exact rule, with the reason recorded at `i18n.test.ts:705-719` — *"730 is a SERVER bound and no client constant may mirror one."* **The copy states the SHAPE of the mistake; the server's 400 states the range.** The one numeral that *is* allowed is `{{hours}}` in `capacity.hoursHelp`, and it is a **tenant's** value read off the envelope, not a platform bound.
5. **A number in this deck always arrives with its unit word.** «12» alone is ambiguous between hours, minutes and a count of people; «12 שעות» is not. This is also what makes §9's bidi argument hold — every numeral is bracketed by Hebrew.
6. **Overload is a WORD, and the word is «עומס יתר».** It appears in exactly three renderings — the panel row, the assign `<option>` and the assign cue — and it is **the same two words in all three**, because a manager who reads it on a row and hears it on a cue must not have to work out that they are the same fact.
7. **Status and urgency are carried by WORDS.** No emoji, no dots, no glyphs, no «⚠», no «!» — an emoji is announced by a screen reader with a name this product did not choose and cannot translate, and the console ships no icon vocabulary at all.
8. **One spelling per fact.** Where two surfaces in this feature say the same thing about the same thing, they share a key: both dialogs' dismiss is the shipped `atelier.form.cancel`; the five band words in the settings dialog are the shipped `atelier.band.*`; the inactive-assignee line is the shipped `atelier.assigneeInactive`. ⚠ **Two byte-identical «שמירה» values are DECLARED separately** (`capacity.submit`, `settings.submit`) and so is a third already shipped (`atelier.form.submitEdit`) — saving a person's hours, saving the boutique's ruler and saving a ticket are **three facts**, and F41's **F-9** records this duplication pattern as deliberate.
9. **Every value is a real string.** No `…`-as-placeholder, no Lorem, nothing to be filled in later. **There is no `…` anywhere in this deck.**
10. **The `ar` column is the approved Hebrew, standing in untranslated** (Interview Q3 / pre-decided #47 / the 2026-07-31 languages ruling), and it is **never an empty string**: i18next's `returnEmptyString` default renders `""` rather than falling back, so a premature switch would blank the page instead of showing Hebrew.
11. **⚠ NO INTERPOLATION IN THIS DECK IS NAMED `count`.** The panel heading interpolates **`{{total}}`**. `count` is i18next's plural-resolution trigger: passing it makes the translator look for `key_one` / `key_two` / `key_many` / `key_other` before the base key, so a bundle carrying only the base key resolves through a fallback path rather than directly. F41's rule 11, inherited.
12. **⚠ AND NO STRING CARRIES A NOUN AFTER A COUNT.** «{{total}} תופרות» is wrong at 1 and wrong at 2 (Hebrew takes a dual), and doing it properly needs four i18next plural suffixes per string **in two bundles**. The heading is «תופרות · {{total}}» — the noun leads, the number follows, and no agreement question arises. F41's **F-3**, at a different noun.

**40 keys invented, 7 reused.** The reused seven are already shipped by F41 and are listed in §6. ⚠ **The `ar` parity guard already covers all 40 for free**: `HE_F41` selects by **prefix** — `key === "nav.atelier" || key.startsWith("atelier.")` (`i18n.test.ts:70-73`) — and is spread into `HE` (`:85`). **Do NOT declare a second `HE_F42 = entries(he.translation, key.startsWith("atelier."))` and spread it into `HE`**: it would double-count the union and make every `HE`-iterating guard run twice over F41's 95 keys, silently and greenly, wasting the next reader's afternoon. F42's block **derives**: `const HE_F42 = HE_F41.filter(([key]) => key.startsWith("atelier.capacity.") || key.startsWith("atelier.settings."));` — **not spread**. §10.

⚠ **`he.ts:1196`'s section header reads *"F41, the atelier. 95 keys, 0 reused"* and goes stale the moment this deck lands.** Corrected in passing to name both features and both counts.

⚠ **«נשלח» appears three times in this file and zero times in a value** — in §0 rule 2, in this sentence, and in §8's check row. `i18n.test.ts:401-402` reads **values**, so the guard is clean; a reader grepping this deck rather than the bundle will find all three and should not report them. **Verified mechanically**: `grep -n 'נשלח\|תישלח\|בדרך'` returns exactly those three lines, none of which is an approved-Hebrew cell.

---

## 1. The panel's chrome — the heading, the empty states, the unassigned total

| Key | What it must say | Approved Hebrew (`he`) | `ar` (untranslated) | Status |
|---|---|---|---|---|
| `atelier.capacity.heading` | ⚠ **The `<ul>`'s `aria-label`, and it is the UNCOUNTED one on purpose** — an accessible name must not churn on a five-second tick, and the roster count *can* change without a staff edit (`seamstresses` is a union, so a retired assignee leaves it when her last undelivered ticket is delivered). Never rendered as visible text | תופרות | תופרות | DRAFTED — `aria-label` only |
| `atelier.capacity.headingCount` | The panel's `<h3>`, visible. The **counted** twin, and the count is what tells a screen-reader user the list is long **before** she enters it — the same job F41's column headings do. ⚠ **`{{total}}` is `seamstresses.length` — PEOPLE, not rows** — which is why the unassigned total is rendered outside the list (`design.md` §10.1). ⚠ **`{{total}}`, never `{{count}}`** (§0 rule 11), and **no noun after the number** (§0 rule 12) | תופרות · {{total}} | תופרות · {{total}} | DRAFTED |
| `atelier.capacity.empty` | The whole list replaced, when the boutique has **no seamstresses at all**. Read by a **shift manager or a seamstress**. A plain fact and no instruction — because the only remedy is on a screen the gate refuses her | אין תופרות רשומות. | אין תופרות רשומות. | DRAFTED |
| `atelier.capacity.emptyOwner` | The same state read by an **owner**, who *can* act. ⚠ **Two keys and not one**: the staff screen is owner-only (`App.tsx:145`), and a line telling a shift manager to go somewhere the gate refuses is **this console lying about its own permissions** — `App.tsx:44-49` records that exact failure for `board`. «במסך הצוות» names the destination in the word the nav row uses | אין תופרות רשומות. אפשר להוסיף במסך הצוות. | אין תופרות רשומות. אפשר להוסיף במסך הצוות. | DRAFTED |
| `atelier.capacity.unassignedRow` | The work nobody holds — a `<p>` **after `</ul>`**, never an `<li>`, and **carrying no bar**: nobody has capacity for it, so there is no denominator and a bar would be a ratio to nothing. ⚠ `{{hours}}` is the **whole unassigned backlog**, not the seven-day slice (`design.md` **F-3**) — the row has no rate to compare against, and «בתור» on the seamstress rows already means the same quantity. **Rendered only when the total is above zero**: a zero line is noise on every board that is fully assigned | לא משויך · {{hours}} שעות | לא משויך · {{hours}} שעות | DRAFTED |

## 2. The row's sentence — the entire accessibility payload of the bar

**⚠ THE BAR IS `aria-hidden` AND CARRIES NO ROLE, NO NAME AND NO VALUE (`design.md` §2.5). Everything it shows is in these six strings, more precisely.** A screen-reader user hears the row and loses nothing; a user in forced colours or greyscale reads the row and loses nothing. **That is what "overload is never colour-only" means concretely**, and it is why deleting «עומס יתר» while keeping the red class has its own named mutation.

The clauses assemble in **this order and no other**, joined by « · » — the alarm as early as the grammar allows, the qualifier last:

```
{load | loadNoCapacity + notSet}   [· over]   [· backlog]   [· fromDefault]
```

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.capacity.load` | **The bar's own numbers, in words.** Reads *"X hours' worth due by {{date}}, out of Y"*: `{{hours}}` is the work due inside a rolling week, `{{date}}` is the end of that week, `{{capacity}}` is her weekly hours. ⚠ **`{{date}}` comes from the WIRE and never from the device** — the server filtered on its own `today_jerusalem + 7`, `lib/jerusalem.ts` ships **no** date arithmetic, and a device that has crossed Jerusalem midnight would print a horizon the SQL did not use (`design.md` **F-1**). ⚠ **Three numerals in one string and NO bidi helper** — §9 | {{hours}} שעות עד {{date}} מתוך {{capacity}} | {{hours}} שעות עד {{date}} מתוך {{capacity}} | DRAFTED — `{{date}}` is `plainDate()`, `d.m.yyyy` |
| `atelier.capacity.loadNoCapacity` | The load half for a seamstress with **no resolved capacity** — no bar is drawn, so there is no denominator to name and no horizon to divide into. ⚠ `{{hours}}` is her **whole backlog** here, not the seven-day slice (`design.md` **F-4**), which is what makes an unconfigured row comparable with a configured one's «בתור» clause. Always paired with `notSet` | {{hours}} שעות | {{hours}} שעות | DRAFTED |
| `atelier.capacity.notSet` | The second half of that row. ⚠ **This is the single most likely state in week one and it must NOT read as an error** — no «חסר», no «לא הוגדר» in the masculine-failure register, no `--color-danger`. It is a fact about configuration, rendered in the muted register, with the fix one tap away. «לא הוגדרה» agrees with «קיבולת», feminine | לא הוגדרה קיבולת | לא הוגדרה קיבולת | DRAFTED |
| `atelier.capacity.over` | ⚠ **THE SINGLE MOST IMPORTANT STRING IN THIS DECK.** For a sighted user the bar turning red is a signal; **for a screen-reader user, and for anyone in greyscale or forced colours, these two words ARE the overload.** Rendered as a `<strong>` **inside the row's one `<p>`** — never a second `Badge`, which would split the sentence into two announced chunks and put a second badge vocabulary above sixty of F41's cards (`design.md` §11 **P-2**). «עומס יתר» — an excess of load. Not «עמוסה» (an adjective about her, and this is a fact about her queue), not «חריגה» (a violation, and nothing here is refused) | עומס יתר | עומס יתר | DRAFTED |
| `atelier.capacity.backlog` | The queue clause — LOOP-STATE's own number, the sum of **all** her undelivered effort with no date predicate, so the total is never hidden behind the bar's seven-day slice. «סה״כ» marks it as the larger figure and «בתור» marks it as waiting rather than due | סה״כ {{hours}} שעות בתור | סה״כ {{hours}} שעות בתור | DRAFTED |
| `atelier.capacity.fromDefault` | The last clause, when the resolved number came from the **boutique's** default rather than from her own row. **The number is honest about whose it is** — a manager reallocating work must know whether 30 is a fact about this seamstress or a fact about the shop. Muted, last, and never rendered when she has her own hours | ברירת מחדל של הבוטיק | ברירת מחדל של הבוטיק | DRAFTED |

**What the three rows of `design.md` §1 actually read, assembled:**

> «6 שעות עד 11.8 מתוך 12 · סה״כ 12 שעות בתור · ברירת מחדל של הבוטיק»
> «4 שעות · לא הוגדרה קיבולת»
> «15 שעות עד 11.8 מתוך 12 · **עומס יתר** · סה״כ 46 שעות בתור»

## 3. The capacity dialog — one person's hours

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.capacity.edit` | The row's trigger, `Button variant="ghost"`, **elevated only** and **absent on an `assignable: false` row** — the server refuses her (`_require_seamstress`) and rendering a control that always 400s is a trap. One word, because it lives under a thumb in a 295 px row beside a name that may wrap | שעות | שעות | DRAFTED |
| `atelier.capacity.editAria` | Its per-row accessible name. **A six-row panel otherwise exposes six buttons all named «שעות»** and a screen-reader user pulling up the control list cannot address one — WCAG 4.1.2 / 2.4.6. **Starts with the visible label** so WCAG 2.5.3 label-in-name holds and a speech-input user saying «שעות» still matches. Asserted in `i18n.test.ts`, not trusted. ⚠ An `aria-label` takes no markup, so `{{name}}` interpolates plainly — there is nothing rendered to reorder | שעות — {{name}} | שעות — {{name}} | DRAFTED — `aria-label` only |
| `atelier.capacity.dialogTitle` | The `Modal` title. Names the quantity, not the person — the row she came from is still on screen behind the dialog, and putting the name here would make the title change on every open for no gain | שעות שבועיות | שעות שבועיות | DRAFTED |
| `atelier.capacity.hoursLabel` | The one field's `<label>`. The unit is in the label, so the field holds a bare number | שעות בשבוע | שעות בשבוע | DRAFTED |
| `atelier.capacity.hoursHelp` | ⚠ **NOT IN D15's TABLE — added here** (`design.md` **F-6**). The `help` line, rendered when the boutique **has** a default. It states the one rule that makes the whole dialog legible: **an empty field means "use the boutique's number", in both directions** — she opens an inherited row and it is already empty, she clears her own and it becomes inherited. `{{hours}}` is the **tenant's** value off the envelope, not a server bound (§0 rule 4) | ריק — חזרה לברירת המחדל של הבוטיק: {{hours}} שעות. | ריק — חזרה לברירת המחדל של הבוטיק: {{hours}} שעות. | DRAFTED |
| `atelier.capacity.hoursHelpNoDefault` | ⚠ **NOT IN D15's TABLE — added here.** The same line on a boutique with **no** default, which is **every boutique on day one** — the state D2 exists to protect. The string above would promise a fallback that does not exist, so it is not shown; this one says what actually happens. **Two keys, because one of them would be a lie exactly when it is read most** | ריק — לא תוגדר קיבולת. | ריק — לא תוגדר קיבולת. | DRAFTED |
| `atelier.capacity.useDefault` | ⚠ **A ghost `Button` in the dialog BODY, under the field, and it CLEARS the field — it does not submit.** `Modal`'s footer is `flex justify-end gap-3` with no wrap and no `className` seam, so a third footer button of five Hebrew words overflows a 295 px panel at 375 (`design.md` **F-6**). Clearing rather than submitting keeps one submit path, one confirm and one error path. **Rendered whenever the boutique has a default**, not conditioned on the field being non-empty — a control that appears as she types is a control that moves under her finger | חזרה לברירת המחדל | חזרה לברירת המחדל | DRAFTED |
| `atelier.capacity.submit` | ⚠ **NOT IN D15's TABLE — added here.** The dialog had no named confirm at all. Byte-identical to `settings.submit` and to the shipped `form.submitEdit`, and **declared separately** under the namespace that names its subject (§0 rule 8) | שמירה | שמירה | DRAFTED |
| `atelier.capacity.error.hours` | Rides the field's own `error` prop, which wires `aria-describedby` + `role="alert"` and flips the border to `--color-danger`. Names **the shape of the number**, never its range — ⚠ **no numeral, ever** (§0 rule 4). «ולא שלילי» rather than «חיובי», because **0 is legal and is not a typo**: a shift manager setting 0 is saying *she is not available this week*, which is a thing this product should be able to say | צריך מספר שעות שלם ולא שלילי. | צריך מספר שעות שלם ולא שלילי. | DRAFTED |
| `atelier.capacity.error.server` | ⚠ **The Hebrew `default:` branch, and it is structural rather than cosmetic.** `main.py`'s error bodies are **English** and this console is Hebrew-only; the concrete message this route can produce is `_require_seamstress`'s literal `"staff_user_id must be a live seamstress"`. F41 records the rule in code at `AtelierSection.tsx:493-497`. Rendered in **one alert inside the dialog, above the footer**, `role="alert"` and focused — never a toast behind a modal, never `error.message` | לא ניתן לשמור את השעות. אפשר לנסות שוב. | לא ניתן לשמור את השעות. אפשר לנסות שוב. | DRAFTED |
| `atelier.capacity.cue.saved` | Announced in F41's shipped `role="status"` region after a successful set. Names her, because the dialog has closed and focus has gone back to a trigger that says only «שעות» — so this is the only thing that says **whose** hours were saved. Written by `AtelierSection`, not the panel, so the shipped `{ text, name }` state and `isolateBidi` work unmodified | {{name}} — עודכנו השעות. | {{name}} — עודכנו השעות. | DRAFTED — `{{name}}` in a bare `<bdi>` |
| `atelier.capacity.cue.cleared` | The same moment when she saved an **empty** field. ⚠ **A different sentence and not a parameter**, because the outcome differs in a way she must hear: her own number is gone and the boutique's applies. «עודכנו השעות» on a clear would be true and useless | {{name}} — חזרה לברירת המחדל. | {{name}} — חזרה לברירת המחדל. | DRAFTED — `{{name}}` in a bare `<bdi>` |

## 4. The settings dialog — the boutique's ruler and its default

**One dialog, one save, both keys, always** (`design.md` §11 **P-7**): `merge_settings`' `||` merges at the **top level only**, so a patch carrying a partial `atelier` object replaces the whole key and deletes what it did not name. Two save buttons would silently delete each other's work.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.settings.open` | The panel-level trigger, `Button variant="ghost"`, **elevated only**, at the panel's **foot** — a boutique-wide configuration used once a quarter must not sit above the rows a manager opens the panel to read (`design.md` §11 **P-5**) | הגדרות | הגדרות | DRAFTED |
| `atelier.settings.openAria` | Its accessible name — it must say **which** settings, because «הגדרות» is a word this console uses in more than one place. The `—` shape is the shipped one (`atelier.pauseAria`), and it **starts with the visible label** so 2.5.3 holds | הגדרות — לוח התפירה | הגדרות — לוח התפירה | DRAFTED |
| `atelier.settings.title` | The `Modal` title. «התפירה» rather than «הלוח», so the dialog names the craft it configures rather than the screen it was opened from — the bands and the default outlive any one board | הגדרות התפירה | הגדרות התפירה | DRAFTED |
| `atelier.settings.bandsLabel` | The group label above the five band fields. «הערכה» is the honest word — the E9 brief's central accepted risk is that these estimates are wrong, and «זמן עבודה» would state as fact what the whole epic treats as a guess. Same word F41 already uses on the intake form's label | הערכות זמן | הערכות זמן | DRAFTED |
| `atelier.settings.bandsHelp` | ⚠ **NOT IN D15's TABLE — added here** (`design.md` **F-11**). D4 establishes that a re-tune re-values nothing **and** that an old card can therefore **silently relabel** — flattening «יום מלא» onto 240 makes every «חצי יום» garment read «יום מלא», with no fallback and no visible act. **This dialog is the only place a human causes that**, and without this line an owner correcting one band gets an unexplained change across her board and no way to connect the two. The sentence is true (the minutes on existing tickets do not move) and it is the reassurance a hesitating owner needs | שינוי ההערכות משפיע רק על כרטיסים חדשים. | שינוי ההערכות משפיע רק על כרטיסים חדשים. | DRAFTED |
| `atelier.settings.bandMinutes` | The `<label>` of each of the five number fields. `{{band}}` is one of the **shipped** `atelier.band.*` words (§6) — one vocabulary for the five bands across the intake form, the card, the picker and this dialog. The unit is in the label, so each field holds a bare number | {{band}} — דקות | {{band}} — דקות | DRAFTED |
| `atelier.settings.defaultCapacity` | The sixth field's `<label>`. Named as a **default** rather than as a capacity, because it is not anybody's hours | ברירת מחדל: שעות בשבוע | ברירת מחדל: שעות בשבוע | DRAFTED |
| `atelier.settings.defaultCapacityHelp` | Its `help` line. States **exactly** who it applies to, because the alternative reading — "this is everyone's capacity" — would make a manager think editing one row here changes the shop. «שלא הוגדרו לה שעות משלה» is the resolution rule in words | חלה על תופרת שלא הוגדרו לה שעות משלה. | חלה על תופרת שלא הוגדרו לה שעות משלה. | DRAFTED |
| `atelier.settings.submit` | The confirm. §0 rule 8's deliberate duplication | שמירה | שמירה | DRAFTED |
| `atelier.settings.error.minutes` | On a band field. ⚠ **No numeral** — 1440 is a server bound (§0 rule 4). «חיובי» here and «ולא שלילי» on the capacity field, and the difference is real: **a band of 0 minutes is meaningless, a capacity of 0 hours is not** | צריך מספר דקות שלם וחיובי. | צריך מספר דקות שלם וחיובי. | DRAFTED |
| `atelier.settings.error.default` | On the sixth field. «או ריק» is the third state and it is a **value**, not an omission — clearing the boutique default is a thing an owner may deliberately do | צריך מספר שעות שלם ולא שלילי, או ריק. | צריך מספר שעות שלם ולא שלילי, או ריק. | DRAFTED |
| `atelier.settings.error.server` | The Hebrew `default:` branch for this dialog, `capacity.error.server`'s argument exactly. **Names the settings**, so a manager with both dialogs open in one minute can tell which save failed | לא ניתן לשמור את ההגדרות. אפשר לנסות שוב. | לא ניתן לשמור את ההגדרות. אפשר לנסות שוב. | DRAFTED |
| `atelier.settings.cue.saved` | Announced after a successful merge. **No interpolation at all** — the subject is the boutique, not a person, and there is no new value worth naming that the dialog she just closed did not show her. ⚠ **This is the sentence both of two shift managers see when one of them has just silently reverted the other's work** (`design.md` §4); the recovery path is the audit trail, and there is deliberately no UI for it | ההגדרות נשמרו. | ההגדרות נשמרו. | DRAFTED |

## 5. The assignment surface — the sorted options and the overload cue

**⚠ EVERY PART OF AN OPTION IS A KEY, INCLUDING THE SEPARATOR.** F41 renders `{row.display_name}` alone in this `<option>` and declares no key of this shape, so all three strings would otherwise ship as **bare Hebrew literals in TSX** — outside the `ar` parity guard, outside `HE_F41`'s prefix fold, untranslated, and invisible to both `he.ts:1210-1213`'s standing rule and this feature's own acceptance line.

| Key | What it must say | Approved Hebrew (`he`) | `ar` | Status |
|---|---|---|---|---|
| `atelier.capacity.optionRow` | The envelope for all three option shapes — **the « · » itself is composed from this key**, so the rendered string contains no literal. `{{name}}` is her display name, `{{detail}}` is one of the three below | {{name}} · {{detail}} | {{name}} · {{detail}} | DRAFTED |
| `atelier.capacity.optionRemaining` | Group 1 — capacity set, real headroom. **The number is why the list is in this order**: a reordered control with no explanation is a control that shuffles for no reason a user can see. «נותרו» — what is left | נותרו {{hours}} שעות | נותרו {{hours}} שעות | DRAFTED |
| `atelier.capacity.optionAssigned` | Group 2 — **no capacity set**, so there is no headroom to state and the only honest number is what she is already holding. ⚠ **«משויכות» names `assigned_minutes`, and that is what fixes the sort key for this group** (`design.md` **F-4**): a group ordered by a number none of its options displays is the invisible rule this whole section exists to avoid | {{hours}} שעות משויכות | {{hours}} שעות משויכות | DRAFTED |
| `atelier.capacity.over` | Group 3 — reused from §2, **the same two words**. She is sorted **last**, labelled, and **one tap away**: nothing is hidden, nothing is disabled, no confirm appears, and the assign answers 200. That is what "overload FLAGS, never blocks" means at the control | *(reused — §2)* | | — |
| `atelier.cue.assignedOverload` | ⚠ **THE ONLY THING A SCREEN-READER USER EVER HEARS ABOUT AN OVERLOAD SHE JUST CAUSED.** F41's D17 forbids the poll from writing into the announced region, so without this clause a sighted user watches the bar turn red on the next tick and a screen-reader user gets **nothing at all** — on the one action that causes it, on a screen where a11y is a legal bar. Chosen at the moment of the write by `wouldOverload(target, effort_minutes)`, and **gated on an actual move**, so re-committing the ticket's current assignee announces the ordinary `atelier.cue.assigned` and never this. ⚠ **Sits beside the shipped `atelier.cue.assigned` and names ONE user value**, which is what keeps `isolateBidi(text, value)` and the shipped `{ text, name }` cue state working unmodified | שויך ל{{seamstress}} — עומס יתר. | שויך ל{{seamstress}} — עומס יתר. | DRAFTED — `{{seamstress}}` in a bare `<bdi>` |

**No string for "you may not do this".** A seamstress sees every row, every bar and every sentence — and **no controls at all**: no «שעות» on any row, no «הגדרות», no disabled button, no lock, no explanation. The absence is cosmetics; the control is the two servers' gates. ⚠ **And the consequence of getting it wrong is not a dead button**: a 403 reaches `runMutation` → `poll.fail` → `usePoll`'s `{401,403}` terminal rule, and **her entire atelier board is replaced by «אין הרשאה»** because she tapped something this console offered her.

## 6. Reused keys — seven, all shipped by F41

| Key | Value | Where F42 uses it | Why reuse rather than declare |
|---|---|---|---|
| `atelier.form.cancel` | ביטול | **both** dialogs' dismiss | §0 rule 8: one act, one word. Esc and the backdrop do the same thing |
| `atelier.band.thirtyMin` | חצי שעה | the settings dialog's first field label, via `bandMinutes` | One vocabulary for the five bands across the intake form, the card, the picker **and** the editor that sets them. A second spelling here would let a boutique tune a band it cannot recognise on a card |
| `atelier.band.oneHour` | שעה | the second | ″ |
| `atelier.band.twoHours` | שעתיים | the third | ″ |
| `atelier.band.halfDay` | חצי יום | the fourth | ″ — ⚠ **the band whose mapping is most likely to be wrong** (*"'half-day' is not 240 minutes in a boutique whose shifts are six hours"*), and this dialog is the writer F41 shipped without |
| `atelier.band.fullDay` | יום מלא | the fifth | ″ |
| `atelier.assigneeInactive` | תופרת שאינה פעילה | the panel row of a retired or re-roled seamstress who still holds live tickets | The card already says it from the same `assignable` flag; the panel row is the second rendering of one fact, and the panel adds the number that says what reassigning her costs |

## 7. What is deliberately NOT worded

| Not written | Why |
|---|---|
| A confirm, a warning or a "she is overloaded, continue?" on any assign | Pre-decided #40. **Overload FLAGS, never blocks.** There is no 409, no confirm step and no disabled option in this feature — so there is no string, because there is no moment |
| An aggregate «הבוטיק בעומס» banner | `design.md` §11 **P-3**. A second, louder signal saying what four rows already say is how a board stops being read — and in a busy season it would be permanently true |
| Anything on the panel heading about overloads | The heading counts the **roster**. An overload total there would need its own key, its own state row and its own assertion; the claim is **dropped rather than half-built** |
| A "last edited by" / conflict notice on the settings dialog | Two shift managers **do** silently lose each other's work, by design, and the recovery path is the audit trail. A conflict dialog because a colleague opened the same form is the platform second-guessing a call that is hers |
| A retry interval, anywhere | Inherited from F41's rule 5: consecutive failures stretch the poll 5 s → 60 s, so any number is true at tick 1 and false by tick 5. The dialogs' server errors say «אפשר לנסות שוב» and name no duration |
| A role name on any refusal | Inherited from F41's rule 6: `NotAuthorizedError` ships one generic body so a probe cannot learn which roles exist — and on a demotion path it would be the product telling a staffer she was demoted, which is her manager's sentence to say |
| Any money word, ILS amount, deposit or price | Deliberately, per the E9 brief and Interview Q1's money fence. **Hours are the only unit on this surface** |
| «נודיע לתופרת», or any notification promise | Nothing in F42 notifies anybody. It would be a lie **and** a red (§0 rule 2) |

## 8. Register check — the mechanical pass

| Rule | Result |
|---|---|
| Exclamation marks in this deck | **0** |
| Values matching `/נשלח\|תישלח\|בדרך/` (`i18n.test.ts:401-402`) | **0** — and it is not a near miss: **nothing in F42 sends, notifies, texts or delivers anything**, so any such string would be a lie before it was a red |
| Values containing **«168»** or **«1440»** (§0 rule 4) | **0.** Both are **server** bounds. The one numeral rendered in a help line is `capacity.hoursHelp`'s `{{hours}}`, which is the **tenant's** default read off the board envelope. F41's `dueDateHorizon` precedent, `i18n.test.ts:705-719` |
| Interpolations named `count` (§0 rule 11) | **0** — the heading uses `{{total}}` |
| Nouns following a count (§0 rule 12) | **0** — «תופרות · {{total}}» leads with the noun, so Hebrew's dual never arises |
| Strings claiming the panel is realtime / live / instant | **0** — no string in this deck makes a freshness claim at all; F41's freshness row owns that and is untouched |
| Strings a **poll tick** can cause to be announced | **0** — exactly three F42 strings ever enter the live region (`capacity.cue.saved`, `capacity.cue.cleared`, `cue.assignedOverload`) and all three are the direct consequence of an **activation**. F41's §4.2 rule is not cracked |
| Interpolations of a **user-supplied** value, per string | **≤ 1 everywhere** — which is what lets the shipped `isolateBidi(text, value)` and the shipped `{ text, name }` cue state work unmodified and **no second helper be invented** |
| Statuses expressible without their word | **0** — overload carries «עומס יתר» **and** `font-semibold`; "no capacity" carries «לא הוגדרה קיבולת»; "inherited" carries «ברירת מחדל של הבוטיק»; unassigned carries «לא משויך». ⚠ **Delete every colour from this panel and nothing is lost** |
| Emoji, glyphs or icon characters anywhere in a value (§0 rule 7) | **0** |
| Reassurance / encouragement copy | **0** — §0 rule 3. ⚠ The temptation is real here: a panel with three green bars invites «הכל בשליטה», and on the fourth tick it would be sitting above a red row |
| Strings that blame the staffer | **0** — `notSet` is a fact about configuration in the muted register, not a failure; both server errors are unblaming and end with a way forward |
| Money words, ILS amounts, deposit words | **0** — deliberately |
| Controls sharing an accessible name within one panel | **0** — «שעות» is disambiguated per row by `editAria`; «הגדרות» is disambiguated from the console's other settings by `openAria` |
| `*Aria` values that do not contain their visible label (WCAG 2.5.3) | **0** — `editAria` begins «שעות», `openAria` begins «הגדרות». **Asserted in `i18n.test.ts`, not trusted** |
| Values for a state the wire cannot carry | **0** — six row strings for six reachable renderings, two empty strings for two roles, and no string for a seventh of anything |
| Placeholders, Lorem, `…`-as-content | **0** — and unlike F41's deck there is no `…` **anywhere** |
| `ar` values that are empty strings | **0** — every row carries the Hebrew as its placeholder. `i18n.test.ts:406-415` is the one guard that catches this **without** the `HE_F41` fold |
| Keys that overwrite or edit a shipped `atelier.*`, `board.*`, `floor.*` or `staff.*` key | **0** — every one of the 40 is new, under `atelier.capacity.*`, `atelier.settings.*` or the single `atelier.cue.assignedOverload` beside F41's shipped `atelier.cue.*` block |
| **Bidi helpers used** | **⚠ ZERO, and §9 is the derivation** — a departure from spec D9, because applying it literally is unbuildable and ships a substring collision |

## 9. ⚠ Bidi — this feature uses NO helper, and that is a decision with a derivation

Spec D9 says *"Every numeric run is `<bdi dir="ltr">` and every name is a bare `<bdi>` — `isolateLtr` / `isolateBidi`."* **Applied literally to `atelier.capacity.load` that is unbuildable and would ship a live defect:**

- The string carries **three** numeric interpolations. The shipped `isolateLtr(text, value)` isolates **one**, by `text.indexOf(value)`.
- **The collision is live, not theoretical.** On «12.1 שעות עד 11.8 מתוך 12», isolating the capacity as `"12"` matches **inside "12.1"** and wraps a fragment of the wrong number; equal hours and capacity leave the second occurrence unwrapped entirely.
- Writing a multi-run helper is barred by F41's own rule: *"no second helper is invented."*

**No helper is needed, because every string in this deck is safe under the bidi algorithm:**

| Shape | Example | Why it resolves correctly |
|---|---|---|
| Numeral bracketed by Hebrew | «סה״כ 46 שעות בתור» | Neutrals between R and EN resolve to R (UBA N1/N2, EN counting as R); the EN run is bumped to an even level by I2 and renders LTR **in place** |
| Numeral at the paragraph **start** | «4 שעות · לא הוגדרה קיבולת» | In an RTL paragraph the first logical run is placed at the physical **right**, reading LTR internally — which is its correct reading order |
| Numeral at the paragraph **end** | «… מתוך 12» | The last logical run is placed at the physical **left**, reading LTR internally — likewise correct |
| Three numerals in one string | «12.1 שעות עד 11.8 מתוך 12» | All three of the above at once, with Hebrew between every pair. Renders exactly as written |
| A name in an `<option>` | «Nina · 4 שעות משויכות» | ⚠ **An `<option>` takes no markup**, so no helper is available anyway. A leading Latin run in an RTL paragraph lands at the physical right and reads LTR — the intended order. **Every option string ends in a Hebrew word**; a string *ending* in the numeral («רותי · 4») is the shape that breaks, and this deck ships none |
| A name in an `aria-label` | «שעות — נועה לוי» | An `aria-label` takes no markup at all; there is nothing rendered to reorder |

**So the rule for this feature is one line:** the seamstress's **name** — the only user-supplied value — is isolated with a **bare `<bdi>` in its own `<span>`**, never interpolated into a sentence, and **nothing else is isolated at all**. ⚠ `isolateLtr` is wrong for a name in any case: it emits `<bdi dir="ltr">`, and forcing LTR on «נועה לוי» reverses its Hebrew words — a bidi defect that **looks deliberate**, which is the kind nobody files.

## 10. The i18n fold — the one failure that would make this whole deck vacuous

**⚠ THE FOLD IS ALREADY DONE AND MUST NOT BE DONE TWICE.** `HE_F41` selects by **prefix** — `key === "nav.atelier" || key.startsWith("atelier.")` (`i18n.test.ts:70-73`) — and is spread into `HE` (`:85`). **So all 40 keys above are already inside the `ar` parity guard, both register guards and the empty-`ar` guard**, with no work.

This is the one place in this feature where a shipped guard does F42's job for it, and it is stated because the *other* failure mode is the expensive one:

- **Declaring `HE_F42 = entries(he.translation, ([key]) => key.startsWith("atelier."))` and spreading it into `HE`** would **double-count the union** — every `HE`-iterating guard would run twice over F41's 95 keys, **silently and greenly**, and the next reader would spend an afternoon on it.
- F42's own block therefore **derives and spreads nothing**:

```ts
const HE_F42 = HE_F41.filter(
  ([key]) => key.startsWith("atelier.capacity.") || key.startsWith("atelier.settings."),
);   // NOT spread into HE — HE_F41 already carries these rows
```

- `i18n.test.ts:721`'s `expect(HE_F41.length).toBeGreaterThanOrEqual(94)` is a **floor** and stays true; it does not need raising.
- ⚠ **`he.ts:1196`'s header comment — *"F41, the atelier. 95 keys, 0 reused"* — goes stale the moment this deck lands** and is corrected in passing to name both features.
- ⚠ **`he.ts:1210-1213`'s standing rule applies to every one of the 40**: *any* quoted `"atelier.…"` literal anywhere in `apps/manage/src` is scraped as an i18n key and must resolve to a defined, non-empty Hebrew string. **Do not name a `data-testid` or a `data-control` `atelier.capacity.save`.**
