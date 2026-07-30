"""F15's owner reads, driven with fakes and no database.

What is worth testing here is the shaping, not the SQL — the db-marked suite owns
the predicates. Three things a silent regression would cost most: the Jerusalem
calendar date becoming the right pair of UTC instants across a DST boundary, the
offset ceiling reaching the repository rather than only the response envelope,
and the response models never growing a field that carries a live credential.

The fake session factory is the `test_storefront_validation.py` scaffold: enough
surface for `tenant_session`'s `set_config` and nothing else, so a statement
escaping to a real session raises here instead of passing silently.
"""

import datetime
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.booking.comms import BookingCommsService
from app.booking.owner import (
    MAX_LIST_OFFSET,
    BookingTransitionInvalidError,
    CustomerAlreadyBookedError,
    OwnerBookingService,
    OwnerResendThrottledError,
)
from app.booking.schemas import (
    OwnerBookingDetail,
    OwnerBookingListResponse,
    OwnerBookingRow,
    OwnerSlotListResponse,
    OwnerSlotRow,
    PhoneCorrectionRequest,
    RescheduleRequest,
)
from app.booking.service import BookingNotFoundError, SlotUnavailableError
from app.booking.slots import Slot
from app.booking.validation import BOOKING_LIST_DEFAULT_LIMIT, BOOKING_LIST_MAX_LIMIT
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
from app.errors import DomainValidationError
from app.models.booking import Booking
from app.models.constants import AuditAction, BookingCancelledBy, BookingStatus, StaffRole
from app.storefront.service import StorefrontService
from app.storefront.validation import BOUTIQUE_TIMEZONE

TENANT_ID = uuid.uuid4()
NOW = datetime.datetime(2026, 7, 30, 9, 0, tzinfo=datetime.UTC)
# The graph turns on the `starts_at` split, so every transition case needs one
# of exactly two fixtures: an appointment that has happened and one that has not.
PAST = datetime.datetime(2026, 7, 1, 7, 0, tzinfo=datetime.UTC)
FUTURE = datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC)

CONFIRMED = BookingStatus.CONFIRMED.value
CANCELLED = BookingStatus.CANCELLED.value
NO_SHOW = BookingStatus.NO_SHOW.value
COMPLETED = BookingStatus.COMPLETED.value

STAFF = StaffContext(
    id=uuid.uuid4(),
    tenant_id=TENANT_ID,
    email="owner@example.com",
    display_name="בעלת הסלון",
    role=StaffRole.OWNER.value,
)


class _FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeSession:
    """`log` is what makes the reschedule ordering assertable: the advisory lock
    is a raw statement on the session, not a repository call, so the only way to
    prove it precedes the read is to record both into one sequence."""

    def __init__(self, log: list[str] | None = None) -> None:
        self._log = log

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def execute(self, *args: object, **kwargs: object) -> None:
        if self._log is not None and args:
            statement = str(args[0])
            if "pg_advisory_xact_lock" in statement:
                self._log.append("advisory_lock")
        return None


@asynccontextmanager
async def _fake_session_factory() -> AsyncIterator[_FakeSession]:
    yield _FakeSession()


def _recording_session_factory(log: list[str]) -> Any:
    @asynccontextmanager
    async def factory() -> AsyncIterator[_FakeSession]:
        yield _FakeSession(log)

    return factory


class _FakeStorefront:
    """Only `list_slots` — the one thing the owner slot grid delegates."""

    def __init__(self, slots: list[Slot]) -> None:
        self._slots = slots
        self.calls: list[tuple[datetime.date | None, datetime.date | None]] = []

    async def list_slots(
        self,
        tenant_id: uuid.UUID,
        *,
        from_date: datetime.date | None = None,
        to_date: datetime.date | None = None,
    ) -> list[Slot]:
        self.calls.append((from_date, to_date))
        return self._slots


def _service(
    storefront: _FakeStorefront | None = None,
    *,
    sms_limiter: FixedWindowRateLimiter | None = None,
    session_factory: Any = None,
) -> OwnerBookingService:
    return OwnerBookingService(
        cast(async_sessionmaker, session_factory or _fake_session_factory),
        storefront=cast(StorefrontService, storefront or _FakeStorefront([])),
        comms=cast(BookingCommsService, object()),
        sms_limiter=sms_limiter or FixedWindowRateLimiter(20, 3600.0, lambda: 0.0),
        clock=lambda: NOW,
    )


def _spent_limiter() -> FixedWindowRateLimiter:
    """max_attempts=0, so `is_blocked` is True for every key from the first call."""
    return FixedWindowRateLimiter(0, 3600.0, lambda: 0.0)


def _booking(**overrides: object) -> Booking:
    row = Booking(
        tenant_id=TENANT_ID,
        customer_id=uuid.uuid4(),
        appointment_type_id=uuid.uuid4(),
        starts_at=datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC),
        seat_index=1,
        terms_version_accepted=1,
        terms_accepted_at=NOW,
        appointment_type_name="מדידת שמלה",
    )
    row.id = uuid.uuid4()
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


