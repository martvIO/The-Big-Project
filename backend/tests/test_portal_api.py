"""Fast API tests for F24's portal surface: a stub PortalService + a hardcoded
TenantContext, no database (test_booking_manage_api.py style).

The db-marked suite proves the behaviour; this file proves the HTTP contract —
the auth matrix (every cookie-authed route 401s without a cookie and with a
garbage one), the cookie's own attributes, `no-store`, and the fact that the
STAFF cookie is not a portal credential and vice versa.

That last pair is the reason this file exists at all. Both apps live on one
tenant host, so both cookies ride every request to it. If `get_current_customer`
read `boutique_session`, an owner signing in would silently acquire a customer
session on her own boutique; if `get_current_staff` read the customer cookie, a
bride would hold a console session. Two names, two dependencies, and two tests.
"""

import dataclasses
import datetime
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.cookies import CUSTOMER_SESSION_COOKIE, SESSION_COOKIE
from app.auth.dependencies import get_auth_service
from app.auth.service import StaffContext
from app.booking.manage import ManageTenant
from app.booking.schemas import (
    ManageBookingFacts,
    ManageBookingResponse,
    ManageBoutique,
    ManagePolicy,
)
from app.main import create_app
from app.models.constants import BookingStatus, MessageKind
from app.portal.schemas import (
    PortalBellItem,
    PortalBellResponse,
    PortalBookingRow,
    PortalBookingsResponse,
    PortalSessionResponse,
)
from app.portal.service import CustomerContext, PortalNoBookingsError, PortalThrottledError
from app.security_headers import SECURITY_HEADERS
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="בלה כלות", settings={})
STAFF_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
STAFF_SESSION_TOKEN = "staff-session-token"
PORTAL_TOKEN = "portal-session-token"
VERIFICATION_TOKEN = "vt-" + "a" * 40
PHONE = "0501234567"

SESSION = "/storefront/portal/session"
ME = "/storefront/portal/me"
LOGOUT = "/storefront/portal/logout"
BOOKINGS = "/storefront/portal/bookings"
BOOKING = "/storefront/portal/booking"
CONFIRM = "/storefront/portal/booking/confirm-attendance"
CANCEL = "/storefront/portal/booking/cancel"
ICS = "/storefront/portal/booking.ics"
BELL = "/storefront/portal/bell"
BELL_SEEN = "/storefront/portal/bell/seen"
BOOKING_ID = uuid.uuid4()
MESSAGE_ID = uuid.uuid4()
# Every route that reads the customer cookie. Grows with each phase; the auth
# matrix below is parametrised over it so a route added without a cookie gate is
# a red rather than a gap.
COOKIE_ROUTES: tuple[tuple[str, str, dict[str, Any] | None], ...] = (
    ("GET", ME, None),
    ("POST", LOGOUT, None),
    ("GET", BOOKINGS, None),
    ("GET", f"{BOOKING}?id={BOOKING_ID}", None),
    ("POST", CONFIRM, {"id": str(BOOKING_ID)}),
    ("POST", CANCEL, {"id": str(BOOKING_ID)}),
    ("GET", f"{ICS}?id={BOOKING_ID}", None),
    ("GET", BELL, None),
    ("POST", BELL_SEEN, None),
)

CUSTOMER = CustomerContext(id=CUSTOMER_ID, tenant_id=TENANT.id, name="רותם", phone="+972501234567")
STARTS_AT = datetime.datetime(2099, 8, 2, 7, 0, tzinfo=datetime.UTC)


def _row() -> PortalBookingRow:
    return PortalBookingRow(
        id=BOOKING_ID,
        starts_at=STARTS_AT,
        status=BookingStatus.CONFIRMED.value,
        attendance_confirmed_at=None,
        appointment_type_name="מדידה ראשונה",
        dress_name="שמלת אלמה",
        dress_size="36",
    )


