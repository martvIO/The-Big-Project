"""The dashboard's arithmetic: one window derivation and six pure folds.

Everything above `DashboardService` is pure — dates and frozen dataclasses in,
values out, no session and no clock — because D3's argument is that the six
metric DEFINITIONS are where this feature can be silently wrong, and a pure fold
over a list of frozen records is pinned by `tests/test_dashboard_math.py` in the
fast no-Docker suite. A SQL-side `GROUP BY` would only ever be exercised from a
`db`-marked module that first runs on CI.

They live here rather than in a fourth module because that is a property of the
FUNCTIONS, not of the file, and they are module-level rather than methods
because a method needing `self` for nothing is what makes a pure test awkward.
"""

import dataclasses
import datetime
from collections import Counter
from collections.abc import Mapping, Sequence
from uuid import UUID

from app.booking.validation import jerusalem_day_index
from app.dashboard.schemas import (
    AppointmentTypeCount,
    CustomerMix,
    HistoryPanel,
    StatusTotals,
    WeekBucket,
)
from app.db.repositories.bookings import BookingFact, CustomerHistory
from app.models.constants import BookingCancelledBy, BookingStatus
from app.storefront.validation import BOUTIQUE_TIMEZONE

# One quarter, twelve bars — the smallest window that shows a season.
HISTORY_WEEKS = 12

# The forward panel's span, INCLUSIVE of today: [today, today + 6].
FORWARD_WINDOW_DAYS = 7

TOP_APPOINTMENT_TYPES = 5


@dataclasses.dataclass(frozen=True)
class HistoryWindow:
    """The twelve complete Sunday-start weeks behind `today`, as both calendar
    dates and the half-open UTC instant pair the projection reads."""

    first_week_start: datetime.date
    current_week_start: datetime.date
    from_instant: datetime.datetime
    until_instant: datetime.datetime


def history_window(today: datetime.date) -> HistoryWindow:
    """The last `HISTORY_WEEKS` COMPLETE Israeli weeks, ending last Saturday.

    Every edge is advanced in DATE space and converted to UTC exactly once.
    Israel's autumn transition is always a Sunday — the first day of the Israeli
    week — so one bucket a year is 169 UTC hours and one is 167:
    `midnight_utc(2026-10-25) + 7 days` is `2026-10-31T21:00Z` while the real
    boundary is `22:00Z`. Advancing on instants misfiles an hour of
    Saturday-night bookings twice a year. This is `list_day`'s lesson
    (`booking/owner.py:150-178`) applied one unit up.

    The current, in-progress week is excluded: a partial final bar reads as a
    collapse, and a rate computed over future appointments is skewed by
    construction — a future booking cannot yet be a no-show.

    **No `date.min`/`date.max` guard, unlike `OwnerBookingService.list_day`
    (`booking/owner.py:163-172`) and `slot_window` (`storefront/service.py:288-299`).**
    No caller-supplied date reaches this arithmetic; `today` comes from a real
    clock and can never approach either end of the `date` range. That is the
    reason the endpoint takes no parameters — a later `?weeks=` would silently
    break it.
    """
    current_week_start = today - datetime.timedelta(days=jerusalem_day_index(today))
    first_week_start = current_week_start - datetime.timedelta(days=7 * HISTORY_WEEKS)
    return HistoryWindow(
        first_week_start=first_week_start,
        current_week_start=current_week_start,
        from_instant=_boutique_midnight(first_week_start),
        until_instant=_boutique_midnight(current_week_start),
    )


def week_buckets(window: HistoryWindow, facts: Sequence[BookingFact]) -> list[WeekBucket]:
    """`HISTORY_WEEKS` buckets, ascending and ZERO-FILLED, counting the
    non-cancelled seat-slots the boutique held.

    Zero-filled so a week with no bookings is a `0` bar and not a missing one.
    The buckets are pre-generated from `window.first_week_start`, so a fact that
    keys outside them — the current in-progress week, say — is counted nowhere
    rather than appended as a thirteenth bar.
    """
    counts = {
        window.first_week_start + datetime.timedelta(days=7 * i): 0 for i in range(HISTORY_WEEKS)
    }
    for fact in facts:
        if fact.status == BookingStatus.CANCELLED.value:
            continue
        bucket = _week_start_of(fact.starts_at)
        if bucket in counts:
            counts[bucket] += 1
    return [WeekBucket(week_start=start, bookings=counts[start]) for start in sorted(counts)]