@pytest.fixture
def day_calls(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    """Records what actually reaches BookingsRepository.list_day."""
    calls: list[dict[str, object]] = []

    async def _list_day(
        self: object,
        session: object,
        tenant_id: uuid.UUID,
        *,
        from_instant: datetime.datetime,
        until_instant: datetime.datetime,
        offset: int,
        limit: int,
    ) -> tuple[list[Booking], int]:
        calls.append(
            {
                "from_instant": from_instant,
                "until_instant": until_instant,
                "offset": offset,
                "limit": limit,
            }
        )
        return [], 0

    monkeypatch.setattr(BookingsRepository, "list_day", _list_day)
    return calls


# --- the Jerusalem day becomes a half-open UTC pair ---


async def test_the_date_becomes_boutique_midnight_to_next_boutique_midnight(
    day_calls: list[dict[str, object]],
) -> None:
    await _service().list_day(
        TENANT_ID, date=datetime.date(2026, 8, 2), offset=0, limit=BOOKING_LIST_DEFAULT_LIMIT
    )
    expected_start = datetime.datetime(2026, 8, 2, 0, 0, tzinfo=BOUTIQUE_TIMEZONE).astimezone(
        datetime.UTC
    )
    expected_end = datetime.datetime(2026, 8, 3, 0, 0, tzinfo=BOUTIQUE_TIMEZONE).astimezone(
        datetime.UTC
    )
    assert day_calls[0]["from_instant"] == expected_start
    assert day_calls[0]["until_instant"] == expected_end
    # Half-open on the right, and Israel is UTC+3 in August.
    assert expected_end - expected_start == datetime.timedelta(hours=24)


@pytest.mark.parametrize(
    ("date", "hours"),
    [
        # Israel springs forward on the last Friday of March: that Jerusalem
        # day is 23 hours long, and the window has to be 23 hours too — a
        # hardcoded +24h would silently drop the day's last booking.
        (datetime.date(2026, 3, 27), 23),
        # …and back on the last Sunday of October: 25 hours.
        (datetime.date(2026, 10, 25), 25),
    ],
)
async def test_a_dst_boundary_day_is_still_one_whole_jerusalem_day(
    day_calls: list[dict[str, object]], date: datetime.date, hours: int
) -> None:
    await _service().list_day(TENANT_ID, date=date, offset=0, limit=10)
    span = cast(datetime.datetime, day_calls[0]["until_instant"]) - cast(
        datetime.datetime, day_calls[0]["from_instant"]
    )
    assert span == datetime.timedelta(hours=hours)


# --- paging, clamped below the router ---


async def test_offset_above_the_ceiling_is_clamped_before_the_repository(
    day_calls: list[dict[str, object]],
) -> None:
    # Unbounded Python ints bind into OFFSET $n::BIGINT: without the ceiling
    # this is a 500 out of asyncpg's encoder, not a bounded page. The router's
    # Query bound cannot be the only clamp — a non-router caller enters here.
    await _service().list_day(TENANT_ID, date=datetime.date(2026, 8, 2), offset=2**63, limit=10)
    assert (day_calls[0]["offset"], day_calls[0]["limit"]) == (MAX_LIST_OFFSET, 10)


async def test_paging_floors_and_ceilings(day_calls: list[dict[str, object]]) -> None:
    await _service().list_day(TENANT_ID, date=datetime.date(2026, 8, 2), offset=-5, limit=100_000)
    assert (day_calls[0]["offset"], day_calls[0]["limit"]) == (0, BOOKING_LIST_MAX_LIMIT)


# --- detail ---


async def test_detail_returns_the_booking(monkeypatch: pytest.MonkeyPatch) -> None:
    found = _booking()

    async def _by_id(
        self: object, session: object, tenant_id: uuid.UUID, booking_id: uuid.UUID
    ) -> Booking:
        return found

    monkeypatch.setattr(BookingsRepository, "by_id", _by_id)
    assert await _service().detail(TENANT_ID, found.id) is found


async def test_an_unknown_booking_is_a_domain_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """BookingNotFoundError subclasses DomainNotFoundError, so the app-wide
    handler bound to the base answers it — F15 adds no 404 handler."""

    async def _missing(
        self: object, session: object, tenant_id: uuid.UUID, booking_id: uuid.UUID
    ) -> None:
        return None

    monkeypatch.setattr(BookingsRepository, "by_id", _missing)
    with pytest.raises(BookingNotFoundError):
        await _service().detail(TENANT_ID, uuid.uuid4())


# --- the owner slot grid delegates, it does not re-materialize ---


async def test_list_slots_is_one_call_into_the_storefront_service() -> None:
    """A second materializer is the one thing slots.py exists to forbid: the
    owner grid is StorefrontService.list_slots plus an owner projection (D6)."""
    slots = [
        Slot(
            starts_at=datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC), capacity=2, booked=1
        )
    ]
    storefront = _FakeStorefront(slots)
    returned = await _service(storefront).list_slots(
        TENANT_ID, from_date=datetime.date(2026, 8, 2), to_date=datetime.date(2026, 8, 3)
    )
    assert returned == slots
    assert storefront.calls == [(datetime.date(2026, 8, 2), datetime.date(2026, 8, 3))]
    # Full Slot objects, so the owner projection has capacity and remaining to
    # render — the two fields the storefront's own projection drops.
    assert (returned[0].capacity, returned[0].remaining) == (2, 1)


# --- the response models ---


def test_manage_token_hash_is_on_no_response_model() -> None:
    """It is the stored half of a live control credential. `manage_link_issued`
    is the only thing about it that reaches the wire."""
    for model in (OwnerBookingRow, OwnerBookingDetail, OwnerSlotRow):
        assert "manage_token_hash" not in model.model_fields
    assert "manage_link_issued" in OwnerBookingDetail.model_fields
    assert OwnerBookingDetail.model_fields["manage_link_issued"].annotation is bool


def test_the_phone_and_the_notes_are_detail_only() -> None:
    """D18: the day list is a glance, not a bulk export of every bride's phone."""
    for field in ("customer_phone", "notes"):
        assert field not in OwnerBookingRow.model_fields
        assert field in OwnerBookingDetail.model_fields


def test_the_detail_carries_every_list_field() -> None:
    assert set(OwnerBookingRow.model_fields) <= set(OwnerBookingDetail.model_fields)


def test_the_list_response_is_the_house_envelope() -> None:
    assert set(OwnerBookingListResponse.model_fields) == {"items", "total", "offset", "limit"}
    assert set(OwnerSlotListResponse.model_fields) == {"slots"}


def test_request_models_reject_an_unknown_key() -> None:
    """ForbidExtraModel, so a typo'd key is a house-shape 400 rather than a
    silently ignored field."""
    with pytest.raises(ValueError):
        RescheduleRequest(starts_at=NOW, seat_index=2)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        PhoneCorrectionRequest(phone="050-123-4567", attested=True)  # type: ignore[call-arg]


def test_reschedule_rejects_a_naive_datetime() -> None:
    with pytest.raises(ValueError):
        RescheduleRequest(starts_at=datetime.datetime(2026, 8, 2, 7, 0))


# ---------------------------------------------------------------------------
# The D3 transition graph (Task 8)
#
# The shape under test is read → compare → return-or-raise → guarded write →
# audit, and the ORDER is the correctness argument: a 409 that has already
# written an audit row, or a no-op that wrote one, is the failure this section
# exists to catch. So every case asserts what was written as well as what was
# answered.
# ---------------------------------------------------------------------------

_UNSET = object()


def _derive(row: Booking, **changes: object) -> Booking:
    """A post-write re-read of the same booking — the shape every guarded writer
    answers with (they all return through a trailing `by_id`)."""
    fields: dict[str, object] = {
        "id": row.id,
        "customer_id": row.customer_id,
        "starts_at": row.starts_at,
        "seat_index": row.seat_index,
        "status": row.status,
    }
    fields.update(changes)
    return _booking(**fields)


class _Writes:
    """Every read and write the owner paths can make, in call order."""

    def __init__(self, loaded: Booking | None) -> None:
        self.loaded = loaded
        self.order: list[str] = []
        self.set_status: list[dict[str, Any]] = []
        self.cancel: list[dict[str, Any]] = []
        self.cancel_pending: list[uuid.UUID] = []
        self.audit: list[dict[str, Any]] = []
        self.offered_slot: list[dict[str, Any]] = []
        self.active_at: list[dict[str, Any]] = []
        self.reschedule: list[dict[str, Any]] = []
        self.reminder: list[dict[str, Any]] = []
        self.by_phone: list[str] = []
        self.set_phone: list[dict[str, Any]] = []
        self.rotations: list[dict[str, Any]] = []
        self.repoint: list[dict[str, Any]] = []


