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

current: F33                    # F57 (PR #33), F19 (PR #34) and F53 (PR #35) ALL MERGED 2026-08-03.
                                # MAIN'S HEAD IS NOW MIGRATION 0017 (F53's customer_crm_fields).
                                # ONE FEATURE IN FLIGHT: F33, and it is this loop's.
                                #
                                # ==== MIGRATION CHAIN — NOW A RULE, NOT A FIXED GRID ====
                                # THE GRID MOVED THREE TIMES IN ONE DAY, WHICH IS THE WHOLE ARGUMENT.
                                # It said head=0014 at breakfast; F57 made it 0015, F19 made it 0016,
                                # F53 made it 0017 — and F33, which was BUILT at 0016 against a head
                                # of 0015, now collides with F19's shipped 0016_deposit_flow and must
                                # ship as 0018/down_revision 0017. Not one of the four fixed numbers
                                # this file originally assigned (F33=0016, F19=0017, F53=0018)
                                # survived contact. Do not read any of them as current.
                                # THE RULE THAT REPLACES THEM:
                                #   Resolve your revision id from `alembic heads` on main
                                #   IMMEDIATELY BEFORE the rebase that precedes your push, and
                                #   make the migration the LAST commit on the branch so the
                                #   renumber costs one amend to one file nothing else references.
                                # Each feature takes the next FREE number rather than reserving one
                                # behind an unfinished sibling: a migration whose down_revision does
                                # not yet exist cannot pass CI at all, so reserving would block a
                                # finished feature on an unfinished one.
                                # The ordering rule is UNCHANGED and is the load-bearing one:
                                # do not OPEN a PR while a lower-numbered migration is still
                                # unmerged. CI tests the merge result, and two files claiming one
                                # revision id is an alembic multiple-heads error that git cannot
                                # see (the filenames differ) and that reads as a mystery.
                                # THREE THINGS MAKE THIS SAFE WITHOUT COORDINATION: (a) a wrong
                                # down_revision names a revision that does not exist, so alembic
                                # errors outright rather than drifting; (b) F19 carries a fast,
                                # no-DB single-head guard that fails in `make test` instead of as
                                # a CI mystery — it is permanent, not scaffolding; (c) each branch
                                # BUILDS against head+1 so it is self-coherent and its db tests
                                # run, then renumbers at rebase.
                                #
                                # ==== WHO OWNS WHAT — RESOLVED 2026-08-03 16:30 ====
                                # THREE SESSIONS WERE LIVE AT ONCE THIS MORNING. Two have since
                                # shipped and only F33 is still in flight:
                                #   F19  MERGED as PR #34 (10:01Z), migration 0016_deposit_flow.
                                #   F53  MERGED as PR #35 (12:54Z), migration 0017_customer_crm_fields.
                                #   F33  .worktrees/qr-walkin-queue — THIS LOOP's, in flight.
                                # THE LIVENESS CHECK THAT MADE THIS SAFE IS WORTH KEEPING. At 12:48
                                # the F19 worktree looked finished and abandoned — 15 commits, a
                                # CLEAN `git status`, nothing new in the log for hours — and this
                                # loop was one command away from rebasing it. Ninety seconds later
                                # it had five modified files: that session was mid-build with
                                # everything uncommitted, and it went on to merge. A session
                                # BETWEEN COMMITS is invisible to `git log` and to a single
                                # `git status`. The only reliable test is a file-mtime sweep:
                                #   find ".worktrees/<slug>" -type f -mmin -15 \
                                #     -not -path "*/.git/*" -not -path "*/node_modules/*" \
                                #     -not -path "*/__pycache__/*" -not -name "*.pyc"
                                # ⚠ BSD/macOS `find` has NO `-newermt` (GNU only). It does not
                                # error — it silently returns nothing, which reads exactly like
                                # "no session is active" and is the most dangerous possible false
                                # negative. Use `-mmin -N`, and filter the caches (.ruff_cache,
                                # .mypy_cache, dist/) or every worktree looks live.
                                #
                                # ---- historical: how these four came to be in flight ----
                                # (kept because the reasoning still governs which entry is pickable)
                                # F33 was started 2026-08-03 by a SECOND session, deliberately, because
                                # F36 — the next entry in file order — deps on F57 and cannot run beside
                                # it. F33's deps [F5,F9,F10,F13] are all merged history, so it is the
                                # loop's own pick (first queued entry whose deps are all merged).
                                # F19 was started 2026-08-03 by a THIRD session on the same reasoning:
                                # every remaining floor-block entry (F36, F37, F41, F42, F58, F59) deps
                                # on F57 or F33, and F60 — the only floor entry that does not — is the
                                # brief's lowest-priority item and wants a hint step on F33's own
                                # /checkin page. F19's deps [F7,F16,F17] are all merged, its spec is
                                # already written and adversarially reviewed, and its Gate 1 is
                                # pre-authorized (see this entry's gate_1_preauthorized field), so the
                                # session goes straight to Gate 2. It touches the payments/booking
                                # modules and neither sibling's files.
                                # THE ONE COUPLING IS THE MIGRATION NUMBER, and it was FOUR-way.
                                # SUPERSEDED — this paragraph's numbers (main 0014, F57 0015, F33
                                # 0016, F19 0017, F53 0018) are the PRE-MERGE assignment. Read the
                                # MIGRATION CHAIN block at the top of `current:` instead: F57's 0015
                                # is on main and F19/F33 have swapped to 0016/0017.
                                # Worktree: .worktrees/deposit-booking-flow on feature/deposit-booking-flow.
                                # Worktree: .worktrees/qr-walkin-queue on feature/qr-walkin-queue.
                                # F53 was started 2026-08-03 by a FOURTH session, on USER INSTRUCTION to
                                # build something depending on none of F57, F33 and F19. Under that
                                # constraint the eligible set is F60, F50, F53 (then E5). F60 is the
                                # loop's own file-order pick but its ENTIRE blast radius is App.tsx +
                                # i18n/{he,ar}.ts — the two files F57 is rewriting — and its storefront
                                # hint step wants F33's /checkin page, so it is not actually independent.
                                # F50 ships from BoardSection.tsx, which F57 has gutted (258 +-, poll
                                # loop extracted to lib/usePoll.ts): a guaranteed hard conflict. F53 is
                                # SMC-4, deps [F31] merged, and almost its whole surface is NEW files
                                # (app/customers/, CustomersSection.tsx, CustomerDetail.tsx) — every
                                # contended file it touches is append-shaped. That is why it was chosen.
                                # Worktree: .worktrees/customers-crm on feature/customers-crm.
                                # ---- F57 ----
                                # floor program iteration 2 of 10 — MID-FLIGHT, interrupted 2026-07-31.
                                # F34 MERGED (PR #32) 2026-07-31 — its merge unblocked this entry.
                                # INTERRUPTED BY A USAGE LIMIT, NOT BY A FAILURE. Do not increment
                                # `attempts` and do not reset to `queued` — the branch has real work.
                                # RESUME AT PLAN TASK 3. State on feature/floor-staff-roles:
                                #   1a90ac7  docs(planning): F57 spec amendments (Task 0)
                                #   727550d  feat(auth): widen StaffRole + break_started_at (Task 2)
                                # Task 1 (deck reconciliation) was folded into 1a90ac7.
                                # UNCOMMITTED in the worktree, half-written, DO NOT TRUST AS DONE:
                                #   backend/tests/test_floor_db.py  (new, Task 3/8, incomplete)
                                #   backend/tests/conftest.py       (modified — inspect before keeping)
                                # Read both before continuing; finish or discard them deliberately.
                                # Then Tasks 3-8 (backend), 9-12 (frontend), 13 (gates).
                                # Migration 0015 is already written and committed in 727550d —
                                # verify with `alembic heads` rather than re-deriving it.
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
    status: merged
    pr: 33
    spec: .planning/specs/floor-staff-roles.md
    deps: [F51, F34]
    shipped: >-
      MERGED 2026-08-03 as PR #33 by the loop (merge-gate.sh exit 0, all three
      gating jobs green on the FIRST CI RUN). Migration 0015 is now ON MAIN, which
      is what unblocks the F19/F33/F53 migration chain below.
      Built from the mid-flight resume point (plan Task 3); Tasks 3-13 complete.
      The PR was opened by a /spartan:build run, whose contract ends at the PR, so
      the merge was the loop's to take and it took it.
      Local gates: 1277 backend fast, 369 db AGAINST A LOCAL POSTGRES 16 CLUSTER
      (not debuting on CI — the F34 precedent, and it is why CI was green first
      time), 488 manage / 733 storefront / 104 ui frontend, 69 e2e, axe zero,
      qa-greps byte-identical to baseline. `git diff main -- backend/app/auth/`
      is EMPTY, which is Task 7's whole claim.
      THREE THINGS A LATER READER NEEDS.
      (1) THE PLAN WAS WRONG ABOUT vite.config.ts AND A PRE-WRITTEN GUARD CAUGHT
      IT. Task 10 says "/manage/floor* is under /manage, already proxied". It is
      not — the dev proxy names second path segments in an explicit alternation,
      because base:"/manage/" means a bare "/manage" proxy would forward the
      console's own shell to the API. test_spa_serving.py derives that list from
      the LIVE route table and went red naming 'floor'. THIRD time a pre-written
      guard has caught a clean-rebase/plan collision here (ruff F811 on F15/F31,
      this same test on F52) and the nastiest failure mode of the three:
      production, CI and the suite all stay green while only a developer's
      machine breaks, serving the SPA shell where the API should be.
      (2) TWO MUTATION CHECKS CHANGED THE WORK. With only Task 3's seven db tests
      present, removing populate_existing=True changed NOTHING — each opens a
      fresh session, so the identity map is empty and the flag is a no-op. The
      forced-interleave race is what actually pins it. Separately, moving
      end_break's previous-value capture after the write reddens one db test and
      leaves ALL 17 fast tests green, because monkeypatched repositories never
      stamp anything. Both mechanisms would have shipped unproven.
      (3) REVIEW FOUND FIVE REAL DEFECTS IN THIS BRANCH'S OWN CODE (5 lenses ->
      11 findings -> 10 adversarially verified -> 5 survived), all fixed and each
      pinned by a mutation. Two MAJOR: a successful poll unmounted the FOCUSED
      in-card alert and dropped focus to <body> five seconds later with no user
      action (WCAG 2.4.3 — the bug class that has now been caught three times in
      this repo), and the success-path focus test was VACUOUS because jsdom does
      not blur a disabled element, so the whole restore effect could be deleted
      with the suite green. One fix — usePoll's mount effect not being idempotent
      under StrictMode — is a bug INHERITED FROM BoardSection ON main, so the
      extraction is what makes one line fix both callers. A second review round
      caught two more, both against the commit message's own claims rather than
      the code; the message is amended to be true.
      CARRIED: Risk 10 hands F20 a staff-break privacy entry; Risk 2 hands F29 the
      number (~17 -> ~28 round trips per 5s per device on the board screen); Risk 1
      says test_the_floor_roles_reach_exactly_the_floor_routes classifies on the
      INTERSECTION of a route's gates and must never be relaxed to a subset check —
      F36 and F58 both extend this router and `any(...)` would red-fail a correctly
      tightened route.
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
    status: merged
    pr: 37
    attempts: 1
    deps: [F8, F13, F31, F34, F57]
    spec: .planning/specs/fitting-rooms.md
    plan: .planning/plans/fitting-rooms.md
    started: >-
      2026-08-03 16:45, worktree .worktrees/fitting-rooms on feature/fitting-rooms.
      Picked because F57's merge made every dep merged history — it is the loop's own
      next pick in file order. Gates 1 and 2 self-approved; the design gate too
      (ruling 2026-07-31: E7's screens assemble from F34's shipped board shell).
      SPEC REVIEW: 41 findings from 3 lenses, 40 applied, 1 rejected in writing.
      EIGHT WERE BLOCKERS and two of them were one root defect worth recording,
      because the feature would have shipped looking finished and been hollow:
      NOTHING IN THE CONSOLE COULD EVER SUPPLY booking_id, so client_label would
      have been null on every v1 assignment, every fitting would have rendered as
      an anonymous visit, and E7's second success criterion would have been void
      while every test passed. The answer is a new minimised route,
      GET /manage/floor/clients, returning booking_id + client_label + starts_at
      and nothing else, for people who are physically in the building today.
      THE SECOND LOAD-BEARING FIND is a documentation defect that is really a
      security defect: THREE SHIPPED COMMENTS (floor/router.py:11-14,
      floor/service.py:69-75, floor/schemas.py:13-16) state as a FACT that the
      floor payload carries ZERO customer data, and one of them is the stated
      justification for the only router in the product admitting all five roles.
      F36 puts a client label on that payload, so this PR REWRITES those three
      comments. Leaving them would leave a false comment standing as the rationale
      for the widest role gate in the codebase.
      Design deck + copy deck (69 keys, machine-validated) reviewed by design-critic;
      its fourteen required changes are BUILD TASKS in the plan, not review notes.
      MIGRATION: built at 0018, renumbered to 0019 when F33's 0018 landed first —
      the rule working exactly as written.
    shipped: >-
      MERGED 2026-08-03 as PR #37, ALL THREE GATING JOBS GREEN ON THE FIRST CI RUN.
      Migration 0019_fitting_rooms. Gates run locally on the pushed tree: 1663 backend
      fast, 537 backend db ON REAL POSTGRES 16.14, 104 ui / 943 storefront / 729
      manage, 74 e2e, axe zero, alembic heads one head.
      THE BUILD RAN CLEAN — 27 agents, ZERO failures, the first workflow today with no
      API deaths.
      THREE THINGS A LATER READER NEEDS.
      (1) THE SPEC'S 409 DISCRIMINATOR DID NOT WORK, AND EVERY 409 WOULD HAVE BEEN A
      500. D3 said to tell the two indexes apart with
      getattr(exc.orig, "constraint_name", None). SQLAlchemy's asyncpg dialect REBUILDS
      the error as IntegrityError("%s: %s" % (type(e), e)) and raises it `from` the
      asyncpg original, so exc.orig carries a FORMATTED STRING and no constraint_name —
      the expression is None for every violation and the claim always took its re-raise
      branch. Verified against the dialect source and three live violations. Corrected
      once, beside the two index constants:
      getattr(getattr(error.orig, "__cause__", None), "constraint_name", None).
      Anything later that discriminates a Postgres constraint by name must use that
      shape, not the obvious one.
      (2) TWO MAJOR REVIEW FINDINGS, BOTH REPRODUCED END TO END BEFORE BEING ACCEPTED
      (3 lenses -> 17 findings -> each judged by an independent skeptic -> 2 survived).
      The sharper one: patch() rebuilt the whole room list FROM A STALE CLOSURE, so two
      concurrent room mutations discarded each other. busyIds is keyed PER ROOM, so
      overlapping mutations are supported by design, and the poll cannot heal the
      window because tick() returns "suppressed" while a mutation is in flight. For up
      to 5s the screen showed a CLAIMED room as free with a live claim button — a
      colleague tapping it gets a 409, the exact state this feature exists to prevent —
      while the freshness stamp asserted the panel was current. The shipped double-tap
      test could not catch it: it covers one control, and `busy` genuinely disables that.
      RoomsRegistryDialog was structurally identical and fixed with it.
      (3) A SHIPPED ROUND-TRIP TEST BROKE BY BEING LANDED ON. test_migration_0017_round_trips
      used command.downgrade(cfg, "-1"), so 0019 arriving on top made it downgrade the
      FITTING-ROOM tables and then assert about customers. That is the deposit block's
      documented rot arriving a second time; fixed with a shared _parent_of(marker)
      helper that resolves the target BY IDENTITY, so F58 landing on top costs nothing.
      CARRIED: F37 attaches its SOS alert to the assignment row and the handover keeps
      the assignment id stable for exactly that reason. Nine mutation checks were run;
      TWO CAME BACK GREEN and are recorded IN THE CODE as not-actually-pinned rather
      than left as false confidence (populate_existing=True, and the five explicit
      tenant_id predicates that RLS already carries).
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
    status: merged
    pr: 36
    attempts: 1
    deps: [F5, F9, F10, F13]
    spec: .planning/specs/qr-walkin-queue.md
    plan: .planning/plans/qr-walkin-queue.md
    shipped: >-
      MERGED 2026-08-03 as PR #36. ALL THREE GATING JOBS GREEN ON THE FIRST CI RUN,
      merge-gate.sh exit 0. Migration 0018_queue_tickets. Gates run locally on the
      exact pushed tree: lint clean, 1548 backend fast, 481 backend db AGAINST REAL
      POSTGRES 16.14, frontend 104 ui / 943 storefront / 598 manage, 74 e2e (69
      before) with axe at zero, alembic heads printing exactly one head.
      FOUR THINGS A LATER READER NEEDS.
      (1) THE PLAN WAS STALE AND THE BUILDERS CAUGHT IT. The spec gained RULING 3
      after the plan was written, and both were committed in one commit so git shows
      no ordering. Ruling 3 DELETES server-side dedup entirely — no unique index, no
      advisory lock, no pre-check, no IntegrityError path, no {"ticket": null}
      branch, no CheckinCreateResponse envelope, no per-phone limiter. Building the
      plan as written would have shipped the exact defect the ruling removes. The
      builders built to the SPEC and said so; the plan on main has since been
      replaced with the corrected version (C1-C23).
      (2) WHY DEDUP IS GONE, because it looks like a regression and is not. Two
      holes, and the second is the bad one. THE ORACLE: with dedup, submitting a
      phone that IS in the queue returned a distinguishable answer — free, silent,
      unbounded, no row written, no evidence anywhere — so anyone could test whether
      a named woman was standing in a named bridal boutique. THE DENIAL: the dedup
      key was freed only by a status change or a soft delete and F33 ships a writer
      for NEITHER (that is F58), so ONE anonymous POST with a known mobile denied
      that woman a queue slot for the rest of the boutique day with no remedy
      anywhere in the product. The create now always creates and always returns a
      full TicketView, so the response is IDENTICAL whether or not that phone is
      queued — that identity IS the security property. A duplicate ticket is a real,
      expected outcome and F58 merges or removes it. Re-scan comfort moved to a
      sessionStorage pointer that dies with the tab and is NOT a security control.
      (3) THE MIGRATION COLLISION HAPPENED, exactly as the rule predicted. The branch
      was built at 0016/down 0015; F19 shipped 0016_deposit_flow while it was
      building. Two files claiming one revision id MERGE WITH NO GIT CONFLICT because
      the filenames differ. Review caught it as a BLOCKER and it shipped as
      0018/down 0017. This is the third time in this program that a pre-written
      guard or an adversarial reviewer caught a clean-rebase collision.
      (4) TWO DEFECTS THE TOOLING CAUSED, not the design. Three build agents died
      mid-task on API 529s. One died having created three storefront modules and
      NEVER `git add`ed them, while committed code imported them: HEAD was broken and
      the working tree looked perfect. There is now a permanent guard,
      backend/tests/test_frontend_imports_are_tracked.py — any later feature whose
      agent dies the same way fails loudly instead of merging a broken HEAD. Review
      also caught a global print stylesheet (`@media print { body * { visibility:
      hidden } }` in index.css, imported unconditionally) that would have made every
      OTHER console section print a blank page; it is now scoped to the QR sheet.
      CARRIED: the collection-notice wording stays OPEN in in_run_gates — it blocks
      two strings, not the feature, and a neutral interim ships meanwhile. F58 now
      owns merging or removing duplicate tickets, and it is the feature that gives
      the status column its first writer.
    resumed: >-
      2026-08-03 12:50 by a NEW session, after the session that wrote the spec and
      plan stopped without committing them — both sat UNTRACKED in the main
      checkout and are committed with this status change. Gates 1 and 2 are
      self-approved (standing approval; the collection-notice string stays parked
      in in_run_gates and a neutral interim ships, which is the F19 precedent).
      The worktree carried an 8-line uncommitted conftest.py addition from that
      session — inspected and kept/discarded deliberately at build start rather
      than trusted as done, per the F57 resume precedent.
      MIGRATION: resolve from `alembic heads` at rebase time. See the rule block
      at the top of `current:` — the old fixed 0016 claim was derived from a head
      of 0014 and is off by one now that F57's 0015 has merged.
    started: >-
      2026-08-03, in PARALLEL with F57 and in its own worktree
      (.worktrees/qr-walkin-queue). Picked because F36, the next entry in file
      order, deps on F57 and cannot be built beside it; F33's deps are all
      merged history, which makes it the loop's own next pick.
      THREE USER RULINGS taken at pick time:
        (1) build F33, not F60 and not an idle wait for F36;
        (2) the printable QR renders SERVER-SIDE via `segno` — pure-Python, zero
            transitive deps — so the manage bundle grows by nothing and the print
            page is a plain <img>; the npm qrcode route was declined;
        (3) the collection notice ships as a NEUTRAL INTERIM sentence and the
            in_run_gates F33 entry STAYS OPEN. This is the F19 precedent exactly.
      MIGRATION: 0016, down_revision 0015. Resolve from `alembic heads` again
      immediately before push; do not open the PR until F57's 0015 is on main.
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
      contractually GET-only — with its OWN FixedWindowRateLimiter instances.
      One budget = one instance: never reuse the OTP or booking limiters, or a
      busy bride morning locks the door queue.
      ⚠ "Dedup on (tenant, phone, day)" AND the per-phone limiter WERE in this note
      and are BOTH DELETED — see the spec's RULING 3, which supersedes this line and
      is the single most important thing about this feature. A later reader who wants
      dedup back must answer its two arguments first, because both are security, not
      taste. (1) THE ORACLE: with dedup, submitting a phone that IS in the queue got a
      distinguishable answer — free, silent, unbounded, no row written, no evidence
      anywhere — so anyone could test whether a named woman was standing in a named
      boutique. (2) THE DENIAL, which is worse: the dedup key was freed only by a
      status change or a soft delete, and F33 ships NEITHER (the staff view that would
      write them is F58), so ONE anonymous POST with a known mobile denied that woman a
      queue slot for the rest of the boutique day, with no remedy anywhere in F33.
      So the create ALWAYS creates and ALWAYS returns a full TicketView: one response
      shape, no branch, identical whether or not that phone is already queued. That
      identity IS the security property. Deleted with it: the partial unique index, the
      advisory lock, the Python pre-check, the IntegrityError path, the {"ticket": null}
      branch, the CheckinCreateResponse envelope and the per-phone create limiter.
      A duplicate ticket is now a REAL, EXPECTED outcome that F58 merges or removes —
      that is the accepted cost. Re-scan comfort moved to a sessionStorage pointer that
      dies with the tab and is explicitly NOT a security control.
      Live-position view polls its own public GET keyed by the ticket UUID (the id is
      the capability; the response carries position + ahead-count + status and echoes
      no PII). One static printed QR per boutique (#30), rendered server-side in manage
      via `segno` (pure Python, zero transitive deps — the manage bundle grows by
      nothing and the print page is a plain <img>). Auto-delete days after the visit
      stays F20's retention job's second consumer. Hebrew only; ar keys untranslated.
  - id: F58
    slug: floor-dispatch
    epic: E6
    title: "Waitlist panel + dispatch (take-next, push-assign, finish, skip)"
    status: building
    attempts: 1
    deps: [F33, F36, F57]
    spec: .planning/specs/floor-dispatch.md
    plan: .planning/plans/floor-dispatch.md
    started: >-
      2026-08-03 22:00, worktree .worktrees/floor-dispatch. THE CRITICAL PATH — see
      deployment_gates; F33 and F59 are both merged-but-not-launchable until this ships.
      SPEC REVIEW: 33 findings from 3 lenses, 32 applied. Two blockers were defects in
      the PROOF rather than the design, which is the rarer and more dangerous kind:
      (1) D3a's stranding proof was misdiagnosed and ITS MUTATION WAS VACUOUS.
      tenant_session is `async with session_factory() as session, session.begin()`, so
      a propagating exception ALREADY rolls back — the claim that a raised 409 would
      let the enclosing session commit is false, the named mutation came back GREEN,
      and A8 (the single test on which F33's deployment gate is discharged) asserted
      NOTHING. Restated truly: every refusal RAISES; nothing may `return` after the
      ticket UPDATE, because a return is the one construct that commits. F36's
      idempotence `return` is the real mutation, and A8b forbids the branch returning.
      (2) TWO CONCURRENT FIRST SKIPS irreversibly REMOVED a customer with the confirm
      bypassed: B's EvalPlanQual re-check passes on A's new tuple, reads skip_count 1
      and jumps to `removed`, while both clients rendered 0 and showed no confirm. The
      old acceptance criterion asserted that outcome AS THE PASS CONDITION. Fixed with
      an `AND skip_count = :seen` conjunct and a third conflict code.
      (3) Four announced cues would have put a CUSTOMER'S NAME into FloorPanel's
      PERSISTENT role="status" region on the five-role screen — worse than the case F36
      explicitly declined, since a removed woman's name would outlive every other trace
      of her. All four now name the act.
      Also: "F58 needs no migration" is FALSE (0019's own DDL comment says F58 adds
      queue_ticket_id alongside its writer); FINISH extends FloorService.release rather
      than adding a sixth route, so F36's shipped release cannot free a room and strand
      a ticket in_service; and a three-role gate is structurally forbidden by a shipped
      walker test that names F58 — so reception cannot skip or remove, recorded as a
      product limitation with an upgrade path rather than worked around.
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
    status: merged
    pr: 38
    attempts: 1
    deps: [F33]
    spec: .planning/specs/public-queue-board.md
    plan: .planning/plans/public-queue-board.md
    started: >-
      2026-08-03 19:10, worktree .worktrees/public-queue-board. Eligible the moment
      F33 merged. Gates 1 and 2 self-approved.
      ⚠ SEE deployment_gates BELOW — this merges but does NOT go on a wall until F58.
      NO MIGRATION, deliberately: F33's queue_tickets already carries every column and
      its (tenant_id, queue_day) partial index is already the exact access path. A
      builder who adds one has misread the feature.
      SPEC REVIEW: 34 findings from 3 lenses, 31 applied, 3 rejected in writing.
      FIVE BLOCKERS. The three worth carrying:
      (1) THE INTERIM BOARD IS NOT DEPLOYABLE and an earlier draft claimed it was
      useful. With no writer for called_at or the status column, nothing is
      highlighted and the board only GROWS; because the order is arrival order and
      the cap is five rows, THE FIVE NAMES FREEZE mid-morning and are still on the
      screen at midnight. The usefulness claim is deleted; the deployment gate is
      the only interim position. See deployment_gates.
      (2) THE BRIEF'S "PUBLIC GET" IS UNAVAILABLE. test_storefront_api.py derives its
      route list over EVERY GET under /storefront and asserts 429 on each against the
      shared storefront limiter, so a GET here answers 200 and reddens a shipped
      guard. The only escapes were sharing the catalog's budget (the exact failure
      main.py names verbatim) or weakening a guard protecting six shipped reads. It
      is a POST — and NOT for F33's reason (F33's routes carry a capability; this
      request body is empty), so the argument is recorded separately.
      (3) THE TV TYPE SCALE WAS clamp()-ed AGAINST vh ONLY, which makes browser text
      resize INERT — a WCAG 1.4.4 AA failure that axe cannot see and that no shipped
      resize sweep covered because /queue was not in RESIZE_ROUTES. Every size is now
      clamp(<rem>, <rem> + <vh>, <rem>) with a 6-column proof table, and A34 pins it.
      ALSO: D13 AMENDS A SHIPPED STRING. F33's check-in notice promises the record is
      shown on "a screen in the boutique". The real processing is publication to an
      unauthenticated worldwide URL, and consenting to the first is not consenting to
      the second. The clause now names the public page. Do not soften it back.
    shipped: >-
      MERGED 2026-08-03 as PR #38, ALL THREE GATING JOBS GREEN ON THE FIRST CI RUN.
      NO MIGRATION — alembic heads unchanged at 0019, which is the claim D2 makes and
      a reviewer verified. Gates local on the pushed tree: 1702 backend fast, 550
      backend db on REAL POSTGRES 16.14, 104 ui / 1013 storefront / 729 manage,
      77 e2e (74 before), axe zero. Build ran 18 agents, ZERO failures.
      ⚠ STILL GATED — see deployment_gates. This merges; the TV does not go on a wall
      until F58 ships.
      THREE THINGS A LATER READER NEEDS.
      (1) A MUTATION CHECK CAUGHT A VACUOUS TEST AND THE TEST WAS STRENGTHENED RATHER
      THAN THE MUTATION ACCEPTED. `test_the_board_order_agrees_with_the_position_count`
      seeded five all-waiting rows, so widening the status filter ON THE BOARD SIDE
      ONLY added no rows and the alarm never fired — the one test whose entire job is
      catching that divergence was blind to it. It now seeds done / in_service /
      soft-deleted / yesterday noise, all EARLIER than every real row, so any one-sided
      widening shifts a position. This is the discipline working: the plan says "fix
      the seed, not the assertion".
      (2) THE PREDICATES ARE NOW SHARED WITH position(), not copied. A divergence
      between the wall and the customer's own phone (she reads 3rd, the wall says 4th)
      is structurally impossible for the shared half rather than merely test-caught.
      The day binding still differs and the helper docstring says why.
      (3) REVIEW'S TWO SURVIVORS WERE BOTH REPRODUCED BY EXECUTION, not argued. The
      MAJOR: in the `failed` state the freshness line rendered «עודכן» with a blank
      time — the page's one designated honesty signal, dangling beside a visible error.
      The sibling position page cannot reach it because it gates on a loaded ticket;
      F59 dropped that gate deliberately and added no replacement arm.
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
    spec: .planning/specs/sos-paging.md
    plan: .planning/plans/sos-paging.md
    gates_done: >-
      Gates 1 and 2 cleared 2026-08-03; deps became merged history when F36 landed.
      SPEC REVIEW: 33 findings from 3 lenses, 33 applied, 0 rejected. Five blockers,
      and EVERY ONE of them was a way an emergency page could be silently lost — which
      is the only defect class that actually matters in this feature:
      (1) AN ACCEPTED ALERT WHOSE RESPONDER VANISHES was lost forever while the raiser
      was actively told help was coming: _escalated short-circuited on status != OPEN,
      so the first «אני מגיעה» stopped every mechanism permanently. Fixed with a second
      READ-TIME boolean (_stalled, 2 minutes) using the identical zero-write mechanism
      — one constant, one branch, one payload field, no column, no worker.
      (2) A TERMINAL POLL KILLED THE EMERGENCY CHANNEL WITH ZERO SIGNAL, and the spec's
      stated mitigation DID NOT EXIST — App.tsx has no fetch interceptor and onNavigate
      is just setSection, so "App will show the login form on her next navigation" was
      simply false. Fixed with an onSessionEnded wire and a persistent channel-down
      strip, because the overlay is the only app-level surface on the eleven sections
      that poll nothing else.
      (3) DISMISSING ON A NON-FLOOR SECTION HID A LIVE EMERGENCY PERMANENTLY. SosCentre
      is a child of FloorPanel and so mounts on 2 of 13 sections; on the other eleven
      the dismiss set was the only state. Fixed by keying the set on
      `${id}:${escalated}:${stalled}` so a safety net re-raises a dismissed card once,
      plus a persistent affordance while any live alert is dismissed.
      (4) THE ALERT WAS ANNOUNCED PERFECTLY TO A KEYBOARD USER WHO COULD NOT REACH THE
      ACK CONTROL — for a user mid-form, «אני מגיעה» sat behind a Shift+Tab run past her
      whole section and the console chrome. Fixed with a document-level capture keydown.
      Also found: «בדרך» is BANNED by i18n.test.ts, which the natural copy would have
      used; and the epic's "every on-shift staffer" has NO REFERENT in the shipped
      schema — there is no on-shift column anywhere — so targeting reads a live
      `sessions` row instead, which is literally what the device-identity ruling
      describes and cannot go stale.
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
    status: merged
    pr: 39
    attempts: 1
    deps: [F8, F13, F31, F34, F57]
    spec: .planning/specs/alteration-tickets.md
    plan: .planning/plans/alteration-tickets.md
    started: >-
      2026-08-03 17:40, worktree .worktrees/alteration-tickets, in PARALLEL with F36.
      Eligible because F57's merge made every dep merged history. Gates 1 and 2
      self-approved; design gate too.
      SPEC REVIEW: 32 findings from 3 lenses, 32 applied, 0 rejected outright.
      FOUR BLOCKERS, and THREE OF THEM WERE ONE SHAPE — a state machine whose
      "impossible" branch was reachable. Worth reading before touching this code:
      (1) THE ADVANCE'S UNREACHABLE BRANCH IS REACHABLE. D3 documented
      `stage_of(row) < target` as impossible after a zero-row UPDATE. But a zero-row
      UPDATE TAKES NO LOCK and the repo runs READ COMMITTED, so a concurrent undo can
      clear the target column between the write and the re-read; `elif stage > target`
      with no else then returns None and 500s. The discriminator is now ONE EQUALITY
      AND ONE ELSE (== target -> 200, anything else -> 409), and the identical hole is
      closed in undo and assign. A forced-interleave db test pins it.
      (2) THE WALKER RESTRUCTURE HANDED seamstress THE DELETE ROUTE that the same
      section takes away, so the test would have failed against CORRECT code — on the
      one test F57's Risk 1 declares untouchable. ATELIER_DELETE is now its own
      constant outside the non-elevated reach set.
      (3) THE STAGE-SKIP SELECT FIRED AN IRREVERSIBLE WRITE ON `change`. A keyboard
      user arrowing to the last stage would fire three advances, three audit rows and
      three focus moves — WCAG 3.2.2 Level A, and it would have been the first Select
      in this console to mutate on change. Both selects now set draft state and a
      sibling button commits, which is how every other Select here already works.
      (4) TWO ROUTES SHIPPED A SERVER WITH NO CLIENT: POST /update and POST /delete had
      no affordance, no states, no copy, no focus destination and no test — and delete
      is destructive, un-undoable and elevated-only.
      NO DRAG-AND-DROP AT ALL, by ruling: a drag-only kanban is unusable by keyboard
      and screen reader, and a11y here is legal, not preference. The board moves by
      explicit controls with five named focus destinations.
      MIGRATION: built at 0019, renumbered to 0020 when F36 took 0019.
    shipped: >-
      MERGED 2026-08-03 as PR #39, migration 0020_alteration_tickets — but ON THE
      THIRD CI RUN, and it is the only feature this run that CI turned back. Both
      red runs are worth reading, because one was a real defect and one was not, and
      they looked identical from the outside (a red "Frontend (lint, types, build)"
      on a branch whose every local gate was green).
      RED 1 — A REAL PRODUCT DEFECT THAT EVERY LOCAL GATE MISSED. Test 5a asserted
      focus follows a card that a colleague moves under you, and CI read <body>.
      Local full-suite PASSED, local isolated FAILED, CI full-suite FAILED — three
      behaviours, and any explanation covering one is wrong. Instrumentation found
      the cause: the restore effect has NO DEPENDENCY ARRAY, so React queues it after
      EVERY commit, and React's first act on a new render pass is to flush the
      PREVIOUS commit's passive effects. So the effect ran once BEFORE the repaint it
      was waiting for, read the intent, CLEARED IT UNCONDITIONALLY, failed its own
      precondition and returned — and the real repaint arrived one commit later with
      nothing left to restore. THE LOCAL/CI DIFFERENCE IS EXACTLY ONE EVENT-LOOP TURN
      (an A/B probe: zero extra turns strands focus, one extra turn restores it), so
      local green was luck, not correctness. It reproduces with REAL timers and no
      `act` on a 150-card board, which is what makes it a product defect and not a
      harness artifact: a seamstress tabbed onto a card control has her focus dropped
      to <body> five seconds after a colleague touches that ticket from another
      phone, the screen reader goes silent, and her next Tab restarts at the top of
      the document. Test 5b was latently broken too; CI just happened to report 5a.
      This is the FIFTH instance of this bug class here (F56, F34, F57, F57's vacuous
      focus test, now this) and the SECOND of the exact clear-before-confirm shape.
      ⚠ THE FIRST FIX WAS WRONG AND AN ADVERSARIAL VERIFIER CAUGHT IT. It kept the
      intent whenever focus was still inside the captured card — which CREATES A NEW
      FOCUS STEAL in the other direction, measured: she tabs out of the document
      herself, the next poll FAILS (the catch path never re-captures), and the stale
      intent fires and yanks focus back onto the card. A WCAG 3.2.x defect newly
      created by an a11y fix. The verifier also caught that the fix's justifying
      comment cited BookPage/ManageBookingPage/MediaGallery as precedent when their
      pattern is different in kind (they key on WHETHER THE TARGET NODE IS MOUNTED and
      carry no activeElement guard, so a held intent can only ever be honoured by the
      render that mounts the node she asked for — "a delayed correct move, never a
      wrong one"). Those three were left untouched, correctly.
      THE SHIPPED FIX stamps each intent with the board-commit COUNT it was recorded
      at and expires it on the first commit past that: stale passes never reach the
      clear, and commits no payload preceded (setStale, the pause toggle, a keystroke)
      never reach it either. Both directions are pinned, both mutations demonstrated
      red, and a third mutation (keep-until-consumed) reds them too — so the tests pin
      the PRINCIPLE, not one predicate. 5d additionally pins the `<=` boundary, which
      was unpinned until a verifier noticed `<` left all 96 tests green.
      RED 2 — NOT A DEFECT AT ALL: 5c and 5d TIMED OUT at the 5s default. They render
      150 cards deliberately, because that is what makes React exceed its 5ms frame
      budget and yield between commit and passive flush — the mechanism itself.
      Shrinking the board to fit the timeout would have deleted the defect rather than
      the delay, so the timeout moved to 20s instead and the mutation was re-verified
      after the change. WORTH GENERALISING: a test whose SIZE is load-bearing needs an
      explicit timeout, because the default is sized for typical tests and CI's
      contended two-core runner is several times slower than this machine.
      SPEC-REVIEW BLOCKERS (32 findings, all applied) are in `started:` above; the
      sharpest was an "impossible" state-machine branch that a zero-row UPDATE's
      missing lock makes reachable under READ COMMITTED.
      MUTATION CHECKS FOUND THREE TESTS THAT COULD NOT FAIL, all closed: a missing SQL
      LIMIT was invisible behind a Python slice (the SELECT materialised the whole
      table every 5s and the response was byte-identical); populate_existing=True
      survived removal because a single-writer test can never show it (it only bites a
      STALE identity map); and an undo's later-columns clause survived because the
      test's target column was already NULL so `IS NOT NULL` refused the write
      single-handed.
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
    status: merged
    pr: 34
    attempts: 1
    spec: .planning/specs/deposit-booking-flow.md
    plan: .planning/plans/deposit-booking-flow.md
    deps: [F7, F16, F17]
    spec_gate: user
    shipped: >-
      SHIPPED as PR #34, merged 2026-08-03. ALL THREE GATING JOBS GREEN ON THE
      FIRST CI RUN. MIGRATION 0016, down_revision 0015 — so main's head is now
      0016 and F33/F53 resolve from there, not from the numbers this file
      assigned earlier.
      IT TOOK THE NEXT FREE NUMBER RATHER THAN RESERVING 0017 BEHIND F33, and
      that correction matters for whoever lands next: a migration numbered 0017
      with down_revision 0016 CANNOT PASS CI UNTIL 0016 EXISTS, so reserving
      would have blocked a finished feature on an unfinished one indefinitely.
      "Resolve from `alembic heads` immediately before your rebase" is the rule;
      a fixed grid is not.
      THE SINGLE-HEAD GUARD EARNED ITSELF ON ITS FIRST REAL COLLISION. The
      rebase onto merged-F57 produced two files declaring revision "0015" —
      different filenames, textually clean merge, nothing wrong-looking in
      review. test_exactly_one_migration_head failed in `make test` in under a
      second and named both heads; renumbering was two literals and a filename.
      Without it the first symptom is every db test erroring at CI fixture setup
      on a branch that was green an hour earlier, with a diff touching no
      migration. It is permanent, not scaffolding.
      THREE BUGS WERE FOUND BY RUNNING THE db SUITE LOCALLY (throwaway Postgres
      16, no Docker) INSTEAD OF LETTING IT DEBUT ON CI — which is why the first
      CI run was green rather than the usual one-red-run-and-a-fix-commit:
        (1) A LATE PAYMENT WAS SILENTLY DROPPED, in shipped F17 code.
            PaymentsRepository.by_id returned the identity-mapped instance
            without refreshing, so after the sweeper expired a row in a
            concurrent transaction, _explain_missed_settlement re-read the SAME
            STALE OBJECT and reported 'pending'. deposit_reaction reads pending
            as "a decline — do nothing", so a bride whose money arrived late had
            her payment left expired, her booking cancelled and NOBODY alerted —
            the exact outcome F17's Gate 1 Q4 ruled must never happen. It
            reproduced ~1 run in 3 under asyncio.gather and was invisible to
            every sequential test. Fixed with populate_existing=True, the same
            trap F34 documents on BookingsRepository._refreshed.
        (2) THE SWEEPER'S ORPHAN CLAIM COULD CANCEL A PAID BOOKING. The spec's
            own SQL excluded only `pending` payments, so race row #11 — the
            crash between settle's commit and the confirm — got its booking
            cancelled, and the redelivery that would have repaired it then
            matched nothing. Any provider whose retry backoff exceeds the hold
            length triggers it every time. Predicate is now pending OR paid.
        (3) THE DOWNGRADE ONLY WORKED UNTIL THE FEATURE HAD BEEN USED. Postgres
            validates ADD CONSTRAINT against the whole table, so narrowing a
            CHECK is refused once a row holds the value. Data now moves first.
      GATE 3.5: 12 findings across three lenses, each adversarially verified;
      10 refuted, 2 confirmed and fixed — the declined payment state was
      UNREACHABLE (it branched on a status the backend never writes on that path
      and its test pinned a fiction), and D18/MD4's action-needed marker rendered
      only in the detail panel, not in "the list the owner already loads every
      morning" — which MD4's own audit note had predicted would be the part most
      likely dropped, because it is the only part with no test that fails loudly
      without it.
      MD3 REMAINS PARKED and its in_run_gates entry STAYS OPEN. The neutral
      interim shipped; the shipped manage.cancelConsequenceFree did NOT survive
      the merge — it is now conditioned on the booking having no deposit.
    started: >-
      2026-08-03, in PARALLEL with F57 and F33, in its own worktree
      (.worktrees/deposit-booking-flow on feature/deposit-booking-flow). Picked
      because every remaining floor-block entry deps on F57 or F33, and F60 —
      the only one that does not — is the brief's lowest-priority item and wants
      a hint step on F33's unbuilt /checkin page. F19's deps are all merged, so
      it is an eligible pick by the loop's own rule.
      GATE 1 WAS ALREADY CLEARED: see gate_1_preauthorized below. The spec is
      written and adversarially reviewed (32 findings, 9 BLOCKER, all applied,
      0 rejected), so this session starts at GATE 2 — the plan — not the spec.
      SEVEN CORRECTIONS were found against the spec by a code recon at pick time
      and are applied in plan Task 0. The load-bearing one is the migration
      number: the spec says "Migration 0014" throughout, but 0014 is F34's
      shipped 0014_booking_check_in and F57/F33 hold 0015/0016. F19 builds
      against 0015/down_revision 0014 so its branch is self-coherent, then
      RENUMBERS to 0017/down_revision 0016 at rebase time. Do not open the PR
      before F57 and F33 merge. The other six are shifted line citations in
      db/repositories/bookings.py and dashboard/service.py (F34 moved them),
      main.py's PaymentService placeholder at :709-712, constants.py being a
      live merge surface F57 is also editing, the late-settlement test seam at
      test_payments_service.py:921-925 that must not be copied, and
      bookings.source not existing (it is F50's, unbuilt).
      MD3 STAYS PARKED and its in_run_gates entry stays open — it blocks two
      strings, not the feature, and the neutral interim ships meanwhile. The
      SHIPPED manage.cancelConsequenceFree sentence must not survive the merge
      either way; that is the one frontend edit F19 cannot ship without.
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
    status: merged
    pr: 35
    attempts: 1
    deps: [F31]
    shipped: >-
      SHIPPED as PR #35, merged 2026-08-03. ALL THREE GATING JOBS GREEN ON THE
      FIRST CI RUN, on a feature with 98 db-marked tests. Not luck: Postgres
      16.14 is installed on this machine, so the whole db suite ran locally
      before the push via main's TEST_POSTGRES_SUPERUSER_URL hatch. THE "no
      Docker locally, db tests debut on CI" PREAMBLE IS STALE — stop budgeting a
      red first round for it. The migration's column row was CAPTURED from a
      live cluster (ARRAY / '{}'::text[] / _text) rather than transcribed, and
      atthasmissing = t confirmed the PG11+ lazy default, so the NOT NULL DEFAULT
      is a catalog-only ALTER with no table rewrite.
      REVIEW: spec 4 lenses -> 22 findings, 0 blockers, 21 fixed + 1 rejected in
      writing; code 5 lenses, every major judged by an independent skeptic ->
      1 survived, 3 refuted, 8 minors, all 9 fixed.
      FOUR THINGS A LATER READER NEEDS.
      (1) THE SMS-LOG PHONE LEG IS FENCED WITH `AND booking_id IS NULL` AND THAT
      IS THE FEATURE. message_log has no customer_id, so a row is attributable by
      booking_id or by phone. Phones are corrected (set_phone) AND recycled by
      carriers. Unfenced: bride A books on phone X, owner corrects A to Y, bride
      B later registers with X, and B's detail renders A's confirmation bodies —
      which carry A's name and appointment time. Cross-customer disclosure inside
      one tenant, invisible to RLS and to every isolation test in the repo. The
      residual (a masked OTP row, no name, no digits) is accepted and named.
      (2) THE PHONE SEARCH WAS BROKEN AS FIRST SPECIFIED, and invisibly so.
      customers.phone only ever holds strict E.164 — normalize_israeli_mobile
      rewrites a typed 05X… to 972+rest — so '+972501234567' ILIKE '%0501234567%'
      is FALSE, and so is '%050%'. Reading the number off a card or typing the
      050 prefix would both have returned "no results" for a customer who
      demonstrably exists. The phone leg runs on a digit-normalized term; the
      name leg stays raw; autoescape=True on both.
      (3) TWO GUARDS BROKE BY BEING LANDED ON TOP OF, neither a defect in F53.
      test_the_deposit_migration_round_trips derived its downgrade target from
      head.down_revision — true only while F19's migration WAS head — so 0017
      made it stop one revision short and reddened a payments test from a feature
      touching no payments file. It now resolves the revision by its own message.
      And Nav.test.tsx asserted toHaveLength(10) against an 11-row nav: adding a
      `roles: ALL` row is FIVE coordinated edits (labels, length, owner count,
      shift-manager slice, and the test names that spell both in words).
      (4) A CLEAN REBASE STILL SHIPPED A SILENT BREAK. Resolving a conflict whose
      boundary cut mid-block left api.test.ts with two missing braces. esbuild
      answers `Transform failed` and vitest prints `Tests no tests` — ONE line,
      not sixty — so every api-client test in apps/manage was unexecuted until it
      was caught. Parse every resolved file, in every language, not just the ones
      whose parser you happen to run.
    started: >-
      2026-08-03, in PARALLEL with F57, F33 and F19, in its own worktree
      (.worktrees/customers-crm). Picked on USER INSTRUCTION for a feature
      depending on none of those three; see the `current:` block for why F60 and
      F50 were rejected. Deps [F31] are merged history.
      MIGRATION: 0018, down_revision 0017. Resolve from `alembic heads` again
      immediately before push; the migration is the LAST commit on the branch so
      the renumber costs one amend to one file nothing else references. Do not
      open the PR until 0015/0016/0017 are all on main.
      TWO SHIPPED GUARDS BITE THIS FEATURE and are cheaper to read than to
      rediscover. (1) i18n.test.ts:247 rejects any string matching
      /נשלח|תישלח|בדרך/, so the natural SMS-log heading «הודעות שנשלחו» is
      refused — «יומן הודעות» is the shipped copy, and it is also the honest one
      because the log renders status='failed' rows. (2) test_spa_serving.py:372
      asserts set equality between the live /manage route table and the vite dev
      proxy's segment alternation, so the `customers` segment must be added to
      Frontend/apps/manage/vite.config.ts or the console silently gets the SPA
      shell with a 200 and the wrong body — the exact bug F52 shipped.
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

deployment_gates:               # MERGED code that must NOT be switched on yet, and what clears it.
                                # Added 2026-08-03 because this was recorded only inside a spec, and
                                # "merged" was reading as "launchable" in this file. It is not the
                                # same thing, and the run report has to say so.
  - feature: F33
    gate: "merges and is fully tested, but is NOT enabled for a live pilot tenant"
    cleared_by: F58
    why: >-
      Ruling 4, qr-walkin-queue.md:13 and its «Deployment ordering» section. Three
      findings collapse into one ordering constraint: F33 writes queue tickets that
      NO SHIPPED SURFACE RENDERS; a duplicate ticket is a normal outcome under
      Ruling 3 and NOTHING in F33 can merge or remove one; and the position page's
      success terminal is unreachable because nothing in F33 writes `done` or
      `removed`. F58's waitlist panel is the first surface that can see the queue,
      and therefore the first that can fix it.
  - feature: F59
    gate: "merges, but the TV does not go on a wall"
    cleared_by: F58
    why: >-
      Inherits F33's gate rather than adding a second one (public-queue-board.md
      D10(4)). Sharper here, and it is a PRIVACY point as much as a usefulness one:
      with no writer for `called_at` or the status column, nothing is ever
      highlighted, the board only grows, and because the order is arrival order and
      the cap is five rows, THE FIVE NAMES ON THE SCREEN ARE THE DAY'S FIVE EARLIEST
      CHECK-INS AND NEVER CHANGE FROM ABOUT 09:15 TO MIDNIGHT. A woman who arrived at
      09:00 and left at 10:00 is still on a public screen at 17:00. Publishing that
      all day on an unauthenticated URL is not «לצורך ניהול התור בלבד», which is the
      purpose limitation the shipped check-in notice promises her.
      Also: the kiosk runs ONE full-screen tab with screen-blanking disabled — the
      poll stops on `document.hidden` by design, which is right for a phone and wrong
      for a wall.
  # WHAT THIS MEANS FOR THE RUN: F58 is not just the next floor feature, it is the
  # CRITICAL PATH — two already-merged features are inert until it lands. It is
  # blocked only on F36, which is building now.

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
  - test: "backend/tests/test_booking_owner_db.py::test_two_concurrent_reschedules_of_one_booking_never_self_collide"
    seen: "2026-08-03 during F59's build, in a full local db run against Postgres 16.14"
    evidence: >-
      Failed once in a full db run, PASSED in isolation, and did not recur in the
      final full run of the same tree. F59 touches nothing in booking reschedule —
      its diff is the queue board — so this is not an F59 regression.
    why_it_matters: >-
      It is a db-marked CONCURRENCY test, so the failure mode it guards is real and a
      flake here is the worst kind: it trains whoever is watching to re-run a red
      concurrency test rather than read it. It has only been seen locally, never on
      CI, which may mean the local runner's shared cluster is the trigger rather than
      the test. Diagnose before assuming either.
    owner: unassigned — pick up at the E6 epic boundary
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
