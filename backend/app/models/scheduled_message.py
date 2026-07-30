import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class ScheduledMessage(StandardColumns, Base):
    """One future SMS, claimed by the worker poller when `send_after` passes.

    This table is the SCHEDULE state and never the evidence — `message_log` keeps
    the evidence and `NotificationService` stays its single writer. A row's whole
    life is pending -> sent | failed | cancelled.

    `manage_token` carries the raw link token while the row is pending, and is
    cleared on every terminal status. `bookings` stores only the sha256, so
    without this the worker could not reproduce the link the confirmation SMS
    already sent (see migration 0010 and the spec amendment).
    """

    __tablename__ = "scheduled_messages"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    # No FK by house rule; the booking is re-read at claim time anyway, which is
    # also the defence against races the schedule-time rules cannot see.
    booking_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    send_after: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    manage_token: Mapped[str | None] = mapped_column(Text, nullable=True)
