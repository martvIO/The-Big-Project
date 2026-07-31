---
tags: [frontend, storefront, html, vite, rtl, branding, accessibility]
sources: [frontend/apps/storefront/index.html]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/storefront/index.html
blob: bded0ad82bd85b99fc8af16900f98b8e00fcd828
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/apps/storefront/index.html

**Role.** Vite's entry document for the public boutique site, and the only place three otherwise-invisible contracts are declared: the document is Hebrew RTL (`lang="he" dir="rtl"` on `<html>`, never toggled at runtime), the viewport meta does **not** disable pinch zoom, and the title is Hebrew with **no MODRYN in it** — this app is the boutique's shop front, so the favicon is the single platform mark permitted to reach it.

**Module.** [[frontend/apps/storefront/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `<html lang="he" dir="rtl">` | attribute pair | the RTL default every component below assumes; logical CSS only |
| `<meta name="viewport">` | tag | `width=device-width, initial-scale=1.0` — deliberately no `user-scalable=no`, no `maximum-scale` |
| favicon links | tags | `/favicon.svg`, `/favicon-32.png` (32×32), `/apple-touch-icon.png` from [[frontend/apps/storefront/public/favicon.svg]] et al. |
| `<title>` | tag | `חנות הכלות` — a static Hebrew placeholder, replaced per route at runtime |
| `#root` | element | the mount node [[frontend/apps/storefront/src/main.tsx]] renders into |
| `<script type="module" src="/src/main.tsx">` | tag | the single entry; Vite rewrites it at build |

## Behavior

`dir="rtl"` here is the whole direction contract: components use logical properties (`ms-*`/`me-*`, `start`/`end`) and [[frontend/scripts/qa-greps.sh]] mechanically fails the build on physical-direction utilities, so nothing downstream sets direction again. Latin and numeric runs opt *out* locally with `<bdi dir="ltr">`; Hebrew free text takes a bare `<bdi>`, because `dir="ltr"` on Hebrew is itself a bidi defect.

**The comment above the favicon links is the F30 branding boundary written into markup.** MODRYN brands the platform, not the tenant — a tab icon counts as chrome, a title does not. [[frontend/apps/manage/index.html]] carries the mirror-image obligation (`MODRYN — ניהול הבוטיק`), and [[frontend/e2e/a11y.spec.ts]] pins both directions at once: `toHaveTitle(/[֐-׿]/)` and `not.toHaveTitle(/MODRYN/i)` here, `/^MODRYN — /` there. Adding "MODRYN" to this `<title>` is a failing e2e test, not a style opinion.

**The static title is a fallback, not the shipped title.** [[frontend/apps/storefront/src/router.tsx]] assigns `document.title` per route from the Hebrew bundle on every navigation (WCAG 2.4.2), and the dress page overwrites it with the dress name. `חנות הכלות` is only what a visitor sees for the frame before React mounts — which is also why it is the one Hebrew string in the app that never routes through [[frontend/apps/storefront/src/i18n/he.ts]].

Omitting `user-scalable=no`/`maximum-scale=1` satisfies WCAG 1.4.4: pinch zoom *is* the resize mechanism on a phone, and blocking it removes 200% text from the visitor who needs it most. IS 5568 makes that a legal obligation in this product. The e2e suite asserts it across **both** apps' `index.html` precisely because the two files are edited independently and neither one's diff shows the other regressing.

## Depends On

- [[frontend/apps/storefront/src/main.tsx]] — module entry
- [[frontend/apps/storefront/public/favicon.svg]] · [[frontend/apps/storefront/public/favicon-32.png]] · [[frontend/apps/storefront/public/apple-touch-icon.png]]
- [[Vite]] — resolves and hashes the module script at build

## Depended On By

- [[frontend/apps/storefront/vite.config.ts]] — implicit build entry (Vite's default `index.html` root)
- [[frontend/e2e/a11y.spec.ts]] — asserts the title and the viewport meta

## Concepts

- [[Hebrew RTL Bidi]]
- [[IS 5568 Accessibility]]

## Tests

- [[frontend/e2e/a11y.spec.ts]] — "storefront: Hebrew document title + cream color-scheme (no forced dark)"; "neither app's index.html disables pinch zoom"

## Notes

Spec: [[.planning/specs/modryn-branding.md]] (F30 — icon set, the title prefix, and the platform-not-tenant rule). No `<meta name="description">`, no `og:` tags and no canonical link: SEO is E10, and `og:image` could not work today anyway — media URLs are 900 s-expiring presigned links served with `attachment` disposition.
