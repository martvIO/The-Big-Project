---
tags: [backend, db, security]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: n/a
---

# Least Privilege Database Role

**Purpose.** The application connects to [[PostgreSQL]] as a non-owner role so that `FORCE ROW LEVEL SECURITY` actually binds it.

Table owners are exempt from plain `ENABLE ROW LEVEL SECURITY`; `FORCE` removes that exemption, but only for non-owners does the distinction matter. Connecting as the owner would silently defeat [[Row Level Security]].

The application role is established in [[backend/migrations/versions/0002_tenants_app_role.py]] and the running role is checked at startup by [[backend/app/db/session.py]].
