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
| E7 | Staff Coordination: Fitting Rooms & SOS Paging | 9 | E6 | — |
| E8 | Workforce: Weekly Scheduler & HR Directory (full) | 10, 11.3 (full) | E6 | — |
| E9 | Alterations Workshop & Capacity | 11.1, 11.2, 11.4 | E5, E7, E8 | — |
| E10 | Scale & Polish: Arabic, WhatsApp, Video, Billing | cross-cutting | E5+ | — |

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
| 8 | Catalog management (dress CRUD, variants, statuses, S3 + presigned image upload) | E2 | 5 | M |
| 9 | RTL design system & tokens (`packages/ui`, `/spartan:ux` design gate, AA contrast) | E2 | 1 | M |
| 10 | Storefront browse (catalog grid + dress pages on tenant subdomain) | E2 | 4, 7, 8, 9 | M |
| 11 | SMS foundation (provider, NotificationService, message_log, OTP send/verify primitive) | E3 | 2, 3 | M |
| 12 | Availability & slot engine (rules → materialized slots, Israeli week) | E3 | 7 | M |
| 13 | Booking core API (dual-path model, **OTP-verified customer phone**, terms acceptance, concurrency-safe claiming, attendance-confirmed field) | E3 | 7, 11, 12 | L |
| 14 | Storefront booking UI (both paths, incl. OTP step) | E3 | 10, 13 | M |
| 15 | Owner booking management (list + day filter, status transitions, **owner reschedule**, edit-phone + resend-link remedy) | E3 | 13 | M |
| 16 | Booking comms lifecycle (confirmation SMS **with manage/cancel link**, owner-change/reschedule notifications, 24h reminder worker, tokenized confirm/cancel page) | E3 | 13 | M |
| 17 | Gateway credential management (per-tenant Grow creds, KMS-encrypted, validation ping, **receipt auto-issuance verified**) | E4 | 2, 7 | S |
| 18 | Grow payment sessions & webhooks (hosted page **J4 charge**, signature-verified + replay-protected webhook, sandbox E2E) | E4 | 17 | M |
| 19 | Deposit booking flow (pending-payment hold + sweeper, refund-due/forfeit decision + owner task; refunds executed manually in Grow console at pilot volume) | E4 | 7, 16, 18 | M |
| 20 | PPL compliance build (consent capture, privacy notice + DPA artifacts, PII-scrub job, retention jobs) — runs parallel to 17–19 | E4 | 13 | M |
| 21 | Hardening, audits & pilot UAT (in-repo security checklist green, backups + restore drill, WAF/headers/dep-scanning, IS 5568 a11y audit, UAT sign-off) | E4 | all | M |

### v1 definition of done

- A real boutique lives at `{slug}.ourbrand.co.il`; tenants are provisioned/suspended via the audited CLI.
- A customer completes both booking paths in Hebrew RTL, **verifying their phone via one-shot OTP**, accepting the versioned terms.
- Deposits-on path: booking confirms only after a signature-verified Grow webhook; **an unpaid hold expires and its slot becomes rebookable; an in-window cancellation is recorded refund-due (and refunded); an out-of-window one is forfeited per the accepted terms version; a receipt is issued for every charge**.
- Deposits-off path: **a booking on a no-deposit appointment type confirms immediately** and triggers the confirmation SMS.
- Confirmation SMS arrives immediately **with the manage/cancel link**; the 24h reminder lands with confirm/cancel; owner cancel/reschedule notifies the customer by SMS.
- Owner manages catalog, hours, terms, and bookings (incl. reschedule with deposit carry-over) from `/manage`.
- Cross-tenant CI isolation suite green; **`.planning/security-checklist-v1.md` fully checked**; IS 5568 accessibility audit passed; backup restore drilled; pilot UAT signed off.

### Explicitly deferred out of v1

Waitlist + auto-reallocation loop · client OTP dashboard + `.ics` links + client bell (v1 customers use the tokenized SMS link) · self-serve boutique signup + web platform console (v1 = CLI) · refund-API automation + k6 load pass (before multi-tenant onboarding) · all in-store real-time (QR queue, shift board, SOS, staff bell) · weekly scheduler + full HR directory · entire alterations module · Arabic strings, WhatsApp, video reels, analytics · calendar-view UI for owner bookings · automated platform billing (manual invoices meanwhile).

