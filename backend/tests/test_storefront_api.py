"""Feature 10 fast API tests for the public storefront read surface: fake
services + a hardcoded TenantContext, no database (test_catalog_api.py style).

Two things here are load-bearing and everything else is scaffolding around them.

**The inverse of F8's auth guard.** `test_every_public_route_answers_without_a_session`
is `test_every_route_requires_authentication` read backwards: these three routes
must answer 200 with no cookie jar at all. A dependency copy-pasted from the
manage router would break the whole storefront, and nothing else would notice.

**The wire-absence walk.** `test_no_forbidden_key_appears_at_any_depth` parses
every response and recursively asserts that no manage-only key exists anywhere in
the tree. A `response_model` cannot give you that assertion — it constrains the
model the router names, not the model six months of edits later made it inherit
from — and the omissions it guards (price when hidden, raw variant quantities,
stock/archive/capacity signals) are the spec's security requirements, not
formatting preferences.
"""

import datetime
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.rate_limit import FixedWindowRateLimiter
from app.boutique.service import AvailabilityResult, SettingsResult
from app.catalog.schemas import DressResponse
from app.catalog.service import (
    MAX_LIST_OFFSET,
    CatalogNotFoundError,
    DressListResult,
    DressView,
    MediaView,
    StockSummary,
)
from app.catalog.validation import DRESS_LIST_DEFAULT_LIMIT
from app.core.config import Settings
from app.main import create_app
from app.models.availability import AvailabilityException, AvailabilityRule
from app.models.dress import Dress
from app.models.dress_media import DressMedia
from app.models.dress_variant import DressVariant
from app.storefront.router import (
    public_boutique,
    public_dress,
    public_dress_detail,
    public_price,
    upcoming_exceptions,
)
from app.storefront.schemas import (
    PublicBoutiqueResponse,
    PublicDressDetailResponse,
    PublicDressResponse,
)
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="בלה כלות", settings={})

DRESS_ID = uuid.uuid4()
VARIANT_ID = uuid.uuid4()
MEDIA_ID = uuid.uuid4()

JPEG = "image/jpeg"
STORAGE_KEY = f"tenants/{TENANT.id}/dresses/{DRESS_ID}/media/{MEDIA_ID}.jpg"
SIGNED_URL = f"https://media.test/{STORAGE_KEY}?X-Amz-Signature=abc"

CREATED_AT = datetime.datetime(2026, 7, 24, 10, 0, tzinfo=datetime.UTC)
URL_EXPIRES_AT = datetime.datetime(2026, 7, 24, 10, 15, tzinfo=datetime.UTC)

# The fixture dress hides a real price on purpose: the hidden-price path is the
# one every response below travels, so the omission is exercised by every test
# in the file rather than by one dedicated case.
HIDDEN_PRICE_AGOROT = 590_000

LIST_PATH = "/storefront/dresses"
DETAIL_PATH = f"/storefront/dresses/{DRESS_ID}"
BOUTIQUE_PATH = "/storefront/boutique"


async def _null_resolver(slug: str) -> TenantContext | None:
    """No host resolves. Enough to build the app and read its route table."""
    return None


def _registered_routes(node: Any) -> Iterator[tuple[str, str]]:
    """(method, path) for every leaf route. FastAPI wraps an included router in a
    `_IncludedRouter` rather than flattening it, so this has to recurse through
    `original_router` — reading `app.routes` alone silently sees four docs routes
    and nothing else, which would make the guards below pass vacuously."""
    for route in getattr(node, "routes", []):
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _registered_routes(inner)
            continue
        path = getattr(route, "path", None)
        if path is None:
            continue
        for method in getattr(route, "methods", None) or ():
            yield method, path


# Anonymous GETs, DERIVED from the live route table rather than hand-written. The
# inverse of F8's ROUTES table: there is no body column because nothing here
# mutates, and no auth column because the whole point is that there is no auth.
#
# Derivation is the load-bearing part. With a literal here, adding
# /storefront/dresses/{dress_id}/media failed exactly one test — the expected-set
# check below — and the natural fix was to extend that literal, after which the
# no-session, tenant-required, no-store and forbidden-key guards still never saw
# the new route. Now they all do. Adding a public route stays a DELIBERATE act
# because test_no_route_is_registered_twice_across_routers still pins the
# expected set explicitly; what is no longer possible is forgetting quietly.
PUBLIC_ROUTES = sorted(
    {
        path.replace("{dress_id}", str(DRESS_ID))
        for method, path in _registered_routes(create_app(resolver=_null_resolver))
        if method == "GET" and path.startswith("/storefront")
    }
)
# An empty parametrize list is collected silently, which is the exact vacuum the
# derivation exists to close.
assert PUBLIC_ROUTES, "no /storefront route was discovered — the guards below would be vacuous"

