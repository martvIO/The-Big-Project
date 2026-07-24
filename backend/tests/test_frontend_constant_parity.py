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

import re
from pathlib import Path

from app.catalog import validation

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_TS = REPO_ROOT / "frontend/apps/manage/src/validation.ts"

# Exactly the constants the spec names as mirrored. Anything else in
# validation.ts (EU_SIZE_QUICK_LIST, the Hebrew messages) is frontend-only.
MIRRORED_CONSTANTS = (
    "MAX_DRESS_NAME_LENGTH",
    "MAX_DRESS_DESCRIPTION_LENGTH",
    "MAX_PRICE_AGOROT",
    "MAX_VARIANTS_PER_DRESS",
    "MAX_SIZE_LABEL_LENGTH",
    "MAX_VARIANT_QUANTITY",
    "MAX_MEDIA_PER_DRESS",
    "MAX_UPLOAD_BYTES",
    "MAX_SEARCH_LENGTH",
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
