# Epic Roadmap — Bridal Boutique Multi-Tenant SaaS

**Created**: 2026-07-21 (rev 2 — post three-critic verification pass)
**Status**: awaiting v1 confirmation
**Source**: 11-section PRD + approved pressure-test plan (ported to `.planning/architecture.md`)

Ten epics, dependency-ordered. **E1–E4 = the proposed v1 slice** (pilot boutique live end-to-end). Every feature goes through its own `/spartan:spec` → `/spartan:plan` → `/spartan:build` cycle with TDD, a security pass, and gate review — no feature skips the pipeline.

---

## Program order

| Epic | Name | PRD § | Depends on | v1? |
|---|---|---|---|---|
| **E1** | Platform Foundation (tenancy, routing, auth, provisioning) | 1, 2 | — | ✅ |
| **E2** | Boutique Setup & Catalog | 2, 3 | E1 | ✅ |
| **E3** | Booking Engine & SMS Lifecycle | 4, 6 (partial) | E1, E2 | ✅ |
| **E4** | Deposits, Compliance & Pilot Hardening | 5 (partial) | E3 | ✅ |
| E5 | Growth: Waitlist, Client Dashboard, Self-Serve Signup & Console | 5, 6 (rest), 2 | E4 | — |
| E6 | In-Store Real-Time: HR Core, QR Queue & Shift Board | 7, 8, 11.3 (core) | E4 | — |
| E7 | Staff Coordination: Fitting Rooms & SOS Paging | 9 | E6 | — |  <!-- before E8 per Q12 -->
| E8 | Workforce: Weekly Scheduler & HR Directory (full) | 10, 11.3 (full) | E6 | — |
| E9 | Alterations Workshop & Capacity | 11.1, 11.2, 11.4 | E5, E7, E8 | — |
| E10 | Scale & Polish: Arabic, WhatsApp channel, Video, Billing | cross-cutting | E5+ | — |

---

## v1 slice (E1–E4) — 21 features

> Detailed briefs in the per-epic files: `e1-platform-foundation.md`, `e2-boutique-setup-catalog.md`, `e3-booking-and-comms.md`, `e4-deposits-and-hardening.md`.

| # | Feature | Epic | Depends on | Effort |
|---|---|---|---|---|
| 1 | Repo scaffolds & CI (FastAPI, Alembic, pnpm monorepo, test harness) | E1 | — | M |
| 2 | Staging env, wildcard DNS/TLS + external lead-time applications (Grow account, SMS sender-ID registration) | E1 | 1 | S |
| 3 | Tenant core + RLS isolation harness + permanent CI isolation suite | E1 | 1 | M |
| 4 | Subdomain routing & tenant resolution (direct DB lookup; no cache in v1) | E1 | 3 | S |
| 5 | Owner auth (owner-only accounts, subdomain-scoped sessions, audit log) | E1 | 3, 4 | M |
| 6 | Tenant provisioning CLI (audited create/suspend/list; operator password reset) | E1 | 5 | S |
| 7 | Owner settings & toggles + structured cancellation policy (refund-window fields versioned with terms) | E2 | 5 | M |
| 8 | Catalog management (dress CRUD, variants, statuses, S3 + presigned image upload) | E2 | 2, 5 | M |
| 9 | RTL design system & tokens (`packages/ui`, `/spartan:ux` design gate, AA contrast) | E2 | 1 | M |
| 10 | Storefront browse (catalog grid + dress pages on tenant subdomain) | E2 | 4, 7, 8, 9 | M |
| 11 | SMS foundation (provider, NotificationService, message_log, OTP send/verify primitive) | E3 | 2, 3 | M |
| 12 | Availability & slot engine (rules → materialized slots, Israeli week) | E3 | 7 | M |
| 13 | Booking core API (dual-path model, **OTP-verified customer phone**, terms acceptance, concurrency-safe claiming, attendance-confirmed field) | E3 | 7, 11, 12 | L |
| 14 | Storefront booking UI (both paths, incl. OTP step; **carries `GET /storefront/terms`** — the public read an anonymous customer needs before she can send a `terms_version`) | E3 | 9, 10, 11, 12, 13 | L |
| 15 | Owner booking management (list + day filter, status transitions, **owner reschedule**, edit-phone + resend-link remedy) | E3 | 13 | M |
| 16 | Booking comms lifecycle (confirmation SMS **with manage/cancel link**, owner-change/reschedule notifications, 24h reminder worker, tokenized confirm/cancel page) | E3 | 13 | M |
| 17 | Gateway credential management (per-tenant Grow creds, KMS-encrypted, validation ping, **receipt auto-issuance verified**) | E4 | 2, 7 | S |
| 18 | Grow payment sessions & webhooks (hosted page **J4 charge**, signature-verified + replay-protected webhook, sandbox E2E) | E4 | 17 | M |
| 19 | Deposit booking flow (pending-payment hold + sweeper, refund-due/forfeit decision + owner task; refunds executed manually in Grow console at pilot volume) | E4 | 7, 16, 18 | M |
| 20 | PPL compliance build (consent capture, privacy notice + DPA artifacts, PII-scrub job, retention jobs) — runs parallel to 17–19 | E4 | 13 | M |
| 21 | Hardening, audits & pilot UAT (in-repo security checklist green, backups + restore drill, WAF/headers/dep-scanning, IS 5568 a11y audit, UAT sign-off) | E4 | all | M |

