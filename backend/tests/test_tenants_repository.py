import asyncio
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.repositories.tenants import TenantsRepository
from app.models.constants import TenantStatus

pytestmark = pytest.mark.db


def _unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _make(url: str) -> tuple[AsyncEngine, TenantsRepository]:
    engine = create_async_engine(url)
    return engine, TenantsRepository(async_sessionmaker(engine, expire_on_commit=False))


async def test_insert_returns_server_defaults(app_role_url: str) -> None:
    engine, repo = _make(app_role_url)
    try:
        tenant = await repo.insert(slug=_unique_slug("bella"), name="Bella Bridal")
        assert tenant.id is not None
        assert tenant.status == TenantStatus.ACTIVE
        assert tenant.settings == {}
        assert tenant.created_at is not None
        assert tenant.deleted_at is None
    finally:
        await engine.dispose()


async def test_by_slug_returns_active_only(app_role_url: str) -> None:
    engine, repo = _make(app_role_url)
    try:
        slug = _unique_slug("aurora")
        created = await repo.insert(slug=slug, name="Aurora")
        found = await repo.by_slug(slug)
        assert found is not None and found.id == created.id
        assert await repo.by_slug(_unique_slug("missing")) is None
    finally:
        await engine.dispose()


async def test_suspended_tenant_is_not_resolvable(app_role_url: str) -> None:
    engine, repo = _make(app_role_url)
    try:
        slug = _unique_slug("paused")
        tenant = await repo.insert(slug=slug, name="Paused")
        assert await repo.suspend(tenant.id) is True
        assert await repo.by_slug(slug) is None
    finally:
        await engine.dispose()


async def test_by_slug_any_status_resolves_suspended_but_not_deleted(app_role_url: str) -> None:
    """The half `by_slug` deliberately refuses: platform operations that must
    still reach a boutique BECAUSE it is suspended (owner password reset)."""
    engine, repo = _make(app_role_url)
    try:
        slug = _unique_slug("paused")
        tenant = await repo.insert(slug=slug, name="Paused")
        assert await repo.suspend(tenant.id) is True
        found = await repo.by_slug_any_status(slug)
        assert found is not None and found.id == tenant.id
        assert found.status == TenantStatus.SUSPENDED

        assert await repo.soft_delete(tenant.id) is True
        assert await repo.by_slug_any_status(slug) is None
    finally:
        await engine.dispose()


async def test_soft_delete_frees_slug_for_reuse(app_role_url: str) -> None:
    engine, repo = _make(app_role_url)
    try:
        slug = _unique_slug("phoenix")
        first = await repo.insert(slug=slug, name="First")
        assert await repo.soft_delete(first.id) is True
        assert await repo.by_slug(slug) is None
        second = await repo.insert(slug=slug, name="Second")
        assert second.id != first.id
        found = await repo.by_slug(slug)
        assert found is not None and found.name == "Second"
    finally:
        await engine.dispose()


async def test_duplicate_active_slug_rejected(app_role_url: str) -> None:
    engine, repo = _make(app_role_url)
    try:
        slug = _unique_slug("dup")
        await repo.insert(slug=slug, name="One")
        with pytest.raises(IntegrityError):
            await repo.insert(slug=slug, name="Two")
    finally:
        await engine.dispose()


async def test_list_active_excludes_suspended_and_deleted(app_role_url: str) -> None:
    engine, repo = _make(app_role_url)
    try:
        marker = uuid.uuid4().hex[:8]
        active = await repo.insert(slug=f"active-{marker}", name="Active")
        suspended = await repo.insert(slug=f"susp-{marker}", name="Suspended")
        deleted = await repo.insert(slug=f"del-{marker}", name="Deleted")
        await repo.suspend(suspended.id)
        await repo.soft_delete(deleted.id)

        listed_ids = {tenant.id for tenant in await repo.list_active()}
        assert active.id in listed_ids
        assert suspended.id not in listed_ids
        assert deleted.id not in listed_ids
    finally:
        await engine.dispose()


async def test_update_trigger_sets_updated_at(app_role_url: str) -> None:
    engine, repo = _make(app_role_url)
    try:
        tenant = await repo.insert(slug=_unique_slug("trig"), name="Trig")
        assert tenant.updated_at is None
        await repo.suspend(tenant.id)
        suspended = await repo.by_id(tenant.id)
        assert suspended is not None and suspended.updated_at is not None
    finally:
        await engine.dispose()


async def test_a_scheduling_merge_and_a_concurrent_toggles_merge_both_survive(
    app_role_url: str,
) -> None:
    """F39 D6 at the repository. `merge_settings` is ONE atomic
    `settings = settings || :patch::jsonb`, never a Python read-modify-write, so
    a writer of the fifth top-level key cannot clobber a concurrent writer of the
    fourth — and `toggles`' deep merge, which is appended LAST in the `||` chain,
    still wins for its own key."""
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    repo = TenantsRepository(async_sessionmaker(engine, expire_on_commit=False))
    block = {"submission_deadline_day_of_week": 5, "submission_deadline_time": "12:15"}
    try:
        tenant = await repo.insert(slug=_unique_slug("sched"), name="Sched")
        await asyncio.gather(
            repo.merge_settings(tenant.id, scheduling=dict(block)),
            repo.merge_settings(tenant.id, toggles={"deposits_enabled": True}),
        )
        settled = await repo.by_id(tenant.id)
        assert settled is not None
        assert settled.settings["scheduling"] == block
        assert settled.settings["toggles"] == {"deposits_enabled": True}
    finally:
        await engine.dispose()


async def test_a_scheduling_merge_leaves_every_sibling_key_alone(app_role_url: str) -> None:
    """⚠ THE SHALLOW `||` IS SAFE AT THE TOP LEVEL AND NOWHERE ELSE. Four
    sibling keys survive a `scheduling` patch; a PARTIAL `scheduling` object
    would replace the whole key and delete the field it did not name, which is
    why `SchedulingSettingsUpdate` requires both and the service refuses the
    rest."""
    engine, repo = _make(app_role_url)
    try:
        tenant = await repo.insert(slug=_unique_slug("sib"), name="Siblings")
        await repo.merge_settings(
            tenant.id,
            profile={"phone": "+972-3-555-0100"},
            atelier={"default_weekly_capacity_hours": 36},
            privacy={"published": True},
        )
        await repo.merge_settings(
            tenant.id,
            scheduling={"submission_deadline_day_of_week": 3, "submission_deadline_time": "18:00"},
        )
        settled = await repo.by_id(tenant.id)
        assert settled is not None
        assert settled.settings["profile"] == {"phone": "+972-3-555-0100"}
        assert settled.settings["atelier"] == {"default_weekly_capacity_hours": 36}
        assert settled.settings["privacy"] == {"published": True}
        assert settled.settings["scheduling"]["submission_deadline_time"] == "18:00"

        # And the other direction: a later PARTIAL patch really does delete —
        # asserted so nobody "fixes" the whole-block rule by relaxing it.
        await repo.merge_settings(tenant.id, scheduling={"submission_deadline_time": "09:00"})
        after = await repo.by_id(tenant.id)
        assert after is not None
        assert after.settings["scheduling"] == {"submission_deadline_time": "09:00"}
    finally:
        await engine.dispose()
