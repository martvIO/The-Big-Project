import dataclasses
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.constants import BookingStatus


@dataclasses.dataclass(frozen=True)
class BookingFact:
    """One row of F52's narrow window projection — seven scalar columns, never
    `select(Booking)`.

    `notes` (free customer text), `manage_token_hash` (a credential hash) and
    `dress_name` must not enter a process that only COUNTS, and seven columns is
    smaller as well as disclosure-minimizing.

    `created_at` earns its place as the seventh: `appointment_type_name` is
    snapshotted when the booking is written (`models/booking.py:19-22`), so the
    newest snapshot of a renamed type belongs to the booking with the greatest
    `created_at`, not the greatest `starts_at`. In a boutique where brides book
    months ahead those two orders disagree routinely (D6).

    `appointment_type_id` and `appointment_type_name` are NOT NULL on the table
    (`0008_bookings.py:63, 71`), so they are non-optional here — a nullable fact
    would put an unproducible `None` into D6's sort key.
    """

    starts_at: datetime
    created_at: datetime
    status: str
    cancelled_by: str | None
    customer_id: UUID
    appointment_type_id: UUID
    appointment_type_name: str


@dataclasses.dataclass(frozen=True)
class CustomerHistory:
    """One cohort member's lifetime, as of the window's right edge — the read
    that cannot fold into the window projection, because it needs rows OUTSIDE
    the window (D7)."""

    first_starts_at: datetime
    bookings: int


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
        self,
        session: AsyncSession,
        tenant_id: UUID,
        booking_id: UUID,
        *,
        token_hash: str,
        allowed_from: tuple[str, ...] | None = None,
        not_before: datetime | None = None,
    ) -> Booking | None:
        """Mint-or-rotate. The backfill uses it to fill a pre-F16 row; F15's
        edit-phone remedy and its resend call this directly, inside their own
        transaction (D8), to invalidate a link that went to the wrong number.

        The two guard keywords are F15's and default to off, so the backfill and
        `reissue_manage_token` keep today's contract byte for byte. F15 passes
        `('confirmed',)` and `now`: D8 requires the same predicate the Python
        guard checked to ride the rotation UPDATE, so a booking that stopped
        being confirmed-and-future between the read and here cannot be handed a
        fresh LIVE control token. That is what makes `None` mean something the
        caller must roll back on rather than a discarded result."""
        predicate = [
            Booking.tenant_id == tenant_id,
            Booking.id == booking_id,
            Booking.deleted_at.is_(None),
        ]
        if allowed_from is not None:
            predicate.append(Booking.status.in_(allowed_from))
        if not_before is not None:
            predicate.append(Booking.starts_at > not_before)
        stmt = (
            update(Booking)
            .where(*predicate)
            .values(manage_token_hash=token_hash)
            .returning(Booking.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.by_id(session, tenant_id, booking_id)

    async def set_customer_id(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        booking_id: UUID,
        *,
        customer_id: UUID,
        allowed_from: tuple[str, ...],
        not_before: datetime,
    ) -> Booking | None:
        """D8's collision branch: the corrected number already belongs to
        another live customer of this tenant, so the BOOKING moves to her rather
        than the digits moving onto a row that is not hers. Both customer rows
        survive — the original may be a real other person, and soft-deleting on
        a guess is worse than leaving a row nobody looks at.

        Carries the same confirmed-and-future guard as the rotation beside it.
        The flush can still raise `IntegrityError` from
        `idx_bookings_tenant_customer_starts_unique` (0009) when the target
        customer already holds this instant; the service pre-checks with
        `active_at` so that is a 409 and not a 500, and this is the backstop."""
        stmt = (
            update(Booking)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.id == booking_id,
                Booking.status.in_(allowed_from),
                Booking.starts_at > not_before,
                Booking.deleted_at.is_(None),
            )
            .values(customer_id=customer_id)
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

    async def set_status(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        booking_id: UUID,
        *,
        to: str,
        allowed_from: tuple[str, ...],
        not_before: datetime | None = None,
        not_after: datetime | None = None,
    ) -> Booking | None:
        """The owner console's three non-cancel transitions, as one writer (D3):
        no-show, completed, and the confirm that undoes a mis-tap of either.

        `allowed_from` is the graph edge and the clock bounds are the
        `starts_at` split the graph turns on — `not_after` for the attendance
        verbs (a PAST appointment), `not_before` for anything that only applies
        to a future one. `None` back means the predicate matched nothing, which
        the service answers as 409: it has already read the row and ruled out
        the legal-repeat case in Python, so a zero-row result here can only be
        a concurrent writer.

        Never writes `cancelled_at` / `cancelled_by` — cancel keeps its own
        writer because it carries that evidence and is shared with the customer
        path. And never `attendance_confirmed_at`: that is F16's column and it
        means the bride said she is coming, not that the owner recorded an
        outcome."""
        predicate = [
            Booking.tenant_id == tenant_id,
            Booking.id == booking_id,
            Booking.status.in_(allowed_from),
            Booking.deleted_at.is_(None),
        ]
        if not_before is not None:
            predicate.append(Booking.starts_at > not_before)
        if not_after is not None:
            predicate.append(Booking.starts_at <= not_after)
        stmt = update(Booking).where(*predicate).values(status=to).returning(Booking.id)
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.by_id(session, tenant_id, booking_id)

    async def cancel(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        booking_id: UUID,
        *,
        at: datetime,
        by: str,
        not_before: datetime | None = None,
    ) -> Booking | None:
        """One statement, and the seat is freed structurally: both partial unique
        indexes (0008's slot-seat, 0009's per-customer instant) exclude
        `status = 'cancelled'`, so this simultaneously returns the seat to the
        grid and re-opens the idempotency slot for a rebook at the same instant.

        Guarded on `status = 'confirmed'` so a repeat cancel writes nothing and
        keeps the first cancellation's evidence — the caller re-reads and renders
        the same cancelled state.

        `None` means the predicate matched nothing, and reading it off the
        `.returning()` scalar is the ONLY way to know that. The re-read cannot
        tell: `update(Booking)` on an `AsyncSession` is ORM-enabled DML whose
        default `evaluate` synchronization stamps the SET values onto the
        identity-mapped instance whatever the database matched, and `by_id`
        hands that same instance back. So a customer cancel that lands in the
        owner's window comes back reading `cancelled` / `cancelled_by='owner'`
        while the row says `customer` — a caller inspecting the returned row
        cannot distinguish its own write from anyone else's.

        `not_before` adds `starts_at > :not_before` and is F15's owner cancel
        ONLY (D3). The customer path must never pass it: `ManageBookingService`
        has already ruled out the cancelled and already-started cases in Python,
        so widening the predicate unconditionally would turn its 409
        BOOKING_ALREADY_STARTED into a 200 rendering an un-cancelled booking."""
        predicate = [
            Booking.tenant_id == tenant_id,
            Booking.id == booking_id,
            Booking.status == BookingStatus.CONFIRMED.value,
            Booking.deleted_at.is_(None),
        ]
        if not_before is not None:
            predicate.append(Booking.starts_at > not_before)
        stmt = (
            update(Booking)
            .where(*predicate)
            .values(status=BookingStatus.CANCELLED.value, cancelled_at=at, cancelled_by=by)
            .returning(Booking.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.by_id(session, tenant_id, booking_id)

    async def reschedule(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        booking_id: UUID,
        *,
        starts_at: datetime,
        seat_index: int,
        not_before: datetime,
    ) -> Booking | None:
        """D5 step 7: the move, in place, as one statement.

        The source seat needs no separate release — both partial unique indexes
        are re-evaluated over the row's new values. A collision on
        `idx_bookings_slot_seat_unique` raises `IntegrityError`, which the
        service maps to SLOT_UNAVAILABLE exactly as `create_booking` maps its
        own lost race.

        `None` is not silence: the per-tenant advisory lock the caller holds
        serializes this against public creates but NOT against the owner status
        endpoints, so zero rows means a concurrent cancel or no-show landed
        between the caller's read and this write. The service rolls back rather
        than committing an audit row for a move that did not happen."""
        stmt = (
            update(Booking)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.id == booking_id,
                Booking.status == BookingStatus.CONFIRMED.value,
                Booking.starts_at > not_before,
                Booking.deleted_at.is_(None),
            )
            .values(starts_at=starts_at, seat_index=seat_index)
            .returning(Booking.id)
        )
        if (await session.execute(stmt)).scalar_one_or_none() is None:
            return None
        return await self.by_id(session, tenant_id, booking_id)

    async def list_day(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        from_instant: datetime,
        until_instant: datetime,
        offset: int,
        limit: int,
    ) -> tuple[list[Booking], int]:
        """The owner console's day list (D17): page plus whole-day total, in
        `[from_instant, until_instant)` — half-open on the right so the caller
        can pass start-of-next-day. One range scan on idx_bookings_tenant_starts.

        **Every status, cancelled included.** This deliberately does NOT inherit
        `count_by_start`'s `status <> 'cancelled'` predicate: that method mirrors
        the occupancy indexes, while a cancelled row here is the owner's evidence
        that the slot re-opened."""
        window = (
            Booking.tenant_id == tenant_id,
            Booking.starts_at >= from_instant,
            Booking.starts_at < until_instant,
            Booking.deleted_at.is_(None),
        )
        page = (
            select(Booking)
            .where(*window)
            .order_by(Booking.starts_at, Booking.seat_index)
            .offset(offset)
            .limit(limit)
        )
        rows = list((await session.execute(page)).scalars().all())
        total = (
            await session.execute(select(func.count()).select_from(Booking).where(*window))
        ).scalar_one()
        return rows, total

    async def list_live_for_customer(
        self, session: AsyncSession, tenant_id: UUID, *, customer_id: UUID, after: datetime
    ) -> list[Booking]:
        """Every booking of this customer whose manage link is still live (D8) —
        the set a phone correction has to re-mint, because `customers.phone` is
        the identity every future SMS reads at send time while
        `manage_token_hash` is per-row. Rides idx_bookings_tenant_customer."""
        stmt = (
            select(Booking)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.customer_id == customer_id,
                Booking.status == BookingStatus.CONFIRMED.value,
                Booking.starts_at > after,
                Booking.deleted_at.is_(None),
            )
            .order_by(Booking.starts_at)
        )
        return list((await session.execute(stmt)).scalars().all())

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

    async def list_window_facts(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        from_instant: datetime,
        until_instant: datetime,
    ) -> list[BookingFact]:
        """F52's narrow window projection: seven scalar columns, EVERY status,
        one range scan on idx_bookings_tenant_starts, half-open on the right.

        Deliberately NOT `select(Booking)`: the ORM row drags `notes` (free
        customer text), `manage_token_hash` (a credential hash) and `dress_name`
        into a process that only counts.

        Deliberately NOT `count_by_start`: its `status <> 'cancelled'` predicate
        mirrors the occupancy indexes, so a cancellation rate computed under it
        is structurally always 0%. Widening `count_by_start` is worse — the slot
        engine depends on it, and the one thing that predicate must not do is
        change.

        **No ORDER BY.** Nothing downstream depends on row order, which is
        precisely why D6's sort key carries `str(appointment_type_id)` as a
        total tie-break rather than leaning on `sorted`'s stability over
        whatever Postgres happened to return.
        """
        stmt = select(
            Booking.starts_at,
            Booking.created_at,
            Booking.status,
            Booking.cancelled_by,
            Booking.customer_id,
            Booking.appointment_type_id,
            Booking.appointment_type_name,
        ).where(
            Booking.tenant_id == tenant_id,
            Booking.starts_at >= from_instant,
            Booking.starts_at < until_instant,
            Booking.deleted_at.is_(None),
        )
        return [
            BookingFact(
                starts_at=starts_at,
                created_at=created_at,
                status=status,
                cancelled_by=cancelled_by,
                customer_id=customer_id,
                appointment_type_id=appointment_type_id,
                appointment_type_name=appointment_type_name,
            )
            for (
                starts_at,
                created_at,
                status,
                cancelled_by,
                customer_id,
                appointment_type_id,
                appointment_type_name,
            ) in (await session.execute(stmt)).all()
        ]

    async def history_by_customer(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        customer_ids: Sequence[UUID],
        *,
        until_instant: datetime,
    ) -> dict[UUID, CustomerHistory]:
        """Each cohort member's lifetime as of the window's right edge — the one
        read that cannot fold into `list_window_facts`, because it needs rows
        OUTSIDE the window (D7). `aggregate_by_dress`'s shape, including the
        empty-input short-circuit. Rides idx_bookings_tenant_customer.

        Both bounds are the metric definitions, not conveniences: cancellations
        are excluded because a bride who booked and cancelled did not visit, and
        `starts_at < until_instant` is what stops a fitting booked for next
        month from retroactively changing last quarter's numbers.
        """
        if not customer_ids:
            return {}
        stmt = (
            select(Booking.customer_id, func.min(Booking.starts_at), func.count())
            .where(
                Booking.tenant_id == tenant_id,
                Booking.customer_id.in_(customer_ids),
                Booking.status != BookingStatus.CANCELLED.value,
                Booking.starts_at < until_instant,
                Booking.deleted_at.is_(None),
            )
            .group_by(Booking.customer_id)
        )
        return {
            customer_id: CustomerHistory(first_starts_at=first_starts_at, bookings=bookings)
            for customer_id, first_starts_at, bookings in (await session.execute(stmt)).all()
        }
