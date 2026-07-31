---
tags: [backend, boutique, python, package-marker]
sources: [backend/app/boutique/__init__.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/boutique/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/boutique/__init__.py

**Role.** Empty package marker for the owner-settings module (profile, toggles, appointment types, opening hours, cancellation-policy terms) — it re-exports nothing.

**Module.** [[backend/app/boutique/_index]] · **Layer.** api

## Public Surface

Nothing. Zero bytes.

## Behavior

Consumers import submodules directly: [[backend/app/main.py]] pulls `BoutiqueSettingsService` and the four typed errors out of [[backend/app/boutique/service.py]], and the storefront and booking test suites pull `WeeklyRuleInput` out of [[backend/app/boutique/validation.py]]. Keeping this file empty is what stops a package-level alias from becoming a second, staler name for any of them.

## Depends On

Nothing.

## Depended On By

- Every `app.boutique.*` import in the tree, implicitly.

## Concepts

- [[Package Layout]]

## Tests

None of its own.
