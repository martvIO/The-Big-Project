"""F22's entries model against real Postgres as the non-owner app role.

Everything here is a claim no fake can make: the active-unique partial index
(one ACTIVE entry per (tenant, phone, day, type) — refused by the DATABASE, not
by a pre-check), its per-tenant scoping under forced RLS, the FIFO order the
manage list publishes, and the guarded cancel's rowcount-0 idempotence.

⚠ db-marked: runs on CI only (no local Docker). Every test mints its own tenant
id — the container is session-scoped and nothing here truncates.
"""

import asyncio
import datetime
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.repositories.waitlist_entries import WaitlistEntriesRepository
from app.db.tenant import tenant_session
from app.models.constants import WaitlistEntryStatus

pytestmark = pytest.mark.db

REPO = WaitlistEntriesRepository()

DAY = datetime.date(2026, 8, 20)
PHONE = "+972501234567"


def _factory(app_role_url: str) -> tuple[Any, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _run(coro: Callable[[], Coroutine[Any, Any, None]]) -> None:
    asyncio.run(coro())


async def _insert(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    day: datetime.date = DAY,
    type_id: uuid.UUID | None = None,
    phone: str = PHONE,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await REPO.insert(
            session,
            tenant_id=tenant_id,
            day=day,
            appointment_type_id=type_id or uuid.uuid4(),
            phone=phone,
        )
        return row.id


def test_insert_round_trips_with_the_waiting_default(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    type_id = uuid.uuid4()

    async def check() -> None:
        try:
            entry_id = await _insert(factory, tenant_id, type_id=type_id)
            async with tenant_session(factory, tenant_id) as session:
                row = await REPO.by_id(session, tenant_id, entry_id)
                assert row is not None
                assert row.day == DAY
                assert row.appointment_type_id == type_id
                assert row.phone == PHONE
                # The DB default, never a client literal: F22 writes no status
                # on the insert at all.
                assert row.status == WaitlistEntryStatus.WAITING.value
                assert row.created_at is not None
        finally:
            await engine.dispose()

    _run(check)


def test_the_active_unique_index_refuses_the_exact_tuple(app_role_url: str) -> None:
    """D1's whole point, refused by the database. The second insert of one
    (tenant, phone, day, type) tuple raises — the SERVICE turns that into the
    idempotent re-read; this layer proves the race collapses to one row."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    type_id = uuid.uuid4()

    async def check() -> None:
        try:
            await _insert(factory, tenant_id, type_id=type_id)
            with pytest.raises(IntegrityError):
                await _insert(factory, tenant_id, type_id=type_id)
        finally:
            await engine.dispose()

    _run(check)


def test_the_active_unique_index_is_per_tenant(app_role_url: str) -> None:
    """The same (phone, day, type) under two tenants both insert: tenant_id
    leads the index columns, so one bride on two boutiques' waitlists is two
    rows, not a conflict."""
    engine, factory = _factory(app_role_url)
    type_id = uuid.uuid4()

    async def check() -> None:
        try:
            await _insert(factory, uuid.uuid4(), type_id=type_id)
            await _insert(factory, uuid.uuid4(), type_id=type_id)
        finally:
            await engine.dispose()

    _run(check)


def test_a_different_day_or_type_is_not_a_conflict(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    type_id = uuid.uuid4()

    async def check() -> None:
        try:
            await _insert(factory, tenant_id, type_id=type_id)
            await _insert(factory, tenant_id, type_id=type_id, day=DAY + datetime.timedelta(days=1))
            await _insert(factory, tenant_id, type_id=uuid.uuid4())
        finally:
            await engine.dispose()

    _run(check)


def test_a_cancelled_entry_frees_the_key(app_role_url: str) -> None:
    """The partial predicate's other half, and F33's first recorded objection
    answered: cancelled leaves the predicate, so the owner cancel (D5) really is
    the in-product remedy for a stuck key — she can rejoin the same day."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    type_id = uuid.uuid4()

    async def check() -> None:
        try:
            entry_id = await _insert(factory, tenant_id, type_id=type_id)
            async with tenant_session(factory, tenant_id) as session:
                cancelled = await REPO.cancel(session, tenant_id, entry_id)
                assert cancelled is not None
                assert cancelled.status == WaitlistEntryStatus.CANCELLED.value
            await _insert(factory, tenant_id, type_id=type_id)
        finally:
            await engine.dispose()

    _run(check)


def test_cancel_is_a_guarded_update_and_a_second_tap_moves_nothing(app_role_url: str) -> None:
    """`WHERE status = 'waiting'` — rowcount 0 on a cancelled row, so the
    service's double-tap answer is the row as-is rather than a second write."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            entry_id = await _insert(factory, tenant_id)
            async with tenant_session(factory, tenant_id) as session:
                assert await REPO.cancel(session, tenant_id, entry_id) is not None
            async with tenant_session(factory, tenant_id) as session:
                assert await REPO.cancel(session, tenant_id, entry_id) is None
                row = await REPO.by_id(session, tenant_id, entry_id)
                assert row is not None
                assert row.status == WaitlistEntryStatus.CANCELLED.value
        finally:
            await engine.dispose()

    _run(check)


def test_list_active_is_fifo_within_a_day_and_days_ascend(app_role_url: str) -> None:
    """(day, created_at) — the row order IS the position the manage table
    publishes (design §4: no position column, the top row is next)."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    later_day = DAY + datetime.timedelta(days=2)

    async def check() -> None:
        try:
            first = await _insert(factory, tenant_id, phone="+972501111111")
            second = await _insert(factory, tenant_id, phone="+972502222222")
            early_on_later_day = await _insert(factory, tenant_id, day=later_day)
            async with tenant_session(factory, tenant_id) as session:
                rows = await REPO.list_active(session, tenant_id, from_day=DAY)
                assert [row.id for row in rows] == [first, second, early_on_later_day]
                only_later = await REPO.list_active(session, tenant_id, day=later_day)
                assert [row.id for row in only_later] == [early_on_later_day]
        finally:
            await engine.dispose()

    _run(check)


def test_list_active_hides_cancelled_and_past_days(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()

    async def check() -> None:
        try:
            live = await _insert(factory, tenant_id, phone="+972501111111")
            cancelled = await _insert(factory, tenant_id, phone="+972502222222")
            await _insert(
                factory, tenant_id, phone="+972503333333", day=DAY - datetime.timedelta(days=7)
            )
            async with tenant_session(factory, tenant_id) as session:
                await REPO.cancel(session, tenant_id, cancelled)
            async with tenant_session(factory, tenant_id) as session:
                rows = await REPO.list_active(session, tenant_id, from_day=DAY)
                assert [row.id for row in rows] == [live]
        finally:
            await engine.dispose()

    _run(check)


def test_another_tenants_entries_are_invisible(app_role_url: str) -> None:
    """RLS plus the explicit predicate: B's list is empty of A's rows, and A's
    entry id answers None to B — the cross-tenant walker proves the HTTP face of
    this, the repository face lives here."""
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()

    async def check() -> None:
        try:
            entry_id = await _insert(factory, tenant_a)
            async with tenant_session(factory, tenant_b) as session:
                assert await REPO.by_id(session, tenant_b, entry_id) is None
                assert await REPO.list_active(session, tenant_b, from_day=DAY) == []
                assert await REPO.cancel(session, tenant_b, entry_id) is None
        finally:
            await engine.dispose()

    _run(check)
