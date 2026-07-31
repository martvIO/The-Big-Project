---
tags: [frontend, ui, test, vitest, hours, timezone, jerusalem]
sources: [frontend/packages/ui/src/__tests__/hours.test.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/__tests__/hours.test.ts
blob: 2d32982c762c6c66c1f5d31ec192f1099971be12
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/__tests__/hours.test.ts

**Role.** The pure-function suite for the opening-hours engine in [[frontend/packages/ui/src/lib/hours.ts]] — week grouping, the Jerusalem day index, "next open day", and today's windows. No DOM, no React; the whole file is arithmetic over an Israeli Sun-first week and an explicit timezone.

**Module.** [[frontend/packages/ui/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `describe("groupWeeklyRules")` | suite | the binding qa §6 fixture: adjacent-identical collapse, every day present, no run spans a gap |
| `describe("jerusalemDayIndex")` | suite | the day index flips at Jerusalem midnight, not the device's |
| `describe("nextOpen")` | suite | `isTomorrow` is literal, `daysAhead` counts real days, `null` when never open |
| `describe("todayHours")` | suite | a day with no rule is closed with empty windows |
| `w(open, close)` | helper | terse `TimeWindow` constructor |

## Behavior

**The `groupWeeklyRules` case asserts the entire returned array with `toEqual`, not a property of it.** The fixture (Sun/Mon and Wed/Thu at 10–19, Tue closed, Fri 09–13, Sat absent) is called *binding* in the source comment because it is the smallest input that separates three different wrong implementations: one that groups by identical windows regardless of adjacency, one that drops days with no rule, and one that emits a `Sun–Thu` run straight through the closed Tuesday. The final assertion — that no row has `startDay === 0 && endDay === 4` — names that third failure explicitly, so a regression reads as "collapsed across a gap" rather than as an opaque array diff. A second case pins the standing Saturday case on its own: one Sunday rule in, and the row covering day 6 must come back `closed: true`.

**The `jerusalemDayIndex` case is the reason the package's test script sets `TZ=America/New_York`** (see [[frontend/packages/ui/package.json]]). It picks two instants an hour apart — `2026-07-24T20:30Z` and `21:30Z`, i.e. 23:30 and 00:30 IDT — and asserts the second index is exactly one day after the first, mod 7. Under a device clock the two instants are the *same* New York afternoon, so a `getDay()`-based implementation returns the same index twice and fails here. It asserts the *relationship* rather than a literal index, which keeps the test honest without hardcoding a weekday.

`nextOpen` is checked on the distinction that its own field name invites getting wrong: `isTomorrow` must be true only when the next open day is literally the next calendar day. The suite derives `tomorrow` and `dayAfter` from `jerusalemDayIndex(now)` rather than writing weekday numbers, so the cases stay correct whatever date the fixture instant lands on. When only the day-after is open, `isTomorrow` is false, `daysAhead` is 2, and `dayIndex` names the real day — the copy a storefront renders ("נפתח ביום ג׳") depends on all three. The empty-rules case pins the `null` return, which is what stops the header from claiming the boutique reopens at some phantom time.

`todayHours` gets the negative case only: a rule set that mentions some *other* day must return `closed: true` with `windows: []`, never the first rule in the list. The exceptions-override path (`Exceptions` keyed by Jerusalem ISO date) that `todayHours` and `nextOpen` both accept is **not** covered here.

## Depends On

- [[frontend/packages/ui/src/lib/hours.ts]] — subject (`groupWeeklyRules`, `jerusalemDayIndex`, `nextOpen`, `todayHours`, `WeeklyRule`)
- [[Vitest]]

## Depended On By

Nothing imports a test file.

## Concepts

- [[Jerusalem Time]]

## Tests

This is the test. The rendering side is [[frontend/packages/ui/src/__tests__/hours-composites.test.tsx]].

## Notes

Two real gaps: the `exceptions` argument (closed-for-a-date and special-hours-for-a-date) is untested on both `todayHours` and `nextOpen`, and so is the DST-safe noon-UTC anchoring inside `addDays` — the helper's stated reason for existing. A DST-crossing `nextOpen` fixture would be the highest-value addition.

The exported constant in the module is spelled `JERusalem`, with the odd capitalisation carried into the source; it is the timezone default, not a typo to "fix" in a page.
