"""F51 StaffService against fake repositories — no Postgres, so this suite runs
in the fast local pass.

**The step order IS the correctness argument.** A test that still passes with the
lock and the read swapped is not testing this feature, so the first three tests
below assert the recorded statement order, the lock's exact key, and the
deliberate ABSENCE of a lock on create. The concurrency behaviour those steps buy
is proven on real Postgres in test_staff_management_db.py, which is CI-only.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any, Self

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.passwords import hash_password, verify_password
from app.auth.service import StaffContext
from app.auth.staff import (
    DuplicateEmailError,
    LastOwnerRequiredError,
    StaffNotFoundError,
    StaffSelfManageError,
    StaffService,
)
from app.errors import DomainValidationError
from app.models.constants import AuditAction, StaffRole
from app.models.staff_user import StaffUser

TENANT_ID = uuid.uuid4()
OWNER_ID = uuid.uuid4()
CREATED_AT = datetime(2026, 7, 30, 9, 0, tzinfo=UTC)
PASSWORD = "correct-horse-staple"


def _row(
    *,
    staff_id: uuid.UUID | None = None,
    email: str = "dana@bella.example",
    display_name: str = "Dana",
    role: str = StaffRole.SHIFT_MANAGER.value,
    password: str = PASSWORD,
) -> StaffUser:
    return StaffUser(
        id=staff_id or uuid.uuid4(),
        tenant_id=TENANT_ID,
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        role=role,
        # Set explicitly for the reason created_at is: both ride a
        # server_default, so an UNFLUSHED ORM instance carries None where the
        # database guarantees False — and the no-op and audit comparisons below
        # are against exactly that value.
        shift_manager_eligible=False,
        created_at=CREATED_AT,
    )


def _actor(staff_id: uuid.UUID = OWNER_ID) -> StaffContext:
    return StaffContext(
        id=staff_id,
        tenant_id=TENANT_ID,
        email="owner@bella.example",
        display_name="Owner",
        role=StaffRole.OWNER.value,
    )


class Trace(list[str]):
    """The ordered call log the assertions read. A plain list plus one field, so
    the session's raw SQL and the repository's method names live in one object
    and the tests never have to reach into StaffService's privates for it."""

    def __init__(self) -> None:
        super().__init__()
        self.statements: list[str] = []


class FakeSession:
    """Enough AsyncSession to satisfy tenant_session: an async context manager
    whose begin() is another one, plus an execute() that records what it saw."""

    def __init__(self, trace: Trace) -> None:
        self.trace = trace

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    def begin(self) -> Self:
        return self

    async def execute(self, statement: object, params: object = None) -> None:
        rendered = str(statement)
        self.trace.statements.append(rendered)
        if "pg_advisory_xact_lock" in rendered:
            self.trace.append("lock")


class FakeStaffRepository:
    def __init__(self, trace: Trace, rows: list[StaffUser] | None = None) -> None:
        self.trace = trace
        self.rows = rows or []
        self.by_email_result: StaffUser | None = None
        self.live_owners = 2
        self.inserted: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []
        self.soft_deleted: list[uuid.UUID] = []
        self.raise_integrity_on_insert = False

    async def list_live(self, session: object, tenant_id: uuid.UUID) -> list[StaffUser]:
        self.trace.append("list_live")
        return self.rows

    async def by_email(self, session: object, tenant_id: uuid.UUID, email: str) -> StaffUser | None:
        self.trace.append("by_email")
        return self.by_email_result

    async def by_id(
        self, session: object, tenant_id: uuid.UUID, staff_id: uuid.UUID
    ) -> StaffUser | None:
        self.trace.append("by_id")
        return next((row for row in self.rows if row.id == staff_id), None)

    async def count_live_owners(self, session: object, tenant_id: uuid.UUID) -> int:
        self.trace.append("count_live_owners")
        return self.live_owners

    async def insert(self, session: object, **kwargs: Any) -> StaffUser:
        self.trace.append("insert")
        if self.raise_integrity_on_insert:
            raise IntegrityError("INSERT", (), Exception("duplicate key"))
        self.inserted.append(kwargs)
        return _row(email=kwargs["email"], display_name=kwargs["display_name"], role=kwargs["role"])

    async def update(
        self, session: object, tenant_id: uuid.UUID, staff_id: uuid.UUID, **kwargs: Any
    ) -> StaffUser | None:
        self.trace.append("update")
        self.updates.append({"staff_id": staff_id, **kwargs})
        row = next((row for row in self.rows if row.id == staff_id), None)
        if row is None:
            return None
        for field, value in kwargs.items():
            if value is not None:
                setattr(row, field, value)
        return row

    async def soft_delete(self, session: object, tenant_id: uuid.UUID, staff_id: uuid.UUID) -> bool:
        self.trace.append("soft_delete")
        self.soft_deleted.append(staff_id)
        return True


