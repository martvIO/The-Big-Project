---
tags: [frontend, typescript, test]
sources: [frontend/e2e]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/e2e
blob: b82fb922836696c3548e293b3149a8ae37bda980
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# frontend/e2e/

**Purpose.** Playwright: journey specs and the axe accessibility specs, run against `vite preview` of both built apps with no backend.

**Parent.** [[frontend/_index]]

## Files

- [[frontend/e2e/a11y.spec.ts]] — The **API-is-down pass**: eight specs that intercept nothing, so both apps are exercised exactly as a visitor meets them when the backend is unreachable. It is also the only place the two apps are checked *together* (the pinch-zoom sweep)…
- [[frontend/e2e/package.json]] — Makes `e2e/` a pnpm workspace member — which is the entire point of the file. Membership is what puts the two spec files under the repo-wide `pnpm -r lint` and `pnpm -r typecheck` sweeps; a bare directory of `.ts` files would be linted and…
- [[frontend/e2e/playwright.config.ts]] — The whole E2E harness in one file: it starts `vite preview` for **both** built apps on fixed ports, pins the browser locale to `he-IL`, and runs a single chromium project. It is what makes "the built stylesheet, the built bundle" — not the…
- [[frontend/e2e/storefront.spec.ts]] — The storefront's whole journey suite in one file: it fulfils every `/storefront/*` request from an in-file fixture, then drives the real built app through the catalog, the dress detail, `/about`, `/accessibility`, the five-step `/book/*`…
- [[frontend/e2e/tsconfig.json]] — Four lines: extend the shared base and add `"types": ["node"]`, because [[frontend/e2e/playwright.config.ts]] reads `process.env.CI` and nothing else in this package touches Node globals.
