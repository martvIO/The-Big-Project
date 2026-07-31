---
tags: [backend, python, schemas, api, pydantic, validation]
sources: [backend/app/schemas.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/schemas.py
blob: 54c959067c8df37346d30fe3bffe9e037aa85b93
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/schemas.py

**Role.** Two wire primitives shared by every API module: `ForbidExtraModel`, the base every **request** model inherits so an unknown key is a 400 rather than a silently dropped field, and `OkResponse`, the single `{"ok": true}` body for mutations with nothing to return.

**Module.** [[backend/app/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `ForbidExtraModel` | class | `BaseModel` with `model_config = ConfigDict(extra="forbid")` |
| `OkResponse` | class | `ok: bool = True` |

## Behavior

`extra="forbid"` turns an unrecognized key into a Pydantic `ValidationError`, which [[backend/app/main.py]]'s `RequestValidationError` handler renders as the house-shape 400. The reason it is a *base class* rather than a per-model config is stated in the docstring and is worth carrying: it is what makes "no client-supplied value can reach an S3 key" an assertion instead of a hope — with `extra="ignore"`, a request carrying `{"key": "../other-tenant/…"}` would parse cleanly and the guarantee would rest on every future model remembering to omit the field. Forbidding extras also catches the frontend/backend name drift (a renamed field) at the first request rather than as a silently-ignored update.

Both classes started in `app/boutique/schemas.py` and moved here when `app/catalog/` needed them: a second domain module importing a *boutique* schema would point the dependency arrow sideways between peers, and F10's generated client would have emitted two distinct `{"ok": true}` types. The move was made non-breaking by re-exporting both from [[backend/app/boutique/schemas.py]] under `X as X` (the explicit re-export form mypy requires), so no wire shape changed and no import had to be rewritten in the same commit.

Note the asymmetry: **request** models inherit `ForbidExtraModel`; **response** models are plain `BaseModel`s (see `HealthResponse` in [[backend/app/api/routes/health.py]]), because forbidding extras on an outbound model constrains nothing a client sends.

## Depends On

- [[Pydantic]] — `BaseModel`, `ConfigDict`

## Depended On By

- [[backend/app/boutique/schemas.py]] — re-exports both, for backward compatibility
- [[backend/app/auth/schemas.py]] · [[backend/app/booking/schemas.py]] · [[backend/app/catalog/schemas.py]] — request bases
- [[backend/app/auth/staff_router.py]] · [[backend/app/catalog/router.py]] — `OkResponse`

## Concepts

- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_boutique_api.py]] — `test_malformed_auth_login_body_is_house_shape_400` and the unknown-key cases
- [[backend/tests/test_catalog_api.py]] — `test_unknown_key_in_any_catalog_body_is_a_400`
- [[backend/tests/test_booking_owner_api.py]] — `test_an_unknown_body_key_is_a_house_shape_400`, parameterized over every owner route
- [[backend/tests/test_booking_owner_service.py]] — `test_request_models_reject_an_unknown_key`

## Notes

`app/storefront/schemas.py` holds the public projections and does not inherit `ForbidExtraModel` for its response models — correct, since the storefront takes no request bodies.
