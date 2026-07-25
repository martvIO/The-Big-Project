# Design QA Checklist — F9 build

**Created**: 2026-07-23 · **Revised**: 2026-07-24 (rev 2 — 50 verified coverage gaps merged; browser baseline attached)
**Target**: `packages/ui`, `apps/storefront`, `apps/manage`
**Binding sources**: [tokens.md](system/tokens.md) · [components.md](system/components.md) · [screens/design-system/](screens/design-system/) · [design-config.md](../design-config.md) · [test-results.md](test-results.md)
**Companion**: [qa-browser-baseline.md](qa-browser-baseline.md) — measured pre-build state of both apps

This is the build-side half of the design gate. The gate checked the *design*; this checks the *code that implements it*. Round 2 of the critic deferred two items here (§9), the 2026-07-23 axe baseline left four document-structure findings as build requirements (§8), and PRE-1 (**Critical**) now has its design fix — the `--space-a11y-clearance` token (2026-07-25, critic re-run) — leaving only its build-time zero-overlap check open (§9).

**Run it**: after the F9 build, before the F9 PR merges. Then again per-app as the F7 restyle and F10 storefront land.

> **A ticked box must mean a check was performed on the built artifact.** Several lines below exist specifically because a plausible-looking build passes the general rule while violating the specific one.

---

## 0. Preconditions (blocking — nothing below is checkable until these are true)

- [ ] `packages/ui/src/theme.css` exists with a single Tailwind v4 `@theme` block exporting every token from tokens.md; both apps `@import "@boutique/ui/theme.css"`
- [ ] The placeholder `tokens` object in `packages/ui/src/index.ts` is replaced by values generated from the same source (TS export retained only for non-CSS use — canvas, meta tags)
- [ ] **Line-heights ship paired with sizes** — a Tailwind v4 `--text-*--line-height` for **all seven** steps: xs 1.4 · sm 1.5 · base 1.6 · lg 1.5 · xl 1.35 · 2xl 1.25 · 3xl 1.15. Exporting `--text-xs: 0.75rem` alone satisfies "every token exported" while Tailwind emits `text-xs` with no leading and the Hebrew-x-height tuning vanishes silently. `grep -c -- '--text-.*--line-height' packages/ui/src/theme.css` must return **7**
- [ ] **Tailwind's built-in `ease-out` is overridden** in `@theme` — v4 ships `cubic-bezier(0, 0, 0.2, 1)`, not the token's `cubic-bezier(0.16, 1, 0.3, 1)`. Without the override, `ease-out` silently means the wrong curve everywhere
- [ ] `@fontsource` imports the **declared weights, not the default** — `@fontsource/frank-ruhl-libre/{400,500,700}.css` and `@fontsource/assistant/{400,600,700}.css`. A bare `@fontsource/<pkg>` import ships **400 only**, dropping the display voice to 400 and faux-bolding Hebrew
- [ ] **The Hebrew subset is actually fetched** — verify in DevTools → Network that a Hebrew woff2 loads, not only a Latin one. A latin-only subset passes every static check and renders Hebrew in a system sans
- [ ] `font-synthesis: none` set globally so a missing face fails visibly instead of being faked
- [ ] **No runtime Google Fonts request in production** — the CDN link is preview-only, confined to the prototypes
- [ ] `color-scheme: only light` on `:root` in `theme.css` — bare `light` does **not** opt out of Chrome-Android Auto Dark Theme, which force-inverts any page declaring no scheme and voids every ratio in §8. `grep -rn 'color-scheme' packages/ui/src` returns exactly one hit; `grep -rnE 'prefers-color-scheme|\bdark:' apps/*/src packages/ui/src` is empty
- [ ] i18next wired with Hebrew as default locale — no hardcoded Hebrew strings in components
- [ ] `@playwright/test` added to the workspace so the browser passes below run in CI, not from a developer's npx cache

---

## 1. Colour laws

Raw gold `#C5A059` is 2.38:1 on cream — **measured, not assumed** ([browser baseline](qa-browser-baseline.md)). It never carries text, at any size.

