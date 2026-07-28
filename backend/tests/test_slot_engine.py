"""The pure slot engine. No database, no clock, no Settings — every hard case
(the Israeli week, Israel's DST transitions, an exception that closes a day the
weekly grid says is open) is a value-in/value-out assertion.
"""

import datetime
import uuid

import pytest

from app.booking.slots import Slot, materialize_slots
from app.booking.validation import (
    DEFAULT_SLOT_CAPACITY,
    SLOT_INTERVAL_MINUTES,
    jerusalem_day_index,
)
from app.models.availability import AvailabilityException, AvailabilityRule
from app.storefront.validation import BOUTIQUE_TIMEZONE

TENANT = uuid.uuid4()

# Israel is UTC+2 in winter, UTC+3 under DST.
WINTER_MONDAY = datetime.date(2026, 1, 5)
SUMMER_MONDAY = datetime.date(2026, 7, 6)

# Israel 2026: DST starts Fri 27 Mar (02:00→03:00), ends Sun 25 Oct (02:00→01:00).
DST_SPRING_FORWARD = datetime.date(2026, 3, 27)
DST_FALL_BACK = datetime.date(2026, 10, 25)

LONG_AGO = datetime.datetime(2000, 1, 1, tzinfo=datetime.UTC)


def _rule(
    day_of_week: int,
    open_time: tuple[int, int] = (10, 0),
    close_time: tuple[int, int] = (12, 0),
    capacity: int = 1,
) -> AvailabilityRule:
    return AvailabilityRule(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        day_of_week=day_of_week,
        open_time=datetime.time(*open_time),
        close_time=datetime.time(*close_time),
        capacity=capacity,
    )


def _exception(
    date: datetime.date,
    open_time: tuple[int, int] | None = None,
    close_time: tuple[int, int] | None = None,
) -> AvailabilityException:
    return AvailabilityException(
        id=uuid.uuid4(),
        tenant_id=TENANT,
        date=date,
        open_time=datetime.time(*open_time) if open_time else None,
        close_time=datetime.time(*close_time) if close_time else None,
        note=None,
    )


def _local(date: datetime.date, hour: int, minute: int = 0) -> datetime.datetime:
    """The UTC instant of a boutique-local wall time."""
    return datetime.datetime.combine(
        date, datetime.time(hour, minute), tzinfo=BOUTIQUE_TIMEZONE
    ).astimezone(datetime.UTC)


def _run(
    *,
    rules: list[AvailabilityRule] | None = None,
    exceptions: list[AvailabilityException] | None = None,
    booked: dict[datetime.datetime, int] | None = None,
    window_start: datetime.date = WINTER_MONDAY,
    window_end: datetime.date | None = None,
    now: datetime.datetime = LONG_AGO,
) -> list[Slot]:
    return materialize_slots(
        rules=rules if rules is not None else [],
        exceptions=exceptions if exceptions is not None else [],
        booked=booked if booked is not None else {},
        window_start=window_start,
        window_end=window_end if window_end is not None else window_start,
        now=now,
    )


def _local_times(slots: list[Slot]) -> list[str]:
    return [
        slot.starts_at.astimezone(BOUTIQUE_TIMEZONE).strftime("%Y-%m-%d %H:%M") for slot in slots
    ]


class TestJerusalemDayIndex:
    @pytest.mark.parametrize(
        ("date", "expected"),
        [
            (datetime.date(2026, 1, 4), 0),  # Sunday
            (datetime.date(2026, 1, 5), 1),  # Monday
            (datetime.date(2026, 1, 6), 2),
            (datetime.date(2026, 1, 7), 3),
            (datetime.date(2026, 1, 8), 4),
            (datetime.date(2026, 1, 9), 5),  # Friday
            (datetime.date(2026, 1, 10), 6),  # Saturday
            (datetime.date(2026, 7, 26), 0),  # a Sunday half a year away
            (datetime.date(2027, 2, 27), 6),
        ],
    )
    def test_sunday_is_zero(self, date: datetime.date, expected: int) -> None:
        assert jerusalem_day_index(date) == expected

    def test_matches_the_iso_weekday_offset_for_a_whole_year(self) -> None:
        day = datetime.date(2026, 1, 1)
        for _ in range(365):
            assert jerusalem_day_index(day) == (day.weekday() + 1) % 7
            assert 0 <= jerusalem_day_index(day) <= 6
            day += datetime.timedelta(days=1)


