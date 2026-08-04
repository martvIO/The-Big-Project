"""F53's four statements against real Postgres as the non-owner app role.

Everything else in the customers CRM is a screen. These are the reads that can
be *wrong* rather than merely ugly, and one of them can be wrong in the way that
renders one bride's name and appointment time on another bride's page — inside
one tenant, invisible to RLS, invisible to every isolation test in the repo.
That is `MessageLogRepository.list_for_customer`'s phone leg and its
`AND booking_id IS NULL` fence, and `test_a_recycled_phone_surfaces_none_of_the
_prior_holders_lifecycle_rows` is the assertion that fails when the fence goes.

Run as `boutique_app`, never as the container superuser: a superuser bypasses
FORCE ROW LEVEL SECURITY unconditionally, which would make every isolation
assertion here vacuously pass.

Every test mints its own tenant id — the Postgres container is session-scoped
and nothing here truncates.

Two things are deliberately NOT here because they need code F53 has not written
yet, and both belong beside the service that introduces them:
  * the non-disclosure value walk over a real row (`SmsLogRow.model_dump()`
    carries neither `provider_message_id` nor `error`) — `SmsLogRow` does not
    exist until the schemas task;
  * `CustomerNotFoundError` for a cross-tenant detail read — that error is
    raised by the service, not by a repository, which answers `None`.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db.repositories.bookings import BookingsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.message_log import (
    SMS_LOG_LIMIT,
    MessageLogRepository,
    _customer_log_where,
)
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.models.constants import BookingStatus, MessageKind
from app.models.customer import Customer
from app.models.message_log import MessageLog

pytestmark = pytest.mark.db

# A number the boutique actually stores: normalize_israeli_mobile has already
# destroyed the leading 0 a human types, which is the whole reason the phone leg
# runs on phone_search_term(term) rather than on the term.
PHONE_X = "+972501234567"
PHONE_Y = "+972529876543"

CUSTOMERS = CustomersRepository()
MESSAGES = MessageLogRepository()
BOOKINGS = BookingsRepository()


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@contextmanager
def _captured_sql(engine: AsyncEngine) -> Iterator[list[str]]:
    """Every statement Postgres was actually handed, for the assertions whose
    subject is the SQL rather than the rows it returned."""
    statements: list[str] = []

    def record(*args: Any) -> None:
        statements.append(args[2])

    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)


def _where_sql(tenant_id: uuid.UUID, customer_id: uuid.UUID, phone: str) -> str:
    """`_customer_log_where`'s predicate ALONE, never the whole statement.

    `select(MessageLog)` renders every mapped column, so the compiled string
    opens with `SELECT message_log.tenant_id, message_log.phone, …` and a
    substring check against the whole of it is a tautology: "message_log.
    tenant_id" is present whatever the predicate says, including with the tenant
    fence deleted outright. Everything after the first WHERE is the predicate,
    and the only other tenant_id in there is `bookings.tenant_id` inside the
    booking-id subquery — a different table name, so the split is unambiguous.
    """
    compiled = str(
        select(MessageLog).where(*_customer_log_where(tenant_id, customer_id, phone)).compile()
    )
    return compiled.split("WHERE", 1)[1]


async def _seed_customer(
    session: AsyncSession, tenant_id: uuid.UUID, *, phone: str, name: str
) -> uuid.UUID:
    customer = await CUSTOMERS.upsert(session, tenant_id, phone=phone, name=name)
    return customer.id


async def _seed_booking(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    customer_id: uuid.UUID,
    *,
    starts_at: datetime,
    status: str = BookingStatus.CONFIRMED.value,
    appointment_type_name: str = "מדידה ראשונה",
    deleted_at: datetime | None = None,
    booking_id: uuid.UUID | None = None,
) -> uuid.UUID:
    booking = Booking(
        tenant_id=tenant_id,
        customer_id=customer_id,
        appointment_type_id=uuid.uuid4(),
        starts_at=starts_at,
        seat_index=1,
        status=status,
        terms_version_accepted=1,
        terms_accepted_at=starts_at,
        appointment_type_name=appointment_type_name,
        deleted_at=deleted_at,
    )
    # `id` is server_default uuid_generate_v4(), so it is random unless pinned —
    # and a test about ORDER BY id needs it pinned, or the expected order is
    # itself a coin flip.
    if booking_id is not None:
        booking.id = booking_id
    session.add(booking)
    await session.flush()
    return booking.id


def _log_row(
    tenant_id: uuid.UUID,
    *,
    phone: str,
    kind: str = MessageKind.CONFIRMATION.value,
    body: str = "הפגישה שלך אושרה",
    booking_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
    deleted_at: datetime | None = None,
    provider_message_id: str | None = None,
    error: str | None = None,
) -> MessageLog:
    """Constructed, never inserted through `MessageLogRepository.insert`.

    `insert` exposes no `created_at`, and `created_at`'s server default is
    `now()` — which is `transaction_timestamp()` in Postgres and therefore
    IDENTICAL for every row written inside one transaction. Fifty-one rows all
    stamped the same instant make both "newest first" and "which row was
    dropped" coin flips, so the fixtures set it explicitly.
    """
    row = MessageLog(
        tenant_id=tenant_id,
        phone=phone,
        kind=kind,
        body=body,
        booking_id=booking_id,
        provider_message_id=provider_message_id,
        error=error,
        deleted_at=deleted_at,
    )
    if created_at is not None:
        row.created_at = created_at
    return row


# --- search (D2) ---


async def test_search_matches_a_name_and_the_total_counts_only_the_matches(
    app_role_url: str,
) -> None:
    """The name leg runs on the RAW term. The term shares no character with any
    stored phone on purpose: an author who picks a digit string that happens to
    be a substring of the stored E.164 keeps the digit-normalization bug green.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            wanted = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            await _seed_customer(session, tenant_id, phone=PHONE_Y, name="דנה כהן")

        async with tenant_session(factory, tenant_id) as session:
            page = await CUSTOMERS.search(session, tenant_id, q="מיכל", offset=0, limit=20)
            total = await CUSTOMERS.count_search(session, tenant_id, q="מיכל")
        assert [row.id for row in page] == [wanted]
        assert total == 1
    finally:
        await engine.dispose()