def _detail_response() -> ManageBookingResponse:
    """The TOKENIZED page's shape, verbatim — reusing it is the mirror guarantee
    (spec D4), so this helper deliberately builds `ManageBookingResponse` and not
    a portal type."""
    return ManageBookingResponse(
        booking=ManageBookingFacts(
            starts_at=STARTS_AT,
            status=BookingStatus.CONFIRMED.value,
            attendance_confirmed_at=None,
            appointment_type_name="מדידה ראשונה",
            dress_name="שמלת אלמה",
            dress_size="36",
            deposit_taken=False,
        ),
        policy=ManagePolicy(refundable_until_hours_before=48, forfeit_percent=50),
        boutique=ManageBoutique(name=TENANT.name, phone=None, address=None, maps_url=None),
    )


@dataclasses.dataclass
class StubPortalService:
    """The router is a thin delegate, so the stub is programmable outcomes and a
    call log — nothing else."""

    error: Exception | None = None
    calls: list[tuple[str, Any]] = dataclasses.field(default_factory=list)

    async def create_session(
        self, tenant_id: uuid.UUID, *, raw_phone: str, verification_token: str
    ) -> tuple[PortalSessionResponse, str]:
        if self.error is not None:
            raise self.error
        self.calls.append(("create_session", (tenant_id, raw_phone, verification_token)))
        return PortalSessionResponse(customer_name=CUSTOMER.name), PORTAL_TOKEN

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> CustomerContext | None:
        return CUSTOMER if token == PORTAL_TOKEN and tenant_id == TENANT.id else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        self.calls.append(("logout", (tenant_id, token)))

    async def list_bookings(
        self, tenant_id: uuid.UUID, customer: CustomerContext
    ) -> PortalBookingsResponse:
        if self.error is not None:
            raise self.error
        self.calls.append(("list_bookings", (tenant_id, customer.id)))
        return PortalBookingsResponse(upcoming=[_row()], past=[])

    async def get_booking(
        self, tenant: ManageTenant, customer: CustomerContext, booking_id: uuid.UUID
    ) -> ManageBookingResponse:
        return self._detail("get_booking", tenant, customer, booking_id)

    async def confirm_attendance(
        self, tenant: ManageTenant, customer: CustomerContext, booking_id: uuid.UUID
    ) -> ManageBookingResponse:
        return self._detail("confirm_attendance", tenant, customer, booking_id)

    async def cancel(
        self, tenant: ManageTenant, customer: CustomerContext, booking_id: uuid.UUID
    ) -> ManageBookingResponse:
        return self._detail("cancel", tenant, customer, booking_id)

    async def bell(self, tenant_id: uuid.UUID, customer: CustomerContext) -> PortalBellResponse:
        if self.error is not None:
            raise self.error
        self.calls.append(("bell", (tenant_id, customer.id)))
        return PortalBellResponse(
            unread_count=1,
            items=[
                PortalBellItem(
                    id=MESSAGE_ID,
                    kind=MessageKind.REMINDER.value,
                    created_at=STARTS_AT,
                    booking_id=BOOKING_ID,
                    starts_at=STARTS_AT,
                    appointment_type_name="מדידה ראשונה",
                )
            ],
        )

    async def mark_bell_seen(self, tenant_id: uuid.UUID, customer: CustomerContext) -> None:
        self.calls.append(("mark_bell_seen", (tenant_id, customer.id)))

    async def get_booking_ics(
        self,
        tenant: ManageTenant,
        customer: CustomerContext,
        booking_id: uuid.UUID,
        *,
        slug: str,
        base_domain: str,
    ) -> str:
        if self.error is not None:
            raise self.error
        self.calls.append(("get_booking_ics", (tenant.id, customer.id, booking_id)))
        return f"BEGIN:VCALENDAR\r\nUID:{booking_id}@{slug}.{base_domain}\r\nEND:VCALENDAR\r\n"

    def _detail(
        self,
        name: str,
        tenant: ManageTenant,
        customer: CustomerContext,
        booking_id: uuid.UUID,
    ) -> ManageBookingResponse:
        if self.error is not None:
            raise self.error
        self.calls.append((name, (tenant.id, customer.id, booking_id)))
        return _detail_response()


