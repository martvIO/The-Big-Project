"""`sos_alerts` in the permanent cross-tenant isolation suite (AC10, AC11).

⚠ **Connected ONLY as the non-owner `boutique_app` role, over a `NullPool`
engine, via the `app_role_url` fixture — NEVER `migrated_db`.** The container
superuser bypasses RLS and every GRANT unconditionally, so a suite pointed at it
can pass vacuously while proving nothing.

**All three of the plan's mandated mutations were RUN, and two of its three
predictions are wrong. The results are recorded here rather than smoothed over,
because the next feature will copy this file.**

| Mutation | Predicted | Actually |
|---|---|---|
| delete `enable_tenant_rls("sos_alerts")` | *every* probe RED | **THREE RED** (below) |
| point the suite at `migrated_db` | green vacuously | **SIX RED** |
| drop 0021's `GRANT` | the write probe RED | **nothing at all** |

The three that red without the policy are `test_no_sos_reader_crosses_a_tenant`,
the five-join probe and the no-context probe — plus `test_tenant_isolation.py`'s
table scan, which is in another file and is what AC11 actually names.

**Why "every probe RED" was never going to be true here, and it is a property of
the repository rather than a gap in the file.** `SosAlertsRepository` spells an
explicit `tenant_id ==` on the driving table AND on all five joins, and every
verb takes its tenant id from the caller's own connection. So a probe reads as an
RLS probe only if it hands a repository the FOREIGN tenant id — then, with the
policy off, that redundant predicate matches and the foreign row comes back. The
three that do exactly that are the three that go red; the rest are asserting
AC10's HTTP status, D3's permissive fallthrough and the GRANTs, none of which the
policy decides. **A probe passing its OWN tenant id and asserting the list is
short proves nothing and would stay green with RLS dropped** — the five-join
probe was written that way first and was rewritten when this mutation caught it.

**The GRANT, and the plan is wrong about why it matters.** Dropping 0021's
`GRANT` changes NOTHING, because 0002's `ALTER DEFAULT PRIVILEGES IN SCHEMA
public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user` already
confers them on every table a later migration creates as that role — 0021's own
comment says the statement is redundant belt-and-braces. What the probe pins is
the PRIVILEGE however it arrives, and that IS live: adding `REVOKE UPDATE ON
sos_alerts FROM app_user` reds `test_the_app_role_may_insert_select_and_update_sos_alerts`
with `permission denied` and reds nothing else in this file. A future narrowing
of 0002's defaults, or a table created by a different deploy role, surfaces here
and nowhere else by name.

**Why this table earns a file rather than one more row in
`test_tenant_isolation.py`'s scan.** The scan proves the POLICY exists. What it
cannot prove is that the read carrying the policy is the one the product runs:
`live_for` LEFT JOINs FIVE tables — `sos_alerts`, `staff_users` three times over
and `fitting_rooms` through `fitting_room_assignments` — and a join is exactly
where a missing policy hides, because the driving table is filtered while the
joined one is not and the row COUNT stays identical. So the payload read is
probed on its JOINED COLUMNS, not on its length.

**And this is the one payload in the product that is fetched on every section,
every few seconds, for the whole shift.** F36's floor read is on two screens;
this one is app-level. A cross-tenant leak here would be continuous.

⚠ **What this file does NOT cover, said plainly: the service verbs are not RLS
probes.** `accept_sos`/`resolve_sos`/`cancel_sos` are called with the intruder's
OWN tenant id — which is what production does, since the tenant comes from the
hostname — so the by-id read refuses on the repository's predicate one step
before the policy is consulted. They are here for AC10's other half: that all
three refusals are one indistinguishable `DomainNotFoundError` and never a 409
naming a stranger's colleague.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.service import StaffContext
from app.db.repositories.fitting_room_assignments import FittingRoomAssignmentsRepository
from app.db.repositories.fitting_rooms import FittingRoomsRepository
from app.db.repositories.sessions import SessionsRepository
from app.db.repositories.sos_alerts import SosAlertsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.floor.service import FloorService
from app.models.constants import SosStatus, StaffRole
from app.models.sos_alert import SosAlert

pytestmark = pytest.mark.db

NOW = datetime(2026, 8, 3, 11, 20, tzinfo=UTC)
LATER = datetime(2026, 8, 3, 13, 45, tzinfo=UTC)

ALERTS = SosAlertsRepository()
SESSIONS = SessionsRepository()


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _actor(tenant_id: uuid.UUID, staff_id: uuid.UUID) -> StaffContext:
    return StaffContext(
        id=staff_id,
        tenant_id=tenant_id,
        email="owner@bella.example",
        display_name="Owner",
        role=StaffRole.OWNER.value,
    )


class _Boutique:
    """One tenant's whole SOS state: two staffers, a room, an assignment, a live
    session and one open alert naming all of them."""

    def __init__(
        self,
        tenant_id: uuid.UUID,
        raiser: uuid.UUID,
        target: uuid.UUID,
        assignment: uuid.UUID,
        alert: uuid.UUID,
    ) -> None:
        self.tenant_id = tenant_id
        self.raiser = raiser
        self.target = target
        self.assignment = assignment
        self.alert = alert


async def _seed(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> _Boutique:
    """⚠ `owner` always: this module COMMITS its rows and the cluster is shared,
    so a floor role here would redden `test_migrations.py`'s 0011 CHECK backfill
    — `test_floor_db.py:10-32`'s rule verbatim. Nothing here reads the role.

    The alert is raised through the SERVICE rather than INSERTed, so the row that
    tenant B then attacks is byte-identical to a production one: a resolved room
    pointer, a reachable target, an audit row and all.
    """
    async with tenant_session(factory, tenant_id) as session:
        staff = StaffUsersRepository()
        raiser = await staff.insert(
            session,
            tenant_id=tenant_id,
            email=f"iso-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name="דנה",
            role=StaffRole.OWNER.value,
        )
        target = await staff.insert(
            session,
            tenant_id=tenant_id,
            email=f"iso-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name="רינה",
            role=StaffRole.OWNER.value,
        )
        rooms = FittingRoomsRepository()
        room = await rooms.insert(session, tenant_id, label="חדר 1", sort_order=0)
        assignment = await FittingRoomAssignmentsRepository().claim(
            session, tenant_id, room_id=room.id, staff_id=raiser.id, booking_id=None
        )
        await SESSIONS.insert(
            session,
            tenant_id=tenant_id,
            staff_user_id=target.id,
            token_hash=uuid.uuid4().hex,
            expires_at=LATER,
        )

    raised = await FloorService(factory, clock=lambda: NOW).raise_sos(
        tenant_id,
        target_staff_user_id=target.id,
        fitting_room_assignment_id=assignment.id,
        note="צריך סיכות",
        actor=_actor(tenant_id, raiser.id),
    )
    # The seed is worthless unless the row it produced is the interesting one.
    assert raised.rerouted is False
    assert raised.sos.row.room_label == "חדר 1"
    return _Boutique(tenant_id, raiser.id, target.id, assignment.id, raised.sos.alert.id)


# --- the readers --------------------------------------------------------------


async def test_no_sos_reader_crosses_a_tenant(app_role_url: str) -> None:
    """Every read F37 owns, run from tenant B's connection with tenant A's
    arguments — which is what makes a pass here RLS doing the work rather than
    the repository's redundant `tenant_id ==` predicate. With the policy off that
    predicate alone would still let `tenant_id == A` through on B's connection,
    because B is the one supplying it.

    ⚠ **`live_for` is probed BOTH ways**, and the second way is the one that
    matters: as an ELEVATED caller (`actor_id=None`), which drops the audience
    clause entirely and leaves RLS as the ONLY thing between one boutique's
    emergencies and another's. Every other predicate in that statement is
    defence; this call has none.

    A foreign id reads as MISSING (`None` / empty), never as a refusal that would
    confirm the row exists — one indistinguishable 404, which is AC10 at the
    repository layer.
    """
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        theirs = await _seed(factory, elsewhere)
        await _seed(factory, here)

        async with tenant_session(factory, here) as session:
            assert await ALERTS.by_id(session, elsewhere, theirs.alert) is None
            assert await ALERTS.view_of(session, elsewhere, theirs.alert) is None
            assert await ALERTS.live_for(session, elsewhere, actor_id=theirs.raiser) == []
            assert await ALERTS.live_for(session, elsewhere, actor_id=None) == []
            assert (
                await ALERTS.assignment_of(session, elsewhere, theirs.assignment, theirs.raiser)
                is None
            )
    finally:
        await engine.dispose()


async def test_the_five_join_payload_never_carries_another_boutiques_names(
    app_role_url: str,
) -> None:
    """⚠ **THE FIVE-TABLE JOIN, probed as its own case, on its JOINED COLUMNS.**

    `live_for` drives from `sos_alerts` and LEFT JOINs `staff_users` three times
    (raiser, target, acceptor) and `fitting_rooms` through
    `fitting_room_assignments`. A policy missing on any ONE of those would leave
    the alert list correctly filtered while a foreign colleague's name — or a
    foreign boutique's room label — rode in on the join, **and the row count
    would be identical**. So the assertion is on the names and the label, never
    on the length.

    ⚠ **The read is DRIVEN with the foreign tenant id, and that is what makes a
    pass here RLS rather than the repository.** `_joined` spells an explicit
    `tenant_id ==` on the driving table and on every one of the five joins, so a
    probe that passed its OWN id would be carried entirely by those predicates
    and would stay green with the policy dropped — the exact shape the module
    docstring says to avoid, and the shape this test was written in first.

    Read as the ELEVATED caller (`actor_id=None`), which drops the audience
    clause and leaves nothing but the tenant predicates and the policy.

    The positive control is not decoration: without it the empty list would also
    be satisfied by a join that never returns anything.
    """
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        theirs = await _seed(factory, elsewhere)
        mine = await _seed(factory, here)

        async with tenant_session(factory, here) as session:
            leaked = await ALERTS.live_for(session, elsewhere, actor_id=None)
            ours = await ALERTS.live_for(session, here, actor_id=None)
        assert leaked == []

        # The control, on the same connection and the same statement: every
        # joined column the leak would have carried really is produced.
        assert [row.alert.id for row in ours] == [mine.alert]
        assert [row.raised_by_name for row in ours] == ["דנה"]
        assert [row.target_name for row in ours] == ["רינה"]
        assert [row.room_label for row in ours] == ["חדר 1"]
        assert theirs.alert != mine.alert
    finally:
        await engine.dispose()


async def test_the_reachability_probe_is_tenant_scoped(app_role_url: str) -> None:
    """`has_live_session` is the raise's only read of another person's state, and
    F37 is its ONLY caller. Tenant B asking about tenant A's signed-in staffer
    gets False — even though the row is live, unexpired and unrevoked.

    Unscoped it would be a cross-tenant presence oracle: a boutique could learn
    which of a competitor's staff ids are signed in right now by watching
    `rerouted` flip on its own raises.
    """
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        theirs = await _seed(factory, elsewhere)
        mine = await _seed(factory, here)

        async with tenant_session(factory, here) as session:
            assert await SESSIONS.has_live_session(session, elsewhere, theirs.target, NOW) is False
            # …and the same call answers True for her own, so False above is
            # isolation rather than a probe that never says yes.
            assert await SESSIONS.has_live_session(session, here, mine.target, NOW) is True
    finally:
        await engine.dispose()


# --- the writers, through the service (AC10) ----------------------------------


async def test_every_sos_verb_on_another_tenants_alert_is_an_indistinguishable_404(
    app_role_url: str,
) -> None:
    """⚠ **AC10 at the layer that answers the HTTP status.** Tenant B tries all
    three mutations against tenant A's alert and gets the SAME
    `DomainNotFoundError` she would get for an id that never existed anywhere —
    never a 403, which would confirm the alert is real, and never one of the two
    409s, which would confirm its status and name a stranger's colleague.

    ⚠ **The 409s are the sharp part.** `SOS_ALREADY_ACCEPTED` carries
    `{"staff_display_name": …}`, so a cross-tenant accept that reached the
    discriminator would hand B a member of A's staff BY NAME. The refusal
    happens at the by-id read, one step before permission and four before the
    discriminator, so there is nothing to leak and no oracle to build.
    """
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        theirs = await _seed(factory, elsewhere)
        mine = await _seed(factory, here)
        service = FloorService(factory, clock=lambda: NOW)
        intruder = _actor(here, mine.raiser)

        for attempt in (
            service.accept_sos(here, theirs.alert, actor=intruder),
            service.resolve_sos(here, theirs.alert, actor=intruder),
            service.cancel_sos(here, theirs.alert, actor=intruder),
        ):
            with pytest.raises(DomainNotFoundError):
                await attempt

        # …and byte-identical for an id that never existed anywhere, which is what
        # makes the two indistinguishable rather than merely both refused.
        with pytest.raises(DomainNotFoundError):
            await service.accept_sos(here, uuid.uuid4(), actor=intruder)
    finally:
        await engine.dispose()


async def test_a_raise_pointing_across_a_tenant_stores_null_and_is_still_created(
    app_role_url: str,
) -> None:
    """⚠ **D3's permissive fallthrough, proven across a tenant boundary — and it
    is the one place isolation and «a page is never silently dropped» could have
    been made to disagree.**

    Tenant B raises with tenant A's `fitting_room_assignment_id` and A's staffer
    as the target. Both pointers fail to resolve — not because they are checked
    against a tenant, but because RLS makes them simply not exist on B's
    connection — so the room is stored NULL and the target is rerouted to B's own
    shift manager. **The alert is created either way.** A stricter reading (a
    404, or a 400 on an unresolvable pointer) would have turned a cross-tenant id
    into an existence oracle AND refused a page, which is the one thing this
    feature may not do.
    """
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        theirs = await _seed(factory, elsewhere)
        mine = await _seed(factory, here)

        raised = await FloorService(factory, clock=lambda: NOW).raise_sos(
            here,
            target_staff_user_id=theirs.target,
            fitting_room_assignment_id=theirs.assignment,
            note=None,
            actor=_actor(here, mine.raiser),
        )
        assert raised.sos.alert.fitting_room_assignment_id is None
        assert raised.sos.alert.target_staff_user_id is None
        assert raised.rerouted is True
        assert raised.sos.row.room_label is None
        assert raised.sos.row.target_name is None

        async with tenant_session(factory, here) as session:
            stored = await session.scalar(
                select(SosAlert).where(SosAlert.id == raised.sos.alert.id)
            )
        assert stored is not None
        assert stored.tenant_id == here
        assert stored.status == SosStatus.OPEN
    finally:
        await engine.dispose()


async def test_nothing_of_the_foreign_boutiques_alert_moved(app_role_url: str) -> None:
    """A silently-refused cross-tenant write and a silently-SUCCEEDING one look
    identical from the caller's side, so the owning tenant re-reads afterwards.
    Every column a verb could have touched is asserted, not just the row's
    existence: a policy that filters SELECT but not UPDATE would leave the alert
    present and closed — an emergency cancelled from another boutique.
    """
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        theirs = await _seed(factory, elsewhere)
        mine = await _seed(factory, here)
        service = FloorService(factory, clock=lambda: NOW)
        intruder = _actor(here, mine.raiser)

        for attempt in (
            service.accept_sos(here, theirs.alert, actor=intruder),
            service.resolve_sos(here, theirs.alert, actor=intruder),
            service.cancel_sos(here, theirs.alert, actor=intruder),
        ):
            with pytest.raises(DomainNotFoundError):
                await attempt

        async with tenant_session(factory, elsewhere) as session:
            stored = await ALERTS.by_id(session, elsewhere, theirs.alert)
        assert stored is not None
        assert stored.status == SosStatus.OPEN
        assert stored.accepted_by is None
        assert stored.acknowledged_at is None
        assert stored.target_staff_user_id == theirs.target
        assert stored.deleted_at is None

        # …and it is still on her own screen, which is the assertion the raiser
        # would actually notice.
        hers = await service.sos(elsewhere, actor=_actor(elsewhere, theirs.raiser))
        assert [one.alert.id for one in hers.alerts] == [theirs.alert]
    finally:
        await engine.dispose()


# --- the GRANTs and the anti-vacuity guard ------------------------------------


async def test_the_app_role_may_insert_select_and_update_sos_alerts(app_role_url: str) -> None:
    """⚠ **THE ONLY TEST IN THE PRODUCT THAT NAMES THIS TABLE WHEN A PRIVILEGE
    GOES MISSING.** Every other db module would break too, but a `permission
    denied` there reads as an unrelated failure in somebody else's feature. Here
    it is the assertion and the failure names `sos_alerts`.

    Every verb the app role actually issues, and no more: INSERT (the raise),
    SELECT (the poll and the by-id read) and UPDATE (accept, then resolve). **No
    DELETE** — nothing in this feature hard-deletes, `deleted_at` has no v1
    writer at all, and asserting a privilege the code never uses would be pinning
    one we could drop.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        mine = await _seed(factory, tenant_id)  # INSERT
        service = FloorService(factory, clock=lambda: NOW)
        target = _actor(tenant_id, mine.target)

        async with tenant_session(factory, tenant_id) as session:  # SELECT
            assert await ALERTS.by_id(session, tenant_id, mine.alert) is not None
            assert len(await ALERTS.live_for(session, tenant_id, actor_id=None)) == 1

        accepted = await service.accept_sos(tenant_id, mine.alert, actor=target)  # UPDATE
        assert accepted.alert.status == SosStatus.ACCEPTED
        closed = await service.resolve_sos(tenant_id, mine.alert, actor=target)  # UPDATE
        assert closed.alert.status == SosStatus.RESOLVED
    finally:
        await engine.dispose()


