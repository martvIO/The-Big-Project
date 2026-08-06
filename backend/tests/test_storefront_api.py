"""Feature 10 fast API tests for the public storefront read surface: a fake
StorefrontService + a hardcoded TenantContext, no database (test_catalog_api.py
style).

Three things here are load-bearing and everything else is scaffolding.

**The inverse of F8's auth guard.** `test_no_route_requires_authentication` is
`test_every_route_requires_authentication` read backwards: these three routes
must answer 200 with no cookie jar at all. A dependency copy-pasted from the
manage router would break the whole storefront, and nothing else would notice.

**The wire-absence walk.** `test_no_manage_only_field_leaks` parses every
response and recursively asserts that no manage-only key exists anywhere in the
tree. A `response_model` cannot give you that assertion — it constrains the
model the router names, not the model six months of edits later made it inherit
from — and the omissions it guards (price when hidden, raw variant quantities,
stock/archive/capacity signals) are the spec's security requirements, not
formatting preferences.

**The middleware ordering.** SecurityHeadersMiddleware is registered LAST in
create_app(), which makes it OUTERMOST, which is the only reason the three
headers land on the TENANT_NOT_FOUND 404 that TenantResolutionMiddleware
returns from its own dispatch without ever calling a handler. On a public
storefront that 404 is the single most-served response to anyone probing the
domain, so it is asserted explicitly alongside the ordinary 200 and 401 cases.
"""

import ast
import dataclasses
import datetime
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Literal, cast

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.booking.slots import Slot
from app.boutique.schemas import TermsVersionResponse
from app.catalog.schemas import DressResponse
from app.catalog.service import CatalogNotFoundError, MediaView
from app.core.config import Settings
from app.main import create_app
from app.models.appointment_type import AppointmentType
from app.models.availability import AvailabilityException, AvailabilityRule
from app.models.dress import Dress
from app.models.dress_media import DressMedia
from app.models.terms_version import TermsVersion
from app.privacy.text import (
    PLATFORM_DPA_HE,
    PLATFORM_NOTICE_HE,
    PLATFORM_SUBPROCESSORS_HE,
    resolve_privacy,
)
from app.security_headers import SECURITY_HEADERS
from app.storage.unconfigured import UnconfiguredMediaStorage
from app.storefront.router import (
    _public_price,
    public_boutique,
    public_dress,
    public_dress_detail,
    public_terms,
)
from app.storefront.schemas import (
    BoutiqueResponse,
    StorefrontDetail,
    StorefrontDress,
    StorefrontTerms,
)
from app.storefront.service import (
    MAX_LIST_OFFSET,
    StorefrontBoutiqueView,
    StorefrontDressDetailView,
    StorefrontDressListView,
    StorefrontDressView,
    StorefrontService,
    StorefrontSizeView,
    upcoming_exceptions,
)
from app.storefront.validation import (
    STOREFRONT_LIST_DEFAULT_LIMIT,
    STOREFRONT_LIST_MAX_LIMIT,
    UPCOMING_EXCEPTIONS_LIMIT,
    SlotWindowError,
)
from app.tenancy.middleware import EXEMPT_PATHS, TenantContext

DRESS_ID = uuid.uuid4()
MEDIA_ID = uuid.uuid4()
APPOINTMENT_TYPE_ID = uuid.uuid4()

JPEG = "image/jpeg"

PROFILE: dict[str, Any] = {
    "essence": "שמלות כלה בעבודת יד",
    "description": "בוטיק כלות",
    "phone": "052-1234567",
    "address": "רח׳ דיזנגוף 99, תל אביב",
    "maps_url": "https://maps.example/bella",
    "instagram": "bella.bridal",
    # NOT one of the six keys public_boutique reads. The projection reads the
    # JSONB blob by explicit key, so a field a later feature adds to `profile`
    # must not reach the public page by default — `secret_note` is in
    # FORBIDDEN_KEYS below and this row is what arms that assertion.
    "secret_note": "owner-only",
}
TOGGLES = {"deposits_enabled": True, "brides_only": False}

TENANT = TenantContext(
    id=uuid.uuid4(),
    slug="bella",
    name="בלה כלות",
    settings={"profile": dict(PROFILE), "toggles": dict(TOGGLES)},
)

STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"

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
TERMS_PATH = "/storefront/terms"

TERMS_TEXT = "ביטול עד 48 שעות מראש — החזר מלא."

# An authenticated /manage route, used only to prove the security headers are
# app-wide rather than storefront-only. Unauthenticated on purpose — a 401 is a
# response the handler never produced, so it also covers the exception path.
MANAGE_PATH = "/manage/dresses"

STOREFRONT_SOURCE_DIR = Path(__file__).resolve().parents[1] / "app" / "storefront"


async def _null_resolver(slug: str) -> TenantContext | None:
    """No host resolves. Enough to build the app and read its route table."""
    return None


