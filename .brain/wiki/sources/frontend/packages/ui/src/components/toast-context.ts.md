---
tags: [frontend, ui, react-context, notifications, testing]
sources: [frontend/packages/ui/src/components/toast-context.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/toast-context.ts
blob: a35f14996c0326d80a0eef753458cb2efeaf89b7
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/toast-context.ts

**Role.** The consumer half of the toast surface, split into its own `.ts` file so the hook and its types can be imported without pulling in the provider's JSX. It declares the `ShowToast` contract and a `useToast()` that **degrades to a no-op** outside a provider rather than throwing.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ToastVariant` | type | `"success" \| "error"` — the only two |
| `ToastOptions` | interface | `{message, variant?}` |
| `ShowToast` | type | `(options: ToastOptions) => void` |
| `ToastContext` | const | `createContext<ShowToast \| null>(null)` |
| `useToast` | fn | returns the provider's `show`, or a module-level `noop` |

## Behavior

`useToast` is `useContext(ToastContext) ?? noop`. The null-default-plus-noop is the whole point and the file says so: a component that fires a toast can be unit-tested in isolation without mounting `ToastProvider`, and in the running app the provider always wraps the tree, so real toasts show. The trade is that a missing provider fails *silently* — a genuinely unwrapped subtree would swallow every notification with no error, so this is a contract to keep in mind when adding a new React root.

`noop` is a single module-level constant, not created per call, so the returned identity is stable across renders in the unwrapped case and does not retrigger effects that depend on the toast function.

There is no `variant` default here — `ToastOptions.variant` is optional, and the fallback to `"success"` is applied inside [[frontend/packages/ui/src/components/Toast.tsx]]'s `show`. Callers wanting an error must pass it explicitly.

## Depends On

- [[React]] — `createContext`, `useContext` (entity)

## Depended On By

- [[frontend/packages/ui/src/components/Toast.tsx]] — provides the context value
- [[frontend/packages/ui/src/index.ts]] — re-exports `useToast` + the three types
- [[frontend/apps/storefront/src/components/ShareButton.tsx]] — share/clipboard confirmation
- [[frontend/apps/manage/src/components/ProfileSection.tsx]] — save-failure only (the console confirms success inline)

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/packages/ui/src/__tests__/Toast.test.tsx]] — includes an explicit case rendering the harness with no provider and asserting nothing appears

## Notes

Kept `.ts` rather than `.tsx` on purpose — no JSX here, and the separation is what lets a test import `useToast` without the provider module.
