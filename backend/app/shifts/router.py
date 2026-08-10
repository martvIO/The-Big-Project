"""Shift templates and the weekly availability window — eight routes on /manage.

**A SIXTH ALL-ROLE ROUTER ON /manage, and it is the SECOND in the codebase that
admits more than two roles** (`floor/router.py` is the first). Router-level so a
route added here later cannot forget the gate, and because
`test_staff_role_gating`'s default-deny walker reads `allowed_roles` off the
router: a /manage router without one is a red build.

**Why a new module rather than a route on an existing router — structural, not
stylistic** (spec D7). `RoleGate` composes by INTERSECTION
(`auth/dependencies.py:44-45`) and the walker yields EVERY gate in the dependency
tree, so a per-route `require_role(*StaffRole)` hung on `boutique/router.py`
(gated OWNER, SHIFT_MANAGER) would still refuse a seamstress. **There is no
per-route widening in this codebase**, which `floor/router.py:73-78` states in
those words. The staff-facing routes therefore cannot live on the boutique router
and cannot live on `auth/staff_router.py` (owner-only) for the same reason.

**What the widening rests on, stated rather than assumed.** The payloads here
carry SHIFT TIMES, WEEK KEYS AND THREE-VALUE ANSWERS — no customer, no phone, no
booking, no money. The one personal datum on any of them is a colleague's DISPLAY
NAME, on two surfaces: `recorded_by_name`, which exists so a staffer can see who
recorded an answer in her name (D5), and `display_name` on the roster-readiness
list, which is ELEVATED-ONLY. A staffer sees her own week and nobody else's.

⚠ **THIS IS NOT AN HOURS-WORKED RECORD AND MUST NEVER BECOME ONE.** The epic's
labour-law row binds every route here: nothing sums a duration, nothing reads
these rows as attendance, and a later feature that does is a review-blocking
drift.

**THREE routes stay open to all five roles and FIVE narrow to owner +
shift_manager**, per-route, composing by intersection. The three open ones are
the staffer's own screen — read the templates, read her week, save it. The five
elevated ones are configuration (the template editor and the seed) and the roster
read, which carries every colleague's name.

⚠ **`PUT /manage/shifts/week/availability` IS OPEN TO ALL FIVE AND ITS REAL RULE
IS TARGET-DEPENDENT** — herself, or elevated on anyone. No `RoleGate` can express
that, so it is open here and refused in the service (`ShiftsService._authorize`,
`floor/service.py:1911-1921`'s exact shape). Its `staff_user_id` names WHOM to
record and never WHO is asking; the acting identity comes from the session cookie
alone.

**The tenant comes from the HOST**, `get_current_tenant(request)`, never
`StaffContext.tenant_id` — the two are equal in practice but are different trust
paths (`dashboard/router.py:17-26` argues this at length). Its `settings` ride
the same object, already bound by the tenancy middleware, so the deadline pair
costs ZERO statements (`AtelierService`'s bands, same rule).

**`_no_store` is a SIXTH local three-line copy**, not an import. The alternative
points the dependency arrow backwards to save three lines;
`auth/staff_router.py:22-27` records the decision.

**No rate limiter**: no /manage router carries one. The five mutating routes ARE
fenced by `CsrfOriginMiddleware` (a method test, so they are fenced by
construction); the three GETs are not, and their protection is the session cookie
and the role gate, alone.

⚠ **The second path segment is `shifts`, which is NEW — so `vite.config.ts`'s
proxy alternation gains it in this same commit.**
`test_spa_serving.py::test_the_manage_dev_proxy_names_every_manage_api_segment`
set-equals the alternation against the live route table's second segments, and a
mismatch breaks only a developer's machine while production, CI and the whole
suite stay green.

**Real HTTP verbs and a path parameter for the target.** The `.claude/rules` RPC
/ `@QueryValue` guidance is Kotlin boilerplate for another codebase; the shipped
/manage convention is real verbs (F15 D7 ruled this, `auth/staff_router.py:27-30`
restates it).
"""

