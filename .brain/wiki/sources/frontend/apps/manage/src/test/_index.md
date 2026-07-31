---
tags: [frontend, typescript, test]
sources: [frontend/apps/manage/src/test]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/src/test
blob: 076f9825fd8683d66a31e04585c21e458a86048a
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/apps/manage/src/test/

**Purpose.** Vitest setup, including the jsdom `<dialog>` stub the confirm modals need.

**Parent.** [[frontend/apps/manage/src/_index]]

## Files

- [[frontend/apps/manage/src/test/setup.ts]] — The console's single Vitest setup file. It does three things and no more: loads `jest-dom`'s matchers, registers Testing Library's `cleanup` by hand (auto-cleanup cannot self-install under `globals: false`), and monkey-patches jsdom's…
