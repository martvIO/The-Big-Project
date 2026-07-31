---
tags: [backend, api, storefront, security, design]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Public Wire Schemas

**What it is.** The response models served to anonymous visitors, kept in their own module
([[backend/app/storefront/schemas.py]]) with one absolute rule: **none of them subclasses a manage
schema, and none ever may.**

## Why inheritance is banned here

Inheritance is exactly how a mandated omission gets silently reverted. Add one field to the
console's `DressResponse` for the owner, and every public row inherits it — with **no diff on the
storefront file and no failing test in that module**. `test_storefront_api.py` asserts the
non-inheritance and the exact field sets, so the ban is mechanical rather than a review habit.

## Four deliberate absences

- **`price_visible` does not ship at all.** Once the number is omitted server-side,
  `price_agorot is None` covers both "the owner hid it" and "no price recorded", which the design
  renders identically. There is then no code path in which the flag and the number can disagree,
  because the flag never leaves the server. The key is serialised as `null` rather than dropped —
  same security property, far better client typing, and a client that could tell the two cases
  apart could tell that *this* dress has a hidden price.
- **`quantity` never appears.** The public size shape is `{size_label, available}`; raw stock is
  boutique-confidential.
- **`out_of_stock`, `total_quantity` and `variant_count` are never even computed.**
  [[backend/app/storefront/service.py]] simply never calls `aggregate_by_dress`. This is the
  strongest form of the rule: the leak is *unreachable*, not merely unserialised. Calling
  `CatalogService` would have been shorter, which is what makes it wrong.
- **`capacity` is absent from the hours row** — it is fitting-room throughput, which discloses how
  many parallel fittings the boutique runs.

## The same discipline on the manage side

`StaffMember` in [[backend/app/auth/schemas.py]] omits `password_hash` and `deleted_at` **by
construction** — never modelled, so no serializer has to remember to filter them, and every row the
list carries is live by definition.

## Shared primitives, and why they moved

`ForbidExtraModel` and `OkResponse` live in [[backend/app/schemas.py]], not in a domain module. A
second domain importing a boutique schema would point the dependency arrow sideways for no reason,
and a generated client would see two `{"ok": true}` types instead of one.

## The trap

`/openapi.json`, `/docs` and `/redoc` are **not registered outside dev** — a public storefront
origin would otherwise put the whole schema in front of crawlers. That is also why
[[frontend/packages/api-client/src/index.ts]] is an empty stub: its `generate` script needs a live
backend with `APP_ENV=dev`, so the codegen route was declined rather than half-adopted.

## Related

- [[Enumeration Resistance]] · [[Input Validation At The Boundary]] · [[Tenant Isolation]]
- [[backend/app/storefront/router.py]] · [[backend/tests/test_storefront_api.py]]
- [[Frontend Scaffold Reality]]
