---
tags: [backend, notifications, otp, sms, python, validation, policy, israel]
sources: [backend/app/notifications/validation.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/notifications/validation.py
blob: eb583cf890006e54d1b57ee689aba41f19510b39
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/notifications/validation.py

**Role.** The one place OTP *product policy* lives — code length, TTL, verify-attempt cap, verification-token TTL — plus the pure helpers that normalize an Israeli mobile to E.164, mint a code, render the Hebrew SMS body, and mask the code out of it before it is persisted.

**Module.** [[backend/app/notifications/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `OTP_CODE_LENGTH` | const | `6` |
| `OTP_TTL_SECONDS` | const | `300` — epic requirement is ≤ 5 minutes |
| `OTP_MAX_VERIFY_ATTEMPTS` | const | `5` guesses per code |
| `VERIFICATION_TOKEN_TTL_SECONDS` | const | `600` — how long the possession proof survives after verify |
| `MASK_CHAR` | const | `●`, the glyph the UI already uses for concealed values |
| `normalize_israeli_mobile` | fn | Human input → `+9725XXXXXXXX`, or `DomainValidationError` |
| `generate_otp_code` | fn | `secrets.randbelow(10**6)` zero-padded to 6 digits |
| `otp_sms_body` | fn | `f"קוד האימות שלך: {code}"` |
| `mask_otp_body` | fn | Replaces the code with six `●` — what `message_log` stores for `kind='otp'` |

## Behavior

These constants are **deliberately not env-tunable**, following the F8/F10 rule that `Settings` carries deployment identity and never product policy; the one exception is the send/verify rate-limit *windows*, which follow the login and presign precedent and live in [[backend/app/core/config.py]] so they can be tuned during an incident. That split is why raising a TTL requires a code change and a test run, while widening a budget does not.

`normalize_israeli_mobile` runs a charset gate before it strips anything: at most one leading `+` followed by digits, spaces, parens and hyphens. It then removes every non-digit, rewrites a leading `05` to `972`, prefixes `+`, and requires the result to match `^\+9725\d{8}$`. Israeli mobiles only, deliberately — the pilot is Israeli, the SMS route is Israeli, and a wrong-country send is pure cost with no delivery. Landlines, foreign numbers and junk all raise `DomainValidationError`, which maps to a 400, because storing an unreachable phone strands the customer behind an SMS link that can never arrive. Every spelling of one number collapses to one string, which is what lets the rate limiters in [[backend/app/notifications/service.py]] key a single bucket per human rather than one per formatting variant.

`generate_otp_code` uses `secrets`, not `random`, and zero-pads — `000042` is a legal code and must not be silently shortened. `mask_otp_body` is a plain `str.replace`, so it is an identity function when the code does not occur in the body; that is fine because it is only ever applied to the body `otp_sms_body` just produced. Masking exists because `message_log` is a forever table and the Spam-Law evidence value is "an OTP was sent to this phone at this time", never the digits — the code itself is worthless in five minutes.

The 5-attempt cap, not the hash, is the real brute-force control: a 6-digit code is roughly 20 bits, so 5 guesses against 10^6 is about 0.0005% per code, and the counter is tracked on the `otp_codes` row precisely so it survives across requests.

## Depends On

- [[backend/app/errors.py]] — `DomainValidationError`
- `re`, `secrets` (stdlib)

## Depended On By

- [[backend/app/notifications/service.py]] — every constant and helper here
- [[backend/app/booking/service.py]] — `normalize_israeli_mobile` on the customer phone
- [[backend/app/booking/owner.py]] — `normalize_israeli_mobile` for the owner phone-correction tap
- [[backend/app/booking/comms_templates.py]] — imports `MASK_CHAR` to mask manage links the same way

## Concepts

- [[One Time Passcode]]
- [[Product Policy Vs Deployment Identity]]
- [[Hebrew First UX]]

## Tests

- [[backend/tests/test_notifications_validation.py]] — `test_normalizes_accepted_formats`, `test_rejects_everything_else`, `test_shape`, `test_zero_padding_preserved`, `test_otp_sms_body_contains_the_code`, `test_mask_hides_the_code_but_keeps_the_shape`, `test_mask_without_occurrence_is_identity`, `test_epic_bounds`

## Notes

The normalization rules are the same derivation family as `waPhone` in [[frontend/apps/storefront/src/lib/contact.ts]] — if one side changes, the other has to move with it; there is no shared source and no parity test binding them.

`otp_sms_body` wording is transactional-only on purpose; the template set gets a counsel read before a real provider goes live (spec Amendment 40 note).
