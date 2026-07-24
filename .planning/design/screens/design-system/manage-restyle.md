# Screen: Manage Console Restyle (F7 components, `/manage`)

**Date**: 2026-07-22 · **Status**: rev 2 — Design Gate PASSED (round 2, design-critic ACCEPT); FINAL approval pending interview synthesis · **Constraint**: component APIs/behavior/tests from F7 are frozen — this respec's the visual layer only (tokens, spacing, type, state visuals).

## Console shell

```
+----------------------------------------------------+
| שם הבוטיק (display serif sm)          [יציאה]       |
+----------------------------------------------------+
| [ פרופיל ] [ שעות ] [ סוגי תורים ] [ מדיניות ]       |   <- tabs @desktop (active: gold-strong underline)
+----------------------------------------------------+     stacked accordion @mobile
| אין עדיין מדיניות ביטולים — נדרשת לפני קבלת         |   <- PolicyBlockerBanner (warning-text on paper,
|   הזמנות. [ליצירת מדיניות ←]                        |      gold-strong border-stripe + text, no icon —
|                                                     |      intentional restraint; not red: cautionary)
+----------------------------------------------------+
| ┌── Card: הגדרה ראשונית 3/4 ─────────────────┐      |   <- SetupProgress (first-run only)
| │ ✓ פרופיל  ✓ שעות  ✓ סוגי תורים  ○ מדיניות │      |
| └────────────────────────────────────────────┘      |
|                                                     |
| ┌── Card (paper, space-6 padding, max 720px) ─┐     |
| │  [section form — Input/Toggle primitives,   │     |
| │   labels above fields, save Button primary   │     |
| │   inline-end, "נשמר לפני רגע" muted cue]     │     |
| └─────────────────────────────────────────────┘     |
+----------------------------------------------------+
```

## Per-component restyle notes

| Component | Restyle |
|---|---|
| `LoginForm` | centered Card on cream, boutique-platform wordmark in display serif, generic error preserved verbatim (F5 anti-enumeration), focus rings per tokens |
| `ProfileSection` | two-group form (פרופיל / הגדרות); toggles with description lines; maps_url field `dir="ltr"` |
| `HoursSection` | weekly editor as a Sun-first grid; windows as rows with TimeFields; capacity as a small numeric field with "מקבילים" label; exceptions list — date + closed/special chips, danger-ghost remove buttons; validation errors inline per row (house error message under the row) |
| `TypesSection` | type cards in a list (name display-serif sm, duration/audience/deposit as muted meta line); archive = ghost-danger with confirm Modal; agorot fields render ₪ presentation with `dir="ltr"` digits |
| `TermsSection` | **immutable-ledger look**: create-form card on top (terms textarea + structured fields with explicit units "שעות לפני התור", "% חילוט"), history below as version rows — `Badge` "גרסה N" + created date + created-by, NO edit affordance anywhere; latest row marked "בתוקף" (gold-text) |
| `shared.tsx` primitives | swap to `packages/ui` primitives (Button/Input/Card/Toast) during the F9 build |

## States (console-wide)

| State | Seen |
|---|---|
| First-run | SetupProgress card + PolicyBlockerBanner; sections show empty-form defaults |
| Steady | no progress card; banner only while no terms version |
| Saving | Button loading state (width locked), inputs disabled |
| Save error | Toast danger with backend message (house error shape already extracted by F7 `api.ts`) + field-level inline errors |
| Session expired | redirected by existing 401 handling to LoginForm — visual continuity (same shell header) |

## Responsive
375: tabs → stacked sections (accordion, one open), forms full-width, save buttons full-width · 768: tabs appear, content max 720px · 1440: identical (console never exceeds 720px content — form readability).

## Notes
The console shares tokens with the storefront but drops the ornament level (no hairline flourishes on forms) — luxury restraint reads as calm competence here. Contrast/focus/labels identical to storefront laws. RTL logical properties throughout; the only LTR islands are phone/URL/money digit fields.
