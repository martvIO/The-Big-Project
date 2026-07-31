---
tags: [backend, storefront, python, validation, timezone, rate-limiting, accessibility]
sources: [backend/app/storefront/validation.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/storefront/validation.py
blob: 5ec6d55d5dd75079a9604075a3c556686789005e
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# backend/app/storefront/validation.py

**Role.** The public storefront's named bounds, its two error types, the boutique's wall clock (`Asia/Jerusalem`) and `profile_text` — the single place the `""`-to-`null` collapse for published profile strings lives. Small, but it is imported by six modules across `storefront/` and `booking/`, which makes it the shared vocabulary rather than a leaf.

**Module.** [[backend/app/storefront/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `STOREFRONT_LIST_DEFAULT_LIMIT` | const | `24` — fills 6/8/12 rows of the 2/3/4-column grid |
| `STOREFRONT_LIST_MAX_LIMIT` | const | `24` — **equal** to the default, deliberately (see Behavior) |
| `UPCOMING_EXCEPTIONS_LIMIT` | const | `12` — one editorial card's worth of closures on `/about` |
| `BOUTIQUE_TIMEZONE` | const | `ZoneInfo("Asia/Jerusalem")` — the boutique's own wall clock |
| `Clock` | type alias | `Callable[[], datetime]`, injectable so date cutoffs are testable with no I/O |
| `StorefrontThrottledError` | class | Per-tenant anonymous read budget spent → 429 |
| `SlotWindowError` | class | `DomainValidationError` subclass → house-shape 400 |
| `profile_text` | fn | One published profile string, or `None` |
| `today_jerusalem` | fn | The boutique's current calendar date |

## Behavior

**`STOREFRONT_LIST_MAX_LIMIT` equals the default, unlike manage's 100, and that is the point.** Every extra unit is a denial-of-wallet multiplier: one unauthenticated call mints one fresh 900-second redeemable media URL per item, each worth up to the upload byte cap and redeemable by any third party. Symmetry with the *authenticated* manage list is not an argument for a public endpoint. Raise it only in the feature that ships a UI which asks for more.

**Nothing here is env-tunable, and nothing here is mirrored to the frontend.** `Settings` carries deployment identity and never product policy, so these constants stay in code; and because no storefront constant is enforced client-side, `test_frontend_constant_parity.py` gains no rows from this file. The *read-throttle* bounds are the documented exception — they live in [[backend/app/core/config.py]] following the `media_presign_*` and `login_*` precedent, so they can be tightened during an incident without a deploy.

**`BOUTIQUE_TIMEZONE` is a correctness boundary, not a formatting nicety.** Opening hours, exception dates and "closed today" are local-calendar facts; filtering them against a UTC date would drop or keep a row for the two hours either side of midnight in Israel. The frontend binds "today" to the same IANA zone and the two must agree, or an exception dated today vanishes from `/about` for those hours. `today_jerusalem` takes an optional `Clock` because the CI runner, a developer's laptop and Israel are three different calendar days for part of every day.

**`profile_text` strips, then collapses `""` to `None`.** Empty string is the wire's canonical *cleared* value and the manage form seeds every blank field to `""` before submitting, so any owner who saves the profile once converts their blanks from `null` to `""`. Shipping `""` to a public surface renders `<a href="tel:">` with no accessible name — a WCAG 2.4.4 (A) failure. The `.strip()` comes first because an owner clearing a field by deleting its text often leaves a space behind, and `" "` is truthy: a space-only address would otherwise render a Waze link to nowhere. A non-`str` value returns `None` rather than raising, since `settings["profile"]` is untyped JSONB. Both public projections read through this — `/about` and the manage-page contact block — so there is exactly one copy of the rule.

**The two error classes differ in kind.** `SlotWindowError` subclasses `DomainValidationError` from [[backend/app/errors.py]] purely to inherit the existing 400 handler — no new handler, no new error code. `StorefrontThrottledError` is its own bare class with its own handler in [[backend/app/main.py]] mapping it to a 429 with the shared `TOO_MANY_ATTEMPTS` body; reusing auth's `RateLimitedError` would have dodged a three-line handler by importing a *login* error into the public read path, a semantic lie no test would catch. Reparenting the throttle errors onto a common base is a behaviour-neutral cleanup owned by F21.

## Depends On

- [[backend/app/errors.py]] — `DomainValidationError`, the base `SlotWindowError` inherits its handler from

## Depended On By

- [[backend/app/storefront/service.py]] — bounds, `Clock`, `today_jerusalem`, `BOUTIQUE_TIMEZONE`, `SlotWindowError`
- [[backend/app/storefront/router.py]] — the two list bounds, `StorefrontThrottledError`, `profile_text`
- [[backend/app/main.py]] — registers the `StorefrontThrottledError` → 429 handler
- [[backend/app/booking/slots.py]] · [[backend/app/booking/slots_io.py]] — `BOUTIQUE_TIMEZONE`
- [[backend/app/booking/owner.py]] — `BOUTIQUE_TIMEZONE`, `Clock`
- [[backend/app/booking/service.py]] · [[backend/app/booking/backfill.py]] — `Clock`
- [[backend/app/booking/manage.py]] — `Clock`, `profile_text`
- [[backend/app/booking/comms.py]] — `profile_text`, for the SMS contact block

## Concepts

- [[Rate Limiting]]
- [[Fail Closed Defaults]]

## Tests

- [[backend/tests/test_storefront_validation.py]] — the bounds, `profile_text`, `upcoming_exceptions`, and the whole `slot_window` clamping table
- [[backend/tests/test_storefront_api.py]] — the limits as seen at the router
- [[backend/tests/test_booking_comms_db.py]] — the `""`-collapse reaching the SMS body
- [[backend/tests/test_frontend_constant_parity.py]] — the file this one deliberately adds no rows to

## Notes

The comparison in `STOREFRONT_LIST_DEFAULT_LIMIT`'s comment is to `DRESS_LIST_DEFAULT_LIMIT` in [[backend/app/catalog/validation.py]] — check that the two are still in step before changing either.

Design context: [[.planning/specs/storefront-browse.md]], [[.planning/specs/booking-comms.md]].
