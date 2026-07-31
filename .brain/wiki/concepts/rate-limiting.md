---
tags: [backend, security, auth, booking, catalog, config]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Rate Limiting

**What it is.** `FixedWindowRateLimiter` in [[backend/app/auth/rate_limit.py]] — an in-process
dict of `key -> (window_start, count)` with an injectable clock. Every budget in the product is one
instance of it, constructed in [[backend/app/main.py]] from a pair of
`*_max_per_window` / `*_window_seconds` fields in [[backend/app/core/config.py]].

Single-instance only. Distributed limiting (Redis) is deferred to the Feature 21 hardening gate,
and the class docstring says so.

## The house trap: `max_attempts` lives on the LIMITER, not on the key

Two keys on one instance share one ceiling. That is why every budget gets **its own instance**, and
why both [[backend/app/main.py]] and [[backend/app/booking/service.py]] carry the same comment where
the booking service takes a `create_limiter` *and* a `phone_limiter`: sharing would give the
per-phone budget the tenant's ceiling, so the per-phone budget could never trip first and would be
pure decoration.

If you find yourself adding a second key prefix to an existing limiter, you are adding a budget that
cannot fire. The one legitimate exception is login in [[backend/app/auth/router.py]], which puts
two keys — `t:{tenant}:e:{email}` and `ip:{ip}` — on one instance *because they are meant to share
one ceiling*: both are brute-force controls of the same size, the per-IP one is only added when a
client IP can be trusted, and only the email key is `reset()` on success.

## The second trap: it counts only what a caller records

`record_failure` is the odd name out — the class counts *events*, and each caller decides which
events are worth counting. There is no automatic metering anywhere.

| Caller | Records |
|---|---|
| login ([[backend/app/auth/router.py]]) | failed attempts only, so a shared IP cannot throttle an honest owner; a success `reset()`s the email key |
| storefront reads ([[backend/app/storefront/router.py]], as a router-level dependency) | **successes**, keyed per tenant so the key space is bounded by tenant count, not visitor count |
| OTP send / verify ([[backend/app/notifications/service.py]]) | every send and every verify attempt |
| booking lookup ([[backend/app/booking/manage.py]]) | every lookup |
| terms creation ([[backend/app/boutique/service.py]]) | every successful creation — rows on an [[Append Only Terms Versions]] path are permanent, so spam is permanent bloat |
| media presign ([[backend/app/catalog/service.py]]) | **both** the rejected path and the success path, by hand |
| booking create ([[backend/app/booking/service.py]]) | every attempt that got past phone verification, success or not |

The presign call site spells out the failure mode: deleting the success-path `record_failure`
because it reads like a bug is how the throttle dies.

## Check before, spend after the proof

[[backend/app/booking/service.py]] checks both budgets *before* opening the transaction and spends
them only once the OTP token is proven. Metering an unproven caller inverts the security property —
the cheapest way to close a boutique for an hour becomes 60 requests carrying nothing but a
hostname. Because the limiter is in-memory it survives the rollback of a failed claim by design: one
verified phone gets a bounded number of attempts, not unlimited ones off a token that keeps
un-burning itself.

The same "consulted before the transaction opens" rule is stated for the owner-side SMS budget in
[[backend/app/booking/owner.py]], so a 429 writes nothing and sends nothing.

## The budgets that exist

Login; storefront reads (per tenant, 6000/60 s); terms creation; media presign; OTP send
(per phone *and* per tenant, two instances); OTP verify; booking create (per phone *and* per tenant,
two instances); booking lookup; owner SMS. All of them are `Settings` fields, so a pilot can be
retuned without a code change.

Each budget raises its **own** exception class with its **own** handler in
[[backend/app/main.py]] — `RateLimitedError`, `TermsThrottledError`, `MediaPresignThrottledError`,
`StorefrontThrottledError`, `OtpThrottledError`, `BookingThrottledError`,
`OwnerResendThrottledError` — and every one of them returns the same `TOO_MANY_ATTEMPTS_BODY` at
429. The duplication is deliberate and commented: these budgets have unrelated keys and unrelated
operational meanings, so reparenting them onto one base is deferred to F21. The response never says
which budget tripped.

## Gotchas

- The memory sweep is amortised, not per-write: the high-water mark floats to 2× the surviving set,
  starting at 1024. A caller with an unbounded key space is still a leak between sweeps — bound the
  key space instead (the storefront's per-tenant key is the precedent).
- The clock is `time.monotonic` in production and injected in tests
  ([[backend/tests/test_rate_limit.py]]) — never `datetime.now()`.
- Shared limiter instances also share state across tests. One budget, one instance.

## Related

- [[Fail Fast Configuration]] · [[Media Upload Pipeline]] · [[Append Only Terms Versions]]
