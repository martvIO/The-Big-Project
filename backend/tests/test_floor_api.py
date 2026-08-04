"""F57 fast API tests: route wiring, the 401, all five roles, the generic 403,
the host-derived tenant, the CSRF fence and the wire shape — a duck-typed
FakeFloorService on app.state.floor_service plus a hardcoded TenantContext
resolver, no database (test_dashboard_api.py style).

**This is the backend milestone.** It is the first point at which the route, the
role gate, the tenant trust path and the wire shape are exercised end to end with
no Postgres. `test_floor_db.py` runs below the router and swaps nothing, so the
two prove disjoint halves.

`FLOOR_ROUTES` is exported for `test_staff_role_gating.py` — the
`test_payments_api` / `test_catalog_api` precedent — so these rows get a real
end-to-end 403 assertion rather than only the structural one.

**F36 takes it to THIRTEEN rows and splits the table in two.** Nine admit all
five roles; four compose `require_role(OWNER, SHIFT_MANAGER)` on top of the
router's five and refuse the three floor roles. Both halves are sized from D10's
table and nothing else — a count taken from prose reds the wiring walk on a 404
the first time it runs.

**F37 takes it to EIGHTEEN**, all five new rows in the OPEN half — fourteen open,
four tightened — and the counts come from D9's table for D10's reason.
"""

import datetime
import inspect
import re
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import main as app_main
from app.auth.dependencies import get_auth_service
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.db.repositories.fitting_rooms import RoomRow
from app.db.repositories.sos_alerts import SosAlertRow
from app.errors import DomainNotFoundError
from app.floor import router as app_router
from app.floor import schemas as app_schemas
from app.floor import service as app_service
from app.floor.service import (
    ClientPickerRead,
    DispatchRead,
    DressPickerRead,
    FloorRead,
    RaisedSos,
    RoomRead,
    SosListRead,
    SosRead,
    WaitlistEntryRead,
    WaitlistRead,
)
from app.floor.validation import (
    QueueEmptyError,
    QueueTicketChangedError,
    QueueTicketNotWaitingError,
    RoomOccupiedError,
    SosAlreadyAcceptedError,
    SosClosedError,
    StaffOccupiedError,
)
from app.main import NOT_AUTHORIZED_BODY, create_app
from app.models.booking import Booking
from app.models.constants import SosStatus, StaffCardStatus, StaffRole
from app.models.dress import Dress
from app.models.fitting_assignment_dress import FittingAssignmentDress
from app.models.sos_alert import SosAlert
from app.models.staff_user import StaffUser
from app.tenancy.middleware import TenantContext

TENANT = TenantContext(id=uuid.uuid4(), slug="bella", name="Bella Bridal", settings={})
STAFF_ID = uuid.uuid4()
TARGET_ID = uuid.uuid4()
TOKEN = "session-token-abc"

ROOM_ID = uuid.uuid4()
ASSIGNMENT_ID = uuid.uuid4()
BINDING_ID = uuid.uuid4()
DRESS_ID = uuid.uuid4()
ALERT_ID = uuid.uuid4()
TICKET_ID = uuid.uuid4()
SECOND_TICKET_ID = uuid.uuid4()

FLOOR_PATH = "/manage/floor"
START_PATH = f"/manage/floor/staff/{TARGET_ID}/break/start"
END_PATH = f"/manage/floor/staff/{TARGET_ID}/break/end"
ROOMS_PATH = "/manage/floor/rooms"
ROOM_PATH = f"{ROOMS_PATH}/{ROOM_ID}"
CLAIM_PATH = f"{ROOM_PATH}/claim"
ASSIGNMENT_PATH = f"/manage/floor/assignments/{ASSIGNMENT_ID}"
RELEASE_PATH = f"{ASSIGNMENT_PATH}/release"
HANDOVER_PATH = f"{ASSIGNMENT_PATH}/handover"
BIND_PATH = f"{ASSIGNMENT_PATH}/dresses"
UNBIND_PATH = f"{BIND_PATH}/{BINDING_ID}"
DRESS_LIST_PATH = "/manage/floor/dresses"
CLIENT_LIST_PATH = "/manage/floor/clients"
SOS_PATH = "/manage/floor/sos"
SOS_ALERT_PATH = f"{SOS_PATH}/{ALERT_ID}"
SOS_ACCEPT_PATH = f"{SOS_ALERT_PATH}/accept"
SOS_RESOLVE_PATH = f"{SOS_ALERT_PATH}/resolve"
SOS_CANCEL_PATH = f"{SOS_ALERT_PATH}/cancel"
# F58. Every path's SECOND SEGMENT is `floor`, which is what keeps
# `apps/manage/vite.config.ts` unedited — `test_spa_serving.py` asserts SET
# EQUALITY between the live route table's second segments and the manage dev
# proxy's alternation, and a mismatch breaks ONLY a developer's machine while
# production, CI and the whole suite stay green, serving the SPA shell where the
# API should be. `/manage/queue/{id}/call` reads better and costs exactly that.
TAKE_NEXT_PATH = f"{ROOM_PATH}/take-next"
ASSIGN_PATH = f"{ROOM_PATH}/assign"
QUEUE_PATH = f"/manage/floor/queue/{TICKET_ID}"
CALL_PATH = f"{QUEUE_PATH}/call"
SKIP_PATH = f"{QUEUE_PATH}/skip"
REMOVE_PATH = f"{QUEUE_PATH}/remove"

BREAK_BEGAN = datetime.datetime(2026, 8, 2, 9, 5, tzinfo=datetime.UTC)
# F36's one new envelope field: the server's instant at serialisation, which is
# what the console's «כבר 42 דק'» is computed against.
SERVER_NOW = datetime.datetime(2026, 8, 2, 11, 20, tzinfo=datetime.UTC)
STARTS_AT = datetime.datetime(2026, 8, 2, 6, 0, tzinfo=datetime.UTC)
# F37: the alert's own `created_at`, seeded rather than defaulted so the wire
# assertion is a literal.
RAISED_AT = datetime.datetime(2026, 8, 2, 11, 19, tzinfo=datetime.UTC)

# CONCRETE urls, not templates (plan C4). The structural walker in
# test_staff_role_gating.py reads `route.path` and needs TEMPLATES, so it keeps
# its own FLOOR_OPEN table; these issue real requests and need real ids.
#
# SEVEN routers now mount prefix="/manage", so a duplicated (method, path) would
# silently win or lose on include order: this table is the wiring guard, and a
# 404 in the walk below is what catches a shadow.
#
# ⚠ SPLIT IN TWO, and the split IS D10's table — sized from it, never from prose.
# The nine open rows admit all five roles; the four tightened ones compose
# `require_role(OWNER, SHIFT_MANAGER)` with the router's five and refuse the
# three floor roles. A row in the wrong half is a red walk below rather than a
# quietly widened registry.
FLOOR_OPEN_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("GET", FLOOR_PATH, None),
    ("POST", START_PATH, None),
    ("POST", END_PATH, None),
    ("POST", CLAIM_PATH, {}),
    ("POST", RELEASE_PATH, None),
    ("POST", BIND_PATH, {"dress_id": str(DRESS_ID)}),
    ("DELETE", UNBIND_PATH, None),
    ("GET", DRESS_LIST_PATH, None),
    ("GET", CLIENT_LIST_PATH, None),
    # F58's three. Take-next and assign carry a TARGET-dependent rule (herself,
    # or elevated on anyone) which no RoleGate can express, so they are open here
    # and refused in the service — the claim's rule verbatim. `call` has no
    # target staffer at all: a summons is not destructive, and reception, a sales
    # assistant and a seamstress all legitimately call the next woman forward.
    ("POST", TAKE_NEXT_PATH, {}),
    ("POST", ASSIGN_PATH, {"queue_ticket_id": str(TICKET_ID)}),
    ("POST", CALL_PATH, None),
    # F37's five, and NONE of them is tightened — every rule in that feature
    # reads the ROW (`target_staff_user_id`, `raised_by`, `accepted_by`) before
    # it can decide, and no `RoleGate` can say "the person this alert names".
    ("GET", SOS_PATH, None),
    ("POST", SOS_PATH, {}),
    ("POST", SOS_ACCEPT_PATH, None),
    ("POST", SOS_RESOLVE_PATH, None),
    ("POST", SOS_CANCEL_PATH, None),
]