class FakeAuthService:
    """Only here so the owner cookie in the cross-cookie tests is a genuinely
    resolvable staff session rather than a random string."""

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
        return self.staff, STAFF_SESSION_TOKEN

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        return self.staff if token == STAFF_SESSION_TOKEN else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        return None


def _client(
    stub: StubPortalService | None = None, *, host: str = "bella.localtest.me"
) -> tuple[TestClient, StubPortalService]:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    service = stub if stub is not None else StubPortalService()
    app.state.portal_service = service
    auth = FakeAuthService()
    app.state.auth_service = auth
    app.dependency_overrides[get_auth_service] = lambda: auth
    return TestClient(app, base_url=f"http://{host}"), service


# --- the mint ---------------------------------------------------------------


def test_the_mint_is_anonymous_and_sets_the_customer_cookie() -> None:
    client, stub = _client()
    with client:
        assert client.cookies == {}
        resp = client.post(SESSION, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN})
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"customer_name": "רותם"}
    assert [name for name, _ in stub.calls] == ["create_session"]
    cookie = resp.headers["set-cookie"]
    assert cookie.startswith(f"{CUSTOMER_SESSION_COOKIE}=")
    # HttpOnly (no JS theft), SameSite=Lax (CSRF, with CsrfOriginMiddleware),
    # path=/ and NO Domain attribute — host-only, so a session minted on
    # boutique A is never sent to boutique B's subdomain.
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Domain=" not in cookie
    # dev settings: Secure is off locally, on everywhere else.
    assert "Secure" not in cookie


def test_the_mint_cookie_carries_the_portal_ttl_not_the_staff_one() -> None:
    """30 days, deliberately longer than the staff 12h (spec D2): every
    re-login costs the tenant a real SMS, so a short TTL is a recurring bill."""
    from app.core.config import get_settings

    client, _ = _client()
    with client:
        resp = client.post(SESSION, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN})
    settings = get_settings()
    assert settings.portal_session_ttl_seconds == 30 * 24 * 3600
    assert settings.portal_session_ttl_seconds != settings.session_ttl_seconds
    assert f"Max-Age={settings.portal_session_ttl_seconds}" in resp.headers["set-cookie"]


def test_an_unknown_phone_is_the_portal_no_bookings_code() -> None:
    """Not an oracle: she just proved possession of the number, so «this phone
    has no bookings here» discloses only her own data (spec D1). Its own code
    rather than the house 404 because the login panel renders a state off it."""
    client, _ = _client(StubPortalService(error=PortalNoBookingsError()))
    with client:
        resp = client.post(SESSION, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PORTAL_NO_BOOKINGS"
    assert "set-cookie" not in resp.headers


def test_the_mint_brake_is_the_shared_too_many_attempts_body() -> None:
    client, _ = _client(StubPortalService(error=PortalThrottledError()))
    with client:
        resp = client.post(SESSION, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN})
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"


def test_the_mint_refuses_an_unknown_field() -> None:
    """ForbidExtra: a field the schema silently dropped is the shape that lets a
    caller believe it sent something."""
    client, _ = _client()
    with client:
        resp = client.post(
            SESSION,
            json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN, "name": "רותם"},
        )
    assert resp.status_code == 400


# --- the auth matrix --------------------------------------------------------


