from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.constants import PaymentStatus
from app.models.payment import Payment


class PaymentsRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see StaffUsersRepository)."""

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        booking_id: UUID,
        provider: str,
        amount_agorot: int,
        provider_session_id: str,
        redirect_url: str,
        hold_expires_at: datetime,
    ) -> Payment:
        """Flush surfaces IntegrityError when idx_payments_booking_pending_unique
        refuses a second LIVE hold for this booking. That index is the backstop
        for a writer that skipped the advisory lock (D23), not the mechanism —
        `live_pending_for_booking` under the lock is the mechanism.

        `redirect_url` is stored rather than re-minted (F19 D8) and is required,
        not optional: `open_deposit`'s converge path calls no gateway at all, so
        a double-tap has no hosted page to hand back unless this column kept the
        first one — and minting a second session there is precisely the orphaned
        payable session D23's ordering exists to prevent."""
        row = Payment(
            tenant_id=tenant_id,
            booking_id=booking_id,
            provider=provider,
            amount_agorot=amount_agorot,
            status=PaymentStatus.PENDING.value,
            provider_session_id=provider_session_id,
            redirect_url=redirect_url,
            hold_expires_at=hold_expires_at,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def live_pending_for_booking(
        self, session: AsyncSession, tenant_id: UUID, *, booking_id: UUID
    ) -> Payment | None:
        """D23's converge read. The pending row the unique index permits at most
        one of — read under the per-tenant advisory lock, BEFORE the gateway is
        called, so a double-tap returns the existing hold instead of minting a
        second payable session at the provider with no row behind it."""
        stmt = select(Payment).where(
            Payment.tenant_id == tenant_id,
            Payment.booking_id == booking_id,
            Payment.status == PaymentStatus.PENDING.value,
            Payment.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_provider_transaction_id(
        self, session: AsyncSession, tenant_id: UUID, *, provider: str, transaction_id: str
    ) -> Payment | None:
        stmt = select(Payment).where(
            Payment.tenant_id == tenant_id,
            Payment.provider == provider,
            Payment.provider_transaction_id == transaction_id,
            Payment.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_provider_session_id(
        self, session: AsyncSession, tenant_id: UUID, *, provider: str, session_id: str
    ) -> Payment | None:
        stmt = select(Payment).where(
            Payment.tenant_id == tenant_id,
            Payment.provider == provider,
            Payment.provider_session_id == session_id,
            Payment.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def settle(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        payment_id: UUID,
        *,
        provider_transaction_id: str,
        paid_at: datetime,
    ) -> Payment | None:
        """ONE guarded UPDATE, never a read-modify-write (D24) — the
        ScheduledMessageRepository.mark shape.

        `WHERE status='pending'` is evaluated by the DATABASE under the row lock,
        not by us, which is the only reason exactly one of two concurrent
        redeliveries can transition the row. A read-then-write is idempotent
        only SEQUENTIALLY: both deliveries would see no settled row, both would
        match the same row by session id, and 0012's unique index has no INSERT
        to refuse on this path.

        Returns None when it did not fire. The caller must then re-read and
        branch, because the two reasons for a miss are not the same event — a
        concurrent delivery won the race, or the hold already expired.

        `redirect_url` is blanked in the same `.values()` (F19 D8), as it is on
        every other exit from `pending`: a live checkout URL outliving its hold
        is a link that takes real money for a seat the boutique has already
        given away.
        """
        stmt = (
            update(Payment)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.id == payment_id,
                Payment.status == PaymentStatus.PENDING.value,
                Payment.deleted_at.is_(None),
            )
            .values(
                status=PaymentStatus.PAID.value,
                paid_at=paid_at,
                provider_transaction_id=provider_transaction_id,
                redirect_url=None,
            )
            # RETURNING rather than rowcount: the async Result is typed without
            # one (the ScheduledMessagesRepository.cancel_pending precedent).
            .returning(Payment.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.by_id(session, tenant_id, payment_id)

    async def settle_late(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        payment_id: UUID,
        *,
        provider_transaction_id: str,
        paid_at: datetime,
    ) -> Payment | None:
        """`settle`'s shape, guarded `WHERE status='expired'` — the money that
        arrived after the sweeper had already released the seat.

        F17's Gate 1 Q4 ruled that a late payment is HONOURED and the deposit
        marked `paid`. `settle` is guarded `WHERE status='pending'`, so it
        matches nothing against an expired row and that ruling shipped with no
        writer at all. This is the missing writer — an implementation gap, not a
        reopened ruling, and deliberately not a distinct `late_paid` status:
        `paid_at > hold_expires_at` already carries the distinction on the row
        itself, and a sixth status would force every present and future
        "money is in" reader to name two values.

        Writing `provider_transaction_id` also RE-ARMS
        `by_provider_transaction_id` for every subsequent redelivery of the same
        transaction, which is what stops the honour path running twice.

        `None` means the row was not `expired` — a concurrent delivery honoured
        it first, or it never expired at all. The caller stops.
        """
        stmt = (
            update(Payment)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.id == payment_id,
                Payment.status == PaymentStatus.EXPIRED.value,
                Payment.deleted_at.is_(None),
            )
            .values(
                status=PaymentStatus.PAID.value,
                paid_at=paid_at,
                provider_transaction_id=provider_transaction_id,
                redirect_url=None,
            )
            .returning(Payment.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.by_id(session, tenant_id, payment_id)

    async def by_booking_ids(
        self, session: AsyncSession, tenant_id: UUID, booking_ids: Sequence[UUID]
    ) -> dict[UUID, Payment]:
        """The owner console's batch read (F19 D18) — one query behind
        `list_day`'s page, never one per row.

        The LATEST payment per booking, because a booking can carry an expired
        hold AND a later paid one and the console renders a single badge: the
        newest row is the one that answers "where is her money". `setdefault`
        over a `created_at DESC` scan keeps the first seen, which is that row.

        Empty input issues no query at all — `history_by_customer`'s
        short-circuit, for the same reason: a day with no bookings must not pay
        for a round trip.
        """
        if not booking_ids:
            return {}
        stmt = (
            select(Payment)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.booking_id.in_(booking_ids),
                Payment.deleted_at.is_(None),
            )
            .order_by(Payment.created_at.desc())
        )
        latest: dict[UUID, Payment] = {}
        for row in (await session.execute(stmt)).scalars():
            latest.setdefault(row.booking_id, row)
        return latest

    async def record_error(
        self, session: AsyncSession, tenant_id: UUID, payment_id: UUID, *, error: str
    ) -> Payment | None:
        """Evidence, not a transition. An amount mismatch leaves `status` at
        'pending' deliberately: whether a mismatched settlement expires or is
        chased by hand is F19's sweeper policy, and inventing a 'failed'
        transition here would pre-empt it."""
        stmt = (
            update(Payment)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.id == payment_id,
                Payment.deleted_at.is_(None),
            )
            .values(error=error)
            .returning(Payment.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.by_id(session, tenant_id, payment_id)

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, payment_id: UUID
    ) -> Payment | None:
        stmt = select(Payment).where(
            Payment.tenant_id == tenant_id,
            Payment.id == payment_id,
            Payment.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()
