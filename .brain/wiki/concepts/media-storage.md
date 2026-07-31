---
tags: [backend, storage, s3, catalog, security, architecture]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Media Storage

**What it is.** The port that dress photos go through — a `Protocol` in
[[backend/app/storage/base.py]] with three implementations, and the only place in the backend that
touches object storage. Images are never served from the API: the browser POSTs straight to S3 and
reads back through short-lived signed GETs.

## Three implementations, chosen at boot

| Class | File | When |
|---|---|---|
| `S3MediaStorage` | [[backend/app/storage/s3.py]] | `MEDIA_BUCKET` is set |
| `UnconfiguredMediaStorage` | [[backend/app/storage/unconfigured.py]] | it is not — every method raises `MediaNotConfiguredError`, the router answers 503 |
| `InMemoryMediaStorage` | [[backend/app/storage/memory.py]] | tests, with a `put()` that stands in for the browser's POST |

`_build_media_storage` in [[backend/app/main.py]] picks one. **A missing bucket is never a boot
failure** — no bucket is a supported deployment. `UnconfiguredMediaStorage` exists rather than
`None` so no call site grows a null check and none can forget one; dress CRUD, variants, reorder and
reads all keep working with `url` serialised as null.

## Sync vs async is a real distinction here

`presigned_post` and `signed_get_url` are plain `def`: botocore signs them with local HMAC and zero
I/O, and making them async would be a lie costing an `await` per gallery item on every list
response. `head_object`, `read_prefix` and `delete_object` are genuine network calls, are `async`,
and the S3 adapter pushes the blocking client off the event loop.

## What the adapter deliberately does not hold

- **No AWS credentials in `Settings`.** boto3 reads them from the process environment, so they never
  enter the config object, never appear in a repr and never get logged.
- **No product policy.** Byte caps and TTLs live once in [[backend/app/catalog/validation.py]] —
  [[backend/app/core/config.py]] says why: an operator raising a byte limit in env while the DB
  `CHECK` stayed put produces an `IntegrityError` on confirm.
- **No client at construction time.** `S3MediaStorage.__init__` does no I/O and no credential
  resolution; building a botocore client walks a provider chain that reads `~/.aws` and calls IMDS
  over the network. The client is built on first use, which is what keeps `create_app()` safe to
  call in the fast suite.

## Two security properties that are easy to delete by accident

- `signed_get_url` pins `ResponseContentType` **and** `ResponseContentDisposition: attachment`.
  S3 cannot emit `X-Content-Type-Options` on a presigned GET, so these two overrides are half the
  sniffing defense; `attachment` is ignored for subresource loads, so `<img src>` still renders while
  a top-level navigation to a polyglot object downloads instead of executing.
- `PresignedPost.fields` carries `policy` + `x-amz-signature` and is bearer material for its whole
  TTL. It is never logged and never appears in an error. `MediaStorageUnavailableError` carries no
  AWS-supplied text — the original is logged with the storage key instead.

## Observability

`/health` ([[backend/app/api/routes/health.py]]) reports `media: "configured" | "unconfigured"` and
**never the bucket, region or endpoint** — it is unauthenticated. That field plus one INFO line at
boot is the only thing that makes a typo'd `MEDIA_BUKCET` visible, since `Settings.model_config`
is `extra="ignore"`.

## Related

- [[Media Upload Pipeline]] · [[Ports And Adapters]] · [[Package Layout]] · [[Boto3]] · [[Fail Fast Configuration]]
- Tests: [[backend/tests/test_storage_port.py]] · [[backend/tests/test_media_upload_s3.py]]