def _registered_routes(node: Any) -> Iterator[tuple[str, str]]:
    """(method, path) for every leaf route. FastAPI wraps an included router in a
    `_IncludedRouter` rather than flattening it, so this has to recurse through
    `original_router` — reading `app.routes` alone silently sees the docs routes
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


def _iter_leaf_routes(node: Any) -> Iterator[Any]:
    for route in getattr(node, "routes", []):
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _iter_leaf_routes(inner)
            continue
        yield route


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
ROUTES = sorted(
    {
        path.replace("{dress_id}", str(DRESS_ID))
        for method, path in _registered_routes(create_app(resolver=_null_resolver))
        if method == "GET" and path.startswith("/storefront")
    }
)
# An empty parametrize list is collected silently, which is the exact vacuum the
# derivation exists to close.
assert ROUTES, "no /storefront route was discovered — the guards below would be vacuous"

# Manage-only keys, per the spec's two "Note for F10" blocks. Asserted at EVERY
# depth of the parsed JSON, so a nested schema cannot smuggle one back.
#
# `id` is deliberately absent: it is a legitimate top-level key on both dress
# shapes. Media-level id absence is asserted separately, by
# test_media_carries_no_identifier_or_object_metadata.
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
        "profile",
        "secret_note",
        "storage_key",
        "status",
        "created_at",
        "updated_at",
        "deleted_at",
        "content_type",
        "byte_size",
        "tenant_id",
        "variants",
        "created_by",
    }
)

# The spec's error table for this surface, verbatim. Four codes, no new ones:
# test_every_spec_error_code_is_asserted checks this set against what the module
# actually exercises, so adding a row to the spec without a test here fails CI.
SPEC_ERROR_CODES = {"TENANT_NOT_FOUND", "NOT_FOUND", "VALIDATION_ERROR", "TOO_MANY_ATTEMPTS"}


def _dress_row(
    *,
    price_visible: bool = False,
    price_agorot: int | None = HIDDEN_PRICE_AGOROT,
    description: str | None = "Silk A-line",
) -> Dress:
    return Dress(
        id=DRESS_ID,
        tenant_id=TENANT.id,
        name="Aurora",
        description=description,
        price_agorot=price_agorot,
        price_visible=price_visible,
        reserved=True,
        sort_order=3,
        created_at=CREATED_AT,
        updated_at=None,
        deleted_at=None,
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
) -> StorefrontDressView:
    return StorefrontDressView(
        row=_dress_row(price_visible=price_visible, price_agorot=price_agorot),
        cover=_media_view(url=url),
    )


def _detail_view(
    *,
    url: str | None = SIGNED_URL,
    price_visible: bool = False,
    price_agorot: int | None = HIDDEN_PRICE_AGOROT,
    description: str | None = "Silk A-line",
) -> StorefrontDressDetailView:
    return StorefrontDressDetailView(
        row=_dress_row(
            price_visible=price_visible, price_agorot=price_agorot, description=description
        ),
        # 38 is sold out and 40 is in stock: the public shape must distinguish
        # them with a boolean and never with the count.
        sizes=[
            StorefrontSizeView(size_label="38", available=False),
            StorefrontSizeView(size_label="40", available=True),
        ],
        media=[_media_view(url=url)],
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


def _slot(hour: int, minute: int, *, remaining: int) -> Slot:
    """capacity is derived from remaining so the fixture cannot accidentally
    assert a capacity that the wire is supposed to never carry."""
    return Slot(
        starts_at=datetime.datetime(2026, 8, 3, hour, minute, tzinfo=datetime.UTC),
        capacity=remaining,
        booked=0,
    )


def _appointment_type() -> AppointmentType:
    return AppointmentType(
        id=APPOINTMENT_TYPE_ID,
        tenant_id=TENANT.id,
        name="מדידת כלה",
        duration_minutes=60,
        audience="brides_only",
        deposit_required=True,
        deposit_amount_agorot=15_000,
        sort_order=0,
        created_at=CREATED_AT,
    )


def _terms_row(
    *,
    tenant_id: uuid.UUID | None = None,
    version: int = 3,
    terms_text: str = TERMS_TEXT,
) -> TermsVersion:
    return TermsVersion(
        id=uuid.uuid4(),
        tenant_id=tenant_id if tenant_id is not None else TENANT.id,
        version=version,
        terms_text=terms_text,
        refundable_until_hours_before=48,
        forfeit_percent=30,
        created_by=STAFF_ID,
        created_at=CREATED_AT,
        updated_at=None,
        deleted_at=None,
    )


def _boutique_view(
    *,
    profile: dict[str, Any] | None = None,
    hours: list[AvailabilityRule] | None = None,
    exceptions: list[AvailabilityException] | None = None,
    settings: dict[str, Any] | None = None,
) -> StorefrontBoutiqueView:
    return StorefrontBoutiqueView(
        name=TENANT.name,
        profile=dict(PROFILE) if profile is None else profile,
        hours=[_rule(0)] if hours is None else hours,
        exceptions=(
            [_exception(datetime.date.today() + datetime.timedelta(days=7))]
            if exceptions is None
            else exceptions
        ),
        # Resolved the way the real service resolves it, so a fake cannot
        # accidentally assert a shape the product never produces (F20 D13).
        privacy=resolve_privacy(settings or {}),
    )


class FakeStorefrontService:
    """Duck-typed StorefrontService covering exactly the six read methods the
    router calls, so a signature drift on any one of them fails here."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.raise_on: dict[str, Exception] = {}
        self.list_view = StorefrontDressListView(
            items=[_dress_view()], total=1, offset=0, limit=STOREFRONT_LIST_DEFAULT_LIMIT
        )
        self.detail_view = _detail_view()
        self.boutique_view = _boutique_view()
        self.slots = [_slot(10, 0, remaining=2), _slot(10, 30, remaining=1)]
        self.appointment_types = [_appointment_type()]
        # Keyed by tenant so the cross-tenant test can prove host A's terms are
        # unreachable under host B; a missing key raises like the real service.
        self.terms_rows: dict[uuid.UUID, TermsVersion] = {TENANT.id: _terms_row()}

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
        offset: int = 0,
        limit: int = STOREFRONT_LIST_DEFAULT_LIMIT,
    ) -> StorefrontDressListView:
        self._record("list_dresses", tenant_id=tenant_id, offset=offset, limit=limit)
        return dataclasses.replace(self.list_view, offset=offset, limit=limit)

    async def get_dress(
        self, tenant_id: uuid.UUID, dress_id: uuid.UUID
    ) -> StorefrontDressDetailView:
        self._record("get_dress", tenant_id=tenant_id, dress_id=dress_id)
        return self.detail_view

    async def get_boutique(
        self, tenant_id: uuid.UUID, *, name: str, settings: dict[str, Any]
    ) -> StorefrontBoutiqueView:
        self._record("get_boutique", tenant_id=tenant_id, name=name, settings=settings)
        return self.boutique_view

    async def list_slots(
        self,
        tenant_id: uuid.UUID,
        *,
        from_date: datetime.date | None = None,
        to_date: datetime.date | None = None,
    ) -> list[Slot]:
        self._record("list_slots", tenant_id=tenant_id, from_date=from_date, to_date=to_date)
        return self.slots

    async def list_appointment_types(self, tenant_id: uuid.UUID) -> list[AppointmentType]:
        self._record("list_appointment_types", tenant_id=tenant_id)
        return self.appointment_types

    async def get_terms(self, tenant_id: uuid.UUID) -> TermsVersion:
        self._record("get_terms", tenant_id=tenant_id)
        row = self.terms_rows.get(tenant_id)
        if row is None:
            raise CatalogNotFoundError
        return row


class FakeAuthService:
    """Only here so the owner cookie set in test_owner_cookie_changes_nothing is a
    genuinely resolvable session rather than a random string — the point of
    test_owner_cookie_changes_nothing is that a REAL owner sees no difference."""

    def __init__(self) -> None:
        self.staff = StaffContext(
            id=STAFF_ID,
            tenant_id=TENANT.id,
            email="owner@bella.example",
            display_name="Owner",
            role="owner",
        )

    async def login(
        self, tenant_id: uuid.UUID, email: str, password: str
    ) -> tuple[StaffContext, str]:
        return self.staff, TOKEN

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        return self.staff if token == TOKEN else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        return None


def _client(
    service: FakeStorefrontService | None = None,
    *,
    host: str = "bella.localtest.me",
    limiter: FixedWindowRateLimiter | None = None,
    tenants: dict[str, TenantContext] | None = None,
) -> TestClient:
    resolvable = {"bella": TENANT} if tenants is None else tenants

    async def _resolver(slug: str) -> TenantContext | None:
        return resolvable.get(slug)

    app = create_app(resolver=_resolver)
    app.state.storefront_service = service if service is not None else FakeStorefrontService()
    auth = FakeAuthService()
    app.state.auth_service = auth
    app.dependency_overrides[get_auth_service] = lambda: auth
    if limiter is not None:
        app.state.storefront_rate_limiter = limiter
    return TestClient(app, base_url=f"http://{host}")


# --- the public contract: no session, no cookie jar, no CSRF ---


@pytest.mark.parametrize("path", ROUTES)
def test_no_route_requires_authentication(path: str) -> None:
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


