---
tags: [frontend, ui, react, storefront, composite, rtl, bidi]
sources: [frontend/packages/ui/src/components/BoutiqueHeader.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/BoutiqueHeader.tsx
blob: 51ef9edeeaa9c39cfe1ab804187b1e43088549fc
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/BoutiqueHeader.tsx

**Role.** The storefront's identity block: the boutique name as the page `<h1>`, then optional essence, a caller-composed today's-hours snippet, and the address — rendered as an external maps link when the tenant's `maps_url` survives scheme checking, and as plain text when it does not.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `BoutiqueHeader` | component | `{name, essence?, hoursText?, address?, mapsUrl?, className?}` |
| `BoutiqueHeaderProps` | interface | `mapsUrl` is `string \| null \| undefined` — a null from the API needs no unwrapping at the call site |

## Behavior

**This component renders the page's only `<h1>`.** Any route that mounts it must not render another; the console solves the same problem differently with an `sr-only` h1 in [[frontend/packages/ui/src/components/ConsoleShell.tsx]].

`hoursText` is a finished Hebrew string composed by the app — the package never touches i18n, and never formats a time itself. It is always styled `ink-muted`, never `danger`: **closed today is not an error state**, and colouring it as one would be both a wrong signal and a contrast trap.

`mapsUrl` goes through `safeHref` from [[frontend/packages/ui/src/lib/url.ts]] before ever reaching an `href`, because React does *not* neutralise a `javascript:` href and the value is tenant-supplied. When the scheme fails the allowlist, `safeHref` returns `undefined` and the address degrades to a plain `<bdi>` — the address is still shown, only the link is dropped. The link carries `target="_blank" rel="noopener noreferrer"`, which is what makes the trailing `↗` honest and matches [[frontend/packages/ui/src/components/ContactPanel.tsx]], which opens the same URL: without them, tapping the address on a phone replaces the storefront, and this site deliberately ships no back affordance.

The address is wrapped in a **bare `<bdi>` with no `dir`**. It is tenant-supplied and may be Hebrew or Latin; forcing `dir="ltr"` would mangle a Hebrew address. This is the house rule — numeric runs get `<bdi dir="ltr">`, free text gets a bare `<bdi>`.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`
- [[frontend/packages/ui/src/lib/url.ts]] — `safeHref`

## Depended On By

- [[frontend/packages/ui/src/index.ts]]
- [[frontend/apps/storefront/src/routes/CatalogPage.tsx]]
- [[frontend/apps/storefront/src/routes/AboutPage.tsx]]

## Concepts

- [[RTL And Bidi Isolation]]
- [[Tenant Isolation]]

## Tests

- [[frontend/packages/ui/src/__tests__/hours-composites.test.tsx]]
- [[frontend/packages/ui/src/__tests__/url.test.ts]] — covers the `safeHref` allowlist this component relies on

## Notes

No `ref` and no props passthrough: it is a leaf presentational header, and callers cannot attach arbitrary attributes to it.
