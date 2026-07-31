---
tags: [frontend, typescript, test]
sources: [frontend/packages/ui/src/test]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/ui/src/test
blob: 40b33b3e7087ebe0e39a30956d5d104bcb59831c
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/packages/ui/src/test/

**Purpose.** Vitest setup shared by the package's suites.

**Parent.** [[frontend/packages/ui/src/_index]]

## Files

- [[frontend/packages/ui/src/test/setup.ts]] — The one setup file every `@boutique/ui` test runs: it loads the `jest-dom` matchers, registers an explicit `afterEach(cleanup)`, and monkey-patches jsdom's incomplete `HTMLDialogElement` so the `<dialog>`-based Modal is testable at all.
