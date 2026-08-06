from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_session import CustomerSession


class CustomerSessionsRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see SessionsRepository, whose four
    statements this file mirrors for the customer side)."""

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        customer_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> CustomerSession:
        row = CustomerSession(
            tenant_id=tenant_id,
            customer_id=customer_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def active_by_token_hash(
        self, session: AsyncSession, tenant_id: UUID, token_hash: str, now: datetime
    ) -> CustomerSession | None:
        """LIVE only, and both halves of that are load-bearing: `deleted_at IS
        NULL` is what logout and F20's erase actually do, and `expires_at > now`
        is the only thing that ever ends a session nobody signed out of.

        Named for its predicate rather than `by_token_hash` so a later caller
        cannot read the signature as "fetch the row" and add its own liveness
        check one layer too late.
        """
        stmt = select(CustomerSession).where(
            CustomerSession.tenant_id == tenant_id,
            CustomerSession.token_hash == token_hash,
            CustomerSession.deleted_at.is_(None),
            CustomerSession.expires_at > now,
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def revoke_by_token_hash(
        self, session: AsyncSession, tenant_id: UUID, token_hash: str
    ) -> bool:
        """Logout. False on a second press — the row is already revoked, which
        is the outcome she asked for, not an error."""
        stmt = (
            update(CustomerSession)
            .where(
                CustomerSession.tenant_id == tenant_id,
                CustomerSession.token_hash == token_hash,
                CustomerSession.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(CustomerSession.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def revoke_all_for_customer(
        self, session: AsyncSession, tenant_id: UUID, customer_id: UUID
    ) -> int:
        """F20's erase step (spec D2), and the count is returned because the
        erase's audit record is the deliverable on that path.

        Runs in the CALLER's transaction on purpose: an erased subject holding a
        live session would keep reading her own "gone" record for up to thirty
        days, so the revocation must commit or roll back with the erasure.
        """
        stmt = (
            update(CustomerSession)
            .where(
                CustomerSession.tenant_id == tenant_id,
                CustomerSession.customer_id == customer_id,
                CustomerSession.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(CustomerSession.id)
            .execution_options(synchronize_session=False)
        )
        return len((await session.execute(stmt)).scalars().all())
