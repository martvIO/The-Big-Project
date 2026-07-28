"""Feature 10 pure units: the service-level paging clamp, the boutique wall
clock, the upcoming-exceptions cutoff, and the Instagram handle gate.

No database and no TestClient. The one piece of scaffolding here — the fake
session factory — exists so the clamp is asserted where it actually lives:
`Query(ge=1, le=...)` guards the ROUTER, and `test_storefront_api.py` covers
that, but a non-router caller (a future SSR path, a warm-up job, a shell) enters
`StorefrontService.list_dresses` directly. This module is what proves the
clamped values reach the repository rather than merely being echoed back in the
response view.
"""

import datetime
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.boutique.validation import (
    MAX_PROFILE_INSTAGRAM_LENGTH,
    BoutiqueValidationError,
    validate_instagram_handle,
    validate_profile,
)
from app.db.repositories.dresses import DressesRepository
from app.models.availability import AvailabilityException
from app.models.dress import Dress
from app.storage.unconfigured import UnconfiguredMediaStorage
from app.storefront.service import (
    MAX_LIST_OFFSET,
    StorefrontService,
    upcoming_exceptions,
)
from app.storefront.validation import (
    STOREFRONT_LIST_DEFAULT_LIMIT,
    STOREFRONT_LIST_MAX_LIMIT,
    UPCOMING_EXCEPTIONS_LIMIT,
    Clock,
    today_jerusalem,
)

TENANT_ID = uuid.uuid4()


# --- service-level paging clamp ---


class _FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeSession:
    """Enough surface for `tenant_session`'s set_config and nothing else — every
    repository call this test reaches is patched out, so a statement escaping to
    a real session would raise here instead of passing silently."""

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def execute(self, *args: object, **kwargs: object) -> None:
        return None


@asynccontextmanager
async def _fake_session_factory() -> AsyncIterator[_FakeSession]:
    yield _FakeSession()


def _service() -> StorefrontService:
    return StorefrontService(
        cast(async_sessionmaker, _fake_session_factory),
        media_storage=UnconfiguredMediaStorage(),
    )


@pytest.fixture
def paging_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    """Records the (offset, limit) that actually reach the repository."""
    calls: list[tuple[int, int]] = []

    async def _list_page(
        self: object,
        session: object,
        tenant_id: uuid.UUID,
        *,
        archived: bool,
        search: str | None,
        offset: int,
        limit: int,
    ) -> list[Dress]:
        calls.append((offset, limit))
        return []

    async def _count(
        self: object,
        session: object,
        tenant_id: uuid.UUID,
        *,
        archived: bool,
        search: str | None,
    ) -> int:
        return 0

    monkeypatch.setattr(DressesRepository, "list_page", _list_page)
    monkeypatch.setattr(DressesRepository, "count", _count)
    return calls


async def test_limit_above_the_cap_is_clamped(paging_calls: list[tuple[int, int]]) -> None:
    view = await _service().list_dresses(TENANT_ID, offset=0, limit=1000)
    assert view.limit == STOREFRONT_LIST_MAX_LIMIT
    assert paging_calls == [(0, STOREFRONT_LIST_MAX_LIMIT)]


async def test_offset_above_the_ceiling_is_clamped(paging_calls: list[tuple[int, int]]) -> None:
    # Unbounded Python ints bind into OFFSET $n::BIGINT: without the ceiling this
    # is a 500 out of asyncpg's encoder, not a bounded page.
    view = await _service().list_dresses(TENANT_ID, offset=2**63, limit=10)
    assert view.offset == MAX_LIST_OFFSET
    assert paging_calls == [(MAX_LIST_OFFSET, 10)]


async def test_negative_paging_floors(paging_calls: list[tuple[int, int]]) -> None:
    view = await _service().list_dresses(TENANT_ID, offset=-5, limit=-1)
    assert (view.offset, view.limit) == (0, 1)
    assert paging_calls == [(0, 1)]


async def test_the_default_limit_survives_the_clamp(paging_calls: list[tuple[int, int]]) -> None:
    # A default above the cap would be silently clamped, so the page size the
    # grid is designed around would quietly stop being the page size shipped.
    assert STOREFRONT_LIST_DEFAULT_LIMIT <= STOREFRONT_LIST_MAX_LIMIT
    view = await _service().list_dresses(TENANT_ID)
    assert view.limit == STOREFRONT_LIST_DEFAULT_LIMIT
    assert paging_calls == [(0, STOREFRONT_LIST_DEFAULT_LIMIT)]


# --- the boutique wall clock ---


def _fixed(moment: datetime.datetime) -> Clock:
    return lambda: moment


def _clock(moment: str, zone: str) -> Clock:
    return _fixed(datetime.datetime.fromisoformat(moment).replace(tzinfo=ZoneInfo(zone)))


