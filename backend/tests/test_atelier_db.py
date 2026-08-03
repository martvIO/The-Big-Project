"""F41's repository against real Postgres as the non-owner app role.

**The guarded writes.** Every stage verb is one conditional UPDATE whose
predicate carries `AND <every column after the target> IS NULL`, and every one
classifies off the `.returning()` scalar rather than off the object it just
wrote — the identity-map trap this repo has documented four times
(`db/repositories/bookings.py`, `booking/owner.py`, `staff_users.py`'s
`_refreshed`, and `test_booking_owner_db.py`'s pinned docstring). Both halves of
every returned tuple are asserted, because the `wrote` flag and the rendered row
fail independently: dropping `populate_existing=True` leaves the flag right and
the row wrong.

⚠ **THIS MODULE COMMITS INTO A SESSION-SCOPED CONTAINER, so no row it commits may
hold a FLOOR ROLE.** `migrated_db` and `app_role_url` are `scope="session"`,
pytest collects alphabetically, and `test_atelier_db.py` sorts BEFORE
`test_migrations.py` — a committed `seamstress` row reddens
`test_adding_the_role_check_validates_existing_rows` there, in a file that never
mentions the atelier. Exiting `tenant_session` IS the commit, so there is nothing
to roll back. **Nothing in this module depends on an assignee's ROLE**: the
repository's assign verbs take a staff id and never look it up, and the
seamstress-role check is `test_atelier_service.py`'s. So the two tests that need
a real `staff_users` row seed `owner` and assert on ids, and the union test seeds
`shift_manager` for its non-assignable leg.

Every test mints its own tenant id; nothing here truncates.
"""

import datetime
import uuid

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.atelier.schemas import AssignTicketRequest, CreateTicketRequest, StageRequest
from app.atelier.service import AtelierService
from app.atelier.stages import DEFAULT_EFFORT_BANDS, stage_of
from app.auth.service import StaffContext
from app.db.repositories.alteration_tickets import (
    BOARD_TICKET_LIMIT,
    DELIVERED_WINDOW_DAYS,
    AlterationTicketsRepository,
)
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.rls import TENANT_ID_SETTING
from app.db.tenant import tenant_session
from app.models.alteration_ticket import AlterationTicket
from app.models.audit_log import AuditLog
from app.models.constants import AuditAction, EffortBand, StaffRole, TicketStage
from app.models.customer import Customer
from app.storefront.validation import BOUTIQUE_TIMEZONE

pytestmark = pytest.mark.db

# Frozen module constants rather than a real clock: every assertion is an
# equality on the stored value, and `now()` would make them approximate.
NOW = datetime.datetime(2026, 8, 2, 11, 20, tzinfo=datetime.UTC)
LATER = datetime.datetime(2026, 8, 2, 13, 45, tzinfo=datetime.UTC)
TODAY = datetime.date(2026, 8, 3)
DUE = datetime.date(2026, 8, 20)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
    )


async def _seed(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    due_date: datetime.date = DUE,
    effort_minutes: int = 60,
    assigned_staff_user_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await AlterationTicketsRepository().insert(
            session,
            tenant_id=tenant_id,
            customer_id=uuid.uuid4(),
            due_date=due_date,
            effort_minutes=effort_minutes,
            at=NOW,
            assigned_staff_user_id=assigned_staff_user_id,
            notes=notes,
        )
        return row.id


async def _seed_staff(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    display_name: str = "Staff",
    role: str = StaffRole.OWNER.value,
) -> uuid.UUID:
    """Seeds `owner` by default and refuses a floor role — see the module
    docstring. This module COMMITS, and a floor role here reddens
    test_migrations.py."""
    assert role in {StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value}, (
        "this module COMMITS its rows; a floor role here reddens test_migrations.py"
    )
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=f"atelier-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name=display_name,
            role=role,
        )
        return staff.id


async def _advance_to(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    ticket_id: uuid.UUID,
    *stages: TicketStage,
) -> None:
    repo = AlterationTicketsRepository()
    for stage in stages:
        async with tenant_session(factory, tenant_id) as session:
            wrote, _ = await repo.advance_stage(session, tenant_id, ticket_id, stage, at=NOW)
        assert wrote is True, stage


# --- insert and by_id ---


async def test_insert_stamps_intake_and_reads_back_as_intake(app_role_url: str) -> None:
    """`intake_at` is stamped by the INSERT itself and nothing else writes it —
    which is why `stage_of`'s INTAKE floor is a defence against a hand-edited row
    rather than a state the API can produce."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            row = await repo.by_id(session, tenant_id, ticket_id)
        assert row is not None
        assert row.intake_at == NOW
        assert row.in_progress_at is None
        assert row.delivered_at is None
        assert stage_of(row) is TicketStage.INTAKE
    finally:
        await engine.dispose()


async def test_by_id_misses_an_absent_a_soft_deleted_and_a_foreign_ticket(
    app_role_url: str,
) -> None:
    """Three misses, one body, because all three must be INDISTINGUISHABLE to the
    caller: the service turns each into the same 404, so a probe cannot use the
    response to learn that a ticket exists under some other tenant.

    ⚠ The cross-tenant leg would stay GREEN with the explicit `tenant_id`
    predicate deleted — RLS carries it on its own. That predicate is
    defence-in-depth against a future RLS regression (a missing FORCE, a policy
    typo, an over-privileged role) and NO single-writer test can prove it. The
    isolation suite is where the RLS half is proved; this asserts the behaviour,
    not the mechanism."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    other_tenant = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        foreign_id = await _seed(factory, other_tenant)

        async with tenant_session(factory, tenant_id) as session:
            assert await repo.by_id(session, tenant_id, uuid.uuid4()) is None
            assert await repo.by_id(session, tenant_id, foreign_id) is None
            assert await repo.by_id(session, tenant_id, ticket_id) is not None

        async with tenant_session(factory, tenant_id) as session:
            assert await repo.soft_delete(session, tenant_id, ticket_id) is True
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.by_id(session, tenant_id, ticket_id) is None
    finally:
        await engine.dispose()


async def test_a_second_soft_delete_reports_no_write(app_role_url: str) -> None:
    """`deleted_at IS NULL` in the predicate is what makes a second call answer
    False rather than re-stamping the timestamp — so a double-tapped delete
    cannot move the retention clock F20 will read off this column."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.soft_delete(session, tenant_id, ticket_id) is True
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.soft_delete(session, tenant_id, ticket_id) is False
    finally:
        await engine.dispose()


# --- advance_stage ---


@pytest.mark.parametrize(
    "target",
    [TicketStage.IN_PROGRESS, TicketStage.QC, TicketStage.READY, TicketStage.DELIVERED],
)
async def test_an_advance_to_each_target_stamps_that_column(
    app_role_url: str, target: TicketStage
) -> None:
    """Each of the four reachable targets FROM INTAKE, one at a time — which is
    also the forward-skip case D2 makes legal: advancing straight to `delivered`
    from `intake` leaves three columns NULL forever and the ticket reads
    `delivered`."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.advance_stage(session, tenant_id, ticket_id, target, at=NOW)
        assert wrote is True
        assert row is not None
        assert stage_of(row) is target

        async with tenant_session(factory, tenant_id) as session:
            stored = await repo.by_id(session, tenant_id, ticket_id)
        assert stored is not None
        assert stage_of(stored) is target
    finally:
        await engine.dispose()


