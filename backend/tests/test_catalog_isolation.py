"""Feature 8's rows in the permanent cross-tenant isolation suite.

Every new repository method and every new service method is probed as tenant A
against tenant B's ids and must return nothing — an unknown id, an archived
dress and another tenant's dress are one indistinguishable miss, by design.

Two cases beyond plain cross-tenant reads:
  * WITHIN one tenant, dress A's media id addressed through dress B's id is also
    a miss — every media method carries all three of (tenant_id, dress_id,
    media_id), so a wrong parent is never a silent re-parent.
  * a storage key generated while bound to A never contains any of B's ids.

Runs as the non-owner boutique_app role over a NullPool engine: the container
superuser bypasses RLS unconditionally, which would make every assertion here
vacuously pass. The endpoint half of this suite lands with the router.
"""

import time
import uuid

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.catalog.service import (
    CatalogNotFoundError,
    CatalogService,
    MediaOrderMismatchError,
)
from app.catalog.validation import VariantInput
from app.db.repositories.dress_media import DressMediaRepository
from app.db.repositories.dress_variants import DressVariantsRepository
from app.db.repositories.dresses import DressesRepository
from app.db.tenant import tenant_session
from app.storage.memory import InMemoryMediaStorage

pytestmark = pytest.mark.db

JPEG = "image/jpeg"
JPEG_BODY = b"\xff\xd8\xff" + b"\x00" * 1021


def _engine(app_role_url: str) -> AsyncEngine:
    # NullPool: probes must not share a connection whose tenant context could
    # otherwise be mistaken for isolation.
    return create_async_engine(app_role_url, poolclass=NullPool)


def _factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def _service(
    factory: async_sessionmaker[AsyncSession], storage: InMemoryMediaStorage
) -> CatalogService:
    return CatalogService(
        factory,
        media_storage=storage,
        presign_rate_limiter=FixedWindowRateLimiter(
            max_attempts=10_000, window_seconds=3600, clock=time.monotonic
        ),
    )


async def _dress_with_photo(
    service: CatalogService, storage: InMemoryMediaStorage, tenant_id: uuid.UUID, name: str
) -> tuple[uuid.UUID, uuid.UUID]:
    """A dress carrying one variant and one confirmed photo — the full surface
    every probe below is aimed at."""
    dress = await service.create_dress(
        tenant_id,
        name=name,
        description=None,
        price_agorot=120_000,
        price_visible=True,
        reserved=False,
        sort_order=0,
    )
    await service.replace_variants(
        tenant_id, dress.row.id, [VariantInput(size_label="38", quantity=2, sort_order=0)]
    )
    presigned = await service.presign_media(
        tenant_id, dress.row.id, content_type=JPEG, byte_size=len(JPEG_BODY)
    )
    storage.put(key=presigned.fields["key"], content_type=JPEG, body=JPEG_BODY)
    await service.confirm_media(tenant_id, dress.row.id, presigned.media_id)
    return dress.row.id, presigned.media_id