# Manage-only keys, per the spec's two "Note for F10" blocks. Asserted at EVERY
# depth of the parsed JSON, so a nested schema cannot smuggle one back.
FORBIDDEN_KEYS = frozenset(
    {
        "price_visible",
        "quantity",
        "out_of_stock",
        "total_quantity",
        "variant_count",
        "archived",
        "media_count",
        "sort_order",
        "media_uploads_enabled",
        "media_slots_remaining",
        "capacity",
        "deposits_enabled",
        "brides_only",
        "toggles",
        "storage_key",
        "status",
        "created_at",
        "updated_at",
        "deleted_at",
        "content_type",
        "byte_size",
        "tenant_id",
    }
)

PROFILE = {
    "phone": "052-1234567",
    "address": "רח׳ דיזנגוף 99, תל אביב",
    "description": "בוטיק כלות",
    "maps_url": "https://maps.example/bella",
}
TOGGLES = {"deposits_enabled": True, "brides_only": False}


def _dress_row(
    *, price_visible: bool = False, price_agorot: int | None = HIDDEN_PRICE_AGOROT
) -> Dress:
    return Dress(
        id=DRESS_ID,
        tenant_id=TENANT.id,
        name="Aurora",
        description="Silk A-line",
        price_agorot=price_agorot,
        price_visible=price_visible,
        reserved=True,
        sort_order=3,
        created_at=CREATED_AT,
        updated_at=None,
        deleted_at=None,
    )


def _variant_row(size_label: str, quantity: int) -> DressVariant:
    return DressVariant(
        id=VARIANT_ID,
        tenant_id=TENANT.id,
        dress_id=DRESS_ID,
        size_label=size_label,
        quantity=quantity,
        sort_order=0,
        created_at=CREATED_AT,
    )


def _media_view(*, url: str | None = SIGNED_URL) -> MediaView:
    row = DressMedia(
        id=MEDIA_ID,
        tenant_id=TENANT.id,
        dress_id=DRESS_ID,
        storage_key=STORAGE_KEY,
        content_type=JPEG,
        byte_size=4096,
        status="ready",
        sort_order=0,
        created_at=CREATED_AT,
    )
    return MediaView(row=row, url=url, url_expires_at=URL_EXPIRES_AT if url else None)


def _dress_view(
    *,
    url: str | None = SIGNED_URL,
    price_visible: bool = False,
    price_agorot: int | None = HIDDEN_PRICE_AGOROT,
    detail: bool = True,
) -> DressView:
    media = [_media_view(url=url)]
    return DressView(
        row=_dress_row(price_visible=price_visible, price_agorot=price_agorot),
        summary=StockSummary(variant_count=2, total_quantity=3, out_of_stock=False),
        media_count=1,
        cover=media[0],
        uploads_enabled=True,
        slots_remaining=11,
        # 38 is sold out and 40 is in stock: the public shape must distinguish
        # them with a boolean and never with the count.
        variants=[_variant_row("38", 0), _variant_row("40", 3)] if detail else [],
        media=media if detail else [],
    )


def _rule(day_of_week: int) -> AvailabilityRule:
    return AvailabilityRule(
        id=uuid.uuid4(),
        tenant_id=TENANT.id,
        day_of_week=day_of_week,
        open_time=datetime.time(10, 0),
        close_time=datetime.time(19, 0),
        capacity=4,
        created_at=CREATED_AT,
    )


def _exception(date: datetime.date, *, note: str | None = "סגור") -> AvailabilityException:
    return AvailabilityException(
        id=uuid.uuid4(),
        tenant_id=TENANT.id,
        date=date,
        open_time=None,
        close_time=None,
        note=note,
        created_at=CREATED_AT,
    )


