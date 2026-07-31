---
tags: [frontend, ui, test, vitest, accessibility, live-region]
sources: [frontend/packages/ui/src/__tests__/Toast.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/Toast.test.tsx
blob: 9400ce53b892ad056b2d90ccbbab466e5bf82ff5
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/Toast.test.tsx

**Role.** Pins the live-region politeness split of [[frontend/packages/ui/src/components/Toast.tsx]] — success is `role="status"`, error is `role="alert"` — plus the one-at-a-time replacement policy, auto-dismiss, and the provider-less no-op degradation of `useToast` from [[frontend/packages/ui/src/components/toast-context.ts]].

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Contract Pinned

| Assertion | Failure it prevents |
|---|---|
| success toast is `role="status"` **and** no `role="alert"` exists | a success message interrupting a screen-reader user mid-sentence; `status` is polite, `alert` is assertive, and the negative half is what stops both roles being emitted |
| firing a second toast leaves **no** `status` and exactly one `alert` with the new message | a silent queue, or two stacked toasts covering each other |
| with `autoDismissMs={30}` the toast is removed | the timer effect actually clears state, not just hides visually |
| a `useToast()` call rendered **outside** `ToastProvider` produces no toast and does not throw | any component that fires a toast becomes unit-testable without mounting the provider |

## Behavior

Tests drive the provider through a local `Harness` component with two buttons, which is the honest way to exercise a context API — the hook is consumed the way real callers consume it rather than being called directly. The first two tests pass `autoDismissMs={10_000}` to take the timer out of play; only the auto-dismiss test shortens it (30 ms) and awaits `waitForElementToBeRemoved`. No fake timers are used anywhere, so that one test is genuinely time-dependent — a slow CI box is the plausible flake source here, and shortening the window further is not the fix.

The replacement test asserts both halves (`status` gone, `alert` present) because the provider holds a single `ActiveToast | null` and a new `show()` overwrites it — there is no queue by design. The `key={toast.id}` on the rendered node means React remounts the element per toast, which is what makes the entry animation replay; nothing here asserts that.

The last test is the reason `useToast` returns `useContext(...) ?? noop` instead of throwing on a missing provider. That is a deliberate trade: it costs a real diagnostic (a component silently toasting into the void because someone forgot the provider) and buys isolated unit tests for every component that fires a toast. In the app the provider is always mounted at the root, so the degraded path is test-only — but a missing provider in production would fail silently, which is worth knowing.

## Depends On

- [[frontend/packages/ui/src/components/Toast.tsx]] — `ToastProvider`, the subject
- [[frontend/packages/ui/src/components/toast-context.ts]] — `useToast`, also under test
- [[Vitest]] — runner (entity)
- [[Testing Library]] — `render` / `fireEvent` / `waitForElementToBeRemoved` (entity)

## Depended On By

- nothing — a leaf test

## Concepts

- [[Accessibility Compliance]]

## Tests

- this *is* the test

## Notes

The toast container is `pointer-events-none` with the inner panel `pointer-events-auto`; there is no dismiss button and none is tested — the only way a toast goes away is the timer or a replacement.
