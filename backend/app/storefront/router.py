"""The public storefront read API: three anonymous, tenant-scoped GETs over the
same services the owner console uses, projected through schemas that share no
inheritance with the manage ones.

**Why prefix="/storefront" and not a public corner of /manage.**
`CsrfOriginMiddleware.PROTECTED_PREFIX` is `/manage`, and any future edge rule
(WAF, CDN cache policy, per-path rate rule) written against `/manage` must not
accidentally cover — or, worse, exempt — anonymous traffic. One prefix, one
audience.

**It is deliberately NOT in tenancy EXEMPT_PATHS.** Public is not the same as
host-agnostic: every route here needs a resolved tenant, and an unresolvable host
must 404 before a handler runs.

**No auth dependency anywhere.** That is the feature, and it is the one thing a
copy-paste from `app/catalog/router.py` would quietly break, so
`test_storefront_api.py` runs F8's authentication guard in reverse over the same
route table.

**GET only; HEAD stays a 405, deliberately.** A HEAD would run the whole handler
— minting signed URLs and spending the same per-IP budget — to return a body the
client discards, and the things that HEAD a URL (link previewers, uptime probes)
are pointed at HTML pages and `/health`, not at a JSON read API.
"""

import datetime
from collections.abc import Sequence
from typing import Annotated
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request, Response

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.router import RateLimitedError, _client_ip
from app.boutique.router import get_boutique_service
from app.boutique.service import AvailabilityResult, BoutiqueSettingsService, SettingsResult
from app.catalog.router import get_catalog_service
from app.catalog.service import MAX_LIST_OFFSET, CatalogService, DressView, MediaView
from app.catalog.validation import DRESS_LIST_DEFAULT_LIMIT
from app.core.config import get_settings
from app.models.availability import AvailabilityException
from app.models.dress import Dress
from app.storefront.schemas import (
    PublicBoutiqueResponse,
    PublicDressDetailResponse,
    PublicDressListResponse,
    PublicDressResponse,
    PublicHoursExceptionResponse,
    PublicHoursRuleResponse,
    PublicMediaResponse,
    PublicProfileResponse,
    PublicVariantResponse,
)
from app.tenancy.middleware import get_current_tenant

# The boutique's own wall clock. Hours, exception dates and "closed today" are
# local-calendar facts, so filtering them against a UTC date would drop or keep a
# row for two hours either side of midnight in Israel.
BOUTIQUE_TIMEZONE = ZoneInfo("Asia/Jerusalem")

NO_STORE = "no-store"


def _no_store(response: Response) -> None:
    """Set on the ROUTER, not per route. Every dress response here carries
    presigned GET URLs valid for SIGNED_GET_TTL_SECONDS — bearer material that
    must not land in a shared cache, a CDN, or a bfcache entry. Setting it
    centrally is what makes the invariant structural: a route added later cannot
    forget it, and /boutique pays nothing for carrying it.
    """
    response.headers["cache-control"] = NO_STORE


def _rate_limit(request: Request) -> None:
    """A per-(tenant, IP) read budget on the one surface with no session behind it.

    Skipped entirely when `_client_ip` yields nothing. Without a trusted proxy
    appending X-Forwarded-For, `request.client.host` is the proxy — so the key
    would collapse to a per-tenant bucket, and a single anonymous visitor could
    429 a boutique's whole storefront. That is strictly worse than no limiter.

    ponytail: in-process fixed window, single instance, no bucket eviction —
    the same ceiling every other limiter here has. Redis-backed distributed
    limiting is the F21 hardening gate.
    """
    ip = _client_ip(request, get_settings().trust_forwarded_for)
    if ip is None:
        return
    limiter: FixedWindowRateLimiter = request.app.state.storefront_rate_limiter
    key = f"sf:{get_current_tenant(request).id}:{ip}"
    if limiter.is_blocked(key):
        raise RateLimitedError
    # FixedWindowRateLimiter counts only what is explicitly recorded — its
    # docstring says "successes never count", which is right for a login form and
    # wrong here. A SUCCESSFUL list mints up to DRESS_LIST_DEFAULT_LIMIT signed
    # URLs, so it is precisely what this bound exists to cap; without this line
    # the limiter is inert. Same reasoning as the presign throttle.
    limiter.record_failure(key)


router = APIRouter(prefix="/storefront", dependencies=[Depends(_no_store), Depends(_rate_limit)])

Catalog = Annotated[CatalogService, Depends(get_catalog_service)]
Boutique = Annotated[BoutiqueSettingsService, Depends(get_boutique_service)]


# --- mappers: pure, importable, and the only place each rule lives ---


def jerusalem_today() -> datetime.date:
    return datetime.datetime.now(BOUTIQUE_TIMEZONE).date()


