from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditLogRepository:
    async def record(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        action: str,
        actor_id: UUID | None = None,
        entity: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        session.add(
            AuditLog(
                tenant_id=tenant_id,
                actor_id=actor_id,
                action=action,
                entity=entity,
                details=details or {},
            )
        )
        await session.flush()

    async def list_actions(self, session: AsyncSession) -> list[str]:
        stmt = select(AuditLog.action).order_by(AuditLog.created_at)
        return list((await session.execute(stmt)).scalars().all())
