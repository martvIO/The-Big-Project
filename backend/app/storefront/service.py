"""Read logic for the public storefront.

**This service exists so that manage-only data is structurally unreachable, not
merely unserialised.** It would have been shorter to call `CatalogService`, and
that is exactly what makes it wrong: `CatalogService.list_dresses` calls
`DressVariantsRepository.aggregate_by_dress` to compute `out_of_stock`,
`total_quantity` and `variant_count`. Routing the public list through it would
mean the boutique's raw stock position is computed on every anonymous request
and kept off the wire only by the response model remembering to omit it. Here
`aggregate_by_dress` is never called at all, which costs one statement less per
page AND makes the leak unreachable rather than merely absent. `count_active`
is skipped for the same reason.

**`by_id_any_state` must never appear in this module.** `by_id` pins
`deleted_at IS NULL`, so an archived dress is an indistinguishable 404 — which
is precisely the design's "השמלה כבר לא זמינה" state.
`test_storefront_module_never_references_by_id_any_state` greps for the symbol.

**Signing runs outside `tenant_session`.** `sign_media` is local HMAC, so F8's
"no MediaStorage network method inside a tenant_session" invariant applies
unchanged; the storefront makes no storage network call at all.
"""

import dataclasses
import datetime
import uuid

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.catalog.service import CatalogNotFoundError, MediaView, sign_media
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.dress_media import DressMediaRepository
from app.db.repositories.dress_variants import DressVariantsRepository
from app.db.repositories.dresses import DressesRepository
from app.db.tenant import tenant_session
from app.models.availability import AvailabilityException, AvailabilityRule
from app.models.dress import Dress
from app.storage.base import MediaStorage
from app.storefront.validation import (
    STOREFRONT_LIST_DEFAULT_LIMIT,
    STOREFRONT_LIST_MAX_LIMIT,
    UPCOMING_EXCEPTIONS_LIMIT,
    Clock,
    today_jerusalem,
)

# Python ints are unbounded and the value is bound into OFFSET $n::BIGINT, so
# without a ceiling ?offset=2**63 is a 500 from asyncpg's encoder rather than a
# 400. Mirrors app.catalog.service.MAX_LIST_OFFSET.
MAX_LIST_OFFSET = 1_000_000


@dataclasses.dataclass(frozen=True)
class StorefrontDressView:
    """A catalog card. Deliberately carries NO stock summary, media count or
    slots-remaining: the public list never buys those statements."""

    row: Dress
    cover: MediaView | None


@dataclasses.dataclass(frozen=True)
class StorefrontDressListView:
    items: list[StorefrontDressView]
    total: int
    offset: int
    limit: int


@dataclasses.dataclass(frozen=True)
class StorefrontSizeView:
    """`available`, never `quantity` — the raw count is boutique-confidential
    and is folded to a boolean here, at the only place it is read."""

    size_label: str
    available: bool


@dataclasses.dataclass(frozen=True)
class StorefrontDressDetailView:
    row: Dress
    sizes: list[StorefrontSizeView]
    media: list[MediaView]


@dataclasses.dataclass(frozen=True)
class StorefrontBoutiqueView:
    name: str
    profile: dict[str, object]
    hours: list[AvailabilityRule]
    exceptions: list[AvailabilityException]


class StorefrontService:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        media_storage: MediaStorage,
        clock: Clock | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._storage = media_storage
        self._clock = clock
        self._dresses = DressesRepository()
        self._variants = DressVariantsRepository()
        self._media = DressMediaRepository()
        self._rules = AvailabilityRulesRepository()
        self._exceptions = AvailabilityExceptionsRepository()

    async def list_dresses(
        self,
        tenant_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = STOREFRONT_LIST_DEFAULT_LIMIT,
    ) -> StorefrontDressListView:
        """Three statements: page, count, covers.

        Clamped again below the router so a non-router caller cannot request an
        unbounded page. `archived` and `search` are pinned, not parameters — no
        query string on this route can reach a repository predicate other than
        paging.
        """
        offset = min(max(offset, 0), MAX_LIST_OFFSET)
        limit = min(max(limit, 1), STOREFRONT_LIST_MAX_LIMIT)
        async with tenant_session(self._session_factory, tenant_id) as session:
            rows = await self._dresses.list_page(
                session, tenant_id, archived=False, search=None, offset=offset, limit=limit
            )
            total = await self._dresses.count(session, tenant_id, archived=False, search=None)
            covers = await self._media.covers_by_dress(session, tenant_id, [row.id for row in rows])

        items = [
            StorefrontDressView(
                row=row,
                # The window's media_count is discarded: gallery slot accounting
                # is an owner concern.
                cover=(sign_media(self._storage, covers[row.id].row) if row.id in covers else None),
            )
            for row in rows
        ]
        return StorefrontDressListView(items=items, total=total, offset=offset, limit=limit)

    async def get_dress(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID
    ) -> StorefrontDressDetailView:
        """Three statements: dress, variants, media."""
        async with tenant_session(self._session_factory, tenant_id) as session:
            row = await self._dresses.by_id(session, tenant_id, dress_id)
            if row is None:
                raise CatalogNotFoundError
            variants = await self._variants.list_active(session, tenant_id, dress_id)
            media = await self._media.list_ready(session, tenant_id, dress_id)

        return StorefrontDressDetailView(
            row=row,
            sizes=[
                StorefrontSizeView(size_label=item.size_label, available=item.quantity > 0)
                for item in variants
            ],
            media=[sign_media(self._storage, item) for item in media],
        )

    async def get_boutique(
        self, tenant_id: uuid.UUID, *, name: str, settings: dict[str, object]
    ) -> StorefrontBoutiqueView:
        """Two statements: rules and upcoming exceptions.

        `name` and `settings` arrive from the already-resolved TenantContext —
        `RepositoryTenantResolver` SELECTed the whole tenants row to route the
        request, so re-reading it here would buy nothing.
        """
        today = today_jerusalem(self._clock)
        async with tenant_session(self._session_factory, tenant_id) as session:
            rules = await self._rules.list_active(session, tenant_id)
            exceptions = await self._exceptions.list_active(session, tenant_id, on_or_after=today)

        raw_profile = settings.get("profile")
        profile: dict[str, object] = raw_profile if isinstance(raw_profile, dict) else {}
        return StorefrontBoutiqueView(
            name=name,
            profile=profile,
            hours=rules,
            exceptions=exceptions[:UPCOMING_EXCEPTIONS_LIMIT],
        )


def upcoming_exceptions(
    rows: list[AvailabilityException], today: datetime.date
) -> list[AvailabilityException]:
    """Today onward, capped. Kept as a pure function alongside the SQL-side
    `on_or_after` filter so the truncation rule is unit-testable with no I/O and
    so a caller holding a pre-fetched list applies the same cutoff."""
    return [row for row in rows if row.date >= today][:UPCOMING_EXCEPTIONS_LIMIT]
