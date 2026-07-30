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
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.booking.comms import BookingCommsService
from app.booking.owner import MAX_LIST_OFFSET, OwnerBookingService
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
from app.db.repositories.bookings import BookingsRepository
from app.models.booking import Booking
from app.storefront.service import StorefrontService
from app.storefront.validation import BOUTIQUE_TIMEZONE

TENANT_ID = uuid.uuid4()
NOW = datetime.datetime(2026, 7, 30, 9, 0, tzinfo=datetime.UTC)


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


def _service(storefront: _FakeStorefront | None = None) -> OwnerBookingService:
    return OwnerBookingService(
        cast(async_sessionmaker, _fake_session_factory),
        storefront=cast(StorefrontService, storefront or _FakeStorefront([])),
        comms=cast(BookingCommsService, object()),
        sms_limiter=FixedWindowRateLimiter(20, 3600.0, lambda: 0.0),
        clock=lambda: NOW,
    )


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
