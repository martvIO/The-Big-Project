from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, func, select, update
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

    async def has_live_session(
        self, session: AsyncSession, tenant_id: UUID, staff_user_id: UUID, now: datetime
    ) -> bool:
        """Is this staffer reachable at all — F37's raise, and NOTHING else reads
        it.

        ⚠ **WHAT THIS PROVES, stated because the copy it drives could be read as
        claiming more: a live row proves A SESSION, NOT A SCREEN.**
        `settings.session_ttl_seconds` is TWELVE HOURS and nothing revokes on
        going home — `revoke_for_staff_user` fires on a password change and on
        deactivation only. A staffer who signs in at 08:00 and leaves at 16:00
        without logging out holds a live row until 20:00. And the console's poll
        stops entirely on `document.hidden`, so a phone asleep in an apron is a
        live session behind a dark screen.

        So this is a cheap UPPER BOUND on reachability: `rerouted: false` claims
        only "she has not signed out and her session has not expired", and
        `rerouted: true` is the case it genuinely closes. **The thirty-second
        escalation is the real safety net, not this read** — that sentence
        belongs here rather than two modules away, because it is the honest
        answer to "what covers a live session on a sleeping device".

        It is still strictly better than the on-shift checkbox the epic asked
        for: nobody has to remember to tick it, and it is derived from an action
        she actually took.
        """
        stmt = select(
            exists().where(
                Session.tenant_id == tenant_id,
                Session.staff_user_id == staff_user_id,
                Session.deleted_at.is_(None),
                Session.expires_at > now,
            )
        )
        return bool((await session.execute(stmt)).scalar_one())

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
