"""The expiry sweeper (F19 D6/D7): two claims, one transaction, per tenant.

**Ownership — why this is its own class and not a method on PaymentService.**
`models/payment.py` says PaymentService is the single writer of `payments`, so
adding a second one deserves an argument rather than a shrug. Two facts decide
it:

1. This job writes `payments` AND `bookings` in ONE transaction, and no existing
   service owns both. PaymentService deliberately owns neither side of that
   pair — `settle_from_webhook` and `honour_late_settlement` both state in their
   own docstrings that they do not touch `bookings`, because a seat decision
   needs the per-tenant advisory lock and the occupancy reads that live in the
   booking domain. Folding a `bookings` writer into it would take that boundary
   away on the first commit.
2. PaymentService cannot be cheaply built here. It requires a `PaymentGateway`,
   a `SecretBox` and a `GatewayCredentialService` with two rate limiters, all
   assembled by private helpers in `main.py`. The sweep calls no gateway and
   decrypts nothing, so putting expiry there would hand the worker process
   merchant key material and an adapter it has no use for, purely to satisfy a
   sentence in a docstring.

**The trade-off rejected**, stated plainly: `payments.status` now has two
writers instead of one, and a future third could point at this precedent. The
containment is that this class is in the payments package, takes the same
injected `WallClock` as `open_deposit`, writes exactly one column pair on rows
its guarded WHERE already proves are `pending`, and never inserts. The
`models/payment.py` docstring needs one line amending to name it — see the
report; that file is outside this task's edit set.
"""

import dataclasses
import datetime
import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.models.constants import AuditAction, BookingCancelledBy, BookingStatus, PaymentStatus
from app.models.payment import Payment
from app.payments.service import WallClock, _utc_now

logger = logging.getLogger("app")

# One page per tick, the backfill.py CHUNK_SIZE shape rather than the drain's 50:
# neither claim holds a provider call, so the only cost of a wide page is the
# row locks it takes. Anything left over is claimed on the next tick.
SWEEP_BATCH_SIZE = 500


@dataclasses.dataclass(frozen=True)
class SweepResult:
    # Claim 1: holds whose clock ran out.
    expired: int = 0
    # ...and the bookings those holds were occupying. Below `expired` only when
    # a booking had already left `pending_payment`, which is worth noticing.
    released: int = 0
    # Claim 2: bookings that never got a payments row at all.
    orphaned: int = 0

    def __add__(self, other: "SweepResult") -> "SweepResult":
        return SweepResult(
            expired=self.expired + other.expired,
            released=self.released + other.released,
            orphaned=self.orphaned + other.orphaned,
        )


