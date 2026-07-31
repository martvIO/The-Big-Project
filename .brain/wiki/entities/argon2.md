---
tags: [backend, auth, security, python]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Argon2

**Purpose.** The staff password hasher. `argon2-cffi>=25.1.0`, declared in
[[backend/pyproject.toml]], wrapped by the four-function module
[[backend/app/auth/passwords.py]]. There is no bcrypt, no passlib and no cost tuning — a bare
`PasswordHasher()` with library defaults.

The module's fourth function is the one that matters: `verify_password_dummy` verifies the
supplied password against a module-level hash of a fixed throwaway string, so the unknown-email
branch in [[backend/app/auth/service.py#login]] spends the same CPU as a real verify. Without it
a 401 would arrive measurably faster for an address that does not exist — see
[[Enumeration Resistance]].

Because the hash is deliberately expensive, both staff-write paths in
[[backend/app/auth/staff.py]] compute it **outside** `tenant_session`, so no pooled connection
(and, on update, no advisory lock) is held across it. The same expense is why
[[backend/app/auth/schemas.py]] caps password length at `MAX_PASSWORD_LENGTH = 4096` — argon2
cost scales with input size, so an unbounded password is a CPU DoS.

**Trap.** `verify_password` returns `False` only for `VerifyMismatchError`. Any other
`argon2.exceptions` error — notably a malformed or non-argon2 `password_hash` — propagates as a
500 rather than a clean 401.

## Related

- [[Owner Authentication]] · [[Enumeration Resistance]] · [[Audit Trail]]
