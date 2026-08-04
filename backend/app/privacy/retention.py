"""The per-data-class retention job (F20 D7/D8/D9).

A REGISTRY of policies rather than one sweeper per class, because the brief
requires reusable machinery and three future consumers are already named: F38's
ex-staff scrub, and F53's notes/tags, which inherit the customer classes.

Two actions, both with a live consumer here so neither ships as speculative code:

  * PURGE — hard DELETE, for classes where the row IS the personal data.
  * SCRUB — UPDATE blanking the personal columns, row retained, for classes that
    are business or operational records CONTAINING personal data. The epic's own
    words: "anonymize in place — soft-delete is not erasure".

**Every policy's predicate must be falsified by its own action** (D22). A DELETE
falsifies itself by construction; a SCRUB does not, and the first draft's
`customers` feed ("orphaned and older than 30 days", with no `erased_at IS NULL`)
re-scrubbed its own output on every tick — overwriting `erased_at`, which for a
subject whose bookings have since been purged is the only PROOF of her erasure;
burning all 50 chunks on rows already done; and, under a stable ordering, never
reaching the rows queued behind them, so the policy stopped working at exactly
the point it had enough work to matter. Both SCRUBs here therefore carry a
predicate their own UPDATE destroys, and `test_retention_db.py` asserts it as a
loop over POLICIES so the next author inherits the guard rather than the lesson.

**The runner owns the chunk loop**, so no policy repeats it, and every policy
runs inside that tenant's `tenant_session`: `scheduled_messages` was not allowed
to be this codebase's first RLS exception (F16 D6), and a job that hard-deletes
is emphatically not going to be either.
"""

import dataclasses
import datetime
import enum
import logging
from collections.abc import Callable, Sequence
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import ColumnElement, Text, cast, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.models.constants import AuditAction
from app.models.customer import Customer
from app.models.message_log import MessageLog
from app.models.otp_code import OtpCode
from app.models.queue_ticket import QueueTicket
from app.models.scheduled_message import ScheduledMessage
from app.models.session import Session as SessionRow
from app.privacy.validation import ERASED_NAME, ERASED_PHONE_PREFIX

logger = logging.getLogger("app")

# Verbatim from `app/booking/backfill.py:36-38`: one page per transaction, and a
# hard ceiling so a runaway cannot loop forever. 500 x 50 is two orders of
# magnitude past the pilot's whole book.
CHUNK_SIZE = 500
MAX_CHUNKS = 50


class RetentionAction(enum.StrEnum):
    PURGE = "purge"
    SCRUB = "scrub"


class PolicyRun(Protocol):
    async def __call__(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        now: datetime.datetime,
        settings: Settings,
        limit: int,
        dry_run: bool,
    ) -> int: ...


@dataclasses.dataclass(frozen=True)
class RetentionPolicy:
    #: Audit suffix. `audit_action()` resolves it through `AuditAction`.
    name: str
    action: RetentionAction
    #: What the SQL actually touches. NOT decoration and not a synonym for
    #: `name`: the runner writes it into the audit row, and
    #: `test_retention_policies.py` walks it to prove no policy names a table
    #: whose DELETE the app role does not hold. Asserting on `name` would make
    #: that a spelling check.
    tables: tuple[str, ...]
    run: PolicyRun


def audit_action(policy: RetentionPolicy) -> AuditAction:
    """A policy with no `AuditAction` member raises here rather than writing an
    unregistered action string into the trail."""
    return AuditAction(f"retention_{policy.name}")


def _cutoff(now: datetime.datetime, seconds: int) -> datetime.datetime:
    return now - datetime.timedelta(seconds=seconds)


async def _count(
    session: AsyncSession, model: type[Any], where: Sequence[ColumnElement[bool]]
) -> int:
    """The dry-run arm. Deliberately UNLIMITED, unlike its writing twin: a
    dry-run consumes no rows, so a chunk loop over a counting statement would
    return the same page 50 times. The runner therefore calls a dry-run policy
    exactly once and reports the true total an armed run would work through."""
    stmt = select(func.count()).select_from(model).where(*where)
    return int((await session.execute(stmt)).scalar_one())


def _page(model: type[Any], where: Sequence[ColumnElement[bool]], *, limit: int) -> Any:
    """The LIMIT lives in SQL, never in a Python slice over an unbounded read —
    the point of chunking is that the DATABASE never materialises more than a
    page, and a slice would make the ceiling decorative."""
    return select(model.id).where(*where).order_by(model.id).limit(limit)