def _install(
    monkeypatch: pytest.MonkeyPatch,
    booking: Booking | None,
    *,
    write_result: Any = _UNSET,
) -> _Writes:
    writes = _Writes(booking)

    async def _by_id(
        self: object, session: object, tenant_id: uuid.UUID, booking_id: uuid.UUID
    ) -> Booking | None:
        writes.order.append("by_id")
        return booking

    async def _set_status(
        self: object,
        session: object,
        tenant_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        to: str,
        allowed_from: tuple[str, ...],
        not_before: datetime.datetime | None = None,
        not_after: datetime.datetime | None = None,
    ) -> Booking | None:
        writes.order.append("set_status")
        writes.set_status.append(
            {
                "to": to,
                "allowed_from": allowed_from,
                "not_before": not_before,
                "not_after": not_after,
            }
        )
        if write_result is not _UNSET:
            return cast(Booking | None, write_result)
        assert booking is not None
        return _derive(booking, status=to)

    async def _cancel(
        self: object,
        session: object,
        tenant_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        at: datetime.datetime,
        by: str,
        not_before: datetime.datetime | None = None,
    ) -> Booking | None:
        writes.order.append("cancel")
        writes.cancel.append({"at": at, "by": by, "not_before": not_before})
        if write_result is not _UNSET:
            return cast(Booking | None, write_result)
        assert booking is not None
        return _derive(booking, status=CANCELLED, cancelled_at=at, cancelled_by=by)

    async def _cancel_pending(
        self: object,
        session: object,
        tenant_id: uuid.UUID,
        *,
        booking_id: uuid.UUID,
        kind: str,
    ) -> int:
        writes.order.append("cancel_pending")
        writes.cancel_pending.append(booking_id)
        return 1

    async def _record(
        self: object,
        session: object,
        *,
        tenant_id: uuid.UUID,
        action: str,
        actor_id: uuid.UUID | None = None,
        entity: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        writes.order.append("audit")
        # `audit_log.details` is JSONB and `session.add` type-checks nothing, so
        # a datetime or a UUID in there raises at FLUSH — which a fake-repo suite
        # would never see. Every audit-writing path pays this one line.
        json.dumps(details)
        writes.audit.append(
            {"action": action, "actor_id": actor_id, "entity": entity, "details": details}
        )

    monkeypatch.setattr(BookingsRepository, "by_id", _by_id)
    monkeypatch.setattr(BookingsRepository, "set_status", _set_status)
    monkeypatch.setattr(BookingsRepository, "cancel", _cancel)
    monkeypatch.setattr(ScheduledMessagesRepository, "cancel_pending", _cancel_pending)
    monkeypatch.setattr(AuditLogRepository, "record", _record)
    return writes


async def _apply(service: OwnerBookingService, verb: str, booking_id: uuid.UUID) -> Any:
    method = getattr(service, verb)
    return await method(TENANT_ID, booking_id, staff=STAFF)


# --- the legal moves ---


@pytest.mark.parametrize(
    ("verb", "start_status", "starts_at", "target", "action"),
    [
        ("no_show", CONFIRMED, PAST, NO_SHOW, AuditAction.BOOKING_NO_SHOW),
        ("complete", CONFIRMED, PAST, COMPLETED, AuditAction.BOOKING_COMPLETED),
        ("no_show", COMPLETED, PAST, NO_SHOW, AuditAction.BOOKING_NO_SHOW),
        ("complete", NO_SHOW, PAST, COMPLETED, AuditAction.BOOKING_COMPLETED),
        # The undo of a mis-tap, and it has no clock bound at all: a future
        # no_show is nonsense the graph never produces, but a mis-tap noticed
        # late is still correctable.
        ("confirm", NO_SHOW, PAST, CONFIRMED, AuditAction.BOOKING_CONFIRMED),
        ("confirm", COMPLETED, PAST, CONFIRMED, AuditAction.BOOKING_CONFIRMED),
    ],
)
async def test_a_legal_transition_writes_the_row_and_exactly_one_audit_row(
    monkeypatch: pytest.MonkeyPatch,
    verb: str,
    start_status: str,
    starts_at: datetime.datetime,
    target: str,
    action: AuditAction,
) -> None:
    booking = _booking(status=start_status, starts_at=starts_at)
    writes = _install(monkeypatch, booking)

    result = await _apply(_service(), verb, booking.id)

    assert (result.booking.status, result.changed) == (target, True)
    assert writes.order == ["by_id", "set_status", "audit"]
    assert writes.set_status[0]["to"] == target
    assert writes.audit == [
        {
            "action": action.value,
            "actor_id": STAFF.id,
            "entity": str(booking.id),
            "details": {"from": start_status, "to": target},
        }
    ]


@pytest.mark.parametrize("verb", ["no_show", "complete"])
async def test_the_attendance_writes_carry_the_past_clock_bound(
    monkeypatch: pytest.MonkeyPatch, verb: str
) -> None:
    """`not_after` on the write, not only the Python check: the predicate is what
    makes the write safe under a concurrent writer, and the Python check is what
    makes the ANSWER honest (D3 step 4)."""
    booking = _booking(status=CONFIRMED, starts_at=PAST)
    writes = _install(monkeypatch, booking)
    await _apply(_service(), verb, booking.id)
    assert writes.set_status[0]["not_after"] == NOW
    assert writes.set_status[0]["not_before"] is None


async def test_confirm_carries_no_clock_bound_and_never_touches_attendance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`attendance_confirmed_at` is F16's column — it means the BRIDE said she is
    coming. The owner correcting her own record of the outcome does not speak
    for her, so `/confirm` writes `status` only (D3)."""
    booking = _booking(status=NO_SHOW, starts_at=PAST, attendance_confirmed_at=None)
    writes = _install(monkeypatch, booking)
    result = await _apply(_service(), "confirm", booking.id)
    assert (writes.set_status[0]["not_after"], writes.set_status[0]["not_before"]) == (None, None)
    assert result.booking.attendance_confirmed_at is None


async def test_owner_cancel_writes_the_evidence_and_kills_the_pending_reminder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`notify_owner_cancel` does not touch `scheduled_messages` (comms.py), so
    without this the customer gets a cancellation SMS and then a reminder for
    the cancelled appointment. The customer path already does it (manage.py)."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)

    result = await _apply(_service(), "cancel", booking.id)

    assert (result.booking.status, result.changed) == (CANCELLED, True)
    assert result.booking.cancelled_by == BookingCancelledBy.OWNER.value
    assert result.booking.cancelled_at == NOW
    assert writes.order == ["by_id", "cancel", "cancel_pending", "audit"]
    assert writes.cancel == [{"at": NOW, "by": BookingCancelledBy.OWNER.value, "not_before": NOW}]
    assert writes.cancel_pending == [booking.id]
    assert writes.audit[0]["action"] == AuditAction.BOOKING_CANCELLED.value
    assert writes.audit[0]["details"] == {"from": CONFIRMED, "to": CANCELLED}


@pytest.mark.parametrize("verb", ["no_show", "complete", "confirm"])
async def test_the_attendance_verbs_write_nothing_to_scheduled_messages(
    monkeypatch: pytest.MonkeyPatch, verb: str
) -> None:
    """D13: they are guarded on `starts_at <= now`, so the reminder has already
    fired or the worker's claim-time re-check flips it. And they send nothing."""
    booking = _booking(status=CONFIRMED if verb != "confirm" else NO_SHOW, starts_at=PAST)
    writes = _install(monkeypatch, booking)
    await _apply(_service(), verb, booking.id)
    assert writes.cancel_pending == []


# --- the refusals: 409, and NOTHING written ---


@pytest.mark.parametrize(
    ("verb", "start_status", "starts_at"),
    [
        # Cancelling is a thing you do to a FUTURE appointment.
        ("cancel", CONFIRMED, PAST),
        # Attendance is a thing you record about a PAST one.
        ("no_show", CONFIRMED, FUTURE),
        ("complete", CONFIRMED, FUTURE),
        # A booking the bride actually attended must never get `cancelled_at` —
        # E4 #19 reads that field to evaluate refund-due versus forfeit.
        ("cancel", NO_SHOW, FUTURE),
        ("cancel", COMPLETED, FUTURE),
        # `cancelled` is terminal: reviving re-enters both partial unique
        # indexes against a seat that may since have been sold.
        ("no_show", CANCELLED, PAST),
        ("complete", CANCELLED, PAST),
        ("confirm", CANCELLED, PAST),
    ],
)
async def test_an_illegal_pair_or_clock_is_a_409_that_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, verb: str, start_status: str, starts_at: datetime.datetime
) -> None:
    booking = _booking(status=start_status, starts_at=starts_at)
    writes = _install(monkeypatch, booking)

    with pytest.raises(BookingTransitionInvalidError):
        await _apply(_service(), verb, booking.id)

    assert writes.order == ["by_id"]
    assert writes.audit == []


