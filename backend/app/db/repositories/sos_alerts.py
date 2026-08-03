import uuid
from datetime import datetime

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.constants import SosStatus
from app.models.fitting_room_assignment import FittingRoomAssignment
from app.models.sos_alert import SosAlert


class SosAlertsRepository:
    """Tenant-scoped via RLS; the explicit `tenant_id` predicate beside every
    `deleted_at IS NULL` is redundant defence-in-depth, which is the house
    pattern.

    ⚠ **Deleting every `tenant_id` predicate in this module leaves the whole db
    suite GREEN**, and that is recorded rather than pretended otherwise: forced
    RLS carries the isolation, so no test here proves the redundancy. It is
    proved by the isolation suite running as the non-owner app role, and a
    repository test asserting it would be asserting RLS.

    ⚠ **There is NO `violated_index()` here and no import of one.** F36's
    neighbouring module needs it because a partial unique index is its whole
    concurrency design; `sos_alerts` HAS NO UNIQUE INDEX (see 0021's DDL
    comment), so there is nothing to violate, no `IntegrityError` to recover
    from, and no `begin_nested()` savepoint to recover into. Copying that shape
    one file over would be cargo.

    F37's structural guarantee is `accept`'s `AND status = 'open'`: it constrains
    a TRANSITION rather than a population, which is exactly what "first-accept-
    owns, expressed structurally" means, and Postgres's row-level write lock on
    the UPDATE serialises the two contenders so the loser's predicate matches
    zero rows.
    """

    async def insert(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        raised_by: uuid.UUID,
        target_staff_user_id: uuid.UUID | None,
        fitting_room_assignment_id: uuid.UUID | None,
        note: str | None,
    ) -> SosAlert:
        """ONE plain statement. No lock, no savepoint, no ON CONFLICT.

        Duplicates are POSSIBLE and they are noise rather than corruption: two
        cards on an overlay, either of which resolves the emergency. What keeps
        them rare is the console's busy discipline disabling the control while
        the request is in flight — categorically smaller than F36's double-claim,
        which put two brides behind one curtain.

        `status` is left to the column default rather than passed, so the DDL is
        the single place «a new alert is open» is written down.
        """
        stmt = (
            insert(SosAlert)
            .values(
                tenant_id=tenant_id,
                raised_by=raised_by,
                target_staff_user_id=target_staff_user_id,
                fitting_room_assignment_id=fitting_room_assignment_id,
                note=note,
            )
            .returning(SosAlert)
        )
        return (await session.execute(stmt)).scalars().one()

    async def by_id(
        self, session: AsyncSession, tenant_id: uuid.UUID, alert_id: uuid.UUID
    ) -> SosAlert | None:
        """⚠ **`deleted_at IS NULL` only — NO `status` filter**, and that is
        `FittingRoomAssignmentsRepository.by_id`'s reason applied to a state
        machine instead of a timestamp.

        All four verbs authorize on the row's own columns, so each must read it
        before it can decide. Filtering `status = 'open'` here would make a
        LOSING accept read as ABSENT and answer 404 — instead of the 409 that
        NAMES THE OWNER, which is the one thing the ruling requires of it.
        """
        return await self._refreshed(session, tenant_id, alert_id)

    async def accept(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        alert_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        at: datetime,
    ) -> tuple[bool, SosAlert | None]:
        """The conditional UPDATE, and `AND status = 'open'` is the guarantee.

        `status`, `accepted_by` and `acknowledged_at` are set by ONE statement,
        so «accepted with nobody» and «open but owned» are both unrepresentable.
        The obvious two-step — stamp the owner, then flip the status —
        reintroduces the whole race this verb exists to close.

        `(True, row)` is the accept. `(False, row)` means somebody else got there
        first OR the alert is already closed, and the SERVICE discriminates on
        `row.status` — the only discriminator this feature has, because there is
        no index and therefore no constraint name. `(False, None)` is gone, and
        that is the 404.

        `at` is the service's injectable clock rather than SQL `now()`, so the db
        suite can freeze it and assert an equality — the shipped shape one module
        over (`FittingRoomAssignmentsRepository.release`).
        """
        wrote = await session.execute(
            update(SosAlert)
            .where(
                SosAlert.tenant_id == tenant_id,
                SosAlert.id == alert_id,
                SosAlert.status == SosStatus.OPEN,
                SosAlert.deleted_at.is_(None),
            )
            .values(status=SosStatus.ACCEPTED, accepted_by=actor_id, acknowledged_at=at)
            .returning(SosAlert.id)
        )
        refreshed = await self._refreshed(session, tenant_id, alert_id)
        return wrote.scalar_one_or_none() is not None, refreshed

    async def assignment_of(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        staff_user_id: uuid.UUID,
    ) -> FittingRoomAssignment | None:
        """The raise's room-pointer read, and it lives here rather than on the
        assignments repository because its predicate is F37's, not F36's.

        ⚠ **`staff_user_id = :actor` is NOT tidiness.** Without it any of the
        five roles could raise with any assignment id in her own tenant, and
        F36's floor payload hands `RoomAssignment.id` out on every occupied tile.
        The page would then render «דנה קוראת לעזרה — חדר 2» while Dana is
        standing in room 4. «No room» is a defined, safe state; «wrong room» is
        not, and in an emergency it is strictly worse — the responder walks to a
        closed curtain with a stranger's bride behind it.

        ⚠ **NO `released_at` filter.** She raises from the room she is standing
        in, the fitting can end between the tap and the write, and a page that
        loses its room because a colleague pressed «שוחרר» renders «no room» for
        no reason a human would accept.

        Unresolved is not an error: the caller stores NULL and carries on. A
        stale room pointer must never refuse a page.
        """
        stmt = select(FittingRoomAssignment).where(
            FittingRoomAssignment.tenant_id == tenant_id,
            FittingRoomAssignment.id == assignment_id,
            FittingRoomAssignment.staff_user_id == staff_user_id,
            FittingRoomAssignment.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def _refreshed(
        self, session: AsyncSession, tenant_id: uuid.UUID, alert_id: uuid.UUID
    ) -> SosAlert | None:
        """`FittingRoomAssignmentsRepository._refreshed` applied to this table,
        and applied UNCONDITIONALLY for the reason that docstring gives:
        "whether a caller happened to load the row first is exactly the reasoning
        that has bitten this repo three times."

        `populate_existing=True` is the whole mechanism. Without it this SELECT
        returns the instance already in the identity map WITHOUT overwriting its
        attributes — i.e. the object the UPDATE's `evaluate` synchronization just
        stamped in Python — so a LOSING accept would render its own `accepted_by`
        and **the 409 would name the wrong person**.

        ⚠ **Dropping the flag leaves `test_sos_repositories.py` GREEN except for
        one test**, and that is recorded rather than hidden: every other test
        here opens a fresh session per operation, so the identity map is empty
        and the flag is a no-op. The case that can see it is the forced
        interleave.

        No `status` filter here on purpose: the accept path needs the
        just-accepted row back to render it, and the losing path needs the
        winner's row to name her.
        """
        return (
            await session.execute(
                select(SosAlert)
                .where(
                    SosAlert.tenant_id == tenant_id,
                    SosAlert.id == alert_id,
                    SosAlert.deleted_at.is_(None),
                )
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
