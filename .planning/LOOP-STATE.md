# MODRYN Program Loop — State

Single source of truth for the autonomous feature loop. Any session continues the run with `/modryn-loop` (see `.claude/commands/modryn-loop.md`). This file is updated by the loop at coarse checkpoints — feature started, PR opened, merged, parked — via `docs(planning)` commits on `main`.

**Do not hand-edit while the loop is mid-feature.** Read it, then let the loop write it.

Status values: `queued` · `specing` · `building` · `in-review` · `pr-open` · `ci-fix` · `merged` · `parked` · `failed`

`spec_gate: user` means Gate 1 is **not** self-approving for that feature — it is a money or legal surface, so the spec stops and waits (Interview Q1). Everything else self-approves.

```yaml
config:
  max_ci_fix_rounds: 2          # fix attempts per PR before parking
  max_feature_attempts: 2       # full restarts of a feature before failing it
  gating_jobs:                  # ALL must pass before merge; main has no branch protection
    - "Backend (lint, types, tests)"
    - "Frontend (lint, types, build)"
    - "Frontend E2E (Playwright + axe)"
  warn_only_jobs:               # usually red — ignore
    - "Code wiki drift (warn-only)"
    - "Dependency audits (warn-only)"
  interview: .planning/epics/interview-2026-07-30.md
  merge_gate: .claude/scripts/merge-gate.sh

current: F15

queue:
  # ---- cross-cutting ----
  - id: F30
    slug: modryn-branding
    epic: cross
    title: MODRYN platform branding
    status: merged
    pr: 20
    deps: []

  # ---- E3 close-out ----
  - id: F16
    slug: booking-comms
    epic: E3
    title: Booking comms lifecycle
    status: merged
    pr: 21
    deps: [F13]
    attempts: 1
    note: >-
      Spec Gate 1 approved; design deck critic-accepted 2026-07-29; Hebrew copy
      approved as drafted (Interview Q5) and the short-notice reminder resolved
      (Q4: send immediately, drop «מחר», one date-led body). Shipped as PR #21,
      merged 2026-07-30. Local gates were green (639 backend / 938 frontend /
      69 e2e, zero axe) and security + concurrency were reviewed by hand, but
      the multi-dimension agent review kept dying on API 529 — spec-conformance
      and frontend/a11y were never independently reviewed. Carried as debt into
      F15's review and the E3 epic-boundary QA pass.
  - id: F15
    slug: owner-booking-management
    epic: E3
    title: Owner booking management
    status: specing
    deps: [F13, F16]
    attempts: 1
    note: >-
      Q6: status management + owner reschedule (needs a slot picker in manage).
      Owner-CREATED bookings are explicitly OUT — no verified phone, no accepted
      terms; that earns its own spec.

  # ---- E4 — payments build against a fake gateway (Interview Q7) ----
  - id: F20
    slug: ppl-compliance
    epic: E4
    title: PPL compliance build
    status: queued
    deps: [F13]
    spec_gate: user
    note: >-
      Q8: ship a platform-written Hebrew default for the collection notice and
      DPA, overridable per boutique from settings. Not lawyer-reviewed.
      Retention periods per pre-decided #10. Also owns the retention job F40 depends on.
  - id: F17
    slug: gateway-port
    epic: E4
    title: Payment gateway port + credential management
    status: queued
    deps: [F7]
    spec_gate: user
    note: >-
      Q7 unparked this: build the provider-agnostic port plus a FAKE gateway
      now, exactly as F11 did for SMS. Real Grow credential validation waits
      for the merchant account, but the interface and its tests do not.
  - id: F19
    slug: deposit-booking-flow
    epic: E4
    title: Deposit booking flow
    status: queued
    deps: [F7, F16, F17]
    spec_gate: user
    note: >-
      Q7: build hold / expiry sweeper / webhook→confirmed against the fake
      gateway. The race most likely to be wrong (hold expiry vs a late webhook)
      does not depend on Grow, so it gets built and race-tested now.
  - id: F18
    slug: grow-adapter
    epic: E4
    title: Grow payment sessions & webhooks (real adapter)
    status: parked
    deps: [F17]
    spec_gate: user
    blocker: "Grow merchant account not filed — external-applications.md #3, user-only"
  - id: F21
    slug: hardening-audits-uat
    epic: E4
    title: Hardening, audits & pilot UAT
    status: queued
    deps: [F16, F15, F20]
    note: >-
      Pre-decided #11: rows needing no production environment (dependency
      scanning, security headers, accessibility pass) run now; the rest wait
      for staging, which waits on the domain purchase.

  # ---- E5 growth ----
  - id: F22
    slug: waitlist-join
    epic: E5
    title: Waitlist join + entries model
    status: queued
    deps: [F12, F13, F14]
    note: "Pre-decided #14: one entry = (tenant, day, appointment type) + OTP-verified phone, FIFO."
  - id: F24
    slug: client-portal
    epic: E5
    title: "Client portal: OTP login, My Bookings, .ics, bell"
    status: queued
    deps: [F11, F13, F16]
    note: >-
      Pre-decided #17: OTP-only login, per-booking .ics download, no two-way
      calendar sync. #18: the bell refreshes on page open — no polling loop.
  - id: F25
    slug: platform-console
    epic: E5
    title: Web platform console (replaces v1 CLI)
    status: queued
    deps: [F6]
    note: "Pre-decided #20: reuses the v1 CLI's audited command layer as its service layer."
  - id: F27
    slug: toggle-matrix-ui
    epic: E5
    title: Full feature-toggle matrix UI
    status: queued
    deps: [F7]
    note: "Pre-decided #19: tenants.settings JSONB under a toggles key, via F7's atomic merge."
  - id: F23
    slug: waitlist-auto-reallocation
    epic: E5
    title: Auto-reallocation loop
    status: queued
    deps: [F22, F16, F19]
    note: >-
      Pre-decided #12/#13/#15/#16: sequential offers with a 2-hour claim window,
      quiet hours 21:00–08:00, atomic conditional claim on the same partial
      unique index as direct booking, offers ride F16's scheduled_messages.
      Deposit interplay uses F19's fake-gateway hold.
  - id: F28
    slug: dress-reservation
    epic: E5
    title: Date-bound dress reservation semantics
    status: queued
    deps: [F8, F13]
    note: >-
      Q9 settled it: RENTAL. A real date range (wedding date + cleaning/return
      buffer) with an overlap check, so the storefront can say "unavailable
      12–18 Aug" and still take fittings on other dates.
  - id: F26
    slug: invite-signup
    epic: E5
    title: Invite-code boutique signup + gateway onboarding
    status: queued
    deps: [F25, F17]
    note: >-
      Q10 (against recommendation): INVITE CODES ONLY. No public signup funnel,
      no subdomain claiming, no captcha/rate-limit/slug-reclamation scope. This
      is smaller than the roadmap assumed, and it is no longer gated by F29.
  - id: F29
    slug: pre-scale-gate
    epic: E5
    title: "Pre-scale gate: refund automation, k6, Redis caching"
    status: parked
    deps: [F18, F21]
    spec_gate: user
    blocker: "refund automation needs the real Grow adapter (F18)"
    note: >-
      Pre-decided #21/#22: tenant-scoped cache keys plus a bounded negative
      cache; k6 targets derived from staging metrics at the 50-tenant horizon.
      The caching and load halves could be split out early if F18 stays blocked.

  # ---- E6..E10 (F31-F49). E7 precedes E8 per Interview Q12.
  # Slugs are placeholders until each spec names its own.
  # ---- E6 in-store real-time ----
  - id: F31
    slug: f31-placeholder
    epic: E6
    title: "Staff records, roles & phone-OTP staff login"
    status: queued
    deps: [F3, F5, F9, F11]
    note: >-
      Q11 (against recommendation): staff sign in by phone + SMS OTP, reusing F11. No work
      emails, no passwords. Costs an SMS per login and depends on sender-ID registration
      in production. Reuses staff_users.role.
  - id: F32
    slug: f32-placeholder
    epic: E6
    title: "Live-update substrate (versioned board state + polling)"
    status: queued
    deps: [F31]
    note: >-
      Pre-decided #23: NO realtime vendor. ~5s refresh; Pusher only if the pilot proves it
      too slow. #25: events are versioned hints, server is truth.
  - id: F33
    slug: f33-placeholder
    epic: E6
    title: "QR walk-in check-in"
    status: queued
    deps: [F5, F9, F10, F13, F20]
    note: >-
      Pre-decided #26: queue ticket by default, auto-deleted days after the visit, one
      opt-in marketing checkbox. #30: one static printed QR per boutique. Soft handoff
      with F20 on the consent column.
  - id: F34
    slug: f34-placeholder
    epic: E6
    title: "Shift-manager live board + dispatch"
    status: queued
    deps: [F31, F32, F33]
    note: >-
      Q2: NOVEL pattern — design gate requires a user-reviewed clickable prototype; does
      NOT self-approve. Pre-decided #28: E6 is done at queue + dispatch, no waiting-time
      analytics.
  - id: F35
    slug: f35-placeholder
    epic: E6
    title: "Staff in-app notification bell"
    status: queued
    deps: [F31, F32, F34]
    note: >-
      Pre-decided #32: in-app only. No browser push, no APNs/FCM.

  # ---- E7 fitting rooms & SOS (before E8, per Interview Q12) ----
  - id: F36
    slug: f36-placeholder
    epic: E7
    title: "Fitting-room registry + staff/client/room/dress assignment"
    status: queued
    deps: [F8, F13, F31, F32, F34]
    note: >-
      Pre-decided #31: one active assignment per room via a partial unique index — same
      concurrency discipline as the F13 slot claim.
  - id: F37
    slug: f37-placeholder
    epic: E7
    title: "SOS paging: role-targeted page, live alert, resolution"
    status: queued
    deps: [F31, F32, F35, F36]
    note: >-
      Pre-decided #29: she picks a ROLE; every on-shift staffer with it is paged; first to
      accept owns it. Rides F32's poll — the latency tradeoff is recorded in the epic's
      Risks.

  # ---- E8 weekly scheduler & full HR ----
  - id: F38
    slug: f38-placeholder
    epic: E8
    title: "HR directory full: photos, eligibility, offboarding"
    status: queued
    deps: [F8, F9, F20, F31]
    note: >-
      Pre-decided #34/#35: soft-delete, retain operational history, scrub PII 7 years
      after last day via F20's retention job.
  - id: F39
    slug: f39-placeholder
    epic: E8
    title: "Staff availability submission (templates + weekly window)"
    status: queued
    deps: [F7, F9, F11, F12, F31, F38]
    note: >-
      Pre-decided #33: owner-defined shift templates per weekday, pre-filled from opening
      hours. #36: weekly, Sunday-start, deadline is a tenant setting.
  - id: F40
    slug: f40-placeholder
    epic: E8
    title: "Roster builder + published roster as current-shift source"
    status: queued
    deps: [F9, F34, F37, F38, F39]
    note: >-
      The published roster supersedes F31's manual on-shift marking; the epic specifies
      the cutover and the no-roster-published week.

  # ---- E9 alterations workshop ----
  - id: F41
    slug: f41-placeholder
    epic: E9
    title: "Job intake + 5-state lifecycle + effort estimate"
    status: queued
    deps: [F8, F13, F31, F34]
    note: >-
      Q13: effort stored as minutes from five preset bands. Pre-decided #39: five states
      as nullable timestamp columns, not a status enum.
  - id: F42
    slug: f42-placeholder
    epic: E9
    title: "Seamstress capacity model + overload alerts + reallocation"
    status: queued
    deps: [F31, F40, F41]
    note: >-
      Q2: NOVEL pattern — design gate requires a user-reviewed clickable prototype; does
      NOT self-approve. Q13: hourly capacity walked back from wedding_date. Pre-decided
      #40: advisory only, every reallocation stays a human action.
  - id: F43
    slug: f43-placeholder
    epic: E9
    title: "Multi-fitting scheduling on the E3 slot engine"
    status: queued
    deps: [F12, F13, F16, F24, F41]
    note: >-
      Reuses the F12 slot engine and links to the F24 client portal for dashboard + .ics.
  - id: F44
    slug: f44-placeholder
    epic: E9
    title: "Live workshop board + owner throughput analytics"
    status: queued
    deps: [F32, F41, F42]
    note: >-
      The one place pre-decided #23 authorises assuming a realtime vendor exists; the
      no-vendor fallback is recorded.

  # ---- E10 scale & polish ----
  - id: F45
    slug: f45-placeholder
    epic: E10
    title: "Arabic strings + comms templates (go-live)"
    status: queued
    deps: [F9, F10, F14, F15, F16, F20, F24, F44, F46, F49]
    note: >-
      Q3: every prior feature ships untranslated ar keys, so this is translation +
      go-live, not a retrofit. Pre-decided #47: ar bundles on existing i18next, RTL reused
      wholesale. Needs a human Arabic reviewer for legal copy — user action.
  - id: F46
    slug: f46-placeholder
    epic: E10
    title: "WhatsApp as a per-boutique channel"
    status: queued
    deps: [F11, F16, F27]
    note: >-
      Q14 (against recommendation): SMS stays DEFAULT and authoritative; WhatsApp is
      opt-in per boutique. NOT a migration. Pre-decided #43: via Twilio, not Meta Cloud
      API. Meta verification is a user action with long lead time.
  - id: F47
    slug: f47-placeholder
    epic: E10
    title: "Dress-page video + media pipeline"
    status: queued
    deps: [F8, F9, F10]
    note: >-
      Q16: short clips on dress pages only, no storefront reels feed. Pre-decided #44:
      Cloudflare Stream.
  - id: F48
    slug: f48-placeholder
    epic: E10
    title: "Automated platform billing"
    status: queued
    deps: [F3, F11, F25, F46]
    spec_gate: user
    note: >-
      Q15: flat base + metered messaging from the existing per-tenant message log.
      Pre-decided #45: 18% VAT, no tax-authority allocation-number API — caps invoice
      amounts; recorded as a risk. Money surface, so Gate 1 stops (Q1).
  - id: F49
    slug: f49-placeholder
    epic: E10
    title: "Storefront SEO/prerender + owner calendar"
    status: queued
    deps: [F4, F8, F9, F10, F12, F15]
    note: >-
      Q17: the storefront sits ALONGSIDE her existing site — no custom domains, no certs.
      Pre-decided #46: build-time prerender + sitemap + per-tenant robots.txt, not SSR.
      #48: calendar layered over the existing bookings list API.

user_actions:                   # only the human can clear these; every report re-nags
  - "Buy the modryn.co.il domain (external-applications.md #2) — unblocks F2 staging and the F21 rows that need it"
  - "File the Grow merchant application (#3) — the longest lead time left; unblocks F18, then F29"
  - "Register SMS sender ID 'MODRYN' (#4) — required before any real SMS, including staff OTP login (Q11)"
  - "File Meta business verification for WhatsApp (pre-decided #42) — long lead time, needed before F46"
  - "Get counsel to review the F16 SMS bodies and the F20 privacy default before either goes live"
  - "Find a human Arabic reviewer for legal/policy copy before F45 goes live"
```

## Run report

_Written when the queue is exhausted._
