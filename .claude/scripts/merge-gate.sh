#!/usr/bin/env bash
# Merge gate for the MODRYN program loop.
#
# `main` has no branch protection, so this is the only thing between a red
# build and production. Exits 0 ONLY when every gating job has passed.
#
#   usage: merge-gate.sh <pr-number>
#   exit 0 = safe to merge · 1 = not safe · 2 = usage/tooling error
#
# Why a script and not "read the output": `gh pr checks` exits non-zero when
# ANY check fails, including the two warn-only jobs that are red on almost
# every PR. Judging that by eye is exactly the mistake that merges a red build.
#
# Keep this POSIX/bash-3.2 clean — macOS ships bash 3.2, where a bash-4-only
# expansion raises "bad substitution", skips the line that sets the failure
# flag, and makes the gate report PASS on a red build. Fails closed only if
# every branch below is portable.
set -uo pipefail

GATING_JOBS=(
  "Backend (lint, types, tests)"
  "Frontend (lint, types, build)"
  "Frontend E2E (Playwright + axe)"
)

pr="${1:-}"
[[ -z "$pr" ]] && { echo "usage: merge-gate.sh <pr-number>" >&2; exit 2; }

if [[ -n "${MERGE_GATE_FIXTURE:-}" ]]; then
  checks="$(cat "$MERGE_GATE_FIXTURE")"          # test hook
else
  checks="$(gh pr checks "$pr" --json name,bucket 2>/dev/null)"
fi
[[ -z "$checks" ]] && { echo "BLOCKED: no check data for PR #$pr" >&2; exit 1; }

verdict=0
for job in "${GATING_JOBS[@]}"; do
  bucket="$(printf '%s' "$checks" | jq -r --arg n "$job" '.[] | select(.name==$n) | .bucket' | head -1)"
  case "$bucket" in
    pass)    printf '  ok       %s\n' "$job" ;;
    "")      printf '  MISSING  %s\n' "$job"; verdict=1 ;;
    pending) printf '  PENDING  %s\n' "$job"; verdict=1 ;;
    *)       printf '  %-8s %s\n' "$bucket" "$job"; verdict=1 ;;
  esac
done

if [[ $verdict -eq 0 ]]; then
  echo "GATE PASS — PR #$pr may merge (warn-only jobs ignored by design)"
else
  echo "GATE BLOCKED — PR #$pr must NOT merge" >&2
fi
exit $verdict
