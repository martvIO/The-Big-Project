---
tags: [backend, boutique, validation, python, product-policy, security, settings]
sources: [backend/app/boutique/validation.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/boutique/validation.py
blob: 2c86a7fa36a1e469eea3faf3634d4e9d9600debe
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/boutique/validation.py

**Role.** Pure, I/O-free write-time gates for owner settings — the storefront-profile fields (phone, address, description, `maps_url`, essence, Instagram handle), the boolean toggles, appointment types, weekly opening windows, exception dates and the cancellation-policy terms — plus every numeric bound the migration CHECKs mirror.

**Module.** [[backend/app/boutique/_index]] · **Layer.** db

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `BoutiqueValidationError` | class | `DomainValidationError` subclass → shared house-shape 400 |
| `WeeklyRuleInput` | frozen dataclass | `(day_of_week, open_time, close_time, capacity=1)` |
| `validate_maps_url` | fn | Length + `urlsplit` scheme allowlist (`http`/`https`) + non-empty netloc |
| `validate_phone` | fn | At most one leading `+`, then digits/space/parens/hyphen only, and at least one digit |
| `validate_instagram_handle` | fn | Anchored `^[A-Za-z0-9._]{1,30}\Z` — a leading `@` is **rejected**, not stripped |
| `validate_profile` | fn | Rejects unknown keys, requires every value be a `str`, then applies the per-field rules |
| `validate_toggles` | fn | Rejects unknown keys; `isinstance(value, bool)`, not truthiness |
| `validate_appointment_type` | fn | Name, `0 < duration_minutes <= 1440`, audience membership, deposit interplay, sort bound |
| `validate_weekly_rules` | fn | Count, `0 <= day_of_week <= 6`, `close > open`, capacity, and same-day overlap detection |
| `validate_exception_times` | fn | Both times set (special hours) or both empty (closed all day); `close > open` |
| `validate_exception_note` | fn | Length ceiling |
| `validate_terms` | fn | Non-blank text, **byte**-capped at 50 KB, `refundable_until_hours_before` and `forfeit_percent` bounds |
| `MAX_*` | const | Phone 32, address 500, description 2000, `maps_url` 1000, essence 120, Instagram 30, type name 200, duration 1440, note 500, terms 50 KiB, deposit 100 000 000 agorot, 50 weekly rules, capacity 1000, refundable 10 years of hours, sort ±1 000 000 |
| `ALLOWED_MAPS_URL_SCHEMES` | const | `frozenset({"http", "https"})` |

## Behavior

Every function raises `BoutiqueValidationError` on failure and returns `None` on success. Two of the gates are security boundaries rather than tidiness. `validate_maps_url` runs `urlsplit`, which lowercases the scheme, so a `JavaScript:` payload cannot slip past a case-sensitive comparison — this is the write-time half of a defense-in-depth pair, since the storefront also escapes at render time. `validate_toggles` uses `isinstance(value, bool)` rather than truthiness precisely so `1` or `"true"` cannot masquerade as a boolean and land in the `tenants.settings` JSONB as the wrong type.

`validate_instagram_handle` rejects a leading `@` instead of normalising it away, and the reasoning generalises: the stored value is interpolated verbatim into `https://instagram.com/{handle}` by the storefront's contact panel, so silently accepting `@bella` would make the column's contract depend on which write path wrote it. One canonical form enforced at the only gate keeps the link builder a pure join.

`validate_profile` and `validate_toggles` both reject unknown keys, which is what makes the JSONB merge safe — `tenants.settings` has no column-level schema, so an unlisted key would otherwise persist forever. Empty string means "cleared field", so the format checks are guarded on truthiness while the length checks use `is not None`: clearing a `maps_url` by sending `""` is legal, sending `"javascript:alert(1)"` is not.

`validate_weekly_rules` is the only non-trivial algorithm here. It buckets rules by day, sorts each bucket by `(open_time, close_time)` and walks adjacent pairs with `itertools.pairwise`, raising when `next.open < prev.close`. Touching windows (`close == next open`) are accepted deliberately — a 09:00–13:00 and a 13:00–18:00 pair is a lunch split, not an overlap. Note the check is per day only; nothing here relates two rules on different days.

`validate_terms` caps on `len(terms_text.encode("utf-8"))` rather than `len()`, because Hebrew is two bytes per character in UTF-8 and the 50 KB budget is about storage of immutable evidence, not glyph count. That immutability is also why the numeric bounds are restated here at all rather than left to the Pydantic `Field` caps: terms rows are append-only, so a bad value written by a non-router caller could never be corrected in place — it would need a whole new version.

`validate_appointment_type` encodes the one cross-field rule in the module: `deposit_required` demands a positive `deposit_amount_agorot`, while an amount without the flag is allowed (a boutique may record a figure before switching deposits on). Money is integer agorot everywhere and never float.

## Depends On

- [[backend/app/errors.py]] — `DomainValidationError`
- [[backend/app/models/constants.py]] — `AppointmentAudience`, whose values become the accepted audience set

## Depended On By

- [[backend/app/boutique/service.py]] — every validator, plus `WeeklyRuleInput`
- [[backend/app/boutique/schemas.py]] — every `Field` bound is one of these constants
- [[backend/app/boutique/router.py]] — `WeeklyRuleInput`
- [[backend/tests/test_booking_validation.py]] — reuses `MAX_RULE_CAPACITY` so the slot engine's seat ceiling cannot drift from the rule's
- [[backend/tests/test_storefront_validation.py]]

## Concepts

- [[Product Policy Vs Deployment Identity]]
- [[Stored XSS Prevention]]
- [[Append Only Terms Versions]]

## Tests

- [[backend/tests/test_boutique_validation.py]] — the unit suite
- [[backend/tests/test_storefront_validation.py]] — the profile fields as the storefront consumes them
- [[backend/tests/test_boutique_service.py]] — imports `BoutiqueValidationError` to assert the service surfaces it unchanged
- [[backend/tests/test_boutique_api.py]] — `validate_profile` at the HTTP boundary

## Notes

`MAX_SORT_ORDER` is declared here and independently re-declared with the same value in [[backend/app/catalog/validation.py]]; the catalog file's comment calls it "reused from" this module, but nothing mechanically links the two literals.

`validate_appointment_type`'s duration message hardcodes "between 1 and 1440" rather than interpolating `MAX_DURATION_MINUTES` — cosmetic today, since the constant is `24 * 60`, but the two would drift silently if the cap changed.

Design context: [[.planning/specs/owner-settings.md]].
