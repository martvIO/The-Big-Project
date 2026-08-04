"""F41's service contract, driven with fakes and no database — the whole
authorization matrix, all four outcomes of every guarded write, and the six audit
rows (`test_floor_service.py`'s scaffold).

**This is where D3's, D4's and D9's discriminators are actually proven.** Each of
the three has TWO OPPOSITE causes for a zero-row write, and telling them apart is
a pure Python decision over a re-read — so it belongs in the fast suite, where it
runs on every push, rather than in a `db`-marked module.

⚠ THE MAPPING IS ONE EQUALITY AND ONE ELSE, NEVER THREE ORDERED COMPARISONS, and
three tests here exist for no other reason: an advance whose re-read shows an
EARLIER stage, an undo of a stage the ticket has skipped past, and a claim whose
re-read shows NULL. All three are ordinary under READ COMMITTED — a zero-row
UPDATE takes no lock — and all three return `None` and 500 from an
`if ==: … elif >: …` pair with no else.

The fake session factory is enough surface for `tenant_session`'s `set_config`
and for D7's `begin_nested()`, and nothing else, so a statement escaping to a
real session raises here instead of passing silently.

What is NOT proven here and must not be claimed: that the repository's guarded
UPDATEs and `populate_existing` re-read behave under a real identity map, and
that D7's savepoint survives two genuinely interleaved intakes. `test_atelier_db.py`
owns the first; the race suite owns the second, and it needs its own seam.
"""

import datetime
import uuid
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any, cast

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.atelier.schemas import (
    AssignTicketRequest,
    CreateTicketRequest,
    StageRequest,
    UpdateTicketRequest,
)
from app.atelier.service import AtelierService
from app.atelier.stages import DEFAULT_EFFORT_BANDS, STAGE_COLUMNS
from app.atelier.validation import (
    AtelierValidationError,
    TicketAlreadyAssignedError,
    TicketStageConflictError,
)
from app.auth.dependencies import NotAuthorizedError
from app.auth.service import StaffContext
from app.db.repositories.alteration_tickets import AlterationTicketsRepository
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.customers import CustomersRepository
from app.db.repositories.dresses import DressesRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.errors import DomainNotFoundError, DomainValidationError
from app.models.alteration_ticket import AlterationTicket
from app.models.constants import AuditAction, EffortBand, StaffRole, TicketStage
from app.models.customer import Customer
from app.models.dress import Dress
from app.models.staff_user import StaffUser

TENANT_ID = uuid.uuid4()
# 2026-08-03 in Jerusalem (UTC+3 in summer), and far enough from midnight that
# the horizon arithmetic never straddles a day.
NOW = datetime.datetime(2026, 8, 3, 9, 0, tzinfo=datetime.UTC)
TODAY = datetime.date(2026, 8, 3)
DUE = datetime.date(2026, 8, 20)
STAMP = datetime.datetime(2026, 8, 2, 11, 20, tzinfo=datetime.UTC)

ELEVATED = [StaffRole.OWNER, StaffRole.SHIFT_MANAGER]
SEAMSTRESS_ID = uuid.uuid4()
COLLEAGUE_ID = uuid.uuid4()

# The tenant's own tuning, deliberately different from every platform default,
# so a resolver that ignored `bands` and read DEFAULT_EFFORT_BANDS would be
# visible in the stored minutes.
TUNED_BANDS = {band: minutes + 7 for band, minutes in DEFAULT_EFFORT_BANDS.items()}


def _actor(role: StaffRole, staff_id: uuid.UUID | None = None) -> StaffContext:
    return StaffContext(
        id=staff_id or uuid.uuid4(),
        tenant_id=TENANT_ID,
        email="staff@bella.example",
        display_name="נועה",
        role=role.value,
    )


def _seamstress_actor() -> StaffContext:
    return _actor(StaffRole.SEAMSTRESS, SEAMSTRESS_ID)


def _ticket(**overrides: object) -> AlterationTicket:
    row = AlterationTicket(
        tenant_id=TENANT_ID,
        customer_id=uuid.uuid4(),
        due_date=DUE,
        effort_minutes=120,
        intake_at=STAMP,
    )
    row.id = uuid.uuid4()
    row.assigned_staff_user_id = None
    row.dress_id = None
    row.dress_name = None
    row.dress_size = None
    row.notes = None
    row.in_progress_at = None
    row.qc_at = None
    row.ready_at = None
    row.delivered_at = None
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _customer(name: str = "מיכל לוי", customer_id: uuid.UUID | None = None) -> Customer:
    row = Customer(tenant_id=TENANT_ID, phone="+972521234567", name=name)
    row.id = customer_id or uuid.uuid4()
    return row


def _staff_row(
    staff_id: uuid.UUID, role: StaffRole = StaffRole.SEAMSTRESS, name: str = "נועה"
) -> StaffUser:
    row = StaffUser(
        tenant_id=TENANT_ID,
        email="noa@bella.example",
        password_hash="not-a-real-hash",
        display_name=name,
        role=role.value,
    )
    row.id = staff_id
    row.deleted_at = None
    return row


def _dress(name: str = "ולנטינה") -> Dress:
    row = Dress(tenant_id=TENANT_ID, name=name)
    row.id = uuid.uuid4()
    return row


class _FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeSession:
    """`begin_nested` is D7's SAVEPOINT and is the only thing this fake carries
    beyond `test_floor_service.py`'s."""

    def __init__(self, recorder: "_Repos") -> None:
        self._recorder = recorder

    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    def begin_nested(self) -> _FakeTransaction:
        self._recorder.order.append("savepoint")
        return _FakeTransaction()

    async def execute(self, *args: object, **kwargs: object) -> None:
        return None


class _Repos:
    """Every repository call in one recorder. `order` is load-bearing twice
    over: it is how "the repository was never reached" is asserted for a
    pure-role refusal, and how "the stamp was captured BEFORE the write" is
    asserted for the undo."""

    def __init__(self) -> None:
        self.order: list[str] = []
        self.audit: list[dict[str, Any]] = []
        self.calls: dict[str, Any] = {}
        # Configurable answers.
        self.by_id_row: AlterationTicket | None = None
        self.wrote: bool = True
        self.refreshed: AlterationTicket | None = None
        self.update_row: AlterationTicket | None = None
        self.deleted: bool = True
        self.customer: Customer | None = None
        self.by_phone_customer: Customer | None = None
        self.upsert_raises: bool = False
        self.dress: Dress | None = None
        self.staff: StaffUser | None = None
        self.board_rows: list[AlterationTicket] = []
        self.board_truncated: bool = False
        self.assignees: list[StaffUser] = []
        self.inserted: AlterationTicket | None = None


