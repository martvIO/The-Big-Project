# Screen: Boutique Profile & Hours (`/about`)

**Date**: 2026-07-22 · **Status**: rev 2 — Design Gate PASSED (round 2, design-critic ACCEPT); FINAL approval pending interview synthesis · **Layout**: centered editorial column (max 640px) · **Purpose**: the trust surface (Flow S3) — answers "אמיתי? שווה ביקור? מתי פתוח?"

## Wireframe

```
+------------------------------------+
|        שם הבוטיק (display)          |
|   ~~~~~~ gold hairline ~~~~~~      |
|  סיפור הבוטיק — פסקה או שתיים       |
|  (body, muted-warm, generous       |
|   line-height 1.6)                 |
|                                    |
|  ┌──────── Card (paper) ────────┐  |
|  │ שעות פעילות                   │  |
|  │ א׳–ה׳     10:00–19:00         │  |
|  │ ו׳        09:00–13:00         │  |
|  │ שבת       סגור                │  |
|  │ ◆ שעות מיוחדות: 14.4 סגור     │  |
|  └──────────────────────────────┘  |
|                                    |
|  ┌──────── Card ────────┐          |
|  │ 052-1234567  [חיוג]  │          |
|  │ [WhatsApp]           │          |
|  │ רח׳ דיזנגוף 99, ת״א ↗ │          |
|  │ [אינסטגרם]           │          |
|  └──────────────────────┘          |
|                                    |
|  ▓▓▓ קביעת תור למדידה ▓▓▓          |
+------------------------------------+
```

## Components
`SectionHeading` · story text (from F7 `profile.description`) · `HoursTable` (weekly rules collapsed to ranges; days with no window = "סגור"; upcoming exceptions listed with dates, `gold-strong` diamond marker + text — never color alone) · `ContactPanel` (tap-to-call, WhatsApp wa.me deep link, **Waze + Google Maps** one-tap navigation from `maps_url`/address — Waze is the Israeli standard, Instagram) · `BookingCTA`.

## States

| State | Seen | Trigger |
|---|---|---|
| Default | all cards | — |
| Closed today | hours card leads with "סגור היום · נפתח מחר ב-10:00" line in ink (not danger — closed isn't an error) | day check |
| No exceptions | exceptions row absent (no empty "none" line) | — |
| Sparse profile | missing description/social rows collapse; hours + contact always render (owner may not have written a story yet) | partial F7 data |
| No maps_url | address as plain text, no link | — |

## Responsive
375: single column, cards full-width · 768+: same column, max 640px centered (editorial page — never goes multi-column).

## Notes
Hours grouping logic (identical consecutive days → "א׳–ה׳") is presentational, computed from F7 `availability_rules`. Phone renders `dir="ltr"`. This surface must work as a **section of `/`** too (v1 may fold it into the catalog page footer-section on small tenants — decided in F10 build; design supports both).
