"""F20's two subject routes against real Postgres as the non-owner app role.

Everything here is a claim no fake can make. The erase is ONE transaction whose
correctness IS an ordering — advisory lock, then the guard, then six writes in a
sequence where step 4 depends on a value step 2 has already destroyed — and an
ordering is only provable against a real transaction with a real second
connection racing it. So are the unique-index collision (two erasures in one
tenant), the `CASE` that keeps `customers_marketing_withdraw_check` unreachable
(a CHECK is DDL), and the survivor set (a scrub that leaves the wrong column
standing is invisible to any fake).

Helpers come from `test_booking_owner_db` rather than being re-typed: every
setup here needs a REAL booking made through `create_booking` — the 0009 replay
branch, the terms snapshot and the manage-token hash are all things a
hand-inserted row would get subtly wrong, and the phone-correction test needs
F15's actual code path.

NullPool + asyncio gives every racer its own connection — the shipped precedent,
and what makes the lock test real rather than two coroutines sharing a session.

Every test mints its own tenant id; the container is session-scoped and nothing
here truncates.
"""

import asyncio
import datetime
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_booking_owner_db import (
    NOW,
    SLOT_A,
    TARGET_DATE,
    _audit,
    _claim,
    _comms,
    _factory,
    _loose,
    _manage_tenant,
    _owner,
    _phone,
    _seed,
    _slot,
    _staff,
    # AUTOUSE, and imported for its side effect rather than called: this module
    # commits a walk-in booking too, and a surviving one makes every round-trip
    # test in the suite fail on 0025's refusing downgrade. See its docstring.
    _sweep_walk_in_bookings,  # noqa: F401
)

from app.auth.rate_limit import FixedWindowRateLimiter
from app.booking.manage import ManageBookingService
from app.booking.tokens import manage_token_hash
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.message_log import MessageLogRepository
from app.db.repositories.queue_tickets import QueueTicketsRepository
from app.db.repositories.waitlist_entries import WaitlistEntriesRepository
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.models.constants import (
    AuditAction,
    BookingSource,
    BookingStatus,
    MarketingConsentSource,
    MessageKind,
    VisitType,
)
from app.models.customer import Customer
from app.models.message_log import MessageLog
from app.models.otp_code import OtpCode
from app.models.queue_ticket import QueueTicket
from app.models.scheduled_message import ScheduledMessage
from app.models.waitlist_entry import WaitlistEntry
from app.privacy.service import (
    PrivacyService,
    SubjectHasActiveBookingError,
    SubjectNotFoundError,
)
from app.privacy.validation import ERASED_NAME, ERASED_PHONE_PREFIX

pytestmark = pytest.mark.db

# TARGET_DATE (2026-08-23) is a real FUTURE date and is what the 409 guard needs.
# PAST_DATE is 28 days earlier, so it lands on the SAME weekday — one seeded
# weekly rule serves both — and comfortably in the real past, which is what
# every erase test needs to get past that same guard.
PAST_DATE = TARGET_DATE - datetime.timedelta(days=28)
PAST_NOW = NOW - datetime.timedelta(days=28)
PAST_SLOT = _slot(10, date=PAST_DATE)
PAST_SLOT_B = _slot(11, date=PAST_DATE)

CUSTOMERS = CustomersRepository()
MESSAGES = MessageLogRepository()
QUEUE_TICKETS = QueueTicketsRepository()
WAITLIST = WaitlistEntriesRepository()


def _privacy(factory: async_sessionmaker[AsyncSession]) -> PrivacyService:
    return PrivacyService(
        factory,
        export_limiter=_loose(),
        erase_limiter=_loose(),
        withdraw_limiter=_loose(),
    )


async def _log(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    phone: str,
    booking_id: uuid.UUID | None,
    body: str,
    kind: str = MessageKind.CONFIRMATION.value,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await MESSAGES.insert(
            session, tenant_id=tenant_id, phone=phone, kind=kind, body=body, booking_id=booking_id
        )
        return row.id


async def _customer(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, customer_id: uuid.UUID
) -> Customer:
    async with tenant_session(factory, tenant_id) as session:
        row = await session.get(Customer, customer_id)
        assert row is not None
        return row


async def _bookings(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, customer_id: uuid.UUID
) -> list[Booking]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = (
            select(Booking)
            .where(Booking.tenant_id == tenant_id, Booking.customer_id == customer_id)
            .order_by(Booking.starts_at)
        )
        return list((await session.execute(stmt)).scalars().all())


# --- the export ---


async def test_the_export_returns_the_enumerated_record(app_role_url: str) -> None:
    """Two bookings and four message rows, and the assertion is on the EXACT
    field set of each shape — not "contains", because the failure this guards
    against is a §13 answer that quietly omits something the controller holds.

    `notes` and `tags` (F53's columns, plan DR-12) and `checked_in_at` (F34's,
    DR-15) are the three the spec's original enumeration predates. All three are
    facts about her that the boutique holds, so §13 reaches them.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        first = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone
        )
        second = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT_B, now=PAST_NOW, phone=phone
        )
        customer_id = first.booking.customer_id
        async with tenant_session(factory, tenant_id) as session:
            row = await session.get(Customer, customer_id)
            assert row is not None
            row.notes = "מגיעה עם אמא"
            row.tags = ["VIP"]
            booking = await session.get(Booking, first.booking.id)
            assert booking is not None
            booking.checked_in_at = PAST_SLOT
        for index in range(4):
            await _log(
                factory,
                tenant_id,
                phone=phone,
                booking_id=first.booking.id if index < 2 else None,
                body=f"הודעה {index}",
            )

        payload = await _privacy(factory).export_subject(
            tenant_id, raw_phone=phone, actor=_staff(tenant_id), reason=None
        )

        assert payload.subject.id == customer_id
        assert payload.subject.phone == phone
        assert payload.subject.notes == "מגיעה עם אמא"
        assert payload.subject.tags == ["VIP"]
        assert payload.subject.erased_at is None
        assert {booking.id for booking in payload.bookings} == {
            first.booking.id,
            second.booking.id,
        }
        assert payload.bookings[0].checked_in_at == PAST_SLOT
        assert payload.bookings[0].terms_version_accepted == 1
        assert len(payload.messages) == 4
        # The message shape ships FOUR fields; `provider_message_id` and `error`
        # have no field at any depth (asserted over the wire in
        # test_privacy_api.py's disclosure walk).
        assert set(payload.messages[0].model_dump()) == {"kind", "status", "created_at", "body"}
        assert [terms.version for terms in payload.accepted_terms] == [1]
        assert payload.accepted_terms[0].terms_text == "תנאי ביטול"
    finally:
        await engine.dispose()


async def test_the_export_audits_the_access_with_a_last4_and_never_the_number(
    app_role_url: str,
) -> None:
    """D19, and checklist row 38 is why the READ is audited at all: it says
    "data ACCESS by operators", not "data changes by operators".

    `audit_log` has no retention class and never will — a clock on the evidence
    would eventually erase the proof of the erasures it records — so a full phone
    written here is a permanent copy of the identifier the sibling route exists
    to destroy.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    actor = _staff(tenant_id)
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone
        )
        await _privacy(factory).export_subject(
            tenant_id, raw_phone=phone, actor=actor, reason="בקשת עיון טלפונית"
        )

        rows = [
            row
            for row in await _audit(factory, tenant_id)
            if row.action == AuditAction.PRIVACY_SUBJECT_EXPORTED.value
        ]
        assert len(rows) == 1
        details = rows[0].details
        assert rows[0].actor_id == actor.id
        assert details["customer_id"] == str(claim.booking.customer_id)
        assert details["phone_last4"] == phone[-4:]
        assert details["reason"] == "בקשת עיון טלפונית"
        written = str(details)
        assert phone not in written, "the audit row carries the FULL phone"
        assert "נועה לוי" not in written, "the audit row carries her name"
    finally:
        await engine.dispose()