@pytest.mark.parametrize(("method", "path", "body"), COOKIE_ROUTES)
def test_a_cookie_authed_route_is_401_without_a_cookie(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    client, _ = _client()
    with client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.parametrize(("method", "path", "body"), COOKIE_ROUTES)
def test_a_cookie_authed_route_is_401_with_a_garbage_cookie(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """One body whether the cookie is missing, expired, revoked or another
    tenant's — the `NotAuthenticatedError` contract the staff side already
    holds."""
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, "not-a-real-token")
        resp = client.request(method, path, json=body)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"


@pytest.mark.parametrize(("method", "path", "body"), COOKIE_ROUTES)
def test_a_staff_cookie_is_not_a_portal_credential(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """The whole reason the cookie has its own name. An owner signed into the
    console must not be silently logged into the portal of her own boutique."""
    client, _ = _client()
    with client:
        client.cookies.set(SESSION_COOKIE, STAFF_SESSION_TOKEN)
        resp = client.request(method, path, json=body)
    assert resp.status_code == 401


def test_a_portal_cookie_is_not_a_staff_credential() -> None:
    """The mirror direction, asserted on a real /manage route: a live customer
    session must never resolve a console principal."""
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.get("/manage/auth/me")
    assert resp.status_code == 401


def test_me_answers_the_session_customers_name() -> None:
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.get(ME)
    assert resp.status_code == 200
    assert resp.json() == {"customer_name": "רותם"}


def test_logout_revokes_and_clears_the_cookie() -> None:
    client, stub = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.post(LOGOUT)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert stub.calls == [("logout", (TENANT.id, PORTAL_TOKEN))]
    cleared = resp.headers["set-cookie"]
    assert cleared.startswith(f"{CUSTOMER_SESSION_COOKIE}=")
    assert "Max-Age=0" in cleared or "expires=Thu, 01 Jan 1970" in cleared.lower()


# --- the shared posture -----------------------------------------------------


@pytest.mark.parametrize(("method", "path"), [("POST", SESSION), ("GET", ME), ("POST", LOGOUT)])
def test_every_portal_route_is_never_cached(method: str, path: str) -> None:
    """Every body here names a real person's appointments, and the flow runs on
    a phone where bfcache is the default."""
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.request(
            method, path, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN}
        )
    assert resp.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(("method", "path"), [("POST", SESSION), ("GET", ME), ("POST", LOGOUT)])
def test_every_portal_route_carries_the_security_headers(method: str, path: str) -> None:
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.request(
            method, path, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN}
        )
    assert {header: resp.headers.get(header) for header in SECURITY_HEADERS} == SECURITY_HEADERS


@pytest.mark.parametrize(("method", "path"), [("POST", SESSION), ("GET", ME), ("POST", LOGOUT)])
def test_unknown_host_is_tenant_not_found(method: str, path: str) -> None:
    """Public is not host-agnostic: an unresolvable host 404s before any
    tenant-scoped handler runs, so a cookie cannot be probed against 'no
    tenant'."""
    client, _ = _client(host="nosuch.localtest.me")
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.request(
            method, path, json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN}
        )
    assert resp.status_code == 404


def test_the_portal_lives_under_the_storefront_prefix() -> None:
    """Spec D7: no new top-level API family. A `/portal` prefix would need a
    vite proxy entry, an SPA-fallback exclusion and a CSRF review, for nothing —
    and `_RESERVED_SEGMENTS` would have to grow a member for it.

    Asserted as an ABSENCE rather than as the whole frozenset: a workspace app
    that genuinely IS its own surface (F25's `/platform`) is supposed to add a
    segment, and pinning the full set would red this module for a feature that
    never touched the portal."""
    from app.main import _RESERVED_SEGMENTS

    assert "portal" not in _RESERVED_SEGMENTS
    assert {"manage", "storefront"} <= _RESERVED_SEGMENTS
    for path in (SESSION, ME, LOGOUT):
        assert path.startswith("/storefront/portal/")


