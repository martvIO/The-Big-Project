"""F39's service against real Postgres as the non-owner app role.

⚠ **THIS MODULE COMMITS INTO A SESSION-SCOPED DATABASE, so no row it commits may
hold a FLOOR ROLE.** `migrated_db` and `app_role_url` are `scope="session"`,
pytest collects alphabetically, and `test_shifts_db.py` sorts BEFORE
`test_migrations.py` — a committed `seamstress` row reddens
`test_adding_the_role_check_validates_existing_rows` there, in a file that never
mentions shifts (`test_atelier_db.py`'s docstring records the same trap and the
same answer). Exiting `tenant_session` IS the commit, so there is nothing to roll
back.

**Nothing here depends on a staffer's STORED role.** The self-or-elevated guard
reads `StaffContext.role`, which is resolved from the session cookie and never
looked up — so the matrix varies the ACTOR's role freely while every committed
`staff_users` row stays `owner` or `shift_manager`.

⚠ **EVERY WEEK IN THIS FILE IS BUILT FROM `_SUNDAY`, NEVER FROM `date.today()`.**
`staff_availability_week_start_check` refuses anything that is not a Sunday, so a
fixture week derived from the day the suite happens to run reds six days out of
seven — with an IntegrityError that names nothing in the diff (the plan's R-D).

Every test mints its own tenant id; nothing here truncates.
"""

import datetime
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.service import StaffContext
from app.db.repositories.availability import AvailabilityRulesRepository
from app.db.repositories.staff_availability import StaffAvailabilityRepository
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.tenant import tenant_session
from app.models.audit_log import AuditLog
from app.models.constants import AuditAction, AvailabilityState, StaffRole
from app.models.staff_availability import StaffAvailability
from app.shifts.schemas import ShiftTemplateInput
from app.shifts.service import (
    NoOpeningHoursError,
    ShiftNotFoundError,
    ShiftsService,
    TemplatesAlreadySeededError,
)
from app.shifts.validation import MAX_TEMPLATES_PER_DAY, TemplateLimitReachedError

pytestmark = pytest.mark.db

# Frozen Jerusalem Sundays plus a clock inside `_CURRENT_WEEK`, so «the current
# week» is deterministic and every derived week is a real Sunday. Asserted rather
# than trusted.
_CURRENT_WEEK = datetime.date(2026, 11, 1)
_NEXT_WEEK = datetime.date(2026, 11, 8)
_WEEK_AFTER = datetime.date(2026, 11, 15)
_PAST_WEEK = datetime.date(2026, 10, 25)
assert all(day.weekday() == 6 for day in (_CURRENT_WEEK, _NEXT_WEEK, _WEEK_AFTER, _PAST_WEEK)), (
    "a fixture week stopped being a Sunday — every db test here would red on a CHECK"
)

# Midday Jerusalem on the Wednesday inside `_CURRENT_WEEK`, so `today_jerusalem`
# lands on the intended date from any host timezone.
_CLOCK = datetime.datetime(2026, 11, 4, 10, 0, tzinfo=datetime.UTC)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    return (
        engine := create_async_engine(app_role_url, poolclass=NullPool),
        async_sessionmaker(engine, expire_on_commit=False),
    )


def _service(factory: async_sessionmaker[AsyncSession]) -> ShiftsService:
    return ShiftsService(factory, clock=lambda: _CLOCK)


def _actor(
    tenant_id: uuid.UUID,
    *,
    staff_id: uuid.UUID | None = None,
    role: str = StaffRole.OWNER.value,
) -> StaffContext:
    return StaffContext(
        id=staff_id or uuid.uuid4(),
        tenant_id=tenant_id,
        email="owner@bella.example",
        display_name="Owner",
        role=role,
    )


async def _seed_staff(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    display_name: str = "Staffer",
    role: str = StaffRole.OWNER.value,
    last_day: datetime.date | None = None,
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
            email=f"shifts-{uuid.uuid4().hex[:10]}@bella.example",
            password_hash="not-a-real-hash",
            display_name=display_name,
            role=role,
        )
        if last_day is not None:
            staff.last_day = last_day
        return staff.id


