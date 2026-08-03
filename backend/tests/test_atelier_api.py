"""F41 fast API tests: route wiring, the 401, all three roles, the per-route
delete tightening, the host-derived tenant, the CSRF fence, the two new 409s and
the wire shape — a duck-typed FakeAtelierService on `app.state.atelier_service`
plus a hardcoded TenantContext resolver, no database (`test_floor_api.py` style).

**This is the backend milestone.** It is the first point at which the routes, the
role gates, the tenant trust path, the band resolution and the wire shape are
exercised end to end with no Postgres. `test_atelier_service.py` runs below the
router and swaps nothing, so the two prove disjoint halves.

`ATELIER_ROUTES` is exported for `test_staff_role_gating.py` — the
`test_floor_api.FLOOR_ROUTES` precedent — so these seven rows get a real
end-to-end 403 assertion rather than only the structural one.
"""

import datetime
import time
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.atelier.schemas import (
    AssignTicketRequest,
    AtelierBoardResponse,
    AtelierTicket,
    CreateTicketRequest,
    EffortBandRef,
    StageRequest,
    UpdateTicketRequest,
)
from app.atelier.stages import DEFAULT_EFFORT_BANDS
from app.atelier.validation import (
    AtelierValidationError,
    TicketAlreadyAssignedError,
    TicketStageConflictError,
)
from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.errors import DomainNotFoundError
from app.main import NOT_AUTHORIZED_BODY, create_app
from app.models.constants import EffortBand, StaffRole, TicketStage
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})
# A tenant that has tuned ONE band. The other four must still resolve to the
# platform defaults — per-band resolution, never all-or-nothing.
TUNED_TENANT = TenantContext(
    id=TENANT.id,
    slug="bella",
    name="Bella Bridal",
    settings={"atelier": {"effort_bands": {"half_day": 300}}},
)

STAFF_ID = uuid.uuid4()
TICKET_ID = uuid.uuid4()
OTHER_TICKET_ID = uuid.uuid4()
SEAMSTRESS_ID = uuid.uuid4()
CUSTOMER_ID = uuid.uuid4()
TOKEN = "session-token-abc"

BOARD_PATH = "/manage/atelier/tickets"
CREATE_PATH = "/manage/atelier/tickets"
UPDATE_PATH = f"/manage/atelier/tickets/{TICKET_ID}/update"
ASSIGN_PATH = f"/manage/atelier/tickets/{TICKET_ID}/assign"
ADVANCE_PATH = f"/manage/atelier/tickets/{TICKET_ID}/stage/advance"
UNDO_PATH = f"/manage/atelier/tickets/{TICKET_ID}/stage/undo"
DELETE_PATH = f"/manage/atelier/tickets/{TICKET_ID}/delete"

DUE = "2026-08-20"
STAMP = datetime.datetime(2026, 8, 1, 8, 10, tzinfo=datetime.UTC)

CREATE_BODY: dict[str, Any] = {
    "customer_name": "מיכל לוי",
    "customer_phone": "0521234567",
    "due_date": DUE,
    "effort_band": "two_hours",
}
UPDATE_BODY: dict[str, Any] = {
    "due_date": "2026-08-22",
    "effort_band": "half_day",
    "dress_id": None,
    "dress_name": "שמלת ערב של הלקוחה",
    "dress_size": "M",
    "notes": "",
}

# CONCRETE urls, not templates. The structural walker in
# test_staff_role_gating.py reads `route.path` and needs TEMPLATES, so it keeps
# its own ATELIER_OPEN table; these seven issue real requests and need real ids.
#
# TEN routers now mount prefix="/manage" — boutique, catalog, owner_booking,
# staff, dashboard, floor, gateway, customers, queue_manage and this one — so a
# duplicated (method, path) would silently win or lose on include order with no
# error at all. This table is the wiring guard, and a 404 in the walk below is
# what catches a shadow.
ATELIER_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", BOARD_PATH, None),
    ("POST", CREATE_PATH, CREATE_BODY),
    ("POST", UPDATE_PATH, UPDATE_BODY),
    ("POST", ASSIGN_PATH, {"staff_user_id": None}),
    ("POST", ADVANCE_PATH, {"stage": "qc"}),
    ("POST", UNDO_PATH, {"stage": "qc"}),
    ("POST", DELETE_PATH, None),
]

