# Project Memory Index

- [scaffold-migration.md](patterns/scaffold-migration.md) — when replacing a scaffold, explicitly diff the old tree's config files against the new one; package-manager defaults don't reproduce prior guardrails
- [async-testcontainers-fixtures.md](patterns/async-testcontainers-fixtures.md) — sync fixtures + asyncio.run() for Testcontainers/Alembic setup; async work only inside test bodies (avoids cross-event-loop failures)
- [two-layer-fail-closed-parsing.md](patterns/two-layer-fail-closed-parsing.md) — split extraction from validation for security-critical identifiers; test both layers plus the pipeline (reuse in Feature 6 CLI)
- [commit-before-raise-in-tenant-session.md](patterns/commit-before-raise-in-tenant-session.md) — a DB write + raise in the same tenant_session transaction is rolled back; commit failure-path audit/log rows before raising
- [insert-only-table-no-returning.md](patterns/insert-only-table-no-returning.md) — INSERT-only append tables: REVOKE ALL before GRANT INSERT (default privileges leak CRUD), and generate PK+timestamps client-side so no RETURNING needs SELECT
- [atomic-parent-child-across-rls.md](patterns/atomic-parent-child-across-rls.md) — client-side UUID + tenant_session to atomically create an RLS-free parent and RLS-forced child in one transaction
