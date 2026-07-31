"""The pure half of the dashboard: the window arithmetic and the six folds.

No database, no `create_app`, no marker — this module runs in the fast suite,
and that is the whole point of D3. Every one of F52's metric DEFINITIONS is
pinned here; a SQL-side `GROUP BY` could only be exercised from a `db`-marked
module that first runs on CI, and the definitions are exactly where this
feature can be silently wrong.
"""

import datetime
import uuid

from app.booking.slots import Slot
from app.booking.slots_io import grid_totals
from app.booking.validation import jerusalem_day_index
from app.dashboard.schemas import WeekBucket
from app.dashboard.service import (
    HISTORY_WEEKS,
    TOP_APPOINTMENT_TYPES,
    build_history,
    cancellation,
    customer_mix,
    history_window,
    no_show_rate,
    status_totals,
    top_types,
    week_buckets,
)
from app.db.repositories.bookings import BookingFact, CustomerHistory
from app.models.constants import BookingStatus
from app.storefront.validation import BOUTIQUE_TIMEZONE

# Israel 2026: DST starts Fri 27 Mar (02:00→03:00), ends Sun 25 Oct (02:00→01:00).
# Both transitions are inside a Sunday-start bucket, never at its edge.
DST_SPRING_WEEK = datetime.date(2026, 3, 22)  # the 167-hour bucket
DST_AUTUMN_WEEK = datetime.date(2026, 10, 25)  # the 169-hour bucket

# Clocks chosen so the DST bucket is the LAST one in the window.
NORMATIVE_TODAY = datetime.date(2026, 7, 31)  # the spec's worked example, a Friday
SPRING_TODAY = DST_SPRING_WEEK + datetime.timedelta(days=7)
AUTUMN_TODAY = DST_AUTUMN_WEEK + datetime.timedelta(days=7)

A_TYPE = uuid.UUID("aaaaaaaa-0000-4000-8000-000000000001")
A_CUSTOMER = uuid.UUID("cccccccc-0000-4000-8000-000000000001")


def _boutique_midnight(day: datetime.date) -> datetime.datetime:
    return datetime.datetime.combine(day, datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE).astimezone(
        datetime.UTC
    )


