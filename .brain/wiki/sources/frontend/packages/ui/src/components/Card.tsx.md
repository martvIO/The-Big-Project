---
tags: [frontend, ui, react, primitive, layout]
sources: [frontend/packages/ui/src/components/Card.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/Card.tsx
blob: 48d672bf8a3216dd5a01918076bab58be90ef931
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/Card.tsx

**Role.** The paper surface every console section and storefront panel sits on: a `<div>` with `rounded-md bg-surface p-6 shadow-sm`, plus one opt-in `hoverElevate` flag. It is the single most-reused primitive in the package.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Card` | component | `{hoverElevate = false, className, ...HTMLAttributes<HTMLDivElement>}` — spreads rest onto the div, renders no children element of its own |
| `CardProps` | interface | |

## Behavior

Deliberately minimal. It takes no children prop explicitly — children flow through the spread — and it forwards **no ref**, so it cannot be a focus or scroll target; a caller needing that wraps it or uses a plain element. `hoverElevate` adds `transition-shadow hover:shadow-md` and is opt-in because a card that lifts on hover reads as clickable; a non-interactive card must not.

The `p-6` and `bg-surface` are the reason so many consumers pass `className` for layout only (`flex flex-col gap-3`, a width, a margin) — those add properties rather than fighting the card's own, which is the only kind of override that reliably works here: `cn()` is a plain join with **no class-merge**, so a call-site `p-4` and the base `p-6` are the same specificity and resolve by stylesheet order, not by argument order. Do not treat a padding override as supported.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`
- [[React]] — `HTMLAttributes`

## Depended On By

- [[frontend/packages/ui/src/index.ts]]
- [[frontend/packages/ui/src/components/DressCard.tsx]], [[frontend/packages/ui/src/components/SetupProgress.tsx]]
- Manage console: [[frontend/apps/manage/src/components/BookingDetail.tsx]], [[frontend/apps/manage/src/components/BookingsSection.tsx]], [[frontend/apps/manage/src/components/CatalogSection.tsx]], [[frontend/apps/manage/src/components/DressEditor.tsx]], [[frontend/apps/manage/src/components/HoursSection.tsx]], [[frontend/apps/manage/src/components/LoginForm.tsx]], [[frontend/apps/manage/src/components/MediaGallery.tsx]], [[frontend/apps/manage/src/components/ProfileSection.tsx]], [[frontend/apps/manage/src/components/StaffSection.tsx]], [[frontend/apps/manage/src/components/TermsSection.tsx]], [[frontend/apps/manage/src/components/TypesSection.tsx]], [[frontend/apps/manage/src/components/VariantMatrix.tsx]]
- Storefront: [[frontend/apps/storefront/src/components/ContactCard.tsx]], [[frontend/apps/storefront/src/components/HoursCard.tsx]], [[frontend/apps/storefront/src/components/booking/TypePicker.tsx]], [[frontend/apps/storefront/src/routes/BookPage.tsx]], [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]]

## Concepts

- [[Design Tokens]]

## Tests

- [[frontend/packages/ui/src/__tests__/Card.test.tsx]] — renders children on a paper surface; adds the hover-elevate transition **only** when asked

## Notes

Renders a bare `<div>` with no landmark role. Sectioning is the caller's job — see [[frontend/packages/ui/src/components/SectionHeading.tsx]].