async def test_an_unknown_phone_is_404_and_writes_no_audit_row(app_role_url: str) -> None:
    """No row for a subject who was never accessed — the export half of D17's
    fabricated-record problem."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        await _seed(factory, tenant_id)
        with pytest.raises(SubjectNotFoundError):
            await _privacy(factory).export_subject(
                tenant_id, raw_phone=_phone(), actor=_staff(tenant_id), reason=None
            )
        assert await _audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def test_the_export_normalises_the_phone_the_owner_typed(app_role_url: str) -> None:
    """`customers.phone` holds strict E.164 and `by_phone` is exact equality, so
    without `normalize_israeli_mobile` every `05X…` an owner reads off a card
    would 404 a customer who demonstrably exists."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = "+972501234567"
    try:
        type_id = await _seed(factory, tenant_id)
        await _claim(factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone)
        payload = await _privacy(factory).export_subject(
            tenant_id, raw_phone="050-123-4567", actor=_staff(tenant_id), reason=None
        )
        assert payload.subject.phone == phone
    finally:
        await engine.dispose()


async def test_the_subject_export_survives_a_walk_in_booking(app_role_url: str) -> None:
    """F50's ripple, asserted here rather than discovered in production.

    0025 made `bookings.terms_version_accepted` and `terms_accepted_at` nullable —
    bounded to `source = 'walk_in'`, but nullable — and this route held TWO
    readers that assumed otherwise. Both were 500s on a LEGALLY MANDATED answer:
    `sorted()` over a set containing None raises TypeError, and `ExportedBooking`
    is a plain BaseModel constructed explicitly, so a None on a non-optional field
    is a ValidationError. Two independent single-line reds, which is the correct
    shape for the highest-risk edit in the feature.

    ⚠ BOTH BOOKINGS ARE REQUIRED. With only a walk-in the `terms` array is empty
    and the "exactly the one version that exists" assertion passes on nothing —
    and with only a storefront booking there is no None to trip over at all. The
    pair is what makes each half of the answer a difference rather than a
    property of the fixture.

    The §13 answer must SHOW THE ABSENCE honestly: a walk-in genuinely carries no
    terms evidence, and inventing a version to keep the schema tidy would be
    fabricating exactly the record F20's D17 refuses to fabricate."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        storefront = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone
        )
        customer_id = storefront.booking.customer_id
        walk_in = await _owner(factory, now=PAST_NOW).create_walk_in(
            tenant_id,
            customer_id=customer_id,
            appointment_type_id=type_id,
            staff=_staff(tenant_id),
        )

        payload = await _privacy(factory).export_subject(
            tenant_id, raw_phone=phone, actor=_staff(tenant_id), reason=None
        )

        exported = {row.id: row for row in payload.bookings}
        assert set(exported) == {storefront.booking.id, walk_in.booking.id}

        assert exported[walk_in.booking.id].terms_version_accepted is None
        assert exported[walk_in.booking.id].terms_accepted_at is None
        # The discriminator, on BOTH rows. Without it the authority reading this
        # export sees a null version with no way to tell a lawful walk-in from a
        # corrupted storefront record — the exact inference `bookings_source_check`
        # and `bookings_terms_evidence_check` exist to make unnecessary. Deleting
        # `source=row.source` from the ExportedBooking construction reds it.
        assert exported[walk_in.booking.id].source == BookingSource.WALK_IN.value
        assert exported[storefront.booking.id].source == BookingSource.STOREFRONT.value
        # She attended — that is a fact about her, so §13 reaches it.
        assert exported[walk_in.booking.id].checked_in_at == PAST_NOW

        assert exported[storefront.booking.id].terms_version_accepted == 1
        assert exported[storefront.booking.id].terms_accepted_at is not None

        # EXACTLY the one version that exists. A `sorted()` that swallowed the
        # None by coercing it, or a comprehension that kept it, would show here.
        assert [terms.version for terms in payload.accepted_terms] == [1]
    finally:
        await engine.dispose()


# --- the erase ---


async def test_the_erase_scrubs_her_and_leaves_the_enumerated_survivors_intact(
    app_role_url: str,
) -> None:
    """Steps 2-5, and the survivor list is the point.

    What survives is the boutique's business and tax record plus the
    terms-acceptance evidence. It is NOT anonymous data and the compliance record
    must not call it that: it is de-identified business record with a controlled
    re-identification key, because an actor who can read `audit_log` can walk
    `customer_id` back to it. Both of those are true only if the row really does
    keep its `starts_at`, its dress and its terms version — which is what the
    second half of this test asserts, and what a scrub that reached too far would
    break.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone
        )
        customer_id = claim.booking.customer_id
        booking_id = claim.booking.id
        async with tenant_session(factory, tenant_id) as session:
            row = await session.get(Customer, customer_id)
            assert row is not None
            row.notes = "אחות של הכלה מהפעם הקודמת"
            row.tags = ["VIP"]
            await CUSTOMERS.record_marketing_consent(session, tenant_id, customer_id)
            booking = await session.get(Booking, booking_id)
            assert booking is not None
            booking.notes = "רגישה לתחרה"
            # NOTHING is seeded into `otp_codes` or `scheduled_messages`:
            # `create_booking` already wrote one of each — the verification code
            # and the reminder — and `idx_scheduled_messages_pending_unique`
            # refuses a second pending row anyway. The counts below are therefore
            # over rows the PRODUCT wrote, which is the stronger assertion.
        await _log(factory, tenant_id, phone=phone, booking_id=booking_id, body="אושר")

        summary = await _privacy(factory).erase_subject(
            tenant_id, customer_id=customer_id, actor=_staff(tenant_id), reason="בקשה שאומתה"
        )

        assert summary.already_erased is False
        assert summary.bookings_scrubbed == 1
        assert summary.messages_scrubbed == 1
        assert summary.otp_codes_purged == 1
        assert summary.scheduled_messages_purged == 1

        erased = await _customer(factory, tenant_id, customer_id)
        assert erased.name == ERASED_NAME
        assert erased.phone == ERASED_PHONE_PREFIX + str(customer_id)
        assert erased.notes is None
        assert erased.tags == []
        assert erased.erased_at is not None
        # The consent stamp SURVIVES and the withdrawal is added beside it: the
        # first is the evidence that the sends made before today were lawful.
        assert erased.marketing_consent_at is not None
        assert erased.marketing_consent_withdrawn_at is not None

        survivor = (await _bookings(factory, tenant_id, customer_id))[0]
        assert survivor.notes is None
        assert survivor.manage_token_hash is None
        assert survivor.starts_at == PAST_SLOT
        assert survivor.status == BookingStatus.CONFIRMED.value
        assert survivor.appointment_type_name == "מדידה ראשונה"
        assert survivor.terms_version_accepted == 1
        assert survivor.terms_accepted_at is not None
        assert survivor.seat_index == 1
        assert survivor.deleted_at is None, "erasure is a scrub in place, never a soft delete"

        async with tenant_session(factory, tenant_id) as session:
            message = (
                (await session.execute(select(MessageLog).where(MessageLog.tenant_id == tenant_id)))
                .scalars()
                .one()
            )
            assert message.phone == ERASED_PHONE_PREFIX + str(customer_id)
            assert message.body == ""
            assert (
                await session.execute(select(OtpCode).where(OtpCode.tenant_id == tenant_id))
            ).scalars().all() == []
            assert (
                await session.execute(
                    select(ScheduledMessage).where(ScheduledMessage.tenant_id == tenant_id)
                )
            ).scalars().all() == []
    finally:
        await engine.dispose()