def test_utc_evening_is_already_tomorrow_in_summer_but_not_in_winter() -> None:
    # IDT is UTC+3, so 21:00 UTC is 00:00 the next day in Israel...
    assert today_jerusalem(_clock("2025-06-30T21:00", "UTC")) == datetime.date(2025, 7, 1)
    # ...while IST is UTC+2, so the same wall clock in January is still 23:00.
    # A fixed offset would get one of these two wrong.
    assert today_jerusalem(_clock("2025-01-15T21:00", "UTC")) == datetime.date(2025, 1, 15)


def test_the_date_flips_at_jerusalem_midnight() -> None:
    before = _clock("2025-06-30T23:30", "Asia/Jerusalem")
    after = _clock("2025-07-01T00:30", "Asia/Jerusalem")
    assert today_jerusalem(before) == datetime.date(2025, 6, 30)
    assert today_jerusalem(after) == datetime.date(2025, 7, 1)


def test_the_reading_machines_timezone_is_irrelevant() -> None:
    """One instant, three source zones, one Jerusalem date — CI, a laptop and
    the boutique are three different calendar days for part of every day."""
    instant = datetime.datetime(2025, 6, 30, 21, 0, tzinfo=datetime.UTC)
    for zone in ("UTC", "America/New_York", "Asia/Tokyo"):
        moved = _fixed(instant.astimezone(ZoneInfo(zone)))
        assert today_jerusalem(moved) == datetime.date(2025, 7, 1)


# --- upcoming exceptions: cutoff + cap ---


def _exception(day: datetime.date) -> AvailabilityException:
    return AvailabilityException(
        tenant_id=TENANT_ID, date=day, open_time=None, close_time=None, note=None
    )


def test_past_dates_are_dropped_and_today_is_kept() -> None:
    today = datetime.date(2025, 7, 1)
    rows = [_exception(today - datetime.timedelta(days=1)), _exception(today)]
    # Today's closure is the single most load-bearing row on /about — an
    # exclusive cutoff would hide "closed today" for the whole day it matters.
    assert [row.date for row in upcoming_exceptions(rows, today)] == [today]


def test_the_list_is_capped_and_keeps_the_earliest_dates() -> None:
    today = datetime.date(2025, 7, 1)
    # Date-ordered on the way in, matching the repository's ORDER BY date, so
    # "the first twelve" and "the twelve earliest" are the same claim.
    rows = [_exception(today + datetime.timedelta(days=n)) for n in range(30)]
    kept = upcoming_exceptions(rows, today)
    assert len(kept) == UPCOMING_EXCEPTIONS_LIMIT
    assert [row.date for row in kept] == [
        today + datetime.timedelta(days=n) for n in range(UPCOMING_EXCEPTIONS_LIMIT)
    ]


def test_the_cap_applies_after_the_cutoff_not_before() -> None:
    today = datetime.date(2025, 7, 1)
    past = [_exception(today - datetime.timedelta(days=n)) for n in range(20, 0, -1)]
    future = [_exception(today + datetime.timedelta(days=n)) for n in range(20)]
    kept = upcoming_exceptions(past + future, today)
    # Truncating first would return twelve dates that have already been and gone.
    assert len(kept) == UPCOMING_EXCEPTIONS_LIMIT
    assert all(row.date >= today for row in kept)


# --- instagram handle: the storefront builds instagram.com/{handle} verbatim ---


def test_valid_handles_pass() -> None:
    validate_instagram_handle("boutique.bella")
    validate_instagram_handle("bella_99")


def test_leading_at_and_path_separators_rejected() -> None:
    # Rejected, never stripped: one canonical stored form is what keeps the
    # storefront's link builder a pure join.
    for handle in ("@bella", "bella/x", "bella bridal", "bella?x=1"):
        with pytest.raises(BoutiqueValidationError):
            validate_instagram_handle(handle)


def test_handle_length_cap_is_instagrams_own() -> None:
    validate_instagram_handle("b" * MAX_PROFILE_INSTAGRAM_LENGTH)
    with pytest.raises(BoutiqueValidationError):
        validate_instagram_handle("b" * (MAX_PROFILE_INSTAGRAM_LENGTH + 1))


def test_the_empty_handle_is_not_a_valid_handle() -> None:
    with pytest.raises(BoutiqueValidationError):
        validate_instagram_handle("")


def test_but_an_empty_instagram_field_clears_the_profile() -> None:
    """The reconciliation between the two tests above: "" fails the pattern, yet
    `validate_profile` must accept it, because "" is the canonical CLEARED value
    on every profile field (exactly like phone) and the manage form seeds blanks
    to "" before submitting. Guarding with `if instagram:` rather than
    `is not None` is what keeps those two facts compatible."""
    validate_profile({"instagram": ""})
    validate_profile({"instagram": "", "phone": "", "essence": ""})
    with pytest.raises(BoutiqueValidationError):
        validate_profile({"instagram": "@bella"})