### v1 definition of done

- A real boutique lives at `{slug}.modryn.co.il`; tenants are provisioned/suspended via the audited CLI.
- A customer completes both booking paths in Hebrew RTL, **verifying their phone via one-shot OTP**, accepting the versioned terms.
- Deposits-on path: booking confirms only after a signature-verified Grow webhook; **an unpaid hold expires and its slot becomes rebookable; an in-window cancellation is recorded refund-due (and refunded); an out-of-window one is forfeited per the accepted terms version; a receipt is issued for every charge**.
- Deposits-off path: **a booking on a no-deposit appointment type confirms immediately** and triggers the confirmation SMS.
- Confirmation SMS arrives immediately **with the manage/cancel link**; the 24h reminder lands with confirm/cancel; owner cancel/reschedule notifies the customer by SMS.
- Owner manages catalog, hours, terms, and bookings (incl. reschedule with deposit carry-over) from `/manage`.
- Cross-tenant CI isolation suite green; **`.planning/security-checklist-v1.md` fully checked**; IS 5568 accessibility audit passed; backup restore drilled; pilot UAT signed off.

### Explicitly deferred out of v1

Waitlist + auto-reallocation loop · client OTP dashboard + `.ics` links + client bell (v1 customers use the tokenized SMS link) · invite-code boutique signup + web platform console (v1 = CLI) · refund-API automation + k6 load pass (before multi-tenant onboarding) · all in-store real-time (QR queue, shift board, SOS, staff bell) · weekly scheduler + full HR directory · entire alterations module · Arabic strings, WhatsApp, video reels, analytics · calendar-view UI for owner bookings · automated platform billing (manual invoices meanwhile).

**Dropped by stakeholder decision (recorded):** email-verification client login (PRD §5 offered "SMS OTP *or* email") — the platform is OTP-only. Two-way Google/Apple calendar sync — replaced by `.ics` links (E5).

---

## Deferred epics — feature lists (spec'd when their phase starts)

### E5 — Growth: Waitlist, Client Dashboard, Self-Serve Signup & Console

> **Defined 2026-07-29** — detailed briefs in `e5-growth.md`. Renumbered from the local #1–#7 stub to the global scheme (**#22–#29**); the old #4 bundle is split into #25 (operator console) + #26 (self-serve signup).

