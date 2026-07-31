---
tags: [frontend, storefront, react, web-share, clipboard, toast]
sources: [frontend/apps/storefront/src/components/ShareButton.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/components/ShareButton.tsx
blob: 6d720068077b298a4e9c93944d79bf6efa21285d
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/components/ShareButton.tsx

**Role.** Share the current dress URL: the native share sheet where the platform has one, a clipboard copy where it does not, and a **spoken** confirmation either way — the toast renders `role="status"`, because a silent clipboard write looks broken to a screen-reader user.

**Module.** [[frontend/apps/storefront/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ShareButton` | component | `{title}` — a ghost `Button` labelled `dress.share` |

## Behavior

The URL is read from `window.location.href` at click time, never from a prop. If `navigator.share` is a function it is tried first; its rejection handler is the interesting part. `AbortError` — the visitor closing the sheet — is a deliberate no-op. **Every other rejection falls through to the clipboard**, because it means the share never happened; the named case is Chromium on desktop rejecting with `NotAllowedError` when it does not count the click as transient activation, which would otherwise leave the visitor with silence and no link.

`copyLink` guards the optional chain: `navigator.clipboard?.writeText(url)` returning `undefined` means no share sheet *and* no clipboard, i.e. an insecure origin, and it says so with an error toast rather than leaving the button inert with no explanation. Success toasts `dress.shareCopied`; a rejected write toasts the shared `FALLBACK_ERROR_MESSAGE` from [[frontend/apps/storefront/src/api.ts]] with `variant: "error"`.

`title` is passed only into the native share payload — it is not rendered, so nothing here needs bidi isolation.

## Depends On

- [[frontend/packages/ui/src/components/Button.tsx]]
- [[frontend/packages/ui/src/components/Toast.tsx]] — `useToast`; the `role="status"` region is the a11y contract
- [[frontend/apps/storefront/src/api.ts]] — `FALLBACK_ERROR_MESSAGE`
- [[i18next]]

## Depended On By

- [[frontend/apps/storefront/src/routes/DressPage.tsx]] — the only consumer, `title={dress.name}`

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/apps/storefront/src/__tests__/ShareButton.test.tsx]] — the share/clipboard/insecure-origin branches and the AbortError no-op

## Notes

The error path reuses the hard-coded Hebrew `FALLBACK_ERROR_MESSAGE` rather than an i18n key — that constant is the app's one non-`t()` user-facing string, and it lives in `api.ts` because the fetch layer needs it before i18n is guaranteed ready.
