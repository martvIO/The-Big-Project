---
tags: [frontend, design, ui, tailwind, accessibility]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Design Tokens

**What it is.** One `@theme` block in [[frontend/packages/ui/src/theme.css]] is the single source of
truth for every colour, font, size, space, radius, shadow and motion value in both apps. This is
Tailwind 4's CSS-first configuration — there is no `tailwind.config.js`.

## The mirror and the test that holds it

[[frontend/packages/ui/src/tokens.ts]] restates the same block as a TypeScript object for consumers
that cannot read a CSS custom property at module scope — the `theme-color` meta tag, the canvas
monogram fill. [[frontend/packages/ui/src/__tests__/tokens.test.ts]] **parses the `@theme` block
out of the CSS** and asserts the object matches it key-for-key, so drift is a red test rather than
a silent divergence.

## The gold law

Three golds, and only one of them is legal for text ([[.planning/design-config.md]]):

| Token | Value | Allowed use |
|---|---|---|
| `--color-gold` | `#C5A059` | decoration and CTA **backgrounds** only |
| `--color-gold-strong` | `#9E7B36` | borders, large accents |
| `--color-gold-text` | `#7F612B` | the **only** text gold |

Gold text on cream fails AA. That is not an opinion in a doc — the same test file computes WCAG
relative luminance and contrast ratios straight from the token hexes, because IS 5568 is the legal
floor here ([[Accessibility Compliance]]).

## Tokens that carry behaviour, not just looks

`--cta-bar-height`, `--space-a11y-clearance` and `--space-a11y-footprint` are layout contracts:
they are how the fixed accessibility trigger and the booking CTA bar avoid each other and how a
scrolling document reserves the space the fixed trigger owes it. Changing them changes behaviour.

## The traps

- **Tailwind v4 auto source-detection skips `node_modules`,** and `@boutique/ui` is reached only
  through the pnpm workspace symlink. Without the `@source "../src"` line in `theme.css`, **no
  class used solely inside `packages/ui` is ever compiled** — both apps break at once, silently.
- **A raw hex outside `theme.css` bypasses the system.** [[frontend/scripts/qa-greps.sh]] fails the
  build on `#rrggbb` anywhere in the storefront source.
- **Fonts are declared per weight.** A bare `@fontsource` import ships 400 alone and faux-bolds
  Hebrew, so each used weight is imported explicitly.

## Related

- [[.planning/design/system/tokens.md]] — the binding token spec ·
  [[.planning/design/system/components.md]]
- [[RTL And Bidi Isolation]] · [[Hebrew First UX]] · [[Accessibility Compliance]]
- [[frontend/packages/ui/src/lib/styles.ts]] · [[frontend/packages/ui/src/index.ts]]
