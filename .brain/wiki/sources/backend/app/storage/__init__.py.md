---
tags: [backend, storage, media, python, package]
sources: [backend/app/storage/__init__.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storage/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/storage/__init__.py

**Role.** Empty package marker for `app.storage` — the media storage port and its three implementations.

**Module.** [[backend/app/storage/_index]] · **Layer.** platform

## Public Surface

Nothing. The file is zero bytes; it re-exports nothing.

## Behavior

Every consumer imports the concrete module it needs — [[backend/app/storage/base.py]] for the port and the error types, [[backend/app/storage/s3.py]], [[backend/app/storage/unconfigured.py]] or [[backend/app/storage/memory.py]] for an implementation. Keeping this file empty means importing `app.storage.base` does not drag `boto3` into a process that only needs the Protocol.

## Depends On

Nothing.

## Depended On By

Implicitly every importer of `app.storage.*`.

## Concepts

- [[Media Storage Port]]

## Tests

None — nothing to test.
