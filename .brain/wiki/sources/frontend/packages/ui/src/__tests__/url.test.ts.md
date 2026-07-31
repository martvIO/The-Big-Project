---
tags: [frontend, ui, test, vitest, security, xss]
sources: [frontend/packages/ui/src/__tests__/url.test.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/url.test.ts
blob: e929f183c7358e1341dba0094ec5b9b0ba02e36f
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/url.test.ts

**Role.** The scheme-allowlist suite for `safeHref` — the single gate every tenant-supplied URL (`maps_url`, Waze) passes before it can reach an `href`. Three cases, one security property: anything that is not `http(s):`, `tel:` or `mailto:` comes back `undefined` so the caller degrades to plain text.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `describe("safeHref")` | suite | pass-through of safe schemes; rejection of unsafe ones; rejection of empty/nullish |

## Behavior

The rejection case is the one that matters, and its inputs are chosen to break a *denylist*: bare `javascript:`, the same with leading whitespace, the same upper-cased, plus `data:text/html,…` and `vbscript:`. [[frontend/packages/ui/src/lib/url.ts]] answers with an allowlist anchored at the string start after a `trim()`, which is why all five fail — a denylist is bypassable because browsers strip leading control characters and whitespace before resolving a scheme, so `"\tjava\tscript:"`-shaped payloads survive a naive `startsWith("javascript:")` check.

The nullish case pins the `undefined` return for `undefined`, `null` and a whitespace-only string, which is the contract [[frontend/packages/ui/src/components/BoutiqueHeader.tsx]] and [[frontend/packages/ui/src/components/ContactPanel.tsx]] rely on: they render an `<a>` only when `safeHref` returns a value, and fall back to unlinked `<bdi>` text otherwise. The visible half of that degrade is asserted in [[frontend/packages/ui/src/__tests__/hours-composites.test.tsx]].

This gate exists because **React does not neutralise a `javascript:` href** — it warns in development and renders the attribute anyway. Tenant profile fields are owner-authored, so without this the console is a stored-XSS vector into every visitor's storefront.

## Depends On

- [[frontend/packages/ui/src/lib/url.ts]] — subject (`safeHref`)
- [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Tenant Isolation]]

## Tests

This is the test.

## Notes

Not covered: relative and protocol-relative URLs (`/x`, `//evil.com`), which the allowlist rejects — correct for the current callers, since every one of them expects an absolute external link, but a future caller wanting an in-app path will find `safeHref` says no.
