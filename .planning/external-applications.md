# External Applications Tracker — standing risk until all approved

**Owner**: user (only the user can file these) · **Re-flag rule**: every feature cycle re-checks this file until every row is `approved`.
Created 2026-07-22 by E1 Feature 2. Lead times are multi-week — filing order is the critical path to the pilot.

| # | Item | Status | Blocks | Notes |
|---|------|--------|--------|-------|
| 1 | AWS account + il-central-1 opt-in | approved | E2 #8 (S3 upload), E4 skeleton, production | **Done 2026-07-27.** Account `849279003056`, `il-central-1` opt-status `ENABLED`. Both buckets live and correctly configured (versioning, public access blocked, bucket-owner-enforced, CORS). Scoped IAM user `boutique-media-staging` created and its keys are wired into the Railway `api`/`worker` services (not root — root was only used for the one-time account-level bootstrap). Billing guardrail is an AWS Budgets budget (`boutique-platform-monthly`, $50/mo, 80%-actual/100%-forecasted email alerts) rather than a CloudWatch billing alarm — Budgets doesn't need the console-only "receive billing alerts" preference toggle that a CloudWatch alarm does, so it's the CLI-scriptable equivalent. **Full presign → upload → confirm → signed-GET smoke test is green against real S3** (byte-identical round trip) — see `docs/infra-runbook.md`. Along the way, found and fixed a real bug in `Backend/app/storage/s3.py`: `generate_presigned_post()` was defaulting to the legacy global S3 endpoint, which il-central-1 (an opt-in region) rejects outright; MinIO-based tests never caught it because that path always sets an explicit endpoint. **F10's spec can now proceed.** Feature 2 Task 2 (Railway staging deploy) was also completed in this pass — see the E1 epic. What's still open: bucket CORS `AllowedOrigins` and the Railway `BASE_DOMAIN` are placeholders (`*.boutique-platform.invalid`) pending item #2 below. |
| 2 | Production domain | **✅ APPROVED — registered 2026-07-31** | (unblocked) | **`modryn.co.il` is BOUGHT.** Registrar **Domain The Net Technologies** (domainthenet.com), registrant Maroun Issa (Haifa), expires **2027-07-31**. Registrar nameservers: `ns1/ns2/ns3.dtnt.info`. **Ruling 2026-07-31: the apex domain is used directly — tenants live at `{slug}.modryn.co.il`, not under a `staging.` prefix.** Rationale: tenant URLs become permanent on day one, and a later infra move (Railway → AWS) is then a DNS change that leaves every boutique's URL untouched. A `*.staging.modryn.co.il` environment can be added later for pre-release testing. **Railway wildcard domain already created** (`*.modryn.co.il`, id `e834bf09-9c5d-4eba-86ac-25e7e5865724`, service `api`) and `BASE_DOMAIN=modryn.co.il` is live on both services. **Awaiting the user to add 3 DNS records at DomainTheNet** — see "DNS records to add" below. ⚠️ The domain-management password was pasted into a chat transcript on 2026-07-31 — **rotate it**; it controls nameservers and transfers. |
| 3 | Production payment processor (Israeli PSP) | **not-started — no longer blocking E4** | live deposit money only | **SUPERSEDED for development 2026-07-31.** The user supplied working **Lemon Squeezy** credentials and ruled LS **test mode** is E4's engine, behind F17's provider-agnostic port. That unblocks F17/F18/F19 entirely — they can be built, demoed and tested with no Israeli merchant account. What LS **cannot** do is carry real money here: it is merchant-of-record, while the deposit is legally the *boutique's* (`architecture.md:13` locks per-tenant merchant accounts; `e10-scale-polish.md:86` forbids platform collection of boutique deposits) and the boutique owes the Israeli receipt. So a production PSP is still needed **before live money** — Grow (Meshulam) remains the leading candidate (Israeli, per-tenant merchant accounts, hosted page) but the decision is open; Tranzila and Cardcom are the usual alternatives. Whichever wins is one adapter file behind the same port. Lead time is still weeks (Israeli business registration + bank docs), so file when the pilot date firms up, not before. |
| 4b | Twilio credentials (development) | **partial — needs 2 values** | F54 (Twilio adapter) | **2026-07-31**: the user supplied an API key pair (`SK…` + secret) and a phone-number resource SID (`PN…`), now in `Backend/.env`. **Still missing:** (a) the **Account SID** (`AC…`) — Twilio's REST path is `/2010-04-01/Accounts/{AccountSid}/Messages.json`, so the key pair authenticates but names no account; (b) the **number itself in E.164** (`+972…`) or a Messaging Service SID (`MG…`) — a `PN…` SID identifies the resource and is **not** accepted as `From`. Both are one copy-paste from the Twilio console. Until then `SMS_PROVIDER` stays unset and OTP send answers 503, which is a supported state. Note this is a *long-code* send; the alphanumeric `MODRYN` sender in row 4 is still required before production. **Secrets were pasted into a chat transcript — rotate after wiring.** |
| 4 | SMS sender-ID / route registration | **blocked — needs the user** | E3 #11 real sends, pilot launch (development is unblocked: F11 ships fake + unconfigured adapters) | **Provider decision made 2026-07-28: Twilio** (comparison in `.planning/specs/sms-foundation.md`). It is the only option with verified pricing, a documented Israel sender-ID path, webhooks, self-serve signup and test credentials; 019 is the runner-up above ~2–3k msgs/month. **Action now:** create a Twilio account, upgrade off trial (trial cannot use alphanumeric senders), then Console → Messaging → Senders → Alphanumeric Sender IDs. Have ready: **sender ID = `MODRYN`** (decided 2026-07-29 in F30 — 6 Latin chars, inside the ≤11 limit, a brand name rather than the INFO/SMS generics Twilio rejects), legal business name + address, use-case "transactional: OTP verification, booking confirmations, appointment reminders", 2–3 sample Hebrew bodies, est. volume 200–500/month. **Lead time ~1 week.** Verify at signup: any Israel registration fee, whether an Israeli business number is required, and that one registration covers all four MNOs. |
| 5 | Meta Business / WhatsApp Business API verification | not-started — **deliberately deferred to last** | E10 #2 (WhatsApp migration) | ROADMAP commits to starting Meta business verification **during v1** — multi-week lead time. **User ruling 2026-07-31: this is the LAST step; do not re-nag before F46.** Accepted consequence: F46 waits on the verification clock at the very end rather than overlapping it with the build. |

