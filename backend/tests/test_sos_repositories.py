"""F37's two repositories against real Postgres as the non-owner app role.

⚠ **Every row this module COMMITS holds `owner` or `shift_manager`, never a
floor role** — `test_floor_db.py:10-32`'s rule verbatim, and it is a hard rule
rather than a preference. `migrated_db` and `app_role_url` are session-scoped,
pytest collects alphabetically, and a committed `reception` row reddens three
tests in `test_migrations.py` that have nothing to do with SOS. Nothing here
asserts anything about the actor's role: the audience rule is the service's job.

**Both operands of every timestamp assertion are frozen module constants.** The
reachability probe takes `now` as an argument and the accept takes `at`, exactly
so this module can assert equalities instead of ranges — a test that goes green
or red on machine speed will be re-run until it passes, which is how a mutation
regime rots.

Every test mints its own tenant id: the container is session-scoped and nothing
here truncates.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.db.repositories.fitting_room_assignments import FittingRoomAssignmentsRepository
from app.db.repositories.fitting_rooms import FittingRoomsRepository
from app.db.repositories.sessions import SessionsRepository
from app.db.repositories.sos_alerts import SosAlertsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.models.constants import SosStatus, StaffRole
from app.models.fitting_room import FittingRoom
from app.models.fitting_room_assignment import FittingRoomAssignment
from app.models.sos_alert import SosAlert
from app.models.staff_user import StaffUser

pytestmark = pytest.mark.db

NOW = datetime(2026, 8, 3, 11, 20, tzinfo=UTC)
LATER = datetime(2026, 8, 3, 13, 45, tzinfo=UTC)


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
    role: str = StaffRole.OWNER.value,
) -> uuid.UUID:
    assert role in {StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value}, (
        "this module COMMITS its rows; a floor role here reddens test_migrations.py"
    )
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=f"sos-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name=display_name,
            role=role,
        )
        return staff.id


async def _seed_session(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    staff_id: uuid.UUID,
    *,
    expires_at: datetime,
    revoked: bool = False,
) -> None:
    async with tenant_session(factory, tenant_id) as session:
        row = await SessionsRepository().insert(
            session,
            tenant_id=tenant_id,
            staff_user_id=staff_id,
            token_hash=uuid.uuid4().hex,
            expires_at=expires_at,
        )
        if revoked:
            row.deleted_at = NOW


async def _seed_assignment(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    staff_id: uuid.UUID,
    *,
    label: str = "חדר 2",
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        room = await FittingRoomsRepository().insert(session, tenant_id, label=label, sort_order=0)
        assignment = await FittingRoomAssignmentsRepository().claim(
            session, tenant_id, room_id=room.id, staff_id=staff_id, booking_id=None
        )
        return assignment.id


async def _insert_alert(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    raised_by: uuid.UUID,
    target: uuid.UUID | None = None,
    assignment_id: uuid.UUID | None = None,
    note: str | None = None,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        alert = await SosAlertsRepository().insert(
            session,
            tenant_id,
            raised_by=raised_by,
            target_staff_user_id=target,
            fitting_room_assignment_id=assignment_id,
            note=note,
        )
        return alert.id


# --- the reachability probe --------------------------------------------------


async def test_a_fresh_session_is_reachable(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        await _seed_session(factory, tenant_id, staff_id, expires_at=LATER)
        async with tenant_session(factory, tenant_id) as session:
            assert await SessionsRepository().has_live_session(session, tenant_id, staff_id, NOW)
    finally:
        await engine.dispose()


async def test_an_expired_session_is_not_reachable(app_role_url: str) -> None:
    """⚠ **THE MUTATION TARGET for `expires_at > :now`, and the raise's own row
    is what it protects.** Drop the conjunct and an expired session reads as
    live: the page is stored against a staffer whose cookie is dead, `rerouted`
    comes back false, the raiser is told a named colleague is coming, and the
    alert reaches NOBODY until the thirty-second escalation. That is the exact
    silent drop this feature forbids. Every test whose target has a fresh session
    stays green."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        await _seed_session(factory, tenant_id, staff_id, expires_at=NOW - timedelta(minutes=1))
        async with tenant_session(factory, tenant_id) as session:
            assert not await SessionsRepository().has_live_session(
                session, tenant_id, staff_id, NOW
            )
    finally:
        await engine.dispose()


