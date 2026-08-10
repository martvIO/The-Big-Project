"""F39's pure rules: the Jerusalem-Sunday week key, the ±4 submission window,
the template bounds and the DST-safe deadline resolver.

Nothing here does I/O, so every rule is provable in the fast lane with no
Postgres and no fakes — `validate_weekly_rules`' shape, and the reason the DST
pair (§ `deadline_at`) can be a unit test rather than a CI-only one.

Deliberately NOT env-tunable, per F8's rule that `Settings` carries deployment
identity and never product policy. The boutique wall clock lives once in
`app/storefront/validation.py` and the week index lives once in
`app/booking/validation.py`; both are IMPORTED here and never restated.
"""

import datetime

from app.booking.validation import jerusalem_day_index
from app.errors import DomainValidationError
from app.models.constants import AvailabilityState
from app.storefront.validation import BOUTIQUE_TIMEZONE

# How far either side of the current week a READ may reach (D1). Writes are
# additionally forward-only — see `assert_writable_week`.
#
# Four weeks is the roster horizon a boutique plans over, and it is small enough
# that no request can ever materialise a year. Rejected: implying "next week"
# with no parameter at all — "next" changes meaning at Saturday midnight and a
# browser on a New York clock disagrees with the server for part of every day,
# which is `lib/jerusalem.ts`' whole reason for existing. The client may NAME a
# week; the server validates it and never trusts the arithmetic.
SUBMISSION_WEEK_WINDOW_WEEKS = 4

# A thumb-sized list on a phone. The owner splits a day into a morning and an
# afternoon, occasionally a third; six is generous and still fits `MyWeekPanel`'s
# one-column render without a scroll of chrome.
MAX_TEMPLATES_PER_DAY = 6

# ⚠ 6 × 7 = 42 EXACTLY, so this is UNREACHABLE through the console — the per-day
# cap always bites first. It is a server-side guard against a non-UI caller and
# needs no screen of its own (design F-11). Stated here so nobody designs a
# total-count meter for a number that cannot be hit.
MAX_TEMPLATES = MAX_TEMPLATES_PER_DAY * 7

# «משמרת בוקר», «משמרת ערב», «ערב שישי — צוות מצומצם». A phrase, not a sentence:
# this string sits on a `<legend>` beside an `HH:MM–HH:MM` range at 375 px.
MAX_SHIFT_LABEL_LENGTH = 60

# The number of days a week spans, inclusive of both ends. `week_end` is the
# SATURDAY: D10's offboarding predicate is `last_day >= week_end`, which is only
# correct if the last day of the week is the Saturday rather than the next Sunday.
_DAYS_IN_WEEK = 7


class ShiftsValidationError(DomainValidationError):
    """Domain-rule violation on a shifts write; the platform's shipped handler
    maps it to the house-shape 400 carrying this message. No new handler."""


class WeekOutOfRangeError(Exception):
    """The named week is outside D1's window, or a write named a week that has
    already begun. 400 `WEEK_OUT_OF_RANGE`.

    ⚠ Deliberately NOT a `DomainValidationError` subclass, `ReservationOverlapError`'s
    recorded rule: Starlette walks `type(exc).__mro__`, so a subclass shipped
    without its own handler would answer a quiet, plausible `VALIDATION_ERROR`
    400 instead of a loud 500 — and the console would render a generic message
    where it has a specific Hebrew one keyed on the code.
    """


class TemplateLimitReachedError(Exception):
    """`MAX_TEMPLATES_PER_DAY` or `MAX_TEMPLATES` reached. 400
    `TEMPLATE_LIMIT_REACHED`. Same non-subclassing rule as `WeekOutOfRangeError`."""


def current_week_start(today: datetime.date) -> datetime.date:
    """The Sunday that opens the week `today` falls in, in the boutique's own
    calendar. `jerusalem_day_index` is 0=Sunday, so subtracting it walks back to
    Sunday and is a no-op on a Sunday."""
    return today - datetime.timedelta(days=jerusalem_day_index(today))


def week_end(week_start: datetime.date) -> datetime.date:
    """INCLUSIVE — the Saturday. See `_DAYS_IN_WEEK`."""
    return week_start + datetime.timedelta(days=_DAYS_IN_WEEK - 1)


def default_week_start(today: datetime.date) -> datetime.date:
    """The week a staffer opening the section with no parameter is here to
    answer (D1): NEXT week, never this one. The current week has begun and F40
    publishes before a week starts."""
    return current_week_start(today) + datetime.timedelta(days=_DAYS_IN_WEEK)


