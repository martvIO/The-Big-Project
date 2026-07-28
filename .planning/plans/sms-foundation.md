# Plan: Feature 11 — SMS Foundation (Epic E3)

**Spec**: `.planning/specs/sms-foundation.md` · **Branch**: `feature/sms-foundation` · **Created**: 2026-07-28

TDD throughout: each task lands its failing tests first, then the code that greens them. Local gate per task: `make lint` + `make test` (db-marked tests are written locally, executed in CI).

## Task 1 — Validation primitives (fast tests)
`Backend/app/notifications/validation.py` + `tests/test_notifications_validation.py`
- `normalize_israeli_mobile` table test: `050-123-4567` → `+972501234567`, `+972 50 123 4567`, `9720501…` reject, landline `03…` reject, junk charset reject.
- Constants: `OTP_CODE_LENGTH`, `OTP_TTL_SECONDS`, `OTP_MAX_VERIFY_ATTEMPTS`, `VERIFICATION_TOKEN_TTL_SECONDS`.
- `generate_otp_code()` (zero-padded, `secrets`), `mask_otp_body()`.

## Task 2 — Port + adapters (fast tests)
`Backend/app/notifications/base.py`, `fake.py`, `unconfigured.py` + `tests/test_notifications_adapters.py`
- Protocol `SmsSender`, `SendResult`, `SmsNotConfiguredError`, `SmsSendError`.
- Fake outbox capture; unconfigured raises.

## Task 3 — Migration 0007 + models + repos (db tests)
`Backend/migrations/versions/0007_sms_foundation.py`, `app/models/{message_log,otp_code}.py`, `app/db/repositories/{message_log,otp_codes}.py` + `tests/test_notifications_repositories.py`, additions to `tests/test_rls_isolation`-style file (`test_notifications_isolation.py`)
- Mirror 0005 pattern exactly (`_STANDARD`, trigger, grants, RLS loop). Downgrade drops both.
- Repos: `MessageLogRepository.insert/update_status`, `OtpCodesRepository.insert/latest_active_by_phone/soft_delete_active_for_phone/increment_attempts/mark_consumed/set_verification/consume_verification`.
- Isolation tests use `app_role_url` (superuser bypasses RLS — vacuous otherwise).
- `test_migrations` up/down round-trip picks up 0007 automatically — verify locally by reading, in CI by execution.

## Task 4 — NotificationService + OtpService (db tests)
`Backend/app/notifications/service.py` + `tests/test_notifications_service.py`
- `NotificationService.send_sms`: message_log queued → adapter → sent/failed; two `tenant_session` phases (no transaction held across provider I/O); OTP body masked in log.
- `OtpService`: send (invalidate-predecessor, limiters, store hash, delegate send), verify (attempts-before-compare, `compare_digest`, expiry split, token mint via `app/auth/tokens.py`), `consume_verification(session, …)` session-taking for F13's transaction.
- Injected `clock` (wall, `time.time`-compatible) for expiry; injected limiters.
- Dev-code path: `otp_dev_code` accepted when set; full send path still runs.

## Task 5 — Router + schemas + wiring (db/API tests)
`app/notifications/router.py`, `schemas.py`; `app/main.py` (state wiring, error handlers, router registration); `app/core/config.py` (settings + validators) + `tests/test_notifications_api.py`, route-table additions in `tests/test_storefront_api.py`
- `POST /storefront/otp/send` 204, `POST /storefront/otp/verify` 200 token.
- Error handler registrations: `SMS_NOT_CONFIGURED` 503, `SMS_UNAVAILABLE` 503, `OTP_INVALID` 400, `OTP_EXPIRED` 400, `OtpThrottledError` → existing `TOO_MANY_ATTEMPTS` 429.
- Settings validators: production forbids `sms_provider="fake"` and `otp_dev_code` (config unit tests, fast).
- Cookie-blindness + no-store + auth-guard-reverse route-table entries.

## Task 6 — Review + ship
- `make lint && make test` clean; read-through of db-marked tests.
- Dual review: phase-reviewer (quality) + adversarial security agent (OTP brute force, enumeration, log leakage, RLS). One fix commit per round.
- Update epic table row (F11 → building → done), external-applications row 4 note (recommendation approved → user files).
- PR `Feature 11: SMS foundation — NotificationService port, message_log, OTP primitive (Epic E3)`; watch `gh pr checks`; expect one db-test fix commit; merge.

## Commit sequence
1. `docs(planning): F11 spec + plan (Gate 1)`
2. `feat(notifications): validation primitives + port and adapters (TDD)`
3. `feat(notifications): migration 0007, models, repositories`
4. `feat(notifications): NotificationService + OtpService`
5. `feat(notifications): public OTP routes, settings, wiring`
6. review fixes, then PR.
