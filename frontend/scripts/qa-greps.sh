#!/usr/bin/env bash
# qa-checklist.md §11 mechanical checks.
#
# Every one of these must find NOTHING. They exist because each is a rule that a
# reviewer reliably fails to notice: the storefront ships no nav component, no
# favorites, no history-based back navigation, no hand-formatted money, and no
# physical direction properties (the whole product is RTL and uses CSS logical
# properties throughout).
#
# Uses §11's nav pattern deliberately, NOT §10's. §10's variant appends
# `aria-expanded`, and DescriptionClamp is a disclosure widget that MUST carry
# aria-expanded to satisfy §8. The two sections disagree; §11 is the mechanical
# list and is the one that runs.
set -uo pipefail

cd "$(dirname "$0")/.."
SRC="apps/storefront/src"
status=0

check() {
  local label="$1" pattern="$2" path="$3"
  local hits
  hits=$(grep -rnE "$pattern" "$path" 2>/dev/null || true)
  if [ -n "$hits" ]; then
    printf '\033[31mFAIL\033[0m  %s\n%s\n\n' "$label" "$hits"
    status=1
  else
    printf '\033[32m ok \033[0m  %s\n' "$label"
  fi
}

check "no nav component"            'hamburger|drawer|nav-?toggle|mega-?nav' "$SRC"
check "no favorites"                'favorit|localStorage|heart'             "$SRC"
check "no history-based back"       'history\.back|navigate\(-1\)|router\.back' "$SRC"
check "no empty fragment hrefs"     'href="#"'                               "$SRC"
# Money renders through <Price> and nowhere else.
check "no hand-formatted shekels"   '₪'                                      "$SRC"
# Physical INLINE direction only — block-direction utilities (mt-, mb-, pt-, pb-)
# are direction-agnostic and legitimate.
check "no physical direction props" '[^a-zA-Z-](ml-|mr-|pl-|pr-|left-|right-|text-left|text-right|border-l-|border-r-)' "$SRC"
# Colour lives in theme.css as tokens; a hex anywhere else bypasses the system.
check "no raw hex colours"          '#[0-9a-fA-F]{6}\b'                      "$SRC"

# Dates must be read in an explicit zone. lib/hours.ts owns the zoned helpers;
# a bare getDay()/toLocaleDateString() reads the DEVICE clock, which is a
# different calendar day from Jerusalem for part of every day.
printf '\n'
zoned=$(grep -rnE 'getDay\(\)|getDate\(\)|toLocaleDateString|toLocaleTimeString' \
  apps/storefront/src apps/manage/src packages/ui/src 2>/dev/null || true)
if [ -n "$zoned" ]; then
  printf '\033[33mreview\033[0m  date reads — each must be explicitly zoned:\n%s\n' "$zoned"
else
  printf '\033[32m ok \033[0m  no unzoned date reads\n'
fi

exit $status