@pytest.mark.parametrize(
    ("verb", "status"),
    [
        ("confirm", CONFIRMED),
        ("cancel", CANCELLED),
        ("no_show", NO_SHOW),
        ("complete", COMPLETED),
    ],
)
async def test_a_repeat_of_the_same_transition_is_200_unchanged_and_writes_no_audit_row(
    monkeypatch: pytest.MonkeyPatch, verb: str, status: str
) -> None:
    """A no-op is not a transition, so there is nothing to record: {from: x, to: x}
    rows would be noise in the one trail this feature has (D3 step 2).

    PAST deliberately, including for cancel — the idempotent answer is checked
    BEFORE the clock, the `manage.py` shape.
    """
    booking = _booking(status=status, starts_at=PAST)
    writes = _install(monkeypatch, booking)

    result = await _apply(_service(), verb, booking.id)

    assert result.booking is booking
    assert result.changed is False
    assert writes.order == ["by_id"]


@pytest.mark.parametrize("verb", ["confirm", "cancel", "no_show", "complete"])
async def test_an_unknown_booking_is_a_404_on_every_transition(
    monkeypatch: pytest.MonkeyPatch, verb: str
) -> None:
    writes = _install(monkeypatch, None)
    with pytest.raises(BookingNotFoundError):
        await _apply(_service(), verb, uuid.uuid4())
    assert writes.order == ["by_id"]


# --- the guarded write is the belt, and losing it rolls back ---


@pytest.mark.parametrize(
    ("verb", "start_status", "starts_at"),
    [
        ("no_show", CONFIRMED, PAST),
        ("complete", CONFIRMED, PAST),
        ("confirm", NO_SHOW, PAST),
        ("cancel", CONFIRMED, FUTURE),
    ],
)
async def test_a_zero_row_guarded_write_is_a_409_with_no_audit_row(
    monkeypatch: pytest.MonkeyPatch, verb: str, start_status: str, starts_at: datetime.datetime
) -> None:
    """Another request moved the row between the read and the write. The 409 is
    honest and the rollback is what keeps the trail honest: committing an audit
    row for a move that did not happen is worse than the 409."""
    booking = _booking(status=start_status, starts_at=starts_at)
    writes = _install(monkeypatch, booking, write_result=None)

    with pytest.raises(BookingTransitionInvalidError):
        await _apply(_service(), verb, booking.id)

    assert writes.audit == []
    assert "cancel_pending" not in writes.order


async def test_a_cancel_whose_row_comes_back_uncancelled_is_a_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`BookingsRepository.cancel` answers through a trailing `by_id` and so
    always returns a row — the customer path depends on that. So the owner
    path's zero-row signal is the re-read's status, not a `None`."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    unchanged = _derive(booking, status=CONFIRMED)
    writes = _install(monkeypatch, booking, write_result=unchanged)

    with pytest.raises(BookingTransitionInvalidError):
        await _apply(_service(), "cancel", booking.id)

    assert writes.audit == []
    assert writes.cancel_pending == []


# --- cancel is deliberately off the owner-SMS budget (D10) ---


async def test_cancel_is_not_metered_by_the_owner_sms_limiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`cancelled` is terminal, so cancel is bounded at one SMS per booking by
    construction and the ceiling is the number of bookings the boutique has."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    _install(monkeypatch, booking)
    result = await _apply(_service(sms_limiter=_spent_limiter()), "cancel", booking.id)
    assert result.changed is True


# ---------------------------------------------------------------------------
# The D5 reschedule protocol (Task 9)
#
# Eight ordered steps in one transaction, and the ORDER is the correctness
# argument — a test that would still pass with the steps reordered is not
# testing this. The one that matters most is the advisory lock preceding the
# read: with the read outside the lock, two submissions of the same dialog both
# see the ORIGINAL `starts_at`, the second misses the no-op short-circuit, and
# step 5's `active_at` then finds the booking ITSELF.
# ---------------------------------------------------------------------------

TARGET = datetime.datetime(2026, 8, 9, 7, 0, tzinfo=datetime.UTC)
YEAR_9999 = datetime.datetime(9999, 12, 31, 23, 0, tzinfo=datetime.UTC)


def _slot(starts_at: datetime.datetime = TARGET, *, capacity: int = 2, booked: int = 0) -> Slot:
    return Slot(starts_at=starts_at, capacity=capacity, booked=booked)


def _install_reschedule(
    monkeypatch: pytest.MonkeyPatch,
    writes: _Writes,
    *,
    slot: Slot | None = None,
    seats: set[int] | None = None,
    collision: Booking | None = None,
    result: Any = _UNSET,
    reminder: datetime.datetime | None = None,
) -> None:
    """Layers the reschedule-only collaborators onto `_install`'s recorder."""

    async def _offered_slot(session: object, **kwargs: object) -> Slot | None:
        writes.order.append("offered_slot")
        writes.offered_slot.append(dict(kwargs))
        return slot

    async def _active_at(
        self: object,
        session: object,
        tenant_id: uuid.UUID,
        *,
        customer_id: uuid.UUID,
        starts_at: datetime.datetime,
    ) -> Booking | None:
        writes.order.append("active_at")
        writes.active_at.append({"customer_id": customer_id, "starts_at": starts_at})
        return collision

    async def _active_seats_at(
        self: object, session: object, tenant_id: uuid.UUID, *, starts_at: datetime.datetime
    ) -> set[int]:
        writes.order.append("active_seats_at")
        return set(seats or set())

    async def _reschedule(
        self: object,
        session: object,
        tenant_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        starts_at: datetime.datetime,
        seat_index: int,
        not_before: datetime.datetime,
    ) -> Booking | None:
        writes.order.append("reschedule")
        writes.reschedule.append(
            {"starts_at": starts_at, "seat_index": seat_index, "not_before": not_before}
        )
        if isinstance(result, BaseException):
            raise result
        if result is not _UNSET:
            return cast(Booking | None, result)
        assert writes.loaded is not None
        return _derive(writes.loaded, starts_at=starts_at, seat_index=seat_index)

    async def _upsert_reminder(session: object, **kwargs: object) -> datetime.datetime | None:
        writes.order.append("upsert_reminder")
        writes.reminder.append(dict(kwargs))
        return reminder

    monkeypatch.setattr("app.booking.owner.offered_slot", _offered_slot)
    monkeypatch.setattr("app.booking.owner.upsert_reminder", _upsert_reminder)
    monkeypatch.setattr(BookingsRepository, "active_at", _active_at)
    monkeypatch.setattr(BookingsRepository, "active_seats_at", _active_seats_at)
    monkeypatch.setattr(BookingsRepository, "reschedule", _reschedule)


