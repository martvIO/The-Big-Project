"""F41's row in the permanent cross-tenant isolation suite — the crown-jewel
suite `architecture.md:48` calls permanent, and the E9 brief's own words are why
it is non-negotiable: *a new tenant table without these probes is a hole in the
crown jewels.*

`alteration_tickets` carries the most intimate column this platform has written
so far. `notes` is free text a seamstress types beside a garment — a bride's
measurements, what she asked to be let out, why the fitting went badly — and
`due_date` beside it is a wedding date. One boutique's workroom must be invisible
to every other.

⚠ **`notes` HAS NO PROBE OF ITS OWN AND THAT IS DELIBERATE.** Every seeded ticket
below carries one, and every read assertion is a whole-row or whole-count
assertion rather than a column list, so the column Risk 8 hands to F20 is covered
by the same statements that cover the rest of the table. A separate `notes`
probe would be a second thing to remember to update when a column is added; a
`SELECT *` that must come back empty is not.

⚠ **CONNECTED ONLY AS THE NON-OWNER `boutique_app` ROLE, over a `NullPool` engine
via the `app_role_url` fixture — NEVER the superuser one.** The container
superuser bypasses RLS unconditionally. Mutation-checked rather than assumed:
pointing every fixture in this file at the superuser URL turns the four raw-SQL
tests RED, because as superuser B genuinely sees A's rows. The plan predicted
they would go "green vacuously" — they do not. A suite written against the
superuser fails loudly here, which is a better outcome than the plan hoped for.

**Two assertion shapes, and the difference is load-bearing.** The repository's
`by_id`, `board` and `assignees` all carry an explicit `tenant_id` predicate as
defence in depth, so a miss through them proves only that PYTHON filtered. The
`SELECT … FROM alteration_tickets` statements below carry NO tenant predicate
anywhere, so nothing but the policy can answer them.

That split is mutation-checked too, and it corrects the plan a second time.
Deleting `enable_tenant_rls("alteration_tickets")` from 0020 does NOT red every
probe here: it reds the four that read raw, and leaves
`test_every_write_verb_from_a_foreign_tenant_is_a_404_and_never_a_refusal` and
`test_the_assignee_union_never_crosses_a_tenant` GREEN, because both are answered
by the repository's own predicate. That is not a hole — it is the plan's third
mutation row (drop `by_id`'s `tenant_id` → stays green, RLS carries it) seen from
the other side. The two mechanisms are independent, each half of this module
proves one of them, and neither should be read as evidence for the other's.

**This module COMMITS into a session-scoped database**, so no row it commits may
hold a FLOOR ROLE — `test_atelier_db.py`'s docstring has the full reasoning, and
`_seed_staff` here seeds `owner` for the same reason. Nothing here depends on an
assignee's role: the union's second leg takes any staff row that holds a live
undelivered ticket.

Every test mints its own tenant ids; nothing here truncates.
"""

import datetime
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.atelier.schemas import AssignTicketRequest, StageRequest, UpdateTicketRequest
from app.atelier.service import AtelierService
from app.atelier.stages import DEFAULT_EFFORT_BANDS
from app.auth.service import StaffContext
from app.db.repositories.alteration_tickets import AlterationTicketsRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.errors import DomainNotFoundError
from app.models.alteration_ticket import AlterationTicket
from app.models.constants import EffortBand, StaffRole, TicketStage

pytestmark = pytest.mark.db

NOW = datetime.datetime(2026, 8, 2, 11, 20, tzinfo=datetime.UTC)
# The board's "today". Every board read below passes it explicitly so the delivered
# window is measured from the same day the seeds were stamped in.
TODAY = datetime.date(2026, 8, 3)
DUE = datetime.date(2026, 8, 20)

# A bride's measurements, in the column F20's scrub will one day have to find.
NOTES_A = 'מותן -3 ס"מ, שוליים לקצר 4 ס"מ. הכלה מגיעה עם נעליים ביום חמישי.'
NOTES_B = "רוכסן להחליף, מידה 38."


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _service(factory: async_sessionmaker[AsyncSession]) -> AtelierService:
    return AtelierService(factory, clock=lambda: NOW)


def _owner(tenant_id: uuid.UUID) -> StaffContext:
    return StaffContext(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email="owner@bella.example",
        display_name="בעלים",
        role=StaffRole.OWNER.value,
    )


async def _seed(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    notes: str,
    due_date: datetime.date = DUE,
    assigned_staff_user_id: uuid.UUID | None = None,
    delivered_at: datetime.datetime | None = None,
) -> uuid.UUID:
    async with tenant_session(factory, tenant_id) as session:
        row = await AlterationTicketsRepository().insert(
            session,
            tenant_id=tenant_id,
            customer_id=uuid.uuid4(),
            due_date=due_date,
            effort_minutes=60,
            at=NOW,
            assigned_staff_user_id=assigned_staff_user_id,
            notes=notes,
        )
        if delivered_at is not None:
            row.delivered_at = delivered_at
        return row.id


