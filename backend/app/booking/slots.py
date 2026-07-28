"""Slot materialization: the ONE place "is this time bookable" is decided.

Pure by construction — rows in, values out, no session, no ORM write, no
`Settings`, no `datetime.now()`. F13 validates a claim against it, F14 paints a
picker from it and F15 offers reschedule targets from it; three implementations
of this question would be three chances to disagree, and the one that disagrees
in F13's favour is a double-booked bride.

**A slot is a START TIME.** It has no duration and no end (pilot decision,
2026-07-28). The appointment type is recorded on the booking and its
`duration_minutes` is information the boutique acts on, but it does not shape
the grid and no booking blocks a later start. `availability_rules.capacity` is
how many bookings may share one start time, so the whole feature needs no
interval-overlap arithmetic anywhere.
"""

import dataclasses
import datetime
from collections.abc import Mapping, Sequence

from app.booking.validation import (
    DEFAULT_SLOT_CAPACITY,
    SLOT_INTERVAL_MINUTES,
    jerusalem_day_index,
)
from app.models.availability import AvailabilityException, AvailabilityRule
from app.storefront.validation import BOUTIQUE_TIMEZONE


@dataclasses.dataclass(frozen=True)
class Slot:
    starts_at: datetime.datetime  # timezone-aware, UTC
    capacity: int
    booked: int

    @property
    def remaining(self) -> int:
        # max(…, 0): an overbooked slot is a data anomaly, and reporting a
        # negative vacancy would be a second bug on top of the first. Such a
        # slot never reaches the caller anyway — materialize_slots drops it.
        return max(self.capacity - self.booked, 0)


@dataclasses.dataclass(frozen=True)
class _Window:
    open_time: datetime.time
    close_time: datetime.time
    capacity: int


def _windows_for(
    date: datetime.date,
    rules_by_day: Mapping[int, list[AvailabilityRule]],
    exceptions_by_date: Mapping[datetime.date, AvailabilityException],
) -> list[_Window]:
    """Exceptions beat the weekly grid in BOTH directions: a row with both times
    NULL closes a day the grid opens, and a row with both times set replaces the
    grid's windows for that date. One window per exception date is F7's
    documented v1 limitation, inherited unchanged."""
    day_rules = rules_by_day.get(jerusalem_day_index(date), [])
    exception = exceptions_by_date.get(date)
    if exception is None:
        return [
            _Window(open_time=rule.open_time, close_time=rule.close_time, capacity=rule.capacity)
            for rule in day_rules
        ]
    if exception.open_time is None or exception.close_time is None:
        return []
    # Capacity is staffing, and an exception changes the HOURS, not the staff —
    # so it inherits the weekday's own capacity. When the day carries several
    # windows with different capacities, the LEAST generous wins: an exception
    # is characteristically a constrained day (a holiday opened for one bride),
    # so erring high is erring toward overselling a boutique that is short-
    # staffed. With no rule to inherit from at all, the DB default.
    capacity = min((rule.capacity for rule in day_rules), default=DEFAULT_SLOT_CAPACITY)
    return [
        _Window(open_time=exception.open_time, close_time=exception.close_time, capacity=capacity)
    ]


def _to_utc(date: datetime.date, wall: datetime.time) -> datetime.datetime | None:
    """Boutique wall time → UTC instant, or None when that wall time is not a
    single real instant.

    Two DST cases, handled explicitly rather than left to `astimezone`'s
    defaults. Israel transitions at 02:00 and a boutique's hours rarely reach
    it — but an exception with unusual hours can, and "rarely" is not a
    correctness argument.

    - **Nonexistent** (spring forward, 02:00→03:00): dropped. A time that does
      not exist cannot be booked. Detected by round-tripping: zoneinfo maps a
      nonexistent local time onto a real instant whose local rendering differs
      from what we asked for.
    - **Ambiguous** (fall back, 01:00 twice): only the FIRST occurrence
      survives, because the grid generates each wall time once and `combine`
      leaves `fold=0`. That is the deliberate choice, not an accident of the
      default: two slots rendering identically at different instants is a worse
      failure than one lost hour a year. The ambiguity test pins it.
    """
    local = datetime.datetime.combine(date, wall, tzinfo=BOUTIQUE_TIMEZONE)
    instant = local.astimezone(datetime.UTC)
    if instant.astimezone(BOUTIQUE_TIMEZONE).replace(tzinfo=None) != local.replace(tzinfo=None):
        return None  # nonexistent
    return instant


def materialize_slots(
    *,
    rules: Sequence[AvailabilityRule],
    exceptions: Sequence[AvailabilityException],
    booked: Mapping[datetime.datetime, int],
    window_start: datetime.date,
    window_end: datetime.date,
    now: datetime.datetime,
) -> list[Slot]:
    """Every bookable start time in [window_start, window_end], both inclusive,
    boutique-calendar dates.

    `booked` is keyed by UTC start instant. It is passed in rather than read
    here because that is what keeps this function pure — and in F12 the caller
    has nothing to pass: the `bookings` table lands with F13.
    """
    rules_by_day: dict[int, list[AvailabilityRule]] = {}
    for rule in rules:
        rules_by_day.setdefault(rule.day_of_week, []).append(rule)
    exceptions_by_date = {row.date: row for row in exceptions}

    step = datetime.timedelta(minutes=SLOT_INTERVAL_MINUTES)
    # Keyed by instant, so overlapping windows on one day cannot yield the same
    # start twice — a duplicated start would double-count against `booked`.
    found: dict[datetime.datetime, int] = {}

    date = window_start
    while date <= window_end:
        for window in _windows_for(date, rules_by_day, exceptions_by_date):
            cursor = datetime.datetime.combine(date, window.open_time)
            end = datetime.datetime.combine(date, window.close_time)
            while cursor < end:  # close_time is exclusive
                instant = _to_utc(date, cursor.time())
                if instant is not None and instant > now:
                    found[instant] = max(found.get(instant, 0), window.capacity)
                cursor += step
        date += datetime.timedelta(days=1)

    slots = []
    for instant in sorted(found):
        capacity = found[instant]
        taken = booked.get(instant, 0)
        # Full slots are DROPPED, never marked: a public response that
        # enumerated them would disclose the boutique's booking density.
        if taken < capacity:
            slots.append(Slot(starts_at=instant, capacity=capacity, booked=taken))
    return slots
