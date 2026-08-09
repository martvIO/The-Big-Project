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
    # NULLABLE from 0032: a `waitlist_offer` row's subject is an ENTRY, not a
    # booking, and `ck_scheduled_messages_subject` is an XOR over the pair.
    # ⚠ Branch on `kind` before dereferencing either one.
    booking_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    waitlist_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    send_after: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    manage_token: Mapped[str | None] = mapped_column(Text, nullable=True)