async def _seed_rules(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    windows: list[tuple[int, int, int]],
) -> None:
    """`(day_of_week, open_hour, close_hour)` — the boutique's opening hours,
    which are the ONLY thing D3's seed reads."""
    async with tenant_session(factory, tenant_id) as session:
        for day, open_hour, close_hour in windows:
            await AvailabilityRulesRepository().insert(
                session,
                tenant_id=tenant_id,
                day_of_week=day,
                open_time=datetime.time(open_hour, 0),
                close_time=datetime.time(close_hour, 0),
                # The slot engine's parallel-appointments number. D3 DROPS it
                # deliberately, so a value here that is not 1 is the test's way of
                # proving no template ever carries it.
                capacity=2,
            )


def _template(
    day_of_week: int = 4,
    label: str = "משמרת בוקר",
    starts: datetime.time = datetime.time(9, 0),
    ends: datetime.time = datetime.time(14, 0),
    sort_order: int = 0,
) -> ShiftTemplateInput:
    return ShiftTemplateInput(
        day_of_week=day_of_week,
        label=label,
        starts_at_time=starts,
        ends_at_time=ends,
        sort_order=sort_order,
    )


async def _answer(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    *,
    staff_user_id: uuid.UUID,
    template_id: uuid.UUID,
    week_start: datetime.date,
) -> None:
    """A live answer, written through the repository — the service's write path
    refuses past and current weeks (D1), and several of these fixtures need
    exactly those."""
    async with tenant_session(factory, tenant_id) as session:
        await StaffAvailabilityRepository().set_state(
            session,
            tenant_id=tenant_id,
            staff_user_id=staff_user_id,
            shift_template_id=template_id,
            week_start=week_start,
            state=AvailabilityState.AVAILABLE.value,
            recorded_by=None,
        )


async def _live_weeks(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, template_id: uuid.UUID
) -> set[datetime.date]:
    async with tenant_session(factory, tenant_id) as session:
        rows = (
            await session.scalars(
                select(StaffAvailability).where(
                    StaffAvailability.tenant_id == tenant_id,
                    StaffAvailability.shift_template_id == template_id,
                    StaffAvailability.deleted_at.is_(None),
                )
            )
        ).all()
    return {row.week_start for row in rows}


async def _audit_actions(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID
) -> list[AuditLog]:
    async with tenant_session(factory, tenant_id) as session:
        return list(
            (
                await session.scalars(
                    select(AuditLog)
                    .where(AuditLog.tenant_id == tenant_id)
                    .order_by(AuditLog.created_at)
                )
            ).all()
        )


# --- D3: the seed ------------------------------------------------------------


async def test_the_seed_writes_one_template_per_opening_hours_row(app_role_url: str) -> None:
    """A boutique whose Sunday is one 09:00–17:00 window gets ONE full-day Sunday
    shift it may then split; one that already entered a split Thursday gets TWO
    Thursday shifts for free.

    ⚠ SATURDAY GETS NOTHING BECAUSE IT HAS NO RULE — emergent from the tenant's
    own data, never a hardcoded Shabbat rule.
    """
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        await _seed_rules(factory, tenant_id, [(0, 9, 17), (4, 10, 14), (4, 16, 21)])
        seeded = await _service(factory).seed_templates(tenant_id, actor=_actor(tenant_id))
        assert seeded.created == 3
        assert [t.day_of_week for t in seeded.templates] == [0, 4, 4]
        assert seeded.templates[0].label == "ראשון 09:00–17:00"
        assert seeded.templates[1].label == "חמישי 10:00–14:00"
        assert seeded.templates[2].label == "חמישי 16:00–21:00"
        # sort_order runs in (day, open_time) order, so the morning precedes the
        # evening without the owner touching anything.
        assert [t.sort_order for t in seeded.templates] == [0, 1, 2]
        assert 6 not in {t.day_of_week for t in seeded.templates}
    finally:
        await engine.dispose()