async def test_the_erase_reaches_her_walk_in_check_ins(app_role_url: str) -> None:
    """⚠ THE FOURTH COLLECTION POINT, and it is the one that made the shipped
    Hebrew false.

    `queue_tickets.name` and `queue_tickets.phone` are both `NOT NULL` and hold
    her REAL name and her REAL normalised E.164 number — the column's own
    comment records that the number matches `customers.phone` exactly, which is
    what makes a bride who booked online in March and walked in in June one
    person in two tables.

    Without the step-4b statement this erase answers 200, stamps `erased_at` and
    leaves both standing FOREVER: the only other thing that would ever remove
    them is the `queue_tickets` retention policy, and `retention_enabled` ships
    `False` (Gate 1 Q2). `PLATFORM_NOTICE_HE` promises the survivors are kept
    «בלי שמך ובלי מספר הטלפון שלך» and the compliance record instructs the owner
    to say so to a regulator. Delete the `update(QueueTicket)` and the two
    `ERASED_*` assertions below both fail.

    The second ticket, on a different number, is what proves the predicate is
    keyed on HER phone rather than draining the tenant's queue.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    other_phone = "+972529998877"
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone
        )
        customer_id = claim.booking.customer_id
        async with tenant_session(factory, tenant_id) as session:
            for day, ticket_phone, name in (
                (PAST_DATE, phone, "נועה לוי"),
                (PAST_DATE - datetime.timedelta(days=40), phone, "נועה לוי"),
                (PAST_DATE, other_phone, "מיכל כהן"),
            ):
                await QUEUE_TICKETS.insert(
                    session,
                    tenant_id=tenant_id,
                    queue_day=day,
                    name=name,
                    phone=ticket_phone,
                    visit_type=VisitType.BRIDE.value,
                    marketing_opt_in_at=PAST_NOW,
                )

        summary = await _privacy(factory).erase_subject(
            tenant_id, customer_id=customer_id, actor=_staff(tenant_id), reason=None
        )

        assert summary.queue_tickets_scrubbed == 2
        async with tenant_session(factory, tenant_id) as session:
            tickets = (
                (
                    await session.execute(
                        select(QueueTicket)
                        .where(QueueTicket.tenant_id == tenant_id)
                        .order_by(QueueTicket.queue_day)
                    )
                )
                .scalars()
                .all()
            )
        hers = [row for row in tickets if row.name != "מיכל כהן"]
        assert len(hers) == 2
        for ticket in hers:
            assert ticket.name == ERASED_NAME
            assert ticket.phone == ERASED_PHONE_PREFIX + str(customer_id)
        untouched = [row for row in tickets if row.name == "מיכל כהן"]
        assert [row.phone for row in untouched] == [other_phone]
    finally:
        await engine.dispose()


async def test_the_export_carries_her_walk_in_check_ins(app_role_url: str) -> None:
    """§13 is the same completeness question as §14, one route earlier: a bride
    the console CAN look up must be shown the check-in rows the boutique holds
    about her, not only her bookings. Delete the `select(QueueTicket)` from
    `export_subject` and this is an empty list."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        await _claim(factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone)
        async with tenant_session(factory, tenant_id) as session:
            await QUEUE_TICKETS.insert(
                session,
                tenant_id=tenant_id,
                queue_day=PAST_DATE,
                name="נועה לוי",
                phone=phone,
                visit_type=VisitType.BRIDE.value,
                marketing_opt_in_at=PAST_NOW,
            )
            await QUEUE_TICKETS.insert(
                session,
                tenant_id=tenant_id,
                queue_day=PAST_DATE,
                name="מיכל כהן",
                phone="+972529998877",
                visit_type=VisitType.BRIDE.value,
            )

        payload = await _privacy(factory).export_subject(
            tenant_id, raw_phone=phone, actor=_staff(tenant_id), reason=None
        )

        assert len(payload.queue_tickets) == 1
        ticket = payload.queue_tickets[0]
        assert ticket.name == "נועה לוי"
        assert ticket.phone == phone
        assert ticket.queue_day == PAST_DATE
        assert ticket.marketing_opt_in_at is not None
        # The queue's own management state is NOT her data, the `seat_index`
        # rule one table over.
        assert set(ticket.model_dump()) == {
            "id",
            "queue_day",
            "created_at",
            "name",
            "phone",
            "visit_type",
            "status",
            "marketing_opt_in_at",
        }
    finally:
        await engine.dispose()


