"""F37's forced interleaves: the five gaps only a real Postgres can settle.

**The only defect class this feature really has is an alert that is silently
lost**, and every case below is one gap away from producing one — a second
responder overwriting the first, a cancel closing an emergency behind a
colleague already walking to that curtain, a page refused because a target's
cookie expired between two statements. `test_sos_db.py` covers each verb's
SEQUENTIAL shape; this file covers what happens when two of them land in the
same instant.

**Why `asyncio.gather` is deliberately not used**, `test_floor_db.py:251-263`
verbatim and for the same reason: gather does not ORDER two transactions, so the
loser most often runs after the winner has committed, the in-memory instance is
already correct, and the zero-row branch these tests exist to prove goes green
without the mechanism ever being exercised. The mechanism is that
`tenant_session` is `async with session_factory() as session, session.begin()`,
so EXITING the context manager IS the commit (`db/tenant.py:25`), and two nested
`tenant_session`s on one `NullPool` factory take two separate connections.
Nothing here can hang: a guarded UPDATE against a committed row RETURNS rather
than waiting, and the loser holds no row lock because its read is a plain SELECT.

**Why the seam needs `_GapRepository` and cannot be arranged from outside.**
Every verb opens its own `tenant_session`, reads the row, decides and writes
inside ONE `async with`, so from the caller's side there is no instant between
the read and the write to land a contender in — which is exactly why
`test_sos_db.py`'s two "race" tests are really sequential and why the shipped
`test_a_cancel_racing_an_accept_never_strands_the_responder` cannot see
`populate_existing`. The seam is one call deep. `_GapRepository` is the only
thing in this file that is not shipped code.

⚠ **Every row this module COMMITS holds `owner` or `shift_manager`, never a floor
role** (`test_floor_db.py:10-32`): `migrated_db` is session-scoped, pytest
collects alphabetically, and a committed `reception` row reddens three tests in
`test_migrations.py` that have nothing to do with SOS.

⚠ **An audit-row count here proves a WRITE, never a no-op.** `tenant_session` is
`session.begin()`, so a refusal rolls its whole transaction back and an audit row
written unconditionally before the raise would never commit — `test_sos_db.py`'s
module docstring records the mutation. What the counts below assert is that
exactly ONE contender committed, which is the whole of first-accept-owns.
"""

import uuid
from collections.abc import Awaitable, Callable
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

from app.auth.service import StaffContext
from app.db.repositories.sessions import SessionsRepository
from app.db.repositories.sos_alerts import SosAlertRow, SosAlertsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.floor.service import FloorService
from app.floor.validation import SosAlreadyAcceptedError, SosClosedError
from app.models.audit_log import AuditLog
from app.models.constants import AuditAction, SosStatus, StaffRole
from app.models.sos_alert import SosAlert

pytestmark = pytest.mark.db

NOW = datetime(2026, 8, 3, 11, 20, tzinfo=UTC)
LATER = datetime(2026, 8, 3, 13, 45, tzinfo=UTC)


