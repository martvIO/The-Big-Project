from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_staff, require_role
from app.auth.service import StaffContext
from app.models.constants import StaffRole
from app.payments.schemas import GatewayStatusResponse, SetGatewayCredentialsRequest
from app.payments.service import GatewayCredentialService
from app.tenancy.middleware import get_current_tenant

# The first router in the repo that is OWNER-ONLY IN FULL (D13). A shift manager
# has no relationship to the boutique's merchant account, and the read itself
# discloses whether the business can take money — the same reading that makes
# F51's staff router owner-only. OWNER_ONLY in test_staff_role_gating.py gains
# these four rows in the same commit, which is what makes narrowing the shift
# manager's surface a deliberate, reviewed act rather than a silent one.
#
# PUT/DELETE rather than POST sub-paths, matching app/boutique/router.py's
# existing PUT /manage/settings and DELETE /manage/appointment-types/{id}.
#
# CSRF is covered, not argued away: CsrfOriginMiddleware.PROTECTED_PREFIX is
# /manage and these are cookie-authenticated state-changing routes.
#
# No Cache-Control: no-store (D17). The OTP router carries it because its verify
# response holds a bearer token; nothing here carries bearer material or a
# secret, and adding the header to one of six /manage routers is drift.
router = APIRouter(
    prefix="/manage",
    dependencies=[Depends(require_role(StaffRole.OWNER))],
)

Staff = Annotated[StaffContext, Depends(get_current_staff)]


def get_gateway_service(request: Request) -> GatewayCredentialService:
    service: GatewayCredentialService = request.app.state.gateway_credential_service
    return service


Service = Annotated[GatewayCredentialService, Depends(get_gateway_service)]


@router.get("/gateway")
async def get_gateway(request: Request, staff: Staff, service: Service) -> GatewayStatusResponse:
    """200 in EVERY state, never 503 — including with no adapter at all. A
    console that cannot read its own status cannot explain to the owner why
    deposits are unavailable. `status()` also never decrypts."""
    tenant = get_current_tenant(request)
    return GatewayStatusResponse.from_status(await service.status(tenant.id))


@router.put("/gateway/credentials")
async def set_gateway_credentials(
    request: Request, staff: Staff, service: Service, body: SetGatewayCredentialsRequest
) -> GatewayStatusResponse:
    tenant = get_current_tenant(request)
    status = await service.connect(tenant.id, fields=body.fields, actor_id=staff.id)
    return GatewayStatusResponse.from_status(status)


@router.post("/gateway/validate")
async def validate_gateway(
    request: Request, staff: Staff, service: Service
) -> GatewayStatusResponse:
    """No body — it re-pings what is already stored."""
    tenant = get_current_tenant(request)
    return GatewayStatusResponse.from_status(await service.revalidate(tenant.id, actor_id=staff.id))


@router.delete("/gateway/credentials")
async def disconnect_gateway(
    request: Request, staff: Staff, service: Service
) -> GatewayStatusResponse:
    """No precondition on in-flight payments (D20): a disconnect is precisely
    what an owner does when a key leaks, and refusing it while a payment is
    pending would make the safe action unavailable exactly when it is needed.
    The superseded row keeps its ciphertext so those charges can still settle."""
    tenant = get_current_tenant(request)
    return GatewayStatusResponse.from_status(await service.disconnect(tenant.id, actor_id=staff.id))
