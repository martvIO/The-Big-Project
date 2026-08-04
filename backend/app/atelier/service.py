"""The atelier board's reads and its six writes.

**The four-outcome discrimination lives HERE and nowhere else.** The repository
answers `(wrote, row)` because three of its five guarded writes have TWO OPPOSITE
causes for zero rows — "already there" and "overtaken" — and telling them apart
needs `stage_of` and the caller's own intent, neither of which belongs in a
statement builder.

⚠ THE DISCRIMINATOR IS ONE EQUALITY AND ONE ELSE, ON ALL THREE OF ADVANCE, UNDO
AND CLAIM. The mapping must be TOTAL over every state the re-read can show,
because the UPDATE and the re-read are two statements and nothing holds a lock
between them: a zero-row UPDATE takes no row lock, this repo runs READ COMMITTED,
and the re-read therefore takes a fresh snapshot. Written as `if == target /
elif > target` with no else, the handler falls off the end and returns `None` —
a 500 on the hottest mutation in the feature. Every one of the three has a named
test in `test_atelier_service.py` for the branch that pair drops.

**The authorization rule has two shapes and both live here, not on the router.**
The router's gate answers "may this role open the atelier at all" — owner, shift
manager, seamstress. These answer "may this person act on THAT ticket", which no
`RoleGate` can express because it depends on the ticket's own
`assigned_staff_user_id`:

    advance / undo   owner, shift_manager -> anything
                     seamstress           -> her own ticket, OR AN UNASSIGNED ONE
    update           seamstress           -> her own ticket ONLY
    assign           seamstress           -> herself on unassigned, or release her own
    delete           refused by the ROUTE, not here (D10)

The advance/update asymmetry is the design and not an oversight: advancing an
unassigned ticket is a seamstress RECORDING WORK SHE HAS JUST DONE, while editing
a `due_date` is a SCHEDULING DECISION about somebody else's queue.

**The refusals that depend on the REQUEST ALONE are each method's first
statement, before any session is opened** (`floor/service.py:11-16`'s rule) — a
403 raised after a read is an existence oracle. The ones that depend on the
TICKET cannot be, and the generic `NotAuthorizedError` body is what keeps that
from being an oracle: it is byte-identical to the 403 an unadmitted role gets, so
a probe learns only that it is not permitted, which it already knew.

**The effort bands arrive as a plain dict from the ROUTER**, resolved from
`TenantContext.settings` which the tenancy middleware already bound. Reading them
through `TenantsRepository` would open a fourth session, pool checkout and
BEGIN/COMMIT on a five-second poll — that repository is constructed with a
`session_factory` and opens its own session inside every method, so it cannot
join this `tenant_session`.
"""

import datetime
from collections.abc import Callable, Mapping
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.atelier.schemas import (
    AssignTicketRequest,
    AtelierBoardResponse,
    AtelierTicket,
    CreateTicketRequest,
    SeamstressCapacityResponse,
    SetCapacityRequest,
    StageRequest,
    UpdateTicketRequest,
)
from app.atelier.stages import STAGE_COLUMNS, later_columns, stage_of
from app.atelier.validation import (
    CONTROL_CHARS,
    CONTROL_CHARS_EXCEPT_WS,
    MAX_DRESS_LABEL_LENGTH,
    MAX_DRESS_SIZE_LENGTH,
    MAX_DUE_DATE_HORIZON_DAYS,
    MAX_TICKET_NOTES_LENGTH,
    AtelierValidationError,
    TicketAlreadyAssignedError,
    TicketStageConflictError,
)
from app.auth.dependencies import NotAuthorizedError
from app.auth.service import StaffContext
from app.booking.validation import validate_customer_name
from app.db.repositories.alteration_tickets import AlterationTicketsRepository
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.dresses import DressesRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.models.alteration_ticket import AlterationTicket
from app.models.constants import AuditAction, EffortBand, StaffRole, TicketStage
from app.models.customer import Customer
from app.models.staff_user import StaffUser
from app.notifications.validation import normalize_israeli_mobile
from app.storefront.validation import today_jerusalem

# Spelled from the enum rather than as literals, `floor/service.py:38-41`'s rule:
# a sixth role added to StaffRole is NOT elevated by default, which is the safe
# direction to fail.
ELEVATED_ROLES = frozenset({StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value})

