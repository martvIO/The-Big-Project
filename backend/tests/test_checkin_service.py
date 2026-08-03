"""F33's check-in service, driven with fakes and no database.

What is worth testing here is the shape validation, the consent branch and the
metering — the db-marked suite owns the SQL. The fake session factory is the
`test_booking_owner_service.py` scaffold: enough surface for `tenant_session`'s
`set_config` and the REAL `QueueTicketsRepository`, so a statement escaping to a
real session raises here instead of passing silently. The repository is real on
purpose — a fake one would let the service and the query drift apart.

**There is no dedup case in this file and there must never be one** (Ruling 3).
The create always creates: no pre-check, no lock, no `IntegrityError` path, no
per-phone budget and no duplicate branch. Nothing in the request path consults
the phone at all, which the source guard at the bottom pins as a property of the
package rather than of any one function.
"""

import datetime
import inspect
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.booking.validation import MAX_CUSTOMER_NAME_LENGTH, BookingValidationError
from app.errors import DomainValidationError
from app.models.constants import QueueTicketStatus, VisitType
from app.models.queue_ticket import QueueTicket
from app.queue.service import QueueService
from app.queue.validation import CheckinThrottledError, QueueTicketNotFoundError

TENANT_ID = uuid.UUID("11111111-1111-4111-8111-111111111111")
TICKET_ID = uuid.UUID("22222222-2222-4222-8222-222222222222")
# 20:00Z on 2026-07-18 is 23:00 Jerusalem the SAME day — the queue_day the
# create must stamp. A UTC-derived date would agree here and disagree at 21:30Z,
# which is why the boundary pair lives in this file too.
NOW = datetime.datetime(2026, 7, 18, 20, 0, tzinfo=datetime.UTC)
JERUSALEM_DAY = datetime.date(2026, 7, 18)

QUEUE_PACKAGE = Path(__file__).resolve().parents[1] / "app" / "queue"


class _FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeResult:
    def __init__(self, *, count: int, row: QueueTicket | None) -> None:
        self._count = count
        self._row = row

    def scalar_one(self) -> int:
        return self._count

    def scalar_one_or_none(self) -> QueueTicket | None:
        return self._row


class _FakeSession:
    """`added` and `statements` are what make the assertions possible: the
    number of INSERTs is a claim this feature makes in two places (one either
    way on the opt-in, none at all on a 400), and it is only checkable by
    recording them.

    `statements` holds the SELECT *objects*, not `str()` of them. `execute()`
    answers a canned result whatever it is handed, so any assertion about a
    WHERE clause has to read the statement itself — and `str()` renders bound
    values as `:queue_day_1`, which is exactly the part that matters. The
    objects let a test read `.compile().params`."""

    def __init__(self, *, count: int = 0, row: QueueTicket | None = None) -> None:
        self.added: list[QueueTicket] = []
        self.statements: list[Any] = []
        self.count = count
        self.row = row

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    def add(self, row: QueueTicket) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        # Standing in for the server defaults, because a fake has no server:
        # without id and created_at the ticket the service returns has no
        # capability and no sort key.
        for row in self.added:
            if row.id is None:
                row.id = TICKET_ID
            if row.created_at is None:
                row.created_at = NOW
            if row.status is None:
                row.status = QueueTicketStatus.WAITING.value

    async def refresh(self, row: QueueTicket) -> None:
        return None

    async def execute(self, *args: object, **kwargs: object) -> _FakeResult:
        if args:
            self.statements.append(args[0])
        return _FakeResult(count=self.count, row=self.row)


def _factory(session: _FakeSession) -> Any:
    @asynccontextmanager
    async def factory() -> AsyncIterator[_FakeSession]:
        yield session

    return factory


def _service(
    session: _FakeSession | None = None,
    *,
    create_limiter: FixedWindowRateLimiter | None = None,
    position_ticket_limiter: FixedWindowRateLimiter | None = None,
    position_miss_limiter: FixedWindowRateLimiter | None = None,
) -> QueueService:
    return QueueService(
        cast(async_sessionmaker, _factory(session if session is not None else _FakeSession())),
        create_limiter=create_limiter or FixedWindowRateLimiter(200, 3600.0, lambda: 0.0),
        position_ticket_limiter=position_ticket_limiter
        or FixedWindowRateLimiter(30, 60.0, lambda: 0.0),
        position_miss_limiter=position_miss_limiter
        or FixedWindowRateLimiter(120, 60.0, lambda: 0.0),
        # F59's fourth budget. Nothing in this file reads the board — the
        # generous ceiling is here so a required kwarg does not become a shared
        # instance the day someone adds a board case to the wrong file.
        board_limiter=FixedWindowRateLimiter(600, 60.0, lambda: 0.0),
        clock=lambda: NOW,
    )


