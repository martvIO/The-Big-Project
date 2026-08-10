from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_invite import PlatformInvite


class PlatformInvitesRepository:
    """Platform-scoped: no tenant predicate anywhere, because there is no tenant
    until an invite is redeemed.

    ⚠ NO METHOD ON THIS CLASS TAKES A RAW CODE. Every lookup is by
    `hash_token(code)`, computed by the caller, so the raw value never travels
    into a query, a bind parameter log or a statement cache. `PlatformInvite`
    has no raw-code field to store it in either.
    """

    async def insert(
        self,
        session: AsyncSession,
        *,
        code_hash: str,
        slug: str,
        name: str,
        owner_email: str,
        created_by: str,
        expires_at: datetime,
    ) -> PlatformInvite:
        row = PlatformInvite(
            code_hash=code_hash,
            slug=slug,
            name=name,
            owner_email=owner_email.strip().lower(),
            created_by=created_by,
            expires_at=expires_at,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def by_code_hash(
        self, session: AsyncSession, code_hash: str, *, include_revoked: bool = False
    ) -> PlatformInvite | None:
        """A READ, used ONLY to shape a refusal — never to decide that a
        redemption may proceed. The decision is `claim`'s conditional UPDATE, and
        keeping those two apart is what makes the race safe: this read can be
        arbitrarily stale without consequence.

        Soft-deleted rows are excluded by default, so a revoked invite reads as
        absent and answers the same `invalid_invite` as an unknown one (D5's
        anti-enumeration posture).

        ⚠ `include_revoked=True` widens the read for ONE caller: the redemption
        path, which must name the invite's issuer on its audit row even when the
        invite is revoked (spec § Audit contract). It changes no wire response —
        the caller still refuses every unredeemable state with the one
        `invalid_invite` — so do not reach for it to decide anything a client
        can observe."""
        stmt = select(PlatformInvite).where(PlatformInvite.code_hash == code_hash)
        if not include_revoked:
            stmt = stmt.where(PlatformInvite.deleted_at.is_(None))
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_visible(self, session: AsyncSession) -> list[PlatformInvite]:
        """Everything not revoked, newest first — open AND redeemed. A redeemed
        invite is the operator's record that the boutique she authorised was
        actually claimed, so it stays on the list; a revoked one leaves it, which
        is what the revoke copy tells her will happen."""
        stmt = (
            select(PlatformInvite)
            .where(PlatformInvite.deleted_at.is_(None))
            .order_by(PlatformInvite.created_at.desc())
        )
        return list((await session.execute(stmt)).scalars().all())

    async def soft_delete(self, session: AsyncSession, invite_id: UUID) -> bool:
        """Revoke. A soft delete and not a DELETE, and the migration REVOKEs the
        DELETE privilege so it cannot quietly become one."""
        stmt = (
            update(PlatformInvite)
            .where(PlatformInvite.id == invite_id, PlatformInvite.deleted_at.is_(None))
            .values(deleted_at=func.now())
            .returning(PlatformInvite.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def claim(
        self,
        session: AsyncSession,
        *,
        code_hash: str,
        tenant_id: UUID,
        now: datetime,
    ) -> UUID | None:
        """⚠ THE SINGLE-USE GUARD, and it is one statement on purpose.

        An atomic conditional UPDATE guarded on `redeemed_at IS NULL`, taken as
        the FIRST statement of the redemption transaction. A second concurrent
        redeemer blocks on this row's lock; when the winner commits, Postgres
        re-evaluates the predicate against the new version, matches zero rows,
        and the loser's whole transaction — tenant, owner and audit row alike —
        rolls back. No advisory lock is needed: a single-row conditional update
        already serialises itself.

        Returns the invite id, or None when nothing matched (unknown, already
        redeemed, revoked or expired). The caller must treat None as fatal to the
        transaction, never as a branch to continue past.
        """
        stmt = (
            update(PlatformInvite)
            .where(
                PlatformInvite.code_hash == code_hash,
                PlatformInvite.redeemed_at.is_(None),
                PlatformInvite.deleted_at.is_(None),
                PlatformInvite.expires_at > now,
            )
            .values(redeemed_at=now, redeemed_tenant_id=tenant_id)
            .returning(PlatformInvite.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none()