FLOOR_TIGHTENED_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    ("POST", ROOMS_PATH, {"label": "חדר 3"}),
    ("PATCH", ROOM_PATH, {"label": "חדר 4"}),
    ("DELETE", ROOM_PATH, None),
    ("POST", HANDOVER_PATH, {"staff_user_id": str(TARGET_ID)}),
    # F58's two, and their ABSENCE from FLOOR_OPEN_ROUTES is the assertion. Skip
    # re-orders a stranger's place in a queue and its second press removes her;
    # remove takes a real customer out of it, irreversibly. There is no middle
    # gate available — `test_the_floor_roles_reach_exactly_the_floor_routes`
    # admits all five or exactly two — so the product cost is recorded rather
    # than engineered around: a reception staffer calls a shift manager.
    ("POST", SKIP_PATH, {"seen_skip_count": 0}),
    ("POST", REMOVE_PATH, None),
]

FLOOR_ROUTES: list[tuple[str, str, dict[str, Any] | None]] = [
    *FLOOR_OPEN_ROUTES,
    *FLOOR_TIGHTENED_ROUTES,
]

# The spec's error table, verbatim. NOT_FOUND is the only one a service method
# raises; the other three come from dependency solving or middleware.
#
# ⚠ NINE after F37, and every member is re-derived from a LIVE response below.
# F57 shipped four and could not have shipped more: `VALIDATION_ERROR` had no
# producer on this router until a route took a body, and the two 409s had no
# handler. F36 landed all three at once — the registry's `ForbidExtraModel` body
# and the two occupancy conflicts — so the set grows here, in the PR that gives
# each of them a writer.
SPEC_ERROR_CODES = {
    "NOT_AUTHENTICATED",
    "NOT_AUTHORIZED",
    "NOT_FOUND",
    "VALIDATION_ERROR",
    "ROOM_OCCUPIED",
    "STAFF_OCCUPIED",
    "CSRF_ORIGIN_MISMATCH",
    # ⚠ TWELVE after F58 and F37, and the five they add each needed a writer
    # before they could be here: `QUEUE_EMPTY` has one the moment take-next
    # lands, the two ticket-state ones the moment any verb can refuse a ticket
    # whose state moved, and the two SOS ones the moment accept can lose. The set
    # equality below is re-derived from LIVE responses, so a thirteenth code
    # arriving without a test fails immediately.
    "QUEUE_EMPTY",
    "QUEUE_TICKET_NOT_WAITING",
    "QUEUE_TICKET_CHANGED",
    "SOS_ALREADY_ACCEPTED",
    "SOS_CLOSED",
}

# Kept in step with test_staff_role_gating.UNKNOWN_ROLE, which owns the tripwire
# asserting it never becomes a real StaffRole.
UNKNOWN_ROLE = "no-such-role"

ALL_ROLES = [role.value for role in StaffRole]


def _room_row(
    *,
    room_id: uuid.UUID | None = None,
    label: str = "חדר 1",
    sort_order: int = 0,
    is_active: bool = True,
    occupied: bool = False,
) -> RoomRow:
    return RoomRow(
        room_id=room_id or ROOM_ID,
        label=label,
        sort_order=sort_order,
        is_active=is_active,
        assignment_id=ASSIGNMENT_ID if occupied else None,
        staff_user_id=TARGET_ID if occupied else None,
        staff_display_name="נועה לוי" if occupied else None,
        staff_role=StaffRole.SEAMSTRESS.value if occupied else None,
        booking_id=None,
        client_label="מיכל" if occupied else None,
        assigned_at=BREAK_BEGAN if occupied else None,
    )


def sos_read(
    *,
    status: str = SosStatus.OPEN,
    escalated: bool = False,
    stalled: bool = False,
    for_me: bool = True,
    accepted_by: uuid.UUID | None = None,
    acknowledged_at: datetime.datetime | None = None,
    note: str | None = "צריך סיכות",
) -> SosRead:
    """One card, exported because test_sos_api.py pins the wire it renders."""
    alert = SosAlert(
        tenant_id=TENANT.id,
        raised_by=STAFF_ID,
        target_staff_user_id=TARGET_ID,
        fitting_room_assignment_id=ASSIGNMENT_ID,
        note=note,
        status=status,
    )
    alert.id = ALERT_ID
    alert.accepted_by = accepted_by
    alert.acknowledged_at = acknowledged_at
    alert.created_at = RAISED_AT
    return SosRead(
        row=SosAlertRow(
            alert=alert,
            raised_by_name="דנה כהן",
            target_name="נועה לוי",
            accepted_by_name="נועה לוי" if accepted_by is not None else None,
            room_label="חדר 1",
        ),
        escalated=escalated,
        stalled=stalled,
        for_me=for_me,
    )


def _staff_user(
    staff_id: uuid.UUID,
    *,
    display_name: str = "נועה לוי",
    role: str = StaffRole.RECEPTION.value,
    break_started_at: datetime.datetime | None = None,
) -> StaffUser:
    row = StaffUser(
        tenant_id=TENANT.id,
        email="staff@bella.example",
        password_hash="not-a-real-hash",
        display_name=display_name,
        role=role,
    )
    row.id = staff_id
    row.break_started_at = break_started_at
    return row


class FakeAuthService:
    def __init__(
        self, role: str = StaffRole.OWNER.value, staff_id: uuid.UUID | None = None
    ) -> None:
        # The session's tenant_id DELIBERATELY disagrees with the host-resolved
        # TENANT.id, so a handler reaching for StaffContext.tenant_id is
        # distinguishable from a correct one (test_dashboard_api.py's reason).
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


