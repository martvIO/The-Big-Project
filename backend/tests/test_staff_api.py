"""F51 fast API tests: route wiring, 401s, the owner-only refusal, house-shape
validation 400s, the complete error-code table and the no-store header — a
duck-typed FakeStaffService on app.state.staff_service plus a hardcoded
TenantContext resolver, no database (test_catalog_api.py style).

**This is the milestone module.** It is the first point at which the whole
four-route table, the three new exception handlers and the owner-only gate are
exercised end to end with no Postgres. The error-code table is the load-bearing
part: there is no error registry, so an unmapped typed error is a bare 500, and
asserting each code against its exact status and house shape is the only thing
that catches it.
"""

import dataclasses
import time
import uuid
from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.schemas import (
    MAX_DISPLAY_NAME_LENGTH,
    MAX_PASSWORD_LENGTH,
    MIN_STAFF_PASSWORD_LENGTH,
    StaffMember,
)
from app.auth.service import StaffContext
from app.auth.staff import (
    DuplicateEmailError,
    LastOwnerRequiredError,
    StaffNotFoundError,
    StaffPhotoPresign,
    StaffSelfManageError,
)
from app.catalog.service import MediaPresignThrottledError
from app.errors import DomainValidationError
from app.main import NOT_AUTHORIZED_BODY, create_app
from app.models.constants import StaffRole
from app.models.staff_user import StaffUser
from app.storage.base import MediaNotConfiguredError
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})
STAFF_ID = uuid.uuid4()
TARGET_ID = uuid.uuid4()
TOKEN = "session-token-abc"
CREATED_AT = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)

LIST_PATH = "/manage/staff"
DETAIL_PATH = f"/manage/staff/{TARGET_ID}"
SELF_PATH = f"/manage/staff/{STAFF_ID}"

GOOD_PASSWORD = "a-long-enough-pw"
CREATE_BODY: dict[str, Any] = {
    "email": "Dana@Bella.Example",
    "display_name": "דנה",
    "role": StaffRole.SHIFT_MANAGER.value,
    "password": GOOD_PASSWORD,
}
PATCH_BODY: dict[str, Any] = {"display_name": "דנה כהן"}

# Every /manage route this feature adds, with a body that passes schema
# validation — so 401 (and CSRF) failures are attributable to the guard alone.
# FIVE routers now mount prefix="/manage", so a duplicated (method, path) would
# silently win or lose on include order: this table is the wiring guard.
ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", LIST_PATH, None),
    ("POST", LIST_PATH, CREATE_BODY),
    ("PATCH", DETAIL_PATH, PATCH_BODY),
    ("DELETE", DETAIL_PATH, None),
]

# The spec's error table, verbatim. test_every_spec_error_code_is_asserted checks
# this set against what the module actually exercises, so adding a row to the
# spec without a test here fails CI.
SPEC_ERROR_CODES = {
    "VALIDATION_ERROR",
    "NOT_FOUND",
    "DUPLICATE_EMAIL",
    "LAST_OWNER_REQUIRED",
    "STAFF_SELF_MANAGE",
    "NOT_AUTHENTICATED",
    "CSRF_ORIGIN_MISMATCH",
    "NOT_AUTHORIZED",
}

# Kept in step with test_staff_role_gating.UNKNOWN_ROLE, which owns the tripwire
# asserting it never becomes a real StaffRole. Duplicated because that module
# imports the API modules, so the dependency cannot run the other way.
UNKNOWN_ROLE = "no-such-role"

# The wire shape of a staff row, asserted by SET EQUALITY on every path that
# emits one. Set equality and not a subset check, deliberately: this payload
# carries an employee's phone number and a signed URL to her face, so a twelfth
# key arriving unreviewed is the failure worth catching — in EITHER direction. A
# field removed silently breaks the console; a field added silently widens what
# the platform discloses about a member of staff.
STAFF_MEMBER_KEYS = {
    "id",
    "email",
    "display_name",
    "role",
    "created_at",
    "phone",
    "start_date",
    "last_day",
    "shift_manager_eligible",
    "photo_url",
    "photo_confirmed_at",
}


