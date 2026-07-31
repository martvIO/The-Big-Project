---
tags: [backend, storage, media, python, protocol, s3]
sources: [backend/app/storage/base.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storage/base.py
blob: 99eaac81d99d68d252e1d42eda95d321972c9848
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/storage/base.py

**Role.** Defines the media storage port — the `MediaStorage` Protocol its three implementations satisfy, the two value objects they return, and the two exception types that let a missing bucket and an unreachable bucket both degrade to 503 instead of 500.

**Module.** [[backend/app/storage/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `MediaStorage` | Protocol | The port: `is_configured`, `presigned_post`, `signed_get_url`, `head_object`, `read_prefix`, `delete_object` |
| `MediaNotConfiguredError` | exception | No bucket, **or** a bucket with no usable credentials — the two are operationally identical |
| `MediaStorageUnavailableError` | exception | Backend unreachable or refusing; carries no AWS-supplied text |
| `PresignedPost` | frozen dataclass | `url` + `fields`; `fields` holds `policy` and `x-amz-signature` and is bearer material for its whole TTL |
| `ObjectHead` | frozen dataclass | `content_type` + `byte_size` as reported by the store, not by the uploader |

## Behavior

This module is pure declaration: no imports from `app/`, no I/O, no logic. The absence of an import from [[backend/app/catalog/validation.py]] is deliberate and load-bearing — callers pass `expires_in` and `filename` in, so TTLs and the content-type→extension map stay in the catalog and there is no cycle between the port and its only real consumer. The sync/async split across the six methods is likewise a decision rather than an accident: `presigned_post` and `signed_get_url` are plain `def` because botocore signs them with a local HMAC and does zero network I/O, so making them `async` would cost an `await` per gallery item on every list response and buy nothing; the three that really talk to the network are `async`. Both exceptions exist so that failures cross the boundary as *typed* facts with no vendor text attached — an AWS message can name the bucket, the account and the full storage key, and the key embeds `tenant_id`. There is no error registry in [[backend/app/main.py]]: both of these have explicit `@app.exception_handler` registrations there, and a new error type added here without one would surface as a 500.

## Depends On

Nothing at runtime — `dataclasses` and `typing.Protocol` only.

## Depended On By

- [[backend/app/storage/s3.py]] — the production implementation
- [[backend/app/storage/unconfigured.py]] — the "no bucket" implementation
- [[backend/app/storage/memory.py]] — the test implementation
- [[backend/app/main.py]] — types `_build_media_storage`'s return, registers the 503 handlers for both exceptions
- [[backend/app/catalog/service.py]] — presign, confirm (head + magic-prefix read), delete, signed reads
- [[backend/app/catalog/router.py]] — catches `MediaNotConfiguredError` at the edge
- [[backend/app/storefront/service.py]] — signs public gallery URLs
- [[backend/app/api/routes/health.py]] — reads `is_configured` only, never bucket identity

## Concepts

- [[Media Storage]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_storage_port.py]] — `test_every_implementation_satisfies_the_port` checks all three against the Protocol; `test_unconfigured_storage_raises_on_every_method` pins the degradation contract

## Notes

`mypy app tests` is what actually enforces the Protocol — [[backend/app/storage/memory.py]] lives under `app/` rather than `tests/` specifically so the type checker holds it to the same shape as the other two.