- [ ] `--color-gold` appears **only** as: CTA button background, hairline ornaments, monogram placeholder art, decorative borders
- [ ] `--color-gold-strong` `#9E7B36` for meaningful non-text UI only: focused input borders, active tab underline, display accents ≥24px, the exceptions diamond marker, the policy banner stripe
- [ ] `--color-gold-text` `#7F612B` is the **only** gold touching text: links, price emphasis, "בתוקף" version marker
- [ ] Primary CTA = gold background + **ink** text (6.41:1 on gold), never gold text
- [ ] No `color: var(--color-gold)` / `text-gold` anywhere; no raw `#C5A059` / `#D4AF37` / gold literal in `apps/` or `packages/ui`
- [ ] **`--illus-1/2/3` stay decorative fills only** — every hit of `grep -rn 'illus' packages/ui/src apps/*/src` is a `fill=`/`stroke=` inside `aria-hidden` art. Never a card, section, banner, badge, chip, input or CTA background, and never a surface carrying text: their pairs were deliberately never computed, and `--color-gold-text` on `--illus-1` measures **4.36:1** — *under* the AA floor. **Zero hits is a pass**; if no component legitimately fills with them, drop them from `theme.css` rather than ship an unowned token

## 2. Token fidelity

- [ ] No raw px in component CSS — spacing from `--space-1..16`, radius from `--radius-sm|md|full`
- [ ] No Tailwind default colour utilities (`bg-blue-500`, `text-gray-600`, **`bg-white`**, **`text-black`**) — every colour resolves to a project token
- [ ] Type sizes from `--text-xs..3xl`, **not** Tailwind's scale (its `text-3xl` is 1.875rem; the token is 2.25rem) — and nothing overrides the paired leading on Hebrew runs: `grep -rnE 'leading-|line-height' apps/*/src packages/ui/src` empty outside `theme.css`
- [ ] Weight law: display never below 400; body 400 / emphasis 600; **no weight 300 anywhere**. `grep -rnoE 'font-weight:\s*[0-9]{3}|\bfont-(thin|extralight|light|medium|semibold|extrabold|black)\b' packages/ui/src apps/*/src | sort -u` — every hit is display 400/500/700 or body 400/600/700
- [ ] Letter-spacing `0` on all Hebrew — no `tracking-*` on Hebrew runs (`0.02em` only on Latin-only all-caps micro-labels)
- [ ] **Font stacks verbatim from tokens.md, declared in `theme.css` and nowhere else** — `"Frank Ruhl Libre", "David Libre", serif` / `"Assistant", "Heebo", system-ui, sans-serif`. Never truncated: the second name is the Hebrew-covering fallback, so `"Frank Ruhl Libre", serif` drops to a Latin serif. **Both prototypes drop `"David Libre"` and `"Heebo"` — do not copy them.**
- [ ] **No Latin-only display serif anywhere** (Playfair, Didot, Cormorant, Bodoni, Baskerville, Georgia — no Hebrew glyphs, they fall back to a sans mid-headline). Headings use the `font-display` utility, never Tailwind's `font-serif`/`font-sans` (v4 defaults are Latin-only)
- [ ] **Motion comes from tokens** — every duration resolves to `var(--motion-fast|base|slow)` (150/200/300ms), every timing function to `var(--ease-out)`. No literal `ms`/`s`, no `ease-in-out`/`linear`/bare `ease`, no Tailwind `duration-*` (they do not read a `--motion-*` namespace). **Sole exemption**: the `Skeleton` pulse keyframe (1.5s)
- [ ] **Motion vocabulary holds** — fades + translates **≤8px**; `scale()` **only** in `Modal` (0.97→1), so a hover zoom on `DressCard`/`Gallery` is a defect; `rotate`/spin **only** in the `Button` spinner; the only `infinite` animations are the Skeleton pulse and that spinner; **no overshoot/spring easing** (control-point y outside 0–1, `bounce`/`elastic`/`back`); nothing autoplays — `Gallery` advances on user input only, no `setInterval`, no `autoplay`
- [ ] Shadows are the warm ink-tinted tokens, never pure black or Tailwind defaults
- [ ] Cards pad `--space-6`; single theme — no dark-mode variants shipped
- [ ] Images have no hard borders — cream matting + `--shadow-sm`

## 3. RTL & locale

