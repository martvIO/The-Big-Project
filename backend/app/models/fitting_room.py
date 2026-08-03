import uuid

from sqlalchemy import Boolean, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class FittingRoom(StandardColumns, Base):
    """A label, a display order, and two different kinds of "not in use".

    `deleted_at IS NOT NULL` means the boutique reconfigured and this room is
    gone from the registry. `is_active = false` means the mirror is broken —
    the room stays on the panel, greyed, with no claim control. Collapsing them
    would leave "out of service" expressible only by deleting the room and
    re-typing it tomorrow, which would orphan every assignment pointing at it.

    Deactivating an OCCUPIED room is allowed and deleting one is refused:
    `is_active` stops the NEXT claim, never the fitting in progress.

    Names are not unique, `dresses`' rule unchanged — a room is only ever
    addressed by id.
    """

    __tablename__ = "fitting_rooms"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
