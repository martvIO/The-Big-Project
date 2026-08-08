from datetime import datetime
from uuid import UUID

from sqlalchemy import Row, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.booking import Booking
from app.models.constants import MessageKind, MessageStatus
from app.models.message_log import MessageLog

# The CRM screen's log window. No pagination and no `kind` filter, so this is a
# hard ceiling — which is exactly why `count_for_customer` ships beside it.
SMS_LOG_LIMIT = 50


def _customer_log_where(
    tenant_id: UUID, customer_id: UUID, phone: str
) -> tuple[ColumnElement[bool], ...]:
    """Attribution for a table that has no `customer_id` (D3) — the one piece of
    F53 that can be wrong in a way that discloses one customer to another.

    `message_log` has a `phone` (always written) and a `booking_id` (nullable,
    populated for lifecycle sends). So there are exactly two ways to attribute a
    row to a person, and only one of them is safe on its own.

    **`AND booking_id IS NULL` fences the phone leg, and it is the feature.**
    Phones are corrected — `CustomersRepository.set_phone` exists precisely for
    the bride who gave a wrong number — and phones are recycled by carriers.
    A row that carries a `booking_id` belongs to that booking's customer, full
    stop: `bookings.customer_id` is authoritative and survives both correction
    branches. A row without one is an OTP or another non-lifecycle send, and for
    those the phone at send time is the only identity that exists. Drop the
    fence and the phone leg re-admits every lifecycle row the booking leg
    already attributed correctly — which is exactly the set that can belong to
    the previous holder of the number, whose confirmation body carries her name
    and her appointment time.

    The residual is named rather than assumed away: a masked OTP row written
    before a recycle still surfaces, because it has no `booking_id` and its
    phone genuinely was that number. Closing it needs `message_log.customer_id`
    at write time plus a backfill that cannot be correct for historical rows.

    **`or_`, not UNION.** A lifecycle SMS to the customer's CURRENT phone matches
    both legs: `UNION ALL` renders it twice, `UNION` sorts the whole result to
    dedupe. `or_` needs neither.

    **`MessageLog.tenant_id` stays explicit.** This is the only query in the
    feature keyed on a phone rather than a customer id, on the one column
    0008_bookings.py designs a collision into — the same phone under two tenants
    is two customers, deliberately. RLS is not a substitute: `core/config.py`
    falls back to a superuser connection whenever `DATABASE_URL` is unset, and a
    superuser bypasses FORCE RLS (`app/db/session.py::ensure_safe_database_role`).
    """
    booking_ids = select(Booking.id).where(
        Booking.tenant_id == tenant_id,
        Booking.customer_id == customer_id,
        Booking.deleted_at.is_(None),
    )
    return (
        MessageLog.tenant_id == tenant_id,
        MessageLog.deleted_at.is_(None),
        or_(
            MessageLog.booking_id.in_(booking_ids),
            and_(MessageLog.phone == phone, MessageLog.booking_id.is_(None)),
        ),
    )


# The bell's window (F24 D6). No pagination: `message_log` is retained 24 months
# and a boutique sends a handful of lifecycle messages per booking, so twenty
# rows is several appointments deep — and the badge caps at «9+» regardless.
BELL_LIMIT = 20


