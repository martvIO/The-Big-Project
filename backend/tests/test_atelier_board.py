"""The board's FOLD: repository rows in, one envelope out — pure, frozen, no
Postgres (`test_dashboard_math.py`'s shape).

What this module owns and `test_atelier_db.py` does not: `overdue` either side of
Jerusalem midnight, `delivered_at` cancelling it, the union's `assignable`
derivation, the bands on the envelope, and the fact that the fold RE-ORDERS
NOTHING.

What it deliberately does NOT own, stated so nobody adds a second copy: the
seven-day delivered window, the 500 ceiling and the `due_date, created_at, id`
ordering are SQL — they live in the repository's predicate and its ORDER BY, and
`test_atelier_db.py` pins them against a real Postgres. The fold cannot observe
them; all it can see is `truncated` arriving on the wire and the row order it was
handed surviving untouched, and both of those are asserted here.
"""

import datetime
import uuid
from typing import Any

from app.atelier.schemas import AtelierBoardResponse, AtelierTicket, SeamstressRef
from app.atelier.stages import DEFAULT_EFFORT_BANDS
from app.models.alteration_ticket import AlterationTicket
from app.models.constants import EffortBand, StaffRole, TicketStage
from app.models.customer import Customer
from app.models.staff_user import StaffUser
from app.storefront.validation import today_jerusalem

TENANT_ID = uuid.uuid4()
TODAY = datetime.date(2026, 8, 3)
# The rolling week D3 filters the bar's numerator on, computed exactly as the
# service computes it: `today_jerusalem + 7`. It reaches the wire as
# `due_soon_through` because the console has no date arithmetic at all (F-1).
HORIZON = TODAY + datetime.timedelta(days=7)
INTAKE_AT = datetime.datetime(2026, 8, 1, 8, 10, tzinfo=datetime.UTC)

Load = dict[uuid.UUID | None, tuple[int, int]]


def _ticket(**overrides: object) -> AlterationTicket:
    row = AlterationTicket(
        tenant_id=TENANT_ID,
        customer_id=uuid.uuid4(),
        due_date=datetime.date(2026, 8, 20),
        effort_minutes=120,
        intake_at=INTAKE_AT,
    )
    row.id = uuid.uuid4()
    row.assigned_staff_user_id = None
    row.dress_id = None
    row.dress_name = None
    row.dress_size = None
    row.notes = None
    row.in_progress_at = None
    row.qc_at = None
    row.ready_at = None
    row.delivered_at = None
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _customer(customer_id: uuid.UUID, name: str) -> Customer:
    row = Customer(tenant_id=TENANT_ID, phone="972521234567", name=name)
    row.id = customer_id
    return row


def _staff(**overrides: object) -> StaffUser:
    row = StaffUser(
        tenant_id=TENANT_ID,
        email="noa@bella.example",
        password_hash="not-a-real-hash",
        display_name="נועה",
        role=StaffRole.SEAMSTRESS.value,
    )
    row.id = uuid.uuid4()
    row.deleted_at = None
    row.weekly_capacity_hours = None
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _one(**overrides: object) -> AtelierTicket:
    row = _ticket(**overrides)
    return AtelierTicket.from_row(row, customer_name="מיכל לוי", today=TODAY)


def _ref(
    row: StaffUser, *, load: Load | None = None, tenant_default: int | None = None
) -> SeamstressRef:
    return SeamstressRef.from_row(row, load=load or {}, tenant_default=tenant_default)


def _board(**overrides: Any) -> AtelierBoardResponse:
    """Every argument of the fold, defaulted to "nothing at all" — so a test says
    only what it is about. The three F42 parameters are REQUIRED on `build`
    itself and carry no defaults there: a fold that could silently omit the
    horizon is a fold the service can forget to hand one."""
    kwargs: dict[str, Any] = {
        "tickets": [],
        "customers": [],
        "assignees": [],
        "bands": DEFAULT_EFFORT_BANDS,
        "truncated": False,
        "today": TODAY,
        "load": {},
        "default_capacity_hours": None,
        "due_soon_through": HORIZON,
    }
    return AtelierBoardResponse.build(**(kwargs | overrides))


# --- overdue: computed on read, never stored (D5) ----------------------------


def test_a_due_date_before_today_is_overdue() -> None:
    assert _one(due_date=datetime.date(2026, 8, 2)).overdue is True


