---
tags: [frontend, ui, design-tokens, typescript, mirror, accessibility]
sources: [frontend/packages/ui/src/tokens.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/tokens.ts
blob: 8cb4dbb041c8fe0e611b93015909200f1e7aae61
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/tokens.ts

**Role.** A TypeScript **mirror** of the `@theme` block in [[frontend/packages/ui/src/theme.css]], for the consumers that cannot read a CSS custom property — a `<meta name="theme-color">` tag, a canvas fill, any module-scope JS. It is not the source of truth; the CSS is, and a test enforces that they never diverge.

**Module.** [[frontend/packages/ui/src/_index]] · **Layer.** frontend / design system

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `themeTokens` | const | the full flat map, keyed by CSS custom-property name (`"--color-gold": "#C5A059"`), `as const` |
| `tokens` | const | ergonomic accessor — `tokens.color.gold` etc., colors only, camelCased |
| `ThemeTokens` | type | `typeof themeTokens` |
| `Tokens` | type | `typeof tokens` |

## Behavior

**Two shapes, one truth.** `themeTokens` carries every declaration in the `@theme` block — the fourteen colors, two font stacks, the seven type steps *with their paired `--text-*--line-height` values*, the spacing scale, radii, shadows, `--ease-out`, the three `--motion-*` durations, the four `--animate-*` shorthands, and the three derived `calc()` layout tokens (`--cta-bar-height`, `--space-a11y-clearance`, `--space-a11y-footprint`). `tokens` is a much narrower convenience object exposing **only colors**, camelCased, for the handful of call sites that want `tokens.color.bg` rather than a string key lookup.

**Drift is a red test, not a silent divergence.** [[frontend/packages/ui/src/__tests__/tokens.test.ts]] reads `src/theme.css` off disk, parses the single `@theme` block into a flat map, whitespace-normalises both sides, and asserts `themeTokens` equals it **key-for-key** — an added, removed or edited CSS token fails the suite until this file is updated. `tokens.color.*` is pinned to the same values by the same suite. Note the parse resolves `src/theme.css` from `process.cwd()`, which only works because pnpm runs the package's `test` script with cwd at the package root.

The same test file also asserts things this mirror cannot express: the AA-corrected `--color-border-input` (`#8A7A5E`, replacing a `#B9A98F` that measured 2.03:1) and `--color-focus` (`#7F612B`), and it computes WCAG relative luminance from the hexes rather than trusting the eye. **IS 5568 / WCAG 2.0 AA is a legal requirement in this product**, so editing a color here without re-running that suite is a compliance risk, not a taste question.

A value copied out of this file into a component is a defect: [[frontend/scripts/qa-greps.sh]] bans raw hex colours in app source precisely so colour keeps flowing from the token layer.

## Depends On

- [[frontend/packages/ui/src/theme.css]] — the authoritative `@theme` block this mirrors

## Depended On By

- [[frontend/packages/ui/src/index.ts]] — re-exports both constants and both types
- [[frontend/packages/ui/src/components/Button.tsx]] · [[frontend/packages/ui/src/components/Input.tsx]] · [[frontend/packages/ui/src/components/DressGrid.tsx]]
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]]

## Concepts

- [[Design Tokens]]

## Tests

- [[frontend/packages/ui/src/__tests__/tokens.test.ts]] — parity, paired line-heights, contrast values, `@source` coverage

## Notes

`--animate-skeleton` is the one sanctioned literal-duration animation (`1.5s`); every other `--animate-*` composes `--motion-*` and `--ease-out`. That exemption is documented in the CSS, not here — this file only copies the resulting string.