def test_exempt_paths_contains_no_storefront_path() -> None:
    """EXEMPT_PATHS skips tenant resolution entirely. The behavioural test below
    proves today's routes 404 on an unknown host; this pins the mechanism, so a
    future `/storefront/...` entry fails here even before a route exists to
    exercise it."""
    assert not [path for path in EXEMPT_PATHS if path.startswith("/storefront")]


@pytest.mark.parametrize("path", ROUTES)
def test_storefront_paths_are_not_exempt(path: str) -> None:
    """Public is not the same as host-agnostic: an unresolvable host must 404
    before a tenant-scoped handler ever runs."""
    with _client(host="nosuch.localtest.me") as client:
        resp = client.get(path)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"


@pytest.mark.parametrize("path", ROUTES)
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

    The expected set stays an explicit literal even though ROUTES is now derived
    from this same table: adding a public surface must fail one test on purpose.
    What changed is that fixing it here also arms the four guards."""
    registered = list(_registered_routes(create_app(resolver=_null_resolver)))
    assert len(registered) == len(set(registered)), "a (method, path) pair is registered twice"
    assert {path for _, path in registered if path.startswith("/storefront")} == {
        "/storefront/dresses",
        "/storefront/dresses/{dress_id}",
        "/storefront/boutique",
        # F12's booking-grid reads, on this same GET-only router.
        "/storefront/slots",
        "/storefront/appointment-types",
        # F11's OTP mutations — a SIBLING router on the same prefix, because the
        # read router is contractually GET-only. Their posture (anonymous,
        # cookie-blind, no-store, POST-only) is asserted in
        # test_notifications_api.py.
        "/storefront/otp/send",
        "/storefront/otp/verify",
        # F13's booking create — the third sibling, same posture, asserted in
        # test_booking_api.py.
        "/storefront/bookings",
        # F14's cancellation-policy read, back on this GET-only read router.
        "/storefront/terms",
        # F16's tokenized manage surface, on that same third sibling. POST for
        # all three INCLUDING the read: a GET would put the manage token in the
        # query string and from there into every access log on the path (D7).
        # Posture asserted in test_booking_manage_api.py.
        "/storefront/booking/lookup",
        "/storefront/booking/confirm-attendance",
        "/storefront/booking/cancel",
        # F19's deposit surface — the FOURTH sibling on this prefix, and the
        # first one a THIRD PARTY calls. The webhook is authenticated by HMAC
        # over the raw body and by nothing else: no cookie, no session, no
        # bearer. It is a sibling rather than a route on the GET-only read
        # router for a reason that is not stylistic — that router carries a
        # per-tenant _throttle, and 429-ing a provider's retry burst turns a
        # transient outage into permanently unconfirmed bookings and money that
        # moved with no row behind it.
        "/storefront/payments/webhook",
        # POST for a read, the /booking/lookup precedent. Keyed on the provider
        # session id and NOT the manage token (D13): the deposit path suppresses
        # the confirmation SMS, so she never receives a manage link to poll with.
        "/storefront/booking/payment-status",
        # F33's walk-in check-in — the FIFTH sibling, and both routes are POSTs
        # INCLUDING the read, for the reason above: the ticket id is the
        # capability and a GET would put it in the query string. Posture asserted
        # in test_checkin_api.py. Note that the five ROUTES-parametrized guards
        # below needed no edit, because F33 registers no new GET here.
        "/storefront/checkin",
        "/storefront/checkin/position",
        # F59's public wall board — a THIRD route on that same fifth sibling, not
        # a sixth sibling. Posture asserted in test_queue_board_api.py.
        #
        # A POST, and NOT for F33's reason: this request carries no capability
        # and no body at all. It is a POST because ROUTES above is DERIVED over
        # every GET under /storefront and the five guards below parametrize over
        # it — test_the_read_throttle_is_not_inert asserts 429 on each against a
        # limiter configured to block everything, and that limiter is a
        # router-level dependency of the GET-only read router which this sibling
        # does not carry. A GET here answers 200 and reddens it, and both escapes
        # are worse: a second key on the catalog's read brake, or a weakened
        # guard over six shipped public reads.
        "/storefront/queue",
        # F22's waitlist join — the SIXTH sibling, F13's create shape minus the
        # booking. Anonymous, cookie-blind, no-store, POST-only; posture and the
        # zero-new-error-codes table asserted in test_waitlist_api.py. No new
        # GET, so the five ROUTES-parametrized guards needed no edit.
        "/storefront/waitlist",
    }
    # Singular /booking/* must never collide with the plural /bookings create.
    assert "/storefront/bookings" not in {
        path for _, path in registered if path.startswith("/storefront/booking/")
    }
    # And no storefront path is reachable under the CSRF-protected prefix.
    assert not any(path.startswith("/manage/storefront") for _, path in registered)


# --- security headers ---


def test_security_headers_are_on_a_storefront_response() -> None:
    with _client() as client:
        resp = client.get(LIST_PATH)
    assert resp.status_code == 200
    assert {header: resp.headers.get(header) for header in SECURITY_HEADERS} == SECURITY_HEADERS


def test_security_headers_are_on_a_manage_response() -> None:
    """App-wide, not storefront-only. A 401 also proves the headers survive a
    response produced by an exception handler rather than by a handler."""
    with _client() as client:
        resp = client.get(MANAGE_PATH)
    assert resp.status_code == 401
    assert {header: resp.headers.get(header) for header in SECURITY_HEADERS} == SECURITY_HEADERS


def test_security_headers_are_on_the_tenant_not_found_404() -> None:
    """The whole reason SecurityHeadersMiddleware is registered LAST (=
    outermost). TenantResolutionMiddleware returns this 404 from its own
    dispatch without ever calling call_next, so any middleware added after it —
    i.e. registered EARLIER — never sees the response. On a public storefront
    this is the most-served response to anyone probing the domain."""
    with _client(host="nosuch.localtest.me") as client:
        resp = client.get(LIST_PATH)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"
    assert {header: resp.headers.get(header) for header in SECURITY_HEADERS} == SECURITY_HEADERS


# --- the wire-absence walk ---


def _all_keys(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _all_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _all_keys(item)


def _media_nodes(node: Any) -> Iterator[dict[str, Any]]:
    """Every media object in a response: a list row's `cover` and each entry of
    a detail's `media` array."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "cover" and isinstance(value, dict):
                yield value
            elif key == "media" and isinstance(value, list):
                yield from (item for item in value if isinstance(item, dict))
            else:
                yield from _media_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from _media_nodes(item)


@pytest.mark.parametrize("path", ROUTES)
def test_no_manage_only_field_leaks(path: str) -> None:
    """The single most important assertion in this feature. A response_model
    constrains the model the router names; it says nothing about what a future
    edit makes that model inherit. This walks the actual parsed JSON, over a
    fully-populated fake, at every nesting level."""
    service = FakeStorefrontService()
    service.boutique_view = _boutique_view(
        hours=[_rule(0), _rule(5)],
        exceptions=[_exception(datetime.date.today() + datetime.timedelta(days=7))],
    )
    with _client(service) as client:
        resp = client.get(path)
    assert resp.status_code == 200
    leaked = FORBIDDEN_KEYS & set(_all_keys(resp.json()))
    assert leaked == set(), f"{path} leaked {sorted(leaked)}"


