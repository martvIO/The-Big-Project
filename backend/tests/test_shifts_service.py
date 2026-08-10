"""F39's service rules that are TOTAL FUNCTIONS — the material-edit predicate,
D3's auto-label, and (C2) the self-or-elevated matrix and D11's diff.

Fast lane: no database. Everything that needs one lives in `test_shifts_db.py`.
"""

import datetime

import pytest

from app.models.constants import StaffRole
from app.shifts.service import (
    ELEVATED_ROLES,
    HEBREW_DAY_NAMES,
    MATERIAL_FIELDS,
    is_material_edit,
    seed_label,
)


def _fields(
    day_of_week: int = 4,
    starts: datetime.time = datetime.time(9, 0),
    ends: datetime.time = datetime.time(14, 0),
) -> dict[str, object]:
    return {"day_of_week": day_of_week, "starts_at_time": starts, "ends_at_time": ends}


def test_an_unchanged_template_is_not_a_material_edit() -> None:
    assert is_material_edit(before=_fields(), after=_fields()) is False


@pytest.mark.parametrize(
    "after",
    [
        _fields(day_of_week=2),
        _fields(starts=datetime.time(10, 0)),
        _fields(ends=datetime.time(21, 0)),
    ],
    ids=["day", "start", "end"],
)
def test_moving_any_of_the_three_material_fields_invalidates(after: dict[str, object]) -> None:
    """D4: a staffer who answered "available, Thursday morning" must not end up
    holding an answer to "available, Thursday NIGHT" that she never gave, on a
    surface whose entire content is what she said."""
    assert is_material_edit(before=_fields(), after=after) is True


def test_label_and_sort_order_are_not_material_fields() -> None:
    """⚠ ASSERTED ON THE CONSTANT, not by calling the predicate with a label —
    `is_material_edit` reads only `MATERIAL_FIELDS`, so a label passed in would
    be ignored and the test would pass for the wrong reason. Renaming «משמרת
    בוקר» to «בוקר» changes nothing anybody answered, and invalidating on it
    would make the owner's typo fix cost other people's answers."""
    assert set(MATERIAL_FIELDS) == {"day_of_week", "starts_at_time", "ends_at_time"}
    assert "label" not in MATERIAL_FIELDS
    assert "sort_order" not in MATERIAL_FIELDS


def test_the_seed_label_names_the_day_and_the_range() -> None:
    """D3's «ראשון 09:00–17:00». An EN DASH, matching every other time range in
    the product, and zero-padded on both ends."""
    assert (
        seed_label(
            day_of_week=0, starts_at_time=datetime.time(9, 0), ends_at_time=datetime.time(17, 0)
        )
        == "ראשון 09:00–17:00"
    )
    assert (
        seed_label(
            day_of_week=4, starts_at_time=datetime.time(16, 0), ends_at_time=datetime.time(21, 30)
        )
        == "חמישי 16:00–21:30"
    )


def test_the_day_names_are_seven_and_start_on_sunday() -> None:
    """Indexed 0=Sunday, `availability_rules.day_of_week`'s encoding and the same
    seven words `apps/manage/src/lib/week.ts` renders."""
    assert len(HEBREW_DAY_NAMES) == 7
    assert HEBREW_DAY_NAMES[0] == "ראשון"
    assert HEBREW_DAY_NAMES[6] == "שבת"


def test_exactly_the_two_elevated_roles_are_elevated() -> None:
    """⚠ SPELLED FROM THE ENUM, so a sixth `StaffRole` is NOT elevated by
    default — the safe direction to fail. Nothing in F39 enters `OWNER_ONLY`: a
    shift manager is admitted everywhere here, and D5's on-behalf write is hers
    as much as the owner's."""
    assert set(ELEVATED_ROLES) == {StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value}
    for role in (StaffRole.RECEPTION, StaffRole.SALES_ASSISTANT, StaffRole.SEAMSTRESS):
        assert role.value not in ELEVATED_ROLES
