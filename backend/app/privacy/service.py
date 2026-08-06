"""The privacy surface's orchestration: the settings write and the three
subject actions.

**`GET /manage/privacy` is not here, and that is D13.** The tenant context
already carries `settings` on every request (`tenancy/resolver.py:7-20`, no
cache), so resolving the documents is a pure function over data the middleware
has already read. Routing it through a service would buy a round trip and a
fake, for nothing.

**Statements are written here rather than in a repository**, following
`app/privacy/retention.py`'s precedent in this same package: the erase's six
steps are one transaction whose ORDER is the design, and spreading them across
six repository methods would let a later author reorder them without noticing
that step 4 depends on the phone step 2 has already destroyed. The two consent
statements a second feature also issues (`record_marketing_consent`,
`withdraw_marketing_consent`) DO live on `CustomersRepository`, because
`create_booking` is their other caller.

**Every write runs inside `tenant_session`**, so RLS is bound for the whole
transaction. A job that hard-deletes was not going to be this codebase's first
RLS exception, and neither is a route that erases a person.
"""

import uuid
from typing import Any

from sqlalchemy import case, delete, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.queue_tickets import QueueTicketsRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError, DomainValidationError
from app.models.appointment_type import AppointmentType
from app.models.booking import Booking
from app.models.constants import AuditAction, BookingStatus, WaitlistEntryStatus
from app.models.customer import Customer
from app.models.message_log import MessageLog
from app.models.otp_code import OtpCode
from app.models.queue_ticket import QueueTicket
from app.models.scheduled_message import ScheduledMessage
from app.models.terms_version import TermsVersion
from app.models.waitlist_entry import WaitlistEntry
from app.notifications.validation import normalize_israeli_mobile
from app.privacy.schemas import (
    ExportedBooking,
    ExportedMessage,
    ExportedQueueTicket,
    ExportedSubject,
    ExportedTerms,
    ExportedWaitlistEntry,
    MarketingWithdrawResponse,
    PrivacyResponse,
    SubjectEraseResponse,
    SubjectExportResponse,
)
from app.privacy.text import (
    PLATFORM_DISCLAIMER_HE,
    PLATFORM_ERASE_REASON_HINT_HE,
    ResolvedPrivacy,
    resolve_privacy,
)
from app.privacy.validation import (
    ERASED_NAME,
    ERASED_PHONE_PREFIX,
    PrivacyThrottledError,
    validate_erase_reason,
    validate_privacy_text,
)


class SubjectNotFoundError(DomainNotFoundError):
    """No live customer for this tenant by that phone (export) or that id
    (erase). Indistinguishable from another tenant's row by design — RLS and the
    explicit tenant predicate make the foreign case identical to the missing
    one."""


class SubjectHasActiveBookingError(Exception):
    """She holds a `confirmed` booking that has not started yet. main.py maps it
    to a 409 telling the owner to cancel or complete it first.

    The erasure duty yields to performing the contract she is still party to:
    silently erasing a bride with a fitting on Thursday would break the
    appointment and the SMS link at once, and «נמחק» is not what she asked for
    when she is still expecting to be let in the door.
    """


def privacy_response(resolved: ResolvedPrivacy) -> PrivacyResponse:
    """The ONE projection, shared by the GET and the PUT, so the two cannot
    disagree about what a save produced. The console does `setForm(response)`
    unconditionally."""
    return PrivacyResponse(
        notice_text=resolved.notice_text,
        notice_is_default=resolved.notice_is_default,
        dpa_text=resolved.dpa_text,
        dpa_is_default=resolved.dpa_is_default,
        subprocessors_text=resolved.subprocessors_text,
        disclaimer_text=PLATFORM_DISCLAIMER_HE,
        erase_reason_hint=PLATFORM_ERASE_REASON_HINT_HE,
    )


def _last4(phone: str | None) -> str | None:
    """The most of a number that may be written down — `booking/owner.py:93-96`,
    adopted verbatim.

    `audit_log` is exempt from every retention class FOREVER, so a full phone
    written there is a permanent copy of the one identifier the erase exists to
    destroy, in the one table designed never to be erased. Four digits plus a
    `customer_id` answers an Amendment-13 complaint and is not a phone book.
    """
    return phone[-4:] if phone else None