# --- step 0: the horizon guard, before any arithmetic ---


async def test_a_year_9999_target_is_a_409_and_not_an_overflow_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`AwareDatetime` accepts the whole datetime range and `.astimezone()` on a
    year-9999 instant raises `OverflowError` — an unhandled 500. Comparison
    itself cannot overflow, so the guard is total (service.py:180-186)."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot())

    with pytest.raises(SlotUnavailableError):
        await _service().reschedule(TENANT_ID, booking.id, new_starts_at=YEAR_9999, staff=STAFF)

    # Before ANY arithmetic means before the transaction, so not even the read ran.
    assert writes.order == []


async def test_a_target_in_the_past_never_reaches_the_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot())
    with pytest.raises(SlotUnavailableError):
        await _service().reschedule(TENANT_ID, booking.id, new_starts_at=PAST, staff=STAFF)
    assert writes.order == []


# --- step 1: the lock, BEFORE the read ---


async def test_the_advisory_lock_is_taken_before_the_booking_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """This is the assertion that fails if the read moves back above the lock.

    With the read outside the lock, two submissions of the same reschedule
    dialog both read `starts_at = T0`; A moves the booking to T2 and commits; B
    wakes holding a stale row, misses the no-op short-circuit, and `active_at`
    finds the booking itself — a spurious CUSTOMER_ALREADY_BOOKED. The audit row
    would be wrong too: T0 -> T2 for a move that was T1 -> T2.
    """
    booking = _booking(status=CONFIRMED, starts_at=FUTURE, seat_index=1)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot())

    await _service(session_factory=_recording_session_factory(writes.order)).reschedule(
        TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF
    )

    assert writes.order.index("advisory_lock") < writes.order.index("by_id")
    assert writes.order == [
        "advisory_lock",
        "by_id",
        "offered_slot",
        "active_at",
        "active_seats_at",
        "reschedule",
        "upsert_reminder",
        "audit",
    ]


# --- step 2: load and guard ---


async def test_rescheduling_an_unknown_booking_is_a_404(monkeypatch: pytest.MonkeyPatch) -> None:
    writes = _install(monkeypatch, None)
    _install_reschedule(monkeypatch, writes, slot=_slot())
    with pytest.raises(BookingNotFoundError):
        await _service().reschedule(TENANT_ID, uuid.uuid4(), new_starts_at=TARGET, staff=STAFF)


@pytest.mark.parametrize("status", [CANCELLED, NO_SHOW, COMPLETED])
async def test_only_a_confirmed_booking_moves(monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    booking = _booking(status=status, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot())
    with pytest.raises(BookingTransitionInvalidError):
        await _service().reschedule(TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF)
    assert writes.audit == []
    assert writes.reschedule == []


async def test_a_past_booking_cannot_be_rewritten_into_next_week(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guarding only on status would let a Tuesday no-show be silently rewritten
    into next week's appointment — overwriting the very `starts_at` the
    attendance record turns on, and texting the bride a confirmation for the
    appointment she missed."""
    booking = _booking(status=CONFIRMED, starts_at=PAST)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot())
    with pytest.raises(BookingTransitionInvalidError):
        await _service().reschedule(TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF)
    assert writes.audit == []


# --- step 3: the no-op short-circuit ---


async def test_a_move_to_the_instant_it_already_holds_writes_nothing_anywhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Not a nicety: `active_at` and `active_seats_at` have no booking-id
    exclusion, so a no-op move would find ITSELF and 409 a capacity-1 booking
    against its own seat."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot())

    limiter = FixedWindowRateLimiter(20, 3600.0, lambda: 0.0)
    result = await _service(sms_limiter=limiter).reschedule(
        TENANT_ID, booking.id, new_starts_at=FUTURE, staff=STAFF
    )

    assert (result.booking is booking, result.changed) == (True, False)
    assert writes.order == ["by_id"]
    # A no-op spends no budget either: no mutation, no SMS.
    assert limiter.is_blocked(f"booking:owner_sms:{TENANT_ID}") is False


# --- steps 4-6: the three distinguishable 409s ---


async def test_an_unoffered_target_is_slot_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """One call buys past instants, off-grid times, closed and exception days,
    the DST rules and capacity — full slots are DROPPED rather than marked."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=None)
    with pytest.raises(SlotUnavailableError):
        await _service().reschedule(TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF)
    assert writes.audit == []
    assert writes.reschedule == []


async def test_the_customer_already_holding_the_target_is_its_own_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """0009's index means one person cannot be at two appointments at one
    instant, and this is a genuinely different failure from a full slot: the
    target can have free seats and still be unmovable-into for THIS bride."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot(), collision=_booking())

    with pytest.raises(CustomerAlreadyBookedError):
        await _service().reschedule(TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF)

    assert writes.active_at == [{"customer_id": booking.customer_id, "starts_at": TARGET}]
    assert writes.reschedule == []


async def test_a_target_whose_every_seat_is_taken_is_slot_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking = _booking(status=CONFIRMED, starts_at=FUTURE, seat_index=1)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot(capacity=2), seats={1, 2})
    with pytest.raises(SlotUnavailableError):
        await _service().reschedule(TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF)
    assert writes.reschedule == []


async def test_the_old_seat_is_never_carried_across(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing in the database bounds a seat by its slot's capacity — 0008's
    CHECK is 1..1000 — so carrying seat 3 into a capacity-1 target satisfies
    both the CHECK and the unique index and is a SILENT oversell. The lowest
    free seat at the target is the only correct answer."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE, seat_index=3)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot(capacity=3), seats={2})

    result = await _service().reschedule(TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF)

    assert writes.reschedule[0]["seat_index"] == 1
    assert result.booking.seat_index == 1


# --- step 7: the guarded write ---


async def test_the_move_is_guarded_on_a_confirmed_future_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot())
    await _service().reschedule(TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF)
    assert writes.reschedule[0]["not_before"] == NOW
    assert writes.reschedule[0]["starts_at"] == TARGET


async def test_a_zero_row_move_rolls_back_before_the_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The per-tenant lock serializes this against public creates but NOT
    against the four owner status endpoints, which take no lock — so a
    concurrent owner cancel can land between the read and the write."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot(), result=None)

    with pytest.raises(BookingTransitionInvalidError):
        await _service().reschedule(TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF)

    assert writes.audit == []
    assert writes.reminder == []


async def test_a_lost_index_race_becomes_slot_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same backstop mapping `create_booking` uses for its own lost race."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_reschedule(
        monkeypatch,
        writes,
        slot=_slot(),
        result=IntegrityError("UPDATE bookings", {}, Exception("duplicate key")),
    )
    with pytest.raises(SlotUnavailableError):
        await _service().reschedule(TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF)
    assert writes.audit == []


# --- step 8: the reminder and the audit row, in this transaction ---


async def test_the_reminder_upsert_runs_inside_the_transaction_before_the_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Post-commit, a crash loses or mis-schedules the reminder with nothing
    sweeping for the gap, and `drain_due` can claim the stale pending row and
    clear its token in the window (D11)."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE, seat_index=3)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot(capacity=2), reminder=TARGET)

    await _service().reschedule(TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF)

    assert writes.order.index("upsert_reminder") < writes.order.index("audit")
    assert writes.reminder[0]["booking_id"] == booking.id
    assert writes.reminder[0]["starts_at"] == TARGET
    assert writes.reminder[0]["now"] == NOW


async def test_a_suppressed_reminder_is_not_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """`None` means the moved appointment is inside the <2h band and legitimately
    gets no reminder — it must not surface as a failure."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot(), reminder=None)
    result = await _service().reschedule(TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF)
    assert result.changed is True
    assert len(writes.audit) == 1


async def test_the_audit_row_names_both_instants_and_both_seats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking = _booking(status=CONFIRMED, starts_at=FUTURE, seat_index=3)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot(capacity=3), seats={1})

    await _service().reschedule(TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF)

    assert writes.audit == [
        {
            "action": AuditAction.BOOKING_RESCHEDULED.value,
            "actor_id": STAFF.id,
            "entity": str(booking.id),
            "details": {
                # ISO strings: `details` is JSONB, and a datetime in there is a
                # TypeError at flush that only the db-marked suite would see.
                "old_starts_at": FUTURE.isoformat(),
                "new_starts_at": TARGET.isoformat(),
                "old_seat_index": 3,
                "new_seat_index": 2,
            },
        }
    ]


# --- the budget, before the transaction opens (D10) ---


async def test_a_throttled_reschedule_writes_nothing_and_never_opens_a_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot())

    with pytest.raises(OwnerResendThrottledError):
        await _service(sms_limiter=_spent_limiter()).reschedule(
            TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF
        )

    assert writes.order == []


