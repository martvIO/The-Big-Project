"""Every retention policy against real Postgres, as `boutique_app`.

Run as the non-owner application role, never as the container superuser: a
superuser bypasses FORCE ROW LEVEL SECURITY unconditionally, which would make
the isolation assertion here vacuously pass — and it would also hide the thing
`test_retention_policies.py`'s exemption walk is really about. That walk is a
cheap early signal; the GRANT is the enforcement, and only this file can feel it.

Every clock boundary is asserted HERE and in both directions, because a policy's
clock is a SQL predicate: a fast test could only recompute the same arithmetic in
Python and compare Python to Python, which stays green with the predicate gone.

Every test mints its own tenant id — the cluster is session-scoped and nothing
here truncates.
"""

import datetime
import uuid
from collections.abc import Sequence
from typing import Any

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.db.repositories.tenants import TenantsRepository
from app.db.tenant import tenant_session
from app.models.audit_log import AuditLog
from app.models.booking import Booking
from app.models.constants import ScheduledMessageKind
from app.models.customer import Customer
from app.models.message_log import MessageLog
from app.models.otp_code import OtpCode
from app.models.queue_ticket import QueueTicket
from app.models.scheduled_message import ScheduledMessage
from app.models.session import Session as SessionRow
from app.models.terms_version import TermsVersion
from app.privacy.retention import CHUNK_SIZE, POLICIES, RetentionRunner, _purge
from app.privacy.validation import ERASED_NAME, ERASED_PHONE_PREFIX

pytestmark = pytest.mark.db

SETTINGS = Settings(app_env="dev")
NOW = datetime.datetime(2026, 8, 4, 12, 0, tzinfo=datetime.UTC)
DAY = datetime.timedelta(days=1)

POLICY_BY_NAME = {policy.name: policy for policy in POLICIES}