# The spec's D13 error table, verbatim. F41 adds EXACTLY TWO codes; asserting the
# observed set is SET-EQUAL to this literal is what stops a third arriving
# unnoticed.
SPEC_ERROR_CODES = {
    "NOT_AUTHENTICATED",
    "NOT_AUTHORIZED",
    "NOT_FOUND",
    "VALIDATION_ERROR",
    "CSRF_ORIGIN_MISMATCH",
    "TICKET_STAGE_CONFLICT",
    "TICKET_ALREADY_ASSIGNED",
}

# Kept in step with test_staff_role_gating.UNKNOWN_ROLE, which owns the tripwire
# asserting it never becomes a real StaffRole.
UNKNOWN_ROLE = "no-such-role"

ATELIER_ROLES = [
    StaffRole.OWNER.value,
    StaffRole.SHIFT_MANAGER.value,
    StaffRole.SEAMSTRESS.value,
]
OUTSIDE_ROLES = [StaffRole.RECEPTION.value, StaffRole.SALES_ASSISTANT.value]


def _ticket(
    ticket_id: uuid.UUID = TICKET_ID,
    *,
    due_date: str = DUE,
    overdue: bool = False,
    stage: TicketStage = TicketStage.INTAKE,
) -> AtelierTicket:
    return AtelierTicket(
        id=ticket_id,
        customer_name="מיכל לוי",
        due_date=datetime.date.fromisoformat(due_date),
        overdue=overdue,
        effort_minutes=120,
        assigned_staff_user_id=None,
        dress_id=None,
        dress_name=None,
        dress_size=None,
        notes=None,
        stage=stage,
        intake_at=STAMP,
        in_progress_at=None,
        qc_at=None,
        ready_at=None,
        delivered_at=None,
    )