async def test_a_committed_reschedule_spends_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """One tap, one unit — the class counts only what the caller records, and
    what D10 meters is the owner tap that caused a real SMS attempt (C4)."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_reschedule(monkeypatch, writes, slot=_slot())

    limiter = FixedWindowRateLimiter(1, 3600.0, lambda: 0.0)
    await _service(sms_limiter=limiter).reschedule(
        TENANT_ID, booking.id, new_starts_at=TARGET, staff=STAFF
    )

    assert limiter.is_blocked(f"booking:owner_sms:{TENANT_ID}") is True


# ---------------------------------------------------------------------------
# Phone correction and resend (Task 10) — the feature's dangerous surface
#
# The corrected number is OWNER-ATTESTED: no OTP, because requiring one would
# require the bride to be reachable at the number that demonstrably does not
# work. What makes that safe enough is mechanical, and every mechanic below has
# a test: normalize first, meter before the transaction opens, rotate INSIDE the
# write, roll back on any failed rotation, and never put a full number in the
# audit row.
# ---------------------------------------------------------------------------

WRONG_PHONE = "+972500001111"
RIGHT_PHONE = "+972500002222"
TOKENS = ["tok-one", "tok-two", "tok-three"]


class _FakeCustomer:
    def __init__(self, phone: str, customer_id: uuid.UUID | None = None) -> None:
        self.id = customer_id or uuid.uuid4()
        self.phone = phone


class _FakePending:
    """The pending reminder row. `reissue_manage_token` re-points it by ORM
    attribute assignment inside the session, and F15 mirrors that exactly."""

    def __init__(self) -> None:
        self.manage_token: str | None = "stale-token"


def _install_rotation(
    monkeypatch: pytest.MonkeyPatch,
    writes: _Writes,
    *,
    live: list[Booking] | None = None,
    by_phone: _FakeCustomer | None = None,
    owner_customer: _FakeCustomer | None = None,
    collision: Booking | None = None,
    set_phone_result: Any = _UNSET,
    hash_result: Any = _UNSET,
    repoint_result: Any = _UNSET,
    pending: dict[uuid.UUID, _FakePending] | None = None,
) -> None:
    minted = list(TOKENS)

    def _mint() -> str:
        return minted.pop(0)

    async def _by_phone(self: object, session: object, tenant_id: uuid.UUID, *, phone: str) -> Any:
        writes.order.append("by_phone")
        writes.by_phone.append(phone)
        return by_phone

    async def _customer_by_id(
        self: object, session: object, tenant_id: uuid.UUID, customer_id: uuid.UUID
    ) -> Any:
        return owner_customer

    async def _set_phone(
        self: object, session: object, tenant_id: uuid.UUID, customer_id: uuid.UUID, *, phone: str
    ) -> Any:
        writes.order.append("set_phone")
        writes.set_phone.append({"customer_id": customer_id, "phone": phone})
        if set_phone_result is not _UNSET:
            return set_phone_result
        return _FakeCustomer(phone, customer_id)

    async def _list_live(
        self: object,
        session: object,
        tenant_id: uuid.UUID,
        *,
        customer_id: uuid.UUID,
        after: datetime.datetime,
    ) -> list[Booking]:
        writes.order.append("list_live")
        return list(live or [])

    async def _set_hash(
        self: object,
        session: object,
        tenant_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        token_hash: str,
        allowed_from: tuple[str, ...] | None = None,
        not_before: datetime.datetime | None = None,
    ) -> Booking | None:
        writes.order.append("set_manage_token_hash")
        writes.rotations.append(
            {"booking_id": booking_id, "allowed_from": allowed_from, "not_before": not_before}
        )
        if hash_result is not _UNSET:
            return cast(Booking | None, hash_result)
        assert writes.loaded is not None
        return _derive(writes.loaded)

    async def _set_customer_id(
        self: object,
        session: object,
        tenant_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        customer_id: uuid.UUID,
        allowed_from: tuple[str, ...],
        not_before: datetime.datetime,
    ) -> Booking | None:
        writes.order.append("set_customer_id")
        writes.repoint.append({"booking_id": booking_id, "customer_id": customer_id})
        if isinstance(repoint_result, BaseException):
            raise repoint_result
        if repoint_result is not _UNSET:
            return cast(Booking | None, repoint_result)
        assert writes.loaded is not None
        return _derive(writes.loaded, customer_id=customer_id)

    async def _pending_for_booking(
        self: object, session: object, tenant_id: uuid.UUID, *, booking_id: uuid.UUID, kind: str
    ) -> Any:
        return (pending or {}).get(booking_id)

    async def _active_at(
        self: object,
        session: object,
        tenant_id: uuid.UUID,
        *,
        customer_id: uuid.UUID,
        starts_at: datetime.datetime,
    ) -> Booking | None:
        writes.order.append("active_at")
        writes.active_at.append({"customer_id": customer_id, "starts_at": starts_at})
        return collision

    monkeypatch.setattr("app.booking.owner.mint_manage_token", _mint)
    monkeypatch.setattr(CustomersRepository, "by_phone", _by_phone)
    monkeypatch.setattr(CustomersRepository, "by_id", _customer_by_id)
    monkeypatch.setattr(CustomersRepository, "set_phone", _set_phone)
    monkeypatch.setattr(BookingsRepository, "list_live_for_customer", _list_live)
    monkeypatch.setattr(BookingsRepository, "set_manage_token_hash", _set_hash)
    monkeypatch.setattr(BookingsRepository, "set_customer_id", _set_customer_id)
    monkeypatch.setattr(BookingsRepository, "active_at", _active_at)
    monkeypatch.setattr(ScheduledMessagesRepository, "pending_for_booking", _pending_for_booking)


async def _correct(
    service: OwnerBookingService, booking_id: uuid.UUID, phone: str = "050-000-2222"
) -> Any:
    return await service.correct_phone(TENANT_ID, booking_id, phone=phone, staff=STAFF)


# --- mechanic 1: normalize first ---


@pytest.mark.parametrize("raw", ["", "not a phone", "+1 415 555 0100", "03-1234567"])
async def test_a_malformed_phone_is_a_400_before_anything_is_written(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    """Through the same `normalize_israeli_mobile` the claim uses, so the stored
    value stays E.164 like every other phone in the product. No client-side copy
    of this exists and none is added (D20)."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_rotation(monkeypatch, writes)

    with pytest.raises(DomainValidationError):
        await _correct(_service(), booking.id, raw)

    assert writes.order == []


