---
tags: [backend, python, http, middleware]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Starlette

**Purpose.** The ASGI toolkit [[FastAPI]] is built on. Not a declared dependency in
[[backend/pyproject.toml]] — it arrives through FastAPI — yet it is imported directly wherever
this app works below the FastAPI abstraction: every middleware, every hand-built response, and
every cookie write.

Direct importers: [[backend/app/csrf.py]], [[backend/app/security_headers.py]],
[[backend/app/tenancy/middleware.py]] (all three on `BaseHTTPMiddleware`), and
[[backend/app/auth/cookies.py]] (`Response`, for `set_cookie`/`delete_cookie`).

**The MRO rule is load-bearing.** Starlette resolves an exception handler by walking
`type(exc).__mro__`, so a handler registered on a concrete class matches that class and its
subclasses **only**. That is the entire reason [[backend/app/errors.py]] exists: `DomainNotFoundError`
and `DomainValidationError` are bases that every domain module raises through, and the two
platform-wide handlers in [[backend/app/main.py]] bind to *those*, not to `app.boutique`'s own
classes. Bound to a concrete class instead, every `app/catalog/` 404 and domain-400 would fall
through as an unhandled **500**. [[backend/app/boutique/service.py]] and
[[backend/app/boutique/validation.py]] keep their historical subclasses precisely because the MRO
still matches them; the error-code table in [[backend/tests/test_catalog_api.py]] is what pins it.

**Middleware order is registration order, reversed.** `BaseHTTPMiddleware` registered *last* in
`create_app()` runs *outermost* — which is how [[backend/app/security_headers.py]] gets to stamp
headers onto responses produced by everything inside it, including the middlewares that
short-circuit.

## Related

- [[FastAPI]] · [[Tenant Resolution]] · [[Fail Closed Defaults]] · [[Uvicorn]]
