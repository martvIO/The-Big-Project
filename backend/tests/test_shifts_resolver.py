"""F40's three-rule on-shift resolver, exhaustively — THE highest-value file in
the feature.

`on_shift_at` is pure and does no I/O, so the whole matrix is a fast-lane test
with no Postgres, no fixtures and no fakes. That is the point of putting it in
`app/shifts/validation.py` rather than on `FloorService`: a subtly wrong answer
here is invisible everywhere else, because every caller downstream faithfully
renders whatever it says.

⚠ EVERY CASE ASSERTS THE FULL TUPLE, never just the boolean. The answer and the
rule are computed together precisely so they cannot disagree (spec D2), and a
test that read only the boolean would pass on an implementation that reported
«לפי סידור העבודה» for a manual override — the wrong Hebrew rule label on a live
floor screen, on a green build.
"""

import datetime

import pytest

from app.booking.validation import jerusalem_day_index
from app.models.constants import OnShiftSource
from app.models.shift_template import ShiftTemplate
from app.shifts.validation import jerusalem_moment, on_shift_at, template_covers

# 2026-11-08 is a Jerusalem Sunday — F39's own fixture week, reused so the two
# resolver files talk about the same calendar.
SUNDAY = datetime.date(2026, 11, 8)
YESTERDAY = SUNDAY - datetime.timedelta(days=1)
TOMORROW = SUNDAY + datetime.timedelta(days=1)


def _template(
    *,
    day_of_week: int = 0,
    starts: datetime.time = datetime.time(9, 0),
    ends: datetime.time = datetime.time(14, 0),
) -> ShiftTemplate:
    """A detached model instance. No session, no database — SQLAlchemy models are
    ordinary objects until something flushes them, which is what keeps this file
    in the fast lane."""
    return ShiftTemplate(day_of_week=day_of_week, starts_at_time=starts, ends_at_time=ends)


def test_the_fixture_week_is_still_a_sunday() -> None:
    assert jerusalem_day_index(SUNDAY) == 0


# --- the sixteen-row matrix ---------------------------------------------------
#
# Named one by one, because each is a different way to be wrong.

_MATRIX: list[tuple[str, dict[str, object], tuple[bool, OnShiftSource]]] = [
    (
        "rule 1 wins over a roster that agrees with it",
        {
            "override_on": SUNDAY,
            "override_value": True,
            "roster_published": True,
            "rostered_now": True,
        },
        (True, OnShiftSource.MANUAL_TODAY),
    ),
    (
        "rule 1 adds a woman the roster left off",
        {
            "override_on": SUNDAY,
            "override_value": True,
            "roster_published": True,
            "rostered_now": False,
        },
        (True, OnShiftSource.MANUAL_TODAY),
    ),
    (
        # ⚠ THE SICK CALL — the case this feature exists for. She is on the
        # published roster and she is not coming in.
        "rule 1 takes a rostered woman off — the sick call",
        {
            "override_on": SUNDAY,
            "override_value": False,
            "roster_published": True,
            "rostered_now": True,
        },
        (False, OnShiftSource.MANUAL_TODAY),
    ),
    (
        "rule 1 confirms a roster that already left her off",
        {
            "override_on": SUNDAY,
            "override_value": False,
            "roster_published": True,
            "rostered_now": False,
        },
        (False, OnShiftSource.MANUAL_TODAY),
    ),
    (
        "rule 1 works with no roster at all",
        {
            "override_on": SUNDAY,
            "override_value": True,
            "roster_published": False,
            "rostered_now": False,
        },
        (True, OnShiftSource.MANUAL_TODAY),
    ),
    (
        # ⚠ Rule 3 puts everybody on, so `false` is the ONLY way a boutique that
        # never publishes can say somebody is not in today.
        "rule 1 takes a woman off in a boutique that never publishes",
        {
            "override_on": SUNDAY,
            "override_value": False,
            "roster_published": False,
            "rostered_now": False,
        },
        (False, OnShiftSource.MANUAL_TODAY),
    ),
    (
        "rule 1 beats a DRAFT roster, true",
        {
            "override_on": SUNDAY,
            "override_value": True,
            "roster_published": False,
            "rostered_now": True,
        },
        (True, OnShiftSource.MANUAL_TODAY),
    ),
    (
        "rule 1 beats a DRAFT roster, false",
        {
            "override_on": SUNDAY,
            "override_value": False,
            "roster_published": False,
            "rostered_now": True,
        },
        (False, OnShiftSource.MANUAL_TODAY),
    ),
    (
        # ⚠ D4's whole freshness rule: an override for a day that is not today is
        # never consulted, so it cannot be stale — it is silent. No clock
        # comparison exists to get wrong and no sweep ever runs.
        "yesterday's override is silent, and the roster answers",
        {
            "override_on": YESTERDAY,
            "override_value": False,
            "roster_published": True,
            "rostered_now": True,
        },
        (True, OnShiftSource.ROSTER),
    ),
    (
        "yesterday's override is silent, and the roster says no",
        {
            "override_on": YESTERDAY,
            "override_value": True,
            "roster_published": True,
            "rostered_now": False,
        },
        (False, OnShiftSource.ROSTER),
    ),
    (
        "yesterday's override is silent, and rule 3 answers",
        {
            "override_on": YESTERDAY,
            "override_value": False,
            "roster_published": False,
            "rostered_now": False,
        },
        (True, OnShiftSource.FALLBACK),
    ),
    (
        # A future date is never consulted either — which is why the route
        # accepts no date and always stamps today_jerusalem().
        "tomorrow's override is not consulted",
        {
            "override_on": TOMORROW,
            "override_value": False,
            "roster_published": True,
            "rostered_now": True,
        },
        (True, OnShiftSource.ROSTER),
    ),
    (
        "no override, published and rostered",
        {
            "override_on": None,
            "override_value": None,
            "roster_published": True,
            "rostered_now": True,
        },
        (True, OnShiftSource.ROSTER),
    ),
    (
        "no override, published and not rostered",
        {
            "override_on": None,
            "override_value": None,
            "roster_published": True,
            "rostered_now": False,
        },
        (False, OnShiftSource.ROSTER),
    ),
    (
        # ⚠ D6: A DRAFT IS NEVER AUTHORITATIVE, even with assignments on it.
        # `rostered_now` is True here and the answer still comes from rule 3.
        "a draft with assignments on it falls through to rule 3",
        {
            "override_on": None,
            "override_value": None,
            "roster_published": False,
            "rostered_now": True,
        },
        (True, OnShiftSource.FALLBACK),
    ),
    (
        # ⚠ D5, and R-G's guard: this row and the one below differ ONLY in
        # whether a published `rosters` row exists. Deriving rule 2 from
        # EXISTS(assignments) collapses them, and collapses them in the dangerous
        # direction — an owner who publishes a genuinely empty Saturday would find
        # the whole boutique reported as on shift.
        "published with zero assignments in the whole week is a real answer",
        {
            "override_on": None,
            "override_value": None,
            "roster_published": True,
            "rostered_now": False,
        },
        (False, OnShiftSource.ROSTER),
    ),
    (
        "no roster row at all falls through to rule 3",
        {
            "override_on": None,
            "override_value": None,
            "roster_published": False,
            "rostered_now": False,
        },
        (True, OnShiftSource.FALLBACK),
    ),
]


