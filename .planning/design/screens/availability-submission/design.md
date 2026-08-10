# Screen design — F39 staff availability submission (`apps/manage`, new section «זמינות למשמרות», Epic E8)

**Date**: 2026-08-10 · **Status**: DESIGN GATE OPEN — **rev 2**, two critic passes folded in (F-14…F-23, P9…P11); awaiting copy approval · **Designer**: Claude (design subagent)
**Consumes**: `.planning/specs/availability-submission.md` (Gate 1 self-approved under Q1) · tokens rev 1 · `packages/ui` as shipped
**Precedents read before drawing**: `.planning/design/screens/hr-directory/` (F38) · `.planning/design/screens/staff-notification-bell/` (F35)
**Copy**: every Hebrew row in §9 needs APPROVAL. Register: calm, feminine address, **no exclamation marks** (pre-decided #5, asserted by `__tests__/i18n.test.ts`).

---

## 0. Scope, and the two audiences that are not the same screen

One new console section, the **seventeenth**, reachable by all five staff roles (D12). Behind that one nav row live **four panes**, and the role split is not cosmetic — it is two different jobs:

| Audience | Pane(s) | Frequency | Device |
|---|---|---|---|
| **Every staffer** (all five roles, including the owner) | `MyWeekPanel` | weekly, once | **a phone, standing in a boutique** |
| **Elevated only** (`owner`, `shift_manager`) | `WeekSubmissionsPane`, the deadline Card, `ShiftTemplatesPane` | weekly read; config once ever | desk or phone |

The staffer is the highest-volume user of this feature by an order of magnitude — eight staffers × 52 weeks against one owner configuring templates once — so §2 optimises her path in taps and everything else is arranged around it.

**Binding inheritances, obeyed and not restated.** F-W1 (`Button size="sm"` = `min-h-9` = 36px, **fails** the 44px floor — `md` only, everywhere in this feature; D13 already says so). DL20 / `ConsoleShell.tsx:53-68` (**the console ships no icon-only control; the visible Hebrew word IS the name**). R19 bidi isolation (`<bdi dir="ltr">` around every numeral run; **bare** `<bdi>` around a human name — `dir="ltr"` on a Hebrew name is itself a defect). The house failure vocabulary `{ns}.loadFailed` + `{ns}.retry` («ניסיון נוסף», verbatim across the console). Jerusalem reads only through `lib/jerusalem.ts` and `@boutique/ui`'s `formatDateRange` — **no new date arithmetic in a component**. `ConsoleShell` caps `#console-main` at `max-w-[720px]`.

**Out of this surface, by spec**: any roster, assignment, coverage target or publish (F40) · standing availability · time-off requests · partial-shift availability · swaps · deadline nudges · overnight shifts · polling · a `@boutique/ui` export for the three-state control (D13).

**And one thing out by epic risk, which is a design constraint and not a feature list.** This is not an hours-worked record and must never read as one. Concretely: **no hour totals anywhere on any of the four panes** — no «סה"כ שעות», no weekly sum beside a name, no duration column on a template row. A shift shows `HH:MM–HH:MM` because that is how a staffer recognises which shift she is answering; the moment a screen adds them up it is an attendance sheet, and the epic's labour-law row says that drift is review-blocking.

---

## 1. Container — `ShiftsSection.tsx`, and the pane order

```
elevated (owner / shift_manager)          non-elevated (reception / sales / seamstress)
┌──────────────────────────────┐          ┌──────────────────────────────┐
│ Card  h2 הזמינות שלי          │          │ Card  h2 הזמינות שלי          │
│ Card  h2 מי הגישה             │          └──────────────────────────────┘
│ Card  h2 מועד ההגשה           │
│ Card  h2 משמרות הבוטיק        │
└──────────────────────────────┘
```

`ELEVATED = new Set(["owner", "shift_manager"])`, spelled locally — `FloorPanel.tsx:41`, `SeamstressPanel.tsx:35` and `AtelierSection.tsx:67` each spell their own for the same reason, and D7 spells the backend twin locally too. `role` and `selfId` arrive as props from `App.tsx`, `AtelierSection`'s shipped signature.

**Order rationale, and the alternative rejected.** Configuration last. Her own week first — for every role, so there is one mental model and one e2e path, and because an owner who has to scroll past a list she reads first is an owner who stops answering her own week. The readiness read is second because it is the recurring elevated act; the deadline and the templates are the once-ever block, which is `HoursSection`'s shape (the recurring thing on top, the configuration under it). **Rejected**: templates first "because they must exist before anything else works" — true exactly once, and §1.1 handles that case properly instead of taxing every subsequent visit.

### 1.1 First run — the one case where the order inverts

When **no live template exists at all**, an elevated actor sees **only the templates Card**. The other three panes have nothing to say (an empty week, an empty readiness list, a deadline governing nothing), and three stacked empties above the one button that fixes them is a first-run screen that hides its own next step. One `if` in the container, no new state.

A non-elevated staffer in the same situation sees §2.5's single `EmptyState` — she cannot fix it, and offering her the seed control would be a door that 403s.

### 1.2 The read contract every pane obeys — loading and load failure, all four

⚠ **§2.5 draws a full state matrix for `MyWeekPanel` and the three elevated panes have none.** Each has its own fetch (`GET /manage/shifts/week/submissions`, the `Settings` read, `GET /manage/shifts/templates`) and each therefore has a first paint before any response and a paint after a failed one. Left unstated, two people building the three panes in parallel diverge — one ships a skeleton, one ships a blank `Card` until data arrives, one ships neither an alert nor a retry on a 500 — which is exactly the per-screen inconsistency the states-matrix convention exists to prevent. **Concretely**: `GET …/week/submissions` 500s on a Sunday morning and the owner sees an empty «מי הגישה» Card with no skeleton, no `role="alert"`, no retry and nothing announced — **indistinguishable from a boutique where nobody has submitted**, which §3 says is the correct and informative render.

**One contract, all four panes**, and it is `MyWeekPanel`'s (§2.5-L / §2.5-F1) applied without variation:

| Pane | Its read | Loading | Load failure |
|---|---|---|---|
| `MyWeekPanel` | `GET /manage/shifts/week` | `Skeleton variant="text" lines={4}` in the Card | `role="alert"` `shifts.loadFailed` + `Button secondary md` `shifts.retry` |
| `WeekSubmissionsPane` | `GET /manage/shifts/week/submissions` | `Skeleton variant="text" lines={4}` | same pair |
| deadline Card | `api.getSettings()` — **its own**, not a prop from `App.tsx`, which holds no settings state; `ProfileSection.tsx:47` and `GatewaySection.tsx:49` each own theirs the same way | `Skeleton variant="text" lines={2}` (two fields) | same pair |
| `ShiftTemplatesPane` | `GET /manage/shifts/templates` | `Skeleton variant="text" lines={6}` (seven weekday groups) | same pair |

- **`shifts.loadFailed` / `shifts.retry` are feature-wide, not `MyWeekPanel`'s.** One `{ns}` pair per section is the house shape — the eleven shipped `{ns}.loadFailed` sites are one per *namespace*, not one per component — and their §9.2 rows are annotated accordingly. Retry re-issues that pane's own read and nothing else's.
- **Each pane loads and fails independently.** They are four fetches, and one 500 on the templates read must not blank a submissions list that arrived fine. No shared "the section failed" state exists.
- **Only the failed pane's Card renders the alert**; its `h2` stays, so the heading order in §10 is unchanged in every state.
- **Save-failure surfaces** are per-pane and already drawn: `MyWeekPanel` §2.7, the on-behalf save §3.1, seed §5.2, template write §5.1, deadline save §4. Every one is a `role="alert"` line inside its own Card carrying a `MAPPED_CODES` lookup (§9.6), never the server's English.
- **First-run interacts with this and does not break it**: §1.1's `if` keys on the *resolved* templates read, so while that read is in flight an elevated actor sees the four Cards' skeletons and the collapse to one Card happens on the response — not a flash of four empties, because none of them has rendered content yet.

---

## 2. `MyWeekPanel` — the staffer's screen

### 2.1 The tap budget, which is the whole design

A typical pilot boutique: six open days (D3 — Saturday has no `availability_rules`, so it has no templates, emergently and never as a hardcoded Shabbat rule), roughly two shifts a day ⇒ **~12 shifts**.

| Path | Taps |
|---|---|
| Open the section | 1 (nav row) |
| Choose a week | **0** — `GET /manage/shifts/week` with no parameter defaults to next week (D1/§API), which is the week she is here to answer |
| Answer 12 shifts one by one | 12 |
| Save | 1 |
| **Total, naïve** | **14** |
| **Total, with P1's bulk fill** | **1 + 1 + k + 1 ≈ 4** for the usual k = 1–2 exceptions |

**P1 — «סימון כל השאר כזמינה»** (`Button variant="secondary" size="md"`, above the shift list): fills **only the shifts she has not yet answered**. It never overwrites an answer she already gave, which is what makes it non-destructive by construction and removes any need for an undo. It writes nothing — it fills the rendered radios and she still taps «שמירת זמינות». This is **not** the copy-forward that O4 defers: it reads no previous week, stores nothing extra, and produces exactly the `PUT` D11 already specifies. Recorded as PROPOSED (§10) because it is the one control the spec does not name.

### 2.2 "Not answered" is a real state, and it is the **fourth radio**

D8 makes the absence of a row the state, and D8/D11 make that state **reachable in both directions**: entries not present in the `PUT` are soft-deleted, which is D8's stated clear path. ⚠ **A native radio cannot be un-checked.** A three-option group is therefore a one-way state machine — «לא נרשם» → one of three, never back — and D8's clear path and D11's soft-delete-on-absence would be unreachable from every surface in this feature.

**Concretely**: a staffer thumbs «מעדיפה» on the wrong row on a phone. With three options she can overwrite it with «זמינה» or «לא זמינה» but cannot withdraw it, so an answer she never meant to give ships to F40 as advisory input, «נענו» only ever climbs, and a shift manager who records against the wrong staffer's shift leaves a `recorded_by`-stamped row nobody can clear.

**Resolution — a fourth option, `shifts.stateUnanswered` «לא נרשם», checked by default.** It is not a stored fourth state: it is the *rendered* name of "no entry", and selecting it means the shift is omitted from the `PUT`, which is exactly D8's soft delete. No `pending` member enters `AvailabilityState`, no column changes, no route changes — the state machine on the wire is unchanged and only the control becomes reversible. Recorded as a departure (§12 P9).

**And it is not the pre-checked default this section still refuses.** Pre-checking «זמינה» would let a save assert something she never said, which is the dishonesty `recorded_by` exists to prevent one decision earlier (D5). Pre-checking «לא נרשם» asserts precisely the truth. It also fixes a second thing for free: an all-unchecked native radio group has no home for the initial arrow key, so the first arrow press in an empty group selects the first option — with a default-checked option, arrow keys move from a known position.

A progress line under the list — `shifts.answered` «נענו: 9 מתוך 12» — tells her what she left blank. It is derived (entries whose state is not «לא נרשם» vs `templates.length`), never fetched, and it carries `role="status"` (§2.9).

### 2.3 Structure, 375px, one column

```
Card
  h2  הזמינות שלי
  ┌ week bar ─────────────────────────────────────────────────┐
  │ [ השבוע הקודם ]  <p role="status"> שבוע 8–14 בנובמבר       │   ← role="status": a week
  │                  [ השבוע הבא ]                              │      change has no other voice
  ├───────────────────────────────────────────────────────────┤
  │ <p> מועד ההגשה: יום רביעי, 4.11, 18:00                     │   ← from deadline_at, §2.6
  │ [ סימון כל השאר כזמינה ]                          (P1)      │
  └───────────────────────────────────────────────────────────┘

  <section>  h3  ראשון · 8.11                    ← shifts.dayHeading, §2.10
    <fieldset>                                   ← ONE tab stop
      <legend> משמרת בוקר · 09:00–14:00
      [ זמינה ] [ לא זמינה ]                     ← grid-cols-2 sm:grid-cols-4,
      [ מעדיפה ] [ לא נרשם ]                        each label min-h-11; §2.2
      <p> נרשם על ידי <bdi>דנה כהן</bdi>.         ← only when recorded_by_name !== null
    </fieldset>
    <fieldset> … second shift on the same weekday …
  <section>  h3  שני · 9.11
    …

  <p role="status"> נענו: 9 מתוך 12              ← §2.9
  [ שמירת זמינות ]   <span role="status"> נשמר לפני רגע
  <p role="alert">   ← mapped error, §2.7
```

Weekday `<section>`s render **only for weekdays that have templates** — a Saturday heading over nothing is chrome that says "you are missing something".

**Measured at 375px**: page `px-4` (32) + `Card p-6` (48) ⇒ 295px of content. `grid-cols-2 gap-2` ⇒ (295 − 8) / 2 = **143px per option**, two rows of two. The longest label «לא זמינה» is ≈62px at `text-base` Assistant plus `px-2` ⇒ 78px — enormous headroom, and the four-up row at `sm` (640) is (720 − 48 − 24) / 4 = **162px** each. Neither breakpoint stacks a label or scrolls a row sideways.

⚠ **Not `grid-cols-4` at 375.** (295 − 24) / 4 = 68px, and «לא זמינה» needs 78px — the fourth option is exactly what makes the single row impossible on a phone, which is why the 2×2 is the mobile shape rather than a preference. Two rows of 44px per shift × 12 shifts is 1056px of list, which scrolls; the alternative is a label that truncates, and a truncated state word on the control that carries the meaning (§2.4) is not a trade this surface can make.

**Week navigation is words, not chevrons.** The spec's §Component behaviour says "two `Button size="md"` chevrons"; DL20 and `NotificationBell` §1 both rule that this console ships no icon-only control, and an `aria-label` on a glyph is a name no sighted user can verify. «השבוע הקודם» / «השבוע הבא» at `md` measure ~122px each — 252px of the 295 available, on one row. A second benefit falls out for free: **there is no directional glyph to get backwards in RTL.** Both buttons `disabled` at D1's ±4 edges.

### 2.4 The control — D13's native radios, three states plus «לא נרשם»

`<fieldset className="border-0 p-0">` + `<legend>` + **four** `<label>`s each wrapping a `sr-only` `<input type="radio">`. **This is `SlotPicker.tsx`'s shipped contract, reduced to four options** — the same `sr-only` input, the same chip label, the same `focus-within:outline-2 outline-offset-2 outline-focus` so the ring is visible on the label the eye can see. Nothing is promoted to `packages/ui` (D13); the day a second surface needs it, `SlotPicker` is already the extraction template.

- **The fourth option is «לא נרשם», default-checked, and it is not a stored state** (§2.2). It maps to *omit this template from the `PUT`*, which is D8's clear path and D11's soft-delete-on-absence. `AvailabilityState` keeps its three members; the client's local model is `AvailabilityState | null` and `null` is the fourth radio's value.

- **`name` is per template**, `${useId()}-${template.id}`. ⚠ Two shifts on the same weekday are legal and expected (D2 — a morning and an afternoon sharing the changeover hour is an ordinary split shift). A `name` keyed on the weekday would fuse them into one group and answering the afternoon would silently clear the morning. This is the cheapest bug in the feature and the only thing preventing it is the key choice.
- **Selection is signalled on three channels**, `SlotPicker`'s rule: `border-gold-strong` + `bg-gold` + `font-semibold`. Ink on gold is 6.41:1. «לא נרשם» selected takes the same treatment as the other three — it is a real answer to "which did you pick", and giving the default a weaker fill would make "unanswered" look like "nothing is selected", which is the ambiguity the fourth option exists to remove.
- **No per-state colour, and this is a deliberate kill.** The obvious design colours «זמינה» green, «לא זמינה» red, «מעדיפה» gold. Rejected twice over: `--color-danger` is reserved for something the owner must fix and «לא זמינה» is a settled fact, not a fault (`lib/booking.tsx:12-14` is the shipped statement of that rule); and four hues would make hue the carrier of meaning inside a group whose options are already four words. **All four options share one selected treatment.** The word is the meaning; the fill only says *which one she picked*.
- **One tab stop per shift.** Twelve shifts are twelve Tab presses, not forty-eight — the whole reason D13 refused a `div` grid with `role="radiogroup"`. Arrow keys move *and* select within a group, which is the native radio contract and is correct here: traversal is Tab, answering is arrow or click.
- **`recorded_by_name` wiring**: the «נרשם על ידי <bdi>{{name}}</bdi>.» line's `useId` goes on the **`<fieldset>`'s `aria-describedby`**, so it is announced once when she enters the group rather than repeated on each of the four radios — and never dropped, which a plain `<p>` after the radios would be for anyone arrowing through. ⚠ The `<bdi>` is **inside the copy value** and the line renders through `<Trans components={{ bdi: <bdi /> }}>` — see §9.0.

### 2.5 States — every one of them

| # | State | What she sees |
|---|---|---|
| **L** | loading | `Skeleton variant="text" lines={4}` inside the Card (`HoursSection.tsx:67`'s shipped shape). No announcement — the section heading already named the screen |
| **D** | default, week open | §2.3 |
| **E1** | **no templates anywhere** | `EmptyState` — title `shifts.noTemplates`, body `shifts.noTemplatesStaffBody`. **No action**: the seed lives in `ShiftTemplatesPane` and has exactly one owner. An `EmptyState` is right *here* (unlike `bell.empty`'s ruling) because for a non-elevated staffer this absence **is** the whole screen, not a corner of one |
| **E2** | templates exist, week untouched | ordinary default — twelve groups sitting on «לא נרשם» is the correct Monday render, not an empty state |
| **K** | **locked** (deadline passed, non-elevated) | `role="status"` banner `shifts.locked`; the shift list re-renders as a **`<dl>` of her answers**, not disabled radios (§2.8); the save button is **removed**, not disabled — a disabled save on a locked form promises an act it cannot perform. Beside the banner, `[ מעבר לשבוע פתוח ]` when a writable week exists inside the ±4 window (it always does unless she is at the +4 edge) |
| **K-e** | deadline passed, **elevated** | no lock (D5). A muted `shifts.lockedElevated` line instead — «מועד ההגשה עבר. הרישום שלך עדיין אפשרי.» She must know she is acting past it; `after_deadline: true` is going into her audit row either way |
| **S** | saved | `role="status"` `common.saved` («נשמר לפני רגע») beside the button. **Reused, not minted** |
| **F1** | load failure | `role="alert"` `shifts.loadFailed` + `Button secondary md` `shifts.retry`. Immediate and unconditional, first render as on every retry — the house shape, and not one of the eleven shipped `{ns}.loadFailed` sites distinguishes the two |
| **F2** | save rejected | §2.7 |
| **X** | offboarded mid-session | her session dies at `resolve_session` (`by_id` filters `deleted_at IS NULL`), which is the console's existing 401 path. Nothing F39-specific to word |

### 2.6 The deadline line, and why it never reads `Settings`

⚠ **`GET /manage/settings` is gated `OWNER, SHIFT_MANAGER` on the boutique router.** A seamstress cannot read `tenants.settings`, so her deadline line cannot come from the setting — which is precisely why D1/§API put `deadline_at` on the week payload as a resolved ISO-8601 UTC instant. **`deadline_at` is the only source, for every role.**

Rendered through the **three** shipped `lib/jerusalem.ts` helpers plus one new sibling:

```
shifts.deadline  «מועד ההגשה: {{day}}, {{time}}»
  {{day}}  = jerusalemWeekday(deadline_at)
             + ", "
             + plainDayMonth(jerusalemIsoDate(deadline_at))   → «יום רביעי, 4.11»
  {{time}} = jerusalemTime(deadline_at)                       → «18:00»
```

⚠ **`jerusalemIsoDate` is the load-bearing step and it is not optional.** `deadline_at` is an ISO-8601 UTC **instant** (`2026-11-04T16:00:00Z`), and `plainDayMonth` takes a **plain `YYYY-MM-DD`** and splits it on `-`; its own header states the rule it exists to enforce — *"a wire date is a plain calendar date and must never meet a `Date`."* Calling it on the instant is that rule run backwards, and it fails twice over:

1. **It renders `NaN`.** `"2026-11-04T16:00:00Z".split("-")` is `["2026", "11", "04T16:00:00Z"]`, so `Number(day)` is `NaN` and the line reads «מועד ההגשה: יום רביעי, NaN.11, 18:00» — on the single most-viewed line in the feature, at the top of `MyWeekPanel` for every staffer on every load.
2. **String-slicing the instant instead is the DST bug D1/D6 exist to prevent.** Reading `2026-11-04` off the UTC instant reads a UTC calendar day as if it were already Jerusalem's. A tenant whose `submission_deadline_time` is `"01:00"` resolves to `23:00Z` the previous day, so the sliced date names Tuesday beside `jerusalemWeekday`'s «יום רביעי» — the exact class of same-instant-different-day disagreement `jerusalem.ts` was written for.

`jerusalemIsoDate(instant)` is the shipped re-zoning step every other instant-to-Jerusalem-calendar-day read in that file goes through (`todayJerusalem()` is two lines below `plainDayMonth` and does exactly this). **The composition is `plainDayMonth(jerusalemIsoDate(deadline_at))` — an instant becomes a Jerusalem plain date, and only then meets the plain-date formatter.** `jerusalemDate` is the near sibling and is deliberately *not* used: it appends the year, and the year already lives once per panel in the week range line (F-7).

The separator inside `{{day}}` is a **comma**, matching §2.3's wireframe and §9.2's annotation. Not « · » — that separator is `atelier.stageCount`'s and belongs between a label and a number, whereas `shifts.deadline` already puts a comma between `{{day}}` and `{{time}}` and two separators in one line is a shape nobody can read back.

`jerusalemWeekday(instant)` is **one new function in `lib/jerusalem.ts`**, not a formatter built in the component — that file's own header says every formatter passes `timeZone: JERusalem` and is never re-declared, and its `TZ=America/New_York` unit block is the guard that makes the rule enforceable. That block gains one case: **`jerusalemWeekday` and `plainDayMonth(jerusalemIsoDate(…))` on the same instant must name the same day**, which is the assertion that would have caught both failures above. The date is added to the spec's «יום רביעי, 18:00» sketch because a bare weekday is ambiguous the moment she pages three weeks out, and the ±4 window means she can.

### 2.7 Save failures, and the one that must change the screen

Codes map to Hebrew before render; the server's English never reaches this page (`StaffSection.tsx:18-23`'s `MAPPED_CODES` is the shipped shape, and F38's build note that an unmapped code renders English on a green build applies verbatim).

| Code | Rendered | Extra behaviour |
|---|---|---|
| `SUBMISSION_CLOSED` (409) | `shifts.errors.closed` | ⚠ **the panel also flips to state K, refetches the week, and MOVES FOCUS** — see below |
| `WEEK_OUT_OF_RANGE` (400) | `shifts.errors.weekOutOfRange` | refetch to the server's default week |
| `NOT_AUTHORIZED` (403, self-or-elevated guard) | `shifts.errors.notAuthorized` (§9.6) | reachable from `WeekSubmissionsPane`'s on-behalf save, not from this pane |
| `NOT_FOUND` (404, unknown template / staffer) | `shifts.errors.notFound` (§9.6) | refetch — a template was removed under her |

⚠ **403 and 404 get their own keys; they may not borrow the shipped house ones.** All three `*.error.NOT_AUTHORIZED` strings in the bundle (`staff`, `privacy`, `customers`) say the action is «לבעלת הבוטיק בלבד» — *owner only* — which is **false here**: D5 admits a shift manager to the on-behalf write, and that is the one thing this 403 must not claim. `i18n.test.ts` separately forbids a 403 body from naming which role holds the permission at all («a probe cannot learn which roles exist»). The shipped shape that satisfies both is `board.accessEnded` / `floor.accessEnded` — it names the owner as **who to ask**, never as the gate — and §9.6's new rows follow it verbatim in structure. Leaving these two unkeyed is what F38's build note calls out: an unmapped code renders the server's English sentence, right-aligned, in a Hebrew console, on a green build.

**Focus on `SUBMISSION_CLOSED`.** ⚠ State K **removes** the save button (§2.5-K) — the very control she just activated. Focus falls to `<body>` and her next Tab restarts at the skip link, so a keyboard user who has just marked twelve shifts must traverse the shell and the whole nav to reach the `<dl>` the locked screen exists to show her (WCAG 2.4.3). The locked banner therefore takes `ref` + `tabIndex={-1}` and is focused in a `useEffect` keyed on the state that carries the answer — `BookingDetail.tsx:108-120`'s shipped rescue, whose comment documents this exact failure and the exact reason a `.focus()` on the *trigger* is a no-op once that trigger is gone. This is one of the three named exceptions in §10's focus contract.

### 2.8 Locked renders text, not disabled radios

The spec's sketch says "all radios `disabled`". ⚠ **A disabled control is not focusable**, so a keyboard or screen-reader user in a locked week cannot reach the answers she already gave — the one thing the locked screen exists to show her. Drawn instead as a `<dl>`: `<dt>` the shift (day · label · `<bdi dir="ltr">HH:MM–HH:MM</bdi>`), `<dd>` her state word, or `shifts.stateUnanswered` «לא נרשם» for a shift she never answered.

Less DOM, fully readable, **zero disabled controls for axe to reason about**, and the information is in text where text is what it is. Recorded as a deliberate departure (§10 P6).

### 2.9 P1 must announce, or it is the one control a blind staffer cannot use

⚠ **«סימון כל השאר כזמינה» silently mutates up to twelve radio groups.** It is the single control this design adds to cut 14 taps to 4, and drawn without a live region it is the one control on the surface whose entire effect is invisible to a screen-reader user: the button's own name does not change, the twelve groups are below it, and the only evidence anything happened is the progress line. §10's own rule — *"no state on any pane renders text only a sighted staffer receives"* — makes that a defect, not an omission.

**Resolution: the progress line carries `role="status"`.** It already says exactly what she needs (`shifts.answered` «נענו: 12 מתוך 12»), it already re-renders on every answer including P1's bulk fill, and making it a live region announces the fill's *result* rather than a separate cue that could disagree with it. **No new copy key** — a `shifts.markRestDone` would be a second sentence about a number the first sentence already carries, and the two could drift.

So `MyWeekPanel` has **two** live regions, not one: the week range line (a week change has no other voice) and the progress line (a bulk fill has no other voice). Both `role="status"`, both polite, neither on a timer. Every other individual answer also updates the progress line, which is correct: `role="status"` is polite and coalesces, and a reader arrowing through a group hears the option name from the radio itself.

### 2.10 The weekday heading's date, and the third `addDays`

Each weekday `<section>` heading is `shifts.dayHeading` «{{day}} · {{date}}» → «ראשון · 8.11», where `{{day}}` is `DAY_NAMES[n]` (§7) and `{{date}}` is `plainDayMonth(addDays(week_start, n))`.

⚠ **`week_start + n` is date arithmetic, and §0 forbids it in a component.** `week_start` is a plain `YYYY-MM-DD` (never an instant), and the naive `new Date(week_start).getDate() + n` is wrong under exactly the `TZ=America/New_York` this repo's `jerusalem` and `dateRange` suites deliberately run: `new Date("2026-11-08")` parses as UTC midnight, reads back as the 7th locally, and the Sunday heading renders «ראשון · 7.11».

**The helper exists twice and is private both times** — `ReservationsPane.tsx:63` and `RescheduleDialog.tsx:17`, each with its own header explaining the UTC-parts rule (*"DATE PARTS, NEVER MILLISECONDS"*). F39 would be the third copy. **`addDays(isoDate, days)` therefore moves to `lib/week.ts` beside `DAY_NAMES`** (§7, §8) — one implementation, one UTC rule, one test. `packages/ui/src/lib/hours.ts`'s `addDays` is a different function on a different type (`JerusalemDate`, zoned) and is not the one to import.

`# ponytail: ReservationsPane and RescheduleDialog keep their private copies in this feature — collapsing them is a two-file follow-up with its own test surface, and F39 does not need to touch either file to stop being the third copy.`

---

## 3. `WeekSubmissionsPane` — roster readiness (elevated)

```
Card
  h2  מי הגישה
  [ השבוע הקודם ]  <p role="status"> שבוע 8–14 בנובמבר  [ השבוע הבא ]
  <p> הגישו 5 מתוך 8
  <ul>
    <li> <bdi>מיכל ברזילי</bdi>  [טרם הגישה]      [ רישום עבור מיכל ברזילי ]   ← not-yet rows FIRST
    <li> <bdi>Ronit</bdi>        [טרם הגישה]      [ רישום עבור Ronit ]
    ─────────────────────────────────────────────────────────────────
    <li> <bdi>דנה כהן</bdi>      [הגישה]  נענו: 12 מתוך 12  [ רישום עבור דנה כהן ]
    <li> <bdi>שירה לוי</bdi>     [הגישה]  נענו: 7 מתוך 12   [ רישום עבור שירה לוי ]
  </ul>
```

**The per-row progress text is `shifts.answered`, reused verbatim from `MyWeekPanel`** — «נענו: {{answered}} מתוך {{total}}», the same string measuring the same thing on two panes, listed once in §9.2 and cross-referenced from §9.3. ⚠ It carries **no trailing noun** (§9.0), which is what makes the reuse legal: the spec-era «… משמרות» would have added a word to a row that must stay on one line at 375 beside a badge and a 44px button, and the sketch above was measured without it.

- **The unsubmitted week is not an empty state.** «הגישו 0 מתוך 8» over eight «טרם הגישה» rows is the correct and informative Monday render. An `EmptyState` here would announce a fault where there is a schedule.
- **`submitted` is "at least one live row"**, and the partial case is shown as a count rather than hidden behind a boolean. ⚠ The spec leaves the predicate unstated; making it "answered every template" would punish a deliberate blank, and D8 has no way to distinguish a blank from a refusal — so the boolean says *she started* and the count says *how far she got*. Both are already on the wire (`WeekSubmissionRow.entries` vs the templates read); no API change.
- Badges: `Badge variant="warning"` «טרם הגישה», `Badge variant="success"` «הגישה». **The word carries the state**; the variant is redundant reinforcement that survives greyscale (`lib/booking.tsx`'s shipped law).
- **Offboarded staff never appear** (D10). If the expanded row's staffer disappears on a refetch, the expansion collapses — one guard, no message: she is gone from the screen, which is the message.
- **Long Hebrew names**: row is `flex flex-wrap items-center gap-2`, the name is a bare `<bdi>` with `break-words`, the badge follows in flow and can never be pushed out of the 720px column. At 375 the badge and the button wrap under the name.

### 3.1 Recording on her behalf — a form, never a write-on-tap

⚠ **D11's `PUT` is a whole-week replace: entries not present are soft-deleted.** The spec's sketch, "each state is tappable — that is the D5 on-behalf-of write", cannot mean write-on-tap: each tap would have to resend that staffer's complete entry set, producing twelve full-week replaces, twelve audit rows and a race with her own save.

Drawn as: the row expands to **the same `<fieldset>` control `MyWeekPanel` uses** — literally the same file (§8) — pre-filled with that staffer's states, plus:

1. `<p>` `shifts.onBehalfNote` — «הזמינות תירשם על שמך כמי שרשמה אותה.» **Before** the act, because `recorded_by` is about to make it permanent and visible on her screen.
2. `[ שמירה עבור <bdi>{{name}}</bdi> ]`, `size="md"`, one request, one audit row.
3. On success, `role="status"` `shifts.onBehalfDone` and the row's badge flips to «הגישה» locally (F51's patch-don't-refetch rule).

⚠ **The expanded form carries `MyWeekPanel`'s weekday grouping too — the same `<section>` + heading + `shifts.dayHeading`, not a bare run of fieldsets.** The legend is `label · HH:MM–HH:MM`, and `label` is **free operator text** (`shifts.templateLabel` «שם המשמרת»); neither D2 nor this design imposes uniqueness, and D3's auto-labels («ראשון 09:00–17:00», which do carry the day) are replaced the moment she splits a day — the obvious naming being «משמרת בוקר» / «משמרת ערב». Without a day grouping a shift manager expands Michal's row and sees six legends all reading «משמרת בוקר · 09:00–14:00» with nothing distinguishing Sunday from Tuesday, then records «לא זמינה» against the wrong day — a write that stamps `recorded_by` permanently and surfaces on Michal's own screen as «נרשם על ידי…». The day context cannot be left to a string the owner owns.

Heading level inside the expanded row is **`h3`** (Card `h2` → `h3` per weekday), which keeps §10's order intact on this pane; `MyWeekPanel`'s own `h3` per weekday is the identical level under its identical `h2`, so the shared component takes the level as a prop and nothing is skipped on either mount.

Focus: the expand button survives the expansion and survives the save, so focus stays on it and no move is needed **on this pane**. That is a claim about this pane only — see §10 for the three flows elsewhere in the feature that *do* unmount their trigger and therefore do move focus.

---

## 4. The deadline Card (elevated) — `tenants.settings.scheduling`

Two controls and one save, in their **own `Card`** with `h2` `shifts.deadlineHeading`.

```
Card
  h2  מועד ההגשה
  <p> הזמינות לכל שבוע נסגרת ביום ובשעה האלה, בשבוע שלפניו.
      אחראית משמרת יכולה לרשום זמינות גם אחרי המועד.
  [ Select: יום ההגשה האחרון ▾ רביעי ]   [ TimeField: שעת ההגשה  18:00 ]
  [ שמירת מועד ההגשה ]   <span role="status"> נשמר לפני רגע
```

- **Its own Card, not a `Modal` and not a block inside the templates Card.** A dialog for two fields is chrome (`AtelierSection`'s settings dialog earns one because it carries five effort bands and a default); and filing a submission deadline under a heading that says «משמרות הבוטיק» is a small lie about what the setting governs.
- **One save for both fields, and that is structural.** D6: `merge_settings` is one atomic `settings = settings || :patch::jsonb`, `||` merges at the **top level only**, so a patch carrying a partial `scheduling` object replaces the whole key and deletes what it did not name. A "save day" button and a "save time" button would erase each other. One dialog, one save, one request — `AtelierSettingsUpdate`'s shipped rule, and `api.ts:130-142` states it in a comment F39 should point at rather than re-derive.
- The weekday `Select` renders `DAY_NAMES` 0…6 (§7). The `TimeField` is the shared `Input type="time"` — native, keyboard-complete, OS-locale-formatted, zero bytes.
- Defaults arrive **default-complete** on the wire (D6: `{...SCHEDULING_DEFAULTS, ...stored}`), so no control here ever needs `?? default` — the `toggles` D3 shape.
- The help paragraph's second sentence is D5 stated to the person who sets the number. An owner choosing Wednesday 18:00 needs to know that it does not lock *her*.

---

## 5. `ShiftTemplatesPane` (elevated) — one Card, seven weekday groups

```
Card
  h2  משמרות הבוטיק
  <section> h3 ראשון
     <ul>
       <li> משמרת בוקר   <bdi dir=ltr>09:00–14:00</bdi>   [עריכה] [הסרה]
       <li> משמרת ערב    <bdi dir=ltr>13:00–20:00</bdi>   [עריכה] [הסרה]
     </ul>
     [ הוספת משמרת ]
  ─ border-t hairline ─
  <section> h3 שני
     …
  <section> h3 שבת            ← rendered, empty, with no list and the add button
```

**One Card, seven `<section>`s, hairline-separated — not seven Cards.** The spec's sentence ("the seven weekdays, each a `Card`") is a sketch with no D-number on it; seven `p-6` boxes is 336px of padding alone inside a 720px column, and F35 §2 already ruled that shape ("20 cards in a 448px dialog is a scroll of chrome"). Recorded as a departure (§10 P3).

- **Saturday renders.** It is empty for almost every boutique (D3 — no `availability_rules` row, so the seed makes no template), and hiding it would make the absence look like a bug rather than the tenant's own data. The add button is there if a boutique does open on Saturday.
- **The per-day cap teaches, it does not just disable.** At `MAX_TEMPLATES_PER_DAY = 6` the add button goes `disabled` **and** a muted `shifts.dayLimitReached` line renders beside it. A disabled control whose reason lives only in a `title` is unreachable by keyboard and by AT.
- ⚠ **`MAX_TEMPLATES = 42` is unreachable through this UI** — 6 × 7 = 42 exactly, so the per-day cap always bites first. It is a server-side guard against a non-UI caller and needs no screen of its own. Stated so nobody designs a total-count meter for a number that cannot be hit.
- **Edit expands the row in place** (F51/`StaffSection`'s shape: list row = read-only meta + two buttons, edit panel = every editable field): `Select(יום)` · `Input(שם המשמרת)` · `TimeField(שעת התחלה)` · `TimeField(שעת סיום)` + `[שמירת המשמרת] [ביטול]`. `sort_order` is **not** a visible field — the list orders by `(day_of_week, sort_order, starts_at_time)` and a manual order box on a two-item list is a control nobody wants. A `PATCH` is a full replace of all five (D2), so the client sends the four edited plus the row's existing `sort_order`.
- **Remove** opens a `Modal` confirm, `variant="danger"` on both the row button and the footer confirm (`StaffSection.tsx:342-352` / `DressEditor.tsx:401` are the house destructive pattern; single-digit rows, so the platform console's table-density exception does not apply). ⚠ **The confirm needs an explicit focus destination.** `packages/ui`'s `Modal` returns focus to its trigger on close — but this trigger is the `[הסרה]` button **on the row that was just deleted**, so on the success path it returns focus to a node that no longer exists and focus lands on `<body>`. On confirm-and-succeed, focus moves to that weekday `<section>`'s `[הוספת משמרת]` button, which is the nearest surviving control in the same group and the plausible next act; on cancel, the `Modal`'s own return is correct and nothing overrides it. §10's second named exception.

### 5.1 D4's invalidation count, and the wire field it needs

D4 binds: *"the owner's confirm dialog states the count **before** she commits."* ⚠ **No route in §API can answer that.** `invalidated_submissions` exists only in the audit `details` of a write that has already happened.

**Resolution — one field, no new route**: `GET /manage/shifts/templates` carries `future_submission_count: number` per template for an elevated reader (one grouped aggregate over `staff_availability` where `week_start > current_week_start`). The templates read already runs when this pane mounts; nothing new is fetched and no read writes anything (F37 D6's principle holds).

**Rejected**: a dedicated preview route — a ninth route whose whole job is to predict a write it does not perform, i.e. the exact read/write disagreement D5 spends a paragraph forbidding. **Rejected**: paging `GET /manage/shifts/week/submissions` across four future weeks to count client-side — four requests to render one sentence.

Then:

- **Confirm dialog** (edit **and** remove): `shifts.invalidateWarning` — «שינוי המשמרת ימחק תשובות שכבר נרשמו לשבועות הבאים. תשובות שיימחקו: {{total}}» — and **rendered only when the count is > 0**. "Will delete 0 answers" is noise on the overwhelmingly common case. ⚠ This is a **redraft of the spec deck's row**, on grammar, not on meaning: see §9.0.
- **A label-or-`sort_order`-only edit invalidates nothing** (D4), so it opens **no confirm at all** and saves straight through. The confirm appears exactly when `day_of_week`, `starts_at_time` or `ends_at_time` moved — the client compares the four fields it holds, which is the same predicate the server applies.
- **After the write**, `role="status"` `shifts.invalidateDone` «תשובות שנמחקו לשבועות הבאים: {{total}}» with the count **the response returned**, which is the truth and may differ from the predicted one if somebody submitted in between. Again suppressed at 0.

### 5.2 Seed — `EmptyState`, and the refusal teaches

When no template exists anywhere (§1.1 has already made this the only Card on screen):

```
EmptyState
  title   משמרות הבוטיק              ← reuses shifts.templatesHeading
  body    shifts.templatesEmptyBody  — once, from opening hours, splittable afterwards
  action  [ יצירת משמרות משעות הפעילות ]   Button primary md
```

⚠ **The button is rendered unconditionally; it is not gated on a pre-check for `availability_rules`.** The spec sketch says "when no `availability_rules` exist either, that button is replaced by a line pointing at «שעות פעילות»". Doing that needs a `GET /manage/availability` on every mount of this pane, purely to hide a control the server already guards with `409 NO_OPENING_HOURS` — a second reader that can disagree with the writer. **`409 NO_OPENING_HOURS` → `shifts.seedNoHours`** on a `role="alert"` line under the button; she learns the same fact, one request later, from the only component that actually knows.

- `409 TEMPLATES_ALREADY_SEEDED` → `shifts.errors.alreadySeeded`, **and refetch** — two managers seeding at once is the only way to reach it, and the winner's templates should appear rather than an error over a blank list.
- Success → `role="status"` `shifts.seedDone` «משמרות שנוצרו משעות הפעילות: {{total}}» and the pane repopulates. The other three panes mount for the first time (§1.1's `if` releases).
- ⚠ **Success unmounts the button she just pressed, so it moves focus.** The `EmptyState` containing `[יצירת משמרות משעות הפעילות]` is replaced by seven populated weekday groups, and §1.1's `if` simultaneously releases three more Cards above — the largest re-render in the feature, and focus falls to `<body>` under it. The `role="status"` `shifts.seedDone` line takes `ref` + `tabIndex={-1}` and is focused on the render that carries the result (`BookingDetail.tsx:108-120`'s shape): she lands on the sentence that says how many were created, with the new list after it in tab order. §10's third named exception.
- **`capacity` is dropped** (D3) and nothing on this screen alludes to headcount. There is no "how many staff" field anywhere in F39; that is F40's coverage model.

---

## 6. Responsive — 375 / 768 / 1440

`ConsoleShell` caps `#console-main` at `max-w-[720px]`, so **768 and 1440 render identically** — the only real breakpoint on this surface is `sm` (640), where wrapped rows come back onto one line. Stated plainly because a design that claims three distinct desktop layouts inside a 720px column is claiming something the shell forbids.

| Width | Deltas |
|---|---|
| **375** | Everything single-column. The four radios sit **2×2 at 143px cells** (§2.3, measured) — the one place the fourth option costs a row of height, and the alternative is a truncated state word. Week bar wraps to two rows: the two buttons, then the range line. Template rows wrap label / times / buttons. Submissions rows wrap badge + button under the name. `Card`'s baked-in `p-6` is **not** overridden |
| **768** | Content is 720px + gutters; rows stop wrapping and the radios go **4-across at 162px** (`sm:grid-cols-4`, so the switch actually happens at 640). No other layout change of its own |
| **1440** | Byte-identical to 768. The column is centred in cream |

**No horizontal scroll at any of the three**, asserted in the e2e leg. The only overflow risks are a long shift label beside a time range and a long Hebrew display name beside two badges — both wrap, neither scrolls.

---

## 7. `lib/week.ts` — `DAY_NAMES` gets a second consumer, `addDays` gets a home

`HoursSection.tsx:9` holds the seven Hebrew day names at indices 0–6 as a module-local const. F39 needs the same seven, in the same order, on three panes. **Move it to `apps/manage/src/lib/week.ts` and import it from both** — one array, one order, one place; `HoursSection` is already in the spec's file list for its one line of copy (§below), so the import swap rides along. Two copies of a seven-element array that must agree with `availability_rules.day_of_week` is exactly the drift `lib/roles.ts` was written to end.

The day **index** stays `jerusalemDayIndex` from `@boutique/ui/lib/hours` — pinned to the backend by `test_frontend_constant_parity.py`, never re-derived here.

**`addDays(isoDate, days)` lands in the same file** (§2.10). It is the only date arithmetic F39 performs, it operates on the same plain `YYYY-MM-DD` `week_start` that `DAY_NAMES` is indexed against, and putting it anywhere else would make F39 the third private copy of a nine-line UTC-parts helper. Its own `TZ=America/New_York` test block moves with it — the guard that makes «ראשון · 8.11» reproducible outside Israel.

**The `HoursSection` pointer line** (D3's dependency, stated where the owner is) is **hardcoded Hebrew**, matching that file, which ships no i18n keys at all. Minting one key for one line in a keyless file is the drift, not the fix:

> «המשמרות של הצוות נוצרות משעות הפעילות האלה, במסך «זמינות למשמרות».»

---

## 8. Files — the spec's list, plus one

Everything in the spec's Frontend Changes table stands. Two additions and one relocation:

| File | Why |
|---|---|
| `components/ShiftAvailabilityFieldset.tsx` | **NEW, a fifth component.** The three-state fieldset has **two mounts on day one** — `MyWeekPanel` and `WeekSubmissionsPane`'s expanded row — and both are inside the axe gate. Two copies means the accessibility contract is written twice and can diverge once. Still **no `@boutique/ui` export** (D13): app-local, one file, `SlotPicker` remains the extraction template when a third consumer appears |
| `lib/week.ts` | **NEW.** `DAY_NAMES` + `addDays(isoDate, days)` (§7, §2.10) |
| `lib/jerusalem.ts` | `jerusalemWeekday(instant)` — one function, in the file whose rule it obeys (§2.6), plus the unit case asserting it agrees with `plainDayMonth(jerusalemIsoDate(…))` |
| `components/HoursSection.tsx` | the pointer line **and** the `DAY_NAMES` import swap |

`ShiftsSection` is the container both panes import, so the fieldset cannot live there — that is the import cycle `lib/booking.tsx`'s header documents.

---

## 9. Copy deck — `he.ts` + `ar.ts` added together, `ar` = the approved Hebrew standing in untranslated (Q3 / #47), never `""`

**Zero exclamation marks** (#5, enforced by `__tests__/i18n.test.ts`). Feminine address throughout. Rows marked ✓ are **verbatim from the spec's copy table**. Rows marked ✎ are **spec rows redrafted here on a mechanical defect** — the reason is stated per row and the meaning is unchanged; they need approval like any new row. The rest are new.

### 9.0 Two mechanical rules every row in this deck obeys

**(a) No plural Hebrew noun after an interpolated numeral, and never the variable name `count`.** The shipped bundle states this in words twice — `atelier.stageCount`: *"it carries NO NOUN: «{{total}} כרטיסים» is wrong at 1 and wrong at 2 (Hebrew takes a dual), and doing it properly needs four plural suffixes per string in two bundles"*; and `atelier.capacity.headingCount` repeats it, adding *"`{{total}}`, NEVER `{{count}}`: `count` is i18next's plural-resolution trigger."* The house shape is **label-then-number** (`booking.dayCount` «תורים ביום זה: {{count}}», `customers.count` «לקוחות ברשימה: {{count}}»).

Five rows in the first draft broke it, all guarded only by "suppressed at 0" — which does nothing at 1. A boutique that has entered only Sunday opening hours seeds and reads «נוצרו 1 משמרות משעות הפעילות.»; an owner fixing a typo on a template with one future answer reads «שינוי המשמרת ימחק 1 תשובות…». Both are ungrammatical Hebrew on a first-run screen. Redrafted (✎): `shifts.seedDone`, `shifts.invalidateWarning`, `shifts.invalidateDone`, `shifts.answered`, `shifts.dayLimitReached`. `shifts.submittedCount` ✓ already obeyed and is untouched.

**(b) Every interpolated human name is `<bdi>`-wrapped inside the copy value, and its row renders through `<Trans>`.** R19 is binding (§0) and a name interpolated by `t()` cannot be isolated any other way — the shipped shape is markup in the value plus `<Trans components={{ bdi: <bdi /> }}>` (`staff.deactivateBody`, `staff.offboardDone`), and `i18n.test.ts` asserts the `<bdi>` survives in the raw string. Four rows carry a name: `shifts.recordedBy` (✎ — it ends with a full stop **immediately after** the name, so for «Ronit Bar» the period resolves to the RTL paragraph direction and renders «נרשם על ידי .Ronit Bar», and this line is both seen and spoken, being the fieldset's `aria-describedby`), `shifts.expandRow`, `shifts.onBehalfSave`, `shifts.onBehalfDone`.

⚠ **Not `<bdi dir="ltr">`** — R19's own second half: a `dir="ltr"` on a Hebrew name is itself a defect, and three of the four names on this surface are Hebrew. Bare `<bdi>`.

### 9.1 Nav + guide

| Key | Hebrew | EN annotation |
|---|---|---|
| `nav.shifts` ✓ | זמינות למשמרות | "Shift availability" — the nav row, inserted after «תפירה» |
| `guide.shifts.1` | כאן מסמנים לאילו משמרות את זמינה בשבוע הקרוב, ושומרים. | step 1 of 2 |
| `guide.shifts.2` | אחראית המשמרת רואה מי כבר הגישה, ויכולה לרשום זמינות במקום מי שלא הספיקה. | step 2 — role-blind by design: `GuideOverlay` renders one step list per section, and a staffer knowing that `recorded_by` exists is the transparency D5 is built on |

### 9.2 `MyWeekPanel`

| Key | Hebrew | EN annotation |
|---|---|---|
| `shifts.myWeekHeading` ✓ | הזמינות שלי | pane `h2` |
| `shifts.weekLabel` | שבוע | precedes the formatted range |
| `shifts.prevWeek` | השבוע הקודם | **words, not a chevron** (DL20) |
| `shifts.nextWeek` | השבוע הבא | |
| `shifts.deadline` ✓ | מועד ההגשה: {{day}}, {{time}} | `{{day}}` = «יום רביעי, 4.11» = `jerusalemWeekday(deadline_at)` + `", "` + `plainDayMonth(jerusalemIsoDate(deadline_at))`; `{{time}}` = `jerusalemTime(deadline_at)`. ⚠ the re-zone step is not optional — §2.6 |
| `shifts.dayHeading` | {{day}} · {{date}} | weekday `<section>` `h3`. `{{day}}` = `DAY_NAMES[n]`, `{{date}}` = `plainDayMonth(addDays(week_start, n))` (§2.10). « · » is `atelier.stageCount`'s shipped separator |
| `shifts.markRestAvailable` | סימון כל השאר כזמינה | P1. Fills only shifts sitting on «לא נרשם»; writes nothing. Its result is announced by `shifts.answered`'s `role="status"` line, not by a cue of its own (§2.9) |
| `shifts.states.available` ✓ | זמינה | |
| `shifts.states.unavailable` ✓ | לא זמינה | |
| `shifts.states.preferred` ✓ | מעדיפה | advisory to F40, never a constraint (D8) |
| `shifts.stateUnanswered` | לא נרשם | **two mounts**: the fourth radio's label (§2.2) and the locked `<dl>`'s value for a shift she never answered. One string, because it is one state |
| `shifts.answered` ✎ | נענו: {{answered}} מתוך {{total}} | derived, never fetched. `role="status"` (§2.9). **Reused verbatim** as `WeekSubmissionsPane`'s per-row progress (§3). ✎ dropped the trailing «משמרות» — §9.0(a); it was wrong at 1 and it is the word §3's one-line row was measured without |
| `shifts.save` ✓ | שמירת זמינות | |
| `shifts.recordedBy` ✎ | נרשם על ידי \<bdi\>{{name}}\</bdi\>. | on the fieldset's `aria-describedby`, through `<Trans>`. ✎ added the `<bdi>` — §9.0(b); the full stop lands immediately after the name and reorders without it |
| `shifts.locked` ✓ | מועד ההגשה לשבוע הזה עבר. אפשר לפנות לאחראית המשמרת כדי לעדכן. | `role="status"` banner |
| `shifts.lockedElevated` | מועד ההגשה עבר. הרישום שלך עדיין אפשרי. | elevated only (D5) |
| `shifts.goToOpenWeek` | מעבר לשבוע פתוח | beside the locked banner |
| `shifts.noTemplates` ✓ | עדיין לא הוגדרו משמרות לשבוע הזה. | `EmptyState` title |
| `shifts.noTemplatesStaffBody` | כשאחראית המשמרת תגדיר משמרות, אפשר יהיה לסמן כאן זמינות. | body — so a blank screen reads as a fact and not as her fault |
| `shifts.loadFailed` | לא הצלחנו לטעון את הנתונים כרגע. | house `{ns}.loadFailed` shape. ⚠ **feature-wide, not this pane's** — all four panes render it on their own load failure (§1.2), which is why it says «הנתונים» and not «הזמינות»: one `{ns}` pair per section is the shipped shape |
| `shifts.retry` | ניסיון נוסף | **verbatim** from `booking.retry` / `checkinQr.retry` / `bell.retry`. No drift. Also feature-wide (§1.2); retry re-issues only its own pane's read |

### 9.3 `WeekSubmissionsPane`

| Key | Hebrew | EN annotation |
|---|---|---|
| `shifts.submissionsHeading` | מי הגישה | pane `h2` |
| `shifts.submittedCount` ✓ | הגישו {{submitted}} מתוך {{total}} | numerals in `<bdi dir="ltr">` |
| `shifts.notSubmitted` ✓ | טרם הגישה | `Badge variant="warning"` |
| `shifts.submitted` | הגישה | `Badge variant="success"` |
| `shifts.expandRow` | רישום עבור \<bdi\>{{name}}\</bdi\> | the expand button's visible label — it *is* the accessible name, computed from the rendered text, so the `<bdi>` costs it nothing. `<Trans>`, §9.0(b) |
| `shifts.close` | סגירה | collapses the expanded row |
| `shifts.onBehalfNote` | הזמינות תירשם על שמך כמי שרשמה אותה. | before the act |
| `shifts.onBehalfSave` | שמירה עבור \<bdi\>{{name}}\</bdi\> | `<Trans>`, §9.0(b) |
| `shifts.onBehalfDone` | הזמינות של \<bdi\>{{name}}\</bdi\> נשמרה. | `role="status"`. `<Trans>`, §9.0(b) — the name sits **mid-string**, the one position where a Latin-script name reorders visibly (`rooms.deleteConfirm`'s note) |
| — | *(per-row progress)* | **no new key**: `shifts.answered` (§9.2), reused verbatim |

### 9.4 Deadline Card

| Key | Hebrew | EN annotation |
|---|---|---|
| `shifts.deadlineHeading` | מועד ההגשה | pane `h2` |
| `shifts.deadlineDay` | יום ההגשה האחרון | `Select` label |
| `shifts.deadlineTime` | שעת ההגשה | `TimeField` label |
| `shifts.deadlineHelp` | הזמינות לכל שבוע נסגרת ביום ובשעה האלה, בשבוע שלפניו. אחראית משמרת יכולה לרשום זמינות גם אחרי המועד. | D5 told to the person who sets the number |
| `shifts.deadlineSave` | שמירת מועד ההגשה | |

### 9.5 `ShiftTemplatesPane`

| Key | Hebrew | EN annotation |
|---|---|---|
| `shifts.templatesHeading` ✓ | משמרות הבוטיק | pane `h2`, reused as the `EmptyState` title |
| `shifts.templatesEmptyBody` | המשמרות נוצרות פעם אחת משעות הפעילות, ואפשר לפצל ולשנות אותן אחר כך. | states that the seed is once-only and refusable (D3) |
| `shifts.seed` ✓ | יצירת משמרות משעות הפעילות | |
| `shifts.seedDone` ✎ | משמרות שנוצרו משעות הפעילות: {{total}} | `role="status"`, and the focus destination on the seed success path (§5.2). ✎ label-then-number — §9.0(a); the draft's «נוצרו 1 משמרות…» is the literal first-run render for a boutique with one opening-hours row |
| `shifts.seedNoHours` ✓ | לא הוגדרו שעות פעילות. אפשר להגדיר אותן במסך שעות פעילות. | rendered from `409 NO_OPENING_HOURS`, never from a pre-check |
| `shifts.addTemplate` | הוספת משמרת | |
| `shifts.dayLimitReached` ✎ | מספר המשמרות המרבי ליום: {{total}} | the disabled-button reason **and** the `400 TEMPLATE_LIMIT_REACHED` message — one string, two arrivals. ✎ label-then-number and `{{total}}` not `{{count}}` — §9.0(a) |
| `shifts.templateDay` | יום | |
| `shifts.templateLabel` | שם המשמרת | |
| `shifts.templateStart` | שעת התחלה | |
| `shifts.templateEnd` | שעת סיום | |
| `shifts.templateSave` | שמירת המשמרת | |
| `shifts.templateCancel` | ביטול | |
| `shifts.edit` | עריכה | |
| `shifts.remove` | הסרה | also the `danger` confirm in the Modal footer |
| `shifts.editTitle` | לשמור את השינוי במשמרת? | Modal title, material edits only |
| `shifts.removeTitle` | להסיר את המשמרת? | Modal title |
| `shifts.removeBody` | המשמרת לא תופיע יותר בשבועות הבאים. | |
| `shifts.invalidateWarning` ✎ | שינוי המשמרת ימחק תשובות שכבר נרשמו לשבועות הבאים. תשובות שיימחקו: {{total}} | pre-commit; **suppressed when the count is 0**. ✎ noun moved off the numeral — §9.0(a); D4's *meaning* (state the count before she commits) is unchanged, and «ימחק 1 תשובות» is the common single-answer case, not an edge |
| `shifts.invalidateDone` ✎ | תשובות שנמחקו לשבועות הבאים: {{total}} | post-commit, the **returned** count; suppressed at 0. ✎ §9.0(a) |

### 9.6 Error codes → Hebrew (every one goes into a pane's `MAPPED_CODES` — one map per pane, `StaffSection.tsx:18-23`'s shipped shape)

| Key | Server code | Hebrew |
|---|---|---|
| `shifts.errors.closed` ✓ | `SUBMISSION_CLOSED` 409 | מועד ההגשה לשבוע הזה עבר. |
| `shifts.errors.weekOutOfRange` ✓ | `WEEK_OUT_OF_RANGE` 400 | אפשר להגיש רק לשבועות הקרובים. |
| `shifts.errors.alreadySeeded` ✓ | `TEMPLATES_ALREADY_SEEDED` 409 | כבר קיימות משמרות. אפשר לערוך אותן ידנית. |
| `shifts.seedNoHours` ✓ | `NO_OPENING_HOURS` 409 | (§9.5) |
| `shifts.dayLimitReached` ✎ | `TEMPLATE_LIMIT_REACHED` 400 | (§9.5) |
| `shifts.errors.notAuthorized` | `NOT_AUTHORIZED` 403 | אין הרשאה לרשום זמינות עבור אשת צוות אחרת כרגע. לבירור אפשר לפנות לבעלת הבוטיק. |
| `shifts.errors.notFound` | `NOT_FOUND` 404 | המשמרת או אשת הצוות כבר לא זמינות. הרשימה תתוקן בעדכון הבא. |

⚠ **These last two are new rows and they exist because the first draft left both codes unkeyed** — §2.7 said "house `NOT_AUTHORIZED` copy" and "house 404 copy", and no such generic key exists. Borrowing one would be a lie: all three shipped `*.error.NOT_AUTHORIZED` strings say the action is «לבעלת הבוטיק בלבד», and D5 admits a **shift manager** to the on-behalf write. Both rows follow the shipped shapes exactly — `board.accessEnded` / `floor.accessEnded` for the 403 (owner named as who to *ask*, never as the gate, which is also what `i18n.test.ts`'s «no role in the 403 body» guard requires) and `floor.error.notFound` / `rooms.error.notFound` for the 404 («… כבר לא … הרשימה תתוקן בעדכון הבא.»). Unkeyed, F38's build note applies verbatim: the server's English sentence renders right-aligned in a Hebrew console on a green build.

**Client-side validation messages are not in this deck** — `validation.ts` returns hardcoded Hebrew (F51's rule, `validateUploadFile`'s precedent): «שעת הסיום חייבת להיות אחרי שעת ההתחלה.» · «יש להזין שם למשמרת.» · «שם המשמרת ארוך מדי.»

---

## 10. Accessibility contract — IS 5568 / WCAG 2.0 AA is a **legal** gate

- **Heading order**: shell `h1` (sr-only) → one `h2` per Card (1 for a staffer, 4 for an elevated actor) → `h3` per weekday → `<legend>` per shift. No level skipped, on any role's render — **including the expanded on-behalf row**, whose weekday groups are `h3` under `WeekSubmissionsPane`'s `h2` (§3.1), the same level the shared fieldset component takes as a prop on its `MyWeekPanel` mount. The `h2`s survive a pane's loading and failure renders (§1.2), so the order is identical in every state.
- **Keyboard order, `MyWeekPanel`**: skip link → chrome → nav → `[השבוע הקודם]` → `[השבוע הבא]` → `[סימון כל השאר כזמינה]` → **one stop per shift group**, in visual (day, then shift) order → `[שמירת זמינות]`. Arrow keys move and select inside a group; Tab leaves it. No roving index, no `role="radiogroup"`. The only `tabindex` anywhere in the feature is the `-1` on the three focus destinations below — never a positive one, never on anything the user can reach by Tab.
- **Focus management — the default is "do not move", with exactly three named exceptions.** Save, week navigation, row expansion and the on-behalf save all leave their trigger mounted, so the browser's own behaviour is correct and a manual move would be the defect. ⚠ **Three flows do not**, and each one drops focus to `<body>` — after which the next Tab restarts at the skip link and the user must traverse the shell and the whole nav (WCAG 2.4.3). Each takes `ref` + `tabIndex={-1}` + `.focus()` in a `useEffect` keyed on the state that carries the answer, which is `BookingDetail.tsx:108-120`'s shipped rescue and whose comment documents this exact failure mode:

  | Flow | What unmounts | Focus goes to |
  |---|---|---|
  | `SUBMISSION_CLOSED` mid-save → state K (§2.7) | the `[שמירת זמינות]` button she just pressed | the `role="status"` locked banner |
  | Seed success (§5.2) | the `EmptyState` holding the button she pressed, plus §1.1's `if` releasing three more Cards | the `role="status"` `shifts.seedDone` line |
  | Remove confirmed (§5) | the row carrying the `Modal`'s own return target | that weekday's `[הוספת משמרת]` |

  The `Modal`'s trap / Esc / backdrop / return-to-trigger stays `packages/ui`'s in every other case; the third row overrides **only** the return target, and **only** on the success path — on cancel the trigger is still there and the shipped behaviour is right.
- **Two live regions, both `role="status"`**: the week range line (a week change alters the whole pane under a button that never moved) and the **progress line** (§2.9 — P1's bulk fill mutates up to twelve groups and has no other voice; without it, the one control that cuts 14 taps to 4 is the one control a blind staffer cannot verify). **Not** `aria-live` on anything that ticks — there is no timer on this surface at all (§0), which is also what keeps SC 2.2.2 inapplicable.
- **Announcements that are the point of a state carry `role`**: `shifts.locked` and every terminal cue take `role="status"`; every failure takes `role="alert"` on first render as on retry. No state on any pane renders text only a sighted staffer receives.
- **Targets ≥ 44px**: every `Button` is `size="md"` (`min-h-11`); every radio label is `min-h-11` (D13); the expand button on a submissions row is a `Button md`. **No `size="sm"` anywhere in this feature** (F-W1, D13). ⚠ LOOP-STATE's 0032-era finding: `Modal`'s 0.97→1 open animation makes a compliant 44px control measure **42.68px mid-transition** — the e2e must call `settleAnimations(page)` (`e2e/fixtures/manage.ts:1041`) before measuring, and must never lower the floor to make a measurement pass.
- **Nothing is signalled by colour alone.** Radio selection carries fill + border + weight, and the option's meaning is the Hebrew word inside it. Submission state is a word inside a Badge. There is no green/red/gold state palette (§2.4).
- **Contrast, from `tokens.md`**: selected chip = ink on `--color-gold` 6.41:1; muted help = `--color-ink-muted` on `--color-surface` 5.61:1; `warning` Badge = `--color-warning-text` 5.20 on paper; `success` Badge 5.56 on paper. `--color-gold-strong` appears only as a border — it carries no text at any size.
- **Bidi**: every `HH:MM–HH:MM`, every count and the deadline time in `<bdi dir="ltr">`; the week range through `RangeText`'s two shapes (§11 F-7); display names in a **bare** `<bdi>`. Logical properties only (`ms-*`, `text-start`, `border-t`) — the qa-greps physical-direction ban applies.
- **Reduced motion**: this feature adds no motion of its own. The `Modal`'s panel/backdrop animation already respects `prefers-reduced-motion`.
- ⚠ **jsdom has no `<dialog>`** — `setup.ts` stubs `showModal()`, so a focus assertion that pre-places focus on its own target is vacuous. Unit tests assert the confirm's **content** (the invalidation count, the day/time in the deadline form); real focus behaviour belongs to the e2e leg.
- **Nothing is signalled by colour alone** — restated for the fourth radio: «לא נרשם» selected carries the same fill + border + weight as the other three, and its meaning is the word inside it (§2.4).
- **axe zero violations** on: the staffer's populated week, the locked week, the no-templates empty state, the elevated four-Card render, **every pane's loading render and every pane's load-failure render** (§1.2 — a `Skeleton` and a `role="alert"` + retry pair are as much a render as the populated one, and three of the four panes only got them in this revision), the expanded on-behalf row, and both `Modal`s — RTL, at 375.

---

## 11. ⚠ FINDINGS — things the spec leaves open that the build cannot

- **F-1 — `locked` must be actor-relative, or the owner's save button vanishes on a write that would have succeeded.** D5 exempts elevated actors from the deadline entirely, but `locked` is a bare boolean on the week payload with no actor in its name. Computed from `(setting, week)` alone it is `true` for an owner past Wednesday 18:00, the panel removes her save button per §2.5, and her legal write becomes unreachable — the precise "the page a person reads and the flow she then enters cannot disagree" failure D5 cites `deposit_due` for. **`locked` is false for `owner` / `shift_manager`, always**, and state K-e renders instead.
- **F-2 — D4's pre-commit count has no route to come from.** §5.1. Resolution: `future_submission_count` per template on the elevated `GET /manage/shifts/templates`. Without it, D4's binding sentence cannot be implemented and the confirm dialog silently loses its number.
- **F-3 — "each state is tappable" contradicts D11.** The `PUT` is a whole-week replace; a per-tap write would soft-delete every unsent entry. §3.1 draws it as a form with its own save.
- **F-4 — `WeekSubmissionRow.entries` cannot show the attribution it creates.** Its entry shape carries `{shift_template_id, state}` only, so the moment a shift manager records on someone's behalf, `recorded_by` is visible on the staffer's screen and invisible on the manager's. Make it `AvailabilityEntry[]` — the type already exists with `recorded_by_name`, and one type for one thing removes a divergence rather than adding a field.
- **F-5 — locked + `disabled` radios strand her own answers** from keyboard and AT. §2.8 renders a `<dl>` instead. Less DOM, no disabled controls, nothing for axe to weigh.
- **F-6 — the radio `name` must be keyed on the template id, not the weekday.** Overlapping same-day templates are legal and expected (D2); a weekday-keyed `name` fuses two shifts into one group and answering the second clears the first, with no error anywhere.
- **F-7 — a Sunday-start week crosses a month boundary roughly once a month, and the spec's header sketch covers only one of the two shapes.** «שבוע 8–14 בנובמבר» is `formatDateRange`'s `same-month` case; the week of 29 November is its `split` case, «29 בנובמבר – 5 בדצמבר», with different bidi isolation (`ReservationsPane.tsx:83-96`'s `RangeText`). **Reuse `formatDateRange` from `@boutique/ui`** — it is exported, UTC-parsed, and unit-tested under `TZ=America/New_York` precisely so a naive implementation reds outside Israel. `RangeText` itself is a 12-line presenter currently private to `ReservationsPane.tsx`; F39 is its second consumer, so it moves to `lib/dateRange.tsx` (`lib/booking.tsx` is the shipped precedent for a JSX helper in `lib/`, and its header states the cycle reason).
- **F-8 — the staffer cannot read `Settings`.** `GET /manage/settings` is gated `OWNER, SHIFT_MANAGER`. Her deadline line comes from `deadline_at` on the week payload and from nowhere else (§2.6). A build that prefills the line from `Settings` will pass every test an owner runs and 403 for three of the five roles.
- **F-9 — no pre-check for opening hours.** §5.2; the `409` teaches, one request later, from the component that knows.
- **F-10 — D12's five coordinated nav edits, restated so the design and `Nav.test.tsx` cannot drift.** `SectionKey` gains `"shifts"` (seventeenth) in `lib/guide.ts` with a non-empty `GUIDE_STEPS.shifts` tuple (the `satisfies` makes omission a type error); `App.tsx` gains `EVERY_ROLE = [...ALL, ...FLOOR_ONLY]` and one NAV row **immediately after `atelier`, before `checkinQr`**; and then: `NAV_LABELS` **15 → 16** with the new label inserted after «תפירה» · the owner test's name and assertion **fifteen → sixteen** · the shift-manager `.slice(0, 12)` → `.slice(0, 13)` in **both** places · the seamstress / reception / sales-assistant row-order assertions. The slot is forced from both sides: after `floor` so `reachable[0]?.key` still lands the three floor roles on «הצוות בקומה», before the three owner-only rows so the shift manager's prefix stays contiguous.
- **F-11 — `MAX_TEMPLATES = 42` is unreachable from this UI** (6 × 7). Server-side guard only; no meter, no counter, no screen.
- **F-12 — `DAY_NAMES` gains a second consumer.** §7.
- **F-13 — `SUBMISSION_CLOSED` mid-save must change the screen, not just annotate it.** §2.7.
- **F-14 — `plainDayMonth` must never be handed `deadline_at`.** §2.6. It takes a plain `YYYY-MM-DD` and splits on `-`; the instant `"2026-11-04T16:00:00Z"` splits to a day part of `"04T16:00:00Z"`, `Number(…)` is `NaN`, and the most-viewed line in the feature renders «יום רביעי, NaN.11, 18:00». Slicing the instant by hand instead reproduces D1/D6's DST bug — a UTC instant read as a Jerusalem calendar day names the wrong day for part of every year, and for a `01:00` deadline setting, always. **`plainDayMonth(jerusalemIsoDate(deadline_at))`**, with a `TZ=America/New_York` case asserting it agrees with `jerusalemWeekday` on the same instant.
- **F-15 — a native radio cannot be un-checked, so three options make D8's clear path unreachable.** §2.2. D8 clears by omission and D11 soft-deletes what the `PUT` does not name, but with three options «לא נרשם» → answered is one-way from every surface in the feature: a mis-tapped «מעדיפה» ships to F40 as advisory input, «נענו» only ever climbs, and a shift manager's mis-recorded row carries `recorded_by` forever. The fourth radio is the whole fix; nothing on the wire changes.
- **F-16 — the three elevated panes had no loading and no load-failure render.** §1.2. A 500 on `GET …/week/submissions` was indistinguishable from «nobody has submitted», which §3 says is the correct informative render. One contract for all four panes, and `shifts.loadFailed`/`shifts.retry` are feature-wide.
- **F-17 — three flows unmount the element holding focus.** §10. `SUBMISSION_CLOSED` removes the save button, seed success removes the `EmptyState`, and the remove confirm's `Modal` returns focus to a row it just deleted. All three drop to `<body>` (WCAG 2.4.3); all three get a named destination.
- **F-18 — P1 mutates twelve groups with nothing announced.** §2.9. The progress line becomes the second `role="status"` region; no new key.
- **F-19 — the on-behalf form had no day context, and the template `label` cannot supply it.** §3.1. `label` is free operator text with no uniqueness rule, and D3's day-carrying auto-labels are replaced the moment she splits a day — six legends reading «משמרת בוקר · 09:00–14:00» is a `recorded_by`-stamped write against the wrong weekday.
- **F-20 — 403 and 404 reach a user and had no keys.** §9.6. The three shipped `NOT_AUTHORIZED` strings all say «owner only», which D5 makes false here.
- **F-21 — five copy rows put a plural Hebrew noun after an interpolated numeral.** §9.0(a). «נוצרו 1 משמרות…» is the literal first-run render for a one-rule boutique. The shipped bundle states the rule in words twice and gives the label-then-number shape.
- **F-22 — four copy rows interpolate a human name with no `<bdi>`.** §9.0(b). `shifts.recordedBy` ends with a full stop immediately after the name, so «Ronit Bar» renders «נרשם על ידי .Ronit Bar» — on a line that is both seen and read aloud through the fieldset's `aria-describedby`.
- **F-23 — the weekday heading needs `week_start + n` and there is no exported helper.** §2.10. `addDays` is private twice already (`ReservationsPane.tsx:63`, `RescheduleDialog.tsx:17`) and §0 forbids a third private copy in a component; the naive `new Date(week_start).getDate()` renders «ראשון · 7.11» under the `TZ=America/New_York` this repo's suites deliberately run. It moves to `lib/week.ts`.

---

## 12. PROPOSED (user confirms at the gate)

- **P1 — «סימון כל השאר כזמינה».** The single largest thing this design does for the staffer: 14 taps → ~4. Non-destructive by construction (fills only unanswered shifts), writes nothing, and is not O4's copy-forward. The one control the spec does not name.
- **P2 — pane order for an elevated actor is my-week → readiness → deadline → templates**, with §1.1 inverting it exactly once, on a boutique with no templates at all.
- **P3 — one Card with seven weekday `<section>`s**, not seven Cards (§5).
- **P4 — the deadline is its own Card**, not a `Modal` and not a block under «משמרות הבוטיק» (§4).
- **P5 — one selected treatment for all three states; no per-state colour** (§2.4).
- **P6 — the locked week renders a `<dl>` of her answers**, not disabled radios (§2.8).
- **P7 — week navigation is words, not chevrons** (DL20; §2.3).
- **P8 — `submitted` means "at least one live row", with a partial count beside it** (§3).
- **P9 — the group is four radios, «לא נרשם» default-checked, 2×2 at 375** (§2.2 / §2.4 / F-15). It stores no fourth state — it is the rendered name of "no entry" and maps to D8's omit-from-`PUT` clear path. It is what makes a mis-tap withdrawable, and it is the reason the mobile layout is two rows rather than one.
- **P10 — five copy rows redrafted for Hebrew number agreement, four for `<bdi>` isolation** (§9.0, marked ✎ in the deck). Three of the nine were ✓ spec rows; the meaning of every one is unchanged and only the shape moved.
- **P11 — two new error keys, `shifts.errors.notAuthorized` and `shifts.errors.notFound`** (§9.6), because the "house copy" §2.7 pointed at does not exist and the nearest shipped strings assert owner-only, which D5 contradicts.

---

## 13. What this surface deliberately does not have

No roster, assignment, coverage target or publish — that is F40 · no reopen mechanism for a locked week (C3: an elevated actor is simply not subject to the deadline, and no per-week state exists to drift) · no `pending` state **stored** anywhere — `AvailabilityState` keeps its three members and D8's fourth is still the absence of a row; the fourth radio «לא נרשם» is that absence's *name on screen* and its selection omits the template from the `PUT` (§2.2, P9), which is D8's own clear path and not a state · no copy-forward or "same as last week" (O4) · no standing availability, time-off request, partial-shift or swap · no deadline nudge, SMS or notification of any kind · no polling, no timer, no live counter · **no hours total, no attendance reading, no pay** (§0) · no capacity or headcount field (D3 dropped it deliberately) · no overnight shift (D2's CHECK) · no template versioning or archive list · no new `@boutique/ui` export and no promotion (D13) · no icon-only control (DL20) · no per-state colour semantics · no cap on how many shifts she may mark «מעדיפה» (O2 — F39 stores it and enforces nothing) · no self-service profile or photo editing (F38 O3 stays deferred; C4).

---

Design Gate: OPEN
