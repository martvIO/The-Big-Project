# Screen: Per-page guided walkthrough — the «מדריך» button (F60 — one trigger in `ConsoleShell`'s header, one `Modal` over any of fourteen sections, one disclosure on the storefront `/checkin`)

**Date**: 2026-08-04 · **Status**: **DESIGN GATE SELF-APPROVED.** The 2026-07-31 ruling named exactly two novel interaction patterns for this run — F34's shift board and F42's capacity matrix — and F60 is neither: its overlay is `@boutique/ui`'s shipped `Modal` (a native `<dialog>` trusted by fifteen call sites since F5) and its trigger is a button in a shipped header row. **No prototype and no `design-critic` pass**, so every `P-` in §10 carries a resolution rather than a question. **The gate goes away; the design work does not** — this deck and `copy.md` are build tasks, not review preconditions.
**Designer**: Claude · **Consumes**: `.planning/specs/guide-walkthrough.md` (**D1–D8**, **DL1–DL21**, Gate 1 standing-approved, 26 of 27 review findings applied) · `.planning/design/system/tokens.md` (**binding**) · `.planning/design/screens/design-system/manage-restyle.md` (**binding** — the 720px cap, the three registers, the never-override-a-`packages/ui`-utility rule) · `.planning/design/screens/sos-paging/design.md` (**F37 — §5 of this deck is entirely about not fighting it**) · `.planning/design/screens/floor-staff-roles/design.md` (F57 — *which control EXISTS is the rendered form of the authorization axes*; no disabled button, no lock glyph, no «אין לך הרשאה» line) · `.planning/design/screens/fitting-rooms/design.md` §5.3 and `floor-dispatch/design.md` P-4 (**both decline `ManageBookingPage`'s reveal-focus-move; §6 is the third**) · `packages/ui` and `apps/manage` **as shipped**
**Copy**: `copy.md` in this directory — **it is canonical, this deck's inline Hebrew is illustrative.** Where a string here differs from that file, that file is the value that ships. This deck ships **two** corrections to spec strings and they are marked in §11.
**Prototype**: **none, deliberately.** The two questions a prototype could answer here — *is a modal readable at 375* and *does a three-button footer fit* — are arithmetic (§2.6) and are done below. The two it could **not** answer are the only genuinely new ones: *does a real screen reader announce a `role="status"` whose text is rewritten inside a `<dialog>` that just left `display:none`*, and *where does Chromium actually put focus after `close()` when the click that preceded it landed on non-focusable dialog content*. jsdom answers both by fiat — **it has no `<dialog>` implementation at all** — and a static prototype answers neither. **`e2e/guide.spec.ts` T1–T9 is the answer to the second; the manual screen-reader pass on this PR is the interim for the first.**

**What this deck is NOT.** It is not a new console section — `SectionKey` stays **fourteen**, `NAV` stays fourteen rows, `Nav.test.tsx` needs no edit, and that is an assertion rather than an omission. It is not a redesign of `Modal` — one **optional** prop, `describedById`, which renders no attribute when omitted, so all fifteen shipped call sites are byte-identical. It is not a redesign of `ConsoleShell` — one optional `ReactNode` slot and one wrapper `<div>`. It is not a tour: nothing is anchored, highlighted, spotlighted or scrolled to (§2.3), which is the single largest reason **no dependency is added**. It ships **zero new `packages/ui` components and zero new variants**.

⚠ **Every number in this deck was re-verified against the tree on 2026-08-04**, after nine features merged the same day. `App.tsx:24-41` carries **fourteen** `SectionKey` members and `:83-152` carries **fourteen** `NAV` rows; `ConsoleShell.tsx:46-51` is a `flex … justify-between` row with exactly **two** children; `Modal.tsx:36-55` sets **no `role`**, binds **no backdrop click**, and renders `{children}` (`:53`) whether `open` is true or false; `Button.tsx:22-38` defines `primary | secondary | ghost | danger` and gives `md` a `min-h-11`; `SosOverlay.tsx:451` is `fixed inset-0 z-40 … bg-danger` — **opaque and full-screen**, which §5.3 depends on. ⚠ **Check the shape, never a line number**: three shipped comments in `SosOverlay.tsx` and `App.tsx` still say "thirteen sections" and "eleven sections", and F60 does not repair them (spec *Codebase conflicts* 3).

---

## 0. Scope

**Three surfaces, and one of them renders on every screen in the console.**

| Surface | Where | Who sees it | Shape |
|---|---|---|---|
| **The «מדריך» trigger** | `ConsoleShell`'s header row, beside «יציאה» | every signed-in staffer, on every section | a bare `<button>` in a new `flex items-center gap-4` wrapper |
| **The step dialog** | the browser's **top layer**, centred | whoever pressed the trigger | `@boutique/ui`'s `Modal` — native `<dialog>` + `showModal()` |
| **The `/checkin` hint** | storefront, in page flow above the name field | a woman standing in the shop doorway | `Button variant="ghost"` + a `<p>`; **APG disclosure, nothing more** |

### Binding inheritances (obeyed, not restated)

From **`tokens.md`**: the gold law (`--color-gold-strong` never carries text — it appears on these surfaces **zero** times); focus ring on every control (law 4); ≥44×44 (law 7 — **the one law that costs this feature a visible change to a shipped shell, §1.2**); no raw px in app code (law 5); no colour communicates alone (law 2 — trivially satisfied, there is no colour-borne state anywhere in this feature); `prefers-reduced-motion` already global (`theme.css:155-163`), so the `Modal`'s scale/fade is already killed and **F60 writes no motion of its own**.
From **`manage-restyle.md`**: the 720px content cap; the three registers (an **outage** is `text-ink-muted`, a **thing she must act on** is `text-danger`, a **nothing-failed notice** is `text-warning-text` — this feature uses none of the three, because a walkthrough is neither a state nor an event); and **never override a `packages/ui` component's own utility from the call site** (F15 **F-6**: `cn()` is a plain join, same-property Tailwind utilities resolve by stylesheet order and the consumer loses). ⚠ **§2.2 records the one place this deck sets a colour on a `Modal` child and why it is not that trap.**
From **`floor-staff-roles/design.md`**: which control **exists** is the rendered form of the authorization axes. F60 obeys it twice — «הקודם» is **absent** on step 1 rather than disabled (DL10), and the guide's own role gating is the *absence* of a step table for a key the reader cannot make active (§1.4).
From **`sos-paging/design.md`**: the red field is an **interruption**, it has no chrome, no backdrop dismiss and no countdown, and **it must never be covered**. §5 is F60's whole answer to that sentence.

### Explicitly NOT here — with the reasons

| Not shipped | Reason |
|---|---|
| A tour library, a focus-trap library, a popper, any dependency | LOOP-STATE's fence. The three things a tour library sells are already answered: the trap is native `<dialog>`, the positioner is not in scope (nothing is anchored), and the state machine is `useState(0)` |
| A hand-rolled Tab/Shift+Tab cycle over a focusable-selector list | ~60 lines of the exact code this repo has got wrong five times (`e2e/sos.spec.ts:32-35`). The fence bans a **dependency**; the platform is not one (DL1) |
| Anchoring, highlighting, spotlighting, a cut-out, a scroll-to | §2.3. It is the reason no positioning engine is needed, and it is the reason this feature is **S** |
| A first-visit auto-open, a "seen" flag, a storage key, a dot on the trigger | DL16. An overlay that opens itself steals focus from a receptionist mid-phone-number — the defect `SosOverlay:15-27` exists to avoid |
| A step-change animation, a slide, a crossfade between steps | §2.7. Motion inside a live region is noise for a sighted reader and nothing at all for the one the region is for |
| Dots, pips or a progress bar for the step indicator | §2.4. A dot row is a colour-only signal that needs `aria-hidden` **and** a text equivalent — two mechanisms where a counter is one |
| An icon on the trigger, a chevron on the `/checkin` disclosure | The console ships **no icon vocabulary at all** (`sos-paging/copy.md` §0 rule 8). A glyph a screen reader names in a language this product did not choose |
| A per-section `aria-label` on the trigger | DL20. The visible «מדריך» **is** the accessible name; an `aria-label` over visible text is the one shape WCAG 2.5.3 can fail |
| A guide on `/queue`, on the login screen, or on any other storefront route | Spec *Out of scope*. `/queue` is a wall display with nobody standing at it |
| A backdrop-click dismiss | `Modal` binds none for any of its fifteen callers, and adding one would be a `Modal` change that reopens fifteen call sites for a feature that ships no capability. **The footer's «סגירה» is the pointer route out** (§2.5) |

---

## 1. The resting state — the «מדריך» button in the console shell

**About 99% of the time this feature is one word in a header row**, and that is the design requirement. A staffer opens the console fifty times a shift; if the guide costs her a banner, a dot, a pulse or a second row, she learns to read past that corner of the chrome.

### 1.1 Placement

⚠ **The diagrams in this deck are drawn LEFT-TO-RIGHT for legibility in a Markdown file. The rendered console is RTL** (`lang="he" dir="rtl"`). Inline-start is the physical **right**; inline-end is the physical **left**. A builder implementing the drawn order ships a mirrored header that passes axe, passes every named test, and reads wrong to the only people who will ever see it. This is F57 §1's, F36 §1's and F37 §2's warning, repeated a fourth time.

```
  ConsoleShell header — RTL, physical right → left
+------------------------------------------------------------------+
|  שם הבוטיק                                    [ מדריך ]  [ יציאה ] |
|  ^ font-display text-lg                        \______________/    |
|    (existing child #1)                          NEW WRAPPER        |
|                                                 flex items-center  |
|                                                 gap-4              |
+------------------------------------------------------------------+
|  [ סקירה ] [ פרופיל והגדרות ] [ שעות פעילות ] … up to 13 rows      |
+------------------------------------------------------------------+
```

**The wrapper is not cosmetic and DL18 says why.** `ConsoleShell.tsx:46-51` is `flex items-center justify-between` with exactly **two** children. A bare third child makes `justify-between` distribute three items across the row and the boutique name, the guide and the logout end up evenly spread — the two chrome controls no longer read as a pair. One `<div className="flex items-center gap-4">{guide}<button …logout/></div>` restores two groups.

**DL18's other half is an assertion this deck re-checked and confirms: there is NO Shift+Tab argument for this placement.** The `<nav>` of up to thirteen buttons (`ConsoleShell.tsx:56-81`) sits between the header row and `<main id="console-main">` (`:84`), so Shift+Tab from `<main>` reaches «סליקה ותשלומים», not the trigger. The placement stands on *it is chrome, in the chrome row* alone.

### 1.2 The trigger's box — and the one visible change F60 makes to a shipped shell

The trigger **matches the logout button's visual register exactly** — `text-sm text-ink-muted hover:text-ink` plus `focusRing` — and adds `min-h-11 px-2`.

| | Logout (shipped) | «מדריך» (new) |
|---|---|---|
| Type | bare `<button type="button">` | same |
| Text | `text-sm text-ink-muted hover:text-ink` | identical |
| Focus | `focusRing` (2px `--color-focus`, 2px offset) | identical |
| Box | none — hit area ≈ 20px tall | **`min-h-11 px-2`** → 44×~60px |

⚠ **Consequence, stated rather than discovered in review: the console header grows from ≈52px to ≈68px on every section.** The row is `items-center` with `py-3` (12px each side); today the tallest child is the `text-lg` display name at ≈28px. A 44px trigger becomes the tallest child. **Taken deliberately**: `tokens.md` law 7 is a house floor and a boutique tablet is a touch surface. The background is transparent, so the 44px box is invisible — visually it is still two text labels side by side, and the extra air is the one thing the shipped row was short of.

**Not a `Button variant="ghost" size="md"`.** That is `font-semibold text-base` with a `rounded-md` hover fill, which would make the guide louder than the logout beside it and read as the header's primary action. The header is chrome; a walkthrough is not an action.

**No icon, no badge, no dot, no `aria-label`** (§0, DL20).

### 1.3 What it looks like at each width

| Width | Header |
|---|---|
| 375 | Boutique name at the inline-start; «מדריך» «יציאה» as a pair at the inline-end. Two short Hebrew words plus `gap-4` ≈ 110px — no wrap, no truncation, ≈150px of slack beside the longest plausible display name |
| 768 | Identical; the row is capped at `max-w-[720px]` and centred |
| 1440 | Identical. The console never exceeds 720px of content (`manage-restyle.md` §Responsive) |

### 1.4 Role gating is the *absence* of a code path, not a branch

The guide is keyed on `activeKey`, and `activeKey` (`App.tsx:208-210`) is already the role-filtered truth — it falls back to `reachable[0]?.key ?? section` whenever `section` is not in the role's reachable set. **So a receptionist can only ever be offered `floor`'s three steps, and F60 contains no filter, no `roles` field and no second permission table** (DL6). This is the shipped form of `floor-staff-roles`' rule: which steps exist is the rendered form of the authorization axes.

The gate the *structure* cannot express is the intra-section one — `TermsSection.tsx:20` hides the publish form from a shift manager, and `AtelierSection.tsx:1344-1356` gives a seamstress no controls at all on a colleague's ticket. **Those are handled in the copy**, by describing what the section is *for* rather than naming a control the reader may not have (DL7). Two rows of `copy.md` carry a ⚠ for it.

---

## 2. The dialog

### 2.1 Anatomy — 375 first, because that is the phone in her apron

```
  375px viewport · RTL · the console + its backdrop behind
+--------------------------------------------------+
|::::::::::: backdrop: bg-ink/40 ::::::::::::::::::|
|:  +------------------------------------------+  :|
|:  |                                          |  :|   <- <dialog>, m-auto,
|:  |  מדריך — לוח היום                        |  :|      w-[min(28rem,100vw-2rem)]
|:  |  ^ h2, font-display text-xl, text-ink    |  :|      = 343px here
|:  |    aria-labelledby target (Modal's own)  |  :|      p-6, rounded-md,
|:  |                                          |  :|      bg-surface-raised,
|:  |  שלב 2 מתוך 3 במדריך                     |  :|      shadow-lg
|:  |  ^ p, text-sm text-ink-muted   [§2.4]    |  :|
|:  |                                          |  :|
|:  |  כשלקוחה מגיעה לוחצים «הגיעה» בשורה      |  :|
|:  |  שלה, והפעולה נרשמת עם השעה; «ביטול      |  :|   <- p id={bodyId},
|:  |  הרישום» מבטל את הרישום הזה בלבד ולא     |  :|      text-base text-ink
|:  |  את התור.                                |  :|      **aria-describedby target**
|:  |                                          |  :|
|:  |  ( sr-only  <p role="status">  )         |  :|   <- §4. Zero height,
|:  |                                          |  :|      never unmounted
|:  |          [ הבא ] [ הקודם ] [ סגירה ]     |  :|   <- Modal's own footer div:
|:  |           ^primary ^secondary  ^ghost    |  :|      mt-6 flex justify-end gap-3
|:  +------------------------------------------+  :|      DOM order is the REVERSE
|::::::::::::::::::::::::::::::::::::::::::::::::::|      of the drawn order — §2.5
+--------------------------------------------------+
```

At 768 and 1440 the panel is `28rem` (448px) and everything else is identical. **There is no desktop layout** — one column, one sentence, three buttons.

### 2.2 The four regions, and the one colour this deck sets on a `Modal` child

| Region | Element | Classes | Owner |
|---|---|---|---|
| Title | `<h2 id={titleId}>` | `font-display text-xl text-ink` | **`Modal`**, unchanged. `aria-labelledby` |
| Counter | `<p>` | `text-sm text-ink-muted` | `GuideOverlay` |
| Step | `<p id={bodyId}>` | `text-base text-ink` | `GuideOverlay`. **`aria-describedby`** |
| Live region | `<p role="status" className="sr-only">` | — | `GuideOverlay`. §4 |
| Footer | 3 × `<Button size="md">` | — | `GuideOverlay`, into `Modal`'s `footer` slot |

⚠ **`text-ink` on the step paragraph is NOT the F-6 trap, and this deck says so because a reviewer will reach for it.** F-6 is about a call-site utility losing a same-property fight **on the same element** — `cn()` is a plain join and stylesheet order decides. Here `Modal.tsx:53` puts `text-ink-muted` on the **wrapper `<div>`**, and the step is a **child `<p>`** carrying its own `text-ink`. An element's own declaration beats an inherited value; there is no specificity contest and no stylesheet-order dependency. The step is the content of this dialog and it gets the content colour; the counter is chrome and keeps the inherited muted.

### 2.3 The dialog does not point at anything, and that is the design

The guide describes the section behind it and **never touches it**: no anchor, no highlight, no cut-out, no spotlight, no scroll-into-view, no arrow. The panel is `m-auto` — centred in the viewport, over the section, and the backdrop dims what it covers.

Three reasons, and the third is why this feature is **S** rather than **L**:

1. **The console is one column capped at 720px with one section on screen at a time.** There is no canvas to get lost on; "the thing I am describing" is the whole of `#console-main`. A spotlight would dim four-fifths of a screen that is already the subject.
2. **Anchoring is a moving target.** Nine features changed these fourteen sections today. An anchor is a selector into somebody else's component, and the first refactor that renames a wrapper turns the guide into an overlay pointing at nothing — silently, with every test green.
3. **A positioning engine is the dependency.** Remove anchoring and the entire argument for a tour library evaporates, which is exactly what spec *Codebase conflicts* 4 records as a positive finding.

**What the reader loses:** she cannot see the section while reading about it. **What she does instead:** «סגירה», look, «מדריך» again. Two taps, on a walkthrough she reads once. That is the trade, taken knowingly.

### 2.4 The step indicator is a sentence, never a row of dots

«שלב 2 מתוך 3 במדריך», `text-sm text-ink-muted`, above the step and below the title.

- **Not dots.** A pip row carries state in fill colour alone (`tokens.md` law 2), so it needs `aria-hidden` **plus** a visually-hidden text equivalent — two mechanisms and a second thing to keep in sync — where a counter is one element that both users read.
- **Not a bar.** `DashboardSection`'s own `Bar` comment states the house rule: `role="progressbar"` announces a *task's* completion, and a reader is not completing a task.
- ⚠ **The trailing «במדריך» is load-bearing twice.** (a) It keeps **both digits between Hebrew words**, which is D5's bidi constraint, satisfied here without `isolateLtr` — and `isolateLtr` is not merely unnecessary but **wrong** for this string, because it splits on `indexOf` (`lib/booking.tsx:76`) and on the last step («שלב 3 מתוך 3») it would isolate the *first* 3 and leave the trailing one bare. (b) The live region utters counter-then-step **alone**, with no chrome around it; one word naming which of the console's `role="status"` regions is speaking is the same argument `floor.idleStopped` makes against being byte-identical to `board.idleStopped`.

### 2.5 The footer — and F60 is this console's first three-control `Modal` footer

DOM order, following `SosRaiseDialog:196-201`'s house pattern (*"ghost dismiss + secondary confirm"*) and `HoursSection:324-330`'s («ביטול» ghost, then «הסרה»): **the dismiss is first in the DOM, the primary is last.**

| DOM | Label | Variant | Present on |
|---|---|---|---|
| 1 | «סגירה» | `ghost` | **every step** |
| 2 | «הקודם» | `secondary` | steps 2..N |
| 3 | «הבא» → «סיום» on the last step | `primary` | every step |

`Modal`'s footer is `mt-6 flex justify-end gap-3`, so in RTL the group sits at the physical **left** and reads (right → left) «סגירה» «הקודם» «הבא». **The dismiss is nearest the content and the primary is in the far corner — the shipped order, unchanged.**

⚠ **This is the console's FIRST footer that renders three controls at once, and the deck verified that rather than assuming it.** All fifteen shipped `Modal` call sites render at most two: `SosRaiseDialog`'s three `<Button>`s are two branches of a ternary; `RescheduleDialog`'s third is inside the body, not the footer. The spec cites the house pattern correctly but the pattern is a **two**-control one, so §2.6 does the arithmetic instead of inheriting it.

**«הקודם» is absent on step 1, not disabled** (DL10). Inside a focus trap every Tab stop is one the user must walk past; a disabled control earns nothing and `Button.tsx:57` is `disabled={disabled || loading}`, which blurs a tapped control and drops focus. **«סגירה» is present on every step** (DL19) — `Modal` binds no backdrop click and the chrome has no X, so without it step 1 is a top-layer dialog containing exactly one control and a boutique tablet with no Esc key can only leave by tapping through to the end.

**On the last step «הבא» is replaced by «סיום» in the same position.** The control under her finger changes identity, deliberately: it is the same slot, it is labelled, and the alternative — a disabled «הבא» beside a «סיום» — puts a dead control inside a trap.

### 2.6 The narrow-viewport arithmetic, because `Modal`'s footer cannot wrap

⚠ **CORRECTS the spec.** *Every state* → *Narrow viewport* says *"Three footer buttons at `size="md"` wrap rather than shrink."* **They cannot wrap** — `Modal.tsx:54` is `flex justify-end gap-3` with **no `flex-wrap`**, so flex items shrink and a too-long label wraps *inside* its own button. The conclusion (this is fine at 375) is right; the mechanism is not. Here is the measurement instead:

| | at 375px |
|---|---|
| Panel | `w-[min(28rem,calc(100vw-2rem))]` → **343px** |
| minus `p-6` × 2 | content box **295px** |
| «סגירה» | `px-4` (32) + ≈44px of `font-semibold` Hebrew at 16px = **76px** |
| «הקודם» | 32 + ≈44 = **76px** |
| «סיום» (widest primary) | 32 + ≈35 = **67px** |
| two × `gap-3` | **24px** |
| **total** | **≈243px** — fits with ≈50px of slack |

`Button.tsx:18-20` sets no `whitespace-nowrap`, so the failure mode at extreme browser zoom is a label wrapping to two lines inside its button — legible, operable, and not a loss of content. **WCAG 2.0 AA has no reflow SC** (1.4.10 is 2.1), so this is below the legal floor as well as above the usable one. The escape hatch, if it is ever wanted, is `flex-wrap` on `Modal`'s footer — **a `Modal` edit that reopens fifteen call sites, which this feature has not earned.**

`data-a11y-text-size`, the A11yMenu's text boost, cannot reach this surface: `A11yMenu` is **storefront-only** (`tokens.md` §Spacing).

### 2.7 Motion

`Modal` already animates the panel (`animate-modal-panel`, scale 0.97→1 + fade at `--motion-base`) and the `::backdrop` (fade at `--motion-fast`). **F60 adds nothing and changes nothing.**

- **Step changes are instant.** A crossfade would be motion inside the region a live announcement is reading, and it would mean the old sentence is briefly still on screen while the new one is announced.
- **Closing is instant** — `close()` is synchronous; `Modal` has no exit animation for any of its fifteen callers. §5 depends on this.
- `prefers-reduced-motion: reduce` is already global (`theme.css:155-163`) and kills both. Nothing to add.

---

## 3. The focus contract, drawn

Everything here is browser behaviour of `<dialog>` + `showModal()` unless marked **[F60]**. **Every line is a named E2E test**, because `e2e/manage.spec.ts:26-30` and `e2e/sos.spec.ts:28-40` both open with the same paragraph: jsdom is not a browser and every focus assertion in this repo is measured in Chromium.

```
   [ מדריך ]                                     ← focus starts here
       │  click                                          [F60] the ONLY writer of `open`
       ▼
   showModal()  ──▶  focus lands on the FIRST focusable descendant
       │                     = «סגירה»  (§2.5's DOM order decides this,
       │                       and NOTHING in F60 calls .focus() — D4.1)
       │
       │   Tab ──▶ סגירה → הקודם → הבא → סגירה → …        cycle, T2
       │   Shift+Tab ──▶ סגירה → הבא → הקודם → סגירה → …  cycle, T3
       │   the console behind is INERT: no Tab stop, no click, no hit test
       │
       │   «הבא» / «הקודם»  ──▶  index changes, FOCUS DOES NOT MOVE  [F60]
       │                          (four steps cost four presses,
       │                           not four presses + four Tabs — DL8)
       │
       ├── Esc ─────────────┐
       ├── «סגירה» ─────────┤
       ├── «סיום» ──────────┼──▶  close()  ──▶  focus RETURNS to [ מדריך ]
       └── an SOS page (§5) ┘                   on ALL FOUR routes
```

| # | Contract | Owner | Test |
|---|---|---|---|
| 1 | Focus is **inside the dialog** after open, on «סגירה» | platform | **T1** |
| 2 | Tab and Shift+Tab cycle within; neither reaches the console | platform | **T2**, **T3** |
| 3 | Esc closes from anywhere inside — and `SosOverlay`'s document **capture** listener returns early while `dialog[open]` matches (`:298`), so Esc never means two things at once | platform + F37 | **T4**, **T8** |
| 4 | Focus returns to «מדריך» on all four close routes | platform | **T5**, **T6**, **T6b**, **T7** |
| 5 | **The guide never opens itself.** `open` is `useState(false)` with exactly one writer — the trigger's `onClick`. No effect, no timer, no storage read, no first-visit branch | **[F60]** | vitest §3 |
| 6 | Step changes move no focus | **[F60]** | vitest §4 |

**Why «סגירה» holding first focus is right and must not be "fixed".** It is a labelled, non-destructive control, and the step is announced by `aria-describedby` regardless of which control holds focus (§4). Adding `autofocus` or a manual `.focus()` on top of the platform's entry is two engines deciding one thing — the class of defect this contract exists to refuse.

---

## 4. The announcement contract, drawn

Three mechanisms, one job each. **The dialog is announced on open by the platform; the region only ever speaks on a CHANGE.**

```
  t0  click «מדריך»
      [F60] setIndex(0) · setAnnounced("") · skipRef = true · setOpen(true)
                                                    ^^^^^^^^^^^^^^^^^^^^^ in THIS order
  t1  showModal()
      AT says:  «מדריך — לוח היום»          ← aria-labelledby  (Modal, shipped)
                «הלוח מציג את תורי היום…»    ← aria-describedby (the ONE new prop)
                «סגירה, לחצן»                ← the focused control
      live region:  EMPTY.  Silent, deliberately.

  t2  «הבא»
      effect on [index] runs → setAnnounced("שלב 2 מתוך 3 במדריך · <step 2>")
      AT says:  «שלב 2 מתוך 3 במדריך · כשלקוחה מגיעה…»   ← role="status", polite
      focus:    still on «הבא». Nothing moved.

  t3  «הקודם»  → index changed → the region speaks again. Going BACK announces.

  t4  Esc / «סגירה» / «סיום»
      AT says:  «מדריך, לחצן»                ← focus returned to a labelled control
      No close cue. A cue for "the help closed" is noise.
```

| When | Mechanism | Why not the others |
|---|---|---|
| **Open** | `aria-labelledby` (title) + **`aria-describedby`** (step) | A live region freshly inserted *with* content is announced by some ATs and not others. Unreliable is worse than silent |
| **Step change** | `sr-only <p role="status">`, **mounted for the dialog's whole lifetime**, text written from an effect on `index` | `aria-describedby` does not re-fire when the described text changes. Moving focus would announce it, at the cost of contract 6 |
| **Close** | nothing | Focus returns to a labelled button and the AT reads it |

**"On change, not on every render" is four properties, and each is one line that has been got wrong elsewhere in this repo:**

1. **Never conditionally mounted.** `Modal.tsx:53` renders `{children}` whether `open` is true or false — the `<dialog>` and everything in it stay mounted, hidden only by the UA's `display:none`. Remounting a live region re-announces it, which would fire on every unrelated re-render of the section behind.
2. **Content is state**, written by `useEffect(…, [index])` — not `t(steps[index])` inline. `AtelierSection.tsx:445-449` records the mechanism: assigning a string to a text node is a real childList mutation inside `role="status"` **even when the two strings are byte-identical**, and `setState` with an equal value is a React no-op — **so the `setState` is the guard**.
3. **The effect skips its first run after open**, via a ref reset in the trigger's `onClick`. Without it, open announces twice.
4. **The region is CLEARED on open** (`setAnnounced("")`). Because it is never unmounted (1) and the effect skips (3), without this it still holds **the last step of the previously visited section** and transitions from `display:none` to exposed carrying that stale sentence — which several ATs announce. This is invisible on a session's first open, which is why vitest §5 has a close-navigate-reopen leg.

⚠ **What the open announcement does NOT include: the counter.** `aria-describedby` points at the step paragraph alone (spec AC5 pins the assertion to it), so a first-time listener hears the sentence but not «מתוך 3». **Accepted**: the counter is orientation, not content, and it arrives on the first «הבא». **The upgrade path costs zero code in `Modal`** — `aria-describedby` takes a *space-separated ID list* by the ARIA spec and `describedById` is a plain string React writes verbatim, so `describedById={`${counterId} ${bodyId}`}` is a one-call-site change if the manual screen-reader pass asks for it. Named here so that pass has something to test against.

---

## 5. An SOS page landing on top

**This is the only way this feature can hurt anybody**, and it is the reason §5 is longer than §2.

### 5.1 Why the guide has to get out of the way

`showModal()` promotes the dialog to the browser's **top layer**. The top layer paints above every `z-index` in the document — including `SosOverlay`'s `z-40` — and makes every node outside the dialog **inert**: unclickable, unreachable by Tab, invisible to hit-testing. There is no z-index, no portal and no stacking context that changes this. **Raising `SosOverlay` above a top-layer dialog is not possible.**

So with the guide open, an arriving emergency page is not merely covered — it is **unanswerable**. Closing the guide is the only mechanism that exists (DL11).

### 5.2 The three frames

```
FRAME 0 — guide open, no page
+--------------------------------+
|::::::: bg-ink/40 backdrop :::::|
|:   +----------------------+   :|
|:   |  מדריך — לוח היום    |   :|   top layer
|:   |  שלב 2 מתוך 3 במדריך |   :|   console behind = INERT
|:   |  כשלקוחה מגיעה…      |   :|
|:   |   [הבא][הקודם][סגירה]|   :|
|:   +----------------------+   :|
+--------------------------------+

FRAME 1 — the poll tick that carries the alert.  ONE COMMIT, and it is NOT drawn
          because it is never painted for a whole frame in practice:
          SosOverlay is mounted BEFORE ConsoleShell (App.tsx:236-237) so its
          effects flush first; its red field mounts UNDER the top-layer dialog
          and is inert.  GuideOverlay's own effect runs in the same commit and
          calls setOpen(false).

FRAME 2 — the next commit: close() runs
+--------------------------------+
|############ bg-danger #########|
|#                              #|
|#  דנה כהן קוראת לעזרה         #|   full screen, opaque
|#  חדר 2                       #|   (SosOverlay.tsx:451)
|#  צריך סיכות                  #|
|#  מאז 11:20                   #|
|#        [ אני מגיעה ]         #|
|#                              #|
+--------------------------------+
   focus is on [ מדריך ] — BEHIND this field.  §5.3.
```

**No transition between frames.** `close()` is synchronous and `Modal` has no exit animation. The dialog and its backdrop are gone in one paint and the red field is simply there.

### 5.3 ⚠ Where focus ends up, and the one thing the spec does not say out loud

Spec D6's *What the user sees* says *"focus returns to the «מדריך» button; the red page is on screen."* **Both are true and they are the same pixel region.** `SosOverlay.tsx:451` is `fixed inset-0 z-40 … bg-danger` — opaque and full-screen — so the returned focus sits on a button that is now **underneath** the emergency, with an invisible focus ring.

Recorded rather than repaired, for four reasons:

1. **It is not a WCAG 2.0 AA failure.** SC 2.4.7 Focus Visible requires a visible indicator *for the focused element*; "focus not obscured" is **SC 2.4.11, WCAG 2.2 AA**, and IS 5568 is WCAG 2.0 AA. Below the legal floor — and stated here so that the next reviewer who spots it does not re-derive it.
2. **The state lasts exactly one keypress.** Esc from anywhere reaches «אני מגיעה» via `SosOverlay`'s capture listener (`:298-313`), which is un-guarded the instant `dialog[open]` stops matching. Tab reaches it too.
3. **The alternatives are worse and are the same defect.** Moving focus ourselves into the card is a second focus authority beside `SosOverlay`'s own MOVE A — two engines, one decision. Disabling or hiding the «מדריך» button during an emergency drops focus to `<body>` when `close()` returns it to a control the same commit removed (DL13) — the sixth instance of this repo's most-shipped defect.
4. **MOVE A is consumed with no effect and that is accepted, not engineered around.** `SosOverlay`'s MOVE A fires only when `document.activeElement === document.body` (`:203-205`) and is consumed once per rising run via `hadCardsRef`. In FRAME 1 focus is inside the dialog, not on `<body>` — but whether it can degrade to `<body>` after a click on non-focusable dialog content is engine-dependent and **must not be assumed either way**. If the guard reads true, the `.focus()` lands on an inert node and does nothing while `hadCardsRef` is already set. **The spec declined the layout-effect fix in writing and this deck agrees**: it buys back one focus move whose absence costs nothing, in exchange for an invisible cross-component ordering dependency. **T7 leg (b) measures it in Chromium** rather than reasoning about it here.

⚠ **Handed to the manual screen-reader pass on this PR**: the sequence at FRAME 2 — a `role="alert"` mounting in the same commit that a `<dialog>` leaves the top layer, with focus returning to an obscured button. That is the one interaction in this feature no automated tool in this repo can observe.

### 5.4 What does *not* close the guide

Only a **`for_me`** page. The channel-down strip and the "N hidden" affordance (`SosOverlay:618`) are not full-screen, are not urgent, and closing a walkthrough for them would be noise. **Scope, and it is the whole scope.**

### 5.5 The detector's shape is a design constraint, not just an implementation one

It is **edge**-triggered over a **set difference** on `SosOverlay`'s **composite** key. The three failures it avoids all end with the same picture — a full-screen emergency painted under an inert top-layer dialog:

| Wrong shape | What the user gets |
|---|---|
| Level (`forMe.length > 0`) | She dismissed a page; the guide slams shut on **every 5s tick** and she can never open it again. Dismissal is deliberate and per-device (`SosOverlay:322-330`) |
| Head-of-list (`forMe[0]`) | A **second** page is invisible: `sos.tsx:129-131` appends oldest-first, so a new alert lands at the **end** |
| Bare id | An **escalation or stall re-rise** is invisible: `dismissKey` (`SosOverlay:59-61`) is `` `${id}:${escalated}:${stalled}` `` precisely because each re-rises the card once |

**A change to `SosOverlay.dismissKey` is a change to this detector.** Say so in the effect's comment, in the shape `SosOverlay:48-58` uses for its own key.

---

## 6. The storefront `/checkin` hint — a reveal-only disclosure

Different surface, different shell, different user, and this repo has already ruled on the trade twice.

### 6.1 Placement

```
  /checkin — 375, RTL, in page flow.  NOTHING is fixed, NOTHING is covered.
+--------------------------------------------------+
|  רישום לתור                                       |  Heading
|                                                   |
|  הרישום האחרון שנעשה מהמכשיר הזה                  |  ← only when `pointer` exists
|                                                   |    (CheckinPage.tsx:254-266)
|  [ מה קורה אחרי הרישום? ]                         |  ← NEW: Button ghost, size md
|                                                   |    aria-expanded, min-h-11
|  הרישום מכניס אותך לתור ההמתנה של הבוטיק —        |  ← NEW: <p id={hintId}>,
|  בסיום נפתח עמוד עם מקומך בתור…                   |    IMMEDIATELY after in DOM
|                                                   |
|  שם מלא          [___________________]            |  ← the first Input
|  טלפון נייד      [___________________]            |
|  סוג הביקור      ( מדידת כלה )( שמלת ערב )        |
|                                                   |
|  הפרטים שאת ממלאת כאן נשמרים אצל…                 |  ← checkin.notice — UNTOUCHED,
|  [ ] אני מאשרת פניות שיווקיות…                    |    still above the box it
|                                                   |    describes, still never
|  [ שליחה ]                                        |    behind a disclosure
+--------------------------------------------------+
|                                     ( ♿ A11yMenu )|  ← fixed, statutory, storefront-only
+--------------------------------------------------+
```

**Below the `pointer` offer link, above the first `<Input>`, in both arms.** Putting an orientation hint above a live "resume your existing ticket" link would bury the more useful control.

`size="md"` (`min-h-11`), matching the retry (`:242`), the submit (`:316-324`) and the visit-type chips' explicit `min-h-11 min-w-11`. **This page has a 44px floor on a public phone surface and F60 does not lower it.**

**A fixed control is impossible here anyway**: `StorefrontLayout.tsx:186-199` puts the statutory `A11yMenu` trigger in the block-end inline-end corner on every route, and a second fixed control would collide with it.

### 6.2 What it is, exactly

`Button variant="ghost" size="md"` carrying `aria-expanded={revealed}` and `aria-controls={revealed ? hintId : undefined}`, with `<p id={hintId}>` **immediately after it in DOM order**. That is the APG disclosure in full: `aria-expanded` announces the state, and the reader's very next item *is* the hint.

**Nothing else. No `tabIndex={-1}`, no ref, no effect, no `onKeyDown`, no Esc handler, no focus move.**

`aria-controls` only while revealed — a dangling IDREF is what axe reports as `aria-valid-attr-value` (`A11yMenu.tsx:120-122`).

**No chevron, no «▾», no rotation.** The label is a question and `aria-expanded` is the state; a glyph would be a third signal that a screen reader names in a vocabulary this product did not choose.

### 6.3 Why no focus move, given that `ManageBookingPage` ships one

This is the **third** deck to decline that shape, and the reasons compound:

1. `ManageBookingPage` has **no Esc handler anywhere in the file** — its close is a ghost «ביטול» (`:469-483`). An Esc handler is only needed *because* focus moved.
2. Its focus move is the **one frontend entry on `LOOP-STATE.md`'s `known_flaky` list** — *"the cancel two-step :: moves focus into the revealed block"*, a jsdom focus/timing race that has already parked a green PR — and `fitting-rooms/design.md` §5.3 and `floor-dispatch/design.md` P-4 each recorded a deliberate decision to avoid it (*"A11y coverage is a reason to pick the simpler element"*). Adopting it here would be the third feature to inherit a known flake onto a merge gate, on the lowest-priority item in the program.
3. **There is nothing to move focus to.** `ManageBookingPage` reveals a decision with two buttons; this reveals one sentence with nothing focusable in it. A `tabIndex={-1}` paragraph is a focus destination invented so an Esc handler has something to close from — and that handler half-works anyway, since one Tab out of a childless `<p>` leaves Esc doing nothing.

**T9 is the whole a11y claim on this surface**: reveal it, Tab, focus reaches the name field. *Nothing is trapped* is the only thing that matters here.

### 6.4 The content fence — positive, not negative

⚠ **The hint states no data-handling fact of any kind.** It names the **queue**: what checking in puts her into, what she gets back, and that a member of staff calls her. `CheckinPage.tsx:299-302` rules directly against the alternative — *"The notice sits ABOVE the box it describes, and is never behind a disclosure: notice at the moment of collection means visible at the moment of collection"* — so a collapsed «מה קורה עם הפרטים שלי?» beside a legally-mandated always-visible notice would be a second, unapproved notice at the same collection point, **and it would void this spec's Gate 1 self-approval** ("no privacy-law text"). `checkin.notice` remains the only data-handling text on the page and F60 does not touch a character of it.

**If the intended content genuinely is data handling, Gate 1 stops being self-approving and the feature stops for the user** (DL15, spec Q1).

---

## 7. Every state

| State | Console | `/checkin` |
|---|---|---|
| **Closed / collapsed** | Only «מדריך» in the header. The `<dialog>` is in the DOM with no `open` attribute, so `SosOverlay`'s guard does not match and Esc keeps its SOS meaning | Only the button. `aria-expanded="false"`, **no** `aria-controls` |
| **First step** | Counter «שלב 1 מתוך N במדריך». Footer «סגירה» + «הבא» (or «סיום» when N = 1 — unreachable today, every section has 2 or 3). **«הקודם» absent, not disabled.** A pointer-only user leaves in one tap via «סגירה». Live region **empty** | n/a — one paragraph, no steps |
| **Middle step** | «סגירה» + «הקודם» + «הבא». Live region carries counter + step | n/a |
| **Last step** | «סגירה» + «הקודם» + **«סיום»** | n/a |
| **Reopened after a section change** | Step 1, counter reset, **live region empty again**. The previous section's sentence is *gone*, not un-hidden (§4 property 4) | n/a |
| **Section with no steps** | **Unrepresentable** — `satisfies Record<SectionKey, readonly [string, ...string[]]>` makes it a compile error, and `typecheck` gates the merge. The button can never offer help that is not there | n/a |
| **Out-of-enum role** | `reachable` is empty, `activeKey` stays `dashboard`, and the guide offers `dashboard`'s two steps over `DashboardSection`'s 403 outage panel. **Accepted** — every step describes a *screen*, not its data, and 0011's CHECK makes the row impossible in the database | n/a |
| **SOS arrives while open** | §5. Guide closes, focus returns to «מדריך» (obscured, §5.3), the red page is on screen and its ack is clickable. Holds for a second page over a first and for an escalation re-rise | n/a — no SOS on the storefront |
| **375px** | Panel 343px with 16px gutters; the panel covers most of the screen and that is correct — this is a modal and there is nothing behind it to read. One sentence, no scroll. Footer fits with ≈50px of slack (§2.6) | Inline. Nothing is covered; the form moves down |
| **`pointer` present + revealed** | n/a | Both render, in DOM order: the «הרישום האחרון…» link, the trigger, the paragraph, then the name field. Nothing is repositioned |
| **Degraded `/checkin`** | n/a | **Withheld in both arms with the form** (`CheckinPage.tsx:229-248`) — no boutique, no form, nothing to explain |
| **Loading** | The trigger renders as soon as the shell does; sections own their own skeletons. Steps describe a screen, not its data, so they are correct before the data lands | Withheld with the form |
| **`prefers-reduced-motion`** | Panel and backdrop animations already killed globally. Nothing else moves | Nothing moves at all |

---

## 8. A11y ledger

| Claim | How it is held | What proves it |
|---|---|---|
| Focus enters the dialog on open | `showModal()` | **T1** (Chromium) |
| Tab / Shift+Tab cycle, console unreachable | `showModal()` inerting the document | **T2**, **T3** |
| Esc closes from anywhere inside | `<dialog>` `cancel` → `Modal.onCancel` (`:38-42`) | **T4** |
| Esc never means two things | `SosOverlay:298`'s `dialog[open]` early return | **T8** |
| Focus returns to «מדריך» on all four routes | `close()` | **T5**, **T6**, **T6b**, **T7** |
| A pointer-only user can leave step 1 | «סגירה» in the footer (DL19) | **T6b** |
| Step 1 is audible on open | **`aria-describedby`** — the one new prop | vitest §7 / **AC5** |
| Step changes announce once, on change | `role="status"` + the four properties of §4 | vitest §5 |
| The guide never steals focus | one writer of `open` | vitest §3 |
| `/checkin` traps nothing | it is a paragraph | **T9** |
| No colour-only signal | there is no colour-borne state in this feature | by construction |
| WCAG 2.5.3 label-in-name | the trigger has visible text and **no `aria-label`** (DL20) | by construction |
| 44×44 | `min-h-11` on the trigger (§1.2) and `size="md"` everywhere else | — |

⚠ **What axe cannot see, and it is most of the above.** axe reports none of the focus class — this repo has shipped a focus-drops-to-`<body>` defect five times (`e2e/sos.spec.ts:32-35`, in as many words) and axe was green every time. **And no vitest test in this feature may assert focus at all**: jsdom 29.1.1 ships no `<dialog>` implementation (`HTMLDialogElement-impl.js` is an empty subclass of `HTMLElementImpl`) and all three `src/test/setup.ts` files stub `showModal` with a body that is literally `this.open = true` — no focus move, no trap, no top layer, **no `cancel` event on Esc**. Every focus assertion a vitest test could write would measure that stub. **That is DL17, and §7 of the vitest block is the one permitted exception because it is a plain IDREF read with no focus and no `<dialog>` behaviour in it.**

The two axe passes (`wcag2a`, `wcag2aa`) are the console with the guide open and `/checkin` with the hint revealed. **They are the floor, not the proof.**

---

## 9. Resolved design questions

No open ones. Each was a real fork; each is closed here.

| # | Question | Resolution |
|---|---|---|
| **P-1** | Counter above or below the step? | **Above.** Orientation, then content — and it puts the two `role="status"` sentences in the same order as the visible ones |
| **P-2** | Dots, a bar, or a counter? | **Counter** (§2.4). A pip row is a colour-only signal needing two mechanisms; a bar would need `role="progressbar"`, which announces a task |
| **P-3** | Does the trigger get an icon or a dot? | **No.** The console ships no icon vocabulary, and a dot would be an unread-badge for content that is never new |
| **P-4** | Is the trigger a `Button` or a bare button like «יציאה»? | **Bare, matching «יציאה» exactly**, plus `min-h-11 px-2` for law 7. A ghost `Button` is `font-semibold text-base` and would outrank the logout beside it (§1.2) |
| **P-5** | Does the dialog anchor to, or highlight, the section? | **No** (§2.3). It is the reason there is no positioning engine and therefore no dependency |
| **P-6** | Any transition on a step change? | **No** (§2.7). Motion under a live announcement leaves the old sentence on screen while the new one is read |
| **P-7** | A chevron on the `/checkin` disclosure? | **No** (§6.2). `aria-expanded` is the state; a glyph is a third signal in a vocabulary the product did not choose |
| **P-8** | Does closing on an SOS page get a transition or a cue? | **No** (§5.2). `close()` is synchronous, `Modal` has no exit animation, and a cue would be a sentence competing with an emergency |
| **P-9** | Does `aria-describedby` cover the counter too? | **No** — AC5 pins the assertion to the step paragraph. The upgrade path needs **zero `Modal` change** (§4, closing note) and is handed to the manual SR pass |
| **P-10** | Should the guide re-key (`key={section}`) so a section change remounts it? | **No.** The only writer of `activeKey` is `ConsoleShell`'s `onNavigate`, which `showModal()` has made inert. One token if a later feature ever changes `section` programmatically (spec D2) |

---

## 10. Findings for the spec

The spec is **not edited from here**; these are reported.

**F-1 ⚠ CORRECTS the spec — `Modal`'s footer cannot wrap.** *Every state* → *Narrow viewport* says three `size="md"` buttons *"wrap rather than shrink"*. `Modal.tsx:54` is `flex justify-end gap-3` with **no `flex-wrap`**; flex items shrink and a long label wraps inside its own button. The conclusion is unaffected — §2.6 measures ≈243px of buttons in a 295px content box at 375 — but the stated mechanism is wrong and a builder who trusts it will not do the arithmetic.

**F-2 ⚠ F60 ships this console's FIRST three-control `Modal` footer.** All fifteen shipped call sites render at most two at once: `SosRaiseDialog:190-215`'s three `<Button>`s are two ternary branches, and `RescheduleDialog:107-119`'s third is in the body. The spec correctly cites `SosRaiseDialog:196-201` as "the house pattern", but that pattern is *ghost dismiss + one confirm* — a **two**-control shape. F60 extends it rather than inheriting it, which is why §2.5 states the DOM order and §2.6 measures the row instead of assuming both.

**F-3 ⚠ CORRECTS D5's example, and the constraint it states is unsatisfiable as written.** D5 illustrates the counter as «שלב 2 מתוך 4»; **N is 2 or 3 for every one of the fourteen sections**, so «מתוך 4» is unrepresentable. More importantly D5 requires *"Both digits must sit between Hebrew words … neither at a string edge"*, and a two-number Hebrew counter **cannot** satisfy that without a trailing noun — «שלב {{step}} מתוך {{total}}» leaves `{{total}}` at the edge. Resolved by copy, not by code: **«שלב {{step}} מתוך {{total}} במדריך»**. ⚠ **And `isolateLtr` is not the alternative**: it splits on `indexOf` (`lib/booking.tsx:76`), so on «שלב 3 מתוך 3» it would isolate the *first* 3 and leave the trailing one bare — the last step, which is the most-visited one.

**F-4 ⚠ Four of the fourteen sections have NO i18n at all, which sharpens R1 and R7 into something a builder can act on.** `grep -c useTranslation` returns **0** for `HoursSection.tsx`, `TypesSection.tsx`, `TermsSection.tsx` and `CatalogSection.tsx` — their Hebrew is hardcoded in the component (`HoursSection:172-269`'s «יום / פתיחה / סגירה / קיבולת / סגור כל היום / הערה»; `TypesSection:77-113`'s «שם / משך (דקות) / קהל יעד / נדרשת מקדמה / מקדמה (₪) / סדר תצוגה»; `TermsSection:128-144`; `CatalogSection:122-247`). R1 says each sentence must be written *"with the section component open"*; for these four **that is the only place the words exist**, and a copywriter working from `he.ts` will invent labels the screen does not use. `copy.md` §0 rule 4 makes this a hard rule and every affected row is cited to its component line.

**F-5 ⚠ The trigger's 44px box grows the console header ≈16px on every section** (§1.2). Not a spec error — the spec never sizes the trigger — but it is F60's one visible change to a shipped shell and it should not be discovered in review. Taken deliberately for `tokens.md` law 7.

**F-6 ⚠ `guide.title` interpolates a nav label, and five of the fourteen labels live in a NESTED object.** `he.ts:14-20` keeps `nav: { profile, hours, types, terms, catalog }` while the other nine are flat dotted literals (`"nav.bookings"`, `"nav.board"`, …). `t("nav.profile")` resolves by the nested walk and `t("nav.bookings")` by `ignoreJSONStructure`'s flat fallback, **so no code change is needed and none should be made** — the nested block is the file's merge-conflict zone (`he.ts:425-429` says so). Recorded because `HE_F60`'s `startsWith("guide.")` filter sees none of them, which is correct and is exactly why D8 adds no `nav.` term to the selector.

**F-7 ⚠ D6's "the red page is on screen" and "focus returns to the «מדריך» button" describe the same pixels.** `SosOverlay.tsx:451` is `fixed inset-0 z-40 … bg-danger` — opaque, full-screen — so the returned focus is obscured (§5.3). **Not a WCAG 2.0 AA failure** (focus-not-obscured is SC 2.4.11, WCAG **2.2**), the state lasts one keypress, and every alternative is a worse defect — but the spec does not say it, and the next reviewer will spend an hour re-deriving it. Handed to the manual screen-reader pass on this PR.

**F-8 The `checkinQr` step count is the one place D1's table and the screen disagree about difficulty.** `CheckinQrSection` is 99 lines with a single `printCta`, and two steps is generous for it; `floor` is three panels totalling ~2,900 lines across `FloorPanel`/`RoomsPanel`/`WaitlistPanel` and three steps is tight. **Not changed** — the totals are a spec ruling and `GUIDE_STEPS`' shape makes any count representable — but `copy.md`'s `floor` rows are the three longest sentences in the deck for this reason, and that is the trade rather than an oversight.
