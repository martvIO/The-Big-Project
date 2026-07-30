"""F15 fast API tests: route wiring, the owner-role guard, the 401 walk, the
complete error-code table and the post-commit send contract — duck-typed
FakeOwnerBookingService on `app.state`, a hardcoded TenantContext, no database.

Two load-bearing parts. The ROUTES table is the wiring guard: FOUR routers now
mount prefix="/manage", so a duplicated (method, path) would silently shadow and
a 404 here is the only thing that catches it. SPEC_ERROR_CODES is the completeness
guard: there is no error registry, so an unmapped typed error is a bare 500, and
asserting each code against its exact status and house shape is what proves the
four handlers Task 5 registered are actually reachable.

The fake is assigned to `app.state.owner_booking_service` rather than through
`app.dependency_overrides`: `get_owner_booking_service(request)` reads app.state
directly, the way every other booking dependency does.

**The D3 transition table is NOT re-run here**, deliberately. The fake has no
graph, so a legal-pair/illegal-pair walk over this surface would assert the
fake's `if`s rather than the product's. The table lives one layer down in
`test_booking_owner_service.py` — same fast suite, same `make test` — where the
real guards are. What this module owes the graph is that each verb reaches its
OWN service method with the right arguments, and that the 409 it raises leaves
as BOOKING_TRANSITION_INVALID; both are asserted below.
"""

import dataclasses
import datetime
import time
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.booking.owner import (
    BookingTransitionInvalidError,
    CustomerAlreadyBookedError,
    OwnerMutation,
    OwnerResendThrottledError,
)
from app.booking.service import BookingNotFoundError, SlotUnavailableError
from app.booking.slots import Slot
from app.booking.validation import BOOKING_LIST_DEFAULT_LIMIT
from app.errors import DomainValidationError
from app.main import create_app
from app.models.booking import Booking
from app.models.constants import BookingCancelledBy, BookingStatus
from app.models.customer import Customer
from app.storefront.validation import SlotWindowError
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})
STAFF_ID = uuid.uuid4()
TOKEN = "session-token-abc"

BOOKING_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
APPOINTMENT_TYPE_ID = uuid.uuid4()
DRESS_ID = uuid.uuid4()

STARTS_AT = datetime.datetime(2026, 8, 2, 7, 0, tzinfo=datetime.UTC)
CREATED_AT = datetime.datetime(2026, 7, 24, 10, 0, tzinfo=datetime.UTC)
TERMS_ACCEPTED_AT = datetime.datetime(2026, 7, 24, 10, 0, tzinfo=datetime.UTC)

RESCHEDULE_BODY = {"starts_at": "2026-08-03T07:00:00Z"}
PHONE_BODY = {"phone": "050-123-4567"}

# `date` is REQUIRED on the list route, so the bare path is a 400 from the
# RequestValidationError handler — which would red-fail the wiring walk on a
# correctly-built route. The query string is part of the constant for that reason.
LIST_PATH = "/manage/bookings?date=2026-08-02"
DETAIL_PATH = f"/manage/bookings/{BOOKING_ID}"
CONFIRM_PATH = f"{DETAIL_PATH}/confirm"
CANCEL_PATH = f"{DETAIL_PATH}/cancel"
NO_SHOW_PATH = f"{DETAIL_PATH}/no-show"
COMPLETE_PATH = f"{DETAIL_PATH}/complete"
RESCHEDULE_PATH = f"{DETAIL_PATH}/reschedule"
PHONE_PATH = f"{DETAIL_PATH}/phone"
RESEND_PATH = f"{DETAIL_PATH}/resend-link"
SLOTS_PATH = "/manage/slots"

# Every /manage route F15 adds, with a body that passes schema validation — so a
# 401, a 403 or a shadow is attributable to the guard alone.
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", LIST_PATH, None),
    ("GET", DETAIL_PATH, None),
    ("POST", CONFIRM_PATH, None),
    ("POST", CANCEL_PATH, None),
    ("POST", NO_SHOW_PATH, None),
    ("POST", COMPLETE_PATH, None),
    ("POST", RESCHEDULE_PATH, RESCHEDULE_BODY),
    ("POST", PHONE_PATH, PHONE_BODY),
    ("POST", RESEND_PATH, None),
    ("GET", SLOTS_PATH, None),
]

