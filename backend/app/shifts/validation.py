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
from typing import Any

from app.booking.validation import jerusalem_day_index
from app.boutique.validation import SCHEDULING_DEFAULTS
from app.errors import DomainValidationError
from app.models.constants import AvailabilityState, OnShiftSource, StaffRole
from app.models.shift_template import ShiftTemplate
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

# F40 D10. ⚠ A GUARD AGAINST A FAT FINGER, NOT A PRODUCT RULE (spec O3): no
# boutique in this pilot has twenty of anything on one shift, and the number
# exists so a stray keypress cannot store 200. It is a constant and not a
# migration, so it moves without one — which is exactly why the console
# INTERPOLATES it into its Hebrew bound message rather than typing «20» there
# (design F-33), and why the server's own error string carries `{{max}}`.
MAX_COVERAGE_TARGET = 20


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


class CoverageTargetInvalidError(Exception):
    """F40 D10: an unknown role key, a non-integer, or a number outside
    `0..MAX_COVERAGE_TARGET`. 400 `COVERAGE_TARGET_INVALID`.

    Same non-subclassing rule as `WeekOutOfRangeError` and for its reason: the
    console has a specific Hebrew sentence keyed on this code, and a
    `DomainValidationError` subclass without its own handler would answer a
    quiet, plausible `VALIDATION_ERROR` 400 the console has no string for.
    """


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


def scheduling_pair(settings: dict[str, Any]) -> tuple[int, datetime.time]:
    """The tenant's `(deadline weekday, local time)`, default-complete.

    ⚠ READ OFF `TenantContext.settings`, WHICH THE MIDDLEWARE HAS ALREADY BOUND
    — `AtelierService`'s shipped rule for its effort bands. `TenantsRepository`
    is constructed with a `session_factory` and opens its own session inside every
    method, so reading it there would cost a second pool checkout and BEGIN/COMMIT
    on every week load, for two values that are already in hand.

    The overlay is `{**SCHEDULING_DEFAULTS, **stored}` and not `.get(..., default)`
    per field: a blob hand-edited to hold one of the two keys must still resolve
    to a complete pair, because a missing deadline cannot be allowed to read as
    «no deadline» on a surface whose whole job is to lock.
    """
    stored = settings.get("scheduling")
    block = {**SCHEDULING_DEFAULTS, **(stored if isinstance(stored, dict) else {})}
    day_of_week = block["submission_deadline_day_of_week"]
    if not isinstance(day_of_week, int) or isinstance(day_of_week, bool):
        raise ShiftsValidationError("submission_deadline_day_of_week must be an integer")
    try:
        deadline_time = datetime.time.fromisoformat(str(block["submission_deadline_time"]))
    except ValueError:
        raise ShiftsValidationError("submission_deadline_time must be HH:MM") from None
    return day_of_week, deadline_time


def jerusalem_moment(at: datetime.datetime) -> tuple[datetime.date, datetime.time, int]:
    """A UTC instant, converted to the boutique's wall clock ONCE (F40 D14).

    Returns `(local_date, local_time, day_index)` together rather than three
    helpers, because the whole DST argument depends on there being exactly one
    conversion: `astimezone` picks exactly one local wall time for any UTC
    instant, so the direction instant → local is ALWAYS unambiguous, including
    inside the autumn fold. Two conversions, taken a microsecond apart across a
    boundary, is how a date and a time start disagreeing about which day it is.

    ⚠ THE BOUTIQUE'S WALL CLOCK IS THE AUTHORITY, and that is a decision rather
    than a convenience. A 25-hour Jerusalem day has one hour whose clock reads
    01:xx twice, and both instants are correctly inside a shift covering 01:00 —
    the boutique was open for both. A 23-hour day has no local 02:xx at all, so a
    shift spanning it is one real hour shorter, which is also correct. Storing
    UTC instants per shift instead would need a per-week materialisation and
    would drift an hour twice a year (F39 D6's argument, second instance).

    Neither `BOUTIQUE_TIMEZONE` nor `jerusalem_day_index` is re-derived here —
    both are imported, for the reason this module's header already states.
    """
    local = at.astimezone(BOUTIQUE_TIMEZONE)
    local_date = local.date()
    return local_date, local.time(), jerusalem_day_index(local_date)