def _install(monkeypatch: pytest.MonkeyPatch, repos: _Repos) -> _Repos:
    async def _by_id(
        _s: object, _session: object, _t: uuid.UUID, ticket_id: uuid.UUID
    ) -> AlterationTicket | None:
        repos.order.append("by_id")
        return repos.by_id_row

    def _guarded(name: str) -> Any:
        async def _write(
            _s: object, _session: object, _t: uuid.UUID, *args: object, **kwargs: object
        ) -> tuple[bool, AlterationTicket | None]:
            repos.order.append(name)
            repos.calls[name] = {"args": args, "kwargs": kwargs}
            return repos.wrote, repos.refreshed

        return _write

    async def _update(
        _s: object, _session: object, _t: uuid.UUID, _ticket_id: uuid.UUID, **kwargs: object
    ) -> AlterationTicket | None:
        """⚠ THIS FAKE STAMPS THE NEW VALUES ONTO THE ROW BEFORE RETURNING IT,
        and that is not decoration — it is what the real `update(AlterationTicket)`
        does. It is ORM-enabled DML whose default `evaluate` synchronization
        writes the SET values onto the identity-mapped instance, which is the
        SAME OBJECT `by_id` handed back. A fake that returned an untouched row
        would make a diff taken AFTER the write look correct and would leave the
        capture-before-the-write mutation green.
        """
        repos.order.append("update")
        repos.calls["update"] = kwargs
        if repos.update_row is not None:
            for key, value in kwargs.items():
                setattr(repos.update_row, key, value)
        return repos.update_row

    async def _soft_delete(
        _s: object, _session: object, _t: uuid.UUID, _ticket_id: uuid.UUID
    ) -> bool:
        repos.order.append("soft_delete")
        return repos.deleted

    async def _insert(_s: object, _session: object, **kwargs: object) -> AlterationTicket:
        repos.order.append("insert")
        repos.calls["insert"] = kwargs
        row = _ticket(
            customer_id=cast(uuid.UUID, kwargs["customer_id"]),
            due_date=cast(datetime.date, kwargs["due_date"]),
            effort_minutes=cast(int, kwargs["effort_minutes"]),
            assigned_staff_user_id=kwargs.get("assigned_staff_user_id"),
            dress_id=kwargs.get("dress_id"),
            dress_name=kwargs.get("dress_name"),
            dress_size=kwargs.get("dress_size"),
            notes=kwargs.get("notes"),
            intake_at=kwargs["at"],
        )
        repos.inserted = row
        return row

    async def _board(
        _s: object, _session: object, _t: uuid.UUID, *, today: datetime.date
    ) -> tuple[list[AlterationTicket], bool]:
        repos.order.append("board")
        repos.calls["board"] = {"today": today}
        return repos.board_rows, repos.board_truncated

    async def _assignees(_s: object, _session: object, _t: uuid.UUID) -> list[StaffUser]:
        repos.order.append("assignees")
        return repos.assignees

    async def _customer_by_id(
        _s: object, _session: object, _t: uuid.UUID, _customer_id: uuid.UUID
    ) -> Customer | None:
        repos.order.append("customer_by_id")
        return repos.customer

    async def _customer_by_ids(
        _s: object, _session: object, _t: uuid.UUID, customer_ids: Sequence[uuid.UUID]
    ) -> list[Customer]:
        repos.order.append("customer_by_ids")
        repos.calls["customer_by_ids"] = list(customer_ids)
        return [repos.customer] if repos.customer is not None else []

    async def _customer_by_phone(
        _s: object, _session: object, _t: uuid.UUID, *, phone: str
    ) -> Customer | None:
        repos.order.append("customer_by_phone")
        return repos.by_phone_customer

    async def _upsert(
        _s: object, _session: object, _t: uuid.UUID, *, phone: str, name: str
    ) -> Customer:
        repos.order.append("upsert")
        repos.calls["upsert"] = {"phone": phone, "name": name}
        if repos.upsert_raises:
            raise IntegrityError("INSERT", {}, Exception("duplicate key"))
        assert repos.customer is not None
        return repos.customer

    async def _dress_by_id(
        _s: object, _session: object, _t: uuid.UUID, dress_id: uuid.UUID
    ) -> Dress | None:
        repos.order.append("dress_by_id")
        return repos.dress

    async def _staff_by_id(
        _s: object, _session: object, _t: uuid.UUID, staff_id: uuid.UUID
    ) -> StaffUser | None:
        repos.order.append("staff_by_id")
        repos.calls["staff_by_id"] = staff_id
        return repos.staff

    async def _record(
        _s: object,
        _session: object,
        *,
        tenant_id: uuid.UUID,
        action: str,
        actor_id: uuid.UUID | None = None,
        entity: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        repos.order.append("audit")
        repos.audit.append(
            {"action": action, "actor_id": actor_id, "entity": entity, "details": details}
        )

    monkeypatch.setattr(AlterationTicketsRepository, "by_id", _by_id)
    monkeypatch.setattr(AlterationTicketsRepository, "advance_stage", _guarded("advance_stage"))
    monkeypatch.setattr(AlterationTicketsRepository, "undo_stage", _guarded("undo_stage"))
    monkeypatch.setattr(AlterationTicketsRepository, "claim", _guarded("claim"))
    monkeypatch.setattr(AlterationTicketsRepository, "release", _guarded("release"))
    monkeypatch.setattr(AlterationTicketsRepository, "assign", _guarded("assign"))
    monkeypatch.setattr(AlterationTicketsRepository, "update", _update)
    monkeypatch.setattr(AlterationTicketsRepository, "soft_delete", _soft_delete)
    monkeypatch.setattr(AlterationTicketsRepository, "insert", _insert)
    monkeypatch.setattr(AlterationTicketsRepository, "board", _board)
    monkeypatch.setattr(AlterationTicketsRepository, "assignees", _assignees)
    monkeypatch.setattr(CustomersRepository, "by_id", _customer_by_id)
    monkeypatch.setattr(CustomersRepository, "by_ids", _customer_by_ids)
    monkeypatch.setattr(CustomersRepository, "by_phone", _customer_by_phone)
    monkeypatch.setattr(CustomersRepository, "upsert", _upsert)
    monkeypatch.setattr(DressesRepository, "by_id", _dress_by_id)
    monkeypatch.setattr(StaffUsersRepository, "by_id", _staff_by_id)
    monkeypatch.setattr(AuditLogRepository, "record", _record)
    return repos


def _service(repos: _Repos) -> AtelierService:
    @asynccontextmanager
    async def _factory() -> AsyncIterator[_FakeSession]:
        yield _FakeSession(repos)

    return AtelierService(cast(async_sessionmaker, _factory), clock=lambda: NOW)


def _ready(
    repos: _Repos, *, row: AlterationTicket, customer: Customer | None = None
) -> AlterationTicket:
    """One live ticket, answered by every read the service makes. Returns it so
    the caller names the id from a non-optional local."""
    repos.by_id_row = row
    repos.refreshed = row
    repos.update_row = row
    repos.customer = customer or _customer()
    return row


def _create_request(**overrides: object) -> CreateTicketRequest:
    payload: dict[str, Any] = {
        "customer_name": "מיכל לוי",
        "customer_phone": "0521234567",
        "due_date": DUE,
        "effort_band": EffortBand.TWO_HOURS,
    }
    payload.update(overrides)
    return CreateTicketRequest(**payload)


def _update_request(**overrides: object) -> UpdateTicketRequest:
    payload: dict[str, Any] = {
        "due_date": DUE,
        "effort_band": EffortBand.TWO_HOURS,
        "dress_id": None,
        "dress_name": None,
        "dress_size": None,
        "notes": None,
    }
    payload.update(overrides)
    return UpdateTicketRequest(**payload)


# --- the authorization matrix (D3's per-verb table, D9) ----------------------


@pytest.mark.parametrize("role", ELEVATED)
async def test_an_elevated_role_may_act_on_any_ticket(
    monkeypatch: pytest.MonkeyPatch, role: StaffRole
) -> None:
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket(assigned_staff_user_id=COLLEAGUE_ID))
    repos.staff = _staff_row(COLLEAGUE_ID)

    service = _service(repos)
    actor = _actor(role)
    assert await service.advance(
        TENANT_ID, ticket.id, StageRequest(stage=TicketStage.QC), actor=actor
    )
    assert await service.update(
        TENANT_ID, ticket.id, _update_request(), actor=actor, bands=TUNED_BANDS
    )
    assert await service.assign(
        TENANT_ID, ticket.id, AssignTicketRequest(staff_user_id=COLLEAGUE_ID), actor=actor
    )


