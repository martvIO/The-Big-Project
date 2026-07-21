---
description: Website idea → critique loop → web research → plan (user approval gate) → build with TDD, security + code review
argument-hint: "your website idea"
---

You are running the full website pipeline for this idea:

**Idea:** $ARGUMENTS

If no idea was given, ask the user for one and stop until they answer.
Respond in the user's language throughout.

## Phase 1 — Stress-test the idea (loop, max 3 rounds)

Each round:
1. **Attack it.** Spawn the `idea-killer` agent with the current version of the idea. Collect: what's missing, what's wrong, weak assumptions, who actually needs this, and why existing products might already solve it.
2. **Research.** Web-search 3–5 similar products/competitors. For each, note: what they do well, common user complaints, one thing to borrow, one thing to avoid.
3. **Ask.** If open questions would materially change the design, ask the user (max 4 questions per round) before continuing.
4. **Improve.** Rewrite the idea as a sharper brief: target user, core problem, the 3 features that matter for v1, and what is explicitly OUT of scope.

Exit the loop when a round produces no NEW critical objections, or after 3 rounds. Never loop forever.

## Phase 2 — Decide how to build and display it

- **Frontend:** framework, rendering strategy (static / SSR / SPA), styling approach, key screens and their states (loading / empty / error).
- **Backend:** whether one is needed at all; if yes — API style, database, auth.
- **Hosting / deploy.**

Present 2 realistic stack options with trade-offs and ONE recommendation. If this repo already defines a stack in `.claude/rules/`, the project stack wins.

## Phase 3 — Final plan → STOP (hard gate)

Write the plan to `.planning/specs/<idea-slug>.md` containing: refined brief, competitor learnings, chosen architecture (frontend + backend), data model, API surface, page/component list, edge cases to handle, security checklist, test strategy, and build order.

Then STOP and show a summary of the plan. **Do not write any production code until the user explicitly approves.** This gate applies even in auto mode.

## Phase 4 — Build (only after approval)

1. Scaffold the backend and frontend architecture from the plan.
2. TDD per feature: failing test → implementation → refactor. No production code without a test.
3. Implement every edge case listed in the plan, each with its own test.
4. **Security pass:** input validation, authorization on every endpoint, no hardcoded secrets, XSS/CSRF/injection checks, dependency audit.
5. **Code review pass:** spawn a reviewer subagent to hunt for correctness bugs and project-rule violations; fix confirmed findings; re-review until clean (max 3 cycles).
6. Run the full test suite and the production build. Fix until green. If something still fails, report it honestly — never claim done when it isn't.

## Phase 5 — Report

Summarize: what was built, test results, security findings and fixes, known gaps, and suggested next steps.