def status_totals(facts: Sequence[BookingFact]) -> StatusTotals:
    """All four CHECK-pinned statuses, counted once.

    `sum(week_buckets(...).bookings) == confirmed + no_show + completed` is the
    consistency invariant `build_history` is pure-tested against — a no-show
    still occupied its seat, and only a cancellation freed one.
    """
    counts = Counter(fact.status for fact in facts)
    return StatusTotals(
        confirmed=counts[BookingStatus.CONFIRMED.value],
        cancelled=counts[BookingStatus.CANCELLED.value],
        no_show=counts[BookingStatus.NO_SHOW.value],
        completed=counts[BookingStatus.COMPLETED.value],
    )


def cancellation(facts: Sequence[BookingFact]) -> tuple[float | None, int, int]:
    """`(rate, by_customer, by_owner)` — the rate over ALL FOUR statuses.

    Attribution is free: `cancelled_by` is already in the projection and
    CHECK-pinned to `('customer','owner')`, with `BookingsRepository.cancel` as
    its only writer. Without it a boutique that closed for a week and cancelled
    twenty appointments itself reads its own closure as customer flakiness.

    Both counts are guarded on `status = 'cancelled'`, which is what makes
    `by_customer + by_owner <= status_totals.cancelled` hold structurally. It is
    `<=` and not `==`: a row cancelled before migration 0010 added the column
    carries NULL and is in neither bucket (Risk 11).
    """
    cancelled = [fact for fact in facts if fact.status == BookingStatus.CANCELLED.value]
    attributed = Counter(fact.cancelled_by for fact in cancelled)
    rate = len(cancelled) / len(facts) if facts else None
    return (
        rate,
        attributed[BookingCancelledBy.CUSTOMER.value],
        attributed[BookingCancelledBy.OWNER.value],
    )


def no_show_rate(totals: StatusTotals) -> float | None:
    """No-shows over the appointments whose outcome was ACTUALLY RECORDED.

    Every booking in the window is in the past, so a row still reading
    `confirmed` is one the owner never classified — `no_show` and `completed`
    are the only two verbs that record an outcome. Counting the unmarked ones as
    attended silently rewards owners who never open the console, so they are
    excluded and `status_totals.confirmed` ships beside this number as the
    unclassified count (D5, Risk 5).

    Deliberately NOT derived from `attendance_confirmed_at IS NULL`: that column
    means the bride tapped her reminder link, not that she came
    (`db/repositories/bookings.py` — `set_status`'s docstring names the
    distinction), and most people never tap SMS links.
    """
    recorded = totals.no_show + totals.completed
    return totals.no_show / recorded if recorded else None


def top_types(facts: Sequence[BookingFact]) -> list[AppointmentTypeCount]:
    """The `TOP_APPOINTMENT_TYPES` busiest types: group by ID, label from the
    snapshot with the greatest `created_at`, non-cancelled only.

    **No join to `appointment_types`.** Both available keys are lossy alone and
    the failures are mirror images — joining `list_active` drops any type
    archived during the window, while grouping on the snapshot `name` splits one
    renamed type into two rows AND merges two different types when a name freed
    by archiving is reused (the unique index is partial on `deleted_at IS NULL`
    precisely so reuse is legal).

    **`max(created_at)`, not `max(starts_at)`.** The name is snapshotted when
    the booking is WRITTEN, so `starts_at` orders by appointment date: rename
    the type on 1 June, and a booking created 1 May for 20 July carries the old
    name while one created 15 June for 20 May carries the new one.
    `max(starts_at)` renders the label every booking made since June has
    already stopped using.

    **`status != 'cancelled'`** — the same predicate `week_buckets` and the
    cohort use (C2). The deck reuses «תורים שלא בוטלו» as this table's count
    header, and three predicates on one screen would show up as a type count
    higher than the sum of the bars above it.

    The sort key `(-count, name, str(id))` is TOTAL. Count and name are both
    ties for two reused-name IDs at equal counts, and D3's statement carries no
    `ORDER BY`, so without the third element the order is whatever Postgres
    happened to return — which can differ across plans, vacuums or restarts.
    """
    counts: Counter[UUID] = Counter()
    newest: dict[UUID, BookingFact] = {}
    for fact in facts:
        if fact.status == BookingStatus.CANCELLED.value:
            continue
        counts[fact.appointment_type_id] += 1
        seen = newest.get(fact.appointment_type_id)
        if seen is None or fact.created_at > seen.created_at:
            newest[fact.appointment_type_id] = fact
    rows = [
        AppointmentTypeCount(
            appointment_type_id=type_id,
            name=newest[type_id].appointment_type_name,
            bookings=count,
        )
        for type_id, count in counts.items()
    ]
    rows.sort(key=lambda row: (-row.bookings, row.name, str(row.appointment_type_id)))
    return rows[:TOP_APPOINTMENT_TYPES]