def _factory(app_role_url: str) -> tuple[Any, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _apply(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    policy_name: str,
    *,
    now: datetime.datetime = NOW,
    limit: int = CHUNK_SIZE,
    dry_run: bool = False,
) -> int:
    policy = POLICY_BY_NAME[policy_name]
    async with tenant_session(factory, tenant_id) as session:
        return await policy.run(
            session, tenant_id, now=now, settings=SETTINGS, limit=limit, dry_run=dry_run
        )


async def _add(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, *rows: Any) -> None:
    async with tenant_session(factory, tenant_id) as session:
        for row in rows:
            session.add(row)


async def _ids(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, model: type[Any]
) -> set[uuid.UUID]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(model.id).where(model.tenant_id == tenant_id)
        return set((await session.execute(stmt)).scalars().all())


async def _rows(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, model: type[Any]
) -> Sequence[Any]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(model).where(model.tenant_id == tenant_id).order_by(model.created_at)
        return list((await session.execute(stmt)).scalars().all())


def _customer(tenant_id: uuid.UUID, *, age_days: float, phone: str, **kwargs: Any) -> Customer:
    return Customer(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        phone=phone,
        name="מיכל לוי",
        created_at=NOW - datetime.timedelta(days=age_days),
        **kwargs,
    )


def _booking(
    tenant_id: uuid.UUID, customer_id: uuid.UUID, *, starts_at: datetime.datetime
) -> Booking:
    return Booking(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        customer_id=customer_id,
        appointment_type_id=uuid.uuid4(),
        starts_at=starts_at,
        seat_index=1,
        terms_version_accepted=1,
        terms_accepted_at=starts_at,
        appointment_type_name="מדידה",
    )


def _ticket(tenant_id: uuid.UUID, *, age_days: int, **kwargs: Any) -> QueueTicket:
    return QueueTicket(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        queue_day=(NOW - datetime.timedelta(days=age_days)).date(),
        name="נועה",
        phone="+972501234567",
        visit_type="bride",
        **kwargs,
    )


# --- 1. otp_codes -----------------------------------------------------------


async def test_otp_codes_are_purged_at_exactly_the_two_ttls_and_not_before(
    app_role_url: str,
) -> None:
    """15 minutes is `OTP_TTL_SECONDS + VERIFICATION_TOKEN_TTL_SECONDS` with ZERO
    margin. The boundary is asserted in both directions because the safe side of
    it is a platform-wide outage: a code purged while still verifiable makes
    every booking in the tenant uncompletable, with no error anywhere."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        rows = {
            label: OtpCode(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                phone="+972501234567",
                code_hash=label,
                expires_at=NOW,
                created_at=NOW - datetime.timedelta(seconds=age),
            )
            for label, age in {"fresh": 5 * 60, "boundary": 900, "stale": 16 * 60}.items()
        }
        await _add(factory, tenant_id, *rows.values())

        assert await _apply(factory, tenant_id, "otp_codes") == 2
        assert await _ids(factory, tenant_id, OtpCode) == {rows["fresh"].id}
    finally:
        await engine.dispose()


# --- 2. sessions ------------------------------------------------------------


async def test_sessions_go_when_expired_or_revoked_and_a_live_one_stays(
    app_role_url: str,
) -> None:
    """No new setting: `session_ttl_seconds` already wrote `expires_at`. A
    revoked (soft-deleted) row goes too — it is dead by definition, and its
    `token_hash` is the only thing on it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        live = SessionRow(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            staff_user_id=uuid.uuid4(),
            token_hash="live",
            expires_at=NOW + datetime.timedelta(seconds=1),
        )
        expired = SessionRow(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            staff_user_id=uuid.uuid4(),
            token_hash="expired",
            expires_at=NOW,
        )
        revoked = SessionRow(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            staff_user_id=uuid.uuid4(),
            token_hash="revoked",
            expires_at=NOW + datetime.timedelta(days=1),
            deleted_at=NOW - DAY,
        )
        await _add(factory, tenant_id, live, expired, revoked)

        assert await _apply(factory, tenant_id, "sessions") == 2
        assert await _ids(factory, tenant_id, SessionRow) == {live.id}
    finally:
        await engine.dispose()


# --- 3. queue_tickets -------------------------------------------------------


async def test_a_queue_ticket_past_its_week_is_scrubbed_and_a_recent_one_is_not(
    app_role_url: str,
) -> None:
    """DR-11. The scrub is what makes F33's shipped public promise true, and it
    is a PLACEHOLDER rather than a NULL because `name` and `phone` are both
    `nullable=False` — which is also what makes the predicate self-falsifying."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        recent = _ticket(tenant_id, age_days=2)
        boundary = _ticket(tenant_id, age_days=7)
        old = _ticket(tenant_id, age_days=8)
        await _add(factory, tenant_id, recent, boundary, old)

        assert await _apply(factory, tenant_id, "queue_tickets") == 2

        by_id = {row.id: row for row in await _rows(factory, tenant_id, QueueTicket)}
        assert by_id[recent.id].name == "נועה"
        assert by_id[recent.id].phone == "+972501234567"
        for scrubbed in (by_id[boundary.id], by_id[old.id]):
            assert scrubbed.name == ERASED_NAME
            assert scrubbed.phone == f"{ERASED_PHONE_PREFIX}{scrubbed.id}"
            # Both columns are NOT NULL — a scrub that reached for NULL would
            # have raised rather than merely written the wrong thing.
            assert scrubbed.name is not None and scrubbed.phone is not None
    finally:
        await engine.dispose()


async def test_an_opted_in_queue_ticket_is_scrubbed_like_any_other(app_role_url: str) -> None:
    """The assertion that PINS DR-11's blocker resolution instead of leaving it
    in prose. The shipped notice promised to keep an opted-in walk-in's name and
    phone "until she asks to remove the consent" — i.e. with no clock at all, in
    a store no send path reads. That promise was made in the boutique's
    commercial favour, not as a subject protection, and it is dropped. What she
    is entitled to — the ability to revoke — is built as the `phone` arm on
    marketing-withdraw.

    `marketing_opt_in_at` survives the scrub: it is a consent fact, not contact
    detail, and the row it sits on no longer names anyone.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        opted_in = _ticket(tenant_id, age_days=30, marketing_opt_in_at=NOW - 30 * DAY)
        await _add(factory, tenant_id, opted_in)

        assert await _apply(factory, tenant_id, "queue_tickets") == 1

        row = (await _rows(factory, tenant_id, QueueTicket))[0]
        assert row.name == ERASED_NAME
        assert row.phone.startswith(ERASED_PHONE_PREFIX)
        assert row.marketing_opt_in_at is not None
    finally:
        await engine.dispose()


# --- 4. message_log ---------------------------------------------------------


async def test_message_log_is_purged_at_twenty_four_months(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        rows = {
            label: MessageLog(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                phone="+972501234567",
                kind="reminder",
                body=label,
                status="sent",
                created_at=NOW - datetime.timedelta(days=age),
            )
            for label, age in {"young": 729, "boundary": 730, "old": 731}.items()
        }
        await _add(factory, tenant_id, *rows.values())

        assert await _apply(factory, tenant_id, "message_log") == 2
        assert await _ids(factory, tenant_id, MessageLog) == {rows["young"].id}
    finally:
        await engine.dispose()


# --- 5. bookings + scheduled_messages ---------------------------------------


async def test_a_seven_year_old_booking_goes_with_its_scheduled_messages(
    app_role_url: str,
) -> None:
    """Same batch, from the id set the page already materialised — an orphan
    sweep over `scheduled_messages` was declined as an anti-join per tick to
    reach rows the booking purge already knows the ids of."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        customer = _customer(tenant_id, age_days=2600, phone="+972501234567")
        old = _booking(tenant_id, customer.id, starts_at=NOW - datetime.timedelta(days=365 * 7 + 1))
        recent = _booking(tenant_id, customer.id, starts_at=NOW - DAY)
        await _add(factory, tenant_id, customer, old, recent)
        await _add(
            factory,
            tenant_id,
            *[
                ScheduledMessage(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    booking_id=booking.id,
                    kind=ScheduledMessageKind.REMINDER.value,
                    send_after=booking.starts_at,
                )
                for booking in (old, recent)
            ],
        )

        assert await _apply(factory, tenant_id, "bookings") == 1

        assert await _ids(factory, tenant_id, Booking) == {recent.id}
        survivors = await _rows(factory, tenant_id, ScheduledMessage)
        assert [row.booking_id for row in survivors] == [recent.id]
    finally:
        await engine.dispose()


async def test_the_booking_page_limit_is_in_the_sql_not_a_python_slice(
    app_role_url: str,
) -> None:
    """Three due bookings and a limit of two: exactly two go. A LIMIT applied
    after an unbounded read would pass every assertion about WHICH rows go and
    still let one tenant's seven-year backlog be materialised in memory."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        customer = _customer(tenant_id, age_days=2600, phone="+972501234567")
        doomed = [
            _booking(tenant_id, customer.id, starts_at=NOW - datetime.timedelta(days=365 * 7 + n))
            for n in (1, 2, 3)
        ]
        await _add(factory, tenant_id, customer, *doomed)

        assert await _apply(factory, tenant_id, "bookings", limit=2) == 2
        assert len(await _ids(factory, tenant_id, Booking)) == 1
        assert await _apply(factory, tenant_id, "bookings", limit=2) == 1
        assert await _ids(factory, tenant_id, Booking) == set()
    finally:
        await engine.dispose()


# --- 6. customers -----------------------------------------------------------


async def test_the_customer_scrub_feeds_on_the_orphans_the_booking_purge_made(
    app_role_url: str,
) -> None:
    """Registry order, proved end to end rather than asserted on a tuple: before
    the booking purge the customer is not orphaned and the scrub finds nothing;
    after it, she is and it does."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        customer = _customer(tenant_id, age_days=2600, phone="+972501234567", notes="מידות")
        booking = _booking(
            tenant_id, customer.id, starts_at=NOW - datetime.timedelta(days=365 * 7 + 1)
        )
        await _add(factory, tenant_id, customer, booking)

        assert await _apply(factory, tenant_id, "customers") == 0
        assert await _apply(factory, tenant_id, "bookings") == 1
        assert await _apply(factory, tenant_id, "customers") == 1

        row = (await _rows(factory, tenant_id, Customer))[0]
        assert row.name == ERASED_NAME
        assert row.phone == f"{ERASED_PHONE_PREFIX}{row.id}"
        # DR-12: `customers.notes` accretes across a year of fittings. An
        # "erasure" that anonymises the name and leaves the paragraph about her
        # is not an erasure.
        assert row.notes is None
        assert row.tags == []
        assert row.erased_at is not None
    finally:
        await engine.dispose()


async def test_a_customer_with_a_live_booking_is_never_scrubbed(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        customer = _customer(tenant_id, age_days=400, phone="+972501234567")
        await _add(factory, tenant_id, customer, _booking(tenant_id, customer.id, starts_at=NOW))

        assert await _apply(factory, tenant_id, "customers") == 0
        assert (await _rows(factory, tenant_id, Customer))[0].name == "מיכל לוי"
    finally:
        await engine.dispose()


async def test_the_thirty_day_orphan_grace_is_a_real_undo_window(app_role_url: str) -> None:
    """NOT padding. A customer row is only ever created inside `create_booking`,
    so the sole way one is orphaned early is F15's phone correction re-pointing
    a booking at an existing row. Without the grace, a mistaken correction is
    anonymised within the hour and unrecoverable."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        young = _customer(tenant_id, age_days=29, phone="+972501111111")
        boundary = _customer(tenant_id, age_days=30, phone="+972502222222")
        old = _customer(tenant_id, age_days=31, phone="+972503333333")
        await _add(factory, tenant_id, young, boundary, old)

        assert await _apply(factory, tenant_id, "customers") == 2

        by_id = {row.id: row for row in await _rows(factory, tenant_id, Customer)}
        assert by_id[young.id].name == "מיכל לוי"
        assert by_id[boundary.id].name == ERASED_NAME
        assert by_id[old.id].name == ERASED_NAME
    finally:
        await engine.dispose()


async def test_two_orphans_in_one_chunk_are_both_scrubbed_without_a_unique_violation(
    app_role_url: str,
) -> None:
    """`idx_customers_tenant_phone_unique` is UNIQUE on (tenant_id, phone), and
    this policy is the path that touches MANY rows at once. A constant
    placeholder makes the second row in a chunk raise, rolls the whole chunk
    back, and repeats that failure on every tick for every tenant past the clock
    — permanently. The endpoint's own two-erasures test cannot reach this path."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        orphans = [_customer(tenant_id, age_days=60, phone=f"+97250000{n:04d}") for n in range(3)]
        await _add(factory, tenant_id, *orphans)

        assert await _apply(factory, tenant_id, "customers") == 3

        rows = await _rows(factory, tenant_id, Customer)
        phones = {row.phone for row in rows}
        assert len(phones) == 3
        assert all(row.phone == f"{ERASED_PHONE_PREFIX}{row.id}" for row in rows)
    finally:
        await engine.dispose()


# --- cross-cutting ----------------------------------------------------------


async def test_a_policy_touches_nothing_of_another_tenants(app_role_url: str) -> None:
    """RLS is the containment, not the WHERE clause — the explicit `tenant_id`
    predicate is defense-in-depth beside it. This asserts the pair holds for a
    job that HARD-DELETES, which is the one place cross-tenant leakage is
    unrecoverable."""
    engine, factory = _factory(app_role_url)
    a, b = uuid.uuid4(), uuid.uuid4()
    try:
        for tenant_id in (a, b):
            await _add(
                factory,
                tenant_id,
                OtpCode(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    phone="+972501234567",
                    code_hash="x",
                    expires_at=NOW,
                    created_at=NOW - datetime.timedelta(hours=1),
                ),
                _ticket(tenant_id, age_days=30),
            )

        assert await _apply(factory, a, "otp_codes") == 1
        assert await _apply(factory, a, "queue_tickets") == 1

        assert len(await _ids(factory, b, OtpCode)) == 1
        assert (await _rows(factory, b, QueueTicket))[0].name == "נועה"
    finally:
        await engine.dispose()


async def test_a_dry_run_counts_the_work_and_writes_nothing(app_role_url: str) -> None:
    """How an operator inspects the first run against real data before trusting
    the scheduled one. The count is deliberately UNLIMITED — a dry run consumes
    no rows, so a chunk loop over it would report the same page 50 times."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        await _add(
            factory,
            tenant_id,
            *[_ticket(tenant_id, age_days=30) for _ in range(3)],
        )

        assert await _apply(factory, tenant_id, "queue_tickets", limit=2, dry_run=True) == 3
        assert [row.name for row in await _rows(factory, tenant_id, QueueTicket)] == ["נועה"] * 3

        assert await _apply(factory, tenant_id, "queue_tickets") == 3
    finally:
        await engine.dispose()


async def test_the_grant_is_what_enforces_the_exemption_list(app_role_url: str) -> None:
    """`test_retention_policies.py`'s walk over `policy.tables` is the cheap early
    signal. THIS is the enforcement: a policy naming one of the four
    DELETE-revoked tables does not merely fail review, it cannot execute at all.

    `terms_versions` stands for the four. It is append-only by GRANT (0005:126)
    because every booking pins a version, and a purge would destroy the terms a
    customer actually agreed to.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        with pytest.raises(ProgrammingError, match="permission denied"):
            async with tenant_session(factory, tenant_id) as session:
                await _purge(
                    session,
                    TermsVersion,
                    [TermsVersion.tenant_id == tenant_id],
                    limit=1,
                    dry_run=False,
                )
    finally:
        await engine.dispose()


async def test_the_app_role_can_still_read_that_table(app_role_url: str) -> None:
    """The anti-vacuity leg for the test above: `permission denied` must be about
    DELETE and not about the table being unreachable altogether."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            assert (
                await session.execute(text("SELECT count(*) FROM terms_versions"))
            ).scalar_one() == 0
    finally:
        await engine.dispose()


