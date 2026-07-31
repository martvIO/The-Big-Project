---
tags: [frontend, storefront, react, accessibility, disclosure]
sources: [frontend/apps/storefront/src/components/DescriptionClamp.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/components/DescriptionClamp.tsx
blob: a724211c8ba5cfcc92b9d248ae8b3db5100a82a7
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/components/DescriptionClamp.tsx

**Role.** The dress description's six-line clamp with a real disclosure toggle — line-based rather than pixel-height, with overflow **measured** from the DOM instead of guessed from a character count, and re-measured when the A11y menu changes the root font size.

**Module.** [[frontend/apps/storefront/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `DescriptionClamp` | component | `{text}` — the clamped paragraph plus its show-more/less `Button` |

## Behavior

State is two booleans: `expanded` (the toggle) and `clampable` (whether a toggle is needed at all). A layout-time `useEffect` compares `scrollHeight > clientHeight + 1` on the paragraph ref, skipping the measurement while expanded — there is no overflow to detect then, and the button must stay rendered regardless, which is why the render condition is `clampable || expanded`.

Three non-obvious commitments. **`line-clamp-6`, never a fixed pixel height** — qa §8 names a px-height clamp as a 200%-text-resize breaker, because the text grows and the box does not. **Measurement, not a character threshold** — the same string wraps to more lines at 200% text size, so a description needing no toggle at 100% needs one at 200%, and a fixed character count cannot know that; measuring also survives a narrow column and a single unbroken word. **A `MutationObserver` on `document.documentElement` attributes** — the `A11yMenu`'s boosts are data attributes on `<html>`, and `data-a11y-text-size` moves the root font size while firing **no** resize event. Without the observer the description silently truncates with no toggle to reveal it, for exactly the visitor who asked for larger text. It watches every attribute rather than filtering to one name, which also covers the readable-font boost at the cost of one extra measure per menu toggle.

The toggle carries both `aria-expanded` and `aria-controls` pointing at the `useId`-generated paragraph id, so the state is exposed to assistive tech rather than implied by the visible label. `text-base` is left to carry the theme's 1.6 line-height — adding a `leading-` utility here would override the token.

## Depends On

- [[frontend/packages/ui/src/components/Button.tsx]] — `variant="ghost"` `size="sm"`
- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`
- [[frontend/packages/ui/src/components/A11yMenu.tsx]] — not imported, but the root data attributes it writes are what the observer exists for
- [[React]] — `useEffect`, `useId`, `useRef`, `useState`
- [[i18next]] — `dress.more` / `dress.less`

## Depended On By

- [[frontend/apps/storefront/src/routes/DressPage.tsx]] — the only consumer, rendered when `dress.description !== null`

## Concepts

- [[Accessibility Compliance]]
- [[IS 5568 Accessibility]]
- [[Design Tokens]]

## Tests

- [[frontend/apps/storefront/src/__tests__/DescriptionClamp.test.tsx]]
- [[frontend/apps/storefront/src/__tests__/DressPage.test.tsx]]

## Notes

The effect depends on `[text, expanded]`, so a route change to a different dress re-measures; the resize listener and observer are both torn down in the same cleanup.
