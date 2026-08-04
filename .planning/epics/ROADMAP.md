# Epic Roadmap — Bridal Boutique Multi-Tenant SaaS

**Created**: 2026-07-21 (rev 2 — post three-critic verification pass)
**Status**: **building** — v1 confirmed and in flight. 12 features merged, 1 in flight, 31 queued, 2 parked (last synced 2026-07-31).
**Source**: 11-section PRD + approved pressure-test plan (ported to `.planning/architecture.md`)

> **This file is the dependency map and the v1 contract. It is NOT the build queue.**
> `.planning/LOOP-STATE.md` is the single source of truth for what is built, what is next, and in what order — it is written by the loop at every checkpoint, this file is not. Where the two disagree, LOOP-STATE governs. The progress table below is a hand-synced snapshot; regenerate it from LOOP-STATE rather than editing it in place.

Ten epics, dependency-ordered. **E1–E4 = the proposed v1 slice** (pilot boutique live end-to-end). Every feature goes through its own `/spartan:spec` → `/spartan:plan` → `/spartan:build` cycle with TDD, a security pass, and gate review — no feature skips the pipeline.

> **BUILD ORDER OVERRIDE, 2026-07-31 — the floor-management program.** The epic order below still describes the *dependency* graph, but it is no longer the *build* order. By user ruling (`LOOP-STATE.md` → `rulings_2026_07_31`) a ten-feature floor-management program sits at the top of the queue and preempts the rest: **F34 → F57 → F36 → F33 → F58 → F59 → F37 → F41 → F42 → F60**, drawing from E6, E7 and E9 at once. It delivers the manager's floor terminal — live staff cards, fitting rooms, waitlist with atomic dispatch, SOS with a 30-second escalation, the atelier kanban with capacity load bars, QR self-check-in and a public queue wall board. Three features are new (**F57**, **F58**, **F59** in E6) plus **F60** (cross-cutting guide overlay). Remaining E4/E5/SMC work is *not* cancelled — the loop picks by file order, so F19, F53 and the rest resume automatically once the floor block is exhausted. **LOOP-STATE.md governs** wherever it and this file disagree.

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

## Progress — snapshot 2026-07-31

**12 merged · 1 building · 31 queued · 2 parked.** Regenerate from `LOOP-STATE.md`; do not maintain by hand.

### Shipped

| Feature | Epic | PR | What landed |
|---|---|---|---|
| F30 | cross | #20 | MODRYN platform branding |
| F31 | SMC | #22 | Staff roles + default-deny `/manage` gating, proven by a CI route walker |
| F16 | E3 | #21 | Booking comms lifecycle |
| F15 | E3 | #24 | Owner booking management |
| F51 | SMC | #25 | Staff management section (owner CRUD) |
| F55 | cross | #26 | FastAPI serves both SPAs same-origin — the frontends had never been hosted anywhere |
| F54 | E3-carveout | #27 | Twilio SMS adapter (real sends) |
| F52 | SMC | #28 | KPI dashboard (ops + customer) |
| F17 | E4 | #29 | Payment gateway port + credential management |
| F56 | cross | #30 | The "flaky" storefront focus test — which turned out to be a real shipped a11y bug |
| F18 | E4 | #31 | Lemon Squeezy test-mode adapter (sessions + webhooks) |
| **F34** | SMC | **#32** | **Live shift board + check-in (5s poll)** — floor program iteration 1 |

### In flight

**F57** `floor-staff-roles` — floor program iteration 2. Spec, design deck and plan are written and merged; the branch carries the `StaffRole` widening and migration `0015`. **Interrupted mid-build at plan Task 3** (usage limit, not a failure) — LOOP-STATE's `current:` block carries the exact resume point and names two uncommitted half-written files that must not be trusted as done.

### Parked — only the user can clear these

| Feature | Why |
|---|---|
| F20 `ppl-compliance` | Gate 1 awaiting USER approval — legal surface (Interview Q1), 5 questions at the spec's head. **This is the roadmap's widest blocker**: F21, F29, F38, F39, F40 and F45 are all unreachable behind it. |
| F32 | Subsumed into F34 (SMC ruling 3) — never build. Kept for the record. |

### The floor-management program — ✅ **COMPLETE 2026-08-04**

`F34 ✅ → F57 ✅ → F36 ✅ → F33 ✅ → F58 ✅ → F59 ✅ → F37 ✅ → F41 ✅ → F42 ✅ → F60 ✅`

All ten shipped, one PR each: F34 #32 · F57 #33 · F33 #36 · F36 #37 · F59 #38 · F41 #39 · F58 #40 · F37 #41 · F60 #42 · F42 #43. Nine of the ten landed on 2026-08-03/04; only F41 needed more than one CI run.

The manager's floor terminal now exists end to end: live staff cards with break status, a fitting-room registry whose occupancy is structurally exclusive, QR self-check-in feeding a waitlist with atomic take-next dispatch, a public wall board, SOS paging with a read-time 30-second escalation, the atelier kanban with capacity load bars, and a per-section guided walkthrough.

**Both deployment gates are cleared.** F33 and F59 merged behind a gate saying they were not launchable until F58 shipped — because F33 wrote queue tickets no surface rendered and F59's board would have frozen its top five names mid-morning. F58 discharged both.

**Epic E7 is complete** (F36 + F37). E6 is complete except F35 (the notification bell, deliberately dropped from F37's deps and still queued as a later durable surface). E9 has F41 + F42 done; F43 and F44 remain.

Detail per feature — including the defects each review caught — is in the `shipped:` blocks in `LOOP-STATE.md`'s `queue:`. Spec-time guidance is in `.planning/floor-program-review-2026-07-31.md`.

⚠ **Owed at the next epic boundary**, recorded in `LOOP-STATE.md`:
- the E7 boundary QA pass (full `make e2e` on `main`, zero-violation axe, a real-Chromium click-through, `/brain-sync`);
- the `known_vacuous` audit — jsdom ships no `<dialog>`, so six shipped `apps/manage` test files that mount a `Modal` may contain focus assertions that cannot fail.

### Still outside the loop's reach — user actions

Three DNS records at DomainTheNet are the only thing between staging and a live `{slug}.modryn.co.il`. Also open: rotate the three secrets pasted into a chat transcript on 2026-07-31, and send the Twilio Account SID + E.164 number. Full list in `LOOP-STATE.md` → `user_actions`.

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
