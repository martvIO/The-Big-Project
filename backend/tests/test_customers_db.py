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

from app.db.repositories.customers import CustomersRepository
from app.db.repositories.message_log import (
    SMS_LOG_LIMIT,
    MessageLogRepository,
    _customer_log_where,
)
from app.db.tenant import tenant_session
from app.models.booking import Booking
from app.models.constants import MessageKind
from app.models.message_log import MessageLog

pytestmark = pytest.mark.db

# A number the boutique actually stores: normalize_israeli_mobile has already
# destroyed the leading 0 a human types, which is the whole reason the phone leg
# runs on phone_search_term(term) rather than on the term.
PHONE_X = "+972501234567"
PHONE_Y = "+972529876543"

CUSTOMERS = CustomersRepository()
MESSAGES = MessageLogRepository()


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
) -> uuid.UUID:
    booking = Booking(
        tenant_id=tenant_id,
        customer_id=customer_id,
        appointment_type_id=uuid.uuid4(),
        starts_at=starts_at,
        seat_index=1,
        terms_version_accepted=1,
        terms_accepted_at=starts_at,
        appointment_type_name="מדידה ראשונה",
    )
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
    full stop — a phone match cannot promote it onto anyone else's page."""
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

        compiled = str(
            select(MessageLog).where(*_customer_log_where(tenant_b, customer_a, PHONE_X)).compile()
        )
        assert "message_log.tenant_id" in compiled
        assert "message_log.booking_id IS NULL" in compiled
    finally:
        await engine.dispose()
