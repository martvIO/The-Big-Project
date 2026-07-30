from typing import Annotated

from fastapi import Depends, Request

from app.auth.cookies import SESSION_COOKIE
from app.auth.service import AuthService, StaffContext
from app.models.constants import StaffRole
from app.tenancy.middleware import get_current_tenant


class NotAuthenticatedError(Exception):
    """No valid session for this request. create_app maps it to a generic 401 —
    the same body whether the cookie is missing, expired, revoked, or belongs to
    another tenant (RLS makes cross-tenant sessions invisible)."""


class NotAuthorizedError(Exception):
    """A live staff session whose role is not admitted for this route. create_app
    maps it to a generic 403 — one body for every unadmitted role, so a probe
    cannot learn which roles exist. Lives here (not in a domain module) because
    every /manage router raises it."""


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


class RoleGate:
    """Dependency admitting only the given staff roles; anything else — including
    a role string the enum does not know — fails closed with NotAuthorizedError.

    Applied router-level as the default posture and per-route to tighten (both
    gates run; FastAPI's per-request dependency cache resolves the session once).
    Role changes and deactivations bite on the very next request because
    resolve_session re-reads staff_users — there is no session state to sweep.

    `allowed_roles` is introspected by test_staff_role_gating's default-deny
    walker: every /manage route must carry a RoleGate, so a future router
    mounted under /manage without one is a red build, not a convention.
    """

    def __init__(self, *allowed: StaffRole) -> None:
        self.allowed_roles: frozenset[str] = frozenset(role.value for role in allowed)

    async def __call__(
        self, staff: Annotated[StaffContext, Depends(get_current_staff)]
    ) -> StaffContext:
        if staff.role not in self.allowed_roles:
            raise NotAuthorizedError
        return staff


def require_role(*allowed: StaffRole) -> RoleGate:
    return RoleGate(*allowed)
