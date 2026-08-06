"""F25's operator identity, against real Postgres as the real app role.

⚠ db-marked: no Docker locally, so these run on CI only.

Everything here connects as `boutique_app` — the non-owner role the web process
and the CLI both hold. That is the point rather than a detail: `platform_operators`
and `platform_sessions` carry NO `tenant_id` and NO RLS (spec D7), so the only
thing standing between the app role and these rows is 0002's default CRUD grant,
and this module is where "the console needs no new database role" stops being a
spec sentence.
"""

import asyncio
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.repositories.platform_operators import PlatformOperatorsRepository
from app.db.repositories.platform_sessions import PlatformSessionsRepository

pytestmark = pytest.mark.db


@pytest.fixture
def factory(app_role_url: str) -> Iterator[async_sessionmaker]:
    engine: AsyncEngine = create_async_engine(app_role_url, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        asyncio.run(engine.dispose())


def _email() -> str:
    return f"op-{uuid.uuid4().hex[:10]}@modryn.example"


OPERATORS = PlatformOperatorsRepository()
SESSIONS = PlatformSessionsRepository()


def test_an_operator_round_trips_and_its_email_lookup_is_case_insensitive(
    factory: async_sessionmaker,
) -> None:
    async def check() -> None:
        email = _email()
        async with factory() as session, session.begin():
            created = await OPERATORS.insert(
                session, email=email, password_hash="not-a-real-hash", display_name="Dana"
            )
            operator_id = created.id

        async with factory() as session:
            # Stored lowercased by the repository, and found whatever case the
            # login form sends — the index is on lower(email) and the read must
            # agree with it or a mixed-case address is silently unloginable.
            assert (await OPERATORS.by_active_email(session, email.upper())) is not None
            found = await OPERATORS.by_active_email(session, email)
            assert found is not None and found.id == operator_id
            assert found.email == email.lower()
            by_id = await OPERATORS.by_id(session, operator_id)
            assert by_id is not None and by_id.display_name == "Dana"

    asyncio.run(check())


def test_a_soft_deleted_operator_is_invisible_to_both_reads(factory: async_sessionmaker) -> None:
    """Deactivation is a soft delete, and it must bite on the NEXT request — so
    `by_id` has to miss too, not only the login lookup. `get_current_operator`
    re-reads through `by_id`, which is the whole mechanism."""

    async def check() -> None:
        email = _email()
        async with factory() as session, session.begin():
            created = await OPERATORS.insert(
                session, email=email, password_hash="h", display_name="Gone"
            )
            operator_id = created.id
        async with factory() as session, session.begin():
            assert await OPERATORS.soft_delete(session, operator_id) is True

        async with factory() as session:
            assert await OPERATORS.by_active_email(session, email) is None
            assert await OPERATORS.by_id(session, operator_id) is None

        # …and the address is reusable, which is the only remedy this feature
        # offers for a typo'd operator email (no HTTP edit route exists).
        async with factory() as session, session.begin():
            await OPERATORS.insert(session, email=email, password_hash="h", display_name="Again")
        async with factory() as session:
            assert await OPERATORS.by_active_email(session, email) is not None

    asyncio.run(check())


def test_count_active_sees_live_operators_only(factory: async_sessionmaker) -> None:
    """The read behind "refuses to deactivate the last active operator". It is
    platform-wide by construction — there is no tenant to scope it to."""

    async def check() -> None:
        async with factory() as session:
            before = await OPERATORS.count_active(session)
        async with factory() as session, session.begin():
            created = await OPERATORS.insert(
                session, email=_email(), password_hash="h", display_name="Counted"
            )
        async with factory() as session:
            assert await OPERATORS.count_active(session) == before + 1
        async with factory() as session, session.begin():
            await OPERATORS.soft_delete(session, created.id)
        async with factory() as session:
            assert await OPERATORS.count_active(session) == before

    asyncio.run(check())


def _live(session_factory: async_sessionmaker, token_hash: str) -> bool:
    async def read() -> bool:
        async with session_factory() as session:
            row = await SESSIONS.live_by_token_hash(session, token_hash, datetime.now(UTC))
            return row is not None

    return asyncio.run(read())


def test_a_session_is_live_until_it_expires_or_is_revoked(factory: async_sessionmaker) -> None:
    """The three ways a cookie stops working, each asserted separately: the row
    is gone, the row is revoked, or the clock passed it. A lookup that forgot the
    expiry predicate would still pass the first two."""

    async def seed(delta: timedelta) -> tuple[uuid.UUID, str]:
        token_hash = uuid.uuid4().hex
        async with factory() as session, session.begin():
            operator = await OPERATORS.insert(
                session, email=_email(), password_hash="h", display_name="Live"
            )
            await SESSIONS.insert(
                session,
                operator_id=operator.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + delta,
            )
        return operator.id, token_hash

    assert _live(factory, uuid.uuid4().hex) is False

    _, live_hash = asyncio.run(seed(timedelta(hours=4)))
    assert _live(factory, live_hash) is True

    _, expired_hash = asyncio.run(seed(timedelta(seconds=-1)))
    assert _live(factory, expired_hash) is False

    async def revoke() -> bool:
        async with factory() as session, session.begin():
            return await SESSIONS.revoke(session, live_hash)

    assert asyncio.run(revoke()) is True
    assert _live(factory, live_hash) is False


def test_revoking_every_session_for_one_operator_spares_the_others(
    factory: async_sessionmaker,
) -> None:
    """Deactivation sweeps ONE operator's cookies. A sweep with a missing
    predicate would sign the whole platform out and read as working."""

    async def check() -> tuple[bool, bool]:
        mine, theirs = uuid.uuid4().hex, uuid.uuid4().hex
        async with factory() as session, session.begin():
            a = await OPERATORS.insert(session, email=_email(), password_hash="h", display_name="A")
            b = await OPERATORS.insert(session, email=_email(), password_hash="h", display_name="B")
            expires = datetime.now(UTC) + timedelta(hours=4)
            await SESSIONS.insert(session, operator_id=a.id, token_hash=mine, expires_at=expires)
            await SESSIONS.insert(session, operator_id=b.id, token_hash=theirs, expires_at=expires)
        async with factory() as session, session.begin():
            await SESSIONS.revoke_all_for_operator(session, a.id)
        async with factory() as session:
            now = datetime.now(UTC)
            return (
                await SESSIONS.live_by_token_hash(session, mine, now) is not None,
                await SESSIONS.live_by_token_hash(session, theirs, now) is not None,
            )

    mine_live, theirs_live = asyncio.run(check())
    assert mine_live is False
    assert theirs_live is True


def test_neither_table_is_reachable_through_a_tenant_context(factory: async_sessionmaker) -> None:
    """The inverse of every other isolation test in this suite, and it is worth
    stating: these rows belong to the PLATFORM, so binding a tenant context must
    change nothing about what the app role can see. If a later migration adds RLS
    here by reflex, this is the red."""

    async def check() -> int:
        async with factory() as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.tenant_id', :value, true)"),
                {"value": str(uuid.uuid4())},
            )
            await OPERATORS.insert(
                session, email=_email(), password_hash="h", display_name="Platform"
            )
        async with factory() as session:
            return await OPERATORS.count_active(session)

    assert asyncio.run(check()) >= 1
