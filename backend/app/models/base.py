import uuid
from datetime import datetime

from sqlalchemy import TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class StandardColumns:
    """House standard columns (see .planning/architecture.md): UUID PK via
    uuid_generate_v4(), TIMESTAMPTZ, soft delete. updated_at is set by the
    shared update_updated_at() DB trigger — never assign it in application code."""

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
