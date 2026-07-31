---
tags: [frontend, storefront, test-setup, jsdom, testing-library, dialog]
sources: [frontend/apps/storefront/src/test/setup.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/test/setup.ts
blob: d54b4b80fa657e622a18e89c0a2bb12a7562e375
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/test/setup.ts

**Role.** The one setup file every storefront test runs: it loads the `jest-dom` matchers, registers an explicit `afterEach(cleanup)`, and monkey-patches jsdom's incomplete `HTMLDialogElement`. The first two are load-bearing today; the third is currently inert insurance — no storefront source file renders a `<dialog>` any more (see Notes).

**Module.** [[frontend/apps/storefront/src/test/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| — | side-effect module | no exports; loaded via `test.setupFiles` in [[frontend/apps/storefront/vitest.config.ts]] |

## Behavior

Three things happen in order. `@testing-library/jest-dom/vitest` extends `expect` with `toBeVisible`, `toHaveAccessibleName` and the rest — the matcher vocabulary the IS 5568 assertions in [[frontend/apps/storefront/src/__tests__/accessibility.test.tsx]] are written in. Then a **hand-written `afterEach(cleanup)`**: Testing Library's automatic cleanup binds to a global `afterEach` that exists only under `globals: true`, which this app does not enable, so without this block DOM from one test would leak into the next and duplicate-element queries would start failing somewhere unrelated.

The third block is the interesting one. **jsdom implements `<dialog>` only partially** — `showModal`, `show` and `close` are missing — so [[frontend/packages/ui/src/components/Modal.tsx]] throws on open under jsdom without a patch. The patch installs on `HTMLDialogElement.prototype` and only `if (typeof dialogProto.showModal !== "function")`, so a future jsdom that ships the real implementation wins automatically. The stubs are minimal and honest: they flip `.open`, and `close` also sets `returnValue` when one is passed and **dispatches a real `close` event**, which is what makes an `onClose` handler bound on the `<dialog>` fire rather than the test calling the callback directly. `globalThis.HTMLDialogElement?.prototype` is optional-chained so the file is harmless outside a DOM environment.

**What the stub deliberately does not fake is focus trapping and the top layer.** A `showModal` that only sets `open = true` does not trap Tab, does not render a `::backdrop`, and does not make the rest of the document inert. Any Modal test riding on it would prove wiring, not containment — real focus-trap behavior is a browser-QA concern, per the file's own comment, and reading a green suite as evidence that the trap works is the trap.

Note what is **not** set up: no `fetch` polyfill and no MSW. Specs mock [[frontend/apps/storefront/src/api.ts]] with `vi.mock` instead, so nothing in this file touches the network. Nor is the clock pinned here — the Jerusalem-vs-device-zone guard is `TZ=America/New_York` on `scripts.test` in [[frontend/apps/storefront/package.json]].

## Depends On

- [[Testing Library]] — `cleanup`, `jest-dom/vitest`
- [[Vitest]] — `afterEach`
- [[jsdom]] — the environment being patched

## Depended On By

- [[frontend/apps/storefront/vitest.config.ts]] — `test.setupFiles`

## Tests

Every spec under `frontend/apps/storefront/src/__tests__/` loads this file — e.g. [[frontend/apps/storefront/src/__tests__/accessibility.test.tsx]], [[frontend/apps/storefront/src/__tests__/StorefrontLayout.test.tsx]] and [[frontend/apps/storefront/src/__tests__/DressPage.test.tsx]] all depend on the jest-dom matchers it installs.

## Notes

**The `<dialog>` comment describes a design the storefront no longer has.** It says the stub exists so "the `@boutique/ui` Modal (native `<dialog>`) behind the booking CTA works in tests", but no file under `frontend/apps/storefront/src/` imports `Modal` or renders a `<dialog>` today: [[frontend/apps/storefront/src/components/BookingCTAButton.tsx]] is an anchor that navigates to `/book/*`, and [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]] states in its own comment that it uses an inline reveal *instead of* a Modal. The same stale premise survives in [[frontend/apps/storefront/src/__tests__/CatalogPage.test.tsx]], whose `.filter((link) => link.closest("dialog") === null)` guards against "a second, closed ContactPanel" inside a dialog that is never rendered — the filter is a no-op. Harmless in both places; do not read either as evidence that a booking modal exists.

Identical to [[frontend/apps/manage/src/test/setup.ts]] apart from one comment clause, and near-identical to [[frontend/packages/ui/src/test/setup.ts]]. Three independent copies with no shared module: a jsdom gap fixed in one is **not** fixed in the other two, and nothing in CI notices the divergence.
