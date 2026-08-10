"""F39 fast API tests: route wiring, the 401, all five roles, the FIVE per-route
tightenings, the host-derived tenant and its settings, the CSRF fence, the five
coded errors and the wire shape — a duck-typed `FakeShiftsService` on
`app.state.shifts_service` plus a hardcoded `TenantContext` resolver, no database
(`test_atelier_api.py` style).

**This is the backend milestone.** It is the first point at which the eight
routes, the role gates, the tenant trust path, the settings resolution and the
wire shape are exercised end to end with no Postgres. `test_shifts_service.py`
and `test_shifts_db.py` run below the router and swap nothing, so the three prove
disjoint halves.

`SHIFTS_ROUTES` is exported for `test_staff_role_gating.py` — the
`test_floor_api.FLOOR_ROUTES` precedent — so these eight rows get a real
end-to-end 403 assertion rather than only the structural one.
"""

import datetime
import time
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth.dependencies import NotAuthorizedError, get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.floor.schemas import SetOnShiftRequest
from app.main import NOT_AUTHORIZED_BODY, create_app
from app.models.constants import AvailabilityState, StaffRole
from app.shifts.schemas import (
    AvailabilityEntryResponse,
    CreateAssignmentRequest,
    PublishedRosterResponse,
    RosterShiftResponse,
    RosterWeekResponse,
    SeedTemplatesResponse,
    ShiftTemplateInput,
    ShiftTemplateListResponse,
    ShiftTemplateResponse,
    ShiftWeekResponse,
    SubmitAvailabilityRequest,
    TemplateWriteResponse,
    WeekSubmissionRowResponse,
    WeekSubmissionsResponse,
)
from app.shifts.service import (
    AvailabilityConflictError,
    NoOpeningHoursError,
    NotShiftManagerEligibleError,
    ShiftManagerSlotTakenError,
    ShiftNotFoundError,
    SubmissionClosedError,
    TemplatesAlreadySeededError,
)
from app.shifts.validation import (
    MAX_COVERAGE_TARGET,
    CoverageTargetInvalidError,
    TemplateLimitReachedError,
    WeekOutOfRangeError,
)
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})
# A tenant that has SAVED a deadline. It rides the same `TenantContext.settings`
# the atelier's bands do and costs the same zero statements — which is the whole
# reason the router resolves it rather than the service reading it back.
SCHEDULED_TENANT = TenantContext(
    id=TENANT.id,
    slug="bella",
    name="Bella Bridal",
    settings={
        "scheduling": {"submission_deadline_day_of_week": 2, "submission_deadline_time": "17:30"}
    },
)

STAFF_ID = uuid.uuid4()
OTHER_STAFF_ID = uuid.uuid4()
TEMPLATE_ID = uuid.uuid4()
# F40: the assignment the DELETE names in its path.
ASSIGNMENT_ID = uuid.uuid4()
ENTRY_ID = uuid.uuid4()
TOKEN = "session-token-abc"

WEEK_START = datetime.date(2026, 11, 8)
WEEK_END = datetime.date(2026, 11, 14)
DEADLINE = datetime.datetime(2026, 11, 4, 16, 0, tzinfo=datetime.UTC)

TEMPLATES_PATH = "/manage/shifts/templates"
TEMPLATE_PATH = f"/manage/shifts/templates/{TEMPLATE_ID}"
SEED_PATH = "/manage/shifts/templates/seed"
WEEK_PATH = "/manage/shifts/week"
SUBMIT_PATH = "/manage/shifts/week/availability"
SUBMISSIONS_PATH = "/manage/shifts/week/submissions"
ROSTER_PATH = "/manage/shifts/roster"
ASSIGNMENTS_PATH = "/manage/shifts/roster/assignments"
ASSIGNMENT_PATH = f"/manage/shifts/roster/assignments/{ASSIGNMENT_ID}"
PUBLISH_PATH = "/manage/shifts/roster/publish"
PUBLISHED_PATH = "/manage/shifts/roster/published"

TEMPLATE_BODY: dict[str, Any] = {
    "day_of_week": 4,
    "label": "משמרת בוקר",
    "starts_at_time": "09:00:00",
    "ends_at_time": "14:00:00",
    "sort_order": 0,
    # ⚠ F40 D10's SIXTH REQUIRED FIELD. This PATCH is a full replace, so an
    # omitted key would silently clear the targets on every unrelated label
    # edit — which is why the schema carries no default and every body here
    # gained the field rather than the field gaining a default.
    "coverage_targets": {},
}
ASSIGN_BODY: dict[str, Any] = {
    "week_start": WEEK_START.isoformat(),
    "shift_template_id": str(TEMPLATE_ID),
    "staff_user_id": str(STAFF_ID),
    "is_shift_manager": False,
    "acknowledge_override": False,
}
SUBMIT_BODY: dict[str, Any] = {
    "week_start": WEEK_START.isoformat(),
    "entries": [{"shift_template_id": str(TEMPLATE_ID), "state": "available"}],
}

