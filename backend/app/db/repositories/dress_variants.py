import dataclasses
import datetime
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dress_variant import DressVariant


@dataclasses.dataclass(frozen=True)
class VariantAggregate:
    """One pre-aggregated group row per dress — the list's third statement. It
    feeds the single out_of_stock formula, so the badge can never be computed
    from a per-row query the page did not pay for."""

    variant_count: int
    total_quantity: int


class DressVariantsRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see AppointmentTypesRepository)."""

    async def list_active(
        self, session: AsyncSession, tenant_id: UUID, dress_id: UUID
    ) -> list[DressVariant]:
        stmt = (
            select(DressVariant)
            .where(
                DressVariant.tenant_id == tenant_id,
                DressVariant.dress_id == dress_id,
                DressVariant.deleted_at.is_(None),
            )
            .order_by(DressVariant.sort_order, DressVariant.id)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def aggregate_by_dress(
        self, session: AsyncSession, tenant_id: UUID, dress_ids: Sequence[UUID]
    ) -> dict[UUID, VariantAggregate]:
        if not dress_ids:
            return {}
        stmt = (
            select(
                DressVariant.dress_id,
                func.count().label("variant_count"),
                func.coalesce(func.sum(DressVariant.quantity), 0).label("total_quantity"),
            )
            .where(
                DressVariant.tenant_id == tenant_id,
                DressVariant.dress_id.in_(dress_ids),
                DressVariant.deleted_at.is_(None),
            )
            .group_by(DressVariant.dress_id)
        )
        rows = (await session.execute(stmt)).all()
        return {
            dress_id: VariantAggregate(variant_count=variant_count, total_quantity=total_quantity)
            for dress_id, variant_count, total_quantity in rows
        }

    async def size_labels_by_dress(
        self, session: AsyncSession, tenant_id: UUID, dress_ids: Sequence[UUID]
    ) -> dict[UUID, list[str]]:
        """Every live size label for a page of dresses, in ONE statement — the
        floor picker's second read (F36 D16), and `aggregate_by_dress`'s shape
        including the empty-input short-circuit.

        Labels rather than `aggregate_by_dress`'s counts, because the picker has
        to render the actual sizes a staffer chooses between. Quantity is
        deliberately not returned: a gown carried in for a fitting is not a sale,
        and stock is the catalog's business.

        Keys are present only for dresses that HAVE live variants, so the caller
        reads with `.get(id, [])` — a dress with no sizes recorded is ordinary
        and binds with a null size.
        """
        if not dress_ids:
            return {}
        stmt = (
            select(DressVariant.dress_id, DressVariant.size_label)
            .where(
                DressVariant.tenant_id == tenant_id,
                DressVariant.dress_id.in_(dress_ids),
                DressVariant.deleted_at.is_(None),
            )
            .order_by(DressVariant.dress_id, DressVariant.sort_order, DressVariant.id)
        )
        grouped: dict[UUID, list[str]] = {}
        for dress_id, size_label in (await session.execute(stmt)).all():
            grouped.setdefault(dress_id, []).append(size_label)
        return grouped

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        dress_id: UUID,
        size_label: str,
        quantity: int,
        sort_order: int,
    ) -> DressVariant:
        row = DressVariant(
            tenant_id=tenant_id,
            dress_id=dress_id,
            size_label=size_label,
            quantity=quantity,
            sort_order=sort_order,
        )
        session.add(row)
        # The partial unique index on lower(size_label) surfaces here.
        await session.flush()
        await session.refresh(row)
        return row

    async def soft_delete_all(self, session: AsyncSession, tenant_id: UUID, dress_id: UUID) -> int:
        """Retires this dress's whole active size matrix — the first half of the
        atomic replace, and the second step of the archive cascade. The
        `deleted_at IS NULL` predicate is what leaves individually-deleted rows
        on their older stamp when a dress is archived."""
        stmt = (
            update(DressVariant)
            .where(
                DressVariant.tenant_id == tenant_id,
                DressVariant.dress_id == dress_id,
                DressVariant.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(DressVariant.id)
        )
        return len((await session.execute(stmt)).scalars().all())

    async def restore_archived_with(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        dress_id: UUID,
        archived_at: datetime.datetime,
    ) -> int:
        """Only the rows the archive itself stamped: matching on the dress's own
        deleted_at is what keeps a size the owner deleted last week deleted."""
        stmt = (
            update(DressVariant)
            .where(
                DressVariant.tenant_id == tenant_id,
                DressVariant.dress_id == dress_id,
                DressVariant.deleted_at == archived_at,
            )
            .values(deleted_at=None)
            .returning(DressVariant.id)
        )
        return len((await session.execute(stmt)).scalars().all())
