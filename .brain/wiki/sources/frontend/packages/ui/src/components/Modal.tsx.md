---
tags: [frontend, ui, react, dialog, accessibility, focus-management]
sources: [frontend/packages/ui/src/components/Modal.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/Modal.tsx
blob: 75437d40caf8de778dc4e389e2b0f5c3692b880d
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/Modal.tsx

**Role.** A thin controlled wrapper over the **native `<dialog>`** element — the platform supplies the focus trap, top-layer stacking, inert background and Esc handling, so this file adds only three things: syncing the `open` prop to `showModal()`/`close()`, a `useId`-generated `aria-labelledby` heading, and the two-element entry motion (panel scale+fade at `--motion-base`, `::backdrop` fade at `--motion-fast`). No portal, no focus-trap library, no scroll-lock hack.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Modal` | fn | `{open, onClose, title, children, footer?}` |
| `ModalProps` | type | as above; `footer` is a caller-supplied node, normally the confirm/cancel buttons |

## Behavior

**`onClose` is dismiss, never confirm.** The `onCancel` handler calls `preventDefault()` before `onClose()`, so Esc routes through the same single dismiss path instead of letting the browser close the dialog behind React's back and desynchronise `open`. The confirm action is always a caller-supplied button in `footer` with its own handler — the Modal has no notion of a primary action, and the test suite pins that Esc fires `onClose` without firing the footer's handler.

**`onClose` must be idempotent, and callers must not assume it fires once.** It is wired to the dialog's native `close` event *as well as* to `onCancel`, so when a parent flips `open` to `false`, the effect calls `dlg.close()`, which fires `close`, which calls `onClose()` a second time. In practice every caller's handler just sets its state flag false again, so this is harmless — but a handler with a side effect (a toast, a POST, a counter) would run twice.

**Children are always mounted.** The `<dialog>` and its subtree render whether `open` is true or false; only `showModal()`/`close()` toggle. Effects and data fetches inside `children` therefore run while the dialog is closed, and a caller that wants mount-on-open must conditionally render the `<Modal>` itself.

**The focus-restore trap is the one thing callers must handle themselves.** Native `<dialog>` returns focus to whatever had it when the dialog opened — but in this console the trigger button typically carries `disabled={busy}` and unmounts (or disables) in the very commit that closes the dialog, so the native restore lands on `<body>` and the next Tab restarts at the skip link (WCAG 2.4.3). [[frontend/apps/manage/src/components/BookingDetail.tsx]] and [[frontend/apps/manage/src/components/DressEditor.tsx]] both carry an explicit `wasOpen` ref + `useEffect` that re-focuses a stored trigger ref on close; treat that as the required pattern, not as boilerplate to remove.

`title` is rendered as an `<h2>` whose id comes from `useId()` — a literal id would break `aria-labelledby` whenever a screen mounts two Modals at once (the console's `DressEditor` and its embedded `MediaGallery` do exactly that). The panel width is `min(28rem, 100vw - 2rem)`, so it never exceeds the viewport on a 375px phone.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`
- [[frontend/packages/ui/src/theme.css]] — `--animate-modal-panel` / `--animate-modal-backdrop` and their keyframes
- [[React]] — `useId`, `useRef`, `useEffect`

## Depended On By

- [[frontend/apps/manage/src/components/BookingDetail.tsx]] · [[frontend/apps/manage/src/components/DressEditor.tsx]] · [[frontend/apps/manage/src/components/HoursSection.tsx]] · [[frontend/apps/manage/src/components/MediaGallery.tsx]] · [[frontend/apps/manage/src/components/RescheduleDialog.tsx]] · [[frontend/apps/manage/src/components/StaffSection.tsx]] · [[frontend/apps/manage/src/components/TypesSection.tsx]]
- [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]]
- [[frontend/packages/ui/src/index.ts]] — barrel re-export

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/packages/ui/src/__tests__/Modal.test.tsx]] — open render, Esc dismisses without confirming, footer button confirms

## Notes

**The docstring on `onClose` says "Esc, backdrop, cancel button" but there is no backdrop-click handler in this file** — no `onClick` on the `<dialog>`, no `closedby` attribute — and native `<dialog>` does *not* dismiss on backdrop click. Backdrop click is currently inert. Trust the code, not the comment.

jsdom does not implement `showModal`/`close`, so all three vitest setups ([[frontend/packages/ui/src/test/setup.ts]], [[frontend/apps/manage/src/test/setup.ts]], [[frontend/apps/storefront/src/test/setup.ts]]) patch `HTMLDialogElement.prototype`. Those shims only flip the `open` attribute — they reproduce nothing of the real focus trap or top layer, so a test that passes here is not evidence the focus behaviour works in a browser.