def test_a_due_date_of_today_is_not_overdue() -> None:
    """The boundary is `<`, not `<=`. A dress due TODAY is due today — flagging
    it in the danger register at 09:00 would spend the badge that has to still
    mean something tomorrow morning."""
    assert _one(due_date=TODAY).overdue is False


def test_a_future_due_date_is_not_overdue() -> None:
    assert _one(due_date=datetime.date(2026, 8, 4)).overdue is False


def test_a_delivered_ticket_is_never_overdue_however_late_it_went_out() -> None:
    """⚠ `delivered_at IS NOT NULL` CANCELS overdue. A garment delivered late is
    a fact about the past, not a thing to chase; the timestamps carry the
    lateness for F44's report. Without this clause the delivered column would
    fill with red badges for work that is finished."""
    delivered = _one(
        due_date=datetime.date(2026, 7, 1),
        delivered_at=datetime.datetime(2026, 8, 2, 15, 0, tzinfo=datetime.UTC),
    )
    assert delivered.overdue is False
    assert _one(due_date=datetime.date(2026, 7, 1)).overdue is True


def test_the_overdue_boundary_moves_at_JERUSALEM_midnight_and_not_at_utc() -> None:
    """⚠ The whole reason `due_date` is a DATE and `today` comes from
    `today_jerusalem`.

    2026-08-02T20:30Z is still 2026-08-02 in Jerusalem (UTC+3 in summer) and
    2026-08-02T21:30Z is already the third. A ticket due on the second is
    therefore NOT overdue at the first instant and IS at the second — and a
    server that compared against `datetime.date.today()` on a UTC runner would
    answer the same for both, three hours late, every single day.
    """
    before = datetime.datetime(2026, 8, 2, 20, 30, tzinfo=datetime.UTC)
    after = datetime.datetime(2026, 8, 2, 21, 30, tzinfo=datetime.UTC)
    due = datetime.date(2026, 8, 2)

    def overdue_at(now: datetime.datetime) -> bool:
        return AtelierTicket.from_row(
            _ticket(due_date=due), customer_name="מיכל", today=today_jerusalem(lambda: now)
        ).overdue

    assert overdue_at(before) is False
    assert overdue_at(after) is True


# --- the derived stage reaches the wire (D2) ---------------------------------


def test_the_wire_stage_is_the_rightmost_stamp_including_across_a_skip() -> None:
    """A NULL earlier stamp beside a later one means "never separately
    recorded" — the ticket is at `ready`, and the fold must not re-derive it as
    `in_progress` by walking to the first hole."""
    row = _one(ready_at=datetime.datetime(2026, 8, 2, 11, 0, tzinfo=datetime.UTC))
    assert row.stage is TicketStage.READY
    assert row.in_progress_at is None
    assert row.qc_at is None


def test_all_five_stamps_ship_so_f44_reads_them_off_the_wire() -> None:
    assert {
        "intake_at",
        "in_progress_at",
        "qc_at",
        "ready_at",
        "delivered_at",
    } <= set(_one().model_dump())


def test_no_ticket_carries_the_customers_phone() -> None:
    """D6's minimisation, asserted rather than assumed: the board is read by a
    seamstress and there is no surface in F41 that calls a bride."""
    keys = set(_one().model_dump())
    assert keys & {"customer_phone", "phone", "customer_id", "tenant_id", "deleted_at"} == set()


# --- the envelope ------------------------------------------------------------


def test_names_are_matched_by_customer_id_and_never_by_position() -> None:
    """The repository answers tickets ordered by `due_date` and customers in
    whatever order the `IN` came back — a positional zip renders one bride's
    name on another bride's garment."""
    first, second = _ticket(), _ticket()
    body = _board(
        tickets=[first, second],
        # Deliberately reversed relative to the tickets.
        customers=[_customer(second.customer_id, "דנה"), _customer(first.customer_id, "מיכל")],
    )
    assert [t.customer_name for t in body.tickets] == ["מיכל", "דנה"]


def test_a_ticket_whose_customer_row_is_gone_still_renders() -> None:
    """No shipped writer sets `customers.deleted_at`, so this is unreachable
    today — it exists so F20's retention scrub cannot drop a garment that is
    physically in the workroom off the board, or 500 a five-second poll."""
    body = _board(tickets=[_ticket()])
    assert body.tickets[0].customer_name == ""