class FakeFloorService:
    """Duck-typed FloorService: records what it was called with and answers rows.

    It does NOT re-implement the authorization rule — that is
    test_floor_service.py's, against the real one. What this fake exists to prove
    is that the ROUTER hands the service the host-resolved tenant, the path's
    target id and the SESSION's actor, in that shape.
    """

    def __init__(self, *, missing: bool = False, raises: Exception | None = None) -> None:
        self.floor_calls: list[uuid.UUID] = []
        self.toggle_calls: list[dict[str, Any]] = []
        # F36: every method appends here, so the thirteen-row wiring walk can
        # assert "this route reached the service" without a per-method branch.
        self.calls: list[dict[str, Any]] = []
        self.missing = missing
        # F36: the two 409 handlers are app-level, so any route that reaches the
        # service can prove their bodies. The break route is the one that exists
        # in this task; the rooms routes assert the same handlers through their
        # own paths once they land.
        self.raises = raises
        # F36: the break writers' occupancy lookup. Default None — the shipped
        # F57 assertions describe a floor with no rooms, which is every boutique
        # until an owner adds one.
        self.occupancy: RoomRow | None = None
        self.occupancy_by_staff_id: dict[uuid.UUID, RoomRow] = {}
        self.room_rows: list[RoomRow] = []
        self.bindings: dict[uuid.UUID, list[FittingAssignmentDress]] = {}
        # F36: what every mutation answers — ONE shape, the same one the
        # payload's `rooms[]` elements carry, so a route that invented its own
        # would fail the literal assertions below rather than merely look odd.
        self.room_read = RoomRead(row=_room_row(), bindings=[])
        self.dress_picker = DressPickerRead(dresses=[], sizes_by_dress_id={}, truncated=False)
        self.client_picker = ClientPickerRead(bookings=[], names_by_customer_id={}, truncated=False)
        # F58: empty by default, which is the COMMON case — a bridal boutique's
        # queue is empty most of the day and the shipped payload assertions
        # describe exactly that floor.
        self.waitlist = WaitlistRead(entries=[], truncated=False)
        self.dispatch = DispatchRead(room=self.room_read, waitlist=self.waitlist)
        # F37: what the four mutating sos verbs answer — ONE shape, the same one
        # the poll's `alerts[]` elements carry, so a route that invented its own
        # would show up as a key-set difference in test_sos_api.py.
        self.sos_read = sos_read()
        self.sos_alerts: list[SosRead] = []
        self.rerouted = False

    async def floor(self, tenant_id: uuid.UUID) -> FloorRead:
        self.floor_calls.append(tenant_id)
        self._record("floor", tenant_id=tenant_id)
        return FloorRead(
            staff_rows=[
                _staff_user(STAFF_ID, display_name="דנה כהן", role=StaffRole.OWNER.value),
                _staff_user(
                    TARGET_ID,
                    display_name="נועה לוי",
                    role=StaffRole.SEAMSTRESS.value,
                    break_started_at=BREAK_BEGAN,
                ),
            ],
            occupancy_by_staff_id=self.occupancy_by_staff_id,
            room_rows=self.room_rows,
            bindings_by_assignment_id=self.bindings,
            server_now=SERVER_NOW,
            waitlist=self.waitlist,
        )

    async def start_break(
        self, tenant_id: uuid.UUID, staff_id: uuid.UUID, *, actor: StaffContext
    ) -> tuple[StaffUser, RoomRow | None]:
        return self._toggle("start", tenant_id, staff_id, actor, BREAK_BEGAN), self.occupancy

    async def end_break(
        self, tenant_id: uuid.UUID, staff_id: uuid.UUID, *, actor: StaffContext
    ) -> tuple[StaffUser, RoomRow | None]:
        return self._toggle("end", tenant_id, staff_id, actor, None), self.occupancy

    def _toggle(
        self,
        verb: str,
        tenant_id: uuid.UUID,
        staff_id: uuid.UUID,
        actor: StaffContext,
        began: datetime.datetime | None,
    ) -> StaffUser:
        self.toggle_calls.append(
            {"verb": verb, "tenant_id": tenant_id, "staff_id": staff_id, "actor_id": actor.id}
        )
        self._record(f"{verb}_break", tenant_id=tenant_id, staff_id=staff_id, actor_id=actor.id)
        if self.raises is not None:
            raise self.raises
        if self.missing:
            raise DomainNotFoundError("staff_user")
        return _staff_user(staff_id, role=StaffRole.SEAMSTRESS.value, break_started_at=began)

    # --- F36: the ten new methods, in D10's order ---------------------------

    async def create_room(
        self, tenant_id: uuid.UUID, *, label: str, sort_order: int, actor: StaffContext
    ) -> RoomRead:
        return self._room(
            "create_room",
            tenant_id=tenant_id,
            label=label,
            sort_order=sort_order,
            actor_id=actor.id,
        )

    async def update_room(
        self,
        tenant_id: uuid.UUID,
        room_id: uuid.UUID,
        *,
        label: str | None,
        sort_order: int | None,
        is_active: bool | None,
        actor: StaffContext,
    ) -> RoomRead:
        return self._room(
            "update_room",
            tenant_id=tenant_id,
            room_id=room_id,
            label=label,
            sort_order=sort_order,
            is_active=is_active,
            actor_id=actor.id,
        )

    async def delete_room(
        self, tenant_id: uuid.UUID, room_id: uuid.UUID, *, actor: StaffContext
    ) -> None:
        self._record("delete_room", tenant_id=tenant_id, room_id=room_id, actor_id=actor.id)
        if self.raises is not None:
            raise self.raises
        if self.missing:
            raise DomainNotFoundError("fitting_room")

    async def claim(
        self,
        tenant_id: uuid.UUID,
        room_id: uuid.UUID,
        *,
        staff_user_id: uuid.UUID | None,
        booking_id: uuid.UUID | None,
        actor: StaffContext,
    ) -> RoomRead:
        return self._room(
            "claim",
            tenant_id=tenant_id,
            room_id=room_id,
            staff_user_id=staff_user_id,
            booking_id=booking_id,
            actor_id=actor.id,
        )

    async def release(
        self, tenant_id: uuid.UUID, assignment_id: uuid.UUID, *, actor: StaffContext
    ) -> RoomRead:
        return self._room(
            "release", tenant_id=tenant_id, assignment_id=assignment_id, actor_id=actor.id
        )

    async def handover(
        self,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        *,
        new_staff_id: uuid.UUID,
        actor: StaffContext,
    ) -> RoomRead:
        return self._room(
            "handover",
            tenant_id=tenant_id,
            assignment_id=assignment_id,
            new_staff_id=new_staff_id,
            actor_id=actor.id,
        )

    async def add_dress(
        self,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        *,
        dress_id: uuid.UUID,
        size_label: str | None,
        actor: StaffContext,
    ) -> RoomRead:
        return self._room(
            "add_dress",
            tenant_id=tenant_id,
            assignment_id=assignment_id,
            dress_id=dress_id,
            size_label=size_label,
            actor_id=actor.id,
        )

    async def remove_dress(
        self,
        tenant_id: uuid.UUID,
        assignment_id: uuid.UUID,
        binding_id: uuid.UUID,
        *,
        actor: StaffContext,
    ) -> RoomRead:
        return self._room(
            "remove_dress",
            tenant_id=tenant_id,
            assignment_id=assignment_id,
            binding_id=binding_id,
            actor_id=actor.id,
        )

    # --- F58: the five dispatch methods, in D11's order ---------------------

    async def take_next(
        self,
        tenant_id: uuid.UUID,
        room_id: uuid.UUID,
        *,
        staff_user_id: uuid.UUID | None,
        actor: StaffContext,
    ) -> DispatchRead:
        return self._dispatch(
            "take_next",
            tenant_id=tenant_id,
            room_id=room_id,
            staff_user_id=staff_user_id,
            actor_id=actor.id,
        )

    async def assign(
        self,
        tenant_id: uuid.UUID,
        room_id: uuid.UUID,
        *,
        queue_ticket_id: uuid.UUID,
        staff_user_id: uuid.UUID | None,
        actor: StaffContext,
    ) -> DispatchRead:
        return self._dispatch(
            "assign",
            tenant_id=tenant_id,
            room_id=room_id,
            queue_ticket_id=queue_ticket_id,
            staff_user_id=staff_user_id,
            actor_id=actor.id,
        )

    async def call(
        self, tenant_id: uuid.UUID, ticket_id: uuid.UUID, *, actor: StaffContext
    ) -> WaitlistRead:
        return self._queue("call", tenant_id=tenant_id, ticket_id=ticket_id, actor_id=actor.id)

    async def skip(
        self,
        tenant_id: uuid.UUID,
        ticket_id: uuid.UUID,
        *,
        seen_skip_count: int,
        actor: StaffContext,
    ) -> WaitlistRead:
        return self._queue(
            "skip",
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            seen_skip_count=seen_skip_count,
            actor_id=actor.id,
        )

    async def remove(
        self, tenant_id: uuid.UUID, ticket_id: uuid.UUID, *, actor: StaffContext
    ) -> WaitlistRead:
        return self._queue("remove", tenant_id=tenant_id, ticket_id=ticket_id, actor_id=actor.id)

    def _dispatch(self, method: str, **kwargs: Any) -> DispatchRead:
        self._record(method, **kwargs)
        if self.raises is not None:
            raise self.raises
        if self.missing:
            raise DomainNotFoundError("fitting_room")
        return self.dispatch

    def _queue(self, method: str, **kwargs: Any) -> WaitlistRead:
        self._record(method, **kwargs)
        if self.raises is not None:
            raise self.raises
        if self.missing:
            raise DomainNotFoundError("queue_ticket")
        return self.waitlist

    # --- F37: the five sos methods, in D9's order ---------------------------

    async def sos(self, tenant_id: uuid.UUID, *, actor: StaffContext) -> SosListRead:
        self._record("sos", tenant_id=tenant_id, actor_id=actor.id)
        if self.raises is not None:
            raise self.raises
        return SosListRead(alerts=self.sos_alerts, server_now=SERVER_NOW)

    async def raise_sos(
        self,
        tenant_id: uuid.UUID,
        *,
        target_staff_user_id: uuid.UUID | None,
        fitting_room_assignment_id: uuid.UUID | None,
        note: str | None,
        actor: StaffContext,
    ) -> RaisedSos:
        self._record(
            "raise_sos",
            tenant_id=tenant_id,
            target_staff_user_id=target_staff_user_id,
            fitting_room_assignment_id=fitting_room_assignment_id,
            note=note,
            actor_id=actor.id,
        )
        if self.raises is not None:
            raise self.raises
        return RaisedSos(sos=self.sos_read, rerouted=self.rerouted)

    async def accept_sos(
        self, tenant_id: uuid.UUID, alert_id: uuid.UUID, *, actor: StaffContext
    ) -> SosRead:
        return self._sos("accept_sos", tenant_id=tenant_id, alert_id=alert_id, actor_id=actor.id)

    async def resolve_sos(
        self, tenant_id: uuid.UUID, alert_id: uuid.UUID, *, actor: StaffContext
    ) -> SosRead:
        return self._sos("resolve_sos", tenant_id=tenant_id, alert_id=alert_id, actor_id=actor.id)

    async def cancel_sos(
        self, tenant_id: uuid.UUID, alert_id: uuid.UUID, *, actor: StaffContext
    ) -> SosRead:
        return self._sos("cancel_sos", tenant_id=tenant_id, alert_id=alert_id, actor_id=actor.id)

    def _sos(self, method: str, **kwargs: Any) -> SosRead:
        self._record(method, **kwargs)
        if self.raises is not None:
            raise self.raises
        if self.missing:
            raise DomainNotFoundError("sos_alert")
        return self.sos_read

    async def dresses(self, tenant_id: uuid.UUID) -> DressPickerRead:
        self._record("dresses", tenant_id=tenant_id)
        if self.raises is not None:
            raise self.raises
        return self.dress_picker

    async def clients(self, tenant_id: uuid.UUID) -> ClientPickerRead:
        self._record("clients", tenant_id=tenant_id)
        if self.raises is not None:
            raise self.raises
        return self.client_picker

    def _record(self, method: str, **kwargs: Any) -> None:
        self.calls.append({"method": method, **kwargs})

    def _room(self, method: str, **kwargs: Any) -> RoomRead:
        self._record(method, **kwargs)
        if self.raises is not None:
            raise self.raises
        if self.missing:
            raise DomainNotFoundError("fitting_room")
        return self.room_read


