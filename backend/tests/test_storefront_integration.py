"""Feature 10's public read paths on real Postgres as boutique_app — the things
the no-Docker loop cannot prove: the statement SHAPE of each read, the real
planner's ordering under tied keys, and the SQL-side `on_or_after` cutoff.

The two statement-count tests are the load-bearing pair. `StorefrontService`
deliberately owns its own repository handles instead of calling `CatalogService`,
and the whole point of that duplication is that `aggregate_by_dress` and
`count_active` are never reached — so out_of_stock, total_quantity and
variant_count are not merely unserialised, they are never computed. That claim is
invisible to a response-shape assertion and would survive any amount of
refactoring; only counting statements catches its loss. The counts are asserted
EXACTLY, never as an upper bound: a regression to the console's service adds one
statement, and `<= 4` would pass it.

Runs as the non-owner application role, never as the container superuser: GRANT
and FORCE-RLS correctness are vacuous when the connecting principal owns the
tables.
"""

import contextlib
import datetime
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.boutique.service import BoutiqueSettingsService
from app.catalog.service import CatalogNotFoundError, CatalogService
from app.catalog.validation import VariantInput
from app.db.tenant import tenant_session
from app.storage.memory import InMemoryMediaStorage
from app.storefront.service import StorefrontService
from app.storefront.validation import (
    BOUTIQUE_TIMEZONE,
    STOREFRONT_LIST_MAX_LIMIT,
    UPCOMING_EXCEPTIONS_LIMIT,
)

pytestmark = pytest.mark.db

JPEG = "image/jpeg"
JPEG_BODY = b"\xff\xd8\xff" + b"\x00" * 1021

CATALOG_PAGE_SIZE = 50

_CATALOG_TABLES_IN_SQL = ("dresses", "dress_variants", "dress_media")


def _engine(app_role_url: str) -> AsyncEngine:
    # NullPool: nothing here may reuse a connection whose tenant context
    # outlived the block that set it.
    return create_async_engine(app_role_url, poolclass=NullPool)


def _factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def _catalog(
    factory: async_sessionmaker[AsyncSession], storage: InMemoryMediaStorage
) -> CatalogService:
    """The owner's console — used here only to SEED. Every assertion below reads
    through StorefrontService."""
    return CatalogService(
        factory,
        media_storage=storage,
        presign_rate_limiter=FixedWindowRateLimiter(
            max_attempts=10_000, window_seconds=3600, clock=time.monotonic
        ),
    )


def _boutique(factory: async_sessionmaker[AsyncSession]) -> BoutiqueSettingsService:
    return BoutiqueSettingsService(
        factory,
        terms_rate_limiter=FixedWindowRateLimiter(
            max_attempts=10_000, window_seconds=3600, clock=time.monotonic
        ),
    )


def _storefront(
    factory: async_sessionmaker[AsyncSession],
    storage: InMemoryMediaStorage,
    *,
    now: datetime.datetime | None = None,
) -> StorefrontService:
    return StorefrontService(
        factory, media_storage=storage, clock=None if now is None else lambda: now
    )


async def _dress(
    catalog: CatalogService, tenant_id: uuid.UUID, name: str, *, sort_order: int = 0
) -> uuid.UUID:
    created = await catalog.create_dress(
        tenant_id,
        name=name,
        description="Ivory silk",
        price_agorot=120_000,
        price_visible=True,
        reserved=False,
        sort_order=sort_order,
    )
    return created.row.id


async def _seed_catalog(
    catalog: CatalogService,
    tenant_id: uuid.UUID,
    count: int = CATALOG_PAGE_SIZE,
    *,
    sort_order: int = 0,
) -> list[uuid.UUID]:
    return [
        await _dress(catalog, tenant_id, f"Dress {index}", sort_order=sort_order)
        for index in range(count)
    ]


async def _pending_photo(
    catalog: CatalogService, tenant_id: uuid.UUID, dress_id: uuid.UUID
) -> uuid.UUID:
    """Presigned and never uploaded — an unverified object that must not reach a
    signed URL on any public surface."""
    presigned = await catalog.presign_media(
        tenant_id, dress_id, content_type=JPEG, byte_size=len(JPEG_BODY)
    )
    return presigned.media_id


async def _ready_photo(
    catalog: CatalogService,
    storage: InMemoryMediaStorage,
    tenant_id: uuid.UUID,
    dress_id: uuid.UUID,
) -> uuid.UUID:
    presigned = await catalog.presign_media(
        tenant_id, dress_id, content_type=JPEG, byte_size=len(JPEG_BODY)
    )
    storage.put(key=presigned.fields["key"], content_type=JPEG, body=JPEG_BODY)
    await catalog.confirm_media(tenant_id, dress_id, presigned.media_id)
    return presigned.media_id


