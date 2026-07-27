---
tags: [backend, tests, python, media]
sources: [backend/tests/conftest.py]
created: 2026-07-23
updated: 2026-07-27
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/tests/conftest.py
blob: 02282c4f66458f74770caf3cd65c0ed918fccdae
commit: e8fd318e17e17aefef55205facf914e60e3a0160
kind: code
applicability: active
---

# backend/tests/conftest.py

**Role.** Guarantees that every `-m db` test runs against a real [[PostgreSQL]] 16 instance with all [[Alembic]] migrations applied **and connects as a non-owner, non-superuser login role**, so that an isolation assertion can never pass vacuously by virtue of the test principal bypassing [[Row Level Security]].

**Module.** [[backend/tests/_index]] · **Layer.** test

## Fixtures

| Fixture | Scope | Yields / Returns |
|---|---|---|
| `run_sql` | session | Callable `(url, statements) -> None` that opens its own engine and runs DDL/DML in one transaction, **outside any test event loop**, via `asyncio.run` |
| `postgres_url` | session | Superuser connection URL for a [[Testcontainers]] `postgres:16-alpine` container; calls `pytest.fail(DOCKER_HELP, pytrace=False)` — not skip — when no Docker daemon is reachable |
| `migrated_db` | session | The same superuser URL, after `alembic upgrade head` and after creating the `boutique_app` LOGIN role and granting it the `app_user` group role from [[backend/migrations/versions/0002_tenants_app_role.py]] |
| `app_role_url` | session | `migrated_db` rewritten to authenticate as `boutique_app` — the least-privileged principal production uses |
| `minio_container` | session | A real [[MinIO]] via [[Testcontainers]]; yields a `MinioEndpoint` (url + creds + bucket), never an open client |

Module-level helpers: `_docker_running` (shells out to `docker info` with a 10s timeout), `_execute_all` (the async body behind `run_sql`), `_create_bucket` (creates the test bucket with the `boto3` client already depended on, not the minio SDK), the frozen `MinioEndpoint` dataclass, and the constants `APP_ROLE_NAME` / `APP_ROLE_PASSWORD` / `DOCKER_HELP` / `BACKEND_DIR` / `MINIO_IMAGE` (pinned `minio/minio:RELEASE.2025-04-22…`) / `MEDIA_BUCKET`.

## Behavior

Every fixture here is **plain synchronous Python** even though all the work it does is async; one-off async calls go through `asyncio.run`. This is deliberate and is the single most load-bearing decision in the file — see [[.memory/patterns/async-testcontainers-fixtures.md]]. `asyncio_mode = "auto"` in [[backend/pyproject.toml]] gives every test its own event loop, so a session-scoped *async* fixture would bind its engine to a loop that no test owns and produce "Future attached to a different loop". Returning bare URL strings sidesteps the problem entirely: each test builds and disposes its own engine.

`migrated_db` drives [[Alembic]] programmatically through `Config`, pointing `script_location` at [[backend/migrations/env.py]]'s directory and overriding `sqlalchemy.url` with the container URL, so [[backend/alembic.ini]] supplies only the remaining defaults. Role creation is wrapped in a `DO $$ ... IF NOT EXISTS` block so a re-run against a still-warm session container is a no-op.

`app_role_url` is derived by string surgery on `migrated_db` (split on `://` then `@`), not rebuilt from container attributes — it therefore always points at the same host/port/database as the migrated superuser URL.

The container is **shared across the whole session and never truncated between tests**. Tests that assert on row counts must therefore scope themselves to a freshly generated tenant UUID or a unique slug rather than assuming an empty table.

`minio_container` is the media analogue of `postgres_url`, and every design choice rhymes with the Postgres one. MinIO was chosen over `moto` by binding decision: it performs genuine SigV4 verification and actually enforces POST-policy conditions, so the upload assertions in [[backend/tests/test_media_upload_s3.py]] mean something a fake would not. It yields an *endpoint + credentials*, never a client — a module-level boto3 client anywhere would start the container during collection, including under `-m 'not db'`. The bucket is created through the same `boto3` client the app already depends on (SigV4, path-style addressing) rather than the `minio` SDK, so the test tree grows no second untyped import. Missing Docker `pytest.fail`s here too, so a daemon-less CI run cannot silently drop the media suite.

## Depends On

- [[backend/alembic.ini]] — Alembic config file loaded by `migrated_db`
- [[backend/migrations/env.py]] — the migration environment `alembic upgrade head` executes
- [[backend/migrations/versions/0002_tenants_app_role.py]] — creates the `app_user` group role that `boutique_app` is granted
- [[backend/pyproject.toml]] — declares the `db` marker and `asyncio_mode = "auto"`
- [[pytest]] · [[Testcontainers]] · [[Docker]] · [[SQLAlchemy]] · [[Alembic]] · [[PostgreSQL]] · [[MinIO]] · [[boto3]]

## Covers

- [[backend/migrations/env.py]] — exercised end to end by every `migrated_db` consumer
- [[backend/alembic.ini]]
- [[backend/migrations/versions/0002_tenants_app_role.py]] — the `app_user` grant path

## Consumed By

- [[backend/tests/test_migrations.py]] · [[backend/tests/test_role_guard.py]] · [[backend/tests/test_tenant_isolation.py]] · [[backend/tests/test_tenants_repository.py]] · [[backend/tests/test_tenancy_integration.py]] · [[backend/tests/test_auth_integration.py]] · [[backend/tests/test_provisioning.py]]
- Media (`minio_container`): [[backend/tests/test_storage_port.py]] · [[backend/tests/test_media_upload_s3.py]]

## Concepts

- [[Row Level Security]]
- [[Tenant Isolation]]
- [[Least Privilege Database Role]]
- [[DB Test Marker]]
- [[Database Migrations]]
- [[Media Storage]]

## Notes

- The comment above `APP_ROLE_NAME` states the rule this whole file exists to enforce: the container superuser bypasses RLS unconditionally, so isolation assertions run as the superuser would all pass while proving nothing. [[backend/tests/test_tenant_isolation.py]] adds a runtime guard for the same hazard.
- Missing Docker **fails** rather than skips, so a CI runner without a daemon cannot silently drop the isolation suite. Fast-only runs are the documented escape hatch: `make test` in [[Makefile]].
- `APP_ROLE_PASSWORD` is a hardcoded container-only credential; it never leaves the ephemeral Testcontainers instance.