@pytest.mark.parametrize("term", ["0501234567", "050-123-4567", "050", "972501234567"])
async def test_a_customer_stored_as_e164_is_found_by_every_local_spelling(
    app_role_url: str, term: str
) -> None:
    """`'+972501234567' ILIKE '%0501234567%'` is FALSE and `%050%` matches
    nothing at all — the stored string contains no 0,5,0 run. These four rows
    red-fail the moment the phone leg runs on the raw term."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            wanted = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            await _seed_customer(session, tenant_id, phone=PHONE_Y, name="דנה כהן")

        async with tenant_session(factory, tenant_id) as session:
            page = await CUSTOMERS.search(session, tenant_id, q=term, offset=0, limit=20)
            total = await CUSTOMERS.count_search(session, tenant_id, q=term)
        assert [row.id for row in page] == [wanted]
        assert total == 1
    finally:
        await engine.dispose()


@pytest.mark.parametrize("wildcard", ["%", "_"])
async def test_a_literal_wildcard_matches_only_the_row_that_contains_it(
    app_role_url: str, wildcard: str
) -> None:
    """`icontains` without `autoescape=True` interpolates the term straight into
    a LIKE pattern, so a typed `%` or `_` returns the WHOLE tenant."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            percent = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל%לוי")
            underscore = await _seed_customer(session, tenant_id, phone=PHONE_Y, name="מיכל_לוי")
            await _seed_customer(session, tenant_id, phone="+972541112222", name="מיכל לוי")

        async with tenant_session(factory, tenant_id) as session:
            page = await CUSTOMERS.search(session, tenant_id, q=wildcard, offset=0, limit=20)
            total = await CUSTOMERS.count_search(session, tenant_id, q=wildcard)
        expected = percent if wildcard == "%" else underscore
        assert [row.id for row in page] == [expected]
        assert total == 1
    finally:
        await engine.dispose()


