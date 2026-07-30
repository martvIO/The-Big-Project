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
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.booking.comms import BookingCommsService
from app.booking.owner import (
    MAX_LIST_OFFSET,
    BookingTransitionInvalidError,
    OwnerBookingService,
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
from app.booking.service import BookingNotFoundError
from app.booking.slots import Slot
from app.booking.validation import BOOKING_LIST_DEFAULT_LIMIT, BOOKING_LIST_MAX_LIMIT
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.scheduled_messages import ScheduledMessagesRepository
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
    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def execute(self, *args: object, **kwargs: object) -> None:
        return None


@asynccontextmanager
async def _fake_session_factory() -> AsyncIterator[_FakeSession]:
    yield _FakeSession()


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
) -> OwnerBookingService:
    return OwnerBookingService(
        cast(async_sessionmaker, _fake_session_factory),
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
    """Every write the transition path can make, in call order."""

    def __init__(self) -> None:
        self.order: list[str] = []
        self.set_status: list[dict[str, Any]] = []
        self.cancel: list[dict[str, Any]] = []
        self.cancel_pending: list[uuid.UUID] = []
        self.audit: list[dict[str, Any]] = []


def _install(
    monkeypatch: pytest.MonkeyPatch,
    booking: Booking | None,
    *,
    write_result: Any = _UNSET,
) -> _Writes:
    writes = _Writes()

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
