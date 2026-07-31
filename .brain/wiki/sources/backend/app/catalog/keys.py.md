---
tags: [backend, catalog, media, s3, python, security, tenancy]
sources: [backend/app/catalog/keys.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/catalog/keys.py
blob: 3fdcfd0b75a3ec425f642d6e88a870e3bab97f47
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/catalog/keys.py

**Role.** The only place an S3 object key or a download filename for dress media is constructed — `tenants/{tenant_id}/dresses/{dress_id}/media/{media_id}{ext}` — with the extension derived from the server-side content-type map rather than from anything the client sent.

**Module.** [[backend/app/catalog/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `build_media_key` | fn | Keyword-only `(tenant_id, dress_id, media_id, content_type)` → the tenant-prefixed object key |
| `build_media_filename` | fn | `{media_id}{ext}` — the name that lands in a signed GET's `Content-Disposition` |
| `_extension` | fn | Private lookup in `ACCEPTED_CONTENT_TYPES`; raises `CatalogValidationError` on an unknown type |

## Behavior

Both builders are pure string joins over four values, none of which a client controls: `tenant_id` comes from the host-derived request context ([[backend/app/tenancy/middleware.py]]), `dress_id` from a dress row the tenant demonstrably owns — [[backend/app/catalog/service.py]] calls `dresses.by_id` *before* it calls in here — `media_id` is minted server-side with `uuid.uuid4()`, and the extension is looked up in `ACCEPTED_CONTENT_TYPES`. The original filename the browser offered is never stored and never reaches a key. `_extension` raises `CatalogValidationError` rather than returning a default, which is why an unaccepted content type cannot produce an extensionless key; in practice `validate_presign` has already rejected it, so this raise is the second gate rather than the first. `build_media_filename` exists as a separate function precisely so the `Content-Disposition` header is built from the row's own id — a client-supplied string in that header is a header-injection and download-name-spoofing surface, and there is no code path that can put one there.

The tenant prefix is deliberately the *first* segment so a future per-tenant IAM `s3:prefix` condition can be attached without rewriting every stored key.

## Depends On

- [[backend/app/catalog/validation.py]] — `ACCEPTED_CONTENT_TYPES` (the authoritative type→extension map) and `CatalogValidationError`

## Depended On By

- [[backend/app/catalog/service.py]] — `build_media_key` inside the presign transaction, `build_media_filename` in `sign_media`
- [[backend/tests/test_catalog_api.py]]
- [[backend/tests/test_catalog_validation.py]]

## Concepts

- [[Tenant Isolation]]
- [[Media Upload Pipeline]]

## Tests

- [[backend/tests/test_catalog_validation.py]] — imports both builders; the key-shape and extension-derivation assertions live here
- [[backend/tests/test_catalog_api.py]] — uses `build_media_key` to place fixture objects at the exact key the service will look for

## Notes

`_extension` is called by both public functions, so a content type accepted by one is accepted by the other by construction — the key's extension and the download name's extension can never disagree.

Design context: [[.planning/specs/catalog-management.md]].