# The spec's error table (D19, as amended by C1), verbatim.
# test_every_spec_error_code_is_asserted checks this set against what the module
# actually exercises, so adding a row to the spec without a test here fails CI.
SPEC_ERROR_CODES = {
    "VALIDATION_ERROR",
    "NOT_FOUND",
    "BOOKING_TRANSITION_INVALID",
    "SLOT_UNAVAILABLE",
    "CUSTOMER_ALREADY_BOOKED",
    "TOO_MANY_ATTEMPTS",
    "NOT_AUTHORIZED",
    "NOT_AUTHENTICATED",
    "CSRF_ORIGIN_MISMATCH",
}


def _booking(**overrides: Any) -> Booking:
    row = Booking(
        tenant_id=TENANT.id,
        customer_id=CUSTOMER_ID,
        appointment_type_id=APPOINTMENT_TYPE_ID,
        starts_at=STARTS_AT,
        seat_index=1,
        status=BookingStatus.CONFIRMED.value,
        terms_version_accepted=3,
        terms_accepted_at=TERMS_ACCEPTED_AT,
        appointment_type_name="מדידת שמלה",
        dress_id=DRESS_ID,
        dress_name="Aurora",
        dress_size="38",
        notes="מגיעה עם אמא",
        manage_token_hash="a" * 64,
    )
    row.id = BOOKING_ID
    row.created_at = CREATED_AT
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _customer() -> Customer:
    row = Customer(tenant_id=TENANT.id, phone="+972501234567", name="נועה")
    row.id = CUSTOMER_ID
    return row


