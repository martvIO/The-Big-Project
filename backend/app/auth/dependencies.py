from fastapi import Request

from app.auth.cookies import SESSION_COOKIE
from app.auth.service import AuthService, StaffContext
from app.tenancy.middleware import get_current_tenant


class NotAuthenticatedError(Exception):
    """No valid session for this request. create_app maps it to a generic 401 —
    the same body whether the cookie is missing, expired, revoked, or belongs to
    another tenant (RLS makes cross-tenant sessions invisible)."""


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


async def get_current_staff(request: Request) -> StaffContext:
    tenant = get_current_tenant(request)
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise NotAuthenticatedError
    service = get_auth_service(request)
    staff = await service.resolve_session(tenant.id, token)
    if staff is None:
        raise NotAuthenticatedError
    return staff
