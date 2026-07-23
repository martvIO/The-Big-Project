#!/usr/bin/env bash
# brain-scan.sh — the single source of truth for .brain wiki coverage and drift.
#
# Recomputes everything from the filesystem + git on every run. There is no progress
# file, no lockfile, and nothing that can desync. Used by the SessionStart hook,
# /brain-sync, the Makefile, and CI.
#
#   MISSING  tracked file with no page
#   STALE    page exists but frontmatter blob != current blob of the file
#   ORPHAN   page under wiki/sources whose path is no longer tracked
#
# Modes:
#   --summary          counts + capped lists (default)
#   --missing          list missing paths only
#   --stale            list stale paths only
#   --orphan           list orphan page paths only
#   --lint             structural checks on every page
#   --check            exit 1 if anything is stale or orphaned (for CI)
#   --all              include kind:generated and applicability:vendored-inapplicable
#   --max N            cap list output (default 15; 0 = unlimited)
#   <path>...          report status for specific repo paths
set -uo pipefail

REPO="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "not a git repo" >&2; exit 2; }
cd "$REPO" || exit 2

PREFIX=".brain/wiki/sources"
MODE="summary"; MAX=15; INCLUDE_ALL=0; PATHS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --summary|--missing|--stale|--orphan|--lint|--check) MODE="${1#--}" ;;
    --all)  INCLUDE_ALL=1 ;;
    --max)  shift; MAX="${1:-15}" ;;
    -*)     echo "unknown flag: $1" >&2; exit 2 ;;
    *)      PATHS+=("$1") ;;
  esac
  shift
done

TMP="$(mktemp -d)" || exit 2
trap 'rm -rf "$TMP"' EXIT

# ---------------------------------------------------------------- current blobs
# Index blobs first (correct for symlinks, which git stores as the target string).
# .brain/ is excluded from its own corpus — the wiki does not document itself.
git ls-files -s 2>/dev/null | sed 's/^[0-7]* \([0-9a-f]*\) [0-3]\t/\1\t/' \
  | awk -F'\t' '$2 !~ /^\.brain\// {print $2"\t"$1}' > "$TMP/blobs"

# Override with working-tree blobs for anything that differs from the index.
git diff --name-only 2>/dev/null | while IFS= read -r p; do
  [ -n "$p" ] || continue
  if [ -L "$p" ]; then
    h="$(printf '%s' "$(readlink "$p")" | git hash-object --stdin 2>/dev/null)"
  elif [ -f "$p" ]; then
    h="$(git hash-object "$p" 2>/dev/null)"
  else
    h="deleted"
  fi
  printf '%s\t%s\n' "$p" "$h"
done > "$TMP/dirty"

if [ -s "$TMP/dirty" ]; then
  awk -F'\t' 'NR==FNR{d[$1]=$2; next} {print $1"\t"($1 in d ? d[$1] : $2)}' \
    "$TMP/dirty" "$TMP/blobs" > "$TMP/blobs.new" && mv "$TMP/blobs.new" "$TMP/blobs"
fi

# ---------------------------------------------------------------- page metadata
# One awk pass over every page: file <TAB> blob <TAB> kind <TAB> applicability
find "$PREFIX" -name '*.md' -type f 2>/dev/null | sort > "$TMP/pagelist"
if [ -s "$TMP/pagelist" ]; then
  # shellcheck disable=SC2046
  awk '
    function flush() { if (cur != "") printf "%s\t%s\t%s\t%s\n", cur, blob, kind, app }
    FNR==1 { flush(); cur=FILENAME; blob=""; kind=""; app=""; infm=0; done=0 }
    done { next }
    FNR==1 && $0=="---" { infm=1; next }
    infm && $0=="---" { done=1; next }
    infm {
      i=index($0,":"); if (i<1) next
      k=substr($0,1,i-1); v=substr($0,i+1)
      gsub(/^[ \t]+|[ \t]+$/,"",k); gsub(/^[ \t]+|[ \t]+$/,"",v)
      if (k=="blob") blob=v; else if (k=="kind") kind=v; else if (k=="applicability") app=v
    }
    END { flush() }
  ' $(cat "$TMP/pagelist") > "$TMP/pages" 2>/dev/null
else
  : > "$TMP/pages"
fi

# ---------------------------------------------------------------- classification
: > "$TMP/missing"; : > "$TMP/stale"; : > "$TMP/orphan"

while IFS="$(printf '\t')" read -r p blob; do
  [ -n "$p" ] || continue
  page="$PREFIX/$p.md"
  if [ ! -f "$page" ]; then
    printf '%s\n' "$p" >> "$TMP/missing"
    continue
  fi
  meta="$(awk -F'\t' -v f="$page" '$1==f {print $2"\t"$3"\t"$4; exit}' "$TMP/pages")"
  pblob="$(printf '%s' "$meta" | cut -f1)"
  pkind="$(printf '%s' "$meta" | cut -f2)"
  papp="$(printf '%s' "$meta" | cut -f3)"
  if [ "$INCLUDE_ALL" -eq 0 ]; then
    [ "$pkind" = "generated" ] && continue
    [ "$papp" = "vendored-inapplicable" ] && continue
  fi
  [ "$pblob" = "$blob" ] || printf '%s\n' "$p" >> "$TMP/stale"
done < "$TMP/blobs"

cut -f1 "$TMP/blobs" | sort > "$TMP/tracked.sorted"
while IFS= read -r page; do
  case "$page" in */_index.md) continue ;; esac
  rel="${page#"$PREFIX"/}"; rel="${rel%.md}"
  grep -Fxq "$rel" "$TMP/tracked.sorted" || printf '%s\n' "$page" >> "$TMP/orphan"
done < "$TMP/pagelist"