# --- D22: every policy's predicate is falsified by its own action -------------
#
# `POLICY_FIXTURES` is keyed by `policy.name` and the KEY SET IS ASSERTED EQUAL to
# the registry FIRST. That ordering is the whole design. The plan's first draft
# said only "a second consecutive run touches zero rows, as a loop over POLICIES",
# and the honest answer to "what single-line deletion makes that red?" was NONE:
# for any policy whose fixture happened to match nothing, run 1 returns 0, run 2
# returns 0, and the assertion passes. One shared fixture across six tables with
# clocks from 15 minutes to 7 years will not match all six. `first > 0` is what
# arms it, and the key-set equality is what makes "a policy added later is covered
# without editing this test" true rather than merely hoped for.


async def _fixture_otp_codes(factory: Any, tenant_id: uuid.UUID) -> None:
    await _add(
        factory,
        tenant_id,
        OtpCode(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            phone="+972501234567",
            code_hash="x",
            expires_at=NOW,
            created_at=NOW - datetime.timedelta(hours=1),
        ),
    )


async def _fixture_sessions(factory: Any, tenant_id: uuid.UUID) -> None:
    await _add(
        factory,
        tenant_id,
        SessionRow(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            staff_user_id=uuid.uuid4(),
            token_hash="dead",
            expires_at=NOW - DAY,
        ),
    )


