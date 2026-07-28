---
tags: [backend, storefront, python, pydantic, wire-models, public-api]
sources: [backend/app/storefront/schemas.py]
created: 2026-07-27
updated: 2026-07-28
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storefront/schemas.py
blob: c6ed73c738579cff69ccf42ec79344dcb28b5708
commit: 3bf3795889113127f3fae36eb18e91a29ebe7fda
kind: code
applicability: active
---

# backend/app/storefront/schemas.py

**Role.** The public wire models. Eight response models, no request model — the only client-supplied values on this surface are `offset` and `limit`, both bounded by `Query(...)` on the route. Renamed and flattened in the F10 spec-conformance pass (PR #15): the old `Public*Response` family became the spec's names, and the boutique payload went flat.

**Module.** [[backend/app/storefront/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `StorefrontMedia` | model | `{url, url_expires_at}` — a presigned GET and its expiry, both nullable (no bucket / signing failed → a read never fails over a missing photo) |
| `StorefrontDress` | model | one catalog card: `{id, name, price_agorot, reserved, cover}` — `description` deliberately omitted from list rows |
| `SizeChip` | model | `{size_label, available}` — availability, never a count |
| `StorefrontDetail` | model | `{id, name, description, price_agorot, reserved, sizes, media}` — NOT a subclass of `StorefrontDress` |
| `DressListResponse` | model | house envelope `{items, total, offset, limit}`; `total` is what load-more counts against |
| `HoursRow` | model | `{day_of_week, open_time, close_time}` — **one row per window, not per day**; **no `capacity`** |
| `ExceptionRow` | model | `{date, open_time, close_time, note}` — both times null = closed all day, both set = special hours |
| `BoutiqueResponse` | model | **flat**: `{name, essence, description, phone, address, maps_url, instagram, hours, exceptions}` — no nested `profile` object |

## Behavior

**None of these subclass a manage schema, and none ever may — nor does `StorefrontDetail` subclass `StorefrontDress`.** Inheritance is exactly how the mandated omissions would get silently reverted: a field added to [[backend/app/catalog/schemas.py#DressResponse]] for the console would reach every storefront row with no diff on this file and no failing test in this module. [[backend/tests/test_storefront_api.py]] asserts the non-inheritance *and* the exact field sets.

Four absences are spec requirements ([[.planning/specs/storefront-browse.md]], "the field allowlist, stated once"), not formatting choices. `price_visible` does not ship **at all**: once the number is omitted server-side, `price_agorot is None` covers both "the owner hid it" and "no price recorded", which the design renders identically ("מחיר בתיאום") — the flag and the number can never disagree because the flag never leaves the server. The key is serialised as `null` rather than dropped (same security property, better client typing, and a client that could tell the two cases apart could tell that *this* dress has a hidden price). `quantity` never appears — raw stock is boutique-confidential; the public size shape is `SizeChip`. `out_of_stock`, `total_quantity` and `variant_count` are **never even computed** — [[backend/app/storefront/service.py]] doesn't call the aggregate at all. `capacity` is absent from `HoursRow` — it is fitting-room throughput, which discloses how many parallel fittings the boutique runs.

`HoursRow` is one row per *window*: F7 allows a lunch break (multiple windows per day), the repository orders by `(day_of_week, open_time)`, and the client groups — a naive one-row-per-day map would keep only the last window. `BoutiqueResponse` is flat because every field is public identity rendered in one header block, and the flat shape is what the spec binds; the profile fields are read out of the settings JSONB by explicit key (in [[backend/app/storefront/router.py]]'s `public_boutique`), so a key a later feature adds cannot reach the public page by default, and `toggles` is not read at all — `brides_only`'s storefront semantics land with E3 #14. Media ids, storage keys, content types, byte sizes and sort orders are all absent — the storefront renders an `<img>`.

## Depends On

- [[Pydantic]] — `BaseModel`

## Depended On By

- [[backend/app/storefront/router.py]]
- [[backend/tests/test_storefront_api.py]]

## Concepts

- [[Media Storage]]

## Tests

- [[backend/tests/test_storefront_api.py]] — key-absence assertions per forbidden field and the exact-field-set assertions

## Notes

Deliberately no `ForbidExtraModel` import: there is no request body on this surface.