async def test_a_soft_deleted_customer_is_in_neither_the_page_nor_the_total(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            live = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            gone = await _seed_customer(session, tenant_id, phone=PHONE_Y, name="מיכל כהן")
            removed = await CUSTOMERS.by_id(session, tenant_id, gone)
            assert removed is not None
            removed.deleted_at = datetime.now(UTC)

        async with tenant_session(factory, tenant_id) as session:
            page = await CUSTOMERS.search(session, tenant_id, q="מיכל", offset=0, limit=20)
            total = await CUSTOMERS.count_search(session, tenant_id, q="מיכל")
        assert [row.id for row in page] == [live]
        assert total == 1
    finally:
        await engine.dispose()


async def test_a_blank_term_is_not_a_filter(app_role_url: str) -> None:
    """`q.strip() == ""` drops the predicate entirely. "She cleared the box"
    means "show me everyone", not "search for the empty string"."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            first = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            second = await _seed_customer(session, tenant_id, phone=PHONE_Y, name="דנה כהן")

        async with tenant_session(factory, tenant_id) as session:
            blank = await CUSTOMERS.search(session, tenant_id, q="   ", offset=0, limit=20)
            absent = await CUSTOMERS.search(session, tenant_id, q=None, offset=0, limit=20)
            total = await CUSTOMERS.count_search(session, tenant_id, q="   ")
        assert {row.id for row in blank} == {first, second}
        assert {row.id for row in absent} == {first, second}
        assert total == 2
    finally:
        await engine.dispose()


async def test_order_is_stable_under_offset_for_identically_named_customers(
    app_role_url: str,
) -> None:
    """Two customers named «מיכל לוי» under one boutique is not hypothetical.
    With `ORDER BY name` alone Postgres may return them in either order across
    plans, so page 1 and page 2 can show the same row and hide the other.

    The emitted-SQL half is here because the behavioural half CANNOT pin the
    tiebreak: at two rows on a fresh heap Postgres returns a consistent order
    with or without `customers.id` in the sort, so deleting the tiebreak leaves
    the paging assertions green. Only reading the statement Postgres was
    actually handed fails when it goes.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            one = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            two = await _seed_customer(session, tenant_id, phone=PHONE_Y, name="מיכל לוי")

        with _captured_sql(engine) as emitted:
            async with tenant_session(factory, tenant_id) as session:
                first = await CUSTOMERS.search(session, tenant_id, q="מיכל", offset=0, limit=1)
                second = await CUSTOMERS.search(session, tenant_id, q="מיכל", offset=1, limit=1)
                total = await CUSTOMERS.count_search(session, tenant_id, q="מיכל")
        assert len(first) == 1
        assert len(second) == 1
        assert first[0].id != second[0].id
        assert {first[0].id, second[0].id} == {one, two}
        assert total == 2

        pages = [sql for sql in emitted if "ORDER BY" in sql]
        assert len(pages) == 2
        assert all("ORDER BY customers.name, customers.id" in sql for sql in pages)
    finally:
        await engine.dispose()


# --- notes and tags (D5) ---


async def test_an_untouched_row_reads_tags_as_an_empty_list_and_notes_as_none(
    app_role_url: str,
) -> None:
    """`[]`, never `None`. A nullable array would give "no tags" two spellings
    and make every predicate over it silently three-valued."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer_id = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")

        async with tenant_session(factory, tenant_id) as session:
            fresh = await CUSTOMERS.by_id(session, tenant_id, customer_id)
        assert fresh is not None
        assert fresh.tags == []
        assert fresh.notes is None
    finally:
        await engine.dispose()


async def test_notes_and_tags_round_trip_and_are_cleared_by_empty_values(
    app_role_url: str,
) -> None:
    """`""` and `[]` are VALUES the owner can write, not absence."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer_id = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")

        async with tenant_session(factory, tenant_id) as session:
            written = await CUSTOMERS.set_notes_and_tags(
                session, tenant_id, customer_id, notes="מגיעה עם אמא", tags=["VIP", "כלה"]
            )
        assert written is not None
        assert written.notes == "מגיעה עם אמא"
        assert written.tags == ["VIP", "כלה"]

        async with tenant_session(factory, tenant_id) as session:
            reread = await CUSTOMERS.by_id(session, tenant_id, customer_id)
        assert reread is not None
        assert reread.tags == ["VIP", "כלה"]

        async with tenant_session(factory, tenant_id) as session:
            cleared = await CUSTOMERS.set_notes_and_tags(
                session, tenant_id, customer_id, notes="", tags=[]
            )
        assert cleared is not None
        assert cleared.notes == ""
        assert cleared.tags == []
    finally:
        await engine.dispose()