class FakeAuthService:
    def __init__(
        self, role: str = StaffRole.OWNER.value, staff_id: uuid.UUID | None = None
    ) -> None:
        # The session's tenant_id DELIBERATELY disagrees with the host-resolved
        # TENANT.id, so a handler reaching for StaffContext.tenant_id is
        # distinguishable from a correct one.
        self.staff = StaffContext(
            id=staff_id or STAFF_ID,
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


class FakeAtelierService:
    """Duck-typed AtelierService: records what it was called with and answers
    wire objects.

    It does NOT re-implement the authorization matrix or the four-outcome
    discriminators — those are `test_atelier_service.py`'s, against the real one.
    What this fake exists to prove is that the ROUTER hands the service the
    host-resolved tenant, the path's ticket id, the SESSION's actor and the
    TENANT'S OWN BANDS, in that shape.
    """

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.raises = raises

    def _record(self, verb: str, **kwargs: Any) -> None:
        if self.raises is not None:
            self.calls.append({"verb": verb, **kwargs})
            raise self.raises
        self.calls.append({"verb": verb, **kwargs})

    async def board(
        self, tenant_id: uuid.UUID, *, bands: dict[EffortBand, int]
    ) -> AtelierBoardResponse:
        self._record("board", tenant_id=tenant_id, bands=dict(bands))
        return AtelierBoardResponse(
            tickets=[_ticket(), _ticket(OTHER_TICKET_ID, due_date="2026-07-01", overdue=True)],
            seamstresses=[],
            effort_bands=[EffortBandRef(band=b, minutes=m) for b, m in bands.items()],
            truncated=False,
        )

    async def create(
        self,
        tenant_id: uuid.UUID,
        request: CreateTicketRequest,
        *,
        actor: StaffContext,
        bands: dict[EffortBand, int],
    ) -> AtelierTicket:
        self._record(
            "create", tenant_id=tenant_id, actor_id=actor.id, request=request, bands=dict(bands)
        )
        return _ticket(due_date=request.due_date.isoformat())

    async def update(
        self,
        tenant_id: uuid.UUID,
        ticket_id: uuid.UUID,
        request: UpdateTicketRequest,
        *,
        actor: StaffContext,
        bands: dict[EffortBand, int],
    ) -> AtelierTicket:
        self._record(
            "update",
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            actor_id=actor.id,
            request=request,
            bands=dict(bands),
        )
        return _ticket(ticket_id)

    async def assign(
        self,
        tenant_id: uuid.UUID,
        ticket_id: uuid.UUID,
        request: AssignTicketRequest,
        *,
        actor: StaffContext,
    ) -> AtelierTicket:
        self._record(
            "assign",
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            actor_id=actor.id,
            staff_user_id=request.staff_user_id,
        )
        return _ticket(ticket_id)

    async def advance(
        self,
        tenant_id: uuid.UUID,
        ticket_id: uuid.UUID,
        request: StageRequest,
        *,
        actor: StaffContext,
    ) -> AtelierTicket:
        self._record(
            "advance",
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            actor_id=actor.id,
            stage=request.stage,
        )
        return _ticket(ticket_id, stage=request.stage)

    async def undo(
        self,
        tenant_id: uuid.UUID,
        ticket_id: uuid.UUID,
        request: StageRequest,
        *,
        actor: StaffContext,
    ) -> AtelierTicket:
        self._record(
            "undo", tenant_id=tenant_id, ticket_id=ticket_id, actor_id=actor.id, stage=request.stage
        )
        return _ticket(ticket_id)

    async def delete(
        self, tenant_id: uuid.UUID, ticket_id: uuid.UUID, *, actor: StaffContext
    ) -> None:
        self._record("delete", tenant_id=tenant_id, ticket_id=ticket_id, actor_id=actor.id)


def _client(
    fake: FakeAtelierService,
    *,
    authed: bool = True,
    role: str = StaffRole.OWNER.value,
    staff_id: uuid.UUID | None = None,
    tenant: TenantContext = TENANT,
) -> TestClient:
    async def _resolver(slug: str) -> TenantContext | None:
        return tenant if slug == "bella" else None

    app = create_app(resolver=_resolver)
    auth = FakeAuthService(role, staff_id)
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    # app.state, not dependency_overrides: get_atelier_service reads app.state
    # directly, the way every other console dependency does.
    app.state.atelier_service = fake
    app.dependency_overrides[get_auth_service] = lambda: auth
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client


# --- wiring, authentication and the role gates ---


def test_every_route_requires_authentication() -> None:
    fake = FakeAtelierService()
    with _client(fake, authed=False) as client:
        for method, path, body in ATELIER_ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert fake.calls == []


def test_every_route_is_wired_and_reaches_its_own_service_method() -> None:
    """TEN routers now mount prefix="/manage": a path collision would silently
    shadow whichever was included first, and a 404 here is what catches it.

    The second assertion is the one that catches a copy-paste between two of the
    six near-identical POST handlers — every route must reach ITS OWN method."""
    seen: list[str] = []
    for method, path, body in ATELIER_ROUTES:
        fake = FakeAtelierService()
        with _client(fake) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{method} {path} → {resp.status_code} {resp.text}"
        assert len(fake.calls) == 1, f"{method} {path} reached {len(fake.calls)} service methods"
        seen.append(fake.calls[0]["verb"])
    assert seen == ["board", "create", "update", "assign", "advance", "undo", "delete"]


@pytest.mark.parametrize("role", ATELIER_ROLES)
def test_all_three_atelier_roles_reach_every_route_except_delete(role: str) -> None:
    """The router gate names THREE ROLE LITERALS, not `*StaffRole`: the atelier's
    admitted set is not "every role the product has", and a sixth role added
    later must be refused here by default."""
    for method, path, body in ATELIER_ROUTES:
        if path == DELETE_PATH:
            continue
        fake = FakeAtelierService()
        with _client(fake, role=role) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{role} {method} {path} → {resp.status_code} {resp.text}"


def test_a_seamstress_may_NOT_delete_a_ticket() -> None:
    """⚠ A REAL END-TO-END 403, not only the structural one, and it is the
    per-route tightening that makes it true: `RoleGate` composes by INTERSECTION,
    so a per-route gate can only narrow — which is also why F41 needs its own
    module and cannot hang a route off an existing router.

    A seamstress removing a garment from the board is destructive and there is no
    un-delete."""
    fake = FakeAtelierService()
    with _client(fake, role=StaffRole.SEAMSTRESS.value) as client:
        resp = client.post(DELETE_PATH)
    assert resp.status_code == 403
    assert resp.json() == NOT_AUTHORIZED_BODY
    assert fake.calls == []


@pytest.mark.parametrize("role", [*OUTSIDE_ROLES, UNKNOWN_ROLE])
def test_a_role_outside_the_three_is_refused_with_the_exact_generic_body(role: str) -> None:
    """Reception and sales_assistant have no business in the workroom, and the
    body is F31's generic one so a probe learns nothing about which roles exist.
    """
    for method, path, body in ATELIER_ROUTES:
        fake = FakeAtelierService()
        with _client(fake, role=role) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 403, f"{role} {method} {path} → {resp.status_code}"
        assert resp.json() == NOT_AUTHORIZED_BODY
        assert fake.calls == []


@pytest.mark.parametrize(
    ("method", "path", "body"), ATELIER_ROUTES, ids=[f"{m}-{p}" for m, p, _ in ATELIER_ROUTES]
)
def test_no_atelier_response_is_cached(method: str, path: str, body: dict[str, Any] | None) -> None:
    """Router-level `_no_store`, so a route added here later cannot forget it. A
    cached board in a shared workroom browser would show one boutique's brides to
    the next person who opens it — and a stale card is worse than none on a
    screen whose whole purpose is being current."""
    fake = FakeAtelierService()
    with _client(fake) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"


# --- the trust path and the bands ---


def test_every_handler_passes_the_HOST_resolved_tenant() -> None:
    """`get_current_tenant(request)` is host-derived; `StaffContext.tenant_id` is
    session-derived. The fake makes them disagree, so a handler reaching for the
    session's id fails here."""
    for method, path, body in ATELIER_ROUTES:
        fake = FakeAtelierService()
        with _client(fake) as client:
            assert client.request(method, path, json=body).status_code == 200
        assert fake.calls[0]["tenant_id"] == TENANT.id


def test_the_target_comes_from_the_PATH_and_the_actor_from_the_SESSION() -> None:
    """The two must come from DIFFERENT places. If a handler ever passed the path
    id as the actor, D9's «herself only» check would be trivially true and every
    seamstress could claim anybody's ticket."""
    fake = FakeAtelierService()
    with _client(fake, role=StaffRole.SEAMSTRESS.value) as client:
        assert client.post(ADVANCE_PATH, json={"stage": "qc"}).status_code == 200
    assert fake.calls == [
        {
            "verb": "advance",
            "tenant_id": TENANT.id,
            "ticket_id": TICKET_ID,
            "actor_id": STAFF_ID,
            "stage": TicketStage.QC,
        }
    ]
    assert TICKET_ID != STAFF_ID


def test_the_bands_come_off_the_REQUESTS_TENANT_and_cost_no_statement() -> None:
    """⚠ `TenantContext.settings` is already bound on the request by the tenancy
    middleware. Reading the mapping back through `TenantsRepository` would open a
    FOURTH session, pool checkout and BEGIN/COMMIT on the hottest read in the
    feature, every five seconds per device — that repository is constructed with
    a session_factory and opens its own session inside every method, so it cannot
    join the atelier's tenant_session.

    Resolution is PER BAND: one tuned key leaves the other four on the platform
    defaults."""
    fake = FakeAtelierService()
    with _client(fake, tenant=TUNED_TENANT) as client:
        body = client.get(BOARD_PATH).json()

    assert fake.calls[0]["bands"] == {
        **DEFAULT_EFFORT_BANDS,
        EffortBand.HALF_DAY: 300,
    }
    assert body["effort_bands"] == [
        {"band": "thirty_min", "minutes": 30},
        {"band": "one_hour", "minutes": 60},
        {"band": "two_hours", "minutes": 120},
        {"band": "half_day", "minutes": 300},
        {"band": "full_day", "minutes": 480},
    ]


def test_a_brand_new_boutique_with_no_atelier_key_gets_the_five_platform_bands() -> None:
    """No shipped writer can reach `settings["atelier"]` — `merge_settings` takes
    only `profile=` and `toggles=` — so an absent key is the NORMAL case, not an
    error. Every tenant always has exactly five bands, which is what lets the
    intake form render with no empty-state branch."""
    fake = FakeAtelierService()
    with _client(fake) as client:
        assert client.get(BOARD_PATH).status_code == 200
    assert fake.calls[0]["bands"] == DEFAULT_EFFORT_BANDS


def test_the_create_handler_passes_the_bands_too() -> None:
    """The band -> minutes resolution happens in the SERVICE, from this dict.
    A create that did not receive it could only fall back to the platform
    defaults and would silently ignore the boutique's tuning."""
    fake = FakeAtelierService()
    with _client(fake, tenant=TUNED_TENANT) as client:
        assert client.post(CREATE_PATH, json=CREATE_BODY).status_code == 200
    assert fake.calls[0]["bands"][EffortBand.HALF_DAY] == 300


# --- the wire shape ---


def test_the_board_payload_is_an_envelope_with_four_named_parts() -> None:
    """An ENVELOPE, never a bare array: F42 adds capacity to `seamstresses`, F43
    adds fitting counts to a ticket, and a bare array would make the first of
    those a breaking shape change on a screen that polls every five seconds."""
    fake = FakeAtelierService()
    with _client(fake) as client:
        body = client.get(BOARD_PATH).json()

    assert set(body) == {"tickets", "seamstresses", "effort_bands", "truncated"}
    assert body["truncated"] is False
    assert body["tickets"] == [
        {
            "id": str(TICKET_ID),
            "customer_name": "מיכל לוי",
            "due_date": DUE,
            "overdue": False,
            "effort_minutes": 120,
            "assigned_staff_user_id": None,
            "dress_id": None,
            "dress_name": None,
            "dress_size": None,
            "notes": None,
            "stage": "intake",
            "intake_at": STAMP.isoformat().replace("+00:00", "Z"),
            "in_progress_at": None,
            "qc_at": None,
            "ready_at": None,
            "delivered_at": None,
        },
        {
            "id": str(OTHER_TICKET_ID),
            "customer_name": "מיכל לוי",
            "due_date": "2026-07-01",
            "overdue": True,
            "effort_minutes": 120,
            "assigned_staff_user_id": None,
            "dress_id": None,
            "dress_name": None,
            "dress_size": None,
            "notes": None,
            "stage": "intake",
            "intake_at": STAMP.isoformat().replace("+00:00", "Z"),
            "in_progress_at": None,
            "qc_at": None,
            "ready_at": None,
            "delivered_at": None,
        },
    ]


def test_no_ticket_on_the_wire_carries_the_brides_PHONE() -> None:
    """D6's minimisation. The board is read by a seamstress and there is no
    surface in F41 that calls a bride — that is F43's fitting booking."""
    fake = FakeAtelierService()
    with _client(fake) as client:
        body = client.get(BOARD_PATH).json()
    keys = {key for ticket in body["tickets"] for key in ticket}
    assert keys & {"customer_phone", "phone", "customer_id", "tenant_id", "deleted_at"} == set()


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (UPDATE_PATH, UPDATE_BODY),
        (ASSIGN_PATH, {"staff_user_id": str(SEAMSTRESS_ID)}),
        (ADVANCE_PATH, {"stage": "qc"}),
        (UNDO_PATH, {"stage": "qc"}),
    ],
)
def test_every_mutation_answers_the_FULL_ticket(path: str, body: dict[str, Any]) -> None:
    """Not `{ok: true}`. The console patches its card from the server's own row,
    so it cannot disagree with itself — and on a 200 no-op that renders the FIRST
    actor's timestamp rather than this request's intent."""
    fake = FakeAtelierService()
    with _client(fake) as client:
        payload = client.post(path, json=body).json()
    assert set(payload) == {
        "id",
        "customer_name",
        "due_date",
        "overdue",
        "effort_minutes",
        "assigned_staff_user_id",
        "dress_id",
        "dress_name",
        "dress_size",
        "notes",
        "stage",
        "intake_at",
        "in_progress_at",
        "qc_at",
        "ready_at",
        "delivered_at",
    }


