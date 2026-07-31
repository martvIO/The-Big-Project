---
tags: [frontend, accessibility, legal, storefront, testing]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Accessibility Compliance

**What it is.** **IS 5568 (WCAG 2.0 AA) is a legal requirement** for a public Israeli site, not a
quality target. [[.planning/architecture.md]] records it under Compliance and
[[.planning/security-checklist-v1.md]] gates the pilot on it. Treat an a11y regression the way you
would treat a data leak, not the way you would treat a styling nit.

## The statement page is a legal artifact

IS 5568 §35 makes הצהרת נגישות — and a **named, reachable contact inside it** — an obligation.
[[frontend/apps/storefront/src/routes/AccessibilityPage.tsx]] therefore ships one `h1`, an `h2` per
section, real lists, and no content that exists only as visual arrangement.

**The responsible party is the boutique, not the platform.** It is the service provider; its own
phone and Instagram come from the layout-level fetch. There is deliberately no platform-operator
coordinator layer. The page has no loading state and no error state either — a statement page that
renders a spinner instead of the statement is itself the failure it exists to declare.
[[frontend/apps/storefront/src/__tests__/accessibility.test.tsx]] guards what an auditor checks:
the declared standard, the menu the statement claims to ship, the limitations it admits, a
reachable complaints contact, a review date, and the absence of placeholder text.

## A first-party menu, never an overlay

[[frontend/packages/ui/src/components/A11yMenu.tsx]] ships five controls — contrast, text size,
readable font, underline links, stop motion. Each toggles a `data-a11y-*` attribute on `<html>`
and [[frontend/packages/ui/src/theme.css]] styles the boost. Third-party accessibility overlays are
not used. [[frontend/packages/ui/src/components/A11y.tsx]] carries the `SkipLink` — the first
focusable element on every storefront page.

## What is checked mechanically

- **axe-core, tags `wcag2a` + `wcag2aa`, zero violations** — [[frontend/e2e/a11y.spec.ts]],
  including a *no-data* pass: with the API unreachable the storefront must still be a valid,
  navigable, accessible document.
- **Contrast is computed, not eyeballed** — [[frontend/packages/ui/src/__tests__/tokens.test.ts]]
  derives WCAG relative luminance from the token hexes themselves. See [[Design Tokens]].
- **Pinch zoom must not be disabled** (WCAG 1.4.4) — asserted against *both*
  [[frontend/apps/storefront/index.html]] and [[frontend/apps/manage/index.html]], because the two
  files are edited independently.

## The traps

- **A Hebrew-only page rendering an English server sentence is invisible to axe** and to every
  layout check. Every backend message is English, so failure copy is selected by error **code** and
  rendered from the Hebrew bundle — pinned by its own e2e test. See [[Hebrew First UX]].
- **The `A11yMenu` trigger is `fixed`, so the *consumer* owes it space.** What it costs is a
  reservation the scrolling document pays with `--space-a11y-footprint` in its footer. Hiding or
  un-fixing the trigger is not the fix.
- **`sr-only` sets `padding: 0`**; a plain `px-4 py-2` on a skip link overrides it and leaves a
  ~64px invisible box that still contributes to `scrollWidth` and trips the horizontal-overflow
  checks. Focus-only padding is the pattern.

## Related

- [[RTL And Bidi Isolation]] · [[Hebrew First UX]] · [[Design Tokens]]
- [[.planning/design/qa-checklist.md]] · [[frontend/scripts/qa-greps.sh]] ·
  [[.planning/design-config.md]]
