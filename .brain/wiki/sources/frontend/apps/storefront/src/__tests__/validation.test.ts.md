---
tags: [frontend, storefront, test, vitest, validation, phone, booking, mirror]
sources: [frontend/apps/storefront/src/__tests__/validation.test.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/validation.test.ts
blob: 9dcc13a33bf3af6569f1d17377ec9a1f0def073f
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/validation.test.ts

**Role.** The mirror test: it pins the client-side booking validators to the *backend's* rules character for character — the two length bounds, the two different control-character sets, the order the three checks run in, and the exact accept/reject table for Israeli mobile numbers. Every divergence it catches is a 400 the visitor cannot retry away.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `booking constants mirror app/booking/validation.py` | suite | `MAX_CUSTOMER_NAME_LENGTH === 80`, `MAX_BOOKING_NOTES_LENGTH === 500` |
| `validateName` | suite | blank-after-trim, **raw**-length measurement, the whole C0 set plus DEL, and check ordering |
| `validateNotes` | suite | optional; raw length; keeps `\t \n \r` and rejects the rest of C0 |
| `ACCEPTED_PHONES` | fixture | nine `[raw, normalized]` pairs — trunk-prefixed, punctuated, `+972`, bare `972`, and the `052`/`058` prefixes |
| `REJECTED_PHONES` | fixture | thirteen rejects: landlines both ways, too short/long, foreign, junk charset, `972` + leading zero, double plus, a letter inside |
| `validatePhone / normalizePhone` | suite | accepts exactly the normalizer's set; on a reject, `normalizePhone` passes the raw input **through** unchanged |

## Behavior

**Length is measured on the raw value, not the trimmed one, because the backend does.** The suite proves it with a value that is 79 characters trimmed and 81 raw: the client must reject it, since blessing it only moves the failure to a 400 the bride cannot clear by editing anything she can see.

The two control-character sets differ on purpose and are tested apart. A name goes through `_CONTROL_CHARS` — the **whole** C0 range plus DEL, newlines included — because F16 templates the name into an SMS. Notes go through `_CONTROL_CHARS_EXCEPT_WS`: it is a paragraph, so `\t`, `\n` and `\r` survive and everything else does not. The notes cases name `U+000B` and `U+000C` explicitly, since those are what a paste out of a word processor actually carries and they were the whole undiagnosable 400.

Check **order** gets its own test, and it is the subtle one. A lone tab is simultaneously blank-after-trim and a control character; the backend answers "name must not be blank", so the client must say the same thing rather than the more specific-sounding control-character message. Likewise a NUL prepended to an already-maximal name reports the length error, not the control error. Two validators that reject the same inputs but disagree on *which* message they show still produce a UI that contradicts the server.

The phone table is ported from [[backend/tests/test_notifications_validation.py]] and both halves are asserted per row: `validatePhone` returns `null`/the Hebrew message, **and** `normalizePhone` returns the E.164 form or — on a reject — the raw input untouched. The pass-through on reject matters because it means `normalizePhone` is never a silent sanitiser; a caller that skips `validatePhone` gets garbage back rather than a plausible-looking wrong number. `"9720501234567"` (country code followed by the leading zero) and `"++972501234567"` are in the reject list specifically because a loose digit-strip implementation accepts both.

Expected messages are asserted as **literal Hebrew strings**, not through `t()`, because these live in [[frontend/apps/storefront/src/validation.ts]] rather than the i18n bundle.

## Depends On

- [[frontend/apps/storefront/src/validation.ts]] — the subject
- [[Vitest]]

## Depended On By

Nothing imports a test file. The rendered half is [[frontend/apps/storefront/src/__tests__/BookPage.test.tsx]], which asserts the messages reach the form; this file owns the rules themselves.

## Notes

The authority is the backend, always: when [[backend/app/booking/validation.py]] or the phone normalizer changes, this file is where the drift surfaces — but a green suite here proves only that the client matches what someone *believed* the backend does. The paired backend suite is the other half of the contract, and neither one alone is the mirror.
