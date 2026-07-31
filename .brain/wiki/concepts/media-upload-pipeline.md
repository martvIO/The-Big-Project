---
tags: [backend, catalog, storage, s3, security, concurrency]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Media Upload Pipeline

**What it is.** The three-call sequence by which a dress photo becomes visible: **presign →
browser POSTs to S3 → confirm**. The bytes never pass through the API. Every step lives in
`CatalogService` in [[backend/app/catalog/service.py]]; the storage calls go through
[[Media Storage]].

## The row's two states

`dress_media.status` is `pending | ready` ([[backend/migrations/versions/0006_catalog.py]]), with a
partial index for each. A `pending` row is a reservation; only `ready` rows appear in a gallery.

**1. `presign_media`** — throttle first (the outermost guard, so a blocked tenant cannot spend a
transaction discovering it is blocked), then validate, then check storage is configured *before*
writing a row that nobody could upload against. Inside the transaction, under the `dress-media:`
[[Advisory Lock]]: resolve the parent dress, sweep stale pendings, count active, enforce
`MAX_MEDIA_PER_DRESS`, insert the pending row. The `media_id` is minted client-side so
`build_media_key` ([[backend/app/catalog/keys.py]]) can run before the single statement that writes
`storage_key` — there is no post-insert UPDATE of the key.

**2. The browser POSTs** the signed policy directly to S3. The policy pins an *exact*
content-length range, so the maximum the browser may post is precisely what it declared.

**3. `confirm_media`** — read the row, short-circuit if already `ready` (a retried confirm after a
lost response is idempotent), then **outside any session** call `head_object` and `read_prefix`, and
finally re-open a transaction under the lock to promote to `ready` with `sort_order = max + 1`.

## Nothing client-supplied reaches an S3 key

`tenants/{tenant_id}/dresses/{dress_id}/media/{media_id}{ext}`. `tenant_id` comes only from the
host-derived request context, `dress_id` only from a dress row this tenant owns (the service
resolves the parent *first*), `media_id` is server-minted, and the extension comes from the declared
content type — never the client's filename, which is not stored at all. `build_media_filename`
derives the download name from the row's own id for the same reason.

## Two network calls with no transaction open

This is the module's stated first invariant: **no `MediaStorage` network method inside a
`tenant_session`**. `tenant_session` is one Postgres transaction, and boto3's default 60 s connect
+ 60 s read timeouts would pin a pool connection *and* a per-dress advisory lock across an S3 stall.
Hence the explicit split, and hence mutations that return a detail view do a write transaction,
then a short read transaction, then mint signed URLs.

## What confirm actually verifies, and what it cannot

`head_object` must return the declared content type, and `read_prefix` must match the documented
magic bytes (`MAGIC_PREFIX_LENGTH = 16`, [[backend/app/catalog/validation.py]]). A mismatch rejects
the object.

**Scope it honestly** — the service does, in a comment worth reading before trimming anything: an
S3 POST policy **cannot be revoked**, so within the remainder of `PRESIGN_TTL_SECONDS` the same
policy can re-POST a different body of identical size to the identical key, *after* this check has
run. The two layers covering that window are `signed_get_url`'s pinned content type + attachment
disposition, and media-origin isolation. Neither is optional, and neither may be trimmed on the
strength of the magic-byte check.

## Orphans are bounded, not eliminated

- A `pending` row older than `PENDING_MEDIA_TTL_SECONDS` (1 h) stops counting toward the cap and is
  swept on the next presign for that dress; the swept objects are deleted **outside** the
  transaction, which is what bounds the orphan window.
- Deleting a `pending` row logs its storage key at INFO, because its policy may still be redeemed
  after `delete_object` has already run against a key that does not exist yet — a silent 204 that
  would otherwise leave no trace for the deferred reconcile job.
- If signing fails *after* the row commits (rotated IAM key), the pending row is released
  immediately — otherwise it would hold a gallery slot for a full TTL on an upload the browser
  never got a policy for.

## Gotchas

- **A rejected presign still costs budget.** Both the `except` path and the success path call
  `record_failure` by hand — [[Rate Limiting]] counts only what a caller explicitly records, and
  the comment says outright that deleting the success-path line "because it reads like a bug" is how
  the throttle dies.
- `reorder_media` compares sorted multisets, so subset, superset, duplicate and unknown id all fail
  one check.
- Byte caps and TTLs live only in [[backend/app/catalog/validation.py]] — not in env, because the DB
  `CHECK` would not follow.

## Related

- [[Media Storage]] · [[Advisory Lock]] · [[Rate Limiting]] · [[Soft Delete]]
- Tests: [[backend/tests/test_media_upload_s3.py]] · [[backend/tests/test_catalog_integration.py]]
