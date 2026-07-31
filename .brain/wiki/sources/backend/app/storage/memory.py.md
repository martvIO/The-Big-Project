---
tags: [backend, storage, media, python, testing]
sources: [backend/app/storage/memory.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storage/memory.py
blob: a5382533d63fa19877ce5b5f85f260aa42cc1517
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/storage/memory.py

**Role.** A dict-backed `MediaStorage` implementation that lets the presign→confirm sequence, the API fakes and the isolation suites run with working media and no container.

**Module.** [[backend/app/storage/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `InMemoryMediaStorage` | class | `MediaStorage` implementation over `objects: dict[str, tuple[str, bytes]]` |
| `InMemoryMediaStorage.put` | method | Test-only: stands in for the browser's direct POST to S3 |
| `objects` | attribute | Public by design — tests assert on it after a delete or a confirm |

## Behavior

There is no upload endpoint in this platform — the browser POSTs straight to S3 — so a test simulates that leg by calling `put()` with the same key the presign returned. `presigned_post` and `signed_get_url` return fixed, obviously-fake strings (`https://media.test/...`, `x-amz-signature: test-signature`); they are shape stand-ins, not signatures, and nothing verifies them. `head_object` returns `None` for an absent key, matching S3's miss semantics. `read_prefix` deliberately does **not** return empty bytes for an absent key: it raises `MediaStorageUnavailableError`, mirroring S3, where a GET on a missing key is an error. Since the confirm path heads the object before reading its prefix, reaching that raise means a real race — turning it into an empty read would hide exactly that.

The file lives under `app/` rather than `tests/` for a type-checking reason: `mypy app tests` then holds it to the `MediaStorage` Protocol the same way it holds [[backend/app/storage/s3.py]] and [[backend/app/storage/unconfigured.py]], so the fake cannot silently drift from the port it fakes.

## Depends On

- [[backend/app/storage/base.py]] — `MediaStorageUnavailableError`, `ObjectHead`, `PresignedPost`

## Depended On By

- [[backend/tests/test_storage_port.py]]
- [[backend/tests/test_catalog_api.py]]
- [[backend/tests/test_catalog_integration.py]]
- [[backend/tests/test_catalog_isolation.py]]
- [[backend/tests/test_storefront_api.py]]
- [[backend/tests/test_storefront_integration.py]]
- [[backend/tests/test_storefront_isolation.py]]
- [[backend/tests/test_staff_role_gating.py]]
- [[backend/tests/test_booking_owner_db.py]]

## Concepts

- [[Media Storage]]

## Tests

- [[backend/tests/test_storage_port.py]] — `test_every_implementation_satisfies_the_port` includes this class; `_UnsignableStorage` subclasses it to prove a read degrades to a `null` url when signing fails

## Notes

Nothing here enforces the policy conditions that make [[backend/app/storage/s3.py]] safe (exact key, exact type, exact byte count). Those are only exercised against real object storage in [[backend/tests/test_media_upload_s3.py]] — a test that passes against this fake proves the *call sequence*, never the S3-side enforcement.
