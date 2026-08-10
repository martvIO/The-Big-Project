"""F39's pure rules: the Sunday week key, the ±4 window, the template bounds and
— the test this feature most needs — the DST-safe deadline resolver.

Fast lane: no database, no HTTP, no fakes. Every function under test is total.
"""

import datetime

import pytest

from app.models.constants import AvailabilityState, StaffRole
from app.shifts.service import MATERIAL_FIELDS, is_material_edit
from app.shifts.validation import (
    MAX_COVERAGE_TARGET,
    MAX_SHIFT_LABEL_LENGTH,
    MAX_TEMPLATES,
    MAX_TEMPLATES_PER_DAY,
    SUBMISSION_WEEK_WINDOW_WEEKS,
    CoverageTargetInvalidError,
    ShiftsValidationError,
    TemplateLimitReachedError,
    WeekOutOfRangeError,
    assert_readable_week,
    assert_template_capacity,
    assert_writable_week,
    current_week_start,
    deadline_at,
    default_week_start,
    validate_coverage_targets,
    validate_state,
    validate_template,
    validate_week_start,
    week_end,
)

# 2026-11-08 is a Sunday. Asserted rather than trusted — a fixture date that
# quietly stops being a Sunday would make half this module vacuous.
_SUNDAY = datetime.date(2026, 11, 8)


def test_the_fixture_date_is_a_sunday() -> None:
    assert _SUNDAY.weekday() == 6


@pytest.mark.parametrize("offset", range(7))
def test_only_a_sunday_is_a_legal_week_key(offset: int) -> None:
    """All seven weekdays, parametrised. `jerusalem_day_index` is IMPORTED from
    `app/booking/validation.py` and never re-derived — its FE twin is pinned by
    `test_frontend_constant_parity.py`, so a second copy of `(weekday()+1)%7`
    here would be a third spelling nothing pins."""
    day = _SUNDAY + datetime.timedelta(days=offset)
    if offset == 0:
        assert validate_week_start(day) == day
    else:
        with pytest.raises(ShiftsValidationError):
            validate_week_start(day)


def test_the_current_week_start_is_the_sunday_on_or_before_today() -> None:
    for offset in range(7):
        assert current_week_start(_SUNDAY + datetime.timedelta(days=offset)) == _SUNDAY


def test_the_week_ends_six_days_after_it_starts() -> None:
    """`week_end` is INCLUSIVE — Sunday through Saturday is seven days, and D10's
    offboarding predicate (`last_day >= week_end`) is only correct if the last
    day of the week is the Saturday rather than the next Sunday."""
    assert week_end(_SUNDAY) == datetime.date(2026, 11, 14)


def test_the_default_week_is_next_week_not_this_one() -> None:
    """D1: the current week has begun, and F40 publishes before a week starts, so
    recording into a running week is F40's roster-edit problem. The read with no
    parameter therefore lands on the week she is here to answer."""
    assert default_week_start(_SUNDAY) == _SUNDAY + datetime.timedelta(days=7)


def test_reads_accept_the_whole_window_in_both_directions() -> None:
    for weeks in range(-SUBMISSION_WEEK_WINDOW_WEEKS, SUBMISSION_WEEK_WINDOW_WEEKS + 1):
        assert_readable_week(_SUNDAY + datetime.timedelta(weeks=weeks), current=_SUNDAY)


def test_reads_refuse_one_week_past_each_edge() -> None:
    for weeks in (-(SUBMISSION_WEEK_WINDOW_WEEKS + 1), SUBMISSION_WEEK_WINDOW_WEEKS + 1):
        with pytest.raises(WeekOutOfRangeError):
            assert_readable_week(_SUNDAY + datetime.timedelta(weeks=weeks), current=_SUNDAY)