def test_the_fold_preserves_the_repositorys_order_exactly() -> None:
    """The ORDER BY is `due_date, created_at, id` and it is the DATABASE's. A
    fold that re-sorted — even by the same keys — would be a second ordering to
    keep in step, and the one the console sees would stop being the one the
    truncation boundary was computed against."""
    rows = [
        _ticket(due_date=datetime.date(2026, 8, 20)),
        _ticket(due_date=datetime.date(2026, 8, 1)),
        _ticket(due_date=datetime.date(2026, 8, 9)),
    ]
    body = _board(tickets=rows, customers=[_customer(row.customer_id, "מיכל") for row in rows])
    assert [t.id for t in body.tickets] == [row.id for row in rows]


def test_truncated_reaches_the_wire_so_the_console_never_states_the_number() -> None:
    """`BOARD_TICKET_LIMIT` is SERVER-ONLY and no client constant mirrors it —
    this flag is why."""
    for flag in (True, False):
        body = _board(truncated=flag)
        assert body.truncated is flag


def test_the_envelope_carries_the_tenants_resolved_bands_in_enum_order() -> None:
    """So the console renders the five choices AND the minutes -> word reverse
    lookup with zero server branches. Iteration is over the ENUM, so a tenant's
    hand-edited blob cannot put a sixth band on the wire or reorder the five."""
    tuned = dict(DEFAULT_EFFORT_BANDS) | {EffortBand.HALF_DAY: 300}
    body = _board(bands=tuned)
    assert [(b.band, b.minutes) for b in body.effort_bands] == [
        (EffortBand.THIRTY_MIN, 30),
        (EffortBand.ONE_HOUR, 60),
        (EffortBand.TWO_HOURS, 120),
        (EffortBand.HALF_DAY, 300),
        (EffortBand.FULL_DAY, 480),
    ]


# --- seamstresses[] is a UNION, not a filter (D9/D12) ------------------------


def test_a_live_seamstress_is_assignable() -> None:
    assert _ref(_staff()).assignable is True


def test_a_RETIRED_assignee_still_ships_and_carries_assignable_false() -> None:
    """⚠ THE ASSERTION THAT FAILS IF SOMEONE "SIMPLIFIES" THE UNION TO A FILTER.

    `StaffUsersRepository.soft_delete` retires her and nothing re-validates
    `assigned_staff_user_id`. Dropping her from the payload would make the
    tickets she still holds render an assignee the console cannot name —
    exactly the invisible bucket the assign-time role check exists to prevent.
    """
    retired = _staff(deleted_at=datetime.datetime(2026, 7, 30, tzinfo=datetime.UTC))
    ref = _ref(retired)
    assert ref.assignable is False
    assert ref.display_name == "נועה"


def test_a_RE_ROLED_assignee_still_ships_and_carries_assignable_false() -> None:
    """The other shipped writer: `StaffUsersRepository.update` sets `role`
    unconditionally. Live, but no longer a seamstress."""
    assert _ref(_staff(role=StaffRole.RECEPTION.value)).assignable is False


def test_the_union_ships_both_kinds_side_by_side_on_one_envelope() -> None:
    live = _staff(display_name="נועה")
    retired = _staff(
        display_name="דנה", deleted_at=datetime.datetime(2026, 7, 30, tzinfo=datetime.UTC)
    )
    body = _board(assignees=[live, retired])
    assert [(s.display_name, s.assignable) for s in body.seamstresses] == [
        ("נועה", True),
        ("דנה", False),
    ]


def test_no_seamstress_ref_carries_an_email_or_a_credential() -> None:
    keys = set(_ref(_staff()).model_dump())
    assert keys == {
        "id",
        "display_name",
        "assignable",
        "weekly_capacity_hours",
        "capacity_is_default",
        "assigned_minutes",
        "due_soon_minutes",
    }


# --- F42: capacity and the TWO load sums on the envelope (D7, D2, D3, F-1) ----
#
# Four fields per seamstress and THREE on the board. The fold stays a total
# function of its arguments with no I/O, which is what keeps this whole module
# out of the db suite — `schemas.py`'s own docstring says that is the reason the
# fold lives there rather than in the service.


def test_a_seamstress_carries_BOTH_sums_under_their_own_names() -> None:
    """⚠ THE ORDER OF THE TUPLE IS `(due_soon, assigned)` AND SWAPPING IT IS
    SILENT: both are minute counts, both are plausible, and the only thing that
    would show is a bar reading 300 % on a healthy row (or a green one on a
    drowning one). Asserted with two DIFFERENT numbers for that reason."""
    her = _staff()
    ref = _ref(her, load={her.id: (900, 2760)})
    assert ref.due_soon_minutes == 900
    assert ref.assigned_minutes == 2760


