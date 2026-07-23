---
tags: [meta, tooling, hazard, spartan]
sources: [.claude/CLAUDE.md, README.md, .planning/architecture.md, backend/pyproject.toml, frontend/package.json]
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: synthesis
applicability: n/a
---

# Documented Stack Vs Actual Stack

**Purpose.** The agent instructions loaded into every session describe a stack this repo does
not use. This page is the evidence document. Every page carrying
`applicability: vendored-inapplicable` backlinks here.

## The claim

[[.claude/CLAUDE.md]] — 480 lines, loaded unconditionally at the start of every session —
contains a section titled *"Kotlin + Micronaut Backend"* stating **"Stack: Kotlin + Micronaut —
coroutines, Either error handling, Exposed ORM"**, and a section titled *"React + Next.js
Frontend"* stating **"Stack: React / Next.js / TypeScript (App Router)"**.

## The evidence against it

| Check | Command | Result |
|---|---|---|
| Any Kotlin/Java/Gradle file | `git ls-files \| grep -E '\.(kt\|kts\|gradle\|java)$'` | **0 files** |
| Any Next.js dependency | `grep -rl '"next"' frontend --include=package.json` | **none** |
| Actual backend | [[backend/pyproject.toml]] | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, `uv` |
| Actual frontend | [[frontend/package.json]] | pnpm 10 workspace, React 19, Vite 8, TypeScript 5.7, Tailwind 4 |

The authoritative statements of this project's stack are [[README.md]] and
[[.planning/architecture.md]] (its "Locked decisions" table), not `.claude/CLAUDE.md`.

## What is affected

13 tracked files under `.claude/` name Kotlin, Micronaut, or Next.js directly:

- Rules — [[.claude/rules/backend-micronaut/KOTLIN.md]], [[.claude/rules/backend-micronaut/API_DESIGN.md]],
  [[.claude/rules/backend-micronaut/CONTROLLERS.md]], [[.claude/rules/backend-micronaut/SERVICES_AND_BEANS.md]],
  [[.claude/rules/backend-micronaut/BATCH_PROCESSING.md]], [[.claude/rules/backend-micronaut/RETROFIT_PLACEMENT.md]]
- Skills — [[.claude/skills/kotlin-best-practices/SKILL.md]], [[.claude/skills/kotlin-best-practices/code-patterns.md]],
  [[.claude/skills/database-table-creator/kotlin-templates.md]]
- Commands — [[.claude/commands/spartan/kotlin-service.md]], [[.claude/commands/spartan/next-app.md]],
  [[.claude/commands/spartan/next-feature.md]]
- Agent — [[.claude/agents/micronaut-backend-expert.md]]

A second, subtler group: the three `.claude/rules/database/` files
([[.claude/rules/database/SCHEMA.md]], [[.claude/rules/database/ORM_AND_REPO.md]],
[[.claude/rules/database/TRANSACTIONS.md]]) are written for **Exposed ORM in Kotlin** —
`SoftDeleteTable`, `transaction(db.primary)`, `EntityID<UUID>.value`. None of that exists here;
this repo uses [[SQLAlchemy]] with [[Alembic]].

These are worth reading anyway for their *intent* — the no-foreign-keys, soft-delete,
`TIMESTAMPTZ`-everywhere, transaction-for-multi-table-writes policies are real design decisions
this project may or may not share. But their code examples are not applicable.

## Why this matters more than a documentation nit

`.claude/CLAUDE.md` is loaded into context on **every** session. `.brain/` pages are read only
when Principle 8 is obeyed. **The wiki cannot outrank the memory file.** Documenting the
mismatch here does not neutralize it.

## The actual fix

Edit [[.claude/CLAUDE.md]] to delete or explicitly fence the "Kotlin + Micronaut Backend" and
"React + Next.js Frontend" sections, replacing them with the real stack. Treat this page as the
evidence for that edit, not as a substitute for it.

**Status: not yet done.** Recorded as a follow-up.

## Related

- [[Vendored Toolkit Applicability Audit]] — file-by-file verdicts
- [[Spartan Toolkit]]
- [[Repo Hazards]]
