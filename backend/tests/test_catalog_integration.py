"""Feature 8 catalog on real Postgres as boutique_app — everything that is
unprovable on the local no-Docker loop: migration 0006's named indexes, the
app_user CRUD grants and CHECK bounds; then the repositories and CatalogService
under real concurrency, real advisory locks and a real query planner.

Runs as the non-owner application role, never as the container superuser: GRANT
and FORCE-RLS correctness are vacuous when the connecting principal owns the
tables.
"""

import asyncio
import contextlib
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
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
    DressView,
    DuplicateSizeError,
    MediaLimitReachedError,
    MediaMismatchError,
    MediaNotUploadedError,
    MediaOrderMismatchError,
    PresignResult,
    StockSummary,
)
from app.catalog.validation import (
    MAX_MEDIA_PER_DRESS,
    VariantInput,
)
from app.db.repositories.dress_media import DressMediaRepository
from app.db.repositories.dress_variants import DressVariantsRepository
from app.db.tenant import tenant_connection, tenant_session
from app.storage.memory import InMemoryMediaStorage

pytestmark = pytest.mark.db

BACKEND_DIR = Path(__file__).resolve().parent.parent

TENANT_ID = uuid.UUID("33333333-3333-4333-8333-333333333333")
DRESS_ID = uuid.UUID("44444444-4444-4444-8444-444444444444")

JPEG = "image/jpeg"
JPEG_BODY = b"\xff\xd8\xff" + b"\x00" * 1021
HTML_BODY = b"<!DOCTYPE html><script>alert(1)</script>" + b" " * 985

CATALOG_TABLES = ("dresses", "dress_variants", "dress_media")

CATALOG_INDEXES = {
    "idx_dresses_tenant_active",
    "idx_dresses_tenant_archived",
    "idx_dress_variants_dress_active",
    "idx_dress_variants_dress_size_unique",
    "idx_dress_media_dress_ready",
    "idx_dress_media_pending",
    "idx_dress_media_storage_key_unique",
}

_MEDIA_INSERT = """
    INSERT INTO dress_media (tenant_id, dress_id, storage_key, content_type, byte_size, status)
    VALUES (:tenant_id, :dress_id, :storage_key, :content_type, :byte_size, :status)
"""


def _media_params(*, storage_key: str, **overrides: object) -> dict[str, object]:
    params: dict[str, object] = {
        "tenant_id": TENANT_ID,
        "dress_id": DRESS_ID,
        "storage_key": f"tenants/{TENANT_ID}/dresses/{DRESS_ID}/media/{storage_key}.jpg",
        "content_type": "image/jpeg",
        "byte_size": 1024,
        "status": "pending",
    }
    params.update(overrides)
    return params