# The full-replace set, in the order the audit row's `changed` list reports them.
# Names only ever — `notes` may hold a bride's measurements and `audit_log` has a
# different retention clock from the row it describes.
EDITABLE_FIELDS = (
    "due_date",
    "effort_minutes",
    "dress_id",
    "dress_name",
    "dress_size",
    "notes",
)

Bands = Mapping[EffortBand, int]


class AtelierService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime.datetime] | None = None,
    ) -> None:
        self._sessions = session_factory
        self._tickets = AlterationTicketsRepository()
        self._customers = CustomersRepository()
        self._dresses = DressesRepository()
        self._staff = StaffUsersRepository()
        self._audit = AuditLogRepository()
        self._clock = clock or (lambda: datetime.datetime.now(datetime.UTC))

    # --- the poll ------------------------------------------------------------

    async def board(self, tenant_id: UUID, *, bands: Bands) -> AtelierBoardResponse:
        """THREE business statements, and that number is the budget: the tickets,
        their customers' names in one `IN`, and the assignee union. The bands are
        not a fourth — they came off the request's already-bound tenant context.
        """
        today = today_jerusalem(self._clock)
        async with tenant_session(self._sessions, tenant_id) as session:
            tickets, truncated = await self._tickets.board(session, tenant_id, today=today)
            customers = await self._customers.by_ids(
                session, tenant_id, [row.customer_id for row in tickets]
            )
            assignees = await self._tickets.assignees(session, tenant_id)
        return AtelierBoardResponse.build(
            tickets=tickets,
            customers=customers,
            assignees=assignees,
            bands=bands,
            truncated=truncated,
            today=today,
        )

    # --- intake --------------------------------------------------------------

    async def create(
        self,
        tenant_id: UUID,
        request: CreateTicketRequest,
        *,
        actor: StaffContext,
        bands: Bands,
    ) -> AtelierTicket:
        today = today_jerusalem(self._clock)
        validate_customer_name(request.customer_name)
        phone = normalize_israeli_mobile(request.customer_phone)
        self._validate_ticket_fields(
            due_date=request.due_date,
            dress_id=request.dress_id,
            dress_name=request.dress_name,
            dress_size=request.dress_size,
            notes=request.notes,
            today=today,
        )
        minutes = bands[request.effort_band]

        async with tenant_session(self._sessions, tenant_id) as session:
            dress_name = await self._resolve_dress_name(
                session, tenant_id, dress_id=request.dress_id, dress_name=request.dress_name
            )
            if request.assigned_staff_user_id is not None:
                await self._require_seamstress(session, tenant_id, request.assigned_staff_user_id)
            customer, renamed = await self._resolve_customer(
                session, tenant_id, phone=phone, name=request.customer_name
            )
            if renamed:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.ATELIER_CUSTOMER_RENAMED,
                    actor_id=actor.id,
                    entity=str(customer.id),
                    # THE FIELD NAME AND NEITHER SPELLING. Both the old and the
                    # new are the bride's own name, and audit_log's retention
                    # clock is not `customers`'.
                    details={"field": "name"},
                )
            row = await self._tickets.insert(
                session,
                tenant_id=tenant_id,
                customer_id=customer.id,
                due_date=request.due_date,
                effort_minutes=minutes,
                at=self._clock(),
                assigned_staff_user_id=request.assigned_staff_user_id,
                dress_id=request.dress_id,
                dress_name=dress_name,
                dress_size=request.dress_size,
                notes=request.notes,
            )
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.ATELIER_TICKET_CREATED,
                actor_id=actor.id,
                entity=str(row.id),
                # IDENTIFIERS and one number. No name, no phone, no notes — the
                # audit row names WHICH customer, never who she is.
                details={
                    "customer_id": str(customer.id),
                    "due_date": request.due_date.isoformat(),
                    "effort_minutes": minutes,
                    "assigned_staff_user_id": _str_or_none(request.assigned_staff_user_id),
                },
            )
            # The echo of the RESOLVED name — which D6 called the mitigation for
            # `upsert` rewriting `customers.name` unconditionally, and which
            # review showed IS NOT ONE: `upsert` has already stored the typed
            # string, so on every path but the race the echo is exactly what she
            # typed and can never differ from it. Kept because the RACE path
            # (`_resolve_customer`'s savepoint) really does answer the WINNER's
            # name; the rename itself is mitigated by the audit row above.
            return AtelierTicket.from_row(row, customer_name=customer.name, today=today)

    # --- the edit ------------------------------------------------------------

    async def update(
        self,
        tenant_id: UUID,
        ticket_id: UUID,
        request: UpdateTicketRequest,
        *,
        actor: StaffContext,
        bands: Bands,
    ) -> AtelierTicket:
        today = today_jerusalem(self._clock)
        self._validate_ticket_fields(
            due_date=request.due_date,
            dress_id=request.dress_id,
            dress_name=request.dress_name,
            dress_size=request.dress_size,
            notes=request.notes,
            today=today,
        )
        minutes = bands[request.effort_band]

        async with tenant_session(self._sessions, tenant_id) as session:
            row = await self._load(session, tenant_id, ticket_id)
            # A seamstress may edit ONLY her own: a `due_date` on a ticket she
            # does not hold is a decision about somebody else's queue.
            if actor.role not in ELEVATED_ROLES and row.assigned_staff_user_id != actor.id:
                raise NotAuthorizedError
            dress_name = await self._resolve_dress_name(
                session, tenant_id, dress_id=request.dress_id, dress_name=request.dress_name
            )
            fields: dict[str, object] = {
                "due_date": request.due_date,
                "effort_minutes": minutes,
                "dress_id": request.dress_id,
                "dress_name": dress_name,
                "dress_size": request.dress_size,
                "notes": request.notes,
            }
            # ⚠ THE DIFF IS TAKEN BEFORE THE WRITE, into locals. `update()` is
            # ORM-enabled DML whose `evaluate` synchronization stamps the SET
            # values onto this very instance — the one `_load` just handed back
            # out of the identity map — so a diff taken afterwards is empty and
            # every edit silently loses its audit row.
            changed = [name for name in EDITABLE_FIELDS if getattr(row, name) != fields[name]]

            refreshed = await self._tickets.update(session, tenant_id, ticket_id, **fields)  # type: ignore[arg-type]
            if refreshed is None:
                raise DomainNotFoundError("alteration_ticket")
            if changed:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.ATELIER_TICKET_UPDATED,
                    actor_id=actor.id,
                    entity=str(ticket_id),
                    # KEY NAMES AND NEVER VALUES.
                    details={"changed": changed},
                )
            return await self._respond(session, tenant_id, refreshed, today=today)

    # --- the state machine ---------------------------------------------------

    async def advance(
        self, tenant_id: UUID, ticket_id: UUID, request: StageRequest, *, actor: StaffContext
    ) -> AtelierTicket:
        today = today_jerusalem(self._clock)
        target = request.stage
        async with tenant_session(self._sessions, tenant_id) as session:
            row = await self._load(session, tenant_id, ticket_id)
            self._authorize_work(row, actor)
            # Before the write, for the identity-map reason `update`'s diff
            # states — `advance_stage` stamps the target column onto this
            # instance whatever the database matched.
            previous = stage_of(row)

            wrote, refreshed = await self._tickets.advance_stage(
                session, tenant_id, ticket_id, target, at=self._clock()
            )
            if refreshed is None:
                raise DomainNotFoundError("alteration_ticket")
            if wrote:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.ATELIER_TICKET_STAGE_ADVANCED,
                    actor_id=actor.id,
                    entity=str(ticket_id),
                    details={"from": previous.value, "to": target.value},
                )
            # ⚠ ONE EQUALITY AND ONE ELSE. `stage_of(refreshed) == target` is
            # THIS caller's own repeat and answers 200 unchanged with no audit
            # row, so the first tapper's timestamp survives. EVERYTHING ELSE is a
            # conflict — including a stage strictly EARLIER than the target,
            # which a concurrent undo makes reachable and which an
            # `elif stage > target` pair returns None for.
            elif stage_of(refreshed) != target:
                raise TicketStageConflictError
            return await self._respond(session, tenant_id, refreshed, today=today)

    async def undo(
        self, tenant_id: UUID, ticket_id: UUID, request: StageRequest, *, actor: StaffContext
    ) -> AtelierTicket:
        stage = request.stage
        if stage is TicketStage.INTAKE:
            # Clearing `intake_at` would leave a ticket whose DERIVED stage is
            # `intake` anyway and whose trail says nothing happened. The remedy
            # for a ticket that should not exist is the delete verb.
            raise AtelierValidationError("intake cannot be undone")

        today = today_jerusalem(self._clock)
        async with tenant_session(self._sessions, tenant_id) as session:
            row = await self._load(session, tenant_id, ticket_id)
            self._authorize_work(row, actor)
            # ⚠ CAPTURED INTO A LOCAL BEFORE THE WRITE, and it is load-bearing in
            # a way `previous_break_started_at` was not: the five timestamps ARE
            # the trail, so this is the one write in the feature that DESTROYS
            # history and the audit row is the only place it survives. Read after
            # the write it records `null` and empties the row it exists to fill.
            previous_stamp = getattr(row, STAGE_COLUMNS[stage])

            wrote, refreshed = await self._tickets.undo_stage(session, tenant_id, ticket_id, stage)
            if refreshed is None:
                raise DomainNotFoundError("alteration_ticket")
            if wrote:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.ATELIER_TICKET_STAGE_UNDONE,
                    actor_id=actor.id,
                    entity=str(ticket_id),
                    details={"stage": stage.value, "previous_stamp": _isoformat(previous_stamp)},
                )
            # ⚠ ONE PREDICATE AND ONE ELSE, for D3's reason and one more of its
            # own: "the column is already NULL" and "a later stamp exists" are
            # NOT DISJOINT — both hold whenever a ticket was undone and then
            # advanced past this stage, a forward skip D2 makes legal — so a
            # caller checking them in that order answers 200 for a ticket that
            # has moved on. A genuine double tap is the column NULL **and
            # nothing after it stamped**; anything else is a conflict.
            elif not _cleared_through(refreshed, stage):
                raise TicketStageConflictError
            return await self._respond(session, tenant_id, refreshed, today=today)

    # --- assignment ----------------------------------------------------------

    async def assign(
        self,
        tenant_id: UUID,
        ticket_id: UUID,
        request: AssignTicketRequest,
        *,
        actor: StaffContext,
    ) -> AtelierTicket:
        target = request.staff_user_id
        elevated = actor.role in ELEVATED_ROLES
        # ⚠ FIRST STATEMENT, BEFORE THE SESSION. This refusal depends on the
        # REQUEST alone — a seamstress may name only herself or `null` — so it
        # must not read the ticket first: a 403 raised after a read is an
        # existence oracle.
        if not elevated and target not in (None, actor.id):
            raise NotAuthorizedError

        today = today_jerusalem(self._clock)
        async with tenant_session(self._sessions, tenant_id) as session:
            if target is not None:
                await self._require_seamstress(session, tenant_id, target)
            row = await self._load(session, tenant_id, ticket_id)
            # Before the write: `assign`/`claim`/`release` all stamp the new
            # value onto this instance whatever the database matched.
            before = row.assigned_staff_user_id

            if elevated:
                # Deliberately LAST-WRITE-WINS and it takes no 409 (D9).
                wrote, refreshed = await self._tickets.assign(
                    session, tenant_id, ticket_id, staff_user_id=target
                )
                refreshed = self._present(refreshed)
            elif target is None:
                wrote, refreshed = await self._tickets.release(
                    session, tenant_id, ticket_id, staff_user_id=actor.id
                )
                refreshed = self._present(refreshed)
                # The mirror of the claim's discriminator: a zero-row release
                # whose re-read is unassigned is her own double tap; anything
                # else means she does not hold it and never did.
                if not wrote and refreshed.assigned_staff_user_id is not None:
                    raise TicketAlreadyAssignedError
            else:
                wrote, refreshed = await self._tickets.claim(
                    session, tenant_id, ticket_id, staff_user_id=actor.id
                )
                refreshed = self._present(refreshed)
                # ⚠ ONE EQUALITY AND ONE ELSE. "Assigned to her" is a double tap
                # or her own second device (200); ANYTHING ELSE is a colleague
                # getting there first — explicitly including a re-read showing
                # NULL, which a winner who claims and releases in the gap makes
                # ordinary under READ COMMITTED.
                if not wrote and refreshed.assigned_staff_user_id != actor.id:
                    raise TicketAlreadyAssignedError

            if refreshed.assigned_staff_user_id != before:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.ATELIER_TICKET_ASSIGNED,
                    actor_id=actor.id,
                    entity=str(ticket_id),
                    details={
                        "from": _str_or_none(before),
                        "to": _str_or_none(refreshed.assigned_staff_user_id),
                    },
                )
            return await self._respond(session, tenant_id, refreshed, today=today)

    # --- removal -------------------------------------------------------------

    async def delete(self, tenant_id: UUID, ticket_id: UUID, *, actor: StaffContext) -> None:
        """No role check here, deliberately: `delete` is the one verb whose
        refusal is expressible as a `RoleGate`, so it carries a per-route
        `require_role(OWNER, SHIFT_MANAGER)` and the route table is where a
        seamstress is refused (D10). Duplicating it here would put the rule in
        two places that can disagree.
        """
        async with tenant_session(self._sessions, tenant_id) as session:
            row = await self._load(session, tenant_id, ticket_id)
            stage = stage_of(row)
            if not await self._tickets.soft_delete(session, tenant_id, ticket_id):
                # Already gone — a concurrent delete won. No audit row: a no-op
                # writes nothing, and a second `atelier_ticket_deleted` would
                # claim this caller removed a ticket she did not remove.
                raise DomainNotFoundError("alteration_ticket")
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.ATELIER_TICKET_DELETED,
                actor_id=actor.id,
                entity=str(ticket_id),
                # What was LOST from the board — a ticket deleted at `qc` is a
                # different event from one deleted ten seconds after intake.
                details={"stage": stage.value},
            )

    # --- capacity ------------------------------------------------------------

    async def set_capacity(
        self,
        tenant_id: UUID,
        staff_user_id: UUID,
        request: SetCapacityRequest,
        *,
        actor: StaffContext,
        tenant_default: int | None,
    ) -> SeamstressCapacityResponse:
        """Her weekly hours (D6). No role check here: this route's refusal
        depends on NOTHING BUT THE ROLE, which is the single criterion a
        `RoleGate` can express, so it carries `require_role(OWNER,
        SHIFT_MANAGER)` on the route — `delete`'s shape exactly — and putting it
        here too would be the same rule in two places that can disagree.

        `tenant_default` arrives from the router off `TenantContext.settings`,
        the way the bands do, at zero statements.

        Two statements: the target read (which is also the audit row's `from`)
        and the guarded UPDATE. There is deliberately no third — a single-assignee
        `SUM(effort_minutes)` would let this answer a whole `SeamstressRef`, but
        the console already holds both load numbers from the last tick and the
        next one corrects them.
        """
        async with tenant_session(self._sessions, tenant_id) as session:
            # One indistinguishable 400 for a receptionist, a retired staffer, an
            # unknown id and another tenant's id (D6/D13). There is no 404 here.
            row = await self._require_seamstress(session, tenant_id, staff_user_id)
            # ⚠ INTO A LOCAL, BEFORE THE WRITE. The UPDATE's `evaluate`
            # synchronization stamps the new hours onto this very instance, so a
            # capture afterwards records the new value as the old one
            # (`floor/service.py:108-116`).
            before = row.weekly_capacity_hours

            refreshed = await self._staff.set_weekly_capacity_hours(
                session, tenant_id, staff_user_id, hours=request.weekly_capacity_hours
            )
            if refreshed is None:
                # Zero rows: she was soft-deleted BETWEEN the check and the
                # UPDATE. A race, and this route's only 404.
                raise DomainNotFoundError("staff_user")

            if refreshed.weekly_capacity_hours != before:
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.ATELIER_CAPACITY_SET,
                    actor_id=actor.id,
                    entity=str(staff_user_id),
                    details={"from": before, "to": refreshed.weekly_capacity_hours},
                )
            return SeamstressCapacityResponse.from_row(refreshed, tenant_default=tenant_default)

    # --- helpers -------------------------------------------------------------

    @staticmethod
    def _authorize_work(row: AlterationTicket, actor: StaffContext) -> None:
        """advance and undo: a seamstress may act on her own ticket OR AN
        UNASSIGNED ONE. Refusing the second would force a claim-then-advance
        two-tap on the common case — a hem picked up off the rack — and a system
        that makes people take an extra step to be honest gets lied to."""
        if actor.role in ELEVATED_ROLES:
            return
        if row.assigned_staff_user_id not in (None, actor.id):
            raise NotAuthorizedError

    async def _load(
        self, session: AsyncSession, tenant_id: UUID, ticket_id: UUID
    ) -> AlterationTicket:
        row = await self._tickets.by_id(session, tenant_id, ticket_id)
        return self._present(row)

    @staticmethod
    def _present(row: AlterationTicket | None) -> AlterationTicket:
        """Soft-deleted, another tenant's, or never existed — deliberately one
        indistinguishable 404 (RLS plus the explicit predicate make a foreign row
        indistinguishable from a missing one, by design)."""
        if row is None:
            raise DomainNotFoundError("alteration_ticket")
        return row

    async def _require_seamstress(
        self, session: AsyncSession, tenant_id: UUID, staff_user_id: UUID
    ) -> StaffUser:
        """⚠ POINT-IN-TIME, AND A NUDGE RATHER THAN AN INVARIANT. Nothing
        re-validates it afterwards and two shipped writers break it the moment
        they run — `StaffUsersRepository.update` sets `role` unconditionally and
        its `soft_delete` retires her. That is exactly why the board's
        `seamstresses[]` is a UNION and carries `assignable`.

        What it does buy: F42's load bars are `SUM(effort_minutes) GROUP BY
        assigned_staff_user_id` against a capacity column F42 puts on
        seamstresses, so a ticket assigned to a receptionist is work that exists
        and that no load bar will ever show. This keeps the common mistake out of
        the column. `by_id` already filters `deleted_at IS NULL`, so a retired
        staffer and an unknown id are one refusal.

        It RETURNS the row rather than only refusing, so F42's capacity write can
        take its audit `from` off the statement this already ran. The three
        shipped callers ignore the value and the refusal is byte-identical; a
        second `by_id` on the capacity path would be a second statement saying
        what this one just read.
        """
        staff = await self._staff.by_id(session, tenant_id, staff_user_id)
        if staff is None or staff.role != StaffRole.SEAMSTRESS.value:
            raise AtelierValidationError("staff_user_id must be a live seamstress")
        return staff

    async def _resolve_dress_name(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        dress_id: UUID | None,
        dress_name: str | None,
    ) -> str | None:
        """0008's snapshot, and the SERVER copies it. When `dress_id` is null the
        client's free text stands on its own — an alteration is frequently on a
        gown the bride already owns, which has no catalog row at all."""
        if dress_id is None:
            return dress_name
        dress = await self._dresses.by_id(session, tenant_id, dress_id)
        if dress is None:
            raise DomainNotFoundError("dress")
        return dress.name

    async def _resolve_customer(
        self, session: AsyncSession, tenant_id: UUID, *, phone: str, name: str
    ) -> tuple[Customer, bool]:
        """⚠ A SAVEPOINT, NOT A RETRY OF THE WHOLE REQUEST.

        F41 is the first caller of `upsert` that holds no advisory lock, and that
        method's own docstring says the lock is why it is safe. `upsert` is
        read-then-insert: two intakes for one brand-new phone interleave into two
        INSERTs and the second hits `idx_customers_tenant_phone_unique`, raising
        an `IntegrityError` inside an open transaction — which in Postgres aborts
        the WHOLE transaction, so without `begin_nested()` the re-read below
        raises `PendingRollbackError` instead of running and the intake 500s with
        the ticket lost.

        The partial unique index is what makes this correct: the loser's INSERT
        is refused, the savepoint rolls back to the instant before it, and
        `by_phone` then finds the winner's committed row.

        Declined: a per-tenant advisory lock — one line instead of five, but it
        serialises every atelier intake in the boutique against every other to
        protect a collision that exists only for a phone the tenant has never
        seen. Declined: rewriting `upsert` as `INSERT … ON CONFLICT` — it is
        shipped with three other callers on the booking path, and that puts the
        booking flow's regression risk inside an atelier PR.

        ⚠ THE SECOND RETURN VALUE IS "THIS INTAKE RENAMED A LIVE CUSTOMER", and
        it costs the one extra `by_phone` above the savepoint. `upsert` holds the
        answer already but cannot say so without a return-type change across
        forty-odd call sites on the booking path, which is the regression risk
        the paragraph above already declined once. The read is one hit on
        `idx_customers_tenant_phone_unique` on a counter action, not on the board
        poll. It also moves the race test's seam by one call — see that test.
        """
        existing = await self._customers.by_phone(session, tenant_id, phone=phone)
        renamed = existing is not None and existing.name != name
        try:
            async with session.begin_nested():
                customer = await self._customers.upsert(session, tenant_id, phone=phone, name=name)
        except IntegrityError:
            customer_or_none = await self._customers.by_phone(session, tenant_id, phone=phone)
            if customer_or_none is None:
                # NOT the unique index. Swallowing a different constraint here
                # would present as a silent, WRONG customer link.
                raise
            # The winner committed in the gap, so this intake wrote no name at
            # all — it ATTACHED to hers. Nothing was renamed.
            return customer_or_none, False
        return customer, renamed

    async def _respond(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        row: AlterationTicket,
        *,
        today: datetime.date,
    ) -> AtelierTicket:
        """Every mutation answers the FULL ticket, so the console patches its
        card from the server's own row and cannot disagree with itself."""
        customer = await self._customers.by_id(session, tenant_id, row.customer_id)
        return AtelierTicket.from_row(
            row, customer_name=customer.name if customer is not None else "", today=today
        )

    @staticmethod
    def _validate_ticket_fields(
        *,
        due_date: datetime.date,
        dress_id: UUID | None,
        dress_name: str | None,
        dress_size: str | None,
        notes: str | None,
        today: datetime.date,
    ) -> None:
        """⚠ THE DUE-DATE BOUNDS ARE ASYMMETRIC AND THE ASYMMETRY IS THE POINT.

        NO LOWER BOUND WHATSOEVER: a past `due_date` is accepted on create and on
        update, 200, with no warning field — a dress that was due yesterday is
        exactly the ticket a boutique most needs to open, and the past-date
        warning is a client affordance only. The upper bound is a TYPO FENCE, not
        a policy: `DATE` accepts year 9999 and one mistyped year poisons the
        board's sort and every capacity number F42 derives from it.
        """
        if due_date > today + datetime.timedelta(days=MAX_DUE_DATE_HORIZON_DAYS):
            raise AtelierValidationError("due_date is too far in the future")
        if dress_id is not None and dress_name is not None:
            # The server overwrites it with the catalog's own name, so accepting
            # it would silently discard what the caller typed.
            raise AtelierValidationError("dress_name is not allowed with dress_id")
        _bounded(dress_name, MAX_DRESS_LABEL_LENGTH, "dress_name")
        _bounded(dress_size, MAX_DRESS_SIZE_LENGTH, "dress_size")
        if notes is not None:
            if len(notes) > MAX_TICKET_NOTES_LENGTH:
                raise AtelierValidationError("notes is too long")
            # Notes KEEP newlines and tabs — it is a paragraph. Every label bars
            # the whole C0 set, because a line break in a value that reaches an
            # SMS template is header-injection material.
            if CONTROL_CHARS_EXCEPT_WS.search(notes):
                raise AtelierValidationError("notes contains invalid characters")


def _bounded(value: str | None, limit: int, field: str) -> None:
    if value is None:
        return
    if len(value) > limit:
        raise AtelierValidationError(f"{field} is too long")
    if CONTROL_CHARS.search(value):
        raise AtelierValidationError(f"{field} contains invalid characters")


def _cleared_through(row: AlterationTicket, stage: TicketStage) -> bool:
    """The named column is NULL **and every column after it is also NULL** — the
    only shape that makes a zero-row undo a genuine double tap rather than a
    ticket that has moved on."""
    return getattr(row, STAGE_COLUMNS[stage]) is None and all(
        getattr(row, column) is None for column in later_columns(stage)
    )


def _isoformat(value: datetime.datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _str_or_none(value: UUID | None) -> str | None:
    return str(value) if value is not None else None
