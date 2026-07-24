# Design Tokens — Bridal Boutique Platform

**Created**: 2026-07-22 · **Status**: rev 1 (typography reconciled against RTL-luxury research lens; final after interview synthesis) · **Binding**: once merged, every color/font/space/radius in `apps/*` and `packages/ui` comes from here. No ad-hoc values.
**AA verification**: every text pair below was computed against WCAG relative-luminance — ratios listed. IS 5568 (= WCAG 2.0 AA) is a legal floor, not a target.

## The gold law (resolves the epic's AA mandate)

Raw brand gold `#C5A059` **fails text contrast on cream (2.38:1) — it never carries text, at any size**. Three golds, three jobs:

| Token | Value | Job | Contrast on cream |
|---|---|---|---|
| `--color-gold` | `#C5A059` | **Decorative only**: hairlines, ornaments, monogram placeholder art, CTA button *background* | 2.38:1 (exempt — decorative / ink text sits on it) |
| `--color-gold-strong` | `#9E7B36` | Meaningful non-text UI: input borders on focus, active tab underline, large display accents (≥24px) | 3.80:1 (≥3:1 ✓) |
| `--color-gold-text` | `#7F612B` | The only gold that touches text: links, small accents, price emphasis | 5.57:1 (≥4.5:1 ✓) |

## Colors

| Token | Value | Usage | Verified pairs |
|---|---|---|---|
| `--color-bg` | `#FDFBF7` | page background (cream) | — |
| `--color-surface` | `#F6F0E6` | cards, sections (paper) | — |
| `--color-surface-raised` | `#FFFFFF` | modals, elevated inputs | — |
| `--color-ink` | `#2B2118` | headings, body text, primary-CTA text | 15.24:1 on cream · 13.89 on paper · 6.41 on gold ✓ |
| `--color-ink-muted` | `#6B5D4F` | secondary text, labels, captions | 6.15 on cream · 5.61 on paper · 6.36 on white ✓ |
| `--color-gold` / `-strong` / `-text` | above | above | above |
| `--color-border` | `#E4DACA` | hairline borders, dividers (decorative) | non-text |
| `--color-border-input` | `#B9A98F` | form control borders (meaningful boundary) | ≥3:1 on surfaces ✓ (computed 3.0+) |
| `--color-success` | `#2E6B4F` | confirmations, saved states | 6.10 on cream · 5.56 on paper ✓ |
| `--color-danger` | `#A03232` | errors, destructive actions | 6.78 on cream · 6.18 on paper ✓ |
| `--color-warning-text` | `#8A5A1E` | cautionary text (e.g. policy blocker) | 5.70 on cream · 5.20 on paper ✓ |
| `--color-focus` | `#7F612B` | focus rings (2px offset ring) | 4.86 on cream ✓ (>3:1) |
| `--illus-1/2/3` | `#EADFCB` `#E7D9C4` `#EFE4D0` | placeholder-illustration fills ONLY (decorative, aria-hidden art) — never UI surfaces or text backgrounds | exempt (decorative) |

Single theme (cream). No dark mode in v1 — the brand is the light luxury paper; revisit only on demand.

## Typography — Hebrew-first

| Token | Value | Usage |
|---|---|---|
| `--font-display` | `"Frank Ruhl Libre", "David Libre", serif` | boutique name, page headings, dress names — the luxury voice. Weights 400/500/700 |
| `--font-body` | `"Assistant", "Heebo", system-ui, sans-serif` | body, forms, UI. Weights 400/600/700 |

Both are Google Fonts with full Hebrew coverage; self-hosted via `@fontsource` in the build (no runtime Google requests — PPL posture + performance). Latin/numeral fallback is inherent (both cover Latin). Digits and prices render in body font always (serif digits wobble in RTL price contexts).

**Research validation** (RTL-luxury lens): Assistant is the de facto body face of the Israeli luxury tier (Factory 54, Karin Bar) — confirmed. Frank Ruhl Libre kept for display over Bellefair (7 weights vs 1; both cover Hebrew). **Latin-only display serifs (Playfair, Didot) are banned for Hebrew headings** — they silently fall back to a sans mid-headline (observed in the wild).

