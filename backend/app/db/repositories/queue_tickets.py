import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.constants import QueueTicketStatus
from app.models.queue_ticket import QueueTicket


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
        sort_key = func.coalesce(QueueTicket.requeued_at, QueueTicket.created_at)
        mine = ticket.requeued_at or ticket.created_at
        stmt = select(func.count()).where(
            QueueTicket.tenant_id == tenant_id,
            QueueTicket.queue_day == ticket.queue_day,
            QueueTicket.status == QueueTicketStatus.WAITING.value,
            QueueTicket.deleted_at.is_(None),
            sort_key < mine,
        )
        return (await session.execute(stmt)).scalar_one() + 1
