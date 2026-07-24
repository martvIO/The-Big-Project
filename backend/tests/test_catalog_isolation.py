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
vacuously pass. The endpoint half at the bottom re-proves the same invariants
through the HTTP surface, where the tenant comes from the request host.
"""

import asyncio
import time
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.catalog.router import get_media_storage
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
from app.main import create_app
from app.storage.memory import InMemoryMediaStorage
from app.tenancy.middleware import TenantContext

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


# --- the endpoint half: the same invariants through the HTTP surface ---

TOKEN = "session-token-isolation"
SLUG_A = "tenanta"
SLUG_B = "tenantb"

UPDATE_BODY: dict[str, Any] = {
    "name": "Hijack",
    "description": None,
    "price_agorot": None,
    "price_visible": False,
    "reserved": True,
    "sort_order": 0,
}
VARIANTS_BODY: dict[str, Any] = {"variants": [{"size_label": "52", "quantity": 9}]}
PRESIGN_BODY: dict[str, Any] = {"content_type": JPEG, "byte_size": len(JPEG_BODY)}


class _OwnerOfWhicheverTenantResolved:
    """Duck-typed AuthService. Authentication is deliberately NOT the variable
    under test here: every probe below arrives as a fully authenticated owner of
    whatever tenant the request host resolved to, so a 404 can only come from
    RLS plus the explicit tenant_id/dress_id predicates."""

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        if token != TOKEN:
            return None
        return StaffContext(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            email="owner@example.test",
            display_name="Owner",
            role="owner",
        )


def _isolation_app(
    factory: async_sessionmaker[AsyncSession],
    storage: InMemoryMediaStorage,
    tenants: dict[str, TenantContext],
) -> FastAPI:
    async def _resolver(slug: str) -> TenantContext | None:
        return tenants.get(slug)

    app = create_app(resolver=_resolver)
    auth = _OwnerOfWhicheverTenantResolved()
    app.state.auth_service = auth
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.state.media_storage = storage
    app.dependency_overrides[get_media_storage] = lambda: storage
    app.state.catalog_service = _service(factory, storage)
    return app


def _authed_client(app: FastAPI, slug: str) -> TestClient:
    client = TestClient(app, base_url=f"http://{slug}.localtest.me")
    client.cookies.set("boutique_session", TOKEN, domain=f"{slug}.localtest.me")
    return client


def test_endpoints_are_404_for_another_tenants_ids(app_role_url: str) -> None:
    """Every /manage/dresses route probed as tenant A against tenant B's ids.
    tenant_id is host-derived, so the only way to address B is to be B."""
    # NullPool: the engine built here is used from TestClient's own event loop,
    # so no connection may be pooled across loops.
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant_a = TenantContext(id=uuid.uuid4(), slug=SLUG_A, settings={})
    tenant_b = TenantContext(id=uuid.uuid4(), slug=SLUG_B, settings={})
    try:
        dress_b, media_b = asyncio.run(_dress_with_photo(service, storage, tenant_b.id, "Belle"))
        app = _isolation_app(factory, storage, {SLUG_A: tenant_a, SLUG_B: tenant_b})

        probes: list[tuple[str, str, dict[str, Any] | None]] = [
            ("GET", f"/manage/dresses/{dress_b}", None),
            ("PATCH", f"/manage/dresses/{dress_b}", UPDATE_BODY),
            ("DELETE", f"/manage/dresses/{dress_b}", None),
            ("POST", f"/manage/dresses/{dress_b}/restore", None),
            ("PUT", f"/manage/dresses/{dress_b}/variants", VARIANTS_BODY),
            ("POST", f"/manage/dresses/{dress_b}/media/presign", PRESIGN_BODY),
            ("POST", f"/manage/dresses/{dress_b}/media/{media_b}/confirm", None),
            ("DELETE", f"/manage/dresses/{dress_b}/media/{media_b}", None),
            ("PUT", f"/manage/dresses/{dress_b}/media/order", {"media_ids": [str(media_b)]}),
        ]
        with _authed_client(app, SLUG_A) as client:
            for method, path, body in probes:
                resp = client.request(method, path, json=body)
                assert resp.status_code == 404, f"{method} {path} → {resp.status_code}"
                # Indistinguishable from a missing row, by design.
                assert resp.json()["error"]["code"] == "NOT_FOUND"
            listed = client.get("/manage/dresses")
        assert listed.status_code == 200
        assert listed.json()["total"] == 0

        # B's dress survived every probe: not renamed, not archived, still has
        # its photo.
        with _authed_client(app, SLUG_B) as client:
            intact = client.get(f"/manage/dresses/{dress_b}")
        assert intact.status_code == 200
        body = intact.json()
        assert body["name"] == "Belle"
        assert body["archived"] is False
        assert [item["id"] for item in body["media"]] == [str(media_b)]
    finally:
        asyncio.run(engine.dispose())


def test_media_addressed_through_the_wrong_dress_url_is_refused(app_role_url: str) -> None:
    """The within-tenant half over HTTP: without dress_id in the WHERE, confirm
    or delete through another dress's URL would silently re-parent the photo."""
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant_a = TenantContext(id=uuid.uuid4(), slug=SLUG_A, settings={})
    try:
        dress_one, media_one = asyncio.run(
            _dress_with_photo(service, storage, tenant_a.id, "Aurora")
        )
        dress_two, media_two = asyncio.run(
            _dress_with_photo(service, storage, tenant_a.id, "Camellia")
        )
        app = _isolation_app(factory, storage, {SLUG_A: tenant_a})

        with _authed_client(app, SLUG_A) as client:
            confirmed = client.post(f"/manage/dresses/{dress_two}/media/{media_one}/confirm")
            deleted = client.delete(f"/manage/dresses/{dress_two}/media/{media_one}")
            reordered = client.put(
                f"/manage/dresses/{dress_two}/media/order",
                json={"media_ids": [str(media_one)]},
            )
            intact_one = client.get(f"/manage/dresses/{dress_one}")
            intact_two = client.get(f"/manage/dresses/{dress_two}")

        assert confirmed.status_code == 404
        assert confirmed.json()["error"]["code"] == "NOT_FOUND"
        assert deleted.status_code == 404
        assert deleted.json()["error"]["code"] == "NOT_FOUND"
        # Reorder answers the conflict code rather than 404 — an unknown id in
        # the payload is a MEDIA_ORDER_MISMATCH by spec. Either way the refusal
        # is total: dress two never adopts dress one's photo.
        assert reordered.status_code == 409
        assert reordered.json()["error"]["code"] == "MEDIA_ORDER_MISMATCH"

        assert [item["id"] for item in intact_one.json()["media"]] == [str(media_one)]
        assert [item["id"] for item in intact_two.json()["media"]] == [str(media_two)]
    finally:
        asyncio.run(engine.dispose())