async def test_repositories_return_nothing_for_another_tenants_ids(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    dresses = DressesRepository()
    variants = DressVariantsRepository()
    media = DressMediaRepository()
    try:
        dress_id, media_id = await _dress_with_photo(service, storage, tenant_a, "Aurora")

        async with tenant_session(factory, tenant_b) as session:
            assert await dresses.by_id(session, tenant_b, dress_id) is None
            assert await dresses.by_id_any_state(session, tenant_b, dress_id) is None
            assert (
                await dresses.list_page(
                    session, tenant_b, archived=False, search=None, offset=0, limit=100
                )
                == []
            )
            assert await dresses.count(session, tenant_b, archived=False, search=None) == 0
            assert await dresses.soft_delete(session, tenant_b, dress_id) is False
            assert await dresses.restore(session, tenant_b, dress_id) is False

            assert await variants.list_active(session, tenant_b, dress_id) == []
            assert await variants.aggregate_by_dress(session, tenant_b, [dress_id]) == {}
            assert await variants.soft_delete_all(session, tenant_b, dress_id) == 0

            assert await media.by_id(session, tenant_b, dress_id, media_id) is None
            assert await media.list_ready(session, tenant_b, dress_id) == []
            assert await media.covers_by_dress(session, tenant_b, [dress_id]) == {}
            assert await media.count_active(session, tenant_b, dress_id, ttl_seconds=3600) == 0
            assert await media.max_ready_sort_order(session, tenant_b, dress_id) == -1
            assert (
                await media.sweep_stale_pendings(session, tenant_b, dress_id, ttl_seconds=0) == []
            )
            assert (
                await media.promote_to_ready(session, tenant_b, dress_id, media_id, sort_order=0)
                is False
            )
            assert await media.set_sort_order(session, tenant_b, dress_id, media_id, 5) is False
            assert await media.soft_delete(session, tenant_b, dress_id, media_id) is False
            assert await media.soft_delete_all(session, tenant_b, dress_id) == 0

        # A's rows survived every probe untouched.
        detail = await service.get_dress(tenant_a, dress_id)
        assert [variant.size_label for variant in detail.variants] == ["38"]
        assert [item.row.id for item in detail.media] == [media_id]
        assert detail.row.deleted_at is None
    finally:
        await engine.dispose()


async def test_service_methods_are_404_for_another_tenants_dress(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    try:
        dress_id, media_id = await _dress_with_photo(service, storage, tenant_a, "Aurora")

        with pytest.raises(CatalogNotFoundError):
            await service.get_dress(tenant_b, dress_id)
        with pytest.raises(CatalogNotFoundError):
            await service.update_dress(
                tenant_b,
                dress_id,
                name="Hijack",
                description=None,
                price_agorot=None,
                price_visible=False,
                reserved=True,
                sort_order=0,
            )
        with pytest.raises(CatalogNotFoundError):
            await service.archive_dress(tenant_b, dress_id)
        with pytest.raises(CatalogNotFoundError):
            await service.restore_dress(tenant_b, dress_id)
        with pytest.raises(CatalogNotFoundError):
            await service.replace_variants(
                tenant_b, dress_id, [VariantInput(size_label="52", quantity=9, sort_order=0)]
            )
        with pytest.raises(CatalogNotFoundError):
            await service.presign_media(
                tenant_b, dress_id, content_type=JPEG, byte_size=len(JPEG_BODY)
            )
        with pytest.raises(CatalogNotFoundError):
            await service.confirm_media(tenant_b, dress_id, media_id)
        with pytest.raises(CatalogNotFoundError):
            await service.delete_media(tenant_b, dress_id, media_id)
        with pytest.raises(CatalogNotFoundError):
            await service.reorder_media(tenant_b, dress_id, [media_id])

        # B's own list never sees A's dress, and A's dress is unchanged.
        assert (await service.list_dresses(tenant_b)).total == 0
        untouched = await service.get_dress(tenant_a, dress_id)
        assert untouched.row.name == "Aurora"
        assert untouched.row.reserved is False
        assert [variant.size_label for variant in untouched.variants] == ["38"]
        assert [item.row.id for item in untouched.media] == [media_id]
    finally:
        await engine.dispose()


async def test_media_addressed_through_the_wrong_dress_of_the_same_tenant_is_a_miss(
    app_role_url: str,
) -> None:
    """The within-tenant half: without dress_id in the WHERE, confirming or
    deleting through another dress's id would silently re-parent the photo."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    media_repo = DressMediaRepository()
    try:
        dress_a, media_a = await _dress_with_photo(service, storage, tenant, "Aurora")
        dress_b, media_b = await _dress_with_photo(service, storage, tenant, "Belle")

        async with tenant_session(factory, tenant) as session:
            assert await media_repo.by_id(session, tenant, dress_b, media_a) is None

        with pytest.raises(CatalogNotFoundError):
            await service.confirm_media(tenant, dress_b, media_a)
        with pytest.raises(CatalogNotFoundError):
            await service.delete_media(tenant, dress_b, media_a)
        # Reorder answers the conflict code rather than 404 — the spec's own rule
        # is that an unknown id in the payload is a MEDIA_ORDER_MISMATCH. Either
        # way the refusal is total: dress B never adopts dress A's photo.
        with pytest.raises(MediaOrderMismatchError):
            await service.reorder_media(tenant, dress_b, [media_a])

        for dress_id, media_id in ((dress_a, media_a), (dress_b, media_b)):
            intact = await service.get_dress(tenant, dress_id)
            assert [item.row.id for item in intact.media] == [media_id]
    finally:
        await engine.dispose()


async def test_a_key_minted_for_one_tenant_never_carries_another_tenants_ids(
    app_role_url: str,
) -> None:
    """The tenant-prefix invariant end to end: tenant_id comes only from the
    host-derived context and dress_id only from a row this tenant owns, so no
    client-supplied value can reach an S3 key."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    try:
        dress_a, _ = await _dress_with_photo(service, storage, tenant_a, "Aurora")
        dress_b, _ = await _dress_with_photo(service, storage, tenant_b, "Belle")

        presigned = await service.presign_media(
            tenant_a, dress_a, content_type=JPEG, byte_size=len(JPEG_BODY)
        )
        key = presigned.fields["key"]
        assert key.startswith(f"tenants/{tenant_a}/dresses/{dress_a}/media/")
        assert str(tenant_b) not in key
        assert str(dress_b) not in key

        async with tenant_session(factory, tenant_a) as session:
            row = await DressMediaRepository().by_id(session, tenant_a, dress_a, presigned.media_id)
        assert row is not None
        assert row.storage_key == key
    finally:
        await engine.dispose()