async def test_a_seamstress_may_advance_HER_OWN_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    repos = _install(monkeypatch, _Repos())
    row = _ticket(assigned_staff_user_id=SEAMSTRESS_ID, in_progress_at=STAMP)
    _ready(repos, row=row)

    result = await _service(repos).advance(
        TENANT_ID, row.id, StageRequest(stage=TicketStage.IN_PROGRESS), actor=_seamstress_actor()
    )

    assert result.id == row.id


async def test_a_seamstress_may_advance_an_UNASSIGNED_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ THE HALF A READER OF THE API TABLE GETS RIGHT, and it is deliberate:
    advancing an unassigned ticket is a seamstress RECORDING WORK SHE HAS JUST
    DONE. Refusing it would force a claim-then-advance two-tap on the common
    case — a hem picked up off the rack — and a system that makes people take an
    extra step to be honest gets lied to."""
    repos = _install(monkeypatch, _Repos())
    row = _ticket(assigned_staff_user_id=None, in_progress_at=STAMP)
    _ready(repos, row=row)

    result = await _service(repos).advance(
        TENANT_ID, row.id, StageRequest(stage=TicketStage.IN_PROGRESS), actor=_seamstress_actor()
    )

    assert result.id == row.id


async def test_a_seamstress_may_NOT_update_an_unassigned_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ THE HALF A READER OF THE API TABLE GETS WRONG, and the asymmetry with
    the test directly above is the design. Editing a `due_date` or an estimate is
    a SCHEDULING DECISION, not a record of work; on a ticket she does not hold it
    is a decision about somebody else's queue, which is a shift manager's call.
    """
    repos = _install(monkeypatch, _Repos())
    row = _ticket(assigned_staff_user_id=None)
    _ready(repos, row=row)

    with pytest.raises(NotAuthorizedError):
        await _service(repos).update(
            TENANT_ID, row.id, _update_request(), actor=_seamstress_actor(), bands=TUNED_BANDS
        )

    assert "update" not in repos.order


async def test_a_seamstress_may_update_her_own_ticket(monkeypatch: pytest.MonkeyPatch) -> None:
    repos = _install(monkeypatch, _Repos())
    row = _ticket(assigned_staff_user_id=SEAMSTRESS_ID)
    _ready(repos, row=row)

    result = await _service(repos).update(
        TENANT_ID, row.id, _update_request(), actor=_seamstress_actor(), bands=TUNED_BANDS
    )

    assert result.id == row.id


async def test_a_seamstress_on_ANOTHERS_ticket_is_refused_on_every_verb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    row = _ticket(assigned_staff_user_id=COLLEAGUE_ID)
    _ready(repos, row=row)
    actor = _seamstress_actor()

    for call in (
        lambda: _service(repos).advance(
            TENANT_ID, row.id, StageRequest(stage=TicketStage.QC), actor=actor
        ),
        lambda: _service(repos).undo(
            TENANT_ID, row.id, StageRequest(stage=TicketStage.QC), actor=actor
        ),
        lambda: _service(repos).update(
            TENANT_ID, row.id, _update_request(), actor=actor, bands=TUNED_BANDS
        ),
    ):
        with pytest.raises(NotAuthorizedError):
            await call()

    assert repos.audit == []
    assert {"advance_stage", "undo_stage", "update"} & set(repos.order) == set()


async def test_a_seamstress_assigning_a_COLLEAGUE_is_refused_before_any_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ The second assertion is the feature. This refusal depends on the REQUEST
    alone — a seamstress may name only herself or `null` — so it is the method's
    first statement and runs before the session is even opened. A 403 raised
    after a read is an existence oracle; an empty `order` is the only way to
    assert it is not."""
    repos = _install(monkeypatch, _Repos())
    _ready(repos, row=_ticket())

    with pytest.raises(NotAuthorizedError):
        await _service(repos).assign(
            TENANT_ID,
            uuid.uuid4(),
            AssignTicketRequest(staff_user_id=COLLEAGUE_ID),
            actor=_seamstress_actor(),
        )

    assert repos.order == []


# --- advance: one equality and one else (D3) ---------------------------------


async def test_an_advance_that_writes_answers_the_row_and_one_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    before = _ticket(in_progress_at=STAMP)
    after = _ticket(in_progress_at=STAMP, qc_at=NOW)
    after.id = before.id
    after.customer_id = before.customer_id
    repos.by_id_row = before
    repos.refreshed = after
    repos.customer = _customer()
    actor = _actor(StaffRole.OWNER)

    result = await _service(repos).advance(
        TENANT_ID, before.id, StageRequest(stage=TicketStage.QC), actor=actor
    )

    assert result.stage is TicketStage.QC
    assert repos.audit == [
        {
            "action": AuditAction.ATELIER_TICKET_STAGE_ADVANCED.value,
            "actor_id": actor.id,
            "entity": str(before.id),
            "details": {"from": "in_progress", "to": "qc"},
        }
    ]


async def test_a_REPEAT_advance_answers_the_row_unchanged_and_writes_no_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """200 unchanged, and the FIRST tapper's timestamp survives. An audit row
    here would assert that this caller moved a ticket she did not move."""
    repos = _install(monkeypatch, _Repos())
    row = _ticket(qc_at=STAMP)
    _ready(repos, row=row)
    repos.wrote = False

    result = await _service(repos).advance(
        TENANT_ID, row.id, StageRequest(stage=TicketStage.QC), actor=_actor(StaffRole.OWNER)
    )

    assert result.qc_at == STAMP
    assert repos.audit == []


async def test_an_advance_overtaken_by_a_LATER_stage_is_a_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shift manager taps `ready` while the seamstress taps `qc`, both from
    boards last painted five seconds ago. `ready` wins; the `qc` writer's
    predicate now fails on `ready_at IS NULL`, matches zero rows, re-reads and
    sees `ready`. A 200 would be a lie."""
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket(ready_at=STAMP))
    repos.wrote = False

    with pytest.raises(TicketStageConflictError):
        await _service(repos).advance(
            TENANT_ID,
            ticket.id,
            StageRequest(stage=TicketStage.QC),
            actor=_actor(StaffRole.OWNER),
        )

    assert repos.audit == []