@pytest.mark.parametrize(
    ("path", "body"), [(path, body) for method, path, body in COOKIE_ROUTES if method == "POST"]
)
def test_every_mutating_cookie_route_is_fenced_by_the_origin_check(
    path: str, body: dict[str, Any] | None
) -> None:
    """The claim the router docstring makes, actually measured — it was FALSE
    when this feature was reviewed, because `PROTECTED_PREFIXES` held `/manage`
    alone and every route here lives under `/storefront/portal`.

    It is not academic: tenants share one registrable domain (`extract_slug`
    reads the leftmost label), so `evil.<base_domain>` is same-SITE with
    `victim.<base_domain>` and `SameSite=Lax` attaches the customer cookie to a
    cross-origin form POST. `logout` and `bell/seen` carry no body at all, which
    makes them CORS-simple: no preflight stands between a forged `<form>` and a
    revoked session or a silently cleared unread badge.

    Parametrised over COOKIE_ROUTES so the next body-less portal POST inherits
    the fence instead of inheriting the gap.
    """
    client, stub = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.post(path, json=body, headers={"origin": "https://evil.localtest.me"})
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"
    # Refused BEFORE the route: the stub logs every handler it reaches, and
    # `resolve_session` deliberately does not log, so an empty list is proof.
    assert stub.calls == []


def test_the_mint_is_fenced_too_and_the_boutiques_own_origin_passes() -> None:
    """The mint reads no cookie, so it is not the CSRF case — but it sits under
    the same prefix and must not have become collateral damage of fencing it."""
    client, stub = _client()
    with client:
        resp = client.post(
            SESSION,
            json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN},
            headers={"origin": "http://bella.localtest.me"},
        )
    assert resp.status_code == 200, resp.text
    assert [name for name, _ in stub.calls] == ["create_session"]

    forged, blocked = _client()
    with forged:
        resp = forged.post(
            SESSION,
            json={"phone": PHONE, "verification_token": VERIFICATION_TOKEN},
            headers={"origin": "https://evil.localtest.me"},
        )
    assert resp.status_code == 403
    assert blocked.calls == []


# --- bookings, detail and the mirrored actions ------------------------------


def test_the_bookings_list_is_split_and_scoped_to_the_session_customer() -> None:
    client, stub = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.get(BOOKINGS)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"upcoming", "past"}
    assert set(body["upcoming"][0]) == {
        "id",
        "starts_at",
        "status",
        "attendance_confirmed_at",
        "appointment_type_name",
        "dress_name",
        "dress_size",
    }
    # The customer id comes from the SESSION and never from the request — there
    # is no parameter a caller could substitute.
    assert stub.calls == [("list_bookings", (TENANT.id, CUSTOMER_ID))]


def test_the_detail_answers_the_tokenized_pages_shape_verbatim() -> None:
    """The mirror guarantee (spec D4): one contract renders both surfaces, so
    they cannot drift into two products."""
    client, stub = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.get(f"{BOOKING}?id={BOOKING_ID}")
    assert resp.status_code == 200
    assert set(resp.json()) == {"booking", "policy", "boutique"}
    assert stub.calls == [("get_booking", (TENANT.id, CUSTOMER_ID, BOOKING_ID))]


@pytest.mark.parametrize(
    ("path", "expected"), [(CONFIRM, "confirm_attendance"), (CANCEL, "cancel")]
)
def test_the_mirrored_actions_delegate_with_the_session_customer(path: str, expected: str) -> None:
    client, stub = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.post(path, json={"id": str(BOOKING_ID)})
    assert resp.status_code == 200
    assert set(resp.json()) == {"booking", "policy", "boutique"}
    assert stub.calls == [(expected, (TENANT.id, CUSTOMER_ID, BOOKING_ID))]


@pytest.mark.parametrize("path", [CONFIRM, CANCEL])
def test_the_mirrored_actions_refuse_an_unknown_field(path: str) -> None:
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.post(path, json={"id": str(BOOKING_ID), "token": "mt-abc"})
    assert resp.status_code == 400


@pytest.mark.parametrize("path", [CONFIRM, CANCEL])
def test_the_mirrored_actions_reject_a_get(path: str) -> None:
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        assert client.get(path).status_code == 405