async def test_a_second_seed_is_refused_and_changes_nothing(app_role_url: str) -> None:
    """The refusal exists to prevent a re-sync silently destroying the owner's
    splits — she splits Thursday, presses a half-remembered button, and gets one
    full-day Thursday back."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    service = _service(factory)
    try:
        await _seed_rules(factory, tenant_id, [(0, 9, 17)])
        await service.seed_templates(tenant_id, actor=_actor(tenant_id))
        await service.create_template(
            tenant_id, actor=_actor(tenant_id), body=_template(day_of_week=0, label="פיצול")
        )
        with pytest.raises(TemplatesAlreadySeededError):
            await service.seed_templates(tenant_id, actor=_actor(tenant_id))
        listed = await service.list_templates(tenant_id, actor=_actor(tenant_id))
        assert {t.label for t in listed.templates} == {"ראשון 09:00–17:00", "פיצול"}
    finally:
        await engine.dispose()


async def test_a_seed_with_no_opening_hours_is_refused(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    try:
        with pytest.raises(NoOpeningHoursError):
            await _service(factory).seed_templates(tenant_id, actor=_actor(tenant_id))
    finally:
        await engine.dispose()


# --- D2 / D4: the editor -----------------------------------------------------


async def test_two_overlapping_templates_on_one_weekday_are_legal(app_role_url: str) -> None:
    """D2, and the one place F39 departs from `validate_weekly_rules`' shape. A
    morning 09:00–14:00 and an afternoon 13:00–20:00 sharing the changeover hour
    is an ordinary split shift; refusing it makes the owner fudge her real
    times."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    service = _service(factory)
    try:
        await service.create_template(
            tenant_id, actor=_actor(tenant_id), body=_template(label="בוקר")
        )
        await service.create_template(
            tenant_id,
            actor=_actor(tenant_id),
            body=_template(
                label="ערב", starts=datetime.time(13, 0), ends=datetime.time(20, 0), sort_order=1
            ),
        )
        listed = await service.list_templates(tenant_id, actor=_actor(tenant_id))
        assert [t.label for t in listed.templates] == ["בוקר", "ערב"]
    finally:
        await engine.dispose()


