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


def _client_ip(request: Request, trust_forwarded_for: bool) -> str | None:
    # Per-IP limiting is only meaningful with the REAL client IP. Without a trusted
    # proxy that appends XFF, request.client.host is the proxy → a global bucket, so
    # we skip the per-IP key entirely (None). With one trusted proxy hop, the last
    # XFF entry is the client the proxy saw.
    if not trust_forwarded_for:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else None


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

    # Per-(tenant,email) is the always-on brute-force control; the per-IP key is
    # extra and only present when we can trust a real client IP.
    keys = [f"t:{tenant.id}:e:{email}"]
    ip = _client_ip(request, settings.trust_forwarded_for)
    if ip is not None:
        keys.append(f"ip:{ip}")

    if any(limiter.is_blocked(key) for key in keys):
        raise RateLimitedError

    try:
        staff, token = await service.login(tenant.id, email, body.password)
    except InvalidCredentialsError:
        # Only failures count toward the limit — successes never throttle anyone.
        for key in keys:
            limiter.record_failure(key)
        raise

    limiter.reset(keys[0])
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