def customer_mix(
    facts: Sequence[BookingFact],
    history: Mapping[UUID, CustomerHistory],
    *,
    from_instant: datetime.datetime,
) -> CustomerMix:
    """The cohort — distinct `customer_id` on NON-CANCELLED facts — split into
    new and returning, plus the lifetime repeat rate.

    A bride who booked and cancelled did not visit, so she is not in the cohort.
    "First-ever" and "ever" are both evaluated as of the window's right edge (the
    `history` read's own bound), so a fitting booked for next month cannot
    retroactively change last quarter's numbers.

    `new` and `repeat_rate` are genuinely different questions and both ship: a
    bride who booked twice inside the window is NEW (her first-ever booking is
    in it) and COUNTS toward the repeat rate (she has two). One is cohort
    composition, the other is retention.

    A cohort member missing from `history` cannot happen through
    `DashboardService` — the cohort ids are what the history read is called
    with — so her in-window facts stand in rather than raising a KeyError on the
    console's most-hit read.
    """
    first_in_window: dict[UUID, datetime.datetime] = {}
    seen_in_window: Counter[UUID] = Counter()
    for fact in facts:
        if fact.status == BookingStatus.CANCELLED.value:
            continue
        seen_in_window[fact.customer_id] += 1
        earliest = first_in_window.get(fact.customer_id)
        if earliest is None or fact.starts_at < earliest:
            first_in_window[fact.customer_id] = fact.starts_at

    total = len(seen_in_window)
    new = 0
    repeat = 0
    for customer_id, in_window_count in seen_in_window.items():
        entry = history.get(customer_id)
        first_ever = entry.first_starts_at if entry is not None else first_in_window[customer_id]
        lifetime = entry.bookings if entry is not None else in_window_count
        if first_ever >= from_instant:
            new += 1
        if lifetime >= 2:
            repeat += 1
    return CustomerMix(
        total=total,
        new=new,
        returning=total - new,
        repeat_rate=repeat / total if total else None,
    )


def build_history(
    window: HistoryWindow,
    facts: Sequence[BookingFact],
    history: Mapping[UUID, CustomerHistory],
) -> HistoryPanel:
    """The whole history panel from one projection — the folds' single entry
    point, so the shape invariants have one call to assert against.

    The window filter is re-applied here even though `list_window_facts` reads
    exactly this range in SQL. That is what makes D2's exclusion of the current,
    in-progress week provable in the FAST suite: without it the assertion would
    only exist inside a `db`-marked module that first runs on CI, which is the
    arrangement D3 exists to avoid.
    """
    in_window = [
        fact for fact in facts if window.from_instant <= fact.starts_at < window.until_instant
    ]
    totals = status_totals(in_window)
    rate, by_customer, by_owner = cancellation(in_window)
    return HistoryPanel(
        from_date=window.first_week_start,
        to_date=window.current_week_start - datetime.timedelta(days=1),
        weeks=week_buckets(window, in_window),
        status_totals=totals,
        cancellation_rate=rate,
        cancelled_by_customer=by_customer,
        cancelled_by_owner=by_owner,
        no_show_rate=no_show_rate(totals),
        appointment_types=top_types(in_window),
        customers=customer_mix(in_window, history, from_instant=window.from_instant),
    )


def _week_start_of(instant: datetime.datetime) -> datetime.date:
    """The Sunday of the JERUSALEM calendar date this instant falls on.

    Two lines, and neither touches a UTC calendar date: an appointment at
    21:30Z in July is already the next day in Israel, and filing it by its UTC
    date would put it in the previous bucket.
    """
    day = instant.astimezone(BOUTIQUE_TIMEZONE).date()
    return day - datetime.timedelta(days=jerusalem_day_index(day))


def _boutique_midnight(day: datetime.date) -> datetime.datetime:
    return datetime.datetime.combine(day, datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE).astimezone(
        datetime.UTC
    )
