"""F52 fast API tests: route wiring, the 401, both roles, the generic 403, the
host-derived tenant and the disclosure walk — a duck-typed FakeDashboardService
on app.state.dashboard_service plus a hardcoded TenantContext resolver, no
database (test_staff_api.py style).

**This is the milestone module.** It is the first point at which the route, the
role gate, the tenant trust path and the disclosure contract are exercised end
to end with no Postgres. `test_dashboard_db.py` runs below the router and swaps
nothing, so the two prove disjoint halves.
"""

import datetime
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.dashboard.schemas import (
    AppointmentTypeCount,
    CustomerMix,
    DashboardResponse,
    ForwardPanel,
    HistoryPanel,
    StatusTotals,
    WeekBucket,
)
from app.dashboard.service import FORWARD_WINDOW_DAYS, HISTORY_WEEKS, history_window
from app.main import NOT_AUTHORIZED_BODY, create_app
from app.models.constants import StaffRole
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})
STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"
PATH = "/manage/dashboard"

# The spec's normative example date: a Friday, jerusalem_day_index == 5.
GENERATED_ON = datetime.date(2026, 7, 31)
WINDOW = history_window(GENERATED_ON)
FITTING_ID = uuid.uuid4()
CONSULT_ID = uuid.uuid4()

# One row. SIX routers now mount prefix="/manage", so a duplicated
# (method, path) would silently win or lose on include order: this table is the
# wiring guard, and a 404 in the walk below is what catches a shadow.
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [("GET", PATH, None)]

# The spec's error table, verbatim — two rows, and NEITHER is raised by a
# service method. The endpoint takes no input, so there is nothing to 400 on,
# and it reads rows that may legitimately not exist, so there is nothing to 404
# on: an empty tenant is a valid all-zero dashboard, not a miss.
#
# CSRF_ORIGIN_MISMATCH is deliberately ABSENT. CsrfOriginMiddleware fences
# MUTATING_METHODS only (csrf.py:48) and this is a GET, so unioning it the way
# test_staff_api.py:458-466 does would assert against a code this route cannot
# produce. test_a_dashboard_read_with_a_mismatched_origin_is_allowed is the leg
# that claim actually rests on.
SPEC_ERROR_CODES = {"NOT_AUTHENTICATED", "NOT_AUTHORIZED"}

# NOT test_storefront_api.FORBIDDEN_KEYS. That frozenset was built for F10's
# manage-only storefront leaks: it contains no customer_id, no phone key and no
# `name`, so borrowing it would prove nothing about THIS endpoint's PII claim —
# and it DOES contain `capacity`, which F52 legitimately ships at
# forward.capacity, so borrowing it would red-fail against this spec's own
# contract.
#
# `capacity` is deliberately permitted (D4: the route is role-gated and GET
# /manage/slots already discloses strictly more — per-slot capacity AND
# remaining — to the same two roles).
# The bare key `name` cannot be forbidden: appointment_types[].name is a TYPE
# label, never a person's. The customer-name key, if one ever appeared, is
# `customer_name`, and it is in the set below.
#
# The SHIPPED /manage spellings matter more than the plausible ones, because
# this set is the tripwire for a future panel rather than for today's payload.
# The bride's phone reaches this console as `customer_phone`
# (`booking/schemas.py:154`), never as the bare `phone` — that one is a request
# field on the anonymous create and lookup bodies. Both are in the set; so is
# `dress_size`, which sits beside `dress_name` on the same owner detail.
DASHBOARD_FORBIDDEN_KEYS = frozenset(
    {
        "customer_id",
        "phone",
        "customer_phone",
        "customer_name",
        "notes",
        "manage_token_hash",
        "email",
        "dress_name",
        "dress_size",
        "seat_index",
    }
)

# Kept in step with test_staff_role_gating.UNKNOWN_ROLE, which owns the tripwire
# asserting it never becomes a real StaffRole. Duplicated because that module
# imports the API modules, so the dependency cannot run the other way.
UNKNOWN_ROLE = "no-such-role"


