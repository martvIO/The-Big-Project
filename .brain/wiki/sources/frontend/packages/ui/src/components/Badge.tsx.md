---
tags: [frontend, ui, react, primitive, contrast]
sources: [frontend/packages/ui/src/components/Badge.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/Badge.tsx
blob: 80e0829a9488233702202b297097438a928d59f2
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/Badge.tsx

**Role.** The one status-chip primitive: a pill `<span>` in five variants (`neutral`, `success`, `danger`, `muted`, `warning`), each an outline plus coloured text at `text-xs`. It is presentational only — no role, no live region — so anything that must be *announced* on change needs its own `role="status"` around it.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Badge` | component | `{variant = "neutral", className, children, ...rest}`; spreads the rest onto the `<span>` (it extends `HTMLAttributes<HTMLSpanElement>`) |
| `BadgeVariant` | type | `"neutral" \| "success" \| "danger" \| "muted" \| "warning"` |
| `BadgeProps` | interface | |

## Behavior

The variant map is a contrast decision, not a palette. Every variant passes AA **as text** at the badge's `text-xs` size — the word carries the meaning and the outline is decorative, which is also why no variant uses a filled background that would need its own foreground check. `warning` additionally sets `font-semibold` and uses `text-warning-text` rather than a raw warning colour, because the plain warning token does not clear the text floor.

**There is deliberately no `gold` variant.** `gold-strong` measures 3.80:1 — below the 4.5:1 text floor — and a Badge is always small text, so a gold marker is spelled `text-gold-text` inline at the call site instead. Adding a `gold` variant here would reintroduce a failing contrast pair in the one place the design system is supposed to prevent it.

`className` is appended last through `cn()`, but `cn()` is a plain join with **no class-merge**: a caller passing e.g. `text-sm` sits at the same specificity as the component's `text-xs` and resolves by stylesheet order, not by call-site precedence. The one in-repo override that works ([[frontend/packages/ui/src/components/DressCard.tsx]] passing `bg-surface-raised` on a `muted` badge) works because the variant sets no background at all — it adds a property rather than fighting one. Do not document call-site overrides as a supported pattern.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`
- [[React]] — `HTMLAttributes`, `ReactNode`

## Depended On By

- [[frontend/packages/ui/src/index.ts]]
- [[frontend/packages/ui/src/components/DressCard.tsx]] — the "reserved" overlay chip
- [[frontend/apps/manage/src/components/BookingsSection.tsx]], [[frontend/apps/manage/src/components/BookingDetail.tsx]], [[frontend/apps/manage/src/components/CatalogSection.tsx]], [[frontend/apps/manage/src/components/DressEditor.tsx]], [[frontend/apps/manage/src/components/HoursSection.tsx]], [[frontend/apps/manage/src/components/StaffSection.tsx]], [[frontend/apps/manage/src/components/TypesSection.tsx]], [[frontend/apps/manage/src/components/VariantMatrix.tsx]], [[frontend/apps/manage/src/lib/booking.tsx]]
- [[frontend/apps/storefront/src/components/booking/TypePicker.tsx]], [[frontend/apps/storefront/src/routes/DressPage.tsx]]

## Concepts

- [[Design Tokens]]

## Tests

- [[frontend/packages/ui/src/__tests__/Badge.test.tsx]] — renders each variant and asserts its text is present (the word, not the colour, is the signal)

## Notes

Status colour is never the sole indicator anywhere Badge is used: the variant always accompanies a translated word supplied by the caller.
