# Screen: Seamstress capacity + load bars + balanced assignment (F42 — `SeamstressPanel`, a panel **inside** the shipped «תפירה» section)

**Date**: 2026-08-04 · **Status**: **DESIGN GATE SELF-APPROVED.** Interview **Q2** named exactly two novel interaction patterns for this run — F34's shift board and **F42's capacity matrix** — and `LOOP-STATE.md` `rulings_2026_07_31` self-approves both: *"build through their Q2 novel-pattern gates without pausing."* ⚠ **And the surface this feature actually ships has no matrix** (spec D8, §Conflicts 1): the matrix's second dimension is the F40 roster projection the same ruling **drops**, so with a flat weekly number there is one value per person, which is a list of the shape F41 already ships five of. **What the missing prototype costs is stated rather than hidden**: the four things a human reviewer would have caught here are the horizon date with no source (**F-1**), the bounded list that shows two rows where the spec claims four *and* reintroduces the nested-scroll trap F41 refused (**F-2**), the three-numeral string the shipped bidi helper cannot isolate without a live substring collision (**F-5**), and a dialog footer that cannot hold the button the spec puts in it (**F-6**).
**Designer**: Claude · **Consumes**: `.planning/specs/seamstress-capacity.md` (**D1–D16**, Gate 1 standing approval, 36 of 38 review findings applied) · `.planning/design/system/tokens.md` (**binding**) · `.planning/design/screens/design-system/manage-restyle.md` (**binding**) · `.planning/design/screens/alteration-tickets/design.md` (**F41 — this deck is a panel inside its section and inherits every one of its rulings**) · `.planning/design/screens/shift-board/design.md` Revision 2 (the `usePoll` contract, at one remove) · `packages/ui` and `apps/manage` **as shipped on `main` at `0c71702`** (F41 merged as PR #39, F58 as PR #40)
**Copy**: `copy.md` in this directory — every Hebrew string with its untranslated `ar` value (Interview Q3 / pre-decided #47 / the 2026-07-31 languages ruling).
**Prototype**: **none, deliberately.** A prototype exists to answer *is this interaction legible*. The interaction here is a list of rows each carrying one button, on a polling surface whose beat, pause control, terminal states, focus discipline and error register were all answered at F34's gate and shipped through F57 and F41. The one genuinely new object is the **bar**, and the console already ships it — `DashboardSection.tsx:20-43` (verified: `aria-hidden`, an explicit refusal of `role="progressbar"`, the 0–100 clamp, the `Number.isFinite` guard, `bg-gold-strong` on `bg-border`, `inlineSize`). A still prototype of a bar is a bar.

**What this deck is NOT.** It is not a redesign of `AtelierSection`, `TicketCard` or any of F41's five columns. It touches F41's tree in **three** places and no others: one new child between the cue and the board branches, the assign `<Select>`'s option order and labels, and one conditional clause on the assign cue. It is **not** the capacity matrix (§0), and it is **not** the console-width decision F41's **F-2** handed here on the assumption that it would be (**F-7**).

---

## 0. Scope

The console gains **no section, no nav row and no `SectionKey` member.** `SectionKey` stays **fourteen**, `NAV` stays **thirteen**, `Nav.test.tsx`'s `.slice(0, 11)` stands, and `App.tsx` is not opened. The panel is **content of the atelier section**, exactly as F58's rooms are content of the floor — `i18n.test.ts:63-66` records the general rule.

| Surface | Who sees it | Shape |
|---|---|---|
| The seamstress panel | owner, shift_manager, **seamstress** (read-only) | `<SeamstressPanel>` — a named `<section>` inside `AtelierSection`, above the board |
| The «שעות» control, one per row | **owner, shift_manager only** | `Button ghost md` → panel-level `Modal` |
| The «הגדרות» control, one per panel | **owner, shift_manager only** | `Button ghost md` → panel-level `Modal` |
| The assign `<Select>`'s option order and labels | **owner, shift_manager only** — it is already inside F41's `{elevated && (` block (`AtelierSection.tsx:1503`) | reordered and relabelled, **no structural change** |
| The assign cue's overload clause | everyone who can assign or claim | one conditional clause on a shipped `role="status"` region |

**⚠ THE EPIC'S "CAPACITY MATRIX" IS F40's SHAPE AND IT IS NOT WHAT THIS DECK DESIGNS.** A matrix is seamstress × *time*, and time is the published-roster projection the 2026-07-31 ruling drops. Spec D8 makes the consequence structural rather than cosmetic: **there is no `role="grid"`, no roving `tabindex` and no arrow-key manager anywhere in this feature.** The e9 Risks' *"the grid is keyboard-navigable"* requirement is therefore discharged **by construction** — a `<ul>` whose every row is text plus one ordinary `Button` is keyboard-navigable in the same sense a paragraph is — which is the identical move F41's D16 made when it refused drag-and-drop. §8 is the concrete pass; it names no new mechanism because there is none.

**Zero new `packages/ui` components and zero new variants.** Everything is `Card`, `Button`, `Input`, `Select`, `Modal`, plus the ten-line `Bar` copied from `DashboardSection` (§2.1). **Nothing is promoted to `packages/ui`** — the dashboard spec's D10 declined promotion at one caller, this is the second, and *promotion is the recorded upgrade at a third*.

**One new colour pair enters the ledger and it is the compliant one.** `bg-gold-strong` on `bg-border` already ships in `DashboardSection`'s `Bar` and is inherited unchanged. `bg-danger` on `bg-border` is new: **`#A03232` on `#E4DACA` = 5.07:1** (computed, not eyeballed). §9 carries both numbers and §10.3 argues which SC binds.

### Binding inheritances (obeyed, not restated)

From **`manage-restyle.md`**: the **720 px content cap at every breakpoint**; the three-register split (an **outage** is `text-ink-muted`, a thing-she-must-fix is `text-danger`, a nothing-failed **notice** is `text-warning-text`); `EmptyState` over a blank region; inline muted cues over Toasts; destructive action = `danger` trigger → `Modal` with a `ghost` dismiss and a `danger` confirm; **never override a `packages/ui` component's own utility from the call site** — `cn()` is a plain join and the consumer loses, which is what makes **F-6** a finding rather than a preference.
From **`tokens.md`**: the gold law (`--color-gold-strong` never carries **text or a meaning-bearing glyph**; a bar fill is neither); focus ring on every control; ≥44×44 targets; no raw px in app code.
From **F41's `design.md`**: the freshness row is the whole live-ness contract and is **never announced and never `aria-hidden`**; **the poll may never write into a live region** (its §4.2, four paragraphs of defence — F42 does not crack it, §5.3); a live region is written **only when its value actually changes**; the pause control is the **first stop inside the section** (SC 2.2.2, legal); `{401, 403}` are terminal and a mutation's 403 is terminal too; **status is carried by the WORD and never by the colour**; `<bdi dir="ltr">` on numeric runs and a **bare `<bdi>`** on Hebrew free text; **`size="sm"` is barred on this surface**; nothing on this board mutates on `change`; **at 375 nothing is height-bounded, because nested scroll containers on touch are a scroll-trap** (its §6 — the rule **F-2** restores).

### Explicitly NOT here — with the spec's reasons

| Not shipped | Reason |
|---|---|
| **Any block, refusal, confirm-on-overload, disabled option or auto-balance suggestion** | Pre-decided #40, spec D11. **Overload FLAGS, never blocks.** There is no 409, no advisory field on any mutation response and no new error code — `SPEC_ERROR_CODES`' set-equality is the proof, not a promise |
| **A capacity matrix, per-day bars, a roster, a horizon walked back from a due date** | F40's, an E8 feature, dropped from this run's deps by ruling. Spec D2 records exactly what F40 replaces: **the denominator, and nothing else** |
| **A second poll loop or a capacity-only endpoint** | F41's D12: *"F42/F43 extend this payload; nobody adds a third loop."* The four new envelope fields are the mechanism |
| **A nav row, a `SectionKey`, an `App.tsx` edit** | §0. The panel is content |
| **Split load, expedite** | Two columns and two `AuditAction` members F41's Out-of-scope already sizes |
| **A per-seamstress ticket list, a drill-down, a sparkline, a trend** | §11 **P-4**. Her tickets are three inches below her row, in the columns |
| **An aggregate «הבוטיק בעומס» banner** | §11 **P-3**. A second, louder signal saying what four rows already say is how a board stops being read |
| **A toast** | Spec D11. The console has a `ToastProvider` and this feature uses it for nothing: the bar is the durable signal, the cue is the announced one |
| **A `<details>` / disclosure / collapse on the panel** | Spec D8. The panel *is* the feature; and `<details open={x}>` is **controlled** in React, so an `open` derived from "is anyone overloaded" would reopen under the user's hand on every five-second tick — F41's post-mortem focus-steal class, in a new costume |
| **Any edit to `restoreRef` / `captureFocus` / `boardCommit`** | Spec D14. **Any edit to that block is a review stop.** §6.3 is why this feature needs none of it |

---

## 1. The panel — anatomy at 375, and exactly where it sits

⚠ **THE DIAGRAMS BELOW ARE DRAWN LEFT-TO-RIGHT, FOR LEGIBILITY IN A MARKDOWN FILE. THE RENDERED CONSOLE IS RTL** — `frontend/apps/manage/index.html:2` is `<html lang="he" dir="rtl">`, verified. So in the shipped product every run inverts: **inline-start is the physical RIGHT and inline-end is the physical LEFT.** The seamstress's name sits at the physical right of her row; the «שעות» button sits at the physical left; **the bar fills from the RIGHT** (§2.6, which is the one place this matters enough to have its own section). This deck ships **no prototype and no `design-critic` pass**, so the ASCII is the sole visual source — a builder implementing the drawn order ships a mirrored panel that passes axe, passes every named vitest assertion, and reads backwards to the only users who will ever see it.

```
+--------------------------------------------------+
|  <main #console-main tabIndex=-1, max-w-720px>    |
|                                                   |
|  לוח התפירה                                        |  h2 — F41's, untouched
|                        עודכן 14:07  [ השהיה ]      |  FRESHNESS ROW — F41's, untouched.
|                                                   |    Pause stays the FIRST stop (SC 2.2.2)
|  <p role="status"> (empty at rest)                 |  F41's ONE announced region
|                                                   |
|  ┌ THE PANEL — new ────────────────────────────┐  |
|  │ תופרות · 3                                   │  |  h3 id=atelier-h-capacity tabIndex={-1}
|  │ ┌ Card (surface-raised, p-6) ─────────────┐  │  |  ONE Card, divide-y rows (§11 P-1)
|  │ │ <ul tabIndex={0} aria-label="תופרות">    │  │  |  NAMED, UNCOUNTED name (§10.1)
|  │ │  ┌ li ────────────────────────────────┐ │  │  |
|  │ │  │ דנה                      [ שעות ]  │ │  │  |  name: bare <bdi>; Button ghost md
|  │ │  │ ████████░░░░░░░░░░░░░░░░░░░░░░░░░  │ │  │  |  THE BAR — aria-hidden, h-2 (§2)
|  │ │  │ 6 שעות עד 11.8 מתוך 12 · סה״כ 12   │ │  │  |  THE PAYLOAD — one <p>, text-sm
|  │ │  │ שעות בתור · ברירת מחדל של הבוטיק    │ │  │  |
|  │ │  └────────────────────────────────────┘ │  │  |
|  │ │  ┌ li ────────────────────────────────┐ │  │  |
|  │ │  │ רותי                     [ שעות ]  │ │  │  |
|  │ │  │ (no bar at all — no denominator)   │ │  │  |  ⚠ NOT an empty bar (§2.3)
|  │ │  │ 4 שעות · לא הוגדרה קיבולת           │ │  │  |
|  │ │  └────────────────────────────────────┘ │  │  |
|  │ │  ┌ li ────────────────────────────────┐ │  │  |
|  │ │  │ נועה                     [ שעות ]  │ │  │  |
|  │ │  │ ████████████████████████████████  │ │  │  |  CLAMPED at 100 %, bg-danger
|  │ │  │ 15 שעות עד 11.8 מתוך 12 · עומס     │ │  │  |  ⚠ THE WORD, not the colour
|  │ │  │ יתר · סה״כ 46 שעות בתור             │ │  │  |
|  │ │  └────────────────────────────────────┘ │  │  |
|  │ │ </ul>                                    │  │  |
|  │ │ לא משויך · 4 שעות                        │  │  |  <p> OUTSIDE the <ul> (§10.1)
|  │ │ [ הגדרות ]                               │  │  |  panel-level, LAST tab stop (§11 P-5)
|  │ └──────────────────────────────────────────┘  |
|  └───────────────────────────────────────────────┘  |
|                                                   |
|  [ כרטיס חדש ]  ← F41's CTA, rail, five columns…   |
+--------------------------------------------------+
```

**Note the row order: דנה, רותי, נועה.** That is `sortByRemainingCapacity`'s three groups rendering — real headroom, then unknown, then overloaded (§4). Alphabetically it would be דנה, נועה, רותי; the panel is not alphabetical and §4 is why.

### 1.1 The insertion point, exactly — one conditional, between the cue and both board branches

The spec (D8) says *"below the freshness row and above whichever of the stage rail or F41's `EmptyState` renders."* Read against the shipped file that resolves to **one** insertion point, and naming it is worth three lines because the two obvious alternatives each break something:

```jsx
{/* AtelierSection.tsx — the cue <p role="status"> ends at :481 */}

{boardData !== null && (
  <SeamstressPanel
    seamstresses={boardData.seamstresses}
    unassignedMinutes={boardData.unassigned_minutes}
    defaultCapacityHours={boardData.default_weekly_capacity_hours}
    dueSoonThrough={boardData.due_soon_through}   {/* F-1 */}
    bands={boardData.effort_bands}
    role={role}
    onSaveCapacity={…} onSaveAtelierSettings={…} onDialogOpenChange={setPanelDialogOpen}
  />
)}

{boardData !== null && boardData.tickets.length === 0 && ( <EmptyState … /> )}   {/* :960 */}
{boardData !== null && boardData.tickets.length > 0  && ( <>…truncated, CTA, rail, columns…</> )}
```

- **Not inside either branch.** The panel renders in **both** — spec §Every state pins the zero-ticket case explicitly, and that is the branch a brand-new boutique is in, i.e. *both* of D2's "first thing a new boutique sees" states. One insertion point is one thing to keep true; two copies is a place to forget one.
- **Not above the cue.** The cue is `role="status"` and is F41's only announced region; pushing it below a list that can be four rows tall separates it from the freshness row it complements, for no gain — the cue is `tabIndex={-1}`, so the tab order is identical either way.
- **Above `boardData.truncated`'s notice**, therefore. Correct: the truncation notice is a fact about the **board**, and it stays adjacent to the rail and columns it describes. The panel is exact regardless (spec: the aggregate is uncapped, so `truncated: true` and correct bars coexist), so nothing about the notice qualifies it.
- **The pause control is still the first stop inside the section.** F41's D17 / SC 2.2.2 rule is non-negotiable and the panel sits below the whole freshness row. Asserted in §8's tab order, not assumed.

### 1.2 The row — three elements, and the sentence is the third

| Slot | Content | Bidi | Notes |
|---|---|---|---|
| Name + control | `display_name` at inline-start, the «שעות» `Button` at inline-end | **bare `<bdi>`** on the name | `flex flex-wrap items-center justify-between gap-2`. `font-semibold text-ink break-words`. **`flex-wrap`**: a long name pushes the button to the next line rather than squeezing it — F41's name/`Badge` rule, at a different pair. The `Button` is absent entirely for a non-elevated viewer and for an `assignable: false` row (§6) |
| The bar | §2 | — | `aria-hidden="true"`, `mt-2`. **Absent — not empty — when the resolved capacity is `null`** |
| The sentence | up to four clauses, one `<p>` | **none, and §10.4 is why** | `mt-1 text-sm text-ink-muted`. **This is the entire accessibility payload of the bar.** Never truncated, never clamped, never abbreviated |

**The sentence's clause order is fixed and the overload word is second, not last.**

```
{load}  [· «עומס יתר»]  [· {backlog}]  [· «ברירת מחדל של הבוטיק»]
```

«6 שעות עד 11.8 מתוך 12 · סה״כ 12 שעות בתור · ברירת מחדל של הבוטיק»
«15 שעות עד 11.8 מתוך 12 · **עומס יתר** · סה״כ 46 שעות בתור»
«4 שעות · לא הוגדרה קיבולת»

The alarm comes as early as the grammar allows, because a screen-reader user hears the clauses in order and a manager scanning three rows reads the first half of each. The `capacity_is_default` clause is last because it is the least urgent fact in the row — it qualifies whose number the denominator is, not whether there is a problem.

**⚠ THE OVERLOAD WORD IS A `<strong>` INSIDE THAT ONE `<p>`, NEVER A SECOND `Badge`.** F41's §2.4 fixes *exactly one `Badge` per card and overdue owns it*, and this panel sits three inches above sixty of those cards. A `Badge` here would also split the payload into two announced chunks, where the whole point of D9 is that the row reads as one continuous sentence. `<strong className="font-semibold text-danger">` — `--color-danger` is **6.18:1 on paper** (tokens ledger), so the word passes AA as text on its own, and `font-semibold` is the non-colour half. The word is the signal; both the weight and the colour are reinforcement. §11 **P-2**.

**The whole row is one `Card` around a `divide-y` list, and the heading is outside it.** §11 **P-1** — F57's shipped panel shape, deliberately the **inverse** of F41's per-ticket `Card`, and the reason is one sentence: **a seamstress row moves nowhere.** F41 made the ticket the `Card` because *"the unit of this screen is a thing that moves between named regions"*; a roster row is a static line about a person, and three stacked `Card`s above five columns of `Card`s is `shadow-sm` on `shadow-sm` for a list that never reorders under a repaint except by the sort it is supposed to have.

---

## 2. ⚠ THE LOAD BAR

### 2.1 Anatomy — the shipped widget, copied verbatim

```jsx
// SeamstressPanel.tsx — DashboardSection.tsx:20-43's shape, not an import.
function Bar({ pct, over }: { pct: number; over: boolean }) {
  const size = Number.isFinite(pct) ? Math.min(Math.max(pct, 0), 100) : 0;
  return (
    <span aria-hidden="true" className="mt-2 block h-2 rounded-sm bg-border">
      <span
        className={cn("block h-2 rounded-sm", over ? "bg-danger" : "bg-gold-strong")}
        style={{ inlineSize: `${size}%` }}
      />
    </span>
  );
}
```

Four things in ten lines, each of which is a decision the dashboard already made and this deck refuses to re-make:

| Element | Why it is exactly this |
|---|---|
| `aria-hidden="true"` on the **track**, so the fill goes with it | §2.5. The whole widget is pruned from the accessibility tree, because the sentence beside it says everything it shows, more precisely |
| `Math.min(Math.max(pct, 0), 100)` | The clamp. A naive `inlineSize: ${ratio * 100}%` at 400 % paints four times outside its track. **400 % is not hypothetical — it is one seamstress and a wedding season** |
| `Number.isFinite(pct) ? … : 0` | `pct` is `due_soon / (hours × 60) × 100`, and `hours === 0` makes that `Infinity` or `NaN`. **`inlineSize: NaN%` is an IGNORED declaration** that silently leaves the previous width in place on a re-render — so on a five-second poll a bar could keep a stale width for a whole shift with nothing on screen wrong. The guard lives in the component, at one site, not at the call sites |
| `bg-gold-strong` / `bg-danger` on `bg-border` | ⚠ **`bg-accent` DOES NOT EXIST.** `theme.css`'s `@theme` block declares bg, surface, surface-raised, ink, ink-muted, gold, gold-strong, gold-text, border, border-input, success, danger, warning-text, focus — **and nothing else** (verified, `:21-35`), and `grep -rn bg-accent frontend/` returns zero hits. Tailwind 4 emits no utility for an undeclared token, so an `accent` fill would leave this feature's headline widget **invisible in its normal state and visible only when it is red** |
| `inlineSize`, never `width` | Kept verbatim as the one spelling of one widget. §2.6 states what it actually buys, honestly |

**`over` is the only argument added to the shipped signature**, and it is `overloaded(row)` — the same predicate, from `lib/capacity.ts`, that sets the word. **One predicate, one place, three consumers** (the colour, the word, the assign cue). That is what makes *"overload is never colour-only"* a **structural** property rather than a rule somebody has to remember: you cannot ship the colour without the word, because they read the same boolean.

### 2.2 What the number means — the bar has ONE numerator and the row states TWO numbers

This is the decision a reader will challenge first, and the spec (D3, §Conflicts 13) makes it explicitly against LOOP-STATE's literal wording, so it is restated here in the visual terms this deck owns.

```
denominator :  weekly_capacity_hours × 60      a RATE  — minutes per WEEK
numerator   :  due_soon_minutes                a FLOW  — minutes due in the NEXT 7 DAYS
                                                         (rolling, from today_jerusalem)
also on screen, in words, never in the bar:
              assigned_minutes                 a STOCK — her whole undelivered backlog
```

**Dividing the stock by the rate is not a utilisation of anything.** A 40 h/week seamstress holding six weeks of evenly-spread forward work renders at **600 %, clamped, red — on day one, on every row, in any boutique with a book.** A bar that is red in the steady state is a bar nobody reads, which is precisely the failure this feature exists to prevent. So the bar divides a week's work by a week's capacity, and the backlog rides in the same sentence, in words, so nothing is hidden.

**Both numbers are on screen in every configured row and they are labelled differently on purpose:**

- «6 שעות **עד 11.8** מתוך 12» — the horizoned figure, and the date is what makes it readable as a horizon rather than a mystery.
- «סה״כ 46 שעות **בתור**» — the queue, unbounded, LOOP-STATE's number verbatim.

⚠ **THE DATE IN THAT SENTENCE HAS NO SOURCE ON THE WIRE OR IN `lib/`, AND THAT IS F-1.** `lib/jerusalem.ts` ships `todayJerusalem()`, `plainDate()`, `plainDayMonth()`, `jerusalemDate/Time/IsoDate()` — **and no date arithmetic of any kind** (verified, whole file). `plainDate`'s own comment forbids the obvious workaround in as many words: *"`new Date("2026-05-03")` parses as UTC midnight, and running that through a zoned formatter re-zones a date that was never in a zone … the exact class of bug this file exists to prevent."* And even a correct client computation would be the **wrong** date: the server filtered on **its** `today_jerusalem + 7`, and a device whose clock has crossed midnight while the payload was held would print a horizon the SQL did not use. The remedy is one field, zero statements and zero new date sources — the server already holds the value. §12 **F-1**.

### 2.3 The five renderings — 0 %, 60 %, 100 %, 140 %, 400 %, and the sixth that is not a percentage

All five against a **12 h capacity** (720 min), drawn LTR (§1 — they fill from the **right** in the shipped console).

| Case | `due_soon` | `pct` | The bar | The sentence |
|---|---|---|---|---|
| **0 %** | 0 min | 0 | `░░░░░░░░░░░░░░░░` — the **track renders, empty** | «0 שעות עד 11.8 מתוך 12» |
| **60 %** | 432 min | 60 | `█████████░░░░░░░` gold | «7.2 שעות עד 11.8 מתוך 12» |
| **100 %** | 720 min | 100 | `████████████████` **gold, full** | «12 שעות עד 11.8 מתוך 12» — **no word** |
| **140 %** | 1 008 min | **100, clamped** | `████████████████` **red, full** | «16.8 שעות עד 11.8 מתוך 12 · **עומס יתר**» |
| **400 %** | 2 880 min | **100, clamped** | `████████████████` **red, full** | «48 שעות עד 11.8 מתוך 12 · **עומס יתר**» |
| **capacity `null`** | any | — | **NO BAR AT ALL — not an empty track** | «4 שעות · לא הוגדרה קיבולת» |
| **capacity `0`, load `0`** | 0 | 0 | empty track | «0 שעות עד 11.8 מתוך 0» — **not** overloaded |
| **capacity `0`, load > 0** | 360 min | **100** | red, full | «6 שעות עד 11.8 מתוך 0 · **עומס יתר**» — the ratio is undefined, the fact is not |

**Three things a reader has to be told, because the table alone implies the opposite of each:**

1. **⚠ 140 % AND 400 % DRAW THE SAME BAR, BYTE FOR BYTE.** The clamp means the bar cannot distinguish "twenty minutes over" from "a month behind" — past 100 % only the colour and the **numbers in the sentence** move. That is designed: **the bar's width answers *how full*, the bar's colour answers *over or not*, and the text answers *by how much*.** Stated so nobody adds a stripe, an overflow nub, a «×4» chip or a second bar to "show the excess" — every one of those is a new visual vocabulary for a fact the sentence already carries precisely, on a widget that is `aria-hidden` and therefore invisible to half the users it would be built for. §12 **F-10**.
2. **⚠ AT EXACTLY 100 % THE BAR IS FULL AND GOLD, AND THAT IS RIGHT.** `overloaded` is `due_soon_minutes > capacity × 60`, strictly. Full-and-calm is the honest rendering of a seamstress with exactly a week of work in a week. The colour flips one minute later with **no width change at all**, which is the one transition on this widget where the two channels move independently.
3. **⚠ `null` CAPACITY DRAWS NOTHING; `0` CAPACITY DRAWS A TRACK.** They are opposite states and the difference must be visible without reading: an empty track says *"she has room and holds nothing"*; no track says *"nobody has told this product how much she can take."* Spec D2's `is not None` rule is the server half and `weekly_capacity_hours === null` is the client half, and `if (!row.weekly_capacity_hours) return null` collapses them — rendering the away-and-drowning seamstress (capacity 0, six hours due) as «לא הוגדרה קיבולת» with no bar and no alarm. Both directions carry named mutations in the spec's Testing table.

**Hours are rendered `Math.ceil(minutes / 6) / 10`, and the rounding direction is load-bearing.** `overloaded` compares **raw minutes**, so with `Math.round` a 721-minute load against a 12 h capacity renders «12 שעות … מתוך 12 · עומס יתר» — **displayed numbers saying equal beside a word saying over**, in the one string that is this feature's entire accessibility payload. With `ceil`: 721 → «12.1 … מתוך 12 · עומס יתר», 719 → «12 … מתוך 12» with no word. It never fires with the five platform bands, all multiples of 30 — and D5 makes bands tunable to any integer in 1..1440 and *"NOT required to be distinct or increasing"*, so a 37-minute band produces loads at arbitrary offsets.

### 2.4 ⚠ How overload reads with the colour removed entirely

The e9 Risks name colour-only urgency as this epic's hard accessibility case, and pre-decided #38 makes IS 5568 / WCAG 2.0 AA **legally** binding on these screens. So the test is not *"is the red distinguishable"* — it is **what survives the colour being gone.**

Render the panel in greyscale, or in a browser with forced colours, or read it with a screen reader, and **nothing is lost**:

| Channel | 60 % row | 140 % row | What survives greyscale |
|---|---|---|---|
| Bar width | 60 % | 100 % | ✓ — a full bar is visibly different from a partial one |
| Bar colour | gold | red | ✗ — and it is the only channel that does not survive |
| **The word** | absent | **«עומס יתר»** | ✓ — a word is a word |
| **The weight** | — | `font-semibold` | ✓ |
| **The numbers** | «7.2 … מתוך 12» | «16.8 … מתוך 12» | ✓ — and these are the only channel that survives *and* carries magnitude |

**The bar is the only thing that carries colour, and it is `aria-hidden` decoration on top of text that is complete on its own.** That is the same shape F41's D17 mandates for overdue — *"Overdue is a `Badge` carrying «באיחור» plus the date, never a red border alone"* — applied to the one widget in this feature whose entire job is a colour.

**And the structural guarantee is the single predicate.** `lib/capacity.ts::overloaded(row)` is the only comparison in the feature; the colour reads it, the word reads it, and the cue reaches it only through `wouldOverload(row, extraMinutes)`. **A build in which the bar is red and the word is missing does not exist**, because there is no second boolean to drift. The spec pins it with `wouldOverload(row, 0) === overloaded(row)` across the whole edge table — one assertion that reds on any drift between the two, including the `null * 60 = 0` case that would otherwise announce «עומס יתר» on every assign to an unconfigured seamstress while leaving the sighted surface correct and axe green.

### 2.5 The bar's accessible role, name and announced value — **NONE, NONE and NONE**

**⚠ A BARE COLOURED DIV IS A FAIL AND SO IS A `role="progressbar"` BOLTED ONTO ONE. Both are refused, and this is the decision.**

| Question | Answer |
|---|---|
| Accessible **role** | **none.** `aria-hidden="true"` prunes the whole widget from the accessibility tree |
| Accessible **name** | **none**, and it may not acquire one — an `aria-label` on an `aria-hidden` element is dead code that a later reader will "fix" by removing the `aria-hidden` |
| Announced **value** | **none.** No `aria-valuenow`, no `aria-valuemin`, no `aria-valuemax`, no `aria-valuetext` |
| What the user actually hears | **the row's `<p>`** — real text in the DOM, read by everyone, in the same words a sighted user reads |

**What a screen reader announces, arrowing into the list** (the three rows of §1, in sort order):

> «תופרות, רשימה, 3 פריטים · **דנה**, 6 שעות עד 11.8 מתוך 12, סה״כ 12 שעות בתור, ברירת מחדל של הבוטיק, שעות — דנה, לחצן · **רותי**, 4 שעות, לא הוגדרה קיבולת, שעות — רותי, לחצן · **נועה**, 15 שעות עד 11.8 מתוך 12, עומס יתר, סה״כ 46 שעות בתור, שעות — נועה, לחצן»

then, **outside the list**: «לא משויך · 4 שעות» and «הגדרות, לחצן».

**Nothing else. No «progressbar», no «125 percent», no widget to enter or exit, and no announcement at all from the five-second poll.**

**Why not `role="progressbar"`.** ARIA defines it as *"progress of a task that takes a long time"*. Nothing here is progressing toward completion — a capacity meter is a **level**, not a task, and an AT would read it as an in-flight operation. It also announces a bare ratio, so the honest form needs `aria-valuetext` — and that string would be **byte-identical to the visible sentence beside it**, putting one fact in the accessibility tree twice. Hiding the visible sentence to remove the duplication then makes visible and announced content diverge, which is the WCAG 2.5.3 failure `aria-label`-over-visible-text causes.

**Why not `role="meter"`.** Semantically it is the right role — ARIA 1.2's *"graphical display of a numeric value within a defined range"* — and it is **declined for support, not for meaning**: NVDA and JAWS announce it inconsistently, and it would need the same `aria-valuetext` duplication to say anything useful. **Recorded as the role to revisit if this repo's a11y bar ever moves to ARIA 1.2 with measured AT support**, which is a different decision from this one.

**⚠ AND THE ONE ASSERTION THAT CATCHES A WRONGLY-ROLED BAR IS NOT AXE.** axe has no rule that fires on a *correctly formed* `progressbar` in the wrong place; it will pass a bar carrying `role="progressbar" aria-valuenow="125"` without complaint. The spec's acceptance line — *the bar is `aria-hidden`, carries no `role`, no `aria-valuenow` and no accessible name* — is the only thing standing between this deck and that build. It may not be dropped as redundant with the axe pass.

### 2.6 ⚠ RTL — what "fills from the inline-start" means physically, stated accurately

**The bar fills from the physical RIGHT.** The console is `dir="rtl"`, the fill is a block box inside a block track with no margins, so the used box is placed at the **start** edge of its containing block, and in `direction: rtl` the start edge is the right one. A 60 % bar is a gold run occupying the **right** 60 % of the track, growing **leftwards** as load rises. **A builder who draws §2.3's diagrams literally ships a bar that empties from the right and fills from the left — it will pass axe, pass every named assertion, and read backwards.**

**And the honest note about `inlineSize`, because the shipped comment overstates it.** `DashboardSection`'s `Bar` says *"inlineSize, NEVER width — a logical property, so in RTL the fill grows from the inline-start (right) edge."* In a horizontal writing mode `inline-size` **computes to `width`**, and a `width`-sized block child already resolves its position against `direction` — so under `dir="rtl"` the two behave identically today. **The RTL fill direction is `dir="rtl"`'s doing, not the logical property's.** `inlineSize` is nonetheless kept verbatim: one widget, one spelling, and it is the form that stays correct if a writing mode ever changes. Recorded so that nobody "proves" the comment wrong in review and replaces the property, and so that nobody believes swapping to `width` is the *cause* of a mirrored bar when they meet one.

---

## 3. The capacity editor — one field, one dialog, one write

**Trigger**: the row's «שעות» `Button ghost md`, elevated only, with a per-row accessible name «שעות — {{name}}» (WCAG 4.1.2: a six-row panel otherwise exposes six buttons all named «שעות»).
**Mount point**: **panel level** — a sibling of the `<ul>` inside `SeamstressPanel`, **never inside an `<li>`.** F41's C6 rule forbids the `<li>` and nothing further: a repaint that removes the row would unmount a dialog mounted inside it and discard what she typed. *Any "section level" reading is wrong* — the dialog needs the panel's state and the panel's heading ref.
**Panel width**: `min(28rem, 100vw − 2rem)` = **448 px max, 343 px at 375**, minus `p-6` × 2 → **295 px of dialog content**, the same measurement as an atelier card.

```
+------------------------------------------+
|  שעות שבועיות                             |  Modal title — font-display text-xl
|                                          |
|  שעות בשבוע                               |  Input label — text-sm font-semibold
|  ריק — חזרה לברירת המחדל של הבוטיק (30).   |  help — text-xs ink-muted (§3.2)
|  [  24                              ]     |  Input type=number inputMode=numeric min=0
|                                          |    ⚠ NO max — 168 is a SERVER bound
|  [ חזרה לברירת המחדל ]                     |  Button ghost md — CLEARS THE FIELD (§3.1)
|                                          |
|                    [ ביטול ]  [ שמירה ]   |  Modal footer — ghost + primary, TWO buttons
+------------------------------------------+
```

**Prefill, and the anti-conversion guard.** The field opens carrying `weekly_capacity_hours` when `capacity_is_default` is **false**, and **empty** when it is **true** — so saving without typing cannot silently convert an inherited number into an owned one. That asymmetry with the settings dialog (§4, which deliberately *does* freeze the platform bands on a blank save) is D2's argument: a *capacity* default is a number about one person that nobody chose, while the bands are a mapping the product ships and stands behind.

### 3.1 ⚠ «חזרה לברירת המחדל» is in the BODY and it CLEARS THE FIELD — it does not submit

The spec puts it in the footer as *"a ghost `Button` that submits `null`"*. **It does not fit and it cannot be made to fit** (§12 **F-6**): `Modal.tsx:56` is `<div className="mt-6 flex justify-end gap-3">` — **hard-coded, no `flex-wrap`, and no `className` seam for a caller to add one.** Three buttons, one of them five Hebrew words, in a 295 px footer at 375, overflow the panel; and editing `Modal` from the call site is barred by `manage-restyle.md` and impossible here anyway.

So the control moves into the body, **below** its field, and its act changes from *submit* to *clear*:

- **One submit path, one confirm, one loading state, one error path.** A second submit would need its own `loading`, its own refusal handling and its own focus destination, for a value the save button can already carry.
- **Empty ⇒ `null` ⇒ "use the boutique default", in both directions and with no mode.** She opens an inherited row (field empty) and saves → `null`, a no-op, 200, no audit row. She opens her own row (field 24), clears it and saves → `null`, cleared back to the default. **The field's emptiness means one thing on this dialog, always**, which is what makes the help line a complete explanation rather than half of one.
- **Rendered whenever the tenant has a default**, i.e. `defaultCapacityHours !== null`, and **not** conditioned on the field being non-empty. A control that appears and disappears as she types is a control that moves under her finger (F34's **F-8**); an already-empty field simply makes it a harmless no-op tap.
- **`Button ghost md`**, 44 px, in the flow of the body, so it is a tab stop between the field and the footer (§8).

### 3.2 The help line is TWO strings, because one of them would be a lie on every new boutique

| Condition | Help line |
|---|---|
| `default_weekly_capacity_hours !== null` | «ריק — חזרה לברירת המחדל של הבוטיק ({{hours}}).» — and the number is the tenant's, so she can see what she is falling back **to** |
| `default_weekly_capacity_hours === null` | «ריק — לא תוגדר קיבולת.» |

D2's whole argument is that "no tenant default" is a **real and common** state — it is what every boutique is in on day one, before anyone opens the settings dialog. A help line promising a fallback that does not exist would be the console describing a state it is currently in as a state it is not. Two rows in a table; §12 **F-6** records why the single-string version was rejected.

### 3.3 Validation — shape on the client, range on the server, Hebrew on both

| What | Where refused | What she sees |
|---|---|---|
| Not an integer, or negative | **client**, before the request | «צריך מספר שעות שלם ולא שלילי.» on the field's own `error` prop — `Input` wires `aria-describedby` + `role="alert"` and flips the border to `border-danger` |
| Over 168, or `true` / `"24"` / `24.0` reaching the wire | **server** — `StrictInt` + `Field(ge=0, le=168)` → 400 `VALIDATION_ERROR` | the field-local message if the console can map it; otherwise the dialog alert, §3.4 |
| The target is not a live seamstress (unknown id, retired, foreign tenant, a receptionist) | **server** — one indistinguishable **400** for all four | the dialog alert |

**⚠ NO STRING IN THIS FEATURE MAY CONTAIN «168» OR «1440».** They are **server** bounds, and a Hebrew sentence quoting one is a mirror exactly as much as a TypeScript constant is, with none of the protection — `test_frontend_constant_parity.py` scrapes only the two `validation.ts` files, so raising the DB CHECK to 200 would leave the sentences lying, silently and greenly. **The precedent is not ambiguous**: F41 declared `atelier.form.error.dueDateHorizon` and **cut it at review** for this exact rule (`i18n.test.ts:705-719`: *"730 is a SERVER bound and no client constant may mirror one"*). The copy states the **shape**; the server's 400 states the range. Same for the `Input`: `min={0}` and `inputMode="numeric"` stay (shape), **`max={168}` is cut** (a bound).

**No `dir` on the number field, and the reason is stated so nobody copies the phone field.** F41's `customer_phone` carries `dir="ltr"` because a phone number contains `+`, `-` and spaces — **neutrals**, which reorder at an RTL boundary. A bare integer 0–168 is one uninterrupted EN run inside an RTL field and resolves correctly with no treatment. Adding `dir="ltr"` would left-align a number in a right-aligned form for no gain.

### 3.4 The dialog's states

| State | What renders |
|---|---|
| **Open** | Prefilled per §3, focus is the native `<dialog>`'s own — **no focus code is written for opening**, F41's intake dialog relies on the same and writes none |
| **Submitting** | The confirm `Button` carries `loading` (which also disables it); **the fields stay enabled**, so a slow network does not eat a correction |
| **Per-field validation error** | On the field's own `error` prop (§3.3) |
| **A server error mapping to no field** | **One alert inside the dialog, above the footer**, `role="alert" tabIndex={-1}`, focused, `text-danger` — never a toast behind a modal, and never `error.message`'s English. ⚠ **The `default:` branch is structural**: `main.py`'s error bodies are English and this console is Hebrew-only, and the concrete message this route can produce is `_require_seamstress`'s literal `"staff_user_id must be a live seamstress"`. F41 records the rule in code at `AtelierSection.tsx:493-497`. **The dialog stays OPEN** — the callback resolved `false` |
| **Success** | The `Modal` closes; native `<dialog>` returns focus to the trigger **by itself**; the cue is announced by `AtelierSection` (§5.3); and the panel repaints from the write's response patched onto the held row — ⚠ **only `weekly_capacity_hours`, `capacity_is_default` and `assignable`.** `assigned_minutes` and `due_soon_minutes` are **left untouched at their last-tick values**, so a capacity save never collapses her bar or drops her «עומס יתר» word for five seconds at the exact moment a manager is looking at it. §6.3 is the focus half |

---

## 4. The effort-band + tenant-default editor — one dialog, one save, both keys, always

**Trigger**: the panel-level «הגדרות» `Button ghost md`, elevated only, accessible name «הגדרות — לוח התפירה» (there are two other «הגדרות»-shaped controls in this console; the suffix is F41's `pauseAria` shape).
**Mount point**: panel level, sibling of the capacity dialog.
**Route**: the shipped `PUT /manage/settings`, whose gate already admits **exactly** owner and shift_manager — which is why spec D5 rides it rather than building a second writer on one JSONB key.

```
+------------------------------------------+
|  הגדרות התפירה                             |
|                                          |
|  הערכות זמן                                |  a plain <p> label, text-sm font-semibold
|  שינוי ההערכות משפיע רק על כרטיסים חדשים.   |  ⚠ D4's consequence, said out loud (§4.1)
|  חצי שעה — דקות     [  30              ]  |  five Inputs, one per band,
|  שעה — דקות         [  60              ]     each labelled with the band's own word
|  שעתיים — דקות      [ 120              ]
|  חצי יום — דקות     [ 300              ]
|  יום מלא — דקות     [ 540              ]
|                                          |
|  ברירת מחדל: שעות בשבוע                    |
|  חלה על תופרת שלא הוגדרו לה שעות משלה.      |  help
|  [  30                               ]    |
|                                          |
|                    [ ביטול ]  [ שמירה ]   |
+------------------------------------------+
```

**Six number `Input`s, `p-6`, a title and a footer** ≈ **530 px tall**. `<dialog:modal>`'s UA stylesheet supplies `max-height: calc(100% - 6px - 2em)` and `overflow: auto`, so it scrolls natively on a short viewport. **Do not add `max-h-[80vh] overflow-y-auto` to `Modal`** — that is a `packages/ui` edit for a behaviour the platform already provides, and it would change every dialog in both apps.

**Prefilled from the board envelope, with no read of its own.** `effort_bands` and `default_weekly_capacity_hours` are already on the wire every five seconds. The spec's review considered and **rejected** a `GET /manage/settings` on open: it buys five seconds off a staleness window whose real length is however long the dialog stays open, which is minutes.

**⚠ EVERY SAVE SENDS THE WHOLE `atelier` BLOCK — BOTH KEYS, ALWAYS — AND THAT IS STRUCTURAL, NOT A CONVENTION.** `merge_settings` is one atomic `settings = settings || :patch::jsonb`, and `||` **merges at the top level only**: a patch carrying a *partial* `atelier` object **replaces the whole key and deletes what it did not name**. A "save bands" button and a "save default hours" button would silently delete each other's work. So there is **one dialog, one save button, one request** — §11 **P-7** — and the request model makes it impossible to send half (`AtelierSettingsUpdate` has no default on either field).

**⚠ A SAVE ON A BRAND-NEW BOUTIQUE FREEZES THE FIVE PLATFORM BANDS, AND THAT IS ACCEPTED.** The prefill is the **resolved** bands, which on a tenant with no `atelier` key are the platform defaults — so opening the dialog and pressing save with no edit writes 30/60/120/240/480 into `settings["atelier"]["effort_bands"]`, after which a future change to the platform numbers never reaches that tenant. Intended: the five bands are the product's own numbers and freezing them on first save is a boutique adopting them.

**⚠ TWO SHIFT MANAGERS WITH THIS DIALOG OPEN SILENTLY LOSE EACH OTHER'S WORK.** Full replace, unconditional `UPDATE`, no version, no if-match, both admitted by the shipped gate. Both see «ההגדרות נשמרו.» and nothing on either screen ever differs. **That is the designed behaviour** — a conflict dialog because a colleague opened the same form is the platform second-guessing a call that is hers — and **the recovery path is the audit trail**, which is what makes `ATELIER_SETTINGS_UPDATED`'s full-value, no-`from` payload load-bearing rather than incidental. There is **no UI for this**: no lock, no "last edited by", no banner. Recorded here because a reviewer will look for one.

### 4.1 ⚠ The bands help line — D4's relabel, said out loud

Spec D4 establishes that a re-tune re-values nothing (there is no `effort_band` column; minutes persist) **and** that an old card can therefore **silently relabel**: flattening «יום מלא» from 480 to 240 makes every garment ever estimated at «חצי יום» read «יום מלא» on the board, with no fallback and no visible act. D4 accepts that. **The dialog says nothing about it, and the spec's key table has no string for it** — so an owner correcting one band gets an unexplained relabel across her board and no way to connect the two.

One key closes it: «שינוי ההערכות משפיע רק על כרטיסים חדשים.» — a `text-xs text-ink-muted` line under the section label. It is true (the minutes on existing tickets do not move), it is the reassurance a hesitating owner needs, and it costs one row. §12 **F-11**.

### 4.2 Validation

| Field | Client (shape) | Server (range and type) |
|---|---|---|
| each band | «צריך מספר דקות שלם וחיובי.» | 1..1440, `StrictInt`, exactly the five keys as a **set equality** → 400 |
| the default | «צריך מספר שעות שלם ולא שלילי, או ריק.» | `null` or 0..168, `StrictInt` → 400 |

**Bands are NOT required to be distinct or increasing.** An owner may flatten her two longest bands onto one number; `bandLabel`'s first-match-wins already handles it (`lib/stages.ts:72-81`, verified), and refusing it would be the platform having an opinion about her workshop. §4.1's line is the honesty that makes that safe.

**⚠ `StrictInt` is what makes the `true` case real, and it is invisible from the client.** `ForbidExtraModel` sets `extra="forbid"` and **nothing else** — no `strict=True` anywhere (`app/schemas.py:13-19`). With a plain `int`, `{"half_day": true}` **coerces to `1`**, lands in range, and is a **200 writing a one-minute «חצי יום»** that silently understates every load bar downstream. Nothing on this screen can produce that payload; it is named because the deck's job is to say what the dialog's 400s mean, and this one is the difference between a refusal and a silent corruption of the ruler.

---

## 5. The assignment surface — sorted by remaining capacity, labelled, and never blocked

**Nothing about the assign control's structure changes.** It is F41's `<Select>` + commit `Button` pair inside `{elevated && (` (`AtelierSection.tsx:1503-1541`, verified): the `<Select>` sets draft state, the sibling `Button` issues the request, **nothing mutates on `change`** (WCAG 3.2.2). F42 changes **the order of the `<option>`s and their text**, and adds **one conditional clause to the cue**.

### 5.1 The order — three groups, and the middle one is the whole point

```
1.  capacity resolved AND remaining > 0    — by `remaining` DESC        (real headroom)
2.  NO capacity resolved                   — by `assigned_minutes` ASC  (unknown)   ← F-4
3.  capacity resolved AND remaining <= 0   — by `remaining` DESC        (least over first)
    tiebreak throughout: display_name ASC, then id ASC
```

**Known headroom beats unknown; unknown beats known overload.** Two groups would put every capacity-set row ahead of every capacity-less one — **including a row at 400 %** — so on the state D2 says every boutique starts in (some configured, most not), the **first option in the control**, the one a hurried shift manager takes, would be the person the panel three inches above is drawing in **red**. "Unknown" and "certainly worse than everyone" are not the same rank, and the feature's own title is *balanced* assignment.

**The `<option value="">לא משויך»` release option is rendered first and is not part of the sort** — it is not a person, it is the absence of one, and it is F41's shipped first child.

**Sorted on the CLIENT and applied at exactly two render sites** (this `<Select>` and the panel's `<ul>`) from one call. The held `seamstresses` array keeps the server's `display_name, id` order — a render-time fold, so nothing downstream inherits an order it did not ask for.

**⚠ Accepted risk: the option order now changes as work moves, which F41's alphabetical order never did.** Three shipped things bound it — the deterministic tiebreak means equal rows never shuffle; `holdRef` returns `"held"` while a pointer is down, so a travelling finger never sees a reorder; and `mutationsRef` suppresses ticks while a write is in flight. The remaining window is a keyboard user with the listbox open and no mutation running, needing a *colleague's* write to land inside it. If a pilot reports it, the mitigation is freezing the order for a card that already has a draft.

### 5.2 The labels — the option carries the number, or the sort is an invisible rule

| Row | Option text | Composed from |
|---|---|---|
| capacity set, headroom | «דנה · נותרו 6 שעות» | `optionRow` ∘ `optionRemaining` |
| capacity set, overloaded | «נועה · עומס יתר» | `optionRow` ∘ `over` |
| no capacity | «רותי · 4 שעות משויכות» | `optionRow` ∘ `optionAssigned` |

**⚠ EVERY PART IS A KEY, INCLUDING THE SEPARATOR.** F41 renders `{row.display_name}` alone in this `<option>` and declares no key of this shape, so all three strings would otherwise ship as **bare Hebrew literals in TSX** — outside the `ar` parity guard, outside `HE_F41`'s prefix fold, untranslated, with both `he.ts:1210-1213`'s standing rule and the acceptance line for `atelier.capacity.*` blind to them. `optionRow` is «{{name}} · {{detail}}», so even the « · » is composed from a key.

**⚠ An `<option>` takes no markup**, so `isolateLtr` type-errors and `dir="ltr"` on the `<option>` reverses a Hebrew name. All three strings are **safe by construction** and the check is mechanical: every one **ends in a Hebrew word**, and no numeral is adjacent to Latin text or to a bare parenthesis. «רותי · 4 שעות משויכות» resolves as R · N · EN · R — the neutral separator takes the paragraph direction (UBA N1/N2, where EN counts as R), the digit run is bumped to an even level and renders LTR **in place**, and nothing lands at a paragraph edge that could reorder. A string *ending* in the number — «רותי · 4» — is the shape that breaks, and this deck ships none.

**⚠ A Latin display name is also safe.** «Nina · 4 שעות משויכות» opens with an L run at the paragraph start; in an RTL paragraph that run is placed at the physical **right** and reads LTR internally, which is exactly the intended reading order. Stated because it is the one input a Hebrew-only reader will not have tested.

### 5.3 Overload FLAGS on the write path, and the flag is one clause on a cue

**No write path gains a status, a refusal, a confirm step or a disabled control.** `assign`, `claim`, `release` and `create`-with-an-assignee are byte-identical to F41. An overloaded seamstress is **selectable**, the assign answers **200**, and no dialog appears. §11 lists what was declined.

**⚠ AND THE CUE IS WHY THIS IS NOT A NICETY.** F41's D17 forbids the poll from writing into the announced region, and it is non-negotiable. So a sighted user watches the bar turn red on the next tick and **a screen-reader user gets nothing at all** unless the cue says it — which would make overload a **sighted-only** signal on the one action that causes it, on a screen where a11y is a legal bar. So:

- `atelier.cue.assigned` = «שויך ל{{seamstress}}.» — F41's, unchanged
- `atelier.cue.assignedOverload` = «שויך ל{{seamstress}} — עומס יתר.» — chosen at the moment of the write

**Chosen by `wouldOverload(target, ticket.effort_minutes)` and by nothing else.** No arithmetic and no `60` at that call site: a hand-rolled predicate that drops the null guard computes `null * 60 = 0` in JS and announces «עומס יתר» on **every** assign to an unconfigured seamstress — correct on screen, green under axe, and a legal-accessibility regression on the one channel a screen-reader user has.

**⚠ AND IT IS GATED ON AN ACTUAL MOVE.** The clause is computed **only when `ticket.assigned_staff_user_id !== targetId`**. `due_soon_minutes` is her **pre-write** load and already includes any ticket she currently holds; the shipped commit fires whenever a draft exists and the `<Select>`'s value defaults to the current assignee, so **arrowing away and back and committing sends a no-op assign to the current holder** — the server answers 200 and writes no audit row, and without the gate the console adds minutes it has already counted and announces a false overload **with no colleague and no race**.

**The console is computing a domain fact here, which F41's rule normally forbids, and the boundary is stated**: it is legitimate because it is **not a control** — nothing is refused, nothing is stored, and the next tick replaces the estimate with the server's own numbers. It can be wrong by one ticket if a colleague assigned something in the same second, and the correction arrives within five seconds in the same panel. **A control computed this way would be a defect; a cue is a message about data the console is already rendering.**

**The cue is written by `AtelierSection`, never by the panel.** The capacity dialog's cues (`cue.saved` / `cue.cleared`) are set in the section's `onSaveCapacity` implementation, which looks the name up by id from the `seamstresses` array it already holds. That keeps the shipped `{ text, name }` state shape and `isolateBidi(text, name)` unmodified, and keeps every cue to **at most one interpolated user value** — F41's §4.1 rule, which is what stops a second helper being invented.

---

## 6. States — the single source for this feature

**The list may not shrink.** Every state the spec's §Every state names is here; the ones this deck adds by decomposition are marked ✚.

| # | State | Trigger | What she sees |
|---|---|---|---|
| **C-load** | First load | section opened | **Nothing.** The panel is inside `boardData !== null`. A skeleton for a list of four names is more chrome than content, and F41's `<Skeleton>` card already says the section is loading |
| **C** | Loaded, capacities set | 200 | `<h3>` «תופרות · 3», one row per seamstress in §5.1's order, then — **outside the `<ul>`** — the unassigned line if non-zero, then «הגדרות» |
| **C-zerotickets** | **A brand-new boutique** | 200, `tickets: []` | ⚠ **THE PANEL STILL RENDERS**, above F41's `<EmptyState>`, which in this branch has replaced **both the columns and the rail** (`AtelierSection.tsx:960-971`, verified). Every seamstress at «0 שעות», no unassigned line. **Setting capacity before the first intake is the useful order**, and this is the branch **both** of D2's "first thing a new boutique sees" states land in |
| **C-nocap** | **The second thing a new boutique sees** | 200, no capacity anywhere | Every row renders **with its real load in hours and NO bar**, each carrying «לא הוגדרה קיבולת». «הגדרות» (one boutique-wide default) and each row's «שעות» (one person) are both one tap away. ⚠ **No bar is drawn against an invented denominator** — the load is true data and always renders; only the bar is withheld, because a bar without a denominator is a picture of a number that does not exist |
| **C-empty** | **EMPTY — no seamstresses at all** | 200, `seamstresses: []` | The `<section>`, the `<h3>` «תופרות · 0», and **one muted line where the `<ul>` would be**. ⚠ **Two strings, not one**: an **owner** reads «אין תופרות רשומות. אפשר להוסיף במסך הצוות.» and **everyone else** reads «אין תופרות רשומות.» — the staff screen is owner-only (`App.tsx:145`), and a line telling a shift manager to go somewhere the gate refuses is this console lying about its own permissions. «הגדרות» still renders for an elevated viewer: the ruler is boutique-wide and worth setting before the first hire |
| **C-empty-work** ✚ | **EMPTY *and* `unassigned_minutes > 0`** | 200 | **Both, in this order**: the muted empty line, then the unassigned `<p>`. A boutique that opens three tickets before adding any staff satisfies both rules at once — a plausible first hour of a pilot — and it is the state in which the unassigned total is **the only true thing on the panel**. A seamstress row cannot stand in for the empty line here, because there are none |
| **C-seamstress** | **A SEAMSTRESS is looking at it** | her own session | Every row, every bar, every sentence, the unassigned line — and **zero controls**: no «שעות» on any row and no «הגדרות». ⚠ **This is not cosmetics.** She is admitted to the board by the router (`atelier/router.py:96-98`) and refused by **both** write routes, and a 403 reaching `runMutation` → `poll.fail` → the `{401,403}` terminal rule would replace **her entire atelier board** with «אין הרשאה» because she tapped a control the console offered her |
| **C-default** | Capacity inherited from the tenant default | `capacity_is_default: true` | The bar and the sentence render normally, plus the muted «ברירת מחדל של הבוטיק» as the sentence's last clause. **The number is honest about whose it is** |
| **C-inactive** | **A retired or re-roled seamstress with live tickets** | `assignable: false`, load > 0 | Her row renders **with her load and her bar** — the work is real and somebody must move it — carrying the shipped «תופרת שאינה פעילה». **The «שעות» control is absent**: `_require_seamstress` refuses her, and rendering a control that always 400s is a trap. She is **not** in the assign `<Select>` (F41's shipped `assignable` filter) |
| **C-stale** | A poll failed with the panel on screen | non-2xx / network | **Unchanged rows.** The freshness row above already swapped `updatedAt` for `staleAt` and said so; blanking correct load numbers to report a network fault is worse than the fault |
| **C-401/403** | Session or permission ended | any tick or mutation | The whole section is replaced by F41's terminal panel and the loop stops — **unless one of the FOUR dialogs is open, in which case the terminal DEFERS** (§6.2). The panel goes with the board once the dialog is dismissed |
| **C-trunc** | Truncated board | 200, `truncated: true` | **The panel is unaffected and exact.** D3's aggregate is uncapped, so `truncated: true` and correct bars coexist — which is the whole argument against the free Python fold |
| **C-busy** ✚ | A save in flight | confirm activated | **That dialog's confirm only**: `loading` on the shipped `Button`. Every panel row stays live. The poll does not tick while a mutation is in flight |

**The ugly edges — each designed rather than discovered:**

| Edge | Behaviour |
|---|---|
| **Capacity 0, load 0** | «0 שעות עד 11.8 מתוך 0», bar empty, **not** overloaded. She is configured as unavailable and holds nothing; that is a consistent state, not an alarm |
| **Capacity 0, load > 0** | «6 שעות עד 11.8 מתוך 0 · עומס יתר», bar full and red. The ratio is undefined; the fact is not. ⚠ She is in **sort group 3**, not group 1 — `remaining` is negative — and truthiness in the resolution would put her **first** |
| **Load with no capacity set** | «4 שעות · לא הוגדרה קיבולת». **No bar, no colour, no word.** This is the single most likely state in week one and it must not read as an error |
| **400 % load** | Bar clamped at 100 %, text unclamped. The numbers are never abbreviated, rounded away or replaced by «>100 %» |
| **Load 721 min against a 12 h capacity** | «12.1 שעות … מתוך 12 · עומס יתר». `Math.ceil` so the sentence can never read «12 מתוך 12» beside a word saying over |
| **20 seamstresses** | Unbounded at 375 (the page scrolls, F41's §6 rule); `md:max-h-96` at ≥768. The `<h3>`'s count is what tells a screen-reader user the list is long **before** she enters it. §7 |
| **A seamstress whose row leaves the payload mid-edit** | Retired **and** her last undelivered ticket delivered — she leaves the union. The dialog is at panel level so it survives the repaint; on save the trigger is gone and §6.3's `<body>` guard puts focus on the panel `<h3>` |
| **`unassigned_minutes` is 0** | The unassigned line is not rendered at all. A zero line is noise on every board that is fully assigned |
| **A band re-tuned yesterday** | Bars are sums of minutes valued under two mappings. **Correct, and left alone** — minutes are minutes, they add, and the number is the true total of what was estimated. Stated so nobody normalises it |
| **A re-tune flattens one band onto another's number** | An old 240-minute ticket under a mapping where `full_day = 240` renders «יום מלא», not the «{{minutes}} דק׳» fallback — `bandLabel` matches on the **minutes value**, first match wins. **The label moves, the load number does not.** Accepted (D4); §4.1 is the dialog's warning |
| **A ticket delivered and then UNDONE** | Re-enters the load immediately, on the next tick, with no other write. Correct — the garment is back in the workroom — and it is the one path by which a bar goes **up** with nobody assigning anything |
| **Every seamstress overloaded** | Every bar red, every row carrying the word. **No aggregated banner** — §11 **P-3** |

### 6.1 What a capacity save does NOT change on screen

⚠ **A successful capacity save repaints only three keys onto the held row: `weekly_capacity_hours`, `capacity_is_default`, `assignable`.** That is all `SeamstressCapacityResponse` carries, and it is deliberate: this write path has **no aggregate**, so the only load value a builder could reach is `(0, 0)` — which would **collapse her bar and drop her «עומס יתר» word for up to five seconds**, on this feature's primary surface, at the exact moment a manager is looking at it. `assigned_minutes` and `due_soon_minutes` keep their last-tick values; the next tick supplies the truth. **The bar's width and colour therefore change on a save only because the denominator changed**, which is exactly what she just did.

### 6.2 ⚠ C7's deferred terminal must cover the two new dialogs, and it does not for free

`AtelierSection` computes `const dialogOpen = form !== null || pendingDelete !== null` (`:212`, verified), and **both** the terminal render (`:782`) and the terminal focus effect gate on it, for the stated reason: *"unmounting the section under an open dialog would silently discard typed work, and a 401 arriving mid-form is exactly the case: the session outlives a shift."*

F42 adds two dialogs whose open state lives in `SeamstressPanel`, which `AtelierSection` **cannot see**. Without a signal, a 401 or 403 tick unmounts the **settings dialog while it holds six edited band values.** So the panel reports its open state up through `onDialogOpenChange(open: boolean)` and the section ORs it in. One boolean, one `useState`, and the mutation that reds it is named.

### 6.3 Focus — one destination, one guard, and BOTH directions pinned

**⚠ THIS REPO HAS SHIPPED A FOCUS-DROPS-TO-`<body>` DEFECT FIVE TIMES (F56, F34, F57, F57's own vacuous test, F41) AND AXE WALKED PAST EVERY ONE**, because axe cannot see a focus move that never happened. F41's post-mortem adds the second half: **the naive fix creates a focus STEAL in the other direction**, and an adversarial verifier caught it after the first fix shipped green.

**What F42 does NOT touch.** `AtelierSection`'s `restoreRef` / `captureFocus` / `boardCommit` machinery (verified at `:165-184`, `:205-225`) is keyed on `[data-ticket-id]` and stamped with the board-commit count. F42 adds **no** seamstress key to it, does not generalise its selector, and adds no destination. **Any edit to that block is a review stop.**

**Because both writes are `Modal`s, and native `<dialog>` restores focus to its trigger by itself** — `Modal.tsx:15-18` says so in those words, verified. Three of the four paths need nothing:

| Path | Destination | Mechanism |
|---|---|---|
| Dialog dismissed (Esc, backdrop, «ביטול») | its trigger | native `<dialog>` |
| Save refused | **the dialog's own alert**, `role="alert" tabIndex={-1}` — the dialog stays open | keyed on the error state |
| Save succeeded, trigger still mounted | its trigger | native `<dialog>` |
| **Save succeeded, the trigger has UNMOUNTED** | **the panel's `<h3 tabIndex={-1}>`** | the one line below |

**The one case `<dialog>` cannot serve.** The capacity dialog's trigger is a `Button` inside a seamstress `<li>`. A seamstress leaves the union when she is retired **and** her last undelivered ticket is delivered. If that lands between opening the dialog and saving it, the trigger has unmounted and `<dialog>`'s auto-restore lands on `<body>`.

**⚠ THE OWNER AND THE TURN ARE BOTH SPECIFIED, BECAUSE "on the paint that follows" IS NOT A MECHANISM.**

```ts
// SeamstressPanel — it owns BOTH the trigger and the heading ref.
// AtelierSection owns runMutation and writes NO focus code for this feature.
const ok = await onSaveCapacity(id, hours);   // resolves, never rejects
if (!ok) return;                              // dialog stays open, alert renders
closeDialog();
setSaveCount((n) => n + 1);                   // monotonic

useEffect(() => {
  if (saveCount === 0) return;
  if (document.activeElement === document.body) headingRef.current?.focus();
}, [saveCount]);                              // runs AFTER React commits the repaint
```

- **The destination is the panel's own `<h3 tabIndex={-1}>`** — F51's shipped stranded-focus pattern, the same one F41 uses for a deleted card's column heading. No ref map, no lookup, one node that is always mounted whenever the panel is.
- **Keyed on the counter, not the payload**: a state setter bails out of a reference-identical value, so keying on the data would silently skip the one repaint the guard is waiting for. That is `boardCommit`'s recorded reason, one level down.
- **The guard is `activeElement === document.body` and nothing else** — the browser saying the repaint dropped focus, rather than the console guessing from the data. It is what makes the move free: if focus is on something real, this does nothing.
- **⚠ AND THAT IS EXACTLY WHY IT CANNOT STEAL.** F41's fix needs a commit stamp because its restore fires on **poll repaints**, which arrive with no user action and can outlive the user's own focus move. This fires **only on a successful save**, in the same turn, and only when focus is already nowhere. **Copying F41's mechanism wholesale is the obvious wrong move**: a stamp here would be machinery for a race this shape does not have.
- **One counter and one effect serve both dialogs.** The settings dialog's trigger is panel-level and never unmounts, so its guard never fires — a second counter would be a second thing to keep true for a path that cannot happen.

**Both directions are named, non-vacuous tests.** A test asserting only "the save succeeded" passes with every focus line deleted; a test asserting only the restore passes against a build that steals. Each asserts `document.activeElement` **is** the expected node — never merely that the node exists. ⚠ **jsdom does not blur a disabled element**, so a test leaning on that is vacuous; F57's own vacuous focus test is the recorded instance.

---

## 7. Breakpoints — 375 / 768 / 1440

| Width | The panel | Arithmetic |
|---|---|---|
| **375** (primary) | Full width, **unbounded**, the page scrolls | 375 − 2 × `--space-4` = 343 shell → − 2 × `--space-6` `Card` padding = **295 px of row content**, identical to F41's card measurement. Row height: 24 (`py-3`) + 44 (the `min-h-11` name/button row) + 16 (bar + `mt-2`) + 25 (one wrapped line + `mt-1`) = **109 px common**, **151 px** when the sentence runs to three lines |
| **768** | Full width — **not** in F41's two-column grid, which begins below the panel. `md:max-h-96 md:overflow-y-auto` | 720 − 32 = 688 − 48 = **640 px of row content**. The sentence never wraps, so every row is **109 px** and 24 rem shows **3.5 rows** |
| **1440** | **Identical to 768.** The console never exceeds 720 px of content and this panel is not the exception | — |

**⚠ BOUNDED AT ≥768 ONLY, AND THE SPEC'S "every width" IS F-2.** Spec D8 says `max-h-64` at every width. Two things are wrong with that and they are independent:

1. **`max-h-64` is 16 rem = 256 px, which is 2.3 common rows and 1.7 worst-case rows — not the "about four rows and a hint of the fifth" the spec claims.** The estimate omitted the 44 px button row that the touch-target floor makes mandatory.
2. **Bounding at 375 reintroduces the exact scroll-trap F41 refused.** F41's §6, verbatim: at 375 column bodies are *"not height-bounded — the page scrolls naturally … Nested scroll containers on touch are a scroll-trap for the sake of a viewport that has no second column to align to."* A bounded panel above a stacked board is that trap, on the primary device, on the feature's own surface.

The remedy is one `md:` prefix and one bound value: **`md:max-h-96 md:overflow-y-auto`**. And the "twenty rows push the rail off screen" worry is answered exactly as F41 answers a 60-card column — the page scrolls, and this product's tenants have **three to six** staff (spec Risk 6: *"the first tenant with fewer than three staff"*). A three-seamstress roster never scrolls at any width.

**`tabIndex={0}` on the `<ul>` stays UNCONDITIONAL** even though the overflow is `md:`-only. That is F41's shipped call and its reason transfers unchanged: axe's `scrollable-region-focusable` fires on exactly this shape, and *"a resize observer deciding an ARIA-relevant attribute is a mechanism to keep true for a tab stop that costs nothing."* It is also useful — it is the keyboard's entry stop into the list (§8), and a named `<ul>` announces «תופרות, רשימה, 3 פריטים» when focused.

**24 rem, not a viewport unit.** `md:max-h-[60vh]` would give a landscape tablet a 300 px window and a tall desktop an 800 px one — one class carrying two designs. `24rem` ≈ 384 px ≈ three and a half rows, is stable across viewports, and honours `:root[data-a11y-text-size]`'s 1.2 rem root scaling for free.

---

## 8. Keyboard — the concrete pass

**No new mechanism, and that is the claim §0 makes structurally.** There is no `role="grid"`, no roving `tabindex`, no arrow-key manager and no focus trap outside the two native `<dialog>`s. What follows is what the DOM order already produces.

```
… shell skip link → logout → nav → #console-main
  → pause / resume                       (STILL the first stop — SC 2.2.2, F41 D17)
  → THE PANEL:
       (the <h3> is tabIndex={-1} — a target, NOT a stop)
       the <ul> itself                   (tabIndex={0} — one stop, announces the count)
       row 1 «שעות»  →  row 2 «שעות»  →  row 3 «שעות»      (render order = sort order)
       (the unassigned <p> is text — no stop)
       «הגדרות»                          (LAST stop in the panel)
  → «כרטיס חדש» → rail: 5 links → F41's five columns, unchanged
```

**Inside the capacity dialog** (native `<dialog>` traps focus, Esc dismisses without writing):

```
the number Input  →  «חזרה לברירת המחדל»  →  «ביטול»  →  «שמירה»
```

**Inside the settings dialog:**

```
band 1 … band 5  →  the default Input  →  «ביטול»  →  «שמירה»
```

**Four things this order is asserted for, not assumed:**

- **`Enter` on «שעות» opens the dialog and calls no API method.** Its own acceptance line — the trigger opens, the confirm writes.
- **`Esc` dismisses without writing**, and focus returns to the trigger by itself.
- **«הגדרות» is last, which is why it sits at the panel's foot rather than beside the heading.** §11 **P-5**: a boutique-wide setting placed before the data would be the first thing after the heading and would push every row one stop further away, on the surface a shift manager visits to read rows.
- **Every stop is ≥44 px.** `Button size="md"` is `min-h-11`; `Input`'s `px-3 py-2 text-base` lands at ≈44 px; **`size="sm"` (36 px) is barred anywhere in this tree**, asserted as a rendering check, because axe has no target-size rule at the level this repo runs it.

**A non-elevated viewer's pass is shorter and still complete**: the `<ul>` is her only stop in the panel, and she reads every row's text on the way past it. Nothing is hidden from her; only the two write controls are absent.

---

## 9. Component notes — exact tokens

| Element | Notes |
|---|---|
| Panel `<section>` | `<section aria-labelledby="atelier-h-capacity" className="space-y-2">` — a **named region**, §10.1 |
| Panel `<h3>` | `<h3 id="atelier-h-capacity" ref={headingRef} tabIndex={-1} className="text-base font-semibold text-ink">` — F41's column-heading shape exactly. Carries the **counted** `atelier.capacity.headingCount`. `tabIndex={-1}` adds **no** tab stop |
| Panel `Card` | `<Card className="space-y-3">`. **`p-6` untouched** — `cn()` is a plain join and the consumer loses |
| The `<ul>` | `<ul tabIndex={0} aria-label={t("atelier.capacity.heading")} className="divide-y divide-border md:max-h-96 md:overflow-y-auto">` — the **uncounted** name (§10.1) and §7's bound |
| Row `<li>` | `<li data-seamstress-id={s.id} className="py-3 first:pt-0 last:pb-0">` |
| Name | `<bdi className="font-semibold text-ink break-words">` — **bare `<bdi>`**; `dir="ltr"` on «נועה לוי» reverses its words and *looks deliberate* |
| Name row | `<div className="flex flex-wrap items-center justify-between gap-2">` — `flex-wrap` so a long name pushes the button down rather than squeezing it |
| The bar | §2.1 verbatim. `aria-hidden="true"`, `mt-2 block h-2 rounded-sm bg-border` track, `bg-gold-strong` / `bg-danger` fill, `style={{ inlineSize }}` |
| The sentence | `<p className="mt-1 text-sm text-ink-muted">` — up to four clauses, `<strong className="font-semibold text-danger">` on «עומס יתר» only |
| «שעות» | `<Button variant="ghost" size="md" fullWidthMobile={false} aria-label={t("atelier.capacity.editAria", { name })}>` — elevated only, absent on an `assignable: false` row |
| Unassigned line | `<p className="text-sm text-ink-muted">` — **after `</ul>`, inside the `Card`**, rendered only when `> 0` |
| «הגדרות» | `<Button variant="ghost" size="md" fullWidthMobile={false} aria-label={t("atelier.settings.openAria")}>` — elevated only, panel foot |
| Empty line | `<p className="text-sm text-ink-muted">` in the `<ul>`'s place |
| Both dialogs | `<Modal open onClose title footer={<><Button variant="ghost">ביטול</Button><Button variant="primary" loading>שמירה</Button></>}>` — the shipped two-button footer, **unmodified** |
| Number fields | `<Input type="number" inputMode="numeric" min={0} label help error />` — **no `max`** (§3.3), **no `dir`** (§3.3) |
| Dialog alert | `<p role="alert" tabIndex={-1} className="text-sm text-danger">` above the footer |

**Contrast, computed — not eyeballed.** From the tokens ledger: ink 13.89 on paper · ink-muted 5.61 · **danger 6.18** · warning-text 5.20 · focus ring 5.57. New to this feature, both **non-text**:

| Pair | Ratio | Where |
|---|---|---|
| `gold-strong #9E7B36` on `border #E4DACA` | **2.84:1** | the bar's normal fill — **inherited unchanged** from `DashboardSection`'s shipped `Bar`, not introduced here |
| `danger #A03232` on `border #E4DACA` | **5.07:1** | the bar's overload fill — **new**, and it clears 3:1 comfortably |

**⚠ Note the direction, because it is the right one.** The pair that falls under 3:1 is the **calm** state; the pair that carries the alarm is the compliant one. §10.3 argues why 1.4.11 does not bind either, and this asymmetry is why the argument is not load-bearing: **the only rendering an overload actually depends on already passes.**

---

## 10. The a11y contract — IS 5568 / WCAG 2.0 AA is a legal requirement (pre-decided #38)

### 10.1 Structure — one named region, one named list, and the two names are different strings

```
<section aria-labelledby="atelier-h-capacity">     ← a region, exposed because it is named
  <h3 id="atelier-h-capacity" tabIndex={-1}>       ← «תופרות · 3»   COUNTED
  <Card>
    <ul tabIndex={0} aria-label="תופרות">           ← «תופרות»        UNCOUNTED
      <li> … </li> × N
    </ul>
    <p>לא משויך · 4 שעות</p>                        ← a SIBLING of the <ul>, never an <li>
    <Button>הגדרות</Button>
  </Card>
</section>
```

- **Both are named, and the names are deliberately different keys.** An unnamed `<section>` is **not exposed as a region at all**, and an unnamed `<ul>` is an anonymous list — so a user navigating by list (NVDA `L`, VoiceOver rotor) would land on **six** consecutive unnamed lists and have no way to tell the capacity panel from the `qc` column.
- **⚠ The `<ul>` takes the UNCOUNTED name, and that is not a style choice: an accessible name must not churn on a five-second tick.** The count *can* change without any staff edit — `seamstresses` is a **union**, so a retired assignee leaves it the moment her last undelivered ticket is delivered, which is a poll-driven change. F41's shipped answer is exactly this split and this deck copies it.
- **⚠ `{{total}}` is `seamstresses.length` — PEOPLE, NOT ROWS — which is why the unassigned total is a `<p>` OUTSIDE the `<ul>`.** With it inside, a screen-reader user would hear «תופרות, 4 פריטים» after a heading claiming 3, on every board with unassigned work. Outside, the list's item count and the heading's number are **the same fact**, and an acceptance line asserts they are equal.
- **`{{total}}`, never `{{count}}`.** `count` is i18next's plural-resolution trigger — F41's rule 11, inherited.
- **Heading levels**: the shell owns the `sr-only` `h1`, F41's section heading is the `h2`, and this `<h3>` sits beside F41's five column `<h3>`s. **No fourth level** — a row is a list item, and giving each a heading would put six headings above five columns of them.

### 10.2 Live regions — F42 adds no region and writes to exactly one

| Region | ARIA | F42's contribution |
|---|---|---|
| F41's cue, above the panel | `role="status"` | **three strings**: `capacity.cue.saved`, `capacity.cue.cleared`, and the conditional `cue.assignedOverload`. All three are the direct consequence of an **activation** |
| The panel's `<ul>` and rows | **no live attributes at all** | none. `aria-live="polite"` on a list that repaints every five seconds on a shared board is a region that talks for a whole shift |
| The freshness row | **no live attributes**, and deliberately **not `aria-hidden`** | none |

**⚠ THE POLL NEVER ANNOUNCES A LOAD CHANGE, AND THIS IS THE ONE PLACE THAT COSTS SOMETHING.** A bar turning red on a tick is exactly the kind of "meaningful change" a reviewer will argue should be announced — and F41's §4.2 spends four paragraphs establishing that it must not be, on the grounds that a shared board's remote changes are not the reader's outcomes. **F42 does not crack that rule**, and the price is named honestly: a screen-reader user learns that a colleague is overloaded only by re-reading the row, or by being told at the moment she causes it (§5.3's cue). **The bounded exception — "announce only when the poll pushes someone over" — is a rule change above this feature**, and it would be the first crack in a rule four surfaces now depend on. Recorded, not taken.

### 10.3 Which success criteria bind, and which explicitly do not

| SC | Binds? | How it is met, or why not |
|---|---|---|
| **1.4.1 Use of Colour** (A) | **YES** — this is the epic's named hard case | §2.4. The **word** «עומס יתר» is the signal, `font-semibold` is the second non-colour channel, and the numbers are the third. One predicate drives the word and the colour together, so a colour-only build cannot be written |
| **1.4.3 Contrast (Minimum)** (AA) | **YES**, for the text | Every string in the panel is `text-ink` (13.89:1), `text-ink-muted` (5.61:1) or `text-danger` (6.18:1) at `text-sm` or larger |
| **1.4.11 Non-text Contrast** (AA) | **NO — argued, not assumed** | The bar is `aria-hidden` decoration **every value of which is text in the same row**; 1.4.11 exempts content whose information is available in another form. `DashboardSection`'s shipped argument is the precedent, in its own words: *"remove every bar and the screen loses nothing."* The 2.84:1 pair is therefore a **recorded decision**, not an oversight — and §9 notes that the overload pair passes anyway |
| **2.1.1 Keyboard** (A) | **YES** | §8. No custom key handling exists to get wrong |
| **2.2.2 Pause, Stop, Hide** (A) | **YES, and it is F41's control** | The panel adds no beat and no second loop. Its only obligation is **not to displace the pause control from the first stop**, which §1.1's insertion point guarantees and §8 asserts |
| **2.4.6 Headings and Labels** (AA) | **YES** | Every control carries a per-row or per-panel accessible name; a six-row panel does not expose six buttons named «שעות» |
| **2.5.3 Label in Name** (A) | **YES** | `capacity.editAria` starts with «שעות» and `settings.openAria` with «הגדרות», so a speech-input user saying the visible word matches. **Asserted in `i18n.test.ts`, not trusted** |
| **3.2.2 On Input** (A) | **YES** | Nothing on this panel mutates on `change`. Every `Input` sets draft state and a footer `Button` commits — F41's D16 rule, and here it is the ordinary form shape anyway. ⚠ A `type="number"` field changes value on wheel when focused; that is the platform's behaviour and it is harmless here **because the draft is not the write** |
| **4.1.2 Name, Role, Value** (A) | **YES** | §2.5 is the whole of it: the bar has **no** role and **no** value, which is the correct answer, and the only assertion that catches a wrongly-roled one is the named test |

**An axe pass runs over the panel and over both open dialogs — and it is explicitly NOT sufficient.** axe cannot see a focus move that never happened (§6.3, five shipped instances), cannot see SC 2.2.2 at all, and will pass a bar carrying `role="progressbar" aria-valuenow="125"` without complaint (§2.5). **Three assertions carry the legal load and may not be cut as redundant**: both focus directions, the overload word's presence with the class deleted, and the bar's absence of widget semantics.

### 10.4 ⚠ Bidi — this feature uses NO helper, and that is a departure from D9 with a reason

Spec D9 says *"Every numeric run is `<bdi dir="ltr">` and every name is a bare `<bdi>` — `isolateLtr` / `isolateBidi`."* **Applied literally to `atelier.capacity.load` that is unbuildable and would ship a live defect** (§12 **F-5**):

- The string is «{{hours}} שעות עד {{date}} מתוך {{capacity}}» — **three** numeric runs. `isolateLtr(text, value)` isolates **one**, by `text.indexOf(value)`.
- **And the collision is live, not theoretical.** On «12.1 שעות עד 11.8 מתוך 12», isolating the capacity with `isolateLtr(text, "12")` matches the **"12" inside "12.1"** and wraps a fragment of the wrong number. Equal hours and capacity («12 … מתוך 12») leave the second occurrence unisolated. F41's own rule bars the alternative — *"no second helper is invented"*.

**No helper is needed, and the reason is the bidi algorithm.** Every numeric run in every string in this feature is **bounded by Hebrew or sits at a paragraph edge where the base direction places it correctly**, and **no string contains Latin text**. Under UBA: neutrals between R and EN resolve to R (N1/N2, EN counting as R), each EN run is bumped to an even level by I2 and renders LTR **in place**, and an RTL paragraph's first and last runs land at the right and left edges respectively — which is their correct reading order. «12.1 שעות עד 11.8 מתוך 12» renders exactly as written.

**So the rule for this feature is one line: the seamstress's NAME is isolated with a bare `<bdi>` in its own `<span>`, and nothing else is isolated at all.** The name is the only user-supplied value, it is never interpolated into the sentence, and an `<option>` and an `aria-label` both take no markup anyway. §12 **F-5**.

---

## 11. RESOLVED decisions — self-approved with the design gate, 2026-08-04

**All eight carry a resolution and none is an open question.** Each keeps its reasoning, because the reasoning is what a later feature would have to overturn to reopen it. **The Hebrew remains the user's to edit post-merge** — the F15 P-1/P-5, F34, F57 and F41 precedent: a one-line `he.ts` / `ar.ts` edit after merge, never a rebuild.

| | Resolution |
|---|---|
| **P-1** | **One `Card` around a `divide-y` list, heading outside it** — F57's shape, the inverse of F41's |
| **P-2** | **The overload word is a `<strong>` inside the row's one `<p>`, never a second `Badge`** |
| **P-3** | **No aggregate overload banner** |
| **P-4** | **No per-seamstress ticket list, drill-down, sparkline or trend** |
| **P-5** | **«הגדרות» at the panel foot, last in tab order** |
| **P-6** | **A seamstress sees the whole panel and zero controls** |
| **P-7** | **One settings dialog for both `atelier` keys, never two** |
| **P-8** | **No bar for the unassigned pile** |

- **P-1 — RESOLVED: `<section>` → `<h3>` → `<Card>` → `<ul className="divide-y">` → `<li>`.** F41 made the *ticket* the `Card` because *"the unit of this screen is a thing that moves between named regions."* A seamstress row **moves nowhere** — it is a static line about a person — so F57's P-1 applies directly: at 375 a card and a row inside a card are the same rectangle, and three stacked `Card`s above five columns of `Card`s is `shadow-sm` on `shadow-sm`. The heading stays outside the `Card`, which is F41's column shape, so the two structures on one screen read as siblings rather than as two conventions.
- **P-2 — RESOLVED: «עומס יתר» is a `<strong>` in the sentence, not a `Badge`.** F41 fixes *exactly one `Badge` per card and overdue owns it*, and this panel sits directly above sixty of those cards; a second `Badge` shape would make the two vocabularies compete. It would also **split the payload into two announced chunks**, where §2.5's whole argument is that the row reads as one continuous sentence. `--color-danger` at `text-sm` is 6.18:1, so the word passes AA as text on its own.
- **P-3 — RESOLVED: no «הבוטיק בעומס» banner, at any threshold.** Tempting when every row is red. Declined: a second, louder signal saying what four rows already say is how a board stops being read — F41's **P-3** made the same call about a sixth count, and the failure mode here is worse because a banner would be *permanently* true in a busy season. **The panel heading is not a consumer of the overload predicate either**: `{{total}}` counts the roster, and an overload total there would need its own key, its own state row and its own assertion. The claim is **dropped rather than half-built**.
- **P-4 — RESOLVED: the row is name · bar · sentence · one `Button`, and nothing else.** No sparkline, no per-stage split, no "which tickets" list, no trend arrow. Her tickets are three inches below, in the columns, sorted by the due date the whole epic subtracts from — a second rendering of them in the panel would be a second thing to keep true through every tick. **Load history and throughput are F44's**, which reads the five stamps directly and needs nothing from here.
- **P-5 — RESOLVED: «הגדרות» sits at the panel's foot.** Beside the heading it would be the first thing after «תופרות · 3» and would push every row one tab stop further away, on a surface a shift manager opens to **read rows**. It is a boutique-wide configuration action, used once a quarter, on a panel read fifty times a shift. The spec's acceptance line pins the order, so this is a resolution rather than a preference.
- **P-6 — RESOLVED: a seamstress sees every row, every bar and every sentence, and no control at all.** No disabled button, no lock glyph, no «אין לך הרשאה» line — F41's §2.3 reasoning, plus one consequence that is specific to this panel and far worse: an ungated control would produce a **403**, `runMutation` routes it to `poll.fail`, `usePoll`'s `{401,403}` rule makes it **terminal**, and **her entire atelier board is replaced by «אין הרשאה»** because she tapped something the console offered her. The absence is cosmetics; the control is the server's per-route gate.
- **P-7 — RESOLVED: one dialog, one save, both `atelier` sub-keys.** Two dialogs, or two save buttons, would each send a *partial* `atelier` object — and `||` merges at the **top level only**, so each would silently delete the other's key. The one-writer rule is made **structural** by the request model having no default on either field, not by a note in a handler. §4.
- **P-8 — RESOLVED: the unassigned pile is a line of text with no bar.** Nobody has capacity for it, so there is no denominator and a bar would be a ratio of a number to nothing. It is also **not an `<li>`** — it is a total, not a person, and inside the list it would put the announced item count one above the heading's. Rendered only when `> 0`.

---

## 12. ⚠ FINDINGS

- **F-1 — ⚠ THE SENTENCE'S HORIZON DATE HAS NO SOURCE, AND THE OBVIOUS WORKAROUND IS THE BUG `lib/jerusalem.ts` EXISTS TO PREVENT.** `atelier.capacity.load` interpolates `{{date}}` — «6 שעות **עד 11.8** מתוך 12» — and nothing can produce it. The envelope carries `unassigned_minutes` and `default_weekly_capacity_hours` and **no date**; `lib/jerusalem.ts` ships six formatters and **zero arithmetic** (verified, whole file), and `plainDate`'s own comment forbids the reach a builder will make: *"`new Date("2026-05-03")` parses as UTC midnight, and running that through a zoned formatter re-zones a date that was never in a zone … the exact class of bug this file exists to prevent."* **And a correct client computation would still print the wrong date**: the SQL filtered on the **server's** `today_jerusalem + 7`, and a device that has crossed Jerusalem midnight while the payload was held names a horizon the aggregate did not use — two clocks for one number, on the string that is this feature's whole accessibility payload. **Remedy: one field, zero statements, zero new date sources.** `AtelierBoardResponse` gains `due_soon_through: datetime.date` beside the two the spec already adds — `board()` computes `horizon` for the `FILTER` and has it in hand — and the console renders it through the shipped `plainDate`. **This makes the envelope's new-field count THREE, not two**, which is a correction to spec D7 and to §Conflicts 5's arithmetic. *Owner: this feature. Trigger: the plan, which must carry it as a task rather than discovering it when the sentence renders «עד undefined».*
- **F-2 — ⚠ `max-h-64` AT EVERY WIDTH IS TWO SEPARATE DEFECTS.** (a) **The number is wrong**: 16 rem = 256 px, and an elevated row is 24 px `py-3` + **44 px** for the `min-h-11` name/button flex row + 16 px of bar + 25–67 px of sentence = **109 px common, 151 px worst**. That is **2.3 rows**, not the spec's *"about four rows and a hint of the fifth"* — the estimate omitted the button row that the 44 px touch floor makes mandatory. (b) **Bounding at 375 reintroduces the trap F41 refused**, in F41's own words: *"Nested scroll containers on touch are a scroll-trap for the sake of a viewport that has no second column to align to"* — and this one sits above a stacked board on the primary device. **Remedy: `md:max-h-96 md:overflow-y-auto`** (24 rem ≈ 3.5 rows at the ≥768 width where the sentence stops wrapping), unbounded at 375 with the page scrolling exactly as F41's columns do, and `tabIndex={0}` unconditional for F41's stated reason. The "twenty rows" worry the spec's bound was protecting against is answered the same way F41 answers a 60-card column, and this product's rosters are three to six. *Owner: this feature. Trigger: the plan.*
- **F-3 — the spec never says WHICH of the two sums becomes `unassigned_minutes`.** D3's aggregate returns `(due_soon_minutes, assigned_minutes)` for every group **including the `NULL` one**, and D7's envelope carries a single `unassigned_minutes` with no statement of which it is. **Resolved: the UNFILTERED sum — the whole unassigned backlog.** Three reasons: the row carries **no bar**, so there is no rate for a horizoned numerator to divide into; it is LOOP-STATE's number verbatim, which is what the seamstress rows already state in the same Hebrew word («סה״כ … בתור»), so one word means one thing on this panel; and the horizoned slice is available from the same tuple for free if a pilot asks for it. *Owner: recorded, resolved here and in `copy.md` §2.*
- **F-4 — the spec never says which number `loadNoCapacity` shows, and the answer forces a one-word change to D10's sort key.** «{{hours}} שעות · לא הוגדרה קיבולת» is the row for a seamstress with **no denominator**, so a horizoned numerator has nothing to be a numerator of. **Resolved: `assigned_minutes` — her whole backlog** — which is also what makes an unconfigured row comparable with the «סה״כ … בתור» clause on a configured one. ⚠ **The consequence is that D10's group 2 must sort by `assigned_minutes` ASC and not `due_soon_minutes` ASC**, or the panel's visible order and the `<Select>`'s visible order are both governed by a number **neither surface displays** — which is exactly D10's own argument for labelling the options at all (*"a reordered list with no explanation is a list that shuffles for no reason a user can see"*). The Hebrew already settles it: `optionAssigned` is «{{hours}} שעות **משויכות**», and *assigned* names `assigned_minutes`. D3's stock-vs-rate argument does not bind here — group 2 has no rate, so the comparison is stock-to-stock **within** the group and is dimensionally sound. **The spec's acceptance line survives unchanged** (*"then no-capacity rows by load ascending"* names no field); only D10's prose needs the one word. *Owner: this feature. Trigger: the plan — one line in `lib/capacity.ts`, plus the assertion that reds if it drifts.*
- **F-5 — ⚠ D9's blanket "every numeric run is `<bdi dir="ltr">`" is unbuildable on this feature's main string and would ship a substring collision.** `atelier.capacity.load` carries **three** numeric interpolations; the shipped `isolateLtr(text, value)` isolates **one**, by `indexOf`. On «12.1 שעות עד 11.8 מתוך 12» isolating the capacity as `"12"` matches **inside "12.1"**; equal hours and capacity leave the second occurrence unwrapped. Writing a multi-run helper is barred by F41's own rule (*"no second helper is invented"*). **Resolved: no bidi helper is used anywhere in this feature, because none is needed** — every numeric run is bounded by Hebrew or sits at a paragraph edge the base direction places correctly, and no string contains Latin text (§10.4 carries the UBA derivation). **The seamstress's name is the only user-supplied value and it is isolated with a bare `<bdi>` in its own element, never interpolated into the sentence.** Recorded rather than folded in silently, because a reviewer diffing this deck against D9 will otherwise read it as drift. *Owner: recorded, resolved in §10.4 and `copy.md` §9.*
- **F-6 — ⚠ THE CAPACITY DIALOG'S THIRD FOOTER BUTTON DOES NOT FIT AND `Modal` CANNOT BE MADE TO HOLD IT.** Spec §Frontend puts «חזרה לברירת המחדל» in the footer as a third `Button` that submits `null`. `Modal.tsx:56` is `<div className="mt-6 flex justify-end gap-3">` — **hard-coded, no `flex-wrap`, and no `className` seam** (verified) — so three buttons, one of them five Hebrew words, overflow a 295 px footer at 375; and editing a `packages/ui` component from a call site is barred outright. **Remedy: the control moves into the dialog body below its field and CLEARS the field rather than submitting** (§3.1). One submit path, one confirm, one loading state, one error path — and **empty ⇒ `null` ⇒ "use the boutique default" in both directions**, which makes the field's emptiness mean one thing on this dialog always. ⚠ **Two consequential copy additions**: the help line explaining that rule is **two strings**, because «חזרה לברירת המחדל של הבוטיק» is a **lie on every tenant that has no default** — which is every boutique on day one, the state D2 exists to protect. *Owner: this feature. Trigger: the plan.*
- **F-7 — F41's F-2 named "F42's capacity matrix" as the owner of the 720 px console-width decision, and F42 declines it.** F41 measured five columns at **128 px** inside `ConsoleShell`'s three 720 px caps and deferred the fix on the grounds that *"a seamstresses × days grid has the same problem, a stronger claim, and its own design gate."* **That grid does not ship** (§0): the second dimension is F40's roster projection, dropped by ruling, and what ships is a full-width list that fits inside 720 px with room to spare. So F42 adds **no** claim on the console width and **the finding needs a new owner**. The natural one is **F44's workshop board**, which the spec's own Out-of-scope describes as *"a layout that owns its whole viewport"* — a wall-mounted display is the first surface in this program with a real reason to exceed a form column. The recorded shape is unchanged: a `contentWidth` prop on `ConsoleShell` applied to **all three** rows (header, nav, main), defaulting to 720. *Owner: F44. Trigger: F44's deck, or a pilot owner asking for a desk view.*
- **F-8 — F41's F-8 named F42 as its own trigger, and the answer is "no change".** F41 recorded that *"if a fourth panel ever lands on this section, the rail is the thing that stops scaling — five chips wrap at 375 already. Owner: team. Trigger: F42, which adds a seamstress directory to this screen."* **The trigger has fired and the rail is untouched**: F42's panel sits **above** the rail as a sibling, not as a sixth chip, and adds no stage, no count and no anchor target. The rail's five chips and their wrap behaviour at 375 are byte-identical to F41. **Closed rather than re-deferred**, because a finding whose named trigger has passed without an answer is a finding that quietly becomes untrue. *Owner: closed.*
- **F-9 — the panel's REGION name churns on a tick, and this is inherited from F41 rather than introduced.** `<section aria-labelledby>` points at the **counted** `<h3>` «תופרות · 3», so the region's accessible name changes whenever the union changes — which a poll can cause without any staff edit (a retired assignee leaves when her last ticket is delivered). §10.1's own rule says a name must not churn, and it is applied to the `<ul>` and not to the `<section>`. **Accepted, and diverging is refused**: F41's five columns have the identical shape with counts that change on **every advance**, and giving this one `<section>` a private uncounted `aria-label` would make the panel structurally different from the five regions beside it for a benefit nobody has measured — a region name is read on entry, not arrowed through the way a list's is. *Owner: recorded, no action. Trigger: a pilot report from a screen-reader user, at which point the fix is one attribute on **six** regions, not one.*
- **F-10 — the bar is byte-identical at 140 % and at 400 %, and a later reader will try to fix it.** The clamp means the widget cannot distinguish "twenty minutes over" from "a month behind": past 100 % only the **colour** and the **sentence's numbers** move. That is designed — the width answers *how full*, the colour answers *over or not*, the text answers *by how much* — and it is stated so nobody adds a stripe, an overflow nub, a «×4» chip or a second bar. Every one of those invents a visual vocabulary for a fact the sentence already carries **precisely**, on a widget that is `aria-hidden` and therefore invisible to half the users it would be built for. **If a pilot genuinely cannot read magnitude from the sentence, the remedy is the sentence, not the bar.** *Owner: recorded, no action.*
- **F-11 — the settings dialog re-tunes the ruler and says nothing about what that does to the board.** D4 establishes that a re-tune re-values nothing **and** that an old card can therefore **silently relabel** — flattening «יום מלא» to 240 makes every «חצי יום» garment read «יום מלא», with no fallback and no visible act — and accepts it. The dialog is the only place a human causes that, and the spec's key table has **no string for it**, so an owner correcting one band gets an unexplained relabel across her board with no way to connect the two. **One key closes it**: «שינוי ההערכות משפיע רק על כרטיסים חדשים.» under the bands label (§4.1) — true, reassuring to a hesitating owner, and one row in `copy.md`. *Owner: this feature. Trigger: the i18n task.*
