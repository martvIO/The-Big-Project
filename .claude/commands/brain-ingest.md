---
name: brain-ingest
description: Batch-generate .brain wiki pages for a directory of tracked repo files. One confirmation per batch, not per file. Use when brain-scan reports missing pages, or to build out a new wave.
---

# /brain-ingest [directory]

Generate `.brain/wiki/sources/` pages for tracked files that don't have one yet.

This deliberately forks `/second-brain-ingest`. That skill's step 2 ("share the 3-5 most
important takeaways… **Wait for confirmation before proceeding**") sits inside a *per-source*
loop — at 350 sources that is 350 confirmations, and it has no bulk mode. This command keeps
the skill's **output contract** (frontmatter, wikilinks, index, log) and replaces only its
**control flow**: one confirmation per batch. Recorded in `.brain/CLAUDE.md` § Deviations item 8.

Read `.brain/CLAUDE.md` before writing anything.

## 1. Scope the batch

```bash
bash .brain/scripts/brain-scan.sh --missing --max 0 | grep "^<directory>/"
```

A batch is **one directory, at most 15 files**. If the directory has more, split by
subdirectory or by natural grouping and do them as separate batches.

## 2. One confirmation, up front

Show the user the batch as a table: file, chosen `kind`, chosen `applicability`, and the
proposed tag set. Then proceed through every file without stopping again.

Choose `kind` by what the file *is*:

| Files | `kind` | `applicability` | Template |
|---|---|---|---|
| `.py` `.ts` `.tsx` `.sh` `.zsh` `.mako` | `code` | `active` | `page-code.md` |
| `.md` in `.planning/` `.memory/`, `README.md` | `doc` | `active` | `page-doc.md` |
| `.toml` `.json` `.yml` `.ini` `.css` `.html` `.gitignore` etc. | `config` | `active` | `page-code.md`, trimmed |
| `uv.lock`, `pnpm-lock.yaml` | `generated` | `n/a` | `page-generated.md` |
| anything under `.claude/` or `.agents/` | `vendored` | see below | `page-vendored.md` |
| git mode `120000` (`git ls-files -s \| awk '$1=="120000"'`) | `symlink` | `active` | `page-symlink.md` |

For `vendored`: set `applicability: vendored-inapplicable` and carry the banner when the file
targets a stack this repo does not use (Kotlin/Micronaut, Exposed ORM, Next.js, Terraform).
Set `applicability: active` and drop the banner when it genuinely applies (core rules, product
and ops commands, the second-brain skills). `kind` stays `vendored` either way — it marks
provenance, not applicability.

## 3. Write the pages

For every file, before writing its page:

```bash
git hash-object <path>     # -> blob:     (for a symlink: printf '%s' "$(readlink <path>)" | git hash-object --stdin)
git rev-parse HEAD         # -> commit:
bash .brain/scripts/brain-page-path.sh <path>   # -> where the page goes
```

Then read the file and fill the template. Quality bar:

- **`Role` / `Purpose` must be specific.** "Handles authentication" is useless; "verifies owner
  credentials against `staff_users`, issues a session cookie, and rate-limits by IP" is useful.
- **Links must be real.** Every `[[path]]` must correspond to a tracked file. Every third-party
  tool gets `[[Entity Name]]`; create the entity page under `wiki/entities/` if missing.
- **No line numbers, ever.** Cite symbols by name.
- **Vendored pages stay ~12 lines.** Read them with `head -60` plus frontmatter — the template
  only needs one or two sentences of "what it says". This is the main cost control.

Parallelize with subagents (3–4 concurrent, one per batch). **Subagents write leaf pages only.**

## 4. Orchestrator-only steps (never delegate these)

After the batch — or after the whole wave — the orchestrator, and only the orchestrator:

1. Writes each affected directory's `_index.md` (needs every leaf page to exist first).
   `blob` for a directory page is `git ls-files -s <dir> | shasum | cut -c1-40`.
2. Regenerates the index: `bash .brain/scripts/brain-index.sh`
3. Appends exactly one entry to `.brain/wiki/log.md`:
   ```
   ## [YYYY-MM-DD] ingest | Wave 1 — backend/ (70 pages)
   Created 70 source pages and 9 directory pages. New concepts: [[Row Level Security]], …
   ```
4. Verifies: `bash .brain/scripts/brain-scan.sh --summary` and `--lint`.

`wiki/index.md`, `wiki/log.md`, and every `_index.md` are the shared-mutable state. Keeping them
orchestrator-owned is what makes parallel leaf writes safe.

## Resume

There is no progress file. The pages **are** the checkpoint — `brain-scan.sh --missing`
recomputes what is left from the filesystem and git on every run. An interruption loses at most
the in-flight batch. Just re-run this command.
