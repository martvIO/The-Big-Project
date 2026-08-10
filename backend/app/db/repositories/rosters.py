import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.roster import Roster


class RostersRepository:
    """Tenant-scoped via RLS; the explicit `tenant_id` predicate is redundant
    defense-in-depth (house pattern).

    Every statement filters `deleted_at IS NULL`. One live roster per (tenant,
    week) is a partial unique index rather than a service read-then-write —
    `idx_rosters_week_unique`.
    """

    async def by_week(
        self, session: AsyncSession, tenant_id: UUID, week_start: datetime.date
    ) -> Roster | None:
        """`None` means NO ROSTER ROW AT ALL for that week, which is rule 3's
        input and is NOT the same as a row with `published_at IS NULL` (D5/D6).
        Every caller has to keep the two apart, so this returns the row and never
        a boolean."""
        stmt = select(Roster).where(
            Roster.tenant_id == tenant_id,
            Roster.week_start == week_start,
            Roster.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_id(self, session: AsyncSession, tenant_id: UUID, roster_id: UUID) -> Roster | None:
        stmt = select(Roster).where(
            Roster.tenant_id == tenant_id,
            Roster.id == roster_id,
            Roster.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def create(
        self, session: AsyncSession, *, tenant_id: UUID, week_start: datetime.date
    ) -> Roster:
        """A DRAFT — `published_at` and `published_by` are both NULL, which is the
        only state this table has besides published (D6).

        Created lazily by the FIRST assignment, in that write's own transaction,
        so an owner who opens the builder and closes it leaves no row behind.
        """
        row = Roster(tenant_id=tenant_id, week_start=week_start)
        session.add(row)
        await session.flush()
        return row

    async def stamp_published(
        self, session: AsyncSession, tenant_id: UUID, roster_id: UUID, *, by: UUID
    ) -> Roster | None:
        """Publish and republish are the SAME statement (D7): publishing is
        idempotent and a republish simply moves the stamp forward.

        ⚠ `func.now()`, NOT THE SERVICE CLOCK, AND THAT IS THE WHOLE POINT OF THE
        ARGUMENT NOT BEING THERE. `changed_since` compares this value against
        `created_at`/`updated_at`, which Postgres stamps — so a `published_at`
        taken from a DIFFERENT clock makes the no-op predicate a comparison
        between two clocks, and any skew between them either swallows a real edit
        or invents one. Both are the transaction timestamp of the connection that
        wrote them, so an assignment written before this publish is strictly
        earlier and one written after is strictly later, by construction.

        ⚠ THE CALLER DECIDES WHETHER TO CALL THIS AT ALL. A publish on a week
        whose assignment set has not moved since the stamp writes NOTHING and
        audits nothing — the shipped no-op rule — and that decision is made from
        `RosterAssignmentsRepository.changed_since`, not from here. A
        `RETURNING`-based «did anything change» would be a lie: the UPDATE
        matches the row whether or not the value moved.

        ⚠ BOTH COLUMNS, ALWAYS. `rosters_published_pair_check` refuses one
        without the other, so a writer that stamped only the instant would be a
        `psycopg` error rather than a half-published week.
        """
        stmt = (
            update(Roster)
            .where(
                Roster.tenant_id == tenant_id,
                Roster.id == roster_id,
                Roster.deleted_at.is_(None),
            )
            .values(published_at=func.now(), published_by=by)
            .returning(Roster.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        stmt_read = select(Roster).where(Roster.id == roster_id)
        return (await session.execute(stmt_read)).scalar_one_or_none()
