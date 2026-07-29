---
description: Run one iteration of the MODRYN program loop — build, review, test, ship the next queued feature
preamble-tier: 3
---

# MODRYN Program Loop

Autonomous feature loop for the MODRYN boutique platform. **One invocation = one feature, carried from spec to merged PR.** State lives in `.planning/LOOP-STATE.md`, not in this conversation, so any session — fresh, compacted, or tomorrow's — continues the run by typing `/modryn-loop`.

Run it on repeat with `/loop /modryn-loop` to keep iterating unattended.

---

## Non-negotiables

Read these before touching anything. Violating them is how this loop breaks the repo.

1. **`.claude/rules/` does NOT describe this repo.** It is Kotlin/Micronaut boilerplate. This repo is Python 3.13 / FastAPI / SQLAlchemy 2 / Alembic / Postgres-with-RLS on the backend and Vite 8 / React 19 / TypeScript / Tailwind 4 (pnpm workspace, apps `storefront` + `manage`, packages `ui` + `api-client`) on the frontend. **Every builder and reviewer subagent prompt must repeat this ignore-instruction verbatim** — omit it once and you get Kotlin-flavoured review findings on Python code.
   DB conventions that *do* apply: no foreign-key constraints, `TEXT` not `VARCHAR`, soft delete via `deleted_at`, `uuid_generate_v4()`, partial indexes for active rows. Real patterns live in `Backend/app/boutique/`.
2. **`main` has no branch protection.** The merge gate in this command is the *only* thing standing between a red build and `main`. Never `gh pr merge --auto` (it merges instantly on an unprotected branch), never `--admin`, never merge while a gating check is pending or failing.
3. **The three gating CI jobs** are `Backend (lint, types, tests)`, `Frontend (lint, types, build)`, and `Frontend E2E (Playwright + axe)`. All three must pass. The jobs `Code wiki drift (warn-only)` and `Dependency audits (warn-only)` are `continue-on-error: true` and are usually red — **ignore them**.
4. **No Docker locally.** Tests marked `db` or `s3` only run on CI. The first CI run of a feature routinely fails on a *test* bug rather than a product bug — that is expected, budgeted for, and not a quality failure.
5. **Paths contain spaces and a `+`.** Quote every shell path.
6. **All code mutations happen in a worktree** under `.worktrees/<slug>`. Parallel sessions share the main checkout — never assume its branch or working tree is what you left it as. Re-read state before every mutation.
7. **Never stop to ask the user a question.** Every product decision was made in `.planning/epics/interview-2026-07-29.md`. Answers recorded there as `DELEGATED` are explicit licence to decide yourself after researching (web + codebase); record what you decided in the spec. If you hit something genuinely unanswerable, park the feature and continue — do not idle.

---

## Iteration algorithm

### 0. Sync and read state

```bash
cd "/Users/mrwen/Documents/Github/Ryan + rawad + mrwen"
git fetch origin main --quiet
```

Read `.planning/LOOP-STATE.md` (a fenced YAML block inside a markdown wrapper). Then re-read `.planning/external-applications.md`: if any external blocker has flipped to approved/registered, clear the `blocker` on the features it gated and set them back to `queued`.

Do **not** switch the main checkout's branch — another session may be using it. Use `git -C .worktrees/<slug>` for feature work, and a dedicated worktree for `main`-side commits if the main checkout is busy.

### 1. Resume check

If `current` names a feature whose status is `building`, `in-review`, `pr-open` or `ci-fix`, a previous session died mid-flight. Inspect reality — does the worktree exist, does the branch have commits, is there an open PR? — and resume at that stage. If the worktree is gone and the branch has nothing, reset the entry to `queued`, increment `attempts`, and carry on. Exceeding `max_feature_attempts` means status `failed` + park.

### 2. Pick the next feature

First `queued` entry whose `deps` are all `merged` and whose `blocker` is null. If none remain, go to step 9 (report). Set its status to `specing`, set `current`, and commit the state change to `main`:

```
docs(planning): loop — F<N> started
```

### 3. Spec and plan (fresh-context subagents)

