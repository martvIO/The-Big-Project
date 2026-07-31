---
tags: [backend, frontend, time, booking, design]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Jerusalem Time

**What it is.** Storage and the wire are UTC. The **boutique's calendar is `Asia/Jerusalem`**, and
every place a date or a wall-clock time is derived, that zone is passed explicitly. A bare
`new Date().getDay()` reads the *device* clock, which is a different calendar day from Jerusalem
for part of every day.

## One constant per side, imported never restated

- Backend: `BOUTIQUE_TIMEZONE = ZoneInfo("Asia/Jerusalem")` declared once in
  [[backend/app/storefront/validation.py]] and **imported** by
  [[backend/app/booking/validation.py]] — its docstring: *two zone constants is one zone constant
  too many*.
- Frontend: `JERusalem` exported from [[frontend/packages/ui/src/lib/hours.ts]] and imported by
  [[frontend/apps/manage/src/lib/jerusalem.ts]]. Every `Intl.DateTimeFormat` in that file passes
  `timeZone`.

## Two spellings of "the same day", on purpose

[[frontend/apps/manage/src/lib/jerusalem.ts]] exports both, and they are not interchangeable:

- `jerusalemDate` → `d.m.yyyy`, unpadded — the spelling
  [[backend/app/booking/comms_templates.py]] already texts the bride, so the owner reads one date
  format across the product;
- `jerusalemIsoDate` → `YYYY-MM-DD` — what `<input type="date">` and the API's `?date=` both take.

`todayJerusalem()` goes through the zoned formatter like everything else rather than reading the
device clock.

## The mechanical guard

[[frontend/scripts/qa-greps.sh]] flags every `getDay()`, `getDate()`, `toLocaleDateString`,
`toLocaleTimeString` and every single-line `Intl.DateTimeFormat(...)` without `timeZone`, across
all three frontend packages, for review. Its comment block is worth reading before "improving" it:
the spec's PCRE-lookahead version of that grep would abort under `grep -E`, the error would be
swallowed by `|| true`, and the whole block would print `ok` while checking nothing.

## Traps

- **Tests must pin a non-UTC device zone.** [[frontend/apps/manage/src/__tests__/jerusalem.test.ts]]
  runs the suite against New York, because on a UTC runner an unzoned read agrees with Jerusalem
  for most of the day and the bug ships anyway.
- **Noon-UTC anchoring.** `addDays` in [[frontend/packages/ui/src/lib/hours.ts]] steps day-to-day
  from noon UTC (≈14:00–15:00 Jerusalem, never near midnight) so the calendar day stays stable
  across DST.
- **Elapsed time is not calendar time.** Rate-limit windows take a *monotonic* clock
  ([[backend/app/auth/rate_limit.py]]); expiries take a UTC `WallClock`
  ([[backend/app/notifications/service.py]]). Conflating them is how DST bugs are born.
- **The bookable horizon carries a two-day pad** — [[backend/app/booking/service.py]]'s
  `BOOKABLE_HORIZON` is `SLOT_WINDOW_MAX_DAYS + 2`, because a naive `+1` ate the last half-hour of
  the final day's grid when the offset shifted.

## Related

- [[Hebrew First UX]] — Israeli week, Sun–Thu
- [[backend/app/booking/slots.py]] · [[backend/app/booking/owner.py]] ·
  [[frontend/apps/manage/src/components/BookingsSection.tsx]]
- [[frontend/packages/ui/src/__tests__/hours.test.ts]]
