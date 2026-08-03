# Screen: Atelier alteration tickets + kanban (F41 — `AtelierSection`, the console's thirteenth section «תפירה»)

**Date**: 2026-08-03 · **Status**: **DESIGN GATE SELF-APPROVED.** Interview **Q2** named exactly two novel interaction patterns for this run — F34's shift board and F42's capacity matrix (`LOOP-STATE.md` `rulings_2026_07_31`) — and both were themselves self-approved the same day. A board of `Card`s assembled from shipped `Card` / `Badge` / `Button` / `Select` / `Modal` on F34's console shell is neither, so there is **no prototype and no `design-critic` pass** at this gate. **What that costs is stated rather than hidden**: the two things a human reviewer would have caught here are SC 2.2.2 (§9.4) and the **fifth focus move** nothing upstream specified (§3.3, **F-1**).
**Designer**: Claude · **Consumes**: `.planning/specs/alteration-tickets.md` (**D1–D19**, Gate 1 standing approval) · `.planning/design/system/tokens.md` (**binding**) · `.planning/design/screens/design-system/manage-restyle.md` (**binding**) · `.planning/design/screens/shift-board/design.md` **Revision 2** (this section is the third `usePoll` surface and inherits F34's rulings whole) · `.planning/design/screens/floor-staff-roles/design.md` (F57 — the shipped reference consumer; every mechanism here is its mechanism with a different payload) · `packages/ui` and `apps/manage` **as shipped at `18127e7`**
**Copy**: `copy.md` in this directory — every Hebrew string with its untranslated `ar` value (Interview Q3 / pre-decided #47 / the 2026-07-31 languages ruling).
**Prototype**: **none, deliberately.** The two questions a prototype exists to answer on a polling surface — is a five-second beat usable, is a one-tap mutation right under a thumb — were answered at F34's gate and the mechanisms are now shared code (`lib/usePoll.ts`). This section introduces no beat and no control shape F34 and F57 have not already put in front of the user. What it *does* introduce — a card that moves between named regions under a keyboard — is not a thing a still prototype could have shown either.

**What this deck is NOT.** It is not a redesign of `FloorPanel`, `BoardSection` or `StaffSection`. F41 touches none of those components (spec §Frontend changes). It is not the capacity matrix — that is F42, which extends this payload and this deck's assign control (§10 **P-8**).

---

## 0. Scope

The console gains a **thirteenth section** — `nav` key `atelier`, label «תפירה» — and **one new component**, `AtelierSection.tsx`, plus one new `lib/stages.ts`.

`App.tsx`'s `SectionKey` union is **twelve** members as shipped (`:20-33`: dashboard, profile, hours, types, terms, catalog, bookings, customers, board, staff, gateway, floor) and `NAV` is twelve rows (`:64-109`). F41's is the thirteenth of each. The in-file comment at `:31` — *"F57's floor — the ELEVENTH member"* — is already stale by one (F53's `customers` landed after it) and should be corrected in passing.

| Surface | Who sees it | Shape |
|---|---|---|
| The whole `atelier` section | owner, shift_manager, **seamstress** | `<AtelierSection selfId role />`, alone in `#console-main` |
| The nav row «תפירה» | the same three | the thirteenth `NAV` row |

**⚠ THE `NAV` ROW GOES IMMEDIATELY AFTER `floor`, AND THAT IS THE SAME POSITION AS "AFTER «לוח היום», BEFORE «צוות»" — the two phrasings in the spec are not in conflict and a builder must not "fix" one against the other.** Verified against the shipped array (`App.tsx:99-109`): the order is `… bookings, customers, board, floor, staff, gateway`, and `floor` carries `roles: FLOOR_ONLY`, so **the owner never sees it**. Insert `atelier` between `floor` and `staff` and all three of the spec's counted claims hold at once:

| Role | Filtered nav after F41 | Which spec claim it satisfies |
|---|---|---|
| owner | dashboard … board, **atelier**, staff, gateway = **12** | `NAV_LABELS` twelve entries, the atelier label «after «לוח היום» and before «צוות»» — true in *her* list because `floor` is invisible to her |
| shift_manager | the same minus staff + gateway = the first **10** | `NAV_LABELS.slice(0, 10)` |
| seamstress | **«הצוות בקומה» then «תפירה»** = 2 | `reachable[0]?.key` still lands her on `floor` with **no edit** to `useState("dashboard")` |
| reception / sales_assistant | «הצוות בקומה» = 1 | unchanged |

Put `atelier` *before* `floor` instead and the last two rows break together: a seamstress would land on the atelier and `Nav.test.tsx`'s «הצוות בקומה»-first assertion would red. One line, three consequences.

**Zero new `packages/ui` components and zero new variants.** Everything is `Card`, `Badge`, `Button`, `Select`, `Input`, `TextArea`, `DateField`, `Modal`, `EmptyState`, `Skeleton` and the two shipped `lib/` helpers (`isolateLtr` / `isolateBidi` — `lib/booking.tsx:75`, `:101`; `plainDate` / `jerusalemTime` / `todayJerusalem` — `lib/jerusalem.ts`). Checked against the shipped files rather than assumed: `Badge.tsx` exports `danger` (`border-danger text-danger`, **6.18:1 on paper**) which is the overdue treatment, and `muted` which is the unassigned one; `Button.tsx`'s `md` is `min-h-11` (44 px) and `focusRing` is applied unconditionally. **No new colour pair enters the ledger** (§8).

**One length in this deck is not a token, and it is a shipped precedent rather than an invention**: the ≥768 column body's `md:max-h-[32rem]` (§6). `Modal.tsx` already ships `w-[min(28rem,calc(100vw-2rem))]` — a raw `rem` panel length, because no spacing token in `tokens.md` runs past `--space-16` (64 px) and none was ever meant to size a scroll viewport. Stated here so it is a decision with a precedent and not a review finding.

### Binding inheritances (obeyed, not restated)

From **`manage-restyle.md`**: **720 px content cap at every breakpoint** (§6 is where this feature collides with it); the three-register split (an **outage** is `text-ink-muted`, a thing-she-must-fix is `text-danger`, a nothing-failed **notice** is `text-warning-text`); `EmptyState` over a blank column; inline muted cues over Toasts; **no `role="tab"` anywhere**; destructive action = `Button variant="danger"` trigger → `Modal` whose footer is `ghost` dismiss + `danger` confirm; **never override a `packages/ui` component's own utility from the call site** (`cn()` is a plain join and the consumer loses — which is why `Card`'s `p-6` is not touched here either).
From **`tokens.md`**: the gold law (`--color-gold-strong` never carries text — **it appears on this screen zero times**); focus ring on every control; ≥44×44 touch targets; no raw px in app code; `prefers-reduced-motion` is already global in `theme.css`.
From **`shift-board/design.md` Revision 2**: the freshness row is the whole live-ness contract and is **never announced and never `aria-hidden`** (its **F-1**); **the poll may never write into a live region** (its D11); a live region is written **only when its value actually changes** (its **F-7**); a tick may not repaint while a pointer is down (its **F-8**); `{401, 403}` are two terminal states, not one; pause/resume is one button whose **name** changes, never `aria-pressed`; resume fetches immediately at the **base** interval.
From **`floor-staff-roles/design.md`**: status is carried by the **word** and never by the colour; **bare `<bdi>`** on Hebrew free text and `<bdi dir="ltr">` on numeric runs (its **F-11**); the failure-path focus move is the one that gets forgotten; a mutation's 403 is **terminal**, a 404 is an in-card alert (its **P-6**); a surface that has stopped updating must still be able to say so; reuse a key whose **namespace names its subject**, never one whose namespace names a screen (its **F-10**).

### Explicitly NOT here — with the spec's reasons

| Not shipped | Reason |
|---|---|
| **Drag and drop, of any kind, anywhere** | Spec **D16**. Every accessible DnD is a keyboard alternative bolted onto a gesture, so the button path gets built either way; WCAG 2.5.7 requires the single-pointer alternative regardless. §3 is the alternative, and it is the interface. |
| **Capacity, load bars, remaining-hours sorting on the assign picker, overload flags** | F42's, on this payload and this control (§10 **P-8**). |
| **Split load, expedite** | F42's own migration (spec §Out of scope) — two more columns and two more audit actions. |
| **The effort-band settings editor** | F42's (spec D8, Risk 4). F41 **reads** the mapping and ships no writer, which is why §7.2 makes the mapping visible in the picker instead. |
| **Pricing, an ILS amount, an invoice** | Deliberately, per the E9 brief and Interview Q1's money fence. There is no `Price` on this screen. |
| **Photos, measurements as fields** | Deliberately. `notes` is free text and is the one field Risk 8 hands to F20. |
| **The bride's phone on a card** | Spec D6's minimisation: the board is read by a seamstress and there is no surface in F41 that calls anybody. |
| **Fittings, the bride's own view, the shop-floor board, throughput medians** | F43's, F24's, F44's. |
| **A second poll loop** | Spec D12/D15: F42, F43 and F44 extend this payload. One loop per section, forever. |
| **A highlight, shimmer, pulse or flash on a card that moved** | F34's D11 and §9.3. It would fire every five seconds on a shared board. |
| **A stage filter, per-column pagination, a search box** | Spec D12 declines all three: five columns come off one payload, and five requests per tick is what D12 exists to prevent. |

---

## 1. The board — mobile 375, loaded (state **A**)

**375 is the primary case, and on this surface that is not a formality.** Pre-decided #27 puts the console on each staffer's own phone signed in as herself; a seamstress's two rows are «הצוות בקומה» and «תפירה», and this one is where her work is. The owner's 1440 laptop gets the *same* layout, for the reason §6 measures.

⚠ **The diagrams below are drawn LEFT-TO-RIGHT, for legibility in a Markdown file. The rendered section is RTL.** So in the shipped console every run inverts: **inline-start is the physical RIGHT and inline-end is the physical LEFT.** The stage rail reads right-to-left, `intake` first at the physical right; the freshness row's `justify-end` puts the pause control at the physical **left**; a card's overdue `Badge` sits at the physical left of the name. This deck ships **no prototype and no `design-critic` pass** (header), so the ASCII block is the sole visual source — a builder implementing the drawn order ships a mirrored board that passes axe, passes every named vitest assertion, and reads backwards to the only users who will ever see it. The block is not redrawn in RTL because a hand-mirrored ASCII diagram is one more thing to keep true; this paragraph is cheaper and says the same. **The one place it matters most is the rail**, because a pipeline drawn in the wrong direction is a pipeline that says the work flows the wrong way.

```
+--------------------------------------------------+
|  <main #console-main tabIndex=-1, max-w-720px>   |
|                                                  |
|  לוח התפירה                                       |  h2, tabIndex={-1}, --text-lg font-semibold ink
|                        עודכן 14:07  [ השהיה ]     |  FRESHNESS ROW — flex, justify-end,
|                                                  |    NOT announced, NOT aria-hidden (§1.2).
|                                                  |    time in <bdi dir="ltr">, --text-sm ink-muted.
|                                                  |    Pause: Button ghost md, 44px, SC 2.2.2
|                                                  |
|  [ כרטיס חדש ]                                    |  Button primary md — the intake CTA (§7)
|                                                  |
|  <p role="status"> (empty at rest)                |  the ONE announced region (§4.2)
|                                                  |
|  ┌ <nav aria-label="מעבר לשלב"> ─────────────┐    |  THE STAGE RAIL (§1.1) — the pipeline
|  │ [התקבל · 4][בעבודה · 7][בקרה · 2]         │    |    at a glance AND the only way past a
|  │ [מוכן · 3][נמסר · 1]                      │    |    long column at 375. Five <a href="#">.
|  └───────────────────────────────────────────┘    |
|                                                  |
|  <section aria-labelledby="atelier-h-intake">     |
|    <h3 id=… tabIndex={-1}>  התקבל · 4             |  --text-base font-semibold ink
|    <ul aria-label="התקבל" tabIndex={0}>           |  NAMED list — §9.1
|    ┌── li > Card (surface, p-6) ──────────┐       |
|    │ מיכל לוי                  [ באיחור ]  │       |  name: bare <bdi>, font-semibold, break-words
|    │ ולנטינה · 38                          │       |  dress snapshot, --text-sm ink-muted
|    │ יעד 12.7.2026                         │       |  due line — --text-sm, danger when overdue
|    │ שעתיים · נועה                          │       |  effort word · assignee (or «לא משויך»)
|    │ להרים 4 ס״מ, לצרף חגורה                │       |  notes — --text-sm ink, NEVER truncated
|    │ ────────────────────────────────────  │       |
|    │ [   לשלב הבא   ]                      │       |  PRIMARY. Button secondary md (§3.1)
|    │ [ העברה לשלב ▾ ] [ העברה ]             │       |  Select + sibling commit Button (§3.4)
|    │ [ תופרת ▾ ] [ שיוך ]  |  [ לקחת ]      │       |  elevated  |  seamstress (§2.3)
|    │ [ ביטול שלב ] [ עריכה ] [ מחיקה ]      │       |  ghost / ghost / danger
|    └───────────────────────────────────────┘       |
|    …                                              |
|  </section>                                       |
|  <section …in_progress>  … <section …delivered>    |  four more, identical structure
+--------------------------------------------------+
```

- **The ticket is the `Card`; the column is not.** A deliberate inversion of F57's choice (its **P-1** made the panel one `Card` around a `divide-y` list, because at 375 a card and a row inside a card are the same rectangle). Here they are not: the unit of this screen is a *thing that moves between named regions*, and at ≥768 two columns sit side by side where a bare `divide-y` list would read as one continuous list spanning both. So `<section>` → `<h3>` → `<ul className="space-y-3">` → `<li><Card>`. **No `Card` inside a `Card`** — the column has a heading, not a container, which is also what keeps `shadow-sm` from stacking on `shadow-sm`.
- **Order is the server's and the client never re-sorts.** `due_date` ASC, `created_at` ASC, `id` ASC (spec D12) — the bride-date rank pre-decided #40 fixes, and the `id` tiebreak is what stops cards shuffling between ticks when several were seeded in one transaction. The console does not add a secondary sort, does not group, and does not hoist her own tickets (§10 **P-4**).
- **The `Card`'s `p-6` is not overridden**, and neither is `Badge`'s or `Button`'s (`cn()` is a plain join — `manage-restyle.md`).
- **No aggregate «12 כרטיסים פתוחים» line.** The rail already carries five counts; a sixth number that is the sum of five visible numbers is a second thing to keep true. §10 **P-3**.

### 1.1 The stage rail — the pipeline at a glance, and the only way past a long column

**Five in-page links, in stage order, each carrying the stage word and that column's count.** `<nav aria-label={t("atelier.railAria")}>` → `<ul className="flex flex-wrap gap-2">` → `<li><a href="#atelier-h-{stage}">`.

It does two jobs, and it exists because §6's arithmetic takes away the one that a five-across board would have done for free:

1. **It is the overview.** «התקבל · 4 · בעבודה · 7 · בקרה · 2 · מוכן · 3 · נמסר · 1» on one line at 375 is the whole pipeline state — which five 128 px columns could never have shown, and which a sighted user of a real five-across board gets by scanning column heights. It is the kanban's actual value delivered in five chips.
2. **It is the skip mechanism.** A stacked board whose `intake` column holds twenty cards puts `delivered` twenty cards down the page. The rail is what makes the fifth column one activation away at every width.

**Zero new mechanism.** They are plain `<a href="#id">` anchors, and the targets are the column `<h3 tabIndex={-1}>`s **that D16 already requires for the delete focus move**. Fragment navigation to a `tabindex="-1"` target focuses it — which is exactly how `ConsoleShell`'s shipped `SkipLink` reaches `#console-main` (`ConsoleShell.tsx:84`, `tabIndex={-1}`). So the rail moves focus *and* scroll with no JavaScript, no `scrollIntoView`, no focus code and no test of its own beyond "activating a rail link focuses that heading".

- **The counts are the same numbers as the headings, computed once** from the grouped payload and passed to both. Two renderings of one array, not two sources.
- **A rail chip for an empty column still renders, reading «בקרה · 0»**, and still links. Hiding it would make the rail's length change under a repaint — the pipeline is five stages whether or not a boutique is using all of them today, and a chip that vanishes is a control that moves under a finger (F34's **F-8**).
- **It is a `<nav>` with a label, not a bare list of links.** An unnamed second navigation landmark beside the shell's is the same defect §9.1 argues against for the columns: a screen-reader user cycling landmarks lands on two things both called "navigation".
- **On the EMPTY board the rail does not render** (§5, state **A-empty**) — five chips reading zero is a wall of zeros, which is precisely the "looks broken" failure the empty state exists to avoid.

### 1.2 The freshness row — inherited whole from F34 and F57

Two things on one line, never announced, never `aria-hidden`:

| Element | Content | Register | Why |
|---|---|---|---|
| inline-end | `atelier.updatedAt` → «עודכן 14:07»; `atelier.staleAt` when a tick failed; `atelier.pausedAt` when the loop is stopped | `--text-sm --color-ink-muted`, escalating to `--color-warning-text font-semibold` in the stale **and** paused cases | The freshness claim, changing **only on a successful fetch**. The escalation is F34's **P-6**: correct-looking cards beside a grey notice are what gets scanned past |
| inline-end, after the time | the pause / resume control — `atelier.pause` «השהיה» ⇄ `atelier.resume` «חידוש» | `Button variant="ghost" size="md"` | **WCAG 2.0 SC 2.2.2 (Level A)**, spec **D17**. §9.4 |

**One slot, three reasons the board might not be current, F34's precedence order unchanged**: terminal (the board is gone) > paused/idle («מושהה · עודכן») > stale («אין עדכון מאז») > running («עודכן»). A stopped loop cannot fail a tick, so the stop is the cause in force and the resume control is the remedy — which is also what keeps «רענון» and «חידוש» off one line.

**This is the third pause control in the console and the copy is what keeps the three apart.** `board.pauseAria` «השהיה — עדכון הלוח» and `floor.pauseAria` «השהיה — עדכון הצוות» ship; `atelier.pauseAria` is «השהיה — לוח התפירה». **`atelier.idleStopped` may not be byte-identical to either of the other two** (F57's **F-4**, generalised): all three write into a `role="status"` region and all three idle windows are reset by the same global `pointerdown`/`keydown`/`focusin`/`scroll` listeners (`usePoll.ts`, the idle effect), so a user who has both a board and this section open in a session hears the same sentence from two regions with nothing naming which stopped. This section is never co-visible with the other two (the console renders one section at a time), which makes the collision rarer here than F57's — and the string still names its own region, because the reason is a rule and not a coincidence.

---

## 2. The ticket card — anatomy, the truncation rule, and the control matrix

### 2.1 What a card shows, top to bottom

Content width is **295 px at 375** (375 − 2×`--space-4` shell gutter = 343, − 2×`--space-6` `Card` padding = 295) and **288 px at ≥768** (§6). Seven pixels apart, so the card is measured once and holds at both — which is the whole reason §6 does not ship a second card design.

| Slot | Content | Bidi | Notes |
|---|---|---|---|
| Name row | `customer_name` + the overdue `Badge` when overdue | **bare `<bdi>`** on the name | `font-semibold text-ink break-words`. `dir="ltr"` on «מיכל לוי» reverses its words and *looks deliberate* (`lib/booking.tsx:101`'s own comment). `flex-wrap` so a long name pushes the Badge to the next line rather than squeezing it |
| Dress line | `dress_name` + « · » + `dress_size`, **omitted entirely when both are null** | bare `<bdi>` on the name; `<bdi dir="ltr">` on a size that is a bare number | `--text-sm --color-ink-muted break-words`. An alteration on the bride's own gown has no catalog row (spec D6), so absence is normal and is not rendered as an empty slot |
| Due line | `atelier.dueDate` → «יעד 12.7.2026» via `plainDate` | `<bdi dir="ltr">` on the date | `--text-sm --color-ink`, escalating to `--color-danger font-semibold` when `overdue`. **Always present** — it is the priority key the whole epic subtracts from |
| Effort + assignee | the band word (or the minutes fallback) + « · » + the seamstress's name, «לא משויך», or «תופרת שאינה פעילה» | bare `<bdi>` on her name | `--text-sm --color-ink-muted`. One line, because two facts of one word each do not each earn a line in 295 px |
| Notes | `notes`, verbatim | bare `<bdi>` | `--text-sm --color-ink`. **Never truncated** — §2.2. Absent when null |
| Controls | §2.3's matrix, each on its own row or paired with its commit button | — | separated from the text block by `--space-3` and nothing else; no divider, no second `Card` |

**The stage is NOT on the card.** It is the column heading, which is the whole point of a board — and repeating it per card is 295 px spent saying what the region already says, plus a second place to keep true. This is F57's **F-3** ruling («מאז 11:20», not «בהפסקה מ־11:20») arriving at a different fact.

### 2.2 The truncation rule — identifiers and instructions are never truncated, and nothing else is long

**Nothing on this card is truncated, clipped, ellipsised or line-clamped.** Stated as a rule because the question has three different-looking answers on one card and they resolve to the same one:

- **A 60-character dress name** (`MAX_DRESS_LABEL_LENGTH` = 200) wraps with `break-words`. `FloorPanel`'s shipped rule for display names applies unchanged: *a board that abbreviates two garments into the same string is worse than a tall card.* «ולנטינה» and «ולנטינה — גרסת ערב» must not both render as «ולנטינה…».
- **A customer name** is the same argument about a person.
- **`notes` up to `MAX_TICKET_NOTES_LENGTH` (500)** is the one that looks like it wants a clamp, and it is the one where a clamp does the most damage. The note **is the instruction** — «להרים 4 ס״מ, לצרף חגורה» — and this board is the surface the seamstress reads it on. Clipping it would put the work order behind «עריכה», a control **a seamstress may not use on a ticket that is not hers** (spec D3's per-verb table). A clamp would therefore hide the instruction from precisely the person doing the work.
- **The ceiling is named rather than engineered away**: a boutique that writes essays into `notes` gets tall cards. The remedy is a shorter note — and the intake form's `TextArea` ships `showCount` with `maxLength={500}` (§7.1), so the length is visible at the moment it is chosen rather than discovered on the board. If a pilot shows real essays, the cheap fix is a `line-clamp-3` **plus** a per-card disclosure, and that is a control this deck deliberately does not add on speculation (**F-6**).

### 2.3 Which controls exist — the two authorization axes, rendered

The board renders **only the operation the server will accept** (the F15 discipline: *"rendering four buttons where three answer 409 is a trap; a disabled button with no explanation is worse than an absent one"*). **Which control exists is cosmetics and the frontend test asserts it as cosmetics** — the server's D3/D9/D10 checks are the control.

| Control | Variant | Rendered when | Absent when |
|---|---|---|---|
| «לשלב הבא» | `Button secondary md` | always, for all three roles on a ticket a seamstress may advance (hers or unassigned) | the stage is `delivered`; a seamstress on **another seamstress's** ticket |
| «העברה לשלב» + «העברה» | `Select` (`min-h-11`) + `Button secondary md` | the same rule, **and only when ≥2 later stages exist** | the stage is `ready` or `delivered` — with one later stage the skip control offers exactly what «לשלב הבא» already does |
| «ביטול שלב» | `Button ghost md` | the same rule | the stage is `intake` (spec D4: `intake` cannot be undone) |
| «תופרת» `Select` + «שיוך» `Button` | `Select` (`min-h-11`) + `Button secondary md` | **owner / shift_manager only** | a seamstress sees the pair below instead |
| «לקחת» / «לשחרר» | `Button secondary md` / `Button ghost md` | **seamstress only** — «לקחת» on an unassigned ticket, «לשחרר» on one assigned to her | a seamstress on another's ticket: neither |
| «עריכה» | `Button ghost md` | owner / shift_manager on any ticket; a seamstress on **her own** ticket only | a seamstress on an unassigned or another's ticket |
| «מחיקה» | `Button danger md` → confirm `Modal` | **owner / shift_manager only** (spec D10's per-route tightening) | seamstress, always |

**What a seamstress sees on a colleague's ticket: the facts, and no controls at all.** No disabled buttons, no lock glyph, no «אין לך הרשאה» line. The same three reasons as every other time this question comes up in this codebase: a disabled control with no explanation is worse than an absent one; an explanation would teach the permission model on a screen she opens fifty times a shift, to answer a question she did not ask; and any such affordance would be the client asserting a rule the server owns.

**«לשלב הבא» is `secondary` and everything reversible is `ghost»`**, matching F34's check-in/undo pair and F57's «להפסקה»/«חזרה» pair exactly. Advancing is the ordinary forward act and gets the ink boundary that makes a target findable in a scan; undoing is the return to normal and is demoted but never hidden. **«מחיקה» is the only `danger` on this screen**, and it is the only irreversible act on it (spec Risk 6: there is no un-delete).

**`size="sm"` is barred on this surface, and it is barred *because* of this table.** `Button.tsx`'s `sm` is `min-h-9` = 36 px, under the 44 floor, and a card carrying up to seven controls in 295 px is exactly the layout in which someone reaches for `sm` to make it fit. The answer is that the card is tall, not that the targets are small — this console runs on staff phones. Asserted as a rendering check (spec's acceptance list), because **axe has no target-size rule at the level this repo runs it**.

### 2.4 An overdue card

| Signal | Treatment | Why |
|---|---|---|
| The `Badge` | `Badge variant="danger"` carrying **«באיחור»** — a word, in the name row, at the inline-end | `border-danger text-danger`, **6.18:1 on paper** (tokens ledger). The E9 Risks name colour-only urgency as this epic's hard accessibility case; the word is the signal and the border is reinforcement |
| The due line | «יעד 12.7.2026» escalates to `--color-danger font-semibold` | The **second** text signal, and the one that says *how* late. `--color-danger` on paper is 6.18:1 as text; `font-semibold` is the non-colour half |
| The card | **nothing.** No red border, no tint, no left rule, no icon | A card whose whole rectangle is coloured is the colour-only signal wearing a costume, and on a 60-card column it is a wall of red that stops meaning anything |

**A delivered ticket is never overdue.** `overdue` is `delivered_at IS NULL AND due_date < today_jerusalem` (spec D5) — a garment delivered late is a fact about the past, not a thing to chase, and the `delivered` column carrying five «באיחור» badges would be a receipt scolding the boutique for work it finished.

---

## 3. ⚠ THE ACCESSIBLE MOVE — the whole a11y payload of D16's no-drag decision

**There is no drag affordance on this board at any width, and the button path is not a fallback — it is the interface.** Spec D16's argument in one line: every accessible drag-and-drop is a keyboard-and-screen-reader alternative bolted onto a pointer gesture, so the button path gets built either way, and WCAG 2.5.7 requires the single-pointer alternative regardless. What follows is what gets built instead.

### 3.1 The primary path — one control, one tap, one stage

**«לשלב הבא» advances to the immediately next stage in `STAGE_ORDER` after the card's current one.** It is the 90 % case: a garment moves forward one stage at a time, and the whole interaction is *find the card, activate one button*. It is first in the card's tab order, it is `secondary` (the only bordered control on the card), and it is the same physical position on every card in every column.

**The skip control is secondary in every sense.** «העברה לשלב» offers **only** the stages strictly later than the current one — a backwards option is never rendered, so D3's 409 is a race guard rather than a routine refusal — and it renders **only when two or more later stages exist**, because with exactly one the skip control and «לשלב הבא» do the same thing and a board that offers one act twice is a board that has to be read twice.

### 3.2 ⚠ NOTHING ON THIS BOARD MUTATES ON `change`

This is the one interaction rule a builder will get wrong by copying the obvious thing, and it is why both `<Select>`s have a sibling commit `Button`.

**On Windows Chrome and Firefox a *closed* native `<select>` changes its value and fires `change` on every arrow keypress.** A keyboard user on an `in_progress` card arrowing down to «נמסר» would fire three separate advances — `qc`, `ready`, `delivered` — writing three timestamps, three `ATELIER_TICKET_STAGE_ADVANCED` audit rows, moving the card across three columns and firing §3.3's focus move three times, **before she had committed to anything**. Under spec D2 those stamps *are* the trail, and under D4 each needs its own undo call to reverse.

That is **WCAG 3.2.2 On Input (Level A)**, inside the AA bar pre-decided #38 makes legally binding, it falsifies this feature's own "fully operable with no pointer" criterion, and it would be the **first `<Select>` in this console to mutate on change** — every shipped one sets draft state and nothing else (`StaffSection.tsx:236-250`, `:375-384`, both of which set a draft object and issue no request).

So: **the `Select` sets per-card draft state; the sibling `Button` issues the request and is `disabled` until the draft is non-null.** Both selects, same shape. The named vitest mutation is *move the request back into the select's `onChange`* — and it must red both pairs.

### 3.3 ⚠ WHERE FOCUS GOES — FIVE destinations, and the fifth is a spec gap this deck opens (F-1)

**A successful advance moves the card to a different column. The tapped control therefore unmounts and the browser drops `document.activeElement` to `<body>`.** On this surface that is not a side effect of `Button` being `disabled={disabled || loading}` — **it is what the feature does**. This bug class has now shipped three times in this repo (F56 on the storefront, F34 on the board, F57 on the floor panel) and **axe walked past it every time, because axe cannot see a focus move that never happened.**

Every rule below is keyed on **state**, never raised inside the handler — the destination node does not exist yet when `setState` runs (`FloorPanel.tsx:220-236` is the shipped shape for exactly this).

| # | Trigger | Destination | Mechanism |
|---|---|---|---|
| **1** | **Advance / skip / undo succeeded** | the **same ticket's** «לשלב הבא» control **in its new column** | a `Map` ref keyed by `data-ticket-id`, which survives the move — a lookup, not a search. Focusing it scrolls it into view natively, so the stacked layout needs no scroll code |
| **1b** | …and the destination card has **no** «לשלב הבא» (it landed on `delivered`, or she is a seamstress who may not advance it further) | the **destination** column's `<h3 tabIndex={-1}>` | F51's shipped stranded-focus pattern, and it needs no new string. **"Destination", not "origin"** — that is where the card now is and where she continues from |
| **2** | **Any mutation failed** (409, 404, 400) | the **in-card alert** (`role="alert" tabIndex={-1}`), `text-danger` | keyed on the error state. **The failure path is the one that gets forgotten**: F34's success path compensated and its catch path restored nothing, and that was a Level A defect found in review, not in CI |
| **3** | **A successful poll unmounts the focused in-card alert** | back to that card's own control | `reclaimFocusRef` (`FloorPanel.tsx:118-131`). Easy to miss because the alert is cleared **about five seconds later with no user action at all**, and the departing-card rescue cannot cover it — the card is still in the list |
| **4** | **A successful DELETE** | the departing card's **own** column `<h3 tabIndex={-1}>` | the card is gone entirely, so the ref map has nothing to look up. `departingCardHoldsFocus` (`FloorPanel.tsx:39`, `:252-266`) pointed at a heading. Without it, deleting the focused card drops focus to `<body>` on the single most destructive action in the feature |
| **5** | ⚠ **A POLL moved the focused card, because a COLLEAGUE advanced it** | the **same ticket's** control in its **new** column; if the ticket is gone from the payload entirely, its **old** column's `<h3>` | **NOT IN THE SPEC — F-1.** Five columns are five `<ul>`s, so a card changing stage **unmounts from one list and mounts in another**. Focus is lost with no user action at all, five seconds after a colleague tapped a button on a different phone. Same class as #3, different trigger, and #3's `reclaimFocusRef` does not fire because the card did not vanish and no alert is involved |

**Rule #5 is the finding this deck exists to have caught**, and it needs one comparison the load path already has both halves of: before applying an incoming payload, if `document.activeElement.closest("[data-ticket-id]")` names a ticket whose incoming `stage` differs from its current one, record the id and re-focus its control after the paint. `FloorPanel`'s `departingCardHoldsFocus` is the same shape asking a different question, and it already runs *"decided BEFORE the new list is applied — the only moment both lists exist"* (`FloorPanel.tsx:104-107`). One named, non-vacuous vitest test, whose mutation is deleting the capture.

**Each of the five gets a test that asserts `document.activeElement` IS the expected node** — never merely that the node exists. F57's shipped note records a success-path focus test that was **vacuous** because jsdom does not blur a disabled element, so the whole restore effect could have been deleted with the suite green.

### 3.4 What a keyboard-only pass across the board looks like

Tab order, top to bottom, exactly once:

```
skip link → header logout → shell nav buttons → #console-main
  → pause / resume               (FIRST inside the section — §9.4)
  → «כרטיס חדש»
  → rail: 5 links                (each jumps to and focuses a column heading)
  → per column, in stage order:
       the <ul> itself           (tabIndex={0} — §6, the scrollable-region rule)
       per card: לשלב הבא → העברה לשלב → העברה → [תופרת ▾ → שיוך | לקחת/לשחרר]
                 → ביטול שלב → עריכה → מחיקה → (the in-card alert, when present)
  → the retry button when present
```

**The rail is what makes this tolerable.** Without it a keyboard user reaching the `delivered` column tabs through every control of every card in four columns first — on a 60-card `intake` that is upward of two hundred stops. With it, five links get her to any column heading, and the `<ul>`'s own tab stop gets her into it.

---

## 4. The poll, made visible

### 4.1 What the user sees on a tick

| Tick outcome | What changes on screen | Announced |
|---|---|---|
| **Nothing changed** (the common case) | the «עודכן HH:MM» time, and nothing else | nothing |
| A colleague advanced a ticket | the card leaves one `<ul>` and appears in another; both `<h3>` counts change; both rail chips change | **nothing** — §4.2 |
| A colleague claimed / released a ticket | the effort+assignee line changes in place | nothing |
| A colleague opened a ticket | a card appears in `intake`, positioned by `due_date` | nothing |
| A colleague deleted a ticket | its card leaves — **unless it holds focus** (§3.3 #5) | nothing |
| A ticket became overdue at Jerusalem midnight | the `Badge` appears and the due line escalates — the server recomputes `overdue` per read (spec D5), so the board rolls itself | nothing |
| The fetch failed | the freshness row flips to **A-stale**, and the next retry is further away than the last | nothing |
| The fetch succeeded after failures | the stale copy clears and the interval resets to the base | nothing |
| The fetch answered **401** | the loop stops; `atelier.sessionEnded` replaces the board | **yes** — `role="alert"` |
| The fetch answered **403** | the loop stops; `atelier.accessEnded` replaces the board | **yes** — `role="alert"` |

**No highlight, no fade, no colour wash on a card that moved.** F34's D11, and it is *more* load-bearing here than there: a card changing column is already a large visual event, and a highlight that can fire every five seconds on a shared board is a strobing screen for a whole shift. It also draws the eye to *what changed* when the question this board answers is *what is late*. `prefers-reduced-motion` falls out of the same rule for free.

### 4.2 ⚠ The live region under a 5-second poll — what counts as MEANINGFUL

**The poll never writes into an aria-live region.** F34's D11, verbatim and non-negotiable. The announced region carries **only user-initiated outcomes**: the create cue, the advance cue, the undo cue, the assign cue, the release cue, the delete cue, the pause, the idle stop, and the first-load `atelier.loading`.

**And the case this rule is hardest on is the one the board is built for: another staffer moves a ticket while you are looking at it.** It is a genuinely meaningful change — the pipeline state changed, and a sighted user sees it — and it is **still not announced.** The reasoning, stated in full because it is the one place a reviewer will push:

1. **A shared board's remote changes are not the reader's outcomes.** On a 60-ticket board with four staffers working, announcing every remote move is a `role="status"` that talks continuously for a whole shift — the auditory form of the highlight this deck already declines. There is no threshold that fixes it: one move per minute is still one interruption per minute, forever, for a fact she did not ask about.
2. **"Meaningful change" is not a property of the data, it is a property of the *user's* relationship to it.** The only remote change that is meaningful to *this* user is one that happens to the card **she is standing on**, and that case is handled — by moving focus (§3.3 #5), which announces the control she landed on.
3. **The place a remote move actually needs to reach her is the moment she acts on stale information**, and it does: her advance answers **409** with copy that names the event — «הכרטיס כבר התקדם. הלוח יתעדכן בעדכון הבא.» — into a `role="alert"` that also takes focus (§3.3 #2). That is one announcement at the one moment it changes what she does, instead of a hundred that do not.
4. **The freshness line is the standing honesty signal**, it is readable, it is **not `aria-hidden`** (F34's **F-1**), and a screen-reader user can read «עודכן 14:07» whenever she wants to know how current the board is.

**And "write" means write, not change.** Assigning a non-empty string to a text node runs the DOM's string-replace-all and produces a real `childList` mutation inside `role="status"` **even when the two strings are byte-identical** (F34's **F-7**). The cue is written **only when its value actually changes** — `setCue` with an equal value is a React no-op, so the guard is the `setState` itself — and the test must drive **several consecutive ticks with the cue already populated**, because a single-tick assertion passes against the broken version whenever the cue starts empty.

### 4.3 The six failure modes are `usePoll`'s, and this section adds none

The single arming site, the `document.hidden` gate plus the `visibilitychange` immediate refetch, the 5 s → 60 s backoff with reset on first success, the `{401, 403}` terminal classification, the idle stop, and the monotonic generation behind `isCurrent` all come from the hook (`lib/usePoll.ts`) and are not re-derived. **Two shipped fixes come with it and this section must not defeat either**: the unmount fix (`runningRef.current = false` **before** `clearTick()` in the mount effect's cleanup) and the StrictMode-idempotent mount effect (`runningRef.current = true` as its **first** line). Both are one line, both are inside the hook, and this section's whole obligation is to import it unmodified.

Four things are the **caller's** and this section must write them:

1. **The pointer hold** — `pointerdown` holds the next repaint, `pointerup`/`pointercancel` releases, `run` returns `"held"`. It matters more here than on the floor panel: a card changing column is a **layout** change under a travelling finger, not a text swap, and it can move every card below it in two columns at once.
2. **`mutationsRef` → `"suppressed"`**, with the single re-arm in the mutation's own **`.finally()`** and never its success path, so a refused advance does not park the loop.
3. **`poll.bump()` before every mutation**, so the one poll still in the air is discarded.
4. **`poll.fail(error)` in every mutation's `catch`**, which is what makes a mutation's 403 terminal on the same `{401,403}` rule the ticks use (F57's **P-6**). A 404 is **not** terminal — a ticket vanishing is a fact about the ticket, not about her access.

**Never optimistic.** Every mutation answers the full ticket and the card is patched from the server's row (spec D15), so the console cannot disagree with itself — and on a 200 no-op that renders the **first** actor's timestamp rather than this request's intent.

---

## 5. States — the single source for this feature

**The list may not shrink.** Every state the spec's §Every state of every surface names is here; the ones this deck adds by decomposition are marked ✚ and none is optional.

| # | State | Trigger | What she sees | Region / focus |
|---|---|---|---|---|
| **A-load** | First load | section opened | `h2` + one `Card` with `<Skeleton variant="text" lines={3} />`. **No freshness row and therefore no pause control** — nothing is auto-updating yet, and a control over a skeleton pauses a fetch the user has not seen produce anything. No rail (there are no counts yet) | the cue carries `atelier.loading`, so loading **is** announced |
| **A** | Loaded | 200, ≥1 ticket | §1 — freshness row, CTA, cue, rail, five named sections | nothing announced |
| **A-empty** | **A brand-new boutique** | 200, `tickets: []` | The five columns **and the rail** are replaced by one `<EmptyState>`: title «אין עדיין כרטיסי תפירה», a body that **teaches the five stage words in one sentence**, and the «כרטיס חדש» CTA as its `action`. **The freshness row still renders above it** — a surface that has stopped updating must still be able to say so. §10 **P-2** is why this is not five empty columns | nothing announced |
| **A-emptycol** ✚ | One column empty, board not | 200 | A muted «אין כרטיסים בשלב זה» **inside** the column, and the rail chip reads «· 0». The four other columns are the context that makes an empty one legible rather than broken | — |
| **A-fail** | **First** fetch failed | non-2xx / network on the initial load | `<p role="alert" className="text-sm text-ink-muted">` `atelier.loadFailed` — the **outage** register — plus a «רענון» `Button secondary md`. **The freshness row and its pause control DO render**: the loop is alive and backing off, so a viewer who wants it to stop must be able to stop it | alert |
| **A-stale** | A poll failed **with cards on screen** | non-2xx / network on any later tick | **The cards stay.** The inline-end flips to `atelier.staleAt` in `--color-warning-text font-semibold`, a second `--text-sm` line carries `atelier.staleBody` + «רענון». **Nothing on screen states the interval and nothing may** — the backoff falsifies any number the moment it doubles | **not announced.** Blanking correct data to report a network fault is worse than the fault |
| **A-paused** | She pressed «השהיה» | a tap on §1.2's control | The loop stops. **The cards stay and are not dimmed** — they were correct at «עודכן 14:07» and pausing did not make them wrong. Inline-end becomes `atelier.pausedAt`; under it, `atelier.paused`. The control reads «חידוש». **No «רענון» in this state** — «רענון» beside «חידוש» is two Hebrew words a hurried reader will not tell apart | **announced once**, `role="status"`. **Focus stays on the control** — it renamed, it did not unmount |
| **A-idle** | The idle timer fired | 10 min with no interaction (`IDLE_STOP_MS`) | Mechanically identical to **A-paused**. **One thing differs and it is why there are two states**: the body line is `atelier.idleStopped`, which names the cause **and its own region** (§1.2) — a board that stopped by itself and does not say why is indistinguishable from a board that broke | **announced once**. Focus is wherever she left it: the timer fires precisely because she was not touching anything |
| **A-401** | Session ended | any tick or any mutation answers 401 | The loop stops. The board is replaced by `<p role="alert">` `atelier.sessionEnded` + «רענון הדף». Cards cleared: a dead session cannot vouch for them | `role="alert"`, once — the loop has stopped, so it cannot repeat |
| **A-403** | Access ended (a mid-shift role change, **or a refused mutation**) | any tick or any mutation answers 403 | Identical shape, **different sentence**: `atelier.accessEnded`. Cards cleared for a second reason 401 does not have — the board is exactly what she may no longer see. **Generic by design; it may not name a role** | `role="alert"`, once |
| **A-trunc** ✚ | The 500-ticket cap was hit | 200, `truncated: true` | One `--text-sm --color-warning-text` line above the rail: the board is showing the most urgent tickets and some are not here. **The console never states the number** — `BOARD_TICKET_LIMIT` is server-only and the flag is on the wire precisely so it stays that way | not announced |
| **A-busy** ✚ | A mutation in flight | a control activated | **that control only**: `loading` on the shipped `Button` (spinner overlaid, label kept for width, `aria-busy`). Every other card's controls stay live. **The poll does not tick while a mutation is in flight**, so the card cannot be repainted under the request | nothing announced yet |
| **A-ok** ✚ | A mutation succeeded | 200 | the card is patched **from the response** (the full ticket), so the board cannot disagree with itself. On a stage change the card moves column, both `<h3>` counts change, both rail chips change | cue is `role="status"`; **focus per §3.3** |
| **A-noop** ✚ | A repeat advance / repeat claim | 200, nothing written | **Identical to A-ok**, deliberately. The server keeps the first timestamp and the card renders it; the cue still confirms. The outcome she wanted is the outcome that holds (spec D3's middle row) | as A-ok |
| **A-conflict** ✚ | 409 `TICKET_STAGE_CONFLICT` / `TICKET_ALREADY_ASSIGNED` | the ticket moved, or a colleague claimed it, between the last tick and the tap | `<p role="alert" tabIndex={-1} className="text-sm text-danger">` **inside that card**, under the controls — a board-level error names no ticket. Two different sentences, because the user's next move differs: a garment moved on (look again) vs. a person took it (the next tick will name her) | alert, **focused** (§3.3 #2) |
| **A-gone** ✚ | 404 `NOT_FOUND` | a mutation on a ticket deleted in the gap between the tick and the tap (or, indistinguishably, another tenant's id) | the same in-card alert, `atelier.error.notFound`. The next tick removes the card. **Not terminal** | alert, focused |

**The intake / edit `Modal` and the delete confirm `Modal` carry their own state tables** — §7.3 and §7.4. A dialog is a surface.

**State precedence.** A mutation's response is always the truth for its card (it *is* an `AtelierTicket`). A poll's response is always the truth for everything else. They cannot fight: the loop does not tick during a mutation (`mutationsRef` → `"suppressed"`) and the mutation bumps the generation on settle.

---

## 6. ⚠ Breakpoints — 375 / 768 / 1440, and why there is no five-across view at ANY width

**This is the decision this deck exists to make, and it is arithmetic, not taste.**

`ConsoleShell` caps content at **720 px**, and it does so in **three** places, not one: the header (`ConsoleShell.tsx:46`), the nav (`:56`) and `#console-main` (`:84`), each `mx-auto max-w-[720px] px-4`. `manage-restyle.md` states the cap as binding at every breakpoint and every one of the console's twelve shipped sections obeys it.

**Five columns inside that cap:**

```
720 − 2 × --space-4 (px-4)          = 688 px of content
688 − 4 × --space-3 (gap-3, 12 px)  = 640 px of columns
640 ÷ 5                             = 128 px per column
128 − 2 × --space-6 (Card p-6)      =  80 px of card content
```

**80 px.** A `Badge` reading «באיחור» at `text-xs px-2` is ≈ 52 px. A `Button size="md"` reading «לשלב הבא» is ≈ 92 px of text plus `px-4` — it **overflows the column it is inside**. «תופרת שאינה פעילה» is four words in 80 px. The five-across board is not tight at 1440; it is impossible at 1440.

**Lifting the cap is not a prop, it is a console redesign, and this feature does not get to make it.** The tempting fix is a `wide` flag on `ConsoleShell` — except the cap is on the header and the nav too, so lifting only `main` puts a 1200 px board under a 720 px nav and a 720 px logout row, which is visibly broken. Lifting all three changes the shell for the twelve sections that were designed against 720 px of form width. That is a design-system decision above this feature, its natural owner is **F42's capacity matrix** (a seamstresses × load grid has the same problem and a stronger claim to it), and it is recorded as **F-2**.

So:

| Width | Layout | Arithmetic | Why |
|---|---|---|---|
| **375** (primary) | **One column.** The five `<section>`s stack in stage order, full width. The rail is the navigation between them. Column bodies are **not** height-bounded — the page scrolls naturally | 375 − 32 = 343 shell → `Card` content **295 px**, identical to F57's measured card | A phone shows one column of anything. Nested scroll containers on touch are a scroll-trap for the sake of a viewport that has no second column to align to |
| **768** | **Two columns** (`md:grid-cols-2 md:gap-4 md:items-start`), stage order reading RTL across then down: `intake`/`in_progress` · `qc`/`ready` · `delivered`/— . Each column body gains `md:max-h-[32rem] md:overflow-y-auto` | 688 − 16 = 672 ÷ 2 = 336 → `Card` content **288 px**, 7 px from the 375 measurement | Two columns halve the vertical run on a tablet, and 336 px is the widest column the cap permits that still fits the card measured once. The bound is what makes the grid honest: CSS grid rows are as tall as their tallest item, so an unbounded 60-card `intake` would push `qc` and `ready` sixty cards down and undo the whole benefit |
| **1440** | **Identical to 768.** The console never exceeds 720 px of content and this section is not the exception | — | A wall-mounted workshop display is not this feature — it is **F44's**, which is the right place for a layout that owns its whole viewport |

**⚠ The bounded column body forces one attribute, and axe has a rule for it.** A `overflow-y: auto` container must be reachable by keyboard — axe's **`scrollable-region-focusable`** fires on exactly this. The remedy is `tabIndex={0}` on the scrolling `<ul>`, and it is applied **unconditionally**, at every width, not just where the `md:` classes bite: the alternative is a resize observer deciding an ARIA-relevant attribute, which is a mechanism to keep true for a tab stop that costs nothing. It is also *useful* — it gives a keyboard user a stop at each column heading's list, which §3.4's tab-order table depends on. A named `<ul tabIndex={0} aria-label="בעבודה">` announces «בעבודה, רשימה, 4 פריטים» when focused.

**32 rem, not a viewport unit.** `md:max-h-[70vh]` would give a landscape phone-tablet a 200 px window and a tall desktop a 900 px one — the same class carrying two different designs. `32rem` ≈ 512 px ≈ three cards, is stable across viewports, and honours `:root[data-a11y-text-size]`'s 1.2 rem root scaling for free (a user who scales text up gets a proportionally taller column, not a tighter one).

**The 375 name-wrap case, unchanged from F57**: a long customer name wraps and pushes the overdue `Badge` to the next line — `flex-wrap` on the name row, `break-words` on the name, **no truncation and no ellipsis anywhere** (§2.2). The card has vertical room it does not have horizontal room.

---

## 7. Intake and edit — the `Modal`, and the five effort bands as a real control

### 7.1 The form

One `Modal` serves both, in create mode and edit mode, opened by «כרטיס חדש» above the columns or by «עריכה» on a card. `Modal.tsx` is the native `<dialog>`: free focus trap, top-layer stacking, Esc-dismisses-never-confirms, and **focus returns to the trigger by itself** — so **no focus code is written here at all**, stated so the fourth `usePoll` consumer does not re-derive it. Panel width is `min(28rem, 100vw − 2rem)` = **448 px max, 343 px at 375**.

| Field | Control | Rules |
|---|---|---|
| `customer_name` | `Input` | Required, ≤ 80. **Create mode only** — in edit mode the customer renders as a static line, because *a ticket opened for the wrong bride is a delete, not an edit* (spec's `UpdateTicketRequest`) |
| `customer_phone` | `Input` `type="tel"` `inputMode="tel"` `dir="ltr"` | Required, `normalize_israeli_mobile`. Create mode only. **Once it parses, the returning-customer notice appears beneath it** — §7.3 |
| `due_date` | **`DateField`** (`<input type="date">` — the platform feature, no picker library) | Required. Defaults to **empty, never to today**: a due date is the one field a hurried user must not be able to accept by not looking at it. **No `min` attribute** — a past date is a 200 on the server (spec D5) and a warning here |
| `effort_band` | `Select` of five | Required, defaults to **`one_hour`** — the middle-low band. A default of `full_day` inflates every estimate and `thirty_min` deflates it. §7.2 |
| `dress_id` | `Select` of the tenant's live dresses + a «לא מהקטלוג» option | Optional. Choosing «לא מהקטלוג» reveals the free-text `dress_name` `Input`; choosing a dress hides it, because the server copies the name and the client must not send one |
| `dress_name` | `Input` | Revealed only by «לא מהקטלוג». ≤ 200 |
| `dress_size` | `Input` | Optional free text, ≤ 40. **Not validated against `dress_variants`** — a seamstress records what she measured, not a stock bucket |
| `notes` | `TextArea` `showCount maxLength={500}` | Optional. `showCount` is the shipped counter and it is what makes §2.2's "no clamp on the board" honest: the length is visible where it is chosen |

**Footer**: `ghost` dismiss + `primary` confirm, the shipped `Modal` footer shape. The confirm carries `loading` while submitting (which also disables it); **the fields stay enabled**, so a slow network does not eat a correction.

**A past `due_date` is a WARNING and never a block.** `--color-warning-text --text-sm` beneath the field, present the moment the date resolves to earlier than `todayJerusalem()`. Pre-decided #40's advisory rule, and **the server agrees** — no lower bound, 200 on create and on update. *A dress that was due yesterday is exactly the ticket a boutique most needs to open*, and a form that refuses it sends the seamstress to WhatsApp.

### 7.2 ⚠ The five bands, and what they look like before a tenant has configured the mapping

**There is no unconfigured state, and that is a design consequence of spec D8 rather than an accident.** The board payload carries `effort_bands[]` resolved **per band** against platform defaults (30 / 60 / 120 / 240 / 480), so a brand-new boutique, a boutique with a partial mapping and a boutique with a corrupt JSONB blob all receive exactly five bands. The `Select` therefore has **no empty branch, no loading branch and no fallback branch** — five `<option>`s, always.

**The option label carries the word AND the minutes: «חצי יום · 240 דק׳».**

This is the deck's answer to a problem the spec names and does not solve: **F41 ships no editor for the mapping and F42 owns it** (Risk 4), so a boutique whose shifts are six hours cannot re-tune «חצי יום» from 240 to 300 without `psql`. Showing the number in the picker does not fix that — but it makes it **visible at the moment the estimate is made**, so the owner discovers the mismatch on day one and asks, instead of discovering it in F42's load bars three weeks later when every estimate in the boutique is already wrong. It costs one interpolation.

**The card shows the word alone; the picker shows the word and its value.** Not an inconsistency: the picker is where the estimate is *chosen* and the number is the thing being chosen; the card is where it is *read* and the word is the summary. The card would be four characters wider for a number nobody is deciding.

**⚠ An `<option>` takes no markup, so neither `isolateLtr` nor `isolateBidi` is available inside one.** The string is built so the numeric run is **bracketed by Hebrew on both sides** — «חצי יום · 240 דק׳» — which is what makes the bidi resolution safe without markup: a weak-LTR numeric run surrounded by strong RTL characters resolves in place. A string ending in the number («חצי יום · 240») would put a neutral run at the paragraph edge and could reorder. Same rule governs the assign `<select>`'s options, which carry Hebrew display names and need no treatment at all.

**Post-re-tune, a stored `effort_minutes` may match no current band**, and the card renders it honestly as «300 דק׳» through `bandLabel`'s fallback. That is the visible consequence of D8's "minutes persist, never the label" and it is correct: a ticket estimated under the old mapping must not be silently re-valued.

### 7.3 The `Modal`'s states

| State | What renders |
|---|---|
| **Open, create** | Empty fields, `due_date` empty, `effort_band` = «שעה», the dress `Select` on «לא מהקטלוג» with `dress_name` revealed. Focus is the dialog's own (native `<dialog>`) |
| **Open, edit** | Prefilled from the card. The customer is a static line, not a field |
| **Submitting** | Confirm `Button` carries `loading`; fields stay enabled |
| **Per-field validation error** | The message rides the field's own `error` prop — `Input` and `Select` both wire `aria-describedby` + `role="alert"` and flip the border to `border-danger`. Covers `customer_name`, `customer_phone`, `due_date`, `effort_band`, `dress_name`, `dress_size`, `notes` |
| **A server error that maps to no field** | An unknown band key, a `dress_id` 404, a 409 from a concurrent edit: **one alert inside the dialog, above the footer**, `role="alert"` and focused — never a Toast behind a modal, and never a message the dialog dismisses itself to show |
| **✚ A returning customer whose stored name differs** | The moment the phone parses, «לקוחה קיימת — השם יעודכן ל…» beside the phone field, `--color-warning-text --text-sm`. `upsert` rewrites `customers.name` **unconditionally** (spec D6) and F53 now renders that name on a screen of its own, so a seamstress typing «מיכל» for a customer stored as «מיכל לוי» must not do that invisibly. No new endpoint — intake echoes the resolved `customer_name` |
| **Success** | The `Modal` closes; native `<dialog>` returns focus to the trigger; `atelier.cue.created` is announced, naming the bride — because focus went back to «כרטיס חדש» and **not** to the new card, so the cue is the only thing that says which ticket was opened |

### 7.4 The delete confirm `Modal`

`Button variant="danger"` trigger → `Modal` whose footer is `ghost` dismiss + `danger` confirm. The shipped destructive pattern (`manage-restyle.md`; `StaffSection.tsx:411-446` is the console's instance), and **two `danger` buttons in one component is correct, not a hierarchy failure** — the trigger and the confirm are never co-visible because the Modal covers the board.

| State | What renders |
|---|---|
| **Open** | Title «מחיקת כרטיס», body naming the bride and stating that it cannot be undone. **`api.deleteTicket` is not called until the confirm is activated** — its own acceptance line and its own test |
| **Submitting** | The `danger` confirm carries `loading` |
| **Refused** | The alert inside the dialog, as §7.3 |
| **Succeeded** | The dialog closes, the card leaves the board, **focus goes to that card's column `<h3>`** (§3.3 #4 — native focus-return would put focus on a trigger that no longer exists), and `atelier.cue.deleted` is announced |

**There is no un-delete** (spec Risk 6), which is why this is the one act on the board that asks before it writes.

---

## 8. Component notes — exact tokens

| Element | Notes |
|---|---|
| Section heading | `<h2 ref={heading} tabIndex={-1} className="text-lg font-semibold text-ink">` — `FloorPanel.tsx:344`'s exact shape. `tabIndex={-1}` adds **no** tab stop |
| Freshness row | `<div className="flex flex-wrap items-center justify-end gap-3 text-sm text-ink-muted">` — `justify-end`, there is no inline-start half. `items-center`, never `items-baseline`, now that the line carries a 44 px control |
| Pause / resume | `Button variant="ghost" size="md"`, `aria-label` swapping with the visible label. **No new variant, no `aria-pressed`, no icon** |
| Intake CTA | `Button variant="primary" size="md"` — the one `primary` on this screen. `fullWidthMobile={false}`: at 375 a full-width primary above a stacked board reads as a page-level action, which it is not |
| Cue region | `<p role="status" tabIndex={-1} className="text-sm text-ink-muted">`, empty at rest. **Written only when its value changes.** ⚠ `{{name}}` renders through **`isolateBidi`** (bare `<bdi>`), never `isolateLtr` — the shipped `{ text, name }` state shape and `FloorPanel.tsx:428`'s exact call. `{{stage}}` and `{{minutes}}` need no isolation: a stage word is **our own Hebrew vocabulary**, and where a numeric run appears in a cue it does not |
| Stage rail | `<nav aria-label>` → `<ul className="flex flex-wrap gap-2">` → `<li><a href="#atelier-h-{stage}" className={cn("rounded-full border border-border px-3 py-2 text-sm text-ink", focusRing)}>`. **`py-2 text-sm` ≈ 40 px — under the 44 floor**, so the chip carries `min-h-11` explicitly and `inline-flex items-center` to keep the label centred |
| Column `<section>` | `<section aria-labelledby={headingId} className="space-y-2">` — a **named region**, §9.1 |
| Column `<h3>` | `<h3 id={headingId} tabIndex={-1} className="text-base font-semibold text-ink">` — the rail's target and §3.3's destinations #1b and #4 |
| Column `<ul>` | `<ul tabIndex={0} aria-label={t(STAGE_LABEL_KEY[stage])} className="space-y-3 md:max-h-[32rem] md:overflow-y-auto">` — §6 for both the bound and the `tabIndex` |
| Ticket `<li>` | `<li data-ticket-id={id}>` — the ref-map key §3.3 depends on, and the `closest()` target rules #4 and #5 read |
| Ticket `Card` | `<Card className="space-y-1">`. **`p-6` untouched** |
| Name | `<bdi className="font-semibold break-words text-ink">` — bare `<bdi>` |
| Overdue `Badge` | `<Badge variant="danger">{t("atelier.overdue")}</Badge>` — `border-danger text-danger`, **6.18:1 on paper**. One `Badge` per card |
| Dress / effort / assignee lines | `<p className="text-sm text-ink-muted">` |
| Due line | `<p className={cn("text-sm", overdue ? "text-danger font-semibold" : "text-ink")}>` with the date in `<bdi dir="ltr">` via `plainDate` — **no new formatter** (spec D18) |
| Notes | `<p className="text-sm text-ink break-words"><bdi>{notes}</bdi></p>` |
| «לשלב הבא» | `Button variant="secondary" size="md"`, `ref` into the id-keyed map |
| Skip / assign `Select` | `<Select label={…} aria-label={…} className="min-h-11">` — `Select.tsx` declares **no min-height** (`px-3 py-2 text-base` lands near 42 px), so the class is not optional. `aria-label` rides `...rest` onto the `<select>` |
| Commit `Button`s | `Button variant="secondary" size="md"`, `disabled` until the sibling draft is non-null |
| «ביטול שלב» / «עריכה» | `Button variant="ghost" size="md"` |
| «מחיקה» | `Button variant="danger" size="md"` → confirm `Modal` |
| In-card alert | `<p role="alert" tabIndex={-1} className="text-sm text-danger">` |
| Loading | `Skeleton variant="text" lines={3}` inside one `Card` — `aria-hidden`, so announcing is the cue region's job |
| Empty board | `EmptyState` with `title`, `body` **and** `action` (the CTA) — §5 **A-empty** |
| Empty column | `<p className="text-sm text-ink-muted">` inside the column |
| Terminal panel | `<p role="alert" className="text-sm text-ink">` + `Button variant="secondary"` — **the same treatment for 401 and 403**, different sentence |

**Contrast, from the tokens ledger — not eyeballed.** ink 13.89 on paper · ink-muted 5.61 · danger 6.18 · warning-text 5.20 · success 5.56 · focus ring 5.57 · border (non-text boundary) ✓. **This feature introduces no new colour pair and no gold at all** — there is no divider on this screen to put the console's one `gold-strong` hairline on. The ledger needs no addition at this gate.

---

## 9. The a11y contract — IS 5568 / WCAG 2.0 AA is a legal requirement (pre-decided #38)

### 9.1 Structure — five named regions of five named lists, and the names are load-bearing

**Five `<section aria-labelledby>` each containing an `<h3>` and a named `<ul>`. Not a table, not a `role="grid"`, not `role="application"`, and not five `<div>`s under a CSS grid.**

The names are not decoration. **An unnamed `<section>` is not exposed as a region at all**, and an unnamed `<ul>` is an anonymous list — so a user navigating by list (NVDA `L`, VoiceOver rotor), which is exactly the navigation a five-region board invites, would land on five consecutive anonymous lists with no way to tell `qc` from `ready`, and the count in the `<h3>` would be reachable only by walking backwards out of the list she is in. With the names she hears «בעבודה, רשימה, 4 פריטים» and arrows through it.

**The count in the `<h3>` is what replaces the visual scan a sighted user gets for free** — it is how she knows a column is long *before* entering it.

**The heading carries «{{stage}} · {{count}}» and deliberately no noun.** Hebrew has singular, dual and plural agreement, so «כרטיס / שני כרטיסים / כרטיסים» would need three i18next plural suffixes per stage — and the `<ul>`'s own list role already announces the item count. Dropping the noun costs nothing a screen reader needs and removes fifteen keys and a whole class of agreement bug. Recorded as a small departure from spec D16's illustrative «בעבודה, 4 כרטיסים» (**F-3**).

**Headings**: the shell owns the single `sr-only` `h1`; the section heading is an `h2`; the five column headings are `h3`. No skipped levels, no fourth level — the card has no heading, because a card is a list item and giving it one would put sixty headings between two columns.

### 9.2 Live regions — the three-region split, inherited whole

| Region | ARIA | Carries | Politeness |
|---|---|---|---|
| **The cue** (`<p>` above the rail) | `role="status"` | first-load `atelier.loading`, then **user-initiated outcomes only**: `cue.created`, `cue.advanced`, `cue.undone`, `cue.assigned`, `cue.released`, `cue.deleted`, `paused`, `idleStopped`, `resumed`. Empty at rest | **polite** |
| **The five lists** | **no live attributes at all** | the cards | **off.** `role="log"` is the tempting wrong answer — it is for append-only chat, and these lists mutate in place and hand items to each other |
| **The freshness row** | **no live attributes**, and deliberately **not `aria-hidden`** | «עודכן 14:07» / the stale / paused copy | **off, but readable.** `aria-hidden` would make the board's only honesty signal sighted-only — F34's **F-1**, accepted into the spec's a11y floor |

**⚠ The cue's TEXT is the entire a11y payload of the no-drag decision, and it is declared copy.** For a sighted user an advance is self-evident — the card is visibly in another column. **For a screen-reader user the cue IS the move.** So `atelier.cue.advanced` names the ticket **and its destination stage**, and the acceptance criterion asserts `getByRole("status")`'s **textContent** contains the customer name and the stage word — not merely that the region changed.

**`role="alert"` appears exactly four times**, and each is bounded: **A-401** (once per dead session — the loop has stopped), **A-403** (once per revocation, same), **A-conflict** / **A-gone** (once per refused activation, bounded by her own tapping), and the `Modal`'s own field and dialog alerts (bounded by her own submitting). **None can be produced by the poll on its own.**

### 9.3 Motion

Nothing on this board animates except the shipped `Button` spinner during a mutation and the `Skeleton` pulse on first load — both already frozen globally by `theme.css`'s `prefers-reduced-motion` block. **No highlight on a card that moved, no fade on an arriving one, no transition on a column's height, no scroll animation from the rail** (`scroll-behavior` is left alone; the reduced-motion block already forces `auto`). **This feature adds no motion rule because it adds no motion.**

### 9.4 SC 2.2.2, target size, and the rest

**SC 2.2.2 Pause, Stop, Hide (Level A) — the row no tool will ever add for us.** Content that auto-updates, starts automatically and is presented in parallel with other content must offer **a mechanism for the user** to pause, stop or hide it. A board repainting every five seconds for a whole shift is squarely that. Three things make this row different from every other item here:

1. **It is a legal bar.** Pre-decided #38 makes IS 5568 / WCAG 2.0 AA legally required for these screens, and Level A sits inside AA.
2. **`axe` cannot see it.** There is no axe rule for 2.2.2 — the criterion needs a human judgement about what counts as auto-updating. The failure mode is not "CI catches it late"; it is "**CI stays green and the product is non-conformant**".
3. **The only coverage is the named frontend tests plus this deck**, and this gate self-approved, so there was no human reviewer behind them either. They **may not be dropped as redundant with the axe assertion**.

The control: **one `<button>` whose accessible name changes**, `min-h-11` (44 px), **first stop inside the section before any card** (a 2.2.2 mechanism placed after the content it governs is reachable only by walking the list that is repainting under the walk), never `aria-pressed`, announced on press through the existing `role="status"`, focus **stays on it** (it renames, it does not unmount), resume fetches **immediately at the base interval**. Idle stop at the shared `IDLE_STOP_MS` = 10 minutes, with its own region-naming copy (§1.2).

**Declined: a frequency picker.** 2.2.2 is satisfied by any one of pause / stop / hide / control-frequency; a picker is a settings surface plus a persisted preference plus a second constant, and the board would then have two places answering "how live is this".

**SC 2.2.1 Timing Adjustable — named, and explicitly not this feature's to close.** `session_ttl_seconds` is 43200 (12 h), under 2.2.1's 20-hour exception, unextendable and unwarned. The remedy is a session-model change owned by F21. What this board does is stop the loop and say so honestly (**A-401**).

- **≥44×44 on every target**: every `Button` is `size="md"` → `min-h-11`; both `<Select>`s carry `min-h-11` explicitly because `Select.tsx` declares none; the rail chips carry it too. **`size="sm"` is barred anywhere in this tree**, asserted as a rendering check.
- **Visible focus ring** on every interactive element — `focusRing` from `@boutique/ui`, applied unconditionally by `Button.tsx` and `Select.tsx` and by hand on the rail's `<a>`s. Nothing here sets `outline: none`.
- **Accessible names disambiguate the ticket on EVERY per-card control, `<Select>`s and commit `Button`s included.** `Select` derives its accessible name **solely** from its required `label` prop, which it renders as a visible `<label htmlFor>` — there is no name-override path in its API. Left at that, a 30-card board exposes 30 comboboxes all named «העברה לשלב» and 30 more all named «תופרת», and a screen-reader user pulling up the control list cannot address a specific ticket (WCAG 4.1.2, 2.4.6). Both spread `...rest` onto the `<select>`, so both carry an `aria-label`. **Each aria value CONTAINS its visible label** (WCAG 2.5.3 label-in-name), so a speech-input user saying «העברה לשלב» still matches — asserted in `i18n.test.ts` for every pair plus the pause pair, not trusted. **⚠ Two of those pairs are missing from spec D18's table and `copy.md` §3.1 adds them** (`atelier.skipCommitAria`, `atelier.assignCommitAria`): D18 names the two `<Select>`s and «לשלב הבא» / «ביטול שלב» / «עריכה» / «מחיקה», and neither commit `Button` — which are per-card controls with a fixed label exactly like the others. **And D18's `assignLabel` «שיוך» collided with `assignCommit` «שיוך»** — two controls in one card with the same accessible name — so the `<Select>`'s visible label is revised to «תופרת» (what is being chosen) against the `Button`'s «שיוך» (the act), which is also how the skip pair reads.
- **Status and urgency carry WORDS**: the stage is the column heading; overdue is «באיחור» in a `Badge`; unassigned is «לא משויך»; an inactive assignee is «תופרת שאינה פעילה»; paused is «מושהה» plus a body line plus the control's own label flip. **Colour is never the signal anywhere on this screen.**
- **Bidi**: `<bdi dir="ltr">` on numeric runs (dates, minutes); **bare `<bdi>`** on Hebrew free text (customer names, dress names, seamstress names, notes). `dir="ltr"` on a Hebrew name is the worse defect *because it looks deliberate*. An `aria-label` takes no markup, so every `*Aria` key interpolates plainly and is outside this rule.
- **Content capped at 720 px** at every width (§6). **`A11yMenu` / `A11yStatementLink` are storefront-only**, so no fixed-chrome clearance applies.
- **An `axe` pass** runs over the board in `__tests__/AtelierSection.test.tsx` — **and it is explicitly not sufficient**, per the three points above and per §3.3's five focus rules, none of which axe can see.

---

## 10. RESOLVED decisions — self-approved with the design gate, 2026-08-03

**All eight carry a resolution and none is an open question.** Each keeps its full reasoning, because the reasoning is what a later feature would have to overturn to reopen it. **The Hebrew remains the user's to edit post-merge** — the F15 P-1/P-5, F34 and F57 precedent: a one-line `he.ts` / `ar.ts` edit after merge, never a rebuild.

| | Resolution |
|---|---|
| **P-1** | **The ticket is the `Card`; the column is a bare named `<section>`** — the inverse of F57's P-1, for a stated reason |
| **P-2** | **The empty board replaces all five columns with one `EmptyState`** that teaches the five stage words |
| **P-3** | **No aggregate count line** — the rail already carries five |
| **P-4** | **A seamstress's own tickets are NOT hoisted or filtered** — server order, one board |
| **P-5** | **No per-card disclosure** — every control the server will accept is visible on the card |
| **P-6** | **The stage is the column, never a `Badge` on the card** |
| **P-7** | **No new numbers**: 5 s / 60 s cap / 10 min idle, all from `usePoll` |
| **P-8** | **F42 extends this deck's assign control and this payload — it does not get a second surface** |

- **P-1 — RESOLVED: `<section>` → `<h3>` → `<ul>` → `<li><Card>`.** F57 made the panel one `Card` around a `divide-y` list because at 375 a card and a row inside a card are the same rectangle, and a `Card` inside a `Card` is a shadow on a shadow. Both halves of that reasoning still hold — which is why the **column** is not a `Card`. But the unit of *this* screen is a thing that moves between named regions, and at ≥768 two `divide-y` lists side by side read as one continuous list spanning both columns. A discrete `Card` per ticket is what makes the move legible. Cost: `space-y-3` between cards instead of `divide-y`, which is one utility either way.
- **P-2 — RESOLVED: the empty board is one `EmptyState` with a title, a body and the CTA, not five empty columns.** This is the first thing every new boutique sees, and five columns each reading «אין כרטיסים בשלב זה» is a wall of nothing that *teaches the vocabulary at the cost of looking broken*. The `EmptyState`'s **body is where the vocabulary gets taught instead** — one sentence naming the five stages in order, which is strictly more useful than five headings with nothing under them and cannot be mistaken for a failure. The rail does not render either, for the same reason (§1.1). **The freshness row does**, because a surface that has stopped updating must still be able to say so.
- **P-3 — RESOLVED: no «12 כרטיסים פתוחים» summary line.** The rail carries five counts computed from the same array; a sixth number that is the sum of five visible numbers is a second fact to keep true through every tick, and F57's **P-3** made the same call for the same reason. If a pilot asks for a single "open work" figure, that is F42's — it will already be summing minutes.
- **P-4 — RESOLVED: no «רק שלי» filter and no hoist of a seamstress's own tickets.** Tempting, because a seamstress's own work is what she came for. Declined for three reasons: a filter would give two staffers standing beside each other **different boards for the same data**, so they could not point at "the third one in בקרה"; the unassigned pile — the thing a shift manager most needs to see and a seamstress most needs to claim from — is by definition not hers, so a "mine" filter hides the work she is supposed to pick up; and it would be a second, client-side ordering beside the server's bride-date rank, which pre-decided #40 fixes and which F42's matrix must agree with. **The recorded upgrade path** if a pilot asks is a client-side filter `Toggle` above the rail — no new endpoint, no new state shape, one line of `.filter()` — and it should be reached for only with a pilot behind it.
- **P-5 — RESOLVED: no «עוד פעולות» disclosure on the card.** With up to seven controls, a card is tall, and a `<details>` would halve it. Declined: a closed `<details>` removes its contents from the accessibility tree, so «מחיקה» and «עריכה» would be one activation further away for *everyone* and invisible to a control-list query, which is the navigation §9.4 just spent a paragraph making work. The controls a given role sees are already narrowed by §2.3's matrix — a seamstress on another's ticket sees **none** — so the seven-control card is the owner's case, and the owner is the one on the widest screen. **If a pilot shows the card is too tall, the first thing to cut is the skip `Select`** (already narrowed to ≥2 later stages), not the visibility of the destructive controls.
- **P-6 — RESOLVED: the stage word appears in the column heading, the rail chip, the skip `<option>`s and the cue — and never as a `Badge` on the card.** The card is *in* the column; a stage `Badge` would be 295 px spent restating the region, and it would be a second place to keep true the moment a card is patched from a mutation response. This is F57's **F-3** («מאז 11:20», not «בהפסקה מ־11:20») applied to a different fact. It also keeps §2.4's rule that there is **exactly one `Badge` per card and overdue owns it**.
- **P-7 — RESOLVED: this section introduces no constant.** `POLL_INTERVAL_MS` = 5 s, `MAX_BACKOFF_MS` = 60 s and `IDLE_STOP_MS` = 10 min are exported by `usePoll` and were ruled at F34's gate. Three surfaces with three different beats would be three things to explain and nothing to gain. If F29 halves the beat, it halves all three. `DELIVERED_WINDOW_DAYS` and `BOARD_TICKET_LIMIT` are **server-only** and must not be mirrored on the client — the `truncated` flag is on the wire precisely so the console never has to know the number.
- **P-8 — RESOLVED: F42 adds `weekly_capacity_hours` and `assigned_minutes` to this payload's `seamstresses[]`, sorts §2.3's assign `Select` by remaining capacity, and renders a load bar in the seamstress directory it brings with it. It does not add a second poll loop and it does not restyle this card.** That is what "an addition, not a rewrite" means concretely, and it is why `AtelierBoardResponse` is an envelope rather than an array. Two consequences this deck pre-authorises: the assign `Select`'s `<option>` labels may grow a capacity suffix (an `<option>` takes no markup, so §7.2's Hebrew-brackets-the-number rule applies to it too), and **F42 must render a second anomalous bucket beside `NULL`** — a non-assignable or unknown assignee, which this deck already surfaces per card as «תופרת שאינה פעילה» from the wire's `assignable` flag.

---

## 11. ⚠ FINDINGS

- **F-1 — ⚠ THERE IS A FIFTH FOCUS MOVE AND THE SPEC NAMES FOUR.** A poll that applies a colleague's stage change **unmounts the focused card from one `<ul>` and mounts it in another**, dropping `document.activeElement` to `<body>` with no user action at all, five seconds after somebody else tapped a button on a different phone. Spec D16 enumerates advance-success, advance-failure, poll-clears-a-focused-alert and delete; none covers this, and `reclaimFocusRef` does not fire because no alert is involved and `departingCardHoldsFocus` does not fire because the ticket is still in the payload. **This is the fourth appearance of the bug class this repo has now shipped three times, and it is the first one whose trigger is another person.** §3.3 rule #5 is the remedy: one comparison in the load path at *"the only moment both lists exist"*, plus a fifth named, non-vacuous vitest test. **It must be built, not filed** — the residual after building it is smaller and is F-4. *Owner: this feature. Trigger: the plan, which must carry it as a task rather than discovering it in review.*
- **F-2 — the five-column board does not fit the console and this deck does not fix the console.** `ConsoleShell` caps content at 720 px in **three** places (`:46`, `:56`, `:84`), which puts five columns at **128 px** and a `Button` reading «לשלב הבא» wider than the column it sits in (§6). Lifting the cap for one section is not a prop — the header and nav carry it too, so a wide `main` under a 720 px nav is visibly broken, and lifting all three re-lays-out twelve sections designed against a 720 px form column. **F42's capacity matrix is the natural owner**: a seamstresses × days grid has the same problem, a stronger claim, and its own design gate. The recorded shape if it is taken: a `contentWidth` prop on `ConsoleShell` applied to all three rows, defaulting to 720. *Owner: F42. Trigger: F42's deck, or a pilot owner asking for a desk view.*
- **F-3 — the column heading drops D16's noun, and Hebrew agreement is why.** Spec D16 illustrates the screen-reader read as «בעבודה, 4 כרטיסים, רשימה בת 4 פריטים». Shipping «{{count}} כרטיסים» literally would mislabel one («1 כרטיסים») and two («2 כרטיסים» where Hebrew takes the dual «שני כרטיסים»), and doing it correctly needs i18next plural suffixes — three forms × the same string, in **two** bundles, all of which the `ar` parity guard then walks. The `<ul>`'s own list role already announces the item count, so the noun is redundant to the reader it was written for. **Shipped as «{{stage}} · {{count}}».** Recorded rather than folded in silently, because a reviewer diffing this deck against D16 will otherwise read it as drift. *Owner: recorded, no action.*
- **F-4 — a screen-reader user whose focused card is moved by a colleague hears the same control re-announced and never learns why.** F-1's fix moves focus correctly, so nothing is lost — but D11 forbids the poll writing into the live region, so no cue explains the move, and the control's `aria-label` («לשלב הבא — מיכל לוי») is byte-identical before and after. She hears the same name twice and the card is now in a different column. **Accepted, because the alternative is worse**: allowing poll-driven writes is the rule §4.2 spends four paragraphs defending, and a bounded exception ("only when the poll moved the FOCUSED card") is a rule change above this feature — it would be the first crack in a rule three surfaces now depend on. **The cheap remedy if a pilot hits it** is exactly that bounded exception, at most one announcement per remote move of one card, never per tick. *Owner: team. Trigger: pilot feedback from a screen-reader user, or F44, which puts the same content on a shared floor display.*
- **F-5 — the spec's first-fetch-failure row asks for a reuse that has nothing to reuse.** §Every state says *"the outage register — reuse a subject-named shipped key rather than declaring `atelier.outage`"*, citing F57's **F-10**. But F-10's rule is *reuse a key whose **namespace names its subject***, and no shipped key names *this* subject — `staff.loadFailed` is «לא הצלחנו לטעון את רשימת הצוות כרגע», which is the staff list, and `board.*` names a screen three roles cannot open. **Resolved by declaring `atelier.loadFailed`**, whose namespace *is* its subject, which is F-10 obeyed rather than departed from. *Owner: recorded, resolved in `copy.md` §5.*
- **F-6 — a 500-character note makes a tall card, and this deck declines to clamp it.** §2.2's reasoning is that the note is the work order and «עריכה» is refused to a seamstress on a ticket that is not hers, so a clamp hides the instruction from the person doing the work. The ceiling stands: a boutique that writes essays gets cards several screens tall, and on a 60-card column that is a lot of scrolling for the rail to rescue. The mitigation that ships is `TextArea`'s `showCount` at the moment of writing. **The remedy if it bites is a `line-clamp-3` PLUS a per-card disclosure — both, never the clamp alone.** *Owner: team. Trigger: pilot feedback.*
- **F-7 — 96 new keys land in `he.ts` and `ar.ts` by hand, and the whole exposure is one missing `...HE_F41`.** The `ar` parity guard exists (`i18n.test.ts:417-420`) and **has since F52** — but `HE` is a hand-assembled union of per-feature selections (`:48`) and four shipped guards iterate it, so a block that is *declared and not spread* is skipped **silently and greenly**. The file records that exact failure in its own words for F52 and F53 asserts the fold rather than trusting it. `copy.md` is the single source for **both** columns, which makes it one file to one file — and the fold assertion (`expect(HE.map(([key]) => key)).toContain("nav.atelier")`) is what makes it a test. *Owner: this feature. Trigger: the i18n task.*
- **F-8 — the rail is a second navigation landmark on a page that already has one, and its counts are a second rendering of the headings' counts.** Both are deliberate (§1.1) and both are the kind of thing a later reader trims. The `<nav aria-label>` is what keeps landmark cycling legible; the shared count comes from one grouped array passed to two renderers, never computed twice. **If a fourth panel ever lands on this section, the rail is the thing that stops scaling** — five chips wrap at 375 already. *Owner: team. Trigger: F42, which adds a seamstress directory to this screen.*
- **F-9 — the console now has three polling surfaces and ~14 of this deck's strings are byte-identical to F34's and F57's.** «השהיה», «חידוש», «רענון», «עודכן {{time}}», «אין עדכון מאז {{time}}», «מושהה · עודכן {{time}}», «ייתכן שהמידע אינו עדכני.», «העדכון חודש.», «תוקף החיבור פג…» and «רענון הדף» now exist under `board.*`, `floor.*` **and** `atelier.*`. F57's **F-9** predicted this precisely — *"F37, F41 and F59 are callers three, four and five, and the PR that adds the third set of duplicates is the one where `poll.*` is worth the rename"*. **This is that PR, and the rename is still declined here**, for the reason that has not changed: lifting them into `poll.*` edits `BoardSection`'s and `FloorPanel`'s i18n, and both components must pass **unedited** — which is the only thing separating a faithful fourth `usePoll` consumer from a subtly different one. **The prediction is now due and the owner should be named rather than the trigger deferred again.** *Owner: team. Trigger: F37 or F59 — whichever is the fourth polling surface — as a standalone i18n PR that touches no component logic.*
- **F-10 — `atelier.cue.advanced` and `cue.undone` do NOT use spec D18's «הועבר ל{{stage}}» / «הוחזר ל{{stage}}» wording, and the reason is grammar, not preference.** The five stage words are past-tense verbs and an adjective — «התקבל», «בעבודה», «בקרה», «מוכן», «נמסר» — and «ל» does not prefix them: «הוחזר להתקבל» and «הועבר לבעבודה» are both ungrammatical, and the undo cue reaches «התקבל» on every undo of `in_progress`, which is the commonest undo there is. **Shipped as a colon construction — «{{name}} — שלב חדש: {{stage}}.» / «{{name}} — חזרה לשלב: {{stage}}.»** — which is word-agnostic, so a sixth stage word can never break it. This also keeps each cue to **one** interpolated *user* value, which is what lets `isolateBidi(cueText, cue.name)` and the shipped `{ text, name }` state shape work unmodified: `{{stage}}` is our own vocabulary and needs no isolation. **The same rule is why `cue.assigned` names only the seamstress and not the ticket** — the card does not move on an assign, so focus is still on it and focus is the referent; a cue names the ticket only when the ticket moved out from under the user. That is not only editorial: it keeps every cue to **at most one interpolated user value**, which is what lets the shipped `isolateBidi(text, value)` and the shipped `{ text, name }` state shape work unmodified and **no second helper be invented**. D18's two-name version would have needed one. Recorded as three copy corrections to D18 rather than folded in silently. *Owner: recorded, resolved in `copy.md` §4.*
- **F-11 — D18's per-card accessible names are two short, and one of the ones it gives collides with another control in the same card.** D18 names the two `<Select>`s and «לשלב הבא» / «ביטול שלב» / «עריכה» / «מחיקה», and **neither commit `Button`** — so a 30-card board would expose 30 buttons named «העברה» and 30 named «שיוך», which is the identical WCAG 4.1.2 / 2.4.6 dead end D18 fixes one control over. `copy.md` §3.1 adds `atelier.skipCommitAria` and `atelier.assignCommitAria`. Separately, **D18's `assignLabel` is «שיוך» and its `assignCommit` is also «שיוך»** — the `<Select>`'s visible `<label>` and the `Button` beside it, two controls in one card carrying **the same accessible name**, which no `— {{name}}` suffix fixes because both would carry it. Resolved by making the `<Select>` name **what is being chosen** («תופרת») against the `Button`'s **act** («שיוך»), which is the shape the skip pair already had. *Owner: recorded, resolved in `copy.md` §3.1.*
- **F-12 — the column count must not interpolate `{{count}}`, and the obvious name is the trap.** `count` is i18next's plural-resolution trigger: passing it makes the translator resolve `key_one` / `key_two` / `key_many` / `key_other` before the base key, so a bundle carrying only the base key reaches its string through a fallback path rather than directly. It renders correctly today. It is one library upgrade, one `pluralSeparator` config change or one `returnObjects` edit away from not — on a string that appears **ten times per paint** (five headings, five rail chips). `copy.md` uses `{{total}}`. Hebrew's dual is the related reason the string carries no noun at all (**F-3**). *Owner: recorded, resolved in `copy.md` §0 rule 11.*