async def _check_in(service: QueueService, **overrides: Any) -> Any:
    kwargs: dict[str, Any] = {
        "name": "נועה",
        "raw_phone": "0501234567",
        "visit_type": VisitType.BRIDE.value,
        "marketing_opt_in": False,
    }
    kwargs.update(overrides)
    return await service.check_in(TENANT_ID, **kwargs)


# --- shape validation: the shipped rules, reused, never a second copy ---


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
async def test_a_blank_name_is_a_domain_400_and_writes_nothing(name: str) -> None:
    session = _FakeSession()
    with pytest.raises(BookingValidationError):
        await _check_in(_service(session), name=name)
    assert session.added == []


async def test_the_name_boundary_is_the_shipped_eighty_not_a_second_number() -> None:
    session = _FakeSession()
    await _check_in(_service(session), name="א" * MAX_CUSTOMER_NAME_LENGTH)
    assert len(session.added) == 1
    with pytest.raises(BookingValidationError):
        await _check_in(_service(_FakeSession()), name="א" * (MAX_CUSTOMER_NAME_LENGTH + 1))


@pytest.mark.parametrize("name", ["נועה\x00", "נועה\nלוי", "נועה\tלוי", "נועה\x7f"])
async def test_control_characters_in_a_name_are_refused(name: str) -> None:
    """Both classes booking/validation.py bars: NUL is an asyncpg DataError and
    therefore a 500 on an anonymous route, and the rest of C0 is SMS
    header-injection material for the feature that templates this name."""
    with pytest.raises(BookingValidationError):
        await _check_in(_service(), name=name)


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("0501234567", "+972501234567"),
        ("050-123-4567", "+972501234567"),
        ("+972 50 123 4567", "+972501234567"),
        ("(050) 1234567", "+972501234567"),
        ("972501234567", "+972501234567"),
    ],
)
async def test_every_phone_form_the_shipped_normalizer_accepts_is_stored_as_one_string(
    raw: str, normalized: str
) -> None:
    session = _FakeSession()
    await _check_in(_service(session), raw_phone=raw)
    assert session.added[0].phone == normalized


@pytest.mark.parametrize("raw", ["", "not-a-phone", "021234567", "+1 555 0100", "05012345"])
async def test_a_phone_the_shipped_normalizer_rejects_is_a_domain_400(raw: str) -> None:
    session = _FakeSession()
    with pytest.raises(DomainValidationError):
        await _check_in(_service(session), raw_phone=raw)
    assert session.added == []


@pytest.mark.parametrize("visit_type", ["", "walk-in", "BRIDE", "groom", "waiting"])
async def test_an_unknown_visit_type_is_a_domain_400(visit_type: str) -> None:
    session = _FakeSession()
    with pytest.raises(DomainValidationError):
        await _check_in(_service(session), visit_type=visit_type)
    assert session.added == []


@pytest.mark.parametrize("visit_type", [VisitType.BRIDE.value, VisitType.EVENING.value])
async def test_both_visit_types_the_check_admits_are_accepted(visit_type: str) -> None:
    session = _FakeSession()
    await _check_in(_service(session), visit_type=visit_type)
    assert session.added[0].visit_type == visit_type


# --- the create itself ---


async def test_the_create_stamps_the_jerusalem_day_from_the_injected_clock() -> None:
    session = _FakeSession()
    ticket = await _check_in(_service(session))
    assert session.added[0].queue_day == JERUSALEM_DAY
    assert session.added[0].tenant_id == TENANT_ID
    assert ticket.id == TICKET_ID
    assert ticket.status == QueueTicketStatus.WAITING.value
    assert ticket.called_at is None


async def test_the_jerusalem_day_rolls_before_the_utc_day_does() -> None:
    """21:30Z on the 18th is 00:30 Jerusalem on the 19th. The boutique's queue
    has already turned over; the UTC calendar has not. A create at that instant
    must land on the 19th or the first arrival of the new day renders behind
    yesterday's ghosts."""
    session = _FakeSession()
    service = QueueService(
        cast(async_sessionmaker, _factory(session)),
        create_limiter=FixedWindowRateLimiter(200, 3600.0, lambda: 0.0),
        position_ticket_limiter=FixedWindowRateLimiter(30, 60.0, lambda: 0.0),
        position_miss_limiter=FixedWindowRateLimiter(120, 60.0, lambda: 0.0),
        board_limiter=FixedWindowRateLimiter(600, 60.0, lambda: 0.0),
        clock=lambda: datetime.datetime(2026, 7, 18, 21, 30, tzinfo=datetime.UTC),
    )
    await _check_in(service)
    assert session.added[0].queue_day == datetime.date(2026, 7, 19)


