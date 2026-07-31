---
tags: [frontend, ui, react, layout, responsive, catalog]
sources: [frontend/packages/ui/src/components/DressGrid.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/DressGrid.tsx
blob: b7fface42668df738e16d49d4705dbdee9fdbedc
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/DressGrid.tsx

**Role.** The catalog's one responsive grid container: 2 columns at 375px, 3 at the `md` breakpoint, 4 at `xl`, with the gutter stepping 16px → 24px at `md` and then *staying* 24px. It is a pure layout shell — it renders `children` and applies no card styling, so the grid and the card ([[frontend/packages/ui/src/components/DressCard.tsx]]) can change independently.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `DressGrid` | fn | `{children, className?}` → a `<div>` with the catalog grid utilities |
| `DressGridProps` | type | the two props above |

## Behavior

The column and gap utilities are hard-coded, not props, because the catalog has exactly one grid and a second configuration would be a second design. The comment records the non-obvious half of the spec: the gap steps once and stops. The design tokens name only the endpoints (mobile and desktop), and a naive reading would ramp the gutter again at the largest breakpoint; holding 24px through `xl` is the deliberate reading of "tokens.md's endpoints, honored at the middle too".

`className` is appended through `cn()`, which is a **plain join with no Tailwind class-merge** — a caller passing `grid-cols-3` does not reliably win over the component's `grid-cols-2`, because same-specificity utilities resolve by stylesheet order, not by argument order. Do not treat call-site column overrides as a supported pattern; if a second layout is genuinely needed, it belongs in this file behind a named variant.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`
- [[Tailwind CSS]] — the grid and breakpoint utilities

## Depended On By

- [[frontend/apps/storefront/src/routes/CatalogPage.tsx]] — the only app consumer; also wraps the loading skeletons so the skeleton grid matches the loaded grid exactly
- [[frontend/packages/ui/src/index.ts]] — barrel re-export

## Concepts

- [[Design Tokens]]

## Tests

- [[frontend/packages/ui/src/__tests__/catalog-composites.test.tsx]]
