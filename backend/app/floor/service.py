"""The floor read and the two break writers.

**The authorization rule has two axes and lives HERE, not on the router.** The
router's gate answers "may this role open the floor at all" — all five, because
the payload carries no customer data. This answers "may this person toggle THAT
person", which no `RoleGate` can express because it depends on the target:

    owner, shift_manager -> anybody
    reception, sales_assistant, seamstress -> herself, and nobody else

**The check is each method's first statement and it runs before the session is
opened.** That ordering is the security property, not a style choice: a 403
raised after a read is an existence oracle, and a non-elevated staffer could
enumerate the tenant's staff ids by which error came back.
`test_floor_service.py` asserts the repository was never called, which is the
only way to state it.

**No rate limiter and no advisory lock.** The writers are idempotent by
predicate and touch one column on one row (see `StaffUsersRepository`), and no
`/manage` router carries a limiter.
"""

import datetime
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.dependencies import NotAuthorizedError
from app.auth.service import StaffContext
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.models.constants import AuditAction, StaffCardStatus, StaffRole
from app.models.staff_user import StaffUser

# Frozen as a module constant so the membership test reads as the rule it is.
# Spelled from the enum rather than as literals: a sixth role added to
# StaffRole is NOT elevated by default, which is the safe direction to fail.
ELEVATED_ROLES = frozenset({StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value})


def card_status(row: StaffUser) -> StaffCardStatus:
    """Derived on read, never stored (D2 adds no status column).

    `occupied` arrives with F36 and is never true until then — it needs an open
    `fitting_room_assignments` row, and that table does not exist yet.
    """
    if row.break_started_at is not None:
        return StaffCardStatus.BREAK
    return StaffCardStatus.AVAILABLE


class FloorService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime.datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._staff = StaffUsersRepository()
        self._audit = AuditLogRepository()
        self._clock = clock or (lambda: datetime.datetime.now(datetime.UTC))

    async def floor(self, tenant_id: UUID) -> list[StaffUser]:
        """Every live staffer, `created_at` ASC so the founding owner is first
        and the cards do not shuffle between ticks.

        No per-role projection: all five roles see the same list, because there
        is nothing on a card a colleague may not see — a name, a role and a
        status. That is also what keeps this payload out of D11's merge
        argument: no customer data, so no gate has to be widened over one.
        """
        async with tenant_session(self._sessions, tenant_id) as session:
            return await self._staff.list_live(session, tenant_id)

    async def start_break(
        self, tenant_id: UUID, staff_id: UUID, *, actor: StaffContext
    ) -> StaffUser:
        self._authorize(staff_id, actor)
        at = self._clock()
        async with tenant_session(self._sessions, tenant_id) as session:
            wrote, row = await self._staff.start_break(session, tenant_id, staff_id, at=at)
            if row is None:
                raise DomainNotFoundError("staff_user")
            if wrote:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.STAFF_BREAK_STARTED,
                    actor_id=actor.id,
                    entity=str(staff_id),
                    # `row.break_started_at`, not `at`: on the winning write they
                    # are equal, and reading it off the row keeps this honest if
                    # the writer ever stops taking the caller's clock.
                    details={
                        "target": str(staff_id),
                        "break_started_at": _isoformat(row.break_started_at),
                    },
                )
            return row

    async def end_break(self, tenant_id: UUID, staff_id: UUID, *, actor: StaffContext) -> StaffUser:
        self._authorize(staff_id, actor)
        async with tenant_session(self._sessions, tenant_id) as session:
            # ⚠ CAPTURED BEFORE THE WRITE, into a local, and that is not style.
            # `end_break`'s UPDATE is ORM-enabled DML whose `evaluate`
            # synchronization stamps `break_started_at = NULL` onto this very
            # instance — `before` and the row the writer returns are the SAME
            # object out of one identity map — so reading it afterwards records
            # `null` and empties the trail this row exists for. The identical
            # trap on `from_status` is written up at `booking/owner.py:326-333`.
            before = await self._staff.by_id(session, tenant_id, staff_id)
            previous = before.break_started_at if before is not None else None

            wrote, row = await self._staff.end_break(session, tenant_id, staff_id)
            if row is None:
                raise DomainNotFoundError("staff_user")
            if wrote:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.STAFF_BREAK_ENDED,
                    actor_id=actor.id,
                    entity=str(staff_id),
                    # Ending a break destroys the only copy of when it began and
                    # there is no history table (D2), so this is the whole
                    # informational content of the row.
                    details={
                        "target": str(staff_id),
                        "previous_break_started_at": _isoformat(previous),
                    },
                )
            return row

    @staticmethod
    def _authorize(staff_id: UUID, actor: StaffContext) -> None:
        """The acting identity is `StaffContext`, resolved from the session
        cookie by `get_current_staff`. It is NEVER read from the path, the query
        or a body: the request names only WHOM to toggle, never WHO is asking. A
        body-supplied `staff_user_id` doubling as the caller's identity is the
        one shape that turns "any staffer on herself" into "any staffer on
        anyone".

        Compares IDS. A display name or an email would be a mutable string two
        people can share.
        """
        if staff_id != actor.id and actor.role not in ELEVATED_ROLES:
            raise NotAuthorizedError


def _isoformat(value: datetime.datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
