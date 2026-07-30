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

current: F16

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
    status: building
    branch: feature/booking-comms
    deps: [F13]
    attempts: 1
    note: >-
      Spec Gate 1 approved; design deck critic-accepted 2026-07-29; Hebrew copy
      approved as drafted (Interview Q5) and the short-notice reminder resolved
      (Q4: send immediately, drop «מחר», one date-led body). Branch exists with
      docs commits only — no code yet. Resume it, do not recreate.
  - id: F15
    slug: owner-booking-management
    epic: E3
    title: Owner booking management
    status: queued
    deps: [F13, F16]
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

  # ---- E6..E10: appended from the epic files (F31-F49); E7 precedes E8 per Interview Q12 ----

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
