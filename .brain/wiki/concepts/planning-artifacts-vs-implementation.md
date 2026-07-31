---
tags: [meta, planning, process, docs]
sources: []
created: 2026-07-31
updated: 2026-07-31
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: concept
applicability: active
---

# Planning Artifacts Vs Implementation

**What it is.** `.planning/` is this project's **decision record** — 21 specs, 17 plans, ten epics,
a design deck, a security checklist and a machine-readable feature queue. It is authoritative for
*intent and rationale*. It is **not** authoritative for behaviour. That distinction mirrors the one
`.brain/CLAUDE.md` draws between orientation and behaviour, and it applies with the same force.

## What is in there

| Path | Holds |
|---|---|
| [[.planning/architecture.md]] | the standing "Locked decisions" table for all epics |
| `.planning/specs/` | one spec per feature, written **before** the code |
| `.planning/plans/` | the implementation plan the spec was broken into |
| `.planning/epics/` | E1–E10, [[.planning/epics/ROADMAP.md]], and the interview rulings features cite by number |
| `.planning/design/` | research → definition → ideation → system → screens |
| [[.planning/security-checklist-v1.md]] | the pilot ship gate |
| [[.planning/LOOP-STATE.md]] | the live queue the autonomous build loop reads *and writes* |

## Specs are not rewritten after the fact

This is the part that bites. A spec records what was decided at the time; the code records what was
built. Two live examples from [[.planning/architecture.md]]:

- its data model names a **`slots` table**. There is none — no migration creates it, because slots
  turned out to be materialized purely from availability rules in [[backend/app/booking/slots.py]];
- it describes `packages/api-client` as **OpenAPI-generated**. F10 declined codegen and
  [[frontend/packages/api-client/src/index.ts]] is a deliberate empty stub explaining why.

Neither is drift to be fixed. They are earlier decisions that a later, reviewed decision overrode.
Unticked checklist boxes read the same way: they gate the pilot, they are not forgotten work.

## Where the reconciliation actually lives

The modules do it themselves. Nearly every backend module docstring cites the ruling that shaped it
by name — *"spec D7"*, *"Interview Q3"*, *"the F8/F10 rule"*, *"pilot decision, 2026-07-28"* — so
reading the module usually gives you both the behaviour and the reason. Read a spec to learn what a
feature was **for**; read the module to learn what it **does**; the docstring is where the two meet.

## The loop file is not documentation

[[.planning/LOOP-STATE.md]] is program state with a hard rule at the top: *do not hand-edit while
the loop is mid-feature*. It is written by `docs(planning)` commits at coarse checkpoints and read
by [[.claude/commands/modryn-loop.md]].

## Related

- [[Vendored Toolkit Applicability Audit]] — `.claude/` is a different animal entirely and must not
  be read as a decision record for this repo
- [[Documented Stack Vs Actual Stack]] · [[Repo Hazards]]
