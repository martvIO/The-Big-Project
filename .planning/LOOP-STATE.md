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

current: null                   # floor program: F34 MERGED (PR #32) 2026-07-31, iteration 1 of 10 done.
                                # Next pick is F57 (floor-staff-roles) — F34's merge unblocked it.
                                # F56 merged (PR #30), F52 merged (PR #28) 2026-07-31.
                                # RE-PRIORITISED 2026-07-31: the FLOOR-MANAGEMENT PROGRAM now sits at the top of
                                # `queue:` and preempts everything. Next pick is F34, then F57, F36, F33, F58,
                                # F59, F37, F41, F42, F60 — ten features, one PR each. F19 (spec done and
                                # self-approved) and F53 are NOT cancelled: they resume automatically the moment
                                # the floor block is exhausted, because the loop picks by file order.
                                # Queue reconciled 2026-07-30 for the finish-the-project run and re-simulated
                                # after the re-order: 0 unreachable, 2 parked (F20 legal gate, F32 subsumed).
                                # Deps absent from this queue (F3-F14) are historical merged features, which is
                                # how the loop reads them.

queue:
  # ==================================================================
  # ==== FLOOR-MANAGEMENT PROGRAM (2026-07-31) — BUILDS FIRST      ====
  # ==== Position IS priority: the loop picks the first eligible    ====
  # ==== entry in FILE order, so this block preempts F19 and F53,   ====
  # ==== which resume automatically once it is exhausted. Ten       ====
  # ==== iterations, one PR each. See rulings_2026_07_31.           ====
  # ==== F34/F36/F33/F37/F41/F42 were MOVED here from their epic    ====
  # ==== blocks below — do not look for a second copy.              ====
  # ==================================================================
  - id: F34
    slug: shift-board-checkin
    epic: SMC
    title: "Live board + check-in (5s poll)"
    status: merged
    pr: 32
    attempts: 1
    deps: [F15, F31]
    spec: .planning/specs/shift-board-checkin.md
    prototype: .planning/design/screens/shift-board/prototype.html
    shipped: >-
      SHIPPED as PR #32, merged 2026-07-31. ALL THREE GATING JOBS GREEN ON THE
      FIRST CI RUN — unusual for a feature whose headline tests are db-marked
      and therefore debut on CI. That is not luck: the builder found Postgres 16
      installed locally, stood up a throwaway cluster outside the repo, ran all
      14 migrations and executed every db-marked test before pushing. It bought
      three things — the three pinned definitions in test_migrations.py are
      CAPTURED rather than guessed (Postgres deparses IN (...) to = ANY
      (ARRAY[...]) and reorders index predicates, so transcribing them from
      0008/0009 would have pinned nothing and reddened CI), one real test bug
      was found and fixed locally (insert() takes no status kwarg), and two
      mutation checks proved the concurrency tests are not vacuous (removing
      populate_existing=True turns both forced-interleave tests red and nothing
      else). Worth repeating for F36/F58, whose races are harder than this one.
      Migration is 0014 — the spec's D2 rule to resolve the revision id from
      `alembic heads` at build time rather than hardcoding 0012 paid off exactly
      as predicted: 0012_payments and 0013_lemonsqueezy_provider landed in the
      window the spec expected to be a design-gate park.
      REVIEW: five lenses, every finding judged by an independent skeptic — 21
      findings, 6 survived, deduplicating to 4 defects, ALL in BoardSection.tsx,
      all fixed in one round (0c7015a) and each verified to fail on the pre-fix
      source. THE TWO BLOCKERS ARE WORTH A LATER READER'S TIME.
      (1) Focus fell to <body> on a FAILED check-in. @boutique/ui's Button is
      disabled={disabled || loading} and both board controls pass loading={busy},
      so the browser blurs the tapped control the instant the request starts. The
      success path compensated and carried a comment naming the hazard; the catch
      path restored nothing. WCAG 2.4.3 Level A, i.e. legal here. This is the
      SECOND time this exact bug class shipped in this repo (F56 was the first,
      on the storefront) and the second time axe passed straight over it — axe
      cannot see a focus move that never happened.
      (2) The poll loop SURVIVED UNMOUNT. Cleanup cancelled the armed timer, but
      the arming sites are load()'s and mutate()'s .finally(), which run AFTER
      cleanup when a request was in flight, and schedule() gates only on
      runningRef — still permissive on a dead component. Nothing in the cycle
      touches React state, so unmount could not break it. Switching nav sections
      mid-request leaked a permanent 5s request loop, one per nav-away, for the
      rest of a 12-hour session. The fix is one line, and it is what makes the
      spec's own claim — "at most one poll in flight per tab BY CONSTRUCTION" —
      actually true rather than aspirational. Any later feature copying D4's
      mechanisms (F57, F37, F41, F59 all will) must copy this line with them.
      Gates: backend 1226 passed / 362 deselected, frontend 1244 across 49 files
      (manage 407, +59 in BoardSection.test.tsx), e2e 69 passed, zero axe.
    note: >-
      SMC-5. DESIGN GATE SELF-APPROVED by user ruling 2026-07-31 — this entry no
      longer parks; build from the finished spec. The spec's design-gate section
      lists deck/prototype revisions (D14 pause + idle-stop control, the {401,403}
      terminal state, the backoff copy); those are BUILD TASKS now, not review
      preconditions. Prototype questions Q-1..Q-4 resolve to the spec's stated
      defaults (5s beat, no row navigation, undo always visible, one chronological
      list); Q-5 resolves NO — the board does not become the landing section, F52's
      dashboard stays. Everything else per the spec verbatim: one migration
      (bookings.checked_in_at TIMESTAMPTZ, NOT a fifth status), two endpoints on
      F15's owner router, BoardSection with the six D4 poll mechanisms.
      This board is the shell every floor panel below attaches to (F57 staff cards,
      F36 rooms, F58 waitlist, F37 SOS centre), which is why it goes first.
      Pre-decided #28 still bounds it: done at queue + dispatch, no waiting-time
      analytics. F32 stays subsumed. F33 is NOT a dep (they meet at F58).
  - id: F57
    slug: floor-staff-roles
    epic: E6
    title: "Floor roles (reception/sales_assistant/seamstress) + break status + staff cards"
    status: queued
    deps: [F51, F34]
    note: >-
      NEW 2026-07-31 (floor program). The brief's staff cards — name, role, live
      status — plus the roles that make them mean anything. Migration widens
      0011's role CHECK and StaffRole to
      owner/shift_manager/reception/sales_assistant/seamstress ('sales_assistant'
      supersedes pre-decided #24's 'sales' slug, user ruling) and adds
      staff_users.break_started_at TIMESTAMPTZ NULL.
      DO NOT REBUILD STAFF CRUD — F51 shipped add/edit/delete; this feature only
      widens its role select. F31's route walker default-denies the three new roles
      on every existing /manage route; they are admitted surface by surface, and
      this feature admits them to exactly two things: the floor read and their own
      break toggle.
      Ships GET /manage/floor (app/floor/) rendering a staff-cards panel on F34's
      board, with its OWN poll loop copying F34's D4 mechanisms per D13. This is
      the SECOND poll caller in the codebase, so the shared usePoll hook gets
      extracted here (apps/manage/src/lib/) — that is what makes it reviewable.
      Status derivation: break if break_started_at is set; occupied arrives with
      F36 and is never true until then; else available. Toggle break/available:
      owner + shift_manager on anyone, any staffer on herself.
  - id: F36
    slug: fitting-rooms
    epic: E7
    title: "Fitting-room registry + assignment (rooms panel)"
    status: queued
    deps: [F8, F13, F31, F34, F57]
    note: >-
      Substance unchanged from the e7 brief; pulled forward and given its floor
      surface. fitting_rooms CRUD (add/remove rooms — the brief's prerequisite for
      any assignment) + fitting_room_assignments where released_at IS the whole
      occupancy model, plus the dress-bindings child table.
      TWO partial unique indexes, both WHERE released_at IS NULL AND deleted_at IS
      NULL: (tenant_id, fitting_room_id) — pre-decided #31, one active assignment
      per room — and NEW (tenant_id, staff_user_id), one active room per worker,
      which is what makes the card's "occupied" a fact rather than a guess.
      INDEX, NOT LOCK (the e7 ruling, and the F51 advisory lock is NOT the
      precedent to copy — that expressed "at least one", which no index can say;
      this is "at most one", which is exactly what an index says). The claim is one
      INSERT; IntegrityError becomes a 409 naming the current occupant.
      Rooms + occupancy EXTEND F57's /manage/floor payload — do not add a second
      poll loop for them. Staff cards gain occupied (client + room). The client
      label is resolved at read time and never snapshotted onto the assignment
      (e7's PII rule).
  - id: F33
    slug: qr-walkin-queue
    epic: E6
    title: "QR self-check-in + queue tickets + live position"
    status: queued
    deps: [F5, F9, F10, F13]
    note: >-
      REVIVED AT FULL SCOPE by user ruling 2026-07-31, overriding the SMC ruling
      that "F33 is not built". The F20 DEP IS DROPPED: F33 adds
      customers.marketing_opt_in_at itself, which e6-instore-realtime.md:71
      pre-authorised in as many words. What F20 owns that F33 cannot invent is the
      collection-notice WORDING — privacy-law text, the Q1 user-only class — so
      that ONE string is parked in in_run_gates and a neutral interim sentence
      ships meanwhile. This is the F19 precedent exactly: park the question, build
      the feature.
      Scope: queue_tickets (status CHECK waiting/in_service/done/removed,
      called_at, requeued_at, skip_count) — a queue ticket is NOT a booking, which
      is what keeps it distinct from F50's walk-in. POSITION IS COMPUTED ON READ,
      ordering by COALESCE(requeued_at, created_at): that keeps pre-decided #30's
      no-stored-position rule AND makes the brief's skip-to-back a one-column
      write instead of a renumbering pass.
      Public storefront /checkin route, 3 fields (name, phone, bride/evening).
      The POST goes on a NEW mutating router — app/storefront/router.py is
      contractually GET-only — with its OWN FixedWindowRateLimiter instances,
      per-tenant and per-phone. One budget = one instance: never reuse the OTP or
      booking limiters, or a busy bride morning locks the door queue.
      Dedup on (tenant, phone, day). Live-position view polls its own public GET
      keyed by the ticket UUID (the id is the capability; the response carries
      position + ahead-count + status and echoes no PII). One static printed QR per
      boutique (#30), rendered in manage. Auto-delete days after the visit stays
      F20's retention job's second consumer. Hebrew only; ar keys untranslated.
  - id: F58
    slug: floor-dispatch
    epic: E6
    title: "Waitlist panel + dispatch (take-next, push-assign, finish, skip)"
    status: queued
    deps: [F33, F36, F57]
    note: >-
      NEW 2026-07-31 (floor program) — the atomic heart of the brief, and the one
      entry where getting the concurrency wrong is visible to a customer. No new
      table: it acts on F33's queue_tickets and F36's assignments. The waitlist
      panel joins the /manage/floor payload (arrival order, wait time computed on
      read) with per-entry call / assign / skip / done.
      TAKE-NEXT is ONE transaction: claim the earliest waiting ticket with
      UPDATE queue_tickets SET status='in_service' WHERE id = (SELECT id ...
      WHERE status='waiting' ORDER BY COALESCE(requeued_at, created_at) LIMIT 1
      FOR UPDATE SKIP LOCKED) RETURNING — the worker's drain pattern, so two
      managers pressing it at the same instant get two DIFFERENT customers or one
      gets a clean "queue empty", never the same customer twice — then INSERT the
      fitting_room_assignment in the same transaction, where F36's two partial
      unique indexes make a double-assign structurally impossible. A lost race
      rolls BOTH back, so the ticket is left `waiting`, not stranded in_service.
      PUSH-ASSIGN: same insert against an explicit ticket id, guarded by the
      conditional UPDATE ... WHERE status='waiting' (rowcount 0 -> 409).
      FINISH ("סיימתי עם הלקוחה"): release the assignment and close the ticket in
      one transaction — the worker frees and the entry closes together or not at all.
      SKIP: requeued_at=now(), skip_count+1; skip_count >= 2 -> removed (the
      brief's second-skip rule). CALL: stamps called_at, which is what F59's wall
      board highlights.
      Race tests to the F13/F51 standard: forced-interleave pairs, db-marked, never
      a bare asyncio.gather for the deterministic branch. THIS FEATURE ALSO BUILDS
      THE /manage/** Playwright interception harness (login + floor payload stubs),
      which the console has never had — recorded as a gap in F34's spec Risk 8.
  - id: F59
    slug: public-queue-board
    epic: E6
    title: "Public wall-screen queue board (/queue)"
    status: queued
    deps: [F33]
    note: >-
      NEW 2026-07-31 (floor program), authorised with the full-queue ruling that
      also revived F33 — pre-decided #27 had deferred the kiosk as "a small
      follow-up if the pilot asks for it", and the user asked.
      Storefront /queue: one matchRoute entry, the day's waiting queue, POSITION +
      FIRST NAME ONLY (that display is named for F20's eventual notice — it is the
      one place a customer's name is shown to a room full of strangers), called
      entries highlighted from F58's called_at, big-type layout legible at TV
      distance. Public GET on the queue router, tenant from Host, no auth,
      Cache-Control: no-store.
      Own 5s poll loop (D4 mechanisms copied per D13) and its OWN SC 2.2.2 pause
      control — a permanently-mounted auto-updating wall screen is the single most
      literal instance of that criterion in the product, and axe cannot see it, so
      the pause control needs a named frontend test the way F34's does.
  - id: F37
    slug: sos-paging
    epic: E7
    title: "SOS: targeted page, full-screen alert, ack/resolve, 30s escalation"
    status: queued
    deps: [F31, F36, F57]
    note: >-
      AMENDED BY THREE USER RULINGS 2026-07-31. (1) 30s auto-escalation is
      REINSTATED, overriding pre-decided #29's "no escalation timer". (2) Targeting
      follows the brief — a SPECIFIC signed-in colleague OR the shift-manager role
      — overriding #29's role-fanout-and-no-name-picker; the two were incompatible,
      since escalate-to-shift-manager is meaningless if the first page already went
      to every shift manager. (3) Delivery is a FULL-SCREEN red overlay in the
      manage app fed by the SOS poll, so the F35 dep is DROPPED (the bell stays
      queued as a later durable upgrade). Still in-app only — #32 stands, no
      browser push, no APNs/FCM, no SMS. What SURVIVES from #29: first-accept-owns,
      and an alert is never silently dropped.
      THE DEVICE-IDENTITY PICKER IS NOT PORTED. It existed in the prototype only
      because that prototype had no auth; MODRYN has real sessions, so sender and
      target are staff_users identities and "the targeted device" is simply where
      that staffer is signed in.
      sos_alerts: raised_by, target_staff_user_id NULLABLE (null = the
      shift-manager role), fitting_room_assignment_id nullable, note, status CHECK
      open/accepted/resolved/cancelled, acknowledged_at. Accept/ack is an atomic
      conditional UPDATE ... WHERE status='open' — rowcount 0 becomes a 409 naming
      the owner (e7's shape, kept).
      ESCALATION IS DERIVED AT READ TIME, not written by the worker: the alerts
      query also returns, to any shift manager, every open alert unacknowledged for
      more than 30 seconds. Justification, because the alternative looks tempting —
      app/worker.py ticks at 60s, so a worker-stamped escalation would arrive up to
      a full minute late (twice the requirement) and would introduce a write that
      races a concurrent ack. The read-time predicate adds zero latency beyond the
      poll, cannot race, and is the house compute-on-read pattern (#30 queue
      positions, F43 fitting ordinals). A durable escalated_at is the recorded
      upgrade path if history ever needs it.
      The alerts poll runs APP-LEVEL in manage so the overlay can render over any
      section; a ~2s tick while an alert is open is pre-authorised in the e7 Risks.
      SOS-centre panel on the board lists active alerts with ack/resolve. Raise
      control is reachable from a room card. Screen-reader announcement of an
      incoming alert is a gate condition, not a nicety (e7 Risks).
  - id: F41
    slug: alteration-tickets
    epic: E9
    title: "Atelier tickets + kanban (intake/in_progress/qc/ready/delivered)"
    status: queued
    deps: [F8, F13, F31, F34, F57]
    note: >-
      PULLED FORWARD from E9 by the floor program, and AMENDED: the kanban states
      are the brief's intake -> in_progress -> qc -> ready -> delivered. Those
      LABELS supersede pre-decided #39's five names (received/measured/in_work/
      ready/collected) — #39's MECHANISM is untouched and non-negotiable: five
      nullable TIMESTAMPTZ columns, no status enum, current state = the latest
      stamped one. Note E9 had no QC state; the brief adds one.
      due_date SUBSUMES E9's wedding_date — an evening gown has no wedding — and
      when an F28 rental reservation exists it can prefill, later.
      Row: customer, dress snapshot (0008's snapshot discipline), due_date,
      effort_minutes from Q13's five preset bands (mapping in tenant settings),
      assigned seamstress (staff_users, seamstress role from F57), notes.
      Kanban section in manage with its own poll endpoint + loop (D13). Advancing
      a state stamps a column and is audited. RLS isolation-suite probes for the
      new tenant table are non-negotiable. Retention is flagged for F20/F21 as e9
      records. No pricing, no photos.
  - id: F42
    slug: seamstress-capacity
    epic: E9
    title: "Seamstress capacity hours + load bars + balanced assignment"
    status: queued
    deps: [F41, F57]
    note: >-
      DESIGN GATE SELF-APPROVED by user ruling 2026-07-31 (Q2 had marked it novel)
      — build through it, do not park.
      SIMPLIFIED CAPACITY MODEL per the brief, and the F40 dep is DROPPED for this
      run: staff_users.weekly_capacity_hours with a tenant default, load =
      SUM(effort_minutes) over tickets not yet delivered, load bar turns red when
      load exceeds capacity. E9's own degradation clause blesses a roster-free
      fallback; the F40 published-roster projection (hourly capacity walked back
      from the due date) is the recorded upgrade path, NOT this build — F40 is E8
      and is nowhere near.
      Seamstress directory panel. The ticket-assignment surface sorts seamstresses
      by remaining capacity, but overload only FLAGS and never blocks — pre-decided
      #40 stands, every reallocation is a human action.
      A11y: overload is never colour-only (the bar carries text), and the grid is
      keyboard-navigable (e9 Risks).
  - id: F60
    slug: guide-walkthrough
    epic: cross
    title: "Per-page guided walkthrough (Guide button)"
    status: queued
    deps: [F34]
    note: >-
      NEW 2026-07-31, deliberately LAST in the floor block — it is the brief's
      lowest-priority item and the only one that ships no capability. A «מדריך»
      button in the console shell opens a per-section step overlay, steps keyed by
      SectionKey, copy in i18n he with untranslated ar per Q3. One hint step on the
      storefront /checkin page too.
      Frontend only: no migration, no endpoint, and NO new dependency — a
      hand-rolled overlay, not a tour library. Focus trap and Esc-to-close are the
      real work here.
      IF THE RUN HAS TO STOP EARLY, THIS IS THE ENTRY TO LEAVE QUEUED.
  # ==================== end floor-management program ====================

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
    status: queued
    spec: .planning/specs/deposit-booking-flow.md
    deps: [F7, F16, F17]
    spec_gate: user
    gate_1_preauthorized: >-
      USER RULING 2026-07-31, recorded late — this entry's `spec_gate: user` and
      gateway-port.md's "re-asked at F19's Gate 1" both predate it, and a session
      reading only those documents will reasonably conclude the gate is still
      open. It is not. Asked directly how this run should treat the F18 and F19
      payment gates, the user chose "Pre-authorize both", with the trade-off
      stated in the question: the whole payment chain builds without stopping,
      and F19's spec makes its money-behaviour calls (hold length, sweeper
      timing, what the bride sees on failure) with nobody checking them. That was
      accepted knowingly.
      So F19's spec SELF-APPROVES and builds. It must still RECORD its money
      decisions prominently — pre-authorization waived the pause, not the
      scrutiny — and F21's audit re-derives them from the code. If a spec author
      still believes a question genuinely needs the user, park that ONE question
      and build the rest rather than stopping the feature.
    note: >-
      Q7: build hold / expiry sweeper / webhook→confirmed against the fake
      gateway. The race most likely to be wrong (hold expiry vs a late webhook)
      does not depend on Grow, so it gets built and race-tested now.
  - id: F18
    slug: lemonsqueezy-adapter
    epic: E4
    title: Lemon Squeezy payment sessions & webhooks (test-mode adapter)
    status: merged
    pr: 31
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
  # F34 MOVED 2026-07-31 into the FLOOR-MANAGEMENT block at the top of this file.
  # Its design gate is self-approved by user ruling, so it no longer parks — it is
  # the floor program's first pick and the shell every floor panel attaches to.
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
    status: merged
    pr: 30
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
      SHIPPED as PR #30, merged 2026-07-31. THE TRIAGE WAS WRONG AND CI CAUGHT IT.
      Round 1 did the obvious thing — wrap the assertions in waitFor — and CI failed
      AGAIN on a site that was ALREADY wrapped. waitFor polling for a full timeout and
      still seeing <body> is only possible if the focus was never coming, so it was
      never a test-timing bug at all.
      THE REAL DEFECT WAS IN SHIPPED PRODUCT CODE, in BOTH storefront routes. The
      focus effects (BookPage ~line 400, ManageBookingPage ~line 184) have NO dependency
      array, so they run after every render, and both CLEARED THE PENDING INTENT BEFORE
      CONFIRMING THE FOCUS LANDED: `ref.current = null` then `node?.focus()`, where node
      is null whenever its conditionally-rendered element has not mounted yet. Any
      interleaving render — a data promise settling, an unrelated setState — discarded
      the intent permanently. A bride cancels an appointment, the confirmation block
      appears, focus never moves into it, and a screen-reader user is left on a button
      that no longer exists. WCAG focus management; axe cannot see a move that never
      happened, which is why every a11y gate passed over it.
      Fix: resolve the node first, return KEEPING the intent if it is not mounted, only
      then clear and focus. Adversarial review then caught that the fix's own persisting
      intent could steal focus mid-typing, so two bounds were added (reset on [step]
      change, and drop a stale `code` intent when she edits the phone). 5 regression
      tests, storefront 728 -> 733.
      TWO THINGS FOR A LATER READER. (1) The negative assertion at router.test.tsx is
      deliberately NOT wrapped in waitFor — polling a negative passes on the first tick
      and stops detecting a focus grab that lands later, turning a real assertion into a
      tautology. (2) src/test/focus.ts (expectFocus) and src/test/interleave.ts exist for
      this class; a comment in BookPage warns that an intent-killer no test can
      distinguish is how the original bug shipped.
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
    status: queued
    deps: [F18, F21]
    spec_gate: user
    note: >-
      Pre-decided #21/#22: tenant-scoped cache keys plus a bounded negative
      cache; k6 targets derived from staging metrics at the 50-tenant horizon.
      The caching and load halves could be split out early if F18 stays blocked.
      UNPARKED 2026-07-31 by its own standing instruction: the blocker read
      "set back to queued when F18 merges", and F18 merged as PR #31. The refunds
      API it needed exists in Lemon Squeezy test mode. Still unpickable until F21
      merges, which is correct — the dep, not a blocker, is what holds it now.

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
  # F33 MOVED 2026-07-31 into the FLOOR-MANAGEMENT block at the top of this file,
  # revived at full scope (QR + queue tickets + live position) with its F20 dep
  # dropped. Pre-decided #26/#30 still bound it; the note there carries them.
  - id: F35
    slug: f35-placeholder
    epic: E6
    title: "Staff in-app notification bell"
    status: queued
    deps: [F31, F34]
    note: >-
      Pre-decided #32: in-app only. No browser push, no APNs/FCM.
      2026-07-31: DROPPED from F37's deps. SOS ships its own full-screen overlay
      and its own alerts poll, so the bell is no longer on the critical path — it
      remains queued as the later durable notification surface.

  # ---- E7 fitting rooms & SOS (before E8, per Interview Q12) ----
  # F36 and F37 MOVED 2026-07-31 into the FLOOR-MANAGEMENT block at the top of this
  # file. F37 is amended there: 30s escalation reinstated, person-or-role targeting,
  # full-screen overlay instead of F35's bell. Pre-decided #31 still governs F36.

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
  # F41 and F42 MOVED 2026-07-31 into the FLOOR-MANAGEMENT block at the top of this
  # file, and amended there: the brief's five status labels supersede #39's names
  # (#39's nullable-timestamp MECHANISM stands), due_date subsumes wedding_date, and
  # F42 ships the simplified weekly-capacity model with its F40 dep dropped.
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
  # F19 MD3 — the ONLY user item this feature left open. It blocks TWO STRINGS,
  # not the feature: F19 builds and ships with a neutral interim sentence.
  - id: F19
    what: "two Hebrew sentences for a bride who PAID a deposit and taps cancel (.planning/specs/deposit-booking-flow.md, MD3)"
    asks: 1
    sharpest: "The SHIPPED string he.ts:297 tells her cancelling is free. That sentence becomes FALSE the day F19 merges, and she has already read it. An engineer cannot invent consumer-facing money copy; a neutral interim ships until you approve the real wording."
  # OPEN NOW — artifacts written, reviewed and on disk. To clear one, say so in any
  # session; the next iteration records the approval in the spec header, drops the
  # entry's blocker, sets it back to `queued` and builds.
  # CLEARED 2026-07-31: F17 — Gate 1 approved, all four answers in the spec's
  # "Gate 1 resolutions"; the entry is `queued` and E4 is unblocked.
  - id: F20
    what: ".planning/specs/ppl-compliance.md — Gate 1 approval (legal surface)"
    asks: 5
    sharpest: "retention_enabled now defaults FALSE, so two security-checklist rows merge amber rather than green. Accept, or overrule back to default-on with no backup to undo an irreversible mass-delete."
  # F33 — like F19's MD3, this blocks ONE STRING, not the feature. F33 builds and
  # ships with a neutral interim sentence in the notice slot.
  - id: F33
    what: "the one-paragraph Hebrew collection notice shown on the public check-in form (privacy-law text, the Q1 user-only class)"
    asks: 1
    sharpest: "The form takes a name and a phone from a member of the public standing in the doorway, and Amendment 13 wants notice at the moment of collection — but no notice text exists anywhere in the product until F20 clears its own gate, so F33 would otherwise collect PII behind silence. Name the boutique, the purpose (queue position + being called), and the retention window."
  # CLEARED 2026-07-31 by user ruling: F34's prototype design gate and F42's
  # capacity-matrix prototype gate are BOTH self-approved for this run. The
  # prototype's open questions resolve to the spec defaults, recorded in the
  # entries and in rulings_2026_07_31.
  # LATER — not yet authored, listed so the run's shape is legible.
  - id: F48
    what: "billing — Gate 1 when E10 is reached (money surface)"

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
  # ---- the floor-management program, ruled the same day ----
  - "FLOOR PROGRAM: the real-time floor-management program builds NOW, ahead of F19 and F53. The queue is re-ordered — the FLOOR block at the top of `queue:` IS the build order, ten features, one PR each. The old Firebase prototype the brief describes (project temp-4d508, RTDB, 24 public Cloud Functions) does NOT exist in this repo and is a BEHAVIOUR reference only: everything builds on the MODRYN stack. No Firebase, no realtime vendor — the recorded 5s poll is what 'live on every device, no refresh' means here, and Pusher stays the pilot-evidence escape hatch it always was."
  - "SOS ESCALATION REINSTATED: 30 seconds unacknowledged auto-escalates to the shift manager, overriding pre-decided #29's 'no escalation timer'. TARGETING follows the brief too — a SPECIFIC signed-in colleague or the shift-manager role — overriding #29's role-fanout and its ban on a name picker. The two rulings were incompatible: escalating to the shift manager is meaningless if the first page already went to every shift manager. First-accept-owns and never-silently-dropped survive unchanged."
  - "SOS DEVICE IDENTITY: the prototype's localStorage 'who am I' picker is NOT ported. It existed only because that prototype had no auth. Sender and target are staff_users identities; 'the targeted device' is just wherever that staffer is signed in. Delivery is a full-screen in-app overlay fed by the SOS poll — F35's bell is DROPPED from F37's deps and stays queued for later. In-app only still (#32): no browser push, no APNs/FCM, no SMS."
  - "CUSTOMER QUEUE, FULL SCOPE: QR self-check-in, live position, and the public wall board all build NOW — overriding the SMC ruling that 'F33 is not built' and pre-decided #27's deferral of the kiosk board. F33 drops its F20 dependency and adds the consent column itself, which e6-instore-realtime.md:71 pre-authorised. The collection-notice WORDING is privacy-law text and stays the user's: it is parked as a single in_run_gates question while a neutral interim sentence ships. That is the F19 precedent — park the question, build the feature."
  - "LANGUAGES: Hebrew only for now. No language switcher, no en/ar toggle — the brief's tri-lingual top bar is deferred. Q3 and E10 are unchanged: every feature keeps shipping ar keys untranslated, and English is not in the plan at all."
  - "DESIGN GATES SELF-APPROVED for this run: F34 (the shift board) and F42 (the capacity matrix) build through their Q2 novel-pattern gates without pausing. F34's spec-listed deck revisions (the D14 pause + idle-stop control, the {401,403} terminal state, the backoff copy) become BUILD TASKS rather than review preconditions; prototype questions Q-1..Q-4 resolve to the spec's stated defaults; Q-5 resolves NO — the board does not become the landing section, F52's dashboard stays."
  - "ROLES: StaffRole widens to reception / sales_assistant / seamstress. Their first consumer is the floor program, which is the bar pre-decided #24 and constants.py both set for adding a role. 'sales_assistant' supersedes #24's 'sales' slug. F31's route walker default-denies all three on every existing /manage route; each floor feature admits them explicitly to its own surface, and F51's staff CRUD is NOT rebuilt — only its role select widens."
  - "ATELIER: the kanban states are the brief's intake -> in_progress -> qc -> ready -> delivered. Those LABELS supersede pre-decided #39's five names, and E9 had no QC state; #39's MECHANISM is untouched — five nullable TIMESTAMPTZ columns, no status enum. The date key is due_date, subsuming E9's wedding_date, because an evening gown has no wedding. F42 ships the SIMPLIFIED capacity model (weekly_capacity_hours per seamstress, load bar red when the sum of undelivered effort exceeds it) and its F40 roster dependency is DROPPED for this run — the roster projection is the recorded upgrade path, and F40 is an E8 feature nowhere near being built."
```

## Run report

_Written when the queue is exhausted._
