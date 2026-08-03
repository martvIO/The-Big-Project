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
from collections.abc import Callable
from typing import NoReturn
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
from app.db.repositories.sessions import SessionsRepository
from app.db.repositories.sos_alerts import SosAlertRow, SosAlertsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.floor.validation import (
    RoomOccupiedError,
    SosAlreadyAcceptedError,
    SosClosedError,
    SosValidationError,
    StaffOccupiedError,
    normalize_room_label,
    normalize_sos_note,
)
from app.models.booking import Booking
from app.models.constants import (
    AuditAction,
    BookingStatus,
    SosStatus,
    StaffCardStatus,
    StaffRole,
)
from app.models.dress import Dress
from app.models.fitting_assignment_dress import FittingAssignmentDress
from app.models.sos_alert import SosAlert
from app.models.staff_user import StaffUser
from app.storefront.validation import BOUTIQUE_TIMEZONE, today_jerusalem

# Frozen as a module constant so the membership test reads as the rule it is.
# Spelled from the enum rather than as literals: a sixth role added to
# StaffRole is NOT elevated by default, which is the safe direction to fail.
ELEVATED_ROLES = frozenset({StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value})

# F37's two read-time thresholds, and THE WORKER IS REJECTED — recorded here
# because the alternative looks tempting and would be strictly worse:
#
#   * `app/worker.py` ticks at `worker_poll_interval_seconds`, DEFAULT 60, so a
#     worker-stamped `escalated_at` would arrive up to a full minute late — TWICE
#     the requirement — for a mechanism whose entire specification is thirty
#     seconds;
#   * it would introduce a WRITE THAT RACES a concurrent ack, two processes
#     touching one row for a value nothing durable needs;
#   * it would run O(tenants) queries per tick even when no boutique in the
#     country has an open alert.
#
# Derived on read it adds zero latency beyond the poll, cannot race anything
# because it writes nothing, and is the house compute-on-read pattern —
# `card_status()` directly below, F36's occupancy, F43's ordinals.
#
# Both numbers move with pilot evidence and neither needs a migration or a
# backfill to move: changing the constant changes every alert on the next tick.
ESCALATION_AFTER = datetime.timedelta(seconds=30)
# Two minutes because a responder walking the length of a boutique and resolving
# on arrival takes well under it, and because a raiser told «דנה מגיעה» will wait
# roughly that long before deciding nobody is coming.
STALLED_AFTER = datetime.timedelta(minutes=2)

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
class SosRead:
    """One alert as a console sees it: the joined row, plus the three booleans
    the SERVER derives so the rule exists once instead of twice.

    Put `for_me` in the console and the audience rule lives in two languages, and
    the day the escalation window moves one of them moves with it. Here it is
    pure branches over a `StaffContext` and a row — a matrix against fakes, with
    no database at all.
    """

    row: SosAlertRow
    escalated: bool
    stalled: bool
    for_me: bool

    @property
    def alert(self) -> SosAlert:
        return self.row.alert


@dataclasses.dataclass(frozen=True)
class SosListRead:
    """The poll's envelope. `server_now` is the instant BOTH derived booleans and
    the console's elapsed line are computed against — see `_escalated`."""

    alerts: list[SosRead]
    server_now: datetime.datetime


