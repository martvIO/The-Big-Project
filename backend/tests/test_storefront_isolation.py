"""Feature 10's rows in the permanent cross-tenant isolation suite — the first
isolation coverage over a PUBLIC surface, and the first over `tenants.name` and
`tenants.settings`.

Every probe below arrives with no session at all, so a leak here would be a leak
to the open internet rather than to a logged-in owner of another boutique. The
tenant comes from the request host and from nowhere else.

Two halves, as in test_catalog_isolation.py: the repository/service half probes
`StorefrontService` and the repositories it holds directly as tenant B against
tenant A's ids; the endpoint half re-proves the same invariants through HTTP,
where the tenant comes from the host header.

Runs as the non-owner boutique_app role over a NullPool engine: the container
superuser bypasses RLS unconditionally, which would make every assertion here
vacuously pass.
"""

import asyncio
import dataclasses
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
from app.catalog.service import CatalogNotFoundError, CatalogService
from app.catalog.validation import VariantInput
from app.db.repositories.availability import (
    AvailabilityExceptionsRepository,
    AvailabilityRulesRepository,
)
from app.db.repositories.dress_media import DressMediaRepository
from app.db.repositories.dress_variants import DressVariantsRepository
from app.db.repositories.dresses import DressesRepository
from app.db.repositories.tenants import TenantsRepository
from app.db.tenant import tenant_session
from app.main import create_app
from app.models.tenant import Tenant
from app.storage.memory import InMemoryMediaStorage
from app.storefront.service import StorefrontService
from app.tenancy.middleware import TenantContext

pytestmark = pytest.mark.db

SLUG_A = "sfa"
SLUG_B = "sfb"

LIST_PATH = "/storefront/dresses"
BOUTIQUE_PATH = "/storefront/boutique"

# Far future, so the storefront's today-onward cutoff always keeps it: this row
# exists to be found in the WRONG boutique's response, and an exception that
# aged out would make that check vacuous.
EXCEPTION_DATE = datetime.date(2099, 1, 1)


@dataclasses.dataclass(frozen=True)
class _Identity:
    """One boutique's public identity, distinguishable in EVERY field the public
    page renders — name, profile and hours — so a leak shows up as a concrete
    wrong string rather than as a missing one."""

    slug: str
    name: str
    essence: str
    phone: str
    address: str
    instagram: str
    opens_at: datetime.time

    @property
    def needles(self) -> tuple[str, ...]:
        return (
            self.name,
            self.essence,
            self.phone,
            self.address,
            self.instagram,
            self.opens_at.isoformat(),
        )


IDENTITY_A = _Identity(
    slug=SLUG_A,
    name="Bella",
    essence="Bella essence",
    phone="052-1111111",
    address="Dizengoff 1",
    instagram="bella_bridal",
    opens_at=datetime.time(10, 0),
)
IDENTITY_B = _Identity(
    slug=SLUG_B,
    name="Camellia",
    essence="Camellia essence",
    phone="052-2222222",
    address="Rothschild 2",
    instagram="camellia_atelier",
    opens_at=datetime.time(8, 30),
)