async def test_a_revoked_session_is_not_reachable(app_role_url: str) -> None:
    """`deleted_at` is stamped by a password change and by deactivation. Both
    mean the cookie is dead, so both mean a named target is unreachable."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        await _seed_session(factory, tenant_id, staff_id, expires_at=LATER, revoked=True)
        async with tenant_session(factory, tenant_id) as session:
            assert not await SessionsRepository().has_live_session(
                session, tenant_id, staff_id, NOW
            )
    finally:
        await engine.dispose()


async def test_a_staffer_who_never_signed_in_is_not_reachable(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            assert not await SessionsRepository().has_live_session(
                session, tenant_id, staff_id, NOW
            )
    finally:
        await engine.dispose()


async def test_another_tenants_live_session_does_not_make_her_reachable(
    app_role_url: str,
) -> None:
    """One id, two boutiques. RLS carries this, and the explicit `tenant_id`
    predicate is defence-in-depth beside it — which is exactly why this test
    would stay GREEN if the predicate were dropped, and why the claim lives in
    the docstring rather than in an assertion pretending otherwise."""
    engine, factory = _factory(app_role_url)
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, theirs)
        await _seed_session(factory, theirs, staff_id, expires_at=LATER)
        async with tenant_session(factory, mine) as session:
            assert not await SessionsRepository().has_live_session(session, mine, staff_id, NOW)
    finally:
        await engine.dispose()


# --- the room pointer --------------------------------------------------------


async def test_her_own_assignment_resolves(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        assignment_id = await _seed_assignment(factory, tenant_id, staff_id)
        async with tenant_session(factory, tenant_id) as session:
            row = await SosAlertsRepository().assignment_of(
                session, tenant_id, assignment_id, staff_id
            )
        assert row is not None
        assert row.id == assignment_id
    finally:
        await engine.dispose()


async def test_another_staffers_assignment_does_not_resolve(app_role_url: str) -> None:
    """⚠ **The `staff_user_id` conjunct is not tidiness and this is the ONLY test
    that fails without it.** F36's floor payload hands `RoomAssignment.id` out on
    every occupied tile to all five roles, so without the conjunct any staffer
    could raise with any assignment id in her own tenant and the page would
    render «דנה קוראת לעזרה — חדר 2» while Dana is standing in room 4.

    «No room» is a defined, safe state; «wrong room» is not, and in an emergency
    it is strictly worse — the responder walks to a closed curtain with a
    stranger's bride behind it. The alert is still created either way, which is
    precisely why nothing else in the feature notices."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        hers = await _seed_staff(factory, tenant_id, display_name="Dana")
        mine = await _seed_staff(factory, tenant_id, display_name="Noa")
        assignment_id = await _seed_assignment(factory, tenant_id, hers)
        async with tenant_session(factory, tenant_id) as session:
            assert (
                await SosAlertsRepository().assignment_of(session, tenant_id, assignment_id, mine)
                is None
            )
    finally:
        await engine.dispose()


