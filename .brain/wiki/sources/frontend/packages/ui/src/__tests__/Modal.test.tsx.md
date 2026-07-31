---
tags: [frontend, ui, test, vitest, dialog, accessibility]
sources: [frontend/packages/ui/src/__tests__/Modal.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/Modal.test.tsx
blob: 9c4ddc44cc150309347cafbac740173b0d61ad9f
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/Modal.test.tsx

**Role.** Pins the **dismiss-is-never-confirm** contract of [[frontend/packages/ui/src/components/Modal.tsx]]: Esc closes and fires `onClose` alone, while the destructive action fires only from the caller's own footer button. Three tests, all around a native `<dialog>` whose modal methods are stubbed by the suite setup.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Contract Pinned

| Assertion | Failure it prevents |
|---|---|
| when `open`, `role="dialog"` exists and both title and body text render | the `showModal()` effect actually ran; `<dialog>` without it is inert and invisible |
| dispatching a cancelable `cancel` event on the dialog calls `onClose` **once** and `onConfirm` **never** | the destructive path being reachable by hitting Esc — the single worst bug this component could have |
| clicking the footer button calls `onConfirm` once | the confirm path still works after the `preventDefault` in `onCancel` |

## Behavior

The middle test is the whole point of the file. `Modal`'s `onCancel` handler calls `e.preventDefault()` and then `onClose()` — it intercepts the browser's own Esc-closes-dialog behavior so that closing always routes through the dismiss handler and never through anything a caller wired to a confirm. The test reproduces Esc by dispatching a raw `new Event("cancel", { cancelable: true })` rather than a key press, because jsdom does not translate `keydown Escape` into the `<dialog>` `cancel` event — the platform behavior being relied on is the one jsdom omits. Reading a `fireEvent.keyDown` into this test would silently stop testing anything.

**What is deliberately not covered: real focus behavior.** The setup file [[frontend/packages/ui/src/test/setup.ts]] stubs `showModal`/`show`/`close` on `HTMLDialogElement.prototype` because jsdom implements `<dialog>` only partially; the stub just flips `.open` and dispatches `close`. So the four things the component actually chose native `<dialog>` *for* — focus trap, top-layer stacking, real Esc handling, focus return to the trigger — are all outside this file. The setup comment states the policy: that is a browser-QA concern, exercised in [[frontend/e2e/a11y.spec.ts]], not a jsdom one. Do not treat a green Modal suite as evidence the focus trap works.

Also unasserted: `aria-labelledby` pointing at the `useId`-generated title id. The component uses `useId` rather than a literal precisely because two Modals can be mounted at once (DressEditor plus its embedded gallery) and duplicate ids break the label — a real invariant with no test behind it.

## Depends On

- [[frontend/packages/ui/src/components/Modal.tsx]] — the subject
- [[frontend/packages/ui/src/components/Button.tsx]] — used to build the footer confirm button
- [[frontend/packages/ui/src/test/setup.ts]] — the `<dialog>` stub these tests require
- [[Vitest]] — runner, `vi.fn()` (entity)
- [[Testing Library]] — `render` / `fireEvent` / `screen` (entity)

## Depended On By

- nothing — a leaf test

## Concepts

- [[Accessibility Compliance]]

## Tests

- this *is* the test

## Notes

Backdrop-click dismissal is not tested and, in the component as written, is not implemented either — `<dialog>` does not close on backdrop click by default, despite `ModalProps.onClose`'s comment listing "backdrop" among the dismiss routes. Treat that comment as intent, not as behavior.