async def test_the_app_role_cannot_reach_an_alert_without_a_tenant_context(
    app_role_url: str,
) -> None:
    """`current_setting(..., missing_ok := true)` yields NULL with no context
    set, so the policy's predicate is NULL and the connection sees ZERO rows. It
    fails CLOSED rather than erroring or, worse, seeing everything — which is what
    makes a forgotten `tenant_session` show up as empty data rather than as a
    cross-tenant leak.

    Deliberately NOT wrapped in `tenant_session`: leaving the context out is
    exactly what is being tested.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        mine = await _seed(factory, tenant_id)

        async with factory() as session, session.begin():
            assert await ALERTS.by_id(session, tenant_id, mine.alert) is None
            assert await ALERTS.view_of(session, tenant_id, mine.alert) is None
            assert await ALERTS.live_for(session, tenant_id, actor_id=None) == []
    finally:
        await engine.dispose()


async def test_the_app_role_is_not_the_owner_of_sos_alerts(app_role_url: str) -> None:
    """The anti-vacuity assertion for the WHOLE module, and the reason it is an
    assertion rather than a comment: `FORCE ROW LEVEL SECURITY` binds the table
    owner too, but a SUPERUSER bypasses every policy and every GRANT
    unconditionally. A future edit pointing this suite at `migrated_db` — or a
    fixture that quietly starts handing back the superuser URL — would leave
    every probe above green while proving nothing.

    So: assert the connected role cannot do something only a superuser or the
    owner can. `ALTER TABLE ... DISABLE ROW LEVEL SECURITY` is the sharpest
    available, because it is precisely the privilege whose absence makes the rest
    of this file meaningful.
    """
    engine, _ = _factory(app_role_url)
    try:
        with pytest.raises(ProgrammingError) as denied:
            async with engine.begin() as conn:
                await conn.execute(text("ALTER TABLE sos_alerts DISABLE ROW LEVEL SECURITY"))
        assert "must be owner" in str(denied.value) or "permission denied" in str(denied.value)
    finally:
        await engine.dispose()


async def test_an_expired_session_in_another_tenant_is_not_an_oracle_either(
    app_role_url: str,
) -> None:
    """The reachability probe's two failure modes are indistinguishable ACROSS a
    tenant, and that is worth its own case because they are distinguishable
    WITHIN one — `test_sos_db.py` asserts that an expired session reroutes while
    a live one does not, i.e. the probe genuinely discriminates.

    From another boutique it must not: A's live session, A's expired session and
    an id that never existed all read False, so `rerouted` on B's own raise
    carries no information about A at all.
    """
    engine, factory = _factory(app_role_url)
    here, elsewhere = uuid.uuid4(), uuid.uuid4()
    try:
        theirs = await _seed(factory, elsewhere)
        expired = uuid.uuid4()
        async with tenant_session(factory, elsewhere) as session:
            await SESSIONS.insert(
                session,
                tenant_id=elsewhere,
                staff_user_id=expired,
                token_hash=uuid.uuid4().hex,
                expires_at=NOW - timedelta(minutes=1),
            )
        await _seed(factory, here)

        async with tenant_session(factory, here) as session:
            probe = SESSIONS.has_live_session
            assert await probe(session, elsewhere, theirs.target, NOW) is False
            assert await probe(session, elsewhere, expired, NOW) is False
            assert await probe(session, elsewhere, uuid.uuid4(), NOW) is False
    finally:
        await engine.dispose()