def _utc(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> datetime.datetime:
    return datetime.datetime(year, month, day, hour, minute, tzinfo=datetime.UTC)


def _fact(
    starts_at: datetime.datetime,
    *,
    status: str = BookingStatus.CONFIRMED.value,
    created_at: datetime.datetime | None = None,
    cancelled_by: str | None = None,
    customer_id: uuid.UUID = A_CUSTOMER,
    appointment_type_id: uuid.UUID = A_TYPE,
    appointment_type_name: str = "מדידה",
) -> BookingFact:
    return BookingFact(
        starts_at=starts_at,
        # Default: booked a fortnight ahead. Every fixture that cares about the
        # created_at/starts_at ORDER passes both explicitly.
        created_at=created_at
        if created_at is not None
        else starts_at - datetime.timedelta(days=14),
        status=status,
        cancelled_by=cancelled_by,
        customer_id=customer_id,
        appointment_type_id=appointment_type_id,
        appointment_type_name=appointment_type_name,
    )


def _count_in(buckets: list[WeekBucket], week_start: datetime.date) -> int:
    return next(bucket.bookings for bucket in buckets if bucket.week_start == week_start)


# --- the window derivation ----------------------------------------------------
#
# The spec's worked example is normative and an off-by-one-week version of it
# survived a full review: every rate assertion further down is invariant to a
# uniform window shift, so the derivation needs its own frozen-clock test.


def test_the_window_matches_the_specs_normative_example() -> None:
    today = datetime.date(2026, 7, 31)  # a Friday
    assert jerusalem_day_index(today) == 5

    window = history_window(today)

    assert window.current_week_start == datetime.date(2026, 7, 26)
    assert window.first_week_start == datetime.date(2026, 5, 3)
    assert window.from_instant == _boutique_midnight(datetime.date(2026, 5, 3))
    assert window.until_instant == _boutique_midnight(datetime.date(2026, 7, 26))


def test_the_three_shape_invariants_hold_on_a_friday_a_sunday_and_a_saturday() -> None:
    for today in (
        datetime.date(2026, 7, 26),  # Sunday — current_week_start == today
        datetime.date(2026, 7, 31),  # Friday — the normative example
        datetime.date(2026, 8, 1),  # Saturday — the widest exclusion, six days
    ):
        window = history_window(today)
        from_date = window.first_week_start
        to_date = window.current_week_start - datetime.timedelta(days=1)
        last_bucket = window.first_week_start + datetime.timedelta(days=7 * (HISTORY_WEEKS - 1))

        assert to_date == from_date + datetime.timedelta(days=7 * HISTORY_WEEKS - 1)
        assert to_date < today
        assert last_bucket == today - datetime.timedelta(days=jerusalem_day_index(today) + 7)


def test_a_sunday_today_is_its_own_week_start() -> None:
    today = datetime.date(2026, 7, 26)
    assert jerusalem_day_index(today) == 0
    assert history_window(today).current_week_start == today


# --- the DST week spans -------------------------------------------------------
#
# This is the pair that red-fails if anyone advances a week edge with
# `+ timedelta(days=7)` on an INSTANT instead of on a date.


def test_the_autumn_bucket_is_169_utc_hours_long() -> None:
    edge = history_window(DST_AUTUMN_WEEK).until_instant
    next_edge = history_window(DST_AUTUMN_WEEK + datetime.timedelta(days=7)).until_instant

    assert next_edge - edge == datetime.timedelta(hours=169)


def test_the_spring_bucket_is_167_utc_hours_long() -> None:
    edge = history_window(DST_SPRING_WEEK).until_instant
    next_edge = history_window(DST_SPRING_WEEK + datetime.timedelta(days=7)).until_instant

    assert next_edge - edge == datetime.timedelta(hours=167)


def test_every_week_edge_is_a_boutique_midnight_across_a_dst_boundary() -> None:
    # The instants themselves, not just their difference: 21:00Z under DST and
    # 22:00Z under standard time, both midnight in Jerusalem.
    assert history_window(DST_AUTUMN_WEEK).until_instant == datetime.datetime(
        2026, 10, 24, 21, 0, tzinfo=datetime.UTC
    )
    assert history_window(DST_AUTUMN_WEEK + datetime.timedelta(days=7)).until_instant == (
        datetime.datetime(2026, 10, 31, 22, 0, tzinfo=datetime.UTC)
    )


# --- Sunday bucketing ---------------------------------------------------------
#
# The bucket key never touches a UTC instant: the Jerusalem calendar date first,
# then `jerusalem_day_index` back to that date's Sunday.


def test_a_sunday_a_friday_and_a_saturday_bucket_to_their_own_sunday() -> None:
    window = history_window(AUTUMN_TODAY)
    buckets = week_buckets(
        window,
        [
            _fact(_boutique_midnight(DST_AUTUMN_WEEK) + datetime.timedelta(hours=10)),
            _fact(_boutique_midnight(datetime.date(2026, 10, 31)) + datetime.timedelta(hours=10)),
        ],
    )

    assert _count_in(buckets, DST_AUTUMN_WEEK) == 2


def test_the_spring_forward_friday_buckets_to_its_sunday() -> None:
    window = history_window(SPRING_TODAY)
    spring_forward_friday = datetime.date(2026, 3, 27)
    assert jerusalem_day_index(spring_forward_friday) == 5

    buckets = week_buckets(
        window,
        [_fact(_boutique_midnight(spring_forward_friday) + datetime.timedelta(hours=10))],
    )

    assert _count_in(buckets, DST_SPRING_WEEK) == 1


def test_a_late_utc_evening_lands_in_the_jerusalem_bucket_not_the_utc_one() -> None:
    # 2026-07-18T21:30Z is Saturday in UTC and Sunday 00:30 in Jerusalem. The
    # UTC calendar date would file it one bucket earlier.
    window = history_window(NORMATIVE_TODAY)

    buckets = week_buckets(window, [_fact(_utc(2026, 7, 18, 21, 30))])

    assert _count_in(buckets, datetime.date(2026, 7, 19)) == 1
    assert _count_in(buckets, datetime.date(2026, 7, 12)) == 0


# --- the DST bucket edges -----------------------------------------------------


def test_the_169_hour_bucket_holds_both_its_edges_and_neither_neighbour() -> None:
    window = history_window(AUTUMN_TODAY)
    opens = _boutique_midnight(DST_AUTUMN_WEEK)  # 2026-10-24T21:00Z, still on DST
    closes = _boutique_midnight(DST_AUTUMN_WEEK + datetime.timedelta(days=7))  # 10-31T22:00Z
    minute = datetime.timedelta(minutes=1)

    buckets = week_buckets(
        window,
        [
            _fact(opens - minute),
            _fact(opens + minute),
            _fact(closes - minute),
            _fact(closes + minute),
        ],
    )

    assert _count_in(buckets, DST_AUTUMN_WEEK) == 2
    assert _count_in(buckets, DST_AUTUMN_WEEK - datetime.timedelta(days=7)) == 1
    # The fact a minute past the close is in the current, in-progress week.
    assert sum(bucket.bookings for bucket in buckets) == 3


def test_the_167_hour_bucket_holds_both_its_edges_and_neither_neighbour() -> None:
    window = history_window(SPRING_TODAY)
    opens = _boutique_midnight(DST_SPRING_WEEK)  # 2026-03-21T22:00Z, standard time
    closes = _boutique_midnight(DST_SPRING_WEEK + datetime.timedelta(days=7))  # 03-28T21:00Z
    minute = datetime.timedelta(minutes=1)

    buckets = week_buckets(
        window,
        [
            _fact(opens - minute),
            _fact(opens + minute),
            _fact(closes - minute),
            _fact(closes + minute),
        ],
    )

    assert _count_in(buckets, DST_SPRING_WEEK) == 2
    assert _count_in(buckets, DST_SPRING_WEEK - datetime.timedelta(days=7)) == 1
    assert sum(bucket.bookings for bucket in buckets) == 3


# --- zero-fill and ordering ---------------------------------------------------


def test_the_buckets_are_always_twelve_ascending_and_zero_filled() -> None:
    window = history_window(NORMATIVE_TODAY)

    buckets = week_buckets(window, [_fact(_utc(2026, 7, 20))])

    assert len(buckets) == HISTORY_WEEKS
    assert [bucket.week_start for bucket in buckets] == [
        window.first_week_start + datetime.timedelta(days=7 * i) for i in range(HISTORY_WEEKS)
    ]
    assert buckets[0].week_start == datetime.date(2026, 5, 3)
    assert buckets[-1].week_start == datetime.date(2026, 7, 19)
    assert buckets[-1].bookings == 1
    assert [bucket.bookings for bucket in buckets[:-1]] == [0] * (HISTORY_WEEKS - 1)


def test_an_empty_window_is_twelve_zero_bars_not_an_empty_list() -> None:
    buckets = week_buckets(history_window(NORMATIVE_TODAY), [])

    assert len(buckets) == HISTORY_WEEKS
    assert all(bucket.bookings == 0 for bucket in buckets)


def test_a_cancelled_booking_is_not_in_any_bar() -> None:
    # D5: the bar counts the seat-slots the boutique HELD. Cancellations are the
    # tile beside it; counting them here would double-count one event.
    window = history_window(NORMATIVE_TODAY)

    buckets = week_buckets(
        window,
        [
            _fact(_utc(2026, 7, 20), status=BookingStatus.CANCELLED.value, cancelled_by="customer"),
            _fact(_utc(2026, 7, 20), status=BookingStatus.NO_SHOW.value),
            _fact(_utc(2026, 7, 20), status=BookingStatus.COMPLETED.value),
        ],
    )

    assert _count_in(buckets, datetime.date(2026, 7, 19)) == 2


# --- status totals and the two rates ------------------------------------------


def test_status_totals_counts_all_four_statuses() -> None:
    totals = status_totals(
        [
            _fact(_utc(2026, 7, 20)),
            _fact(_utc(2026, 7, 20)),
            _fact(_utc(2026, 7, 21), status=BookingStatus.CANCELLED.value, cancelled_by="owner"),
            _fact(_utc(2026, 7, 22), status=BookingStatus.NO_SHOW.value),
            _fact(_utc(2026, 7, 23), status=BookingStatus.COMPLETED.value),
            _fact(_utc(2026, 7, 23), status=BookingStatus.COMPLETED.value),
            _fact(_utc(2026, 7, 23), status=BookingStatus.COMPLETED.value),
        ]
    )

    assert totals.confirmed == 2
    assert totals.cancelled == 1
    assert totals.no_show == 1
    assert totals.completed == 3


def test_an_empty_window_leaves_both_rates_not_computable() -> None:
    rate, by_customer, by_owner = cancellation([])

    assert rate is None
    assert (by_customer, by_owner) == (0, 0)
    assert no_show_rate(status_totals([])) is None


def test_a_window_with_only_confirmed_rows_is_zero_cancellation_and_no_no_show_rate() -> None:
    # The two are different facts: nothing was cancelled (0.0), and no outcome
    # was ever recorded, so the no-show rate has no denominator at all (None).
    facts = [_fact(_utc(2026, 7, 20)), _fact(_utc(2026, 7, 21))]

    rate, _, _ = cancellation(facts)

    assert rate == 0.0
    assert no_show_rate(status_totals(facts)) is None


def test_a_window_of_nothing_but_cancellations_is_a_rate_of_one() -> None:
    facts = [
        _fact(_utc(2026, 7, 20), status=BookingStatus.CANCELLED.value, cancelled_by="customer"),
        _fact(_utc(2026, 7, 21), status=BookingStatus.CANCELLED.value, cancelled_by="owner"),
    ]

    rate, _, _ = cancellation(facts)

    assert rate == 1.0
    assert no_show_rate(status_totals(facts)) is None


def test_the_cancellation_denominator_is_all_four_statuses() -> None:
    facts = [
        _fact(_utc(2026, 7, 20), status=BookingStatus.CANCELLED.value, cancelled_by="customer"),
        _fact(_utc(2026, 7, 21)),
        _fact(_utc(2026, 7, 22), status=BookingStatus.NO_SHOW.value),
        _fact(_utc(2026, 7, 23), status=BookingStatus.COMPLETED.value),
    ]

    rate, _, _ = cancellation(facts)

    assert rate == 0.25


def test_the_wire_carries_the_unrounded_quotient() -> None:
    # D5: the console does ALL the rounding, so a rate that renders under the
    # one-decimal floor is still distinguishable from a true zero here.
    facts = [_fact(_utc(2026, 7, 20), status=BookingStatus.CANCELLED.value, cancelled_by="owner")]
    facts += [_fact(_utc(2026, 7, 21)) for _ in range(112)]

    rate, _, _ = cancellation(facts)

    assert rate == 1 / 113


def test_the_no_show_denominator_is_recorded_outcomes_only() -> None:
    # Three no-shows, one completed, and forty unmarked appointments: 75%, not
    # 6.8%. Counting unmarked rows as attended would reward owners who never
    # touch the console.
    facts = [_fact(_utc(2026, 7, 20), status=BookingStatus.NO_SHOW.value) for _ in range(3)]
    facts += [_fact(_utc(2026, 7, 21), status=BookingStatus.COMPLETED.value)]
    facts += [_fact(_utc(2026, 7, 22)) for _ in range(40)]

    assert no_show_rate(status_totals(facts)) == 0.75


# --- cancellation attribution -------------------------------------------------


def test_cancellations_are_attributed_and_a_null_attribution_is_in_neither_bucket() -> None:
    # Risk 11: a row cancelled before migration 0010 added the column carries
    # NULL. The two counts are therefore NOT a partition of `cancelled`.
    facts = [
        _fact(_utc(2026, 7, 20), status=BookingStatus.CANCELLED.value, cancelled_by="customer"),
        _fact(_utc(2026, 7, 20), status=BookingStatus.CANCELLED.value, cancelled_by="customer"),
        _fact(_utc(2026, 7, 21), status=BookingStatus.CANCELLED.value, cancelled_by="owner"),
        _fact(_utc(2026, 7, 22), status=BookingStatus.CANCELLED.value, cancelled_by=None),
    ]

    _, by_customer, by_owner = cancellation(facts)
    totals = status_totals(facts)

    assert (by_customer, by_owner) == (2, 1)
    assert by_customer + by_owner < totals.cancelled
    assert by_customer + by_owner <= totals.cancelled


def test_an_attribution_on_a_row_that_is_not_cancelled_is_not_counted() -> None:
    # `cancel` is cancelled_by's only writer and it guards on status='confirmed',
    # but the <= invariant must hold on the CONTRACT, not on today's writers.
    facts = [
        _fact(_utc(2026, 7, 20), status=BookingStatus.COMPLETED.value, cancelled_by="owner"),
        _fact(_utc(2026, 7, 21), status=BookingStatus.CANCELLED.value, cancelled_by="owner"),
    ]

    _, by_customer, by_owner = cancellation(facts)

    assert (by_customer, by_owner) == (0, 1)
    assert by_customer + by_owner <= status_totals(facts).cancelled


# --- the appointment-type fold ------------------------------------------------
#
# Both available keys are lossy alone and the failures are mirror images:
# joining `list_active` drops a type archived mid-window, while grouping on the
# snapshot NAME splits a renamed type in two and merges two types that reused
# one freed name. So: group by id, label from the newest snapshot.

TYPE_ARCHIVED = uuid.UUID("11111111-0000-4000-8000-000000000001")
TYPE_REUSED = uuid.UUID("22222222-0000-4000-8000-000000000002")


def _escort(starts_at: datetime.datetime, type_id: uuid.UUID) -> BookingFact:
    """One booking of the type named «ליווי» — the name the archive frees and a
    second appointment_type_id then legally reuses."""
    return _fact(starts_at, appointment_type_id=type_id, appointment_type_name="ליווי")


def test_a_type_renamed_mid_window_is_one_row_labelled_from_the_newest_snapshot() -> None:
    # The rename lands on 1 June. `created_at` and `starts_at` order the two
    # bookings OPPOSITELY, which is the whole point of the fixture: under
    # max(starts_at) the label would be the name every booking made since June
    # has already stopped using.
    booked_in_may_for_july = _fact(
        _utc(2026, 7, 20),
        created_at=_utc(2026, 5, 1),
        appointment_type_name="מדידה",
    )
    booked_in_june_for_may = _fact(
        _utc(2026, 5, 20),
        created_at=_utc(2026, 6, 15),
        appointment_type_name="מדידת ערב",
    )

    rows = top_types([booked_in_may_for_july, booked_in_june_for_may])

    assert len(rows) == 1
    assert rows[0].appointment_type_id == A_TYPE
    assert rows[0].bookings == 2
    assert rows[0].name == "מדידת ערב"


def test_a_type_archived_during_the_window_keeps_its_row_and_its_name() -> None:
    # There is no join to `appointment_types` at all, so `list_active`'s
    # `deleted_at IS NULL` cannot drop anything here.
    rows = top_types(
        [
            _escort(_utc(2026, 7, 20), TYPE_ARCHIVED),
            _fact(_utc(2026, 7, 21), appointment_type_id=A_TYPE),
            _fact(_utc(2026, 7, 22), appointment_type_id=A_TYPE),
        ]
    )

    assert [(row.appointment_type_id, row.name, row.bookings) for row in rows] == [
        (A_TYPE, "מדידה", 2),
        (TYPE_ARCHIVED, "ליווי", 1),
    ]


def test_a_name_freed_by_archiving_and_reused_is_two_rows_not_one() -> None:
    # The unique index on appointment_types is partial on `deleted_at IS NULL`
    # exactly so that reuse is legal.
    rows = top_types(
        [
            _escort(_utc(2026, 7, 20), TYPE_ARCHIVED),
            _escort(_utc(2026, 7, 21), TYPE_ARCHIVED),
            _escort(_utc(2026, 7, 22), TYPE_REUSED),
        ]
    )

    assert len(rows) == 2
    assert {row.appointment_type_id for row in rows} == {TYPE_ARCHIVED, TYPE_REUSED}
    assert all(row.name == "ליווי" for row in rows)


def test_two_reused_name_ids_at_equal_counts_order_stably_under_a_reversed_input() -> None:
    # Count and name are BOTH ties here, and D3's statement carries no ORDER BY,
    # so without the str(id) third element the order falls through to `sorted`'s
    # stability over whatever row order Postgres happened to return.
    facts = [
        _escort(_utc(2026, 7, 20), TYPE_ARCHIVED),
        _escort(_utc(2026, 7, 21), TYPE_REUSED),
    ]

    forward = [row.appointment_type_id for row in top_types(facts)]
    reversed_ = [row.appointment_type_id for row in top_types(list(reversed(facts)))]

    assert forward == reversed_ == [TYPE_ARCHIVED, TYPE_REUSED]


def test_a_cancelled_booking_does_not_raise_its_types_count() -> None:
    # C2: one predicate for every count this screen labels «תורים שלא בוטלו».
    facts = [
        _fact(_utc(2026, 7, 20)),
        _fact(_utc(2026, 7, 21), status=BookingStatus.CANCELLED.value, cancelled_by="customer"),
    ]

    rows = top_types(facts)

    assert [row.bookings for row in rows] == [1]


def test_only_the_top_five_types_are_returned_highest_count_first() -> None:
    facts = []
    for index in range(7):
        type_id = uuid.UUID(f"33333333-0000-4000-8000-00000000000{index}")
        facts += [
            _fact(_utc(2026, 7, 20), appointment_type_id=type_id, appointment_type_name=f"t{index}")
            for _ in range(index + 1)
        ]

    rows = top_types(facts)

    assert len(rows) == TOP_APPOINTMENT_TYPES
    assert [row.bookings for row in rows] == [7, 6, 5, 4, 3]


def test_an_empty_window_has_no_type_rows() -> None:
    assert top_types([]) == []


# --- new vs returning vs repeat -----------------------------------------------
#
# D7: every number here is a fold over BOOKINGS. F15's phone-correction
# collision branch leaves customer rows with no bookings and customers whose
# `created_at` post-dates their own first visit, so a `customers`-derived answer
# looks right in dev and lies only at the tenants that used the remedy.

BRIDE_A = uuid.UUID("cccccccc-0000-4000-8000-00000000000a")
BRIDE_B = uuid.UUID("cccccccc-0000-4000-8000-00000000000b")

WINDOW_FROM = _boutique_midnight(datetime.date(2026, 5, 3))


def test_an_empty_window_has_no_cohort_and_no_repeat_rate() -> None:
    mix = customer_mix([], {}, from_instant=WINDOW_FROM)

    assert (mix.total, mix.new, mix.returning) == (0, 0, 0)
    assert mix.repeat_rate is None


def test_two_bookings_re_pointed_to_one_customer_are_one_cohort_member() -> None:
    facts = [
        _fact(_utc(2026, 5, 20), customer_id=BRIDE_A),
        _fact(_utc(2026, 7, 20), customer_id=BRIDE_A),
    ]
    history = {BRIDE_A: CustomerHistory(first_starts_at=_utc(2026, 5, 20), bookings=2)}

    mix = customer_mix(facts, history, from_instant=WINDOW_FROM)

    assert mix.total == 1
    # She booked twice INSIDE the window, so she is new AND counts toward the
    # repeat rate: cohort composition and retention are different questions.
    assert (mix.new, mix.returning) == (1, 0)
    assert mix.repeat_rate == 1.0


def test_a_customer_row_with_no_bookings_never_reaches_the_cohort() -> None:
    # It cannot: the fold is over facts. This is the whole of D7's cure.
    orphan = uuid.UUID("cccccccc-0000-4000-8000-0000000000ff")
    history = {
        BRIDE_A: CustomerHistory(first_starts_at=_utc(2026, 5, 20), bookings=1),
        orphan: CustomerHistory(first_starts_at=_utc(2020, 1, 1), bookings=0),
    }

    mix = customer_mix(
        [_fact(_utc(2026, 5, 20), customer_id=BRIDE_A)], history, from_instant=WINDOW_FROM
    )

    assert mix.total == 1


def test_a_bride_whose_first_ever_booking_predates_the_window_is_returning() -> None:
    facts = [_fact(_utc(2026, 7, 20), customer_id=BRIDE_A)]
    history = {BRIDE_A: CustomerHistory(first_starts_at=_utc(2025, 11, 2), bookings=4)}

    mix = customer_mix(facts, history, from_instant=WINDOW_FROM)

    assert (mix.total, mix.new, mix.returning) == (1, 0, 1)
    assert mix.repeat_rate == 1.0


def test_a_bride_who_only_cancelled_did_not_visit_and_is_not_in_the_cohort() -> None:
    facts = [
        _fact(_utc(2026, 7, 20), customer_id=BRIDE_A),
        _fact(
            _utc(2026, 7, 21),
            customer_id=BRIDE_B,
            status=BookingStatus.CANCELLED.value,
            cancelled_by="customer",
        ),
    ]
    history = {
        BRIDE_A: CustomerHistory(first_starts_at=_utc(2026, 7, 20), bookings=1),
        BRIDE_B: CustomerHistory(first_starts_at=_utc(2026, 7, 21), bookings=1),
    }

    mix = customer_mix(facts, history, from_instant=WINDOW_FROM)

    assert mix.total == 1
    assert mix.new + mix.returning == mix.total


def test_a_phone_correction_split_scores_the_corrected_bride_as_new() -> None:
    # Risk 12, pinned rather than assumed away. F15's collision branch re-points
    # exactly ONE confirmed future booking, so one human's past visits stay on
    # customer A while her corrected visit sits under customer B.
    #
    # A has two PRE-window bookings and nothing inside it, so she is not in the
    # cohort at all; B has one in-window booking and a lifetime count of 1.
    facts = [_fact(_utc(2026, 7, 20), customer_id=BRIDE_B)]
    history = {
        BRIDE_A: CustomerHistory(first_starts_at=_utc(2025, 9, 1), bookings=2),
        BRIDE_B: CustomerHistory(first_starts_at=_utc(2026, 7, 20), bookings=1),
    }

    mix = customer_mix(facts, history, from_instant=WINDOW_FROM)

    assert (mix.total, mix.new, mix.returning) == (1, 1, 0)
    # She is excluded from the repeat rate although the human has been before.
    assert mix.repeat_rate == 0.0


def test_the_repeat_rate_is_lifetime_bookings_not_in_window_ones() -> None:
    facts = [
        _fact(_utc(2026, 7, 20), customer_id=BRIDE_A),
        _fact(_utc(2026, 7, 21), customer_id=BRIDE_B),
    ]
    history = {
        BRIDE_A: CustomerHistory(first_starts_at=_utc(2025, 9, 1), bookings=3),
        BRIDE_B: CustomerHistory(first_starts_at=_utc(2026, 7, 21), bookings=1),
    }

    mix = customer_mix(facts, history, from_instant=WINDOW_FROM)

    assert (mix.total, mix.new, mix.returning) == (2, 1, 1)
    assert mix.repeat_rate == 0.5


# --- build_history: the one entry point ---------------------------------------


def test_the_current_in_progress_week_is_in_no_bucket_and_in_no_status_total() -> None:
    # today is Friday 2026-07-31, so the current week began Sunday 2026-07-26
    # and Tuesday the 28th is inside it. The repository read applies the same
    # bound; re-applying it here is what makes the exclusion pure-testable.
    window = history_window(NORMATIVE_TODAY)
    inside_the_current_week = _fact(_utc(2026, 7, 28, 9, 0))
    last_covered_saturday = _fact(_utc(2026, 7, 25, 9, 0))

    panel = build_history(window, [inside_the_current_week, last_covered_saturday], {})

    assert sum(bucket.bookings for bucket in panel.weeks) == 1
    assert panel.status_totals.confirmed == 1
    assert _count_in(panel.weeks, datetime.date(2026, 7, 19)) == 1


def test_a_booking_before_the_first_bucket_is_excluded_too() -> None:
    window = history_window(NORMATIVE_TODAY)
    one_second_early = _fact(window.from_instant - datetime.timedelta(seconds=1))
    on_the_floor = _fact(window.from_instant)

    panel = build_history(window, [one_second_early, on_the_floor], {})

    assert sum(bucket.bookings for bucket in panel.weeks) == 1
    assert panel.status_totals.confirmed == 1


def test_the_panel_carries_the_specs_normative_dates() -> None:
    panel = build_history(history_window(NORMATIVE_TODAY), [], {})

    assert panel.from_date == datetime.date(2026, 5, 3)
    assert panel.to_date == datetime.date(2026, 7, 25)
    assert panel.to_date < NORMATIVE_TODAY
    assert len(panel.weeks) == HISTORY_WEEKS
    assert panel.weeks[0].week_start == panel.from_date


def test_the_bars_sum_to_confirmed_plus_no_show_plus_completed() -> None:
    # The consistency invariant. A no-show still occupied its seat, so it is in
    # the bar — which is why the bar is labelled as seat-slots the boutique HELD
    # and never as appointments that took place.
    facts = [
        _fact(_utc(2026, 5, 20)),
        _fact(_utc(2026, 6, 10), status=BookingStatus.NO_SHOW.value),
        _fact(_utc(2026, 6, 10), status=BookingStatus.COMPLETED.value),
        _fact(_utc(2026, 7, 20), status=BookingStatus.COMPLETED.value),
        _fact(_utc(2026, 7, 21), status=BookingStatus.CANCELLED.value, cancelled_by="owner"),
    ]

    panel = build_history(history_window(NORMATIVE_TODAY), facts, {})
    totals = panel.status_totals

    assert sum(bucket.bookings for bucket in panel.weeks) == (
        totals.confirmed + totals.no_show + totals.completed
    )
    assert sum(bucket.bookings for bucket in panel.weeks) == 4


def test_the_type_counts_never_exceed_the_bars_above_them() -> None:
    # C2's invariant. `<=`, not `==`: TOP_APPOINTMENT_TYPES truncates (Risk 14).
    facts = []
    for index in range(7):
        type_id = uuid.UUID(f"44444444-0000-4000-8000-00000000000{index}")
        facts += [
            _fact(_utc(2026, 6, 10), appointment_type_id=type_id, appointment_type_name=f"t{index}")
            for _ in range(index + 1)
        ]
    facts.append(
        _fact(_utc(2026, 6, 11), status=BookingStatus.CANCELLED.value, cancelled_by="customer")
    )

    panel = build_history(history_window(NORMATIVE_TODAY), facts, {})

    assert sum(row.bookings for row in panel.appointment_types) <= sum(
        bucket.bookings for bucket in panel.weeks
    )
    assert sum(row.bookings for row in panel.appointment_types) == 25
    assert sum(bucket.bookings for bucket in panel.weeks) == 28


def test_an_empty_tenant_is_a_valid_all_zero_panel_and_not_an_error() -> None:
    panel = build_history(history_window(NORMATIVE_TODAY), [], {})

    assert panel.cancellation_rate is None
    assert panel.no_show_rate is None
    assert panel.customers.repeat_rate is None
    assert panel.customers.total == 0
    assert (panel.cancelled_by_customer, panel.cancelled_by_owner) == (0, 0)
    assert panel.appointment_types == []
    assert [bucket.bookings for bucket in panel.weeks] == [0] * HISTORY_WEEKS


def test_the_cohort_is_scored_against_the_windows_own_floor() -> None:
    # build_history passes window.from_instant to customer_mix, so "new" means
    # "first ever inside THIS window" and nothing else.
    window = history_window(NORMATIVE_TODAY)
    facts = [
        _fact(_utc(2026, 7, 20), customer_id=BRIDE_A),
        _fact(_utc(2026, 7, 20), customer_id=BRIDE_B),
    ]
    history = {
        BRIDE_A: CustomerHistory(first_starts_at=window.from_instant, bookings=1),
        BRIDE_B: CustomerHistory(
            first_starts_at=window.from_instant - datetime.timedelta(seconds=1), bookings=2
        ),
    }

    panel = build_history(window, facts, history)

    assert (panel.customers.total, panel.customers.new, panel.customers.returning) == (2, 1, 1)
    assert panel.customers.repeat_rate == 0.5


# --- forward utilization ------------------------------------------------------
#
# `grid_totals` takes a grid and a mapping, so it needs no session. The grid it
# is handed comes from `materialize_slots(booked={})`: the engine DROPS full
# slots rather than marking them, so a grid built any other way omits precisely
# the fully-booked instants — the ones that make utilization high (D4).

SLOT_ONE = _utc(2026, 8, 3, 10, 0)
SLOT_TWO = _utc(2026, 8, 3, 10, 30)
SLOT_THREE = _utc(2026, 8, 4, 10, 0)
OFF_GRID = _utc(2026, 8, 5, 15, 0)


def _slot(starts_at: datetime.datetime, capacity: int) -> Slot:
    # booked=0 on every slot, because that is what `booked={}` produces. If
    # `grid_totals` read `slot.booked` instead of the mapping it would answer 0
    # everywhere, so these fixtures pin the mapping as the numerator's source.
    return Slot(starts_at=starts_at, capacity=capacity, booked=0)


def test_the_grid_is_the_denominator_and_the_mapping_only_the_numerator() -> None:
    grid = [_slot(SLOT_ONE, 2), _slot(SLOT_TWO, 2), _slot(SLOT_THREE, 2)]

    totals = grid_totals(grid, {SLOT_ONE: 1})

    assert totals.capacity == 6
    assert totals.booked == 1
    assert totals.utilization == 1 / 6


def test_an_overbooked_instant_clamps_to_its_own_capacity() -> None:
    # A data anomaly, and reporting a utilization above 100% would be a second
    # bug on top of the first — the same posture Slot.remaining takes.
    grid = [_slot(SLOT_ONE, 2)]

    totals = grid_totals(grid, {SLOT_ONE: 5})

    assert totals.booked == 2
    assert totals.booked <= totals.capacity
    assert totals.utilization == 1.0


def test_an_instant_the_grid_no_longer_offers_contributes_nothing() -> None:
    # A booking made under a weekly rule the owner has since deleted, or on a
    # date a later exception closed: the row exists and count_by_start counts
    # it, but there is no capacity behind it.
    #
    # THIS is the case that red-fails if anyone ships sum(mapping.values()) as
    # forward.booked — that spelling answers 5, and 5 > capacity.
    grid = [_slot(SLOT_ONE, 2)]

    totals = grid_totals(grid, {SLOT_ONE: 1, OFF_GRID: 4})

    assert totals.booked == 1
    assert totals.capacity == 2
    assert totals.booked <= totals.capacity


def test_a_boutique_with_no_open_hours_has_no_utilization() -> None:
    # Not 0%: closed hours and zero demand are different facts, and the copy
    # deck gives them different strings.
    totals = grid_totals([], {SLOT_ONE: 3})

    assert (totals.capacity, totals.booked) == (0, 0)
    assert totals.utilization is None


def test_booked_never_exceeds_capacity_and_utilization_is_their_quotient() -> None:
    cases: list[tuple[list[Slot], dict[datetime.datetime, int]]] = [
        ([_slot(SLOT_ONE, 1)], {}),
        ([_slot(SLOT_ONE, 1)], {SLOT_ONE: 1}),
        ([_slot(SLOT_ONE, 3), _slot(SLOT_TWO, 3)], {SLOT_ONE: 3, SLOT_TWO: 1}),
        ([_slot(SLOT_ONE, 3), _slot(SLOT_TWO, 3)], {SLOT_ONE: 9, OFF_GRID: 9}),
    ]

    for grid, booked_by_instant in cases:
        totals = grid_totals(grid, booked_by_instant)

        assert totals.booked <= totals.capacity
        assert totals.utilization == totals.booked / totals.capacity
