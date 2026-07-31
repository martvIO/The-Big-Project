---
tags: [frontend, storefront, test, vitest, i18n, hebrew, static-analysis]
sources: [frontend/apps/storefront/src/__tests__/i18n-keys.test.ts]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/src/__tests__/i18n-keys.test.ts
blob: 0c2d92a8867897ac0f0209ccf5665d3f2fd4d7e2
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: code
applicability: active
---

# frontend/apps/storefront/src/__tests__/i18n-keys.test.ts

**Role.** A source scanner, not a rendering test: it reads every dotted literal key out of the app's own `.ts`/`.tsx` files with `node:fs`, resolves each one against the `he.ts` bundle **without going through `t()`**, and asserts it lands on real, non-empty Hebrew that i18next also registers.

**Module.** [[frontend/apps/storefront/src/__tests__/_index]] · **Layer.** test

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `SRC` | const | `join(process.cwd(), "src")` — `import.meta.url` is not a `file:` URL under jsdom, and Vitest runs with the package root as cwd |
| `SECTIONS` | const | `new Set(Object.keys(he.translation))` — the top-level namespaces; membership is what separates a key from a className or a URL |
| `DOTTED_LITERAL` | regex | a double-quoted `word(.word)+` literal |
| `sourceFiles(dir)` | helper | recursive walk that **excludes** `__tests__` and `test` — tests are the thing being guarded, not a source of shipped keys |
| `keysIn` / `resolve` | helper | extract-and-filter; then a `split(".").reduce()` walk down the nested bundle |
| `USED_KEYS` | const | the deduplicated, sorted scan result, with `src/i18n` itself excluded |
| `finds the keys the source actually uses` | test | `length > 40` plus three named keys — the anti-vacuous guard |
| two `it.each(USED_KEYS)` suites | test | each key resolves to real Hebrew; each key is registered with i18next |

## Behavior

The defect this file exists for cannot be caught by any rendering test. i18next answers a miss by returning **the bare key**, so a deleted or renamed entry renders `statement.limitsAlt` in Latin onto a Hebrew page — and a test written as `expect(…).toHaveTextContent(t("statement.limitsAlt"))` keeps passing, because both sides degrade to the same ASCII literal. Resolving through the raw bundle instead of `t()` is what breaks that symmetry.

**The `> 40` floor is the load-bearing line.** A scanner that silently matches nothing — a changed quote style, a moved `src`, a `SECTIONS` set built from the wrong object — makes both `it.each` suites iterate an empty array and pass with zero assertions run. The floor plus three explicitly named keys (`statement.limitsAlt`, `statement.coordinatorNoChannel`, `dress.share`) turns that failure mode from green into red. Treat the number as a ratchet: raise it as copy grows, never lower it.

**This scanner is not portable to `apps/manage`, and the reason is structural.** It assumes a strictly *nested* bundle: `SECTIONS` is the set of top-level keys, and `resolve()` walks `split(".")` segment by segment. The storefront's [[frontend/apps/storefront/src/i18n/he.ts]] is exactly that — twelve nested namespaces. The console's [[frontend/apps/manage/src/i18n/he.ts]] mixes **flat dotted keys** (`"booking.error.SLOT_UNAVAILABLE"` as a literal property) in beside nested namespaces, which i18next resolves via its `ignoreJSONStructure` retry but which this walk cannot follow at all. That is why [[frontend/apps/manage/src/__tests__/i18n.test.ts]] enumerates explicit key decks with its own numeric floors rather than scanning source.

The Hebrew assertion is applied to the **prose only**: `{{placeholders}}` are stripped first, because a value like `"{{date}} {{open}}–{{close}}"` carries no words of its own and demanding Hebrew of it would be wrong. Array values are unwrapped and every entry checked. The second suite then re-resolves each key through the live instance — `returnObjects` for arrays, `skipOnVariables` for interpolated strings — because a key present in `he.ts` but not registered with i18next fails in exactly the same visible way.

## Depends On

- [[frontend/apps/storefront/src/i18n/he.ts]] — the resource bundle, imported directly
- [[frontend/apps/storefront/src/i18n/index.ts]] — the initialised instance, for the registration half
- [[Vitest]] · [[i18next]] · `node:fs` / `node:path`

## Depended On By

Nothing imports a test file. Every other suite in this directory asserts Hebrew via `i18n.t(...)`; this file is what makes those assertions meaningful rather than self-fulfilling.

## Concepts

- [[RTL And Bidi Isolation]]

## Notes

The scan is textual, so a key built dynamically (template literal, computed segment) is invisible to it — `` t(`errors.${code}`) `` would never appear in `USED_KEYS`. The `errors.*` family is instead covered end-to-end by [[frontend/apps/storefront/src/__tests__/api.test.ts]], which asserts each mapped key renders Hebrew with no Latin characters. Note also that `packages/ui` components never call i18n — strings arrive as props — so this suite is scoped to the app's own bundle by construction and can never cover a UI-package string.
