---
tags: [backend, python]
sources: [backend/app/core]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/core
blob: 9d2bf86e71d9635b0a10e3b4dba6cb0f23d93972
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/core/

**Purpose.** The settings object, and only that. Deployment identity lives here; product policy deliberately does not.

**Parent.** [[backend/app/_index]]

## Files

- [[backend/app/core/__init__.py]] — Empty file marking `app.core` as a package; the subpackage currently holds exactly one module, [[backend/app/core/config.py]].
- [[backend/app/core/config.py]] — The single environment-backed settings object: database URL, platform base domain, session TTL, every rate-limit window, media and SMS deployment identity, and the proxy-trust flag — with **four** boot-time validators that refuse to start…