class FakeSessionsRepository:
    def __init__(self, trace: Trace) -> None:
        self.trace = trace
        self.revoked: list[dict[str, Any]] = []

    async def revoke_for_staff_user(
        self,
        session: object,
        tenant_id: uuid.UUID,
        staff_user_id: uuid.UUID,
        *,
        except_token_hash: str | None = None,
    ) -> None:
        self.trace.append("revoke_sessions")
        self.revoked.append(
            {"staff_user_id": staff_user_id, "except_token_hash": except_token_hash}
        )


class FakeAuditRepository:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def record(self, session: object, **kwargs: Any) -> None:
        self.rows.append(kwargs)

    def actions(self) -> list[str]:
        return [row["action"] for row in self.rows]


def _service(
    rows: list[StaffUser] | None = None,
) -> tuple[StaffService, FakeStaffRepository, FakeAuditRepository, Trace]:
    trace = Trace()
    session = FakeSession(trace)
    service = StaffService(lambda: session)  # type: ignore[arg-type]
    staff = FakeStaffRepository(trace, rows)
    audit = FakeAuditRepository()
    service._staff = staff  # type: ignore[assignment]
    service._audit = audit  # type: ignore[assignment]
    return service, staff, audit, trace


def _session_spy(service: StaffService, trace: Trace) -> FakeSessionsRepository:
    """Opt-in rather than part of `_service`: only the password paths touch the
    sessions table, and widening the tuple would touch twenty call sites."""
    sessions = FakeSessionsRepository(trace)
    service._sessions = sessions  # type: ignore[assignment]
    return sessions


# --- the lock protocol: the step order IS the correctness argument ---


async def test_the_lock_is_taken_before_any_read_on_patch_and_delete() -> None:
    """Spec D3, and F15's D5 lesson restated: a read taken outside the lock is a
    stale read, and the last-owner guard would then be evaluated against a count
    another transaction has already invalidated. This is the test that fails if
    the by_id call ever moves back above the lock."""
    target = _row()
    for run in ("patch", "delete"):
        service, _, _, trace = _service([target])
        if run == "patch":
            await service.update(TENANT_ID, target.id, display_name="Renamed", actor=_actor())
        else:
            await service.deactivate(TENANT_ID, target.id, actor=_actor())
        assert trace[0] == "lock", (run, trace)
        assert trace[1] == "by_id", (run, trace)


async def test_the_lock_key_is_namespaced_and_not_the_booking_claim_key() -> None:
    """`hashtext(:tenant_id)` bare is the booking-claim lock (booking/service.py,
    booking/owner.py). Reusing it would serialize every staff edit against every
    public booking create for this tenant — correct but pointlessly wide. The
    prefix is a SQL literal and the id is bound, never interpolated."""
    target = _row()
    service, _, _, trace = _service([target])
    await service.deactivate(TENANT_ID, target.id, actor=_actor())
    # Every statement tenant_session and the service issued, in order.
    locks = [s for s in trace.statements if "pg_advisory_xact_lock" in s]
    assert len(locks) == 1
    assert "hashtext('staff:' || :tenant_id)" in locks[0]