import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth.dependencies import get_current_staff, require_role
from app.auth.service import StaffContext
from app.models.constants import StaffRole
from app.shifts.schemas import (
    CreateAssignmentRequest,
    PublishedRosterResponse,
    PublishRosterRequest,
    RosterShiftResponse,
    RosterWeekResponse,
    SeedTemplatesResponse,
    ShiftTemplateInput,
    ShiftTemplateListResponse,
    ShiftTemplateResponse,
    ShiftWeekResponse,
    SubmitAvailabilityRequest,
    TemplateWriteResponse,
    WeekSubmissionsResponse,
)
from app.shifts.service import ShiftsService
from app.tenancy.middleware import get_current_tenant

NO_STORE = "no-store"


def _no_store(response: Response) -> None:
    response.headers["cache-control"] = NO_STORE


def get_shifts_service(request: Request) -> ShiftsService:
    service: ShiftsService = request.app.state.shifts_service
    return service


router = APIRouter(
    prefix="/manage",
    dependencies=[
        Depends(_no_store),
        Depends(require_role(*StaffRole)),
    ],
)

# Spelled once and hung on five routes. It composes by INTERSECTION with the
# router's five, so it can only narrow — which is exactly what these five need.
ELEVATED = Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER))

Service = Annotated[ShiftsService, Depends(get_shifts_service)]
Staff = Annotated[StaffContext, Depends(get_current_staff)]


# --- templates ---------------------------------------------------------------


@router.get("/shifts/templates")
async def list_templates(
    request: Request, service: Service, staff: Staff
) -> ShiftTemplateListResponse:
    """Open to all five: a staffer cannot answer a week without knowing which
    shifts it has. `future_submission_count` is populated for an elevated reader
    only — see the service."""
    return await service.list_templates(get_current_tenant(request).id, actor=staff)


@router.post("/shifts/templates", status_code=201, dependencies=[ELEVATED])
async def create_template(
    request: Request, service: Service, staff: Staff, body: ShiftTemplateInput
) -> ShiftTemplateResponse:
    return await service.create_template(get_current_tenant(request).id, actor=staff, body=body)


@router.patch("/shifts/templates/{template_id}", dependencies=[ELEVATED])
async def update_template(
    request: Request,
    template_id: uuid.UUID,
    service: Service,
    staff: Staff,
    body: ShiftTemplateInput,
) -> TemplateWriteResponse:
    """A full replace of all five fields (D2), plus D4's invalidation in the same
    transaction. The response carries the count that really moved, which the
    console announces instead of the one its confirm dialog predicted."""
    return await service.update_template(
        get_current_tenant(request).id, template_id, actor=staff, body=body
    )


@router.delete("/shifts/templates/{template_id}", dependencies=[ELEVATED])
async def delete_template(
    request: Request, template_id: uuid.UUID, service: Service, staff: Staff
) -> TemplateWriteResponse:
    return await service.delete_template(get_current_tenant(request).id, template_id, actor=staff)


@router.post("/shifts/templates/seed", dependencies=[ELEVATED])
async def seed_templates(request: Request, service: Service, staff: Staff) -> SeedTemplatesResponse:
    """D3, and it is NEVER triggered by a read — a read path that writes is what
    F37's D6 rejected on principle. It refuses if any live template exists, so a
    half-remembered second press cannot destroy the owner's splits."""
    return await service.seed_templates(get_current_tenant(request).id, actor=staff)


# --- the week ----------------------------------------------------------------


@router.get("/shifts/week")
async def get_week(
    request: Request,
    service: Service,
    staff: Staff,
    week_start: datetime.date | None = None,
) -> ShiftWeekResponse:
    """HER OWN week. `week_start` is optional and defaults to NEXT week (D1); the
    server validates the Sunday-ness and the ±4 window and never trusts the
    client's arithmetic."""
    tenant = get_current_tenant(request)
    return await service.week(
        tenant.id, actor=staff, settings=tenant.settings, week_start=week_start
    )


@router.put("/shifts/week/availability")
async def submit_availability(
    request: Request, service: Service, staff: Staff, body: SubmitAvailabilityRequest
) -> ShiftWeekResponse:
    """⚠ OPEN TO ALL FIVE AT THE GATE, NARROWED IN THE SERVICE. The real rule is
    target-dependent — herself, or elevated on anyone — which no `RoleGate` can
    express, so the 403 comes from `ShiftsService._authorize`."""
    tenant = get_current_tenant(request)
    return await service.submit(tenant.id, actor=staff, settings=tenant.settings, body=body)