async def test_the_erased_manage_token_no_longer_resolves(app_role_url: str) -> None:
    """NULLing `manage_token_hash` is what kills the still-live SMS link, and
    the only honest way to assert it is through the public lookup the link
    actually uses."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone
        )
        token = claim.manage_token
        assert token is not None
        async with tenant_session(factory, tenant_id) as session:
            booking = await session.get(Booking, claim.booking.id)
            assert booking is not None
            booking.manage_token_hash = manage_token_hash(token)

        manage = ManageBookingService(factory, lookup_limiter=_loose(), clock=lambda: PAST_NOW)
        # `ManageBookingFacts` deliberately carries no id — the link is
        # possession-auth and names nobody — so the pre-state assertion is on
        # the one fact that identifies THIS booking on this token.
        before = await manage.lookup(_manage_tenant(tenant_id), token=token)
        assert before.booking.starts_at == PAST_SLOT

        await _privacy(factory).erase_subject(
            tenant_id, customer_id=claim.booking.customer_id, actor=_staff(tenant_id), reason=None
        )

        from app.booking.manage import BookingLinkInvalidError

        with pytest.raises(BookingLinkInvalidError):
            await manage.lookup(_manage_tenant(tenant_id), token=token)
    finally:
        await engine.dispose()


async def test_two_erasures_in_one_tenant_do_not_violate_the_phone_unique_index(
    app_role_url: str,
) -> None:
    """`idx_customers_tenant_phone_unique` is UNIQUE on (tenant_id, phone), so a
    CONSTANT placeholder would make the SECOND erasure in a boutique raise —
    permanently, and only for boutiques that have already served one request.
    The per-row `erased:{id}` form is what admits any number of them."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        first = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=_phone()
        )
        second = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT_B, now=PAST_NOW, phone=_phone()
        )
        service = _privacy(factory)
        for claim in (first, second):
            await service.erase_subject(
                tenant_id,
                customer_id=claim.booking.customer_id,
                actor=_staff(tenant_id),
                reason=None,
            )
        phones = {
            (await _customer(factory, tenant_id, claim.booking.customer_id)).phone
            for claim in (first, second)
        }
        assert len(phones) == 2
    finally:
        await engine.dispose()


