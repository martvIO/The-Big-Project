---
tags: [frontend, typescript, ui]
sources: [frontend/apps/storefront/src/components]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/components
blob: fdba5aa145b1f8b327d9b604186bdb20afb64758
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/storefront/src/components/

**Purpose.** Storefront-only presentational components — the ones too site-specific to earn a place in `packages/ui`.

**Parent.** [[frontend/apps/storefront/src/_index]]

## Files

- [[frontend/apps/storefront/src/components/BookingCTAButton.tsx]] — The one entry into `/book/*` — a `ButtonLink` anchor carrying `booking.cta`, wrapped in the fixed-bar `BookingCTA` by default and rendered bare when `inline`.
- [[frontend/apps/storefront/src/components/ContactCard.tsx]] — `ContactPanel` on paper — and one guard: it returns `null` when the boutique has published no usable channel, so a freshly provisioned tenant never gets a blank `Card`.
- [[frontend/apps/storefront/src/components/DescriptionClamp.tsx]] — The dress description's six-line clamp with a real disclosure toggle — line-based rather than pixel-height, with overflow **measured** from the DOM instead of guessed from a character count, and re-measured when the A11y menu changes the…
- [[frontend/apps/storefront/src/components/HoursCard.tsx]] — `HoursTable` plus the two things the shared primitive deliberately does not own: the composed "today" lead line above it, and the upcoming-exceptions list beneath it.
- [[frontend/apps/storefront/src/components/Monogram.tsx]] — The dress detail page's no-photo art: the **boutique's** first character in the display serif, on paper, inside a gold hairline at a 3:4 aspect box.
- [[frontend/apps/storefront/src/components/ShareButton.tsx]] — Share the current dress URL: the native share sheet where the platform has one, a clipboard copy where it does not, and a **spoken** confirmation either way — the toast renders `role="status"`, because a silent clipboard write looks broken…
- [[frontend/apps/storefront/src/components/StorefrontLayout.tsx]] — The app shell and the **single owner of the boutique fetch**: it calls `getBoutiqueOnce()` once for the whole app, publishes `{boutique, loading, error, retry}` through a context every route reads, and owns the chrome that no route can own…

## Subdirectories

- [[frontend/apps/storefront/src/components/booking/_index]] — The booking flow's pickers, minus the slot picker, which was promoted into `packages/ui` when the owner console needed it too.
