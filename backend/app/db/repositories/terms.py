from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.terms_version import TermsVersion


class TermsVersionsRepository:
    """Append-only by DB grant (SELECT + INSERT only): no update or delete
    method exists, and none could run. deleted_at is structurally always NULL;
    the predicate stays for house-style uniformity."""

    async def max_version(self, session: AsyncSession, tenant_id: UUID) -> int:
        stmt = select(func.coalesce(func.max(TermsVersion.version), 0)).where(
            TermsVersion.tenant_id == tenant_id,
            TermsVersion.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one()

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        version: int,
        terms_text: str,
        refundable_until_hours_before: int,
        forfeit_percent: int,
        created_by: UUID,
    ) -> TermsVersion:
        row = TermsVersion(
            tenant_id=tenant_id,
            version=version,
            terms_text=terms_text,
            refundable_until_hours_before=refundable_until_hours_before,
            forfeit_percent=forfeit_percent,
            created_by=created_by,
        )
        session.add(row)
        await session.flush()  # unique (tenant_id, version) violations surface here
        await session.refresh(row)
        return row

    async def current(self, session: AsyncSession, tenant_id: UUID) -> TermsVersion | None:
        stmt = (
            select(TermsVersion)
            .where(
                TermsVersion.tenant_id == tenant_id,
                TermsVersion.deleted_at.is_(None),
            )
            .order_by(TermsVersion.version.desc())
            .limit(1)
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_versions(
        self, session: AsyncSession, tenant_id: UUID, *, offset: int, limit: int
    ) -> list[TermsVersion]:
        stmt = (
            select(TermsVersion)
            .where(
                TermsVersion.tenant_id == tenant_id,
                TermsVersion.deleted_at.is_(None),
            )
            .order_by(TermsVersion.version.desc())
            .offset(offset)
            .limit(limit)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def count(self, session: AsyncSession, tenant_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(TermsVersion)
            .where(
                TermsVersion.tenant_id == tenant_id,
                TermsVersion.deleted_at.is_(None),
            )
        )
        return (await session.execute(stmt)).scalar_one()
