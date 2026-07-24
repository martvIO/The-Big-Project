#!/usr/bin/env bash
# .brain SessionEnd hook — async, best-effort, NON-BLOCKING.
#
# Records which tracked files changed during this session into an append-only queue.
# SessionEnd cannot run a Claude turn, so this only writes the queue; the actual wiki
# reconciliation happens at the start of the next session (see on-session-start.sh)
# or on demand via /brain-sync.
#
# It must never fail the session or spend API budget. Every path exits 0.
set -uo pipefail

PROJ="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null && pwd)}"
Q="$PROJ/.brain/queue"
mkdir -p "$Q" 2>/dev/null || exit 0
cd "$PROJ" 2>/dev/null || exit 0

TS="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)" || exit 0
BASE="$(head -n1 "$Q/baseline" 2>/dev/null || true)"
HEAD_NOW="$(git rev-parse HEAD 2>/dev/null || true)"

TMP="$(mktemp 2>/dev/null)" || exit 0

{
  # committed during the session
  if [ -n "$BASE" ] && [ -n "$HEAD_NOW" ] && [ "$BASE" != "$HEAD_NOW" ]; then
    git diff --name-only "$BASE".."$HEAD_NOW" 2>/dev/null || true
  fi
  # working-tree paths not present in the baseline snapshot
  if [ -f "$Q/baseline.status" ]; then
    git status --porcelain=v1 2>/dev/null | sed 's/^...//; s/^.* -> //' \
      | grep -Fxv -f <(sed 's/^...//; s/^.* -> //' "$Q/baseline.status" 2>/dev/null) 2>/dev/null || true
  else
    git status --porcelain=v1 2>/dev/null | sed 's/^...//; s/^.* -> //' || true
  fi
} 2>/dev/null | grep -v '^\.brain/' | sort -u > "$TMP" 2>/dev/null || true

while IFS= read -r p; do
  [ -n "$p" ] || continue
  if [ -L "$p" ]; then
    h="$(printf '%s' "$(readlink "$p" 2>/dev/null)" | git hash-object --stdin 2>/dev/null || echo unknown)"
  elif [ -f "$p" ]; then
    h="$(git hash-object "$p" 2>/dev/null || echo unknown)"
  else
    h="deleted"
  fi
  printf '%s\t%s\t%s\n' "$TS" "$p" "$h"
done < "$TMP" >> "$Q/pending.tsv" 2>/dev/null || true

rm -f "$TMP" 2>/dev/null || true
exit 0