@dataclasses.dataclass(frozen=True)
class RaisedSos:
    """What the raise answers, and it is the ONE mutation in this feature whose
    answer is not just the row.

    ⚠ `rerouted` is a fact about THIS REQUEST, not about the row, which is why
    it cannot be inferred later: nobody reading the alert afterwards can know
    whether `target_staff_user_id IS NULL` means "she asked for the shift
    manager" or "she asked for Dana and Dana was logged out". The audit row keeps
    the pair; this flag is what lets the raiser be TOLD, on screen, in the moment
    it matters.

    *Declined: letting the console infer it by comparing what it sent with what
    came back — correct today, and exactly the kind of implicit contract that
    survives one refactor.*
    """

    sos: SosRead
    rerouted: bool


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
        self._sos = SosAlertsRepository()
        # F37's reachability probe, and the ONLY reader of it. Named
        # `_session_rows` because `self._sessions` is already the session
        # FACTORY on this class — two very different things one letter apart.
        self._session_rows = SessionsRepository()
        self._clock = clock or (lambda: datetime.datetime.now(datetime.UTC))

    async def floor(self, tenant_id: UUID) -> FloorRead:
        """Every live staffer, `created_at` ASC so the founding owner is first
        and the cards do not shuffle between ticks — plus every live room and
        the gowns in the occupied ones.

        No per-role projection: all five roles see the same payload.

        ⚠ **What this payload carries changed in F36, and the sentence that used
        to stand here is now false.** It claimed this read carried none of a
        customer's data at all, and therefore that no gate had to be widened over
        one — but the rooms, and `occupancy` on the staff cards, carry a client
        label. The rule as it actually is: **the floor payload carries the
        minimum customer datum required by the person standing on the floor — at
        most one name per occupied room, for the duration of the fitting, never
        the day's customer book.** A seamstress
        called to room 3 has to know who is in it; she does not have to know who
        else is booked today, and this read still cannot tell her.

        That label is resolved on every read from the live rows rather than
        snapshotted, which is what makes a retention sweep or an erasure render
        an anonymous visit instead of quietly preserving a name in a table
        nobody thought of.

        TWO extra statements on the tick's EXISTING session — no second
        `tenant_session`, no second pool checkout, no second `tenants.by_slug`.
        The bindings read is skipped entirely when nothing is occupied, because
        an empty boutique polls every five seconds and must not pay for it.
        """
        async with tenant_session(self._sessions, tenant_id) as session:
            staff_rows = await self._staff.list_live(session, tenant_id)
            room_rows = await self._rooms.list_with_occupancy(session, tenant_id)
            bindings = await self._dress_bindings.by_assignment_ids(
                session,
                tenant_id,
                [row.assignment_id for row in room_rows if row.assignment_id is not None],
            )
        return FloorRead(
            staff_rows=staff_rows,
            occupancy_by_staff_id={
                row.staff_user_id: row for row in room_rows if row.staff_user_id is not None
            },
            room_rows=room_rows,
            bindings_by_assignment_id=bindings,
            server_now=self._clock(),
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

    def _today_window(self) -> tuple[datetime.datetime, datetime.datetime]:
        """Today's Jerusalem calendar day as a half-open UTC range.

        Written once because the claim's check-in predicate and the client picker
        must agree exactly: a booking the picker offers and the claim then refuses
        would be a control that does nothing, and two transcriptions of the same
        arithmetic are two chances for that.
        """
        today = today_jerusalem(self._clock)
        return (
            datetime.datetime.combine(today, datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE),
            datetime.datetime.combine(
                today + datetime.timedelta(days=1), datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
            ),
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

    # --- F37: the SOS page ----------------------------------------------------

    async def sos(self, tenant_id: UUID, *, actor: StaffContext) -> SosListRead:
        """The app-level poll's whole payload: one statement, then three pure
        derivations per row against ONE `server_now`.

        ⚠ **The audience clause is built in Python and an elevated caller gets no
        extra predicate at all** — faster than binding a boolean into SQL, and
        clearer. `ELEVATED_ROLES` is this layer's decision; the repository takes
        an id and never a role.
        """
        server_now = self._clock()
        async with tenant_session(self._sessions, tenant_id) as session:
            rows = await self._sos.live_for(
                session,
                tenant_id,
                actor_id=None if actor.role in ELEVATED_ROLES else actor.id,
            )
        return SosListRead(
            alerts=[_sos_read(row, actor=actor, server_now=server_now) for row in rows],
            server_now=server_now,
        )

    async def raise_sos(
        self,
        tenant_id: UUID,
        *,
        target_staff_user_id: UUID | None,
        fitting_room_assignment_id: UUID | None,
        note: str | None,
        actor: StaffContext,
    ) -> RaisedSos:
        """One staffer asking for help, and it has exactly THREE failure modes:
        401 (no session), 403 (a role outside the five — unreachable for a
        signed-in staffer, since the router admits all five) and 400 (note too
        long, or self-target).

        ⚠ **NOTHING ABOUT THE STATE OF THE BOUTIQUE CAN REFUSE A PAGE.** Not a
        missing room, not a deleted room, not a released assignment, not a
        colleague who went home, not a colleague who does not exist, not an empty
        shift, not another alert already open. That sentence IS «a page is never
        silently dropped», and `test_nothing_about_the_boutique_can_refuse_a_page`
        walks it as a table.

        ⚠ **There is NO `_authorize` call here and its absence is the design.**
        `_authorize`'s docstring names the hazard as a body-supplied
        `staff_user_id` doubling as the caller's identity; this body carries a
        TARGET and never an actor. `raised_by = actor.id`, full stop — nobody may
        raise a page AS somebody else, not even an owner, because an SOS is a
        first-person statement and an owner who needs help raises her own.
        `RaiseSosRequest` is a `ForbidExtraModel`, so a body carrying `raised_by`
        is a 400 rather than a silently ignored key.
        """
        note = normalize_sos_note(note)
        if target_staff_user_id is not None and target_staff_user_id == actor.id:
            # A self-page has no audience: it would sit open forever escalating
            # to the shift manager for nothing, and the raiser never gets the
            # overlay for her own page, so nothing would ever surface it to her
            # either.
            raise SosValidationError("cannot page yourself")

        at = self._clock()
        async with tenant_session(self._sessions, tenant_id) as session:
            assignment_id = None
            if fitting_room_assignment_id is not None:
                # PERMISSIVE, and it must be HER OWN assignment. Unresolved ->
                # store NULL and carry on: a stale room pointer must never refuse
                # a page, and RLS makes a foreign tenant's id simply not resolve,
                # so there is no leak and no oracle.
                assignment = await self._sos.assignment_of(
                    session, tenant_id, fitting_room_assignment_id, actor.id
                )
                assignment_id = assignment.id if assignment is not None else None

            # PERMISSIVE, and this is THE no-reachable-target case. A named
            # target must resolve to a live staff row AND hold a live session. If
            # either check fails the alert is created with a NULL target —
            # rerouted to the shift manager IN THE DATA and not merely in the UI
            # — and the raiser is TOLD SO. The raise does not fail.
            #
            # Why the role audience can never be empty: a NULL target routes to
            # ELEVATED_ROLES = {owner, shift_manager}, and `auth/staff.py` holds
            # the last-owner invariant ("at least one live owner") under an
            # advisory lock. So the epic's "with no on-shift staffer in the
            # requested role" is unreachable for the ROLE target and real only
            # for a NAMED one — which is exactly why it is discharged here.
            target_id = target_staff_user_id
            if target_id is not None:
                target_row = await self._staff.by_id(session, tenant_id, target_id)
                reachable = target_row is not None and await self._session_rows.has_live_session(
                    session, tenant_id, target_id, at
                )
                if not reachable:
                    target_id = None

            alert = await self._sos.insert(
                session,
                tenant_id,
                raised_by=actor.id,
                target_staff_user_id=target_id,
                fitting_room_assignment_id=assignment_id,
                note=note,
            )
            rerouted = target_staff_user_id is not None and target_id is None
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.SOS_RAISED,
                actor_id=actor.id,
                entity=str(alert.id),
                # ⚠ The requested_target / target PAIR is the whole point. The
                # reroute writes NULL into the column, destroying the only record
                # of whom she actually tried to page — `previous_break_started_at`
                # and the handover `from`, third instance. Without the pair the
                # trail says a page went to the shift manager and cannot say Dana
                # was meant to get it.
                details={
                    "alert": str(alert.id),
                    "requested_target": _str_or_none(target_staff_user_id),
                    "target": _str_or_none(target_id),
                    "rerouted": rerouted,
                    "assignment": _str_or_none(assignment_id),
                },
            )
            return RaisedSos(
                sos=await self._sos_view(session, tenant_id, alert.id, actor=actor, at=at),
                rerouted=rerouted,
            )

    async def _sos_view(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        alert_id: UUID,
        *,
        actor: StaffContext,
        at: datetime.datetime,
    ) -> SosRead:
        """What every mutation answers: the SAME shape the poll's `alerts[]`
        elements carry, read back from the database rather than assembled from
        the request, so the console patches one card in place and cannot disagree
        with itself.

        A row that vanished between the write and this read is unrepresentable —
        nothing hard-deletes an alert and there is no sweeper — so it raises
        rather than returning `None` for a caller to mishandle.
        """
        row = await self._sos.view_of(session, tenant_id, alert_id)
        if row is None:
            raise RuntimeError(f"sos alert {alert_id} cannot be read back")
        return _sos_read(row, actor=actor, server_now=at)

    async def accept_sos(self, tenant_id: UUID, alert_id: UUID, *, actor: StaffContext) -> SosRead:
        """«אני מגיעה» — and the ORDER of these steps IS the first-accept-owns
        guarantee.

        read (no status filter) -> visibility 404 -> permission 404 ->
        IDEMPOTENCE -> the conditional UPDATE -> rowcount-0 discriminator.

        ⚠ **Both refusals are 404 and byte-identical to a missing id.** Whose
        alert it is can only be learned by READING it, so a 403 on a real id and
        a 404 on a fake one would discriminate existence and let any staffer
        enumerate the tenant's alerts.

        ⚠ **IDEMPOTENCE IS RESOLVED BEFORE THE 409, keyed on the REQUEST.** She
        tapped twice, or two of her devices did. Resolved after the 409 instead,
        a double-tap tells her — by name — that SHE has it, as an error. Every
        single-accept test stays green either way, which is why the ordering is
        spelled out rather than left to the reader.

        The raiser may not accept her own page: she has resolve and cancel.
        """
        at = self._clock()
        async with tenant_session(self._sessions, tenant_id) as session:
            row = await self._sos.by_id(session, tenant_id, alert_id)
            if row is None or not _visible_to(row, actor=actor):
                raise DomainNotFoundError("sos_alert")
            if not (row.target_staff_user_id == actor.id or actor.role in ELEVATED_ROLES):
                raise DomainNotFoundError("sos_alert")
            if row.status == SosStatus.ACCEPTED and row.accepted_by == actor.id:
                return await self._sos_view(session, tenant_id, alert_id, actor=actor, at=at)

            wrote, after = await self._sos.accept(
                session, tenant_id, alert_id, actor_id=actor.id, at=at
            )
            if wrote:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.SOS_ACCEPTED,
                    actor_id=actor.id,
                    entity=str(alert_id),
                    details={"alert": str(alert_id), "raised_by": str(row.raised_by)},
                )
                if after is None:
                    raise RuntimeError("sos accept wrote a row it cannot read back")
                return await self._sos_view(session, tenant_id, alert_id, actor=actor, at=at)

            if after is None:
                raise DomainNotFoundError("sos_alert")
            return await self._refuse_accept(session, tenant_id, after)

    async def _refuse_accept(
        self, session: AsyncSession, tenant_id: UUID, row: SosAlert
    ) -> NoReturn:
        """Rowcount 0 -> discriminate on the CURRENT status, which is the only
        discriminator this feature has: there is no index, therefore no
        constraint name to read.

        ⚠ **The `open` branch is genuinely unreachable and STILL raises.** A
        zero-row UPDATE takes no lock and the repo runs READ COMMITTED, so a
        concurrent write can move the row between the UPDATE and the re-read —
        but nothing moves a row BACK to `open`, and `uuid_generate_v4()` makes
        delete-and-recreate-with-the-same-id impossible. It is spelled as a raise
        rather than as a comment claiming impossibility because F41's review
        found exactly that shape: an "impossible" branch with no `else` returns
        `None` and 500s with no message.
        """
        if row.status in (SosStatus.RESOLVED, SosStatus.CANCELLED):
            raise SosClosedError
        if row.status == SosStatus.ACCEPTED:
            raise SosAlreadyAcceptedError(await self._name_of(session, tenant_id, row.accepted_by))
        raise RuntimeError(f"sos accept matched no row but reads back {row.status!r}")

    async def _name_of(
        self, session: AsyncSession, tenant_id: UUID, staff_id: UUID | None
    ) -> dict[str, str] | None:
        """The 409's `details`, and it is OPTIONAL — the key is ABSENT rather
        than null when there is nobody to name.

        `accepted_by` points at a `staff_users` row that staff removal can
        soft-delete at any time, and the acceptor can be removed between her
        accept and this read. «{{name}} כבר מגיעה.» rendering with an empty
        interpolation on a legally binding surface is worse than a sentence that
        admits it does not know.
        """
        if staff_id is None:
            return None
        row = await self._staff.by_id(session, tenant_id, staff_id)
        return {"staff_display_name": row.display_name} if row is not None else None

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


