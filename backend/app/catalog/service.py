"""Catalog business logic: dresses, their size matrix and their photos.

Three invariants hold this module together.

**No MediaStorage network method inside a tenant_session.** `tenant_session` is
`async with session_factory() as session, session.begin()` — the whole block is
ONE Postgres transaction, and boto3's default 60 s connect + 60 s read timeouts
would pin a pool connection *and* a per-dress advisory lock across an S3 stall.
So presign, confirm and media-delete are each explicit multi-step sequences with
every `head_object` / `read_prefix` / `delete_object` outside the session.
`presigned_post` and `signed_get_url` are local HMAC and may run anywhere;
mutations that return a detail view do their write transaction, then a short
read transaction, then mint signed URLs.

**Resolve the parent dress first.** The first statement inside the session — and,
for presign, inside the lock — is `dresses.by_id(...)`, whose predicate makes an
unknown id, an archived dress and another tenant's dress one indistinguishable
404. `build_media_key` runs only after that returns a row, so no unverified id
can reach an S3 key.

**Two lock prefixes.** Photo work takes `dress-media:<id>` and stock work takes
`dress-variants:<id>`, so the two never serialise against each other, and both
stay clear of Feature 7's un-prefixed `hashtext(:tenant_id)` lock space.
"""

import dataclasses
import datetime
import logging
import uuid
from collections.abc import Sequence
from typing import NoReturn

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.catalog.keys import build_media_filename, build_media_key
from app.catalog.validation import (
    DRESS_LIST_DEFAULT_LIMIT,
    DRESS_LIST_MAX_LIMIT,
    MAGIC_PREFIX_LENGTH,
    MAX_MEDIA_PER_DRESS,
    PENDING_MEDIA_TTL_SECONDS,
    PRESIGN_TTL_SECONDS,
    SIGNED_GET_TTL_SECONDS,
    VariantInput,
    matches_magic_prefix,
    normalize_size_label,
    validate_dress,
    validate_presign,
    validate_search,
    validate_variants,
)
from app.db.repositories.dress_media import DressMediaRepository
from app.db.repositories.dress_variants import DressVariantsRepository, VariantAggregate
from app.db.repositories.dresses import DressesRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.models.constants import DressMediaStatus
from app.models.dress import Dress
from app.models.dress_media import DressMedia
from app.models.dress_variant import DressVariant
from app.storage.base import (
    MediaNotConfiguredError,
    MediaStorage,
    MediaStorageUnavailableError,
    PresignedPost,
)

logger = logging.getLogger("catalog")

# DRESS_LIST_MAX_LIMIT's missing twin. `offset` reaches the driver as
# `OFFSET $n::BIGINT` (SQLAlchemy's asyncpg dialect casts it explicitly), so a
# value past int8 never becomes a 400 — it dies in asyncpg's `int8_encode` as a
# DataError with no handler above it, i.e. a 500 on an anonymous endpoint.
# 1_000_000 is ~41,000 pages of DRESS_LIST_DEFAULT_LIMIT for a catalog that holds
# tens of dresses, and 9.2e12x inside int8, so nothing downstream can overflow.
# ponytail: lives here rather than beside DRESS_LIST_MAX_LIMIT in validation.py
# only to keep this branch's diff off a file other tracks are editing.
MAX_LIST_OFFSET = 1_000_000

# hashtext() keys an xact-scoped lock that releases with the transaction. The
# prefix is a SQL literal and the dress id is bound — never interpolated.
_MEDIA_LOCK = text("SELECT pg_advisory_xact_lock(hashtext('dress-media:' || :dress_id))")
_VARIANTS_LOCK = text("SELECT pg_advisory_xact_lock(hashtext('dress-variants:' || :dress_id))")


class CatalogNotFoundError(DomainNotFoundError):
    """Unknown dress, unknown media, an archived dress on a route other than
    detail/restore, or a media id parented by a different dress — all one
    indistinguishable miss, including another tenant's ids."""


class DuplicateSizeError(Exception):
    """Two variants normalise to the same lower(size_label) — caught in the
    payload, or by the partial unique index, never as a raw 500."""


class MediaLimitReachedError(Exception):
    """Ready + young-pending photos already fill the per-dress gallery."""


class MediaNotUploadedError(Exception):
    """Confirm found no object: a genuine 404 head miss, not an outage. The row
    stays pending and remains confirmable."""