def upcoming_exceptions(
    rows: Sequence[AvailabilityException], today: datetime.date
) -> list[AvailabilityException]:
    """Today onward only. A past exception is history the owner may want and
    noise the customer certainly does not.

    Takes the clock as an argument so the filter is unit-testable with no I/O.
    `AvailabilityExceptionsRepository.list_active` is deliberately left alone —
    the manage console needs the full history.
    """
    return [row for row in rows if row.date >= today]


def public_price(row: Dress) -> int | None:
    """The ONE place the price rule lives. A hidden price that reaches the browser
    and is merely not rendered is not hidden."""
    return row.price_agorot if row.price_visible else None


def public_media(view: MediaView) -> PublicMediaResponse:
    return PublicMediaResponse(url=view.url, url_expires_at=view.url_expires_at)


def public_dress(view: DressView) -> PublicDressResponse:
    return PublicDressResponse(
        id=view.row.id,
        name=view.row.name,
        price_agorot=public_price(view.row),
        reserved=view.row.reserved,
        cover=public_media(view.cover) if view.cover is not None else None,
    )


def public_dress_detail(view: DressView) -> PublicDressDetailResponse:
    return PublicDressDetailResponse(
        id=view.row.id,
        name=view.row.name,
        description=view.row.description,
        price_agorot=public_price(view.row),
        reserved=view.row.reserved,
        # availability, never stock: the count is boutique-confidential.
        variants=[
            PublicVariantResponse(size_label=row.size_label, available=row.quantity > 0)
            for row in view.variants
        ],
        media=[public_media(item) for item in view.media],
    )


def public_boutique(
    *,
    name: str,
    settings: SettingsResult,
    availability: AvailabilityResult,
    today: datetime.date,
) -> PublicBoutiqueResponse:
    profile = settings.profile
    # Only the four keys the design renders are read out of the JSONB blob, so a
    # key a later feature adds to `profile` cannot reach the public page by
    # default. `toggles` is not read at all.
    return PublicBoutiqueResponse(
        name=name,
        profile=PublicProfileResponse(
            phone=profile.get("phone"),
            address=profile.get("address"),
            description=profile.get("description"),
            maps_url=profile.get("maps_url"),
        ),
        rules=[
            PublicHoursRuleResponse(
                day_of_week=rule.day_of_week,
                open_time=rule.open_time,
                close_time=rule.close_time,
            )
            for rule in availability.rules
        ],
        exceptions=[
            PublicHoursExceptionResponse(
                date=row.date,
                open_time=row.open_time,
                close_time=row.close_time,
                note=row.note,
            )
            for row in upcoming_exceptions(availability.exceptions, today)
        ],
    )


# --- routes ---


@router.get("/dresses")
async def list_dresses(
    request: Request,
    service: Catalog,
    offset: Annotated[int, Query(ge=0, le=MAX_LIST_OFFSET)] = 0,
) -> PublicDressListResponse:
    """`offset` is the ONLY query parameter. No `limit` and no `search`: the page
    size is pinned at DRESS_LIST_DEFAULT_LIMIT so one anonymous request can never
    mint 100 signed URLs, and the design ships no filter UI, so nothing is lost.

    `le` matters as much as `ge`: Python ints are unbounded and the value is bound
    into `OFFSET $n::BIGINT`, so without a ceiling `?offset=2**63` is a 500 from
    asyncpg's encoder rather than a 400 from here.
    """
    tenant = get_current_tenant(request)
    result = await service.list_dresses(
        tenant.id, archived=False, offset=offset, limit=DRESS_LIST_DEFAULT_LIMIT
    )
    return PublicDressListResponse(
        items=[public_dress(view) for view in result.items],
        total=result.total,
        offset=result.offset,
        limit=result.limit,
    )


@router.get("/dresses/{dress_id}")
async def get_dress(
    request: Request, service: Catalog, dress_id: UUID
) -> PublicDressDetailResponse:
    tenant = get_current_tenant(request)
    # include_archived=False is the whole difference from the manage detail: an
    # archived id routes through DressesRepository.by_id, misses, and becomes the
    # same indistinguishable 404 as an unknown or a foreign one.
    view = await service.get_dress(tenant.id, dress_id, include_archived=False)
    return public_dress_detail(view)


@router.get("/boutique")
async def get_boutique(request: Request, service: Boutique) -> PublicBoutiqueResponse:
    tenant = get_current_tenant(request)
    settings = await service.get_settings(tenant.id)
    availability = await service.get_availability(tenant.id)
    return public_boutique(
        name=tenant.name,
        settings=settings,
        availability=availability,
        today=jerusalem_today(),
    )