@contextlib.contextmanager
def _catalog_statements(engine: AsyncEngine) -> Iterator[list[str]]:
    """Counts only statements that touch a catalog table — tenant_session issues
    a set_config of its own, so an unfiltered counter would pin a number that has
    nothing to do with the read shape. Lifted verbatim from
    test_catalog_integration.py so both suites count the same way."""
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


async def test_list_issues_exactly_three_statements(app_role_url: str) -> None:
    """The page, its COUNT and one DISTINCT ON cover query — three, whatever the
    catalog size. The console's list buys FOUR because it also runs the grouped
    variant aggregate; a fourth here means the public list has started computing
    the boutique's raw stock position on every anonymous request."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    catalog = _catalog(factory, storage)
    storefront = _storefront(factory, storage)
    tenant = uuid.uuid4()
    try:
        # sort_order 0 vs 1 pins the three photographed dresses onto page one
        # whatever the planner does with the created_at tiebreak.
        featured = [
            await _dress(catalog, tenant, f"Featured {index}", sort_order=0) for index in range(3)
        ]
        for dress_id in featured:
            await catalog.replace_variants(
                tenant, dress_id, [VariantInput(size_label="38", quantity=1, sort_order=0)]
            )
            await _ready_photo(catalog, storage, tenant, dress_id)
        await _seed_catalog(catalog, tenant, CATALOG_PAGE_SIZE - len(featured), sort_order=1)

        with _catalog_statements(engine) as statements:
            page = await storefront.list_dresses(tenant)

        assert len(statements) == 3, statements
        # The narrower claim behind the count: the variants table is never read
        # on this path at all, so there is no aggregate to leak or to forget.
        assert [item for item in statements if "dress_variants" in item] == []
        assert len(page.items) == STOREFRONT_LIST_MAX_LIMIT
        assert page.total == CATALOG_PAGE_SIZE
        # Covers were actually signed, and signed onto the right rows — so the
        # three statements are three real reads, not an early return.
        assert {item.row.id for item in page.items if item.cover is not None} == set(featured)
    finally:
        await engine.dispose()


async def test_detail_issues_exactly_three_statements(app_role_url: str) -> None:
    """The dress, its variants and its ready media — three, and never one query
    per photo. Counted inside a 50-dress catalog so a detail read that started
    scanning the catalog would show up here too."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    catalog = _catalog(factory, storage)
    storefront = _storefront(factory, storage)
    tenant = uuid.uuid4()
    try:
        ids = await _seed_catalog(catalog, tenant)
        target = ids[0]
        await catalog.replace_variants(
            tenant,
            target,
            [
                VariantInput(size_label="38", quantity=2, sort_order=0),
                VariantInput(size_label="40", quantity=0, sort_order=1),
            ],
        )
        for _ in range(2):
            await _ready_photo(catalog, storage, tenant, target)

        with _catalog_statements(engine) as statements:
            detail = await storefront.get_dress(tenant, target)

        assert len(statements) == 3, statements
        # Both collections came back populated, so none of the three statements
        # is a miss that would make the count accidentally right.
        assert [size.size_label for size in detail.sizes] == ["38", "40"]
        assert [size.available for size in detail.sizes] == [True, False]
        assert len(detail.media) == 2
    finally:
        await engine.dispose()


async def test_archived_dress_is_absent_from_list_and_404_on_detail(app_role_url: str) -> None:
    """Archive is a soft delete and the storefront must treat it as gone. `by_id`
    pins deleted_at IS NULL, so the detail miss is indistinguishable from an
    unknown id — which is the design's "השמלה כבר לא זמינה" state."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    catalog = _catalog(factory, storage)
    storefront = _storefront(factory, storage)
    tenant = uuid.uuid4()
    try:
        kept = await _dress(catalog, tenant, "Aurora")
        archived = await _dress(catalog, tenant, "Camellia")
        await catalog.archive_dress(tenant, archived)

        page = await storefront.list_dresses(tenant)
        assert [item.row.id for item in page.items] == [kept]
        assert page.total == 1

        with pytest.raises(CatalogNotFoundError):
            await storefront.get_dress(tenant, archived)
        # The kept dress still resolves, so the 404 above is about the archive
        # and not about the read path being broken.
        assert (await storefront.get_dress(tenant, kept)).row.id == kept
    finally:
        await engine.dispose()


async def test_list_ordering_matches_manage(app_role_url: str) -> None:
    """sort_order ASC, created_at DESC, id ASC — the same order the console
    lists, because both go through DressesRepository.list_page. Exercised with
    the two leading keys COLLIDING so the id tiebreak is what decides: without
    it a page can repeat or skip a row, and the storefront's load-more button is
    the one place a user sees that as a duplicate card."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    catalog = _catalog(factory, storage)
    storefront = _storefront(factory, storage)
    tenant = uuid.uuid4()
    try:
        ids = [await _dress(catalog, tenant, f"Dress {index}") for index in range(5)]
        async with tenant_session(factory, tenant) as session:
            await session.execute(
                text(
                    "UPDATE dresses SET sort_order = 7, "
                    "created_at = TIMESTAMPTZ '2026-01-01 00:00:00+00'"
                )
            )

        public = [item.row.id for item in (await storefront.list_dresses(tenant)).items]
        manage = [item.row.id for item in (await catalog.list_dresses(tenant)).items]
        assert public == manage
        assert public == sorted(ids)
    finally:
        await engine.dispose()


