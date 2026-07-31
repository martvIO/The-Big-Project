---
tags: [frontend, storefront, typescript, validation, constant-parity, booking]
sources: [frontend/apps/storefront/src/validation.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/validation.ts
blob: a475863a5f4f53dd83eea5e6d8993f2e7bf4c52c
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/validation.ts

**Role.** The client-side mirror of the booking form's server bounds — two length caps, two control-character classes, and the Israeli-mobile normalizer — so the bride sees an immediate Hebrew error instead of a round-trip 400. **The backend is the authority**; this file exists only to make its refusals predictable, and a Python test fails the build if any of it drifts.

**Module.** [[frontend/apps/storefront/src/_index]] · **Layer.** validation

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `MAX_CUSTOMER_NAME_LENGTH` | const | 80 — mirrored from `app.booking.validation` |
| `MAX_BOOKING_NOTES_LENGTH` | const | 500 — mirrored from `app.booking.validation` |
| `validateName` | fn | `string → error message \| null` |
| `validateNotes` | fn | `string → error message \| null` |
| `normalizePhone` | fn | raw → `+9725XXXXXXXX`, or the raw string unchanged when invalid |
| `validatePhone` | fn | `string → error message \| null` |

`CONTROL_CHARS` and `CONTROL_CHARS_EXCEPT_WS` are module-private but are **read as text** by the parity test, so their declaration form (`const NAME = /…/;`) is part of the contract.

## Behavior

**[[backend/tests/test_frontend_constant_parity.py]] pins this file from the Python side, and it pins two different things.** The numeric constants are scraped by regex and compared against `app.booking.validation`'s attributes of the same name. Separately, `test_control_character_classes_match_the_backend` extracts the **regex bodies byte-for-byte** and asserts they equal `_CONTROL_CHARS.pattern` and `_CONTROL_CHARS_EXCEPT_WS.pattern` — so `/[\x00-\x1f\x7f]/` and `/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/` are not merely equivalent to the Python classes, they are the same characters in the same order. Rewriting one of them into a shorter-but-equal form fails CI. That test reads both files as **text** so it can run in the fast, no-Docker, no-Node suite.

**Backend semantics are mirrored in order, not just in outcome:** blank checks run on the **trimmed** value, length checks on the **raw** value, control-character checks last, and the **raw** value is what goes on the wire. Getting the order wrong would let a name of 80 spaces past a trimmed length check the server applies to the raw string.

**The two control classes differ by exactly `\t \n \r`, and the asymmetry is the interesting part.** `name` bars the whole C0 set plus DEL because a line break in a value F16 templates into an SMS is header-injection material. `notes` is a paragraph, so it keeps the three whitespace controls. The failure this guards is not hypothetical: a bride pasting notes out of Word carries U+000B or U+000C, spends a real SMS getting to the submit, accepts the policy — and then every attempt fails identically with a 400 she can neither understand nor escape, while burning her booking-create budget.

**`normalizeOrNull` is the client twin of `normalize_israeli_mobile`, same steps in the same order:** charset gate on the trimmed input (`/^\+?[0-9 ()-]+$/`), strip every non-digit, replace a leading `05`'s zero with `972`, then assert the final shape `/^\+9725\d{8}$/`. The OTP token is keyed on the **normalized** form, so any divergence here surfaces at runtime as `PHONE_NOT_VERIFIED` rather than as a validation error. `normalizePhone` returns the raw string when normalization fails — safe only because `validatePhone` has already refused it, so an invalid value never reaches the wire. Normalization happens exactly once, here, before each of `/otp/send`, `/otp/verify` and `/bookings`.

**Messages come from [[frontend/apps/storefront/src/i18n/he.ts]] through `i18n.t()`, not from string literals.** The module imports the initialised i18next instance directly rather than using a hook, because these are called from event handlers. [[frontend/apps/manage/src/validation.ts]]'s twin hardcodes its Hebrew, and the cost surfaced in review: `he.ts` separately defined `booking.nameRequired`, `nameTooLong`, `notesTooLong` and `phoneInvalid` with byte-identical text that no production code referenced, so the two copies were held together by nothing but luck.

## Depends On

- [[frontend/apps/storefront/src/i18n/index.ts]] — the initialised i18next instance, imported as a value
- [[backend/app/booking/validation.py]] — the authority these constants and classes mirror
- [[backend/app/notifications/validation.py]] — `normalize_israeli_mobile`

## Depended On By

- [[frontend/apps/storefront/src/routes/BookPage.tsx]] — the only production consumer
- [[frontend/apps/storefront/src/__tests__/validation.test.ts]]

## Tests

- [[frontend/apps/storefront/src/__tests__/validation.test.ts]] — the TypeScript side
- [[backend/tests/test_frontend_constant_parity.py]] — the drift guard; fails if a bound or a control-character class diverges from Python

## Notes

Two `oxlint-disable-next-line no-control-regex` comments are load-bearing: the rule would otherwise reject the very literals the parity test demands. **`PHONE_CHARSET` and `NORMALIZED_MOBILE` are NOT covered by the parity test** — `_TS_REGEX_RE` only extracts what `_MIRRORED_PATTERNS` names, and that tuple lists only the two control classes. A drift in the phone normalizer is caught by the OTP round-trip failing, not by CI.
