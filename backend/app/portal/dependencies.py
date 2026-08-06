from fastapi import Request

from app.auth.cookies import CUSTOMER_SESSION_COOKIE
from app.auth.dependencies import NotAuthenticatedError
from app.portal.service import CustomerContext, PortalService
from app.tenancy.middleware import get_current_tenant


def get_portal_service(request: Request) -> PortalService:
    service: PortalService = request.app.state.portal_service
    return service


async def get_current_customer(request: Request) -> CustomerContext:
    """`get_current_staff` mirrored for the customer side, and it reads a
    DIFFERENT cookie name on purpose (spec D2): both cookies ride every request
    to a tenant host, so one shared name would let either principal resolve the
    other's session.

    It reuses `NotAuthenticatedError` — one 401 body whether the cookie is
    missing, expired, revoked, erased or another tenant's, exactly as the staff
    dependency does. RLS makes the cross-tenant case invisible rather than
    distinguishable.
    """
    tenant = get_current_tenant(request)
    token = request.cookies.get(CUSTOMER_SESSION_COOKIE)
    if not token:
        raise NotAuthenticatedError
    customer = await get_portal_service(request).resolve_session(tenant.id, token)
    if customer is None:
        raise NotAuthenticatedError
    return customer
