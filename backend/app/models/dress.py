import uuid

from sqlalchemy import Boolean, Integer, Text, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns


class Dress(StandardColumns, Base):
    """Soft delete = archive, and the archive view reads the same rows back.

    Stock is deliberately absent: out_of_stock is derived from the dress's
    variant rows on every read, so a badge can never disagree with the matrix.
    Names are not unique — a boutique legitimately carries one designer model in
    two colours, and a dress is only ever addressed by id.
    """

    __tablename__ = "dresses"

    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Money in agorot — integer, never float. NULL = no price recorded.
    price_agorot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_visible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    # The manual, date-less owner flag; E5 #7's date-bound reservation supersedes it.
    reserved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