async def test_an_advance_whose_reread_shows_an_EARLIER_stage_is_a_409_and_never_a_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ THE CASE AN `if == target / elif > target` PAIR WITH NO ELSE DROPS ON
    THE FLOOR, returning `None` and 500ing the hottest mutation in the feature.

    It needs four ordinary steps and no exotic isolation level. A ticket is at
    `qc`; A taps advance → `qc` (a stale board, or a double tap); A's UPDATE
    evaluates `qc_at IS NULL` → false → ZERO ROWS AND NO ROW LOCK; B's undo of
    `qc` commits — a shipped verb of this same feature; A's re-read, which is a
    second statement under READ COMMITTED and therefore a fresh snapshot, sees
    `qc_at` NULL and the ticket at `in_progress`.

    Strictly LESS than the target, zero rows written, and the honest answer is
    409: the ticket is not where A last saw it.
    """
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket(in_progress_at=STAMP))
    repos.wrote = False

    with pytest.raises(TicketStageConflictError):
        await _service(repos).advance(
            TENANT_ID,
            ticket.id,
            StageRequest(stage=TicketStage.QC),
            actor=_actor(StaffRole.OWNER),
        )


async def test_an_advance_on_a_row_that_is_gone_is_a_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    repos.by_id_row = None

    with pytest.raises(DomainNotFoundError):
        await _service(repos).advance(
            TENANT_ID,
            uuid.uuid4(),
            StageRequest(stage=TicketStage.QC),
            actor=_actor(StaffRole.OWNER),
        )


async def test_an_advance_whose_row_vanishes_between_the_read_and_the_write_is_a_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    ticket = _ticket()
    repos.by_id_row = ticket
    repos.refreshed = None
    repos.wrote = False

    with pytest.raises(DomainNotFoundError):
        await _service(repos).advance(
            TENANT_ID,
            ticket.id,
            StageRequest(stage=TicketStage.QC),
            actor=_actor(StaffRole.OWNER),
        )


# --- undo: the same discriminator, and the stamp it destroys (D4) ------------


async def test_an_undo_that_writes_carries_the_stamp_it_destroyed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ CAPTURED INTO A LOCAL BEFORE THE WRITE, and that is not style. The five
    timestamps ARE the trail, so an un-stamp is the one write in this feature
    that DESTROYS history and this row is the only place it survives. The
    repository's UPDATE is ORM-enabled DML whose `evaluate` synchronization
    stamps NULL onto the very instance `by_id` just handed back, so a
    capture-after-write records `null` and empties the row it exists to fill.

    `order` is what makes that assertion real: the capture must sit between the
    read and the write.
    """
    repos = _install(monkeypatch, _Repos())
    before = _ticket(ready_at=STAMP)
    after = _ticket(ready_at=None)
    after.id = before.id
    after.customer_id = before.customer_id
    repos.by_id_row = before
    repos.refreshed = after
    repos.customer = _customer()
    actor = _actor(StaffRole.SHIFT_MANAGER)

    result = await _service(repos).undo(
        TENANT_ID, before.id, StageRequest(stage=TicketStage.READY), actor=actor
    )

    assert result.ready_at is None
    assert repos.order == ["by_id", "undo_stage", "audit", "customer_by_id"]
    assert repos.audit == [
        {
            "action": AuditAction.ATELIER_TICKET_STAGE_UNDONE.value,
            "actor_id": actor.id,
            "entity": str(before.id),
            "details": {"stage": "ready", "previous_stamp": STAMP.isoformat()},
        }
    ]


async def test_a_repeat_undo_with_nothing_later_stamped_is_a_200_no_op(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket(in_progress_at=STAMP))
    repos.wrote = False

    result = await _service(repos).undo(
        TENANT_ID,
        ticket.id,
        StageRequest(stage=TicketStage.QC),
        actor=_actor(StaffRole.OWNER),
    )

    assert result.stage is TicketStage.IN_PROGRESS
    assert repos.audit == []


async def test_the_SKIP_then_STALE_UNDO_sequence_is_a_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ D4's worked example verbatim, and it needs NO CONCURRENCY AT ALL —
    forward skips are legal and normal under D2.

    A ticket is at `in_progress`. A undoes `in_progress` (→ `intake`), then
    advances STRAIGHT TO `qc`, skipping `in_progress`. B's board was painted
    before all that and still shows `in_progress`; B taps «ביטול שלב» sending
    `{"stage": "in_progress"}`. The predicate `in_progress_at IS NOT NULL` fails
    → zero rows. Now `in_progress_at` IS NULL **and** `qc_at` IS set — and an
    earlier draft's two zero-row branches ("already NULL → 200" and "a later
    stamp exists → 409") are BOTH TRUE, so a builder implementing them in the
    order written answers 200 for a ticket that has moved on.
    """
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket(in_progress_at=None, qc_at=STAMP))
    repos.wrote = False

    with pytest.raises(TicketStageConflictError):
        await _service(repos).undo(
            TENANT_ID,
            ticket.id,
            StageRequest(stage=TicketStage.IN_PROGRESS),
            actor=_actor(StaffRole.OWNER),
        )

    assert repos.audit == []


async def test_undoing_INTAKE_is_a_400_and_never_reaches_the_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clearing `intake_at` would leave a ticket whose DERIVED stage is `intake`
    anyway and whose trail says nothing happened — a lie with no upside. The
    remedy for a ticket that should not exist is the delete verb."""
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket())

    with pytest.raises(AtelierValidationError):
        await _service(repos).undo(
            TENANT_ID,
            ticket.id,
            StageRequest(stage=TicketStage.INTAKE),
            actor=_actor(StaffRole.OWNER),
        )

    assert repos.order == []


async def test_an_undo_on_a_row_that_is_gone_is_a_404(monkeypatch: pytest.MonkeyPatch) -> None:
    repos = _install(monkeypatch, _Repos())
    repos.by_id_row = None

    with pytest.raises(DomainNotFoundError):
        await _service(repos).undo(
            TENANT_ID,
            uuid.uuid4(),
            StageRequest(stage=TicketStage.READY),
            actor=_actor(StaffRole.OWNER),
        )


# --- assignment: two axes (D9) -----------------------------------------------


async def test_a_seamstress_claiming_an_unassigned_ticket_answers_200_and_one_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    before = _ticket(assigned_staff_user_id=None)
    after = _ticket(assigned_staff_user_id=SEAMSTRESS_ID)
    after.id = before.id
    after.customer_id = before.customer_id
    repos.by_id_row = before
    repos.refreshed = after
    repos.customer = _customer()
    repos.staff = _staff_row(SEAMSTRESS_ID)

    result = await _service(repos).assign(
        TENANT_ID,
        before.id,
        AssignTicketRequest(staff_user_id=SEAMSTRESS_ID),
        actor=_seamstress_actor(),
    )

    assert result.assigned_staff_user_id == SEAMSTRESS_ID
    assert "claim" in repos.order
    assert repos.audit == [
        {
            "action": AuditAction.ATELIER_TICKET_ASSIGNED.value,
            "actor_id": SEAMSTRESS_ID,
            "entity": str(before.id),
            "details": {"from": None, "to": str(SEAMSTRESS_ID)},
        }
    ]


