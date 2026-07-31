---
tags: [backend, security, api, design]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Enumeration Resistance

**What it is.** The house rule that a failure body describes *what happened to the caller*, never
*why*. One body per outcome class, shared by every cause inside it — because naming the cause
leaks the shape of the boutique's data to an anonymous prober.

## The classes

Every body below is a module-level constant in [[backend/app/main.py]], bound to a handler.

| Body | Covers |
|---|---|
| `404 TENANT_NOT_FOUND` | unknown slug, suspended, deleted, reserved, apex — [[backend/app/tenancy/middleware.py]] |
| `401 INVALID_CREDENTIALS` | wrong password **and** unknown email |
| `403 NOT_AUTHORIZED` | every role that is not admitted; never names a role |
| `404 NOT_FOUND` | unknown id, archived row, **and another tenant's id** — [[backend/app/errors.py#DomainNotFoundError]] |
| `409 SLOT_UNAVAILABLE` | full, off-grid, past, or a closed day — [[backend/app/booking/service.py#SlotUnavailableError]] |
| `400 OTP_INVALID` | wrong code, no live code, attempt cap spent — [[backend/app/notifications/service.py]] |

## Timing is part of the body

A generic body that arrives faster for an unknown account is still an oracle. So the unknown-email
login path verifies against a precomputed dummy hash ([[backend/app/auth/passwords.py]]), and the
OTP verify path compares against `_ABSENT_ROW_HASH` when no live code exists, purely so the miss
costs the same hash as a real wrong guess.

## Where the omission is structural, not textual

- **Full slots are dropped from the grid, never marked.** [[backend/app/booking/slots.py]] emits
  only slots with `taken < capacity`; a response that enumerated full ones would disclose the
  boutique's booking density.
- **`by_id_any_state` may never appear in the storefront module** — [[backend/app/storefront/service.py]]
  says so in its docstring and a test greps for the symbol, so an archived dress is
  indistinguishable from one that never existed.
- **Cross-tenant rows are invisible before the predicate runs.** [[Row Level Security]] is what
  makes "another tenant's id" and "no such id" the same 404 rather than two code paths that must
  agree.

## The two deliberate distinctions

Not everything is collapsed, and the exceptions are reasoned:

- **`OTP_EXPIRED` is split from `OTP_INVALID`.** "Request a new code" is real UX, and expiry
  reveals nothing the attacker doesn't already know from their own send time.
- **A tripped per-phone OTP budget answers `204`, not `429`.** A 429 here would turn the send
  endpoint into an oracle for "is this number mid-booking at this boutique". A tripped *tenant*
  ceiling is an operational fact about the boutique, so that one does 429
  ([[backend/app/notifications/service.py]]).

## Related

- [[Fail Closed Defaults]] · [[Tenant Resolution]] · [[Public Wire Schemas]]
- [[backend/app/catalog/service.py]] · [[backend/app/auth/staff.py]] · [[backend/app/booking/owner.py]]
- [[.planning/security-checklist-v1.md]]