async def test_the_message_predicate_reaches_a_pre_correction_phone(app_role_url: str) -> None:
    """⚠ THE `OR booking_id IN (…)` LEG, AND IT IS NOT BELT-AND-BRACES.

    F15's phone correction, collision branch: the booking re-points at the
    customer who already holds the corrected number and BOTH customer rows
    survive. Every `message_log` row written before the correction still carries
    the OLD number and still points at the booking — so a phone-only predicate
    leaves her first number in the log forever, in the action that exists to
    remove it.

    Set up through the real `correct_phone`, never by hand: the orphaning is a
    property of that code path, and a hand-built fixture would assert the
    predicate against a shape the product cannot actually produce.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    old_phone = _phone()
    kept_phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        # The customer who already holds the corrected number.
        keeper = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=kept_phone
        )
        # The mistyped one, on a LIVE future booking — `correct_phone` guards on
        # exactly that, so the correction is only reachable here.
        wrong = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=old_phone)
        stale = await _log(
            factory, tenant_id, phone=old_phone, booking_id=wrong.booking.id, body="אושר"
        )

        comms, _ = _comms(factory)
        await _owner(factory, comms=comms).correct_phone(
            tenant_id, wrong.booking.id, phone=kept_phone, staff=_staff(tenant_id)
        )

        async with tenant_session(factory, tenant_id) as session:
            moved = await session.get(Booking, wrong.booking.id)
            assert moved is not None
            assert moved.customer_id == keeper.booking.customer_id, (
                "the collision branch did not re-point the booking — this test's premise is gone"
            )
            # Its future `confirmed` status is what step 1 refuses on, and the
            # subject is entitled to have it cancelled first. Set here rather
            # than through the cancel service because the SUBJECT of this test is
            # the message predicate, not the cancellation.
            moved.status = BookingStatus.CANCELLED.value

        summary = await _privacy(factory).erase_subject(
            tenant_id,
            customer_id=keeper.booking.customer_id,
            actor=_staff(tenant_id),
            reason=None,
        )
        assert summary.messages_scrubbed == 1

        async with tenant_session(factory, tenant_id) as session:
            row = await session.get(MessageLog, stale)
            assert row is not None
            assert row.phone != old_phone, "her PRE-CORRECTION number is still in the log"
            assert row.body == ""
    finally:
        await engine.dispose()


async def test_a_second_erase_with_the_same_customer_id_is_zero_counts(
    app_role_url: str,
) -> None:
    """Reachable ONLY because the route is keyed on the id (D17). She tapped
    twice; that is not an error, and the zero counts are a true statement about
    the second call rather than a fiction.

    `erased_at` must not move — for a subject whose bookings have since aged out
    it is the only proof left that the erasure happened at all.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=_phone()
        )
        customer_id = claim.booking.customer_id
        service = _privacy(factory)
        await service.erase_subject(
            tenant_id, customer_id=customer_id, actor=_staff(tenant_id), reason=None
        )
        first_stamp = (await _customer(factory, tenant_id, customer_id)).erased_at

        repeat = await service.erase_subject(
            tenant_id, customer_id=customer_id, actor=_staff(tenant_id), reason=None
        )
        assert repeat.already_erased is True
        assert repeat.bookings_scrubbed == 0
        assert repeat.messages_scrubbed == 0
        assert repeat.otp_codes_purged == 0
        assert repeat.scheduled_messages_purged == 0
        assert (await _customer(factory, tenant_id, customer_id)).erased_at == first_stamp
    finally:
        await engine.dispose()


async def test_an_unknown_customer_id_is_404_and_writes_no_audit_row(app_role_url: str) -> None:
    """⚠ D17's WHOLE ARGUMENT, ASSERTED. A 200-with-zero-counts for an
    unresolvable subject would give an owner who mistyped a digit a success
    screen AND write a `privacy_subject_erased` row for a person who was never
    touched — a fabricated §14 compliance record, on the one path where the
    record is the entire deliverable.

    ⚠ **What the second assertion can and cannot catch, verified by mutation
    rather than assumed.** Adding an `await self._audit.record(...)` immediately
    BEFORE the `raise` leaves this test green — `tenant_session` wraps the body
    in `session.begin()`, so the raise rolls the row away and it never commits.
    The mutation that reddens it is the one D17 actually warns about: replacing
    the raise with a 200-and-an-audit-row. That is the shape a future author
    reaches for when "she will click it more than once" gets misapplied to an
    unresolvable id, and it is the one this test is here to stop.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        await _seed(factory, tenant_id)
        with pytest.raises(SubjectNotFoundError):
            await _privacy(factory).erase_subject(
                tenant_id, customer_id=uuid.uuid4(), actor=_staff(tenant_id), reason=None
            )
        assert await _audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def test_the_erase_refuses_while_a_confirmed_future_booking_exists(
    app_role_url: str,
) -> None:
    """The erasure duty yields to performing the contract she is still party to.
    Silently erasing a bride with a fitting on Thursday would break the
    appointment and the SMS link at once."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(factory, tenant_id, type_id, starts_at=SLOT_A, phone=_phone())
        with pytest.raises(SubjectHasActiveBookingError):
            await _privacy(factory).erase_subject(
                tenant_id,
                customer_id=claim.booking.customer_id,
                actor=_staff(tenant_id),
                reason=None,
            )
        # Nothing moved, and no record claims it did.
        assert (await _customer(factory, tenant_id, claim.booking.customer_id)).erased_at is None
        assert await _audit(factory, tenant_id) == []
    finally:
        await engine.dispose()


async def test_erasing_a_never_consenting_subject_leaves_the_withdrawal_null(
    app_role_url: str,
) -> None:
    """⚠ THE MAJORITY PATH, and the one an unconditional
    `marketing_consent_withdrawn_at = now()` breaks.

    `customers_marketing_withdraw_check` REJECTS a withdrawal stamp on a row with
    no consent — it does not ignore it — so without the `CASE` this route is an
    IntegrityError 500 for every customer who never ticked the box, which is most
    of them. A test seeded with a consenting subject stays green through that,
    which is exactly why this one exists beside it.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=_phone()
        )
        customer_id = claim.booking.customer_id
        assert (await _customer(factory, tenant_id, customer_id)).marketing_consent_at is None

        await _privacy(factory).erase_subject(
            tenant_id, customer_id=customer_id, actor=_staff(tenant_id), reason=None
        )

        erased = await _customer(factory, tenant_id, customer_id)
        assert erased.erased_at is not None
        assert erased.marketing_consent_withdrawn_at is None
    finally:
        await engine.dispose()


async def test_the_erase_audit_row_carries_counts_a_last4_and_no_identifier(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone
        )
        await _privacy(factory).erase_subject(
            tenant_id,
            customer_id=claim.booking.customer_id,
            actor=_staff(tenant_id),
            reason="בקשת מחיקה טלפונית שאומתה",
        )
        rows = [
            row
            for row in await _audit(factory, tenant_id)
            if row.action == AuditAction.PRIVACY_SUBJECT_ERASED.value
        ]
        assert len(rows) == 1
        details = rows[0].details
        assert details["counts"]["bookings_scrubbed"] == 1
        assert details["phone_last4"] == phone[-4:]
        written = str(details)
        assert phone not in written
        assert "נועה לוי" not in written
    finally:
        await engine.dispose()


async def test_the_erase_takes_the_tenant_advisory_lock_as_its_first_statement(
    app_role_url: str,
) -> None:
    """⚠ D18. Without this line the erase and the public booking path do not
    contend at all: the erase reads her row and passes the step-1 guard, a
    concurrent `create_booking` — holding the lock the erase did not take —
    upserts the same row and issues `existing.name = <her real name>`, that
    UPDATE blocks on the erase's ROW lock and applies AFTER the erase commits.
    Final state: `erased_at` set, phone scrubbed, and her real name back on the
    row. An erasure record that is a lie is worse than a refusal.

    Asserted by holding the SAME lock `create_booking` takes
    (`hashtext(:tenant_id)`, `booking/service.py:387`) on a second connection and
    proving the erase CANNOT proceed while it is held — then that it completes
    the moment it is released. Deleting the `pg_advisory_xact_lock` line makes
    the erase finish immediately and reddens the first assertion.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=_phone()
        )
        released = asyncio.Event()

        async def _hold_the_booking_lock() -> None:
            from sqlalchemy import text

            async with tenant_session(factory, tenant_id) as session:
                await session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext(:tenant_id))"),
                    {"tenant_id": str(tenant_id)},
                )
                await released.wait()

        holder = asyncio.create_task(_hold_the_booking_lock())
        # Let the holder actually acquire before the erase starts.
        await asyncio.sleep(0.2)
        erase = asyncio.create_task(
            _privacy(factory).erase_subject(
                tenant_id,
                customer_id=claim.booking.customer_id,
                actor=_staff(tenant_id),
                reason=None,
            )
        )
        done, _ = await asyncio.wait({erase}, timeout=1.0)
        assert not done, "the erase ran while the booking path held the tenant lock"

        released.set()
        await holder
        summary = await asyncio.wait_for(erase, timeout=10)
        assert summary.already_erased is False
    finally:
        await engine.dispose()