class FakeCatalogService:
    """Duck-typed CatalogService covering only the two read methods the
    storefront calls, so a signature drift on either one fails here."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.raise_on: dict[str, Exception] = {}
        self.view = _dress_view()

    def _record(self, method: str, /, **kwargs: Any) -> None:
        self.calls.append((method, kwargs))
        exc = self.raise_on.get(method)
        if exc is not None:
            raise exc

    def call(self, method: str) -> dict[str, Any]:
        matches = [kwargs for called, kwargs in self.calls if called == method]
        assert len(matches) == 1, f"expected exactly one {method} call, saw {self.calls}"
        return matches[0]

    async def list_dresses(
        self,
        tenant_id: uuid.UUID,
        *,
        archived: bool = False,
        search: str | None = None,
        offset: int = 0,
        limit: int = DRESS_LIST_DEFAULT_LIMIT,
    ) -> DressListResult:
        self._record(
            "list_dresses",
            tenant_id=tenant_id,
            archived=archived,
            search=search,
            offset=offset,
            limit=limit,
        )
        return DressListResult(
            items=[_dress_view(detail=False)], total=1, offset=offset, limit=limit
        )

    async def get_dress(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID, *, include_archived: bool = True
    ) -> DressView:
        self._record(
            "get_dress", tenant_id=tenant_id, dress_id=dress_id, include_archived=include_archived
        )
        return self.view


class FakeBoutiqueService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, uuid.UUID]] = []
        self.settings = SettingsResult(profile=dict(PROFILE), toggles=dict(TOGGLES))
        self.availability = AvailabilityResult(rules=[_rule(0)], exceptions=[])

    async def get_settings(self, tenant_id: uuid.UUID) -> SettingsResult:
        self.calls.append(("get_settings", tenant_id))
        return self.settings

    async def get_availability(self, tenant_id: uuid.UUID) -> AvailabilityResult:
        self.calls.append(("get_availability", tenant_id))
        return self.availability


def _client(
    catalog: FakeCatalogService | None = None,
    boutique: FakeBoutiqueService | None = None,
    *,
    host: str = "bella.localtest.me",
    limiter: FixedWindowRateLimiter | None = None,
) -> TestClient:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    app.state.catalog_service = catalog if catalog is not None else FakeCatalogService()
    app.state.boutique_service = boutique if boutique is not None else FakeBoutiqueService()
    if limiter is not None:
        app.state.storefront_rate_limiter = limiter
    return TestClient(app, base_url=f"http://{host}")


# --- the public contract: no session, no cookie jar, no CSRF ---


@pytest.mark.parametrize("path", PUBLIC_ROUTES)
def test_every_public_route_answers_without_a_session(path: str) -> None:
    """The inverse of F8's test_every_route_requires_authentication. No cookie is
    ever set on this client, so a manage dependency copied in by accident shows
    up as a 401 here rather than as a dead storefront in production.

    Reading the request jar is only half of the backwards reading. A session- or
    CSRF-issuing dependency copy-pasted from the manage router does not 401 — it
    answers 200 and hands every anonymous visitor an identity, on a `no-store`
    response, in a header an empty jar cannot see. So assert the response too."""
    with _client() as client:
        assert client.cookies == {}
        resp = client.get(path)
    assert resp.status_code == 200, f"{path} → {resp.status_code} {resp.text}"
    assert "set-cookie" not in resp.headers, f"{path} issued {resp.headers.get('set-cookie')}"


@pytest.mark.parametrize("path", PUBLIC_ROUTES)
def test_every_public_route_still_requires_a_resolved_tenant(path: str) -> None:
    """Public is not the same as host-agnostic: /storefront must never join
    EXEMPT_PATHS, or an unresolvable host would reach a tenant-scoped handler."""
    with _client(host="nosuch.localtest.me") as client:
        resp = client.get(path)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"


@pytest.mark.parametrize("path", PUBLIC_ROUTES)
def test_every_public_route_is_never_cached(path: str) -> None:
    """Image URLs are presigned GETs valid for SIGNED_GET_TTL_SECONDS — bearer
    material that must not reach a shared cache or a bfcache entry. Set on the
    router, so a route added later cannot forget it."""
    with _client() as client:
        resp = client.get(path)
    assert resp.headers["cache-control"] == "no-store"


def test_no_route_is_registered_twice_across_routers() -> None:
    """F8's shadowing guard applied across routers: /manage and /storefront are
    mounted on one app, and a duplicated (method, path) would silently win or
    lose depending on include order.

    The expected set stays an explicit literal even though PUBLIC_ROUTES is now
    derived from this same table: adding a public surface must fail one test on
    purpose. What changed is that fixing it here also arms the four guards."""
    registered = list(_registered_routes(create_app(resolver=_null_resolver)))
    assert len(registered) == len(set(registered)), "a (method, path) pair is registered twice"
    assert {path for _, path in registered if path.startswith("/storefront")} == {
        "/storefront/dresses",
        "/storefront/dresses/{dress_id}",
        "/storefront/boutique",
    }
    # And no storefront path is reachable under the CSRF-protected prefix.
    assert not any(path.startswith("/manage/storefront") for _, path in registered)


# --- the wire-absence walk ---


def _all_keys(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _all_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _all_keys(item)


@pytest.mark.parametrize("path", PUBLIC_ROUTES)
def test_no_forbidden_key_appears_at_any_depth(path: str) -> None:
    """The single most important assertion in this feature. A response_model
    constrains the model the router names; it says nothing about what a future
    edit makes that model inherit. This walks the actual parsed JSON."""
    boutique = FakeBoutiqueService()
    boutique.availability = AvailabilityResult(
        rules=[_rule(0), _rule(5)],
        exceptions=[_exception(datetime.date.today() + datetime.timedelta(days=7))],
    )
    with _client(boutique=boutique) as client:
        resp = client.get(path)
    assert resp.status_code == 200
    leaked = FORBIDDEN_KEYS & set(_all_keys(resp.json()))
    assert leaked == set(), f"{path} leaked {sorted(leaked)}"


# --- dresses ---


def test_list_pins_the_page_size_and_exposes_only_offset() -> None:
    """No `limit` and no `search`: an anonymous caller can never make one request
    mint more than DRESS_LIST_DEFAULT_LIMIT signed URLs."""
    catalog = FakeCatalogService()
    with _client(catalog) as client:
        resp = client.get(LIST_PATH, params={"offset": 24, "limit": 100, "search": "aurora"})
    assert resp.status_code == 200
    call = catalog.call("list_dresses")
    assert call["offset"] == 24
    assert call["limit"] == DRESS_LIST_DEFAULT_LIMIT
    assert call["search"] is None
    assert call["archived"] is False
    # The envelope still carries limit so the client can page.
    body = resp.json()
    assert body["limit"] == DRESS_LIST_DEFAULT_LIMIT
    assert body["total"] == 1
    assert set(body) == {"items", "total", "offset", "limit"}


def test_list_rejects_a_negative_offset() -> None:
    catalog = FakeCatalogService()
    with _client(catalog) as client:
        resp = client.get(LIST_PATH, params={"offset": -1})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert catalog.calls == []


def test_list_rejects_an_offset_past_the_ceiling() -> None:
    """`ge=0` alone is not a bound. Python ints are unbounded, and this value is
    bound into `OFFSET $n::BIGINT` — so `?offset=2**63` was a 200 from the router
    and then an unhandled 500 out of asyncpg's int8 encoder, on an anonymous,
    trivially-scriptable endpoint. The int8 assertion is what stops a later
    "let's allow deeper paging" from walking the ceiling back past the encoder."""
    assert MAX_LIST_OFFSET < 2**63
    catalog = FakeCatalogService()
    with _client(catalog) as client:
        at_bound = client.get(LIST_PATH, params={"offset": MAX_LIST_OFFSET})
        beyond = client.get(LIST_PATH, params={"offset": MAX_LIST_OFFSET + 1})
        overflow = client.get(LIST_PATH, params={"offset": 2**63})
    assert at_bound.status_code == 200
    assert beyond.status_code == 400
    assert beyond.json()["error"]["code"] == "VALIDATION_ERROR"
    assert overflow.status_code == 400
    # Exactly one recorded call proves neither rejected offset reached the query.
    assert catalog.call("list_dresses")["offset"] == MAX_LIST_OFFSET


def test_list_row_omits_a_hidden_price_and_the_description() -> None:
    with _client() as client:
        resp = client.get(LIST_PATH)
    assert resp.json()["items"] == [
        {
            "id": str(DRESS_ID),
            "name": "Aurora",
            "price_agorot": None,
            "reserved": True,
            "cover": {"url": SIGNED_URL, "url_expires_at": "2026-07-24T10:15:00Z"},
        }
    ]


def test_a_visible_price_still_ships() -> None:
    catalog = FakeCatalogService()
    catalog.view = _dress_view(price_visible=True, price_agorot=120_000)
    with _client(catalog) as client:
        resp = client.get(DETAIL_PATH)
    assert resp.json()["price_agorot"] == 120_000


def test_detail_reports_availability_never_stock() -> None:
    with _client() as client:
        resp = client.get(DETAIL_PATH)
    body = resp.json()
    assert body["variants"] == [
        {"size_label": "38", "available": False},
        {"size_label": "40", "available": True},
    ]
    assert set(body) == {
        "id",
        "name",
        "description",
        "price_agorot",
        "reserved",
        "variants",
        "media",
    }


def test_detail_asks_the_service_to_exclude_archived_dresses() -> None:
    catalog = FakeCatalogService()
    with _client(catalog) as client:
        client.get(DETAIL_PATH)
    assert catalog.call("get_dress") == {
        "tenant_id": TENANT.id,
        "dress_id": DRESS_ID,
        "include_archived": False,
    }


def test_an_archived_dress_is_a_404() -> None:
    catalog = FakeCatalogService()
    catalog.raise_on["get_dress"] = CatalogNotFoundError()
    with _client(catalog) as client:
        resp = client.get(DETAIL_PATH)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_reads_never_503_when_storage_is_unconfigured() -> None:
    """A read must never fail because there is no bucket — the page renders
    without photos. `_media_view` already serialises a null url; this asserts the
    route does not turn that into an error."""
    catalog = FakeCatalogService()
    catalog.view = _dress_view(url=None)
    with _client(catalog) as client:
        detail = client.get(DETAIL_PATH)
    assert detail.status_code == 200
    assert detail.json()["media"] == [{"url": None, "url_expires_at": None}]


# --- boutique profile + hours ---


def test_boutique_returns_the_display_name_profile_and_hours() -> None:
    boutique = FakeBoutiqueService()
    with _client(boutique=boutique) as client:
        resp = client.get(BOUTIQUE_PATH)
    body = resp.json()
    assert body["name"] == TENANT.name
    assert body["profile"] == PROFILE
    assert body["rules"] == [{"day_of_week": 0, "open_time": "10:00:00", "close_time": "19:00:00"}]
    assert [call[0] for call in boutique.calls] == ["get_settings", "get_availability"]


def test_boutique_drops_past_exceptions() -> None:
    today = datetime.date.today()
    boutique = FakeBoutiqueService()
    boutique.availability = AvailabilityResult(
        rules=[],
        exceptions=[
            _exception(today - datetime.timedelta(days=30)),
            _exception(today + datetime.timedelta(days=30), note="שעות מיוחדות"),
        ],
    )
    with _client(boutique=boutique) as client:
        resp = client.get(BOUTIQUE_PATH)
    assert resp.json()["exceptions"] == [
        {
            "date": (today + datetime.timedelta(days=30)).isoformat(),
            "open_time": None,
            "close_time": None,
            "note": "שעות מיוחדות",
        }
    ]


def test_boutique_survives_an_empty_profile() -> None:
    boutique = FakeBoutiqueService()
    boutique.settings = SettingsResult(profile={}, toggles={})
    with _client(boutique=boutique) as client:
        resp = client.get(BOUTIQUE_PATH)
    assert resp.status_code == 200
    assert resp.json()["profile"] == {
        "phone": None,
        "address": None,
        "description": None,
        "maps_url": None,
    }


# --- structural: the public schemas may never inherit from the manage ones ---


def test_public_schemas_share_no_inheritance_with_the_manage_schemas() -> None:
    """Inheritance is exactly how the mandated omissions get silently reverted:
    one field added to DressResponse and every storefront row carries it."""
    assert not issubclass(PublicDressResponse, DressResponse)
    assert not issubclass(PublicDressDetailResponse, PublicDressResponse)
    assert not issubclass(PublicDressDetailResponse, DressResponse)


def test_public_dress_row_has_exactly_these_fields() -> None:
    """The assertion that fails CI when someone adds a field "just for
    debugging"."""
    assert set(PublicDressResponse.model_fields) == {
        "id",
        "name",
        "price_agorot",
        "reserved",
        "cover",
    }


