---
tags: [frontend, testing, dom]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# jsdom

**Purpose.** The DOM implementation every [[Vitest]] suite runs in. Version `^29.1.1`, set as
`environment: "jsdom"` in [[frontend/packages/ui/vitest.config.ts]],
[[frontend/apps/storefront/vitest.config.ts]] and [[frontend/apps/manage/vitest.config.ts]].
`packages/api-client` has no jsdom because it has no tests.

**jsdom has no layout and no stylesheets, and that shapes the tests.** Every element reports
`scrollHeight = clientHeight = 0`, no Tailwind class computes to anything, and
`window.scrollTo`/`scrollY` do not exist. So anything measured is stubbed and the *measurement*
is asserted rather than the pixel — see
[[frontend/apps/storefront/src/__tests__/DescriptionClamp.test.tsx]] and the class-name (not
computed-style) assertions in [[frontend/apps/storefront/src/__tests__/CatalogPage.test.tsx]].

**The `<dialog>` shim is a stub, not an implementation.** All three `src/test/setup.ts` files
patch `HTMLDialogElement.prototype` when `showModal` is missing —
[[frontend/packages/ui/src/test/setup.ts]] ·
[[frontend/apps/storefront/src/test/setup.ts]] · [[frontend/apps/manage/src/test/setup.ts]].
The shim only flips the `open` attribute and dispatches `close`. It does **not** reproduce the
top layer, the backdrop, inertness of the rest of the page, `Escape` handling or focus trapping.
A passing Modal test therefore says the open/close wiring works; it says nothing about whether
the dialog is actually modal. That verification belongs to [[Playwright]].

**Trap.** `import.meta.url` is not a `file:` URL under the jsdom environment, so the one test
that reads source files off disk resolves them from `process.cwd()` (the package root Vitest runs
in) instead — see [[frontend/apps/storefront/src/__tests__/i18n-keys.test.ts]].

## Related

- [[Vitest]] · [[Testing Library]] · [[Playwright]] · [[Accessibility Compliance]]
