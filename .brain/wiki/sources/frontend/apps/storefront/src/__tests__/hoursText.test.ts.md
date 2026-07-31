---
tags: [frontend, storefront, test, vitest, opening-hours, jerusalem, timezone]
sources: [frontend/apps/storefront/src/__tests__/hoursText.test.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/hoursText.test.ts
blob: e121eb810330d55c1766da7a223728a59b239dad
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/hoursText.test.ts

**Role.** The unit suite for the pure opening-hours text layer — date/time formatting, grouping the wire's per-window rows into per-day rules, folding exceptions into a lookup, and `todayLine()`, the single highest-stakes string on an appointment-only boutique's page.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `SUN_TO_THU` | fixture | the classic Israeli boutique week — five rows, Friday and Saturday carrying *no rule at all*, which the module reads as closed |
| `boutique(hours, exceptions)` | helper | a minimal `BoutiqueResponse` around the two fields under test |
| `THURSDAY` / `FRIDAY` / `SATURDAY_IN_JERUSALEM_FRIDAY_IN_NEW_YORK` | fixture | pinned instants; the third is the one that tells the two clocks apart |
| `shortDate` / `hhmm` | suite | `d.m` with leading zeros dropped; the wire's seconds trimmed |
| `toWeeklyRules` | suite | two windows on one day become one rule with two windows |
| `toExceptions` | suite | a closed day is a **present key with an empty array**, not an absent key |
| `todayLine` | suite | eight cases: open, closed-today + tomorrow, closed-today + named weekday, no rules at all, and both directions of exception override |

## Behavior

The whole module is pure, so every branch is reachable with a pinned `Date` and no DOM. What makes the assertions *mean* something is the `TZ=America/New_York` pin in [[frontend/apps/storefront/package.json]]'s test script — every case therefore also proves the calculation reads Asia/Jerusalem rather than the device clock. `2026-12-25T22:30:00Z` is still Friday the 25th in New York but already Saturday the 26th in Jerusalem; a device-clock read gets that case wrong and only that case makes it visible.

`shortDate` is asserted as day-**dot**-month explicitly, because `25.12` vs `12.25` is exactly the ambiguity that would ship silently through a review.

`toWeeklyRules` is tested with `day_of_week: 0` appearing twice, since the wire ships one row per *window* and a lunch break is two rows for one day — a naive one-to-one map keeps only the afternoon and silently hides the morning the boutique is open. `toExceptions` pins the corresponding subtlety on the other side: a closed-all-day exception must produce a key mapped to `[]`, because an **absent** key means "no exception" and falls back to the weekly rule, which would reopen a day the owner closed.

`todayLine`'s cases walk the reopen search, and the two exception cases run in both directions — a closed exception hides an otherwise-open weekday (and the reopen walks *past* Friday to Sunday rather than stopping at the next calendar day), and a special-hours exception opens an otherwise-closed one (Friday reads `09:00–13:00`). One case pins a closed exception on the reopen *target*: Sunday closed by exception pushes Friday's reopen to Monday, the branch an "always the next weekly rule" shortcut gets wrong.

**The no-rules case returns `null`, not "closed today."** That is the state every newly provisioned tenant ships in, and rendering סגור היום there advertises a closure the owner never entered.

## Depends On

- [[frontend/apps/storefront/src/lib/hoursText.ts]] — the subject
- [[frontend/apps/storefront/src/api.ts]] — `BoutiqueResponse`, `HoursRow`, `ExceptionRow` wire types
- [[frontend/apps/storefront/src/i18n/index.ts]] — expected strings built through `t()` and the `hours.days` label array
- [[Vitest]]

## Depended On By

Nothing imports a test file. The rendered counterpart is [[frontend/apps/storefront/src/routes/AboutPage.tsx]] via [[frontend/apps/storefront/src/__tests__/AboutPage.test.tsx]], which asserts the line appears rather than how it is computed.

## Concepts

- [[Jerusalem Time]]

## Notes

Expected values are composed through `t("about.today", {hours: "…"})` rather than hardcoded Hebrew, so a copy edit does not break the suite while a *logic* change does. [[frontend/scripts/qa-greps.sh]] mechanically bans an unzoned "today" read; this file is the behavioral half of the same rule — and if the `TZ=` pin is ever dropped from the package script, the suite keeps passing while guarding much less, so treat the pin as part of the test.