- [ ] `lang="he" dir="rtl"` on `<html>` in both apps ✓ *(already true)*
- [ ] **Zero physical direction properties in component CSS** — logical only (`padding-inline-start`, `margin-inline-end`, `inset-inline-*`, `text-align: start|end`). Check JSX style objects too (`marginLeft`, `paddingRight`), which a class-name grep misses entirely
- [ ] Numeric columns `text-align: end`
- [ ] LTR islands present and isolated — phone, `maps_url`, email, Instagram handle, Latin dress names, **and money/agorot input fields** (§4)
- [ ] `Gallery` swipe direction RTL-correct (first image on the inline-start)
- [ ] Directional motion enters from **inline-start** — note this is inline-axis only; `Toast` is a *block*-axis entrance and is not governed by it
- [ ] Israeli week ordering (Sun-first) in `HoursSection` and `HoursTable`
- [ ] **"Today" resolves in IANA `Asia/Jerusalem`** — never the device clock, never a fixed `+02:00`/`+03:00` offset (Israel has DST; F7 stores naked `day_of_week` + `TIME` + exception `DATE`, so the timezone frame exists only in the render). Vitest with a frozen clock asserts `HoursTable`, `HoursSection` closed-today and `BoutiqueHeader`'s `היום:` snippet render identically under `TZ=America/New_York` and `TZ=Asia/Jerusalem`, including the 23:00→00:30 day flip. No `getDay()`/`getDate()`/`toLocale*` without an explicit `timeZone: 'Asia/Jerusalem'`
- [ ] `נפתח מחר ב-…` is emitted **only** when the next open window is literally tomorrow — a closed Saturday, back-to-back closed days, or a closed exception date must name the real next open day

## 4. The `Price` component (contract, not a suggestion)

- [ ] Every money amount renders through `Price` — a hand-formatted shekel string in app code is a defect
- [ ] Format number-then-shekel: **"5,900 ₪"**, numeric run `dir="ltr"` + `unicode-bidi: isolate`, digits in body font
- [ ] Hidden-price "מחיר בתיאום" (muted italic) occupies the **same slot at the same height** — no card-height jump in a mixed grid
- [ ] Agorot→shekel conversion happens once, in `Price`
- [ ] **Console money inputs are the only sanctioned `₪` outside `Price`** — `TypesSection`'s deposit field renders `₪` as a static label/suffix adornment (never a character the owner types), numeric input `dir="ltr"` + `unicode-bidi: isolate`, body font. Presentation-only: the agorot arithmetic and prop signature stay exactly as F7 shipped them

## 5. Components (`packages/ui`)

Every component ships default / hover / focus-visible / disabled + RTL layout + keyboard operability + Vitest coverage.

- [ ] `Button` — variants, sizes, full-width mobile option, **loading state locks width**
- [ ] `Input`/`TextArea` — visible label always, help text, char counter, error via `aria-describedby`, `dir` override prop
- [ ] `Select` native · `Toggle` label+description · `TimeField`/`DateField` native, styled
- [ ] `Badge` — gold variant uses `gold-strong`, large-text only
- [ ] `Card` — paper bg, radius-md, shadow-sm, hover-elevate variant
- [ ] `Toast` — `role="status"` (success) / `role="alert"` (error), auto-dismiss, **one at a time**
- [ ] `Modal` — focus-trapped, `Esc` closes, focus returns to trigger, motion **split across two elements**: panel scale 0.97→1 + fade at `--motion-base`, backdrop a *separate* element with its own opacity transition at `--motion-fast`
- [ ] `Skeleton` — text lines, 3:4 image blocks, pulse ≤1.5s, **static under reduced-motion**
- [ ] `EmptyState` icon-less by default · `SectionHeading` display serif + `aria-hidden` ornament
- [ ] `SkipLink` present and first in tab order on every storefront page · `VisuallyHidden` + focus-ring utility exported
- [ ] `Toast` entrance is **block-axis from block-start** + fade at `--motion-slow` — no inline-axis translate, no `scale()`, no overshoot. (Exit is unspecified by the design — do not invent one.)
- [ ] **`apps/manage/src/components/shared.tsx` is DELETED, not retokened** — the console imports `Button`/`Input`/`TextArea`/`Card`/`Toast` from `@boutique/ui`. A Tailwind class-string constant carries none of the behavior §5 requires, so a divergent console `Toast` ships without `role="alert"` while every box here is ticked. Both empty: `grep -rnE '(inputClass|primaryButtonClass|secondaryButtonClass|dangerButtonClass|labelClass|cardClass)' apps/manage/src` and `grep -rnE 'function (ErrorNotice|SavedNotice|Loading)\b' apps/manage/src`; and `grep -rln '@boutique/ui' apps/manage/src/components` lists all five section files
- [ ] **Destructive console actions are never one-click** — type archive and exception remove each open the `packages/ui` `Modal` first (never `window.confirm`, never a bare button straight to the API); cancel/`Esc` fires **no** network call and returns focus to the trigger. F7 ships both one-click today; adding the interstitial is in F9 scope and preserves the F7 API. **If `Modal` ships with zero call sites, this line fails**
- [ ] **`ConsoleShell` nav is a real widget** — pick one contract and honor it fully: **(a) ARIA tabs** (`role="tablist"`, one `aria-selected="true"`, roving `tabindex`, Arrow-key movement, `aria-controls` → `role="tabpanel"`) or **(b) plain nav** (`aria-current="page"`, **no** `role="tab"`). Never `role="tab"` without the keyboard contract. @375 accordion headers are `<button aria-expanded>` + `aria-controls`. No `<div onClick>`; logout is a `<button>` with a text name; the gold-strong underline is never the only active signal
- [ ] Nothing from "NOT in v1" shipped: no custom dropdowns, carousels beyond the gallery, data tables, charts, avatar menus, dark theme, toast queues

