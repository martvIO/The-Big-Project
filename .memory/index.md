# Project Memory Index

- [scaffold-migration.md](patterns/scaffold-migration.md) — when replacing a scaffold, explicitly diff the old tree's config files against the new one; package-manager defaults don't reproduce prior guardrails
- [async-testcontainers-fixtures.md](patterns/async-testcontainers-fixtures.md) — sync fixtures + asyncio.run() for Testcontainers/Alembic setup; async work only inside test bodies (avoids cross-event-loop failures)
- [two-layer-fail-closed-parsing.md](patterns/two-layer-fail-closed-parsing.md) — split extraction from validation for security-critical identifiers; test both layers plus the pipeline (reuse in Feature 6 CLI)
