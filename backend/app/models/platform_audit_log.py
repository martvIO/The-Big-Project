import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlatformAuditLog(Base):
    """Append-only PLATFORM-scoped operator trail (provisioning, suspension, …).
    Deliberately NOT tenant-scoped: the column is `target_tenant_id`, not
    `tenant_id`, so the forced-RLS metadata scan doesn't require RLS on it — this
    table is meant to be readable across tenants by platform operators."""

    __tablename__ = "platform_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    operator: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_tenant_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