n_tracked=$(wc -l < "$TMP/blobs" | tr -d ' ')
n_pages=$(grep -cv '/_index\.md$' "$TMP/pagelist" 2>/dev/null) || true
n_pages=${n_pages:-0}
n_missing=$(wc -l < "$TMP/missing" | tr -d ' ')
n_stale=$(wc -l < "$TMP/stale" | tr -d ' ')
n_orphan=$(wc -l < "$TMP/orphan" | tr -d ' ')

cap() { if [ "$MAX" -eq 0 ]; then cat; else head -n "$MAX"; fi; }

# Title Case topic name -> kebab-case page filename stem.
slug() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-'; }

# ---------------------------------------------------------------- specific paths
if [ ${#PATHS[@]} -gt 0 ]; then
  rc=0
  for p in "${PATHS[@]}"; do
    p="${p#./}"
    if grep -Fxq "$p" "$TMP/missing" 2>/dev/null; then printf 'MISSING  %s\n' "$p"; rc=1
    elif grep -Fxq "$p" "$TMP/stale" 2>/dev/null; then printf 'STALE    %s\n' "$p"; rc=1
    elif grep -q "^$(printf '%s' "$p" | sed 's/[][\.*^$/]/\\&/g')	" "$TMP/blobs" 2>/dev/null; then
      printf 'CURRENT  %s\n' "$p"
    else printf 'UNTRACKED %s\n' "$p"; fi
  done
  exit $rc
fi

case "$MODE" in
  missing) cap < "$TMP/missing" ;;
  stale)   cap < "$TMP/stale" ;;
  orphan)  cap < "$TMP/orphan" ;;
  check)
    if [ "$n_stale" -gt 0 ] || [ "$n_orphan" -gt 0 ]; then
      printf '[.brain] FAIL — %s stale, %s orphan\n' "$n_stale" "$n_orphan"
      sed 's/^/  stale:  /' "$TMP/stale"; sed 's/^/  orphan: /' "$TMP/orphan"
      exit 1
    fi
    printf '[.brain] OK — %s/%s pages current, %s missing\n' "$n_pages" "$n_tracked" "$n_missing"
    ;;
  lint)
    rc=0
    while IFS= read -r page; do
      rel="$(bash .brain/scripts/brain-page-path.sh --reverse "$page")"
      meta="$(awk -F'\t' -v f="$page" '$1==f {print $2"\t"$3"\t"$4; exit}' "$TMP/pages")"
      b="$(printf '%s' "$meta" | cut -f1)"; k="$(printf '%s' "$meta" | cut -f2)"
      [ -n "$k" ] || { printf 'LINT no-kind        %s\n' "$page"; rc=1; }
      case "$page" in
        */_index.md) ;;
        *) if ! printf '%s' "$b" | grep -Eq '^[0-9a-f]{40}$'; then
             printf 'LINT bad-blob       %s\n' "$page"; rc=1; fi ;;
      esac
      grep -q "^path: $(printf '%s' "$rel" | sed 's/[][\.*^$/]/\\&/g')$" "$page" 2>/dev/null \
        || { printf 'LINT path-mismatch  %s\n' "$page"; rc=1; }
    done < "$TMP/pagelist"
    # Wikilink classification.
    #   BROKEN  — points at a path that is not a tracked file. A real defect.
    #   PENDING — points at a tracked file whose page is not built yet. Expected
    #             while waves are still running; informational, never fails.
    #   TOPIC   — Title-Case concept/entity link with no page yet. Informational.
    grep -roh '\[\[[^]]*\]\]' .brain/wiki 2>/dev/null \
      | sed 's/^\[\[//; s/\]\]$//; s/#.*$//; s/|.*$//' | sort -u \
    | while IFS= read -r t; do
        [ -n "$t" ] || continue
        case "$t" in */_index) continue ;; esac
        if [ -f "$PREFIX/$t.md" ]; then continue; fi
        if grep -Fxq "$t" "$TMP/tracked.sorted" 2>/dev/null; then
          printf 'PENDING page-not-built  [[%s]]\n' "$t"
        elif printf '%s' "$t" | grep -q '[/.]'; then
          printf 'BROKEN  not-a-file      [[%s]]\n' "$t"
        elif [ -f ".brain/wiki/concepts/$(slug "$t").md" ] \
          || [ -f ".brain/wiki/entities/$(slug "$t").md" ] \
          || [ -f ".brain/wiki/synthesis/$(slug "$t").md" ]; then
          continue
        else
          printf 'TOPIC   no-page-yet     [[%s]]\n' "$t"
        fi
      done
    exit $rc
    ;;
  summary|*)
    printf '[.brain] %s tracked files · %s pages · %s stale · %s missing · %s orphan\n' \
      "$n_tracked" "$n_pages" "$n_stale" "$n_missing" "$n_orphan"
    if [ "$n_stale" -gt 0 ]; then
      printf 'Stale (page no longer matches the file):\n'
      cap < "$TMP/stale" | sed 's/^/  /'
      [ "$MAX" -ne 0 ] && [ "$n_stale" -gt "$MAX" ] && printf '  … and %s more\n' "$((n_stale-MAX))"
    fi
    if [ "$n_orphan" -gt 0 ]; then
      printf 'Orphan pages (file no longer tracked):\n'
      cap < "$TMP/orphan" | sed 's/^/  /'
    fi
    if [ "$n_missing" -gt 0 ]; then
      printf 'Missing: %s tracked files have no page yet.\n' "$n_missing"
    fi
    if [ "$n_stale" -gt 0 ] || [ "$n_orphan" -gt 0 ]; then
      printf 'Run /brain-sync to reconcile. Do not reconcile inline during unrelated work.\n'
    fi
    ;;
esac
