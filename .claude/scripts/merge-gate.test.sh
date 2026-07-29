#!/usr/bin/env bash
# Self-check for merge-gate.sh. Run: bash .claude/scripts/merge-gate.test.sh
set -uo pipefail
cd "$(dirname "$0")"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
fails=0

check() { # name expected_exit json
  printf '%s' "$3" > "$tmp/f.json"
  MERGE_GATE_FIXTURE="$tmp/f.json" bash ./merge-gate.sh 999 >/dev/null 2>&1
  local got=$?
  if [[ $got -eq $2 ]]; then echo "  ok   $1"; else echo "  FAIL $1 (want exit $2, got $got)"; fails=1; fi
}

GREEN='[{"name":"Backend (lint, types, tests)","bucket":"pass"},
        {"name":"Frontend (lint, types, build)","bucket":"pass"},
        {"name":"Frontend E2E (Playwright + axe)","bucket":"pass"}'

# the real-world shape: both warn-only jobs red, all gating jobs green
check "green + warn-only red merges"  0 "$GREEN,{\"name\":\"Dependency audits (warn-only)\",\"bucket\":\"fail\"},{\"name\":\"Code wiki drift (warn-only)\",\"bucket\":\"fail\"}]"
check "all green merges"              0 "$GREEN]"
check "gating failure blocks"         1 '[{"name":"Backend (lint, types, tests)","bucket":"fail"},{"name":"Frontend (lint, types, build)","bucket":"pass"},{"name":"Frontend E2E (Playwright + axe)","bucket":"pass"}]'
check "pending blocks"                1 '[{"name":"Backend (lint, types, tests)","bucket":"pending"},{"name":"Frontend (lint, types, build)","bucket":"pass"},{"name":"Frontend E2E (Playwright + axe)","bucket":"pass"}]'
check "missing e2e job blocks"        1 '[{"name":"Backend (lint, types, tests)","bucket":"pass"},{"name":"Frontend (lint, types, build)","bucket":"pass"}]'
check "empty check data blocks"       1 ''
check "skipped gating job blocks"     1 '[{"name":"Backend (lint, types, tests)","bucket":"skipping"},{"name":"Frontend (lint, types, build)","bucket":"pass"},{"name":"Frontend E2E (Playwright + axe)","bucket":"pass"}]'

[[ $fails -eq 0 ]] && echo "merge-gate: all checks passed" || { echo "merge-gate: FAILURES"; exit 1; }