async def test_only_the_supplied_half_moves_and_supplying_neither_writes_nothing(
    app_role_url: str,
) -> None:
    """`None` means NOT SUPPLIED. A tags-only write must leave notes alone, or
    the console's two independent controls become one destructive one."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer_id = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            await CUSTOMERS.set_notes_and_tags(
                session, tenant_id, customer_id, notes="מגיעה עם אמא", tags=["VIP"]
            )

        async with tenant_session(factory, tenant_id) as session:
            tags_only = await CUSTOMERS.set_notes_and_tags(
                session, tenant_id, customer_id, tags=["כלה"]
            )
        assert tags_only is not None
        assert tags_only.tags == ["כלה"]
        assert tags_only.notes == "מגיעה עם אמא"

        async with tenant_session(factory, tenant_id) as session:
            untouched = await CUSTOMERS.set_notes_and_tags(session, tenant_id, customer_id)
        assert untouched is not None
        assert untouched.tags == ["כלה"]
        assert untouched.notes == "מגיעה עם אמא"
    finally:
        await engine.dispose()


async def test_set_notes_and_tags_answers_none_for_a_customer_of_another_tenant(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_a) as session:
            customer_id = await _seed_customer(session, tenant_a, phone=PHONE_X, name="מיכל לוי")

        async with tenant_session(factory, tenant_b) as session:
            stolen = await CUSTOMERS.set_notes_and_tags(
                session, tenant_b, customer_id, notes="לא שלך"
            )
        assert stolen is None

        async with tenant_session(factory, tenant_a) as session:
            intact = await CUSTOMERS.by_id(session, tenant_a, customer_id)
        assert intact is not None
        assert intact.notes is None
    finally:
        await engine.dispose()


# --- the SMS log (D3) ---


async def test_a_lifecycle_row_survives_a_phone_correction(app_role_url: str) -> None:
    """The BOOKING link attributes it, not the phone. `set_phone` moves
    `customers.phone` and deliberately leaves `message_log` alone — the log is
    evidence of what was actually sent, to what number, at what time."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    starts_at = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer_id = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            booking_id = await _seed_booking(session, tenant_id, customer_id, starts_at=starts_at)
            session.add(_log_row(tenant_id, phone=PHONE_X, booking_id=booking_id))

        async with tenant_session(factory, tenant_id) as session:
            corrected = await CUSTOMERS.set_phone(session, tenant_id, customer_id, phone=PHONE_Y)
        assert corrected is not None

        async with tenant_session(factory, tenant_id) as session:
            rows = await MESSAGES.list_for_customer(session, tenant_id, customer_id, phone=PHONE_Y)
            total = await MESSAGES.count_for_customer(
                session, tenant_id, customer_id, phone=PHONE_Y
            )
        assert [row.booking_id for row in rows] == [booking_id]
        assert total == 1
    finally:
        await engine.dispose()


async def test_the_phone_leg_matches_only_rows_without_a_booking_id(app_role_url: str) -> None:
    """A row that carries a `booking_id` belongs to that booking's customer,
    full stop — a phone match cannot promote it onto anyone else's page.

    Both halves of the fence, and this is where they belong: the rows prove the
    effect for this fixture, and the predicate assertion proves the `AND
    booking_id IS NULL` is in the SQL at all. It moved here from
    `test_two_tenants_sharing_one_phone_stay_isolated`, where deleting the fence
    reddened a test whose name is about TENANT isolation and says nothing about
    attribution inside one."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    starts_at = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    try:
        async with tenant_session(factory, tenant_id) as session:
            mine = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            other = await _seed_customer(session, tenant_id, phone=PHONE_Y, name="דנה כהן")
            other_booking = await _seed_booking(session, tenant_id, other, starts_at=starts_at)
            # Same phone as `mine`, but it belongs to `other`'s booking.
            session.add(_log_row(tenant_id, phone=PHONE_X, booking_id=other_booking))
            session.add(_log_row(tenant_id, phone=PHONE_X, kind=MessageKind.OTP.value))

        async with tenant_session(factory, tenant_id) as session:
            rows = await MESSAGES.list_for_customer(session, tenant_id, mine, phone=PHONE_X)
            total = await MESSAGES.count_for_customer(session, tenant_id, mine, phone=PHONE_X)
        assert [row.kind for row in rows] == [MessageKind.OTP.value]
        assert total == 1
        assert "message_log.booking_id IS NULL" in _where_sql(tenant_id, mine, PHONE_X)
    finally:
        await engine.dispose()


async def test_a_recycled_phone_surfaces_none_of_the_prior_holders_lifecycle_rows(
    app_role_url: str,
) -> None:
    """THE headline assertion of this feature, and the reason this module exists.

    Bride A books on phone X; F16 writes her confirmation and her reminder with
    `booking_id` set and her NAME AND APPOINTMENT TIME in the body. The owner
    corrects A's number to Y — which is the branch invoked precisely when a
    number was MISTYPED, i.e. when it probably belongs to a real other person.
    Bride B then registers on X. Under a phone-only predicate B's screen renders
    A's confirmation bodies: a cross-customer disclosure inside one tenant,
    invisible to RLS because both rows belong to the same boutique.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    starts_at = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
    try:
        async with tenant_session(factory, tenant_id) as session:
            bride_a = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            booking_id = await _seed_booking(session, tenant_id, bride_a, starts_at=starts_at)
            session.add(
                _log_row(
                    tenant_id,
                    phone=PHONE_X,
                    kind=MessageKind.CONFIRMATION.value,
                    body="מיכל לוי, הפגישה שלך נקבעה ל־1.9 בשעה 13:00",
                    booking_id=booking_id,
                )
            )
            session.add(
                _log_row(
                    tenant_id,
                    phone=PHONE_X,
                    kind=MessageKind.REMINDER.value,
                    body="מיכל לוי, תזכורת לפגישה מחר בשעה 13:00",
                    booking_id=booking_id,
                )
            )

        async with tenant_session(factory, tenant_id) as session:
            await CUSTOMERS.set_phone(session, tenant_id, bride_a, phone=PHONE_Y)

        async with tenant_session(factory, tenant_id) as session:
            bride_b = await _seed_customer(session, tenant_id, phone=PHONE_X, name="דנה כהן")

        async with tenant_session(factory, tenant_id) as session:
            b_rows = await MESSAGES.list_for_customer(session, tenant_id, bride_b, phone=PHONE_X)
            b_total = await MESSAGES.count_for_customer(session, tenant_id, bride_b, phone=PHONE_X)
            a_rows = await MESSAGES.list_for_customer(session, tenant_id, bride_a, phone=PHONE_Y)
            a_total = await MESSAGES.count_for_customer(session, tenant_id, bride_a, phone=PHONE_Y)
        assert b_rows == []
        assert b_total == 0
        assert {row.kind for row in a_rows} == {
            MessageKind.CONFIRMATION.value,
            MessageKind.REMINDER.value,
        }
        assert a_total == 2
    finally:
        await engine.dispose()


