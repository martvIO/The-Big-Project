# Epic: E4 — Deposits, Compliance & Pilot Hardening

**Created**: 2026-07-21 (rev 2 — post verification pass)
**Status**: planning — **roadmap only, by decision on 2026-07-29.** No E4 feature gets a spec until E3 is closer to done; each is spec'd feature-by-feature when its turn arrives, matching the per-feature `/spartan:spec` → `/spartan:plan` → `/spartan:build` pipeline every shipped feature has used. Writing all five specs now would mean guessing at Grow's integration details before the merchant account exists, and rewriting them afterwards.

**Sequencing when E4 starts**: #17 → #18 → #19 are a chain and all three are gated on **Grow merchant-account approval**, which is external lead time filed in E1 #2 and still outstanding. **#20 (PPL compliance) depends only on E3 #13, which has shipped** — so it is the one E4 feature that is spec-able today, and it is the right place to start if Grow is still pending when E3 closes. #21 is last by definition: it is the ship gate.
**Owner**: team
**PRD**: §5 (Israeli billing, deposit דמי רצינות; client dashboard deferred to E5)

---

## Why

Deposits are the boutique's no-show defense and a locked v1 requirement. This epic integrates Grow (hosted payment page, per-tenant merchant accounts, PCI SAQ-A), wires deposits into the booking flow, builds the PPL compliance layer, and hardens the platform to the in-repo security checklist before the pilot goes live. Verification pass split the gateway work (credentials vs. sessions), surfaced the Israeli receipt (קבלה) obligation, deferred refund-API automation to manual-at-pilot-volume, and made the ship gate a versioned in-repo artifact.

---

## Success Criteria