class TestGrid:
    def test_close_time_is_exclusive(self) -> None:
        slots = _run(rules=[_rule(1, (10, 0), (12, 0))])
        assert _local_times(slots) == [
            "2026-01-05 10:00",
            "2026-01-05 10:30",
            "2026-01-05 11:00",
            "2026-01-05 11:30",
        ]

    def test_interval_is_the_named_constant(self) -> None:
        slots = _run(rules=[_rule(1, (10, 0), (11, 0))])
        delta = slots[1].starts_at - slots[0].starts_at
        assert delta == datetime.timedelta(minutes=SLOT_INTERVAL_MINUTES)

    def test_open_time_off_the_interval_grid_is_honoured(self) -> None:
        """The grid starts at open_time, not at the top of the hour."""
        slots = _run(rules=[_rule(1, (10, 20), (11, 30))])
        assert _local_times(slots) == ["2026-01-05 10:20", "2026-01-05 10:50", "2026-01-05 11:20"]

    def test_a_day_with_no_rule_has_no_slots(self) -> None:
        assert _run(rules=[_rule(2)]) == []  # Tuesday rule, Monday window

    def test_multiple_windows_on_one_day_are_unioned_and_sorted(self) -> None:
        slots = _run(rules=[_rule(1, (16, 0), (17, 0)), _rule(1, (10, 0), (11, 0))])
        assert _local_times(slots) == [
            "2026-01-05 10:00",
            "2026-01-05 10:30",
            "2026-01-05 16:00",
            "2026-01-05 16:30",
        ]

    def test_overlapping_windows_never_duplicate_a_start(self) -> None:
        slots = _run(rules=[_rule(1, (10, 0), (11, 0)), _rule(1, (10, 30), (11, 30))])
        assert _local_times(slots) == [
            "2026-01-05 10:00",
            "2026-01-05 10:30",
            "2026-01-05 11:00",
        ]

    def test_window_spans_multiple_days(self) -> None:
        slots = _run(
            rules=[_rule(1, (10, 0), (11, 0)), _rule(3, (10, 0), (11, 0))],
            window_start=WINTER_MONDAY,
            window_end=WINTER_MONDAY + datetime.timedelta(days=6),
        )
        assert _local_times(slots) == [
            "2026-01-05 10:00",
            "2026-01-05 10:30",
            "2026-01-07 10:00",
            "2026-01-07 10:30",
        ]

    def test_window_end_is_inclusive(self) -> None:
        slots = _run(
            rules=[_rule(2, (10, 0), (10, 30))],
            window_start=WINTER_MONDAY,
            window_end=WINTER_MONDAY + datetime.timedelta(days=1),
        )
        assert _local_times(slots) == ["2026-01-06 10:00"]


class TestExceptions:
    def test_closed_all_day_beats_an_open_weekly_rule(self) -> None:
        slots = _run(rules=[_rule(1)], exceptions=[_exception(WINTER_MONDAY)])
        assert slots == []

    def test_special_hours_replace_the_weekly_window(self) -> None:
        slots = _run(
            rules=[_rule(1, (10, 0), (18, 0))],
            exceptions=[_exception(WINTER_MONDAY, (9, 0), (10, 0))],
        )
        assert _local_times(slots) == ["2026-01-05 09:00", "2026-01-05 09:30"]

    def test_an_exception_opens_a_day_the_weekly_grid_closes(self) -> None:
        slots = _run(rules=[], exceptions=[_exception(WINTER_MONDAY, (9, 0), (10, 0))])
        assert _local_times(slots) == ["2026-01-05 09:00", "2026-01-05 09:30"]

    def test_an_exception_on_another_date_is_ignored(self) -> None:
        slots = _run(
            rules=[_rule(1, (10, 0), (11, 0))],
            exceptions=[_exception(WINTER_MONDAY + datetime.timedelta(days=1))],
        )
        assert len(slots) == 2

    def test_exception_day_inherits_the_weekly_capacity(self) -> None:
        slots = _run(
            rules=[_rule(1, (10, 0), (18, 0), capacity=4)],
            exceptions=[_exception(WINTER_MONDAY, (9, 0), (9, 30))],
        )
        assert [slot.capacity for slot in slots] == [4]

    def test_exception_day_without_a_rule_falls_back_to_the_default(self) -> None:
        slots = _run(exceptions=[_exception(WINTER_MONDAY, (9, 0), (9, 30))])
        assert [slot.capacity for slot in slots] == [DEFAULT_SLOT_CAPACITY]

    def test_multi_window_day_inherits_the_narrowest_capacity(self) -> None:
        """Several rules can cover one weekday with different capacities. An
        exception is characteristically a CONSTRAINED day — a holiday opened for
        one bride — so the least generous wins: erring high here would oversell
        a boutique that is short-staffed, and overselling is the failure this
        whole feature exists to prevent."""
        slots = _run(
            rules=[_rule(1, (10, 0), (11, 0), capacity=2), _rule(1, (16, 0), (17, 0), capacity=5)],
            exceptions=[_exception(WINTER_MONDAY, (9, 0), (9, 30))],
        )
        assert [slot.capacity for slot in slots] == [2]