def _str_or_none(value: UUID | None) -> str | None:
    return str(value) if value is not None else None


def _escalated(row: SosAlert, *, server_now: datetime.datetime) -> bool:
    """OPEN, unacknowledged, and older than thirty seconds.

    `status == 'open'` already implies `acknowledged_at IS NULL` — one UPDATE
    writes both — and the second conjunct is spelled anyway so the predicate
    reads as the rule rather than as a consequence of another decision.

    ⚠ **TWO CLOCKS.** `created_at` is `server_default=text("now()")`, i.e. the
    DATABASE host's transaction-start time, while `server_now` is the SERVICE's
    Python clock — the same instant that goes on the wire and that the console's
    elapsed line anchors on. The skew is NTP-bounded and irrelevant against a
    thirty-second threshold read every two seconds, and one instant deciding both
    is what stops the overlay disagreeing with itself.

    ⚠ **AND THERE IS DELIBERATELY NO `max(timedelta(0), …)` CLAMP**, unlike
    `lib/elapsed.ts` where the clamp is genuinely load-bearing. That returns a
    RENDERED NUMBER, so a negative delta ships «כבר -1 דק'» to a screen. This
    returns a BOOLEAN against a one-sided positive threshold:
    `timedelta(seconds=-5) >= timedelta(seconds=30)` is already False, BYTE
    IDENTICAL to the clamped result. A clamp here pins nothing — spec review ran
    the "drop the clamp" mutation and it came back GREEN — so the negative-delta
    case is an assertion and not a mutation target.

    ⚠ **What escalation changes is whether the overlay RISES on her device, never
    who may SEE the alert.** A shift manager sees every alert in her tenant from
    t=0 because she is the fallback; if every one also rose full-screen she would
    learn within a day to dismiss them unread.
    """
    if row.status != SosStatus.OPEN or row.acknowledged_at is not None:
        return False
    return server_now - row.created_at >= ESCALATION_AFTER


