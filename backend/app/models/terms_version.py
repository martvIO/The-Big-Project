import uuid

from sqlalchemy import Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class TermsVersion(StandardColumns, Base):
    """Append-only, DB-enforced: app_user holds SELECT + INSERT only, so no code
    path can ever UPDATE or DELETE a version — what a customer accepted at
    booking time stays reconstructable forever. StandardColumns is kept for
    uniformity; updated_at/deleted_at exist but stay NULL structurally (no
    updated_at trigger either). Current policy = max(version) per tenant."""

    __tablename__ = "terms_versions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    terms_text: Mapped[str] = mapped_column(Text, nullable=False)
    refundable_until_hours_before: Mapped[int] = mapped_column(Integer, nullable=False)
    # % of deposit forfeited outside the refund window (E4 evaluates this).
    forfeit_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("100")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