async def test_the_position_of_a_fresh_ticket_is_the_waiting_count_plus_one() -> None:
    ticket = await _check_in(_service(_FakeSession(count=3)))
    assert ticket.position == 4


async def test_the_create_writes_no_status_and_no_skip_count() -> None:
    """F33 writes the DB defaults and nothing else — every transition out of
    `waiting` is F58's. A service that started setting them would be the first
    step towards F33 owning a status machine it has no surface for."""
    session = _FakeSession()
    await _check_in(_service(session))
    row = session.added[0]
    assert row.called_at is None
    assert row.requeued_at is None
    assert row.deleted_at is None


# --- the opt-in branch ---


async def test_an_unticked_box_leaves_the_consent_column_null() -> None:
    session = _FakeSession()
    await _check_in(_service(session), marketing_opt_in=False)
    assert len(session.added) == 1
    assert session.added[0].marketing_opt_in_at is None


async def test_a_ticked_box_stamps_the_injected_clocks_instant_in_the_same_insert() -> None:
    session = _FakeSession()
    await _check_in(_service(session), marketing_opt_in=True)
    assert len(session.added) == 1
    assert session.added[0].marketing_opt_in_at == NOW


async def test_the_consent_never_reaches_the_wire() -> None:
    """`TicketView` is four fields. A consent timestamp on an anonymous
    response would tell anyone holding the id what she agreed to."""
    ticket = await _check_in(_service(), marketing_opt_in=True)
    assert set(ticket.model_dump()) == {"id", "status", "position", "called_at"}


# --- the create budget ---


async def test_a_spent_create_budget_raises_and_writes_nothing() -> None:
    limiter = FixedWindowRateLimiter(1, 3600.0, lambda: 0.0)
    session = _FakeSession()
    service = _service(session, create_limiter=limiter)
    await _check_in(service)
    with pytest.raises(CheckinThrottledError):
        await _check_in(service)
    assert len(session.added) == 1


async def test_the_create_budget_is_keyed_on_the_tenant_and_nothing_else() -> None:
    """Never on the phone. A phone-keyed 429 on an anonymous surface answers
    "is this number here" to anyone who submits it, which is the oracle
    Ruling 3 exists to close."""
    limiter = FixedWindowRateLimiter(1, 3600.0, lambda: 0.0)
    service = _service(create_limiter=limiter)
    await _check_in(service)
    with pytest.raises(CheckinThrottledError):
        await _check_in(service, raw_phone="0529999999")
    assert limiter.is_blocked(f"checkin:{TENANT_ID}")
    assert not limiter.is_blocked(f"checkin:{uuid.uuid4()}")


async def test_a_four_hundred_does_not_burn_the_boutiques_allowance() -> None:
    """Charged AFTER shape validation, deliberately: a blank name must not
    spend a real customer's slot in the window."""
    limiter = FixedWindowRateLimiter(1, 3600.0, lambda: 0.0)
    service = _service(create_limiter=limiter)
    with pytest.raises(BookingValidationError):
        await _check_in(service, name="  ")
    with pytest.raises(DomainValidationError):
        await _check_in(service, raw_phone="nope")
    assert not limiter.is_blocked(f"checkin:{TENANT_ID}")
    await _check_in(service)
    assert limiter.is_blocked(f"checkin:{TENANT_ID}")


async def test_a_second_well_formed_create_for_one_phone_is_charged_and_written() -> None:
    """A resubmission is a request, so it is metered — and under Ruling 3 it is
    also a ticket. Two rows, two ids, no branch anywhere."""
    session = _FakeSession()
    service = _service(session)
    first = await _check_in(service)
    second = await _check_in(service)
    assert len(session.added) == 2
    assert set(first.model_dump()) == set(second.model_dump())


# --- C2: app/queue/ knows nothing about customers, and cannot be made to ---


def test_no_module_in_the_queue_package_references_the_customers_repository() -> None:
    """Ruling 2 as a property of the package, not of a function. F33 has no
    possession proof of any kind, and `CustomersRepository.upsert` overwrites
    `existing.name` — from this form that is a stranger renaming a real
    customer. Re-add the import and this reddens.

    The files are read as TEXT on purpose, the
    `test_frontend_constant_parity.py` shape: this must run in the fast,
    no-Docker suite.
    """
    sources = sorted(QUEUE_PACKAGE.glob("*.py"))
    assert sources, "app/queue/ has no modules — the guard would pass vacuously"
    for path in sources:
        text = path.read_text(encoding="utf-8")
        assert "CustomersRepository" not in text, path.name
        assert "app.db.repositories.customers" not in text, path.name


