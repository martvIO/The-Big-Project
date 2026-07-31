---
tags: [backend, python, errors, platform, api]
sources: [backend/app/errors.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/errors.py
blob: 243d013eb4b86a33c07915ee1f26984c2f31f265
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/errors.py

**Role.** The two domain-error base classes every module raises through — `DomainNotFoundError` → house-shape 404, `DomainValidationError` → house-shape 400 carrying the exception's own message — so a new domain module inherits both responses without registering a handler.

**Module.** [[backend/app/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `DomainNotFoundError` | class | Target row doesn't exist *for this tenant* |
| `DomainValidationError` | class | A domain-rule violation on a write; the handler surfaces `str(exc)` |

## Behavior

Both are bare `Exception` subclasses with no attributes — all the design is in *where the handlers bind*. [[backend/app/main.py]] registers `@app.exception_handler` on these two **bases**, never on a leaf. That is forced by Starlette, which resolves a handler by walking `type(exc).__mro__` and taking the first registered class it finds: a handler bound to a concrete subclass matches that class and its own subclasses only. Before this file existed the 404 and 400 handlers were bound to `app.boutique`'s own error classes, so the moment `app/catalog/` raised its own same-named errors every one of them came back as an unhandled **500**. Binding to the bases is what makes "raise and it is a correct 400" true for every module.

The corollary is the rule for adding errors: a new domain error that wants the house 400 or 404 subclasses one of these and registers nothing. A new error that wants a *different* status (409, 429, 503) is its own class and **needs its own explicit handler** — there is no error registry in `main.py` that would catch the omission, and an unregistered leaf falls through to a 500. `main.py` currently registers around forty such handlers alongside these two.

`DomainNotFoundError`'s docstring carries a security invariant, not just a definition: another tenant's id must produce the *same* 404 as a nonexistent one. FORCE RLS plus each repository's explicit `tenant_id` predicate make a foreign row genuinely indistinguishable from a missing one, so the 404 is not a decision the service has to remember to make — it is the only outcome available. Distinguishing the two would turn every by-id route into a cross-tenant existence oracle.

## Depends On

Nothing — two class definitions, no imports.

## Depended On By

- [[backend/app/main.py]] — binds the 400 and 404 handlers to these bases
- [[backend/app/auth/staff.py]] — raises both
- [[backend/app/booking/service.py]] · [[backend/app/booking/owner.py]] · [[backend/app/booking/validation.py]]
- [[backend/app/catalog/service.py]] · [[backend/app/catalog/validation.py]]
- [[backend/app/boutique/service.py]] · [[backend/app/boutique/validation.py]]
- [[backend/app/notifications/validation.py]]
- [[backend/app/storefront/validation.py]] — `SlotWindowError` subclasses `DomainValidationError` to reuse the handler
- [[backend/app/booking/owner_router.py]]

## Concepts

- [[Row Level Security]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_storefront_validation.py]] — `SlotWindowError` is caught as a `DomainValidationError`
- [[backend/tests/test_staff_api.py]] · [[backend/tests/test_staff_service.py]] · [[backend/tests/test_staff_management_db.py]]
- [[backend/tests/test_booking_owner_api.py]] · [[backend/tests/test_booking_owner_service.py]]
- [[backend/tests/test_notifications_api.py]] · [[backend/tests/test_notifications_validation.py]]
- [[backend/tests/test_storefront_api.py]] — a foreign-tenant id and a nonexistent id return the same 404

## Notes

`main.py`'s own comment records the subtlety that keeps the staff surface working: `DuplicateEmailError` and friends need explicit handlers, while the staff module's not-found subclasses `DomainNotFoundError` and is served by the base handler here.
