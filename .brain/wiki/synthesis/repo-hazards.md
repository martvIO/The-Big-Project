---
tags: [meta, hazard, tooling]
sources: [Makefile, .gitignore, .claude/CLAUDE.md]
created: 2026-07-23
updated: 2026-07-23
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
kind: synthesis
applicability: n/a
---

# Repo Hazards

**Purpose.** Traps in this repository that will silently waste your time. Read this before your
first substantial change.

## 1. Directory case: git says `backend/`, the disk says `Backend/`

The on-disk directories are `Backend/` and `Frontend/`; git's index stores them lowercase.
macOS's case-insensitive filesystem hides the discrepancy for `cd` and `ls`, but pathspecs are
matched against the index:

```bash
git ls-files Backend    # -> 0 results, silently
git ls-files backend    # -> 70 results
```

**Always use the lowercase form** in `git ls-files`, `git diff`, `git log -- <path>`, and in
every `path:` field in this wiki. A silent empty result is the failure mode, which is why this
is hazard number one.

## 2. The repo path contains spaces and a `+`

`/Users/mrwen/Documents/Github/Ryan + rawad + mrwen`. Every shell invocation must quote it.
[[Makefile]] opens with a comment about exactly this and uses `$(CURDIR)` throughout — follow
that discipline. Unquoted `$CLAUDE_PROJECT_DIR` in a hook command will break in a way that looks
like the hook simply not firing.

## 3. `.worktrees/owner-settings/` is a second full checkout

A git worktree on branch `feature/owner-settings` lives at `.worktrees/owner-settings/` — a
complete duplicate of the repo, roughly 335 MB and ~11,000 files. It is git-ignored.

Consequences: a naive recursive `grep`, `find`, or file-count over the repo root will double
every result and appear to find two copies of every file. Restrict searches with `git ls-files`
or exclude `.worktrees/` explicitly.

## 4. `frontend/App/` is dead

A stale scaffold left over from an earlier setup — ~747 files including its own `node_modules/`
and `.env`. It is **not** referenced by `frontend/pnpm-workspace.yaml` or by any [[Makefile]]
target, and it is git-ignored. Nothing imports it. Do not edit it, and do not take it as
evidence of how the frontend is structured — see [[Frontend Scaffold Reality]].

## 5. Ignored trees dwarf the tracked repo

350 tracked files against roughly 8,200 ignored ones: `backend/.venv/` (~4,460),
`frontend/node_modules/` (~2,780), 74 `__pycache__/` directories, plus the two above. Any tool
pointed at the directory tree rather than at `git ls-files` will drown.

## 6. Documented conventions target the wrong stack

The single biggest hazard, with its own page: [[Documented Stack Vs Actual Stack]].

## 7. `.handoff/` is referenced but has never existed

[[.claude/CLAUDE.md]] Principle 4 and `/spartan:context-save` both write to `.handoff/` and
`.memory/transcripts/`. Neither directory has ever been created — the mechanism was designed,
documented as auto-triggered, and used zero times. Only `.memory/patterns/` is real and
populated. Treat this as the base rate for prose-only conventions in this repo, and as the
reason this wiki leans on `make brain-check` in CI rather than on good intentions.

## 8. qmd search: `--path` is silently ignored

`qmd search "query" --path wiki/` does not filter — it returns hits from outside the given path
and gives no error. The flag as documented in the second-brain query skill does not work on this
build. **Always scope with `-c <collection>` instead.**

## Related

- [[Documented Stack Vs Actual Stack]]
- [[Frontend Scaffold Reality]]
