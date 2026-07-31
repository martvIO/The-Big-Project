---
tags: [frontend, storefront, seo, crawling, privacy, static-asset]
sources: [frontend/apps/storefront/public/robots.txt]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/public/robots.txt
blob: 7510cbd685d1cc7efe1cca518403d1c96b13ee76
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/apps/storefront/public/robots.txt

**Role.** Two directives — `User-agent: *` / `Disallow: /` — that keep every search engine out of every tenant storefront until E10 ships real SEO. Five lines of comment carry the reasoning, because the file looks like an oversight and is the opposite of one.

**Module.** [[frontend/apps/storefront/public/_index]] · **Layer.** platform / static asset

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `User-agent: *` | directive | applies to every crawler |
| `Disallow: /` | directive | the entire site, including `/dress/:id`, `/about`, `/accessibility` and `/b/{token}` |

## Behavior

**The default this file overrides is crawl-everything, and the spec enumerates three concrete harms it would cause.** A boutique that has not launched gets its `/dress/{id}` pages indexed; the presigned media URLs behind them are ~900 s links that answer 403 a quarter of an hour later, so the cached result is a broken page; and the owner's street address, which the storefront renders as public identity, lands in search results with no owner-facing control until E10 exists. This is a *control*, deliberately shipped ahead of the feature it controls — the spec's line is "SEO is E10. The off switch is not."

Vite copies `public/` verbatim into `dist/`, so the file is served at the site root of every tenant with no build step and no route. Being one static file, it is also **flat across tenants**: `Disallow: /` is right precisely because it needs no per-boutique decision. E10's plan replaces it with a per-tenant `robots.txt` resolved by `Host` through the existing tenancy middleware, alongside a `sitemap.xml` and build-time prerendering (pre-decided #46 — *not* SSR).

**It is not a security boundary.** `Disallow` is honored by well-behaved crawlers and by nothing else; anything actually confidential has to be absent from the API response, which is how [[backend/app/storefront/schemas.py]] handles it. There is no matching file in the console app — [[frontend/apps/manage/index.html]]'s app ships no `robots.txt`, and does not need one, because every route behind it requires a session.

## Depends On

- [[Vite]] — `publicDir` copy, no transform

## Depended On By

Nothing in code. It is fetched by crawlers at `/robots.txt` and referenced by no module, test, or build step.

## Notes

Spec: [[.planning/specs/storefront-browse.md]] (F10 — "`robots.txt` ships here, as a control, not as SEO"). Replacement is scoped in [[.planning/epics/e10-scale-polish.md]]. Predates [[.planning/specs/modryn-branding.md]] — F30's own surface table notes that the storefront's `public/` already existed because of this file, while the console's `public/` was created from scratch.

Nothing asserts its content: no unit test, no e2e spec, no CI grep. Deleting it is a silent change with an entirely non-silent consequence.
