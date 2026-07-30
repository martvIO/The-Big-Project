from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.constants import BookingStatus


class BookingsRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see StaffUsersRepository)."""

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        appointment_type_id: UUID,
        starts_at: datetime,
        seat_index: int,
        terms_version_accepted: int,
        terms_accepted_at: datetime,
        appointment_type_name: str,
        dress_id: UUID | None = None,
        dress_name: str | None = None,
        dress_size: str | None = None,
        notes: str | None = None,
        manage_token_hash: str | None = None,
    ) -> Booking:
        """Flush surfaces IntegrityError when the (tenant, starts_at, seat_index)
        partial unique index rejects a lost race. Deliberately NOT pre-checked
        here: the index is the truth and a pre-check would be a TOCTOU — the
        service maps the error to SLOT_UNAVAILABLE.

        **Any caller that picks `seat_index` from `active_seats_at` must first
        hold `pg_advisory_xact_lock(hashtext(tenant_id))`** — see
        BookingService.create_booking. Oversell stays structurally impossible
        without it (the index is the backstop), but a writer that skips the
        lock races the read and hands honest customers a spurious 409. F15's
        owner-side reschedule is the next caller; owner-side creation is out of
        F15 (Interview Q6) and belongs to the owner-created-bookings spec."""
        row = Booking(
            tenant_id=tenant_id,
            customer_id=customer_id,
            appointment_type_id=appointment_type_id,
            starts_at=starts_at,
            seat_index=seat_index,
            terms_version_accepted=terms_version_accepted,
            terms_accepted_at=terms_accepted_at,
            appointment_type_name=appointment_type_name,
            dress_id=dress_id,
            dress_name=dress_name,
            dress_size=dress_size,
            notes=notes,
            manage_token_hash=manage_token_hash,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, booking_id: UUID
    ) -> Booking | None:
        stmt = select(Booking).where(
            Booking.tenant_id == tenant_id,
            Booking.id == booking_id,
            Booking.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def active_at(
        self, session: AsyncSession, tenant_id: UUID, *, customer_id: UUID, starts_at: datetime
    ) -> Booking | None:
        """This customer's live booking at one instant, or None.

        The predicate mirrors 0009's partial unique index exactly, so a hit is
        precisely a row that index would refuse to duplicate — which is what
        lets `create_booking` answer a replayed create with the existing
        booking instead of a second appointment. `scalar_one_or_none` is safe
        for the same reason: the index permits at most one."""
        stmt = select(Booking).where(
            Booking.tenant_id == tenant_id,
            Booking.customer_id == customer_id,
            Booking.starts_at == starts_at,
            Booking.status != BookingStatus.CANCELLED.value,
            Booking.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def active_seats_at(
        self, session: AsyncSession, tenant_id: UUID, *, starts_at: datetime
    ) -> set[int]:
        """Seat indexes occupied at one instant. `status <> 'cancelled'` mirrors
        the unique index predicate exactly: a no-show or completed booking still
        holds its seat, only a cancellation frees it — so the claim can hand a
        freed seat number back out instead of overflowing past capacity."""
        stmt = select(Booking.seat_index).where(
            Booking.tenant_id == tenant_id,
            Booking.starts_at == starts_at,
            Booking.status != BookingStatus.CANCELLED.value,
            Booking.deleted_at.is_(None),
        )
        return set((await session.execute(stmt)).scalars().all())

    async def by_manage_token_hash(
        self, session: AsyncSession, tenant_id: UUID, token_hash: str
    ) -> Booking | None:
        """The tokenized page's ONLY read path — possession of the link, never an
        id. Rides idx_bookings_manage_token.

        No status predicate: a cancelled booking and a past one both still answer
        the link (the design's C and P states), because an honest "this was
        cancelled" beats a dead link for someone re-opening her SMS. The service
        decides which ACTIONS remain legal.
        """
        stmt = select(Booking).where(
            Booking.tenant_id == tenant_id,
            Booking.manage_token_hash == token_hash,
            Booking.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def set_manage_token_hash(
        self, session: AsyncSession, tenant_id: UUID, booking_id: UUID, *, token_hash: str
    ) -> Booking | None:
        """Mint-or-rotate. The backfill uses it to fill a pre-F16 row; F15's
        edit-phone remedy and its resend call this directly, inside their own
        transaction (D8), to invalidate a link that went to the wrong number."""
        stmt = (
            update(Booking)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.id == booking_id,
                Booking.deleted_at.is_(None),
            )
            .values(manage_token_hash=token_hash)
            .returning(Booking.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.by_id(session, tenant_id, booking_id)

    async def confirm_attendance(
        self, session: AsyncSession, tenant_id: UUID, booking_id: UUID, *, at: datetime
    ) -> Booking | None:
        """Idempotent by predicate, not by a read-then-write: `IS NULL` means a
        second tap keeps the FIRST confirmation's timestamp rather than moving
        it, and a caller that gets no row back re-reads the booking and renders
        the same success (checklist row 21)."""
        stmt = (
            update(Booking)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.id == booking_id,
                Booking.attendance_confirmed_at.is_(None),
                Booking.status == BookingStatus.CONFIRMED.value,
                Booking.deleted_at.is_(None),
            )
            .values(attendance_confirmed_at=at)
            .returning(Booking.id)
        )
        await session.execute(stmt)
        return await self.by_id(session, tenant_id, booking_id)

    async def cancel(
        self, session: AsyncSession, tenant_id: UUID, booking_id: UUID, *, at: datetime, by: str
    ) -> Booking | None:
        """One statement, and the seat is freed structurally: both partial unique
        indexes (0008's slot-seat, 0009's per-customer instant) exclude
        `status = 'cancelled'`, so this simultaneously returns the seat to the
        grid and re-opens the idempotency slot for a rebook at the same instant.

        Guarded on `status = 'confirmed'` so a repeat cancel writes nothing and
        keeps the first cancellation's evidence — the caller re-reads and renders
        the same cancelled state."""
        stmt = (
            update(Booking)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.id == booking_id,
                Booking.status == BookingStatus.CONFIRMED.value,
                Booking.deleted_at.is_(None),
            )
            .values(status=BookingStatus.CANCELLED.value, cancelled_at=at, cancelled_by=by)
            .returning(Booking.id)
        )
        await session.execute(stmt)
        return await self.by_id(session, tenant_id, booking_id)

    async def list_confirmed_without_manage_token(
        self, session: AsyncSession, tenant_id: UUID, *, after: datetime, limit: int
    ) -> list[Booking]:
        """The backfill's feed (D10): confirmed, still in the future, and never
        issued a link. The predicate is also what makes a second run a no-op —
        the first run filled `manage_token_hash`."""
        stmt = (
            select(Booking)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.status == BookingStatus.CONFIRMED.value,
                Booking.starts_at > after,
                Booking.manage_token_hash.is_(None),
                Booking.deleted_at.is_(None),
            )
            .order_by(Booking.starts_at)
            .limit(limit)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def count_by_start(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        from_instant: datetime,
        until_instant: datetime,
    ) -> dict[datetime, int]:
        """Per-instant occupied-seat counts in [from_instant, until_instant) —
        the real feed for F12's `booked` mapping. Half-open on the right so a
        caller can pass start-of-next-day without double counting midnight.
        One GROUP BY range scan on idx_bookings_tenant_starts."""
        stmt = (
            select(Booking.starts_at, func.count())
            .where(
                Booking.tenant_id == tenant_id,
                Booking.starts_at >= from_instant,
                Booking.starts_at < until_instant,
                Booking.status != BookingStatus.CANCELLED.value,
                Booking.deleted_at.is_(None),
            )
            .group_by(Booking.starts_at)
        )
        return {starts_at: count for starts_at, count in (await session.execute(stmt)).all()}
