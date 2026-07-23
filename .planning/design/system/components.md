# Component Inventory — `packages/ui` (F9 build scope)

**Created**: 2026-07-22 · **Consumers**: `apps/storefront` (F10), `apps/manage` (F7 restyle) · RTL-first: CSS logical properties only (`padding-inline-start`, `margin-inline-end`, `text-align: start`) — never `left/right` in component CSS.

Every component ships with: default / hover / focus-visible / disabled states, RTL-correct layout, keyboard operability, and Vitest coverage in the F9 build. States beyond that are listed per component.

## Core primitives

| Component | Variants / notes | Extra states |
|---|---|---|
| `Button` | primary (gold bg + ink text), secondary (ink outline), ghost, danger; sm/md/lg; full-width mobile option | loading (spinner replaces label, width locked) |
| `Input` / `TextArea` | label REQUIRED (never placeholder-as-label), help text, char counter (terms), `dir` override for phone/URL fields (LTR content in RTL form) | error (message tied via `aria-describedby`), disabled |
| `Select` | native `<select>` styled — no custom dropdown in v1 (a11y cost not worth it) | error, disabled |
| `Toggle` | for boolean settings (deposits, brides-only); label + description | disabled |
| `TimeField` / `DateField` | native inputs styled; Israeli week ordering handled at the composite level | error |
| `Badge` | status chips: neutral (ink-tint), gold (accent — large-text-safe `gold-strong`), success, danger | — |
| `Card` | surface `paper` bg, radius-md, shadow-sm; hover-elevate variant for interactive cards | — |
| `Toast` | success/error; auto-dismiss; `role="status"` / `role="alert"` | — |
| `Modal` | confirm dialogs (archive type, delete exception); focus-trapped, `Esc` closes, scale+fade motion | — |
| `Skeleton` | text lines, image blocks (3:4), card composites; pulse ≤1.5s, disabled under reduced-motion | — |
| `EmptyState` | icon-less by default (restraint) — headline + body + optional CTA; storefront variant with boutique identity | — |
| `SectionHeading` | display-serif heading + optional gold hairline ornament (decorative `gold` raw) | — |
| `VisuallyHidden`, `FocusRing utility`, `SkipLink` | a11y plumbing; skip-link mandatory on storefront | — |

## Storefront composites

| Component | Notes | States |
|---|---|---|
| `BoutiqueHeader` | name (display serif), essence line, hours-today snippet, location link; sits over catalog | closed-today |
| `DressCard` | 3:4 image (object-cover, cream matting on letterbox), name, `Price`, status badge only when meaningful; layout reserves a favorites-heart slot (feature wired in F10 — no-login localStorage) | image-missing (monogram placeholder), reserved |
| `DressGrid` | responsive: 2-col @375, 3-col @768, 4-col @1440; gap from spacing scale | loading (skeleton cards), empty |
| `Gallery` | swipe + dots on mobile, thumbnail rail on desktop; RTL swipe direction correct; pinch-zoom not in v1 | single-image (no chrome) |
| `Price` | THE only way to render money: "5,900 ₪" convention, numeric run `dir="ltr"` + `unicode-bidi: isolate`; visibility-aware — value in ink or "מחיר בתיאום" muted italic in the same layout slot, no jump | — |
| `HoursTable` | Sun–Thu / Fri / Sat rows, "סגור" explicit, exceptions ("שעות מיוחדות") inline with date | no-exceptions |
| `BookingCTA` | persistent bottom bar @mobile, inline @desktop; v1 action = contact panel (phone / WhatsApp deep-link) until E3 booking lands | — |
| `ContactPanel` | tap-to-call, WhatsApp (wa.me deep link — the culturally expected side door), address → **Waze + Google Maps** one-tap links (Waze is the Israeli standard), Instagram | — |
| `A11yStatementLink` | footer link to `/accessibility` (IS 5568 obligation) on every page | — |
| `A11yMenu` | **first-party** accessibility menu (never a third-party overlay): discreet fixed button bottom-left (RTL end), opens: contrast boost, text size, readable font, underlined links, stop animations. Hosts the statement link. Base experience passes AA with the menu untouched | open/closed |

## Manage composites (restyle of F7 — API/behavior frozen, visuals only)

| Component | Restyle notes |
|---|---|
| `ConsoleShell` | header (boutique name, logout), section nav (tabs @desktop, stacked @mobile), content column max-width for form readability |
| `SetupProgress` | first-run checklist "3/4 הושלמו" + next-step pointer; derived client-side from section data presence |
| `PolicyBlockerBanner` | shown while no terms version exists — danger-adjacent but not alarmist; links to the policy section |
| `LoginForm` | centered card on cream, display-serif heading, generic error (no enumeration — preserves F5 behavior) |
| `ProfileSection` / `HoursSection` / `TypesSection` / `TermsSection` | retokened: Card surfaces, Input/Toggle primitives, section headings, save buttons → `Button primary`; TermsSection history list gets the immutable-ledger look (version chip + date, no edit affordances) |

## Explicitly NOT in v1

Custom dropdowns/comboboxes · carousels beyond the dress gallery · data tables (nothing tabular yet) · charts · avatar/user-menu systems (owner-only) · dark theme (cream brand is single-theme; revisit if ever requested) · toast queues (one at a time).
