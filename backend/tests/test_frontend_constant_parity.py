"""Drift guard for the client/server constant mirror.

`frontend/apps/manage/src/validation.ts` restates a handful of bounds from
`app/catalog/validation.py` so the owner sees an immediate Hebrew error instead
of a round-trip 400. Nothing enforces that the two copies agree, and the failure
mode is silent: raise a cap on one side only and the console either rejects a
legal file or lets an illegal one reach S3 before the API refuses it.

The file is read as **text** on purpose — this test must run in the fast,
no-Docker, no-Node suite. A regex scrape is enough for literals.

The path is spelled lowercase (`frontend/...`) because git tracks it lowercase;
macOS resolves it case-insensitively and Linux CI checks it out that way.
"""

import datetime
import re
from pathlib import Path

from app.booking.validation import jerusalem_day_index
from app.catalog import validation

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_TS = REPO_ROOT / "frontend/apps/manage/src/validation.ts"

# The nine the spec names, plus the two validation.ts also declares AND enforces
# (MIN_UPLOAD_BYTES in validateUploadFile, MAX_SORT_ORDER in validateDress) —
# both are silent-drift cases of exactly the kind this test exists for: raise
# MIN_UPLOAD_BYTES on the server only and the console queues a file the API then
# refuses with a 400. Anything else in validation.ts (EU_SIZE_QUICK_LIST, the
# Hebrew messages) is frontend-only.
MIRRORED_CONSTANTS = (
    "MAX_DRESS_NAME_LENGTH",
    "MAX_DRESS_DESCRIPTION_LENGTH",
    "MAX_PRICE_AGOROT",
    "MAX_VARIANTS_PER_DRESS",
    "MAX_SIZE_LABEL_LENGTH",
    "MAX_VARIANT_QUANTITY",
    "MAX_MEDIA_PER_DRESS",
    "MAX_UPLOAD_BYTES",
    "MIN_UPLOAD_BYTES",
    "MAX_SEARCH_LENGTH",
    "MAX_SORT_ORDER",
)

_CONST_RE = re.compile(r"^export const (?P<name>[A-Z][A-Z0-9_]*)\s*=\s*(?P<value>[0-9_]+);", re.M)
_ACCEPTED_RE = re.compile(r"export const ACCEPTED_CONTENT_TYPES[^{]*\{(?P<body>[^}]*)\}", re.S)


def _source() -> str:
    assert VALIDATION_TS.is_file(), f"missing mirrored constants file: {VALIDATION_TS}"
    return VALIDATION_TS.read_text(encoding="utf-8")


def _numeric_constants(source: str) -> dict[str, int]:
    # TypeScript numeric separators (10_485_760) are legal and used on both sides.
    return {
        match.group("name"): int(match.group("value").replace("_", ""))
        for match in _CONST_RE.finditer(source)
    }


def test_every_mirrored_constant_is_declared_in_validation_ts() -> None:
    declared = _numeric_constants(_source())
    missing = [name for name in MIRRORED_CONSTANTS if name not in declared]
    assert missing == [], f"validation.ts does not export: {missing}"


def test_mirrored_numeric_constants_match_the_backend() -> None:
    declared = _numeric_constants(_source())
    frontend = {name: declared[name] for name in MIRRORED_CONSTANTS if name in declared}
    backend = {name: getattr(validation, name) for name in MIRRORED_CONSTANTS}
    assert frontend == backend


def test_accepted_content_type_keys_match_the_backend() -> None:
    match = _ACCEPTED_RE.search(_source())
    assert match is not None, "validation.ts does not export ACCEPTED_CONTENT_TYPES"
    keys = set(re.findall(r'"([^"]+)"\s*:', match.group("body")))
    assert keys == set(validation.ACCEPTED_CONTENT_TYPES)


# --- the Israeli week: backend conversion vs the UI's weekday map ---

HOURS_TS = REPO_ROOT / "frontend/packages/ui/src/lib/hours.ts"
_WEEKDAY_INDEX_RE = re.compile(
    r"const WEEKDAY_INDEX: Record<string, number> = \{(?P<body>[^}]*)\}", re.S
)
_WEEKDAY_ENTRY_RE = re.compile(r"(?P<name>[A-Za-z]{3})\s*:\s*(?P<index>\d)")

# datetime.weekday() order, Monday-first — the axis jerusalem_day_index converts
# FROM. Sunday's 0 is the whole point: availability_rules.day_of_week is the
# Israeli week, and a boutique whose Sunday rules render on Monday is a boutique
# with the wrong opening hours on every screen.
_ENGLISH_ABBREVIATIONS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def test_the_ui_weekday_map_matches_the_backend_israeli_week() -> None:
    """`packages/ui/src/lib/hours.ts` maps Intl weekday names to indices; the
    backend derives the same index arithmetically in
    `app.booking.validation.jerusalem_day_index`. Nothing else forces the two to
    agree, and disagreement is silent: the grid would render a boutique's Sunday
    hours on the wrong day, and the slot engine would materialize them there."""
    source = HOURS_TS.read_text(encoding="utf-8")
    match = _WEEKDAY_INDEX_RE.search(source)
    assert match is not None, f"WEEKDAY_INDEX not found in {HOURS_TS}"
    frontend = {
        entry.group("name"): int(entry.group("index"))
        for entry in _WEEKDAY_ENTRY_RE.finditer(match.group("body"))
    }
    assert len(frontend) == 7, f"expected seven weekdays, got {frontend}"

    # A real week, Monday-first, so the mapping is checked against dates rather
    # than against a restatement of the same formula.
    monday = datetime.date(2026, 1, 5)
    backend = {
        _ENGLISH_ABBREVIATIONS[offset]: jerusalem_day_index(
            monday + datetime.timedelta(days=offset)
        )
        for offset in range(7)
    }
    assert frontend == backend
