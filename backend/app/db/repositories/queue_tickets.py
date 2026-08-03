import datetime
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import ColumnElement, Row, func, select
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


class QueueTicketsRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see CustomersRepository).

    There is no `active_today`, no dedup lookup and no read keyed on `phone`:
    the create always creates, so nothing in the request path ever consults the
    number a caller submitted. That absence is the security property, not an
    omission.
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
