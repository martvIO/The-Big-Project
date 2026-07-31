---
tags: [frontend, ui, test, vitest, accessibility]
sources: [frontend/packages/ui/src/__tests__/Badge.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/Badge.test.tsx
blob: ee853f144e802b40691ba19113e800c536f9028a
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/Badge.test.tsx

**Role.** A single test over [[frontend/packages/ui/src/components/Badge.tsx]] that pins the non-negotiable half of the badge contract: whatever the variant, the *word* is rendered and findable. Colour is decorative; the text carries the meaning.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Contract Pinned

`muted`, `warning` and `danger` each render their Hebrew label into the DOM (`getByText`), asserted across a single `rerender` chain. No class, no colour, no contrast ratio is asserted.

## Behavior

The test deliberately checks nothing about styling, and the reason is a WCAG rule rather than laziness: colour may not be the sole carrier of information (1.4.1), so the badge is correct exactly when its label reads standalone — `במלאי (3)`, `אזל מהמלאי`, `בארכיון`. A test that asserted the `border-warning` class would pass on a badge that had lost its text and fail on a legitimate palette change; this one has the opposite, correct sensitivity.

Two variants of the component (`neutral`, `success`) are not exercised — the file uses `rerender` to walk only the three the console actually renders. Contrast is *not* tested here at all; the component's own comment records the reasoning (every variant clears AA as `text-xs`, and there is deliberately no `gold` variant because `gold-strong` measures 3.80:1). That ratio claim lives in [[frontend/packages/ui/src/__tests__/tokens.test.ts]] and the axe run in [[frontend/e2e/a11y.spec.ts]], not here.

No i18n call appears anywhere: like every `packages/ui` component, `Badge` takes its string as a child, and the test supplies Hebrew literals directly.

## Depends On

- [[frontend/packages/ui/src/components/Badge.tsx]] — the subject
- [[Vitest]] — runner (entity)
- [[Testing Library]] — `render` / `rerender` / `screen` (entity)

## Depended On By

- nothing — a leaf test

## Concepts

- [[Accessibility Compliance]]

## Tests

- this *is* the test

## Notes

Badge's `className` pass-through (used by [[frontend/packages/ui/src/components/DressCard.tsx]] for absolute positioning) is untested here; `cn()` performs no class merge, so a consumer class cannot be relied on to override the component's own — never document such an override as supported.
