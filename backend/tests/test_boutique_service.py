"""Feature 7 repository + service integration on real Postgres as boutique_app:
CRUD per resource, advisory-locked weekly replace, terms version race with the
fresh-session retry, DB-enforced terms immutability, CHECK rejects, atomic
settings merge under concurrency, and cross-tenant invisibility."""

import asyncio
import datetime
import json
import time
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.boutique.service import (
    BoutiqueSettingsService,
    DuplicateDateError,
    DuplicateNameError,
    NotFoundError,
    TermsThrottledError,
    TermsVersionConflictError,
)
from app.boutique.validation import BoutiqueValidationError, WeeklyRuleInput
from app.db.repositories.appointment_types import AppointmentTypesRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.repositories.terms import TermsVersionsRepository
from app.db.tenant import tenant_session
from app.models.constants import AppointmentAudience
from app.models.terms_version import TermsVersion

pytestmark = pytest.mark.db

STAFF_ID = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")


def _engine(app_role_url: str) -> AsyncEngine:
    # NullPool: the concurrency tests need genuinely separate connections.
    return create_async_engine(app_role_url, poolclass=NullPool)


def _factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


def _service(
    factory: async_sessionmaker[AsyncSession],
    limiter: FixedWindowRateLimiter | None = None,
) -> BoutiqueSettingsService:
    return BoutiqueSettingsService(
        factory,
        terms_rate_limiter=limiter
        or FixedWindowRateLimiter(max_attempts=1000, window_seconds=3600, clock=time.monotonic),
    )


def _rule(day: int, open_h: int, close_h: int, capacity: int = 1) -> WeeklyRuleInput:
    return WeeklyRuleInput(
        day_of_week=day,
        open_time=datetime.time(open_h, 0),
        close_time=datetime.time(close_h, 0),
        capacity=capacity,
    )


async def _create_terms(
    service: BoutiqueSettingsService, tenant_id: uuid.UUID, terms_text: str = "Cancel 48h before."
) -> TermsVersion:
    return await service.create_terms_version(
        tenant_id,
        terms_text=terms_text,
        refundable_until_hours_before=48,
        forfeit_percent=100,
        created_by=STAFF_ID,
    )


# --- settings (tenants.settings JSONB, atomic merge) ---


async def test_settings_roundtrip_and_partial_merge(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"settings-{uuid.uuid4().hex[:8]}", name="Bella")

        initial = await service.get_settings(tenant.id)
        assert initial.profile == {} and initial.toggles == {}

        updated = await service.update_settings(
            tenant.id,
            profile={"phone": "+972-3-555-0100", "description": "Bridal boutique"},
            toggles={"deposits_enabled": True, "brides_only": False},
        )
        assert updated.profile["phone"] == "+972-3-555-0100"
        assert updated.toggles == {"deposits_enabled": True, "brides_only": False}

        # Toggles-only update: the profile key must be left untouched (only the
        # provided keys enter the patch).
        await service.update_settings(tenant.id, toggles={"deposits_enabled": False})
        again = await service.get_settings(tenant.id)
        assert again.profile["phone"] == "+972-3-555-0100"
        assert again.toggles == {"deposits_enabled": False}
    finally:
        await engine.dispose()


async def test_update_settings_rejects_javascript_maps_url(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"xss-{uuid.uuid4().hex[:8]}", name="XSS")
        with pytest.raises(BoutiqueValidationError):
            await service.update_settings(tenant.id, profile={"maps_url": "javascript:alert(1)"})
        unchanged = await service.get_settings(tenant.id)
        assert unchanged.profile == {}
    finally:
        await engine.dispose()