async def test_a_repeat_claim_of_a_ticket_she_already_holds_is_a_200_no_op(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket(assigned_staff_user_id=SEAMSTRESS_ID))
    repos.staff = _staff_row(SEAMSTRESS_ID)
    repos.wrote = False

    result = await _service(repos).assign(
        TENANT_ID,
        ticket.id,
        AssignTicketRequest(staff_user_id=SEAMSTRESS_ID),
        actor=_seamstress_actor(),
    )

    assert result.assigned_staff_user_id == SEAMSTRESS_ID
    assert repos.audit == []


async def test_a_claim_lost_to_a_colleague_is_a_409(monkeypatch: pytest.MonkeyPatch) -> None:
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket(assigned_staff_user_id=COLLEAGUE_ID))
    repos.staff = _staff_row(SEAMSTRESS_ID)
    repos.wrote = False

    with pytest.raises(TicketAlreadyAssignedError):
        await _service(repos).assign(
            TENANT_ID,
            ticket.id,
            AssignTicketRequest(staff_user_id=SEAMSTRESS_ID),
            actor=_seamstress_actor(),
        )

    assert repos.audit == []


async def test_a_claim_whose_reread_shows_NULL_is_a_409_and_never_a_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ THE CASE AN `if her / elif someone-else` PAIR DROPS ON THE FLOOR.

    A winner who claims and then RELEASES between the loser's zero-row UPDATE and
    its re-read — ordinary under READ COMMITTED, because the zero-row UPDATE took
    no lock. `assigned_staff_user_id` is neither hers nor a colleague's; it is
    NULL, and there is no third branch.
    """
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket(assigned_staff_user_id=None))
    repos.staff = _staff_row(SEAMSTRESS_ID)
    repos.wrote = False

    with pytest.raises(TicketAlreadyAssignedError):
        await _service(repos).assign(
            TENANT_ID,
            ticket.id,
            AssignTicketRequest(staff_user_id=SEAMSTRESS_ID),
            actor=_seamstress_actor(),
        )


async def test_a_seamstress_releases_her_own_claim_and_the_predicate_is_the_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    before = _ticket(assigned_staff_user_id=SEAMSTRESS_ID)
    after = _ticket(assigned_staff_user_id=None)
    after.id = before.id
    after.customer_id = before.customer_id
    repos.by_id_row = before
    repos.refreshed = after
    repos.customer = _customer()

    result = await _service(repos).assign(
        TENANT_ID, before.id, AssignTicketRequest(staff_user_id=None), actor=_seamstress_actor()
    )

    assert result.assigned_staff_user_id is None
    assert repos.calls["release"]["kwargs"] == {"staff_user_id": SEAMSTRESS_ID}
    assert repos.audit[0]["details"] == {"from": str(SEAMSTRESS_ID), "to": None}


async def test_a_release_that_finds_a_COLLEAGUE_holding_it_is_a_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mirror of the claim's else, and it is the same one-predicate-and-one-
    else shape: a seamstress can drop her own claim and can never drop anybody
    else's, so a zero-row release whose re-read is not unassigned is a conflict.
    """
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket(assigned_staff_user_id=COLLEAGUE_ID))
    repos.wrote = False

    with pytest.raises(TicketAlreadyAssignedError):
        await _service(repos).assign(
            TENANT_ID,
            ticket.id,
            AssignTicketRequest(staff_user_id=None),
            actor=_seamstress_actor(),
        )


async def test_a_repeat_release_of_an_already_unassigned_ticket_is_a_200_no_op(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket(assigned_staff_user_id=None))
    repos.wrote = False

    result = await _service(repos).assign(
        TENANT_ID,
        ticket.id,
        AssignTicketRequest(staff_user_id=None),
        actor=_seamstress_actor(),
    )

    assert result.assigned_staff_user_id is None
    assert repos.audit == []


async def test_elevated_assignment_is_LAST_WRITE_WINS_and_takes_no_409(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A manager reassigning a garment is making a staffing decision with a
    person in front of her. A conflict dialog because a colleague touched the
    same ticket four seconds ago is the platform second-guessing a call that is
    hers; the audit row's from/to is what makes a reassignment war legible after
    the fact."""
    repos = _install(monkeypatch, _Repos())
    before = _ticket(assigned_staff_user_id=COLLEAGUE_ID)
    after = _ticket(assigned_staff_user_id=SEAMSTRESS_ID)
    after.id = before.id
    after.customer_id = before.customer_id
    repos.by_id_row = before
    repos.refreshed = after
    repos.customer = _customer()
    repos.staff = _staff_row(SEAMSTRESS_ID)

    result = await _service(repos).assign(
        TENANT_ID,
        before.id,
        AssignTicketRequest(staff_user_id=SEAMSTRESS_ID),
        actor=_actor(StaffRole.SHIFT_MANAGER),
    )

    assert result.assigned_staff_user_id == SEAMSTRESS_ID
    assert "assign" in repos.order
    assert {"claim", "release"} & set(repos.order) == set()
    assert repos.audit[0]["details"] == {"from": str(COLLEAGUE_ID), "to": str(SEAMSTRESS_ID)}


async def test_an_assignment_that_changes_nothing_writes_no_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket(assigned_staff_user_id=SEAMSTRESS_ID))
    repos.staff = _staff_row(SEAMSTRESS_ID)

    await _service(repos).assign(
        TENANT_ID,
        ticket.id,
        AssignTicketRequest(staff_user_id=SEAMSTRESS_ID),
        actor=_actor(StaffRole.OWNER),
    )

    assert repos.audit == []


async def test_a_NON_SEAMSTRESS_assignee_is_a_400_and_never_reaches_the_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F42's load bars are `SUM(effort_minutes) GROUP BY assigned_staff_user_id`
    against a capacity column F42 puts on seamstresses. A ticket assigned to a
    receptionist is work that exists and that NO load bar will ever show —
    invisible, not merely unusual."""
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket())
    repos.staff = _staff_row(COLLEAGUE_ID, role=StaffRole.RECEPTION)

    with pytest.raises(DomainValidationError):
        await _service(repos).assign(
            TENANT_ID,
            ticket.id,
            AssignTicketRequest(staff_user_id=COLLEAGUE_ID),
            actor=_actor(StaffRole.OWNER),
        )

    assert {"assign", "claim"} & set(repos.order) == set()


async def test_an_UNKNOWN_or_RETIRED_assignee_is_a_400(monkeypatch: pytest.MonkeyPatch) -> None:
    """`StaffUsersRepository.by_id` already filters `deleted_at IS NULL`, so a
    retired staffer and an id that never existed are one indistinguishable
    refusal — which is also the check that catches a seamstress retired
    mid-shift whose session is still live claiming a ticket."""
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket())
    repos.staff = None

    with pytest.raises(DomainValidationError):
        await _service(repos).assign(
            TENANT_ID,
            ticket.id,
            AssignTicketRequest(staff_user_id=COLLEAGUE_ID),
            actor=_actor(StaffRole.OWNER),
        )


