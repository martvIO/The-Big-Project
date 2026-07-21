from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth.cookies import clear_session_cookie, set_session_cookie
from app.auth.dependencies import get_auth_service, get_current_staff
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.schemas import LoginRequest, StaffResponse
from app.auth.service import AuthService, InvalidCredentialsError, StaffContext
from app.core.config import get_settings
from app.tenancy.middleware import get_current_tenant

router = APIRouter(prefix="/manage/auth")


class RateLimitedError(Exception):
    pass


def _staff_response(staff: StaffContext) -> StaffResponse:
    return StaffResponse(
        id=str(staff.id),
        email=staff.email,
        display_name=staff.display_name,
        role=staff.role,
    )


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> StaffResponse:
    settings = get_settings()
    tenant = get_current_tenant(request)
    limiter: FixedWindowRateLimiter = request.app.state.login_rate_limiter
    email = body.email.lower()
    client_ip = request.client.host if request.client else "unknown"
    # Both keys must have headroom — an attacker can't exhaust one victim's budget
    # from many IPs, nor spray many accounts from one IP.
    for key in (f"t:{tenant.id}:e:{email}", f"ip:{client_ip}"):
        if not limiter.check_and_increment(key):
            raise RateLimitedError

    try:
        staff, token = await service.login(tenant.id, email, body.password)
    except InvalidCredentialsError:
        raise
    limiter.reset(f"t:{tenant.id}:e:{email}")
    set_session_cookie(
        response, token, secure=settings.secure_cookies, max_age=settings.session_ttl_seconds
    )
    return _staff_response(staff)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, bool]:
    tenant = get_current_tenant(request)
    token = request.cookies.get("boutique_session")
    if token:
        await service.logout(tenant.id, token)
    clear_session_cookie(response, secure=get_settings().secure_cookies)
    return {"ok": True}


@router.get("/me")
async def me(staff: Annotated[StaffContext, Depends(get_current_staff)]) -> StaffResponse:
    return _staff_response(staff)
