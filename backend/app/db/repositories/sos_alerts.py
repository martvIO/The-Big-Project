import dataclasses
import uuid
from datetime import datetime

from sqlalchemy import Select, and_, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.constants import SosStatus
from app.models.fitting_room import FittingRoom
from app.models.fitting_room_assignment import FittingRoomAssignment
from app.models.sos_alert import SosAlert
from app.models.staff_user import StaffUser

LIVE_STATUSES = (SosStatus.OPEN, SosStatus.ACCEPTED)


@dataclasses.dataclass(frozen=True)
class SosAlertRow:
    """One card: the alert, plus the four things its pointers resolve to.

    Frozen, and holding the ORM row rather than copying its columns out, so the
    read-time predicates keep operating on a `SosAlert` exactly as D6 spells them
    and there is no second transcription of twelve fields to drift.

    ⚠ **There is no customer datum here and there is no join that could produce
    one.** F36's floor payload carries a bride's name and is fetched only while
    the console is on the board or the floor; this one is fetched on every
    section, every few seconds, for the whole shift. The responder needs to know
    who is calling and which curtain — the person in the room is the colleague
    who raised it.
    """

    alert: SosAlert
    # Null ONLY when the staff row is gone entirely: the three staff joins carry
    # no `deleted_at` filter, so a colleague removed mid-page still has a name.
    raised_by_name: str | None
    # Null when the target is the shift-manager ROLE, and also when the named
    # staffer's row was swept — the card says «no name» either way, and the
    # column that would have told them apart is the one the reroute overwrites.
    target_name: str | None
    accepted_by_name: str | None
    # Null = no room on this page, which is ordinary.
    room_label: str | None


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

    async def live_for(
        self, session: AsyncSession, tenant_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> list[SosAlertRow]:
        """Every alert this caller may see, oldest first — D10's ONE statement.

        ⚠ **`actor_id=None` IS the elevated caller**, and she gets no extra
        predicate at all rather than a bound-in boolean: faster, and it keeps
        this module out of the business of knowing which roles are elevated.
        WHICH callers pass None is `ELEVATED_ROLES`' decision and lives in the
        service beside the rest of D7.

        Everybody else sees exactly the three alerts that are hers — the one she
        raised (so she sees the accept), the one she was named on, and the one she
        owns. That filter runs HERE, on the server, which is the whole reason an
        overlay fed by this read can be mounted app-wide on eleven sections.

        OLDEST first, and it is not a preference: the overlay and the centre both
        render this order, so the longest-waiting emergency is the one at the top
        and the cards do not shuffle between ticks.
        """
        stmt = self._joined(tenant_id).where(SosAlert.status.in_(LIVE_STATUSES))
        if actor_id is not None:
            stmt = stmt.where(
                or_(
                    SosAlert.raised_by == actor_id,
                    SosAlert.target_staff_user_id == actor_id,
                    SosAlert.accepted_by == actor_id,
                )
            )
        return await self._rows(session, stmt.order_by(SosAlert.created_at))

    async def view_of(
        self, session: AsyncSession, tenant_id: uuid.UUID, alert_id: uuid.UUID
    ) -> SosAlertRow | None:
        """ONE card, the same join — what every mutation answers.

        ⚠ **NO status filter and no audience clause**, which is `by_id`'s reason
        applied to the ANSWER rather than to the decision: a resolve answers the
        row it just closed, and the verb has already decided who may see it.
        """
        rows = await self._rows(session, self._joined(tenant_id).where(SosAlert.id == alert_id))
        return rows[0] if rows else None

    def _joined(self, tenant_id: uuid.UUID) -> Select[tuple[SosAlert, str, str, str, str]]:
        """The join chain, written ONCE.

        ⚠ The four name columns are typed `str` because that is what the COLUMN
        is; every one of them comes back NULL from an outer join whose right side
        is missing, and `SosAlertRow` is where that truth is declared.

        Two callers narrow this with a predicate and nothing else: a second
        transcription of five outer joins is five chances for one `deleted_at` to
        differ between the poll and the row a mutation answers with.

        There are no FK constraints in this schema, so every predicate is spelled
        out. Three of them are decisions with named tests:

        - **The three `staff_users` joins carry NO `deleted_at` filter.** A
          colleague removed mid-page still has a name, and an alert that cannot
          say who called is worse than one naming a departed colleague. It is also
          what makes the 409's `details`-less branch rare rather than routine.
        - **The assignment join carries no `released_at` filter** — the fitting
          can end while the page is open and the alert must still say where.
        - **The rooms join carries NO `deleted_at` filter**, F36's Risk 1(c)
          decided there and handed here verbatim: once the assignment is released
          the owner may soft-delete the room, and rendering a since-deleted
          label is deliberate and safe because **a room label is not personal
          data**.

        All five are LEFT, so an alert whose every pointer has been swept still
        renders — with null names, a null room and a card that says so. An alert
        that vanished because a pointer did would be a page silently dropped.
        """
        raiser = aliased(StaffUser)
        target = aliased(StaffUser)
        acceptor = aliased(StaffUser)
        return (
            select(
                SosAlert,
                raiser.display_name,
                target.display_name,
                acceptor.display_name,
                FittingRoom.label,
            )
            .select_from(SosAlert)
            .outerjoin(raiser, and_(raiser.tenant_id == tenant_id, raiser.id == SosAlert.raised_by))
            .outerjoin(
                target,
                and_(target.tenant_id == tenant_id, target.id == SosAlert.target_staff_user_id),
            )
            .outerjoin(
                acceptor,
                and_(acceptor.tenant_id == tenant_id, acceptor.id == SosAlert.accepted_by),
            )
            .outerjoin(
                FittingRoomAssignment,
                and_(
                    FittingRoomAssignment.tenant_id == tenant_id,
                    FittingRoomAssignment.id == SosAlert.fitting_room_assignment_id,
                    FittingRoomAssignment.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                FittingRoom,
                and_(
                    FittingRoom.tenant_id == tenant_id,
                    FittingRoom.id == FittingRoomAssignment.fitting_room_id,
                ),
            )
            .where(SosAlert.tenant_id == tenant_id, SosAlert.deleted_at.is_(None))
        )

    async def _rows(
        self,
        session: AsyncSession,
        stmt: Select[tuple[SosAlert, str, str, str, str]],
    ) -> list[SosAlertRow]:
        """`populate_existing=True` for `_refreshed`'s reason, and it matters most
        exactly here: this read runs AFTER the verb's own guarded UPDATE, whose
        `evaluate` synchronization may have stamped the caller's intent onto an
        identity-mapped instance the database never touched. Without the flag a
        card could render what this request wanted rather than what happened.
        """
        rows = (await session.execute(stmt.execution_options(populate_existing=True))).all()
        return [
            SosAlertRow(
                alert=row[0],
                raised_by_name=row[1],
                target_name=row[2],
                accepted_by_name=row[3],
                room_label=row[4],
            )
            for row in rows
        ]

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