# CONCRETE urls, not templates. The structural walker in
# `test_staff_role_gating.py` reads `route.path` and needs TEMPLATES, so it keeps
# its own SHIFTS_OPEN / SHIFTS_ELEVATED tables; these eight issue real requests.
#
# ELEVEN routers now mount prefix="/manage", so a duplicated (method, path) would
# silently win or lose on include order with no error at all. This table is the
# wiring guard, and a 404 in the walk below is what catches a shadow.
SHIFTS_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", TEMPLATES_PATH, None),
    ("POST", TEMPLATES_PATH, TEMPLATE_BODY),
    ("PATCH", TEMPLATE_PATH, TEMPLATE_BODY),
    ("DELETE", TEMPLATE_PATH, None),
    ("POST", SEED_PATH, None),
    ("GET", WEEK_PATH, None),
    ("PUT", SUBMIT_PATH, SUBMIT_BODY),
    ("GET", SUBMISSIONS_PATH, None),
    # F40's five. Thirteen rows on one router now, and the shadow guard matters
    # more with every one: `/shifts/roster/assignments` and
    # `/shifts/roster/published` both sit under `/shifts/roster`, so a stray
    # `{week}`-style path parameter on the parent would swallow either.
    ("GET", ROSTER_PATH, None),
    ("POST", ASSIGNMENTS_PATH, ASSIGN_BODY),
    ("DELETE", ASSIGNMENT_PATH, None),
    ("POST", PUBLISH_PATH, {"week_start": WEEK_START.isoformat()}),
    ("GET", PUBLISHED_PATH, None),
]

# The FIVE routes carrying a per-route tightening on top of the router's five
# roles. `RoleGate` composes by INTERSECTION, so a per-route gate can only ever
# NARROW — there is no per-route widening anywhere in this codebase.
ELEVATED_ROUTES = {
    ("POST", TEMPLATES_PATH),
    ("PATCH", TEMPLATE_PATH),
    ("DELETE", TEMPLATE_PATH),
    ("POST", SEED_PATH),
    ("GET", SUBMISSIONS_PATH),
    # F40's four builder verbs. ⚠ `PUBLISHED_PATH` IS DELIBERATELY ABSENT: the
    # published week reads to EVERY role (D13), because the floor board already
    # names every colleague and a staffer who cannot see the roster cannot plan.
    ("GET", ROSTER_PATH),
    ("POST", ASSIGNMENTS_PATH),
    ("DELETE", ASSIGNMENT_PATH),
    ("POST", PUBLISH_PATH),
}

# The spec's error table, verbatim. F39 adds EXACTLY FIVE codes; asserting the
# observed set is SET-EQUAL to this literal is what stops a sixth arriving
# unnoticed — and an unmapped code renders the server's ENGLISH sentence,
# right-aligned, in a Hebrew console, on a green build.
SPEC_ERROR_CODES = {
    "NOT_AUTHENTICATED",
    "NOT_AUTHORIZED",
    "NOT_FOUND",
    "VALIDATION_ERROR",
    "CSRF_ORIGIN_MISMATCH",
    "WEEK_OUT_OF_RANGE",
    "SUBMISSION_CLOSED",
    "TEMPLATES_ALREADY_SEEDED",
    "NO_OPENING_HOURS",
    "TEMPLATE_LIMIT_REACHED",
    # F40's four.
    "AVAILABILITY_CONFLICT",
    "NOT_SHIFT_MANAGER_ELIGIBLE",
    "SHIFT_MANAGER_SLOT_TAKEN",
    "COVERAGE_TARGET_INVALID",
}

ALL_ROLES = [role.value for role in StaffRole]
NON_ELEVATED = [
    StaffRole.RECEPTION.value,
    StaffRole.SALES_ASSISTANT.value,
    StaffRole.SEAMSTRESS.value,
]


def _template(**overrides: Any) -> ShiftTemplateResponse:
    base: dict[str, Any] = {
        "id": TEMPLATE_ID,
        "day_of_week": 4,
        "label": "משמרת בוקר",
        "starts_at_time": datetime.time(9, 0),
        "ends_at_time": datetime.time(14, 0),
        "sort_order": 0,
    }
    return ShiftTemplateResponse(**{**base, **overrides})


def _roster_shift() -> RosterShiftResponse:
    return RosterShiftResponse(
        template=_template(),
        assignments=[],
        coverage_targets={},
        assigned_by_role={},
    )


def _roster_week() -> RosterWeekResponse:
    return RosterWeekResponse(
        week_start=WEEK_START,
        week_end=WEEK_START,
        published_at=None,
        published_by_name=None,
        edited_since_publish=False,
        shifts=[_roster_shift()],
        staff=[],
    )