async def _null_resolver(slug: str) -> TenantContext | None:
    return None


def _leaf_routes(node: Any) -> Iterator[Any]:
    """FastAPI wraps an included router in `_IncludedRouter` rather than
    flattening it — recurse through `original_router` or the walk sees only the
    docs routes and passes vacuously. Duplicated from test_staff_role_gating.py
    rather than imported: that module imports THIS one, and the cycle would be
    the fix that breaks collection."""
    for route in getattr(node, "routes", []):
        inner = getattr(route, "original_router", None)
        if inner is not None:
            yield from _leaf_routes(inner)
            continue
        yield route


def _client(
    fake: FakeFloorService,
    *,
    authed: bool = True,
    role: str = StaffRole.OWNER.value,
    staff_id: uuid.UUID | None = None,
) -> TestClient:
    async def _resolver(slug: str) -> TenantContext | None:
        return TENANT if slug == "bella" else None

    app = create_app(resolver=_resolver)
    auth = FakeAuthService(role, staff_id)
    app.state.auth_service = auth
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=3, window_seconds=900, clock=time.monotonic
    )
    # app.state, not dependency_overrides: get_floor_service reads app.state
    # directly, the way every other console dependency does.
    app.state.floor_service = fake
    app.dependency_overrides[get_auth_service] = lambda: auth
    client = TestClient(app, base_url="http://bella.localtest.me")
    if authed:
        client.cookies.set("boutique_session", TOKEN, domain="bella.localtest.me")
    return client


# --- wiring, authentication and the role gate ---


def test_every_route_requires_authentication() -> None:
    fake = FakeFloorService()
    with _client(fake, authed=False) as client:
        for method, path, body in FLOOR_ROUTES:
            resp = client.request(method, path, json=body)
            assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "NOT_AUTHENTICATED"
    assert fake.floor_calls == []
    assert fake.toggle_calls == []
    assert fake.calls == []


def test_the_route_table_names_every_live_floor_route() -> None:
    """⚠ THE ANTI-VACUITY HALF, and it is not decoration — without it the walks
    below only prove that every row this table NAMES exists. A row silently
    MISSING is invisible: the route ships ungated-by-this-module, all thirteen
    tests pass, and the count in the docstring above becomes a claim nobody
    checks. (Verified by mutation: deleting `GET /clients` from the table leaves
    this module green without this test.)

    `FLOOR_OPEN` in test_staff_role_gating.py carries the same guard for the same
    reason, in its own comment.
    """
    app = create_app(resolver=_null_resolver)
    live = {
        (method, getattr(route, "path", ""))
        for route in _leaf_routes(app)
        for method in (getattr(route, "methods", None) or ())
        if getattr(route, "path", "").startswith("/manage/floor")
    }
    assert len(live) == 23, sorted(live)
    assert len({(method, path) for method, path, _ in FLOOR_ROUTES}) == len(FLOOR_ROUTES)
    assert len(FLOOR_ROUTES) == len(live), (
        f"the route table has {len(FLOOR_ROUTES)} rows for {len(live)} live routes: {sorted(live)}"
    )


def test_every_route_is_wired_and_reaches_the_service() -> None:
    """SEVEN routers now mount prefix="/manage": a path collision would silently
    shadow, and a 404 here is what catches it.

    TWENTY-THREE rows after F58 and F37, and the count comes from D11's and D9's
    tables rather than from prose — a table sized by counting sentences reds this walk on a 404 the
    first time it runs."""
    for method, path, body in FLOOR_ROUTES:
        fake = FakeFloorService()
        with _client(fake) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{method} {path} → {resp.status_code} {resp.text}"
        assert fake.calls, f"{method} {path} never reached the service"


@pytest.mark.parametrize("role", ALL_ROLES)
def test_all_five_roles_reach_every_open_floor_route(role: str) -> None:
    """⚠ The ONLY router in the codebase admitting more than two roles, and the
    gate is spelled `require_role(*StaffRole)` so this test covers a sixth role
    the day one is added. The floor payload carries at most one customer name per
    occupied room and never the day book, which is what makes that safe — plus
    test_the_floor_roles_reach_exactly_the_floor_routes, which pins these three
    roles OUT of every other /manage route.
    """
    for method, path, body in FLOOR_OPEN_ROUTES:
        fake = FakeFloorService()
        with _client(fake, role=role) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{role} {method} {path} → {resp.status_code}"


@pytest.mark.parametrize(
    "role", [role.value for role in (StaffRole.OWNER, StaffRole.SHIFT_MANAGER)]
)
def test_the_two_elevated_roles_reach_the_four_tightened_routes(role: str) -> None:
    for method, path, body in FLOOR_TIGHTENED_ROUTES:
        fake = FakeFloorService()
        with _client(fake, role=role) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 200, f"{role} {method} {path} → {resp.status_code}"


@pytest.mark.parametrize(
    "role",
    [
        StaffRole.RECEPTION.value,
        StaffRole.SALES_ASSISTANT.value,
        StaffRole.SEAMSTRESS.value,
    ],
)
def test_a_floor_role_is_refused_the_registry_and_the_handover_before_the_service(
    role: str,
) -> None:
    """The per-route `require_role(OWNER, SHIFT_MANAGER)` composing to an
    INTERSECTION with the router's five (`auth/dependencies.py:44-45`).

    Handover is in here rather than in the service, and the refusal landing
    BEFORE the service is the whole reason: a role predicate that depends on
    nothing about the target is what `RoleGate` is, and putting it in the
    service would force `FLOOR_OPEN` to assert that a seamstress may reach a
    route she always 403s on."""
    for method, path, body in FLOOR_TIGHTENED_ROUTES:
        fake = FakeFloorService()
        with _client(fake, role=role) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 403, f"{role} {method} {path} → {resp.status_code}"
        assert resp.json() == NOT_AUTHORIZED_BODY
        assert fake.calls == [], f"{role} {method} {path} reached the service"


