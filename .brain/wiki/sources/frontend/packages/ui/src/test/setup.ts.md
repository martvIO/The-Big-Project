---
tags: [frontend, ui, test-setup, jsdom, testing-library, dialog]
sources: [frontend/packages/ui/src/test/setup.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/test/setup.ts
blob: 2daf3dd153714253617ea93fa34a074b56fdd2c6
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/test/setup.ts

**Role.** The one setup file every `@boutique/ui` test runs: it loads the `jest-dom` matchers, registers an explicit `afterEach(cleanup)`, and monkey-patches jsdom's incomplete `HTMLDialogElement` so the `<dialog>`-based Modal is testable at all.

**Module.** [[frontend/packages/ui/src/test/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| — | side-effect module | no exports; imported via `setupFiles` in [[frontend/packages/ui/vitest.config.ts]] |

## Behavior

Three things happen, in order. `@testing-library/jest-dom/vitest` extends `expect` with `toBeVisible`, `toHaveAccessibleName` and the rest — the matcher vocabulary the a11y assertions are written in. Then a **hand-written `afterEach(cleanup)`**: Testing Library's automatic cleanup hooks a global `afterEach` that only exists when Vitest runs with `globals: true`, and this package does not, so without this block DOM from one test would leak into the next and duplicate-element queries would start failing in confusing places.

The third block is the interesting one. **jsdom implements `<dialog>` only partially** — `showModal`, `show` and `close` are missing — so [[frontend/packages/ui/src/components/Modal.tsx]] would throw on open. The patch is installed on `HTMLDialogElement.prototype` and only `if (typeof dialogProto.showModal !== "function")`, so a future jsdom that ships the real implementation wins automatically. The stubs are minimal and honest: they flip `.open`, and `close` also sets `returnValue` when one is passed and **dispatches a real `close` event** — which is what makes the `onClose` handler bound on Modal's `<dialog>` actually fire in jsdom, so the tests exercise the real listener path instead of the callback directly. `globalThis.HTMLDialogElement?.prototype` is optional-chained so the file is harmless in a non-DOM environment.

**What the stub deliberately does not fake is focus trapping and the top layer.** A jsdom `showModal` that sets `open = true` does not trap Tab, does not render a `::backdrop`, and does not make the rest of the document inert. Modal tests therefore prove wiring, not containment — real focus-trap behavior is a browser-QA concern, per the file's own comment. Reading a green Modal suite as evidence that the focus trap works is the trap here.

## Depends On

- [[Testing Library]] — `cleanup`, `jest-dom/vitest`
- [[Vitest]] — `afterEach`
- [[jsdom]] — the environment being patched

## Depended On By

- [[frontend/packages/ui/vitest.config.ts]] — `test.setupFiles`

## Tests

- [[frontend/packages/ui/src/__tests__/Modal.test.tsx]] — the direct beneficiary of the `<dialog>` stub
- [[frontend/packages/ui/src/__tests__/Toast.test.tsx]], [[frontend/packages/ui/src/__tests__/A11y.test.tsx]] — rely on the jest-dom matchers

## Notes

The apps carry their own equivalents ([[frontend/apps/storefront/src/test/setup.ts]], [[frontend/apps/manage/src/test/setup.ts]]); this file is not shared with them, so a jsdom gap fixed here is not automatically fixed there.
