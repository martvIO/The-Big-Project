---
tags: [backend, security, middleware, tenancy]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# CSRF Origin Check

**What it is.** Defence in depth for the cookie-authenticated `/manage` surface: a mutating
request whose `Origin` names a different *hostname* than its `Host` is refused with `403
CSRF_ORIGIN_MISMATCH`. Implemented once, in [[backend/app/csrf.py]].

## Why `SameSite=Lax` is not enough

The session cookie already sets `SameSite=Lax` ([[backend/app/auth/cookies.py]]), which blocks
classic cross-**site** CSRF. But this product's whole routing model is wildcard subdomains
(`{slug}.modryn.co.il` — see [[Tenant Resolution]]), and **a sibling subdomain is same-site**. Once
public tenant pages exist, Lax does nothing against `evil-boutique.modryn.co.il` posting at
`bella.modryn.co.il/manage/…`. This middleware is the control that covers that gap.

## Three decisions worth knowing before you touch it

- **A missing `Origin` passes.** Requests without one are not browser cross-origin submissions —
  curl, server-to-server, the test client. Rejecting them would break the fast API suite and buy
  nothing.
- **Hostnames only, never scheme or port.** The dev proxy serves the app on `:5173` while the API
  sees the same hostname, and the sibling-subdomain attack this blocks is purely a hostname
  property. `"null"` and malformed Origins parse to `None` and are rejected.
- **It guards `/manage` by prefix, and mutating verbs only.** `/storefront` is anonymous and has
  no cookie to ride.

## Ordering is load-bearing

The middleware is registered so that it runs **before routing**, which means a forged Origin can
never surface as `NOT_AUTHORIZED` — the request never reaches dependency solving at all. That is
not incidental: `test_a_forged_origin_beats_the_role_gate_on_the_same_route` in
[[backend/tests/test_staff_role_gating.py]] asserts it by counting `resolve_session` calls, not by
comparing status codes (both answers are 403).

Note the contrast with [[backend/app/security_headers.py]], which is registered **last** precisely
so it is *outermost* and stamps the tenant-resolution 404 that never reaches a handler. Middleware
order in this app is a decision each time, not a default.

## Related

- [[Owner Authentication]] · [[Role Based Access Control]] · [[Tenant Isolation]]
- [[.planning/security-checklist-v1.md]] — HSTS and CSP are still open, and deliberately so
