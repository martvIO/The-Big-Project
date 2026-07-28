# Screen: Manage Console Restyle (F7 components, `/manage`)

**Date**: 2026-07-22 · **Status**: rev 2 — Design Gate PASSED (round 2, design-critic ACCEPT); FINAL approval pending interview synthesis · **Constraint**: component APIs/behavior/tests from F7 are frozen — this respec's the visual layer only (tokens, spacing, type, state visuals).

## Console shell

```
+----------------------------------------------------+
| שם הבוטיק (display serif sm)          [יציאה]       |
+----------------------------------------------------+
| [ פרופיל ] [ שעות ] [ סוגי תורים ] [ מדיניות ] [ שמלות ] |   <- 5 nav items @desktop (active: gold-strong underline
+----------------------------------------------------+        + aria-current="page"). stacked full-width nav @mobile.
                                                          Fifth tab "שמלות" (route key `catalog`) is F8's catalog;
                                                          it does NOT join SetupProgress (setup = booking prereqs).
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
| `ProfileSection` | two-group form (פרופיל / הגדרות); toggles with description lines; maps_url and instagram fields `dir="ltr"`. **A public-visibility helper line sits directly under the FIRST (פרופיל) heading — "השדות האלה מופיעים בדף הפומבי של הבוטיק" — in muted ink, not a warning colour.** Placement is load-bearing: F10 is the PR that makes `phone`, `address`, `description` and `maps_url` world-readable for the first time, and a home-based boutique's owner typed her home address into a field that had only ever been private. It must cover those four existing fields, not just the two F10 added (`essence`, `instagram`); it must NOT sit under the הגדרות heading, since toggles are not published. |
| `HoursSection` | weekly editor as a Sun-first grid; windows as rows with TimeFields; capacity as a small numeric field with "מקבילים" label; exceptions list — date + closed/special chips, danger-ghost remove buttons; validation errors inline per row (house error message under the row) |
| `TypesSection` | type cards in a list (name display-serif sm, duration/audience/deposit as muted meta line); archive = ghost-danger with confirm Modal; agorot fields render ₪ presentation with `dir="ltr"` digits |
| `TermsSection` | **immutable-ledger look**: create-form card on top (terms textarea + structured fields with explicit units "שעות לפני התור", "% חילוט"), history below as version rows — `Badge` "גרסה N" + created date + created-by, NO edit affordance anywhere; latest row marked "בתוקף" (gold-text) |
| `CatalogSection` (F8) | dress list: search `Input` (`dir` neutral), sort-order control, "הוספת שמלה" primary Button, dress rows as `Card`s with name (display-serif sm), `Price`, status `Badge` (`muted` "במלאי (N)" / `warning` "אזל מהמלאי" / `muted` "בארכיון"); archive = ghost-danger + confirm `Modal`. Restyle only — F8 API/behavior/tests frozen |
| `DressEditor` (F8) | edit form in a `Card`: name/description/price `Input`s (price ₪ adornment + `dir="ltr"` digits), price-visibility `Toggle`, status controls, `VariantMatrix` + `MediaGallery` embedded; save Button loading + "נשמר לפני רגע" cue |
| `VariantMatrix` (F8) | size × quantity grid; unlisted-size chips (`muted` Badge), quantity stepper `Input`s (`dir="ltr"`), at-cap counter (`warning` Badge); `text-align: end` on numeric columns |
| `MediaGallery` (F8) | image thumbnails (3:4, cream matting, shadow-sm), presigned-upload file input, reorder + delete-per-photo behind a confirm `Modal`; storage-disabled 503 notice as a `muted`/info panel |
| `shared.tsx` primitives | **deleted** (not retokened) — all sections import Button/Input/TextArea/Card/Toast from `packages/ui` during the F9 build |

## Navigation semantics (ConsoleShell)

Contract **(b) plain nav**, not ARIA tabs: the shell nav is a `<nav>` of buttons that swap the single `#console-main` content panel, so each carries `aria-current="page"` when active and `aria-controls="console-main"` (the `gold-strong` underline is never the *only* active signal — `aria-current` + `font-semibold` also mark it). **No `role="tab"`** anywhere — a `role="tab"` without the full roving-tabindex/Arrow-key keyboard contract is a defect. At ≤767px the nav **stacks full-width** and at ≥768px it is a horizontal tab row; one section's content shows at a time. It is a panel-swapping nav, **not a disclosure accordion** — such a nav correctly uses `aria-current`/`aria-controls`, not `aria-expanded` (putting `aria-expanded` on nav items is an ARIA anti-pattern). Logout is a `<button>` with a text name. The console has a single `h1` (the console/boutique title); each section heading is a lower level, no skipped levels.

## States (console-wide)

| State | Seen |
|---|---|
| First-run | SetupProgress card + PolicyBlockerBanner; sections show empty-form defaults |
| Steady | no progress card; banner only while no terms version |
| Saving | Button loading state (width locked), inputs disabled |
| Save success | inline "נשמר לפני רגע" cue in the save row (`--text-xs`, `--color-ink-muted`), inline-start of the primary Button — **not** a Toast; Button returns from loading at unchanged width |
| Save error | Toast danger with backend message (house error shape already extracted by F7 `api.ts`) + field-level inline errors |
| Catalog empty | `שמלות` section with no dresses renders an `EmptyState` (headline + "הוספת שמלה" CTA), not a blank column |
| Storage disabled | no S3 bucket configured → media write endpoints answer 503; `MediaGallery` shows a `muted`/info panel explaining uploads are unavailable, and the rest of the catalog stays fully usable |
| Session expired | redirected by existing 401 handling to LoginForm — visual continuity (same shell header) |

## Responsive
375: nav stacks full-width (one section's content shown at a time), forms full-width, save buttons full-width · 768: horizontal tab row appears, content max 720px · 1440: identical (console never exceeds 720px content — form readability).

## Notes
The console shares tokens with the storefront but drops the ornament level (no hairline flourishes on forms) — luxury restraint reads as calm competence here. Contrast/focus/labels identical to storefront laws. RTL logical properties throughout; the only LTR islands are phone/URL/money digit fields.
