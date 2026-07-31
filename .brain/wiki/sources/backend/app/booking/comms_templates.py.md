---
tags: [backend, booking, python, sms, hebrew, rtl, templates, pure-function]
sources: [backend/app/booking/comms_templates.py]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/booking/comms_templates.py
blob: f95778a555b1da996c7e8c84dd8b61032c170804
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# backend/app/booking/comms_templates.py

**Role.** The four Hebrew lifecycle SMS bodies, the UCS-2 segment arithmetic that keeps them inside a three-segment cost ceiling, the boutique-zone date/weekday/time rendering they use, and the mask that keeps the raw manage token out of the `message_log` evidence trail.

**Module.** [[backend/app/booking/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `confirmation_sms_body` | fn | Sent immediately after a booking commits |
| `reminder_sms_body` | fn | One body for all three reminder bands |
| `owner_cancel_sms_body` | fn | Owner cancelled — states no refund/forfeit outcome |
| `owner_reschedule_sms_body` | fn | `starts_at` is the NEW time; same manage link |
| `manage_link` | fn | `https://{slug}.{base_domain}/b/{token}` |
| `mask_manage_link` | fn | Replaces the raw token with `MASKED_TOKEN` for the log body |
| `ucs2_segments` | fn | Segment cost of a body as UCS-2 |
| `truncate_boutique_name` | fn | Slice to `BOUTIQUE_NAME_MAX_CHARS`, then `rstrip` |
| `jerusalem_weekday` · `jerusalem_date` · `jerusalem_time` | fn | Boutique-zone rendering |
| `UCS2_SINGLE_LIMIT` · `UCS2_CONCAT_LIMIT` | const | 70 / 67 |
| `*_MAX_SEGMENTS` | const | 3 for each of the four bodies |
| `BOUTIQUE_NAME_MAX_CHARS` · `MANAGE_LINK_SLUG_BUDGET_CHARS` | const | 25 / 30 |
| `MASKED_TOKEN` | const | Three mask glyphs, the same one the OTP mask and the UI use |

## Behavior

Pure — nothing here imports from `app/db`, opens a session or reaches a sender — so every rule below is unit-testable with no I/O. The wording comes verbatim from the approved copy document; counsel signs the bodies off before a real provider goes live, which is a pre-provider gate rather than a pre-merge one.

**The segment budget is the reason most of the constants exist.** A Hebrew body is UCS-2 on the wire: 70 characters in a single message, 67 once the provider has to concatenate (six of the seventy go to the UDH header). `ucs2_segments` counts UTF-16 code units, so an astral character costs two, and it ceils without importing `math`. Three segments is a **cost** ceiling, not a correctness one — a fourth sends fine and bills again. Two inputs are unbounded in the database and therefore capped or budgeted here: `tenants.name` is unbounded TEXT and is truncated to 25 characters so production matches the tested fixture; the tenant slug can legally be a 63-character DNS label, which pushes the confirmation body to a fourth segment, and rather than refuse to boot on a legitimate slug the ceiling is documented, budgeted at 30 characters and pinned by a test — so an invoice is never how it gets discovered. `truncate_boutique_name` `rstrip`s after slicing because a cut landing mid-word leaves a trailing space and every body puts a colon or comma straight after the name.

`manage_link` uses the short `/b/{token}` path deliberately: the alternative spends roughly fourteen extra UCS-2 characters per SMS forever. It is always `https`, even for a dev `base_domain`, because a real SMS may not carry a cleartext link and the fake sender sends nothing anyway. `mask_manage_link` is what makes the evidence row safe: `bookings` stores only the token's sha256, so persisting the raw token in the forever-table beside its own hash would defeat hashed storage completely — identical reasoning and mechanism to the OTP body mask.

The weekday table is hand-rolled and indexed by `datetime.weekday()` **directly** rather than reordered at the call site, and it is not `locale`-dependent, so every body reads the same on a CI runner, on a laptop and in Israel. `jerusalem_weekday` returns the bare day word so «ליום {weekday}» reads correctly for שבת too.

Three copy decisions are load-bearing. The **confirmation carries no location line**: one body cannot honestly carry both unbounded tenant free-text and the manage link inside three segments, and the manage page's contact panel carries maps/waze anyway — so the link she gets leads to the location. The **reminder carries no «מחר»**, because a booking made under 24 hours out gets its reminder immediately, so "tomorrow" would be false; the weekday and date carry the timing instead, which is also what makes a reminder that fires late still honest, since the body renders from `starts_at` and never from "in 24 hours". The **owner-cancel body states no refund or forfeit outcome**, because nothing yet exists to compute one, and it drops the «לשאלות:» clause entirely when the boutique published no phone — a freshly provisioned tenant has every profile field null, and that label followed by nothing is worse than a shorter sentence.

Every constant here is deliberately not env-tunable, per the house rule that `Settings` carries deployment identity and never product policy.

## Depends On

- [[backend/app/notifications/validation.py]] — `MASK_CHAR`
- [[backend/app/storefront/validation.py]] — `BOUTIQUE_TIMEZONE`

## Depended On By

- [[backend/app/booking/comms.py]] — the only caller; builds and masks every body
- [[backend/app/booking/tokens.py]] — not an import, but the 43-character token length the budget arithmetic assumes is fixed there

## Concepts

- [[Tenant Resolution]]

## Tests

- [[backend/tests/test_booking_comms_templates.py]] — every body, the segment arithmetic, truncation, and the masking
- [[backend/tests/test_manage_token.py]] — pins `MANAGE_LINK_SLUG_BUDGET_CHARS` against the slug rules
- [[backend/tests/test_booking_comms_db.py]] — asserts `MASKED_TOKEN` is what actually lands in `message_log`

## Notes

Design context: [[.planning/specs/booking-comms.md]] and the approved copy at [[.planning/design/screens/manage-booking/copy.md]].
