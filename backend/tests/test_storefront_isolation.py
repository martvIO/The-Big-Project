"""Feature 10's rows in the permanent cross-tenant isolation suite — the first
isolation coverage over a PUBLIC surface, and the first over `tenants.name` and
`tenants.settings`.

Every probe below arrives with no session at all, so a leak here would be a leak
to the open internet rather than to a logged-in owner of another boutique. The
tenant comes from the request host and from nowhere else.

Runs as the non-owner boutique_app role over a NullPool engine: the container
superuser bypasses RLS unconditionally, which would make every assertion here
vacuously pass.
"""

import asyncio
import datetime
import time
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.auth.rate_limit import FixedWindowRateLimiter
from app.boutique.service import BoutiqueSettingsService
from app.boutique.validation import WeeklyRuleInput
from app.catalog.service import CatalogService
from app.catalog.validation import VariantInput
from app.db.repositories.tenants import TenantsRepository
from app.main import create_app
from app.models.tenant import Tenant
from app.storage.memory import InMemoryMediaStorage
from app.tenancy.middleware import TenantContext

pytestmark = pytest.mark.db

SLUG_A = "sfa"
SLUG_B = "sfb"

LIST_PATH = "/storefront/dresses"
BOUTIQUE_PATH = "/storefront/boutique"


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    # NullPool: the engine is used from TestClient's own event loop, so no
    # connection may be pooled across loops.
    engine = create_async_engine(app_role_url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _catalog(factory: async_sessionmaker[AsyncSession]) -> CatalogService:
    return CatalogService(
        factory,
        media_storage=InMemoryMediaStorage(),
        presign_rate_limiter=FixedWindowRateLimiter(
            max_attempts=10_000, window_seconds=3600, clock=time.monotonic
        ),
    )


def _boutique(factory: async_sessionmaker[AsyncSession]) -> BoutiqueSettingsService:
    return BoutiqueSettingsService(
        factory,
        terms_rate_limiter=FixedWindowRateLimiter(
            max_attempts=10_000, window_seconds=3600, clock=time.monotonic
        ),
    )


async def _seed(
    factory: async_sessionmaker[AsyncSession],
    *,
    slug: str,
    name: str,
    phone: str,
    address: str,
    opens_at: datetime.time,
) -> Tenant:
    """A tenant with a distinguishable value in every field the public boutique
    page renders — name, profile and hours — so a leak shows up as a concrete
    wrong string rather than as a missing one."""
    tenant = await TenantsRepository(factory).insert(
        slug=f"{slug}-{uuid.uuid4().hex[:8]}", name=name
    )
    boutique = _boutique(factory)
    await boutique.update_settings(
        tenant.id,
        profile={"phone": phone, "address": address, "description": f"{name} story"},
    )
    await boutique.replace_weekly_rules(
        tenant.id,
        [
            WeeklyRuleInput(
                day_of_week=0,
                open_time=opens_at,
                close_time=datetime.time(19, 0),
                capacity=4,
            )
        ],
    )
    return tenant


async def _dress(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, name: str
) -> uuid.UUID:
    service = _catalog(factory)
    view = await service.create_dress(
        tenant_id,
        name=name,
        description=None,
        price_agorot=120_000,
        price_visible=True,
        reserved=False,
        sort_order=0,
    )
    await service.replace_variants(
        tenant_id, view.row.id, [VariantInput(size_label="38", quantity=2, sort_order=0)]
    )
    return view.row.id


def _storefront_app(
    factory: async_sessionmaker[AsyncSession], tenants: dict[str, TenantContext]
) -> FastAPI:
    async def _resolver(slug: str) -> TenantContext | None:
        return tenants.get(slug)

    app = create_app(resolver=_resolver)
    app.state.catalog_service = _catalog(factory)
    app.state.boutique_service = _boutique(factory)
    return app


def _context(tenant: Tenant, slug: str) -> TenantContext:
    return TenantContext(id=tenant.id, slug=slug, name=tenant.name, settings=tenant.settings)


def test_a_public_visitor_never_sees_another_tenants_catalog(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    try:
        tenant_a = asyncio.run(
            _seed(
                factory,
                slug=SLUG_A,
                name="Bella",
                phone="052-1111111",
                address="Dizengoff 1",
                opens_at=datetime.time(10, 0),
            )
        )
        tenant_b = asyncio.run(
            _seed(
                factory,
                slug=SLUG_B,
                name="Camellia",
                phone="052-2222222",
                address="Rothschild 2",
                opens_at=datetime.time(8, 30),
            )
        )
        dress_a = asyncio.run(_dress(factory, tenant_a.id, "Aurora"))
        dress_b = asyncio.run(_dress(factory, tenant_b.id, "Belle"))
        app = _storefront_app(
            factory, {SLUG_A: _context(tenant_a, SLUG_A), SLUG_B: _context(tenant_b, SLUG_B)}
        )

        # No cookie jar, no session: this is the anonymous internet.
        with TestClient(app, base_url=f"http://{SLUG_A}.localtest.me") as client:
            listed = client.get(LIST_PATH)
            foreign = client.get(f"/storefront/dresses/{dress_b}")
            own = client.get(f"/storefront/dresses/{dress_a}")

        assert listed.status_code == 200
        body = listed.json()
        assert [item["id"] for item in body["items"]] == [str(dress_a)]
        assert [item["name"] for item in body["items"]] == ["Aurora"]
        assert str(dress_b) not in listed.text
        assert "Belle" not in listed.text

        # Another tenant's id is indistinguishable from a missing one, by design.
        assert foreign.status_code == 404
        assert foreign.json()["error"]["code"] == "NOT_FOUND"
        assert own.status_code == 200
    finally:
        asyncio.run(engine.dispose())


def test_the_boutique_page_carries_only_the_resolved_tenants_identity(app_role_url: str) -> None:
    """`tenants.name` and `tenants.settings` are platform-scoped columns with no
    RLS behind them — the host-derived context is the ONLY thing scoping them,
    which is exactly why this needs a test on a public surface."""
    engine, factory = _factory(app_role_url)
    try:
        tenant_a = asyncio.run(
            _seed(
                factory,
                slug=SLUG_A,
                name="Bella",
                phone="052-1111111",
                address="Dizengoff 1",
                opens_at=datetime.time(10, 0),
            )
        )
        tenant_b = asyncio.run(
            _seed(
                factory,
                slug=SLUG_B,
                name="Camellia",
                phone="052-2222222",
                address="Rothschild 2",
                opens_at=datetime.time(8, 30),
            )
        )
        asyncio.run(
            _boutique(factory).add_availability_exception(
                tenant_b.id,
                date=datetime.date(2099, 1, 1),
                open_time=None,
                close_time=None,
                note="B only",
            )
        )
        app = _storefront_app(
            factory, {SLUG_A: _context(tenant_a, SLUG_A), SLUG_B: _context(tenant_b, SLUG_B)}
        )

        with TestClient(app, base_url=f"http://{SLUG_A}.localtest.me") as client:
            resp = client.get(BOUTIQUE_PATH)

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Bella"
        assert body["profile"]["phone"] == "052-1111111"
        assert body["profile"]["address"] == "Dizengoff 1"
        assert body["rules"] == [
            {"day_of_week": 0, "open_time": "10:00:00", "close_time": "19:00:00"}
        ]
        assert body["exceptions"] == []
        for needle in ("Camellia", "052-2222222", "Rothschild 2", "B only", "08:30"):
            assert needle not in resp.text
    finally:
        asyncio.run(engine.dispose())


def test_an_archived_dress_leaves_the_public_surface_entirely(app_role_url: str) -> None:
    """Archive is a soft delete, and the storefront must treat it as gone: absent
    from the tenant's OWN list and a 404 on the tenant's OWN detail."""
    engine, factory = _factory(app_role_url)
    try:
        tenant_a = asyncio.run(
            _seed(
                factory,
                slug=SLUG_A,
                name="Bella",
                phone="052-1111111",
                address="Dizengoff 1",
                opens_at=datetime.time(10, 0),
            )
        )
        kept = asyncio.run(_dress(factory, tenant_a.id, "Aurora"))
        archived = asyncio.run(_dress(factory, tenant_a.id, "Camellia"))
        asyncio.run(_catalog(factory).archive_dress(tenant_a.id, archived))
        app = _storefront_app(factory, {SLUG_A: _context(tenant_a, SLUG_A)})

        with TestClient(app, base_url=f"http://{SLUG_A}.localtest.me") as client:
            listed = client.get(LIST_PATH)
            detail = client.get(f"/storefront/dresses/{archived}")

        assert [item["id"] for item in listed.json()["items"]] == [str(kept)]
        assert listed.json()["total"] == 1
        assert detail.status_code == 404
        assert detail.json()["error"]["code"] == "NOT_FOUND"
    finally:
        asyncio.run(engine.dispose())