class MessageLogRepository:
    """Tenant-scoped via RLS; the explicit tenant_id predicate is redundant
    defense-in-depth (house pattern — see StaffUsersRepository)."""

    async def insert(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        phone: str,
        kind: str,
        body: str,
        booking_id: UUID | None = None,
    ) -> MessageLog:
        row = MessageLog(
            tenant_id=tenant_id,
            phone=phone,
            kind=kind,
            body=body,
            booking_id=booking_id,
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    async def update_status(
        self,
        session: AsyncSession,
        tenant_id: UUID,
        log_id: UUID,
        *,
        status: str,
        provider_message_id: str | None = None,
        error: str | None = None,
    ) -> MessageLog | None:
        row = await self._by_id(session, tenant_id, log_id)
        if row is None:
            return None
        row.status = status
        row.provider_message_id = provider_message_id
        row.error = error
        await session.flush()
        await session.refresh(row)
        return row

    async def list_by_phone(
        self, session: AsyncSession, tenant_id: UUID, *, phone: str
    ) -> list[MessageLog]:
        stmt = (
            select(MessageLog)
            .where(
                MessageLog.tenant_id == tenant_id,
                MessageLog.phone == phone,
                MessageLog.deleted_at.is_(None),
            )
            .order_by(MessageLog.created_at)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def list_for_customer(
        self, session: AsyncSession, tenant_id: UUID, customer_id: UUID, *, phone: str
    ) -> list[MessageLog]:
        """The CRM screen's log panel, newest first — which is why F53 cannot
        reuse `list_by_phone` above and appends its own.

        The `id` tiebreak is not decoration: `created_at` is `server_default
        now()`, and Postgres `now()` is `transaction_timestamp()`, constant for
        every row written inside one transaction. Without it, "newest first"
        over rows sharing an instant is a coin flip.
        """
        stmt = (
            select(MessageLog)
            .where(*_customer_log_where(tenant_id, customer_id, phone))
            .order_by(MessageLog.created_at.desc(), MessageLog.id.desc())
            .limit(SMS_LOG_LIMIT)
        )
        return list((await session.execute(stmt)).scalars().all())

    async def count_for_customer(
        self, session: AsyncSession, tenant_id: UUID, customer_id: UUID, *, phone: str
    ) -> int:
        """The number beside the window. OTP rows are written by an anonymous
        endpoint, never carry a `booking_id`, and are always the newest — so
        fifty of them evict every confirmation and reminder from the view,
        permanently. Without this count the screen would answer "how many
        messages did you send this person" with "fifty"."""
        stmt = (
            select(func.count())
            .select_from(MessageLog)
            .where(*_customer_log_where(tenant_id, customer_id, phone))
        )
        return (await session.execute(stmt)).scalar_one()

    async def list_bell_for_customer(
        self, session: AsyncSession, tenant_id: UUID, customer_id: UUID
    ) -> list[Row[tuple[UUID, str, datetime, UUID | None, datetime, str]]]:
        """The bell projection (F24 D6): what the boutique actually TOLD her.

        **`body` is not in the SELECT, and that is the strongest available form
        of the rule** — a later author cannot forget to strip it from a shape
        that never carried it. Bodies store masked OTP codes and send-time
        Hebrew; the client renders from `kind` plus these facts.

        **`status = 'sent'` only.** A failed send never reached her, and the
        bell mirrors her INBOX, not our attempts — showing a failure here would
        have the boutique claiming to have told her something it did not.

        **`kind != 'otp'`** because a login code is not news about an
        appointment, and because those are the rows whose bodies are masked.

        **Attribution is the BOOKING JOIN alone**, never the phone: this is the
        `_customer_log_where` fence above taken to its conclusion. A row without
        a `booking_id` cannot be attributed to a person safely (phones are
        corrected and recycled), and every kind the bell renders carries one.

        The `id` tiebreak is the `list_for_customer` sentence verbatim:
        `created_at` is `now()` = `transaction_timestamp()`, constant for rows
        written in one transaction, so "newest first" over a tie is otherwise a
        coin flip — and under a LIMIT a tie decides which row is DROPPED.
        """
        stmt = (
            select(
                MessageLog.id,
                MessageLog.kind,
                MessageLog.created_at,
                MessageLog.booking_id,
                Booking.starts_at,
                Booking.appointment_type_name,
            )
            .join(Booking, Booking.id == MessageLog.booking_id)
            .where(
                MessageLog.tenant_id == tenant_id,
                MessageLog.deleted_at.is_(None),
                MessageLog.kind != MessageKind.OTP.value,
                MessageLog.status == MessageStatus.SENT.value,
                Booking.tenant_id == tenant_id,
                Booking.customer_id == customer_id,
                Booking.deleted_at.is_(None),
            )
            .order_by(MessageLog.created_at.desc(), MessageLog.id.desc())
            .limit(BELL_LIMIT)
        )
        return list((await session.execute(stmt)).all())

    async def _by_id(
        self, session: AsyncSession, tenant_id: UUID, log_id: UUID
    ) -> MessageLog | None:
        stmt = select(MessageLog).where(
            MessageLog.tenant_id == tenant_id,
            MessageLog.id == log_id,
            MessageLog.deleted_at.is_(None),
        )
        return (await session.execute(stmt)).scalar_one_or_none()
