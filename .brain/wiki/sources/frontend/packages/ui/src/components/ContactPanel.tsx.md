---
tags: [frontend, ui, react, storefront, composite, rtl, bidi, security]
sources: [frontend/packages/ui/src/components/ContactPanel.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/ContactPanel.tsx
blob: 14b644857bccdf21f7d4877d0e8969a16bf23242
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/ContactPanel.tsx

**Role.** The five contact channels as a column of links — tap-to-call, a `wa.me` WhatsApp deep link, Waze, Google Maps and Instagram — each rendered only when its value is present, with tenant-supplied URLs scheme-checked before they reach an `href`.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ContactPanel` | component | `{phone?, whatsapp?, wazeUrl?, mapsUrl?, instagram?, labels, className?}` — every channel optional, so a freshly provisioned tenant renders an empty (but valid) panel |
| `ContactPanelLabels` | interface | `{call, whatsapp, waze, maps, instagram?}` |
| `ContactPanelProps` | interface | |

## Behavior

`whatsapp` is **digits only** (the component builds `https://wa.me/{digits}`) and `instagram` is a **handle without `@`** (the component builds `https://instagram.com/{handle}` and prints `@{handle}`) — both are formatting contracts the caller must honour; nothing validates them here. `phone` becomes `tel:${phone}` unchecked, which is safe only because a `tel:` URI is constructed rather than passed through.

`wazeUrl` and `mapsUrl` are the two values that arrive verbatim from tenant settings, so both go through `safeHref` from [[frontend/packages/ui/src/lib/url.ts]] first: React does **not** neutralise a `javascript:` href, and `safeHref` returns `undefined` for anything outside the `https?: | tel: | mailto:` allowlist, which drops the row entirely. All four external links carry `target="_blank" rel="noopener noreferrer"`; only `tel:` does not, since it never navigates.

`labels.instagram` is the one optional label, and the row renders only when **both** the handle and its label exist. That is deliberate: no caller can supply a handle until the profile carries one, and a required-but-unusable label would force every call site to pass a dead string.

The Instagram handle is the panel's one bidi hazard and gets `<bdi dir="ltr">` — a Latin/URL run inside an RTL panel, where `dir="ltr"` is correct precisely because the content is guaranteed non-Hebrew (Hebrew free text elsewhere takes a bare `<bdi>`). It also carries `min-w-0` and `[overflow-wrap:anywhere]`, which is **WCAG 1.4.10 reflow, not cosmetics**: a handle is a single unbreakable Latin token, so at 200% text on a 375px viewport `@some.long.handle` is wider than its line and pushes the whole document sideways. `anywhere` rather than `break-word` because only `anywhere` will break a token that offers no break opportunity at all.

`linkClass` is computed once at module scope — every row shares one class string, so the focus ring and link colour cannot drift between channels.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`
- [[frontend/packages/ui/src/lib/url.ts]] — `safeHref`

## Depended On By

- [[frontend/packages/ui/src/index.ts]]
- [[frontend/apps/storefront/src/lib/contact.ts]] — the shared adapter that builds the props and labels for all four call sites
- [[frontend/apps/storefront/src/components/ContactCard.tsx]], [[frontend/apps/storefront/src/components/booking/TypePicker.tsx]], [[frontend/apps/storefront/src/routes/AboutPage.tsx]], [[frontend/apps/storefront/src/routes/BookPage.tsx]]

## Concepts

- [[RTL And Bidi Isolation]]
- [[Tenant Isolation]]

## Tests

- [[frontend/packages/ui/src/__tests__/chrome-composites.test.tsx]] — asserts tap-to-call, WhatsApp, Waze, Maps and Instagram are all wired
- [[frontend/packages/ui/src/__tests__/url.test.ts]] — the `safeHref` allowlist
- [[frontend/apps/storefront/src/__tests__/ContactCard.test.tsx]], [[frontend/apps/storefront/src/__tests__/BookPage.test.tsx]], [[frontend/apps/storefront/src/__tests__/CatalogPage.test.tsx]]

## Notes

The panel has no heading and no landmark — it is a bare `flex` column. Callers supply the surrounding `Card` and heading; [[frontend/apps/storefront/src/lib/contact.ts]] returns `null` when a tenant has no channels at all, so the empty-panel case is handled above this component rather than in it.
