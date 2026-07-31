---
tags: [frontend, manage, i18n, hebrew, copy, accessibility]
sources: [frontend/apps/manage/src/i18n/he.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/i18n/he.ts
blob: cd9017cb842cfca980b4f21b123e45d777c7f072
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/manage/src/i18n/he.ts

**Role.** The console's Hebrew string catalog and the only locale an owner can reach in v1 — every visible word in the owner console that is not data. It is structurally two catalogs in one object: **nested namespaces** (`document`, `console`, `nav`, `common`, `login`, `profile`) from the earlier sections, and **flat dotted literal keys** (`"booking.*"`, `"staff.*"`) transcribed row-for-row from the feature copy decks.

**Module.** [[frontend/apps/manage/src/i18n/_index]] · **Layer.** i18n

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `he` | const (`as const`) | `{ translation: { … } }` — the shape [[frontend/apps/manage/src/i18n/index.ts]] registers under `he` |

## Behavior

**The dotted keys are flat on purpose.** F15's booking copy and F51's staff copy are transcribed one key per row from [[.planning/design/screens/owner-bookings/copy.md]] and [[.planning/design/screens/manage-staff/copy.md]], so the deck and this block diff against each other line by line — nesting them would break that correspondence. They resolve because i18next's `ignoreJSONStructure` (default true) falls back to a flat lookup when the nested path misses, which is exactly why [[frontend/apps/manage/src/__tests__/i18n.test.ts]] exists: an unresolved key renders the key itself into the console, silently.

**Two of the decks' rules are mechanical and machine-enforced**: no exclamation mark anywhere, and no string that claims, implies or hedges that a message was sent. The second is not stylistic — the SMS send path swallows its errors, so the platform holds no evidence of delivery; every string states the state change and stops. `booking.deliveryNotice` says the limit out loud, once. The staff block goes further because there **is no channel** at all (no mailer exists in the backend, and SMS was removed from the staff auth path): `staff.passwordNotice` is phrased «יש למסור…» rather than «אינה נשלחת…» specifically because the latter contains נשלח and would trip the guard — and copy that has to dodge its own guard is one edit from lying.

**Status and role strings carry state in the word, never in colour.** `booking.statusConfirmed` / `Completed` / `NoShow` / `Cancelled` and `staff.roleOwner` / `roleShiftManager` are the accessible half of a Badge whose variant is redundant reinforcement, so the UI survives greyscale, colour blindness and forced-colours mode.

Two interpolation sites need bidi care and get it at the render site, not here: `booking.dayCount` (`{{count}}`) and `booking.phoneModalBody` (`{{phone}}`) are split and isolated by `isolateLtr` in [[frontend/apps/manage/src/lib/booking.tsx]], which is safe only because the surrounding Hebrew carries no digits of its own. `staff.deactivateBody` instead embeds a literal `<bdi>` tag and is rendered through `<Trans components={{ bdi: <bdi /> }}>` — a Latin staff name inside an RTL sentence reorders without an isolate, and the bare `<bdi>` (no `dir="ltr"`) is correct because the name may itself be Hebrew.

Two error-code maps live here and they are **not** equals. `booking.error.*` (four codes) is pinned by `SPEC_ERROR_CODES` in [[backend/tests/test_booking_owner_api.py]], so it cannot drift; `staff.error.*` (four codes) is kept by hand against `MAPPED_CODES` in [[frontend/apps/manage/src/components/StaffSection.tsx]] with nothing enforcing it. Every unmapped code — `VALIDATION_ERROR` included — deliberately falls through to the server's own message, because a per-field validation sentence cannot be reproduced client-side. `staff.currentPasswordWrong` is the one exception: that single 400 comes back as English, so the field renders its own Hebrew instead.

Some copy is deliberately *narrower* than it could be. `booking.rescheduleConsequence` says the link will point at the new time and does **not** say the old link dies, because reschedule only rotates the token when there is no pending reminder to inherit from. `booking.modalKeep` is «חזרה», not «ביטול» — a "cancel" button on a cancellation dialog is the worst word available. `staff.deactivateCta` is «השבתה», never «מחיקה», because the row is soft-deleted and its audit trail lives on.

## Depends On

- [[.planning/design/screens/owner-bookings/copy.md]] — the F15 source deck
- [[.planning/design/screens/manage-staff/copy.md]] — the F51 source deck

## Depended On By

- [[frontend/apps/manage/src/i18n/index.ts]]
- [[frontend/apps/manage/src/__tests__/i18n.test.ts]]

## Concepts

- [[RTL Bidi Isolation]]
- [[IS 5568 Accessibility]]

## Tests

- [[frontend/apps/manage/src/__tests__/i18n.test.ts]] — every key resolves; no exclamation marks; no delivery claims; per-feature key floors kept separate so one deck cannot shrink behind the other's count

## Notes

`nav.bookings` and `nav.staff` exist **only** as flat dotted keys — the nested `nav` object stops at `catalog`. [[frontend/apps/manage/src/App.tsx]] looks all seven up the same way (`t("nav.bookings")`), so this is invisible at the call site and works purely by `ignoreJSONStructure`. Both `document.title` and `console.title` hold the same string; the document title is actually set in [[frontend/apps/manage/index.html]], so the `document` namespace has no reader in the app today.
