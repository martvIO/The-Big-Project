"""F51 StaffService against fake repositories — no Postgres, so this suite runs
in the fast local pass.

**The step order IS the correctness argument.** A test that still passes with the
lock and the read swapped is not testing this feature, so the first three tests
below assert the recorded statement order, the lock's exact key, and the
deliberate ABSENCE of a lock on create. The concurrency behaviour those steps buy
is proven on real Postgres in test_staff_management_db.py, which is CI-only.
"""

import time
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any, Self

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth.passwords import hash_password, verify_password
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import StaffContext
from app.auth.staff import (
    DuplicateEmailError,
    LastOwnerRequiredError,
    StaffNotFoundError,
    StaffSelfManageError,
    StaffService,
)
from app.catalog.service import MediaNotUploadedError, MediaPresignThrottledError
from app.errors import DomainValidationError
from app.models.constants import AuditAction, StaffRole
from app.models.staff_user import StaffUser
from app.storage.base import (
    MediaNotConfiguredError,
    MediaStorageUnavailableError,
    ObjectHead,
    PresignedPost,
)
from app.storefront.validation import today_jerusalem

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
        self.offboarded: list[dict[str, Any]] = []
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

    async def soft_delete(
        self, session: object, tenant_id: uuid.UUID, staff_id: uuid.UUID, *, last_day: date
    ) -> bool:
        self.trace.append("soft_delete")
        self.soft_deleted.append(staff_id)
        self.offboarded.append({"staff_id": staff_id, "last_day": last_day})
        return True

    # --- the photo triples ---
    #
    # These mutate the SAME StaffUser instance the tests hold, which is what
    # makes "the live photo survived a presign" assertable off the row rather
    # than off a call log. Each mirrors the real repository's guard exactly:
    # promote is conditional on `photo_pending_key IS NOT NULL`, clear is not.

    async def set_pending_photo(
        self,
        session: object,
        tenant_id: uuid.UUID,
        staff_id: uuid.UUID,
        *,
        storage_key: str | None,
        content_type: str | None,
        at: datetime | None,
    ) -> bool:
        self.trace.append("set_pending_photo")
        row = next((row for row in self.rows if row.id == staff_id), None)
        if row is None:
            return False
        row.photo_pending_key = storage_key
        row.photo_pending_content_type = content_type
        row.photo_pending_at = at
        return True

    async def promote_pending_photo(
        self, session: object, tenant_id: uuid.UUID, staff_id: uuid.UUID, *, at: datetime
    ) -> StaffUser | None:
        self.trace.append("promote_pending_photo")
        row = next((row for row in self.rows if row.id == staff_id), None)
        if row is None or row.photo_pending_key is None:
            return None
        row.photo_key = row.photo_pending_key
        row.photo_content_type = row.photo_pending_content_type
        row.photo_confirmed_at = at
        row.photo_pending_key = None
        row.photo_pending_content_type = None
        row.photo_pending_at = None
        return row

    async def clear_photo(
        self, session: object, tenant_id: uuid.UUID, staff_id: uuid.UUID
    ) -> StaffUser | None:
        self.trace.append("clear_photo")
        row = next((row for row in self.rows if row.id == staff_id), None)
        if row is None:
            return None
        row.photo_key = None
        row.photo_content_type = None
        row.photo_confirmed_at = None
        row.photo_pending_key = None
        row.photo_pending_content_type = None
        row.photo_pending_at = None
        return row


