"""D6's capacity write, driven with fakes and no database.

`test_atelier_service.py`'s scaffold, narrowed to the three repository calls this
path makes: the target read, the guarded UPDATE and the audit row.

⚠ THE WRITE FAKE STAMPS THE NEW HOURS ONTO THE ROW IT WAS HANDED, and that is
not decoration — it is what the real path does twice over. `update(StaffUser)` is
ORM-enabled DML whose default `evaluate` synchronization writes the SET value
onto the identity-mapped instance, and `_refreshed`'s `populate_existing=True`
then overwrites that same object's attributes from the database. Both hand back
the object `by_id` already returned. A fake that answered a fresh, untouched row
would leave the capture-after-the-write mutation GREEN here — which is exactly
what F57's note records happening.

What is NOT proven here and must not be claimed: that `populate_existing=True`
defeats a real identity map under a real interleave. `test_atelier_capacity_db.py`
owns that, and it is the one assertion no fake can produce.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.atelier.schemas import SeamstressCapacityResponse, SetCapacityRequest
from app.atelier.service import AtelierService
from app.atelier.stages import MAX_WEEKLY_CAPACITY_HOURS
from app.atelier.validation import AtelierValidationError
from app.auth.service import StaffContext
from app.db.repositories.audit_log import AuditLogRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.errors import DomainNotFoundError, DomainValidationError
from app.models.constants import AuditAction, StaffRole
from app.models.staff_user import StaffUser

TENANT_ID = uuid.uuid4()
SEAMSTRESS_ID = uuid.uuid4()
OTHER_TENANTS_ID = uuid.uuid4()
TENANT_DEFAULT = 40


def _actor(role: StaffRole = StaffRole.SHIFT_MANAGER) -> StaffContext:
    return StaffContext(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        email="manager@bella.example",
        display_name="רות",
        role=role.value,
    )


def _staff_row(
    role: StaffRole = StaffRole.SEAMSTRESS,
    *,
    hours: int | None = None,
    staff_id: uuid.UUID = SEAMSTRESS_ID,
) -> StaffUser:
    row = StaffUser(
        tenant_id=TENANT_ID,
        email="noa@bella.example",
        password_hash="not-a-real-hash",
        display_name="נועה",
        role=role.value,
    )
    row.id = staff_id
    row.deleted_at = None
    row.weekly_capacity_hours = hours
    return row


class _FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeSession:
    def begin(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def execute(self, *args: object, **kwargs: object) -> None:
        return None


class _Repos:
    def __init__(self) -> None:
        self.order: list[str] = []
        self.audit: list[dict[str, Any]] = []
        self.calls: dict[str, Any] = {}
        # `None` is the shipped answer for gone, another tenant's, or never
        # existed — `by_id` already filters tenant_id AND deleted_at IS NULL.
        self.staff: StaffUser | None = None
        # `None` is zero rows from the guarded UPDATE: the live row vanished
        # BETWEEN the check and the write. That race is this route's only 404.
        self.wrote: bool = True


def _install(monkeypatch: pytest.MonkeyPatch, repos: _Repos) -> _Repos:
    async def _by_id(
        _s: object, _session: object, _t: uuid.UUID, staff_id: uuid.UUID
    ) -> StaffUser | None:
        repos.order.append("staff_by_id")
        repos.calls["staff_by_id"] = staff_id
        return repos.staff

    async def _set_hours(
        _s: object,
        _session: object,
        _t: uuid.UUID,
        staff_id: uuid.UUID,
        *,
        hours: int | None,
    ) -> StaffUser | None:
        repos.order.append("set_weekly_capacity_hours")
        repos.calls["set_weekly_capacity_hours"] = {"staff_id": staff_id, "hours": hours}
        if not repos.wrote or repos.staff is None:
            return None
        # See the module docstring: the real path hands back the SAME object,
        # carrying the new value.
        repos.staff.weekly_capacity_hours = hours
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

    monkeypatch.setattr(StaffUsersRepository, "by_id", _by_id)
    monkeypatch.setattr(StaffUsersRepository, "set_weekly_capacity_hours", _set_hours)
    monkeypatch.setattr(AuditLogRepository, "record", _record)
    return repos


def _service(repos: _Repos) -> AtelierService:
    @asynccontextmanager
    async def _factory() -> AsyncIterator[_FakeSession]:
        yield _FakeSession()

    return AtelierService(cast(async_sessionmaker, _factory))


async def _set(
    service: AtelierService,
    hours: int | None,
    *,
    staff_user_id: uuid.UUID = SEAMSTRESS_ID,
    tenant_default: int | None = TENANT_DEFAULT,
    actor: StaffContext | None = None,
) -> SeamstressCapacityResponse:
    return await service.set_capacity(
        TENANT_ID,
        staff_user_id,
        SetCapacityRequest(weekly_capacity_hours=hours),
        actor=actor or _actor(),
        tenant_default=tenant_default,
    )


# --- the one indistinguishable 400 (D6, D13) ---------------------------------


async def test_every_ordinary_refusal_is_one_indistinguishable_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ FOUR CASES, ONE REFUSAL, AND THERE IS NO 404 ON THIS ROUTE.

    `_require_seamstress` raises the same `AtelierValidationError` for `row is
    None` and for a wrong role, and `by_id` already filters BOTH `tenant_id` and
    `deleted_at IS NULL` — so a live receptionist, a retired seamstress, an
    unknown id and another tenant's id are one 400 with a byte-identical body.
    The handler renders `str(exc)` (`main.py:949-953`), so identical messages
    ARE identical bodies.

    That is correct rather than sloppy: RLS plus the tenant predicate make a
    foreign row indistinguishable from a missing one by design, which is the
    posture `_present` already takes for tickets. The obvious reading —
    "missing → 404" — is unreachable without forking a shipped helper, and the
    information it would leak (this id exists but is not a seamstress) buys a
    prober something for no product gain.
    """
    seen: list[tuple[type[Exception], str]] = []
    for staff in (
        _staff_row(StaffRole.RECEPTION),  # a live staffer with the wrong role
        None,  # retired: by_id filters deleted_at IS NULL
        None,  # an unknown id
        None,  # another tenant's id: by_id filters tenant_id, and RLS agrees
    ):
        repos = _install(monkeypatch, _Repos())
        repos.staff = staff
        with pytest.raises(AtelierValidationError) as excinfo:
            await _set(_service(repos), 24, staff_user_id=OTHER_TENANTS_ID)
        seen.append((type(excinfo.value), str(excinfo.value)))

    assert len(seen) == 4
    assert len(set(seen)) == 1, f"the four refusals are distinguishable: {seen}"
    # A DomainValidationError, so the shipped handler maps it to 400 and F42
    # adds no error code (D13).
    assert issubclass(seen[0][0], DomainValidationError)


