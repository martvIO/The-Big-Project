"""The public OTP surface: two anonymous, tenant-scoped POSTs.

**A sibling router on /storefront, not new routes in app/storefront/router.py.**
That router is contractually GET-only (its module docstring, and the HEAD-405
argument) — the OTP mutations live here so the read router's contract stays
mechanically true. Same prefix, registered after it in create_app(); the
cross-router shadowing guard in test_storefront_api.py covers both.

**Not under /manage, and CSRF is structurally N/A.** These endpoints read no
cookie and carry no ambient credential, so there is nothing a cross-site
request could ride: the controls are tenant-from-Host, the per-phone and
per-tenant send budgets, and OTP possession itself. The cookie-blindness test
(a request carrying a valid owner cookie gets a byte-identical response) is
what keeps this claim true forever.

**204 on send, deliberately.** The response confirms only that a well-formed
request was accepted — never whether a code went out, which is observable by
the phone's owner alone. There is nothing here to enumerate: unknown phones
and known phones answer identically.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth.client_ip import client_ip
from app.core.config import get_settings
from app.notifications.schemas import OtpSendRequest, OtpVerifyRequest, OtpVerifyResponse
from app.notifications.service import OtpService
from app.tenancy.middleware import get_current_tenant

NO_STORE = "no-store"


def get_otp_service(request: Request) -> OtpService:
    service: OtpService = request.app.state.otp_service
    return service


def _no_store(response: Response) -> None:
    """Router-level like the storefront reads: the verify response carries a
    bearer verification_token that must never land in a shared cache or bfcache
    entry, and send pays nothing for carrying the same header."""
    response.headers["cache-control"] = NO_STORE


router = APIRouter(prefix="/storefront", dependencies=[Depends(_no_store)])

Otp = Annotated[OtpService, Depends(get_otp_service)]


@router.post("/otp/send", status_code=204)
async def send_otp(request: Request, service: Otp, body: OtpSendRequest) -> None:
    """⚠ `ip` IS `None` ON EVERY DEPLOYMENT WE CURRENTLY HAVE. `client_ip` returns
    `None` unless `trust_forwarded_for`, which ships `False` (`config.py:37`), so
    the per-IP send budget below is code-complete and INERT — row R16 is amber
    for that reason, and arming it (`TRUST_FORWARDED_FOR=true`, correct only
    behind exactly one trusted proxy that appends XFF) is `F62`'s."""
    tenant = get_current_tenant(request)
    ip = client_ip(request, get_settings().trust_forwarded_for)
    await service.send(tenant.id, body.phone, ip=ip)


@router.post("/otp/verify")
async def verify_otp(request: Request, service: Otp, body: OtpVerifyRequest) -> OtpVerifyResponse:
    tenant = get_current_tenant(request)
    result = await service.verify(tenant.id, body.phone, body.code)
    return OtpVerifyResponse(
        verification_token=result.verification_token,
        expires_at=result.expires_at,
    )