def _all_keys(node: Any) -> Iterator[str]:
    """Every key at every depth — test_storefront_api.py:643-651, reused."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _all_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _all_keys(item)


def _response() -> DashboardResponse:
    """A FULLY POPULATED payload — twelve real buckets, two appointment types, a
    real cohort and a real forward panel.

    The disclosure walk is only worth running against this: an all-`null`,
    all-empty fixture would pass it vacuously, because a key that never appears
    cannot leak.
    """
    return DashboardResponse(
        generated_on=GENERATED_ON,
        history=HistoryPanel(
            from_date=WINDOW.first_week_start,
            to_date=WINDOW.current_week_start - datetime.timedelta(days=1),
            weeks=[
                WeekBucket(
                    week_start=WINDOW.first_week_start + datetime.timedelta(days=7 * index),
                    bookings=20 + index,
                )
                for index in range(HISTORY_WEEKS)
            ],
            status_totals=StatusTotals(confirmed=12, cancelled=9, no_show=4, completed=88),
            # The UNROUNDED quotient: the console does every bit of the rounding.
            cancellation_rate=9 / 113,
            cancelled_by_customer=7,
            cancelled_by_owner=2,
            no_show_rate=4 / 92,
            appointment_types=[
                AppointmentTypeCount(appointment_type_id=FITTING_ID, name="מדידה", bookings=61),
                AppointmentTypeCount(appointment_type_id=CONSULT_ID, name="ייעוץ", bookings=12),
            ],
            customers=CustomerMix(total=74, new=51, returning=23, repeat_rate=23 / 74),
        ),
        forward=ForwardPanel(
            from_date=GENERATED_ON,
            to_date=GENERATED_ON + datetime.timedelta(days=FORWARD_WINDOW_DAYS - 1),
            capacity=84,
            booked=37,
            utilization=37 / 84,
        ),
    )


class FakeAuthService:
    def __init__(self, role: str = StaffRole.OWNER.value) -> None:
        # The session's tenant_id DELIBERATELY disagrees with the host-resolved
        # TENANT.id. In production the two are equal — get_current_staff resolves
        # the session against the host-derived id under RLS — so a handler that
        # reached for StaffContext.tenant_id would be indistinguishable from a
        # correct one under an agreeing fake. This is what makes
        # test_the_handler_passes_the_host_resolved_tenant able to fail.
        self.staff = StaffContext(
            id=STAFF_ID,
            tenant_id=uuid.uuid4(),
            email="owner@bella.example",
            display_name="Owner",
            role=role,
        )

    async def login(
        self, tenant_id: uuid.UUID, email: str, password: str
    ) -> tuple[StaffContext, str]:
        return self.staff, TOKEN

    async def resolve_session(self, tenant_id: uuid.UUID, token: str) -> StaffContext | None:
        return self.staff if token == TOKEN else None

    async def logout(self, tenant_id: uuid.UUID, token: str) -> None:
        return None


class FakeDashboardService:
    """Duck-typed DashboardService: records the tenant_id it was called with and
    answers one fully populated response."""

    def __init__(self) -> None:
        self.calls: list[uuid.UUID] = []

    async def dashboard(self, tenant_id: uuid.UUID) -> DashboardResponse:
        self.calls.append(tenant_id)
        return _response()


def _client(
    fake: FakeDashboardService, *, authed: bool = True, role: str = StaffRole.OWNER.value
) -> TestClient:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    auth = FakeAuthService(role)
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    # app.state, not dependency_overrides: get_dashboard_service reads app.state
    # directly, the way every other console dependency does.
    app.state.dashboard_service = fake
    app.dependency_overrides[get_auth_service] = lambda: auth
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client


# --- wiring, authentication and the role gate ---


def test_every_route_requires_authentication() -> None:
    fake = FakeDashboardService()
    with _client(fake, authed=False) as client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert fake.calls == []  # the guard fires before any service call


def test_every_route_is_wired_and_reaches_the_service() -> None:
    """Six routers now mount prefix="/manage": a path collision would silently
    shadow, and a 404 here is what catches it."""
    for method, path, body in ROUTES:
        fake = FakeDashboardService()
        with _client(fake) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{method} {path} → {resp.status_code} {resp.text}"
        assert fake.calls, f"{method} {path} never reached the service"


@pytest.mark.parametrize("role", [StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value])
def test_both_roles_get_the_same_dashboard(role: str) -> None:
    """The SMC epic's locked table admits both. There is no per-role projection —
    a shift manager sees the same six answers the owner does."""
    fake = FakeDashboardService()
    with _client(fake, role=role) as client:
        resp = client.get(PATH)
    assert resp.status_code == 200
    assert resp.json() == _response().model_dump(mode="json")


def test_an_unknown_role_is_refused_with_the_exact_generic_body() -> None:
    """Fails closed: a role the enum does not know is not admitted by accident.
    The comparison is against the imported constant, so it pins uniformity with
    every other /manage refusal rather than a literal of its own."""
    fake = FakeDashboardService()
    with _client(fake, role=UNKNOWN_ROLE) as client:
        resp = client.get(PATH)
    assert resp.status_code == 403
    assert resp.json() == NOT_AUTHORIZED_BODY
    assert fake.calls == []  # the gate raises during dependency solving


@pytest.mark.parametrize(("method", "path", "body"), ROUTES, ids=[f"{m}-{p}" for m, p, _ in ROUTES])
def test_no_dashboard_response_is_cached(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """Router-level `_no_store`, so a route added here later cannot forget it.
    This is the console's landing screen: a cached copy in a shared browser
    would show one boutique's numbers to the next person who opens it."""
    fake = FakeDashboardService()
    with _client(fake) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"


