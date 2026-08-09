from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_session import PlatformSession


class PlatformSessionsRepository:
    async def insert(
        self,
        session: AsyncSession,
        *,
        operator_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> PlatformSession:
        row = PlatformSession(operator_id=operator_id, token_hash=token_hash, expires_at=expires_at)
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def live_by_token_hash(
        self, session: AsyncSession, token_hash: str, now: datetime
    ) -> PlatformSession | None:
        """Both predicates are load-bearing and neither substitutes for the
        other: `deleted_at IS NULL` is logout and deactivation, `expires_at > now`
        is the fixed 4h TTL. There is no sliding renewal — nothing here writes
        `expires_at` after the insert."""
        stmt = select(PlatformSession).where(
            PlatformSession.token_hash == token_hash,
            PlatformSession.deleted_at.is_(None),
            PlatformSession.expires_at > now,
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def revoke(self, session: AsyncSession, token_hash: str) -> bool:
        stmt = (
            update(PlatformSession)
            .where(PlatformSession.token_hash == token_hash, PlatformSession.deleted_at.is_(None))
            .values(deleted_at=func.now())
            .returning(PlatformSession.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def revoke_all_for_operator(self, session: AsyncSession, operator_id: UUID) -> None:
        """Deactivation's sweep. Unlike the staff twin there is no
        `except_token_hash`: an operator being deactivated keeps nothing, and the
        acting principal is the CLI, which holds no cookie to spare."""
        stmt = update(PlatformSession).where(
            PlatformSession.operator_id == operator_id,
            PlatformSession.deleted_at.is_(None),
        )
        await session.execute(stmt.values(deleted_at=func.now()))
