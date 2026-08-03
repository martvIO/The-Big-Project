import datetime
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.atelier.stages import STAGE_COLUMNS, later_columns
from app.models.alteration_ticket import AlterationTicket
from app.models.constants import StaffRole, TicketStage
from app.models.staff_user import StaffUser
from app.storefront.validation import BOUTIQUE_TIMEZONE

# One boutique week. The `delivered` column is a RECEIPT of the last week, not an
# archive: without a window a five-second poll ships a boutique's entire
# alteration history on every tick, forever. Its ceiling is stated rather than
# hidden — a ticket delivered eight days ago is invisible to the board and
# reachable only through F44's report, which is the correct trade for a live
# surface.
DELIVERED_WINDOW_DAYS = 7

# The window bounds the delivered column but NOT the undelivered one: a boutique
# that abandons the board accumulates `intake` rows without bound, and an
# unbounded five-second payload is the failure mode the client cannot recover
# from. 500 is far above any real workroom.
#
# ⚠ SERVER-ONLY. `truncated` is on the wire precisely so the console never has to
# know this number, and no client constant mirrors it.
BOARD_TICKET_LIMIT = 500


class AlterationTicketsRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see CustomersRepository).

    ⚠ EVERY WRITE HERE IS A CONDITIONAL UPDATE THAT CLASSIFIES OFF ITS
    `.returning()` SCALAR, and every one answers through `_refreshed`. Both
    halves matter and both fail independently — see `_refreshed`'s docstring for
    why the second one is not optional and why no single-writer test can prove
    it.

    The repository answers `(wrote, row)` and never an outcome: three of the five
    verbs have TWO OPPOSITE causes for zero rows (already there, or overtaken),
    and telling them apart needs `stage_of` and the caller's intent. That
    discrimination is the service's — one equality and one else — and putting it
    here would mean this layer raising HTTP-shaped errors.
    """

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        due_date: datetime.date,
        effort_minutes: int,
        at: datetime.datetime,
        assigned_staff_user_id: UUID | None = None,
        dress_id: UUID | None = None,
        dress_name: str | None = None,
        dress_size: str | None = None,
        notes: str | None = None,
    ) -> AlterationTicket:
        """`intake_at` is stamped BY THE INSERT from the injectable clock, never
        left to a column default: it is the first member of the state machine and
        every other stamp comes from the same clock, so reading one of the five
        off the database's clock and four off the application's would make the
        trail disagree with itself by the handler's own latency."""
        row = AlterationTicket(
            tenant_id=tenant_id,
            customer_id=customer_id,
            due_date=due_date,
            effort_minutes=effort_minutes,
            assigned_staff_user_id=assigned_staff_user_id,
            dress_id=dress_id,
            dress_name=dress_name,
            dress_size=dress_size,
            notes=notes,
            intake_at=at,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, ticket_id: UUID
    ) -> AlterationTicket | None:
        stmt = select(AlterationTicket).where(
            AlterationTicket.tenant_id == tenant_id,
            AlterationTicket.id == ticket_id,
            AlterationTicket.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def advance_stage(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        ticket_id: UUID,
        target: TicketStage,
        *,
        at: datetime.datetime,
    ) -> tuple[bool, AlterationTicket | None]:
        """Stamp `target`'s column, if and only if it and everything after it are
        still NULL.

        ⚠ `AND <every column after target> IS NULL` IS THE WHOLE CONCURRENCY
        MECHANISM AND IT DOES TWO JOBS. It refuses a BACKWARDS stamp — a stale
        board tapping `in_progress` on a ticket already at `ready`, where
        `in_progress_at IS NULL` is true and the write would otherwise succeed
        and leave a stamp later than the one after it — and it refuses the LOSER
        of a genuine race. Both are evaluated by the database in one predicate,
        which is the only place they can be: a pre-read another transaction can
        invalidate between the SELECT and the UPDATE is not a guard.

        No advisory lock. This writes one column on one row and its predicate
        expresses its entire invariant; taking a lock would serialise every stage
        advance in the boutique against every other. F51's namespaced lock exists
        because the last-owner invariant is "at least one", which no single
        statement can express — this is not that.

        ⚠ ZERO ROWS HAS TWO OPPOSITE CAUSES and this layer does not tell them
        apart. The caller re-reads and discriminates with ONE EQUALITY AND ONE
        ELSE: `stage_of(row) == target` is the caller's own repeat (200), and
        ANYTHING ELSE is a conflict (409) — including a stage strictly EARLIER
        than the target, which is reachable because a zero-row UPDATE takes no
        lock and this repo runs READ COMMITTED, so a concurrent undo can clear
        the column between the write and the re-read.
        """
        stmt = (
            update(AlterationTicket)
            .where(
                AlterationTicket.tenant_id == tenant_id,
                AlterationTicket.id == ticket_id,
                AlterationTicket.deleted_at.is_(None),
                getattr(AlterationTicket, STAGE_COLUMNS[target]).is_(None),
                *(getattr(AlterationTicket, column).is_(None) for column in later_columns(target)),
            )
            .values({STAGE_COLUMNS[target]: at})
            .returning(AlterationTicket.id)
        )
        wrote = await session.execute(stmt)
        refreshed = await self._refreshed(session, tenant_id, ticket_id)
        return wrote.scalar_one_or_none() is not None, refreshed

    async def undo_stage(
        self, session: AsyncSession, tenant_id: UUID, ticket_id: UUID, stage: TicketStage
    ) -> tuple[bool, AlterationTicket | None]:
        """Clear `stage`'s column, if and only if it is set and nothing after it
        is — `advance_stage`'s shape with the target's own clause inverted, and
        every word of that docstring applies here too.

        The client names the stage it INTENDS to clear, taken from what its last
        poll showed. That is what makes a stale board harmless: if the ticket
        moved on between the paint and the tap, the predicate fails and the
        caller gets a conflict rather than clearing a stage that arrived after it
        last looked.

        ⚠ THE TWO ZERO-ROW CAUSES ARE NOT DISJOINT, which is why the caller's
        discriminator is one equality and one else here too. "The column is
        already NULL" and "a later stamp exists" are BOTH true whenever a ticket
        was undone and then advanced past this stage — a forward skip D2 makes
        legal and normal — so a caller checking them in that order answers 200
        for a ticket that has moved on.
        """
        stmt = (
            update(AlterationTicket)
            .where(
                AlterationTicket.tenant_id == tenant_id,
                AlterationTicket.id == ticket_id,
                AlterationTicket.deleted_at.is_(None),
                getattr(AlterationTicket, STAGE_COLUMNS[stage]).is_not(None),
                *(getattr(AlterationTicket, column).is_(None) for column in later_columns(stage)),
            )
            .values({STAGE_COLUMNS[stage]: None})
            .returning(AlterationTicket.id)
        )
        wrote = await session.execute(stmt)
        refreshed = await self._refreshed(session, tenant_id, ticket_id)
        return wrote.scalar_one_or_none() is not None, refreshed

    async def claim(
        self, session: AsyncSession, tenant_id: UUID, ticket_id: UUID, *, staff_user_id: UUID
    ) -> tuple[bool, AlterationTicket | None]:
        """A seamstress takes an UNASSIGNED ticket. Two of them looking at the
        same card on two phones is the race, and `assigned_staff_user_id IS NULL`
        in the WHERE is the guard.

        The loser's returned row carries the WINNER's id, which is what lets the
        caller tell a double tap (200) from a colleague getting there first (409)
        with no second statement. "Anything else" includes a re-read showing
        NULL — a winner who claims and releases in the gap — which READ COMMITTED
        makes ordinary.
        """
        stmt = (
            update(AlterationTicket)
            .where(
                AlterationTicket.tenant_id == tenant_id,
                AlterationTicket.id == ticket_id,
                AlterationTicket.deleted_at.is_(None),
                AlterationTicket.assigned_staff_user_id.is_(None),
            )
            .values(assigned_staff_user_id=staff_user_id)
            .returning(AlterationTicket.id)
        )
        wrote = await session.execute(stmt)
        refreshed = await self._refreshed(session, tenant_id, ticket_id)
        return wrote.scalar_one_or_none() is not None, refreshed

    async def release(
        self, session: AsyncSession, tenant_id: UUID, ticket_id: UUID, *, staff_user_id: UUID
    ) -> tuple[bool, AlterationTicket | None]:
        """The mirror: `assigned_staff_user_id = :her`, so a seamstress can drop
        her own claim and can never drop anybody else's. In the predicate and not
        only in a pre-read, for the same reason as everything else here."""
        stmt = (
            update(AlterationTicket)
            .where(
                AlterationTicket.tenant_id == tenant_id,
                AlterationTicket.id == ticket_id,
                AlterationTicket.deleted_at.is_(None),
                AlterationTicket.assigned_staff_user_id == staff_user_id,
            )
            .values(assigned_staff_user_id=None)
            .returning(AlterationTicket.id)
        )
        wrote = await session.execute(stmt)
        refreshed = await self._refreshed(session, tenant_id, ticket_id)
        return wrote.scalar_one_or_none() is not None, refreshed

    async def assign(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        ticket_id: UUID,
        *,
        staff_user_id: UUID | None,
    ) -> tuple[bool, AlterationTicket | None]:
        """The elevated write: DELIBERATELY LAST-WRITE-WINS and it takes no
        conflict. A manager reassigning a garment is making a staffing decision
        with a person in front of her, and a conflict dialog because a colleague
        touched the same ticket four seconds ago is the platform second-guessing
        a call that is hers. The audit row carries `from` and `to`, so a
        reassignment war is legible after the fact.

        `None` is a value, not an omission — it unassigns. Unconditional is about
        the ASSIGNEE only: `deleted_at IS NULL` still applies, because a deleted
        ticket is gone to every verb.

        `_refreshed` changes WHICH row this renders, never who won.
        """
        stmt = (
            update(AlterationTicket)
            .where(
                AlterationTicket.tenant_id == tenant_id,
                AlterationTicket.id == ticket_id,
                AlterationTicket.deleted_at.is_(None),
            )
            .values(assigned_staff_user_id=staff_user_id)
            .returning(AlterationTicket.id)
        )
        wrote = await session.execute(stmt)
        refreshed = await self._refreshed(session, tenant_id, ticket_id)
        return wrote.scalar_one_or_none() is not None, refreshed

    async def update(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        ticket_id: UUID,
        *,
        due_date: datetime.date,
        effort_minutes: int,
        dress_id: UUID | None,
        dress_name: str | None,
        dress_size: str | None,
        notes: str | None,
    ) -> AlterationTicket | None:
        """A FULL REPLACE — every editable field on every call, no `None`-means-
        omitted convention anywhere in the signature. The request model is what
        makes "omitted" impossible; here `None` means "clear it", which is the
        only reading that lets a seamstress delete a note.

        Not editable, deliberately: the CUSTOMER (a ticket opened for the wrong
        bride is a delete and a re-open, not an edit that silently re-points a
        garment at someone else) and the five STAMPS (a stage moves by its own
        verb, under its own predicate).

        `None` means no live row by that id.
        """
        stmt = (
            update(AlterationTicket)
            .where(
                AlterationTicket.tenant_id == tenant_id,
                AlterationTicket.id == ticket_id,
                AlterationTicket.deleted_at.is_(None),
            )
            .values(
                due_date=due_date,
                effort_minutes=effort_minutes,
                dress_id=dress_id,
                dress_name=dress_name,
                dress_size=dress_size,
                notes=notes,
            )
            .returning(AlterationTicket.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self._refreshed(session, tenant_id, ticket_id)

    async def soft_delete(self, session: AsyncSession, tenant_id: UUID, ticket_id: UUID) -> bool:
        """Returns whether a live row was hit — not the row, because delete
        answers an ok body and the caller already holds the row it audited.
        `deleted_at IS NULL` in the predicate is what makes a second call answer
        False rather than re-stamping the timestamp, so a double-tapped delete
        cannot move the retention clock F20 reads off this column."""
        stmt = (
            update(AlterationTicket)
            .where(
                AlterationTicket.tenant_id == tenant_id,
                AlterationTicket.id == ticket_id,
                AlterationTicket.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(AlterationTicket.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def board(
        self, session: AsyncSession, tenant_id: UUID, *, today: datetime.date
    ) -> tuple[list[AlterationTicket], bool]:
        """The board's tickets and whether the ceiling bit.

        Every live ticket not yet delivered, PLUS every ticket delivered on or
        after `today - DELIVERED_WINDOW_DAYS`. The cutoff is midnight in
        JERUSALEM of that day, computed in Python: `due_date` is a calendar day
        and the window is counted in them, and Jerusalem arithmetic lives in
        Python by rule (`storefront/validation.py`) so it is testable against an
        injectable clock instead of the database's.

        ⚠ ORDERING IS `due_date, created_at, id` AND THE `id` IS NOT DECORATION.
        `created_at` defaults to `now()`, which in Postgres is TRANSACTION START
        TIME and is therefore identical for every row inserted in one
        transaction — so two tickets opened in one intake share it exactly. With
        `ORDER BY due_date, created_at` alone Postgres may return them in either
        order across plans, and the console's cards shuffle between ticks for no
        reason a user can see. `CustomersRepository.search` states the same
        failure for OFFSET paging; `StaffUsersRepository.list_live`'s
        single-column order is NOT a precedent for a unique tiebreak.

        `truncated` is derived by asking for ONE ROW MORE than the limit rather
        than by a second COUNT statement — the poll's statement budget is three,
        and a count over an unbounded table is the thing the limit exists to
        avoid. Ordering by `due_date` ASC means a truncated payload drops the
        LEAST urgent tickets, which is the only truncation that is defensible.
        """
        cutoff = datetime.datetime.combine(
            today - datetime.timedelta(days=DELIVERED_WINDOW_DAYS),
            datetime.time.min,
            tzinfo=BOUTIQUE_TIMEZONE,
        )
        stmt = (
            select(AlterationTicket)
            .where(
                AlterationTicket.tenant_id == tenant_id,
                AlterationTicket.deleted_at.is_(None),
                or_(
                    AlterationTicket.delivered_at.is_(None),
                    AlterationTicket.delivered_at >= cutoff,
                ),
            )
            .order_by(
                AlterationTicket.due_date,
                AlterationTicket.created_at,
                AlterationTicket.id,
            )
            .limit(BOARD_TICKET_LIMIT + 1)
        )
        rows = list((await session.execute(stmt)).scalars().all())
        return rows[:BOARD_TICKET_LIMIT], len(rows) > BOARD_TICKET_LIMIT

    async def assignees(self, session: AsyncSession, tenant_id: UUID) -> list[StaffUser]:
        """The board's `seamstresses[]` — A UNION, NOT A FILTER (D9/D12).

        Every LIVE staff row holding `role = 'seamstress'`, PLUS every distinct
        assignee on a live undelivered ticket **whatever that person's role or
        deleted_at now is**. The role check runs ONCE, at assign time, and two
        shipped writers break it the moment they run: `StaffUsersRepository`'s
        `update` sets the role unconditionally and its `soft_delete` retires her.
        A filter would make those tickets' assignee vanish from the payload —
        producing exactly the invisible bucket the assign-time check exists to
        prevent — so the union keeps her on the wire and the console's «תופרת
        שאינה פעילה» branch is data-driven instead of inferred from absence.

        ⚠ THIS IS THE ONE READ IN THE FEATURE THAT DELIBERATELY RETURNS
        SOFT-DELETED ROWS, and only through the second leg. `assignable` is not a
        column: the caller derives it from the row (live AND still a seamstress),
        which is a pure function and needs no extra type.

        The second leg is scoped to live UNDELIVERED tickets, so a retired
        staffer whose only ticket went out last week drops off — the same
        unbounded-growth failure the delivered window closes for tickets.

        One statement with a subquery, not two: the poll's budget is three
        business statements and this is the third.
        """
        assigned = (
            select(AlterationTicket.assigned_staff_user_id)
            .where(
                AlterationTicket.tenant_id == tenant_id,
                AlterationTicket.deleted_at.is_(None),
                AlterationTicket.delivered_at.is_(None),
                AlterationTicket.assigned_staff_user_id.is_not(None),
            )
            .distinct()
        )
        stmt = (
            select(StaffUser)
            .where(
                StaffUser.tenant_id == tenant_id,
                or_(
                    StaffUser.id.in_(assigned),
                    (StaffUser.deleted_at.is_(None))
                    & (StaffUser.role == StaffRole.SEAMSTRESS.value),
                ),
            )
            .order_by(StaffUser.display_name, StaffUser.id)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def _refreshed(
        self, session: AsyncSession, tenant_id: UUID, ticket_id: UUID
    ) -> AlterationTicket | None:
        """The re-read that defeats the identity map — `StaffUsersRepository`'s
        `_refreshed` verbatim, for the same reason.

        `populate_existing=True` is the whole mechanism and it is not a spare
        keyword to drop: without it this SELECT returns the instance already in
        the identity map WITHOUT overwriting its attributes — i.e. the object the
        UPDATE just stamped — so the caller renders its own INTENT instead of the
        database's answer. Under READ COMMITTED it also sees a concurrent
        transaction's commit, which is what makes the LOSER of a race render the
        WINNER's row.

        `update(AlterationTicket)` is ORM-enabled DML whose default `evaluate`
        synchronization stamps the SET value onto the identity-mapped instance
        WHATEVER the database matched, and the session factory is built
        `expire_on_commit=False`. Every write in this feature has the shape that
        poisons, because every one of them loads the row first — for the audit
        row's `from`, or to authorize a seamstress against
        `assigned_staff_user_id`.

        It is applied UNCONDITIONALLY on every write path rather than per call
        site: whether a caller happened to load the row first is exactly the
        reasoning that has bitten this repo three times, and the flag costs one
        chained method.

        ⚠ NO SINGLE-WRITER TEST CAN PROVE THIS. Deleting the flag leaves every
        `wrote` assertion green and only the rendered row wrong, and the case
        that shows it cleanly — the loser of a race rendering the winner's row —
        needs two interleaved transactions. The race suite owns that half.
        """
        return (
            await session.execute(
                select(AlterationTicket)
                .where(
                    AlterationTicket.tenant_id == tenant_id,
                    AlterationTicket.id == ticket_id,
                    AlterationTicket.deleted_at.is_(None),
                )
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
