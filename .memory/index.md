# Project Memory Index

- [scaffold-migration.md](patterns/scaffold-migration.md) — when replacing a scaffold, explicitly diff the old tree's config files against the new one; package-manager defaults don't reproduce prior guardrails
- [async-testcontainers-fixtures.md](patterns/async-testcontainers-fixtures.md) — sync fixtures + asyncio.run() for Testcontainers/Alembic setup; async work only inside test bodies (avoids cross-event-loop failures)
