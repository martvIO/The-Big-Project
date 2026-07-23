# Design QA Checklist — F9 build

**Created**: 2026-07-23 · **Status**: written against design package rev 2 (gate PASSED) · **Target**: `packages/ui`, `apps/storefront`, `apps/manage`
**Binding sources**: [tokens.md](system/tokens.md) · [components.md](system/components.md) · [screens/design-system/](screens/design-system/) · [design-config.md](../design-config.md)

This is the build-side half of the design gate. The gate checked the *design*; this checks the *code that implements it*. Round 2 of the critic explicitly deferred two items here (§9). Critical usability findings that survive into the build land here too, per [test-results.md](test-results.md) — "Critical findings that survive into the build become QA items, not deferred debt."

**Run it**: after the F9 build, before the F9 PR merges. Then again per-app as F7 restyle and F10 storefront land.

---

## 0. Preconditions (blocking — nothing below is checkable until these are true)

- [ ] `packages/ui/src/theme.css` exists with a single Tailwind v4 `@theme` block exporting every token from tokens.md
- [ ] Both apps `@import "@boutique/ui/theme.css"` in their `index.css`
- [ ] The placeholder `tokens` object in `packages/ui/src/index.ts` is replaced by values generated from the same source (TS export retained only for non-CSS use — canvas, meta tags)
- [ ] `@fontsource` packages for Frank Ruhl Libre + Assistant installed and imported — **no runtime Google Fonts request in production** (the prototype's CDN link is preview-only)
- [ ] i18next wired with Hebrew as default locale — no hardcoded Hebrew strings in components

> As of 2026-07-23 **none of these are true** — see §12.

---

## 1. The gold law (the single highest-risk token rule)

Raw gold `#C5A059` is 2.38:1 on cream. It never carries text, at any size.

- [ ] `--color-gold` `#C5A059` appears **only** as: CTA button background, hairline ornaments, monogram placeholder art, decorative borders
- [ ] `--color-gold-strong` `#9E7B36` used for meaningful non-text UI only: focused input borders, active tab underline, display accents ≥24px, the exceptions diamond marker, the policy banner stripe
- [ ] `--color-gold-text` `#7F612B` is the **only** gold touching text: links, price emphasis, "בתוקף" version marker
- [ ] Primary CTA = gold background + **ink** text (`#2B2118`, 6.41:1 on gold), never gold text
- [ ] Grep for gold-on-light text: no `color: var(--color-gold)` / `text-gold` anywhere
- [ ] No raw hex `#C5A059`, `#D4AF37`, or any gold literal in `apps/` or `packages/ui` component code

## 2. Token fidelity

- [ ] No raw px values in component CSS — spacing from `--space-1..16` (4/8/12/16/24/32/48/64), radius from `--radius-sm|md|full`
- [ ] No Tailwind default color utilities (`bg-blue-500`, `text-gray-600`, `bg-white`) — every color resolves to a project token
- [ ] Type sizes come from `--text-xs..3xl` — **not** Tailwind's default scale (Tailwind's `text-3xl` is 1.875rem; the token is 2.25rem)
- [ ] Weight law: display font never below 400; body 400 / emphasis 600; **no weight 300 anywhere** (Hebrew thins badly)
- [ ] Letter-spacing is `0` on all Hebrew text — no `tracking-*` utilities on Hebrew runs (`0.02em` allowed only on Latin-only all-caps micro-labels)
- [ ] Shadows are the warm ink-tinted tokens (`rgb(43 33 24 / …)`), never pure black or Tailwind defaults
- [ ] Cards pad `--space-6`; page gutters `--space-4` @mobile / `--space-12` @desktop
- [ ] Single theme — no dark-mode variants shipped (cream is the brand)
- [ ] Images have no hard borders — cream matting + `--shadow-sm`

## 3. RTL & locale

- [ ] `lang="he" dir="rtl"` on `<html>` in both apps ✓ *(already true in both `index.html`)*
- [ ] **Zero physical direction properties in component CSS** — `padding-inline-start`, `margin-inline-end`, `text-align: start|end`, `inset-inline-*`. No `left`/`right`/`ml-`/`pr-` in `packages/ui`
- [ ] Numeric columns use `text-align: end`, not `left`
- [ ] LTR islands present and isolated: phone, `maps_url`, email, Instagram handle, Latin dress names — `dir="ltr"` spans
- [ ] Gallery swipe direction is RTL-correct (first image on the inline-start)
- [ ] Directional motion enters from **inline-start**, not a hardcoded direction
- [ ] Israeli week ordering (Sun-first) in `HoursSection` and `HoursTable`

