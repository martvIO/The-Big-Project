"""F26 D6 — the two ANONYMOUS routes, in their own module.

⚠ THE SEPARATE FILE IS THE DESIGN, not tidiness. `app/platform/router.py`
declares `Depends(get_current_operator)` on its routers; if these two lived
there, one edit to a shared dependency list would either open the console or
close signup, and neither would look like a change to the other. Two routers
under one prefix means a route cannot acquire or lose an operator context by
accident, and `test_staff_role_gating` names both of these in an allowlist with
a written justification so a THIRD anonymous /platform route is a deliberate act.

Reachable ONLY on the console host: the tenancy middleware fences `/platform*`
to `admin.{base_domain}` in both directions. ⚠ NEVER add `/platform/join` to
`EXEMPT_PATHS` — exemption skips tenant resolution on EVERY host and would open
the join route on every boutique's subdomain. The fence is the label branch, not
an exemption.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.auth.client_ip import client_ip
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.router import RateLimitedError
from app.auth.tokens import hash_token
from app.core.config import get_settings
from app.platform.router import ConsoleCommandRefused, get_provisioning_service
from app.platform.schemas import (
    MAX_INVITE_CODE_LENGTH,
    InvitePreviewResponse,
    RedeemInviteRequest,
    RedeemInviteResponse,
)
from app.platform.service import ProvisioningService

router = APIRouter(prefix="/platform/join")

# One bucket for the whole surface. Not a code, not an address — the point is
# that nothing about it is caller-controlled (`platform_auth_router`'s
# `_GLOBAL_KEY`, same argument).
_GLOBAL_KEY = "invite-redeem"

ServiceDep = Annotated[ProvisioningService, Depends(get_provisioning_service)]


def _spend(request: Request, code: str) -> None:
    """Check both arms BEFORE doing any work, and raise 429 if either is spent.

    ⚠ WHAT THIS PROTECTS IS NOT A PASSWORD. Every refusal on these two routes
    writes an `INVITE_REDEEM_FAILED` row into `platform_audit_log`, which 0004
    makes INSERT-only and which no retention policy prunes — so an unmetered
    anonymous route here lets a caller permanently fill a table the app can
    neither read back nor delete from. Q10 removed the abuse programme; it did
    not remove that.

    ⚠ ITS OWN INSTANCES, never keys on `platform_login_rate_limiter`.
    `max_attempts` lives on the LIMITER, so sharing would give signup the console
    login's ceiling and let a flood of bad codes close the platform's front door
    (`.memory/limiter-max-is-per-instance`, the rule main.py states seven times).
    """
    limiter: FixedWindowRateLimiter = request.app.state.invite_redeem_rate_limiter
    global_limiter: FixedWindowRateLimiter = request.app.state.invite_redeem_global_rate_limiter
    if global_limiter.is_blocked(_GLOBAL_KEY) or any(
        limiter.is_blocked(key) for key in _keys(request, code)
    ):
        raise RateLimitedError


def _keys(request: Request, code: str) -> list[str]:
    """Keyed on the code's HASH, never the code. The limiter holds its keys in
    memory for the window's duration, and a raw invite code sitting in a
    process-wide dict is a live boutique-creation credential in a place nobody
    would think to look for one.

    The per-IP arm is inert while `trust_forwarded_for` is False (which is every
    deployment we have) and inherits R16's CGNAT caveat unchanged."""
    keys = [f"code:{hash_token(code)}"]
    ip = client_ip(request, get_settings().trust_forwarded_for)
    if ip is not None:
        keys.append(f"ip:{ip}")
    return keys


def _record_failure(request: Request, code: str) -> None:
    """FAILURES ONLY. An owner redeeming her own invite — preview then submit —
    never throttles herself, and a spent budget on the one link that creates her
    boutique is a denial of service rather than a control."""
    limiter: FixedWindowRateLimiter = request.app.state.invite_redeem_rate_limiter
    global_limiter: FixedWindowRateLimiter = request.app.state.invite_redeem_global_rate_limiter
    for key in _keys(request, code):
        limiter.record_failure(key)
    global_limiter.record_failure(_GLOBAL_KEY)


@router.get("/invite")
async def preview_invite(
    request: Request,
    service: ServiceDep,
    code: Annotated[str, Query(min_length=1, max_length=MAX_INVITE_CODE_LENGTH)],
) -> InvitePreviewResponse:
    """A read that discloses a boutique name to an unauthenticated caller holding
    a 256-bit secret, and that is the whole point: the owner sees which boutique
    and which address she is claiming BEFORE she spends the invite, so a mistyped
    one is caught while revoke-and-reissue still fixes it (D2).

    Writes NO audit row. A read of one's own invite is not a platform event, and
    `TENANTS_LISTED`'s cross-tenant-enumeration argument does not reach a caller
    who already holds the secret for this single row. Registered in
    `test_audit_coverage.py`'s read exemptions with that reason.

    Unknown, expired, redeemed and revoked all answer the same 404
    `invalid_invite` — a distinct "already redeemed" would confirm to an
    anonymous caller that a code was real (D5).
    """
    _spend(request, code)
    found = await service.preview_invite(code=code)
    if found is None:
        _record_failure(request, code)
        raise ConsoleCommandRefused("invalid_invite")
    return InvitePreviewResponse(slug=found.slug, name=found.name, owner_email=found.owner_email)


@router.post("/redeem")
async def redeem_invite(
    request: Request, body: RedeemInviteRequest, service: ServiceDep
) -> RedeemInviteResponse:
    """The tenant, its owner and the invite's consumption commit together or not
    at all — the service owns that transaction (D4), and this router does what
    every other console route does: parse, delegate, translate a returned
    refusal.

    NO SESSION IS ISSUED. The owner lands on a success screen and signs in on her
    own boutique's host, where the staff cookie belongs. Minting one here would
    mean a platform-host cookie for a tenant identity, which is precisely the
    lookup-path sharing spec D3 forbids.
    """
    _spend(request, body.code)
    result = await service.redeem_invite(code=body.code, owner_password=body.owner_password)
    if not result.ok or result.slug is None:
        _record_failure(request, body.code)
        raise ConsoleCommandRefused(result.message)
    settings = get_settings()
    return RedeemInviteResponse(
        slug=result.slug,
        # Always https and the configured base domain, `manage_link`'s rule. F17
        # already ships the gateway surface behind this door; F26 links to it and
        # adds no payment code (D7).
        manage_url=f"https://{result.slug}.{settings.base_domain}/manage",
    )