def test_writes_additionally_refuse_the_current_week_and_every_past_one() -> None:
    """The read/write asymmetry is D1's, and it is the reason `assert_writable_week`
    exists at all rather than a `strict=` flag on the reader: a past week is
    READABLE (she may look at what she said) and never writable."""
    assert_writable_week(_SUNDAY + datetime.timedelta(weeks=1), current=_SUNDAY)
    for weeks in (0, -1, -SUBMISSION_WEEK_WINDOW_WEEKS):
        with pytest.raises(WeekOutOfRangeError):
            assert_writable_week(_SUNDAY + datetime.timedelta(weeks=weeks), current=_SUNDAY)


def test_a_write_past_the_far_edge_is_still_out_of_range() -> None:
    with pytest.raises(WeekOutOfRangeError):
        assert_writable_week(
            _SUNDAY + datetime.timedelta(weeks=SUBMISSION_WEEK_WINDOW_WEEKS + 1), current=_SUNDAY
        )


def test_a_non_sunday_is_refused_by_both_window_guards() -> None:
    monday = _SUNDAY + datetime.timedelta(days=1)
    for guard in (assert_readable_week, assert_writable_week):
        with pytest.raises(ShiftsValidationError):
            guard(monday, current=_SUNDAY)


# --- templates ---------------------------------------------------------------


def _template(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "day_of_week": 4,
        "label": "משמרת בוקר",
        "starts_at_time": datetime.time(9, 0),
        "ends_at_time": datetime.time(14, 0),
    }
    return {**base, **overrides}


def test_a_legal_template_returns_its_trimmed_label() -> None:
    assert validate_template(**_template(label="  משמרת בוקר  ")) == "משמרת בוקר"  # type: ignore[arg-type]


def test_the_end_must_be_after_the_start_so_there_is_no_overnight_shift() -> None:
    """D2's ceiling, and it is the DDL's too. A bridal boutique does not run an
    overnight shift; adding one needs a `crosses_midnight` flag or a duration
    column, and nothing here blocks that."""
    for start, end in (
        (datetime.time(22, 0), datetime.time(2, 0)),
        (datetime.time(9, 0), datetime.time(9, 0)),
    ):
        with pytest.raises(ShiftsValidationError):
            validate_template(**_template(starts_at_time=start, ends_at_time=end))  # type: ignore[arg-type]


@pytest.mark.parametrize("day", [-1, 7, 100])
def test_the_day_index_is_zero_through_six(day: int) -> None:
    with pytest.raises(ShiftsValidationError):
        validate_template(**_template(day_of_week=day))  # type: ignore[arg-type]


def test_a_blank_label_is_refused_and_a_long_one_is_bounded() -> None:
    for label in ("", "   "):
        with pytest.raises(ShiftsValidationError):
            validate_template(**_template(label=label))  # type: ignore[arg-type]
    assert validate_template(**_template(label="א" * MAX_SHIFT_LABEL_LENGTH))  # type: ignore[arg-type]
    with pytest.raises(ShiftsValidationError):
        validate_template(**_template(label="א" * (MAX_SHIFT_LABEL_LENGTH + 1)))  # type: ignore[arg-type]


def test_the_per_day_cap_bites_before_the_total_one() -> None:
    """⚠ 6 × 7 = 42 EXACTLY, so `MAX_TEMPLATES` is unreachable through the
    console — it is a server-side guard against a non-UI caller and needs no
    screen. Asserted so nobody designs a total-count meter for a number the UI
    cannot hit (design F-11)."""
    assert MAX_TEMPLATES_PER_DAY * 7 == MAX_TEMPLATES
    assert_template_capacity(day_count=MAX_TEMPLATES_PER_DAY - 1, total_count=0)
    with pytest.raises(TemplateLimitReachedError):
        assert_template_capacity(day_count=MAX_TEMPLATES_PER_DAY, total_count=0)
    with pytest.raises(TemplateLimitReachedError):
        assert_template_capacity(day_count=0, total_count=MAX_TEMPLATES)


# --- state -------------------------------------------------------------------


