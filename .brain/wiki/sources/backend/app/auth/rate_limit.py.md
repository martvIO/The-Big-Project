---
tags: [backend, auth, python, rate-limiting, in-memory, security]
sources: [backend/app/auth/rate_limit.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/auth/rate_limit.py
blob: 1dc67b1b0fd5cff0d4ff87af969b638f03e5e90e
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/auth/rate_limit.py

**Role.** The one in-process fixed-window counter every rate limit in this backend is built from — login, terms creation, media presign, storefront reads, OTP send/verify, booking create, booking lookup and the owner SMS taps all instantiate it. `max_attempts` lives on the **instance**, which is why one budget means one `FixedWindowRateLimiter`.

**Module.** [[backend/app/auth/_index]] · **Layer.** auth

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `FixedWindowRateLimiter` | class | Constructed with `max_attempts`, `window_seconds`, and an injectable `clock` |
| `is_blocked` | method | Read-only pre-check: has this key reached `max_attempts` inside the live window? |
| `record_failure` | method | Increment this key's count, opening a fresh window if the old one expired |
| `reset` | method | Drop a key's bucket entirely (login calls it on success) |
| `_SWEEP_FLOOR` | class const | `1024` — the amortised sweep never triggers below this many keys |

## Behavior

State is a plain `dict[str, tuple[window_start, count]]`; `_current_count` treats a bucket older than `window_seconds` as `(now, 0)` without deleting it, so window rollover is lazy and needs no timer. `record_failure` is the only writer and is also where the sweep is amortised: it fires only when the dict exceeds `_sweep_at`, after which the high-water mark floats to `2 * len(surviving)` (floored at 1024), so a busy instance does not walk the whole dict on every write. `is_blocked` never writes, which is what lets a caller pre-check several keys and then charge only the ones it means to. **The trap worth carrying:** `max_attempts` is per *limiter*, not per *key* — adding a second key namespace to an existing instance silently makes both budgets the same number. [[backend/app/main.py]] therefore constructs a separate instance for every budget, and the OTP send and verify budgets are two instances precisely because they must differ.

The method name `record_failure` is a leftover from the first caller and now misdescribes half of them: [[backend/app/auth/router.py]] records only failed logins (so a shared IP cannot be throttled by another user's typing), [[backend/app/storefront/router.py]] records **successes** (it meters reads, keyed per tenant so the key space is bounded by tenant count rather than visitor count), and [[backend/app/booking/service.py]] records every attempt that got past phone verification — both halves of that being load-bearing, since metering before the proof would let an unauthenticated caller spend a tenant's whole budget with garbage tokens, and metering successes only would let one verification token retry forever because a failed claim rolls its own burn back. The class counts events; each caller decides which events count.

The limiter is per **process**, so with more than one API instance the effective budget multiplies by the instance count. That is accepted for the single-instance pilot and named as the Feature 21 hardening gate (a Redis-backed shared store). The injectable `clock` exists so the suites can advance time instead of sleeping.

## Depends On

Nothing — stdlib only, no I/O.

## Depended On By

- [[backend/app/auth/router.py]] — login: per-`(tenant,email)` always, per-IP only when `trust_forwarded_for`
- [[backend/app/main.py]] — constructs every limiter instance at app build
- [[backend/app/boutique/service.py]] — terms-version creation throttle
- [[backend/app/catalog/service.py]] — media presign throttle
- [[backend/app/storefront/router.py]] — anonymous storefront read budget (records on success)
- [[backend/app/notifications/service.py]] — OTP send (per phone, per tenant) and verify budgets
- [[backend/app/booking/service.py]] — booking-create budgets
- [[backend/app/booking/manage.py]] — the F16 `/b/{token}` anti-scrape budget
- [[backend/app/booking/owner.py]] — the F15 owner-SMS runaway brake

## Concepts

- [[Rate Limiting]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_rate_limit.py]] — window rollover, blocking at the cap, `reset`, and the amortised sweep
- [[backend/tests/test_auth_api.py]] — the login budget end to end, including that success clears the key
- [[backend/tests/test_notifications_service.py]] · [[backend/tests/test_booking_service.py]] · [[backend/tests/test_storefront_api.py]] — the non-login callers

## Notes

`is_blocked` + `record_failure` is a read-then-write with no lock. Under concurrent requests two callers can both read "not blocked" and both charge, so the cap is approximately, not exactly, `max_attempts` — irrelevant at these budget sizes and gone once F21 moves the store.

Every window value and cap is a field on [[backend/app/core/config.py]]; nothing here is hardcoded but the sweep floor.
