# v1 Security Checklist — Ship Gate

**Status**: open — every item must be checked (with evidence) before the pilot goes live.
**Owned by**: E4 Feature 21. Referenced from `epics/ROADMAP.md` (v1 definition of done).

## Tenant isolation
- [ ] RLS `FORCE`d on all tenant tables; app DB role is non-owner; policies keyed to `current_setting('app.tenant_id')`
- [ ] Unset tenant context returns zero rows (regression test)
- [ ] CI cross-tenant isolation suite: every repository method + API endpoint probed as tenant A against tenant B's data — green, blocking, never removed
- [ ] Tenant never accepted from client input (host-derived only)
- [ ] S3 keys tenant-prefixed; media served via short-lived signed URLs
- [ ] Provisioning CLI: access-restricted, every invocation audit-logged (incl. any RLS-bypass)

## Sessions & auth
- [ ] Cookies `HttpOnly` + `Secure` + `SameSite=Lax`, scoped to the exact subdomain — never the parent domain
- [ ] Login + OTP rate-limited per phone and per IP; OTP ≤5-min expiry, single-use
- [ ] Booking-flow phone verification (OTP) enforced before customer record creation
- [ ] Operator password-reset path via audited CLI only

## Tokens & links
- [ ] Manage/confirm/cancel tokens ≥128-bit random, stored hashed, expire at appointment time, idempotent on repeat use

## Payments (PCI SAQ-A)
- [ ] Card entry exclusively on Grow's hosted page; no PAN ever proxied, logged, or stored on our origin
- [ ] Webhook signature verification + replay protection; duplicate deliveries idempotent
- [ ] Per-tenant gateway credentials KMS-encrypted; never logged
- [ ] Receipt (קבלה) issuance confirmed for every charge and refund
- [ ] CSP forbids card fields / third-party scripts on our origin

## Platform hardening
- [ ] Secrets in AWS Secrets Manager (no plaintext env secrets in prod)
- [ ] Rate limiting + WAF on public booking + OTP endpoints
- [ ] Security headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options
- [ ] Dependency scanning (pip-audit, npm audit) green in CI
- [ ] Upload validation: content-type + size limits on presigned S3 uploads

## Data protection (PPL / Data Security Regulations)

> Rows 39-43 were assessed at **F20** (PPL compliance build). Three are green; two
> are **amber** and stay unchecked, each with a named owner. An amber row is one
> F20 partly discharged — checking it would hand F21 a lie to audit, which is the
> failure F21 exists to catch. Evidence for all five: `.planning/ppl-compliance-record.md`.
> Splitting rows 40 and 42 into their per-owner clauses is F21's edit, not F20's.

- [ ] Audit log on all owner/CLI mutations and data access by operators
- [x] Privacy notice per tenant; DPA text in boutique ToS — **F20**: platform-written Hebrew notice + DPA clause, per-boutique overridable, rendered at every collection point and on `/privacy`; platform-owned sub-processor list, structurally un-overridable
- [ ] Consent captured with timestamp + terms-version + source; marketing opt-in separate, unbundled, default OFF; opt-out honored in every marketing send — **AMBER (F20)**: capture, structural unbundling, structural default-off (a NULL timestamp, not a flippable boolean) and an owner/shift-manager opt-out writer with both arms all ship. **The send-time clause has no subject until a marketing send exists.** *Owner: F46.*
- [x] PII-scrub job (true erasure, not soft-delete) tested — **F20**: the SCRUB action, its `customers` and `queue_tickets` consumers, and the `subject-erase` transaction, all db-tested against real Postgres
- [ ] Retention jobs per data class running (OTP: minutes; queue entries: days; bookings: years; message log: months) — **AMBER (F20)**: six per-class policies ship, tested, with boot-validated floors; the queue-entries clause **closed at F20** (F33's tickets have a policy). **`retention_enabled` ships `False`** — the job is shipped but not *running*, because an unattended irreversible mass-delete must not precede a drilled restore (row 44). *Owner: F21.*
- [x] Processing-activities record started; incident-response procedure written — **F20**: `.planning/ppl-compliance-record.md` §1 and §3
- [ ] Backups automated; restore drilled; RPO/RTO documented — **gates row 42.**

## Accessibility (IS 5568 / WCAG 2.0 AA — legal requirement)
- [ ] axe-core automated pass on storefront + booking flow
- [ ] Manual keyboard + screen-reader spot check
- [ ] Contrast audit passed (gold-as-accent, dark ink for text)
- [ ] Accessibility statement page published
