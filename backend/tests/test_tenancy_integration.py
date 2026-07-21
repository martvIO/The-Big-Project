import asyncio
import contextlib
import uuid
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.repositories.tenants import TenantsRepository
from app.main import create_app
from app.tenancy.middleware import TenantContext, get_current_tenant
from app.tenancy.resolver import RepositoryTenantResolver

pytestmark = pytest.mark.db


def _setup(app_role_url: str) -> tuple[AsyncEngine, TenantsRepository, FastAPI]:
    # NullPool: connections open/close per use, so the engine created here works
    # inside TestClient's separate event loop without cross-loop pooling issues.
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app = create_app(resolver=RepositoryTenantResolver(factory))

    @app.get("/whoami")
    async def whoami(
        tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    ) -> dict[str, str]:
        return {"tenant_id": str(tenant.id), "slug": tenant.slug}

    return engine, TenantsRepository(factory), app


def test_active_tenant_resolves_end_to_end(app_role_url: str) -> None:
    engine, repo, app = _setup(app_role_url)
    try:
        slug = f"shop-{uuid.uuid4().hex[:8]}"
        tenant = asyncio.run(repo.insert(slug=slug, name="Shop"))
        with TestClient(app, base_url=f"http://{slug}.localtest.me") as client:
            resp = client.get("/whoami")
        assert resp.status_code == 200
        assert resp.json()["tenant_id"] == str(tenant.id)
    finally:
        asyncio.run(engine.dispose())


def test_suspended_and_deleted_tenants_are_404(app_role_url: str) -> None:
    engine, repo, app = _setup(app_role_url)
    try:
        suspended_slug = f"paused-{uuid.uuid4().hex[:8]}"
        deleted_slug = f"gone-{uuid.uuid4().hex[:8]}"
        suspended = asyncio.run(repo.insert(slug=suspended_slug, name="Paused"))
        deleted = asyncio.run(repo.insert(slug=deleted_slug, name="Gone"))
        asyncio.run(repo.suspend(suspended.id))
        asyncio.run(repo.soft_delete(deleted.id))

        bodies = []
        for slug in (suspended_slug, deleted_slug, f"never-{uuid.uuid4().hex[:8]}"):
            with TestClient(app, base_url=f"http://{slug}.localtest.me") as client:
                resp = client.get("/whoami")
            assert resp.status_code == 404
            bodies.append(resp.json())
        # Suspended, deleted, and never-existed are indistinguishable.
        assert bodies[0] == bodies[1] == bodies[2]
    finally:
        asyncio.run(engine.dispose())


def test_reserved_slug_is_404_even_with_a_row(app_role_url: str) -> None:
    engine, repo, app = _setup(app_role_url)
    try:
        # "admin" is a fixed slug (from RESERVED_SLUGS), so re-running just this
        # test against a still-warm container session would collide on the
        # partial unique index — suppress makes the test re-runnable.
        with contextlib.suppress(IntegrityError):
            asyncio.run(repo.insert(slug="admin", name="Sneaky"))
        with TestClient(app, base_url="http://admin.localtest.me") as client:
            assert client.get("/whoami").status_code == 404
    finally:
        asyncio.run(engine.dispose())
