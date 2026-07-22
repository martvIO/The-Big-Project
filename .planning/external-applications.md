# External Applications Tracker — standing risk until all approved

**Owner**: user (only the user can file these) · **Re-flag rule**: every feature cycle re-checks this file until every row is `approved`.
Created 2026-07-22 by E1 Feature 2. Lead times are multi-week — filing order is the critical path to the pilot.

| # | Item | Status | Blocks | Notes |
|---|------|--------|--------|-------|
| 1 | AWS account + il-central-1 opt-in | not-started | E2 #8 (S3 upload), E4 skeleton, production | Create account, enable the il-central-1 opt-in region, billing alarm. Fastest item — do first. |
| 2 | Production domain | not-started | staging DNS naming, Route 53 zone, production | `.co.il` may require Israeli-entity eligibility — confirm registrar rules before committing. A separate cheap staging domain is an acceptable stopgap (buy now if the production domain will take time). |
| 3 | Grow (Meshulam) merchant account | not-started | E4 #17–18 (payments), deposit flows | Needs Israeli business registration + bank account docs. Longest lead time — file ASAP. Per-tenant merchant accounts: the pilot boutique files its own; platform needs sandbox access for E4 development. |
| 4 | SMS sender-ID / route registration | not-started | E3 #11 (OTP + booking SMS) | Provider decision (Twilio vs Inforu vs 019) is F2 Task 1 — comparison pending. Sender-ID registration is filed with the chosen provider/route after the decision. |
| 5 | Meta Business / WhatsApp Business API verification | not-started | E10 #2 (WhatsApp migration) | ROADMAP commits to starting Meta business verification **during v1** — multi-week lead time. Start-by trigger: E4 kickoff at the latest. |

## Status legend
`not-started` → `filed` (application submitted, waiting) → `approved` (credentials in hand) · `blocked` (needs user input/docs)

## What the user needs to do now

1. **AWS**: create the account, enable il-central-1, send confirmation. No credentials in the repo — **AWS keys go to Railway env only**; the only GitHub secret in this design is the project-scoped `RAILWAY_TOKEN`.
2. **Domain**: decide production brand domain; check `.co.il` registrar eligibility; if slow, buy a staging domain immediately so F2 Tasks 3/5 can proceed.
3. **Grow**: start the merchant application for the pilot boutique + request sandbox/developer access. This is the long pole for E4.
4. **SMS**: wait for the F2 Task 1 comparison (days, not weeks), then file the sender-ID registration with the recommended provider.

## Decisions record

- SMS provider: _pending F2 Task 1 comparison._
- Staging wildcard TLS host: _pending Railway wildcard-domain support check (fallback: Cloudflare front)._
- il-central-1 service availability: _pending AWS account._