class PrivacyService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        export_limiter: FixedWindowRateLimiter,
        erase_limiter: FixedWindowRateLimiter,
        withdraw_limiter: FixedWindowRateLimiter,
    ) -> None:
        self._session_factory = session_factory
        self._tenants = TenantsRepository(session_factory)
        self._customers = CustomersRepository()
        self._queue_tickets = QueueTicketsRepository()
        self._audit = AuditLogRepository()
        # THREE INSTANCES, never one limiter with three keys: `max_attempts` is
        # per instance, so a shared one would give all three routes a single
        # ceiling and let an owner's morning of lookups lock out the erase she
        # is working towards.
        self._export_limiter = export_limiter
        self._erase_limiter = erase_limiter
        self._withdraw_limiter = withdraw_limiter

    # --- the two documents ---

    async def update_privacy(
        self, tenant_id: uuid.UUID, *, notice_text: str | None, dpa_text: str | None
    ) -> PrivacyResponse:
        """A WHOLE-OBJECT replacement of `settings["privacy"]` (D16).

        `None` and `""` both mean "revert to the platform default", and both are
        stored as `""` rather than by removing the key: `||` can add or replace a
        JSONB key but never REMOVE one, so `""` is the only revert sentinel this
        statement can actually reach. `resolve_privacy` collapses it back.

        Validation runs FIRST, outside the session — a refused document must not
        cost a connection.
        """
        notice = (notice_text or "").strip()
        dpa = (dpa_text or "").strip()
        validate_privacy_text(notice, field="notice_text")
        validate_privacy_text(dpa, field="dpa_text")
        merged = await self._tenants.merge_settings(
            tenant_id, privacy={"notice_text": notice, "dpa_text": dpa}
        )
        if merged is None:
            raise SubjectNotFoundError
        return privacy_response(resolve_privacy(merged))

    # --- §13 access ---

    async def export_subject(
        self, tenant_id: uuid.UUID, *, raw_phone: str, actor: StaffContext, reason: str | None
    ) -> SubjectExportResponse:
        """Phone in, whole person out — and the `subject.id` the other two routes
        take (D17).

        The phone is normalised through the shipped `normalize_israeli_mobile`,
        so the owner may type it the way the customer says it on the telephone.
        `customers.phone` holds strict E.164 and `by_phone` is exact equality, so
        without this every `05X…` lookup would 404 a customer who demonstrably
        exists.
        """
        if reason is not None:
            validate_erase_reason(reason)
        self._spend(self._export_limiter, tenant_id)
        phone = normalize_israeli_mobile(raw_phone)
        async with tenant_session(self._session_factory, tenant_id) as session:
            customer = await self._customers.by_phone(session, tenant_id, phone=phone)
            if customer is None:
                # No audit row: nothing was accessed. Writing one here would
                # record an operator reading a subject who does not exist, which
                # is the export half of D17's fabricated-record problem.
                raise SubjectNotFoundError
            bookings = list(
                (
                    await session.execute(
                        select(Booking)
                        .where(
                            Booking.tenant_id == tenant_id,
                            Booking.customer_id == customer.id,
                            Booking.deleted_at.is_(None),
                        )
                        .order_by(Booking.starts_at)
                    )
                )
                .scalars()
                .all()
            )
            messages = list(
                (
                    await session.execute(
                        select(MessageLog)
                        .where(*_her_messages(tenant_id, customer.phone, bookings))
                        .order_by(MessageLog.created_at)
                    )
                )
                .scalars()
                .all()
            )
            # DR-9's fourth collection point. `queue_tickets.phone` is stored
            # normalised E.164 "so it matches customers.phone exactly" (the
            # column's own comment), which is what makes this reachable at all
            # for a bride who both booked online and walked in. §13 reaches it:
            # the row holds her real name and her real number.
            tickets = list(
                (
                    await session.execute(
                        select(QueueTicket)
                        .where(
                            QueueTicket.tenant_id == tenant_id,
                            QueueTicket.phone == phone,
                            QueueTicket.deleted_at.is_(None),
                        )
                        .order_by(QueueTicket.queue_day, QueueTicket.created_at)
                    )
                )
                .scalars()
                .all()
            )
            # F22's fifth collection point. `waitlist_entries.phone` is stored
            # normalised E.164 like the queue's, so the same equality reaches
            # it. The type NAME is resolved app-side (no FK, house rule) and
            # deliberately NOT filtered on deleted_at: an archived type still
            # names what she asked for.
            waitlist_rows = list(
                (
                    await session.execute(
                        select(WaitlistEntry)
                        .where(
                            WaitlistEntry.tenant_id == tenant_id,
                            WaitlistEntry.phone == phone,
                            WaitlistEntry.deleted_at.is_(None),
                        )
                        .order_by(WaitlistEntry.day, WaitlistEntry.created_at)
                    )
                )
                .scalars()
                .all()
            )
            waitlist_type_ids = {row.appointment_type_id for row in waitlist_rows}
            type_names: dict[uuid.UUID, str] = (
                {}
                if not waitlist_type_ids
                else {
                    type_id: name
                    for type_id, name in (
                        await session.execute(
                            select(AppointmentType.id, AppointmentType.name).where(
                                AppointmentType.tenant_id == tenant_id,
                                AppointmentType.id.in_(waitlist_type_ids),
                            )
                        )
                    ).all()
                }
            )
            # The `is not None` is F50's, and it is the difference between this
            # route answering and 500-ing: a walk-in booking carries NO terms
            # evidence (0025 made the two columns nullable, bounded to
            # `source = 'walk_in'`), and `sorted()` over a set holding None raises
            # TypeError. §13 is a legally-mandated answer; it must not be the one
            # route that falls over on a row the product creates on purpose.
            versions = sorted(
                {
                    row.terms_version_accepted
                    for row in bookings
                    if row.terms_version_accepted is not None
                }
            )
            terms = (
                []
                if not versions
                else list(
                    (
                        await session.execute(
                            select(TermsVersion)
                            .where(
                                TermsVersion.tenant_id == tenant_id,
                                TermsVersion.version.in_(versions),
                                TermsVersion.deleted_at.is_(None),
                            )
                            .order_by(TermsVersion.version)
                        )
                    )
                    .scalars()
                    .all()
                )
            )
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.PRIVACY_SUBJECT_EXPORTED,
                actor_id=actor.id,
                entity=str(customer.id),
                details=_subject_details(customer.id, phone, reason),
            )
            return SubjectExportResponse(
                subject=ExportedSubject(
                    id=customer.id,
                    phone=customer.phone,
                    name=customer.name,
                    created_at=customer.created_at,
                    notes=customer.notes,
                    tags=list(customer.tags),
                    marketing_consent_at=customer.marketing_consent_at,
                    marketing_consent_source=customer.marketing_consent_source,
                    marketing_consent_withdrawn_at=customer.marketing_consent_withdrawn_at,
                    erased_at=customer.erased_at,
                ),
                bookings=[
                    ExportedBooking(
                        id=row.id,
                        starts_at=row.starts_at,
                        status=row.status,
                        source=row.source,
                        appointment_type_name=row.appointment_type_name,
                        dress_name=row.dress_name,
                        dress_size=row.dress_size,
                        notes=row.notes,
                        attendance_confirmed_at=row.attendance_confirmed_at,
                        checked_in_at=row.checked_in_at,
                        terms_version_accepted=row.terms_version_accepted,
                        terms_accepted_at=row.terms_accepted_at,
                        cancelled_at=row.cancelled_at,
                        cancelled_by=row.cancelled_by,
                    )
                    for row in bookings
                ],
                messages=[
                    ExportedMessage(
                        kind=row.kind,
                        status=row.status,
                        created_at=row.created_at,
                        body=row.body,
                    )
                    for row in messages
                ],
                queue_tickets=[
                    ExportedQueueTicket(
                        id=row.id,
                        queue_day=row.queue_day,
                        created_at=row.created_at,
                        name=row.name,
                        phone=row.phone,
                        visit_type=row.visit_type,
                        status=row.status,
                        marketing_opt_in_at=row.marketing_opt_in_at,
                    )
                    for row in tickets
                ],
                waitlist_entries=[
                    ExportedWaitlistEntry(
                        day=row.day,
                        appointment_type_name=type_names.get(row.appointment_type_id),
                        status=row.status,
                        created_at=row.created_at,
                    )
                    for row in waitlist_rows
                ],
                accepted_terms=[
                    ExportedTerms(
                        version=row.version,
                        terms_text=row.terms_text,
                        refundable_until_hours_before=row.refundable_until_hours_before,
                        forfeit_percent=row.forfeit_percent,
                    )
                    for row in terms
                ],
            )

    # --- §14 erasure ---

    async def erase_subject(
        self,
        tenant_id: uuid.UUID,
        *,
        customer_id: uuid.UUID,
        actor: StaffContext,
        reason: str | None,
    ) -> SubjectEraseResponse:
        """ONE transaction, six steps, and the order is the design.

        ⚠ **`pg_advisory_xact_lock` is the FIRST statement (D18) and it is not
        defensive style.** `create_booking` and `reschedule` both take the
        per-tenant lock, and `CustomersRepository.upsert`'s docstring is explicit
        that it is lock-free "because every caller already holds" it. Without
        this line: the erase reads her row and passes the step-1 guard; a
        concurrent storefront `create_booking` — holding the lock the erase did
        not take — upserts the same row and issues `existing.name = <her real
        name>`; that UPDATE blocks on the erase's row lock and applies AFTER the
        erase commits. Final state: `erased_at` set, phone scrubbed, her real
        name back on the row, and a `confirmed` future booking that step 1's 409
        exists to prevent. An erasure record that is a lie is worse than a
        refusal.
        """
        if reason is not None:
            validate_erase_reason(reason)
        self._spend(self._erase_limiter, tenant_id)
        async with tenant_session(self._session_factory, tenant_id) as session:
            # 0. The lock, before any read. `hashtext` matches the booking
            #    path's key derivation, so the two contend on the same lock.
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": str(tenant_id)}
            )
            customer = await self._customers.by_id(session, tenant_id, customer_id)
            if customer is None:
                # 404 and NO audit row. An unknown id must not produce a
                # `privacy_subject_erased` record for a subject who was never
                # touched — that is a fabricated §14 record on the one path
                # where the record is the entire deliverable (D17).
                raise SubjectNotFoundError
            # The phone is read HERE and held in Python: step 2 overwrites the
            # column, so steps 4 and 5 could not find it afterwards.
            phone = customer.phone
            if customer.erased_at is not None:
                # Idempotent, and reachable only because the route is keyed on
                # the id. She tapped twice; that is not an error (F16 D1's "she
                # will click it more than once", applied to the owner). Zero
                # counts are TRUE of this call.
                await self._audit.record(
                    session,
                    tenant_id=tenant_id,
                    action=AuditAction.PRIVACY_SUBJECT_ERASED,
                    actor_id=actor.id,
                    entity=str(customer_id),
                    details=_subject_details(
                        customer_id, phone, reason, counts=_ZERO_COUNTS, already_erased=True
                    ),
                )
                return SubjectEraseResponse(
                    customer_id=customer_id, already_erased=True, **_ZERO_COUNTS
                )

            # 1. Refuse while a live future booking exists.
            live = (
                await session.execute(
                    select(func.count())
                    .select_from(Booking)
                    .where(
                        Booking.tenant_id == tenant_id,
                        Booking.customer_id == customer_id,
                        Booking.deleted_at.is_(None),
                        Booking.status == BookingStatus.CONFIRMED.value,
                        Booking.starts_at > func.now(),
                    )
                )
            ).scalar_one()
            if live:
                raise SubjectHasActiveBookingError

            booking_ids = list(
                (
                    await session.execute(
                        select(Booking.id).where(
                            Booking.tenant_id == tenant_id, Booking.customer_id == customer_id
                        )
                    )
                )
                .scalars()
                .all()
            )

            # 2. Her row. The phone placeholder is PER ROW so
            #    `idx_customers_tenant_phone_unique` admits any number of
            #    erasures in one tenant; `notes`/`tags` go with it (DR-12),
            #    because a paragraph the console wrote about her is more
            #    sensitive than the booking notes, not less.
            await session.execute(
                update(Customer)
                .where(Customer.tenant_id == tenant_id, Customer.id == customer_id)
                .values(
                    name=ERASED_NAME,
                    phone=ERASED_PHONE_PREFIX + str(customer_id),
                    notes=None,
                    tags=[],
                    erased_at=func.now(),
                    # ⚠ THE `CASE` IS LOAD-BEARING AND THE MAJORITY PATH DEPENDS
                    # ON IT. `customers_marketing_withdraw_check` REJECTS a
                    # withdrawal stamp on a row with no consent — it does not
                    # ignore it — and a NULL consent is every customer who never
                    # ticked the box. An unconditional `= now()` here is an
                    # IntegrityError 500 for most subjects, while a test seeded
                    # with a consenting one stays green.
                    marketing_consent_withdrawn_at=_withdraw_case(),
                )
                .execution_options(synchronize_session=False)
            )

            # 3. Her bookings survive as the boutique's business and tax record;
            #    the free text and the still-live SMS link do not.
            bookings_scrubbed = len(
                (
                    await session.execute(
                        update(Booking)
                        .where(Booking.tenant_id == tenant_id, Booking.customer_id == customer_id)
                        .values(notes=None, manage_token_hash=None)
                        .returning(Booking.id)
                        .execution_options(synchronize_session=False)
                    )
                )
                .scalars()
                .all()
            )

            # 4. `phone = :phone OR booking_id IN (:hers)`, and the OR is not
            #    belt-and-braces: F15's phone correction re-points
            #    `bookings.customer_id` at an existing row and ORPHANS the old
            #    ones, so a phone-only predicate leaves her PRE-CORRECTION
            #    number in the log forever.
            messages_scrubbed = len(
                (
                    await session.execute(
                        update(MessageLog)
                        .where(*_her_messages(tenant_id, phone, booking_ids))
                        .values(phone=ERASED_PHONE_PREFIX + str(customer_id), body="")
                        .returning(MessageLog.id)
                        .execution_options(synchronize_session=False)
                    )
                )
                .scalars()
                .all()
            )

            # 4b. Her walk-in check-ins (DR-9's fourth collection point). Without
            #     this statement the erase returns 200 and leaves her REAL NAME
            #     and her REAL E.164 NUMBER standing in `queue_tickets` — and the
            #     only thing that would ever remove them is the queue retention
            #     policy, which ships disarmed (Gate 1 Q2). The public Hebrew
            #     promises the survivors are kept «בלי שמך ובלי מספר הטלפון שלך»;
            #     that sentence is true only with this line.
            #
            #     Matched on the phone HELD IN PYTHON — step 2 destroyed the
            #     column — and deliberately NOT filtered on `deleted_at`: an
            #     erasure must reach every copy, including a row some future
            #     feature soft-deletes. The placeholder is per row, the
            #     `customers` convention, so a tenant's Nth erasure cannot
            #     collide with its first.
            tickets_scrubbed = len(
                (
                    await session.execute(
                        update(QueueTicket)
                        .where(
                            QueueTicket.tenant_id == tenant_id,
                            QueueTicket.phone == phone,
                        )
                        .values(name=ERASED_NAME, phone=ERASED_PHONE_PREFIX + str(customer_id))
                        .returning(QueueTicket.id)
                        .execution_options(synchronize_session=False)
                    )
                )
                .scalars()
                .all()
            )

            # 4c. Her booking-waitlist joins (F22, spec D4). Same spelling as
            #     the queue scrub above: matched on the phone HELD IN PYTHON —
            #     step 2 destroyed the column — not filtered on deleted_at, and
            #     the placeholder is per erasure so the row survives as evidence
            #     she was on the list while naming nobody. An erased phone can
            #     rejoin later — new OTP, new entry, new consent context.
            #
            #     The status CASE is load-bearing too: a scrub that stopped at
            #     the phone would leave her ACTIVE — on the manage list, inside
            #     `idx_waitlist_entries_active_unique`, first in line for an F23
            #     offer nobody can send her. Active rows ('waiting'/'offered')
            #     take the manage cancel's exact value; terminal rows keep their
            #     status — history, not state. No WAITLIST_ENTRY_CANCELLED row:
            #     like every surface above, the change rides the single
            #     PRIVACY_SUBJECT_ERASED record in step 6.
            waitlist_scrubbed = len(
                (
                    await session.execute(
                        update(WaitlistEntry)
                        .where(
                            WaitlistEntry.tenant_id == tenant_id,
                            WaitlistEntry.phone == phone,
                        )
                        .values(
                            phone=ERASED_PHONE_PREFIX + str(customer_id),
                            status=case(
                                (
                                    WaitlistEntry.status.in_(
                                        (
                                            WaitlistEntryStatus.WAITING.value,
                                            WaitlistEntryStatus.OFFERED.value,
                                        )
                                    ),
                                    WaitlistEntryStatus.CANCELLED.value,
                                ),
                                else_=WaitlistEntry.status,
                            ),
                        )
                        .returning(WaitlistEntry.id)
                        .execution_options(synchronize_session=False)
                    )
                )
                .scalars()
                .all()
            )

            # 5. PURGED, not scrubbed: the whole row is her data in both cases.
            otp_purged = len(
                (
                    await session.execute(
                        delete(OtpCode)
                        .where(OtpCode.tenant_id == tenant_id, OtpCode.phone == phone)
                        .returning(OtpCode.id)
                        .execution_options(synchronize_session=False)
                    )
                )
                .scalars()
                .all()
            )
            scheduled_purged = (
                0
                if not booking_ids
                else len(
                    (
                        await session.execute(
                            delete(ScheduledMessage)
                            .where(
                                ScheduledMessage.tenant_id == tenant_id,
                                ScheduledMessage.booking_id.in_(booking_ids),
                            )
                            .returning(ScheduledMessage.id)
                            .execution_options(synchronize_session=False)
                        )
                    )
                    .scalars()
                    .all()
                )
            )

            counts = {
                "bookings_scrubbed": bookings_scrubbed,
                "messages_scrubbed": messages_scrubbed,
                "queue_tickets_scrubbed": tickets_scrubbed,
                "waitlist_entries_scrubbed": waitlist_scrubbed,
                "otp_codes_purged": otp_purged,
                "scheduled_messages_purged": scheduled_purged,
            }
            # 6. The record. `customer_id` + `phone_last4` + counts + reason,
            #    and never a name or a full number (D19).
            await self._audit.record(
                session,
                tenant_id=tenant_id,
                action=AuditAction.PRIVACY_SUBJECT_ERASED,
                actor_id=actor.id,
                entity=str(customer_id),
                details=_subject_details(
                    customer_id, phone, reason, counts=counts, already_erased=False
                ),
            )
            return SubjectEraseResponse(customer_id=customer_id, already_erased=False, **counts)

    # --- §30A withdrawal ---

    async def withdraw_marketing(
        self,
        tenant_id: uuid.UUID,
        *,
        customer_id: uuid.UUID | None,
        raw_phone: str | None,
        actor: StaffContext,
    ) -> MarketingWithdrawResponse:
        """The lesser action, short of erasure (D15) — and the ONE privacy route
        a shift manager may take (Gate 1 Q4).

        Two arms, two stores, and the phone arm never writes `customers`.

        An unknown phone answers `changed: false`, not 404: a walk-in who never
        ticked the box and a number the boutique has never seen are the same
        outcome she asked for. An unknown `customer_id` DOES 404 — the console
        only ever sends one it got from a lookup, so a miss there means the id
        is wrong rather than that the answer is "nothing to do".

        **Audited only when something changed.** `PLATFORM_DPA_HE` promises the
        public that staff changes to a customer's record are logged, and this is
        one; the `changed` guard is what keeps that promise without letting the
        one route a shift manager can spam accumulate rows in the one table that
        is exempt from every retention class. The phone arm needs the row most —
        it NULLs its own evidence.
        """
        self._spend(self._withdraw_limiter, tenant_id)
        async with tenant_session(self._session_factory, tenant_id) as session:
            if customer_id is not None:
                subject = await self._customers.by_id(session, tenant_id, customer_id)
                if subject is None:
                    raise SubjectNotFoundError
                changed = await self._customers.withdraw_marketing_consent(
                    session, tenant_id, customer_id
                )
                if changed:
                    await self._audit_withdrawal(
                        session,
                        tenant_id,
                        actor=actor,
                        customer_id=customer_id,
                        phone=subject.phone,
                    )
                return MarketingWithdrawResponse(changed=changed)
            if raw_phone is None:  # pragma: no cover - the schema forbids it
                raise DomainValidationError("Send exactly one of customer_id or phone.")
            phone = normalize_israeli_mobile(raw_phone)
            cleared = await self._queue_tickets.withdraw_marketing_opt_in(
                session, tenant_id, phone=phone
            )
            if cleared:
                await self._audit_withdrawal(
                    session, tenant_id, actor=actor, customer_id=None, phone=phone, cleared=cleared
                )
            return MarketingWithdrawResponse(changed=cleared > 0)

    async def _audit_withdrawal(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        actor: StaffContext,
        customer_id: uuid.UUID | None,
        phone: str,
        cleared: int | None = None,
    ) -> None:
        """`phone_last4` and never the number, D19's rule applied to the third
        subject route. The phone arm has no `customer_id` to carry — that is the
        whole point of the split — so `entity` is the last four digits, which is
        also the most of a number that may be written here."""
        details: dict[str, Any] = {"phone_last4": _last4(phone)}
        if customer_id is not None:
            details["customer_id"] = str(customer_id)
        if cleared is not None:
            details["tickets_cleared"] = cleared
        await self._audit.record(
            session,
            tenant_id=tenant_id,
            action=AuditAction.PRIVACY_MARKETING_WITHDRAWN,
            actor_id=actor.id,
            entity=str(customer_id) if customer_id is not None else str(_last4(phone)),
            details=details,
        )

    def _spend(self, limiter: FixedWindowRateLimiter, tenant_id: uuid.UUID) -> None:
        """Read the budget then record against it. Recorded on EVERY call, not
        only on failures: the thing being bounded is how often a whole person is
        assembled or destroyed, and a limiter that counted only misses would be
        inert on exactly the calls that succeed."""
        key = f"privacy:{tenant_id}"
        if limiter.is_blocked(key):
            raise PrivacyThrottledError
        limiter.record_failure(key)