async def test_an_otp_row_with_no_booking_id_is_included_by_the_phone_leg(
    app_role_url: str,
) -> None:
    """Included, unfiltered. The body is already masked, `message_log` is the
    Spam-Law evidence trail, and for a customer who verified her phone and then
    abandoned the flow the OTP rows are the ONLY evidence anything was sent."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer_id = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            session.add(
                _log_row(
                    tenant_id,
                    phone=PHONE_X,
                    kind=MessageKind.OTP.value,
                    body="קוד האימות שלך: ••••••",
                )
            )

        async with tenant_session(factory, tenant_id) as session:
            rows = await MESSAGES.list_for_customer(session, tenant_id, customer_id, phone=PHONE_X)
            total = await MESSAGES.count_for_customer(
                session, tenant_id, customer_id, phone=PHONE_X
            )
        assert [row.kind for row in rows] == [MessageKind.OTP.value]
        assert total == 1
    finally:
        await engine.dispose()


async def test_an_otp_row_stops_following_a_corrected_phone(app_role_url: str) -> None:
    """The under-report, CHARACTERISED rather than discovered.

    An OTP row has no `booking_id`, so the fence cannot reach it and the phone
    at send time is the only identity it has. After a correction it drops off
    its own customer's log. This is Risk 1's second direction and it is
    ACCEPTED, not a bug to fix here: closing it needs `message_log.customer_id`
    populated at write time plus a backfill that cannot be correct for
    historical rows, because the customer that phone belonged to at send time is
    exactly the thing not recorded.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer_id = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            session.add(_log_row(tenant_id, phone=PHONE_X, kind=MessageKind.OTP.value))

        async with tenant_session(factory, tenant_id) as session:
            await CUSTOMERS.set_phone(session, tenant_id, customer_id, phone=PHONE_Y)

        async with tenant_session(factory, tenant_id) as session:
            rows = await MESSAGES.list_for_customer(session, tenant_id, customer_id, phone=PHONE_Y)
            total = await MESSAGES.count_for_customer(
                session, tenant_id, customer_id, phone=PHONE_Y
            )
        assert rows == []
        assert total == 0
    finally:
        await engine.dispose()


