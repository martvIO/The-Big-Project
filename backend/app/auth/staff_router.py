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

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.auth.cookies import SESSION_COOKIE
from app.auth.dependencies import get_current_staff, require_role
from app.auth.photo import sign_staff_photo
from app.auth.schemas import (
    CreateStaffRequest,
    StaffMember,
    StaffPhotoPresignRequest,
    StaffPhotoPresignResponse,
    UpdateStaffRequest,
)
from app.auth.service import StaffContext
from app.auth.staff import StaffService
from app.auth.tokens import hash_token
from app.models.constants import StaffRole
from app.models.staff_user import StaffUser
from app.schemas import OkResponse
from app.storage.base import MediaStorage
from app.tenancy.middleware import get_current_tenant

NO_STORE = "no-store"


def _no_store(response: Response) -> None:
    response.headers["cache-control"] = NO_STORE


def get_staff_service(request: Request) -> StaffService:
    service: StaffService = request.app.state.staff_service
    return service


def get_media_storage(request: Request) -> MediaStorage:
    """The same `app.state.media_storage` the catalog signs through — one bucket,
    one port, one place it is built. Read off app.state rather than injected into
    StaffService because signing is a READ concern of this router and the board's
    schema module; the WRITE side (presign/confirm/delete) is where the service
    needs it."""
    storage: MediaStorage = request.app.state.media_storage
    return storage


router = APIRouter(
    prefix="/manage",
    dependencies=[Depends(_no_store), Depends(require_role(StaffRole.OWNER))],
)

Staff = Annotated[StaffContext, Depends(get_current_staff)]
Service = Annotated[StaffService, Depends(get_staff_service)]
Storage = Annotated[MediaStorage, Depends(get_media_storage)]


def _member(row: StaffUser, storage: MediaStorage) -> StaffMember:
    """The ONE wire builder for this router, and it stays the one: a second
    builder is how `photo_url` would end up signed on the list and null on the
    PATCH response for a week before anybody noticed.

    `sign_staff_photo` is a plain call, not an await — signing is local HMAC with
    zero I/O — and it degrades to None rather than raising, so a rotated bucket
    credential answers a 200 with `photo_url: null` instead of 503-ing a read
    that has nothing to do with storage."""
    return StaffMember(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        role=row.role,
        created_at=row.created_at,
        phone=row.phone,
        start_date=row.start_date,
        last_day=row.last_day,
        shift_manager_eligible=row.shift_manager_eligible,
        photo_url=sign_staff_photo(storage, row),
        photo_confirmed_at=row.photo_confirmed_at,
    )


@router.get("/staff")
async def list_staff(
    request: Request, staff: Staff, service: Service, storage: Storage
) -> list[StaffMember]:
    """A bare array, no envelope and no pagination — the
    GET /manage/appointment-types precedent for a small list (spec D6)."""
    tenant = get_current_tenant(request)
    return [_member(row, storage) for row in await service.list_staff(tenant.id)]


@router.post("/staff")
async def create_staff(
    request: Request, staff: Staff, service: Service, storage: Storage, body: CreateStaffRequest
) -> StaffMember:
    tenant = get_current_tenant(request)
    created = await service.create(
        tenant.id,
        email=body.email,
        display_name=body.display_name,
        role=body.role.value,
        password=body.password,
        phone=body.phone,
        start_date=body.start_date,
        shift_manager_eligible=body.shift_manager_eligible,
        actor=staff,
    )
    return _member(created, storage)


@router.patch("/staff/{staff_id}")
async def update_staff(
    request: Request,
    staff: Staff,
    service: Service,
    storage: Storage,
    staff_id: UUID,
    body: UpdateStaffRequest,
) -> StaffMember:
    tenant = get_current_tenant(request)
    # A password write revokes the target's other sessions; this is the one
    # cookie that must survive it, so the acting token's hash goes down with the
    # call. `staff` above already proved the cookie is present and valid.
    token = request.cookies.get(SESSION_COOKIE)
    updated = await service.update(
        tenant.id,
        staff_id,
        display_name=body.display_name,
        role=body.role.value if body.role is not None else None,
        password=body.password,
        current_password=body.current_password,
        phone=body.phone,
        start_date=body.start_date,
        shift_manager_eligible=body.shift_manager_eligible,
        acting_token_hash=hash_token(token) if token else None,
        actor=staff,
    )
    return _member(updated, storage)


@router.delete("/staff/{staff_id}")
async def deactivate_staff(
    request: Request,
    staff: Staff,
    service: Service,
    staff_id: UUID,
    last_day: date | None = None,
) -> OkResponse:
    """Offboarding — F51's endpoint, extended rather than replaced.

    `last_day` is an OPTIONAL query parameter and its absence means "today in
    Jerusalem", resolved in the service. It is deliberately not a body: DELETE
    with a body is unevenly supported by clients and proxies, and this is one
    scalar. A `date` annotation means `?last_day=not-a-date` is a house 400 at
    the boundary and never reaches the column.
    """
    tenant = get_current_tenant(request)
    await service.deactivate(tenant.id, staff_id, last_day=last_day, actor=staff)
    return OkResponse()


# --- F38: the profile photo, three routes on the SAME owner-only router ------
#
# No per-route decorator, deliberately: the gate is mounted on the router, so a
# route added here cannot forget it. The three (method, path) templates still
# have to be named in test_staff_role_gating's OWNER_ONLY set, in
# test_cross_tenant_walker's walk and in test_audit_coverage's mutating-route
# assertion — those three tables are what turn "cannot forget" into a test.


@router.post("/staff/{staff_id}/photo/presign")
async def presign_staff_photo(
    request: Request,
    staff: Staff,
    service: Service,
    staff_id: UUID,
    body: StaffPhotoPresignRequest,
) -> StaffPhotoPresignResponse:
    """Answers the POST policy the browser uploads with. It carries no photo id:
    the confirm route reads the pending triple off the row, so the client never
    holds an identifier it could substitute for another staffer's."""
    tenant = get_current_tenant(request)
    presign = await service.presign_photo(
        tenant.id,
        staff_id,
        content_type=body.content_type,
        byte_size=body.byte_size,
        actor_id=staff.id,
    )
    return StaffPhotoPresignResponse(
        url=presign.url,
        fields=presign.fields,
        expires_in=presign.expires_in,
        max_bytes=presign.max_bytes,
    )


@router.post("/staff/{staff_id}/photo/confirm")
async def confirm_staff_photo(
    request: Request, staff: Staff, service: Service, storage: Storage, staff_id: UUID
) -> StaffMember:
    """No body: everything this needs is already on the row. Answers the updated
    member so the console re-renders from the server's own view rather than
    guessing what the promote did."""
    tenant = get_current_tenant(request)
    confirmed = await service.confirm_photo(tenant.id, staff_id, actor_id=staff.id)
    return _member(confirmed, storage)


@router.delete("/staff/{staff_id}/photo")
async def delete_staff_photo(
    request: Request, staff: Staff, service: Service, storage: Storage, staff_id: UUID
) -> StaffMember:
    tenant = get_current_tenant(request)
    cleared = await service.delete_photo(tenant.id, staff_id, actor_id=staff.id)
    return _member(cleared, storage)