## 4. The `Price` component (contract, not a suggestion)

- [ ] Every money amount on both apps renders through `Price` — a hand-formatted shekel string in app code is a defect
- [ ] Format is number-then-shekel: **"5,900 ₪"**
- [ ] Numeric run wrapped `dir="ltr"` + `unicode-bidi: isolate`
- [ ] Digits render in body font (Assistant), never the display serif
- [ ] Hidden-price variant "מחיר בתיאום" (muted italic) occupies the **same layout slot at the same height** — verify no card-height jump in a mixed grid
- [ ] Agorot→shekel conversion happens once, in `Price` — not scattered per call site

## 5. Components (`packages/ui`)

Every component ships default / hover / focus-visible / disabled + RTL layout + keyboard operability + Vitest coverage.

- [ ] `Button` — primary/secondary/ghost/danger, sm/md/lg, full-width mobile option, **loading state locks width** (no reflow when the spinner replaces the label)
- [ ] `Input`/`TextArea` — visible label always (placeholder-as-label is a defect), help text, char counter, error tied via `aria-describedby`, `dir` override prop for phone/URL fields
- [ ] `Select` — native `<select>` styled; no custom dropdown shipped
- [ ] `Toggle` — label + description, keyboard operable
- [ ] `TimeField`/`DateField` — native inputs styled
- [ ] `Badge` — neutral/gold/success/danger; gold variant uses `gold-strong` and is large-text-only
- [ ] `Card` — paper bg, radius-md, shadow-sm, hover-elevate variant
- [ ] `Toast` — `role="status"` (success) / `role="alert"` (error), auto-dismiss, **one at a time** (no queue in v1)
- [ ] `Modal` — focus-trapped, `Esc` closes, focus returns to trigger on close, scale 0.97→1 + fade
- [ ] `Skeleton` — text lines, 3:4 image blocks, pulse ≤1.5s, **static under reduced-motion**
- [ ] `EmptyState` — icon-less by default
- [ ] `SectionHeading` — display serif + optional gold hairline, ornament `aria-hidden`
- [ ] `SkipLink` — present and first in tab order on every storefront page
- [ ] `VisuallyHidden`, focus-ring utility exported
- [ ] Nothing from the "NOT in v1" list shipped: no custom dropdowns, carousels beyond the gallery, data tables, charts, avatar menus, dark theme, toast queues

## 6. Screens & states

**Every state below is a real render, not a described one.** The most common miss is shipping only the default.

### Catalog (`/`)
- [ ] Default · Loading (header + 6 skeleton cards) · Error (inline retry **under the header — identity stays intact**)
- [ ] **Empty (critical)** — identity moment: name, essence, hours, inline contact panel, CTA bar, "הקולקציה בדרך" muted. Must not read as broken; the storefront ships before the catalog does
- [ ] Price-hidden mix — no layout jump between a priced and an unpriced card
- [ ] Reserved — "הוזמן" badge top-inline-start, **card not dimmed** (still browsable)
- [ ] No hero carousel; 3:4 crop + cream matting absorbs photo variance
- [ ] Footer carries הצהרת נגישות on every page

### Dress detail (`/dress/{id}`)
- [ ] Default · Loading (3:4 gallery skeleton + text lines)
- [ ] Single photo — gallery chrome (dots/thumbs) hidden **entirely**
- [ ] No photo — monogram placeholder (initial in display serif on paper, gold hairline frame), never a broken-image glyph
- [ ] Reserved — badge beside the name, **CTA still live**
- [ ] Archived / bad id — "השמלה כבר לא זמינה" + back-to-catalog CTA
- [ ] Long description — 6-line clamp + "עוד" expander
- [ ] Size chips are informational `Badge`s, **not selectable controls**
- [ ] Share via Web Share API with copy-link fallback
- [ ] No zoom/lightbox in v1

