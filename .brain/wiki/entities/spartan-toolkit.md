---
tags: [meta, tooling, vendored]
sources: []
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: entity
applicability: n/a
---

# Spartan Toolkit

**Purpose.** A vendored agent-tooling toolkit installed under `.claude/` — 71 slash commands, 22 rule files, 9 agents, and ~30 skills. Version is recorded in `.claude/.spartan-version`; enabled packs in `.claude/.spartan-packs`.

**It is generic, not written for this project.** Large parts of it target stacks this repo does not use — Kotlin/Micronaut, Exposed ORM, Next.js, Terraform. See [[Documented Stack Vs Actual Stack]] and [[Vendored Toolkit Applicability Audit]] before following any of its conventions.

Pages for its files carry `kind: vendored`, and those targeting inapplicable stacks also carry `applicability: vendored-inapplicable`, which excludes them from the default drift report.
