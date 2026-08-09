"""F21 B4 / row R38: catalog's nine audit rows on real Postgres.

`test_audit_coverage.py` proves a `_audit.record(...)` call sits on each of the
nine mutating paths. It cannot prove a row lands, that the row carries the right
action and actor, or that it rides the mutation's transaction — three properties
that are exactly where audit code goes wrong. This module drives the real service
against the real database as the non-owner `boutique_app` role and reads the
table back.

⚠ THE TENTH TEST IS THE ONE THAT MATTERS MOST. Nine audit calls that also fire on
an idempotent retry are nine audit calls AND a trail that lies: `dress_media`
confirm is retried by the browser on every lost response, and a row per retry
would claim a photo was published three times when it was published once. That is
the standing rule this repo already writes down five times over (D13's "a no-op
writes no row", FITTING_ROOM_CLAIMED, ATELIER_CAPACITY_SET, SOS_RESOLVED,
QUEUE_TICKET_CALLED), and `test_a_reconfirm_writes_no_second_row` is what holds
it here.

Every test takes its own engine and its own random tenant id, so the row counts
are exact rather than "at least one" — an assertion that would survive the very
duplicate-row bug the module exists to catch.
"""

import datetime
import time
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.catalog.service import CatalogService, PresignResult
from app.catalog.validation import VariantInput
from app.db.tenant import tenant_session
from app.models.audit_log import AuditLog
from app.models.constants import AuditAction
from app.storage.memory import InMemoryMediaStorage

pytestmark = pytest.mark.db

ACTOR_ID = uuid.uuid4()
JPEG = "image/jpeg"
# Past MIN_UPLOAD_BYTES (1024) — `validate_presign` refuses anything smaller, and
# a body that never reaches the service proves nothing about the row it writes.
JPEG_BODY = b"\xff\xd8\xff\xe0" + b"a" * 2048


def _engine(app_role_url: str) -> AsyncEngine:
    return create_async_engine(app_role_url, poolclass=NullPool)


def _service(engine: AsyncEngine, storage: InMemoryMediaStorage) -> CatalogService:
    return CatalogService(
        async_sessionmaker(engine, expire_on_commit=False),
        media_storage=storage,
        presign_rate_limiter=FixedWindowRateLimiter(
            max_attempts=10_000, window_seconds=3600, clock=time.monotonic
        ),
        pending_ttl_seconds=3600,
    )


