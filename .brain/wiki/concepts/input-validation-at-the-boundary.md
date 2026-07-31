---
tags: [backend, frontend, validation, security, design]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Input Validation At The Boundary

**What it is.** Four layers, each answering a different question, with one number written once and
mirrored outward. The layering is why a bad request is a clean Hebrew message rather than a 500.

| Layer | Answers | Lives in |
|---|---|---|
| Pydantic request model | is the *shape* legal? | `*/schemas.py` |
| `validation.py` | is the *value* within product policy? | `app/<module>/validation.py` |
| DB `CHECK` | is it absurd? | the migration that created the column |
| `validation.ts` | can the user be told before a round trip? | the two frontend apps |

## Unknown keys are a 400, not a silent drop

Every request model inherits `ForbidExtraModel` ([[backend/app/schemas.py]]) — `extra="forbid"`.
Its docstring names the payoff: that is what makes *"no client-supplied value can reach an S3
key"* an assertion rather than a hope ([[backend/app/catalog/keys.py]]).

## The validation modules are pure

[[backend/app/catalog/validation.py]], [[backend/app/booking/validation.py]],
[[backend/app/boutique/validation.py]] and [[backend/app/notifications/validation.py]] do no I/O and
carry no `Settings`. Each numeric bound names its DB counterpart directly beneath it. The split
between 400 and 409/404 is explicit: shape questions are answerable from the request alone (400);
"does this dress exist", "is this size active", "is the slot real" need the database and belong to
the service.

## The DB CHECKs are absurdity ceilings, not the policy

Migration `0006`'s constraints sit at exactly **10×** the product caps — INT4 headroom, so
tightening product policy never needs a migration. One deliberate exception: `byte_size` is 2×,
because that value is also a security bound the presigned POST policy enforces.

## The frontend mirror, and the guard that keeps it honest

Two files restate backend bounds so the user sees an immediate Hebrew error:
[[frontend/apps/manage/src/validation.ts]] mirrors the catalog and staff bounds,
[[frontend/apps/storefront/src/validation.ts]] mirrors the booking ones.
[[backend/tests/test_frontend_constant_parity.py]] reads them as **text** (so it runs in the fast,
no-Node suite) and re-asserts every constant against the Python.

## The trap

**A cap raised on one side only is silent.** Raise it on the server and the client rejects a legal
value; raise it on the client and an illegal one reaches the API before it refuses. Worse in the
catalog: raise `MAX_UPLOAD_BYTES` in one place and the confirm step turns a clean 400 into an
`IntegrityError` 500 against the untouched `CHECK`. Never edit a bound without grepping for its
name across `backend/app`, `frontend/apps/*/src` and `backend/migrations/versions`.

## Related

- [[Product Policy Vs Deployment Identity]] — why none of these numbers are env-tunable
- [[Stored XSS Prevention]] · [[Public Wire Schemas]] · [[Fail Closed Defaults]]
- [[backend/app/auth/schemas.py]] — `DisplayName` strips *before* the bounds, because
  `min_length=1` alone admits `"   "`
