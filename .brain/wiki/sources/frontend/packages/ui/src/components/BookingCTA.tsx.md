---
tags: [frontend, ui, react, layout, responsive]
sources: [frontend/packages/ui/src/components/BookingCTA.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/BookingCTA.tsx
blob: cb30105ffafa7b1fa7ee3970aece41c06f2e74a3
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/BookingCTA.tsx

**Role.** A responsive wrapper, not a button: below 768 it pins whatever it wraps to the viewport bottom as a full-bleed bordered bar; from 768 up it dissolves to a plain static, transparent, padding-free container so the same child flows inline in the page.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `BookingCTA` | component | `{children, className?}` — no `onClick`, no label; the action is entirely the caller's child |
| `BookingCTAProps` | interface | |

## Behavior

Two class sets on one `<div>`: `fixed inset-x-0 bottom-0 z-40 border-t border-border bg-bg p-3` at the mobile default, then `md:static md:inset-auto md:border-0 md:bg-transparent md:p-0` unwinding every one of them at the breakpoint. Nothing about the bar is conditional in JS, so it cannot be turned off at runtime — a caller that wants the inline form renders the child **without** this wrapper (which is exactly what [[frontend/apps/storefront/src/components/BookingCTAButton.tsx]] does with its `inline` prop; its own comment notes that `BookingCTA` cannot be talked out of its bar by a `className`, because `cn()` has no class-merge).

The bar's footprint is a published number, not an implementation detail: `--cta-bar-height` in [[frontend/packages/ui/src/tokens.ts]] is `calc(56px + 2 * var(--space-3))` — an 56px button plus the `p-3` above and below, 80px total. Two things consume it. Pages carrying a bar reserve matching bottom padding so the bar never covers the last content, and [[frontend/packages/ui/src/components/A11yMenu.tsx]] lifts its fixed trigger by `--space-a11y-clearance` (= `--cta-bar-height + --space-3`) when told a bar is present. Changing the padding here without changing the token silently breaks both.

`z-40` sits one layer below the A11y menu's `z-50`, so the accessibility trigger is never covered by the CTA bar.

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`
- [[frontend/packages/ui/src/tokens.ts]] — `--cta-bar-height` is the contract this component's padding must match
- [[React]] — `ReactNode`

## Depended On By

- [[frontend/packages/ui/src/index.ts]]
- [[frontend/apps/storefront/src/components/BookingCTAButton.tsx]] — the only direct consumer; wraps a `ButtonLink`
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — knows which routes carry a bar, and passes `hasBookingBar` down to the A11y menu

## Concepts

- [[Design Tokens]]

## Tests

- [[frontend/packages/ui/src/__tests__/chrome-composites.test.tsx]] — asserts it renders as a fixed bottom bar carrying its action, and that it spans the full inline axis with a utility Tailwind actually generates
- [[frontend/packages/ui/src/__tests__/tokens.test.ts]] — guards `--cta-bar-height`
- [[frontend/apps/storefront/src/__tests__/AboutPage.test.tsx]], [[frontend/e2e/storefront.spec.ts]]

## Notes

Uses physical `inset-x-0 bottom-0` rather than logical properties — correct here, because the bar is symmetric on the inline axis and pinned on the block axis, so RTL cannot change it.
