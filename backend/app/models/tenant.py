from typing import Any

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, StandardColumns
from app.models.constants import TenantStatus


class Tenant(StandardColumns, Base):
    """Platform-scoped: no tenant_id column and no RLS — this IS the tenant registry."""

    __tablename__ = "tenants"

    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text(f"'{TenantStatus.ACTIVE}'")
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
