import datetime
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.roster import Roster
from app.models.roster_assignment import RosterAssignment
from app.models.shift_template import ShiftTemplate
from app.shifts.validation import current_week_start, jerusalem_moment


class RosterAssignmentsRepository:
    """Tenant-scoped via RLS; the explicit `tenant_id` predicate is redundant
    defense-in-depth (house pattern).

    Every READ filters `deleted_at IS NULL`. `changed_since` is the deliberate
    exception and says so in its own docstring — a removal is an edit, and a
    predicate that could not see soft-deleted rows would report an unchanged week
    after the owner took somebody off it.
    """

    async def by_roster(
        self, session: AsyncSession, tenant_id: UUID, roster_id: UUID
    ) -> list[RosterAssignment]:
        stmt = select(RosterAssignment).where(
            RosterAssignment.tenant_id == tenant_id,
            RosterAssignment.roster_id == roster_id,
            RosterAssignment.deleted_at.is_(None),
        )
        return list((await session.execute(stmt)).scalars().all())

    async def by_staff_and_roster(
        self, session: AsyncSession, tenant_id: UUID, *, roster_id: UUID, staff_user_id: UUID
    ) -> list[RosterAssignment]:
        """Her own shifts for one week — `MyWeekPanel`'s published block, which is
        open to every role and reads nobody else's rows."""
        stmt = select(RosterAssignment).where(
            RosterAssignment.tenant_id == tenant_id,
            RosterAssignment.roster_id == roster_id,
            RosterAssignment.staff_user_id == staff_user_id,
            RosterAssignment.deleted_at.is_(None),
        )
        return list((await session.execute(stmt)).scalars().all())

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, assignment_id: UUID
    ) -> RosterAssignment | None:
        stmt = select(RosterAssignment).where(
            RosterAssignment.tenant_id == tenant_id,
            RosterAssignment.id == assignment_id,
            RosterAssignment.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def live_for_triple(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        roster_id: UUID,
        shift_template_id: UUID,
        staff_user_id: UUID,
    ) -> RosterAssignment | None:
        """The UPSERT's read (design F-2). `idx_roster_assignments_unique` makes
        at most one row match, so `scalar_one_or_none` is a claim about the schema
        and not an assumption about the data."""
        stmt = select(RosterAssignment).where(
            RosterAssignment.tenant_id == tenant_id,
            RosterAssignment.roster_id == roster_id,
            RosterAssignment.shift_template_id == shift_template_id,
            RosterAssignment.staff_user_id == staff_user_id,
            RosterAssignment.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        roster_id: UUID,
        shift_template_id: UUID,
        staff_user_id: UUID,
        assigned_by: UUID,
        is_shift_manager: bool = False,
        override_of_state: str | None = None,
    ) -> RosterAssignment:
        row = RosterAssignment(
            tenant_id=tenant_id,
            roster_id=roster_id,
            shift_template_id=shift_template_id,
            staff_user_id=staff_user_id,
            assigned_by=assigned_by,
            is_shift_manager=is_shift_manager,
            override_of_state=override_of_state,
        )
        session.add(row)
        await session.flush()
        return row

    async def set_manager_flag(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        assignment_id: UUID,
        *,
        is_shift_manager: bool,
    ) -> RosterAssignment | None:
        """⚠ THE ONLY FIELD AN UPSERT ON A LIVE ROW MAY MOVE. `override_of_state`
        is stamped at assignment time and never updated (design F-5), so this
        statement names one column and touching a second here would erase the
        record of what the owner knowingly did.

        A second setter on one shift hits `idx_roster_assignments_manager_unique`
        and raises `IntegrityError`, which the service turns into
        `409 SHIFT_MANAGER_SLOT_TAKEN` — from the index, never from a read that
        raced.
        """
        stmt = (
            update(RosterAssignment)
            .where(
                RosterAssignment.tenant_id == tenant_id,
                RosterAssignment.id == assignment_id,
                RosterAssignment.deleted_at.is_(None),
            )
            .values(is_shift_manager=is_shift_manager)
            .returning(RosterAssignment.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.by_id(session, tenant_id, assignment_id)

    async def soft_delete(
        self, session: AsyncSession, tenant_id: UUID, assignment_id: UUID
    ) -> RosterAssignment | None:
        """Returns the row as it was BEFORE the delete, captured first.

        ⚠ THE READ COMES BEFORE THE WRITE, into a local, and that is not style.
        The UPDATE is ORM-enabled DML whose `evaluate` synchronisation stamps
        `deleted_at` onto the very instance a later read would return out of the
        same identity map — `end_break`'s recorded trap, and here it would make
        the audit row describe a removal of nothing.
        """
        before = await self.by_id(session, tenant_id, assignment_id)
        if before is None:
            return None
        stmt = (
            update(RosterAssignment)
            .where(
                RosterAssignment.tenant_id == tenant_id,
                RosterAssignment.id == assignment_id,
                RosterAssignment.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(RosterAssignment.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return before

    async def changed_since(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        roster_id: UUID,
        since: datetime.datetime,
    ) -> bool:
        """Has the assignment set moved since `since` (D7)?

        ⚠ ONE METHOD, TWO CALLERS, AND THAT IS THE POINT. `edited_since_publish`
        on the builder header and publish's own no-op predicate are the same
        question, and two implementations of it would be two answers — the pane
        saying «בוצעו שינויים מאז הפרסום» while publish refuses to write, or the
        reverse.

        ⚠ IT COUNTS SOFT-DELETED ROWS TOO, which is why there is no
        `deleted_at IS NULL` filter here. A REMOVAL IS AN EDIT: an owner who
        takes somebody off a published week and presses «פרסום מחדש» must get a
        stamp and an audit row, and a naive `MAX(created_at)` misses exactly that
        case. The soft delete is an UPDATE, so the trigger stamps `updated_at`
        and the second clause sees it.

        `updated_at > since` is NULL-safe in SQL — a row never updated yields
        NULL, which is not true — so the two clauses need no COALESCE.
        """
        stmt = (
            select(func.count())
            .select_from(RosterAssignment)
            .where(
                RosterAssignment.tenant_id == tenant_id,
                RosterAssignment.roster_id == roster_id,
                or_(
                    RosterAssignment.created_at > since,
                    RosterAssignment.updated_at > since,
                ),
            )
        )
        return bool((await session.execute(stmt)).scalar_one())

    async def on_shift_staff_ids(
        self, session: AsyncSession, tenant_id: UUID, at: datetime.datetime
    ) -> set[UUID]:
        """Who the PUBLISHED roster puts on shift at that instant — ONE statement.

        ⚠ THIS IS THE SEAM D15 SHIPS INSTEAD OF REWIRING F37 AND F42. Extending
        SOS's role route to prefer on-shift targets, or F42's `assignable` to
        read the roster, is a `SELECT` over this set plus one sentence on screen.
        Deliberately not built here, and the word «never» does not belong in that
        note.

        The join is `template_covers`' SQL twin and must stay its twin: the same
        half-open interval, the same day index, the same «published means the
        `rosters` row exists and carries a stamp». A DRAFT ROSTER RETURNS THE
        EMPTY SET, which is correct and is not the same fact as «nobody is
        rostered» — the caller distinguishes them by asking `RostersRepository`
        whether a published row exists at all (D5).
        """
        local_date, local_time, day_index = jerusalem_moment(at)
        week = current_week_start(local_date)
        stmt = (
            select(RosterAssignment.staff_user_id)
            .join(Roster, Roster.id == RosterAssignment.roster_id)
            .join(ShiftTemplate, ShiftTemplate.id == RosterAssignment.shift_template_id)
            .where(
                RosterAssignment.tenant_id == tenant_id,
                RosterAssignment.deleted_at.is_(None),
                Roster.tenant_id == tenant_id,
                Roster.deleted_at.is_(None),
                Roster.week_start == week,
                Roster.published_at.is_not(None),
                ShiftTemplate.tenant_id == tenant_id,
                ShiftTemplate.deleted_at.is_(None),
                ShiftTemplate.day_of_week == day_index,
                ShiftTemplate.starts_at_time <= local_time,
                ShiftTemplate.ends_at_time > local_time,
            )
        )
        return set((await session.execute(stmt)).scalars().all())