@pytest.mark.parametrize(("name", "inputs", "expected"), _MATRIX, ids=[row[0] for row in _MATRIX])
def test_the_three_rule_matrix(
    name: str, inputs: dict[str, object], expected: tuple[bool, OnShiftSource]
) -> None:
    assert on_shift_at(**inputs, local_date=SUNDAY) == expected, name  # type: ignore[arg-type]


# --- the two ties the matrix table does not spell -----------------------------


def test_an_override_agreeing_with_the_roster_still_reports_manual_today() -> None:
    """THE RULE THAT ANSWERED IS THE RULE THAT ANSWERED. An implementation that
    only reported `MANUAL_TODAY` when the override CHANGED the outcome would
    print «לפי סידור העבודה» beside a card the owner marked by hand this morning,
    and «ביטול הסימון הידני» would then appear with no label explaining it."""
    for value in (True, False):
        assert on_shift_at(
            override_on=SUNDAY,
            override_value=value,
            roster_published=True,
            rostered_now=value,
            local_date=SUNDAY,
        ) == (value, OnShiftSource.MANUAL_TODAY)


def test_a_stale_override_never_leaks_manual_today_into_the_source() -> None:
    """The mirror of the row above. Yesterday's flag must not colour today's
    answer even when the two agree — the label is what tells a shift manager
    whether anyone has touched this card today."""
    answer, source = on_shift_at(
        override_on=YESTERDAY,
        override_value=True,
        roster_published=True,
        rostered_now=True,
        local_date=SUNDAY,
    )
    assert (answer, source) == (True, OnShiftSource.ROSTER)


def test_a_half_written_override_pair_is_ignored_rather_than_answered() -> None:
    """`staff_users_on_shift_pair_check` makes this unreachable through the
    database, so this is a guard on the FUNCTION rather than on the data: a
    caller passing a date with no value must not get `None` back where the wire
    promises a boolean."""
    assert on_shift_at(
        override_on=SUNDAY,
        override_value=None,
        roster_published=True,
        rostered_now=True,
        local_date=SUNDAY,
    ) == (True, OnShiftSource.ROSTER)


# --- template_covers: the half-open interval ----------------------------------


def test_the_shift_interval_is_half_open_at_both_ends() -> None:
    """⚠ THE DECISION, and it is invisible except for one minute a day. F39
    permits overlapping templates on a weekday (its D2), so 09:00–14:00 and
    14:00–20:00 BOTH contain 14:00 under a closed interval and the board would
    credit the outgoing staffer with the incoming shift. `<` on the right end is
    what makes a handover instantaneous."""
    morning = _template(starts=datetime.time(9, 0), ends=datetime.time(14, 0))
    evening = _template(starts=datetime.time(14, 0), ends=datetime.time(20, 0))

    assert template_covers(morning, local_time=datetime.time(9, 0), day_index=0) is True
    assert template_covers(morning, local_time=datetime.time(13, 59), day_index=0) is True
    assert template_covers(morning, local_time=datetime.time(14, 0), day_index=0) is False
    assert template_covers(evening, local_time=datetime.time(14, 0), day_index=0) is True
    assert template_covers(morning, local_time=datetime.time(8, 59), day_index=0) is False
    assert template_covers(evening, local_time=datetime.time(20, 0), day_index=0) is False


