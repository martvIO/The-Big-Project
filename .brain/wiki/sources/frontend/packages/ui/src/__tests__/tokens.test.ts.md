---
tags: [frontend, ui, test, vitest, design-tokens, accessibility, tailwind]
sources: [frontend/packages/ui/src/__tests__/tokens.test.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/tokens.test.ts
blob: 72f271c35e7c86992d3d759ba48cd0f1c83b36d4
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/tokens.test.ts

**Role.** The design-token guard, and the most unusual test in the repo: it reads `src/theme.css` and `src/components/Button.tsx` off disk as **text**, parses the `@theme` block into a map, and *computes* WCAG relative luminance from the token hexes — so the AA contrast floor is certified arithmetically rather than eyeballed. It also sweeps the whole workspace for Tailwind class names that emit no CSS.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `parseThemeBlock` | fn | extracts the single `@theme { … }` body into `{ "--name": "value" }`, skipping wildcard `initial` clears |
| `luminance` / `contrastRatio` | fn | WCAG 2.0 relative luminance and the `(L1+0.05)/(L2+0.05)` ratio, from a `#RRGGBB` string |
| `norm` | fn | whitespace-collapses a value so multi-line CSS compares equal to the TS mirror |
| `describe("token single-source parity")` | suite | the eight cases below |

## Behavior

**Parity.** `themeTokens` in [[frontend/packages/ui/src/tokens.ts]] is asserted to equal the parsed `@theme` block **key-for-key with `toEqual`** — extra keys on either side fail. [[frontend/packages/ui/src/theme.css]] is the single source of truth; the TS object exists only for consumers that cannot read a CSS custom property at module scope (the `theme-color` meta tag, canvas monogram fills). A final case walks `tokens.color`, camel→kebab-cases each name, and requires the flat mirror to back it, so the ergonomic nested object cannot drift either. The typography case demands all seven size steps ship a paired `--text-*--line-height` **and** that exactly seven such keys exist — an unpaired step would silently inherit Tailwind's default leading.

**Certified contrast, not asserted contrast.** The `primary CTA contrast` block reads `Button.tsx` as text, regex-extracts the `primary:` variant class string, and resolves its `bg-*` / `text-*` utilities back to `--color-*` tokens (last-wins, matching the cascade; a missing `hover:` falls back to the resting value). It then requires ≥ 4.5:1 at rest **and on hover** — the hover pair matters because mobile browsers leave `:hover` latched after a tap, so the failing state is what a bride actually looks at. A "guards the guard" case first reproduces two ratios already published in [[.planning/design/system/tokens.md]] (ink-on-bg ≈ 15.24, gold-strong-on-raised ≈ 3.93), so a broken `luminance` cannot make everything pass. A separate case bars `text-gold-strong` from the variant outright: gold-strong is a non-text UI colour by token law, and a ratio check alone would let it through on a large-text variant.

**Regression pins.** `--color-border-input` must be `#8A7A5E` and the string `#B9A98F` must not appear anywhere in the stylesheet — the old value was 2.03:1, fixed in the F9 Phase-0 pass. `--color-focus` is pinned to `#7F612B`, and `--ease-out` to the token curve, which deliberately *overrides* a Tailwind built-in. Two global opt-outs are matched as raw text: `color-scheme: only light` and `font-synthesis: none`. The `color-scheme` property name is assembled with `["color","scheme"].join("-")` purely so the qa §0 grep over `packages/ui/src` keeps returning exactly one hit — a small but load-bearing trick; spelling it literally here would create a permanent false positive in the checklist.

**Two filesystem sweeps.** The `@source` case resolves the glob declared in `theme.css` for real and asserts `components/BookingCTA.tsx` exists underneath it: Tailwind v4 never scans `node_modules`, and both apps reach this package through the pnpm workspace symlink, so a wrong relative path means every class used only inside `packages/ui` compiles to nothing — silently. The `inset-inline` case walks `packages/ui/src`, `apps/storefront/src` and `apps/manage/src` recursively (skipping `__tests__`) and requires zero occurrences of the CSS *property* name where Tailwind wants the `inset-x` / `inset-s` / `inset-e` *utility*. It asserts up front that all three roots resolved, so a moved directory fails loudly instead of vacuously passing. This is the bug that shrink-wrapped the CTA bar and stacked both gallery arrows on one rect; nothing rendered can see a class that never existed.

Both file reads use `process.cwd()`, which is correct only because pnpm runs each package's `test` script with cwd at the package root.

## Depends On

- [[frontend/packages/ui/src/tokens.ts]] — subject (`themeTokens`, `tokens`)
- [[frontend/packages/ui/src/theme.css]] — read as text, parsed
- [[frontend/packages/ui/src/components/Button.tsx]] — read as text for the `primary` variant classes
- [[Vitest]] · [[Tailwind CSS]] · [[pnpm]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Design Tokens]]
- [[IS 5568 Accessibility]]

## Tests

This is the test. Published ratios live in [[.planning/design/system/tokens.md]]; the mechanical raw-hex ban is in [[frontend/scripts/qa-greps.sh]].

## Notes

This file is coupled to source *text*, not source behavior: the `primary:` regex breaks if the variant map is reformatted, and `parseThemeBlock` assumes a single `@theme` block whose first `}` closes it (a nested rule inside it would truncate the parse). Both are acceptable trades for coverage nothing else can provide, but a failure here may mean "formatting changed", not "a token regressed" — read the assertion before changing a colour.

Only the `primary` Button variant is contrast-certified. The other three variants, and every non-Button colour pair in the product, are unguarded.