async def test_fifty_one_rows_give_fifty_newest_first_and_a_total_of_fifty_one(
    app_role_url: str,
) -> None:
    """The window is not a bound on the bride's behaviour: OTP rows are written
    by an anonymous endpoint, never carry a `booking_id`, and are always the
    newest. `messages_total` is what keeps "how many messages did you send this
    person" answerable once the fifty-row window truncates.

    The fixture rows carry DISTINCT `created_at` values so "newest first" means
    something — which is also why the `id DESC` tiebreak needs the emitted-SQL
    assertion below rather than a row assertion. The tiebreak exists for rows
    written inside ONE transaction, which all share `transaction_timestamp()`;
    any fixture that reproduces that behaviourally makes the ordering a coin
    flip and the test flaky instead of strict.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    base = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer_id = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            for index in range(SMS_LOG_LIMIT + 1):
                session.add(
                    _log_row(
                        tenant_id,
                        phone=PHONE_X,
                        kind=MessageKind.OTP.value,
                        body=f"הודעה {index}",
                        created_at=base + timedelta(minutes=index),
                    )
                )

        with _captured_sql(engine) as emitted:
            async with tenant_session(factory, tenant_id) as session:
                rows = await MESSAGES.list_for_customer(
                    session, tenant_id, customer_id, phone=PHONE_X
                )
                total = await MESSAGES.count_for_customer(
                    session, tenant_id, customer_id, phone=PHONE_X
                )
        window = [sql for sql in emitted if "ORDER BY" in sql]
        assert len(window) == 1
        assert "ORDER BY message_log.created_at DESC, message_log.id DESC" in window[0]
        assert len(rows) == SMS_LOG_LIMIT
        assert total == SMS_LOG_LIMIT + 1
        assert [row.body for row in rows] == [
            f"הודעה {index}" for index in range(SMS_LOG_LIMIT, 0, -1)
        ]
    finally:
        await engine.dispose()


async def test_a_soft_deleted_log_row_is_in_neither_the_window_nor_the_count(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer_id = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            session.add(_log_row(tenant_id, phone=PHONE_X, kind=MessageKind.OTP.value, body="חיה"))
            session.add(
                _log_row(
                    tenant_id,
                    phone=PHONE_X,
                    kind=MessageKind.OTP.value,
                    body="מחוקה",
                    deleted_at=datetime.now(UTC),
                )
            )

        async with tenant_session(factory, tenant_id) as session:
            rows = await MESSAGES.list_for_customer(session, tenant_id, customer_id, phone=PHONE_X)
            total = await MESSAGES.count_for_customer(
                session, tenant_id, customer_id, phone=PHONE_X
            )
        assert [row.body for row in rows] == ["חיה"]
        assert total == 1
    finally:
        await engine.dispose()


async def test_two_tenants_sharing_one_phone_stay_isolated(app_role_url: str) -> None:
    """`0008_bookings.py:42-45` designs this collision in: the same phone under
    two tenants is two customers, deliberately.

    The compiled-statement half is not decoration. Under `app_role_url` RLS
    already masks a missing `MessageLog.tenant_id ==` predicate, and the fast
    modules issue no SQL at all — so without it the explicit filter can be
    deleted and every suite stays green, right up until a deployment where
    `DATABASE_URL` is unset and `core/config.py:250` hands the app a superuser
    connection that bypasses FORCE RLS.

    It asserts ONE thing, and that thing is cross-tenant. The `booking_id IS
    NULL` assertion that used to sit here is intra-tenant attribution and now
    lives in `test_the_phone_leg_matches_only_rows_without_a_booking_id`, whose
    name is about the fence — so a red here means what the name says.
    """
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_a) as session:
            customer_a = await _seed_customer(session, tenant_a, phone=PHONE_X, name="מיכל לוי")
            session.add(_log_row(tenant_a, phone=PHONE_X, kind=MessageKind.OTP.value, body="של א"))
        async with tenant_session(factory, tenant_b) as session:
            customer_b = await _seed_customer(session, tenant_b, phone=PHONE_X, name="דנה כהן")
            session.add(_log_row(tenant_b, phone=PHONE_X, kind=MessageKind.OTP.value, body="של ב"))

        async with tenant_session(factory, tenant_b) as session:
            rows = await MESSAGES.list_for_customer(session, tenant_b, customer_b, phone=PHONE_X)
            total = await MESSAGES.count_for_customer(session, tenant_b, customer_b, phone=PHONE_X)
        assert [row.body for row in rows] == ["של ב"]
        assert total == 1

        assert "message_log.tenant_id" in _where_sql(tenant_b, customer_a, PHONE_X)
    finally:
        await engine.dispose()


# --- booking history (D4) ---


async def test_the_history_carries_every_status_including_cancelled_newest_first(
    app_role_url: str,
) -> None:
    """The two departures from `list_live_for_customer` are what this pins.

    That method is F15's re-mint feed: it pins `status = 'confirmed'` and
    `starts_at > after`, so reusing it here would show a bride with three past
    cancellations an empty history. Every booking below is in the PAST and one
    of them is cancelled, so a service that reached for the shipped method
    answers `[]` and this test is the thing that says so.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    base = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer_id = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            other_id = await _seed_customer(session, tenant_id, phone=PHONE_Y, name="דנה כהן")
            for index, status in enumerate(
                (
                    BookingStatus.COMPLETED.value,
                    BookingStatus.CANCELLED.value,
                    BookingStatus.NO_SHOW.value,
                    BookingStatus.CONFIRMED.value,
                )
            ):
                await _seed_booking(
                    session,
                    tenant_id,
                    customer_id,
                    starts_at=base + timedelta(days=index),
                    status=status,
                )
            # Same tenant, a different bride: the customer_id predicate is the
            # only thing keeping her appointment off this page.
            await _seed_booking(session, tenant_id, other_id, starts_at=base + timedelta(days=9))

        async with tenant_session(factory, tenant_id) as session:
            rows = await BOOKINGS.list_recent_for_customer(
                session, tenant_id, customer_id=customer_id, limit=10
            )
        assert [row.status for row in rows] == [
            BookingStatus.CONFIRMED.value,
            BookingStatus.NO_SHOW.value,
            BookingStatus.CANCELLED.value,
            BookingStatus.COMPLETED.value,
        ]
        assert [row.starts_at for row in rows] == [
            base + timedelta(days=index) for index in (3, 2, 1, 0)
        ]
    finally:
        await engine.dispose()


