---
tags: [frontend, storefront, react, contact, empty-state]
sources: [frontend/apps/storefront/src/components/ContactCard.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/components/ContactCard.tsx
blob: d32fecbc07a062427ce47c2f659f878e374c302d
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/components/ContactCard.tsx

**Role.** `ContactPanel` on paper — and one guard: it returns `null` when the boutique has published no usable channel, so a freshly provisioned tenant never gets a blank `Card`. That null-return is essentially the component's entire contract; the derivations live elsewhere.

**Module.** [[frontend/apps/storefront/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ContactCard` | component | `{boutique, className?}` — the contact block wrapped in a `Card`, or nothing |

## Behavior

It calls `contactChannels(boutique)`; a `null` result means every channel derivation came back empty and the component renders nothing at all. `ContactPanel` with no channels emits zero children, so the `Card` would otherwise paint a bare paper rectangle on `/about` and under the catalog empty state — the defect [[frontend/apps/storefront/src/__tests__/ContactCard.test.tsx]] pins with `toBeEmptyDOMElement()`. The emptiness test cannot be "any field is set": a `maps_url` of `javascript:alert(1)` is dropped by the URL scheme guard before it can become an `href`, so counting it would put the empty card straight back.

Labels come from `contactLabels(t)` — the component itself passes `t` down rather than letting the shared `packages/ui` primitive touch i18n, which it never may. Because the *degrade* is a null return rather than an empty render, every caller that needs a visible "no contact details" sentence has to branch at its own call site; [[frontend/apps/storefront/src/routes/BookPage.tsx]] and [[frontend/apps/storefront/src/routes/AboutPage.tsx]] both do, and that is deliberate — a wrapper cannot know whether silence or a sentence is the right answer for the screen.

## Depends On

- [[frontend/apps/storefront/src/lib/contact.ts]] — `contactChannels`, `contactLabels`; the scheme allowlist and Waze/WhatsApp derivations
- [[frontend/packages/ui/src/components/ContactPanel.tsx]] · [[frontend/packages/ui/src/components/Card.tsx]]
- [[frontend/apps/storefront/src/api.ts]] — `BoutiqueResponse` type only
- [[i18next]]

## Depended On By

- [[frontend/apps/storefront/src/routes/AboutPage.tsx]]
- [[frontend/apps/storefront/src/routes/CatalogPage.tsx]] — under the empty catalog
- [[frontend/apps/storefront/src/routes/BookPage.tsx]] — every phone-only exit in the flow
- [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]] — last block on every state that has a boutique

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/apps/storefront/src/__tests__/ContactCard.test.tsx]] — four tests, all about the null-return
- [[frontend/apps/storefront/src/__tests__/contact.test.ts]] — the derivations themselves

## Notes

`ManageBookingPage` synthesises a `BoutiqueResponse` from the manage lookup's four-field boutique block when the layout fetch has none — this component's prop type is the reason that shim exists.
