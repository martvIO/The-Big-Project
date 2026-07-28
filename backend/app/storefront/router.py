"""The public storefront read API: three anonymous, tenant-scoped GETs.

**Why prefix="/storefront" and not a public corner of /manage.**
`CsrfOriginMiddleware.PROTECTED_PREFIX` is `/manage` and F10 has no mutating
route to protect; `app/boutique/router.py` and `app/catalog/router.py` both
mount `/manage`, so a third router there would make path shadowing a three-way
hazard; and the dev proxy needs one unambiguous prefix to forward. Any future
edge rule (WAF, CDN cache policy, per-path rate rule) written against `/manage`
must not accidentally cover — or, worse, exempt — anonymous traffic.

**It is deliberately NOT in tenancy EXEMPT_PATHS.** Public is not the same as
host-agnostic: every route here needs a resolved tenant, and an unresolvable
host must 404 before a handler runs. Tenant identity derives from DNS, never
from auth and never from client input.

**No auth dependency anywhere.** `Depends(get_current_staff)` is this codebase's
one and only owner-only marker, and its ABSENCE is what makes a route public —
there is no role guard, scope or annotation to also remove. That is the feature,
and it is the one thing a copy-paste from `app/catalog/router.py` would quietly
break, so `test_storefront_api.py` runs F8's authentication guard in reverse
over the same route table.

**No handler reads a cookie.** The storefront and the console share the origin
`{slug}.{domain}`, so a browser would attach `boutique_session` if the client
asked it to; the client sends `credentials: "omit"` and a test asserts that a
request carrying a valid owner cookie gets a byte-identical response to one
carrying none. A public endpoint that behaves differently for a logged-in owner
is a public endpoint with a hidden second contract.

**GET only; HEAD stays a 405, deliberately.** A HEAD would run the whole handler
— minting signed URLs and spending the same read budget — to return a body the
client discards, and the things that HEAD a URL (link previewers, uptime probes)
are pointed at HTML pages and `/health`, not at a JSON read API.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.auth.rate_limit import FixedWindowRateLimiter
from app.catalog.service import MediaView
from app.models.dress import Dress
from app.storefront.schemas import (
    BoutiqueResponse,
    DressListResponse,
    ExceptionRow,
    HoursRow,
    SizeChip,
    StorefrontDetail,
    StorefrontDress,
    StorefrontMedia,
)
from app.storefront.service import (
    StorefrontBoutiqueView,
    StorefrontDressDetailView,
    StorefrontDressListView,
    StorefrontDressView,
    StorefrontService,
)
from app.storefront.validation import (
    STOREFRONT_LIST_DEFAULT_LIMIT,
    STOREFRONT_LIST_MAX_LIMIT,
    StorefrontThrottledError,
)
from app.tenancy.middleware import get_current_tenant

NO_STORE = "no-store"


def get_storefront_service(request: Request) -> StorefrontService:
    service: StorefrontService = request.app.state.storefront_service
    return service


def _no_store(response: Response) -> None:
    """Set on the ROUTER, not per route. Every dress response here carries
    presigned GET URLs valid for SIGNED_GET_TTL_SECONDS — bearer material that
    must not land in a shared cache, a CDN, or a bfcache entry. Setting it
    centrally is what makes the invariant structural: a route added later cannot
    forget it, and /boutique pays nothing for carrying it.
    """
    response.headers["cache-control"] = NO_STORE


def _throttle(request: Request) -> None:
    """A per-TENANT read budget on the one surface with no session behind it.

    Keyed per tenant, not per IP, and that is a deliberate, honest trade: per-IP
    keying needs `trust_forwarded_for`, which the Cloudflare-fallback two-hop
    caveat leaves unresolved, and behind an untrusted proxy `request.client.host`
    is the proxy — so an IP key would silently collapse to one bucket for every
    visitor anyway.

    Be clear about what this is: a runaway brake, not a defence. It is
    in-process and single-instance (so it resets on deploy and does not
    aggregate across replicas), and it does not bound S3 egress at all — a
    minted URL is redeemable by anyone, any number of times, for 900 seconds. A
    determined scraper degrades the boutique it is scraping. Distributed
    limiting, per-IP keying and a WAF are the F21 hardening gate.

    The window is sized so it CANNOT fire on organic traffic: a first paint is
    2 requests and a dress tap is 1 more, so the default 6000/60s is roughly
    3000 first-paints per minute per tenant. The obvious number, 600, would 429
    real customers the minute a boutique's Instagram story lands — the exact
    traffic event this product exists for — while a scraper simply paces itself.
    """
    limiter: FixedWindowRateLimiter = request.app.state.storefront_rate_limiter
    key = f"storefront:{get_current_tenant(request).id}"
    if limiter.is_blocked(key):
        raise StorefrontThrottledError
    # FixedWindowRateLimiter counts only what is explicitly recorded — its
    # docstring says "successes never count", which is right for a login form
    # and wrong here. A SUCCESSFUL list mints up to STOREFRONT_LIST_MAX_LIMIT
    # signed URLs, so it is precisely what this bound exists to cap; without
    # this line the limiter is inert. Same reasoning as the presign throttle.
    limiter.record_failure(key)


router = APIRouter(prefix="/storefront", dependencies=[Depends(_no_store), Depends(_throttle)])

Storefront = Annotated[StorefrontService, Depends(get_storefront_service)]


# --- projections: pure, importable, and the only place each rule lives ---


def _public_price(row: Dress) -> int | None:
    """The ONE place the price rule lives. A hidden price that reaches the
    browser and is merely not rendered is not hidden."""
    return row.price_agorot if row.price_visible else None


def _media(view: MediaView) -> StorefrontMedia:
    return StorefrontMedia(url=view.url, url_expires_at=view.url_expires_at)


def public_dress(view: StorefrontDressView) -> StorefrontDress:
    return StorefrontDress(
        id=view.row.id,
        name=view.row.name,
        price_agorot=_public_price(view.row),
        reserved=view.row.reserved,
        cover=_media(view.cover) if view.cover is not None else None,
    )


def public_dress_detail(view: StorefrontDressDetailView) -> StorefrontDetail:
    return StorefrontDetail(
        id=view.row.id,
        name=view.row.name,
        # `or None` for the same reason as the profile fields below: a cleared
        # description is "" in the column, and "" renders an empty <p>.
        description=view.row.description or None,
        price_agorot=_public_price(view.row),
        reserved=view.row.reserved,
        sizes=[
            SizeChip(size_label=item.size_label, available=item.available) for item in view.sizes
        ],
        media=[_media(item) for item in view.media],
    )


def public_boutique(view: StorefrontBoutiqueView) -> BoutiqueResponse:
    """Only the six keys the design renders are read out of the JSONB blob, so a
    key a later feature adds to `profile` cannot reach the public page by
    default.

    `or None` collapses "" to null. Empty string is the wire's *canonical
    cleared value* (see boutique/validation.py) and the manage form seeds every
    blank field to "" before submitting, so any owner who saves the profile once
    converts their blanks from null to "". Shipping "" to the storefront renders
    `<a href="tel:">` with no accessible name — a WCAG 2.4.4 (A) failure, worst
    of all on the statutory הצהרת נגישות contact block. Both values already MEAN
    "not set"; making them identical on the wire is what lets every client guard
    be a plain null check.
    """
    profile = view.profile

    def field(key: str) -> str | None:
        value = profile.get(key)
        return value or None if isinstance(value, str) else None

    return BoutiqueResponse(
        name=view.name,
        essence=field("essence"),
        description=field("description"),
        phone=field("phone"),
        address=field("address"),
        maps_url=field("maps_url"),
        instagram=field("instagram"),
        hours=[
            HoursRow(
                day_of_week=rule.day_of_week,
                open_time=rule.open_time,
                close_time=rule.close_time,
            )
            for rule in view.hours
        ],
        exceptions=[
            ExceptionRow(
                date=row.date,
                open_time=row.open_time,
                close_time=row.close_time,
                note=row.note,
            )
            for row in view.exceptions
        ],
    )


def public_dress_list(view: StorefrontDressListView) -> DressListResponse:
    return DressListResponse(
        items=[public_dress(item) for item in view.items],
        total=view.total,
        offset=view.offset,
        limit=view.limit,
    )


# --- routes ---


@router.get("/dresses")
async def list_dresses(
    request: Request,
    service: Storefront,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[
        int, Query(ge=1, le=STOREFRONT_LIST_MAX_LIMIT)
    ] = STOREFRONT_LIST_DEFAULT_LIMIT,
) -> DressListResponse:
    """`offset` and `limit` are the ONLY query parameters, and `limit` is capped
    at STOREFRONT_LIST_MAX_LIMIT so one anonymous request can never mint more
    than a page of signed URLs. There is no `archived` and no `search`: no query
    string on this route can reach a repository predicate other than paging.
    """
    tenant = get_current_tenant(request)
    return public_dress_list(await service.list_dresses(tenant.id, offset=offset, limit=limit))


@router.get("/dresses/{dress_id}")
async def get_dress(request: Request, service: Storefront, dress_id: UUID) -> StorefrontDetail:
    tenant = get_current_tenant(request)
    # `by_id` pins deleted_at IS NULL, so an archived dress misses and becomes
    # the same indistinguishable 404 as an unknown or a foreign one.
    return public_dress_detail(await service.get_dress(tenant.id, dress_id))


@router.get("/boutique")
async def get_boutique(request: Request, service: Storefront) -> BoutiqueResponse:
    tenant = get_current_tenant(request)
    return public_boutique(
        await service.get_boutique(tenant.id, name=tenant.name, settings=tenant.settings)
    )