async def test_a_second_advance_to_the_same_stage_keeps_the_first_timestamp(
    app_role_url: str,
) -> None:
    """The `<target>_at IS NULL` clause. A double tap must keep the FIRST
    timestamp rather than move it — and the row that comes back must carry that
    first value, not the `at` this call passed in. Dropping
    `populate_existing=True` leaves `wrote` correct and this assertion red, which
    is the whole reason both halves are asserted separately."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        await _advance_to(factory, tenant_id, ticket_id, TicketStage.QC)

        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.advance_stage(
                session, tenant_id, ticket_id, TicketStage.QC, at=LATER
            )
        assert wrote is False
        assert row is not None
        assert row.qc_at == NOW
    finally:
        await engine.dispose()


async def test_an_advance_BEHIND_the_current_stage_writes_nothing(app_role_url: str) -> None:
    """THE PREDICATE'S OTHER JOB, and the one no `<target>_at IS NULL` clause can
    do on its own: a stale board taps `in_progress` on a ticket already at
    `ready`. `in_progress_at` IS NULL, so without the `AND <every later column>
    IS NULL` clause this write SUCCEEDS and puts an in_progress stamp later than
    the ready one on the row.

    The row comes back unchanged and still reads `ready`; the service turns the
    zero rows plus a re-read that is not the target into a 409."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        await _advance_to(factory, tenant_id, ticket_id, TicketStage.READY)

        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.advance_stage(
                session, tenant_id, ticket_id, TicketStage.IN_PROGRESS, at=LATER
            )
        assert wrote is False
        assert row is not None
        assert row.in_progress_at is None
        assert stage_of(row) is TicketStage.READY
    finally:
        await engine.dispose()


async def test_an_advance_on_a_soft_deleted_or_absent_ticket_answers_no_row(
    app_role_url: str,
) -> None:
    """`(False, None)` is the 404 case and it is the only answer that means
    "gone" — soft-deleted, another tenant's, or never existed."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            await repo.soft_delete(session, tenant_id, ticket_id)

        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.advance_stage(
                session, tenant_id, ticket_id, TicketStage.QC, at=NOW
            )
            assert (wrote, row) == (False, None)
            absent = await repo.advance_stage(
                session, tenant_id, uuid.uuid4(), TicketStage.QC, at=NOW
            )
            assert absent == (False, None)
    finally:
        await engine.dispose()


# --- undo_stage ---


async def test_an_undo_clears_the_rightmost_stamp(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        await _advance_to(factory, tenant_id, ticket_id, TicketStage.IN_PROGRESS)

        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.undo_stage(
                session, tenant_id, ticket_id, TicketStage.IN_PROGRESS
            )
        assert wrote is True
        assert row is not None
        assert row.in_progress_at is None
        assert stage_of(row) is TicketStage.INTAKE

        async with tenant_session(factory, tenant_id) as session:
            stored = await repo.by_id(session, tenant_id, ticket_id)
        assert stored is not None
        assert stored.in_progress_at is None
    finally:
        await engine.dispose()


async def test_a_second_undo_of_the_same_stage_writes_nothing(app_role_url: str) -> None:
    """The `<stage>_at IS NOT NULL` clause: a genuine double tap, nothing later
    exists, and the row is already where she wanted it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        await _advance_to(factory, tenant_id, ticket_id, TicketStage.QC)

        async with tenant_session(factory, tenant_id) as session:
            await repo.undo_stage(session, tenant_id, ticket_id, TicketStage.QC)
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.undo_stage(session, tenant_id, ticket_id, TicketStage.QC)
        assert wrote is False
        assert row is not None
        assert row.qc_at is None
    finally:
        await engine.dispose()


async def test_an_undo_of_a_stage_a_later_stamp_has_passed_writes_nothing(
    app_role_url: str,
) -> None:
    """D4's skip-then-stale-undo sequence, at the database.

    A ticket is at `in_progress`. Someone undoes it, then advances STRAIGHT to
    `qc`, skipping `in_progress` — legal and normal under D2. A board painted
    before all that still shows `in_progress` and taps «ביטול שלב». The
    `<every later column> IS NULL` clause is what refuses it: `in_progress_at` is
    already NULL AND `qc_at` is set, which is exactly the state D4 notes an
    "already NULL -> 200 no-op" rule would answer 200 for."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        await _advance_to(factory, tenant_id, ticket_id, TicketStage.IN_PROGRESS)
        async with tenant_session(factory, tenant_id) as session:
            await repo.undo_stage(session, tenant_id, ticket_id, TicketStage.IN_PROGRESS)
        await _advance_to(factory, tenant_id, ticket_id, TicketStage.QC)

        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.undo_stage(
                session, tenant_id, ticket_id, TicketStage.IN_PROGRESS
            )
        assert wrote is False
        assert row is not None
        # The state that makes "already NULL means no-op" and "a later stamp
        # exists means conflict" NOT disjoint — both are true here.
        assert row.in_progress_at is None
        assert row.qc_at == NOW
        assert stage_of(row) is TicketStage.QC
    finally:
        await engine.dispose()


async def test_an_undo_of_a_stage_the_ticket_has_since_MOVED_PAST_writes_nothing(
    app_role_url: str,
) -> None:
    """The undo's `<every later column> IS NULL` clause, on the ONLY state that
    exercises it — and it took a surviving mutation to find that state.

    The sibling test above has `in_progress_at` already NULL, so the
    `IS NOT NULL` clause refuses it single-handed and the later-columns clause is
    never consulted. HERE both stamps are set: a board painted at `in_progress`
    taps «ביטול שלב» after the garment has reached `qc`. Without the later-columns
    clause that UPDATE SUCCEEDS — it clears a stage the ticket genuinely passed
    through and leaves a hole that D2 says means "never separately recorded",
    which is now a lie about the record.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        await _advance_to(factory, tenant_id, ticket_id, TicketStage.IN_PROGRESS, TicketStage.QC)

        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.undo_stage(
                session, tenant_id, ticket_id, TicketStage.IN_PROGRESS
            )
        assert wrote is False
        assert row is not None
        assert row.in_progress_at == NOW, "the passed-through stamp must survive"
        assert row.qc_at == NOW
        assert stage_of(row) is TicketStage.QC

        # Undoing the RIGHTMOST stamp is the verb's actual job and still works.
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.undo_stage(session, tenant_id, ticket_id, TicketStage.QC)
        assert wrote is True
        assert row is not None
        assert stage_of(row) is TicketStage.IN_PROGRESS
    finally:
        await engine.dispose()


# --- claim, release, assign ---


async def test_a_claim_on_an_unassigned_ticket_writes_and_a_second_one_does_not(
    app_role_url: str,
) -> None:
    """`assigned_staff_user_id IS NULL` in the WHERE is the race guard, and it is
    in the PREDICATE rather than in a pre-read for the reason every conditional
    write in this repo states: a pre-read another transaction can invalidate is
    not a guard.

    The loser's row comes back carrying the WINNER's id — which is what lets the
    service tell "my own double tap" (200) from "a colleague got there first"
    (409) without a second statement."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        first, second = uuid.uuid4(), uuid.uuid4()

        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.claim(session, tenant_id, ticket_id, staff_user_id=first)
        assert wrote is True
        assert row is not None
        assert row.assigned_staff_user_id == first

        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.claim(session, tenant_id, ticket_id, staff_user_id=second)
        assert wrote is False
        assert row is not None
        assert row.assigned_staff_user_id == first
    finally:
        await engine.dispose()


async def test_a_release_drops_only_her_own_claim(app_role_url: str) -> None:
    """`assigned_staff_user_id = :her` is the mirror predicate, so a seamstress
    can drop her own claim and can NEVER drop anybody else's."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        mine, hers = uuid.uuid4(), uuid.uuid4()
        ticket_id = await _seed(factory, tenant_id, assigned_staff_user_id=hers)

        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.release(session, tenant_id, ticket_id, staff_user_id=mine)
        assert wrote is False
        assert row is not None
        assert row.assigned_staff_user_id == hers

        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.release(session, tenant_id, ticket_id, staff_user_id=hers)
        assert wrote is True
        assert row is not None
        assert row.assigned_staff_user_id is None
    finally:
        await engine.dispose()