class FakeDeleteStorage:
    """Only `delete_object` — the one storage member offboarding touches. The
    read-side signer is exercised in test_staff_photo.py against a structurally
    complete fake; this one is deliberately narrow because it is injected onto a
    private attribute rather than passed to a typed parameter."""

    def __init__(self, *, raises: Exception | None = None) -> None:
        self._raises = raises
        self.deleted: list[str] = []

    async def delete_object(self, *, key: str) -> None:
        self.deleted.append(key)
        if self._raises is not None:
            raise self._raises


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
    service = StaffService(
        lambda: session,  # type: ignore[arg-type]
        media_storage=FakeDeleteStorage(),  # type: ignore[arg-type]
        # A real limiter with a real budget — the photo tests below assert the
        # throttle, and a stub would make those assertions vacuous.
        presign_rate_limiter=FixedWindowRateLimiter(
            max_attempts=3, window_seconds=900, clock=time.monotonic
        ),
    )
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
    # F38 widened this row from two keys to four. Asserted by equality rather
    # than by containment so the widening had to be made here, on purpose:
    # `last_day` is the retention clock's zero and `photo_storage_key` is the
    # only durable record of an orphaned object when the best-effort delete
    # fails, so neither may quietly disappear from the trail later.
    assert audit.rows[0]["details"] == {
        "email": "gone@bella.example",
        "role": StaffRole.SHIFT_MANAGER.value,
        "last_day": today_jerusalem().isoformat(),
        "photo_storage_key": None,
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
    # SCOPED TO `details`, not to the whole row. The row also carries randomly
    # generated UUIDs, every decimal digit is also a hex digit, and "999" spells
    # itself in roughly one UUID pair in fifty — this assertion red-flagged an
    # `actor_id` of `…4775-9660-999eab00c064` on its first run. A leak detector
    # that fires on unrelated randomness destroys the signal in both directions.
    assert "999" not in str(audit.rows[0]["details"])


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


# --- F38: offboarding -------------------------------------------------------


def _offboard_service(
    rows: list[StaffUser] | None = None, *, delete_raises: Exception | None = None
) -> tuple[StaffService, FakeStaffRepository, FakeAuditRepository, FakeDeleteStorage]:
    """`_service` already wires a quiet storage fake, so this only replaces it
    when a test needs to SEE the deletes or make one fail."""
    service, staff, audit, _ = _service(rows)
    storage = FakeDeleteStorage(raises=delete_raises)
    service._storage = storage  # type: ignore[assignment]
    return service, staff, audit, storage


async def test_offboarding_defaults_last_day_to_today_in_jerusalem() -> None:
    """A missing default would silently exempt her from the retention clock
    FOREVER — the policy's predicate requires `last_day IS NOT NULL`, so a NULL
    here is not "unknown", it is "never scrub this person".

    Jerusalem and not UTC: the two are different calendar days for two or three
    hours of every night, and this is the date the seven-year clock counts from.
    """
    target = _row()
    service, staff, _, _ = _offboard_service([target])
    await service.deactivate(TENANT_ID, target.id, actor=_actor())
    assert staff.offboarded[0]["last_day"] == today_jerusalem()


async def test_an_explicit_last_day_is_written_instead_of_today() -> None:
    target = _row()
    target.start_date = date(2020, 1, 1)
    service, staff, _, _ = _offboard_service([target])
    await service.deactivate(TENANT_ID, target.id, last_day=date(2026, 8, 31), actor=_actor())
    assert staff.offboarded[0]["last_day"] == date(2026, 8, 31)


async def test_a_last_day_more_than_a_year_out_is_refused_and_writes_nothing() -> None:
    """A typo fence, not a policy about notice periods. `2036` for `2026` is one
    keystroke and would park her outside the scrub for a decade."""
    target = _row()
    service, staff, audit, _ = _offboard_service([target])
    with pytest.raises(DomainValidationError):
        await service.deactivate(
            TENANT_ID,
            target.id,
            last_day=today_jerusalem() + timedelta(days=366),
            actor=_actor(),
        )
    assert staff.offboarded == []
    assert audit.rows == []


async def test_a_last_day_before_her_start_date_is_refused() -> None:
    """She cannot have left before she arrived, and the pair is the only place
    the two dates are ever compared — so this is where an inverted range gets
    caught rather than in a report six months later."""
    target = _row()
    target.start_date = date(2026, 5, 1)
    service, staff, _, _ = _offboard_service([target])
    with pytest.raises(DomainValidationError):
        await service.deactivate(TENANT_ID, target.id, last_day=date(2026, 4, 30), actor=_actor())
    assert staff.offboarded == []


async def test_a_last_day_before_a_start_date_she_does_not_have_is_allowed() -> None:
    """NULL `start_date` means "no start date recorded", which is the state every
    pre-F38 row is in. Comparing against it would refuse every offboarding in the
    boutique until somebody backfilled a column nobody has."""
    target = _row()
    service, staff, _, _ = _offboard_service([target])
    await service.deactivate(TENANT_ID, target.id, last_day=date(2020, 1, 1), actor=_actor())
    assert staff.offboarded[0]["last_day"] == date(2020, 1, 1)


async def test_offboarding_never_sweeps_her_sessions() -> None:
    """THE assertion, and it is an assertion about an ABSENCE.

    `resolve_session` re-reads `staff_users` on every request and `by_id` filters
    `deleted_at IS NULL`, so her live cookie is a 401 on her very next request —
    proven on real Postgres by F31. F20's `sessions` policy reclaims the dead rows
    on its own clock. A `revoke_for_staff_user` here would be a SECOND mechanism
    for a fact the first one already guarantees, and a second mechanism is one
    that can disagree."""
    target = _row()
    service, _, _, _ = _offboard_service([target])
    sessions = _session_spy(service, Trace())
    await service.deactivate(TENANT_ID, target.id, actor=_actor())
    assert sessions.revoked == []


async def test_the_audit_row_carries_the_last_day_and_the_photo_key() -> None:
    """`photo_storage_key` is the load-bearing field: the object delete below is
    best-effort and swallows a storage outage, so on that path THIS ROW is the
    only durable record of which object was orphaned."""
    target = _row()
    target.photo_key = "tenants/t/staff/s/photo/p.jpg"
    service, _, audit, _ = _offboard_service([target])
    await service.deactivate(TENANT_ID, target.id, last_day=None, actor=_actor())
    assert audit.actions() == [AuditAction.STAFF_DEACTIVATED]
    details = audit.rows[0]["details"]
    assert details["last_day"] == today_jerusalem().isoformat()
    assert details["photo_storage_key"] == "tenants/t/staff/s/photo/p.jpg"


async def test_a_staffer_with_no_photo_audits_a_null_key_and_deletes_nothing() -> None:
    target = _row()
    service, _, audit, storage = _offboard_service([target])
    await service.deactivate(TENANT_ID, target.id, actor=_actor())
    assert audit.rows[0]["details"]["photo_storage_key"] is None
    assert storage.deleted == []


async def test_the_photo_object_is_deleted_after_the_transaction() -> None:
    """At OFFBOARDING and not at the seven-year scrub — stricter than the brief,
    deliberately. Her face is the most identifying datum on the row, nothing
    operational reads it once she is gone, and it keeps the retention policy a
    PURE SQL STATEMENT: the shipped `PolicyRun` contract hands a policy a session
    and nothing else, so an S3 call inside one would widen a tested interface for
    a single caller."""
    target = _row()
    target.photo_key = "tenants/t/staff/s/photo/p.jpg"
    target.photo_pending_key = "tenants/t/staff/s/photo/pending.png"
    service, _, _, storage = _offboard_service([target])
    await service.deactivate(TENANT_ID, target.id, actor=_actor())
    # BOTH objects: an in-flight replace at the moment she is offboarded would
    # otherwise leave the pending upload in the bucket with nothing pointing at
    # it and no audit row naming it.
    assert storage.deleted == [
        "tenants/t/staff/s/photo/p.jpg",
        "tenants/t/staff/s/photo/pending.png",
    ]


async def test_a_storage_failure_does_not_fail_the_offboarding() -> None:
    """Best-effort and LOGGED, never raised: the row is already soft-deleted and
    committed, so raising here would answer 503 to an owner whose staffer IS in
    fact offboarded — and she would press it again."""
    target = _row()
    target.photo_key = "tenants/t/staff/s/photo/p.jpg"
    service, staff, audit, _ = _offboard_service(
        [target], delete_raises=MediaStorageUnavailableError()
    )
    await service.deactivate(TENANT_ID, target.id, actor=_actor())
    assert staff.offboarded[0]["staff_id"] == target.id
    assert audit.rows[0]["details"]["photo_storage_key"] == "tenants/t/staff/s/photo/p.jpg"


async def test_the_three_f51_guards_still_fire_and_none_of_them_writes_a_last_day() -> None:
    """F51's protocol is unchanged, and the addition must not have created a path
    where a refused offboarding still stamps a leaving date on a live employee."""
    me = _row(staff_id=OWNER_ID, role=StaffRole.OWNER.value)
    service, staff, _, _ = _offboard_service([me])
    with pytest.raises(StaffSelfManageError):
        await service.deactivate(TENANT_ID, OWNER_ID, actor=_actor())
    assert staff.offboarded == []

    only_owner = _row(role=StaffRole.OWNER.value)
    service, staff, _, _ = _offboard_service([only_owner])
    staff.live_owners = 1
    with pytest.raises(LastOwnerRequiredError):
        await service.deactivate(TENANT_ID, only_owner.id, actor=_actor())
    assert staff.offboarded == []

    service, staff, _, _ = _offboard_service([])
    with pytest.raises(StaffNotFoundError):
        await service.deactivate(TENANT_ID, uuid.uuid4(), actor=_actor())
    assert staff.offboarded == []


# --- F38: the photo pipeline, driven through the SERVICE ---------------------
#
# The gap this section closes: `test_staff_photo.py` covers the pure module (key
# shape, bounds, sign-and-degrade) and `test_staff_api.py` substitutes a
# duck-typed FakeStaffService, so until now NOTHING executed presign_photo,
# confirm_photo or delete_photo at all. Inverting the magic-byte check at
# staff.py:725 left the whole suite green while every valid JPEG was rejected and
# every polyglot promoted — and that check is the ONE defence this pipeline adds
# on top of the S3 POST policy.
#
# Fakes rather than real Postgres and a real bucket, deliberately: every property
# below is a property of the SERVICE's ordering — verify before promote, promote
# before the superseded delete, clear before reject — and none of them needs a
# row on disk to be falsified. The RLS and GRANT halves are already proven in
# test_staff_management_db.py.

JPEG_MAGIC = b"\xff\xd8\xff" + b"\x00" * 13
UPLOADED_JPEG = ObjectHead(content_type="image/jpeg", byte_size=1024)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


class FakePhotoStorage:
    """A structurally complete `MediaStorage` (the `test_staff_photo.py` rule: a
    partial fake needs a cast, and a cast is what lets a later signature change
    on the real port sail past every test)."""

    def __init__(
        self,
        *,
        configured: bool = True,
        head: ObjectHead | None = UPLOADED_JPEG,
        prefix: bytes = JPEG_MAGIC,
        presign_raises: Exception | None = None,
    ) -> None:
        self._configured = configured
        self.head = head
        self.prefix = prefix
        self._presign_raises = presign_raises
        self.presigned: list[str] = []
        self.headed: list[str] = []
        self.read: list[str] = []
        self.deleted: list[str] = []
        #: Awaited from inside `read_prefix`, i.e. after confirm has read the
        #: pending key and BEFORE it takes the promote lock. That is the exact
        #: window a concurrent presign lands in.
        self.on_read_prefix: Any = None

    @property
    def is_configured(self) -> bool:
        return self._configured

    def presigned_post(
        self, *, key: str, content_type: str, exact_bytes: int, expires_in: int
    ) -> PresignedPost:
        self.presigned.append(key)
        if self._presign_raises is not None:
            raise self._presign_raises
        return PresignedPost(url="https://bucket.example/", fields={"policy": "opaque"})

    def signed_get_url(self, *, key: str, content_type: str, filename: str, expires_in: int) -> str:
        return f"https://bucket.example/{key}?signed"

    async def head_object(self, *, key: str) -> ObjectHead | None:
        self.headed.append(key)
        return self.head

    async def read_prefix(self, *, key: str, length: int) -> bytes:
        self.read.append(key)
        if self.on_read_prefix is not None:
            hook, self.on_read_prefix = self.on_read_prefix, None
            await hook()
        return self.prefix

    async def delete_object(self, *, key: str) -> None:
        self.deleted.append(key)


def _photo_service(
    rows: list[StaffUser] | None = None,
    *,
    storage: FakePhotoStorage | None = None,
    max_attempts: int = 3,
) -> tuple[StaffService, FakeStaffRepository, FakeAuditRepository, FakePhotoStorage]:
    service, staff, audit, _ = _service(rows)
    photo_storage = storage or FakePhotoStorage()
    service._storage = photo_storage  # type: ignore[assignment]
    service._presign_limiter = FixedWindowRateLimiter(  # type: ignore[assignment]
        max_attempts=max_attempts, window_seconds=900, clock=time.monotonic
    )
    return service, staff, audit, photo_storage


async def _presign(service: StaffService, staff_id: uuid.UUID, **kwargs: Any) -> Any:
    return await service.presign_photo(
        TENANT_ID,
        staff_id,
        content_type=kwargs.pop("content_type", "image/jpeg"),
        byte_size=kwargs.pop("byte_size", 1024),
        actor_id=OWNER_ID,
    )


# --- presign ---


async def test_presign_writes_only_the_pending_triple_and_the_live_photo_survives() -> None:
    """The pair of triples IS the replace mechanism: the photo currently on the
    board must keep rendering for the whole upload, so a presign that touched the
    live triple would blank every face in the shop for the duration of one
    owner's file picker."""
    target = _row()
    target.photo_key = "tenants/t/staff/s/photo/live.jpg"
    target.photo_content_type = "image/jpeg"
    service, staff, audit, storage = _photo_service([target])

    presigned = await _presign(service, target.id)

    assert target.photo_key == "tenants/t/staff/s/photo/live.jpg"
    assert target.photo_pending_key is not None
    assert target.photo_pending_key != target.photo_key
    # The POST policy pins an EXACT content-length range, so the ceiling handed
    # back is precisely what the browser declared and not the 2 MiB cap.
    assert presigned.max_bytes == 1024
    assert audit.actions() == [AuditAction.STAFF_PHOTO_PRESIGNED]
    assert audit.rows[0]["details"]["storage_key"] == target.photo_pending_key
    assert storage.deleted == []


async def test_a_second_presign_supersedes_the_first_and_deletes_its_object() -> None:
    """The only thing bounding the orphan window: after the overwrite the row
    names the old key nowhere, so if this delete is dropped the object is
    unreachable and unaudited forever."""
    target = _row()
    service, _, _, storage = _photo_service([target])
    await _presign(service, target.id)
    first = target.photo_pending_key

    await _presign(service, target.id, content_type="image/png")

    assert first is not None
    assert storage.deleted == [first]
    assert target.photo_pending_key != first


async def test_presign_refuses_a_bad_type_and_an_over_cap_size_before_touching_the_row() -> None:
    target = _row()
    service, _, audit, storage = _photo_service([target])
    for content_type, byte_size in (("image/svg+xml", 1024), ("image/jpeg", 3_000_000)):
        with pytest.raises(DomainValidationError):
            await _presign(service, target.id, content_type=content_type, byte_size=byte_size)
    assert target.photo_pending_key is None
    assert audit.rows == []
    assert storage.presigned == []


async def test_an_unconfigured_bucket_refuses_the_presign_before_writing_a_pending_triple() -> None:
    """A pending triple against a bucket that does not exist is a console stuck
    on "uploading…" against an upload the browser never received a policy for."""
    target = _row()
    service, _, audit, _ = _photo_service([target], storage=FakePhotoStorage(configured=False))
    with pytest.raises(MediaNotConfiguredError):
        await _presign(service, target.id)
    assert target.photo_pending_key is None
    assert audit.rows == []


async def test_a_signing_failure_after_the_commit_rolls_the_pending_triple_back() -> None:
    """`is_configured` passed and signing failed anyway — a rotated IAM key. The
    pending triple is already COMMITTED, so leaving it would make the console
    render a permanent "uploading…"."""
    target = _row()
    service, _, _, _ = _photo_service(
        [target],
        storage=FakePhotoStorage(presign_raises=MediaStorageUnavailableError()),
    )
    with pytest.raises(MediaStorageUnavailableError):
        await _presign(service, target.id)
    assert target.photo_pending_key is None


async def test_the_staff_throttle_bounds_presign_and_counts_successes() -> None:
    """`FixedWindowRateLimiter` counts only what is explicitly recorded and its
    docstring says successes never count — so a SUCCESSFUL presign, which
    authorises a 2 MiB write to our bucket, is recorded by hand or the throttle
    is inert. This is the test that reds if that line is deleted as a bug."""
    target = _row()
    service, _, _, _ = _photo_service([target], max_attempts=2)
    await _presign(service, target.id)
    await _presign(service, target.id)
    with pytest.raises(MediaPresignThrottledError):
        await _presign(service, target.id)


async def test_the_staff_throttle_is_its_own_instance_and_not_the_catalogs() -> None:
    """`max_attempts` lives ON the limiter, so two keys on one limiter share a
    single ceiling (`.memory/limiter-max-is-per-instance`). Sharing the catalog's
    would let a morning of gallery work lock out one avatar — this asserts the
    two budgets are genuinely independent, which is the entire justification for
    the second FixedWindowRateLimiter at main.py:857."""
    target = _row()
    service, _, _, _ = _photo_service([target], max_attempts=1)
    catalog_limiter = FixedWindowRateLimiter(
        max_attempts=1, window_seconds=900, clock=time.monotonic
    )
    catalog_limiter.record_failure(f"presign:{TENANT_ID}")
    assert catalog_limiter.is_blocked(f"presign:{TENANT_ID}")

    await _presign(service, target.id)
    assert not catalog_limiter.is_blocked(f"presign:staff:{TENANT_ID}")


# --- confirm ---


async def test_confirm_promotes_the_pending_triple_and_audits_the_key_it_promoted() -> None:
    target = _row()
    service, _, audit, storage = _photo_service([target])
    await _presign(service, target.id)
    pending = target.photo_pending_key

    confirmed = await service.confirm_photo(TENANT_ID, target.id, actor_id=OWNER_ID)

    assert confirmed.photo_key == pending
    assert confirmed.photo_content_type == "image/jpeg"
    assert confirmed.photo_confirmed_at is not None
    assert confirmed.photo_pending_key is None
    assert audit.actions() == [
        AuditAction.STAFF_PHOTO_PRESIGNED,
        AuditAction.STAFF_PHOTO_CONFIRMED,
    ]
    assert audit.rows[1]["details"] == {"storage_key": pending, "superseded_storage_key": None}
    assert storage.headed == [pending]
    assert storage.read == [pending]


async def test_a_retried_confirm_promotes_nothing_and_writes_no_second_audit_row() -> None:
    """A row asserting a promotion nobody performed is worse than no row: the
    audit trail is the only durable record of which object went live."""
    target = _row()
    service, _, audit, storage = _photo_service([target])
    await _presign(service, target.id)
    first = await service.confirm_photo(TENANT_ID, target.id, actor_id=OWNER_ID)
    second = await service.confirm_photo(TENANT_ID, target.id, actor_id=OWNER_ID)

    assert second.photo_key == first.photo_key
    assert audit.actions().count(AuditAction.STAFF_PHOTO_CONFIRMED) == 1
    # The short-circuit is BEFORE the network calls: a retry after a lost
    # response must not re-head an object that is already live.
    assert len(storage.headed) == 1
    assert storage.deleted == []


async def test_a_magic_byte_mismatch_is_refused_the_object_deleted_and_the_row_cleared() -> None:
    """The content-type-honest polyglot: it passed the POST policy at exactly the
    declared size and exactly the declared type, and THIS is what refuses it.

    ACCEPTANCE, stated so it can be checked rather than believed: inverting
    `if not matches_magic_prefix(...)` at staff.py must turn this test red."""
    target = _row()
    target.photo_key = "tenants/t/staff/s/photo/live.jpg"
    target.photo_content_type = "image/jpeg"
    service, _, audit, storage = _photo_service([target], storage=FakePhotoStorage(prefix=b"<svg"))
    await _presign(service, target.id)
    pending = target.photo_pending_key

    with pytest.raises(DomainValidationError):
        await service.confirm_photo(TENANT_ID, target.id, actor_id=OWNER_ID)

    assert storage.deleted == [pending]
    assert target.photo_pending_key is None
    # The live photo is UNTOUCHED — a rejected replace never blanks the cell.
    assert target.photo_key == "tenants/t/staff/s/photo/live.jpg"
    assert AuditAction.STAFF_PHOTO_CONFIRMED not in audit.actions()


async def test_a_content_type_mismatch_is_refused_before_the_bytes_are_even_read() -> None:
    """The ORDER is the security argument: head → declared-type match →
    read_prefix → magic match. An object whose stored type disagrees with what
    was declared is refused without spending a range read on it."""
    target = _row()
    storage = FakePhotoStorage(head=ObjectHead(content_type="image/png", byte_size=1024))
    service, _, _, _ = _photo_service([target], storage=storage)
    await _presign(service, target.id, content_type="image/jpeg")
    pending = target.photo_pending_key

    with pytest.raises(DomainValidationError):
        await service.confirm_photo(TENANT_ID, target.id, actor_id=OWNER_ID)

    assert storage.read == []
    assert storage.deleted == [pending]


async def test_a_confirm_with_no_object_in_the_bucket_says_so_and_keeps_the_triple() -> None:
    """Distinct from a mismatch: nothing was uploaded, so there is nothing to
    delete and the pending triple stays valid for the retry the browser is about
    to make against a policy that has not expired."""
    target = _row()
    service, _, _, storage = _photo_service([target], storage=FakePhotoStorage(head=None))
    await _presign(service, target.id)

    with pytest.raises(MediaNotUploadedError):
        await service.confirm_photo(TENANT_ID, target.id, actor_id=OWNER_ID)
    assert target.photo_pending_key is not None
    assert storage.deleted == []


async def test_a_confirmed_replace_deletes_the_superseded_object_after_auditing_it() -> None:
    """AFTER the audit row that names it: the delete is best-effort, so on a
    storage outage that row is the only durable record of the orphan."""
    target = _row()
    target.photo_key = "tenants/t/staff/s/photo/old.jpg"
    target.photo_content_type = "image/jpeg"
    service, _, audit, storage = _photo_service([target])
    await _presign(service, target.id)
    pending = target.photo_pending_key

    await service.confirm_photo(TENANT_ID, target.id, actor_id=OWNER_ID)

    assert audit.rows[1]["details"] == {
        "storage_key": pending,
        "superseded_storage_key": "tenants/t/staff/s/photo/old.jpg",
    }
    assert storage.deleted == ["tenants/t/staff/s/photo/old.jpg"]


async def test_confirm_promotes_only_the_object_it_actually_verified() -> None:
    """⚠ THE VERIFIED OBJECT AND THE PROMOTED OBJECT MUST BE THE SAME ONE.

    `promote_pending_photo` copies whatever key is on the row at promote time,
    and the two network calls run outside any session against the key read in the
    FIRST transaction. Without the comparison before the promote, an owner can
    presign K1, upload a valid JPEG, issue confirm A, then presign K2 inside the
    two-network-call window and POST arbitrary bytes at the declared type and
    size — and confirm A promotes K2, a body whose magic bytes were never read,
    under an audit row that says K1.

    The hook fires from inside `read_prefix`, which is exactly that window."""
    target = _row()
    service, _, audit, storage = _photo_service([target])
    await _presign(service, target.id)
    verified = target.photo_pending_key

    async def racing_presign() -> None:
        await _presign(service, target.id, content_type="image/png")

    storage.on_read_prefix = racing_presign

    result = await service.confirm_photo(TENANT_ID, target.id, actor_id=OWNER_ID)

    raced = target.photo_pending_key
    assert raced is not None
    assert raced != verified
    # Nothing was promoted, and in particular the unverified K2 did not go live.
    assert result.photo_key is None
    assert target.photo_pending_key == raced
    assert AuditAction.STAFF_PHOTO_CONFIRMED not in audit.actions()


async def test_a_rejected_confirm_racing_a_fresh_presign_leaves_the_new_triple_alone() -> None:
    """Same root cause on the reject arm: an unconditional clear would wipe the
    triple the NEW presign just wrote while deleting only the old object, leaving
    an upload the browser is still waiting on with nothing to confirm."""
    target = _row()
    service, _, _, storage = _photo_service([target], storage=FakePhotoStorage(prefix=b"<svg"))
    await _presign(service, target.id)
    rejected = target.photo_pending_key

    async def racing_presign() -> None:
        await _presign(service, target.id, content_type="image/png")

    storage.on_read_prefix = racing_presign

    with pytest.raises(DomainValidationError):
        await service.confirm_photo(TENANT_ID, target.id, actor_id=OWNER_ID)

    assert target.photo_pending_key is not None
    assert target.photo_pending_key != rejected
    assert rejected in storage.deleted


async def test_an_unconfigured_bucket_refuses_confirm_and_delete_too() -> None:
    """All three WRITE paths answer 503. The READ path is unaffected — a board
    poll degrades `photo_url` to null and never 503s (`sign_staff_photo`)."""
    target = _row()
    service, _, _, _ = _photo_service([target], storage=FakePhotoStorage(configured=False))
    with pytest.raises(MediaNotConfiguredError):
        await service.confirm_photo(TENANT_ID, target.id, actor_id=OWNER_ID)
    with pytest.raises(MediaNotConfiguredError):
        await service.delete_photo(TENANT_ID, target.id, actor_id=OWNER_ID)


# --- delete ---


async def test_delete_clears_both_triples_audits_the_live_key_and_removes_both_objects() -> None:
    target = _row()
    target.photo_key = "tenants/t/staff/s/photo/live.jpg"
    target.photo_content_type = "image/jpeg"
    target.photo_confirmed_at = CREATED_AT
    target.photo_pending_key = "tenants/t/staff/s/photo/inflight.png"
    service, _, audit, storage = _photo_service([target])

    cleared = await service.delete_photo(TENANT_ID, target.id, actor_id=OWNER_ID)

    assert cleared.photo_key is None
    assert cleared.photo_content_type is None
    assert cleared.photo_confirmed_at is None
    assert cleared.photo_pending_key is None
    assert audit.actions() == [AuditAction.STAFF_PHOTO_DELETED]
    assert audit.rows[0]["details"] == {"storage_key": "tenants/t/staff/s/photo/live.jpg"}
    assert storage.deleted == [
        "tenants/t/staff/s/photo/live.jpg",
        "tenants/t/staff/s/photo/inflight.png",
    ]


async def test_every_photo_path_refuses_an_id_this_tenant_does_not_own() -> None:
    service, _, audit, _ = _photo_service([])
    stranger = uuid.uuid4()
    with pytest.raises(StaffNotFoundError):
        await _presign(service, stranger)
    with pytest.raises(StaffNotFoundError):
        await service.confirm_photo(TENANT_ID, stranger, actor_id=OWNER_ID)
    with pytest.raises(StaffNotFoundError):
        await service.delete_photo(TENANT_ID, stranger, actor_id=OWNER_ID)
    assert audit.rows == []
