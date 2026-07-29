---
tags: [backend, storefront, python, pydantic, wire-models, public-api]
sources: [backend/app/storefront/schemas.py]
created: 2026-07-27
updated: 2026-07-29
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storefront/schemas.py
blob: 06fac1697464dbd079da36d5d8c49305ce84a8a2
commit: 9507140f3d31cba691e762fc0ed89c9f738e912b
kind: code
applicability: active
---

# backend/app/storefront/schemas.py

**Role.** The public wire models. Twelve response models, no request model — the only client-supplied values on this surface are `offset`, `limit` and the `/slots` date window, all bounded on the route. Renamed and flattened in the F10 spec-conformance pass (PR #15): the old `Public*Response` family became the spec's names, and the boutique payload went flat. E3 added the booking-grid models (F12: `SlotRow`, `SlotListResponse`, `AppointmentTypeRow`) and the cancellation-policy read (F14: `StorefrontTerms`).

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
| `SlotRow` | model | `{starts_at}` and nothing else — **no `capacity`, no `remaining`** |
| `SlotListResponse` | model | `{slots}` |
| `StorefrontTerms` | model | `{version, terms_text, refundable_until_hours_before, forfeit_percent}` — the policy a customer must see before accepting |
| `AppointmentTypeRow` | model | `{id, name, duration_minutes, audience, deposit_required, deposit_amount_agorot}` |

## Behavior

**None of these subclass a manage schema, and none ever may — nor does `StorefrontDetail` subclass `StorefrontDress`.** Inheritance is exactly how the mandated omissions would get silently reverted: a field added to [[backend/app/catalog/schemas.py#DressResponse]] for the console would reach every storefront row with no diff on this file and no failing test in this module. [[backend/tests/test_storefront_api.py]] asserts the non-inheritance *and* the exact field sets.

Four absences are spec requirements ([[.planning/specs/storefront-browse.md]], "the field allowlist, stated once"), not formatting choices. `price_visible` does not ship **at all**: once the number is omitted server-side, `price_agorot is None` covers both "the owner hid it" and "no price recorded", which the design renders identically ("מחיר בתיאום") — the flag and the number can never disagree because the flag never leaves the server. The key is serialised as `null` rather than dropped (same security property, better client typing, and a client that could tell the two cases apart could tell that *this* dress has a hidden price). `quantity` never appears — raw stock is boutique-confidential; the public size shape is `SizeChip`. `out_of_stock`, `total_quantity` and `variant_count` are **never even computed** — [[backend/app/storefront/service.py]] doesn't call the aggregate at all. `capacity` is absent from `HoursRow` — it is fitting-room throughput, which discloses how many parallel fittings the boutique runs.

**`SlotRow` carries the start time and nothing else, and the omission has a story worth keeping.** An earlier draft also shipped `remaining`, which reads like the safe half of `capacity` — but the slot engine drops full slots, so with nothing booked `remaining` equals `capacity` exactly, for every slot, on every response. That republishes verbatim the field `HoursRow`'s allowlist fences off ("discloses how many parallel fittings the boutique runs"), just under a different key — and the wire-absence walk in [[backend/tests/test_storefront_api.py]] cannot catch it, because the key it forbids is spelled differently. The picker does not need it either: every slot the engine returns is by construction bookable, so the time *is* the whole message. A scarcity cue is a legitimate product idea, but it should be a deliberately coarse signal over a real booking count, not a number that happens to equal capacity today.

**`StorefrontTerms` is the same non-inheritance rule applied to a legal surface** (F14). It is not a subclass of the manage-side `TermsVersionResponse`: `id`, `tenant_id`, `created_by` and the timestamps are operator provenance, not booking-page content. `version` ships because the booking POST sends back the version the customer accepted — it is the pointer that makes consent auditable. The two numbers it carries (`refundable_until_hours_before`, `forfeit_percent`) are the ones a bride is actually agreeing to; `forfeit_percent` is a percentage **of the deposit** (stated in the F7 spec's schema line and repeated in [[backend/app/models/terms_version.py]]'s column comment).

**`AppointmentTypeRow.audience` is disclosed, not enforced.** An anonymous visitor cannot be classified as a bride, so the field exists for the UI to *label* the option; real enforcement waits for a client identity (E5). The deposit fields ship now because a customer is entitled to see a deposit before choosing a time rather than after — E4's payment step reads the same two fields.

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