# --- intake (D6, D7) ---------------------------------------------------------


async def test_intake_upserts_the_customer_INSIDE_a_savepoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ F41 IS THE FIRST CALLER OF `upsert` THAT HOLDS NO ADVISORY LOCK, and
    the method's own docstring says that matters. `upsert` is read-then-insert:
    two intakes for one brand-new phone interleave into two INSERTs and the
    second hits the partial unique index, raising an IntegrityError INSIDE an
    open transaction — which in Postgres aborts the whole transaction, so the
    intake 500s and the ticket is lost.

    `order` is what pins the savepoint to the call it wraps."""
    repos = _install(monkeypatch, _Repos())
    repos.customer = _customer()

    await _service(repos).create(
        TENANT_ID, _create_request(), actor=_actor(StaffRole.SEAMSTRESS), bands=TUNED_BANDS
    )

    # `customer_by_phone` FIRST and outside the savepoint: `_resolve_customer`
    # reads the live row to answer "did this intake rename her" before `upsert`
    # overwrites the answer. Then the savepoint, then the write it wraps.
    assert repos.order[:3] == ["customer_by_phone", "savepoint", "upsert"]


async def test_a_LOSING_intake_reads_the_winners_customer_back_after_an_IntegrityError(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The partial unique index is what makes the savepoint correct: the loser's
    INSERT is refused, the savepoint rolls back to the instant before it, and
    `by_phone` then finds the winner's committed row. Without `begin_nested()`
    that re-read would raise PendingRollbackError instead of running."""
    repos = _install(monkeypatch, _Repos())
    winner = _customer("מיכל לוי")
    repos.customer = _customer("מיכל לוי")
    repos.upsert_raises = True
    repos.by_phone_customer = winner

    result = await _service(repos).create(
        TENANT_ID, _create_request(), actor=_actor(StaffRole.OWNER), bands=TUNED_BANDS
    )

    assert repos.order[:4] == [
        "customer_by_phone",
        "savepoint",
        "upsert",
        "customer_by_phone",
    ]
    assert repos.calls["insert"]["customer_id"] == winner.id
    assert result.customer_name == "מיכל לוי"


async def test_an_IntegrityError_whose_reread_finds_NOTHING_is_RE_RAISED(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ Swallowing it would present a DIFFERENT constraint failing as a silent,
    wrong customer link — a ticket attached to whichever row `by_phone` happened
    to return, or to none at all."""
    repos = _install(monkeypatch, _Repos())
    repos.customer = _customer()
    repos.upsert_raises = True
    repos.by_phone_customer = None

    with pytest.raises(IntegrityError):
        await _service(repos).create(
            TENANT_ID, _create_request(), actor=_actor(StaffRole.OWNER), bands=TUNED_BANDS
        )

    assert "insert" not in repos.order


async def test_intake_echoes_the_RESOLVED_customer_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`upsert` rewrites `customers.name` unconditionally, so a staff member
    typing «מיכל» for a phone stored as «מיכל לוי» silently renames that
    customer — and F53 renders that name on a screen of its own.

    ⚠ THE ECHO IS NOT THE MITIGATION, which is what D6 claimed and what review
    disproved: `upsert` has already stored the typed string, so on every path but
    the savepoint race the echoed name IS the typed name and cannot differ from
    it. What this test actually pins is that the wire carries the row the
    database holds rather than the request field — which is what makes the
    LOSING-intake test above meaningful. The rename itself is mitigated by the
    `atelier_customer_renamed` audit row (`test_atelier_db.py`), because the
    notice the deck specifies needs a pre-submit lookup and the plan forbids the
    endpoint it would take."""
    repos = _install(monkeypatch, _Repos())
    repos.customer = _customer("מיכל")

    result = await _service(repos).create(
        TENANT_ID,
        _create_request(customer_name="מיכל"),
        actor=_actor(StaffRole.OWNER),
        bands=TUNED_BANDS,
    )

    assert result.customer_name == "מיכל"
    assert repos.calls["upsert"] == {"phone": "+972521234567", "name": "מיכל"}


async def test_the_SERVER_copies_the_dress_name_and_the_client_never_sends_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """0008's snapshot reasoning: the server copies, so the snapshot cannot
    disagree with the row it was taken from on the day it was taken."""
    repos = _install(monkeypatch, _Repos())
    repos.customer = _customer()
    repos.dress = _dress("ולנטינה")

    await _service(repos).create(
        TENANT_ID,
        _create_request(dress_id=repos.dress.id),
        actor=_actor(StaffRole.OWNER),
        bands=TUNED_BANDS,
    )

    assert repos.calls["insert"]["dress_name"] == "ולנטינה"


async def test_an_unknown_or_archived_dress_id_is_a_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    repos.customer = _customer()
    repos.dress = None

    with pytest.raises(DomainNotFoundError):
        await _service(repos).create(
            TENANT_ID,
            _create_request(dress_id=uuid.uuid4()),
            actor=_actor(StaffRole.OWNER),
            bands=TUNED_BANDS,
        )

    assert "insert" not in repos.order


async def test_a_free_text_dress_name_is_kept_when_dress_id_is_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An alteration is frequently on a gown the bride already owns, which has no
    catalog row at all — which is why `dress_name` has two sources and why all
    three dress columns are nullable."""
    repos = _install(monkeypatch, _Repos())
    repos.customer = _customer()

    await _service(repos).create(
        TENANT_ID,
        _create_request(dress_name="שמלת ערב של הלקוחה"),
        actor=_actor(StaffRole.OWNER),
        bands=TUNED_BANDS,
    )

    assert repos.calls["insert"]["dress_name"] == "שמלת ערב של הלקוחה"
    assert "dress_by_id" not in repos.order


async def test_a_dress_name_sent_BESIDE_a_dress_id_is_a_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The server would overwrite it with the catalog's own name, so accepting it
    would silently discard what the caller typed. Refusing is the honest answer
    and it is one clause."""
    repos = _install(monkeypatch, _Repos())
    repos.customer = _customer()
    repos.dress = _dress()

    with pytest.raises(DomainValidationError):
        await _service(repos).create(
            TENANT_ID,
            _create_request(dress_id=uuid.uuid4(), dress_name="משהו אחר"),
            actor=_actor(StaffRole.OWNER),
            bands=TUNED_BANDS,
        )


async def test_the_band_resolves_to_the_TENANTS_minutes_and_never_the_platform_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wire carries the BAND KEY; the server resolves it; the row stores
    MINUTES. There is no request shape in which 37 minutes reaches the row."""
    repos = _install(monkeypatch, _Repos())
    repos.customer = _customer()

    await _service(repos).create(
        TENANT_ID,
        _create_request(effort_band=EffortBand.HALF_DAY),
        actor=_actor(StaffRole.OWNER),
        bands=TUNED_BANDS,
    )

    assert repos.calls["insert"]["effort_minutes"] == TUNED_BANDS[EffortBand.HALF_DAY]
    assert repos.calls["insert"]["effort_minutes"] != DEFAULT_EFFORT_BANDS[EffortBand.HALF_DAY]


async def test_the_create_audit_row_carries_the_four_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    repos.customer = _customer()
    repos.staff = _staff_row(SEAMSTRESS_ID)
    actor = _actor(StaffRole.OWNER)

    result = await _service(repos).create(
        TENANT_ID,
        _create_request(assigned_staff_user_id=SEAMSTRESS_ID),
        actor=actor,
        bands=TUNED_BANDS,
    )

    assert repos.audit == [
        {
            "action": AuditAction.ATELIER_TICKET_CREATED.value,
            "actor_id": actor.id,
            "entity": str(result.id),
            "details": {
                "customer_id": str(repos.customer.id),
                "due_date": DUE.isoformat(),
                "effort_minutes": TUNED_BANDS[EffortBand.TWO_HOURS],
                "assigned_staff_user_id": str(SEAMSTRESS_ID),
            },
        }
    ]


# --- due_date: the bounds are ASYMMETRIC and the asymmetry is the point (D5) --


async def test_a_PAST_due_date_is_a_200_on_create(monkeypatch: pytest.MonkeyPatch) -> None:
    """⚠ THE ASSERTION THAT STOPS SOMEONE RESOLVING D5 THE WRONG WAY LATER.

    There is NO lower bound. A dress that was due yesterday is exactly the ticket
    a boutique most needs to open, and the past-date warning is a client
    affordance only — no `min` attribute, no warning field on the wire.
    """
    repos = _install(monkeypatch, _Repos())
    repos.customer = _customer()

    result = await _service(repos).create(
        TENANT_ID,
        _create_request(due_date=datetime.date(2020, 1, 1)),
        actor=_actor(StaffRole.OWNER),
        bands=TUNED_BANDS,
    )

    assert result.due_date == datetime.date(2020, 1, 1)
    assert result.overdue is True


async def test_a_PAST_due_date_is_a_200_on_update(monkeypatch: pytest.MonkeyPatch) -> None:
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket(due_date=datetime.date(2020, 1, 1)))

    result = await _service(repos).update(
        TENANT_ID,
        ticket.id,
        _update_request(due_date=datetime.date(2020, 1, 1)),
        actor=_actor(StaffRole.OWNER),
        bands=TUNED_BANDS,
    )

    assert result.due_date == datetime.date(2020, 1, 1)


async def test_a_due_date_beyond_the_horizon_is_a_400_on_create_and_on_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A TYPO FENCE, not a policy about how far ahead a boutique may plan: DATE
    accepts year 9999 and one mistyped year poisons the board's sort and every
    capacity number F42 derives from it."""
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket())
    far = TODAY + datetime.timedelta(days=731)

    with pytest.raises(DomainValidationError):
        await _service(repos).create(
            TENANT_ID,
            _create_request(due_date=far),
            actor=_actor(StaffRole.OWNER),
            bands=TUNED_BANDS,
        )
    with pytest.raises(DomainValidationError):
        await _service(repos).update(
            TENANT_ID,
            ticket.id,
            _update_request(due_date=far),
            actor=_actor(StaffRole.OWNER),
            bands=TUNED_BANDS,
        )

    assert repos.order == []


