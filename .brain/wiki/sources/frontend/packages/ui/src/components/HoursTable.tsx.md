---
tags: [frontend, ui, react, hours, israeli-week, bidi, storefront]
sources: [frontend/packages/ui/src/components/HoursTable.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/HoursTable.tsx
blob: b9a33d579a7b87d44dd1a37de8933fd02d36f19a
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/HoursTable.tsx

**Role.** Renders the whole Israeli week — Sunday-first, index 0 = Sunday through 6 = Saturday — as a two-column `<table>`, collapsing adjacent identical days into a single "א׳–ה׳" row and printing the caller's closed label for any day with no window. Every day is accounted for whether or not a rule exists for it, which is what makes a closed Saturday appear rather than silently vanish.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `HoursTable` | fn | `{rules, dayLabels, closedLabel, rangeSeparator?, className?}` |
| `HoursTableProps` | type | as above; `dayLabels` is a seven-element array indexed Sun→Sat, `rangeSeparator` defaults to `–` |

## Behavior

All grouping logic lives in `groupWeeklyRules` from [[frontend/packages/ui/src/lib/hours.ts]]; this file only renders. That helper walks days 0..6 and closes a row whenever the next day's window set differs, so collapsing requires days to be **both adjacent in the Sun-first week and window-identical** — Sun–Thu 10:00–19:00 with Friday short and Saturday absent yields three rows, and the absent Saturday becomes a `closed: true` row rather than being dropped.

Each row is a `<tr>` whose day cell is a `<th scope="row">` with `font-normal` — semantic row header for screen readers, visually plain. A day may carry **multiple windows** (F7 allows a lunch break), and each window is rendered as its own `<bdi dir="ltr">` separated by an inline-start margin, so a two-window day reads as two time ranges rather than one merged span.

The `dir="ltr"` on those `<bdi>` elements is correct precisely because the content is a **numeric run** (`10:00–19:00`) — digits and the separator must read left-to-right inside the RTL table. This is the opposite of the rule for Hebrew free text, which takes a bare `<bdi>`; forcing `dir="ltr"` on Hebrew is itself a bidi defect. `closedLabel` is Hebrew free text and is rendered **unwrapped**, which is the correct treatment for a run that is already RTL.

The component holds no Hebrew and no formatter: `dayLabels`, `closedLabel` and `rangeSeparator` are all props, and the underlying `lib/hours` module reads every date through a Jerusalem-zoned `Intl` formatter, never the device clock.

## Depends On

- [[frontend/packages/ui/src/lib/hours.ts]] — `groupWeeklyRules`, the `WeeklyRule` type
- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`

## Depended On By

- [[frontend/apps/storefront/src/components/HoursCard.tsx]] — the only app consumer; supplies the Hebrew day labels from [[frontend/apps/storefront/src/i18n/he.ts]]
- [[frontend/packages/ui/src/index.ts]] — barrel re-export

## Concepts

- [[RTL And Bidi Isolation]]

## Tests

- [[frontend/packages/ui/src/__tests__/hours-composites.test.tsx]] — asserts a Saturday closed row appears when the rules omit Saturday entirely
- [[frontend/packages/ui/src/__tests__/hours.test.ts]] — the grouping helper itself

## Notes

The date-window *exceptions* map (`Exceptions` in `lib/hours`) is not consumed here — this table renders the standing weekly rules only. Today's actual open/closed line comes from `todayHours` / `nextOpen`, rendered by [[frontend/apps/storefront/src/lib/hoursText.ts]] into the boutique header.