# --- the trust path ---


def test_the_handler_passes_the_host_resolved_tenant() -> None:
    """The only place this is observable: `test_dashboard_db.py`'s isolation test
    runs BELOW the router.

    `get_current_tenant(request)` is host-derived — TenantResolutionMiddleware
    binds it from the Host header and nothing else. The other source in hand,
    StaffContext.tenant_id, is session-derived, and F52 is the first /manage
    route with no independent reason to inject `staff` at all, which makes it
    exactly the route where an implementer reaches for the session id.
    """
    fake = FakeDashboardService()
    with _client(fake) as client:
        assert client.get(PATH).status_code == 200
    assert fake.calls == [TENANT.id]


# --- the disclosure walk ---


def test_no_customer_identifier_reaches_the_wire() -> None:
    """Nothing in the payload identifies a customer: `customer_id` is folded away
    in the service and only counts reach the wire (D8)."""
    fake = FakeDashboardService()
    with _client(fake) as client:
        body = client.get(PATH).json()
    keys = set(_all_keys(body))

    assert keys & DASHBOARD_FORBIDDEN_KEYS == set()
    # The walk is not vacuous: every nested collection it has to descend into is
    # populated, so a leaked key would have somewhere to appear.
    assert len(body["history"]["weeks"]) == HISTORY_WEEKS
    assert [row["name"] for row in body["history"]["appointment_types"]] == ["מדידה", "ייעוץ"]
    assert body["history"]["customers"]["total"] > 0
    assert body["forward"]["capacity"] > 0
    # Deliberately present, and named here so a future reader does not "fix" it:
    # D4's posture ships the two forward integers to these two roles on purpose,
    # and `name` is a TYPE label — which is why the bare key cannot be forbidden
    # and `customer_name` is what the set fences instead.
    assert {"capacity", "booked", "name"} <= keys


# --- the error table ---


def test_every_spec_error_code_is_asserted() -> None:
    """Mechanical completeness, re-derived from live responses rather than from a
    literal: F52 raises no error from a service method at all, so there is no
    ERROR_CASES table for the codes to be read off."""
    observed = set()
    fake = FakeDashboardService()
    with _client(fake, authed=False) as client:
        observed.add(client.get(PATH).json()["error"]["code"])
    with _client(fake, role=UNKNOWN_ROLE) as client:
        observed.add(client.get(PATH).json()["error"]["code"])
    assert observed == SPEC_ERROR_CODES


def test_a_dashboard_read_with_a_mismatched_origin_is_allowed() -> None:
    """The leg SPEC_ERROR_CODES rests on, asserted rather than assumed: this is a
    GET and CsrfOriginMiddleware fences MUTATING_METHODS only, so
    CSRF_ORIGIN_MISMATCH is not reachable here. The protection on this route is
    the session cookie and the role gate, alone."""
    fake = FakeDashboardService()
    with _client(fake) as client:
        resp = client.get(PATH, headers={"origin": "http://evil.localtest.me"})
    assert resp.status_code == 200
