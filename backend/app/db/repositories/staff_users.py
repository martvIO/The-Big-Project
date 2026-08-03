from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.constants import StaffRole
from app.models.staff_user import StaffUser


class StaffUsersRepository:
    """Tenant-scoped via RLS (the session's tenant context). The explicit
    tenant_id predicate is redundant defense-in-depth: it keeps the auth-critical
    reads correct even if a future RLS regression (a missing FORCE, a policy typo,
    an over-privileged role) slipped through."""

    async def by_email(
        self, session: AsyncSession, tenant_id: UUID, email: str
    ) -> StaffUser | None:
        stmt = select(StaffUser).where(
            StaffUser.tenant_id == tenant_id,
            StaffUser.email == email,
            StaffUser.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, staff_id: UUID
    ) -> StaffUser | None:
        stmt = select(StaffUser).where(
            StaffUser.tenant_id == tenant_id,
            StaffUser.id == staff_id,
            StaffUser.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_live(self, session: AsyncSession, tenant_id: UUID) -> list[StaffUser]:
        """created_at ASC, so the founding owner is first and the console's rows
        do not shuffle between page loads."""
        stmt = (
            select(StaffUser)
            .where(StaffUser.tenant_id == tenant_id, StaffUser.deleted_at.is_(None))
            .order_by(StaffUser.created_at)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def count_live_owners(self, session: AsyncSession, tenant_id: UUID) -> int:
        """The last-owner invariant's read. It is only correct under the caller's
        advisory lock — see app/auth/staff.py: a count taken outside the lock is a
        count another transaction has already invalidated.

        No index supports it and F51 adds none (spec D1): RLS narrows the scan to
        one tenant's single-digit staff rows.
        """
        stmt = select(func.count()).where(
            StaffUser.tenant_id == tenant_id,
            StaffUser.role == StaffRole.OWNER.value,
            StaffUser.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one()

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        email: str,
        password_hash: str,
        display_name: str,
        # A Python default rather than a required kwarg: making it required would
        # mean editing ProvisioningService.provision — a shipped file on the
        # tenant-creation path — to say what staff_users' server_default already
        # says. The one consequence is that the INSERT now emits role='owner'
        # explicitly instead of letting the default fill it.
        role: str = StaffRole.OWNER.value,
    ) -> StaffUser:
        staff = StaffUser(
            tenant_id=tenant_id,
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            role=role,
        )
        session.add(staff)
        await session.flush()
        await session.refresh(staff)
        return staff

    async def update(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        staff_id: UUID,
        *,
        display_name: str | None = None,
        role: str | None = None,
        password_hash: str | None = None,
    ) -> StaffUser | None:
        """Every argument omitted is a legal no-op, not an error: the service's
        no-op PATCH path calls straight through here, and an empty `.values()`
        would be a SQLAlchemy error rather than a 200.

        updated_at is never assigned — the DB trigger owns it, and `refresh` is
        what picks the trigger's value back up (the dresses/platform rule).
        """
        row = await self.by_id(session, tenant_id, staff_id)
        if row is None:
            return None
        if display_name is None and role is None and password_hash is None:
            return row
        if display_name is not None:
            row.display_name = display_name
        if role is not None:
            row.role = role
        if password_hash is not None:
            row.password_hash = password_hash
        await session.flush()
        await session.refresh(row)
        return row

    async def start_break(
        self, session: AsyncSession, tenant_id: UUID, staff_id: UUID, *, at: datetime
    ) -> tuple[bool, StaffUser | None]:
        """F57: she is stepping off the floor.

        Idempotent by predicate — `break_started_at IS NULL` means a second
        staffer's tap keeps the FIRST timestamp rather than moving it, which is
        what makes two managers pressing at once agree instead of the later one
        winning.

        The `bool` is read off the `.returning()` scalar and NOT off the row,
        because it cannot be read off the row. `update(StaffUser)` here is
        ORM-enabled DML whose default `evaluate` synchronization stamps
        `break_started_at = :at` onto the identity-mapped instance WHATEVER the
        database matched, and the session factory is built
        `expire_on_commit=False` (`db/session.py:66`), so a trailing `by_id`
        hands that poisoned object straight back. This repo has documented the
        trap three times and shipped the fix once — `bookings.py:473` (`cancel`,
        the governing precedent: the `.returning()` scalar is the ONLY honest
        "did I write?"), `bookings.py:300` (`check_in`, the same rule with two
        zero-row causes), `booking/owner.py:326-333` (capture BEFORE the write)
        and `test_booking_owner_db.py:747` (the race no fake can produce).

        Returns `(wrote, row)`, and NOT F34's four-member `CheckInOutcome`: that
        needed three values because zero rows there had two OPPOSITE causes
        (already checked in vs no longer confirmed). A break has no status
        guard, so zero rows with a live row back means the target state already
        holds, full stop. `(False, None)` is the only other answer and it means
        gone — soft-deleted, another tenant's, or never existed.

        No advisory lock. F51's namespaced one (`app/auth/staff.py`) exists
        because the last-owner invariant is "at least one", which no index and
        no single statement can express; this writes one column on one row and
        has no cross-row invariant to serialise. Taking it would serialise every
        break in the boutique against every staff edit.
        """
        wrote = await session.execute(
            update(StaffUser)
            .where(
                StaffUser.tenant_id == tenant_id,
                StaffUser.id == staff_id,
                StaffUser.break_started_at.is_(None),
                StaffUser.deleted_at.is_(None),
            )
            .values(break_started_at=at)
            .returning(StaffUser.id)
        )
        refreshed = await self._refreshed(session, tenant_id, staff_id)
        return wrote.scalar_one_or_none() is not None, refreshed

    async def end_break(
        self, session: AsyncSession, tenant_id: UUID, staff_id: UUID
    ) -> tuple[bool, StaffUser | None]:
        """She is back on the floor. `start_break`'s shape with the predicate
        inverted; every word of that docstring applies here too.

        Nothing schedules this (spec D7) — a break ends when somebody says so,
        because every automatic end would be a guess about a shift and there is
        no roster to guess from.
        """
        wrote = await session.execute(
            update(StaffUser)
            .where(
                StaffUser.tenant_id == tenant_id,
                StaffUser.id == staff_id,
                StaffUser.break_started_at.is_not(None),
                StaffUser.deleted_at.is_(None),
            )
            .values(break_started_at=None)
            .returning(StaffUser.id)
        )
        refreshed = await self._refreshed(session, tenant_id, staff_id)
        return wrote.scalar_one_or_none() is not None, refreshed

    async def _refreshed(
        self, session: AsyncSession, tenant_id: UUID, staff_id: UUID
    ) -> StaffUser | None:
        """The re-read that defeats the identity map — `bookings.py`'s
        `_refreshed` verbatim, for the same reason.

        `populate_existing=True` is the whole mechanism and it is not a spare
        keyword to drop: without it this SELECT returns the instance already in
        the identity map WITHOUT overwriting its attributes — i.e. the object
        the UPDATE just stamped — so the caller renders its own intent instead
        of the database's answer. Under READ COMMITTED it also sees a concurrent
        transaction's commit, which is what makes the LOSER of a start-racing-an-
        end render the WINNER's value.

        It is applied unconditionally rather than per call site: whether a caller
        happened to load the row first is exactly the reasoning that has bitten
        this repo three times, and the flag costs one chained method.
        """
        return (
            await session.execute(
                select(StaffUser)
                .where(
                    StaffUser.tenant_id == tenant_id,
                    StaffUser.id == staff_id,
                    StaffUser.deleted_at.is_(None),
                )
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    async def soft_delete(self, session: AsyncSession, tenant_id: UUID, staff_id: UUID) -> bool:
        """Returns whether a live row was hit — not the row, because DELETE
        answers OkResponse and the service already holds the row from its
        post-lock read. deleted_at IS NULL in the predicate is what makes a second
        call answer False rather than re-stamping the timestamp."""
        stmt = (
            update(StaffUser)
            .where(
                StaffUser.tenant_id == tenant_id,
                StaffUser.id == staff_id,
                StaffUser.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(StaffUser.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None
