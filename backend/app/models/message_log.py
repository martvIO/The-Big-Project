import uuid

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class MessageLog(StandardColumns, Base):
    """One row per SMS send attempt — the Spam-Law evidence trail. Written only
    by NotificationService (queued → sent/failed), never by adapters or feature
    code. OTP bodies are stored MASKED (see app/notifications/validation.py)."""

    __tablename__ = "message_log"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'queued'"))
    provider_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Provider failure detail for operators; never reaches a response body.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # No FK by house rule; F16 populates it for lifecycle sends.
    booking_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