def test_public_boutique_has_exactly_these_fields() -> None:
    """The two dress schemas are pinned by set-equality; the boutique top level
    was only spot-checked, so a new top-level field whose name is not in
    FORBIDDEN_KEYS would ship with nothing red. The nested shapes are already
    pinned by the exact-dict equality in the route tests above."""
    assert set(PublicBoutiqueResponse.model_fields) == {
        "name",
        "profile",
        "rules",
        "exceptions",
    }


def test_public_dress_detail_has_exactly_these_fields() -> None:
    assert set(PublicDressDetailResponse.model_fields) == {
        "id",
        "name",
        "description",
        "price_agorot",
        "reserved",
        "variants",
        "media",
    }


# --- pure functions (no I/O, no clock) ---


@pytest.mark.parametrize(
    ("price_visible", "price_agorot", "expected"),
    [
        (True, HIDDEN_PRICE_AGOROT, HIDDEN_PRICE_AGOROT),
        (True, None, None),
        (False, HIDDEN_PRICE_AGOROT, None),
        (False, None, None),
    ],
)
def test_public_price_covers_every_combination(
    price_visible: bool, price_agorot: int | None, expected: int | None
) -> None:
    """`price_agorot is None` covers both "hidden" and "no price recorded", which
    the spec renders identically — so the flag never ships and the two can never
    disagree."""
    row = _dress_row(price_visible=price_visible, price_agorot=price_agorot)
    assert public_price(row) == expected