@pytest.mark.parametrize("path", [LIST_PATH, DETAIL_PATH])
def test_media_carries_no_identifier_or_object_metadata(path: str) -> None:
    """Key-set equality over the media subtrees only — `id` is legitimate at the
    top level of both dress shapes, so it cannot go in FORBIDDEN_KEYS.

    Deliberately NOT a substring check on the response text: the tenant, dress
    and media UUIDs all appear legitimately inside the signed URL, so a
    substring assertion would be wrong rather than strict, and the first person
    to hit it would "fix" it by weakening it."""
    with _client() as client:
        resp = client.get(path)
    assert resp.status_code == 200
    nodes = list(_media_nodes(resp.json()))
    assert nodes, f"{path} exposed no media node — the assertion below would be vacuous"
    for node in nodes:
        assert set(node) == {"url", "url_expires_at"}, node


# --- dresses ---


def test_list_applies_the_documented_page_defaults() -> None:
    service = FakeStorefrontService()
    with _client(service) as client:
        resp = client.get(LIST_PATH)
    assert resp.status_code == 200
    assert service.call("list_dresses") == {
        "tenant_id": TENANT.id,
        "offset": 0,
        "limit": STOREFRONT_LIST_DEFAULT_LIMIT,
    }
    body = resp.json()
    assert set(body) == {"items", "total", "offset", "limit"}
    assert body["limit"] == STOREFRONT_LIST_DEFAULT_LIMIT
    assert body["total"] == 1


def test_list_accepts_limit_up_to_the_ceiling_and_rejects_one_past_it() -> None:
    """`limit` is a real query parameter now, bounded by Query(le=...) — so the
    ceiling is a 400 at the router rather than a silently ignored value. One
    anonymous request can therefore never mint more than a page of signed URLs.
    """
    service = FakeStorefrontService()
    with _client(service) as client:
        at_bound = client.get(LIST_PATH, params={"limit": STOREFRONT_LIST_MAX_LIMIT})
        beyond = client.get(LIST_PATH, params={"limit": STOREFRONT_LIST_MAX_LIMIT + 1})
        zero = client.get(LIST_PATH, params={"limit": 0})
    assert at_bound.status_code == 200
    assert at_bound.json()["limit"] == STOREFRONT_LIST_MAX_LIMIT
    for rejected in (beyond, zero):
        assert rejected.status_code == 400
        assert rejected.json()["error"]["code"] == "VALIDATION_ERROR"
    # Exactly one recorded call proves neither rejected limit reached the query.
    assert service.call("list_dresses")["limit"] == STOREFRONT_LIST_MAX_LIMIT


def test_list_exposes_offset_and_limit_and_nothing_else() -> None:
    """`archived` and `search` are pinned inside the service, not parameters: no
    query string on this route can reach a repository predicate other than
    paging. FastAPI drops undeclared query params silently, so the proof is the
    kwargs the service was actually called with."""
    service = FakeStorefrontService()
    with _client(service) as client:
        resp = client.get(
            LIST_PATH, params={"offset": 24, "limit": 12, "search": "aurora", "archived": True}
        )
    assert resp.status_code == 200
    assert service.call("list_dresses") == {"tenant_id": TENANT.id, "offset": 24, "limit": 12}


def test_list_rejects_a_negative_offset() -> None:
    service = FakeStorefrontService()
    with _client(service) as client:
        resp = client.get(LIST_PATH, params={"offset": -1})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert service.calls == []


async def test_a_monstrous_offset_is_clamped_below_int8_before_it_reaches_sql() -> None:
    """`ge=0` alone is not a bound. Python ints are unbounded, and this value is
    bound into `OFFSET $n::BIGINT` — so `?offset=2**63` reaches asyncpg's int8
    encoder as an unhandled DataError, i.e. a 500 on an anonymous,
    trivially-scriptable endpoint.

    The router deliberately does NOT reject it (a caller paging past the end
    wants an empty page, not an error); StorefrontService clamps instead. So the
    guard has to be asserted against the REAL service with stubbed repositories —
    asserting it against the fake would only assert the fake. The
    `MAX_LIST_OFFSET < 2**63` line is what stops a later "let's allow deeper
    paging" from walking the ceiling back past the encoder.

    Same stub also pins `archived=False` / `search=None`: they are hardcoded
    inside the service, so no query string can reach a repository predicate
    other than paging.
    """
    assert MAX_LIST_OFFSET < 2**63

    dresses = _RecordingDresses()
    # The class itself is the factory: tenant_session only ever calls it and
    # enters the result.
    factory = cast(Any, _StubSession)
    service = StorefrontService(factory, media_storage=UnconfiguredMediaStorage())
    service._dresses = dresses  # type: ignore[assignment]
    service._media = _RecordingMedia()  # type: ignore[assignment]

    view = await service.list_dresses(TENANT.id, offset=2**63, limit=STOREFRONT_LIST_MAX_LIMIT)

    assert view.offset == MAX_LIST_OFFSET
    assert dresses.page_kwargs == {
        "archived": False,
        "search": None,
        "offset": MAX_LIST_OFFSET,
        "limit": STOREFRONT_LIST_MAX_LIMIT,
    }


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


def test_hidden_price_serialises_null() -> None:
    """price_visible=False with a real number recorded: the number must not
    reach the browser at all, and the key must still be present as null so the
    client cannot tell this dress apart from one with no price."""
    service = FakeStorefrontService()
    service.detail_view = _detail_view(price_visible=False, price_agorot=HIDDEN_PRICE_AGOROT)
    with _client(service) as client:
        resp = client.get(DETAIL_PATH)
    body = resp.json()
    assert body["price_agorot"] is None
    assert "price_agorot" in body


def test_null_price_serialises_null() -> None:
    """The other half: price_visible=True but nothing recorded. The two cases
    are indistinguishable on the wire, which is exactly why price_visible never
    ships — the flag and the number can never disagree."""
    service = FakeStorefrontService()
    service.detail_view = _detail_view(price_visible=True, price_agorot=None)
    with _client(service) as client:
        resp = client.get(DETAIL_PATH)
    body = resp.json()
    assert body["price_agorot"] is None
    assert "price_agorot" in body


def test_a_visible_price_still_ships() -> None:
    service = FakeStorefrontService()
    service.detail_view = _detail_view(price_visible=True, price_agorot=120_000)
    with _client(service) as client:
        resp = client.get(DETAIL_PATH)
    assert resp.json()["price_agorot"] == 120_000


def test_detail_reports_availability_never_stock() -> None:
    with _client() as client:
        resp = client.get(DETAIL_PATH)
    body = resp.json()
    assert body["sizes"] == [
        {"size_label": "38", "available": False},
        {"size_label": "40", "available": True},
    ]
    assert set(body) == {
        "id",
        "name",
        "description",
        "price_agorot",
        "reserved",
        "sizes",
        "media",
    }


