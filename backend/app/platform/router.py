"""F25 D5 — the console's four endpoints, in front of an UNCHANGED service.

Pre-decided #20 said the CLI's audited command layer becomes the console's
service layer, and that turned out to be almost no work: `ProvisioningService`
already takes a session factory, already returns result dataclasses, and already
owns its own failure audits. So this file is a router and nothing else — it
parses, delegates with the authenticated operator's email, and translates a
returned refusal into the house error body.

⚠ THE SERVICE OWNS THE AUDIT ROWS, INCLUDING THE FAILURE ONES, and that is why
this router raises AFTER the call rather than refusing before it. Moving a
validation forward — checking the slug here, say — would skip the
`TENANT_PROVISION_FAILED` row the CLI writes for the same refusal, and the
console would silently keep a thinner book than the shell it replaced.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.platform.auth import OperatorContext, get_current_operator
from app.platform.schemas import (
    CreateInviteRequest,
    InviteCreatedResponse,
    InviteListResponse,
    InviteRow,
    ProvisionRequest,
    ResetOwnerPasswordRequest,
    RevokeInviteRequest,
    SuspendRequest,
    TenantListResponse,
    TenantRow,
)
from app.platform.service import CommandResult, InviteSummary, ProvisioningService
from app.schemas import OkResponse

# Reachable ONLY on the console host and ONLY with a live operator session: the
# tenancy middleware fences the prefix both ways, csrf.py protects it, and every
# route below carries `Depends(get_current_operator)`.
router = APIRouter(prefix="/platform/tenants", dependencies=[Depends(get_current_operator)])


# The service's refusal messages, mapped to the status each one deserves. The
# CODE IS THE MESSAGE STRING VERBATIM — the console keys its Hebrew sentences on
# it (design deck §6) and falls through to a generic sentence for anything
# unlisted, so a rename here silently downgrades a precise sentence to "something
# went wrong" and this table is where that decision has to be made on purpose.
#
# `slug_taken` is 409 and not 400: the request is well-formed, and what refuses
# it is another boutique — possibly a SUSPENDED one, which still holds its slug
# and which the operator cannot see in the list.
_REFUSAL_STATUS = {
    "invalid_or_reserved_slug": 400,
    "empty_password": 400,
    "password_too_short": 400,
    "slug_taken": 409,
    "tenant_not_found": 404,
    "owner_not_found": 404,
    # F26. `invalid_invite` is ONE code for four states — unknown, expired,
    # already redeemed, revoked — at 404. A distinct "already redeemed" would
    # tell an unauthenticated caller that a code was real, which is exactly the
    # anti-enumeration reading `TENANT_NOT_FOUND` already carries (spec D5).
    "invalid_invite": 404,
    # The operator-side twin, and deliberately NOT the same code: the console is
    # authenticated and revoking an id that is already gone is a stale screen,
    # not an enumeration attempt.
    "invite_not_found": 404,
}


class ConsoleCommandRefused(Exception):
    """A business refusal the service RETURNED. create_app maps it to the house
    error body with the service's own message as the code.

    One class for all five rather than five exception types: the console branches
    on the code string, not on a Python class, and five handlers in main.py would
    be five places to forget the next one. An unmapped message still arrives as
    itself at 400 — degraded to the console's generic sentence, never mistaken
    for somebody else's refusal and never a 500.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
        self.status = _REFUSAL_STATUS.get(code, 400)


def get_provisioning_service(request: Request) -> ProvisioningService:
    service: ProvisioningService = request.app.state.provisioning_service
    return service


def _ok(result: CommandResult) -> OkResponse:
    if not result.ok:
        raise ConsoleCommandRefused(result.message)
    return OkResponse()


ServiceDep = Annotated[ProvisioningService, Depends(get_provisioning_service)]
OperatorDep = Annotated[OperatorContext, Depends(get_current_operator)]


@router.post("/provision")
async def provision(
    body: ProvisionRequest, service: ServiceDep, operator: OperatorDep
) -> OkResponse:
    # Nothing of the new tenant is echoed back. The console appends the row from
    # the values the operator just typed (design §data discipline) — and the
    # initial owner password, the one secret in this request, leaves the server's
    # hands the moment argon2 has it.
    return _ok(
        await service.provision(
            slug=body.slug,
            name=body.name,
            owner_email=body.owner_email,
            owner_password=body.owner_password,
            operator=operator.email,
        )
    )


