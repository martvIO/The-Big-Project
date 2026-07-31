---
tags: [frontend, manage, test, vitest, timezone, jerusalem]
sources: [frontend/apps/manage/src/__tests__/jerusalem.test.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/__tests__/jerusalem.test.ts
blob: a33261d18edc383898ed7806755c2dbcbf201384
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/apps/manage/src/__tests__/jerusalem.test.ts

**Role.** The unit suite that pins the console's three Jerusalem-zoned date helpers to the *boutique's* calendar rather than the device's — the smallest file in the batch and the one every other date assertion in the console leans on.

**Module.** [[frontend/apps/manage/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `jerusalemDate / jerusalemTime` | suite | `d.m.yyyy` unpadded day/month, `HH:MM` zero-padded 24h, both read in Asia/Jerusalem |
| `todayJerusalem` | suite | the ISO date an `<input type="date">` wants, taken from the Jerusalem calendar |

## Behavior

The suite's whole load-bearing property is stated in its header comment: these assertions only *mean* anything because `apps/manage`'s `test` script pins `TZ=America/New_York` ([[frontend/apps/manage/package.json]]), the same deliberately-wrong zone the storefront and `packages/ui` pin. On a UTC runner an unzoned `new Date()` read agrees with Jerusalem for most of the day, so a device-clock bug would pass green — the wrong zone is what makes the test able to fail.

Two fixtures carry the argument. `2026-08-04T07:00:00Z` is 10:00 Jerusalem and 03:00 New York, so it catches a wall-clock error. `2026-08-04T21:30:00Z` is 00:30 on the **5th** in Jerusalem and 17:30 on the **4th** in New York, so it catches a *calendar-day* error — the one that silently files a booking under yesterday. `todayJerusalem` is exercised through `vi.useFakeTimers()` + `vi.setSystemTime`, with `vi.useRealTimers()` in `afterEach` so the fake clock cannot leak into a sibling file.

The formatting assertions are specific on purpose: day and month are **unpadded** (`4.8.2026`, matching the SMS deck) while the hour **is** padded (`07:05`), and the clock stays 24h past noon (`19:00`).

## Depends On

- [[frontend/apps/manage/src/lib/jerusalem.ts]] — the subject
- [[Vitest]] — `vi.useFakeTimers`, `vi.setSystemTime`

## Depended On By

Nothing imports a test file. Its guarantee is consumed by every suite that asserts a rendered time — [[frontend/apps/manage/src/__tests__/BookingsSection.test.tsx]] and [[frontend/apps/manage/src/__tests__/BookingDetail.test.tsx]] both restate the 07:00Z → 10:00 fixture in their own comments.

## Concepts

- [[Jerusalem Time]]

## Notes

[[frontend/scripts/qa-greps.sh]] mechanically bans an unzoned "today" read; this suite is the behavioral half of the same rule. If the `TZ=` pin is ever dropped from the package script, the file keeps passing while guarding nothing — treat the pin as part of the test.
