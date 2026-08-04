"""The privacy surface: five routes on /manage.

**A SIBLING /manage router, not four more routes on the boutique one.** Five
routes plus a service plus a schema module is more than `boutique/router.py`
should absorb, and F17, F51 and F53 all set the precedent of a `/manage` router
in its own package. The role-gating walker reads the router-level gate
identically either way, so the choice is about where the owner-only tightenings
are legible, and they are legible when they are the only three `dependencies=`
in one short file.

**Same shadowing warning every other /manage router carries.** A duplicated
(method, path) would silently win or lose on include order with nothing going
red; `PRIVACY_ROUTES` in test_privacy_api.py is what keeps that honest, and the
include comment in main.py is where the count lives.

⚠ **`POST /manage/privacy/marketing-withdraw` carries NO route-level gate, and
that absence is a RULING (Gate 1 Q4), not an oversight.** It inherits the
router's `(OWNER, SHIFT_MANAGER)`. Withdrawing a marketing consent is the one
privacy action a front-desk staffer must be able to take while the woman is on
the telephone — it destroys nothing, it is the lesser action short of erasure
(D15), and routing it through the owner would mean telling a caller exercising a
statutory right to ring back tomorrow. The other three stay owner-only: two of
them assemble or destroy a whole person, and the third publishes the boutique's
legal notice.

Because a default-deny walker cannot tell a deliberate omission from a forgotten
gate, `test_marketing_withdraw_is_not_owner_only_in_the_route_table` asserts the
absence POSITIVELY. Adding a `require_role(OWNER)` here to "tidy up" reddens it.

**Real HTTP verbs** are the shipped /manage convention (`dashboard/router.py`,
`customers/router.py`, `auth/staff_router.py`, in identical words). The
`.claude/rules` RPC guidance is Kotlin boilerplate for another codebase; F15's
D7 already ruled this.

**`_no_store` is another local three-line copy**, not an import — the decision is
recorded in `auth/staff_router.py:21-25`. It matters more here than anywhere:
`subject-export` answers with a whole person in one document, and a cached copy
of that in a shared boutique browser is the disclosure the route exists to
control.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth.dependencies import get_current_staff, require_role
from app.auth.service import StaffContext
from app.models.constants import StaffRole
from app.privacy.schemas import (
    MarketingWithdrawRequest,
    MarketingWithdrawResponse,
    PrivacyResponse,
    PrivacyUpdate,
    SubjectEraseRequest,
    SubjectEraseResponse,
    SubjectExportRequest,
    SubjectExportResponse,
)
from app.privacy.service import PrivacyService, privacy_response
from app.privacy.text import resolve_privacy
from app.tenancy.middleware import get_current_tenant

NO_STORE = "no-store"


def _no_store(response: Response) -> None:
    response.headers["cache-control"] = NO_STORE


def get_privacy_service(request: Request) -> PrivacyService:
    service: PrivacyService = request.app.state.privacy_service
    return service


router = APIRouter(
    prefix="/manage",
    dependencies=[
        Depends(_no_store),
        Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)),
    ],
)

Staff = Annotated[StaffContext, Depends(get_current_staff)]
Service = Annotated[PrivacyService, Depends(get_privacy_service)]

OWNER_ONLY = [Depends(require_role(StaffRole.OWNER))]


@router.get("/privacy")
async def get_privacy(request: Request) -> PrivacyResponse:
    """NO service and NO database round trip, and that is D13 rather than a
    shortcut. `RepositoryTenantResolver` has already SELECTed the whole tenants
    row to route this request and builds `TenantContext(id, slug, name,
    settings)` with no cache, so the documents are a pure function over data
    already in hand — and an owner's edit is visible on the very next request.

    It declares no `staff` parameter for `customers/router.py`'s reason: the
    router-level gate needs no binding, so the only reason to inject
    `StaffContext` is a use for the acting identity, and a read has none.
    """
    return privacy_response(resolve_privacy(get_current_tenant(request).settings))


@router.put("/privacy", dependencies=OWNER_ONLY)
async def update_privacy(
    request: Request, staff: Staff, service: Service, body: PrivacyUpdate
) -> PrivacyResponse:
    """Owner-only: this publishes the boutique's legal notice, and the boutique
    — not the platform, not a shift manager — is the controller answerable for
    what it says.

    Both body keys are required (D16); the schema's docstring has the whole
    argument, and `test_privacy_api` pins that omitting either is a 422.
    """
    return await service.update_privacy(
        get_current_tenant(request).id, notice_text=body.notice_text, dpa_text=body.dpa_text
    )


@router.post("/privacy/subject-export", dependencies=OWNER_ONLY)
async def subject_export(
    request: Request, staff: Staff, service: Service, body: SubjectExportRequest
) -> SubjectExportResponse:
    """Owner-only, and audited as an ACCESS (D19): checklist row 38 covers "data
    access by operators", not only mutations."""
    return await service.export_subject(
        get_current_tenant(request).id, raw_phone=body.phone, actor=staff, reason=body.reason
    )


@router.post("/privacy/subject-erase", dependencies=OWNER_ONLY)
async def subject_erase(
    request: Request, staff: Staff, service: Service, body: SubjectEraseRequest
) -> SubjectEraseResponse:
    """Owner-only and irreversible."""
    return await service.erase_subject(
        get_current_tenant(request).id,
        customer_id=body.customer_id,
        actor=staff,
        reason=body.reason,
    )


@router.post("/privacy/marketing-withdraw")
async def marketing_withdraw(
    request: Request, service: Service, body: MarketingWithdrawRequest
) -> MarketingWithdrawResponse:
    """⚠ NO `dependencies=OWNER_ONLY` — Gate 1 Q4. See the module docstring; the
    absence is asserted positively in test_staff_role_gating.py.

    No `staff` parameter either, and for the same reason the two GETs in
    `customers/router.py` declare none: nothing here reads the acting identity.
    This route writes no audit row — it is a consent state change the subject
    herself asked for over the telephone, and `audit_log` is exempt from every
    retention class, so a row per revocation would accumulate `customer_id`s
    forever to record the one action that takes nothing away.
    """
    return await service.withdraw_marketing(
        get_current_tenant(request).id, customer_id=body.customer_id, raw_phone=body.phone
    )
