import uuid

from sqlalchemy import Boolean, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns
from app.models.constants import AppointmentAudience


class AppointmentType(StandardColumns, Base):
    """Soft delete = archive: E3 bookings reference types by id + snapshot, so
    archiving never corrupts history and frees the name for reuse."""

    __tablename__ = "appointment_types"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    audience: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text(f"'{AppointmentAudience.ALL}'")
    )
    deposit_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # Money in agorot — integer, never float.
    deposit_amount_agorot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
