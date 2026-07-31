---
tags: [frontend, storefront, react, hours, jerusalem-time]
sources: [frontend/apps/storefront/src/components/HoursCard.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/components/HoursCard.tsx
blob: 4d8533fb986a74776d33431d8913e6cb3eab8995
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/components/HoursCard.tsx

**Role.** `HoursTable` plus the two things the shared primitive deliberately does not own: the composed "today" lead line above it, and the upcoming-exceptions list beneath it.

**Module.** [[frontend/apps/storefront/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `HoursCard` | component | `{boutique, now?, className?}` — the whole hours block on paper |
| `HoursCardProps` | interface | |

## Behavior

`now` defaults to `new Date()` but is injectable so a test can pin a weekday without faking the machine clock — the hours arithmetic itself is timezone-explicit (`Asia/Jerusalem`) inside [[frontend/apps/storefront/src/lib/hoursText.ts]], never the device zone. `todayLine()` returns `null` when the boutique has **no weekly rules at all**, which is not the same state as being closed today; that null falls back to `about.hoursUnavailable`. The closed-today line renders in plain `text-ink`, never the danger colour — being closed is not an error.

Weekly rows go through `toWeeklyRules(boutique.hours)` because the wire ships **one row per window, not per day** (F7 allows a lunch break, and the repository orders by `(day_of_week, open_time)`); the day labels come from `t("hours.days", { returnObjects: true })` as a `string[]`.

The exceptions list is this component's own. Each row is closed-all-day when either time is `null`, otherwise special hours; the date goes through `shortDate` and the times through `hhmm`, and an optional `note` is appended after a `·`. Every row is prefixed with an `aria-hidden` `◆` **and** the `about.exceptionsLabel` text — an exception is never signalled by colour or glyph alone (WCAG 1.4.1). The list is omitted entirely when `exceptions` is empty rather than rendering an empty `<ul>`.

## Depends On

- [[frontend/apps/storefront/src/lib/hoursText.ts]] — `todayLine`, `toWeeklyRules`, `shortDate`, `hhmm`
- [[frontend/packages/ui/src/components/HoursTable.tsx]] · [[frontend/packages/ui/src/components/Card.tsx]] · [[frontend/packages/ui/src/components/SectionHeading.tsx]]
- [[frontend/apps/storefront/src/api.ts]] — `BoutiqueResponse` type only
- [[i18next]]

## Depended On By

- [[frontend/apps/storefront/src/routes/AboutPage.tsx]]
- [[frontend/apps/storefront/src/routes/CatalogPage.tsx]] — inside the empty-catalog state

## Concepts

- [[Jerusalem Time]]
- [[RTL And Bidi Isolation]]
- [[Accessibility Compliance]]

## Tests

- [[frontend/apps/storefront/src/__tests__/AboutPage.test.tsx]] · [[frontend/apps/storefront/src/__tests__/CatalogPage.test.tsx]]
- [[frontend/apps/storefront/src/__tests__/hoursText.test.ts]] — the underlying derivations
- [[frontend/packages/ui/src/__tests__/hours-composites.test.tsx]] — the table primitive

## Notes

The catalog also calls `todayLine` directly for its `BoutiqueHeader` one-liner, so the same function feeds two different presentations; keep them consistent by changing `hoursText.ts`, not either call site.