def _factory(app_role_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    # NullPool: probes must never share a connection whose lingering tenant
    # context could be mistaken for isolation — and the engine is also used from
    # TestClient's own event loop, so no connection may be pooled across loops.
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


def _storefront(factory: async_sessionmaker[AsyncSession]) -> StorefrontService:
    return StorefrontService(factory, media_storage=InMemoryMediaStorage())


async def _hours(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID, identity: _Identity
) -> None:
    """Hours live in their own tenant-scoped table, so this works for a bare
    uuid — unlike the profile, which is a column on an existing tenants row."""
    await _boutique(factory).replace_weekly_rules(
        tenant_id,
        [
            WeeklyRuleInput(
                day_of_week=0,
                open_time=identity.opens_at,
                close_time=datetime.time(19, 0),
                capacity=4,
            )
        ],
    )


async def _seed(factory: async_sessionmaker[AsyncSession], identity: _Identity) -> Tenant:
    tenants = TenantsRepository(factory)
    tenant = await tenants.insert(
        slug=f"{identity.slug}-{uuid.uuid4().hex[:8]}", name=identity.name
    )
    await _boutique(factory).update_settings(
        tenant.id,
        profile={
            "essence": identity.essence,
            "phone": identity.phone,
            "address": identity.address,
            "instagram": identity.instagram,
            "description": f"{identity.name} story",
        },
    )
    await _hours(factory, tenant.id, identity)
    # RE-READ, and this is load-bearing rather than tidiness. `insert()` returns
    # the row as it was BEFORE update_settings merged the profile into the
    # settings JSONB, so the object above still carries `settings == {}`.
    # _context() copies that field straight onto the TenantContext, and
    # GET /storefront/boutique reads the profile from the context rather than
    # re-SELECTing — so seeding without this returns a blank identity and the
    # both-directions assertion below would compare "" to "" and pass for the
    # wrong reason.
    seeded = await tenants.by_id(tenant.id)
    assert seeded is not None, "the tenant we just inserted must be readable"
    assert seeded.settings.get("profile"), "the seeded profile must reach the tenants row"
    return seeded


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
    # The public routes read through StorefrontService and nothing else — it
    # holds its own repository handles rather than delegating to CatalogService.
    app.state.storefront_service = _storefront(factory)
    return app


def _context(tenant: Tenant, slug: str) -> TenantContext:
    return TenantContext(id=tenant.id, slug=slug, name=tenant.name, settings=tenant.settings)


# --- the repository/service half ---


async def test_storefront_repositories_return_nothing_for_another_tenants_ids(
    app_role_url: str,
) -> None:
    """Every repository handle StorefrontService holds, probed as tenant B
    against tenant A's ids. These methods are the storefront's ENTIRE
    database surface — if one of them ever answered, an anonymous request to
    boutique B would render boutique A."""
    engine, factory = _factory(app_role_url)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    dresses = DressesRepository()
    variants = DressVariantsRepository()
    media = DressMediaRepository()
    rules = AvailabilityRulesRepository()
    exceptions = AvailabilityExceptionsRepository()
    try:
        dress_a = await _dress(factory, tenant_a, "Aurora")
        await _hours(factory, tenant_a, IDENTITY_A)
        await _boutique(factory).add_availability_exception(
            tenant_a, date=EXCEPTION_DATE, open_time=None, close_time=None, note="A only"
        )

        async with tenant_session(factory, tenant_b) as session:
            assert await dresses.by_id(session, tenant_b, dress_a) is None
            assert (
                await dresses.list_page(
                    session, tenant_b, archived=False, search=None, offset=0, limit=100
                )
                == []
            )
            assert await dresses.count(session, tenant_b, archived=False, search=None) == 0
            assert await variants.list_active(session, tenant_b, dress_a) == []
            assert await media.list_ready(session, tenant_b, dress_a) == []
            assert await media.covers_by_dress(session, tenant_b, [dress_a]) == {}
            assert await rules.list_active(session, tenant_b) == []
            # Both shapes: the storefront passes a cutoff, the console does not,
            # and neither may reach across the tenant boundary. The cutoff used
            # here is A's own exception date, so a leak would be admitted by the
            # filter rather than hidden by it.
            assert await exceptions.list_active(session, tenant_b) == []
            assert await exceptions.list_active(session, tenant_b, on_or_after=EXCEPTION_DATE) == []

        # A's rows survived every probe.
        async with tenant_session(factory, tenant_a) as session:
            assert await dresses.count(session, tenant_a, archived=False, search=None) == 1
            assert len(await rules.list_active(session, tenant_a)) == 1
            assert len(await exceptions.list_active(session, tenant_a)) == 1
    finally:
        await engine.dispose()


async def test_storefront_service_reads_are_empty_for_another_tenants_ids(
    app_role_url: str,
) -> None:
    """The three public read paths, bound to tenant B and aimed at tenant A. The
    detail read must be an indistinguishable miss — the same 404 an unknown id
    gets, never a 403 that would confirm the dress exists somewhere."""
    engine, factory = _factory(app_role_url)
    storefront = _storefront(factory)
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    try:
        dress_a = await _dress(factory, tenant_a, "Aurora")
        await _hours(factory, tenant_a, IDENTITY_A)
        await _boutique(factory).add_availability_exception(
            tenant_a, date=EXCEPTION_DATE, open_time=None, close_time=None, note="A only"
        )

        with pytest.raises(CatalogNotFoundError):
            await storefront.get_dress(tenant_b, dress_a)

        page = await storefront.list_dresses(tenant_b)
        assert page.items == []
        assert page.total == 0

        # `name` and `settings` come from the caller's own TenantContext, so the
        # thing under test here is the hours and the exceptions — the only part
        # of this response that is fetched.
        foreign = await storefront.get_boutique(tenant_b, name="Camellia", settings={})
        assert foreign.hours == []
        assert foreign.exceptions == []

        # A's own reads are unaffected — the empties above are isolation, not a
        # broken read path.
        own_page = await storefront.list_dresses(tenant_a)
        assert [item.row.id for item in own_page.items] == [dress_a]
        assert (await storefront.get_dress(tenant_a, dress_a)).row.id == dress_a
        own_boutique = await storefront.get_boutique(tenant_a, name="Bella", settings={})
        assert len(own_boutique.hours) == 1
        assert [row.note for row in own_boutique.exceptions] == ["A only"]
    finally:
        await engine.dispose()


# --- the endpoint half: the same invariants through the HTTP surface ---


def test_a_public_visitor_never_sees_another_tenants_catalog(app_role_url: str) -> None:
    engine, factory = _factory(app_role_url)
    try:
        tenant_a = asyncio.run(_seed(factory, IDENTITY_A))
        tenant_b = asyncio.run(_seed(factory, IDENTITY_B))
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
    """Asserted in BOTH directions, which is what makes it worth the fixture:
    `tenants.name` and `tenants.settings` are platform-scoped columns with no RLS
    behind them, so the host header is the entire control. A one-directional
    check would still pass if the resolver always returned the first tenant."""
    engine, factory = _factory(app_role_url)
    try:
        tenant_a = asyncio.run(_seed(factory, IDENTITY_A))
        tenant_b = asyncio.run(_seed(factory, IDENTITY_B))
        # On B only: an exception is tenant-scoped data fetched per request, so
        # it is the half of this response that RLS — not the host — protects.
        asyncio.run(
            _boutique(factory).add_availability_exception(
                tenant_b.id,
                date=EXCEPTION_DATE,
                open_time=None,
                close_time=None,
                note="B only",
            )
        )
        app = _storefront_app(
            factory, {SLUG_A: _context(tenant_a, SLUG_A), SLUG_B: _context(tenant_b, SLUG_B)}
        )

        with TestClient(app, base_url=f"http://{SLUG_A}.localtest.me") as client:
            from_a = client.get(BOUTIQUE_PATH)
        with TestClient(app, base_url=f"http://{SLUG_B}.localtest.me") as client:
            from_b = client.get(BOUTIQUE_PATH)

        mirrored = ((from_a, IDENTITY_A, IDENTITY_B), (from_b, IDENTITY_B, IDENTITY_A))
        for resp, identity, other in mirrored:
            assert resp.status_code == 200
            body = resp.json()
            assert body["name"] == identity.name
            assert body["essence"] == identity.essence
            assert body["phone"] == identity.phone
            assert body["address"] == identity.address
            assert body["instagram"] == identity.instagram
            assert body["hours"] == [
                {
                    "day_of_week": 0,
                    "open_time": identity.opens_at.isoformat(),
                    "close_time": "19:00:00",
                }
            ]
            for needle in other.needles:
                assert needle not in resp.text, f"{other.name} leaked into {identity.name}"

        assert from_a.json()["exceptions"] == []
        assert [row["note"] for row in from_b.json()["exceptions"]] == ["B only"]
        assert "B only" not in from_a.text
    finally:
        asyncio.run(engine.dispose())


def test_an_archived_dress_leaves_the_public_surface_entirely(app_role_url: str) -> None:
    """Archive is a soft delete, and the storefront must treat it as gone: absent
    from the tenant's OWN list and a 404 on the tenant's OWN detail."""
    engine, factory = _factory(app_role_url)
    try:
        tenant_a = asyncio.run(_seed(factory, IDENTITY_A))
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