async def test_the_erase_touches_no_other_tenants_rows(app_role_url: str) -> None:
    """RLS is the fence and the explicit tenant predicate is the second one. The
    two boutiques share a phone number deliberately — the same woman really can
    be a customer of both, and one boutique erasing her must not erase the
    other's record of her."""
    engine, factory = _factory(app_role_url)
    mine = uuid.uuid4()
    theirs = uuid.uuid4()
    phone = _phone()
    try:
        mine_type = await _seed(factory, mine)
        theirs_type = await _seed(factory, theirs)
        ours = await _claim(
            factory, mine, mine_type, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone
        )
        hers = await _claim(
            factory, theirs, theirs_type, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone
        )

        await _privacy(factory).erase_subject(
            mine, customer_id=ours.booking.customer_id, actor=_staff(mine), reason=None
        )

        untouched = await _customer(factory, theirs, hers.booking.customer_id)
        assert untouched.phone == phone
        assert untouched.name == "נועה לוי"
        assert untouched.erased_at is None
    finally:
        await engine.dispose()


async def test_the_budget_is_per_route_and_a_spent_export_does_not_block_the_erase(
    app_role_url: str,
) -> None:
    """One budget, one instance. A shared limiter would let an owner's morning
    of lookups 429 the erase they were leading to."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=_phone()
        )
        from app.privacy.validation import PrivacyThrottledError

        service = PrivacyService(
            factory,
            export_limiter=FixedWindowRateLimiter(0, 3600.0, lambda: 0.0),
            erase_limiter=_loose(),
            withdraw_limiter=_loose(),
        )
        with pytest.raises(PrivacyThrottledError):
            await service.export_subject(
                tenant_id, raw_phone=_phone(), actor=_staff(tenant_id), reason=None
            )
        summary = await service.erase_subject(
            tenant_id, customer_id=claim.booking.customer_id, actor=_staff(tenant_id), reason=None
        )
        assert summary.already_erased is False
    finally:
        await engine.dispose()


# --- C8: the booking form's marketing consent ---


async def test_the_booking_form_stamps_the_consent_only_when_the_box_is_ticked(
    app_role_url: str,
) -> None:
    """Three legs, and the middle one is the compliance property.

    Unticked issues NO statement at all — not a clearing one. An empty checkbox
    on a later booking is not a withdrawal, and treating an omission as one
    would silently revoke a consent the boutique can prove it holds.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    quiet_phone = _phone()
    consenting_phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        quiet = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=quiet_phone
        )
        assert (
            await _customer(factory, tenant_id, quiet.booking.customer_id)
        ).marketing_consent_at is None

        consenting = await _claim(
            factory,
            tenant_id,
            type_id,
            starts_at=PAST_SLOT_B,
            now=PAST_NOW,
            phone=consenting_phone,
            marketing_consent=True,
        )
        customer_id = consenting.booking.customer_id
        row = await _customer(factory, tenant_id, customer_id)
        assert row.marketing_consent_at is not None
        assert row.marketing_consent_source == MarketingConsentSource.BOOKING_FORM.value
        stamped_at = row.marketing_consent_at

        # A second booking by the same consenting customer must NOT re-stamp:
        # the original timestamp is the evidence of when she agreed, and moving
        # it forward would misdate the proof.
        await _claim(
            factory,
            tenant_id,
            type_id,
            starts_at=_slot(12, date=PAST_DATE),
            now=PAST_NOW,
            phone=consenting_phone,
            marketing_consent=True,
        )
        assert (await _customer(factory, tenant_id, customer_id)).marketing_consent_at == stamped_at
    finally:
        await engine.dispose()