def test_two_overlapping_templates_both_cover_one_instant_and_that_is_legal() -> None:
    """A morning 09:00–14:00 and an afternoon 13:00–20:00 sharing the changeover
    hour is an ordinary split shift (F39 D2). The caller ORs them into one
    answer; there is no double-count to make because the result is a boolean."""
    morning = _template(starts=datetime.time(9, 0), ends=datetime.time(14, 0))
    afternoon = _template(starts=datetime.time(13, 0), ends=datetime.time(20, 0))
    at = datetime.time(13, 30)
    covering = [
        row for row in (morning, afternoon) if template_covers(row, local_time=at, day_index=0)
    ]
    assert len(covering) == 2
    assert any(template_covers(row, local_time=at, day_index=0) for row in covering) is True


def test_a_template_on_another_weekday_never_covers() -> None:
    """The commonest way to build a roster against the wrong Thursday."""
    monday_shift = _template(day_of_week=1)
    assert template_covers(monday_shift, local_time=datetime.time(10, 0), day_index=1) is True
    assert template_covers(monday_shift, local_time=datetime.time(10, 0), day_index=0) is False


# --- DST: the triple no single-season implementation passes -------------------


def test_the_same_wall_clock_shift_covers_a_winter_and_a_summer_instant() -> None:
    """⚠ THE BOUTIQUE'S WALL CLOCK IS THE AUTHORITY, not an elapsed-seconds
    computation. «09:30 on a Sunday» is 07:30Z in winter and 06:30Z in summer,
    and one shift row must cover both — a naive implementation is right in
    exactly one season, and the wrong season ships six months of a board that
    says «לא במשמרת» about a woman standing at the counter.

    Storing UTC instants per shift instead would need a per-week
    materialisation and would drift an hour twice a year (F39 D6's argument,
    second instance)."""
    morning = _template(starts=datetime.time(9, 0), ends=datetime.time(14, 0))
    winter = datetime.datetime(2027, 1, 3, 7, 30, tzinfo=datetime.UTC)
    summer = datetime.datetime(2027, 7, 4, 6, 30, tzinfo=datetime.UTC)

    for instant, expected_date in (
        (winter, datetime.date(2027, 1, 3)),
        (summer, datetime.date(2027, 7, 4)),
    ):
        local_date, local_time, day_index = jerusalem_moment(instant)
        assert local_date == expected_date, instant
        assert day_index == 0, instant
        assert local_time == datetime.time(9, 30), instant
        assert template_covers(morning, local_time=local_time, day_index=day_index) is True


def test_both_instants_inside_the_autumn_fold_land_in_the_shift_that_covers_them() -> None:
    """⚠ DST NEEDS NO CODE, and this is why. The direction is instant → local,
    which is ALWAYS unambiguous: `astimezone` picks exactly one local wall time
    for any UTC instant, including inside the fold. A 25-hour Jerusalem day
    therefore has one hour whose clock reads 01:xx twice, and BOTH instants land
    inside a shift that covers 01:00 — correct, the boutique was open for both.

    2026-10-25 is the Sunday Israel leaves DST: 22:30Z and 23:30Z on the 24th are
    two different instants that both read 01:30 locally."""
    night = _template(starts=datetime.time(1, 0), ends=datetime.time(3, 0))
    first = datetime.datetime(2026, 10, 24, 22, 30, tzinfo=datetime.UTC)
    second = datetime.datetime(2026, 10, 24, 23, 30, tzinfo=datetime.UTC)
    assert first != second

    for instant in (first, second):
        local_date, local_time, day_index = jerusalem_moment(instant)
        assert local_date == datetime.date(2026, 10, 25), instant
        assert local_time == datetime.time(1, 30), instant
        assert template_covers(night, local_time=local_time, day_index=day_index) is True


def test_the_week_rollover_happens_on_the_boutiques_clock_and_not_on_utcs() -> None:
    """D14's last clause. 19:30Z on 2026-11-07 is still Saturday 21:30 in
    Jerusalem — the week that opened on 2026-11-01 — while 22:30Z on the SAME UTC
    day is already Sunday 00:30 there, which opens the next week. A resolver
    keying off the UTC date would put both in the same week and would roll the
    boutique's roster over two hours early, every night."""
    still_saturday = datetime.datetime(2026, 11, 7, 19, 30, tzinfo=datetime.UTC)
    already_sunday = datetime.datetime(2026, 11, 7, 22, 30, tzinfo=datetime.UTC)

    local_date, _, day_index = jerusalem_moment(still_saturday)
    assert (local_date, day_index) == (datetime.date(2026, 11, 7), 6)

    local_date, _, day_index = jerusalem_moment(already_sunday)
    assert (local_date, day_index) == (SUNDAY, 0)
