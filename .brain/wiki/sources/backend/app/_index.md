---
tags: [backend, python]
sources: [backend/app]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app
blob: 7dc0c86953c7661618737cb5fc659d91e000a7ed
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/

**Purpose.** The application package. One sub-package per bounded surface (auth, booking, catalog, boutique, storefront, notifications, platform), plus the shared plumbing every one of them imports: the settings object, the error bases, the CSRF and security-header middleware, and the ASGI factory that wires it all together.

**Parent.** [[backend/_index]]

## Files

- [[backend/app/__init__.py]] — Empty file whose only job is to make `app` an importable package, so every module is addressed as `app.<subpackage>.<module>` (`app.main:app` for [[Uvicorn]], `python -m app.cli`, `python -m app.worker`).
- [[backend/app/cli.py]] — The operator-only argparse front end for [[Tenant Provisioning]] — `provision`, `suspend`, `reset-password`, `list`, and (F16) `backfill-booking-links` — run over SSH/CI as `python -m app.cli`; it reads passwords from getpass/stdin (never…
- [[backend/app/csrf.py]] — Middleware that rejects a mutating `/manage` request whose `Origin` header names a different hostname than its `Host` header, with a 403 `CSRF_ORIGIN_MISMATCH` — the defense `SameSite=Lax` cannot provide once sibling tenant subdomains are…
- [[backend/app/errors.py]] — The two domain-error base classes every module raises through — `DomainNotFoundError` → house-shape 404, `DomainValidationError` → house-shape 400 carrying the exception's own message — so a new domain module inherits both responses…
- [[backend/app/main.py]] — The ASGI application factory: builds the `FastAPI` instance (API docs/schema dark outside dev), installs the security-headers, CSRF-origin and subdomain [[Tenant Resolution]] middleware, parks the shared `AuthService`…
- [[backend/app/schemas.py]] — Two wire primitives shared by every API module: `ForbidExtraModel`, the base every **request** model inherits so an unknown key is a 400 rather than a silently dropped field, and `OkResponse`, the single `{"ok": true}` body for mutations…
- [[backend/app/security_headers.py]] — Outermost middleware; stamps `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: strict-origin-when-cross-origin` onto every response the app emits — including the ones returned from inside another middleware…
- [[backend/app/worker.py]] — The background-process entrypoint (`uv run python -m app.worker`, wired into the root `Makefile` and deployed as its own Railway service).

## Subdirectories

- [[backend/app/api/_index]] — A scaffold vestige. It holds only the `/health` probe — every other router lives in its own domain package, so a reader looking here for "the API" is in the wrong place.
- [[backend/app/auth/_index]] — Owner and staff identity: password verification, opaque session tokens, the session cookie, and — since F31 — the role gate that makes every `/manage` route default-deny.
- [[backend/app/booking/_index]] — The booking engine and the most intricate code in the repo: the concurrency-safe seat claim, the availability question, the SMS lifecycle, the customer's tokenized manage page, and the owner console's booking surface.
- [[backend/app/boutique/_index]] — Owner settings: profile, opening hours, appointment types, and the append-only terms versions a booking pins itself to.
- [[backend/app/catalog/_index]] — The owner's dress catalogue — dresses, size variants, and the presign/confirm media pipeline that puts photos in S3.
- [[backend/app/core/_index]] — The settings object, and only that. Deployment identity lives here; product policy deliberately does not.
- [[backend/app/db/_index]] — Engine, session factory, the tenant-binding wrapper that sets the RLS context, and the repository layer beneath.
- [[backend/app/models/_index]] — The SQLAlchemy declarative models — one per table, each mirroring a raw-SQL migration, plus the shared base and the `StrEnum` registry whose values several DB `CHECK` constraints pin.
- [[backend/app/notifications/_index]] — The SMS port and the OTP primitive: a provider-agnostic sender, its fake and unconfigured adapters, and the single writer of the `message_log` evidence trail.
- [[backend/app/platform/_index]] — The operator-side surface — tenant provisioning and the INSERT-only platform audit log. CLI-only; it has no HTTP routes at all.
- [[backend/app/storage/_index]] — The media abstraction: an S3 adapter, an in-memory one for tests, and an unconfigured one that answers 503 — because a missing bucket is a supported deployment, not a crash.
- [[backend/app/storefront/_index]] — The public, anonymous read surface: the catalogue a bride browses and the slot grid she books from. Contractually GET-only and cookie-blind.
- [[backend/app/tenancy/_index]] — Subdomain-to-tenant resolution and the middleware that runs it — the thing every RLS session context depends on.
