import dataclasses
from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.constants import BookingStatus


class CheckInOutcome(StrEnum):
    """What F34's two check-in writers answer, because a bare `Booking | None`
    cannot express three things (spec D4(5)).

    Deliberately NOT in `app/models/constants.py`: every enum there is a
    PERSISTED value, and this one is never written anywhere. Putting it there
    would make it the first non-persisted member and would invite a future
    migration author to widen a CHECK for it. It lives beside the writers that
    return it, following this module's own precedent for non-persisted return
    contracts — `BookingFact` and `CustomerHistory` above.
    """

    # The predicate matched: THIS request wrote it. Read off the `.returning()`
    # scalar and nowhere else.
    WROTE = "wrote"
    # Zero rows, and the predicate's TARGET STATE already holds. It reads two
    # ways and both are 200-unchanged: for `check_in` it is "she is already
    # checked in", for `undo_check_in` it is "it is already clear". What the
    # member names is the target state holding, which is exactly what makes 200
    # the honest answer rather than 409 — the outcome the caller wanted is the
    # outcome that holds, so refusing would be a lie told to the person who was
    # right.
    ALREADY_CHECKED_IN = "already_checked_in"
    # Zero rows because the row is no longer `confirmed` — somebody cancelled her
    # in the gap. 409. `undo_check_in` carries no status guard, so it can never
    # answer this one.
    NOT_CONFIRMED = "not_confirmed"
    # The row is gone or soft-deleted (or was never this tenant's, which RLS
    # makes the same thing). 404.
    MISSING = "missing"


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
        status: str = BookingStatus.CONFIRMED.value,
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
        F15 (Interview Q6) and belongs to the owner-created-bookings spec.

        `status` defaults to the model's own server default, so every pre-F19
        caller is byte-identical. F19's deposit flow passes `pending_payment`:
        the booking claims the seat FIRST and the money arrives second, and a
        held seat is an occupied seat because every occupancy predicate here
        excludes `cancelled` and nothing else."""
        row = Booking(
            tenant_id=tenant_id,
            customer_id=customer_id,
            appointment_type_id=appointment_type_id,
            starts_at=starts_at,
            seat_index=seat_index,
            status=status,
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

    async def check_in(
        self, session: AsyncSession, tenant_id: UUID, booking_id: UUID, *, at: datetime
    ) -> tuple[CheckInOutcome, Booking | None]:
        """F34: record that this person is physically in the boutique.

        Idempotent by predicate, `confirm_attendance`'s shape verbatim: `IS NULL`
        means a second staffer's tap keeps the FIRST arrival time rather than
        moving it. What is NOT copied from `confirm_attendance` is its ANSWER —
        it never returns None for zero rows and its caller renders whatever comes
        back, because a bride re-tapping her own link has exactly one possible
        meaning. Check-in has two, and they mean opposite things:

          * already checked in            -> 200 unchanged, no audit row
          * no longer confirmed (a cancel landed in the gap) -> 409

        So this must discriminate, and `cancel`'s rule above is the governing
        precedent: the `.returning()` scalar is the ONLY honest "did I write?".
        The re-read cannot answer it, because this UPDATE is ORM-enabled DML
        whose default `evaluate` synchronization stamps `checked_in_at = :at`
        onto the identity-mapped instance WHATEVER the database matched, the
        factory is built `expire_on_commit=False`, and `by_id` hands that same
        poisoned object back. A caller doing `if booking.checked_in_at is not
        None` after the write is reading the value it just wrote in memory: the
        409 branch becomes unreachable, a check-in that lost to a concurrent
        cancel answers a false 200 on a `cancelled` row with no audit trail
        behind it, and the render carries the LOSING staffer's timestamp —
        contradicting the one guarantee this case exists to make.

        Hence step 2's `populate_existing=True`: it overwrites the
        identity-mapped instance's attributes from the row the database actually
        holds, undoing the stamp, and under READ COMMITTED that statement sees
        the other transaction's commit. One statement and one documented flag,
        fixing the discrimination and the rendering together. A column-only Core
        `select(Booking.status, Booking.checked_in_at)` would answer the branch
        equally well but leaves the entity poisoned for RENDERING, so it needs a
        second re-read anyway; `session.refresh()` is the same statement with
        more surface.

        No advisory lock. F15 takes one for the reschedule because that PICKS A
        SEAT FROM A COUNT (see `insert` above); this reads and writes one column
        on one row and has no cross-row invariant to serialise. Taking it would
        serialise every check-in in the boutique against every public booking
        create, for nothing.
        """
        wrote = await session.execute(
            update(Booking)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.id == booking_id,
                Booking.checked_in_at.is_(None),
                Booking.status == BookingStatus.CONFIRMED.value,
                Booking.deleted_at.is_(None),
            )
            .values(checked_in_at=at)
            .returning(Booking.id)
        )
        refreshed = await self._refreshed(session, tenant_id, booking_id)
        if wrote.scalar_one_or_none() is not None:
            return CheckInOutcome.WROTE, refreshed
        if refreshed is None:
            return CheckInOutcome.MISSING, None
        # The two zero-row causes, separated by what the DATABASE now says and
        # never by the object this request mutated.
        if refreshed.checked_in_at is not None:
            return CheckInOutcome.ALREADY_CHECKED_IN, refreshed
        return CheckInOutcome.NOT_CONFIRMED, refreshed

    async def undo_check_in(
        self, session: AsyncSession, tenant_id: UUID, booking_id: UUID
    ) -> tuple[CheckInOutcome, Booking | None]:
        """The undo of a mis-tapped check-in — and it carries NO status guard at
        all (spec D5), the `/confirm` precedent: a mis-tap is correctable
        whenever it is noticed. A bride checked in and then cancelled must still
        have it undoable, or a wrong arrival record is permanent on a surface
        where the tap is one finger wide.

        So its only failure is MISSING, and `ALREADY_CHECKED_IN` here reads as
        "it is already clear". It uses the same refreshed read as `check_in`, for
        the same reason: a concurrent undo must render the database's NULL and
        not this request's own stamp.
        """
        wrote = await session.execute(
            update(Booking)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.id == booking_id,
                Booking.checked_in_at.is_not(None),
                Booking.deleted_at.is_(None),
            )
            .values(checked_in_at=None)
            .returning(Booking.id)
        )
        refreshed = await self._refreshed(session, tenant_id, booking_id)
        if wrote.scalar_one_or_none() is not None:
            return CheckInOutcome.WROTE, refreshed
        if refreshed is None:
            return CheckInOutcome.MISSING, None
        # Zero rows with the row still present can only mean `checked_in_at` is
        # already NULL — there is no status guard to fail. So the undo
        # structurally cannot answer NOT_CONFIRMED, and the target state holding
        # is read as "it is already clear".
        return CheckInOutcome.ALREADY_CHECKED_IN, refreshed

    async def _refreshed(
        self, session: AsyncSession, tenant_id: UUID, booking_id: UUID
    ) -> Booking | None:
        """The re-read that defeats the identity map. Both check-in writers
        classify off THIS row and off their own `.returning()` scalar — never off
        an object the caller loaded earlier.

        `populate_existing=True` is the whole mechanism and it is not a spare
        keyword to drop: without it this SELECT returns the instance already in
        the identity map WITHOUT overwriting its attributes — i.e. the object the
        UPDATE's `evaluate` synchronization just stamped — so the branch above it
        would read this request's own intent instead of the database's answer,
        which is exactly the bug the writers' docstrings describe. Under READ
        COMMITTED this statement also sees a concurrent transaction's commit,
        which is what makes the losing writer render the WINNER's timestamp.
        """
        return (
            await session.execute(
                select(Booking)
                .where(
                    Booking.tenant_id == tenant_id,
                    Booking.id == booking_id,
                    Booking.deleted_at.is_(None),
                )
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

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
        allowed_from: tuple[str, ...] = (BookingStatus.CONFIRMED.value,),
        not_before: datetime | None = None,
    ) -> Booking | None:
        """One statement, and the seat is freed structurally: both partial unique
        indexes (0008's slot-seat, 0009's per-customer instant) exclude
        `status = 'cancelled'`, so this simultaneously returns the seat to the
        grid and re-opens the idempotency slot for a rebook at the same instant.

        Guarded on `status IN allowed_from` so a repeat cancel writes nothing and
        keeps the first cancellation's evidence — the caller re-reads and renders
        the same cancelled state.

        `allowed_from` defaults to `('confirmed',)`, which is every pre-F19
        caller unchanged. F19's expiry sweeper passes `('pending_payment',)`
        (D2): releasing an abandoned deposit hold is the same write with the
        same evidence, so it gets one widened keyword rather than a SECOND
        writer of `cancelled_at`/`cancelled_by`. The default is also what keeps
        the sweeper's rows invisible to the owner and customer paths, which must
        409 on an unpaid hold rather than cancel it out from under the gateway.

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
            Booking.status.in_(allowed_from),
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

    async def rebind(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        booking_id: UUID,
        *,
        seat_index: int,
        allowed_from: tuple[str, ...],
        not_before: datetime,
    ) -> Booking | None:
        """F19 D5 step 3: a deposit that arrived after the hold was swept buys
        back the seat she chose. One guarded UPDATE — status, seat, and the
        clearing of the cancel evidence, together or not at all.

        **It is not `set_status`.** That writer emits `.values(status=to)` and
        NOTHING else by design (its own docstring says so), and it cannot carry
        `seat_index`. Splitting the rebind into two statements would open a
        window where the row reads `confirmed` at a STALE seat index — and
        because `create_booking` hands freed seat numbers back out, that stale
        index is very likely ANOTHER BRIDE'S SEAT.

        **The cancel evidence is cleared.** A row reading `confirmed` while
        still carrying `cancelled_at`/`cancelled_by` is the exact defect that
        made `set_status` wrong for the cancel path, and those two columns feed
        F52's attribution and F20's compliance read. The cancellation was
        undone; the RECORD of it survives in the `GATEWAY_LATE_SETTLEMENT` audit
        row and in `payments.error`.

        **`not_before` is REQUIRED**, unlike on its sibling writers, where it is
        an opt-in keyword. The provider's retry budget against a 15-minute hold
        is unknowable until a real PSP exists, so a delivery that arrives hours
        or days late is not a hypothetical: without the bound it would flip a
        PAST booking to `confirmed`, mint a fresh manage token, and text the
        bride "your appointment is confirmed" for a date that has already
        passed, while silently re-occupying a seat in a past slot.

        **`allowed_from` admits BOTH `cancelled` and `pending_payment`.**
        `cancelled` is the ordinary case. `pending_payment` is the belt for a
        sweeper ordering race: if the sweeper's payments UPDATE has committed
        but its booking cancel has not yet been observed, the booking is still
        `pending_payment`, and a narrow `('cancelled',)` would match nothing and
        file a FALSE "seat taken" alert on a seat that is in fact free.

        `None` means the predicate matched nothing, read off the `.returning()`
        scalar for the reason `cancel` documents. It is not an error: D5 step 4
        (hold the money, alert the owner) is the honest answer to a seat that is
        no longer free, and `IntegrityError` from either partial unique index
        routes to that same branch in the caller.
        """
        stmt = (
            update(Booking)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.id == booking_id,
                Booking.status.in_(allowed_from),
                Booking.starts_at > not_before,
                Booking.deleted_at.is_(None),
            )
            .values(
                status=BookingStatus.CONFIRMED.value,
                seat_index=seat_index,
                cancelled_at=None,
                cancelled_by=None,
            )
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

    async def list_recent_for_customer(
        self, session: AsyncSession, tenant_id: UUID, *, customer_id: UUID, limit: int
    ) -> list[Booking]:
        """The CRM screen's booking-history panel (F53 D4). Rides
        idx_bookings_tenant_customer, same as `list_live_for_customer` above.

        **Every status, cancelled included, and no lower bound on `starts_at`** —
        which is the whole reason this is a second method rather than a call to
        that one. `list_live_for_customer` is F15's re-mint feed: it pins
        `status = 'confirmed'` and `starts_at > after` because it answers "which
        manage links must be reissued". Reused here it would show a bride with
        three past cancellations an empty history, and "she cancelled twice" is
        precisely the fact this screen exists to surface — `list_day`'s argument,
        one panel over.
        """
        stmt = (
            select(Booking)
            .where(
                Booking.tenant_id == tenant_id,
                Booking.customer_id == customer_id,
                Booking.deleted_at.is_(None),
            )
            .order_by(Booking.starts_at.desc())
            .limit(limit)
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
