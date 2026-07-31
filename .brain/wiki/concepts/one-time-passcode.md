---
tags: [backend, security, sms, booking]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# One Time Passcode

**What it is.** The customer identity realm. A bride never gets a password — she proves possession
of an Israeli mobile with a six-digit SMS code, and that proof becomes a short-lived verification
token the booking transaction consumes.

## The policy, and where it lives

All of it is in [[backend/app/notifications/validation.py]], not in `Settings`
(see [[Product Policy Vs Deployment Identity]]): six digits from `secrets.randbelow`, 300-second
TTL, five row-tracked verify attempts, and a 600-second verification token — long enough to finish
the booking form, short enough that an abandoned token dies before the slot picker goes stale.

One live code per `(tenant, phone)`: a resend soft-deletes its predecessor
([[backend/app/models/otp_code.py]]). That model's docstring is blunt about the security argument —
**`code_hash` is hygiene, not a boundary.** The attempt cap and the expiry are what make 10⁶ codes
safe; hashing a six-digit number stops nothing.

## Send and verify are throttled separately

The per-code attempt cap burns *one* code. Without an independent verify budget an attacker simply
requests a fresh code and keeps guessing, and each attempt is an unauthenticated `SELECT` plus a
locking `UPDATE` ([[backend/app/core/config.py]]). Both budgets are checked *after* normalization,
so every spelling of a number shares one bucket.

## The code must never reach a log

`message_log` is a forever-table and the code is worthless in five minutes, so `mask_otp_body`
replaces the digits with `●` before the row is written. [[backend/app/notifications/fake.py]]
follows the same rule the other direction: it deliberately does **not** log the body, because
staging runs that adapter on a publicly reachable host with a widely readable log stream. Provider
exception text is truncated and masked too — several SMS SDKs echo the failing request, body
included.

## The staging escape hatches are boot failures in production

`sms_provider="fake"` sends nothing and `otp_dev_code` bypasses the comparison entirely. Either
one in production silently voids the phone verification the whole booking flow rests on, so
`Settings` refuses to construct — see [[Fail Fast Configuration]].

## Phone shape is a gate, not a formality

`normalize_israeli_mobile` accepts the ways a human types a number and returns E.164, rejecting
landlines and foreign numbers outright. Storing an unreachable phone strands the customer behind
an SMS link that can never arrive, and a wrong-country send is pure cost.

## Related

- [[Enumeration Resistance]] — a spent per-phone send budget answers `204`, not `429`
- [[Opaque Token Hashing]] · [[Graceful Degradation]] · [[Ports And Adapters]]
- [[backend/app/notifications/service.py]] · [[backend/migrations/versions/0007_sms_foundation.py]]
- [[backend/tests/test_notifications_service.py]] · [[backend/tests/test_notifications_validation.py]]
