---
tags: [backend, api, frontend, catalog, boutique, pydantic]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Full Replace Update Semantics

**What it is.** The house rule for every entity update endpoint: the request model declares **every
field as required with no default**, so an omitted key is a `422`, never a silent clear. The verb
on the wire is still `PATCH`; the semantics are `PUT`.

## The bug it exists to prevent

A nullable scalar with `default=None` cannot distinguish "the client did not send `price_agorot`"
from "the client set `price_agorot` to null". Under a partial-update reading, forgetting a field
wipes it. So `UpdateDressRequest` in [[backend/app/catalog/schemas.py]] and
`UpdateAppointmentTypeRequest` in [[backend/app/boutique/schemas.py]] both write

```python
description: str | None = Field(max_length=...)   # required, NO default
price_agorot: int | None = Field(ge=1, le=...)    # required, NO default
```

and both carry the same docstring. The catalog one adds the trap explicitly: copying
`CreateDressRequest`'s `default=None` into the update model *reintroduces exactly the bug the
full-replace rule exists to prevent*. The create models keep their defaults — that asymmetry is
intentional and is the thing most likely to be "tidied up" by mistake.

The frontend is the other half of the contract: `updateDress` in
[[frontend/apps/manage/src/api.ts]] sends every field on every save, with the rationale in a
comment above it.

## Collection replaces work the same way

`PUT /manage/dresses/{id}/variants` replaces the whole size matrix in one write —
`CatalogService.replace_variants` in [[backend/app/catalog/service.py]] validates first,
soft-deletes the existing set under the `dress-variants:` [[Advisory Lock]], then re-inserts.
`BoutiqueSettingsService.replace_weekly_rules` in [[backend/app/boutique/service.py]] does the same
for opening hours. Both validate *before* opening the transaction, so a rejected replacement leaves
the old set untouched, and both need the lock because two concurrent replaces under READ COMMITTED
would otherwise UNION their sets.

The manage UI mirrors it: [[frontend/apps/manage/src/__tests__/VariantMatrix.test.tsx]] pins
"PUTs the whole matrix as one full replace". A per-row save button would imply per-row persistence
and would make the duplicate-size check — a property of the *set* — impossible to place.

## The one endpoint that is deliberately a merge

`PUT /manage/settings` in [[backend/app/boutique/router.py]] is the exception: it dumps with
`model_dump(exclude_unset=True)` because the underlying `settings || :patch::jsonb` merge replaces
whole top-level keys, so only fields the client actually sent may enter the patch. That merge
protects sibling *top-level* keys and cannot protect fields nested inside one — which is why any
nested settings object added later has to make its own keys required instead.

## Gotchas

- Request models extend `ForbidExtraModel`, so an unknown key is rejected too — full replace does
  not mean "send anything".
- `PATCH` on the wire with `PUT` semantics is intentional and is only visible in the schema. Read
  the request model, not the decorator.
- Tests pin it from both ends: a partial body must be a `400`/`422`
  ([[backend/tests/test_boutique_api.py]], [[backend/tests/test_catalog_api.py]]).

## Related

- [[Advisory Lock]] · [[Partial Unique Index]] · [[Pydantic]]