- [ ] With deposits enabled, a booking is only confirmed after a signature-verified Grow webhook (**J4 charge, not J5 hold** — locked decision); the customer pays on Grow's hosted page (no card data ever touches our origin); duplicate webhooks are idempotent; **a receipt is issued for every charge and refund**
- [ ] Unpaid holds expire and release their slot automatically; cancellation inside the structured policy window (E2 #7) marks the payment refund-due with an owner task; outside it, forfeit is recorded against the accepted terms version; deposits-off appointment types confirm instantly with no payment step
- [ ] `.planning/security-checklist-v1.md` fully green; PPL artifacts live (consent capture, privacy notice, DPA, PII scrub, retention jobs); backup/restore drilled; IS 5568 accessibility audit passed; pilot UAT signed off

---

## Features

| # | Feature | Status | Spec | Plan | Depends On |
|---|---------|--------|------|------|------------|
| 17 | Gateway credential management | **done (PR #29)** | `.planning/specs/gateway-port.md` | — | E1 #2, E2 #7 |
| 18 | ~~Grow~~ **Lemon Squeezy** payment sessions & webhooks | **done (PR #31)** | `.planning/specs/lemonsqueezy-adapter.md` | — | #17 |
| 19 | Deposit booking flow | **done (PR #34)** | `.planning/specs/deposit-booking-flow.md` | `.planning/plans/deposit-booking-flow.md` | E2 #7, E3 #16, #18 |
| 20 | PPL compliance build | **done (PR #45)** — migration `0024` | `.planning/specs/ppl-compliance.md` | `.planning/plans/ppl-compliance.md` | E3 #13 |
| 21 | Hardening, audits & pilot UAT | todo — **now unblocked**, F20 merged | — | — | all v1 |

**#18's provider changed and the row above says so deliberately.** The 2026-07-31 ruling
made **Lemon Squeezy test mode** E4's engine behind F17's provider-agnostic port. LS is
merchant-of-record while the deposit is legally the *boutique's* money, so it can never
carry live deposits — the production Israeli PSP is deferred to before-live-money and is
one adapter file behind the same port. Grow is not cancelled, only demoted to one
candidate for that decision.

**#20 shipped with two amber checklist rows, on purpose.** `retention_enabled` ships
`False` (Gate 1 Q2) because there is no backup and no tested restore — that is **#21's**
row 44, and flipping it is what turns row 42 green. Row 40 waits on F46's send-time
opt-out. Marking either green before then would hand #21 a lie to audit.

**What #21 inherits from the 2026-08-04 walkthrough:** nine logged defects in
`LOOP-STATE.md → known_product_bugs` (six a11y — a legal requirement here), and
`walkthrough_coverage_gaps` **G2**: the deposit/payment leg has **zero** browser
coverage. It is the only leg with money semantics and the one nobody has walked.

---

## Feature Briefs

### Feature 17: Gateway credential management (S)
Provider-agnostic gateway interface + per-tenant Grow credentials stored KMS-encrypted (**KMS provisioned here**), validation ping, credential status surfaced in owner settings. **Verifies whether Grow auto-issues receipts (קבלה/חשבונית) for charges and refunds — an Israeli legal obligation for J4 charges; if it doesn't, receipt issuance enters Feature 19's scope.** Independent of the booking flow, so it proceeds in parallel with E3 the moment Grow approval (filed in E1 #2) lands.

### Feature 18: Grow payment sessions & webhooks (M)
Hosted-payment-page session creation (**J4 immediate charge — never J5 auth-hold**; holds expire in days, appointments are weeks out), webhook endpoint with signature verification + replay protection, refund API call wrapped but **not auto-invoked in v1**. Exercised end-to-end against the Grow sandbox. Yaad/Tranzila remain future implementations behind the Feature 17 interface.

### Feature 19: Deposit booking flow (M)
When the tenant's deposit toggle is on: booking enters `pending_payment` with a 15-minute slot hold → redirect to hosted page → webhook flips to `confirmed` and triggers the Feature 16 confirmation SMS. Sweeper worker cancels expired unpaid holds and frees slots. Cancellation branches on E2 #7's **structured refund-window fields**: inside → payment marked refund-due + owner task (**refund executed manually in Grow's console at pilot volume; API automation is E5 #29**); outside → forfeit recorded. Race-tested: hold expiry vs. late webhook. Reschedule (E3 #15) carries the deposit — no new charge.

### Feature 20: PPL compliance build (M)
Runs in parallel with 17–19. Consent capture (terms checkbox required; separate unbundled marketing opt-in, default OFF, with timestamp + terms-version + source), per-tenant privacy notice, DPA text in boutique ToS, PII-scrub job (anonymize in place — soft-delete is not erasure), retention jobs per data class (OTP minutes, queue days, bookings years), processing-activities record.

### Feature 21: Hardening, audits & pilot UAT (L — includes production stand-up)
Also owns **production environment stand-up** (compute, production wildcard DNS/TLS, prod Postgres, Secrets Manager migration) and **Terraform-izing the F2 infra runbook** — previously unowned scope, folded in here per the F2 rev-2 verification pass. The ship gate. Runs **`.planning/security-checklist-v1.md`** (in-repo, versioned — created with this epic) to fully green: RLS suite, cookies, rate limits, token hygiene, webhook security, KMS, audit log, secrets in Secrets Manager, WAF/headers/dependency scanning, backups + tested restore with written RPO/RTO. axe-core + manual IS 5568 accessibility audit. Pilot onboarding with real Hebrew content + UAT sign-off. (k6 load testing deliberately cut from v1 — concurrency *correctness* is covered by Feature 13/19 race tests; load testing gates multi-tenant onboarding in E5 #29.)

---

## Risks

- **Grow merchant-account approval is external lead time** — filed in E1 #2; if it slips, Features 17–19 slip, not the rest of v1 (E3 completes independently).
- Webhook delivery reliability: confirmation must not depend on the customer's redirect completing — webhook is authoritative, plus a reconciliation poll for missed webhooks.
- Receipt auto-issuance assumption — verified early in Feature 17, scope adjusted before Feature 19 spec if wrong.

## Notes

- v1 ships when Feature 21's checklist is fully green — it is a gate, not a formality.