def test_presigned_key_over_http_carries_only_the_host_derived_tenant(
    app_role_url: str,
) -> None:
    """The tenant-prefix invariant at the HTTP boundary: the request body has no
    field that can influence the key, and the prefix comes from the host."""
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant_a = TenantContext(id=uuid.uuid4(), slug=SLUG_A, settings={})
    tenant_b = TenantContext(id=uuid.uuid4(), slug=SLUG_B, settings={})
    try:
        dress_a, _ = asyncio.run(_dress_with_photo(service, storage, tenant_a.id, "Aurora"))
        app = _isolation_app(factory, storage, {SLUG_A: tenant_a, SLUG_B: tenant_b})

        with _authed_client(app, SLUG_A) as client:
            resp = client.post(
                f"/manage/dresses/{dress_a}/media/presign",
                json={**PRESIGN_BODY, "key": f"tenants/{tenant_b.id}/evil.jpg"},
            )
            # An extra key is a house-shape 400, never a silently ignored field.
            assert resp.status_code == 400
            assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

            honest = client.post(f"/manage/dresses/{dress_a}/media/presign", json=PRESIGN_BODY)
        assert honest.status_code == 200
        key = honest.json()["fields"]["key"]
        assert key.startswith(f"tenants/{tenant_a.id}/dresses/{dress_a}/media/")
        assert str(tenant_b.id) not in key
    finally:
        asyncio.run(engine.dispose())
