---
tags: [backend, python, async, storage]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# AnyIO

**Purpose.** The async runtime [[Starlette]] and [[FastAPI]] are built on. This repo touches it
directly in exactly one place: `to_thread.run_sync` in [[backend/app/storage/s3.py]].

boto3 is a blocking library, so the three real network calls on the storage port —
`head_object`, `read_prefix`, `delete_object` — wrap their synchronous inner function in
`await to_thread.run_sync(...)` to keep the event loop free. The other two port methods
(`presigned_post`, `signed_get_url`) are deliberately plain `def`, because botocore signs those
with local HMAC and does no I/O — see the `MediaStorage` protocol docstring in
[[backend/app/storage/base.py]].

**Trap.** `anyio` is **not** in `[project].dependencies` in [[backend/pyproject.toml]] — the
import works only because FastAPI pulls it in through Starlette. Nothing pins it, so a future
dependency rearrangement that drops Starlette's transitive anyio breaks `app/storage/s3.py` at
import time, not at call time.

## Related

- [[Media Storage]] · [[Ports And Adapters]] · [[Boto3]]