async def _fixture_queue_tickets(factory: Any, tenant_id: uuid.UUID) -> None:
    await _add(factory, tenant_id, _ticket(tenant_id, age_days=30))


async def _fixture_message_log(factory: Any, tenant_id: uuid.UUID) -> None:
    await _add(
        factory,
        tenant_id,
        MessageLog(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            phone="+972501234567",
            kind="reminder",
            body="שלום",
            status="sent",
            created_at=NOW - datetime.timedelta(days=800),
        ),
    )


async def _fixture_bookings(factory: Any, tenant_id: uuid.UUID) -> None:
    await _add(
        factory,
        tenant_id,
        _booking(tenant_id, uuid.uuid4(), starts_at=NOW - datetime.timedelta(days=365 * 8)),
    )


async def _fixture_customers(factory: Any, tenant_id: uuid.UUID) -> None:
    await _add(factory, tenant_id, _customer(tenant_id, age_days=90, phone="+972504444444"))


POLICY_FIXTURES = {
    "otp_codes": _fixture_otp_codes,
    "sessions": _fixture_sessions,
    "queue_tickets": _fixture_queue_tickets,
    "message_log": _fixture_message_log,
    "bookings": _fixture_bookings,
    "customers": _fixture_customers,
}


def test_every_registered_policy_has_a_self_consumption_fixture() -> None:
    """A policy added without a fixture is a FAILURE, not a silent pass. Without
    this the loop below would simply not cover it, which is exactly the vacuum
    that made the first draft's version of D22 unfalsifiable."""
    assert set(POLICY_FIXTURES) == {policy.name for policy in POLICIES}