async def test_settings_unknown_tenant_raises_not_found(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    try:
        with pytest.raises(NotFoundError):
            await service.get_settings(uuid.uuid4())
        with pytest.raises(NotFoundError):
            await service.update_settings(uuid.uuid4(), toggles={"brides_only": True})
    finally:
        await engine.dispose()


async def test_merge_settings_preserves_concurrently_written_sibling_key(
    app_role_url: str,
) -> None:
    """The atomic || merge must never clobber a sibling top-level key written by
    a concurrent transaction (E4 will add such keys) — by construction, not luck."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    tenants = TenantsRepository(factory)
    try:
        tenant = await tenants.insert(slug=f"merge-{uuid.uuid4().hex[:8]}", name="Merge")

        async def write_sibling() -> None:
            async with factory() as session, session.begin():
                await session.execute(
                    text(
                        "UPDATE tenants SET settings = settings || CAST(:patch AS jsonb) "
                        "WHERE id = :tenant_id"
                    ),
                    {
                        "patch": json.dumps({"marketing": {"consent_default": True}}),
                        "tenant_id": tenant.id,
                    },
                )

        await asyncio.gather(
            tenants.merge_settings(tenant.id, profile={"phone": "03-555-0100"}),
            write_sibling(),
        )

        refreshed = await tenants.by_id(tenant.id)
        assert refreshed is not None
        assert refreshed.settings["marketing"] == {"consent_default": True}
        assert refreshed.settings["profile"] == {"phone": "03-555-0100"}
    finally:
        await engine.dispose()


# --- appointment types CRUD ---


async def test_appointment_type_crud_lifecycle(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        created = await service.create_appointment_type(tenant, name="Fitting", duration_minutes=60)
        assert created.audience == AppointmentAudience.ALL
        assert created.deposit_required is False
        assert created.deposit_amount_agorot is None
        assert created.sort_order == 0

        listed = await service.list_appointment_types(tenant)
        assert [item.id for item in listed] == [created.id]

        updated = await service.update_appointment_type(
            tenant,
            created.id,
            name="First Fitting",
            duration_minutes=90,
            audience=AppointmentAudience.BRIDES_ONLY,
            deposit_required=True,
            deposit_amount_agorot=20_000,
            sort_order=1,
        )
        assert updated.name == "First Fitting"
        assert updated.duration_minutes == 90
        assert updated.updated_at is not None  # set by the DB trigger

        await service.archive_appointment_type(tenant, created.id)
        assert await service.list_appointment_types(tenant) == []

        # Archiving frees the name for reuse (partial unique index).
        again = await service.create_appointment_type(
            tenant, name="First Fitting", duration_minutes=45
        )
        assert again.id != created.id
    finally:
        await engine.dispose()


async def test_duplicate_active_type_name_raises(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        first = await service.create_appointment_type(tenant, name="Fitting", duration_minutes=60)
        with pytest.raises(DuplicateNameError):
            await service.create_appointment_type(tenant, name="Fitting", duration_minutes=30)
        other = await service.create_appointment_type(tenant, name="Pickup", duration_minutes=15)
        with pytest.raises(DuplicateNameError):
            await service.update_appointment_type(
                tenant,
                other.id,
                name="Fitting",
                duration_minutes=15,
                audience=AppointmentAudience.ALL,
                deposit_required=False,
                deposit_amount_agorot=None,
                sort_order=0,
            )
        assert first.name == "Fitting"
    finally:
        await engine.dispose()


async def test_update_or_archive_missing_type_raises_not_found(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        with pytest.raises(NotFoundError):
            await service.update_appointment_type(
                tenant,
                uuid.uuid4(),
                name="Ghost",
                duration_minutes=30,
                audience=AppointmentAudience.ALL,
                deposit_required=False,
                deposit_amount_agorot=None,
                sort_order=0,
            )
        with pytest.raises(NotFoundError):
            await service.archive_appointment_type(tenant, uuid.uuid4())
    finally:
        await engine.dispose()


# --- weekly rules: atomic replace under the per-tenant advisory lock ---


async def test_weekly_rules_replace_lifecycle(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        first = await service.replace_weekly_rules(tenant, [_rule(0, 9, 12), _rule(0, 12, 17)])
        assert len(first) == 2

        second = await service.replace_weekly_rules(tenant, [_rule(2, 10, 14, capacity=2)])
        assert len(second) == 1

        availability = await service.get_availability(tenant)
        assert [(r.day_of_week, r.capacity) for r in availability.rules] == [(2, 2)]

        # An invalid replacement must leave state untouched.
        with pytest.raises(BoutiqueValidationError):
            await service.replace_weekly_rules(tenant, [_rule(4, 9, 13), _rule(4, 12, 17)])
        untouched = await service.get_availability(tenant)
        assert [(r.day_of_week, r.capacity) for r in untouched.rules] == [(2, 2)]

        # Empty set = closed all week; valid.
        assert await service.replace_weekly_rules(tenant, []) == []
        assert (await service.get_availability(tenant)).rules == []
    finally:
        await engine.dispose()


async def test_concurrent_weekly_replaces_never_union(app_role_url: str) -> None:
    """Two concurrent replaces are serialized by pg_advisory_xact_lock — the
    final state is exactly ONE submitted set, never a union of both."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    set_a = [_rule(0, 9, 12), _rule(1, 9, 12)]
    set_b = [_rule(2, 10, 14), _rule(3, 10, 14), _rule(4, 10, 14)]
    try:
        await asyncio.gather(
            service.replace_weekly_rules(tenant, set_a),
            service.replace_weekly_rules(tenant, set_b),
        )
        final = await service.get_availability(tenant)
        days = sorted(rule.day_of_week for rule in final.rules)
        assert days in ([0, 1], [2, 3, 4]), f"union detected: {days}"
    finally:
        await engine.dispose()


# --- availability exceptions ---


async def test_availability_exceptions_lifecycle(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    closed_day = datetime.date(2026, 9, 23)
    special_day = datetime.date(2026, 9, 24)
    try:
        closed = await service.add_availability_exception(
            tenant, date=closed_day, open_time=None, close_time=None, note="Yom Kippur"
        )
        assert closed.open_time is None and closed.close_time is None

        special = await service.add_availability_exception(
            tenant,
            date=special_day,
            open_time=datetime.time(10, 0),
            close_time=datetime.time(13, 0),
        )
        assert special.open_time == datetime.time(10, 0)

        with pytest.raises(DuplicateDateError):
            await service.add_availability_exception(
                tenant, date=closed_day, open_time=None, close_time=None
            )

        with pytest.raises(BoutiqueValidationError):
            await service.add_availability_exception(
                tenant,
                date=datetime.date(2026, 9, 25),
                open_time=datetime.time(10, 0),
                close_time=None,
            )

        await service.remove_availability_exception(tenant, closed.id)
        remaining = (await service.get_availability(tenant)).exceptions
        assert [item.id for item in remaining] == [special.id]

        with pytest.raises(NotFoundError):
            await service.remove_availability_exception(tenant, closed.id)

        # Removal frees the date for a fresh exception (partial unique index).
        await service.add_availability_exception(
            tenant, date=closed_day, open_time=None, close_time=None
        )
    finally:
        await engine.dispose()


# --- terms versions: sequential, immutable, raced, throttled, paginated ---


async def test_terms_versions_are_sequential_with_history_pagination(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        empty = await service.get_terms_history(tenant)
        assert empty.current is None and empty.versions == [] and empty.total == 0

        for text_body in ("v1 terms", "v2 terms", "v3 terms"):
            await _create_terms(service, tenant, terms_text=text_body)

        history = await service.get_terms_history(tenant)
        assert history.current is not None and history.current.version == 3
        assert [item.version for item in history.versions] == [3, 2, 1]
        assert history.total == 3

        page = await service.get_terms_history(tenant, offset=1, limit=1)
        assert [item.version for item in page.versions] == [2]
        assert page.total == 3
    finally:
        await engine.dispose()


async def test_concurrent_terms_creates_stay_strictly_sequential(app_role_url: str) -> None:
    """The unique-index backstop + fresh-session retry: two racing creates must
    land as versions 1 and 2 — never a gap, never a duplicate, never a 500."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        created = await asyncio.gather(
            _create_terms(service, tenant, terms_text="racer A"),
            _create_terms(service, tenant, terms_text="racer B"),
        )
        assert sorted(item.version for item in created) == [1, 2]
        history = await service.get_terms_history(tenant)
        assert [item.version for item in history.versions] == [2, 1]
    finally:
        await engine.dispose()


class _StaleMaxOnceRepository(TermsVersionsRepository):
    """Serves a stale max exactly once — deterministically forces the unique
    collision so the fresh-session retry path is exercised every run."""

    def __init__(self, stale_reads: int) -> None:
        self._stale_reads = stale_reads

    async def max_version(self, session: AsyncSession, tenant_id: uuid.UUID) -> int:
        if self._stale_reads > 0:
            self._stale_reads -= 1
            return 0
        return await super().max_version(session, tenant_id)


async def test_terms_retry_recomputes_in_a_fresh_session(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        await _create_terms(service, tenant, terms_text="v1")
        # First attempt sees a stale max (0), collides with v1, and must retry
        # in a FRESH tenant_session (the aborted one cannot be reused).
        service._terms = _StaleMaxOnceRepository(stale_reads=1)
        created = await _create_terms(service, tenant, terms_text="v2")
        assert created.version == 2
    finally:
        await engine.dispose()


async def test_terms_second_collision_raises_conflict(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        await _create_terms(service, tenant, terms_text="v1")
        service._terms = _StaleMaxOnceRepository(stale_reads=2)
        with pytest.raises(TermsVersionConflictError):
            await _create_terms(service, tenant, terms_text="doomed")
        history = await service.get_terms_history(tenant)
        assert history.total == 1  # the failed create left nothing behind
    finally:
        await engine.dispose()


async def test_terms_creation_is_throttled_per_tenant(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    limiter = FixedWindowRateLimiter(max_attempts=2, window_seconds=3600, clock=time.monotonic)
    service = _service(factory, limiter=limiter)
    tenant = uuid.uuid4()
    other_tenant = uuid.uuid4()
    try:
        await _create_terms(service, tenant, terms_text="v1")
        await _create_terms(service, tenant, terms_text="v2")
        with pytest.raises(TermsThrottledError):
            await _create_terms(service, tenant, terms_text="v3")
        assert (await service.get_terms_history(tenant)).total == 2
        # The throttle is per-tenant, not global.
        await _create_terms(service, other_tenant, terms_text="other v1")
    finally:
        await engine.dispose()


async def test_terms_update_and_delete_denied_at_the_db(app_role_url: str) -> None:
    """Immutability is structural: app_user holds SELECT + INSERT only, so even
    raw SQL from the app role cannot rewrite accepted policy evidence."""
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant = uuid.uuid4()
    try:
        await _create_terms(service, tenant, terms_text="immutable")

        with pytest.raises(ProgrammingError, match="permission denied"):
            async with tenant_session(factory, tenant) as session:
                await session.execute(text("UPDATE terms_versions SET terms_text = 'tampered'"))

        with pytest.raises(ProgrammingError, match="permission denied"):
            async with tenant_session(factory, tenant) as session:
                await session.execute(text("DELETE FROM terms_versions"))

        history = await service.get_terms_history(tenant)
        assert history.current is not None and history.current.terms_text == "immutable"
    finally:
        await engine.dispose()


# --- CHECK constraints: the DB rejects out-of-bounds financial fields even when
# --- service validation is bypassed ---


async def test_check_constraints_reject_bad_values_below_the_service(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    terms_repo = TermsVersionsRepository()
    types_repo = AppointmentTypesRepository()
    tenant = uuid.uuid4()
    try:
        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant) as session:
                await terms_repo.insert(
                    session,
                    tenant_id=tenant,
                    version=1,
                    terms_text="bad forfeit",
                    refundable_until_hours_before=48,
                    forfeit_percent=150,
                    created_by=STAFF_ID,
                )

        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant) as session:
                await terms_repo.insert(
                    session,
                    tenant_id=tenant,
                    version=1,
                    terms_text="negative hours",
                    refundable_until_hours_before=-1,
                    forfeit_percent=100,
                    created_by=STAFF_ID,
                )

        with pytest.raises(IntegrityError):
            async with tenant_session(factory, tenant) as session:
                await types_repo.insert(
                    session,
                    tenant_id=tenant,
                    name="zero duration",
                    duration_minutes=0,
                    audience=AppointmentAudience.ALL,
                    deposit_required=False,
                    deposit_amount_agorot=None,
                    sort_order=0,
                )
    finally:
        await engine.dispose()


# --- cross-tenant invisibility for every new resource ---


async def test_cross_tenant_invisibility_for_all_new_resources(app_role_url: str) -> None:
    engine = _engine(app_role_url)
    factory = _factory(engine)
    service = _service(factory)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    try:
        appointment = await service.create_appointment_type(
            tenant_a, name="Fitting", duration_minutes=60
        )
        await service.replace_weekly_rules(tenant_a, [_rule(0, 9, 12)])
        exception = await service.add_availability_exception(
            tenant_a, date=datetime.date(2026, 9, 23), open_time=None, close_time=None
        )
        await _create_terms(service, tenant_a)

        # B reads nothing of A's.
        assert await service.list_appointment_types(tenant_b) == []
        availability_b = await service.get_availability(tenant_b)
        assert availability_b.rules == [] and availability_b.exceptions == []
        history_b = await service.get_terms_history(tenant_b)
        assert history_b.current is None and history_b.total == 0

        # B cannot write A's rows.
        with pytest.raises(NotFoundError):
            await service.update_appointment_type(
                tenant_b,
                appointment.id,
                name="Hijack",
                duration_minutes=5,
                audience=AppointmentAudience.ALL,
                deposit_required=False,
                deposit_amount_agorot=None,
                sort_order=0,
            )
        with pytest.raises(NotFoundError):
            await service.archive_appointment_type(tenant_b, appointment.id)
        with pytest.raises(NotFoundError):
            await service.remove_availability_exception(tenant_b, exception.id)
        # B replacing its own rules must not touch A's weekly grid.
        await service.replace_weekly_rules(tenant_b, [_rule(5, 8, 10)])

        # A's data is intact.
        assert [item.id for item in await service.list_appointment_types(tenant_a)] == [
            appointment.id
        ]
        availability_a = await service.get_availability(tenant_a)
        assert [rule.day_of_week for rule in availability_a.rules] == [0]
        assert [item.id for item in availability_a.exceptions] == [exception.id]
        assert (await service.get_terms_history(tenant_a)).total == 1
    finally:
        await engine.dispose()
