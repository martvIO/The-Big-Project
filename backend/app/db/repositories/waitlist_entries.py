import datetime
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.constants import WaitlistEntryStatus
from app.models.waitlist_entry import WaitlistEntry

# The two states the active-unique index predicate names — "on the list" as far
# as the join's dedup and the manage list are concerned. Spelled once here so
# by_active_tuple and list_active cannot drift from each other, though the INDEX
# predicate is the one the database enforces.
_ACTIVE = (WaitlistEntryStatus.WAITING.value, WaitlistEntryStatus.OFFERED.value)


class WaitlistEntriesRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see CustomersRepository)."""

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        day: datetime.date,
        appointment_type_id: UUID,
        phone: str,
    ) -> WaitlistEntry:
        """`status` is left to its DB default — F22's join writes no transition,
        and `created_at` is the column default because it is the FIFO sort key:
        a caller-supplied one would let a client choose its own place in line.

        The active-unique index makes the duplicate tuple an IntegrityError; the
        SERVICE owns that branch (re-read, same 201) because the answer is a
        product decision, not a storage one.
        """
        row = WaitlistEntry(
            tenant_id=tenant_id,
            day=day,
            appointment_type_id=appointment_type_id,
            phone=phone,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def by_active_tuple(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        phone: str,
        day: datetime.date,
        appointment_type_id: UUID,
    ) -> WaitlistEntry | None:
        """The IntegrityError re-read: exactly the unique index's key and
        predicate, so the row that refused the INSERT is the row this answers."""
        stmt = select(WaitlistEntry).where(
            WaitlistEntry.tenant_id == tenant_id,
            WaitlistEntry.phone == phone,
            WaitlistEntry.day == day,
            WaitlistEntry.appointment_type_id == appointment_type_id,
            WaitlistEntry.status.in_(_ACTIVE),
            WaitlistEntry.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_active(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        day: datetime.date | None = None,
        from_day: datetime.date | None = None,
    ) -> Sequence[WaitlistEntry]:
        """The manage list: active entries, `(day, created_at)` — FIFO visible
        as row order, which IS the position (D5: computed nowhere, returned to
        no one). `day` filters one day; otherwise `from_day` floors the range
        (the service passes today, hiding dead past-day rows the retention
        sweep owns). `, id` breaks a created_at tie so two reads cannot
        transpose two rows."""
        stmt = select(WaitlistEntry).where(
            WaitlistEntry.tenant_id == tenant_id,
            WaitlistEntry.status.in_(_ACTIVE),
            WaitlistEntry.deleted_at.is_(None),
        )
        if day is not None:
            stmt = stmt.where(WaitlistEntry.day == day)
        elif from_day is not None:
            stmt = stmt.where(WaitlistEntry.day >= from_day)
        stmt = stmt.order_by(WaitlistEntry.day, WaitlistEntry.created_at, WaitlistEntry.id)
        return list((await session.execute(stmt)).scalars().all())

    async def cancel(
        self, session: AsyncSession, tenant_id: UUID, entry_id: UUID
    ) -> WaitlistEntry | None:
        """The guarded UPDATE — `WHERE status = 'waiting'` (F23 widens the guard
        for 'offered' when offers exist). Rowcount 0 has two causes the service
        tells apart with `by_id`: gone/foreign (404) and already-terminal (the
        idempotent double-tap, answered with the row as-is).

        `synchronize_session=False`: the WHERE is not Python-evaluable and no
        caller reads an identity-mapped instance afterwards — the entity is
        re-read fresh below. `updated_at` is the trigger's."""
        stmt = (
            update(WaitlistEntry)
            .where(
                WaitlistEntry.tenant_id == tenant_id,
                WaitlistEntry.id == entry_id,
                WaitlistEntry.status == WaitlistEntryStatus.WAITING.value,
                WaitlistEntry.deleted_at.is_(None),
            )
            .values(status=WaitlistEntryStatus.CANCELLED.value)
            .returning(WaitlistEntry.id)
            .execution_options(synchronize_session=False)
        )
        cancelled = (await session.execute(stmt)).scalar_one_or_none()
        if cancelled is None:
            return None
        return await self.by_id(session, tenant_id, cancelled)

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, entry_id: UUID
    ) -> WaitlistEntry | None:
        stmt = select(WaitlistEntry).where(
            WaitlistEntry.tenant_id == tenant_id,
            WaitlistEntry.id == entry_id,
            WaitlistEntry.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()