@router.post("/suspend")
async def suspend(body: SuspendRequest, service: ServiceDep, operator: OperatorDep) -> OkResponse:
    return _ok(await service.suspend(slug=body.slug, operator=operator.email))


@router.post("/reset-owner-password")
async def reset_owner_password(
    body: ResetOwnerPasswordRequest, service: ServiceDep, operator: OperatorDep
) -> OkResponse:
    return _ok(
        await service.reset_owner_password(
            slug=body.slug,
            owner_email=body.owner_email,
            new_password=body.new_password,
            operator=operator.email,
        )
    )


@router.get("")
async def list_tenants(service: ServiceDep, operator: OperatorDep) -> TenantListResponse:
    """⚠ A GET THAT WRITES A ROW, and it is the one exception in this product.

    F21's D6 made `list_tenants` the single audited read: it is a full
    cross-tenant enumeration — every boutique's slug, trading name and status in
    one answer. The standing rule that no GET handler writes (dashboard/service.py
    :373) governs a tenant's staff reading their OWN boutique; this is a platform
    operator reading across all of them, and the row R12 demanded travels from the
    shell to HTTP unchanged rather than being dropped on the way.

    Which is also why the console fetches this ONCE per mount and filters
    client-side — a refetch loop would spam the platform's own book.
    """
    rows = await service.list_tenants(operator=operator.email)
    return TenantListResponse(
        tenants=[
            TenantRow(slug=row.slug, name=row.name, status=row.status, created_at=row.created_at)
            for row in rows
        ]
    )


# --- F26 invites -------------------------------------------------------------
#
# A SECOND router rather than more paths on the one above, for one reason: the
# prefix differs (`/platform/invites` vs `/platform/tenants`). The dependency is
# the same and is declared the same way — on the router, so a route added here
# later cannot be born ungated. The anonymous join pair lives in its OWN module
# (`join_router.py`, spec D6) precisely so that no route can acquire or lose an
# operator context by somebody editing a shared dependency list.
invites_router = APIRouter(prefix="/platform/invites", dependencies=[Depends(get_current_operator)])


def _invite_row(summary: InviteSummary) -> InviteRow:
    return InviteRow(
        id=summary.id,
        slug=summary.slug,
        name=summary.name,
        owner_email=summary.owner_email,
        created_by=summary.created_by,
        expires_at=summary.expires_at,
        redeemed_at=summary.redeemed_at,
        created_at=summary.created_at,
    )


@invites_router.post("")
async def create_invite(
    body: CreateInviteRequest, service: ServiceDep, operator: OperatorDep
) -> InviteCreatedResponse:
    """⚠ THE ONE RESPONSE IN THIS PRODUCT THAT CARRIES A LIVE INVITE CODE.

    It is built here from the service's return value and never touched again:
    no logger, no audit `details`, no error message, no second read (spec R-C).
    The console shows it once in a panel with no dismissal vector, and after
    that nothing anywhere can produce it.
    """
    result = await service.create_invite(
        slug=body.slug,
        name=body.name,
        owner_email=body.owner_email,
        operator=operator.email,
    )
    if not result.ok or result.code is None or result.invite is None:
        raise ConsoleCommandRefused(result.message)
    settings = get_settings()
    return InviteCreatedResponse(
        code=result.code,
        # Always https and the configured base domain, `manage_link`'s rule: the
        # operator copies this and hands it over, so it has to be the address the
        # owner will actually open rather than whatever host the console is being
        # driven from.
        join_url=(
            f"https://{settings.platform_host_label}.{settings.base_domain}"
            f"/platform/join?code={result.code}"
        ),
        invite=_invite_row(result.invite),
    )


@invites_router.get("")
async def list_invites(service: ServiceDep, operator: OperatorDep) -> InviteListResponse:
    """A GET that writes NO row, unlike `GET /platform/tenants` one file above.

    The asymmetry is the point and it is argued in the service: that one is a
    full cross-tenant enumeration of every boutique trading on the platform
    (F21 D6); this lists authorisations the operator population issued itself and
    names no boutique that exists. Registered in `test_audit_coverage.py` so the
    difference is reviewable rather than silent.
    """
    return InviteListResponse(invites=[_invite_row(row) for row in await service.list_invites()])


@invites_router.post("/revoke")
async def revoke_invite(
    body: RevokeInviteRequest, service: ServiceDep, operator: OperatorDep
) -> OkResponse:
    return _ok(await service.revoke_invite(invite_id=body.id, operator=operator.email))
