import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

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
