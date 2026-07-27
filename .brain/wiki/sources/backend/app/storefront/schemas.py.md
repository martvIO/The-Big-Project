---
tags: [backend, storefront, python, pydantic, wire-models, public-api]
sources: [backend/app/storefront/schemas.py]
created: 2026-07-27
updated: 2026-07-27
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storefront/schemas.py
blob: 8cc0ac647e7efa1521a0eb5d1bdaf26ce538e936
commit: c9b045a8b70028db0de520384cdecf68f9b34c74
kind: code
applicability: active
---

# backend/app/storefront/schemas.py

**Role.** The public wire models. Nine response models, no request model — the only client-supplied value on this surface is `offset`, bounded on the route.

**Module.** [[backend/app/storefront/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `PublicMediaResponse` | model | `{url, url_expires_at}` — a presigned GET and its expiry, nothing else |
| `PublicDressResponse` | model | one catalog card: `{id, name, price_agorot, reserved, cover}` |
| `PublicVariantResponse` | model | `{size_label, available}` — availability, never a count |
| `PublicDressDetailResponse` | model | `{id, name, description, price_agorot, reserved, variants, media}` |
| `PublicDressListResponse` | model | house envelope `{items, total, offset, limit}` |
| `PublicProfileResponse` | model | `{phone, address, description, maps_url}`, all nullable |
| `PublicHoursRuleResponse` | model | `{day_of_week, open_time, close_time}` — **no `capacity`** |
| `PublicHoursExceptionResponse` | model | `{date, open_time, close_time, note}` |
| `PublicBoutiqueResponse` | model | `{name, profile, rules, exceptions}` |

## Behavior

**None of these subclass a manage schema, and `PublicDressDetailResponse` does not subclass `PublicDressResponse` either.** Inheritance is how the mandated omissions would get silently reverted: a field added to [[backend/app/catalog/schemas.py#DressResponse]] for the console would reach every storefront row with no diff on this file. [[backend/tests/test_storefront_api.py]] asserts the non-inheritance *and* the exact `model_fields` set of both dress models.

Three absences are spec requirements (`.planning/specs/catalog-management.md`, the two "Note for F10" blocks), not formatting choices. `price_visible` does not ship **at all**: once the number is omitted server-side, `price_agorot is None` covers both "the owner hid it" and "no price recorded", which the design renders identically — so the flag and the number can never disagree, because the flag never leaves the server. The key is serialised as `null` rather than dropped (same security property, better client typing). `quantity` never appears — raw stock is boutique-confidential. `capacity` is absent from the hours rule — it is fitting-room throughput, not opening hours.

`description` is omitted from the list row: cards do not render it, and carrying it would multiply a 24-row payload for nothing. Media ids, storage keys, content types, byte sizes and sort orders are all absent — the storefront renders an `<img>`.

## Depends On

- [[Pydantic]] — `BaseModel`

## Depended On By

- [[backend/app/storefront/router.py]]
- [[backend/tests/test_storefront_api.py]]

## Concepts

- [[Media Storage]]

## Tests

- [[backend/tests/test_storefront_api.py]] — the recursive forbidden-key walk and the exact-field-set assertions

## Notes

Deliberately no `ForbidExtraModel` import: there is no request body on this surface.
