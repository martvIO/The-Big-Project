# External Applications Tracker — standing risk until all approved

**Owner**: user (only the user can file these) · **Re-flag rule**: every feature cycle re-checks this file until every row is `approved`.
Created 2026-07-22 by E1 Feature 2. Lead times are multi-week — filing order is the critical path to the pilot.

| # | Item | Status | Blocks | Notes |
|---|------|--------|--------|-------|
| 1 | AWS account + il-central-1 opt-in | approved | E2 #8 (S3 upload), E4 skeleton, production | **Done 2026-07-27.** Account `849279003056`, `il-central-1` opt-status `ENABLED`. Both buckets live and correctly configured (versioning, public access blocked, bucket-owner-enforced, CORS). Scoped IAM user `boutique-media-staging` created and its keys are wired into the Railway `api`/`worker` services (not root — root was only used for the one-time account-level bootstrap). Billing guardrail is an AWS Budgets budget (`boutique-platform-monthly`, $50/mo, 80%-actual/100%-forecasted email alerts) rather than a CloudWatch billing alarm — Budgets doesn't need the console-only "receive billing alerts" preference toggle that a CloudWatch alarm does, so it's the CLI-scriptable equivalent. **Full presign → upload → confirm → signed-GET smoke test is green against real S3** (byte-identical round trip) — see `docs/infra-runbook.md`. Along the way, found and fixed a real bug in `Backend/app/storage/s3.py`: `generate_presigned_post()` was defaulting to the legacy global S3 endpoint, which il-central-1 (an opt-in region) rejects outright; MinIO-based tests never caught it because that path always sets an explicit endpoint. **F10's spec can now proceed.** Feature 2 Task 2 (Railway staging deploy) was also completed in this pass — see the E1 epic. What's still open: bucket CORS `AllowedOrigins` and the Railway `BASE_DOMAIN` are placeholders (`*.boutique-platform.invalid`) pending item #2 below. |
| 2 | Production domain | not-started | staging DNS naming, Route 53 zone, production | **Name decided 2026-07-29 (F30): `modryn.co.il`**, wildcard `*.modryn.co.il` — `.planning/architecture.md`, the ROADMAP and E1 now say so instead of the `ourbrand` placeholder. The *registration* is still the user's to file and nothing here is bought yet. `.co.il` may require Israeli-entity eligibility — confirm registrar rules before committing, and check `modryn.co.il` is actually free. A separate cheap staging domain is an acceptable stopgap (buy now if the production domain will take time). |
| 3 | Grow (Meshulam) merchant account | not-started | E4 #17–18 (payments), deposit flows | Needs Israeli business registration + bank account docs. Longest lead time — file ASAP. Per-tenant merchant accounts: the pilot boutique files its own; platform needs sandbox access for E4 development. |
| 4 | SMS sender-ID / route registration | **blocked — needs the user** | E3 #11 real sends, pilot launch (development is unblocked: F11 ships fake + unconfigured adapters) | **Provider decision made 2026-07-28: Twilio** (comparison in `.planning/specs/sms-foundation.md`). It is the only option with verified pricing, a documented Israel sender-ID path, webhooks, self-serve signup and test credentials; 019 is the runner-up above ~2–3k msgs/month. **Action now:** create a Twilio account, upgrade off trial (trial cannot use alphanumeric senders), then Console → Messaging → Senders → Alphanumeric Sender IDs. Have ready: **sender ID = `MODRYN`** (decided 2026-07-29 in F30 — 6 Latin chars, inside the ≤11 limit, a brand name rather than the INFO/SMS generics Twilio rejects), legal business name + address, use-case "transactional: OTP verification, booking confirmations, appointment reminders", 2–3 sample Hebrew bodies, est. volume 200–500/month. **Lead time ~1 week.** Verify at signup: any Israel registration fee, whether an Israeli business number is required, and that one registration covers all four MNOs. |
| 5 | Meta Business / WhatsApp Business API verification | not-started | E10 #2 (WhatsApp migration) | ROADMAP commits to starting Meta business verification **during v1** — multi-week lead time. Start-by trigger: E4 kickoff at the latest. |

## Status legend
`not-started` → `filed` (application submitted, waiting) → `approved` (credentials in hand) · `blocked` (needs user input/docs)

## What the user needs to do now

1. **AWS**: done — account created, il-central-1 opted in, both buckets provisioned, IAM keys in Railway env, billing budget set, smoke test green. Nothing further needed from the user here; F10's spec can proceed.
2. **Domain**: the name is decided (`modryn.co.il`) — what is left is to check availability + `.co.il` registrar eligibility and register it; if slow, buy a staging domain immediately so F2 Tasks 3/5 can proceed.
3. **Grow**: start the merchant application for the pilot boutique + request sandbox/developer access. This is the long pole for E4.
4. **SMS**: wait for the F2 Task 1 comparison (days, not weeks), then file the sender-ID registration with the recommended provider.

## Decisions record

- Brand name: **MODRYN** (2026-07-29, F30). Production domain `modryn.co.il`; SMS alphanumeric sender ID `MODRYN`. Neither is registered yet — see rows 2 and 4.
- SMS provider: _pending F2 Task 1 comparison._
- Staging wildcard TLS host: _pending Railway wildcard-domain support check (fallback: Cloudflare front)._
- il-central-1 service availability: confirmed 2026-07-27 — region opt-status `ENABLED`, S3 available and in use.