def validate_week_start(value: datetime.date) -> datetime.date:
    """A week key is a Jerusalem SUNDAY and nothing else.

    The DB carries the same rule as `staff_availability_week_start_check`, so
    deleting this guard does not open the door — which is exactly what
    `test_shifts_db.py` drives. Two guards, because this one produces a Hebrew
    400 and that one produces a `psycopg` error nobody should ever see.
    """
    if jerusalem_day_index(value) != 0:
        raise ShiftsValidationError("week_start must be a Sunday")
    return value


def assert_readable_week(week_start: datetime.date, *, current: datetime.date) -> None:
    validate_week_start(week_start)
    validate_week_start(current)
    delta_weeks = (week_start - current).days // _DAYS_IN_WEEK
    if abs(delta_weeks) > SUBMISSION_WEEK_WINDOW_WEEKS:
        raise WeekOutOfRangeError


def assert_writable_week(week_start: datetime.date, *, current: datetime.date) -> None:
    """Everything `assert_readable_week` requires, PLUS forward-only.

    A past week is readable — she may look at what she said — and never writable:
    recording availability into a running week is F40's roster-edit problem, and
    F39 building a second write path into it would be the coverage surface this
    spec keeps out.
    """
    assert_readable_week(week_start, current=current)
    if week_start <= current:
        raise WeekOutOfRangeError


def validate_template(
    *,
    day_of_week: int,
    label: str,
    starts_at_time: datetime.time,
    ends_at_time: datetime.time,
) -> str:
    """Returns the TRIMMED label, so the caller cannot store the untrimmed one it
    passed in — `validate_profile`'s shape.

    ⚠ NO OVERLAP RULE, deliberately, and this is the one place F39 departs from
    `validate_weekly_rules`. A morning 09:00–14:00 and an afternoon 13:00–20:00
    sharing the changeover hour is an ordinary split shift, and refusing it makes
    the owner fudge her real times. Coverage arithmetic over overlapping shifts
    is F40's problem to state, not this feature's to prevent (O3).
    """
    if not 0 <= day_of_week <= 6:
        raise ShiftsValidationError("day_of_week must be between 0 and 6")
    trimmed = label.strip()
    if not trimmed:
        raise ShiftsValidationError("label must not be blank")
    if len(trimmed) > MAX_SHIFT_LABEL_LENGTH:
        raise ShiftsValidationError("label is too long")
    # No overnight shift — the same rule `shift_templates_order_check` carries.
    if ends_at_time <= starts_at_time:
        raise ShiftsValidationError("ends_at_time must be after starts_at_time")
    return trimmed


def assert_template_capacity(*, day_count: int, total_count: int) -> None:
    """`day_count` and `total_count` are the LIVE counts BEFORE the insert."""
    if day_count >= MAX_TEMPLATES_PER_DAY or total_count >= MAX_TEMPLATES:
        raise TemplateLimitReachedError


def validate_state(value: str) -> AvailabilityState:
    """⚠ `pending` in particular is a 400 and never a row. It is the console's
    fourth radio «לא נרשם» — the rendered NAME of an absent row (D8) — and
    selecting it OMITS the template from the PUT rather than storing a value."""
    try:
        return AvailabilityState(value)
    except ValueError:
        raise ShiftsValidationError(f"unknown availability state: {value}") from None


def deadline_at(
    week_start: datetime.date,
    *,
    day_of_week: int,
    deadline_time: datetime.time,
) -> datetime.datetime:
    """The UTC instant at which `week_start`'s submissions close (D5/D6).

    ⚠ A WEEKDAY AND A LOCAL TIME, RESOLVED PER WEEK — never a stored instant.
    That is the `user_preferences` shape `TIMEZONE.md` prescribes and it is here
    for its exact reason: "18:00 Wednesday" is `16:00Z` in winter and `15:00Z` in
    summer, so a stored UTC value drifts an hour twice a year and the lock fires
    at the wrong minute for half the year. `test_shifts_validation.py`'s
    January/July pair is the guard, and a naive implementation passes exactly one
    of the two.

    The deadline day is the named weekday in the week PRECEDING `week_start`, so
    the default Wednesday 18:00 leaves Thursday–Saturday to build the roster
    before Sunday.
    """
    validate_week_start(week_start)
    if not 0 <= day_of_week <= 6:
        raise ShiftsValidationError("submission_deadline_day_of_week must be between 0 and 6")
    deadline_date = week_start - datetime.timedelta(days=_DAYS_IN_WEEK - day_of_week)
    local = datetime.datetime.combine(deadline_date, deadline_time, tzinfo=BOUTIQUE_TIMEZONE)
    return local.astimezone(datetime.UTC)