async def _purge(
    session: AsyncSession,
    model: type[Any],
    where: Sequence[ColumnElement[bool]],
    *,
    limit: int,
    dry_run: bool,
) -> int:
    if dry_run:
        return await _count(session, model, where)
    stmt = (
        delete(model)
        .where(model.id.in_(_page(model, where, limit=limit)))
        # RETURNING rather than rowcount: the async Result is typed without one
        # (the ScheduledMessagesRepository.cancel_pending precedent).
        .returning(model.id)
    )
    return len((await session.execute(stmt)).scalars().all())


async def _scrub(
    session: AsyncSession,
    model: type[Any],
    where: Sequence[ColumnElement[bool]],
    values: dict[str, Any],
    *,
    limit: int,
    dry_run: bool,
) -> int:
    if dry_run:
        return await _count(session, model, where)
    stmt = (
        update(model)
        .where(model.id.in_(_page(model, where, limit=limit)))
        .values(**values)
        .returning(model.id)
    )
    return len((await session.execute(stmt)).scalars().all())


def _erased_phone(model: type[Any]) -> ColumnElement[str]:
    """`erased:{id}`, computed PER ROW in SQL.

    A constant placeholder passes every single-row test and then fails in
    production the first time a chunk carries two rows:
    `idx_customers_tenant_phone_unique` refuses the second, the whole chunk
    transaction rolls back, and that failure repeats on every tick for every
    tenant past the clock, permanently. The same form is used on
    `queue_tickets`, which has no such index, so that one `erased:` convention
    holds across both scrubs and `send_sms`' refusal catches either.
    """
    return func.concat(ERASED_PHONE_PREFIX, cast(model.id, Text))


# --- the six classes --------------------------------------------------------


async def _purge_otp_codes(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    now: datetime.datetime,
    settings: Settings,
    limit: int,
    dry_run: bool,
) -> int:
    """15 minutes from `created_at`, which is EXACTLY the longest life anything
    on the row can have: `OTP_TTL_SECONDS + VERIFICATION_TOKEN_TTL_SECONDS`, with
    zero margin, safe only because verify refuses at `expires_at <= now`."""
    where = [
        OtpCode.tenant_id == tenant_id,
        OtpCode.created_at <= _cutoff(now, settings.retention_otp_seconds),
    ]
    return await _purge(session, OtpCode, where, limit=limit, dry_run=dry_run)


async def _purge_sessions(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    now: datetime.datetime,
    settings: Settings,
    limit: int,
    dry_run: bool,
) -> int:
    """NO new setting. `session_ttl_seconds` is already written into
    `expires_at` at mint time, so a second knob would be a second source of
    truth for one clock. A revoked (soft-deleted) session goes too — it is dead
    by definition and its `token_hash` is the only thing on the row."""
    where = [
        SessionRow.tenant_id == tenant_id,
        or_(SessionRow.expires_at <= now, SessionRow.deleted_at.is_not(None)),
    ]
    return await _purge(session, SessionRow, where, limit=limit, dry_run=dry_run)


async def _scrub_queue_tickets(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    now: datetime.datetime,
    settings: Settings,
    limit: int,
    dry_run: bool,
) -> int:
    """DR-11: F33's live public notice already promises the walk-in that her
    details go, and nothing deleted them. SCRUB and not PURGE because
    `fitting_room_assignments.queue_ticket_id` is a nullable no-FK pointer, and
    a purge leaves danglers with no way to tell "aged out" from "never existed".
    Blanking name and phone discharges «הפרטים … נמחקים» — the details are what
    the notice names, not the row.

    `name` and `phone` are both `nullable=False`, so "blank" is a PLACEHOLDER
    and never NULL — which is also what makes the predicate self-falsifying.

    **`marketing_opt_in_at` is left alone and the scrub is UNCONDITIONAL.** The
    shipped notice's second half promised to keep an opted-in bride's contact
    detail "until she asks to remove the consent" — i.e. with no clock at all,
    in a store no send path reads. Holding it forever would re-create "nothing is
    ever deleted" inside the feature that exists to end it. What she is actually
    entitled to is the ability to REVOKE, which did not exist and which F20 builds
    (the `phone` arm on marketing-withdraw); the copy drops the retention promise.
    """
    cutoff_day = _cutoff(now, settings.retention_queue_ticket_seconds).date()
    where = [
        QueueTicket.tenant_id == tenant_id,
        QueueTicket.queue_day <= cutoff_day,
        QueueTicket.name != ERASED_NAME,
    ]
    values = {"name": ERASED_NAME, "phone": _erased_phone(QueueTicket)}
    return await _scrub(session, QueueTicket, where, values, limit=limit, dry_run=dry_run)