def test_detail_passes_the_resolved_tenant_and_the_url_id() -> None:
    service = FakeStorefrontService()
    with _client(service) as client:
        client.get(DETAIL_PATH)
    assert service.call("get_dress") == {"tenant_id": TENANT.id, "dress_id": DRESS_ID}


def test_an_archived_or_unknown_dress_is_a_404() -> None:
    service = FakeStorefrontService()
    service.raise_on["get_dress"] = CatalogNotFoundError()
    with _client(service) as client:
        resp = client.get(DETAIL_PATH)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_a_non_uuid_dress_id_is_a_400() -> None:
    """api.ts's isNotFound maps 400 VALIDATION_ERROR on this route to
    "השמלה כבר לא זמינה" — see test_the_detail_route_declares_exactly_one_parameter
    for the invariant that keeps that mapping honest. This is the one 400 the
    route can actually produce."""
    service = FakeStorefrontService()
    with _client(service) as client:
        resp = client.get("/storefront/dresses/not-a-uuid")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert service.calls == []


def test_reads_never_503_when_storage_is_unconfigured() -> None:
    """A read must never fail because there is no bucket — the page renders
    without photos. `sign_media` already yields a null url; this asserts the
    route does not turn that into an error."""
    service = FakeStorefrontService()
    service.detail_view = _detail_view(url=None)
    with _client(service) as client:
        detail = client.get(DETAIL_PATH)
    assert detail.status_code == 200
    assert detail.json()["media"] == [{"url": None, "url_expires_at": None}]


def test_a_cleared_dress_description_is_null_on_the_wire() -> None:
    service = FakeStorefrontService()
    service.detail_view = _detail_view(description="")
    with _client(service) as client:
        resp = client.get(DETAIL_PATH)
    assert resp.status_code == 200
    assert resp.json()["description"] is None


# --- boutique profile + hours ---


def test_boutique_is_flat_and_reads_name_and_settings_from_the_tenant_context() -> None:
    """No nested `profile` object, and no second SELECT: the resolver already
    read the whole tenants row to route the request, so `name` and `settings`
    arrive from TenantContext."""
    service = FakeStorefrontService()
    service.boutique_view = _boutique_view(hours=[_rule(0)], exceptions=[])
    with _client(service) as client:
        resp = client.get(BOUTIQUE_PATH)
    assert resp.status_code == 200
    assert resp.json() == {
        "name": TENANT.name,
        "essence": PROFILE["essence"],
        "description": PROFILE["description"],
        "phone": PROFILE["phone"],
        "address": PROFILE["address"],
        "maps_url": PROFILE["maps_url"],
        "instagram": PROFILE["instagram"],
        "hours": [{"day_of_week": 0, "open_time": "10:00:00", "close_time": "19:00:00"}],
        "exceptions": [],
        # F20 D13: the two documents plus the platform sub-processor list ride
        # on THIS response rather than on a `/storefront/privacy` of their own,
        # so a legally-required page has no failure mode the rest of the site
        # does not already have.
        "privacy_notice_text": PLATFORM_NOTICE_HE,
        "privacy_dpa_text": PLATFORM_DPA_HE,
        "privacy_subprocessors_text": PLATFORM_SUBPROCESSORS_HE,
    }
    assert service.call("get_boutique") == {
        "tenant_id": TENANT.id,
        "name": TENANT.name,
        "settings": TENANT.settings,
    }


def test_boutique_projects_one_row_per_window_not_per_day() -> None:
    """F7 allows a boutique a lunch break, so two windows can share a day. A
    naive one-row-per-day map would keep only the last and render half the
    boutique's hours."""
    morning = _rule(0)
    afternoon = _rule(0)
    afternoon.open_time = datetime.time(16, 0)
    afternoon.close_time = datetime.time(21, 0)
    service = FakeStorefrontService()
    service.boutique_view = _boutique_view(hours=[morning, afternoon], exceptions=[])
    with _client(service) as client:
        resp = client.get(BOUTIQUE_PATH)
    assert resp.json()["hours"] == [
        {"day_of_week": 0, "open_time": "10:00:00", "close_time": "19:00:00"},
        {"day_of_week": 0, "open_time": "16:00:00", "close_time": "21:00:00"},
    ]


def test_boutique_projects_the_upcoming_exceptions_it_is_given() -> None:
    future = datetime.date.today() + datetime.timedelta(days=30)
    service = FakeStorefrontService()
    service.boutique_view = _boutique_view(
        hours=[], exceptions=[_exception(future, note="שעות מיוחדות")]
    )
    with _client(service) as client:
        resp = client.get(BOUTIQUE_PATH)
    assert resp.json()["exceptions"] == [
        {
            "date": future.isoformat(),
            "open_time": None,
            "close_time": None,
            "note": "שעות מיוחדות",
        }
    ]


def test_boutique_survives_an_empty_profile() -> None:
    service = FakeStorefrontService()
    service.boutique_view = _boutique_view(profile={}, hours=[], exceptions=[])
    with _client(service) as client:
        resp = client.get(BOUTIQUE_PATH)
    assert resp.status_code == 200
    assert resp.json() == {
        "name": TENANT.name,
        "essence": None,
        "description": None,
        "phone": None,
        "address": None,
        "maps_url": None,
        "instagram": None,
        "hours": [],
        "exceptions": [],
        # The platform defaults, not null: a boutique that has configured nothing
        # still owes a §11 notice, and an empty privacy field on the wire would
        # render a legally-required page blank.
        "privacy_notice_text": PLATFORM_NOTICE_HE,
        "privacy_dpa_text": PLATFORM_DPA_HE,
        "privacy_subprocessors_text": PLATFORM_SUBPROCESSORS_HE,
    }


def test_a_cleared_profile_field_is_null_on_the_wire_not_an_empty_string() -> None:
    """Empty string is the CANONICAL cleared value (boutique/validation.py), and
    the manage form seeds every blank field to "" before submitting — so any owner
    who saves the profile once turns their blanks from null into "".

    A "" reaching the storefront renders `<a href="tel:">` with no accessible
    name: a WCAG 2.4.4 (A) failure, and it lands three times on the statutory
    הצהרת נגישות page whose whole legal function is to publish a reachable
    channel. Both values already mean "not set", so the wire must not distinguish
    them — that is what lets every client guard be a plain null check.
    """
    service = FakeStorefrontService()
    service.boutique_view = _boutique_view(
        profile=dict.fromkeys(
            ["essence", "description", "phone", "address", "maps_url", "instagram"], ""
        ),
        hours=[],
        exceptions=[],
    )
    with _client(service) as client:
        resp = client.get(BOUTIQUE_PATH)
    assert resp.status_code == 200
    assert resp.json() == {
        "name": TENANT.name,
        "essence": None,
        "description": None,
        "phone": None,
        "address": None,
        "maps_url": None,
        "instagram": None,
        "hours": [],
        "exceptions": [],
        # The platform defaults, not null: a boutique that has configured nothing
        # still owes a §11 notice, and an empty privacy field on the wire would
        # render a legally-required page blank.
        "privacy_notice_text": PLATFORM_NOTICE_HE,
        "privacy_dpa_text": PLATFORM_DPA_HE,
        "privacy_subprocessors_text": PLATFORM_SUBPROCESSORS_HE,
    }