class _GapRepository(SosAlertsRepository):
    """The shipped repository, plus one callback that fires ONCE immediately
    before a named method and from INSIDE the caller's already-open transaction.

    That placement is the whole point. `accept_sos` has already read the row and
    decided it is open; the contender then commits on its own connection; only
    then does the guarded UPDATE run, against a row that moved underneath it.
    Reversing the order — contender first, then the whole verb — is the
    SEQUENTIAL shape `test_sos_db.py` already covers, and it cannot see the
    identity map at all.

    One hook, keyed by name, rather than five subclasses: the five races differ
    only in where the seam is.

    ⚠ **`fired` is public and asserted**, because a hook that silently never runs
    turns a race test into a sequential one that passes for the wrong reason —
    and in `test_a_target_whose_session_dies_in_the_gap_still_gets_the_page` it
    would pass VACUOUSLY, since a target who never signed out is reachable
    anyway. Three of the tests below fail loudly if the seam does not open; that
    one would not.
    """

    def __init__(self, before: str, run: Callable[[], Awaitable[None]]) -> None:
        self._before = before
        self._run = run
        self.fired = False

    async def _gap(self, name: str) -> None:
        if name != self._before or self.fired:
            return
        # Once: a verb that reads its row back through the same method would
        # otherwise re-run the contender against a row it has already moved.
        self.fired = True
        await self._run()

    async def insert(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        *,
        raised_by: uuid.UUID,
        target_staff_user_id: uuid.UUID | None,
        fitting_room_assignment_id: uuid.UUID | None,
        note: str | None,
    ) -> SosAlert:
        await self._gap("insert")
        return await super().insert(
            session,
            tenant_id,
            raised_by=raised_by,
            target_staff_user_id=target_staff_user_id,
            fitting_room_assignment_id=fitting_room_assignment_id,
            note=note,
        )

    async def accept(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        alert_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        at: datetime,
    ) -> tuple[bool, SosAlert | None]:
        await self._gap("accept")
        return await super().accept(session, tenant_id, alert_id, actor_id=actor_id, at=at)

    async def resolve(
        self, session: AsyncSession, tenant_id: uuid.UUID, alert_id: uuid.UUID
    ) -> tuple[bool, SosAlert | None]:
        await self._gap("resolve")
        return await super().resolve(session, tenant_id, alert_id)

    async def cancel(
        self, session: AsyncSession, tenant_id: uuid.UUID, alert_id: uuid.UUID
    ) -> tuple[bool, SosAlert | None]:
        await self._gap("cancel")
        return await super().cancel(session, tenant_id, alert_id)

    async def live_for(
        self, session: AsyncSession, tenant_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> list[SosAlertRow]:
        await self._gap("live_for")
        return await super().live_for(session, tenant_id, actor_id=actor_id)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
    )


def _service(
    factory: async_sessionmaker[AsyncSession],
    *,
    now: datetime = NOW,
    gap: _GapRepository | None = None,
) -> FloorService:
    """The shipped service, optionally with the seam opened.

    `_sos` is reassigned rather than injected because the constructor takes no
    repository: F37's races are the only caller that needs one, and a production
    seam existing solely so a test can use it is the shape this repo does not
    ship.
    """
    service = FloorService(factory, clock=lambda: now)
    if gap is not None:
        service._sos = gap
    return service


def _actor(staff_id: uuid.UUID, tenant_id: uuid.UUID, role: StaffRole) -> StaffContext:
    return StaffContext(
        id=staff_id,
        tenant_id=tenant_id,
        email="staff@example.com",
        display_name="Actor",
        role=role.value,
    )


async def _seed_staff(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    display_name: str,
    role: str = StaffRole.OWNER.value,
) -> uuid.UUID:
    assert role in {StaffRole.OWNER.value, StaffRole.SHIFT_MANAGER.value}, (
        "this module COMMITS its rows; a floor role here reddens test_migrations.py"
    )
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=f"race-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name=display_name,
            role=role,
        )
        return staff.id


async def _sign_in(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, staff_id: uuid.UUID
) -> None:
    async with tenant_session(factory, tenant_id) as session:
        await SessionsRepository().insert(
            session,
            tenant_id=tenant_id,
            staff_user_id=staff_id,
            token_hash=uuid.uuid4().hex,
            expires_at=LATER,
        )


async def _raise(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    raiser: uuid.UUID,
    *,
    target: uuid.UUID | None = None,
) -> uuid.UUID:
    result = await _service(factory).raise_sos(
        tenant_id,
        target_staff_user_id=target,
        fitting_room_assignment_id=None,
        note=None,
        actor=_actor(raiser, tenant_id, StaffRole.OWNER),
    )
    return result.sos.alert.id


async def _stored(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, alert_id: uuid.UUID
) -> SosAlert:
    async with tenant_session(factory, tenant_id) as session:
        row = await session.scalar(select(SosAlert).where(SosAlert.id == alert_id))
    assert row is not None
    return row


async def _audit_rows(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, action: AuditAction
) -> list[AuditLog]:
    async with tenant_session(factory, tenant_id) as session:
        rows = await session.execute(
            select(AuditLog).where(AuditLog.tenant_id == tenant_id, AuditLog.action == action)
        )
        return list(rows.scalars().all())