async def test_a_released_assignment_still_resolves(app_role_url: str) -> None:
    """⚠ **NO `released_at` filter, and that is the decision.** She raises from
    the room she is standing in; the fitting can end between the tap and the
    write, and a page that loses its room because a colleague pressed «שוחרר» is
    a page that renders «no room» for no reason a human would accept."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        assignment_id = await _seed_assignment(factory, tenant_id, staff_id)
        async with tenant_session(factory, tenant_id) as session:
            await FittingRoomAssignmentsRepository().release(
                session, tenant_id, assignment_id, at=NOW
            )
        async with tenant_session(factory, tenant_id) as session:
            row = await SosAlertsRepository().assignment_of(
                session, tenant_id, assignment_id, staff_id
            )
        assert row is not None
        assert row.released_at == NOW
    finally:
        await engine.dispose()


async def test_a_soft_deleted_assignment_does_not_resolve(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        assignment_id = await _seed_assignment(factory, tenant_id, staff_id)
        async with tenant_session(factory, tenant_id) as session:
            await session.execute(
                update(FittingRoomAssignment)
                .where(FittingRoomAssignment.id == assignment_id)
                .values(deleted_at=NOW)
            )
        async with tenant_session(factory, tenant_id) as session:
            assert (
                await SosAlertsRepository().assignment_of(
                    session, tenant_id, assignment_id, staff_id
                )
                is None
            )
    finally:
        await engine.dispose()


# --- insert and the by-id read -----------------------------------------------


async def test_an_insert_stores_every_field_and_opens_the_alert(app_role_url: str) -> None:
    """⚠ **One plain INSERT — no lock, no savepoint, no ON CONFLICT.** There is
    no unique index on this table, therefore no `IntegrityError` to recover from,
    therefore nothing for a savepoint to roll back to. `violated_index()` lives in
    the neighbouring module and is exactly the thing not to import here."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        target = await _seed_staff(factory, tenant_id, display_name="Dana")
        assignment_id = await _seed_assignment(factory, tenant_id, raiser)
        alert_id = await _insert_alert(
            factory,
            tenant_id,
            raised_by=raiser,
            target=target,
            assignment_id=assignment_id,
            note="צריך סיכות",
        )
        async with tenant_session(factory, tenant_id) as session:
            row = await SosAlertsRepository().by_id(session, tenant_id, alert_id)
        assert row is not None
        assert row.raised_by == raiser
        assert row.target_staff_user_id == target
        assert row.fitting_room_assignment_id == assignment_id
        assert row.note == "צריך סיכות"
        assert row.status == SosStatus.OPEN
        assert row.accepted_by is None
        assert row.acknowledged_at is None
    finally:
        await engine.dispose()


async def test_a_role_targeted_alert_stores_a_null_target(app_role_url: str) -> None:
    """NULL is the shift-manager ROLE, and it is the DEFAULT rather than an edge
    case: it is what a staffer alone with a bride actually taps."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id)
        alert_id = await _insert_alert(factory, tenant_id, raised_by=raiser)
        async with tenant_session(factory, tenant_id) as session:
            row = await SosAlertsRepository().by_id(session, tenant_id, alert_id)
        assert row is not None
        assert row.target_staff_user_id is None
        assert row.fitting_room_assignment_id is None
        assert row.note is None
    finally:
        await engine.dispose()


async def test_by_id_does_not_filter_on_status(app_role_url: str) -> None:
    """⚠ **NO `status` filter, `fitting_room_assignments.by_id`'s reason.**
    Filtering here would make a LOSING accept read as ABSENT and answer 404 —
    instead of the 409 that names the owner, which is the one thing the ruling
    requires of it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id)
        acceptor = await _seed_staff(factory, tenant_id, display_name="Dana")
        alert_id = await _insert_alert(factory, tenant_id, raised_by=raiser)
        async with tenant_session(factory, tenant_id) as session:
            await SosAlertsRepository().accept(
                session, tenant_id, alert_id, actor_id=acceptor, at=NOW
            )
        async with tenant_session(factory, tenant_id) as session:
            row = await SosAlertsRepository().by_id(session, tenant_id, alert_id)
        assert row is not None
        assert row.status == SosStatus.ACCEPTED
    finally:
        await engine.dispose()


async def test_another_tenants_alert_is_not_readable(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, theirs)
        alert_id = await _insert_alert(factory, theirs, raised_by=raiser)
        async with tenant_session(factory, mine) as session:
            assert await SosAlertsRepository().by_id(session, mine, alert_id) is None
    finally:
        await engine.dispose()


# --- the guarded accept ------------------------------------------------------


