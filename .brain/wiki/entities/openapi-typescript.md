---
tags: [frontend, tooling, api, declined]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# openapi-typescript

**Purpose.** Generates TypeScript types from the backend's OpenAPI schema. Version `^7.5.0`, a
devDependency of [[frontend/packages/api-client/package.json]] with a `generate` script pointing
at `http://localhost:8000/openapi.json`. **Nothing in the repo consumes its output** — it is
installed so the step *could* run, not because anything on the critical path uses it.

[[frontend/packages/api-client/src/index.ts]] is an `export {}` stub whose entire body is the
comment explaining the refusal: codegen buys drift-proof types but needs a live backend in the
dev loop and a committed artifact CI can neither regenerate nor verify — so it drifts silently,
which is the exact failure it was bought to prevent. Three read-only GETs with no request body
did not justify that. Both apps ship their own hand-written `src/api.ts` instead.

**Trap.** `pnpm --filter @boutique/api-client generate` needs the backend running **and**
`APP_ENV=dev`: `/openapi.json` is disabled outside dev (a public storefront origin would put the
schema in front of crawlers), so on a staging or production API the command fetches a 404 and
writes nothing useful. It is never run in [[.github/workflows/ci.yml]].

The stub names its own owner: the booking flow's mutations with real request bodies are where
codegen starts paying for itself.

## Related

- [[FastAPI]] · [[TypeScript]] · [[Vite]]