async def test_second_page_returns_the_next_24(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    catalog = _catalog(factory, storage)
    storefront = _storefront(factory, storage)
    tenant = uuid.uuid4()
    try:
        await _seed_catalog(catalog, tenant)
        whole = [
            item.row.id
            for item in (await catalog.list_dresses(tenant, limit=CATALOG_PAGE_SIZE)).items
        ]

        first = await storefront.list_dresses(tenant)
        second = await storefront.list_dresses(tenant, offset=STOREFRONT_LIST_MAX_LIMIT)

        first_ids = [item.row.id for item in first.items]
        second_ids = [item.row.id for item in second.items]
        assert first_ids == whole[:STOREFRONT_LIST_MAX_LIMIT]
        assert second_ids == whole[STOREFRONT_LIST_MAX_LIMIT : STOREFRONT_LIST_MAX_LIMIT * 2]
        assert set(first_ids).isdisjoint(second_ids)
        assert second.offset == STOREFRONT_LIST_MAX_LIMIT
        assert second.limit == STOREFRONT_LIST_MAX_LIMIT
        # `total` is the whole catalog, not the page — it is what the load-more
        # button counts against.
        assert first.total == second.total == CATALOG_PAGE_SIZE
    finally:
        await engine.dispose()


async def test_only_ready_media_is_returned(app_role_url: str) -> None:
    """A pending row is an object nobody has verified — it may not be the image
    it claims to be. It occupies a gallery slot for the owner and must appear in
    neither the public cover nor the public gallery."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    catalog = _catalog(factory, storage)
    storefront = _storefront(factory, storage)
    tenant = uuid.uuid4()
    try:
        mixed = await _dress(catalog, tenant, "Aurora")
        ready_id = await _ready_photo(catalog, storage, tenant, mixed)
        await _pending_photo(catalog, tenant, mixed)

        pending_only = await _dress(catalog, tenant, "Belle")
        await _pending_photo(catalog, tenant, pending_only)

        covers = {item.row.id: item.cover for item in (await storefront.list_dresses(tenant)).items}
        mixed_cover = covers[mixed]
        assert mixed_cover is not None
        assert mixed_cover.row.id == ready_id
        # A dress whose only photo is pending has no cover at all — not a signed
        # URL to an unverified object.
        assert covers[pending_only] is None

        assert [item.row.id for item in (await storefront.get_dress(tenant, mixed)).media] == [
            ready_id
        ]
        assert (await storefront.get_dress(tenant, pending_only)).media == []
    finally:
        await engine.dispose()


async def test_upcoming_exceptions_filter(app_role_url: str) -> None:
    """Yesterday's closure is history; today's is the one a visitor standing
    outside the door needs. The cutoff runs in SQL via `on_or_after`, so a
    boutique with three years of recorded holidays never ships them to the public
    page to have them discarded in Python — and the cap keeps /about an editorial
    card rather than a calendar.

    The clock is injected: the CI runner, a laptop and Israel are three different
    calendar days for part of every day, so a test that trusted the machine's TZ
    would be green until it was not."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    storage = InMemoryMediaStorage()
    boutique = _boutique(factory)
    tenant = uuid.uuid4()
    now = datetime.datetime(2026, 7, 28, 12, 0, tzinfo=BOUTIQUE_TIMEZONE)
    today = now.date()
    day = datetime.timedelta(days=1)
    storefront = _storefront(factory, storage, now=now)
    try:
        # One more future exception than the cap, so the truncation is exercised
        # rather than merely fitted.
        offsets = [-1, 0, *range(1, UPCOMING_EXCEPTIONS_LIMIT + 2)]
        for offset in offsets:
            await boutique.add_availability_exception(
                tenant,
                date=today + offset * day,
                open_time=None,
                close_time=None,
                note=f"offset {offset}",
            )

        view = await storefront.get_boutique(tenant, name="Bella", settings={})

        dates = [row.date for row in view.exceptions]
        assert len(dates) == UPCOMING_EXCEPTIONS_LIMIT
        assert dates == sorted(dates)
        assert dates[0] == today
        assert today - day not in dates
        assert dates[-1] == today + (UPCOMING_EXCEPTIONS_LIMIT - 1) * day
        # The overflowing tail is dropped from the END, not the start.
        assert today + (UPCOMING_EXCEPTIONS_LIMIT + 1) * day not in dates
    finally:
        await engine.dispose()