async def test_create_takes_no_lock_at_all() -> None:
    """Stated as a ruling rather than an omission (spec D3): an insert can only
    RAISE the live-owner count, and a raise never invalidates a decision another
    transaction already made under the lock."""
    service, _, _, trace = _service()
    await service.create(
        TENANT_ID,
        email="new@bella.example",
        display_name="New",
        role=StaffRole.SHIFT_MANAGER.value,
        password="a-long-enough-pw",
        actor=_actor(),
    )
    assert "lock" not in trace


# --- create ---


async def test_create_lowercases_the_address_before_it_reaches_the_repository() -> None:
    """Spec D5. login lowercases before lookup (auth/router.py:52) and by_email
    matches exactly, so a row written as Dana@Bella.example is an account that can
    NEVER sign in — a silent, total failure with no error anywhere."""
    service, staff, audit, _ = _service()
    created = await service.create(
        TENANT_ID,
        email="Dana@Bella.Example",
        display_name="Dana",
        role=StaffRole.SHIFT_MANAGER.value,
        password="a-long-enough-pw",
        actor=_actor(),
    )
    assert staff.inserted[0]["email"] == "dana@bella.example"
    assert created.email == "dana@bella.example"
    assert audit.rows[0]["details"]["email"] == "dana@bella.example"


async def test_create_hashes_the_password_and_never_stores_it_in_the_clear() -> None:
    service, staff, audit, _ = _service()
    await service.create(
        TENANT_ID,
        email="new@bella.example",
        display_name="New",
        role=StaffRole.SHIFT_MANAGER.value,
        password="a-long-enough-pw",
        actor=_actor(),
    )
    stored = staff.inserted[0]["password_hash"]
    assert stored != "a-long-enough-pw"
    assert verify_password("a-long-enough-pw", stored)
    # Spec D8: no password material, plaintext OR hashed, ever enters details.
    rendered = repr(audit.rows)
    assert "a-long-enough-pw" not in rendered
    assert stored not in rendered


async def test_create_audits_the_new_row_with_its_email_and_role() -> None:
    service, _, audit, _ = _service()
    created = await service.create(
        TENANT_ID,
        email="new@bella.example",
        display_name="New",
        role=StaffRole.SHIFT_MANAGER.value,
        password="a-long-enough-pw",
        actor=_actor(),
    )
    assert audit.actions() == [AuditAction.STAFF_CREATED]
    assert audit.rows[0]["actor_id"] == OWNER_ID
    assert audit.rows[0]["entity"] == str(created.id)
    assert audit.rows[0]["details"] == {
        "email": "new@bella.example",
        "role": StaffRole.SHIFT_MANAGER.value,
    }


async def test_a_duplicate_live_email_is_refused_by_the_pre_check() -> None:
    service, staff, _, _ = _service()
    staff.by_email_result = _row(email="taken@bella.example")
    with pytest.raises(DuplicateEmailError):
        await service.create(
            TENANT_ID,
            email="taken@bella.example",
            display_name="New",
            role=StaffRole.SHIFT_MANAGER.value,
            password="a-long-enough-pw",
            actor=_actor(),
        )
    assert staff.inserted == []


async def test_a_duplicate_live_email_is_refused_by_the_integrity_backstop() -> None:
    """The pre-check RACES. The partial unique index is the real authority, and a
    500 on a duplicate email is not an acceptable answer — the create_booking
    pattern, with the try wrapping the WHOLE tenant_session block because catching
    inside it would try to raise from an aborted transaction."""
    service, staff, _, _ = _service()
    staff.raise_integrity_on_insert = True
    with pytest.raises(DuplicateEmailError):
        await service.create(
            TENANT_ID,
            email="racy@bella.example",
            display_name="New",
            role=StaffRole.SHIFT_MANAGER.value,
            password="a-long-enough-pw",
            actor=_actor(),
        )


