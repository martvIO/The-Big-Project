"""Drift guard for the client/server constant mirror.

Two frontend files restate backend bounds so the user sees an immediate Hebrew
error instead of a round-trip 400: `frontend/apps/manage/src/validation.ts`
mirrors `app/catalog/validation.py`, `app/auth/schemas.py` **and
`app/customers/validation.py`**, and `frontend/apps/storefront/src/validation.ts`
mirrors `app/booking/validation.py`. Nothing enforces that the copies agree, and the
failure mode is silent: raise a cap on one side only and the client either
rejects a legal value or lets an illegal one reach the API before it refuses.

The staff row is additionally load-bearing for F51's plan C6: the staff forms
render one field-local Hebrew message for the single 400 the server can answer
them (a wrong `current_password`), and that is only honest because every OTHER
400 those forms could produce is caught client-side first. Three of the four
guards are the mirrored bounds below and this test is what keeps them in step;
the fourth is `validateStaffDraft`'s email shape check, which mirrors no
constant — `EmailStr` is an algorithm, not a number — and is pinned instead by
`validation.test.ts` against the addresses verified here to round-trip. The
2026-07-30 review found that fourth guard missing, which had made this
paragraph's claim false.

The files are read as **text** on purpose — this test must run in the fast,
no-Docker, no-Node suite. A regex scrape is enough for literals.

The paths are spelled lowercase (`frontend/...`) because git tracks them
lowercase; macOS resolves them case-insensitively and Linux CI checks them out
that way.
"""

import datetime
import re
from pathlib import Path
from types import ModuleType

import pytest

from app.auth import schemas as auth_schemas
from app.booking import validation as booking_validation
from app.booking.validation import jerusalem_day_index
from app.catalog import validation as catalog_validation
from app.customers import validation as customers_validation
from app.floor import validation as floor_validation

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGE_VALIDATION_TS = REPO_ROOT / "frontend/apps/manage/src/validation.ts"
STOREFRONT_VALIDATION_TS = REPO_ROOT / "frontend/apps/storefront/src/validation.ts"

# manage: the nine the F8 spec names, plus the two validation.ts also declares
# AND enforces (MIN_UPLOAD_BYTES in validateUploadFile, MAX_SORT_ORDER in
# validateDress) — both are silent-drift cases of exactly the kind this test
# exists for: raise MIN_UPLOAD_BYTES on the server only and the console queues
# a file the API then refuses with a 400. storefront: the two bounds F14's
# booking form enforces client-side (D7). Anything else in either file
# (EU_SIZE_QUICK_LIST, normalizePhone, the Hebrew messages) is frontend-only.
MIRRORS = (
    pytest.param(
        MANAGE_VALIDATION_TS,
        catalog_validation,
        (
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
        ),
        id="manage",
    ),
    pytest.param(
        MANAGE_VALIDATION_TS,
        auth_schemas,
        (
            "MIN_STAFF_PASSWORD_LENGTH",
            "MAX_PASSWORD_LENGTH",
            "MAX_DISPLAY_NAME_LENGTH",
        ),
        id="manage-staff",
    ),
    # F53's four. MAX_SEARCH_TERM_LENGTH is the one a reader would call
    # server-only: it is not a write bound at all, it is `Query(max_length=…)` on
    # the list route. It rides here because the console applies it as `maxLength`
    # on the search box, and without that mirror a pasted over-long term answers
    # 400, the catch sets loadError, and the list renders «אפשר לנסות שוב בעוד
    # רגע» — a wait-and-retry message for an input error that fails identically
    # on every retry.
    pytest.param(
        MANAGE_VALIDATION_TS,
        customers_validation,
        (
            "MAX_TAG_LENGTH",
            "MAX_TAGS",
            "MAX_CUSTOMER_NOTES_LENGTH",
            "MAX_SEARCH_TERM_LENGTH",
        ),
        id="manage-customers",
    ),
    # F36's one. The registry dialog caps its label input at this length, so
    # without the mirror an owner types a 41st character, the row saves, the API
    # answers a house 400 carrying an ENGLISH message, and the Hebrew dialog
    # renders it — for an input error that fails identically on every retry.
    pytest.param(
        MANAGE_VALIDATION_TS,
        floor_validation,
        ("MAX_ROOM_LABEL_LENGTH", "MAX_SOS_NOTE_LENGTH"),
        id="manage-floor",
    ),
    pytest.param(
        STOREFRONT_VALIDATION_TS,
        booking_validation,
        (
            "MAX_CUSTOMER_NAME_LENGTH",
            "MAX_BOOKING_NOTES_LENGTH",
        ),
        id="storefront",
    ),
)