def _entry() -> AvailabilityEntryResponse:
    return AvailabilityEntryResponse(
        id=ENTRY_ID,
        shift_template_id=TEMPLATE_ID,
        state=AvailabilityState.AVAILABLE,
        recorded_by_name="דנה כהן",
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


class FakeShiftsService:
    """Duck-typed `ShiftsService`: records what it was called with and answers
    wire objects.

    It does NOT re-implement the self-or-elevated matrix, D11's diff or the lock
    predicate — those are `test_shifts_service.py`'s and `test_shifts_db.py`'s,
    against the real one. What this fake exists to prove is that the ROUTER hands
    the service the host-resolved tenant, the path's template id, the SESSION's
    actor and the TENANT'S OWN SETTINGS, in that shape.
    """

    def __init__(self, *, raises: Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.raises = raises

    def _record(self, verb: str, **kwargs: Any) -> None:
        self.calls.append({"verb": verb, **kwargs})
        if self.raises is not None:
            raise self.raises

    def call(self, verb: str) -> dict[str, Any]:
        matches = [entry for entry in self.calls if entry["verb"] == verb]
        assert len(matches) == 1, f"{verb} called {len(matches)} times"
        return matches[0]

    async def list_templates(
        self, tenant_id: uuid.UUID, *, actor: StaffContext
    ) -> ShiftTemplateListResponse:
        self._record("list_templates", tenant_id=tenant_id, actor=actor)
        return ShiftTemplateListResponse(templates=[_template(future_submission_count=2)])

    async def create_template(
        self, tenant_id: uuid.UUID, *, actor: StaffContext, body: ShiftTemplateInput
    ) -> ShiftTemplateResponse:
        self._record("create_template", tenant_id=tenant_id, actor=actor, body=body)
        return _template()

    async def update_template(
        self,
        tenant_id: uuid.UUID,
        template_id: uuid.UUID,
        *,
        actor: StaffContext,
        body: ShiftTemplateInput,
    ) -> TemplateWriteResponse:
        self._record(
            "update_template",
            tenant_id=tenant_id,
            template_id=template_id,
            actor=actor,
            body=body,
        )
        return TemplateWriteResponse(template=_template(), invalidated_submissions=3)

    async def delete_template(
        self, tenant_id: uuid.UUID, template_id: uuid.UUID, *, actor: StaffContext
    ) -> TemplateWriteResponse:
        self._record("delete_template", tenant_id=tenant_id, template_id=template_id, actor=actor)
        return TemplateWriteResponse(template=None, invalidated_submissions=1)

    async def seed_templates(
        self, tenant_id: uuid.UUID, *, actor: StaffContext
    ) -> SeedTemplatesResponse:
        self._record("seed_templates", tenant_id=tenant_id, actor=actor)
        return SeedTemplatesResponse(created=1, templates=[_template()])

    async def week(
        self,
        tenant_id: uuid.UUID,
        *,
        actor: StaffContext,
        settings: dict[str, Any],
        week_start: datetime.date | None = None,
    ) -> ShiftWeekResponse:
        self._record(
            "week", tenant_id=tenant_id, actor=actor, settings=settings, week_start=week_start
        )
        return ShiftWeekResponse(
            week_start=WEEK_START,
            week_end=WEEK_END,
            deadline_at=DEADLINE,
            locked=False,
            templates=[_template()],
            entries=[_entry()],
        )

    async def submit(
        self,
        tenant_id: uuid.UUID,
        *,
        actor: StaffContext,
        settings: dict[str, Any],
        body: SubmitAvailabilityRequest,
    ) -> ShiftWeekResponse:
        self._record("submit", tenant_id=tenant_id, actor=actor, settings=settings, body=body)
        return ShiftWeekResponse(
            week_start=body.week_start,
            week_end=WEEK_END,
            deadline_at=DEADLINE,
            locked=False,
            templates=[_template()],
            entries=[_entry()],
        )

    async def roster(
        self,
        tenant_id: uuid.UUID,
        *,
        actor: StaffContext,
        week_start: datetime.date | None = None,
    ) -> RosterWeekResponse:
        self._record("roster", tenant_id=tenant_id, actor=actor, week_start=week_start)
        return _roster_week()

    async def assign(
        self, tenant_id: uuid.UUID, *, actor: StaffContext, body: CreateAssignmentRequest
    ) -> RosterShiftResponse:
        self._record("assign", tenant_id=tenant_id, actor=actor, body=body)
        return _roster_shift()

    async def unassign(
        self, tenant_id: uuid.UUID, *, actor: StaffContext, assignment_id: uuid.UUID
    ) -> RosterShiftResponse:
        self._record("unassign", tenant_id=tenant_id, actor=actor, assignment_id=assignment_id)
        return _roster_shift()

    async def publish(
        self, tenant_id: uuid.UUID, *, actor: StaffContext, week_start: datetime.date
    ) -> RosterWeekResponse:
        self._record("publish", tenant_id=tenant_id, actor=actor, week_start=week_start)
        return _roster_week()

    async def published(
        self, tenant_id: uuid.UUID, *, week_start: datetime.date | None = None
    ) -> PublishedRosterResponse:
        self._record("published", tenant_id=tenant_id, week_start=week_start)
        return PublishedRosterResponse(
            published=False,
            published_at=None,
            week_start=WEEK_START,
            week_end=WEEK_START,
            shifts=[],
        )

    async def submissions(
        self, tenant_id: uuid.UUID, *, week_start: datetime.date | None = None
    ) -> WeekSubmissionsResponse:
        self._record("submissions", tenant_id=tenant_id, week_start=week_start)
        return WeekSubmissionsResponse(
            week_start=WEEK_START,
            week_end=WEEK_END,
            submitted_count=1,
            total=2,
            rows=[
                WeekSubmissionRowResponse(
                    staff_user_id=STAFF_ID,
                    display_name="דנה כהן",
                    submitted=True,
                    entries=[_entry()],
                ),
                WeekSubmissionRowResponse(
                    staff_user_id=OTHER_STAFF_ID,
                    display_name="מיכל ברזילי",
                    submitted=False,
                    entries=[],
                ),
            ],
        )


def _client(
    fake: FakeShiftsService,
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
    # app.state, not dependency_overrides: `get_shifts_service` reads app.state
    # directly, the way every other console dependency does.
    app.state.shifts_service = fake
    app.dependency_overrides[get_auth_service] = lambda: auth
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client


# --- wiring, authentication and the role gates ---


@pytest.mark.parametrize(("method", "path", "body"), SHIFTS_ROUTES)
def test_every_route_requires_authentication(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    fake = FakeShiftsService()
    with _client(fake, authed=False) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 401
    assert fake.calls == []


@pytest.mark.parametrize(("method", "path", "body"), SHIFTS_ROUTES)
def test_no_route_is_shadowed_by_another_manage_router(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """Eleven routers mount prefix="/manage". A duplicated (method, path) would
    silently win or lose on include order with no error at all; a 404 or a 405
    here is what catches the shadow."""
    with _client(FakeShiftsService()) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code not in (404, 405), resp.text


@pytest.mark.parametrize("role", ALL_ROLES)
def test_every_role_reads_the_templates_and_her_own_week(role: str) -> None:
    """All five, and that is the point of the router's gate: a staffer cannot
    answer a week without knowing which shifts it has."""
    with _client(FakeShiftsService(), role=role) as client:
        assert client.get(TEMPLATES_PATH).status_code == 200
        assert client.get(WEEK_PATH).status_code == 200
        assert client.put(SUBMIT_PATH, json=SUBMIT_BODY).status_code == 200


@pytest.mark.parametrize("role", NON_ELEVATED)
@pytest.mark.parametrize(("method", "path"), sorted(ELEVATED_ROUTES))
def test_the_five_elevated_routes_refuse_every_floor_role(
    method: str, path: str, role: str
) -> None:
    fake = FakeShiftsService()
    with _client(fake, role=role) as client:
        resp = client.request(
            method, path, json=TEMPLATE_BODY if method in ("POST", "PATCH") else None
        )
    assert resp.status_code == 403
    assert resp.json() == NOT_AUTHORIZED_BODY
    assert fake.calls == []


@pytest.mark.parametrize("role", [StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value])
def test_both_elevated_roles_reach_every_elevated_route(role: str) -> None:
    """⚠ THE SHIFT MANAGER IS ADMITTED EVERYWHERE IN THIS FEATURE (spec D5).
    Putting any of these in `OWNER_ONLY` is the one edit that would silently make
    that false."""
    with _client(FakeShiftsService(), role=role) as client:
        assert client.post(TEMPLATES_PATH, json=TEMPLATE_BODY).status_code == 201
        assert client.patch(TEMPLATE_PATH, json=TEMPLATE_BODY).status_code == 200
        assert client.delete(TEMPLATE_PATH).status_code == 200
        assert client.post(SEED_PATH).status_code == 200
        assert client.get(SUBMISSIONS_PATH).status_code == 200


# --- the tenant trust path ---


def test_the_tenant_comes_from_the_host_and_never_from_the_session() -> None:
    """`FakeAuthService`'s `StaffContext.tenant_id` deliberately disagrees with
    the host-resolved one, so a handler reaching for the session's is
    distinguishable from a correct one."""
    fake = FakeShiftsService()
    with _client(fake) as client:
        client.get(WEEK_PATH)
    call = fake.call("week")
    assert call["tenant_id"] == TENANT.id
    assert call["actor"].tenant_id != TENANT.id


def test_the_deadline_settings_ride_the_request_at_zero_statements() -> None:
    """`TenantContext.settings` is already bound by the tenancy middleware, so the
    deadline pair costs no read of its own — `AtelierService`'s bands, same rule
    and the same reason (`TenantsRepository` opens its own session and could not
    join the service's)."""
    fake = FakeShiftsService()
    with _client(fake, tenant=SCHEDULED_TENANT) as client:
        client.get(WEEK_PATH)
        client.put(SUBMIT_PATH, json=SUBMIT_BODY)
    assert fake.call("week")["settings"] == SCHEDULED_TENANT.settings
    assert fake.call("submit")["settings"] == SCHEDULED_TENANT.settings


def test_the_path_id_and_the_session_actor_reach_the_service() -> None:
    fake = FakeShiftsService()
    with _client(fake, staff_id=OTHER_STAFF_ID) as client:
        client.patch(TEMPLATE_PATH, json=TEMPLATE_BODY)
    call = fake.call("update_template")
    assert call["template_id"] == TEMPLATE_ID
    assert call["actor"].id == OTHER_STAFF_ID


def test_the_optional_week_start_reaches_the_service_and_defaults_to_none() -> None:
    """D1: the client may NAME a week; the server validates the Sunday-ness and
    the window and never trusts the arithmetic. No parameter means «next week»,
    resolved server-side from the Jerusalem clock."""
    fake = FakeShiftsService()
    with _client(fake) as client:
        client.get(WEEK_PATH, params={"week_start": "2026-11-15"})
        client.get(SUBMISSIONS_PATH)
    assert fake.call("week")["week_start"] == datetime.date(2026, 11, 15)
    assert fake.call("submissions")["week_start"] is None


def test_the_submit_body_names_whom_to_record_and_never_who_is_asking() -> None:
    fake = FakeShiftsService()
    with _client(fake, staff_id=STAFF_ID) as client:
        client.put(SUBMIT_PATH, json={**SUBMIT_BODY, "staff_user_id": str(OTHER_STAFF_ID)})
    call = fake.call("submit")
    assert call["body"].staff_user_id == OTHER_STAFF_ID
    assert call["actor"].id == STAFF_ID


# --- the wire shape ---


def test_the_week_payload_carries_plain_dates_and_a_utc_instant() -> None:
    """⚠ `deadline_at` IS AN INSTANT AND THE TWO WEEK KEYS ARE PLAIN CALENDAR
    DATES. `plainDayMonth` on the console splits a `YYYY-MM-DD` on `-`, so handing
    it the instant renders «NaN.11»; and slicing the instant by hand instead reads
    a UTC calendar day as a Jerusalem one, which is D1/D6's DST bug."""
    with _client(FakeShiftsService()) as client:
        body = client.get(WEEK_PATH).json()
    assert body["week_start"] == "2026-11-08"
    assert body["week_end"] == "2026-11-14"
    assert body["deadline_at"] == "2026-11-04T16:00:00Z"
    assert body["locked"] is False
    assert body["entries"][0]["state"] == "available"
    assert body["entries"][0]["recorded_by_name"] == "דנה כהן"
    assert body["templates"][0]["starts_at_time"] == "09:00:00"


def test_the_templates_read_carries_the_pre_commit_invalidation_count() -> None:
    """D4's binding sentence needs a number BEFORE she commits, and this is the
    only route that can answer it (design F-2)."""
    with _client(FakeShiftsService()) as client:
        body = client.get(TEMPLATES_PATH).json()
    assert body["templates"][0]["future_submission_count"] == 2


def test_the_two_invalidating_writes_answer_the_count_that_really_moved() -> None:
    with _client(FakeShiftsService()) as client:
        patched = client.patch(TEMPLATE_PATH, json=TEMPLATE_BODY).json()
        removed = client.delete(TEMPLATE_PATH).json()
    assert patched["invalidated_submissions"] == 3
    assert patched["template"]["id"] == str(TEMPLATE_ID)
    assert removed["invalidated_submissions"] == 1
    # No row is left to render, and returning the pre-delete one would put a
    # shift back on a screen that just removed it.
    assert removed["template"] is None


def test_the_submissions_read_carries_names_counts_and_per_row_entries() -> None:
    with _client(FakeShiftsService()) as client:
        body = client.get(SUBMISSIONS_PATH).json()
    assert body["submitted_count"] == 1
    assert body["total"] == 2
    assert body["rows"][0]["display_name"] == "דנה כהן"
    assert body["rows"][0]["submitted"] is True
    # design F-4: the same entry TYPE the staffer's own panel gets, so the
    # attribution an on-behalf write creates is visible on both screens.
    assert body["rows"][0]["entries"][0]["recorded_by_name"] == "דנה כהן"
    assert body["rows"][1]["submitted"] is False
    assert body["rows"][1]["entries"] == []


def test_the_create_answers_201() -> None:
    with _client(FakeShiftsService()) as client:
        assert client.post(TEMPLATES_PATH, json=TEMPLATE_BODY).status_code == 201


@pytest.mark.parametrize(("method", "path", "body"), SHIFTS_ROUTES)
def test_every_response_is_no_store(method: str, path: str, body: dict[str, Any] | None) -> None:
    with _client(FakeShiftsService()) as client:
        resp = client.request(method, path, json=body)
    assert resp.headers["cache-control"] == "no-store"


# --- the five coded errors ---


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (WeekOutOfRangeError(), 400, "WEEK_OUT_OF_RANGE"),
        (TemplateLimitReachedError(), 400, "TEMPLATE_LIMIT_REACHED"),
        (SubmissionClosedError(), 409, "SUBMISSION_CLOSED"),
        (TemplatesAlreadySeededError(), 409, "TEMPLATES_ALREADY_SEEDED"),
        (NoOpeningHoursError(), 409, "NO_OPENING_HOURS"),
        (ShiftNotFoundError(), 404, "NOT_FOUND"),
        (NotAuthorizedError(), 403, "NOT_AUTHORIZED"),
        # F40's four. `NOT_SHIFT_MANAGER_ELIGIBLE` and `COVERAGE_TARGET_INVALID`
        # are 400s — the request is malformed against the server's rules. The
        # other two are 409s: the body is well-formed and conflicts with server
        # state.
        (AvailabilityConflictError(), 409, "AVAILABILITY_CONFLICT"),
        (NotShiftManagerEligibleError(), 400, "NOT_SHIFT_MANAGER_ELIGIBLE"),
        (ShiftManagerSlotTakenError(), 409, "SHIFT_MANAGER_SLOT_TAKEN"),
        (CoverageTargetInvalidError(), 400, "COVERAGE_TARGET_INVALID"),
    ],
)
def test_each_service_refusal_maps_to_its_own_code(exc: Exception, status: int, code: str) -> None:
    """⚠ EVERY ONE OF THESE NEEDS ITS OWN HANDLER. None of the five F39 errors is
    a `DomainValidationError` subclass: Starlette walks `type(exc).__mro__`, so a
    subclass shipped without a handler would answer a quiet, plausible
    `VALIDATION_ERROR` 400 — and the console, which maps CODES to Hebrew, would
    render the server's English sentence right-aligned on a green build."""
    with _client(FakeShiftsService(raises=exc)) as client:
        resp = client.put(SUBMIT_PATH, json=SUBMIT_BODY)
    assert resp.status_code == status
    assert resp.json()["error"]["code"] == code


def test_the_error_codes_are_exactly_the_spec_table() -> None:
    """A sixth code arriving unnoticed is what this set equality stops. Asserted
    against the module constant so the spec's table and the observed set cannot
    drift apart silently."""
    observed = {
        "NOT_AUTHENTICATED",
        "NOT_AUTHORIZED",
        "NOT_FOUND",
        "VALIDATION_ERROR",
        "CSRF_ORIGIN_MISMATCH",
    }
    for exc in (
        WeekOutOfRangeError(),
        TemplateLimitReachedError(),
        SubmissionClosedError(),
        TemplatesAlreadySeededError(),
        NoOpeningHoursError(),
        # F40's four. Every one is re-derived from a LIVE response, so a handler
        # that was never registered shows up here as a `VALIDATION_ERROR` rather
        # than as a missing member of a literal.
        AvailabilityConflictError(),
        NotShiftManagerEligibleError(),
        ShiftManagerSlotTakenError(),
        CoverageTargetInvalidError(),
    ):
        with _client(FakeShiftsService(raises=exc)) as client:
            observed.add(client.put(SUBMIT_PATH, json=SUBMIT_BODY).json()["error"]["code"])
    assert observed == SPEC_ERROR_CODES


def test_a_malformed_body_is_a_house_shape_400_before_the_service() -> None:
    fake = FakeShiftsService()
    with _client(fake) as client:
        resp = client.put(SUBMIT_PATH, json={"week_start": "not-a-date", "entries": []})
    assert resp.status_code in (400, 422)
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_an_unknown_state_is_refused_by_the_schema() -> None:
    """`pending` in particular: it is the console's fourth radio «לא נרשם», the
    rendered name of an ABSENT row (D8), and it must never reach a column."""
    fake = FakeShiftsService()
    with _client(fake) as client:
        resp = client.put(
            SUBMIT_PATH,
            json={
                "week_start": WEEK_START.isoformat(),
                "entries": [{"shift_template_id": str(TEMPLATE_ID), "state": "pending"}],
            },
        )
    assert resp.status_code in (400, 422)
    assert fake.calls == []


@pytest.mark.parametrize("sort_order", [3_000_000_000, -3_000_000_000])
def test_an_out_of_range_sort_order_is_refused_by_the_schema(sort_order: int) -> None:
    """⚠ `sort_order` IS THE ONE TEMPLATE FIELD NO DOMAIN RULE READS.

    `validate_template` never sees it, so unbounded it rides straight into an
    `INTEGER` column and asyncpg answers «value out of int32 range» as a
    `DBAPIError` — whose `__mro__` `main.py` maps nowhere, making it a 500 with no
    code `MAPPED_CODES` can render. Bounded at the schema it is the house-shape
    400 every other out-of-range field already produces, before the service.
    """
    fake = FakeShiftsService()
    with _client(fake) as client:
        resp = client.post(TEMPLATES_PATH, json={**TEMPLATE_BODY, "sort_order": sort_order})
    assert resp.status_code in (400, 422)
    assert fake.calls == []


def test_an_unknown_body_key_is_refused() -> None:
    fake = FakeShiftsService()
    with _client(fake) as client:
        resp = client.put(SUBMIT_PATH, json={**SUBMIT_BODY, "recorded_by": str(STAFF_ID)})
    assert resp.status_code in (400, 422)
    assert fake.calls == []


# --- the CSRF fence ---


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [row for row in SHIFTS_ROUTES if row[0] in ("POST", "PATCH", "DELETE", "PUT")],
)
def test_every_mutating_route_is_csrf_fenced(
    method: str, path: str, body: dict[str, Any] | None
) -> None:
    """`CsrfOriginMiddleware` gates on `request.method in MUTATING_METHODS` — a
    method test rather than a path list — so all five are fenced by construction.
    Asserted anyway, because "by construction" is a claim about a file this
    feature does not touch."""
    fake = FakeShiftsService()
    with _client(fake) as client:
        resp = client.request(method, path, json=body, headers={"Origin": "http://evil.example"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"
    assert fake.calls == []


# --- F40 D10: coverage targets on the template full-replace -------------------


def test_the_template_write_refuses_a_body_without_coverage_targets() -> None:
    """⚠ THE SIXTH REQUIRED FIELD, and required is the whole point (D10). F39's
    PATCH is a FULL REPLACE, so a `coverage_targets` carrying a default would let
    an unrelated label edit silently clear every target the owner set — the same
    class of silent loss `UpdateAppointmentTypeRequest`'s rule exists to prevent.

    Refused BEFORE the service, by the schema, which is why the fake records no
    call at all.
    """
    without = {key: value for key, value in TEMPLATE_BODY.items() if key != "coverage_targets"}
    fake = FakeShiftsService()
    with _client(fake) as client:
        assert client.patch(f"{TEMPLATES_PATH}/{TEMPLATE_ID}", json=without).status_code == 400
        assert client.post(TEMPLATES_PATH, json=without).status_code == 400
    assert fake.calls == []


def test_an_empty_map_is_accepted_and_reaches_the_service() -> None:
    """`{}` is the DEFAULT state of every template that predates this feature, so
    it is the ordinary case rather than an edge one."""
    fake = FakeShiftsService()
    with _client(fake) as client:
        resp = client.patch(
            f"{TEMPLATES_PATH}/{TEMPLATE_ID}",
            json={**TEMPLATE_BODY, "coverage_targets": {}},
        )
    assert resp.status_code == 200
    assert fake.call("update_template")["body"].coverage_targets == {}


def test_a_sparse_map_reaches_the_service_untouched() -> None:
    """⚠ `0` SURVIVES THE WIRE. An absent key is «no target» and `0` is
    «deliberately nobody» (D10) — a schema that dropped falsy values would turn
    the second into the first between the browser and the validator."""
    fake = FakeShiftsService()
    with _client(fake) as client:
        client.patch(
            f"{TEMPLATES_PATH}/{TEMPLATE_ID}",
            json={**TEMPLATE_BODY, "coverage_targets": {"sales_assistant": 2, "seamstress": 0}},
        )
    assert fake.call("update_template")["body"].coverage_targets == {
        "sales_assistant": 2,
        "seamstress": 0,
    }


def test_an_invalid_target_maps_to_its_own_coded_400() -> None:
    """⚠ `COVERAGE_TARGET_INVALID` AND NOT A GENERIC 422, because the console has
    a specific Hebrew sentence keyed on this code — an unmapped code renders the
    server's ENGLISH message, right-aligned, in a Hebrew console, on a green
    build (F38's build note). This proves the HANDLER is registered, which is the
    half a validator test cannot reach."""
    with _client(FakeShiftsService(raises=CoverageTargetInvalidError())) as client:
        resp = client.patch(
            f"{TEMPLATES_PATH}/{TEMPLATE_ID}",
            json={**TEMPLATE_BODY, "coverage_targets": {"seamstress": 99}},
        )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "COVERAGE_TARGET_INVALID"
    # O3 says the constant will move, so the bound is INTERPOLATED rather than
    # typed into the sentence (design F-33).
    assert str(MAX_COVERAGE_TARGET) in resp.json()["error"]["message"]


# --- F40: the five roster routes ----------------------------------------------


def test_the_assignment_write_answers_200_on_both_paths_and_never_201() -> None:
    """⚠ PLAN §0.1's RESOLUTION OF A SPEC/DESIGN CONFLICT, pinned. Design F-2
    turns this route into an UPSERT on the live `(roster, template, staffer)`
    triple, and a route that is sometimes a create and sometimes an update,
    answering two codes, forces the client to branch on a status to decide what
    it just did. One code, one client path — the spec's `201` row is superseded.
    """
    fake = FakeShiftsService()
    with _client(fake) as client:
        first = client.post(ASSIGNMENTS_PATH, json=ASSIGN_BODY)
        second = client.post(ASSIGNMENTS_PATH, json=ASSIGN_BODY)
    assert first.status_code == 200
    assert second.status_code == 200


def test_both_assignment_routes_answer_the_affected_shift_and_not_the_week() -> None:
    """⚠ PLAN §0.1 AGAIN, and the reason is R-C. The pane permits two concurrent
    writes on one shift BY DESIGN (per-control `loading`, nothing else disables),
    so a whole-week payload per tap lets the earlier-issued response arriving
    second overwrite the later assignment — the owner sees one fewer woman on a
    shift she then publishes, and it fails no functional test."""
    week_keys = {
        "week_start",
        "week_end",
        "published_at",
        "published_by_name",
        "edited_since_publish",
        "shifts",
        "staff",
    }
    shift_keys = {"template", "assignments", "coverage_targets", "assigned_by_role"}
    with _client(FakeShiftsService()) as client:
        assert set(client.post(ASSIGNMENTS_PATH, json=ASSIGN_BODY).json()) == shift_keys
        assert set(client.delete(ASSIGNMENT_PATH).json()) == shift_keys
        # And the two WEEK routes answer the week, so the shapes are not
        # accidentally the same thing.
        assert set(client.get(ROSTER_PATH).json()) == week_keys
        assert (
            set(client.post(PUBLISH_PATH, json={"week_start": WEEK_START.isoformat()}).json())
            == week_keys
        )


def test_the_published_read_is_open_to_every_role_and_the_builder_is_not() -> None:
    """D13's split, over HTTP. A staffer who cannot see the published roster
    cannot plan; a staffer who could open the BUILDER would see every
    colleague's submitted state, which is F39's own reason for gating
    `/shifts/week/submissions`."""
    for role in ALL_ROLES:
        with _client(FakeShiftsService(), role=role) as client:
            assert client.get(PUBLISHED_PATH).status_code == 200, role
            expected = 200 if role in {"owner", "shift_manager"} else 403
            assert client.get(ROSTER_PATH).status_code == expected, role


def test_the_week_keys_are_plain_dates_and_published_at_is_a_utc_instant() -> None:
    """⚠ DIFFERENT KINDS OF THING, AND THE WIRE SAYS SO (F39's schema header). A
    week is a page of the boutique's calendar — `YYYY-MM-DD`, no offset to get
    wrong — and `published_at` is an INSTANT. The console's `plainDayMonth`
    refuses to meet a `Date` for exactly this reason."""
    with _client(FakeShiftsService()) as client:
        body = client.get(ROSTER_PATH).json()
    assert body["week_start"] == WEEK_START.isoformat()
    assert "T" not in body["week_start"]
    # Null here because the fake answers a draft; the instant shape is asserted
    # against real rows in test_roster_db.py.
    assert body["published_at"] is None


def test_the_override_body_carries_no_date_and_a_supplied_one_is_refused() -> None:
    """⚠ D3: the override is ALWAYS today, computed server-side. Accepting a date
    would make rule 1 pre-settable for tomorrow — a roster edit wearing an
    override's clothes — and would let a client's clock decide what «today»
    means. `ForbidExtraModel` is what turns a supplied one into a house-shape 400
    rather than a silently ignored field."""
    assert set(SetOnShiftRequest.model_fields) == {"on_shift"}
    with pytest.raises(ValidationError):
        SetOnShiftRequest(on_shift=True, on_shift_on="2026-11-08")  # type: ignore[call-arg]


def test_the_five_roster_routes_reach_their_own_service_method() -> None:
    """The wiring walk, per verb: a shadowed path would answer another handler's
    method and this is what names it."""
    for path, method, verb, body in (
        (ROSTER_PATH, "GET", "roster", None),
        (ASSIGNMENTS_PATH, "POST", "assign", ASSIGN_BODY),
        (ASSIGNMENT_PATH, "DELETE", "unassign", None),
        (PUBLISH_PATH, "POST", "publish", {"week_start": WEEK_START.isoformat()}),
        (PUBLISHED_PATH, "GET", "published", None),
    ):
        fake = FakeShiftsService()
        with _client(fake) as client:
            assert client.request(method, path, json=body).status_code == 200, path
        assert [call["verb"] for call in fake.calls] == [verb], path


def test_the_delete_takes_its_assignment_id_from_the_path() -> None:
    fake = FakeShiftsService()
    with _client(fake) as client:
        client.delete(ASSIGNMENT_PATH)
    assert fake.call("unassign")["assignment_id"] == ASSIGNMENT_ID