# --- the self-guard (spec D4) ---


async def test_self_demotion_and_self_deactivation_are_refused_and_write_nothing() -> None:
    """Deactivation is instantly effective, so a self-deactivate is a lockout the
    console cannot undo — there is no restore route and the operator CLI's
    password reset carries role == 'owner' in its WHERE clause. Self-demotion is
    the same lockout one step slower, since this router is owner-only."""
    me = _row(staff_id=OWNER_ID, role=StaffRole.OWNER.value, display_name="Owner")
    service, staff, audit, _ = _service([me])
    with pytest.raises(StaffSelfManageError):
        await service.update(
            TENANT_ID, OWNER_ID, role=StaffRole.SHIFT_MANAGER.value, actor=_actor()
        )
    with pytest.raises(StaffSelfManageError):
        await service.deactivate(TENANT_ID, OWNER_ID, actor=_actor())
    assert staff.updates == []
    assert staff.soft_deleted == []
    assert audit.rows == []


async def test_an_owner_may_still_rename_herself() -> None:
    """ProvisioningService seeds every founding owner with
    display_name = owner_email, so this section is where she fixes that. A
    guard that blocked it would strand every boutique's founder."""
    me = _row(staff_id=OWNER_ID, role=StaffRole.OWNER.value, display_name="owner@bella.example")
    service, _, audit, _ = _service([me])
    updated = await service.update(TENANT_ID, OWNER_ID, display_name="דנה", actor=_actor())
    assert updated.display_name == "דנה"
    assert audit.actions() == [AuditAction.STAFF_UPDATED]


async def test_resending_her_own_unchanged_role_is_a_no_op_not_a_refusal() -> None:
    """The inline edit form posts display_name AND role together. If the guard
    fired on the mere PRESENCE of `role` rather than on it MOVING, an owner could
    never rename herself through that form — she would get a 409 for a field she
    did not change."""
    me = _row(staff_id=OWNER_ID, role=StaffRole.OWNER.value, display_name="Owner")
    service, staff, audit, _ = _service([me])
    updated = await service.update(
        TENANT_ID, OWNER_ID, display_name="Dana", role=StaffRole.OWNER.value, actor=_actor()
    )
    assert updated.display_name == "Dana"
    assert audit.actions() == [AuditAction.STAFF_UPDATED]
    assert staff.updates[0]["role"] is None


# --- current_password on the self path (spec D4) ---


async def test_a_self_password_change_needs_the_current_one() -> None:
    """The one security control F51 adds beyond the epic's two guards. A stolen
    owner session already grants the whole console — but for the session's
    remaining TTL. Letting it silently rewrite the owner's password converts a
    bounded compromise into a permanent takeover whose only remedy is an operator
    CLI ticket."""
    me = _row(staff_id=OWNER_ID, role=StaffRole.OWNER.value, password="my-real-password")
    original = me.password_hash
    service, staff, audit, _ = _service([me])

    with pytest.raises(DomainValidationError):
        await service.update(TENANT_ID, OWNER_ID, password="brand-new-pw-1", actor=_actor())
    with pytest.raises(DomainValidationError):
        await service.update(
            TENANT_ID,
            OWNER_ID,
            password="brand-new-pw-1",
            current_password="not-my-password",
            actor=_actor(),
        )
    assert me.password_hash == original
    assert staff.updates == []
    assert audit.rows == []

    updated = await service.update(
        TENANT_ID,
        OWNER_ID,
        password="brand-new-pw-1",
        current_password="my-real-password",
        actor=_actor(),
    )
    assert verify_password("brand-new-pw-1", updated.password_hash)
    assert audit.actions() == [AuditAction.STAFF_PASSWORD_RESET]
    assert audit.rows[0]["details"] == {"self": True}