async def test_the_seventh_template_on_one_day_is_refused(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    service = _service(factory)
    try:
        for index in range(MAX_TEMPLATES_PER_DAY):
            await service.create_template(
                tenant_id, actor=_actor(tenant_id), body=_template(label=f"משמרת {index}")
            )
        with pytest.raises(TemplateLimitReachedError):
            await service.create_template(
                tenant_id, actor=_actor(tenant_id), body=_template(label="שביעית")
            )
        # A different weekday is unaffected — the cap is per day.
        await service.create_template(
            tenant_id, actor=_actor(tenant_id), body=_template(day_of_week=2, label="שלישי")
        )
    finally:
        await engine.dispose()


async def test_a_material_edit_invalidates_future_weeks_and_leaves_the_rest(
    app_role_url: str,
) -> None:
    """⚠ D4's WHOLE RULE IN ONE TEST. Past and current weeks are HISTORY — F40
    may already have published off them — so a material edit reaches strictly
    forward, and the count it reports is the count the confirm dialog predicted."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    service = _service(factory)
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        created = await service.create_template(
            tenant_id, actor=_actor(tenant_id), body=_template()
        )
        for week in (_PAST_WEEK, _CURRENT_WEEK, _NEXT_WEEK, _WEEK_AFTER):
            await _answer(
                factory,
                tenant_id,
                staff_user_id=staff_id,
                template_id=created.id,
                week_start=week,
            )

        # The pre-commit prediction, which is the ONLY route that can answer it.
        predicted = await service.list_templates(tenant_id, actor=_actor(tenant_id))
        assert predicted.templates[0].future_submission_count == 2

        await service.update_template(
            tenant_id,
            created.id,
            actor=_actor(tenant_id),
            body=_template(starts=datetime.time(16, 0), ends=datetime.time(21, 0)),
        )
        assert await _live_weeks(factory, tenant_id, created.id) == {_PAST_WEEK, _CURRENT_WEEK}

        rows = await _audit_actions(factory, tenant_id)
        updated = [r for r in rows if r.action == AuditAction.SHIFT_TEMPLATE_UPDATED.value]
        assert len(updated) == 1
        assert updated[0].details == {"material": True, "invalidated_submissions": 2}
    finally:
        await engine.dispose()


async def test_a_label_only_edit_invalidates_nothing(app_role_url: str) -> None:
    """Renaming «משמרת בוקר» to «בוקר» changes nothing anybody answered, so the
    console opens no confirm dialog and the service deletes no row."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    service = _service(factory)
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        created = await service.create_template(
            tenant_id, actor=_actor(tenant_id), body=_template()
        )
        await _answer(
            factory,
            tenant_id,
            staff_user_id=staff_id,
            template_id=created.id,
            week_start=_NEXT_WEEK,
        )
        await service.update_template(
            tenant_id,
            created.id,
            actor=_actor(tenant_id),
            body=_template(label="בוקר", sort_order=3),
        )
        assert await _live_weeks(factory, tenant_id, created.id) == {_NEXT_WEEK}
        rows = await _audit_actions(factory, tenant_id)
        updated = [r for r in rows if r.action == AuditAction.SHIFT_TEMPLATE_UPDATED.value]
        assert updated[0].details == {"material": False, "invalidated_submissions": 0}
    finally:
        await engine.dispose()


async def test_deleting_a_template_invalidates_its_future_answers(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    service = _service(factory)
    try:
        staff_id = await _seed_staff(factory, tenant_id)
        created = await service.create_template(
            tenant_id, actor=_actor(tenant_id), body=_template()
        )
        for week in (_CURRENT_WEEK, _NEXT_WEEK):
            await _answer(
                factory,
                tenant_id,
                staff_user_id=staff_id,
                template_id=created.id,
                week_start=week,
            )
        assert await service.delete_template(tenant_id, created.id, actor=_actor(tenant_id)) == 1
        assert await _live_weeks(factory, tenant_id, created.id) == {_CURRENT_WEEK}
        assert (await service.list_templates(tenant_id, actor=_actor(tenant_id))).templates == []
        # Gone means gone: a second delete is a 404, not a silent success.
        with pytest.raises(ShiftNotFoundError):
            await service.delete_template(tenant_id, created.id, actor=_actor(tenant_id))
    finally:
        await engine.dispose()


async def test_a_non_elevated_reader_gets_no_invalidation_counts(app_role_url: str) -> None:
    """`None` and not `0`: "not asked" and "no answers exist" are different facts,
    and a `0` would let a later reader build a confirm dialog on a number nobody
    computed. She has no editor and no confirm dialog, so she never pays for the
    aggregate either."""
    engine, factory = _factory(app_role_url)
    tenant_id = uuid.uuid4()
    service = _service(factory)
    try:
        await service.create_template(tenant_id, actor=_actor(tenant_id), body=_template())
        seamstress = _actor(tenant_id, role=StaffRole.SEAMSTRESS.value)
        listed = await service.list_templates(tenant_id, actor=seamstress)
        assert listed.templates[0].future_submission_count is None
    finally:
        await engine.dispose()


async def test_another_tenants_template_is_invisible_to_both_writes(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    service = _service(factory)
    try:
        created = await service.create_template(tenant_a, actor=_actor(tenant_a), body=_template())
        with pytest.raises(ShiftNotFoundError):
            await service.update_template(
                tenant_b, created.id, actor=_actor(tenant_b), body=_template(label="חטיפה")
            )
        with pytest.raises(ShiftNotFoundError):
            await service.delete_template(tenant_b, created.id, actor=_actor(tenant_b))
        assert (await service.list_templates(tenant_a, actor=_actor(tenant_a))).templates[
            0
        ].label == "משמרת בוקר"
    finally:
        await engine.dispose()
