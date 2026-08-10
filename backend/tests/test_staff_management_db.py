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

**The route half is sync `def`, deliberately.** asyncio_mode="auto" would give an
async test its own loop and TestClient starts a second one inside it, so seeding
for those tests goes through asyncio.run and every engine is NullPool — the
test_staff_role_gating_integration rule. The service-level tests above them are
plain async, because no TestClient is involved.

Every test mints its own tenant id: the Postgres container is session-scoped and
nothing here truncates.
"""

import asyncio
import time
import uuid
from datetime import UTC, date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.passwords import hash_password, verify_password
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import AuthService, StaffContext
from app.auth.staff import (
    DuplicateEmailError,
    LastOwnerRequiredError,
    StaffNotFoundError,
    StaffSelfManageError,
    StaffService,
)
from app.boutique.service import BoutiqueSettingsService
from app.core.config import Settings
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.fitting_rooms import FittingRoomsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.tenant import tenant_session
from app.errors import DomainValidationError
from app.main import NOT_AUTHENTICATED_BODY, NOT_AUTHORIZED_BODY, create_app
from app.models.alteration_ticket import AlterationTicket
from app.models.audit_log import AuditLog
from app.models.constants import AuditAction, StaffRole
from app.models.fitting_room import FittingRoom
from app.models.fitting_room_assignment import FittingRoomAssignment
from app.models.sos_alert import SosAlert
from app.tenancy.resolver import RepositoryTenantResolver

# F38 made `last_day` a REQUIRED argument on StaffUsersRepository.soft_delete —
# the retention policy's predicate needs `last_day IS NOT NULL`, so a row
# offboarded without one is a person the platform can never scrub, and a default
# would have made forgetting it silent. This module only ever soft-deletes a
# staffer to set up a fixture, so any past date does; naming it says so.
_LEFT_ON = date(2026, 1, 31)


class _NoBucket:
    """An unconfigured storage port. Every test in this module offboards a
    staffer who has no photo, so the only member offboarding could reach is
    `delete_object` on an empty key list — i.e. never. `is_configured` answers
    False so that if a test ever DOES give someone a photo, the read path
    degrades to `photo_url: null` rather than reaching for credentials that do
    not exist in CI."""

    @property
    def is_configured(self) -> bool:
        return False

    async def delete_object(self, *, key: str) -> None:  # pragma: no cover
        raise AssertionError("this module offboards nobody with a photo")


_NO_BUCKET = _NoBucket()


pytestmark = pytest.mark.db

PASSWORD = "s3cret-staff-pw"
SETTINGS = Settings(app_env="dev", session_ttl_seconds=3600)


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
            assert await repo.soft_delete(session, tenant_id, staff_id, last_day=_LEFT_ON) is True
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
            assert await repo.soft_delete(session, tenant_id, staff_id, last_day=_LEFT_ON) is True
        async with tenant_session(factory, tenant_id) as session:
            # The predicate carries deleted_at IS NULL, so the second call misses.
            assert await repo.soft_delete(session, tenant_id, staff_id, last_day=_LEFT_ON) is False
            assert (
                await repo.soft_delete(session, tenant_id, uuid.uuid4(), last_day=_LEFT_ON) is False
            )
            assert await repo.by_id(session, tenant_id, staff_id) is None
    finally:
        await engine.dispose()


async def test_insert_and_update_write_f38s_three_hr_fields(app_role_url: str) -> None:
    """`phone`, `start_date` and `shift_manager_eligible` against real columns.

    Both writers, because they disagree on purpose. `insert` defaults all three
    so ProvisioningService.provision — a shipped file on the tenant-creation
    path — needs no edit; `update` reads `None` as "not sent" and `""` as
    "clear it", the one spelling that can ever remove a number. The hand-written
    fake in test_staff_service.py cannot prove either against a real
    nullable/NOT NULL pair, or that `boutique_app` may write them at all."""
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
                display_name="Defaulted",
            )
            filled = await repo.insert(
                session,
                tenant_id=tenant_id,
                email=_email(),
                password_hash=hash_password(PASSWORD),
                display_name="Filled",
                phone="050-1234567",
                start_date=date(2026, 3, 1),
                shift_manager_eligible=True,
            )
            defaulted_id, filled_id = defaulted.id, filled.id

        async with tenant_session(factory, tenant_id) as session:
            blank = await repo.by_id(session, tenant_id, defaulted_id)
            written = await repo.by_id(session, tenant_id, filled_id)
        assert blank is not None
        # NOT NULL with a server default on the boolean; the other two are null.
        assert (blank.phone, blank.start_date, blank.shift_manager_eligible) == (None, None, False)
        assert written is not None
        assert written.phone == "050-1234567"
        assert written.start_date == date(2026, 3, 1)
        assert written.shift_manager_eligible is True

        async with tenant_session(factory, tenant_id) as session:
            moved = await repo.update(
                session,
                tenant_id,
                filled_id,
                phone="050-7654321",
                start_date=date(2026, 4, 1),
                shift_manager_eligible=False,
            )
        assert moved is not None
        assert moved.phone == "050-7654321"
        assert moved.start_date == date(2026, 4, 1)
        assert moved.shift_manager_eligible is False

        # "" removes the number and leaves everything else where it was.
        async with tenant_session(factory, tenant_id) as session:
            cleared = await repo.update(session, tenant_id, filled_id, phone="")
        assert cleared is not None
        assert cleared.phone is None
        assert cleared.start_date == date(2026, 4, 1)
    finally:
        await engine.dispose()


async def test_the_photo_triples_pend_promote_idempotently_and_clear(app_role_url: str) -> None:
    """The two-transaction confirm dance, against the database it was written for.

    Three things only real Postgres can answer. `promote_pending_photo` assigns
    COLUMN TO COLUMN (`photo_key = photo_pending_key`) under a
    `photo_pending_key IS NOT NULL` guard — SQL the fake in test_staff_service.py
    reproduces by hand and therefore cannot falsify. That guard is what makes a
    retried confirm after a lost response a no-op returning `None` rather than a
    second promotion that blanks the live triple it just wrote. And `boutique_app`
    has never written any of these six columns under forced RLS before this test.

    The replace half is the middle block: `set_pending_photo` must leave the LIVE
    triple alone, which is the whole reason there are two triples — the photo on
    the board keeps rendering while an upload is in flight."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = StaffUsersRepository()
        staff_id = await _seed_staff(factory, tenant_id)
        first_at = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)

        async with tenant_session(factory, tenant_id) as session:
            assert (
                await repo.set_pending_photo(
                    session,
                    tenant_id,
                    staff_id,
                    storage_key="tenants/t/staff/s/photo/one.jpg",
                    content_type="image/jpeg",
                    at=first_at,
                )
                is True
            )
        async with tenant_session(factory, tenant_id) as session:
            pending = await repo.by_id(session, tenant_id, staff_id)
        assert pending is not None
        assert pending.photo_pending_key == "tenants/t/staff/s/photo/one.jpg"
        assert pending.photo_pending_content_type == "image/jpeg"
        assert pending.photo_pending_at == first_at
        # Presign writes ONLY the pending triple.
        assert pending.photo_key is None
        assert pending.photo_confirmed_at is None

        confirmed_at = datetime(2026, 8, 1, 9, 5, tzinfo=UTC)
        async with tenant_session(factory, tenant_id) as session:
            promoted = await repo.promote_pending_photo(
                session, tenant_id, staff_id, at=confirmed_at
            )
        assert promoted is not None
        assert promoted.photo_key == "tenants/t/staff/s/photo/one.jpg"
        assert promoted.photo_content_type == "image/jpeg"
        assert promoted.photo_confirmed_at == confirmed_at
        assert promoted.photo_pending_key is None
        assert promoted.photo_pending_content_type is None
        assert promoted.photo_pending_at is None

        # The retry after a lost response: nothing to promote, and — the point —
        # the live triple it already wrote is still standing.
        async with tenant_session(factory, tenant_id) as session:
            assert (
                await repo.promote_pending_photo(
                    session, tenant_id, staff_id, at=datetime(2026, 8, 1, 9, 6, tzinfo=UTC)
                )
                is None
            )
        async with tenant_session(factory, tenant_id) as session:
            after_retry = await repo.by_id(session, tenant_id, staff_id)
        assert after_retry is not None
        assert after_retry.photo_key == "tenants/t/staff/s/photo/one.jpg"
        assert after_retry.photo_confirmed_at == confirmed_at

        # REPLACE: the old photo stays visible for the whole upload window.
        async with tenant_session(factory, tenant_id) as session:
            await repo.set_pending_photo(
                session,
                tenant_id,
                staff_id,
                storage_key="tenants/t/staff/s/photo/two.png",
                content_type="image/png",
                at=datetime(2026, 8, 2, 9, 0, tzinfo=UTC),
            )
        async with tenant_session(factory, tenant_id) as session:
            replacing = await repo.by_id(session, tenant_id, staff_id)
        assert replacing is not None
        assert replacing.photo_key == "tenants/t/staff/s/photo/one.jpg"
        assert replacing.photo_pending_key == "tenants/t/staff/s/photo/two.png"

        # clear_photo is unconditional and takes BOTH halves, so a delete racing
        # a confirm cannot leave the pending half behind.
        async with tenant_session(factory, tenant_id) as session:
            cleared = await repo.clear_photo(session, tenant_id, staff_id)
        assert cleared is not None
        assert cleared.photo_key is None
        assert cleared.photo_content_type is None
        assert cleared.photo_confirmed_at is None
        assert cleared.photo_pending_key is None
        assert cleared.photo_pending_content_type is None
        assert cleared.photo_pending_at is None

        async with tenant_session(factory, tenant_id) as session:
            assert await repo.clear_photo(session, tenant_id, uuid.uuid4()) is None
            assert (
                await repo.set_pending_photo(
                    session,
                    tenant_id,
                    uuid.uuid4(),
                    storage_key="k",
                    content_type="image/jpeg",
                    at=first_at,
                )
                is False
            )
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
            await repo.soft_delete(session, tenant_id, archived_owner, last_day=_LEFT_ON)
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
            await repo.soft_delete(session, tenant_id, gone, last_day=_LEFT_ON)
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
            await repo.soft_delete(session, tenant_id, first, last_day=_LEFT_ON)
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