async def test_the_refused_target_is_never_written_and_never_audited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`test_floor_service.py`'s shipped assertion shape, on the refusal this
    route actually has. ⚠ The plan calls this "the pure-role refusal"; there is
    no such thing here — the ROLE refusal is the route's `require_role(OWNER,
    SHIFT_MANAGER)` and never reaches the service at all (D6). What the service
    refuses is the TARGET, and it must refuse it before writing anything."""
    repos = _install(monkeypatch, _Repos())
    repos.staff = _staff_row(StaffRole.SALES_ASSISTANT)
    with pytest.raises(AtelierValidationError):
        await _set(_service(repos), 24)
    assert repos.order == ["staff_by_id"]
    assert repos.audit == []


async def test_a_row_that_vanishes_between_the_check_and_the_update_is_the_only_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zero rows from the guarded UPDATE means the live row was soft-deleted
    after `_require_seamstress` passed. A race, and the ONLY 404 on this
    route."""
    repos = _install(monkeypatch, _Repos())
    repos.staff = _staff_row(hours=12)
    repos.wrote = False
    with pytest.raises(DomainNotFoundError):
        await _set(_service(repos), 24)
    assert repos.audit == []


# --- StrictInt (D5's hole, closed on this request model too) -----------------


@pytest.mark.parametrize("value", [True, False, "24", 24.0, "", [24]])
def test_a_strict_int_is_required(value: Any) -> None:
    """⚠ THE NAMED MUTATION. `ForbidExtraModel` sets `extra="forbid"` and NOTHING
    else (`app/schemas.py:13-18` — no `strict=True` anywhere), so a plain `int`
    would COERCE before any validator or bound ran: `true` becomes `1`, lands
    inside `0..168`, and is accepted as a ONE-HOUR WEEK. Relax `StrictInt` to
    `int` and the `True` row turns 200."""
    with pytest.raises(ValidationError):
        SetCapacityRequest(weekly_capacity_hours=value)


@pytest.mark.parametrize("value", [-1, MAX_WEEKLY_CAPACITY_HOURS + 1, 1000])
def test_the_hours_are_bounded_by_the_columns_own_check(value: int) -> None:
    with pytest.raises(ValidationError):
        SetCapacityRequest(weekly_capacity_hours=value)


@pytest.mark.parametrize("value", [0, 1, MAX_WEEKLY_CAPACITY_HOURS])
def test_the_bound_admits_both_ends_including_zero(value: int) -> None:
    assert SetCapacityRequest(weekly_capacity_hours=value).weekly_capacity_hours == value


def test_the_field_is_required_with_no_schema_default() -> None:
    """`null` is a VALUE — it clears her hours back to the tenant default — never
    an omission. `AssignTicketRequest.staff_user_id`'s shipped rule: an optional
    field would make a malformed request that dropped the key indistinguishable
    from a deliberate clear.

    `model_validate` rather than the constructor, so the assertion is about the
    WIRE shape and mypy does not refuse to compile a request the server must
    still refuse at runtime."""
    with pytest.raises(ValidationError):
        SetCapacityRequest.model_validate({})
    assert SetCapacityRequest(weekly_capacity_hours=None).weekly_capacity_hours is None


def test_no_other_key_can_be_sent() -> None:
    with pytest.raises(ValidationError):
        SetCapacityRequest.model_validate({"weekly_capacity_hours": 24, "assigned_minutes": 0})


# --- the write, the audit row and the answer (D6, D12) -----------------------


async def test_setting_the_hours_she_already_has_writes_no_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """200 and nothing recorded — F34's D8, F57's D8, F41's D11 and the shipped
    `StaffService.update` rule. A second audit row would claim somebody changed
    a number that did not change."""
    repos = _install(monkeypatch, _Repos())
    repos.staff = _staff_row(hours=24)
    answer = await _set(_service(repos), 24)
    assert answer.weekly_capacity_hours == 24
    assert answer.capacity_is_default is False
    assert repos.audit == []


async def test_the_capacity_audit_row_carries_the_value_it_replaced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ THE `before` IS CAPTURED INTO A LOCAL BEFORE THE WRITE. Move the capture
    after it and `details["from"]` becomes the value that was just written — the
    write stamps the new hours onto the very instance being read (see the module
    docstring). `floor/service.py:108-116`'s rule and F41's undo's."""
    repos = _install(monkeypatch, _Repos())
    repos.staff = _staff_row(hours=24)
    actor = _actor()
    await _set(_service(repos), 30, actor=actor)
    assert repos.audit == [
        {
            "action": AuditAction.ATELIER_CAPACITY_SET,
            "actor_id": actor.id,
            "entity": str(SEAMSTRESS_ID),
            "details": {"from": 24, "to": 30},
        }
    ]


async def test_the_audit_row_names_the_acting_staffer_and_the_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    repos.staff = _staff_row(hours=None)
    actor = _actor(StaffRole.OWNER)
    await _set(_service(repos), 12, actor=actor)
    row = repos.audit[0]
    assert row["actor_id"] == actor.id
    assert row["entity"] == str(SEAMSTRESS_ID)
    assert row["details"] == {"from": None, "to": 12}


async def test_clearing_her_hours_records_a_null_and_answers_the_tenant_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`null` CLEARS. The answer is the RESOLVED value (D2), so the console
    immediately renders the boutique's default and says whose it is."""
    repos = _install(monkeypatch, _Repos())
    repos.staff = _staff_row(hours=24)
    answer = await _set(_service(repos), None)
    assert repos.calls["set_weekly_capacity_hours"] == {
        "staff_id": SEAMSTRESS_ID,
        "hours": None,
    }
    assert repos.audit[0]["details"] == {"from": 24, "to": None}
    assert (answer.weekly_capacity_hours, answer.capacity_is_default) == (TENANT_DEFAULT, True)


async def test_a_cleared_row_on_a_boutique_with_no_default_answers_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No bar, «לא הוגדרה קיבולת», and `capacity_is_default` FALSE — there is
    nothing to have defaulted to."""
    repos = _install(monkeypatch, _Repos())
    repos.staff = _staff_row(hours=24)
    answer = await _set(_service(repos), None, tenant_default=None)
    assert (answer.weekly_capacity_hours, answer.capacity_is_default) == (None, False)


async def test_zero_hours_are_hers_and_are_not_the_boutiques(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The route's half of D2's boundary: `0` is "away this week" and it is a
    value she set."""
    repos = _install(monkeypatch, _Repos())
    repos.staff = _staff_row(hours=None)
    answer = await _set(_service(repos), 0)
    assert (answer.weekly_capacity_hours, answer.capacity_is_default) == (0, False)


async def test_the_answer_is_capacity_facts_only_and_never_a_seamstress_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ IT DOES NOT ANSWER A `SeamstressRef` (D6). That model requires both load
    numbers, this path has no aggregate, and the only value a builder could reach
    without buying a second business statement is `(0, 0)` — which would collapse
    her bar and drop her «עומס יתר» word for up to five seconds, on this feature's
    own primary surface, at the moment a manager is looking at it. The console
    already holds both numbers from the last tick and patches only these keys."""
    repos = _install(monkeypatch, _Repos())
    repos.staff = _staff_row(hours=None)
    answer = await _set(_service(repos), 12)
    assert set(answer.model_dump()) == {
        "id",
        "display_name",
        "assignable",
        "weekly_capacity_hours",
        "capacity_is_default",
    }
    assert answer.id == SEAMSTRESS_ID
    assert answer.display_name == "נועה"
    assert answer.assignable is True


async def test_the_write_is_reached_exactly_once_and_after_the_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = _install(monkeypatch, _Repos())
    repos.staff = _staff_row(hours=None)
    await _set(_service(repos), 12)
    assert repos.order == ["staff_by_id", "set_weekly_capacity_hours", "audit"]
    assert repos.calls["staff_by_id"] == SEAMSTRESS_ID
