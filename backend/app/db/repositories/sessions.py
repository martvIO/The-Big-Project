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
        self, session: AsyncSession, tenant_id: UUID, token_hash: str, now: datetime
    ) -> Session | None:
        # Explicit tenant_id predicate = defense-in-depth beside RLS on the
        # session-resolution path (the cross-tenant boundary that matters most).
        stmt = select(Session).where(
            Session.tenant_id == tenant_id,
            Session.token_hash == token_hash,
            Session.deleted_at.is_(None),
            Session.expires_at > now,
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def revoke_for_staff_user(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        staff_user_id: UUID,
        *,
        except_token_hash: str | None = None,
    ) -> None:
        """Every live session this staffer holds, minus the caller's own cookie.

        Deactivation needs no sweep — `resolve_session` re-reads `staff_users`
        and `by_id` filters `deleted_at IS NULL`, so a deactivated staffer's
        cookie is a 401 on her next request. A PASSWORD CHANGE has no such
        seam: `resolve_session` never consults `password_hash`, so without this
        the sessions the old password could have leaked outlive it for the
        whole TTL. Nothing returned — no caller has a use for the count.
        """
        stmt = update(Session).where(
            Session.tenant_id == tenant_id,
            Session.staff_user_id == staff_user_id,
            Session.deleted_at.is_(None),
        )
        if except_token_hash is not None:
            stmt = stmt.where(Session.token_hash != except_token_hash)
        await session.execute(stmt.values(deleted_at=func.now()))

    async def revoke_by_token_hash(self, session: AsyncSession, token_hash: str) -> bool:
        stmt = (
            update(Session)
            .where(Session.token_hash == token_hash, Session.deleted_at.is_(None))
            .values(deleted_at=func.now())
            .returning(Session.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None
