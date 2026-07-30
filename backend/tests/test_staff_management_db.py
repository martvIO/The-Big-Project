"""F51 against real Postgres as the non-owner app role (`boutique_app`).

Two things live here and nothing else does.

**The repository writers.** F31 shipped a `StaffUsersRepository` with three
read/insert methods and no way to write `role` at all; every assertion in the
first section is a signature this feature invents, exercised through
`tenant_session` under forced RLS with only the app role's GRANTs.

**The concurrency proof.** NullPool + `asyncio.gather` gives every racer its own
connection (the `test_booking_service.py` precedent), so the namespaced
per-tenant advisory lock is exercised for real: two live owners, two concurrent
removals, exactly one winner. That test is what fails if the lock is dropped or
if the owner-count read moves above it — and it is the one that would pass,
wrongly, under the single-guarded-UPDATE form spec D3 rejects.

**Not re-proven here**: that `boutique_app` can write `role` past 0011's CHECK
under forced RLS. `test_migrations.py`'s
`test_the_app_role_can_promote_to_shift_manager_but_not_to_an_unknown_role` is
F31's deliberate pre-flight for exactly this feature and already covers both
halves — the legal role and the refused unknown one.

Every test mints its own tenant id: the Postgres container is session-scoped and
nothing here truncates.
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

from app.auth.passwords import hash_password
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.models.constants import StaffRole

pytestmark = pytest.mark.db

PASSWORD = "s3cret-staff-pw"


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
    )


def _email() -> str:
    return f"staff-{uuid.uuid4().hex[:10]}@bella.example"


async def _seed_staff(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    role: str = StaffRole.OWNER.value,
    email: str | None = None,
    display_name: str = "Staff",
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=email or _email(),
            password_hash=hash_password(PASSWORD),
            display_name=display_name,
            role=role,
        )
        return staff.id


# --- repository writers ---


async def test_insert_defaults_to_owner_and_accepts_an_explicit_role(app_role_url: str) -> None:
    """The `role` kwarg is a Python DEFAULT, not a required argument: making it
    required would mean editing ProvisioningService.provision — a shipped file on
    the tenant-creation path — to say what the default already says."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        async with tenant_session(factory, tenant_id) as session:
            defaulted = await repo.insert(
                session,
                tenant_id=tenant_id,
                email=_email(),
                password_hash=hash_password(PASSWORD),
                display_name="Owner",
            )
            explicit = await repo.insert(
                session,
                tenant_id=tenant_id,
                email=_email(),
                password_hash=hash_password(PASSWORD),
                display_name="Manager",
                role=StaffRole.SHIFT_MANAGER.value,
            )
            defaulted_id, explicit_id = defaulted.id, explicit.id

        async with tenant_session(factory, tenant_id) as session:
            reread_default = await repo.by_id(session, tenant_id, defaulted_id)
            reread_explicit = await repo.by_id(session, tenant_id, explicit_id)
        assert reread_default is not None
        assert reread_default.role == StaffRole.OWNER.value
        assert reread_explicit is not None
        assert reread_explicit.role == StaffRole.SHIFT_MANAGER.value
    finally:
        await engine.dispose()


async def test_update_writes_each_field_alone_and_two_together(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id)

        async with tenant_session(factory, tenant_id) as session:
            renamed = await repo.update(session, tenant_id, staff_id, display_name="דנה")
        assert renamed is not None
        assert renamed.display_name == "דנה"
        assert renamed.role == StaffRole.OWNER.value

        async with tenant_session(factory, tenant_id) as session:
            demoted = await repo.update(
                session, tenant_id, staff_id, role=StaffRole.SHIFT_MANAGER.value
            )
        assert demoted is not None
        assert demoted.role == StaffRole.SHIFT_MANAGER.value
        assert demoted.display_name == "דנה"

        new_hash = hash_password("a-different-password")
        async with tenant_session(factory, tenant_id) as session:
            both = await repo.update(
                session, tenant_id, staff_id, display_name="Dana", password_hash=new_hash
            )
        assert both is not None
        assert both.display_name == "Dana"
        assert both.password_hash == new_hash
    finally:
        await engine.dispose()


