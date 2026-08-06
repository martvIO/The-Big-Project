"""F24's session store against real Postgres as the non-owner app role.

Three things here can be wrong in a way no fast test would catch, and all three
are security properties rather than ergonomics:

* the liveness predicate — a lookup that forgets `expires_at > now` or
  `deleted_at IS NULL` turns logout and expiry into decoration;
* RLS on a brand-new tenant table — the migration is the only thing that binds
  it, and a missing `enable_tenant_rls` call is invisible to every other suite;
* `revoke_all_for_customer`, the statement F20's erase leans on — one missing
  `customer_id` predicate and an erase logs out the whole boutique.

Run as `boutique_app`, never as the container superuser: a superuser bypasses
FORCE ROW LEVEL SECURITY unconditionally, which would make the isolation
assertion vacuously pass. Every test mints its own tenant id — the Postgres
container is session-scoped and nothing here truncates.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db.repositories.customer_sessions import CustomerSessionsRepository
from app.db.repositories.customers import CustomersRepository
from app.db.tenant import tenant_session
from app.models.customer_session import CustomerSession

pytestmark = pytest.mark.db

SESSIONS = CustomerSessionsRepository()
CUSTOMERS = CustomersRepository()


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def test_an_inserted_session_is_found_by_its_token_hash(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id, customer_id = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    try:
        async with tenant_session(factory, tenant_id) as session:
            row = await SESSIONS.insert(
                session,
                tenant_id=tenant_id,
                customer_id=customer_id,
                token_hash="hash-live",
                expires_at=now + timedelta(days=30),
            )
            assert row.id is not None
            found = await SESSIONS.active_by_token_hash(session, tenant_id, "hash-live", now)
            assert found is not None
            assert found.customer_id == customer_id
    finally:
        await engine.dispose()


async def test_an_expired_session_is_not_found(app_role_url: str) -> None:
    """The fixed 30-day TTL is the whole revocation story for a forgotten
    device (spec D2), so this predicate is the control and not a nicety."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    now = datetime.now(UTC)
    try:
        async with tenant_session(factory, tenant_id) as session:
            await SESSIONS.insert(
                session,
                tenant_id=tenant_id,
                customer_id=uuid.uuid4(),
                token_hash="hash-expired",
                expires_at=now - timedelta(seconds=1),
            )
            assert (
                await SESSIONS.active_by_token_hash(session, tenant_id, "hash-expired", now) is None
            )
    finally:
        await engine.dispose()


async def test_a_revoked_session_is_not_found(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    now = datetime.now(UTC)
    try:
        async with tenant_session(factory, tenant_id) as session:
            await SESSIONS.insert(
                session,
                tenant_id=tenant_id,
                customer_id=uuid.uuid4(),
                token_hash="hash-revoked",
                expires_at=now + timedelta(days=30),
            )
            assert await SESSIONS.revoke_by_token_hash(session, tenant_id, "hash-revoked") is True
            assert (
                await SESSIONS.active_by_token_hash(session, tenant_id, "hash-revoked", now) is None
            )
            # The double tap is False, not an error: logout is a button she can
            # press twice and a second press is the same outcome.
            assert await SESSIONS.revoke_by_token_hash(session, tenant_id, "hash-revoked") is False
    finally:
        await engine.dispose()


async def test_one_tenants_sessions_are_invisible_to_another(app_role_url: str) -> None:
    """The house isolation shape: the row is written under tenant B's context
    and read under tenant A's. RLS is what refuses — the repository's explicit
    `tenant_id ==` predicate is defence-in-depth on top of it, which is why
    this test asks for B's id while bound to A."""
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    try:
        async with tenant_session(factory, tenant_b) as session:
            await SESSIONS.insert(
                session,
                tenant_id=tenant_b,
                customer_id=uuid.uuid4(),
                token_hash="hash-cross-tenant",
                expires_at=now + timedelta(days=30),
            )
        async with tenant_session(factory, tenant_a) as session:
            assert (
                await SESSIONS.active_by_token_hash(session, tenant_b, "hash-cross-tenant", now)
                is None
            )
            # And with the RLS context bound to A, even a raw select over the
            # table sees nothing of B's.
            rows = (
                (
                    await session.execute(
                        select(CustomerSession).where(
                            CustomerSession.token_hash == "hash-cross-tenant"
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert list(rows) == []
    finally:
        await engine.dispose()


async def test_revoking_for_one_customer_leaves_her_neighbours_signed_in(
    app_role_url: str,
) -> None:
    """F20's erase calls this. A missing `customer_id` predicate would sign out
    every customer of the boutique on one subject-erase — a bug that looks like
    an outage and reads like a breach."""
    engine, factory = _factory(app_role_url)
    tenant_id, erased, neighbour = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    try:
        async with tenant_session(factory, tenant_id) as session:
            for token, customer_id in (
                ("hers-1", erased),
                ("hers-2", erased),
                ("neighbour", neighbour),
            ):
                await SESSIONS.insert(
                    session,
                    tenant_id=tenant_id,
                    customer_id=customer_id,
                    token_hash=token,
                    expires_at=now + timedelta(days=30),
                )
            revoked = await SESSIONS.revoke_all_for_customer(session, tenant_id, erased)
            assert revoked == 2
            assert await SESSIONS.active_by_token_hash(session, tenant_id, "hers-1", now) is None
            assert await SESSIONS.active_by_token_hash(session, tenant_id, "hers-2", now) is None
            assert (
                await SESSIONS.active_by_token_hash(session, tenant_id, "neighbour", now)
            ) is not None
    finally:
        await engine.dispose()


async def test_set_bell_seen_stamps_the_customer_row(app_role_url: str) -> None:
    """NULL means never opened — the badge counts everything until this runs
    once (spec D6)."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    stamp = datetime.now(UTC)
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await CUSTOMERS.upsert(
                session, tenant_id, phone="+972501110001", name="Rotem"
            )
            assert customer.bell_seen_at is None
            assert await CUSTOMERS.set_bell_seen(session, tenant_id, customer.id, at=stamp) is True
            refreshed = await CUSTOMERS.by_id(session, tenant_id, customer.id)
            assert refreshed is not None
            assert refreshed.bell_seen_at is not None
            # An unknown id is False rather than an exception: the caller is a
            # cookie-authed route whose session row could have been erased
            # between the dependency and the write.
            assert (
                await CUSTOMERS.set_bell_seen(session, tenant_id, uuid.uuid4(), at=stamp) is False
            )
    finally:
        await engine.dispose()