## 6. Screens & states

**Every state below is a real render, not a described one.**

### Catalog (`/`)
- [ ] Default · Loading (header + 6 skeleton cards) · Error (inline retry **under the header, identity intact**)
- [ ] **Empty (critical)** — identity moment: name, essence, hours, inline contact panel, CTA bar, "הקולקציה בדרך" muted. The storefront ships before the catalog does
- [ ] Price-hidden mix — no layout jump · Reserved — "הוזמן" badge top-inline-start, **card not dimmed**
- [ ] **`BoutiqueHeader` default carries all four parts** — name (display, `--text-3xl`), essence (`--text-base`, muted), hours-today snippet, **and the location link**: a real `<a>` to `maps_url` with `dir="ltr"`, `↗` marker `aria-hidden`, degrading to plain address text with no dead link when `maps_url` is null
- [ ] **`BoutiqueHeader` closed-today ships and renders on `/`** (not only `/about`) — the `היום: 10:00–19:00` snippet is *replaced* in the same meta run by `סגור היום · נפתח מחר ב-10:00`, location link retained, in ink/ink-muted. Assert the computed colour is **not** `--color-danger` — closed isn't an error. Vitest on both day-check branches; never blank, `undefined`, or yesterday's range
- [ ] **`DressCard` reserves the favorites slot and ships no favorite feature** — an empty non-interactive `aria-hidden="true"` 44×44 box at `inset-block-start`/`inset-inline-end: var(--space-3)` over the 3:4 photo. No `<button>`, no icon, no `localStorage`, not in the tab order; must not displace the "הוזמן" badge (inline-**start**) and must not change card height. `grep -rniE 'favorit|localStorage|heart' packages/ui/src apps/storefront/src` empty in F9
- [ ] **Image-missing card** — a dress with 0 photos renders the monogram filling the whole 3:4 slot and emits **no `<img>` at all**; a broken-image glyph or collapsed slot is a defect. Verify in a **mixed grid**: photo-less card and photographed sibling in the same row have identical height. Accessible name stays the dress name. This is `DressCard`, distinct from the detail `Gallery` no-photo state — check both
- [ ] **Photos fade in on `load`** — opacity 0→1 over `--motion-base`, opacity only. The 3:4 box carries `aspect-ratio: 3/4` so the slot is reserved before decode: **CLS 0**. Verify the **cached** path — an image whose `load` already fired must not stay at `opacity: 0` (invisible dresses on second visit): test hard reload *and* warm reload. Under reduced-motion renders at `opacity: 1`
- [ ] No hero carousel; 3:4 crop + cream matting; footer carries הצהרת נגישות on every page

### Dress detail (`/dress/{id}`)
- [ ] Default · Loading · Single photo (chrome hidden **entirely**) · No photo (monogram) · Reserved (**CTA still live**) · Archived (`השמלה כבר לא זמינה` + back CTA) · Long description (6-line clamp + "עוד")
- [ ] **"חזרה לקולקציה" back-link renders in every state**, not only archived — a real `<a>` to the catalog route, **never** `history.back()`/`navigate(-1)`/`router.back()`: the storefront's primary entry is an Instagram-bio deep link with no history stack. Inline-start, logical properties, arrow glyph `aria-hidden`. Present at 375/768/1440 — it carries no mobile-only class in the gate-passed prototype
- [ ] Size chips informational `Badge`s, **not selectable** · share via Web Share API with copy-link fallback · no zoom/lightbox in v1