async def _seed_staff(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> uuid.UUID:
    """`owner`, never a floor role — this module COMMITS. See the module
    docstring; the union's second leg does not care about the role."""
    async with tenant_session(factory, tenant_id) as session:
        staff = await StaffUsersRepository().insert(
            session,
            tenant_id=tenant_id,
            email=f"isolation-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name="שרה",
            role=StaffRole.OWNER.value,
        )
        return staff.id


async def _visible_count(factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID) -> int:
    """No tenant predicate anywhere in the statement — RLS is the only thing that
    can answer it, which is what stops the assertion being vacuous."""
    async with tenant_session(factory, tenant_id) as session:
        return (await session.execute(text("SELECT count(*) FROM alteration_tickets"))).scalar_one()


async def test_a_second_tenant_sees_nothing_of_the_firsts_atelier(app_role_url: str) -> None:
    """Every reader B has, against a ticket she was told the id of.

    The raw `SELECT *` is the one that measures RLS: no tenant predicate, so the
    policy is the only thing that can return zero rows — and because it is a star
    select it covers `notes`, `due_date` and every column a later feature adds.
    """
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    repo = AlterationTicketsRepository()
    try:
        ticket_id = await _seed(factory, tenant_a, notes=NOTES_A)

        assert await _visible_count(factory, tenant_b) == 0

        async with tenant_session(factory, tenant_b) as session:
            assert await repo.by_id(session, tenant_b, ticket_id) is None
            tickets, truncated = await repo.board(session, tenant_b, today=TODAY)
            assert (tickets, truncated) == ([], False)
            # Her measurements, her wedding date, asked for with no predicate of
            # any kind. RLS answers zero rows.
            rows = await session.execute(text("SELECT * FROM alteration_tickets"))
            assert rows.all() == []

        assert await _visible_count(factory, tenant_a) == 1
    finally:
        await engine.dispose()


async def test_the_second_tenants_board_never_counts_the_firsts_tickets(
    app_role_url: str,
) -> None:
    """The board is the read this feature performs every five seconds per device,
    and it is the one that would leak a competitor's WORKLOAD as a number — how
    many garments the boutique down the road has in its workroom, answered for
    free with no row ever crossing the boundary.

    A's three include a recently delivered ticket, so the delivered window's leg
    of the predicate is exercised on both sides of the boundary too.
    """
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    repo = AlterationTicketsRepository()
    try:
        for _ in range(2):
            await _seed(factory, tenant_a, notes=NOTES_A)
        await _seed(factory, tenant_a, notes=NOTES_A, delivered_at=NOW)
        b_id = await _seed(factory, tenant_b, notes=NOTES_B)

        async with tenant_session(factory, tenant_b) as session:
            tickets, _ = await repo.board(session, tenant_b, today=TODAY)
            assert [row.id for row in tickets] == [b_id]
            visible = (
                await session.execute(text("SELECT count(*) FROM alteration_tickets"))
            ).scalar_one()
            assert visible == 1  # not 4 — no tenant predicate in that statement

        # And nothing of A's moved when B read and wrote her own.
        async with tenant_session(factory, tenant_a) as session:
            tickets, _ = await repo.board(session, tenant_a, today=TODAY)
            assert len(tickets) == 3
            assert {row.notes for row in tickets} == {NOTES_A}
            assert all(row.intake_at == NOW and row.deleted_at is None for row in tickets)
    finally:
        await engine.dispose()


async def test_every_write_verb_from_a_foreign_tenant_is_a_404_and_never_a_refusal(
    app_role_url: str,
) -> None:
    """All five write verbs, and a 404 rather than a 403 for every one.

    A refusal that distinguished "not yours" from "no such ticket" would CONFIRM
    the guessed id exists, and under RLS plus the explicit predicate a foreign row
    is genuinely indistinguishable from a missing one — so the same class comes
    back for A's real id and for an invented one. That equivalence is asserted,
    not assumed.

    `assign` is called with `staff_user_id: null`: an id would be checked against
    B's own staff first and would answer the validation error instead, which is a
    different question from this one.
    """
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    actor = _owner(tenant_b)
    try:
        ticket_id = await _seed(factory, tenant_a, notes=NOTES_A)
        service = _service(factory)
        invented = uuid.uuid4()

        for target in (ticket_id, invented):
            with pytest.raises(DomainNotFoundError):
                await service.advance(
                    tenant_b, target, StageRequest(stage=TicketStage.QC), actor=actor
                )
            with pytest.raises(DomainNotFoundError):
                await service.undo(
                    tenant_b, target, StageRequest(stage=TicketStage.QC), actor=actor
                )
            with pytest.raises(DomainNotFoundError):
                await service.assign(
                    tenant_b, target, AssignTicketRequest(staff_user_id=None), actor=actor
                )
            with pytest.raises(DomainNotFoundError):
                await service.update(
                    tenant_b,
                    target,
                    UpdateTicketRequest(
                        due_date=DUE,
                        effort_band=EffortBand.HALF_DAY,
                        dress_id=None,
                        dress_name="smuggled",
                        dress_size=None,
                        notes="smuggled",
                    ),
                    actor=actor,
                    bands=DEFAULT_EFFORT_BANDS,
                )
            with pytest.raises(DomainNotFoundError):
                await service.delete(tenant_b, target, actor=actor)

        # Nothing of A's was stamped, edited or removed by any of the twenty
        # attempts above.
        async with tenant_session(factory, tenant_a) as session:
            row = await AlterationTicketsRepository().by_id(session, tenant_a, ticket_id)
        assert row is not None
        assert row.notes == NOTES_A
        assert row.dress_name is None
        assert row.effort_minutes == 60
        assert row.assigned_staff_user_id is None
        assert row.deleted_at is None
        assert (row.qc_at, row.ready_at, row.delivered_at) == (None, None, None)
    finally:
        await engine.dispose()


async def test_the_assignee_union_never_crosses_a_tenant(app_role_url: str) -> None:
    """The union's second leg is a SUBQUERY over `alteration_tickets` — the one
    place in this feature where a ticket decides which STAFF rows come back. A
    foreign ticket that leaked into it would put another boutique's staff name on
    B's assignment dropdown."""
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    repo = AlterationTicketsRepository()
    try:
        staff_id = await _seed_staff(factory, tenant_a)
        await _seed(factory, tenant_a, notes=NOTES_A, assigned_staff_user_id=staff_id)

        async with tenant_session(factory, tenant_b) as session:
            assert await repo.assignees(session, tenant_b) == []
        async with tenant_session(factory, tenant_a) as session:
            assert [row.id for row in await repo.assignees(session, tenant_a)] == [staff_id]
    finally:
        await engine.dispose()


async def test_a_connection_with_no_tenant_context_sees_no_tickets_at_all(
    app_role_url: str,
) -> None:
    """RLS must fail CLOSED. `current_setting('app.tenant_id', true)::uuid` is
    NULL on a connection nobody bound, `tenant_id = NULL` is never true, and the
    answer is zero rows — not an error, and never every boutique's workroom."""
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    try:
        await _seed(factory, tenant_a, notes=NOTES_A)
        async with engine.connect() as conn:
            count = await conn.execute(text("SELECT count(*) FROM alteration_tickets"))
            assert count.scalar_one() == 0
    finally:
        await engine.dispose()


async def test_the_app_role_can_insert_select_update_and_delete_alteration_tickets(
    app_role_url: str,
) -> None:
    """All four privileges, exercised as the app role.

    ⚠ THE PLAN SAYS DROPPING 0020's `GRANT … ON alteration_tickets TO app_user`
    "fails nothing until exactly here, as `permission denied`". MUTATION-CHECKED
    AND FALSE: deleting that line leaves the ENTIRE db suite green, this test
    included. Migration 0002 issues `ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user`, and those
    defaults attach to the ROLE running the migration — which in this suite, and
    in the deploy, is the same role that creates 0020's table. The explicit GRANT
    is house style (every table migration since 0003 carries one) and insurance
    against exactly the caveat 0002 writes down: a table created OUT OF BAND, by
    a different deploy role or by hand. No test in this environment can reach
    that, because there is only one migration role.

    What this test therefore proves is not the GRANT statement but the PRIVILEGES
    — that `boutique_app` really can perform all four verbs on this table under
    forced RLS, by whatever route it was granted them. DELETE is the one the
    application never uses (every removal is a soft delete), so this is the only
    place it is proved at all, and it is the verb a bad REVOKE would take first.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    ticket_id = uuid.uuid4()
    try:
        async with tenant_session(factory, tenant_id) as session:
            await session.execute(
                text(
                    "INSERT INTO alteration_tickets "
                    "(id, tenant_id, customer_id, due_date, effort_minutes, notes) "
                    "VALUES (:id, :tid, :cid, :due, 60, :notes)"
                ),
                {
                    "id": ticket_id,
                    "tid": tenant_id,
                    "cid": uuid.uuid4(),
                    "due": DUE,
                    "notes": NOTES_A,
                },
            )
            stored = (
                await session.execute(text("SELECT notes FROM alteration_tickets"))
            ).scalar_one()
            assert stored == NOTES_A

            await session.execute(
                text("UPDATE alteration_tickets SET notes = :notes"), {"notes": NOTES_B}
            )
            stored = (
                await session.execute(text("SELECT notes FROM alteration_tickets"))
            ).scalar_one()
            assert stored == NOTES_B

            await session.execute(text("DELETE FROM alteration_tickets"))
            assert (
                await session.execute(text("SELECT count(*) FROM alteration_tickets"))
            ).scalar_one() == 0

        # The ORM path agrees: the row really is gone from the table.
        async with tenant_session(factory, tenant_id) as session:
            assert (
                await session.scalar(
                    text("SELECT count(*) FROM alteration_tickets WHERE id = :id"),
                    {"id": ticket_id},
                )
            ) == 0
            assert await session.get(AlterationTicket, ticket_id) is None
    finally:
        await engine.dispose()
