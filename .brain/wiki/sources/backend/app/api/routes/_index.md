---
tags: [backend, python]
sources: [backend/app/api/routes]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/api/routes
blob: bb551ad84ae8ec104e49bbe14079bcaf9e03061c
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/api/routes/

**Purpose.** The health probe, and nothing else.

**Parent.** [[backend/app/api/_index]]

## Files

- [[backend/app/api/routes/__init__.py]] — Empty file marking `app.api.routes` as a package; its only member is the unauthenticated `/health` probe.
- [[backend/app/api/routes/health.py]] — The unauthenticated, host-agnostic liveness probe: answers `{status, version, media}` where `media` reports only *whether* a media bucket is configured — never which one.