class DepositSweeper:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        hold_seconds: int,
        poll_interval_seconds: int,
        clock: WallClock = _utc_now,
    ) -> None:
        self._session_factory = session_factory
        self._hold_seconds = hold_seconds
        self._poll_interval_seconds = poll_interval_seconds
        # The SAME injected clock as `open_deposit`, deliberately: the hold is
        # written by one and read by the other, and a test that cannot move both
        # sides of that comparison together cannot pin the expiry-vs-webhook
        # race at all.
        self._clock = clock
        self._bookings = BookingsRepository()
        self._audit = AuditLogRepository()

    async def sweep(self, tenant_id: UUID) -> SweepResult:
        """Both claims in ONE transaction (D6).

        Not stylistic. If the payments UPDATE committed first, a webhook blocked
        on that row lock would wake, see `expired`, honour it, and find a booking
        still at `pending_payment` — which files a false "seat taken" alert on a
        seat that is in fact free, and then the sweeper cancels the booking
        anyway. One transaction closes that window; D5's widened `allowed_from`
        is the belt.
        """
        now = self._clock()
        async with tenant_session(self._session_factory, tenant_id) as session:
            released = 0
            claimed = await self._expire_holds(session, tenant_id, now)
            for payment_id, booking_id in claimed:
                booking = await self._bookings.cancel(
                    session,
                    tenant_id,
                    booking_id,
                    at=now,
                    by=BookingCancelledBy.EXPIRED.value,
                    allowed_from=(BookingStatus.PENDING_PAYMENT.value,),
                )
                if booking is not None:
                    released += 1
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.DEPOSIT_HOLD_EXPIRED.value,
                    entity="payments",
                    details={
                        "payment_id": str(payment_id),
                        "booking_id": str(booking_id),
                        # False means the booking had already left
                        # `pending_payment` under us. Near-unreachable — every
                        # owner and customer verb 409s on an unpaid hold — which
                        # is exactly why it is worth a trace rather than a
                        # silent skip.
                        "seat_released": booking is not None,
                    },
                )

            orphans = await self._cancel_orphans(session, tenant_id, now)
            for booking_id in orphans:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.DEPOSIT_HOLD_EXPIRED.value,
                    entity="bookings",
                    details={
                        "booking_id": str(booking_id),
                        # Same lifecycle event — a hold ran out and the seat was
                        # released — reached without a `payments` row existing at
                        # all. constants.py splits OPENED from EXPIRED because
                        # they are different states; this is not a third state,
                        # it is the same one via the crash path, and it is the
                        # only trace a gateway failure at checkout leaves.
                        "orphan": True,
                    },
                )

        return SweepResult(expired=len(claimed), released=released, orphaned=len(orphans))

    async def _expire_holds(
        self, session: AsyncSession, tenant_id: UUID, now: datetime.datetime
    ) -> list[tuple[UUID, UUID]]:
        """Claim 1 — the ordinary expiry. Rides `idx_payments_hold_expiry`.

        **No locking clause, deliberately.** A locking clause is legal only on
        SELECT; the guarded `WHERE status='pending'` evaluated by the database
        already gives exactly-once; and BLOCKING behind an in-flight `settle` is
        the desired serialization — it is what makes the ordering argument in
        `sweep` true. `SKIP LOCKED` would defer a contended row a full poll
        interval and buys nothing at one worker replica.

        The id subquery is the only way to bound an UPDATE (Postgres has no
        UPDATE ... LIMIT). It takes no locks; the outer guard is still what
        decides the race.
        """
        predicate = (
            Payment.tenant_id == tenant_id,
            Payment.status == PaymentStatus.PENDING.value,
            Payment.hold_expires_at <= now,
            Payment.deleted_at.is_(None),
        )
        stmt = (
            update(Payment)
            .where(
                *predicate,
                Payment.id.in_(select(Payment.id).where(*predicate).limit(SWEEP_BATCH_SIZE)),
            )
            # `redirect_url` is blanked on every exit from `pending` (D8): a live
            # checkout URL outliving its hold takes real money for a seat the
            # boutique has already given away.
            .values(status=PaymentStatus.EXPIRED.value, redirect_url=None)
            .returning(Payment.id, Payment.booking_id)
            # A bulk UPDATE has no single identity-mapped row to stamp, and the
            # answer is read off RETURNING regardless — see cancel()'s docstring
            # on why a re-read cannot tell you what the database matched.
            .execution_options(synchronize_session=False)
        )
        return [(row[0], row[1]) for row in (await session.execute(stmt)).all()]

    async def _cancel_orphans(
        self, session: AsyncSession, tenant_id: UUID, now: datetime.datetime
    ) -> list[UUID]:
        """Claim 2 — the orphan and crash backstop, on `bookings`. Rides
        `idx_bookings_pending_payment`.

        **Without this, every gateway failure at checkout leaks a seat
        permanently.** The booking commits first in `pending_payment`, and
        `open_deposit` opens its OWN session and re-takes the same advisory lock
        `create_booking` holds to COMMIT — so folding the two is impossible.
        Everything between the two commits leaves a committed `pending_payment`
        booking with NO payments row at all: invisible to claim 1, which sweeps
        `payments`; and this sweeper is the only writer that can move
        `pending_payment` to `cancelled`, because every owner and customer verb
        409s on an unpaid hold.

        The `+ poll_interval` grace is what guarantees this never races the
        ordinary path: a hold opened one tick ago is still claim 1's business.

        **The exclusion is `pending` OR `paid`, and the spec's own SQL had only
        `pending`.** Written that way, this claim cancels a booking whose payment
        is PAID — which is exactly race row #11, the crash between `settle`'s
        commit and the booking confirm. That window's recoverer is the next
        provider redelivery running the guarded confirm, and the confirm is
        `allowed_from=('pending_payment',)`: if this claim has already moved the
        row to `cancelled`, the redelivery matches nothing, and a bride who PAID
        is left with a cancelled appointment and her seat resold. A provider
        whose retry backoff exceeds the hold length would trigger it every time.
        Caught by `test_a_paid_hold_is_never_swept`, which is the spec's own
        "the sweeper never touches a paid booking" criterion.

        `expired` and `failed` are deliberately NOT excluded. An `expired`
        payment beside a still-`pending_payment` booking is a torn claim 1 and
        wants exactly this repair; a `failed` one is MD4's compensation having
        crashed before it confirmed, where freeing the seat is the safe outcome
        and confirming an unpaid booking is not.
        """
        grace = datetime.timedelta(seconds=self._hold_seconds + self._poll_interval_seconds)
        live_hold = (
            select(Payment.id)
            .where(
                Payment.booking_id == Booking.id,
                Payment.deleted_at.is_(None),
                Payment.status.in_((PaymentStatus.PENDING.value, PaymentStatus.PAID.value)),
            )
            .exists()
        )
        predicate = (
            Booking.tenant_id == tenant_id,
            Booking.status == BookingStatus.PENDING_PAYMENT.value,
            Booking.deleted_at.is_(None),
            Booking.created_at <= now - grace,
            ~live_hold,
        )
        stmt = (
            update(Booking)
            .where(
                *predicate,
                Booking.id.in_(select(Booking.id).where(*predicate).limit(SWEEP_BATCH_SIZE)),
            )
            .values(
                status=BookingStatus.CANCELLED.value,
                cancelled_at=now,
                cancelled_by=BookingCancelledBy.EXPIRED.value,
            )
            .returning(Booking.id)
            .execution_options(synchronize_session=False)
        )
        return list((await session.execute(stmt)).scalars().all())
