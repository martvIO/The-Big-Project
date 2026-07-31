---
tags: [backend, python, architecture, conventions]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Package Layout

**What it is.** The shape every feature package under `backend/app/` takes. Knowing it means you
can guess a file's path before looking: a feature is a directory, and inside it the same four
module names recur.

## The quadruple

| Module | Holds |
|---|---|
| `router.py` | FastAPI routes, dependency wiring, HTTP status mapping |
| `schemas.py` | Pydantic request/response models (`ForbidExtraModel` subclasses) |
| `service.py` | business logic; owns the `tenant_session`, i.e. the transaction |
| `validation.py` | pure functions and constants, importable with no DB and no app |

[[backend/app/boutique/router.py]] / [[backend/app/boutique/schemas.py]] /
[[backend/app/boutique/service.py]] / [[backend/app/boutique/validation.py]] is the canonical set;
`catalog`, `storefront` and `notifications` repeat it exactly. `booking` and `auth` are the two that
grew extra modules rather than extra packages — `booking` adds `owner.py` + `owner_router.py`,
`manage.py`, `slots.py`/`slots_io.py`, `comms.py`, `tokens.py`, `backfill.py`; `auth` adds
`staff.py` + `staff_router.py`, `passwords.py`, `cookies.py`, `dependencies.py`, `rate_limit.py`,
`tokens.py`. [[backend/app/auth/staff.py]] records the reasoning: two files in an existing package,
not a new `app/staff/` package for one router.

The split between `validation.py` and `service.py` is what makes the fast test suite possible —
validation is import-safe with no database, so `test_*_validation.py` runs without a container.

## `__init__.py` is always zero bytes

Never a re-export barrel. Consumers import the concrete submodule
(`from app.catalog.service import CatalogService`), so a package-level alias can never become a
second, staler name. In [[backend/app/db/repositories/__init__.py]] the emptiness is load-bearing
for a further reason: a barrel there would make importing one repository transitively import every
model onto the declarative base, and both Alembic autogenerate and the forced-RLS metadata scan
depend on which models are registered at a given moment.

## The other four kinds of directory

- **`models/`** — one file per table, plus `base.py` (`StandardColumns`) and `constants.py`
  (every `StrEnum` in the product). See [[Soft Delete]].
- **`db/repositories/`** — one file per table, mirroring `models/`. See [[Repository Pattern]].
- **`db/`** proper — `session.py`, `tenant.py`, `rls.py`: the three files [[Row Level Security]]
  lives in.
- **Ports** — `storage/` and `notifications/` are not features but adapter packages: `base.py`
  defines a `Protocol` and the typed errors, then one real implementation, one in-memory fake and
  one `unconfigured.py` that raises on every method. See [[Ports And Adapters]] and [[Media Storage]].

App-root singletons sit beside the packages: [[backend/app/main.py]] (the only composition root),
[[backend/app/errors.py]], [[backend/app/schemas.py]], [[backend/app/csrf.py]],
[[backend/app/security_headers.py]], [[backend/app/cli.py]], [[backend/app/worker.py]].

## Gotchas

- **Tests are flat.** `backend/tests/` has no packages at all — one `test_<feature>_<layer>.py` per
  slice (`_validation`, `_service`, `_api`, `_integration`, `_isolation`, `_db`), sharing one
  [[backend/tests/conftest.py]].
- `.claude/rules/` describes a Kotlin/Micronaut `module-client` / `module-repository` layout. None
  of it applies — see [[Documented Stack Vs Actual Stack]].

## Related

- [[Repository Pattern]] · [[Media Storage]] · [[Row Level Security]] · [[FastAPI]]