async def test_an_elevated_assign_is_unconditional_and_accepts_null(app_role_url: str) -> None:
    """D9: elevated assignment is deliberately LAST-WRITE-WINS and takes no
    conflict. A manager reassigning a garment is making a staffing decision with
    a person in front of her, and a conflict dialog because a colleague touched
    the same ticket four seconds ago is the platform second-guessing a call that
    is hers.

    `_refreshed` changes WHICH row it renders, never who won."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        first, second = uuid.uuid4(), uuid.uuid4()
        ticket_id = await _seed(factory, tenant_id, assigned_staff_user_id=first)

        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.assign(session, tenant_id, ticket_id, staff_user_id=second)
        assert wrote is True
        assert row is not None
        assert row.assigned_staff_user_id == second

        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await repo.assign(session, tenant_id, ticket_id, staff_user_id=None)
        assert wrote is True
        assert row is not None
        assert row.assigned_staff_user_id is None
    finally:
        await engine.dispose()


async def test_an_assign_on_a_soft_deleted_ticket_answers_no_row(app_role_url: str) -> None:
    """Unconditional means unconditional about the ASSIGNEE, never about
    `deleted_at`: a deleted ticket is gone to every verb."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            await repo.soft_delete(session, tenant_id, ticket_id)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.assign(session, tenant_id, ticket_id, staff_user_id=uuid.uuid4()) == (
                False,
                None,
            )
    finally:
        await engine.dispose()


# --- update ---


async def test_update_replaces_every_editable_field_and_answers_the_stored_row(
    app_role_url: str,
) -> None:
    """A FULL REPLACE: every editable field is written on every call, so an
    omitted key can never silently clear a value — the schema layer is what makes
    "omitted" impossible, and this is the write that assumes it.

    The customer is NOT editable and the five stamps are NOT editable: a ticket
    opened for the wrong bride is a delete and a re-open, and a stage is moved by
    its own verb."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id, notes="original")
        async with tenant_session(factory, tenant_id) as session:
            before = await repo.by_id(session, tenant_id, ticket_id)
        assert before is not None
        customer_id = before.customer_id

        dress_id = uuid.uuid4()
        async with tenant_session(factory, tenant_id) as session:
            row = await repo.update(
                session,
                tenant_id,
                ticket_id,
                due_date=datetime.date(2026, 9, 1),
                effort_minutes=240,
                dress_id=dress_id,
                dress_name="ולנטינה",
                dress_size="38",
                notes=None,
            )
        assert row is not None
        assert row.due_date == datetime.date(2026, 9, 1)
        assert row.effort_minutes == 240
        assert row.dress_id == dress_id
        assert row.dress_name == "ולנטינה"
        assert row.dress_size == "38"
        assert row.notes is None
        assert row.customer_id == customer_id
        assert row.intake_at == NOW

        async with tenant_session(factory, tenant_id) as session:
            stored = await repo.by_id(session, tenant_id, ticket_id)
        assert stored is not None
        assert stored.effort_minutes == 240
        assert stored.notes is None
    finally:
        await engine.dispose()


async def test_update_misses_a_soft_deleted_ticket(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            await repo.soft_delete(session, tenant_id, ticket_id)
        async with tenant_session(factory, tenant_id) as session:
            assert (
                await repo.update(
                    session,
                    tenant_id,
                    ticket_id,
                    due_date=DUE,
                    effort_minutes=30,
                    dress_id=None,
                    dress_name=None,
                    dress_size=None,
                    notes=None,
                )
                is None
            )
    finally:
        await engine.dispose()


# --- the board read ---


async def test_the_board_orders_by_due_date_then_created_at_then_id(app_role_url: str) -> None:
    """⚠ THE `id` TIEBREAK IS NOT DECORATION AND THIS SEED IS WHY.

    `created_at` defaults to `now()`, which in Postgres is TRANSACTION START TIME
    — identical for every row inserted in one transaction. These three tickets
    share one `due_date` AND one `created_at`, so `ORDER BY due_date, created_at`
    alone leaves Postgres free to return them in either order across plans, and
    the console's cards shuffle between ticks for no reason a user can see.

    `CustomersRepository.search` states the same failure for OFFSET paging.
    `StaffUsersRepository.list_live`'s single-column order is NOT a precedent —
    it gets away with it because its tests seed one row per session.

    Two consecutive reads, asserted equal AND asserted sorted by id, so the test
    fails on a non-deterministic order rather than merely on a different one."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        # ONE transaction, so all three share a created_at.
        async with tenant_session(factory, tenant_id) as session:
            for _ in range(3):
                await repo.insert(
                    session,
                    tenant_id=tenant_id,
                    customer_id=uuid.uuid4(),
                    due_date=DUE,
                    effort_minutes=60,
                    at=NOW,
                )
        # One with an earlier due date — it must sort first regardless of when it
        # was created.
        urgent = await _seed(factory, tenant_id, due_date=datetime.date(2026, 8, 5))

        async with tenant_session(factory, tenant_id) as session:
            first, truncated = await repo.board(session, tenant_id, today=TODAY)
        async with tenant_session(factory, tenant_id) as session:
            second, _ = await repo.board(session, tenant_id, today=TODAY)

        assert truncated is False
        assert [row.id for row in first] == [row.id for row in second]
        assert first[0].id == urgent
        created = {row.created_at for row in first[1:]}
        assert len(created) == 1, "the three same-transaction rows must share a created_at"
        assert [row.id for row in first[1:]] == sorted(row.id for row in first[1:])
    finally:
        await engine.dispose()