@pytest.mark.parametrize("policy_name", [policy.name for policy in POLICIES])
async def test_a_second_consecutive_run_touches_zero_rows(
    app_role_url: str, policy_name: str
) -> None:
    """The invariant F38's staff SCRUB inherits, which is why it lives on the
    registry rather than in one policy's comment.

    ACCEPTANCE, stated so it can be checked rather than believed: deleting
    `Customer.erased_at.is_(None)` from the customers policy must turn the
    `customers` case RED, and deleting `QueueTicket.name != ERASED_NAME` must
    turn the `queue_tickets` case RED. Both were run; both did.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        await POLICY_FIXTURES[policy_name](factory, tenant_id)

        first = await _apply(factory, tenant_id, policy_name)
        second = await _apply(factory, tenant_id, policy_name)

        assert first > 0, "the fixture matched nothing — the invariant would be vacuous"
        assert second == 0
    finally:
        await engine.dispose()


async def test_a_second_customers_run_leaves_erased_at_byte_identical(
    app_role_url: str,
) -> None:
    """The consequence the count alone cannot show. For a §14 subject whose
    bookings have since been purged, `erased_at` is the PROOF of her erasure —
    and the first draft overwrote it hourly."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        await _add(factory, tenant_id, _customer(tenant_id, age_days=90, phone="+972505555555"))

        assert await _apply(factory, tenant_id, "customers") == 1
        stamped = (await _rows(factory, tenant_id, Customer))[0].erased_at

        later = NOW + datetime.timedelta(days=1)
        assert await _apply(factory, tenant_id, "customers", now=later) == 0
        assert (await _rows(factory, tenant_id, Customer))[0].erased_at == stamped
    finally:
        await engine.dispose()


