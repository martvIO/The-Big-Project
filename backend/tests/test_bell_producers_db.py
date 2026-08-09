"""F35's producers against real Postgres: the notification commits WITH its
event, or with nothing.

`test_bell_service.py` proves the four guards with fakes. It cannot prove the one
property the whole delivery design rests on — that the insert rides the
producer's transaction — because a monkeypatched repository never reaches one.
This module proves exactly that, and the CHECK the DDL puts under `kind`.

⚠ **THE HARNESS'S RULES ARE `test_queue_dispatch_db.py`'s**, and rule 1 is the
one that bites: every row this module COMMITS holds `owner`, never a floor role,
because `migrated_db` is session-scoped and `test_migrations.py` re-adds 0011's
two-value CHECK over whatever rows exist. Nothing here asserts anything about a
role. Every test mints its own tenant id; nothing truncates.
"""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.service import StaffContext
from app.db.repositories.fitting_room_assignments import FittingRoomAssignmentsRepository
from app.db.repositories.fitting_rooms import FittingRoomsRepository
from app.db.repositories.queue_tickets import QueueTicketsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.floor.service import FloorService
from app.floor.validation import RoomOccupiedError
from app.models.audit_log import AuditLog
from app.models.constants import AuditAction, StaffNotificationKind, StaffRole, VisitType
from app.models.fitting_room import FittingRoom
from app.models.staff_notification import StaffNotification

pytestmark = pytest.mark.db

# 09:12Z on 2026-08-03 is 12:12 Asia/Jerusalem — same calendar day, which is what
# makes `_today()`'s Jerusalem binding assertable against a frozen clock.
NOW = datetime(2026, 8, 3, 9, 12, tzinfo=UTC)
TODAY = date(2026, 8, 3)

ROOMS = FittingRoomsRepository()
ASSIGNMENTS = FittingRoomAssignmentsRepository()
TICKETS = QueueTicketsRepository()


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
    )


def _actor(tenant_id: uuid.UUID, staff_id: uuid.UUID) -> StaffContext:
    """Always OWNER — hard rule 1."""
    return StaffContext(
        id=staff_id,
        tenant_id=tenant_id,
        email="owner@bella.example",
        display_name="Owner",
        role=StaffRole.OWNER.value,
    )


async def _seed_staff(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, *, display_name: str = "Staff"
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=f"bell-prod-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name=display_name,
            role=StaffRole.OWNER.value,
        )
        return staff.id


async def _notifications(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> list[StaffNotification]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(StaffNotification).where(StaffNotification.tenant_id == tenant_id)
        return list((await session.execute(stmt)).scalars().all())


async def _dispatch_audit(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> list[AuditLog]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(AuditLog).where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.action == AuditAction.QUEUE_TICKET_DISPATCHED.value,
        )
        return list((await session.execute(stmt)).scalars().all())


async def test_a_dispatch_commits_its_notification_with_its_audit_row(app_role_url: str) -> None:
    """The positive half, and it is not decoration: the rollback assertion below
    is only meaningful against a path that demonstrably writes."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room_id = (await _seed_room(factory, tenant_id)).id
        manager = await _seed_staff(factory, tenant_id, display_name="Manager")
        target = await _seed_staff(factory, tenant_id, display_name="Dana")
        await _seed_ticket(factory, tenant_id)

        await FloorService(factory, clock=lambda: NOW).take_next(
            tenant_id, room_id, staff_user_id=target, actor=_actor(tenant_id, manager)
        )

        rows = await _notifications(factory, tenant_id)
        assert len(rows) == 1
        assert rows[0].staff_user_id == target
        assert rows[0].actor_staff_user_id == manager
        assert rows[0].kind == StaffNotificationKind.DISPATCH_ASSIGNED.value
        assert rows[0].read_at is None
        assert len(await _dispatch_audit(factory, tenant_id)) == 1
    finally:
        await engine.dispose()


async def test_a_take_next_that_loses_the_room_writes_no_notification(app_role_url: str) -> None:
    """⚠ **The headline, and the reason the insert is INSIDE the `async with`.**

    A committed occupant makes the assignment INSERT raise `IntegrityError`,
    which propagates out of `tenant_session` and ROLLS THE WHOLE TRANSACTION
    BACK. Zero notification rows alongside zero audit rows is the assertion —
    the bell must never claim a dispatch the customer never got, and a
    notification written in a transaction of its own would survive exactly this.

    ⚠ Mutation: move the insert below the `except IntegrityError` handler, or
    give it its own `tenant_session`, and this reds with one orphan row while
    `test_bell_service.py` stays entirely green.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        room = await _seed_room(factory, tenant_id)
        manager = await _seed_staff(factory, tenant_id, display_name="Manager")
        target = await _seed_staff(factory, tenant_id, display_name="Dana")
        occupant = await _seed_staff(factory, tenant_id, display_name="Rotem")
        await _seed_ticket(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            await ASSIGNMENTS.claim(
                session, tenant_id, room_id=room.id, staff_id=occupant, booking_id=None
            )

        with pytest.raises(RoomOccupiedError):
            await FloorService(factory, clock=lambda: NOW).take_next(
                tenant_id, room.id, staff_user_id=target, actor=_actor(tenant_id, manager)
            )

        assert await _notifications(factory, tenant_id) == []
        assert await _dispatch_audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def test_the_check_refuses_a_fourth_kind(app_role_url: str) -> None:
    """The three values are pinned by the DATABASE, so a fourth arrives through a
    migration and therefore a review — never through a typo in a producer."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        with pytest.raises(DBAPIError) as refused:
            async with tenant_session(factory, tenant_id) as session:
                await session.execute(
                    text(
                        "INSERT INTO staff_notifications "
                        "(tenant_id, staff_user_id, actor_staff_user_id, kind, entity_id) "
                        "VALUES (:t, :s, :a, 'help_is_coming', :e)"
                    ),
                    {
                        "t": str(tenant_id),
                        "s": str(staff_id),
                        "a": str(staff_id),
                        "e": str(uuid.uuid4()),
                    },
                )
        assert "staff_notifications_kind_check" in str(refused.value)
        assert await _notifications(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def _seed_room(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> FittingRoom:
    async with tenant_session(factory, tenant_id) as session:
        return await ROOMS.insert(session, tenant_id, label="חדר 1", sort_order=0)


async def _seed_ticket(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> None:
    async with tenant_session(factory, tenant_id) as session:
        await TICKETS.insert(
            session,
            tenant_id=tenant_id,
            queue_day=TODAY,
            name="נועה בר",
            phone=f"+9725{uuid.uuid4().int % 10**8:08d}",
            visit_type=VisitType.BRIDE.value,
        )
