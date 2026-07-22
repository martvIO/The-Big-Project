# Plan: Feature 4 — Subdomain Routing & Tenant Resolution (Epic E1)

## Context

Features 1 (scaffolds/CI, PR #1) and 3 (tenant core + RLS, PR #2) are built, double-ACCEPT-reviewed, and CI-green. Feature 4 is next in the approved order: turn `{slug}.{base-domain}` requests into a resolved tenant bound to the request — the second layer of the isolation defense (layer 1 = RLS, layer 2 = "tenant comes only from the hostname, never from client input"). Branch `feature/subdomain-routing` stacks on `feature/tenant-core-rls` (PR #3 → base PR #2). On approval: spec+plan saved to `.planning/`, then TDD build → dual reviewer agents → stacked PR → CI watch, same pipeline as Features 1/3.

**Status**: draft · **Epic**: E1 (Feature 4 of 6) · **Effort**: M · **Created**: 2026-07-21

## Problem

Nothing maps an incoming host to a tenant. Every storefront/manage feature after this needs the request already bound to exactly one active boutique, with unknown, suspended, deleted, or reserved hostnames rejected — and the tenant identity must be impossible to supply via client input.

## Goal

A request to `bella.localtest.me:8000` (dev) resolves the active tenant "bella" and exposes it to routes; any other host — unknown slug, suspended/soft-deleted tenant, reserved name, apex domain, garbage — gets a clean 404. `/health` (and API-docs paths, for now) stay host-agnostic.

## Design

**New module `backend/app/tenancy/`** (router-per-domain layout):

- `slugs.py` — pure functions, no I/O:
  - `RESERVED_SLUGS` frozenset (`www`, `api`, `admin`, `app`, `mail`, `staging`, `cdn`, `assets`, `status`, `docs`, …) — also imported by Feature 6's provisioning CLI so reservation is enforced at both ends.
  - `is_valid_slug(slug)` — DNS-label rule: `^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$`, not reserved.
  - `extract_slug(host, base_domain)` — strips port, lowercases, requires exactly `<label>.<base_domain>`; returns `None` for apex, multi-label, empty/missing host, non-matching domains.
- `middleware.py`:
  - `TenantContext` frozen dataclass: `id: UUID`, `slug: str`, `settings: dict` — a boundary type, not the ORM entity.
  - `TenantResolver` protocol: `async (slug) -> TenantContext | None`. Production impl wraps `TenantsRepository.by_slug` (active-only filtering — suspended/deleted already excluded — direct indexed lookup, no cache per the verified roadmap decision). Injecting the resolver at `create_app(resolver=...)` keeps tests free of global-engine monkeypatching.
  - Starlette middleware: exempt paths (`/health`, `/openapi.json`, `/docs`, `/redoc` — docs exposure revisited at the Feature 21 hardening gate) pass through; otherwise `extract_slug` → validate → resolve → attach `request.state.tenant` or return 404 JSON (`{"error": {"code": "TENANT_NOT_FOUND", ...}}`, snake_case). One generic 404 for all failure kinds — don't leak whether a slug exists.
- `get_current_tenant` FastAPI dependency reading `request.state.tenant` for later features' routes.

**Config**: `base_domain` setting (default `localtest.me` for dev; staging/prod set the real domain via env — the actual production domain is still an open external item).

**Explicitly out of scope**: Redis slug caching (E5), marketing page on apex (404 for now), auth (Feature 5), wiring `tenant_connection`/RLS into request handling (first route that touches tenant data does this — Feature 7), reserved-slug enforcement at provisioning time (Feature 6, imports the same constant).

## Tasks (TDD; local red→green for pure logic, db-marked tests CI-gated as before)

1. **Slug/host parsing** — `tests/test_slugs.py` first (valid/invalid/reserved slugs; extract: happy, port, uppercase, apex, multi-label, wrong domain, empty host) → implement `slugs.py`. Pure unit tests, run locally.
2. **Config** — `base_domain` added to `Settings` + unit test.
3. **Middleware + wiring** — `middleware.py`, resolver protocol + production resolver, `create_app(resolver=None)` wiring; `TestClient`-based unit tests with a **fake resolver** (no DB): resolution attaches state, 404 paths, exempt paths, generic-404 indistinguishability.
4. **DB integration tests** (`@pytest.mark.db`) — app wired to a real resolver against the Testcontainers DB via the existing `app_role_url`/fixtures from Feature 3's harness (`tests/conftest.py`): active tenant resolves end-to-end (probe route echoes tenant id), suspended → 404, soft-deleted → 404, reserved slug → 404 even if a row exists.
5. **Docs + status** — README dev-domain note (`{slug}.localtest.me:8000`), epic table Feature 4 → building→(done via PR), rsync `.planning/` to main repo.

**Reuse**: `TenantsRepository.by_slug` (backend/app/db/repositories/tenants.py), `get_session_factory` (backend/app/db/session.py), test fixtures `migrated_db`/`app_role_url`/`run_sql` (backend/tests/conftest.py).

## Security notes (for the reviewers' benefit, addressed by design)

- Tenant identity derives from Host header only; Host is attacker-controlled in principle, but the only thing a forged Host yields is *another tenant's public storefront* — the same thing DNS gives anyone; no privilege attaches to resolution itself. Unmatched hosts fail closed (404).
- Generic 404 prevents slug-existence enumeration distinguishing "unknown" vs "suspended".
- Resolver output is a minimal frozen `TenantContext` — routes can't accidentally mutate or lazy-load through an ORM object.

## Verification

1. Local: `uv run pytest -m "not db"` — slug/middleware unit tests green (red shown first for Task 1); ruff + mypy clean; `pnpm` untouched.
2. Manual: `make dev` → `curl -H "Host: nosuch.localtest.me" localhost:8000/` → 404 JSON; `curl localhost:8000/health` → 200 regardless of host.
3. CI on stacked PR #3: full suite incl. new db integration tests (isolation suite from Feature 3 keeps running).
4. Dual reviewer agents (quality + adversarial security) → fix loop → both ACCEPT before ship, per pipeline.

## After approval

Save spec (`.planning/specs/subdomain-routing.md`) + this plan (`.planning/plans/subdomain-routing.md`), create the stacked worktree, build per tasks above, ship PR #3 stacked on #2. Standing reminders: PRs #1/#2 await your merge; Grow account, SMS sender-ID, production domain, and staging accounts remain user-side blockers for Feature 2.