# --- the service under real concurrency: the last-owner race ---


def _actor(staff_id: uuid.UUID, tenant_id: uuid.UUID) -> StaffContext:
    return StaffContext(
        id=staff_id,
        tenant_id=tenant_id,
        email="acting@bella.example",
        display_name="Acting",
        role=StaffRole.OWNER.value,
    )


async def test_two_concurrent_removals_of_two_owners_leave_exactly_one(
    app_role_url: str,
) -> None:
    """**The headline.** Two live owners, each removing the other at the same
    instant. NullPool gives every racer its own connection, so the advisory lock
    is exercised for real.

    This is the test that fails if the lock is dropped or if the count read moves
    above it — and, crucially, the one that would pass WRONGLY under the single
    guarded `UPDATE … WHERE (SELECT count(*) …) > 1` form spec D3 rejects: under
    READ COMMITTED both statements see 2, both commit, and the tenant silently
    ends with zero owners.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        service = StaffService(
            factory,
            media_storage=_NO_BUCKET,  # type: ignore[arg-type]
            presign_rate_limiter=FixedWindowRateLimiter(
                max_attempts=50, window_seconds=900, clock=time.monotonic
            ),
        )
        first = await _seed_staff(factory, tenant_id, role=StaffRole.OWNER.value)
        second = await _seed_staff(factory, tenant_id, role=StaffRole.OWNER.value)

        results = await asyncio.gather(
            service.deactivate(tenant_id, second, actor=_actor(first, tenant_id)),
            service.deactivate(tenant_id, first, actor=_actor(second, tenant_id)),
            return_exceptions=True,
        )
        winners = [r for r in results if not isinstance(r, BaseException)]
        losers = [r for r in results if isinstance(r, LastOwnerRequiredError)]
        assert len(winners) == 1, f"expected one winner, got {results!r}"
        assert len(losers) == 1, f"expected one LastOwnerRequiredError, got {results!r}"

        async with tenant_session(factory, tenant_id) as session:
            assert await StaffUsersRepository().count_live_owners(session, tenant_id) == 1
    finally:
        await engine.dispose()


async def test_a_deactivation_racing_a_demotion_also_leaves_exactly_one(
    app_role_url: str,
) -> None:
    """The cross-operation half. Whichever commits first, the loser's post-lock
    count read sees the winner's write — which is the entire reason the read is
    inside the lock rather than beside it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        service = StaffService(
            factory,
            media_storage=_NO_BUCKET,  # type: ignore[arg-type]
            presign_rate_limiter=FixedWindowRateLimiter(
                max_attempts=50, window_seconds=900, clock=time.monotonic
            ),
        )
        first = await _seed_staff(factory, tenant_id, role=StaffRole.OWNER.value)
        second = await _seed_staff(factory, tenant_id, role=StaffRole.OWNER.value)

        results = await asyncio.gather(
            service.deactivate(tenant_id, second, actor=_actor(first, tenant_id)),
            service.update(
                tenant_id,
                first,
                role=StaffRole.SHIFT_MANAGER.value,
                actor=_actor(second, tenant_id),
            ),
            return_exceptions=True,
        )
        losers = [r for r in results if isinstance(r, LastOwnerRequiredError)]
        assert len(losers) == 1, f"expected one LastOwnerRequiredError, got {results!r}"

        async with tenant_session(factory, tenant_id) as session:
            assert await StaffUsersRepository().count_live_owners(session, tenant_id) == 1
    finally:
        await engine.dispose()