async def test_resetting_someone_elses_password_never_consults_current_password() -> None:
    """An owner resetting another staffer's password sends no current_password —
    she does not know it, and that is the field's whole point."""
    target = _row()
    service, _, audit, trace = _service([target])
    _session_spy(service, trace)
    updated = await service.update(TENANT_ID, target.id, password="brand-new-pw-1", actor=_actor())
    assert verify_password("brand-new-pw-1", updated.password_hash)
    assert audit.actions() == [AuditAction.STAFF_PASSWORD_RESET]
    assert audit.rows[0]["details"] == {"self": False}


async def test_a_password_write_revokes_the_targets_sessions_except_the_acting_cookie() -> None:
    """Deactivation needs no sweep — resolve_session re-reads staff_users. A
    password change gets no such seam for free: nothing consults password_hash
    after login, so without this the sessions the OLD password could have leaked
    survive it for the whole TTL, and inside that window a stolen owner cookie
    can mint a second owner through POST /manage/staff that outlives everything.
    The acting cookie is spared so the owner keeps the tab she just used."""
    me = _row(staff_id=OWNER_ID, role=StaffRole.OWNER.value, password="my-real-password")
    service, _, _, trace = _service([me])
    sessions = _session_spy(service, trace)

    await service.update(
        TENANT_ID,
        OWNER_ID,
        password="brand-new-pw-1",
        current_password="my-real-password",
        acting_token_hash="hash-of-her-live-cookie",
        actor=_actor(),
    )
    assert sessions.revoked == [
        {"staff_user_id": OWNER_ID, "except_token_hash": "hash-of-her-live-cookie"}
    ]
    # Inside the lock and before the transaction closes, so a revoke cannot
    # commit without the hash it was meant to invalidate.
    assert trace.index("revoke_sessions") > trace.index("update")


async def test_a_patch_that_writes_no_password_revokes_nothing() -> None:
    """A rename is not a credential event. Revoking on every PATCH would sign a
    staffer out because someone fixed a typo in her name."""
    target = _row()
    service, _, _, trace = _service([target])
    sessions = _session_spy(service, trace)
    await service.update(TENANT_ID, target.id, display_name="Renamed", actor=_actor())
    assert sessions.revoked == []


# --- the last-owner guard (spec D3) ---


async def test_the_last_owner_can_be_neither_demoted_nor_deactivated() -> None:
    sole = _row(role=StaffRole.OWNER.value)
    for run in ("demote", "deactivate"):
        service, staff, audit, _ = _service([sole])
        staff.live_owners = 1
        with pytest.raises(LastOwnerRequiredError):
            if run == "demote":
                await service.update(
                    TENANT_ID, sole.id, role=StaffRole.SHIFT_MANAGER.value, actor=_actor()
                )
            else:
                await service.deactivate(TENANT_ID, sole.id, actor=_actor())
        assert staff.updates == [], run
        assert staff.soft_deleted == [], run
        assert audit.rows == [], run


async def test_the_last_owner_guard_stays_quiet_when_it_should() -> None:
    """It fires only when the target IS currently a live owner and the operation
    would stop that being true. A second live owner, a target who is already a
    shift manager, and a PATCH that moves only the display name are all legal."""
    owner = _row(role=StaffRole.OWNER.value)
    service, staff, _, _ = _service([owner])
    staff.live_owners = 2
    await service.update(TENANT_ID, owner.id, role=StaffRole.SHIFT_MANAGER.value, actor=_actor())

    manager = _row(role=StaffRole.SHIFT_MANAGER.value)
    service, staff, _, trace = _service([manager])
    staff.live_owners = 1
    await service.deactivate(TENANT_ID, manager.id, actor=_actor())
    assert "count_live_owners" not in trace

    sole = _row(role=StaffRole.OWNER.value)
    service, staff, _, trace = _service([sole])
    staff.live_owners = 1
    await service.update(TENANT_ID, sole.id, display_name="Renamed", actor=_actor())
    assert "count_live_owners" not in trace


