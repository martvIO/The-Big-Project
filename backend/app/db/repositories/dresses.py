from uuid import UUID

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dress import Dress


def _escape_like(value: str) -> str:
    """ILIKE reads %, _ and \\ as syntax. An owner searching for "50%_lace" must
    get a literal match, not a wildcard scan."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class DressesRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see AppointmentTypesRepository)."""

    def _scope(
        self, tenant_id: UUID, *, archived: bool, search: str | None
    ) -> list[ColumnElement[bool]]:
        # archived is exclusive, never a combined view: each branch is served by
        # exactly one partial index.
        predicates: list[ColumnElement[bool]] = [
            Dress.tenant_id == tenant_id,
            Dress.deleted_at.is_not(None) if archived else Dress.deleted_at.is_(None),
        ]
        if search:
            predicates.append(Dress.name.ilike(f"%{_escape_like(search)}%", escape="\\"))
        return predicates

    async def by_id(self, session: AsyncSession, tenant_id: UUID, dress_id: UUID) -> Dress | None:
        """The predicate every /manage/dresses/{dress_id}/... route resolves
        first: an unknown id, an archived dress and another tenant's dress are
        one indistinguishable miss."""
        stmt = select(Dress).where(
            Dress.tenant_id == tenant_id,
            Dress.id == dress_id,
            Dress.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def by_id_any_state(
        self, session: AsyncSession, tenant_id: UUID, dress_id: UUID
    ) -> Dress | None:
        """Detail and restore are the only two routes that resolve an archived
        dress — everything else must keep treating it as missing."""
        stmt = select(Dress).where(Dress.tenant_id == tenant_id, Dress.id == dress_id)
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        archived: bool,
        search: str | None,
        offset: int,
        limit: int,
    ) -> list[Dress]:
        stmt = (
            select(Dress)
            .where(*self._scope(tenant_id, archived=archived, search=search))
            # All four keys of idx_dresses_tenant_active: with sort_order and
            # created_at tied, id is what keeps a page from repeating or
            # skipping a row under concurrent inserts.
            .order_by(Dress.sort_order, Dress.created_at.desc(), Dress.id)
            .offset(offset)
            .limit(limit)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def count(
        self, session: AsyncSession, tenant_id: UUID, *, archived: bool, search: str | None
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(Dress)
            .where(*self._scope(tenant_id, archived=archived, search=search))
        )
        return (await session.execute(stmt)).scalar_one()

    async def list_for_picker(
        self, session: AsyncSession, tenant_id: UUID, *, limit: int
    ) -> list[Dress]:
        """The floor's one-shot dress list (F36 D16) — fetched when the dress
        dialog opens, never on the poll.

        `ORDER BY sort_order, name, id` and NOT `list_page`'s
        `created_at DESC`: a picker is scanned by a human looking for a name,
        where the catalog page is read newest-first. Live dresses only, and the
        caller renders a one-line «truncated» notice when it gets `limit` rows
        back rather than silently hiding gowns.

        It lives on this repository rather than on a fitting-room one because
        this file owns every query against `dresses` — but the DISCLOSURE
        argument is F36's: name and size labels are strictly less than the
        boutique's own storefront already publishes to an anonymous visitor
        (`storefront/service.py`), which is what lets the floor router answer it
        for all five roles when the catalog router admits only two.
        """
        stmt = (
            select(Dress)
            .where(Dress.tenant_id == tenant_id, Dress.deleted_at.is_(None))
            .order_by(Dress.sort_order, Dress.name, Dress.id)
            .limit(limit)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        name: str,
        description: str | None,
        price_agorot: int | None,
        price_visible: bool,
        reserved: bool,
        sort_order: int,
    ) -> Dress:
        row = Dress(
            tenant_id=tenant_id,
            name=name,
            description=description,
            price_agorot=price_agorot,
            price_visible=price_visible,
            reserved=reserved,
            sort_order=sort_order,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def update_fields(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        dress_id: UUID,
        *,
        name: str,
        description: str | None,
        price_agorot: int | None,
        price_visible: bool,
        reserved: bool,
        sort_order: int,
    ) -> Dress | None:
        row = await self.by_id(session, tenant_id, dress_id)
        if row is None:
            return None
        row.name = name
        row.description = description
        row.price_agorot = price_agorot
        row.price_visible = price_visible
        row.reserved = reserved
        row.sort_order = sort_order
        await session.flush()
        await session.refresh(row)  # picks up the trigger-maintained updated_at
        return row

    async def soft_delete(self, session: AsyncSession, tenant_id: UUID, dress_id: UUID) -> bool:
        stmt = (
            update(Dress)
            .where(
                Dress.tenant_id == tenant_id,
                Dress.id == dress_id,
                Dress.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(Dress.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def restore(self, session: AsyncSession, tenant_id: UUID, dress_id: UUID) -> bool:
        stmt = (
            update(Dress)
            .where(
                Dress.tenant_id == tenant_id,
                Dress.id == dress_id,
                Dress.deleted_at.is_not(None),
            )
            .values(deleted_at=None)
            .returning(Dress.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None
