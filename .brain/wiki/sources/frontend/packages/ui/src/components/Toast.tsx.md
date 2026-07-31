---
tags: [frontend, ui, component, notifications, accessibility, react-context]
sources: [frontend/packages/ui/src/components/Toast.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/Toast.tsx
blob: 4621cd7a8317b440f9b6cb39e20df1067eaa387e
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/Toast.tsx

**Role.** The provider half of the notification surface: it owns the single active toast, publishes a `show` callback over [[frontend/packages/ui/src/components/toast-context.ts]], auto-dismisses on a timer, and picks the live-region role from the variant — `role="alert"` for errors (assertive, interrupts) and `role="status"` for success (polite, waits for a pause).

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ToastProvider` | fn | context provider + the fixed-position toast host |
| `ToastProviderProps` | interface | `{children, autoDismissMs?}` — defaults to `4000` |

## Behavior

State is exactly one `ActiveToast | null` plus a monotonic `idRef` counter. `show` is a `useCallback` with an empty dep list, so the context value is referentially stable and consumers do not re-render when a toast appears — the file's comment states the queueing policy plainly: **one at a time, a new toast replaces the current one, no queue.** That means a burst of failures shows only the last message; the design accepts this because a stack of toasts over an RTL form is worse than one clear line.

Dismissal is a `useEffect` keyed on `[toast, autoDismissMs]`. The timeout callback is guarded — `setToast(current => current?.id === toast.id ? null : current)` — so a replacement toast's timer is not cancelled by its predecessor's expiry; combined with the effect's cleanup `clearTimeout`, each toast gets its own full window. The `id` also serves as the JSX `key`, which forces a remount and therefore replays the `animate-toast` entry animation for every new message even when the text is identical.

The host is `pointer-events-none` on the outer positioning layer and `pointer-events-auto` on the bubble, so the invisible full-width strip never swallows clicks on the page beneath. It is positioned with the logical `start-0 end-0`, not `left/right` — a physical pair would be flagged by `frontend/scripts/qa-greps.sh`. There is **no dismiss button and no close affordance**: the only way out is the timer.

## Depends On

- [[frontend/packages/ui/src/components/toast-context.ts]] — `ToastContext`, `ShowToast`, `ToastVariant`
- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`
- [[Tailwind CSS]] — `animate-toast` maps to the `--animate-toast` theme token (entity)

## Depended On By

- [[frontend/packages/ui/src/index.ts]] — re-exports `ToastProvider` + `ToastProviderProps`
- [[frontend/apps/storefront/src/App.tsx]] — wraps the storefront tree
- [[frontend/apps/manage/src/App.tsx]] — wraps the console tree

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/packages/ui/src/__tests__/Toast.test.tsx]] — the role split (`status` vs `alert`), the replace-not-queue rule, auto-dismiss at `autoDismissMs={30}`, and the no-op degradation outside a provider

## Notes

**The two apps use this surface for opposite purposes, and the split is a rule worth knowing before adding a call.** In the manage console a toast is for *failure only*: [[frontend/apps/manage/src/components/ProfileSection.tsx]] fires `toast({variant: "error"})` in its catch block and marks success with an inline `saved` cue next to the submit button — a mutation the owner just triggered should confirm itself where she is looking, not in a strip at the top that vanishes in four seconds. In the storefront the success path is legitimate: [[frontend/apps/storefront/src/components/ShareButton.tsx]] uses `role="status"` precisely because a silent clipboard write gives a screen-reader user no signal at all.

`autoDismissMs` defaults to 4s and is not tuned per-variant; an error message a user needs to re-read has no way back once it has gone.
