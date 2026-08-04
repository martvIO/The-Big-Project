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
from collections.abc import Mapping

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.booking.service import deposit_due
from app.booking.slots import Slot, materialize_slots
from app.booking.validation import SLOT_WINDOW_DEFAULT_DAYS, SLOT_WINDOW_MAX_DAYS
from app.catalog.service import CatalogNotFoundError, MediaView, sign_media
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.dress_media import DressMediaRepository
from app.db.repositories.dress_variants import DressVariantsRepository
from app.db.repositories.dresses import DressesRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.models.appointment_type import AppointmentType
from app.models.availability import AvailabilityException, AvailabilityRule
from app.models.dress import Dress
from app.models.terms_version import TermsVersion
from app.payments.service import GatewayCredentialService
from app.privacy.text import ResolvedPrivacy, resolve_privacy
from app.storage.base import MediaStorage
from app.storefront.validation import (
    BOUTIQUE_TIMEZONE,
    STOREFRONT_LIST_DEFAULT_LIMIT,
    STOREFRONT_LIST_MAX_LIMIT,
    UPCOMING_EXCEPTIONS_LIMIT,
    Clock,
    SlotWindowError,
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
    # F20 D13. Resolved HERE and not in `public_boutique`, because this is the
    # one place the whole `settings` blob is in hand — the projection receives
    # this view and nothing else, which is what keeps the "only the keys the
    # design renders are read" rule enforceable rather than aspirational.
    privacy: ResolvedPrivacy


class StorefrontService:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        media_storage: MediaStorage,
        clock: Clock | None = None,
        gateway_credentials: GatewayCredentialService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._storage = media_storage
        self._clock = clock
        # D10. The service, not the repository: the disclosure has to run the
        # USE path's predicate, and `is_connected` is where that lives. None =
        # no gateway service wired, which reads as not connected.
        self._gateway_credentials = gateway_credentials
        self._dresses = DressesRepository()
        self._variants = DressVariantsRepository()
        self._media = DressMediaRepository()
        self._rules = AvailabilityRulesRepository()
        self._exceptions = AvailabilityExceptionsRepository()
        self._appointment_types = AppointmentTypesRepository()
        self._bookings = BookingsRepository()
        self._terms = TermsVersionsRepository()

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

    async def list_slots(
        self,
        tenant_id: uuid.UUID,
        *,
        from_date: datetime.date | None = None,
        to_date: datetime.date | None = None,
    ) -> list[Slot]:
        """Three statements: the active weekly set, the exceptions in the
        window, and the per-instant booked counts. The grid itself is computed
        by the pure engine.

        F12 shipped this with `booked={}`; F13 closed the seam — this is the
        one line the parameter existed for, and the engine did not change. Full
        slots are DROPPED by the engine, never marked, so the response still
        discloses nothing about the boutique's booking density.
        """
        today = today_jerusalem(self._clock)
        window_start, window_end = slot_window(from_date, to_date, today)
        # The engine keys `booked` by UTC start instant; the window is boutique
        # calendar dates, so its edges become boutique-midnight instants. The
        # right edge is half-open — start of the day AFTER window_end.
        window_first = datetime.datetime.combine(
            window_start, datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
        ).astimezone(datetime.UTC)
        window_last = datetime.datetime.combine(
            window_end + datetime.timedelta(days=1), datetime.time.min, tzinfo=BOUTIQUE_TIMEZONE
        ).astimezone(datetime.UTC)
        async with tenant_session(self._session_factory, tenant_id) as session:
            rules = await self._rules.list_active(session, tenant_id)
            # Bounded on BOTH sides in SQL: the window bounds the response
            # either way, but an unbounded upper predicate would still scan
            # every future exception the boutique has ever recorded, on every
            # anonymous request.
            exceptions = await self._exceptions.list_active(
                session, tenant_id, on_or_after=window_start, on_or_before=window_end
            )
            booked = await self._bookings.count_by_start(
                session, tenant_id, from_instant=window_first, until_instant=window_last
            )
        now = self._clock() if self._clock is not None else datetime.datetime.now(datetime.UTC)
        return materialize_slots(
            rules=rules,
            exceptions=exceptions,
            booked=booked,
            window_start=window_start,
            window_end=window_end,
            now=now.astimezone(datetime.UTC),
        )

    async def list_appointment_types(
        self, tenant_id: uuid.UUID, *, settings: Mapping[str, object] | None = None
    ) -> list[AppointmentType]:
        """Two statements now. Active types only — `list_active` pins
        `deleted_at IS NULL`, so an archived type leaves the public surface the
        same way an archived dress does.

        No audience filter: `brides_only` marks a type for brides and an
        ANONYMOUS visitor cannot be classified as one, so a server-side filter
        here would be theatre. The field ships so the UI can label the option;
        real enforcement waits for a client identity (E5).

        The second statement is D10's gateway read, asked ONCE for the page
        rather than once per type, inside the session this method already opens
        — an extra indexed statement on an open connection, on a route that is
        already throttled. `settings` is the resolved TenantContext's; ABSENT
        reads as deposits-off, so a caller that has not been taught to pass it
        discloses no deposit rather than one it cannot collect.
        """
        async with tenant_session(self._session_factory, tenant_id) as session:
            rows = await self._appointment_types.list_active(session, tenant_id)
            connected = self._gateway_credentials is not None and (
                await self._gateway_credentials.is_connected(tenant_id, session)
            )
        # AFTER the session has committed and closed, deliberately: these rows
        # are detached here, so clearing the pair below is a projection and can
        # never be flushed back as a write.
        return [
            row if deposit_due(settings, row, gateway_connected=connected) else hide_deposit(row)
            for row in rows
        ]

    async def get_terms(self, tenant_id: uuid.UUID) -> TermsVersion:
        """One statement. A boutique that never published a policy has nothing
        for a customer to accept, so the miss is the module's ordinary 404
        rather than an empty shape the client would have to special-case."""
        async with tenant_session(self._session_factory, tenant_id) as session:
            row = await self._terms.current(session, tenant_id)
        if row is None:
            raise CatalogNotFoundError
        return row

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
            # No round trip: `settings` arrived on the already-resolved
            # TenantContext, and `resolve_privacy` is pure.
            privacy=resolve_privacy(dict(settings)),
        )


