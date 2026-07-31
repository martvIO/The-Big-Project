---
tags: [backend, notifications, python, package]
sources: [backend/app/notifications/__init__.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/notifications/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/notifications/__init__.py

**Role.** Empty package marker for the SMS/OTP module — it re-exports nothing, so every importer names the submodule directly (`from app.notifications.service import OtpService`).

**Module.** [[backend/app/notifications/_index]] · **Layer.** platform

## Public Surface

Nothing. The file is zero bytes.

## Behavior

No side effects at import time, which is the point: the package holds a port ([[backend/app/notifications/base.py]]), two adapters, a service pair, a router and a validation module, and any convenience re-export here would make importing the port drag in SQLAlchemy and the repositories.

## Depends On

Nothing.

## Depended On By

- [[backend/app/main.py]], [[backend/app/worker.py]], [[backend/app/booking/comms.py]], [[backend/app/booking/service.py]] — all import submodules through this package

## Concepts

- [[Ports And Adapters]]
