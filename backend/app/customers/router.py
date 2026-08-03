"""The customer CRM: three routes on /manage.

**Another router on /manage**, registered after gateway_router in create_app()
and carrying the same shadowing warning the others carry — a duplicated
(method, path) would silently win or lose on include order. `ROUTES` in
test_customers_api.py is what keeps that honest, and the include comment in
main.py is where the count lives.

**Both roles at ROUTER level.** The SMC epic's locked table admits owner and
shift manager, and there is no per-role projection: a shift manager sees the
same card the owner does and edits the same notes. Router-level so a route
added here later cannot forget the gate, and because test_staff_role_gating's
default-deny walker reads `allowed_roles` off the router — a /manage router
without one is a red build. It must NOT be added to that module's OWNER_ONLY
set: a both-roles route there reports as `unenforced_owner_only`.

**The two GETs declare no `staff` parameter; the PATCH does.** The RoleGate
above runs router-level and needs no binding, so the only reason to inject
StaffContext is a use for the acting identity — and the PATCH has exactly one,
`actor_id` on its audit row (D8). Declaring it on the GETs would be a parameter
with no reader, and would put the session-derived tenant_id in reach on two
routes that have no other reason to want it. The tenant comes from
`get_current_tenant(request)` on all three, host-derived, never from
`StaffContext.tenant_id`.

**`_no_store` is another local three-line copy**, not an import. The
alternative points the dependency arrow backwards to save three lines;
`auth/staff_router.py:21-25` records the decision. No ordinal is stated here on
purpose — every ordinal written into this codebase so far has gone stale.

**No try/except and no error mapping anywhere below.**
`CustomerNotFoundError` and `CustomerValidationError` subclass the
`app/errors.py` bases, so the platform handlers answer both through Starlette's
MRO walk and F53 registers nothing of its own (D9).

**Real HTTP verbs and a path parameter** are the shipped /manage convention
(`dashboard/router.py`, `auth/staff_router.py`, `booking/owner_router.py`, all
three in identical words). The `.claude/rules` RPC / `@QueryValue` guidance is
Kotlin boilerplate for another codebase; F15's D7 already ruled this.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.auth.dependencies import get_current_staff, require_role
from app.auth.service import StaffContext
from app.customers.schemas import CustomerDetail, CustomerListResponse, UpdateCustomerRequest
from app.customers.service import CustomersService
from app.customers.validation import (
    CUSTOMER_LIST_DEFAULT_LIMIT,
    CUSTOMER_LIST_MAX_LIMIT,
    MAX_LIST_OFFSET,
    MAX_SEARCH_TERM_LENGTH,
)
from app.models.constants import StaffRole
from app.tenancy.middleware import get_current_tenant

NO_STORE = "no-store"


def _no_store(response: Response) -> None:
    response.headers["cache-control"] = NO_STORE


def get_customers_service(request: Request) -> CustomersService:
    service: CustomersService = request.app.state.customers_service
    return service


router = APIRouter(
    prefix="/manage",
    dependencies=[
        Depends(_no_store),
        Depends(require_role(StaffRole.OWNER, StaffRole.SHIFT_MANAGER)),
    ],
)

Staff = Annotated[StaffContext, Depends(get_current_staff)]
Service = Annotated[CustomersService, Depends(get_customers_service)]


@router.get("/customers")
async def list_customers(
    request: Request,
    service: Service,
    q: Annotated[str | None, Query(max_length=MAX_SEARCH_TERM_LENGTH)] = None,
    # `le=MAX_LIST_OFFSET` at the boundary, and the service clamps again below
    # it: `offset` binds into OFFSET $n::BIGINT, so an unbounded Python int from
    # a non-router caller would die in asyncpg's encoder as a 500.
    offset: Annotated[int, Query(ge=0, le=MAX_LIST_OFFSET)] = 0,
    limit: Annotated[int, Query(ge=1, le=CUSTOMER_LIST_MAX_LIMIT)] = CUSTOMER_LIST_DEFAULT_LIMIT,
) -> CustomerListResponse:
    """A blank or whitespace-only `q` is not a filter — the repository drops the
    predicate rather than searching for the empty string, because "she cleared
    the box" means "show me everyone"."""
    return await service.list_customers(
        get_current_tenant(request).id, q=q, offset=offset, limit=limit
    )


@router.get("/customers/{customer_id}")
async def get_customer(request: Request, service: Service, customer_id: UUID) -> CustomerDetail:
    return await service.detail(get_current_tenant(request).id, customer_id)


@router.patch("/customers/{customer_id}")
async def update_customer(
    request: Request,
    staff: Staff,
    service: Service,
    customer_id: UUID,
    body: UpdateCustomerRequest,
) -> CustomerDetail:
    """Answers the SAME fully-built detail the GET does, on the write path and
    on the D8 no-op path alike: the console does `setDetail(updated)`
    unconditionally, so a response with empty panels would blank the booking
    history and the SMS log the instant the owner pressed save."""
    return await service.update(
        get_current_tenant(request).id,
        customer_id,
        notes=body.notes,
        tags=body.tags,
        actor=staff,
    )