async def test_an_unticked_second_booking_does_not_revoke_an_existing_consent(
    app_role_url: str,
) -> None:
    """The half a clearing statement would break, asserted on its own because it
    is the one a "just set the column to the checkbox value" refactor destroys —
    and destroys silently, since nothing in the product reads the column yet."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        first = await _claim(
            factory,
            tenant_id,
            type_id,
            starts_at=PAST_SLOT,
            now=PAST_NOW,
            phone=phone,
            marketing_consent=True,
        )
        await _claim(factory, tenant_id, type_id, starts_at=PAST_SLOT_B, now=PAST_NOW, phone=phone)
        assert (
            await _customer(factory, tenant_id, first.booking.customer_id)
        ).marketing_consent_at is not None
    finally:
        await engine.dispose()


async def test_the_0009_replay_path_still_stamps_the_consent(app_role_url: str) -> None:
    """⚠ D20, AND THE REASON A SINGLE CALL SITE WOULD BE WRONG.

    When a claim commits but its 201 dies on a flaky mobile network, the retry
    takes the idempotency branch at `booking/service.py:412-427` and returns
    BEFORE step 6's `upsert` — so a consent write placed only beside the upsert
    is unreachable on exactly the resubmission a customer is most likely to
    make. She ticked the box, she saw a failure, she pressed the button again,
    and the second render tells her it worked.

    Setup: book WITHOUT the box, then replay the same slot and phone WITH it.
    The replay is a real one — `_claim` mints a fresh verification token, and
    the branch is entered because a live booking already exists at that instant
    for that customer.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        first = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone
        )
        customer_id = first.booking.customer_id
        assert (await _customer(factory, tenant_id, customer_id)).marketing_consent_at is None

        replay = await _claim(
            factory,
            tenant_id,
            type_id,
            starts_at=PAST_SLOT,
            now=PAST_NOW,
            phone=phone,
            marketing_consent=True,
        )
        assert replay.created is False, "this is not the replay branch — the test proves nothing"
        assert replay.booking.id == first.booking.id
        assert (await _customer(factory, tenant_id, customer_id)).marketing_consent_at is not None
    finally:
        await engine.dispose()


# --- C5: the two withdrawal arms, end to end ---


async def test_the_withdraw_customer_arm_is_additive_and_404s_an_unknown_id(
    app_role_url: str,
) -> None:
    """The lesser action short of erasure (D15). The consent stamp survives —
    it is the evidence that sends made before this instant were lawful.

    An unknown id IS a 404 here, unlike an unknown phone: the console only ever
    sends an id it got from a lookup, so a miss means the id is wrong rather
    than that the answer is "nothing to do".
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(
            factory,
            tenant_id,
            type_id,
            starts_at=PAST_SLOT,
            now=PAST_NOW,
            phone=_phone(),
            marketing_consent=True,
        )
        customer_id = claim.booking.customer_id
        service = _privacy(factory)

        first = await service.withdraw_marketing(
            tenant_id, customer_id=customer_id, raw_phone=None, actor=_staff(tenant_id)
        )
        assert first.changed is True
        row = await _customer(factory, tenant_id, customer_id)
        assert row.marketing_consent_withdrawn_at is not None
        assert row.marketing_consent_at is not None

        repeat = await service.withdraw_marketing(
            tenant_id, customer_id=customer_id, raw_phone=None, actor=_staff(tenant_id)
        )
        assert repeat.changed is False

        with pytest.raises(SubjectNotFoundError):
            await service.withdraw_marketing(
                tenant_id, customer_id=uuid.uuid4(), raw_phone=None, actor=_staff(tenant_id)
            )
    finally:
        await engine.dispose()


async def test_the_withdraw_phone_arm_normalises_and_never_touches_customers(
    app_role_url: str,
) -> None:
    """⚠ DR-10's amendment, and the normalisation is the half that breaks
    silently.

    A walk-in has NO `customers` row — F33 never writes one, and F20 declines to
    promote her counter opt-in into provable consent — so the id arm cannot reach
    her at all, while the notice she was shown promises she may revoke.
    `queue_tickets.phone` is stored normalised E.164, and the owner will type
    `050-…` off a card: without `normalize_israeli_mobile` this arm answers
    `changed: false` for every walk-in in the country.

    An unknown phone is `changed: false` and NOT a 404 — a woman who never ticked
    the box and a number the boutique has never seen are the same outcome she
    asked for, and telling them apart would turn a front-desk revocation into a
    presence oracle over the queue.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    walk_in_phone = "+972501234567"
    try:
        async with tenant_session(factory, tenant_id) as session:
            await QUEUE_TICKETS.insert(
                session,
                tenant_id=tenant_id,
                queue_day=PAST_DATE,
                name="נועה",
                phone=walk_in_phone,
                visit_type=VisitType.BRIDE.value,
                marketing_opt_in_at=PAST_NOW,
            )
        service = _privacy(factory)

        cleared = await service.withdraw_marketing(
            tenant_id, customer_id=None, raw_phone="050-123-4567", actor=_staff(tenant_id)
        )
        assert cleared.changed is True

        async with tenant_session(factory, tenant_id) as session:
            ticket = (
                (
                    await session.execute(
                        select(QueueTicket).where(QueueTicket.tenant_id == tenant_id)
                    )
                )
                .scalars()
                .one()
            )
            assert ticket.marketing_opt_in_at is None
            # Still in the queue, still herself: this is a consent withdrawal.
            assert ticket.name == "נועה"
            assert ticket.phone == walk_in_phone
            # NO `customers` row was created — nothing was laundered from an
            # unverified counter submission into provable consent (DR-10).
            assert (
                await session.execute(select(Customer).where(Customer.tenant_id == tenant_id))
            ).scalars().all() == []

        repeat = await service.withdraw_marketing(
            tenant_id, customer_id=None, raw_phone="050-123-4567", actor=_staff(tenant_id)
        )
        assert repeat.changed is False
        unknown = await service.withdraw_marketing(
            tenant_id, customer_id=None, raw_phone="052-999-8877", actor=_staff(tenant_id)
        )
        assert unknown.changed is False
    finally:
        await engine.dispose()


