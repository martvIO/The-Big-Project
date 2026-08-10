# Screen design — F40 roster builder + the published roster as the on-shift source (`apps/manage`, Epic E8)

**Date**: 2026-08-10 · **Status**: DESIGN GATE OPEN — awaiting critic + copy approval · **Designer**: Claude (design subagent)
**Consumes**: `.planning/specs/roster-builder.md` (Gate 1 self-approved under Q1, C1–C6 / D1–D17) · tokens rev 1 · `packages/ui` as shipped
**Precedents read before drawing**: `.planning/design/screens/availability-submission/` (F39 — merged, PR #58) · `.planning/design/screens/hr-directory/` (F38) · `.planning/design/screens/toggle-matrix-ui/` (F27) · the shipped `ShiftsSection` / `MyWeekPanel` / `WeekSubmissionsPane` / `ShiftTemplatesPane` / `ShiftAvailabilityFieldset` / `FloorPanel` / `lib/week.ts` / `lib/jerusalem.ts` / `lib/roles.ts`
**Copy**: every Hebrew row in §9 needs APPROVAL. Register: calm, feminine address, **no exclamation marks** (pre-decided #5, asserted by `__tests__/i18n.test.ts`).

---

## 0. Scope, and what the owner is actually optimising for

Two surfaces, two audiences, and they are not the same job:

| Audience | Surface | Frequency | Device |
|---|---|---|---|
| **Elevated only** (`owner`, `shift_manager`) | `RosterPane` + `RosterCellDialog` in the existing «משמרות» section; the coverage-target fields on `ShiftTemplatesPane`; the override control on `FloorPanel` | **once a week, in one sitting, under time pressure** | desk or a phone standing in the boutique |
| **Every staffer** (all five roles) | the `MyWeekPanel` published block; the on-shift line on every `FloorPanel` card | daily glance | a phone / the shared floor tablet |

### 0.1 The one sentence that governs `RosterPane`

**She is closing gaps, not reading data.** On a Wednesday evening after submissions close, the owner performs one act, repeatedly: *find a shift that still needs somebody → see who can take it → tap a name → move on.* Her success condition is "no shift is short and every shift has a woman in charge." Her failure mode is **"I published and missed one."**

Everything below is arranged around three questions, in this order of frequency:

| Question | How often | Where this design answers it |
|---|---|---|
| "Which shift still needs work?" | continuously, the whole session | the standing shortage line (§2.6) + «חסר איוש» on the shift itself + P1's filter |
| "Who can cover *this* shift?" | ~12 times a week | `RosterCellDialog`, sorted by who wants it (§3) |
| "Am I overloading Dana?" | a handful of times | her week count, **inside the dialog, at the moment of the decision** (§3.3) |

**Rejected up front — the roster as a staff × shift grid.** §1 gives the arithmetic; the design reason is simpler and it is decisive: **the matrix already ships, one Card above this one.** `WeekSubmissionsPane` is one row per staffer with her answers for the week — that *is* the person-across-the-week read, it is the readiness read D17 deliberately stacks above the build, and building a second matrix underneath it would be two lists of the same people differing only in what they claim, which is D1's own rejection applied to a different pair.

### 0.2 Binding inheritances, obeyed and not restated

F-W1 (`Button size="sm"` = `min-h-9` = **36px**, fails the 44px floor — `md` only, everywhere in this feature). DL20 / `ConsoleShell.tsx:53-68` (**this console ships no icon-only control; the visible Hebrew word IS the name** — which is why there is no `×` on a chip anywhere below). R19 bidi isolation (**bare** `<bdi>` around a human name; `dir="ltr"` on a Hebrew name is itself a defect). The house failure vocabulary `shifts.loadFailed` + `shifts.retry` («ניסיון נוסף», verbatim). Jerusalem reads only through `lib/jerusalem.ts`; the single piece of date arithmetic through `lib/week.ts`' `addDays`. `ConsoleShell` caps `#console-main` at **`max-w-[720px]`**, at every viewport width.

### 0.3 And one thing out by epic risk, which is a design constraint and not a feature list

**This is not an hours-worked record and no screen here may read as one.** F39's §0 binds unchanged and binds *harder*, because a roster with times on it is one `SUM()` away from a timesheet:

- **No hour totals anywhere.** No «סה"כ שעות», no weekly sum beside a name, no duration column, no «X שעות במשמרת».
- **No warning about a long day, no double-booking flag, no rest-period check.** Two overlapping templates on one weekday are legal (F39 D2) and rostering the same woman on both is an ordinary split shift; a platform that starts validating that is doing Hours of Work and Rest Law validation, which the epic puts *visibly* out. The mitigation is §3.3's week count — **the owner sees the load; the platform does not judge it.**
- A shift shows `HH:MM–HH:MM` because that is how she recognises which shift she is filling. Nothing adds them up.

---

## 1. There is no grid, and this is the arithmetic that settles it

`ConsoleShell` caps `#console-main` at 720px **at 375, 768 and 1440 alike**. A pilot boutique is 8 staff × ~12 shifts.

| Layout | Column width available | Verdict |
|---|---|---|
| 9-column table (shift label + 8 staff) at 1440 / 768 | (720 − 48 padding − 120 label) / 8 = **69px** | below the 44px floor once a cell holds a control; a Hebrew display name does not fit in any header |
| the same at 375 | (295 − 100 label) / 8 = **24px** | not a layout |
| 9-column table inside `overflow-x: auto` | — | a horizontally scrolling table inside an RTL page, whose sticky first column is on the *inline* start, is a pattern this console has never shipped and axe cannot rescue; **§7 asserts no horizontal scroll at any of the three widths** |

96 cells is not the problem. **69px is the problem, and it does not improve at 1440 because the shell does not widen.** So the surface is a **list of shifts in day order** — F39's shipped `ShiftTemplatesPane` shape with people in it, on the same nav row, which the elevated actor already reads every week.

The three reads a matrix would have served are served like this:

- **column read** ("this shift: who?") → the shift block itself (§2.3) — the primary structure, because it is the primary act.
- **row read** ("Dana across the week") → her count in the dialog at the moment of the decision (§3.3), plus `WeekSubmissionsPane` one Card above for her *answers*.
- **whole-week read** ("am I done?") → the standing shortage line (§2.6), which is one number and updates on every write.

---

## 2. `RosterPane` — elevated, the fifth Card in `ShiftsSection`

Inserted **between `WeekSubmissionsPane` and `ShiftsDeadlineCard`** (D17): readiness above the build, configuration below it, which is `ShiftsSection`'s stated ordering unchanged. An elevated actor now sees **five `h2`s** in this section; a non-elevated staffer still sees one.

⚠ **It goes inside the `!firstRun` branch**, beside `MyWeekPanel` and `WeekSubmissionsPane` — never beside `ShiftTemplatesPane`. `ShiftsSection`'s first-run `if` collapses the section to the templates Card when no live template exists, and a roster builder over zero shifts is the fourth stacked empty that `if` exists to remove. One line in the existing conditional, no new state, and §2.8-E1 needs no drawing of its own.

### 2.0 ⚠ Every button's variant, and every button's in-flight state — both stated, neither defaulted

⚠ **`Button`'s `variant` defaults to `primary`, and `primary` is `bg-gold text-ink`** (`packages/ui/src/components/Button.tsx:41` / `:31`). A control this design does not name a variant for **ships gold**. On this pane that is twelve gold «הוספה למשמרת» buttons, a gold «הוספה» on every dialog row, a gold override confirm and up to three gold buttons per floor card — a wall of CTAs against design-config's *"restraint over decoration"* and the gold law's whole point that gold is an accent. **Silence is not an omission here; it is an instruction.** So the variant is stated for every control in the feature, and there is **exactly one `primary` on each surface**:

| Surface | `primary` (the one gold control) | `secondary` | `danger` | `ghost` |
|---|---|---|---|---|
| `RosterPane` | `shifts.publish` / `shifts.republish` — **the only gold on the pane** | week pager (§2.10) · `shifts.setManager` / `shifts.clearManager` (§2.5) · `shifts.addToShift` · `shifts.retry` | `shifts.removeAssignment` (§2.3) | — |
| `RosterCellDialog` | **none** — the dialog is an editor, and a gold button per row is the same wall one modal deeper | `shifts.cellAdd` · `shifts.assignAnyway` | `shifts.cellRemove` | — |
| `ShiftTemplatesPane` fieldset | unchanged — the pane's shipped save button keeps its variant | — | — | — |
| `FloorPanel` card | **none** — the board carries no gold today and gains none (C1) | `floor.markOnShift` / `floor.markOffShift` | — | `floor.clearOnShiftOverride` — it undoes a state, which is the shipped break toggle's own `ghost` branch (`FloorPanel.tsx:964`) |

- **`assignAnyway` is `secondary`, deliberately.** The deliberateness of the second tap is carried by the warning line above it and by the changed label — not by making the one button in the dialog that writes an exception the loudest thing on screen. D11 asks for a second act, not for alarm.
- **The add/remove flip flips the variant too** (`secondary` ⇄ `danger`), matching the shift block's own pair. The label already carries the meaning; the variant is redundant reinforcement, §9.0(d)'s shape applied to a control.

⚠ **And every write button shows that it is writing.** `Button` ships `loading` — spinner overlaid, label kept in the DOM so the **width never jumps**, `aria-busy`, and `disabled={disabled || loading}` (`Button.tsx:56-57`). This is not optional decoration on this feature: §0.1's owner taps «הוספה» *dozens of times a session*, fast, on a phone at the boutique counter. Unguarded, a double-tap or a tap on the next row before the first POST resolves sends a second write — a duplicate assignment surfacing as a `409` from the partial unique index, or a `DELETE` against a row that is already gone, both of which reach her as an unexplained alert for what felt like one action.

- **The pressed button carries `loading`; nothing else disables.** Two different rows may be written concurrently — that is legal and it is how she works — so the guard is per-control, not per-dialog. `FloorPanel`'s shipped `busyIds: readonly string[]` is exactly this shape and is the precedent, keyed here by assignment identity rather than card id.
- **Re-arm in `.finally()`, never in the success branch**, so a failed write leaves a live button rather than a permanently spinning one (`mutate`'s shipped rule, §6.3).
- **Applies to**: `cellAdd` / `cellRemove` / `assignAnyway` in the dialog, `removeAssignment` and `setManager` / `clearManager` on the shift block, `publish`, and all three floor mark/clear buttons. The week pager and P1 are client-only and take none.
- **The disabled-while-loading blur is why the focus rescues in §10 are written the way they are** — a `disabled` button drops focus to `<body>`, which is the same blur `FloorPanel`'s `restoreFocusRef` effect already handles (§6.3).

### 2.1 Structure at 375px, one column

```
Card
  h2  סידור עבודה
  ┌ week bar ────────────────────────────────────────────────┐
  │ [ השבוע הקודם ]  [ השבוע הבא ]                            │
  │ <p role="status"> שבוע 8–14 בנובמבר                        │  ← RangeText, F39's shape
  ├──────────────────────────────────────────────────────────┤
  │ <p> טיוטה. הסידור אינו גלוי לצוות ואינו קובע מי במשמרת.    │  ← or «פורסם ב־… על ידי …»
  │ <p> בוצעו שינויים מאז הפרסום. הם כבר בתוקף בלוח הקומה.     │  ← edited_since_publish only
  │ <p> השבוע הזה כבר בעיצומו. כל שינוי משפיע על לוח            │  ← offset ≤ −1 only, §2.10
  │     הקומה מיד.                                            │
  ├──────────────────────────────────────────────────────────┤
  │ <p role="status"> משמרות שחסר בהן איוש: 3                  │  ← the standing count, §2.6
  │ [ פרסום הסידור ]ᵖ  <span role="status"> הסידור פורסם.      │  ← count FIRST, §2.7 / §2.0
  │ [✓] הצגת משמרות שחסר בהן איוש בלבד                        │  ← P1, Checkbox min-h-11, §2.6
  └──────────────────────────────────────────────────────────┘

  <section>  h3  ראשון · 8.11                       ← shifts.dayHeading, REUSED VERBATIM
    <section>  h4  משמרת בוקר · <bdi dir=ltr>09:00–14:00</bdi>
      <p>  אחראית משמרת: <bdi>דנה כהן</bdi>
      <p>  מוכרת: 1 מתוך 2   [חסר איוש]             ← Badge variant="warning"
      <p>  תופרת: 1 מתוך 1
      <p>  קבלה: 1                                  ← no target set: a plain count (D10)
      <ul>
        <li> <bdi>דנה כהן</bdi> · מוכרת
             [ ביטול הסימון כאחראית משמרת ]ˢ  [ הסרה ]ᵈ
        <li> <bdi>מיכל ברזילי</bdi> · תופרת  [שובצה בחריגה]
             [ הסרה ]ᵈ
      </ul>
      [ הוספה למשמרת ]ˢ
    <section>  h4  משמרת ערב · <bdi dir=ltr>14:00–20:00</bdi>
      <p> עדיין לא שובצה אף אחת למשמרת הזו.
      …
  <section>  h3  שני · 9.11
    …
```

ᵖ = `variant="primary"` · ˢ = `secondary` · ᵈ = `danger` (§2.0 — the annotation is on the drawing because the drawing is what gets copied, and an unannotated button is a gold one).

**Heading levels are h2 → h3 (weekday) → h4 (shift), and that is a departure from the spec's §Accessibility line** ("each shift `Card` is a `<section>` with an `h3` naming the shift"). The reason is F39's shipped F-19, verbatim: `label` is **free operator text with no uniqueness rule**, and D3's day-carrying auto-labels are replaced the moment she splits a day — so six `h3`s all reading «משמרת בוקר · 09:00–14:00» with nothing distinguishing Sunday from Tuesday is a screen on which the owner rosters the wrong day. The weekday must be a heading, not a caption, because heading navigation is the *only* way to move through 12 shifts without tabbing every control. Recorded as P2. Nothing else changes: the grid is still navigable by heading, one level deeper and unambiguous.

**Weekday `<section>`s render only for weekdays that have templates** — `byWeekday()` is copied from `MyWeekPanel`/`WeekSubmissionsPane`'s shipped shape (three mounts now; it stays a private function in each, because it is four lines and F39 already declined to promote it).

**Shift blocks are `<section>`s inside the one `Card`, hairline-separated — not twelve `Card`s.** Twelve `p-6` boxes is 576px of padding alone inside a 720px column; F39's §5 already ruled the same shape for the templates pane and F35 before it.

### 2.2 Not `Card` per shift, and not a `<details>` per weekday

The honest cost of §2.1 at 375 is a long page: twelve shifts × (h4 44 + manager line 22 + up to three coverage lines 66 + up to three wrapped assignment rows ~200 + add button 44 + gaps) ≈ **4,000–5,000px of scroll**. Stated rather than hidden, because a design that calls that "responsive" is claiming something it has not measured.

**Rejected — collapsing each weekday into a `<details>`.** It halves the scroll and hides the exact thing she is here to find: a shortage inside a collapsed day is invisible, and the failure is silent («I published and missed one» is the *stated* failure mode). `<details>` is also not in `packages/ui` and its open/closed state is a second thing to get wrong under RTL.

**The scroll is managed by P1 instead** (§2.6): the filter cuts the list to the shifts that still need work, which is the same reduction, chosen by her, with nothing hidden that she has not been told about.

**Rejected — a weekday jump bar, and this is the considered answer to "heading navigation only serves the screen-reader user."** The objection is that a rotor user reaches Friday in one jump while §0.1's sighted, phone-holding owner thumb-scrolls past every earlier day, so the design names a cost it does not close. It is declined on the shape of the task:

- **On the first pass — the pass the 4,000px estimate describes — she is not seeking Friday.** She is building an empty week, which means visiting **every** shift in day order, top to bottom. That is exactly what a scroll gives her, and a jump control offers nothing: there is no shift to skip. Travel time is not the failure §0.1 names; «I published and missed one» is, and skipping days is the mechanism that causes it.
- **The seek-to-Friday case arises on a second pass, over a partly-built week — which is precisely when P1 works.** The critic's own argument concedes that the held set does not shrink an empty week; it also concedes, by the same reasoning, that it *does* shrink a partly-built one. The two mechanisms cover disjoint passes, in the right order.
- **The cost is not small.** Seven day controls at `min-h-11` is ~88px of permanent header chrome at 375 — on the pane whose entire problem is vertical budget — plus a focus-move-on-in-page-navigate surface this console has never shipped, on a pane that already carries two named focus exceptions. Buying four thumb flicks on a once-a-week task with that is the trade this section exists to refuse.

The cost stays stated rather than closed, which is the honest position: it is a known, bounded, once-a-week cost with no fix that is cheaper than the cost.

### 2.3 The shift block — rows, never chips

The spec's §Component behaviour says "its assigned staff as removable chips." ⚠ **A removable chip is an icon-only control.** A pill with an `×` is exactly what DL20 and `ConsoleShell.tsx:53-68` forbid — *"the console ships no icon-only control; the visible Hebrew word IS the name"* — and an `×` glyph sized for a chip is nowhere near 44px. Drawn as a **`<ul>` of rows**, one `<li>` per assignment:

`<bdi>{display_name}</bdi>` · muted role word (`roleLabelKey(role)`, `lib/roles.ts`, never a second Badge) · `Badge variant="warning"` «שובצה בחריגה» **only when `override_of_state !== null`** · the manager control when applicable (§2.5) · `Button variant="danger" size="md"` «הסרה».

- **`variant="danger"` on remove**, `StaffSection.tsx:342-352` / `ShiftTemplatesPane`'s shipped destructive pattern — **and no confirm `Modal`.** Removing an assignment from an unpublished or published draft is one tap to undo (she re-adds her), it destroys nothing but a row, and F39's Modal-animation finding makes every avoidable dialog an a11y measurement cost. The confirm in `ShiftTemplatesPane` exists because a template edit **deletes other people's submitted answers**; this deletes nothing of anyone's.
- ⚠ **The remove button's accessible name must carry the shift as well as the person.** «הסרה — דנה כהן» is the shipped F38/F57 disambiguator and it is **not enough here**: Dana appears on four shifts, so a rotor listing the pane's buttons shows four identically-named controls. `shifts.removeAssignmentAria` = «הסרה — {{name}} ממשמרת {{shift}}», where `{{shift}}` is `«ראשון · משמרת בוקר»`. Same reasoning for `shifts.addToShiftAria` — twelve «הוספה למשמרת» buttons otherwise. This is the first screen in the console where the same person is a control on twelve different rows, which is why the shipped disambiguator does not carry over.
- **A long Hebrew name never truncates.** The row is `flex flex-wrap items-center gap-2`, the name is a bare `<bdi className="break-words">` and the badge and buttons follow in flow. FloorPanel's shipped law: *"no truncation and no ellipsis on a display name, ever — a panel that abbreviates a colleague's name makes two colleagues look like one."* At 375 the controls wrap onto the line below the name.
- **Empty shift**: no `<ul>`, one muted `<p>` `shifts.emptyShift` «עדיין לא שובצה אף אחת למשמרת הזו.» — **not** an `EmptyState` (that is a 12-times-per-page block of centred chrome for a fact that is one sentence long, and a shift with nobody on it is publishable and often correct).

### 2.4 Coverage lines — sparse, ordered, and never colour

One line per role, built from `coverage_targets` ∪ `assigned_by_role` (both on the wire, both server-computed), rendered in **`ROLE_OPTIONS` order** (`lib/roles.ts`, derived from `ROLE_LABEL_KEY`) so the lines sit in the same order on every one of the twelve shifts:

| Case | Render | Short? |
|---|---|---|
| role has a target | `shifts.coverage` «{{role}}: {{assigned}} מתוך {{target}}» + `Badge variant="warning"` «חסר איוש» when `assigned < target` | yes, when short |
| role has assignments and **no** target | `shifts.coverageNoTarget` «{{role}}: {{total}}» — a plain count, no «מתוך», no Badge | never |
| role has neither | nothing | — |

- ⚠ **`shifts.coverage` gains the role word, and that is a ✎ redraft of a spec row.** The spec's «{{assigned}} מתוך {{target}}» is unreadable the moment a shift has two coverage lines, which is the ordinary case — two bare `1 מתוך 2` lines under one heading name nothing. §9.0(a) is satisfied: it is label-then-number and there is no plural noun after a numeral.
- **A missing key is not `0`.** D10's sparse map is honoured on screen: absent ⇒ a plain count (or nothing), `0` ⇒ «מוכרת: 0 מתוך 0», which reads oddly and is exactly right — she said *deliberately nobody* and nobody is assigned.
- **«חסר איוש» is a WORD, never a colour.** `Badge variant="warning"` is redundant reinforcement that survives greyscale — `lib/booking.tsx`'s shipped law, and an a11y requirement rather than a preference.

### 2.5 The shift-manager slot

The slot is a property of **an assignment that already exists** (`roster_assignments.is_shift_manager`), so the control lives on the assignment rows and the answer lives on one line above them:

- `shifts.managerLine` «אחראית משמרת: <bdi>{{name}}</bdi>» when the slot is filled; `shifts.managerNone` «לא נבחרה אחראית משמרת.» when it is not. **The gap is a sentence, not an absence** — "no manager on this shift" is a thing she must notice before publishing, and a blank line says nothing.
- When the slot is **empty**: every assigned staffer with `shift_manager_eligible` gets `Button variant="secondary" size="md"` «סימון כאחראית משמרת».
- When the slot is **filled**: only the holder's row has a control, `Button variant="secondary" size="md"` «ביטול הסימון כאחראית משמרת». Swapping is therefore clear-then-set: **two deliberate acts, each a single visible write.**
  ⚠ **Deliberately not one control that does two writes.** The partial unique index makes the second setter 409; a `Select` that silently cleared the incumbent and then set the new holder would, on a failure between the two, leave the shift with no manager at all and tell her nothing. Clear-then-set makes `409 SHIFT_MANAGER_SLOT_TAKEN` **unreachable through this UI**, which returns it to being what it was designed as — the concurrency guard for two managers building the same week.
- **Nobody eligible anywhere** (D12's fresh-boutique case): `shifts.managerNoneEligible` renders **once, in the pane's header block** — never once per shift. Twelve copies of «אף אחת מהצוות אינה מסומנת כמתאימה לניהול משמרת. אפשר לסמן במסך צוות.» is the same repetition defect §6.2 removes from the floor board. In that state the per-shift `shifts.managerNone` line still renders (the fact is still true per shift) and no row carries a set control.
- ⚠ **This needs `POST /manage/shifts/roster/assignments` to be an UPSERT on the live `(roster, template, staffer)` triple** — see F-2. There is no other route that can move `is_shift_manager` on an existing row, and without it "make Dana the manager" costs a `DELETE` + a `POST`: two audit rows, a window in which she is not on the shift at all, and the silent loss of her `override_of_state` stamp.

### 2.6 P1 — the shortage line and the filter

**The standing line**: `shifts.shortageCount` «משמרות שחסר בהן איוש: {{total}}», `role="status"`, derived client-side (a shift is short iff some role in its `coverage_targets` has `assigned < target`), recomputed on every write.

- **It renders only when at least one template in the week carries a target.** With no targets anywhere the count is structurally 0 and «כל יעדי האיוש מולאו» would be a claim about nothing. When targets exist and none is short: `shifts.shortageNone` «כל יעדי האיוש מולאו.»
- **A missing shift manager is deliberately NOT counted here.** A coverage target is something the owner set — an expectation she is failing. A shift with no manager may be entirely intentional on a quiet Tuesday morning, and D12 guarantees that on a fresh boutique *nobody is eligible at all*, so counting it would park a permanent «5 problems» banner on the screen of every boutique that has not yet ticked a checkbox on «צוות». Two counters would also be two numbers competing to be the one she watches.

**P1 — `Checkbox` «הצגת משמרות שחסר בהן איוש בלבד»**, `packages/ui`'s shipped `Checkbox` (its `<label>` is already `min-h-11`, so the 44px floor comes free). It is the single control that makes §2.2's 4,000px scroll workable, and it is the only control on this pane the spec does not name.

⚠ **P1 renders under exactly the same condition as the count line — at least one template in the week carries a target — and this gate is not optional.** `shift_templates.coverage_targets` ships `NOT NULL DEFAULT '{}'` (spec, data model) and D10 makes targets optional, so on a boutique that has never filled one the "is short" predicate is **structurally false for every shift, forever**. Ungated, the failure is silent and total: a fresh boutique's owner opens «סידור עבודה», sees twelve shifts and one checkbox, ticks it, and **every weekday `<section>` disappears** — no shifts, and no count line either, because §2.6's own rule already suppressed it. Nothing on the screen distinguishes that from a load bug, nothing tells her to untick, and the blank pane is visually identical to "I've filled every target." A control whose predicate cannot be true on this tenant must not be on this tenant's screen. Gated, the checkbox and the count line appear and disappear together, which is also the honest read: **both are answers about targets, and a boutique with no targets has no question.**

**And when the filter empties the list legitimately** — targets exist, none is short — the pane renders the count slot's `shifts.shortageNone` «כל יעדי האיוש מולאו.» with no weekday `<section>`s below it and P1 still ticked and reachable. That is state **E6** in §2.8. No new key: the sentence that explains the empty list is the same sentence that was already true.

⚠ **The filtered set is captured when the box is ticked, and does not re-evaluate on every write.** Live filtering has a concrete failure: she assigns the last missing woman to «משמרת בוקר», the shift stops being short, the whole `<section>` unmounts **while her dialog is open inside it and her finger is on the next control** — focus to `<body>`, the dialog's return target gone, and the list reflowing under her hands on every single assignment. Holding the set (one `useState<string[] | null>`) means the list is stable for the whole pass, completed shifts stay visible with their «חסר איוש» badges gone, and un-ticking then re-ticking is how she takes a fresh cut. The **count line still updates live**, so she watches the number fall without the page moving.

⚠ **Ticking P1 does not change the count, so the count cannot be the filter's voice.** The number of short shifts is identical before and after — filtering changes *which shifts render*, not how many are short — and a live region whose text does not change never fires. Left as-is, a screen-reader user hears the checkbox's own "checked" and then nothing at all while nine of twelve `<section>`s leave the DOM under her heading rotor. So the count region carries **a second line while the box is ticked**: `shifts.shortageFilterOn` «מוצגות משמרות שחסר בהן איוש בלבד.», added on tick and removed on untick. The region's text changes in **both** directions, so both are announced, and the same sentence is the sighted reader's reminder of why the list is short. One new key, no new region.

### 2.7 Publish — the act, the confirm that does not exist, and what changes

One `Button size="md"` in the header block: `shifts.publish` «פרסום הסידור» when `published_at === null`, `shifts.republish` «פרסום מחדש» otherwise.

**No confirm dialog** (spec, §Component behaviour). The reasons hold and are worth stating because publishing 12 shifts feels like it wants one: publishing is **idempotent and reversible by editing** (D7 — a published week stays editable and edits land immediately), there is no unpublish to strand her in, and F39's `Modal`-animation finding makes every avoidable dialog an a11y measurement cost.

**What stands in for the confirm is placement, and the DOM order is therefore load-bearing.** The shortage line (§2.6) sits **immediately above the publish button** — §2.1's drawing shows it in that order and §10's keyboard order repeats it, because a builder copies the drawing and the drawing is the only artefact that can put this wrong. ⚠ **Publish above the count is the defect this whole paragraph exists to prevent**: a keyboard or screen-reader user reaches «פרסום הסידור» without the count ever having been read or spoken, and a sighted owner on a 375px phone has it below the fold — which ships the feature with no confirmation *and* no working substitute for one, i.e. exactly the «I published and missed one» failure §0.1 names as the pane's reason to exist. Order is **count → publish → P1**: the number she is publishing *with* is the last thing before the control, and the filter sits with the list it governs. Publish never consults the count (pre-decided #40: flagged, never blocked) and never blocks — that is the product decision — but she cannot press the button without the count having been in her eye.

**What changes visibly, in order:**

1. The header line flips from `shifts.rosterDraft` «טיוטה. הסידור אינו גלוי לצוות ואינו קובע מי במשמרת.» to `shifts.rosterPublished` «פורסם ב־{{date}} בשעה {{time}} על ידי <bdi>{{name}}</bdi>.»
2. The button's label flips to «פרסום מחדש».
3. `<span role="status">` `shifts.publishDone` «הסידור פורסם.» appears beside the button — the house save-cue shape (`MyWeekPanel`'s `common.saved`), cleared by the next edit.
4. **On a screen she is not looking at**: every staffer's `MyWeekPanel` published block (§4) stops saying «טרם פורסם» and lists her shifts.
5. **On the floor board**, within one ~5s tick: every card gains an on-shift line and the week-level «אין סידור עבודה» line disappears (§6.5).

**Focus does not move.** The button survives its own press — only its label changes — so the browser's behaviour is correct and a manual move would be the defect. That is the default rule and it is stated here because publish *feels* like a flow that should move focus. The header line is a plain `<p>`; the announcement is the save-cue span, which is why the pane does not need a third live region (§10).

**A republish that changes nothing writes nothing** (D7's no-op rule). The pane still shows the cue: telling her «nothing happened» when the outcome she wanted is the outcome that holds would be telling her she was wrong when she was right — `floor.breakStartedCue`'s shipped F-ok/F-noop argument, verbatim.

### 2.8 States — every one of them

| # | State | What she sees |
|---|---|---|
| **L** | loading | `Skeleton variant="text" lines={6}` inside the Card, the `h2` above it. No announcement — the heading already named the screen. F39 §1.2's contract, and `RosterPane` is its **fifth** pane |
| **D** | default, draft | §2.1, header line `shifts.rosterDraft` |
| **D-p** | default, published | identical, header line `shifts.rosterPublished`, plus `shifts.rosterEditedSincePublish` when `edited_since_publish` |
| **E1** | **no templates at all** | `RosterPane` **does not render** — `ShiftsSection`'s first-run `if` has already collapsed the section to `ShiftTemplatesPane`. No empty state is drawn, and none should be |
| **E2** | templates exist, **nobody submitted availability** | ⚠ **not an empty state, and not a block.** Every shift renders with `shifts.emptyShift`; the dialog lists everyone at «לא נרשם»; the owner builds the week anyway. One muted line in the header block, rendered iff every `RosterStaffRef.states` is empty: `shifts.noSubmissionsWeek` «אף אחת מהצוות לא סימנה זמינות לשבוע הזה. אפשר לשבץ בכל זאת.» A boutique that never uses F39 is a supported boutique |
| **E3** | templates exist, week untouched | ordinary default — twelve empty shifts is the correct Wednesday render |
| **E4** | **nobody `shift_manager_eligible`** | `shifts.managerNoneEligible` once in the header block (§2.5) |
| **E5** | **no live staff** | unreachable: the signed-in actor is herself in `list_live`, so `staff[]` is never empty. Stated so nobody draws it |
| **E6** | **P1 ticked, nothing short** | ⚠ the one filtered-empty render, and it must not read as a load bug. `shifts.shortageNone` «כל יעדי האיוש מולאו.» in the count slot, `shifts.shortageFilterOn` beside it, **zero weekday `<section>`s**, P1 still ticked and reachable. No new key and no `EmptyState` — the sentence that was already true is the explanation |
| **E7** | **no coverage target anywhere in the week** | ⚠ **the count line and P1 both absent** (§2.6). The pane is the twelve shifts and the publish button, and «חסר איוש» never appears on any of them. This is the default render on a boutique that has not used D10, and it is correct: no targets, no shortage question, no control that answers one |
| **S** | published | §2.7 |
| **F1** | load failure | `role="alert"` `shifts.loadFailed` + `Button secondary md` `shifts.retry`, in the Card, `h2` retained. Immediate and unconditional, first render as on every retry |
| **F2** | write rejected | §2.9 |
| **X** | role changed mid-session / session died | the console's shipped 401/403 path. Nothing F40-specific to word |

### 2.9 Write failures — the four new codes, mapped by hand

`MAPPED_CODES` on `RosterPane`, `StaffSection.tsx:18-23`'s shipped shape. ⚠ **`SPEC_ERROR_CODES` in `test_shifts_api.py` is a Python set checked against Python and cannot catch an unmapped code** (F39's own recorded note) — an eighth code renders the server's English sentence, right-aligned, in a Hebrew console, on a green build.

| Code | Rendered | Extra behaviour |
|---|---|---|
| `AVAILABILITY_CONFLICT` 409 | `shifts.errors.availabilityConflict` | should be **unreachable through this UI** — §3.4's second tap always carries `acknowledge_override: true`. Mapped anyway, because "unreachable" is a claim about the client |
| `NOT_SHIFT_MANAGER_ELIGIBLE` 400 | `shifts.errors.notEligible` | refetch — her eligibility changed on «צוות» under this pane |
| `SHIFT_MANAGER_SLOT_TAKEN` 409 | `shifts.errors.managerSlotTaken` | **refetch.** Another elevated actor filled it; the screen and the flow must not disagree |
| `COVERAGE_TARGET_INVALID` 400 | `shifts.errors.coverageTargetInvalid` | on `ShiftTemplatesPane`, not here |
| `WEEK_OUT_OF_RANGE` 400 | `shifts.errors.weekOutOfRange` — **F39's, reused verbatim** | refetch to the server's default week |
| `NOT_FOUND` 404 | `shifts.errors.notFound` — **F39's, reused verbatim** («המשמרת או אשת הצוות כבר לא זמינות. הרשימה תתוקן בעדכון הבא.») | refetch |
| `NOT_AUTHORIZED` 403 | ⚠ **`shifts.errors.rosterNotAuthorized` — a NEW key** | see below |

⚠ **The 403 may not borrow F39's key.** `shifts.errors.notAuthorized` reads «אין הרשאה **לרשום זמינות עבור אשת צוות אחרת** כרגע» — a sentence about the on-behalf availability write, which is not what was refused. It follows `board.accessEnded`'s shape (the owner named as who to **ask**, never as the gate, which `i18n.test.ts`' «no role in a 403 body» guard also requires) and the new row follows it verbatim in structure.

All write failures render in **one `role="alert"` line inside the pane**, under the header block, never per shift — twelve possible alert slots is twelve places to look for one sentence.

### 2.10 The week pager, and the three kinds of week

Two `Button variant="secondary" size="md"` — **words, not chevrons** (DL20; and there is no directional glyph to get backwards in RTL) — reusing `shifts.prevWeek` / `shifts.nextWeek` and **`FIRST_OFFSET` / `LAST_OFFSET` from `lib/week.ts` verbatim**. The roster read defaults to F39's `default_week_start` (**next** week) and uses `assert_readable_week` (±4 around the current week), so the shipped `[-5, +3]` window around that origin is *exactly* this pane's window. No new constant, no new arithmetic.

⚠ **The offset is also how this pane knows which kind of week it is showing, and it must be, because a device clock may not be read.** `lib/week.ts` already states the rule: the origin is the server's default week, not `new Date()`.

| Offset | Week | Extra line |
|---|---|---|
| `≥ 0` | next week onward — the ordinary case | none |
| `= −1` | **the week already in progress** | `shifts.rosterInProgressWeek` «השבוע הזה כבר בעיצומו. כל שינוי משפיע על לוח הקומה מיד.» |
| `≤ −2` | a past week | `shifts.rosterPastWeek` «השבוע הזה כבר הסתיים.» |

**Neither line blocks anything.** D7 is explicit that a running week is not special-cased: publishing it is legal and takes effect immediately, because the owner is stating what is true *now* and refusing her would leave her nothing but the same-day override for the rest of the week. A past week is editable for the same reason the read window is ±4 — she may be correcting a record — and inventing a lock here would be C5's rejected state machine arriving through the front end.

**Paging clears the pane's transient state**: the publish cue, the write alert, and P1's held filter set (which belongs to the week she left). `WeekSubmissionsPane`'s shipped `step()` does exactly this for its expansion, for the same reason.

---

## 3. `RosterCellDialog` — the shift's editor, not an "add" picker

`packages/ui`'s `Modal`, opened by «הוספה למשמרת» on a shift block.

⚠ **`ModalProps.title` is a `string`** (`Modal.tsx:10`), so it cannot carry a `<bdi dir="ltr">` time range. Title is `shifts.cellDialogTitle` «שיבוץ למשמרת»; the shift's identity is the **first line of the body**, composed in JSX — `{DAY_NAMES[day]} · {label} · <bdi dir="ltr">{HH:MM–HH:MM}</bdi>` — and its id is handed to `Modal`'s `describedById` so the dialog announces *which* shift on open.

### 3.1 One control per person, and it flips

```
Modal  h2 (Modal's own)  שיבוץ למשמרת
  <p id=…>  ראשון · משמרת בוקר · <bdi dir=ltr>09:00–14:00</bdi>
  <p role="status">                                  ← the CUE region: assign/remove only, §3.1
  <ul>
    <li> <bdi>דנה כהן</bdi>  שובצה · מוכרת · שובצה השבוע: 3        [ הסרה ]ᵈ
    ────────────────────────────────────────────────────────────
    <li> <bdi>שירה לוי</bdi>  מעדיפה · מוכרת · שובצה השבוע: 1      [ הוספה ]ˢ
    <li> <bdi>Ronit Bar</bdi> זמינה · קבלה · שובצה השבוע: 4        [ הוספה ]ˢ
    <li> <bdi>נועה כץ</bdi>   לא נרשם · תופרת · שובצה השבוע: 0     [ הוספה ]ˢ
    <li> <bdi>מיכל ברזילי</bdi> לא זמינה · תופרת · שובצה השבוע: 2  [ הוספה ]ˢ
         <p role="status"> …סימנה שאינה זמינה…      ← the WARNING, IN THE ROW, §3.4
  </ul>
```

ᵖ = `primary` · ˢ = `secondary` · ᵈ = `danger` (§2.0). Every one of these buttons takes `loading` while its write is in flight.

⚠ **The dialog has TWO `role="status"` nodes, not one, and the override warning is the one that lives in the row.** An earlier draft of this section put the warning in the top region to keep the dialog to a single region; that is the wrong trade and its failure is concrete. In a 448px modal on a 375px phone, arming row 5 of 8 would paint the sentence above her scroll position while the button that just changed to «שיבוץ בכל זאת» is under her finger: she sees a label change with **no visible reason**, taps again, and the second tap is the write. That is D11's «never a slip» defeated by the very mechanism meant to enforce it. **The warning must be adjacent to the button whose meaning it changed.**

Two regions is not a cost here, because **they cannot fire together.** Arming a row writes nothing and produces only the warning; any write clears the arm (removing text from a region announces nothing) and produces only the cue. The sequences are mutually exclusive in time, so there is never a competing announcement — which was the only real reason to want one region. §3.4's «at most one row in confirm state» keeps its own, independent justification: two armed rows is two half-committed overrides on one screen, and no way to tell at a glance which «הוספה» is still a first tap.

**The button flips «הוספה» ⇄ «הסרה» in place, and nothing unmounts.** This is the single structural decision in the dialog and it buys three things at once:

1. **No focus exception.** A dialog that removed the row it just assigned would drop focus to `<body>` on every single assignment — the most repeated act in the feature — and would need F39's `ref` + `tabIndex={-1}` rescue twelve times a session. The control surviving its own press is the house default and the reason there is nothing to rescue.
2. **A mis-tap is withdrawable without closing anything** — the same argument F39 made for its fourth radio, applied to a button.
3. **The dialog states the shift's current roster before it offers options**, which is what an editor does and a picker does not.

Assigned rows sort **first**, marked `shifts.cellAssigned` «שובצה» in muted words (not a Badge — the row already carries a state word and F36's one-pill law applies). Removing from the dialog and removing from the shift block are the same act reaching the same route; both paths exist because opening a dialog to undo a mis-tap you can see on the page behind it is a tax.

### 3.2 The sort is the design

Below the assigned block: **`preferred` → `available` → not answered → `unavailable`**, and stable in the server's `staff[]` order within each bucket so the list does not reshuffle from shift to shift.

Her state renders as a **word**, reusing F39's shipped strings: `shifts.states.preferred` «מעדיפה» / `shifts.states.available` «זמינה» / **`shifts.stateUnanswered` «לא נרשם»** / `shifts.states.unavailable` «לא זמינה».

⚠ **«לא נרשם», not the spec's «טרם הגישה».** `shifts.notSubmitted` «טרם הגישה» is a fact about *the person* — she has not submitted at all — and it is `WeekSubmissionsPane`'s Badge. Here the fact is about *this shift*: a staffer who answered eleven of twelve shifts and left this one blank has emphatically «הגישה». F39 minted `shifts.stateUnanswered` for exactly this per-shift absence and mounts it twice already. This removes a key from the spec's deck rather than adding one.

**No per-state colour, on any of the four.** F39's `ShiftAvailabilityFieldset` records the kill in full: `--color-danger` is reserved for something the owner must **fix** and «לא זמינה» is a settled fact, not a fault; and four hues would make hue the carrier of meaning inside a list whose rows are already four words.

### 3.3 The week count — the row read, without a matrix

`shifts.cellWeekCount` «שובצה השבוע: {{total}}», muted, on every row. Counted client-side across `RosterWeek.shifts[].assignments[]` — **no wire change, no second read**.

This is where §1's "row read" lands, and the placement is the point: the question *"is Dana already on four shifts?"* only ever matters at the instant the owner is about to make it five. A number on the row she is looking at answers it in place; a matrix answers it two screens away and asks her to hold the answer in her head. §0.3 binds it: this is a **count of shifts**, never a sum of hours, and it carries no threshold, no warning colour and no cap.

### 3.4 Assigning against «לא זמינה» — two taps, inline, never a nested dialog

Tapping «הוספה» on an `unavailable` row **writes nothing**. That row reveals, inline:

- `shifts.overrideWarning` «<bdi>{{name}}</bdi> סימנה שאינה זמינה במשמרת הזו. השיבוץ יירשם כחריגה.»
- the button's label swaps to `shifts.assignAnyway` «שיבוץ בכל זאת».

The second tap is the write, with `acknowledge_override: true`. **Every other row is one tap.** That is D11 kept literally — *"an override is always a second, deliberate act, never a slip"* — at the cost of one tap on the rows that deserve it and zero on the rest.

- ⚠ **Inline, never a `Modal` inside a `Modal`.** This console ships no nested dialog; a second focus trap inside the first is a pattern with no precedent here and no way to test cheaply.
- **At most one row can be in confirm state.** Tapping «הוספה» on another row clears the first. Two armed rows is two half-committed overrides on one screen with no way to tell at a glance which «הוספה» is still a first tap.
- **The warning carries `role="status"` and renders INSIDE THE ROW**, immediately under the name and above/beside the button whose label it just changed (§3.1). It is the announced consequence of her tap, and focus stays on the button (which is why relying on the button's changed accessible name would be unreliable: no focus change occurs to trigger a re-announcement). ⚠ **It is not written to the dialog's top cue region** — see §3.1 for the failure that placement produces.
- ⚠ **A shift nobody can cover.** When every un-assigned staffer sits in the `unavailable` bucket, the dialog renders `shifts.cellAllUnavailable` «כל מי שהגישה סימנה שאינה זמינה במשמרת הזו.» above the list. Without it she reads eight names, taps one, and only then discovers that every option is a refusal. The pane still does not block, and the override path is still the answer — but she is told before she starts, not after.

### 3.5 The stale stamp — the case that costs a no-show

`override_of_state` is stamped **at assignment time** and never updated (spec, data model). F39's week stays writable until the deadline, and an elevated actor may write past it. So this sequence is ordinary:

> Sunday: Michal marks «זמינה» for Thursday evening. Monday: the owner rosters her. Tuesday: Michal changes her answer to «לא זמינה».

The assignment row's `override_of_state` is `null` — correctly, nothing was overridden — and the live `RosterStaffRef.states[template_id]` now says `unavailable`. **Both facts are already on the wire.** The shift block renders:

- the `Badge` «שובצה בחריגה» **from the stamp**, because that is the record of what the owner knowingly did; and
- when the stamp is `null` **and** the live state is `unavailable`, one muted line on that row: `shifts.unavailableAfterAssign` «<bdi>{{name}}</bdi> סימנה שאינה זמינה אחרי השיבוץ.»

Two different facts, two different renders, neither overwriting the other. This is the one edge in the feature that the data model already anticipates and that a build reading only `override_of_state` would render as a perfectly healthy shift.

---

## 4. `MyWeekPanel`'s published block — every role, read-only

A block inside `MyWeekPanel`'s existing `Card`, `h3` `shifts.myRosterHeading` «המשמרות שלי», **above the answering form and below the week bar**, from `ShiftWeek.roster_published` + `rostered_template_ids[]`.

```
Card  h2  הזמינות שלי
  week bar  [השבוע הקודם] [השבוע הבא]  <p role="status"> שבוע 8–14 בנובמבר
  ── h3  המשמרות שלי ─────────────────────────────────────
     <ul>  ראשון · משמרת בוקר · <bdi dir=ltr>09:00–14:00</bdi>
           חמישי · משמרת ערב  · <bdi dir=ltr>16:00–21:00</bdi>
  ── hairline ────────────────────────────────────────────
  <p> מועד ההגשה: יום רביעי, 4.11, 18:00
  …the four-radio form, unchanged…
```

**Order**: the week bar governs both blocks (they are both about the displayed week), so it stays first. Then the fact she came for — *when do I work* — then the task. Three distinct states, because D5 says they are three distinct facts:

| Wire | Rendered |
|---|---|
| `roster_published === false` | `shifts.myRosterUnpublished` «סידור העבודה לשבוע הזה טרם פורסם.» |
| published, `rostered_template_ids` empty | `shifts.myRosterNone` «לא שובצת למשמרות בשבוע הזה.» |
| published, non-empty | a `<ul>` of `{DAY_NAMES[day]} · {label} · <bdi dir="ltr">HH:MM–HH:MM</bdi>`, in `(day, sort_order, starts_at_time)` order — the server's, unchanged |

- ⚠ **No hour totals, no «סה"כ», no count of shifts.** §0.3, on the surface most tempting to add one to.
- **No control of any kind.** She cannot accept, decline, swap or acknowledge a shift; D13 puts self-service on-shift marking out by name, and a button here would be the attendance punch the epic's labour-law row forbids.
- ⚠ **The default week is the wrong week for this block, and that is an accepted cost.** `GET /manage/shifts/week` defaults to **next** week — the week she is here to *answer* — so on a Monday her published *current* week is one «השבוע הקודם» tap away and the default view honestly reports «טרם פורסם» for a week nobody has built yet. The pager is already at the top of the Card and is the whole remedy; changing the default would break F39's shipped, pinned contract for the higher-volume act. Recorded as O2 so the next reader finds the argument rather than a silence.
- **Heading levels**: Card `h2` → this `h3` → the weekday `h3`s of the form below. Same level, two siblings, nothing skipped.

---

## 5. `ShiftTemplatesPane` — coverage targets on the existing draft panel

The draft panel (`ShiftTemplatesPane.tsx:375-433`) gains a `<fieldset>` after `TimeField(שעת סיום)`:

```
<fieldset>  <legend>  יעדי איוש
  grid-cols-1 sm:grid-cols-2  gap-3
    [ בעלת הבוטיק   ][ אחראית משמרת ]     ← each Input carries help=
    [ קבלה          ][ מוכרת        ]        «שדה ריק — אין יעד. אפס — במפורש אף אחת.»
    [ תופרת         ]
```

⚠ **The help line is a prop on every one of the five `Input`s — it is NOT one paragraph under the `<legend>`.** `Input` builds `helpId` from its own `useId()` and links it with `aria-describedby` **per field** (`Input.tsx:21-24, 30-35`); a `<p>` at fieldset level is linked to nothing. Drawn the other way, a screen-reader user tabbing into «מוכרת» hears the legend and the label and **never the one rule that makes the control usable** — so she clears the field intending «אף אחת», writes an absent key instead of `0`, and the shift renders a plain count with no «חסר איוש» badge for a role she believed she had zeroed. §9.6's stated mitigation is «announced at capture», and only the `help` prop delivers it.

The visible cost is the sentence repeated five times in `text-xs text-ink-muted`. That is accepted, for two reasons: `Input` overwrites a caller-supplied `aria-describedby` (it sets the attribute *after* `{...rest}`), so a shared node cannot be linked without a `packages/ui` change §8 rules out; and five muted 6-word lines in a two-column grid read as field hints, which is what they are.

- **One `Input type="number"` per member of `ROLE_OPTIONS`**, label = `t(ROLE_LABEL_KEY[role])`, `min={0} max={MAX_COVERAGE_TARGET}` (= 20), `inputMode="numeric"`, `className="min-h-11"` so a five-field block on a phone meets the 44px floor without touching `packages/ui`. Driving it off `ROLE_OPTIONS` rather than a hand-picked subset inherits `lib/roles.ts`' own guarantee — *"a sixth role appears in both dropdowns the day it is added"* — instead of minting a curated list that silently omits it.
- ⚠ **Empty and `0` are different values and the control must say so.** `shifts.coverageTargetsHelp` «שדה ריק — אין יעד. אפס — במפורש אף אחת.» goes in `Input`'s `help` slot, which `Input.tsx:31-35` links with `aria-describedby`, so it is announced **at capture**. This is D10's sparse map surfaced honestly; a number field where `""` and `0` mean different things and nothing says so is the cheapest bug in this half of the feature.
- **`PATCH` is a full replace of all fields** (F39 D2), so `coverage_targets` is the **sixth required field**: `draftOf(row)` must seed the existing targets or an unrelated label edit silently clears them. `bodyOf(draft)` assembles the sparse map, omitting blanks.
- ⚠ **A targets-only edit opens NO confirm and invalidates nothing.** `isMaterialEdit` reads `day_of_week`, `starts_at_time`, `ends_at_time` and **must not gain a fourth field** — a coverage number changes nothing any staffer answered. Restated here because "add the new field to the material set" is the reflex, and doing it would delete every future submission on the template the first time somebody fixes a target from 2 to 3.
- **Client validation is hardcoded Hebrew in `validation.ts`** (F51's rule, `validateShiftTemplate`'s shipped precedent) mirroring the server bound; `COVERAGE_TARGET_INVALID` maps to `shifts.errors.coverageTargetInvalid` for anything that reaches the server anyway. ⚠ **The bound is interpolated from the constant, not typed into the sentence**: `` `יעד האיוש חייב להיות מספר שלם בין 0 ל־${MAX_COVERAGE_TARGET}.` ``. F51's rule is about *where the string lives* (in `validation.ts`, not the i18n deck) and a template literal satisfies it; `test_frontend_constant_parity.py` greps the `export const NAME = <digits>;` line and is untouched. The alternative is the defect §9.8 rejects for the server-side row and then reproduces here: O3 calls `MAX_COVERAGE_TARGET = 20` a fat-finger guard rather than a product rule, so it will be changed, and the day it becomes 30 the owner typing 25 is told «בין 0 ל־20» by the client and «בין 0 ל־30» by the server, on the same field in the same session. One rule, one bound, one source.

---

## 6. `FloorPanel` — the rule label, the override, and the claim that is demoted

### 6.1 The label, and it is the same for everyone

`StaffCard` gains `on_shift` and `on_shift_source`. The card gains **one line under the status `Badge`**, built as **two elements with the console's shipped « · » between them — never one interpolated sentence** (`FloorPanel.tsx:904-914`'s stated rule):

```
<p className="text-sm text-ink">
  {t(card.on_shift ? "floor.onShift" : "floor.offShift")}
  {" · "}
  {t(ON_SHIFT_SOURCE_KEY[card.on_shift_source])}
</p>
```

`ON_SHIFT_SOURCE_KEY: Record<OnShiftSource, string>` lives in **`lib/onShift.ts`** with **no fallback** — `lib/roles.ts`' argument verbatim, and F57's recorded near-miss (a two-branch ternary that printed «אחראית משמרת» for every seamstress) is the reason. A fourth source is a compile error here rather than a wrong Hebrew word that ships silently.

| `on_shift_source` | `on_shift` | Line |
|---|---|---|
| `roster` | `true` | «במשמרת · לפי סידור העבודה» |
| `roster` | `false` | «לא במשמרת · לפי סידור העבודה» |
| `manual_today` | `true` | «במשמרת · נקבע ידנית להיום» |
| `manual_today` | `false` | «לא במשמרת · נקבע ידנית להיום» |
| `fallback` | always `true` | **nothing on the card** — §6.2 |

**Owner and staffer read the identical line, and that is D8 kept literally.** The board is a shared floor tablet; two women standing at it must not be told different things about the same card. What is role-split is the **control**, not the label (§6.3) — which is exactly F39's shape (her own radios; the on-behalf write for elevated only).

⚠ **An off-shift card is not dimmed, greyed, reordered or moved.** D1: the board **labels and never filters**, and a visual de-emphasis is filtering with the evidence left on screen — plus it would make on-shift-ness a colour, which §10 forbids. `card_status` still wins the Badge: a staffer who is off-shift and standing in room 2 renders `occupied` **and** «לא במשמרת», and D9 says that tuple is the single most useful thing this feature puts on the board.

### 6.2 ⚠ Rule 3 renders nothing on the card, and one line above the list instead

The spec's copy deck gives `floor.onShiftNoRoster` «אין סידור עבודה לשבוע הזה» as a per-card rule label. **Drawn as a week-level line instead, and this is the most consequential departure in the design.**

The failure it removes: a boutique with no published roster renders **eight cards each carrying «במשמרת · אין סידור עבודה לשבוע הזה»** — eight copies of one sentence that says nothing about the person it is attached to, on the screen a seamstress opens twenty times a day. And C1's whole promise is that *"a boutique that never publishes sees **no change at all**"*; eight new lines of text on every card, permanently, is very much a change, and it is the change that makes the honest fallback feel like a nag.

So:

- A card whose source is `fallback` renders **no on-shift line**. "The system has not been told anything" is honestly rendered as silence, not as a sentence asserting she is on shift.
- One muted `<p>` at the top of the staff `Card`, above the `<ul>`, rendered **iff at least one card's source is `fallback`**: ✎ `floor.onShiftNoRoster` «אין סידור עבודה לשבוע הזה. כל מי שלא סומנה ידנית **נחשבת** כמי שבמשמרת.»
  ⚠ **«נחשבת», not «מוצגת» — the clause states the RULE, because it cannot state the display.** This bullet is the one that deletes the display: a `fallback` card renders **no on-shift line at all**. A sentence promising «כל מי שלא סומנה ידנית **מוצגת** כמי שבמשמרת» would then send a shift manager looking under Dana's badge for a «במשמרת» word that is not there, unable to tell "Dana is on shift by fallback" from "the board has no answer for Dana" — and on a board where one colleague *does* carry a manual override, the two card kinds (one labelled, one blank) invite the exactly-wrong reading that the **blank** cards are the undecided ones. This line is the only carrier of rule 3 for a reader who does not know three rules exist, so it must describe what is true of the person, not what is painted on her card.
- A card whose own answer comes from **rule 1 still carries its line**, because that fact *is* per-person and it is the exception the week line just named.

⚠ **This is not the client inferring a rule label** (D8's ban). The client infers *where* to render a server-supplied string, from a server-supplied enum. The derivation is sound: if any card answers `fallback`, rule 2 did not fire, so there is no published roster for today's week. In the (representable, vanishing) case where **every** staffer has a same-day override in an unpublished week, no card says `fallback`, the week line does not render, and every card carries its own manual label — nothing is lost and nothing lies.

The line's placement is inside the staff `Card` and not beside the panel `h2`: the `h2` sits above `SosCentre`, `RoomsPanel` and `WaitlistPanel`, three panels away from the list it would be describing.

### 6.3 The override control — elevated only, beside the break toggle

The card's control area becomes `<div className="flex flex-wrap items-center gap-2 shrink-0">` holding up to three `Button size="md"`:

| Card state | Controls (elevated) |
|---|---|
| `on_shift: true`, source `roster` or `fallback` | break toggle · `floor.markOffShift` «סימון שאינה במשמרת» `secondary` |
| `on_shift: false`, source `roster` | break toggle · `floor.markOnShift` «סימון במשמרת» `secondary` |
| source `manual_today` | break toggle · the contradicting mark button `secondary` · `floor.clearOnShiftOverride` «ביטול הסימון הידני» `ghost` |

- **Exactly one mark button, and its label always contradicts the current answer.** Two buttons («on» and «off») would leave one of them a no-op that still writes a row and an audit entry.
- **Non-elevated sees the line and no control** (D13) — no disabled button, no lock glyph, no «אין הרשאה» line. The absence is cosmetics; the control is the server's gate.
- ⚠ **The mark/clear gate is `ELEVATED.has(role)` ALONE, and it is emphatically NOT `mayToggle`.** `FloorPanel.tsx:867` computes `const mayToggle = isSelf || ELEVATED.has(role);` — the break toggle is **self-or-elevated**, because a seamstress may record her own break. Reusing that variable here (it is the one those lines already compute, which is exactly why the mistake is available) renders «סימון שאינה במשמרת» on a seamstress's **own** card. She taps it; the server refuses `403`; `mutate`'s P-6 rule treats {401,403} as terminal, so by this section's own text the whole floor panel drops to `floor.accessEnded` — **she loses the staff board for the session by pressing a button that should never have rendered**, having attempted precisely the attendance punch D13 and §13 put out of scope («no self-service on-shift marking, anywhere, for anyone»). A **new** `const mayMarkOnShift = ELEVATED.has(role);` beside it, and the two predicates never share a name.
- ⚠ **Per-person accessible names are required and the spec's deck has only the visible labels.** Eight cards × «סימון שאינה במשמרת» is the screen-reader dead end `floor.breakStartAria` exists to close. Three new aria keys, `— {{name}}` shaped, carrying **no markup** (an `aria-label` takes none, so there is nothing to isolate — FloorPanel's own note).
- **The write goes through `mutate()`**, exactly like `toggle`: the poll is suppressed for the request, the panel is patched **from the server's card** and never optimistically, and the re-arm lives in the `.finally()`. ⚠ **Which means the two override routes must return the patched `StaffCard`** (F-1). The client cannot compute the new `on_shift_source` — that is the whole of D8 — so a route answering `204` would force a refetch or a guess, and a guess is the panel disagreeing with itself.
- ⚠ **And, exactly like `toggle`, each write announces itself in the panel's EXISTING cue region.** `toggle` does not only patch the card: it writes `floor.breakStartedCue` / `floor.breakEndedCue` into the panel's one `role="status"` (`FloorPanel.tsx:589` → the keyed `<span>` at `:690`). Three user-initiated writes modelled on it that announce **nothing** would leave a screen-reader user pressing «סימון שאינה במשמרת» and receiving silence — focus stays on the button by design, an accessible-name change does not re-announce without a focus event (§3.4 states that rule itself), the on-shift line silently flips and a third button appears — while the break toggle 2px away speaks on every press. Three cue strings, §9.7, written through the shipped writer with `isolateBidi(text, name)` and a bumped `nonce`, so a repeated cue still replaces the keyed node. **This is not a new region** (§10): it is the region the panel already has, used for the only thing it is allowed to carry — an outcome the viewer asked for.
- **Failure**: the in-card `role="alert"` slot, reusing `floor.error.notFound` verbatim for a 404 (a colleague offboarded between ticks) and `staff.loadFailed` otherwise. **A 403 is terminal for the whole panel** and that is correct rather than a bug: `mutate`'s P-6 rule treats {401, 403} as terminal, the control never renders for a role that would be refused, so the only way to reach it is a role change mid-session — which *is* the terminal case.
- **Focus**: the mark button survives its own press (its label flips) → no move, and the shipped `restoreFocusRef` effect hands focus back after the disabled-while-loading blur. ⚠ **But that effect does not generalise as shipped, and it must be re-keyed before a second button goes on a card.** `controlRefs` is a `Map<string, HTMLButtonElement | null>` keyed by `card.id` (`FloorPanel.tsx:195`) with exactly **one** writer — the break toggle's ref callback (`:962`) — and the restore reads `controlRefs.current.get(pending)?.focus()` (`:377`, `:404`). This section puts **up to three** buttons on a card. Registered unchanged, all three write the same key: the last mounted wins, and React's ref cleanup on «ביטול הסימון הידני» writes `null` into Dana's slot. An elevated user then tabs to «סימון שאינה במשמרת» on Dana's card and presses it — `Button` is `disabled={disabled || loading}`, the browser blurs to `<body>`, and the effect focuses whichever button happens to hold Dana's entry: the **break toggle**, or nothing at all. That also **regresses the shipped break toggle**, whose focus restore has worked since F57.
  **The map is keyed `` `${card.id}:${control}` ``** — `:break`, `:mark`, `:clear` — and `restoreFocusRef` / `reclaimFocusRef` carry the composite key of the control that was pressed. The break toggle becomes `` `${card.id}:break` `` and behaves exactly as it does today; the `busyIds.includes(pending)` guard reads the card id off the key's first segment. One key shape, four call sites, no behaviour change to anything shipped.
  ⚠ **«ביטול הסימון הידני» does NOT survive its own press** — clearing the override moves the source to `roster`/`fallback` and unmounts it. Focus goes to `` `${card.id}:mark` ``, the nearest surviving control in the same group (`ShiftTemplatesPane`'s remove-confirm rescue, same shape). §10's one named exception on this panel.

### 6.4 The demoted claim, and why a stale override cannot become permanent

⚠ **There is no F31 toggle to demote** (C1, verified by grep): F31 shipped the `shift_manager` role member and `/manage` gating and nothing else. What is demoted is **liveness as an implicit on-shift claim** — `list_live` returns every non-deleted staffer and the board renders all of them, which is the product's current, unlabelled answer to "who is on shift."

Where the demoted claim still lives, and what it now says:

1. **It still puts every live staffer on the board, unfiltered.** That is D1 and it is deliberate — `GET /manage/floor` is what a seamstress opens to find out who is in the building, and a colleague who walked in anyway must not vanish from it.
2. **It no longer answers the question.** `deleted_at IS NULL` now means *on the payroll*; the on-shift answer comes from the resolver and arrives **with its provenance attached** (§6.1). The demotion happens on that one line and nowhere else.
3. **A boutique that never publishes and never overrides sees the board it sees today**, plus one muted week-level line (§6.2). That is C1's promise discharged literally.

And the successor toggle — the one F40 actually introduces — cannot go stale:

- **It is scoped to a Jerusalem calendar DATE, not timestamped** (D3/D4). An override for a day that is not today is never consulted, so it is not stale — it is *silent*. There is no clock comparison anywhere to get wrong.
- **At Jerusalem midnight the date stops matching and rule 2 or 3 answers again, with no worker, no scheduled job and no writer.** On screen that is delivered by the panel's existing ~5s poll: an override set at 23:59 still labels the card «נקבע ידנית להיום»; the same row read at 00:01 renders «לפי סידור העבודה» or nothing, on the next tick, with nobody having acted. **No client timer is added** — which also keeps SC 2.2.2 exactly where F57 left it, on the pause control the panel already ships.
- **Within the day it is visible rather than silent**, three ways: the per-card «נקבע ידנית להיום» label; the «ביטול הסימון הידני» control beside it; and one muted line at the top of the staff `Card`, rendered iff at least one card is `manual_today` — `floor.onShiftOverrideNote` «הסימון הידני תקף להיום בלבד ומתאפס בחצות.» **Once per board, never once per card**, for §6.2's repetition reason.
- **An offboarded staffer leaves the board entirely** (`list_live`); her override row survives on the table and is never consulted again. Nothing renders and nothing needs to.

The staff `Card` therefore has a **notes region above the `<ul>`** holding zero, one or two muted lines — the week line first (the fact), the override note second (the exception to it). Both can render at once and each is then true of a different card, which is why the week line's ✎ redraft says «כל מי שלא סומנה ידנית».

### 6.5 What a publish does to this screen

The largest simultaneous repaint the board has ever had, and it arrives from a poll rather than from anything the viewer did: eight cards each gain a ~22px line (≈176px of vertical shift) and the week-level line disappears, within one ~5s tick of the owner pressing «פרסום הסידור» on another device.

**No new code, and the existing mitigation is the right one.** `FloorPanel`'s `holdRef` pointer-hold exists precisely for a repaint that moves controls under a travelling finger, and it consumes the next tick after any `pointerdown`. This is a once-per-week event, it is covered by that hold, and it needs no announcement: the poll may never write to the cue region (spec D12 — a status update every five seconds would announce the whole staff list forever).

---

## 7. Responsive — 375 / 768 / 1440

`ConsoleShell` caps `#console-main` at `max-w-[720px]`, so **768 and 1440 render identically** and the only real breakpoint on these surfaces is `sm` (640). Stated plainly because §1's whole argument rests on it.

| Width | Deltas |
|---|---|
| **375** | Everything single-column; 295px of content inside `Card p-6`. Shift blocks stack; each assignment row wraps to name → badge/marker → controls. Coverage lines wrap the Badge under the count. The week bar wraps to two rows (two buttons, then the range line). Coverage-target inputs are `grid-cols-1`. Dialog rows wrap name → state/role/count → button. `Card`'s baked-in `p-6` is **not** overridden |
| **768** | Content is 720px + gutters; assignment rows and coverage lines come back onto one line; coverage-target inputs go `sm:grid-cols-2`. Nothing else changes |
| **1440** | Byte-identical to 768. The column is centred in cream |

**No horizontal scroll at any of the three**, asserted in the e2e leg — and that assertion is the reason §1 exists. The only overflow risks are a long Hebrew display name beside a Badge and two buttons, and a time range beside a shift label; both wrap, neither scrolls. Numerals are small integers and the one order-breaking run (`HH:MM–HH:MM`, whose en-dash is a neutral) is isolated (§10).

---

## 8. Files — the spec's list, plus two, minus one

Everything in the spec's Frontend Changes table stands, with these adjustments:

| File | Why |
|---|---|
| `components/RosterPane.tsx` | **NEW** — §2. Its own read, its own skeleton, its own alert + retry, its own pager (F39 §1.2's contract, fifth pane) |
| `components/RosterCellDialog.tsx` | **NEW** — §3 |
| `lib/onShift.ts` | **NEW** — `ON_SHIFT_SOURCE_KEY: Record<OnShiftSource, string>`, no fallback (D8) |
| `components/ShiftsSection.tsx` | one pane inserted **inside the `!firstRun` branch**, after `WeekSubmissionsPane` (§2) |
| `components/MyWeekPanel.tsx` | the `h3` published block above the deadline line (§4) |
| `components/ShiftTemplatesPane.tsx` | the coverage-target fieldset; `draftOf`/`bodyOf` carry the sixth field (§5) |
| `components/FloorPanel.tsx` | the on-shift line, the notes region, the override controls, one focus rescue (§6) |
| `lib/guide.ts` | `GUIDE_STEPS.shifts` gains a **third** element — the tuple type is `readonly [string, ...string[]]`, so no `SectionKey` and no `satisfies` change |
| `validation.ts` | `MAX_COVERAGE_TARGET` mirror (parity-tested) + the Hebrew bound message, **interpolating the constant, not a literal `20`** (§5 / F-33) |
| `i18n/he.ts` + `i18n/ar.ts` | §9; `nav.shifts` **renamed**; `ar` = the approved Hebrew standing in, untranslated |
| `api.ts` | the wire types + five roster calls + two override calls; `StaffCard` 8 → 10 keys, `ShiftWeek` + `ShiftTemplate` extended |
| — | **no `lib/week.ts` change**: `DAY_NAMES`, `DAYS_IN_WEEK`, `addDays`, `FIRST_OFFSET`, `LAST_OFFSET` are all reused verbatim (§2.10) |
| — | **no `packages/ui` change and nothing promoted.** Every control here is `Card` / `Button` / `Badge` / `Checkbox` / `Input` / `Modal` / `Skeleton` / `EmptyState` as shipped |

`vite.config.ts` is unchanged (both second segments already proxied). `ShiftAvailabilityFieldset` is **not** reused — the dialog picks people, it does not answer availability.

---

## 9. Copy deck — `he.ts` + `ar.ts` added together, `ar` = the approved Hebrew standing in untranslated (Q3 / #47), never `""`

**Zero exclamation marks** (#5, enforced by `__tests__/i18n.test.ts`). Feminine address throughout. ✓ = **verbatim from the spec's copy table**. ✎ = **a spec row redrafted here on a mechanical or factual defect**, reason stated per row, meaning unchanged; these need approval like any new row. The rest are new.

### 9.0 The four mechanical rules every row obeys

**(a) No plural Hebrew noun after an interpolated numeral, and never the variable name `count`.** The shipped bundle states this twice (`atelier.stageCount`, `atelier.capacity.headingCount`); F39 redrafted five rows on it. House shape is **label-then-number**. Every counting row below is label-then-number and uses `{{total}}`.

**(b) Every interpolated human name is `<bdi>`-wrapped inside the copy value, and its row renders through `<Trans components={{ bdi: <bdi /> }}>`.** ⚠ **Bare `<bdi>`, never `<bdi dir="ltr">`** — an LTR base direction reverses a Hebrew name. Six rows carry a name; four of them are ✎ because the spec's versions do not. **`aria-*` keys are the exception and carry no markup** — an `aria-label` takes none, so `{{name}}` is bare there (`floor.breakStartAria`'s shipped shape).

**(c) Numeral isolation is for runs that contain neutrals, not for bare integers.** `HH:MM–HH:MM` gets `<bdi dir="ltr">` because the en-dash is a direction-neutral that reorders. A bare integer between Hebrew words does **not**, and this is the shipped bundle's own practice: `shifts.answered` («נענו: 9 מתוך 12») and `shifts.submittedCount` both render unisolated in merged code, as does `shifts.deadline`'s `{{time}}`. Stated because the spec's a11y line reads "every numeral run" and a literal reading would red shipped lines.

**(d) A rule label and a state word are never a colour.** Every row below that reports a state is a word first; a `Badge` variant is redundant reinforcement.

### 9.1 Nav + guide

| Key | Hebrew | EN annotation |
|---|---|---|
| `nav.shifts` ✓ | משמרות | **renamed** from «זמינות למשמרות» (D17): the row now leads to two jobs and the old label names one. ⚠ **Six edits, not three, and two of them are the ordering assertions.** `grep -rn "זמינות למשמרות" apps/manage/src` returns: `i18n/he.ts:2671`, `i18n/ar.ts:1013`, `__tests__/i18n.test.ts:1880` (`expect(i18n.t("nav.shifts")).toBe(…)`, inside the HE_F39 block), and `__tests__/Nav.test.tsx:127`, **`:214`** and **`:235`** — the last two being `expect(navItems()).toEqual([…])` themselves. An earlier draft of this row claimed the ordering assertions were untouched; they are not, and this is the one copy row flagged for user approval, so the gate must see the real cost. The **row count**, the `.slice(0, 13)`, the role sets and `NAV_LABELS`' shape are genuinely untouched. Flagged as O1 |
| `guide.shifts.3` ✓ | כאן בונים את סידור העבודה לשבוע ומפרסמים אותו לצוות. | third step; role-blind by design, like steps 1–2 |

### 9.2 `RosterPane` — header block

| Key | Hebrew | EN annotation |
|---|---|---|
| `shifts.rosterHeading` ✓ | סידור עבודה | pane `h2` |
| `shifts.rosterDraft` ✓ | טיוטה. הסידור אינו גלוי לצוות ואינו קובע מי במשמרת. | the two things a draft is not, in the order she cares about |
| `shifts.rosterPublished` ✎ | פורסם על ידי \<bdi\>{{name}}\</bdi\> ב־{{date}} בשעה {{time}}. | `<Trans>`. ✎ **twice**: added the `<bdi>` (§9.0(b)), **and moved the name off the end of the sentence**. ⚠ `<bdi>` isolates a name's *interior*; it does **not** move a trailing full stop. The isolate resolves as a neutral, so stop + isolate both take the RTL paragraph level and the stop lays out to the **left** of «Ronit Bar» — reproducing F-22's «על ידי .Ronit Bar» verbatim, on the header line of a legally gated RTL screen. Naming the defect and keeping the shape fixes nothing. With the name in the middle, the terminal stop follows `{{time}}`'s digit run and there is no Latin adjacency to glue it to. `{{date}}` = `jerusalemDate(published_at)`, `{{time}}` = `jerusalemTime(published_at)` — both digits-plus-CS runs, unisolated per §9.0(c) |
| `shifts.rosterEditedSincePublish` ✓ | בוצעו שינויים מאז הפרסום. הם כבר בתוקף בלוח הקומה. | D7 stated to the person who made them: edits land immediately and do **not** move `published_at` |
| `shifts.rosterInProgressWeek` | השבוע הזה כבר בעיצומו. כל שינוי משפיע על לוח הקומה מיד. | offset = −1 (§2.10). Informs, never blocks |
| `shifts.rosterPastWeek` | השבוע הזה כבר הסתיים. | offset ≤ −2 |
| `shifts.publish` ✓ | פרסום הסידור | `Button size="md"` |
| `shifts.republish` ✓ | פרסום מחדש | same button, `published_at !== null` |
| `shifts.publishDone` | הסידור פורסם. | `role="status"` beside the button, the house save-cue shape. One sentence for publish **and** republish — the outcome she wanted is the outcome that holds |
| `shifts.shortageCount` | משמרות שחסר בהן איוש: {{total}} | `role="status"`, standing. Rendered only when some template carries a target (§2.6). §9.0(a) |
| `shifts.shortageNone` | כל יעדי האיוש מולאו. | same slot, when targets exist and none is short |
| `shifts.shortageFilter` | הצגת משמרות שחסר בהן איוש בלבד | P1's `Checkbox` label. The set is captured on tick, and **the control renders only when some template carries a target** (§2.6) |
| `shifts.shortageFilterOn` | מוצגות משמרות שחסר בהן איוש בלבד. | ⚠ **the filter's only voice.** In the count region while P1 is ticked, removed on untick. Ticking P1 does **not** change the shortage number, so a region whose text did not change would never fire and the filter's whole effect would be inaudible (§2.6) |
| `shifts.noSubmissionsWeek` | אף אחת מהצוות לא סימנה זמינות לשבוע הזה. אפשר לשבץ בכל זאת. | E2 — a boutique that never uses F39 is a supported boutique |
| `shifts.managerNoneEligible` ✓ | אף אחת מהצוות אינה מסומנת כמתאימה לניהול משמרת. אפשר לסמן במסך צוות. | **once per pane** (§2.5), never once per shift |
| — | *(week bar, range line, load failure, retry)* | **no new keys**: `shifts.prevWeek`, `shifts.nextWeek`, `shifts.weekLabel`, `shifts.loadFailed`, `shifts.retry` reused verbatim — the last two are feature-wide by F39's §1.2 |

### 9.3 `RosterPane` — the shift block

| Key | Hebrew | EN annotation |
|---|---|---|
| — | *(weekday `h3`)* | **no new key**: `shifts.dayHeading` «{{day}} · {{date}}» reused verbatim, `{{date}}` = `plainDayMonth(addDays(week_start, n))` |
| `shifts.coverage` ✎ | {{role}}: {{assigned}} מתוך {{target}} | ✎ gained `{{role}}` — two bare «1 מתוך 2» lines under one heading name nothing, and two coverage lines is the ordinary case. `{{role}}` = `t(ROLE_LABEL_KEY[role])`. §9.0(a) |
| `shifts.coverageNoTarget` | {{role}}: {{total}} | a role with assignments and **no** target — a plain count, no bar, never «חסר איוש» (D10) |
| `shifts.coverageShort` ✓ | חסר איוש | `Badge variant="warning"`. **The word carries the state** |
| `shifts.emptyShift` ✓ | עדיין לא שובצה אף אחת למשמרת הזו. | a muted line, not an `EmptyState` — twelve `EmptyState`s is a page of centred chrome |
| `shifts.managerLine` | אחראית משמרת: \<bdi\>{{name}}\</bdi\> | `<Trans>`, §9.0(b) |
| `shifts.managerNone` | לא נבחרה אחראית משמרת. | the gap is a sentence, not a blank |
| `shifts.setManager` | סימון כאחראית משמרת | on an eligible assigned row, slot empty |
| `shifts.setManagerAria` | סימון כאחראית משמרת — {{name}} | plain `{{name}}`, §9.0(b) |
| `shifts.clearManager` | ביטול הסימון כאחראית משמרת | on the holder's row |
| `shifts.clearManagerAria` | ביטול הסימון כאחראית משמרת — {{name}} | |
| `shifts.overrideBadge` ✓ | שובצה בחריגה | `Badge variant="warning"`, from `override_of_state !== null` |
| `shifts.unavailableAfterAssign` | \<bdi\>{{name}}\</bdi\> סימנה שאינה זמינה אחרי השיבוץ. | §3.5 — stamp `null`, live state `unavailable`. `<Trans>` |
| `shifts.addToShift` ✓ | הוספה למשמרת | opens `RosterCellDialog` |
| `shifts.addToShiftAria` | הוספה למשמרת {{shift}} | twelve otherwise-identical buttons. `{{shift}}` = «ראשון · משמרת בוקר» |
| `shifts.removeAssignment` | הסרה | `Button variant="danger" size="md"`, **no confirm Modal** (§2.3) |
| `shifts.removeAssignmentAria` | הסרה — {{name}} ממשמרת {{shift}} | ⚠ the shift is **not optional**: the same woman is a remove button on four shifts |

### 9.4 `RosterCellDialog`

| Key | Hebrew | EN annotation |
|---|---|---|
| `shifts.cellDialogTitle` | שיבוץ למשמרת | `Modal`'s `title` — a **string** prop, so the shift identity lives in the body line and not here |
| `shifts.cellAssigned` | שובצה | muted marker on an assigned row; not a Badge (one pill per row) |
| `shifts.cellWeekCount` | שובצה השבוע: {{total}} | §3.3, muted. **A count of shifts, never hours**, and it carries no threshold. §9.0(a) |
| `shifts.cellAdd` | הוספה | one tap on every row except `unavailable` |
| `shifts.cellAddAria` | הוספה — {{name}} | |
| `shifts.cellRemove` | הסרה | the same button, flipped; nothing unmounts (§3.1) |
| `shifts.cellRemoveAria` | הסרה — {{name}} | the dialog already names the shift |
| `shifts.assignAnyway` ✓ | שיבוץ בכל זאת | the second, deliberate tap — the `acknowledge_override: true` write |
| `shifts.overrideWarning` ✎ | \<bdi\>{{name}}\</bdi\> סימנה שאינה זמינה במשמרת הזו. השיבוץ יירשם כחריגה. | inline in the row, `role="status"`. ✎ added the `<bdi>` — §9.0(b) |
| `shifts.cellAllUnavailable` | כל מי שהגישה סימנה שאינה זמינה במשמרת הזו. | above the list, when every unassigned staffer is `unavailable` (§3.4). Does not block |
| `shifts.cellAssignedCue` | \<bdi\>{{name}}\</bdi\> שובצה למשמרת. | the dialog's one `role="status"` region. `<Trans>` |
| `shifts.cellRemovedCue` | \<bdi\>{{name}}\</bdi\> הוסרה מהמשמרת. | same region |
| — | *(her state per shift)* | **no new keys, and one spec key deleted**: `shifts.states.preferred` / `.available` / `.unavailable` and **`shifts.stateUnanswered` «לא נרשם»** reused verbatim. ✎ the spec's «טרם הגישה» on the cell is dropped — that string is `shifts.notSubmitted`, a fact about the *person*, and it is false of a staffer who answered eleven of twelve shifts (§3.2) |

### 9.5 `MyWeekPanel`'s published block

| Key | Hebrew | EN annotation |
|---|---|---|
| `shifts.myRosterHeading` ✓ | המשמרות שלי | `h3` under «הזמינות שלי». The pair is the feature: what she *said she could do* vs what she *was given* |
| `shifts.myRosterUnpublished` ✓ | סידור העבודה לשבוע הזה טרם פורסם. | `roster_published === false` |
| `shifts.myRosterNone` ✓ | לא שובצת למשמרות בשבוע הזה. | published, empty list — a **different fact** (D5), hence a different sentence |

### 9.6 `ShiftTemplatesPane` — coverage targets

| Key | Hebrew | EN annotation |
|---|---|---|
| `shifts.coverageTargets` ✓ | יעדי איוש | the `<legend>` |
| `shifts.coverageTargetsHelp` | שדה ריק — אין יעד. אפס — במפורש אף אחת. | `Input`'s `help` slot, `aria-describedby`-linked, announced at capture. D10's sparse map made honest |
| — | *(per-role labels)* | **no new keys**: `t(ROLE_LABEL_KEY[role])` from `lib/roles.ts` |

### 9.7 `FloorPanel`

| Key | Hebrew | EN annotation |
|---|---|---|
| `floor.onShift` ✓ | במשמרת | first fragment of the card line |
| `floor.offShift` ✓ | לא במשמרת | |
| `floor.onShiftManualToday` ✓ | נקבע ידנית להיום | `ON_SHIFT_SOURCE_KEY.manual_today` |
| `floor.onShiftRoster` ✓ | לפי סידור העבודה | `ON_SHIFT_SOURCE_KEY.roster` |
| `floor.onShiftNoRoster` ✎ | אין סידור עבודה לשבוע הזה. כל מי שלא סומנה ידנית נחשבת כמי שבמשמרת. | ⚠ ✎ **twice over** (§6.2): moved from the card to **one week-level line above the list**, and the second sentence added because a `manual_today` card in an unpublished week makes «כל הצוות» false. ⚠ **«נחשבת», not «מוצגת»** — a `fallback` card renders no on-shift line, so a sentence about what is *displayed* would describe a render §6.2 deletes; the clause states the rule that governs the person. `ON_SHIFT_SOURCE_KEY.fallback` still maps to it — the `Record` stays total and no-fallback — the render site is what moved |
| `floor.onShiftOverrideNote` ✓ | הסימון הידני תקף להיום בלבד ומתאפס בחצות. | **once per board**, iff some card is `manual_today` |
| `floor.markOnShift` ✓ | סימון במשמרת | |
| `floor.markOnShiftAria` | סימון במשמרת — {{name}} | plain `{{name}}` (§9.0(b)) |
| `floor.markOffShift` ✓ | סימון שאינה במשמרת | |
| `floor.markOffShiftAria` | סימון שאינה במשמרת — {{name}} | |
| `floor.clearOnShiftOverride` ✓ | ביטול הסימון הידני | |
| `floor.clearOnShiftOverrideAria` | ביטול הסימון הידני — {{name}} | |
| `floor.markedOnShiftCue` | {{name}} מסומנת כמי שבמשמרת היום. | ⚠ the panel's **existing** `role="status"`, written through the shipped writer exactly as `floor.breakStartedCue` is (`FloorPanel.tsx:589`). Plain `{{name}}` — the writer applies `isolateBidi`, not `<Trans>` |
| `floor.markedOffShiftCue` | {{name}} מסומנת כמי שאינה במשמרת היום. | same region, same writer |
| `floor.onShiftOverrideClearedCue` | הסימון הידני עבור {{name}} בוטל. | same. Without these three, a screen-reader user's press produces **silence** — focus stays put by design and an accessible-name change does not re-announce (§6.3) |
| — | *(override failures)* | **no new keys**: `floor.error.notFound` (404) and `staff.loadFailed` reused verbatim; a 403 is terminal and renders the shipped `floor.accessEnded` (§6.3) |

### 9.8 Error codes → Hebrew (every one added to a pane's `MAPPED_CODES` **by hand**)

| Key | Server code | Hebrew |
|---|---|---|
| `shifts.errors.availabilityConflict` ✎ | `AVAILABILITY_CONFLICT` 409 | \<bdi\>{{name}}\</bdi\> סימנה שאינה זמינה. צריך לאשר את החריגה. |
| `shifts.errors.notEligible` ✓ | `NOT_SHIFT_MANAGER_ELIGIBLE` 400 | אפשר לשבץ כאחראית משמרת רק מי שסומנה כמתאימה לכך. |
| `shifts.errors.managerSlotTaken` ✓ | `SHIFT_MANAGER_SLOT_TAKEN` 409 | כבר שובצה אחראית משמרת למשמרת הזו. |
| `shifts.errors.coverageTargetInvalid` ✎ | `COVERAGE_TARGET_INVALID` 400 | יעד האיוש חייב להיות מספר שלם בין 0 ל־{{max}}. |
| `shifts.errors.rosterNotAuthorized` | `NOT_AUTHORIZED` 403 | אין הרשאה לבנות או לפרסם סידור עבודה כרגע. לבירור אפשר לפנות לבעלת הבוטיק. |
| — | `WEEK_OUT_OF_RANGE` 400 · `NOT_FOUND` 404 | **F39's `shifts.errors.weekOutOfRange` / `shifts.errors.notFound`, reused verbatim** |

✎ `availabilityConflict`: added the `<bdi>` (§9.0(b)) — the name is at the head of the string. ✎ `coverageTargetInvalid`: `20` became `{{max}}`, fed from the `MAX_COVERAGE_TARGET` mirror that `test_frontend_constant_parity.py` pins — a hardcoded bound in a copy string is a second source of truth for a number O3 calls a fat-finger guard rather than a product rule.

⚠ **`shifts.errors.rosterNotAuthorized` is a new key and may not borrow F39's** — `shifts.errors.notAuthorized` is a sentence about the on-behalf *availability* write and would be a wrong claim here. It follows `board.accessEnded` / `floor.accessEnded`'s shape: the owner is named as who to **ask**, never as the gate.

**Client-side validation messages are not in this deck** — `validation.ts` returns hardcoded Hebrew (F51's rule, `validateShiftTemplate`'s precedent). ⚠ **With the bound interpolated, not literal**: `` `יעד האיוש חייב להיות מספר שלם בין 0 ל־${MAX_COVERAGE_TARGET}.` `` — the same one-source-of-truth argument that turned `20` into `{{max}}` two rows above applies to the same rule on the same field, and typing the literal here would leave client and server disagreeing the first time O3's fat-finger guard moves (§5).

---

## 10. Accessibility contract — IS 5568 / WCAG 2.0 AA is a **legal** gate

- **Heading order.** `RosterPane`: shell `h1` (sr-only) → pane `h2` → weekday `h3` → shift `h4`. The `h2` survives the loading and failure renders, so the order is identical in every state (F39 §1.2's rule, fifth pane). `MyWeekPanel`: `h2` → the published block's `h3` → the weekday `h3`s (siblings, nothing skipped). `RosterCellDialog`: `Modal`'s own `h2`, and the body adds **no heading** — the shift identity is a `<p>` wired through `describedById`.
- **Reading order in the header block is `count → publish → filter`** (§2.1, §2.7). The count is a `<p>` and takes no tab stop, so the **tab** order below is the same either way — which is exactly why the DOM order has to be stated: it is the only thing that puts the number in front of the button for a linear reader, and it is the whole of §2.7's substitute for a publish confirmation.
- **Keyboard order, `RosterPane`**: skip link → chrome → nav → `[השבוע הקודם]` → `[השבוע הבא]` → `[פרסום הסידור]` → `[הצגת משמרות שחסר בהן איוש בלבד]` → then, in visual (day, then shift, then row) order: per assignment `[סימון/ביטול הסימון כאחראית משמרת]?` → `[הסרה]`, then `[הוספה למשמרת]`. **Twelve shifts is twelve heading stops**, which is why §2.1 puts the weekday and the shift both in the heading tree — the alternative is tabbing past ~40 controls to reach the eighth shift.
- **Focus management — the default is "do not move", with exactly two named exceptions in this feature.** Publish, the dialog's add/remove flip, the P1 filter, the manager set/clear and the week pager all leave their trigger mounted, so the browser's behaviour is correct and a manual move would be the defect. ⚠ **"Mounted" is not "focused":** §2.0 puts `loading` on every write button, and `Button` is `disabled={disabled || loading}`, so the browser blurs to `<body>` for the duration of the request. The restore is `FloorPanel`'s shipped shape — re-focus **only if** `document.activeElement === document.body`, so a user who tabbed away mid-request is not yanked back (`FloorPanel.tsx:376-378`).

  | Flow | What unmounts | Focus goes to |
  |---|---|---|
  | Remove an assignment from a shift block (§2.3) | the `[הסרה]` button, with its row | that shift's `[הוספה למשמרת]` — the nearest surviving control in the same group. `ShiftTemplatesPane`'s shipped `addButtons.current[day]?.focus()` rescue, keyed by template id |
  | Clear a same-day override on the floor board (§6.3) | `[ביטול הסימון הידני]` | the mark button on the same card |

  `Modal`'s trap / Esc / backdrop / return-to-trigger stays `packages/ui`'s, unmodified — the dialog's trigger («הוספה למשמרת») survives, so the shipped return is right. One guard: if that shift's `<section>` is gone on close (a template soft-deleted under her), fall back to the pane `h2`, `FloorPanel`'s shipped shape.
  ⚠ **P1's held filter set exists partly for this** (§2.6): a live filter would unmount the open dialog's own trigger on the write that closes a shortage.
- **Live regions.** `RosterPane` has **two standing** (`role="status"`, polite, neither on a timer): the week range line — a week change alters the whole pane under a button that never moved — and the shortage slot, which carries the count, `shifts.shortageNone`, and `shifts.shortageFilterOn` while P1 is ticked. ⚠ **The count is not the filter's voice** — ticking P1 does not change the number, and a region whose text does not change never fires; `shortageFilterOn` is the text change, in both directions (§2.6). Publish uses the **house save-cue span** (`role="status"` beside the button, `MyWeekPanel`'s `common.saved` shape), cleared by the next edit. `RosterCellDialog` has **two** — the top cue (assign/remove) and the in-row override warning — which cannot fire together, because arming writes nothing and any write clears the arm (§3.1). **`FloorPanel` gains no NEW region and reuses the one it has**: the three override writes announce through the panel's shipped `role="status"` cue exactly as `toggle` does (§6.3, `FloorPanel.tsx:589`/`:690`). The **poll** still may never write there (spec D12) — the on-shift line changing on a tick is not an outcome of anything the viewer did.
- **Announcements that are the point of a state carry a role.** Every failure is `role="alert"` on first render as on retry; every terminal cue is `role="status"`. **No state on any of these surfaces renders text only a sighted user receives.** The two that this claim previously covered only by assertion: **P1's filter** now has `shortageFilterOn`, and the **three floor override writes** now have their own cues. A write on a shift with **no** coverage target moves no count and is announced by the surface that made it — the dialog's cue for a dialog write; for a remove on the shift block, the focus rescue lands on `[הוספה למשמרת]`, whose accessible name carries the shift (`shifts.addToShiftAria`), so the move itself names where she now is.
- **Targets ≥ 44px.** Every `Button` is `size="md"` (`min-h-11`); `Checkbox`'s label row is `min-h-11` by construction; the coverage-target `Input`s take `className="min-h-11"`. **No `size="sm"` anywhere in this feature** (F-W1). ⚠ LOOP-STATE's 0032-era finding: `Modal`'s 0.97→1 open animation makes a compliant 44px control measure **42.68px mid-transition** — the e2e must `settleAnimations(page)` before measuring `RosterCellDialog`, and must never lower the floor to make a measurement pass.
- **Nothing is signalled by colour alone.** Shortage is «חסר איוש», an override is «שובצה בחריגה», the manager is a named line, on-shift is «במשמרת» / «לא במשמרת», the rule is a named phrase. **An off-shift card is not dimmed** (§6.1) — that would make on-shift-ness a colour and filtering-by-opacity at the same time.
- **Contrast, from `tokens.md`**: `warning` Badge = `--color-warning-text` 5.20 on paper; muted lines = `--color-ink-muted` 5.61 on paper; `danger` Button = white on `#A03232` ≈ 7.0:1. `--color-gold-strong` appears nowhere carrying text.
- **Bidi**: every `HH:MM–HH:MM` in `<bdi dir="ltr">` (§9.0(c)); every display name in a **bare** `<bdi>` with `break-words` and **no truncation, ever**; bare integers unisolated, following `shifts.answered`'s shipped shape. Logical properties only (`ms-*`, `text-start`, `border-t`) — the qa-greps physical-direction ban applies.
- **Reduced motion**: this feature adds no motion of its own. `Modal`'s panel/backdrop animation already respects `prefers-reduced-motion`.
- ⚠ **jsdom has no `<dialog>`** — `setup.ts` stubs `showModal()`, so a focus assertion that pre-places focus on its own target is vacuous. Unit tests assert the dialog's **content** (the sort order, the override copy and payload, the eligible-only manager list, the all-unavailable line); real focus behaviour belongs to the e2e leg, which is where F39's own locked-banner focus bug was finally caught.
- **axe zero violations** on: the draft pane, the published pane, the pane with P1's filter on, **the pane's E6 filtered-empty render and its E7 no-targets render** (no count line, no checkbox), **the pane's loading render and its load-failure render**, `RosterCellDialog` open (default and mid-override-confirm, with the warning in the row), `MyWeekPanel`'s three published-block states, and the floor board **with each of the three rule labels** plus all three override controls rendered on one card — RTL, at 375.

---

## 11. ⚠ FINDINGS — things the spec leaves open that the build cannot

- **F-1 — the two override routes must return the patched `StaffCard`.** §6.3. The spec gives `POST/DELETE /manage/floor/staff/{id}/on-shift` a body but no response shape. `FloorPanel`'s shipped discipline is *"NOT optimistic — the card is patched from the SERVER's card, so the panel cannot disagree with itself"*, and the client **cannot** compute `on_shift_source` (that is the whole of D8). A `204` forces a refetch or a guess, and a guess here prints the wrong Hebrew rule label on a live floor screen.
- **F-2 — `POST /manage/shifts/roster/assignments` must be an UPSERT on the live `(roster, template, staffer)` triple.** §2.5. `is_shift_manager` is a column on an assignment row and no route can move it on an existing row; without the upsert, "make Dana the manager" is `DELETE` + `POST` — two audit rows, the silent loss of her `override_of_state` stamp, and a window in which she is not on the shift at all. The upsert also makes `409 SHIFT_MANAGER_SLOT_TAKEN` unreachable through the UI and returns the partial unique index to being the concurrency guard D12 designed it as.
- **F-3 — there is no grid, and the shell is why.** §1. `max-w-[720px]` at every viewport gives 69px per staff column at 1440 and 24px at 375. Any build that starts from the word "grid" ends in an `overflow-x` container inside an RTL page that §7 forbids and axe cannot rescue.
- **F-4 — rule 3 must not render on eight cards.** §6.2. Eight copies of «אין סידור עבודה לשבוע הזה» is permanent noise in a boutique that never publishes — which C1 promises *"sees no change at all"*. The line moves above the list, renders once, and gains a clause so it stays true when one card carries a manual override.
- **F-5 — `override_of_state` is stamped and never updated, so a staffer can go unavailable *after* she was rostered.** §3.5. Both facts are already on the wire; a build reading only the stamp renders that shift as perfectly healthy, and the boutique discovers it on Thursday evening.
- **F-6 — the shipped `— {{name}}` disambiguator is not enough on this pane.** §2.3. This is the first console screen on which the same person is a control on twelve different rows; the remove button's accessible name needs the shift too.
- **F-7 — the 403 may not borrow F39's `shifts.errors.notAuthorized`.** §9.8. That string is a sentence about the on-behalf availability write. Unkeyed or mis-keyed, F38's build note applies verbatim: the server's English renders right-aligned in a Hebrew console on a green build.
- **F-8 — "removable chips" are icon-only controls.** §2.3. DL20 and `ConsoleShell.tsx:53-68` forbid them, and an `×` sized for a chip is nowhere near 44px. Rows, with a worded `[הסרה]`.
- **F-9 — a live shortage filter unmounts the shift the owner is working inside.** §2.6. Assigning the last missing woman would remove the `<section>` containing her open dialog's trigger. The filtered set is captured on tick.
- **F-10 — the shift heading must be `h4` under a weekday `h3`, not `h3` alone.** §2.1. `label` is free operator text with no uniqueness rule (F39's shipped F-19); six headings reading «משמרת בוקר · 09:00–14:00» with nothing naming the day is a roster built against the wrong Thursday.
- **F-11 — `Modal.title` is a `string`.** §3. The shift's time range cannot be bidi-isolated in it, so the shift identity is the body's first line, wired through `describedById` so the dialog still announces which shift on open.
- **F-12 — `isMaterialEdit` must NOT gain `coverage_targets`.** §5. "Add the new field to the material set" is the reflex, and doing it soft-deletes every future submission on a template the first time somebody changes a target from 2 to 3.
- **F-13 — empty and `0` are different values in a number field and nothing says so.** §5. D10's sparse map is invisible in the control that writes it without the `help` line.
- **F-14 — `RosterPane` belongs in `ShiftsSection`'s `!firstRun` branch.** §2. Placed beside `ShiftTemplatesPane` it becomes the fourth stacked empty on a first-run boutique that the shipped `if` exists to remove.
- **F-15 — the per-shift «טרם הגישה» is the wrong string.** §3.2. It is `shifts.notSubmitted`, a fact about the person, and it is false of a staffer who answered eleven of twelve shifts. `shifts.stateUnanswered` «לא נרשם» is F39's per-shift absence and already mounts twice.
- **F-16 — `shifts.coverage` is unreadable without the role word.** §2.4 / §9.3. Two coverage lines per shift is the ordinary case.
- **F-17 — a publish repaints eight floor cards at once, from a poll.** §6.5. ~176px of vertical shift under a travelling finger; the existing `holdRef` pointer-hold is the mitigation and no new code is needed — stated so nobody adds a second one, and so nobody is surprised by the movement in QA.
- **F-18 — `MyWeekPanel`'s default week is next week, so her *published* week is one pager tap away.** §4. An accepted cost of D17's one-pane decision, recorded rather than silently absorbed.
- **F-19 — a 403 on the override kills the whole floor panel, and that is correct.** §6.3. `mutate`'s P-6 {401,403} rule makes it terminal; the control never renders for a role that would be refused, so the only path to it is a role change mid-session. Stated because it reads exactly like a bug.
- **F-20 — three new `aria-*` keys on the floor board.** §6.3 / §9.7. Eight cards × «סימון שאינה במשמרת» is the dead end `floor.breakStartAria` exists to close, and the spec's deck carries only the visible labels.
- **F-21 — `Button`'s `variant` defaults to `primary`, and `primary` is `bg-gold text-ink`.** §2.0. A control this design leaves unnamed **ships gold**: twelve gold add buttons, a gold button per dialog row, a gold override confirm, three gold buttons per floor card. Every control in the feature now carries a stated variant and each surface has exactly one `primary`.
- **F-22 — every write button takes `loading`.** §2.0. §0.1's owner taps «הוספה» dozens of times a session under time pressure; unguarded, a double-tap or a tap on the next row mid-request sends a second write — a `409` from the partial unique index, or a `DELETE` against a row already gone, both reaching her as an unexplained alert for what felt like one action. `Button` already ships the spinner, the width lock, `aria-busy` and `disabled`.
- **F-23 — P1's checkbox must be gated on the same condition as the count line.** §2.6 / §2.8-E7. `coverage_targets` is `NOT NULL DEFAULT '{}'`, so on a boutique that has set no target the "is short" predicate is structurally false forever: ticking the box empties the pane with the count line already suppressed, and nothing distinguishes that from a load bug or from success.
- **F-24 — the shortage count is not P1's voice.** §2.6 / §10. Filtering changes which shifts render, not how many are short; a region whose text does not change never fires. `shifts.shortageFilterOn` is the text change, in both directions.
- **F-25 — the header block's DOM order is `count → publish → filter`, and it is load-bearing.** §2.1 / §2.7. §2.7's placement argument **is** the publish confirmation. Publish drawn above the count ships the feature with neither.
- **F-26 — the mark/clear gate is `ELEVATED.has(role)`, NOT `mayToggle`.** §6.3. `FloorPanel.tsx:867` computes `mayToggle = isSelf || ELEVATED.has(role)` — reusing it renders «סימון שאינה במשמרת» on a seamstress's own card, whose press is a 403, which `mutate`'s P-6 rule makes terminal for the whole panel. She loses the board by pressing a button D13 says should never exist.
- **F-27 — `controlRefs` is keyed by `card.id` with one writer, and three buttons per card break it.** §6.3. Keyed `` `${card.id}:${control}` `` instead; otherwise the ref cleanup on «ביטול הסימון הידני» nulls Dana's slot and the shipped break-toggle focus restore regresses along with the new controls.
- **F-28 — the three override writes must announce in the panel's existing cue.** §6.3 / §9.7. `toggle` writes `floor.breakStartedCue`; three writes modelled on it that announce nothing leave a screen-reader user in silence, 2px from a button that speaks.
- **F-29 — the dialog's override warning lives IN THE ROW, and the dialog therefore has two `role="status"` nodes.** §3.1 / §3.4. Painted at the top of the modal it is above her scroll position while the button under her finger changes label for no visible reason — she taps again, and the second tap is the write. The two regions cannot fire together.
- **F-30 — the coverage-target help line is a per-`Input` `help` prop, not one `<p>` under the `<legend>`.** §5. `Input` builds `helpId` from its own `useId()`; a fieldset-level paragraph is `aria-describedby`-linked to nothing, and the empty-vs-`0` rule is then never spoken to the person who most needs it.
- **F-31 — `<bdi>` does not move a trailing full stop.** §9.2. The isolate resolves as a neutral and takes the RTL paragraph level along with the stop, so `«… על ידי <bdi>{{name}}</bdi>.»` renders F-22's «.Ronit Bar» exactly as the unisolated string does. The name moves out of final position; the isolate alone is not a fix.
- **F-32 — renaming `nav.shifts` is six edits, two of them the ordering assertions.** §9.1. `i18n/he.ts:2671`, `i18n/ar.ts:1013`, `i18n.test.ts:1880`, `Nav.test.tsx:127`, `:214`, `:235`. This is the one copy row flagged for user approval, so the gate must be quoted the real cost.
- **F-33 — the client-side bound is interpolated from `MAX_COVERAGE_TARGET`, not typed into the Hebrew.** §5 / §9.8. The design parameterised the *server* error string on exactly this reasoning; a literal on the client is the same second source of truth, and O3 says the constant will move.

---

## 12. PROPOSED (user confirms at the gate)

- **P1 — «הצגת משמרות שחסר בהן איוש בלבד»** (§2.6). The single control that makes a 4,000px page workable, with its set captured on tick rather than live. The one control the spec does not name.
- **P2 — weekday `h3` → shift `h4`**, rather than the spec's shift-`h3` (§2.1 / F-10).
- **P3 — assignments are rows with a worded `[הסרה]`, not removable chips** (§2.3 / F-8), and removal opens **no confirm** — it destroys nothing of anyone's.
- **P4 — the dialog's button flips «הוספה» ⇄ «הסרה» in place**, making it the shift's editor rather than an add-picker, and removing what would otherwise be the most-repeated focus exception in the feature (§3.1).
- **P5 — the override acknowledgement is inline in the row, never a nested `Modal`** (§3.4).
- **P6 — rule 3 renders nothing on the card and one line above the list** (§6.2 / F-4), with `floor.onShiftNoRoster` redrafted to stay true beside a manual override.
- **P7 — `floor.onShiftOverrideNote` and `shifts.managerNoneEligible` render once per screen**, not once per card / once per shift (§6.4, §2.5).
- **P8 — a missing shift manager is not counted in the shortage line** (§2.6); it is a per-shift sentence instead, because on a fresh boutique nobody is eligible and a permanent counter would be a permanent accusation.
- **P9 — the manager slot is clear-then-set, two deliberate acts**, rather than one control issuing two writes (§2.5).
- **P10 — coverage targets are one `Input` per `ROLE_OPTIONS` member**, driven off `lib/roles.ts` rather than a curated subset (§5).
- **P11 — ten copy rows redrafted** (marked ✎ in §9): four for `<bdi>` isolation, **one of which (`rosterPublished`) is redrafted a second time to move the name off the sentence end — see P18**; three on factual grounds (`coverage`'s role word, `onShiftNoRoster`'s render site and its «נחשבת» clause, `coverageTargetInvalid`'s `{{max}}`), and one spec key **deleted** («טרם הגישה» on the cell → `shifts.stateUnanswered`). Meaning is unchanged on every one.
- **P12 — two new keys the spec's deck lacks**: `shifts.errors.rosterNotAuthorized` (F-7) and the three floor `aria-*` rows (F-20), plus the state/edge rows §2.8 and §3.4 require.
- **P13 — every button's variant is stated and each surface carries exactly one `primary`** (§2.0 / F-21), because the component default is gold and silence therefore ships a wall of CTAs against the gold law.
- **P14 — every write button takes `loading`** (§2.0 / F-22), per-control rather than per-dialog, re-armed in `.finally()`.
- **P15 — P1's checkbox is gated on a target existing somewhere in the week**, and §2.8 gains states **E6** (filter on, nothing short) and **E7** (no target anywhere) (§2.6 / F-23).
- **P16 — one new key, `shifts.shortageFilterOn`**, so the filter has a voice the count cannot give it (§2.6 / F-24).
- **P17 — three new cue keys on the floor board**, written to the panel's existing `role="status"` (§9.7 / F-28).
- **P18 — `shifts.rosterPublished` is redrafted a second time**, moving the name out of sentence-final position (§9.2 / F-31). This makes **ten** ✎ rows, not nine.

---

## 13. What this surface deliberately does not have

**No hour totals, no weekly sum, no duration column, no attendance reading and no pay** (§0.3) · **no double-booking flag, no long-day warning and no rest-period check** — the platform shows the load and does not judge it · no auto-generated or optimised roster · no multi-week publish and no copy-last-week (O4) · no staff-initiated swap, decline or acknowledgement · no self-service on-shift marking, anywhere, for anyone (D13) · **no unpublish and no edit lock** (C5/D7) · **no confirm dialog on publish** (§2.7) and none on removing an assignment (§2.3) · no publish block on a shortage or a missing manager (pre-decided #40) · no filtering, dimming, reordering or hiding of any card on the floor board (D1) · no second "who is on shift" screen · no per-week coverage target (targets are per template, D10) · no notification, SMS or bell when a roster publishes (O5) · **no polling on any surface this feature adds** · no timer, no countdown, no live clock and therefore nothing that brings SC 2.2.2 into scope · no historical roster analytics · no new nav row and no eighteenth `SectionKey` (D17) · no rewiring of F37's SOS (C2/D15) or F42's `assignable` (C3/D15) · no new `@boutique/ui` export and nothing promoted · no icon-only control (DL20) · no per-state colour semantics anywhere.

---

Design Gate: OPEN
