---
tags: [frontend, storefront, test, vitest, contact, empty-state]
sources: [frontend/apps/storefront/src/__tests__/ContactCard.test.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/ContactCard.test.tsx
blob: cfb69719481fd57c6930a5f14add1fc2fbb78457
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/ContactCard.test.tsx

**Role.** Four tests, all about one decision: when `ContactCard` renders *nothing at all* versus when it renders the paper card. The wrapper's only job beyond `ContactPanel` is that null-return, so this file is the whole contract.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `boutique(patch)` | helper | a `BoutiqueResponse` with every contact field `null` — the shape a freshly provisioned tenant is in |

## Behavior

The suite imports the app's real i18n instance and asserts against `i18n.t("contact.call")` / `i18n.t("contact.waze")`, so the accessible names it queries are the production Hebrew strings rather than keys — nothing here is stubbed.

Two of the four tests assert `toBeEmptyDOMElement()`. The first is the all-null profile, and the comment names the defect it caught: `ContactPanel` with no channels emits zero children, so the `Card` was painting a bare rectangle on `/about` and under the catalog empty state. The second is subtler and is the reason the emptiness check cannot be a naive "any field set" test — a `maps_url` of `javascript:alert(1)` is dropped by the URL guard before it can become an `href`, so counting it as "a contact exists" would put the empty card straight back. The remaining two pin the positive direction, once for a phone alone (asserting the literal `tel:` href, unnormalised) and once for an address alone, because Waze is derived from the address text and needs no phone.

## Depends On

- [[frontend/apps/storefront/src/components/ContactCard.tsx]] — the subject
- [[frontend/apps/storefront/src/api.ts]] — the `BoutiqueResponse` type only
- [[frontend/apps/storefront/src/i18n/index.ts]] — imported for its side effect, then `void`-ed so the import is not tree-shaken
- [[Testing Library]] · [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Hebrew RTL Bidi]]

## Notes

The channel derivation itself (including the scheme allowlist) lives in [[frontend/apps/storefront/src/lib/contact.ts]] and is covered by [[frontend/apps/storefront/src/__tests__/contact.test.ts]]; this file only checks that the card honours a `null` result.