async def test_the_board_keeps_a_recently_delivered_ticket_and_drops_an_older_one(
    app_role_url: str,
) -> None:
    """The delivered column is a RECEIPT OF THE LAST WEEK, not an archive.
    Without the window a five-second poll ships a boutique's entire alteration
    history on every tick, forever.

    The boundary is asserted from BOTH sides at once — a ticket delivered exactly
    `DELIVERED_WINDOW_DAYS` ago is IN, one delivered a day earlier is OUT — so a
    off-by-one in either direction is red."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        inside = await _seed(factory, tenant_id)
        outside = await _seed(factory, tenant_id)
        live = await _seed(factory, tenant_id)

        # Midnight in JERUSALEM on the cutoff day — the exact boundary, because
        # `due_date` is a calendar day and the window is counted in them. One
        # second earlier is the day before, and the day before is out.
        edge = datetime.datetime.combine(
            TODAY - datetime.timedelta(days=DELIVERED_WINDOW_DAYS),
            datetime.time.min,
            tzinfo=BOUTIQUE_TIMEZONE,
        )
        async with tenant_session(factory, tenant_id) as session:
            await repo.advance_stage(session, tenant_id, inside, TicketStage.DELIVERED, at=edge)
            await repo.advance_stage(
                session,
                tenant_id,
                outside,
                TicketStage.DELIVERED,
                at=edge - datetime.timedelta(seconds=1),
            )

        async with tenant_session(factory, tenant_id) as session:
            rows, truncated = await repo.board(session, tenant_id, today=TODAY)
        ids = {row.id for row in rows}
        assert live in ids
        assert inside in ids
        assert outside not in ids
        assert truncated is False
    finally:
        await engine.dispose()


async def test_the_board_excludes_soft_deleted_tickets(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        kept = await _seed(factory, tenant_id)
        gone = await _seed(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            await repo.soft_delete(session, tenant_id, gone)
        async with tenant_session(factory, tenant_id) as session:
            rows, _ = await repo.board(session, tenant_id, today=TODAY)
        assert {row.id for row in rows} == {kept}
    finally:
        await engine.dispose()


async def test_the_board_caps_at_the_limit_and_flags_the_truncation(app_role_url: str) -> None:
    """The window bounds the delivered column but NOT the undelivered one: a
    boutique that abandons the board accumulates `intake` rows without bound, and
    an unbounded five-second payload is the failure mode the client cannot
    recover from.

    Ordering by `due_date` ASC means a truncated payload drops the LEAST urgent
    tickets, which is the only truncation that is defensible — asserted here, not
    just the count."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        async with tenant_session(factory, tenant_id) as session:
            for offset in range(BOARD_TICKET_LIMIT + 3):
                await repo.insert(
                    session,
                    tenant_id=tenant_id,
                    customer_id=uuid.uuid4(),
                    due_date=DUE + datetime.timedelta(days=offset),
                    effort_minutes=60,
                    at=NOW,
                )

        async with tenant_session(factory, tenant_id) as session:
            rows, truncated = await repo.board(session, tenant_id, today=TODAY)
        assert len(rows) == BOARD_TICKET_LIMIT
        assert truncated is True
        assert rows[0].due_date == DUE
        assert rows[-1].due_date == DUE + datetime.timedelta(days=BOARD_TICKET_LIMIT - 1)
    finally:
        await engine.dispose()


async def test_the_board_is_not_truncated_at_exactly_the_limit(app_role_url: str) -> None:
    """The off-by-one that a `len(rows) >= LIMIT` test would let through: exactly
    500 tickets is a complete board, and telling the console it was truncated
    would put a warning on a screen that is showing everything."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        async with tenant_session(factory, tenant_id) as session:
            for offset in range(BOARD_TICKET_LIMIT):
                await repo.insert(
                    session,
                    tenant_id=tenant_id,
                    customer_id=uuid.uuid4(),
                    due_date=DUE + datetime.timedelta(days=offset),
                    effort_minutes=60,
                    at=NOW,
                )
        async with tenant_session(factory, tenant_id) as session:
            rows, truncated = await repo.board(session, tenant_id, today=TODAY)
        assert len(rows) == BOARD_TICKET_LIMIT
        assert truncated is False
    finally:
        await engine.dispose()


async def test_the_board_asks_THE_DATABASE_for_the_cap(app_role_url: str) -> None:
    """⚠ THE ONLY TEST HERE THAT LOOKS AT THE SQL, AND IT EXISTS BECAUSE A
    MUTATION SURVIVED WITHOUT IT.

    Deleting `.limit()` and keeping the `rows[:BOARD_TICKET_LIMIT]` slice leaves
    every other assertion in this module GREEN — same list, same `truncated`
    flag, identical observable behaviour — while the SELECT materialises the
    tenant's entire ticket history into memory on every five-second tick. That is
    precisely the failure the ceiling exists to prevent, and no black-box
    assertion can see it, because the two implementations are indistinguishable
    from their return value.

    So this one asserts the bound is the DATABASE's. The slice is not redundant
    with the LIMIT: the query asks for one row MORE than the cap so `truncated`
    needs no second COUNT statement, and the slice is what trims that probe row.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    executed: list[str] = []

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _record(
        conn: object,
        cursor: object,
        statement: str,
        parameters: object,
        context: object,
        executemany: bool,
    ) -> None:
        executed.append(statement)

    try:
        repo = AlterationTicketsRepository()
        await _seed(factory, tenant_id)
        executed.clear()
        async with tenant_session(factory, tenant_id) as session:
            await repo.board(session, tenant_id, today=TODAY)

        selects = [
            statement
            for statement in executed
            if "FROM alteration_tickets" in statement and "ORDER BY" in statement
        ]
        assert len(selects) == 1, f"the board read must be ONE statement, got {len(selects)}"
        assert "LIMIT" in selects[0], "the ceiling must be the database's, not a Python slice"
    finally:
        await engine.dispose()