async def test_the_horizon_boundary_itself_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    repos = _install(monkeypatch, _Repos())
    repos.customer = _customer()
    edge = TODAY + datetime.timedelta(days=730)

    result = await _service(repos).create(
        TENANT_ID,
        _create_request(due_date=edge),
        actor=_actor(StaffRole.OWNER),
        bands=TUNED_BANDS,
    )

    assert result.due_date == edge


# --- the other 400s ----------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"customer_name": "   "},
        {"customer_name": "מיכל\x07לוי"},
        {"customer_name": "x" * 81},
        {"customer_phone": "03-1234567"},
        {"notes": "x" * 501},
        {"notes": "מדידה\x00"},
        {"dress_name": "x" * 201},
        {"dress_size": "x" * 41},
    ],
    ids=[
        "blank-name",
        "control-char-in-name",
        "name-too-long",
        "landline",
        "notes-too-long",
        "nul-in-notes",
        "dress-name-too-long",
        "dress-size-too-long",
    ],
)
async def test_a_malformed_intake_field_is_a_400(
    monkeypatch: pytest.MonkeyPatch, overrides: dict[str, Any]
) -> None:
    repos = _install(monkeypatch, _Repos())
    repos.customer = _customer()

    with pytest.raises(DomainValidationError):
        await _service(repos).create(
            TENANT_ID,
            _create_request(**overrides),
            actor=_actor(StaffRole.OWNER),
            bands=TUNED_BANDS,
        )

    assert repos.order == []


async def test_notes_keep_newlines_and_tabs_while_labels_bar_the_whole_C0_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The BOOKING path's two regexes, not the storefront's: `notes` is a
    paragraph and keeps whitespace, while a line break in a label that reaches an
    SMS template is header-injection material."""
    repos = _install(monkeypatch, _Repos())
    repos.customer = _customer()

    await _service(repos).create(
        TENANT_ID,
        _create_request(notes='להרים 4 ס"מ\nלצרף חגורה'),
        actor=_actor(StaffRole.OWNER),
        bands=TUNED_BANDS,
    )

    assert repos.calls["insert"]["notes"] == 'להרים 4 ס"מ\nלצרף חגורה'

    with pytest.raises(DomainValidationError):
        await _service(repos).create(
            TENANT_ID,
            _create_request(dress_name="ולנטינה\n"),
            actor=_actor(StaffRole.OWNER),
            bands=TUNED_BANDS,
        )


# --- update: the diff, and what the audit row may carry (D11) ----------------


async def test_an_update_that_changes_nothing_writes_no_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket(effort_minutes=TUNED_BANDS[EffortBand.TWO_HOURS]))

    await _service(repos).update(
        TENANT_ID,
        ticket.id,
        _update_request(),
        actor=_actor(StaffRole.OWNER),
        bands=TUNED_BANDS,
    )

    assert "update" in repos.order
    assert repos.audit == []


async def test_the_update_audit_row_carries_changed_key_NAMES_and_never_VALUES(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ `notes` may hold a bride's MEASUREMENTS — the most intimate data this
    platform carries — and `audit_log` has a different retention clock from the
    row it describes. Copying the text there would put the same data in two
    places with two deletion dates. F15's BOOKING_PHONE_CORRECTED carries
    `old_customer_id` because an IDENTIFIER is what a security audit asks for; a
    paragraph of measurements is not.

    The diff must also be taken BEFORE the write, for the identity-map reason the
    undo's `previous_stamp` states at length.
    """
    repos = _install(monkeypatch, _Repos())
    row = _ticket(effort_minutes=TUNED_BANDS[EffortBand.TWO_HOURS], notes="ישן")
    _ready(repos, row=row)
    secret = "היקף מותן 68"

    await _service(repos).update(
        TENANT_ID,
        row.id,
        _update_request(due_date=datetime.date(2026, 9, 1), notes=secret),
        actor=_actor(StaffRole.OWNER),
        bands=TUNED_BANDS,
    )

    assert repos.audit[0]["action"] == AuditAction.ATELIER_TICKET_UPDATED.value
    assert repos.audit[0]["details"] == {"changed": ["due_date", "notes"]}
    assert secret not in repr(repos.audit)
    assert "ישן" not in repr(repos.audit)