# --- F57: the widened role set passes through F51's guards unchanged ---


@pytest.mark.parametrize(
    "role",
    [StaffRole.RECEPTION.value, StaffRole.SALES_ASSISTANT.value, StaffRole.SEAMSTRESS.value],
)
async def test_the_last_owner_guard_fires_on_a_move_to_any_floor_role(role: str) -> None:
    """⚠ The guard keys on the target LEAVING `owner`, never on where it is
    going (`auth/staff.py:187-193`), so widening StaffRole cannot open a hole in
    it — but "cannot" is a claim, and this is what makes it a fact.

    Without it, the sole owner of a boutique could demote herself to seamstress
    and lock every human being out of the console, with the tenant's only remedy
    being an operator CLI ticket.
    """
    sole = _row(role=StaffRole.OWNER.value)
    service, staff, audit, _ = _service([sole])
    staff.live_owners = 1

    with pytest.raises(LastOwnerRequiredError):
        await service.update(TENANT_ID, sole.id, role=role, actor=_actor())

    assert staff.updates == []
    assert audit.rows == []


@pytest.mark.parametrize(
    "role",
    [StaffRole.RECEPTION.value, StaffRole.SALES_ASSISTANT.value, StaffRole.SEAMSTRESS.value],
)
async def test_the_self_demote_guard_fires_on_a_move_to_any_floor_role(role: str) -> None:
    """The other half of the same move, and it fires FIRST (`:187-188`) — an
    owner may not demote herself even when another live owner exists, so this
    seeds two."""
    me = _row(staff_id=OWNER_ID, role=StaffRole.OWNER.value)
    service, staff, audit, _ = _service([me])
    staff.live_owners = 2

    with pytest.raises(StaffSelfManageError):
        await service.update(TENANT_ID, me.id, role=role, actor=_actor())

    assert staff.updates == []
    assert audit.rows == []


async def test_a_role_change_into_a_floor_role_audits_both_values() -> None:
    """`STAFF_ROLE_CHANGED`'s details are plain strings (`:251`), so they carry
    the new values with no edit — asserted rather than assumed, because a trail
    recording `to: null` for exactly the three newest roles would be invisible
    until someone read the table."""
    target = _row(role=StaffRole.SHIFT_MANAGER.value)
    service, staff, audit, _ = _service([target])
    staff.live_owners = 2

    await service.update(TENANT_ID, target.id, role=StaffRole.SEAMSTRESS.value, actor=_actor())

    assert audit.actions() == [AuditAction.STAFF_ROLE_CHANGED]
    assert audit.rows[0]["details"] == {
        "from": StaffRole.SHIFT_MANAGER.value,
        "to": StaffRole.SEAMSTRESS.value,
    }


# --- audit: one row per thing that actually changed (spec D8) ---


async def test_a_patch_moving_role_and_password_writes_exactly_two_rows() -> None:
    target = _row(role=StaffRole.SHIFT_MANAGER.value)
    service, staff, audit, _ = _service([target])
    staff.live_owners = 2
    await service.update(
        TENANT_ID,
        target.id,
        role=StaffRole.OWNER.value,
        password="brand-new-pw-1",
        actor=_actor(),
    )
    assert audit.actions() == [AuditAction.STAFF_ROLE_CHANGED, AuditAction.STAFF_PASSWORD_RESET]
    assert audit.rows[0]["details"] == {
        "from": StaffRole.SHIFT_MANAGER.value,
        "to": StaffRole.OWNER.value,
    }


async def test_a_no_op_patch_writes_nothing_and_answers_the_row_unchanged() -> None:
    """F15's D3 rule. `password` is never compared — an argon2 verify against the
    new value to detect "same password" would be a gratuitous verify that leaks
    nothing useful, so a supplied password is ALWAYS a change."""
    target = _row(display_name="Dana", role=StaffRole.SHIFT_MANAGER.value)
    service, staff, audit, _ = _service([target])
    unchanged = await service.update(
        TENANT_ID,
        target.id,
        display_name="Dana",
        role=StaffRole.SHIFT_MANAGER.value,
        actor=_actor(),
    )
    assert unchanged is target
    assert staff.updates == []
    assert audit.rows == []


