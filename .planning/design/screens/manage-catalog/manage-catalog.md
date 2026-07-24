# Screen: Catalog Management (F8 — manage console, tab «שמלות»)

**Date**: 2026-07-24 · **Status**: rev 4 — revised against the round-3 accessibility review; zero HIGH outstanding (see §13 Revision log)
**Constraint (read this before building anything)**: `packages/ui` today ships **placeholder tokens only**. The real token system and the RTL component library are **F9's build deliverable and have not happened yet**. F8 therefore ships **functional and deliberately plain**, using the existing `apps/manage/src/components/shared.tsx` primitives — exactly as F7 did. **This document specifies the target visual layer that the F9 build implements**, alongside `manage-restyle.md`'s four existing sections. Nothing here changes F8's component APIs, request/response shapes, error codes or behaviour: those are fixed by `.planning/specs/catalog-management.md` and are what F8's code implements *now*. Structure, copy, states, keyboard model and a11y obligations in this document are binding on F8's build; colour, type, spacing, radius and shadow are binding on F9's build.

**Binding sources**: `system/tokens.md` (all tokens; the three-golds law; the Price convention; the 9 usage laws) · `system/components.md` (reuse before invent) · `screens/design-system/manage-restyle.md` (the console language this extends) · `screens/design-system/storefront-catalog.md` + `storefront-dress-detail.md` (the customer-facing dialect this must match) · `specs/catalog-management.md` (data, constants, errors, copy).

> **Reading the wireframes.** ASCII is drawn in **logical order** — inline-**start** on the left of the page, inline-**end** on the right — matching `manage-restyle.md`. On screen everything is mirrored: inline-start is the **right** edge. The console is `dir="rtl"` and every rule below is written in logical properties (`padding-inline-*`, `margin-inline-*`, `border-inline-*`, `text-align: start/end`, `inset-inline-*`, `min-block-size`, `min-inline-size`, `max-inline-size`). **A physical directional *or sizing* property anywhere in catalog CSS is a review defect** — `min-height`, `max-width` and `min-width` resolve identically in a horizontal writing mode, but the prototype is what the F9 build copies, so the convention has to hold there verbatim. Media-query *features* (`@media (max-width:767px)`) are exempt: they are viewport queries, not properties.

---

## 0. Scope

Four surfaces, one console tab:

| # | Surface | Component (F8) |
|---|---|---|
| A | Catalog list | `CatalogSection.tsx` |
| B | Create + edit dress form | `DressEditor.tsx` |
| C | Variant (size/quantity) matrix | `VariantMatrix.tsx` |
| D | Image manager | `MediaGallery.tsx` |

**Navigation model (one model at every breakpoint)**: master–detail **by replacement**, not side-by-side. Opening a dress swaps the list out of the 720px content column and swaps the editor in; a back-link returns. There is no two-pane variant at 1440 — the console's max content width is 720px by `manage-restyle.md` law, and a 720px two-pane would give the editor ~340px, which no form survives. One layout, one focus-return rule, one set of states to test.

---

## 1. Console shell amendment — discharges F8 Risk 6

`manage-restyle.md` passed its gate against four sections. F8 adds a fifth. This section is the amendment it asks for; **fold it into `manage-restyle.md` in the same PR series**.

### 1.1 Five-tab shell

```
+---------------------------------------------------------------+
| בֶּלָה — ניהול  (display serif, --text-lg)          [יציאה]      |
+---------------------------------------------------------------+
| [פרופיל והגדרות] [שעות פעילות] [סוגי תורים] [מדיניות] [שמלות]  |  <- @≥768 tab row
+---------------------------------------------------------------+     @375 stacked accordion
|                                                               |
|   content column · max 720px · page gutters                   |
|   --space-4 @375 / --space-12 @≥1024                          |
|                                                               |
+---------------------------------------------------------------+
```

- **Tab order**: שמלות goes **last**. The first four are setup-shaped (configure once, revisit rarely); catalog is ongoing content. Putting ongoing work at the end of a setup sequence is wrong for frequency but right for the mental model, and the tab strip is one keystroke either way. Ruled: keep the setup order stable, append.
- **375 accordion re-check (Risk 6 asks for this explicitly)**: five stacked headers × 44px = 220px of chrome above an opened catalog list. That is acceptable and the passed accordion decision **stands unchanged**. Two conditions: (a) the שמלות panel header stays visible while the panel is open, so the exit is never scrolled off; (b) inside the open panel, opening a dress swaps list→editor *within* the panel — the accordion never closes as a side effect of a row click.
- **Tab overflow @768**: five Hebrew labels ≈ 420px of text + gaps at `--text-sm`/600 — fits 768 without scrolling. The strip keeps `overflow-x: auto` as insurance and never wraps to two rows (a wrapped tab row reads as two navigations).
- **Active tab**: `--color-gold-strong` 2px `border-block-end`, label `--color-ink`; inactive label `--color-ink-muted`. Unchanged from `manage-restyle.md`.
- **Semantics — ruled, and it is NOT the ARIA tab pattern.** The strip is a `<nav aria-label="מדורי הקונסולה">` of plain `<button>`s; the active one carries `aria-current="page"`. No `role="tablist"`, no `role="tab"`, no `role="tabpanel"`, no roving `tabindex`. Two reasons, both binding:
  1. `role="tab"` promises AT that the strip is **one** tab stop navigated with arrow keys. §8.1's keyboard model is **five sequential Tab stops**. Declaring the role and shipping sequential tabbing is a broken contract, and `role="tab"` without `aria-controls` → a `role="tabpanel"` also leaves the user never told which region the control governs (WCAG 4.1.2).
  2. At ≤767 these same buttons **are accordion headers**, and an accordion header must never be `role="tab"`. Roles cannot be swapped by a media query.
  `manage-restyle.md` assigned no ARIA here (it says only "tabs @desktop / stacked accordion @mobile"), so this ruling fills its gap rather than contradicting it. **At ≤767 the F9 build wraps each button in an `<h2>` and adds `aria-expanded` + `aria-controls` pointing at its panel** — that is the accordion contract, and it is the only place these controls gain state ARIA.
- **Heading outline (binding).** `h1` = the console title "בֶּלָה — ניהול" (a `<span>` gives the document no `h1` and the catalog list no heading target at all — a screen-reader user paging a 24-row list navigates by heading). `h2` = the open section ("שמלות") or, in the editor, the dress name. `h3` = Card headings. `h4` = empty-state headings **inside a Card that already has an `h3`**; where the Card has no `h3` the empty-state heading is itself the `h3`. No level is ever skipped.
- **Heading outline at ≤767 — ruled, because the accordion contract collides with it.** At ≤767 each nav button is wrapped in an `<h2>` (the accordion header), so the in-panel section heading would be a second `<h2>שמלות</h2>` immediately after the first, and in the editor a second `<h2>` at the same level as the section. Ruling: **at ≤767 the accordion header *is* the section `<h2>`; the in-panel `.page-h` heading is suppressed on the list screen, and the editor's dress-name heading renders as `<h3>` with Card headings at `<h4>` and Card-internal empty states at `<h5>`.** The outline is therefore `h1 console title → h2 accordion header → h3 dress name → h4 Card headings` at ≤767 and `h1 → h2 section / dress name → h3 Card headings` at ≥768 — no level skipped at either width. The build takes the level from one `headingLevel` value rather than hard-coding tags, so the two outlines cannot drift. **§8.1's focus destination follows this**: it is the editor's dress-name heading — `<h2 tabindex="-1">` at ≥768, `<h3 tabindex="-1">` at ≤767 — and it is unambiguous at both widths because the section heading is never rendered twice.
- **`SetupProgress`**: catalog **does not join it**. Decided in the F8 spec (Risk 6) — setup means the prerequisites for accepting bookings; catalog is content, and `storefront-catalog.md` already ships a dignified zero-dress storefront ("הקולקציה בדרך"). The checklist stays 4-item; denominators unchanged.
- **`PolicyBlockerBanner`**: renders above the catalog tab like every other section. Catalog work is not gated on it.

### 1.2 New rows for `manage-restyle.md`'s per-component table

