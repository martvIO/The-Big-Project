---
tags: [frontend, storefront, test, vitest, accessibility, text-resize, jsdom]
sources: [frontend/apps/storefront/src/__tests__/DescriptionClamp.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/DescriptionClamp.test.tsx
blob: 57767ad6d75cf6210a731126928a8d112d143a2f
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/DescriptionClamp.test.tsx

**Role.** Three tests for the one thing about the clamp that no other suite can reach: the toggle appearing and disappearing *because the A11yMenu's text-size boost changed the layout*, with no resize event to hang it on.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `scrollHeight` / `clientHeight` | module state | the two numbers the component measures, hand-driven per test |
| `TEXT` | const | one Hebrew dress description; its length is irrelevant — the stubs decide overflow |

## Behavior

jsdom performs no layout, so `scrollHeight` and `clientHeight` are always 0 and the component's `scrollHeight > clientHeight + 1` test can never fire on its own. `beforeAll` redefines both properties on `HTMLParagraphElement.prototype` as getters over module-level variables, which is what lets a test say "the same text now overflows six lines" without touching the text.

The middle test is the point of the file. It renders with the text fitting, asserts no toggle, then sets `data-a11y-text-size` on `<html>` inside `act` and asserts the toggle has appeared with `aria-expanded="false"`. That attribute is how the accessibility menu applies its `font-size: 1.2rem` boost, and **it fires no resize event** — so a component listening only to `resize` would leave a visitor who asked for larger text with a silently truncated description and no way to reveal the tail. What actually makes the assertion pass is the component's `MutationObserver` on the document element, which watches *every* attribute rather than filtering to one name. The third test drives the same attribute on and back off in a single `act` and requires the toggle to be gone again, which is the assertion that would fail if the observer only ever latched `clampable` to `true`.

Scoping the stub to `HTMLParagraphElement.prototype` matters: it is narrow enough that the surrounding `Button` and container keep jsdom's zeros, so nothing else in the tree accidentally reads as overflowing. The `afterEach` removes the attribute rather than the property definitions, which stay for the file's lifetime.

## Depends On

- [[frontend/apps/storefront/src/components/DescriptionClamp.tsx]] — the subject
- [[frontend/apps/storefront/src/i18n/index.ts]] — bare side-effect import; the toggle labels asserted are the literal Hebrew «עוד»
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Accessibility Compliance]]

## Notes

[[frontend/apps/storefront/src/__tests__/DressPage.test.tsx]] also exercises the clamp, but through `HTMLElement.prototype` stubs held constant for a render — it covers the `aria-controls`/`aria-expanded` wiring and the fits-already case. The dynamic boost is only covered here.