**Dropped by stakeholder decision (recorded):** email-verification client login (PRD §5 offered "SMS OTP *or* email") — the platform is OTP-only. Two-way Google/Apple calendar sync — replaced by `.ics` links (E5).

---

## Deferred epics — feature lists (spec'd when their phase starts)

### E5 — Growth: Waitlist, Client Dashboard, Self-Serve Signup & Console
1. Waitlist join (storefront, full-day path) + entries model
2. Auto-reallocation loop: sequential offers, expiry cascade, atomic claim (race-safe per approved plan)
3. Client OTP login + "My Bookings" dashboard + `.ics` links + **client-side notification bell**
4. Self-serve boutique signup (subdomain claiming, reserved slugs) + **web platform console** (replaces v1 CLI) + gateway-connect onboarding
5. Full feature-toggle matrix UI (§2 grid)
6. Refund-API automation + k6 load pass + Redis slug/config caching (pre-scale gate)
7. **Date-bound dress reservation semantics** (מוזמן לתאריך מסוים) — owning feature for the pilot's purchase/rental/made-to-order decision

### E6 — In-Store Real-Time: HR Core, QR Queue & Shift Board
1. **HR directory core**: staff records, roles (reception/seamstress/sales), per-staff logins, manual "on shift now" marking (interim until E8 roster derives it)
2. Realtime foundation: Pusher channels, server-side channel auth, versioned events, board-state refetch
3. QR walk-in check-in (form, dedup by phone, queue position)
4. Shift-manager live board: staff status with roles, queue view, dispatch action
5. **Staff** in-app notification bell (client bell is E5 #3)

### E7 — Staff Coordination: Fitting Rooms & SOS *(depends on E6 — staff identities/logins come from E6 #1)*
1. Fitting-room registry + staff↔client↔room↔dress assignment model (rich staff cards)
2. SOS paging: targeted page to on-shift colleague or shift manager, live alert, resolution flow

### E8 — Workforce: Weekly Scheduler & HR Directory (full)
1. HR directory full: photos, shift-manager eligibility, offboarding (operational history **retained** per §11.3; PII scrub only after legal retention window, via E4 #20 retention jobs)
2. Staff availability submission (3-tier shifts, weekly window)
3. Roster builder: targets per shift/role, shortage validation, manual override; published roster **replaces E6's manual on-shift marking** as the "current shift" source

### E9 — Alterations Workshop *(depends on E5 #3 for dashboard/.ics linkage, E7, E8)*
1. Job intake + lifecycle pipeline (5 states, timestamped) — includes per-job **effort-estimate field** (PRD gap fix)
2. Seamstress capacity model + deadline-aware overload alerts (bride-date hard priority) + **manual reallocation: reassign / split load / expedite from the matrix** (§11.2)
3. Multi-fitting scheduling (fitting slots from E3 slot engine, linked to client dashboard + `.ics`)
4. Live workshop board + owner throughput analytics

### E10 — Scale & Polish
1. Arabic storefront strings + comms templates
2. WhatsApp Business API migration (Meta verification started during v1)
3. Video reels + media pipeline (transcode, CDN)
4. Automated platform billing for tenants
5. Storefront SEO/prerendering · owner calendar-view polish

---

## Standing risks (tracked across all epics)

- **Two external lead-time items start in Feature 2, week 1**: the Grow merchant-account application **and Israeli SMS sender-ID/route registration** — both can take weeks and both gate the v1 DoD.
- **Cross-tenant leakage** is the existential risk — the CI isolation suite (Feature 3) is permanent and blocking from the first migration onward.
- Open product questions to resolve with the pilot boutique **before E3 spec**: slot capacity model details (parallel appointments/fitting rooms), bride-priority in the walk-in queue. Before E5 #7: dress "Reserved" semantics (purchase/rental/made-to-order).
- IS 5568 accessibility (WCAG 2.0 AA) is a legal requirement — enforced from Feature 9, audited in Feature 21. The gold-on-cream palette needs contrast resolution at the design gate.
- Israeli receipt (קבלה/חשבונית) obligation for J4 charges — verified against Grow's auto-issuance in Feature 17; if absent, receipt issuance enters Feature 19 scope.