async def test_a_rename_audits_the_old_and_the_new_name() -> None:
    target = _row(display_name="Old")
    service, _, audit, _ = _service([target])
    await service.update(TENANT_ID, target.id, display_name="New", actor=_actor())
    assert audit.rows[0]["details"] == {"display_name": {"from": "Old", "to": "New"}}


async def test_deactivate_audits_the_row_it_removed() -> None:
    target = _row(email="gone@bella.example", role=StaffRole.SHIFT_MANAGER.value)
    service, staff, audit, _ = _service([target])
    await service.deactivate(TENANT_ID, target.id, actor=_actor())
    assert staff.soft_deleted == [target.id]
    assert audit.actions() == [AuditAction.STAFF_DEACTIVATED]
    assert audit.rows[0]["details"] == {
        "email": "gone@bella.example",
        "role": StaffRole.SHIFT_MANAGER.value,
    }


# --- misses ---


async def test_an_unknown_id_misses_on_both_mutations() -> None:
    """Which is also what another tenant's id answers — RLS and the repository's
    redundant predicate make foreign rows indistinguishable from missing ones."""
    service, _, _, _ = _service([])
    with pytest.raises(StaffNotFoundError):
        await service.update(TENANT_ID, uuid.uuid4(), display_name="X", actor=_actor())
    with pytest.raises(StaffNotFoundError):
        await service.deactivate(TENANT_ID, uuid.uuid4(), actor=_actor())


async def test_list_staff_takes_no_lock_and_reads_the_live_rows() -> None:
    rows = [_row(), _row()]
    service, _, _, trace = _service(rows)
    assert await service.list_staff(TENANT_ID) == rows
    assert trace == ["list_live"]


# --- F38: phone, dates and shift-manager eligibility ------------------------


async def test_create_persists_the_three_profile_fields() -> None:
    service, staff, _, _ = _service()
    await service.create(
        TENANT_ID,
        email="new@bella.example",
        display_name="Dana",
        role=StaffRole.SEAMSTRESS.value,
        password=PASSWORD,
        phone="+972-52-123-4567",
        start_date=date(2026, 8, 1),
        shift_manager_eligible=True,
        actor=_actor(),
    )
    assert staff.inserted[0]["phone"] == "+972-52-123-4567"
    assert staff.inserted[0]["start_date"] == date(2026, 8, 1)
    assert staff.inserted[0]["shift_manager_eligible"] is True


async def test_create_without_the_three_writes_the_absent_states() -> None:
    """NULL phone and NULL start_date are real states — "no number recorded",
    "no start date recorded" — and eligibility defaults to False because an
    unanswered "may she be slotted as shift manager" is a no, not a third
    state."""
    service, staff, _, _ = _service()
    await service.create(
        TENANT_ID,
        email="new@bella.example",
        display_name="Dana",
        role=StaffRole.RECEPTION.value,
        password=PASSWORD,
        actor=_actor(),
    )
    assert staff.inserted[0]["phone"] is None
    assert staff.inserted[0]["start_date"] is None
    assert staff.inserted[0]["shift_manager_eligible"] is False


async def test_a_malformed_phone_is_refused_before_the_row_is_touched() -> None:
    """Through the IMPORTED `validate_phone` (app/boutique/validation.py), never
    a second regex: the boutique profile's number and a staffer's number are the
    same kind of string and one gate is what keeps them agreeing.

    Refused BEFORE any write, so a bad number costs no row and no audit line."""
    target = _row()
    service, staff, audit, _ = _service([target])
    with pytest.raises(DomainValidationError):
        await service.update(TENANT_ID, target.id, phone="not a phone", actor=_actor())
    assert staff.updates == []
    assert audit.rows == []


