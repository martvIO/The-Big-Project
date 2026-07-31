---
tags: [frontend, ui, test, vitest, manage, accessibility]
sources: [frontend/packages/ui/src/__tests__/console-composites.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/console-composites.test.tsx
blob: bf2178ee36e43c14281acfd7f34690b7d2f28d53
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/console-composites.test.tsx

**Role.** The suite for the three owner-console composites — the app frame, the onboarding checklist, and the missing-cancellation-policy banner. Its sharpest assertion is negative: the console nav must never become a `role="tab"` set.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `describe("ConsoleShell")` | suite | `aria-current="page"` on the active nav item, no `tab` role, an `h1`, and callback routing |
| `describe("SetupProgress")` | suite | derived count interpolation and "first incomplete section" targeting, at 0/4, 2/4 and 4/4 |
| `describe("PolicyBlockerBanner")` | suite | message renders and the action button routes through `onAction` |
| `nav` / `items` | const | Hebrew fixtures — every string is a prop |

## Behavior

The `ConsoleShell` case asserts `aria-current="page"` on the active item *and* `screen.queryByRole("tab")` being null in the same test. That pairing is the point: the nav looks like a tab row from 768px up, and the obvious "improvement" is to give it `role="tab"` / `role="tablist"`. Doing so silently promises the APG keyboard contract (arrow-key roving focus, Home/End, focus management on panel swap) that [[frontend/packages/ui/src/components/ConsoleShell.tsx]] does not implement — a worse outcome for a screen-reader user than a plain `<nav>`. The same test also pins the `h1`, which is `sr-only` in the component; it is the console's document title for AT and would vanish unnoticed in a layout refactor.

`SetupProgress` is verified as *derived, never authored*. `countLabel` is a `(done, total) => string` callback, so the test supplies its own template and asserts the interpolated `"2/4 הושלמו"` — there is no hardcoded fraction anywhere in the component or the apps. The `onGoTo` assertion checks that the CTA targets `"types"`, the first item with `done: false`, not the first item overall and not the last. A second case rerenders the same fixture all-false and all-true, covering the two boundaries where an off-by-one or a `firstIncomplete` of `undefined` would surface; note that at 4/4 the CTA button is absent by design (the component only renders it when a `firstIncomplete` exists).

`PolicyBlockerBanner` gets the minimum that matters — the message is visible and the action fires — because the rest of its contract is visual (gold-strong inline-start stripe, `warning-text` on paper, no icon, never red) and belongs to the design-token guard in [[frontend/packages/ui/src/__tests__/tokens.test.ts]] and browser QA.

All three composites take Hebrew strings as props; `packages/ui` has no i18next dependency, which this file exercises implicitly by passing them.

## Depends On

- [[frontend/packages/ui/src/components/ConsoleShell.tsx]] — subject
- [[frontend/packages/ui/src/components/SetupProgress.tsx]] — subject
- [[frontend/packages/ui/src/components/PolicyBlockerBanner.tsx]] — subject
- [[frontend/packages/ui/src/test/setup.ts]] — jest-dom + RTL cleanup
- [[Vitest]] · [[Testing Library]] · [[React]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Accessibility Compliance]]

## Tests

This is the test.

## Notes

`ConsoleShell` also sets `aria-controls="console-main"` on every nav button, which this suite does not assert — the single-panel swap it describes is real, but the IDREF is only valid while `ConsoleShell` renders its own `<main>`, so a consumer that renders the shell twice would break it silently. Worth an assertion if that ever becomes possible.
