#!/usr/bin/env bash
# Single source of truth for the repo-path <-> page-path mapping.
# Never reimplement this anywhere else.
#
#   brain-page-path.sh backend/app/main.py
#     -> .brain/wiki/sources/backend/app/main.py.md
#   brain-page-path.sh --dir backend/app
#     -> .brain/wiki/sources/backend/app/_index.md
#   brain-page-path.sh --reverse .brain/wiki/sources/backend/app/main.py.md
#     -> backend/app/main.py
set -uo pipefail

PREFIX=".brain/wiki/sources"

usage() { printf 'usage: brain-page-path.sh [--dir|--reverse] <path>\n' >&2; exit 2; }

[ $# -ge 1 ] || usage

case "${1:-}" in
  --dir)
    [ $# -eq 2 ] || usage
    d="${2#./}"; d="${d%/}"
    if [ -z "$d" ] || [ "$d" = "." ]; then
      printf '%s/_index.md\n' "$PREFIX"
    else
      printf '%s/%s/_index.md\n' "$PREFIX" "$d"
    fi
    ;;
  --reverse)
    [ $# -eq 2 ] || usage
    p="${2#./}"
    p="${p#"$PREFIX"/}"
    case "$p" in
      */_index.md) printf '%s\n' "${p%/_index.md}" ;;
      _index.md)   printf '.\n' ;;
      *.md)        printf '%s\n' "${p%.md}" ;;
      *)           printf '%s\n' "$p" ;;
    esac
    ;;
  -*)
    usage
    ;;
  *)
    [ $# -eq 1 ] || usage
    f="${1#./}"
    printf '%s/%s.md\n' "$PREFIX" "$f"
    ;;
esac
