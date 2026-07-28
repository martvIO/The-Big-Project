# External Applications Tracker — standing risk until all approved

**Owner**: user (only the user can file these) · **Re-flag rule**: every feature cycle re-checks this file until every row is `approved`.
Created 2026-07-22 by E1 Feature 2. Lead times are multi-week — filing order is the critical path to the pilot.

| # | Item | Status | Blocks | Notes |
|---|------|--------|--------|-------|
| 1 | AWS account + il-central-1 opt-in | approved | E2 #8 (S3 upload), E4 skeleton, production | **Done 2026-07-27.** Account `849279003056`, `il-central-1` opt-status `ENABLED`. Both buckets live and correctly configured (versioning, public access blocked, bucket-owner-enforced, CORS). Scoped IAM user `boutique-media-staging` created and its keys are wired into the Railway `api`/`worker` services (not root — root was only used for the one-time account-level bootstrap). Billing guardrail is an AWS Budgets budget (`boutique-platform-monthly`, $50/mo, 80%-actual/100%-forecasted email alerts) rather than a CloudWatch billing alarm — Budgets doesn't need the console-only "receive billing alerts" preference toggle that a CloudWatch alarm does, so it's the CLI-scriptable equivalent. **Full presign → upload → confirm → signed-GET smoke test is green against real S3** (byte-identical round trip) — see `docs/infra-runbook.md`. Along the way, found and fixed a real bug in `Backend/app/storage/s3.py`: `generate_presigned_post()` was defaulting to the legacy global S3 endpoint, which il-central-1 (an opt-in region) rejects outright; MinIO-based tests never caught it because that path always sets an explicit endpoint. **F10's spec can now proceed.** Feature 2 Task 2 (Railway staging deploy) was also completed in this pass — see the E1 epic. What's still open: bucket CORS `AllowedOrigins` and the Railway `BASE_DOMAIN` are placeholders (`*.boutique-platform.invalid`) pending item #2 below. |
| 2 | Production domain | not-started | staging DNS naming, Route 53 zone, production | `.co.il` may require Israeli-entity eligibility — confirm registrar rules before committing. A separate cheap staging domain is an acceptable stopgap (buy now if the production domain will take time). |
| 3 | Grow (Meshulam) merchant account | not-started | E4 #17–18 (payments), deposit flows | Needs Israeli business registration + bank account docs. Longest lead time — file ASAP. Per-tenant merchant accounts: the pilot boutique files its own; platform needs sandbox access for E4 development. |
| 4 | SMS sender-ID / route registration | not-started | E3 #11 (OTP + booking SMS) | Provider decision (Twilio vs Inforu vs 019) is F2 Task 1 — comparison pending. Sender-ID registration is filed with the chosen provider/route after the decision. |
| 5 | Meta Business / WhatsApp Business API verification | not-started | E10 #2 (WhatsApp migration) | ROADMAP commits to starting Meta business verification **during v1** — multi-week lead time. Start-by trigger: E4 kickoff at the latest. |

## Status legend
`not-started` → `filed` (application submitted, waiting) → `approved` (credentials in hand) · `blocked` (needs user input/docs)

## What the user needs to do now

1. **AWS**: done — account created, il-central-1 opted in, both buckets provisioned, IAM keys in Railway env, billing budget set, smoke test green. Nothing further needed from the user here; F10's spec can proceed.
2. **Domain**: decide production brand domain; check `.co.il` registrar eligibility; if slow, buy a staging domain immediately so F2 Tasks 3/5 can proceed.
3. **Grow**: start the merchant application for the pilot boutique + request sandbox/developer access. This is the long pole for E4.
4. **SMS**: wait for the F2 Task 1 comparison (days, not weeks), then file the sender-ID registration with the recommended provider.

## Decisions record

- SMS provider: _pending F2 Task 1 comparison._
- Staging wildcard TLS host: _pending Railway wildcard-domain support check (fallback: Cloudflare front)._
- il-central-1 service availability: confirmed 2026-07-27 — region opt-status `ENABLED`, S3 available and in use.