async def test_the_board_never_returns_another_tenants_tickets(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    other_tenant = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        mine = await _seed(factory, tenant_id)
        await _seed(factory, other_tenant)
        async with tenant_session(factory, tenant_id) as session:
            rows, _ = await repo.board(session, tenant_id, today=TODAY)
        assert {row.id for row in rows} == {mine}
    finally:
        await engine.dispose()


# --- the seamstress union ---


async def test_the_seamstress_list_is_a_union_and_not_a_filter(app_role_url: str) -> None:
    """D9/D12: live seamstresses PLUS every distinct assignee on a live
    undelivered ticket, whether or not that person is still a seamstress.

    The check that an assignee holds `role = 'seamstress'` runs ONCE, at assign
    time, and two shipped writers break it the moment they run —
    `StaffUsersRepository.update` sets the role unconditionally and `soft_delete`
    retires her. A FILTER would make those tickets' assignee vanish from the
    payload, producing exactly the invisible bucket the check exists to prevent;
    the union keeps her on the wire so the console's «תופרת שאינה פעילה» branch
    is data-driven instead of inferred from absence.

    ⚠ This module commits, so its rows hold OWNER and SHIFT_MANAGER (see the
    module docstring) — which is fine here precisely because the point is that a
    NON-seamstress assignee still comes back. The role-at-assign-time check is
    the service's, not this layer's."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        re_roled = await _seed_staff(
            factory, tenant_id, display_name="דנה", role=StaffRole.SHIFT_MANAGER.value
        )
        retired = await _seed_staff(factory, tenant_id, display_name="אורית")
        unrelated = await _seed_staff(factory, tenant_id, display_name="רון")

        await _seed(factory, tenant_id, assigned_staff_user_id=re_roled)
        await _seed(factory, tenant_id, assigned_staff_user_id=retired)
        async with tenant_session(factory, tenant_id) as session:
            await StaffUsersRepository().soft_delete(session, tenant_id, retired)

        async with tenant_session(factory, tenant_id) as session:
            rows = await repo.assignees(session, tenant_id)
        ids = {row.id for row in rows}
        assert re_roled in ids, "a re-roled assignee must stay on the wire"
        assert retired in ids, "a retired assignee must stay on the wire"
        assert unrelated not in ids, "a staffer with no ticket and no seamstress role is not here"
    finally:
        await engine.dispose()


async def test_a_delivered_or_deleted_tickets_assignee_drops_out_of_the_union(
    app_role_url: str,
) -> None:
    """The union's second leg is scoped to LIVE UNDELIVERED tickets. A staffer
    who is no longer a seamstress and whose only ticket went out last week is not
    an assignment target and not a card label — keeping her would grow the
    payload forever, which is the same failure the delivered window closes for
    tickets."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        delivered_only = await _seed_staff(factory, tenant_id, display_name="שרה")
        deleted_only = await _seed_staff(factory, tenant_id, display_name="נעמה")

        done = await _seed(factory, tenant_id, assigned_staff_user_id=delivered_only)
        dropped = await _seed(factory, tenant_id, assigned_staff_user_id=deleted_only)
        async with tenant_session(factory, tenant_id) as session:
            await repo.advance_stage(session, tenant_id, done, TicketStage.DELIVERED, at=NOW)
            await repo.soft_delete(session, tenant_id, dropped)

        async with tenant_session(factory, tenant_id) as session:
            rows = await repo.assignees(session, tenant_id)
        assert {row.id for row in rows} == set()
    finally:
        await engine.dispose()


async def test_a_live_seamstress_with_no_ticket_at_all_is_still_an_assignment_target(
    app_role_url: str,
) -> None:
    """The union's FIRST leg, and the only test in this module that needs a real
    `seamstress` row — so it runs inside a transaction it rolls back.

    The rollback is not fastidiousness: this module commits into a session-scoped
    container, and a committed floor role reddens
    `test_adding_the_role_check_validates_existing_rows` in `test_migrations.py`,
    which re-adds 0011's TWO-VALUE role CHECK over the whole populated table. The
    read below sees its own uncommitted INSERT because it is the same
    transaction, which is exactly what makes this shape available at all.

    Without this leg the union degenerates into "whoever already holds a ticket",
    and a boutique's newest seamstress could never be given her first one."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        async with factory() as session:
            await session.execute(
                text("SELECT set_config(:name, :value, true)"),
                {"name": TENANT_ID_SETTING, "value": str(tenant_id)},
            )
            try:
                fresh = await StaffUsersRepository().insert(
                    session,
                    tenant_id=tenant_id,
                    email=f"atelier-{uuid.uuid4().hex[:10]}@bella.example",
                    password_hash="not-a-real-hash",
                    display_name="נועה",
                    role=StaffRole.SEAMSTRESS.value,
                )
                rows = await repo.assignees(session, tenant_id)
                assert [row.id for row in rows] == [fresh.id]
                assert rows[0].deleted_at is None
                assert rows[0].role == StaffRole.SEAMSTRESS.value
            finally:
                await session.rollback()
    finally:
        await engine.dispose()


async def test_the_seamstress_list_never_crosses_a_tenant(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    other_tenant = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        theirs = await _seed_staff(factory, other_tenant, display_name="זרה")
        await _seed(factory, other_tenant, assigned_staff_user_id=theirs)
        async with tenant_session(factory, tenant_id) as session:
            assert await repo.assignees(session, tenant_id) == []
    finally:
        await engine.dispose()


# --- _refreshed ---


async def test_a_zero_row_write_renders_the_stored_value_and_not_its_own_argument(
    app_role_url: str,
) -> None:
    """The identity-map trap in the shape the SERVICE has: load the row first
    (for the audit row's `from`, or to authorize a seamstress), then write.

    ⚠ THIS ONE PASSES WITHOUT `populate_existing=True` AND THE TEST BELOW IS WHY
    IT IS NOT ENOUGH. A mutation run proved it: with a single writer, SQLAlchemy's
    `evaluate` synchronization re-checks the UPDATE's criteria against the
    in-session object, finds it does not match, and declines to stamp it — so the
    plain SELECT hands back an instance that happens to be correct. The flag only
    becomes load-bearing when the in-map instance is STALE, which needs a second
    committed transaction. Kept anyway because it pins the contract this layer
    promises; the next test is what pins the mechanism.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        await _advance_to(factory, tenant_id, ticket_id, TicketStage.QC)
        winner = uuid.uuid4()
        async with tenant_session(factory, tenant_id) as session:
            await repo.claim(session, tenant_id, ticket_id, staff_user_id=winner)

        # One session, loading the row FIRST — the shape the service has, and the
        # shape that poisons without the flag.
        async with tenant_session(factory, tenant_id) as session:
            loaded = await repo.by_id(session, tenant_id, ticket_id)
            assert loaded is not None
            _, advanced = await repo.advance_stage(
                session, tenant_id, ticket_id, TicketStage.QC, at=LATER
            )
            _, claimed = await repo.claim(session, tenant_id, ticket_id, staff_user_id=uuid.uuid4())
            assert advanced is not None
            assert claimed is not None
            assert advanced.qc_at == NOW, "the refused advance rendered its own argument"
            assert claimed.assigned_staff_user_id == winner, (
                "the refused claim rendered its own argument"
            )

        async with tenant_session(factory, tenant_id) as session:
            stored = await session.scalar(
                select(AlterationTicket).where(AlterationTicket.id == ticket_id)
            )
        assert stored is not None
        assert stored.qc_at == NOW
        assert stored.assigned_staff_user_id == winner
    finally:
        await engine.dispose()


async def test_the_loser_of_a_claim_renders_the_WINNERS_row_not_its_own_stale_copy(
    app_role_url: str,
) -> None:
    """⚠ THE ONLY TEST IN THIS MODULE THAT PROVES `populate_existing=True`, and it
    exists because the mutation survived every other one.

    Two sessions, no `asyncio.gather` and no interleave — B opens INSIDE A and
    commits, which is deterministic and is all the mechanism needs. The sequence
    is the ordinary one D15 promises cannot produce a disagreement:

    1. A loads the unassigned ticket — the shape every write in this feature has,
       because each one reads the row to authorize or to audit.
    2. B claims it for the WINNER and commits.
    3. A claims it for someone else. Zero rows: the predicate
       `assigned_staff_user_id IS NULL` is now false.
    4. A's `_refreshed` must render the WINNER.

    Without the flag, step 4's SELECT finds the instance already in A's identity
    map and returns it WITHOUT overwriting its attributes — the copy A loaded at
    step 1, where the ticket was still unassigned. A's caller then answers 200
    "unassigned", a colleague's claim is invisible on her screen, and the console
    disagrees with the database it just asked. READ COMMITTED is what makes the
    fresh read see B's commit at all; the flag is what makes the ORM use it.

    `wrote` is False either way, which is exactly why both halves of every tuple
    in this module are asserted separately.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        winner, loser = uuid.uuid4(), uuid.uuid4()

        async with tenant_session(factory, tenant_id) as session_a:
            stale = await repo.by_id(session_a, tenant_id, ticket_id)
            assert stale is not None
            assert stale.assigned_staff_user_id is None

            async with tenant_session(factory, tenant_id) as session_b:
                wrote, _ = await repo.claim(session_b, tenant_id, ticket_id, staff_user_id=winner)
                assert wrote is True

            wrote, row = await repo.claim(session_a, tenant_id, ticket_id, staff_user_id=loser)
            assert wrote is False
            assert row is not None
            assert row.assigned_staff_user_id == winner, (
                "the loser rendered its own stale copy — populate_existing=True is gone"
            )
    finally:
        await engine.dispose()


# --- the forced interleaves ---
#
# ⚠ NO `asyncio.gather` ANYWHERE BELOW, deliberately, for the reason
# `test_booking_owner_db.py:1313-1336` and `test_floor_db.py:251-263` state
# verbatim: gather does not ORDER two transactions. The loser most often loads
# AFTER the winner has committed, its in-memory instance is already correct, and
# the zero-row branch each test exists to prove goes green with the mechanism
# never exercised.
#
# The mechanism used instead is `tenant_session`'s own shape. Exiting the context
# manager IS the commit (`db/tenant.py`), and two nested `tenant_session`s on one
# NullPool factory take two separate connections — so opening B INSIDE A and
# letting it exit gives, deterministically and single-threaded:
#
#     A loads (stale)  →  B writes and COMMITS  →  A writes  →  A re-reads
#
# Under READ COMMITTED A's UPDATE and A's re-read both see B's commit. That is
# every ordering these guards care about, and it is reproducible.
#
# ⚠ THE ORDER IS FORCED, NOT PREFERRED. B must commit BEFORE A writes: A's write
# takes a row lock it cannot release until the outer `async with` exits, so an
# arrangement where B writes second is not a slower test, it is a hang.


async def test_a_concurrent_advance_to_a_later_stage_refuses_the_earlier_one(
    app_role_url: str,
) -> None:
    """RACE #1 — the `AND <every later column> IS NULL` clause, proved against a
    writer whose OWN VIEW of the row says the write is legal.

    A loads the ticket at `intake`. B advances it to `ready` and commits. A then
    taps `qc` — the stage its last poll showed as next. Every column A can see is
    still NULL, so a guard written as a pre-read in Python would let this through;
    the predicate is evaluated by the DATABASE at write time, against `ready_at`
    as B just committed it, and refuses.

    Delete the later-columns clause and A stamps `qc_at` on a garment already at
    `ready`: the row then carries a qc timestamp LATER than its ready one, the
    board paints it backwards, and F44's `ready_at - in_progress_at` medians are
    computed from a trail that never happened.

    ⚠ THAT MUTATION ALSO REDS `test_an_advance_BEHIND_the_current_stage_writes_
    nothing`, and the plan's prediction that every single-writer test stays green
    is wrong on this branch: Task 3 already pins the backwards half with one
    writer. What this test pins ALONE is that the guard lives in the PREDICATE.
    Mutation-checked: replace the SQL clause with a Python guard read off
    `session.get()` — the row already in this session's identity map, which is
    the natural "I have the row, why ask again" simplification — and the
    single-writer test stays GREEN (its session never loaded the row, so the get
    goes to the database and is accurate) while this one and race #2 go RED. A
    pre-read another transaction can invalidate is not a guard, and this is the
    only test on the branch that can say so.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)

        async with tenant_session(factory, tenant_id) as session_a:
            stale = await repo.by_id(session_a, tenant_id, ticket_id)
            assert stale is not None
            assert stale.qc_at is None
            assert stale.ready_at is None  # A's whole justification for tapping qc

            async with tenant_session(factory, tenant_id) as session_b:
                wrote, _ = await repo.advance_stage(
                    session_b, tenant_id, ticket_id, TicketStage.READY, at=NOW
                )
                assert wrote is True

            wrote, row = await repo.advance_stage(
                session_a, tenant_id, ticket_id, TicketStage.QC, at=LATER
            )
            assert wrote is False
            assert row is not None

        async with tenant_session(factory, tenant_id) as session:
            stored = await session.scalar(
                select(AlterationTicket).where(AlterationTicket.id == ticket_id)
            )
        assert stored is not None
        assert stored.qc_at is None, "the loser stamped a stage the garment had already left"
        assert stored.ready_at == NOW
        assert stage_of(stored) is TicketStage.READY
    finally:
        await engine.dispose()


async def test_the_loser_of_an_advance_race_renders_the_databases_stage(
    app_role_url: str,
) -> None:
    """RACE #2 — `populate_existing=True` inside `_refreshed`, on the ADVANCE
    path.

    The same interleave as race #1, asserting the OTHER half of the tuple. A's
    UPDATE matched nothing, but SQLAlchemy's ORM-enabled DML runs `evaluate`
    synchronization by default: it re-checks the UPDATE's criteria against the
    instance in A's identity map — the stale copy A loaded, where every stamp
    after `qc` is still NULL — decides it matches, and stamps `qc_at` onto it.
    `expire_on_commit=False` then hands that object straight back.

    Without the flag A's re-read finds that poisoned instance and returns it
    WITHOUT overwriting its attributes, so A answers `qc` — her own intent, for a
    write the database refused — and the console shows a stage the garment left
    two seconds ago. With it, A renders `ready`.

    ⚠ IT MUST BE THIS SHAPE: A has to have LOADED the row before writing.
    `AtelierService.advance` does exactly that on every call, for the audit row's
    `from`. F57's note records that with only fresh-session tests present,
    removing this flag changed nothing at all.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)

        async with tenant_session(factory, tenant_id) as session_a:
            stale = await repo.by_id(session_a, tenant_id, ticket_id)
            assert stale is not None

            async with tenant_session(factory, tenant_id) as session_b:
                wrote, _ = await repo.advance_stage(
                    session_b, tenant_id, ticket_id, TicketStage.READY, at=NOW
                )
                assert wrote is True

            wrote, row = await repo.advance_stage(
                session_a, tenant_id, ticket_id, TicketStage.QC, at=LATER
            )
            assert wrote is False
            assert row is not None
            assert row.ready_at == NOW, "the loser rendered its own stale copy"
            assert row.qc_at is None, "evaluate synchronization stamped the refused value"
            assert stage_of(row) is TicketStage.READY
    finally:
        await engine.dispose()


async def test_two_seamstresses_claiming_one_ticket_leave_one_owner(
    app_role_url: str,
) -> None:
    """RACE #3 — `AND assigned_staff_user_id IS NULL` in the claim predicate.

    Two phones, one card, one unassigned ticket. Both women saw it free; the
    predicate is what makes the second tap a refusal rather than a silent
    overwrite of a colleague's claim.

    Exactly ONE of the two ids is stored afterwards, and it is the FIRST
    committer's. Delete the clause and the loser overwrites the winner: two
    seamstresses each believe the garment is theirs, and the one who claimed it
    first finds it gone from her list at the next poll with nothing anywhere
    recording that it moved.

    ⚠ Deleting the clause outright reds FOUR tests, so on its own it pins nothing
    specific to this one. The mutation that isolates it is race #1's: move the
    guard out of the predicate and read it off `session.get()` instead. The
    single-writer claim test stays GREEN — its two claims run in two fresh
    sessions, so the get is a real query — and only the two race-shaped tests go
    RED. This session loaded the ticket while it was still free, which is exactly
    the phone that shows a free card and the exact state a pre-read preserves.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        winner, loser = uuid.uuid4(), uuid.uuid4()

        async with tenant_session(factory, tenant_id) as session_a:
            stale = await repo.by_id(session_a, tenant_id, ticket_id)
            assert stale is not None
            assert stale.assigned_staff_user_id is None  # what the loser's phone showed

            async with tenant_session(factory, tenant_id) as session_b:
                wrote, _ = await repo.claim(session_b, tenant_id, ticket_id, staff_user_id=winner)
                assert wrote is True

            wrote, row = await repo.claim(session_a, tenant_id, ticket_id, staff_user_id=loser)
            assert wrote is False
            assert row is not None

        async with tenant_session(factory, tenant_id) as session:
            stored = await session.scalar(
                select(AlterationTicket).where(AlterationTicket.id == ticket_id)
            )
        assert stored is not None
        assert stored.assigned_staff_user_id == winner, "the loser overwrote the winner's claim"
    finally:
        await engine.dispose()


async def test_the_loser_of_an_elevated_reassign_renders_the_databases_row(
    app_role_url: str,
) -> None:
    """`populate_existing=True` applied to the ASSIGN path and not only to
    advance — the row that stops the flag being re-scoped to one call site, which
    is the mistake `staff_users.py`'s own `_refreshed` docstring says has bitten
    this repo three times.

    ⚠ THE PLAN NAMES THIS `test_the_loser_of_an_elevated_reassign_renders_the_
    databases_assignee` AND THAT TEST CANNOT EXIST. `assign` is deliberately
    unconditional (D9): whoever writes LAST is the database's answer, and with a
    forced interleave the second writer is always this session — so its own
    assignee IS the stored one, with the flag or without it. There is no losing
    assign.

    What IS observable, and what this asserts, is every OTHER column: A loads the
    ticket at `intake`, B advances it to `ready` and commits, A reassigns. A's
    write succeeds, so A's assignee is correct either way — but without the flag
    A's re-read hands back the instance it loaded before B committed, and A
    renders a card at `intake` with a fresh assignee. The manager reassigns a
    garment and her screen quietly rewinds its stage.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = AlterationTicketsRepository()
        ticket_id = await _seed(factory, tenant_id)
        target = uuid.uuid4()

        async with tenant_session(factory, tenant_id) as session_a:
            stale = await repo.by_id(session_a, tenant_id, ticket_id)
            assert stale is not None
            assert stale.ready_at is None

            async with tenant_session(factory, tenant_id) as session_b:
                wrote, _ = await repo.advance_stage(
                    session_b, tenant_id, ticket_id, TicketStage.READY, at=NOW
                )
                assert wrote is True

            wrote, row = await repo.assign(session_a, tenant_id, ticket_id, staff_user_id=target)
            assert wrote is True
            assert row is not None
            assert row.assigned_staff_user_id == target
            assert row.ready_at == NOW, "the reassign rendered a stage the ticket had left"
            assert stage_of(row) is TicketStage.READY
    finally:
        await engine.dispose()


# --- the service against real Postgres: the savepoint and the undo's audit row ---


def _service(factory: async_sessionmaker[AsyncSession]) -> AtelierService:
    return AtelierService(factory, clock=lambda: NOW)


def _owner(tenant_id: uuid.UUID) -> StaffContext:
    """OWNER, so `_authorize_work` returns on the role alone and this module never
    has to COMMIT a floor-role staff row — see the module docstring."""
    return StaffContext(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="owner@bella.example",
        display_name="בעלים",
        role=StaffRole.OWNER.value,
    )


async def test_two_intakes_for_one_new_phone_create_one_customer(
    app_role_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RACE #4 — D7's `session.begin_nested()` SAVEPOINT around
    `CustomersRepository.upsert`.

    ⚠ THIS RACE NEEDS ITS OWN SEAM AND A TEST WRITTEN WITHOUT ONE IS VACUOUS.
    `upsert` is read-then-insert INSIDE ONE CALL (`by_phone` → miss → add →
    flush), so for the `IntegrityError` to fire BOTH sessions must miss before
    EITHER inserts — and plain session ordering gives only two arrangements,
    neither of which is a test. Loser held open first: the loser INSERTs, holds
    the index tuple uncommitted, and the winner's flush BLOCKS on a transaction
    that cannot commit until the outer `async with` exits — single-threaded
    asyncio, so a hang. Winner first and committed: the loser's `by_phone` FINDS
    the row, never INSERTs, never enters the savepoint, and the test passes
    identically with `begin_nested()` deleted.

    The seam is therefore explicit: the `by_phone` INSIDE `upsert` returns `None`
    and, as a side effect, commits the winner's customer row from a `tenant_
    session` of its own. That forces miss → winner commits → loser INSERTs →
    `IntegrityError`, deterministically, with no `gather`. Every other call —
    `_resolve_customer`'s rename probe before the savepoint, and D7's re-read
    after it rolls back — delegates to the real method.

    ⚠ KEYED ON CALL #2, NOT #1, and the number is load-bearing rather than
    incidental: `_resolve_customer` reads `by_phone` once BEFORE the savepoint to
    answer "did this intake rename a live customer". Fire the seam on call #1 and
    `upsert`'s own read then FINDS the committed winner, updates her name to «מיכל»
    and never INSERTs — no `IntegrityError`, no savepoint, and a test that passes
    with `begin_nested()` deleted. If a future edit changes how many times this
    path reads `by_phone`, THIS is the line to move.

    Two mutations bite. Delete the savepoint (keep the `try`): the
    `IntegrityError` has aborted the enclosing transaction, so the re-read raises
    `PendingRollbackError` and the intake 500s with the ticket lost. Delete the
    whole `try`: the raw `IntegrityError` reaches the router, which is the 500
    the guard exists to prevent.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        real_by_phone = CustomersRepository.by_phone
        calls: list[str] = []
        winner_name = "מיכל לוי"

        async def seam(
            self: CustomersRepository,
            session: AsyncSession,
            tid: uuid.UUID,
            *,
            phone: str,
        ) -> Customer | None:
            calls.append(phone)
            if len(calls) == 2:
                # The other intake, in the gap between `upsert`'s miss and its
                # INSERT. A separate connection off the same NullPool factory;
                # exiting the context manager is the commit.
                async with tenant_session(factory, tid) as winner:
                    winner.add(Customer(tenant_id=tid, phone=phone, name=winner_name))
                return None
            return await real_by_phone(self, session, tid, phone=phone)

        monkeypatch.setattr(CustomersRepository, "by_phone", seam)

        ticket = await _service(factory).create(
            tenant_id,
            CreateTicketRequest(
                customer_name="מיכל",
                customer_phone="0501234567",
                due_date=DUE,
                effort_band=EffortBand.ONE_HOUR,
            ),
            actor=_owner(tenant_id),
            bands=DEFAULT_EFFORT_BANDS,
        )

        # The rename probe, the seam inside `upsert`, and the re-read after the
        # savepoint — three reads, in that order.
        assert len(calls) == 3

        async with tenant_session(factory, tenant_id) as session:
            customers = list(
                (await session.execute(select(Customer).where(Customer.phone == "+972501234567")))
                .scalars()
                .all()
            )
            stored = await session.scalar(
                select(AlterationTicket).where(AlterationTicket.id == ticket.id)
            )

        assert len(customers) == 1, "the losing intake created a second customer"
        assert stored is not None
        assert stored.customer_id == customers[0].id
        # The loser attached to the WINNER's row rather than inventing its own,
        # so the name on the wire is the one the database holds.
        assert ticket.customer_name == winner_name
        assert customers[0].name == winner_name
    finally:
        await engine.dispose()


async def test_the_undo_audit_row_carries_the_stamp_it_destroyed(app_role_url: str) -> None:
    """The previous stamp captured into a LOCAL, BEFORE the write.

    Undo is the one write in this feature that DESTROYS history: the five
    timestamps ARE the trail, and once `qc_at` is NULL the moment it held is gone
    from the row forever. The audit row's `previous_stamp` is the only place it
    survives.

    Move the capture after the write and it records `null`. `undo_stage` is
    ORM-enabled DML whose `evaluate` synchronization stamps the SET value — here
    `None` — onto the very instance `_load` just handed back out of the identity
    map, so a read taken afterwards sees the cleared column and empties the row it
    exists to fill. `test_floor_db.py::test_the_end_audit_row_carries_the_
    timestamp_the_break_actually_started` is the shipped precedent.

    ⚠ THIS MUST BE A `db` TEST. F57's note records that this mutation leaves
    every fast test green: monkeypatched repositories never stamp anything, so
    the poisoning that makes the capture load-bearing does not happen at all.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    actor = _owner(tenant_id)
    try:
        ticket_id = await _seed(factory, tenant_id)
        await _advance_to(factory, tenant_id, ticket_id, TicketStage.IN_PROGRESS, TicketStage.QC)

        await _service(factory).undo(
            tenant_id, ticket_id, StageRequest(stage=TicketStage.QC), actor=actor
        )

        async with tenant_session(factory, tenant_id) as session:
            row = await session.scalar(
                select(AuditLog).where(
                    AuditLog.action == AuditAction.ATELIER_TICKET_STAGE_UNDONE.value
                )
            )
            stored = await session.scalar(
                select(AlterationTicket).where(AlterationTicket.id == ticket_id)
            )

        assert row is not None
        assert row.details["stage"] == TicketStage.QC.value
        assert row.details["previous_stamp"] == NOW.isoformat(), (
            "the capture ran after the write and recorded the value it destroyed as null"
        )
        # And the stamp really is gone from the row, so the audit entry is the
        # only surviving record of it.
        assert stored is not None
        assert stored.qc_at is None
    finally:
        await engine.dispose()


async def test_the_advance_audit_row_names_the_stage_the_ticket_LEFT(app_role_url: str) -> None:
    """`previous = stage_of(row)` captured into a LOCAL, BEFORE the write.

    Same identity-map trap as the undo above, and it went unpinned: `_refreshed`
    re-selects the same PK in the same session with `populate_existing=True`, so
    it hands back THE SAME instance `_load` returned with the database's new
    values stamped over it. Read the stage after `advance_stage` and every
    `atelier_ticket_stage_advanced` row reads `{"from": "qc", "to": "qc"}` — a
    trail that records the destination twice and the origin never.

    ⚠ THIS MUST BE A `db` TEST, for the reason the undo's docstring gives: the
    fast fakes hand back a DIFFERENT object and never mutate the loaded row, so
    the poisoning that makes the capture load-bearing cannot happen there and the
    mutation stays green across the whole fast suite.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        ticket_id = await _seed(factory, tenant_id)
        await _advance_to(factory, tenant_id, ticket_id, TicketStage.IN_PROGRESS)

        await _service(factory).advance(
            tenant_id, ticket_id, StageRequest(stage=TicketStage.QC), actor=_owner(tenant_id)
        )

        async with tenant_session(factory, tenant_id) as session:
            row = await session.scalar(
                select(AuditLog).where(
                    AuditLog.action == AuditAction.ATELIER_TICKET_STAGE_ADVANCED.value
                )
            )

        assert row is not None
        assert row.details["to"] == TicketStage.QC.value
        assert row.details["from"] == TicketStage.IN_PROGRESS.value, (
            "the capture ran after the write, so `from` is the stage the ticket "
            "ARRIVED at and the row names its destination twice"
        )
    finally:
        await engine.dispose()


async def test_the_assign_audit_row_names_the_staffer_who_HELD_the_ticket(
    app_role_url: str,
) -> None:
    """`before = row.assigned_staff_user_id` captured into a LOCAL, BEFORE the
    write — and here the capture does not merely corrupt the row, it DELETES it.

    `assign` writes its audit row only when `refreshed.assigned_staff_user_id !=
    before`. `_refreshed` returns the same identity-mapped instance the write
    just stamped, so a capture taken afterwards compares one attribute against
    itself: never unequal, never audited, and D11's from/to trail for assignment
    silently stops existing. The undo's `previous_stamp` fails loudly by
    recording a null; this one fails by recording nothing at all.

    An ELEVATED release, deliberately: it is the assign path that changes the
    holder without `_require_seamstress`, so this module never has to COMMIT a
    floor-role staff row (see the module docstring). The repository's assign
    verbs take an id and never look it up.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    held_by = uuid.uuid4()
    try:
        ticket_id = await _seed(factory, tenant_id, assigned_staff_user_id=held_by)

        await _service(factory).assign(
            tenant_id,
            ticket_id,
            AssignTicketRequest(staff_user_id=None),
            actor=_owner(tenant_id),
        )

        async with tenant_session(factory, tenant_id) as session:
            row = await session.scalar(
                select(AuditLog).where(AuditLog.action == AuditAction.ATELIER_TICKET_ASSIGNED.value)
            )

        assert row is not None, (
            "no assignment audit row at all — the capture ran after the write, so "
            "the from/to comparison was the new value against itself"
        )
        assert row.details["from"] == str(held_by)
        assert row.details["to"] is None
    finally:
        await engine.dispose()


async def test_an_intake_that_RENAMES_a_returning_customer_leaves_a_trail(
    app_role_url: str,
) -> None:
    """D6's accepted risk, made recoverable.

    `CustomersRepository.upsert` assigns `existing.name = name` UNCONDITIONALLY,
    so a seamstress typing «מ» at the counter for a phone stored as «מיכל לוי»
    rewrites that customer's name — on a screen (F53's CustomerDetail) she has no
    permission to open, from a router that admits her. Intake is the first writer
    of `customers.name` in this product whose actor does not control the phone;
    the booking path proves the phone with an OTP first.

    The deck's mitigation — a notice beside the phone field naming the stored
    name — is NOT BUILDABLE as specified: it needs the stored name BEFORE submit,
    the plan forbids a new endpoint, and the whole customers router is
    owner + shift_manager while intake admits a seamstress. So the rename is
    recorded instead of previewed: an owner can ask WHO renamed WHICH customer
    and WHEN, which is the question the CRM cannot otherwise answer at all.

    ⚠ THE ROW NAMES THE FIELD AND NEVER THE VALUES, D11's rule and
    `CUSTOMER_UPDATED`'s shape: `audit_log` has a different retention clock from
    the row it describes, and both the old and the new spelling of a bride's name
    are hers.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    stored_name = "מיכל לוי"
    try:
        async with tenant_session(factory, tenant_id) as session:
            customer = await CustomersRepository().upsert(
                session, tenant_id, phone="+972501234567", name=stored_name
            )
            customer_id = customer.id

        service = _service(factory)
        request = CreateTicketRequest(
            customer_name="מ",
            customer_phone="0501234567",
            due_date=DUE,
            effort_band=EffortBand.ONE_HOUR,
        )
        await service.create(
            tenant_id, request, actor=_owner(tenant_id), bands=DEFAULT_EFFORT_BANDS
        )
        # A SECOND intake typing the same «מ» renames nothing and must write no
        # second row — otherwise every repeat visit logs a rename that did not
        # happen and the trail stops meaning anything.
        await service.create(
            tenant_id, request, actor=_owner(tenant_id), bands=DEFAULT_EFFORT_BANDS
        )

        async with tenant_session(factory, tenant_id) as session:
            rows = list(
                (
                    await session.execute(
                        select(AuditLog).where(
                            AuditLog.action == AuditAction.ATELIER_CUSTOMER_RENAMED.value
                        )
                    )
                )
                .scalars()
                .all()
            )

        assert len(rows) == 1, "one rename happened; the second intake changed nothing"
        assert rows[0].entity == str(customer_id)
        assert rows[0].details == {"field": "name"}
        assert stored_name not in str(rows[0].details)
    finally:
        await engine.dispose()
