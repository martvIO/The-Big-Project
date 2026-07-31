---
tags: [frontend, manage, typescript, validation, mirror, money, hebrew]
sources: [frontend/apps/manage/src/validation.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/validation.ts
blob: 233e316e8e71f51ff54ac753b8180716e5cadf96
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/src/validation.ts

**Role.** The console's client-side **mirror** of the backend's bounds and validators, in three blocks (boutique settings, catalog, staff) plus the shekel↔agorot money helpers. Every validator returns `string | null` — a ready-to-render Hebrew message, or `null` for valid — so a form's error path is one `if`. The backend stays the authority; these exist so the owner sees an immediate Hebrew sentence instead of a round-trip 400 in English.

**Module.** [[frontend/apps/manage/src/_index]] · **Layer.** validation

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `MAX_APPOINTMENT_TYPE_NAME_LENGTH`, `MAX_DURATION_MINUTES`, `MAX_DEPOSIT_AMOUNT_AGOROT`, `MAX_TERMS_TEXT_BYTES` | const | boutique-settings bounds |
| `agorotFromIlsInput(input)` | fn | `"120.50"` → `12050`; `null` if the string is not `\d+(\.\d{1,2})?` |
| `ilsFromAgorot(agorot)` | fn | exact `"120.50"` round-trip for form fields |
| `formatIlsAmount(agorot)` | fn | display only — thousands grouped, a `.00` fraction dropped |
| `validateAppointmentType(draft)` | fn | name, duration, deposit-required-implies-amount |
| `validateWeeklyRules(rules)` | fn | day/time/capacity bounds **and** same-day window overlap |
| `validateExceptionTimes(open, close)` | fn | both-or-neither, and close after open |
| `validateTerms(draft)` | fn | non-empty text, 50 KB **byte** cap, refund window, forfeit percent |
| `MAX_DRESS_*`, `MAX_PRICE_AGOROT`, `MAX_VARIANTS_PER_DRESS`, `MAX_SIZE_LABEL_LENGTH`, `MAX_VARIANT_QUANTITY`, `MAX_MEDIA_PER_DRESS`, `MAX_UPLOAD_BYTES`, `MIN_UPLOAD_BYTES`, `MAX_SEARCH_LENGTH`, `MAX_SORT_ORDER` | const | catalog bounds |
| `ACCEPTED_CONTENT_TYPES` | const | `image/jpeg\|png\|webp` → extension |
| `EU_SIZE_QUICK_LIST` | const | frontend-only quick-entry sizes, no server counterpart |
| `normalizeSizeLabel(label)` / `sizeKey(label)` | fn | trim+collapse whitespace / the lowercased collision key |
| `validateDress`, `validateVariants`, `validateUploadFile` | fn | catalog validators |
| `MIN_STAFF_PASSWORD_LENGTH`, `MAX_PASSWORD_LENGTH`, `MAX_DISPLAY_NAME_LENGTH` | const | staff bounds |
| `validateStaffDraft(draft)` | fn | display name, optional email shape, optional password length |
| `AppointmentTypeDraft`, `WeeklyRuleDraft`, `TermsDraft`, `DressDraft`, `VariantDraft`, `UploadCandidate`, `StaffDraft` | interface | the shapes the validators take |

## Behavior

**Money never touches a float.** `agorotFromIlsInput` splits on the dot and does integer arithmetic (`whole * 100 + fraction.padEnd(2,"0")`); `parseFloat(x) * 100` would round `120.29` to 12028 on some inputs. The regex refuses a leading `+`/`-`, a bare `.5`, three decimals and any whitespace beyond the trim, so a rejected string is `null` rather than a silently truncated number. `formatIlsAmount` is display-only and its callers wrap the result in `<bdi dir="ltr">` — the grouped numeric run must not reorder inside surrounding Hebrew.

**`validateWeeklyRules` is the only validator with real structure.** After the per-rule bounds it buckets rules by `day_of_week`, sorts each bucket by opening minute, and rejects a window that starts before the previous one closes. **Touching windows are legal** (`close == next open`), which is what makes a lunch-break split into two windows work; an off-by-one to `<=` here would silently forbid the shape F7 exists to support.

**Two caps are deliberately the "wrong" unit, and both are correct.** `validateTerms` measures `terms_text` with `TextEncoder` because the server's 50 KB limit is bytes and Hebrew is two bytes per character — a character count would let a Hebrew policy nearly twice the allowed size through to a 400. `validateUploadFile` also enforces a **minimum** size (`MIN_UPLOAD_BYTES`), which catches a zero-or-tiny file that is not a real image. HEIC gets its own message ahead of the general type check because Safari hands over an empty `type` for it, so the filename extension is the fallback, and «שמרי כ-JPG» is an action the owner can actually take on her phone.

**`sizeKey` is the client-side twin of the database's `lower(size_label)` partial unique index** — it is how `validateVariants` predicts, before the request leaves, the collision that index would refuse — so "US 6" and "us 6" cannot become two stock buckets for one size. `normalizeSizeLabel` deliberately does **not** lowercase: the owner's "US 6" is stored as typed, and only the collision *key* is folded.

**`EMAIL_SHAPE` exists to close a gap the browser leaves.** WHATWG's `type="email"` control regex makes the dot in the domain optional, so `dana@bella` passes native constraint validation and comes back as an English pydantic sentence in an RTL console. The regex is deliberately not an RFC 5322 attempt — the server remains the authority on deliverability. `StaffDraft.email` is `null` on the edit form (the address is not editable after creation) and `password: null` means "leave it alone". There is **no password composition rule** by design: NIST 800-63B advises against them, since they push an owner toward `Boutique1!`.

The staff block is load-bearing beyond convenience: the staff forms render one field-local Hebrew message for the single 400 the server can answer them (a wrong `current_password`), and that is only honest because every other 400 those forms could produce is caught here first.

## Depends On

- [[backend/app/boutique/validation.py]], [[backend/app/catalog/validation.py]], [[backend/app/auth/schemas.py]] — the Python bounds these mirror

## Depended On By

- [[frontend/apps/manage/src/components/HoursSection.tsx]], [[frontend/apps/manage/src/components/TypesSection.tsx]], [[frontend/apps/manage/src/components/TermsSection.tsx]], [[frontend/apps/manage/src/components/CatalogSection.tsx]], [[frontend/apps/manage/src/components/DressEditor.tsx]], [[frontend/apps/manage/src/components/VariantMatrix.tsx]], [[frontend/apps/manage/src/components/MediaGallery.tsx]], [[frontend/apps/manage/src/components/StaffSection.tsx]]

## Concepts

- [[RTL And Bidi Isolation]]

## Tests

- [[frontend/apps/manage/src/__tests__/validation.test.ts]]
- [[backend/tests/test_frontend_constant_parity.py]] — **the drift guard**: fails if any constant here diverges from its Python counterpart

## Notes

`EU_SIZE_QUICK_LIST` is intentionally frontend-only — the backend accepts free-text labels and has no consumer for it, so declaring it server-side too would guarantee drift with nothing to catch it. `MAX_MEDIA_PER_DRESS` and `MAX_SEARCH_LENGTH` are exported for callers to bound their own inputs and are not referenced by any validator in this file.
