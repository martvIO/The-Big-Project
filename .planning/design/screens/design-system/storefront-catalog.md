# Screen: Storefront Catalog (`/`)

**Date**: 2026-07-22 · **Status**: rev 2 — Design Gate PASSED (round 2, design-critic ACCEPT); FINAL approval pending interview synthesis · **Layout**: single column, identity header over grid · **Consumes**: F7 profile/hours + F8 dresses (designed against F8's table shape)

## Wireframe (mobile 375 — primary)

```
+---------------------------------------+
| [skip-link (a11y, visually hidden)]   |
|                                       |
|          שם הבוטיק  (display serif)    |
|      משפט מהות אחד (muted)             |
|   היום: 10:00–19:00 · תל אביב ↗        |
|  ~~~~~~~ gold hairline ornament ~~~~~~ |
+---------------------------------------+
| [dress]  [dress]                      |
| [photo]  [photo]        2-col grid    |
|  שם       שם                          |
|  X,XXX ₪  מחיר בתיאום                  |
| [dress]  [dress]                      |
|   ...      ...                        |
+---------------------------------------+
| footer: הצהרת נגישות · אינסטגרם · טלפון |
+---------------------------------------+
| ▓▓▓▓▓  קביעת תור למדידה  ▓▓▓▓▓        |  <- persistent bottom CTA bar (gold bg, ink text)
+---------------------------------------+
```

## Components
`BoutiqueHeader` (name `--text-3xl` display, essence `--text-base` muted, hours-today + location from F7 data) · `DressGrid` of `DressCard` (3:4 photo, name `--text-lg`, `PriceTag`) · `BookingCTA` (bottom bar @mobile, inline in header @desktop) · `A11yStatementLink` · `SkipLink`.

## States

| State | What the user sees | Trigger |
|---|---|---|
| Default | header + grid | data present |
| Loading | header (cached/SSR) + 6 skeleton cards | initial fetch |
| **Empty (critical — live pre-F8)** | full-bleed identity moment: name, essence, hours, contact panel inline, CTA bar; "הקולקציה בדרך" line in muted — the storefront must feel complete with zero dresses | no dresses |
| Price-hidden mix | cards align: value and "מחיר בתיאום" occupy the same slot, same height — no layout jumps | per-dress flag |
| Reserved dress | `Badge` "הוזמן" top-inline-start on photo; card not dimmed (still browsable) | manual flag |
| Error | inline retry block under header, identity intact | fetch failure |

## Responsive
375: 2-col grid, gutter `--space-4`, bottom CTA bar · 768: 3-col, gutter `--space-6`, CTA moves into header row · 1440: 4-col, max-width 1200px centered, gutters `--space-12`.

## Notes
No hero carousel — the grid IS the hero. Photography variance is absorbed by fixed 3:4 crop + cream matting (`--color-surface` letterbox). Booking CTA v1 opens `ContactPanel` (phone/WhatsApp) until E3 replaces it with the real flow — same visual seam.
