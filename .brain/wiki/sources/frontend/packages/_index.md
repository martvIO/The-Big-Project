---
tags: [frontend, typescript]
sources: [frontend/packages]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages
blob: 75a441b330ff1c93d0b42522fbf85576c4c07cb8
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/packages/

**Purpose.** The shared workspace packages.

**Parent.** [[frontend/_index]]

## Subdirectories

- [[frontend/packages/api-client/_index]] — A deliberate non-implementation. Codegen was considered and declined; the header records why, and both apps hand-write their own typed fetch client instead.
- [[frontend/packages/ui/_index]] — The shared component library. It has no i18next dependency by design — every string arrives as a prop.
