"""The floor read, the two break writers, the room registry, the claim and its
dress bindings, and the two one-shot pickers.

**The TARGET-DEPENDENT half of the authorization rule lives HERE, not on the
router.** The router's gate answers "may this role open the floor at all" — all
five, because the payload carries the minimum customer datum required by the
person standing on the floor (at most one name per occupied room, never the
day's customer book). This answers "may this person toggle, claim for, or
release THAT person", which no `RoleGate` can express because it depends on the
target:

    owner, shift_manager -> anybody
    reception, sales_assistant, seamstress -> herself, and nobody else

⚠ **The handover's rule is NOT here, and its absence is deliberate** — it is a
pure role predicate, so it is the ROUTE's gate. Splitting the two by whether the
predicate reads the target is the rule; see `handover`'s own docstring.

**The check is each method's first statement and it runs before the session is
opened.** That ordering is the security property, not a style choice: a 403
raised after a read is an existence oracle, and a non-elevated staffer could
enumerate the tenant's staff ids by which error came back.
`test_floor_service.py` asserts the repository was never called, which is the
only way to state it.

**No rate limiter and no advisory lock.** The break writers are idempotent by
predicate and touch one column on one row (see `StaffUsersRepository`); the
claim's atomicity is a partial unique index rather than a lock (D3), and no
`/manage` router carries a limiter.
"""

import dataclasses
import datetime
from collections import Counter
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.dependencies import NotAuthorizedError
from app.auth.service import StaffContext
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.dress_variants import DressVariantsRepository
from app.db.repositories.dresses import DressesRepository
from app.db.repositories.fitting_assignment_dresses import FittingAssignmentDressesRepository
from app.db.repositories.fitting_room_assignments import (
    ROOM_ACTIVE_INDEX,
    STAFF_ACTIVE_INDEX,
    FittingRoomAssignmentsRepository,
    violated_index,
)
from app.db.repositories.fitting_rooms import FittingRoomsRepository, RoomRow
from app.db.repositories.queue_tickets import WAITLIST_LIMIT, QueueTicketsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.floor.validation import (
    QueueEmptyError,
    QueueTicketChangedError,
    QueueTicketNotWaitingError,
    RoomOccupiedError,
    StaffOccupiedError,
    normalize_room_label,
)
from app.models.booking import Booking
from app.models.constants import (
    AuditAction,
    BookingStatus,
    QueueTicketStatus,
    StaffCardStatus,
    StaffRole,
)
from app.models.dress import Dress
from app.models.fitting_assignment_dress import FittingAssignmentDress
from app.models.staff_user import StaffUser
from app.queue.validation import QueueTicketNotFoundError
from app.storefront.validation import BOUTIQUE_TIMEZONE, today_jerusalem

# Frozen as a module constant so the membership test reads as the rule it is.
# Spelled from the enum rather than as literals: a sixth role added to
# StaffRole is NOT elevated by default, which is the safe direction to fail.
ELEVATED_ROLES = frozenset({StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value})

# D16's two one-shot pickers. BOUNDS, not page sizes: neither list paginates and
# neither is on the poll, so the number is "more than any boutique has" rather
# than "one screenful". `truncated` is the honesty the UI renders in the one case
# a bound bites — F34's precedent, whose comment is the argument: a hidden bride
# is the one failure a board may not have.
DRESS_PICKER_LIMIT = 500
CLIENT_PICKER_LIMIT = 200


def card_status(row: StaffUser, *, occupied: bool) -> StaffCardStatus:
    """Derived on read, never stored (D2 adds no status column).

    ⚠ **`occupied` BEATS `break`, and the order of these two branches is the
    decision.** She is standing in a fitting room with a client; the break is a
    stale toggle nobody cleared, and telling a shift manager looking for help
    that the person she can see in room 2 is «בהפסקה» is the screen lying about
    something visible. `break_started_at` stays on the wire regardless, so a card
    can still say she forgot to end one.
    """
    if occupied:
        return StaffCardStatus.OCCUPIED
    if row.break_started_at is not None:
        return StaffCardStatus.BREAK
    return StaffCardStatus.AVAILABLE


@dataclasses.dataclass(frozen=True)
class RoomRead:
    """One tile and its gowns — what every mutation answers.

    Frozen and flat so `Room.from_row` stays a pure renderer: the schema module
    never grows a query, and the mutation's answer is the SAME shape the
    payload's `rooms[]` elements carry, so the panel patches one tile in place
    from the server's own row and cannot disagree with itself.
    """

    row: RoomRow
    bindings: list[FittingAssignmentDress]


@dataclasses.dataclass(frozen=True)
class WaitlistEntryRead:
    """One waiting walk-in, already reduced to what the wire may carry.

    ⚠ **There is no `phone` field and that is the design.** The repository's
    projection selects the number because D9's duplicate flag groups on it; the
    flag is computed in the service and the number stops here, so no renderer
    downstream has one to leak by accident. `duplicate` is the whole of what
    survives that grouping.

    `arrived_at` is `created_at` and never the sort key: a skip moves the
    ordering key, so sending it would reset the panel's rendered clock to zero
    and say «הגיעה זה עתה» about a woman who has been standing there forty
    minutes. `called` is a BOOLEAN, not the instant — the panel needs to know
    WHETHER, and the timestamp would let anyone with the screen time how long a
    named woman has been standing at a counter.
    """

    id: UUID
    name: str
    visit_type: str
    arrived_at: datetime.datetime
    called: bool
    skip_count: int
    duplicate: bool


@dataclasses.dataclass(frozen=True)
class WaitlistRead:
    """The panel's list plus F36's `truncated` honesty, verbatim: the UI renders
    one line saying the list is partial and names NO count and NO limit, because
    both are the server's to change without a copy edit.

    ⚠ `truncated: True` also means the duplicate flag is BEST-EFFORT on that
    payload — a pair straddling the bound has one twin invisible, so the other
    renders clean. Accepted, because the bound bites only inside a griefing flood
    and a flag that lies by omission on row 40 of a 40-row list would be the real
    problem.
    """

    entries: list[WaitlistEntryRead]
    truncated: bool


@dataclasses.dataclass(frozen=True)
class DispatchRead:
    """What the two dispatch verbs answer: the tile that changed AND the queue it
    changed it from.

    One round trip rather than two, and it is not an economy — the panel and the
    tile are two halves of one act, and a client that patched the tile from the
    response but waited up to five seconds for the row to leave the list would
    render the same woman as both in-service and waiting.
    """

    room: "RoomRead"
    waitlist: WaitlistRead


