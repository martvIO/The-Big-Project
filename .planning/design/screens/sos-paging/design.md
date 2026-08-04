# Screen: SOS paging — the full-screen alert overlay, the SOS centre, the raise dialog (F37 — `SosOverlay` app-level, `SosCentre` inside F57's shipped `FloorPanel`)

**Date**: 2026-08-03 · **Status**: **DESIGN GATE SELF-APPROVED.** Interview **Q2** named exactly two novel interaction patterns for this run — F34's shift board and F42's capacity matrix (`LOOP-STATE.md`, `rulings_2026_07_31`) — and E7's screens assemble from F34's board shell and F57's shipped `FloorPanel`. So there is **no prototype and no `design-critic` pass**, and every `P-` in §10 carries a resolution rather than a question. **The gate goes away; the design work does not** — this deck and `copy.md` are build tasks (spec **D17**, **D18**), not review preconditions. ⚠ **One clause of the gate does NOT go away: the manual screen-reader pass on this PR** (e7 Risks — *"Add an explicit manual screen-reader check to the design gate for F37 rather than trusting the mechanical pass"*), and spec **D15** is a gate condition in its own right.
**Designer**: Claude · **Consumes**: `.planning/specs/sos-paging.md` (**D1–D18**, Gate 1 standing-approved, 33 review findings applied) · `.planning/design/system/tokens.md` (**binding**) · `.planning/design/screens/design-system/manage-restyle.md` (**binding**) · `.planning/design/screens/fitting-rooms/design.md` (F36 — this feature adds a fourth control to its tile and inherits **F-3**'s interpolation rule and **F-4**'s `Select` height) · `.planning/design/screens/floor-staff-roles/design.md` (F57 — `SosCentre` is a child of that panel and inherits every ruling in it) · `.planning/design/screens/shift-board/design.md` **Revision 2** (F34's **D11** live-region rule, **F-7** write-vs-change, **F-8** pointer-hold, the `{401,403}` pair) · `packages/ui` and `apps/manage` **as shipped**
**Copy**: `copy.md` in this directory — **it is canonical, this deck's inline Hebrew is illustrative.** Spec D17 says so in as many words; the F57 and F36 precedent is that corrections land in `copy.md` first, and **this deck ships four** (§11 **F-5**).
**Prototype**: **none, deliberately.** The two questions a prototype would answer — *is a live beat usable*, *is a one-tap act right under a thumb* — were answered at F34's gate and the mechanisms are now shared code (`usePoll`, `FloorPanel.mutate`). The question a prototype **could not** answer is the only genuinely new one here: *does a real screen reader announce a `role="alert"` that mounts inside a React commit, and does a real browser leave the caret in an input under a `position: fixed; inset: 0` sibling?* jsdom answers both by fiat and a static prototype answers neither. **Risk 6 hands F58 four named cases, and the manual screen-reader pass on this PR is the interim.**

**What this deck is NOT.** It is not a redesign of `FloorPanel` — F57 shipped it as PR #33 and this feature adds **one child panel above `RoomsPanel`** and one line to a comment. It is not a redesign of `RoomsPanel` — F36 shipped it as PR #37 and this feature adds **one control to one tile** and **one optional prop**. It is not a new console section: `SectionKey` stays **thirteen**, `NAV` stays thirteen rows, `Nav.test.tsx` needs no edit, and that is an assertion rather than an omission. It is not F35's bell — the bell is dropped from this feature's deps by the 2026-07-31 ruling and stays queued as the later durable surface.

⚠ **The numbers this deck quotes were re-verified against the tree on 2026-08-03**, after F57 (PR #33), F53 (PR #35), F33 and F36 (PR #37) all merged the same day. `App.tsx:20-33` carries **thirteen** `SectionKey` members; `ToastProvider` wraps the signed-in tree at `App.tsx:187`; `setStaff(null)` appears in exactly **two** places (`:142`, `:164`); `ConsoleShell.tsx:84` renders `<main id="console-main" tabIndex={-1} className="… max-w-[720px] …">`; `i18n.test.ts` now folds **nine** per-feature constants into `HE` and F37 makes it ten. ⚠ **Check the FOLD, never a line number** — the array moves every time a feature lands, which is exactly why the mechanism and not the citation is what this deck records. *Reported as spec drift in §11; the spec is not edited from here.*

---

## 0. Scope

Four surfaces. **One of them renders on every screen in the console and three of them render on one.**

| Surface | Where it renders | Who sees it | Shape |
|---|---|---|---|
| **The alert overlay** | **app-level, over any of the thirteen sections** | anyone with a **rising** alert (`for_me`, spec D7) | `<SosOverlay/>`, first in `App`'s signed-in tree, **before** `<ConsoleShell>` |
| **The channel strip + the re-open affordance** | app-level, bottom edge | the same caller, when the channel is dead or an alert is dismissed-but-live | rendered by `<SosOverlay/>` instead of `null` |
| **The SOS centre** | inside `<FloorPanel/>`, **above** `<RoomsPanel/>` | all five roles, on `board` and `floor` — **2 of 13 sections** | `<SosCentre/>`, a child of `FloorPanel` (spec D16) |
| **The raise dialog** | top layer | all five roles, from two triggers | `<SosRaiseDialog/>`, the shipped `Modal` |

Plus **one control** on one room tile (§5) and **one prop** on `RoomsPanel`.

**Zero new `packages/ui` components and zero new variants.** Everything is `Button`, `Card`, `Badge`, `Select`, `Input`, `Modal` and the two shipped bidi helpers (`isolateLtr`, `isolateBidi` — `lib/booking.tsx`). Verified against the shipped files rather than assumed: `Button.tsx:37` gives `md` a `min-h-11` (44px) and `:38` gives `lg` a `min-h-12`; `:63` applies `focusRing` unconditionally; `:57` is `disabled={disabled || loading}`, which is why the browser blurs every tapped control and why §9.2 exists; `Badge.tsx:15-21` exports `neutral / success / danger / muted / warning`; `Modal.tsx:19-49` is a native `<dialog>` whose `showModal()` puts it in the **top layer**, above every `z-index` in the document, and whose `onCancel` owns Esc; `Select.tsx:12` carries the *"native `<select>` — no custom dropdown in v1"* decision this feature would otherwise re-argue; `Card.tsx` is `rounded-md bg-surface p-6 shadow-sm` — **paper, not white**, which §8 depends on.

### Binding inheritances (obeyed, not restated)

From **`tokens.md`**: the gold law (`--color-gold-strong` never carries text — it appears on these screens **zero** times); focus ring on every control (law 4); ≥44×44 (law 7); no raw px in app code (law 5); **no colour communicates alone (law 2)** — which on a full-screen red field is not a formality but the load-bearing constraint of the whole surface; `prefers-reduced-motion` already global (`theme.css:155-163`).
From **`manage-restyle.md`**: the 720px content cap; the three registers (an **outage** is `text-ink-muted`, a **thing she must act on** is `text-danger`, a **nothing-failed notice** is `text-warning-text`); `EmptyState` over a blank column — **and §4.1 records the one place this deck declines it, with the reason**; **never override a `packages/ui` component's own utility from the call site** (F15 **F-6** — `cn()` is a plain join, same-property Tailwind utilities resolve by stylesheet order and the consumer loses). ⚠ **That last one is why §2.1 exists**: it makes "just pass `outline-surface-raised` at the call site" not a solution.
From **`shift-board/design.md` Revision 2**: the poll may never write into a live region (**D11**); a live region is written only when its value actually changes (**F-7**); a tick may not repaint while a pointer is down (**F-8**); `{401,403}` are two states, not one.
From **`floor-staff-roles/design.md`**: **which control EXISTS is the rendered form of the authorization axes** — no disabled button, no lock glyph, no «אין לך הרשאה» line, no tooltip; the WORD carries the state and the colour never does; a display name takes a **bare `<bdi>`** and a numeric run takes `<bdi dir="ltr">` (**F-11**); pause/resume is one button whose **name** changes, never `aria-pressed`; `floor.pause*`, `floor.resume*`, `floor.paused*`, `floor.stale*`, `floor.updatedAt`, `floor.idleStopped`, `floor.refresh`, `floor.reload`, `floor.sessionEnded`, `floor.accessEnded`, `staff.loadFailed` are **shipped and reused unchanged**.
From **`fitting-rooms/design.md`**: **F-3** — no string may place a Hebrew preposition, article or agreeing verb immediately against a user-typed noun; `{{room}}` carries its own noun and its own gender («בחדר {{room}}» renders «בחדר חדר 2»). F37 interpolates `{{room}}` and inherits the rule whole. **F-4** — the shipped `Select` renders ≈43.6px and takes `className="min-h-11"` at the call site, which is not an F-6 violation because `Select` declares no `min-h-*` to lose.

### Explicitly NOT here — with the spec's reasons

| Not shipped | Reason |
|---|---|
| A sound, a vibration, a flash, a pulse, a shimmer | Spec Out-of-scope. A boutique fitting room is a quiet room; an autoplaying alarm is a WCAG 1.4.2 problem and a bride's afternoon. An animated emergency is also a vestibular trigger and a distraction from reading it |
| A countdown, a live elapsed counter, a ticking «כבר 12 שניות» | Spec **D15**. It would be auto-updating content inside a `role="alert"`, would re-announce on some ATs, and would drag SC 2.2.2 back onto a region whose whole **D11** argument is that it has nothing to pause. The overlay shows an **absolute** «מאז 11:20» through `jerusalemTime`, which never subtracts |
| A `<dialog>` / `showModal()` / `inert` on the console | Spec **D15**. Each of the three moves focus **by definition**, and this repo has shipped a focus bug four times (F56, F34, F57, F36's stale closure) |
| A backdrop-dismiss on the red field | §2.3. A pocket press must not close an emergency |
| A "1 of 3" counter, a carousel, an auto-scroll to the newest card | §2.5 |
| A severity, a priority, a per-role SLA, a response-time report | Spec Out-of-scope; **D1** declines the columns and **D2** the index |
| A second pause control, a second freshness row, a second SC 2.2.2 mechanism on the board | Spec **D16**: `SosCentre` is a **child**. F36's **D15** already ruled two is the answer and *"three would start to be a defect"* |
| A fourteenth nav section, a «קריאות» row, an `App.tsx` section change | Spec **D11**: the alerts are not a destination, they are an interruption |
| A customer's name, anywhere on this payload | Spec **D10** — the feature's largest privacy decision, and the app-level poll is exactly why |
| An un-accept verb, an auto-resolve, an auto-expire | Spec Out-of-scope. §2.3 records the consequence honestly and §11 **F-2** carries the residual |
| A browser push, a service worker, an SMS | #32 and the 2026-07-31 ruling: **in-app only** |

---

## 1. The normal state — and it is the only state that renders nothing

**About 100% of the time this feature is invisible, and that is a design requirement rather than a happy accident.** A staffer opens the console fifty times a shift and never sees a page. If the SOS machinery costs her anything at rest — a permanent banner, a bell with a zero on it, a red strip, an empty list card taking a third of the floor screen — she learns to read past the whole region, and the one time it fires she reads past that too.

| Section | What SOS costs at rest |
|---|---|
| The other **eleven** sections | **Nothing. `SosOverlay` renders `null`** — no DOM, no landmark, no live region, no focus consequence, no tab stop. The only trace is one poll every five seconds, which is §7's honest cost and nothing a person can see |
| `board`, `floor` | **One heading row.** «קריאות עזרה» as an `h3` with the «קריאה לעזרה» trigger at its inline-end, and one muted line under it. **No `Card`, no `EmptyState`, no list container** — §4.1 does that arithmetic |

⚠ **`SosOverlay` renders `null` in TWO states and they are not the same state.** No alerts at all, and alerts exist but none is `for_me` (a shift manager watching a seamstress-to-seamstress page for its first thirty seconds). Both render nothing; the second is what stops her being interrupted by every page in the boutique and learning within a day to dismiss them unread (spec **D6**). It is also why **the escalation changes no audience** — she could already *see* that alert in the SOS centre from second zero — it changes only whether it **rises**.

---

## 2. The alert overlay — mobile 375 first, because that is the phone in her apron

⚠ **The diagrams in this deck are drawn LEFT-TO-RIGHT, for legibility in a Markdown file. The rendered pages are RTL** (`lang="he" dir="rtl"`). In the shipped console every run inverts: **inline-start is the physical RIGHT, inline-end is the physical LEFT.** The raiser's name starts at the physical right; a `justify-end` control row puts its buttons at the physical **left**; the floating affordance in §2.7 sits at the physical **left** edge. This deck ships **no prototype**, so these ASCII blocks are the sole visual source — a builder implementing the drawn order ships a mirrored overlay that passes axe, passes every named vitest assertion, and reads wrong to the only users who will ever see it. **It is F57's §1 and F36's §1 warning, repeated a third time because this surface is the one whose users are running.**

### 2.1 ⚠ The red is the FIELD. The card is paper. — this CORRECTS spec D15, and the arithmetic is why

Spec D15 says: *"The red is `bg-danger` + `text-surface-raised` — the pair the shipped error toast already uses (`Toast.tsx:46-48`), so the overlay inherits the product's one AA-checked red-on-light rather than inventing a red at build time."* **The token choice is right and is kept. The surface it is applied to cannot be the one the cards sit on**, and the reason is four measured numbers, not a preference.

`--color-danger` is `#A03232` (tokens.md). Against it:

| Foreground | Where it would be used | Contrast on `#A03232` | Verdict |
|---|---|---|---|
| `--color-surface-raised` `#FFFFFF` | the field's own text | **7.00:1** | ✓ — the ledger's existing `Button danger` row |
| `--color-ink` `#2B2118` | **every shipped `Button secondary` and `ghost` label**, every `Badge neutral` | **2.25:1** | ✗ — fails AA text |
| `--color-focus` `#7F612B` | **the one focus ring in the product**, `focusRing`, drawn at `outline-offset-2` i.e. **on whatever is behind the control** | **1.22:1** | ✗ — **invisible**, and it is the *only* focus indicator this console has |
| `--color-danger` `#A03232` | `Button danger`'s own fill | **1.00:1** | ✗ — the emergency's most natural button disappears |

Every shipped `packages/ui` control assumes a light surface. `secondary` is `border border-ink bg-transparent text-ink`; `ghost` is `bg-transparent text-ink`; `danger` is `bg-danger text-surface-raised`; every `Badge` variant is a border plus coloured text. **Put the ack control directly on `bg-danger` and the product's whole component vocabulary either fails contrast or vanishes** — and `focusRing` at 1.22:1 is a WCAG 2.4.7 failure on an emergency control, on a surface where IS 5568 is legally binding, **that axe cannot report**: its contrast rule computes an element against its own background and does not model an `outline` drawn on a parent.

**And the obvious patch is not available.** Passing `className="focus-visible:outline-surface-raised"` at the call site is exactly `manage-restyle.md`'s F15 **F-6**: `cn()` is a plain join, both classes set `outline-color`, and which one wins is decided by the order Tailwind emitted them in the stylesheet — not by the order in the `class` attribute. The consumer loses, non-deterministically, on the focus ring of an emergency control.

> **RESOLUTION: `SosOverlay` paints the whole viewport `bg-danger`; each alert renders as a `bg-surface-raised` card on it.**

Full-screen red is preserved literally — the field fills the viewport at every width, edge to edge, and there is no width at which it reads as a band or a toast. What changes is that the **words and the controls sit on the product's own paper**, so `text-ink` reads at ≈16:1, `focusRing` reads at **5.76:1 on white** (tokens ledger), and every shipped variant behaves as shipped with no override anywhere. The card reuses `Modal`'s exact skin — `rounded-md bg-surface-raised p-6 shadow-lg` (`Modal.tsx:44-46`) — because the overlay card **is** the product's "on top of everything" surface even though it is deliberately not a `<dialog>`.

**The red is still doing its job, and its job was never to be a text background.** It is the thing visible from across a room, through a doorway, at arm's length in an apron — an unmistakable field. The information is words on paper, exactly as it is everywhere else in this console. And law 2 is satisfied by construction: **the red is emphasis over information that is already words**, which is the sentence spec D15 itself uses.

*Two ledger rows are added at this gate and both are negative:* **ink on danger 2.25:1 ✗** and **focus on danger 1.22:1 ✗**. They are recorded so the next feature that wants a coloured field meets the measurement rather than the absence.

### 2.2 One rising alert, 375 — what she must read while walking

```
+==================================================+   <div
|  fixed inset-0 z-40 bg-danger overflow-y-auto     |    className="fixed inset-0 z-40 bg-danger
|  overscroll-contain p-4                           |                overflow-y-auto overscroll-contain p-4">
|                                                   |
|  +---- card: bg-surface-raised rounded-md ----+   |   Modal's skin, NOT a <dialog>
|  |      p-6 shadow-lg, max-w-720 mx-auto      |   |
|  |                                            |   |
|  |  ┌ role="alert"  ─────────────────────┐    |   |   ⚠ WRITE-ONCE. Text byte-identical
|  |  │                                    │    |   |     from mount to unmount (AC16)
|  |  │  דנה כהן קוראת לעזרה                │    |   |   text-xl font-semibold text-ink
|  |  │                                    │    |   |     name in a bare <bdi>
|  |  │  חדר 2                              │    |   |   text-xl font-semibold text-ink
|  |  │                                    │    |   |     BARE LABEL, no prefix (§2.4),
|  |  │                                    │    |   |     preceded by a <span className="sr-only">
|  |  │                                    │    |   |     «מיקום» INSIDE the region (DC-4)
|  |  │  צריך סיכות                          │    |   |   text-lg text-ink, bare <bdi>
|  |  └────────────────────────────────────┘    |   |     ABSENT when she typed nothing
|  |                                            |   |
|  |  מאז 11:20                                  |   |   ⚠ SIBLING, outside the region.
|  |                                            |   |     text-sm text-ink-muted,
|  |                                            |   |     time in <bdi dir="ltr">
|  |  +------------------------------------+    |   |
|  |  |          אני מגיעה                   |    |   |   Button primary lg fullWidthMobile
|  |  +------------------------------------+    |   |     48px, FIRST in DOM
|  |                            [ הסתרה ]       |   |   Button ghost md, justify-end
|  +--------------------------------------------+   |
|                                                   |
+==================================================+
```

**Reading order is the walking order, and nothing else may come before it.**

| # | Line | Why it is where it is |
|---|---|---|
| 1 | **WHO** — «דנה כהן קוראת לעזרה» | The one thing that tells her whether to run. A colleague's name is also the only identity on this surface: the raiser **is** the person in the room, which is spec D10's argument for why no customer's name is needed here at all |
| 2 | **WHERE** — «חדר 2» | Which curtain. `text-xl` because it is the other half of a glance, not a detail |
| 3 | **WHAT** — «צריך סיכות» | What to bring. `text-lg` because she reads it on the way, not from across the floor. **Absent, not blank, when there is no note** |
| 4 | **WHEN** — «מאז 11:20» | Muted, small, outside the announced region. It is triage information for a second responder, not an instruction |

**Sizes are the token scale and nothing else** (law 5): `--text-xl` = 1.4375rem/1.35, `--text-lg` = 1.1875rem/1.5, `--text-sm` = 0.875rem/1.5. ⚠ **`font-body` at `font-semibold`, not `font-display`**, even at `text-xl`: `tokens.md` files `--text-xl` under "section headings (display font)", but Frank Ruhl Libre is the luxury serif voice and Assistant at 600 is measurably faster to read at a glance in Hebrew. This is a usage note in the tokens table, not a law; law 5 (every size from tokens) is obeyed.

**No truncation and no ellipsis on a name, a room label or a note, ever** (spec D18). All three wrap. A 295px card that abbreviates makes two staffers look like one and a room label look like another room.

**Arithmetic at 375**: 375 − 2×`--space-4` (the field's `p-4`) = **343** of card; − 2×`--space-6` (the card's `p-6`) = **295** of content. That is the same 295 a room tile has, so the two surfaces wrap at the same widths and a builder can reuse F36's judgement. Card height ≈ 24 + 31 + 29 + 29 + 12 + 20 + 16 + 48 + 12 + 44 + 24 ≈ **265px**.

### 2.3 The two controls — and the tension the ruling creates, resolved

The requirement is **"large, unmissable, one-handed-tappable"** and **"impossible to hit by accident while pocketing the phone."** Those fight, and the fight is real: the ack is deliberately **not** confirm-gated (an emergency acknowledgement behind a two-step is the wrong instrument), and spec Out-of-scope forbids an un-accept verb, so an accidental accept is not directly reversible.

**«אני מגיעה» — `Button variant="primary" size="lg" fullWidthMobile`.** Gold fill, ink label, **6.41:1** (tokens ledger), `min-h-12` = 48px, full-bleed across the card's 295px at 375 and auto-width from `sm` up. First in DOM, therefore **first reached by Tab once focus is in the overlay** — reaching «אני מגיעה» costs one Tab from the card container and hiding costs two. ⚠ **DC-1: that is deliberately NOT the same as "the default outcome of a keypress inside the overlay is accepting the emergency".** MOVE A fires precisely when `activeElement` is `<body>`, i.e. precisely when the next Space is a page scroll — so parking focus ON the ack would convert an involuntary keypress into an **irreversible** accept (there is no un-accept verb) sitting on top of the two-minute stall hole in **F-2**. MOVE A and MOVE C therefore land on the **card CONTAINER**, where the default outcome of a keypress is nothing. §9.4's Esc route-in is the explicit **exemption** and lands on the control, because a deliberate keypress is a different act from an involuntary arrival.

*Declined `variant="danger"`:* red-on-red is invisible on the field and, on the card, red is this product's **destructive** register (delete a room, cancel a booking). «I am coming» is the most affirmative act on the screen and must not wear the colour of the most destructive one. *Declined `secondary`:* an ink outline is the room tile's "ends the current state" weight, not an emergency's. Gold is the console's one filled, high-contrast, AA-verified affirmative fill, and this is the one screen that most deserves it.

**«הסתרה» — `Button variant="ghost" size="md" fullWidthMobile={false}`, second in DOM, its own line, `justify-end`.** Lowest visual weight in the vocabulary, 44px, and physically separated from the ack by a full row.

**The six things that make an accidental accept improbable, and none of them is a second tap:**

1. **The red field is inert.** There is no handler on it. A tap anywhere except the two controls does **nothing at all** — no dismiss, no accept, no scroll-jack. Stated as a rule because "tap the backdrop to dismiss" is the reflex a builder brings from every modal library, and here it would let a pocket press close an emergency.
2. **Geometry.** The nearest control edge is ≥ `--space-4` + `--space-6` = **40px** from any screen edge. Pocket and palm contact is an edge-and-corner phenomenon; a 48px target floating 40px inside every margin is a poor accidental target and an excellent deliberate one.
3. **Activation is a `click`, never a `pointerdown`.** No `onPointerDown`, no `onTouchStart`, anywhere in this feature. A native `<button>` fires on press **and** release over the same target.
4. **A pocketed phone is a dark screen, and a dark screen has no overlay.** `usePoll` pauses on `document.hidden` — the ceiling Risk 1 names honestly is, for this one hazard, the guard. The overlay cannot be mis-tapped on a locked device because it is not being rendered to one.
5. **The involuntary arrival never lands on the control.** MOVE A and MOVE C focus the card `<article>`, whose default keypress outcome is nothing at all (DC-1, above). The only focus move that lands on «אני מגיעה» is the one she asked for by pressing Esc.
6. **And if it happens anyway, it is not permanent silence.** `_stalled` re-rises the card for every elevated caller two minutes after an accept nobody followed through on (spec D6). ⚠ **That two-minute window is a real hole and §11 F-2 records it as a finding rather than as reassurance** — the honest statement is *an accidental accept costs up to two minutes of a raiser believing help is coming*, and `STALLED_AFTER` is one module constant if the pilot says two minutes is too long.

### 2.4 The escalated state, and how a shift manager tells it from a fresh one

```
|  |  ┌ role="alert" — UNCHANGED, never re-written ┐  |
|  |  │  דנה כהן קוראת לעזרה                        │  |
|  |  │  חדר 2                                      │  |
|  |  │  צריך סיכות                                  │  |
|  |  └─────────────────────────────────────────────┘  |
|  |                                                   |
|  |  ללא מענה                                          |   ⚠ SIBLING. text-base
|  |  מאז 11:20                                         |     font-semibold text-danger
```

**Four distinguishers, and the first three cost nothing to build:**

1. **A word.** «ללא מענה» in `text-danger font-semibold`, in a **sibling node outside** the `role="alert"` region (spec D15, AC16). `--color-danger` on white is **7.01:1 ✓** (DC-10). Never a border colour, never a background swap, never a second `Badge` — F51's shipped rule (*"The WORD carries the role; the colour never does"*) and `FloorPanel.tsx:42`+`:735`.
2. ⚠ **The word carries no number, and that is spec D17's correction, not a stylistic preference.** «ללא מענה כבר 30 שניות» would state a flat thirty seconds to a shift manager looking at a four-minute-old page, because `escalated` is an unbounded boolean. The card already carries «מאז 11:20» for the when; `SosCentre` carries `elapsedLine` for the how-long.
3. **The ordering already agrees with the escalation by construction.** Cards render **oldest first** (spec's state table), and an escalated alert is >30s old, so escalated cards are at the top of the stack without a second sort and without a special case. Say it once, build nothing.
4. ⚠ **For most escalations, the escalation IS the arrival — and it announces.** A name-targeted page is not `for_me` for a shift manager until `escalated` flips, so at t=30s the card **mounts on her device for the first time** and its `role="alert"` announces it. Escalation on an **already-mounted** card (a role-targeted page she was already seeing) is silent — the clause appears in the sibling, and `role="alert"` is `aria-atomic`, so writing into the region would re-announce the whole card assertively for a fact that changes nothing about what she has to do. **Those two behaviours look inconsistent and are not**: the second person is already looking at it.
   And a card she **dismissed** before it escalated re-rises exactly once, because the dismiss set is keyed `${id}:${escalated}:${stalled}` (spec D15) — a re-rise is a fresh mount, so it announces too. **One rule covers all three: an alert announces when it arrives on your screen, and never otherwise.**

**The stalled state is the same shape with a different word.** «אין תזוזה מאז שאושרה», same sibling, same register, same re-rise-once rule. It is the only thing standing between «דנה מגיעה» and an emergency nobody is answering (spec D6).

### 2.5 A second alert arriving while the first overlay is open

```
+==================================================+
|  [ card 1 — 11:20 · דנה · חדר 2 ]                 |   oldest first
|                                                   |
|  [ card 2 — 11:24 · נועה · הבמה ]                  |   mounts BELOW, announces ITSELF only
|                                                   |
|  [ card 3 — 11:25 ]  ← top edge visible at y=578  |   the white sliver is the scroll cue
+==================================================+
```

- **One `role="alert"` per card, keyed by `alert.id`.** A second page mounts a second region and **does not touch the first** — which is exactly why the spec refuses one `role="alert"` wrapping the list: with a wrapper, `aria-atomic` would re-announce every card, so the seamstress hears again about the emergency she already answered.
- **Oldest first, always.** The longest-waiting emergency is the one to answer. The newest card therefore mounts at the **bottom**, which is the correct trade: it announces itself regardless of where it is, and re-sorting or promoting it would move a card out from under a travelling finger.
- **No auto-scroll to the new card.** A scroll under a reader mid-sentence is a repaint she cannot follow and a WCAG 3.2.x surprise on the one screen where surprises are expensive.
- **No counter, no "1 of 3", no carousel, no pagination.** The field is `overflow-y-auto overscroll-contain` and the stack scrolls. `overscroll-contain` so a flick at the end of the list does not scroll the console **behind** the overlay, which she cannot see and would have to undo.
- **The scroll affordance is arithmetic, not a chrome element.** Field `p-4` = 16, cards ≈265px, `gap-4` = 16 → card 1 at y=16, card 2 at y=297, card 3 at y=578. In a 667px viewport the third card's top ~89px is visible: a white sliver on red, which is the standard "more below" cue and costs nothing. **The stack must therefore not carry extra bottom padding beyond the field's own `p-4`** — that is the one layout constraint this cue depends on.
- **Three simultaneous alerts in one boutique means something has gone very wrong**, and a scroll is the right cost for a state that should never occur. No design effort is spent past three.

### 2.6 The overlay is visually blocking and interactively non-blocking — and what that costs

This is spec D15's resolution of *"impossible to miss"* against *"must not steal focus"*, and both halves are stated because only one of them is a benefit.

- **A pointer user's next tap lands on the overlay** and she dismisses or accepts in one tap, with no state lost anywhere behind it.
- **A keyboard user's caret never moves.** Her form is intact, her keystrokes are not lost, and the alert is **still announced**, because `role="alert"` interrupts a screen reader **without** taking focus — the entire reason that role exists, and why it and not `alertdialog` is correct here.
- ⚠ **And the hazard that asymmetry creates: she is now typing into a field she cannot see.** `inset: 0` covers the viewport, so a receptionist mid-phone-number has a live caret, no visible input, no visible label and no visible validation. **The trade is taken deliberately** — the ruling says *full-screen red*, and a band is missable on a 375px phone held inside a curtain, which is the entire scenario. **Losing her keystrokes is worse than obscuring them for the two or three seconds it takes to press Esc twice or tap «הסתרה».** §9.3 bounds it; Risk 6 hands F58 «typing behind the overlay» as a named real-browser case, because whether a caret under a fixed overlay is genuinely still usable is precisely what jsdom answers by fiat.

**`aria-hidden` is set on nothing, deliberately.** The console behind the overlay is still there for a screen reader — she may be mid-task, and the alert is an interruption, not a replacement.

**Stacking, verified against the tree:** the overlay is `z-40`; `ToastProvider`'s container is `fixed … z-50` (`Toast.tsx:40`), so an accept/resolve toast renders **above** the field and is readable; a native `<dialog>` opened with `showModal()` is in the **top layer**, above every `z-index` in the document, so `SosRaiseDialog` and F36's three dialogs are visually above the overlay **for free** — which is what makes MOVE A's `document.body` guard visually coherent and not merely focus-coherent. `z-40` is already the console-adjacent convention (`BookingCTA.tsx:16`); `apps/manage` has no other positioned layer.

### 2.7 When the overlay renders something other than the field: the strip and the affordance

Both live in **one** fixed container at the bottom edge, so they can never collide and no offset arithmetic exists:

```
                                    (console renders normally above)
+--------------------------------------------------+
|                          [ קריאות עזרה · 2 ]       |   Button danger md — the re-open
|  ערוץ הקריאות אינו פעיל.        [ רענון הדף ]       |   role="alert" strip + Button secondary
+--------------------------------------------------+   pointer-events-none fixed inset-x-0
```

**The channel strip** — `sos.channelDown` — renders on a **403 on the poll** (terminal `access`, and it is emphatically **not** a logout) and on a loop **backed off beyond one tick**. `border-t border-danger bg-surface-raised p-3`, the text `role="alert" text-sm text-ink`, the control `Button variant="secondary" size="md"` — F57's terminal-panel shape (`FloorPanel.tsx:446-456`) reused whole, and `BookingCTA.tsx:16`'s fixed-bottom-bar shape reused for the container. ⚠ **It is the only app-level surface this feature has, so it is the only thing that can say the channel is dead on the eleven sections with no `SosCentre`.** «Nothing renders» is not an acceptable state for an emergency receiver that has stopped receiving.

**The re-open affordance** — `sos.dismissedCount` — renders whenever the dismiss set holds a **still-live** alert. `Button variant="danger" size="md"` (white on red, **7.01:1 ✓**; its focus ring is drawn on the console's cream at 5.57:1 ✓), ≥44×44, and it re-opens the overlay. Without it, a dismissal on any of the eleven sections with no SOS centre is **total and permanent** — and the role-targeted route is the raise dialog's first and default option, so that is the common path, not an edge.

**A 401 renders neither.** The overlay renders nothing, the loop stops, `onSessionEnded` fires **exactly once**, and `App` calls the `setStaff(null)` it already has (`App.tsx:142`, `:164` — the only two places `staff` is ever cleared, verified) → `LoginForm`. There is no fetch interceptor and `onNavigate` is `setSection` (`:196`), so without the callback the console keeps rendering a working-looking shell over a dead channel.

---

## 3. What the raiser sees after raising

She is the one person the overlay never rises for (spec D7): she is holding a bride's corset with one hand and her phone with the other, and a full-screen red interruption caused by her own tap would be the product shouting at the person who asked for quiet. So her feedback is **three things, in order**, and each answers a different question.

| # | When | Where | What |
|---|---|---|---|
| 1 | The instant the raise returns, `rerouted: false` | the dialog closes; `FloorPanel`'s **one** `role="status"` region | «הקריאה נרשמה.» ⚠ not «נשלחה» — the `/נשלח\|תישלח\|בדרך/` ban |
| 2 | The instant the raise returns, `rerouted: true` | ⚠ **the dialog STAYS OPEN**, body replaced, one «הבנתי» | «{{name}} לא מחוברת עכשיו. הקריאה עברה למנהלת המשמרת.» |
| 3 | Within one 2-second tick of somebody accepting | her own row in `SosCentre` | the `Badge` becomes «מטופלת» and the row carries «{{name}} מגיעה.» |

**Why #2 is a dialog and not a cue, restated because it is the one message the ruling mandates.** A transient polite cue written into `FloorPanel`'s single `role="status"` `<p>` — whose text the next cue overwrites — delivered at the exact moment a native `<dialog>` closes and focus moves, is the classic case assistive tech drops or defers. It is also **unrecoverable**: `rerouted` is deliberately a fact about the **request** and not about the row (spec D10), so **no `SosCentre` row can ever show it again**. Miss it and she believes Dana was paged, Dana was never paged, and nothing on any screen will ever say otherwise. So it is an **explicit acknowledgement** — the correct interaction weight — and the mutation is: close unconditionally, and it must go red.

⚠ **«nobody in that role is on shift» is, after the 2026-07-31 ruling, always about a NAMED colleague.** The shift-manager route can never have an empty audience: `ELEVATED_ROLES = {owner, shift_manager}` and F51's last-owner advisory lock holds *"at least one live owner"* (`auth/staff.py:9-34`). So the sentence names a person, and it is worded for the negative case on purpose — a live `sessions` row proves **a session, not a screen** (12-hour TTL, nothing revokes on going home), so `rerouted: false` claims only "she has not signed out". **The thirty-second escalation, not the reroute, is what covers a live session on a sleeping phone**, and the copy does not pretend otherwise.

⚠ **What she does NOT see, recorded rather than assumed:** step 3 renders only in `SosCentre`, which exists on **2 of 13** sections. A raiser who navigates to `bookings` while waiting loses her only view of who is coming — the overlay will not rise for her own page, and no toast fires because the accept is somebody else's action on somebody else's device. Both raise triggers live on the floor section, so she is there by construction and has no reason to leave; **§11 F-3 records the ceiling and its trigger rather than building a fourth surface for it.**

---

## 4. The SOS centre — a panel that is a trigger 99% of the time and a list the rest

### 4.1 Empty — which is what it looks like almost always

```
|  קריאות עזרה                      [ קריאה לעזרה ]  |   h3 tabIndex={-1} · Button danger md
|  אין עכשיו קריאות פתוחות.                          |   text-sm text-ink-muted
|                                                   |
|  חדרי מדידה                        [ ניהול חדרים ]  |   ← F36's, unchanged, below
```

**No `Card`, no `EmptyState`, no list container when the list is empty — and that is a deliberate divergence from the house rule.** `manage-restyle.md` prefers `EmptyState` over a blank column, and `RoomsPanel` uses it. `EmptyState` renders `py-12` around a `font-display text-xl` centred title: ≈**140px** of permanent vertical real estate, visually the loudest block on the floor screen, saying *there is no emergency*. On a screen a staffer reads fifty times a shift, that makes the absence of an emergency the centre of the floor. The condition `EmptyState` exists for is *content that should be here and is not*; **no alerts is not a missing thing, it is the desired state.** So: one heading row plus one muted line, ≈**64px**, and the `Card` appears only when there is something to put in it.

**The heading row is F36's shipped shape one panel up** — `<div className="flex flex-wrap items-center justify-between gap-3">`, heading at inline-start, trigger at inline-end — so the two panels' chrome is identical and a builder writes it once.

**The trigger is rendered for all five roles and is never absent.** Unlike every other control in this program, it encodes no permission: any of the five may raise, always, and the raise has exactly three failure modes, none of which is about the state of the boutique (spec D3).

### 4.2 Populated

```
|  קריאות עזרה                      [ קריאה לעזרה ]  |
|  +------ Card (surface, p-6) -----------------+   |
|  | <ul class="divide-y divide-border">        |   |   F36's exact list shape
|  | ┌ <li data-alert-id> ──────────────────    |   |
|  | │ דנה כהן                       [ פתוחה ]   |   |   raiser bare <bdi> semibold ·
|  | │ חדר 2                                    |   |     ONE Badge, danger
|  | │ צריך סיכות                                |   |
|  | │ כבר 3 דק'                                 |   |   elapsedLine — F36's, REUSED
|  | │ ללא מענה                                  |   |   text-danger semibold WORDS,
|  | │              [ אני מגיעה ] [ ביטול הקריאה ] |   |     never a second Badge
|  | └                                          |   |
|  | ┌ נועה לוי                      [ מטופלת ]  |   |
|  | │ הבמה                                     |   |
|  | │ מיכל מגיעה.                               |   |   who is coming — the raiser's answer
|  | │ אין תזוזה מאז שאושרה                       |   |   the stall word, same register
|  | │                              [ נפתר ]     |   |
|  | └ </ul>                                    |   |
|  +--------------------------------------------+   |
```

- **Oldest first — the same order as the overlay**, so the two screens never disagree about which emergency is next.
- **Exactly one `Badge` per row and it is the status word** (F15's rule, F36's **P-2**, F57's **P-2**): «פתוחה» → `Badge variant="danger"`, «מטופלת» → `Badge variant="neutral"`. Escalation and stall are **words beside it**, never a second pill and never a colour change on the first.
- **`elapsedLine` is F36's shipped helper, reused unchanged** — `rooms.elapsed` / `rooms.elapsedJustNow` across namespaces, deliberately, because `lib/elapsed.ts` hardcodes those keys and a second elapsed implementation is what spec D17's no-date-library rule forbids.
- **Which control EXISTS is the rendered form of the permission rules** (F57's shipped comment, `FloorPanel.tsx:639-644`), and it matters more here than anywhere: a **403 is terminal for the whole floor screen** (`usePoll.terminalOf` → `"access"`), and for the three floor roles that is the entire product going dark.

| Control | Rendered only when |
|---|---|
| «אני מגיעה» | `status === "open" && (target_staff_user_id === selfId \|\| ELEVATED.has(role))` |
| «נפתר» | `raised_by === selfId \|\| accepted_by === selfId \|\| ELEVATED.has(role)` |
| «ביטול הקריאה» | `status === "open" && (raised_by === selfId \|\| ELEVATED.has(role))` |

**No disabled buttons, no lock glyphs — absence.** A seamstress looking at a colleague's alert she was not named in sees a row and no controls at all.

- **The raiser's own row shows her own name and no accept control** (spec D7 — she may not accept her own page; she has cancel and resolve). *Declined a «הקריאה שלך» marker*: with one alert there is nothing to scan, with three her name is right there, and the controls already differ. One fewer key; add it if a pilot raiser ever asks which row is hers.
- ⚠ **The panel freezes while `FloorPanel` is paused**, from a snapshot ref, exactly as `RoomsPanel` already receives `paused` — because the pause control is named «השהיה — עדכון הצוות» and governs the region it sits in, and after this feature that region contains a list fed by a loop the pause does not stop. **The overlay keeps rising while the board is paused, and that is the safety property: pausing a VIEW must never disable the CHANNEL.**
- ⚠ **One exemption from the freeze: an alert THIS device just raised.** Both raise triggers are on the floor section, the overlay never rises for her own page, and a frozen list will not add it — so a staffer who paused the board and then raised would see her own new alert **nowhere**. The raise's response alert is merged into the frozen snapshot. The freeze exists so the pause control does not lie about **the poll**; a row this device created one tap ago is not the poll moving underneath her.

---

## 5. The raise control on a room tile, and the dialog behind it

### 5.1 The tile's fourth control

```
| ┌ חדר 2                          [ תפוס ]    |
| │ דנה כהן · תופרת · לקוחה מיכל · כבר 42 דק'    |
| │ שמלות בחדר …                                |
| │  [ קריאה לעזרה ] [ הוספת שמלה ]              |   ← line 1: danger FIRST, then ghost
| │           [ העברה לעמיתה ] [ שחרור ]         |   ← line 2 (העברה elevated only)
| └                                             |
```

**Rendered only when `assignment.staff_user_id === selfId`** — the tile of the room she is standing in, which is what prefills `fitting_room_assignment_id`. Never on a colleague's tile: raising on somebody else's behalf is not a thing (spec D3, and the server refuses a foreign assignment id by storing `NULL` rather than by failing).

**`Button variant="danger" size="md" fullWidthMobile={false}`, FIRST in the action row's DOM.** DOM order is tab order is wrap order, and the emergency control must be first in all three. Its focus ring is drawn `outline-offset-2` on the `Card`'s paper — gold-text on `--color-surface` = **5.08:1 ✓** — which is the §2.1 problem *not* recurring, precisely because the button sits on paper rather than on a red field.

⚠ **Red on this tile is the console's first non-destructive `danger`, and the collision is worth one sentence rather than a new variant.** Everywhere else red means *destructive*. Here it means *this act has consequences you should mean* — which is the same underlying claim, and it is the only variant that is unmistakable at a glance in a hurry. `secondary` is unavailable: F36's shipped rule is **one `secondary` per tile and it is the act that ends the tile's current state** («שחרור»). `ghost` would make the emergency control indistinguishable from «הוספת שמלה».

**Mis-tap is a solved problem here and needs none of §2.3's machinery, because the trigger cannot page anybody.** It opens a dialog with a default target and a separate «שליחת הקריאה». A mis-tap costs one Esc. **That is why this control can be as large and as prominent as it likes** — the confirm-versus-speed tension exists only on the ack, where a second tap would be wrong.

**375 arithmetic**: 295px of tile. «קריאה לעזרה» ≈ 88 + 32 padding = **120px**; «הוספת שמלה» ≈ **112px**; 120 + 12 gap + 112 = **244 ≤ 295** ✓, so line 1 holds two. «העברה לעמיתה» + «שחרור» take line 2 for an elevated caller; a seamstress on her own tile has three controls and two lines. **The row wraps; it never shrinks, and `min-h-11` is not negotiable on any of the four** (spec D18). `flex flex-wrap justify-end gap-3` is already the shipped container (`RoomsPanel.tsx:838`) and needs no change.

⚠ **`FloorPanel`'s `holdRef` gains one more reason and no code.** Its comment already records that F36 made it carry far more than the ~20px it was built for; an SOS-centre row appearing **above** the rooms panel moves every tile below it, directly under a travelling finger. The mechanism is unchanged; the comment gains the case.

### 5.2 `SosRaiseDialog` — the shipped `Modal`, three fields, one send

```
+-- <dialog> (top layer, w-[min(28rem,100vw-2rem)]) --+
|  קריאה לעזרה                                          |   Modal's own h2
|                                                       |
|  למי לקרוא                                             |   Select LABEL (not a placeholder)
|  [ מנהלת המשמרת                              ▾ ]      |   FIRST and DEFAULT, value ""
|      נועה לוי                                          |   every other live staffer
|      מיכל ברק — בהפסקה                                 |   F36's on-break hint shape
|                                                       |   ⚠ HERSELF EXCLUDED
|  מה צריך                                               |   Input LABEL
|  [ ................................. ]  לא חובה        |   maxLength = 120
|                                                       |
|                          [ ביטול ] [ שליחת הקריאה ]    |   ghost + secondary
+-------------------------------------------------------+
```

- **`Select` and `Input` from `@boutique/ui`, named — not "a native `<select>`".** `Select` requires `label: string`, wires `useId()` → `htmlFor`, `aria-invalid`, `aria-describedby` and `focusRing`. Written as a bare element a builder loses the label association **and** the focus ring on a legally binding surface, **and axe sees the missing label but not the missing ring** (F36's D16, same sentence, same reason). Both carry `className="min-h-11"` per F36's **F-4**, which is not an F-6 violation because neither declares a `min-h-*` to lose.
- **«מנהלת המשמרת» first and default** because it is the route that can never have an empty audience and the one a staffer under pressure should not have to think about. **Herself excluded** from the list — the server refuses a self-target with a 400, and excluding it *prevents* the error rather than explaining it (F36's `RoomHandoverDialog` argument).
- **A colleague on a break is annotated, not excluded.** «{{name}} — בהפסקה» reuses F36's shipped `rooms.handoverOnBreak` shape. A seamstress on a five-minute break is exactly who you want for a corset back.
- **The note is optional and its cap is 120** (`MAX_SOS_NOTE_LENGTH`, mirrored through the existing `id="manage-floor"` parity param). `maxLength` on the `Input` so over-length is unreachable client-side; the server's 400 exists anyway and has a string.
- **Footer is the house pattern**: `ghost` dismiss + `secondary` confirm (`manage-restyle.md`). The dialog has two buttons and the confirm is at the inline-end; it does not need a filled variant to be found.
- **Both triggers open this one dialog, and `FloorPanel` owns its open state** because it is the common parent of the tile trigger and the centre trigger.

**The four states that are not "open and typing":**

| State | What happens |
|---|---|
| **Sending** | «שליחת הקריאה» goes `loading`; `Button` is `disabled={disabled\|\|loading}` so the browser blurs it. Every other control stays live |
| ⚠ **Rerouted** (`rerouted: true`) | **The dialog does NOT close.** Body → «{{name}} לא מחוברת עכשיו. הקריאה עברה למנהלת המשמרת.»; footer → one «הבנתי». **MOVE E** focuses «הבנתי», because the button that had focus has just unmounted |
| ⚠ **The send FAILED** — 5xx, dropped connection, a wifi blackspot inside a curtain | **The dialog stays open with the note preserved**, and renders `sos.error.raiseFailed` = «הקריאה לא נרשמה. נסי שוב — או קראי בקול.» — **the only string in this console that names the manual fallback out loud**, because on this one screen `FALLBACK_ERROR_MESSAGE`'s bare «נסי שוב» is the wrong instruction. **MOVE F** focuses the alert. A retry costs one tap and may duplicate, which spec D2 rules **noise, not corruption** |
| **The tile's assignment was released underneath the open dialog** | The raise still succeeds; the server resolves `fitting_room_assignment_id` to `NULL`. **A page never fails over a stale room** (spec D3) |
| **An SOS overlay rises while this dialog is open** | Focus does not move — MOVE A's `document.body` guard resolves it with no extra code, and the `<dialog>` is in the top layer so it is visually above the field too. **Asserted, because accidental correctness is what a later refactor deletes** |
| **Esc while this dialog is open** | Closes the **dialog**, never the overlay. §9.4's capture handler is guarded on `document.querySelector("dialog[open]") === null` |

---

## 6. States — the single source for this feature

**The list may not shrink.** States inherited from `FloorPanel`'s poll (load, fail, stale, paused, idle, 401, 403) are **F57's, unchanged**, and govern `SosCentre` too.

### The overlay

| # | State | Trigger | What she sees | Region / focus |
|---|---|---|---|---|
| **S-none** | **No alerts — the normal state, ~100% of the time** | — | **`null`.** No DOM, no region, no landmark, no tab stop | nothing |
| **S-quiet** | Alerts exist, none is `for_me` | a seamstress-to-seamstress page, seen by a shift manager in its first 30s | **`null`.** She sees it in the SOS centre and is not interrupted | nothing |
| **S-one** | One rising alert | poll tick | §2.2 — one card, announced once | `role="alert"`; **MOVE A** iff `activeElement === body`, landing on the card **container** (DC-1) |
| **S-many** | Several rising | poll tick | §2.5 — oldest first, one region each, no auto-scroll | each announces itself, only itself |
| **S-esc** | `escalated: true` | 30s unacknowledged | §2.4 — «ללא מענה» in a **sibling**. A card dismissed before it escalated **re-rises once** | the region's text is **unchanged**; a re-rise is a fresh mount and announces |
| **S-stall** | `stalled: true` | accepted, unresolved 2 min | «אין תזוזה מאז שאושרה», same sibling, re-rises for elevated callers | as S-esc |
| **S-gone** | Somebody else accepted while it was up | next tick, `status !== "open"` | the card leaves. **No error, no message** — she did not lose a race, somebody answered | **MOVE C** (to the next card's **container**), or **MOVE B** |
| **S-mine** | This caller accepted | 200 | the card leaves; `SosCentre` shows «מטופלת» | **MOVE B/C via the `actedRef` fallback** — the tapped control was `disabled` mid-flight, so a real browser had already blurred it to `<body>` and `focusedCardId()` cannot answer. Plus a `role="status"` **toast** (§9.5), ⚠ **fired from an effect gated on `terminal === null`**, because `mutate` returns `null` on a terminal 401/403 exactly as it does on a success |
| **S-409a** | `SOS_ALREADY_ACCEPTED` | accept lost the race | in-card alert naming the owner — «דנה כבר מגיעה.» — or the `details`-less «מישהי אחרת כבר מגיעה.» The card stays until the next tick removes it | `role="alert"`; **MOVE D**, guarded |
| **S-409b** | `SOS_CLOSED` | accept on a resolved/cancelled alert | in-card alert «הקריאה כבר נסגרה.» | as S-409a |
| **S-404** | The alert is gone | accept on a swept row | in-card alert, **not terminal** | as S-409a |
| **S-hide** | Dismissed | «הסתרה» or Esc-from-inside | the card leaves **this device only**; the row is untouched, keeps escalating, comes back on reload | **MOVE B/C**; ⚠ while the set holds a live alert the overlay renders the **affordance**, never `null` |
| **S-401** | Session expired | 401 on a tick or an action | nothing renders, the loop stops, `onSessionEnded` fires **once** → `App`'s `setStaff(null)` → `LoginForm` | — |
| **S-403** | Role revoked | 403 on a tick | ⚠ **NOT a logout.** The persistent `sos.channelDown` strip (§2.7) | `role="alert"`, once |
| **S-down** | Backend down | backoff past one tick | the same strip. **«Nothing renders» is not acceptable for an emergency receiver that has stopped receiving** | as S-403 |
| **S-ghost** | The raiser was removed from staff mid-page | `raised_by_name: null` | «אשת צוות שאינה ברשימה קוראת לעזרה» + the room. The page is still answerable | as S-one |
| **S-noroom** | She was not in a room | `room_label: null` | «לא בחדר מדידה» in the WHERE slot | as S-one |
| **S-released** | The fitting ended while the page was open | server joins without a `released_at` filter | the room label **still renders**. «חדר 2» is still where to go | as S-one |

### The SOS centre

| State | Render |
|---|---|
| Initial load | `FloorPanel`'s existing `Skeleton` shape; the heading row is present, the list is not |
| **No alerts** | §4.1 — heading row + trigger + one muted line. **No `Card`, no `EmptyState`.** The panel never disappears; it is an entry point |
| One open | raiser, room, note, `elapsedLine`, «פתוחה», the controls she may use |
| Several | oldest first, same order as the overlay |
| Accepted by somebody else | «מטופלת» + «{{name}} מגיעה.»; the accept control is gone, resolve remains for raiser/acceptor/elevated |
| Accepted, acceptor's staff row removed | «מישהי כבר מגיעה.» |
| Escalated | «ללא מענה» as words beside «פתוחה» |
| Accepted and **stalled** | «אין תזוזה מאז שאושרה» as words beside «מטופלת». The row is otherwise unchanged; resolve is still the way out |
| Raised by me, unanswered | my own row, **no accept control** — `mayAccept` carries `alert.raised_by !== selfId`, mirroring the server's predicate, **and it applies to an ELEVATED raiser too**: without the term an owner's own page rendered «אני מגיעה» and one tap silenced the alert on every device for two minutes — cancel + resolve |
| **Any action SUCCEEDS** | the tapped control goes; **MOVE I** restores focus to the row's remaining control or to the panel's `<h3>`, never `<body>` |
| Raised by me while the board is **paused** | ⚠ **my new alert appears anyway** — the one exemption from the freeze (§4.2) |
| Cancel refused, 409 | «{{name}} כבר מגיעה. אפשר לסמן «נפתר» במקום.» — the remedy is one word over, and it is the honest one: a colleague is already walking to that curtain |
| Any action → 404 | «הקריאה כבר לא פתוחה. הרשימה תתוקן בעדכון הבא.» — **not terminal** |
| Any action → 403 | **terminal for the whole floor panel**, F57's shipped state. Unreachable by design, because the control would not have been rendered |
| Paused | the list **freezes** from a snapshot; the freshness line says «מושהה». **The overlay keeps rising** |
| Failed poll with rows on screen | rows kept, freshness marked stale, «רענון» — `FloorPanel`'s shipped behaviour |

### The raise dialog

open · target list loaded · **no colleagues at all** (only «מנהלת המשמרת», always valid) · note typed · at the 120 cap · sending · ⚠ **rerouted — stays open with «הבנתי», and the sentence is ANNOUNCED**: `<p id role="status">` plus `aria-describedby` on the ack, because `Modal` sets only `aria-labelledby` and MOVE E's destination is a button whose whole label is «הבנתי» · ⚠ **send failed — stays open, note preserved, `sos.error.raiseFailed`** · the tile's assignment released underneath · an assignment belonging to another staffer (resolves to `NULL`, the alert is still created) · an overlay rises while it is open (focus does not move) · Esc closes the dialog and not the overlay · cancelled-and-focus-returned via **`FloorPanel`'s own `sosTriggerRef`** (MOVE G).

**State precedence.** A mutation's response is the truth for its alert (it *is* a `SosAlert`). A poll's response is the truth for everything else. They cannot fight: the loop does not tick during a mutation and the mutation bumps the generation on settle.

---

## 7. Breakpoints — 375 / 768 / 1440

| Width | The overlay | The SOS centre | The tile |
|---|---|---|---|
| **375** (primary) | field `p-4`; card 343 wide, 295 of content; **«אני מגיעה» full-bleed** (`fullWidthMobile`), «הסתרה» on its own line `justify-end` | heading row wraps if the trigger does not fit; rows are one column | the action row wraps to **two lines**, «קריאה לעזרה» first |
| **768** | field `p-4`; card capped at **720** and centred; the two controls share one `flex justify-end gap-3` line, accept still first in DOM | rows put the controls at the inline-end of the same line as the text (`sm:flex-row sm:items-start`) | the four controls fit one line at 672 of tile |
| **1440** | **identical to 768.** The field is red across the full viewport; the card stays 720 and centred | identical | identical |
| Every width | the field is `overflow-y-auto overscroll-contain`; the stack is `mx-auto max-w-[720px] flex-col gap-4` | `FloorPanel`'s 720 cap (`ConsoleShell.tsx:84`) | — |

**One reading measure at every width, and the red does the scaling.** The console never exceeds 720px (`ConsoleShell.tsx:84`) and neither does this card — so on a 1440 desktop the emergency is a 720px document on a wall of red, which is more legible than a 1440px-wide line of text and is the same object she saw on her phone.

**`items-start`, not `items-center`, in a `SosCentre` row at 768** — a row's text block is three to five lines and its control row is one; centring floats the controls into the middle of the note. F36's divergence from F57 for the same height reason.

---

## 8. Component notes — exact tokens

| Element | Notes |
|---|---|
| Overlay field | `<div className="fixed inset-0 z-40 overflow-y-auto overscroll-contain bg-danger p-4">` — **no handler, no `onClick`, no backdrop-dismiss** (§2.3). Not a `<dialog>`, not `showModal()`, not `inert` (spec D15) |
| Card stack | `<div className="mx-auto flex w-full max-w-[720px] flex-col gap-4">` — **no extra bottom padding**, §2.5's scroll cue depends on it |
| Alert card | `<article className="rounded-md bg-surface-raised p-6 shadow-lg">` — `Modal.tsx:44-46`'s skin, reused; keyed by `alert.id` |
| The announced region | `<div role="alert">` wrapping **three** children and nothing else: who, where, note. ⚠ **Its text is byte-identical from mount to unmount** (AC16). The time, the escalation clause and the stall clause are **siblings after it** |
| WHO | `<p className="text-xl font-semibold text-ink">` with the name in a bare `<bdi>`; `sos.raiserGone` when `raised_by_name` is null |
| WHERE | `<p className="text-xl font-semibold text-ink"><bdi>{room_label}</bdi></p>`, or `sos.noRoom` as a plain line. ⚠ **Bare label, no prefix** — the boutique's own label already contains «חדר», so «בחדר {{room}}» renders «בחדר חדר 2» (F36 **F-3**). *Declined a «מיקום:» prefix*: it is register-wrong for an emergency and buys nothing the card's position does not already say |
| WHAT | `<p className="text-lg text-ink"><bdi>{note}</bdi></p>` — **the element is absent when the note is null**, never an empty line |
| WHEN | `<p className="text-sm text-ink-muted">{isolateLtr(t("sos.since", { time }), time)}</p>` — `jerusalemTime`, which **never subtracts** (`jerusalem.ts:35`, `FloorPanel.tsx:705-716`'s shape) |
| Escalation / stall clause | `<p className="text-base font-semibold text-danger">` — a **sibling** of the alert region. `--color-danger` on `--color-surface-raised` **7.01:1 ✓** (DC-10 — re-measured; an earlier draft carried a transcribed approximation) |
| Accept | `Button variant="primary" size="lg" fullWidthMobile` + `aria-label={t("sos.acceptAria", { name })}` — `min-h-12`, gold/ink 6.41:1 ✓, **first in DOM** |
| Dismiss | `Button variant="ghost" size="md" fullWidthMobile={false}` + `aria-label={t("sos.dismissAria", { name })}` — `min-h-11`, second in DOM, own line |
| In-card alert | `<p role="alert" tabIndex={-1} className="text-sm font-semibold text-warning-text">` — ⚠ **the notice register, not `text-danger`**: a 409 is two people reaching for one emergency and a 404 is a screen one tick behind. **Nothing that can go wrong here is her fault**, which is F36's **F-7** reasoning on the same class of error |
| Bottom container | `<div className="pointer-events-none fixed inset-x-0 bottom-0 z-40 flex flex-col items-end gap-2 p-4">` — one container, so the strip and the affordance can never collide. ⚠ **`inset-x-0`** (DC-2 — the logical-property spelling an earlier draft carried is not a Tailwind 4 utility and would be dropped silently). ⚠ **`pointer-events-none` is LOAD-BEARING and its two children carry `pointer-events-auto`** — `Toast.tsx:40`'s shipped shape. Without it this is an INVISIBLE full-viewport band ≈76px tall (`p-4` + the affordance's `min-h-11`) at `z-40`, on all thirteen sections, for as long as any dismissed alert stays live; measured in Chromium, a click at the centre of a console control in the bottom 76px reached the band and never the control |
| Channel strip | `<div className="pointer-events-auto w-full rounded-md border border-danger bg-surface-raised p-3">` + `<p role="alert" className="text-sm text-ink">` + `Button variant="secondary" size="md"`. F57's terminal-panel shape (`FloorPanel.tsx:446-456`) |
| Re-open affordance | `Button variant="danger" size="md" className="pointer-events-auto"` — white on danger **7.01:1 ✓**, focus ring on the console's cream **5.57:1 ✓**, ≥44×44 |
| SOS-centre heading | `<h3 ref={headingRef} tabIndex={-1} className="text-base font-semibold text-ink">` — matches F36's rooms `h3` exactly; `tabIndex={-1}` adds **no** tab stop. ⚠ **It is MOVE I's fallback and NOT MOVE G's**: MOVE G falls back to `FloorPanel`'s own `<h2 ref={headingRef}>` (`:103`), which is the heading actually in scope for a dialog `FloorPanel` owns. This ref is `SosCentre`'s own, and it is what MOVE I lands on when the row she acted on left with the control she tapped |
| SOS-centre heading row | `<div className="flex flex-wrap items-center justify-between gap-3">` — F36's shipped shape |
| SOS-centre trigger | `Button variant="danger" size="md" fullWidthMobile={false}` — all five roles, always |
| SOS-centre list | `<Card>` → `<ul className="divide-y divide-border">` → `<li data-alert-id={id} className="flex flex-col gap-3 py-4 sm:flex-row sm:items-start">` — `FloorPanel.tsx:630`+`:648` / `RoomsPanel`'s exact shape |
| Row status | `Badge variant={status === "open" ? "danger" : "neutral"}` — **one per row** |
| Row elapsed | `elapsedLine(t, serverNow, created_at)` — F36's shipped helper, **no new formatter** |
| Row controls | `Button` `secondary` (accept) · `ghost` (resolve) · `ghost` (cancel), all `size="md" fullWidthMobile={false}` in a `flex flex-wrap justify-end gap-3` |
| Tile raise control | `Button variant="danger" size="md" fullWidthMobile={false}` + `aria-label={t("sos.raiseAria", { room })}`, **first** in the shipped action row |
| Dialog | the shipped `Modal`; `Select` + `Input`, both `className="min-h-11"` (F36 **F-4**); footer `ghost` dismiss + `secondary` confirm |
| Dialog error | `<p role="alert" tabIndex={-1} className="text-sm font-semibold text-warning-text">` inside the `Modal` body |

**Contrast, computed at this gate — not eyeballed.** ink on surface-raised ≈16.1 · ink on surface (paper) 13.89 · ink-muted on paper 5.61, on white 6.36 · danger text on white **7.01**, on paper 6.18 · warning-text on white 5.90, on paper 5.20 · white on danger **7.01** · gold/ink 6.41 · focus ring on cream 5.57, on paper 5.08, on white 5.76. **Two negative rows enter the ledger at this gate** (§2.1): **ink on danger 2.25 ✗** and **focus on danger 1.22 ✗**. (DC-10: all four danger-surface numbers are RE-MEASURED at this gate; the earlier draft's transcribed approximations are superseded and every conclusion drawn from them is unchanged.) **No gold-strong anywhere; this feature adds no new colour and no new token.**

---

## 9. The a11y contract — IS 5568 / WCAG 2.0 AA is legally binding (pre-decided #38), and this section IS the gate

axe must return **zero** violations **and axe is not the coverage — in both directions.** It cannot see a focus move that never happened (this repo has shipped that four times: F56 on the storefront, F34 on the board, F57 on `FloorPanel`, F36's stale-closure MAJOR) and it equally cannot see a focus move that **should not have happened**, which is the new failure class this feature could introduce. It has no rule for SC 2.2.2. It cannot see a focus ring that is the wrong colour against a parent's background (§2.1). **A manual screen-reader pass is a gate condition on this PR** (e7 Risks), not a deferral to F58.

### 9.1 The announcement — what, once, via what

- **One `role="alert"` per card**, never one wrapping the list. `role="alert"` carries implicit `aria-live="assertive"` **and** implicit `aria-atomic="true"`, so with a wrapper a second page would re-announce **every** card and the seamstress would hear again about the emergency she already answered. Per card, mounting announces exactly the new one.
- **The announced content is three block children of the region — who, where, note** — read as one atomic utterance: «דנה כהן קוראת לעזרה … חדר 2 … צריך סיכות». They are the **same nodes** the sighted user reads, so nothing is duplicated for a screen reader: **one visually-hidden LABEL and no copy of any value.** ⚠ **DC-4** — the WHERE line renders the boutique's own label bare («2» is fully supported), and ARIA prohibits naming `role=paragraph`, so a `<span className="sr-only">{t("sos.roomA11yPrefix")}</span>` («מיקום») sits **inside** the region before the `<bdi>`. It labels a value, never restates one, so there is nothing to drift.
- **Announced exactly once, by construction and not by a guard.** Cards are keyed by `alert.id`, so a card that stays mounted across ticks is never re-announced — React skips an identical text update, so no `childList` mutation occurs inside the region (F34's **F-7** hazard, avoided structurally).
- ⚠ **The region's text is WRITE-ONCE.** «מאז 11:20», «ללא מענה» and «אין תזוזה מאז שאושרה» all render in **siblings outside it**. Putting the escalation clause inside would re-announce the whole card assertively thirty seconds later, interrupting whatever the screen reader was saying, for a fact that changes nothing about what she has to do. **AC16's mutation: move the clause inside the region → red.**
- **The poll never writes into any live region.** F34's **D11**, verbatim and non-negotiable. A card mounting is not the poll writing into a region — it is new content arriving, which is exactly what `role="alert"` is for.
- **`role="alert"` on this screen is bounded by construction**: one per rising alert, and an alert is a row a person created.

### 9.2 Focus — NINE moves, each with a named, non-vacuous mutation, and each in BOTH directions

⚠ **`Button.tsx:57` is `disabled={disabled || loading}`, so the browser blurs the tapped control the instant a request starts, and every action in this feature is that shape.** ⚠ **And jsdom does not blur a disabled element** — F57's shipped note records that its own success-path focus test was therefore **VACUOUS**: `document.activeElement` never became `<body>`, the guard never passed, and the whole restore effect could be deleted with the suite green. **Every test below must reach `<body>` before the promise resolves, or it asserts nothing.** ⚠ **AND `control.blur()` DOES NOT DO THAT.** jsdom's `HTMLElement.blur()` **bails out on an element that is not a focusable area**, and a disabled button is not one — so the blur an earlier draft prescribed is a **NO-OP on exactly the controls it was prescribed for**, measured: an assertion of `activeElement === document.body` straight after `accept.blur()` failed with activeElement still the disabled button. Reaching `<body>` in jsdom requires **focusing and blurring a scratch node outside React's tree**; the alternative is a Chromium journey in `e2e/sos.spec.ts`, which is where the two hardest of these now live.
⚠ **AND A FOCUS ASSERTION MUST WAIT FOR THE MOVE, NOT FOR THE DOM.** Every move here runs in a **passive effect**; `findByText` / `waitFor(textContent)` waits for the COMMIT. Under load the two are different moments, and a bare `expect(document.activeElement).toBe(X)` straight after a text-only wait reddens intermittently — measured on the unmodified tree at **3 failures in 10 `make fe-test` runs**, across three different tests. Positive directions therefore assert inside `waitFor` (still non-vacuous: delete the move and it times out); **negative/steal directions stay BARE and add one `settle()`**, because a `waitFor` on "focus did not move" would pass the instant it looked true and miss a steal one flush later. The same applies to a test's PRECONDITION: wait for MOVE A to have landed before blurring, or the blur is a no-op on `<body>` and the guard under test is never exercised.

⚠ **AND EVERY RESTORE NEEDS BOTH DIRECTIONS.** F41's post-mortem: its first fix stopped focus being dropped and shipped a focus **STEAL** instead. A test asserting «focus moved to X» cannot fail when focus was taken from somewhere it should not have been, so each move below carries a negative case as well as its mutation.

| # | Move | Condition | Destination | Mutation that must turn it red |
|---|---|---|---|---|
| **A** | The first rising alert appears | **iff `document.activeElement === document.body`** | ⚠ **that card's CONTAINER** — `<article ref tabIndex={-1} aria-labelledby={whoId}>`, **never «אני מגיעה»** (DC-1, §2.3). Named by the WHO line's own node rather than left bare, so an AT does not re-read the subtree the alert just announced | delete the `=== document.body` guard, then assert focus does not leave a text input; and assert `activeElement.tagName` is `ARTICLE` and **not** `BUTTON` |
| **B** | The overlay unmounts while holding focus | `activeElement` was inside it **OR `document.activeElement === document.body` and `actedRef` names the card that left** | `document.getElementById("console-main")` — the `<main tabIndex={-1}>` `ConsoleShell` already renders and the skip link already targets (`ConsoleShell.tsx:43,84`). **Never `<body>`** | delete the effect |
| **C** | A card leaves with siblings remaining | `activeElement` was inside that card **OR she tapped that card's accept and nothing holds focus** | the **next remaining** card's **CONTAINER** (DC-1, as A); falls through to B when none remains | delete the departing-card check; and delete the `actedRef` fallback — the SUCCESSFUL-accept case reds |
| **D** | A failed action's in-card alert appears | **iff `activeElement` is inside that same card** | that alert | remove the in-card guard, then assert focus does **not** leave a text input behind the overlay when a 409 lands |
| **E** | ⚠ **The raise dialog's send control is replaced by «הבנתי»** (rerouted) | always — the focused element has just unmounted | «הבנתי» | delete it; focus falls to `<body>` inside an open `<dialog>` and the one message the ruling mandates becomes unreachable by keyboard |
| **F** | The raise dialog's failure alert appears | iff `activeElement` is the `<dialog>` or `<body>` (which is where the send button's blur left it) | that alert | delete it |
| **G** | The raise dialog closes | `activeElement === document.body` | **`FloorPanel`'s own `sosTriggerRef`**, `trigger.isConnected ? trigger.focus() : FloorPanel's own headingRef.current?.focus()`. **Never `<body>`** | delete the `isConnected` branch — focus goes nowhere when the tile was released underneath |
| **H** | ⚠ **A `SosCentre` ROW's own failure alert appears** (DC-7) | iff she acted on that row **and** `activeElement` is `<body>` or inside that row | that row's `<p role="alert" tabIndex={-1}>` | share `FloorPanel`'s `cardError`/`cardAlertRef` instead — the 409 renders nowhere and steals focus into a **staff card**, because `cardError.id` is a staff-card id |
| **I** | ⚠ **A `SosCentre` action SUCCEEDS** — the tapped control is removed (`mayAccept` flips false) or the whole row is (resolve/cancel) | iff she acted on that row **and** `activeElement` is `<body>` or inside that row | the row's **remaining control**, falling back to `SosCentre`'s own `<h3 ref={headingRef} tabIndex={-1}>` when the row went too. **Never `<body>`** | delete the intent — both success cases red; delete the `<body>`-or-inside guard — the steal case reds |

⚠ **MOVE A fires on a freshly loaded or untouched tab — NOT on "the common case on a shop floor."** A console anybody has touched holds focus on the last-clicked element: clicking a nav row or a `Button` leaves focus on it, which is precisely why four shipped restore effects exist. **A board tablet loaded at 09:00 and untouched since IS on `<body>`, and there the emergency is one keypress from being accepted. A tablet in use is not, and there MOVE A does not fire at all** — `role="alert"` alone carries the announcement and §9.4 carries the reach. Both branches are real; which one is common depends on whether anybody has touched the screen.

⚠ **MOVE G is NOT a reuse of `RoomsPanel.tsx:307-330`, and citing it would ship the fifth focus bug.** That effect is `useEffect(…, [openDialog])` reading `dialogTriggerRef` (`:160`), which `openFrom` (`:558-562`) sets from `event.currentTarget` — and it is keyed on **`RoomsPanel`'s own `openDialog` state** (`:144`), all verified. With the open-state in `FloorPanel`, `RoomsPanel`'s `openDialog` never changes, **the effect never runs, the native `<dialog>`'s own return has no target, and focus drops to `<body>` for something the user did.** So: the tile's prop is `onRaise?: (assignmentId: string, trigger: HTMLButtonElement) => void`, the tile's handler passes `event.currentTarget`, **`FloorPanel` stores it in its own `sosTriggerRef`**, and the fallback is **`FloorPanel`'s own `<h2 ref={headingRef} tabIndex={-1}>`** (`:436`, verified) — the heading actually in scope.

⚠ **MOVE D copies `FloorPanel.tsx:265-292`'s shape and NOT its guard.** That shipped effect fires `cardAlertRef.current?.focus()` unconditionally, which is correct *there* because the panel's `Button` is `disabled={disabled||loading}` and the browser already blurred it. **Copied into the overlay it becomes an unguarded focus move on an error path, in the one component whose whole premise is that it never moves focus uninvited.** The in-card guard says: she tapped *this card's* accept, so focus is hers to reclaim — but a 409 landing while she is typing behind the overlay must not pull her out.

### 9.3 The mid-typing hazard — bounded, not waved past

The overlay does not take focus (MOVE A's guard) and does not `inert` the console, so **no keystroke is lost.** What is lost is **sight of the field she is typing into**, and there is no free fix: the ruling says full-screen red, and a band is missable on a 375px phone inside a curtain.

**What bounds it:**

1. **Two Esc presses get her out with her value intact** (§9.4): the first moves focus into «אני מגיעה» and does not touch the input; the second dismisses the card and MOVE B parks focus on `#console-main`.
2. **One tap gets a pointer user out**, on a 44px control 40px inside every screen edge.
3. **Nothing behind the overlay auto-submits.** No form in this console submits on a poll, on a tick or on a timer.
4. **Her value survives the dismiss** — dismissal is per-device and in-memory and unmounts nothing behind it.

**What is NOT claimed:** that a real browser keeps a caret usable under a `position: fixed; inset: 0` sibling, that she can see her own validation while the overlay is up, or that she will not press Enter blind. **Risk 6 hands F58 «typing behind the overlay» as its fourth named real-browser case**, and the manual screen-reader pass on this PR is the interim evidence. This is the trade spec D15 takes in writing; it is recorded here rather than discovered in a pilot.

### 9.4 Keyboard-only operation — and the route IN, which MOVE A alone does not provide

**An alert announced perfectly to a user who cannot reach the ack control is not an accessible alert.** MOVE A deliberately does not move focus when something holds it, and Esc bound to the container fires only when focus is already inside — so for **the exact user this design protects**, someone mid-form in `main`, «אני מגיעה» sits behind a Shift+Tab run past every preceding focusable in her section **plus the whole `ConsoleShell` chrome** (SkipLink → logout → up to ten nav rows → `<main id="console-main">`, verified `App.tsx:67-125`, `ConsoleShell.tsx:43,84`). Forward Tab is worse. *"First in DOM is first reached by Tab"* is true only in the `<body>` case — i.e. only where focus moved anyway.

> **Esc from OUTSIDE the overlay MOVES FOCUS INTO the first rising card's «אני מגיעה». Esc from INSIDE keeps its meaning: dismiss.**

⚠ **THIS ROW IS THE EXPLICIT EXEMPTION FROM DC-1, and the distinction is deliberate-versus-involuntary.** MOVES A and C land on the card **container** because they fire on an arrival the user did not ask for, and the next Space on a body-focused page must not become an irreversible accept. Esc from outside is a **keypress she chose to make**, so it lands on the **control** — that is the whole point of the route in. A builder "unifying" the two destinations reverts DC-1.

One document-level **capture** `keydown`, live only while at least one alert is rising, with **two guards**, each preserving a shipped behaviour rather than being defensive padding:

- **`document.querySelector("dialog[open]") === null`** — this is what keeps F36's three shipped `<dialog>`s and `SosRaiseDialog` owning their own Esc (`Modal.tsx:38-44`'s `onCancel`). `Modal` renders its `<dialog>` unconditionally and toggles `open` via `showModal()`/`close()`, so the selector matches only while one is genuinely open. Verified.
- **the event target is not a `<select>`** — ⚠ **`RoomsPanel.tsx:790` renders a bare `Select` on the free tile, OUTSIDE any dialog** (verified), and Esc closing an open native dropdown is browser behaviour a capture listener would pre-empt. Two characters of condition; jsdom would never have caught it.

**Tab order while an alert is up:** card 1 «אני מגיעה» → card 1 «הסתרה» → card 2 … → SkipLink → logout → nav → `#console-main` → the section's own stops. ⚠ **The skip link is therefore no longer the first tab stop while an alert is rising, and that is correct**: WCAG 2.4.1 asks for a bypass mechanism, not for it to be first, and an emergency ack that came after a ten-row nav walk would be the failure §9.4 exists to close. The same holds for the bottom container in §2.7 — while a live alert is dismissed or the channel is down, its control is the first stop in the app.

**Every action is keyboard-reachable and none needs a pointer.** The only interaction primitives are `<button>`, native `<select>`, native `<input type="text">` and Esc. **No drag, no long-press, no swipe, no hover-only affordance, no custom widget, and no keypress that mutates anything** — the raise `Select` sets draft state and a sibling button commits, which is how every `Select` in this console already works and is the WCAG 3.2.2 rule F41's review found the hard way.

### 9.5 Urgency is never carried by colour, and the regions are three

- **The red field is not information.** Every state this feature has is a Hebrew word on a card: «דנה כהן קוראת לעזרה», «ללא מענה», «אין תזוזה מאז שאושרה», «פתוחה», «מטופלת». Law 2, and F51's shipped sentence (*"The WORD carries the role; the colour never does"*) with `FloorPanel.tsx:42`+`:735`'s state variant. **Remove every colour from this feature and nothing is lost but emphasis.**
- **Three regions, three politenesses, on purpose** — stated so nobody "consolidates" them:

| Region | Politeness | Written by | Where it exists |
|---|---|---|---|
| The overlay's per-card `role="alert"` | assertive, event-driven | a card mounting | app-level, all thirteen sections |
| The shipped `ToastProvider` (`Toast.tsx:38-50`, `App.tsx:187`) | `role="status"` polite / `role="alert"` on error | **actions issued FROM the overlay** | app-level, all thirteen |
| `FloorPanel`'s single `role="status"` (`FloorPanel.tsx:510-520`) | polite, user-initiated only | actions issued from `SosCentre` | `board` and `floor` only |

⚠ **The toast is not an optional flourish.** An accept from the overlay removes the card, MOVE B parks focus on `<main id="console-main">` — an **unlabelled container** — and on any of the eleven sections with no `SosCentre` there is **no `role="status"` region at all**. A shift manager who accepts an emergency from the catalog screen would otherwise get: the red vanishes, focus jumps to the top of an unnamed main, and **nothing is announced or shown.** `ToastProvider` is already wrapped around the signed-in tree; `SosOverlay` calls the shipped `useToast()`. **AC29's mutation: delete the call → red.** `SosCentre` keeps writing into `FloorPanel`'s region for actions taken there, unchanged.

### 9.6 The rest of the contract

- **SC 2.2.2 — this feature adds NO pause control, and the argument is why it does not need one.** In the idle state `SosOverlay` renders **nothing**: the criterion governs auto-updating information presented in parallel with other content, and there is no content to pause, stop or hide. In the alert state **nothing auto-updates** — static text, an absolute time, no countdown and no live counter (which is what keeps the argument true rather than merely claimed). The "hide" mechanism the criterion asks for **exists**: «הסתרה», plus Esc. ⚠ **And the idle STOP is disabled on this loop** (`idleStopMs: null`) because a phone in an apron pocket, untouched for eleven minutes, would otherwise **silently stop receiving pages** — the worst property an emergency channel can have.
- ⚠ **`FloorPanel`'s shipped pause and idle assertions now govern one more region and MUST NOT be cut as redundant.** axe has no SC 2.2.2 rule, so those frontend tests are the sole coverage of a Level A requirement inside a legally binding AA bar — and the **freeze-while-paused** behaviour (§4.2) needs its own named test, because a pause control whose region keeps moving is a 2.2.2 failure that passes axe.
- **≥44×44 on every target.** Accept `min-h-12`; every other control `size="md"` → `min-h-11`; `Select` and `Input` carry `min-h-11` per F36's **F-4**; the tile's fourth control wraps rather than shrinks.
- **Visible focus ring on every interactive element** — `focusRing`, applied unconditionally by `Button.tsx:62`, `Input.tsx:45`, `Select.tsx:31`. Nothing sets `outline: none`. ⚠ **And §2.1 is what makes this true rather than nominal**: on `bg-danger` the shipped ring is 1.22:1 and axe would not say so.
- **Bidi**: `<bdi dir="ltr">` on every numeric run (times, the count on the affordance); **bare `<bdi>`** on every Hebrew free-text run (staff names, room labels, the note). Forcing LTR on a Hebrew name reverses its words and it is the defect that *looks* deliberate. An `aria-label` takes no markup, so an interpolated name in one needs no bidi treatment (F57 **F-11**).
- **No truncation and no ellipsis on a name, a room label or a note, ever.**
- **Headings**: `ConsoleShell` owns the `h1`; `FloorPanel`'s `h2` is unchanged; `SosCentre` brings an `h3` beside F36's rooms `h3`; the `Modal` brings its own `h2` inside the top layer, which is the shipped component's behaviour. ⚠ **The overlay brings NO heading** — every card already opens with «{{name}} קוראת לעזרה», which is the region's own first line and carries the meaning; a field-level heading would be a second thing to keep true and would sit outside every live region saying what the live regions already say.
- **Motion: this feature adds none.** The overlay **appears**; it does not animate, fade, slide, pulse, flash or shimmer. `prefers-reduced-motion` therefore needs no new rule (`theme.css:155-163` already freezes the `Modal` panel animation and the `Button` spinner, the only two motions on these screens).
- **Content capped at 720px** at every width, overlay included. `A11yMenu` / `A11yStatementLink` are storefront-only, so no fixed-chrome clearance applies to the bottom container.
- **An axe pass** runs over the overlay, the centre and the dialog — **and is explicitly not sufficient**, per §2.1, §9.2 and §9.6.

---

## 10. RESOLVED decisions — self-approved with the design gate, 2026-08-03

**All nine carry a resolution and none is an open question.** Each keeps its reasoning, because the reasoning is what a later feature would have to overturn to reopen it. **The Hebrew remains the user's to edit post-merge** — the F15 P-1/P-5, F34, F57 and F36 precedent: a one-line `he.ts` / `ar.ts` edit after merge, never a rebuild.

| | Resolution |
|---|---|
| **P-1** | **The red is the field; the cards are `bg-surface-raised`** — §2.1, four measured numbers |
| **P-2** | **The ack is `Button primary lg`, not `danger`** — red is this product's destructive register |
| **P-3** | **The field is inert to taps** — no backdrop-dismiss on an emergency |
| **P-4** | **Oldest first, no auto-scroll, no counter, no carousel** |
| **P-5** | **The room label renders bare, with no Hebrew prefix** — F36's **F-3** |
| **P-6** | **No `EmptyState` on the SOS centre's 99% state** — 64px, not 140px |
| **P-7** | **The tile's raise control is `danger` and first in the action row** |
| **P-8** | **No heading on the overlay field** — the card's first line is the heading |
| **P-9** | **This deck introduces no new component, variant, colour, token or motion rule** |

- **P-1 — RESOLVED: `bg-danger` paints the viewport; every alert card is `bg-surface-raised`.** §2.1 is the full argument and it is arithmetic, not taste: `text-ink` on `#A03232` is **2.25:1**, the product's one focus ring is **1.22:1** on it, and `Button danger` is invisible on it — and the call-site override that would "fix" the ring is exactly F15 **F-6**'s non-deterministic loss. Full-screen red survives literally; the words move onto paper where the whole shipped vocabulary already works. *Declined a translucent scrim (`bg-danger/80`): a translucent emergency reads as a loading state and puts an unbounded set of backgrounds behind the ring.* **This CORRECTS spec D15's surface, not its token.**
- **P-2 — RESOLVED: «אני מגיעה» is `Button variant="primary" size="lg" fullWidthMobile`.** Gold fill, ink label, 6.41:1, 48px, full-bleed at 375, first in DOM. `danger` is the console's destructive register (delete a room, cancel a booking) and the most affirmative act on the floor must not wear it; `secondary` is F36's "ends the current state" weight; `ghost` is indistinguishable from a dismiss.
- **P-3 — RESOLVED: the red field carries no handler.** A tap on it does nothing. §2.3's six guards resolve "unmissable" against "un-mis-tappable" **without a confirm step**, which an emergency acknowledgement must not have. The residual — an accidental accept costs up to two minutes of `STALLED_AFTER` — is **F-2**, recorded as a finding rather than as reassurance.
- **P-4 — RESOLVED: oldest first, no auto-scroll, no "1 of 3", no carousel, no pagination.** The longest-waiting emergency is the one to answer, escalated cards are therefore at the top **by construction and with no second sort**, and the newest card announces itself wherever it lands. The scroll cue is the third card's white top edge at y=578 in a 667px viewport — arithmetic, not chrome.
- **P-5 — RESOLVED: «חדר 2» renders as a bare label in a `<bdi>`, with no Hebrew prefix and no interpolated sentence.** F36's **F-3**: the boutique types the room's own noun, so «בחדר {{room}}» renders «בחדר חדר 2» and «{{room}} נתפס» renders «הבמה נתפס». *Declined a «מיקום:» prefix* — technically correct, register-wrong for an emergency, and the card's second line is unambiguous by position. The announced sentence joins the three region children as one utterance, which is what carries the relation for a screen reader.
- **P-6 — RESOLVED: the empty SOS centre is a heading row plus one muted line — no `Card`, no `EmptyState`.** `EmptyState`'s `py-12` + `font-display text-xl` is ≈140px of the loudest block on the floor screen saying *there is no emergency*. The house rule exists for **content that should be here and is not**; no alerts is the desired state. 64px, and the `Card` appears only when there is something in it. *Declined hiding the panel entirely when empty*: it is the second raise entry point and the only one for a staffer who is not in a room.
- **P-7 — RESOLVED: «קריאה לעזרה» is `Button variant="danger"`, first in the tile's action row.** DOM order is tab order is wrap order and the emergency must be first in all three. Red here is the console's first **non-destructive** danger, and the collision is worth one sentence, not a new variant: red means *this act has consequences you should mean*. `secondary` is taken by F36's one-per-tile rule; `ghost` hides it. **A mis-tap costs one Esc**, because the control opens a dialog and cannot page anybody — which is exactly why it may be prominent.
- **P-8 — RESOLVED: no heading, no title bar and no chrome on the overlay field.** Every card opens with «{{name}} קוראת לעזרה» — the region's own first line, the loudest text on the screen, and the thing law 2 requires the red to be paired with. A field heading would sit **outside** every live region, restating what the regions say, and would be one more string to keep true. *Declined a visually-hidden `<h2>` too*: the same duplication, invisible.
- **P-9 — RESOLVED: this feature introduces no `packages/ui` component, no variant, no colour, no token, no formatter and no motion rule.** Two negative contrast rows enter the ledger (§8) and nothing else. `usePoll` gains two optional fields and the acceptance rule is F36's D15 one level down — **`BoardSection.test.tsx` and `FloorPanel.test.tsx` pass with ZERO EDITS**, which is the only instrument that can tell a faithful extension from a subtly different one.

---

## 11. ⚠ FINDINGS

- **F-1 — spec D15 puts the alert cards on `bg-danger`, and the shipped focus ring is 1.22:1 against it.** §2.1 has the four measured numbers. The consequence is not cosmetic: `focusRing` is the console's **only** focus indicator, `outline-offset-2` draws it on whatever is behind the control, and a keyboard user on an emergency ack would have no visible focus at all — a WCAG 2.4.7 failure on a legally binding surface **that axe cannot report**, because its contrast rule computes an element against its own background. `text-ink` at 2.25:1 and `Button danger` at 1.00:1 make the same point about the rest of the vocabulary. **The fix is one word in the deck — the cards are `bg-surface-raised` — and it preserves the ruling's "full-screen red" exactly**, because the field is what fills the screen. **This is a correction to the spec, recorded rather than folded in silently** (the F57 F-2/F-3 and F36 F-3 precedent). *Owner: team. **Trigger: this PR's build.***
- **F-2 — an accidental accept is not reversible, and the design's answer is a two-minute hole that should be named rather than reassured about.** Spec Out-of-scope forbids an un-accept verb, with a good reason (it would give D4's `else: raise` a reachable input and make "who owns this" answerable two ways). §2.3's five guards make an accidental accept improbable, and `_stalled` makes it non-permanent — **but between the tap and `STALLED_AFTER` the raiser's screen reads «דנה מגיעה» and nobody is walking.** Two minutes is a ruling-free number; the read-time derivation means changing it changes every alert immediately, with no migration and no backfill. **The recorded remedy is the constant, not a verb.** *Owner: team. Trigger: pilot evidence — an accepted alert that stalls more than once in a week.*
- **F-3 — «who is coming» renders on 2 of 13 sections, and the raiser is the one person the overlay never reaches.** `sos.acceptedBy` lives on a `SosCentre` row; `SosCentre` is a child of `FloorPanel`; `FloorPanel` is mounted on `board` and `floor` (verified `App.tsx:207-215`). The raiser is on the floor section by construction — both raise triggers are there — and has no reason to leave while she is waiting. But if she does, she loses her only view of the accept: the overlay will not rise for her own page (spec D7, correctly), and no toast fires because the accept is somebody else's action on somebody else's device. **Not built here**, because the cheapest honest fix is a fourth app-level surface for a case that requires the raiser to walk away from the emergency she just reported. *Owner: team. Trigger: pilot evidence, or F35's durable bell — which is the surface that solves it properly.*
- **F-4 — `FloorPanel`'s `h2` now names one third of its own content, and F36's F-1 said F58 would be the PR that earns the rename.** The panel is «צוות בקומה» and contains, in order, `SosCentre` («קריאות עזרה»), `RoomsPanel` («חדרי מדידה») and the staff list — which has no heading at all. A heading-walking user hears the section name, then two subsections that are not staff, then falls out into unnamed cards. **F37 does not rename `floor.heading`**, because `FloorPanel.test.tsx`'s shipped expectations must pass unedited (spec D12's acceptance rule) and a copy change on a shipped panel is exactly the kind of edit that rule exists to catch. **But the trigger has arrived one PR early**: F36 predicted three panels at F58 and F37 delivers them now. *Owner: team. Trigger: F58, unchanged — but it is now overdue rather than upcoming.*
- **F-5 — this deck ships five copy corrections to spec D17, and all five are in `copy.md`.** (a) `sos.dismissAria` cannot be «הסתרת ההתראה — …» when the visible label is «הסתרה»: **an accessible name must contain the visible label** (WCAG 2.5.3 label-in-name, Level A), and «הסתרת» is a different word. It becomes «הסתרה — הקריאה מ{{name}}». (b) `sos.channelReload` is **«רענון הדף»**, not D17's «רענון» — D17 says to reuse `floor.reload`'s word and `floor.reload` **is** «רענון הדף»; «רענון» is `floor.refresh`, a *different* act (refetch, not reload) on a strip whose only remedy is a page reload. (c) `sos.room` is not a string at all — the room renders as a bare `<bdi>` in its own element (P-5), so D17's row becomes a **note**, not a key. (d) `sos.centreRaise` and `sos.targetOnBreak` are **deleted**: the first is byte-identical to `sos.raise` and the second to the shipped `rooms.handoverOnBreak`, and two keys holding one string are two things to keep true and twice the hand transcription into `ar.ts`. (e) D17's table plus its trailing "plus …" line resolves to **48** keys once the two `details`-less error variants, the strip, the affordance, the dialog's failure state and every accessible name are counted — not "~40" — which is what spec Risk 11's `ar.ts` estimate should read. **`copy.md` is canonical and each correction is marked in its own row** — the F57 and F36 precedent. *Owner: team. Trigger: the copy transcription.*
- **F-6 — `i18n.test.ts`'s two register guards and its `ar` parity guard will silently skip this whole namespace unless `HE_F37` is FOLDED INTO `HE`, not merely declared** — and **the «בדרך» ban this spec cites as already binding does not touch `sos.*` until the fold happens.** The file says so about itself at `:32-36`: *"Folded in, not just declared: without this the resolve check, BOTH register guards and the `ar` parity guard silently skip every F52 key."* The entire wording decision for «אני מגיעה» rests on that ban. ⚠ **The `HE` array now folds NINE constants and F37 makes it ten** — check the FOLD and never a line number, because the array moves every time a feature lands. The line to add is `const HE_F37 = entries(he.translation, (key) => key.startsWith("sos."));`. **No `nav.` term in the selector, and that is an assertion rather than an omission** — F37 adds no nav row. *Owner: team. **Trigger: this PR's build.***
- **F-7 — MOVE E and MOVE F are focus moves the spec does not name, and both are inside a native `<dialog>` where "the browser handles it" is false.** Spec D16 rules that a rerouted raise keeps the dialog open with «הבנתי» and that a failed send keeps it open with `sos.error.raiseFailed`. In both, **the control that had focus has just been unmounted or disabled** — `Button` is `disabled={disabled||loading}` — and a `<dialog>` whose focused child is removed drops focus to the dialog element or `<body>` depending on engine. Neither move has a rule, an AC or a mutation in the spec. **They are §9.2 rows E and F**, with the guards written out, because this is the fifth and sixth instance of the bug class this repo has shipped four times, on the surface D15 declares a gate condition. *Owner: team. **Trigger: this PR's build.***
- **F-8 — no E2E covers any of this, and F37 widens the gap more than any feature before it.** The console's entire e2e surface is two login-screen tests because `vite preview` runs with no backend (`e2e/a11y.spec.ts:10-13`). The three behaviours that matter most here are the three jsdom models worst: whether a real browser leaves the caret usable in an input under a fixed overlay, whether a real screen reader announces a `role="alert"` that mounts inside a React commit, and whether Tab and the capture-Esc route genuinely reach the overlay's controls from a form field. **jsdom already made one F57 focus test vacuous.** F58 owns the `/manage/**` interception harness and inherits **four** named cases (spec Risk 6). **The manual screen-reader pass on this PR is the interim and is a gate condition, not a deferral.** *Owner: team. Trigger: F58.*
- **F-9 — three loops on the board screen is this architecture's ceiling and F58 will want a fourth.** `BoardSection` 5s + `FloorPanel` 5s + SOS 5s/2s, with **two** pause controls (the SOS loop adds none, deliberately — a third would start to be a defect, F36's D15). Eleven sections that shipped **zero** requests now issue ~11 round trips per 5s, ~27 with an alert open, and `tenants.by_slug` — the uncached-per-request lever already assigned to F29 — is paid **three times per beat** on the board. **This is also the first loop in the product with no idle stop**, so a console left open overnight polls until the 12-hour session expires. **F29 must be handed those three numbers, not left to discover them** (spec Risk 4). If a fifth `usePoll` caller ever appears, that is the moment to ask whether the console wants one multiplexed poll rather than N. *Owner: team. Trigger: F58's spec, and F29's k6 pass.*

- **F-10 — the spec's `usePoll` signature contradicts itself, and the wrong half is the one a builder copies.** Spec **Frontend changes** lists `intervalMs?: number` while **D12** — and D12's whole argument — requires `intervalMs: number | (() => number)`: the tick writes the gap on the line above `succeeded()`, in the same microtask chain as the response, so a state-derived gap re-arms the alert-observing tick at 5 000 ms and costs a silent five-second hole exactly when the raiser is waiting to see who is coming. **And the obvious prop-rerender-then-tick test passes over it**, which is the shape of F57's vacuous focus test. The Frontend-changes row is the one a builder reads while typing the signature. *Owner: team. **Trigger: this PR's build.*** (DC-9; spec amended.)
- **F-11 — the accept permission had no `raised_by` term on EITHER side, and an elevated raiser could silence her own emergency in one tap.** Spec:204 states both clauses in one bullet — the permitted set, then *"the raiser may not accept her own page"* — and `accept_sos`'s own docstring repeated the second sentence three lines above a guard that did not implement it. The target check refused a seamstress; the elevated branch passed an owner straight through, and `SosCentre.tsx`'s `mayAccept` rendered the control to match. The consequence is the silent-loss class this feature exists to prevent: `_escalated` short-circuits on `status != OPEN`, so the alert stops rising on **every device in the boutique** for the two minutes `_stalled` takes, while `_for_me`'s accepted branch returns `stalled and elevated` — False for the raiser at every t — so an owner alone on the floor silences her own page **permanently**. **FIXED in this PR**, server and client, with the existing test parametrized over `[SEAMSTRESS, OWNER, SHIFT_MANAGER]` (it reds on the two elevated rows). *Owner: team. **Trigger: this PR's review — closed.***
- **F-12 — MOVE B and MOVE C were DEAD on the path a real browser takes, and the only tests for them drove the one control that is never disabled.** «הסתרה» is synchronous and carries no `loading`, so focus genuinely stays on it in **both** engines and the departing-card intent is captured — the tests passed over a path Chromium never walks. On a **successful accept** the tapped control goes `disabled` mid-flight, the browser blurs it to `<body>`, and the render that drops the card reads `<body>`: `focusedCardId()` is null, the intent was never recorded, and focus sat on `<body>` against AC15's *"Never `<body>`"*. **FIXED**: the departing-card capture carries MOVE D's two-engine condition (`focusedCardId() ?? (activeElement === body ? actedRef.current : null)`), the existing `previous.includes(held)` guard keeps a stale `actedRef` from firing on a later commit, and **both directions** are pinned plus a Chromium journey. ⚠ **The generalisable lesson, and it belongs in §9.2: `control.blur()` is a NO-OP on a disabled element in jsdom**, so every focus test in this repo written that way proves less than it looks. *Owner: team. **Trigger: this PR's review — closed.***
- **F-13 — `SosCentre`'s SUCCESS path had no focus owner at all, and the overlay announced a success it had been refused.** Two separate defects with one root: DC-7 gave `SosCentre` its own FAILURE-path pair (MOVE H) and stopped there, so a keyboard user tapping «נפתר» was left on `<body>` with her next Tab restarting at the skip link (**MOVE I**, now built, with `SosCentre`'s own `<h3 ref tabIndex={-1}>` as the fallback §8 had specified and the build had dropped); and `SosOverlay.answer` fired its toast on `failure === null`, which the provider returns on a **terminal** 401/403 as well as on a success — so a responder refused by `CsrfOriginMiddleware`'s `CSRF_ORIGIN_MISMATCH` was told «הקריאה התקבלה.» with the channel-down strip beside it and the alert still open and unowned. `SosCentre` already guarded the second one; the overlay — the surface that exists so an emergency is not silently lost — did not. **Both FIXED.** *Owner: team. **Trigger: this PR's review — closed.***
- **F-14 — the bottom container was an invisible tap-swallowing band across all thirteen sections.** `fixed inset-x-0 bottom-0 … p-4` with no `pointer-events-none` is a full-viewport strip ≈76px tall at `z-40` whenever a dismissed alert is still live — and the role-targeted page is the raise dialog's DEFAULT, so that is the common path. Measured in Chromium: a real click at the centre of a console control inside the band fired only the band's listener. `Toast.tsx:40` is the shipped shape for exactly this (`pointer-events-none` on the container, `pointer-events-auto` on the child) and it was not copied. **FIXED**, with a Chromium `elementFromPoint` journey, since jsdom does no hit testing. ⚠ **Geography note for anyone reading §2.7's diagram: `index.html` is `dir="rtl"`, so `items-end` puts the affordance at the LEFT and the dead zone was the right.** *Owner: team. **Trigger: this PR's review — closed.***
- **F-15 — the rerouted sentence, the one message the ruling mandates, was announced to nobody.** The dialog body was swapped for a bare `<p>`: no live region, no `id`, and `Modal` sets only `aria-labelledby` (no `aria-describedby`), so it was not the dialog's accessible description either — while MOVE E moved focus to a button whose entire label is «הבנתי». A blind raiser heard «הבנתי, לחצן» and nothing about Dana, acknowledged, and put the phone down believing Dana was paged; `rerouted` is a fact about the REQUEST (spec D10), so no `SosCentre` row can ever tell her otherwise. The sibling failure branch one line over already carried `role="alert"`. **FIXED** with both mechanisms — `role="status"` for the swap and `aria-describedby` on the ack, because either alone is engine-dependent here. *Owner: team. **Trigger: this PR's review — closed.***

- **F-16 — three of this suite's focus tests were intermittently red on the unmodified tree, and the cause is a shape the whole repo uses.** `AC2`/MOVE E, `MOVE D`, and MOVE A's *"second card even when nothing holds focus"* each asserted `document.activeElement` immediately after a wait that only observed DOM TEXT — but every move in this feature runs in a **passive effect**, so under load the commit and the move are different moments. Measured: **3 failures in 10 `make fe-test` runs before the fix, 0 in 14 after.** MOVE A's case was worse than a timing miss: its *precondition* (`blur()` to reach `<body>`) silently failed because MOVE A had not yet fired, so the guard under test was never exercised and the test then reddened for the wrong reason. **FIXED**: positive directions assert inside `waitFor` (mutation-checked — deleting each move still reds), negative directions stay bare with an added `settle()` so a late steal is caught rather than raced, and preconditions wait for the move they depend on. **§9.2 carries the rule.** *Owner: team. **Trigger: this PR's review — closed.***

**Parked question, carried forward from the spec and not reopened here:** *should the overlay rise for an alert raised before this device signed in?* It does — the poll returns every live alert and `for_me` knows nothing about when the session started, so a shift manager signing in at 14:00 gets a full-screen overlay for a page raised at 13:58 and never answered. That is almost certainly right (an unanswered emergency is an unanswered emergency), and the alternative — suppressing anything older than the session — would silently hide exactly the alert that most needs answering. It ships as-is; the pilot settles whether it feels like a system that works or a system that shouts on login.