class TestCapacity:
    def test_remaining_reflects_bookings(self) -> None:
        start = _local(WINTER_MONDAY, 10)
        slots = _run(rules=[_rule(1, (10, 0), (11, 0), capacity=3)], booked={start: 1})
        assert [(slot.capacity, slot.booked, slot.remaining) for slot in slots] == [
            (3, 1, 2),
            (3, 0, 3),
        ]

    def test_a_full_slot_is_dropped_entirely(self) -> None:
        """Never marked — a public response that enumerated full slots would
        disclose the boutique's booking density."""
        start = _local(WINTER_MONDAY, 10)
        slots = _run(rules=[_rule(1, (10, 0), (11, 0), capacity=1)], booked={start: 1})
        assert _local_times(slots) == ["2026-01-05 10:30"]

    def test_overbooked_data_anomaly_drops_rather_than_going_negative(self) -> None:
        start = _local(WINTER_MONDAY, 10)
        slots = _run(rules=[_rule(1, (10, 0), (11, 0), capacity=2)], booked={start: 5})
        assert _local_times(slots) == ["2026-01-05 10:30"]
        assert all(slot.remaining >= 0 for slot in slots)

    def test_bookings_outside_the_grid_are_ignored(self) -> None:
        slots = _run(
            rules=[_rule(1, (10, 0), (11, 0))],
            booked={_local(WINTER_MONDAY, 23): 9},
        )
        assert len(slots) == 2


class TestNowBoundary:
    def test_a_slot_exactly_at_now_is_out(self) -> None:
        slots = _run(rules=[_rule(1, (10, 0), (11, 0))], now=_local(WINTER_MONDAY, 10))
        assert _local_times(slots) == ["2026-01-05 10:30"]

    def test_a_slot_one_second_after_now_is_in(self) -> None:
        now = _local(WINTER_MONDAY, 10) - datetime.timedelta(seconds=1)
        slots = _run(rules=[_rule(1, (10, 0), (10, 30))], now=now)
        assert _local_times(slots) == ["2026-01-05 10:00"]


class TestDaylightSaving:
    def test_a_nonexistent_local_time_is_dropped(self) -> None:
        """Israel springs forward at 02:00 → 03:00. 02:00 and 02:30 do not exist
        that day, so they cannot be booked."""
        assert jerusalem_day_index(DST_SPRING_FORWARD) == 5  # Friday
        slots = _run(
            rules=[_rule(5, (1, 0), (4, 0))],
            window_start=DST_SPRING_FORWARD,
        )
        assert _local_times(slots) == [
            "2026-03-27 01:00",
            "2026-03-27 01:30",
            "2026-03-27 03:00",
            "2026-03-27 03:30",
        ]

    def test_an_ambiguous_local_time_appears_exactly_once(self) -> None:
        """Israel falls back at 02:00 → 01:00, so 01:00 and 01:30 happen twice.
        The FIRST occurrence is kept: two slots rendering identically at
        different instants is worse than one hour of lost capacity a year."""
        assert jerusalem_day_index(DST_FALL_BACK) == 0  # Sunday
        slots = _run(rules=[_rule(0, (0, 30), (3, 0))], window_start=DST_FALL_BACK)
        assert _local_times(slots) == [
            "2026-10-25 00:30",
            "2026-10-25 01:00",
            "2026-10-25 01:30",
            "2026-10-25 02:00",
            "2026-10-25 02:30",
        ]
        # …and every kept instant is distinct and strictly increasing.
        instants = [slot.starts_at for slot in slots]
        assert instants == sorted(instants)
        assert len(set(instants)) == len(instants)

    def test_a_normal_day_either_side_is_unaffected(self) -> None:
        for date in (
            DST_SPRING_FORWARD - datetime.timedelta(days=7),
            DST_SPRING_FORWARD + datetime.timedelta(days=7),
        ):
            slots = _run(
                rules=[_rule(jerusalem_day_index(date), (1, 0), (4, 0))], window_start=date
            )
            assert len(slots) == 6

    def test_summer_and_winter_wall_times_map_to_different_offsets(self) -> None:
        winter = _run(rules=[_rule(1, (10, 0), (10, 30))], window_start=WINTER_MONDAY)
        summer = _run(rules=[_rule(1, (10, 0), (10, 30))], window_start=SUMMER_MONDAY)
        assert winter[0].starts_at.hour == 8  # UTC+2
        assert summer[0].starts_at.hour == 7  # UTC+3
        assert _local_times(winter) == ["2026-01-05 10:00"]
        assert _local_times(summer) == ["2026-07-06 10:00"]


def test_every_slot_is_timezone_aware_utc() -> None:
    slots = _run(rules=[_rule(1, (10, 0), (11, 0))])
    assert slots
    assert all(slot.starts_at.tzinfo is datetime.UTC for slot in slots)


def test_output_is_sorted_by_start() -> None:
    slots = _run(
        rules=[_rule(3, (10, 0), (11, 0)), _rule(1, (16, 0), (17, 0))],
        window_start=WINTER_MONDAY,
        window_end=WINTER_MONDAY + datetime.timedelta(days=6),
    )
    assert [slot.starts_at for slot in slots] == sorted(slot.starts_at for slot in slots)


def test_an_empty_window_is_empty_not_an_error() -> None:
    assert _run(rules=[_rule(1)], window_start=WINTER_MONDAY, window_end=WINTER_MONDAY) != []
    assert (
        _run(
            rules=[_rule(1)],
            window_start=WINTER_MONDAY + datetime.timedelta(days=1),
            window_end=WINTER_MONDAY,
        )
        == []
    )
