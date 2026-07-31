---
tags: [frontend, ui, test, vitest, accessibility, rtl]
sources: [frontend/packages/ui/src/__tests__/chrome-composites.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/chrome-composites.test.tsx
blob: 52d14474edafae4ed4853ad04201c28381988e27
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/chrome-composites.test.tsx

**Role.** The suite for the storefront's persistent page chrome — the fixed booking bar, the contact link block, and the first-party accessibility menu. Two of its assertions are not behavioral at all but *class-string* assertions, deliberately: they guard against Tailwind utilities that compile to nothing, which no rendered-DOM assertion can see.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `describe("BookingCTA")` | suite | fixed-bar rendering plus the `inset-x-0` / `inset-inline` utility-name guard |
| `describe("ContactPanel")` | suite | asserts the exact `href` each channel builds: `tel:`, `wa.me`, Waze, Instagram |
| `describe("A11yStatementLink")` | suite | the statement link resolves to the passed `href` |
| `describe("A11yMenu")` | suite | disclosure semantics, `<html>` boost attributes, dangling-IDREF avoidance, CTA clearance |
| `contactLabels` / `a11yControls` | const | Hebrew label fixtures — the components take every string as a prop |

## Behavior

The `afterEach` strips `data-a11y-contrast` and `data-a11y-text-size` from `document.documentElement`, because [[frontend/packages/ui/src/components/A11yMenu.tsx]] toggles boosts by writing attributes on `<html>` — a side effect that outlives Testing Library's `cleanup()` and would leak into every later file in the same worker.

**The A11yMenu block is the load-bearing part, and it asserts what the component must *not* be.** It checks that `role="menu"` and `role="menuitemcheckbox"` are absent, that the trigger carries no `aria-haspopup` (which is synonymous with `aria-haspopup="menu"`), and that the five controls are `aria-pressed` toggle buttons inside a single `role="group"` wired both ways — `group[aria-labelledby] === trigger.id` and `trigger[aria-controls] === group.id`. It further asserts each control is `toContainElement`'d by the group, not merely present on the page, so a refactor that moves a control outside the panel fails here rather than in an axe run. A separate case asserts `aria-controls` is *dropped* when closed: the panel is unmounted, and a live IDREF to a missing element is exactly what axe reports as `aria-valid-attr-value`.

**Two class-string assertions exist because the DOM cannot show a class that emitted no CSS.** `BookingCTA` must contain `inset-x-0` and must *not* contain `inset-inline` — the latter is the CSS property name, not a Tailwind utility, so it compiles to nothing and the bar shrink-wraps to its content at 375px while still rendering perfectly in jsdom. The same trap is swept workspace-wide by [[frontend/packages/ui/src/__tests__/tokens.test.ts]]; this file catches the specific regression on the CTA. Likewise the `hasBookingBar` case asserts the class string carries `var(--space-a11y-clearance)`, the PRE-1 token that lifts the a11y trigger clear of the bar below 768.

`ContactPanel` is checked by accessible name → `href` pair, which simultaneously proves the Hebrew labels arrive as props (the package ships no i18n) and that the deep-link construction is right. Note it passes only safe URLs; the scheme-rejection half of that contract lives in [[frontend/packages/ui/src/__tests__/url.test.ts]].

## Depends On

- [[frontend/packages/ui/src/components/BookingCTA.tsx]] — subject
- [[frontend/packages/ui/src/components/ContactPanel.tsx]] — subject
- [[frontend/packages/ui/src/components/A11yMenu.tsx]] — subject (`A11yMenu`, `A11yStatementLink`)
- [[frontend/packages/ui/src/test/setup.ts]] — jest-dom matchers and RTL cleanup, via [[frontend/packages/ui/vitest.config.ts]]
- [[Vitest]] · [[Testing Library]] · [[React]]

## Depended On By

Nothing imports a test file. It runs via `pnpm --filter @boutique/ui test`.

## Concepts

- [[Accessibility Compliance]]
- [[Design Tokens]]

## Tests

This *is* the test. The components' own visual/axe coverage lives in [[frontend/packages/ui/src/__tests__/A11y.test.tsx]] and the browser-QA pass.

## Notes

Reading a `className` in a unit test is normally a smell; here it is the only available detector for a utility that never existed. Do not "clean these up" into DOM assertions — they would pass on the broken code. See [[.planning/design/qa-checklist.md]] for the mechanical companion greps and [[frontend/scripts/qa-greps.sh]] for their implementation.