def test_the_queue_service_constructor_names_no_customers_repository() -> None:
    """The other half: a kwarg wired in "purely to count zero" would restore
    the exact handle Ruling 2 removed."""
    parameters = inspect.signature(QueueService.__init__).parameters
    assert not [name for name in parameters if "customer" in name.lower()]


def test_no_module_in_the_queue_package_reaches_for_a_ticket_by_phone() -> None:
    """The Ruling 3 guard. A read keyed on the submitted number is the only way
    back to a presence oracle, so the absence is pinned rather than trusted:
    `phone` may be written and may be validated, but no lookup, filter or
    uniqueness may be built on it.
    """
    banned = re.compile(r"active_today|by_phone|phone\s*==")
    for path in sorted(QUEUE_PACKAGE.glob("*.py")):
        assert not banned.search(path.read_text(encoding="utf-8")), path.name


# --- the position read (Task 4) ---


def _waiting_ticket(
    *, status: str = QueueTicketStatus.WAITING.value, called_at: datetime.datetime | None = None
) -> QueueTicket:
    row = QueueTicket(
        tenant_id=TENANT_ID,
        queue_day=JERUSALEM_DAY,
        name="נועה",
        phone="+972501234567",
        visit_type=VisitType.BRIDE.value,
    )
    row.id = TICKET_ID
    row.created_at = NOW
    row.status = status
    row.called_at = called_at
    return row


async def test_the_position_read_answers_the_tickets_own_four_fields() -> None:
    called = datetime.datetime(2026, 7, 18, 20, 30, tzinfo=datetime.UTC)
    session = _FakeSession(count=2, row=_waiting_ticket(called_at=called))
    ticket = await _service(session).position(TENANT_ID, TICKET_ID)
    assert ticket.model_dump() == {
        "id": TICKET_ID,
        "status": QueueTicketStatus.WAITING.value,
        "position": 3,
        "called_at": called,
    }


@pytest.mark.parametrize(
    "status",
    [
        QueueTicketStatus.IN_SERVICE.value,
        QueueTicketStatus.DONE.value,
        QueueTicketStatus.REMOVED.value,
    ],
)
async def test_a_ticket_that_is_not_waiting_reports_no_position(status: str) -> None:
    """A number with no referent is worse than no number: nothing that is not
    waiting has a place in a queue."""
    session = _FakeSession(count=5, row=_waiting_ticket(status=status))
    ticket = await _service(session).position(TENANT_ID, TICKET_ID)
    assert ticket.position is None
    assert ticket.status == status


async def test_the_position_is_counted_within_the_tickets_own_queue_day() -> None:
    """C11, re-asserted through the service. The repository binds the day from
    the row it has in hand; the service must not pass today's date down and
    tell someone who walked out yesterday that she is next.

    Asserted on the COUNT statement's bound value and not on the returned
    number: `_FakeSession.execute` answers `count` whatever it is given, so
    `position == 5` is `4 + 1` and holds just as well against a query bound to
    `today_jerusalem()`. The clock here says 2026-07-18 and the ticket says
    2026-07-17, so the two are distinguishable — which is the whole point.
    (`test_queue_repositories.py` pins the same rule against real SQL, but it
    is db-marked and invisible to `pytest -m "not db"`.)"""
    yesterday = _waiting_ticket()
    yesterday.queue_day = datetime.date(2026, 7, 17)
    session = _FakeSession(count=4, row=yesterday)
    ticket = await _service(session).position(TENANT_ID, TICKET_ID)
    assert ticket.position == 5

    # by_id first, then the count — the count is the one with a day predicate.
    bound = session.statements[-1].compile().params
    assert bound["queue_day_1"] == datetime.date(2026, 7, 17)
    assert JERUSALEM_DAY not in bound.values()


async def test_an_unknown_id_is_a_not_found_that_inherits_the_shipped_handler() -> None:
    with pytest.raises(QueueTicketNotFoundError):
        await _service(_FakeSession(row=None)).position(TENANT_ID, uuid.uuid4())