class FakeAuthService:
    def __init__(self, *, role: str = "owner") -> None:
        self.staff = StaffContext(
            id=STAFF_ID,
            tenant_id=TENANT.id,
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


class FakeOwnerBookingService:
    """Duck-typed OwnerBookingService: records every call, raises on demand,
    returns canned ORM rows (instantiable without a database)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.raise_on: dict[str, Exception] = {}
        self.booking = _booking()
        self.changed = True
        self.manage_token: str | None = "raw-token-xyz"
        self.slots: list[Slot] = [Slot(starts_at=STARTS_AT, capacity=2, booked=1)]

    def _record(self, method: str, /, **kwargs: Any) -> None:
        self.calls.append((method, kwargs))
        exc = self.raise_on.get(method)
        if exc is not None:
            raise exc

    def call(self, method: str) -> dict[str, Any]:
        matches = [kwargs for called, kwargs in self.calls if called == method]
        assert len(matches) == 1, f"expected exactly one {method} call, saw {self.calls}"
        return matches[0]

    async def list_day(
        self, tenant_id: uuid.UUID, *, date: datetime.date, offset: int, limit: int
    ) -> tuple[list[Booking], int]:
        self._record("list_day", tenant_id=tenant_id, date=date, offset=offset, limit=limit)
        return [self.booking], 1

    async def detail(self, tenant_id: uuid.UUID, booking_id: uuid.UUID) -> Booking:
        self._record("detail", tenant_id=tenant_id, booking_id=booking_id)
        return self.booking

    async def customers_for(
        self, tenant_id: uuid.UUID, customer_ids: Any
    ) -> dict[uuid.UUID, Customer]:
        self._record("customers_for", tenant_id=tenant_id, customer_ids=set(customer_ids))
        return {CUSTOMER_ID: _customer()}

    async def list_slots(
        self,
        tenant_id: uuid.UUID,
        *,
        from_date: datetime.date | None = None,
        to_date: datetime.date | None = None,
    ) -> list[Slot]:
        self._record("list_slots", tenant_id=tenant_id, from_date=from_date, to_date=to_date)
        return self.slots

    def _mutation(self, method: str, **kwargs: Any) -> OwnerMutation:
        self._record(method, **kwargs)
        return OwnerMutation(
            booking=self.booking, changed=self.changed, manage_token=self.manage_token
        )

    async def confirm(
        self, tenant_id: uuid.UUID, booking_id: uuid.UUID, *, staff: StaffContext
    ) -> OwnerMutation:
        return self._mutation("confirm", tenant_id=tenant_id, booking_id=booking_id, staff=staff)

    async def cancel(
        self, tenant_id: uuid.UUID, booking_id: uuid.UUID, *, staff: StaffContext
    ) -> OwnerMutation:
        return self._mutation("cancel", tenant_id=tenant_id, booking_id=booking_id, staff=staff)

    async def no_show(
        self, tenant_id: uuid.UUID, booking_id: uuid.UUID, *, staff: StaffContext
    ) -> OwnerMutation:
        return self._mutation("no_show", tenant_id=tenant_id, booking_id=booking_id, staff=staff)

    async def complete(
        self, tenant_id: uuid.UUID, booking_id: uuid.UUID, *, staff: StaffContext
    ) -> OwnerMutation:
        return self._mutation("complete", tenant_id=tenant_id, booking_id=booking_id, staff=staff)

    async def reschedule(
        self,
        tenant_id: uuid.UUID,
        booking_id: uuid.UUID,
        *,
        new_starts_at: datetime.datetime,
        staff: StaffContext,
    ) -> OwnerMutation:
        return self._mutation(
            "reschedule",
            tenant_id=tenant_id,
            booking_id=booking_id,
            new_starts_at=new_starts_at,
            staff=staff,
        )

    async def correct_phone(
        self, tenant_id: uuid.UUID, booking_id: uuid.UUID, *, phone: str, staff: StaffContext
    ) -> OwnerMutation:
        return self._mutation(
            "correct_phone", tenant_id=tenant_id, booking_id=booking_id, phone=phone, staff=staff
        )

    async def resend_link(
        self, tenant_id: uuid.UUID, booking_id: uuid.UUID, *, staff: StaffContext
    ) -> OwnerMutation:
        return self._mutation(
            "resend_link", tenant_id=tenant_id, booking_id=booking_id, staff=staff
        )


class FakeComms:
    """Records the post-commit sends. `is_configured` is never consulted here —
    the router awaits the seam and discards, and the seam owns that check."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []

    async def send_confirmation(self, tenant: Any, *, booking: Booking, manage_token: str) -> bool:
        self.sent.append(
            ("send_confirmation", {"tenant": tenant, "booking": booking, "token": manage_token})
        )
        return True

    async def notify_owner_cancel(self, tenant: Any, *, booking: Booking) -> bool:
        self.sent.append(("notify_owner_cancel", {"tenant": tenant, "booking": booking}))
        return True

    async def notify_owner_reschedule(self, tenant: Any, *, booking: Booking) -> bool:
        self.sent.append(("notify_owner_reschedule", {"tenant": tenant, "booking": booking}))
        return True


def _client(
    fake: FakeOwnerBookingService,
    *,
    authed: bool = True,
    role: str = "owner",
    comms: FakeComms | None = None,
) -> TestClient:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    auth = FakeAuthService(role=role)
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    app.state.owner_booking_service = fake
    if comms is not None:
        app.state.booking_comms_service = comms
    app.dependency_overrides[get_auth_service] = lambda: auth
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client


# --- wiring + the two guards ---


def test_every_route_requires_authentication() -> None:
    fake = FakeOwnerBookingService()
    with _client(fake, authed=False) as client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert fake.calls == []  # the guard fires before any service call


def test_every_route_refuses_a_staff_member_who_is_not_the_owner() -> None:
    """Vacuous today — StaffRole has exactly one member — and deliberate: on the
    day E6 adds ASSISTANT, a data change with no code change and no failing test
    would otherwise hand that assistant the bride's phone and notes, the ability
    to cancel any booking, and the ability to re-point a live SMS control link at
    any number with no OTP."""
    fake = FakeOwnerBookingService()
    with _client(fake, role="assistant") as client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 403, f"{method} {path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "NOT_AUTHORIZED"
    assert fake.calls == []


def test_every_route_is_wired_and_reaches_the_service() -> None:
    """Four routers now mount prefix="/manage": a path collision would silently
    shadow, and a non-200 here is what catches it."""
    for method, path, body in ROUTES:
        fake = FakeOwnerBookingService()
        with _client(fake) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{method} {path} → {resp.status_code} {resp.text}"
        assert fake.calls, f"{method} {path} never reached the service"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [pytest.param(*route, id=f"{route[0].lower()}-{route[1]}") for route in ROUTES],
)
def test_no_owner_booking_response_is_ever_cached(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """Every response here names a real person's appointment, phone and free-text
    notes. The header is set on the ROUTER, so a route added later cannot forget
    it — parametrizing over the whole table is what keeps that true."""
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"


# --- the day list ---


def test_the_list_applies_the_documented_defaults() -> None:
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.get(LIST_PATH)
    assert resp.status_code == 200
    assert fake.call("list_day") == {
        "tenant_id": TENANT.id,
        "date": datetime.date(2026, 8, 2),
        "offset": 0,
        "limit": BOOKING_LIST_DEFAULT_LIMIT,
    }
    body = resp.json()
    assert (body["total"], body["offset"], body["limit"]) == (1, 0, BOOKING_LIST_DEFAULT_LIMIT)
    assert body["items"] == [
        {
            "id": str(BOOKING_ID),
            "starts_at": "2026-08-02T07:00:00Z",
            "status": "confirmed",
            "attendance_confirmed_at": None,
            "customer_name": "נועה",
            "appointment_type_name": "מדידת שמלה",
            "dress_name": "Aurora",
        }
    ]


def test_the_list_row_carries_neither_the_phone_nor_the_notes() -> None:
    """D18: the day list is a glance at the day, not a bulk PII export of it."""
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.get(LIST_PATH)
    row = resp.json()["items"][0]
    for key in ("customer_phone", "notes", "manage_token_hash", "manage_link_issued"):
        assert key not in row


def test_the_list_passes_paging_through() -> None:
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.get(
            "/manage/bookings", params={"date": "2026-08-02", "offset": 50, "limit": 10}
        )
    assert resp.status_code == 200
    assert (fake.call("list_day")["offset"], fake.call("list_day")["limit"]) == (50, 10)


def test_a_missing_date_is_a_house_shape_400() -> None:
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.get("/manage/bookings")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_a_malformed_date_is_a_house_shape_400() -> None:
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.get("/manage/bookings", params={"date": "the-second"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_an_enormous_offset_is_refused_at_the_boundary_not_in_the_encoder() -> None:
    """`offset` binds into OFFSET $n::BIGINT. The service clamps too — this is
    the router half, and a 400 is the honest answer to a caller-supplied value
    that could never be a page."""
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.get("/manage/bookings", params={"date": "2026-08-02", "offset": 2**63})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_a_limit_over_the_maximum_is_a_400() -> None:
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.get("/manage/bookings", params={"date": "2026-08-02", "limit": 201})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


# --- the detail ---


def test_the_detail_carries_the_phone_the_notes_and_the_terms_evidence() -> None:
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.get(DETAIL_PATH)
    assert resp.status_code == 200
    assert resp.json() == {
        "id": str(BOOKING_ID),
        "starts_at": "2026-08-02T07:00:00Z",
        "status": "confirmed",
        "attendance_confirmed_at": None,
        "customer_name": "נועה",
        "appointment_type_name": "מדידת שמלה",
        "dress_name": "Aurora",
        "customer_phone": "+972501234567",
        "notes": "מגיעה עם אמא",
        "dress_id": str(DRESS_ID),
        "dress_size": "38",
        "seat_index": 1,
        "created_at": "2026-07-24T10:00:00Z",
        "terms_version_accepted": 3,
        "terms_accepted_at": "2026-07-24T10:00:00Z",
        "cancelled_at": None,
        "cancelled_by": None,
        "manage_link_issued": True,
    }


def test_the_stored_token_hash_never_reaches_the_wire() -> None:
    """It is the stored half of a live control credential; `manage_link_issued`
    is the only thing about it the owner is told."""
    fake = FakeOwnerBookingService()
    fake.booking = _booking(manage_token_hash=None)
    with _client(fake) as client:
        resp = client.get(DETAIL_PATH)
    body = resp.json()
    assert body["manage_link_issued"] is False
    assert "manage_token_hash" not in body
    assert "a" * 64 not in resp.text


def test_the_detail_renders_the_cancel_evidence() -> None:
    cancelled_at = datetime.datetime(2026, 7, 30, 9, 0, tzinfo=datetime.UTC)
    fake = FakeOwnerBookingService()
    fake.booking = _booking(
        status=BookingStatus.CANCELLED.value,
        cancelled_at=cancelled_at,
        cancelled_by=BookingCancelledBy.OWNER.value,
    )
    with _client(fake) as client:
        resp = client.get(DETAIL_PATH)
    body = resp.json()
    assert (body["status"], body["cancelled_by"]) == ("cancelled", "owner")
    assert body["cancelled_at"] == "2026-07-30T09:00:00Z"


# --- the four transitions reach their own service method ---


@pytest.mark.parametrize(
    ("path", "method_name"),
    [
        pytest.param(CONFIRM_PATH, "confirm", id="confirm"),
        pytest.param(CANCEL_PATH, "cancel", id="cancel"),
        pytest.param(NO_SHOW_PATH, "no_show", id="no-show"),
        pytest.param(COMPLETE_PATH, "complete", id="complete"),
    ],
)
def test_each_transition_verb_has_its_own_handler(path: str, method_name: str) -> None:
    """Four verb sub-paths, not one PATCH with a `status` field (D7): cancel is
    guarded on a FUTURE starts_at, sends an SMS and cancels a reminder; no-show
    and complete are guarded on a past one and send nothing; confirm is the undo."""
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.post(path)
    assert resp.status_code == 200
    assert fake.call(method_name) == {
        "tenant_id": TENANT.id,
        "booking_id": BOOKING_ID,
        "staff": FakeAuthService().staff,
    }


def test_every_mutation_answers_the_same_detail_shape() -> None:
    """The ManageBookingResponse precedent: one response type post-action, so
    the console re-renders every state from it instead of branching on which
    call it made — and the list can patch its row with no refetch."""
    detail_keys: set[str] | None = None
    for _, path, body in ROUTES:
        if not path.startswith(DETAIL_PATH) or path == DETAIL_PATH:
            continue
        fake = FakeOwnerBookingService()
        with _client(fake) as client:
            resp = client.post(path, json=body)
        assert resp.status_code == 200, path
        keys = set(resp.json())
        if detail_keys is None:
            detail_keys = keys
        assert keys == detail_keys, path
    assert detail_keys is not None
    assert "manage_link_issued" in detail_keys


def test_reschedule_passes_the_parsed_instant_through() -> None:
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.post(RESCHEDULE_PATH, json=RESCHEDULE_BODY)
    assert resp.status_code == 200
    assert fake.call("reschedule")["new_starts_at"] == datetime.datetime(
        2026, 8, 3, 7, 0, tzinfo=datetime.UTC
    )


def test_a_naive_reschedule_instant_is_a_400() -> None:
    """AwareDatetime, so a timestamp with no offset never reaches the grid
    comparison as an ambiguous wall time."""
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.post(RESCHEDULE_PATH, json={"starts_at": "2026-08-03T07:00:00"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_the_phone_reaches_the_service_unnormalized() -> None:
    """Normalization is the service's — it is the same function the public claim
    uses, and doing it twice is two places for the rule to drift."""
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.post(PHONE_PATH, json=PHONE_BODY)
    assert resp.status_code == 200
    assert fake.call("correct_phone")["phone"] == "050-123-4567"


@pytest.mark.parametrize(
    ("path", "body"),
    [
        pytest.param(RESCHEDULE_PATH, {**RESCHEDULE_BODY, "evil": 1}, id="reschedule"),
        pytest.param(PHONE_PATH, {**PHONE_BODY, "evil": 1}, id="phone"),
    ],
)
def test_an_unknown_body_key_is_a_house_shape_400(path: str, body: dict[str, Any]) -> None:
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.post(path, json=body)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


# --- the owner slot grid ---


def test_the_owner_slot_grid_carries_capacity_and_remaining() -> None:
    """The storefront's projection drops both, and `availability-slot-engine.md`
    argues at length why. That fence is about anonymous visitors; an owner
    picking a reschedule target needs to know she is taking the last place (D6)."""
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.get(SLOTS_PATH, params={"from": "2026-08-02", "to": "2026-08-03"})
    assert resp.status_code == 200
    assert resp.json() == {
        "slots": [{"starts_at": "2026-08-02T07:00:00Z", "capacity": 2, "remaining": 1}]
    }
    assert fake.call("list_slots") == {
        "tenant_id": TENANT.id,
        "from_date": datetime.date(2026, 8, 2),
        "to_date": datetime.date(2026, 8, 3),
    }


def test_the_owner_slot_window_defaults_to_the_service() -> None:
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.get(SLOTS_PATH)
    assert resp.status_code == 200
    assert fake.call("list_slots") == {
        "tenant_id": TENANT.id,
        "from_date": None,
        "to_date": None,
    }


# --- the post-commit sends (D11) ---


def test_owner_cancel_texts_the_customer_after_the_commit() -> None:
    fake = FakeOwnerBookingService()
    comms = FakeComms()
    with _client(fake, comms=comms) as client:
        resp = client.post(CANCEL_PATH)
    assert resp.status_code == 200
    assert [name for name, _ in comms.sent] == ["notify_owner_cancel"]
    assert comms.sent[0][1]["booking"] is fake.booking


def test_reschedule_texts_the_new_time_after_the_commit() -> None:
    fake = FakeOwnerBookingService()
    comms = FakeComms()
    with _client(fake, comms=comms) as client:
        resp = client.post(RESCHEDULE_PATH, json=RESCHEDULE_BODY)
    assert resp.status_code == 200
    assert [name for name, _ in comms.sent] == ["notify_owner_reschedule"]


@pytest.mark.parametrize(
    ("path", "body"),
    [
        pytest.param(PHONE_PATH, PHONE_BODY, id="phone"),
        pytest.param(RESEND_PATH, None, id="resend"),
    ],
)
def test_the_rotation_routes_send_the_confirmation_with_the_minted_token(
    path: str, body: dict[str, Any] | None
) -> None:
    """sha256 is one-way, so the raw token minted INSIDE the transaction travels
    out on the mutation result or the message has no link to carry."""
    fake = FakeOwnerBookingService()
    comms = FakeComms()
    with _client(fake, comms=comms) as client:
        resp = client.post(path, json=body)
    assert resp.status_code == 200
    assert [name for name, _ in comms.sent] == ["send_confirmation"]
    assert comms.sent[0][1]["token"] == "raw-token-xyz"


@pytest.mark.parametrize(
    "path",
    [
        pytest.param(CONFIRM_PATH, id="confirm"),
        pytest.param(NO_SHOW_PATH, id="no-show"),
        pytest.param(COMPLETE_PATH, id="complete"),
    ],
)
def test_no_show_completed_and_confirmed_text_nobody(path: str) -> None:
    """D13: there is no template, and texting a bride «you did not show up» is a
    product decision orders of magnitude larger than a status field."""
    fake = FakeOwnerBookingService()
    comms = FakeComms()
    with _client(fake, comms=comms) as client:
        resp = client.post(path)
    assert resp.status_code == 200
    assert comms.sent == []


@pytest.mark.parametrize(
    ("path", "body"),
    [
        pytest.param(CANCEL_PATH, None, id="cancel"),
        pytest.param(RESCHEDULE_PATH, RESCHEDULE_BODY, id="reschedule"),
    ],
)
def test_a_no_op_mutation_sends_nothing(path: str, body: dict[str, Any] | None) -> None:
    """A repeat of the same transition (D3 step 2) and a reschedule to the instant
    the booking already holds (D5 step 3) are both 200s in which nothing happened
    — so nothing is texted."""
    fake = FakeOwnerBookingService()
    fake.changed = False
    comms = FakeComms()
    with _client(fake, comms=comms) as client:
        resp = client.post(path, json=body)
    assert resp.status_code == 200
    assert comms.sent == []


def test_a_correction_that_minted_no_token_sends_nothing() -> None:
    fake = FakeOwnerBookingService()
    fake.manage_token = None
    comms = FakeComms()
    with _client(fake, comms=comms) as client:
        resp = client.post(PHONE_PATH, json=PHONE_BODY)
    assert resp.status_code == 200
    assert comms.sent == []


# --- the complete error-code table ---


@dataclasses.dataclass(frozen=True)
class ErrorCase:
    """One row of D19's error table: the service method that raises, the route
    that reaches it, and the status + code the handler must produce."""

    method_name: str
    verb: str
    path: str
    body: dict[str, Any] | None
    error: Exception
    status: int
    code: str


ERROR_CASES: list[ErrorCase] = [
    ErrorCase("detail", "GET", DETAIL_PATH, None, BookingNotFoundError(), 404, "NOT_FOUND"),
    ErrorCase(
        "no_show",
        "POST",
        NO_SHOW_PATH,
        None,
        BookingTransitionInvalidError("confirmed -> no_show before starts_at"),
        409,
        "BOOKING_TRANSITION_INVALID",
    ),
    ErrorCase(
        "reschedule",
        "POST",
        RESCHEDULE_PATH,
        RESCHEDULE_BODY,
        SlotUnavailableError(),
        409,
        "SLOT_UNAVAILABLE",
    ),
    ErrorCase(
        "reschedule",
        "POST",
        RESCHEDULE_PATH,
        RESCHEDULE_BODY,
        CustomerAlreadyBookedError(),
        409,
        "CUSTOMER_ALREADY_BOOKED",
    ),
    ErrorCase(
        "resend_link",
        "POST",
        RESEND_PATH,
        None,
        OwnerResendThrottledError(),
        429,
        "TOO_MANY_ATTEMPTS",
    ),
    # The service normalizes, so a malformed number raises out of
    # `normalize_israeli_mobile` rather than off a schema bound — and that is a
    # DomainValidationError, answered by the handler bound to the base.
    ErrorCase(
        "correct_phone",
        "POST",
        PHONE_PATH,
        PHONE_BODY,
        DomainValidationError("Enter a valid Israeli mobile number."),
        400,
        "VALIDATION_ERROR",
    ),
    # `to < from` on the owner grid. SlotWindowError subclasses
    # DomainValidationError, so the handler bound to the BASE already answers it
    # — this row is what proves that claim rather than assuming it.
    ErrorCase(
        "list_slots",
        "GET",
        SLOTS_PATH,
        None,
        SlotWindowError("`to` must not precede `from`."),
        400,
        "VALIDATION_ERROR",
    ),
    # NOT_AUTHORIZED needs a row of its own: the completeness check below reads
    # ERROR_CASES, not every assertion in the module, so the role-guard walk
    # above would not feed the set.
    ErrorCase(
        "detail",
        "GET",
        DETAIL_PATH,
        None,
        AssertionError("unreachable — the guard fires first"),
        403,
        "NOT_AUTHORIZED",
    ),
]


@pytest.mark.parametrize("case", ERROR_CASES, ids=[case.code for case in ERROR_CASES])
def test_every_domain_error_maps_to_its_status_and_house_shape(case: ErrorCase) -> None:
    """A forgotten handler registration returns 500, not the documented status —
    and there is no error registry, so every one of F15's three new codes is a
    bare 500 until its handler exists."""
    fake = FakeOwnerBookingService()
    # The role guard is the one row that cannot be provoked from a service raise:
    # it fires before the handler is reached, which is the point of it.
    role = "assistant" if case.code == "NOT_AUTHORIZED" else "owner"
    if role == "owner":
        fake.raise_on[case.method_name] = case.error
    with _client(fake, role=role) as client:
        resp = client.request(case.verb, case.path, json=case.body)
    assert resp.status_code == case.status
    body = resp.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == case.code
    assert body["error"]["message"]


def test_a_failed_mutation_sends_nothing() -> None:
    """The send is post-commit and the commit did not happen."""
    fake = FakeOwnerBookingService()
    fake.raise_on["cancel"] = BookingTransitionInvalidError("cancelled -> cancelled")
    comms = FakeComms()
    with _client(fake, comms=comms) as client:
        resp = client.post(CANCEL_PATH)
    assert resp.status_code == 409
    assert comms.sent == []


def test_the_throttle_reuses_the_existing_too_many_attempts_body() -> None:
    """A fourth spelling of "too many attempts" would be a new code for the same
    fact (D10)."""
    fake = FakeOwnerBookingService()
    fake.raise_on["resend_link"] = OwnerResendThrottledError()
    with _client(fake) as client:
        resp = client.post(RESEND_PATH)
    assert resp.status_code == 429
    assert resp.json() == {
        "error": {"code": "TOO_MANY_ATTEMPTS", "message": "Too many attempts. Try again later."}
    }


def test_every_spec_error_code_is_asserted() -> None:
    """Mechanical completeness: a row added to the spec's error table without a
    test here fails immediately, rather than shipping as a 500."""
    covered = {case.code for case in ERROR_CASES}
    covered |= {"NOT_AUTHENTICATED", "CSRF_ORIGIN_MISMATCH"}
    assert covered == SPEC_ERROR_CODES


# --- CSRF origin middleware (already covers every mutating /manage route) ---


def test_a_mutating_owner_booking_request_from_a_foreign_origin_is_403() -> None:
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.post(CANCEL_PATH, headers={"origin": "http://evil.localtest.me"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"
    assert fake.calls == []


def test_an_owner_booking_read_from_a_foreign_origin_is_allowed() -> None:
    fake = FakeOwnerBookingService()
    with _client(fake) as client:
        resp = client.get(DETAIL_PATH, headers={"origin": "http://evil.localtest.me"})
    assert resp.status_code == 200
