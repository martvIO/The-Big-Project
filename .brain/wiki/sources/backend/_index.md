---
tags: [backend, python]
sources: [backend]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend
blob: f3b77d0798fa9fc983d3be353ebfb8e6644fba6b
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/

**Purpose.** The Python 3.13 / FastAPI service: the whole API, the async SQLAlchemy data layer, the raw-SQL migrations, and the background worker. Managed by `uv`; driven by the root `Makefile`.

**Parent.** _(repository root)_

## Files

- [[backend/.env.example]]
- [[backend/.python-version]]
- [[backend/alembic.ini]]
- [[backend/pyproject.toml]]
- [[backend/uv.lock]]

## Subdirectories

- [[backend/app/_index]] — The application package. One sub-package per bounded surface (auth, booking, catalog, boutique, storefront, notifications, platform), plus the shared plumbing every one of them imports: the settings object, the error bases, the CSRF and security-header middleware, and the ASGI factory that wires it all together.
- [[backend/migrations/_index]]
- [[backend/tests/_index]] — The test suite. Unmarked tests run everywhere; `db`-marked tests need Docker (Testcontainers Postgres) and `s3`-marked ones additionally need MinIO, so both are CI-only.
