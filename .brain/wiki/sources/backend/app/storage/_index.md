---
tags: [backend, python]
sources: [backend/app/storage]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storage
blob: 6885b841a22175f7481f94b70ef92891bafd45b5
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/storage/

**Purpose.** The media abstraction: an S3 adapter, an in-memory one for tests, and an unconfigured one that answers 503 — because a missing bucket is a supported deployment, not a crash.

**Parent.** [[backend/app/_index]]

## Files

- [[backend/app/storage/__init__.py]] — Empty package marker for `app.storage` — the media storage port and its three implementations.
- [[backend/app/storage/base.py]] — Defines the media storage port — the `MediaStorage` Protocol its three implementations satisfy, the two value objects they return, and the two exception types that let a missing bucket and an unreachable bucket both degrade to 503 instead…
- [[backend/app/storage/memory.py]] — A dict-backed `MediaStorage` implementation that lets the presign→confirm sequence, the API fakes and the isolation suites run with working media and no container.
- [[backend/app/storage/s3.py]] — The production media storage implementation: mints browser-direct POST upload policies that S3 itself enforces (exact key, exact content type, exact byte count), signs attachment-forcing GET URLs, and runs head/read/delete off the event…
- [[backend/app/storage/unconfigured.py]] — The null-object implementation of the media storage port for deployments with no `MEDIA_BUCKET` — every method raises `MediaNotConfiguredError` so the router answers one 503 and the rest of the catalog keeps working.
