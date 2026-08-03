"""The walk-in check-in, the position read and the public wall board.

**The create always creates.** There is no dedup key, no advisory lock, no
pre-check, no `IntegrityError` path and no duplicate branch — so this module
contains no `try` block at all and the transaction is one INSERT that conflicts
with nothing. A second submission of the same number on the same day mints a
second ticket and returns it exactly as the first, which means the response is
identical in shape, in status and in work done whether or not that phone was
already in the queue. A stranger who submits a woman's mobile learns nothing
about her and takes nothing from her.

The version this replaced answered a duplicate distinguishably. That was a free,
silent, unbounded presence oracle in the positive direction; and its unique
index freed its key only on a status change or a soft delete, neither of which
anything in F33 writes — so one anonymous POST denied a named woman a queue slot
for the rest of the boutique day, with no remedy anywhere in the shipped
product. A duplicate ticket is now a real, expected outcome, and F58 merges or
removes it.

**Four limiter instances, never a second key on an existing budget.**
`max_attempts` lives on the LIMITER, so one instance is one ceiling however many
keys it holds. Reusing the OTP budgets would let a bride-heavy morning close the
door queue; reusing booking-create's would let a morning of walk-ins close the
front door; reusing the storefront read brake would let one leaked poll loop 429
the catalog for every shopper on the site. F59's board is the fourth and the
most vivid of them: one wall screen is 720 reads an hour, 3.6x the ENTIRE
check-in create ceiling, so a board sharing that budget would spend it about
seventeen minutes into the shop day and start answering 429 to every woman
scanning the QR at the door. The wall screen would close the front door.
"""

import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.db.repositories.queue_tickets import QueueTicketsRepository
from app.db.tenant import tenant_session
from app.models.queue_ticket import QueueTicket
from app.notifications.validation import normalize_israeli_mobile
from app.queue.schemas import QueueBoardEntry, QueueBoardView, TicketView
from app.queue.validation import (
    BOARD_ROW_LIMIT,
    CheckinThrottledError,
    QueueTicketNotFoundError,
    board_display_name,
    validate_checkin_request,
)
from app.storefront.validation import Clock, today_jerusalem


