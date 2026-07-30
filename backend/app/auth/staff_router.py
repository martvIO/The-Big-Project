"""The owner-only staff surface: four routes on /manage.

**A fifth router on /manage.** Registered after owner_booking_router in
create_app(), carrying the same shadowing warning the other four already carry —
five routers now mount this prefix and a duplicated (method, path) would silently
win or lose on include order. `test_staff_api.py`'s ROUTES table is what keeps
that honest.

**Owner-only at ROUTER level, not per route.** The SMC epic's locked table names
exactly two owner-only surfaces: this whole router and POST /manage/terms. Put
router-level, a route added here later cannot forget the gate, and
test_staff_role_gating's default-deny walker reads `allowed_roles` off it — which
is why the four (method, path) templates also have to be named in that module's
OWNER_ONLY set.

**Every handler takes `staff`.** The acting id is what the self-guard compares
and what every audit row carries; the gate above is what refuses, so this is not
a second guard. FastAPI's per-request dependency cache collapses the two to one
resolve_session call.

**`_no_store` is a third local three-line copy**, not an import from
app.booking.owner_router. The alternative points the dependency arrow backwards —
app.auth importing from app.booking — to save three lines, and hoisting it to a
new shared module would touch two shipped files for cosmetics. Recorded so the
duplication reads as a decision.

**Path parameters and real HTTP verbs** are the shipped /manage convention
(boutique/router.py, catalog/router.py, booking/owner_router.py). The
`.claude/rules` RPC / @QueryValue guidance is Kotlin boilerplate for another
codebase; F15's D7 already ruled this.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.auth.dependencies import get_current_staff, require_role
from app.auth.schemas import CreateStaffRequest, StaffMember, UpdateStaffRequest
from app.auth.service import StaffContext
from app.auth.staff import StaffService
from app.models.constants import StaffRole
from app.models.staff_user import StaffUser
from app.schemas import OkResponse
from app.tenancy.middleware import get_current_tenant

NO_STORE = "no-store"


def _no_store(response: Response) -> None:
    response.headers["cache-control"] = NO_STORE


def get_staff_service(request: Request) -> StaffService:
    service: StaffService = request.app.state.staff_service
    return service


router = APIRouter(
    prefix="/manage",
    dependencies=[Depends(_no_store), Depends(require_role(StaffRole.OWNER))],
)

Staff = Annotated[StaffContext, Depends(get_current_staff)]
Service = Annotated[StaffService, Depends(get_staff_service)]


def _member(row: StaffUser) -> StaffMember:
    return StaffMember(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        role=row.role,
        created_at=row.created_at,
    )


@router.get("/staff")
async def list_staff(request: Request, staff: Staff, service: Service) -> list[StaffMember]:
    """A bare array, no envelope and no pagination — the
    GET /manage/appointment-types precedent for a small list (spec D6)."""
    tenant = get_current_tenant(request)
    return [_member(row) for row in await service.list_staff(tenant.id)]


@router.post("/staff")
async def create_staff(
    request: Request, staff: Staff, service: Service, body: CreateStaffRequest
) -> StaffMember:
    tenant = get_current_tenant(request)
    created = await service.create(
        tenant.id,
        email=body.email,
        display_name=body.display_name,
        role=body.role.value,
        password=body.password,
        actor=staff,
    )
    return _member(created)


@router.patch("/staff/{staff_id}")
async def update_staff(
    request: Request,
    staff: Staff,
    service: Service,
    staff_id: UUID,
    body: UpdateStaffRequest,
) -> StaffMember:
    tenant = get_current_tenant(request)
    updated = await service.update(
        tenant.id,
        staff_id,
        display_name=body.display_name,
        role=body.role.value if body.role is not None else None,
        password=body.password,
        current_password=body.current_password,
        actor=staff,
    )
    return _member(updated)


@router.delete("/staff/{staff_id}")
async def deactivate_staff(
    request: Request, staff: Staff, service: Service, staff_id: UUID
) -> OkResponse:
    tenant = get_current_tenant(request)
    await service.deactivate(tenant.id, staff_id, actor=staff)
    return OkResponse()