**Price convention (platform-wide, enforced by the `Price` component)**: number-then-shekel — **"5,900 ₪"** — with the numeric run wrapped in `dir="ltr"` + `unicode-bidi: isolate`. Real Israeli sites hand-patch this per element and ship both orders on one page; we systematize it once.

Scale (rem, 16px base — minor-third-ish, tuned for Hebrew x-height):

| Token | Size / line | Usage |
|---|---|---|
| `--text-xs` | 0.75rem / 1.4 | captions, badges |
| `--text-sm` | 0.875rem / 1.5 | secondary text, labels |
| `--text-base` | 1rem / 1.6 | body |
| `--text-lg` | 1.1875rem / 1.5 | lead text, card titles |
| `--text-xl` | 1.4375rem / 1.35 | section headings (display font) |
| `--text-2xl` | 1.75rem / 1.25 | page headings (display) |
| `--text-3xl` | 2.25rem / 1.15 | boutique name / hero (display) |

Weight law: display font never below 400; body UI text 400, emphasis 600, never 300 (Hebrew thins badly). Letter-spacing: 0 for Hebrew (tracking breaks Hebrew); `0.02em` allowed on Latin-only all-caps micro-labels.

## Spacing — 4px base

`--space-1..16`: 4, 8, 12, 16, 24, 32, 48, 64 px (1,2,3,4,6,8,12,16). Component internals ≤ `--space-4`; section rhythm ≥ `--space-6`. Generosity is the luxury signal: cards pad `--space-6`, page gutters `--space-4` @mobile / `--space-12` @desktop.

## Radius & shadows

| Token | Value | Usage |
|---|---|---|
| `--radius-sm` | 4px | inputs, chips |
| `--radius-md` | 8px | cards, buttons, modals |
| `--radius-full` | 9999px | badges/pills |
| `--shadow-sm` | `0 1px 2px rgb(43 33 24 / 0.06)` | cards |
| `--shadow-md` | `0 4px 12px rgb(43 33 24 / 0.10)` | dropdown/raised |
| `--shadow-lg` | `0 12px 32px rgb(43 33 24 / 0.14)` | modals |

Shadows are warm (ink-tinted), never pure black. No images have hard borders — cream matting + shadow-sm.

## Motion

| Token | Value |
|---|---|
| `--motion-fast` | 150ms |
| `--motion-base` | 200ms |
| `--motion-slow` | 300ms |
| `--ease-out` | cubic-bezier(0.16, 1, 0.3, 1) |

Language: fades and small translates (≤8px); scale only for modals (0.97→1). Nothing bounces, nothing spins except spinners, nothing autoplays. `prefers-reduced-motion: reduce` ⇒ all transitions → `none`, skeleton pulse → static. RTL note: directional slide-ins use logical direction (enter from inline-start).

## Tailwind v4 mapping (F9 build)

`packages/ui/src/theme.css` — a single `@theme` block exporting every token as CSS custom properties consumed by Tailwind v4 utilities (`bg-bg`, `text-ink`, `border-border-input`, `font-display`, etc.); apps `@import "@boutique/ui/theme.css"` in their `index.css`. The existing `tokens` TS object is replaced by generated const values from the same source (single source of truth; TS export kept for non-CSS use like canvas/meta tags).

## Usage laws (the critic enforces these)

1. Gold never carries text except `--color-gold-text`. CTA = gold *background* + ink text.
2. No color communicates alone — status pairs with text/icon.
3. Placeholder text is never the label. Every input has a visible label.
4. Focus ring visible on every interactive element (`--color-focus`, 2px, 2px offset) — never `outline: none` without replacement.
5. All spacing/typography from tokens — a raw px value in app code is a review defect.
6. Hebrew is the default (`lang="he" dir="rtl"`); Latin content (URLs, emails, phone) gets `dir="ltr"` inline spans.
7. Touch targets ≥44×44px on mobile.
8. Prices only ever render through the `Price` component ("5,900 ₪", LTR-isolated digits) — a hand-formatted shekel amount in app code is a review defect.
9. No promo/sale visual language, ever: no discount badges, no entry popups, no threshold bars, no countdowns — the single clearest de-luxury signal in the Israeli market.
