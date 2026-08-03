import datetime
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import ColumnElement, Row, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.constants import QueueTicketStatus
from app.models.queue_ticket import QueueTicket


def _live_waiting(tenant_id: UUID, queue_day: datetime.date) -> tuple[ColumnElement[bool], ...]:
    """The queue, defined once: this boutique, this day, still waiting, not
    deleted.

    Both readers bind these four and they are ONE expression rather than two
    copies for a reason that is about a customer rather than about tidiness.
    `position` answers a woman's own phone and `board` answers the screen on the
    wall she is standing in front of; index `i` of the board equals `position ==
    i + 1` only while both range over an identical set. Two copies that drift —
    F58 widening one status filter, say — put a different number on the wall
    from the one on her phone, and nothing about that failure looks like a bug
    until a customer says so.

    The two readers still bind `queue_day` DIFFERENTLY, deliberately, and that
    is the caller's argument to make: `position` binds the ticket's own day so
    someone who walked out yesterday is not told she is next; `board` binds
    today so a ticket nobody closed overnight does not sit at position 1 on a
    wall forever.
    """
    return (
        QueueTicket.tenant_id == tenant_id,
        QueueTicket.queue_day == queue_day,
        QueueTicket.status == QueueTicketStatus.WAITING.value,
        QueueTicket.deleted_at.is_(None),
    )


def _sort_key() -> ColumnElement[datetime.datetime]:
    """The queue's published order, also defined once. F33 shipped the COALESCE
    before anything wrote `requeued_at` because the ordering is the contract,
    not the column: F58's skip has to be a one-column write rather than a
    renumbering pass."""
    return func.coalesce(QueueTicket.requeued_at, QueueTicket.created_at)


# A BOUND, not a page size — F36's picker reasoning: "more than any boutique
# has", so `truncated` is the honesty for the one case it bites, a griefing
# flood inside F33's 200/hour tenant ceiling. The panel does not paginate and is
# not on a second poll, so there is nothing here for a page size to mean.
WAITLIST_LIMIT = 100

# The skip that removes. Named rather than spelled `2` inline because the `CASE`
# reads the PRE-update count, so the literal is easy to misread as "she has been
# skipped twice already" when it means "this is her second skip".
SKIP_LIMIT = 2


class QueueTicketsRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see CustomersRepository).

    There is no `active_today` and no dedup lookup: the create always creates, so
    nothing in the REQUEST path ever consults the number a caller submitted.

    ⚠ **F58 makes the old form of that sentence false and this is its
    correction.** It promised "no read keyed on `phone` … that absence is the
    security property", and D9's duplicate flag groups today's waiting arrivals
    by exactly that column. The property that was actually load-bearing survives
    and is what this class still guarantees: **no read on an anonymous,
    unauthenticated surface is keyed on `phone`, and no response body anywhere
    carries it.** The oracle Ruling 3 closed was a public one; a signed-in
    staffer of this tenant grouping today's own arrivals is a different surface
    with a different threat model, and saying so beats leaving a false comment
    standing as the rationale.

    ⚠ **EVERY ORM-enabled UPDATE below carries
    `.execution_options(synchronize_session=False)`** — all six. SQLAlchemy 2.0's
    default is `'auto'` (`'evaluate'`, falling back to `'fetch'`); none of these
    WHERE clauses is Python-evaluable, `skip`'s `skip_count + 1` and its `CASE`
    least of all, and no caller reads an identity-mapped instance afterwards.

    ⚠ **Every statement in this class is a COLUMN PROJECTION except `by_id`**, so
    no `QueueTicket` instance is constructed on any F58 path at all. The class of
    bug F36 and F57 each shipped once — ORM-enabled DML stamping a SET value onto
    an identity-mapped instance a later line then reads — is therefore
    structurally unreachable here rather than defended against.
    """

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        queue_day: datetime.date,
        name: str,
        phone: str,
        visit_type: str,
        marketing_opt_in_at: datetime.datetime | None = None,
    ) -> QueueTicket:
        """`status` and `skip_count` are left to their DB defaults — F33 writes
        no transition and F58 owns every one of them. `created_at` is the
        column default too: it is the sort key, and a caller-supplied one would
        let a client choose its own place in the queue."""
        row = QueueTicket(
            tenant_id=tenant_id,
            queue_day=queue_day,
            name=name,
            phone=phone,
            visit_type=visit_type,
            marketing_opt_in_at=marketing_opt_in_at,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def claim_next(
        self, session: AsyncSession, tenant_id: UUID, *, day: datetime.date
    ) -> Row[tuple[UUID, str, str, datetime.datetime | None]] | None:
        """Take the head of today's queue and move it to `in_service`, in ONE
        statement. `None` means nobody is waiting, and it writes nothing.

        ⚠ **`FOR UPDATE` on the SUBQUERY is what makes two managers get two
        different customers; `SKIP LOCKED` is what makes the loser NOT WAIT.**
        They are different properties and each has its own test. The inner plan
        is `Limit → LockRows → Sort → Scan`, with LockRows BELOW the Limit: with
        plain `FOR UPDATE` the loser blocks on the row lock, and when the winner
        commits, LockRows runs an EvalPlanQual re-check against the updated
        tuple, the `status = 'waiting'` qual now fails, the row is discarded and
        LockRows pulls the NEXT row from the sort and locks that one. So the row
        lock plus the `status` qual is what makes one woman unreachable twice;
        `SKIP LOCKED` only stops a take-next waiting behind an unrelated
        transaction that happens to hold a queue row (a call or a skip does too).

        ⚠ **SKIP LOCKED can therefore serve OUT OF ORDER**, and that is accepted
        rather than overlooked: if the winner rolls back (D3a) the loser has
        already taken the next ticket, and the head is served after her. The
        window is one statement long, and the alternative it buys is two managers
        walking two brides to the same curtain with one ticket between them.

        The two OUTER conjuncts are **redundant by construction** — the
        subquery's `FOR UPDATE` holds the row for the whole transaction, so
        nothing can change between the two statements. They are there for the
        reader: every other predicate in this feature leads with `tenant_id`, and
        this is the one statement in the product that moves a named customer into
        a fitting room. It is the statement someone will study, and the one that
        silently loses its tenant scoping if `tenant_session` is ever refactored.

        The predicates and the sort key are `_live_waiting()` and `_sort_key()`
        CALLED, never re-spelled — `_live_waiting`'s own docstring names "F58
        widening one status filter, say" as the hazard it exists to prevent.

        A COLUMN PROJECTION and not the entity, for `board`'s reason and one
        more: an ORM-enabled UPDATE plus `select(QueueTicket)` would put a
        `QueueTicket` carrying a phone and a consent timestamp into the identity
        map at exactly the moment `_refreshed`'s docstring says this repo has
        been bitten three times.

        `synchronize_session=False` because this WHERE cannot be evaluated in
        Python (a locking scalar subquery least of all) and no caller reads an
        identity-mapped instance afterwards. `updated_at` is not in the SET list
        — the shipped trigger owns it.
        """
        head = (
            select(QueueTicket.id)
            .where(*_live_waiting(tenant_id, day))
            .order_by(_sort_key().asc(), QueueTicket.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
            .scalar_subquery()
        )
        stmt = (
            update(QueueTicket)
            .where(
                QueueTicket.tenant_id == tenant_id,
                QueueTicket.status == QueueTicketStatus.WAITING.value,
                QueueTicket.id == head,
            )
            .values(status=QueueTicketStatus.IN_SERVICE.value)
            .returning(
                QueueTicket.id,
                QueueTicket.name,
                QueueTicket.visit_type,
                QueueTicket.called_at,
            )
            .execution_options(synchronize_session=False)
        )
        return (await session.execute(stmt)).one_or_none()

    async def claim_by_id(
        self, session: AsyncSession, tenant_id: UUID, ticket_id: UUID
    ) -> Row[tuple[UUID, str, str, datetime.datetime | None]] | None:
        """Push-assign's half of D3: the same move to `in_service`, against a
        ticket the manager NAMED rather than the head of the queue.

        `None` is rowcount 0 and it has exactly TWO causes — gone (or another
        tenant's, or swept) and not `waiting` — which this statement cannot tell
        apart. The service's `status_of` read is where they are, and it is the
        only place they are.

        No `FOR UPDATE` and no `SKIP LOCKED`: there is no queue to walk and no
        head to pick, so the conditional UPDATE's own row lock plus its `status`
        qual is the whole of the serialisation. Two managers assigning one ticket
        to two rooms serialise here and the loser's EvalPlanQual re-check fails
        on the updated tuple.
        """
        stmt = (
            update(QueueTicket)
            .where(
                QueueTicket.tenant_id == tenant_id,
                QueueTicket.id == ticket_id,
                QueueTicket.status == QueueTicketStatus.WAITING.value,
                QueueTicket.deleted_at.is_(None),
            )
            .values(status=QueueTicketStatus.IN_SERVICE.value)
            .returning(
                QueueTicket.id,
                QueueTicket.name,
                QueueTicket.visit_type,
                QueueTicket.called_at,
            )
            .execution_options(synchronize_session=False)
        )
        return (await session.execute(stmt)).one_or_none()

    async def close(self, session: AsyncSession, tenant_id: UUID, ticket_id: UUID) -> bool:
        """FINISH — and it is a statement on the RELEASE's existing transaction,
        never a route of its own (D5). The worker frees and the entry closes
        together, or neither does.

        ⚠ **`AND status = 'in_service'`**: a ticket a manager REMOVED while the
        fitting was running is `removed`, and freeing the room must not resurrect
        her as `done`. `False` here is not an error and raises nothing — the room
        is free, which is what the staffer asked for.
        """
        stmt = (
            update(QueueTicket)
            .where(
                QueueTicket.tenant_id == tenant_id,
                QueueTicket.id == ticket_id,
                QueueTicket.status == QueueTicketStatus.IN_SERVICE.value,
                QueueTicket.deleted_at.is_(None),
            )
            .values(status=QueueTicketStatus.DONE.value)
            .returning(QueueTicket.id)
            .execution_options(synchronize_session=False)
        )
        return (await session.execute(stmt)).one_or_none() is not None

    async def skip(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        ticket_id: UUID,
        *,
        now: datetime.datetime,
        seen_skip_count: int,
    ) -> Row[tuple[UUID, int, str]] | None:
        """Skip-to-back, and the second skip removes — ONE statement, because
        every part of it has to be evaluated against one row version.

        ⚠ **`AND skip_count = :seen_skip_count` IS NOT BOOKKEEPING. Without it
        two ordinary single taps REMOVE a customer with the confirm bypassed.**
        Two managers see the same no-show at `skip_count == 0` and both tap
        «דלגי». A takes the row lock, writes 1, stays `waiting`, commits. B was
        blocked; on A's commit READ COMMITTED's EvalPlanQual re-evaluates B's
        predicate against the NEW tuple, `status = 'waiting'` still holds, and
        B's SET expressions read the new row: 1 → 2, and the `CASE` fires
        `'removed'`. She is gone, irreversibly, and NEITHER client ever rendered
        the confirm, because the confirm is gated on `skip_count >= 1` and both
        read 0 from the same tick. With the conjunct B's rowcount is 0 and the
        service answers 409 `QUEUE_TICKET_CHANGED`.

        ⚠ **The `CASE` reads the PRE-update `skip_count`**, because every SET
        expression in one UPDATE is evaluated against the old row. `skip_count +
        1 >= SKIP_LIMIT` therefore means "this is her second skip".

        ⚠ **`skip_count + 1` is the ATOMIC increment**, never a Python
        read-modify-write: the conjunct refuses a caller whose count is stale,
        and this is what keeps the DELIBERATE second skip from losing one.

        ⚠ **`called_at = NULL`.** She was called and did not come — that is why
        she is being skipped. Leaving the stamp would highlight her on F59's
        public wall board at the BACK of the queue and leave her own page reading
        «אפשר לגשת לדלפק» indefinitely. It also makes the summons re-issuable.

        `requeued_at` is the whole skip-to-back, one column rather than a
        renumbering pass, because `position()` orders on
        `COALESCE(requeued_at, created_at)` — F33 shipped that COALESCE before
        anything wrote the column precisely so this feature could not change a
        published read's semantics by adding one.
        """
        stmt = (
            update(QueueTicket)
            .where(
                QueueTicket.tenant_id == tenant_id,
                QueueTicket.id == ticket_id,
                QueueTicket.status == QueueTicketStatus.WAITING.value,
                QueueTicket.deleted_at.is_(None),
                QueueTicket.skip_count == seen_skip_count,
            )
            .values(
                requeued_at=now,
                called_at=None,
                skip_count=QueueTicket.skip_count + 1,
                status=case(
                    (
                        QueueTicket.skip_count + 1 >= SKIP_LIMIT,
                        QueueTicketStatus.REMOVED.value,
                    ),
                    else_=QueueTicketStatus.WAITING.value,
                ),
            )
            .returning(QueueTicket.id, QueueTicket.skip_count, QueueTicket.status)
            .execution_options(synchronize_session=False)
        )
        return (await session.execute(stmt)).one_or_none()

    async def call(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        ticket_id: UUID,
        *,
        now: datetime.datetime,
    ) -> Row[tuple[UUID, datetime.datetime | None]] | None:
        """The summons. `status` IS NOT TOUCHED, and F59's spec records that its
        board breaks if it is: the board's predicate is `status == 'waiting'`,
        byte-identical to `position()`'s, so flipping the status at call time
        drops the called row off the wall board the instant it is called — the
        opposite of the feature. That is the one contract F59 could not enforce
        for itself.

        `called_at IS NULL` makes a second call keep the FIRST timestamp instead
        of moving it — `release()`'s shipped idempotence, one table over. It also
        gives this verb's rowcount 0 a THIRD cause, and it is the ordinary one: a
        re-call is a 200 with no audit row, not an error.
        """
        stmt = (
            update(QueueTicket)
            .where(
                QueueTicket.tenant_id == tenant_id,
                QueueTicket.id == ticket_id,
                QueueTicket.status == QueueTicketStatus.WAITING.value,
                QueueTicket.deleted_at.is_(None),
                QueueTicket.called_at.is_(None),
            )
            .values(called_at=now)
            .returning(QueueTicket.id, QueueTicket.called_at)
            .execution_options(synchronize_session=False)
        )
        return (await session.execute(stmt)).one_or_none()

    async def remove(self, session: AsyncSession, tenant_id: UUID, ticket_id: UUID) -> bool:
        """The no-show and the duplicate, which are the same act (D8). No undo
        and no restore verb — the confirm in front of it and the audit row behind
        it are what the design carries instead.

        Its rowcount 0 really does have only D4's two causes: no `skip_count`
        conjunct, no `called_at` conjunct.
        """
        stmt = (
            update(QueueTicket)
            .where(
                QueueTicket.tenant_id == tenant_id,
                QueueTicket.id == ticket_id,
                QueueTicket.status == QueueTicketStatus.WAITING.value,
                QueueTicket.deleted_at.is_(None),
            )
            .values(status=QueueTicketStatus.REMOVED.value)
            .returning(QueueTicket.id)
            .execution_options(synchronize_session=False)
        )
        return (await session.execute(stmt)).one_or_none() is not None

    async def status_of(
        self, session: AsyncSession, tenant_id: UUID, ticket_id: UUID
    ) -> tuple[str, int] | None:
        """The refusal read, and it is a PROJECTION rather than `by_id` for a
        reason that is NOT the answer — the two return the same facts.

        `by_id` is a `select(QueueTicket)` ENTITY read. Issued here it would pull
        a normalised Israeli mobile and a consent timestamp into the same session
        as an ORM-enabled UPDATE, and put a `QueueTicket` in the identity map at
        exactly the moment `FittingRoomAssignmentsRepository._refreshed`'s
        docstring says this repo has been bitten three times. `(status,
        skip_count)` is everything all three refusal tables need.
        """
        stmt = select(QueueTicket.status, QueueTicket.skip_count).where(
            QueueTicket.tenant_id == tenant_id,
            QueueTicket.id == ticket_id,
            QueueTicket.deleted_at.is_(None),
        )
        row = (await session.execute(stmt)).one_or_none()
        return (row.status, row.skip_count) if row is not None else None

    async def waiting_for_panel(
        self, session: AsyncSession, tenant_id: UUID, day: datetime.date, *, limit: int
    ) -> Sequence[
        Row[tuple[UUID, str, str, datetime.datetime, datetime.datetime | None, int, str]]
    ]:
        """The console's waitlist: today's waiting rows in queue order, capped.

        The predicates and the sort key are `_live_waiting()` and `_sort_key()`
        CALLED, never re-spelled — `_live_waiting`'s own docstring names "F58
        widening one status filter, say" as the hazard it exists to prevent, and
        the panel's `position` is `index + 1` over THIS order.

        A COLUMN PROJECTION, never `select(QueueTicket)`: the entity pulls a
        phone and a consent timestamp for every waiting woman into the process
        twelve times a minute, forever, for a view that renders six fields.

        ⚠ **`phone` IS selected and NEVER serialised.** It is here for D9's
        duplicate grouping and for nothing else; the service computes a boolean
        from it and the wire shape has no phone field to carry it.

        ⚠ **`created_at` is the panel's `arrived_at`, and the sort key is not.**
        Two facts, two columns: `arrived_at` is when she walked in and never
        moves; `COALESCE(requeued_at, created_at)` is what a skip moves. Sending
        the sort key would reset the rendered clock to zero on every skip and the
        panel would say «הגיעה זה עתה» about a woman who has been standing there
        forty minutes.

        `, id ASC` breaks a tie so two ticks cannot transpose two rows.
        `position()` has no second key and cannot agree on a tie; that residual
        is F59's, recorded and pinned rather than papered over.
        """
        stmt = (
            select(
                QueueTicket.id,
                QueueTicket.name,
                QueueTicket.visit_type,
                QueueTicket.created_at,
                QueueTicket.called_at,
                QueueTicket.skip_count,
                QueueTicket.phone,
            )
            .where(*_live_waiting(tenant_id, day))
            .order_by(_sort_key().asc(), QueueTicket.id.asc())
            .limit(limit)
        )
        return (await session.execute(stmt)).all()

    async def in_service_phones(
        self, session: AsyncSession, tenant_id: UUID, day: datetime.date
    ) -> set[str]:
        """D9's second statement, and it is D9's alone.

        ⚠ **`_live_waiting` CANNOT be reused here** — its third predicate is
        `status == 'waiting'` and the whole point of this read is the rows that
        are not. Without it the duplicate flag is blind to precisely the case the
        remedy exists for: she re-scanned, was dispatched on the first ticket,
        and the second is still waiting with nothing marking it.

        A PHONE-ONLY projection: no name, no id, nothing that could be rendered
        by accident.
        """
        stmt = select(QueueTicket.phone).where(
            QueueTicket.tenant_id == tenant_id,
            QueueTicket.queue_day == day,
            QueueTicket.status == QueueTicketStatus.IN_SERVICE.value,
            QueueTicket.deleted_at.is_(None),
        )
        return set((await session.execute(stmt)).scalars().all())

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, ticket_id: UUID
    ) -> QueueTicket | None:
        stmt = select(QueueTicket).where(
            QueueTicket.tenant_id == tenant_id,
            QueueTicket.id == ticket_id,
            QueueTicket.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def position(
        self, session: AsyncSession, tenant_id: UUID, ticket: QueueTicket
    ) -> int | None:
        """1-based place among the WAITING tickets of THIS ticket's own queue
        day, ordered by COALESCE(requeued_at, created_at). `None` unless the
        ticket is itself waiting.

        The day comes from `ticket.queue_day` and NEVER from a clock. Bound to
        today, a ticket left waiting from an earlier day — the normal state of
        things until F58 can close one — counts zero earlier sort keys and
        renders 1, telling someone who walked out yesterday that she is next.
        The read has the row in hand, so this costs nothing.

        Counted on read and never stored: a stored position must be renumbered
        on every insert and removal, and two concurrent renumberings produce
        duplicate or skipped positions a customer sees on two different phones.
        `(tenant_id, queue_day)` is exactly the index prefix, so this is one
        range scan over a handful of rows.
        """
        if ticket.status != QueueTicketStatus.WAITING.value:
            return None
        mine = ticket.requeued_at or ticket.created_at
        stmt = select(func.count()).where(
            *_live_waiting(tenant_id, ticket.queue_day),
            _sort_key() < mine,
        )
        return (await session.execute(stmt)).scalar_one() + 1

    async def board(
        self, session: AsyncSession, tenant_id: UUID, queue_day: datetime.date, *, limit: int
    ) -> tuple[Sequence[Row[tuple[str, datetime.datetime | None]]], int]:
        """The public wall board: today's waiting rows in queue order, capped,
        plus the untruncated count.

        A COLUMN PROJECTION, never `select(QueueTicket)`. Selecting the entity
        would pull five normalised Israeli mobiles and five consent timestamps
        into the process on every poll, twelve times a minute, forever, for a
        view that renders a first name and one boolean. Nothing would leak — the
        schema narrows — but minimisation does not only belong on the wire, and
        the projection is what makes this class's promise true in the stronger
        sense: on this path the phone never enters the process at all.

        The predicates and the sort key are `position`'s, shared rather than
        copied — see `_live_waiting`. `queue_day` is TODAY here and the ticket's
        own day there; the caller passes it and `_live_waiting` explains why the
        two differ.

        `, id ASC` breaks a tie on the sort key. Not to agree with `position` on
        one — it cannot, the count has no second key — but because without it a
        tie makes the row order non-deterministic across polls, which on a wall
        screen is two names swapping every five seconds.

        Two statements, not one. A window function would return five copies of
        one integer and would still have nothing to return when the board is
        empty; `len(rows)` is capped at `limit`, so an overflow line built on it
        would say zero forever, silently, on a wall.

        ⚠ The count counts TICKETS, not women. There is no uniqueness on this
        table beyond the primary key, so one woman who re-scanned the QR is two
        rows and counts twice. The board cannot deduplicate and must not try:
        the only key that would identify her is `phone`.
        """
        predicates = _live_waiting(tenant_id, queue_day)
        rows = (
            await session.execute(
                select(QueueTicket.name, QueueTicket.called_at)
                .where(*predicates)
                .order_by(_sort_key().asc(), QueueTicket.id.asc())
                .limit(limit)
            )
        ).all()
        total = (await session.execute(select(func.count()).where(*predicates))).scalar_one()
        return rows, total