def hide_deposit(row: AppointmentType) -> AppointmentType:
    """F17's Q1, applied to one row: with no collectable deposit the storefront
    hides it entirely and books as if deposits were off.

    Cleared ON THE ROW rather than omitted from the wire because the row is the
    projection's only input — `public_appointment_type` copies the pair field by
    field — so "no deposit is owed" has to be true of what it copies. That is
    also the STRONGER disclosure: `{required: false, amount: null}` is exactly
    what a type that never had a deposit ships, whereas an omitted pair would be
    a distinguishable third state telling an anonymous visitor that THIS
    boutique wants a deposit and currently cannot take one.

    Call it only on a detached row (the session has committed and closed) — on
    an attached one SQLAlchemy would flush the clear into the boutique's own
    configuration.
    """
    row.deposit_required = False
    row.deposit_amount_agorot = None
    return row


def slot_window(
    from_date: datetime.date | None, to_date: datetime.date | None, today: datetime.date
) -> tuple[datetime.date, datetime.date]:
    """Resolve and bound the requested window into the publishable band.

    Pure and importable so the clamping rule is unit-testable and so the router
    stays a parser. `to < from` is a caller error (400); a `to` beyond the
    ceiling is silently clamped rather than rejected, because a picker asking
    for more than it can render is a UI bug, not a user error, and 60 days of
    grid is already a generous answer.

    **Both bounds are clamped against `today`, never against the caller's own
    value, and that is what makes the arithmetic here total.** `date + timedelta`
    raises `OverflowError` within 60 days of `date.max`, and `?from=9999-12-31`
    is among the first things anyone probes on a public endpoint — it would
    escape as a bare 500 outside the house error shape. `today` comes from a
    real clock and can never be near either end of the `date` range. Same
    reasoning as `MAX_LIST_OFFSET` above: an unbounded caller-supplied value
    reaches something that raises rather than validates.

    Clamping the FLOOR to today costs nothing, because the engine already drops
    everything at or before `now`. A window lying entirely in the past comes
    back inverted and materializes to no slots — the same empty answer as
    before, without a second rule that could disagree with the first.
    """
    requested_start = from_date if from_date is not None else today
    ceiling = today + datetime.timedelta(days=SLOT_WINDOW_MAX_DAYS)
    # Checked against what the CALLER asked for, so a wholly-past window stays
    # an empty answer rather than becoming a 400 once the floor clamp moves.
    if to_date is not None and to_date < requested_start:
        raise SlotWindowError("`to` must not precede `from`.")
    start = min(max(requested_start, today), ceiling)
    if to_date is None:
        return start, min(start + datetime.timedelta(days=SLOT_WINDOW_DEFAULT_DAYS), ceiling)
    # min() only: comparing against a date.max `to` is safe where adding to it
    # is not.
    return start, min(to_date, ceiling)


def upcoming_exceptions(
    rows: list[AvailabilityException], today: datetime.date
) -> list[AvailabilityException]:
    """Today onward, capped. Kept as a pure function alongside the SQL-side
    `on_or_after` filter so the truncation rule is unit-testable with no I/O and
    so a caller holding a pre-fetched list applies the same cutoff."""
    return [row for row in rows if row.date >= today][:UPCOMING_EXCEPTIONS_LIMIT]