# --- the owner cookie is not a second contract ---


def test_owner_cookie_changes_nothing() -> None:
    """The storefront and the console share the origin {slug}.{domain}, so a
    browser would attach `boutique_session` if the client asked it to. A public
    endpoint that behaves differently for a logged-in owner is a public endpoint
    with a hidden second contract — so the bytes must be identical, not merely
    the status code.
    """
    with _client() as client:
        anonymous = {path: client.get(path) for path in ROUTES}
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
        authenticated = {path: client.get(path) for path in ROUTES}
    for path in ROUTES:
        assert anonymous[path].status_code == authenticated[path].status_code == 200, path
        assert anonymous[path].content == authenticated[path].content, path


# --- structural: the public schemas may never inherit from the manage ones ---


def test_public_schemas_share_no_inheritance_with_the_manage_schemas() -> None:
    """Inheritance is exactly how the mandated omissions get silently reverted:
    one field added to DressResponse and every storefront row carries it."""
    assert not issubclass(StorefrontDress, DressResponse)
    assert not issubclass(StorefrontDetail, StorefrontDress)
    assert not issubclass(StorefrontDetail, DressResponse)
    assert not issubclass(StorefrontTerms, TermsVersionResponse)


def test_storefront_dress_row_has_exactly_these_fields() -> None:
    """The assertion that fails CI when someone adds a field "just for
    debugging"."""
    assert set(StorefrontDress.model_fields) == {
        "id",
        "name",
        "price_agorot",
        "reserved",
        "cover",
    }


def test_storefront_detail_has_exactly_these_fields() -> None:
    assert set(StorefrontDetail.model_fields) == {
        "id",
        "name",
        "description",
        "price_agorot",
        "reserved",
        "sizes",
        "media",
    }


def test_storefront_terms_has_exactly_these_fields() -> None:
    """`id`, `tenant_id`, `created_by` and the timestamps are operator
    provenance, not booking-page content."""
    assert set(StorefrontTerms.model_fields) == {
        "version",
        "terms_text",
        "refundable_until_hours_before",
        "forfeit_percent",
    }


