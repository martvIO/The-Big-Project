---
tags: [frontend, testing, react, accessibility]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Testing Library

**Purpose.** How every component test in this repo queries the DOM. `@testing-library/react`
16.3, `@testing-library/dom` 10.4 and `@testing-library/jest-dom` 7.0, devDependencies of the
three packages that run [[Vitest]]: [[frontend/packages/ui/package.json]],
[[frontend/apps/storefront/package.json]] and [[frontend/apps/manage/package.json]]. There is no
enzyme, no shallow rendering, and no snapshot testing.

**Cleanup is explicit, not automatic.** RTL's auto-cleanup hooks onto a global `afterEach` that
does not exist here — the Vitest configs leave `globals: false` — so each of the three
`src/test/setup.ts` files calls `cleanup()` in its own `afterEach` and imports
`@testing-library/jest-dom/vitest` for the matchers:
[[frontend/packages/ui/src/test/setup.ts]] · [[frontend/apps/storefront/src/test/setup.ts]] ·
[[frontend/apps/manage/src/test/setup.ts]]. Drop that `afterEach` from a new package and tests
leak DOM into each other.

**No `@testing-library/user-event`.** Interaction tests use `fireEvent` directly — see
[[frontend/packages/ui/src/__tests__/Modal.test.tsx]]. That is a real ceiling: `fireEvent`
dispatches one event, where `user-event` would replay the whole browser sequence (focus, keydown,
keyup, pointer). Anything depending on that sequence — focus trapping in particular — is not
provable here and is deferred to [[Playwright]].

**Trap.** The role-first query style is also this repo's cheapest accessibility check, so a
`getByRole("button", { name: … })` that starts failing usually means the accessible name broke,
not the test. With Hebrew UI copy the accessible name is Hebrew — see
[[frontend/packages/ui/src/__tests__/DressCard.bidi.test.tsx]].

## Related

- [[Vitest]] · [[jsdom]] · [[React]] · [[Accessibility Compliance]] · [[RTL And Bidi Isolation]]