def test_every_enum_member_is_accepted_and_nothing_else_is() -> None:
    for member in AvailabilityState:
        assert validate_state(member.value) is member
    # ⚠ `pending` in particular: it is the console's fourth radio «לא נרשם», and
    # it is NOT a stored state (D8). A client sending it is a 400, never a row.
    for value in ("pending", "PREFERRED", "", "yes"):
        with pytest.raises(ShiftsValidationError):
            validate_state(value)


# --- the deadline, and this is the pair the feature most needs ---------------


def test_the_same_setting_resolves_to_a_different_utc_instant_in_january_and_july() -> None:
    """⚠ THE DST PAIR. Jerusalem is UTC+2 in winter and UTC+3 in summer, so one
    stored `(3, "18:00")` — Wednesday 18:00 — is `16:00Z` in January and `15:00Z`
    in July. A naive implementation (a fixed offset, or a stored UTC instant)
    passes EXACTLY ONE of these two, which is why they are one test.

    The deadline day is the named weekday in the week PRECEDING `week_start`, so
    Wednesday 18:00 leaves Thursday–Saturday to build the roster before Sunday.
    """
    january = deadline_at(
        datetime.date(2026, 1, 11), day_of_week=3, deadline_time=datetime.time(18, 0)
    )
    july = deadline_at(
        datetime.date(2026, 7, 12), day_of_week=3, deadline_time=datetime.time(18, 0)
    )
    assert january == datetime.datetime(2026, 1, 7, 16, 0, tzinfo=datetime.UTC)
    assert july == datetime.datetime(2026, 7, 8, 15, 0, tzinfo=datetime.UTC)


def test_the_deadline_lands_in_the_week_before_the_one_it_closes() -> None:
    """Sunday..Saturday, all seven settings, against the same target week."""
    for day_of_week in range(7):
        resolved = deadline_at(_SUNDAY, day_of_week=day_of_week, deadline_time=datetime.time(18, 0))
        local = resolved.astimezone(datetime.UTC)
        assert local < datetime.datetime(2026, 11, 8, tzinfo=datetime.UTC), day_of_week
        assert local >= datetime.datetime(2026, 10, 31, tzinfo=datetime.UTC), day_of_week


def test_the_resolved_deadline_is_always_utc() -> None:
    """The wire carries an ISO-8601 UTC instant (`Instant` rule); nothing on the
    API ever emits `+02:00` or a zone name."""
    resolved = deadline_at(_SUNDAY, day_of_week=3, deadline_time=datetime.time(18, 0))
    assert resolved.tzinfo is datetime.UTC
    assert resolved.isoformat().endswith("+00:00")


@pytest.mark.parametrize("day_of_week", [-1, 7])
def test_a_deadline_day_outside_the_week_is_refused(day_of_week: int) -> None:
    with pytest.raises(ShiftsValidationError):
        deadline_at(_SUNDAY, day_of_week=day_of_week, deadline_time=datetime.time(18, 0))


def test_a_deadline_cannot_be_resolved_against_a_non_sunday() -> None:
    with pytest.raises(ShiftsValidationError):
        deadline_at(
            _SUNDAY + datetime.timedelta(days=1),
            day_of_week=3,
            deadline_time=datetime.time(18, 0),
        )


# --- F40: coverage targets, and the edit that stays immaterial ----------------


def test_a_sparse_map_of_known_roles_is_accepted_and_preserved() -> None:
    """D10's shape. `{}` is valid and means «no target on this shift», which is
    the DEFAULT state of every template that predates the feature."""
    assert validate_coverage_targets({}) == {}
    assert validate_coverage_targets(
        {StaffRole.SALES_ASSISTANT.value: 2, StaffRole.SEAMSTRESS.value: 1}
    ) == {"sales_assistant": 2, "seamstress": 1}


def test_zero_is_accepted_and_is_not_the_same_as_an_absent_key() -> None:
    """⚠ THE DISTINCTION D10 RESTS ON. An absent key is «no target» and renders
    as a plain count; `0` is «deliberately nobody» and renders as a target. A
    validator that dropped falsy values would silently turn the second into the
    first, and the shift would stop reporting «חסר איוש» for a role the owner
    had explicitly zeroed."""
    assert validate_coverage_targets({StaffRole.SEAMSTRESS.value: 0}) == {"seamstress": 0}