@pytest.mark.parametrize(
    "error_name",
    ["BookingAlreadyStartedError", "BookingCancelledError", "BookingAwaitingPaymentError"],
)
def test_the_portal_actions_answer_the_same_409_matrix_as_the_token_page(error_name: str) -> None:
    """Same transitions, same guards, same codes — the mirror is a shared code
    path and not a copied table."""
    import app.booking.manage as manage

    error = getattr(manage, error_name)
    client, _ = _client(StubPortalService(error=error()))
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.post(CANCEL, json={"id": str(BOOKING_ID)})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] in {
        "BOOKING_ALREADY_STARTED",
        "BOOKING_CANCELLED",
        "BOOKING_AWAITING_PAYMENT",
    }


def test_a_booking_that_is_not_hers_is_the_house_404() -> None:
    """No cross-customer existence oracle: unknown and not-hers are the same
    body, so a probe learns nothing about another bride's appointments."""
    from app.booking.service import BookingNotFoundError

    client, _ = _client(StubPortalService(error=BookingNotFoundError()))
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        detail = client.get(f"{BOOKING}?id={BOOKING_ID}")
        cancelled = client.post(CANCEL, json={"id": str(BOOKING_ID)})
    assert detail.status_code == cancelled.status_code == 404
    assert detail.json() == cancelled.json()
    assert detail.json()["error"]["code"] == "NOT_FOUND"


# --- the `.ics` download ----------------------------------------------------


def test_the_portal_ics_is_a_calendar_attachment_and_never_cached() -> None:
    """The three headers a download depends on. `no-store` is asserted because
    the handler returns its OWN Response, which discards the router
    dependency's — the exact way this header silently goes missing."""
    client, stub = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.get(f"{ICS}?id={BOOKING_ID}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/calendar; charset=utf-8"
    assert resp.headers["content-disposition"] == 'attachment; filename="appointment.ics"'
    assert resp.headers["cache-control"] == "no-store"
    assert resp.text.startswith("BEGIN:VCALENDAR")
    assert stub.calls == [("get_booking_ics", (TENANT.id, CUSTOMER_ID, BOOKING_ID))]


def test_the_portal_ics_is_a_get_because_the_id_is_not_a_capability() -> None:
    """The one download link in this product that may sit in a URL — the cookie
    is the credential, and on iOS a direct `text/calendar` response is what
    opens the add-to-calendar sheet."""
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        assert client.post(ICS, json={"id": str(BOOKING_ID)}).status_code == 405


def test_a_cancelled_booking_serves_no_calendar_file() -> None:
    """The transition-appropriate 409, not an empty file: an entry for an
    appointment she does not have is worse than a refusal."""
    from app.booking.manage import BookingCancelledError

    client, _ = _client(StubPortalService(error=BookingCancelledError()))
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.get(f"{ICS}?id={BOOKING_ID}")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "BOOKING_CANCELLED"


def test_another_customers_booking_serves_no_calendar_file() -> None:
    from app.booking.service import BookingNotFoundError

    client, _ = _client(StubPortalService(error=BookingNotFoundError()))
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.get(f"{ICS}?id={BOOKING_ID}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# --- the bell ---------------------------------------------------------------


def test_the_bell_never_puts_a_message_body_on_the_wire() -> None:
    """The D6 rule, as a SET EQUALITY on the item keys rather than an absence
    check: `message_log.body` stores masked OTP codes and send-time Hebrew, and
    the client renders every row from `kind` plus these booking facts."""
    client, stub = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.get(BELL)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"unread_count", "items"}
    assert set(body["items"][0]) == {
        "id",
        "kind",
        "created_at",
        "booking_id",
        "starts_at",
        "appointment_type_name",
    }
    assert "body" not in resp.text
    assert stub.calls == [("bell", (TENANT.id, CUSTOMER_ID))]


def test_marking_the_bell_seen_is_a_post_with_no_body() -> None:
    client, stub = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        resp = client.post(BELL_SEEN)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert stub.calls == [("mark_bell_seen", (TENANT.id, CUSTOMER_ID))]


def test_the_bell_is_never_cached() -> None:
    client, _ = _client()
    with client:
        client.cookies.set(CUSTOMER_SESSION_COOKIE, PORTAL_TOKEN)
        assert client.get(BELL).headers["cache-control"] == "no-store"
