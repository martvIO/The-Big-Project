import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class FittingRoomAssignment(StandardColumns, Base):
    """One worker holding one room for one client, right now or once upon a time.

    `released_at IS NULL AND deleted_at IS NULL` is what ACTIVE means and it is
    the whole model — no status column, no boolean, no row that gets deleted.
    Both partial unique indexes in 0018 are predicated on exactly that pair of
    nulls, so the model and the guarantee are the same sentence.

    **No `assigned_at`: `created_at` IS the claim time.** The row is created at
    the instant of the claim, so a second column would be a second copy of one
    fact. The wire field is still `assigned_at`, sourced from `created_at`,
    because a handover mutates `staff_user_id` alone — the card's elapsed time
    is the CLIENT's time in the room, and a separate column would tempt someone
    to reset it.

    **No personal field of any kind.** `booking_id` and nothing else: the client
    label is resolved on every read from the live bookings → customers rows, so
    a retention sweep or an erasure makes the tile render as an anonymous visit
    instead of quietly preserving a name in a table nobody thought of.
    """

    __tablename__ = "fitting_room_assignments"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    fitting_room_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # Mutated in place by a handover, which is what preserves the dress bindings
    # for free: release-and-reinsert would have to copy every child row.
    staff_user_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # NULL is legal and ordinary: a staffer prepping a room, or any walk-in until
    # F58 ships the queue link, produces a row with no client. That is the same
    # render path a swept booking takes, so the anonymous branch is exercised
    # from day one rather than being dead code.
    booking_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    # NOT `deleted_at`. `deleted_at` means this record is wrong and should not
    # have existed; a completed fitting is neither. Stamped from the service's
    # injectable clock rather than SQL now(), so the db suite can freeze it and
    # assert an equality — `created_at` is DB-generated and is not freezable.
    released_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
