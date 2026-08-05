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

# F21 (PR #48) took "Dependency audits" off continue-on-error and renamed it off
# "(warn-only)", so it is a FOURTH gating job. These fixtures moved with it: the
# old ones named it as warn-only, and after the rename the gate correctly blocked
# them for a MISSING gating job — which is what caught this file needing an edit.
GREEN='[{"name":"Backend (lint, types, tests)","bucket":"pass"},
        {"name":"Frontend (lint, types, build)","bucket":"pass"},
        {"name":"Frontend E2E (Playwright + axe)","bucket":"pass"},
        {"name":"Dependency audits","bucket":"pass"}'

# the real-world shape: the one remaining warn-only job red, all gating jobs green
check "green + warn-only red merges"  0 "$GREEN,{\"name\":\"Code wiki drift (warn-only)\",\"bucket\":\"fail\"}]"
check "all green merges"              0 "$GREEN]"
check "gating failure blocks"         1 '[{"name":"Backend (lint, types, tests)","bucket":"fail"},{"name":"Frontend (lint, types, build)","bucket":"pass"},{"name":"Frontend E2E (Playwright + axe)","bucket":"pass"},{"name":"Dependency audits","bucket":"pass"}]'
check "pending blocks"                1 '[{"name":"Backend (lint, types, tests)","bucket":"pending"},{"name":"Frontend (lint, types, build)","bucket":"pass"},{"name":"Frontend E2E (Playwright + axe)","bucket":"pass"},{"name":"Dependency audits","bucket":"pass"}]'
check "missing e2e job blocks"        1 '[{"name":"Backend (lint, types, tests)","bucket":"pass"},{"name":"Frontend (lint, types, build)","bucket":"pass"},{"name":"Dependency audits","bucket":"pass"}]'
check "empty check data blocks"       1 ''
check "skipped gating job blocks"     1 '[{"name":"Backend (lint, types, tests)","bucket":"skipping"},{"name":"Frontend (lint, types, build)","bucket":"pass"},{"name":"Frontend E2E (Playwright + axe)","bucket":"pass"},{"name":"Dependency audits","bucket":"pass"}]'
# the new gate actually gates — a red audit must block, and a missing audit job
# must block, or the rename would have quietly demoted it back to a report
check "audit failure blocks"          1 '[{"name":"Backend (lint, types, tests)","bucket":"pass"},{"name":"Frontend (lint, types, build)","bucket":"pass"},{"name":"Frontend E2E (Playwright + axe)","bucket":"pass"},{"name":"Dependency audits","bucket":"fail"}]'
check "missing audit job blocks"      1 '[{"name":"Backend (lint, types, tests)","bucket":"pass"},{"name":"Frontend (lint, types, build)","bucket":"pass"},{"name":"Frontend E2E (Playwright + axe)","bucket":"pass"}]'
# the OLD name must not satisfy the gate — a revert of the ci.yml rename that left
# the job warn-only would otherwise pass silently
check "old warn-only name blocks"     1 '[{"name":"Backend (lint, types, tests)","bucket":"pass"},{"name":"Frontend (lint, types, build)","bucket":"pass"},{"name":"Frontend E2E (Playwright + axe)","bucket":"pass"},{"name":"Dependency audits (warn-only)","bucket":"pass"}]'

[[ $fails -eq 0 ]] && echo "merge-gate: all checks passed" || { echo "merge-gate: FAILURES"; exit 1; }
