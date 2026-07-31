---
tags: [backend, testing, design]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Test Doubles

**What it is.** The house testing style: hand-written `Fake*` classes that structurally match the
real collaborator, injected through FastAPI's own seams. `unittest.mock` patching does not appear
in this suite.

## Where the fakes live

Fakes are defined in the API test module that first needed them —
`FakeAuthService`, `FakeBoutiqueService` in [[backend/tests/test_boutique_api.py]],
`FakeCatalogService` in [[backend/tests/test_catalog_api.py]] — and are then **imported across test
modules**. [[backend/tests/test_staff_role_gating.py]] imports both, along with their hand-
maintained `ROUTES` tables, so its HTTP matrix covers exactly what those modules cover.

Injection uses two seams and no monkeypatching: `app.state.<name>_service` for the services
`create_app` hangs there, and `app.dependency_overrides` for anything reached through `Depends`.

## The double that lives in `app/`

`InMemoryMediaStorage` is in [[backend/app/storage/memory.py]], not under `tests/`, and its
docstring says why: `mypy app tests` then checks it against the [[Ports And Adapters]] `Protocol`
exactly like the S3 and Unconfigured adapters. `FakeSmsSender`
([[backend/app/notifications/fake.py]]) is there for the same reason, and doubles as the
dev/staging adapter.

## Clocks are injected, and there are two kinds

Never conflated, because conflating them is how DST bugs are born:

- **monotonic** `Callable[[], float]` for rate-limit windows — elapsed time
  ([[backend/app/auth/rate_limit.py]]);
- **`WallClock`** returning aware UTC for expiry — calendar time
  ([[backend/app/notifications/service.py]]).

Similarly injectable rather than slept through: `PENDING_MEDIA_TTL_SECONDS` is a `CatalogService`
constructor argument so the abandoned-upload sweep is testable without backdating rows.

## Where a fake is *not* allowed

Anything touching [[Row Level Security]] runs against real Postgres via [[Testcontainers]] — SQLite
would lie ([[backend/tests/conftest.py]], and see [[DB Test Marker]]). Isolation tests must
additionally connect as the non-owner `boutique_app` role, because the container superuser bypasses
RLS unconditionally and every isolation assertion would pass vacuously.

## The trap: a fake that makes a test pass for the wrong reason

`test_unknown_role_is_403_on_every_gated_route` deliberately leaves the *real* (unconfigured)
`CatalogService` wired while exercising catalog routes. If the gate were a decoy that carried
`allowed_roles` but never raised, the request would fall through to that service and blow the test
up — instead of quietly passing against a helpful fake. A double that is *too* helpful is the
failure mode this suite is written against.

## Related

- [[DB Test Marker]] · [[Ports And Adapters]] · [[Role Based Access Control]]
- [[backend/tests/test_storage_port.py]] · [[backend/tests/test_rate_limit.py]] ·
  [[backend/tests/test_worker.py]]