### Profile & hours (`/about`)
- [ ] Default · Closed today (`סגור היום · נפתח מחר ב-10:00` in **ink, not danger**, leading the card) · No exceptions (row absent) · Sparse profile · No `maps_url` (plain text, no dead link)
- [ ] **Loading and Error render** — the screen spec's States table omits both rows. Loading: heading + hairline paint first, hours/contact cards render `Skeleton` blocks, never a blank column or bare spinner. Error: the catalog's `error-block` pattern — name + hairline above it, message in **ink not danger**, secondary-Button retry, **phone/WhatsApp still reachable** so the trust surface degrades to a contact card rather than a dead page. `apps/storefront` is a client-fetched SPA — there is no SSR to hide either
- [ ] **`HoursTable` renders the whole Israeli week** — all 7 days accounted for Sun-first, and **every day with no window renders the literal "סגור" — never blank, never `—`, never an omitted row** (Saturday is the standing case). Assert with a fixture that omits Saturday entirely: the `שבת` row *and* its `סגור` label are both in the DOM
- [ ] **Grouping is a unit-tested pure function** — ranges collapse only across days *adjacent in the Sun-first week* **and** with an *identical set of windows* (F7 allows multiple windows/day). Fixture: Sun/Mon/Wed/Thu 10:00–19:00, **Tue no rule**, Fri 09:00–13:00, Sat no rule ⇒ five rows (`א׳–ב׳` / `ג׳ סגור` / `ד׳–ה׳` / `ו׳` / `שבת סגור`) and **never** `א׳–ה׳`
- [ ] Exceptions use `gold-strong` diamond **+ text** · contact panel: tap-to-call, `wa.me`, **Waze + Google Maps**, Instagram · column max 640px, never multi-column

### Manage console
- [ ] First-run · Steady · Saving (button loading, inputs disabled) · Save error (danger Toast + field-level inline errors) · Session expired (401 → LoginForm, same shell)
- [ ] **Save success is the inline cue, not a Toast** — "נשמר לפני רגע" in the save row, inline-start of the primary Button, `--text-xs` + `--color-ink-muted`, on every section form (the four F7 sections **and** `DressEditor`); Button returns from loading at unchanged width, inputs re-enable. The console states table maps Toast to *Save error* only
- [ ] **`SetupProgress` is derived, never authored** — ticks come from the F7 section responses the sections already render; **no new `/manage/*` endpoint and no new field on an existing F7 response** (the F7 router diff must be empty). `grep -rnE '[0-4]\s*/\s*4' apps/manage/src` empty — the label interpolates `{done}/{total}`. Renders correctly at 0/4 and 1/4, not only the wireframe's 3/4; saving the last section flips its ✓ and drops the card to steady **without a reload**; pointer names the first incomplete section in nav order
- [ ] **The progress pointer and the banner's `ליצירת מדיניות ←` each open the section they name** — both are `href="#"` dead-by-design in the prototype and excluded from session findings by the moderator brief, so **no session will ever catch this**. `grep -rn 'href="#"' apps/manage/src` must be empty
- [ ] `PolicyBlockerBanner`: warning-text on paper + gold-strong stripe, **no icon, not red**
- [ ] `TermsSection` immutable-ledger: version chip + date + created-by, **no edit or delete affordance anywhere**, latest marked "בתוקף" in gold-text
- [ ] **Structured-field units live in the visible label** — `refundable_until_hours_before` → "שעות לפני התור", `forfeit_percent` → "% חילוט". A bare "חילוט" label is a defect; so is a unit that appears only in the placeholder or only in the "בין 0 ל-100" error (which fires after entry, too late). These drive E4's refund math and the version is append-only — a mis-entered unit cannot be edited away
- [ ] `LoginForm` generic error preserved verbatim (F5 anti-enumeration)
- [ ] Console content capped at 720px; no hairline ornaments on forms
- [ ] **F7 component APIs, behavior and tests unchanged** — a changed prop signature or a modified F7 test is a defect (the confirm-modal and primitive-swap items above are explicitly in scope and preserve the API)

## 7. Responsive (375 / 768 / 1440)

- [ ] Catalog grid 2/3/4-col; max-width 1200 centred @1440
- [ ] **Gutters step at all three widths, measured from computed style** — page gutter `--space-4` @375 · **`--space-6` @768** · `--space-12` @1440; grid `gap` `--space-4` @375 · `--space-6` @768 · **still `--space-6` @1440** (the gap does not step to `--space-12`). The token law states only the endpoints, so a build that skips 768 passes it
- [ ] **Booking CTA checked per screen at 375 and 768, exactly one instance visible at each width** — catalog + empty (bottom bar @375 → inline in `BoutiqueHeader` @≥768) · detail (bottom bar @375 → inline in the **facts column, not the header** @≥768) · `/about` (**static inline full-width button, no bottom bar at any width** — nothing moves at 768). Two of the three differ from the catalog rule; checking only the catalog is how the round-1 "missing detail mobile CTA bar" finding returns
- [ ] **Fixed bottom chrome reserves its own space** — at 375 and 767px scrolled to the end, the footer row and the last content sit **fully above** the CTA bar: zero overlap with the bar or the fixed a11y button, and הצהרת נגישות is tappable. Scroll containers carry `padding-block-end ≥ bar height + env(safe-area-inset-bottom)`, derived from the bar height via token/`calc()` — **not** the prototype's off-scale 96/120/140px literals — and the reservation is **removed at ≥768** where the CTA goes inline (no dead gutter)
- [ ] **Console @375: every form control *and* its save Button fill the card content box** (card inline-size − 2×`--space-6`), no shrink-to-fit, in all five sections and `LoginForm`. §5 checks only that `Button` *offers* full-width-mobile; this checks it is *applied*. At ≥768 the save button returns to auto width, inline-end
- [ ] Detail 55/45 @768 with thumbs · 60/40 @1440 with sticky facts column · console accordion @375 (one open) → tabs @≥768
- [ ] No horizontal scroll at any of the three widths
- [ ] Tested with a **long Hebrew boutique name** and a long dress name — no overflow or clipped descenders

