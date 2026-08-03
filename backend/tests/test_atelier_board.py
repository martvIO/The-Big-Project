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

from app.atelier.schemas import AtelierBoardResponse, AtelierTicket, SeamstressRef
from app.atelier.stages import DEFAULT_EFFORT_BANDS
from app.models.alteration_ticket import AlterationTicket
from app.models.constants import EffortBand, StaffRole, TicketStage
from app.models.customer import Customer
from app.models.staff_user import StaffUser
from app.storefront.validation import today_jerusalem

TENANT_ID = uuid.uuid4()
TODAY = datetime.date(2026, 8, 3)
INTAKE_AT = datetime.datetime(2026, 8, 1, 8, 10, tzinfo=datetime.UTC)


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
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _one(**overrides: object) -> AtelierTicket:
    row = _ticket(**overrides)
    return AtelierTicket.from_row(row, customer_name="מיכל לוי", today=TODAY)


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
    body = AtelierBoardResponse.build(
        tickets=[first, second],
        # Deliberately reversed relative to the tickets.
        customers=[_customer(second.customer_id, "דנה"), _customer(first.customer_id, "מיכל")],
        assignees=[],
        bands=DEFAULT_EFFORT_BANDS,
        truncated=False,
        today=TODAY,
    )
    assert [t.customer_name for t in body.tickets] == ["מיכל", "דנה"]


def test_a_ticket_whose_customer_row_is_gone_still_renders() -> None:
    """No shipped writer sets `customers.deleted_at`, so this is unreachable
    today — it exists so F20's retention scrub cannot drop a garment that is
    physically in the workroom off the board, or 500 a five-second poll."""
    body = AtelierBoardResponse.build(
        tickets=[_ticket()],
        customers=[],
        assignees=[],
        bands=DEFAULT_EFFORT_BANDS,
        truncated=False,
        today=TODAY,
    )
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
    body = AtelierBoardResponse.build(
        tickets=rows,
        customers=[_customer(row.customer_id, "מיכל") for row in rows],
        assignees=[],
        bands=DEFAULT_EFFORT_BANDS,
        truncated=False,
        today=TODAY,
    )
    assert [t.id for t in body.tickets] == [row.id for row in rows]


def test_truncated_reaches_the_wire_so_the_console_never_states_the_number() -> None:
    """`BOARD_TICKET_LIMIT` is SERVER-ONLY and no client constant mirrors it —
    this flag is why."""
    for flag in (True, False):
        body = AtelierBoardResponse.build(
            tickets=[],
            customers=[],
            assignees=[],
            bands=DEFAULT_EFFORT_BANDS,
            truncated=flag,
            today=TODAY,
        )
        assert body.truncated is flag


def test_the_envelope_carries_the_tenants_resolved_bands_in_enum_order() -> None:
    """So the console renders the five choices AND the minutes -> word reverse
    lookup with zero server branches. Iteration is over the ENUM, so a tenant's
    hand-edited blob cannot put a sixth band on the wire or reorder the five."""
    tuned = dict(DEFAULT_EFFORT_BANDS) | {EffortBand.HALF_DAY: 300}
    body = AtelierBoardResponse.build(
        tickets=[],
        customers=[],
        assignees=[],
        bands=tuned,
        truncated=False,
        today=TODAY,
    )
    assert [(b.band, b.minutes) for b in body.effort_bands] == [
        (EffortBand.THIRTY_MIN, 30),
        (EffortBand.ONE_HOUR, 60),
        (EffortBand.TWO_HOURS, 120),
        (EffortBand.HALF_DAY, 300),
        (EffortBand.FULL_DAY, 480),
    ]


# --- seamstresses[] is a UNION, not a filter (D9/D12) ------------------------


def test_a_live_seamstress_is_assignable() -> None:
    assert SeamstressRef.from_row(_staff()).assignable is True


def test_a_RETIRED_assignee_still_ships_and_carries_assignable_false() -> None:
    """⚠ THE ASSERTION THAT FAILS IF SOMEONE "SIMPLIFIES" THE UNION TO A FILTER.

    `StaffUsersRepository.soft_delete` retires her and nothing re-validates
    `assigned_staff_user_id`. Dropping her from the payload would make the
    tickets she still holds render an assignee the console cannot name —
    exactly the invisible bucket the assign-time role check exists to prevent.
    """
    retired = _staff(deleted_at=datetime.datetime(2026, 7, 30, tzinfo=datetime.UTC))
    ref = SeamstressRef.from_row(retired)
    assert ref.assignable is False
    assert ref.display_name == "נועה"


def test_a_RE_ROLED_assignee_still_ships_and_carries_assignable_false() -> None:
    """The other shipped writer: `StaffUsersRepository.update` sets `role`
    unconditionally. Live, but no longer a seamstress."""
    assert SeamstressRef.from_row(_staff(role=StaffRole.RECEPTION.value)).assignable is False


def test_the_union_ships_both_kinds_side_by_side_on_one_envelope() -> None:
    live = _staff(display_name="נועה")
    retired = _staff(
        display_name="דנה", deleted_at=datetime.datetime(2026, 7, 30, tzinfo=datetime.UTC)
    )
    body = AtelierBoardResponse.build(
        tickets=[],
        customers=[],
        assignees=[live, retired],
        bands=DEFAULT_EFFORT_BANDS,
        truncated=False,
        today=TODAY,
    )
    assert [(s.display_name, s.assignable) for s in body.seamstresses] == [
        ("נועה", True),
        ("דנה", False),
    ]


def test_no_seamstress_ref_carries_an_email_or_a_credential() -> None:
    keys = set(SeamstressRef.from_row(_staff()).model_dump())
    assert keys == {"id", "display_name", "assignable"}