@dataclasses.dataclass(frozen=True)
class FloorRead:
    """The whole payload's data, pre-joined, so `FloorResponse.from_rows` renders
    and does not query.

    `occupancy_by_staff_id` is DERIVED from `room_rows` rather than read
    separately — the rooms join already carries every occupied staffer, and a
    second statement for the same fact is how the two derivations start to
    disagree.

    `server_now` rides the envelope because the console computes «כבר 42 דק'»
    against it: a server-computed minute count is stale the instant it is
    serialised, and a device-clock one is wrong by however far a boutique
    tablet has drifted.
    """

    staff_rows: list[StaffUser]
    occupancy_by_staff_id: dict[UUID, RoomRow]
    room_rows: list[RoomRow]
    bindings_by_assignment_id: dict[UUID, list[FittingAssignmentDress]]
    server_now: datetime.datetime
    waitlist: WaitlistRead


@dataclasses.dataclass(frozen=True)
class DressPickerRead:
    """The dress picker's two statements, pre-joined, so `FloorDressList` renders
    and does not query. `sizes_by_dress_id` is sparse — a gown with no live
    variants is ordinary and binds with a null size."""

    dresses: list[Dress]
    sizes_by_dress_id: dict[UUID, list[str]]
    truncated: bool


@dataclasses.dataclass(frozen=True)
class ClientPickerRead:
    """The client picker's two statements, same shape.

    The name is keyed by CUSTOMER id and looked up per booking rather than
    snapshotted, so an erased customer renders an anonymous row here for exactly
    the same reason she renders an anonymous visit on the payload — one rule, two
    surfaces.
    """

    bookings: list[Booking]
    names_by_customer_id: dict[UUID, str]
    truncated: bool