If `.planning/specs/<slug>.md` is missing, dispatch a spec-writer subagent: it reads the epic brief, the relevant interview answers, and **verifies against the current codebase** (what already exists to build on changes with every merge). The spec header records `Gate 1: standing approval — interview-2026-07-29.md §Standing approvals`.

Frontend-touching features also get a design doc under `.planning/design/screens/<slug>/`, following the copy rules already approved in the interview, plus the `design-critic` agent. The design gate is agent-approved under the standing delegation.

Then a plan-writer subagent produces `.planning/plans/<slug>.md`.

### 4. Worktree

```bash
git worktree add ".worktrees/<slug>" -b "feature/<slug>" origin/main
```

### 5. Build (TDD)

One builder subagent working inside the worktree. Its prompt **must** carry the ignore-`.claude/rules/` preamble from Non-negotiables plus the DB conventions. Failing test first, then the code that makes it pass. Conventional, scoped commits (`feat(booking):`, `test(e2e):`) — a handful of logical commits, not one mega-commit.

### 6. Dual review

Two reviewers in parallel over the diff: the `phase-reviewer` agent for quality/design, and an adversarial security reviewer. The builder applies **one fix commit per round**. Maximum `max_ci_fix_rounds` rounds. A BLOCKER finding that survives the last round means status `failed` → park → continue to the next feature. Never let a reviewer review its own work.

### 7. Local gates

In the worktree: `make lint`, backend unit tests (non-`db`), `make fe-test`. If the feature touches the frontend, also `make fe-build` and `make e2e`. Red sends you back to step 5, bounded by `max_feature_attempts`.

### 8. Ship

```bash
git push -u origin "feature/<slug>"
gh pr create --title "Feature <N>: <Title> (Epic E<X>)" --body "<summary, spec link, test evidence>"
gh pr checks <n> --watch
```

On a red gating job: `gh run view --log-failed`, dispatch a fix subagent into the worktree, one commit, re-watch. Bounded by `max_ci_fix_rounds`; exceeded → status `ci-fix`, park, continue.

**Merge gate.** Never judge check output by eye — `gh pr checks` exits non-zero whenever *any* check fails, and the two warn-only jobs are red on almost every PR. Ask the script:

```bash
bash .claude/scripts/merge-gate.sh <n> && gh pr merge <n> --merge
```

`merge-gate.sh` exits 0 only when all three gating jobs report `pass`; missing, pending, skipped or failed all block. It fails closed. Its self-check is `bash .claude/scripts/merge-gate.test.sh` — run that if you ever edit it.

Then, on the `main` side: pull, and commit the bookkeeping —

```
docs(planning): F<N> shipped (PR #<M>) — <one line>
```

updating the epic's Features table row to `done (PR #M)` and the `LOOP-STATE` entry to `merged`. Remove the worktree. Push.

### 9. Epic boundary

When the merged feature was the last of its epic: run the full `make e2e` on `main`, confirm the axe a11y spec is zero-violation (IS 5568 / WCAG 2.0 AA is a **legal** requirement here, not a nicety), do a real-Chromium click-through of the epic's user journeys with the Playwright MCP tools against `vite preview`, then `/brain-sync`. Findings become a fix commit or a new queued entry. The epic is not `done` in LOOP-STATE until this passes.

### 10. Continue

Schedule the next iteration and stop cleanly. If context is getting heavy, write state, say plainly that the run continues with `/modryn-loop` in a fresh session, and stop — the state file makes restart lossless.

### 11. Report

When the queue holds nothing but `parked`/`merged` entries, append a `## Run report` to `LOOP-STATE.md`: what shipped (feature, PR, date), what parked and exactly why, and the outstanding `user_actions` only the human can clear (merchant account, domain purchase, SMS sender-ID registration). Commit it and stop the loop.

---

## Honest limits

- Features blocked on external accounts (payment gateway, SMS sender ID, production domain) **cannot** be built around. They stay parked and get re-nagged in every report.
- Interview answers age. A spec-writer that finds an answer contradicted by shipped reality records the conflict in the spec, takes the codebase-consistent reading, and continues.
- Auto-merge means a green-CI-but-wrong feature can reach `main`. Dual review and the epic QA pass are the compensating controls; they are not a guarantee.
