from typing import Any
from uuid import UUID

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
        session.add(
            PlatformAuditLog(
                operator=operator,
                action=action,
                target_tenant_id=target_tenant_id,
                details=details or {},
            )
        )
        await session.flush()