async def test_the_history_drops_soft_deleted_rows_and_honours_the_limit(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    base = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer_id = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            await _seed_booking(
                session,
                tenant_id,
                customer_id,
                starts_at=base,
                appointment_type_name="הישנה",
            )
            await _seed_booking(
                session,
                tenant_id,
                customer_id,
                starts_at=base + timedelta(days=1),
                appointment_type_name="האמצעית",
            )
            # The newest by starts_at, and soft-deleted: it must not be the row
            # a limit of one returns.
            await _seed_booking(
                session,
                tenant_id,
                customer_id,
                starts_at=base + timedelta(days=2),
                appointment_type_name="המחוקה",
                deleted_at=datetime.now(UTC),
            )

        async with tenant_session(factory, tenant_id) as session:
            capped = await BOOKINGS.list_recent_for_customer(
                session, tenant_id, customer_id=customer_id, limit=1
            )
            everything = await BOOKINGS.list_recent_for_customer(
                session, tenant_id, customer_id=customer_id, limit=10
            )
        assert [row.appointment_type_name for row in capped] == ["האמצעית"]
        assert [row.appointment_type_name for row in everything] == ["האמצעית", "הישנה"]
    finally:
        await engine.dispose()


async def test_the_history_breaks_a_starts_at_tie_on_id(app_role_url: str) -> None:
    """Three bookings at ONE instant, which is a state the schema designs for
    rather than an artificial one.

    `idx_bookings_tenant_customer_starts_unique` is partial on `WHERE deleted_at
    IS NULL AND status <> 'cancelled'`, and 0009's own comment says why: "a
    customer who cancels can rebook the very same time". So one confirmed row
    plus any number of cancelled ones can share a `starts_at` — and this read
    deliberately includes cancelled rows, so all three land on the panel.

    Under `ORDER BY starts_at DESC` alone the order among them is whatever the
    plan happens to emit, and this method runs under a LIMIT, so a tie at the
    boundary decides which row is DROPPED, not merely where it sits. Both
    siblings in this feature already carry a tiebreak for the same reason —
    `search` orders by (name, id) and `list_for_customer` by (created_at DESC,
    id DESC).

    The ids are MINTED and then sorted rather than written as literals — the
    cluster is session-scoped and nothing here truncates, so a fixed id is a
    `bookings_pkey` collision on the second run. Python compares `UUID.int`
    big-endian and Postgres memcmps the same 16 bytes, so the two agree on the
    order.

    The SEED ORDER IS DECORRELATED FROM THE ID ORDER on purpose, and that is the
    whole difficulty of this test. Today's plan is `Index Scan Backward using
    idx_bookings_tenant_starts`, which walks ties in reverse insertion order —
    so seeding ascending would hand back descending ids with no tiebreak at all
    and the test would pass against the bug it exists to catch. Middle, lowest,
    highest is not any of the orders a plan can produce for free.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    tie = datetime(2026, 3, 1, 11, 0, tzinfo=UTC)
    low, mid, high = sorted(uuid.uuid4() for _ in range(3))
    ids = [low, mid, high]
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer_id = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")
            for index, booking_id in enumerate((mid, low, high)):
                await _seed_booking(
                    session,
                    tenant_id,
                    customer_id,
                    starts_at=tie,
                    # Only ONE of the three may be non-cancelled: the partial
                    # unique index admits the tie precisely because a cancelled
                    # row is outside it.
                    status=(
                        BookingStatus.CONFIRMED.value
                        if index == 1
                        else BookingStatus.CANCELLED.value
                    ),
                    booking_id=booking_id,
                )
            # A later booking, to prove the tiebreak is SECONDARY — starts_at
            # still decides first.
            newest = await _seed_booking(
                session,
                tenant_id,
                customer_id,
                starts_at=tie + timedelta(days=1),
                status=BookingStatus.CANCELLED.value,
            )

        async with tenant_session(factory, tenant_id) as session:
            rows = await BOOKINGS.list_recent_for_customer(
                session, tenant_id, customer_id=customer_id, limit=10
            )
            # The tie sits ON the limit boundary: without a total order, which
            # of the three is dropped here is undefined.
            capped = await BOOKINGS.list_recent_for_customer(
                session, tenant_id, customer_id=customer_id, limit=3
            )
        assert [row.id for row in rows] == [newest, ids[2], ids[1], ids[0]]
        assert [row.id for row in capped] == [newest, ids[2], ids[1]]
    finally:
        await engine.dispose()


# --- F20: the four privacy consent columns (A2) ---


async def test_the_four_consent_columns_round_trip_as_aware_utc_and_default_to_absent(
    app_role_url: str,
) -> None:
    """The ORM mapping against the real column types, which is the one thing
    neither the migration test nor a metadata assertion can see: a `TIMESTAMPTZ`
    mapped as a naive `datetime` reads back with no tzinfo, and every retention
    clock and every "was this consent live when we sent?" comparison in F20 is
    arithmetic on these three values.

    The untouched half is the other assertion. NULL is the ONLY spelling of "no
    consent on record" (D6) — consent is the presence of a timestamp, so a
    default on any of these would make the absent state unreachable and, on
    `marketing_consent_at`, would consent every existing bride in one word.

    `updated_at` is not written here on purpose: it is the DB trigger's, and this
    file's other tests would notice if it were not.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    consented = datetime(2026, 3, 1, 9, 30, tzinfo=UTC)
    withdrawn = datetime(2026, 4, 2, 11, 15, tzinfo=UTC)
    erased = datetime(2026, 5, 3, 13, 45, tzinfo=UTC)
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer_id = await _seed_customer(session, tenant_id, phone=PHONE_X, name="מיכל לוי")

        async with tenant_session(factory, tenant_id) as session:
            untouched = await CUSTOMERS.by_id(session, tenant_id, customer_id)
        assert untouched is not None
        assert untouched.marketing_consent_at is None
        assert untouched.marketing_consent_source is None
        assert untouched.marketing_consent_withdrawn_at is None
        assert untouched.erased_at is None

        async with tenant_session(factory, tenant_id) as session:
            row = await session.get(Customer, customer_id)
            assert row is not None
            row.marketing_consent_at = consented
            # The literal, not an enum: `customers_marketing_consent_source_check`
            # is the source of truth and test_migrations pins it. The enum lands
            # with A7's `record_marketing_consent`, which is the only writer.
            row.marketing_consent_source = "booking_form"
            row.marketing_consent_withdrawn_at = withdrawn
            row.erased_at = erased

        async with tenant_session(factory, tenant_id) as session:
            fresh = await CUSTOMERS.by_id(session, tenant_id, customer_id)
        assert fresh is not None
        assert fresh.marketing_consent_at == consented
        assert fresh.marketing_consent_withdrawn_at == withdrawn
        assert fresh.erased_at == erased
        assert fresh.marketing_consent_source == "booking_form"
        # Equality above holds for a naive datetime too, once asyncpg has applied
        # the session TZ. tzinfo is what actually distinguishes the mapping.
        assert fresh.marketing_consent_at.tzinfo is not None
        assert fresh.marketing_consent_withdrawn_at.tzinfo is not None
        assert fresh.erased_at.tzinfo is not None
    finally:
        await engine.dispose()
