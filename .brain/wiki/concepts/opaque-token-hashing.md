---
tags: [backend, security, auth, booking]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Opaque Token Hashing

**What it is.** Every bearer credential this product mints — the staff session cookie and the
customer's booking manage link — is 32 CSPRNG bytes stored as a plain `sha256` hex digest. One
primitive, two consumers: [[backend/app/auth/tokens.py]], reused verbatim by
[[backend/app/booking/tokens.py]] rather than inventing a second scheme.

## A fast hash is the *correct* choice here

This is the inverse of the reasoning in [[backend/app/auth/passwords.py]] one file over, and the
two live side by side on purpose:

| | password | token |
|---|---|---|
| entropy | human-chosen, low | 256 bits, `secrets.token_urlsafe(32)` |
| threat | offline dictionary / rainbow | none available — the space is unguessable |
| algorithm | argon2, deliberately slow | sha256, deliberately fast |

There is nothing to *guess* about a 256-bit random value, so a memory-hard KDF would buy no
security and would charge an argon2 verify on **every authenticated request** — a self-inflicted
DoS on the read path. Only the digest is stored, so a database leak still cannot recover a live
token.

## The redundant comparison in the booking path

`manage_token_matches` ends with `hmac.compare_digest` even though
`BookingsRepository.by_manage_token_hash` already selected on an equality against that same hash.
Its docstring names the reason: if the predicate is ever widened — a prefix match, a `LIKE`, a
join that loses its tenant clause — this comparison is the thing that stops the widened query from
handing back a booking whose token the caller does not hold.

## Related

- [[Owner Authentication]] · [[One Time Passcode]] · [[Enumeration Resistance]]
- [[backend/app/db/repositories/sessions.py]] · [[backend/app/db/repositories/bookings.py]]
- [[backend/tests/test_manage_token.py]] · [[backend/app/booking/comms_templates.py]] — the SMS
  budget arithmetic is written against exactly the 43-character urlsafe length
