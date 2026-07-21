from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session


class SessionsRepository:
    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        staff_user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> Session:
        row = Session(
            tenant_id=tenant_id,
            staff_user_id=staff_user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def active_by_token_hash(
        self, session: AsyncSession, token_hash: str, now: datetime
    ) -> Session | None:
        stmt = select(Session).where(
            Session.token_hash == token_hash,
            Session.deleted_at.is_(None),
            Session.expires_at > now,
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def revoke_by_token_hash(self, session: AsyncSession, token_hash: str) -> bool:
        stmt = (
            update(Session)
            .where(Session.token_hash == token_hash, Session.deleted_at.is_(None))
            .values(deleted_at=func.now())
            .returning(Session.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None
