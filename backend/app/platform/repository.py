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
        # Generate the PK client-side: app_user has INSERT-only (no SELECT) on this
        # table, and a server-default PK would make the ORM's flush issue
        # INSERT ... RETURNING id — which needs SELECT — and fail.
        session.add(
            PlatformAuditLog(
                id=uuid4(),
                operator=operator,
                action=action,
                target_tenant_id=target_tenant_id,
                details=details or {},
            )
        )
        await session.flush()