def _row(
    *,
    staff_id: uuid.UUID | None = None,
    email: str = "dana@bella.example",
    display_name: str = "דנה",
    role: str = StaffRole.SHIFT_MANAGER.value,
) -> StaffUser:
    return StaffUser(
        id=staff_id or TARGET_ID,
        tenant_id=TENANT.id,
        email=email,
        password_hash="$argon2id$never-on-the-wire",
        display_name=display_name,
        role=role,
        # Set explicitly: created_at rides a server_default, so an unflushed ORM
        # instance carries None and StaffMember would refuse it. F38's
        # shift_manager_eligible is here for exactly the same reason — NOT NULL
        # DEFAULT false in the database, None on an instance that never went
        # through it.
        shift_manager_eligible=False,
        created_at=CREATED_AT,
    )


class FakeAuthService:
    def __init__(self, role: str = StaffRole.OWNER.value) -> None:
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


class FakeStaffService:
    """Duck-typed StaffService: records every call, raises on demand, returns
    canned ORM rows (instantiable without a database)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.raise_on: dict[str, Exception] = {}

    def _record(self, name: str, **kwargs: Any) -> None:
        if name in self.raise_on:
            raise self.raise_on[name]
        self.calls.append((name, kwargs))

    def call(self, name: str) -> dict[str, Any]:
        return next(payload for called, payload in self.calls if called == name)

    async def list_staff(self, tenant_id: uuid.UUID) -> list[StaffUser]:
        self._record("list_staff", tenant_id=tenant_id)
        return [_row(staff_id=STAFF_ID, role=StaffRole.OWNER.value), _row()]

    async def create(self, tenant_id: uuid.UUID, **kwargs: Any) -> StaffUser:
        self._record("create", tenant_id=tenant_id, **kwargs)
        return _row()

    async def update(self, tenant_id: uuid.UUID, staff_id: uuid.UUID, **kwargs: Any) -> StaffUser:
        self._record("update", tenant_id=tenant_id, staff_id=staff_id, **kwargs)
        return _row(staff_id=staff_id)

    async def deactivate(self, tenant_id: uuid.UUID, staff_id: uuid.UUID, **kwargs: Any) -> None:
        self._record("deactivate", tenant_id=tenant_id, staff_id=staff_id, **kwargs)

    async def presign_photo(
        self, tenant_id: uuid.UUID, staff_id: uuid.UUID, **kwargs: Any
    ) -> StaffPhotoPresign:
        self._record("presign_photo", tenant_id=tenant_id, staff_id=staff_id, **kwargs)
        return StaffPhotoPresign(
            url="https://bucket.example/",
            fields={"key": "tenants/t/staff/s/photo/p.jpg", "policy": "opaque"},
            expires_in=300,
            max_bytes=kwargs["byte_size"],
        )

    async def confirm_photo(
        self, tenant_id: uuid.UUID, staff_id: uuid.UUID, **kwargs: Any
    ) -> StaffUser:
        self._record("confirm_photo", tenant_id=tenant_id, staff_id=staff_id, **kwargs)
        return _row(staff_id=staff_id)

    async def delete_photo(
        self, tenant_id: uuid.UUID, staff_id: uuid.UUID, **kwargs: Any
    ) -> StaffUser:
        self._record("delete_photo", tenant_id=tenant_id, staff_id=staff_id, **kwargs)
        return _row(staff_id=staff_id)


def _client(
    fake: FakeStaffService, *, authed: bool = True, role: str = StaffRole.OWNER.value
) -> TestClient:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    auth = FakeAuthService(role)
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    # app.state, not dependency_overrides: get_staff_service reads app.state
    # directly, the way every other console dependency does.
    app.state.staff_service = fake
    app.dependency_overrides[get_auth_service] = lambda: auth
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client


# --- wiring, authentication and the owner-only gate ---


def test_every_route_requires_authentication() -> None:
    fake = FakeStaffService()
    with _client(fake, authed=False) as client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert fake.calls == []  # the guard fires before any service call


def test_every_route_is_wired_and_reaches_the_service() -> None:
    """Five routers now mount prefix="/manage": a path collision would silently
    shadow, and a 404 here is what catches it."""
    for method, path, body in ROUTES:
        fake = FakeStaffService()
        with _client(fake) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{method} {path} → {resp.status_code} {resp.text}"
        assert fake.calls, f"{method} {path} never reached the service"


def test_a_shift_manager_is_refused_on_every_route() -> None:
    """The SMC epic's locked table names exactly two owner-only surfaces: this
    whole router and POST /manage/terms. The gate is router-level, so a route
    added here later cannot forget it.

    The comparison is against the imported constant, so it pins uniformity across
    routes rather than the literals; the code and the generic message are pinned
    once in test_staff_role_gating.test_the_not_authorized_contract_is_pinned_by_literal.
    """
    fake = FakeStaffService()
    with _client(fake, role=StaffRole.SHIFT_MANAGER.value) as client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 403, f"{method} {path} → {resp.status_code}"
            assert resp.json() == NOT_AUTHORIZED_BODY
    assert fake.calls == []  # the gate raises during dependency solving


def test_an_unknown_role_is_refused_on_every_route() -> None:
    """Fails closed: a role the enum does not know is not admitted by accident."""
    fake = FakeStaffService()
    with _client(fake, role=UNKNOWN_ROLE) as client:
        for method, path, body in ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 403, f"{method} {path} → {resp.status_code}"
            assert resp.json() == NOT_AUTHORIZED_BODY
    assert fake.calls == []


@pytest.mark.parametrize(("method", "path", "body"), ROUTES, ids=[f"{m}-{p}" for m, p, _ in ROUTES])
def test_no_staff_response_is_cached(method: str, path: str, body: dict[str, Any] | None) -> None:
    """Router-level `_no_store`, so a route added later cannot forget it. Every
    response here names a real staffer's address and role."""
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"


