---
tags: [backend, platform, python, package]
sources: [backend/app/platform/__init__.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/platform/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/platform/__init__.py

**Role.** Empty package marker for `app.platform` — the operator-side surface: tenant provisioning and the INSERT-only platform audit log.

**Module.** [[backend/app/platform/_index]] · **Layer.** platform

## Public Surface

Nothing. The file is zero bytes; it re-exports nothing.

## Behavior

Consumers import the concrete module: [[backend/app/cli.py]] imports `ProvisioningService`, `CommandResult` and `TenantSummary` from [[backend/app/platform/service.py]], and the service itself constructs [[backend/app/platform/repository.py]]'s `PlatformAuditLogRepository`. Nothing under `app/api/` reaches into this package — the operator surface is CLI-only until F25's platform console.

## Depends On

Nothing.

## Depended On By

Implicitly every importer of `app.platform.*`.

## Concepts

- [[Platform Audit Log]]

## Tests

None — nothing to test.
