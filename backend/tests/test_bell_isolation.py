"""`staff_notifications` in the permanent cross-tenant isolation suite.

⚠ **Connected ONLY as the non-owner `boutique_app` role, over a `NullPool`
engine, via the `app_role_url` fixture — NEVER `migrated_db`.** The container
superuser bypasses RLS and every GRANT unconditionally, so a suite pointed at it
passes vacuously while proving nothing.

**Every probe hands a repository the FOREIGN tenant id**, which is the only shape
that reads as an RLS probe here. `StaffNotificationsRepository` spells an
explicit `tenant_id ==` on every statement, so a probe passing its OWN tenant id
and asserting the list is short would stay green with the policy dropped — it
would be asserting the redundant predicate, not the policy. `test_sos_isolation.py`
records that same mutation catching that same mistake one feature ago.

**Why this table earns a file rather than one more row in
`test_tenant_isolation.py`'s scan.** The scan proves the POLICY exists. What it
cannot prove is that the reads the product runs are the ones carrying it — and
`recent` LEFT JOINs `staff_users`, which is exactly where a missing policy hides,
because the driving table is filtered while the joined one is not and the row
COUNT stays identical. So the list read is probed on its JOINED COLUMN.

**And the count read is app-level.** It rides the SOS tick on all 18 sections
every few seconds for the whole shift, so a cross-tenant leak in it would be
continuous rather than occasional.
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db.repositories.staff_notifications import StaffNotificationsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.models.constants import StaffNotificationKind, StaffRole

pytestmark = pytest.mark.db

AT = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
    )


async def _seed_tenant_with_one_notification(
    factory: async_sessionmaker[AsyncSession], display_name: str
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A tenant, its recipient, and one unread row. Returns the ids a foreign
    caller would have to guess — and which, guessed correctly, must still yield
    nothing."""
    tenant_id = uuid.uuid4()
    async with tenant_session(factory, tenant_id) as session:
        recipient = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=f"bell-iso-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name=display_name,
            role=StaffRole.OWNER.value,
        )
    async with tenant_session(factory, tenant_id) as session:
        row = await StaffNotificationsRepository().insert(
            session,
            tenant_id,
            staff_user_id=recipient.id,
            actor_staff_user_id=recipient.id,
            kind=StaffNotificationKind.DISPATCH_ASSIGNED.value,
            entity_id=uuid.uuid4(),
        )
    return tenant_id, recipient.id, row.id


@pytest.mark.anyio
async def test_no_bell_reader_crosses_a_tenant(app_role_url: str) -> None:
    """A's connection, B's tenant id, B's staffer id — every id correct, and all
    three reads still see nothing. This is the probe that reds if
    `enable_tenant_rls("staff_notifications")` is ever dropped from the
    migration."""
    engine, factory = _factory(app_role_url)
    try:
        tenant_a = uuid.uuid4()
        tenant_b, her_staff_id, her_row_id = await _seed_tenant_with_one_notification(
            factory, "Bella B"
        )
        assert tenant_a != tenant_b

        # A's session variable, B's tenant id passed to every repository call.
        async with tenant_session(factory, tenant_a) as session:
            repo = StaffNotificationsRepository()
            assert await repo.unread_count(session, tenant_b, her_staff_id) == 0
            assert await repo.recent(session, tenant_b, her_staff_id) == []
            # The write is a read probe too: the UPDATE matches nothing and the
            # count it answers is computed under the same policy.
            assert await repo.mark_read(session, tenant_b, her_staff_id, [her_row_id], at=AT) == 0

        # And B's row is untouched — an intruder's mark must not clear her bell.
        async with tenant_session(factory, tenant_b) as session:
            assert (
                await StaffNotificationsRepository().unread_count(session, tenant_b, her_staff_id)
            ) == 1
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_the_actor_join_does_not_leak_a_foreign_colleagues_name(app_role_url: str) -> None:
    """The join probe, and it asserts a JOINED COLUMN rather than a length.

    Both tenants get a staffer with the SAME id is impossible, so instead: A's
    own notification names an actor id that also exists in B. Reading it from A
    must resolve A's name or NULL, never B's — a join missing its `tenant_id`
    predicate would produce B's row while keeping A's row count identical.
    """
    engine, factory = _factory(app_role_url)
    try:
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        async with tenant_session(factory, tenant_b) as session:
            foreign_actor = await StaffUsersRepository().insert(
                session,
                tenant_id=tenant_b,
                email=f"bell-iso-{uuid.uuid4().hex[:10]}@bella.example",
                password_hash="not-a-real-hash",
                display_name="Foreign Colleague",
                role=StaffRole.OWNER.value,
            )
        async with tenant_session(factory, tenant_a) as session:
            mine = await StaffUsersRepository().insert(
                session,
                tenant_id=tenant_a,
                email=f"bell-iso-{uuid.uuid4().hex[:10]}@bella.example",
                password_hash="not-a-real-hash",
                display_name="Mine",
                role=StaffRole.OWNER.value,
            )
        async with tenant_session(factory, tenant_a) as session:
            await StaffNotificationsRepository().insert(
                session,
                tenant_a,
                staff_user_id=mine.id,
                actor_staff_user_id=foreign_actor.id,
                kind=StaffNotificationKind.SOS_TARGETED.value,
                entity_id=uuid.uuid4(),
            )

        async with tenant_session(factory, tenant_a) as session:
            rows = await StaffNotificationsRepository().recent(session, tenant_a, mine.id)
        assert len(rows) == 1
        assert rows[0].actor_name is None
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_a_connection_with_no_tenant_context_sees_nothing(app_role_url: str) -> None:
    """`current_setting(..., true)` yields NULL with no context set, so the
    policy fails CLOSED. A connection that forgot `tenant_session` reads zero
    rows rather than everything."""
    engine, factory = _factory(app_role_url)
    try:
        tenant_id, staff_id, _ = await _seed_tenant_with_one_notification(factory, "Bella")
        async with factory() as session:
            repo = StaffNotificationsRepository()
            assert await repo.unread_count(session, tenant_id, staff_id) == 0
            assert await repo.recent(session, tenant_id, staff_id) == []
    finally:
        await engine.dispose()