class QueueService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        create_limiter: FixedWindowRateLimiter,
        position_ticket_limiter: FixedWindowRateLimiter,
        position_miss_limiter: FixedWindowRateLimiter,
        board_limiter: FixedWindowRateLimiter,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._create_limiter = create_limiter
        self._position_ticket_limiter = position_ticket_limiter
        self._position_miss_limiter = position_miss_limiter
        self._board_limiter = board_limiter
        self._clock = clock
        self._tickets = QueueTicketsRepository()

    def _now(self) -> datetime.datetime:
        now = self._clock() if self._clock is not None else datetime.datetime.now(datetime.UTC)
        return now.astimezone(datetime.UTC)

    async def check_in(
        self,
        tenant_id: uuid.UUID,
        *,
        name: str,
        raw_phone: str,
        visit_type: str,
        marketing_opt_in: bool,
    ) -> TicketView:
        """Validate the shape, normalise the phone, spend the tenant's budget,
        write one row, count her place.

        The budget is RECORDED before the write, unlike booking-create, which
        defers until the OTP proof succeeds. The difference is the whole reason:
        booking-create defers because an anonymous caller could otherwise drain
        a tenant's budget with garbage verification tokens. F33 has no proof to
        fail — every well-formed check-in is a write, so metering the attempt IS
        metering the write. It happens after shape validation so a blank-name
        400 does not burn a real customer's allowance.
        """
        validate_checkin_request(name=name, visit_type=visit_type)
        phone = normalize_israeli_mobile(raw_phone)

        # Keyed on the TENANT — an operational fact about the boutique, which is
        # the only key the codebase permits to answer 429 on an anonymous
        # surface. A phone-keyed budget would answer "is this number here" to
        # anyone who submits it, which is the oracle this feature closed.
        tenant_key = f"checkin:{tenant_id}"
        if self._create_limiter.is_blocked(tenant_key):
            raise CheckinThrottledError
        self._create_limiter.record_failure(tenant_key)

        # One clock read, not two: `queue_day` and the consent stamp must come
        # from the same instant or a create at 00:00:00 Jerusalem could stamp
        # one on either side of the boundary.
        now = self._now()
        async with tenant_session(self._session_factory, tenant_id) as session:
            ticket = await self._tickets.insert(
                session,
                tenant_id=tenant_id,
                queue_day=today_jerusalem(lambda: now),
                name=name,
                phone=phone,
                visit_type=visit_type,
                # A submission record, NOT a consent record: this form has no
                # possession proof of any kind, so the row evidences that
                # someone typed a number. F20 is the only place a verified
                # phone is in hand, and it owns the promotion.
                marketing_opt_in_at=now if marketing_opt_in else None,
            )
            return _view(ticket, await self._tickets.position(session, tenant_id, ticket))

    async def position(self, tenant_id: uuid.UUID, ticket_id: uuid.UUID) -> TicketView:
        """The per-ticket budget is charged on every read, hit or miss. The
        per-tenant brake is consulted and charged on a MISS ONLY.

        That asymmetry is the whole point. `is_blocked` fires on a repeated KEY,
        and the ticket key comes from the caller's own body — a walk of fresh
        random UUIDs never repeats one, so the per-ticket budget cannot bound
        it. Charging the tenant on every read instead meant one host at 50 rps
        denied every real bride her position page. Now a flood of guessed ids
        denies only reads that no legitimate client makes, while a hit on a live
        ticket rides its own 30/60s and never touches the brake.

        Charging the per-ticket budget on a miss too is deliberate: it is what
        bounds a walk that hammers ONE guessed id, which the miss brake alone
        would let through at its own rate. Two keys, two shapes of walk.
        """
        ticket_key = f"checkin:position:{tenant_id}:{ticket_id}"
        if self._position_ticket_limiter.is_blocked(ticket_key):
            raise CheckinThrottledError
        self._position_ticket_limiter.record_failure(ticket_key)

        async with tenant_session(self._session_factory, tenant_id) as session:
            ticket = await self._tickets.by_id(session, tenant_id, ticket_id)
            if ticket is None:
                miss_key = f"checkin:position:miss:{tenant_id}"
                if self._position_miss_limiter.is_blocked(miss_key):
                    # A spent brake turns this 404 into a 429, which defers the
                    # client's terminal by up to one window rather than lying to
                    # it. Wasteful, never wrong; answering 404 regardless would
                    # make the brake bound nothing.
                    raise CheckinThrottledError
                self._position_miss_limiter.record_failure(miss_key)
                raise QueueTicketNotFoundError
            return _view(ticket, await self._tickets.position(session, tenant_id, ticket))

    async def board(self, tenant_id: uuid.UUID) -> QueueBoardView:
        """Today's waiting queue, capped, first names only, for a television on
        a boutique wall. Anonymous, so every field is a disclosure decision.

        Its own budget, and the fourth instance rather than a second key on one
        of the three above — the module docstring works the create-limiter
        arithmetic. Charged on every read including an empty board: the cost is
        the query, not the rows.

        There is no miss branch and there must not be one. Every resolvable
        tenant has a board; an empty queue is an empty board, always 200, one
        shape, no branch.

        One clock read and it happens on the SERVER, so the request carries no
        date and the board empties at midnight Jerusalem with no client-side
        date logic at all — on a screen that is expected to be mounted for
        months.
        """
        board_key = f"queue:board:{tenant_id}"
        if self._board_limiter.is_blocked(board_key):
            raise CheckinThrottledError
        self._board_limiter.record_failure(board_key)

        now = self._now()
        async with tenant_session(self._session_factory, tenant_id) as session:
            rows, waiting_total = await self._tickets.board(
                session,
                tenant_id,
                today_jerusalem(lambda: now),
                limit=BOARD_ROW_LIMIT,
            )
            return QueueBoardView(
                entries=[
                    QueueBoardEntry(
                        # The SERVER numbers the rows. A client free to renumber
                        # would be free to disagree with her phone.
                        position=index + 1,
                        first_name=board_display_name(row.name),
                        # The wall needs WHETHER, not WHEN.
                        called=row.called_at is not None,
                    )
                    for index, row in enumerate(rows)
                ],
                waiting_total=waiting_total,
            )


def _view(ticket: QueueTicket, position: int | None) -> TicketView:
    return TicketView(
        id=ticket.id, status=ticket.status, position=position, called_at=ticket.called_at
    )