@router.get("/shifts/week/submissions", dependencies=[ELEVATED])
async def get_submissions(
    request: Request,
    service: Service,
    week_start: datetime.date | None = None,
) -> WeekSubmissionsResponse:
    """Roster readiness. ELEVATED because it carries every colleague's display
    name and what she said — a staffer's own screen shows her own week and
    nothing about anybody else's."""
    return await service.submissions(get_current_tenant(request).id, week_start=week_start)


# --- F40: the roster ---------------------------------------------------------
#
# FIVE routes on THIS router, not a sixth one: the second path segment is
# `shifts`, which `vite.config.ts`' proxy alternation already carries, so there
# is no new mount, no `main.py` edit and no frontend config change.


@router.get("/shifts/roster", dependencies=[ELEVATED])
async def get_roster(
    request: Request,
    service: Service,
    staff: Staff,
    week_start: datetime.date | None = None,
) -> RosterWeekResponse:
    """The builder. ELEVATED because it carries every colleague's submitted
    state — F39's own reason for gating `/shifts/week/submissions`.

    `week_start` is optional and defaults to NEXT week (F39's `default_week_start`);
    the server validates the Sunday-ness and the ±4 window and never trusts the
    client's arithmetic."""
    return await service.roster(get_current_tenant(request).id, actor=staff, week_start=week_start)


@router.post("/shifts/roster/assignments", dependencies=[ELEVATED])
async def create_assignment(
    request: Request, service: Service, staff: Staff, body: CreateAssignmentRequest
) -> RosterShiftResponse:
    """⚠ 200 ON BOTH PATHS AND NEVER 201. It is an UPSERT on the live
    `(roster, template, staffer)` triple (design F-2), and a route that is
    sometimes a create and sometimes an update, answering two codes, forces the
    client to branch on a status to decide what it just did.

    ⚠ IT ANSWERS THE AFFECTED SHIFT, never the whole week. A whole-week payload
    per tap breaks under the pane's deliberate per-control concurrency: two
    writes in flight from one dialog, the earlier-issued response arriving
    second, and the later assignment silently lost."""
    return await service.assign(get_current_tenant(request).id, actor=staff, body=body)


@router.delete("/shifts/roster/assignments/{assignment_id}", dependencies=[ELEVATED])
async def delete_assignment(
    request: Request, assignment_id: uuid.UUID, service: Service, staff: Staff
) -> RosterShiftResponse:
    """Soft delete, answering the same `RosterShiftResponse` the create does — so
    the pane patches one block in place from the server's own row and cannot
    disagree with itself."""
    return await service.unassign(
        get_current_tenant(request).id, actor=staff, assignment_id=assignment_id
    )


@router.post("/shifts/roster/publish", dependencies=[ELEVATED])
async def publish_roster(
    request: Request, service: Service, staff: Staff, body: PublishRosterRequest
) -> RosterWeekResponse:
    """Idempotent (D7). A publish on a week whose assignment set has not moved
    since the stamp writes nothing and audits nothing, and answers 200 with the
    same payload. THERE IS NO UNPUBLISH and a running week is not special-cased."""
    return await service.publish(
        get_current_tenant(request).id, actor=staff, week_start=body.week_start
    )


@router.get("/shifts/roster/published")
async def get_published_roster(
    request: Request,
    service: Service,
    week_start: datetime.date | None = None,
) -> PublishedRosterResponse:
    """⚠ OPEN TO EVERY ROLE (D13). The floor board already names every colleague,
    a roster discloses nothing new, and a staffer who cannot see the published
    roster cannot plan.

    ⚠ NEVER A 404 FOR AN UNPUBLISHED WEEK (D6). «No roster yet» is a real,
    renderable answer — `{published: false, shifts: []}` — and a 404 would make
    the console branch on a status code to say it."""
    return await service.published(get_current_tenant(request).id, week_start=week_start)