# --- no password material on the wire ---


def test_the_staff_member_model_has_no_password_field_at_all() -> None:
    """Absent BY CONSTRUCTION rather than filtered: nothing has to remember to
    strip it, and the same goes for deleted_at (every listed row is live)."""
    assert "password_hash" not in StaffMember.model_fields
    assert "password" not in StaffMember.model_fields
    assert "deleted_at" not in StaffMember.model_fields


@pytest.mark.parametrize(("method", "path", "body"), ROUTES, ids=[f"{m}-{p}" for m, p, _ in ROUTES])
def test_no_success_body_carries_password_material(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 200
    text = resp.text.lower()
    assert "password" not in text
    assert "argon2" not in text


# --- the create contract ---


def test_create_forwards_the_address_verbatim_and_lets_the_service_lowercase_it() -> None:
    """Recorded honestly, because the plan's two halves disagreed: the lowercase
    lives in StaffService, NOT here. One layer owns the invariant — the one whose
    write it protects — and putting a second copy in the router would be a rule
    with two homes and no test proving they agree.

    What proves the lowercase is test_staff_service (the unit) and
    test_staff_management_db (the login seam end to end). What this asserts is
    that the router does not mangle the address on the way through — AND the
    thing that makes the service's `.lower()` load-bearing rather than
    decorative: pydantic's EmailStr normalizes only the DOMAIN, so
    `Dana@Bella.Example` arrives as `Dana@bella.example`. A capitalised local
    part is precisely the row that can never sign in, and the schema does not
    save us from it.
    """
    fake = FakeStaffService()
    with _client(fake) as client:
        assert client.post(LIST_PATH, json=CREATE_BODY).status_code == 200
    forwarded = fake.call("create")["email"]
    assert forwarded == "Dana@bella.example"
    assert forwarded != forwarded.lower()


def test_create_passes_the_acting_staff_through_as_the_actor() -> None:
    """The acting id is what the self-guard compares and what every audit row
    carries; a handler that dropped it would silently un-guard both."""
    fake = FakeStaffService()
    with _client(fake) as client:
        client.post(LIST_PATH, json=CREATE_BODY)
    assert fake.call("create")["actor"].id == STAFF_ID


def test_list_answers_a_bare_array_not_an_envelope() -> None:
    """GET /manage/appointment-types is the in-repo precedent for a small list; a
    boutique's staff table is single-digit, and paging controls nobody can reach
    are the un-lazy thing (spec D6)."""
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.get(LIST_PATH)
    body = resp.json()
    assert isinstance(body, list)
    assert {row["role"] for row in body} == {
        StaffRole.OWNER.value,
        StaffRole.SHIFT_MANAGER.value,
    }
    assert set(body[0]) == STAFF_MEMBER_KEYS


def test_patch_forwards_every_optional_field_including_current_password() -> None:
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.patch(
            SELF_PATH,
            json={
                "display_name": "Owner",
                "role": StaffRole.OWNER.value,
                "password": GOOD_PASSWORD,
                "current_password": "the-old-one",
            },
        )
    assert resp.status_code == 200
    call = fake.call("update")
    assert call["staff_id"] == STAFF_ID
    assert call["display_name"] == "Owner"
    assert call["role"] == StaffRole.OWNER.value
    assert call["password"] == GOOD_PASSWORD
    assert call["current_password"] == "the-old-one"


def test_an_omitted_patch_field_reaches_the_service_as_none() -> None:
    """Not as a missing key and not as an empty string — the service's no-op rule
    reads None to mean "not supplied"."""
    fake = FakeStaffService()
    with _client(fake) as client:
        client.patch(DETAIL_PATH, json=PATCH_BODY)
    call = fake.call("update")
    assert call["role"] is None
    assert call["password"] is None
    assert call["current_password"] is None


def test_delete_answers_the_house_ok_response() -> None:
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.delete(DETAIL_PATH)
    assert resp.json() == {"ok": True}


# --- the complete error-code table ---


@dataclasses.dataclass(frozen=True)
class ErrorCase:
    """One row of the spec's error table: the service method that raises, the
    route that reaches it, and the status + code the handler must produce."""

    method_name: str
    verb: str
    path: str
    body: dict[str, Any] | None
    error: Exception
    status: int
    code: str


ERROR_CASES: list[ErrorCase] = [
    ErrorCase(
        "create", "POST", LIST_PATH, CREATE_BODY, DuplicateEmailError(), 409, "DUPLICATE_EMAIL"
    ),
    ErrorCase(
        "update",
        "PATCH",
        DETAIL_PATH,
        PATCH_BODY,
        LastOwnerRequiredError(),
        409,
        "LAST_OWNER_REQUIRED",
    ),
    ErrorCase(
        "deactivate",
        "DELETE",
        DETAIL_PATH,
        None,
        LastOwnerRequiredError(),
        409,
        "LAST_OWNER_REQUIRED",
    ),
    ErrorCase(
        "update", "PATCH", SELF_PATH, PATCH_BODY, StaffSelfManageError(), 409, "STAFF_SELF_MANAGE"
    ),
    ErrorCase(
        "deactivate", "DELETE", SELF_PATH, None, StaffSelfManageError(), 409, "STAFF_SELF_MANAGE"
    ),
    ErrorCase("update", "PATCH", DETAIL_PATH, PATCH_BODY, StaffNotFoundError(), 404, "NOT_FOUND"),
    ErrorCase("deactivate", "DELETE", DETAIL_PATH, None, StaffNotFoundError(), 404, "NOT_FOUND"),
    ErrorCase(
        "update",
        "PATCH",
        SELF_PATH,
        {"password": GOOD_PASSWORD},
        DomainValidationError("current_password is required"),
        400,
        "VALIDATION_ERROR",
    ),
]


@pytest.mark.parametrize("case", ERROR_CASES, ids=[f"{c.code}-{c.verb}" for c in ERROR_CASES])
def test_every_domain_error_maps_to_its_status_and_house_shape(case: ErrorCase) -> None:
    """A forgotten handler registration returns 500, not the documented status.
    StaffNotFoundError deliberately has NO handler of its own — it subclasses the
    app/errors.py base, and this is what proves the inheritance actually resolves."""
    fake = FakeStaffService()
    fake.raise_on[case.method_name] = case.error
    with _client(fake) as client:
        resp = client.request(case.verb, case.path, json=case.body)
    assert resp.status_code == case.status
    body = resp.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == case.code
    assert body["error"]["message"]


def test_the_last_owner_body_names_no_count() -> None:
    """Spec D7: how many owners exist is not the owner's problem to solve, and
    naming it would leak the tenant's staffing to a probe. The word "owner"
    itself is fine and load-bearing here — unlike the generic 403 body, this
    message is ABOUT the owner role, and hiding it would leave a refusal that
    explains nothing."""
    fake = FakeStaffService()
    fake.raise_on["deactivate"] = LastOwnerRequiredError()
    with _client(fake) as client:
        message = client.delete(DETAIL_PATH).json()["error"]["message"]
    assert not any(character.isdigit() for character in message), message


def test_every_spec_error_code_is_asserted() -> None:
    """Mechanical completeness: a row added to the spec's error table without a
    test here fails immediately, rather than shipping as a 500."""
    covered = {case.code for case in ERROR_CASES}
    # Hand-unioned, not ErrorCase rows: all three are raised during dependency
    # solving or in middleware, never by a service method, so no ErrorCase can
    # express them. Their tests are the walks above.
    covered |= {"NOT_AUTHENTICATED", "CSRF_ORIGIN_MISMATCH", "NOT_AUTHORIZED"}
    assert covered == SPEC_ERROR_CODES


# --- house-shape request validation ---


@pytest.mark.parametrize(
    ("verb", "path", "body"),
    [
        pytest.param("POST", LIST_PATH, {**CREATE_BODY, "display_name": ""}, id="empty-name"),
        # The schema is the trust boundary, and `min_length=1` alone admits this:
        # a whitespace name renders as an empty <bdi> in the console, findable
        # only by its email. Both verbs, because PATCH can blank an existing one.
        pytest.param("POST", LIST_PATH, {**CREATE_BODY, "display_name": "   "}, id="blank-name"),
        pytest.param("PATCH", DETAIL_PATH, {"display_name": "   "}, id="blank-name-patch"),
        pytest.param(
            "POST",
            LIST_PATH,
            {**CREATE_BODY, "display_name": "x" * (MAX_DISPLAY_NAME_LENGTH + 1)},
            id="long-name",
        ),
        pytest.param(
            "POST",
            LIST_PATH,
            {**CREATE_BODY, "password": "x" * (MIN_STAFF_PASSWORD_LENGTH - 1)},
            id="short-password",
        ),
        pytest.param(
            "POST",
            LIST_PATH,
            {**CREATE_BODY, "password": "x" * (MAX_PASSWORD_LENGTH + 1)},
            id="huge-password",
        ),
        pytest.param("POST", LIST_PATH, {**CREATE_BODY, "role": UNKNOWN_ROLE}, id="unknown-role"),
        pytest.param("POST", LIST_PATH, {**CREATE_BODY, "email": "not-an-email"}, id="bad-email"),
        pytest.param("POST", LIST_PATH, {**CREATE_BODY, "evil": 1}, id="unknown-key-create"),
        pytest.param("PATCH", DETAIL_PATH, {**PATCH_BODY, "evil": 1}, id="unknown-key-patch"),
        pytest.param(
            "PATCH", DETAIL_PATH, {"email": "moved@bella.example"}, id="email-not-patchable"
        ),
        pytest.param("PATCH", DETAIL_PATH, {"role": UNKNOWN_ROLE}, id="unknown-role-patch"),
        pytest.param("PATCH", DETAIL_PATH, {"password": "short"}, id="short-password-patch"),
    ],
)
def test_a_bad_body_is_a_house_shape_400_and_never_reaches_the_service(
    verb: str, path: str, body: dict[str, Any]
) -> None:
    """400, not 422 — main.py normalizes RequestValidationError platform-wide.
    `email` on PATCH is refused by ForbidExtraModel, which is the schema half of
    spec D5: a login identity must not move under a live session."""
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.request(verb, path, json=body)
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_an_unknown_role_never_reaches_the_database_check() -> None:
    """`role` is typed as StaffRole, so the DB's CHECK is the second line of
    defence and not the first — a 400 at the boundary, never a 500 from Postgres.

    ⚠ This probe was the literal 'reception' until F57, chosen because 0011 named
    it as a role that did not exist yet. F57 added it, and the test went red
    asserting the opposite of its own name — a real 400 became a real 201. That
    is precisely the failure test_staff_role_gating.py's UNKNOWN_ROLE sentinel and
    its tripwire exist to prevent, and the repair is to use the sentinel, which
    this module already imports and uses two cases above."""
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.post(LIST_PATH, json={**CREATE_BODY, "role": UNKNOWN_ROLE})
    assert resp.status_code == 400
    assert fake.calls == []


@pytest.mark.parametrize(
    "role",
    [StaffRole.RECEPTION.value, StaffRole.SALES_ASSISTANT.value, StaffRole.SEAMSTRESS.value],
)
def test_the_three_floor_roles_are_accepted_on_create_and_on_patch(role: str) -> None:
    """F57 adds ZERO production code to app/auth/ and this is the proof, because
    "widening the enum widens nothing" cuts both ways and a reviewer will ask.

    `CreateStaffRequest.role: StaffRole` and `UpdateStaffRequest.role:
    StaffRole | None` are typed as the enum precisely so an unknown value is a
    house 400 at the boundary and can never reach 0011's CHECK
    (`auth/schemas.py:65-67`). Widening the enum therefore widens both request
    schemas with no edit — asserted end to end over HTTP rather than assumed.
    """
    fake = FakeStaffService()
    with _client(fake) as client:
        created = client.post(LIST_PATH, json={**CREATE_BODY, "role": role})
        patched = client.patch(DETAIL_PATH, json={"role": role})

    assert created.status_code == 200, created.text
    assert patched.status_code == 200, patched.text
    # The enum member reaches the service, not the raw string — so this also
    # fails if a future schema change starts coercing it to something else.
    assert fake.call("create")["role"] == role
    assert fake.call("update")["role"] == role


def test_a_malformed_staff_id_is_a_400_not_a_500() -> None:
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.delete("/manage/staff/not-a-uuid")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


# --- CSRF ---


def test_a_mutating_staff_request_with_a_mismatched_origin_is_403() -> None:
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.post(
            LIST_PATH, json=CREATE_BODY, headers={"origin": "http://evil.localtest.me"}
        )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"
    assert fake.calls == []


def test_patch_and_delete_are_both_inside_the_csrf_fence() -> None:
    """Both verbs are in CsrfOriginMiddleware.MUTATING_METHODS. Asserted rather
    than assumed: the console's dev proxy is cross-origin, so a verb outside the
    fence would be a live forgery surface."""
    for verb, path, body in (("PATCH", DETAIL_PATH, PATCH_BODY), ("DELETE", DETAIL_PATH, None)):
        fake = FakeStaffService()
        with _client(fake) as client:
            resp = client.request(
                verb, path, json=body, headers={"origin": "http://evil.localtest.me"}
            )
        assert resp.status_code == 403, verb
        assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH", verb
        assert fake.calls == []


def test_the_staff_list_read_with_a_mismatched_origin_is_allowed() -> None:
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.get(LIST_PATH, headers={"origin": "http://evil.localtest.me"})
    assert resp.status_code == 200


# --- F38: the profile fields on the wire ---


def test_every_path_that_emits_a_staff_row_emits_the_same_eleven_keys() -> None:
    """One `_member` builder, asserted on all three paths that reach it.

    Without this, `photo_url` signed on the list and absent from the PATCH
    response is a defect that renders correctly until the moment the owner
    changes a photo and the row goes blank — and no single-path test would
    notice, because each path is individually consistent with itself."""
    fake = FakeStaffService()
    with _client(fake) as client:
        assert set(client.get(LIST_PATH).json()[0]) == STAFF_MEMBER_KEYS
        assert set(client.post(LIST_PATH, json=CREATE_BODY).json()) == STAFF_MEMBER_KEYS
        assert set(client.patch(DETAIL_PATH, json=PATCH_BODY).json()) == STAFF_MEMBER_KEYS


def test_create_forwards_the_three_profile_fields() -> None:
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.post(
            LIST_PATH,
            json={
                **CREATE_BODY,
                "phone": "+972-52-123-4567",
                "start_date": "2026-08-01",
                "shift_manager_eligible": True,
            },
        )
    assert resp.status_code == 200
    call = fake.call("create")
    assert call["phone"] == "+972-52-123-4567"
    assert call["start_date"] == date(2026, 8, 1)
    assert call["shift_manager_eligible"] is True


def test_create_defaults_eligibility_to_false_and_the_rest_to_none() -> None:
    """An unanswered "may she be slotted as shift manager" is a no, not a third
    state — so this one field defaults to a value while phone and start date
    default to the absent state they genuinely have."""
    fake = FakeStaffService()
    with _client(fake) as client:
        client.post(LIST_PATH, json=CREATE_BODY)
    call = fake.call("create")
    assert call["phone"] is None
    assert call["start_date"] is None
    assert call["shift_manager_eligible"] is False


def test_an_omitted_eligibility_on_patch_reaches_the_service_as_none() -> None:
    """`bool | None` and not `bool` on the PATCH body, and this is why: a `False`
    default would silently un-tick eligibility every time the owner saved any
    OTHER field on the row."""
    fake = FakeStaffService()
    with _client(fake) as client:
        client.patch(DETAIL_PATH, json={"display_name": "דנה"})
    assert fake.call("update")["shift_manager_eligible"] is None


def test_an_empty_phone_on_patch_reaches_the_service_as_an_empty_string() -> None:
    """The clear signal survives the schema. `min_length` on this field would
    turn "remove my number" into a 422 about string length — which is why the
    field deliberately carries a max and no min."""
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.patch(DETAIL_PATH, json={"phone": ""})
    assert resp.status_code == 200
    assert fake.call("update")["phone"] == ""


def test_a_start_date_that_is_not_a_date_is_a_house_shaped_400() -> None:
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.patch(DETAIL_PATH, json={"start_date": "last tuesday"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_an_over_long_phone_is_refused_at_the_schema_not_the_service() -> None:
    """The LENGTH bound is the schema's and the CHARSET bound is
    `validate_phone`'s. Split that way because a 4 KB phone number should never
    reach a domain function, while a malformed one should get the console's own
    Hebrew rather than a schema error about a regex."""
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.patch(DETAIL_PATH, json={"phone": "+" + "5" * 200})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_delete_forwards_an_explicit_last_day_and_defaults_it_to_none() -> None:
    """A query parameter and not a body: DELETE-with-a-body is unevenly supported
    by clients and proxies, and this is one scalar. `None` here is the router
    saying "not sent" — the SERVICE is what turns that into today-Jerusalem, so
    the default lives in exactly one place."""
    fake = FakeStaffService()
    with _client(fake) as client:
        assert client.delete(f"{DETAIL_PATH}?last_day=2026-08-31").status_code == 200
        assert fake.call("deactivate")["last_day"] == date(2026, 8, 31)

    fake = FakeStaffService()
    with _client(fake) as client:
        assert client.delete(DETAIL_PATH).status_code == 200
        assert fake.call("deactivate")["last_day"] is None


def test_a_malformed_last_day_never_reaches_the_service() -> None:
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.delete(f"{DETAIL_PATH}?last_day=whenever")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


# --- F38: the three photo routes ---


PRESIGN_PATH = f"{DETAIL_PATH}/photo/presign"
CONFIRM_PATH = f"{DETAIL_PATH}/photo/confirm"
PHOTO_PATH = f"{DETAIL_PATH}/photo"
PRESIGN_BODY: dict[str, Any] = {"content_type": "image/jpeg", "byte_size": 4096}

PHOTO_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("POST", PRESIGN_PATH, PRESIGN_BODY),
    ("POST", CONFIRM_PATH, None),
    ("DELETE", PHOTO_PATH, None),
]


@pytest.mark.parametrize(
    ("method", "path", "body"),
    PHOTO_ROUTES,
    ids=[f"{m}-{p}" for m, p, _ in PHOTO_ROUTES],
)
def test_every_photo_route_inherits_the_router_gate_without_its_own_decorator(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """The gate is mounted on the ROUTER, so these three carry no decorator of
    their own — which is only safe if that inheritance is tested rather than
    assumed. A shift manager is the probe because she is the role closest to an
    owner and the one a mis-scoped gate would admit."""
    fake = FakeStaffService()
    with _client(fake, role=StaffRole.SHIFT_MANAGER.value) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 403, f"{method} {path} → {resp.status_code}"
    assert resp.json() == NOT_AUTHORIZED_BODY
    assert fake.calls == []


@pytest.mark.parametrize(
    ("method", "path", "body"),
    PHOTO_ROUTES,
    ids=[f"{m}-{p}" for m, p, _ in PHOTO_ROUTES],
)
def test_every_photo_route_answers_404_for_an_unknown_staffer(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """Which is also what ANOTHER TENANT's staff id answers — RLS and the
    repository's redundant tenant predicate make a foreign row indistinguishable
    from a missing one, and this route family must not become the place that
    distinction leaks."""
    fake = FakeStaffService()
    fake.raise_on = {"presign_photo": StaffNotFoundError(), "confirm_photo": StaffNotFoundError()}
    fake.raise_on["delete_photo"] = StaffNotFoundError()
    with _client(fake) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_presign_answers_the_post_policy_and_forwards_the_declared_claims() -> None:
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.post(PRESIGN_PATH, json=PRESIGN_BODY)
    assert resp.status_code == 200
    assert set(resp.json()) == {"url", "fields", "expires_in", "max_bytes"}
    call = fake.call("presign_photo")
    assert call["content_type"] == "image/jpeg"
    assert call["byte_size"] == 4096
    assert call["actor_id"] == STAFF_ID


def test_the_presign_response_carries_no_photo_id() -> None:
    """Deliberate: the confirm route reads the pending triple off the ROW, so the
    client never holds an identifier it could substitute for another staffer's.
    Asserted positively because "we did not add a field" is exactly the kind of
    decision a later convenience edit undoes."""
    fake = FakeStaffService()
    with _client(fake) as client:
        body = client.post(PRESIGN_PATH, json=PRESIGN_BODY).json()
    assert "photo_id" not in body
    assert "storage_key" not in body


def test_confirm_and_delete_answer_the_updated_member() -> None:
    """The full member and not a bare ok: the console re-renders from the
    server's own view rather than guessing what the promote did."""
    fake = FakeStaffService()
    with _client(fake) as client:
        assert set(client.post(CONFIRM_PATH).json()) == STAFF_MEMBER_KEYS
        assert set(client.delete(PHOTO_PATH).json()) == STAFF_MEMBER_KEYS


def test_a_presign_body_with_an_unknown_field_is_refused() -> None:
    """`ForbidExtraModel`, so a client that invents `storage_key` gets a 400
    rather than having it silently ignored — the key is server-built and no
    client value may ever reach it."""
    fake = FakeStaffService()
    with _client(fake) as client:
        resp = client.post(
            PRESIGN_PATH, json={**PRESIGN_BODY, "storage_key": "tenants/other/x.jpg"}
        )
    assert resp.status_code == 400
    assert fake.calls == []


def test_an_unconfigured_bucket_is_a_503_on_every_photo_write() -> None:
    """…while `GET /manage/staff` still answers 200 with `photo_url: null`. The
    asymmetry is the whole degrade posture: a storage outage must never take down
    a read the boutique runs on."""
    fake = FakeStaffService()
    fake.raise_on = {
        "presign_photo": MediaNotConfiguredError(),
        "confirm_photo": MediaNotConfiguredError(),
        "delete_photo": MediaNotConfiguredError(),
    }
    with _client(fake) as client:
        for method, path, body in PHOTO_ROUTES:
            assert client.request(method, path, json=body).status_code == 503
        listed = client.get(LIST_PATH)
    assert listed.status_code == 200
    assert listed.json()[0]["photo_url"] is None


def test_a_throttled_presign_is_a_429_in_the_house_shape() -> None:
    fake = FakeStaffService()
    fake.raise_on = {"presign_photo": MediaPresignThrottledError()}
    with _client(fake) as client:
        resp = client.post(PRESIGN_PATH, json=PRESIGN_BODY)
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
