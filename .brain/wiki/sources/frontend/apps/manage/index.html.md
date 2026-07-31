---
tags: [frontend, manage, html, vite, rtl, branding, accessibility]
sources: [frontend/apps/manage/index.html]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: frontend/apps/manage/index.html
blob: 065994491277d83a3a9a4edb2583d0adfdaa70f5
commit: a93ff9bec72c63d35742e0c7ad0eae12f8106de6
kind: config
applicability: active
---

# frontend/apps/manage/index.html

**Role.** Vite's entry document for the owner console — and the only place four otherwise-invisible contracts are declared: the document is Hebrew RTL (`lang="he" dir="rtl"` on `<html>`, not toggled at runtime), the viewport meta does **not** disable pinch zoom, the three MODRYN favicon links are attached, and the document title carries the `MODRYN — ` prefix that the console is *required* to have and the storefront is *forbidden* to have.

**Module.** [[frontend/apps/manage/_index]] · **Layer.** platform

## Public Surface

| Symbol | Kind | Purpose |
|---|---|---|
| `<html lang="he" dir="rtl">` | attribute pair | the app's RTL default; every component below assumes it and uses logical properties only |
| `<meta name="viewport">` | tag | `width=device-width, initial-scale=1.0` — deliberately no `user-scalable=no` and no `maximum-scale` |
| favicon links | tags | `/favicon.svg`, `/favicon-32.png` (32×32), `/apple-touch-icon.png` — served from [[frontend/apps/manage/public/favicon.svg]] et al. |
| `<title>` | tag | `MODRYN — ניהול הבוטיק` |
| `#root` | element | the mount node [[frontend/apps/manage/src/main.tsx]] hydrates |
| `<script type="module" src="/src/main.tsx">` | tag | the single entry; Vite rewrites it at build |

## Behavior

`dir="rtl"` here is why nothing downstream sets direction: components use logical CSS (`ms-*`/`me-*`, `start`/`end`) and `frontend/scripts/qa-greps.sh` mechanically bans physical-direction props, so this one attribute is the whole direction contract. Individual Latin/numeric runs opt *out* locally with `<bdi dir="ltr">`; Hebrew free text takes a bare `<bdi>`.

The two accessibility clauses are both load-bearing and both invisible to a reviewer skimming for markup. Omitting `user-scalable=no`/`maximum-scale=1` satisfies WCAG 1.4.4 — pinch zoom *is* the resize mechanism on a phone, and blocking it removes 200% text from the visitor who needs it most. IS 5568 makes that a legal obligation here, not a nicety, so [[frontend/e2e/a11y.spec.ts]] asserts it across **both** apps' index.html precisely because the two files are edited independently and neither one's change shows up in the other's diff.

The title is the console half of the F30 branding rule: MODRYN brands the *platform*, never the tenant. [[frontend/apps/storefront/index.html]] carries the same three favicon links (a tab icon is chrome) and a Hebrew title with no MODRYN in it — the e2e suite pins both directions, `toHaveTitle(/^MODRYN — /)` here and `not.toHaveTitle(/MODRYN/i)` there. The title is also static markup rather than an i18n string, so it is the one Hebrew string in the app that never routes through [[frontend/apps/manage/src/i18n/he.ts]]; the runtime `document.title` update does.

## Depends On

- [[frontend/apps/manage/src/main.tsx]] — module entry
- [[frontend/apps/manage/public/favicon.svg]] · [[frontend/apps/manage/public/favicon-32.png]] · [[frontend/apps/manage/public/apple-touch-icon.png]]
- [[Vite]] — resolves and hashes the module script at build

## Depended On By

- [[frontend/apps/manage/vite.config.ts]] — implicit build entry (Vite's default `index.html` root)
- [[frontend/e2e/a11y.spec.ts]] — asserts the title and the viewport meta

## Concepts

- [[RTL And Bidi Isolation]]
- [[Accessibility Compliance]]

## Tests

- [[frontend/e2e/a11y.spec.ts]] — "neither app's index.html disables pinch zoom"; the manage-title / storefront-title branding pair

## Notes

Spec: [[.planning/specs/modryn-branding.md]] (F30 — the icon set, the title prefix, and the "platform not tenant" rule).