def test_every_staff_role_is_a_legal_key() -> None:
    """Driven off the enum, so a sixth role is a legal target the day it exists —
    `lib/roles.ts`' own guarantee, kept on the server side too."""
    for role in StaffRole:
        assert validate_coverage_targets({role.value: 1}) == {role.value: 1}


def test_an_unknown_role_key_is_refused() -> None:
    with pytest.raises(CoverageTargetInvalidError):
        validate_coverage_targets({"barista": 1})


@pytest.mark.parametrize("value", [-1, MAX_COVERAGE_TARGET + 1, 999])
def test_a_target_outside_the_bound_is_refused(value: int) -> None:
    with pytest.raises(CoverageTargetInvalidError):
        validate_coverage_targets({StaffRole.SEAMSTRESS.value: value})


def test_the_bound_itself_is_accepted() -> None:
    assert validate_coverage_targets({StaffRole.SEAMSTRESS.value: MAX_COVERAGE_TARGET}) == {
        "seamstress": MAX_COVERAGE_TARGET
    }


@pytest.mark.parametrize("value", ["2", 2.5, None, [2], {"n": 2}])
def test_a_non_integer_target_is_refused(value: object) -> None:
    with pytest.raises(CoverageTargetInvalidError):
        validate_coverage_targets({StaffRole.SEAMSTRESS.value: value})


def test_true_does_not_coerce_to_one() -> None:
    """⚠ `bool` IS A SUBCLASS OF `int` IN PYTHON, so `isinstance(True, int)` is
    True and a naive check stores «1 seamstress» for a client that sent `true`.
    F39's `AtelierSettingsUpdate` finding, verbatim reason."""
    for value in (True, False):
        with pytest.raises(CoverageTargetInvalidError):
            validate_coverage_targets({StaffRole.SEAMSTRESS.value: value})


def test_a_non_mapping_payload_is_refused() -> None:
    """A five-element vector is the shape D10 rejects, and a list is how a client
    would send one."""
    for payload in ([1, 2], "seamstress", 3, None):
        with pytest.raises(CoverageTargetInvalidError):
            validate_coverage_targets(payload)


def test_a_targets_only_edit_is_not_a_material_edit() -> None:
    """⚠ A POSITIVE UNCHANGED ASSERTION, written before the field exists anywhere
    else. «Add the new field to the material set» is the reflex, and it is a
    DATA-LOSS reflex: the first owner who fixes a target from 2 to 3 would
    soft-delete every future submission on that template. `is_material_edit`
    reads `day_of_week`, `starts_at_time`, `ends_at_time` and must not gain a
    fourth — a coverage number changes nothing any staffer answered.

    It passes a `coverage_targets` key on both sides deliberately: if somebody
    adds the field to `MATERIAL_FIELDS`, this reds with a `KeyError` on the
    before/after dicts long before it reds on the boolean.
    """
    unchanged = {
        "day_of_week": 4,
        "starts_at_time": datetime.time(9, 0),
        "ends_at_time": datetime.time(14, 0),
    }
    assert is_material_edit(before=dict(unchanged), after=dict(unchanged)) is False
    assert MATERIAL_FIELDS == ("day_of_week", "starts_at_time", "ends_at_time")
    assert "coverage_targets" not in MATERIAL_FIELDS


def test_the_three_material_fields_still_invalidate() -> None:
    """The other direction, so the assertion above cannot be satisfied by an
    `is_material_edit` that returns False for everything."""
    before = {
        "day_of_week": 4,
        "starts_at_time": datetime.time(9, 0),
        "ends_at_time": datetime.time(14, 0),
    }
    for field, moved in (
        ("day_of_week", 5),
        ("starts_at_time", datetime.time(10, 0)),
        ("ends_at_time", datetime.time(15, 0)),
    ):
        assert is_material_edit(before=dict(before), after={**before, field: moved}) is True, field