async def _age(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    alert_id: uuid.UUID,
    **fields: datetime,
) -> None:
    """`created_at` is `server_default=text("now()")`, so it is SEEDED — both
    operands of the thirty-second comparison frozen, or the assertion goes green
    or red on machine speed."""
    async with tenant_session(factory, tenant_id) as session:
        await session.execute(update(SosAlert).where(SosAlert.id == alert_id).values(**fields))


# --- accept vs accept ---------------------------------------------------------


async def test_two_responders_accepting_in_the_same_instant_leave_exactly_one_owner(
    app_role_url: str,
) -> None:
    """⚠ **THE feature's centrepiece race, and it has TWO named mutations.**

    Rina reads the alert as open. Dana's whole accept commits in the gap. Only
    then does Rina's guarded UPDATE run.

    **Drop `AND status = 'open'`** and Rina's UPDATE matches the accepted row:
    `accepted_by` flips to Rina, Dana is never told, and two people walk to one
    curtain while a third emergency goes unanswered. Every test that accepts once
    stays green.

    **Drop `populate_existing=True` from `_refreshed`** and the 409 NAMES THE
    WRONG PERSON. Rina's in-memory instance still reads `status = 'open'`, so the
    UPDATE's `evaluate` synchronization re-runs that predicate IN PYTHON, matches,
    and stamps `accepted_by = Rina` onto an object the database never touched;
    with `expire_on_commit=False` a plain re-read hands it straight back and Rina
    is told «רינה כבר מגיעה» — by herself, about herself. Every other accept test
    opens a fresh session per operation, so the identity map is empty and the
    flag is a no-op there.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="דנה כהן")
        rina = await _seed_staff(factory, tenant_id, display_name="רינה")
        alert_id = await _raise(factory, tenant_id, raiser)

        async def dana_accepts() -> None:
            await _service(factory).accept_sos(
                tenant_id, alert_id, actor=_actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)
            )

        loser = _service(factory, gap=_GapRepository("accept", dana_accepts))
        with pytest.raises(SosAlreadyAcceptedError) as raised:
            await loser.accept_sos(
                tenant_id, alert_id, actor=_actor(rina, tenant_id, StaffRole.SHIFT_MANAGER)
            )
        assert raised.value.details == {"staff_display_name": "דנה כהן"}

        stored = await _stored(factory, tenant_id, alert_id)
        assert stored.status == SosStatus.ACCEPTED
        assert stored.accepted_by == dana
        assert stored.acknowledged_at == NOW
        # ONE winner, one trail row, and the loser's whole transaction rolled
        # back — which is what "exactly one" means at the database.
        rows = await _audit_rows(factory, tenant_id, AuditAction.SOS_ACCEPTED)
        assert [row.actor_id for row in rows] == [dana]
    finally:
        await engine.dispose()


# --- accept vs the two closers ------------------------------------------------


@pytest.mark.parametrize("closer", ["resolve", "cancel"])
async def test_an_accept_landing_behind_a_closer_is_refused_and_owns_nothing(
    app_role_url: str, closer: str
) -> None:
    """The responder taps «אני מגיעה» in the same instant the raiser closes the
    page. She must be TOLD it is over — never left owning a closed alert, and
    never told a colleague already has it.

    Drop `populate_existing=True` and this reds with the sharpest possible
    symptom: Dana's own `evaluate`-stamped instance reads `accepted`/`accepted_by
    = Dana`, so `_refuse_accept` takes the ALREADY-ACCEPTED branch and raises
    «דנה כבר מגיעה» — at Dana, naming Dana, for an alert nobody accepted. Two
    files now pin that flag from opposite directions.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="דנה כהן")
        alert_id = await _raise(factory, tenant_id, raiser)
        actor = _actor(raiser, tenant_id, StaffRole.OWNER)

        async def raiser_closes() -> None:
            service = _service(factory)
            if closer == "resolve":
                await service.resolve_sos(tenant_id, alert_id, actor=actor)
            else:
                await service.cancel_sos(tenant_id, alert_id, actor=actor)

        responder = _service(factory, gap=_GapRepository("accept", raiser_closes))
        with pytest.raises(SosClosedError) as refused:
            await responder.accept_sos(
                tenant_id, alert_id, actor=_actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)
            )
        # No name on a closed page: there is nobody to name, and the code the
        # console renders is «נפתר» rather than «כבר מגיעה».
        assert refused.value.details is None

        stored = await _stored(factory, tenant_id, alert_id)
        expected = SosStatus.RESOLVED if closer == "resolve" else SosStatus.CANCELLED
        assert stored.status == expected
        assert stored.accepted_by is None
        assert stored.acknowledged_at is None
        assert await _audit_rows(factory, tenant_id, AuditAction.SOS_ACCEPTED) == []
    finally:
        await engine.dispose()


async def test_a_cancel_landing_behind_an_accept_never_strands_the_responder(
    app_role_url: str,
) -> None:
    """⚠ **The gap version of the shipped sequential test, and it pins one more
    mechanism than that one can.**

    The raiser reads her own page as open and taps «ביטול». Dana's accept commits
    in the gap. The cancel's `status = 'open'` UPDATE then matches zero rows and
    the discriminator must read the DATABASE's `accepted`.

    **Widen cancel's predicate to resolve's pair** and the cancel succeeds
    against an accepted alert: Dana walks to a curtain for an emergency that was
    cancelled behind her, and she is never told. Every sequential cancel test
    stays green.

    **Drop `populate_existing=True`** and it is worse and quieter: the canceller's
    own instance reads `cancelled`, so the service takes the "she wanted it closed
    and it is closed" branch and answers 200. The row IS accepted, Dana IS
    walking, and the raiser is told the page is cancelled. The shipped sequential
    test cannot see this — its canceller loads the row AFTER the accept committed,
    so the instance is already correct.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="דנה כהן")
        alert_id = await _raise(factory, tenant_id, raiser)

        async def dana_accepts() -> None:
            await _service(factory).accept_sos(
                tenant_id, alert_id, actor=_actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)
            )

        canceller = _service(factory, gap=_GapRepository("cancel", dana_accepts))
        with pytest.raises(SosAlreadyAcceptedError) as refused:
            await canceller.cancel_sos(
                tenant_id, alert_id, actor=_actor(raiser, tenant_id, StaffRole.OWNER)
            )
        assert refused.value.details == {"staff_display_name": "דנה כהן"}

        stored = await _stored(factory, tenant_id, alert_id)
        assert stored.status == SosStatus.ACCEPTED
        assert stored.accepted_by == dana
        assert await _audit_rows(factory, tenant_id, AuditAction.SOS_CANCELLED) == []
    finally:
        await engine.dispose()


async def test_a_resolve_landing_behind_an_accept_closes_and_keeps_the_owner(
    app_role_url: str,
) -> None:
    """The asymmetry with cancel, under a real race: resolve closes from EITHER
    live state, so an accept landing in the gap does not refuse it. The emergency
    is over whoever was walking.

    **Narrow resolve's predicate to `status = 'open'`** and this reds loudly — the
    UPDATE matches zero rows and resolve's discriminator has no `accepted` branch
    at all, so the raiser's «נפתר» answers a 500.

    ⚠ **What this test RECORDS rather than defends: the audit row says
    `from_status: 'open'`, and the transition the database actually performed was
    `accepted -> resolved`.** `from_status` is captured before the writer because
    it must be — the UPDATE's `evaluate` synchronization would otherwise stamp
    'resolved' onto the very instance it is read from and the row would say
    `resolved -> resolved`, empty of its whole content (`test_sos_db.py`'s
    `test_a_resolve_records_the_state_it_destroys`). Under a lost race the
    captured value is therefore the state the RESOLVER SAW rather than the one she
    destroyed. That is the lesser of the two, it is bounded by the width of this
    gap, and «did anybody answer?» is still answerable — from the `SOS_ACCEPTED`
    row, which is exactly the pair D1 declines to add a `resolved_at` for.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="דנה כהן")
        alert_id = await _raise(factory, tenant_id, raiser)

        async def dana_accepts() -> None:
            await _service(factory).accept_sos(
                tenant_id, alert_id, actor=_actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)
            )

        resolver = _service(factory, gap=_GapRepository("resolve", dana_accepts))
        closed = await resolver.resolve_sos(
            tenant_id, alert_id, actor=_actor(raiser, tenant_id, StaffRole.OWNER)
        )
        assert closed.alert.status == SosStatus.RESOLVED

        stored = await _stored(factory, tenant_id, alert_id)
        assert stored.status == SosStatus.RESOLVED
        # Neither closer touches the owner columns, so the trail still says who
        # answered — the whole of D1's no-`resolved_by` argument.
        assert stored.accepted_by == dana
        assert stored.acknowledged_at == NOW
        # …and it is off every screen in the boutique.
        assert (
            await _service(factory).sos(
                tenant_id, actor=_actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)
            )
        ).alerts == []

        rows = await _audit_rows(factory, tenant_id, AuditAction.SOS_RESOLVED)
        assert [row.details["from_status"] for row in rows] == [SosStatus.OPEN]
    finally:
        await engine.dispose()


# --- the raise, and the reachability read that is an upper bound --------------


async def test_a_target_whose_session_dies_in_the_gap_still_gets_the_page(
    app_role_url: str,
) -> None:
    """⚠ **NOTHING ABOUT THE BOUTIQUE MAY REFUSE A PAGE — including a target who
    goes offline between the reachability read and the INSERT.**

    Dana holds a live session when the probe runs and holds none by the time the
    row is written. The alert is created anyway, targeted at Dana, and `rerouted`
    stays false, because a raise that failed here — or one that rolled back to
    re-probe — would be the exact silent drop this feature exists to prevent.

    ⚠ **So the read is an UPPER BOUND and this test is where that is written
    down.** `rerouted: false` claims only "she had not signed out one statement
    ago". The safety net is the thirty-second escalation, which is asserted below
    rather than described: the alert really does reach the shift manager, whose
    device is where the page lands when the named colleague's does not.

    Mutation direction is inverted for this one and that is stated plainly: the
    mechanism is the ABSENCE of a post-insert re-check, so it is checked by ADDING
    one (re-probe after the insert and reroute) — which reds this test and reds
    nothing else, because every other reachability case decides before the write.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="דנה כהן")
        manager = await _seed_staff(factory, tenant_id, display_name="רינה")
        await _sign_in(factory, tenant_id, dana)

        async def dana_signs_out() -> None:
            async with tenant_session(factory, tenant_id) as session:
                await SessionsRepository().revoke_for_staff_user(session, tenant_id, dana)

        gap = _GapRepository("insert", dana_signs_out)
        service = _service(factory, gap=gap)
        result = await service.raise_sos(
            tenant_id,
            target_staff_user_id=dana,
            fitting_room_assignment_id=None,
            note="צריך סיכות",
            actor=_actor(raiser, tenant_id, StaffRole.OWNER),
        )
        assert result.rerouted is False
        assert result.sos.alert.target_staff_user_id == dana

        # ⚠ THE ANTI-VACUITY PAIR, and this is the one test in the file that
        # needs it. `fired` says the seam opened; the dead session says the
        # sign-out really happened. Together they order the three statements —
        # probe (reachable) -> revoke -> insert (still targeted at Dana) — which
        # neither assertion states alone, and without them a hook that never ran
        # would pass this test with a colleague who never left.
        assert gap.fired is True
        async with tenant_session(factory, tenant_id) as session:
            live = await SessionsRepository().has_live_session(session, tenant_id, dana, NOW)
        assert live is False

        stored = await _stored(factory, tenant_id, result.sos.alert.id)
        assert stored.status == SosStatus.OPEN
        assert stored.target_staff_user_id == dana
        rows = await _audit_rows(factory, tenant_id, AuditAction.SOS_RAISED)
        assert [row.details["rerouted"] for row in rows] == [False]

        # The safety net, asserted rather than promised: thirty-one seconds later
        # the page a logged-out colleague can no longer answer rises on the shift
        # manager's screen.
        await _age(factory, tenant_id, stored.id, created_at=NOW - timedelta(seconds=31))
        read = await _service(factory).sos(
            tenant_id, actor=_actor(manager, tenant_id, StaffRole.SHIFT_MANAGER)
        )
        assert [(one.escalated, one.for_me) for one in read.alerts] == [(True, True)]
    finally:
        await engine.dispose()


# --- escalation vs the ack ----------------------------------------------------


async def test_an_ack_committing_inside_the_poll_stops_the_escalation_that_tick(
    app_role_url: str,
) -> None:
    """⚠ **An emergency somebody has already taken must never rise full-screen on
    a third device**, and the gap is one poll wide: the shift manager's read
    opens its transaction, Dana's «אני מגיעה» commits, and only then does the
    payload's one statement run.

    Two things are being asserted at once and both matter. That the ack is SEEN —
    the poll's transaction began before it committed, and only READ COMMITTED
    makes the later statement see it; under a repeatable-read session this poll
    would be blind to the ack and the overlay would rise on an answered page.
    And that seeing it is ENOUGH — `escalated` and `for_me` are derived from the
    row the read returned, so the thirty-second clock stops mattering the instant
    the row says somebody owns it.

    **Delete `_escalated`'s guard** (`status != OPEN or acknowledged_at is not
    None`) and the second poll reports an alert Dana already owns as escalated,
    which is a full-screen red interruption for a handled emergency — the exact
    thing that teaches a shift manager to dismiss them unread. **Drop `stalled
    and` from `_for_me`'s accepted branch** and it rises anyway even with
    `escalated` correct. The first poll is the anti-vacuity half: without it a
    guard that returned False unconditionally would pass.

    ⚠ **Neither CONJUNCT alone reds anything here, and that is recorded rather
    than left as false confidence.** Both mutations were run: dropping `status !=
    OPEN` leaves this file green (`acknowledged_at` shadows it, and the fast
    suite's `test_a_closed_alert_never_escalates` is what catches it), and
    dropping `acknowledged_at is not None` leaves the ENTIRE backend suite green
    — an accepted row carries both, so the conjuncts shadow each other on every
    input this feature can produce. The guard as a whole is what this test pins;
    the fast suite pins one half of it; nothing pins the other.

    ⚠ The alert is targeted at a NAMED colleague on purpose. A NULL target routes
    to the role, and `_for_me` returns True for an elevated caller from t=0
    regardless of escalation — so the escalation would not be the discriminator
    and this test would prove nothing about it.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        raiser = await _seed_staff(factory, tenant_id, display_name="Noa")
        dana = await _seed_staff(factory, tenant_id, display_name="דנה כהן")
        rina = await _seed_staff(factory, tenant_id, display_name="רינה")
        await _sign_in(factory, tenant_id, dana)
        alert_id = await _raise(factory, tenant_id, raiser, target=dana)
        await _age(factory, tenant_id, alert_id, created_at=NOW - timedelta(seconds=31))
        manager = _actor(rina, tenant_id, StaffRole.SHIFT_MANAGER)

        unanswered = await _service(factory).sos(tenant_id, actor=manager)
        assert [(one.escalated, one.for_me) for one in unanswered.alerts] == [(True, True)]

        async def dana_accepts() -> None:
            await _service(factory).accept_sos(
                tenant_id, alert_id, actor=_actor(dana, tenant_id, StaffRole.SHIFT_MANAGER)
            )

        polling = _service(factory, gap=_GapRepository("live_for", dana_accepts))
        answered = await polling.sos(tenant_id, actor=manager)
        assert [(one.escalated, one.stalled, one.for_me) for one in answered.alerts] == [
            (False, False, False)
        ]
        assert answered.alerts[0].alert.status == SosStatus.ACCEPTED
        assert answered.alerts[0].row.accepted_by_name == "דנה כהן"
    finally:
        await engine.dispose()