async def test_a_foreign_tenants_ticket_is_a_miss_and_never_a_403() -> None:
    """RLS plus the repository's explicit predicate make a foreign row
    indistinguishable from an absent one, and that indistinguishability IS the
    security property — a 403 would confirm the ticket exists."""
    with pytest.raises(QueueTicketNotFoundError):
        await _service(_FakeSession(row=None)).position(uuid.uuid4(), TICKET_ID)


# --- Task 4: the metering table, and C7 is what it encodes ---


async def test_a_hit_charges_the_ticket_budget_and_leaves_the_tenant_brake_alone() -> None:
    """Both limiters are built with a ceiling of one, so `is_blocked` after the
    call reads as "was this budget charged" with no reach into the limiter's
    internals."""
    ticket_limiter = FixedWindowRateLimiter(1, 60.0, lambda: 0.0)
    miss_limiter = FixedWindowRateLimiter(1, 60.0, lambda: 0.0)
    session = _FakeSession(count=0, row=_waiting_ticket())
    await _service(
        session, position_ticket_limiter=ticket_limiter, position_miss_limiter=miss_limiter
    ).position(TENANT_ID, TICKET_ID)
    assert ticket_limiter.is_blocked(f"checkin:position:{TENANT_ID}:{TICKET_ID}") is True
    assert miss_limiter.is_blocked(f"checkin:position:miss:{TENANT_ID}") is False


async def test_a_miss_charges_both_budgets() -> None:
    ticket_limiter = FixedWindowRateLimiter(1, 60.0, lambda: 0.0)
    miss_limiter = FixedWindowRateLimiter(1, 60.0, lambda: 0.0)
    unknown = uuid.uuid4()
    with pytest.raises(QueueTicketNotFoundError):
        await _service(
            _FakeSession(row=None),
            position_ticket_limiter=ticket_limiter,
            position_miss_limiter=miss_limiter,
        ).position(TENANT_ID, unknown)
    assert ticket_limiter.is_blocked(f"checkin:position:{TENANT_ID}:{unknown}") is True
    assert miss_limiter.is_blocked(f"checkin:position:miss:{TENANT_ID}") is True


async def test_a_spent_ticket_budget_throttles_that_one_ticket() -> None:
    """The caller's own budget, keyed on a capability they already hold, so a
    429 on it discloses nothing. A leaked poll loop stops at its own ceiling
    instead of at the boutique's."""
    ticket_limiter = FixedWindowRateLimiter(1, 60.0, lambda: 0.0)
    session = _FakeSession(count=0, row=_waiting_ticket())
    service = _service(session, position_ticket_limiter=ticket_limiter)
    await service.position(TENANT_ID, TICKET_ID)
    with pytest.raises(CheckinThrottledError):
        await service.position(TENANT_ID, TICKET_ID)


async def test_a_spent_miss_brake_throttles_the_next_miss() -> None:
    miss_limiter = FixedWindowRateLimiter(1, 60.0, lambda: 0.0)
    service = _service(_FakeSession(row=None), position_miss_limiter=miss_limiter)
    with pytest.raises(QueueTicketNotFoundError):
        await service.position(TENANT_ID, uuid.uuid4())
    with pytest.raises(CheckinThrottledError):
        await service.position(TENANT_ID, uuid.uuid4())


async def test_a_spent_miss_brake_still_answers_a_real_ticket() -> None:
    """C7, and this is the assertion that fails if someone puts the tenant
    charge back on the hit path. `is_blocked` fires on a repeated KEY, and the
    ticket key comes from the caller's own body — a walk of fresh UUIDs never
    repeats one, so charging the tenant on every read let one host at 50 rps
    deny every real bride her position page."""
    miss_limiter = FixedWindowRateLimiter(1, 60.0, lambda: 0.0)
    miss_limiter.record_failure(f"checkin:position:miss:{TENANT_ID}")
    session = _FakeSession(count=1, row=_waiting_ticket())
    ticket = await _service(session, position_miss_limiter=miss_limiter).position(
        TENANT_ID, TICKET_ID
    )
    assert ticket.position == 2


async def test_the_miss_brake_is_keyed_on_the_tenant_and_the_ticket_budget_on_the_ticket() -> None:
    ticket_limiter = FixedWindowRateLimiter(1, 60.0, lambda: 0.0)
    session = _FakeSession(count=0, row=_waiting_ticket())
    service = _service(session, position_ticket_limiter=ticket_limiter)
    await service.position(TENANT_ID, TICKET_ID)
    other = uuid.uuid4()
    session.row = _waiting_ticket()
    session.row.id = other
    # A different ticket is a different key, so the first ticket's spent budget
    # cannot deny it. One budget per capability, not one per boutique.
    assert (await service.position(TENANT_ID, other)).id == other
