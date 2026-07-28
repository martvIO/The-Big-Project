import uuid

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class Customer(StandardColumns, Base):
    """Keyed by (tenant, phone) and created ONLY after OTP verification proved
    possession of that number — an unverified phone would strand a paying
    customer behind an SMS link that can never arrive."""

    __tablename__ = "customers"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
