from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_audit_log import PlatformAuditLog


class PlatformAuditLogRepository:
    async def record(
        self,
        session: AsyncSession,
        *,
        operator: str,
        action: str,
        target_tenant_id: UUID | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        # Set id AND created_at client-side so the INSERT has no server-generated
        # columns to fetch back. app_user is INSERT-only (no SELECT) on this table,
        # and any RETURNING (which the ORM emits to populate server defaults) needs
        # SELECT and would fail.
        session.add(
            PlatformAuditLog(
                id=uuid4(),
                operator=operator,
                action=action,
                target_tenant_id=target_tenant_id,
                details=details or {},
                created_at=datetime.now(UTC),
            )
        )
        await session.flush()
