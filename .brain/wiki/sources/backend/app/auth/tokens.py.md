---
tags: [backend, auth, python, tokens, session, security, hashing]
sources: [backend/app/auth/tokens.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/auth/tokens.py
blob: 2d54ee07b4f97f2569c12f784d44f0cb4fa58bb4
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/auth/tokens.py

**Role.** Mints 256-bit URL-safe session tokens and hashes them with SHA-256, so the database stores only hashes and a dump of `sessions` cannot be replayed as live cookies.

**Module.** [[backend/app/auth/_index]] · **Layer.** auth

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `TOKEN_BYTES` | const | `32` — 256 bits of entropy per token |
| `generate_session_token` | fn | `secrets.token_urlsafe(TOKEN_BYTES)` — CSPRNG, cookie- and URL-safe |
| `hash_token` | fn | Hex SHA-256 of the token's UTF-8 bytes |

## Behavior

Three lines with one deliberate cryptographic choice behind them: a **fast** one-way hash is correct here precisely because the input is not a password. Session tokens are full-entropy random values, so there is no dictionary to grind and no reason to pay argon2's cost on every authenticated request — which would be once per `resolve_session`, i.e. once per `/manage` call. That is the exact inverse of the reasoning in [[backend/app/auth/passwords.py]], and the two files exist separately so neither reasoning leaks into the other. `secrets.token_urlsafe` is used rather than `uuid4` because a UUID carries only 122 bits and a version/variant structure; `token_urlsafe` output needs no encoding to survive a cookie value or a URL path segment. Neither function performs I/O or holds state, so both are safe to call anywhere. The plaintext token exists only in the HTTP response and the client's cookie — nothing in this repo writes it to a log or a row.

## Depends On

- Python stdlib `secrets`, `hashlib` — no project imports

## Depended On By

- [[backend/app/auth/service.py]] — mints on login, hashes for session lookup, revoke and logout
- [[backend/app/auth/staff_router.py]] — hashes the acting cookie so a self password reset does not sign the actor out
- [[backend/app/booking/tokens.py]] — reuses both helpers for the customer's `/b/{token}` manage link
- [[backend/app/notifications/service.py]] — reuses both for OTP-related token material

## Concepts

- [[Owner Authentication]]
- [[Opaque Token Hashing]]

## Tests

- [[backend/tests/test_auth_integration.py]] — round-trips a real login token through the DB
- [[backend/tests/test_booking_service.py]] · [[backend/tests/test_booking_comms_db.py]] · [[backend/tests/test_booking_owner_db.py]] — use `hash_token` to look up rows the code wrote

## Notes

Because [[backend/app/booking/tokens.py]] shares these primitives, the same 256-bit ceiling is what stands behind the public `/b/{token}` booking-manage URL — that token's entropy, not its rate limit, is the real control there (see [[backend/app/booking/manage.py]]).

Design context: [[.planning/specs/owner-auth.md]].