async def _purge_message_log(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    now: datetime.datetime,
    settings: Settings,
    limit: int,
    dry_run: bool,
) -> int:
    where = [
        MessageLog.tenant_id == tenant_id,
        MessageLog.created_at <= _cutoff(now, settings.retention_message_log_seconds),
    ]
    return await _purge(session, MessageLog, where, limit=limit, dry_run=dry_run)


async def _purge_bookings(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    now: datetime.datetime,
    settings: Settings,
    limit: int,
    dry_run: bool,
) -> int:
    """Seven years from `starts_at` — the appointment, not the row's birthday.

    `scheduled_messages` for the same bookings go in the SAME batch, from the id
    set this statement already materialised. An orphan sweep over that table was
    declined: it is an anti-join per tick to reach rows the booking purge already
    knows the ids of.

    The page's LIMIT is on the id SELECT, so both DELETEs are bounded by one
    statement rather than by a Python slice over an unbounded read.
    """
    where = [
        Booking.tenant_id == tenant_id,
        Booking.starts_at <= _cutoff(now, settings.retention_bookings_seconds),
    ]
    if dry_run:
        return await _count(session, Booking, where)
    doomed = list((await session.execute(_page(Booking, where, limit=limit))).scalars().all())
    if not doomed:
        return 0
    await session.execute(
        delete(ScheduledMessage).where(
            ScheduledMessage.tenant_id == tenant_id,
            ScheduledMessage.booking_id.in_(doomed),
        )
    )
    stmt = delete(Booking).where(Booking.id.in_(doomed)).returning(Booking.id)
    return len((await session.execute(stmt)).scalars().all())


async def _scrub_customers(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    now: datetime.datetime,
    settings: Settings,
    limit: int,
    dry_run: bool,
) -> int:
    """SCRUB and not PURGE: `bookings.customer_id` is a no-FK pointer and F22,
    F33 and F53 all point at customers too, so a purged row leaves them dangling
    with no way to tell "erased" from "never existed". A scrubbed one keeps a
    resolvable id carrying no personal data — pre-decided #35's own shape for
    staff, which F38 then inherits with tests rather than writing its own.

    Three conjuncts and all three are load-bearing:
      * orphaned — no booking row points here, which only becomes true after the
        bookings policy has run, hence the registry order;
      * older than the 30-day orphan grace — NOT padding. A customer row is only
        ever created inside `create_booking`, so the sole way one is orphaned
        early is F15's phone correction re-pointing a booking at an existing
        row. Without a grace, a mistaken correction is anonymised within the
        hour and unrecoverable;
      * `erased_at IS NULL` — D22. Delete this one line and the policy re-scrubs
        its own output forever.

    `notes` and `tags` go with the name (DR-12). `customers.notes` accretes
    across a year of fittings, so an "erasure" that anonymises the name and
    leaves the paragraph about her is not an erasure.
    """
    orphan = ~select(Booking.id).where(Booking.customer_id == Customer.id).exists()
    where = [
        Customer.tenant_id == tenant_id,
        Customer.erased_at.is_(None),
        Customer.created_at <= _cutoff(now, settings.retention_orphan_customer_seconds),
        orphan,
    ]
    values: dict[str, Any] = {
        "name": ERASED_NAME,
        "phone": _erased_phone(Customer),
        "notes": None,
        "tags": [],
        "erased_at": now,
    }
    return await _scrub(session, Customer, where, values, limit=limit, dry_run=dry_run)


#: ORDER IS LOAD-BEARING — `bookings` before `customers`, asserted on the tuple
#: in `test_retention_policies.py` rather than left to this comment.
POLICIES: tuple[RetentionPolicy, ...] = (
    RetentionPolicy("otp_codes", RetentionAction.PURGE, ("otp_codes",), _purge_otp_codes),
    RetentionPolicy("sessions", RetentionAction.PURGE, ("sessions",), _purge_sessions),
    RetentionPolicy(
        "queue_tickets", RetentionAction.SCRUB, ("queue_tickets",), _scrub_queue_tickets
    ),
    RetentionPolicy("message_log", RetentionAction.PURGE, ("message_log",), _purge_message_log),
    RetentionPolicy(
        "bookings", RetentionAction.PURGE, ("bookings", "scheduled_messages"), _purge_bookings
    ),
    RetentionPolicy("customers", RetentionAction.SCRUB, ("customers",), _scrub_customers),
)


@dataclasses.dataclass(frozen=True)
class RetentionResult:
    tenants: int = 0
    #: Tenants whose run raised and was skipped. Surfaced rather than swallowed:
    #: a silently degraded retention job still reports "ran fine" to the only
    #: operator who would ever look.
    failed_tenants: int = 0
    #: Rows touched, per policy name, summed across tenants.
    rows: dict[str, int] = dataclasses.field(default_factory=dict)


