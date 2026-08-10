from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.constants import ScheduledMessageStatus
from app.models.scheduled_message import ScheduledMessage


class ScheduledMessagesRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see StaffUsersRepository).

    Every terminal transition clears `manage_token`: the raw link token is kept
    only for as long as a pending row still has to reproduce the link the
    confirmation SMS already sent.
    """

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        kind: str,
        send_after: datetime,
        manage_token: str | None,
        booking_id: UUID | None = None,
        waitlist_entry_id: UUID | None = None,
    ) -> ScheduledMessage:
        """Flush surfaces IntegrityError when the pending-unique index for this
        row's SUBJECT refuses a second PENDING row — `(tenant, booking, kind)`
        for a reminder, `(tenant, entry, kind)` for an offer. Either way it is
        the idempotency key, so a double-schedule converges instead of
        double-sending. Deliberately not pre-checked: the index is the truth and
        a pre-check would be a TOCTOU.

        Exactly one subject, enforced by `ck_scheduled_messages_subject`; both
        are keyword-only and defaulted so a caller cannot pass them positionally
        and get the XOR backwards.
        """
        row = ScheduledMessage(
            tenant_id=tenant_id,
            booking_id=booking_id,
            waitlist_entry_id=waitlist_entry_id,
            kind=kind,
            send_after=send_after,
            status=ScheduledMessageStatus.PENDING.value,
            manage_token=manage_token,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def pending_for_booking(
        self, session: AsyncSession, tenant_id: UUID, *, booking_id: UUID, kind: str
    ) -> ScheduledMessage | None:
        """The pending row the unique index permits at most one of."""
        stmt = select(ScheduledMessage).where(
            ScheduledMessage.tenant_id == tenant_id,
            ScheduledMessage.booking_id == booking_id,
            ScheduledMessage.kind == kind,
            ScheduledMessage.status == ScheduledMessageStatus.PENDING.value,
            ScheduledMessage.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def cancel_pending(
        self, session: AsyncSession, tenant_id: UUID, *, booking_id: UUID, kind: str
    ) -> int:
        """Flip every pending row of this kind to 'cancelled' and drop its token.
        Returns the row count so a caller can tell "there was one" from "there
        was none" without a second read."""
        stmt = (
            update(ScheduledMessage)
            .where(
                ScheduledMessage.tenant_id == tenant_id,
                ScheduledMessage.booking_id == booking_id,
                ScheduledMessage.kind == kind,
                ScheduledMessage.status == ScheduledMessageStatus.PENDING.value,
                ScheduledMessage.deleted_at.is_(None),
            )
            .values(status=ScheduledMessageStatus.CANCELLED.value, manage_token=None)
            # RETURNING rather than rowcount: the async Result is typed without
            # one, and the ids are the honest count anyway.
            .returning(ScheduledMessage.id)
        )
        return len((await session.execute(stmt)).scalars().all())

    async def latest_for_entry(
        self, session: AsyncSession, tenant_id: UUID, *, waitlist_entry_id: UUID, kind: str
    ) -> ScheduledMessage | None:
        """The offer half's read, and it is deliberately NOT `pending_for_entry`.

        D7's rule asks a question about a message that has already left pending —
        "did this offer's SMS actually reach `sent`?" — so the read has to see
        terminal rows. Newest first, because a re-offered entry accumulates one
        row per offer and only the current one is evidence about the current
        deadline.
        """
        stmt = (
            select(ScheduledMessage)
            .where(
                ScheduledMessage.tenant_id == tenant_id,
                ScheduledMessage.waitlist_entry_id == waitlist_entry_id,
                ScheduledMessage.kind == kind,
                ScheduledMessage.deleted_at.is_(None),
            )
            .order_by(ScheduledMessage.created_at.desc(), ScheduledMessage.id.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalars().first()

    async def count_failed_for_entry(
        self, session: AsyncSession, tenant_id: UUID, *, waitlist_entry_id: UUID, kind: str
    ) -> int:
        """How many of this entry's offer texts the provider has REFUSED.

        D7 sends an offer whose SMS never reached `sent` back to `waiting`, and
        for a provider outage that is right and self-healing. For a permanently
        unreachable recipient — a number that replied STOP, a disconnected line —
        it is an unbounded loop: offer, fail, wait, offer, once per window
        forever, and because `waiting_pairs` excludes any pair holding a live
        offer, every bride behind her in that queue is frozen out for the whole
        window each cycle.

        These rows are the attempt counter the entry does not carry: `_offer_one`
        inserts exactly one per offer, and a `failed` one means the adapter was
        called and said no. A `sent` message never leaves the entry `offered`
        long enough to accumulate, so a nonzero count here really is refusals.
        """
        stmt = select(func.count()).where(
            ScheduledMessage.tenant_id == tenant_id,
            ScheduledMessage.waitlist_entry_id == waitlist_entry_id,
            ScheduledMessage.kind == kind,
            ScheduledMessage.status == ScheduledMessageStatus.FAILED.value,
            ScheduledMessage.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one()

    async def cancel_pending_for_entry(
        self, session: AsyncSession, tenant_id: UUID, *, waitlist_entry_id: UUID, kind: str
    ) -> int:
        """`cancel_pending`'s offer-side twin. Same statement, other subject —
        an entry leaving `offered` (expired, claimed, declined, owner-cancelled)
        must not leave a text about that offer queued behind it."""
        stmt = (
            update(ScheduledMessage)
            .where(
                ScheduledMessage.tenant_id == tenant_id,
                ScheduledMessage.waitlist_entry_id == waitlist_entry_id,
                ScheduledMessage.kind == kind,
                ScheduledMessage.status == ScheduledMessageStatus.PENDING.value,
                ScheduledMessage.deleted_at.is_(None),
            )
            .values(status=ScheduledMessageStatus.CANCELLED.value, manage_token=None)
            .returning(ScheduledMessage.id)
        )
        return len((await session.execute(stmt)).scalars().all())

    async def claim_due(
        self, session: AsyncSession, tenant_id: UUID, *, now: datetime, limit: int
    ) -> list[ScheduledMessage]:
        """Lock and return up to `limit` due pending rows for this tenant.

        `FOR UPDATE SKIP LOCKED` — the codebase's first use, committed by
        architecture.md ("scheduled_messages table + poller worker, never 'cron
        exactly 24h'"). A second worker replica claiming concurrently skips these
        rows entirely rather than waiting on them or, worse, sending them again.

        The lock is held until the caller's transaction ends, which by design
        SPANS the provider call: the trade is at-least-once redelivery (a crash
        before the mark leaves the row pending) against the standard SKIP-LOCKED
        queue guarantee. If duplicate sends ever matter, the upgrade path is
        claim-commit-then-send with a 'sending' status.
        """
        stmt = (
            select(ScheduledMessage)
            .where(
                ScheduledMessage.tenant_id == tenant_id,
                ScheduledMessage.status == ScheduledMessageStatus.PENDING.value,
                ScheduledMessage.send_after <= now,
                ScheduledMessage.deleted_at.is_(None),
            )
            # Oldest first: a backlog drains in the order the appointments were
            # promised, not in physical row order.
            .order_by(ScheduledMessage.send_after)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def mark(
        self, session: AsyncSession, tenant_id: UUID, message_id: UUID, *, status: str
    ) -> ScheduledMessage | None:
        """Terminal transition. Guarded on `status = 'pending'` so a row can only
        leave pending once — belt to the claim's braces."""
        stmt = (
            update(ScheduledMessage)
            .where(
                ScheduledMessage.tenant_id == tenant_id,
                ScheduledMessage.id == message_id,
                ScheduledMessage.status == ScheduledMessageStatus.PENDING.value,
                ScheduledMessage.deleted_at.is_(None),
            )
            .values(status=status, manage_token=None)
            .returning(ScheduledMessage.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self._by_id(session, tenant_id, message_id)

    async def _by_id(
        self, session: AsyncSession, tenant_id: UUID, message_id: UUID
    ) -> ScheduledMessage | None:
        stmt = select(ScheduledMessage).where(
            ScheduledMessage.tenant_id == tenant_id,
            ScheduledMessage.id == message_id,
            ScheduledMessage.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()