## 8. Accessibility — IS 5568 / WCAG 2.0 AA (legal floor)

- [ ] Contrast measured in the **built** UI: ink 15.24:1 cream / 13.89 paper · ink-muted 6.15 / 5.61 · gold-text 5.57 · success 6.10 · danger 6.78 · warning-text 5.70 / 5.20. Non-text ≥3:1 — gold-strong 3.80, border-input `#8A7A5E` 3.69 paper · 4.18 white · 4.04 cream
- [ ] **Document structure — re-run axe-core against the built routes** and clear the four findings the 2026-07-23 baseline left as build requirements: `landmark-one-main`, `page-has-heading-one`, `heading-order`, `region`. Exactly one `<main>` per route, `<nav>`/`<footer>` as real landmarks, one `h1` per route (dress name on detail, section name on console), no skipped levels
- [ ] **The skip link actually moves focus** — its `href` resolves to that `<main>`, which carries `tabindex="-1"`, so the next Tab lands inside the content, not back in the header. Axe cannot catch this; keyboard-verify in Safari and Firefox, where a fragment jump to a non-focusable target silently does nothing
- [ ] **Per-route document title** (WCAG 2.0 **Level A** 2.4.2) — distinct, Hebrew, i18n-keyed on `/`, `/dress/{id}` (dress name, same source as its alt), `/about`, `/accessibility`, and each console section. **Verify by client navigation with no reload** — a Vite SPA keeps `index.html`'s title forever by default, and both apps currently ship one hardcoded English title. axe's `document-title` rule passes while this defect is live
- [ ] Focus ring on **every** interactive element: 2px `--color-focus`, 2px offset — no `outline: none` without replacement
- [ ] **Focus ring not clipped by an overflow ancestor** — every `overflow` hit with a focusable descendant renders the full ring **plus** its 2px offset. Known case: the console tab strip (`overflow-x: auto` computes `overflow-y: auto` and cuts the ring vertically) — fix with `padding-block`, never `outline-offset: 0`
- [ ] **Text resize to 200%** (1.4.4) at all three widths, under *both* browser zoom **and** text-only resize (root 32px): no clipped/overlapped text, no lost content, no horizontal scroll. Re-run with the `A11yMenu` text-size boost on — it must reflow, not just restyle. No px `font-size` pinned on `html`/`body`; `--text-*` stay rem; neither `index.html` carries `user-scalable=no`/`maximum-scale=1` (the "no zoom/lightbox" gallery rule must **not** be implemented by disabling page zoom). Fixed-px boxes break first: CTA bar, a11y button, 88px monogram, pill badges, the 6-line clamp, DressCard height in a mixed grid
- [ ] **`Gallery` keyboard + AT pass on a multi-photo detail page (≥3 images)** — the single-photo state hides the chrome and passes vacuously. Every image reachable by keyboard alone via focusable prev/next or thumbnails, or arrow-key nav on a focusable region; **scroll-snap swipe is not a keyboard affordance**. Every control has an accessible name, and current position is exposed to AT (`aria-current` + labelled indicators, or a polite live region — the prototype's `aria-hidden` dots do not count)
- [ ] Focus order matches visual order in RTL · every input has a visible label, errors via `aria-describedby`
- [ ] Dress photos take alt from the dress name; ornaments and monogram art `aria-hidden`
- [ ] No colour-only signals · touch targets ≥44×44 @mobile · reduced motion: transitions `none`, skeleton static, **scroll-snap retained**
- [ ] `/accessibility` (הצהרת נגישות) exists with real content, linked from every storefront page footer
- [ ] `A11yMenu` is **first-party** — contrast boost, text size, readable font, underlined links, stop animations. **No third-party overlay.** Base experience passes AA with it untouched
- [ ] Keyboard-only pass of catalog → detail → CTA → contact panel → Esc; screen-reader pass of the catalog, **the dress detail**, and one console form
- [ ] One manual pass with the OS/browser in dark mode: time fields, date field, capacity spinner, `LoginForm` autofill and scrollbars all stay cream/paper with ink text

## 9. Deferred here by the gate, and unfixed defects

- [ ] **PRE-1 — fixed-element collision @375** ([test-results.md](test-results.md), **Critical**). The fixed `A11yMenu` button rendered on top of the `BookingCTA` bar and swallowed **60×44px, 13.8%** of the primary booking CTA. **Design fix applied 2026-07-25** (critic re-run ACCEPT): the button's `inset-block-end` below 768 is the `--space-a11y-clearance` token (92px = the 80px bar footprint — 56px button + `--space-3` ×2 — plus `--space-3`), lifting it clear of the bar independent of its own height. **Build-time check (still open):** assert zero `getBoundingClientRect()` overlap on catalog, empty and detail at 375. Note `A11yMenu` is storefront-only, so there is **no** console collision to check — `apps/manage` ships no fixed accessibility button (the demo-prototype console overlap does not reproduce); the console's concern is PRE-2 bottom-padding, not PRE-1.
- [ ] **PRE-2** — on `/about` and the console (no fixed bar) the scrollable page reserves bottom padding ≥ the button's footprint, so it never rests on a Waze link or a form input
- [ ] **Error-block identity** — the inline validation error ("חילוט חייב להיות בין 0 ל-100") must read as *this field needs a different value*, not *you broke something*
- [ ] **Hours-card closed-today variant** — ink, not danger; leads the card (see also the `BoutiqueHeader` closed-today item in §6 — these are two different surfaces)

## 10. Brand / anti-generic

- [ ] **No promo language anywhere**: no discount badges, sale ribbons, entry popups, threshold bars, countdowns, urgency copy
- [ ] **Tap depth from a cold Instagram/WhatsApp link** — `/` paints the grid directly (no interstitial of any kind), a detail is **1 tap** from a card, `BookingCTA` is **0 taps**. `/about` and `/accessibility` are reached from the footer, **not** a menu: no hamburger, no nav drawer, no mega-nav — the inventory specifies no storefront nav component, so shipping one is a defect. `grep -rniE 'hamburger|drawer|nav-?toggle|mega-?nav|aria-expanded' apps/storefront/src` empty
- [ ] No purple/blue SaaS gradients, no neon accents, no icon-per-feature clutter
- [ ] No Lorem ipsum, no marketing fluff — real Hebrew copy or a real i18n key
- [ ] Storefront reads as a boutique, not a tech product; photography does the talking

## 11. Mechanical checks

Run from `Frontend/`. These catch drift cheaply; none of them replaces the browser passes above.

```bash
# raw hex outside theme.css
grep -rnE '#[0-9a-fA-F]{6}\b' apps/*/src packages/ui/src --include='*.ts*' --include='*.css' | grep -v theme.css

# physical direction properties (also check JSX style objects, which this misses)
grep -rnE '(padding|margin|border)-(left|right)|text-align:\s*(left|right)|\b(ml|mr|pl|pr)-[0-9]' packages/ui/src apps/*/src
grep -rnE 'marginLeft|marginRight|paddingLeft|paddingRight|left:|right:' packages/ui/src apps/*/src

# banned weights + Hebrew tracking
grep -rnoE 'font-weight:\s*[0-9]{3}|\bfont-(thin|extralight|light|medium|semibold|extrabold|black)\b|tracking-' apps/*/src packages/ui/src | sort -u

# Tailwind default palette, incl. the suffix-less ones
grep -rnE '\b(bg|text|border)-(gray|slate|zinc|blue|purple|indigo|red|green|white|black)\b' apps/*/src packages/ui/src

# fonts: banned families, Tailwind family utilities, literal families outside theme.css
grep -rniE 'playfair|didot|cormorant|bodoni|baskerville|\bgeorgia\b|times new roman' apps/*/src apps/*/index.html packages/ui/src apps/*/package.json packages/ui/package.json
grep -rnE '\bfont-(serif|sans|mono)\b' apps/*/src packages/ui/src
grep -rn 'font-family' apps/*/src packages/ui/src | grep -v 'var(--font-'

# motion: expect exactly one hit (the Skeleton pulse)
grep -rnE '(transition|animation)[^;]*[0-9]+m?s|duration-\[?[0-9]|\bease-in|\blinear\b|cubic-bezier|transition:\s*all' packages/ui/src apps/*/src

# line-heights paired (must print 7)
grep -c -- '--text-.*--line-height' packages/ui/src/theme.css

# focus removed without replacement
grep -rnE 'outline:\s*none|outline-none|outline-0' packages/ui/src apps/*/src

# hand-formatted money — whitelist by FILE, not by line
grep -rn '₪' apps/*/src packages/ui/src | grep -v -e 'Price' -e 'TypesSection'

# runtime Google Fonts
grep -rn 'googleapis.com\|gstatic.com' apps/*/index.html apps/*/src packages/ui/src

# console must not keep local primitives or dead links
grep -rnE '(inputClass|primaryButtonClass|secondaryButtonClass|dangerButtonClass|labelClass|cardClass)' apps/manage/src
grep -rn 'href="#"' apps/manage/src
grep -rnE '[0-4]\s*/\s*4' apps/manage/src

# storefront must not grow a nav, favorites, or a history-based back
grep -rniE 'hamburger|drawer|nav-?toggle|mega-?nav' apps/storefront/src
grep -rniE 'favorit|localStorage|heart' packages/ui/src apps/storefront/src
grep -rnE 'history\.back|navigate\(-1\)|router\.back' apps/storefront/src

# timezone must be explicit
grep -rnE 'getDay\(\)|getDate\(\)|toLocaleDateString|toLocaleTimeString' apps/*/src packages/ui/src
```

Then:

```bash
pnpm -r lint && pnpm -r typecheck && pnpm -r build
pnpm -r test        # note: no `test` script exists in any package yet — the F9 build adds it
```

Browser QA: `/spartan:qa <url> <feature>` — keyboard pass, reduced-motion pass, 200% resize pass, and the three breakpoints.

## 12. Measured pre-build baseline

Full results: **[qa-browser-baseline.md](qa-browser-baseline.md)** (Playwright/Chromium, 2026-07-24, both apps, three viewports + reduced-motion).

The F9 build has not started. `packages/ui` exports a 3-value placeholder and no components; there is no `theme.css`, no `@fontsource`, no i18next. Both apps render a centred placeholder. §1–§10 are therefore not yet checkable — but the placeholders already violate the token laws, **measured in a real browser**, and must not survive the build:

| # | Where | Violation | Measured |
|---|---|---|---|
| 1 | both `App.tsx:14` | `--color-gold` **carrying text on cream** | **2.38:1** (needs 4.5) — the exact failure the three-gold law exists to prevent |
| 2 | both `App.tsx` | `font-light` on a Hebrew heading | computed `font-weight: 300` — banned |
| 3 | both `App.tsx` | `tracking-wide` on Hebrew | computed `letter-spacing: 0.75px` — must be 0 |
| 4 | both apps | **neither brand font loads** | `document.fonts` empty; Hebrew renders in the system sans stack |
| 5 | both `App.tsx` | `text-3xl` = Tailwind default | computed **30px**, token is 36px |
| 6 | `packages/ui/src/index.ts` | placeholder token object, self-documented as pre-gate | gate has passed — due for replacement |
| 7 | both `index.css` | `@import "tailwindcss"` only, no theme import | — |

Already correct and worth keeping: `lang="he" dir="rtl"` on both documents · viewport meta with no `user-scalable=no` · one `<main>` and one `<h1>` per app · ink-on-cream measured at **15.24:1**, matching tokens.md exactly · zero console/network errors · no horizontal scroll at any width.

---

## Gate status

The design package passed the critic at rev 2. Final approval **was gated on interview synthesis** ([test-results.md](test-results.md) records **0 of 8 participant sessions run**; five bets — mixed price grid, "הוזמן" wording, contact-panel-as-CTA, empty boutique, blocker tone — are unvalidated); on 2026-07-25 the user **waived the interview gate by directive** to start the F9 build, so those five bets are carried as post-ship validation risks.

What *has* run is the automated half: axe-core 4.11 against the prototype on 2026-07-23 — **0 WCAG 2.0 A/AA violations**, 264 `color-contrast` node checks passed, confirming the three-gold law under measurement. It also surfaced **PRE-1 (Critical)**, a fixed-element collision; its **design fix landed 2026-07-25** as the `--space-a11y-clearance` token (design-critic re-run ACCEPT), leaving only the build-time zero-overlap verification open (§9).

So this checklist is a usable build gate throughout. If interview sessions later move a screen, re-run `design-critic` and re-issue this checklist against the revised specs.