def test_an_unknown_role_is_refused_with_the_exact_generic_body() -> None:
    """Fails closed even though the gate names every role the product has: a role
    string the enum does not know is still not admitted."""
    for method, path, body in FLOOR_ROUTES:
        fake = FakeFloorService()
        with _client(fake, role=UNKNOWN_ROLE) as client:
            resp = client.request(method, path, json=body)
        assert resp.status_code == 403
        assert resp.json() == NOT_AUTHORIZED_BODY
        assert fake.floor_calls == []
        assert fake.toggle_calls == []
        assert fake.calls == []


@pytest.mark.parametrize(
    ("method", "path", "body"), FLOOR_ROUTES, ids=[f"{m}-{p}" for m, p, _ in FLOOR_ROUTES]
)
def test_no_floor_response_is_cached(method: str, path: str, body: dict[str, Any] | None) -> None:
    """Router-level `_no_store`, so a route added here later cannot forget it. A
    cached floor in a shared browser would show one boutique's staff to the next
    person who opens it — and a stale card is worse than none on a screen whose
    whole purpose is being current."""
    fake = FakeFloorService()
    with _client(fake) as client:
        resp = client.request(method, path, json=body)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"


# --- the trust path ---


def test_every_handler_passes_the_host_resolved_tenant() -> None:
    """`get_current_tenant(request)` is host-derived; StaffContext.tenant_id is
    session-derived. The fake makes them disagree, so a handler reaching for the
    session's id fails here.

    All EIGHTEEN, not the three F57 shipped: the ten new handlers each spell
    `get_current_tenant(request)` themselves, and a copy-paste that reached for
    `staff.tenant_id` instead would be invisible in production (the two agree) and
    catastrophic in a cross-tenant session."""
    fake = FakeFloorService()
    with _client(fake) as client:
        for method, path, body in FLOOR_ROUTES:
            assert client.request(method, path, json=body).status_code == 200

    assert fake.floor_calls == [TENANT.id]
    assert [call["tenant_id"] for call in fake.calls] == [TENANT.id] * len(FLOOR_ROUTES)


def test_no_floor_module_still_claims_the_payload_carries_zero_customer_data() -> None:
    """⚠ Three shipped comments stated as a FACT that the floor payload carries
    ZERO customer data, and one of them is the stated justification for the only
    router in the product admitting five roles. F36 puts a client label on that
    payload — inside `StaffCard` itself — so the claim is false, and a false
    comment on a security rationale is worse than never having written one.

    Pinned as a text assertion because nothing else can see it: every runtime
    test passes either way.

    ⚠ **F36's REPLACEMENT is now false too, and the positive assertion alone
    could not see that.** "at most one name per occupied room" was true of F36's
    payload and is not true of F58's: WAITLIST_LIMIT is 100, and every waiting
    row additionally carries F33's position-page capability. The guard was
    satisfied by the stale sentence because that sentence CONTAINS the phrase
    "minimum customer datum" — so a module could keep the falsified clause as its
    stated rationale and stay green, which is exactly what `service.py`'s module
    docstring did.

    The rule is not that the phrase is banned: `router.py` and `service.py.floor`
    both QUOTE it, correctly, as a claim that was once made and is no longer
    true. The rule is that it may only ever appear QUOTED. Counting the quoted
    occurrences against all of them says that in one line and bites on the next
    module that asserts it bare."""
    falsified = "at most one name per occupied room"
    for module in (app_router, app_service, app_schemas):
        source = inspect.getsource(module)
        assert "ZERO customer data" not in source, module.__name__
        assert "no customer data" not in source, module.__name__
        assert "minimum customer datum" in source, module.__name__
        assert source.count(falsified) == source.count(f'"{falsified}"'), module.__name__


def test_the_target_comes_from_the_path_and_the_actor_from_the_session() -> None:
    """⚠ The two axes must come from DIFFERENT places, and this is where that is
    observable over HTTP. If the handler ever passed the path id as the actor,
    `staff_id == actor.id` would be trivially true and every staffer could toggle
    anybody — the D6 check would still be present and would always pass."""
    fake = FakeFloorService()
    with _client(fake, role=StaffRole.SEAMSTRESS.value) as client:
        assert client.post(START_PATH).status_code == 200

    assert fake.toggle_calls == [
        {"verb": "start", "tenant_id": TENANT.id, "staff_id": TARGET_ID, "actor_id": STAFF_ID}
    ]
    assert TARGET_ID != STAFF_ID


def test_each_toggle_reaches_its_own_service_method() -> None:
    fake = FakeFloorService()
    with _client(fake) as client:
        client.post(START_PATH)
        client.post(END_PATH)
    assert [call["verb"] for call in fake.toggle_calls] == ["start", "end"]


# --- the wire shape ---


def test_the_floor_payload_is_an_envelope_with_one_card_per_live_staffer() -> None:
    """An ENVELOPE, not a bare array: F36 added the rooms and F58 adds the
    waitlist to this same payload, and a bare array would have made the first of
    them a breaking change on a screen that polls every five seconds.

    `rooms` and `server_now` are F36's two new envelope keys. `server_now` is the
    ONE field the console's «כבר 42 דק'» is computed against: a server-computed
    minute count is stale the instant it is serialised, and a device-clock one is
    wrong by however far a boutique tablet has drifted.
    """
    fake = FakeFloorService()
    with _client(fake) as client:
        body = client.get(FLOOR_PATH).json()

    assert body == {
        "staff": [
            {
                "id": str(STAFF_ID),
                "display_name": "דנה כהן",
                "role": "owner",
                "status": "available",
                "break_started_at": None,
                "occupancy": None,
            },
            {
                "id": str(TARGET_ID),
                "display_name": "נועה לוי",
                "role": "seamstress",
                "status": "break",
                "break_started_at": BREAK_BEGAN.isoformat().replace("+00:00", "Z"),
                "occupancy": None,
            },
        ],
        "rooms": [],
        "server_now": SERVER_NOW.isoformat().replace("+00:00", "Z"),
        # F58's one new envelope key, and the EMPTY case is the one asserted
        # here on purpose: a bridal boutique's queue is empty most of the day,
        # and «אין ממתינות בתור» has to be a quiet answer rather than a broken
        # one. The populated shape has its own test below.
        "waitlist": {"entries": [], "truncated": False},
    }


def test_the_extended_payload_renders_one_occupied_and_one_free_room() -> None:
    """The whole of D11's added shape, as a LITERAL — the tile, its gowns, the
    client label resolved at read time, and the same fact denormalised onto the
    holder's staff card.

    The free room's `assignment` is `null` rather than absent, and the occupied
    room's `staff_display_name` is a real name rather than an id: the person
    reading this screen is standing in a corridor and needs to know who is in
    room 1, not which uuid is.
    """
    free_id = uuid.uuid4()
    occupied = _room_row(occupied=True, label="חדר 1")
    free = _room_row(room_id=free_id, label="חדר 2", sort_order=1)
    binding = FittingAssignmentDress(
        tenant_id=TENANT.id,
        fitting_room_assignment_id=ASSIGNMENT_ID,
        dress_id=DRESS_ID,
        dress_name="שמלה 47",
        dress_size="38",
    )
    binding.id = BINDING_ID

    fake = FakeFloorService()
    fake.room_rows = [occupied, free]
    fake.occupancy_by_staff_id = {TARGET_ID: occupied}
    fake.bindings = {ASSIGNMENT_ID: [binding]}
    with _client(fake) as client:
        body = client.get(FLOOR_PATH).json()

    assert body["rooms"] == [
        {
            "id": str(ROOM_ID),
            "label": "חדר 1",
            "sort_order": 0,
            "is_active": True,
            "assignment": {
                "id": str(ASSIGNMENT_ID),
                "staff_user_id": str(TARGET_ID),
                "staff_display_name": "נועה לוי",
                "staff_role": "seamstress",
                "client_label": "מיכל",
                "booking_id": None,
                "assigned_at": BREAK_BEGAN.isoformat().replace("+00:00", "Z"),
                "dresses": [
                    {
                        "id": str(BINDING_ID),
                        "dress_id": str(DRESS_ID),
                        "dress_name": "שמלה 47",
                        "dress_size": "38",
                    }
                ],
            },
        },
        {
            "id": str(free_id),
            "label": "חדר 2",
            "sort_order": 1,
            "is_active": True,
            "assignment": None,
        },
    ]
    assert body["server_now"] == SERVER_NOW.isoformat().replace("+00:00", "Z")
    # The holder's card says `occupied`, and the two derivations cannot disagree
    # because they come from one argument.
    holder = next(card for card in body["staff"] if card["id"] == str(TARGET_ID))
    assert holder["status"] == "occupied"
    assert holder["occupancy"] == {
        "assignment_id": str(ASSIGNMENT_ID),
        "fitting_room_id": str(ROOM_ID),
        "room_label": "חדר 1",
        "client_label": "מיכל",
        "assigned_at": BREAK_BEGAN.isoformat().replace("+00:00", "Z"),
    }


