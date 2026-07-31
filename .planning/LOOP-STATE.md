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

current: F19                    # spec-only iteration (spec_gate: user). F52 merged (PR #28) 2026-07-31. F51 merged (PR #25). F15 merged (PR #24); E3 DONE — boundary QA passed 2026-07-30
                                # Queue reconciled 2026-07-30 for the finish-the-project run:
                                # 32 features reachable, 0 unreachable, 3 parked (F18/F29 external, F32 subsumed).
                                # Verified by simulating the pick rule to exhaustion — deps absent from this
                                # queue (F3-F14) are historical merged features, which is how the loop reads them.

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
    status: merged
    pr: 24
    deps: [F13, F16]
    attempts: 1
    note: >-
      Q6: status management + owner reschedule (needs a slot picker in manage).
      Owner-CREATED bookings are explicitly OUT — no verified phone, no accepted
      terms; that earns its own spec (now queued as F50).
      Spec written and Gate 1 self-approved 2026-07-30. Three adversarial review
      lenses returned 33 findings (5 blockers); 32 fixed, 1 rejected in writing.
      Effort revised M → L at Gate 1. Built in 18 TDD commits; dual review ran
      FOUR lenses (quality, security/concurrency, spec-conformance,
      frontend/a11y — the last two discharging F16's parked debt), 16 findings,
      each judged by two skeptics, 9 survived, one fix commit. Merged as PR #24
      2026-07-30, all three gating jobs green.
      TWO THINGS A LATER READER NEEDS. (1) F31 merged first and collided: both
      features had invented a NotAuthorizedError, and the rebase applied with no
      textual conflict, so Python's second binding silently left F31's class with
      no handler — every shipped role-gated 403 would have become a 500. CI's
      ruff F811 is what caught it. Resolved per shift-manager-console.md's
      pre-written contingency: F15 adopted require_role and dropped its copy.
      (2) That ruling admits shift_manager on all ten F15 routes, so Risk 2 (the
      owner-attested phone re-points a live SMS control link with no OTP) now
      extends to shift managers — F15's D20 guard was one of its three bounds and
      it is gone. Recorded in the spec.
      RULED 2026-07-30: the user ACKNOWLEDGED this as shipped. Owner and
      shift_manager may both correct a phone on their word alone, with no OTP on the
      new number. The nag is cleared from user_actions and is NOT to be re-raised as
      an open question. The F21 security audit is the scheduled re-check — it must
      re-derive the risk from scratch rather than treat this acknowledgment as a
      finding already closed.
  - id: F50
    slug: walk-in-bookings
    epic: E3-carveout
    title: Owner-created bookings (walk-in half first)
    status: queued
    deps: [F15, F34]
    note: >-
      Carved out of F15 by Interview Q6 and queued here because F15's spec found
      it load-bearing and the roadmap has no entry for it: a booking the owner
      creates has no bride-verified phone and no accepted terms, so the SMS
      control link would target an unverified number. It is also the only remedy
      path for F15's Risk 1 (a mis-tapped cancel is terminal, and the rebook has
      to come from somewhere). SPLIT by the SMC epic (2026-07-30, SMC-6): the
      walk-in half ships from the live board — a real booking with
      source='walk_in', NO manage token, NO SMS, NULL terms (DB CHECK keeps
      storefront rows non-null), checked_in_at at birth — the recorded danger
      (SMS link to an unverified number) evaporates because no link is minted.
      The remote/scheduled owner-create half (which DOES need the link, consent
      capture and a terms answer) stays open in this entry after SMC-6.

  # ---- E4 — payments build against a fake gateway (Interview Q7) ----
  - id: F20
    slug: ppl-compliance
    epic: E4
    title: PPL compliance build
    status: parked
    deps: [F13]
    spec_gate: user
    blocker: "Gate 1 — spec written 2026-07-30 and awaiting USER approval (legal surface, Interview Q1). 5 questions listed at the spec's head."
    spec: .planning/specs/ppl-compliance.md
    note: >-
      Q8: ship a platform-written Hebrew default for the collection notice and
      DPA, overridable per boutique from settings. Not lawyer-reviewed.
      Retention periods per pre-decided #10. Also owns the reusable retention job
      that F38 depends on — corrected 2026-07-30 from "F40", which was wrong: F40 is
      the E8 roster builder and has nothing to do with retention. The dependant is
      F38 (HR offboarding), whose pre-decided #34/#35 scrub of ex-staff PII 7 years
      after last day runs on this job. F33's walk-in queue-ticket auto-delete is a
      second consumer. Design the job as per-data-class machinery, not a booking sweeper.
  - id: F17
    slug: gateway-port
    epic: E4
    title: Payment gateway port + credential management
    status: merged
    pr: 29
    deps: [F7]
    attempts: 1
    spec_gate: user
    spec: .planning/specs/gateway-port.md
    note: >-
      Q7 unparked this: build the provider-agnostic port plus a FAKE gateway
      now, exactly as F11 did for SMS. The interface and its tests never needed
      a merchant account.
      GATE 1 APPROVED 2026-07-31 — all four questions answered, recorded in the
      spec's "Gate 1 resolutions" section. Q1 deposits-on-no-gateway: option (a),
      the storefront HIDES the deposit and books anyway (a dead calendar is worse
      than silently not collecting); F19 implements. Q2 KMS: accepted unchecked
      at merge, deferred per D3. Q3 payments retention: 7 years, matching
      pre-decided #10. Q4 late settlement on an expired hold: HONOUR the money and
      alert the owner — rebind if the seat is free, surface it to her if not;
      no refund() is added (D12 stands), F19 owns the rebind-or-alert behaviour.
      PROVIDER RULING same date: Grow is no longer E4's engine. Lemon Squeezy TEST
      MODE takes the seat FakeGateway was built for (see F18). Every "Grow" in the
      spec now reads "the production PSP, TBD" — that decision is deferred to
      before-live-money and is one adapter file, which is exactly what D5's
      adapter-declared credential_fields bought.
  - id: F19
    slug: deposit-booking-flow
    epic: E4
    title: Deposit booking flow
    status: specing
    deps: [F7, F16, F17]
    spec_gate: user
    note: >-
      Q7: build hold / expiry sweeper / webhook→confirmed against the fake
      gateway. The race most likely to be wrong (hold expiry vs a late webhook)
      does not depend on Grow, so it gets built and race-tested now.
  - id: F18
    slug: lemonsqueezy-adapter
    epic: E4
    title: Lemon Squeezy payment sessions & webhooks (test-mode adapter)
    status: specing
    spec: .planning/specs/lemonsqueezy-adapter.md
    attempts: 1
    deps: [F17]
    spec_gate: user
    note: >-
      UNPARKED 2026-07-31. Was "Grow adapter, blocked on a merchant account nobody
      had". The user supplied working Lemon Squeezy credentials and ruled LS TEST
      MODE is E4's engine behind F17's port, so this feature is now buildable with
      no Israeli merchant account.
      Scope: app/payments/lemonsqueezy.py implementing the F17 PaymentGateway
      protocol — create_session against the LS checkouts API, verify_webhook over
      the X-Signature HMAC-SHA256 header, validate_credentials as an authenticated
      store fetch. Migration widens 0012's CHECK to ('fake','lemonsqueezy').
      TWO BOUNDS THAT ARE NOT NEGOTIABLE. (1) TEST MODE ONLY: LS is
      merchant-of-record and the deposit is legally the BOUTIQUE's money
      (architecture.md:13 per-tenant merchants; e10-scale-polish.md:86 forbids
      platform collection of boutique deposits), so APP_ENV=production +
      payment_provider='lemonsqueezy' must be a boot failure until a production-PSP
      ruling exists — same shape as the fake-gateway guard. (2) The spec phase MUST
      verify LS's actual API shapes, signature header and error envelope against
      live docs (WebFetch), not from memory.
      Also: LS joins the F20 sub-processor disclosure list (ppl-compliance.md:334).
  - id: F21
    slug: hardening-audits-uat
    epic: E4
    title: Hardening, audits & pilot UAT
    status: queued
    deps: [F16, F15, F20]
    note: >-
      Pre-decided #11: rows needing no production environment (dependency
      scanning, security headers, accessibility pass) run now; the rest wait
      for staging, which waits on the domain purchase. The spec must therefore
      SPLIT: build the non-production rows as this feature, and record the
      production rows as a parked follow-up naming the domain as the blocker —
      do not let the whole feature park on staging.
      CARRIES ONE NAMED AUDIT ROW (from F15 Risk 2, acknowledged 2026-07-30):
      owner AND shift_manager can re-point a live SMS control link by typing a
      new phone, with no OTP. The user acknowledged this for the pilot; F21 must
      re-derive it from the code at production scale rather than treat the
      acknowledgment as a closed finding.

  # ---- Deploy: the frontends have never been hosted anywhere ----
  - id: F55
    slug: serve-spas-from-api
    epic: cross
    title: "FastAPI serves the built SPAs (same-origin hosting)"
    status: merged
    pr: 26
    deps: []
    attempts: 1
    claimed_by: >-
      Parallel build run started 2026-07-31, running BESIDE the F52 loop rather
      than through it. `current:` stays F52 and is not this run's to write —
      claims here are status-only. Run order: F55, F54, F17, F18, F19. F53 is
      deliberately left to the F52 session's loop.
    note: >-
      NEW 2026-07-31. The gap nobody had noticed: CI builds both React apps and
      then throws them away. Only the API is deployed, so the console and the
      storefront exist on developer machines and nowhere else. The domain is now
      bought and the Railway wildcard is created, which makes this the last piece
      between here and a URL a boutique can open.
      USER RULING 2026-07-31 after a written trade-off review: the API serves the
      built static files — SAME ORIGIN. Not a separate origin (Cloudflare Pages
      style), and the reason is specific to this codebase rather than taste:
      app/auth/cookies.py mints the session cookie with NO Domain attribute, so
      the browser itself refuses to send boutique A's session to boutique B's
      subdomain. A separate frontend origin forces Domain=.modryn.co.il to make
      credentialed cross-origin calls work, and that single change hands every
      tenant's cookie to every tenant's hostname — trading a browser-enforced
      isolation guarantee for one we would have to re-implement and never get
      wrong. It would also force dynamic wildcard CORS into a codebase that
      documents "no CORS, ever".
      Cloudflare stays available as a LATER pure addition, but only in front of
      the same origin (edge static + proxy /manage and /storefront through) —
      that costs no code change. Note for F20 if it ever happens: Cloudflare
      terminates TLS, so bride PII would transit their edge, which the
      il-central-1 data-residency decision has to account for.
      Scope: mount StaticFiles for each app, SPA-fallback to index.html per host
      (manage vs storefront is decided by which app the host maps to), leave every
      /manage, /storefront and /health route ahead of the catch-all, keep the
      security headers middleware outermost, and add a CI step that builds the
      SPAs into the image the deploy uploads. Must not break the Vite dev proxy.
      Watch: the storefront is anonymous and the console is not, so the fallback
      must never serve the console shell on a storefront host.

  # ---- E3 carve-out: the SMS adapter F11 deliberately deferred ----
  - id: F54
    slug: sms-twilio-adapter
    epic: E3-carveout
    title: Twilio SMS adapter (real sends)
    status: merged
    pr: 27
    deps: [F11]
    attempts: 1
    note: >-
      NEW 2026-07-31. F11 shipped the SmsSender port with fake + unconfigured
      adapters and recorded (sms-foundation.md:148-163) that "the Twilio adapter
      lands as its own small commit once the account and registered sender exist".
      The user supplied Twilio credentials 2026-07-31, so it lands now.
      Scope is genuinely small — the protocol is two members (is_configured,
      async send(phone, body) -> SendResult). app/notifications/twilio.py over the
      REST API with httpx (currently a DEV-only dep — promote it), widen
      settings.sms_provider's Literal to ["fake","twilio"], one elif in
      _build_sms_sender, and the production boot guard's parity case.
      Credentials follow the boto3 precedent: read from the process environment,
      never into Settings (.env.example documents the names).
      TWO VALUES STILL MISSING (external-applications.md row 4b): the Account SID
      (AC…) — the REST path is /Accounts/{AccountSid}/Messages.json so the API key
      pair authenticates but names no account — and the number in E.164, because a
      PN… resource SID is not accepted as `From`. Build against a faked transport
      regardless; the values only gate a live send.
      NOTE the hazard already anticipated: NotificationService._scrub exists
      because "several SMS SDKs echo the failing request — including the message
      body — in their exception". Twilio is exactly that shape; the scrub must be
      tested against a real Twilio error payload, not a synthetic one.
      Dev default stays SMS_PROVIDER=fake — real keys mean real SMS and real cost.
      Also: Twilio joins the F20 sub-processor disclosure list.

  # ---- SMC console finish (moved here 2026-07-30: user ruled SMC before E5) ----
  # F34 sits first so its prototype gate reaches the user on the very next
  # iteration and its review runs on the user's clock while F51-F53 build.
  - id: F34
    slug: shift-board-checkin
    epic: SMC
    title: "Live board + check-in (5s poll)"
    status: parked
    deps: [F15, F31]
    blocker: "Design gate — clickable prototype awaiting USER review (Interview Q2, novel pattern). Gate 1 self-approved; only the design gate is open."
    spec: .planning/specs/shift-board-checkin.md
    prototype: .planning/design/screens/shift-board/prototype.html
    note: >-
      SMC-5. Q2: NOVEL pattern — design gate requires a user-reviewed clickable
      prototype; does NOT self-approve. Pre-decided #28: done at queue + dispatch,
      no waiting-time analytics. Re-scoped by the SMC epic (2026-07-30): F32
      subsumed (client 5s poll of GET /manage/bookings?date=, no version field,
      pause on document.hidden); F33 no longer a dep (walk-ins become real
      bookings via F50) though F33 itself is still built later per the 2026-07-30
      ruling. Check-in = bookings.checked_in_at TIMESTAMPTZ column,
      NOT a fifth status — the CHECK, both partial unique indexes and E4's
      pending_payment widening stay untouched. Endpoints land on F15's owner router.
      Sequencing note: spec + prototype are authored, then the entry PARKS on the
      user's prototype review. It does not self-approve. Build resumes when the
      user says so; F51-F53 fill the wait.
  - id: F51
    slug: staff-management
    epic: SMC
    title: "Staff management section (owner CRUD)"
    status: merged
    pr: 25
    deps: [F31]
    attempts: 1
    note: >-
      SMC-2. Owner-only staff router (/manage/staff list/create/patch/soft-delete),
      guards: no self-deactivate, never remove the last live owner. Role-filtered
      nav table lands here. Deactivation is instantly effective (resolve_session
      re-reads staff_users per request) — no session sweep, do not build one.
      SHIPPED as PR #25, merged 2026-07-30, all three gating jobs green on the FIRST
      CI run (no fix round — unusual for a feature whose headline test is db-marked
      and therefore debuts on CI). NO MIGRATION: staff_users already carried every
      column, 0011 already CHECK-pins the role set, the email unique index is already
      partial on deleted_at IS NULL, and audit_log.action is unconstrained TEXT.
      THREE THINGS A LATER READER NEEDS.
      (1) The last-owner guard is a NAMESPACED per-tenant advisory lock taken BEFORE
      the read: pg_advisory_xact_lock(hashtext('staff:' || tenant_id)). The obvious
      single-statement UPDATE ... WHERE (SELECT count(*)) > 1 is UNSAFE under READ
      COMMITTED — two concurrent requests each read a snapshot lacking the other's
      uncommitted write, both see 2, both commit, tenant ends with zero owners and no
      error anywhere. A partial unique index cannot express this: an index says "at
      most one", the invariant is "at least one". The key is PREFIXED so staff edits
      do not serialize against public booking creates (booking/service.py uses the
      bare hashtext(tenant_id)). The asyncio.gather race test is db-marked: it is the
      single test that fails if the lock is dropped, and it only runs on CI.
      (2) Credential delivery is out of band by necessity, not by choice — there is no
      mailer in the backend and SMC ruling 1 removed SMS from the staff auth path. The
      owner types the password and tells the staffer; the console says so and never
      claims anything was sent. This is also WHY password reset is a PATCH field: the
      operator CLI's reset_owner_password carries role == OWNER in its WHERE clause, so
      without it a shift manager who forgets her password has no remedy in the product.
      (3) Review's best catch: a password write did not revoke the target's existing
      sessions, so a reset did not lock out whoever held the old credential. Fixed in
      a8355b5. F51 also adds one control beyond the epic's ask — a SELF password change
      requires current_password, turning a stolen owner session from a permanent
      takeover (remedy: an operator CLI ticket) into a session-TTL-bounded one.
  - id: F52
    slug: kpi-dashboard
    epic: SMC
    title: "KPI dashboard (ops + customer)"
    status: merged
    pr: 28
    deps: [F31]
    attempts: 1
    note: >-
      SMC-3. GET /manage/dashboard, Jerusalem window, both roles: bookings/week
      (Sunday-start buckets), no-show + cancellation rates, busiest types,
      new-vs-returning, repeat rate, FORWARD-ONLY 7-day slot utilization
      (historical capacity doesn't exist; snapshot job is the recorded upgrade
      path). No revenue until E4. Landing section for the console. No chart dep.
      SHIPPED as PR #28, merged 2026-07-31, all three gating jobs green. NO
      MIGRATION. Spec review ran 3 lenses -> 20 findings (1 blocker: the normative
      example payload shipped an in-progress week), all 20 fixed, none rejected.
      Code review ran 4 lenses -> 6 findings, 0 blockers, 1 MAJOR survived two
      skeptics. 1005 backend / 1138 frontend / 69 e2e green, zero axe violations.
      FOUR THINGS A LATER READER NEEDS.
      (1) Forward utilization calls materialize_slots with booked={}. The engine
      DROPS full slots on purpose ("a public response that enumerated them would
      disclose the boutique's booking density", slots.py:149-152), so summing
      capacity over its normal output omits exactly the fully-booked slots — the
      metric is biased downward and the error GROWS as the boutique gets busier.
      booked={} makes taken 0 everywhere and CHECK (capacity > 0) makes that total,
      so the grid is complete with ZERO change to the engine. An include_full flag
      was declined: its only job would be switching off a disclosure control on the
      function that also serves anonymous storefront traffic.
      (2) The forward window's two bounds differ by one day DELIBERATELY —
      materialize_slots is inclusive on both ends (today+6), count_by_start is
      half-open on the right (midnight of today+7). Either error misstates
      utilization by up to a seventh, permanently and silently. A db test pins it
      by putting its booked slot on today+6 specifically.
      (3) Busiest-types labels come from max(created_at), NOT max(starts_at) —
      appointment_type_name is snapshotted at booking CREATION, and brides book
      months ahead, so starts_at order routinely disagrees. Review caught this; the
      fixture is required to order the two keys OPPOSITELY or the test pins neither.
      (4) F55 merged mid-review and the rebase applied with NO textual conflict and
      still broke: F55's guard derives the /manage path-segment set from the LIVE
      route table, F52 is the tenth such router, and without the vite.config.ts edit
      /manage/dashboard was served the SPA shell instead of proxied to the API — a
      200 with the WRONG BODY, which no status assertion catches. Fixed in 6c232cc.
      This is the second time a pre-written guard caught a clean-rebase collision
      (the first was ruff F811 on F15/F31). Router order verified: dashboard_router
      registers before _register_spas.
  - id: F56
    slug: storefront-focus-flake
    epic: cross
    title: "Fix the flaky storefront focus assertions (CI merge blocker)"
    status: queued
    deps: []
    note: >-
      FOUND BY F52's CI run 2026-07-31, and it is NOT an F52 regression — F52
      touches zero storefront files. `frontend/apps/storefront/src/__tests__/
      BookPage.test.tsx` asserts `document.activeElement` synchronously after a
      focus move; on CI it intermittently reads `<body>` instead of the element
      carrying tabindex="-1". PROOF it is pre-existing and flaky rather than a
      regression: commit fc5f7eb8 is a DOCUMENTATION-ONLY change (.planning
      markdown, no code at all) and its Frontend job failed with the same
      assertion shape (`<p tabindex="-1">` that time, `<div>` on F52's run).
      Re-running the identical commit turned it green. This is a GATING job, so
      the flake blocks an arbitrary fraction of ALL merges and cost F52 one full
      CI cycle. Likely fix: await the focus move (findBy*/waitFor) instead of
      asserting synchronously. Small, but it taxes every feature until done.
  - id: F53
    slug: customers-crm
    epic: SMC
    title: "Customers CRM + notes/tags + SMS log"
    status: queued
    deps: [F31]
    note: >-
      SMC-4. customers.notes TEXT + tags TEXT[] (migration), ILIKE search,
      detail with booking history, read-only SMS log (message_log by phone OR
      by the customer's booking ids — phone corrections orphan old rows).
      Never expose provider_message_id/error. Audit logs field names only (PII).

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
    blocker: "refund automation needs a gateway adapter with a refunds API (F18) — UNBLOCKED 2026-07-31: Lemon Squeezy test mode has one, so this can build once F18 lands. Set back to queued when F18 merges."
    note: >-
      Pre-decided #21/#22: tenant-scoped cache keys plus a bounded negative
      cache; k6 targets derived from staging metrics at the 50-tenant horizon.
      The caching and load halves could be split out early if F18 stays blocked.

  # ---- E6..E10 (F31-F49). E7 precedes E8 per Interview Q12.
  # Slugs are placeholders until each spec names its own.
  # ---- E6 in-store real-time ----
  - id: F31
    slug: staff-roles-gating
    epic: SMC
    title: "Staff roles & default-deny manage gating"
    status: merged
    pr: 22
    deps: [F3, F5]
    note: >-
      Q11 OVERRIDDEN by user decision 2026-07-30 (Shift Manager Console epic,
      .planning/epics/shift-manager-console.md): staff sign in with email +
      password through the unchanged /manage/auth/login — no OTP, no F11 dep,
      no sender-ID blocker. Scope: shift_manager enum member + DB CHECK +
      require_role default-deny gating on every /manage route, proven by a CI
      route walker. Staff CRUD UI moved to F51. Started 2026-07-30 on
      feature/staff-roles-gating, parallel to F15 (contingency: gates the three
      shipped /manage routers now; F15's owner_router adopts require_role on rebase).
      Test hardening shipped separately as PR #23 (merged 2026-07-30): all 13
      audited coverage gaps closed, +16 tests, CI 882 passed with no deselections.
      The DB->gate seam is now proven on real Postgres
      (tests/test_staff_role_gating_integration.py — a shift_manager row written by
      the app principal past 0011's CHECK decides the gate over HTTP, and demotion
      bites on the next request, so F51 needs no session sweep). Two notes for
      whoever touches this next: the app-role UPDATE probe in test_migrations.py is
      F51's pre-flight (boutique_app can write the role past the CHECK under RLS),
      and NOT_AUTHORIZED's wire code plus generic body are pinned by literal in
      test_the_not_authorized_contract_is_pinned_by_literal — F15's rebase fails
      loudly if its role-naming variant of the same-named constant wins the merge.
  - id: F32
    slug: f32-placeholder
    epic: E6
    title: "Live-update substrate (versioned board state + polling)"
    status: parked
    deps: [F31]
    blocker: "subsumed into F34 (SMC epic ruling 3, 2026-07-30) — never build"
    note: >-
      Pre-decided #23: NO realtime vendor. ~5s refresh; Pusher only if the pilot proves it
      too slow. #25: events are versioned hints, server is truth.
      SUBSUMED into F34 by the SMC epic (2026-07-30): the board polls the F15
      bookings API wholesale; the version field is dropped (computing it costs
      the same as answering in full). Entry kept for the record, do not build.
      PARKED 2026-07-30 (program reconciliation) because it was still `queued`
      with its only dep merged, so the loop's next pick would have been a feature
      the epic ruled out. Every downstream dep list that named F32 (F35, F36,
      F37, F44) was rewritten to name F34 or to drop it — leaving them pointing at
      a never-merging entry would have stalled E7 and E9 permanently.
  # F51, F52, F53 and F34 (the rest of the SMC console) were moved ABOVE the E5
  # block on 2026-07-30 — the user's build-order ruling is "finish SMC first", and
  # the loop picks the first eligible entry in FILE order, so priority has to be
  # expressed as position. Do not re-sort this file by epic.
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
      KEPT by user ruling 2026-07-30. The SMC epic contradicted itself — ruling 3 said
      "F33 is not built" while ruling 2 said E6-proper's QR queue "stays queued" — and
      the user resolved it in favour of building. Read the two as complementary, not
      alternatives: F50 makes a walk-in the STAFF books a real booking; F33 is the
      self-service QR at the door that captures a lead before anyone is free to serve
      her, with a queue ticket that is NOT a booking. Builds after F20 (needs its
      consent column). If F34's board makes the queue-ticket model redundant in
      practice, say so then — do not silently skip it.
  - id: F35
    slug: f35-placeholder
    epic: E6
    title: "Staff in-app notification bell"
    status: queued
    deps: [F31, F34]
    note: >-
      Pre-decided #32: in-app only. No browser push, no APNs/FCM.

  # ---- E7 fitting rooms & SOS (before E8, per Interview Q12) ----
  - id: F36
    slug: f36-placeholder
    epic: E7
    title: "Fitting-room registry + staff/client/room/dress assignment"
    status: queued
    deps: [F8, F13, F31, F34]
    note: >-
      Pre-decided #31: one active assignment per room via a partial unique index — same
      concurrency discipline as the F13 slot claim.
  - id: F37
    slug: f37-placeholder
    epic: E7
    title: "SOS paging: role-targeted page, live alert, resolution"
    status: queued
    deps: [F31, F35, F36]
    note: >-
      Pre-decided #29: she picks a ROLE; every on-shift staffer with it is paged; first to
      accept owns it. Rides F34's 5s poll (F32 subsumed) — the latency tradeoff is
      recorded in the epic's Risks.

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
    deps: [F34, F41, F42]
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
  # Rewritten 2026-07-31: the user supplied Lemon Squeezy + Twilio credentials,
  # which removed the two longest-standing blockers. What remains is smaller.
  - "Add 3 DNS records at DomainTheNet (external-applications.md → 'DNS records to add') — the domain is BOUGHT and the Railway wildcard is created; these records are the only thing between here and a live https://{slug}.modryn.co.il"
  - "Send the Twilio ACCOUNT SID (AC…) and the phone number in E.164 (#4b) — the only two values F54 is missing; the API key pair alone names no account and a PN… SID is not a valid `From`"
  - "ROTATE THREE SECRETS pasted into a chat transcript on 2026-07-31: the modryn.co.il domain-management password (highest priority — it controls nameservers and transfers), the Lemon Squeezy API key + webhook secret, and the Twilio API key secret"
  - "Choose the production Israeli PSP before live money (#3) — Grow/Tranzila/Cardcom; NOT urgent, LS test mode covers every E4 build, and the winner is one adapter file behind F17's port"
  - "Register SMS sender ID 'MODRYN' (#4) — required before PRODUCTION sends; development runs on the Twilio long-code number"
  - "Get counsel to review the F16 SMS bodies and the F20 privacy default before either goes live"
  - "Find a human Arabic reviewer for legal/policy copy before F45 goes live"
  - "Meta business verification (#5) — user ruled 2026-07-31 this is the LAST step. Do not re-nag before F46."

in_run_gates:                   # block a specific feature; the user clears them mid-run
  # OPEN NOW — artifacts written, reviewed and on disk. To clear one, say so in any
  # session; the next iteration records the approval in the spec header, drops the
  # entry's blocker, sets it back to `queued` and builds.
  # CLEARED 2026-07-31: F17 — Gate 1 approved, all four answers in the spec's
  # "Gate 1 resolutions"; the entry is `queued` and E4 is unblocked.
  - id: F20
    what: ".planning/specs/ppl-compliance.md — Gate 1 approval (legal surface)"
    asks: 5
    sharpest: "retention_enabled now defaults FALSE, so two security-checklist rows merge amber rather than green. Accept, or overrule back to default-on with no backup to undo an irreversible mass-delete."
  - id: F34
    what: ".planning/design/screens/shift-board/prototype.html — design gate (Interview Q2, novel)"
    asks: 8
    sharpest: "Open it in a browser and press «השהיה». That pause control is what makes the board lawful under WCAG 2.0 SC 2.2.2 — a Level A criterion axe-core cannot detect, so CI would have shipped green without it."
  # LATER — not yet authored, listed so the run's shape is legible.
  - id: F19
    what: "deposit flow — spec written once F17 merges, then Gate 1 (payments)"
  - id: F48
    what: "billing — Gate 1 when E10 is reached (money surface)"
  - id: F42
    what: "seamstress capacity matrix — clickable prototype (Q2 novel)"

rulings_2026_07_30:             # taken in the finish-the-project planning session
  - "Build order: finish the SMC console before E5. Queue reordered to match."
  - "F33 QR check-in is KEPT (builds after F20), resolving the SMC epic's self-contradiction."
  - "F15 phone-correction without OTP is ACKNOWLEDGED as shipped for owner AND shift_manager."

known_flaky:                    # nondeterministic tests — they gate every merge, so treat as debt
  - test: "frontend/apps/storefront/src/__tests__/ManageBookingPage.test.tsx :: the cancel two-step :: moves focus into the revealed block, onto the question itself"
    seen: "2026-07-31 on PR #27, whose diff touched ZERO frontend files"
    evidence: >-
      The same commit failed then passed on a plain re-run. The element it waits
      for IS in the DOM dump; document.activeElement is <body> instead. A jsdom
      focus/timing race, not a regression.
    why_it_matters: >-
      merge-gate.sh blocks on the Frontend job, so a flaky test can park a
      perfectly good feature — and worse, it trains whoever is watching to
      re-run red CI without reading it, which is how a real failure gets waved
      through. Fix the wait, do not raise the timeout.
    owner: unassigned — pick up at the E4 boundary or sooner if it recurs

rulings_2026_07_31:             # the user supplied credentials; E4 unblocked
  - "PAYMENTS: Lemon Squeezy TEST MODE is E4's engine behind F17's port. It is a development engine only — LS is merchant-of-record and the deposit is legally the boutique's money, so it can never carry live deposits. The production Israeli PSP is deferred to before-live-money and is one adapter file."
  - "F17 Gate 1 APPROVED. Q1 no-gateway → hide the deposit and book anyway. Q2 KMS → deferred, accepted unchecked. Q3 payments retention → 7 years. Q4 expired-hold webhook → HONOUR the money and alert the owner; no refund() is added."
  - "SMS: Twilio credentials supplied; the adapter F11 deferred becomes F54. Two values still missing (Account SID, E.164 number) — they gate a live send, not the build."
  - "Meta/WhatsApp verification is the LAST step by user ruling. F46 waits on its clock at the end rather than overlapping it."
  - "Grow is NOT cancelled — it is demoted from 'the blocker' to 'one candidate for the production PSP decision', which now sits after E4 rather than before it."
```

## Run report

_Written when the queue is exhausted._