async def test_an_empty_phone_clears_the_number_rather_than_failing_validation() -> None:
    """The one way to REMOVE a number, and it has to exist: `None` already means
    "not sent" on this API, so without an explicit clear a staffer who asks for
    her number to come off the system could not be obliged until the seven-year
    scrub.

    An emptied `<input>` posts "" natively, so this needs no sentinel value and
    no tri-state — and `validate_phone` would refuse "" anyway (no digit), which
    is why the branch sits above it rather than inside it."""
    target = _row()
    target.phone = "+972-52-123-4567"
    service, staff, audit, _ = _service([target])
    await service.update(TENANT_ID, target.id, phone="   ", actor=_actor())
    assert staff.updates[0]["phone"] == ""
    assert audit.rows[0]["details"] == {"phone": {"from": True, "to": False}}


async def test_the_phone_audit_row_records_presence_and_never_the_number() -> None:
    """STRICTER than the shipped `phone_last4` convention, deliberately.

    `audit_log` has no retention class at all — by ruling, because a clock on the
    evidence would erase the proof of the erasures it records. So ANY digits of a
    staffer's number written here outlive the scrub that exists to destroy it,
    permanently. Presence is the whole fact an audit reader needs ("somebody put
    a number on Dana's row on the 3rd"); the number itself is on the row until
    the clock takes it."""
    target = _row()
    service, _, audit, _ = _service([target])
    await service.update(TENANT_ID, target.id, phone="+972-52-999-8888", actor=_actor())
    assert audit.rows[0]["details"] == {"phone": {"from": False, "to": True}}
    assert "999" not in str(audit.rows[0])


async def test_each_moved_profile_field_writes_exactly_one_audit_row() -> None:
    """F51's D8 rule extending to the new fields unchanged: one row per thing
    that ACTUALLY changed, so a PATCH carrying three fields of which one moved
    writes one row and not three."""
    target = _row()
    target.start_date = date(2026, 1, 1)
    target.shift_manager_eligible = False
    service, _, audit, _ = _service([target])
    await service.update(
        TENANT_ID,
        target.id,
        display_name=target.display_name,
        start_date=date(2026, 2, 2),
        shift_manager_eligible=False,
        actor=_actor(),
    )
    assert audit.actions() == [AuditAction.STAFF_UPDATED]
    assert audit.rows[0]["details"] == {"start_date": {"from": "2026-01-01", "to": "2026-02-02"}}


async def test_toggling_eligibility_audits_both_values() -> None:
    """`shift_manager_eligible` is a boolean SEPARATE from `role`, and the audit
    row keeps them separate too: this is not a STAFF_ROLE_CHANGED, because "may
    be assigned as shift manager" is not "her job is shift manager"."""
    target = _row(role=StaffRole.SALES_ASSISTANT.value)
    service, _, audit, _ = _service([target])
    await service.update(TENANT_ID, target.id, shift_manager_eligible=True, actor=_actor())
    assert audit.actions() == [AuditAction.STAFF_UPDATED]
    assert audit.rows[0]["details"] == {"shift_manager_eligible": {"from": False, "to": True}}


async def test_a_patch_resending_the_three_unchanged_is_still_a_no_op() -> None:
    """F51's D3 no-op rule reaches the new fields, and the inline edit form is
    why it must: that form posts every field on every save, so the stricter
    reading would write three audit rows every time the owner pressed save
    without changing anything."""
    target = _row()
    target.phone = "+972-52-123-4567"
    target.start_date = date(2026, 1, 1)
    target.shift_manager_eligible = True
    service, staff, audit, _ = _service([target])
    returned = await service.update(
        TENANT_ID,
        target.id,
        display_name=target.display_name,
        phone="+972-52-123-4567",
        start_date=date(2026, 1, 1),
        shift_manager_eligible=True,
        actor=_actor(),
    )
    assert returned is target
    assert staff.updates == []
    assert audit.rows == []