def test_delete_answers_an_ok_body_and_not_a_ticket() -> None:
    fake = FakeAtelierService()
    with _client(fake) as client:
        assert client.post(DELETE_PATH).json() == {"ok": True}


def test_the_stage_wire_literals_are_exactly_the_five() -> None:
    """SET EQUALITY. The console's `STAGE_ORDER`, the five columns and every
    conditional write's predicate are all spelled from this enum."""
    assert {stage.value for stage in TicketStage} == {
        "intake",
        "in_progress",
        "qc",
        "ready",
        "delivered",
    }


def test_the_effort_band_wire_literals_are_exactly_the_five() -> None:
    assert {band.value for band in EffortBand} == {
        "thirty_min",
        "one_hour",
        "two_hours",
        "half_day",
        "full_day",
    }


# --- validation at the boundary (D5, D8) ---


def test_a_band_key_outside_the_five_is_a_400_and_never_reaches_the_service() -> None:
    """The wire carries the BAND KEY and the server resolves it, so there is no
    request shape in which 37 minutes reaches the row — and an invented sixth key
    is refused by the request model before any handler runs."""
    fake = FakeAtelierService()
    with _client(fake) as client:
        resp = client.post(CREATE_PATH, json={**CREATE_BODY, "effort_band": "three_hours"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_effort_minutes_can_never_be_sent_by_a_client() -> None:
    """`ForbidExtraModel`. This is the assertion that makes "five preset bands,
    not a minute field" a structural property of the wire."""
    fake = FakeAtelierService()
    with _client(fake) as client:
        resp = client.post(CREATE_PATH, json={**CREATE_BODY, "effort_minutes": 37})
    assert resp.status_code == 400
    assert fake.calls == []


def test_a_PAST_due_date_reaches_the_service_and_answers_200() -> None:
    """⚠ THE API-LEVEL HALF OF D5, and it is what fails if someone adds a
    `Field(ge=…)` to the request model or a router-level lower bound. There is no
    lower bound anywhere: a dress that was due yesterday is exactly the ticket a
    boutique most needs to open."""
    fake = FakeAtelierService()
    with _client(fake) as client:
        resp = client.post(CREATE_PATH, json={**CREATE_BODY, "due_date": "2020-01-01"})
    assert resp.status_code == 200
    assert fake.calls[0]["request"].due_date == datetime.date(2020, 1, 1)


def test_a_due_date_beyond_the_horizon_answers_the_house_shape_400() -> None:
    """`AtelierValidationError` is a `DomainValidationError`, so it needs NO new
    handler — the shipped one maps it. The bound itself is
    `test_atelier_service.py`'s."""
    fake = FakeAtelierService(raises=AtelierValidationError("due_date is too far in the future"))
    with _client(fake) as client:
        resp = client.post(CREATE_PATH, json={**CREATE_BODY, "due_date": "9999-01-01"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_an_update_that_omits_a_field_is_a_400() -> None:
    """The full-replace rule, at the wire. An optional field would make a
    malformed request that dropped `notes` indistinguishable from a deliberate
    clear."""
    fake = FakeAtelierService()
    body = {key: value for key, value in UPDATE_BODY.items() if key != "notes"}
    with _client(fake) as client:
        resp = client.post(UPDATE_PATH, json=body)
    assert resp.status_code == 400
    assert fake.calls == []


# --- the error table (D13) ---


def test_a_missing_ticket_is_a_404() -> None:
    fake = FakeAtelierService(raises=DomainNotFoundError("alteration_ticket"))
    with _client(fake) as client:
        assert client.post(ADVANCE_PATH, json={"stage": "qc"}).status_code == 404
        assert (
            client.post(ADVANCE_PATH, json={"stage": "qc"}).json()["error"]["code"] == "NOT_FOUND"
        )


def test_a_stage_conflict_is_a_409_with_its_OWN_code() -> None:
    """Two codes and not one: a stage conflict says the GARMENT moved on and the
    remedy is to look again. Collapsing it into the shipped generic CONFLICT
    would make the console branch on a message string."""
    fake = FakeAtelierService(raises=TicketStageConflictError())
    with _client(fake) as client:
        resp = client.post(ADVANCE_PATH, json={"stage": "qc"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "TICKET_STAGE_CONFLICT"


def test_an_assignment_conflict_is_a_409_with_a_DIFFERENT_code() -> None:
    """An assignment conflict says a PERSON took it, and the next tick will name
    her — a different sentence and a different next move from a stage conflict.
    """
    fake = FakeAtelierService(raises=TicketAlreadyAssignedError())
    with _client(fake) as client:
        resp = client.post(ASSIGN_PATH, json={"staff_user_id": str(SEAMSTRESS_ID)})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "TICKET_ALREADY_ASSIGNED"


def test_the_two_conflict_bodies_are_different_sentences() -> None:
    """If both handlers returned the same body the two codes would be
    decoration."""
    stage = FakeAtelierService(raises=TicketStageConflictError())
    assigned = FakeAtelierService(raises=TicketAlreadyAssignedError())
    with _client(stage) as client:
        first = client.post(ADVANCE_PATH, json={"stage": "qc"}).json()
    with _client(assigned) as client:
        second = client.post(ASSIGN_PATH, json={"staff_user_id": None}).json()
    assert first != second
    assert first["error"]["message"] != second["error"]["message"]


def test_a_mutation_from_a_foreign_origin_is_refused() -> None:
    """All six POSTs ARE fenced — CsrfOriginMiddleware gates on
    `request.method in MUTATING_METHODS`."""
    for method, path, body in ATELIER_ROUTES:
        if method != "POST":
            continue
        fake = FakeAtelierService()
        with _client(fake) as client:
            resp = client.request(
                method, path, json=body, headers={"origin": "http://evil.localtest.me"}
            )
        assert resp.status_code == 403, f"{path} → {resp.status_code}"
        assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"
        assert fake.calls == []


def test_the_board_read_from_a_foreign_origin_is_ALLOWED() -> None:
    """The asymmetry is asserted rather than assumed: the GET is not fenced, and
    its protection is the session cookie and the role gate, alone."""
    fake = FakeAtelierService()
    with _client(fake) as client:
        resp = client.get(BOARD_PATH, headers={"origin": "http://evil.localtest.me"})
    assert resp.status_code == 200


def test_every_spec_error_code_is_asserted() -> None:
    """Mechanical completeness, re-derived from LIVE responses rather than from a
    literal — and SET EQUALITY, so a third new code arriving without a test here
    fails immediately."""
    observed = set()
    with _client(FakeAtelierService(), authed=False) as client:
        observed.add(client.get(BOARD_PATH).json()["error"]["code"])
    with _client(FakeAtelierService(), role=UNKNOWN_ROLE) as client:
        observed.add(client.get(BOARD_PATH).json()["error"]["code"])
    with _client(FakeAtelierService(raises=DomainNotFoundError("alteration_ticket"))) as client:
        observed.add(client.post(ADVANCE_PATH, json={"stage": "qc"}).json()["error"]["code"])
    with _client(FakeAtelierService()) as client:
        observed.add(
            client.post(CREATE_PATH, json={**CREATE_BODY, "effort_band": "nope"}).json()["error"][
                "code"
            ]
        )
    with _client(FakeAtelierService()) as client:
        observed.add(
            client.post(
                ADVANCE_PATH, json={"stage": "qc"}, headers={"origin": "http://evil.localtest.me"}
            ).json()["error"]["code"]
        )
    with _client(FakeAtelierService(raises=TicketStageConflictError())) as client:
        observed.add(client.post(ADVANCE_PATH, json={"stage": "qc"}).json()["error"]["code"])
    with _client(FakeAtelierService(raises=TicketAlreadyAssignedError())) as client:
        observed.add(client.post(ASSIGN_PATH, json={"staff_user_id": None}).json()["error"]["code"])
    assert observed == SPEC_ERROR_CODES