def _stalled(row: SosAlert, *, server_now: datetime.datetime) -> bool:
    """ACCEPTED two minutes ago and still not resolved — THE SECOND SILENCE.

    ⚠ **This closes the hole `_escalated` opens, and without it the accept path
    re-opens the one guarantee this feature exists to make.** `_escalated`
    short-circuits on `status != OPEN` and `_for_me` returns False for any
    non-open row, so **the instant anybody taps «אני מגיעה» the alert stops
    escalating and stops rising on every device in the boutique, forever.** If
    the acceptor's phone dies, her session drops, she is pulled into another
    fitting, or she taps accept and forgets, nothing ever re-surfaces it: there
    is no auto-resolve, no un-accept verb and no second threshold.

    And it is worse than silence, because the raiser's screen reads «דנה מגיעה»
    — she stops looking for help on the strength of a signal the product cannot
    back. «A page is never silently dropped» is discharged on the CREATE path by
    the reroute; this is the same sentence on the ACCEPT path.

    Same zero-write mechanism as `_escalated`, same shared `server_now` anchor:
    one more constant and one more branch, no column, no writer, no worker.
    """
    if row.status != SosStatus.ACCEPTED or row.acknowledged_at is None:
        return False
    return server_now - row.acknowledged_at >= STALLED_AFTER


