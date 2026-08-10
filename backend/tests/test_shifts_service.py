"""F39's service rules that are TOTAL FUNCTIONS — the material-edit predicate,
D3's auto-label, and (C2) the self-or-elevated matrix and D11's diff.

Fast lane: no database. Everything that needs one lives in `test_shifts_db.py`.
"""

import datetime
import uuid

import pytest

from app.auth.dependencies import NotAuthorizedError
from app.auth.service import StaffContext
from app.models.constants import AvailabilityState, StaffRole
from app.models.staff_user import StaffUser
from app.shifts.service import (
    ELEVATED_ROLES,
    HEBREW_DAY_NAMES,
    MATERIAL_FIELDS,
    ShiftsService,
    _state_counts,
    is_available_for_week,
    is_material_edit,
    plan_week_write,
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


# --- D5: the self-or-elevated guard -----------------------------------------


def _actor(role: str, staff_id: uuid.UUID) -> StaffContext:
    return StaffContext(
        id=staff_id,
        tenant_id=uuid.uuid4(),
        email="who@bella.example",
        display_name="Who",
        role=role,
    )


@pytest.mark.parametrize("role", [member.value for member in StaffRole])
def test_every_role_may_record_her_own_week(role: str) -> None:
    """All five, including the three floor roles: answering her own week is the
    whole point of the section, which is why the router admits every role and the
    narrowing lives here rather than in a gate."""
    me = uuid.uuid4()
    ShiftsService._authorize(me, _actor(role, me))


@pytest.mark.parametrize("role", [member.value for member in StaffRole])
def test_only_an_elevated_actor_may_record_for_somebody_else(role: str) -> None:
    """⚠ THE MATRIX, ALL FIVE ROLES × (self, other). D5 admits owner AND shift
    manager to the on-behalf write — `ELEVATED_ROLES` is the shipped predicate for
    «may act on anyone» across breaks, room claims and dispatch, and putting this
    route in `OWNER_ONLY` instead is the one edit that would silently make D5
    false."""
    me, her = uuid.uuid4(), uuid.uuid4()
    actor = _actor(role, me)
    if role in ELEVATED_ROLES:
        ShiftsService._authorize(her, actor)
    else:
        with pytest.raises(NotAuthorizedError):
            ShiftsService._authorize(her, actor)


# --- D11: the whole-week replace, as a diff ---------------------------------

_A, _B, _C = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def test_an_unanswered_shift_is_added() -> None:
    changed, cleared = plan_week_write(
        existing={}, requested={_A: AvailabilityState.AVAILABLE}, recorded_by=None
    )
    assert changed == [_A]
    assert cleared == []


def test_a_moved_state_is_written_and_an_unchanged_one_is_not() -> None:
    changed, cleared = plan_week_write(
        existing={
            _A: (AvailabilityState.AVAILABLE.value, None),
            _B: (AvailabilityState.AVAILABLE.value, None),
        },
        requested={_A: AvailabilityState.PREFERRED, _B: AvailabilityState.AVAILABLE},
        recorded_by=None,
    )
    assert changed == [_A]
    assert cleared == []


def test_a_shift_absent_from_the_request_is_cleared() -> None:
    """D8's clear path, reached from the console by putting a shift back on «לא
    נרשם» — the fourth radio is the rendered NAME of an absent row and its
    selection OMITS the template from the PUT."""
    changed, cleared = plan_week_write(
        existing={
            _A: (AvailabilityState.AVAILABLE.value, None),
            _B: (AvailabilityState.UNAVAILABLE.value, None),
        },
        requested={_A: AvailabilityState.AVAILABLE},
        recorded_by=None,
    )
    assert changed == []
    assert cleared == [_B]


def test_an_empty_request_clears_the_whole_week() -> None:
    changed, cleared = plan_week_write(
        existing={_A: (AvailabilityState.AVAILABLE.value, None)},
        requested={},
        recorded_by=None,
    )
    assert changed == []
    assert cleared == [_A]


def test_a_save_that_changes_nothing_plans_nothing() -> None:
    """⚠ THE NO-OP RULE'S GUARD. Both lists empty is what stops an audit row
    being written for an act nobody performed — and «who recorded whose
    availability» is exactly the question that table gets asked."""
    existing = {
        _A: (AvailabilityState.AVAILABLE.value, None),
        _B: (AvailabilityState.PREFERRED.value, None),
    }
    changed, cleared = plan_week_write(
        existing=existing,
        requested={_A: AvailabilityState.AVAILABLE, _B: AvailabilityState.PREFERRED},
        recorded_by=None,
    )
    assert changed == [] and cleared == []


def test_a_staffer_correcting_an_on_behalf_row_rewrites_it_even_at_the_same_state() -> None:
    """⚠ THE CLAUSE A DIFF ON STATE ALONE WOULD DROP. She sends the same answer a
    shift manager already recorded for her; without comparing `recorded_by` this
    is "unchanged", the column keeps the manager's id, and her own screen goes on
    saying «נרשם על ידי דנה» about an answer she just gave herself."""
    recorder = uuid.uuid4()
    changed, cleared = plan_week_write(
        existing={_C: (AvailabilityState.AVAILABLE.value, recorder)},
        requested={_C: AvailabilityState.AVAILABLE},
        recorded_by=None,
    )
    assert changed == [_C]
    assert cleared == []


# --- D10: offboarded staff are never asked ----------------------------------


def _staffer(
    *, deleted_at: datetime.datetime | None = None, last_day: datetime.date | None = None
) -> StaffUser:
    return StaffUser(
        tenant_id=uuid.uuid4(),
        email="s@bella.example",
        password_hash="x",
        display_name="S",
        role=StaffRole.OWNER.value,
        deleted_at=deleted_at,
        last_day=last_day,
    )


def test_a_live_staffer_with_no_last_day_is_always_asked() -> None:
    assert is_available_for_week(_staffer(), week_end_date=datetime.date(2026, 11, 14))


def test_a_soft_deleted_staffer_is_never_asked() -> None:
    gone = _staffer(deleted_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC))
    assert not is_available_for_week(gone, week_end_date=datetime.date(2026, 11, 14))


def test_a_staffer_whose_last_day_falls_inside_the_week_is_still_asked() -> None:
    """⚠ `>=`, AND `week_end` IS THE SATURDAY. A staffer leaving on the Saturday
    still works that week; `>` would drop her from a week she is rostered for, and
    a `week_end` of the following Sunday would keep somebody who left."""
    ends_on = datetime.date(2026, 11, 14)
    assert is_available_for_week(_staffer(last_day=ends_on), week_end_date=ends_on)
    assert is_available_for_week(
        _staffer(last_day=ends_on + datetime.timedelta(days=1)), week_end_date=ends_on
    )
    assert not is_available_for_week(
        _staffer(last_day=ends_on - datetime.timedelta(days=1)), week_end_date=ends_on
    )


# --- the audit row's counts --------------------------------------------------


def test_the_state_counts_name_every_member_including_the_zeroes() -> None:
    """A reader comparing two audit rows must not have to guess whether a missing
    key means «none» or «this row predates the member»."""
    counts = _state_counts([AvailabilityState.AVAILABLE, AvailabilityState.AVAILABLE])
    assert counts == {"available": 2, "unavailable": 0, "preferred": 0}
    assert set(counts) == {member.value for member in AvailabilityState}
