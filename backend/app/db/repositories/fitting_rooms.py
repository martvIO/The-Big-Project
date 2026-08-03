import dataclasses
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.constants import BookingStatus
from app.models.customer import Customer
from app.models.fitting_room import FittingRoom
from app.models.fitting_room_assignment import FittingRoomAssignment
from app.models.staff_user import StaffUser


@dataclasses.dataclass(frozen=True)
class RoomRow:
    """One tile: a room, and the one active assignment the partial unique index
    guarantees it has at most one of.

    Flat rather than nested, and frozen, because `FloorResponse.from_rows` is a
    PURE RENDERER of this — the schema module never grows a query. Every
    assignment field is None together: `assignment_id is None` means free.
    """

    room_id: uuid.UUID
    label: str
    sort_order: int
    is_active: bool
    assignment_id: uuid.UUID | None
    staff_user_id: uuid.UUID | None
    # Null when the holder was soft-deleted from staff_users AND swept, which is
    # why the panel types this `string | null`. See list_with_occupancy.
    staff_display_name: str | None
    staff_role: str | None
    booking_id: uuid.UUID | None
    # Null = an anonymous visit. Resolved on EVERY read from the live rows, never
    # snapshotted onto the assignment.
    client_label: str | None
    # The assignment's created_at (D2 — there is no assigned_at column).
    assigned_at: datetime | None


class FittingRoomsRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defence-in-depth (house pattern — see StaffUsersRepository).

    ⚠ **That redundancy is NOT proved by this module's tests and pretending
    otherwise would be worse than not claiming it.** Dropping every explicit
    `tenant_id ==` below leaves the whole repository suite GREEN, because RLS is
    forced on all three tables and carries the isolation on its own. What the
    predicate buys is the case RLS cannot cover — a future missing FORCE, a
    policy typo, an over-privileged role — and the only test that can see it is
    the isolation suite running as a role RLS does not bind. Mutation performed,
    recorded here, restored.
    """

    async def insert(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        label: str,
        sort_order: int = 0,
        is_active: bool = True,
    ) -> FittingRoom:
        room = FittingRoom(
            tenant_id=tenant_id, label=label, sort_order=sort_order, is_active=is_active
        )
        session.add(room)
        await session.flush()
        await session.refresh(room)
        return room

    async def by_id(
        self, session: AsyncSession, tenant_id: uuid.UUID, room_id: uuid.UUID
    ) -> FittingRoom | None:
        """An unknown id, a soft-deleted room and another tenant's room are one
        indistinguishable miss, which is what lets every route answer 404
        without discriminating existence."""
        stmt = select(FittingRoom).where(
            FittingRoom.tenant_id == tenant_id,
            FittingRoom.id == room_id,
            FittingRoom.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_id_for_update(
        self, session: AsyncSession, tenant_id: uuid.UUID, room_id: uuid.UUID
    ) -> FittingRoom | None:
        """`by_id` under a ROW LOCK, and the lock is the whole point (AC17).

        Deleting a room is the one hidden read-then-write in this feature: read
        occupancy, then stamp `deleted_at`. That is a CROSS-ROW invariant, which
        is exactly the shape a unique index cannot express. Under READ COMMITTED
        the delete sees zero active assignments while a concurrent claim is
        uncommitted, both commit, and the result is a soft-deleted room holding a
        live assignment — a row no read surfaces, so there is NO UI PATH TO
        RELEASE IT: the staffer's key stays in
        `idx_fitting_room_assignments_staff_active` forever and she can never
        claim another room. Recovery needs psql.

        Writing the guard as `UPDATE ... WHERE NOT EXISTS (SELECT 1 FROM
        fitting_room_assignments ...)` does not fix it — EvalPlanQual does not
        re-read other tables.

        So the delete and the claim both take this lock on the ROOM row first,
        and the delete then issues its occupancy guard as a SEPARATE statement,
        whose new snapshot is taken after the lock is held and therefore sees the
        committed claim. Cost: one row lock per room. Nothing that was concurrent
        becomes serial — two claims on one room already resolve to one winner via
        the index, and claims on different rooms take different locks.
        """
        stmt = (
            select(FittingRoom)
            .where(
                FittingRoom.tenant_id == tenant_id,
                FittingRoom.id == room_id,
                FittingRoom.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_live(self, session: AsyncSession, tenant_id: uuid.UUID) -> list[FittingRoom]:
        """Every live room, ACTIVE AND INACTIVE. Only `deleted_at` removes a row:
        an inactive room stays on the panel, greyed and unclaimable, because a
        room a staffer cannot find is worse than one she can see is out of
        service.

        BOTH sort keys, riding idx_fitting_rooms_tenant_order. `created_at` is
        the tiebreak and it is load-bearing rather than decorative: `sort_order`
        defaults to 0 and the registry lets it be omitted, so a boutique that
        never reorders has every room in one equal-`sort_order` group, and a
        5-second repaint that re-sorts the tiles is a repaint a finger cannot
        travel across.
        """
        stmt = (
            select(FittingRoom)
            .where(FittingRoom.tenant_id == tenant_id, FittingRoom.deleted_at.is_(None))
            .order_by(FittingRoom.sort_order, FittingRoom.created_at)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def update(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        room_id: uuid.UUID,
        *,
        label: str | None = None,
        sort_order: int | None = None,
        is_active: bool | None = None,
    ) -> FittingRoom | None:
        """`None` means NOT SUPPLIED, never "clear it" — `CustomersRepository`'s
        rule. The dialog's three controls are independent, so a reorder must
        leave the label alone. Supplying nothing is a legal no-op that still
        answers the live row, so the service's diff can decline to write without
        a second read path."""
        room = await self.by_id(session, tenant_id, room_id)
        if room is None:
            return None
        if label is not None:
            room.label = label
        if sort_order is not None:
            room.sort_order = sort_order
        if is_active is not None:
            room.is_active = is_active
        await session.flush()
        await session.refresh(room)
        return room

    async def soft_delete(
        self, session: AsyncSession, tenant_id: uuid.UUID, room_id: uuid.UUID
    ) -> bool:
        """Whether a live row was hit. `deleted_at IS NULL` in the predicate is
        what makes a second call answer False rather than re-stamp the timestamp.

        The caller holds `by_id_for_update`'s lock and has already run the
        occupancy guard — this method does not check occupancy, because a guard
        issued inside the same statement would be the unsafe snapshot read that
        `by_id_for_update`'s docstring rejects.
        """
        stmt = (
            update(FittingRoom)
            .where(
                FittingRoom.tenant_id == tenant_id,
                FittingRoom.id == room_id,
                FittingRoom.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(FittingRoom.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def list_with_occupancy(
        self, session: AsyncSession, tenant_id: uuid.UUID
    ) -> list[RoomRow]:
        """The payload's FIRST statement: one outer-join chain driving from
        `fitting_rooms`, so an unoccupied room still produces a row.

        There are no FK constraints in this schema, so every join predicate is
        spelled out here rather than left to a reader to assume. Two of them are
        load-bearing and each has a named test:

        - **`staff_users` carries NO `deleted_at` filter.** A holder soft-deleted
          mid-fitting leaves a live assignment with no staff card, and the name is
          not a snapshot, so this is the only thing that lets the tile still say
          who is in there. Adding a filter reddens
          `test_a_soft_deleted_holder_still_names_the_tile`.
        - **`customers` DOES carry one.** An Amendment 13 erasure is about the
          PERSON, not her appointment: F20 soft-deleting `customers` while the
          booking survives is the likeliest shape, and without this conjunct her
          name keeps rendering on a payload five roles can open after the
          platform told her it was erased. Dropping it reddens
          `test_a_deleted_customer_renders_an_anonymous_visit` and leaves the
          deleted-BOOKING case green, which is the distinction.

        The assignment join repeats D3's index predicate exactly so the planner
        uses the index. All five joins are LEFT, so an assignment whose source
        row has been swept still renders a room with `client_label` null.
        """
        return await self._occupancy_rows(session, tenant_id)

    async def room_with_occupancy(
        self, session: AsyncSession, tenant_id: uuid.UUID, room_id: uuid.UUID
    ) -> RoomRow | None:
        """ONE tile, the same join. Every mutation answers the full room
        RENDERED FROM THE DATABASE rather than from the request, which is what
        lets the panel patch a tile in place and never disagree with itself."""
        rows = await self._occupancy_rows(session, tenant_id, room_id=room_id)
        return rows[0] if rows else None

    async def occupancy_for_staff(
        self, session: AsyncSession, tenant_id: uuid.UUID, staff_id: uuid.UUID
    ) -> RoomRow | None:
        """Which room this staffer is in, denormalised — the break routes' one
        extra lookup.

        `POST …/break/start` answers a full card, and if that staffer is standing
        in a fitting room the card must say `occupied`. "Pass False, it's just
        the break route" is the shortcut that ships a card contradicting the
        panel it lands in five seconds later.

        The `staff_user_id` predicate is a strict qual on the OUTER-joined side,
        so the planner collapses that join to an inner one and reaches the row
        through `idx_fitting_room_assignments_staff_active` — which holds at most
        one key per staffer by construction, so this never has to choose.
        """
        rows = await self._occupancy_rows(session, tenant_id, staff_id=staff_id)
        return rows[0] if rows else None

    async def _occupancy_rows(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        room_id: uuid.UUID | None = None,
        staff_id: uuid.UUID | None = None,
    ) -> list[RoomRow]:
        """The one join chain, written once. Three callers narrow it with a
        predicate and nothing else — a second transcription of five outer joins
        is five chances for one `deleted_at` to differ between the payload and
        the row a mutation answers with."""
        stmt = (
            select(
                FittingRoom.id,
                FittingRoom.label,
                FittingRoom.sort_order,
                FittingRoom.is_active,
                FittingRoomAssignment.id,
                FittingRoomAssignment.staff_user_id,
                FittingRoomAssignment.booking_id,
                FittingRoomAssignment.created_at,
                StaffUser.display_name,
                StaffUser.role,
                Customer.name,
            )
            .select_from(FittingRoom)
            .outerjoin(
                FittingRoomAssignment,
                and_(
                    FittingRoomAssignment.tenant_id == tenant_id,
                    FittingRoomAssignment.fitting_room_id == FittingRoom.id,
                    FittingRoomAssignment.released_at.is_(None),
                    FittingRoomAssignment.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                StaffUser,
                and_(
                    StaffUser.tenant_id == tenant_id,
                    StaffUser.id == FittingRoomAssignment.staff_user_id,
                ),
            )
            .outerjoin(
                Booking,
                and_(
                    Booking.tenant_id == tenant_id,
                    Booking.id == FittingRoomAssignment.booking_id,
                    Booking.deleted_at.is_(None),
                    Booking.status != BookingStatus.CANCELLED.value,
                ),
            )
            .outerjoin(
                Customer,
                and_(
                    Customer.tenant_id == tenant_id,
                    Customer.id == Booking.customer_id,
                    Customer.deleted_at.is_(None),
                ),
            )
            .where(FittingRoom.tenant_id == tenant_id, FittingRoom.deleted_at.is_(None))
            .order_by(FittingRoom.sort_order, FittingRoom.created_at)
        )
        if room_id is not None:
            stmt = stmt.where(FittingRoom.id == room_id)
        if staff_id is not None:
            stmt = stmt.where(FittingRoomAssignment.staff_user_id == staff_id)
        rows: list[Any] = list((await session.execute(stmt)).all())
        return [
            RoomRow(
                room_id=row[0],
                label=row[1],
                sort_order=row[2],
                is_active=row[3],
                assignment_id=row[4],
                staff_user_id=row[5],
                booking_id=row[6],
                assigned_at=row[7],
                staff_display_name=row[8],
                staff_role=row[9],
                client_label=row[10],
            )
            for row in rows
        ]