22. Waitlist join (storefront, full-day path) + entries model
23. Auto-reallocation loop: sequential offers, expiry cascade, atomic claim (race-safe per approved plan)
24. Client OTP login + "My Bookings" dashboard + `.ics` links + **client-side notification bell**
25. **Web platform console** (replaces v1 CLI)
26. **Invite-code** boutique signup + gateway-connect onboarding (Q10 — no public funnel, no subdomain claiming, no longer gated by #29)
27. Full feature-toggle matrix UI (§2 grid)
28. **Date-bound dress reservation semantics** (מוזמן לתאריך מסוים) — owning feature for the pilot's purchase/rental/made-to-order decision
29. Refund-API automation + k6 load pass + Redis slug/config caching (pre-scale gate)

### E6 — In-Store Real-Time: HR Core, QR Queue & Shift Board

> **Defined 2026-07-30** — detailed briefs in `e6-instore-realtime.md`. Promoted from the local #1–#5 stub to the global scheme (**F31–F35**). Decisions from `interview-2026-07-30.md`.

31. **HR directory core**: staff records, roles (reception/seamstress/sales), **staff login by phone + SMS OTP** (Q11 — not email/password), manual "on shift now" marking (interim until F40's roster derives it)
32. Live-update substrate: versioned board state, tenant-private channels, full refetch on version gap — **~5s polling, no realtime vendor** (pre-decided #23; Pusher only if the pilot proves polling too slow)
33. QR walk-in check-in (form, dedup by phone, queue position) — one static printed QR per boutique
34. Shift-manager live board: staff status with roles, queue view, dispatch action — **novel pattern, prototype to the user at its design gate** (Q2)
35. **Staff** in-app notification bell, no push (client bell is F24)

### E7 — Staff Coordination: Fitting Rooms & SOS *(ships BEFORE E8 per Q12; staff identities come from F31)*

> **Defined 2026-07-30** — detailed briefs in `e7-fitting-rooms-sos.md`. Global scheme **F36–F37**.

36. Fitting-room registry + staff↔client↔room↔dress assignment model — one active assignment per room via a **partial unique index**, same concurrency discipline as the F13 slot claim
37. SOS paging: she picks a **role**, every on-shift staffer with it is paged, first to accept owns it; live alert + resolution flow

### E8 — Workforce: Weekly Scheduler & HR Directory (full)

> **Defined 2026-07-30** — detailed briefs in `e8-scheduler-hr.md`. Global scheme **F38–F40**. Sequenced after E7 (Q12).

38. HR directory full: photos, shift-manager eligibility, offboarding (operational history **retained** per §11.3; PII scrub 7 years after last day via F20's retention job)
39. Staff availability submission — owner-defined shift **templates** per weekday pre-filled from opening hours, weekly Sunday-start window, deadline as a tenant setting
40. Roster builder: targets per shift/role, shortage validation, manual override; published roster **supersedes F31's manual on-shift marking** as the current-shift source

### E9 — Alterations Workshop *(depends on F24 for dashboard/.ics linkage, E7, E8)*

> **Defined 2026-07-30** — detailed briefs in `e9-alterations.md`. Global scheme **F41–F44**.

41. Job intake + lifecycle pipeline (5 states as nullable timestamps) — per-job **effort estimate in minutes from five preset bands** (Q13)
42. Seamstress capacity model (**hourly**, walked back from the wedding date) + deadline-aware overload alerts + manual reassign / split / expedite — **advisory only**, and a **novel pattern needing a prototype at its design gate** (Q2, Q13, pre-decided #40)
43. Multi-fitting scheduling (fitting slots from the F12 slot engine, linked to the F24 client dashboard + `.ics`)
44. Live workshop board + owner throughput analytics

### E10 — Scale & Polish

> **Defined 2026-07-30** — detailed briefs in `e10-scale-polish.md`. Global scheme **F45–F49**. Largely independent features; F45 runs last.

45. Arabic storefront strings + comms templates — **translation and go-live**, not a retrofit: every feature from F30 onward ships untranslated `ar` keys as it lands (Q3). Needs a human Arabic reviewer for legal copy.
46. **WhatsApp as a per-boutique channel via Twilio** — SMS stays the default and authoritative channel (Q14; this supersedes the old "WhatsApp Business API migration" framing). Meta verification is a long-lead user action to file now.
47. Dress-page video + media pipeline (Cloudflare Stream) — clips on dress pages only, no storefront reels feed
48. Automated platform billing: flat base + metered messaging, 18% VAT, no tax-authority allocation-number API
49. Storefront SEO via **build-time prerender** + sitemap + per-tenant robots.txt (the storefront sits *alongside* her existing site — no custom domains) · owner calendar-view polish over the existing bookings API
---

## Standing risks (tracked across all epics)

- **Two external lead-time items start in Feature 2, week 1**: the Grow merchant-account application **and Israeli SMS sender-ID/route registration** — both can take weeks and both gate the v1 DoD.
- **Cross-tenant leakage** is the existential risk — the CI isolation suite (Feature 3) is permanent and blocking from the first migration onward.
- Open product questions to resolve with the pilot boutique **before E3 spec**: slot capacity model details (parallel appointments/fitting rooms), bride-priority in the walk-in queue. Before E5 #28: dress "Reserved" semantics (purchase/rental/made-to-order).
- Tenant resolution does one DB lookup per request with no rate limit until Feature 21; E5 #29's caching work should include a bounded negative-result cache (Feature 4 security review). API docs paths stay tenant-exempt until the Feature 21 gate.
- IS 5568 accessibility (WCAG 2.0 AA) is a legal requirement — enforced from Feature 9, audited in Feature 21. The gold-on-cream palette needs contrast resolution at the design gate.
- Israeli receipt (קבלה/חשבונית) obligation for J4 charges — verified against Grow's auto-issuance in Feature 17; if absent, receipt issuance enters Feature 19 scope.
