from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth.client_ip import client_ip
from app.auth.cookies import (
    clear_platform_session_cookie,
    platform_session_cookie_name,
    set_platform_session_cookie,
)
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.router import RateLimitedError
from app.auth.schemas import LoginRequest
from app.auth.service import InvalidCredentialsError
from app.core.config import get_settings
from app.platform.auth import (
    OperatorAuthService,
    OperatorContext,
    get_current_operator,
    get_operator_auth_service,
)
from app.platform.schemas import OperatorResponse

# Reachable ONLY on the console host: the tenancy middleware 404s /platform* on
# every tenant host and everything-but-/platform* on the console host. The prefix
# is also in csrf.py's PROTECTED_PREFIXES tuple, so the two mutating routes below
# carry the Origin-vs-Host check.
router = APIRouter(prefix="/platform/auth")

# One bucket for the whole route. Not an email, not an address — the point is
# that nothing about it is caller-controlled.
_GLOBAL_KEY = "platform-login"


def _response(operator: OperatorContext) -> OperatorResponse:
    return OperatorResponse(
        email=operator.email,
        display_name=operator.display_name,
        base_domain=get_settings().base_domain,
    )


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    service: Annotated[OperatorAuthService, Depends(get_operator_auth_service)],
) -> OperatorResponse:
    settings = get_settings()
    # ⚠ ITS OWN LIMITER INSTANCE, never a key on the staff budget.
    # `max_attempts` lives on the LIMITER, so sharing would give the console the
    # staff ceiling and let one tenant's brute-force close the platform's front
    # door — or the reverse (`.memory/limiter-max-is-per-instance`, and the rule
    # main.py states five times).
    limiter: FixedWindowRateLimiter = request.app.state.platform_login_rate_limiter
    email = body.email.lower()

    # Per-email is the always-on control; the per-IP arm is inert until
    # `trust_forwarded_for` flips (F62's), and inherits R16's CGNAT caveat
    # unchanged.
    keys = [f"e:{email}"]
    ip = client_ip(request, settings.trust_forwarded_for)
    if ip is not None:
        keys.append(f"ip:{ip}")

    # ⚠ AND ONE ARM THE CALLER CANNOT ROTATE OUT OF. Both keys above are chosen
    # by whoever is calling — a script sending a fresh address each time never
    # trips the per-email budget, and with `trust_forwarded_for` False there is
    # no second arm at all. Unmetered, each such attempt buys a full argon2id
    # verify (64 MiB, m=64MiB/t=3/p=4, `verify_password_dummy` on the
    # unknown-address path) and one permanent `platform_audit_log` row that 0004
    # makes INSERT-only and no RetentionPolicy prunes. On the single-instance
    # pilot that is host memory and the platform's sole access-evidence book,
    # both spent by an anonymous caller.
    #
    # Its own instance because `max_attempts` lives on the LIMITER
    # (`.memory/limiter-max-is-per-instance`, the rule main.py states six times).
    #
    # ponytail: a spent global budget refuses the console login for the rest of
    # the window, including the real operator's — a real cost, and strictly the
    # smaller one: without it the host serving every boutique OOMs instead. The
    # upgrade that removes the trade is the distributed limiter plus a real
    # per-IP arm, both parked in F62.
    global_limiter: FixedWindowRateLimiter = request.app.state.platform_login_global_rate_limiter

    if global_limiter.is_blocked(_GLOBAL_KEY) or any(limiter.is_blocked(key) for key in keys):
        raise RateLimitedError

    try:
        operator, token = await service.login(email, body.password)
    except InvalidCredentialsError:
        # Only FAILURES count — a busy operator signing in normally never
        # throttles herself, and a spent budget on the one account that can fix
        # anything is a denial of service rather than a control.
        for key in keys:
            limiter.record_failure(key)
        global_limiter.record_failure(_GLOBAL_KEY)
        raise

    limiter.reset(keys[0])
    set_platform_session_cookie(
        response,
        token,
        secure=settings.secure_cookies,
        # 4h and not the staff 12h (spec D3): highest privilege, lowest login
        # frequency, and re-login costs one password entry. Fixed expiry — nothing
        # slides it.
        max_age=settings.platform_session_ttl_seconds,
    )
    return _response(operator)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    service: Annotated[OperatorAuthService, Depends(get_operator_auth_service)],
) -> dict[str, bool]:
    # No `get_current_operator` dependency and no 401 without a cookie: signing
    # out of a session you do not hold is not an error, and answering one would
    # make logout an oracle for "was that token live".
    #
    # AND NO AUDIT ROW, deliberately — the one console mutation without one. Spec
    # D4 enumerates the platform book's new actions as OPERATOR_LOGIN and
    # OPERATOR_LOGIN_FAILED only. That book answers "who touched the platform,
    # and when did somebody try"; a session ending is neither, and the login row
    # already bounds the window this closes. The staff twin DOES write LOGOUT,
    # into its own tenant's audit_log, which is a different book answering a
    # different question. Recorded in test_audit_coverage.py's exemption list so
    # the decision is reviewable rather than silent.
    secure = get_settings().secure_cookies
    token = request.cookies.get(platform_session_cookie_name(secure))
    if token:
        await service.logout(token)
    clear_platform_session_cookie(response, secure=secure)
    return {"ok": True}


@router.get("/me")
async def me(
    operator: Annotated[OperatorContext, Depends(get_current_operator)],
) -> OperatorResponse:
    return _response(operator)
