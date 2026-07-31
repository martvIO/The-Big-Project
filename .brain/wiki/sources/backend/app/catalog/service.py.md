---
tags: [backend, catalog, service, media, s3, python, concurrency, tenancy, rate-limiting]
sources: [backend/app/catalog/service.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/catalog/service.py
blob: 9cfbd41bad5c5c6080d8f393e40c2e6a85b0ecf6
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/catalog/service.py

**Role.** All catalog business logic — dress CRUD with archive/restore, the whole-matrix variant replace, and the three-step S3 media lifecycle (presign → browser POST → confirm) — plus `sign_media`, the one function that mints signed GET URLs for **both** the owner console and the public storefront.

**Module.** [[backend/app/catalog/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `CatalogService` | class | Constructed with a session factory, a `MediaStorage` port, a presign `FixedWindowRateLimiter`, and an injectable `pending_ttl_seconds` |
| `sign_media` | fn | Module-level, storage-injected: one media row → `MediaView`, degrading to `url=None` on any storage failure |
| `list_dresses` / `create_dress` / `get_dress` / `update_dress` / `archive_dress` / `restore_dress` | method | Dress lifecycle |
| `replace_variants` | method | Whole-matrix replace under a per-dress advisory lock |
| `presign_media` / `confirm_media` / `delete_media` / `reorder_media` | method | The media lifecycle |
| `DressView` / `MediaView` / `StockSummary` / `DressListResult` / `PresignResult` | frozen dataclass | The router's input types — deliberately not ORM rows |
| `CatalogNotFoundError` | error | `DomainNotFoundError` subclass → shared 404 |
| `DuplicateSizeError` | error | 409 |
| `MediaLimitReachedError` / `MediaNotUploadedError` / `MediaMismatchError` / `MediaOrderMismatchError` | error | 409 each, distinct bodies |
| `MediaPresignThrottledError` | error | 429 |
| `MAX_LIST_OFFSET` | const | 1 000 000 |

## Behavior

Three invariants hold the module together, and each closes a specific failure.

**No `MediaStorage` network call inside a `tenant_session`.** `tenant_session` opens one Postgres transaction for the whole `async with` block, so a boto3 call inside it would pin a pool connection *and* a per-dress advisory lock across an S3 stall (boto3 defaults to 60 s connect + 60 s read). `presign_media`, `confirm_media` and `delete_media` are therefore explicit multi-step sequences with every `head_object` / `read_prefix` / `delete_object` outside the session; mutations that return a detail view do a write transaction, then a short read transaction (`_detail_view`), and only then mint signed URLs. `presigned_post` and `signed_get_url` are local HMAC and may run anywhere.

**Resolve the parent dress first.** The first statement inside every session — and, for presign, inside the lock — is `dresses.by_id(...)`, whose predicate collapses an unknown id, an archived dress and another tenant's dress into one indistinguishable 404. `build_media_key` runs only after that returns a row, so no unverified id can reach an S3 key. `get_dress` is the deliberate exception: it passes `include_archived=True`, because the owner must be able to open an archived dress in order to restore it. The storefront no longer routes through here at all — [[backend/app/storefront/service.py]] calls `DressesRepository.by_id` directly, which pins `deleted_at IS NULL` structurally rather than by a caller remembering a flag.

**Two lock prefixes.** Photo work takes `dress-media:<id>`, stock work takes `dress-variants:<id>`, so the two never serialise against each other, and both stay clear of the un-prefixed `hashtext(:tenant_id)` lock space that [[backend/app/boutique/service.py]] uses for its weekly-rule replace. The lock prefix is a SQL literal and the dress id is a bound parameter — never interpolated.

`presign_media` is the densest path. The throttle check is the *outermost* guard so a blocked tenant cannot spend a transaction discovering it is blocked; then validation; then an early `is_configured` check, because an unconfigured storage would otherwise leave a pending row nobody could ever upload against. Inside the lock it sweeps stale pendings, counts active media, enforces `MAX_MEDIA_PER_DRESS`, and inserts the pending row with a key built from the client-side-minted `media_id` — so the key exists before the single statement that writes it and there is no post-insert `UPDATE` of `storage_key`. Two `record_failure` calls look like bugs and are not: `FixedWindowRateLimiter` counts only what is explicitly recorded, so a *rejected* presign (which already cost a transaction, a lock and two counting queries) and a *successful* one (which authorises a 10 MiB write to the bucket) must each be recorded by hand or the throttle is inert. The success recording sits above the signing call because the committed transaction, not the signature, is what the bound protects. If signing then fails anyway — rotated IAM credentials pass `is_configured` — `_release_pending` hands the gallery slot back, otherwise a photo-less dress would answer `MEDIA_LIMIT_REACHED` on its twelfth attempt for a whole `PENDING_MEDIA_TTL_SECONDS`. Swept objects are deleted only after the transaction commits, since the sweep is the sole holder of those keys and that ordering is what bounds the orphan window.

`confirm_media` reads the row, short-circuits idempotently if it is already `READY` (so a retried confirm after a lost response touches no storage), then does two real network calls outside any session: `head_object` for existence and declared content type, and `read_prefix` for the magic bytes. A mismatch on either deletes the object best-effort and raises `MediaMismatchError`. The magic check is scoped honestly in the code and worth repeating: it verifies the object **at confirm time only**. An S3 POST policy cannot be revoked, so within the remainder of `PRESIGN_TTL_SECONDS` the same policy can re-POST a different body of identical size to the identical key. The two layers covering that window — `signed_get_url` pinning `ResponseContentType` plus attachment disposition, and the media-origin-isolation invariant — are not optional and may not be trimmed on the strength of this check.

`reorder_media` compares `sorted(media_ids)` against the sorted current ready set: a subset, a superset, a duplicate and an unknown id all fail it, and since ids are unique a duplicate cannot sneak through as a matching multiset. It is the one media route that keeps working with no bucket, because it is pure database work.

`archive_dress` soft-deletes children first in one transaction; `now()` is `transaction_timestamp()`, so all three stamps are byte-identical — and `restore_dress` matches children on exactly that stamp, which is why it reads the dress's own `deleted_at` **first** (it is simultaneously the already-restored guard and the restore key). S3 objects are retained across archive.

`_stock_summary` is the single `out_of_stock` formula and nothing is stored: a cached boolean would need a trigger or an independently-failing second write, either of which creates a state where the badge disagrees with the matrix. Zero variants means out of stock. `sign_media` is module-level for the same reason — a security-relevant degradation rule that exists in two places will eventually hold in only one of them.

`MAX_LIST_OFFSET` guards a real 500: `offset` reaches the driver as `OFFSET $n::BIGINT`, so a value past int8 dies inside asyncpg's `int8_encode` as a `DataError` with no handler above it. Both `offset` and `limit` are clamped here as well as at the router, so a non-router caller cannot request an unbounded page.

## Depends On

- [[backend/app/db/tenant.py]] — `tenant_session`, the RLS-bound transaction
- [[backend/app/db/repositories/dresses.py]] · [[backend/app/db/repositories/dress_variants.py]] · [[backend/app/db/repositories/dress_media.py]]
- [[backend/app/catalog/validation.py]] — every bound, TTL and validator
- [[backend/app/catalog/keys.py]] — `build_media_key`, `build_media_filename`
- [[backend/app/storage/base.py]] — the `MediaStorage` port and its two failure types
- [[backend/app/auth/rate_limit.py]] — `FixedWindowRateLimiter` for the presign budget
- [[backend/app/errors.py]] — `DomainNotFoundError`
- [[backend/app/models/dress.py]] · [[backend/app/models/dress_variant.py]] · [[backend/app/models/dress_media.py]] · [[backend/app/models/constants.py]]
- [[SQLAlchemy]] — `text`, `IntegrityError`, async session types

## Depended On By

- [[backend/app/catalog/router.py]] — the whole surface
- [[backend/app/main.py]] — constructs `CatalogService`, registers a handler for each of the six typed errors
- [[backend/app/storefront/service.py]] — reuses `sign_media`, `MediaView` and `CatalogNotFoundError`
- [[backend/app/storefront/router.py]] — `MediaView`

## Concepts

- [[Media Upload Pipeline]]
- [[Advisory Lock]]
- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_catalog_integration.py]] — the DB-backed lifecycle suite
- [[backend/tests/test_catalog_isolation.py]] — cross-tenant 404s through the service
- [[backend/tests/test_catalog_api.py]] — the HTTP surface
- [[backend/tests/test_media_upload_s3.py]] — presign/confirm against a real object store, including magic-prefix rejection
- [[backend/tests/test_storage_port.py]] — TTL and port-contract assertions
- [[backend/tests/test_storefront_integration.py]] · [[backend/tests/test_storefront_isolation.py]] — seed catalogue data through this service

## Notes

`pending_ttl_seconds` is a constructor parameter purely so the stale-pending sweep can be tested without sleeping or backdating rows; [[backend/app/main.py]] passes `PENDING_MEDIA_TTL_SECONDS` unchanged.

`_best_effort_delete` swallows storage failures but always logs key, tenant, dress and media id — that log line is the only input a future orphan-reconcile job will have. The same is true of the `logger.info` in `delete_media`'s pending branch: a deleted pending row's POST policy is still redeemable, so the object may land *after* the delete ran against a key that did not yet exist, a silent S3 204 that would otherwise leave no trace at all.

There is no error registry in [[backend/app/main.py]] — every one of the six typed errors above needs an explicit `@app.exception_handler`, and all six currently have one.

Design context: [[.planning/specs/catalog-management.md]].
