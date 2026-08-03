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
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.booking.slots_io import forward_capacity
from app.booking.validation import jerusalem_day_index
from app.dashboard.schemas import (
    AppointmentTypeCount,
    CustomerMix,
    DashboardResponse,
    ForwardPanel,
    HistoryPanel,
    StatusTotals,
    WeekBucket,
)
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.bookings import BookingFact, BookingsRepository, CustomerHistory
from app.db.tenant import tenant_session
from app.models.constants import BookingCancelledBy, BookingStatus
from app.storefront.validation import BOUTIQUE_TIMEZONE, Clock, today_jerusalem

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


def status_totals(facts: Sequence[BookingFact], *, pending_payment: int = 0) -> StatusTotals:
    """All five CHECK-pinned statuses, counted once.

    `sum(week_buckets(...).bookings) == confirmed + no_show + completed` is the
    consistency invariant `build_history` is pure-tested against — a no-show
    still occupied its seat, and only a cancellation freed one.

    `pending_payment` is PASSED IN rather than counted, because
    `DashboardService.dashboard` filters those rows out of `facts` before any
    fold sees them (D14): counting here would answer zero forever. Taking the
    unfiltered count as an argument is what keeps the number visible while
    keeping a live checkout out of the invariant above.
    """
    counts = Counter(fact.status for fact in facts)
    return StatusTotals(
        confirmed=counts[BookingStatus.CONFIRMED.value],
        cancelled=counts[BookingStatus.CANCELLED.value],
        no_show=counts[BookingStatus.NO_SHOW.value],
        completed=counts[BookingStatus.COMPLETED.value],
        pending_payment=pending_payment,
    )


def cancellation(facts: Sequence[BookingFact]) -> tuple[float | None, int, int]:
    """`(rate, by_customer, by_owner)` — the rate over every status the panel
    counts, which is the four real outcomes: `pending_payment` never reaches
    this fold (D14) and `cancelled_by = 'expired'` is dropped below (MD5).

    Attribution is free: `cancelled_by` is already in the projection and
    CHECK-pinned to `('customer','owner')`, with `BookingsRepository.cancel` as
    its only writer. Without it a boutique that closed for a week and cancelled
    twenty appointments itself reads its own closure as customer flakiness.

    Both counts are guarded on `status = 'cancelled'`, which is what makes
    `by_customer + by_owner <= status_totals.cancelled` hold structurally. It is
    `<=` and not `==`: a row cancelled before migration 0010 added the column
    carries NULL and is in neither bucket (Risk 11). F19 widens that gap on
    purpose — an expired hold is `cancelled` in the totals and in neither
    attribution bucket nor this rate.

    **MD5: `cancelled_by = 'expired'` is in NEITHER the numerator NOR the
    denominator.** Freeing an abandoned checkout means writing
    `status = 'cancelled'` (D2 — the only writer that frees a seat), so the row
    arrives here already reading `cancelled`; filtering `pending_payment`
    upstream does nothing for it, because it is a different row in a different
    state. Left in, the owner reads "31%" where the truth is "8% plus twelve
    checkouts that were never appointments", and she steers the boutique on the
    wrong number. The exclusion has to reach the DENOMINATOR too — dropping it
    from the numerator alone is the half that silently changes nothing.
    """
    counted = [fact for fact in facts if fact.cancelled_by != BookingCancelledBy.EXPIRED.value]
    cancelled = [fact for fact in counted if fact.status == BookingStatus.CANCELLED.value]
    attributed = Counter(fact.cancelled_by for fact in cancelled)
    rate = len(cancelled) / len(counted) if counted else None
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
    *,
    pending_payment: int = 0,
) -> HistoryPanel:
    """The whole history panel from one projection — the folds' single entry
    point, so the shape invariants have one call to assert against.

    `facts` is expected to carry NO `pending_payment` rows: its caller strips
    them once, before the cohort fold (D14). This function does not re-strip
    them, because the whole point of the single filter is that no fold owns the
    predicate — the count arrives as `pending_payment` instead.

    The window filter is re-applied here even though `list_window_facts` reads
    exactly this range in SQL. That is what makes D2's exclusion of the current,
    in-progress week provable in the FAST suite: without it the assertion would
    only exist inside a `db`-marked module that first runs on CI, which is the
    arrangement D3 exists to avoid.
    """
    in_window = [
        fact for fact in facts if window.from_instant <= fact.starts_at < window.until_instant
    ]
    totals = status_totals(in_window, pending_payment=pending_payment)
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


