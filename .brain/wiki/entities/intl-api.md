---
tags: [frontend, dates, timezone, formatting, hebrew]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Intl API

**Purpose.** The platform's built-in `Intl.DateTimeFormat` / `Intl.NumberFormat` is the *only* date, time and money formatting in the frontend. There is no `date-fns`, no `dayjs`, no `luxon` — check `frontend/pnpm-lock.yaml`.

**Every formatter that reads a booking instant must pass `timeZone: JERusalem`.** That constant is `"Asia/Jerusalem"`, exported once from [[frontend/packages/ui/src/lib/hours.ts]] and re-exported through [[frontend/packages/ui/src/index.ts]]; it is never re-declared. The zoned formatters live in [[frontend/apps/manage/src/lib/jerusalem.ts]], [[frontend/apps/storefront/src/routes/BookPage.tsx]] and [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]]. **A bare `new Date()` read of "today" is a bug**: for part of every day the device's calendar day is not the boutique's, and a booking belongs to the boutique's day — hence `todayJerusalem()` rather than a local-clock date. See [[Jerusalem Time]].

Formatters build with `formatToParts`, not `format`, wherever the output feeds `<input type="date">` or the API's `?date=` — the human `d.m.yyyy` spelling and the ISO one are separate exported functions on purpose.

Money is `Intl.NumberFormat("he-IL")` inside [[frontend/packages/ui/src/components/Price.tsx]] and nowhere else, wrapped in `<bdi dir="ltr">` so digits and `₪` read correctly inside RTL text; [[frontend/scripts/qa-greps.sh]] hard-fails on a `₪` anywhere in storefront source.

**The trap: the unzoned-formatter check is warning-only.** That same script prints `review` for bare `Intl.DateTimeFormat(...)` constructions but never sets its exit status, and two live call sites are printed on every run — `formatDate` in [[frontend/apps/manage/src/components/HoursSection.tsx]] and in [[frontend/apps/manage/src/components/TermsSection.tsx]]. The Terms one formats a **server UTC instant** in the device zone. What actually catches this class of bug is [[Vitest]]: every frontend `test` script pins `TZ=America/New_York`.