class MediaMismatchError(Exception):
    """The object's content type or its first bytes disagree with the row that
    authorised the upload. The object is deleted best-effort before this raises."""


class MediaOrderMismatchError(Exception):
    """The reorder payload is not an exact permutation of the current ready set.
    409, not 400: the body is well-formed and conflicts with server state."""


class MediaPresignThrottledError(Exception):
    """Per-tenant presign throttle tripped."""


@dataclasses.dataclass(frozen=True)
class StockSummary:
    variant_count: int
    total_quantity: int
    out_of_stock: bool


@dataclasses.dataclass(frozen=True)
class MediaView:
    """url is None when no bucket is configured, or when signing that url fails —
    reads keep working with the gallery unrendered, and only the media write
    endpoints answer 503."""

    row: DressMedia
    url: str | None
    url_expires_at: datetime.datetime | None


@dataclasses.dataclass(frozen=True)
class DressView:
    """The frozen view the router turns into a response (Feature 7's
    SettingsResult precedent): out_of_stock, media_count, cover and archived are
    not columns, so model_validate(row) would raise.

    `variants` and `media` are the detail payload and stay empty on list rows —
    paying for them per row is the N+1 the pinned four-statement list shape
    exists to prevent. `slots_remaining` is likewise authoritative only on the
    detail path, which is the only place the response carries it; list rows
    derive it from the ready count because the list deliberately does not buy a
    pending-count statement.
    """

    row: Dress
    summary: StockSummary
    media_count: int
    cover: MediaView | None
    uploads_enabled: bool
    slots_remaining: int
    variants: list[DressVariant] = dataclasses.field(default_factory=list)
    media: list[MediaView] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class DressListResult:
    items: list[DressView]
    total: int
    offset: int
    limit: int


@dataclasses.dataclass(frozen=True)
class PresignResult:
    media_id: uuid.UUID
    url: str
    fields: dict[str, str]
    expires_in: int
    max_bytes: int


@dataclasses.dataclass(frozen=True)
class _DetailRows:
    """Everything the detail view needs, read in one transaction so the signed
    URLs can be minted after it closes."""

    dress: Dress
    variants: list[DressVariant]
    media: list[DressMedia]
    aggregate: VariantAggregate
    active_media: int


def sign_media(storage: MediaStorage, row: DressMedia) -> MediaView:
    """Mint a presigned GET for one media row, degrading to `url=None`.

    Module-level and storage-injected so BOTH the owner console and the public
    storefront sign through the same function. The degradation rule below is a
    security-relevant invariant, and an invariant that exists in two places is
    one that will eventually hold in only one of them.

    Signing is local HMAC, so this is safe to call outside a session and would
    be a lie to await. With no bucket the url serialises as null rather than
    failing the read — only the media WRITE endpoints answer 503.
    """
    if not storage.is_configured:
        return MediaView(row=row, url=None, url_expires_at=None)
    try:
        url = storage.signed_get_url(
            key=row.storage_key,
            content_type=row.content_type,
            filename=build_media_filename(media_id=row.id, content_type=row.content_type),
            expires_in=SIGNED_GET_TTL_SECONDS,
        )
    except (MediaNotConfiguredError, MediaStorageUnavailableError):
        # A bucket whose credentials rotated is still `is_configured`, so
        # branching on that alone would let a signing failure propagate out
        # of a plain GET /manage/dresses as a 503 and take the whole catalog
        # down with the gallery. Degrade exactly as an absent bucket does.
        # The storage port already logged the operation and the key.
        logger.warning(
            "media url signing failed, serialising a null url: "
            "tenant_id=%s dress_id=%s media_id=%s",
            row.tenant_id,
            row.dress_id,
            row.id,
        )
        return MediaView(row=row, url=None, url_expires_at=None)
    expires_at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        seconds=SIGNED_GET_TTL_SECONDS
    )
    return MediaView(row=row, url=url, url_expires_at=expires_at)


def _stock_summary(aggregate: VariantAggregate) -> StockSummary:
    """The single out_of_stock formula. Nothing is stored: the only writer of
    stock is the variant replace, and a cached boolean would need either a
    trigger or a second write that can fail independently — both create a state
    where the badge and the matrix disagree. Zero variants ⇒ out of stock."""
    return StockSummary(
        variant_count=aggregate.variant_count,
        total_quantity=aggregate.total_quantity,
        out_of_stock=aggregate.total_quantity == 0,
    )