async def test_the_stored_number_is_the_e164_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_rotation(
        monkeypatch, writes, live=[booking], owner_customer=_FakeCustomer(WRONG_PHONE)
    )
    await _correct(_service(), booking.id, "050-000-2222")
    assert writes.set_phone[0]["phone"] == RIGHT_PHONE
    assert writes.by_phone == [RIGHT_PHONE]


# --- mechanic 4: the guard, on both operations ---


@pytest.mark.parametrize("operation", ["correct_phone", "resend_link"])
@pytest.mark.parametrize(
    ("status", "starts_at"),
    [(CANCELLED, FUTURE), (NO_SHOW, PAST), (COMPLETED, PAST), (CONFIRMED, PAST)],
)
async def test_neither_operation_touches_a_booking_that_is_not_confirmed_and_future(
    monkeypatch: pytest.MonkeyPatch, operation: str, status: str, starts_at: datetime.datetime
) -> None:
    """A live control link must never be minted for an appointment that no
    longer exists — that is the outcome the guard exists to prevent."""
    booking = _booking(status=status, starts_at=starts_at)
    writes = _install(monkeypatch, booking)
    _install_rotation(monkeypatch, writes, live=[booking])

    with pytest.raises(BookingTransitionInvalidError):
        if operation == "correct_phone":
            await _correct(_service(), booking.id)
        else:
            await _service().resend_link(TENANT_ID, booking.id, staff=STAFF)

    assert writes.rotations == []
    assert writes.audit == []


@pytest.mark.parametrize("operation", ["correct_phone", "resend_link"])
async def test_an_unknown_booking_is_a_404_on_both_operations(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    writes = _install(monkeypatch, None)
    _install_rotation(monkeypatch, writes)
    with pytest.raises(BookingNotFoundError):
        if operation == "correct_phone":
            await _correct(_service(), uuid.uuid4())
        else:
            await _service().resend_link(TENANT_ID, uuid.uuid4(), staff=STAFF)


# --- the non-collision branch: every live booking of that customer rotates ---


async def test_the_non_collision_branch_rotates_every_live_booking_of_that_customer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`customers` IS the phone identity, so `set_phone` moves every booking that
    customer holds onto the new number — but `manage_token_hash` is per-row. A
    bride holding two live bookings against the same mistyped number would
    otherwise keep a working stranger-held cancel link on the second one."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    sibling = _booking(status=CONFIRMED, starts_at=TARGET, customer_id=booking.customer_id)
    writes = _install(monkeypatch, booking)
    sibling_pending = _FakePending()
    _install_rotation(
        monkeypatch,
        writes,
        live=[booking, sibling],
        owner_customer=_FakeCustomer(WRONG_PHONE, booking.customer_id),
        pending={sibling.id: sibling_pending},
    )

    result = await _correct(_service(), booking.id)

    assert [row["booking_id"] for row in writes.rotations] == [booking.id, sibling.id]
    # The rotation carries the guard predicate so it cannot go stale mid-loop.
    assert writes.rotations[0]["allowed_from"] == (CONFIRMED,)
    assert writes.rotations[0]["not_before"] == NOW
    # The sibling's pending reminder now carries the sibling's NEW token, or it
    # would send a link this call just invalidated.
    assert sibling_pending.manage_token == TOKENS[1]
    # ...and the token that leaves is the one minted for the EDITED booking.
    assert result.manage_token == TOKENS[0]
    assert result.changed is True


async def test_the_audit_row_names_both_customers_and_every_rotated_booking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Last4 alone cannot reconstruct the correction: `set_phone` overwrites
    `customers.phone` in place and `customers` has no history table, so the ids
    are what let an Amendment-13 complaint be answered at all."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    sibling = _booking(status=CONFIRMED, starts_at=TARGET, customer_id=booking.customer_id)
    writes = _install(monkeypatch, booking)
    _install_rotation(
        monkeypatch,
        writes,
        live=[booking, sibling],
        owner_customer=_FakeCustomer(WRONG_PHONE, booking.customer_id),
    )

    await _correct(_service(), booking.id)

    assert writes.audit == [
        {
            "action": AuditAction.BOOKING_PHONE_CORRECTED.value,
            "actor_id": STAFF.id,
            "entity": str(booking.id),
            "details": {
                "old_phone_last4": "1111",
                "new_phone_last4": "2222",
                "attested": True,
                "old_customer_id": str(booking.customer_id),
                "new_customer_id": str(booking.customer_id),
                "repointed": False,
                "rotated_booking_ids": [str(booking.id), str(sibling.id)],
            },
        }
    ]


async def test_no_full_phone_number_ever_reaches_the_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`audit_log` is retained on the AUDIT clock, not the booking clock, and a
    full number in JSONB is a second uncontrolled copy of the one PII field this
    feature exists to edit."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_rotation(
        monkeypatch,
        writes,
        live=[booking],
        owner_customer=_FakeCustomer(WRONG_PHONE, booking.customer_id),
    )
    await _correct(_service(), booking.id)
    rendered = json.dumps(writes.audit[0]["details"])
    assert WRONG_PHONE not in rendered
    assert RIGHT_PHONE not in rendered
    assert "0000" not in rendered  # nothing longer than the last four digits


# --- the collision branch: a re-point, not a merge and not a refusal ---


async def test_a_collision_repoints_the_booking_and_rotates_only_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On this branch the digits were never wrong, the IDENTITY was. The original
    customer may be a real other person whose other bookings are genuinely hers,
    so rotating them would revoke credentials nobody proved were misdirected."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    sibling = _booking(status=CONFIRMED, starts_at=TARGET, customer_id=booking.customer_id)
    target = _FakeCustomer(RIGHT_PHONE)
    writes = _install(monkeypatch, booking)
    _install_rotation(
        monkeypatch,
        writes,
        live=[booking, sibling],
        by_phone=target,
        owner_customer=_FakeCustomer(WRONG_PHONE, booking.customer_id),
    )

    result = await _correct(_service(), booking.id)

    # `customers.phone` is NOT touched and both customer rows survive.
    assert writes.set_phone == []
    assert writes.repoint == [{"booking_id": booking.id, "customer_id": target.id}]
    assert [row["booking_id"] for row in writes.rotations] == [booking.id]
    assert result.manage_token == TOKENS[0]
    assert writes.audit[0]["details"]["repointed"] is True
    assert writes.audit[0]["details"]["new_customer_id"] == str(target.id)
    assert writes.audit[0]["details"]["rotated_booking_ids"] == [str(booking.id)]


