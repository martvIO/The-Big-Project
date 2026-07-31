---
tags: [frontend, ui, component, typography, accessibility]
sources: [frontend/packages/ui/src/components/SectionHeading.tsx]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/components/SectionHeading.tsx
blob: 362b6d55beefae42cdbe1193bfc15424c0ebff3b
commit: 593e0b0c60607f16bf0603170d49286f03a3c05f
kind: code
applicability: active
---

# frontend/packages/ui/src/components/SectionHeading.tsx

**Role.** The one section title in the system: it separates the *heading level* (an `as` prop the caller sets from the page's outline) from the *visual weight* (fixed at `font-display text-xl text-ink`), so nobody ever reaches for a smaller `<h3>` to get smaller text. The optional gold hairline underneath is an `aria-hidden` ornament, never a semantic rule.

**Module.** [[frontend/packages/ui/src/components/_index]] · **Layer.** ui

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `SectionHeading` | fn | renders `children` inside a `<h1>`/`<h2>`/`<h3>` wrapped in a flex column |
| `SectionHeadingProps` | interface | `{children, as?, ornament?, className?}` |

## Behavior

`as` defaults to `"h2"` and is typed to exactly `h1 | h2 | h3` — a deeper level is not offered, because the level is the document outline and a section this component titles never nests four deep in either app. The tag is chosen by assigning the prop to a capitalised local (`const Tag = as`), the standard React dynamic-element idiom; the type union is what keeps it from becoming a `<div>`-shaped escape hatch.

The `ornament` hairline is a bare `<span>` with `aria-hidden="true"` and `h-px w-12 bg-gold`. It carries `aria-hidden` because it is a decorative divider, not an `<hr>` — announcing "separator" after every heading is exactly the noise that makes screen-reader navigation worse. Note that it is `w-12`, a *physical* width, which is direction-agnostic and therefore fine under the RTL rules; it sits at the flex column's start edge, so in the RTL document it renders on the right.

`className` merges onto the outer wrapper via `cn()`, not onto the heading element — a caller can space the block but cannot restyle the type. That is deliberate, and doubly enforced by `cn()` performing no class-merge (see Notes).

## Depends On

- [[frontend/packages/ui/src/lib/styles.ts]] — `cn`
- [[React]] — `ReactNode` type only (entity)

## Depended On By

- [[frontend/packages/ui/src/index.ts]] — re-exports `SectionHeading` + `SectionHeadingProps`
- [[frontend/apps/manage/src/components/ProfileSection.tsx]] — `as="h2"` over the profile form
- [[frontend/apps/storefront/src/components/HoursCard.tsx]]
- [[frontend/apps/storefront/src/routes/AboutPage.tsx]]
- [[frontend/apps/storefront/src/routes/AccessibilityPage.tsx]]

## Concepts

- [[Accessibility Compliance]]

## Tests

- [[frontend/packages/ui/src/__tests__/display-primitives.test.tsx]] — asserts `as="h1" ornament` yields a real level-1 heading whose accessible name is the child text (i.e. the ornament contributes nothing)

## Notes

Takes no i18n call — the title arrives as `children`, like every `packages/ui` component. A caller that wants a different size must not pass `text-2xl` through `className`: `cn()` is a plain join with no class-merge, so two same-specificity Tailwind rules resolve by stylesheet order, not by call-site order.
