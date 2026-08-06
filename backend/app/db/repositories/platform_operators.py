from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_operator import PlatformOperator


class PlatformOperatorsRepository:
    """Platform-scoped: no tenant predicate anywhere, because there is no tenant.

    Every read filters `deleted_at IS NULL` — soft delete is deactivation here
    (spec D2), so a row that leaks past the filter is a deactivated operator who
    can still sign in.
    """

    async def insert(
        self,
        session: AsyncSession,
        *,
        email: str,
        password_hash: str,
        display_name: str,
    ) -> PlatformOperator:
        # Lowercased HERE rather than at each call site: the unique index is on
        # `lower(email)` and `by_active_email` compares lowercased, so a stored
        # mixed-case address would be found by the read and refused by the index
        # in ways that disagree.
        row = PlatformOperator(
            email=email.strip().lower(),
            password_hash=password_hash,
            display_name=display_name,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def by_active_email(self, session: AsyncSession, email: str) -> PlatformOperator | None:
        stmt = select(PlatformOperator).where(
            func.lower(PlatformOperator.email) == email.strip().lower(),
            PlatformOperator.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_id(self, session: AsyncSession, operator_id: UUID) -> PlatformOperator | None:
        stmt = select(PlatformOperator).where(
            PlatformOperator.id == operator_id,
            PlatformOperator.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def count_active(self, session: AsyncSession) -> int:
        """The read behind the last-operator refusal. Racy in the strict sense —
        two concurrent deactivations could each see two — and deliberately left
        so: there is ONE operator in the v1 posture (spec D2), the loss is a
        CLI-only lockout recoverable by `create-operator` from the same shell,
        and an advisory lock for a command a human types once is ceremony."""
        stmt = select(func.count()).where(PlatformOperator.deleted_at.is_(None))
        return (await session.execute(stmt)).scalar_one()

    async def soft_delete(self, session: AsyncSession, operator_id: UUID) -> bool:
        stmt = (
            update(PlatformOperator)
            .where(PlatformOperator.id == operator_id, PlatformOperator.deleted_at.is_(None))
            .values(deleted_at=func.now())
            .returning(PlatformOperator.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None