_ZERO_COUNTS = {
    "bookings_scrubbed": 0,
    "messages_scrubbed": 0,
    "queue_tickets_scrubbed": 0,
    "waitlist_entries_scrubbed": 0,
    "otp_codes_purged": 0,
    "scheduled_messages_purged": 0,
}


def _withdraw_case() -> Any:
    """`CASE WHEN marketing_consent_at IS NOT NULL THEN now() ELSE
    marketing_consent_withdrawn_at END` — see the call site for why it cannot be
    an unconditional assignment.

    The ELSE writes the column back to itself rather than to NULL, so a subject
    who consented and had ALREADY withdrawn keeps her original withdrawal
    instant: that timestamp is evidence of when the boutique stopped being
    allowed to send, and the erasure must not restate it as today.
    """
    return case(
        (Customer.marketing_consent_at.is_not(None), func.now()),
        else_=Customer.marketing_consent_withdrawn_at,
    )


def _subject_details(
    customer_id: uuid.UUID,
    phone: str,
    reason: str | None,
    *,
    counts: dict[str, int] | None = None,
    already_erased: bool | None = None,
) -> dict[str, Any]:
    """The audit payload for both subject routes. `phone_last4` and never the
    number; no name at any depth. `test_privacy_api.py` walks the written
    payload for both."""
    details: dict[str, Any] = {"customer_id": str(customer_id), "phone_last4": _last4(phone)}
    if reason is not None:
        details["reason"] = reason
    if counts is not None:
        details["counts"] = counts
    if already_erased is not None:
        details["already_erased"] = already_erased
    return details


def _her_messages(tenant_id: uuid.UUID, phone: str, bookings: list[Any]) -> list[Any]:
    """`phone = :hers OR booking_id IN (:her bookings)`, shared by the export and
    the erase so the two cannot disagree about which rows are hers.

    ⚠ **A `str`, never the `Customer`.** The erase's step 2 overwrites
    `customers.phone`, and this predicate is built at step 4. Taking the ORM
    object made the phone leg correct only because nothing between them expires
    the identity map — add a `commit()` or drop `synchronize_session=False` and
    it silently resolves to `erased:{id}`, matching nothing and leaving her
    pre-correction number in `message_log` forever. The call site holds the
    string it captured before step 2; this signature is what makes that the only
    thing it can pass.

    `bookings` may be `Booking` rows or bare ids — the export holds the rows it
    already read and the erase holds a projection of ids, and materialising the
    other shape at either call site would be a second statement for nothing.
    """
    ids = [row if isinstance(row, uuid.UUID) else row.id for row in bookings]
    legs = [MessageLog.phone == phone]
    if ids:
        legs.append(MessageLog.booking_id.in_(ids))
    return [
        MessageLog.tenant_id == tenant_id,
        MessageLog.deleted_at.is_(None),
        or_(*legs),
    ]