_EMPTY_AGGREGATE = VariantAggregate(variant_count=0, total_quantity=0)


class CatalogService:
    """Every tenant-table access goes through tenant_session — FORCE RLS would
    return zero rows without the context. `pending_ttl_seconds` is injectable so
    the stale-pending sweep is testable without sleeping or backdating rows."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        media_storage: MediaStorage,
        presign_rate_limiter: FixedWindowRateLimiter,
        pending_ttl_seconds: int = PENDING_MEDIA_TTL_SECONDS,
    ) -> None:
        self._session_factory = session_factory
        self._storage = media_storage
        self._presign_limiter = presign_rate_limiter
        self._pending_ttl_seconds = pending_ttl_seconds
        self._dresses = DressesRepository()
        self._variants = DressVariantsRepository()
        self._media = DressMediaRepository()

    # --- dresses ---

    async def list_dresses(
        self,
        tenant_id: uuid.UUID,
        *,
        archived: bool = False,
        search: str | None = None,
        offset: int = 0,
        limit: int = DRESS_LIST_DEFAULT_LIMIT,
    ) -> DressListResult:
        # Clamped again below the router (Feature 7 precedent) so a non-router
        # caller cannot request an unbounded page — or, at the top end, one the
        # int8 bind parameter cannot encode.
        offset = min(max(offset, 0), MAX_LIST_OFFSET)
        limit = min(max(limit, 1), DRESS_LIST_MAX_LIMIT)
        validate_search(search)
        async with tenant_session(self._session_factory, tenant_id) as session:
            rows = await self._dresses.list_page(
                session,
                tenant_id,
                archived=archived,
                search=search,
                offset=offset,
                limit=limit,
            )
            total = await self._dresses.count(session, tenant_id, archived=archived, search=search)
            dress_ids = [row.id for row in rows]
            aggregates = await self._variants.aggregate_by_dress(session, tenant_id, dress_ids)
            covers = await self._media.covers_by_dress(session, tenant_id, dress_ids)

        items = []
        for row in rows:
            cover = covers.get(row.id)
            media_count = cover.media_count if cover is not None else 0
            items.append(
                DressView(
                    row=row,
                    summary=_stock_summary(aggregates.get(row.id, _EMPTY_AGGREGATE)),
                    media_count=media_count,
                    cover=self._media_view(cover.row) if cover is not None else None,
                    uploads_enabled=self._storage.is_configured,
                    slots_remaining=max(MAX_MEDIA_PER_DRESS - media_count, 0),
                )
            )
        return DressListResult(items=items, total=total, offset=offset, limit=limit)

    async def create_dress(
        self,
        tenant_id: uuid.UUID,
        *,
        name: str,
        description: str | None,
        price_agorot: int | None,
        price_visible: bool,
        reserved: bool,
        sort_order: int,
    ) -> DressView:
        validate_dress(
            name=name,
            description=description,
            price_agorot=price_agorot,
            sort_order=sort_order,
        )
        async with tenant_session(self._session_factory, tenant_id) as session:
            row = await self._dresses.insert(
                session,
                tenant_id=tenant_id,
                name=name,
                description=description,
                price_agorot=price_agorot,
                price_visible=price_visible,
                reserved=reserved,
                sort_order=sort_order,
            )
        # A brand-new dress has no variants and no media, so the view is exact
        # without buying a second read transaction.
        return DressView(
            row=row,
            summary=_stock_summary(_EMPTY_AGGREGATE),
            media_count=0,
            cover=None,
            uploads_enabled=self._storage.is_configured,
            slots_remaining=MAX_MEDIA_PER_DRESS,
        )

    async def get_dress(self, tenant_id: uuid.UUID, dress_id: uuid.UUID) -> DressView:
        # Always resolves an archived dress: this is the OWNER's detail read, and
        # the owner must be able to open an archived dress to restore it.
        #
        # There is no include_archived switch any more. The storefront used to
        # pass False here; it now has its own StorefrontService.get_dress, which
        # calls DressesRepository.by_id directly — that pins deleted_at IS NULL,
        # so an archived id is an indistinguishable 404 by construction rather
        # than by a caller remembering to flip a flag.
        return await self._detail_view(tenant_id, dress_id, include_archived=True)

    async def update_dress(
        self,
        tenant_id: uuid.UUID,
        dress_id: uuid.UUID,
        *,
        name: str,
        description: str | None,
        price_agorot: int | None,
        price_visible: bool,
        reserved: bool,
        sort_order: int,
    ) -> DressView:
        validate_dress(
            name=name,
            description=description,
            price_agorot=price_agorot,
            sort_order=sort_order,
        )
        async with tenant_session(self._session_factory, tenant_id) as session:
            updated = await self._dresses.update_fields(
                session,
                tenant_id,
                dress_id,
                name=name,
                description=description,
                price_agorot=price_agorot,
                price_visible=price_visible,
                reserved=reserved,
                sort_order=sort_order,
            )
            if updated is None:
                raise CatalogNotFoundError
        return await self._detail_view(tenant_id, dress_id)

    async def archive_dress(self, tenant_id: uuid.UUID, dress_id: uuid.UUID) -> None:
        """One transaction, children first. now() is transaction_timestamp(), so
        all three stamps are byte-identical — which is what restore matches on.
        S3 objects are retained."""
        async with tenant_session(self._session_factory, tenant_id) as session:
            dress = await self._dresses.by_id(session, tenant_id, dress_id)
            if dress is None:
                raise CatalogNotFoundError
            await self._media.soft_delete_all(session, tenant_id, dress_id)
            await self._variants.soft_delete_all(session, tenant_id, dress_id)
            await self._dresses.soft_delete(session, tenant_id, dress_id)

    async def restore_dress(self, tenant_id: uuid.UUID, dress_id: uuid.UUID) -> DressView:
        async with tenant_session(self._session_factory, tenant_id) as session:
            dress = await self._dresses.by_id_any_state(session, tenant_id, dress_id)
            # Read the dress's own stamp FIRST: it is both the already-restored
            # guard and the key children are matched on.
            if dress is None or dress.deleted_at is None:
                raise CatalogNotFoundError
            archived_at = dress.deleted_at
            await self._variants.restore_archived_with(session, tenant_id, dress_id, archived_at)
            await self._media.restore_archived_with(session, tenant_id, dress_id, archived_at)
            await self._dresses.restore(session, tenant_id, dress_id)
        return await self._detail_view(tenant_id, dress_id)

    # --- variants ---

    async def replace_variants(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, variants: Sequence[VariantInput]
    ) -> DressView:
        # Validate FIRST — a rejected replacement must leave the matrix untouched.
        normalized = [
            dataclasses.replace(variant, size_label=normalize_size_label(variant.size_label))
            for variant in variants
        ]
        validate_variants(normalized)
        self._reject_duplicate_sizes(normalized)
        try:
            async with tenant_session(self._session_factory, tenant_id) as session:
                # Without the lock, two concurrent replaces under READ COMMITTED
                # would both pass validation and UNION their sets.
                await session.execute(_VARIANTS_LOCK, {"dress_id": str(dress_id)})
                dress = await self._dresses.by_id(session, tenant_id, dress_id)
                if dress is None:
                    raise CatalogNotFoundError
                await self._variants.soft_delete_all(session, tenant_id, dress_id)
                for variant in normalized:
                    await self._variants.insert(
                        session,
                        tenant_id=tenant_id,
                        dress_id=dress_id,
                        size_label=variant.size_label,
                        quantity=variant.quantity,
                        sort_order=variant.sort_order,
                    )
        except IntegrityError:
            # Validation already covered the CHECK bounds, so an IntegrityError
            # here is the lower(size_label) partial unique index.
            raise DuplicateSizeError from None
        return await self._detail_view(tenant_id, dress_id)

    @staticmethod
    def _reject_duplicate_sizes(variants: Sequence[VariantInput]) -> None:
        """Normalisation collapses whitespace but keeps case, so "US 6" and
        "us 6" still reach the DB as two labels. Catching them here turns the
        index violation into the same 409 without a wasted round trip."""
        seen: set[str] = set()
        for variant in variants:
            key = variant.size_label.lower()
            if key in seen:
                raise DuplicateSizeError
            seen.add(key)

    # --- media ---

    async def presign_media(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, *, content_type: str, byte_size: int
    ) -> PresignResult:
        # Step 1, before any work: the throttle is the OUTERMOST guard, so a
        # blocked tenant cannot spend a transaction discovering it is blocked.
        throttle_key = f"presign:{tenant_id}"
        if self._presign_limiter.is_blocked(throttle_key):
            raise MediaPresignThrottledError
        validate_presign(content_type=content_type, byte_size=byte_size)
        # Checked before the row is written: an unconfigured storage would
        # otherwise leave a pending row nobody can ever upload against.
        if not self._storage.is_configured:
            raise MediaNotConfiguredError

        media_id = uuid.uuid4()
        try:
            async with tenant_session(self._session_factory, tenant_id) as session:
                await session.execute(_MEDIA_LOCK, {"dress_id": str(dress_id)})
                dress = await self._dresses.by_id(session, tenant_id, dress_id)
                if dress is None:
                    raise CatalogNotFoundError
                swept = await self._media.sweep_stale_pendings(
                    session, tenant_id, dress_id, ttl_seconds=self._pending_ttl_seconds
                )
                active = await self._media.count_active(
                    session, tenant_id, dress_id, ttl_seconds=self._pending_ttl_seconds
                )
                if active >= MAX_MEDIA_PER_DRESS:
                    raise MediaLimitReachedError
                # media_id is minted client-side so the key exists before the
                # single, only statement that writes it — there is no post-insert
                # UPDATE of storage_key. build_media_key runs only now that the
                # dress resolved.
                storage_key = build_media_key(
                    tenant_id=tenant_id,
                    dress_id=dress_id,
                    media_id=media_id,
                    content_type=content_type,
                )
                await self._media.insert_pending(
                    session,
                    tenant_id=tenant_id,
                    dress_id=dress_id,
                    media_id=media_id,
                    storage_key=storage_key,
                    content_type=content_type,
                    byte_size=byte_size,
                )
        except (CatalogNotFoundError, MediaLimitReachedError):
            # A REJECTED presign is not free: it has already opened a
            # transaction, taken the per-dress media advisory lock and (for the
            # limit case) run the sweep plus two counting queries. Leaving it
            # unrecorded makes an unbounded loop against a full gallery — or
            # against random dress ids — cost the throttle nothing, which is
            # exactly what the bound exists to prevent.
            self._presign_limiter.record_failure(throttle_key)
            raise
        # FixedWindowRateLimiter counts only what is explicitly recorded — its
        # docstring says "successes never count". A SUCCESSFUL presign authorises
        # a 10 MiB write to our bucket, so it must be recorded by hand or the
        # throttle is inert. This is the create_terms_version precedent; deleting
        # this line because it reads like a bug is how the throttle dies. It sits
        # above the signing call rather than below it because the committed
        # transaction — not the signature — is what the bound exists to protect:
        # a signing failure must still cost budget.
        self._presign_limiter.record_failure(throttle_key)

        # Outside the transaction: the sweep is the only holder of those keys,
        # so deleting the objects here is what bounds the orphan window.
        for swept_id, swept_key in swept:
            await self._best_effort_delete(
                tenant_id=tenant_id, dress_id=dress_id, media_id=swept_id, storage_key=swept_key
            )
        try:
            presigned = self._sign_upload(
                key=storage_key, content_type=content_type, byte_size=byte_size
            )
        except (MediaNotConfiguredError, MediaStorageUnavailableError):
            # is_configured passed the early guard, then signing failed anyway —
            # a rotated or expired IAM key. The row is already committed and
            # count_active counts young pendings, so leaving it would spend a
            # gallery slot for a whole PENDING_MEDIA_TTL_SECONDS on an upload the
            # browser never received a policy for, until the twelfth attempt
            # answers 409 MEDIA_LIMIT_REACHED on a dress with no photos.
            await self._release_pending(tenant_id, dress_id, media_id)
            raise
        return PresignResult(
            media_id=media_id,
            url=presigned.url,
            fields=presigned.fields,
            expires_in=PRESIGN_TTL_SECONDS,
            # The policy pins an EXACT content-length range, so the maximum the
            # browser may post is precisely what it declared.
            max_bytes=byte_size,
        )

    async def confirm_media(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, media_id: uuid.UUID
    ) -> DressView:
        if not self._storage.is_configured:
            raise MediaNotConfiguredError

        async with tenant_session(self._session_factory, tenant_id) as session:
            dress = await self._dresses.by_id(session, tenant_id, dress_id)
            if dress is None:
                raise CatalogNotFoundError
            row = await self._media.by_id(session, tenant_id, dress_id, media_id)
            if row is None:
                raise CatalogNotFoundError
            already_ready = row.status == DressMediaStatus.READY
            storage_key = row.storage_key
            declared_type = row.content_type
        if already_ready:
            # The idempotent short-circuit: a retried confirm after a lost
            # response returns the same view without touching storage.
            return await self._detail_view(tenant_id, dress_id)

        # Outside any session: two real network calls, neither of which may hold
        # a Postgres transaction open.
        head = await self._storage.head_object(key=storage_key)
        if head is None:
            raise MediaNotUploadedError
        if head.content_type != declared_type:
            await self._reject_object(
                tenant_id=tenant_id,
                dress_id=dress_id,
                media_id=media_id,
                storage_key=storage_key,
            )
        prefix = await self._storage.read_prefix(key=storage_key, length=MAGIC_PREFIX_LENGTH)
        if not matches_magic_prefix(declared_type, prefix):
            # The content-type-honest polyglot: it passed the POST policy at
            # exactly the declared size, and this check is what refuses it.
            # Scope it honestly: this verifies the object AT CONFIRM TIME only.
            # An S3 POST policy cannot be revoked, so within the remainder of
            # PRESIGN_TTL_SECONDS the same policy can re-POST a different body
            # of the identical size to the identical key, and this check has
            # already run. The two layers that cover that window are
            # signed_get_url pinning ResponseContentType + attachment
            # disposition, and the media-origin-isolation invariant — neither is
            # optional, and neither may be trimmed on the strength of this one.
            await self._reject_object(
                tenant_id=tenant_id,
                dress_id=dress_id,
                media_id=media_id,
                storage_key=storage_key,
            )

        async with tenant_session(self._session_factory, tenant_id) as session:
            await session.execute(_MEDIA_LOCK, {"dress_id": str(dress_id)})
            row = await self._media.by_id(session, tenant_id, dress_id, media_id)
            if row is None:
                raise CatalogNotFoundError
            if row.status == DressMediaStatus.PENDING:
                next_sort = (
                    await self._media.max_ready_sort_order(session, tenant_id, dress_id)
                ) + 1
                await self._media.promote_to_ready(
                    session, tenant_id, dress_id, media_id, sort_order=next_sort
                )
        return await self._detail_view(tenant_id, dress_id)

    async def delete_media(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, media_id: uuid.UUID
    ) -> DressView:
        if not self._storage.is_configured:
            raise MediaNotConfiguredError

        async with tenant_session(self._session_factory, tenant_id) as session:
            await session.execute(_MEDIA_LOCK, {"dress_id": str(dress_id)})
            dress = await self._dresses.by_id(session, tenant_id, dress_id)
            if dress is None:
                raise CatalogNotFoundError
            row = await self._media.by_id(session, tenant_id, dress_id, media_id)
            if row is None:
                raise CatalogNotFoundError
            storage_key = row.storage_key
            was_pending = row.status == DressMediaStatus.PENDING
            await self._media.soft_delete(session, tenant_id, dress_id, media_id)

        if was_pending:
            # A pending row's POST policy is still redeemable for the rest of
            # PRESIGN_TTL_SECONDS and an S3 POST policy cannot be revoked, so the
            # object may land AFTER the delete_object below has already run
            # against a key that does not exist yet — a silent 204 that logs
            # nothing. The UI's abort path hits this on every timed-out upload,
            # so the key is recorded here: without it this orphan class leaves no
            # trace at all for the deferred reconcile job (spec Risk 4).
            logger.info(
                "pending media deleted, its upload policy may still be redeemed: "
                "tenant_id=%s dress_id=%s media_id=%s storage_key=%s",
                tenant_id,
                dress_id,
                media_id,
                storage_key,
            )
        # The row is already gone: the object delete is best-effort by design.
        await self._best_effort_delete(
            tenant_id=tenant_id, dress_id=dress_id, media_id=media_id, storage_key=storage_key
        )
        return await self._detail_view(tenant_id, dress_id)

    async def reorder_media(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, media_ids: Sequence[uuid.UUID]
    ) -> DressView:
        async with tenant_session(self._session_factory, tenant_id) as session:
            await session.execute(_MEDIA_LOCK, {"dress_id": str(dress_id)})
            dress = await self._dresses.by_id(session, tenant_id, dress_id)
            if dress is None:
                raise CatalogNotFoundError
            current = await self._media.list_ready(session, tenant_id, dress_id)
            # A multiset comparison: a subset, a superset, a duplicate and an
            # unknown id all fail it, and ids are unique so duplicates cannot
            # sneak through as a matching multiset.
            if sorted(media_ids) != sorted(row.id for row in current):
                raise MediaOrderMismatchError
            for position, media_id in enumerate(media_ids):
                await self._media.set_sort_order(session, tenant_id, dress_id, media_id, position)
        return await self._detail_view(tenant_id, dress_id)

    # --- views ---

    async def _detail_view(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, *, include_archived: bool = False
    ) -> DressView:
        """A short read transaction of its own, so signed URLs are minted after
        the session closes and a write path never holds a transaction across a
        storage call."""
        async with tenant_session(self._session_factory, tenant_id) as session:
            rows = await self._load_detail(
                session, tenant_id, dress_id, include_archived=include_archived
            )
        media = [self._media_view(row) for row in rows.media]
        return DressView(
            row=rows.dress,
            summary=_stock_summary(rows.aggregate),
            media_count=len(media),
            cover=media[0] if media else None,
            uploads_enabled=self._storage.is_configured,
            slots_remaining=max(MAX_MEDIA_PER_DRESS - rows.active_media, 0),
            variants=rows.variants,
            media=media,
        )

    async def _load_detail(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        dress_id: uuid.UUID,
        *,
        include_archived: bool,
    ) -> _DetailRows:
        dress = (
            await self._dresses.by_id_any_state(session, tenant_id, dress_id)
            if include_archived
            else await self._dresses.by_id(session, tenant_id, dress_id)
        )
        if dress is None:
            raise CatalogNotFoundError
        aggregates = await self._variants.aggregate_by_dress(session, tenant_id, [dress_id])
        return _DetailRows(
            dress=dress,
            variants=await self._variants.list_active(session, tenant_id, dress_id),
            media=await self._media.list_ready(session, tenant_id, dress_id),
            aggregate=aggregates.get(dress_id, _EMPTY_AGGREGATE),
            active_media=await self._media.count_active(
                session, tenant_id, dress_id, ttl_seconds=self._pending_ttl_seconds
            ),
        )

    async def _release_pending(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, media_id: uuid.UUID
    ) -> None:
        """Hand back the gallery slot a presign minted but could never hand to
        the browser. Takes the same lock as every other dress_media write, and —
        like every write path here — makes no storage call inside the session."""
        async with tenant_session(self._session_factory, tenant_id) as session:
            await session.execute(_MEDIA_LOCK, {"dress_id": str(dress_id)})
            await self._media.soft_delete(session, tenant_id, dress_id, media_id)

    def _sign_upload(self, *, key: str, content_type: str, byte_size: int) -> PresignedPost:
        """The one place the presign TTL is chosen. The length range is exact,
        not MIN..MAX: "declare 1 KiB, post 10 MiB" is the deliberate way to plant
        a large orphan the DB can never find again."""
        return self._storage.presigned_post(
            key=key,
            content_type=content_type,
            exact_bytes=byte_size,
            expires_in=PRESIGN_TTL_SECONDS,
        )

    def _media_view(self, row: DressMedia) -> MediaView:
        return sign_media(self._storage, row)

    async def _reject_object(
        self,
        *,
        tenant_id: uuid.UUID,
        dress_id: uuid.UUID,
        media_id: uuid.UUID,
        storage_key: str,
    ) -> NoReturn:
        """An object that fails verification must not persist — that is the
        second half of the orphan story."""
        await self._best_effort_delete(
            tenant_id=tenant_id, dress_id=dress_id, media_id=media_id, storage_key=storage_key
        )
        raise MediaMismatchError

    async def _best_effort_delete(
        self,
        *,
        tenant_id: uuid.UUID,
        dress_id: uuid.UUID,
        media_id: uuid.UUID,
        storage_key: str,
    ) -> None:
        try:
            await self._storage.delete_object(key=storage_key)
        except (MediaNotConfiguredError, MediaStorageUnavailableError):
            # Swallowed because the row is already gone, but never silently:
            # this line is the future reconcile job's only input.
            logger.warning(
                "media object delete failed, orphan retained: "
                "tenant_id=%s dress_id=%s media_id=%s storage_key=%s",
                tenant_id,
                dress_id,
                media_id,
                storage_key,
            )
