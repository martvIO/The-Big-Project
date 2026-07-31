---
tags: [backend, python]
sources: [backend/app/auth]
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: backend/app/auth
blob: f4b355a04d87ebc9efaa7bf7bdfda18d927a7457
commit: 13d107b8b16f1f2676f1cdb1c994f95822fe2ba0
kind: directory
applicability: active
---

# backend/app/auth/

**Purpose.** Owner and staff identity: password verification, opaque session tokens, the session cookie, and — since F31 — the role gate that makes every `/manage` route default-deny.

**Parent.** [[backend/app/_index]]

## Files

- [[backend/app/auth/__init__.py]] — Empty file marking `app.auth` as a package — the home of [[Owner Authentication]]: password hashing, session tokens, cookies, the login rate limiter, the FastAPI router and its request dependencies.
- [[backend/app/auth/cookies.py]] — Owns the name of the staff session cookie and the exact attribute set it is written and cleared with — deliberately *without* a `Domain` attribute, which is what keeps a session minted on one boutique's subdomain from being sent to…
- [[backend/app/auth/dependencies.py]] — The authentication and authorization seam every `/manage` route hangs off: `get_current_staff` turns the session cookie into a `StaffContext` or raises, `RoleGate`/`require_role` admits only listed roles and fails closed on everything…
- [[backend/app/auth/passwords.py]] — The one argon2 hasher for staff passwords, plus `verify_password_dummy` — a verify against a precomputed throwaway hash whose only job is to make the unknown-email login path burn the same CPU as a real one, so response time cannot…
- [[backend/app/auth/rate_limit.py]] — The one in-process fixed-window counter every rate limit in this backend is built from — login, terms creation, media presign, storefront reads, OTP send/verify, booking create, booking lookup and the owner SMS taps all instantiate it.…
- [[backend/app/auth/router.py]] — The three `/manage/auth` routes — login (rate-limited per `(tenant,email)`, and per-IP only when a real client IP can be trusted), logout, and `me` — plus `RateLimitedError`, the 429 the login budget raises.
- [[backend/app/auth/schemas.py]] — The wire contract for login and for owner staff administration, plus the three password/name bounds the frontend is held to by a parity test — and `StaffMember`, whose safety comes from what it does *not* model.
- [[backend/app/auth/service.py]] — Verifies staff credentials against `staff_users`, mints and stores a hashed session row, resolves a cookie back to a `StaffContext` on every request, and revokes on logout — writing a `LOGIN` / `LOGIN_FAILED` / `LOGOUT` audit row on every…
- [[backend/app/auth/staff.py]] — Owner-only staff administration — list, create, update (name / role / password) and deactivate — holding two invariants that must survive **concurrency**: a staffer may not demote or deactivate herself, and a tenant may never be left with…
- [[backend/app/auth/staff_router.py]] — The four owner-only staff routes on `/manage` — list, create, patch, deactivate — gated at **router** level so a route added here later cannot forget the gate, and carrying `no-store` on every response.
- [[backend/app/auth/tokens.py]] — Mints 256-bit URL-safe session tokens and hashes them with SHA-256, so the database stores only hashes and a dump of `sessions` cannot be replayed as live cookies.
