---
tags: [frontend, storefront, test, vitest, api-client, error-handling, hebrew]
sources: [frontend/apps/storefront/src/__tests__/api.test.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/api.test.ts
blob: 9118563367a3e879dfa4cb775089781ec698f222
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/api.test.ts

**Role.** The full contract test for the storefront's hand-written fetch client: error extraction from the house envelope, the three fallback paths that must produce an `ApiError` rather than a raw `SyntaxError`, `credentials: "omit"` on **every** verb, the code→Hebrew-key mapping that keeps English backend prose off a Hebrew-only page, the exact path and query shape of all nine endpoints, and `getBoutiqueOnce`'s single-flight cache including its failure eviction.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `t` | helper | `i18n.t` bound to the **real** Hebrew catalogue — a stubbed `t()` would pass on a missing key |
| `LATIN` | const | `/[A-Za-z]/` — the actual teeth of the error-rendering suite |
| `stubFetch(makeResponse)` | helper | a fresh `Response` per call, because a body is single-use |
| `apiFetch error extraction` | suite | house shape, non-JSON body, missing envelope, **200 answering HTML**, `isNotFound` |
| `apiFetch request mechanics` | suite | credentials omitted, bare GET, JSON POST, 204 without a parse |
| `errorMessage` / `errorMessageOr` | suite | eleven code→key rows; surface-specific fallback vs. a code that does say something |
| `storefront endpoints` | suite | list/detail/boutique/terms/appointment-types/slots/otp-verify/bookings |
| `booking-path VALIDATION_ERROR stays out of isNotFound` | suite | pins a deliberate disagreement between two helpers |
| `getBoutiqueOnce` | suite | one fetch for concurrent + later callers; a rejected attempt is dropped |

## Behavior

**The eleven-row error table's real assertion is `not.toMatch(LATIN)`.** Every backend message is English, so rendering `ApiError.message` would paint Latin text onto a Hebrew-only page for a suspended tenant, an unknown slug, an archived dress or a throttle trip. The Latin guard fails the instant anyone "helpfully" falls back to `error.message` — and it catches a second defect for free, because i18next answers a missing key by echoing the key back, which is also Latin. Each row additionally asserts `rendered !== key`, so a renamed resource is red rather than silently ASCII.

The 200-answering-HTML case is not hypothetical and the source comment says so: under the SPA history fallback with no backend behind the dev proxy, `/storefront/dresses` returns `200 text/html` — exactly the state the blocking e2e job runs in. A raw `SyntaxError` escapes the page's catch and blanks the screen instead of rendering the error card, so `apiFetch` must convert it.

**The `booking-path VALIDATION_ERROR` suite documents a pair of helpers that intentionally disagree.** `isNotFound` folds `400 VALIDATION_ERROR` into "dress gone", which is correct on the dress detail (a malformed UUID is the only 400 that surface can produce, and a Retry button would re-issue the same 400 forever) and **wrong** on the booking POST, where a schema 400 is a form problem. The test asserts both halves out loud: `isNotFound(error)` is `true` and `errorMessageKey(error)` is `errors.validation`. Routing a booking failure through `isNotFound` therefore fails here rather than in production.

Request mechanics are pinned per verb because the omission is a security property, not a default: `credentials: "omit"` on the GETs *and* on the mutations, since the booking credential is the verification token in the body and a cookie on this surface is a cookie in a log. GETs must send no `body` and no `headers` at all; the 204 from `/otp/send` must resolve `undefined` without a parse attempt.

Endpoint assertions read the query through `new URL(path, base).searchParams` rather than string-matching, so parameter order cannot make them brittle. Two are worth naming: `listDresses` sends **only** `offset` (the limit is server-pinned at 24, and a client-sent limit would be a widening surface), and `getDress` percent-encodes the id into the path. The `createBooking` case asserts the posted body **verbatim in snake_case** including the explicit `null`s — this app hand-writes its client and does no case conversion, so a camelCase field name here is a silent 400.

`getBoutiqueOnce` is tested for both directions of its cache: two concurrent calls and one later call all share a single fetch and the *same object identity*, while a rejected attempt must be evicted so a retry actually retries — otherwise the layout's retry button is permanently inert.

## Depends On

- [[frontend/apps/storefront/src/api.ts]] — the subject
- [[frontend/apps/storefront/src/i18n/index.ts]] — the real Hebrew catalogue, deliberately not stubbed
- [[Vitest]] — `vi.stubGlobal("fetch", …)`

## Depended On By

Nothing imports a test file. Its guarantees are leaned on by every route and component suite in this directory that mocks `api` and asserts a Hebrew error string, and by [[frontend/apps/storefront/src/__tests__/StorefrontLayout.test.tsx]], which asserts the *single* `getBoutique()` call this file proves the cache delivers.

## Concepts

- [[Tenant Isolation]]

## Notes

`resetBoutiqueCache()` runs in `afterEach` alongside `vi.unstubAllGlobals()`; the module-scope promise would otherwise leak a resolved boutique into the next file. The wire types this suite exercises mirror [[backend/app/storefront/schemas.py]] — the fixture bodies are the same field sets, so a backend rename that this client does not follow shows up as a type error at build rather than here.
