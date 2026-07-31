---
tags: [frontend, ui, test, vitest, accessibility]
sources: [frontend/packages/ui/src/__tests__/display-primitives.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/display-primitives.test.tsx
blob: 94d380a6f426d1788caa9159baaeba90b0c1a590
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/display-primitives.test.tsx

**Role.** The small suite for the three purely presentational primitives — loading skeleton, empty state, section heading. Short by design: what these components owe is the AT contract (hidden vs. announced, correct heading level), not behavior.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `describe("Skeleton")` | suite | `aria-hidden="true"`, one child per requested text line, `animate-skeleton` token class |
| `describe("EmptyState")` | suite | title, body and the optional `action` slot all render |
| `describe("SectionHeading")` | suite | `as="h1"` produces a real level-1 heading whose name excludes the ornament |

## Behavior

The `Skeleton` cases assert the two things that actually break. First, the wrapper carries `aria-hidden="true"` — a shimmer that a screen reader reads as content is worse than no placeholder at all — and `lines={4}` yields exactly four children, so the `lines` prop is not quietly ignored. Second, the class string contains `animate-skeleton`, the named token animation; the reduced-motion freeze lives in the global block in [[frontend/packages/ui/src/theme.css]], not in the component, so asserting the token name here is what ties the two together. A hand-rolled `animate-pulse` would render identically in jsdom and ignore `prefers-reduced-motion`.

`SectionHeading` is checked through `getByRole("heading", { level: 1, name: … })` with `ornament` on. That single query covers both halves: the `as` prop must map to a real heading tag (not a styled `<div>`), and the decorative gold hairline must stay `aria-hidden` — if it leaked into the accessible name, the name match would fail.

`EmptyState` gets a plain render check for title, body and a passed-in `action` node. There is no hidden contract to guard; the component is a layout wrapper and its restraint (icon-less by default) is a design rule, not a testable one.

## Depends On

- [[frontend/packages/ui/src/components/Skeleton.tsx]] — subject
- [[frontend/packages/ui/src/components/EmptyState.tsx]] — subject
- [[frontend/packages/ui/src/components/SectionHeading.tsx]] — subject
- [[frontend/packages/ui/src/test/setup.ts]] — jest-dom + RTL cleanup
- [[Vitest]] · [[Testing Library]] · [[React]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Accessibility Compliance]]
- [[Design Tokens]]

## Tests

This is the test.

## Notes

`Skeleton`'s `variant="block"` and the `w-2/3` last-line taper are unasserted — low value, since neither has an accessibility or layout-collapse failure mode.
