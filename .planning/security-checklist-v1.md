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
- [ ] Audit log on all owner/CLI mutations and data access by operators
- [ ] Privacy notice per tenant; DPA text in boutique ToS
- [ ] Consent captured with timestamp + terms-version + source; marketing opt-in separate, unbundled, default OFF; opt-out honored in every marketing send
- [ ] PII-scrub job (true erasure, not soft-delete) tested
- [ ] Retention jobs per data class running (OTP: minutes; queue entries: days; bookings: years; message log: months)
- [ ] Processing-activities record started; incident-response procedure written
- [ ] Backups automated; restore drilled; RPO/RTO documented

## Accessibility (IS 5568 / WCAG 2.0 AA — legal requirement)
- [ ] axe-core automated pass on storefront + booking flow
- [ ] Manual keyboard + screen-reader spot check
- [ ] Contrast audit passed (gold-as-accent, dark ink for text)
- [ ] Accessibility statement page published