def test_a_seamstress_absent_from_the_aggregate_reads_zero_and_does_NOT_vanish() -> None:
    """D3's aggregate returns no group at all for a seamstress holding nothing —
    there is no `HAVING`, there is simply no row — so the fold's `.get(id, (0, 0))`
    is the only thing that keeps her on the panel with an empty bar instead of
    dropping her off it.

    Mutation: `load[row.id]` → KeyError, and the board 500s on a five-second poll
    the first time anybody finishes their last job."""
    idle, busy = _staff(display_name="נועה"), _staff(display_name="דנה")
    body = _board(assignees=[idle, busy], load={busy.id: (45, 45)})

    assert [s.display_name for s in body.seamstresses] == ["נועה", "דנה"]
    assert (body.seamstresses[0].due_soon_minutes, body.seamstresses[0].assigned_minutes) == (0, 0)
    assert (body.seamstresses[1].due_soon_minutes, body.seamstresses[1].assigned_minutes) == (
        45,
        45,
    )


def test_a_RETIRED_assignee_carries_a_REAL_load_beside_assignable_false() -> None:
    """F41's Risk 9.2 anomalous bucket, now carrying a number. `from_row` keeps
    deriving `assignable` from the row and F42 does not touch it — so a retired
    seamstress with live tickets ships `assignable: false`, a real
    `assigned_minutes`, and whatever capacity resolves. The panel has to be able
    to show her: the work is real and somebody has to take it."""
    retired = _staff(deleted_at=datetime.datetime(2026, 7, 30, tzinfo=datetime.UTC))
    ref = _ref(retired, load={retired.id: (120, 600)}, tenant_default=30)
    assert ref.assignable is False
    assert (ref.due_soon_minutes, ref.assigned_minutes) == (120, 600)
    assert (ref.weekly_capacity_hours, ref.capacity_is_default) == (30, True)


def test_a_book_due_entirely_next_month_is_ZERO_on_the_bar_and_WHOLE_on_the_backlog() -> None:
    """D3's dimensional argument, seen from the wire: `due_soon_minutes` is the
    bar's numerator (a week of work against a week of capacity) and
    `assigned_minutes` is the ruling's number (the whole undelivered queue,
    stated in words beside the bar). A seamstress whose every job is due in six
    weeks is not overloaded THIS week, and the row must say both things."""
    her = _staff()
    ref = _ref(her, load={her.id: (0, 5400)})
    assert ref.due_soon_minutes == 0
    assert ref.assigned_minutes == 5400


def test_her_own_hours_win_and_are_never_labelled_the_boutiques() -> None:
    her = _staff(weekly_capacity_hours=12)
    ref = _ref(her, tenant_default=40)
    assert (ref.weekly_capacity_hours, ref.capacity_is_default) == (12, False)


def test_an_inherited_number_reaches_the_wire_FLAGGED_as_the_boutiques() -> None:
    """The resolved number and her own column are DIFFERENT FACTS and the console
    needs both: the panel must not present an inherited number as hers, and the
    editor must be able to tell "clear back to the default" from "set to the same
    number"."""
    ref = _ref(_staff(), tenant_default=40)
    assert (ref.weekly_capacity_hours, ref.capacity_is_default) == (40, True)


def test_neither_set_is_a_NULL_capacity_and_null_is_never_a_default() -> None:
    """`null` is a real answer and means "no bar" — never zero, never a guess.
    `capacity_is_default` is False because there is nothing to have defaulted
    to."""
    ref = _ref(_staff(), tenant_default=None)
    assert (ref.weekly_capacity_hours, ref.capacity_is_default) == (None, False)


def test_a_ZERO_capacity_reaches_the_wire_as_zero_and_as_HERS() -> None:
    """⚠ THE `is not None` GUARD, ASSERTED AT THE WIRE AS WELL AS IN THE FOLD.
    `resolve_capacity`'s `or` bug hands her the boutique's forty, renders her bar
    at a fraction of the truth in the non-overload colour, prints «ברירת מחדל של
    הבוטיק» on a number she set herself, and sorts her FIRST in the assign
    select — all four on the seamstress who is away this week."""
    her = _staff(weekly_capacity_hours=0)
    ref = _ref(her, load={her.id: (360, 360)}, tenant_default=40)
    assert (ref.weekly_capacity_hours, ref.capacity_is_default) == (0, False)
    assert ref.due_soon_minutes == 360