_CONST_RE = re.compile(r"^export const (?P<name>[A-Z][A-Z0-9_]*)\s*=\s*(?P<value>[0-9_]+);", re.M)
_ACCEPTED_RE = re.compile(r"export const ACCEPTED_CONTENT_TYPES[^{]*\{(?P<body>[^}]*)\}", re.S)


def _source(path: Path) -> str:
    assert path.is_file(), f"missing mirrored constants file: {path}"
    return path.read_text(encoding="utf-8")


def _numeric_constants(source: str) -> dict[str, int]:
    # TypeScript numeric separators (10_485_760) are legal and used on both sides.
    return {
        match.group("name"): int(match.group("value").replace("_", ""))
        for match in _CONST_RE.finditer(source)
    }


@pytest.mark.parametrize(("path", "backend", "names"), MIRRORS)
def test_every_mirrored_constant_is_declared_in_validation_ts(
    path: Path, backend: ModuleType, names: tuple[str, ...]
) -> None:
    declared = _numeric_constants(_source(path))
    missing = [name for name in names if name not in declared]
    assert missing == [], f"{path} does not export: {missing}"


@pytest.mark.parametrize(("path", "backend", "names"), MIRRORS)
def test_mirrored_numeric_constants_match_the_backend(
    path: Path, backend: ModuleType, names: tuple[str, ...]
) -> None:
    declared = _numeric_constants(_source(path))
    frontend = {name: declared[name] for name in names if name in declared}
    backend_values = {name: getattr(backend, name) for name in names}
    assert frontend == backend_values


_TS_REGEX_RE = re.compile(r"^const (?P<name>[A-Z][A-Z0-9_]*)\s*=\s*/(?P<body>.+)/;", re.M)

# The character classes are literals on both sides, so the pattern bodies compare
# byte-for-byte. They earn a guard of their own because the failure they prevent is
# the worst kind this file exists for: a control character (a U+000B soft break
# pasted from Word) passes a client that only checks blank-and-length, so the bride
# spends a real SMS, accepts the policy, submits, and receives a 400 she can neither
# understand nor escape — every retry fails identically.
_MIRRORED_PATTERNS = (
    ("CONTROL_CHARS", "_CONTROL_CHARS"),
    ("CONTROL_CHARS_EXCEPT_WS", "_CONTROL_CHARS_EXCEPT_WS"),
)


# Both consoles now carry the pair: the storefront for the booking form, the
# manage console for a customer's notes and tags. `app/customers/validation.py`
# imports the two classes straight out of `app/booking/validation.py` rather than
# restating them, so one backend module is still the single authority for both
# rows here.
@pytest.mark.parametrize("path", (STOREFRONT_VALIDATION_TS, MANAGE_VALIDATION_TS))
def test_control_character_classes_match_the_backend(path: Path) -> None:
    declared = {
        match.group("name"): match.group("body") for match in _TS_REGEX_RE.finditer(_source(path))
    }
    for ts_name, py_name in _MIRRORED_PATTERNS:
        # Names the file under test: the message used to say "storefront"
        # unconditionally, which sent a manage failure to the wrong file.
        assert ts_name in declared, f"{path.name} in {path.parent} does not declare {ts_name}"
        assert declared[ts_name] == getattr(booking_validation, py_name).pattern


def test_accepted_content_type_keys_match_the_backend() -> None:
    match = _ACCEPTED_RE.search(_source(MANAGE_VALIDATION_TS))
    assert match is not None, "validation.ts does not export ACCEPTED_CONTENT_TYPES"
    keys = set(re.findall(r'"([^"]+)"\s*:', match.group("body")))
    assert keys == set(catalog_validation.ACCEPTED_CONTENT_TYPES)


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