| Component | Restyle |
|---|---|
| `CatalogSection` | toolbar Card (search + two filter toggles + primary "שמלה חדשה") over a list Card of dress **rows** — not a grid. The console is a working surface; the lookbook is the storefront. Row = 3:4 cover (`--color-surface` matting, `--radius-md`, `--shadow-sm`) + name in display serif `--text-lg`/500 + one muted meta line (Price · stock badge · photo count). `Badge` "הוזמן" on its **own line between the name and the meta line** — never nested inside the name's line-clamp box (§2.3) |
| `DressEditor` | single Card ≤720px, labels above fields, save `Button primary` inline-end + "נשמר לפני רגע" muted cue — `manage-restyle.md`'s form vocabulary verbatim. Adds: the price-visibility **preview line** and a bottom danger row (ארכיון / שחזור) behind a confirm `Modal` |
| `VariantMatrix` | second Card under the editor. EU quick-entry `chip` row (buttons, `--radius-full`, `--color-border-input` hairline) over stock rows; each row = size chip + quantity stepper + remove. Own save button ("שמירת מלאי") — the matrix is a separate write |
| `MediaGallery` | third Card. Header carries the cap counter inline-end. Visible file input + persistent guidance line, then an ordered thumbnail grid of 3:4 cream-matted boxes (the storefront's exact framing) with per-item ↑/↓ + primary + delete. **Storage-disabled** renders a calm `role="status"` notice, never a banner and never danger colour |

### 1.3 New console-wide states

| State | Seen |
|---|---|
| Upload in flight | queue rows under the file input + one polite `role="status"` line — "מעלה 3 מתוך 8" while running, **"הועלו N מתוך M · K נכשלו" on drain**, so failures are spoken and not merely drawn. Plus one `role="alert"` when part of the batch is rejected client-side (no request, no focus move). No byte-level percentage — `fetch` exposes no upload progress and F8 adds no XHR uploader (spec) |
| Media storage not configured | calm notice in the gallery Card only. **The rest of the console, the rest of the editor and the whole catalog stay fully usable.** Not a banner, not a blocker, not `--color-danger` |

---

## 2. Screen A — Catalog list

### 2.1 Desktop 1440 (content column 720px; 768 is identical)

```
+-------------------------------------------------------------------------+
| בֶּלָה — ניהול                                                  [יציאה]   |
+-------------------------------------------------------------------------+
| [פרופיל והגדרות] [שעות פעילות] [סוגי תורים] [מדיניות] [שמלות*]           |
+-------------------------------------------------------------------------+
|  שמלות                          (h2, display, --text-xl, tabindex=-1)   |
|                                                                         |
|  +-- Card (paper, --space-6, radius-md, shadow-sm) -------------------+  |
|  |  חיפוש שמלה                                                        |  |
|  |  [ ..................................... ]        [ שמלה חדשה ]     |  |
|  |  [x] הוזמנו בלבד     [ ] ארכיון                                    |  |
|  +--------------------------------------------------------------------+  |
|                                                                         |
|  מציג 1–24 מתוך 61                          (--text-sm, ink-muted)      |
|                                                                         |
|  +-- Card: list (ul) ------------------------------------------------+  |
|  | +------+  עלמה                                    (display, lg)   |  |
|  | | 3:4  |  8,900 ₪ · במלאי (7) · 5 תמונות          (sm, muted)     |  |
|  | +------+                                                          |  |
|  | ------------------------------------------------ hairline border  |  |
|  | +------+  שירה                                                    |  |
|  | | 3:4  |  (הוזמן)          <- chip line, SIBLING of the name       |  |
|  | +------+  12,400 ₪ · אזל מהמלאי · 3 תמונות                        |  |
|  | ------------------------------------------------                  |  |
|  | +------+  נועה                                                    |  |
|  | |monog.|  מחיר בתיאום · לא הוגדרו מידות · אין תמונות               |  |
|  | +------+                                                          |  |
|  | ------------------------------------------------                  |  |
|  | +------+  שמלת כלה נסיכותית עם מחוך מחורז בעבודת יד,               |  |
|  | | 3:4  |  שובל כנסייתי וטול משי איטלקי…      (clamped 2 lines)     |  |
|  | +------+  (הוזמן)          <- survives the clamp: it is OUTSIDE it |  |
|  |           15,800 ₪ · במלאי (2) · 12 תמונות                        |  |
|  +--------------------------------------------------------------------+  |
|                                                                         |
|  מציג 1–24 מתוך 61            [ הקודם ]  [ הבא ]      (inline-end)      |
+-------------------------------------------------------------------------+
```

### 2.2 Mobile 375

```
+-------------------------------+
| בֶּלָה — ניהול        [יציאה]  |
+-------------------------------+
| › פרופיל והגדרות              |   accordion headers, 44px each
| › שעות פעילות                 |
| › סוגי תורים                  |
| › מדיניות ביטולים             |
| ⌄ שמלות                       |   <- open panel; header stays put
+-------------------------------+
|  +-- Card ------------------+ |
|  | חיפוש שמלה               | |
|  | [ .................... ] | |
|  | [x] הוזמנו בלבד          | |
|  | [ ] ארכיון               | |
|  | [    שמלה חדשה         ] | |  <- full-width primary @375
|  +--------------------------+ |
|  מציג 1–24 מתוך 61            |
|  +-- Card: list ------------+ |
|  | +----+ עלמה             | |  cover 64×85
|  | |3:4 | 8,900 ₪          | |  meta wraps to 2 lines
|  | +----+ במלאי (7) ·      | |
|  | |    | 5 תמונות         | |
|  | -----------------------  | |
|  | +----+ שירה             | |
|  | |3:4 | (הוזמן)          | |  chip on its own line
|  | +----+ 12,400 ₪         | |
|  | |    | אזל מהמלאי · 3   | |
|  +--------------------------+ |
|  [ הקודם ]      [ הבא ]       |
+-------------------------------+
```

### 2.3 Component notes — exact tokens

| Element | Spec |
|---|---|
| Section heading | `<h2 tabindex="-1">שמלות</h2>`, `--font-display`, `--text-xl`, weight 500, `--color-ink`. First thing in the content column, above the toolbar Card. It is the tab's announced identity and the only heading target on the list screen (§1.1 heading outline) |
| Toolbar Card / list Card | `background: var(--color-surface)` · `border-radius: var(--radius-md)` · `box-shadow: var(--shadow-sm)` · `padding: var(--space-6)` (`--space-4` @375) · `max-inline-size: 720px` |
| Search input | `Input` primitive; **visible label** "חיפוש שמלה" (`--text-sm`/600, `margin-block-end: var(--space-1)`) — usage law 3. `dir="auto"` (Hebrew and Latin dress names both occur) · `maxlength=100` (`MAX_SEARCH_LENGTH`) · border `var(--color-border-input)`, bg `var(--color-surface-raised)`, `min-block-size: 44px`, `border-radius: var(--radius-sm)` |
| Filter toggles | native checkboxes with visible labels "הוזמנו בלבד" / "ארכיון"; label + box hit area ≥44×44 |
| "שמלה חדשה" | `Button primary` — `background: var(--color-gold)` + `color: var(--color-ink)` (**6.41:1** ✓, and the only legal way gold touches this button: gold as *background*, ink as text — usage law 1). `border-radius: var(--radius-md)`, `min-block-size: 44px`, `font-weight: 700` |
| Count line | `--text-sm`, `var(--color-ink-muted)` (5.61 on paper ✓). Numeric runs isolated: `מציג <bdi dir="ltr">1–24</bdi> מתוך <bdi dir="ltr">61</bdi>` |
| Row (`<li>` → one `<button>`) | **one affordance per row**: the entire row is the button that opens the editor. No second "עריכה" button — a row with two targets is two tab stops for one action. `padding-block: var(--space-4)`, `border-block-end: 1px solid var(--color-border)`, `:last-child` none. Hover: `background: var(--color-surface-raised)` (not a shadow lift — rows are not cards) |
| Cover box | `inline-size: 72px` (64 @375), `aspect-ratio: 3/4`, `background: var(--color-surface)` (the cream matting), `border-radius: var(--radius-md)`, `box-shadow: var(--shadow-sm)`, `overflow: hidden`. `<img loading="lazy" decoding="async" alt="">` `object-fit: cover` — `alt=""` because the dress name is the adjacent accessible text inside the same button (spec). **No hard border** — matting + shadow only (tokens.md) |
| No-photo cover | the storefront's monogram treatment, scaled: boutique initial in `--font-display` on `var(--color-surface)`, `--color-gold` hairline ring, `aria-hidden="true"`. Never a broken-image glyph |
| Dress name | `--font-display`, `--text-lg`, `font-weight: 500`, `color: var(--color-ink)` (**13.89:1** on paper ✓), `letter-spacing: 0` (tracking breaks Hebrew). Clamped to 2 lines; the full string is still the button's accessible name (the clamp is visual only — no `title` attribute, which is unreachable on touch). **The clamp box contains the name text and nothing else** |
| Status-chip line | **Sibling of the name, never a child of it.** `display:flex; gap: var(--space-2); flex-wrap: wrap; margin-block-start: var(--space-1)`; rendered only when ≥1 chip exists. This is a hard rule, not a layout preference: a chip nested inside a `-webkit-line-clamp` box is clipped out of the visible row on exactly the edge case §6 budgets for (200-char Hebrew name + `reserved`), while surviving in the button's accessible name — a sighted owner loses the status a screen-reader user still hears, which no SR-only review pass catches. Reserved is the one status the console shares with the storefront and the one the owner acts on |
| Meta line | `--text-sm`, `var(--color-ink-muted)` (5.61 ✓), items separated by ` · ` |
| Price | the `Price` component — **the only** way money renders (usage law 8). "8,900 ₪", numeric run `dir="ltr"` + `unicode-bidi: isolate`. Hidden price → "מחיר בתיאום" in `var(--color-ink-muted)`, italic, **same layout slot, same height** — identical to `storefront-catalog.md`'s price-hidden rule so the two views cannot disagree |
| "הוזמן" `Badge` — **default variant** | `background: var(--color-surface-raised)`, `color: var(--color-ink)` (**15.75:1** on white ✓), `--text-xs`/600, `padding: 2px var(--space-3)`, `border-radius: var(--radius-full)`, `box-shadow: var(--shadow-sm)` — **byte-identical to the storefront `Badge`**. *Anchor differs by necessity*: the storefront overlays it on a large card photo; a 72px console cover cannot carry a legible overlay, so the console places the same chip on **its own line under the name**. Same chip, different anchor — recorded deliberately |
| "בארכיון" `Badge` — **`muted` variant** | `color: var(--color-ink-muted)` on `--color-surface-raised` (**6.36:1** ✓), `box-shadow: none`, `border: 1px solid var(--color-border)`. **Deliberately not identical to "הוזמן".** "הוזמן" is a live status the storefront also shows and the owner acts on; "בארכיון" is a console-only shelf label on a row that is already read-only. The recession is the point. `muted` is not currently one of `components.md`'s four enumerated `Badge` variants — queued as §12 item 7 |
| Stock badge (three-way, derived client-side, read-only) | `variant_count == 0` → "לא הוגדרו מידות", `Badge muted` (`--color-ink-muted` on `--color-surface-raised`, 6.36 ✓) · `variant_count > 0 && total_quantity == 0` → "אזל מהמלאי", **`Badge warning`** (`--color-warning-text`/600 on `--color-surface-raised`, 5.90 ✓, `border: 1px solid var(--color-border)`, no shadow) · else "במלאי (N)" with N in `<bdi dir="ltr">`, `Badge muted` (6.36 ✓). Colour never carries the meaning alone — the word does (usage law 2). `warning` is likewise not in `components.md`'s enumerated variants — same §12 item 7. **This badge does not exist on the storefront** (`out_of_stock` is manage-only per spec); "הוזמן" is the one chip both surfaces share |
| Photo count | `<bdi dir="ltr">5</bdi> תמונות` / "אין תמונות" when 0 |
| Pager | `Button secondary` ×2, `min-block-size: 44px`, `disabled` at the ends |

### 2.4 States

| State | What the owner sees | Trigger |
|---|---|---|
| **Default** | toolbar + count + rows + pager | ≥1 dress on the page |
| **Loading** | toolbar rendered live (search is usable immediately); 6 `Skeleton` rows — a 72×96 `--radius-md` block + two text lines (100% / 40%), `--color-surface` fill, 1.5s pulse, **static under `prefers-reduced-motion`** | initial fetch / page change |
| **Empty (no dresses at all)** | `EmptyState`, icon-less: "אין עדיין שמלות בקטלוג" (`--text-lg` display) + "השמלה הראשונה תופיע כאן ובאתר של הבוטיק." (muted) + `Button primary` "שמלה חדשה". Never a system-error look | `total == 0`, no filter active |
| **Empty (filtered)** | different copy, same block: "לא נמצאו שמלות התואמות לחיפוש." + `Button secondary` "ניקוי החיפוש". Distinguishing these two matters — the first is a first-run moment, the second is a dead end the owner must be able to reverse | `total == 0` with search/filter |
| **Empty (archive)** | "אין שמלות בארכיון." | `archived=true`, `total == 0` |
| **Error** | inline block inside the list Card, console chrome intact: `--text-lg` display heading "לא הצלחנו לטעון את השמלות", muted body, `Button secondary` "נסי שוב". Backend message shown when the house error envelope carries one (`errorMessage()`); never a raw Axios/fetch string | fetch failure |
| **Success** | there is no "saved" state on the list — mutations happen in the editor and patch the row in place (`onDressChanged`), so the row's badges and cover update with no refetch and no flash | any editor mutation |
| Archive view | same list, rows show a `Badge` "בארכיון"; row still opens (detail resolves archived dresses read-only) | `archived=true` |
| Searching | after the 300ms debounce settles, a polite `role="status"` announces "נמצאו <bdi>4</bdi> שמלות" — **that region is the count line above the list** (§8.1), not a second one; the list screen has exactly one polite region. The list itself does not spin between keystrokes — it dims to 0.6 opacity while stale (no motion under reduced-motion) | typing |

---

## 3. Screen B — Create + edit dress form

### 3.1 Desktop 1440 / 768 (720px column)

```
+-------------------------------------------------------------------------+
|  → חזרה לרשימת השמלות            (secondary link, inline-start)          |
|                                                                         |
|  עלמה                                        (h2, display, --text-xl)   |
|                                                                         |
|  +-- Card: פרטי השמלה ------------------------------------------------+  |
|  |  שם השמלה *                                                        |  |
|  |  [ עלמה .......................................... ]  12/200        |  |
|  |                                                                    |  |
|  |  תיאור                                                             |  |
|  |  [ .............................................. ]                |  |
|  |  [ .............................................. ]  318/4000      |  |
|  |                                                                    |  |
|  |  מחיר (₪)                                                          |  |
|  |  [ 8900 ]  <- dir="ltr" island, inputMode="decimal", 160px          |  |
|  |                                                                    |  |
|  |  [x] הצגת המחיר באתר                                               |  |
|  |      כשהאפשרות כבויה, הלקוחות רואות «מחיר בתיאום» במקום הסכום.      |  |
|  |                                                                    |  |
|  |  ┌ בקטלוג יוצג:  8,900 ₪ ────────────────────────┐  <- preview      |  |
|  |  └───────────────────────────────────────────────┘                 |  |
|  |                                                                    |  |
|  |  [ ] הוזמן                                                         |  |
|  |      סימון ידני, ללא תאריך — יש להסיר ידנית כשהשמלה מתפנה           |  |
|  |                                                                    |  |
|  |  סדר בקטלוג                                                        |  |
|  |  [ 0 ]   מספר נמוך = מוצג ראשון                                    |  |
|  |                                                                    |  |
|  |                        נשמר לפני רגע   [ שמירה ]  <- inline-end     |  |
|  +--------------------------------------------------------------------+  |
|                                                                         |
|  +-- Card: מידות ומלאי  (Screen C) -----------------------------------+  |
|  +-- Card: תמונות       (Screen D) -----------------------------------+  |
|                                                                         |
|  ------------------------------------------------- hairline            |
|  [ העברה לארכיון ]        <- ghost-danger, inline-start, confirm Modal  |
+-------------------------------------------------------------------------+
```

### 3.2 Mobile 375

Same order, one column; every field full-width; the price input keeps its 160px cap (a phone-wide number field invites a phone number); **save button full-width** (`manage-restyle.md`'s 375 rule) with the "נשמר לפני רגע" cue moving *above* it. The three Cards stack with `--space-6` between them. The archive row sits last, above the panel end.

### 3.3 Create mode

```
|  +-- Card: פרטי השמלה --------------------------+
|  |  ...fields, fully active...                  |
|  |                        [ יצירת שמלה ]        |
|  +----------------------------------------------+
|  +-- Card: מידות ומלאי  (controls disabled; heading  +
|  |                        and hint at full contrast)  |
|  |  יש לשמור את השמלה לפני הוספת מידות ותמונות        |
|  |  הוספה מהירה (מידות אירופאיות) —                   |
|  |    יש לשמור את השמלה תחילה   <- visible group label|
|  |  (32)(34)(36)(38)(40)        <- disabled, NOT      |
|  |                                 aria-hidden        |
|  +----------------------------------------------------+
|  +-- Card: תמונות       (controls disabled; heading   +
|  |                        and hint at full contrast)  |
|  |  יש לשמור את השמלה לפני הוספת מידות ותמונות        |
|  |  הוספת תמונות (יש לשמור את השמלה תחילה)            |
|  |  [ בחירת קבצים… ]            <- disabled           |
|  +----------------------------------------------------+
```

The disabled Cards are **rendered, not hidden** — the owner must see that sizes and photos exist and are one save away. The hint is a real `<p>` inside each Card (not a `title`, not a tooltip), so it is read by AT even though the controls inside are `disabled`. On a successful `POST` the editor loads the detail and switches to edit mode **in place** (no navigation, per spec), the two Cards enable, and a polite `role="status"` announces "השמלה נוצרה. אפשר להוסיף מידות ותמונות."

**Two rules make this state legal, and both were violated in rev 1:**

1. **No opacity on the pane.** `opacity` composites over *everything* in the Card, including text that is not a disabled control. `--color-ink-muted` at 0.55 over paper resolves to `#AA9F93` = **2.29:1**; `--color-ink` at 0.55 resolves to `#867E75` = **3.53:1**, and the Card `<h3>` at `--text-lg` (19px) / weight 500 is **not** large text (large = ≥24px, or ≥18.66px at weight ≥700), so it needs 4.5:1 too. That is a hard WCAG 1.4.3 failure on the one paragraph whose entire job is to explain the state. It cannot be tuned: no opacity below 0.9 rescues `--color-ink-muted` on paper (0.7 → 3.01, 0.8 → 3.68, 0.9 → 4.50). WCAG's inactive-control exemption covers the disabled chips and the disabled file input; it does **not** cover a heading, a paragraph or a counter. **The `<h3>`, the hint `<p>` and the photo counter render at their full token colours** (`--color-ink` 13.89:1 / `--color-ink-muted` 5.61:1) and the recession is carried by the `disabled` controls, which dim themselves and are exempt.
2. **Every disabled control states its reason on its own visible label.** Not on a detached paragraph elsewhere in the Card — `disabled` drops the control from the tab order, so a screen-reader user arriving by any other route never learns why. The file input's label reads "הוספת תמונות (יש לשמור את השמלה תחילה)"; the quick-size chip group gets a visible group label "הוספה מהירה (מידות אירופאיות) — יש לשמור את השמלה תחילה" and is `role="group" aria-labelledby`, **never `aria-hidden="true"`** — hiding the affordance from AT contradicts this section's own argument that the owner must *see* that sizes exist.

### 3.4 Component notes — exact tokens

| Element | Spec |
|---|---|
| Back-link | `Button ghost` styled as a link, `--text-sm`, `var(--color-gold-text)`. It sits in the content column **outside every Card**, i.e. on `--color-bg` (cream) — **5.57:1**, the figure `tokens.md` already publishes. (The 5.08:1 paper figure belongs to the *in-Card* gold-text uses — "תמונה ראשית" and "קבעי כתמונה ראשית" — see §10.1.) `min-block-size: 44px`. Arrow glyph is `→` and it points **inline-start**, i.e. rightward on screen in RTL; rendered `aria-hidden` with the text carrying the meaning |
| Editor heading | The dress name in `--font-display`, `--text-xl`, weight 500, `--color-ink`, always `tabindex="-1"` (it is §8.1's focus destination on row-open). **Level follows §1.1's two outlines — `<h2>` at ≥768, `<h3>` at ≤767, from one `headingLevel` value, never a hard-coded tag**; the visual treatment is identical at both widths. Wraps freely — **never clamped** (this is the one place the owner must read a 200-char name in full) |
| Field label | `--text-sm`, weight 600, `--color-ink`, `margin-block-end: var(--space-1)`, **always visible** (usage law 3). Required fields carry a text `*` plus `required` — the asterisk is explained once at the top of the Card: "שדות המסומנים ב-* הם חובה" |
| Input / TextArea | `background: var(--color-surface-raised)`, `border: 1px solid var(--color-border-input)` — **at the corrected token value `#8A7A5E`: 3.69:1 on paper, 4.18:1 on white, 4.04:1 on cream**, all ≥3:1. The rev-1 value `#B9A98F` computed **2.03 / 2.30 / 2.22** and was the *only* visible boundary of every field in this feature (the fields have no fill contrast against the white or paper they sit on either), so a 2.03:1 hairline was the sole thing saying "this is a field". See §12 item 3a — this is a `tokens.md` correction, not a local override. `border-radius: var(--radius-sm)`, `padding: var(--space-2) var(--space-3)`, `min-block-size: 44px`. Focus: `2px solid var(--color-focus)` with `2px` offset (usage law 4). Textarea `min-block-size: 120px`, `resize: block` |
| Char counter | `--text-xs`, `var(--color-ink-muted)`, inline-end under the field, `<bdi dir="ltr">12/200</bdi>`. Turns `var(--color-warning-text)`/600 within 20 of the cap — a colour change **plus** the number, never colour alone |
| Price field | `inputMode="decimal"` `dir="ltr"` — an LTR island. **The box keeps its RTL position in the form flow; only its content direction flips**, and `text-align` is left unset so it inherits `start` *within* the input's own `ltr` direction. The ₪ lives in the **label** ("מחיר (₪)"), not as an in-field suffix — F7's `TypesSection` deposit-field precedent, and it sidesteps a bidi trap for zero benefit. `max-inline-size: 160px` |
| Preview line | the single place price + visibility resolve to one readable outcome. `background: var(--color-surface-raised)`, `border-inline-start: 3px solid var(--color-gold)` (decorative — raw gold carries **no text here**, usage law 1), `border-radius: var(--radius-sm)`, `padding: var(--space-3)`. Text: `בקטלוג יוצג: ` in `--color-ink-muted` + the `Price` component in `--color-ink`, or "מחיר בתיאום" muted italic. **The visible line is plain text and repaints immediately on every keystroke — it is not itself the live region.** The announcement is a `VisuallyHidden role="status"` sibling written **only on discrete events**: the `price_visible` toggle changing, and the price input's `change`/`blur`. §4.3's ruling applies here verbatim — a continuously-changing value is not a discrete event, and a live region bound to the price input announces once per character ("8", "89", "890", "8900"), each announcement interrupting the last and re-reading the whole atomic region. If keystroke-driven announcement is ever wanted, debounce ≥500ms after input settles and suppress it when the resolved string is unchanged since the last announcement — the same fallback §4.3 specifies for the stock total |
| **Toggle row geometry (both toggles)** | The `<label>` **wraps the checkbox and its title line together** and carries `min-block-size: 44px`; the checkbox itself is `24×24`. That makes the whole title row one ≥44×44 hit target — the same treatment the filter checkboxes already use (`.check`). A bare `20×20` box next to a `--text-sm` line is ~21px tall and misses the bar at 375 on the two most consequential controls in the form (usage law 7). The **description stays outside the `<label>`**, tied by `aria-describedby`, so it is not folded into the accessible name; it is offset by `padding-inline-start: calc(24px + var(--space-3))` to align under the title |
| `price_visible` `Toggle` | label "הצגת המחיר באתר" + description line in `--text-xs`/`--color-ink-muted` (usage: `components.md` `Toggle` = label + description). Wired to the preview |
| `reserved` `Toggle` | label "הוזמן" + description **verbatim from spec**: "סימון ידני, ללא תאריך — יש להסיר ידנית כשהשמלה מתפנה". The date-less-ness is the whole point of the copy — date-bound reservation is E5 #7 and the owner must not form the expectation. The description is `aria-describedby`-tied to the control, not a decorative caption |
| `sort_order` field | `type="number"` `dir="ltr"`, `max-inline-size: 96px`, help "מספר נמוך = מוצג ראשון" |
| Save row | `display:flex; justify-content:flex-end; gap: var(--space-3)` → visually the **inline-end**, i.e. the left in RTL. `Button primary` "שמירה" (gold bg + ink text, 6.41 ✓), loading state = spinner replaces the label with **width locked** (`components.md`). Muted cue "נשמר לפני רגע" in `--text-xs`/`--color-ink-muted`, `role="status"` |
| Archive row | separated by a `1px solid var(--color-border)` hairline and `--space-6`. `Button ghost-danger`: `color: var(--color-danger)` on paper (6.18 ✓), no fill, no border. Opens a focus-trapped `Modal`: "להעביר את «עלמה» לארכיון?" / "השמלה תוסר מהאתר. אפשר לשחזר אותה מלשונית «ארכיון»." / [ביטול] [העברה לארכיון]. Archived dress → the row shows "שחזור" instead |

### 3.5 States

| State | What the owner sees | Trigger |
|---|---|---|
| **Default (edit)** | populated form, all three Cards live | detail loaded |
| **Default (create)** | fields Card live, other two disabled with the hint | no id yet |
| **Loading** | `Skeleton`: heading line + 6 field blocks; the two lower Cards render their frames only | `GET /manage/dresses/{id}` |
| **Empty** | not applicable — a dress form is never empty; the *sub-Cards* carry the empty states (§4.5, §5.5) | — |
| **Saving** | save `Button` in loading state, all inputs `disabled`, archive button `disabled` | submit in flight |
| **Validation error (client)** | inline `--text-xs` `--color-danger` message under the offending field, `aria-invalid="true"` + `aria-describedby` to it; focus moves to the **first** invalid field; no request is sent | `validateDress` fails |
| **Save error (server)** | `Toast` danger with the backend message from the house `{"error":{"code","message"}}` envelope, **plus** the field-level inline error when the code maps to a field. Form stays populated — nothing is cleared | 4xx/5xx |
| **Success** | "נשמר לפני רגע" cue appears next to the save button and fades after 4s (text removed from the DOM, not just faded — a stale "saved" cue is a lie) | 200 |
| **Archived (read-only view)** | Card renders with a `Badge` "בארכיון" beside the heading and a muted line "השמלה בארכיון — לשחזור לחצי «שחזור»." All fields `disabled`; the variants and gallery Cards are `disabled` too (server 404s their writes on an archived dress) | `archived: true` |
| **Name collision hint** | non-blocking `--text-xs` `--color-ink-muted` line under the name field: "כבר קיימת שמלה בשם הזה. אפשר להמשיך." Never an error colour, never blocks the save — the DB deliberately allows duplicate names (same designer model, two colours) | client-side match against the loaded list page |

---

## 4. Screen C — Variant (size/quantity) matrix

### 4.1 Desktop 1440 / 768

```
+-- Card: מידות ומלאי ------------------------------------------------+
|  מידות ומלאי                              סה״כ במלאי: 7 יחידות       |
|                                                                     |
|  הוספה מהירה (מידות אירופאיות)                                       |
|  (32) (34) (•36) (•38) (40) (42) (44) (46) (48) (50) (52) (54)      |
|  (56) (58)                          • = כבר ברשימה                   |
|                                                                     |
|  מידה מותאמת                                                        |
|  [ מידה מיוחדת לפי מדידה ....... ]  [ הוספה ]                        |
|                                                                     |
|  ---------------------------------------------------- hairline      |
|  ( 36 )        כמות  [ + ][  3  ][ − ]                  [ הסרה ]     |
|  ( 38 )        כמות  [ + ][  4  ][ − ]                  [ הסרה ]     |
|  ( מידה       כמות  [ + ][  0  ][ − ]                  [ הסרה ]     |
|    מיוחדת )                                                         |
|  ---------------------------------------------------- hairline      |
|  ^ drawn in LOGICAL order like every wireframe here. On screen the   |
|    stepper is an LTR island and renders  − 3 +  left-to-right; the   |
|    "כמות" label stays outside it in RTL flow. See §4.3.              |
|                                                                     |
|                                             [ שמירת מלאי ]           |
+---------------------------------------------------------------------+
```

**Duplicate-size inline error** (rendered under the custom-size input, before any request):

```
|  מידה מותאמת                                                        |
|  [ 38 ......................... ]  [ הוספה ]                        |
|  ⓘ המידה «38» כבר קיימת ברשימה.        <- --color-danger, --text-xs |
```

**Auto "אזל" hint** (all quantities 0):

```
|  ---------------------------------------------------- hairline      |
|  כל המידות במלאי 0 — השמלה תסומן «אזל מהמלאי» בקטלוג הניהול.        |
|     (--color-warning-text, --text-sm, role="status")                |
```

### 4.2 Mobile 375

```
+-- Card ------------------------+
| מידות ומלאי                    |
| סה״כ במלאי: 7 יחידות           |
|                                |
| הוספה מהירה                    |
| (32)(34)(•36)(•38)(40)(42)     |  chips wrap, 44×44 each
| (44)(46)(48)(50)(52)(54)(56)   |  • = כבר ברשימה
| (58)                           |
|                                |
| מידה מותאמת                    |
| [ ......................... ]  |
| [        הוספה              ]  |
| ------------------------------ |
| ( 36 )                         |  row stacks:
| כמות  [ + ][ 3 ][ − ]  [הסרה]  |  label line, then controls line
| ------------------------------ |  (logical order — the LTR island
| ( 38 )                         |   renders − 3 + on screen, §4.3)
| כמות  [ + ][ 4 ][ − ]  [הסרה]  |
| ------------------------------ |
| [        שמירת מלאי          ] |  full-width
+--------------------------------+
```

### 4.3 Component notes — exact tokens

| Element | Spec |
|---|---|
| Quick-entry chip — **plain `<button>`, never `aria-pressed`** | `border: 1px solid var(--color-border-input)` (**3.69:1** on paper at the corrected token) · `border-radius: var(--radius-full)` (pill, matching the already-passed `design-system/prototype.html` chip — see §12 item 3e) · `--text-sm` · `min-block-size: 44px; min-inline-size: 44px` · label `<bdi dir="ltr">38</bdi>`. **Already-listed** (`.listed`): `background: var(--color-surface-raised)`, `border-color: var(--color-gold-strong)` (**3.47:1 against the paper Card outside the chip, 3.93:1 against the chip's own white fill** — both ≥3:1 for a non-text boundary), label weight 600 **plus** a visible `•` marker — listed-ness never rests on the border colour alone (usage law 2). List is `EU_SIZE_QUICK_LIST` = 32…58 even, frontend-only |
| **Why not `aria-pressed` — ruled** | `aria-pressed` declares a *toggle button*, and ARIA requires activation to flip the pressed state. §8.3 rules the opposite: a second press does **not** remove the size — it moves focus to the existing row. So AT would announce "38, לחצן, לחוץ", the owner would activate it expecting to un-press (i.e. delete the size), and focus would silently jump to a quantity field instead. This is the same broken-contract defect as the `role="tab"` ruling in §1.1, and it is resolved the same way: **drop the ARIA that promises behaviour the control does not have, and carry the state in the accessible name** — `aria-label="38 — כבר ברשימה"` when listed, plain "38" otherwise. That is exactly the vocabulary §4.1's wireframe legend already uses (`• = כבר ברשימה`), and it matches what the button actually does. The alternative — making the chip a real toggle whose second press removes the row — was rejected: it collides with §8.3's focus-move rationale and turns a low-stakes add affordance into a destructive one |
| **The `•` marker is a real element, not `content:`** | `<span class="mark" aria-hidden="true">•</span>` inside the button, not `::before{content:"• "}`. Chrome and Firefox fold generated content into the accessible name, so a `content:` marker computes the name as "• 38" — the redundant cue added to satisfy usage law 2 would leak into the one string it must not touch. Colour: **the `•` is rendered text at 14px, so it takes `--color-gold-text` (5.76:1 on the white listed fill), never `--color-gold-strong`** — gold-strong is reserved for meaningful *non-text* UI and large display accents ≥24px |
| Chips container | `role="group"` `aria-label="הוספה מהירה של מידות אירופאיות"`; `display:flex; flex-wrap:wrap; gap: var(--space-2)` |
| Custom size input | label "מידה מותאמת", `dir="auto"` (both "מידה מיוחדת" and "US 6 / EU 36" occur), `maxlength=32` (`MAX_SIZE_LABEL_LENGTH`) |
| Stock row | `<li>` · `padding-block: var(--space-3)` · `border-block-end: 1px solid var(--color-border)` · size rendered as a static chip (same chip visual, `border-color: var(--color-border)`, not a button), label `<bdi>`-wrapped |
| Quantity stepper | `<input type="number" dir="ltr" min="0" max="1000">` (`MAX_VARIANT_QUANTITY`) flanked by `−` / `+` `Button secondary` at 44×44. The **input is the source of truth**; the steppers are convenience. Each stepper carries `aria-label="הפחתת כמות במידה 38"` / `"הגדלת כמות במידה 38"` — never a bare "−". `−` is `disabled` at 0. **The input itself takes `aria-labelledby`, not `aria-label`**: its visible label is the "כמות" `<span>` in the row, and an `aria-label` would silently override that visible text rather than include it. `aria-labelledby="qty-lbl-{size} size-{size}"` points at the visible "כמות" span **and** the already-visible size chip → "כמות 38". Nothing is duplicated and nothing is hidden |
| **Stepper direction — ruled** | The `−` / value / `+` cluster is an **LTR island**, exactly like the price field: `direction: ltr; unicode-bidi: isolate` on the control group, with the visible "כמות" label kept **outside** it in RTL flow. **Drawn in logical order — which is how every wireframe in this document is drawn — the cluster reads `+ value −`; on screen the island renders `− value +` left-to-right.** (`−` sits at the physical left of the digits and `+` at the physical right, matching how the numeric value itself reads; `כמות` sits at the far right.) The §4.1 and §4.2 wireframes draw the logical order and annotate the rendered order, so the two coordinate systems are never mixed on one line. Without this ruling the flex row mirrors (RTL order: כמות, −, value, +) while the `dir="ltr"` numeric run between the buttons does not — a decrement/increment pair mirrored around a numeric island that isn't, which is the one arrangement guaranteed to read inconsistently. Not an operability failure (the per-size `aria-label`s are explicit and both buttons are reachable) but an RTL decision this doc must make so the F9 build does not guess it the other way. Precedents: §3.4 rules the price field an LTR island; §5.4 rules ↑/↓ over ←/→ *because* they are direction-neutral |
| Remove | `Button ghost-danger` "הסרה", `aria-label="הסרה — מידה 38"` — the accessible name **begins with the visible label verbatim**, disambiguator appended (§10.3, WCAG 2.5.3). ≥44×44 |
| Total line | `סה״כ במלאי: <bdi dir="ltr">7</bdi> יחידות`, `--text-sm`, `--color-ink-muted`. Recomputes live as the owner types, so the derived badge is never a surprise at save time — but it is **plain text, not `role="status"`**. Bound to `<input type="number">`, a live region here fires on every keystroke and every arrow-key repeat (typing "12" = two announcements, each interrupting the last), and on a 60-row matrix that is actively hostile while also competing with the §4.5 אזל hint in the same Card. A continuously-changing value is not a discrete event. The event that carries meaning is the 0-crossing, and that already has its own region. If the total must also be spoken, debounce ≥500ms after input settles and announce only when the value actually changed since the last announcement |
| Save | `Button primary` "שמירת מלאי", inline-end (full-width @375). **Separate from the dress save** — the matrix is `PUT …/variants`, a whole-set replace, and merging the two buttons would imply one atomic write that does not exist |
| Unsaved marker | while the local matrix differs from the loaded one: `--text-xs` `--color-warning-text` "יש שינויים שלא נשמרו" next to the save button, and the button label stays "שמירת מלאי" (never becomes "שמור *") |

### 4.4 Why one matrix and not per-size cards

The whole matrix is one write (`PUT`, full replace, spec). A per-row save button would suggest per-row persistence and would make the duplicate-size check — which is a property of the *set* — impossible to place. One set, one save.

### 4.5 States

| State | What the owner sees | Trigger |
|---|---|---|
| **Default** | chips + rows + total + save | ≥1 variant |
| **Loading** | inherited from the editor's detail fetch — the Card renders its frame and a 3-line `Skeleton` | detail in flight |
| **Empty (zero variants)** | `EmptyState` inside the Card: "לא הוגדרו מידות לשמלה הזו." + "בחרי מידה מהרשימה המהירה, או הוסיפי מידה מותאמת." The quick chips render **above** the empty text, not below it — the fix is the first thing in the tab order. The dress's stock badge reads "לא הוגדרו מידות", **not** "אזל מהמלאי" (spec edge case 6) | `variants == []` |
| **Error (client, duplicate)** | inline `--color-danger` `--text-xs` under the custom-size input or under the offending row, `aria-invalid="true"` + `aria-describedby`-tied **and `role="alert"`**; the row is **not** added; focus stays in the input with its text intact so the owner can correct it. The `role="alert"` is not redundant with `aria-describedby` — it is the only thing that speaks. §8.3 keeps focus in the input (right for usability), which means the error is inserted *under standing focus*; screen readers announce `aria-describedby` when focus **arrives** at a control and do not reliably re-announce it when the referenced node is inserted or changed underneath one. Without the alert a blind owner presses "הוספה", hears nothing, and sees no row — a silent failure | normalised label collides |
| **Error (client, count)** | "אפשר עד 60 מידות לשמלה." in `role="alert"` — it surfaces on activation with **no accompanying focus move**, same shape as the duplicate error. **And every control the cap disables states the reason on its own visible label** (§10.3), exactly as create mode does: the chip group's visible label becomes "הוספה מהירה (מידות אירופאיות) — הגעת ל-60 מידות", the custom-size input's label becomes "מידה מותאמת (הגעת ל-60 מידות)", and the disabled "הוספה" button carries `aria-label="הוספה — הגעת ל-60 מידות"`. The `aria-describedby` that rev 2 put on the disabled input is **removed**: a `disabled` input is not reachable, so the reference is inert and the reason has to live on the label instead | `MAX_VARIANTS_PER_DRESS` |
| **Error (server)** | `Toast` danger. `409 DUPLICATE_SIZE` maps back to the offending row's inline error (the client check should have caught it; the server is the authority). The previous saved matrix is untouched — the local draft stays on screen for correction, never wiped | `PUT` fails |
| **Saving** | save `Button` loading, all quantity inputs and chips `disabled` | in flight |
| **Success** | "המלאי נשמר" `Toast` success (`--color-success` on paper, 5.56 ✓) + the unsaved marker clears + the dress row's stock badge repaints from the returned `DressDetail` | 200 |
| **Derived אזל hint** | `role="status"` line, `--color-warning-text` (5.20 on paper ✓): "כל המידות במלאי 0 — השמלה תסומן «אזל מהמלאי» בקטלוג הניהול." Appears live as the last quantity hits 0, before the save. Explicitly says *manage* catalog — `out_of_stock` is manage-only and the storefront renders no out-of-stock badge (spec) | all quantities 0, ≥1 row |

---

## 5. Screen D — Image manager

### 5.1 Desktop 1440 / 768

```
+-- Card: תמונות -------------------------------------------------------+
|  תמונות                                            5 מתוך 12          |
|                                                                       |
|  הוספת תמונות                                                         |
|  [ בחירת קבצים… ]  (real <input type="file" multiple>, keyboard-       |
|                     reachable, never display:none)                    |
|  צלמי לאורך (פורטרט). עד 10MB לתמונה · JPG/PNG/WebP ·                 |
|  4–6 תמונות לשמלה מספיקות                                             |
|                                                                       |
|  --- upload queue (only while non-empty) ---------------------------  |
|  2 קבצים לא צורפו — פרטים ברשימה למטה   <- role="alert", assertive     |
|     (client-side rejection only: no request, no focus move)           |
|  מעלה 2 מתוך 3                          <- role="status", polite       |
|     (RUNNING form — the drawn state still has a row in flight. The     |
|      denominator is 3, not 5: the two files rejected client-side       |
|      never left the browser, and they are counted by the alert above.  |
|      On drain the SAME region reads "הועלו 2 מתוך 3 · 1 נכשלה" — §5.5) |
|  IMG_4821.jpg   3.2MB    הועלתה                                       |
|  IMG_4822.jpg   4.1MB    מעלה…                                        |
|  IMG_4823.heic  6.0MB    נכשלה — HEIC אינו נתמך. שמרי כ-JPG           |
|     (client-side reject — no retry: the same file fails identically)  |
|  IMG_4824.jpg  11.4MB    נכשלה — הקובץ גדול מ-10MB                    |
|  IMG_4825.jpg   3.4MB    נכשלה — העלאת הקובץ נכשלה.   [ נסי שוב ]      |
|     (aria-label="נסי שוב — IMG_4825.jpg" — visible label first)        |
|                                                                       |
|  --- gallery (ol) --------------------------------------------------  |
|  +-----------+  +-----------+  +-----------+                          |
|  |(1)  3:4   |  |(2)  3:4   |  |(3)  3:4   |                          |
|  |           |  |           |  |           |                          |
|  +-----------+  +-----------+  +-----------+                          |
|  תמונה ראשית    [↑][↓][מחיקה] [↑][↓][מחיקה]                           |
|  (מוצגת בקטלוג)  קבעי כתמונה   קבעי כתמונה                            |
|  [↑][↓][מחיקה]   ראשית          ראשית                                 |
|                                                                       |
|  התמונה הועברה למקום 3 מתוך 5      <- role="status" (shared region)   |
+-----------------------------------------------------------------------+
```

### 5.2 Storage-disabled state (`media_uploads_enabled === false`, or any 503)

```
+-- Card: תמונות -------------------------------------------------------+
|  תמונות                                            0 מתוך 12          |
|                                                                       |
|  +-- notice (role="status", WHITE fill + border-input hairline) --+    |
|  |  העלאת תמונות עדיין לא זמינה                                   |    |
|  |  אפשר להמשיך למלא את פרטי השמלה ואת המידות — התמונות יתווספו   |    |
|  |  מאוחר יותר.                                                   |    |
|  +----------------------------------------------------------------+   |
|                                                                       |
|  הוספת תמונות (לא זמין כרגע)                                          |
|  [ בחירת קבצים… ]   <- disabled, but the reason is on the visible     |
|                        <label>, so it is announced. `disabled`         |
|                        alone would drop it from the tab order and a    |
|                        screen-reader user would never learn why.       |
+-----------------------------------------------------------------------+
```

**This is not an error and not a blocker.** Deliberate visual distinction:

| | `PolicyBlockerBanner` | Storage-disabled notice |
|---|---|---|
| Means | "you must act before you can take bookings" | "the platform isn't ready; nothing for you to do" |
| Surface | `--color-surface` (paper, on the cream page) | **`--color-surface-raised`** (white, on the paper Card) |
| Marker | `border-inline-start: 3px solid var(--color-gold-strong)` | **no stripe** — a `1px solid var(--color-border-input)` hairline all round (**3.69:1** against the paper Card, **4.18:1** against the notice's own white fill), plus the fill change |
| Text | `--color-warning-text` (5.20 on paper ✓) | lead `--color-ink` (**15.75:1** on white ✓), body `--color-ink-muted` (**6.36:1** on white ✓) |
| Action | link to the section that fixes it | none — there is nothing the owner can do |

**Why the notice's fill *and* its border both changed (rev 2 fill, rev 3 border).** Rev 1 specified `--color-surface` for a notice that sits *inside* a `--color-surface` Card: a **1.00:1** fill-to-fill relationship delimited by a `--color-border` hairline at **1.22:1** on paper. For a low-vision owner, or on a low-contrast display, there was no visible box at all — the notice read as loose body copy inside the photos Card, which defeats the entire point of §5.2 (a calm but *legible* explanation of why uploads are unavailable). The text was always fine; the block boundary did not exist.

Rev 2 changed the fill to `--color-surface-raised`. That was necessary but **not sufficient**: `#FFFFFF` on `#F6F0E6` is **1.13:1**, and the `--color-border` hairline at 1.22:1 was still the thing doing the delimiting — the same problem moved 0.13 of a ratio point. Nothing here fails 1.4.3 (the text is 15.75 lead / 6.36 body) and nothing violates IS 5568; what it missed was this document's own bar in §10.3, on the one block whose entire job is to read as a distinct, calm explanation rather than as loose body copy.

Rev 3 keeps the white fill — the rationale for it is sound — and gives the block a boundary that actually exists: **`1px solid var(--color-border-input)`**, which at the corrected token `#8A7A5E` is **3.69:1 against the paper Card** and **4.18:1 against the notice's own white fill**. That is the console's established form-boundary vocabulary on this surface, so it introduces no new language, and it preserves every deliberate distinction from `PolicyBlockerBanner`: no danger colour, no gold stripe, no action, no urgency. The fill is likewise the one the `Badge`, the preview line and the form inputs already use here.

Everything else in the editor — name, description, price, visibility, reserved, sort order, the entire variant matrix, archive, restore — stays **fully interactive**. That is the whole requirement.

### 5.3 Mobile 375

```
+-- Card: תמונות ----------------+
| תמונות             5 מתוך 12   |
| הוספת תמונות                   |
| [   בחירת קבצים…            ]  |
| צלמי לאורך (פורטרט). עד 10MB   |
| לתמונה · JPG/PNG/WebP ·        |
| 4–6 תמונות לשמלה מספיקות       |
| ----------------------------   |
| +---------+  +---------+       |  2-col grid
| |(1) 3:4  |  |(2) 3:4  |       |
| +---------+  +---------+       |
| תמונה ראשית   [↑][↓]           |  control cluster wraps
| (מוצגת בקטלוג) [  מחיקה   ]     |  to 2 rows @375
| [↑][↓]        [קבעי כתמונה     |
| [ מחיקה ]      ראשית      ]     |
+--------------------------------+
```

### 5.4 Component notes — exact tokens

| Element | Spec |
|---|---|
| Cap counter | Card header inline-end, `--text-sm`, `<bdi dir="ltr">5</bdi> מתוך <bdi dir="ltr">12</bdi>`. `--color-ink-muted`; at 12/12 it becomes `--color-warning-text`/600 **and** the copy changes to "הגלריה מלאה" — number + word, never colour alone |
| File input | a **real, visible, focusable** `<input type="file" multiple accept="image/jpeg,image/png,image/webp">` with a visible `<label>`. `display:none` + a label-click shim is **forbidden**: it breaks Safari/VoiceOver and, in the disabled case, hides the reason. Styled via `::file-selector-button` with `Button secondary` tokens (`border: 1px solid var(--color-ink)`, `--radius-md`); the surrounding input gets the focus ring via `:focus-within` |
| **The 44px floor belongs on `::file-selector-button`** | In Chrome and Safari, clicking the *text* portion of a file input does nothing — only the `::file-selector-button` pseudo-element opens the picker. So `min-block-size: 44px` on the `<input>` alone is cosmetic: the real touch target on the owner's phone is the button, and a 34px button fails usage law 7 on the primary control of Screen D. Rule: `::file-selector-button { min-block-size: 44px; padding-block: var(--space-2) }`, and the wrapping input grows to contain it — `min-block-size: var(--space-16)` (64px = 44 + 2×`--space-2` padding + 2×1px border, rounded to the scale) so the button is never clipped |
| Per-item accessible names | **Every per-item control in the תמונות Card — gallery items *and* queue rows alike — carries its item's identity in its accessible name.** In the gallery that identity is the ordinal, resolved from the same source as the ordinal chip; in the **queue** it is the filename, already rendered adjacent in the row. **The identity is *appended*, never substituted** (§10.3, WCAG 2.5.3): where the control has visible text the accessible name begins with that text verbatim and the disambiguator follows an em-dash — `aria-label="קבעי כתמונה ראשית — תמונה 2"`, `aria-label="מחיקה — תמונה 2"`, `aria-label="נסי שוב — IMG_5002.jpg"`. Rev 2 scoped this rule to "inside the gallery", and the queue is a *sibling* of the gallery, so two bare "נסי שוב" buttons (three, counting the list-error state) slipped through with identical names. The consequence is the same destructive-adjacent one: from a buttons list the owner cannot tell which file she is re-uploading, and retry re-runs the full presign → POST → confirm cycle, i.e. it consumes a gallery slot |
| Guidance line | verbatim from spec, persistent (not a tooltip, not a first-run hint): "צלמי לאורך (פורטרט). עד 10MB לתמונה · JPG/PNG/WebP · 4–6 תמונות לשמלה מספיקות" · `--text-xs`, `--color-ink-muted`. This is the shipped mitigation for having no image processing (spec Risk 3) — it is not decoration and must not be trimmed |
| Slot precheck line | when fewer than the selected count remain: "ניתן להעלות עד 12 תמונות לשמלה — נותרו <bdi dir="ltr">3</bdi>" |
| Queue row | filename `dir="auto"` (Latin filenames are the norm, Hebrew ones happen), size `<bdi dir="ltr">3.2MB</bdi>`, state word. `--text-sm`, `padding-block: var(--space-2)`, `border-block-end: 1px solid var(--color-border)`. Five states, exactly as spec: `ממתין` · `מעלה…` · `מאמת…` · `הועלתה` (`--color-success`, 5.56 ✓) · `נכשלה — {reason}` (`--color-danger`, 6.18 ✓) + `Button secondary` "נסי שוב" |
| Progress | **no percentage bar.** `fetch` exposes no upload-progress event and F8 adds no XHR uploader. Uploads are sequential, so exactly one row is ever non-terminal; the queue itself plus the polite `role="status"` summary is the progress affordance — "מעלה <bdi>3</bdi> מתוך <bdi>8</bdi>" while running, and **the same region reports the terminal counts on drain** ("הועלו <bdi>1</bdi> מתוך <bdi>3</bdi> · <bdi>2</bdi> נכשלו"). A progress region that stops at the last "מעלה…" leaves every failure silent |
| Thumbnail | `<li>` in an `<ol>`. Box: `aspect-ratio: 3/4`, `background: var(--color-surface)` (cream matting), `border-radius: var(--radius-md)`, `box-shadow: var(--shadow-sm)`, `overflow: hidden`; `<img style="object-fit:cover">` `alt="{dress.name} — תמונה {i+1}"` (spec). **This is the storefront's exact framing** — the owner sees the real catalog crop before publishing, which is the only place that verification can happen |
| Ordinal chip | small `Badge` at `inset-block-start: var(--space-2); inset-inline-start: var(--space-2)`, `<bdi dir="ltr">2</bdi>` — the anchor that makes "הזזת תמונה 2 קדימה" a resolvable instruction |
| Primary caption | item 1 only: "תמונה ראשית (מוצגת בקטלוג)", `--text-xs`, `var(--color-gold-text)` weight 600 (5.08 on paper — §10.2). The one place gold touches text here, and it is the legal gold |
| Reorder buttons | `↑` `↓`, 44×44, `Button secondary`. `aria-label="הזזת תמונה 2 אחורה"` / `"הזזת תמונה 2 קדימה"` (spec). First item's `↑` and last item's `↓` are `disabled`. Glyph is `aria-hidden`; the label carries the meaning. **RTL note**: reorder is a list-position operation, not a spatial one — `↑`/`↓` are used precisely because they are direction-neutral in RTL, where `←`/`→` invert |
| Primary action | "קבעי כתמונה ראשית" (spec), on every item **except** item 1. Text `Button ghost`, `--color-gold-text` (5.08:1 on the paper Card), ≥44px block size, `aria-label="קבעי כתמונה ראשית — תמונה {i}"`. Implemented as `PUT /media/order` with that id at index 0 |
| Delete | `Button ghost-danger` "מחיקה", `aria-label="מחיקה — תמונה 2"`; opens a focus-trapped `Modal`: "למחוק את התמונה?" / "לא ניתן לשחזר תמונה שנמחקה." / [ביטול] [מחיקה] |
| Live regions — **exactly two, and the queue summary is terminal** | (1) A **polite `role="status"`** shared by the reorder result ("התמונה הועברה למקום <bdi>3</bdi> מתוך <bdi>5</bdi>"), the per-photo success line and the **queue summary**. The summary does **not** die at "מעלה <bdi>2</bdi> מתוך <bdi>4</bdi>": when the queue drains it becomes the terminal outcome — "הועלו <bdi>1</bdi> מתוך <bdi>3</bdi> · <bdi>2</bdi> נכשלו" — which is what makes every server-side failure (S3, network, `409 MEDIA_MISMATCH`, `409 MEDIA_NOT_UPLOADED`, `409 MEDIA_LIMIT_REACHED`, `429`) audible. The per-row `נכשלה — …` strings live in `<ul class="queue">`, a **sibling** of the region, so on their own they announce nothing. (2) One **assertive `role="alert"`**, rendered above the queue, for the single event that produces no request and no focus move: client-side batch rejection — "<bdi>2</bdi> קבצים לא צורפו — פרטים ברשימה למטה". **Two regions, not three**: §10.3's one-region-per-discrete-event rule is what keeps the announcements from overlapping, and the running/terminal counts are one continuous event stream on one region |
| Drag-and-drop | **not in v1.** ↑/↓ buttons are the reorder affordance (spec: IS 5568 is a legal floor and drag is the least accessible reorder pattern). If drag is ever added it is an enhancement *layered over* the buttons, which must remain |

### 5.5 States

| State | What the owner sees | Trigger |
|---|---|---|
| **Default** | counter + input + guidance + gallery `<ol>` | ≥1 ready photo |
| **Loading** | 3 `Skeleton` 3:4 blocks in the grid | detail fetch |
| **Empty** | `EmptyState` in the Card: "אין עדיין תמונות לשמלה הזו." + "התמונה הראשונה תהיה התמונה הראשית בקטלוג." The file input and the guidance line sit **above** it — the fix precedes the description of the problem | `media == []` |
| **Uploading** | queue rows + the polite summary reading "מעלה <bdi>2</bdi> מתוך <bdi>4</bdi>"; the gallery below stays interactive (the owner can reorder existing photos mid-upload) | queue non-empty |
| **Batch partly rejected before any request (announcement)** | **`role="alert"`, assertive, rendered above the queue: "<bdi>2</bdi> קבצים לא צורפו — פרטים ברשימה למטה".** This is the one failure with **no request and no focus move** — rejection is instantaneous on file selection and focus is still standing in the file input — so §10.3's binding rule applies verbatim: an error that appears without an accompanying focus move must be in an assertive live region. Without it a blind owner selects four photos, two are silently dropped for HEIC/>10MB, and she believes all four uploaded. The count goes in the alert; the per-file reasons stay in the rows | ≥1 file fails `validateUploadFile` |
| **Pre-validation error (client, before any request)** | the file never leaves the browser. Per-file reason in its queue row: type → "HEIC אינו נתמך. שמרי כ-JPG" / "סוג הקובץ אינו נתמך — JPG, PNG או WebP בלבד"; size → "הקובץ גדול מ-10MB"; count → the slot precheck line. **No "נסי שוב" on these rows** — the same file fails identically. Valid files in the same batch continue, and the batch is announced by the row above | `validateUploadFile` |
| **Queue drained (announcement)** | the **same** polite summary that carried the running count switches to the terminal outcome: "הועלו <bdi>1</bdi> מתוך <bdi>3</bdi> · <bdi>2</bdi> נכשלו". This is what makes every server-side failure below audible — the per-row `נכשלה — …` strings sit in `<ul class="queue">`, a sibling of the region, and announce nothing on their own. One region reused, not a third region added | last non-terminal row resolves |
| **Upload failure (S3 / network)** | row shows "נכשלה — העלאת הקובץ נכשלה. נסי שוב." (non-2xx) or "נכשלה — לא ניתן היה להעלות את הקובץ. בדקי את החיבור ונסי שוב." (rejected fetch / CORS). The client **deletes the pending row** so the slot is released immediately, then offers "נסי שוב" — `aria-label="נסי שוב — {filename}"`, never a bare "נסי שוב" (§5.4) — which re-runs the full presign → POST → confirm cycle. The rest of the queue keeps going; the failure reaches the owner through the terminal summary | non-ok / rejected |
| **Verification failure** | "נכשלה — הקובץ אינו תמונה תקינה." (`409 MEDIA_MISMATCH`) / "נכשלה — הקובץ לא הגיע לשרת. נסי שוב." (`409 MEDIA_NOT_UPLOADED`). Never surfaces an S3 XML body or an AWS string. Retry button named per filename; counted in the terminal summary | confirm 409 |
| **Cap race** | "הגלריה מלאה. ייתכן שהעלאות שנכשלו עדיין תופסות מקום — רענני את העמוד ונסי שוב." (spec verbatim). Counted in the terminal summary | `409 MEDIA_LIMIT_REACHED` |
| **Throttled** | "יותר מדי העלאות בזמן קצר. נסי שוב בעוד כמה דקות." Counted in the terminal summary | `429` |
| **Storage disabled** | §5.2 — calm `role="status"` notice; input disabled with the reason on the visible label; **everything else in the editor stays usable** | `media_uploads_enabled === false` or any media 503 |
| **Storage unavailable** | same calm treatment, different copy: "אחסון התמונות אינו זמין כרגע. התמונות שכבר הועלו מוצגות כרגיל." The pending row is left untouched server-side and remains confirmable | `503 MEDIA_STORAGE_UNAVAILABLE` |
| **Signed-URL expiry** | one `<img onError>` triggers exactly one `GET /manage/dresses/{id}` per gallery mount (`hasRefreshedRef`); if it still fails, that tile renders the no-photo placeholder rather than a broken-image glyph and no further refetch is attempted | 15-min TTL elapsed |
| **Success** | the new thumbnail appears at the end of the `<ol>` and the counter increments. Announcement, on the one shared polite region: a **single-file** batch announces "התמונה נוספה. <bdi>6</bdi> מתוך <bdi>12</bdi>"; a **multi-file** batch does not announce per file (that would be one interruption per photo) — it carries the running "מעלה N מתוך M" and then the terminal "הועלו N מתוך M · K נכשלו". Terminal queue rows clear 4s after the queue drains | confirm 200 |
| **Reordering** | optimistic swap, focus retained (§8.4); `MEDIA_ORDER_MISMATCH` → silent refetch + `Toast` "הסדר עודכן מחדש" | ↑/↓ / set-primary |

---

## 6. Edge cases (cross-screen, required set)

| Edge case | Where it shows | Treatment |
|---|---|---|
| **Very long Hebrew dress name** (up to 200 chars) | list row | clamped to 2 lines (`-webkit-line-clamp: 2`, `overflow: hidden`); the full string remains the button's accessible name. **No `title` attribute** — unreachable on touch, and the editor shows it in full |
| **Long name + `reserved` together** (the compound case) | list row | ```+------+ שמלת כלה נסיכותית עם מחוך…``` / ```| 3:4 | (הוזמן)``` / ```+------+ 15,800 ₪ · במלאי (2) · 12 תמונות``` — the "הוזמן" chip is a **sibling of the clamped name on its own line**, so the clamp cannot swallow it. Rev 1 nested the chip inside the clamp box and this exact row lost its status visually while keeping it in the accessible name — a sighted-only failure that an SR-only review pass cannot catch. §2.3 "Status-chip line" is the binding rule |
| | editor heading | wraps freely, never clamped; `overflow-wrap: anywhere` so an unbroken 200-char run cannot widen the 720px column |
| | archive `Modal` | dress name truncated to ~40 chars + `…` in the question line; the Modal is a confirmation, not a display surface |
| **60+ dresses** | list | paged at `DRESS_LIST_DEFAULT_LIMIT = 24`. Count line **above and below** the list (24 rows is a long scroll; the owner must be able to page without scrolling back up). `loading="lazy"` on every cover — this is the heaviest egress path in v1 (unprocessed originals, spec Risk 3). No infinite scroll: it makes "where was I" unanswerable and breaks the back-from-editor focus return |
| **Dress with no photos** | list row | monogram placeholder art (`aria-hidden`), the storefront's "no photo" dignity applied at 72px |
| | meta line | "אין תמונות" |
| | gallery | empty state (§5.5) |
| **A single photo** | gallery | the ↑/↓ cluster and "קבעי כתמונה ראשית" are **hidden entirely**, not rendered disabled — a control that can never be enabled is noise. Only "מחיקה" remains. This matches `storefront-dress-detail.md`'s "single photo → gallery chrome hidden entirely" |
| | primary caption | still shown ("תמונה ראשית (מוצגת בקטלוג)") — it is a statement of fact, not a control |
| **Exactly at cap (12/12)** | counter | "<bdi>12</bdi> מתוך <bdi>12</bdi>" in `--color-warning-text`/600 + copy "הגלריה מלאה" |
| | file input | `disabled`, with "לא ניתן להוסיף — יש למחוק תמונה כדי לפנות מקום" on the **visible label** (never on the disabled control alone) |
| | after a delete | input re-enables, counter repaints, `role="status"` announces "התפנה מקום לתמונה נוספת" |
| **Zero variants** | list stock badge | "לא הוגדרו מידות" (neutral) — **not** "אזל מהמלאי". Without this a boutique entering 60 dresses before touching a size matrix sees a full page of red-flavoured warnings on brand-new work (spec) |
| | matrix | empty state with the quick chips first in the tab order |
| **Price null + `price_visible` true** | preview line | "בקטלוג יוצג: מחיר בתיאום" — valid, and the preview is the only place the owner reads that outcome at write time (spec edge case 14) |
| **Archived dress opened** | editor | read-only view with the "בארכיון" badge; only "שחזור" is enabled |
| **Repeat archive / restore (404)** | either | treated as "already done" — the row leaves/joins the list silently. No error toast (spec edge case 15) |
| **Mixed price visibility in one list** | rows | the price slot has a fixed block size, so a "מחיר בתיאום" row and an "8,900 ₪" row are the same height — the storefront's no-jump rule applied to the console |

---

## 7. Responsive

| Width | Behaviour |
|---|---|
| **375** | console tabs → stacked accordion (unchanged from `manage-restyle.md`; five headers re-checked in §1.1). **The accordion header is the section `<h2>`, so the in-panel "שמלות" heading is not rendered and the editor's headings cascade one level (§1.1)** — a visible change at this width, not only a semantic one. Page gutters `--space-4`; Card padding `--space-4`. Toolbar stacks: search → filters → full-width "שמלה חדשה". List rows: cover 64×85, name clamps 2 lines, meta wraps to 2 lines, row is one full-bleed button. Save buttons full-width. Variant rows stack (label line, then stepper + remove line). Media grid **2-col**, control cluster wraps to two rows. Every interactive target ≥44×44 |
| **768** | tab row appears; content column caps at 720px; page gutters `--space-6`. List rows single-line meta, cover 72×96. Variant rows single-line. Media grid **3-col**. Save buttons return to inline-end, auto width |
| **1440** | **identical to 768** — the console never exceeds 720px of content (`manage-restyle.md`). Only the page gutters grow to `--space-12` and the column centres. There is deliberately **no** wide two-pane catalog layout: a 720px master–detail split leaves the editor ~340px, and the storefront is where photography gets space |

Touch: every button, chip, checkbox, stepper and file control is ≥44×44 at 375 (usage law 7). The list row is far larger; its hit area is the whole row including the cover.

---

## 8. Interaction & keyboard model

### 8.1 Catalog list

- **Tab order** = visual order: **skip link ("דילוג לתוכן העמוד") →** tab strip → search → "הוזמנו בלבד" → "ארכיון" → "שמלה חדשה" → row 1 → row 2 → … → הקודם → הבא. The skip link is the first stop on every screen and targets the content column; **that target carries `tabindex="-1"`** (§10.3) — a `<div>` is not focusable by default, and without it Safari/VoiceOver scrolls but leaves focus standing on the link, so the next Tab walks straight back into the nav the owner just skipped.
- **Row activation**: `Enter` / `Space`. On open, focus moves to the editor's **dress-name heading** with `tabindex="-1"` — `<h2>` at ≥768, `<h3>` at ≤767 per §1.1's mobile heading ruling — and the owner hears where they landed. There is exactly one candidate at either width, because the section heading is never rendered twice.
- **Return**: the back-link, `Esc` (when no Modal is open) and a successful archive all return to the list and **restore focus to the row button that opened the editor**, by a ref keyed on `dress.id`. If that row no longer exists (archived), focus goes to the row that took its position, or to "שמלה חדשה" if the list is now empty. Focus never drops to `<body>`.
- **Search**: 300ms debounce, `offset` resets to 0. Result count announced politely after the debounce settles, never per keystroke.
- **Filters**: `archived` and `הוזמנו בלבד` each reset `offset` and re-announce the count.
- **Paging**: `הקודם`/`הבא` are `disabled` at the ends (never hidden — a disappearing control is a moving target). After a page change, focus moves to the count line (`tabindex="-1"`) and it is announced. **Both count lines carry `tabindex="-1"`** (above and below the list — either can be the focus destination depending on which pager was used); **only the upper one is the polite `role="status"`**, and it is the same region the search result count uses, so the list screen has exactly one polite region and a page change is never spoken twice.

### 8.2 Dress form

- Standard form order, labels above fields. `Enter` in any single-line field submits.
- On a failed client validation, focus moves to the first invalid field; its message is `aria-describedby`-tied and `aria-invalid="true"` is set.
- The preview **announces on discrete events only**: the `price_visible` toggle changing, and the price input's `change`/`blur` — **never its `input` event**. A keyboard-only owner hears "בקטלוג יוצג: מחיר בתיאום" the moment the toggle flips, and hears the resolved amount once when she leaves the price field — not once per digit. The visible preview line updates immediately either way; the live region is a `VisuallyHidden` sibling (§3.4), because a node that repaints per keystroke cannot also be the thing that speaks per event.
- Archive `Modal`: focus trapped, initial focus on **ביטול** (the safe choice), `Esc` closes, focus returns to the archive button. Confirm → list + focus per §8.1.

### 8.3 Variant matrix

- **Quick chip**: adds the row and moves focus to **that row's quantity input** — the owner's next action is typing a quantity, and the chip's own state has already changed, so leaving focus on it would be a dead stop. The chip takes the **listed** treatment and stays **enabled**; its accessible name becomes `aria-label="38 — כבר ברשימה"` (it is **not** `aria-pressed` — see §4.3's ruling: a toggle-button role would promise that a second press un-presses, which is precisely what does not happen here). Pressing it again does not duplicate — it moves focus to the existing row and announces "מידה 38 כבר ברשימה — המיקוד עבר לשדה הכמות". A chip that disables on use would destroy focus.
- **Custom size**: `Enter` in the input = "הוספה". A duplicate keeps focus in the input with its text intact and renders the inline error.
- **Remove**: after removal focus moves to the next row's remove button; if it was the last row, to the custom-size input. Announced: "מידה 38 הוסרה".
- **Steppers**: the number input handles `↑`/`↓` natively; the `−`/`+` buttons are convenience with explicit per-size `aria-label`s. `−` is `disabled` at 0.
- Saving disables every control in the Card, not just the button.

### 8.4 Image manager — the reorder contract

This is the accessibility-critical part. **Drag-only would fail the bar; ↑/↓ buttons are required and are the primary path.**

1. Activating `↑` or `↓` swaps the item optimistically and issues `PUT /media/order`.
2. Focus is **restored to the same logical button** on the moved item, resolved through a ref keyed on `media.id` — not on index, which has just changed under it.
3. **If that button is now `disabled`** (the item reached an end of the list), focus moves to its sibling in the same cluster (`↑`→`↓`, `↓`→`↑`). This is the case naive button-reordering gets wrong, and it is what makes button reorder worse than drag when it is missed.
4. The shared polite `role="status"` announces "התמונה הועברה למקום <bdi>3</bdi> מתוך <bdi>5</bdi>".
5. On error the swap rolls back; on `MEDIA_ORDER_MISMATCH` the gallery refetches and announces "הסדר עודכן מחדש".

Other rules: "קבעי כתמונה ראשית" moves the item to index 0 and then focuses the **new item 1's** delete button (its ↑ is now disabled and its "set primary" action no longer exists — focus cannot stay on a control that has been removed from the DOM). Delete confirm returns focus to the previous item's `↑`, or to the file input if the gallery is now empty. After a batch upload completes, focus stays wherever the owner left it — the queue is `role="status"`, never a focus grab.

---

## 9. Motion

Inherits the shared motion plan (`design-system/README.md`). Catalog-specific:

| Element | Animation | Duration / ease |
|---|---|---|
| List ↔ editor swap | fade + 8px rise on the incoming panel | `--motion-base` / `--ease-out` |
| Row hover | `background` transition | `--motion-fast` |
| Thumbnail image | fade-in on load | `--motion-base` |
| Skeletons | pulse, 1.5s loop | — |
| Modal | scale 0.97→1 + fade; backdrop fade | `--motion-base` / `--motion-fast` |
| Toast | slide from block-start + fade | `--motion-slow` |
| **Thumbnail reorder** | **none — the swap is instant.** A moving thumbnail competes with the `role="status"` announcement during a keyboard reorder and makes the operation feel unfinished. Only the ordinal chip cross-fades at `--motion-fast` | — |

`prefers-reduced-motion: reduce` ⇒ every transition above becomes `none`, skeletons go static. Nothing bounces, nothing spins except a spinner, nothing autoplays.

---

## 10. Accessibility (IS 5568 = WCAG 2.0 AA — a floor, not a target)

**The prototype's own chrome is held to these same bars.** `prototype.html`'s screen-switcher bar is not part of the product, but it is the artifact F9 opens first and it is operated by the same people during review: its buttons meet the 44px touch floor, and because that bar is `--color-ink`, the global `--color-focus` ring (2.74:1 against it) is re-coloured to `--color-bg` on that bar only (15.24:1). A demo harness that fails the bars the document sets teaches the wrong default.

### 10.1 Contrast ledger — every pair this design relies on

**Rev 2: every row below was recomputed from the hex values, against the surface the pair actually renders on** — not transcribed from `tokens.md`. Rev 1 copied the token table and inherited three wrong background attributions plus one figure that could not be reproduced at all (`--color-border-input`); a ledger that lists the wrong surface is how a false ≥3:1 claim survives review. Where a recomputed figure disagrees with `tokens.md`, the correction is queued in §12 and the **recomputed figure governs**.

| Element | Foreground | Background | Ratio | Note |
|---|---|---|---|---|
| Dress name, field labels, headings, price value | `--color-ink` | `--color-surface` (paper) | **13.89:1** | matches tokens.md |
| Same on the page background | `--color-ink` | `--color-bg` (cream) | **15.24:1** | matches tokens.md |
| Primary buttons ("שמלה חדשה", "שמירה", "שמירת מלאי") | `--color-ink` | `--color-gold` | **6.41:1** | gold as *background* only — usage law 1 |
| Meta line, help text, counters, "מחיר בתיאום", saved cue, create-mode hint | `--color-ink-muted` | `--color-surface` | **5.61:1** | matches tokens.md |
| Same on cream (count line, page-level text) | `--color-ink-muted` | `--color-bg` | **6.15:1** | matches tokens.md |
| Storage-notice body (notice fill is now white) | `--color-ink-muted` | `--color-surface-raised` | **6.36:1** | §5.2 |
| Storage-notice lead | `--color-ink` | `--color-surface-raised` | **15.75:1** | recomputed (rev 1 said "≥13.89 by monotonicity" — true but imprecise) |
| Badge text, `muted` variant: "במלאי (N)", "לא הוגדרו מידות", **"בארכיון"** | `--color-ink-muted` | `--color-surface-raised` | **6.36:1** | "בארכיון" is deliberately the muted variant, **not** identical to "הוזמן" — see §2.3. Rev 1's ledger claimed they shared one pairing; the prototype always rendered them differently |
| Badge text, default variant: **"הוזמן"** | `--color-ink` | `--color-surface-raised` | **15.75:1** | byte-identical to the passed storefront `Badge` |
| Badge text, `warning` variant: "אזל מהמלאי" | `--color-warning-text` | `--color-surface-raised` | **5.90:1** ‡ | §10.2 |
| At-cap counter "12 מתוך 12 · הגלריה מלאה" | `--color-warning-text` | `--color-surface` | **5.20:1** | **corrected** — rev 1 attributed this to `--color-surface-raised` (5.90). The counter sits in the Card header, i.e. on paper |
| Derived-אזל hint line, unsaved marker, near-cap char counter | `--color-warning-text` | `--color-surface` | **5.20:1** | matches tokens.md |
| Inline field errors, "נכשלה — …", ghost-danger buttons | `--color-danger` | `--color-surface` | **6.18:1** | matches tokens.md |
| Same on cream (Toast on page bg) | `--color-danger` | `--color-bg` | **6.78:1** | matches tokens.md |
| "הועלתה", success Toast | `--color-success` | `--color-surface` | **5.56:1** | matches tokens.md |
| **Back-link ("חזרה לרשימת השמלות")** | `--color-gold-text` | `--color-bg` (cream) | **5.57:1** | **corrected in rev 4.** The back-link sits in the content column *outside* every Card, so its background is the cream page, not paper. Rev 3 filed it under the paper row (5.08) — the pair passed either way, but the ledger named a surface the control never renders on, which is the exact defect §10.1's rev-2 rewrite exists to prevent. Matches tokens.md |
| **"תמונה ראשית (מוצגת בקטלוג)", "קבעי כתמונה ראשית"** | `--color-gold-text` | `--color-surface` (paper) | **5.08:1** ‡ | §10.2. These two *are* inside the תמונות Card — the paper figure is theirs |
| **Listed-chip `•` marker** (rendered text, `--text-sm`) | `--color-gold-text` | `--color-surface-raised` (the listed chip's own fill) | **5.76:1** ‡ | §10.2. Rev 1 used `--color-gold-strong` here, contradicting this section's own "never below 24px" claim |
| Active-tab underline (non-text) | `--color-gold-strong` | `--color-bg` | **3.80:1** ✓ | the tab strip sits on cream |
| Listed-chip border (non-text) — two neighbours, both stated | `--color-gold-strong` | `--color-surface` (paper Card, outside) / `--color-surface-raised` (chip fill, inside) | **3.47:1** / **3.93:1** ✓ | **corrected** — rev 1 cited 3.80 against cream; the chip is inside a paper Card |
| Input / chip / stepper / file-input / secondary-button borders (non-text) | `--color-border-input` **at the corrected `#8A7A5E`** | `--color-surface` / `--color-surface-raised` / `--color-bg` | **3.69 / 4.18 / 4.04** ✓ | **corrected.** The rev-1 token `#B9A98F` computes **2.03 / 2.30 / 2.22** — it never met ≥3:1, and `tokens.md` line 27 publishes "≥3:1 ✓ (computed 3.0+)", a number that cannot be reproduced. §12 item 3a |
| **Storage-notice boundary (non-text)** | `--color-border-input` **at `#8A7A5E`** | `--color-surface` (the paper Card it sits in) / `--color-surface-raised` (its own white fill) | **3.69 / 4.18** ✓ | **new in rev 3.** The white fill alone is **1.13:1** against paper and the old `--color-border` hairline **1.22:1** — neither is an edge. The notice is the one block whose entire job is to read as a distinct block, so its boundary is load-bearing and takes the ≥3:1 token. §5.2 |
| Batch-rejection alert ("2 קבצים לא צורפו…") | `--color-danger` | `--color-surface` | **6.18:1** | same pairing as the inline field errors; the alert sits in the paper תמונות Card |
| Focus ring (2px, 2px offset, non-text) | `--color-focus` | `--color-bg` / `--color-surface` / `--color-surface-raised` | **5.57 / 5.08 / 5.76** ✓ | **corrected** — rev 1 copied `tokens.md` line 31's 4.86. `--color-focus` is byte-identical to `--color-gold-text` (`#7F612B`), which the same table lists at 5.57 on the same background; `tokens.md` publishes two ratios for one hex. §12 item 3c |
| Card hairlines, row dividers, badge outlines | `--color-border` | — | decorative, non-text (1.22 on paper) | **never a load-bearing boundary.** Where a block's edge must be perceivable, the fill changes instead (§5.2) |
| Cover / thumbnail matting | `--color-surface` | — | decorative | — |
| Monogram + dress placeholder art | `--illus-1/2/3`, `--color-gold` | `--color-surface` | exempt — `aria-hidden` decorative art | — |

**Never used in this design**: raw `--color-gold` on text (2.38:1 — usage law 1); `--color-gold-strong` on text at *any* size in this feature (its only two uses are the active-tab underline and the listed-chip border, both non-text boundaries — the listed-chip `•`, which *is* text, takes `--color-gold-text`); `opacity` as a way to recess text (§3.3); any colour not in `tokens.md`.

### 10.2 The two computed pairs (‡)

`tokens.md` publishes `--color-gold-text` on **cream** (5.57:1) and `--color-warning-text` on cream (5.70:1) and on paper (5.20:1). This design additionally needs **gold-text on paper** (Card interiors) and **warning-text on surface-raised** (badge fills). Both are computed with the same WCAG relative-luminance method `tokens.md` used, and the method is validated by reproducing its published figures exactly:

| Pair | Computed | Method check |
|---|---|---|
| `--color-gold-text #7F612B` on `--color-surface #F6F0E6` | **5.08:1** ✓ (≥4.5) | the same computation on `--color-bg #FDFBF7` returns **5.57:1**, matching tokens.md's published value |
| `--color-warning-text #8A5A1E` on `--color-surface-raised #FFFFFF` | **5.90:1** ✓ | the same computation on `--color-bg` returns **5.70:1**, matching tokens.md |
| `--color-gold-text #7F612B` on `--color-surface-raised #FFFFFF` (listed-chip `•`) | **5.76:1** ✓ | same method; the listed chip's fill is white |

All three pass AA for normal text with margin. **Action for F9**: add these rows to `tokens.md`'s verified-pairs table — the passed `design-system/prototype.html` already ships gold-text on paper (`.version-row .current`) without a listed ratio, so this closes an existing documentation gap rather than opening a new one.

### 10.2b Two `tokens.md` figures that do not reproduce (rev 2 finding)

Recomputing the ledger surfaced two published numbers that are wrong, not merely under-specified. Both are queued in §12; **the F9 build must not ship against the published values.** The first of the two (`--color-border-input`) is a **gate condition on the F9 build start** — see §12 item 3a for the remedy and the blast radius. Neither is an F8 defect: `tokens.md` is F9's file and has passed its own gate, so this document escalates rather than edits.

| tokens.md | Published | Recomputed | Consequence |
|---|---|---|---|
| line 27 — `--color-border-input #B9A98F` | "≥3:1 on surfaces ✓ (computed 3.0+)" | **2.03** paper · **2.30** white · **2.22** cream | Fails the ≥3:1 non-text-boundary bar this brief sets and WCAG 2.1 SC 1.4.11 (WCAG 2.0 AA — the literal IS 5568 floor — has no non-text-contrast SC, so this is not strictly an IS 5568 violation; it is a failure of our own stated bar). Affects the search input, name input, description textarea, price input, sort-order input, unlisted size chips, quantity stepper inputs, the file input **and (rev 3) the storage-disabled notice's boundary**. These controls have no fill contrast against the white/paper behind them either, so the hairline was the only thing saying "this is a field". **Fix: darken the token to `#8A7A5E`** → 3.69 / 4.18 / 4.04. Do **not** paper over it by reusing `--color-gold-strong #9E7B36` (3.47 on paper — it passes) as the resting border: that makes every field gold and collides with the listed-chip signal in §4.3 |
| line 31 — `--color-focus #7F612B` | 4.86 on cream | **5.57** on cream | `#7F612B` is byte-identical to `--color-gold-text`, which line 14 of the same file lists at 5.57 on the same background. One hex, two published ratios. Nothing fails — the figure is simply wrong and rev 1 copied the wrong one |

### 10.3 Checklist

- [x] **Contrast** — every text pair ≥4.5:1 per §10.1, **recomputed in rev 2 against the surface each pair actually renders on**; every non-text boundary (`gold-strong` 3.47–3.93, corrected `border-input` 3.69–4.18, focus ring 5.08–5.76) ≥3:1
- [x] **No opacity on text, ever** — a disabled *pane* is forbidden. Recession is carried by the `disabled` controls (WCAG-exempt); headings, hints and counters render at full token colour. §3.3 shows why no opacity value can be tuned into compliance for `--color-ink-muted` on paper
- [x] **Every block boundary that carries meaning is perceivable** — where a block must read as a distinct block (the storage notice) the fill changes **and** the boundary is `--color-border-input` at ≥3:1 (3.69 on paper / 4.18 on its own white fill). A `--color-border` hairline (1.22:1) is decorative and is never the only thing delimiting a region — and neither is a white-on-paper fill change (**1.13:1**), which is why rev 2's fill-only remedy was not enough on its own
- [x] **Gold law** — gold never carries text; `--color-gold-text` is the only gold on text (back-link, primary-photo caption, listed-chip `•`); `--color-gold-strong` appears on **zero** text in this feature — only the active-tab underline and the listed-chip border, both non-text boundaries; raw `--color-gold` appears only as button background (with ink text, 6.41:1), as the preview line's decorative border stripe, and inside `aria-hidden` placeholder art
- [x] **No colour-only signals** — the three-way stock state is three different *words*; the at-cap counter changes copy as well as colour; the listed chip gains a `•` marker as well as a border **and says "כבר ברשימה" in its accessible name**; the queue states are words
- [x] **No ARIA that promises behaviour the control does not have** — no `role="tab"` on a strip that is five sequential Tab stops (§1.1); no `aria-pressed` on a quick-size chip whose second press does not un-press (§4.3). Both are the same defect class, resolved the same way: drop the role, carry the state in the accessible name
- [x] **No generated content inside an accessible name** — redundant markers are real `aria-hidden` elements, never `::before{content:…}`, because Chrome and Firefox fold generated content into the computed name (the listed-chip `•`)
- [x] **Labels** — every input, chip, stepper, file input and filter has a **visible** label; placeholder is never the label (usage law 3). Icon/glyph-only buttons (`↑ ↓ − +`) carry explicit per-item `aria-label`s naming the size or the photo ordinal. **Every per-item control in the תמונות Card — gallery items *and* queue rows — carries its item's identity in its accessible name**: the ordinal for gallery controls (including the text-labelled "קבעי כתמונה ראשית", where four identical names would be unnavigable from a buttons list) and the **filename** for queue retry buttons
  - **Where a control has visible text, its accessible name must BEGIN with that text verbatim; the disambiguator is appended after an em-dash, never substituted (WCAG 2.5.3 Label in Name).** Rev 3 wrote the disambiguated names as gerunds with the identity spliced mid-string — visible "הסרה" vs name "הסרת מידה 36", "מחיקה" vs "מחיקת תמונה 2", "קבעי כתמונה ראשית" vs "קביעת תמונה 2 כתמונה ראשית", "נסי שוב" vs "ניסיון חוזר להעלאת IMG_5002.jpg". None of those contains the visible label as a substring, so a voice-control owner saying the word she can see matches nothing and **cannot operate remove, delete, set-primary or retry at all**. The binding shape is the one the disabled add button already used: `aria-label="הסרה — מידה 38"`, `"מחיקה — תמונה 2"`, `"קבעי כתמונה ראשית — תמונה 2"`, `"נסי שוב — IMG_5002.jpg"`, `"הוספה — הגעת ל-60 מידות"`. Icon-only controls (`↑ ↓ − +`) have no visible text and are unaffected
  - **A visible label is never overridden by `aria-label`.** Where the label is rendered as text next to the control (the variant row's "כמות" span), the control takes `aria-labelledby` pointing at that visible node — plus the already-visible size chip — so the name is "כמות 38" and the visible words are inside it. `aria-label` there would replace the visible label with a string the owner cannot see
- [x] **Errors** — `aria-invalid="true"` + `aria-describedby` to the inline message; focus moves to the first invalid field on submit. **Rule: an error that appears *without* an accompanying focus move must be in an assertive live region (`role="alert"`) as well** — screen readers announce `aria-describedby` when focus *arrives* at a control and do not reliably re-announce it when the referenced node changes under standing focus. Applies to the duplicate-size error, the variant-cap message (§4.5) **and the client-side batch-rejection summary in the upload queue (§5.5)** — that last one is the case rev 2 stated the rule for and then did not apply. Errors reached *by* a focus move need only `aria-describedby`. **`aria-describedby` on a `disabled` control is inert** and is never the carrier of a reason — the reason goes on the visible label (see below)
- [x] **Heading outline** — at ≥768: `h1` console title → `h2` open section / dress name → `h3` Card headings → `h4` empty states inside a Card that has an `h3`. At ≤767 the accordion header **is** the section `h2`, the in-panel section heading is suppressed, and the editor cascades one level down (`h3` dress name → `h4` Cards → `h5` Card-internal empty states). No skipped levels and no duplicated section heading at either width; §8.1's focus destination is unambiguous at both (§1.1)
- [x] **Keyboard** — every path in §8 is button-driven. **Image reordering is keyboard-operable by construction**: ↑/↓ buttons are the primary affordance, drag is explicitly not in v1, and the disabled-button focus rule (§8.4 step 3) is a build requirement, not a nicety
- [x] **Focus never lost** — explicit destination specified for every DOM-mutating action: row open, back, archive, chip add, row remove, reorder, set-primary, delete, page change
- [x] **Focus visible** — 2px `--color-focus` ring at 2px offset on every interactive element; `outline: none` without a replacement is a review defect. **`outline` + `outline-offset` and nothing else** — the rule carries no `border-radius` of its own: browsers already draw the ring following the element's own radius, so a fixed 2px there only takes effect where it disagrees with the shape it is tracing (pill chips and badges at `--radius-full`, square-cornered rows at 0)
- [x] **Images** — gallery `alt="{dress.name} — תמונה {i+1}"`; list covers `alt=""` (the name is the adjacent accessible text inside the same button); monogram/dress placeholder art `aria-hidden="true"`
- [x] **Touch targets** — ≥44×44 at 375 for every control, including the wrapped media control cluster, the 14 EU chips, **both `Toggle` rows (the `<label>` wraps checkbox + title and carries `min-block-size: 44px`; the box is 24×24)** and **`::file-selector-button`, where the file input's real hit target lives**
- [x] **Live regions** — one polite `role="status"` per **discrete event**: the price preview (outcome change), the list count line (page change + post-debounce search count, one region for both), the derived-אזל hint (0-crossing), gallery (reorder + queue summary). **The gallery's queue summary is terminal, not just running** — on drain it becomes "הועלו N מתוך M · K נכשלו", which is the only thing that speaks a server-side upload failure (the per-row `נכשלה — …` strings are in a sibling `<ul>` and announce nothing). `role="alert"` is reserved for the danger `Toast` and for errors that appear with no focus move (see Errors above) — in the תמונות Card that is exactly one alert, the client-side batch rejection. **Two regions in that Card, never three.** Never `aria-live="assertive"` on progress
  - **One rule, no exceptions: a continuously-changing value is never itself a live region.** This is not a carve-out for the variant stock total — it governs every value bound to a text or number input in this feature. The **stock total** and the **price preview** are both plain text that repaint immediately and neither is the announcing node: the total's meaningful event is the 0-crossing, which has its own region; the preview's are the `price_visible` toggle changing and the price input's `change`/`blur`, which write a `VisuallyHidden role="status"` sibling. Bound directly to the input, either would announce once per keystroke ("8", "89", "890", "8900"), each announcement interrupting the last, re-reading the whole atomic region, and — on a 60-row matrix — drowning the אזל hint sharing its Card. Where keystroke-driven announcement is genuinely wanted the fallback is the same in both places: debounce ≥500 ms after input settles and suppress the announcement when the resolved string is unchanged since the last one
- [x] **Skip link** — every screen opens with "דילוג לתוכן העמוד" as the first tab stop, targeting the `.console-body` content column. **The target carries `tabindex="-1"`**: it is a `<div>`, so it cannot take focus otherwise, and in Safari/VoiceOver focus would stay on the link while only the scroll position moved — the next Tab then walks back into the nav the owner just asked to skip. The link is visible on focus (`:focus-visible` brings it in from off-screen), never permanently hidden
- [x] **Disabled controls explain themselves** — **every** disabled control in this feature states its reason on its own **visible label**, not on a detached paragraph nearby: the storage-disabled file input ("הוספת תמונות (לא זמין כרגע)"), the at-cap file input, the create-mode file input ("הוספת תמונות (יש לשמור את השמלה תחילה)"), the create-mode quick-size chip group (visible group label, `role="group" aria-labelledby`, **never `aria-hidden`**) **and the whole 60-variant cap cluster** — chip group label "הוספה מהירה (מידות אירופאיות) — הגעת ל-60 מידות", input label "מידה מותאמת (הגעת ל-60 מידות)", add button `aria-label="הוספה — הגעת ל-60 מידות"`. `disabled` removes a control from the tab order, so a screen-reader user reaching it by any other route would otherwise never learn why (spec) — and for the same reason an `aria-describedby` pointing *from* a disabled control is inert and does not count as an explanation
- [x] **Reduced motion** — §9; skeletons static, list/panel transitions none
- [x] **Navigation semantics** — the section strip is a `<nav>` of buttons with `aria-current="page"`, **not** `role="tablist"`/`role="tab"`: the keyboard model is five sequential Tab stops (§8.1), not one arrow-navigated stop, and at ≤767 the same controls are accordion headers, which may never be `role="tab"` (§1.1)
- [x] **RTL** — `lang="he" dir="rtl"` at the document; CSS logical properties throughout, **including sizing (`min-block-size` / `min-inline-size` / `max-inline-size`, never `min-height` / `min-width` / `max-width`)** so the F9 build inherits the convention verbatim from the prototype; LTR islands **only** for the price input, the quantity stepper *control group* (§4.3 ruling), the sort-order number input, file sizes, counts and ranges — each wrapped in `<bdi dir="ltr">` or carrying `dir="ltr"` + `unicode-bidi: isolate` (`Price` does this by construction). `dir="auto"` on the search field, the custom-size field and uploaded filenames, where Hebrew and Latin both occur
- [x] **No promo/sale language anywhere** (usage law 9) — no "חדש!" ribbons, no discount chips, no countdowns, no urgency copy. The catalog console has *zero* promotional surfaces by design

---

## 11. Copy deck (Hebrew, verbatim — F8 implements these strings now)

| Key | String |
|---|---|
| Tab | שמלות |
| New dress | שמלה חדשה |
| Search label | חיפוש שמלה |
| Filters | הוזמנו בלבד · ארכיון |
| Paging | הקודם · הבא · מציג 1–24 מתוך 61 |
| Empty (none) | אין עדיין שמלות בקטלוג · השמלה הראשונה תופיע כאן ובאתר של הבוטיק. |
| Empty (filtered) | לא נמצאו שמלות התואמות לחיפוש. · ניקוי החיפוש |
| Empty (archive) | אין שמלות בארכיון. |
| List error | לא הצלחנו לטעון את השמלות · נסי שוב |
| Stock badges | לא הוגדרו מידות · אזל מהמלאי · במלאי (N) |
| Chips | הוזמן · בארכיון |
| Hidden price | מחיר בתיאום |
| Form fields | שם השמלה · תיאור · מחיר (₪) · סדר בקטלוג |
| Sort help | מספר נמוך = מוצג ראשון |
| Price visibility | הצגת המחיר באתר · כשהאפשרות כבויה, הלקוחות רואות «מחיר בתיאום» במקום הסכום. |
| Preview | בקטלוג יוצג: |
| Reserved | הוזמן · סימון ידני, ללא תאריך — יש להסיר ידנית כשהשמלה מתפנה |
| Create-mode hint | יש לשמור את השמלה לפני הוספת מידות ותמונות |
| Disabled-control labels — the reason on the **visible label** of every disabled control (create mode, variant cap, at-cap gallery, storage disabled) | הוספת תמונות (יש לשמור את השמלה תחילה) · הוספה מהירה (מידות אירופאיות) — יש לשמור את השמלה תחילה · הוספה מהירה (מידות אירופאיות) — הגעת ל-60 מידות · מידה מותאמת (הגעת ל-60 מידות) · הוספה — הגעת ל-60 מידות (`aria-label`) |
| Created | השמלה נוצרה. אפשר להוסיף מידות ותמונות. |
| Save | שמירה · יצירת שמלה · נשמר לפני רגע |
| Archive | העברה לארכיון · שחזור · להעביר את «{שם}» לארכיון? · השמלה תוסר מהאתר. אפשר לשחזר אותה מלשונית «ארכיון». |
| Archived view | השמלה בארכיון — לשחזור לחצי «שחזור». |
| Name collision | כבר קיימת שמלה בשם הזה. אפשר להמשיך. |
| Variants | מידות ומלאי · הוספה מהירה (מידות אירופאיות) · מידה מותאמת · הוספה · כמות · הסרה · שמירת מלאי |
| Remove size (`aria-label`, size required; visible label first, §10.3) | הסרה — מידה 38 |
| Variants total | סה״כ במלאי: N יחידות |
| Variants empty | לא הוגדרו מידות לשמלה הזו. · בחרי מידה מהרשימה המהירה, או הוסיפי מידה מותאמת. |
| Duplicate size | המידה «38» כבר קיימת ברשימה. |
| Quick chip, already listed (`aria-label` — **not** `aria-pressed`; §4.3) | 38 — כבר ברשימה |
| Size already listed | מידה 38 כבר ברשימה — המיקוד עבר לשדה הכמות |
| Variant cap | אפשר עד 60 מידות לשמלה. |
| Derived אזל | כל המידות במלאי 0 — השמלה תסומן «אזל מהמלאי» בקטלוג הניהול. |
| Unsaved | יש שינויים שלא נשמרו |
| Variants saved | המלאי נשמר |
| Media | תמונות · הוספת תמונות · בחירת קבצים… · N מתוך 12 |
| Media guidance | צלמי לאורך (פורטרט). עד 10MB לתמונה · JPG/PNG/WebP · 4–6 תמונות לשמלה מספיקות |
| Media empty | אין עדיין תמונות לשמלה הזו. · התמונה הראשונה תהיה התמונה הראשית בקטלוג. |
| Queue states | ממתין · מעלה… · מאמת… · הועלתה · נכשלה — {סיבה} · נסי שוב |
| Queue retry (`aria-label`, filename required — §5.4; visible label first, §10.3) | נסי שוב — IMG_5002.jpg |
| Queue summary (running, polite `role="status"`) | מעלה 3 מתוך 8 |
| Queue summary (terminal, **same** region, on drain) | הועלו 1 מתוך 3 · 2 נכשלו |
| Batch rejected client-side (`role="alert"`, assertive — no request, no focus move) | 2 קבצים לא צורפו — פרטים ברשימה למטה |
| Slots | ניתן להעלות עד 12 תמונות לשמלה — נותרו 3 |
| At cap | הגלריה מלאה · לא ניתן להוסיף — יש למחוק תמונה כדי לפנות מקום · התפנה מקום לתמונה נוספת |
| Cap race | הגלריה מלאה. ייתכן שהעלאות שנכשלו עדיין תופסות מקום — רענני את העמוד ונסי שוב. |
| Upload errors | העלאת הקובץ נכשלה. נסי שוב. · לא ניתן היה להעלות את הקובץ. בדקי את החיבור ונסי שוב. · הקובץ גדול מ-10MB · HEIC אינו נתמך. שמרי כ-JPG · סוג הקובץ אינו נתמך — JPG, PNG או WebP בלבד · הקובץ אינו תמונה תקינה. · הקובץ לא הגיע לשרת. נסי שוב. |
| Throttled | יותר מדי העלאות בזמן קצר. נסי שוב בעוד כמה דקות. |
| Primary photo | תמונה ראשית (מוצגת בקטלוג) · קבעי כתמונה ראשית |
| Primary photo (`aria-label`, ordinal required; visible label first, §10.3) | קבעי כתמונה ראשית — תמונה 2 |
| Reorder | הזזת תמונה 2 אחורה · הזזת תמונה 2 קדימה · התמונה הועברה למקום 3 מתוך 5 · הסדר עודכן מחדש |
| Delete photo | מחיקה · למחוק את התמונה? · לא ניתן לשחזר תמונה שנמחקה. |
| Delete photo (`aria-label`, ordinal required; visible label first, §10.3) | מחיקה — תמונה 2 |
| Photo added | התמונה נוספה. 6 מתוך 12 |
| Storage disabled | העלאת תמונות עדיין לא זמינה · אפשר להמשיך למלא את פרטי השמלה ואת המידות — התמונות יתווספו מאוחר יותר. · הוספת תמונות (לא זמין כרגע) |
| Storage unavailable | אחסון התמונות אינו זמין כרגע. התמונות שכבר הועלו מוצגות כרגיל. |
| Skip link (first tab stop on every screen; target carries `tabindex="-1"` — §10.3) | דילוג לתוכן העמוד |
| Back | חזרה לרשימת השמלות |
| Required note | שדות המסומנים ב-* הם חובה |

---

## 12. Open items and conflicts (raise before the F9 build starts)

1. **Tab label conflict — `שמלות` vs `קטלוג`.** This document specifies **"שמלות"**. `catalog-management.md`'s frontend table specifies `{ key: "catalog", label: "קטלוג" }`. One of them must be amended (a one-word change in `App.tsx`). **Recommendation: "שמלות".** The console's other tabs name the *object* the owner manages (סוגי תורים, שעות פעילות); "קטלוג" is the storefront's word for the public grid, and reusing it inside the console conflates the two surfaces. The route key stays `catalog`.
2. **"הוזמנו בלבד" has no API parameter.** The spec's `CatalogSection` row specifies a toggle "bound to the `reserved` query param", but the API table for `GET /manage/dresses` lists only `offset`, `limit`, `search`, `archived`. Filtering client-side over one 24-row page would be actively misleading with 61 dresses. **Resolve one of two ways before F8 builds it**: add `reserved: bool | None` to the router signature (cheap — the active partial index already leads with `tenant_id`), or drop the toggle from v1. This document renders it; if it is dropped, delete the control and its copy-deck row.
3. **`tokens.md` corrections — one is blocking.** Rev 2 recomputed every pair the catalog relies on (§10.1, §10.2, §10.2b). Four edits, one PR:
   - **3a — GATE CONDITION ON THE F9 BUILD START. `--color-border-input` must change value in `tokens.md` before F9 begins.** This is **the single largest contrast exposure in the feature** and it is an **escalation into F9's file, not an F8 defect** — `tokens.md` is F9's artifact and has already passed its own gate, so F8 does not edit it and must not be asked to. What F8 owes is an accurate, actionable hand-off, which is this item.
     - **The defect.** `--color-border-input: #B9A98F` computes **2.03:1 on paper / 2.30 on white / 2.22 on cream**, while `tokens.md` line 27 publishes "≥3:1 on surfaces ✓ (computed 3.0+)" — a figure that cannot be reproduced by any method against any of the three surfaces.
     - **The blast radius.** This token is the *sole visible boundary* of nearly every control in F8 — search input, name input, description textarea, price input, sort-order input, unlisted size chips, quantity stepper inputs, the file input and the storage-disabled notice — and of every form in the console beyond it. Those controls have no fill contrast against the white or paper behind them either, so the hairline is the only thing saying "this is a field". Nothing else in this design depends on one token this heavily.
     - **The remedy, specifically.** Change the value to **`#8A7A5E`** → **3.69:1 on `--color-surface` (paper) · 4.18:1 on `--color-surface-raised` (white) · 4.04:1 on `--color-bg` (cream)**, all ≥3:1, and replace line 27's bare "≥3:1 ✓ (computed 3.0+)" with those three per-surface figures. Do **not** paper over it by reusing `--color-gold-strong #9E7B36` (3.47 on paper — it passes) as the resting border: that golds every field in the console and collides with the listed-chip signal in §4.3.
     - **Status until then.** `manage-catalog/prototype.html` already ships the corrected value **under the existing token name** (never as a raw hex), so the artifact F9 copies is correct today and the two files do not silently disagree. **The F9 build must not ship against the published `#B9A98F`.** The change is a token change, not a catalog-local override: `manage-restyle.md`'s four existing sections and `storefront-*`'s inputs inherit it too, and every one of them gets *more* legible.
   - **3b** — add the verified rows this design needs and `tokens.md` does not publish: `--color-gold-text` on `--color-surface` (**5.08:1**) and on `--color-surface-raised` (**5.76:1**), and `--color-warning-text` on `--color-surface-raised` (**5.90:1**). The passed `design-system/prototype.html` already ships gold-text on paper (`.version-row .current`) without a listed ratio, so this closes an existing gap rather than opening one.
   - **3c** — `tokens.md` line 31 lists `--color-focus #7F612B` at 4.86 on cream. Recomputed it is **5.57** — byte-identical to `--color-gold-text`, which line 14 lists at 5.57 against the same background. One hex, two published ratios; line 31 should read 5.57.
   - **3d** — state explicitly in the gold law that `--color-gold-strong` is barred from *rendered text of any kind*, including CSS `content:` glyphs. Rev 1 used it for a 14px `•` while its own ledger claimed it was never used on text below 24px; naming the case closes the loophole.
   - **3e — doc-only.** `tokens.md`'s radius table assigns "inputs, chips" to `--radius-sm` (4px), but chips render as **pills** (`--radius-full`) both here and in the already-passed `design-system/prototype.html`. The rendering is right and consistent with precedent; the usage note is what is stale. Split the row into **"inputs" → `--radius-sm`** and **"chips / badges (pill)" → `--radius-full`**. No value changes, no rendering changes.
4. **`manage-restyle.md` must absorb §1** — five-tab shell, the four new component rows, and the two new console-wide states. Until it does, `manage-restyle.md` describes a four-section console that no longer exists (F8 spec Risk 6).
5. **Prototype token naming.** `manage-catalog/prototype.html` declares custom properties under `tokens.md`'s **canonical** names (`--space-4`, `--text-lg`, `--radius-md`, `--shadow-sm`) so a reviewer can diff them line-for-line. The earlier `design-system/prototype.html` used abbreviations (`--s4`, `--t-lg`, `--r-md`, `--sh-sm`). Harmonise on the canonical names when `packages/ui/src/theme.css` is authored in the F9 build — the `@theme` block is the single source and abbreviations there would break the Tailwind v4 utility names.
6. **Photography guidance is a shipped artifact, not a document.** The upload guidance line is the epic's stated mitigation for having no image processing (spec Risk 3). It must not be shortened during the F9 restyle to make the Card look tidier.
7. **`components.md` needs two named `Badge` variants.** This design uses `muted` (ink-muted text, `--color-border` outline, no shadow — "במלאי (N)", "לא הוגדרו מידות", "בארכיון") and `warning` (`--color-warning-text`/600, outline, no shadow — "אזל מהמלאי", the at-cap counter). Neither is among `components.md`'s four enumerated variants (neutral/ink-tint, gold, success, danger). Add both to the `Badge` row — same PR as item 3, same reviewer, no new work. Both pass AA as text (6.36 and 5.90 on white); the outline is decorative, since the word carries the meaning in every case. **Gate condition (rev 3): this row must land in `components.md` before or with the F9 build that consumes this document** — a build that reads `components.md` as the component contract would otherwise find two variants it is told to render and no definition for either.
8. **`manage-restyle.md` §1.1 must also absorb the navigation-semantics ruling** (plain `<nav>` + `aria-current`, no `role="tab"`; accordion headers get `aria-expanded`/`aria-controls` inside a heading at ≤767) and the heading-outline rule (`h1` console title). `manage-restyle.md` left ARIA unassigned here, and the four existing sections have the same strip.

---

## 13. Revision log

### Round 3 — accessibility critic, 9 findings, **zero HIGH** (2026-07-24) → rev 4

Design-critic ACCEPT stands. All 8 actionable findings are fixed in this document **and** in `prototype.html`; the ninth is an escalation into `tokens.md`, which is F9's already-passed artifact and is therefore **not edited here** — it is re-stated as a gate condition instead. No new colour value was introduced: every fix reuses a token already in `tokens.md`, and a full sweep confirms the prototype still carries zero raw colour outside its `:root` block.

| # | Sev | Finding | Resolution |
|---|---|---|---|
| 30 | **MED** | **WCAG 2.5.3 "Label in Name" failed on every text-labelled button.** The disambiguated names were written as gerunds with the identity spliced mid-string, so the visible word was not a substring of the accessible name at all: visible "הסרה" vs name "הסרת מידה 36"; "מחיקה" vs "מחיקת תמונה 2"; "קבעי כתמונה ראשית" vs "קביעת תמונה 2 כתמונה ראשית"; "נסי שוב" vs "ניסיון חוזר להעלאת IMG_5002.jpg". A voice-control owner says the word she can see and matches nothing — she cannot operate remove, delete, set-primary or retry **at all** | **Every accessible name now begins with the visible label verbatim, disambiguator appended after an em-dash** — the shape the disabled add button already used correctly (`aria-label="הוספה — הגעת ל-60 מידות"`). `"הסרה — מידה 38"` · `"מחיקה — תמונה 2"` · `"קבעי כתמונה ראשית — תמונה 2"` · `"נסי שוב — IMG_5002.jpg"`. Applied to **all 17** such buttons in the prototype, not only the four cited. §10.3's Labels bullet gains the rule; §4.3, §5.1, §5.4, §5.5 and four §11 rows updated. Icon-only controls (`↑ ↓ − +`) have no visible text and are untouched. Verified by substring assertion over the parsed prototype: **109 buttons/links with visible text, 0 failures** |
| 31 | **MED** | The price preview's `role="status"` was wired to both the visibility toggle **and** the price text input, so typing "8900" fired four announcements, each interrupting the last and each re-reading the whole atomic region. This is the defect round 1 finding 13 removed from the variant stock total and §4.3 re-argued: "a continuously-changing value is not a discrete event" | **The doc's own §4.3 ruling applied to the preview.** The visible `.preview` line is plain text and repaints immediately (that is what a preview is for); the announcement moves to a `VisuallyHidden role="status"` sibling written **only on discrete events** — the `price_visible` toggle changing, and the price input's `change`/`blur`, never its `input`. Fallback if keystroke-driven announcement is ever wanted is the one §4.3 already specifies: debounce ≥500 ms after input settles, suppress when the resolved string is unchanged. §3.4's Preview row and §8.2's third bullet amended; §10.3's live-region bullet rewritten so the stock total is **an instance of one rule** rather than a rule plus an unexplained exception |
| 32 | LOW | Skip links targeted `<div class="console-body">` elements with no `tabindex="-1"`. The target cannot take focus, so in Safari/VoiceOver only the scroll position moves and the next Tab returns to the nav just skipped. The link also existed **only** in the prototype — an F9 build reading this document as the contract would have dropped it | `tabindex="-1"` added to all five `.console-body` targets; §10.3 gains a Skip-link row; §8.1's tab order names it as the first stop; "דילוג לתוכן העמוד" added to the §11 copy deck |
| 33 | LOW | `:focus-visible` carried `border-radius:2px` alongside `outline`/`outline-offset` | Declaration deleted. Browsers already trace the element's own radius; the fixed 2px only took effect where it *disagreed* with the shape — pill chips and badges at `--radius-full`, square rows at 0. §10.3's Focus-visible bullet records it |
| 34 | LOW | The quantity input's visible label "כמות" is a bare `<span>`, so `aria-label="כמות במידה 36"` silently **overrode** the visible text rather than including it | Span given an `id`; the input now uses `aria-labelledby="qty-lbl-36 size-36"`, referencing the visible label **and** the already-visible size chip → "כמות 36". Nothing hidden, nothing duplicated. Applied to all five stepper rows. §4.3's stepper row and §10.3's Labels bullet updated |
| 35 | LOW | The prototype's own chrome missed the bars the document sets: `.proto-nav button{min-block-size:32px}` is under the 44px floor (usage law 7), and the global `--color-focus` ring computes **2.74:1** against the `--color-ink` bar | `min-block-size:44px`, and a light ring scoped to that bar only — `.proto-nav :focus-visible{outline-color:var(--color-bg)}` = **15.24:1**. §10 gains a one-line note that the prototype chrome is held to the same bars as the product: it is the first artifact F9 opens, and a demo harness that fails them teaches the wrong default |
| 36 | LOW | §8.1's binding rule "after a page change, focus moves to the count line (`tabindex="-1"`) and it is announced" had no trace in the prototype | `tabindex="-1"` on **both** `.count-line` paragraphs (either pager can be the origin) and `role="status"` on the **upper** one only — it is the same region the post-debounce search count uses, so the list screen keeps exactly one polite region and a page change is never spoken twice. §8.1's paging bullet and §10.3's live-region bullet state which line carries which |
| 37 | LOW | §10.1 filed the back-link's `--color-gold-text` pair under `--color-surface` (paper, 5.08:1), but the back-link renders in the content column *outside* every Card, i.e. on `--color-bg` (cream) | Row **split**: back-link on cream = **5.57:1** (the figure `tokens.md` already publishes); "תמונה ראשית" / "קבעי כתמונה ראשית" on paper = **5.08:1** ‡ (they *are* inside the תמונות Card). §3.4's back-link row corrected to match. Both pairs always passed — the defect was a ledger naming a surface the control never renders on, which is exactly what §10.1's rev-2 rewrite exists to prevent |
| — | ESCALATION | `tokens.md` still ships `--color-border-input: #B9A98F`, whose real contrast (2.03 / 2.30 / 2.22) falls short of the ≥3:1 its own table claims | **Deliberately NOT fixed here.** `tokens.md` is F9's file and has passed its own gate; F8 does not edit it. §12 item 3a was **rewritten as an explicit gate condition on the F9 build start**, carrying the specific remedy (`#B9A98F` → `#8A7A5E`, with the three per-surface figures), the blast radius, the rejected alternative, and the statement that this is **the single largest contrast exposure in the feature** — an escalation, not an F8 defect. §10.2b cross-references it. The prototype continues to ship the corrected value under the existing token name so the artifact F9 copies is correct today |

**Verification pass (rev 4).** The prototype was parsed and every `<button>`/`<a>` with visible text checked by substring assertion — accessible name (`aria-label`, else `aria-labelledby` resolution, else content) must start with the visible text, with `aria-hidden` subtrees excluded: **109 checked, 0 failures**, 20 icon-only controls correctly out of scope. Five `aria-labelledby` idrefs all resolve. Zero external references (`src`/`href` off-document): the file remains self-contained with inline CSS and no frameworks. Hex literals: 19, all inside the `:root` token block plus the two inside the `--color-border-input` correction comment — **no new raw colour**. Physical directional/sizing properties outside media-query features: **zero**.

### Round 2 — two critics, 11 findings (2026-07-24)

The one HIGH and all five MEDIUM findings are fixed in this document **and** in `prototype.html`. Four of the five LOW findings are fixed as well; the fifth needed no action. Every ratio quoted was recomputed from hex, and no new colour value was introduced — every fix reuses a token already in `tokens.md`.

| # | Sev | Finding | Resolution |
|---|---|---|---|
| 19 | **HIGH** | Upload **failures** were never announced. `.qsummary` (polite) died at "מעלה N מתוך M"; `<ul class="queue">` is a *sibling* of it, so every `נכשלה — …` string was visual-only; the error card's `<p class="live">` was left literally empty. Worst case: client-side pre-validation, which produces **no request and no focus move** — the owner selects four photos, two are dropped for HEIC/>10MB, and she believes all four uploaded. §10.3 had stated the governing rule in round 1 and then not applied it here | **Two additions, no third region.** (1) One `role="alert"` above the queue for the no-request case: «<bdi>2</bdi> קבצים לא צורפו — פרטים ברשימה למטה». (2) The **existing** polite `.qsummary` now carries the terminal outcome on drain — «הועלו <bdi>1</bdi> מתוך <bdi>3</bdi> · <bdi>2</bdi> נכשלו» — which covers every server-side failure (S3, network, `409 MEDIA_MISMATCH`, `409 MEDIA_NOT_UPLOADED`, cap race, `429`) with one announcement instead of one per row. The empty `.live` paragraph is deleted. §5.4's live-region row rewritten, §5.5 gains two announcement rows, §5.1's wireframe redrawn, strings added to §11. Also ruled: a multi-file batch does **not** announce per photo — the running + terminal summary carries it |
| 20 | MED | `aria-pressed` on the quick-size chips was a broken contract: ARIA requires a toggle button's press to flip its state, and §8.3 rules that a second press instead moves focus to the existing row. Secondary: the `•` marker was `::before{content:"• "}`, which Chrome and Firefox fold into the accessible name ("• 38") | **Option (a): `aria-pressed` dropped.** State moves into the accessible name — `aria-label="38 — כבר ברשימה"` when listed, plain "38" otherwise — which is the vocabulary §4.1's wireframe legend already used and describes what the button actually does. The toggle alternative (b) was rejected: it collides with §8.3's focus rationale and turns a low-stakes add into a destructive action. The `•` is now a real `<span class="mark" aria-hidden="true">`. Visual treatment unchanged; `--color-gold-text` at 5.76:1 on the white fill re-verified. Selector `.chip[aria-pressed="true"]` → `.chip.listed` throughout; §4.3 gains two ruling rows, §8.3 and §10.1/§10.3 renamed "pressed" → "listed" |
| 21 | MED | Rev 2's fix for round-1 finding 12 changed only the notice **fill**. White on paper is **1.13:1**, still delimited by the 1.22:1 `--color-border` hairline — the same problem moved 0.13 of a ratio point, against §10.3's own "every meaningful block boundary is perceivable" | **Fill kept, boundary given.** `.notice` border → `--color-border-input` (`#8A7A5E`): **3.69:1** against the paper Card, **4.18:1** against its own white fill. That is the console's established form-boundary token on this surface, so no new vocabulary, and every deliberate distinction from `PolicyBlockerBanner` survives — no danger colour, no gold stripe, no action. §5.2's comparison table and rationale rewritten; §10.1 gains a boundary row; §10.3 amended |
| 22 | MED | The §4.1/§4.2 stepper wireframes drew `כמות [ − ][ 3 ][ + ]` — the row in **logical** order, the island in **physical** order — while §4.3 rules the cluster an LTR island, i.e. `כמות, +, value, −` read logically. The wireframe is the artifact a builder copies, and it handed F9 the opposite guess to the one §4.3 exists to prevent | **Both wireframes redrawn** as `כמות [ + ][ 3 ][ − ]`, with an annotation under each stating the rendered order. §4.3's ruling gains the explicit clause: "drawn in logical order the cluster reads `+ value −`; on screen the island renders `− value +` left-to-right." One reading only |
| 23 | MED | The 60-variant cap state broke §10.3's own rule: the disabled chip group, the disabled custom-size input and the disabled "הוספה" button all carried no reason on their visible labels, and the `aria-describedby` pointing from the `disabled` input was inert | **Create-mode treatment mirrored exactly.** Group label → «הוספה מהירה (מידות אירופאיות) — הגעת ל-60 מידות»; input label → «מידה מותאמת (הגעת ל-60 מידות)»; add button → `aria-label="הוספה — הגעת ל-60 מידות"`; the inert `aria-describedby` removed; `role="alert"` on the message kept (it is what speaks at the moment of the block). §4.5's row updated, §10.3's bullet widened, §11's row renamed from "Create-mode disabled labels" to cover every disabled-with-reason label |
| 24 | MED | Two `נסי שוב` buttons in the upload queue had identical accessible names — the same defect as round-1 finding 11, which §5.4 had scoped to "inside the **gallery**"; the queue is a sibling and fell outside the rule | **`aria-label="ניסיון חוזר להעלאת {filename}"`** on each, sourced from the filename already rendered in `.qrow .fname`. *(String shape superseded in round 3 by finding 30 — the accessible name must start with the visible "נסי שוב"; the rule that the filename must be in the name is unchanged.)* §5.4's rule widened to "every per-item control in the תמונות Card — gallery items and queue rows alike"; §10.3's Labels bullet and §11's queue rows updated |
| 25 | LOW | §4.3 published the chip border at "3.44:1 on paper"; §10.1 publishes 3.69 for the same pair. Recomputed from hex, `#8A7A5E` on `#F6F0E6` = **3.69:1**; 3.44 corresponds to nothing in the palette | §4.3 corrected to **3.69:1**. §10.1 was already right and is untouched |
| 26 | LOW | `.vh` used physical `width`/`height`, the only survivor of round-1 finding 18, and was dead code | Kept and made logical — `inline-size:1px; block-size:1px`. `VisuallyHidden` is a real `components.md` primitive that F9 will implement, so the rule the build copies is now uniform rather than absent. A full re-sweep confirms zero physical directional or sizing properties remain outside media-query features |
| 27 | LOW | The ≤767 accordion contract collided with the binding heading outline: two consecutive `<h2>שמלות</h2>` on the list screen, two same-level `<h2>`s in the editor, and §8.1's focus target therefore ambiguous at mobile | **Ruled in §1.1.** At ≤767 the accordion header *is* the section `<h2>`; the in-panel section heading is suppressed; the editor cascades one level (`h3` dress name → `h4` Cards → `h5` Card-internal empty states). Outline: `h1 → h2 accordion header → h3 dress name → h4 Cards`, no skip. §8.1's focus destination restated as "the dress-name heading, `<h2>` at ≥768 / `<h3>` at ≤767" — one candidate at either width. The build takes the level from a single `headingLevel` value so the two outlines cannot drift |
| 28 | LOW | `@media (max-width:767px){.save-row{flex-direction:column-reverse}}` put the button above the cue, the opposite of §3.2, and made visual order diverge from DOM order | Changed to `flex-direction:column`. DOM order `[cue, button]` now renders cue above full-width button, matching §3.2, with visual order = DOM order (1.3.2). Applies to both `.save-row` instances |
| 29 | LOW | `tokens.md`'s radius table assigns chips to `--radius-sm`, but chips render as pills here and in the passed `design-system/prototype.html` | Queued as **§12 item 3e** — a doc-only split of that row into "inputs" (`--radius-sm`) and "chips / badges (pill)" (`--radius-full`), in the same PR as the other `tokens.md` corrections. The rendering is correct and unchanged |
| — | LOW | The two new `Badge` variants (`muted`, `warning`) are not in `components.md`'s enumerated four | **No new action** — already tracked as §12 item 7 since round 1. Rev 3 adds a gate condition to that item: it must land before or with the F9 build that consumes this document |

**Adjudications where findings pulled in different directions**

- **Finding 19 vs §10.3's one-region-per-discrete-event rule.** The obvious fix — a third live region for failures — was rejected, and the critic's own guidance agreed. Client-side batch rejection is genuinely a *separate* discrete event (no request, no focus move, instantaneous, assertive), so it earns the one `role="alert"`; running progress and terminal outcome are one continuous event stream on one polite region. Two regions in the תמונות Card, and that count is now written into §5.4 and §10.3 so a later revision cannot quietly add a third.
- **Finding 20 (a) vs (b).** Option (b) — a genuine toggle chip whose second press removes the size — would have kept `aria-pressed` honest, but it makes a one-tap control destructive and contradicts §8.3's focus ruling, which exists because the owner's next action after adding a size is typing a quantity. Chose (a): the accessible name already had to say something, the wireframe legend already said it, and dropping ARIA that over-promises is the same call §1.1 made for `role="tab"` — one precedent, not two.
- **Finding 21 vs §5.2's deliberate "no marker" decision (and round 1's finding-12 adjudication).** Round 1 chose a fill change *over* a darker border to stay away from the `PolicyBlockerBanner` vocabulary. Rev 3 keeps that intent and takes both: the marker being avoided was the **gold stripe**, not a boundary as such. `--color-border-input` is a neutral warm brown already used for every field in the console — it says "this is a delimited region", not "act on me" — so the distinction the section exists to preserve is intact while the boundary now actually exists.
- **Finding 27 — cascade vs. duplicate heading.** Suppressing the in-panel heading at ≤767 costs a one-level cascade in the editor, which is slightly more build work than emitting two `<h2>`s. Chose the cascade: two identical consecutive `<h2>שמלות</h2>` makes heading navigation report a section that does not exist, and it leaves §8.1's focus destination genuinely ambiguous — a build-time cost is cheaper than an ambiguity handed to F9.

**Two further corrections found by the rev-3 self-review, raised by neither critic**

- **§5.1's queue-summary line did not add up.** The wireframe drew a *terminal* summary — "הועלו <bdi>1</bdi> מתוך <bdi>2</bdi> · <bdi>1</bdi> נכשלה" — on a queue state that still has a row reading "מעלה…", and with a denominator of 2 against three files that were actually sent (`IMG_4821` ok, `IMG_4822` in flight, `IMG_4825` failed; the other two were rejected client-side and never left the browser). Same transcription class as finding 25, in the wireframe that finding 19 had just redrawn. **Corrected to the running form "מעלה <bdi>2</bdi> מתוך <bdi>3</bdi>"**, with an annotation stating both the denominator's provenance and the terminal string the same region shows on drain. No rule changed — the drawing was simply wrong about its own state.
- **Finding 27's ruling was not visible in the artifact F9 copies.** The ruling landed in §1.1 and §10.3 but `prototype.html` still carried only the ≥768 outline in its `.page-h` comment and drew the section `<h2>` at every width with no note. Since the prototype does not implement the accordion's heading wrapping, it keeps drawing the ≥768 heading — but the comment block above `.page-h` now carries **both** outlines, and the list-screen heading and the editor's dress-name heading each carry an inline note (`suppressed at ≤767` / `<h2>` at ≥768, `<h3>` at ≤767, one `headingLevel` value). A builder copying the prototype without the doc open would otherwise have reproduced the exact duplicate-`<h2>` the ruling exists to prevent.

**Verification pass (rev 3).** All 29 contrast figures published in §10.1, §10.2, §10.2b, §4.3, §5.2 and §2.3 were recomputed from hex with the WCAG relative-luminance formula: **29/29 reproduce exactly, zero mismatches.** A full sweep of `prototype.html` confirms **zero raw colour values** outside the `:root` token block (the only two hex strings in the file are inside the comment documenting the `--color-border-input` correction) and **zero physical directional or sizing properties** outside media-query features.

### Round 1 — two critics, 17 findings (2026-07-24)

All 4 HIGH and all 10 MEDIUM findings are fixed in this document **and** in `prototype.html`. Both LOW findings are fixed as well — each was cheap and neither added clutter. Every ratio quoted below was recomputed from the hex values, not transcribed.

| # | Sev | Finding | Resolution |
|---|---|---|---|
| 1 | HIGH | `.disabled-pane{opacity:.55}` composited the create-mode heading (3.53:1), hint (2.29:1) and counter (2.29:1) below AA | **Opacity deleted.** All text at full token colour; recession carried by the `disabled` controls (WCAG-exempt). §3.3 rewritten with the compositing maths showing no opacity value can be tuned into compliance; wireframe annotation changed to "(controls disabled; heading and hint at full contrast)" |
| 2 | HIGH | `--color-border-input #B9A98F` = 2.03:1 on paper, not the ≥3:1 the ledger claimed; sole boundary of every field | **Token value corrected to `#8A7A5E`** (3.69 / 4.18 / 4.04) in the prototype under the same token name, and raised as blocking §12 item 3a for `tokens.md`. Explicitly rejected the alternative of reusing `--color-gold-strong` as the resting border (it passes at 3.47, but golds every field and collides with the pressed-chip signal) |
| 3 | HIGH | Price-visibility and reserved toggles were 20×20 boxes with ~21px labels — under 44×44 | **`<label>` now wraps checkbox + title**, `min-block-size: 44px`, box 24×24; description stays outside the label on `aria-describedby`. Same treatment `.check` already used. Ruled in §3.4 |
| 4 | HIGH | Status chips nested inside the `-webkit-line-clamp` name box → "הוזמן" clipped on long names | **`.row-chips` moved out** to a sibling line that is never clamped. §2.3 gains a binding "Status-chip line" row; §6 gains the compound long-name + reserved edge case; the prototype's long row now carries a chip so the case is drawn, and both wireframes updated |
| 5 | MED | Pressed-chip `•` was a 14px text glyph in `--color-gold-strong` (3.47), contradicting §10.1's own "never below 24px" claim | Recoloured to **`--color-gold-text`** (5.76 on the chip's white fill). Chose recolour over widening the ledger: gold-strong stays barred from all rendered text, which keeps one rule instead of one rule plus an exception. §12 item 3d asks `tokens.md` to name `content:` glyphs explicitly |
| 6 | MED | Prototype rendered "בארכיון" as `badge muted` while §10.1 claimed it was identical to "הוזמן" | **Ledger corrected, prototype kept.** "הוזמן" is a live status the storefront also shows; "בארכיון" is a console-only shelf label on an already read-only row — the recession is intentional. §2.3 now has separate rows for the two, §10.1 lists the muted pairing at 6.36 and the "identical" wording is gone |
| 7 | MED | `muted` / `warning` Badge treatments are not in `components.md`'s enumerated variants | Named as variants in §2.3 and queued as **§12 item 7**, to land in the same PR as the `tokens.md` corrections. Consistent with how this doc already handles cross-file amendments — it does not edit passed artifacts mid-round |
| 8 | MED | `role="tab"` declared without `aria-controls` / `role="tabpanel"` / roving tabindex, and applied at the breakpoint where the control is an accordion | **ARIA roles dropped.** Now `<nav aria-label>` + `aria-current="page"`, matching §8.1's five sequential Tab stops. Chose this over building the full tab pattern: the tab contract would have to be un-declared again at ≤767, and roles cannot be swapped by a media query. §1.1 rules it and specifies the ≤767 accordion contract (`<h2>` + `aria-expanded` + `aria-controls`) |
| 9 | MED | `::file-selector-button` at 34px — the file input's real hit target | **44px on the pseudo-element** plus `padding-block`; wrapper grown to `--space-16` (64px) so the button is not clipped. §5.4 gains a row explaining *why* the floor belongs on the pseudo-element |
| 10 | MED | Duplicate-size error announced nothing — it appears under standing focus | **`role="alert"` added**, alongside the existing `aria-invalid` + `aria-describedby` (complementary, not redundant). Same for the variant-cap message, which now has a rendered state in the prototype. General rule recorded in §10.3 |
| 11 | MED | Four "קבעי כתמונה ראשית" buttons with identical accessible names | **`aria-label="קביעת תמונה {i} כתמונה ראשית"`** on each, ordinal from the same source as ↑/↓/delete. *(String shape superseded in round 3 by finding 30 — the accessible name must start with the visible "קבעי כתמונה ראשית"; the rule that the ordinal must be in the name is unchanged.)* Rule generalised in §5.4, string added to §11 |
| 12 | MED | Storage notice was paper-on-paper (1.00:1) inside a paper Card, delimited by a 1.22:1 hairline | **Fill changed to `--color-surface-raised`.** Chose the fill change over darkening the border: it reuses vocabulary already on this surface (Badge, preview line, inputs) and keeps every deliberate contrast with `PolicyBlockerBanner` — no danger colour, no gold stripe, no action. §5.2 table and rationale updated |
| 13 | MED | `role="status"` on the running stock total → one announcement per keystroke, competing with the אזל hint | **Removed.** Plain text that updates visually; the 0-crossing hint keeps its region because that is the event that carries meaning. §4.3 and §10.3 amended with the debounce fallback if it is ever wanted |
| 14 | MED | Create-mode disabled file input and chip group did not state their reason on the visible label; chips were `aria-hidden` | **Both fixed.** Labels now carry the reason; the chip group is `role="group" aria-labelledby` with a visible group label and is **not** `aria-hidden` — hiding it contradicted §3.3's own argument. §10.3 bullet generalised from "the disabled file input" to every disabled control |
| 15 | MED | Stepper RTL direction never ruled — mirrored −/+ around a non-mirroring numeric island | **Ruled an LTR island**, matching the price-field precedent: `direction: ltr; unicode-bidi: isolate` on the control group, "כמות" stays outside in RTL flow. §4.3 gains a "Stepper direction — ruled" row |
| 16 | LOW | §10.1 transcribed from `tokens.md`; focus-ring, at-cap-counter and pressed-chip-border rows cited the wrong surface or the wrong figure | **Whole ledger recomputed** against the surface each pair actually renders on; three rows corrected, several rows split per-surface. New §10.2b records the two `tokens.md` figures that do not reproduce; §12 item 3c queues the focus-ring correction |
| 17 | LOW | No `<h1>`; catalog list had zero headings; `h2→h4` skips | `<h1>` console title, `<h2>` section heading on every screen, empty-state headings demoted or promoted so no level is skipped. Outline rule added to §1.1 and §10.3 |
| 18 | LOW | Physical `min-height` / `min-width` / `max-width` where the spec tables mandate logical | Swapped throughout the prototype (media-query *features* left alone — they are viewport queries, not properties). §8 preamble tightened from "a physical `left`/`right`" to "a physical directional **or sizing** property" |

**Adjudications where findings pulled in different directions**

- **Finding 5 vs finding 16 (gold-strong on the `•`).** The critic offered a choice: recolour, or keep gold-strong and add a justified exception to the ledger (defensible under WCAG 1.4.11 since the `•` is a redundant selection cue, not a word). Chose **recolour**. The marker is unambiguously rendered text — it is produced by `content:` and inherits `--text-sm` — and `--color-gold-text` costs nothing, passes as text (5.76), and preserves a single unqualified rule ("gold-strong never touches text") over a rule with a case-by-case carve-out. A carve-out is exactly what rev 1's ledger accidentally granted itself.
- **Finding 2 (token) vs the standing constraint that `tokens.md` is a passed artifact.** The critic's instruction was "amend the token, not the doc". `tokens.md` is out of scope for this round's edits, so the prototype ships the corrected value **under the existing token name** (never as a raw hex) and §12 item 3a marks the `tokens.md` change as blocking for F9. This keeps the prototype — the artifact F9 copies from — correct today, without silently forking the token system.
- **Finding 12 (notice fill) vs §5.2's deliberate "no marker" decision.** Kept the no-marker decision; changed only the *fill*. A stripe or a darker border would have moved the notice toward the `PolicyBlockerBanner` vocabulary the section exists to stay away from; a white fill on paper reads as "a distinct block" without reading as "act on me".
- **`.row-meta .sep`** was `--color-border-input`. With the token darkened it would have gone from a 2.03:1 to a 3.69:1 glyph — better, but still an ambiguous "decorative text" case. Changed to `--color-ink-muted` (5.61 on paper) so a rendered glyph is never justified by a non-text threshold. Not raised by either critic; recorded here because it is a visible change.
