---
tags: [frontend, manage, test, vitest, jsdom, testing-library, dialog]
sources: [frontend/apps/manage/src/test/setup.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/test/setup.ts
blob: 0f808f9484092e74435ffc7e92736089668489d1
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/src/test/setup.ts

**Role.** The console's single Vitest setup file. It does three things and no more: loads `jest-dom`'s matchers, registers Testing Library's `cleanup` by hand (auto-cleanup cannot self-install under `globals: false`), and monkey-patches jsdom's partial `HTMLDialogElement` so the `@boutique/ui` `Modal` — a real `<dialog>` — can be opened and closed in tests at all.

**Module.** [[frontend/apps/manage/src/test/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| side-effect import | — | `@testing-library/jest-dom/vitest` — adds `toBeVisible`, `toHaveAccessibleName`, … to `expect` |
| `afterEach(cleanup)` | hook | unmounts every render between tests |
| `HTMLDialogElement.prototype.showModal` / `.show` / `.close` | patch | installed only if `showModal` is not already a function |

## Behavior

The `cleanup` registration is not boilerplate: Testing Library auto-registers on the *global* `afterEach`, which [[frontend/apps/manage/vitest.config.ts]] does not expose (`globals` stays `false`). Without this block, DOM from one test leaks into the next and `getByRole` starts matching two nodes — a failure that reads like a component bug.

The dialog patch is feature-detected (`typeof showModal !== "function"`) so a future jsdom that implements `<dialog>` natively takes over silently instead of being shadowed. The three stubs are the minimum that keeps the component contract honest: `showModal`/`show` set `open = true`, and `close` sets `open = false`, records `returnValue` when one is passed, and **dispatches a `close` event** — that last part is what makes an `onClose` handler wired to the native event actually fire, so the confirm dialogs in the console can be asserted end-to-end.

What the stubs deliberately do **not** reproduce is the browser's modal semantics: no top-layer, no focus trap, no inert background, no Esc-to-dismiss. Those are the parts of the `<dialog>` a11y story that IS 5568 actually cares about, and they are covered in a real browser by [[frontend/e2e/a11y.spec.ts]]. Treating a green jsdom test as proof that a modal traps focus is the specific mistake this file makes possible.

## Depends On

- [[Testing Library]] — `cleanup`, `jest-dom/vitest`
- [[Vitest]] — `afterEach`
- [[jsdom]]

## Depended On By

- [[frontend/apps/manage/vitest.config.ts]] — `setupFiles`
- transitively every test under `frontend/apps/manage/src/__tests__/`

## Concepts

- [[Accessibility Compliance]]

## Notes

**Three near-identical copies of this file exist** — this one, [[frontend/apps/storefront/src/test/setup.ts]] and [[frontend/packages/ui/src/test/setup.ts]] — differing only in a comment. They are edited independently, so a fix to the dialog stub here reaches neither of the others. The component this stub exists for is [[frontend/packages/ui/src/components/Modal.tsx]], which calls `showModal()` in an effect.