async def test_a_withdrawal_that_changed_something_writes_exactly_one_audit_row(
    app_role_url: str,
) -> None:
    """`PLATFORM_DPA_HE` publishes to every bride that staff changes to a
    customer's record are written to an activity log. This is one, and it is the
    ONE privacy route a non-owner can reach (Gate 1 Q4) — the widest role
    exposure on the surface.

    Both arms, because the phone arm needs the row MORE: it NULLs
    `queue_tickets.marketing_opt_in_at`, so afterwards the row is
    indistinguishable from a walk-in who never ticked the box and the boutique
    can evidence neither that she asked nor that it complied.

    A REPEAT writes nothing — the guard is `changed`, and the underlying
    statements are self-falsifying — which is what keeps a route a shift manager
    can call 120 times an hour from bloating the one table with no clock.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    walk_in_phone = "+972529998877"
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone
        )
        customer_id = claim.booking.customer_id
        async with tenant_session(factory, tenant_id) as session:
            await CUSTOMERS.record_marketing_consent(session, tenant_id, customer_id)
            await QUEUE_TICKETS.insert(
                session,
                tenant_id=tenant_id,
                queue_day=PAST_DATE,
                name="נועה לוי",
                phone=walk_in_phone,
                visit_type=VisitType.BRIDE.value,
                marketing_opt_in_at=PAST_NOW,
            )
        service = _privacy(factory)

        await service.withdraw_marketing(
            tenant_id, customer_id=customer_id, raw_phone=None, actor=_staff(tenant_id)
        )
        await service.withdraw_marketing(
            tenant_id, customer_id=None, raw_phone=walk_in_phone, actor=_staff(tenant_id)
        )
        # Both repeats change nothing and must therefore leave no trace.
        await service.withdraw_marketing(
            tenant_id, customer_id=customer_id, raw_phone=None, actor=_staff(tenant_id)
        )
        await service.withdraw_marketing(
            tenant_id, customer_id=None, raw_phone=walk_in_phone, actor=_staff(tenant_id)
        )

        rows = [
            row
            for row in await _audit(factory, tenant_id)
            if row.action == AuditAction.PRIVACY_MARKETING_WITHDRAWN.value
        ]
        assert len(rows) == 2
        by_arm = {("customer_id" in row.details): row for row in rows}
        assert by_arm[True].details["customer_id"] == str(customer_id)
        assert by_arm[True].details["phone_last4"] == phone[-4:]
        assert by_arm[False].details["phone_last4"] == walk_in_phone[-4:]
        assert by_arm[False].details["tickets_cleared"] == 1
        # D19's rule, third route: `phone_last4` and never the number, no name.
        written = str([row.details for row in rows])
        assert phone not in written
        assert walk_in_phone not in written
        assert "נועה לוי" not in written
    finally:
        await engine.dispose()


# --- F22: the booking-waitlist ripples (spec D4 — same PR as the migration) ---


async def _join_waitlist(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    phone: str,
    day: datetime.date,
    appointment_type_id: uuid.UUID | None = None,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await WAITLIST.insert(
            session,
            tenant_id=tenant_id,
            day=day,
            appointment_type_id=appointment_type_id or uuid.uuid4(),
            phone=phone,
        )
        return row.id


async def test_the_export_carries_her_waitlist_entries(app_role_url: str) -> None:
    """§13's completeness question, fifth collection point: a phone-bearing
    table absent from the export is a silently incomplete legal answer. Delete
    the `select(WaitlistEntry)` from `export_subject` and this is an empty
    list."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    try:
        type_id = await _seed(factory, tenant_id)
        await _claim(factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone)
        await _join_waitlist(
            factory, tenant_id, phone=phone, day=TARGET_DATE, appointment_type_id=type_id
        )
        await _join_waitlist(factory, tenant_id, phone="+972529998877", day=TARGET_DATE)

        payload = await _privacy(factory).export_subject(
            tenant_id, raw_phone=phone, actor=_staff(tenant_id), reason=None
        )

        assert len(payload.waitlist_entries) == 1
        entry = payload.waitlist_entries[0]
        assert entry.day == TARGET_DATE
        # The type NAME, resolved app-side — the id is boutique bookkeeping and
        # says nothing to the subject or to the regulator reading her file.
        assert entry.appointment_type_name == "מדידה ראשונה"
        assert entry.status == "waiting"
        # D4's enumerated field set, exactly: day, type name, status, created_at.
        # No phone (it is the lookup key), no id, no tenant column.
        assert set(entry.model_dump()) == {
            "day",
            "appointment_type_name",
            "status",
            "created_at",
        }
    finally:
        await engine.dispose()


async def test_the_erase_scrubs_her_waitlist_phone_and_the_row_survives(
    app_role_url: str,
) -> None:
    """The erase's spelling on this table: `phone -> erased:{customer_id}`, the
    row retained as evidence she was on the list. An erased phone can rejoin
    later — new OTP, new entry, new consent context — which is why the scrub
    frees nothing else. The second entry on another number proves the predicate
    is keyed on HER phone rather than draining the tenant's waitlist."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    phone = _phone()
    other_phone = "+972529998877"
    try:
        type_id = await _seed(factory, tenant_id)
        claim = await _claim(
            factory, tenant_id, type_id, starts_at=PAST_SLOT, now=PAST_NOW, phone=phone
        )
        customer_id = claim.booking.customer_id
        hers = await _join_waitlist(
            factory, tenant_id, phone=phone, day=TARGET_DATE, appointment_type_id=type_id
        )
        other = await _join_waitlist(factory, tenant_id, phone=other_phone, day=TARGET_DATE)

        summary = await _privacy(factory).erase_subject(
            tenant_id, customer_id=customer_id, actor=_staff(tenant_id), reason=None
        )

        assert summary.waitlist_entries_scrubbed == 1
        async with tenant_session(factory, tenant_id) as session:
            scrubbed = await session.get(WaitlistEntry, hers)
            untouched = await session.get(WaitlistEntry, other)
            assert scrubbed is not None and untouched is not None
            assert scrubbed.phone == ERASED_PHONE_PREFIX + str(customer_id)
            assert scrubbed.status == "waiting"
            assert scrubbed.deleted_at is None
            assert untouched.phone == other_phone
    finally:
        await engine.dispose()
