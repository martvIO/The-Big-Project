---
tags: [frontend, api-client, stub, openapi, codegen, decision-record]
sources: [frontend/packages/api-client/src/index.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/packages/api-client/src/index.ts
blob: f0cee5ed021946902cc465d6749be886f6b923d0
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/packages/api-client/src/index.ts

**Role.** `export {}` and a header comment. This is a **deliberate non-implementation**, not unfinished work: the file exists to hold the recorded decision that OpenAPI codegen was declined for F10, and to keep the package importable-but-empty so nothing silently starts depending on a client that does not exist.

**Module.** [[frontend/packages/api-client/_index]] · **Layer.** api

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `export {}` | statement | makes the file a module (`isolatedModules` in [[frontend/tsconfig.base.json]] rejects a file with no top-level export or import). No runtime surface at all. |

## Behavior

The header states the reasoning in full and it is worth preserving verbatim in spirit: codegen buys drift-proof types, but it needs a **live backend in the dev loop** and produces a **committed artifact CI can neither regenerate nor verify** — so the generated file drifts silently, which is the exact failure codegen was bought to prevent. Three read-only GETs with no request body did not justify that trade. Both apps therefore hand-write their own typed fetch client: [[frontend/apps/storefront/src/api.ts]] and [[frontend/apps/manage/src/api.ts]].

A second constraint landed with F10 and is recorded here: the `generate` script in [[frontend/packages/api-client/package.json]] now also needs `APP_ENV=dev`, because `/openapi.json` is disabled outside dev (`create_app` in [[backend/app/main.py]]) — a public storefront origin would otherwise put the schema in front of crawlers.

The comment names an owner and a trigger: **E3 #14**, when the booking flow adds mutations with real request bodies, is where codegen starts paying for itself, and hoisting the shared fetch helpers out of the two apps belongs in that same pass. That trigger has since been overtaken by events — the booking mutations shipped ([[frontend/apps/storefront/src/routes/BookPage.tsx]] POSTs bookings, OTP and the tokenized manage calls) and the two apps still hand-write their clients. Treat the note as an open decision to revisit, not as a description of the current tree.

## Depends On

Nothing. No imports, no dependencies at runtime.

## Depended On By

Nothing imports `@boutique/api-client` — no app declares it as a dependency and no file imports from it. The two apps' own `src/api.ts` files are the real clients:

- [[frontend/apps/storefront/src/api.ts]] — names the package only in a comment, recording the same deferral ("hoisting them into `@boutique/api-client` is a cleanup with no consumer pressure yet")
- [[frontend/apps/manage/src/api.ts]] — the helper the storefront's is a deliberate local copy of; the two differ on credentials and on error rendering

## Notes

Do not "finish" this file on the assumption it is a stub someone forgot. Adding types here without also removing the hand-written clients produces two sources of truth for the same wire shapes — strictly worse than either alternative. If codegen is adopted, the `src/generated/schema.d.ts` path the `generate` script writes to is not currently committed or gitignored anywhere; that gap is part of the decision to make, not an oversight to patch in isolation.