def test_every_mutation_answers_the_same_room_shape() -> None:
    """ONE shape for eight routes, so the panel patches a tile in place from the
    server's own row and cannot disagree with itself. A route that grew its own
    answer would show up here as a key-set difference."""
    fake = FakeFloorService()
    fake.room_read = RoomRead(row=_room_row(occupied=True), bindings=[])
    fake.dispatch = DispatchRead(room=fake.room_read, waitlist=fake.waitlist)
    keys = {"id", "label", "sort_order", "is_active", "assignment"}
    with _client(fake) as client:
        for method, path, body in FLOOR_ROUTES:
            if (method, path) in {("GET", FLOOR_PATH), ("DELETE", ROOM_PATH)} or path in {
                DRESS_LIST_PATH,
                CLIENT_LIST_PATH,
                START_PATH,
                END_PATH,
                # F58's three queue verbs answer a `Waitlist` and no tile: they
                # act on a ROW, and the row is gone from the list they answer
                # with. They have their own shape assertion below.
                CALL_PATH,
                SKIP_PATH,
                REMOVE_PATH,
                # F37's five answer an ALERT, not a room. Their own one-shape
                # assertion is test_sos_api.py's, by set equality.
                SOS_PATH,
                SOS_ACCEPT_PATH,
                SOS_RESOLVE_PATH,
                SOS_CANCEL_PATH,
            }:
                continue
            answered = client.request(method, path, json=body).json()
            # The two dispatch verbs answer the tile AND the queue, so the tile
            # is one level down — and it is the SAME shape, which is the point.
            if path in {TAKE_NEXT_PATH, ASSIGN_PATH}:
                assert set(answered) == {"room", "waitlist"}, f"{method} {path}"
                answered = answered["room"]
            assert set(answered) == keys, f"{method} {path} answered {sorted(answered)}"
            assert answered["assignment"] is not None


def test_a_room_delete_answers_the_shipped_ok_envelope() -> None:
    fake = FakeFloorService()
    with _client(fake) as client:
        resp = client.delete(ROOM_PATH)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_the_dress_picker_answers_names_and_sizes_and_nothing_else() -> None:
    """Strictly less than the boutique's own storefront already publishes to an
    anonymous visitor: no price, no description, no media, no `reserved` flag, no
    stock quantity. That is the whole disclosure argument for answering it on a
    router the catalog's own gate would refuse."""
    dress = Dress(tenant_id=TENANT.id, name="שמלה 47", sort_order=0)
    dress.id = DRESS_ID
    fake = FakeFloorService()
    fake.dress_picker = DressPickerRead(
        dresses=[dress], sizes_by_dress_id={DRESS_ID: ["38", "40"]}, truncated=True
    )
    with _client(fake) as client:
        body = client.get(DRESS_LIST_PATH).json()
    assert body == {
        "dresses": [{"id": str(DRESS_ID), "name": "שמלה 47", "sizes": ["38", "40"]}],
        "truncated": True,
    }


def test_the_client_picker_answers_a_booking_id_a_label_and_a_time_and_nothing_else() -> None:
    """⚠ The route without which `booking_id` has no producer anywhere in the
    console — and the one whose key set is the minimisation claim itself. No
    phone, no notes, no dress, no size, no status, no manage token, no
    `customer_id`: a seamstress walking a bride to room 2 needs to be able to say
    which bride, and nothing more."""
    booking_id, customer_id = uuid.uuid4(), uuid.uuid4()
    booking = Booking(
        tenant_id=TENANT.id,
        customer_id=customer_id,
        appointment_type_id=uuid.uuid4(),
        starts_at=STARTS_AT,
        seat_index=1,
        status="confirmed",
        terms_version_accepted=1,
        terms_accepted_at=STARTS_AT,
        appointment_type_name="מדידה",
    )
    booking.id = booking_id
    fake = FakeFloorService()
    fake.client_picker = ClientPickerRead(
        bookings=[booking], names_by_customer_id={customer_id: "מיכל"}, truncated=False
    )
    with _client(fake) as client:
        body = client.get(CLIENT_LIST_PATH).json()
    assert body == {
        "clients": [
            {
                "booking_id": str(booking_id),
                "client_label": "מיכל",
                "starts_at": STARTS_AT.isoformat().replace("+00:00", "Z"),
            }
        ],
        "truncated": False,
    }
    assert set(body["clients"][0]) == {"booking_id", "client_label", "starts_at"}


def test_an_erased_customer_leaves_the_picker_row_anonymous() -> None:
    """The label is resolved at read time from the live rows, so an Amendment 13
    erasure renders an anonymous row rather than quietly preserving a name."""
    booking = Booking(
        tenant_id=TENANT.id,
        customer_id=uuid.uuid4(),
        appointment_type_id=uuid.uuid4(),
        starts_at=STARTS_AT,
        seat_index=1,
        status="confirmed",
        terms_version_accepted=1,
        terms_accepted_at=STARTS_AT,
        appointment_type_name="מדידה",
    )
    booking.id = uuid.uuid4()
    fake = FakeFloorService()
    fake.client_picker = ClientPickerRead(
        bookings=[booking], names_by_customer_id={}, truncated=False
    )
    with _client(fake) as client:
        body = client.get(CLIENT_LIST_PATH).json()
    assert body["clients"][0]["client_label"] is None


def test_the_claim_reads_the_body_as_the_target_and_the_session_as_the_actor() -> None:
    """⚠ The FIRST body in the product carrying a target staff id, which is the
    exact shape that turns "any staffer on herself" into "any staffer on anyone"
    if a route ever reads it as the caller's identity. It is passed through as
    `staff_user_id`; `actor_id` comes from the session and they must differ."""
    booking_id = uuid.uuid4()
    fake = FakeFloorService()
    with _client(fake, role=StaffRole.SEAMSTRESS.value) as client:
        assert (
            client.post(
                CLAIM_PATH, json={"staff_user_id": str(TARGET_ID), "booking_id": str(booking_id)}
            ).status_code
            == 200
        )
    assert fake.calls == [
        {
            "method": "claim",
            "tenant_id": TENANT.id,
            "room_id": ROOM_ID,
            "staff_user_id": TARGET_ID,
            "booking_id": booking_id,
            "actor_id": STAFF_ID,
        }
    ]
    assert TARGET_ID != STAFF_ID


def test_an_empty_claim_body_names_neither_a_staffer_nor_a_booking() -> None:
    """One tap if she does not care which bride — the anonymous visit is the
    DEFAULT, not an edge case."""
    fake = FakeFloorService()
    with _client(fake) as client:
        assert client.post(CLAIM_PATH, json={}).status_code == 200
    assert fake.calls[0]["staff_user_id"] is None
    assert fake.calls[0]["booking_id"] is None


def test_every_room_body_refuses_an_unknown_key_over_http() -> None:
    """`ForbidExtraModel` is the house form, and this is where it is observable:
    a typo'd key silently ignored on a registry write is a label the owner
    thinks she changed."""
    fake = FakeFloorService()
    with _client(fake) as client:
        for path, body in (
            (ROOMS_PATH, {"label": "חדר 3", "bogus": 1}),
            (CLAIM_PATH, {"bogus": 1}),
            (HANDOVER_PATH, {"staff_user_id": str(TARGET_ID), "bogus": 1}),
            (BIND_PATH, {"dress_id": str(DRESS_ID), "bogus": 1}),
        ):
            resp = client.post(path, json=body)
            assert resp.status_code == 400, f"{path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
        resp = client.patch(ROOM_PATH, json={"label": "חדר 4", "bogus": 1})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    assert fake.calls == []