def test_the_unassigned_pile_is_the_UNFILTERED_sum(  # noqa: E501
) -> None:
    """F-3, and it is the one place the envelope reads the SECOND member of the
    tuple. The NULL group gets no bar — nobody has capacity for work nobody
    holds — so there is no rate to divide by and no reason to narrow it to a
    week. The panel states it in words.

    Mutation: read the filtered sum instead → 240 becomes 60 and the pile
    understates itself by every job due after Tuesday week."""
    body = _board(load={None: (60, 240)})
    assert body.unassigned_minutes == 240


def test_a_board_with_nothing_unassigned_reports_zero_rather_than_omitting_the_key() -> None:
    """The NULL group is simply absent from the aggregate when every live ticket
    is assigned. The field is not optional: a missing key and a zero are the same
    sentence on screen and only one of them is a number."""
    assert _board(load={_staff().id: (30, 30)}).unassigned_minutes == 0


def test_the_envelope_carries_the_tenant_default_and_the_horizon_it_FILTERED_ON() -> None:
    """⚠ `due_soon_through` EXISTS BECAUSE THE CLIENT CANNOT COMPUTE IT (F-1).
    `lib/jerusalem.ts` ships six formatters and ZERO date arithmetic, and a
    client that invented `new Date() + 7` would print a date in the BROWSER's
    zone against a filter the SERVER ran in Jerusalem's — off by a day for
    anybody travelling, and off by nothing that anyone could see.

    The default rides `TenantContext.settings` at zero statements, so the
    settings dialog opens with no read of its own and the panel can say whose
    default an inherited number is."""
    body = _board(default_capacity_hours=30)
    assert body.default_weekly_capacity_hours == 30
    assert body.due_soon_through == HORIZON
    assert _board().default_weekly_capacity_hours is None


def test_the_envelope_is_SEVEN_named_parts_and_the_tickets_are_untouched() -> None:
    """F41's four plus F42's three. `tickets` is byte-identical — not one field
    added, removed or renamed — which is what makes D7's "the envelope extends,
    it never breaks" an assertion instead of an intention."""
    row = _ticket()
    body = _board(tickets=[row], customers=[_customer(row.customer_id, "מיכל")])

    assert set(body.model_dump()) == {
        "tickets",
        "seamstresses",
        "effort_bands",
        "truncated",
        "unassigned_minutes",
        "default_weekly_capacity_hours",
        "due_soon_through",
    }
    assert body.model_dump()["tickets"] == [
        {
            "id": row.id,
            "customer_name": "מיכל",
            "due_date": datetime.date(2026, 8, 20),
            "overdue": False,
            "effort_minutes": 120,
            "assigned_staff_user_id": None,
            "dress_id": None,
            "dress_name": None,
            "dress_size": None,
            "notes": None,
            "stage": TicketStage.INTAKE,
            "intake_at": INTAKE_AT,
            "in_progress_at": None,
            "qc_at": None,
            "ready_at": None,
            "delivered_at": None,
        }
    ]


def test_the_fold_re_orders_the_SEAMSTRESSES_no_more_than_it_re_orders_the_tickets() -> None:
    """⚠ THE ASSIGN SORT IS THE CONSOLE'S AND THE SERVER MUST NOT GUESS AT IT.

    `assignees()` answers `display_name, id` and the fold hands that order
    straight through — even though D10 sorts the panel and the assign `<Select>`
    by REMAINING CAPACITY. Sorting here would be a second ordering to keep in
    step with the client's, computed from the same three numbers, and the two
    would diverge the first time either changed. The numbers travel; the
    ordering is a rendering decision.
    """
    first = _staff(display_name="אביגיל")
    second = _staff(display_name="דנה")
    third = _staff(display_name="נועה")
    # Every plausible sort key disagrees with the input order: `second` has the
    # most headroom, `third` the most load, `first` no capacity at all.
    body = _board(
        assignees=[first, second, third],
        load={first.id: (600, 600), second.id: (60, 60), third.id: (1200, 1200)},
        default_capacity_hours=None,
    )
    assert [s.display_name for s in body.seamstresses] == ["אביגיל", "דנה", "נועה"]
