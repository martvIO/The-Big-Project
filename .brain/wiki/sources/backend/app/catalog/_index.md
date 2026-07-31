---
tags: [backend, python]
sources: [backend/app/catalog]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/catalog
blob: dc2fed40eb7c2a557d559dd52a0ca6ac90d94a57
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/catalog/

**Purpose.** The owner's dress catalogue — dresses, size variants, and the presign/confirm media pipeline that puts photos in S3.

**Parent.** [[backend/app/_index]]

## Files

- [[backend/app/catalog/__init__.py]] — Empty package marker for the owner's dress catalogue module — it re-exports nothing, so every consumer imports the concrete submodule by name.
- [[backend/app/catalog/keys.py]] — The only place an S3 object key or a download filename for dress media is constructed — `tenants/{tenant_id}/dresses/{dress_id}/media/{media_id}{ext}` — with the extension derived from the server-side content-type map rather than from…
- [[backend/app/catalog/router.py]] — The eleven `/manage` catalog endpoints — a thin translator between HTTP and `CatalogService`'s frozen views — gated router-wide on `OWNER | SHIFT_MANAGER` and stamped router-wide with `Cache-Control: no-store`.
- [[backend/app/catalog/schemas.py]] — The wire contract for the `/manage` catalog API — extra-forbidding request models whose `Field` bounds mirror [[backend/app/catalog/validation.py]], plus response models for dresses, variants, media and the presigned POST.
- [[backend/app/catalog/service.py]] — All catalog business logic — dress CRUD with archive/restore, the whole-matrix variant replace, and the three-step S3 media lifecycle (presign → browser POST → confirm) — plus `sign_media`, the one function that mints signed GET URLs for…
- [[backend/app/catalog/validation.py]] — The single home of catalog *product policy* — every numeric bound, the accepted image-type set, the magic-byte signature table, the presign/signed-GET/pending TTLs and the list page sizes — as pure I/O-free functions and constants that the…
