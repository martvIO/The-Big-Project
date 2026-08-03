"""The customer CRM's orchestration: one search, one detail builder, one write.

**No clock.** Nothing here is time-derived — the booking history is ordered by
`starts_at` and has no window, and the log has no band.

**No advisory lock (D7), and that is a ruling rather than an omission.** F51's
`staff.py` opens with one because its invariant is *at least one live owner*,
which no index can express and which a `count(*)` subquery cannot enforce under
READ COMMITTED. F53 has no invariant of that shape: a notes/tags edit is a
single-row UPDATE, and two staff editing one bride's card inside one save cycle
is last-write-wins — the answer every text field in this product already gives.
An `updated_at` precondition was declined with it: it turns a rare recoverable
overwrite into a frequent confusing 409 on a field where the loser can retype.

**ONE `_build_detail`, and both the read path and the write path go through
it.** The console does `setDetail(updated)` unconditionally, so a PATCH that
answered `bookings: []` / `messages: []` would blank both panels the instant the
owner pressed «שמירה» — until she navigated away and back. It is the same rule
`BookingsSection.tsx` states for the row, *"the row is patched from the
response, so the two views cannot disagree — same object"*, and it only holds if
the response really is the same object.

**One `tenant_session` per request**, so `session.begin()` makes the whole
handler body one transaction: one connection, one RLS binding for all three
reads, and one atomic unit on the write path.

⚠ It does NOT buy a stable read view, and the claim that it does — which the
spec and the plan both still make — is false against this code. `get_engine()`
sets no `isolation_level` and `tenant_session` issues no SET TRANSACTION
ISOLATION LEVEL, so Postgres runs READ COMMITTED, where every statement takes a
FRESH snapshot. A booking created between the customer read and the message read
therefore CAN still produce a log row whose `booking_id` matches nothing in the
history panel beside it. Cross-panel consistency here is best-effort, and the
panels are read-only evidence, so a one-refresh skew is a cosmetic race rather
than a correctness bug.

Raising the isolation level would fix it and is deliberately NOT done here: it is
a repo-wide behaviour change (every caller of `get_engine()` inherits it, and
REPEATABLE READ turns concurrent writes into serialization failures the handlers
do not retry) and must not ride in on this feature. Anyone adding a field to
`SmsLogRow` that has to agree with the booking panel needs to read this
paragraph, not the sentence it replaced.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.service import StaffContext
from app.customers.schemas import (
    CustomerBookingRow,
    CustomerDetail,
    CustomerListResponse,
    CustomerRow,
    SmsLogRow,
)
from app.customers.validation import (
    BOOKING_HISTORY_LIMIT,
    CUSTOMER_LIST_MAX_LIMIT,
    MAX_LIST_OFFSET,
    normalize_tags,
    validate_notes,
)
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.message_log import MessageLogRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.models.constants import AuditAction
from app.models.customer import Customer


class CustomerNotFoundError(DomainNotFoundError):
    """Unknown, soft-deleted, or another tenant's customer id — one
    indistinguishable miss. RLS and the repository's redundant tenant predicate
    are what make the foreign case identical to the missing one, by design.
    Subclasses the app/errors.py base, so it needs no handler of its own."""


class CustomersService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._customers = CustomersRepository()
        self._bookings = BookingsRepository()
        self._messages = MessageLogRepository()
        self._audit = AuditLogRepository()

    async def list_customers(
        self, tenant_id: uuid.UUID, *, q: str | None, offset: int, limit: int
    ) -> CustomerListResponse:
        """Clamped a second time BELOW the router's own Query bounds, the
        `booking/owner.py:179-180` shape: a non-router caller passing an
        unbounded offset would otherwise die in asyncpg's int8_encode as a 500.

        `total` runs the SAME predicate as the page — the repository shares one
        `_search_where` between them, so the two cannot drift.
        """
        safe_offset = min(max(offset, 0), MAX_LIST_OFFSET)
        safe_limit = min(max(limit, 1), CUSTOMER_LIST_MAX_LIMIT)
        async with tenant_session(self._session_factory, tenant_id) as session:
            rows = await self._customers.search(
                session, tenant_id, q=q, offset=safe_offset, limit=safe_limit
            )
            total = await self._customers.count_search(session, tenant_id, q=q)
        return CustomerListResponse(
            items=[
                CustomerRow(id=row.id, name=row.name, phone=row.phone, tags=list(row.tags))
                for row in rows
            ],
            total=total,
            offset=safe_offset,
            limit=safe_limit,
        )

    async def detail(self, tenant_id: uuid.UUID, customer_id: uuid.UUID) -> CustomerDetail:
        async with tenant_session(self._session_factory, tenant_id) as session:
            customer = await self._customers.by_id(session, tenant_id, customer_id)
            built = None if customer is None else await self._build_detail(session, customer)
        # OUTSIDE the `async with`, the `booking/owner.py:191-199` shape: the
        # transaction closes cleanly and the handler-facing raise is not tangled
        # in the context manager's exit.
        if built is None:
            raise CustomerNotFoundError
        return built

    async def update(
        self,
        tenant_id: uuid.UUID,
        customer_id: uuid.UUID,
        *,
        notes: str | None,
        tags: list[str] | None,
        actor: StaffContext,
    ) -> CustomerDetail:
        """`None` means NOT SUPPLIED on both fields; `""` and `[]` are values
        that clear.

        Validation runs FIRST, outside the session — a refused tag must not
        cost a connection, and a `CustomerValidationError` is a
        `DomainValidationError`, so the app-wide handler answers the 400.
        """
        if notes is not None:
            validate_notes(notes)
        normalized = None if tags is None else normalize_tags(tags)

        async with tenant_session(self._session_factory, tenant_id) as session:
            current = await self._customers.by_id(session, tenant_id, customer_id)
            if current is None:
                built = None
            else:
                # Normalized BEFORE the diff, so re-saving an unedited chip list
                # is a no-op rather than a write plus an audit row claiming
                # something changed.
                changed = sorted(_moved(current, notes=notes, tags=normalized))
                if changed:
                    await self._customers.set_notes_and_tags(
                        session,
                        tenant_id,
                        customer_id,
                        notes=notes if "notes" in changed else None,
                        tags=normalized if "tags" in changed else None,
                    )
                    # FIELD NAMES ONLY (D8) — no from, no to, no note text, no
                    # tag string, no name and no phone. `audit_log` has no
                    # retention policy and platform operators read across
                    # tenants, so a bride's free text written there would leave
                    # the tenant that owns it.
                    await self._audit.record(
                        session,
                        tenant_id=tenant_id,
                        action=AuditAction.CUSTOMER_UPDATED,
                        actor_id=actor.id,
                        entity=str(customer_id),
                        details={"fields": changed},
                    )
                built = await self._build_detail(session, current)
        if built is None:
            raise CustomerNotFoundError
        return built

    async def _build_detail(self, session: AsyncSession, customer: Customer) -> CustomerDetail:
        """The one place `CustomerDetail` is assembled. `customer` is passed in
        rather than re-read by id because the write path already holds the row
        the UPDATE synchronized — a second read would be a second statement
        answering the same question."""
        bookings = await self._bookings.list_recent_for_customer(
            session, customer.tenant_id, customer_id=customer.id, limit=BOOKING_HISTORY_LIMIT
        )
        messages = await self._messages.list_for_customer(
            session, customer.tenant_id, customer.id, phone=customer.phone
        )
        messages_total = await self._messages.count_for_customer(
            session, customer.tenant_id, customer.id, phone=customer.phone
        )
        return CustomerDetail(
            id=customer.id,
            name=customer.name,
            phone=customer.phone,
            notes=customer.notes,
            tags=list(customer.tags),
            bookings=[
                CustomerBookingRow(
                    id=row.id,
                    starts_at=row.starts_at,
                    status=row.status,
                    appointment_type_name=row.appointment_type_name,
                )
                for row in bookings
            ],
            messages=[
                SmsLogRow(
                    id=row.id,
                    created_at=row.created_at,
                    kind=row.kind,
                    status=row.status,
                    body=row.body,
                )
                for row in messages
            ],
            messages_total=messages_total,
        )


def _moved(customer: Customer, *, notes: str | None, tags: list[str] | None) -> set[str]:
    """Which SUPPLIED field differs from what is stored. An unsupplied field is
    never compared, so a tags-only patch cannot touch notes."""
    changed: set[str] = set()
    if notes is not None and notes != customer.notes:
        changed.add("notes")
    if tags is not None and tags != list(customer.tags):
        changed.add("tags")
    return changed
