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

current: F21                    # ==================================================================
                                # ==== IN FLIGHT, 2026-08-05 — F21 hardening-audits-uat ===========
                                # ==================================================================
                                # F21 STARTED 2026-08-05. E4's last entry. Its note mandates a SPLIT:
                                # the rows needing no production environment build now; the rows that
                                # need a live staging host become a parked follow-up. The domain IS
                                # bought (modryn.co.il) but its 3 DNS records are unadded, so there is
                                # still no reachable host — the split stands.
                                #
                                # 26 MERGED · 20 QUEUED · 1 PARKED FOREVER (F32, subsumed).
                                # NOTHING IS USER-BLOCKED. The next pick is plain file order:
                                # F21, then F22 F24 F25 F27 F28 F35 F38 F44 F47 F49 — ELEVEN are
                                # eligible right now, so parallel sessions are worth running.
                                # See `remaining_work_estimate` for the sizing and the ~4-5 day
                                # (parallel) / ~11 day (sequential) figures, both anchored on
                                # measured wall-clock rather than feel.
                                #
                                # F61 SHIPPED (PR #47) AND CLOSED THE WALKTHROUGH DEBT. All nine
                                # known_product_bugs carry `fixed_in: F61`; only /fake-pay remains,
                                # and it is a LOW backend tidiness item.
                                #
                                # ⚠ THE OPERATIONAL LESSON OF THIS SESSION, worth more than the
                                # fixes: A REVIEWER THAT DIES MID-MUTATION LEAVES SOURCE REVERTED.
                                # One died between its revert and its restore, leaving fabricated
                                # i18n keys in an ErrorBoundary — the fallback for a crashed app,
                                # itself broken, one commit from shipping.
                                # THE RULE IS NOT "CHECK FOR A DIRTY TREE". It is:
                                #   1. is an agent LIVE?  find <dir> -name 'agent-*.jsonl' -mmin -5
                                #   2. THEN read the tree.
                                # Dirty + live  = work in progress, DO NOT TOUCH.
                                # Dirty + dead  = a mutation to revert.
                                # Getting that backwards costs either a live agent's work or a
                                # shipped fabrication. This session got it wrong once in each
                                # direction before settling on the ordering above.
                                #
                                # ---- the 2026-08-04 handoff, still accurate below ----
                                # ==================================================================
                                # 25 MERGED · 20 BUILDABLE · 1 PARKED FOREVER (F32, subsumed).
                                # (PR #44 is not in that count — it was debt + infrastructure,
                                # not a queue entry. FOUR PRs shipped this session: #44 harness,
                                # #45 F20, #46 F50, plus dd75ea1's walkthrough findings on main.)
                                # ELEVEN ARE ELIGIBLE RIGHT NOW, verified by resolving deps against
                                # the merged set rather than by reading file order:
                                #   F21 F22 F24 F25 F27 F28 F35 F38 F44 F47 F49
                                #
                                # ✅ THE NINE WALKTHROUGH DEFECTS ARE ALL FIXED — F61, the a11y/UX
                                # batch this block asked for. DO NOT RE-PICK THEM: every entry in
                                # `known_product_bugs` now carries `fixed_in: F61` and the test that
                                # reds if the fix is reverted, and every one of those mutations was
                                # RUN. Six were a11y, a LEGAL requirement here (IS 5568 / WCAG 2.0 AA).
                                # The two worst were invisible to both suites by construction — a
                                # role="status" that never fires and an aria-invalid that lies about
                                # corrected input — and the batch closed the instruments too:
                                # a MutationObserver on the live region for the first, and a real
                                # Chromium keypress for the implicit-submission half of the second.
                                # F61 also found a TENTH, in the fix for the fifth: `/checkin` had the
                                # same missing <form> as the booking flow and the first pass shipped
                                # only the booking half. Read `known_product_bugs`' new header for the
                                # three lessons that outlive the nine — the live-region one is a
                                # STILL-OPEN sweep across three more files.
                                # NOTHING IS USER-BLOCKED. Two user items remain and BOTH are
                                # DEPLOY-time, not build-time: the 3 DNS records and the 2 Twilio
                                # values. The queue can run to exhaustion without another answer.
                                #
                                # THIS SESSION SHIPPED TWO PRs:
                                #   #44  QA foundation — the real-world harness + the dialog audit
                                #   #45  F20 PPL compliance (migration 0024) — Gate 1 cleared by the
                                #        user, all five answered, Q4 OVERRULING the spec
                                #
                                # THE NEXT PICK reverts to plain file order: F50 (walk-in bookings,
                                # SMC-6), then F22, F24, F25, F27, F28, F35, F44, F47, F49 — all
                                # eligible now — then the wave they unlock (F21, F38, F23, F26, F43,
                                # F46), then F29/F39/F48, then F40, then F45 last.
                                # F20's merge unblocked F21 and F38, which head the remaining depth.
                                #
                                # ⚠ THE ONE THING STILL OWED, and it is now CHEAP because the harness
                                # exists: NOBODY HAS WALKED THE JOURNEYS. docs/real-world-qa.md §3
                                # holds five of them (bride / walk-in / floor / atelier / cross) and
                                # PR #44 proved only BOOT, TENANCY, STATIC SERVING, THE SEED CONTRACT
                                # AND THE STOREFRONT READS. The browser assertions — real <dialog>
                                # focus, the SOS 30s wall-clock escalation, payload-key drift on
                                # POST /storefront/bookings and /storefront/checkin — remain
                                # UNVERIFIED CLAIMS. Run it at the next epic boundary; the recipe is
                                # in the runbook and every command in it was actually executed.
                                # RLS is also unexercised there — that run was as `postgres`.
                                #
                                # WHY THE HARNESS EXISTS AT ALL, so nobody deletes it as redundant:
                                # frontend/e2e/fixtures/manage.ts says in its own header that it
                                # STUBS THE API, so it proves the CONSOLE and not the CONTRACT —
                                # "a backend change that renames a payload key passes every test in
                                # this file while breaking production." The backend suite never opens
                                # a browser. THE TWO HALVES OF THIS PRODUCT HAD ONLY EVER BEEN TESTED
                                # APART. F20 then proved the point within hours: nine e2e tests went
                                # red on a fixture that predated the feature, and the local build
                                # never noticed.
                                #
                                # ---- previous handoff, still accurate on everything else ----
                                #
                                # ==================================================================
                                # ==== HANDOFF, 2026-08-04 — READ THIS FIRST ====
                                # ==================================================================
                                # THE FLOOR-MANAGEMENT PROGRAM IS COMPLETE. All ten features merged,
                                # one PR each:
                                #   F34 #32 · F57 #33 · F33 #36 · F36 #37 · F59 #38 · F41 #39
                                #   F58 #40 · F37 #41 · F60 #42 · F42 #43
                                # 23 of 46 queue entries are `merged`. main's migration head is 0023.
                                # BOTH deployment_gates are CLEARED — nothing merged is un-launchable.
                                # EPIC E7 IS COMPLETE (F36 + F37). E6 is complete except F35.
                                #
                                # THE NEXT PICK, by the loop's own rule (first `queued` entry in FILE
                                # order whose deps are all merged and whose blocker is null), is
                                # **F50** (walk-in bookings, the SMC-6 carveout). After that the
                                # eligible set is F22, F24, F25, F27, F28, F35, F47, F49.
                                #
                                # ⚠ TWO THINGS ARE OWED BEFORE MORE FEATURES, and they are cheap:
                                # (1) THE E7 EPIC-BOUNDARY QA PASS (loop step 9) has NOT been run.
                                #     Full `make e2e` on main, confirm axe is zero-violation, a real
                                #     Chromium click-through of the floor journeys via the Playwright
                                #     MCP tools against `vite preview`, then `/brain-sync`. The floor
                                #     program shipped ten features in two days and NOTHING has yet
                                #     driven the assembled product in a real browser.
                                # (2) THE `known_vacuous` AUDIT (see that block below). jsdom ships no
                                #     <dialog>, so six shipped apps/manage test files that mount a
                                #     Modal may carry focus assertions that CANNOT FAIL. Unaudited.
                                #
                                # THE WIDEST BLOCKER IS UNCHANGED AND IS THE USER'S: F20 is parked at
                                # a legal Gate 1 with five questions, and F21, F29, F38, F39, F40 and
                                # F45 are all unreachable behind it. See user_actions.
                                #
                                # ==== MIGRATION CHAIN — A RULE, NOT A FIXED GRID ====
                                # THE GRID MOVED NINE TIMES IN TWO DAYS, WHICH IS THE WHOLE ARGUMENT.
                                # It said head=0014 at breakfast on 2026-08-03; it is 0023 now, and
                                # not one fixed number this file ever assigned survived contact.
                                # F33 built at 0016 and shipped at 0018; F36 built at 0018 and shipped
                                # at 0019; F41 built at 0019 and shipped at 0020; F37 built at 0021
                                # and shipped at 0022; F42 built at 0022 and shipped at 0023.
                                # Do not read any hardcoded number in this file as current.
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
  # ==== F61 — MERGED. Kept at the top only until the next feature ====
  # ==== starts; move or delete it then.                            ====
  # ==================================================================
  - id: F61
    slug: a11y-walkthrough-fixes
    epic: cross
    title: "The TEN defects the first real-world walkthrough found (nine + one review found)"
    status: merged
    pr: 47
    attempts: 1
    deps: []
    migration: none
    shipped: >-
      SHIPPED as PR #47, merged 2026-08-05. 18 commits, 35 files, +1798/-359. NO
      MIGRATION — alembic heads stayed 0025.
      GATES AT MERGE: lint 0 · pytest not-db 2351 · pytest "db and not s3" 845 against
      real PG16 · vitest 2515 (ui 108, storefront 1097, manage 1310) · build 0 · e2e 155
      with axe ZERO violations · qa-greps 0.

      WHY THESE NEEDED A BROWSER TO FIND, and the reason the walkthrough earns its keep:
      TWO OF THEM ARE INVISIBLE TO BOTH SUITES BY CONSTRUCTION. vitest runs in jsdom,
      where HTMLDialogElementImpl is a nine-line empty subclass and test/setup.ts stubs
      showModal; the Playwright suite intercepts every API call and says so in its own
      header ("it proves the CONSOLE and not the CONTRACT"). So a role="status" that
      never fires and an aria-invalid that lies about corrected input both passed every
      gate this repo had.

      REVIEW FOUND A TENTH, AND IT WAS CREATED BY THE FIX FOR THE FIFTH. The batch
      wrapped the BOOKING flow in a <form> so Enter advances, then wrote a comment
      asserting the check-in form shared the treatment. It did not — CheckinPage.tsx had
      no <form> at all, so Enter and a phone keyboard's Go key stayed dead on THE KIOSK
      SURFACE, the one only ever used on a phone by a woman standing in a doorway. The
      branch had touched those exact onChange handlers for defect #1 and not noticed.
      A comment asserting something false about a sibling file is precisely the
      misdirection the /fake-pay entry was corrected for.

      THREE CLAIMS CORRECTED ON THE RECORD:
      (1) A TEST BASELINE WAS WRONG BY 16x. Review reported ~16.4 s idle runtime behind a
      padded budget. Re-measured three ways: 0.98 s isolated, 1.07 s beside storefront,
      3.87 s under the full gate. Budgets kept — the 150-card board IS the mechanism —
      but the real numbers now sit in all three files and in known_flaky, so a genuine
      regression cannot hide behind a padded ceiling.
      (2) The booking e2e ledger overstated its own mutations: one claimed to red "all
      three steps" reds SLOT ONLY, because per the HTML spec a form with one blocking
      field and no submit button still submits, and the details step has none that block.
      (3) "/privacy has no axe scan" — REFUTED. It ships via AXE_ROUTES and its fixture
      carries a bullet run, so the scan covers real <ul>/<li>.

      TWO OF THE BUILD'S OWN PROOFS WERE VACUOUS AND IT CAUGHT THEM BY RUNNING THE
      MUTATION RATHER THAN READING: a `typed === ""` guard unreachable against a real
      subject (deleting it stayed green), and a list-parity fixture that separated its two
      runs with a BLANK LINE, so a mutation merging every bullet in a block into one list
      PASSED it. Both fixtures rebuilt to measure the boundary the code actually decides.

      A PRE-EXISTING VITEST FLAKE FAMILY was diagnosed and fixed as collateral: ~50% red
      under the concurrent gate, proved to predate these commits by reproducing 4/4 RED on
      a worktree at ea7ddb4. Three causes — focus assertions racing passive effects,
      selectors evaluated before mount, budgets too tight for a contended runner. 6/6
      consecutive green after.
    hazard_seen_2026_08_05: >-
      ⚠ A REVIEWER THAT DIES MID-MUTATION LEAVES SOURCE REVERTED, and this run proved it.
      A session died between reviewer 2's revert and its restore, leaving
      apps/storefront/src/main.tsx with the ErrorBoundary's real i18n keys swapped for
      FABRICATED ones. Committing that would have shipped an error boundary rendering two
      MISSING translation keys — the fallback for a crashed app, itself broken.
      THE RULE THAT FOLLOWS, and it is not "check for a dirty tree": CHECK WHETHER AN
      AGENT IS LIVE (`find <transcript-dir> -name 'agent-*.jsonl' -mmin -5`), THEN check
      the tree. A dirty worktree under a LIVE agent is work in progress and must not be
      touched; a dirty worktree under a DEAD one is a mutation to revert. Confusing the
      two costs either a destroyed agent's work or a shipped fabrication.
    review_findings_all_resolved: >-
      Two reviewers, six + adversarial findings, ZERO blockers, all applied or rejected
      on the record in PR #47. Two rejections worth keeping: the "/privacy has no axe
      scan" claim was REFUTED against the shipped AXE_ROUTES test, and two nits (a
      redundant 405 assertion, a regex duplicated across two files) were declined because
      neither can mislead — both fail red rather than silently green.
      ⚠ THE "~16.4 s IDLE TEST RUNTIME" FIGURE THAT APPEARED IN REVIEW WAS WRONG BY 16x
      and is corrected here so nobody re-derives from it: the real numbers are 0.98 s
      isolated, 1.07 s beside storefront, 3.87 s under the whole gate. They live in the
      three test files and in known_flaky.
    note: >-
      NOT a roadmap feature — a fix batch for defects found by driving the assembled
      product in a real browser, which is why it has no spec or plan. The nine
      `known_product_bugs` it discharged carry `fixed_in: F61` with, for each, the test
      that reds if the fix is reverted. The tenth (/fake-pay) is untouched and still
      open — correctly, it is a LOW backend tidiness item this batch was not scoped for.
      STILL OPEN, recorded rather than smuggled in: FloorPanel.tsx, GuideOverlay.tsx and
      RoomsRegistryDialog.tsx carry the SAME wrong live-region comment that caused defect
      #2. RoomsRegistryDialog is safe BY ACCIDENT (it clears to "" first); the other two
      are unaudited. That is the next sweep.

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
    status: merged
    pr: 40
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
    shipped: >-
      MERGED 2026-08-04 as PR #40, ALL THREE GATING JOBS GREEN ON THE FIRST CI RUN.
      Migration 0021_floor_dispatch (one nullable ALTER TABLE ADD COLUMN). Build ran
      23 agents with zero failures. Gates local on the pushed tree: 1956 backend fast,
      645 backend db ON REAL POSTGRES 16.14, 104 ui / 1017 storefront / 950 manage,
      88 e2e (77 before), axe zero, one alembic head.
      ⚠⚠ THIS FEATURE DISCHARGES BOTH DEPLOYMENT GATES — see `deployment_gates`, now
      cleared. F33's queue tickets have a surface that renders them, a duplicate has a
      remedy, `close` writes `done` so the customer's position page reaches its success
      terminal, and `call` writes `called_at` so F59's wall board highlights.
      THE THING WORTH CARRYING: THE PROOF WAS WRONG TWICE BEFORE THE CODE WAS.
      (1) The spec's original stranding mutation was VACUOUS — a raised 409 already
      rolls back with or without a savepoint, so A8, the single test on which F33's
      deployment gate is discharged, asserted nothing. Review caught it.
      (2) The REBUILT A8 still could not reach the IntegrityError. The shipped
      snapshot-then-nested-commit idiom commits the winner BEFORE the service call, and
      take-next's step 2b refuses that before the INSERT — so the headline mutation came
      back green on the first build too. A8 is now a genuinely-uncommitted-winner
      interleave, the only window 2b cannot see, and the mutation finally bites:
      unmutated -> RoomOccupiedError, ticket stays `waiting`; mutated -> 200,
      ticket `in_service`, assignment.queue_ticket_id NULL. That is a woman dispatched
      to nobody, and it took TWO ROUNDS to build a test that could see it.
      (3) A third vacuity found in passing: an RLS test was measuring the explicit
      tenant_id predicate rather than RLS — swapping the role left all 8 green. The
      docstring now says what it actually pins.
      ALSO SHIPPED: the REUSABLE /manage/** Playwright interception harness. The console
      had NEVER had e2e coverage (the gap F34's spec recorded as Risk 8); every later
      console feature inherits it, and it is built so a later feature adds a stub rather
      than a fork.
      Every focus move was run FIRST-IN-WORKER IN ISOLATION as well as in the full
      suite, per the F41 post-mortem — a full-suite pass can be luck decided by one
      event-loop turn.
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
    status: merged
    pr: 41
    deps: [F31, F36, F57]
    spec: .planning/specs/sos-paging.md
    plan: .planning/plans/sos-paging.md
    started: >-
      2026-08-03 22:30, worktree .worktrees/sos-paging, in PARALLEL with F58.
      Migration resolves from `alembic heads` at rebase; F58 is building with one too.
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
    shipped: >-
      MERGED 2026-08-04 as PR #41, ALL THREE GATING JOBS GREEN ON THE FIRST CI RUN.
      Migration 0022_sos_alerts. Build ran 21 agents with zero failures. Gates on the
      merged tree: 2111 backend fast (main was 1956), 726 backend db ON REAL POSTGRES
      (645), 104 ui / 1017 storefront / 1086 manage (950), 98 e2e (88), one alembic head.
      **THIS COMPLETES EPIC E7** — F36 and F37 are its only two features.
      THE HARD PART WAS NOT THE FEATURE, IT WAS THE MERGE. F58 landed mid-build and both
      features extend the same floor module: 14 CONFLICTED FILES and two migrations both
      claiming revision 0021. A rebase would have replayed 20 commits through those
      conflicts, so it was merged instead (the shape F36 and F58 both used).
      ⚠ THE THING TO CARRY: ONE CONFLICT GIT RESOLVED CLEANLY AND WRONGLY.
      `assert len(live) == 18` — BOTH SIDES HAD WRITTEN 18, so git merged it with no
      marker at all, while the true merged route count is 23. No conflict marker can
      show you that class; only re-deriving the number from the live route table can.
      The same discipline caught the migration rename capturing pre-edit content.
      HOW LOSS WAS RULED OUT rather than assumed: every conflicted test file was counted
      against BOTH parents and lands at exactly `main + HEAD - base`
      (test_floor_api 39, walker 23, FloorPanel 47, RoomsPanel 70, i18n 95), the route
      table was extracted from all three revisions and set-compared (23 = 18 + 18 - 13,
      an exact union), and all ten of the two features' routes were hit through the test
      client. The ROLE WALKER still asserts SET EQUALITY (NON_ELEVATED_REACH 17/17/23)
      and was NOT weakened to make the merge pass — its docstring forbids that.
      F58's e2e harness won outright; F37's vendored copy is gone, no fork.
      ONE FALSE CLAIM THIS REPO HAD CARRIED SINCE F36 IS NOW CORRECTED. `_OccupiedError`'s
      docstring said parenting the conflict base onto DomainValidationError "would make
      the shipped handler answer 400 and leave both 409 handlers unreachable". Mutation:
      EVERY HTTP ASSERTION STAYED GREEN — Starlette takes the first __mro__ match, so a
      handler registered on the concrete class still wins. What the parentage actually
      decides is that a subclass shipped WITHOUT a handler answers a loud 500 rather than
      a quiet, plausible 400. Rule kept, reason rewritten.
      ALSO: two of the plan's mutation claims are unprovable by a db test — tenant_session
      is session.begin(), so a 409 rolls back the very audit row the mutation was meant to
      expose. Both are pinned by the fast suite instead, and the docstrings now say so
      rather than leaving an implied guarantee.
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
    status: merged
    pr: 43
    attempts: 1
    deps: [F41, F57]
    spec: .planning/specs/seamstress-capacity.md
    plan: .planning/plans/seamstress-capacity.md
    started: >-
      2026-08-04 03:15, worktree .worktrees/seamstress-capacity. Eligible once F41 merged.
      SPEC REVIEW: 38 findings from 3 lenses, 36 applied, 2 rejected in writing. Six
      unique blockers, and the first is CONCEPTUAL rather than mechanical — the kind that
      ships looking finished and is worse than useless:
      (1) THE BAR DIVIDED A STOCK BY A RATE. Load was SUM(effort) over EVERY undelivered
      ticket — an unbounded backlog — against ONE WEEK of capacity. It would read
      permanently red in a perfectly healthy shop and green on exactly the Thursday the
      feature exists to warn about. It is now TWO SUMS in one statement: one filtered to a
      due-date horizon (what the bar renders) plus the unfiltered total (the backlog
      reading).
      (2) ForbidExtraModel sets extra="forbid" and NOT strict, so pydantic coerces
      `true` -> 1 and `"30"` -> 30 BEFORE any validator runs — the one-minute-band trap
      the spec claimed to defend was wide open. StrictInt on the band mapping and on
      weekly_capacity_hours.
      (3) The capacity route answered SeamstressRef, whose required assigned_minutes it
      has no source for — and the only obtainable value would have ZEROED the very bar the
      save just updated. It answers its own response shape now.
      (4) The panel's two write controls were never role-gated, so a seamstress tapping
      one lost her whole board.
      (5) Four validation cases demanded 404s that _require_seamstress — the helper the
      design adopts verbatim — can never produce. One indistinguishable 400 with
      byte-identical bodies; the only 404 is the check-to-UPDATE race.
      (6) The bar's markup named a colour token that does not exist and filled from the
      wrong edge in RTL. The console already ships this widget — copy it.
      THE BAR HAS NO ARIA ROLE, deliberately: it is aria-hidden and the TEXT beside it is
      the payload, so a screen reader gets a sentence rather than a percentage and
      overload is never colour-only.
      Recorded conflict worth keeping: "the capacity MATRIX" (Q2's novel pattern) cannot
      exist under the simplified model — a matrix's second dimension is time, which is the
      roster projection the same ruling drops. It ships as a LIST, which also discharges
      the keyboard requirement structurally.
    shipped: >-
      MERGED 2026-08-04 as PR #43, ALL THREE GATING JOBS GREEN ON THE FIRST CI RUN.
      Migration 0023_seamstress_capacity (built at 0022, renumbered when F37 took it).
      Gates on the merged tree: 2235 backend fast, 750 backend db ON REAL POSTGRES,
      104 ui / 1029 storefront / 1242 manage, 126 e2e.
      **THIS COMPLETES THE FLOOR-MANAGEMENT PROGRAM — ALL TEN FEATURES MERGED.**
      THE LOAD IS TWO SUMS AND THAT IS THE FEATURE: coalesce(sum(effort_minutes)
      FILTER (WHERE due_date <= :horizon), 0) for the bar, plus the unfiltered sum for
      the backlog. Dropping the FILTER reddens three tests. UNITS are isolated in
      lib/capacity.ts and the negative half is asserted by grep — no `* 60` or `/ 60`
      anywhere in app/atelier/ or the repository. A mutation replacing the aggregate
      with a Python fold over board()'s tickets returns (500,500) against an asserted
      (520,520) — the exact silent under-count a truncated board would cause.
      MERGE WITH F60: three i18n conflicts. The second was NOT a straight
      concatenation — both sides ended mid-`it` and SHARED the trailing `});\n});`
      that closes whichever block comes last, so a naive union left an unclosed brace
      and the file reported **"Tests no tests"** rather than a failure count. That is
      the silent-death class; resolved and then VERIFIED by counting
      103 (main) + 111 (F42) - 95 (base) = 119, an exact union.
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
    status: merged
    pr: 42
    attempts: 1
    deps: [F34]
    spec: .planning/specs/guide-walkthrough.md
    plan: .planning/plans/guide-walkthrough.md
    started: >-
      2026-08-04 05:10, worktree .worktrees/guide-walkthrough. Last entry of the floor
      program. SPEC REVIEW: 27 findings from 2 lenses, 26 applied, 1 rejected in writing.
      ⚠ THE FINDING THAT REACHES BEYOND THIS FEATURE is recorded in `known_vacuous` above:
      jsdom ships NO <dialog> implementation, so every vitest assertion about dialog focus,
      the trap or Esc measures a stub. F60 routes all nine of its focus criteria to
      Playwright instead; six other shipped test files are unaudited.
      TWO CORRECTIONS TO THIS VERY ENTRY. (a) `deps: [F34]` is WRONG in the way that
      matters — F34 is one of fourteen sections and F60 touches none of its code; the
      binding deps are F37 (the SOS overlay it must yield to) and F33 (the /checkin page).
      (b) "Focus trap and Esc-to-close are the real work here" is FALSE: packages/ui's
      Modal is already a native <dialog> with showModal() and onCancel, used by fifteen
      callers. The real work is the announcement contract and the SOS collision.
      THE SOS COLLISION HAS EXACTLY ONE RESOLUTION and it is worth knowing why: showModal()
      promotes to the TOP LAYER and INERTS the document, so an emergency arriving over an
      open guide would be invisible AND unanswerable — no z-index or portal beats the top
      layer. The guide must CLOSE, edge-triggered on the for_me set GROWING (level-triggered
      would lock it shut forever behind a dismissed live alert).
      TWO BLOCKERS LIVED IN THAT DETECTOR: keying on the FIRST id never fires when an alert
      already exists (the list appends oldest-first, so a new one lands at the END), and
      keying on the BARE id is blind to F37's escalation/stall re-rises, which use the
      composite ${id}:${escalated}:${stalled}. It is a SET DIFFERENCE over that composite.
      NO NEW DEPENDENCY, and the spec argues it positively: a tour library sells a focus
      trap (already shipped), a positioning engine (nothing is anchored) and a step state
      machine (eleven lines of useState).
    shipped: >-
      MERGED 2026-08-04 as PR #42, ALL THREE GATING JOBS GREEN ON THE FIRST CI RUN.
      NO migration (alembic heads unchanged), NO new dependency (the diff over every
      package.json and the lockfile is empty). Gates: 2111 backend fast, 104 ui /
      1029 storefront / 1108 manage, 113 e2e (98 before).
      ALL NINE FOCUS CRITERIA ARE PLAYWRIGHT TESTS, NOT VITEST — see `known_vacuous`.
      THREE SPECIFICATION ERRORS THE BUILD CAUGHT, all worth knowing:
      (1) The announcement effect as specified was BROKEN. Keyed on [index] with a
      skip-ref armed in onClick, the first open already has index 0, so the effect never
      runs, the ref stays armed, and it SWALLOWS THE FIRST «הבא» — step 2 is never
      announced. Built as [index, open] with the open-guard before the ref check.
      (2) A step key present in GUIDE_STEPS but MISSING from he.ts had nothing to catch
      it — the plan's mutation pointed at a test that reads the TABLE, not the bundle, so
      a typo'd key would render a raw key into a Hebrew dialog with every guard green.
      A new test walks the table through i18n.t.
      (3) The storefront value-parity test was VACUOUS as specified:
      resolve(key, ar) === resolve(key, he) passes when NEITHER bundle has the key
      (undefined === undefined). It went green against empty bundles until a
      `typeof === "string"` leg was added.
      Thirteen mutation checks were run, each observed red then restored.
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
    status: merged          # WALK-IN HALF ONLY — the remote half is still open, see `still_open`
    pr: 46
    attempts: 1
    deps: [F15, F34]
    spec: .planning/specs/walk-in-bookings.md
    plan: .planning/plans/walk-in-bookings.md
    still_open: >-
      THE REMOTE/SCHEDULED OWNER-CREATE HALF. It needs the manage link, consent capture
      and a terms answer — none of which the walk-in half required, because a walk-in
      mints no token. Re-queue it as its own entry when E3 is revisited. F15's Risk 1
      (a mis-tapped terminal cancel) is RE-POINTED at that half, not closed by this one:
      a walk-in stamped at `now` cannot restore next Tuesday's appointment. What this
      half does remedy is the mis-tap discovered AT THE DOOR.
    shipped: >-
      SHIPPED as PR #46, merged 2026-08-04. Migration 0025. 6 commits.
      GATES AT MERGE: lint exit 0 · 2346 fast · 845 db against real PG16 · 2496 frontend
      (manage 1304, storefront 1088, ui 104) · 150 e2e · alembic heads = 0025, one head.

      THE BRIEF WAS WRONG ABOUT THE CODE IN FIVE PLACES and two were load-bearing:
      (1) `bookings.source` DID NOT EXIST — no migration added it. F50 builds it, and it
      earns its place as the terms CHECK's discriminator rather than as a label.
      (2) "a DB CHECK keeps storefront rows non-null" IS INVERTED. 0008_bookings.py has
      plain NOT NULLs and NO such CHECK. So this feature had to BUILD the constraint that
      makes dropping those NOT NULLs safe — building on the brief's assumption would have
      made terms evidence optional FOR EVERYONE, not just walk-ins.
      Also: the "no link is minted" discharge was under-argued (two shipped writers mint
      tokens on rows that have none; the real discharges are that a `customers` row
      REQUIRES an OTP, and that starts_at = now puts the row outside both predicates).

      TWO RULINGS THE SPEC HAD TO MAKE, both recorded rather than defaulted:
      MARKETING CONSENT IS **NO FIELD AT ALL**, not `false`. The 0024 CHECK admits only
      'booking_form', and MarketingConsentSource's docstring already refuses F33's
      STRONGER case as laundering. Shipping `false` days after F20 would have been a §30A
      violation committed by the feature built to prevent exactly that.
      NO §11 COLLECTION POINT: the body is two UUIDs, so nothing is obtained from the
      subject. That dissolved the notice question, meant no new public Hebrew, and is why
      Gate 1 self-approved with no in_run_gate opened.

      THE HAZARD THAT WAS NOT IN F50's OWN CODE: dropping the two terms NOT NULLs broke
      six readers, TWO of them a LIVE 500 on F20's §13 subject-export route merged the
      same morning. Migration + both reader fixes shipped in ONE commit.

      PROOFS RUN, NOT ASSERTED. R-1 is the one that mattered: the terms-evidence CHECK and
      its inverse are behaviourally identical on every value that exists today, so ONE
      test had to discriminate. Inverting the constraint reds it ALONE while the
      four-corner, source-check, positive-version and droppable tests stay green. The
      refusing downgrade() was proved by adding a DELETE to it and watching red. The §30A
      test seeds a REAL consent and asserts byte-identity PLUS an unchanged updated_at, so
      the trigger itself testifies no customers UPDATE was issued — against a NULL-consent
      customer the same assertion would have been NULL-to-NULL and vacuous.

      A DEFECT THE PLAN DID NOT ANTICIPATE, worth remembering: a refusing downgrade() plus
      a session-scoped shared `migrated_db` is a collision — ONE surviving walk-in row
      made ALL EIGHTEEN round-trip tests fail, in modules that never heard of F50, with a
      NotNullViolationError naming a column their feature does not own. Fixed with a
      module-scoped sweep, verbatim the trap F57 documented one table over. The migration
      was NOT softened.

      REVIEW: 11 applied, 8 rejected with recorded reasons. The best applied finding CLOSED
      A RISK THE SPEC HAD ACCEPTED — the backfill feed could mint a manage_token_hash on a
      walk-in, which is the exact danger this carve-out exists to avoid. One line on the
      feed closed it. §13 export also gained `source`, so the Privacy Protection Authority
      is not handed the ambiguity F50 created.
      R-8 IS A CLAIM THIS BUILD MADE AND WITHDREW: it wrote in a test comment that an F16
      test was vacuous, then found its probe had mutated the FIRST OF TWO
      `starts_at > after` occurrences, in a different method. The seeded row added on that
      false premise was removed with it. R-7 records that the vacuity hunt found NOTHING,
      so a zero-finding result is never read as a skipped review.
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
    status: merged
    pr: 45
    attempts: 1
    deps: [F13]
    spec_gate: user            # DISCHARGED 2026-08-04 — kept as the record of what it was
    blocker: null              # was: Gate 1, 5 questions, parked from 2026-07-30
    spec: .planning/specs/ppl-compliance.md
    plan: .planning/plans/ppl-compliance.md
    copy: .planning/design/screens/privacy/copy.md
    shipped: >-
      SHIPPED as PR #45, merged 2026-08-04. Migration 0024. 24 commits, 96 files,
      +12042/-72. ALL THREE GATING JOBS GREEN ON THE FIRST CI RUN — bought, not lucky:
      the db-marked tests were run locally against a throwaway PG16 on :55432 before the
      push (819 passed), which is the F34 discipline.
      GATES AT MERGE: lint exit 0 (mypy app tests scripts, 302 files) · 2334 fast ·
      819 db · 2461 frontend (ui 104, storefront 1088, manage 1269) · 143 e2e ·
      `alembic heads` = 0024, exactly one head.

      THE PLANNING PASS PAID FOR ITSELF THREE TIMES, and all three would have failed the
      build outright. The spec was 5 days and NINE MERGED FEATURES old; re-verifying every
      citation found 16 drifts.
      (1) THE SUB-PROCESSOR LIST WAS ABOUT TO BE FALSE IN A STATUTORY DISCLOSURE. The spec
      says twice, in bold, "no SMS provider yet — must not name Twilio as live". STALE:
      F54 shipped app/notifications/twilio.py after it was written. Named CONDITIONALLY
      now, under a disclosure principle stated once and applied uniformly — the first
      draft had applied three different standards to three processors, which a reviewing
      lawyer finds in one pass.
      (2) A LIVE PROMISE F20 WAS ABOUT TO BREAK. he.ts:483 (shipped) tells a woman who
      ticks the box that her details are kept UNTIL SHE ASKS TO REMOVE THE CONSENT. The
      retention job would have destroyed them in 7 days, and she could not have withdrawn
      anyway — marketing-withdraw keyed on customer_id and F33 never writes `customers`.
      Fixed by BUILDING the revocation half (a phone arm) and striking the false clause.
      (3) PHASE F WOULD NOT HAVE TYPECHECKED. SectionKey is a compile-time gate; adding
      `privacy` forces a non-empty GUIDE_STEPS.privacy tuple in BOTH i18n bundles.

      REVIEW: three lenses. TWO INDEPENDENT REVIEWERS CONVERGED ON THE SAME DEFECT, which
      is the strongest signal this setup produces. §14 ERASE NEVER TOUCHED queue_tickets.
      The transaction covered customers, bookings, message_log, otp_codes,
      scheduled_messages. A walk-in row holds `name` and `phone`, both nullable=False,
      the phone normalised to E.164 SPECIFICALLY SO IT MATCHES customers.phone EXACTLY —
      the model's own comment states the equality that makes re-identification trivial.
      A bride who booked online AND checked in by QR got a 200, an erased_at stamp, and
      her real name and mobile left in place PERMANENTLY, because the only thing that
      would ever scrub them is the retention policy and retention_enabled ships False
      (Q2). It made the shipped Hebrew FALSE. export_subject was incomplete for the same
      woman. 12 findings applied in one round, 2 rejected with recorded reasons.
      THE REJECTION WORTH REMEMBERING: a proposed UI for the walk-in phone arm would have
      put the control on an owner-only panel and left the SHIFT MANAGER — the role Q4
      exists for, and the one the finding's own scenario names on the telephone — exactly
      as stuck, while LOOKING fixed.

      PROOFS: 15 mutants in Phase C alone, all red, including `dependencies=OWNER_ONLY`
      added to marketing-withdraw (reds four tests — the Q4 positive-absence assertion
      genuinely bites). FOUR VACUOUS TESTS FOUND AND FIXED OR DELETED: a booking-page
      LIMIT test a Python slice satisfied (now captures emitted SQL via a
      before_cursor_execute listener); resolve_privacy({}) green across the whole suite;
      a PrivacyPage assertion a no-op substituteBoutique could not redden; and one
      deleted outright for having no unique mutation.
      NINE E2E TESTS WERE RED AND THE LOCAL BUILD NEVER NOTICED — the Playwright boutique
      fixture predates F20 and sent none of the three now-required documents, so
      undefined.split gave a blank page with no <h1>. Fixed the FIXTURE, not the
      component: the field is non-optional on the wire type, so a guard in BookPage would
      be dead code that also hid the next drift. The reason it got that far is that plan
      §5 named three required E2E properties and NONE had been built.
      A GATES AGENT CAUGHT ITSELF: one mutation failed tsc, so Playwright ran the stale
      dist and "passed". It discarded that result rather than banking it.
    gate_1_cleared: >-
      2026-08-04. ALL FIVE Gate 1 questions answered by the user; the resolutions
      table is in the spec under "Gate 1 — resolutions" and the spec's status is
      now APPROVED — build.
        Q1 Hebrew copy  → CLAUDE DRAFTS, user approves copy.md before the PR merges.
                          It is a BUILD TASK (authored first), not a precondition to
                          starting. Does NOT discharge the standing counsel review.
        Q2 retention_enabled → ships False. Two amber checklist rows (40, 42)
                          accepted over a green flag on an unattended irreversible
                          delete with no backup. D9-revised stands.
        Q3 DPA override → NARROW. Sub-processor list stays platform-owned. D14 stands.
        Q4 marketing-withdraw → ⚠ OVERRULES THE SPEC. Ships (OWNER, SHIFT_MANAGER),
                          not owner-only. The spec is AMENDED in four places (API
                          table, D15 paragraph, D15 decision log, both test sections).
                          The route carries NO route-level require_role and is the ONE
                          privacy route absent from OWNER_ONLY — asserted POSITIVELY,
                          because a default-deny walker cannot tell a deliberate
                          omission from a forgotten one and a later author adding it
                          back would silently revoke a permission the user granted.
        Q5 retention periods → as specified, with the digit-drop floors. Still flagged
                          for counsel at the F21 audit; they live in Settings, so
                          counsel changing one is one env var for all tenants.
    why_this_is_the_pick: >-
      BUILD F20 FIRST, overriding the loop's file-order rule (which would pick F50).
      F20 heads the ONLY 4-deep chain left in the queue — F20 → F38 → F39 → F40 — and
      additionally gates F21, F29 and F45: seven entries in all. Every other eligible
      entry is a leaf or near-leaf, so taking F20 first makes the critical path 4
      features instead of 5+. Its spec was already written AND adversarially reviewed
      (25 findings, 24 applied); only the gate was open, and it is now closed. After
      F20 merges, revert to plain file order.
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
    status: specing
    attempts: 1
    started: "2026-08-05 — the loop's own file-order pick; deps F15/F16/F20 all merged, no blocker."
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
  # ==== ALL CLEAR as of 2026-08-04 — F58 merged (PR #40). ====
  # Both entries below are DISCHARGED and kept as the record of what the gate meant and
  # what discharged it. Nothing on main is currently gated.
  - feature: F33
    gate: "merged but NOT enabled for a live pilot tenant"
    cleared_by: F58
    status: CLEARED 2026-08-04 by PR #40
    why: >-
      Ruling 4, qr-walkin-queue.md. F33 wrote queue tickets that NO SHIPPED SURFACE
      RENDERED; a duplicate ticket is a normal outcome under Ruling 3 and nothing could
      merge or remove one; and the position page's success terminal was unreachable
      because nothing wrote `done` or `removed`. F58's waitlist panel renders the queue,
      `remove` remedies a duplicate, and `close` writes `done`.
  - feature: F59
    gate: "merged, but the TV does not go on a wall"
    cleared_by: F58
    status: CLEARED 2026-08-04 by PR #40
    why: >-
      With no writer for `called_at` or the status column, nothing was ever highlighted,
      the board only grew, and because the order is arrival order and the cap is five
      rows THE FIVE NAMES FROZE mid-morning — a woman who arrived at 09:00 and left at
      10:00 was still on a public screen at 17:00, which is not «לצורך ניהול התור בלבד».
      F58's `call` writes `called_at` and `close`/`remove` retire rows, so the board
      moves and the privacy argument is answered.
      STILL TRUE and NOT a gate: the kiosk must run ONE full-screen tab with
      screen-blanking disabled — the poll stops on `document.hidden` by design, which is
      right for a phone and wrong for a wall.

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
  # CLEARED 2026-08-04 — all five answered. Kept as the record; see the F20 queue
  # entry's `gate_1_cleared` field for the rulings. ONE ASK SURVIVES, and it is a
  # REVIEW rather than a block: the user approves the drafted Hebrew copy.md before
  # F20's PR merges. F20 builds now.
  # ==== F20's LAST ASK IS DISCHARGED 2026-08-04 — copy APPROVED, PR #45 merged ====
  - id: F20
    what: "APPROVE the drafted Hebrew copy at .planning/design/screens/privacy/copy.md"
    asks: 0
    status: DISCHARGED 2026-08-04 — user approved as drafted; PR #45 merged
    still_open: >-
      NOT the counsel review. That stays in `user_actions` and must happen before pilot
      go-live. What makes it cheap is structural rather than lucky: the text lives in
      `tenants.settings`, so counsel's version is ONE settings field per tenant, or one
      constant for every tenant that has not overridden. The sub-processor list is
      platform-owned (Q3), so amending IT reaches every tenant including the overriders.
    sharpest: >-
      Ten strings went in front of members of the public in Hebrew. The two that carried
      the most judgement: the §30A revocation sentence encodes Q4 as «אפשר לבקש מאיתנו»
      / «אפשר לומר זאת לכל אחת מאיתנו» — the BOUTIQUE, never «the owner», because a bride
      in a shop cannot tell which woman behind the counter that is; and the Twilio bullet
      is CONDITIONAL, because `sms_provider` ships unset and staging runs `fake`, so an
      unconditional claim would be false on the deployment we actually run while omitting
      it entirely would be the worse error.
  # F33's own notice question is DISCHARGED TOO, by the same approval: F20 replaced the
  # interim string at he.ts:483 with the counsel-shaped text (commit 1a5a091, "the
  # counsel swap on the walk-in notice, in both bundles"). See the F33 entry below —
  # its interim sentence is no longer shipped.
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

known_vacuous:                  # tests that CANNOT fail, found 2026-08-04. Not flaky — blind.
  # ==================================================================
  # ==== AUDITED AND CLOSED 2026-08-04 by PR #44. ====================
  # ==================================================================
  # THE MECHANISM BELOW IS CORRECT AND CONFIRMED — jsdom 29.1.1's
  # HTMLDialogElementImpl is a NINE-LINE EMPTY SUBCLASS (read from
  # node_modules, not inferred), so every setup.ts passes its install
  # guard and the stub is live.
  #
  # THE BLAST RADIUS BELOW WAS WRONG, AND WRONG IN THE EXPENSIVE
  # DIRECTION — it invited deleting sound coverage. Five of the six
  # named files are DISCIPLINED. The decisive mechanic the note missed:
  # `fireEvent.click` does not move focus in jsdom and `render` focuses
  # nothing, so activeElement is <body> for a whole click-driven flow.
  # An assertion that a node HAS focus after a close can then only pass
  # if the component ran an explicit .focus() — THAT IS REAL COVERAGE.
  # Vacuity requires the test to PRE-PLACE focus on its own assertion
  # target (`trigger.focus()` -> open -> close -> expect(trigger)),
  # because the stub never takes it away.
  #
  # EXACTLY FOUR ASSERTIONS MATCHED, all one copied template:
  #   RoomsRegistryDialog.test.tsx  x2   (in the stated radius)
  #   RoomDressDialog.test.tsx      x1   (NOT in it — audit found it)
  #   RoomHandoverDialog.test.tsx   x1   (NOT in it — audit found it)
  # The last two carried a comment asserting "jsdom implements the
  # <dialog> close focusing steps". FALSE, and worse than no comment:
  # it made an unfailable test read as a deliberately-weak one.
  #
  # THE REAL HOLE WAS A GAP, NOT BAD TESTS. Nothing anywhere asserted
  # that focus ENTERS a dialog, that Tab is trapped, or that a real
  # Escape dismisses it — none of it expressible under the stub. Closed
  # by frontend/e2e/dialog-focus.spec.ts: 4 rules x 2 dialogs, each RUN
  # against the mutation that removes what it measures. M1 (the stub,
  # reproduced in Chromium) reds SEVEN OF EIGHT, which is the argument
  # for the file in one number.
  #
  # STOREFRONT HAS NO DIALOG AT ALL — no Modal import, no <dialog> in
  # any component. Its setup.ts stub is dead code and its comment
  # ("the @boutique/ui Modal behind the booking CTA") is stale.
  # packages/ui's own Modal.test.tsx has no focus/trap/Esc assertion
  # whatsoever and is correctly scoped.
  #
  # STANDING RULE, unchanged and now proven: assert dialog focus, traps
  # and Esc in PLAYWRIGHT, never vitest. But do NOT call a unit
  # assertion vacuous without checking whether it PRE-PLACED focus —
  # over-claiming vacuity deletes working tests.
  - what: "every vitest assertion about <dialog> focus, the focus TRAP, or Esc-to-close"
    found_by: F60's spec review
    evidence: >-
      jsdom ships NO <dialog> implementation — HTMLDialogElement-impl.js is an empty
      subclass — so BOTH `frontend/apps/{manage,storefront}/src/test/setup.ts` stub
      `showModal` as `this.open = true`. That stub performs NO focus move, installs NO
      trap and fires NO `cancel` event. Any unit test asserting those things is therefore
      measuring the stub, not the platform, and would pass with the component's focus code
      deleted entirely.
    blast_radius: >-
      Six shipped manage test files mount a Modal: BookingDetail, AtelierSection,
      SosRaiseDialog, SosOverlay, RoomsRegistryDialog, StaffSection. Their NON-dialog
      focus assertions are fine; the dialog ones are not. This has NOT been audited
      feature by feature — F60 discovered it and routed its own nine focus criteria to
      e2e instead, which is the correct remedy.
    why_it_matters: >-
      a11y here is a LEGAL requirement (IS 5568 / WCAG 2.0 AA) and axe cannot see a focus
      move that never happened. This repo has shipped a focus-drops-to-<body> defect FIVE
      times; a whole class of test that CANNOT catch the sixth is worse than no test,
      because it reads as coverage.
    how_to_apply: >-
      Assert dialog focus, traps and Esc in PLAYWRIGHT, never vitest. A named e2e test per
      rule, each with the deletion that reddens it. If a unit test must touch a dialog,
      restrict it to content and callbacks.
    owner: CLOSED 2026-08-04 by PR #44 — see the block above for what the audit changed

known_product_bugs:             # real defects found but deliberately not fixed in the PR that found them
  - what: "/fake-pay answers 200 with a blank storefront shell when PAYMENT_PROVIDER is unset"
    found_by: PR #44's harness verification, driving the real stack
    evidence: >-
      `/fake-pay` is not in EXEMPT_PATHS and `fake-pay` is not a reserved first segment,
      so `_SpaFallbackRoute` claims the path and returns the storefront HTML shell with a
      200. With PAYMENT_PROVIDER=fake and an unknown session it is a clean 404
      (FakePayService.facts raises DomainNotFoundError) — so the two configurations differ
      in the one direction that matters and the WRONG one is silent.
    why_it_matters: >-
      ⚠ CORRECTED 2026-08-04 — THIS ENTRY OVERSTATED THE HARM AND THE OVERSTATEMENT WAS
      ITSELF THE DEFECT. It claimed a misconfigured deposit deployment "redirects the
      bride to a URL that answers 200 with a blank page… she just sees nothing and the
      booking never completes." THE WALKTHROUGH'S VERIFIER PROVED THAT STATE UNREACHABLE:
        payments/service.py  is_connected() -> False on GatewayNotConfigured/SecretBoxNotConfigured
        booking/service.py   deposit_due() REQUIRES gateway_connected
        booking/router.py    deposit_due false -> payment_session_id null -> routes to /book/confirm
        payments/fake_pay.py register_fake_pay() returns early unless provider == "fake"
      THE SAME MISSING CONFIG THAT UNREGISTERS /fake-pay ALSO MAKES deposit_due FALSE,
      and deposit_due is the only thing that ever produces the redirect. No bride can be
      sent to an unregistered /fake-pay. Under `lemonsqueezy` the redirect is the
      provider's absolute URL, so that path does not reach it either.
      WHAT IS ACTUALLY TRUE is smaller and more general: `_SpaFallbackRoute` declines only
      EXEMPT_PATHS and the two reserved first segments, so ANY unregistered path answers
      200 with the storefront shell. `/favicon.ico` is the live example — main.py's own
      comment predicts it ("an unlisted file falls to the catch-all and returns the HTML
      shell with a 200, which nosniff then makes the browser refuse. Silently dead.").
      THE LESSON WORTH MORE THAN THE BUG: an overstated known-bug entry misdirects
      whoever picks it up. Severity claims in this file are load-bearing — a future
      reader budgets by them. Write what you proved, not what you feared.
    fix: >-
      add the fake-pay path to `_SpaFallbackRoute`'s decline set (tidiness, LOW — not a
      bride-facing outage), and ship a real `favicon.ico` in `apps/storefront/public/`.
    owner: unassigned — LOW; pick up with any E4/E5 payments feature

  # ==== FOUND 2026-08-04 BY THE FIRST REAL-WORLD WALKTHROUGH (8 agents, 5 journeys, ====
  # ==== real Chromium against real FastAPI + real Postgres). Every one below was     ====
  # ==== REPRODUCED by an adversarial verifier whose default verdict was REFUTED.     ====
  # ==== It confirmed 6 of 9 claims, INVERTED one (the /fake-pay entry above) and     ====
  # ==== DOWNGRADED a journey agent's FAIL to a documented decision.                  ====
  # ==== THE PATTERN: BOTH TOP DEFECTS ARE THINGS NEITHER SUITE CAN SEE — a           ====
  # ==== role="status" that never fires and an aria-invalid that lies. Invisible to   ====
  # ==== vitest (jsdom) and to the intercepted Playwright suite alike.                ====
  #
  # ==== ✅ ALL NINE ARE FIXED IN F61 (2026-08-05). DO NOT RE-PICK THEM. =============
  # Each carries `fixed_in: F61` with the test that reds if the fix is reverted; every
  # one of those mutations was run, not merely named. They are kept rather than deleted
  # because the ENTRY is the record of what the walkthrough could see that the gates
  # could not — that is the reusable part, and deleting it loses it.
  #
  # THREE THINGS F61 LEARNED THAT ARE WORTH MORE THAN THE NINE FIXES:
  #   1. `role="status"` is not enough. React SKIPS the DOM text write when a live
  #      region re-renders to the same string, so a cue that repeats verbatim is
  #      SILENT. Two comments in this repo asserted the opposite. The nonce+key on
  #      `AtelierSection`'s cue is the fix; `FloorPanel.tsx:270`, `GuideOverlay.tsx:49`
  #      and `RoomsRegistryDialog.tsx:160` still carry the wrong belief and are the
  #      obvious next sweep — RoomsRegistryDialog happens to be safe by accident,
  #      because it clears to "" before every write.
  #   2. A padded test budget is not free. Three budgets went to 60s here; the number
  #      that justified two of them was WRONG BY 16× and nobody checked. See
  #      `known_flaky` for the re-measured baselines.
  #   3. A comment that misdescribes a SIBLING file is the same defect class as the
  #      /fake-pay overstatement above. Review round 1 caught one on this branch.
  - what: "/checkin pins its validation errors after the user corrects them"
    fixed_in: F61 — clearError() on all three onChange; CheckinPage.test.tsx reds on removing any one
    severity: MEDIUM · a11y · NEVER-WORKED
    where: "frontend/apps/storefront/src/routes/CheckinPage.tsx (name/phone/visitType onChange)"
    evidence: >-
      Submit empty -> 3 role="alert" + aria-invalid="true". Fill every field with VALID
      data and all three persist unchanged until the next submit. onChange only calls
      setName(...); fieldErrors is rewritten ONLY inside forward(), i.e. on submit.
      A screen reader announces the field as invalid while it holds correct input.
    why_it_matters: >-
      THE CORRECT PATTERN ALREADY EXISTS FOUR FILES OVER. BookPage.tsx defines
      clearError() and wires it on the SAME Input component with the SAME
      error={fieldErrors.name} prop. The booking flow clears; check-in does not. This is
      drift between two surfaces that should share one behaviour, not a missing idea.
    fix: "call clearError('name'|'phone'|'visitType') in the three onChange handlers"
  - what: "editing an atelier ticket is the only mutation that announces nothing"
    fixed_in: >-
      F61 — setCue lifted out of the create branch, atelier.cue.updated added to he.ts + ar.ts,
      AND a nonce keying the span inside the region so a REPEATED edit of one bride (whose text
      is byte-identical) still mutates it. Two AtelierSection.test.tsx tests, four mutations run.
    severity: MEDIUM · a11y · NEVER-WORKED
    where: "frontend/apps/manage/src/components/AtelierSection.tsx — setCue is inside `if (form.mode === 'create')`"
    evidence: >-
      A MutationObserver installed BEFORE the action (defeating the auto-dismiss race)
      logged ZERO entries on a successful 200 update. Structural confirmation: he.ts has
      atelier.cue.created/advanced/undone/assigned/released/deleted/capacity.saved/
      capacity.cleared/settings.saved and NO atelier.cue.updated — the string was never
      written. A sighted user sees the dialog close; a screen-reader user gets silence
      indistinguishable from a failed save.
    fix: "add atelier.cue.updated to he.ts + ar.ts and lift setCue out of the create branch"
  - what: "the erase confirmation rejects the phone format its own lookup just accepted"
    fixed_in: F61 — phoneKey() normalises both sides; PrivacySection.test.tsx reds on restoring the exact compare
    severity: MEDIUM · destructive-action UX
    where: "frontend/apps/manage/src/components/PrivacySection.tsx — exact compare against stored E.164"
    evidence: >-
      Look a customer up with 0501234599 (the field's own help says to). The
      type-to-confirm then demands +972501234599 and refuses with «המספר שהוקלד אינו
      תואם» — "the number you typed doesn't match".
    why_it_matters: >-
      On an IRREVERSIBLE privacy action, an error reading "doesn't match" invites the
      operator to conclude SHE HAS THE WRONG WOMAN, when the record is right and only the
      normalisation differs. The next move after that conclusion is to go looking for a
      different customer to erase.
    fix: "compare normalised digits, or say +972… in the label"
  - what: "every staff-row button is nameless"
    fixed_in: F61 — aria-label="{action} — {name}"; StaffSection.test.tsx asserts the names are UNIQUE, not merely present
    severity: MEDIUM · a11y
    where: "frontend/apps/manage/src/components/StaffSection.tsx row buttons"
    evidence: >-
      aria-label, aria-labelledby and aria-describedby are ALL null on both row buttons.
      With 7 rows on screen that is seven identical «עריכה» and six identical «השבתה» in
      one list — AND ONE OF THEM DEACTIVATES A COLLEAGUE'S ACCESS.
    why_it_matters: >-
      It breaks the console's OWN convention: the floor, waitlist and atelier panels all
      render «{action} — {name}», and the runbook cites that as the rule.
    fix: "aria-label={`${action} — ${name}`}, matching the floor panels"
  - what: "the booking flow is not a <form>; Enter in a text field does nothing"
    fixed_in: >-
      F61 — ForwardForm on all three booking steps AND on /checkin, which the first pass missed;
      structure in vitest, the keypress in Playwright (jsdom has no implicit submission).
    severity: MEDIUM · UX
    where: "frontend/apps/storefront/src/routes/BookPage.tsx — document.querySelector('form') is null"
    evidence: >-
      Typed a valid name on /book/details and pressed Enter: no navigation, no error, no
      role=alert, no console output. `{hasForm:false, continueBtn:{type:'button',
      insideForm:false}}`.
    why_it_matters: >-
      On a phone the virtual keyboard's Go/↵ key is dead on the last field, and the user
      must Tab past the notes textarea AND the marketing checkbox to reach «המשך».
    fix: "one <form onSubmit> wrapper plus type=submit"
  - what: "unrouted paths escape the platform error envelope"
    fixed_in: F61 — @app.exception_handler(404); a 405 guard test stops it widening to StarletteHTTPException
    severity: LOW-MEDIUM
    where: "backend/app/main.py — no 404 exception handler"
    evidence: "/manage/nope and /storefront/nope answer {\"detail\":\"Not Found\"}; every HANDLED error is {\"error\":{code,message}}"
    why_it_matters: >-
      FRONTEND.md mandates reading response.data.error.message, which is undefined here,
      so every stale-URL 404 reaches the user as the generic fallback string.
    fix: "one @app.exception_handler(404) emitting the envelope"
  - what: "the logout button is 29x21 px"
    fixed_in: F61 — min-h-11 px-2; guide.spec.ts MEASURES boundingBox in Chromium, the only instrument that can
    severity: LOW · a11y
    where: "frontend/apps/manage — «יציאה»"
    evidence: "measured 29 x 21; fails even WCAG 2.5.8 AA (24 x 24). Every other console control is 44 px high."
    fix: "size it like its siblings"
  - what: "neither SPA has a React error boundary"
    fixed_in: >-
      F61 — one boundary per app root. NOTE the scope, because the entry below overstates it: a ROOT
      boundary replaces the SOS overlay along with everything else. It buys a sentence and a reload,
      NOT a surviving emergency channel. That would need a second boundary around the overlay.
    severity: MEDIUM-LOW
    where: "grep -rn 'ErrorBoundary|componentDidCatch|getDerivedStateFromError' apps packages -> 0 source hits"
    evidence: >-
      NOT reproduced in a browser — the verifier read the code and REFUSED to dress that
      up as a repro, because forcing a render throw meant modifying a stack four other
      agents had just used. Recorded with the caveat intact.
    why_it_matters: >-
      React 19 unmounts the whole tree on an uncaught render error: a blank page with no
      recovery affordance. On the manage console THAT PAGE IS ALSO THE SOS EMERGENCY
      CHANNEL.
    fix: "one boundary per app root rendering the existing outage copy + a reload control"
  - what: "the privacy documents render 17 bulleted lines with no list semantics"
    fixed_in: >-
      F61 — PrivacyProse parses bullet runs into <ul>/<li> at the RENDERER; backend/app/privacy/
      is untouched, so the byte cap and the no-HTML invariant both still hold.
    severity: LOW-MEDIUM · a11y · WCAG 1.3.1 (A)
    where: "/privacy and the §11 details notice — `•` inside <p class='whitespace-pre-line'>, zero <ul>/<ol>/<li>"
    why_it_matters: >-
      axe passes it and cannot do otherwise — axe cannot know text beginning with «•» was
      MEANT to be a list. A screen-reader user gets one undifferentiated paragraph where a
      sighted user gets an enumerated set of rights and recipients, on the page whose
      entire purpose is communicating exactly those. This is a legal surface here.
    fix: >-
      render the bullet runs as real <ul>/<li> at the component, NOT by putting markup in
      the settings text — PLATFORM_NOTICE_HE is byte-capped, no-HTML by invariant, and
      boutique-overridable, so the parsing belongs in the renderer.

remaining_work_estimate:        # synced 2026-08-05. Anchored on THIS session's measured wall-clock, not on feel.
  remaining_features: 20
  critical_path_depth: 3        # waves, not features — eleven of twenty have no unmet dep
  waves:
    wave_1_buildable_now: [F21, F22, F24, F25, F27, F28, F35, F38, F44, F47, F49]
    wave_2: [F23, F26, F29, F39, F43, F46]
    wave_3: [F40, F45, F48]
  measured_this_session: >-
    These are wall-clock numbers from the 2026-08-04/05 run, which is the only honest
    basis available. Each figure is spec/plan + build + gates + review + fix + CI + merge.
      QA foundation (PR #44, 8 agents)      ~46 min
      F20 plan (5 agents)                   ~55 min
      F20 build (10 agents)                 ~3.1 h   -> F20 total ~4.5 h  (Effort L)
      F50 spec+plan (3 agents)              ~37 min
      F50 build (7 agents)                  ~1.7 h   -> F50 total ~2.6 h  (medium)
      real-world walkthrough (8 agents)     ~2.2 h
    So: a MEDIUM feature is ~2.5-3 h end to end. A LARGE one is ~4.5-5 h.
  sizing:
    large_4_5h: [F21, F24, F25, F38, F40, F43, F45, F46, F48]      # 9 — new surfaces, external integrations, or money
    medium_2_5_3h: [F22, F23, F26, F27, F28, F29, F35, F39, F44, F47, F49]  # 11
  estimate:
    features_only: "~71 h  (9 x 4.5 + 11 x 2.75)"
    plus_epic_boundary_qa: "~12 h  (E4 E5 E6 E8 E9 E10, ~2 h each — the walkthrough is the template and it now exists)"
    plus_ci_fix_rounds: "~2 h  (historically ~1 feature in 5 needs one round)"
    total_sequential: "~85 h  ≈ 11 working days, one feature at a time"
    with_parallel_sessions: >-
      ~4-5 DAYS. The empirical anchor is the floor program: TEN features in TWO days
      across 3-4 concurrent sessions. Wave 1 has ELEVEN independent features, so that
      parallelism is available immediately rather than theoretically.
  what_would_blow_the_estimate:
    - "F45 (Arabic + comms templates, go-live) needs a HUMAN ARABIC REVIEWER for legal/policy copy — a user_action, not a build task. It is wave 3, so it does not block anything."
    - "F46 (WhatsApp) waits on META BUSINESS VERIFICATION, which the user ruled is the LAST step. Multi-week clock, deliberately not overlapped. F48 deps on F46, so both slip together."
    - "F29 and F48 each stop at a Gate 1 money question. Budget a round trip."
    - "G2 (the payment leg has no browser coverage) is not in the 85 h. Closing it needs console setup plus fake gateway credentials — call it half a day, and do it before the pilot rather than after."
  not_in_the_estimate:
    - "The nine known_product_bugs. F61 (this session) is taking them as one batch."
    - "brain-sync: .brain reports ~70 stale pages and ~640 missing. Reconcile with /brain-sync at an epic boundary, never mid-feature."

walkthrough_coverage_gaps:      # what the 2026-08-04 run did NOT prove. Silence here reads as coverage.
  - id: G1
    what: "RLS WAS NEVER EXERCISED. By anyone. THE MOST CONSEQUENTIAL ITEM IN THE RUN."
    evidence: >-
      backend/.env set DATABASE_URL=…postgres:postgres@…  · pg_stat_activity: the app
      connected as `postgres` · pg_roles: rolsuper = t · pg_class: 23 tables carry
      relrowsecurity. POSTGRES RLS, EVEN FORCEd, DOES NOT APPLY TO SUPERUSERS.
      Journey E reported "Tenant isolation — PASS" and what it ACTUALLY proved was cookie
      host-scoping, CORS and the 404 no-oracle — all app-layer, all real, NONE of them the
      database. Everything the runbook lists as binding under the app role
      (terms_versions INSERT+SELECT only, platform_audit_log INSERT-only, no DELETE on
      payment tables, unreadable alembic_version) was SILENTLY VOID for the whole run.
    the_sharpest_part: >-
      `boutique_app` ALREADY EXISTED in the cluster with rolsuper = f. Somebody had set it
      up. `.env` was simply never pointed at it. A safeguard you have to remember to
      switch on is a safeguard that does not run.
    fixed_how: >-
      docs/real-world-qa.md §2.2 NOW WRITES THE APP-ROLE URL BY DEFAULT and §2.1 shows the
      inline owner-URL override for alembic and app.cli. §5 is no longer an optional
      appendix. A run that deliberately uses `postgres` must write "RLS NOT EXERCISED" at
      the top of its report.
  - id: G2
    what: "the ENTIRE deposit/payment leg — zero coverage, and it is the only leg with money semantics"
    detail: >-
      All five /book/pay states, the HMAC webhook round-trip, the decline path (whose
      transaction id differs per outcome on purpose), the DEPOSIT_HOLD_SECONDS sweeper
      expiry, the bounded-poll timeout. Blocked because seed_demo.py sets every
      appointment type deposit_required:false DELIBERATELY (a deposit type strands the
      demo booking in pending_payment). Turning it on needs console setup + fake gateway
      credentials. THE PAYMENT CONTRACT IS EXACTLY AS UNTESTED AFTER THIS RUN AS BEFORE IT.
  - id: G3
    what: "/b/{token} awaiting-payment and past-appointment states — never rendered"
    detail: >-
      BOOKING_AWAITING_PAYMENT exists SPECIFICALLY so a mid-checkout bride is never told
      she was cancelled. That string has still never been seen on screen. Blocked by G2.
  - id: G4
    what: "document.hidden poll suspension is PERMANENTLY untestable in this harness"
    detail: >-
      Chromium under CDP never reports a Playwright-driven background tab as hidden — a
      probe showed visibilitychange never fires and document.hidden stays false. Journey B
      hit this as a FALSE NEGATIVE first, caught itself, and proved the handler with a
      synthetic property override instead. RECORD IT AS OUT-OF-REACH, NEVER AS "PASSED".
  - id: G6
    what: "dashboard honest-degradation strings unreached"
    detail: "«פחות מ־0.1%» and the outage line need contrived data or a forced fetch failure."

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
    owner: >-
      unassigned — pick up at the E4 boundary or sooner if it recurs. PARTLY ANSWERED by
      F61, which fixed seven load-flaky frontend tests by TIGHTENING waits and not one by
      raising a timeout: `getBy` -> `findBy`, a bare read -> `waitFor`, and an
      `await act(async () => {})` before an Esc that cannot be waited for. Same class of
      race as this entry, different files (SosRaiseDialog, WaitlistPanel, SeamstressPanel,
      SosOverlay, CatalogPage). This specific ManageBookingPage assertion was NOT touched.
  # ---- ACCEPTED DEBT, not a flake: three padded budgets, recorded so nobody re-derives ----
  - test: >-
      frontend/apps/manage/src/__tests__/AtelierSection.test.tsx :: 5c and 5d (60 s each) ·
      frontend/apps/storefront/src/__tests__/CatalogPage.test.tsx :: load-more (60 s test, 30 s per wait)
    seen: "2026-08-05, F61 review round 1 — the reviewer flagged the padding, the verifier flagged the number behind it"
    evidence: >-
      The commit that raised 5c/5d from 20 s to 60 s wrote "measured idle on an M-series
      laptop they take 16.4 s and 15.3 s". RE-MEASURED THREE WAYS AND IT IS WRONG BY 16×:
        isolated, that file alone        5c 0.98 s   5d 0.93 s
        with the storefront alongside    5c 1.07 s   5d 1.02 s
        the whole gate concurrent        5c 3.87 s   5d 1.15 s   CatalogPage 2.91 s
      What IS real is the SPREAD — 4× between alone and under `pnpm -r test` — and PR #39's
      first CI run, where a 5 s budget genuinely timed out on the contended 2-core runner.
    why_it_matters: >-
      A test whose true cost is ~4 s inside a 60 s budget passes through a 15× regression in
      silence, and these three now own the frontend gate's tail. The budgets are KEPT — the
      150-card board and the 50-dress catalogue are the mechanism, not padding, and shrinking
      either deletes the defect instead of the delay — but the baselines above are the numbers
      to watch, and they are now written into all three test files.
      THE LESSON, which is the same one the /fake-pay entry taught: a measurement nobody
      re-ran is not evidence. This one survived a commit message, a code comment and a review.
    owner: unassigned — LOW; revisit only if the gate's tail becomes a problem

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

## Session report — 2026-08-05 (F61, the a11y/UX batch)

**All nine walkthrough defects fixed, plus a tenth found inside one of the fixes.** One branch, one review round, one adversarial verification round. No migration.

| # | Defect | Fixed in | The test that reds if reverted |
|---|---|---|---|
| 1 | `/checkin` pins validation errors after correction | `CheckinPage.tsx` | `CheckinPage.test.tsx` — per-field isolation, `aria-invalid` + message |
| 2 | Editing an atelier ticket announces nothing | `AtelierSection.tsx` | two tests; the second uses a **MutationObserver**, the only instrument that can see it |
| 3 | Erase confirm rejects its own lookup's phone format | `PrivacySection.tsx` | `PrivacySection.test.tsx` |
| 4 | Every staff-row button is nameless | `StaffSection.tsx` | `StaffSection.test.tsx` — asserts names are **unique**, not merely present |
| 5 | Booking flow is not a `<form>` | `BookPage.tsx` **+ `CheckinPage.tsx`** | structure in vitest, the keypress in Playwright |
| 6 | Unrouted paths escape the error envelope | `backend/app/main.py` | `test_spa_serving.py`, incl. a 405 guard |
| 7 | Logout control 29 × 21 px | `ConsoleShell.tsx` | `guide.spec.ts` — `boundingBox()` in real Chromium |
| 8 | Neither SPA has an error boundary | `packages/ui` + both `main.tsx` | behaviour in `packages/ui`, wiring in each app |
| 9 | Privacy bullets have no list semantics | `PrivacyProse.tsx` | vitest ×3 + e2e ×2; backend privacy text untouched |

**The tenth: `/checkin` had defect 5 too, and the first pass shipped only the booking half** — while editing that very file for defect 1. A comment in `BookPage.tsx` even asserted the check-in form already carried the same `required`/`noValidate` reasoning; it had no `<form>` at all. The kiosk surface is the one that is *only* ever used on a phone, where the keyboard's Go key **is** the submit button.

### What the two review rounds actually bought

**Both rounds' best findings were about claims, not code** — the same lesson as the `/fake-pay` correction:

- A commit message, a code comment and a review had all carried "measured idle these tests take 16.4 s and 15.3 s". Re-measured three ways: **0.98 s / 0.93 s isolated, 3.87 s / 1.15 s under the concurrent gate**. Wrong by 16×, and it was the sole justification for a 20 s → 60 s budget raise. See `known_flaky`.
- The booking e2e's own mutation ledger claimed a mutation "reds all three steps". Re-run: it reds at the **slot** step only — details still advances, because HTML submits a button-less form that has exactly one implicit-submission-blocking field. Ledger corrected against a real build.
- A source comment asserted `setCue` with an equal value "is a React no-op". It never is — a fresh object always re-renders. What actually stayed silent is React's **text-child diff**, which skips the DOM write when the string is unchanged. That is defect 2's other half (below), and three more files still carry the wrong belief.

**The half of defect 2 the first fix left silent.** `atelier.cue.updated` interpolates only `{{name}}`, so a *second* edit of one bride produces byte-identical cue text — and therefore no DOM mutation and no announcement. Fix her date, save; reopen, fix her notes, save: silence indistinguishable from a failed save, which is exactly what the cue exists to remove. Fixed with a **nonce on the cue state keying a span inside the live region**, so the `<p role="status">` is never remounted (an added region is not announced) but its child always is. One guard on the writer covers all eight call sites — including the two other repeatable cues, capacity-save and settings-save.

**Still open, and it is a real sweep:** `FloorPanel.tsx:270`, `GuideOverlay.tsx:49` and `RoomsRegistryDialog.tsx:160` carry the same wrong comment. `RoomsRegistryDialog` is safe by accident (it clears to `""` before every write); the other two are not audited.

### Gates, run on this tree

| Gate | Result |
|---|---|
| `pytest -m "not db"` | **2351 passed** |
| `pytest -m "db and not s3"` | **845 passed** (9 s3-marked error locally — no MinIO; unrelated to this diff) |
| `ruff check` · `ruff format --check` · `mypy` | clean · 328 formatted · **302 files, no issues** |
| `pnpm -r lint` · `pnpm -r typecheck` | clean · clean |
| `pnpm -r test` | **2515 passed** (ui 108 / storefront 1097 / manage 1310) |
| `pnpm -r build` | clean |
| `pnpm e2e` | **155 passed** (was 153; +2 for `/checkin`'s Enter) |
| `frontend/scripts/qa-greps.sh` | exit 0 |

---

## Session report — 2026-08-03 → 2026-08-04

**The floor-management program is complete.** Ten features, one PR each, nine of them in this window.

| # | Feature | PR | Migration | CI runs |
|---|---|---|---|---|
| F57 | Floor roles, break status, staff cards | #33 | 0015 | 1 |
| F33 | QR self-check-in, queue tickets, live position | #36 | 0018 | 1 |
| F36 | Fitting-room registry + assignment | #37 | 0019 | 1 |
| F59 | Public wall-screen queue board | #38 | — | 1 |
| F41 | Atelier tickets + kanban | #39 | 0020 | **3** |
| F58 | Waitlist + dispatch | #40 | 0021 | 1 |
| F37 | SOS paging | #41 | 0022 | 1 |
| F60 | Guided walkthrough | #42 | — | 1 |
| F42 | Seamstress capacity + load bars | #43 | 0023 | 1 |

F19 (#34) and F53 (#35) merged in the same window from **other sessions** and were deliberately left alone; see the liveness note in `current:`.

### What the reviews actually bought

Every feature's review found something, and the pattern is worth recording: **the most dangerous findings were in the proofs, not the code.**

- **F58** — the spec's stranding mutation was *vacuous*, so A8 (the one test discharging F33's deployment gate) asserted nothing. The rebuilt A8 *still* could not reach the `IntegrityError`. Only the third attempt bites.
- **F41** — three tests that could not fail: a missing SQL `LIMIT` hidden behind a Python slice, `populate_existing=True` (only bites a stale identity map, so a single-writer test can never show it), and an undo clause whose target column was already NULL.
- **F59** — the board-vs-position agreement test seeded five all-waiting rows, so widening the filter on one side alone added no rows and the alarm never fired.
- **F60** — **jsdom ships no `<dialog>`**, so every vitest assertion about dialog focus, traps or Esc measures a stub. See `known_vacuous`.
- **F42** — the load bar divided a *stock* by a *rate*: permanently red in a healthy shop, green on exactly the day it exists to warn about.
- **F36** — the spec's 409 discriminator (`exc.orig.constraint_name`) is always `None` here, so **every 409 would have been a 500**.

### Two CI reds, and only one was a defect

**F41 red 1 was real and every local gate missed it.** A focus-restore effect with no dependency array cleared its intent before the repaint it awaited, dropping a seamstress's focus to `<body>` five seconds after a colleague touched her ticket. Local full-suite passed, the same test in isolation failed, CI failed — three behaviours; the margin is **exactly one event-loop turn**. The first fix was then refuted by an adversarial verifier for creating a focus *steal* in the other direction.

**F41 red 2 was not a defect** — two tests timed out because their 150-card board *is* the mechanism (it makes React yield between commit and passive flush). Shrinking it would have deleted the defect rather than the delay.

### Merge hazards this window taught

- **Git can resolve a conflict cleanly and wrongly.** In the F37/F58 merge both sides had written `assert len(live) == 18`, so git merged that line with no marker while the true count was 23.
- **A broken test file reports `Tests no tests`, not failures.** Hit twice — once for real in the F42/F60 i18n merge, where both sides ended mid-`it` and shared a trailing `});` so a naive union left an unclosed brace.
- The remedy both times: **count tests against both parents** and require `main + HEAD − base`.

### Owed, in priority order

1. **The E7 epic-boundary QA pass** (loop step 9) — never run. Ten features shipped in two days and nothing has driven the assembled product in a real browser.
2. **The `known_vacuous` audit** — six `apps/manage` test files mount a `Modal`; their focus assertions may be incapable of failing.
3. `known_flaky` still holds two entries.

### Next pick

**F50** (walk-in bookings, SMC-6). Then F22, F24, F25, F27, F28, F35, F47, F49.

---

## Run report

_Written when the queue is exhausted._
