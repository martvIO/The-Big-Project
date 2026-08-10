import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.staff_availability import StaffAvailability


class StaffAvailabilityRepository:
    """Tenant-scoped via RLS; the explicit `tenant_id` predicate is redundant
    defense-in-depth (house pattern).

    Every statement filters `deleted_at IS NULL`, and that is the WHOLE contract
    of D8: the absence of a live row IS "not answered", so a soft delete returns
    the pair to unanswered by the same predicate every reader already uses.
    """

    async def live_for_week(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        week_start: datetime.date,
        staff_user_id: UUID | None = None,
    ) -> list[StaffAvailability]:
        """One week. With `staff_user_id` it is her own panel; without it, the
        roster-readiness read for every staffer at once — one statement, which is
        what `idx_staff_availability_week` is ordered for."""
        stmt = select(StaffAvailability).where(
            StaffAvailability.tenant_id == tenant_id,
            StaffAvailability.week_start == week_start,
            StaffAvailability.deleted_at.is_(None),
        )
        if staff_user_id is not None:
            stmt = stmt.where(StaffAvailability.staff_user_id == staff_user_id)
        return list((await session.execute(stmt)).scalars().all())

    async def set_state(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        staff_user_id: UUID,
        shift_template_id: UUID,
        week_start: datetime.date,
        state: str,
        recorded_by: UUID | None,
    ) -> None:
        """One (staffer, shift, week) pair, written unconditionally.

        ⚠ THE CALLER DECIDES WHAT CHANGED, NOT THIS METHOD. The service has
        already read the week's live rows to build D11's diff, so it knows an
        unchanged pair without asking — and it simply does not call this for one.
        A `RETURNING`-based «did anything change» here would be a lie anyway: the
        UPDATE matches the row whether or not the value moved. That pre-read is
        what makes «a save that changes nothing writes no audit row» (D11)
        provable rather than hopeful.

        ⚠ `UPDATE … RETURNING` FIRST, `INSERT` ON ZERO ROWS, AND THE CALLER
        RETRIES THE WHOLE THING ONCE ON `IntegrityError`
        (`_insert_next_terms_version`'s shipped optimistic shape). There is NO
        advisory lock: the tenant-wide key the booking claim and F28 take is far
        too coarse for a per-tap write, and `idx_staff_availability_unique` is a
        structural guarantee where that lock would only be a serialisation.

        ⚠ `recorded_by` IS ALWAYS WRITTEN, INCLUDING THE `None` THAT CLEARS IT.
        A staffer correcting a row an elevated actor recorded for her must end up
        with `recorded_by IS NULL` — her screen renders «נרשם על ידי…» off this
        column, and leaving a stale id there would make it say somebody else gave
        an answer she just gave herself.
        """
        stmt = (
            update(StaffAvailability)
            .where(
                StaffAvailability.tenant_id == tenant_id,
                StaffAvailability.staff_user_id == staff_user_id,
                StaffAvailability.shift_template_id == shift_template_id,
                StaffAvailability.week_start == week_start,
                StaffAvailability.deleted_at.is_(None),
            )
            .values(state=state, recorded_by=recorded_by)
            .returning(StaffAvailability.id)
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is not None:
            return
        session.add(
            StaffAvailability(
                tenant_id=tenant_id,
                staff_user_id=staff_user_id,
                shift_template_id=shift_template_id,
                week_start=week_start,
                state=state,
                recorded_by=recorded_by,
            )
        )
        await session.flush()

    async def soft_delete_pairs(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        staff_user_id: UUID,
        week_start: datetime.date,
        template_ids: list[UUID],
    ) -> int:
        """D11's other half: live rows for that (staffer, week) whose template is
        NOT in the request are cleared. The caller passes the EXPLICIT ids to
        clear, computed from the same pre-read that builds the diff — never a
        `NOT IN` over the request, which is an empty predicate for an empty
        request in SQL and a silent full sweep in several ORMs."""
        if not template_ids:
            return 0
        stmt = (
            update(StaffAvailability)
            .where(
                StaffAvailability.tenant_id == tenant_id,
                StaffAvailability.staff_user_id == staff_user_id,
                StaffAvailability.week_start == week_start,
                StaffAvailability.shift_template_id.in_(template_ids),
                StaffAvailability.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(StaffAvailability.id)
        )
        return len((await session.execute(stmt)).scalars().all())

    async def soft_delete_future_by_template(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        template_id: UUID,
        *,
        after_week: datetime.date,
    ) -> int:
        """D4's invalidation, in the caller's transaction. Returns the count the
        confirm dialog predicted and the audit row records.

        ⚠ STRICTLY `> after_week`. The current and past weeks are HISTORY — F40
        may already have published off them — so a material edit reaches forward
        only, and the owner's typo fix cannot rewrite what a roster was built on.
        """
        stmt = (
            update(StaffAvailability)
            .where(
                StaffAvailability.tenant_id == tenant_id,
                StaffAvailability.shift_template_id == template_id,
                StaffAvailability.week_start > after_week,
                StaffAvailability.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(StaffAvailability.id)
        )
        return len((await session.execute(stmt)).scalars().all())

    async def future_counts_by_template(
        self, session: AsyncSession, tenant_id: UUID, *, after_week: datetime.date
    ) -> dict[UUID, int]:
        """The number D4 binds the confirm dialog to state BEFORE she commits
        (design F-2/§5.1). ONE grouped aggregate over the same predicate
        `soft_delete_future_by_template` uses, so the prediction and the write
        cannot disagree about which rows they mean — and it rides the templates
        read the elevated pane already makes, so nothing new is fetched and no
        read path writes."""
        stmt = (
            select(StaffAvailability.shift_template_id, func.count())
            .where(
                StaffAvailability.tenant_id == tenant_id,
                StaffAvailability.week_start > after_week,
                StaffAvailability.deleted_at.is_(None),
            )
            .group_by(StaffAvailability.shift_template_id)
        )
        return {template_id: int(count) for template_id, count in (await session.execute(stmt))}
