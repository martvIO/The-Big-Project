# MODRYN Program Loop — State

Single source of truth for the autonomous feature loop. Any session continues the run with `/modryn-loop` (see `.claude/commands/modryn-loop.md`). This file is updated by the loop at coarse checkpoints — feature started, PR opened, merged, parked — via `docs(planning)` commits on `main`.

**Do not hand-edit while the loop is mid-feature.** Read it, then let the loop write it.

Status values: `queued` · `specing` · `building` · `in-review` · `pr-open` · `ci-fix` · `merged` · `parked` · `failed`

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
  interview: .planning/epics/interview-2026-07-29.md

current: F30

queue:
  # ---- cross-cutting ----
  - id: F30
    slug: modryn-branding
    epic: cross
    title: MODRYN platform branding
    status: building
    branch: feature/modryn-branding
    deps: []
    attempts: 1

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
      Spec Gate 1 approved; design deck accepted by critic 2026-07-29 with DRAFT
      Hebrew awaiting user sign-off in the interview. Resume the existing branch.
  - id: F15
    slug: owner-booking-management
    epic: E3
    title: Owner booking management
    status: queued
    deps: [F13, F16]

  # ---- E4 (payment half hard-blocked on the Grow merchant account) ----
  - id: F20
    slug: ppl-compliance
    epic: E4
    title: PPL compliance build
    status: queued
    deps: [F13]
    note: the only E4 feature buildable without the gateway
  - id: F17
    slug: gateway-credential-management
    epic: E4
    title: Gateway credential management
    status: parked
    deps: [F7]
    blocker: "Grow merchant account not filed — external-applications.md, user-only"
  - id: F18
    slug: grow-payment-sessions
    epic: E4
    title: Grow payment sessions & webhooks
    status: parked
    deps: [F17]
    blocker: "inherits F17"
  - id: F19
    slug: deposit-booking-flow
    epic: E4
    title: Deposit booking flow
    status: parked
    deps: [F7, F16, F18]
    blocker: "inherits F18"
  - id: F21
    slug: hardening-audits-uat
    epic: E4
    title: Hardening, audits & pilot UAT
    status: parked
    deps: [F16, F15, F20]
    blocker: "runs last across all of v1"

  # ---- E5 growth ----
  - id: F22
    slug: waitlist-join
    epic: E5
    title: Waitlist join + entries model
    status: queued
    deps: [F12, F13, F14]
  - id: F24
    slug: client-portal
    epic: E5
    title: "Client portal: OTP login, My Bookings, .ics, bell"
    status: queued
    deps: [F11, F13, F16]
  - id: F25
    slug: platform-console
    epic: E5
    title: Web platform console (replaces v1 CLI)
    status: queued
    deps: [F6]
  - id: F27
    slug: toggle-matrix-ui
    epic: E5
    title: Full feature-toggle matrix UI
    status: queued
    deps: [F7]
  - id: F23
    slug: waitlist-auto-reallocation
    epic: E5
    title: Auto-reallocation loop
    status: queued
    deps: [F22, F16, F19]
    note: >-
      Deposit interplay depends on F19. If payments are still blocked when this
      is reached, build the non-deposit cascade per the interview ruling.
  - id: F28
    slug: dress-reservation
    epic: E5
    title: Date-bound dress reservation semantics
    status: queued
    deps: [F8, F13]
    note: needs the pilot purchase/rental/made-to-order answer from the interview
  - id: F26
    slug: self-serve-signup
    epic: E5
    title: Self-serve boutique signup + gateway onboarding
    status: parked
    deps: [F25, F4, F17]
    blocker: "inherits F17; public launch additionally gated by F29"
  - id: F29
    slug: pre-scale-gate
    epic: E5
    title: "Pre-scale gate: refund automation, k6, Redis caching"
    status: parked
    deps: [F18, F21]
    blocker: "inherits F18"

  # ---- E6..E10: defined after the interview; F31-F49 appended by the epic generator ----

user_actions:                   # only the human can clear these; every report re-nags
  - "Buy the modryn.co.il domain (external-applications.md #2) — unblocks F2 staging"
  - "File the Grow merchant application (#3) — unblocks F17, F18, F19, F26, F29"
  - "Register SMS sender ID 'MODRYN' (#4) — required before any real SMS sends"
```

## Run report

_Written when the queue is exhausted._
