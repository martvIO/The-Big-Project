---
tags: [backend, auth, python, package]
sources: [backend/app/auth/__init__.py]
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/auth/__init__.py
blob: e69de29bb2d1d6434b8b29ae775ad8c2e48c5391
commit: d9d860b47f2c78acb9ce7304f18c1e18cc370851
kind: code
applicability: active
---

# backend/app/auth/__init__.py

**Role.** Empty file marking `app.auth` as a package — the home of [[Owner Authentication]]: password hashing, session tokens, cookies, the login rate limiter, the FastAPI router and its request dependencies.

**Module.** [[backend/app/auth/_index]] · **Layer.** auth

## Behavior

Zero bytes, no re-exports. Every consumer imports the concrete module (`from app.auth.service import AuthService`), which keeps `import app.auth.passwords` from dragging in the SQLAlchemy-dependent service layer.

## Concepts

- [[Owner Authentication]]