async def test_an_accept_writes_status_owner_and_timestamp_in_one_statement(
    app_role_url: str,
) -> None:
    """`status` and `accepted_by` are set by ONE statement, so «accepted with
    nobody» and «open but owned» are both unrepresentable. The obvious two-step —
    stamp the owner, then flip the status — reintroduces the whole race this verb
    exists to close.

    `acknowledged_at` comes from the caller's clock rather than SQL `now()`,
    which is why this is an equality and not a range."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id)
        acceptor = await _seed_staff(factory, tenant_id, display_name="Dana")
        alert_id = await _insert_alert(factory, tenant_id, raised_by=raiser)
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await SosAlertsRepository().accept(
                session, tenant_id, alert_id, actor_id=acceptor, at=NOW
            )
        assert wrote is True
        assert row is not None
        assert row.status == SosStatus.ACCEPTED
        assert row.accepted_by == acceptor
        assert row.acknowledged_at == NOW

        # Its OWN session, so the assertion cannot be satisfied by the instance
        # the write left in the first session's identity map.
        async with tenant_session(factory, tenant_id) as session:
            stored = await SosAlertsRepository().by_id(session, tenant_id, alert_id)
        assert stored is not None
        assert stored.accepted_by == acceptor
        assert stored.acknowledged_at == NOW
    finally:
        await engine.dispose()


async def test_a_second_accept_landing_in_the_gap_renders_the_winners_owner(
    app_role_url: str,
) -> None:
    """⚠ **THE FORCED INTERLEAVE, and the two mutations it is the only test for.**

    `asyncio.gather` is deliberately NOT used, for `test_floor_db.py:251-263`'s
    reason verbatim: gather does not ORDER two transactions, so the loser most
    often runs after the winner commits, the in-memory instance is already
    correct, and the zero-row branch goes green without the mechanism ever being
    exercised. The mechanism here is that `tenant_session` is
    `async with session_factory() as session, session.begin()`, so EXITING the
    context manager IS the commit, and two nested ones on a NullPool factory take
    two separate connections.

    THE ORDER: the loser opens and READS (a plain SELECT, no row locks) -> the
    winner's inner block opens, writes and EXITS, which is the commit -> only
    then does the loser's guarded UPDATE run, and it matches zero rows
    immediately. Nothing blocks and nothing can hang: a guarded UPDATE against an
    already-committed row RETURNS rather than waiting.

    MUTATION 1 — drop `AND status = 'open'` from the predicate. The loser then
    OVERWRITES the winner: `accepted_by` flips to the second responder, the first
    is never told, and two people walk to one curtain while a third emergency
    goes unanswered. Every other accept test accepts once, so this is the only
    test that fails.

    MUTATION 2 — drop `populate_existing=True` from the re-read. `update()` is
    ORM-enabled DML whose default `evaluate` synchronization re-evaluates the
    predicate IN PYTHON against the identity-mapped instance, which still reads
    `open`, so it stamps this request's OWN owner onto a row the database never
    touched — and the 409 would then NAME THE WRONG PERSON. Every test that opens
    a fresh session per operation has an empty identity map and cannot see it.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        repo = SosAlertsRepository()
        raiser = await _seed_staff(factory, tenant_id)
        winner = await _seed_staff(factory, tenant_id, display_name="Dana")
        loser = await _seed_staff(factory, tenant_id, display_name="Rina")
        alert_id = await _insert_alert(factory, tenant_id, raised_by=raiser)

        # The LOSER's session, held open across the winner's whole transaction.
        async with tenant_session(factory, tenant_id) as losing:
            loaded = await repo.by_id(losing, tenant_id, alert_id)
            assert loaded is not None
            assert loaded.status == SosStatus.OPEN  # the predicate WOULD match

            async with tenant_session(factory, tenant_id) as winning:
                won, _ = await repo.accept(winning, tenant_id, alert_id, actor_id=winner, at=NOW)
                assert won is True

            wrote, row = await repo.accept(losing, tenant_id, alert_id, actor_id=loser, at=LATER)

        assert wrote is False
        assert row is not None
        # The DATABASE's answer, not this request's own intent — this is the row
        # the 409's `details` is built from.
        assert row.accepted_by == winner
        assert row.accepted_by != loser
        assert row.acknowledged_at == NOW

        async with tenant_session(factory, tenant_id) as session:
            stored = await repo.by_id(session, tenant_id, alert_id)
        assert stored is not None
        assert stored.accepted_by == winner
        assert stored.acknowledged_at == NOW
    finally:
        await engine.dispose()


