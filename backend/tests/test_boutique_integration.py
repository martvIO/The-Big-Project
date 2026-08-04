"""Feature 7 end-to-end on real Postgres as boutique_app: provision-style seed,
owner login via the real AuthService, full configuration through the real
BoutiqueSettingsService, then read everything back."""

import datetime
import time
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth.passwords import hash_password
from app.auth.rate_limit import FixedWindowRateLimiter
from app.auth.service import AuthService
from app.boutique.service import BoutiqueSettingsService
from app.boutique.validation import WeeklyRuleInput
from app.core.config import Settings
from app.db.repositories.staff_users import StaffUsersRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.tenant import tenant_session
from app.models.constants import AppointmentAudience

pytestmark = pytest.mark.db


async def test_owner_configures_boutique_end_to_end(app_role_url: str) -> None:
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        tenants = TenantsRepository(factory)
        tenant = await tenants.insert(slug=f"e2e-{uuid.uuid4().hex[:8]}", name="Bella Bridal")

        email = f"owner-{uuid.uuid4().hex[:8]}@bella.example"
        async with tenant_session(factory, tenant.id) as session:
            await StaffUsersRepository().insert(
                session,
                tenant_id=tenant.id,
                email=email,
                password_hash=hash_password("s3cret-owner-pw"),
                display_name="Owner",
            )

        auth = AuthService(factory, Settings(app_env="dev", session_ttl_seconds=3600))
        staff, token = await auth.login(tenant.id, email, "s3cret-owner-pw")
        assert await auth.resolve_session(tenant.id, token) is not None

        service = BoutiqueSettingsService(
            factory,
            terms_rate_limiter=FixedWindowRateLimiter(
                max_attempts=100, window_seconds=3600, clock=time.monotonic
            ),
        )

        await service.update_settings(
            tenant.id,
            actor=staff,
            profile={
                "phone": "+972-3-555-0100",
                "address": "1 Dizengoff St, Tel Aviv",
                "description": "Bridal boutique",
                "maps_url": "https://maps.example.com/bella",
            },
            toggles={"deposits_enabled": True, "brides_only": False},
        )

        created_type = await service.create_appointment_type(
            tenant.id,
            name="Fitting",
            duration_minutes=60,
            audience=AppointmentAudience.BRIDES_ONLY,
            deposit_required=True,
            deposit_amount_agorot=15000,
            sort_order=1,
        )

        rules = await service.replace_weekly_rules(
            tenant.id,
            [
                WeeklyRuleInput(
                    day_of_week=0,
                    open_time=datetime.time(9, 0),
                    close_time=datetime.time(13, 0),
                ),
                WeeklyRuleInput(
                    day_of_week=0,
                    open_time=datetime.time(14, 0),
                    close_time=datetime.time(18, 0),
                    capacity=2,
                ),
            ],
        )
        assert len(rules) == 2

        exception = await service.add_availability_exception(
            tenant.id,
            date=datetime.date(2026, 9, 23),
            open_time=None,
            close_time=None,
            note="Yom Kippur",
        )

        terms = await service.create_terms_version(
            tenant.id,
            terms_text="Cancel up to 48 hours before your appointment for a full refund.",
            refundable_until_hours_before=48,
            forfeit_percent=50,
            created_by=staff.id,
        )
        assert terms.version == 1

        # --- read everything back ---
        settings = await service.get_settings(tenant.id)
        assert settings.profile["phone"] == "+972-3-555-0100"
        assert settings.toggles == {"deposits_enabled": True, "brides_only": False}

        types = await service.list_appointment_types(tenant.id)
        assert [row.id for row in types] == [created_type.id]
        assert types[0].deposit_amount_agorot == 15000

        availability = await service.get_availability(tenant.id)
        assert [
            (rule.day_of_week, rule.open_time, rule.capacity) for rule in availability.rules
        ] == [
            (0, datetime.time(9, 0), 1),
            (0, datetime.time(14, 0), 2),
        ]
        assert [row.id for row in availability.exceptions] == [exception.id]
        assert availability.exceptions[0].note == "Yom Kippur"

        history = await service.get_terms_history(tenant.id)
        assert history.current is not None and history.current.id == terms.id
        assert history.total == 1
        assert history.versions[0].forfeit_percent == 50
        assert history.versions[0].created_by == staff.id
    finally:
        await engine.dispose()


async def test_list_all_reaches_the_tenants_list_active_hides(app_role_url: str) -> None:
    """D21. `list_active()` filters `deleted_at IS NULL AND status = 'active'`,
    and BOTH excluded states are operator-invoked (`suspend`, `soft_delete` are
    shipped CLI commands). Pinning the retention runner to that enumeration would
    mean a boutique suspended for non-payment, or churned and off-boarded, keeps
    every bride's name, phone, notes and SMS body FOREVER with no clock ever
    applied — which makes "nothing is ever deleted" permanently true for exactly
    the boutiques most likely to hold abandoned data.

    The poller keeps `list_active()`, where skipping a suspended tenant is right:
    a suspended boutique should not be texting.
    """
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        tenants = TenantsRepository(factory)
        live = await tenants.insert(slug=f"live-{uuid.uuid4().hex[:8]}", name="Live")
        suspended = await tenants.insert(slug=f"susp-{uuid.uuid4().hex[:8]}", name="Suspended")
        deleted = await tenants.insert(slug=f"gone-{uuid.uuid4().hex[:8]}", name="Off-boarded")
        assert await tenants.suspend(suspended.id) is True
        assert await tenants.soft_delete(deleted.id) is True

        active_ids = {t.id for t in await tenants.list_active()}
        all_ids = {t.id for t in await tenants.list_all()}

        assert suspended.id not in active_ids
        assert deleted.id not in active_ids
        assert {live.id, suspended.id, deleted.id} <= all_ids
    finally:
        await engine.dispose()