# --- the service against real Postgres: guards, duplicates, audit, RLS ---


async def test_a_duplicate_live_email_is_409_on_the_pre_check(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        service = StaffService(
            factory,
            media_storage=_NO_BUCKET,  # type: ignore[arg-type]
            presign_rate_limiter=FixedWindowRateLimiter(
                max_attempts=50, window_seconds=900, clock=time.monotonic
            ),
        )
        owner = await _seed_staff(factory, tenant_id, role=StaffRole.OWNER.value)
        address = _email()
        await service.create(
            tenant_id,
            email=address,
            display_name="First",
            role=StaffRole.SHIFT_MANAGER.value,
            password=PASSWORD,
            actor=_actor(owner, tenant_id),
        )
        with pytest.raises(DuplicateEmailError):
            await service.create(
                tenant_id,
                email=address,
                display_name="Second",
                role=StaffRole.SHIFT_MANAGER.value,
                password=PASSWORD,
                actor=_actor(owner, tenant_id),
            )
    finally:
        await engine.dispose()


async def test_a_duplicate_live_email_is_409_on_the_integrity_backstop(
    app_role_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pre-check RACES; the partial unique index is the real authority. With
    the pre-check monkeypatched away, the raw IntegrityError must still surface as
    a clean 409 and never as a 500 — the create_booking pattern."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        service = StaffService(
            factory,
            media_storage=_NO_BUCKET,  # type: ignore[arg-type]
            presign_rate_limiter=FixedWindowRateLimiter(
                max_attempts=50, window_seconds=900, clock=time.monotonic
            ),
        )
        owner = await _seed_staff(factory, tenant_id, role=StaffRole.OWNER.value)
        address = _email()
        await service.create(
            tenant_id,
            email=address,
            display_name="First",
            role=StaffRole.SHIFT_MANAGER.value,
            password=PASSWORD,
            actor=_actor(owner, tenant_id),
        )

        async def _blind(
            self: StaffUsersRepository, session: object, tenant_id: uuid.UUID, email: str
        ) -> None:
            return None

        monkeypatch.setattr(StaffUsersRepository, "by_email", _blind)
        with pytest.raises(DuplicateEmailError):
            await service.create(
                tenant_id,
                email=address,
                display_name="Second",
                role=StaffRole.SHIFT_MANAGER.value,
                password=PASSWORD,
                actor=_actor(owner, tenant_id),
            )
    finally:
        await engine.dispose()


async def test_the_self_guard_refuses_and_writes_nothing(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        service = StaffService(
            factory,
            media_storage=_NO_BUCKET,  # type: ignore[arg-type]
            presign_rate_limiter=FixedWindowRateLimiter(
                max_attempts=50, window_seconds=900, clock=time.monotonic
            ),
        )
        me = await _seed_staff(factory, tenant_id, role=StaffRole.OWNER.value)
        await _seed_staff(factory, tenant_id, role=StaffRole.OWNER.value)
        actor = _actor(me, tenant_id)

        with pytest.raises(StaffSelfManageError):
            await service.update(tenant_id, me, role=StaffRole.SHIFT_MANAGER.value, actor=actor)
        with pytest.raises(StaffSelfManageError):
            await service.deactivate(tenant_id, me, actor=actor)

        async with tenant_session(factory, tenant_id) as session:
            row = await StaffUsersRepository().by_id(session, tenant_id, me)
            assert row is not None
            assert row.role == StaffRole.OWNER.value
            # The guard raises INSIDE the transaction, so the rollback is what
            # makes this true — an audit row written before the guard would show
            # up right here.
            assert await AuditLogRepository().list_actions(session) == []
    finally:
        await engine.dispose()


async def test_an_owner_renames_herself_and_changes_her_own_password(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        service = StaffService(
            factory,
            media_storage=_NO_BUCKET,  # type: ignore[arg-type]
            presign_rate_limiter=FixedWindowRateLimiter(
                max_attempts=50, window_seconds=900, clock=time.monotonic
            ),
        )
        me = await _seed_staff(factory, tenant_id, role=StaffRole.OWNER.value)
        actor = _actor(me, tenant_id)

        renamed = await service.update(tenant_id, me, display_name="דנה", actor=actor)
        assert renamed.display_name == "דנה"

        with pytest.raises(DomainValidationError):
            await service.update(tenant_id, me, password="a-brand-new-pw", actor=actor)
        with pytest.raises(DomainValidationError):
            await service.update(
                tenant_id,
                me,
                password="a-brand-new-pw",
                current_password="wrong-one",
                actor=actor,
            )
        async with tenant_session(factory, tenant_id) as session:
            unchanged = await StaffUsersRepository().by_id(session, tenant_id, me)
            assert unchanged is not None
            assert verify_password(PASSWORD, unchanged.password_hash)

        await service.update(
            tenant_id, me, password="a-brand-new-pw", current_password=PASSWORD, actor=actor
        )
        async with tenant_session(factory, tenant_id) as session:
            rotated = await StaffUsersRepository().by_id(session, tenant_id, me)
            assert rotated is not None
            assert verify_password("a-brand-new-pw", rotated.password_hash)
    finally:
        await engine.dispose()


async def test_audit_writes_one_row_per_actual_change_and_none_for_a_no_op(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        service = StaffService(
            factory,
            media_storage=_NO_BUCKET,  # type: ignore[arg-type]
            presign_rate_limiter=FixedWindowRateLimiter(
                max_attempts=50, window_seconds=900, clock=time.monotonic
            ),
        )
        owner = await _seed_staff(factory, tenant_id, role=StaffRole.OWNER.value)
        actor = _actor(owner, tenant_id)
        target = await _seed_staff(
            factory, tenant_id, role=StaffRole.SHIFT_MANAGER.value, display_name="Old"
        )

        await service.update(
            tenant_id,
            target,
            display_name="New",
            role=StaffRole.OWNER.value,
            password="another-long-pw",
            actor=actor,
        )
        # Every value already matches — no write, no audit row, 200 unchanged.
        await service.update(
            tenant_id, target, display_name="New", role=StaffRole.OWNER.value, actor=actor
        )
        await service.deactivate(tenant_id, target, actor=actor)

        async with tenant_session(factory, tenant_id) as session:
            stmt = select(AuditLog).order_by(AuditLog.created_at)
            rows = list((await session.execute(stmt)).scalars().all())
        assert [row.action for row in rows] == [
            AuditAction.STAFF_UPDATED.value,
            AuditAction.STAFF_ROLE_CHANGED.value,
            AuditAction.STAFF_PASSWORD_RESET.value,
            AuditAction.STAFF_DEACTIVATED.value,
        ]
        assert {row.actor_id for row in rows} == {owner}
        assert {row.entity for row in rows} == {str(target)}
        assert rows[1].details == {
            "from": StaffRole.SHIFT_MANAGER.value,
            "to": StaffRole.OWNER.value,
        }
        assert rows[2].details == {"self": False}
        # No password material, plaintext or hashed, anywhere in details.
        rendered = repr([row.details for row in rows])
        assert "another-long-pw" not in rendered
        assert "argon2" not in rendered
    finally:
        await engine.dispose()


async def test_f38s_three_patch_fields_audit_one_row_each_and_none_for_a_no_op(
    app_role_url: str,
) -> None:
    """The sibling of the test above, for F38's three — and deliberately its own
    test rather than three more kwargs on that one.

    Each of phone, start_date and shift_manager_eligible records its OWN
    STAFF_UPDATED row (spec D8: one row per thing that actually changed), so
    folding them into that test would have added three rows to an assertion that
    pins ORDER, and `created_at` is `now()` — one value for every row written in
    a single transaction. Asserted by DETAILS KEY instead, which is order-free.

    The no-op half is the load-bearing half: the console's edit form posts every
    field on every save, so a field left out of the moved-not-present comparison
    would write an audit row each time the owner pressed save having changed
    nothing.

    The phone row carries PRESENCE and never the number — stricter than the
    shipped `phone_last4` convention, because `audit_log` has no retention class
    and any digits here would outlive the seven-year scrub that exists to destroy
    exactly this identifier."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        service = StaffService(
            factory,
            media_storage=_NO_BUCKET,  # type: ignore[arg-type]
            presign_rate_limiter=FixedWindowRateLimiter(
                max_attempts=50, window_seconds=900, clock=time.monotonic
            ),
        )
        owner = await _seed_staff(factory, tenant_id, role=StaffRole.OWNER.value)
        actor = _actor(owner, tenant_id)
        target = await _seed_staff(factory, tenant_id, role=StaffRole.SHIFT_MANAGER.value)

        updated = await service.update(
            tenant_id,
            target,
            phone="050-1234567",
            start_date=date(2026, 3, 1),
            shift_manager_eligible=True,
            actor=actor,
        )
        assert updated.phone == "050-1234567"
        assert updated.start_date == date(2026, 3, 1)
        assert updated.shift_manager_eligible is True

        # Every value re-sent unchanged — the save-with-nothing-touched case.
        await service.update(
            tenant_id,
            target,
            phone="050-1234567",
            start_date=date(2026, 3, 1),
            shift_manager_eligible=True,
            actor=actor,
        )

        async with tenant_session(factory, tenant_id) as session:
            rows = list((await session.execute(select(AuditLog))).scalars().all())
        assert [row.action for row in rows] == [AuditAction.STAFF_UPDATED.value] * 3
        assert {row.actor_id for row in rows} == {owner}
        assert {row.entity for row in rows} == {str(target)}
        by_key = {next(iter(row.details)): row.details for row in rows}
        assert set(by_key) == {"phone", "start_date", "shift_manager_eligible"}
        assert by_key["phone"] == {"phone": {"from": False, "to": True}}
        assert by_key["start_date"] == {"start_date": {"from": None, "to": "2026-03-01"}}
        assert by_key["shift_manager_eligible"] == {
            "shift_manager_eligible": {"from": False, "to": True}
        }
        # The number itself is never written to a log with no retention clock.
        assert "1234567" not in repr([row.details for row in rows])

        # "" is the one spelling that removes a number, and removing IS a move.
        await service.update(tenant_id, target, phone="", actor=actor)
        async with tenant_session(factory, tenant_id) as session:
            after = list((await session.execute(select(AuditLog))).scalars().all())
        assert len(after) == 4
        assert {"phone": {"from": True, "to": False}} in [row.details for row in after]
    finally:
        await engine.dispose()


async def test_another_tenants_staff_row_is_indistinguishable_from_missing(
    app_role_url: str,
) -> None:
    """RLS, asserted through the service rather than the repository: a 404 is what
    a foreign id must answer, and a 403 or a 200 would both be leaks."""
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        service = StaffService(
            factory,
            media_storage=_NO_BUCKET,  # type: ignore[arg-type]
            presign_rate_limiter=FixedWindowRateLimiter(
                max_attempts=50, window_seconds=900, clock=time.monotonic
            ),
        )
        theirs = await _seed_staff(factory, elsewhere, role=StaffRole.SHIFT_MANAGER.value)
        mine = await _seed_staff(factory, here, role=StaffRole.OWNER.value)
        actor = _actor(mine, here)

        assert [row.id for row in await service.list_staff(here)] == [mine]
        with pytest.raises(StaffNotFoundError):
            await service.update(here, theirs, display_name="Hijacked", actor=actor)
        with pytest.raises(StaffNotFoundError):
            await service.deactivate(here, theirs, actor=actor)

        async with tenant_session(factory, elsewhere) as session:
            survivor = await StaffUsersRepository().by_id(session, elsewhere, theirs)
            assert survivor is not None
            assert survivor.display_name == "Staff"
    finally:
        await engine.dispose()


# --- D2: the retention proof ------------------------------------------------


async def test_offboarding_retains_every_operational_row_that_points_at_her(
    app_role_url: str,
) -> None:
    """Plan task D2, and it needs its OWN test precisely because the FK-less
    schema makes the regression silent.

    `soft_delete` touches only `staff_users` columns TODAY. Nothing enforces
    that: no constraint, no CASCADE to forbid, no join to notice. A future
    "tidy-up" adding `deleted_at IS NULL` to any of the four reads below — or a
    well-meant `DELETE FROM fitting_room_assignments WHERE staff_user_id = …`
    inside the offboarding transaction — destroys the boutique's operational
    history with a green suite, because every existing test here offboards a
    staffer who appears in no other table.

    Four tables, chosen because each is a different SHAPE of pointer:
      * `fitting_room_assignments.staff_user_id` — NOT NULL, the room she held;
      * `sos_alerts.target_staff_user_id` — nullable, whom a colleague paged;
      * `alteration_tickets.assigned_staff_user_id` — nullable, her workload;
      * `audit_log.actor_id` — the evidence trail, which has no retention class
        at all by ruling.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        service = StaffService(
            factory,
            media_storage=_NO_BUCKET,  # type: ignore[arg-type]
            presign_rate_limiter=FixedWindowRateLimiter(
                max_attempts=50, window_seconds=900, clock=time.monotonic
            ),
        )
        owner = await _seed_staff(factory, tenant_id, role=StaffRole.OWNER.value)
        leaver = await _seed_staff(
            factory, tenant_id, role=StaffRole.SHIFT_MANAGER.value, display_name="דנה כהן"
        )

        room = FittingRoom(id=uuid.uuid4(), tenant_id=tenant_id, label="חדר 1", sort_order=1)
        assignment = FittingRoomAssignment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            fitting_room_id=room.id,
            staff_user_id=leaver,
        )
        alert = SosAlert(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            raised_by=owner,
            target_staff_user_id=leaver,
        )
        ticket = AlterationTicket(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            customer_id=uuid.uuid4(),
            due_date=date(2026, 9, 1),
            effort_minutes=30,
            assigned_staff_user_id=leaver,
        )
        trail = AuditLog(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            actor_id=leaver,
            action=AuditAction.STAFF_UPDATED,
            entity=str(leaver),
        )
        async with tenant_session(factory, tenant_id) as session:
            for row in (room, assignment, alert, ticket, trail):
                session.add(row)

        await service.deactivate(tenant_id, leaver, actor=_actor(owner, tenant_id))

        async with tenant_session(factory, tenant_id) as session:
            gone = await StaffUsersRepository().by_id(session, tenant_id, leaver)
            assert gone is None, "the staffer herself IS offboarded — the test is not vacuous"

            # Each read is by PRIMARY KEY and asserts the pointer column too: a
            # row that survived with its `staff_user_id` nulled would satisfy a
            # bare existence check and still have lost the fact.
            held = await session.get(FittingRoomAssignment, assignment.id)
            assert held is not None
            assert held.staff_user_id == leaver
            assert held.released_at is None

            paged = await session.get(SosAlert, alert.id)
            assert paged is not None
            assert paged.target_staff_user_id == leaver

            work = await session.get(AlterationTicket, ticket.id)
            assert work is not None
            assert work.assigned_staff_user_id == leaver

            evidence = await session.get(AuditLog, trail.id)
            assert evidence is not None
            assert evidence.actor_id == leaver

            # ⚠ The plan's D2 line says this tile renders `staff_display_name:
            # null`. It does NOT, and the difference is deliberate upstream: the
            # `staff_users` join in `_occupancy_rows` carries NO `deleted_at`
            # filter, precisely so a holder offboarded mid-fitting leaves a tile
            # that can still say who is in there
            # (`test_a_soft_deleted_holder_still_names_the_tile`). What D2 is
            # actually about is that the ROW SURVIVES the offboarding rather than
            # the room reading as free, so that is what is asserted.
            tile = await FittingRoomsRepository().room_with_occupancy(session, tenant_id, room.id)
            assert tile is not None
            assert tile.assignment_id == assignment.id
            assert tile.staff_user_id == leaver
            assert tile.staff_display_name == "דנה כהן"
    finally:
        await engine.dispose()


# --- the routes, over real HTTP, against real Postgres ---


def _app(factory: async_sessionmaker[AsyncSession]) -> FastAPI:
    """create_app() with the real resolver and the state services these routes
    touch repointed at the container — the test_staff_role_gating_integration
    recipe, plus the staff service this feature adds."""
    app = create_app(resolver=RepositoryTenantResolver(factory))
    app.state.auth_service = AuthService(factory, SETTINGS)
    app.state.staff_service = StaffService(
        factory,
        media_storage=_NO_BUCKET,  # type: ignore[arg-type]
        presign_rate_limiter=FixedWindowRateLimiter(
            max_attempts=50, window_seconds=900, clock=time.monotonic
        ),
    )
    app.state.boutique_service = BoutiqueSettingsService(
        factory,
        terms_rate_limiter=FixedWindowRateLimiter(
            max_attempts=100, window_seconds=3600, clock=lambda: 0.0
        ),
    )
    # Generous on purpose: several of these tests log in more than five times,
    # and a 429 here would read as an auth failure rather than a throttle.
    app.state.login_rate_limiter = FixedWindowRateLimiter(
        max_attempts=1000, window_seconds=3600, clock=lambda: 0.0
    )
    return app


async def _seed_tenant(factory: async_sessionmaker[AsyncSession]) -> tuple[uuid.UUID, str, str]:
    slug = f"staff{uuid.uuid4().hex[:8]}"
    tenant = await TenantsRepository(factory).insert(slug=slug, name="Bella Bridal")
    email = _email()
    await _seed_staff(factory, tenant.id, role=StaffRole.OWNER.value, email=email)
    return tenant.id, slug, email


def _client(app: FastAPI, slug: str) -> TestClient:
    return TestClient(app, base_url=f"http://{slug}.localtest.me")


def _login(client: TestClient, email: str, password: str = PASSWORD) -> Response:
    return client.post("/manage/auth/login", json={"email": email, "password": password})


def test_a_created_staffer_signs_in_immediately_with_the_password_the_owner_set(
    app_role_url: str,
) -> None:
    """The one thing no unit test can prove: lowercase + argon2 + by_email, end to
    end through the UNCHANGED /manage/auth/login (SMC ruling 1 — email and
    password, no phone OTP). The address is created MIXED-CASE on purpose: a row
    written as Dana@Bella.example can never sign in, and pydantic's EmailStr
    normalizes only the domain, so nothing above the service catches it."""
    engine, factory = _factory(app_role_url)
    try:
        tenant_id, slug, owner_email = asyncio.run(_seed_tenant(factory))
        app = _app(factory)
        mixed = f"Dana.{uuid.uuid4().hex[:6]}@Bella.Example"
        new_password = "her-own-long-password"

        with _client(app, slug) as owner:
            assert _login(owner, owner_email).status_code == 200
            created = owner.post(
                "/manage/staff",
                json={
                    "email": mixed,
                    "display_name": "דנה",
                    "role": StaffRole.SHIFT_MANAGER.value,
                    "password": new_password,
                },
            )
        assert created.status_code == 200, created.text
        assert created.json()["email"] == mixed.lower()
        assert "password" not in created.text.lower()

        with _client(app, slug) as newcomer:
            signed_in = _login(newcomer, mixed.lower(), new_password)
            assert signed_in.status_code == 200, signed_in.text
            assert signed_in.json()["role"] == StaffRole.SHIFT_MANAGER.value
            # And the persona the whole SMC epic is built around now exists:
            # admitted on the shared console, refused on the owner-only router.
            assert newcomer.get("/manage/settings").status_code == 200
            assert newcomer.get("/manage/staff").status_code == 403
    finally:
        asyncio.run(engine.dispose())


def test_deactivating_through_the_route_kills_the_targets_session_on_her_next_request(
    app_role_url: str,
) -> None:
    """F31's test_a_soft_deleted_shift_managers_live_cookie_is_401_not_403 already
    proves the SEAM — by_id filters deleted_at IS NULL, so resolve_session returns
    None and the gate is never reached. What it cannot prove is that the PRODUCT's
    own write does it: F31 used a hand-written UPDATE, and this drives
    DELETE /manage/staff/{staff_id} through the service, under the advisory lock,
    as boutique_app. No sweep exists and none is built."""
    engine, factory = _factory(app_role_url)
    try:
        tenant_id, slug, owner_email = asyncio.run(_seed_tenant(factory))
        target_email = _email()
        target_id = asyncio.run(
            _seed_staff(factory, tenant_id, role=StaffRole.SHIFT_MANAGER.value, email=target_email)
        )
        app = _app(factory)

        with _client(app, slug) as target, _client(app, slug) as owner:
            assert _login(target, target_email).status_code == 200
            assert target.get("/manage/settings").status_code == 200

            assert _login(owner, owner_email).status_code == 200
            removed = owner.delete(f"/manage/staff/{target_id}")
            assert removed.status_code == 200, removed.text
            assert removed.json() == {"ok": True}

            # Same cookie, no re-login: 401, not 403 — deactivation is an
            # authentication failure, not an authorization one.
            after = target.get("/manage/settings")
            assert after.status_code == 401
            assert after.json() == NOT_AUTHENTICATED_BODY
            # And she is gone from the list the owner sees — the list is
            # live-only, which is why there is no restore route (spec D5).
            assert target_id not in {
                uuid.UUID(row["id"]) for row in owner.get("/manage/staff").json()
            }
    finally:
        asyncio.run(engine.dispose())


def test_a_password_change_kills_the_other_live_sessions_but_not_the_acting_one(
    app_role_url: str,
) -> None:
    """The `current_password` check only «converts a permanent takeover into a
    bounded one» (spec D4) if the bound actually closes. `resolve_session` never
    consults `password_hash`, so a stolen cookie survives the password change
    that is meant to contain it — and inside that window POST /manage/staff can
    mint a standalone second owner that outlives the TTL, the new password and
    every logout. Two cookies for the same owner: the one that sends the PATCH
    lives on, the other is a 401 on its very next request."""
    engine, factory = _factory(app_role_url)
    try:
        tenant_id, slug, owner_email = asyncio.run(_seed_tenant(factory))
        app = _app(factory)

        with _client(app, slug) as acting, _client(app, slug) as stolen:
            me = _login(acting, owner_email)
            assert me.status_code == 200
            my_id = me.json()["id"]
            assert _login(stolen, owner_email).status_code == 200
            assert stolen.get("/manage/settings").status_code == 200

            changed = acting.patch(
                f"/manage/staff/{my_id}",
                json={"password": "her-brand-new-password", "current_password": PASSWORD},
            )
            assert changed.status_code == 200, changed.text

            assert stolen.get("/manage/settings").status_code == 401
            assert stolen.post("/manage/staff", json={}).status_code == 401
            # And the tab she changed it in is still hers.
            assert acting.get("/manage/staff").status_code == 200

        # The new credential is the live one; the old is gone.
        with _client(app, slug) as fresh:
            assert _login(fresh, owner_email).status_code == 401
            assert _login(fresh, owner_email, "her-brand-new-password").status_code == 200
    finally:
        asyncio.run(engine.dispose())


def test_a_password_reset_by_the_owner_signs_the_target_out_everywhere(
    app_role_url: str,
) -> None:
    """The reset-someone-else path: the owner holds no session of the target's,
    so the acting-cookie exclusion is a no-op and every one of the target's
    sessions goes."""
    engine, factory = _factory(app_role_url)
    try:
        tenant_id, slug, owner_email = asyncio.run(_seed_tenant(factory))
        target_email = _email()
        target_id = asyncio.run(
            _seed_staff(factory, tenant_id, role=StaffRole.SHIFT_MANAGER.value, email=target_email)
        )
        app = _app(factory)

        with _client(app, slug) as target, _client(app, slug) as owner:
            assert _login(target, target_email).status_code == 200
            assert target.get("/manage/settings").status_code == 200

            assert _login(owner, owner_email).status_code == 200
            reset = owner.patch(f"/manage/staff/{target_id}", json={"password": "a-reset-password"})
            assert reset.status_code == 200, reset.text

            assert target.get("/manage/settings").status_code == 401
            assert owner.get("/manage/staff").status_code == 200
    finally:
        asyncio.run(engine.dispose())


def test_a_demotion_through_the_route_bites_on_the_very_next_request(
    app_role_url: str,
) -> None:
    """The console half of F31's demotion proof, now driven by the product rather
    than by a test-only UPDATE: the demoted account keeps the shared console and
    loses the owner-only router, on the same cookie."""
    engine, factory = _factory(app_role_url)
    try:
        tenant_id, slug, owner_email = asyncio.run(_seed_tenant(factory))
        second_email = _email()
        second_id = asyncio.run(
            _seed_staff(factory, tenant_id, role=StaffRole.OWNER.value, email=second_email)
        )
        app = _app(factory)

        with _client(app, slug) as demoted, _client(app, slug) as owner:
            assert _login(demoted, second_email).status_code == 200
            assert demoted.get("/manage/staff").status_code == 200

            assert _login(owner, owner_email).status_code == 200
            patched = owner.patch(
                f"/manage/staff/{second_id}", json={"role": StaffRole.SHIFT_MANAGER.value}
            )
            assert patched.status_code == 200, patched.text
            assert patched.json()["role"] == StaffRole.SHIFT_MANAGER.value

            refused = demoted.get("/manage/staff")
            assert refused.status_code == 403
            assert refused.json() == NOT_AUTHORIZED_BODY
            assert demoted.get("/manage/settings").status_code == 200
            assert demoted.get("/manage/auth/me").json()["role"] == (StaffRole.SHIFT_MANAGER.value)
    finally:
        asyncio.run(engine.dispose())


def test_the_route_refuses_a_self_deactivate_and_the_owner_stays_signed_in(
    app_role_url: str,
) -> None:
    engine, factory = _factory(app_role_url)
    try:
        tenant_id, slug, owner_email = asyncio.run(_seed_tenant(factory))
        app = _app(factory)
        with _client(app, slug) as owner:
            me = _login(owner, owner_email)
            assert me.status_code == 200
            my_id = me.json()["id"]

            refused = owner.delete(f"/manage/staff/{my_id}")
            assert refused.status_code == 409
            assert refused.json()["error"]["code"] == "STAFF_SELF_MANAGE"
            assert owner.get("/manage/staff").status_code == 200
    finally:
        asyncio.run(engine.dispose())
