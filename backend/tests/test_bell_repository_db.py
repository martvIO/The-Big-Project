"""F35's `StaffNotificationsRepository` against real Postgres as the non-owner
app role.

⚠ **Every row this module COMMITS holds `owner` or `shift_manager`, never a
floor role** — `test_sos_repositories.py:3-9`'s rule verbatim: `migrated_db` and
`app_role_url` are session-scoped, pytest collects alphabetically, and a
committed `reception` row reddens three tests in `test_migrations.py` that have
nothing to do with the bell. Nothing here asserts anything about the actor's
role; the bell's audience is all five and that is the router's business.

**`mark_read`'s `at` is a frozen module constant** so the idempotence test can
assert an EQUALITY rather than a range. A test that goes green or red on machine
speed will be re-run until it passes, which is how a mutation regime rots.

Every test mints its own tenant id: the container is session-scoped and nothing
here truncates.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update
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
from app.models.staff_notification import StaffNotification
from app.models.staff_user import StaffUser

pytestmark = pytest.mark.db

MARKED = datetime(2026, 8, 6, 9, 15, tzinfo=UTC)
REMARKED = datetime(2026, 8, 6, 17, 40, tzinfo=UTC)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
    )


async def _seed_staff(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    display_name: str = "Staff",
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=f"bell-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name=display_name,
            role=StaffRole.OWNER.value,
        )
        return staff.id


async def _insert(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    recipient: uuid.UUID,
    actor: uuid.UUID,
    kind: str = StaffNotificationKind.DISPATCH_ASSIGNED.value,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await StaffNotificationsRepository().insert(
            session,
            tenant_id,
            staff_user_id=recipient,
            actor_staff_user_id=actor,
            kind=kind,
            entity_id=uuid.uuid4(),
        )
        return row.id


@pytest.mark.anyio
async def test_a_notification_round_trips_with_its_actor_name(app_role_url: str) -> None:
    """Insert, then read it back through the list. The actor's display name is
    resolved by the join and never copied onto the row — a colleague who is
    renamed is renamed on every notification she ever caused."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        recipient = await _seed_staff(factory, tenant_id, display_name="Rotem")
        actor = await _seed_staff(factory, tenant_id, display_name="Dana Cohen")
        entity = uuid.uuid4()
        async with tenant_session(factory, tenant_id) as session:
            written = await StaffNotificationsRepository().insert(
                session,
                tenant_id,
                staff_user_id=recipient,
                actor_staff_user_id=actor,
                kind=StaffNotificationKind.ROOM_HANDED_OVER.value,
                entity_id=entity,
            )
        assert written.read_at is None

        async with tenant_session(factory, tenant_id) as session:
            rows = await StaffNotificationsRepository().recent(session, tenant_id, recipient)
        assert len(rows) == 1
        assert rows[0].notification.kind == StaffNotificationKind.ROOM_HANDED_OVER.value
        assert rows[0].notification.entity_id == entity
        assert rows[0].actor_name == "Dana Cohen"
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_recent_is_newest_first_and_caps_at_twenty(app_role_url: str) -> None:
    """The cap is HARD and there is no cursor. 25 rows in, 20 out, newest first
    — which is also what the panel's «מוצגות 20 ההתראות האחרונות» note claims on
    screen, so the two must not drift."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        recipient = await _seed_staff(factory, tenant_id)
        actor = await _seed_staff(factory, tenant_id)
        for _ in range(25):
            await _insert(factory, tenant_id, recipient=recipient, actor=actor)

        async with tenant_session(factory, tenant_id) as session:
            rows = await StaffNotificationsRepository().recent(session, tenant_id, recipient)
        assert len(rows) == 20
        stamps = [row.notification.created_at for row in rows]
        assert stamps == sorted(stamps, reverse=True)
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_a_soft_deleted_colleague_still_has_a_name(app_role_url: str) -> None:
    """F37's shipped rule, handed here verbatim: the staff join carries NO
    `deleted_at` filter. A notification that cannot say who dispatched you is
    worse than one naming a colleague who has since left."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        recipient = await _seed_staff(factory, tenant_id)
        actor = await _seed_staff(factory, tenant_id, display_name="Michal")
        await _insert(factory, tenant_id, recipient=recipient, actor=actor)
        async with tenant_session(factory, tenant_id) as session:
            await session.execute(
                update(StaffUser)
                .where(StaffUser.tenant_id == tenant_id, StaffUser.id == actor)
                .values(deleted_at=MARKED)
            )

        async with tenant_session(factory, tenant_id) as session:
            rows = await StaffNotificationsRepository().recent(session, tenant_id, recipient)
        assert rows[0].actor_name == "Michal"
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_a_vanished_actor_row_reads_as_no_name(app_role_url: str) -> None:
    """NULL only when the row is GONE ENTIRELY — the nameless copy variant's one
    trigger. An outer join is what makes the notification survive it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        recipient = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            row = await StaffNotificationsRepository().insert(
                session,
                tenant_id,
                staff_user_id=recipient,
                actor_staff_user_id=uuid.uuid4(),
                kind=StaffNotificationKind.SOS_TARGETED.value,
                entity_id=uuid.uuid4(),
            )
        assert row.id is not None

        async with tenant_session(factory, tenant_id) as session:
            rows = await StaffNotificationsRepository().recent(session, tenant_id, recipient)
        assert len(rows) == 1
        assert rows[0].actor_name is None
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_mark_read_is_idempotent_and_keeps_the_first_timestamp(app_role_url: str) -> None:
    """`WHERE read_at IS NULL` is the whole mechanism. A second mark — a retried
    request, or a row already read on another device — writes nothing, so the
    stamp says when she actually saw it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        recipient = await _seed_staff(factory, tenant_id)
        actor = await _seed_staff(factory, tenant_id)
        first = await _insert(factory, tenant_id, recipient=recipient, actor=actor)

        async with tenant_session(factory, tenant_id) as session:
            remaining = await StaffNotificationsRepository().mark_read(
                session, tenant_id, recipient, [first], at=MARKED
            )
        assert remaining == 0

        async with tenant_session(factory, tenant_id) as session:
            again = await StaffNotificationsRepository().mark_read(
                session, tenant_id, recipient, [first], at=REMARKED
            )
        assert again == 0

        async with tenant_session(factory, tenant_id) as session:
            rows = await StaffNotificationsRepository().recent(session, tenant_id, recipient)
        assert rows[0].notification.read_at == MARKED
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_mark_read_cannot_reach_another_staffers_row(app_role_url: str) -> None:
    """Both predicates on every statement. Handing this verb a colleague's id
    changes nothing and answers HER OWN count — which is the number the bell is
    about to render, so answering the colleague's would be worse than a 404."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        mine = await _seed_staff(factory, tenant_id)
        hers = await _seed_staff(factory, tenant_id)
        actor = await _seed_staff(factory, tenant_id)
        await _insert(factory, tenant_id, recipient=mine, actor=actor)
        her_row = await _insert(factory, tenant_id, recipient=hers, actor=actor)

        async with tenant_session(factory, tenant_id) as session:
            still_mine = await StaffNotificationsRepository().mark_read(
                session, tenant_id, mine, [her_row], at=MARKED
            )
        assert still_mine == 1

        async with tenant_session(factory, tenant_id) as session:
            assert await StaffNotificationsRepository().unread_count(session, tenant_id, hers) == 1
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_unread_count_ignores_read_and_soft_deleted_rows(app_role_url: str) -> None:
    """The count's predicate is `idx_staff_notifications_unread`'s predicate
    character for character (`read_at IS NULL AND deleted_at IS NULL`, keyed by
    tenant and staffer). This count rides the SOS tick on all 18 sections, so a
    predicate that drifts off the index is a cost paid on the emergency
    channel's read."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        recipient = await _seed_staff(factory, tenant_id)
        actor = await _seed_staff(factory, tenant_id)
        unread = await _insert(factory, tenant_id, recipient=recipient, actor=actor)
        read = await _insert(factory, tenant_id, recipient=recipient, actor=actor)
        swept = await _insert(factory, tenant_id, recipient=recipient, actor=actor)
        assert unread != read

        async with tenant_session(factory, tenant_id) as session:
            await StaffNotificationsRepository().mark_read(
                session, tenant_id, recipient, [read], at=MARKED
            )
        async with tenant_session(factory, tenant_id) as session:
            # `deleted_at` has no v1 WRITER; the predicate is still asserted,
            # because the index carries it and the day something sweeps rows the
            # count must already agree with the index.
            await session.execute(
                update(StaffNotification)
                .where(StaffNotification.tenant_id == tenant_id, StaffNotification.id == swept)
                .values(deleted_at=MARKED + timedelta(minutes=1))
            )

        async with tenant_session(factory, tenant_id) as session:
            assert (
                await StaffNotificationsRepository().unread_count(session, tenant_id, recipient)
            ) == 1
    finally:
        await engine.dispose()