def test_boutique_response_has_exactly_these_flat_fields() -> None:
    """FLAT: the old nested `profile` object is gone, and `rules` is now `hours`.
    Set-equality is what catches a new top-level field whose name happens not to
    be in FORBIDDEN_KEYS."""
    assert set(BoutiqueResponse.model_fields) == {
        "name",
        "essence",
        "description",
        "phone",
        "address",
        "maps_url",
        "instagram",
        "hours",
        "exceptions",
        "privacy_notice_text",
        "privacy_dpa_text",
        "privacy_subprocessors_text",
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
    assert _public_price(row) == expected


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


def test_upcoming_exceptions_truncates_a_three_year_holiday_log() -> None:
    """A boutique that has recorded every holiday since it opened must not turn
    /about into a calendar."""
    today = datetime.date(2026, 7, 27)
    rows = [_exception(today + datetime.timedelta(days=day)) for day in range(60)]
    assert len(upcoming_exceptions(rows, today)) == UPCOMING_EXCEPTIONS_LIMIT


def test_mappers_are_importable_pure_functions() -> None:
    assert public_dress(_dress_view()).price_agorot is None
    assert [size.available for size in public_dress_detail(_detail_view()).sizes] == [False, True]
    assert public_boutique(_boutique_view()).name == TENANT.name
    assert public_terms(_terms_row()).version == 3


# --- the per-tenant read budget ---


def test_read_throttle_maps_to_429() -> None:
    """Keyed "storefront:{tenant_id}" with NO IP component — so a second visitor
    of the same boutique shares the budget, and a forged X-Forwarded-For buys
    nothing. The old per-(tenant, IP) key was inert in production: _client_ip
    returns None whenever trust_forwarded_for is False, which is the default.
    """
    limiter = FixedWindowRateLimiter(max_attempts=2, window_seconds=60, clock=time.monotonic)
    with _client(limiter=limiter) as client:
        assert client.get(LIST_PATH).status_code == 200
        assert client.get(BOUTIQUE_PATH).status_code == 200
        # A different claimed IP does NOT get a fresh bucket: this fails the day
        # someone re-keys the limiter on the client address.
        blocked = client.get(LIST_PATH, headers={"x-forwarded-for": "203.0.113.9"})
    assert blocked.status_code == 429
    # Zero new error codes: the shared TOO_MANY_ATTEMPTS body serves this.
    assert blocked.json() == {
        "error": {"code": "TOO_MANY_ATTEMPTS", "message": "Too many attempts. Try again later."}
    }


@pytest.mark.parametrize("path", ROUTES)
def test_the_read_throttle_is_not_inert(path: str) -> None:
    """FixedWindowRateLimiter counts only what is explicitly recorded, and its
    docstring says "successes never count" — which is right for a login form and
    wrong here. Without the record_failure call on the success path the limiter
    never fires at all, and every route below would answer 200 against a limiter
    configured to block everything."""
    blocks_everything = FixedWindowRateLimiter(
        max_attempts=0, window_seconds=60, clock=time.monotonic
    )
    with _client(limiter=blocks_everything) as client:
        resp = client.get(path)
    assert resp.status_code == 429


# --- the complete error-code table ---


@dataclasses.dataclass(frozen=True)
class ErrorCase:
    """One row of the spec's error table for this surface: a probe that provokes
    it, and the status + code the app must produce."""

    code: str
    status: int
    probe: Callable[[], Any]


def _probe_tenant_not_found() -> Any:
    with _client(host="nosuch.localtest.me") as client:
        return client.get(LIST_PATH)


def _probe_not_found() -> Any:
    service = FakeStorefrontService()
    service.raise_on["get_dress"] = CatalogNotFoundError()
    with _client(service) as client:
        return client.get(DETAIL_PATH)


def _probe_validation_error() -> Any:
    with _client() as client:
        return client.get(LIST_PATH, params={"limit": STOREFRONT_LIST_MAX_LIMIT + 1})


def _probe_too_many_attempts() -> Any:
    blocked = FixedWindowRateLimiter(max_attempts=0, window_seconds=60, clock=time.monotonic)
    with _client(limiter=blocked) as client:
        return client.get(LIST_PATH)


ERROR_CASES: list[ErrorCase] = [
    ErrorCase("TENANT_NOT_FOUND", 404, _probe_tenant_not_found),
    ErrorCase("NOT_FOUND", 404, _probe_not_found),
    ErrorCase("VALIDATION_ERROR", 400, _probe_validation_error),
    ErrorCase("TOO_MANY_ATTEMPTS", 429, _probe_too_many_attempts),
]


@pytest.mark.parametrize("case", ERROR_CASES, ids=[case.code for case in ERROR_CASES])
def test_every_error_maps_to_its_status_and_house_shape(case: ErrorCase) -> None:
    """A forgotten handler registration returns 500, not the documented status —
    and StorefrontThrottledError is a brand-new exception class whose handler is
    the only thing between the read budget and an unhandled 500."""
    resp = case.probe()
    assert resp.status_code == case.status
    body = resp.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == case.code
    assert body["error"]["message"]


def test_every_spec_error_code_is_asserted() -> None:
    """Mechanical completeness: a row added to the spec's error table without a
    test here fails immediately, rather than shipping as a 500."""
    assert {case.code for case in ERROR_CASES} == SPEC_ERROR_CODES


# --- source-level guards ---


def _referenced_names(source: str) -> set[str]:
    """Every attribute and bare name the module actually references. Parsed, not
    grepped: `service.py`'s docstring says the forbidden symbol's name out loud
    (to explain why it is forbidden), so a substring scan would fail on the very
    prose that documents the rule."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Name):
            names.add(node.id)
    return names


def test_storefront_module_never_references_by_id_any_state() -> None:
    """`by_id` pins `deleted_at IS NULL`, so an archived dress is an
    indistinguishable 404 — precisely the design's "השמלה כבר לא זמינה" state.
    `by_id_any_state` is the manage console's detail/restore escape hatch and
    would turn an archived dress into a browsable public page."""
    sources = sorted(STOREFRONT_SOURCE_DIR.glob("*.py"))
    assert sources, f"no source under {STOREFRONT_SOURCE_DIR} — this guard would be vacuous"
    offenders = [
        path.name
        for path in sources
        if "by_id_any_state" in _referenced_names(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_the_detail_route_declares_exactly_one_parameter() -> None:
    """`api.ts`'s isNotFound maps 400 VALIDATION_ERROR on this route to
    "השמלה כבר לא זמינה" and suppresses the retry button, on the strength of one
    invariant: the ONLY 400 reachable here is a malformed UUID. That holds today
    — the route takes no query params and no body, the limiter answers 429, and
    both tenant and dress misses answer 404.

    But main.py maps EVERY DomainValidationError to VALIDATION_ERROR, so the day
    this route gains a query parameter, a real validation failure silently
    becomes "this dress does not exist" with no way to retry. This pins the
    premise rather than the conclusion.
    """
    app = create_app(resolver=_null_resolver)
    detail = [
        route
        for route in _iter_leaf_routes(app)
        if getattr(route, "path", None) == "/storefront/dresses/{dress_id}"
    ]
    assert len(detail) == 1, "the detail route moved — revisit isNotFound in api.ts"
    params = detail[0].dependant.query_params + detail[0].dependant.body_params
    assert params == [], (
        "the detail route gained a parameter, so 400 VALIDATION_ERROR no longer "
        "means 'malformed id' — api.ts isNotFound must stop treating it as a miss"
    )


# --- docs are dark outside dev ---


DOCS_PATHS = ["/openapi.json", "/docs", "/redoc"]


AppEnv = Literal["dev", "staging", "production"]


def _settings(app_env: AppEnv) -> Settings:
    # database_url and a non-localtest.me base_domain are both REQUIRED outside
    # dev or the config validators raise; the media fields are pinned so a local
    # .env cannot change what this test builds.
    return Settings(
        app_env=app_env,
        database_url="postgresql+asyncpg://app:pw@db:5432/boutique",
        base_domain="boutique.example" if app_env != "dev" else "localtest.me",
        media_bucket=None,
        media_endpoint_url=None,
        media_force_path_style=False,
    )


def _app_with_settings(monkeypatch: pytest.MonkeyPatch, app_env: AppEnv) -> TestClient:
    monkeypatch.setattr("app.main.get_settings", lambda: _settings(app_env))
    return TestClient(create_app(resolver=_null_resolver))


def test_openapi_is_unreachable_outside_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    """F10 makes this origin publicly crawlable, and the first crawler that finds
    {slug}.{domain} also finds /openapi.json — a complete, uncredentialed
    description of every /manage route and of exactly the fields the storefront
    allowlist exists to fence off. create_app passes docs_url/redoc_url/
    openapi_url=None outside dev, so FastAPI never registers the routes at all.

    get_settings is @lru_cache-d AND Settings reads .env, so the only honest way
    to drive this is a hand-built Settings patched over app.main.get_settings.
    """
    client = _app_with_settings(monkeypatch, "production")
    for path in DOCS_PATHS:
        assert client.get(path).status_code == 404, path

    # The control: the same three paths ARE served in dev. Without it a typo in
    # DOCS_PATHS would make every assertion above pass for the wrong reason.
    dev_client = _app_with_settings(monkeypatch, "dev")
    for path in DOCS_PATHS:
        assert dev_client.get(path).status_code == 200, path


# --- stubs for the offset-clamp unit test (no database, no event loop of its own) ---


class _NullBegin:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args: Any) -> None:
        return None


class _StubSession:
    """Just enough of AsyncSession for tenant_session()'s set_config call. The
    repositories are stubbed too, so no statement is ever built."""

    async def execute(self, *args: Any, **kwargs: Any) -> None:
        return None

    def begin(self) -> _NullBegin:
        return _NullBegin()

    async def __aenter__(self) -> "_StubSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None


class _RecordingDresses:
    def __init__(self) -> None:
        self.page_kwargs: dict[str, Any] | None = None

    async def list_page(
        self,
        session: Any,
        tenant_id: uuid.UUID,
        *,
        archived: bool,
        search: str | None,
        offset: int,
        limit: int,
    ) -> list[Dress]:
        self.page_kwargs = {
            "archived": archived,
            "search": search,
            "offset": offset,
            "limit": limit,
        }
        return []

    async def count(
        self, session: Any, tenant_id: uuid.UUID, *, archived: bool, search: str | None
    ) -> int:
        return 0


class _RecordingMedia:
    async def covers_by_dress(
        self, session: Any, tenant_id: uuid.UUID, dress_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, Any]:
        return {}


class _StubTerms:
    def __init__(self, row: TermsVersion | None) -> None:
        self.row = row
        self.tenant_ids: list[uuid.UUID] = []

    async def current(self, session: Any, tenant_id: uuid.UUID) -> TermsVersion | None:
        self.tenant_ids.append(tenant_id)
        return self.row


# --- F12: the booking grid reads ---


def test_slots_ship_start_times_and_nothing_else() -> None:
    """`capacity` is in FORBIDDEN_KEYS so the wire-absence walk arms itself.
    This pins the harder half: `remaining` must not be here EITHER. With no
    bookings it equals capacity exactly, so shipping it would republish the
    fenced field under a key the absence walk does not know to forbid."""
    with _client() as client:
        resp = client.get("/storefront/slots")
    assert resp.status_code == 200
    assert resp.json() == {
        "slots": [
            {"starts_at": "2026-08-03T10:00:00Z"},
            {"starts_at": "2026-08-03T10:30:00Z"},
        ]
    }
    assert "remaining" not in resp.text
    assert "capacity" not in resp.text


def test_slots_pass_the_window_through_verbatim() -> None:
    service = FakeStorefrontService()
    with _client(service) as client:
        resp = client.get("/storefront/slots?from=2026-08-02&to=2026-08-08")
    assert resp.status_code == 200
    call = service.call("list_slots")
    assert call["from_date"] == datetime.date(2026, 8, 2)
    assert call["to_date"] == datetime.date(2026, 8, 8)


def test_slots_default_the_window_to_the_service() -> None:
    """Both bounds are None on the wire; resolving them is the service's job
    (it owns `today` in Jerusalem), not the router's."""
    service = FakeStorefrontService()
    with _client(service) as client:
        client.get("/storefront/slots")
    call = service.call("list_slots")
    assert call["from_date"] is None
    assert call["to_date"] is None


def test_an_inverted_window_is_a_400_not_an_empty_list() -> None:
    """Answering "no availability" to a caller bug would hide it."""
    service = FakeStorefrontService()
    service.raise_on["list_slots"] = SlotWindowError("`to` must not precede `from`.")
    with _client(service) as client:
        resp = client.get("/storefront/slots?from=2026-08-08&to=2026-08-02")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_a_malformed_date_is_a_house_shape_400() -> None:
    with _client() as client:
        resp = client.get("/storefront/slots?from=not-a-date")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_appointment_types_ship_the_booking_facts() -> None:
    with _client() as client:
        resp = client.get("/storefront/appointment-types")
    assert resp.status_code == 200
    assert resp.json() == [
        {
            "id": str(APPOINTMENT_TYPE_ID),
            "name": "מדידת כלה",
            "duration_minutes": 60,
            # Disclosed, not enforced: an anonymous visitor cannot be classified
            # as a bride, so the UI labels the option and E5 owns enforcement.
            "audience": "brides_only",
            "deposit_required": True,
            "deposit_amount_agorot": 15_000,
        }
    ]


# --- F14: the public terms read ---


def test_terms_ship_exactly_the_four_policy_fields() -> None:
    """Exact-equality is the allowlist: `id`, `tenant_id`, `created_by` and the
    timestamps are absent because nothing else CAN be present."""
    with _client() as client:
        resp = client.get(TERMS_PATH)
    assert resp.status_code == 200
    assert resp.json() == {
        "version": 3,
        "terms_text": TERMS_TEXT,
        "refundable_until_hours_before": 48,
        "forfeit_percent": 30,
    }


def test_no_published_terms_is_a_404() -> None:
    """D5: a boutique that never published a policy has nothing for a customer
    to accept, and the miss is the module's ordinary NOT_FOUND."""
    service = FakeStorefrontService()
    service.terms_rows.clear()
    with _client(service) as client:
        resp = client.get(TERMS_PATH)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_terms_are_tenant_isolated_by_host() -> None:
    """Tenant identity derives from DNS: the same path under another boutique's
    host serves THAT boutique's policy, never a neighbour's."""
    tenant_b = TenantContext(id=uuid.uuid4(), slug="noya", name="נויה", settings={})
    service = FakeStorefrontService()
    service.terms_rows[tenant_b.id] = _terms_row(
        tenant_id=tenant_b.id, version=9, terms_text="ללא החזר."
    )
    tenants = {"bella": TENANT, "noya": tenant_b}
    with _client(service, tenants=tenants) as client:
        body_a = client.get(TERMS_PATH).json()
    with _client(service, host="noya.localtest.me", tenants=tenants) as client:
        body_b = client.get(TERMS_PATH).json()
    assert body_a["terms_text"] == TERMS_TEXT
    assert body_b == {
        "version": 9,
        "terms_text": "ללא החזר.",
        "refundable_until_hours_before": 48,
        "forfeit_percent": 30,
    }
    assert [kwargs["tenant_id"] for called, kwargs in service.calls if called == "get_terms"] == [
        TENANT.id,
        tenant_b.id,
    ]


def test_terms_are_no_store_and_cookie_blind() -> None:
    with _client() as client:
        anonymous = client.get(TERMS_PATH)
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
        authenticated = client.get(TERMS_PATH)
    assert anonymous.status_code == authenticated.status_code == 200
    assert anonymous.headers["cache-control"] == "no-store"
    assert anonymous.content == authenticated.content


async def test_get_terms_reads_the_current_version_and_404s_when_none_exists() -> None:
    """Against the REAL service with a stubbed repository, like the offset-clamp
    test: the None→404 fold lives in the service, so asserting it against the
    fake would only assert the fake."""
    factory = cast(Any, _StubSession)
    service = StorefrontService(factory, media_storage=UnconfiguredMediaStorage())
    row = _terms_row()
    stub = _StubTerms(row)
    service._terms = stub  # type: ignore[assignment]
    assert await service.get_terms(TENANT.id) is row
    assert stub.tenant_ids == [TENANT.id]

    service._terms = _StubTerms(None)  # type: ignore[assignment]
    with pytest.raises(CatalogNotFoundError):
        await service.get_terms(TENANT.id)


def test_the_privacy_documents_are_anonymous_cookie_blind_and_no_store() -> None:
    """⚠ F20 D13. The §11 notice is served to a woman who has typed nothing yet,
    so it must be reachable with no session at all — and byte-identical with one,
    which is F11's cookie-blindness invariant applied to the one payload whose
    contents are a legal representation.

    `no-store` matters here for a reason the rest of this response does not have:
    an owner editing her notice must not be arguing with a browser cache about
    which version of a statutory document a customer saw.
    """
    service = FakeStorefrontService()
    service.boutique_view = _boutique_view()
    with _client(service) as client:
        anonymous = client.get(BOUTIQUE_PATH)
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
        authenticated = client.get(BOUTIQUE_PATH)
    assert anonymous.status_code == authenticated.status_code == 200
    assert anonymous.content == authenticated.content
    assert anonymous.headers["cache-control"] == "no-store"
    assert anonymous.json()["privacy_notice_text"] == PLATFORM_NOTICE_HE


def test_a_boutiques_override_reaches_the_wire_and_the_subprocessor_list_never_does() -> None:
    """The override half and D14's un-overridable half, in one walk.

    A settings blob that TRIES to set `subprocessors_text` changes nothing — that
    is what makes adding a processor to the platform list reach every tenant by
    construction, instead of only the boutiques that never edited their DPA
    prose. `""` is the revert sentinel, because `||` can add or replace a JSONB
    key but never remove one.
    """
    service = FakeStorefrontService()
    service.boutique_view = _boutique_view(
        settings={
            "privacy": {
                "notice_text": "הנוסח של הבוטיק",
                "dpa_text": "   ",
                "subprocessors_text": "רשימה מזויפת",
            }
        }
    )
    with _client(service) as client:
        body = client.get(BOUTIQUE_PATH).json()
    assert body["privacy_notice_text"] == "הנוסח של הבוטיק"
    # Whitespace-only is a cleared textarea, not a document.
    assert body["privacy_dpa_text"] == PLATFORM_DPA_HE
    assert body["privacy_subprocessors_text"] == PLATFORM_SUBPROCESSORS_HE