### Profile & hours (`/about`)
- [ ] Default · Closed today ("סגור היום · נפתח מחר ב-10:00" in **ink, not danger** — closed isn't an error)
- [ ] No exceptions — row absent entirely, no empty "none" line
- [ ] Sparse profile — missing description/social collapse; hours + contact always render
- [ ] No `maps_url` — address as plain text, no dead link
- [ ] Exceptions use `gold-strong` diamond **+ text**, never the marker alone
- [ ] Contact panel: tap-to-call, WhatsApp `wa.me` deep link, **Waze + Google Maps** both present, Instagram
- [ ] Column max 640px, never multi-column

### Manage console
- [ ] First-run (SetupProgress + PolicyBlockerBanner) · Steady (neither) · Saving (button loading, inputs disabled) · Save error (danger Toast + field-level inline errors) · Session expired (401 → LoginForm, same shell header)
- [ ] `PolicyBlockerBanner`: warning-text on paper + gold-strong stripe, **no icon, not red**
- [ ] `TermsSection` immutable-ledger: version chip + date + created-by, **no edit or delete affordance anywhere**, latest marked "בתוקף" in gold-text
- [ ] `LoginForm` generic error preserved verbatim (F5 anti-enumeration — do not "improve" it into an enumeration oracle)
- [ ] Console content capped at 720px at every breakpoint
- [ ] No hairline ornaments on forms (console drops the ornament level)
- [ ] **F7 component APIs, behavior and tests unchanged** — this is a visual restyle; a changed prop signature or a modified F7 test is a defect

## 7. Responsive (375 / 768 / 1440)

- [ ] Catalog grid: 2-col @375 · 3-col @768 · 4-col @1440 (max-width 1200 centered)
- [ ] Booking CTA: bottom bar @mobile only · moves inline into the header @≥768
- [ ] Detail: single column @375 · 55/45 @768 with thumbs · 60/40 @1440 with sticky facts column
- [ ] Console: accordion @375 (one open) · tabs @≥768
- [ ] No horizontal scroll at any of the three widths
- [ ] Tested with a **long Hebrew boutique name** and a long dress name — no overflow or clipped descenders

## 8. Accessibility — IS 5568 / WCAG 2.0 AA (legal floor)

- [ ] Contrast measured in the **built** UI, not assumed from the token table: ink 15.24:1 cream / 13.89 paper · ink-muted 6.15 / 5.61 · gold-text 5.57 · success 6.10 · danger 6.78 · warning-text 5.70 cream / 5.20 paper
- [ ] Non-text boundaries ≥3:1 — `gold-strong` 3.80, `border-input` 3.0+
- [ ] Focus ring on **every** interactive element: 2px `--color-focus`, 2px offset — grep for `outline: none` / `outline-0` with no replacement
- [ ] Focus order matches visual order **in RTL**
- [ ] Skip-link reachable on first Tab on every storefront page
- [ ] Every input has a visible label; errors tied via `aria-describedby`
- [ ] Dress photos take alt from the dress name; ornaments and monogram art `aria-hidden`
- [ ] No color-only signals — status badges carry text, exceptions carry a marker **and** text
- [ ] Touch targets ≥44×44 @mobile; CTA bar 56px; the a11y button itself ≥44×44
- [ ] `prefers-reduced-motion: reduce` ⇒ all transitions `none`, skeleton static, **scroll-snap retained** (navigation, not decoration)
- [ ] `/accessibility` (הצהרת נגישות) page exists with real content and is linked from every storefront page footer
- [ ] `A11yMenu` is **first-party** — contrast boost, text size, readable font, underlined links, stop animations. **No third-party overlay widget.** Base experience passes AA with the menu untouched
- [ ] Keyboard-only pass of each flow: catalog → detail → CTA → contact panel → Esc
- [ ] Screen-reader pass of the catalog and one console form

## 9. Deferred here by the design gate (round 2)

- [ ] **Error-block identity** — the inline validation error (e.g. "חילוט חייב להיות בין 0 ל-100") must read as *this field needs a different value*, not *you broke something*. Round 2 flagged this explicitly; O2/O3 in the usability test probe the same tone question
- [ ] **Hours-card closed-today variant** — verify the built variant against [storefront-profile-hours.md](screens/design-system/storefront-profile-hours.md): ink, not danger; leads the card

## 10. Brand / anti-generic

- [ ] **No promo language anywhere**: no discount badges, no sale ribbons, no entry popups, no free-shipping threshold bars, no countdowns, no urgency copy. This is the clearest de-luxury signal in the Israeli market
- [ ] No purple/blue SaaS gradients, no neon accents, no icon-per-feature clutter
- [ ] No Lorem ipsum and no marketing fluff — real Hebrew copy or a real i18n key
- [ ] Storefront reads as a boutique, not a tech product (the O4 question: would an owner put this link in her Instagram bio?)
- [ ] Photography does the talking; whitespace is generous

## 11. Mechanical checks

Cheap greps that catch most token drift. Run from `Frontend/`:

```bash
# raw hex in app/component code (should be empty — theme.css is the only place)
grep -rnE '#[0-9a-fA-F]{6}\b' apps/*/src packages/ui/src --include='*.ts*' --include='*.css' | grep -v theme.css

# physical direction properties in RTL components (should be empty)
grep -rnE '(padding|margin|border)-(left|right)|text-align:\s*(left|right)|\b(ml|mr|pl|pr|left|right)-[0-9]' packages/ui/src apps/*/src

# banned weight + Hebrew tracking
grep -rnE 'font-light|font-weight:\s*300|tracking-' apps/*/src packages/ui/src

# Tailwind default palette leaking in
grep -rnE '\b(bg|text|border)-(gray|slate|zinc|blue|purple|indigo|red|green)-[0-9]' apps/*/src packages/ui/src

# focus removed without replacement
grep -rnE 'outline:\s*none|outline-none|outline-0' packages/ui/src apps/*/src

# hand-formatted money (must go through <Price>)
grep -rn '₪' apps/*/src packages/ui/src | grep -v 'Price'

# runtime Google Fonts request (must be self-hosted in production)
grep -rn 'fonts.googleapis.com\|fonts.gstatic.com' apps/*/index.html apps/*/src packages/ui/src
```

Then the real checks, which no grep replaces:

```bash
pnpm -r lint && pnpm -r typecheck && pnpm -r build   # oxlint hooks rules + TS
pnpm -r test                                          # component state coverage
```

Browser QA once the apps render something: `/spartan:qa <url> <feature>` — keyboard pass, reduced-motion pass, and the three breakpoints.

---

## 12. Current state — findings against committed code (2026-07-23)

The F9 **build has not started**. `packages/ui` exports a 3-value placeholder object and no components; there is no `theme.css`, no `@fontsource`, no i18next. Both apps render a centered placeholder. So §1–§10 are not yet checkable — but the placeholders themselves already violate the token laws, and these must not survive the build:

| # | File | Violation | Rule |
|---|---|---|---|
| 1 | [App.tsx](../../Frontend/apps/storefront/src/App.tsx#L14) · [App.tsx](../../Frontend/apps/manage/src/App.tsx#L14) | `style={{ color: tokens.color.gold }}` — raw `#C5A059` **carrying text on cream, 2.38:1** | The gold law (§1). This is the exact failure the whole three-gold system exists to prevent, and it currently ships in both apps |
| 2 | both `App.tsx` | `font-light` on a Hebrew heading (weight 300) | Weight law — "never 300 (Hebrew thins badly)" (§2) |
| 3 | both `App.tsx` | `tracking-wide` on Hebrew | "Letter-spacing: 0 for Hebrew (tracking breaks Hebrew)" (§2) |
| 4 | both `App.tsx` | `text-3xl` resolves to Tailwind's 1.875rem, not the token's 2.25rem | Type scale (§2) |
| 5 | both `App.tsx` | Inline `style={{}}` with TS token values instead of CSS custom properties | Tailwind v4 `@theme` mapping (§0) |
| 6 | [index.ts](../../Frontend/packages/ui/src/index.ts) | Placeholder token object, self-documented as pre-gate ("do not extend before that") | The gate has now passed — this file is due for replacement by generated values (§0) |
| 7 | both `index.css` | `@import "tailwindcss"` only — no theme import | §0 |

Both `index.html` files correctly carry `lang="he" dir="rtl"` — that one is already right.

---

## Gate status note

The design package passed the critic at rev 2, but **final approval still gates on interview synthesis** — [test-results.md](test-results.md) records 0 of 8 sessions run, and [interview-status.md](research/interview-status.md) holds the release. Five bets (mixed price grid, "הוזמן" wording, contact-panel-as-CTA, empty boutique, blocker tone) are unvalidated. If sessions change a screen, re-run the critic and re-issue this checklist against the revised specs before using it as a merge gate.
