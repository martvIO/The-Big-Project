"""A citation in an exemption reason must be a line a reviewer can actually open.

`test_audit_coverage.py` and `test_cross_tenant_walker.py` each hold a list of
routes that deliberately do something a reviewer would otherwise flag — an
unaudited mutation, a 404 that is not evidence of a tenant check — and each
requires the reason to name where the decision lives in the shipped code.

⚠ BOTH ENFORCED ONLY THE SHAPE `\\w+/\\w+\\.py:\\d+` UNTIL THE 2026-08-05 ROUND-2
REVIEW. `totally/fake.py:999999` and `a/b.py:0` both satisfied that, while
`test_audit_coverage.py`'s own assertion message said "a rationale a reviewer
cannot open is prose, not a record". This module is that message, enforced: the
file exists under `app/`, and the line number is a line it actually has.

It does NOT check that the cited line says what the reason claims — no test can —
but a citation that has rotted past the end of its file, or into a file that was
renamed, now reds instead of reading as diligence.
"""

import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

# `floor/service.py:1193-1195` — a range is one citation with two endpoints, and
# both ends are checked.
CITATION = re.compile(r"(\w+/\w+\.py):(\d+)(?:-(\d+))?")


def assert_citations_open(reason: str, subject: object) -> int:
    """Check every `module/file.py:line` in `reason`. Returns how many it found,
    so a caller can also assert that there was at least one."""
    found = 0
    for match in CITATION.finditer(reason):
        relative, first, last = match.group(1), int(match.group(2)), match.group(3)
        path = APP_ROOT / relative
        assert path.exists(), (
            f"{subject} cites {match.group(0)}, but app/{relative} does not exist. "
            "A citation a reviewer cannot open is prose, not a record — repoint it."
        )
        total = len(path.read_text(encoding="utf-8").splitlines())
        for line in {first, int(last) if last is not None else first}:
            assert 1 <= line <= total, (
                f"{subject} cites {match.group(0)}, but app/{relative} has {total} "
                "lines. The decision moved or the file shrank — reread it and repoint "
                "the citation rather than leaving one that opens on nothing."
            )
        found += 1
    return found
