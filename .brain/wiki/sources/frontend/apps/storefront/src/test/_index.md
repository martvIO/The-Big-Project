---
tags: [frontend, typescript, test]
sources: [frontend/apps/storefront/src/test]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/test
blob: c11b934669ceafd9e3e156d0dc751b58df93df80
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/storefront/src/test/

**Purpose.** Vitest setup.

**Parent.** [[frontend/apps/storefront/src/_index]]

## Files

- [[frontend/apps/storefront/src/test/setup.ts]] — The one setup file every storefront test runs: it loads the `jest-dom` matchers, registers an explicit `afterEach(cleanup)`, and monkey-patches jsdom's incomplete `HTMLDialogElement`.
