"""The console's waitlist: list and cancel, two routes on /manage.

**The TWELFTH /manage router**, registered after the privacy one and before
storefront_router in create_app(), keeping every /manage router contiguous and
ahead of the anonymous surfaces. Same shadowing hazard as the eleven above — a
duplicated (method, path) would silently win or lose on include order with no
error at all; the manage walk in test_waitlist_api.py is what keeps these two
honest.

**Both roles at ROUTER level** — `require_role(OWNER, SHIFT_MANAGER)`, the
customers/checkin-qr shape verbatim, and exactly-two matching the
booking-management gate: the SMC locked matrix admits all-five or exactly-two
only, and cancel is a mutation reception should route through a manager. The
mechanical consequence: these routes must NOT join test_staff_role_gating.py's
OWNER_ONLY set (pinned in test_waitlist_api.py).

**`_no_store` is another local three-line copy**, not an import — the shipped
convention (auth/staff_router.py:22-27 records the decision).
"""

import datetime
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.auth.dependencies import get_current_staff, require_role
from app.auth.service import StaffContext
from app.models.constants import StaffRole
from app.tenancy.middleware import get_current_tenant
from app.waitlist.router import get_waitlist_service
from app.waitlist.schemas import ManageWaitlistResponse, ManageWaitlistRow
from app.waitlist.service import WaitlistService

NO_STORE = "no-store"


def _no_store(response: Response) -> None:
    response.headers["cache-control"] = NO_STORE


router = APIRouter(
    prefix="/manage",
    dependencies=[
        Depends(_no_store),
        Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)),
    ],
)

Waitlist = Annotated[WaitlistService, Depends(get_waitlist_service)]
Staff = Annotated[StaffContext, Depends(get_current_staff)]


@router.get("/waitlist")
async def list_waitlist(
    request: Request, service: Waitlist, day: datetime.date | None = None
) -> ManageWaitlistResponse:
    """`day` optional; absent = all active entries for `day >= today`, ordered
    `(day, created_at)` — FIFO visible as list order. No pagination (D5's
    recorded ceiling)."""
    return await service.list_entries(get_current_tenant(request).id, day=day)


@router.post("/waitlist/{entry_id}/cancel")
async def cancel_waitlist_entry(
    request: Request, service: Waitlist, staff: Staff, entry_id: uuid.UUID
) -> ManageWaitlistRow:
    """A guarded UPDATE behind it: the double-tap answers the row as-is (200,
    not an error), unknown/foreign ids answer the shipped 404."""
    return await service.cancel_entry(
        get_current_tenant(request).id, entry_id=entry_id, actor=staff
    )