class RetentionRunner:
    """Owns the tenant loop, the chunk loop and the audit trail, so no policy
    repeats any of them.

    `tenants` and `policies` are injectable because the loop's containment
    properties — a short page ends the drain, MAX_CHUNKS bounds it, one tenant's
    failure never reaches another, a dry run writes nothing — are true before any
    row exists and should not need a database to assert. Production never passes
    either.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        settings: Settings,
        clock: Callable[[], datetime.datetime] | None = None,
        tenants: TenantsRepository | None = None,
        policies: tuple[RetentionPolicy, ...] = POLICIES,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._clock = clock
        # list_all(), NEVER list_active() — D21. See TenantsRepository.list_all.
        self._tenants = tenants or TenantsRepository(session_factory)
        self._policies = policies
        self._audit = AuditLogRepository()

    def _now(self) -> datetime.datetime:
        now = self._clock() if self._clock is not None else datetime.datetime.now(datetime.UTC)
        return now.astimezone(datetime.UTC)

    async def run(self, *, dry_run: bool = False) -> RetentionResult:
        now = self._now()
        tenants = await self._tenants.list_all()
        rows: dict[str, int] = {}
        failed = 0
        for tenant in tenants:
            try:
                touched = await self._run_for_tenant(tenant.id, now=now, dry_run=dry_run)
            except Exception:
                # One tenant's failure is logged and skipped, never allowed to
                # stop the others — `poll_once`'s rule with higher stakes: the
                # clock the other boutiques are on is a legal duty, and nothing
                # else in the system would notice it had stopped.
                logger.exception("retention failed for tenant %s", tenant.id)
                failed += 1
                continue
            for name, count in touched.items():
                rows[name] = rows.get(name, 0) + count
        return RetentionResult(tenants=len(tenants), failed_tenants=failed, rows=rows)

    async def _run_for_tenant(
        self, tenant_id: UUID, *, now: datetime.datetime, dry_run: bool
    ) -> dict[str, int]:
        touched: dict[str, int] = {}
        for policy in self._policies:
            count = await self._drain(policy, tenant_id, now=now, dry_run=dry_run)
            if not count:
                # A RUN THAT TOUCHED NOTHING WRITES NO ROW. Six rows per tenant
                # per hour of "deleted 0" is permanent bloat in the one table
                # with no retention class of its own.
                continue
            touched[policy.name] = count
            if not dry_run:
                await self._record(policy, tenant_id, count)
        return touched

    async def _drain(
        self, policy: RetentionPolicy, tenant_id: UUID, *, now: datetime.datetime, dry_run: bool
    ) -> int:
        """One page per transaction (`backfill.py`'s shape), inside that tenant's
        `tenant_session`: `scheduled_messages` was not allowed to be this
        codebase's first RLS exception, and a job that hard-deletes is not going
        to be either.

        A dry run is NOT looped. It consumes no rows, so a chunk loop over a
        counting statement would report the same page MAX_CHUNKS times.
        """
        if dry_run:
            async with tenant_session(self._session_factory, tenant_id) as session:
                return await self._call(policy, session, tenant_id, now=now, dry_run=True)
        total = 0
        for _ in range(MAX_CHUNKS):
            async with tenant_session(self._session_factory, tenant_id) as session:
                count = await self._call(policy, session, tenant_id, now=now, dry_run=False)
            total += count
            if count < CHUNK_SIZE:
                return total
        logger.warning(
            "retention: tenant %s policy %s hit MAX_CHUNKS — the next tick continues it",
            tenant_id,
            policy.name,
        )
        return total

    async def _call(
        self,
        policy: RetentionPolicy,
        session: AsyncSession,
        tenant_id: UUID,
        *,
        now: datetime.datetime,
        dry_run: bool,
    ) -> int:
        return await policy.run(
            session,
            tenant_id,
            now=now,
            settings=self._settings,
            limit=CHUNK_SIZE,
            dry_run=dry_run,
        )

    async def _record(self, policy: RetentionPolicy, tenant_id: UUID, count: int) -> None:
        """The tenant's own evidence that its clock ran, in its own transaction.

        The trade-off, stated: a crash between the last chunk's commit and this
        insert loses the row for work that did happen. The alternative — writing
        it inside every chunk transaction — is up to MAX_CHUNKS rows per policy
        per tick, in the table that has no retention class to reclaim them.

        `details` carries counts and table NAMES only. Never a name, never a
        phone: `audit_log` has no retention policy and platform operators read
        across tenants.
        """
        async with tenant_session(self._session_factory, tenant_id) as session:
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=audit_action(policy),
                entity=policy.tables[0],
                details={
                    "rows": count,
                    "action": policy.action.value,
                    "tables": list(policy.tables),
                },
            )
