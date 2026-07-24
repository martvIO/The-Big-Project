# Log

Chronological record of all operations. **Append-only — never edit an existing entry.**

## [2026-07-23] setup | .brain initialized
Created the code wiki at `.brain/` for the Boutique Platform repo: 1:1 page coverage of all
350 tracked files (`.brain/` itself excluded from its own corpus).

Machinery: `brain-page-path.sh` (the canonical repo-path ↔ page-path mapping),
`brain-scan.sh` (missing/stale/orphan, keyed on per-file `git hash-object` rather than repo
HEAD), `brain-index.sh` (generates `wiki/index.md`), six page templates, and SessionStart /
SessionEnd hooks registered in `.claude/settings.json`.

Behavioral wiring: Principle 8 "Consult the Second Brain First (Orientation, Not Truth)" added
to `.claude/CLAUDE.md`; `/brain-ingest` and `/brain-sync` commands added; `brain-scan`,
`brain-index`, `brain-lint`, `brain-check` targets added to the `Makefile`.

Vault: `.brain/` symlinked to `/Users/mrwen/second-brain/boutique-platform`. Verified that qmd
does **not** follow the symlink, so a dedicated collection is registered separately rather than
relying on the vault's `**/*.md` glob.

## [2026-07-23] ingest | Wave 0 — foundation, and Wave 1 partial (backend/)
Wrote 3 synthesis pages ([[Documented Stack Vs Actual Stack]], [[Repo Hazards]],
[[Frontend Scaffold Reality]]), 12 entity pages, and 9 concept pages including
[[Row Level Security]].

Wave 1 (backend/, 70 pages) was dispatched as 4 parallel batches but all four terminated on an
API session limit after writing 10 source pages: `backend/app/{__init__,main,cli,worker}.py`,
`backend/app/core/{__init__,config}.py`, `backend/app/auth/__init__.py`,
`backend/app/db/{rls,session}.py`, and `backend/tests/conftest.py`.

No state was corrupted — the pages *are* the checkpoint, so `brain-scan.sh --missing`
recomputed the remaining 340 from git with nothing to repair. Resume with `/brain-ingest`.

Verified this pass: drift detector (CURRENT → STALE → CURRENT, `touch` correctly does not flag,
`kind: generated` excluded), SessionStart baseline + JSON context injection, SessionEnd queue
writing and its degenerate cases, `make brain-check`, and `--lint` (0 broken links, 0 structural
failures).