def test_a_toggle_answers_one_card_and_not_the_whole_floor() -> None:
    """⚠ SIX keys, and it stays a SET EQUALITY. `occupancy` is F36's; the
    assertion is what catches a SEVENTH field arriving unreviewed on a payload
    all five roles can open, which on this particular payload is the whole of the
    no-customer-data argument mechanised."""
    fake = FakeFloorService()
    with _client(fake) as client:
        body = client.post(START_PATH).json()
    assert set(body) == {
        "id",
        "display_name",
        "role",
        "status",
        "break_started_at",
        "occupancy",
    }
    assert body["status"] == "break"


def test_a_break_route_answers_occupied_when_the_staffer_is_in_a_room() -> None:
    """⚠ The status and the occupancy object are derived from ONE argument, so
    they cannot disagree — a card saying «פנויה» about a staffer standing in room
    2 is the lie this whole field exists to prevent, one word over."""
    fake = FakeFloorService()
    fake.occupancy = RoomRow(
        room_id=uuid.uuid4(),
        label="חדר 2",
        sort_order=1,
        is_active=True,
        assignment_id=uuid.uuid4(),
        staff_user_id=TARGET_ID,
        staff_display_name="נועה לוי",
        staff_role=StaffRole.SEAMSTRESS.value,
        booking_id=None,
        client_label="מיכל",
        assigned_at=BREAK_BEGAN,
    )
    with _client(fake) as client:
        body = client.post(START_PATH).json()

    assert body["status"] == "occupied"
    assert body["occupancy"]["room_label"] == "חדר 2"
    assert body["occupancy"]["client_label"] == "מיכל"
    # The break timestamp stays on the wire regardless, so the card can still say
    # she forgot to end one.
    assert body["break_started_at"] is not None


def test_no_card_carries_an_email_or_any_credential() -> None:
    """A card is a name, a role and a status. `email` is the key a later reader
    reaches for as a stable identifier — `id` is the key, and the address of
    every member of staff is not something a seamstress needs to see who is on a
    break."""
    fake = FakeFloorService()
    with _client(fake) as client:
        body = client.get(FLOOR_PATH).json()
    keys = {key for card in body["staff"] for key in card}
    assert keys & {"email", "password_hash", "tenant_id", "deleted_at"} == set()


def test_the_card_status_wire_literals_are_exactly_available_break_and_occupied() -> None:
    """SET EQUALITY, and it stays one. F36 is the PR that gives `occupied` a
    writer — an open `fitting_room_assignments` row — so the literal and its
    producer land together, which is the whole of the ScheduledMessageKind rule.
    A FOURTH value arriving without one fails here, in the module that pins the
    WIRE, as well as in test_floor_service.py."""
    assert {status.value for status in StaffCardStatus} == {"available", "break", "occupied"}


# --- the error table ---


def test_a_missing_target_is_a_404() -> None:
    fake = FakeFloorService(missing=True)
    with _client(fake) as client:
        for path in (START_PATH, END_PATH):
            resp = client.post(path)
            assert resp.status_code == 404
            assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_a_room_occupied_conflict_is_a_409_that_names_the_occupant() -> None:
    """The ruling requires the 409 to NAME the current occupant, and `message`
    is English prose the console never renders for a MAPPED code — so the datum
    has to travel in `details` or it is unreachable by the UI."""
    fake = FakeFloorService(raises=RoomOccupiedError({"staff_display_name": "דנה"}))
    with _client(fake) as client:
        resp = client.post(START_PATH)
    assert resp.status_code == 409
    assert resp.json() == {
        "error": {
            "code": "ROOM_OCCUPIED",
            "message": "This fitting room is already claimed.",
            "details": {"staff_display_name": "דנה"},
        }
    }


def test_a_staff_occupied_conflict_is_a_409_that_names_the_room() -> None:
    fake = FakeFloorService(raises=StaffOccupiedError({"room_label": "חדר 2"}))
    with _client(fake) as client:
        resp = client.post(START_PATH)
    assert resp.status_code == 409
    assert resp.json() == {
        "error": {
            "code": "STAFF_OCCUPIED",
            "message": "That staff member is already in a fitting room.",
            "details": {"room_label": "חדר 2"},
        }
    }


@pytest.mark.parametrize(
    ("error", "code"),
    [(RoomOccupiedError, "ROOM_OCCUPIED"), (StaffOccupiedError, "STAFF_OCCUPIED")],
)
def test_an_occupancy_conflict_omits_details_entirely_when_nobody_is_there(
    error: type[Exception], code: str
) -> None:
    """⚠ The key is ABSENT, never `{"staff_display_name": null}`.

    The loser blocks on the winner's uncommitted index key and gets the
    violation when the winner commits; in that gap the winner can release, and
    there is then no occupant to name. A null would break the console's
    `Record<string, string>` type and render «{{name}} כבר בחדר הזה.» with an
    empty interpolation on a legally binding surface.
    """
    with _client(FakeFloorService(raises=error())) as client:
        resp = client.post(START_PATH)
    assert resp.status_code == 409
    assert resp.json() == {"error": {"code": code, "message": resp.json()["error"]["message"]}}
    assert "details" not in resp.json()["error"]


def test_no_other_error_body_in_main_carries_a_details_key() -> None:
    """`details` extends the shipped `{"code", "message"}` envelope, and the set
    of bodies that carry it is a thing a reviewer should be able to enumerate.
    Every other module-level `*_BODY` in `main.py` is a frozen two-key dict, and
    the two new ones are frozen two-key dicts too — the third key is built at
    RAISE time by the handler, never stored."""
    bodies = {
        name: value
        for name, value in vars(app_main).items()
        if name.endswith("_BODY") and isinstance(value, dict)
    }
    assert {
        "ROOM_OCCUPIED_BODY",
        "STAFF_OCCUPIED_BODY",
        "QUEUE_TICKET_NOT_WAITING_BODY",
        "QUEUE_TICKET_CHANGED_BODY",
        "SOS_ALREADY_ACCEPTED_BODY",
        "SOS_CLOSED_BODY",
    } <= set(bodies)
    for name, body in bodies.items():
        assert set(body["error"]) == {"code", "message"}, name


def test_every_mutating_verb_with_a_mismatched_origin_is_refused() -> None:
    """All NINETEEN mutating routes ARE fenced — CsrfOriginMiddleware gates on
    `request.method in MUTATING_METHODS` (csrf.py:15,48), which is a METHOD test
    and not a path list, so the eight F36 adds, the five F58 adds and the four
    F37 adds are fenced by construction. That is asserted rather than assumed because
    "by construction" is the sentence that stops being true the day somebody adds
    a GET that writes."""
    fake = FakeFloorService()
    mutating = [(m, p, b) for m, p, b in FLOOR_ROUTES if m != "GET"]
    assert len(mutating) == 19
    with _client(fake) as client:
        for method, path, body in mutating:
            resp = client.request(
                method, path, json=body, headers={"origin": "http://evil.localtest.me"}
            )
            assert resp.status_code == 403, f"{method} {path} → {resp.status_code}"
            assert resp.json()["error"]["code"] == "CSRF_ORIGIN_MISMATCH"
    assert fake.toggle_calls == []
    assert fake.calls == []


def test_the_four_floor_reads_with_a_mismatched_origin_are_allowed() -> None:
    """The GETs are NOT fenced, and that asymmetry is asserted rather than
    assumed: CsrfOriginMiddleware fences MUTATING_METHODS only. The protection on
    the four reads is the session cookie and the role gate, alone — and F37's is
    the one that polls every section for a whole shift."""
    fake = FakeFloorService()
    with _client(fake) as client:
        for path in (FLOOR_PATH, DRESS_LIST_PATH, CLIENT_LIST_PATH, SOS_PATH):
            resp = client.get(path, headers={"origin": "http://evil.localtest.me"})
            assert resp.status_code == 200, f"{path} → {resp.status_code}"


# --- F58: the waitlist on the envelope, and the three new 409s ---


