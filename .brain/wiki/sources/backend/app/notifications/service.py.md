---
tags: [backend, notifications, otp, sms, python, service, rate-limiting, security, tenancy]
sources: [backend/app/notifications/service.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/notifications/service.py
blob: 919a5c0f5b080912b959ebffea8fd4310728554b
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/notifications/service.py

**Role.** Two services stacked on the SMS port: `NotificationService.send_sms` is the **single writer of `message_log`** for the entire application (insert `queued` → call the adapter → mark `sent`/`failed`), and `OtpService` owns the code lifecycle on top of it — mint, hash, store, throttle, verify under an attempt cap, and mint the `verification_token` the booking epic treats as proof of phone possession.

**Module.** [[backend/app/notifications/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `NotificationService` | class | `is_configured`, `send_sms(tenant_id, *, phone, body, kind, booking_id=None, log_body=None) -> MessageLog` |
| `NotificationService._scrub` | method | Truncates provider exception text and replaces any echo of the wire body with `log_body` |
| `NotificationService._mark` | method | Second short transaction that writes the terminal status |
| `OtpService` | class | `send`, `verify`, `consume_verification` |
| `VerifyResult` | frozen dataclass | `verification_token`, `expires_at` |
| `OtpInvalidError` | exception | Wrong code, no live code, or cap exceeded — one indistinguishable error |
| `OtpExpiredError` | exception | Distinguished from invalid deliberately |
| `OtpThrottledError` | exception | Tenant send budget or verify budget exhausted → 429 |
| `WallClock` | type alias | `Callable[[], datetime]`, injectable for expiry tests |
| `MAX_PROVIDER_ERROR_LENGTH` | const | `200` |
| `_ABSENT_ROW_HASH` | const | `"0" * 64` — compared against when no live code exists so the miss costs the same hash |

## Behavior

**`send_sms` opens two separate `tenant_session`s and can never be atomic with a caller's write.** That is the design, not a limitation: `tenant_session` is `session.begin()`, so holding one open across an adapter call would let a hanging provider pin a DB transaction, and — more importantly — a *failed* send must leave its evidence row behind rather than roll it away. The first transaction inserts a `queued` row; the adapter is called with the transaction closed; a second transaction marks `sent` with the provider message id, or `failed` with a scrubbed reason. Before any of that, `is_configured` is checked and `SmsNotConfiguredError` is raised **pre-insert**, which is what makes the unconfigured deployment evidence-free while a configured-but-broken provider is not — an F11 ruling [[backend/app/booking/comms.py]] and [[backend/app/booking/owner.py]] both depend on. `log_body` exists for callers that must not retain the wire body verbatim; only the caller knows the code, so only the caller can mask it.

**`_scrub` is the reason a provider exception cannot poison the forever-table.** Several SMS SDKs echo the failing request — body included — in their exception text, which would write the very code `mask_otp_body` exists to keep out of `message_log`. `_scrub` truncates to `MAX_PROVIDER_ERROR_LENGTH` and then replaces any occurrence of `body` with `log_body`, so the mask survives into the error column too. The provider's text never reaches the HTTP caller at all: `SmsSendError` is raised bare, same containment as the media port.

**`OtpService.send` throttles after normalization and answers its two exhaustions differently.** Normalizing first means every spelling of a number shares one bucket. A tripped **tenant** ceiling raises `OtpThrottledError` (429) — an operational fact about the boutique. A tripped **phone** budget returns `None` silently, sending nothing, because a 429 there would turn the endpoint into an oracle for "is this number mid-booking at this boutique", on a surface whose entire posture is that known and unknown phones are indistinguishable. Both budgets are recorded on the *attempt*, not on success — the metered resource is the send itself. Then: soft-delete any active code for the phone (one live code per phone, so a resend invalidates its predecessor rather than racing it), insert the new hashed code with `now + OTP_TTL_SECONDS`, commit, and only then call `send_sms`. That order is deliberate — a provider failure leaves an orphan row that the next resend invalidates, whereas the reverse order would send an SMS whose code was never stored.

**`OtpService.verify` decides inside the transaction and raises outside it, and this shape is the whole security of the attempt cap.** Because `tenant_session` is a transaction, a `raise` inside the block would roll back the `attempts = attempts + 1` write along with it: every failed guess would undo its own increment, `attempts` would sit at 0 forever, and 10^6 unlimited guesses inside the 5-minute TTL would be a phone takeover. So failures are captured in a local and re-raised after the block closes. Within the block: a missing row still performs one hash comparison against `_ABSENT_ROW_HASH` so "no live code for this phone" is not readable off response time; an already-locked row stops *writing* rather than merely answering, because the column's `CHECK (attempts <= 50)` is a defensive ceiling that must stay unreachable or it becomes an `IntegrityError` 500 on an anonymous endpoint; otherwise the increment happens **before** the comparison, so a crash between compare and record cannot grant a free guess. Expiry is checked after the increment. Success mints a session-grade token via `generate_session_token`, stores only `hash_token(token)` with `VERIFICATION_TOKEN_TTL_SECONDS`, and a raced double-verify that loses the guarded UPDATE returns the same `OtpInvalidError` as a wrong code.

**`consume_verification` takes a caller-supplied `AsyncSession` instead of opening its own** — the one method here that does. F13 calls it inside the booking transaction so the customer INSERT and the token burn commit or roll back together; a booking that fails to claim its slot must give the token back.

`_matches` hashes both sides before `hmac.compare_digest`, including the optional `dev_code`: `compare_digest` raises `TypeError` on non-ASCII and `code` is attacker-supplied, so comparing raw strings would turn a Hebrew digit into a 500 instead of a clean miss. `WallClock` is kept distinct from the monotonic clocks the rate limiters take — expiry is calendar time, windows are elapsed time.

## Depends On

- [[backend/app/notifications/base.py]] — `SmsSender`, both error types
- [[backend/app/notifications/validation.py]] — every OTP constant and helper
- [[backend/app/db/repositories/message_log.py]] — `insert`, `update_status`
- [[backend/app/db/repositories/otp_codes.py]] — `soft_delete_active_for_phone`, `insert`, `latest_active_by_phone`, `increment_attempts`, `mark_consumed`, `consume_verification`
- [[backend/app/db/tenant.py]] — `tenant_session`
- [[backend/app/auth/rate_limit.py]] — `FixedWindowRateLimiter` (three separate instances)
- [[backend/app/auth/tokens.py]] — `generate_session_token`, `hash_token`
- [[backend/app/models/constants.py]] — `MessageKind`, `MessageStatus`
- [[backend/app/models/message_log.py]] — return type
- [[SQLAlchemy]] — `async_sessionmaker`

## Depended On By

- [[backend/app/main.py]] — constructs both services and all three limiters from [[backend/app/core/config.py]]; registers handlers for the three OTP errors
- [[backend/app/notifications/router.py]] — the public OTP endpoints
- [[backend/app/booking/service.py]] — calls `consume_verification` inside the booking transaction
- [[backend/app/booking/comms.py]] — every booking SMS goes through `send_sms`
- [[backend/app/worker.py]] — builds its own `NotificationService` for the reminder drain

## Concepts

- [[One Time Passcode]]
- [[Rate Limiting]]
- [[Row Level Security]]
- [[Audit Trail]]

## Tests

- [[backend/tests/test_notifications_service.py]] — the lifecycle suite: `test_full_otp_lifecycle_send_verify_consume`, `test_message_log_masks_the_otp_code`, `test_verify_is_single_use`, `test_verify_expires_at_ttl`, `test_attempt_cap_burns_the_code`, `test_failed_guesses_persist_their_attempt_increment` (the rollback trap), `test_attempts_stop_climbing_once_locked`, `test_verify_is_rate_limited`, `test_send_throttles_per_tenant_with_429`, `test_exhausted_phone_budget_stays_silent`, `test_non_ascii_code_is_a_clean_miss_not_a_crash`, `test_unconfigured_sender_writes_nothing`, `test_resend_invalidates_the_previous_code`, `test_send_throttles_per_phone`, `test_dev_code_is_accepted_when_configured`, `test_dev_code_requires_a_live_send`, `test_provider_explosion_is_contained`, `test_provider_error_never_persists_the_live_code`
- [[backend/tests/test_notifications_api.py]] — HTTP contract and the error table
- [[backend/tests/test_notifications_isolation.py]] — a foreign tenant can neither read nor consume another's `otp_codes`

## Notes

**One rate-limit budget = one `FixedWindowRateLimiter` instance.** `max_attempts` lives on the limiter, not on the key, so the three budgets here (send-per-phone, send-per-tenant, verify-per-phone) are three separate objects built in [[backend/app/main.py]]. Reusing one instance for two budgets silently merges their ceilings.

`_dev_code` is the staging escape hatch; [[backend/app/core/config.py]]'s `_forbid_sms_test_paths_in_production` makes a non-`None` value a boot failure in production. Note `test_dev_code_requires_a_live_send` — the dev code still needs a live `otp_codes` row, so it bypasses the comparison but not the lifecycle.