def test_upcoming_exceptions_keeps_today_and_the_future_in_order() -> None:
    today = datetime.date(2026, 7, 27)
    rows = [
        _exception(today - datetime.timedelta(days=1)),
        _exception(today),
        _exception(today + datetime.timedelta(days=60)),
        _exception(today + datetime.timedelta(days=2)),
    ]
    kept = upcoming_exceptions(rows, today)
    # A past exception is history for the owner and noise for the customer; the
    # repository is left alone because the manage console needs the full list.
    assert [row.date for row in kept] == [
        today,
        today + datetime.timedelta(days=60),
        today + datetime.timedelta(days=2),
    ]


def test_mappers_are_importable_pure_functions() -> None:
    view = _dress_view()
    assert public_dress(view).price_agorot is None
    assert [variant.available for variant in public_dress_detail(view).variants] == [False, True]
    assert (
        public_boutique(
            name="בלה",
            settings=SettingsResult(profile=dict(PROFILE), toggles=dict(TOGGLES)),
            availability=AvailabilityResult(rules=[], exceptions=[]),
            today=datetime.date(2026, 7, 27),
        ).name
        == "בלה"
    )


# --- the per-IP read budget ---


def test_the_limiter_is_skipped_when_there_is_no_trusted_client_ip() -> None:
    """With TRUST_FORWARDED_FOR off, request.client.host is the proxy: a bucket
    keyed on it is a per-tenant bucket, and one anonymous visitor could 429 a
    boutique's whole storefront. A limiter that blocks everything proves the
    check never runs."""
    blocks_everything = FixedWindowRateLimiter(
        max_attempts=0, window_seconds=60, clock=time.monotonic
    )
    with _client(limiter=blocks_everything) as client:
        for path in PUBLIC_ROUTES:
            assert client.get(path).status_code == 200


def test_a_trusted_client_ip_is_throttled_with_the_existing_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.storefront.router.get_settings",
        lambda: Settings(app_env="dev", trust_forwarded_for=True),
    )
    limiter = FixedWindowRateLimiter(max_attempts=2, window_seconds=60, clock=time.monotonic)
    headers = {"x-forwarded-for": "203.0.113.9"}
    with _client(limiter=limiter) as client:
        assert client.get(LIST_PATH, headers=headers).status_code == 200
        assert client.get(BOUTIQUE_PATH, headers=headers).status_code == 200
        blocked = client.get(LIST_PATH, headers=headers)
        # A different visitor of the same boutique is unaffected.
        other = client.get(LIST_PATH, headers={"x-forwarded-for": "198.51.100.4"})
    assert blocked.status_code == 429
    # Zero new error codes: the existing TOO_MANY_ATTEMPTS handler serves this.
    assert blocked.json() == {
        "error": {"code": "TOO_MANY_ATTEMPTS", "message": "Too many attempts. Try again later."}
    }
    assert other.status_code == 200