def template_covers(template: ShiftTemplate, *, local_time: datetime.time, day_index: int) -> bool:
    """Does this shift contain that Jerusalem wall-clock moment (F40 D14)?

    ⚠ HALF-OPEN: `starts_at_time <= local_time < ends_at_time`, and the `<` on
    the right end is the decision. F39 permits overlapping templates on one
    weekday (its D2), so a back-to-back 09:00–14:00 and 14:00–20:00 pair BOTH
    contain 14:00 under a closed interval and the board would credit the outgoing
    staffer with the incoming shift. `<` is what makes a handover instantaneous.

    NO WRAPAROUND, because `shift_templates_order_check` bars
    `ends_at_time <= starts_at_time` — there is no overnight shift to split
    across two dates.

    Overlapping templates that both cover an instant are legal and produce ONE
    answer: the caller ORs them, and a boolean cannot be double-counted.
    """
    return (
        template.day_of_week == day_index
        and template.starts_at_time <= local_time < template.ends_at_time
    )


def on_shift_at(
    *,
    override_on: datetime.date | None,
    override_value: bool | None,
    roster_published: bool,
    rostered_now: bool,
    local_date: datetime.date,
) -> tuple[bool, OnShiftSource]:
    """Is she on shift, and WHICH RULE SAID SO (F40, spec D2).

        1. override_on == local_date  ->  (override_value, MANUAL_TODAY)
        2. roster_published           ->  (rostered_now,   ROSTER)
        3. otherwise                  ->  (True,           FALLBACK)

    ⚠ THE TUPLE IS THE POINT. The answer and the rule are computed together, so
    they cannot disagree — the console maps the source through a `Record` with no
    fallback and prints one of three Hebrew phrases beside the answer, on a
    shared floor tablet two women read at once.

    ⚠ RULE 2 KEYS ON THE EXISTENCE OF A PUBLISHED ROSTER, NEVER ON ASSIGNMENTS
    (D5). "Published with nobody on this shift" is `(False, ROSTER)` — she is
    genuinely not on, the owner said so by publishing a week that does not
    include her — while "no roster published" is `(True, FALLBACK)`, because the
    boutique has not told the system anything and the system does not pretend to
    know. Deriving `roster_published` from `EXISTS(assignments)` collapses the
    two in the dangerous direction: an owner who publishes a genuinely empty
    Saturday would find the whole boutique reported as on shift.

    ⚠ RULE 3 IS TODAY'S EXACT BEHAVIOUR (spec C1). There is no F31 flag being
    demoted — what is demoted is LIVENESS as an implicit on-shift claim, so a
    boutique that never publishes and never overrides sees no change at all.

    ⚠ NO COMPARISON AGAINST `published_at`, deliberately (D3). The epic phrases
    rule 1 as "a same-day flag set AFTER the roster was published wins", and that
    comparison causes a concrete failure: the owner marks Dana off for Sunday at
    08:00, edits THURSDAY's shift at 15:00 and republishes, `published_at` moves
    past Dana's flag, and Dana silently reappears as on-shift for the rest of
    Sunday. Scoping the override to a Jerusalem calendar DATE delivers the whole
    of what that comparison was reaching for, with no clock arithmetic to get
    wrong.

    `override_value is not None` narrows the pair rather than trusting it: the DB
    CHECK makes a half-written pair unreachable, and a function that returned
    `None` where the wire promises a boolean would be a 500 on the floor board.
    """
    if override_value is not None and override_on == local_date:
        return override_value, OnShiftSource.MANUAL_TODAY
    if roster_published:
        return rostered_now, OnShiftSource.ROSTER
    return True, OnShiftSource.FALLBACK


def validate_coverage_targets(value: object) -> dict[str, int]:
    """D10's sparse map: `{"sales_assistant": 2, "seamstress": 1}`.

    ⚠ SPARSE, AND THE SPARSENESS CARRIES MEANING. An ABSENT key is «no target»
    and renders as a plain count; `0` is «deliberately nobody» and renders as a
    target with a «חסר איוש» badge the moment somebody is assigned. They are not
    the same fact, so a validator that dropped falsy values would silently
    destroy the second — which is why every branch below preserves `0`.

    ⚠ `bool` IS A SUBCLASS OF `int`, so `isinstance(True, int)` is True and a
    naive check stores «1 seamstress» for a client that sent `true`. F39's
    `AtelierSettingsUpdate` finding, verbatim reason, and the reason the type
    test is spelled as two clauses rather than one.

    Keys are validated against `StaffRole` rather than a curated subset, so a
    sixth role is a legal target the day it exists (`lib/roles.ts`' own
    guarantee, kept on the server side too).
    """
    if not isinstance(value, dict):
        raise CoverageTargetInvalidError
    known = {member.value for member in StaffRole}
    validated: dict[str, int] = {}
    for key, target in value.items():
        if key not in known:
            raise CoverageTargetInvalidError
        if isinstance(target, bool) or not isinstance(target, int):
            raise CoverageTargetInvalidError
        if not 0 <= target <= MAX_COVERAGE_TARGET:
            raise CoverageTargetInvalidError
        validated[key] = target
    return validated
