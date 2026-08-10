from datetime import date, datetime
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
        # F38's three, each defaulted so ProvisioningService.provision — a
        # shipped file on the tenant-creation path — needs no edit to say what
        # the founding owner's absent phone and unset eligibility already are.
        phone: str | None = None,
        start_date: date | None = None,
        shift_manager_eligible: bool = False,
    ) -> StaffUser:
        staff = StaffUser(
            tenant_id=tenant_id,
            email=email,
            password_hash=password_hash,
            display_name=display_name,
            role=role,
            phone=phone,
            start_date=start_date,
            shift_manager_eligible=shift_manager_eligible,
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
        phone: str | None = None,
        start_date: date | None = None,
        shift_manager_eligible: bool | None = None,
    ) -> StaffUser | None:
        """Every argument omitted is a legal no-op, not an error: the service's
        no-op PATCH path calls straight through here, and an empty `.values()`
        would be a SQLAlchemy error rather than a 200.

        ⚠ `phone` carries ONE extra convention, and it is the same one the HTTP
        boundary already uses: `None` is "not sent", `""` is "clear it". On this
        signature `None` universally means "leave it alone", so without that
        second spelling a number could be set and changed but never REMOVED —
        and an emptied `<input>` posts `""` natively, so it costs no sentinel
        type and no tri-state anywhere in the stack.

        updated_at is never assigned — the DB trigger owns it, and `refresh` is
        what picks the trigger's value back up (the dresses/platform rule).
        """
        row = await self.by_id(session, tenant_id, staff_id)
        if row is None:
            return None
        if (
            display_name is None
            and role is None
            and password_hash is None
            and phone is None
            and start_date is None
            and shift_manager_eligible is None
        ):
            return row
        if display_name is not None:
            row.display_name = display_name
        if role is not None:
            row.role = role
        if password_hash is not None:
            row.password_hash = password_hash
        if phone is not None:
            row.phone = phone or None
        if start_date is not None:
            row.start_date = start_date
        if shift_manager_eligible is not None:
            row.shift_manager_eligible = shift_manager_eligible
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

    async def set_weekly_capacity_hours(
        self, session: AsyncSession, tenant_id: UUID, staff_id: UUID, *, hours: int | None
    ) -> StaffUser | None:
        """F42: her weekly capacity, or `None` to clear it back to the tenant
        default. Deliberately LAST-WRITE-WINS with an unconditional predicate —
        no version, no if-match, no 409 (D6): a manager setting a colleague's
        hours is making a staffing call that is hers, and a conflict dialog
        because another manager touched the same row four seconds ago is the
        platform second-guessing it.

        `None` back means ZERO ROWS — the live row vanished between the caller's
        `_require_seamstress` and this UPDATE. The caller maps that to the one
        404 this route has, and it is a race.

        ⚠ NO `updated_at = now()`. `update`'s docstring above is the house rule
        verbatim: the DB trigger owns it and the re-read is what picks the
        trigger's value back up. Neither shipped writer on this table assigns it.

        The answer comes through `_refreshed` and NOT off the returning row: the
        caller has already loaded this row (it must, for `_require_seamstress`
        and for the audit row's `from`), so this is ORM-enabled DML whose
        `evaluate` synchronization has stamped `hours` onto the identity-mapped
        instance whatever the database matched. `_refreshed`'s
        `populate_existing=True` is what makes the loser of two writes render the
        DATABASE's hours instead of its own.
        """
        wrote = await session.execute(
            update(StaffUser)
            .where(
                StaffUser.tenant_id == tenant_id,
                StaffUser.id == staff_id,
                StaffUser.deleted_at.is_(None),
            )
            .values(weekly_capacity_hours=hours)
            .returning(StaffUser.id)
        )
        if wrote.scalar_one_or_none() is None:
            return None
        return await self._refreshed(session, tenant_id, staff_id)

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

    async def set_pending_photo(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        staff_id: UUID,
        *,
        storage_key: str | None,
        content_type: str | None,
        at: datetime | None,
    ) -> bool:
        """Writes — or, with all three None, CLEARS — the pending triple.

        One method for both because they are the same statement with different
        values, and because the triple is all-or-nothing: three columns that must
        move together are one write, not three arguments a caller could get half
        right. The schema cannot express it (a CHECK spanning three would refuse
        the ordinary intermediate state a two-phase confirm creates), so this is
        where the invariant lives.

        Touches NEITHER the live triple nor `deleted_at`: an in-flight upload
        must leave the photo currently on the board rendering, which is the whole
        reason there are two triples.
        """
        wrote = await session.execute(
            update(StaffUser)
            .where(
                StaffUser.tenant_id == tenant_id,
                StaffUser.id == staff_id,
                StaffUser.deleted_at.is_(None),
            )
            .values(
                photo_pending_key=storage_key,
                photo_pending_content_type=content_type,
                photo_pending_at=at,
            )
            .returning(StaffUser.id)
        )
        return wrote.scalar_one_or_none() is not None

    async def promote_pending_photo(
        self, session: AsyncSession, tenant_id: UUID, staff_id: UUID, *, at: datetime
    ) -> StaffUser | None:
        """Pending becomes live, in ONE statement, guarded by
        `photo_pending_key IS NOT NULL`.

        That predicate is what makes a retried confirm — after a lost response —
        a no-op rather than a second promotion that would blank the live triple
        it already wrote. `None` back therefore means "nothing to promote", which
        the caller reads as idempotent success and not as an error.

        The answer comes through `_refreshed` and never off the returning row:
        this is ORM-enabled DML whose `evaluate` synchronization stamps these
        values onto the identity-mapped instance whatever the database matched,
        and the session factory is `expire_on_commit=False`.
        """
        wrote = await session.execute(
            update(StaffUser)
            .where(
                StaffUser.tenant_id == tenant_id,
                StaffUser.id == staff_id,
                StaffUser.deleted_at.is_(None),
                StaffUser.photo_pending_key.is_not(None),
            )
            .values(
                photo_key=StaffUser.photo_pending_key,
                photo_content_type=StaffUser.photo_pending_content_type,
                photo_confirmed_at=at,
                photo_pending_key=None,
                photo_pending_content_type=None,
                photo_pending_at=None,
            )
            .returning(StaffUser.id)
        )
        if wrote.scalar_one_or_none() is None:
            return None
        return await self._refreshed(session, tenant_id, staff_id)

    async def clear_photo(
        self, session: AsyncSession, tenant_id: UUID, staff_id: UUID
    ) -> StaffUser | None:
        """All six columns, one statement. Unconditional rather than guarded on
        `photo_key IS NOT NULL`, so a delete that races a confirm cannot leave
        the pending half behind."""
        wrote = await session.execute(
            update(StaffUser)
            .where(
                StaffUser.tenant_id == tenant_id,
                StaffUser.id == staff_id,
                StaffUser.deleted_at.is_(None),
            )
            .values(
                photo_key=None,
                photo_content_type=None,
                photo_confirmed_at=None,
                photo_pending_key=None,
                photo_pending_content_type=None,
                photo_pending_at=None,
            )
            .returning(StaffUser.id)
        )
        if wrote.scalar_one_or_none() is None:
            return None
        return await self._refreshed(session, tenant_id, staff_id)

    async def soft_delete(
        self, session: AsyncSession, tenant_id: UUID, staff_id: UUID, *, last_day: date
    ) -> bool:
        """Offboarding, as ONE statement.

        Returns whether a live row was hit — not the row, because DELETE answers
        OkResponse and the service already holds the row from its post-lock read.
        `deleted_at IS NULL` in the predicate is what makes a second call answer
        False rather than re-stamping the timestamp.

        ⚠ `last_day` is REQUIRED and has no default. That is the second half of
        the guard the service's `_resolve_last_day` is the first half of: the
        retention policy's predicate needs `last_day IS NOT NULL`, so a row
        soft-deleted without one is a person the platform can never scrub. A
        default here would make forgetting it silent.

        The six photo columns are nulled in the SAME statement as `deleted_at`,
        so there is no window in which a row is offboarded but still points at an
        object — and no second UPDATE that could fail on its own. The OBJECT is
        deleted by the caller, after the transaction, best-effort.
        """
        stmt = (
            update(StaffUser)
            .where(
                StaffUser.tenant_id == tenant_id,
                StaffUser.id == staff_id,
                StaffUser.deleted_at.is_(None),
            )
            .values(
                deleted_at=func.now(),
                last_day=last_day,
                photo_key=None,
                photo_content_type=None,
                photo_confirmed_at=None,
                photo_pending_key=None,
                photo_pending_content_type=None,
                photo_pending_at=None,
            )
            .returning(StaffUser.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None
