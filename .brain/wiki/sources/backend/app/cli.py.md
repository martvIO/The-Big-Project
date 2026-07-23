---
tags: [backend, cli, python, platform, entrypoint]
sources: [backend/app/cli.py]
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/cli.py
blob: 0a6844733ca6387e08de3c7b20363b79d593a4c3
commit: d9d860b47f2c78acb9ce7304f18c1e18cc370851
kind: code
applicability: active
---

# backend/app/cli.py

**Role.** The operator-only argparse front end for [[Tenant Provisioning]] — `provision`, `suspend`, `reset-password`, `list` — run over SSH/CI as `python -m app.cli`; it reads passwords from getpass/stdin (never argv), sanitizes operator-supplied text before printing, and delegates every state change to `ProvisioningService`.

**Module.** [[backend/app/_index]] · **Layer.** cli

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `main` | fn | Process entrypoint: parses argv, awaits the database role check, builds `ProvisioningService`, dispatches; returns the exit code |
| `build_parser` | fn | Constructs the `ArgumentParser` with the four required subcommands and the shared `--operator` flag |
| `run` | fn | Test seam — `asyncio.run(_dispatch(...))` with an injected service and password reader, no database bootstrap |
| `ProvisioningLike` | class | `Protocol` describing the four service methods, so `run` accepts a fake |
| `PasswordReader` | const | `Callable[[], str]` type alias for the injected password source |

## Behavior

`main` imports [[backend/app/db/session.py]] and [[backend/app/platform/service.py]] *inside the function*, keeping module import cheap and database-free; it then awaits `ensure_safe_database_role` for the same reason the web app does — an operator running under personal elevated credentials would silently void the `WITH CHECK` isolation net. `_dispatch` maps the subcommand to a service coroutine and funnels the `CommandResult` through `_report`, which prints `OK: <message>` (appending the new tenant id when present) and returns 0, or prints `FAILED: <message>` to stderr and returns 1; an unrecognized command returns 2, though argparse's `required=True` on the subparser normally makes that unreachable. `list` prints tab-separated `slug, status, name, created_at` rows, or `(no tenants)` for an empty result. Every operator-supplied string that reaches stdout passes through `_safe`, which replaces C0 control characters and DEL with spaces so a tab or newline cannot corrupt the columnar output and an ANSI escape cannot spoof the terminal. `_read_password` uses `getpass` when stdin is a TTY and a single stripped stdin line otherwise, which is what makes CI piping work without leaking the secret into the process list or shell history. `--operator` defaults to `$USER` and is recorded on the platform audit row for each mutation.

## Depends On

- [[backend/app/platform/service.py]] — `ProvisioningService`, `CommandResult`, `TenantSummary`
- [[backend/app/db/session.py]] — lazy session factory and `ensure_safe_database_role` (imported lazily inside `main`)

## Concepts

- [[Tenant Provisioning]]
- [[Audit Trail]]
- [[Row Level Security]]

## Tests

- [[backend/tests/test_cli.py]] — parser shape, `run` against a fake `ProvisioningLike`, exit codes, and `_print_tenants` control-character sanitization
- [[backend/tests/test_provisioning.py]] — the service behind the CLI, against real Postgres

## Notes

`--owner-password` is intentionally absent from every subcommand; adding it would reintroduce the argv leak the module docstring warns about. Spec and plan: [[.planning/specs/tenant-provisioning-cli.md]], [[.planning/plans/tenant-provisioning-cli.md]].