class DashboardService:
    """The console's landing read: five statements and one grid, in one
    tenant-scoped transaction.

    **Its own clock**, resolved with the house one-liner (`booking/owner.py`);
    it never borrows `StorefrontService._clock`, and `create_app` wires none —
    the parameter exists so the `db` suite can freeze the window.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._bookings = BookingsRepository()
        self._rules = AvailabilityRulesRepository()
        self._exceptions = AvailabilityExceptionsRepository()

    def _now(self) -> datetime.datetime:
        now = self._clock() if self._clock is not None else datetime.datetime.now(datetime.UTC)
        return now.astimezone(datetime.UTC)

    async def dashboard(self, tenant_id: uuid.UUID) -> DashboardResponse:
        """THREE statements against `bookings` plus the two availability reads.

        The window projection and the cohort history are the two visible here;
        the third is `count_by_start`, issued inside `forward_capacity`. Counting
        it is the point — Risk 3's threshold is a per-request cost on the
        console's most-hit read, and a docstring that undercounts it is what a
        future maintainer would reason from.

        **No audit row.** No GET handler in this product writes one — not the
        booking day list, not the booking detail that renders a bride's phone
        and free-text notes, not the owner-only staff list. This is the
        most-hit read in the console, and auditing it would put a write on
        every page load (D9).
        """
        today = today_jerusalem(self._clock)
        window = history_window(today)
        # INCLUSIVE, so `today + 6` and never `today + 7`: the slot engine's
        # window is inclusive on both ends (`slots.py:116-117, 134`), so seven
        # days is six steps. `today + 7` would materialize eight days of
        # capacity into a metric labelled seven and inflate the denominator by
        # ~14% with nothing in the response to reveal the error. The +1 that
        # turns this into `count_by_start`'s half-open ceiling lives inside
        # `forward_capacity`, in one place, with the comment on it.
        forward_end = today + datetime.timedelta(days=FORWARD_WINDOW_DAYS - 1)
        async with tenant_session(self._session_factory, tenant_id) as session:
            window_facts = await self._bookings.list_window_facts(
                session,
                tenant_id,
                from_instant=window.from_instant,
                until_instant=window.until_instant,
            )
            # ONE predicate, HERE, for six consumers (D14). A checkout in
            # progress is not an appointment: counting it would make "bookings
            # last week" move as brides open and abandon payment pages.
            #
            # `list_window_facts` keeps its "EVERY status" contract — F20 and
            # F52 read it — so the predicate belongs at the consumer, and it
            # belongs ONCE. A `continue` per fold plus a field on StatusTotals
            # covers `week_buckets` and `status_totals` and leaves FOUR wrong:
            #   * `cancellation` divides by `len(facts)`, so a live checkout
            #     sits in the DENOMINATOR of the headline cancellation rate;
            #   * `top_types` counts an unpaid hold as a booking in the chart;
            #   * `customer_mix` puts a bride who never paid into the cohort;
            #   * the `cohort_ids` fold below sends her id to the history read
            #     and into the repeat-rate denominator.
            facts = [
                fact for fact in window_facts if fact.status != BookingStatus.PENDING_PAYMENT.value
            ]
            # The UNFILTERED count, the one number on the panel that is allowed
            # to see a checkout in progress (MD5's volume signal for Risk 3).
            pending_payment = len(window_facts) - len(facts)
            # The cohort `customer_mix` folds — distinct customer_id on
            # non-cancelled facts — so the history read is called with exactly
            # the ids it will be looked up by, and never with a wider set.
            cohort_ids = sorted(
                {fact.customer_id for fact in facts if fact.status != BookingStatus.CANCELLED.value}
            )
            history = await self._bookings.history_by_customer(
                session, tenant_id, cohort_ids, until_instant=window.until_instant
            )
            forward = await forward_capacity(
                session,
                tenant_id=tenant_id,
                window_start=today,
                window_end=forward_end,
                now=self._now(),
                rules=self._rules,
                exceptions=self._exceptions,
                bookings=self._bookings,
            )
        return DashboardResponse(
            generated_on=today,
            history=build_history(window, facts, history, pending_payment=pending_payment),
            forward=ForwardPanel(
                from_date=today,
                to_date=forward_end,
                capacity=forward.capacity,
                booked=forward.booked,
                utilization=forward.utilization,
            ),
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