## DNS records to add at DomainTheNet (item #2, pending)

Railway issued these when `*.modryn.co.il` was created. **All three are required** — a wildcard
domain will not validate without the TXT, which is the usual reason a certificate hangs on
"issuing" for days.

| Type | Name / Host | Value |
|---|---|---|
| CNAME | `*` | `u12mz5w2.up.railway.app` |
| CNAME | `_acme-challenge` | `u12mz5w2.authorize.railwaydns.net` |
| TXT | `_railway-verify` | `railway-verify=2f2d75f26795dc4db5744bc206c6fa423dcf42064f7b354c0ea0bf1f66b97ef8` |

Notes: the `*` CNAME covers `{slug}.modryn.co.il` for every tenant but **not** the apex —
`modryn.co.il` itself stays unrouted until there is a marketing page to serve, which is
deliberate (the tenant resolver 404s an apex request anyway). Certificate issuance takes
hours once the records resolve. Verify progress with
`railway domain status e834bf09-9c5d-4eba-86ac-25e7e5865724 --service api`.

**Still to do once DNS is live:** update both S3 buckets' CORS `AllowedOrigins`, which still
carry the `*.boutique-platform.invalid` placeholder (`docs/infra-runbook.md:55-59`).

## Status legend
`not-started` → `filed` (application submitted, waiting) → `approved` (credentials in hand) · `blocked` (needs user input/docs)

## What the user needs to do now

1. **AWS**: done — account created, il-central-1 opted in, both buckets provisioned, IAM keys in Railway env, billing budget set, smoke test green. Nothing further needed from the user here; F10's spec can proceed.
2. **Domain**: ✅ bought 2026-07-31. **What is left is one paste job**: add the three DNS records above in DomainTheNet's control panel. Then rotate the domain password (it went through a chat transcript).
3. **Twilio (2 values)**: paste the **Account SID** (`AC…`) and the **phone number in E.164** from the Twilio console. Everything else for F54 is already wired.
4. **Rotate**: the Lemon Squeezy API key + webhook secret and the Twilio API key secret were pasted into a chat transcript. Regenerate both once the adapters are green.
5. **Payment processor**: no longer urgent — LS test mode covers all of E4's build. File the Israeli PSP application when the pilot date firms up (see row 3).
6. **SMS sender ID**: still needed before *production* sends (row 4); development runs on the long-code number.

## Decisions record

- Brand name: **MODRYN** (2026-07-29, F30). Production domain `modryn.co.il`; SMS alphanumeric sender ID `MODRYN`. Neither is registered yet — see rows 2 and 4.
- SMS provider: _pending F2 Task 1 comparison._
- Staging wildcard TLS host: **RESOLVED 2026-07-31 — Railway supports wildcard custom domains with automatic TLS.** Adding `*.modryn.co.il` yields two CNAME records (the wildcard + `_acme-challenge`) and one TXT record; **all three are required** — a wildcard will not verify without the TXT. Certificate issuance takes hours, occasionally a day. If DNS is fronted by Cloudflare: SSL mode must be **Full** (not Strict), and proxying must be **OFF** (grey cloud) on the `_acme-challenge` record or issuance hangs. No Cloudflare front is required — the registrar's own DNS is enough, since the only need is a wildcard A/CNAME. Source: https://docs.railway.com/networking/domains/working-with-domains
- il-central-1 service availability: confirmed 2026-07-27 — region opt-status `ENABLED`, S3 available and in use.
