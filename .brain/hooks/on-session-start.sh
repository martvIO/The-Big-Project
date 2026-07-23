#!/usr/bin/env bash
# .brain SessionStart hook.
#
#  1. Writes the baseline that on-session-end.sh diffs against (SessionEnd has no
#     idea when the session started, so the start hook has to record it).
#  2. Runs brain-scan.sh and injects a capped summary of outstanding wiki work.
#
# Non-critical: any failure just means no injection. Always exits 0.
set -uo pipefail

PROJ="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)}"
Q="$PROJ/.brain/queue"
mkdir -p "$Q" 2>/dev/null || exit 0
cd "$PROJ" 2>/dev/null || exit 0

# 1. baseline for THIS session
git rev-parse HEAD > "$Q/baseline" 2>/dev/null || true
git status --porcelain=v1 > "$Q/baseline.status" 2>/dev/null || true

# 2. authoritative outstanding work — recomputed from git, never read from the queue
SUMMARY="$(bash "$PROJ/.brain/scripts/brain-scan.sh" --summary --max 12 2>/dev/null || true)"
[ -n "$SUMMARY" ] || exit 0

# recent-activity narrative (advisory only — the queue carries zero correctness weight)
if [ -s "$Q/pending.tsv" ]; then
  N="$(wc -l < "$Q/pending.tsv" 2>/dev/null | tr -d ' ')"
  SUMMARY="$SUMMARY
Recent session activity: .brain/queue/pending.tsv ($N entries)"
fi

CTX="$(printf '%s' "$SUMMARY" | head -c 2000)"

if command -v jq >/dev/null 2>&1; then
  printf '%s' "$CTX" | jq -Rs \
    '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:.}}' 2>/dev/null || true
else
  printf '%s\n' "$CTX"
fi
exit 0
