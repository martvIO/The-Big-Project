---
tags: [vendored, spartan]
sources: [<PATH>]
created: <DATE>
updated: <DATE>
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: <PATH>
blob: <GIT_HASH_OBJECT>
commit: <GIT_HEAD>
kind: vendored
applicability: vendored-inapplicable
---

# <PATH>

> **VENDORED — NOT THIS PROJECT'S CONVENTIONS.** Shipped by the [[Spartan Toolkit]].
> Targets **<STACK>**, which this repo does not use. See [[Documented Stack Vs Actual Stack]].

**Purpose.** What it says, in one or two sentences.

**Applies to this repo?** No — targets <STACK>; this repo is Python/FastAPI + React/Vite.

**Safe to delete?** Yes / No (referenced by [[.claude/commands/spartan/…]]).

<!--
Set `applicability: active` instead, and drop the banner, when the file genuinely does
apply here (e.g. core/ rules, product/ops commands). Keep `kind: vendored` either way —
it marks provenance, not applicability.
-->