def _for_me(row: SosAlert, *, actor: StaffContext, escalated: bool, stalled: bool) -> bool:
    """Whether the full-screen overlay RISES on THIS caller's device — a narrower
    question than `_visible_to`'s, and the narrowing is the whole of D7.

    ⚠ **The raiser never gets the overlay for her own page**, and this is the
    sharpest of the small decisions. She is holding a bride's corset with one
    hand and her phone in the other; a full-screen red interruption on her own
    device, caused by her own tap, would be the product shouting at the person
    who asked for quiet. She sees it in the SOS centre, and the thing she
    actually needs — who is coming — arrives as the accept on the same tick.
    """
    if row.raised_by == actor.id:
        return False
    if row.status == SosStatus.ACCEPTED:
        # An accepted alert is somebody's job — UNLESS nobody has moved on it for
        # two minutes, at which point it is nobody's job again and the elevated
        # fallback gets it back. D6's second silence, and the ONE branch that
        # keeps the accept path non-silent.
        return stalled and actor.role in ELEVATED_ROLES
    if row.status != SosStatus.OPEN:
        return False
    if row.target_staff_user_id == actor.id:
        return True
    if actor.role in ELEVATED_ROLES:
        return row.target_staff_user_id is None or escalated
    return False


def _sos_read(row: SosAlertRow, *, actor: StaffContext, server_now: datetime.datetime) -> SosRead:
    """The three derivations, from ONE instant, in one place — so a card and its
    badge can never be computed against two."""
    escalated = _escalated(row.alert, server_now=server_now)
    stalled = _stalled(row.alert, server_now=server_now)
    return SosRead(
        row=row,
        escalated=escalated,
        stalled=stalled,
        for_me=_for_me(row.alert, actor=actor, escalated=escalated, stalled=stalled),
    )


def _visible_to(row: SosAlert, *, actor: StaffContext) -> bool:
    """D7's audience rule, applied to ONE row that was read by id.

    An elevated caller sees every alert in her tenant from the instant it is
    raised — «never silently dropped» requires it, and she is the fallback.
    Everybody else sees only the three alerts that are hers: the one she raised
    (so she can see the accept), the one she was named on, and the one she owns.

    ⚠ This is VISIBILITY and not RISING. Whether the full-screen overlay appears
    on her device is a separate, narrower predicate — otherwise a shift manager
    would get a red interruption for every seamstress-to-seamstress page in the
    boutique and would learn within a day to dismiss them unread.
    """
    if actor.role in ELEVATED_ROLES:
        return True
    return actor.id in (row.raised_by, row.target_staff_user_id, row.accepted_by)
