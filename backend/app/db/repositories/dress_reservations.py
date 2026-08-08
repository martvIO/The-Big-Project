import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dress_reservation import DressReservation


class DressReservationsRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see DressesRepository).

    Every statement here filters `deleted_at IS NULL`. A soft-deleted reservation
    must free its window for BOTH the overlap check and the booking claim — that
    is the entire delete contract, and delete + re-add is the spec's substitute
    for an edit endpoint.
    """

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        dress_id: UUID,
        starts_on: datetime.date,
        ends_on: datetime.date,
        customer_id: UUID | None = None,
        notes: str | None = None,
    ) -> DressReservation:
        row = DressReservation(
            tenant_id=tenant_id,
            dress_id=dress_id,
            starts_on=starts_on,
            ends_on=ends_on,
            customer_id=customer_id,
            notes=notes,
        )
        session.add(row)
        await session.flush()
        return row

    async def overlapping(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        dress_id: UUID,
        *,
        starts_on: datetime.date,
        ends_on: datetime.date,
    ) -> list[DressReservation]:
        """The write-path conflict query: existing `[a1,a2]` conflicts with new
        `[b1,b2]` iff `a1 <= b2 AND b1 <= a2`.

        ⚠ BOTH COMPARISONS ARE NON-STRICT and that is the decision, not an
        oversight. `<` on either side would make a window ending on the 18th
        compatible with one starting the same day, i.e. one gown at two weddings.
        The adjacent case (ends 18 / starts 19) stays legal because the cleaning
        and return buffer is already inside `ends_on`.

        The caller must hold the tenant advisory lock — this SELECT is a read,
        and nothing in the schema stops two concurrent creates from both seeing
        an empty result.
        """
        stmt = (
            select(DressReservation)
            .where(
                DressReservation.tenant_id == tenant_id,
                DressReservation.dress_id == dress_id,
                DressReservation.deleted_at.is_(None),
                DressReservation.starts_on <= ends_on,
                DressReservation.ends_on >= starts_on,
            )
            .order_by(DressReservation.starts_on)
        )
        return list((await session.execute(stmt)).scalars())

    async def containing(
        self, session: AsyncSession, tenant_id: UUID, dress_id: UUID, day: datetime.date
    ) -> DressReservation | None:
        """The booking claim's one question: is this gown away on this day?

        ⚠ `day` MUST be a boutique-LOCAL date. The caller converts through
        BOUTIQUE_TIMEZONE; a UTC `.date()` is the previous day for every instant
        from 22:00 UTC onward, which is inside the boutique's evening.
        """
        stmt = select(DressReservation).where(
            DressReservation.tenant_id == tenant_id,
            DressReservation.dress_id == dress_id,
            DressReservation.deleted_at.is_(None),
            DressReservation.starts_on <= day,
            DressReservation.ends_on >= day,
        )
        return (await session.execute(stmt)).scalars().first()

    async def live_by_dress(
        self, session: AsyncSession, tenant_id: UUID, dress_id: UUID
    ) -> list[DressReservation]:
        """The manage pane's list: newest window first, past ones included — the
        owner deletes stale rows herself and hiding them would make the pane
        disagree with the overlap check she is fighting."""
        stmt = (
            select(DressReservation)
            .where(
                DressReservation.tenant_id == tenant_id,
                DressReservation.dress_id == dress_id,
                DressReservation.deleted_at.is_(None),
            )
            .order_by(DressReservation.starts_on.desc(), DressReservation.id)
        )
        return list((await session.execute(stmt)).scalars())

    async def current_or_future_by_dress(
        self, session: AsyncSession, tenant_id: UUID, dress_id: UUID, today: datetime.date
    ) -> list[DressReservation]:
        """The storefront projection (D6), ascending. `ends_on >= today` and not
        `> today`: a gown due back today is still away for the rest of it."""
        stmt = (
            select(DressReservation)
            .where(
                DressReservation.tenant_id == tenant_id,
                DressReservation.dress_id == dress_id,
                DressReservation.deleted_at.is_(None),
                DressReservation.ends_on >= today,
            )
            .order_by(DressReservation.starts_on, DressReservation.id)
        )
        return list((await session.execute(stmt)).scalars())

    async def soft_delete(
        self, session: AsyncSession, tenant_id: UUID, reservation_id: UUID
    ) -> bool:
        """False means no live row by that id — unknown, already deleted, or
        another tenant's. One indistinguishable miss, as everywhere else."""
        stmt = (
            update(DressReservation)
            .where(
                DressReservation.tenant_id == tenant_id,
                DressReservation.id == reservation_id,
                DressReservation.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(DressReservation.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None
