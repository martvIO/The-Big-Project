import uuid

from sqlalchemy import Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class DressVariant(StandardColumns, Base):
    """One size bucket of one dress, and the only source of truth for stock.

    The partial unique index is on lower(size_label): the service already strips
    and collapses whitespace, but without lower() "US 6" and "us 6" would live on
    as two stock buckets for one physical size. Hebrew has no case, so lower() is
    a no-op on the common path and a real guard on Latin custom labels.
    """

    __tablename__ = "dress_variants"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    dress_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    size_label: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
