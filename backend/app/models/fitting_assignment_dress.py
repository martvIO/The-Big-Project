import uuid

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class FittingAssignmentDress(StandardColumns, Base):
    """One gown carried into one fitting.

    A child table rather than a JSONB array on the assignment: two staffers
    adding and removing dresses at once would make an array a read-modify-write,
    and the loser's write would silently drop the winner's dress with no error
    and no index able to say so. Here each add and each remove is a single-row
    statement that cannot lose anything it did not touch.

    Removing a dress is a SOFT DELETE, and that soft delete plus `removed_by` IS
    the audit record — which is why no `FITTING_DRESS_REMOVED` audit action
    exists.
    """

    __tablename__ = "fitting_assignment_dresses"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    fitting_room_assignment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), nullable=False
    )
    dress_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # Snapshots, `bookings`' reasoning unchanged: the owner may rename or archive
    # a dress mid-fitting and the card must render what actually went into the
    # room. `dress_id` is kept alongside so the image resolves at read time.
    dress_name: Mapped[str] = mapped_column(Text, nullable=False)
    # Nullable: a sample gown carried in before a size is chosen is an ordinary
    # event, and `bookings.dress_size` is nullable for the same reason.
    dress_size: Mapped[str | None] = mapped_column(Text, nullable=True)
    # NULL while the binding is live. Stamped with `deleted_at` on the remove —
    # without it the row answers what left the room and when, and cannot answer
    # who took it out.
    removed_by: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
