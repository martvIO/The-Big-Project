---
tags: [meta, tooling, spartan, hazard]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Vendored Toolkit Applicability Audit

**What it is.** The **method** for deciding whether a file under `.claude/` applies to this repo,
and the verdict vocabulary that goes in a page's `applicability:` field. The *evidence* that the
toolkit targets another stack lives once, in [[Documented Stack Vs Actual Stack]] — this page does
not restate it.

185 files under `.claude/` are tracked. Most are unmodified [[Spartan Toolkit]] boilerplate,
installed wholesale and written for other repositories.

## The three verdicts

**`vendored-inapplicable`** — the file names a language, framework or ORM that does not exist here
(Kotlin, Micronaut, Gradle, Exposed, Next.js, App Router). Read for *intent* if you like; never for
code. This is the **default verdict** for anything under `.claude/rules/`, `.claude/skills/`,
`.claude/agents/` and `.claude/commands/spartan/`, because the toolkit was not curated on the way
in.

**`active`** — first-party files that happen to live under `.claude/`. These are not vendored at
all: [[.claude/commands/modryn-loop.md]], [[.claude/commands/brain-ingest.md]],
[[.claude/commands/brain-sync.md]] and [[.claude/scripts/merge-gate.sh]] were written for this
repo and are invoked by it.

**Contradicted by shipped code** — the sharpest category, and the one worth checking for before
following any rule. The vendored guidance is not merely irrelevant; a reviewed decision in this
repo says the opposite:

- [[.claude/rules/backend-micronaut/API_DESIGN.md]] bans `@Delete` / `@Patch` and path parameters.
  This backend uses both, everywhere on `/manage`. [[backend/app/auth/staff_router.py]]'s docstring
  records the ruling in one line: *"The `.claude/rules` RPC / @QueryValue guidance is Kotlin
  boilerplate for another codebase; F15's D7 already ruled this."*
- [[.claude/rules/database/SCHEMA.md]] describes Exposed `SoftDeleteTable` / `transaction(db.primary)`
  patterns. The *policies* underneath it — no FK constraints, soft delete, `TIMESTAMPTZ`
  everywhere — are real and shared ([[.planning/architecture.md]]). The code examples are for a
  different ORM; this repo uses [[SQLAlchemy]].

## How to audit a file you have not seen before

1. Does it name a language, framework or ORM? Check it against `git ls-files` — one grep settles it.
2. Does any tracked repo file import, invoke or reference it? A first-party command or script will
   be reachable from the [[Makefile]], CI, or [[.planning/LOOP-STATE.md]].
3. Does a shipped module docstring already overrule it? Several do, by name.

If 1 fails and 2 finds nothing, the verdict is `vendored-inapplicable`. Say so on the page and
backlink to [[Documented Stack Vs Actual Stack]].

## The trap that makes this more than bookkeeping

[[.claude/CLAUDE.md]] is loaded into context on **every** session. A `.brain/` page is read only
when someone goes looking. Marking a file inapplicable here **does not stop it steering a session**
— it only gives you something to point at afterwards. The real fix is editing `.claude/CLAUDE.md`,
which is still open.

## Related

- [[Documented Stack Vs Actual Stack]] · [[Repo Hazards]] · [[Spartan Toolkit]]
- [[Planning Artifacts Vs Implementation]] — `.planning/` is a decision record for *this* repo and
  is read the opposite way
