import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class OtpCode(StandardColumns, Base):
    """One live code per (tenant, phone) — a resend soft-deletes its predecessor.
    The verification_* columns are minted on successful verify and consumed by
    F13's booking transaction; all three ship here so 0008 never touches this
    table. code_hash is hygiene, not a boundary — the attempt cap and expiry
    carry the security argument (see the F11 spec)."""

    __tablename__ = "otp_codes"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    consumed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    verification_token_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    verification_consumed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
