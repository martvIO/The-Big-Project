---
tags: []
sources: [<DIR>]
created: <DATE>
updated: <DATE>
# --- .brain extensions (see .brain/CLAUDE.md § Deviations) ---
path: <DIR>
blob: <GIT_LS_FILES_S_DIR_SHASUM>
commit: <GIT_HEAD>
kind: directory
applicability: active
---

# <DIR>/

**Purpose.** One sentence: what this module is responsible for.

**Parent.** [[<PARENT_DIR>/_index]]

## Files

- [[<DIR>/thing.py]] — one-line summary
- [[<DIR>/other.py]] — one-line summary

## Subdirectories

- [[<DIR>/sub/_index]] — one-line summary

## Concepts

- [[Concept Name]]

<!--
blob for a directory page = `git ls-files -s <DIR> | shasum | cut -c1-40`
so that adding or removing a file in the directory marks this page stale.
Written by the orchestrator at the end of a wave, never by a batch subagent.
-->
