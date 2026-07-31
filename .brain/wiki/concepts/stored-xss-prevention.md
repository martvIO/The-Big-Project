---
tags: [backend, frontend, security, catalog, storefront]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Stored XSS Prevention

**What it is.** Two things stored by one party render for another: the boutique's own settings and
media render to anonymous visitors, and the customer's name and notes render into the owner's
console. Both directions are gated at write **and** at render, because there is no CSP yet.

## URLs: allowlist at write, allowlist again at render

`maps_url` is tenant-supplied and lands in an `href`.
[[backend/app/boutique/validation.py]] allowlists the scheme at write time
(`ALLOWED_MAPS_URL_SCHEMES = {http, https}`), and [[frontend/packages/ui/src/lib/url.ts]] does it
again at render with `safeHref`. Its comment carries the two facts that make this not redundant:

- **React does *not* neutralise a `javascript:` href.** JSX escaping saves text children, not
  attribute values.
- **An allowlist beats a denylist** because browsers strip leading control characters and
  whitespace — `"java\tscript:"` defeats a denylist and never matches a must-start-with rule.

## Media: SVG is excluded because it is executable

[[backend/app/catalog/validation.py]] accepts exactly `image/jpeg`, `image/png`, `image/webp`. Its
comment states the reason plainly — *SVG is executable markup, and an SVG served from our bucket
is stored XSS*. The database pins the same set because it is a security boundary, not duplication.

Three further hardenings on that path:

- the object's **magic bytes** are asserted at confirm, and `webp` is checked as two segments
  (`RIFF` at 0, `WEBP` at 8) because a single-prefix table would silently accept anything
  RIFF-shaped — a `.wav`, an `.avi`, a polyglot;
- the key extension comes from the **declared content type**, never the client filename, and the
  original filename is not stored at all ([[backend/app/catalog/keys.py]]);
- the `Content-Disposition` download name is derived from the row's own id, so no client string
  reaches that header.

## Free text renders as a React text child, and only that

Customer `name` and `notes` are the first customer-authored strings in the product
([[backend/app/booking/validation.py]]). Bounded at write, and at render both
[[frontend/apps/manage/src/components/BookingDetail.tsx]] and
[[frontend/apps/storefront/src/routes/BookPage.tsx]] state it in a comment: no
`dangerouslySetInnerHTML`, no markdown pass, no linkification. Those two comments are the only
occurrences of the string in the whole source tree.

## The trap

**CSP is deliberately absent, not forgotten.** [[backend/app/security_headers.py]] explains why —
a CSP for a Vite bundle needs a nonce-or-hash story authored against a deployed artifact, and there
is no frontend deploy pipeline yet. Until F21 lands it, the render-time discipline above *is* the
whole defence; there is no backstop header to catch a slip.

## Related

- [[Input Validation At The Boundary]] · [[Enumeration Resistance]]
- [[.planning/security-checklist-v1.md]] · [[frontend/packages/ui/src/components/ContactPanel.tsx]]