async def test_an_accept_of_a_missing_alert_reports_neither_a_write_nor_a_row(
    app_role_url: str,
) -> None:
    """`(False, None)` is the 404 and `(False, row)` is the 409 — the pair is
    what separates «somebody else has it» from «there is no such alert», and the
    service cannot tell them apart without both halves."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        async with tenant_session(factory, tenant_id) as session:
            wrote, row = await SosAlertsRepository().accept(
                session, tenant_id, uuid.uuid4(), actor_id=staff_id, at=NOW
            )
        assert wrote is False
        assert row is None
    finally:
        await engine.dispose()


async def test_an_accept_never_touches_another_tenants_alert(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, theirs)
        alert_id = await _insert_alert(factory, theirs, raised_by=raiser)
        intruder = await _seed_staff(factory, mine)
        async with tenant_session(factory, mine) as session:
            wrote, row = await SosAlertsRepository().accept(
                session, mine, alert_id, actor_id=intruder, at=NOW
            )
        assert wrote is False
        assert row is None

        async with tenant_session(factory, theirs) as session:
            stored = await session.scalar(select(SosAlert).where(SosAlert.id == alert_id))
        assert stored is not None
        assert stored.status == SosStatus.OPEN
        assert stored.accepted_by is None
    finally:
        await engine.dispose()


# --- the payload read: one statement, five LEFT JOINs -------------------------
#
# ⚠ **`actor_id=None` IS the elevated caller** — the repository takes an id and
# never a role, so which roles are elevated stays `ELEVATED_ROLES`' decision in
# the service. That is also what lets the audience clause be tested at all in a
# module forbidden from committing a floor role: nothing here needs one.


async def test_the_live_read_resolves_the_raiser_the_target_the_acceptor_and_the_room(
    app_role_url: str,
) -> None:
    """D10's whole join chain in one row — and NO customer datum reaches it. The
    assignment is bound to a booking on the floor payload; this read never goes
    near `bookings` or `customers`, which is the largest privacy decision in the
    feature expressed as an absent join."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="נועה")
        dana = await _seed_staff(factory, tenant_id, display_name="דנה")
        assignment_id = await _seed_assignment(factory, tenant_id, raiser, label="חדר 2")
        alert_id = await _insert_alert(
            factory,
            tenant_id,
            raised_by=raiser,
            target=dana,
            assignment_id=assignment_id,
            note="צריך סיכות",
        )
        async with tenant_session(factory, tenant_id) as session:
            await SosAlertsRepository().accept(session, tenant_id, alert_id, actor_id=dana, at=NOW)
        async with tenant_session(factory, tenant_id) as session:
            rows = await SosAlertsRepository().live_for(session, tenant_id, actor_id=None)
        assert len(rows) == 1
        row = rows[0]
        assert row.alert.id == alert_id
        assert row.alert.note == "צריך סיכות"
        assert row.raised_by_name == "נועה"
        assert row.target_name == "דנה"
        assert row.accepted_by_name == "דנה"
        assert row.room_label == "חדר 2"
    finally:
        await engine.dispose()