# --- the runner against real Postgres ---------------------------------------
#
# Deliberately driven with a POLICY SUBSET. `list_all()` reaches every tenant in
# this session-scoped cluster, including the ones other db modules created, so a
# full-registry run here would hard-delete their rows out from under them. The
# subset is chosen so that only rows THIS test aged can qualify.


def _runner(factory: Any, policies: tuple[Any, ...]) -> RetentionRunner:
    return RetentionRunner(
        factory,
        settings=SETTINGS,
        clock=lambda: NOW,
        policies=policies,
    )


async def _audit_rows(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> list[AuditLog]:
    async with tenant_session(factory, tenant_id) as session:
        stmt = select(AuditLog).where(AuditLog.tenant_id == tenant_id)
        return list((await session.execute(stmt)).scalars().all())


async def test_the_runner_writes_one_audit_row_for_the_policy_that_touched_rows(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"ret-{uuid.uuid4().hex[:8]}", name="Retention")
        await _add(factory, tenant.id, _ticket(tenant.id, age_days=30))

        result = await _runner(
            factory, (POLICY_BY_NAME["queue_tickets"], POLICY_BY_NAME["customers"])
        ).run()

        assert result.failed_tenants == 0
        assert result.rows["queue_tickets"] >= 1

        rows = await _audit_rows(factory, tenant.id)
        assert [row.action for row in rows] == ["retention_queue_tickets"]
        assert rows[0].entity == "queue_tickets"
        assert rows[0].details == {
            "rows": 1,
            "action": "scrub",
            "tables": ["queue_tickets"],
        }
        # No name, no phone: audit_log has no retention class and platform
        # operators read across tenants.
        assert "נועה" not in str(rows[0].details)
    finally:
        await engine.dispose()


async def test_a_dry_run_against_real_postgres_writes_neither_data_nor_evidence(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"dry-{uuid.uuid4().hex[:8]}", name="Dry run")
        await _add(factory, tenant.id, _ticket(tenant.id, age_days=30))

        result = await _runner(factory, (POLICY_BY_NAME["queue_tickets"],)).run(dry_run=True)

        assert result.rows["queue_tickets"] >= 1
        assert (await _rows(factory, tenant.id, QueueTicket))[0].name == "נועה"
        assert await _audit_rows(factory, tenant.id) == []
    finally:
        await engine.dispose()


async def test_a_suspended_and_an_offboarded_boutiques_clocks_still_run(
    app_role_url: str,
) -> None:
    """D21, end to end. Under `list_active()` these two tenants' rows were never
    reachable at all — which made "nothing is ever deleted" permanently true for
    precisely the boutiques most likely to hold abandoned data, and made
    suspension a way to opt out of a duty the platform enforces on the
    controller's behalf."""
    engine, factory = _factory(app_role_url)
    tenants = TenantsRepository(factory)
    try:
        suspended = await tenants.insert(slug=f"sus-{uuid.uuid4().hex[:8]}", name="Suspended")
        offboarded = await tenants.insert(slug=f"off-{uuid.uuid4().hex[:8]}", name="Off-boarded")
        for tenant in (suspended, offboarded):
            await _add(factory, tenant.id, _ticket(tenant.id, age_days=30))
        assert await tenants.suspend(suspended.id) is True
        assert await tenants.soft_delete(offboarded.id) is True

        await _runner(factory, (POLICY_BY_NAME["queue_tickets"],)).run()

        for tenant in (suspended, offboarded):
            assert (await _rows(factory, tenant.id, QueueTicket))[0].name == ERASED_NAME
    finally:
        await engine.dispose()