def test_the_waitlist_rides_the_same_envelope_and_carries_exactly_eight_keys_per_entry() -> None:
    """⚠ THE SET EQUALITY IS THE POINT. A ninth key arriving on a five-role
    payload that now carries up to a hundred customer names is exactly the change
    that must not happen quietly, and this is the same guard F36 put on
    `StaffCard`.

    `position` is `index + 1` over the SERVER's order and never a second count
    query — two derivations of one number are two chances for the wall, her phone
    and this panel to disagree.
    """
    fake = FakeFloorService()
    fake.waitlist = WaitlistRead(
        entries=[
            WaitlistEntryRead(
                id=TICKET_ID,
                name="נועה בר",
                visit_type="bride",
                arrived_at=STARTS_AT,
                called=True,
                skip_count=1,
                duplicate=True,
            ),
            WaitlistEntryRead(
                id=SECOND_TICKET_ID,
                name="מיכל",
                visit_type="evening",
                arrived_at=BREAK_BEGAN,
                called=False,
                skip_count=0,
                duplicate=False,
            ),
        ],
        truncated=True,
    )
    with _client(fake) as client:
        body = client.get(FLOOR_PATH).json()

    assert body["waitlist"] == {
        "entries": [
            {
                "id": str(TICKET_ID),
                "name": "נועה בר",
                "visit_type": "bride",
                "position": 1,
                "arrived_at": STARTS_AT.isoformat().replace("+00:00", "Z"),
                "called": True,
                "skip_count": 1,
                "duplicate": True,
            },
            {
                "id": str(SECOND_TICKET_ID),
                "name": "מיכל",
                "visit_type": "evening",
                "position": 2,
                "arrived_at": BREAK_BEGAN.isoformat().replace("+00:00", "Z"),
                "called": False,
                "skip_count": 0,
                "duplicate": False,
            },
        ],
        "truncated": True,
    }
    assert set(body["waitlist"]["entries"][0]) == {
        "id",
        "name",
        "visit_type",
        "position",
        "arrived_at",
        "called",
        "skip_count",
        "duplicate",
    }


def test_no_phone_no_consent_and_no_queue_day_reaches_the_payload() -> None:
    """A4, and it is a RECURSIVE scan over the whole serialised envelope rather
    than a look at the keys this module happens to know about.

    The repository's projection DOES select `phone` — D9's duplicate flag groups
    on it — and the service turns it into a boolean and drops it. This is the
    assertion that the drop actually happened, and it is written to survive a
    later feature nesting a new object anywhere in the tree.
    """
    fake = FakeFloorService()
    fake.room_rows = [_room_row(occupied=True)]
    fake.waitlist = WaitlistRead(
        entries=[
            WaitlistEntryRead(
                id=TICKET_ID,
                name="נועה בר",
                visit_type="bride",
                arrived_at=STARTS_AT,
                called=False,
                skip_count=0,
                duplicate=False,
            )
        ],
        truncated=False,
    )
    with _client(fake) as client:
        body = client.get(FLOOR_PATH).json()

    banned_keys = {"phone", "marketing_opt_in_at", "queue_day"}
    israeli_mobile = re.compile(r"^\+972\d{9}$")

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            assert not (banned_keys & set(node)), sorted(banned_keys & set(node))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            assert not israeli_mobile.match(node), node

    walk(body)


@pytest.mark.parametrize(
    ("error", "code", "details", "message"),
    [
        (QueueEmptyError(), "QUEUE_EMPTY", None, "Nobody is waiting in the queue."),
        (
            QueueTicketNotWaitingError({"status": "in_service"}),
            "QUEUE_TICKET_NOT_WAITING",
            {"status": "in_service"},
            "That queue entry is no longer waiting.",
        ),
        (
            QueueTicketChangedError({"skip_count": "1"}),
            "QUEUE_TICKET_CHANGED",
            {"skip_count": "1"},
            "That queue entry changed. Reload.",
        ),
    ],
)
def test_each_new_conflict_is_a_409_carrying_its_own_code(
    error: Exception, code: str, details: dict[str, str] | None, message: str
) -> None:
    """Three codes and not one with a discriminating `details`: three causes,
    three Hebrew sentences and three remedies — take another room / she is
    already being seen / reload and try again — and a `details`-key sniff in the
    console is a worse place for that branch than an error code.

    ⚠ MUTATION PERFORMED: register the two `_OccupiedError` subclasses on the
    shared BASE instead of on themselves → Starlette resolves on the MRO, both
    answer one code, and two of these three parametrisations red.
    """
    with _client(FakeFloorService(raises=error)) as client:
        resp = client.post(START_PATH)

    assert resp.status_code == 409
    expected: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        expected["details"] = details
    assert resp.json() == {"error": expected}


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (QueueTicketNotWaitingError, "QUEUE_TICKET_NOT_WAITING"),
        (QueueTicketChangedError, "QUEUE_TICKET_CHANGED"),
    ],
)
def test_the_two_new_detailed_conflicts_omit_details_entirely_when_they_have_none(
    error: type[Exception], code: str
) -> None:
    """The key is ABSENT, never null — `_occupied_body`'s rule, inherited rather
    than re-implemented. A null would break the console's `Record<string, string>`
    type on a legally binding surface."""
    with _client(FakeFloorService(raises=error())) as client:
        resp = client.post(START_PATH)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == code
    assert "details" not in resp.json()["error"]


def test_the_queue_empty_body_can_never_grow_a_details_key() -> None:
    """⚠ It is a plain frozen body rather than an `_occupied_body` caller, and
    that is the assertion: there is nobody to name on an empty queue, so the
    handler has no third key to build and `QueueEmptyError` carries no `details`
    attribute at all."""
    assert not hasattr(QueueEmptyError(), "details")
    assert set(app_main.QUEUE_EMPTY_BODY["error"]) == {"code", "message"}


def test_every_spec_error_code_is_asserted() -> None:
    """Mechanical completeness, re-derived from live responses rather than from a
    literal — and SET EQUALITY, so an error code added without a test here fails
    immediately.

    NINE after F37. `VALIDATION_ERROR` became reachable on this router for the
    first time in F36 because the registry takes a body, and the occupancy 409s
    because the claim and the handover can conflict; the two SOS codes arrive
    with the accept and the cancel, each with its own handler block."""
    observed = set()
    with _client(FakeFloorService(), authed=False) as client:
        observed.add(client.get(FLOOR_PATH).json()["error"]["code"])
    with _client(FakeFloorService(), role=UNKNOWN_ROLE) as client:
        observed.add(client.get(FLOOR_PATH).json()["error"]["code"])
    with _client(FakeFloorService(missing=True)) as client:
        observed.add(client.post(START_PATH).json()["error"]["code"])
    with _client(FakeFloorService()) as client:
        observed.add(client.post(ROOMS_PATH, json={"bogus": 1}).json()["error"]["code"])
    with _client(FakeFloorService(raises=RoomOccupiedError())) as client:
        observed.add(client.post(CLAIM_PATH, json={}).json()["error"]["code"])
    with _client(FakeFloorService(raises=StaffOccupiedError())) as client:
        observed.add(
            client.post(HANDOVER_PATH, json={"staff_user_id": str(TARGET_ID)}).json()["error"][
                "code"
            ]
        )
    with _client(FakeFloorService()) as client:
        observed.add(
            client.post(START_PATH, headers={"origin": "http://evil.localtest.me"}).json()["error"][
                "code"
            ]
        )
    for error in (
        QueueEmptyError(),
        QueueTicketNotWaitingError({"status": "removed"}),
        QueueTicketChangedError({"skip_count": "2"}),
    ):
        with _client(FakeFloorService(raises=error)) as client:
            observed.add(client.post(START_PATH).json()["error"]["code"])
    with _client(FakeFloorService(raises=SosAlreadyAcceptedError())) as client:
        observed.add(client.post(SOS_ACCEPT_PATH).json()["error"]["code"])
    with _client(FakeFloorService(raises=SosClosedError())) as client:
        observed.add(client.post(SOS_ACCEPT_PATH).json()["error"]["code"])
    assert observed == SPEC_ERROR_CODES
