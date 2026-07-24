import dataclasses
import datetime
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.constants import DressMediaStatus
from app.models.dress_media import DressMedia


@dataclasses.dataclass(frozen=True)
class MediaCover:
    """The list's fourth statement in one row per dress: the first ready photo
    plus how many ready photos that dress has."""

    row: DressMedia
    media_count: int


def _stale_before(ttl_seconds: int) -> ColumnElement[Any]:
    """`now() - ttl`, computed by the database. created_at is stamped with
    transaction_timestamp(), so comparing it against an application clock would
    make the sweep depend on two clocks agreeing. make_interval's positional
    arguments are (years, months, weeks, days, hours, mins, secs)."""
    return func.now() - func.make_interval(0, 0, 0, 0, 0, 0, ttl_seconds)


class DressMediaRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see AppointmentTypesRepository).

    Every method carries all three of (tenant_id, dress_id, media_id) in its
    WHERE alongside `deleted_at IS NULL`: a media id that exists but belongs to
    a *different dress of the same tenant* must be a miss, never a silent
    re-parent.
    """

    async def by_id(
        self, session: AsyncSession, tenant_id: UUID, dress_id: UUID, media_id: UUID
    ) -> DressMedia | None:
        stmt = select(DressMedia).where(
            DressMedia.tenant_id == tenant_id,
            DressMedia.dress_id == dress_id,
            DressMedia.id == media_id,
            DressMedia.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()

    async def list_ready(
        self, session: AsyncSession, tenant_id: UUID, dress_id: UUID
    ) -> list[DressMedia]:
        """The gallery read path — ready rows only. A pending row is an
        unverified object and must never reach a signed URL."""
        stmt = (
            select(DressMedia)
            .where(
                DressMedia.tenant_id == tenant_id,
                DressMedia.dress_id == dress_id,
                DressMedia.deleted_at.is_(None),
                DressMedia.status == DressMediaStatus.READY,
            )
            .order_by(DressMedia.sort_order, DressMedia.id)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def covers_by_dress(
        self, session: AsyncSession, tenant_id: UUID, dress_ids: Sequence[UUID]
    ) -> dict[UUID, MediaCover]:
        if not dress_ids:
            return {}
        # DISTINCT ON picks the cover; the window count runs before DISTINCT, so
        # media_count still sees every ready row of the dress. One statement for
        # the whole page, never one per row.
        stmt = (
            select(
                DressMedia,
                func.count().over(partition_by=DressMedia.dress_id).label("media_count"),
            )
            .where(
                DressMedia.tenant_id == tenant_id,
                DressMedia.dress_id.in_(dress_ids),
                DressMedia.deleted_at.is_(None),
                DressMedia.status == DressMediaStatus.READY,
            )
            .distinct(DressMedia.dress_id)
            .order_by(DressMedia.dress_id, DressMedia.sort_order, DressMedia.id)
        )
        rows = (await session.execute(stmt)).all()
        return {row.dress_id: MediaCover(row=row, media_count=count) for row, count in rows}

    async def count_active(
        self, session: AsyncSession, tenant_id: UUID, dress_id: UUID, *, ttl_seconds: int
    ) -> int:
        """Ready rows plus pendings young enough to still be someone's upload in
        flight. An abandoned pending stops occupying a gallery slot rather than
        locking it for an hour."""
        stmt = (
            select(func.count())
            .select_from(DressMedia)
            .where(
                DressMedia.tenant_id == tenant_id,
                DressMedia.dress_id == dress_id,
                DressMedia.deleted_at.is_(None),
                or_(
                    DressMedia.status == DressMediaStatus.READY,
                    DressMedia.created_at >= _stale_before(ttl_seconds),
                ),
            )
        )
        return (await session.execute(stmt)).scalar_one()

    async def max_ready_sort_order(
        self, session: AsyncSession, tenant_id: UUID, dress_id: UUID
    ) -> int:
        """-1 for an empty gallery, so the caller's `+ 1` yields the first slot."""
        stmt = select(func.coalesce(func.max(DressMedia.sort_order), -1)).where(
            DressMedia.tenant_id == tenant_id,
            DressMedia.dress_id == dress_id,
            DressMedia.deleted_at.is_(None),
            DressMedia.status == DressMediaStatus.READY,
        )
        return (await session.execute(stmt)).scalar_one()

    async def insert_pending(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        dress_id: UUID,
        media_id: UUID,
        storage_key: str,
        content_type: str,
        byte_size: int,
    ) -> DressMedia:
        """media_id and storage_key are both required arguments: the key embeds
        the row's own id, so the service mints the id client-side and this is the
        single, only statement that writes the key. It is never patched
        afterwards and never mutated."""
        row = DressMedia(
            id=media_id,
            tenant_id=tenant_id,
            dress_id=dress_id,
            storage_key=storage_key,
            content_type=content_type,
            byte_size=byte_size,
            status=DressMediaStatus.PENDING,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def sweep_stale_pendings(
        self, session: AsyncSession, tenant_id: UUID, dress_id: UUID, *, ttl_seconds: int
    ) -> list[tuple[UUID, str]]:
        """Soft-deletes abandoned pendings and hands back their (id, key) pairs.
        The sweep is the only holder of those keys, so returning them is what
        bounds the orphan window instead of leaving the objects forever."""
        stmt = (
            update(DressMedia)
            .where(
                DressMedia.tenant_id == tenant_id,
                DressMedia.dress_id == dress_id,
                DressMedia.deleted_at.is_(None),
                DressMedia.status == DressMediaStatus.PENDING,
                DressMedia.created_at < _stale_before(ttl_seconds),
            )
            .values(deleted_at=func.now())
            .returning(DressMedia.id, DressMedia.storage_key)
            # The only statement here whose RETURNING is more than the primary
            # key: session synchronisation would want that RETURNING for itself.
            # Nothing re-reads these rows in this session, so opt out rather than
            # let the two contend.
            .execution_options(synchronize_session=False)
        )
        return [(media_id, key) for media_id, key in (await session.execute(stmt)).all()]

    async def promote_to_ready(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        dress_id: UUID,
        media_id: UUID,
        *,
        sort_order: int,
    ) -> bool:
        """The `status = 'pending'` predicate is confirm's idempotency guard: a
        retried confirm updates zero rows instead of double-bumping sort_order.
        The caller holds the per-dress media advisory lock."""
        stmt = (
            update(DressMedia)
            .where(
                DressMedia.tenant_id == tenant_id,
                DressMedia.dress_id == dress_id,
                DressMedia.id == media_id,
                DressMedia.deleted_at.is_(None),
                DressMedia.status == DressMediaStatus.PENDING,
            )
            .values(status=DressMediaStatus.READY, sort_order=sort_order)
            .returning(DressMedia.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def set_sort_order(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        dress_id: UUID,
        media_id: UUID,
        sort_order: int,
    ) -> bool:
        stmt = (
            update(DressMedia)
            .where(
                DressMedia.tenant_id == tenant_id,
                DressMedia.dress_id == dress_id,
                DressMedia.id == media_id,
                DressMedia.deleted_at.is_(None),
                DressMedia.status == DressMediaStatus.READY,
            )
            .values(sort_order=sort_order)
            .returning(DressMedia.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def soft_delete(
        self, session: AsyncSession, tenant_id: UUID, dress_id: UUID, media_id: UUID
    ) -> bool:
        """Accepts a row in EITHER status: deleting a pending row frees a gallery
        slot immediately and is the client's abort path after a failed upload."""
        stmt = (
            update(DressMedia)
            .where(
                DressMedia.tenant_id == tenant_id,
                DressMedia.dress_id == dress_id,
                DressMedia.id == media_id,
                DressMedia.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(DressMedia.id)
        )
        return (await session.execute(stmt)).scalar_one_or_none() is not None

    async def soft_delete_all(self, session: AsyncSession, tenant_id: UUID, dress_id: UUID) -> int:
        """First step of the archive cascade. The `deleted_at IS NULL` predicate
        is what leaves an individually-deleted photo on its older stamp."""
        stmt = (
            update(DressMedia)
            .where(
                DressMedia.tenant_id == tenant_id,
                DressMedia.dress_id == dress_id,
                DressMedia.deleted_at.is_(None),
            )
            .values(deleted_at=func.now())
            .returning(DressMedia.id)
        )
        return len((await session.execute(stmt)).scalars().all())

    async def restore_archived_with(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        dress_id: UUID,
        archived_at: datetime.datetime,
    ) -> int:
        """Only the rows the archive itself stamped — so a photo the owner
        deleted last week stays deleted through an archive/restore cycle."""
        stmt = (
            update(DressMedia)
            .where(
                DressMedia.tenant_id == tenant_id,
                DressMedia.dress_id == dress_id,
                DressMedia.deleted_at == archived_at,
            )
            .values(deleted_at=None)
            .returning(DressMedia.id)
        )
        return len((await session.execute(stmt)).scalars().all())
