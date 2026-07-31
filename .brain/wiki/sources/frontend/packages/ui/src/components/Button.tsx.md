---
tags: [frontend, ui, react, primitive, contrast, forwarded-ref]
sources: [frontend/packages/ui/src/components/Button.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/Button.tsx
blob: 5c98f88ed05ab54dcccfeaeca37f22bbe1bc9204
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/Button.tsx

**Role.** The single button primitive and the **only** definition of the product's variant set — `primary | secondary | ghost | danger`, three sizes, an optional `fullWidthMobile`, a `loading` state that also disables and sets `aria-busy`, and a forwarded `ref`. Plus `ButtonLink`: the same visual surface on an `<a>`, with the button-only affordances deliberately amputated.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `Button` | component | `{variant = "primary", size = "md", fullWidthMobile = false, loading = false, disabled, ref, ...ButtonHTMLAttributes}` |
| `ButtonLink` | component | `{href, variant, size, fullWidthMobile, ...AnchorHTMLAttributes}` minus `href`/`type` |
| `ButtonVariant` | type | `"primary" \| "secondary" \| "ghost" \| "danger"` — the complete set |
| `ButtonSize` | type | `"sm" \| "md" \| "lg"` → `min-h-9 / min-h-11 / min-h-12` |
| `ButtonProps`, `ButtonLinkProps` | interface | |

## Behavior

**`ref` is a plain prop** (React 19 style, no `forwardRef` wrapper) and it is load-bearing: focus-to-first-invalid on form submission depends on a caller being able to hold a ref to the control it must focus. `type="button"` is hardcoded **before** the `{...rest}` spread, so a caller *can* still pass `type="submit"` and win — the default only prevents accidental implicit submits.

`loading` does three things at once: it forces `disabled` (`disabled={disabled || loading}`), sets `aria-busy`, and — the non-obvious part — **keeps the label in the DOM**, merely `invisible` and `aria-hidden`, while the spinner is absolutely overlaid. That is a width lock: removing the label would collapse the button mid-interaction and shift everything beside it.

The variant map encodes a contrast history worth not re-litigating. `primary` is `bg-gold text-ink` **including on hover** (6.41:1, identical at rest and on hover); the hover affordance is elevation (`hover:shadow-md`), not a colour swap. The previous hover — `gold-strong` background with a white label — measured 3.93:1, under the 4.5 floor, and mobile browsers leave `:hover` stuck after a tap, so a user sat looking at the failing state. No token is dark enough to darken under `ink` and still clear 4.5, so there is no colour-based hover available at all. There is likewise **no `ghost-danger`**: the set above is closed, and combining `ghost` with a `className` does *not* produce one, because `cn()` is a plain join with no class-merge — a call-site `text-danger` and the variant's `text-ink` are the same specificity and resolve by stylesheet order.

The `base` string uses `transition` rather than `transition-colors` precisely so the `primary` elevation animates, with `duration-(--motion-fast)` resolving to a motion token.

`ButtonLink` intentionally omits `loading`, `disabled`, `type` and `ref`: a link can be none of those, and a "disabled anchor" is the commonest way a design system ships an unreachable control. It otherwise composes the identical `base + variants + sizes + focusRing`, which the test suite pins byte-for-byte against `Button`.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`, `focusRing`
- [[frontend/packages/ui/src/tokens.ts]] — `--motion-fast`, and the `gold` / `ink` / `danger` colour tokens

## Depended On By

- [[frontend/packages/ui/src/index.ts]]
- [[frontend/packages/ui/src/components/EmptyState.tsx]]
- Manage console: [[frontend/apps/manage/src/components/LoginForm.tsx]], [[frontend/apps/manage/src/components/BookingDetail.tsx]], [[frontend/apps/manage/src/components/CatalogSection.tsx]], [[frontend/apps/manage/src/components/DressEditor.tsx]], [[frontend/apps/manage/src/components/HoursSection.tsx]], [[frontend/apps/manage/src/components/MediaGallery.tsx]], [[frontend/apps/manage/src/components/ProfileSection.tsx]], [[frontend/apps/manage/src/components/RescheduleDialog.tsx]], [[frontend/apps/manage/src/components/StaffSection.tsx]], [[frontend/apps/manage/src/components/TermsSection.tsx]], [[frontend/apps/manage/src/components/TypesSection.tsx]], [[frontend/apps/manage/src/components/VariantMatrix.tsx]]
- Storefront: [[frontend/apps/storefront/src/components/BookingCTAButton.tsx]] (`ButtonLink`), [[frontend/apps/storefront/src/components/DescriptionClamp.tsx]], [[frontend/apps/storefront/src/components/ShareButton.tsx]], [[frontend/apps/storefront/src/routes/AboutPage.tsx]], [[frontend/apps/storefront/src/routes/BookPage.tsx]], [[frontend/apps/storefront/src/routes/CatalogPage.tsx]], [[frontend/apps/storefront/src/routes/DressPage.tsx]], [[frontend/apps/storefront/src/routes/ManageBookingPage.tsx]]

## Concepts

- [[Design Tokens]]

## Tests

- [[frontend/packages/ui/src/__tests__/Button.test.tsx]] — label as accessible name; `loading` keeps the label in the DOM and marks busy + disabled; transition duration/easing come from motion tokens; `onClick` does not fire while loading; **markup is asserted byte-identical to a pre-`ButtonLink` capture** (a regression fence around the shared `base`); `ButtonLink` carries the same classes and none of `Button`'s button-only surface
- [[frontend/packages/ui/src/__tests__/tokens.test.ts]], [[frontend/e2e/a11y.spec.ts]]

## Notes

The byte-identical-markup test means any change to `base`, `variants` or `sizes` — even a reordering — fails the suite. That is intentional; update the captured string in the same commit and explain why.
