---
tags: [backend, catalog, validation, python, product-policy, media, security]
sources: [backend/app/catalog/validation.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/catalog/validation.py
blob: 8807075cc8bd62758bc3a7a5b93ff09747d671e8
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/catalog/validation.py

**Role.** The single home of catalog *product policy* — every numeric bound, the accepted image-type set, the magic-byte signature table, the presign/signed-GET/pending TTLs and the list page sizes — as pure I/O-free functions and constants that the Pydantic schemas, the DB CHECKs and the frontend all mirror.

**Module.** [[backend/app/catalog/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `CatalogValidationError` | class | Subclass of `DomainValidationError`; the shared handler turns it into the house-shape 400 |
| `VariantInput` | frozen dataclass | `(size_label, quantity, sort_order=0)` — the service's variant payload type |
| `normalize_size_label` | fn | Strip + collapse internal whitespace; **case is preserved** |
| `matches_magic_prefix` | fn | True only when every documented signature segment sits at its documented offset |
| `validate_dress` | fn | Name non-blank/length, description length, `0 < price_agorot <= MAX_PRICE_AGOROT` (NULL allowed), `abs(sort_order)` bound |
| `validate_variants` | fn | Count, label blank/length, `0 <= quantity <= MAX_VARIANT_QUANTITY`, sort bound. **No** duplicate detection |
| `validate_presign` | fn | Content type in `ACCEPTED_CONTENT_TYPES`, `MIN_UPLOAD_BYTES <= byte_size <= MAX_UPLOAD_BYTES` |
| `validate_search` | fn | Length ceiling on the manage list's `search` param |
| `ACCEPTED_CONTENT_TYPES` | const | `{image/jpeg: .jpg, image/png: .png, image/webp: .webp}` — type→extension, authoritative |
| `MAGIC_PREFIXES` / `MAGIC_PREFIX_LENGTH` | const | Per-type `(offset, bytes)` segment tuples; 16 bytes read at confirm |
| `MAX_*` / `MIN_UPLOAD_BYTES` | const | Name 200, description 4000, price 100 000 000 agorot, 60 variants, label 32, quantity 1000, 12 media, 10 MiB / 1 KiB upload, search 100, sort ±1 000 000 |
| `DB_MAX_PRICE_AGOROT` / `DB_MAX_QUANTITY` / `DB_MAX_BYTE_SIZE` | const | Migration 0006's absurdity ceilings, declared beside the caps they guard |
| `PRESIGN_TTL_SECONDS` / `SIGNED_GET_TTL_SECONDS` / `PENDING_MEDIA_TTL_SECONDS` | const | 300 / 900 / 3600 |
| `DRESS_LIST_DEFAULT_LIMIT` / `DRESS_LIST_MAX_LIMIT` | const | 24 / 100 |

## Behavior

Every function raises `CatalogValidationError` and returns `None` on success, so callers use them as gates rather than as transformers — the one transformer, `normalize_size_label`, is separate and is applied by the service before `validate_variants` runs. Duplicate size detection is deliberately *absent* here: two labels colliding under `lower()` is a 409 conflict, not a 400 malformed body, so it lives in `CatalogService._reject_duplicate_sizes` and is backstopped by a partial unique index. `normalize_size_label` not lowercasing is the paired decision — the owner's "US 6" is stored exactly as typed, and it is `lower()` *in the index* that stops "US 6" and "us 6" from becoming two stock buckets for one physical size.

The security-relevant constants are the type map and the magic table. HEIC, GIF and SVG are excluded from `ACCEPTED_CONTENT_TYPES` on purpose — an SVG is executable markup, and an SVG served from the media bucket is stored XSS. `MAGIC_PREFIXES` models webp as **two** segments (`RIFF` at 0, `WEBP` at 8) rather than one prefix, because a single-prefix table would pass any RIFF-shaped file: a `.wav`, an `.avi`, a polyglot. `matches_magic_prefix` returns `False` for an unknown content type instead of raising, so it fails closed when called with a type that somehow escaped the earlier gate.

Each numeric cap names its DB counterpart. Migration 0006's CHECKs sit at exactly 10x these values — INT4 headroom, so tightening product policy never requires a migration — with one deliberate exception: `DB_MAX_BYTE_SIZE` is only 2x `MAX_UPLOAD_BYTES`, because `byte_size` is not merely a product bound but a *security* bound that the presigned POST policy enforces as an exact content-length range. `MIN_UPLOAD_BYTES` bounds the **declared** size, which is what kills empty and probe uploads before a pending row is ever written.

The split from [[backend/app/core/config.py]] is the load-bearing design here: `Settings` carries deployment identity (bucket, region, endpoint) and never policy, so an operator cannot raise a byte cap in env while the DB CHECK and the frontend validator stay put — the result would be a clean 400 degrading into an `IntegrityError` 500 at confirm.

## Depends On

- [[backend/app/errors.py]] — `DomainValidationError`, the shared 400 base

## Depended On By

- [[backend/app/catalog/service.py]] — every validator, both TTLs, the media cap, the list limits, `VariantInput`, `normalize_size_label`, `matches_magic_prefix`
- [[backend/app/catalog/schemas.py]] — the `Field` bounds mirror these constants
- [[backend/app/catalog/keys.py]] — `ACCEPTED_CONTENT_TYPES`, `CatalogValidationError`
- [[backend/app/catalog/router.py]] — list limits, `MAX_SEARCH_LENGTH`, `VariantInput`
- [[backend/app/main.py]] — `PENDING_MEDIA_TTL_SECONDS` into the `CatalogService` constructor
- [[backend/app/booking/service.py]] — `normalize_size_label`, so a booking's requested size matches the catalogue's stored label byte for byte

## Concepts

- [[Product Policy Vs Deployment Identity]]
- [[Media Upload Pipeline]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_catalog_validation.py]] — the unit suite; also asserts each cap/DB-ceiling pair mechanically rather than relying on a reviewer
- [[backend/tests/test_frontend_constant_parity.py]] — re-asserts every constant that `frontend/apps/manage/src/validation.ts` restates, and that its exported `ACCEPTED_CONTENT_TYPES` key set equals this module's
- [[backend/tests/test_catalog_api.py]]
- [[backend/tests/test_media_upload_s3.py]] — magic-prefix rejection end to end

## Notes

`MAX_SORT_ORDER` is documented as reused from [[backend/app/boutique/validation.py]] but is re-declared here as its own literal rather than imported — the two modules happen to agree at 1 000 000, and nothing mechanically holds them together.

`MAX_LIST_OFFSET`, the twin of `DRESS_LIST_MAX_LIMIT`, does **not** live here — it sits in [[backend/app/catalog/service.py]] with a `ponytail:` note explaining that the placement was branch hygiene, not design.

Design context: [[.planning/specs/catalog-management.md]].