async def test_a_removed_raiser_still_names_the_page(app_role_url: str) -> None:
    """⚠ **The three `staff_users` joins carry NO `deleted_at` filter**, and add
    one to any of them and this reds. F36's ghost-holder rule: a staffer removed
    mid-page still has a name, and an alert that cannot say who called is worse
    than one naming a departed colleague."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="נועה")
        alert_id = await _insert_alert(factory, tenant_id, raised_by=raiser)
        async with tenant_session(factory, tenant_id) as session:
            await session.execute(
                update(StaffUser).where(StaffUser.id == raiser).values(deleted_at=NOW)
            )
        async with tenant_session(factory, tenant_id) as session:
            rows = await SosAlertsRepository().live_for(session, tenant_id, actor_id=None)
        assert [row.alert.id for row in rows] == [alert_id]
        assert rows[0].raised_by_name == "נועה"
    finally:
        await engine.dispose()


async def test_a_released_assignment_still_resolves_its_room_label(app_role_url: str) -> None:
    """⚠ **NO `released_at` filter on the assignment join and NO `deleted_at`
    filter on the rooms join** — F36's Risk 1(c), decided there and handed here
    verbatim. The fitting ends while the page is open and the owner may then
    soft-delete the room; the alert must still say WHERE. A room label is not
    personal data, so the no-snapshot rule does not reach it."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="נועה")
        assignment_id = await _seed_assignment(factory, tenant_id, raiser, label="חדר 2")
        alert_id = await _insert_alert(
            factory, tenant_id, raised_by=raiser, assignment_id=assignment_id
        )
        async with tenant_session(factory, tenant_id) as session:
            _, assignment = await FittingRoomAssignmentsRepository().release(
                session, tenant_id, assignment_id, at=NOW
            )
            assert assignment is not None
            await session.execute(
                update(FittingRoom)
                .where(FittingRoom.id == assignment.fitting_room_id)
                .values(deleted_at=NOW)
            )
        async with tenant_session(factory, tenant_id) as session:
            rows = await SosAlertsRepository().live_for(session, tenant_id, actor_id=None)
        assert [row.alert.id for row in rows] == [alert_id]
        assert rows[0].room_label == "חדר 2"
    finally:
        await engine.dispose()


async def test_an_alert_whose_every_pointer_was_swept_still_renders(app_role_url: str) -> None:
    """All five joins are LEFT, so the card renders with nulls and says so — an
    alert that vanishes because a pointer did is a page silently dropped."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        ghost = uuid.uuid4()
        alert_id = await _insert_alert(
            factory, tenant_id, raised_by=ghost, target=uuid.uuid4(), assignment_id=uuid.uuid4()
        )
        async with tenant_session(factory, tenant_id) as session:
            rows = await SosAlertsRepository().live_for(session, tenant_id, actor_id=None)
        assert [row.alert.id for row in rows] == [alert_id]
        assert rows[0].raised_by_name is None
        assert rows[0].target_name is None
        assert rows[0].accepted_by_name is None
        assert rows[0].room_label is None
    finally:
        await engine.dispose()


async def test_the_live_read_carries_the_open_and_the_accepted_and_nothing_else(
    app_role_url: str,
) -> None:
    """The predicate is `idx_sos_alerts_live`'s, byte for byte, so the planner
    uses it — and a resolved alert is history the console has no reader for."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id)
        open_id = await _insert_alert(factory, tenant_id, raised_by=raiser)
        accepted_id = await _insert_alert(factory, tenant_id, raised_by=raiser)
        resolved_id = await _insert_alert(factory, tenant_id, raised_by=raiser)
        cancelled_id = await _insert_alert(factory, tenant_id, raised_by=raiser)
        swept_id = await _insert_alert(factory, tenant_id, raised_by=raiser)
        async with tenant_session(factory, tenant_id) as session:
            await SosAlertsRepository().accept(
                session, tenant_id, accepted_id, actor_id=raiser, at=NOW
            )
            await session.execute(
                update(SosAlert).where(SosAlert.id == resolved_id).values(status=SosStatus.RESOLVED)
            )
            await session.execute(
                update(SosAlert)
                .where(SosAlert.id == cancelled_id)
                .values(status=SosStatus.CANCELLED)
            )
            await session.execute(
                update(SosAlert).where(SosAlert.id == swept_id).values(deleted_at=NOW)
            )
        async with tenant_session(factory, tenant_id) as session:
            rows = await SosAlertsRepository().live_for(session, tenant_id, actor_id=None)
        assert {row.alert.id for row in rows} == {open_id, accepted_id}
    finally:
        await engine.dispose()


