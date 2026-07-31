---
tags: [backend, auth, security, staff]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Owner Authentication

**What it is.** The staff auth realm: email + password login against `staff_users`, exchanged for
an opaque session cookie on the `/manage` surface. It is the *only* password realm in the
product — customers never get a password, they prove a phone with a [[One Time Passcode]].

## The shape

[[backend/app/auth/service.py]] verifies with argon2 ([[backend/app/auth/passwords.py]]), mints a
256-bit token ([[backend/app/auth/tokens.py]]), stores only its sha256, and
[[backend/app/auth/router.py]] sets it as `boutique_session`. The cookie
([[backend/app/auth/cookies.py]]) is `HttpOnly` + `SameSite=Lax` + `Secure` outside dev, and
carries **no `Domain` attribute** — host-only, so a session minted at boutique A is never sent to
boutique B's subdomain. That is the cookie half of [[Tenant Isolation]]; the DB half is
[[Row Level Security]].

## Three things that look incidental and are not

**The login transaction must commit even when it fails.** `LOGIN_FAILED` is an audit row, and
raising inside `tenant_session` rolls it back with everything else. So `AuthService.login`
computes an `outcome`, lets the transaction close, and raises *outside* it.

**An unknown email still does argon2 work.** `verify_password_dummy` verifies against a
precomputed hash of a random value, so "no such account" costs the same wall time as "wrong
password" — see [[Enumeration Resistance]].

**The brute-force key is per-(tenant, email), not per-IP.** [[backend/app/auth/rate_limit.py]]
only ever records *failures*, so a shared client IP cannot throttle a legitimate owner. The
per-IP key exists but is off unless `trust_forwarded_for` is set, because behind an untrusted
proxy `request.client.host` is the proxy — one global bucket a tiny burst could use to 429 every
tenant at once ([[backend/app/core/config.py]]).

## Session resolution

`get_current_staff` in [[backend/app/auth/dependencies.py]] reads the cookie, hashes it, and
`resolve_session` re-reads `staff_users` on **every request**. There is no cached principal, which
is what makes a role change or a deactivation bite on the very next request with no session state
to sweep — the property [[Role Based Access Control]] depends on.

## Related

- [[Opaque Token Hashing]] · [[Role Based Access Control]] · [[CSRF Origin Check]]
- [[backend/app/auth/schemas.py]] — `MIN_STAFF_PASSWORD_LENGTH = 10`, and the reasoning for
  declining composition rules and rotation
- [[backend/tests/test_auth_api.py]] · [[backend/tests/test_auth_integration.py]]
- [[.planning/specs/owner-auth.md]] · [[.planning/plans/owner-auth.md]]
