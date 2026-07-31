---
tags: [frontend, storefront, test, vitest, web-share, clipboard, toast]
sources: [frontend/apps/storefront/src/__tests__/ShareButton.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/ShareButton.test.tsx
blob: 943dd1f96ad0508c48a7cbff955a1ebf9213f7d7
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/ShareButton.test.tsx

**Role.** Six tests over the share button's three platform branches — native sheet, clipboard fallback, neither — with the file's real weight going to the two share *rejections* that must not be treated alike: a dismissed sheet (nothing failed) and a refused call (`NotAllowedError`, which leaves the visitor with nothing unless the clipboard catches it).

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `stub(property, value)` | helper | redefines `navigator.share` / `navigator.clipboard` (both are non-writable in jsdom, so assignment is not enough) |
| `flush()` | helper | two awaited microtask turns inside `act` |
| `renderShare(title)` | helper | mounts the button inside a `ToastProvider` and returns it |

## Behavior

`flush()` exists because the "nothing happened" assertions cannot be written with `findBy*`: proving a toast was *not* raised needs a deterministic point after the click's microtasks have drained, and an await-nothing has no such point. The positive cases still use `findByRole`, so the helper is only load-bearing on the negative ones.

The branch matrix is: a resolving `navigator.share` gets `{ title, url: window.location.href }` and must **not** copy anything and must **not** raise a toast (a native sheet is its own confirmation). An `AbortError` rejection is silence on both counts — copying the link behind her back after she declined to share would be answering a decision she already made. A `NotAllowedError` rejection *does* fall through to the clipboard and *does* announce, because that is Chromium desktop refusing a share it did not count as transient activation, and swallowing it leaves the visitor with no sheet, no link and no message. With `navigator.share` absent the clipboard path copies and announces through `role="status"` — a silent clipboard write gives a screen-reader user no cue that anything happened. A rejected `writeText` and a wholly absent `navigator.clipboard` (an insecure origin) both surface `FALLBACK_ERROR_MESSAGE` through `role="alert"`, so the control never goes inert without explanation.

`afterEach` clears both stubs back to `undefined`; the `beforeEach` reinstalls a fresh resolving `writeText` spy, which is why the failure case overrides it with `mockReturnValue` rather than redefining the property.

## Depends On

- [[frontend/apps/storefront/src/components/ShareButton.tsx]] — the subject
- [[frontend/apps/storefront/src/api.ts]] — `FALLBACK_ERROR_MESSAGE`, imported real
- [[frontend/packages/ui/src/components/Toast.tsx]] — `ToastProvider` supplies the `status`/`alert` regions asserted
- [[frontend/apps/storefront/src/i18n/index.ts]] — `dress.share`, `dress.shareCopied`
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[IS 5568 Accessibility]]

## Notes

Every assertion is about `window.location.href` as jsdom reports it, so the tests are indifferent to the surrounding route; the button is never rendered inside a page here.