async def test_the_live_read_is_oldest_first(app_role_url: str) -> None:
    """OLDEST first, and it is not a preference: the overlay and the centre both
    render this order, and the longest-waiting emergency is the one at the top."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id)
        first = await _insert_alert(factory, tenant_id, raised_by=raiser)
        second = await _insert_alert(factory, tenant_id, raised_by=raiser)
        third = await _insert_alert(factory, tenant_id, raised_by=raiser)
        async with tenant_session(factory, tenant_id) as session:
            rows = await SosAlertsRepository().live_for(session, tenant_id, actor_id=None)
        assert [row.alert.id for row in rows] == [first, second, third]
    finally:
        await engine.dispose()


async def test_an_elevated_caller_sees_every_alert_in_the_tenant(app_role_url: str) -> None:
    """She is the fallback, so «never silently dropped» requires it: a shift
    manager sees every alert from the instant it is raised — an alert she neither
    raised, was named on, nor owns. Whether one RISES on her device is a separate,
    narrower predicate.

    Elevation is spelled `actor_id=None` here; WHICH roles spell it that way is
    the service's `ELEVATED_ROLES` test, not this module's."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        stranger = await _seed_staff(factory, tenant_id, display_name="Rina")
        alert_id = await _insert_alert(factory, tenant_id, raised_by=stranger)
        async with tenant_session(factory, tenant_id) as session:
            rows = await SosAlertsRepository().live_for(session, tenant_id, actor_id=None)
        assert [row.alert.id for row in rows] == [alert_id]
    finally:
        await engine.dispose()


async def test_a_floor_role_sees_only_the_three_alerts_that_are_hers(app_role_url: str) -> None:
    """⚠ **THE audience clause, and the mutation is dropping the `or_(...)`.**
    Hers are the one she raised (so she sees the accept), the one she was named
    on, and the one she owns. A stranger's page is not hers to see — and the
    whole reason the overlay can be app-level on eleven sections is that this
    filter runs on the SERVER."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        her = await _seed_staff(factory, tenant_id, display_name="Noa")
        stranger = await _seed_staff(factory, tenant_id, display_name="Rina")
        raised = await _insert_alert(factory, tenant_id, raised_by=her)
        named = await _insert_alert(factory, tenant_id, raised_by=stranger, target=her)
        owned = await _insert_alert(factory, tenant_id, raised_by=stranger)
        await _insert_alert(factory, tenant_id, raised_by=stranger)
        async with tenant_session(factory, tenant_id) as session:
            await SosAlertsRepository().accept(session, tenant_id, owned, actor_id=her, at=NOW)
        async with tenant_session(factory, tenant_id) as session:
            rows = await SosAlertsRepository().live_for(session, tenant_id, actor_id=her)
        assert {row.alert.id for row in rows} == {raised, named, owned}
    finally:
        await engine.dispose()


async def test_the_live_read_never_crosses_a_tenant_boundary(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, theirs)
        await _insert_alert(factory, theirs, raised_by=raiser)
        async with tenant_session(factory, mine) as session:
            rows = await SosAlertsRepository().live_for(session, mine, actor_id=None)
        assert rows == []
    finally:
        await engine.dispose()


async def test_the_view_of_one_alert_answers_a_closed_one_too(app_role_url: str) -> None:
    """⚠ **NO status filter here, and it is `by_id`'s reason applied to the
    ANSWER instead of the decision**: a resolve answers the row it just closed,
    and a read that dropped it would leave the console patching a card from
    nothing."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="נועה")
        alert_id = await _insert_alert(factory, tenant_id, raised_by=raiser)
        async with tenant_session(factory, tenant_id) as session:
            await session.execute(
                update(SosAlert).where(SosAlert.id == alert_id).values(status=SosStatus.RESOLVED)
            )
        async with tenant_session(factory, tenant_id) as session:
            row = await SosAlertsRepository().view_of(session, tenant_id, alert_id)
            missing = await SosAlertsRepository().view_of(session, tenant_id, uuid.uuid4())
        assert row is not None
        assert row.alert.status == SosStatus.RESOLVED
        assert row.raised_by_name == "נועה"
        assert missing is None
    finally:
        await engine.dispose()