async def test_an_update_of_a_missing_ticket_is_a_404(monkeypatch: pytest.MonkeyPatch) -> None:
    repos = _install(monkeypatch, _Repos())
    repos.by_id_row = None

    with pytest.raises(DomainNotFoundError):
        await _service(repos).update(
            TENANT_ID,
            uuid.uuid4(),
            _update_request(),
            actor=_actor(StaffRole.OWNER),
            bands=TUNED_BANDS,
        )


async def test_an_update_clears_a_note_when_it_is_sent_as_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The full-replace convention's whole point: here `None` means "clear it",
    which is the only reading that lets a seamstress delete a note — and the
    request model's required fields are what make "omitted" impossible."""
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(
        repos, row=_ticket(notes="ישן", effort_minutes=TUNED_BANDS[EffortBand.TWO_HOURS])
    )

    await _service(repos).update(
        TENANT_ID,
        ticket.id,
        _update_request(notes=None),
        actor=_actor(StaffRole.OWNER),
        bands=TUNED_BANDS,
    )

    assert repos.calls["update"]["notes"] is None
    assert repos.audit[0]["details"] == {"changed": ["notes"]}


# --- delete ------------------------------------------------------------------


async def test_delete_soft_deletes_and_audits_the_stage_it_removed_from_the_board(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The service takes NO role check — the ROUTE's per-route
    `require_role(OWNER, SHIFT_MANAGER)` is the control (D10), and
    `test_atelier_api.py` is where the seamstress's 403 is asserted."""
    repos = _install(monkeypatch, _Repos())
    row = _ticket(qc_at=STAMP)
    _ready(repos, row=row)
    actor = _actor(StaffRole.OWNER)

    await _service(repos).delete(TENANT_ID, row.id, actor=actor)

    assert repos.order == ["by_id", "soft_delete", "audit"]
    assert repos.audit == [
        {
            "action": AuditAction.ATELIER_TICKET_DELETED.value,
            "actor_id": actor.id,
            "entity": str(row.id),
            "details": {"stage": "qc"},
        }
    ]


async def test_deleting_a_missing_ticket_is_a_404(monkeypatch: pytest.MonkeyPatch) -> None:
    repos = _install(monkeypatch, _Repos())
    repos.by_id_row = None

    with pytest.raises(DomainNotFoundError):
        await _service(repos).delete(TENANT_ID, uuid.uuid4(), actor=_actor(StaffRole.OWNER))


async def test_a_DOUBLE_TAPPED_delete_is_a_404_and_writes_no_second_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`deleted_at IS NULL` in the predicate is what makes the second call answer
    False rather than re-stamping the timestamp — a double-tapped delete must not
    move the retention clock F20 reads off this column."""
    repos = _install(monkeypatch, _Repos())
    ticket = _ready(repos, row=_ticket())
    repos.deleted = False

    with pytest.raises(DomainNotFoundError):
        await _service(repos).delete(TENANT_ID, ticket.id, actor=_actor(StaffRole.OWNER))

    assert repos.audit == []


# --- the board read ----------------------------------------------------------


async def test_the_board_asks_for_the_window_against_the_JERUSALEM_calendar_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    row = _ticket()
    repos.board_rows = [row]
    repos.customer = _customer(customer_id=row.customer_id)
    repos.assignees = [_staff_row(SEAMSTRESS_ID)]

    body = await _service(repos).board(TENANT_ID, bands=TUNED_BANDS)

    assert repos.calls["board"] == {"today": TODAY}
    assert repos.calls["customer_by_ids"] == [row.customer_id]
    assert [t.id for t in body.tickets] == [row.id]
    assert [s.id for s in body.seamstresses] == [SEAMSTRESS_ID]


async def test_the_board_costs_exactly_three_business_statements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ The poll's budget, and the reason the BANDS come off
    `TenantContext.settings` in the router rather than through
    `TenantsRepository`: that repository opens its OWN session inside every
    method, so it cannot join this `tenant_session` and would cost a fourth pool
    checkout and a fourth BEGIN/COMMIT every five seconds per device."""
    repos = _install(monkeypatch, _Repos())
    repos.board_rows = []

    await _service(repos).board(TENANT_ID, bands=TUNED_BANDS)

    assert repos.order == ["board", "customer_by_ids", "assignees"]


async def test_the_board_carries_the_bands_it_was_handed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())

    body = await _service(repos).board(TENANT_ID, bands=TUNED_BANDS)

    assert {b.band: b.minutes for b in body.effort_bands} == TUNED_BANDS


# --- the shape of the stage columns the service reasons over ------------------


def test_every_stage_has_a_column_so_the_undo_no_op_predicate_is_total() -> None:
    assert set(STAGE_COLUMNS) == set(TicketStage)


@pytest.mark.parametrize("field", ["due_date", "effort_band", "dress_id", "dress_name", "notes"])
def test_every_editable_field_on_the_update_request_is_REQUIRED(field: str) -> None:
    """⚠ A FULL REPLACE, and the absence of defaults is the whole mechanism.

    With an optional field, an OMITTED key and an explicitly cleared one are the
    same request — so a console that forgets to send `notes` silently deletes a
    bride's measurements and nothing anywhere can tell the two apart.
    `UpdateAppointmentTypeRequest`'s shipped rule.
    """
    payload: dict[str, Any] = {
        "due_date": DUE,
        "effort_band": EffortBand.TWO_HOURS,
        "dress_id": None,
        "dress_name": None,
        "dress_size": None,
        "notes": None,
    }
    del payload[field]
    with pytest.raises(ValidationError):
        UpdateTicketRequest(**payload)


def test_an_unknown_key_on_any_request_model_is_refused() -> None:
    """`ForbidExtraModel`, and it is what makes "the client can never send
    `effort_minutes`" an assertion rather than a hope."""
    with pytest.raises(ValidationError):
        _create_request(effort_minutes=37)


def test_every_atelier_audit_value_is_pinned_by_literal() -> None:
    """SET EQUALITY over a literal, so a new member or a renamed value is a
    deliberate act. `audit_log.action` is plain TEXT with no CHECK, so nothing in
    the database would refuse a typo.

    `atelier_customer_renamed` is F41's seventh, added at review: it is the only
    row in this namespace whose `entity` is a CUSTOMER rather than a ticket,
    because intake writes `customers.name` and D6's promised notice is not
    buildable without an endpoint the plan forbids.

    ⚠ The name no longer counts the members. F42 makes the block eight and the
    settings row makes it nine; a test whose NAME carries the count is a second
    literal to keep in step, and the set equality below is the whole
    assertion."""
    assert {action.value for action in AuditAction if action.value.startswith("atelier_")} == {
        "atelier_customer_renamed",
        "atelier_ticket_created",
        "atelier_ticket_updated",
        "atelier_ticket_assigned",
        "atelier_ticket_stage_advanced",
        "atelier_ticket_stage_undone",
        "atelier_ticket_deleted",
        # F42: her weekly hours changed, and by whom.
        "atelier_capacity_set",
    }