class FloorService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime.datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._staff = StaffUsersRepository()
        self._audit = AuditLogRepository()
        self._rooms = FittingRoomsRepository()
        self._assignments = FittingRoomAssignmentsRepository()
        self._dress_bindings = FittingAssignmentDressesRepository()
        self._bookings = BookingsRepository()
        self._dresses = DressesRepository()
        self._variants = DressVariantsRepository()
        self._customers = CustomersRepository()
        self._tickets = QueueTicketsRepository()
        self._clock = clock or (lambda: datetime.datetime.now(datetime.UTC))

    async def floor(self, tenant_id: UUID) -> FloorRead:
        """Every live staffer, `created_at` ASC so the founding owner is first
        and the cards do not shuffle between ticks — plus every live room and
        the gowns in the occupied ones.

        No per-role projection: all five roles see the same payload.

        ⚠ **What this payload carries changed in F36, changed again in F58, and
        the sentence that used to stand here has now been false twice.** It first
        claimed this read carried none of a customer's data at all; F36's
        rewrite then said "at most one name per occupied room", and F58 puts up
        to a hundred more on it. The rule as it actually is:

        **The floor payload carries the minimum customer datum required by the
        person standing on the floor — the people who are physically in the
        boutique right now: one name per occupied fitting room, plus the name of
        every walk-in currently waiting to be served, and never the day's booking
        book.** Every name leaves the payload the moment she does — a released
        fitting, a served ticket, a skipped-out ticket, a removed ticket, or
        midnight Jerusalem. Nothing on it carries a phone, an email, an address
        or a consent flag.

        ⚠ **It DOES carry each waiting ticket's id, and that id is F33's
        position-page capability.** This payload is the only server path other
        than the check-in response that emits one, so it is disclosed to a
        signed-in staffer of this tenant and to nobody else — and **the console
        must never render it as a link to `/q/{id}`.**

        Every one of those names is resolved on every read from the live rows
        rather than snapshotted, which is what makes a retention sweep or an
        erasure render an anonymous visit instead of quietly preserving a name in
        a table nobody thought of.

        FOUR extra statements on the tick's EXISTING session — the rooms join,
        the bindings, the waitlist and D9's in-service phone projection — with no
        second `tenant_session`, no second pool checkout and no second
        `tenants.by_slug`. The bindings read is skipped entirely when nothing is
        occupied, because an empty boutique polls every five seconds and must not
        pay for it; the waitlist's two are NOT skippable, because an empty queue
        is the common case and «אין ממתינות בתור» is the answer the panel exists
        to give.
        """
        async with tenant_session(self._sessions, tenant_id) as session:
            staff_rows = await self._staff.list_live(session, tenant_id)
            room_rows = await self._rooms.list_with_occupancy(session, tenant_id)
            bindings = await self._dress_bindings.by_assignment_ids(
                session,
                tenant_id,
                [row.assignment_id for row in room_rows if row.assignment_id is not None],
            )
            waitlist = await self._waitlist(session, tenant_id)
        return FloorRead(
            staff_rows=staff_rows,
            occupancy_by_staff_id={
                row.staff_user_id: row for row in room_rows if row.staff_user_id is not None
            },
            room_rows=room_rows,
            bindings_by_assignment_id=bindings,
            server_now=self._clock(),
            waitlist=waitlist,
        )

    async def _waitlist(self, session: AsyncSession, tenant_id: UUID) -> WaitlistRead:
        """D2's read plus D9's flag, on the session the caller already holds.

        TWO statements, and the second one is the whole of why the flag is worth
        having. `_live_waiting()` cannot be reused for it — its third predicate is
        `status == 'waiting'` and the case that matters most is the twin who is
        already IN a room: she re-scanned, was dispatched on the first ticket,
        and the second is still waiting with nothing marking it. A manager with
        two «נועה»s and neither flagged removes one by inference, and a removal
        has no undo.

        ⚠ **The phone stops HERE.** It is selected for this grouping and turned
        into a boolean in this function; `WaitlistEntryRead` has no field to
        carry it and no renderer downstream has one to leak.

        ⚠ **`day` is TODAY**, and that is the opposite of `position()`'s binding
        for a stated reason: `position()` has a ticket in hand and binding it to
        today would tell a woman who walked out yesterday that she is next, while
        the panel has no ticket and yesterday's ghosts must not sit above this
        morning's first arrival. The consequence is real and F20's sweep owns it:
        an unclosed ticket from an earlier day is invisible here and therefore
        unremovable from this panel.
        """
        day = self._today()
        rows = await self._tickets.waiting_for_panel(session, tenant_id, day, limit=WAITLIST_LIMIT)
        in_service = await self._tickets.in_service_phones(session, tenant_id, day)
        waiting_counts = Counter(row.phone for row in rows)
        return WaitlistRead(
            entries=[
                WaitlistEntryRead(
                    id=row.id,
                    name=row.name,
                    visit_type=row.visit_type,
                    arrived_at=row.created_at,
                    called=row.called_at is not None,
                    skip_count=row.skip_count,
                    duplicate=waiting_counts[row.phone] > 1 or row.phone in in_service,
                )
                for row in rows
            ],
            truncated=len(rows) == WAITLIST_LIMIT,
        )

    async def start_break(
        self, tenant_id: UUID, staff_id: UUID, *, actor: StaffContext
    ) -> tuple[StaffUser, RoomRow | None]:
        self._authorize(staff_id, actor)
        at = self._clock()
        async with tenant_session(self._sessions, tenant_id) as session:
            wrote, row = await self._staff.start_break(session, tenant_id, staff_id, at=at)
            if row is None:
                raise DomainNotFoundError("staff_user")
            if wrote:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.STAFF_BREAK_STARTED,
                    actor_id=actor.id,
                    entity=str(staff_id),
                    # `row.break_started_at`, not `at`: on the winning write they
                    # are equal, and reading it off the row keeps this honest if
                    # the writer ever stops taking the caller's clock.
                    details={
                        "target": str(staff_id),
                        "break_started_at": _isoformat(row.break_started_at),
                    },
                )
            # ⚠ NOT `occupied=False`. This route answers a FULL card, and if that
            # staffer is standing in a fitting room the card must say so — "pass
            # False, it's just the break route" is the shortcut that ships a card
            # contradicting the panel it lands in five seconds later. One indexed
            # lookup on a path that already holds a session.
            return row, await self._rooms.occupancy_for_staff(session, tenant_id, staff_id)

    async def end_break(
        self, tenant_id: UUID, staff_id: UUID, *, actor: StaffContext
    ) -> tuple[StaffUser, RoomRow | None]:
        self._authorize(staff_id, actor)
        async with tenant_session(self._sessions, tenant_id) as session:
            # ⚠ CAPTURED BEFORE THE WRITE, into a local, and that is not style.
            # `end_break`'s UPDATE is ORM-enabled DML whose `evaluate`
            # synchronization stamps `break_started_at = NULL` onto this very
            # instance — `before` and the row the writer returns are the SAME
            # object out of one identity map — so reading it afterwards records
            # `null` and empties the trail this row exists for. The identical
            # trap on `from_status` is written up at `booking/owner.py:326-333`.
            before = await self._staff.by_id(session, tenant_id, staff_id)
            previous = before.break_started_at if before is not None else None

            wrote, row = await self._staff.end_break(session, tenant_id, staff_id)
            if row is None:
                raise DomainNotFoundError("staff_user")
            if wrote:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.STAFF_BREAK_ENDED,
                    actor_id=actor.id,
                    entity=str(staff_id),
                    # Ending a break destroys the only copy of when it began and
                    # there is no history table (D2), so this is the whole
                    # informational content of the row.
                    details={
                        "target": str(staff_id),
                        "previous_break_started_at": _isoformat(previous),
                    },
                )
            return row, await self._rooms.occupancy_for_staff(session, tenant_id, staff_id)

    # --- F36: the claim, the release, the handover ----------------------------

    async def claim(
        self,
        tenant_id: UUID,
        room_id: UUID,
        *,
        staff_user_id: UUID | None,
        booking_id: UUID | None,
        actor: StaffContext,
    ) -> RoomRead:
        """ONE INSERT, and the absence of a lock is the design (see
        `FittingRoomAssignmentsRepository.claim`).

        Ordered exactly, and every step is load-bearing:

        1. **Authorize, before any read.** `staff_user_id` defaults to the
           caller. ⚠ This is the FIRST body in the product to carry a target
           staff id, the shape `_authorize`'s own docstring names as the hazard:
           the field is read ONLY as the target and passed straight into
           `_authorize`; the acting identity is the `StaffContext` from the
           session cookie and no path here may read the body as one. Running it
           after the room read would make the 403 an existence oracle.
        2. **Read the room `FOR UPDATE`** — the claim's half of the per-room lock
           that keeps a concurrent delete from soft-deleting an occupied room.
           Missing, deleted, INACTIVE or another tenant's is one indistinguishable
           404: the panel renders no claim control on an inactive room, so
           reaching that branch means the client was one tick stale.
        3. **Read the booking** if given, under the check-in predicate.
        4. **SAVEPOINT, then the INSERT.** The `try` is OUTSIDE the `async with`
           and the write is a Core execute, so the `IntegrityError` surfaces
           where this `except` can see it.
        5. Audit in the same transaction, before commit.
        6. Answer the full room RENDERED FROM THE DATABASE, never from the
           request — which is why the panel is not optimistic.
        """
        target_staff_id = staff_user_id or actor.id
        self._authorize(target_staff_id, actor)
        async with tenant_session(self._sessions, tenant_id) as session:
            room = await self._rooms.by_id_for_update(session, tenant_id, room_id)
            if room is None or not room.is_active:
                raise DomainNotFoundError("fitting_room")
            if booking_id is not None:
                booking = await self._bookings.by_id(session, tenant_id, booking_id)
                if booking is None or not self._is_claimable(booking):
                    raise DomainNotFoundError("booking")
            try:
                # ⚠ The SAVEPOINT is not a lock in disguise. A failed flush aborts
                # the enclosing Postgres transaction, and this method MUST recover:
                # the 409 has to name the current occupant, and the occupant can
                # only be read after the conflict is known. `begin_nested()` rolls
                # back to the savepoint and leaves the outer transaction alive, so
                # that read happens in the same session, the same tenant context
                # and the same round-trip budget. It serialises nothing.
                async with session.begin_nested():
                    assignment = await self._assignments.claim(
                        session,
                        tenant_id,
                        room_id=room_id,
                        staff_id=target_staff_id,
                        booking_id=booking_id,
                    )
            except IntegrityError as error:
                return await self._resolve_claim_conflict(
                    session, tenant_id, room_id, target_staff_id, error
                )
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.FITTING_ROOM_CLAIMED,
                actor_id=actor.id,
                entity=str(room_id),
                details={
                    "room": str(room_id),
                    "assignment": str(assignment.id),
                    "staff": str(target_staff_id),
                    "booking": str(booking_id) if booking_id is not None else None,
                },
            )
            return await self._room_read(session, tenant_id, room_id)

    async def _resolve_claim_conflict(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        room_id: UUID,
        target_staff_id: UUID,
        error: IntegrityError,
    ) -> RoomRead:
        """⚠ **IDEMPOTENCE IS RESOLVED FIRST, AND IT IS KEYED ON THE REQUEST —
        NEVER ON THE CONSTRAINT NAME.**

        A staffer re-claiming the room she already holds violates BOTH partial
        unique indexes at once, and Postgres reports only the first that fails,
        in `RelationGetIndexList` order — i.e. index OID, i.e. migration creation
        order. Deriving this branch from the name would make it an artefact of
        that ordering and would flip silently after any `REINDEX CONCURRENTLY` or
        `pg_repack`. If the staff index reported first, a staffer tapping the room
        she is standing in would read «היא כבר בחדר 2.» — the screen refusing her
        with the name of the room she is in.

        So: one read keyed on `(tenant_id, room_id, target_staff_id)`. A hit is a
        200 with that card and NO audit row — nothing changed. Only on a miss does
        the constraint name pick between the two 409s, and an UNRECOGNISED name
        RE-RAISES: a 500 on a violation nobody predicted is correct, and silently
        mapping it to ROOM_OCCUPIED would tell a staffer a lie about furniture.
        """
        existing = await self._assignments.active_for(session, tenant_id, room_id, target_staff_id)
        if existing is not None:
            return await self._room_read(session, tenant_id, room_id)
        constraint = violated_index(error)
        if constraint == ROOM_ACTIVE_INDEX:
            occupant = await self._assignments.occupant_of_room(session, tenant_id, room_id)
            raise RoomOccupiedError(
                await self._occupant_details(session, tenant_id, occupant)
            ) from error
        if constraint == STAFF_ACTIVE_INDEX:
            raise StaffOccupiedError(
                await self._held_room_details(session, tenant_id, target_staff_id)
            ) from error
        raise error

    async def take_next(
        self, tenant_id: UUID, room_id: UUID, *, staff_user_id: UUID | None, actor: StaffContext
    ) -> DispatchRead:
        """The head of today's queue into this room, in ONE transaction (D3).

        ⚠ **NOTHING INSIDE THE `async with` MAY `return` AFTER THE TICKET UPDATE
        HAS RUN, AND EVERY REFUSAL RAISES.** `db/tenant.py:25` is
        `async with session_factory() as session, session.begin():`, so an
        exception propagating out of that block ROLLS BACK and a `return` from
        inside it COMMITS. That is the whole guarantee, and it is narrower than
        the one an earlier draft of the spec named: a raised 409 rolls the ticket
        write back with or without a savepoint, so the savepoint is not what
        protects the customer — the absence of a `return` is.

        What a `return` would cost, concretely: the ticket UPDATE has run, the
        INSERT failed, the block returns, `tenant_session` commits — and the
        woman is `in_service` with no room. Gone from the waitlist, gone from the
        public board, on no tile, her own phone reading «התור שלך התחיל» for the
        rest of the day, recoverable only with psql. No verb in this feature can
        reach that state to undo it.

        **There is NO savepoint and NO idempotence branch**, and both absences
        are the design rather than an economy. No savepoint because nothing after
        the conflict needs the transaction alive — the occupant read moves to a
        second, short, read-only session paid only on a refusal — so the `try`
        wraps the `async with` ITSELF. No idempotence branch because the
        transaction that would have made a 200 true is gone: every
        `IntegrityError` out of here is a refusal, and answering 200 would report
        a dispatch that claimed nobody while consuming the head of the queue.
        That is the exact inverse of `claim`, where a re-claim IS a true 200.

        Ordered exactly:

        1. **Authorize, before any read** — a 403 raised after a read is an
           existence oracle (module docstring).
        2. **Room `FOR UPDATE`**, then **2b: the occupant read** — a FAST PATH,
           not the guarantee. `has_active_for_room`'s shipped docstring is the
           authority for why a read issued after that lock sees the committed
           claim; `occupant_of_room` is the same predicate returning the row the
           409 needs anyway, so it is one read and not two. Without 2b the
           feature's most likely collision (two managers on one free tile inside
           one 5s tick) claims a real customer's ticket and throws it away, and a
           third take-next SKIP-LOCKs past her — out-of-order service
           MANUFACTURED by the design rather than forced by it.
        3. The ticket, 4. the empty-queue refusal, 5. the INSERT (which RAISES),
           6. the audit row IN THE SAME TRANSACTION so a lost race cannot leave a
           trail claiming a dispatch that did not happen, 7. the room read.

        The answer is the tile AND the queue, because they are two halves of one
        act: a client that patched the tile from this response but waited up to
        five seconds for the row to leave the list would render the same woman as
        both in-service and waiting.
        """
        target_staff_id = staff_user_id or actor.id
        self._authorize(target_staff_id, actor)
        try:
            async with tenant_session(self._sessions, tenant_id) as session:
                room = await self._rooms.by_id_for_update(session, tenant_id, room_id)
                if room is None or not room.is_active:
                    raise DomainNotFoundError("fitting_room")
                occupant = await self._assignments.occupant_of_room(session, tenant_id, room_id)
                if occupant is not None:
                    raise RoomOccupiedError(
                        await self._occupant_details(session, tenant_id, occupant)
                    )
                ticket = await self._tickets.claim_next(session, tenant_id, day=self._today())
                if ticket is None:
                    raise QueueEmptyError
                assignment = await self._assignments.claim(
                    session,
                    tenant_id,
                    room_id=room_id,
                    staff_id=target_staff_id,
                    booking_id=None,
                    queue_ticket_id=ticket.id,
                )
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.QUEUE_TICKET_DISPATCHED,
                    actor_id=actor.id,
                    entity=str(ticket.id),
                    details={
                        "ticket": str(ticket.id),
                        "room": str(room_id),
                        "assignment": str(assignment.id),
                        "staff": str(target_staff_id),
                        "mode": "take_next",
                    },
                )
                return await self._dispatch_read(session, tenant_id, room_id)
        except IntegrityError as error:
            # ⚠ THE TRANSACTION IS ALREADY GONE — the exception left the
            # `async with`, which rolled it back. The ticket is `waiting` again
            # at its original position (`requeued_at` was never touched) and no
            # audit row was written.
            raise await self._occupied_error(tenant_id, room_id, target_staff_id, error) from error

    async def _occupied_error(
        self, tenant_id: UUID, room_id: UUID, target_staff_id: UUID, error: IntegrityError
    ) -> Exception:
        """Returns the exception to raise; the caller does `raise ... from error`.

        ⚠ **NO IDEMPOTENCE BRANCH.** `active_for` is deliberately NOT consulted.
        On the dispatch verbs the ticket write is live and a `return` would
        commit it (see `take_next`), so the shipped analogue's FIRST branch
        (`_resolve_claim_conflict`, above) — correct there — strands a customer
        here. A dispatch that violated either index dispatched NOBODY and must
        refuse.

        ⚠ **The ROOM is resolved FIRST and WITHOUT the constraint name.** F36's
        rule applied to a case its own branch ORDER cannot cover: a write
        violating BOTH indexes reports whichever has the lower OID — migration
        creation order, which flips after any REINDEX CONCURRENTLY or pg_repack.
        Reading the occupant first makes the answer deterministic. (Step 2b
        already refuses the committed-occupant case before the INSERT, so this
        runs only for a winner that had not yet committed when 2b read — but it
        must still be right.)

        ⚠ **An UNRECOGNISED constraint RE-RAISES**, unchanged from F36: a 500 on
        a violation nobody predicted is correct, and silently mapping it to
        ROOM_OCCUPIED would tell a staffer a lie about furniture. This is why the
        helper RETURNS an exception rather than raising one — `return error` is
        how that branch is expressible at all.

        A SECOND `tenant_session`, and F36 was right to decline one for its claim
        ("another pool checkout, another set_config, another BEGIN/COMMIT and a
        second place for the tenant id to be wrong") — it had a savepoint
        available. Here the savepoint is not available and would not help, so the
        second checkout is the price of correctness and is paid only on a
        refusal. The tenant id is an argument, so there is no second place for it
        to be wrong.
        """
        async with tenant_session(self._sessions, tenant_id) as session:
            occupant = await self._assignments.occupant_of_room(session, tenant_id, room_id)
            if occupant is not None:
                return RoomOccupiedError(await self._occupant_details(session, tenant_id, occupant))
            held = await self._assignments.room_of_staff(session, tenant_id, target_staff_id)
            if held is not None:
                return StaffOccupiedError(
                    await self._held_room_details(session, tenant_id, target_staff_id)
                )
        # ⚠ MEMBERSHIP, not `is None`. The spec's D3a snippet writes
        # `if violated_index(error) is None: return error`, which is WEAKER than
        # the F36 rule the same docstring says it keeps: a violation carrying an
        # unrecognised NAME — any unique index a later feature adds to this
        # table — would fall through to ROOM_OCCUPIED, which is exactly the lie
        # about furniture F36 declined to tell. `not in (…)` covers both the
        # unnamed and the unknown-named case. Caught by the parametrised
        # re-raise test, which copies F36's shipped [None, "idx_something…"].
        if violated_index(error) not in (ROOM_ACTIVE_INDEX, STAFF_ACTIVE_INDEX):
            return error
        # A recognised violation with nobody left to name: the winner released in
        # the gap. «החדר נתפס זה עתה. נסי שוב.»
        return RoomOccupiedError(None)

    async def assign(
        self,
        tenant_id: UUID,
        room_id: UUID,
        *,
        queue_ticket_id: UUID,
        staff_user_id: UUID | None,
        actor: StaffContext,
    ) -> DispatchRead:
        """Push-assign: `take_next` with step 3 naming a ticket instead of
        draining the queue (D4).

        **Everything else is take-next's, deliberately and line for line** — the
        same `_authorize` before any read, the same room lock, the same step 2b,
        the same `try` around the whole `async with`, the same absence of a
        savepoint and the same absence of an idempotence branch. Read
        `take_next`'s docstring; every word of the ⚠ block applies here, and the
        stranded-customer failure it describes is reachable from this verb by
        exactly the same edit.

        ⚠ **`claim_next` MUST NOT be reachable from here.** A push-assign that
        quietly served the head of the queue would put a woman the manager was
        not looking at into the room she was.

        Rowcount 0 on the ticket is TWO answers and the read is where they are
        told apart — `status_of`, never `by_id` (D2).
        """
        target_staff_id = staff_user_id or actor.id
        self._authorize(target_staff_id, actor)
        try:
            async with tenant_session(self._sessions, tenant_id) as session:
                room = await self._rooms.by_id_for_update(session, tenant_id, room_id)
                if room is None or not room.is_active:
                    raise DomainNotFoundError("fitting_room")
                occupant = await self._assignments.occupant_of_room(session, tenant_id, room_id)
                if occupant is not None:
                    raise RoomOccupiedError(
                        await self._occupant_details(session, tenant_id, occupant)
                    )
                ticket = await self._tickets.claim_by_id(session, tenant_id, queue_ticket_id)
                if ticket is None:
                    # Unreachable third branch, and it stays a raise rather than a
                    # fall-through: this verb's predicate is `status_of`'s exactly
                    # and nothing in the product moves a ticket back to `waiting`,
                    # so a live waiting row here means two statements of one
                    # transaction disagreed. «רענני ונסי שוב» is the only honest
                    # remedy for that.
                    raise QueueTicketChangedError(
                        {
                            "skip_count": str(
                                await self._ticket_refusal(session, tenant_id, queue_ticket_id)
                            )
                        }
                    )
                assignment = await self._assignments.claim(
                    session,
                    tenant_id,
                    room_id=room_id,
                    staff_id=target_staff_id,
                    booking_id=None,
                    queue_ticket_id=ticket.id,
                )
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.QUEUE_TICKET_DISPATCHED,
                    actor_id=actor.id,
                    entity=str(ticket.id),
                    details={
                        "ticket": str(ticket.id),
                        "room": str(room_id),
                        "assignment": str(assignment.id),
                        "staff": str(target_staff_id),
                        "mode": "assign",
                    },
                )
                return await self._dispatch_read(session, tenant_id, room_id)
        except IntegrityError as error:
            raise await self._occupied_error(tenant_id, room_id, target_staff_id, error) from error

    async def call(self, tenant_id: UUID, ticket_id: UUID, *, actor: StaffContext) -> WaitlistRead:
        """The summons (D7). No `_authorize`: a call has no target STAFFER, so
        there is nothing for a self-or-elevated rule to compare, and the router's
        five-role gate is the whole check.

        ⚠ **ROWCOUNT 0 HAS THREE CAUSES HERE, NOT D4'S TWO, AND THE THIRD IS THE
        ORDINARY ONE.** The extra `called_at IS NULL` conjunct adds it: she is
        already called. That is a 200 with the current waitlist and NO audit row —
        she wanted her called and she is called, and a {called → called} entry
        would be noise in a trail this area has four rows in. A builder
        implementing D4's two-answer table literally falls through here with no
        branch at all, which is a silent no-op reported as success or a 500.
        """
        at = self._clock()
        async with tenant_session(self._sessions, tenant_id) as session:
            row = await self._tickets.call(session, tenant_id, ticket_id, now=at)
            if row is None:
                # Raises on the two shared causes; a return means she was already
                # called, which is the third.
                await self._ticket_refusal(session, tenant_id, ticket_id)
            else:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.QUEUE_TICKET_CALLED,
                    actor_id=actor.id,
                    entity=str(ticket_id),
                    # `row.called_at`, not `at`: on the winning write they are
                    # equal, and reading it off the statement keeps this honest if
                    # the writer ever stops taking the caller's clock.
                    details={"ticket": str(ticket_id), "called_at": _isoformat(row.called_at)},
                )
            return await self._waitlist(session, tenant_id)

    async def skip(
        self, tenant_id: UUID, ticket_id: UUID, *, seen_skip_count: int, actor: StaffContext
    ) -> WaitlistRead:
        """Skip-to-back, and the second skip removes (D6). `ELEVATED` at the
        route, so there is no target-dependent check to make here either.

        ⚠ **Rowcount 0 is THREE answers and the third one is what stops two
        ordinary single taps removing a customer.** The row is live and still
        `waiting`, so what failed is `skip_count = :seen_skip_count`: a colleague
        skipped her between this manager's render and her tap, and escalating on
        a count nobody saw would remove her with the confirm — gated on
        `skip_count >= 1` — never rendered on either device. 409
        `QUEUE_TICKET_CHANGED` carries the count the server actually holds; the
        next tick renders 1 and the next press correctly opens the confirm.

        The audit row's `status` is read off the statement's own RETURNING rather
        than re-derived in Python: the `CASE` is the authority on whether this
        press removed her.
        """
        at = self._clock()
        async with tenant_session(self._sessions, tenant_id) as session:
            row = await self._tickets.skip(
                session, tenant_id, ticket_id, now=at, seen_skip_count=seen_skip_count
            )
            if row is None:
                raise QueueTicketChangedError(
                    {"skip_count": str(await self._ticket_refusal(session, tenant_id, ticket_id))}
                )
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.QUEUE_TICKET_SKIPPED,
                actor_id=actor.id,
                entity=str(ticket_id),
                details={
                    "ticket": str(ticket_id),
                    "skip_count": row.skip_count,
                    "status": row.status,
                },
            )
            return await self._waitlist(session, tenant_id)

    async def remove(
        self, tenant_id: UUID, ticket_id: UUID, *, actor: StaffContext
    ) -> WaitlistRead:
        """The no-show and Ruling 3's duplicate, which are the same act (D8).

        Destructive with no undo, so the confirm in front of it and this row
        behind it are what the design carries instead of a restore verb — one
        more route, one more gate, one more audit value and one more control, to
        undo an act that already has a confirm in front of it.

        Rowcount 0 really does have only D4's two causes here: no `skip_count`
        conjunct and no `called_at` one.
        """
        async with tenant_session(self._sessions, tenant_id) as session:
            if not await self._tickets.remove(session, tenant_id, ticket_id):
                # See `assign`: the third branch is unreachable and the honest
                # answer to a state this table cannot produce is "reload".
                raise QueueTicketChangedError(
                    {"skip_count": str(await self._ticket_refusal(session, tenant_id, ticket_id))}
                )
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.QUEUE_TICKET_REMOVED,
                actor_id=actor.id,
                entity=str(ticket_id),
                details={"ticket": str(ticket_id)},
            )
            return await self._waitlist(session, tenant_id)

    async def _ticket_refusal(self, session: AsyncSession, tenant_id: UUID, ticket_id: UUID) -> int:
        """The rowcount-0 read, shared by the four verbs that can take one.

        It RAISES the two causes every one of them shares — gone (or swept, or
        another tenant's) is a 404; no longer `waiting` is a 409 naming the state
        — and RETURNS the live `skip_count` when the row is still waiting,
        because THAT fact means something different on each verb and is therefore
        the verb's to answer: a re-call on `call`, a stale count on `skip`, and
        an unreachable disagreement on `assign` and `remove`.

        ⚠ **`status_of` and never `by_id`.** The projection is what keeps a phone
        and a consent timestamp out of a session that is running ORM-enabled
        UPDATEs, and — measured, not assumed — an entity read here answers the
        PRE-skip count out of the identity map, so `skip` would refuse a caller
        who sent the value it had just been told.

        ⚠ **Nothing has been written when this runs.** Every caller reaches it on
        a rowcount of 0, so raising out of `tenant_session` rolls back a
        transaction that changed nothing — which is why these raises are safe
        where a `return` after the dispatch verbs' ticket write would not be.
        """
        found = await self._tickets.status_of(session, tenant_id, ticket_id)
        if found is None:
            raise QueueTicketNotFoundError
        status, skip_count = found
        if status != QueueTicketStatus.WAITING.value:
            raise QueueTicketNotWaitingError({"status": status})
        return skip_count

    async def release(
        self, tenant_id: UUID, assignment_id: UUID, *, actor: StaffContext
    ) -> RoomRead:
        """A conditional UPDATE, and **rowcount 0 is not an error**.

        ⚠ The two axes apply here too, but they CANNOT run first and the refusal
        is a **404, not a 403**. The target is an assignment id, and whose it is
        can only be learned by reading the row — so a 403 on a real id and a 404
        on a fake one would discriminate existence. Answering 404 costs no extra
        code path and keeps the two responses byte-identical.

        One consequence, stated rather than discovered: when the holder has been
        soft-deleted from `staff_users` since the claim, `staff_user_id` matches
        nobody, so only an elevated caller can clear the tile. That is the right
        answer and it is not a gap.
        """
        at = self._clock()
        async with tenant_session(self._sessions, tenant_id) as session:
            assignment = await self._assignments.by_id(session, tenant_id, assignment_id)
            if assignment is None or (
                assignment.staff_user_id != actor.id and actor.role not in ELEVATED_ROLES
            ):
                raise DomainNotFoundError("fitting_room_assignment")
            wrote, row = await self._assignments.release(session, tenant_id, assignment_id, at=at)
            if row is None:
                raise DomainNotFoundError("fitting_room_assignment")
            if wrote:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.FITTING_ROOM_RELEASED,
                    actor_id=actor.id,
                    entity=str(assignment_id),
                    details={
                        "room": str(row.fitting_room_id),
                        "assignment": str(assignment_id),
                        "staff": str(row.staff_user_id),
                    },
                )
            # `wrote is False` with a live row back means somebody already
            # released it. She wanted the room free and the room is free: 200,
            # rendered from the database, and no audit row — a
            # {released → released} entry would be noise in the only trail this
            # area has.
            return await self._room_read(session, tenant_id, row.fitting_room_id)

    async def handover(
        self, tenant_id: UUID, assignment_id: UUID, *, new_staff_id: UUID, actor: StaffContext
    ) -> RoomRead:
        """A guarded UPDATE of ONE column, which is why the dress bindings
        survive for free.

        ⚠ **No role check here: the ROUTE gate owns it**
        (`require_role(OWNER, SHIFT_MANAGER)`), and that asymmetry with the claim
        and the release is deliberate. Handover's predicate depends on nothing
        about the target, so it is a pure role predicate — precisely what
        `RoleGate` is. The other two are target-dependent (self OR elevated) and
        genuinely cannot live in a gate. Putting this one in the service instead
        would force `FLOOR_OPEN` to assert that a seamstress may reach a route she
        always gets a 403 on, and a 403 is TERMINAL for the whole floor screen —
        a rendered control that 403s blanks a seamstress's only screen.
        """
        async with tenant_session(self._sessions, tenant_id) as session:
            # ⚠ CAPTURED BEFORE THE WRITE, into a local, and that is not style:
            # the UPDATE is ORM-enabled DML whose `evaluate` synchronization
            # stamps the new value onto this very instance out of one identity
            # map, so reading it afterwards would record the NEW staffer as the
            # OLD one and empty the audit row of its whole informational content.
            before = await self._assignments.by_id(session, tenant_id, assignment_id)
            previous_staff_id = before.staff_user_id if before is not None else None
            try:
                async with session.begin_nested():
                    wrote, row = await self._assignments.handover(
                        session, tenant_id, assignment_id, new_staff_id=new_staff_id
                    )
            except IntegrityError as error:
                # The SECOND index earning its keep on a path that is not the
                # claim: handing a room to a colleague who already holds one.
                # There is no idempotence branch here — a handover to the current
                # holder violates nothing and simply rewrites the same value.
                if violated_index(error) == STAFF_ACTIVE_INDEX:
                    raise StaffOccupiedError(
                        await self._held_room_details(session, tenant_id, new_staff_id)
                    ) from error
                raise
            if not wrote or row is None:
                raise DomainNotFoundError("fitting_room_assignment")
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.FITTING_ROOM_HANDED_OVER,
                actor_id=actor.id,
                entity=str(assignment_id),
                details={
                    "assignment": str(assignment_id),
                    "from": str(previous_staff_id) if previous_staff_id is not None else None,
                    "to": str(new_staff_id),
                },
            )
            return await self._room_read(session, tenant_id, row.fitting_room_id)

    # --- F36: the dress bindings (D4) -----------------------------------------

    async def add_dress(
        self,
        tenant_id: UUID,
        assignment_id: UUID,
        *,
        dress_id: UUID,
        size_label: str | None,
        actor: StaffContext,
    ) -> RoomRead:
        """⚠ **No ownership check, and that is a recorded decision rather than an
        omission.** A colleague fetching a second gown for a fitting already in
        progress is the normal case on a shop floor, and binding a dress is not a
        destructive act on the HOLDER's room — release and handover take the room
        away from her, which is why those two carry the two axes and these two do
        not. `removed_by` is what keeps the permissiveness accountable.

        No audit row on either branch: the binding ROW is the record (D13), and a
        dozen actions per fitting would swamp the four that are not.
        """
        async with tenant_session(self._sessions, tenant_id) as session:
            assignment = await self._assignments.active_by_id(session, tenant_id, assignment_id)
            if assignment is None:
                raise DomainNotFoundError("fitting_room_assignment")
            dress = await self._dresses.by_id(session, tenant_id, dress_id)
            if dress is None:
                raise DomainNotFoundError("dress")
            # A concurrent double-add resolves to SUCCESS: both staffers wanted
            # the dress in the room and the dress is in the room. `dress_name` is
            # a SNAPSHOT — the owner may rename or archive a gown mid-fitting and
            # the card must render what actually went in.
            await self._dress_bindings.add(
                session,
                tenant_id,
                assignment_id=assignment_id,
                dress_id=dress_id,
                dress_name=dress.name,
                dress_size=size_label,
            )
            return await self._room_read(session, tenant_id, assignment.fitting_room_id)

    async def remove_dress(
        self, tenant_id: UUID, assignment_id: UUID, binding_id: UUID, *, actor: StaffContext
    ) -> RoomRead:
        """The soft delete plus `removed_by` IS the audit record, which is why no
        FITTING_DRESS_REMOVED action exists: the row survives and answers what
        left the room, when, and who took it out."""
        at = self._clock()
        async with tenant_session(self._sessions, tenant_id) as session:
            assignment = await self._assignments.active_by_id(session, tenant_id, assignment_id)
            if assignment is None:
                raise DomainNotFoundError("fitting_room_assignment")
            removed = await self._dress_bindings.remove(
                session,
                tenant_id,
                assignment_id=assignment_id,
                binding_id=binding_id,
                actor_id=actor.id,
                at=at,
            )
            if not removed:
                raise DomainNotFoundError("fitting_assignment_dress")
            return await self._room_read(session, tenant_id, assignment.fitting_room_id)

    # --- F36: the registry (D1) -----------------------------------------------

    async def create_room(
        self, tenant_id: UUID, *, label: str, sort_order: int, actor: StaffContext
    ) -> RoomRead:
        """No audit row: creating a room is non-destructive, visible on the
        screen that did it, and already timed by `created_at`."""
        normalized = normalize_room_label(label)
        async with tenant_session(self._sessions, tenant_id) as session:
            room = await self._rooms.insert(
                session, tenant_id, label=normalized, sort_order=sort_order
            )
            return await self._room_read(session, tenant_id, room.id)

    async def update_room(
        self,
        tenant_id: UUID,
        room_id: UUID,
        *,
        label: str | None,
        sort_order: int | None,
        is_active: bool | None,
        actor: StaffContext,
    ) -> RoomRead:
        """`None` means NOT SUPPLIED, so a reorder leaves the label alone.

        **Deactivating an OCCUPIED room is allowed** — that is the "the mirror
        just broke" case, and evicting a half-dressed bride to satisfy a flag
        would be the product being clever at her expense. `is_active` stops the
        NEXT claim, never the fitting in progress.
        """
        normalized = normalize_room_label(label) if label is not None else None
        async with tenant_session(self._sessions, tenant_id) as session:
            room = await self._rooms.update(
                session,
                tenant_id,
                room_id,
                label=normalized,
                sort_order=sort_order,
                is_active=is_active,
            )
            if room is None:
                raise DomainNotFoundError("fitting_room")
            return await self._room_read(session, tenant_id, room_id)

    async def delete_room(self, tenant_id: UUID, room_id: UUID, *, actor: StaffContext) -> None:
        """⚠ **Lock, THEN guard, THEN stamp — and the ordering is AC17.**

        This is the one hidden read-then-write in the feature: read occupancy,
        write `deleted_at`. That is a cross-row invariant, which is exactly the
        shape no unique index can express. Under READ COMMITTED the delete would
        see zero active assignments while a concurrent claim is uncommitted, both
        would commit, and the result is a soft-deleted room holding a live
        assignment — a row no read surfaces, so there is NO UI PATH TO RELEASE IT
        and the staffer's key stays in the staff index forever. Recovery needs
        psql.

        `by_id_for_update` takes the row lock; the occupancy guard is then a
        SEPARATE statement whose new snapshot, taken under the lock, sees the
        committed claim. Folding it into the UPDATE as a `NOT EXISTS` would be
        the unsafe count-against-a-snapshot shape — EvalPlanQual does not re-read
        other tables.
        """
        async with tenant_session(self._sessions, tenant_id) as session:
            room = await self._rooms.by_id_for_update(session, tenant_id, room_id)
            if room is None:
                raise DomainNotFoundError("fitting_room")
            # Captured before the stamp: the row is about to be soft-deleted and
            # its label may be re-typed onto a new room tomorrow, so an id alone
            # would record that something was removed and could not say what.
            label = room.label
            if await self._assignments.has_active_for_room(session, tenant_id, room_id):
                occupant = await self._assignments.occupant_of_room(session, tenant_id, room_id)
                raise RoomOccupiedError(await self._occupant_details(session, tenant_id, occupant))
            await self._rooms.soft_delete(session, tenant_id, room_id)
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.FITTING_ROOM_DELETED,
                actor_id=actor.id,
                entity=str(room_id),
                details={"room": str(room_id), "label": label},
            )

    # --- F36: the two one-shot pickers (D16) ----------------------------------

    async def dresses(self, tenant_id: UUID) -> DressPickerRead:
        """Fetched ONCE, when the dress dialog opens — never on the poll.

        This router answers it rather than the catalog's because `RoleGate`
        NARROWS ONLY: `catalog/router.py` admits owner and shift_manager and there
        is no per-route way to let a seamstress in, so widening that router is the
        only alternative and is exactly what the role-gating walker exists to
        prevent. What travels is a name and its size labels — strictly less than
        the boutique's own storefront already publishes to an anonymous visitor.
        """
        async with tenant_session(self._sessions, tenant_id) as session:
            rows = await self._dresses.list_for_picker(session, tenant_id, limit=DRESS_PICKER_LIMIT)
            sizes = await self._variants.size_labels_by_dress(
                session, tenant_id, [row.id for row in rows]
            )
        return DressPickerRead(
            dresses=rows,
            sizes_by_dress_id=sizes,
            truncated=len(rows) == DRESS_PICKER_LIMIT,
        )

    async def clients(self, tenant_id: UUID) -> ClientPickerRead:
        """⚠ **The only thing in the console that can supply a `booking_id`.**

        Without it `booking_id` is on the claim body with no producer: the three
        floor roles cannot reach `/manage/bookings` at all, so every claim they
        could make would be anonymous and the client label — the thing the feature
        exists for — would be null on the surface that matters.

        Today's JERUSALEM calendar day and `checked_in_at IS NOT NULL`, i.e. the
        people physically in the building. That predicate is the whole
        minimisation argument, and it is the same one the payload makes: this is
        the arrivals, never the day book.
        """
        start, end = self._today_window()
        async with tenant_session(self._sessions, tenant_id) as session:
            rows = await self._bookings.list_checked_in_between(
                session,
                tenant_id,
                from_instant=start,
                until_instant=end,
                limit=CLIENT_PICKER_LIMIT,
            )
            customers = await self._customers.by_ids(
                session, tenant_id, [row.customer_id for row in rows]
            )
        return ClientPickerRead(
            bookings=rows,
            names_by_customer_id={row.id: row.name for row in customers},
            truncated=len(rows) == CLIENT_PICKER_LIMIT,
        )

    # --- F36: shared helpers ---------------------------------------------------

    def _today(self) -> datetime.date:
        """Today's Jerusalem calendar day, and `_today_window()` calls it rather
        than re-deriving it — so the dispatch day and the client picker's window
        cannot drift apart, which is the argument `_today_window` already makes
        one level down."""
        return today_jerusalem(self._clock)

    def _today_window(self) -> tuple[datetime.datetime, datetime.datetime]:
        """Today's Jerusalem calendar day as a half-open UTC range.

        Written once because the claim's check-in predicate and the client picker
        must agree exactly: a booking the picker offers and the claim then refuses
        would be a control that does nothing, and two transcriptions of the same
        arithmetic are two chances for that.
        """
        today = self._today()
        return (
            datetime.datetime.combine(today, datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE),
            datetime.datetime.combine(
                today + datetime.timedelta(days=1), datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
            ),
        )

    async def _dispatch_read(
        self, session: AsyncSession, tenant_id: UUID, room_id: UUID
    ) -> DispatchRead:
        """What both dispatch verbs answer, on the session that made the write —
        so the tile and the queue are read from ONE committed state and cannot
        disagree about the woman who just moved between them."""
        return DispatchRead(
            room=await self._room_read(session, tenant_id, room_id),
            waitlist=await self._waitlist(session, tenant_id),
        )

    async def _room_read(self, session: AsyncSession, tenant_id: UUID, room_id: UUID) -> RoomRead:
        row = await self._rooms.room_with_occupancy(session, tenant_id, room_id)
        if row is None:
            raise DomainNotFoundError("fitting_room")
        bindings = await self._dress_bindings.by_assignment_ids(
            session, tenant_id, [row.assignment_id] if row.assignment_id is not None else []
        )
        return RoomRead(
            row=row,
            bindings=bindings.get(row.assignment_id, []) if row.assignment_id is not None else [],
        )

    async def _occupant_details(
        self, session: AsyncSession, tenant_id: UUID, occupant: object
    ) -> dict[str, str] | None:
        """`None` when there is nobody to name, and the key is then ABSENT from
        the body rather than null. The occupant can release between the index
        violation and this read; so can her staff row vanish."""
        staff_user_id = getattr(occupant, "staff_user_id", None)
        if staff_user_id is None:
            return None
        holder = await self._staff.by_id(session, tenant_id, staff_user_id)
        if holder is None:
            return None
        return {"staff_display_name": holder.display_name}

    async def _held_room_details(
        self, session: AsyncSession, tenant_id: UUID, staff_id: UUID
    ) -> dict[str, str] | None:
        held = await self._assignments.room_of_staff(session, tenant_id, staff_id)
        if held is None:
            return None
        room = await self._rooms.by_id(session, tenant_id, held.fitting_room_id)
        if room is None:
            return None
        return {"room_label": room.label}

    def _is_claimable(self, booking: Booking) -> bool:
        """⚠ **The check-in predicate is what makes the privacy argument TRUE
        rather than aspirational.**

        `deleted_at IS NULL AND status <> 'cancelled'` alone admits NEXT MONTH's
        booking, whose customer's name would then surface on a five-role payload
        for as long as the assignment stayed open. `checked_in_at IS NOT NULL`
        plus today's JERUSALEM calendar day is "she is physically in the
        building", which is the whole of the minimisation claim.

        `pending_payment` is admitted DELIBERATELY, and it is the one place this
        codebase's rule runs the other way: every owner and customer verb 409s on
        an unpaid hold, but the bride is standing in the boutique having been
        checked in, and refusing to name her on a room tile over a deposit is the
        product being clever at the expense of the person in front of it.
        """
        if booking.checked_in_at is None or booking.status == BookingStatus.CANCELLED.value:
            return False
        start, end = self._today_window()
        return start <= booking.starts_at < end

    @staticmethod
    def _authorize(staff_id: UUID, actor: StaffContext) -> None:
        """The acting identity is `StaffContext`, resolved from the session
        cookie by `get_current_staff`. It is NEVER read from the path, the query
        or a body: the request names only WHOM to toggle, never WHO is asking. A
        body-supplied `staff_user_id` doubling as the caller's identity is the
        one shape that turns "any staffer on herself" into "any staffer on
        anyone".

        Compares IDS. A display name or an email would be a mutable string two
        people can share.
        """
        if staff_id != actor.id and actor.role not in ELEVATED_ROLES:
            raise NotAuthorizedError


def _isoformat(value: datetime.datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