async def _rows(engine: AsyncEngine, tenant_id: uuid.UUID) -> list[AuditLog]:
    """Read through `tenant_session` — `audit_log` is force-RLS like every other
    tenant table, so a bare session returns nothing and every assertion below
    would pass on an empty list."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with tenant_session(factory, tenant_id) as session:
        result = await session.execute(select(AuditLog).order_by(AuditLog.created_at))
        return list(result.scalars().all())


async def _dress(service: CatalogService, tenant_id: uuid.UUID) -> uuid.UUID:
    created = await service.create_dress(
        tenant_id,
        name="Aurora",
        description=None,
        price_agorot=None,
        price_visible=True,
        reserved=False,
        sort_order=0,
        actor_id=ACTOR_ID,
    )
    return created.row.id


async def _upload(
    service: CatalogService,
    storage: InMemoryMediaStorage,
    tenant_id: uuid.UUID,
    dress_id: uuid.UUID,
) -> PresignResult:
    presigned = await service.presign_media(
        tenant_id, dress_id, content_type=JPEG, byte_size=len(JPEG_BODY), actor_id=ACTOR_ID
    )
    storage.put(key=presigned.fields["key"], content_type=JPEG, body=JPEG_BODY)
    return presigned


def _only(rows: list[AuditLog], action: AuditAction) -> AuditLog:
    """Exactly one, never `[0]` of many: a duplicated row is the failure this
    module was written to catch, and `[0]` would hide it."""
    matching = [row for row in rows if row.action == action]
    assert len(matching) == 1, f"{action}: expected exactly one row, got {len(matching)}"
    return matching[0]


async def test_create_writes_one_row_naming_the_dress(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    storage = InMemoryMediaStorage()
    service = _service(engine, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        row = _only(await _rows(engine, tenant), AuditAction.DRESS_CREATED)
        assert row.actor_id == ACTOR_ID
        assert row.entity == str(dress_id)
        assert row.details == {"name": "Aurora", "price_visible": True}
    finally:
        await engine.dispose()


async def test_update_writes_one_row(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    service = _service(engine, InMemoryMediaStorage())
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        await service.update_dress(
            tenant,
            dress_id,
            name="Aurora II",
            description=None,
            price_agorot=None,
            price_visible=False,
            reserved=True,
            sort_order=5,
            actor_id=ACTOR_ID,
        )
        row = _only(await _rows(engine, tenant), AuditAction.DRESS_UPDATED)
        assert row.actor_id == ACTOR_ID
        assert row.entity == str(dress_id)
        assert row.details == {"name": "Aurora II", "price_visible": False, "reserved": True}
    finally:
        await engine.dispose()


async def test_archive_writes_one_row_carrying_the_name(app_role_url: str) -> None:
    """The name is read into a local BEFORE `soft_delete` runs. `soft_delete` is
    ORM-enabled DML whose `evaluate` synchronization stamps the very instance the
    name is read off — the identity-map trap this repo has now hit five times."""
    engine = _engine(app_role_url)
    service = _service(engine, InMemoryMediaStorage())
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        await service.archive_dress(tenant, dress_id, actor_id=ACTOR_ID)
        row = _only(await _rows(engine, tenant), AuditAction.DRESS_ARCHIVED)
        assert row.actor_id == ACTOR_ID
        assert row.entity == str(dress_id)
        assert row.details == {"name": "Aurora"}
    finally:
        await engine.dispose()


async def test_restore_writes_one_row(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    service = _service(engine, InMemoryMediaStorage())
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        await service.archive_dress(tenant, dress_id, actor_id=ACTOR_ID)
        await service.restore_dress(tenant, dress_id, actor_id=ACTOR_ID)
        row = _only(await _rows(engine, tenant), AuditAction.DRESS_RESTORED)
        assert row.actor_id == ACTOR_ID
        assert row.entity == str(dress_id)
        assert row.details == {"name": "Aurora"}
    finally:
        await engine.dispose()


async def test_variant_replacement_writes_one_row_with_the_resulting_matrix(
    app_role_url: str,
) -> None:
    engine = _engine(app_role_url)
    service = _service(engine, InMemoryMediaStorage())
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        await service.replace_variants(
            tenant,
            dress_id,
            [
                VariantInput(size_label="38", quantity=2, sort_order=0),
                VariantInput(size_label="40", quantity=1, sort_order=1),
            ],
            actor_id=ACTOR_ID,
        )
        row = _only(await _rows(engine, tenant), AuditAction.DRESS_VARIANTS_REPLACED)
        assert row.entity == str(dress_id)
        assert row.details == {"sizes": ["38", "40"], "total_quantity": 3}
    finally:
        await engine.dispose()


async def test_presign_writes_one_row_carrying_the_storage_key(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    storage = InMemoryMediaStorage()
    service = _service(engine, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        presigned = await _upload(service, storage, tenant, dress_id)
        row = _only(await _rows(engine, tenant), AuditAction.DRESS_MEDIA_PRESIGNED)
        assert row.entity == str(presigned.media_id)
        assert row.details["dress_id"] == str(dress_id)
        assert row.details["storage_key"] == presigned.fields["key"]
        assert row.details["content_type"] == JPEG
        assert row.details["byte_size"] == len(JPEG_BODY)
    finally:
        await engine.dispose()


async def test_a_refused_presign_writes_no_row(app_role_url: str) -> None:
    """The credential was never issued, so nothing happened to record. This is
    what makes the presign row inside the transaction rather than beside it."""
    engine = _engine(app_role_url)
    service = _service(engine, InMemoryMediaStorage())
    tenant = uuid.uuid4()
    try:
        with pytest.raises(Exception):  # noqa: B017 — CatalogNotFoundError
            await service.presign_media(
                tenant,
                uuid.uuid4(),
                content_type=JPEG,
                byte_size=len(JPEG_BODY),
                actor_id=ACTOR_ID,
            )
        assert await _rows(engine, tenant) == []
    finally:
        await engine.dispose()


async def test_confirm_writes_one_row(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    storage = InMemoryMediaStorage()
    service = _service(engine, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        presigned = await _upload(service, storage, tenant, dress_id)
        await service.confirm_media(tenant, dress_id, presigned.media_id, actor_id=ACTOR_ID)
        row = _only(await _rows(engine, tenant), AuditAction.DRESS_MEDIA_CONFIRMED)
        assert row.actor_id == ACTOR_ID
        assert row.entity == str(presigned.media_id)
        # First photo on the dress: `max_ready_sort_order` answers -1 on an empty
        # gallery, so the first promotion lands at 0.
        assert row.details == {"dress_id": str(dress_id), "sort_order": 0}
    finally:
        await engine.dispose()


async def test_a_reconfirm_writes_no_second_row(app_role_url: str) -> None:
    """⚠ THE NO-OP TEST. Confirm is idempotent by design — the browser retries it
    on every lost response — so a row per call would turn one published photo
    into three in the trail. Standing rule, stated in five other blocks of
    `AuditAction` and enforced here.

    ⚠ AND A MUTATION RESULT WORTH WRITING DOWN, because it corrects what a reader
    would assume this test guards. Hoisting the `_audit.record(...)` OUT of
    `confirm_media`'s `status == PENDING` branch — the placement the service
    comments defend — leaves this test **GREEN**. On the sequential retry path the
    property is held one layer earlier, by the `already_ready` short-circuit that
    returns before the second session is ever opened; the PENDING guard is the
    backup that covers the concurrent case, where two confirms race and only one
    promotes. Moving the write ABOVE the short-circuit does red this test (and
    `test_confirm_writes_one_row` with it), which is what proves it has teeth.

    So: this test pins the OBSERVABLE property, and the guard it does not reach is
    redundant on the path it drives. Both are worth keeping, and anyone deleting
    the PENDING guard on the strength of a green suite should know they are
    deleting the concurrent half, not dead code.
    """
    engine = _engine(app_role_url)
    storage = InMemoryMediaStorage()
    service = _service(engine, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        presigned = await _upload(service, storage, tenant, dress_id)
        for _ in range(3):
            await service.confirm_media(tenant, dress_id, presigned.media_id, actor_id=ACTOR_ID)
        rows = await _rows(engine, tenant)
        confirmed = [row for row in rows if row.action == AuditAction.DRESS_MEDIA_CONFIRMED]
        assert len(confirmed) == 1, f"a retried confirm wrote {len(confirmed)} rows"
    finally:
        await engine.dispose()


async def test_media_delete_writes_one_row_carrying_the_orphan_key(app_role_url: str) -> None:
    """`storage_key` is the field doing the work: `_best_effort_delete` swallows a
    storage outage, so on that path this row is the only durable record of which
    object was left behind."""
    engine = _engine(app_role_url)
    storage = InMemoryMediaStorage()
    service = _service(engine, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        presigned = await _upload(service, storage, tenant, dress_id)
        await service.confirm_media(tenant, dress_id, presigned.media_id, actor_id=ACTOR_ID)
        await service.delete_media(tenant, dress_id, presigned.media_id, actor_id=ACTOR_ID)
        row = _only(await _rows(engine, tenant), AuditAction.DRESS_MEDIA_DELETED)
        assert row.actor_id == ACTOR_ID
        assert row.entity == str(presigned.media_id)
        assert row.details == {
            "dress_id": str(dress_id),
            "storage_key": presigned.fields["key"],
            "was_pending": False,
        }
    finally:
        await engine.dispose()


async def test_reorder_writes_one_row_with_the_resulting_sequence(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    storage = InMemoryMediaStorage()
    service = _service(engine, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        first = await _upload(service, storage, tenant, dress_id)
        await service.confirm_media(tenant, dress_id, first.media_id, actor_id=ACTOR_ID)
        second = await _upload(service, storage, tenant, dress_id)
        await service.confirm_media(tenant, dress_id, second.media_id, actor_id=ACTOR_ID)

        await service.reorder_media(
            tenant, dress_id, [second.media_id, first.media_id], actor_id=ACTOR_ID
        )
        row = _only(await _rows(engine, tenant), AuditAction.DRESS_MEDIA_REORDERED)
        assert row.entity == str(dress_id)
        assert row.details == {"media_ids": [str(second.media_id), str(first.media_id)]}
    finally:
        await engine.dispose()


async def test_every_catalog_action_has_a_live_writer(app_role_url: str) -> None:
    """The anti-vacuity leg for the whole module, and the property
    `queue/manage_router.py:29` states as a house rule: every shipped
    `AuditAction` value has a live writer. One full lifecycle produces all nine,
    so an action added to the enum and never wired reds here rather than sitting
    in the file looking like coverage."""
    engine = _engine(app_role_url)
    storage = InMemoryMediaStorage()
    service = _service(engine, storage)
    tenant = uuid.uuid4()
    try:
        dress_id = await _dress(service, tenant)
        await service.update_dress(
            tenant,
            dress_id,
            name="Aurora II",
            description=None,
            price_agorot=None,
            price_visible=True,
            reserved=False,
            sort_order=0,
            actor_id=ACTOR_ID,
        )
        await service.replace_variants(
            tenant,
            dress_id,
            [VariantInput(size_label="38", quantity=1, sort_order=0)],
            actor_id=ACTOR_ID,
        )
        media = await _upload(service, storage, tenant, dress_id)
        await service.confirm_media(tenant, dress_id, media.media_id, actor_id=ACTOR_ID)
        await service.reorder_media(tenant, dress_id, [media.media_id], actor_id=ACTOR_ID)
        await service.delete_media(tenant, dress_id, media.media_id, actor_id=ACTOR_ID)
        await service.archive_dress(tenant, dress_id, actor_id=ACTOR_ID)
        await service.restore_dress(tenant, dress_id, actor_id=ACTOR_ID)
        # F28's pair. They belong in the LIFECYCLE rather than in the expected
        # set's filter: this test's whole property is that a shipped AuditAction
        # with no live writer reds here, so narrowing the filter to exclude them
        # would be the one edit that turns the assertion vacuous.
        reservation = await service.create_reservation(
            tenant,
            dress_id,
            starts_on=datetime.date(2099, 3, 1),
            ends_on=datetime.date(2099, 3, 6),
            actor_id=ACTOR_ID,
        )
        await service.delete_reservation(tenant, dress_id, reservation.row.id, actor_id=ACTOR_ID)

        written = {row.action for row in await _rows(engine, tenant)}
        expected = {
            action.value
            for action in AuditAction
            if action.value.startswith(("dress_created", "dress_updated", "dress_"))
        }
        assert written == expected, f"unwritten catalog actions: {sorted(expected - written)}"
    finally:
        await engine.dispose()
