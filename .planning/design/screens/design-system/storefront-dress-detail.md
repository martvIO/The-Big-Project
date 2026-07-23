# Screen: Dress Detail (`/dress/{id}`)

**Date**: 2026-07-22 · **Status**: rev 1 — critic-gated, pending interview synthesis · **Layout**: gallery-dominant; single column @mobile, 60/40 split @desktop

## Wireframe (mobile / desktop)

```
mobile 375:                          desktop 1440 (max 1200 centered):
+--------------------+               +---------------------------+----------------+
| ← חזרה לקולקציה     |               | [thumb]  [ MAIN PHOTO ]   |  שם השמלה       |
| [  MAIN  PHOTO  ]  |               | [thumb]  [    3:4     ]   |  ₪X,XXX         |
| [   3:4 swipe   ]  |               | [thumb]                   |  ~ hairline ~   |
|  • • ○ ○           |               |                           |  תיאור...        |
|  שם השמלה (serif)   |               |                           |  מידות: 36 38 40 |
|  ₪X,XXX            |               |                           |                 |
|  ~~ hairline ~~    |               |                           |  [קביעת תור]     |
|  תיאור ...          |               |                           |  [שיתוף ↗]      |
|  מידות: 36 38 40 42 |               +---------------------------+----------------+
+--------------------+
| ▓▓ קביעת תור למדידה ▓▓ |  <- bottom bar
+--------------------+
```

## Components
`Gallery` (RTL-correct swipe, dots @mobile, thumbnail rail inline-start @desktop) · dress name `--text-2xl` display · `PriceTag` · description body clamped at 6 lines + "עוד" expander · size chips (`Badge` neutral — informational, not selectable; availability shown, selection happens at the fitting) · `BookingCTA` · share (native share sheet) · breadcrumb back-link.

## States

| State | What the user sees | Trigger |
|---|---|---|
| Default | full layout | — |
| Loading | gallery skeleton (3:4) + text lines | fetch |
| Single photo | gallery chrome (dots/thumbs) hidden entirely | 1 image |
| No photo | monogram placeholder art (boutique initial in display serif on paper, gold hairline frame) — dignified, never a broken-image glyph | 0 images |
| Price hidden | "מחיר בתיאום" muted italic in the price slot | flag |
| Reserved | "הוזמן" badge beside name; CTA remains (booking a fitting for a reserved dress is a boutique conversation, not a hard block) | manual flag |
| Archived / bad id | "השמלה כבר לא זמינה" + CTA back to catalog (storefront 404-within-tenant) | soft-deleted id |
| Long description | 6-line clamp + expander | length |

## Responsive
375: single column, bottom CTA bar, swipe gallery · 768: two-column starts (55/45), thumbs appear · 1440: 60/40, sticky facts column while gallery scrolls.

## Notes
No zoom/lightbox in v1 (a11y + scope); full-bleed tap opens the image native-size. Share uses the Web Share API with graceful copy-link fallback. `dir="ltr"` spans for any Latin dress names.