async def test_every_catalog_index_exists(app_role_url: str) -> None:
    engine = create_async_engine(app_role_url)
    try:
        async with engine.connect() as engine_conn:
            present = (
                (
                    await engine_conn.execute(
                        text("SELECT indexname FROM pg_indexes WHERE schemaname = 'public'")
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()
    assert CATALOG_INDEXES - set(present) == set()


async def test_app_user_holds_crud_on_every_catalog_table(app_role_url: str) -> None:
    """Nothing here is append-only, so all four privileges must be granted —
    a copied REVOKE dance would break every UPDATE the service issues."""
    engine = create_async_engine(app_role_url)
    try:
        async with engine.connect() as engine_conn:
            for table in CATALOG_TABLES:
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    granted = await engine_conn.execute(
                        text("SELECT has_table_privilege('app_user', :table, :privilege)"),
                        {"table": table, "privilege": privilege},
                    )
                    assert granted.scalar_one() is True, f"app_user lacks {privilege} on {table}"
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    ("statement", "params"),
    [
        pytest.param(
            _MEDIA_INSERT,
            _media_params(storage_key="svg", content_type="image/svg+xml"),
            id="content_type_outside_the_accepted_set",
        ),
        pytest.param(
            _MEDIA_INSERT,
            _media_params(storage_key="oversize", byte_size=20971521),
            id="byte_size_above_the_2x_ceiling",
        ),
        pytest.param(
            _MEDIA_INSERT,
            _media_params(storage_key="processing", status="processing"),
            id="status_outside_the_accepted_set",
        ),
        pytest.param(
            """
            INSERT INTO dress_variants (tenant_id, dress_id, size_label, quantity)
            VALUES (:tenant_id, :dress_id, '38', -1)
            """,
            {"tenant_id": TENANT_ID, "dress_id": DRESS_ID},
            id="negative_quantity",
        ),
        pytest.param(
            """
            INSERT INTO dresses (tenant_id, name, price_agorot)
            VALUES (:tenant_id, 'Free dress', 0)
            """,
            {"tenant_id": TENANT_ID},
            id="zero_price",
        ),
    ],
)
async def test_check_constraints_reject_out_of_bound_writes(
    app_role_url: str, statement: str, params: dict[str, object]
) -> None:
    """An accepted content type and an accepted status are security boundaries,
    not duplication: an image/svg+xml object served from our bucket is stored
    XSS, and a status the confirm path never wrote would expose an unverified
    object. Widening either must be a deliberate migration."""
    engine = create_async_engine(app_role_url)
    try:
        with pytest.raises(IntegrityError):
            async with tenant_connection(engine, TENANT_ID) as conn:
                await conn.execute(text(statement), params)
    finally:
        await engine.dispose()


# --- repositories + service on the real engine ---


def _engine(app_role_url: str) -> AsyncEngine:
    # NullPool: the concurrency tests below need genuinely separate connections.
    # A pooled engine silently serialises the very races they assert.
    return create_async_engine(app_role_url, poolclass=NullPool)


def _factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def _service(
    factory: async_sessionmaker[AsyncSession],
    storage: InMemoryMediaStorage,
    *,
    pending_ttl_seconds: int = 3600,
    max_presigns: int = 10_000,
) -> CatalogService:
    return CatalogService(
        factory,
        media_storage=storage,
        presign_rate_limiter=FixedWindowRateLimiter(
            max_attempts=max_presigns, window_seconds=3600, clock=time.monotonic
        ),
        pending_ttl_seconds=pending_ttl_seconds,
    )


async def _dress(service: CatalogService, tenant_id: uuid.UUID, name: str = "Aurora") -> uuid.UUID:
    created = await service.create_dress(
        tenant_id,
        name=name,
        description=None,
        price_agorot=None,
        price_visible=True,
        reserved=False,
        sort_order=0,
    )
    return created.row.id


async def _upload(
    service: CatalogService,
    storage: InMemoryMediaStorage,
    tenant_id: uuid.UUID,
    dress_id: uuid.UUID,
    *,
    body: bytes = JPEG_BODY,
) -> PresignResult:
    """Presign, then simulate the browser's POST by putting the object under the
    exact key the policy pinned."""
    presigned = await service.presign_media(
        tenant_id, dress_id, content_type=JPEG, byte_size=len(body)
    )
    storage.put(key=presigned.fields["key"], content_type=JPEG, body=body)
    return presigned


async def _pending_count(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> int:
    async with tenant_session(factory, tenant_id) as session:
        result = await session.execute(
            text("SELECT count(*) FROM dress_media WHERE status = 'pending' AND deleted_at IS NULL")
        )
        return int(result.scalar_one())


async def test_dress_crud_lifecycle(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        created = await service.create_dress(
            tenant,
            name="Aurora",
            description="Ivory silk",
            price_agorot=1_200_00,
            price_visible=True,
            reserved=False,
            sort_order=2,
        )
        # Zero variants is out_of_stock by derivation, never by a stored flag.
        assert created.summary.out_of_stock is True
        assert created.summary.variant_count == 0
        assert created.media_count == 0
        assert created.cover is None

        updated = await service.update_dress(
            tenant,
            created.row.id,
            name="Aurora II",
            description=None,
            price_agorot=None,
            price_visible=False,
            reserved=True,
            sort_order=5,
        )
        assert updated.row.name == "Aurora II"
        assert updated.row.description is None
        assert updated.row.price_agorot is None
        assert updated.row.reserved is True
        assert updated.row.updated_at is not None  # set by the DB trigger

        page = await service.list_dresses(tenant)
        assert [item.row.id for item in page.items] == [created.row.id]
        assert page.total == 1

        # ILIKE with escaped wildcards: a literal % must not become a scan.
        assert (await service.list_dresses(tenant, search="aurora")).total == 1
        assert (await service.list_dresses(tenant, search="%")).total == 0
    finally:
        await engine.dispose()


async def test_variant_replace_is_a_full_replacement(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)

        first = await service.replace_variants(
            tenant,
            dress_id,
            [
                VariantInput(size_label=" 38 ", quantity=2, sort_order=0),
                VariantInput(size_label="US  6", quantity=0, sort_order=1),
            ],
        )
        assert [variant.size_label for variant in first.variants] == ["38", "US 6"]
        assert first.summary.total_quantity == 2
        assert first.summary.variant_count == 2
        assert first.summary.out_of_stock is False

        second = await service.replace_variants(
            tenant, dress_id, [VariantInput(size_label="42", quantity=0, sort_order=0)]
        )
        assert [variant.size_label for variant in second.variants] == ["42"]
        assert second.summary.out_of_stock is True

        cleared = await service.replace_variants(tenant, dress_id, [])
        assert cleared.variants == []
        assert cleared.summary.variant_count == 0
        assert cleared.summary.out_of_stock is True
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    "labels",
    [
        pytest.param(("38", "38"), id="identical"),
        pytest.param(("38", " 38 "), id="whitespace_variant"),
        pytest.param(("US 6", "us 6"), id="case_variant"),
        pytest.param(("US 6", "US  6"), id="internal_whitespace_variant"),
    ],
)
async def test_duplicate_sizes_are_refused(app_role_url: str, labels: tuple[str, str]) -> None:
    """Normalisation collapses whitespace; lower() in the partial unique index
    catches the rest. Either way it is a clean 409, never a raw 500."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        with pytest.raises(DuplicateSizeError):
            await service.replace_variants(
                tenant,
                dress_id,
                [
                    VariantInput(size_label=labels[0], quantity=1, sort_order=0),
                    VariantInput(size_label=labels[1], quantity=1, sort_order=1),
                ],
            )
        detail = await service.get_dress(tenant, dress_id)
        assert detail.variants == []
    finally:
        await engine.dispose()


async def test_partial_unique_index_is_the_backstop_below_the_service(app_role_url: str) -> None:
    """The service rejects in-payload duplicates before touching the DB, so the
    lower(size_label) index only fires on a concurrent race — asserted here
    directly through the repository. It must be an IntegrityError, which is what
    replace_variants maps to DUPLICATE_SIZE instead of letting a 500 out."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    variants = DressVariantsRepository()
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant) as session:
                for label in ("US 6", "us 6"):
                    await variants.insert(
                        session,
                        tenant_id=tenant,
                        dress_id=dress_id,
                        size_label=label,
                        quantity=1,
                        sort_order=0,
                    )

        # The index is partial on deleted_at IS NULL, so a replaced matrix frees
        # its labels for reuse rather than poisoning them forever.
        await service.replace_variants(
            tenant, dress_id, [VariantInput(size_label="US 6", quantity=1, sort_order=0)]
        )
        reused = await service.replace_variants(
            tenant, dress_id, [VariantInput(size_label="us 6", quantity=2, sort_order=0)]
        )
        assert [variant.size_label for variant in reused.variants] == ["us 6"]
    finally:
        await engine.dispose()


async def test_media_presign_confirm_delete_lifecycle(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)

        presigned = await _upload(service, storage, tenant, dress_id)
        assert presigned.fields["key"].startswith(f"tenants/{tenant}/dresses/{dress_id}/media/")

        # A pending row occupies a slot but never reaches the gallery.
        pending_view = await service.get_dress(tenant, dress_id)
        assert pending_view.media == []
        assert pending_view.slots_remaining == MAX_MEDIA_PER_DRESS - 1

        confirmed = await service.confirm_media(tenant, dress_id, presigned.media_id)
        assert [item.row.id for item in confirmed.media] == [presigned.media_id]
        assert confirmed.media[0].row.sort_order == 0
        assert confirmed.media_count == 1
        assert confirmed.cover is not None
        assert confirmed.cover.row.id == presigned.media_id

        after_delete = await service.delete_media(tenant, dress_id, presigned.media_id)
        assert after_delete.media == []
        assert after_delete.media_count == 0
        assert await storage.head_object(key=presigned.fields["key"]) is None

        with pytest.raises(CatalogNotFoundError):
            await service.delete_media(tenant, dress_id, presigned.media_id)
    finally:
        await engine.dispose()


async def test_confirm_without_an_upload_is_not_uploaded(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        presigned = await service.presign_media(
            tenant, dress_id, content_type=JPEG, byte_size=len(JPEG_BODY)
        )
        with pytest.raises(MediaNotUploadedError):
            await service.confirm_media(tenant, dress_id, presigned.media_id)
        # The row stays pending and remains confirmable.
        assert await _pending_count(factory, tenant) == 1
    finally:
        await engine.dispose()


async def test_confirm_deletes_an_object_whose_magic_bytes_disagree(app_role_url: str) -> None:
    """The content-type-honest polyglot: declared and posted as image/jpeg at
    exactly the declared size, so the POST policy passes it. The 16-byte prefix
    check is what makes the allowlist real rather than declared."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        presigned = await _upload(service, storage, tenant, dress_id, body=HTML_BODY)
        with pytest.raises(MediaMismatchError):
            await service.confirm_media(tenant, dress_id, presigned.media_id)
        assert await storage.head_object(key=presigned.fields["key"]) is None
    finally:
        await engine.dispose()


async def test_media_reorder_requires_an_exact_permutation(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        first = await _upload(service, storage, tenant, dress_id)
        await service.confirm_media(tenant, dress_id, first.media_id)
        second = await _upload(service, storage, tenant, dress_id)
        await service.confirm_media(tenant, dress_id, second.media_id)

        reordered = await service.reorder_media(tenant, dress_id, [second.media_id, first.media_id])
        assert [item.row.id for item in reordered.media] == [second.media_id, first.media_id]
        assert [item.row.sort_order for item in reordered.media] == [0, 1]

        for payload in (
            [first.media_id],
            [first.media_id, second.media_id, uuid.uuid4()],
            [first.media_id, first.media_id],
            [uuid.uuid4(), uuid.uuid4()],
        ):
            with pytest.raises(MediaOrderMismatchError):
                await service.reorder_media(tenant, dress_id, payload)

        unchanged = await service.get_dress(tenant, dress_id)
        assert [item.row.id for item in unchanged.media] == [second.media_id, first.media_id]
    finally:
        await engine.dispose()


async def test_archive_then_restore_keeps_individually_deleted_photos_deleted(
    app_role_url: str,
) -> None:
    """The archive UPDATEs carry `deleted_at IS NULL`, so a photo the owner
    deleted last week keeps its older stamp; restore matches children on the
    dress's own stamp. Without both halves, restoring resurrects deletions."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        await service.replace_variants(
            tenant, dress_id, [VariantInput(size_label="38", quantity=1, sort_order=0)]
        )
        kept = await _upload(service, storage, tenant, dress_id)
        await service.confirm_media(tenant, dress_id, kept.media_id)
        dropped = await _upload(service, storage, tenant, dress_id)
        await service.confirm_media(tenant, dress_id, dropped.media_id)
        await service.delete_media(tenant, dress_id, dropped.media_id)

        await service.archive_dress(tenant, dress_id)

        # Archived dresses vanish from the active list and stay readable.
        assert (await service.list_dresses(tenant)).total == 0
        assert (await service.list_dresses(tenant, archived=True)).total == 1
        archived = await service.get_dress(tenant, dress_id)
        assert archived.row.deleted_at is not None

        # Every other route treats an archived dress as missing.
        with pytest.raises(CatalogNotFoundError):
            await service.update_dress(
                tenant,
                dress_id,
                name="Nope",
                description=None,
                price_agorot=None,
                price_visible=True,
                reserved=False,
                sort_order=0,
            )
        with pytest.raises(CatalogNotFoundError):
            await service.archive_dress(tenant, dress_id)

        restored = await service.restore_dress(tenant, dress_id)
        assert restored.row.deleted_at is None
        assert [variant.size_label for variant in restored.variants] == ["38"]
        assert [item.row.id for item in restored.media] == [kept.media_id]

        async with tenant_session(factory, tenant) as session:
            still_deleted = await DressMediaRepository().by_id(
                session, tenant, dress_id, dropped.media_id
            )
        assert still_deleted is None

        with pytest.raises(CatalogNotFoundError):
            await service.restore_dress(tenant, dress_id)
    finally:
        await engine.dispose()


async def test_concurrent_variant_replaces_never_union(app_role_url: str) -> None:
    """Two concurrent replaces are serialised by the per-dress variants lock —
    the final state is exactly ONE submitted set, never a union of both. A
    second dress replaced at the same time proves the lock is keyed per dress."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    set_a = [
        VariantInput(size_label=label, quantity=1, sort_order=index)
        for index, label in enumerate(("38", "40"))
    ]
    set_b = [
        VariantInput(size_label=label, quantity=1, sort_order=index)
        for index, label in enumerate(("44", "46", "48"))
    ]
    other_set = [VariantInput(size_label="52", quantity=3, sort_order=0)]
    try:
        dress_id = await _dress(service, tenant, name="Aurora")
        other_id = await _dress(service, tenant, name="Belle")

        await asyncio.gather(
            service.replace_variants(tenant, dress_id, set_a),
            service.replace_variants(tenant, dress_id, set_b),
            service.replace_variants(tenant, other_id, other_set),
        )

        final = await service.get_dress(tenant, dress_id)
        labels = sorted(variant.size_label for variant in final.variants)
        assert labels in (["38", "40"], ["44", "46", "48"]), f"union detected: {labels}"

        untouched = await service.get_dress(tenant, other_id)
        assert [variant.size_label for variant in untouched.variants] == ["52"]
    finally:
        await engine.dispose()


async def test_concurrent_presigns_respect_the_cap(app_role_url: str) -> None:
    """All 13 run inside the same per-dress media lock, so the 13th loses and
    gets MEDIA_LIMIT_REACHED — never an over-full gallery."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        outcomes = await asyncio.gather(
            *(
                service.presign_media(tenant, dress_id, content_type=JPEG, byte_size=len(JPEG_BODY))
                for _ in range(MAX_MEDIA_PER_DRESS + 1)
            ),
            return_exceptions=True,
        )

        granted = [item for item in outcomes if isinstance(item, PresignResult)]
        refused = [item for item in outcomes if isinstance(item, MediaLimitReachedError)]
        assert len(granted) == MAX_MEDIA_PER_DRESS
        assert len(refused) >= 1

        async with tenant_session(factory, tenant) as session:
            rows = await session.execute(
                text(
                    "SELECT count(*) FROM dress_media "
                    "WHERE dress_id = :dress_id AND deleted_at IS NULL"
                ),
                {"dress_id": dress_id},
            )
            assert int(rows.scalar_one()) == MAX_MEDIA_PER_DRESS
    finally:
        await engine.dispose()


async def test_confirm_is_idempotent_and_never_forks_a_row(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        presigned = await _upload(service, storage, tenant, dress_id)

        first = await service.confirm_media(tenant, dress_id, presigned.media_id)
        again = await service.confirm_media(tenant, dress_id, presigned.media_id)
        assert [(item.row.id, item.row.sort_order) for item in first.media] == [
            (item.row.id, item.row.sort_order) for item in again.media
        ]
        assert [item.row.sort_order for item in again.media] == [0]

        async with tenant_session(factory, tenant) as session:
            rows = await session.execute(
                text(
                    "SELECT count(*) FROM dress_media "
                    "WHERE dress_id = :dress_id AND deleted_at IS NULL"
                ),
                {"dress_id": dress_id},
            )
            assert int(rows.scalar_one()) == 1

        # Two gathered confirms of the SAME media id: both succeed, same
        # sort_order, no IntegrityError. Confirm is an UPDATE guarded by
        # status = 'pending' plus a re-read inside the locked promote
        # transaction — it cannot double-bump or fork.
        second_dress = await _dress(service, tenant, name="Belle")
        raced = await _upload(service, storage, tenant, second_dress)
        both = await asyncio.gather(
            service.confirm_media(tenant, second_dress, raced.media_id),
            service.confirm_media(tenant, second_dress, raced.media_id),
        )
        assert [view.media[0].row.sort_order for view in both] == [0, 0]
    finally:
        await engine.dispose()


async def test_concurrent_confirms_get_distinct_sort_orders(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        first = await _upload(service, storage, tenant, dress_id)
        second = await _upload(service, storage, tenant, dress_id)

        await asyncio.gather(
            service.confirm_media(tenant, dress_id, first.media_id),
            service.confirm_media(tenant, dress_id, second.media_id),
        )

        detail = await service.get_dress(tenant, dress_id)
        assert sorted(item.row.sort_order for item in detail.media) == [0, 1]
    finally:
        await engine.dispose()


async def test_stale_pendings_are_excluded_and_swept(app_role_url: str) -> None:
    """pending_ttl_seconds=0 is the injectable seam — no sleep, no raw-SQL
    backdating. Afterwards exactly one pending row survives, which proves the
    sweep DELETED the twelve rather than merely excluding them from the count."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    filling = _service(factory, storage)
    sweeping = _service(factory, storage, pending_ttl_seconds=0)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(filling, tenant)
        stale = [
            await filling.presign_media(
                tenant, dress_id, content_type=JPEG, byte_size=len(JPEG_BODY)
            )
            for _ in range(MAX_MEDIA_PER_DRESS)
        ]
        with pytest.raises(MediaLimitReachedError):
            await filling.presign_media(
                tenant, dress_id, content_type=JPEG, byte_size=len(JPEG_BODY)
            )

        thirteenth = await sweeping.presign_media(
            tenant, dress_id, content_type=JPEG, byte_size=len(JPEG_BODY)
        )
        assert await _pending_count(factory, tenant) == 1
        assert thirteenth.media_id not in {presigned.media_id for presigned in stale}

        # The sweep holds the swept rows' storage keys, so it deletes the objects
        # it is about to orphan — that is what bounds the orphan window to one
        # TTL plus the next presign rather than forever.
        storage.put(key=thirteenth.fields["key"], content_type=JPEG, body=JPEG_BODY)
        await sweeping.presign_media(tenant, dress_id, content_type=JPEG, byte_size=len(JPEG_BODY))
        assert await storage.head_object(key=thirteenth.fields["key"]) is None
    finally:
        await engine.dispose()


async def test_list_ordering_is_stable_when_both_leading_keys_collide(app_role_url: str) -> None:
    """sort_order ASC, created_at DESC, id ASC — all four index keys. With the
    first two tied, id is what keeps a page from repeating or skipping a row
    under concurrent inserts."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        ids = [await _dress(service, tenant, name=f"Dress {index}") for index in range(3)]
        async with tenant_session(factory, tenant) as session:
            await session.execute(
                text(
                    "UPDATE dresses SET sort_order = 7, "
                    "created_at = TIMESTAMPTZ '2026-01-01 00:00:00+00'"
                )
            )

        page = await service.list_dresses(tenant)
        assert [item.row.id for item in page.items] == sorted(ids)
    finally:
        await engine.dispose()


_CATALOG_TABLES_IN_SQL = ("dresses", "dress_variants", "dress_media")


@contextlib.contextmanager
def _catalog_statements(engine: AsyncEngine) -> Iterator[list[str]]:
    """Counts only statements that touch a catalog table. tenant_session issues
    a set_config of its own, so an unfiltered counter sees five where the pinned
    shape is four — the filter is decided here, not after the test flakes."""
    seen: list[str] = []

    def _record(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        if any(table in statement for table in _CATALOG_TABLES_IN_SQL):
            seen.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _record)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _record)


async def test_list_page_issues_a_fixed_statement_count(app_role_url: str) -> None:
    """The page, its COUNT, one grouped variant aggregate and one DISTINCT ON
    cover query — four, whatever the page size. Pins the N+1 shut."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        for index in range(50):
            dress_id = await _dress(service, tenant, name=f"Dress {index}")
            if index < 3:
                await service.replace_variants(
                    tenant, dress_id, [VariantInput(size_label="38", quantity=1, sort_order=0)]
                )
                presigned = await _upload(service, storage, tenant, dress_id)
                await service.confirm_media(tenant, dress_id, presigned.media_id)

        with _catalog_statements(engine) as statements:
            page = await service.list_dresses(tenant, limit=50)

        assert len(page.items) == 50
        assert len(statements) == 4, statements
        assert page.items[0].summary.variant_count == 1
        assert page.items[0].media_count == 1
        assert page.items[0].cover is not None
        # A dress with no group row must still serialise the zero state.
        bare = next(item for item in page.items if item.row.name == "Dress 49")
        assert bare.summary == StockSummary(variant_count=0, total_quantity=0, out_of_stock=True)
        assert bare.cover is None
        assert bare.media_count == 0
    finally:
        await engine.dispose()


async def test_list_views_are_dress_views_without_detail_payload(app_role_url: str) -> None:
    """List rows carry the derived summary and the cover only: variants and the
    full gallery belong to the detail read, and paying for them per row is the
    N+1 the four-statement shape exists to prevent."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    service = _service(factory, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        await service.replace_variants(
            tenant, dress_id, [VariantInput(size_label="38", quantity=4, sort_order=0)]
        )
        page = await service.list_dresses(tenant)
        row = page.items[0]
        assert isinstance(row, DressView)
        assert row.variants == []
        assert row.media == []
        assert row.summary.total_quantity == 4
        assert row.summary.out_of_stock is False
    finally:
        await engine.dispose()


def _catalog_table_count(url: str) -> int:
    async def count() -> int:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT count(*) FROM pg_tables "
                        "WHERE tablename IN ('dresses', 'dress_variants', 'dress_media')"
                    )
                )
                return int(result.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(count())


def test_migration_0006_round_trips(migrated_db: str) -> None:
    """downgrade drops dress_media, dress_variants, dresses in child-first order;
    upgrade puts all three back with their indexes, grants and policies. Runs as
    the migration owner (the app role cannot DROP), and destroys catalog rows —
    so it owns no fixtures and shares no state with the tests above."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", migrated_db)

    assert _catalog_table_count(migrated_db) == 3
    command.downgrade(cfg, "0005")
    assert _catalog_table_count(migrated_db) == 0
    command.upgrade(cfg, "head")
    assert _catalog_table_count(migrated_db) == 3