async def test_the_0009_precheck_makes_the_repoint_a_409_and_never_a_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two sisters in one capacity-2 slot at 14:00 and the owner corrects the
    first one's number to the second one's: the re-point would put two live rows
    on (tenant, customer B, 14:00) and the flush would raise. With no error
    registry that escapes as a bare 500 outside the house error shape."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    target = _FakeCustomer(RIGHT_PHONE)
    writes = _install(monkeypatch, booking)
    _install_rotation(
        monkeypatch,
        writes,
        by_phone=target,
        collision=_booking(),
        owner_customer=_FakeCustomer(WRONG_PHONE, booking.customer_id),
    )

    with pytest.raises(CustomerAlreadyBookedError):
        await _correct(_service(), booking.id)

    assert writes.active_at == [{"customer_id": target.id, "starts_at": booking.starts_at}]
    assert writes.repoint == []
    assert writes.audit == []


async def test_a_lost_0009_race_on_the_repoint_is_the_same_409_not_a_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pre-check is the answer; the flush's IntegrityError is the backstop,
    mapped to the same error the way `create_booking` treats its own race."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_rotation(
        monkeypatch,
        writes,
        by_phone=_FakeCustomer(RIGHT_PHONE),
        owner_customer=_FakeCustomer(WRONG_PHONE, booking.customer_id),
        repoint_result=IntegrityError("UPDATE bookings", {}, Exception("duplicate key")),
    )
    with pytest.raises(CustomerAlreadyBookedError):
        await _correct(_service(), booking.id)
    assert writes.audit == []


async def test_correcting_to_the_number_the_customer_already_has_is_not_a_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`by_phone` answering with the booking's OWN customer is not another
    person holding the number — it is the same person. Re-pointing a booking at
    the customer it already has would be a no-op dressed as an identity fix."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    hers = _FakeCustomer(RIGHT_PHONE, booking.customer_id)
    writes = _install(monkeypatch, booking)
    _install_rotation(monkeypatch, writes, live=[booking], by_phone=hers, owner_customer=hers)

    await _correct(_service(), booking.id)

    assert writes.repoint == []
    assert writes.set_phone[0]["customer_id"] == booking.customer_id
    assert writes.audit[0]["details"]["repointed"] is False


# --- a failed rotation is a hard failure, never a discarded result ---


@pytest.mark.parametrize("operation", ["correct_phone", "resend_link"])
async def test_a_none_from_any_rotation_aborts_the_whole_thing(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    """There must be no committed state in which the phone is corrected and the
    old hash survives: the stranger's link would still resolve and still cancel
    the bride's appointment, and nothing sweeps for it."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_rotation(
        monkeypatch,
        writes,
        live=[booking],
        owner_customer=_FakeCustomer(WRONG_PHONE, booking.customer_id),
        hash_result=None,
    )

    with pytest.raises(BookingTransitionInvalidError):
        if operation == "correct_phone":
            await _correct(_service(), booking.id)
        else:
            await _service().resend_link(TENANT_ID, booking.id, staff=STAFF)

    assert writes.audit == []


async def test_a_none_from_a_siblings_rotation_aborts_the_correction_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    sibling = _booking(status=CONFIRMED, starts_at=TARGET, customer_id=booking.customer_id)
    writes = _install(monkeypatch, booking)

    outcomes: list[Booking | None] = [_derive(booking), None]

    _install_rotation(
        monkeypatch,
        writes,
        live=[booking, sibling],
        owner_customer=_FakeCustomer(WRONG_PHONE, booking.customer_id),
    )
    original = BookingsRepository.set_manage_token_hash

    async def _flaky(*args: Any, **kwargs: Any) -> Booking | None:
        await original(*args, **kwargs)
        return outcomes.pop(0)

    monkeypatch.setattr(BookingsRepository, "set_manage_token_hash", _flaky)

    with pytest.raises(BookingTransitionInvalidError):
        await _correct(_service(), booking.id)

    assert writes.audit == []


# --- resend is a rotation, not a re-send (D9) ---


async def test_resend_rotates_this_booking_and_repoints_its_pending_reminder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plain resend is impossible anyway: `bookings` stores only the sha256 and
    `cancel_pending` clears the raw token, so nothing on the platform can
    reproduce a sent link. Rotation is the only honest behaviour on offer."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    pending = _FakePending()
    _install_rotation(monkeypatch, writes, pending={booking.id: pending})

    result = await _service().resend_link(TENANT_ID, booking.id, staff=STAFF)

    assert [row["booking_id"] for row in writes.rotations] == [booking.id]
    assert writes.rotations[0]["allowed_from"] == (CONFIRMED,)
    assert writes.rotations[0]["not_before"] == NOW
    assert pending.manage_token == TOKENS[0]
    assert result.manage_token == TOKENS[0]
    # No phone edit: neither customer writer is reached.
    assert (writes.set_phone, writes.repoint, writes.by_phone) == ([], [], [])
    assert writes.audit == [
        {
            "action": AuditAction.BOOKING_LINK_RESENT.value,
            "actor_id": STAFF.id,
            "entity": str(booking.id),
            "details": {"customer_id": str(booking.customer_id)},
        }
    ]


# --- the budget, before the transaction opens (D10) ---


@pytest.mark.parametrize("operation", ["correct_phone", "resend_link"])
async def test_a_throttled_call_writes_nothing_and_sends_nothing(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    """The natural reading — meter the send, where the SMS actually is — is the
    dangerous one: it would commit the corrected number and skip the rotation,
    leaving a live link pointing at the number the owner just proved is wrong.
    That state is reachable with no attacker, at 21 taps in an hour."""
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_rotation(
        monkeypatch,
        writes,
        live=[booking],
        owner_customer=_FakeCustomer(WRONG_PHONE, booking.customer_id),
    )
    service = _service(sms_limiter=_spent_limiter())

    with pytest.raises(OwnerResendThrottledError):
        if operation == "correct_phone":
            await _correct(service, booking.id)
        else:
            await service.resend_link(TENANT_ID, booking.id, staff=STAFF)

    assert writes.order == []
    assert (writes.set_phone, writes.rotations) == ([], [])


@pytest.mark.parametrize("operation", ["correct_phone", "resend_link"])
async def test_a_committed_correction_or_resend_spends_the_budget(
    monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    booking = _booking(status=CONFIRMED, starts_at=FUTURE)
    writes = _install(monkeypatch, booking)
    _install_rotation(
        monkeypatch,
        writes,
        live=[booking],
        owner_customer=_FakeCustomer(WRONG_PHONE, booking.customer_id),
    )
    limiter = FixedWindowRateLimiter(1, 3600.0, lambda: 0.0)
    service = _service(sms_limiter=limiter)

    if operation == "correct_phone":
        await _correct(service, booking.id)
    else:
        await service.resend_link(TENANT_ID, booking.id, staff=STAFF)

    assert limiter.is_blocked(f"booking:owner_sms:{TENANT_ID}") is True
