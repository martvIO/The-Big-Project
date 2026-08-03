# Screen: Public wall-screen queue board (F59 — `apps/storefront`, route `/queue`, Epic E6)

**Date**: 2026-08-03 · **Status**: **DESIGN GATE SELF-APPROVED** under the 2026-07-31 ruling (`LOOP-STATE.md` `rulings_2026_07_31`, "DESIGN GATES SELF-APPROVED for this run"), and because this screen assembles from shipped `@boutique/ui` primitives and adds no component and no variant (§0).
**Designer**: Claude · **Consumes**: `.planning/specs/public-queue-board.md` (**D1–D14**, Gate 1 standing approval) · `.planning/design/screens/shift-board/design.md` (F34's deck — this screen inherits its 2.2.2 framing and its live-region split) · `tokens.md` rev 1 (**binding**) · `packages/ui` and `apps/storefront` **as shipped at PR #36's merge commit**
**Copy**: `copy.md` in this directory — every Hebrew string with its untranslated `ar` value (Interview Q3 / pre-decided #47).
**Prototype**: **none, and that is a decision rather than an omission.** F34 shipped `prototype.html` because Interview **Q2** named its board a genuinely novel interaction pattern and because the two questions it raised (is a 5s beat usable under a thumb, is one-tap check-in right) are only answerable by pressing something. F59 raises neither: the interaction surface is **one button**, copied wholesale from a page that shipped in PR #36, and the only genuinely novel question — *is this legible from a seat four metres away* — **cannot be answered in a browser window on a laptop at 60cm.** A prototype would demonstrate the wrong thing convincingly. The two honest checks are §1's millimetre arithmetic and A30's `toBeInViewport()` at 1920×1080; the third is a photograph on the pilot day, which is not a design deliverable.

**⚠ Read §9 first if you are reviewing.** Fourteen findings. **Three are build-blocking** — a wrong type-scale table in the spec (**F-1**), a 4K case where the name falls below the brief's own legibility floor (**F-2**), and a pause-control class that `cn()` cannot make win (**F-4**) — and one is a copy defect that ships ungrammatical Hebrew at an ordinary count (**F-6**).

---

## 0. Scope

One route, one page, one button.

| Surface | Component | Shape |
|---|---|---|
| The wall board | `apps/storefront/src/routes/QueueBoardPage.tsx` (**new**) | heading + gold ornament → freshness line + pause control → `<ul>` of ≤5 rows → overflow line → two `VisuallyHidden role="status"` regions |

**Zero new `packages/ui` components, zero new variants, zero new tokens, zero new colour pairs.** Everything is `Button` (ghost, md), `Skeleton` (block), `VisuallyHidden`, `cn`, `JERusalem` and the shipped `theme.css` tokens. This survived the whole design: the one place a new thing could have been forced is the called row's highlight, and §2.2 closes it with a `border-gold-strong` inline-start rule that the gold law already permits as a non-text UI boundary. **No `EmptyState`** — and that is a decision with arithmetic behind it (§4, state `W-empty`), not an oversight.

### Binding inheritances (obeyed, not restated)

From **`tokens.md` rev 1**: the gold law (`--color-gold-strong` never carries text; `--color-gold` is decorative only); focus ring on every interactive element; ≥44×44 touch targets; no raw px in app code except the established container `max-w-[…]` precedent (`QueuePositionPage.tsx:19`, `StorefrontLayout.tsx:147`); `prefers-reduced-motion` is already global (`theme.css:165-173`).
From **F34's deck**: the three-region live-region split; a poll may never write into an announced region; status is never signalled by colour alone; a freshness line is *readable, reachable and not in a live region*, never `aria-hidden`; `<bdi dir="ltr">` for numeric runs and **bare `<bdi>`** for customer-authored text.
From the **spec**: no ticket id on the wire; no dispatch of any kind; no migration; no `sessionStorage`; no staff surface; five rows on the server; no motion; no idle stop; no terminal on the loop; no second gate and no feature flag.

### Explicitly NOT here — with the reason

| Not shipped | Reason |
|---|---|
| **Scrolling, paging, marquee or a carousel for a long queue** | D8. Each drags SC 2.2.2 out of *auto-updating*, where one button discharges it, and into *moving/scrolling*, where it does not — and a woman hunting for her own number on a list that pages away under her eyes is worse off than one who reads «ועוד 35 בתור». One static line. |
| **A highlight, fade, pulse, crossfade or shimmer when a row changes** | D8/D11(b). This is the substantive protection the room can actually be given: a board whose data has not changed produces **no visual change at all**, because React commits only changed text nodes. It discharges SC 2.3.1 and `prefers-reduced-motion` by construction rather than by a media query, and it is what makes the screen calm to sit beside for an hour. |
| **The boutique's name anywhere on the board** | **F-11.** It costs ~49px of a band with 68px of slack (§1.3), the room already knows which shop it is standing in, and `StorefrontLayout` does not render it on any route (**F-5**) so there is nothing free to inherit. The brand on this screen is the cream/paper palette, Frank Ruhl Libre and the gold ornament — all of which cost nothing. |
| **Any wait-time text, «הבאה בתור», or a "now serving" banner** | D10(1) and pre-decided #28. Until F58 ships, position 1 is *the first person who arrived today*, not the next person to be seen, so «הבאה בתור» would be a lie for most of the day. |
| **An idle stop** | D11. F34's board is an unattended *staff* tablet where inactivity means nobody is there. This board is **designed** to be read by people who are not touching it: inactivity is the use case, the content is public by ruling so there is no exposure to close, and a ten-minute timer would freeze a wall screen with nobody in the room to press resume. |
| **A row that navigates, a QR on the board, a per-boutique theme, a portrait layout** | Out of scope, spec. The board takes no input and the route carries no parameter. |
| **A privacy notice on the board itself** | D13. It collects nothing from the people reading it, and it would spend rows on reassurance theatre. The notice belongs at the point of collection, which is `/checkin` — and this PR amends it (`copy.md` §5). |

---

## 1. The board at 1920×1080 — the primary case, and it is not a phone

**1920×1080 is the design target, and 375 is what the same page does on a phone.** That inverts every other storefront deck in this project, deliberately: the viewport is a panel across a salon, there is no thumb, no hover, no scroll gesture and nobody standing at it. Two constraints replace the breakpoint sweep — **legible at three to five metres**, and **everything on one screenful, because nobody in the room can scroll it.**

⚠ **The diagram below is drawn in LOGICAL order — inline-start first. The page is `dir="rtl"`, so inline-start is the RIGHT edge of the screen.**

```
+========================================================================+  1920 × 1080
|                                                                        |
|  ממתינות בתור                                        <h1>, 43.4px      |  ← heading band, ~68px
|  ▬▬▬▬▬▬▬▬                                            gold ornament     |
|                                                                        |
|  עודכן 14:07              [ השהיית העדכון ]           59.0px / 24.6px  |  ← freshness + pause, 71px
|                                                                        |     PAUSE IS THE FIRST CONTROL
|  ┌──────────────────────────────────────────────────────────────────┐  |     IN <main>, BEFORE THE ROWS
|  │  1    נועה                                                       │  |
|  │  2    מיכל                                                       │  |  ← 5 rows × 107px + 4 × 8px gap
|  │  3    אלכסנדרינה…                                                │  |     = 567px
|  │┃ 4    שיר                    גשי לדלפק                           │  |     ┃ = 8px gold-strong rule
|  │  5    נועה                                                       │  |         (the CALLED row — §2.2)
|  └──────────────────────────────────────────────────────────────────┘  |
|         ↑         ↑                     ↑                              |
|      75.6px    59.0px                59.0px                            |
|                                                                        |
|  ועוד 35 בתור                                         59.0px           |  ← overflow line, 71px
|                                                                        |
|  (VisuallyHidden role="status" × 2 — nothing painted)                   |
+------------------------------------------------------------------------+
|  על הבוטיק · הצהרת נגישות · @handle · 03-1234567                        |  ← StorefrontLayout footer
|  (+ 68px --space-a11y-footprint reserved for the fixed A11yMenu trigger) |     ~115px, NOT REMOVABLE
+========================================================================+
```

Rows **3** and **5** are the two cases the room will actually meet and the two a build will get wrong: `אלכסנדרינה…` is D5's server-side truncation (11 characters + «…», so the tail never reaches the wire), and the second `נועה` is **one woman holding two tickets** under F33's Ruling 3 — an ordinary outcome of the ordinary re-entry path, not an edge case (§2.3).

**Row 4 is drawn called and cannot occur.** F58 is the only writer of `called_at` and it is not built (spec D10). Everything about the highlight in §2.2 is designed, built and tested against a stub, and **no e2e journey may attempt it** — there is no product path.

### 1.1 The type scale — recomputed, and the spec's table is wrong in four cells (**F-1**)

The shape is `clamp(<rem floor>, <rem> + <vh>, <rem cap>)`. The `vh` half tracks the panel; **the `rem` half is what makes the A11yMenu's text-size control (`theme.css:170-172`, `:root[data-a11y-text-size] { font-size: 1.2rem }`) do anything at all**, which is SC 1.4.4 — AA, legally required here, and invisible to axe exactly like 2.2.2.

Constants: 1vh = **10.8px** at 1080, **21.6px** at 2160, **7.68px** at 768. Roots: **16px** default, **19.2px** boosted, **32px** at `resizeTextTo200Percent` (`storefront.spec.ts:1385-1390`).

| Element | Class | 1080p default | 1080p, A11y boost | 1080p, 200% text-only | **4K @ DPR 1** | 1366×768 |
|---|---|---|---|---|---|---|
| Position number | `text-[clamp(2.5rem,2.5rem+3.3vh,9rem)]` | **75.6** | 83.6 | 115.6 | **111.3** | 65.3 |
| First name | `text-[clamp(2rem,2rem+2.5vh,7rem)]` | **59.0** | 65.4 | 91.0 | **86.0** | 51.2 |
| Heading | `text-[clamp(1.5rem,1.5rem+1.8vh,4rem)]` | **43.4** | 48.2 | 67.4 | **62.9** | 37.8 |
| **Freshness line** | the **name** scale | **59.0** | 65.4 | 91.0 | **86.0** | 51.2 |
| **Overflow line** | the **name** scale | **59.0** | 65.4 | 91.0 | **86.0** | 51.2 |
| **Empty-state title** | the **position** scale | **75.6** | 83.6 | 115.6 | **111.3** | 65.3 |
| **Empty-state hint / error line** | the **name** scale | **59.0** | 65.4 | 91.0 | **86.0** | 51.2 |
| Pause control label | `text-[clamp(1rem,1rem+0.8vh,2rem)]` | **24.6** | 27.8 | 40.6 | **32.0** (capped) | 22.1 |

**What the spec got wrong, cell by cell** — the 1080p default column is right to a tenth and it is the one the height budget and every legibility number run off, so nothing downstream of it moves:

| Cell | Spec D8 | Correct | What happened |
|---|---|---|---|
| Position, boost | 86.9 | **83.6** | 2.5rem at a 19.2px root is 48, not 51.3 |
| Position, 200% | 111.6 | **115.6** | 80 + 35.64 |
| Position, 4K | 144 *(capped)* | **111.3** *(not capped)* | 40 + 71.28 is 33px under the 9rem cap |
| Name, 200% | 86.0 | **91.0** | 86.0 is the 4K value — the two columns were transposed |
| Name, 4K | 112 *(capped)* | **86.0** *(not capped)* | same transposition |
| Heading, 200% | 62.9 | **67.4** | 62.9 is the 4K value |
| Heading, 4K | 64 *(capped)* | **62.9** *(not capped)* | same |
| Pause, boost | 28.4 | **27.8** | 19.2 + 8.64 |

The pattern is a transposition: the spec's "4K @1×" column carries the caps (which never bind — see below) and its "200% text-only" column carries the 4K values. **The correction is not cosmetic**: it is what exposes **F-2**, because a "capped at 112px" name is a comfortable name and an 86.0px name at 4K is not.

**⚠ The `clamp()` floors never bind, and the spec's "the `clamp` floors are the phone sizes" is false (F-14).** `clamp(a, a + x, b)` with `x ≥ 0` is `min(a + x, b)` — the floor is unreachable at any viewport height above zero. A 375×812 phone therefore renders a **66.8px** position number and a **52.3px** name, not 40 and 32. That is not a defect (the page *is* a wall board, and it scrolls on a phone), but it is the reason `/queue` joining `RESIZE_ROUTES` is load-bearing rather than a formality: at 375 with a 32px root the row is a 106.8px number beside an 84.3px name in a 311px content box, which only survives because of `min-w-0` + `[overflow-wrap:anywhere]` (§5). **The `clamp()` form is kept anyway** — A34 pins the class strings, and a floor that would bind if the coefficients are ever retuned is free insurance.

### 1.2 Legibility in millimetres, and the 4K case fails the brief (**F-2**)

A 55" 16:9 panel is 1217.7mm wide. Cap height ≈ 0.70 × font-size. Comfortable reading ≈ cap × 150.

| Viewport | mm / CSS px | Position | First name | Freshness / overflow | Pause label |
|---|---|---|---|---|---|
| **1920×1080** (or 4K at DPR 2) | 0.634 | 75.6px → 33.6mm → **5.0m** | 59.0px → 26.2mm → **3.9m** | 26.2mm → **3.9m** | 24.6px → 10.9mm → 1.6m |
| **3840×2160 at DPR 1** | 0.317 | 111.3px → 24.7mm → **3.7m** | 86.0px → **19.1mm → 2.9m** ✗ | 19.1mm → **2.9m** ✗ | 32.0px → 7.1mm → 1.1m |
| 1366×768 (32" panel, 0.595) | 0.595 | 65.3px → 27.2mm → 4.1m | 51.2px → 21.3mm → 3.2m | 3.2m | 22.1px → 9.2mm → 1.4m |

**At 4K reporting a 3840×2160 CSS viewport the first name reads to 2.9m against a stated 3–5m audience, and so does the freshness line that D11(c)'s whole 2.2.2 resolution rests on.** The mechanism is precise and worth stating, because the instinct is to blame the caps and the caps are innocent: on the same physical panel, doubling the pixel count halves mm/px and doubles the `vh` term's pixel value, so **the `vh` half of every size is physically constant** (22.6mm either way) — and the `rem` half, which is a fixed count of CSS pixels, is physically **halved**. The name's 2rem floor is 20.3mm of glyph at 1080p and 10.1mm at 4K@DPR1, and that is the entire 27% loss.

**Ruled: this is a kiosk configuration line, not code.** Two lines on the D10(4) checklist, beside "the TV waits for F58" and "one full-screen tab, screen-blanking disabled":

3. **On a 4K panel, the browser must present a 1920×1080 CSS viewport** — either because it reports `devicePixelRatio: 2` (which most TV and set-top browsers do) or because page zoom is set to **200%**. Zoom is exact, not approximate: at 200% one CSS px is two device px, mm/px returns to 0.634, and every cell of the 1080p column is reproduced identically.
4. **The panel must present a viewport at least 1080 CSS px tall** — see **F-3**.

**Declined: raising the `rem` floors so 4K@DPR1 self-corrects.** It would make every size larger at 1080p too, where the budget already fits exactly five rows (§1.3) — buying the mis-configured case at the cost of the configured one. **Declined: a `@media (min-height: 1600px)` branch.** It is a second scale to keep true, tested by nothing in CI (no runner has a 2160px viewport), for a case one browser setting closes. **Declined: `vmin`/`vmax` or a container query.** Same objection, more machinery.

### 1.3 The height budget at 1920×1080 — this is where `BOARD_ROW_LIMIT = 5` comes from

Spacing utilities (`pt-6`, `gap-6`, `py-2`) are px literals from `theme.css` and do **not** grow under the root-font-size boost; only font-derived boxes do.

| Band | px | Derivation |
|---|---|---|
| `StorefrontLayout` `<footer>` | **115** | 1 (`border-t`) + 24 (`pt-6`) + 22 (one `text-sm` link line, 14 × 1.5) + **68** (`--space-a11y-footprint`, `theme.css:93`). **Not removable**: the shell mounts above the Router (`App.tsx`) and the הצהרת נגישות link is statutory. |
| Page block padding (`pt-6 pb-6`) | **48** | The page's own block-end padding is free — the footer already pays `--space-a11y-footprint` for the fixed A11yMenu trigger, and `StorefrontLayout.tsx:134-145` says the reservation "belongs HERE and not on a page div". A second reservation would double-count it. |
| Heading + ornament + `gap-3` | **68** | 43.4 × 1.2 = 52, + 12 gap, + 4 (`h-1` ornament) |
| `gap-6` | **24** | |
| Freshness line + pause control | **71** | `max(59.0 × 1.2 = 71, pause button ≈ 53)`. The 44px control fits *inside* the freshness line's box. |
| `gap-6` | **24** | |
| `gap-6` + overflow line | **95** | 24 + 59.0 × 1.2 = 71. Rendered only when `waiting_total > entries.length`, but the budget must assume it. |
| **Chrome total** | **445** | |
| **Available for rows** | **635** | 1080 − 445 |
| One row | **107** | 75.6 × 1.2 = 90.7 (**the POSITION NUMBER governs the line box, not the name**) + `py-2` 16 |
| **5 rows** | **567** | 5 × 107 + 4 × 8 (`gap-2`) — fits with **68px** to spare |
| 6 rows | **682** | ✗ over by 47px |

**Five fits with 60% of a row to spare; six does not fit at all.** The spec's conclusion is confirmed by a budget that differs from it in every band (its footer figure is ~55px conservative and its heading/overflow bands are a few px light), which is the useful kind of agreement.

**⚠ F-13 — under the A11yMenu text-size boost the slack goes to exactly zero.** Recomputing at a 19.2px root: chrome 468, band 612, five rows 5 × 116 + 32 = **612**. The fifth row's last pixel sits on the fold. That is tolerable and it is worth saying why rather than leaving a reader to find it: **the boost needs a pointer, and the wall has none** — the A11yMenu trigger is a fixed button nobody in the room can reach — and the population that *does* press it is on a phone, where the page scrolls. **There is no unscrollable victim of the zero-slack case.** It is still the reason A30's `toBeInViewport()` on `row.nth(4)` is not ceremonial, and the reason `scrollHeight <= innerHeight` alone would not have caught the six-row version.

---

## 2. The row

### 2.1 Anatomy

| Slot | Content | Type | Bidi | Notes |
|---|---|---|---|---|
| Leading | `position` | 75.6px, `text-ink` | `<bdi dir="ltr">` | `w-[2ch] shrink-0 text-center tabular-nums` so a two-digit number does not shift the name column. **This is the taller glyph and it governs the row's line box** (§1.3). |
| Name | `first_name` | 59.0px, `text-ink` | **bare `<bdi>`** | `min-w-0 [overflow-wrap:anywhere]`. `dir="ltr"` on Hebrew is itself a bidi defect — the shipped rule (`QueuePositionPage.tsx:332` takes `dir="ltr"` for the *numeral* half only). |
| Trailing | `queueBoard.called`, only when `called === true` | 59.0px, `text-warning-text` | — | §2.2. Absent entirely otherwise — a per-row empty slot would be five lines of nothing. |

The row is `<li className="flex flex-wrap items-baseline gap-6 py-2 …">`. **`items-baseline`, not `items-center`**: a 75.6px number and a 59.0px name centred against each other float apart; sitting them on one baseline is what makes a column of five read as a list rather than as five separate cards. **`flex-wrap`** is for the phone only (§5) and never fires on a panel.

**The row is not a control and contains none.** Nothing on this page is clickable except the pause button and, in the error arm, the retry. There is no navigation, no detail, no tap target in a row, and no `role`, `title`, `aria-label` or `data-*` attribute on a row may carry text the room cannot see — the e2e journey asserts the rendered row text **equals** the fixture's `first_name` exactly, which is an assertion about what the *client* could get wrong and can therefore fail.

**The React key is `position`**, never the name and never an index-with-meaning. D7 argues it is correct rather than tolerated: rows are positional, hold no input state and no focus, so a re-render swaps text inside a stable row. A name key would **collide** — on two different women with the same first name *and* on one woman holding two tickets (§2.3).

### 2.2 The called row — three signals, none of them colour, and it cannot happen yet

WCAG 1.4.1 forbids colour as the sole carrier, and at four metres on a cheap panel the rule is not academic: a tint is the first thing a compressed backlight loses.

| Signal | Value | Contrast | Why |
|---|---|---|---|
| **A word** | `queueBoard.called` → «גשי לדלפק» | `--color-warning-text` on `--color-surface` = **5.20:1** | The one that actually carries the state. Present in the accessible name for free, because it is real text in the row. |
| **A rule** | `border-s-8 border-gold-strong` at the row's inline-start | **3.80:1** on cream — a **non-text** UI boundary, inside the gold law | 8px, not a hairline: at 0.634 mm/px a 1px rule is 0.63mm and is invisible from a seat. Gold-strong carries no text and no meaning alone here, so `tokens.md`'s bar is met exactly. |
| **A field** | `bg-surface` (#F6F0E6) behind the row | ~1.06:1 against `--color-bg` | **This is not a signal at four metres and is not asked to be one.** It is a near-invisible paper tint that reads as intent at one metre and as nothing at four. Stated so nobody "fixes" the design by making it darker: a strong fill would need a new token, and `theme.css:20-34` ships no called/warning background. |

**The number and the name of a called row stay `text-ink`** (13.89:1 on paper), never `text-warning-text`. The biggest glyphs on the screen are the ones a woman is scanning for; dropping them from 15.24:1 to 5.20:1 to signal a state that three other things already carry is the wrong trade at four metres.

**A called row is highlighted in place and NEVER reordered.** The number on the wall must equal the number on her phone (D3), and a row that jumps to the top is motion (D8/D11). F58 may call out of order; position 5 lit while 1–4 sit dark is a correct render of a correct fact.

**⚠ None of this can occur on the day F59 ships.** `called_at` has no writer until F58 (`app/models/constants.py:101-104`; `LOOP-STATE.md:501-502`), so `called` is `false` on every entry, always. The highlight is built and tested against a **stub** — the frontend test seeds `called: true` through the stubbed API client and the db test seeds `called_at` directly in a fixture — which is F33's own D10 precedent verbatim. **No e2e journey may attempt it.**

### 2.3 Two rows, one woman — designed, not pretended away (F33 Ruling 3)

Ruling 3 deleted server-side dedup outright, for two reasons the deleted version got wrong: with dedup, submitting a phone that was in the queue returned a **free, silent, unbounded oracle** for whether a named woman was standing in a named bridal boutique; and because F33 ships no writer for any status transition, **one anonymous POST with a known mobile denied that woman a queue slot for the rest of the boutique day.** `app/models/queue_ticket.py:23-26` states the consequence on the shipped table: *"a second ticket for the same phone on the same day is a real, expected outcome, and F58 merges or removes it."*

So the wall can show:

```
  3    נועה
  5    נועה
```

and this is the **ordinary outcome of the ordinary re-entry path** — F33's D8 records that a QR re-scan opens a fresh browsing context with an empty `sessionStorage` pointer.

**The design does exactly nothing about it, and that is the ruling rather than a shrug.**

- **The board must not deduplicate.** The only key that would identify her is `phone`, and `QueueTicketsRepository`'s class docstring (`app/db/repositories/queue_tickets.py:15-18`) promises no read is keyed on it and calls that absence *"the security property, not an omission"*. Deduplicating on the public board would be the one read that breaks it, on the one endpoint where breaking it is worst.
- **The board never claims a row is a person.** A row is a *place in the queue*. That is why the overflow line counts places and not women (**F-6**, `copy.md` §2), and why the heading is a noun phrase rather than a count.
- **The room cannot tell two Noas from one Noa twice, and the position number cannot disambiguate a woman from herself.** Accepted. F58 owns the merge, exactly as the model comment says.
- **No initial, no suffix, no marker.** Any disambiguator discloses strictly more on the one surface where less is the whole design.

A frontend test asserts two entries with an identical `first_name` both render, at their two positions — which is also the test that fails if anyone keys the list by name.

### 2.4 The pause control — the SC 2.2.2 mechanism, and its *smallness* is the design

**One `<Button variant="ghost" size="md">` whose accessible NAME flips** between `checkin.pause` («השהיית העדכון») and `checkin.resume` («חידוש העדכון»), copied from `QueuePositionPage.tsx:309-315`.

| Property | Value | Verified |
|---|---|---|
| Element | one button, two names. **No `aria-pressed`**, **no `aria-label` variant** | An `aria-label` would override the visible text and break the rule that the name *is* the label; `aria-pressed` beside a changing name is two contradictory facts. |
| Target | `size="md"` → `min-h-11` = **44px**, `px-4` | `Button.tsx:37` — `sm` is `min-h-9` = 36px and under the floor. Asserted as a **class**, never a measurement: jsdom has no layout engine (`vitest.config.ts:9`). |
| Variant | `ghost` = `bg-transparent text-ink` (`Button.tsx:31`) → **15.24:1** on cream | The shipped demoted treatment. No border, no fill. |
| Focus ring | `focusRing` applied unconditionally at `Button.tsx:62` — 2px `--color-focus` (5.57:1), 2px offset | Nothing on this page sets `outline: none`. |
| Label size | **24.6px at 1080p**, the smallest text on the screen | See below — this is a decision, not a leftover. |
| Position | **first control in `<main>`, before the rows in the DOM** | A 2.2.2 mechanism placed after the content it governs is reachable only by walking content that repaints under the walk. |
| Pause | `runningRef.current = false`, clear the tick, set `paused`, write `checkin.pausedCue` into the cue region | |
| Resume | running true, **reset the backoff to 5s**, bump the generation, fetch **immediately**, write `checkin.resumedCue` | A control that inherited a 60-second gap would look like a control that did not work. |
| Focus after press | **does not move.** The control renames; it does not unmount | Moving focus would be the defect. |
| Present in | live, **empty** and **error** states | §4. The copied `live &&` gate at `QueuePositionPage.tsx:295` does **not** come across — F59's loop has no terminal, so in the error state a request is still going out every 5–60s and will replace the retry arm under the user's thumb, which is 2.2.2's subject exactly. |

**⚠ F-4 — the label's class cannot be passed to `Button`.** `sizes.md` bakes `text-base` into the component (`Button.tsx:37`) and `cn()` is a plain join with no tailwind-merge (`lib/styles.ts:4-6`) — so a `className="text-[clamp(1rem,1rem+0.8vh,2rem)]"` on the `Button` ships **both** utilities and the winner is Tailwind's stylesheet order, not the class attribute. This is F15's F-6 trap, in the one place a build will walk into it. **The fix is one element and no design-system change**: put the clamp on a `<span>` inside the Button's children, where it is a descendant rather than a competitor.

```tsx
<Button variant="ghost" size="md" onClick={paused ? resume : pause}>
  <span className="text-[clamp(1rem,1rem+0.8vh,2rem)]">{t(paused ? "checkin.resume" : "checkin.pause")}</span>
</Button>
```

**Why the pause label is deliberately the smallest text on a screen designed to be read from four metres.** This is where the spec's D11 tension resolves into a pixel decision, so it is stated as one:

- **It is not for the room, and it must not look like it is.** A control the room can read at four metres is a control the room will eventually try to press — and a wall board frozen by a passer-by reads as *live* to the next woman who sits down. D11(c) calls that "actively harmful" and it is right. **Making the pause room-legible would make the screen less honest, not more accessible.**
- **The users it is for are all within arm's reach of a pointer.** The staffer configuring the kiosk, at the panel. Any woman in the salon who opens the same public URL **on her own phone** — an entirely ordinary thing to do with a URL that is public by ruling, and the population whose existence makes this page's 2.2.2 conformance genuine rather than formal. And any keyboard user anywhere: one Tab from the skip link.
- **10.9mm of cap height is legible to ~1.6m**, which is the distance at which somebody is *operating* rather than *watching*. The size is the mechanism by which the design keeps the audience out of the control.

**A34 must not "fix" this.** The freshness and overflow lines are pinned at the *name* scale precisely so the pause label can be pinned at the *small* one without the two being confused for the same oversight.

**Declined: leaning on 2.2.2's "essential activity" exception.** The control is cheaper than the argument, F34 set the precedent of not leaning on exceptions, and an exception asserted in a spec is not a defence anyone can check. **Declined: a frequency picker** (a settings surface and a persisted preference for a criterion one button closes). **Declined: `document.hidden` as the mechanism** — it is automatic, and automatic is not "a mechanism for the user"; it is what makes this gap easy to miss. **Declined: the kiosk browser's own controls** — 2.2.2 asks for a mechanism *in the content*.

---

## 3. The poll, made visible

### 3.1 What the room sees on a tick

| Tick outcome | What changes on the wall | What is announced |
|---|---|---|
| **Nothing changed** (the overwhelmingly common case) | **the «עודכן 14:07» time, and literally nothing else.** React commits only changed text nodes, so a board whose data is unchanged produces no visual change at all | nothing |
| A woman checked in at the door | a row appears at the end, or nothing visible if she lands past position 5 and only the overflow count moves | nothing |
| F58 called someone forward (**post-F58 only**) | that row gains its rule and its word, **in place** | nothing — §7.1 |
| The fetch failed | the freshness line switches to «העדכון האחרון היה 14:07»; **the rows stay** | nothing |
| The fetch answered 429 (`board_limiter` spent) | identical to the above. The client backs off 5s → 60s | nothing |
| The fetch answered 404 (`TENANT_NOT_FOUND`) | identical. **The loop does NOT stop** — §3.2 | nothing |
| The fetch succeeded after failures | the stale sentence clears and the interval resets to 5s | nothing |
| Midnight Jerusalem | the board empties, because the server computes `today_jerusalem` per request. **Zero client-side date logic** — no `todayJerusalem` import, no date-roll generation bump, no test for it | nothing |

**Nothing on this screen animates**, with exactly one bounded exception (§7.3). No highlight on a changed row, no fade on an arriving row, no pulse on the freshness line, no spinner between ticks. **An in-flight indicator is declined for F34's reason and one of this screen's own**: a spinner that appears every five seconds forever is the definition of visual noise, and on a screen mounted for months it is a flicker somebody has to sit next to.

### 3.2 The failure modes, and the one thing that must NOT be copied

Five mechanisms come across from `QueuePositionPage.tsx` **verbatim, with their comments**, because the comments name two defects that shipped in this repo:

1. **Schedule-after-settle, one arming site** (`:105-118`) — at most one request in flight per tab *by construction*.
2. **One monotonic `generationRef`, compared at three points** — success (`:129`), catch (`:151`) **and the `.finally()`** (`:177`). The third is the one that gets dropped, and without it a superseded load arms a second timer.
3. **`tickRef` updated on every render with no dependency array** (`:191-193`).
4. **`document.hidden` guarded twice** (`:111`, `:184`) with an immediate refetch on `visibilitychange` (`:217-237`).
5. **5s → 60s backoff, reset by the first success** (`:138`, `:171`).

**⚠ The two lines that leaked once, and on this screen they are worse than anywhere else:**

- **`runningRef.current = true` as the FIRST line of the mount effect** (`:196-201`). Without it, a setup → cleanup → setup cycle — which StrictMode performs on purpose — leaves the loop **permanently dead behind a pause button that still looks like it works**. On a phone that is a wrong number; **on a wall it is a TV showing a correct board frozen at the moment of mount, with nobody in the room to notice.** F57's review found this exact bug inherited from `BoardSection` (`LOOP-STATE.md:265-267`). It gets its own named test.
- **`runningRef.current = false` BEFORE `clearTick()` in the cleanup** (`:203-213`). `clearTick()` alone cancels only the timer armed right now; the arming site is a `.finally()` that runs *after* cleanup, and nothing in `tick → load → finally → schedule` touches React state. This has shipped as a defect **twice** (`LOOP-STATE.md:193-202`, `:265-267`).

**⚠ What must NOT be copied: the terminal branch.** `QueuePositionPage.tsx:139-143` and `:158-163` stop the loop on a closed status and on `isNotFound(error)`. Every one of those has no subject here:

- there is no ticket, so no `CLOSED_STATUSES` and no `status` field on the payload at all;
- there is no capability, so no `clearCheckinTicket()` — **F59 touches `sessionStorage` not at all** and imports nothing from `lib/checkinTicket.ts`;
- and **`isNotFound` must not stop this loop.** A 404 on `/storefront/queue` is `TENANT_NOT_FOUND` — a fact about the *server*, not about a dead link the user holds. F33's page stops because *her ticket is gone and no retry will bring it back*. **F59's page has nothing to lose and nobody at the keyboard: a wall screen that gives up permanently needs a human to notice and reload, and there is none.**

**So F59's loop has no terminal at all.** Every failure — 404, 429, 5xx, network — backs off to 60s and keeps trying at one request a minute until the server comes back and the board heals itself. That is a deliberate divergence from a file a builder will have open beside them, so it is pinned by a named test (`a 404 does not stop the loop`).

**One exception, and it is `document.hidden`.** `schedule()` returns without arming while the tab reports hidden, and the only path back is the `visibilitychange` listener. On a phone that is right and self-correcting. **On a permanently mounted kiosk it is the one state where the board freezes with no automatic recovery and, by the argument above, nobody in the room to notice.** Accepted as a ceiling — removing the guard would poll a genuinely hidden tab forever and reopen D6's budget arithmetic — and mitigated by configuration: **one full-screen tab, screen-blanking disabled**, on the D10(4) checklist.

---

## 4. States — the single source for this feature

The list may not shrink. Testids are `queue-board-*` and **never** `queueBoard.*`: once `queueBoard` is a section of `he.ts`, any quoted `"queueBoard.…"` literal anywhere under `apps/storefront/src` is scraped as an i18n key by `i18n-keys.test.ts:22` and fails the suite with a confusing "missing from he.ts".

| # | State | Trigger | What is on the wall | Announced / focus |
|---|---|---|---|---|
| **W-load** | First paint, before the first response | mount | Heading + ornament. A `VisuallyHidden role="status"` (`queue-board-loading-status`) carrying `queueBoard.loading`. **One** `Skeleton variant="block"` in a wrapper the height of the rows band (**F-10**). **No freshness line and no pause control** — nothing is updating yet, and a pause offered before the first response is a lie about the page. Under a second at boot | the loading region is `role="status"`, so loading **is** announced. It **unmounts** on the first settled response, and that unmount is a `childList` mutation A23 must name as expected |
| **W** | `entries.length ≥ 1` | 200 | §1's diagram. Heading; freshness + pause **before** the rows; 1–5 rows; the overflow line when `waiting_total > entries.length` | nothing announced, ever (§7.1) |
| **W-one** | `entries.length === 1` | 200 | One row. **No special case, no "you are the only one" copy**, same layout, same scale. A list of one is a list, and the 4 empty rows' worth of space is air rather than a problem to solve | — |
| **W-EMPTY** | `entries.length === 0`, a response has arrived | 200 `{"entries": [], "waiting_total": 0}` — **never a 404, never a 204** | **The state the screen is in for most of the day, and it is designed.** Heading; **the freshness line and the pause control exactly as in `W`**; `queueBoard.empty` centred in the rows band at the **position scale** (75.6px, reads beyond 5m); `queueBoard.emptyHint` under it at the **name scale** (59.0px, ~3.9m). **The freshness line is the load-bearing part**: without it an empty board is indistinguishable from a crashed board, and the first thing a staffer does to a blank TV is reboot it. With «עודכן 14:07» ticking, the screen visibly proves it is alive with nothing to show | nothing announced |
| **W-fail** | The **first** request failed and nothing ever loaded | 404 / 429 / 5xx / network | Heading; **the freshness line and the pause control** (§2.4 — the loop is still running, so 2.2.2 still applies and the shipped `live &&` gate is not copied); a `<p role="alert">` with `queueBoard.loadFailed` at the **name scale**, because the room must be able to tell a broken board from an empty one — otherwise a woman reads a failure as "nobody is waiting"; a `secondary` retry `Button` at the pause label's scale. **The loop keeps running underneath** (§3.2), so the wall heals itself; the retry button exists for the phone user, who is the only one who will ever press it | `role="alert"`, once. Repeated failures re-render the identical text child, so React's reconciler touches no DOM node and cannot re-announce (§7.1) |
| **W-stale** | Something loaded, then a tick failed | any later failure | **The last good board stays on screen, unchanged.** Only the freshness line switches, to `checkin.staleAt` → «העדכון האחרון היה 14:07». Blanking a correct board because one request failed throws away the only thing the room came to read. This is `loadedRef` at `QueuePositionPage.tsx:166-170` | not announced |
| **W-paused** | The user pressed pause | a press, from a phone or the kiosk's own pointer | Board unchanged and **not dimmed** — it was correct at 14:07 and pausing did not make it wrong. The freshness line becomes `checkin.pausedAt` → «העדכון מושהה. עודכן 14:07»; the control's name flips to «חידוש העדכון» | `checkin.pausedCue` announced **once** through the cue region. **Focus stays on the control** — it renamed, it did not unmount |
| **W-called** | Any entry `called === true` | **unreachable until F58** | §2.2. Built, tested against a stub, and reachable by no product path | nothing announced — **deliberately unlike `QueuePositionPage.tsx:144-149`** (§7.1) |
| **W-over** | `waiting_total > entries.length` | any of the above | One static line, `waiting_total − entries.length`, at the **name scale**. A modifier on `W`, not a state of its own — it composes with `W`, `W-stale` and `W-paused` and never with `W-empty` | — |

**Precedence in the freshness slot**: `W-paused` beats `W-stale` beats `W`. A stopped loop cannot fail a tick, so the stop is the cause in force — and the resume control is the remedy. `QueuePositionPage.tsx:270-275` derives exactly this and F59 copies it.

### The ugly edges, each decided

| Edge | Behaviour |
|---|---|
| **One person waiting** | `W-one`. No special case. |
| **40 tickets waiting** | Five rows plus «ועוד 35 בתור», computed as `waiting_total − entries.length`, **never echoed**. An off-by-one here is a wrong number on a wall, so the arithmetic gets its own test. |
| **`waiting_total − entries.length === 1`** | «ועוד 1 בתור». **Grammatical at every count** — which the spec's «ועוד 1 ממתינות» is not (**F-6**), and 6 waiting tickets is an ordinary Tuesday. |
| **A very long first name** | Truncated **server-side** to 11 characters + «…» (D5), so the tail never reaches the wire. `min-w-0` + `[overflow-wrap:anywhere]` on the row anyway, because at 200% text-only on a 375px phone even 12 characters overflow. |
| **A one-word name** | Shown in full. Exactly what she typed, not one character more. |
| **A name typed surname-first («כהן נועה»)** | «כהן» goes on the wall. **Accepted, unfixable ceiling** — the field is one free-text «שם מלא» and no heuristic can classify a token. It is why nothing in this deck or the spec claims "the surname never leaves the database", and why `copy.md` §5's notice clause says *the first word of the name you entered*. |
| **A first name that identifies her on its own** | Shown. **No derivation can fix this and none must pretend to.** The remedy is not technical: she is told, at the moment of collection, that the first word of her name goes on a public page. That is `copy.md` §5, and it is a build task in this PR. |
| **Two different women named נועה** | Both shown. The position number disambiguates. No initial, no suffix. |
| **⚠ One woman holding two tickets** | Both rows render, at two positions, with the same first name, and `waiting_total` counts both. §2.3 — an ordinary outcome, not an edge case. **The board does not and must not deduplicate.** |
| **A called entry at position 5** | Highlighted **in place**, never reordered (§2.2). |
| **Every entry `called: false`, forever, and the top five frozen** | The interim until F58. Nothing is highlighted, the board only grows, and because the order is arrival order and the cap is five, **the five names on the wall are the day's five earliest check-ins, unchanged from about 09:15 until midnight** — women who arrived at 09:00 and left at 10:00 are still on the screen at 17:00. **Which is exactly why D10(4) says the board is not deployable to a customer-facing wall in the interim at all.** The interim exists so the code is reviewed, tested and merged, not so a customer reads it. |
| **A stale `waiting` ticket from an earlier day** | Not on the board (scoped to today) while its own `/q/{id}` page still reports its own day's position. Honest in both places; the only legitimate disagreement between the two screens. |
| **A tie on `COALESCE(requeued_at, created_at)`** | The board's own order is stable across polls (`, id ASC`), so no name flickers between two positions every five seconds. The wall and one phone may disagree by one; accepted residual, F58 owns it. |
| **A remote flooder holding `board_limiter` spent** | `W-stale`, indefinitely: a correct board labelled «העדכון האחרון היה 14:07», in **room-legible type**. **Stale, never blank and never wrong** — that is the bound, and it is only true because the freshness line is at the name scale rather than at 24px. |

---

## 5. Viewports — a distance, not a breakpoint sweep

There is exactly **one** layout branch in the whole feature, and it is `flex-wrap` firing on a phone.

| Viewport | What is different | Why |
|---|---|---|
| **1920×1080** (primary) | Nothing — this is the design. Container `mx-auto w-full max-w-[1400px] px-4 pt-6 pb-6 md:px-8` | The `max-w-[…]` px literal follows the shipped container precedent (`QueuePositionPage.tsx:19`'s `max-w-[640px]`, `StorefrontLayout.tsx:147`'s `max-w-[1200px]`) and is not the raw-px defect `tokens.md` law 5 bans. 1400 leaves generous air around a row that measures ~700px of content. |
| **3840×2160** | Nothing in code. **Configuration**: browser zoom 200%, or a browser reporting DPR 2 — see **F-2** and D10(4) checklist line 3 | Unzoomed, the name reads to 2.9m against a 3–5m brief, and a 1400px column floats in a 3840px viewport. Zoomed, the 1080p column is reproduced to the pixel. |
| **1366×768** | Nothing in code. **Only three rows fit; rows 4 and 5 are below a fold nobody in the room can scroll** — see **F-3** | Chrome ≈ 411px leaves a 357px band against a 102px row. The remedy if a pilot ships a 768 panel is **one server constant** (`BOARD_ROW_LIMIT`), because D4 makes the client render whatever it receives and assert no count. |
| **375 (a phone)** | **The single branch**: the row's `flex-wrap` fires and the name drops under the number. `min-w-0` + `[overflow-wrap:anywhere]` on the name; the page scrolls | The same page, not a second design. At 375 with a 32px root (`resizeTextTo200Percent`) the row is a 106.8px number beside an 84.3px name in a 311px box — a 12-character Hebrew name at 84px is roughly 500px of content. These are the **same two fixes** the shipped suite already applied to the Gallery thumbnail strip and the footer's Instagram handle to keep `TEXT_RESIZE_BROKEN_AT_375` empty (`storefront.spec.ts:1373-1383`). |

**`/queue` joins two of the three e2e route lists and not the third**, decided one at a time because they are three different constants and an earlier spec draft conflated them:

| List | Line | Joins? | Why |
|---|---|---|---|
| `ROUTES` — 375 / 768 / 1440 horizontal-scroll sweep | `:713-720` | **YES** | The phone is the same page and F33's two public routes are both already in it. "This is not the responsive sweep" means *the brief is a viewing distance, not a set of breakpoints* — it never meant the page skips a horizontal-overflow check. |
| `RESIZE_ROUTES` — the three SC 1.4.4 sweeps | `:1363` | **YES**, and it is a **new** step | F33 joined neither. The whole point of putting a `rem` term in the preferred value is that the A11yMenu boost now has an effect worth sweeping. `TEXT_RESIZE_BROKEN_AT_375` (`:1383`) **stays empty** — the wrapping row is what keeps it empty. |
| `AXE_ROUTES` | `:681-693` | **NO** | It is a `[name, path, list, boutique?]` 4-tuple and **cannot pass `installApi`'s 4th (`booking`) or 5th (`tickets`) argument**, so a member would scan the empty state and nothing else. F59's axe coverage is a **bespoke journey** in the shape of `:2407-2425` — F33's own precedent for `/checkin` and `/q/`. |

**⚠ `gotoSettled`'s `/queue` arm waits on `queue-board-freshness`, never on `queue-board-row`.** The helper (`:524-558`) is one `if/else` chain on `path`, so `/queue` gets **exactly one** tell for **every** journey that visits it — and this feature requires an empty-board journey, which renders no row at all. Falling through to the final `else` is worse, not better: it waits on `page.getByText(BOUTIQUE.name)` (`:555`), and **`/queue` never renders the boutique name** (**F-5**), so the fallthrough hangs. The freshness line is present in every non-loading state, is written **only** on a settled response, and is therefore exactly the "the data landed" property the helper asks for.

---

## 6. Component notes — exact tokens

| Element | Notes |
|---|---|
| Page container | `<div data-testid="queue-board" className="mx-auto flex w-full max-w-[1400px] flex-col gap-6 px-4 pt-6 pb-6 md:px-8">` — `pb-6`, **not** `QueuePositionPage.tsx:19`'s `pb-16`: that value is the fixed A11yMenu trigger's footprint stated on the page, and `StorefrontLayout.tsx:146`'s footer already reserves `--space-a11y-footprint` for it. A second reservation double-counts 68px of a band with 68px of slack. |
| Heading | `<h1 className="font-display text-[clamp(1.5rem,1.5rem+1.8vh,4rem)] text-ink">` + `<span aria-hidden="true" className="h-1 w-32 bg-gold" />` — the shipped `Heading` shape from `QueuePositionPage.tsx:58-66`, with the ornament grown from `h-px w-12` to `h-1 w-32`. At 0.634 mm/px a 1px rule is 0.63mm and is not seen from a seat; the ornament exists to be seen. `--color-gold` at 2.38:1 is **decorative, `aria-hidden`, meaning-free** and exempt under the gold law. |
| Freshness line | `<span data-testid="queue-board-freshness" className="text-[clamp(2rem,2rem+2.5vh,7rem)] text-ink">` + `<bdi dir="ltr">{freshTime}</bdi>`. **`text-ink`, never `text-ink-muted`, and never the `text-warning-text` escalation the shipped page applies at `:305`** — see **F-7**. Paused and stale add **`font-semibold` only**. |
| Freshness + pause row | `<div className="flex flex-wrap items-center gap-6">` — `items-center` rather than `items-baseline`, because baseline-aligning a 44px button against a 59px line drops it out of the line's box. |
| Pause control | `<Button variant="ghost" size="md">` with the clamp on an inner `<span>` (**F-4**). No new variant, no `aria-pressed`, no `aria-label`, no icon. |
| List | `<ul className="flex flex-col gap-2">` — no `Card`, no `divide-y`. A `Card` is `bg-surface` + `p-6` + `shadow-sm`, which spends 48px of vertical budget on a frame nobody sees at four metres; a divider is a hairline at 0.63mm. **Whitespace is the separator on this screen.** |
| Row | `<li className="flex flex-wrap items-baseline gap-6 py-2">`, called rows adding `border-s-8 border-gold-strong bg-surface ps-4`. **`border-s-`/`ps-` and never `border-l-`/`pl-`** — `qa-greps.sh:40` bans physical inline direction utilities under `apps/storefront/src`, and a big-type board is exactly where a builder reaches for `text-left`. |
| Position | `<bdi dir="ltr" className="w-[2ch] shrink-0 text-center tabular-nums font-display text-[clamp(2.5rem,2.5rem+3.3vh,9rem)] text-ink">` |
| Name | `<bdi className="min-w-0 font-display text-[clamp(2rem,2rem+2.5vh,7rem)] text-ink [overflow-wrap:anywhere]">` — **bare `<bdi>`**, no `dir`. |
| Called word | `<span className="text-[clamp(2rem,2rem+2.5vh,7rem)] text-warning-text">` |
| Overflow line | `<p data-testid="queue-board-overflow" className="text-[clamp(2rem,2rem+2.5vh,7rem)] text-ink">` |
| Empty title / hint | `<p data-testid="queue-board-empty" className="text-center font-display text-[clamp(2.5rem,2.5rem+3.3vh,9rem)] text-ink">` and a `text-center …text-[clamp(2rem,…)] text-ink` hint. `text-center` is not a banned physical-direction utility (`qa-greps.sh:40` bans `text-left`/`text-right`). **Not `EmptyState`** — its title is `text-xl` (23px → 10.2mm cap → 1.5m) and its body `text-base`, which is a caption on a wall. |
| Loading | **one** `<div className="min-h-[567px]"><Skeleton variant="block" /></div>` — **F-10**. `Skeleton variant="text"` renders `h-4` bars (16px) on a screen whose rows are 107px, and five of them pulsing is five times the page's entire motion budget. `aria-hidden` by construction, so the announcement is the `role="status"` region's job. |
| Error | `<p role="alert" className="text-[clamp(2rem,2rem+2.5vh,7rem)] text-ink">` + `<Button variant="secondary" size="md">` with the label clamp on an inner span (**F-4** again). |
| Live regions | two `<VisuallyHidden><span role="status" data-testid="queue-board-loading-status|queue-board-cue" /></VisuallyHidden>` — the `QueuePositionPage.tsx:283-285` and `:375-379` shapes. |
| Time formatter | a module-level, **multi-line** `Intl.DateTimeFormat("en-GB", { timeZone: JERusalem, … })` — `QueuePositionPage.tsx:41-46` copied. `qa-greps.sh` flags a single-line formatter without a zone, and a zoneless formatter reads the **device** clock: on a TV nobody has ever set the clock on. |

**Contrast, from the tokens ledger — ratios, not token names, because this surface is a glossy panel under salon lighting at four metres and WCAG's 3:1 large-text floor is a near-viewing figure:**

| Pair | Ratio | Where |
|---|---|---|
| `--color-ink` on `--color-bg` | **15.24:1** | position, name, heading, freshness, overflow, empty copy, error copy — **every text element on the page** |
| `--color-ink` on `--color-surface` | **13.89:1** | a called row's number and name |
| `--color-warning-text` on `--color-surface` | **5.20:1** | the called word, and nothing else |
| `--color-gold-strong` on `--color-bg` | **3.80:1** | the called row's 8px inline-start rule — **non-text**, ≥3:1 ✓ |
| `--color-gold` on `--color-bg` | 2.38:1 | the heading ornament — decorative, `aria-hidden`, meaning-free, exempt |
| `--color-focus` on `--color-bg` | **5.57:1** | the focus ring, `Button.tsx:62` |

**`--color-ink-muted` (6.15:1) is declined on this surface entirely** — by decision, not by omission. It passes axe comfortably and is a poor choice for panel-at-distance, most of all on the freshness line the honesty argument depends on. **This feature introduces no new colour pair, so the ledger needs no addition at this gate.**

---

## 7. The a11y contract — IS 5568 / WCAG 2.0 AA is a legal requirement (pre-decided #38)

**Two Level-A/AA criteria on this screen are invisible to axe, and both are discharged by named tests that may never be dropped as redundant with the axe row.**

### 7.1 Live regions — two `role="status"`, and the board announces no content at all

| Region | Testid | Lifetime | What may write to it |
|---|---|---|---|
| **Loading** | `queue-board-loading-status` | mounted at first paint, **unmounted on the first settled response** | Nothing. It is one-shot. Its removal **is** a `childList` mutation, and a `MutationObserver` scoped to `[role="status"]` broadly observes it on the first tick. |
| **Cue** | `queue-board-cue` | persistent for the life of the page | `checkin.pausedCue` and `checkin.resumedCue`, and **nothing else**. |

**A23's assertion — "the poll never writes into `role='status'`" — is about the CUE region and must say so by testid.** Written against `[role="status"]` broadly it goes red on the first tick **against correct code**, gets "fixed" by loosening it, and lands in exactly the vacuous form Risk 4 exists to prevent.

**The board announces no content, ever — a deliberate divergence from `QueuePositionPage.tsx:144-149`.** That page announces the `waiting → called` edge because it is *her* ticket and the one thing she came for. This board is about **other people**: pushing «מיכל, גשי לדלפק» into a stranger's screen reader is both noise and a broadcast she did not agree to. There is no `called` announcement on this page and there must not be one.

**The freshness line is visible, in the reading order, never `aria-hidden`, and outside every announced region.** F34's F-1 ruling, now the spec's own. The "outside" assertion has a known vacuous form: **every live region in this repo is a bare `role="status"` with no `aria-live` attribute** (`QueuePositionPage.tsx:376`, `BoardSection.tsx:416-420`), and `closest()` matches attributes rather than implicit ARIA — so `closest('[aria-live]')` returns `null` **even from inside one**. The assertion is `closest('[role="status"],[role="alert"],[aria-live]')`, **with a negative control** proving the selector matches when the line *is* nested inside.

**The error arm's `role="alert"` cannot re-announce on a repeated failure.** `W-fail` re-renders the identical JSX text child, and React's reconciler leaves the `Text` node untouched — unlike F34's F-7, whose writer was a manual `textContent =` that string-replace-alls whether or not the value differs. **Because the loop has no terminal, this arm can be re-rendered every 60 seconds for hours**, so the frontend test drives several consecutive failures and asserts one announcement rather than one failure and none.

### 7.2 Focus, and content moving underneath it

- **Rows are keyed by `position`**, so a repaint mutates text nodes inside stable elements. There is no focus inside a row to lose — the rows contain no controls at all.
- **The page sets no `document.title` and moves no focus on mount.** `router.tsx:315-330` does title, `scrollTo` and `getElementById(MAIN_ID)?.focus()` in one parent effect, and React flushes a child's passive effects **before** its parent's — so anything the page writes is silently overwritten one tick later and the dead code reads as working. Asserted in the **sentinel** form: set `document.title` to a sentinel, render the page **in isolation** inside `<StorefrontLayout>`, assert it is unchanged. Rendering through `<Router />` to satisfy a "the title is whatever the Router set" wording produces an assertion that **cannot fail**.
- **Tab order**: skip link → `#content` → **the pause control** → the retry button when present → footer links (על הבוטיק, הצהרת נגישות, handle, phone) → the fixed `A11yMenu` trigger. **The pause control's position is a ruling, not DOM luck**: it is the first stop inside the board, so one Tab from the skip target stops the thing that is happening. A 2.2.2 mechanism after the content it governs is reachable only by walking content that repaints under the walk.
- **After a press, focus does not move.** The control renames; it does not unmount.
- **No `pointerdown` repaint hold** — F34 needed one because a remote check-in grew a row under a descending finger. This board has no tap target in a row and nothing a finger travels toward, so the mechanism has no subject.
- **The board never scrolls itself**, at any time, for any reason.

### 7.3 Motion — the inventory, complete

| Thing | When | Disposition |
|---|---|---|
| `Skeleton`'s `animate-skeleton` pulse | first paint only, under a second at boot | **The page's only animation.** `aria-hidden`, one element rather than five (**F-10**), never re-shown on a re-poll (a failed tick keeps the board — `W-stale`). Frozen by `prefers-reduced-motion` (`theme.css:165-173`) and by the A11yMenu's stop-motion toggle. |
| `Button`'s `transition duration-(--motion-fast)` | hover / press | Shipped `Button` behaviour. There is no hover on a wall; on a phone it is the same button as everywhere else. |
| Everything else | — | **None.** No transition, crossfade, flash, pulse, marquee, auto-scroll, carousel or highlight-on-change. A number that changes changes **in place**. This is enforced by construction — there is nothing to reduce — which discharges SC 2.3.1 and `prefers-reduced-motion` without a media query. |

### 7.4 The rest of the floor

**SC 2.2.2 Pause, Stop, Hide (Level A) — the criterion this screen is the most literal instance of in the product, and the one no tool will ever add for us.** §2.4 is the mechanism; the three-part resolution of the wall-screen tension is (a) the user WCAG addresses is reachable and it is not the room — it is the kiosk operator and every woman who opens the public URL on her own phone; (b) for the room, the protection is that the board **does not move** (§7.3); (c) a pause the room could reach would be **actively harmful**, so the honest protection against a frozen wall is the **freshness line**, on the wall, in Hebrew, at the name scale, saying «העדכון מושהה. עודכן 14:07». **Axe has no 2.2.2 rule**, so the failure mode is not "CI catches it late" — it is "**CI stays green and the product is non-conformant**". The named test is `the wall board carries a working pause control (SC 2.2.2)`.

**SC 1.4.4 Resize Text (AA) — the second criterion axe cannot see, and the reason every size has a `rem` term.** A `vh`-only preferred value makes `theme.css:170-172`'s text-size boost a **complete no-op** at 1080p, at 4K and on a phone, and browser zoom does not rescue it (page zoom shrinks the CSS-pixel viewport and enlarges the pixel, so `vh` text is net-constant by construction). The repo treats the boost as a real contract in three separate test files. Discharged by **class** assertions (A34) plus `/queue` joining `RESIZE_ROUTES`.

- **SC 1.4.1 Use of Colour**: the called row carries a **word**, plus an 8px rule, plus a field — three signals, one of which is colour (§2.2). The freshness states are **three distinguishable sentences**, never one sentence and a class (D12).
- **SC 1.4.3 Contrast**: every text element is 15.24:1 or 13.89:1 except the called word at 5.20:1; the one non-text boundary is 3.80:1. §6.
- **SC 1.4.10 Reflow**: `min-w-0` + `[overflow-wrap:anywhere]` on the name, and `/queue` in `ROUTES`' 375/768/1440 sweep.
- **≥44×44**: the pause and the retry are both `size="md"` → `min-h-11`, asserted as a **class** (`toHaveClass("min-h-11")`), never a measurement — jsdom has no layout engine and `BoardSection.test.tsx:509-515` is the precedent that spells the trap out.
- **Visible focus ring** on both controls — `focusRing` at `Button.tsx:62`. Nothing sets `outline: none`.
- **Bidi**: `<bdi dir="ltr">` on the position number and the freshness time; **bare `<bdi>`** on the first name. `dir="ltr"` on a Hebrew name is the worse defect because it looks deliberate.
- **Headings**: one `h1`, no `h2`, no `h3` — the board has no groups.
- **The `A11yMenu` and the הצהרת נגישות link ship on this route** like every storefront route; the footer's `--space-a11y-footprint` reservation is in the height budget (§1.3) rather than fought.
- **An axe pass** over the live, empty and error states, in `QueueBoardPage.test.tsx` and in a bespoke `storefront.spec.ts` journey — **and it is explicitly not sufficient** for either 2.2.2 or 1.4.4.

---

## 8. Decisions taken in this deck

The design gate is self-approved, so there are no open `P-` questions. Every call below is resolved; each is one line to overturn.

| | Decision |
|---|---|
| **W-1** | **1920×1080 is the primary case and 375 is the derivative.** Inverts every other storefront deck, deliberately. |
| **W-2** | **Five rows, `gap-2`, no `Card`, no dividers.** Whitespace is the separator; a Card frame costs 48px of a band with 68px of slack and is invisible at four metres. |
| **W-3** | **The row's line box is governed by the position number (75.6px), not the name (59.0px).** `items-baseline`. |
| **W-4** | **Called = word + 8px `gold-strong` inline-start rule + `bg-surface` field**, in that order of load-bearing. The number and name stay `text-ink`. No new token, no new variant. |
| **W-5** | **The pause label is the smallest text on the screen on purpose** (24.6px, ~1.6m). Room-legible would be actively harmful; the control's size is how the design keeps the audience out of it. **A34 must not promote it.** |
| **W-6** | **The freshness line is `text-ink` in every state**, with `font-semibold` as the only escalation. The shipped `text-warning-text` swap is not copied — **F-7**. |
| **W-7** | **The empty state is title-at-position-scale + hint-at-name-scale, centred, no `EmptyState` component, no illustration, no CTA button.** The hint is room-legible because its whole job is to tell a walk-in to scan the code. |
| **W-8** | **The error line is at the name scale**, because the room must be able to tell a broken board from an empty one. |
| **W-9** | **One `Skeleton variant="block"`, not five text bars** — **F-10**. |
| **W-10** | **No boutique name on the board** — **F-11**. |
| **W-11** | **The heading ornament grows from `h-px w-12` to `h-1 w-32`.** A 0.63mm rule is not an ornament at four metres. |
| **W-12** | **`max-w-[1400px]`**, following the shipped container-literal precedent. |
| **W-13** | **The overflow line counts places, not women** — `copy.md` §2, **F-6**. |
| **W-14** | **`checkin.retry` is reused rather than minting `queueBoard.retry`** — **F-8**. Eight new keys, not nine. |
| **W-15** | **Two kiosk-checklist lines are added to F33's existing Ruling-4 gate**, beyond the spec's two: a 1080-CSS-px minimum viewport height (**F-3**) and a 1920×1080 CSS viewport on 4K panels (**F-2**). |

---

## 9. ⚠ FINDINGS

**Three build-blocking (F-1, F-2, F-4), one copy defect that ships ungrammatical Hebrew (F-6), two spec corrections (F-1, F-5).** Every citation below was opened and read on `main` at PR #36's merge commit.

- **F-1 — BUILD-BLOCKING. The spec's D8 type-scale table is wrong in four cells, and the error is a column transposition.** The "4K @1×" column carries cap values that **never bind** and the "200% text-only" column carries the true 4K values. Recomputed in §1.1: position boost 83.6 (not 86.9), position 200% 115.6 (not 111.6), position 4K **111.3 and uncapped** (not 144), name 200% 91.0 (not 86.0), name 4K **86.0 and uncapped** (not 112), heading 200% 67.4 (not 62.9), heading 4K 62.9 (not 64), pause boost 27.8 (not 28.4). **The 1080p default column is right to a tenth**, so the height budget, the row cap and every legibility number downstream of it are unaffected — but the corrected 4K column is what exposes F-2, which the wrong one concealed. *Owner: this deck; §1.1 supersedes the spec's table.*

- **F-2 — BUILD-BLOCKING (configuration, not code). On a 4K panel presenting a 3840×2160 CSS viewport, the first name reads to ~2.9m against the brief's 3–5m floor, and so does the freshness line the whole 2.2.2 resolution rests on.** The mechanism is that `rem + vh` keeps the `vh` half **physically constant** across pixel densities on one panel and **halves** the `rem` half — the name's 2rem term is 20.3mm of glyph at 1080p and 10.1mm at 4K@DPR1. The caps are innocent; they never bind. **The fix is one kiosk-checklist line — a 1920×1080 CSS viewport, via a browser reporting DPR 2 (which most TV browsers do) or page zoom at 200%** — which reproduces the 1080p column exactly. Raising the `rem` floors, adding a `min-height` media branch and switching to `vmin` were all weighed and declined in §1.2: each buys the mis-configured case at the cost of the configured one, or ships a second scale that nothing in CI can test. *Owner: team, at build. Trigger: the first pilot install on a 4K panel.*

- **F-3 — At 1366×768 only three rows fit, and two of five sit below a fold nobody in the room can scroll.** Chrome ≈411px leaves a 357px band against a 102px row. A cheap 768p panel is a realistic pilot purchase and A30 only tests 1920×1080. **Ruled: a kiosk-checklist line stating a 1080-CSS-px minimum viewport height, not viewport-adaptive code.** D4 forbids the cap adapting to the viewport, and a viewport-height field on a request that currently carries **nothing** would be a new client-driven lever on an anonymous endpoint. If a pilot ships a 768 panel the remedy is **one server constant** — `BOARD_ROW_LIMIT = 3` — and no frontend change, because D4 makes the client render whatever it receives and assert no count. *Owner: team. Trigger: the pilot hardware order.*

- **F-4 — BUILD-BLOCKING. The pause control's font-size class cannot be passed to `Button`.** `sizes.md` bakes `text-base` into the component (`Button.tsx:37`) and `cn()` is a plain join with no tailwind-merge (`packages/ui/src/lib/styles.ts:4-6`), so a `className` carrying `text-[clamp(1rem,1rem+0.8vh,2rem)]` ships **both** utilities and the winner is Tailwind's stylesheet order rather than the class attribute — F15's F-6 trap, in the one place this build walks into it. Identically for the retry button. **Fix: the clamp goes on a `<span>` inside the Button's children** (§2.4), where it is a descendant rather than a competitor. One element, no design-system change, no new variant. *Owner: team, at build.*

- **F-5 — Spec correction. `StorefrontLayout` does not render the boutique name on any route, so the spec's Rejected-finding #2 rests on a false premise.** Verified: the layout fetches the boutique into context (`StorefrontLayout.tsx:85-99`) and renders only the footer's about / הצהרת נגישות / handle / phone. The name that `gotoSettled`'s final `else` waits on (`storefront.spec.ts:555`) is rendered by **`/accessibility`'s own page body**, as that arm's own comment says. So the original finding was right and the rejection's reasoning was wrong: falling through would **hang**, not resolve against a skeleton. **The conclusion is unchanged and now rests on a true premise** — `/queue` needs its own `gotoSettled` arm, keyed on `queue-board-freshness`. This also removes the one "free" argument for putting the boutique name on the board (**F-11**). *Owner: this deck; recorded so a reviewer does not re-derive it.*

- **F-6 — COPY DEFECT. «ועוד {{count}} ממתינות» is ungrammatical at an ordinary count, and it counts tickets while saying women.** Two independent problems: (1) `waiting_total − entries.length === 1` happens the moment a sixth ticket exists, and «ועוד 1 ממתינות» needs the singular «ממתינה» — the shipped house rule for exactly this is `apps/manage/src/i18n/he.ts:67-69`, *"Label-then-number, so it is grammatical at every count without four Hebrew plural forms"*; (2) under Ruling 3 the quantity is a count of **tickets**, so a woman who re-scanned is counted twice by a word that names women. **«ועוד {{count}} בתור»** fixes both — «בתור» does not inflect for number, and it counts places in a queue, which is exactly what `waiting_total` is. **This refines D10 on an axis D10 did not consider** (D10 ruled on arrivals-vs-waiters and resolved it with the deployment gate; Ruling 3's ticket-vs-woman axis survives F58's merge window). D10's ruling and its gate are untouched, «נרשמו היום» stays declined, and the change is one string in two files. *Owner: the user, revertible in one line; `copy.md` §2 carries the full argument.*

- **F-7 — The freshness line must not copy `QueuePositionPage.tsx:305`'s `font-semibold text-warning-text` escalation.** On a panel it drops the page's only honesty signal from **15.24:1 to 5.70:1** at the exact moment the signal matters most — an "escalation" that makes the more urgent state *harder* to read from a seat. The state is already carried by three distinguishable sentences (D12), which is what the rule against colour-alone asks for. **`font-semibold` stays; the colour swap does not come across.** The frontend test must assert the three states differ **as text** (`toHaveTextContent`), never as a class. *Owner: this deck.*

- **F-8 — `checkin.retry` is reused rather than minting `queueBoard.retry`.** Same word («ניסיון נוסף»), same act, and D12's own stated principle is that the vocabulary must not diverge between two screens in the same shop — the seven freshness/pause keys are reused on exactly that reasoning and `retry` is the same class. Eight new keys instead of nine, in two files. The spec's Frontend-changes table lists `retry` under `queueBoard`; **a builder following it literally ships a ninth key that duplicates a shipped value.** *Owner: this deck, revertible in one line.*

- **F-9 — The brief's `/נשלח|תישלח|בדרך/` ban does not govern this app, and no storefront guard replaces it.** It lives at `apps/manage/src/__tests__/i18n.test.ts:452` and walks the **manage** HE bundle. The storefront's `i18n-keys.test.ts` checks key resolution, Hebrew presence and `ar` non-emptiness, and carries **no register guard at all** — and `apps/storefront/src/i18n/he.ts:38` already ships «הקולקציה בדרך», which the manage guard would redden if it were ever ported. **F59's copy complies with the ban anyway** (`copy.md` §7) because it costs nothing and F59 sends nothing, but **no test enforces it and a later editor will not be stopped.** Recorded rather than fixed: adding a storefront register guard means auditing an existing violation, which is a separate change with its own argument. *Owner: team. Trigger: F45, or the first storefront string that promises a send.*

- **F-10 — `Skeleton variant="text"` is wrong on this screen twice over.** Its bars are `h-4` (16px) on a page whose rows are 107px, so the loading state does not resemble the state it is standing in for; and five pulsing bars is five times the page's entire motion budget on a screen mounted for months. **One `Skeleton variant="block"` inside a `min-h-[567px]` wrapper** — `variant="block"` is `h-full w-full`, so the wrapper sizes it without overriding a `packages/ui` utility (the F-4 trap avoided by construction). *Owner: this deck.*

- **F-11 — The boutique name is deliberately absent.** It would cost ~49px at the pause label's scale, against a rows band with 68px of slack and zero slack under the text-size boost (**F-13**); the room already knows which shop it is standing in; and after **F-5** there is nothing free to inherit — a name would mean a new `useBoutique()` read, a loading arm and a failure arm on a page that currently has one data source. The brand on this screen is the palette, the display face and the gold ornament. *Owner: this deck.*

- **F-12 — The D13 notice amendment forces one word of collateral edit to a counsel-gated string.** Inserting the queue-board clause after the retention sentence moves the nearest antecedent of «הם» in «הם לא ישמשו לפניות שיווקיות» from «הפרטים» to «מספר הטלפון שלך». **«הם» must become «הפרטים».** The meaning is identical and the alternative — appending the clause after the marketing sentence to preserve the pronoun — buries the one new processing this feature adds behind the consent text, in the one place Amendment 13 requires prominence. `CheckinPage.test.tsx:297-306` still passes either way (the `{{boutique}}` interpolation is untouched), which is exactly why **A32b must assert the clause against the resource bundle and never through `t()`**. *Owner: the user, via counsel; `copy.md` §5 carries the full before/after.*

- **F-13 — Under the A11yMenu text-size boost at 1080p the row band has exactly zero slack**: chrome 468, band 612, five rows 612. The fifth row's last pixel sits on the fold. **Tolerable, and the reason is worth stating**: the boost needs a pointer and the wall has none, while the population that presses it is on a phone where the page scrolls — **there is no unscrollable victim.** It is nonetheless why A30's `toBeInViewport()` on `row.nth(4)` is not ceremonial: `scrollHeight <= innerHeight` alone would not name the row that fell off. *Owner: team, at build.*

- **F-14 — The `clamp()` floors never bind, so the spec's "the `clamp` floors are the phone sizes" is false.** `clamp(a, a + x, b)` with `x ≥ 0` is `min(a + x, b)`. A 375×812 phone renders a **66.8px** number and a **52.3px** name, not 40 and 32. Not a defect — the page *is* a wall board and a phone can scroll — but it is why `/queue` joining `RESIZE_ROUTES` is load-bearing: at 375 with a 32px root the row is a 106.8px number beside an 84.3px name in a 311px box, and only `min-w-0` + `[overflow-wrap:anywhere]` keeps `TEXT_RESIZE_BROKEN_AT_375` empty. **The `clamp()` form is kept** — A34 pins the class strings, and a floor that would bind under retuned coefficients is free insurance. *Owner: this deck.*
