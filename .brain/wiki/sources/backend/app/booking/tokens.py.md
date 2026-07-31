---
tags: [backend, booking, python, security, tokens, hashing]
sources: [backend/app/booking/tokens.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/tokens.py
blob: 4efe1916ab8bc691fb8beb262236fa52f1a3c97c
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/tokens.py

**Role.** Mint, hash and constant-time-compare the manage-link credential — the secret in `/b/{token}` that lets an anonymous bride read, confirm attendance on and cancel her own booking, stored on `bookings.manage_token_hash` as sha256 only.

**Module.** [[backend/app/booking/_index]] · **Layer.** auth

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `mint_manage_token` | fn | A fresh raw token — delegates to `generate_session_token` (32 random bytes, 43 urlsafe characters) |
| `manage_token_hash` | fn | sha256 of the raw token — what is stored |
| `manage_token_matches` | fn | `hmac.compare_digest` of the recomputed hash against the stored one; `False` when the stored hash is `None` |

## Behavior

Three thin wrappers over [[backend/app/auth/tokens.py]] rather than a second token scheme — the reuse is the design decision, and the 43-character length it fixes is what the SMS segment arithmetic in [[backend/app/booking/comms_templates.py]] is written against. The raw token exists only in flight: it is minted inside the claim transaction, its hash committed with the row it authorises, and the raw value then survives only in an SMS body and, while a reminder is still pending, on the `scheduled_messages` row. Because sha256 is one-way, that is why every rotation path must carry the raw value out on its result object rather than re-read it later.

`manage_token_matches` is **deliberately redundant** and the docstring is explicit about why. `BookingsRepository.by_manage_token_hash` already selects on an equality against this same hash, so any returned row has matched — the point is that if that predicate is ever widened (a prefix match, a `LIKE`, a join that loses its tenant clause), this comparison is the thing that still refuses to hand back a booking whose token the caller does not hold. `compare_digest` rather than `==` because both sides are attacker-influenced hex and length-dependent comparison on a credential is a habit worth not having. The `None` guard matters operationally too: a booking whose link was never issued, or whose hash was cleared, fails closed instead of matching a `None`.

## Depends On

- [[backend/app/auth/tokens.py]] — `generate_session_token`, `hash_token`

## Depended On By

- [[backend/app/booking/service.py]] — mints and hashes on the claim's INSERT
- [[backend/app/booking/manage.py]] — hashes the incoming token for lookup and re-checks with `manage_token_matches`
- [[backend/app/booking/comms.py]] — rotation in `reissue_manage_token`, `upsert_reminder` and `_rotate`
- [[backend/app/booking/owner.py]] — `_rotate_links`, the phone-correction and resend paths
- [[backend/app/booking/backfill.py]] — mints for pre-F16 bookings

## Concepts

- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_manage_token.py]] — mint uniqueness, hash stability, and the constant-time compare including the `None` case
- [[backend/tests/test_booking_comms_db.py]] — the token through a real rotation and send
- [[backend/tests/test_booking_owner_db.py]] — rotation under the owner console's transactions

## Notes

The token space is 256 bits, which is the real control on `/b/{token}`; the per-tenant lookup budget in [[backend/app/booking/manage.py]] is only the anti-scrape floor beneath it.

Design context: [[.planning/specs/booking-comms.md]].
