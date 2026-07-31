---
tags: [frontend, typescript]
sources: [frontend/packages/api-client]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/api-client
blob: 0862f32954cc2e019ce9ce0de67a3943c20be28a
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/packages/api-client/

**Purpose.** A deliberate non-implementation. Codegen was considered and declined; the header records why, and both apps hand-write their own typed fetch client instead.

**Parent.** [[frontend/packages/_index]]

## Files

- [[frontend/packages/api-client/package.json]] — The manifest of a workspace package with no consumers and no runtime code — it exists to keep the *option* of OpenAPI codegen wired up (the `generate` script) while [[frontend/packages/api-client/src/index.ts]] stays an intentional `export…
- [[frontend/packages/api-client/tsconfig.json]] — Two lines: extend [[frontend/tsconfig.base.json]], include `src`.

## Subdirectories

- [[frontend/packages/api-client/src/_index]] — An empty export. See the package page for the decision it encodes.