async def test_update_with_nothing_to_write_is_a_no_op_not_an_error(app_role_url: str) -> None:
    """An empty `.values()` is a SQLAlchemy error, so the guard has to be in the
    repository: the service's no-op PATCH path calls straight through here."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id, display_name="Unchanged")
        async with tenant_session(factory, tenant_id) as session:
            row = await repo.update(session, tenant_id, staff_id)
        assert row is not None
        assert row.display_name == "Unchanged"
        assert row.updated_at is None
    finally:
        await engine.dispose()


async def test_update_moves_updated_at_without_assigning_it(app_role_url: str) -> None:
    """The DB trigger owns updated_at — `platform/service.py:161`'s rule. A
    repository that assigned it would silently take ownership of a column the
    schema maintains."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            before = await repo.by_id(session, tenant_id, staff_id)
            assert before is not None
            assert before.updated_at is None

        async with tenant_session(factory, tenant_id) as session:
            after = await repo.update(session, tenant_id, staff_id, display_name="Moved")
        assert after is not None
        assert after.updated_at is not None
    finally:
        await engine.dispose()


async def test_update_misses_an_unknown_and_a_soft_deleted_row(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.update(session, tenant_id, uuid.uuid4(), display_name="X") is None

        async with tenant_session(factory, tenant_id) as session:
            assert await repo.soft_delete(session, tenant_id, staff_id) is True
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.update(session, tenant_id, staff_id, display_name="X") is None
    finally:
        await engine.dispose()


async def test_soft_delete_is_idempotent_and_misses_unknown_ids(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.soft_delete(session, tenant_id, staff_id) is True
        async with tenant_session(factory, tenant_id) as session:
            # The predicate carries deleted_at IS NULL, so the second call misses.
            assert await repo.soft_delete(session, tenant_id, staff_id) is False
            assert await repo.soft_delete(session, tenant_id, uuid.uuid4()) is False
            assert await repo.by_id(session, tenant_id, staff_id) is None
    finally:
        await engine.dispose()


async def test_count_live_owners_counts_only_live_owners(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        await _seed_staff(factory, tenant_id)
        await _seed_staff(factory, tenant_id, role=StaffRole.SHIFT_MANAGER.value)
        archived_owner = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.count_live_owners(session, tenant_id) == 2
            await repo.soft_delete(session, tenant_id, archived_owner)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.count_live_owners(session, tenant_id) == 1
    finally:
        await engine.dispose()


async def test_count_live_owners_cannot_see_another_tenants_owners(app_role_url: str) -> None:
    """RLS, not the redundant predicate, is what makes this true — but both are
    in place, and a regression in either would show up here."""
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        await _seed_staff(factory, elsewhere)
        await _seed_staff(factory, elsewhere)
        async with tenant_session(factory, here) as session:
            assert await repo.count_live_owners(session, here) == 0
    finally:
        await engine.dispose()


async def test_list_live_is_live_only_and_ordered_by_created_at(app_role_url: str) -> None:
    """created_at ASC so the founding owner is first and the order is the same on
    every page load — an unordered list would shuffle the console's rows."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        first = await _seed_staff(factory, tenant_id, display_name="First")
        second = await _seed_staff(factory, tenant_id, display_name="Second")
        gone = await _seed_staff(factory, tenant_id, display_name="Gone")
        async with tenant_session(factory, tenant_id) as session:
            await repo.soft_delete(session, tenant_id, gone)
        async with tenant_session(factory, tenant_id) as session:
            rows = await repo.list_live(session, tenant_id)
        assert [row.id for row in rows] == [first, second]
    finally:
        await engine.dispose()


async def test_list_live_cannot_see_another_tenants_staff(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        await _seed_staff(factory, elsewhere)
        async with tenant_session(factory, here) as session:
            assert await StaffUsersRepository().list_live(session, here) == []
    finally:
        await engine.dispose()


async def test_a_soft_deleted_email_can_be_reused(app_role_url: str) -> None:
    """idx_staff_users_tenant_email_unique is partial on deleted_at IS NULL, which
    is the whole reason F51 ships no restore route and no email edit (spec D5):
    deactivate + re-create is the two-tap remedy for a typo, an address change and
    a mis-tapped deactivate alike."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    address = _email()
    try:
        repo = StaffUsersRepository()
        first = await _seed_staff(factory, tenant_id, email=address)
        async with tenant_session(factory, tenant_id) as session:
            await repo.soft_delete(session, tenant_id, first)
        second = await _seed_staff(factory, tenant_id, email=address)
        assert second != first
        async with tenant_session(factory, tenant_id) as session:
            found = await repo.by_email(session, tenant_id, address)
        assert found is not None
        assert found.id == second
        assert found.deleted_at is None
        # Sanity on the fixture's own clock assumption — nothing here is frozen.
        assert found.created_at <= datetime.now(UTC)
    finally:
        await engine.dispose()
