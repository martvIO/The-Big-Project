---
tags: [frontend, manage, test, vitest, validation, money, mirrored-bounds]
sources: [frontend/apps/manage/src/__tests__/validation.test.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/__tests__/validation.test.ts
blob: 46d606981f70603db3963781a0dd46c2a6a1c46c
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/__tests__/validation.test.ts

**Role.** The pure-function suite for the console's client-side validators, and — more importantly — the place where every **mirrored** bound is asserted against the literal value the backend uses, so a limit that drifts on one side fails here rather than as a surprise 422 in front of an owner.

**Module.** [[frontend/apps/manage/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `money (agorot <-> ILS)` | suite | `agorotFromIlsInput` / `ilsFromAgorot` — integer agorot in, two-decimal string out |
| `validateAppointmentType` | suite | deposit coupling, duration bounds, blank names |
| `validateWeeklyRules` / `validateExceptionTimes` | suites | window overlap, touching windows, one-sided exception times |
| `validateTerms` | suite | blank text, the 50 KB **byte** cap, refund window, `forfeit_percent` 0–100 |
| `catalog constants mirror app/catalog/validation.py` | suite | eleven bounds asserted at literal values, plus the accepted content types and the EU size list |
| `normalizeSizeLabel` / `formatIlsAmount` / `validateDress` / `validateVariants` / `validateUploadFile` | suites | catalog rules (Feature 8) |
| `validateStaffDraft` | suite | F51 bounds mirroring `backend/app/auth/schemas.py` |

## Behavior

**The constants suite asserts literals, not identities.** `expect(MAX_DRESS_NAME_LENGTH).toBe(200)` would be worthless as `toBe(MAX_DRESS_NAME_LENGTH)`; written as a literal it is a second copy of the number that has to be changed deliberately, which is the whole mechanism by which a mirror of [[backend/app/catalog/validation.py]] stays honest. The same applies to `ACCEPTED_CONTENT_TYPES` (exactly the three types the presign policy pins) and `EU_SIZE_QUICK_LIST` (even sizes 32–58 — explicitly frontend-only, with no backend counterpart).

Three rules are subtler than they look. The terms cap is a **byte** cap, not a character cap, and the test says why: Hebrew is 2 bytes/char in UTF-8, so 26,000 characters is 52,000 bytes and fails while 25,000 fits under 51,200. `normalizeSizeLabel` strips and collapses whitespace but **does not lowercase** — casing is preserved as typed — even though duplicate *detection* folds case, so `"US 6"` and `"us  6"` collide while both retain their own spelling. `validateWeeklyRules` accepts *touching* windows (`09:00–12:00` beside `12:00–17:00`, the lunch-break shape) while rejecting overlaps, and only within the same `day_of_week`.

`validateUploadFile` returns the user-facing Hebrew string rather than a boolean, and each message is asserted verbatim: HEIC gets its own transcode instruction (matched by content type *or* by extension, because Safari hands over an empty type), any other unaccepted type gets the generic JPG/PNG/WebP sentence, oversize gets the 10 MB sentence, and undersize gets «הקובץ אינו תמונה תקינה.» — the same message a `MEDIA_MISMATCH` confirm failure produces in the gallery.

`validateStaffDraft` exists mainly to close a **browser** gap, and the comment records it precisely: WHATWG's `type="email"` regex makes the dot in the domain optional, so `dana@bella` passes native constraint validation, and pydantic's `EmailStr` then answers an English sentence that the create form would render verbatim into the RTL console. The validator therefore rejects `dana@bella`, `dana@`, `@bella.example` and an address with an internal space, while accepting `d.a+1@mail.co.il` and a surrounding-whitespace address. Both `password: null` and `email: null` are accepted — the edit form omits the password to mean "unchanged" and has no email field at all (D5) — and there is deliberately **no** password composition rule: NIST 800-63B advises against them and they push an owner toward `Boutique1!` (spec D6).

## Depends On

- [[frontend/apps/manage/src/validation.ts]] — the subject
- [[Vitest]]

## Depended On By

Nothing imports a test file. The bounds it pins are mirrored from [[backend/app/catalog/validation.py]] and [[backend/app/auth/schemas.py]]; the components that consume them are covered by [[frontend/apps/manage/src/__tests__/VariantMatrix.test.tsx]], [[frontend/apps/manage/src/__tests__/MediaGallery.test.tsx]] and [[frontend/apps/manage/src/__tests__/StaffSection.test.tsx]].

## Concepts

- [[Fail Closed Defaults]]

## Notes

Money is integer agorot end to end; `agorotFromIlsInput` rejects `"1.234"` (three decimals) and negatives by returning `null`, and `formatIlsAmount` drops a zero fraction while grouping thousands — the shekel sign is added by the caller, never hand-formatted ([[frontend/scripts/qa-greps.sh]] bans hand-formatted shekels).
